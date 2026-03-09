from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any


def _parse_ts(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _coerce_now(value: object) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    parsed = _parse_ts(value)
    if parsed is not None:
        return parsed
    return datetime.now(timezone.utc)


def confidence_badge(confidence: str | None) -> str:
    normalized = str(confidence or "").strip().lower()
    if normalized == "confirmed":
        return "Confirmed"
    if normalized == "likely":
        return "Likely"
    return "Uncertain"


def _freshness_bucket(ts: object, *, now: datetime) -> tuple[str, float | None]:
    parsed = _parse_ts(ts)
    if parsed is None:
        return "unknown", None
    age = now - parsed
    if age < timedelta(0):
        age = timedelta(0)
    age_seconds = age.total_seconds()
    if age <= timedelta(minutes=15):
        return "live", age_seconds
    if age <= timedelta(hours=6):
        return "fresh", age_seconds
    if age <= timedelta(days=2):
        return "recent", age_seconds
    return "stale", age_seconds


def _provenance_state(artifact: dict[str, Any]) -> tuple[bool, bool]:
    provenance = artifact.get("provenance", {}) if isinstance(artifact.get("provenance"), dict) else {}
    rel_path = str(provenance.get("rel_path", "")).strip()
    has_local_provenance = bool(rel_path)
    has_anchor = has_local_provenance and (
        provenance.get("line") is not None or provenance.get("record_index") is not None
    )
    return has_local_provenance, has_anchor


def calibrate_fabric_artifact(
    artifact: dict[str, Any],
    *,
    volatile_sources: set[str] | None = None,
    now: object | None = None,
) -> dict[str, Any]:
    current = _coerce_now(now)
    volatile = str(artifact.get("source", "")).strip().lower() in {
        str(item).strip().lower() for item in (volatile_sources or set())
    }
    verification_status = str(artifact.get("verification_status", "")).strip().lower() or "unverified"
    freshness, age_seconds = _freshness_bucket(artifact.get("ts"), now=current)
    has_local_provenance, has_anchor = _provenance_state(artifact)

    confidence = "uncertain"
    can_claim_done = False
    reasons: list[str] = []
    caveats: list[str] = []
    next_checks: list[str] = []

    if verification_status == "verified":
        reasons.append("artifact carries verified status")
        if has_local_provenance:
            reasons.append("artifact is backed by local provenance")
        if volatile and freshness in {"stale", "unknown"}:
            confidence = "likely" if has_local_provenance else "uncertain"
            caveats.append("current-state source is not fresh enough to treat as established state")
            next_checks.append(f"refresh {artifact.get('source')} before relying on it as current state")
        elif has_local_provenance:
            confidence = "confirmed"
            can_claim_done = True
        else:
            confidence = "likely"
            caveats.append("verified evidence without local provenance should not be treated as confirmed")
    elif verification_status == "partial":
        confidence = "likely" if has_local_provenance else "uncertain"
        reasons.append("artifact has partial verification")
        next_checks.append("complete verification before treating this as settled state")
    elif verification_status in {"failed", "blocked"}:
        reasons.append(f"artifact status is {verification_status}")
        next_checks.append("inspect the underlying receipts before relying on this claim")
    else:
        if has_local_provenance and volatile and freshness in {"live", "fresh"}:
            confidence = "likely"
            reasons.append("fresh current-state evidence is present")
            caveats.append("current-state evidence still needs explicit verification for confirmed claims")
            next_checks.append(f"refresh or verify {artifact.get('source')} before treating it as confirmed")
        elif has_local_provenance and not volatile:
            confidence = "likely"
            reasons.append("artifact has local provenance but no explicit verification")
            next_checks.append("pair this artifact with receipts or validation before making a confirmed claim")
        else:
            reasons.append("artifact lacks enough provenance or verification for a stable claim")
            next_checks.append("gather fresher or verified evidence")

    if not has_local_provenance:
        caveats.append("artifact is missing local provenance")
    if volatile and freshness in {"stale", "unknown"}:
        caveats.append("volatile evidence may already be out of date")
    if freshness == "unknown":
        caveats.append("artifact has no usable timestamp")
    if volatile and confidence == "confirmed" and freshness not in {"live", "fresh", "recent"}:
        confidence = "likely"
        can_claim_done = False

    return {
        "confidence": confidence,
        "trust_badge": confidence_badge(confidence),
        "can_claim_done": can_claim_done,
        "verification_status": verification_status,
        "volatile": volatile,
        "freshness": freshness,
        "age_seconds": age_seconds,
        "has_local_provenance": has_local_provenance,
        "has_anchor": has_anchor,
        "reasons": reasons,
        "caveats": caveats,
        "next_checks": next_checks,
    }


def summarize_calibrated_artifacts(
    artifacts: list[dict[str, Any]],
    *,
    volatile_sources: set[str] | None = None,
    now: object | None = None,
) -> dict[str, Any]:
    counts = {"confirmed": 0, "likely": 0, "uncertain": 0}
    done_claim_ready_count = 0
    stale_current_state_count = 0
    local_provenance_count = 0
    anchored_provenance_count = 0
    fresh_provenance_count = 0

    for artifact in artifacts:
        calibration = calibrate_fabric_artifact(artifact, volatile_sources=volatile_sources, now=now)
        counts[calibration["confidence"]] += 1
        if calibration["can_claim_done"]:
            done_claim_ready_count += 1
        if calibration["volatile"] and calibration["freshness"] in {"stale", "unknown"}:
            stale_current_state_count += 1
        if calibration["has_local_provenance"]:
            local_provenance_count += 1
        if calibration["has_anchor"]:
            anchored_provenance_count += 1
        if calibration["has_local_provenance"] and calibration["freshness"] in {"live", "fresh", "recent"}:
            fresh_provenance_count += 1

    return {
        "confidence_counts": counts,
        "done_claim_ready_count": done_claim_ready_count,
        "stale_current_state_count": stale_current_state_count,
        "local_provenance_count": local_provenance_count,
        "anchored_provenance_count": anchored_provenance_count,
        "fresh_provenance_count": fresh_provenance_count,
    }


def summarize_fabric_posture(summary: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = summary if isinstance(summary, Mapping) else {}
    calibration = payload.get("calibration", {})
    calibration = calibration if isinstance(calibration, Mapping) else {}
    counts = calibration.get("confidence_counts", {})
    counts = counts if isinstance(counts, Mapping) else {}

    confirmed = int(counts.get("confirmed", 0) or 0)
    likely = int(counts.get("likely", 0) or 0)
    uncertain = int(counts.get("uncertain", 0) or 0)
    citation_ready_count = int(payload.get("citation_ready_count", 0) or 0)
    stale_current_state_count = int(calibration.get("stale_current_state_count", 0) or 0)
    done_claim_ready_count = int(calibration.get("done_claim_ready_count", 0) or 0)

    trust = "Uncertain"
    if citation_ready_count > 0 and confirmed > 0 and uncertain == 0 and stale_current_state_count == 0:
        trust = "Confirmed"
    elif citation_ready_count > 0 or confirmed > 0 or likely > 0:
        trust = "Likely"

    warning = ""
    if stale_current_state_count > 0:
        warning = (
            f"Refresh {stale_current_state_count} stale current-state artifact(s) "
            "before treating memory as current proof."
        )
    elif citation_ready_count == 0:
        warning = "Knowledge Fabric has no citation-ready evidence yet; memory claims stay uncertain."

    return {
        "trust": trust,
        "citation_ready_count": citation_ready_count,
        "confirmed_count": confirmed,
        "likely_count": likely,
        "uncertain_count": uncertain,
        "stale_current_state_count": stale_current_state_count,
        "done_claim_ready_count": done_claim_ready_count,
        "warning": warning,
    }
