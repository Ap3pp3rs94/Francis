from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir
from francis.managed_copy_isolation import latest_managed_copy_isolation_verification_for_provision
from francis.managed_copy_provisioning import managed_copy_provision_for_copy
from francis.telemetry.audit import record as audit_record

MANAGED_COPY_SAFE_DELTA_REVIEW_CONTRACT = "stage18_managed_copy_safe_delta_review_v1"
MANAGED_COPY_SAFE_DELTA_REVIEW_RECEIPT_KIND = "francis.stage18.managed_copies.safe_delta_review_receipt"
MANAGED_COPY_SAFE_DELTA_REVIEW_RECEIPTS_KIND = "francis.stage18.managed_copies.safe_delta_review_receipts"

ALLOWED_SAFE_DELTA_SIGNAL_CLASSES = (
    "capability_metadata",
    "policy_hardening_delta",
    "quality_gate_learning",
    "regression_case_summary",
    "performance_signal",
    "class_level_friction_pattern",
    "non_sensitive_outcome_metric",
)
DENIED_SAFE_DELTA_SIGNAL_CLASSES = (
    "raw_customer_artifact",
    "tenant_memory_trace",
    "tenant_receipt_payload",
    "credential_or_connector_secret",
    "support_session_private_context",
    "tenant_identifying_metadata",
)
_CANDIDATE_FIELDS = (
    "signal_fingerprint",
    "summary_fingerprint",
    "lineage_fingerprint",
    "source_record_count",
    "contains_raw_private_data",
    "contains_tenant_identifiers",
    "redaction_review_complete",
    "abstraction_level",
    "retention_class",
)
_ABSTRACTION_LEVELS = {"metadata_only", "class_level", "aggregate"}
_REVIEW_LOCK = threading.Lock()


