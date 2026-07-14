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
_CHECK_FIELDS = ("id", "ready", "status", "blocker")
_RECEIPT_FIELDS = (
    "ok",
    "kind",
    "contract",
    "receipt_id",
    "receipt_fingerprint",
    "status",
    "actor",
    "copy_id",
    "tenant_key",
    "provisioning_receipt_id",
    "isolation_verification_receipt_id",
    "signal_class",
    "direction",
    "candidate",
    "candidate_fingerprint",
    "candidate_checks",
    "tenant_policy_checks",
    "review_fingerprint",
    "safe_delta_approved",
    "safe_delta_exported",
    "learning_written",
    "recorded_ts",
    "governance",
)
_GOVERNANCE = {
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
}
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
    review_directory = _guarded_review_directory(
        provision_receipt,
        isolation_receipt,
        create=False,
        require_live=True,
    )
    tenant_root = review_directory.parents[1] if review_directory is not None else None
    tenant_policy_checks = _tenant_safe_delta_policy_checks(tenant_root)

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
    if provision_receipt and isolation_receipt.get("live_state_aligned") and review_directory is None:
        blockers.append("safe_delta_review_path_boundary_invalid")
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
        _read_review_receipt_candidate(_review_receipt_path(review_directory, review_fingerprint))
        if review_fingerprint and review_directory is not None
        else (False, {})
    )
    existing_matches = bool(
        existing_present
        and review_directory is not None
        and _valid_review_receipt(
            existing_receipt,
            path=_review_receipt_path(review_directory, review_fingerprint),
            review_directory=review_directory,
            copy_id=copy_id,
            tenant_key=tenant_key,
            provisioning_receipt_id=provisioning_receipt_id,
            isolation_receipt_id=isolation_receipt_id,
        )
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
        "signal_class": signal_class
        if signal_class in {*ALLOWED_SAFE_DELTA_SIGNAL_CLASSES, *DENIED_SAFE_DELTA_SIGNAL_CLASSES}
        else "unknown",
        "signal_allowed_by_contract": signal_class in ALLOWED_SAFE_DELTA_SIGNAL_CLASSES,
        "signal_denied_by_contract": signal_class in DENIED_SAFE_DELTA_SIGNAL_CLASSES,
        "direction": direction if direction in {"export", "import", "ingest"} else "unknown",
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
    if not _source_lineage_matches(
        provision_receipt,
        isolation_receipt,
        copy_id=copy_id,
        tenant_key=tenant_key,
        provisioning_receipt_id=provisioning_receipt_id,
        isolation_receipt_id=isolation_receipt_id,
        require_live=True,
    ):
        return _blocked("blocked_safe_delta_review_state_drift", "safe_delta_source_boundary_changed_since_dry_run")
    review_directory = _guarded_review_directory(
        provision_receipt,
        isolation_receipt,
        create=False,
        require_live=True,
    )
    if review_directory is None:
        return _blocked("blocked_safe_delta_review_path_boundary", "safe_delta_review_path_boundary_invalid")
    tenant_policy_checks = _tenant_safe_delta_policy_checks(review_directory.parents[1])
    if not all(check.get("ready") for check in tenant_policy_checks):
        return _blocked("blocked_safe_delta_review_policy_drift", "safe_delta_tenant_policy_changed_since_dry_run")

    candidate = dict(_mapping(plan.get("normalized_candidate")))
    candidate_checks = _candidate_checks(candidate)
    current_fingerprint = _review_fingerprint(
        actor=_safe_text(plan.get("actor")),
        copy_id=copy_id,
        tenant_key=tenant_key,
        provisioning_receipt_id=provisioning_receipt_id,
        isolation_receipt_id=isolation_receipt_id,
        signal_class=_safe_text(plan.get("signal_class")),
        direction=_safe_text(plan.get("direction")),
        candidate=candidate,
        candidate_checks=candidate_checks,
        tenant_policy_checks=tenant_policy_checks,
    )
    if not all(check.get("ready") for check in candidate_checks) or current_fingerprint != expected_fingerprint:
        return _blocked("blocked_safe_delta_review_state_drift", "safe_delta_review_plan_changed_since_dry_run")

    review_directory = _guarded_review_directory(
        provision_receipt,
        isolation_receipt,
        create=True,
        require_live=True,
    )
    if review_directory is None:
        return _blocked("blocked_safe_delta_review_path_boundary", "safe_delta_review_path_boundary_invalid")
    receipt_path = _review_receipt_path(review_directory, expected_fingerprint)
    with _REVIEW_LOCK:
        existing_result = _existing_review_receipt_result(
            receipt_path,
            expected_fingerprint,
            review_directory=review_directory,
            copy_id=copy_id,
            tenant_key=tenant_key,
            provisioning_receipt_id=provisioning_receipt_id,
            isolation_receipt_id=isolation_receipt_id,
        )
        if existing_result is not None:
            return existing_result

        recorded_ts = int(time.time())
        receipt = {
            "ok": True,
            "kind": MANAGED_COPY_SAFE_DELTA_REVIEW_RECEIPT_KIND,
            "contract": MANAGED_COPY_SAFE_DELTA_REVIEW_CONTRACT,
            "receipt_id": f"managed_copy_safe_delta_review_{expected_fingerprint[:16]}",
            "receipt_fingerprint": "",
            "status": "operator_approval_required",
            "actor": _safe_text(plan.get("actor")),
            "copy_id": copy_id,
            "tenant_key": tenant_key,
            "provisioning_receipt_id": provisioning_receipt_id,
            "isolation_verification_receipt_id": isolation_receipt_id,
            "signal_class": _safe_text(plan.get("signal_class")),
            "direction": "export",
            "candidate": candidate,
            "candidate_fingerprint": _fingerprint(candidate),
            "candidate_checks": candidate_checks,
            "tenant_policy_checks": tenant_policy_checks,
            "review_fingerprint": expected_fingerprint,
            "safe_delta_approved": False,
            "safe_delta_exported": False,
            "learning_written": False,
            "recorded_ts": recorded_ts,
            "governance": dict(_GOVERNANCE),
        }
        receipt["receipt_fingerprint"] = _receipt_fingerprint(receipt)
        if not _valid_review_receipt(
            receipt,
            path=receipt_path,
            review_directory=review_directory,
            copy_id=copy_id,
            tenant_key=tenant_key,
            provisioning_receipt_id=provisioning_receipt_id,
            isolation_receipt_id=isolation_receipt_id,
        ):
            return _blocked("failed_safe_delta_review_receipt", "safe_delta_review_receipt_invalid")
        try:
            _write_json_atomic(receipt_path, receipt)
        except FileExistsError:
            concurrent_result = _existing_review_receipt_result(
                receipt_path,
                expected_fingerprint,
                review_directory=review_directory,
                copy_id=copy_id,
                tenant_key=tenant_key,
                provisioning_receipt_id=provisioning_receipt_id,
                isolation_receipt_id=isolation_receipt_id,
            )
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


def managed_copy_safe_delta_review_receipts_readback(
    *,
    copy_id: str = "",
    provisioning_receipt_id: str = "",
    isolation_verification_receipt_id: str = "",
    review_fingerprint: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    expected_copy_id = _safe_text(copy_id)
    expected_provisioning_receipt_id = _safe_text(provisioning_receipt_id)
    expected_isolation_receipt_id = _safe_text(isolation_verification_receipt_id)
    expected_review_fingerprint = _safe_text(review_fingerprint)
    if not expected_copy_id or not expected_provisioning_receipt_id or not expected_isolation_receipt_id:
        return _review_receipts_payload(status="lineage_required", limit=limit)
    if expected_review_fingerprint and not _is_sha256(expected_review_fingerprint):
        return _review_receipts_payload(status="review_fingerprint_invalid", limit=limit)

    provision = managed_copy_provision_for_copy(
        expected_copy_id,
        provisioning_receipt_id=expected_provisioning_receipt_id,
    )
    isolation = latest_managed_copy_isolation_verification_for_provision(
        expected_provisioning_receipt_id,
        provision_fingerprint=_safe_text(provision.get("provision_fingerprint")),
        copy_id=expected_copy_id,
    )
    expected_tenant_key = _safe_text(provision.get("tenant_key"))
    if not _source_lineage_matches(
        provision,
        isolation,
        copy_id=expected_copy_id,
        tenant_key=expected_tenant_key,
        provisioning_receipt_id=expected_provisioning_receipt_id,
        isolation_receipt_id=expected_isolation_receipt_id,
        require_live=False,
    ):
        return _review_receipts_payload(status="source_drift_detected", limit=limit)
    review_directory = _guarded_review_directory(
        provision,
        isolation,
        create=False,
        require_live=False,
    )
    if review_directory is None:
        return _review_receipts_payload(status="source_drift_detected", limit=limit)

    candidate_count = 0
    invalid_receipt_count = 0
    valid_candidates: list[tuple[dict[str, Any], Path]] = []
    paths = (
        [_review_receipt_path(review_directory, expected_review_fingerprint)]
        if expected_review_fingerprint
        else list(review_directory.glob("*.json"))
        if review_directory.is_dir()
        else []
    )
    for path in paths:
        present, item = _read_review_receipt_candidate(path)
        if not present:
            continue
        candidate_count += 1
        if _valid_review_receipt(
            item,
            path=path,
            review_directory=review_directory,
            copy_id=expected_copy_id,
            tenant_key=expected_tenant_key,
            provisioning_receipt_id=expected_provisioning_receipt_id,
            isolation_receipt_id=expected_isolation_receipt_id,
        ):
            valid_candidates.append((item, path))
        else:
            invalid_receipt_count += 1
    valid_candidates = sorted(
        valid_candidates,
        key=lambda candidate: _safe_text(candidate[0].get("review_fingerprint")),
        reverse=True,
    )
    live_items = [
        _with_live_alignment(
            item,
            provision_receipt=provision,
            isolation_receipt=isolation,
            review_directory=review_directory,
        )
        for item, _path in valid_candidates
    ]
    aligned_items = [item for item in live_items if item.get("live_source_boundary_aligned")]
    return _review_receipts_payload(
        items=live_items,
        candidate_count=candidate_count,
        invalid_receipt_count=invalid_receipt_count,
        live_aligned_count=len(aligned_items),
        limit=limit,
    )


def _review_receipts_payload(
    *,
    items: list[dict[str, Any]] | None = None,
    candidate_count: int = 0,
    invalid_receipt_count: int = 0,
    live_aligned_count: int = 0,
    status: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    valid_items = items or []
    latest_valid = valid_items[0] if valid_items else {}
    receipt_set_valid = invalid_receipt_count == 0
    if status:
        effective_status = status
    elif invalid_receipt_count:
        effective_status = "receipt_validation_failed"
    elif live_aligned_count:
        effective_status = "operator_approval_required"
    elif valid_items:
        effective_status = "source_drift_detected"
    else:
        effective_status = "empty"
    return {
        "ok": True,
        "kind": MANAGED_COPY_SAFE_DELTA_REVIEW_RECEIPTS_KIND,
        "status": effective_status,
        "items": valid_items[: _safe_limit(limit)],
        "count": candidate_count,
        "valid_count": len(valid_items),
        "invalid_receipt_count": invalid_receipt_count,
        "invalid_receipts_redacted": bool(invalid_receipt_count),
        "receipt_set_valid": receipt_set_valid,
        "live_aligned_count": live_aligned_count,
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
            if live_aligned_count
            else "stage18_safe_delta_source_boundary_reverification"
            if effective_status == "source_drift_detected"
            else "stage18_safe_delta_lineage_query"
            if effective_status in {"lineage_required", "review_fingerprint_invalid"}
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


def _tenant_safe_delta_policy_checks(tenant_root: Path | None) -> list[dict[str, Any]]:
    config = _read_json(tenant_root / "config" / "managed_copy.json") if tenant_root is not None else {}
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


def _with_live_alignment(
    item: dict[str, Any],
    *,
    provision_receipt: dict[str, Any],
    isolation_receipt: dict[str, Any],
    review_directory: Path,
) -> dict[str, Any]:
    current_review_directory = _guarded_review_directory(
        provision_receipt,
        isolation_receipt,
        create=False,
        require_live=True,
    )
    aligned = bool(
        _source_lineage_matches(
            provision_receipt,
            isolation_receipt,
            copy_id=_safe_text(item.get("copy_id")),
            tenant_key=_safe_text(item.get("tenant_key")),
            provisioning_receipt_id=_safe_text(item.get("provisioning_receipt_id")),
            isolation_receipt_id=_safe_text(item.get("isolation_verification_receipt_id")),
            require_live=True,
        )
        and current_review_directory == review_directory
        and all(check.get("ready") for check in _tenant_safe_delta_policy_checks(review_directory.parents[1]))
    )
    return {
        **{field: item[field] for field in _RECEIPT_FIELDS},
        "live_source_boundary_aligned": aligned,
        "live_source_boundary_drift_detected": bool(item and not aligned),
    }


def _valid_review_receipt(
    item: dict[str, Any],
    *,
    path: Path | None = None,
    review_directory: Path | None = None,
    copy_id: str = "",
    tenant_key: str = "",
    provisioning_receipt_id: str = "",
    isolation_receipt_id: str = "",
) -> bool:
    governance = _mapping(item.get("governance"))
    candidate = _mapping(item.get("candidate"))
    candidate_checks = item.get("candidate_checks")
    tenant_policy_checks = item.get("tenant_policy_checks")
    expected_candidate_checks = _candidate_checks(candidate)
    expected_tenant_policy_checks = _ready_tenant_policy_checks()
    expected_fingerprint = _review_fingerprint(
        actor=_safe_text(item.get("actor")),
        copy_id=_safe_text(item.get("copy_id")),
        tenant_key=_safe_text(item.get("tenant_key")),
        provisioning_receipt_id=_safe_text(item.get("provisioning_receipt_id")),
        isolation_receipt_id=_safe_text(item.get("isolation_verification_receipt_id")),
        signal_class=_safe_text(item.get("signal_class")),
        direction=_safe_text(item.get("direction")),
        candidate=candidate,
        candidate_checks=expected_candidate_checks,
        tenant_policy_checks=expected_tenant_policy_checks,
    )
    stored_review_fingerprint = _safe_text(item.get("review_fingerprint"))
    expected_receipt_id = f"managed_copy_safe_delta_review_{stored_review_fingerprint[:16]}"
    path_valid = path is None and review_directory is None
    if path is not None and review_directory is not None:
        expected_path = _review_receipt_path(review_directory, stored_review_fingerprint)
        path_valid = bool(
            path == expected_path
            and path.parent == review_directory
            and not (_path_is_link_like(path) if path.exists() else False)
            and not (_path_is_link_like(review_directory) if review_directory.exists() else False)
            and (_resolved_within(path, review_directory) if path.exists() else True)
        )
    return (
        set(item) == set(_RECEIPT_FIELDS)
        and item.get("ok") is True
        and _safe_text(item.get("kind")) == MANAGED_COPY_SAFE_DELTA_REVIEW_RECEIPT_KIND
        and _safe_text(item.get("contract")) == MANAGED_COPY_SAFE_DELTA_REVIEW_CONTRACT
        and _safe_text(item.get("receipt_id")) == expected_receipt_id
        and _is_sha256(item.get("receipt_fingerprint"))
        and _safe_text(item.get("receipt_fingerprint")) == _receipt_fingerprint(item)
        and _safe_text(item.get("status")) == "operator_approval_required"
        and isinstance(item.get("actor"), str)
        and bool(item["actor"].strip())
        and _safe_text(item.get("copy_id")).startswith("managed_copy_")
        and _is_sha256(item.get("tenant_key"))
        and _safe_text(item.get("provisioning_receipt_id")).startswith("managed_copy_provision_")
        and _safe_text(item.get("isolation_verification_receipt_id")).startswith("managed_copy_isolation_")
        and _safe_text(item.get("signal_class")) in ALLOWED_SAFE_DELTA_SIGNAL_CLASSES
        and _safe_text(item.get("direction")) == "export"
        and set(candidate) == set(_CANDIDATE_FIELDS)
        and _is_sha256(item.get("candidate_fingerprint"))
        and _fingerprint(candidate) == _safe_text(item.get("candidate_fingerprint"))
        and _valid_checks(candidate_checks, expected=expected_candidate_checks)
        and all(check["ready"] for check in expected_candidate_checks)
        and _valid_checks(tenant_policy_checks, expected=expected_tenant_policy_checks)
        and _is_sha256(item.get("review_fingerprint"))
        and stored_review_fingerprint == expected_fingerprint
        and item.get("safe_delta_approved") is False
        and item.get("safe_delta_exported") is False
        and item.get("learning_written") is False
        and isinstance(item.get("recorded_ts"), int)
        and not isinstance(item.get("recorded_ts"), bool)
        and int(item["recorded_ts"]) > 0
        and governance == _GOVERNANCE
        and (not copy_id or _safe_text(item.get("copy_id")) == copy_id)
        and (not tenant_key or _safe_text(item.get("tenant_key")) == tenant_key)
        and (not provisioning_receipt_id or _safe_text(item.get("provisioning_receipt_id")) == provisioning_receipt_id)
        and (
            not isolation_receipt_id
            or _safe_text(item.get("isolation_verification_receipt_id")) == isolation_receipt_id
        )
        and path_valid
    )


def _valid_checks(value: Any, *, expected: list[dict[str, Any]]) -> bool:
    if not isinstance(value, list) or len(value) != len(expected):
        return False
    return all(
        isinstance(item, dict) and set(item) == set(_CHECK_FIELDS) and item == expected_item
        for item, expected_item in zip(value, expected, strict=True)
    )


def _ready_tenant_policy_checks() -> list[dict[str, Any]]:
    return [
        _check("tenant_safe_delta_policy_present", True, "tenant_safe_delta_policy_missing"),
        _check("tenant_raw_private_pooling_blocked", True, "tenant_raw_private_pooling_must_remain_blocked"),
        _check("tenant_operator_review_required", True, "tenant_safe_delta_operator_review_required"),
    ]


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


def _receipt_fingerprint(item: dict[str, Any]) -> str:
    return _fingerprint({field: item.get(field) for field in _RECEIPT_FIELDS if field != "receipt_fingerprint"})


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


def _source_lineage_matches(
    provision_receipt: dict[str, Any],
    isolation_receipt: dict[str, Any],
    *,
    copy_id: str,
    tenant_key: str,
    provisioning_receipt_id: str,
    isolation_receipt_id: str,
    require_live: bool,
) -> bool:
    expected_state_root = f"managed_copies/tenants/{tenant_key}" if _is_sha256(tenant_key) else ""
    return bool(
        provision_receipt
        and isolation_receipt
        and expected_state_root
        and _safe_text(provision_receipt.get("copy_id")) == copy_id
        and _safe_text(provision_receipt.get("tenant_key")) == tenant_key
        and _safe_text(provision_receipt.get("receipt_id")) == provisioning_receipt_id
        and _safe_text(provision_receipt.get("state_root")) == expected_state_root
        and _safe_text(isolation_receipt.get("copy_id")) == copy_id
        and _safe_text(isolation_receipt.get("tenant_key")) == tenant_key
        and _safe_text(isolation_receipt.get("provisioning_receipt_id")) == provisioning_receipt_id
        and _safe_text(isolation_receipt.get("receipt_id")) == isolation_receipt_id
        and _safe_text(isolation_receipt.get("state_root")) == expected_state_root
        and (not require_live or isolation_receipt.get("live_state_aligned") is True)
    )


def _guarded_tenant_root(
    provision_receipt: dict[str, Any],
    isolation_receipt: dict[str, Any],
    *,
    require_live: bool,
) -> Path | None:
    copy_id = _safe_text(provision_receipt.get("copy_id"))
    tenant_key = _safe_text(provision_receipt.get("tenant_key"))
    provisioning_receipt_id = _safe_text(provision_receipt.get("receipt_id"))
    isolation_receipt_id = _safe_text(isolation_receipt.get("receipt_id"))
    if not _source_lineage_matches(
        provision_receipt,
        isolation_receipt,
        copy_id=copy_id,
        tenant_key=tenant_key,
        provisioning_receipt_id=provisioning_receipt_id,
        isolation_receipt_id=isolation_receipt_id,
        require_live=require_live,
    ):
        return None
    tenant_root = data_dir() / Path(_safe_text(provision_receipt.get("state_root")))
    if not tenant_root.is_dir() or _path_is_link_like(tenant_root) or not _resolved_within(tenant_root, data_dir()):
        return None
    return tenant_root


def _guarded_review_directory(
    provision_receipt: dict[str, Any],
    isolation_receipt: dict[str, Any],
    *,
    create: bool,
    require_live: bool = True,
) -> Path | None:
    tenant_root = _guarded_tenant_root(
        provision_receipt,
        isolation_receipt,
        require_live=require_live,
    )
    if tenant_root is None:
        return None
    receipts_directory = tenant_root / "receipts"
    if (
        not receipts_directory.is_dir()
        or _path_is_link_like(receipts_directory)
        or not _resolved_within(receipts_directory, tenant_root)
    ):
        return None
    review_directory = receipts_directory / "sd"
    if _path_is_link_like(review_directory):
        return None
    if create and not review_directory.exists():
        try:
            review_directory.mkdir()
        except FileExistsError:
            pass
        except OSError:
            return None
    if _path_is_link_like(review_directory):
        return None
    if review_directory.exists() and (
        not review_directory.is_dir()
        or _path_is_link_like(review_directory)
        or not _resolved_within(review_directory, receipts_directory)
    ):
        return None
    return review_directory


def _review_receipt_path(review_directory: Path, review_fingerprint: str) -> Path:
    return review_directory / f"{review_fingerprint[:16]}.json"


def _resolved_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return False
    return True


def _path_is_link_like(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction and is_junction())


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
    *,
    review_directory: Path,
    copy_id: str,
    tenant_key: str,
    provisioning_receipt_id: str,
    isolation_receipt_id: str,
) -> dict[str, Any] | None:
    present, existing = _read_review_receipt_candidate(path)
    if not present:
        return None
    if (
        _valid_review_receipt(
            existing,
            path=path,
            review_directory=review_directory,
            copy_id=copy_id,
            tenant_key=tenant_key,
            provisioning_receipt_id=provisioning_receipt_id,
            isolation_receipt_id=isolation_receipt_id,
        )
        and _safe_text(existing.get("review_fingerprint")) == expected_fingerprint
    ):
        return _recorded_result(existing, status="already_reviewed", writes_receipt=False)
    return _blocked("blocked_safe_delta_review_receipt_conflict", "safe_delta_review_receipt_conflict")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    return len(text) == 64 and all(character in "0123456789abcdef" for character in text)


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
