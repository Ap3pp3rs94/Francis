from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from francis.managed_copy_safe_delta_runtime_evidence import (
    SAFE_DELTA_RUNTIME_SOURCE_CONTRACT,
    SAFE_DELTA_RUNTIME_SOURCE_KIND,
    safe_delta_runtime_source_directory,
    verify_safe_delta_runtime_source,
)
from francis.managed_copy_safe_delta_runtime_invocation import (
    SOURCE_ACTION,
    SOURCE_ROUTE,
    _load_artifact_lineage,
    safe_delta_runtime_invocations_readback,
)

CONTRACT = "stage18_managed_copy_safe_delta_runtime_source_recording_v1"
KIND = "francis.stage18.managed_copies.safe_delta_runtime_source_recording"
PREFLIGHT_SCOPE = "managed_copies.safe_delta.runtime_source.preflight"
_INPUT_FIELDS = {
    "request_actor",
    "copy_id",
    "provisioning_receipt_id",
    "isolation_verification_receipt_id",
    "runtime_invocation_receipt_id",
    "runtime_invocation_receipt_fingerprint",
    "runtime_invocation_fingerprint",
    "pilot_lease_id",
    "package_id",
    "pilot_run_id",
    "trace_id",
    "dry_run",
    "source_fingerprint",
    "confirm_source_recording",
}
_LOCK = threading.Lock()