def managed_copy_safe_delta_review_plan(
    payload: dict[str, Any],
    *,
    actor: str,
    provision_receipt: dict[str, Any],
    isolation_receipt: dict[str, Any],
) -> dict[str, Any]:
    safe_actor = _redacted_text(actor)[:240]
    copy_id = _safe_text(provision_receipt.get("copy_id"))
    tenant_key = _safe_text(provision_receipt.get("tenant_key"))
    provisioning_receipt_id = _safe_text(provision_receipt.get("receipt_id"))
    isolation_receipt_id = _safe_text(isolation_receipt.get("receipt_id"))
    provided_copy_id = _safe_text(payload.get("copy_id"))
    provided_provisioning_receipt_id = _safe_text(payload.get("provisioning_receipt_id"))
    provided_isolation_receipt_id = _safe_text(payload.get("isolation_verification_receipt_id"))
    signal_class = _safe_text(payload.get("signal_class"))
    direction = _safe_text(payload.get("direction"))
    candidate = _mapping(payload.get("candidate"))
    normalized_candidate = {field: candidate.get(field) for field in _CANDIDATE_FIELDS if field in candidate}
    candidate_checks = _candidate_checks(candidate)
    tenant_policy_checks = _tenant_safe_delta_policy_checks(tenant_key)

    blockers: list[str] = []
    if not safe_actor:
        blockers.append("safe_delta_review_actor_missing")
    if not provided_copy_id:
        blockers.append("copy_id_missing")
    if not provided_provisioning_receipt_id:
        blockers.append("copy_provision_receipt_id_missing")
    if not provided_isolation_receipt_id:
        blockers.append("isolation_verification_receipt_id_missing")
    if not provision_receipt:
        blockers.append("copy_provision_receipt_missing_or_mismatch")
    if provision_receipt and provided_copy_id != copy_id:
        blockers.append("copy_id_mismatch")
    if provision_receipt and provided_provisioning_receipt_id != provisioning_receipt_id:
        blockers.append("copy_provision_receipt_id_mismatch")
    if not isolation_receipt or not isolation_receipt.get("live_state_aligned"):
        blockers.append("live_structural_isolation_receipt_required")
    if isolation_receipt and provided_isolation_receipt_id != isolation_receipt_id:
        blockers.append("isolation_verification_receipt_id_mismatch")
    if signal_class in DENIED_SAFE_DELTA_SIGNAL_CLASSES:
        blockers.append("safe_delta_signal_class_denied")
    elif signal_class not in ALLOWED_SAFE_DELTA_SIGNAL_CLASSES:
        blockers.append("safe_delta_signal_class_unknown")
    if direction != "export":
        blockers.append("safe_delta_review_direction_must_be_export")
    blockers.extend(
        _safe_text(check.get("blocker"))
        for check in [*candidate_checks, *tenant_policy_checks]
        if not check.get("ready")
    )
    blockers = [blocker for blocker in blockers if blocker]

    review_fingerprint = (
        _review_fingerprint(
            actor=safe_actor,
            copy_id=copy_id,
            tenant_key=tenant_key,
            provisioning_receipt_id=provisioning_receipt_id,
            isolation_receipt_id=isolation_receipt_id,
            signal_class=signal_class,
            direction=direction,
            candidate=normalized_candidate,
            candidate_checks=candidate_checks,
            tenant_policy_checks=tenant_policy_checks,
        )
        if not blockers
        else ""
    )
    existing_present, existing_receipt = (
        _read_review_receipt_candidate(_review_receipt_path(tenant_key, review_fingerprint))
        if review_fingerprint
        else (False, {})
    )
    existing_matches = bool(
        existing_present
        and _valid_review_receipt(existing_receipt)
        and _safe_text(existing_receipt.get("review_fingerprint")) == review_fingerprint
    )
    ready = not blockers
    return {
        "ok": ready,
        "kind": "francis.stage18.managed_copies.safe_delta_review_plan",
        "contract": MANAGED_COPY_SAFE_DELTA_REVIEW_CONTRACT,
        "status": "safe_delta_review_ready" if ready else "blocked",
        "actor": safe_actor,
        "copy_id": copy_id,
        "tenant_key": tenant_key,
        "provisioning_receipt_id": provisioning_receipt_id,
        "isolation_verification_receipt_id": isolation_receipt_id,
        "signal_class": signal_class,
        "signal_allowed_by_contract": signal_class in ALLOWED_SAFE_DELTA_SIGNAL_CLASSES,
        "signal_denied_by_contract": signal_class in DENIED_SAFE_DELTA_SIGNAL_CLASSES,
        "direction": direction,
        "candidate_field_presence": {field: field in candidate for field in _CANDIDATE_FIELDS},
        "candidate_unknown_field_count": len(set(candidate).difference(_CANDIDATE_FIELDS)),
        "candidate_checks": candidate_checks,
        "candidate_fingerprint": _fingerprint(normalized_candidate) if normalized_candidate else "",
        "tenant_policy_checks": tenant_policy_checks,
        "review_contract_ready": ready,
        "blockers": blockers,
        "review_fingerprint": review_fingerprint,
        "existing_review_matches": existing_matches,
        "normalized_candidate": normalized_candidate if ready else {},
        "dry_run_confirmation": {
            "required_for_recording": True,
            "fingerprint": review_fingerprint,
            "fingerprint_contract": MANAGED_COPY_SAFE_DELTA_REVIEW_CONTRACT,
        },
        "safe_delta_approved": False,
        "safe_delta_exported": False,
        "learning_written": False,
        "writes_receipt": False,
        "writes_tenant_state": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def record_managed_copy_safe_delta_review(
    plan: dict[str, Any],
    *,
    provided_fingerprint: str,
    confirm_review: bool,
) -> dict[str, Any]:
    expected_fingerprint = _safe_text(plan.get("review_fingerprint"))
    if not plan.get("review_contract_ready"):
        return _blocked("blocked_safe_delta_review_contract", "safe_delta_review_contract_not_ready")
    if not confirm_review:
        return _blocked("blocked_safe_delta_review_confirmation", "safe_delta_review_confirmation_required")
    if not expected_fingerprint or _safe_text(provided_fingerprint) != expected_fingerprint:
        return _blocked("blocked_safe_delta_review_dry_run_confirmation", "safe_delta_review_fingerprint_mismatch")

    copy_id = _safe_text(plan.get("copy_id"))
    tenant_key = _safe_text(plan.get("tenant_key"))
    provisioning_receipt_id = _safe_text(plan.get("provisioning_receipt_id"))
    isolation_receipt_id = _safe_text(plan.get("isolation_verification_receipt_id"))
    provision_receipt = managed_copy_provision_for_copy(
        copy_id,
        provisioning_receipt_id=provisioning_receipt_id,
    )
    isolation_receipt = latest_managed_copy_isolation_verification_for_provision(
        provisioning_receipt_id,
        provision_fingerprint=_safe_text(provision_receipt.get("provision_fingerprint")),
        copy_id=copy_id,
    )
    if (
        not provision_receipt
        or not isolation_receipt.get("live_state_aligned")
        or _safe_text(isolation_receipt.get("receipt_id")) != isolation_receipt_id
    ):
        return _blocked("blocked_safe_delta_review_state_drift", "safe_delta_source_boundary_changed_since_dry_run")
    if not all(check.get("ready") for check in _tenant_safe_delta_policy_checks(tenant_key)):
        return _blocked("blocked_safe_delta_review_policy_drift", "safe_delta_tenant_policy_changed_since_dry_run")

    receipt_path = _review_receipt_path(tenant_key, expected_fingerprint)
    with _REVIEW_LOCK:
        existing_result = _existing_review_receipt_result(receipt_path, expected_fingerprint)
        if existing_result is not None:
            return existing_result

        recorded_ts = int(time.time())
        receipt = {
            "ok": True,
            "kind": MANAGED_COPY_SAFE_DELTA_REVIEW_RECEIPT_KIND,
            "contract": MANAGED_COPY_SAFE_DELTA_REVIEW_CONTRACT,
            "receipt_id": f"managed_copy_safe_delta_review_{expected_fingerprint[:16]}",
            "status": "operator_approval_required",
            "actor": _safe_text(plan.get("actor")),
            "copy_id": copy_id,
            "tenant_key": tenant_key,
            "provisioning_receipt_id": provisioning_receipt_id,
            "isolation_verification_receipt_id": isolation_receipt_id,
            "signal_class": _safe_text(plan.get("signal_class")),
            "direction": "export",
            "candidate": dict(_mapping(plan.get("normalized_candidate"))),
            "candidate_fingerprint": _safe_text(plan.get("candidate_fingerprint")),
            "candidate_checks": list(plan.get("candidate_checks") or []),
            "tenant_policy_checks": list(plan.get("tenant_policy_checks") or []),
            "review_fingerprint": expected_fingerprint,
            "safe_delta_approved": False,
            "safe_delta_exported": False,
            "learning_written": False,
            "recorded_ts": recorded_ts,
            "governance": {
                "exact_candidate_schema_enforced": True,
                "raw_candidate_payload_stored": False,
                "tenant_identifiers_stored": False,
                "live_structural_isolation_required": True,
                "tenant_safe_delta_policy_required": True,
                "operator_approval_required_before_export": True,
                "exports_delta": False,
                "writes_learning": False,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
        }
        if not _valid_review_receipt(receipt):
            return _blocked("failed_safe_delta_review_receipt", "safe_delta_review_receipt_invalid")
        try:
            _write_json_atomic(receipt_path, receipt)
        except FileExistsError:
            concurrent_result = _existing_review_receipt_result(receipt_path, expected_fingerprint)
            return concurrent_result or _blocked(
                "blocked_safe_delta_review_receipt_conflict",
                "safe_delta_review_receipt_conflict",
            )
        except OSError:
            return _blocked("failed_safe_delta_review_write", "safe_delta_review_receipt_write_failed")

    audit_record(
        "managed_copies.safe_delta_review_recorded",
        actor=_safe_text(plan.get("actor")),
        copy_id=copy_id,
        tenant_key=tenant_key,
        signal_class=_safe_text(plan.get("signal_class")),
        review_fingerprint=expected_fingerprint,
    )
    return _recorded_result(receipt, status="operator_approval_required", writes_receipt=True)


def managed_copy_safe_delta_review_receipts_readback(*, limit: int = 20) -> dict[str, Any]:
    candidate_count = 0
    invalid_receipt_count = 0
    valid_items: list[dict[str, Any]] = []
    for path in _tenant_roots_path().glob("*/receipts/sd/*.json"):
        present, item = _read_review_receipt_candidate(path)
        if not present:
            continue
        candidate_count += 1
        if _valid_review_receipt(item):
            valid_items.append(item)
        else:
            invalid_receipt_count += 1
    valid_items = sorted(
        valid_items,
        key=lambda item: _safe_int(item.get("recorded_ts")),
        reverse=True,
    )
    live_items = [_with_live_alignment(item) for item in valid_items]
    aligned_items = [item for item in live_items if item.get("live_source_boundary_aligned")]
    latest_valid = live_items[0] if live_items else {}
    receipt_set_valid = invalid_receipt_count == 0
    safe_limit = _safe_limit(limit)
    return {
        "ok": True,
        "kind": MANAGED_COPY_SAFE_DELTA_REVIEW_RECEIPTS_KIND,
        "status": "receipt_validation_failed"
        if invalid_receipt_count
        else "operator_approval_required"
        if aligned_items
        else "source_drift_detected"
        if valid_items
        else "empty",
        "items": live_items[:safe_limit],
        "count": candidate_count,
        "valid_count": len(valid_items),
        "invalid_receipt_count": invalid_receipt_count,
        "invalid_receipts_redacted": bool(invalid_receipt_count),
        "receipt_set_valid": receipt_set_valid,
        "live_aligned_count": len(aligned_items),
        "latest_receipt": latest_valid,
        "latest_receipt_id": _safe_text(latest_valid.get("receipt_id")),
        "latest_receipt_valid": bool(latest_valid),
        "latest_valid_receipt": latest_valid,
        "latest_valid_receipt_id": _safe_text(latest_valid.get("receipt_id")),
        "safe_delta_review_recorded": bool(valid_items and receipt_set_valid),
        "safe_delta_approved": False,
        "safe_delta_exported": False,
        "learning_written": False,
        "writes_receipts": False,
        "writes_tenant_state": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "next_smallest_truthful_gap": (
            "stage18_safe_delta_receipt_remediation"
            if invalid_receipt_count
            else "stage18_safe_delta_operator_approval"
            if aligned_items
            else "stage18_safe_delta_source_boundary_reverification"
            if valid_items
            else "stage18_safe_delta_candidate_review"
        ),
    }


def _candidate_checks(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    unknown_fields = sorted(set(candidate).difference(_CANDIDATE_FIELDS))
    source_record_count = candidate.get("source_record_count")
    return [
        _check(
            "candidate_schema_exact",
            set(candidate) == set(_CANDIDATE_FIELDS),
            "safe_delta_candidate_schema_not_exact" if not unknown_fields else "safe_delta_candidate_unknown_fields",
        ),
        _check(
            "signal_fingerprint_valid",
            _is_sha256(candidate.get("signal_fingerprint")),
            "safe_delta_signal_fingerprint_invalid",
        ),
        _check(
            "summary_fingerprint_valid",
            _is_sha256(candidate.get("summary_fingerprint")),
            "safe_delta_summary_fingerprint_invalid",
        ),
        _check(
            "lineage_fingerprint_valid",
            _is_sha256(candidate.get("lineage_fingerprint")),
            "safe_delta_lineage_fingerprint_invalid",
        ),
        _check(
            "source_record_count_bounded",
            isinstance(source_record_count, int)
            and not isinstance(source_record_count, bool)
            and 1 <= source_record_count <= 1_000_000,
            "safe_delta_source_record_count_invalid",
        ),
        _check(
            "raw_private_data_absent",
            candidate.get("contains_raw_private_data") is False,
            "safe_delta_raw_private_data_must_be_absent",
        ),
        _check(
            "tenant_identifiers_absent",
            candidate.get("contains_tenant_identifiers") is False,
            "safe_delta_tenant_identifiers_must_be_absent",
        ),
        _check(
            "redaction_review_complete",
            candidate.get("redaction_review_complete") is True,
            "safe_delta_redaction_review_required",
        ),
        _check(
            "abstraction_level_allowed",
            _safe_text(candidate.get("abstraction_level")) in _ABSTRACTION_LEVELS,
            "safe_delta_abstraction_level_invalid",
        ),
        _check(
            "retention_review_only",
            _safe_text(candidate.get("retention_class")) == "review_receipt_only",
            "safe_delta_retention_class_must_be_review_receipt_only",
        ),
    ]


def _tenant_safe_delta_policy_checks(tenant_key: str) -> list[dict[str, Any]]:
    config_path = _tenant_root(tenant_key) / "config" / "managed_copy.json"
    config = _read_json(config_path)
    policy = _mapping(config.get("safe_delta_policy"))
    return [
        _check(
            "tenant_safe_delta_policy_present",
            bool(config and policy),
            "tenant_safe_delta_policy_missing",
        ),
        _check(
            "tenant_raw_private_pooling_blocked",
            policy.get("raw_private_pooling_allowed") is False,
            "tenant_raw_private_pooling_must_remain_blocked",
        ),
        _check(
            "tenant_operator_review_required",
            policy.get("operator_review_required") is True,
            "tenant_safe_delta_operator_review_required",
        ),
    ]


def _with_live_alignment(item: dict[str, Any]) -> dict[str, Any]:
    provision = managed_copy_provision_for_copy(
        _safe_text(item.get("copy_id")),
        provisioning_receipt_id=_safe_text(item.get("provisioning_receipt_id")),
    )
    isolation = latest_managed_copy_isolation_verification_for_provision(
        _safe_text(item.get("provisioning_receipt_id")),
        provision_fingerprint=_safe_text(provision.get("provision_fingerprint")),
        copy_id=_safe_text(item.get("copy_id")),
    )
    aligned = bool(
        provision
        and isolation.get("live_state_aligned")
        and _safe_text(isolation.get("receipt_id")) == _safe_text(item.get("isolation_verification_receipt_id"))
        and all(check.get("ready") for check in _tenant_safe_delta_policy_checks(_safe_text(item.get("tenant_key"))))
    )
    return {
        **item,
        "live_source_boundary_aligned": aligned,
        "live_source_boundary_drift_detected": bool(item and not aligned),
    }


def _valid_review_receipt(item: dict[str, Any]) -> bool:
    governance = _mapping(item.get("governance"))
    candidate = _mapping(item.get("candidate"))
    candidate_checks = item.get("candidate_checks")
    tenant_policy_checks = item.get("tenant_policy_checks")
    expected_fingerprint = _review_fingerprint(
        actor=_safe_text(item.get("actor")),
        copy_id=_safe_text(item.get("copy_id")),
        tenant_key=_safe_text(item.get("tenant_key")),
        provisioning_receipt_id=_safe_text(item.get("provisioning_receipt_id")),
        isolation_receipt_id=_safe_text(item.get("isolation_verification_receipt_id")),
        signal_class=_safe_text(item.get("signal_class")),
        direction=_safe_text(item.get("direction")),
        candidate=candidate,
        candidate_checks=candidate_checks if isinstance(candidate_checks, list) else [],
        tenant_policy_checks=tenant_policy_checks if isinstance(tenant_policy_checks, list) else [],
    )
    return (
        _safe_text(item.get("kind")) == MANAGED_COPY_SAFE_DELTA_REVIEW_RECEIPT_KIND
        and _safe_text(item.get("contract")) == MANAGED_COPY_SAFE_DELTA_REVIEW_CONTRACT
        and _safe_text(item.get("receipt_id")).startswith("managed_copy_safe_delta_review_")
        and _safe_text(item.get("status")) == "operator_approval_required"
        and bool(_safe_text(item.get("actor")))
        and _safe_text(item.get("copy_id")).startswith("managed_copy_")
        and _is_sha256(item.get("tenant_key"))
        and _safe_text(item.get("provisioning_receipt_id")).startswith("managed_copy_provision_")
        and _safe_text(item.get("isolation_verification_receipt_id")).startswith("managed_copy_isolation_")
        and _safe_text(item.get("signal_class")) in ALLOWED_SAFE_DELTA_SIGNAL_CLASSES
        and _safe_text(item.get("direction")) == "export"
        and set(candidate) == set(_CANDIDATE_FIELDS)
        and _fingerprint(candidate) == _safe_text(item.get("candidate_fingerprint"))
        and _valid_checks(candidate_checks, expected_ids=(check["id"] for check in _candidate_checks(candidate)))
        and _valid_checks(
            tenant_policy_checks,
            expected_ids=(
                "tenant_safe_delta_policy_present",
                "tenant_raw_private_pooling_blocked",
                "tenant_operator_review_required",
            ),
        )
        and _is_sha256(item.get("review_fingerprint"))
        and _safe_text(item.get("review_fingerprint")) == expected_fingerprint
        and not bool(item.get("safe_delta_approved"))
        and not bool(item.get("safe_delta_exported"))
        and not bool(item.get("learning_written"))
        and _safe_int(item.get("recorded_ts")) > 0
        and bool(governance.get("exact_candidate_schema_enforced"))
        and not bool(governance.get("raw_candidate_payload_stored"))
        and not bool(governance.get("tenant_identifiers_stored"))
        and bool(governance.get("live_structural_isolation_required"))
        and bool(governance.get("tenant_safe_delta_policy_required"))
        and bool(governance.get("operator_approval_required_before_export"))
        and not bool(governance.get("exports_delta"))
        and not bool(governance.get("writes_learning"))
        and not bool(governance.get("grants_execution_authority"))
        and not bool(governance.get("grants_mutation_authority"))
    )


def _valid_checks(value: Any, *, expected_ids: Any) -> bool:
    expected = tuple(expected_ids)
    if not isinstance(value, list) or len(value) != len(expected):
        return False
    return all(
        isinstance(item, dict)
        and _safe_text(item.get("id")) == expected_id
        and item.get("ready") is True
        and _safe_text(item.get("status")) == "ready"
        and not _safe_text(item.get("blocker"))
        for item, expected_id in zip(value, expected, strict=True)
    )


def _review_fingerprint(
    *,
    actor: str,
    copy_id: str,
    tenant_key: str,
    provisioning_receipt_id: str,
    isolation_receipt_id: str,
    signal_class: str,
    direction: str,
    candidate: dict[str, Any],
    candidate_checks: list[dict[str, Any]],
    tenant_policy_checks: list[dict[str, Any]],
) -> str:
    return _fingerprint(
        {
            "contract": MANAGED_COPY_SAFE_DELTA_REVIEW_CONTRACT,
            "actor": actor,
            "copy_id": copy_id,
            "tenant_key": tenant_key,
            "provisioning_receipt_id": provisioning_receipt_id,
            "isolation_verification_receipt_id": isolation_receipt_id,
            "signal_class": signal_class,
            "direction": direction,
            "candidate": candidate,
            "candidate_checks": candidate_checks,
            "tenant_policy_checks": tenant_policy_checks,
        }
    )


def _check(check_id: str, ready: bool, blocker: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "ready": ready,
        "status": "ready" if ready else "blocked",
        "blocker": "" if ready else blocker,
    }


def _recorded_result(receipt: dict[str, Any], *, status: str, writes_receipt: bool) -> dict[str, Any]:
    return {
        "ok": True,
        "status": status,
        "error": "",
        "receipt": receipt,
        "receipt_id": _safe_text(receipt.get("receipt_id")),
        "safe_delta_review_recorded": True,
        "safe_delta_approved": False,
        "safe_delta_exported": False,
        "learning_written": False,
        "writes_receipt": writes_receipt,
        "writes_tenant_state": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def _blocked(status: str, error: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": status,
        "error": error,
        "receipt": None,
        "receipt_id": "",
        "safe_delta_review_recorded": False,
        "safe_delta_approved": False,
        "safe_delta_exported": False,
        "learning_written": False,
        "writes_receipt": False,
        "writes_tenant_state": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def _tenant_roots_path() -> Path:
    return data_dir() / "managed_copies" / "tenants"


def _tenant_root(tenant_key: str) -> Path:
    return _tenant_roots_path() / tenant_key


def _review_receipt_path(tenant_key: str, review_fingerprint: str) -> Path:
    return _tenant_root(tenant_key) / "receipts" / "sd" / f"{review_fingerprint[:16]}.json"


def _read_review_receipt_candidate(path: Path) -> tuple[bool, dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False, {}
    except OSError:
        return True, {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return True, {}
    return True, payload if isinstance(payload, dict) else {}


def _existing_review_receipt_result(
    path: Path,
    expected_fingerprint: str,
) -> dict[str, Any] | None:
    present, existing = _read_review_receipt_candidate(path)
    if not present:
        return None
    if _valid_review_receipt(existing) and _safe_text(existing.get("review_fingerprint")) == expected_fingerprint:
        return _recorded_result(existing, status="already_reviewed", writes_receipt=False)
    return _blocked("blocked_safe_delta_review_receipt_conflict", "safe_delta_review_receipt_conflict")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _is_sha256(value: Any) -> bool:
    text = _safe_text(value)
    return len(text) == 64 and all(character in "0123456789abcdef" for character in text)


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_limit(value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 20
    return min(max(parsed, 1), 500)


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _redacted_text(value: Any) -> str:
    return redact_secret_text(_safe_text(value))