def plan_safe_delta_runtime_source(payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    unknown = sorted(set(payload) - _INPUT_FIELDS)
    request = {
        key: _text(payload.get(key))
        for key in (
            "request_actor",
            "copy_id",
            "provisioning_receipt_id",
            "isolation_verification_receipt_id",
            "runtime_invocation_receipt_id",
            "runtime_invocation_receipt_fingerprint",
            "runtime_invocation_fingerprint",
            "pilot_lease_id",
            "package_id",
            "pilot_run_id",
            "trace_id",
        )
    }
    blockers: list[str] = []
    if unknown:
        blockers.append("safe_delta_runtime_source_unknown_fields")
    if request["request_actor"] != actor or not _identifier(actor):
        blockers.append("safe_delta_runtime_source_actor_lineage_mismatch")
    if payload.get("dry_run") is not True:
        blockers.append("safe_delta_runtime_source_dry_run_true_required")
    if not all(
        _identifier(request[field])
        for field in (
            "request_actor",
            "copy_id",
            "provisioning_receipt_id",
            "isolation_verification_receipt_id",
            "runtime_invocation_receipt_id",
            "pilot_lease_id",
            "package_id",
            "pilot_run_id",
            "trace_id",
        )
    ):
        blockers.append("safe_delta_runtime_source_identifier_invalid")
    if not all(
        _sha(request[field]) for field in ("runtime_invocation_receipt_fingerprint", "runtime_invocation_fingerprint")
    ):
        blockers.append("safe_delta_runtime_source_fingerprint_invalid")
    lineage, blocker = _load_lineage(request)
    if blocker:
        blockers.append(blocker)
    binding = {
        "contract": CONTRACT,
        "actor": actor,
        "request": request,
        "lineage_fingerprint": _fingerprint(_source_lineage(lineage)) if not blockers else "",
    }
    fingerprint = _fingerprint(binding) if not blockers else ""
    provided = _text(payload.get("source_fingerprint"))
    if provided and provided != fingerprint:
        blockers.append("safe_delta_runtime_source_fingerprint_mismatch")
        fingerprint = ""
    return {
        "ok": not blockers,
        "kind": KIND,
        "contract": CONTRACT,
        "status": "source_recording_ready" if not blockers else "blocked",
        "error": "" if not blockers else blockers[0],
        "actor": actor if _identifier(actor) else "",
        "request": request,
        "source_fingerprint": fingerprint,
        "blockers": blockers,
        "dry_run": payload.get("dry_run") is True,
        "writes_receipt": False,
        **_governance(False),
    }


def record_safe_delta_runtime_source(
    plan: dict[str, Any],
    *,
    provided_fingerprint: str,
    confirmed: bool,
    authority: dict[str, Any],
) -> dict[str, Any]:
    if not confirmed:
        return _blocked("safe_delta_runtime_source_confirmation_required")
    expected = _text(plan.get("source_fingerprint"))
    if not expected or provided_fingerprint != expected:
        return _blocked("safe_delta_runtime_source_fingerprint_mismatch")
    if not _valid_authority(authority, plan):
        return _blocked("safe_delta_runtime_source_authority_lineage_invalid")
    with _LOCK:
        current_authority = _reload_authority(plan)
        if current_authority != authority or not _valid_authority(current_authority, plan):
            return _blocked("safe_delta_runtime_source_authority_changed_under_lock")
        request = plan.get("request")
        request = dict(request) if isinstance(request, dict) else {}
        fresh = plan_safe_delta_runtime_source(
            {**request, "dry_run": True, "source_fingerprint": expected, "confirm_source_recording": False},
            actor=_text(plan.get("actor")),
        )
        if not fresh.get("ok") or fresh.get("source_fingerprint") != expected:
            return _blocked("safe_delta_runtime_source_lineage_drift")
        lineage, blocker = _load_lineage(request)
        if blocker:
            return _blocked(blocker)
        receipt = _receipt(fresh, lineage, authority)
        path = safe_delta_runtime_source_directory() / f"{receipt['receipt_id']}.json"
        content = _encode(receipt)
        present, existing = _read(path)
        if present:
            if _valid_existing(existing, path) and _same_binding(existing, receipt):
                verified = verify_safe_delta_runtime_source(
                    _text(existing.get("receipt_id")),
                    _text(existing.get("receipt_fingerprint")),
                )
                if verified.get("valid") is True:
                    return _recorded(existing, writes=False)
            return _blocked("safe_delta_runtime_source_conflict")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            _publish_exclusive(path, content)
        except OSError:
            return _blocked("safe_delta_runtime_source_write_failed")
        present, written = _read(path)
        if not present or written != receipt or not _exact_bytes(path, content) or not _valid_existing(written, path):
            return _cleanup_required(
                "safe_delta_runtime_source_write_verification_failed_after_publication",
                receipt,
                path,
                content,
            )
        current, current_blocker = _load_lineage(request)
        if current_blocker or _source_lineage(current) != _source_lineage(lineage):
            return _cleanup_required(
                "safe_delta_runtime_source_post_write_lineage_drift",
                receipt,
                path,
                content,
            )
        verified = verify_safe_delta_runtime_source(receipt["receipt_id"], receipt["receipt_fingerprint"])
        if verified.get("valid") is not True:
            return _cleanup_required(
                "safe_delta_runtime_source_post_write_verification_failed",
                receipt,
                path,
                content,
            )
        return _recorded(receipt, writes=True)


def _load_lineage(request: dict[str, str]) -> tuple[dict[str, Any], str]:
    from francis.managed_copy_safe_delta import managed_copy_safe_delta_review_receipts_readback
    from francis.managed_copy_safe_delta_approval import managed_copy_safe_delta_decisions_readback

    invocations = safe_delta_runtime_invocations_readback(
        copy_id=request["copy_id"],
        provisioning_receipt_id=request["provisioning_receipt_id"],
        isolation_verification_receipt_id=request["isolation_verification_receipt_id"],
        invocation_fingerprint=request["runtime_invocation_fingerprint"],
        limit=20,
    )
    invocation = invocations.get("latest_valid_receipt")
    invocation = invocation if isinstance(invocation, dict) else {}
    if (
        invocations.get("valid_count") != 1
        or invocation.get("receipt_id") != request["runtime_invocation_receipt_id"]
        or invocation.get("receipt_fingerprint") != request["runtime_invocation_receipt_fingerprint"]
        or invocation.get("pilot_lease_id") != request["pilot_lease_id"]
        or invocation.get("package_id") != request["package_id"]
        or invocation.get("pilot_run_id") != request["pilot_run_id"]
        or invocation.get("trace_id") != request["trace_id"]
        or invocation.get("invocation_result", {}).get("eligible_for_core_review") is not True
    ):
        return {}, "safe_delta_runtime_source_invocation_invalid"
    artifact_request = {
        key: _text(invocation.get(key))
        for key in (
            "copy_id",
            "provisioning_receipt_id",
            "isolation_verification_receipt_id",
            "artifact_plan_fingerprint",
            "export_artifact_receipt_id",
            "export_artifact_receipt_fingerprint",
            "artifact_content_fingerprint",
        )
    }
    artifact_request["request_actor"] = _text(invocation.get("actor"))
    artifact_lineage, blocker = _load_artifact_lineage(artifact_request)
    if blocker:
        return {}, "safe_delta_runtime_source_artifact_lineage_invalid"
    artifact_receipt = artifact_lineage["export_artifact_receipt"]
    review_fingerprint = _text(artifact_receipt.get("review_fingerprint"))
    reviews = managed_copy_safe_delta_review_receipts_readback(
        copy_id=request["copy_id"],
        provisioning_receipt_id=request["provisioning_receipt_id"],
        isolation_verification_receipt_id=request["isolation_verification_receipt_id"],
        review_fingerprint=review_fingerprint,
        limit=20,
    )
    review = reviews.get("latest_valid_receipt")
    review = review if isinstance(review, dict) else {}
    decisions = managed_copy_safe_delta_decisions_readback(
        copy_id=request["copy_id"],
        provisioning_receipt_id=request["provisioning_receipt_id"],
        isolation_verification_receipt_id=request["isolation_verification_receipt_id"],
        review_fingerprint=review_fingerprint,
        limit=20,
    )
    decision = decisions.get("latest_valid_receipt")
    decision = decision if isinstance(decision, dict) else {}
    if (
        reviews.get("receipt_set_valid") is not True
        or review.get("receipt_id") is None
        or decisions.get("safe_delta_approved") is not True
        or decision.get("receipt_id") is None
    ):
        return {}, "safe_delta_runtime_source_review_or_decision_invalid"
    return {
        **artifact_lineage,
        "invocation": invocation,
        "artifact_receipt": artifact_receipt,
        "review": review,
        "decision": decision,
    }, ""


def _source_lineage(lineage: dict[str, Any]) -> dict[str, Any]:
    invocation = lineage.get("invocation", {})
    artifact = lineage.get("artifact_receipt", {})
    review = lineage.get("review", {})
    decision = lineage.get("decision", {})
    return {
        "tenant_key": lineage.get("tenant_key"),
        "copy_id": invocation.get("copy_id"),
        "provisioning_receipt_id": invocation.get("provisioning_receipt_id"),
        "provisioning_receipt_fingerprint": invocation.get("provisioning_receipt_fingerprint"),
        "isolation_verification_receipt_id": invocation.get("isolation_verification_receipt_id"),
        "isolation_verification_receipt_fingerprint": invocation.get("isolation_verification_receipt_fingerprint"),
        "review_receipt_id": review.get("receipt_id"),
        "review_receipt_fingerprint": review.get("receipt_fingerprint"),
        "review_fingerprint": artifact.get("review_fingerprint"),
        "safe_delta_decision_receipt_id": decision.get("receipt_id"),
        "safe_delta_decision_receipt_fingerprint": decision.get("receipt_fingerprint"),
        "export_authorization_decision_receipt_id": artifact.get("authorization_decision_receipt_id"),
        "export_authorization_decision_receipt_fingerprint": artifact.get("authorization_decision_receipt_fingerprint"),
        "artifact_plan_fingerprint": invocation.get("artifact_plan_fingerprint"),
        "export_artifact_receipt_id": invocation.get("export_artifact_receipt_id"),
        "export_artifact_receipt_fingerprint": invocation.get("export_artifact_receipt_fingerprint"),
        "artifact_content_fingerprint": invocation.get("artifact_content_fingerprint"),
        "runtime_invocation_receipt_id": invocation.get("receipt_id"),
        "runtime_invocation_receipt_fingerprint": invocation.get("receipt_fingerprint"),
        "runtime_invocation_fingerprint": invocation.get("invocation_fingerprint"),
        "runtime_invocation_result_fingerprint": invocation.get("invocation_result_fingerprint"),
        "signal_class": review.get("signal_class"),
    }


def _receipt(plan: dict[str, Any], lineage: dict[str, Any], authority: dict[str, Any]) -> dict[str, Any]:
    source = {
        "kind": SAFE_DELTA_RUNTIME_SOURCE_KIND,
        "contract": SAFE_DELTA_RUNTIME_SOURCE_CONTRACT,
        "receipt_id": f"managed_copy_safe_delta_runtime_source_{plan['source_fingerprint'][:16]}",
        "status": "exported",
        "evidence_class": "canonical_runtime",
        "actor": plan["actor"],
        **_source_lineage(lineage),
        "pilot_lease_id": authority["lease_id"],
        "package_id": authority["package_id"],
        "package_fingerprint": authority["package_fingerprint"],
        "pilot_run_id": authority["pilot_run_id"],
        "operator_decision_fingerprint": authority["operator_decision_fingerprint"],
        "invocation_lease_authority_fingerprint": authority["consumed_prefix_fingerprints"][0],
        "source_lease_authority_fingerprint": authority["lease_authority_fingerprint"],
        "authority_route": SOURCE_ROUTE,
        "authority_method": "POST",
        "authority_action": SOURCE_ACTION,
        "trace_id": plan["request"]["trace_id"],
        "fixture_only": False,
        "runtime_gate_ready": True,
        "recorded_at_unix_ms": int(time.time() * 1000),
        "receipt_fingerprint": "",
    }
    source["receipt_fingerprint"] = _fingerprint_without(source, "receipt_fingerprint")
    return source


def _valid_authority(authority: dict[str, Any], plan: dict[str, Any]) -> bool:
    request = plan.get("request")
    request = request if isinstance(request, dict) else {}
    prefixes = authority.get("consumed_prefix_fingerprints")
    return bool(
        authority.get("valid") is True
        and authority.get("actor_id") == plan.get("actor")
        and authority.get("lease_id") == request.get("pilot_lease_id")
        and authority.get("package_id") == request.get("package_id")
        and authority.get("pilot_run_id") == request.get("pilot_run_id")
        and authority.get("operation_consumed_binding_count") == 2
        and isinstance(prefixes, list)
        and len(prefixes) == 2
        and authority.get("lease_authority_fingerprint") == prefixes[1]
        and all(_sha(authority.get(field)) for field in ("package_fingerprint", "operator_decision_fingerprint"))
    )


def _reload_authority(plan: dict[str, Any]) -> dict[str, Any]:
    from francis.managed_copy_pilot_runtime import pilot_runtime_lease_authority_snapshot
    from francis.managed_copy_safe_delta_runtime_invocation import lease_bindings

    request = plan.get("request")
    request = request if isinstance(request, dict) else {}
    return pilot_runtime_lease_authority_snapshot(
        request.get("pilot_lease_id"),
        actor=plan.get("actor"),
        expected_bindings=lease_bindings(),
    )


def _valid_existing(receipt: dict[str, Any], path: Path) -> bool:
    return bool(
        receipt.get("receipt_id")
        and path == safe_delta_runtime_source_directory() / f"{receipt['receipt_id']}.json"
        and receipt.get("receipt_fingerprint") == _fingerprint_without(receipt, "receipt_fingerprint")
    )


def _same_binding(existing: dict[str, Any], expected: dict[str, Any]) -> bool:
    ignored = {"recorded_at_unix_ms", "receipt_fingerprint"}
    return all(existing.get(key) == expected.get(key) for key in set(expected) - ignored)


def _publish_exclusive(path: Path, content: bytes) -> None:
    temp = path.with_name(f".zs-{uuid.uuid4().hex[:8]}.tmp")
    try:
        with temp.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name == "nt":
            os.rename(temp, path)
        else:
            os.link(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _read(path: Path) -> tuple[bool, dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return True, {}
    return True, value if isinstance(value, dict) else {}


def _recorded(receipt: dict[str, Any], *, writes: bool) -> dict[str, Any]:
    return {
        "ok": True,
        "status": "source_recorded" if writes else "already_recorded",
        "error": "",
        "receipt": receipt,
        "receipt_id": receipt["receipt_id"],
        "receipt_fingerprint": receipt["receipt_fingerprint"],
        "writes_receipt": writes,
        **_governance(writes),
    }


def _blocked(error: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "blocked",
        "error": error,
        "receipt": None,
        "receipt_id": "",
        "receipt_fingerprint": "",
        "writes_receipt": False,
        **_governance(False),
    }


def _cleanup_required(error: str, receipt: dict[str, Any], path: Path, content: bytes) -> dict[str, Any]:
    preserved = _exact_bytes(path, content)
    return {
        **_blocked(error),
        "status": "cleanup_required",
        "writes_receipt": preserved,
        "quarantined_receipt_id": receipt["receipt_id"] if preserved else "",
        "quarantined_receipt_fingerprint": receipt["receipt_fingerprint"] if preserved else "",
        "quarantined_receipt_preserved": preserved,
        **_governance(preserved),
    }


def _governance(writes: bool) -> dict[str, Any]:
    return {
        "writes_receipt": writes,
        "canonical_runtime_evidence": writes,
        "runtime_gate_ready": writes,
        "fixture_only": False,
        "writes_tenant_state": False,
        "uses_network": False,
        "uses_connector": False,
        "imports_artifact": False,
        "writes_learning": False,
        "mutates_core": False,
        "uses_docker": False,
        "uses_orb": False,
        "runs_shell": False,
        "runs_git": False,
        "grants_authority": False,
        "records_runtime_evidence": False,
        "closes_stage18": False,
    }


def _encode(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def _exact_bytes(path: Path, expected: bytes) -> bool:
    try:
        return path.read_bytes() == expected
    except OSError:
        return False


def _fingerprint_without(value: dict[str, Any], field: str) -> str:
    return _fingerprint({key: item for key, item in value.items() if key != field})


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _identifier(value: Any) -> str:
    text = value.strip() if type(value) is str else ""
    return text if text and len(text) <= 240 and all(char.isalnum() or char in "._:-" for char in text) else ""


def _sha(value: Any) -> bool:
    return type(value) is str and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
