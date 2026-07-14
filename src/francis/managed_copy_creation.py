from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from collections import deque
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir
from francis.telemetry.audit import record as audit_record

MANAGED_COPY_REQUEST_CONTRACT = "stage18_managed_copy_request_v1"
MANAGED_COPY_REQUEST_RECEIPT_KIND = "francis.stage18.managed_copies.copy_request_receipt"
MANAGED_COPY_REQUEST_RECEIPTS_KIND = "francis.stage18.managed_copies.copy_request_receipts"
MANAGED_COPY_PREFLIGHT_CONTRACT = "stage18_managed_copy_preflight_v2"
MANAGED_COPY_PREFLIGHT_RECEIPT_KIND = "francis.stage18.managed_copies.copy_preflight_receipt"
MANAGED_COPY_PREFLIGHT_RECEIPTS_KIND = "francis.stage18.managed_copies.copy_preflight_receipts"
MANAGED_COPY_CREATION_PLAN_CONTRACT = "stage18_managed_copy_creation_plan_v1"
MANAGED_COPY_CREATION_PLAN_RECEIPT_KIND = "francis.stage18.managed_copies.copy_creation_plan_receipt"
MANAGED_COPY_CREATION_PLAN_RECEIPTS_KIND = "francis.stage18.managed_copies.copy_creation_plan_receipts"

_REQUEST_MAPPING_FIELDS = (
    "tenant_identity",
    "tenant_policy",
    "isolation_profile",
    "capability_lineage",
    "safe_delta_policy",
    "support_boundary",
    "decommission_policy",
)
_ISOLATION_DOMAINS = (
    "tenant_data",
    "tenant_memory",
    "tenant_receipts",
    "tenant_connectors",
    "tenant_capability_packs",
    "tenant_policy",
    "support_operator_authority",
)
_MANAGED_COPY_LAW_CHECK_IDS = (
    "tenant_identity_named",
    "tenant_admin_declared",
    "core_surrender_blocked",
    "privacy_weak_pooling_blocked",
    *(f"{domain}_isolated" for domain in _ISOLATION_DOMAINS),
    "capability_base_lineage_declared",
    "customization_layer_tenant_scoped",
    "raw_private_pooling_blocked",
    "safe_delta_operator_review_required",
    "support_default_denied",
    "support_time_bounded",
    "decommission_export_required",
    "decommission_proof_receipts_required",
)
_REQUEST_WRITE_LOCK = threading.Lock()
_PREFLIGHT_WRITE_LOCK = threading.Lock()
_PLAN_WRITE_LOCK = threading.Lock()
_PLAN_STEP_FIELDS = (
    ("establish_copy_identity", "tenant_identity"),
    ("apply_tenant_policy", "tenant_policy"),
    ("prepare_isolation_boundaries", "isolation_profile"),
    ("bind_capability_lineage", "capability_lineage"),
    ("configure_safe_delta_policy", "safe_delta_policy"),
    ("configure_support_boundary", "support_boundary"),
    ("prepare_decommission_policy", "decommission_policy"),
)


def managed_copy_request_plan(
    payload: dict[str, Any],
    *,
    actor: str,
    stage17_closed: bool,
    stage17_receipt_id: str,
) -> dict[str, Any]:
    safe_actor = _redacted_text(actor)[:240]
    tenant_id, field_presence, field_fingerprints = _request_field_evidence(payload)

    blockers: list[str] = []
    if not stage17_closed:
        blockers.append("stage17_prerequisite_not_closed")
    if not safe_actor:
        blockers.append("request_actor_missing")
    if not tenant_id:
        blockers.append("tenant_id_missing")
    blockers.extend(f"{field}_missing_or_invalid" for field in _REQUEST_MAPPING_FIELDS if not field_presence[field])

    tenant_key = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest() if tenant_id else ""
    fingerprint_evidence = {
        "contract": MANAGED_COPY_REQUEST_CONTRACT,
        "actor": safe_actor,
        "tenant_key": tenant_key,
        "stage17_closure_receipt_id": _safe_text(stage17_receipt_id),
        "request_field_presence": field_presence,
        "request_field_fingerprints": field_fingerprints,
    }
    dry_run_fingerprint = _fingerprint(fingerprint_evidence) if not blockers else ""
    return {
        "ok": not blockers,
        "kind": "francis.stage18.managed_copies.copy_request_plan",
        "contract": MANAGED_COPY_REQUEST_CONTRACT,
        "status": "planned" if not blockers else "blocked",
        "actor": safe_actor,
        "tenant_key": tenant_key,
        "request_known": any(field_presence.values()),
        "request_contract_ready": not blockers,
        "request_field_presence": field_presence,
        "request_field_fingerprints": field_fingerprints,
        "stage17_closed_by_receipt": stage17_closed,
        "stage17_closure_receipt_id": _safe_text(stage17_receipt_id),
        "blockers": blockers,
        "dry_run_fingerprint": dry_run_fingerprint,
        "dry_run_confirmation": {
            "required_for_record": True,
            "fingerprint": dry_run_fingerprint,
            "fingerprint_contract": MANAGED_COPY_REQUEST_CONTRACT,
        },
        "contains_raw_tenant_payload": False,
        "writes_receipt": False,
        "writes_tenant_state": False,
        "creates_copy": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def record_managed_copy_request(
    plan: dict[str, Any],
    *,
    provided_fingerprint: str,
    confirm_request_recording: bool,
) -> dict[str, Any]:
    expected_fingerprint = _safe_text(plan.get("dry_run_fingerprint"))
    if not plan.get("request_contract_ready"):
        return _record_blocked("blocked_copy_request_contract", "copy_request_contract_not_ready", plan)
    if not confirm_request_recording:
        return _record_blocked(
            "blocked_request_recording_confirmation",
            "copy_request_recording_confirmation_required",
            plan,
        )
    if not expected_fingerprint or _safe_text(provided_fingerprint) != expected_fingerprint:
        return _record_blocked("blocked_dry_run_confirmation", "dry_run_fingerprint_mismatch", plan)

    with _REQUEST_WRITE_LOCK:
        existing = _receipt_by_fingerprint(
            expected_fingerprint,
            stage17_receipt_id=_safe_text(plan.get("stage17_closure_receipt_id")),
        )
        if existing:
            return {
                "ok": True,
                "status": "already_recorded",
                "error": "",
                "receipt": existing,
                "receipt_id": _safe_text(existing.get("receipt_id")),
                "copy_request_recorded": True,
                "copy_created": False,
                "writes_receipt": False,
                "writes_tenant_state": False,
                "starts_runtime": False,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            }

        receipt_id = f"managed_copy_request_{uuid.uuid4().hex[:12]}"
        receipt = {
            "ok": True,
            "kind": MANAGED_COPY_REQUEST_RECEIPT_KIND,
            "receipt_id": receipt_id,
            "contract": MANAGED_COPY_REQUEST_CONTRACT,
            "status": "requested",
            "actor": _safe_text(plan.get("actor")),
            "tenant_key": _safe_text(plan.get("tenant_key")),
            "request_fingerprint": expected_fingerprint,
            "request_field_presence": dict(plan.get("request_field_presence") or {}),
            "request_field_fingerprints": dict(plan.get("request_field_fingerprints") or {}),
            "stage17_closure_receipt_id": _safe_text(plan.get("stage17_closure_receipt_id")),
            "request_contract_ready": True,
            "copy_request_recorded": True,
            "copy_created": False,
            "tenant_state_written": False,
            "runtime_started": False,
            "recorded_ts": int(time.time()),
            "governance": {
                "copy_request_receipt": True,
                "permission_checked_by_route": True,
                "dry_run_fingerprint_matched": True,
                "explicit_recording_confirmation": True,
                "stage17_closure_receipt_required": True,
                "contains_raw_tenant_payload": False,
                "does_not_create_copy": True,
                "does_not_write_tenant_state": True,
                "does_not_start_runtime": True,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
        }
        _append_jsonl(_request_receipts_path(), receipt)

    audit_record(
        "managed_copies.copy_request_recorded",
        actor=receipt["actor"],
        receipt_id=receipt_id,
        tenant_key=receipt["tenant_key"],
        request_fingerprint=expected_fingerprint,
        stage17_closure_receipt_id=receipt["stage17_closure_receipt_id"],
    )
    return {
        "ok": True,
        "status": "recorded",
        "error": "",
        "receipt": receipt,
        "receipt_id": receipt_id,
        "copy_request_recorded": True,
        "copy_created": False,
        "writes_receipt": True,
        "writes_tenant_state": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def managed_copy_request_receipts_readback(*, limit: int = 20) -> dict[str, Any]:
    path = _request_receipts_path()
    items = _read_jsonl_tail(path, limit=_safe_limit(limit))
    valid_count, latest_valid_receipt = _valid_receipt_summary(path)
    latest = items[-1] if items else {}
    latest_valid = _valid_request_receipt(latest)
    return {
        "ok": True,
        "kind": MANAGED_COPY_REQUEST_RECEIPTS_KIND,
        "status": "ready" if valid_count else "empty",
        "items": items,
        "count": len(items),
        "valid_count": valid_count,
        "latest_receipt": latest,
        "latest_receipt_id": _safe_text(latest.get("receipt_id")),
        "latest_receipt_valid": latest_valid,
        "latest_valid_receipt": latest_valid_receipt,
        "latest_valid_receipt_id": _safe_text(latest_valid_receipt.get("receipt_id")),
        "copy_request_recording_ready": bool(valid_count),
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_tenant_state": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "expected_receipt_path": "logs/managed_copies/copy_requests.jsonl",
        "next_smallest_truthful_gap": (
            "stage18_copy_creation_preflight_process" if valid_count else "stage18_copy_creation_request_recording"
        ),
    }


def managed_copy_preflight_plan(
    payload: dict[str, Any],
    *,
    actor: str,
    request_receipt: dict[str, Any],
) -> dict[str, Any]:
    safe_actor = _redacted_text(actor)[:240]
    provided_request_receipt_id = _safe_text(payload.get("request_receipt_id"))
    expected_request_receipt_id = _safe_text(request_receipt.get("receipt_id"))
    tenant_id, field_presence, field_fingerprints = _request_field_evidence(payload)
    managed_copy_law_checks = _managed_copy_law_checks(payload)
    managed_copy_law_ready = all(bool(check["ready"]) for check in managed_copy_law_checks)
    tenant_key = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest() if tenant_id else ""
    expected_field_fingerprints = request_receipt.get("request_field_fingerprints")
    expected_field_fingerprints = expected_field_fingerprints if isinstance(expected_field_fingerprints, dict) else {}

    blockers: list[str] = []
    if not request_receipt:
        blockers.append("copy_request_receipt_missing")
    if not safe_actor:
        blockers.append("preflight_actor_missing")
    if not provided_request_receipt_id:
        blockers.append("copy_request_receipt_id_missing")
    elif expected_request_receipt_id and provided_request_receipt_id != expected_request_receipt_id:
        blockers.append("copy_request_receipt_id_mismatch")
    if not tenant_id:
        blockers.append("tenant_id_missing")
    blockers.extend(f"{field}_missing_or_invalid" for field in _REQUEST_MAPPING_FIELDS if not field_presence[field])
    blockers.extend(_safe_text(check.get("blocker")) for check in managed_copy_law_checks if not check["ready"])

    expected_tenant_key = _safe_text(request_receipt.get("tenant_key"))
    if tenant_key and expected_tenant_key and tenant_key != expected_tenant_key:
        blockers.append("tenant_key_mismatch")
    for field in _REQUEST_MAPPING_FIELDS:
        fingerprint = field_fingerprints.get(field, "")
        expected_fingerprint = _safe_text(expected_field_fingerprints.get(field))
        if fingerprint and expected_fingerprint and fingerprint != expected_fingerprint:
            blockers.append(f"{field}_fingerprint_mismatch")

    stage17_receipt_id = _safe_text(request_receipt.get("stage17_closure_receipt_id"))
    request_fingerprint = _safe_text(request_receipt.get("request_fingerprint"))
    request_receipt_aligned = bool(
        request_receipt
        and expected_request_receipt_id
        and provided_request_receipt_id == expected_request_receipt_id
        and tenant_key
        and tenant_key == expected_tenant_key
        and all(field_presence.values())
        and all(
            field_fingerprints.get(field, "") == _safe_text(expected_field_fingerprints.get(field))
            for field in _REQUEST_MAPPING_FIELDS
        )
    )
    if request_receipt and not request_receipt_aligned and not blockers:
        blockers.append("copy_request_payload_not_aligned")

    fingerprint_evidence = {
        "contract": MANAGED_COPY_PREFLIGHT_CONTRACT,
        "actor": safe_actor,
        "tenant_key": tenant_key,
        "request_receipt_id": expected_request_receipt_id,
        "request_fingerprint": request_fingerprint,
        "stage17_closure_receipt_id": stage17_receipt_id,
        "request_field_presence": field_presence,
        "request_field_fingerprints": field_fingerprints,
        "managed_copy_law_checks": managed_copy_law_checks,
    }
    preflight_fingerprint = _fingerprint(fingerprint_evidence) if not blockers else ""
    return {
        "ok": not blockers,
        "kind": "francis.stage18.managed_copies.copy_preflight_plan",
        "contract": MANAGED_COPY_PREFLIGHT_CONTRACT,
        "status": "preflight_planned" if not blockers else "blocked",
        "actor": safe_actor,
        "tenant_key": tenant_key,
        "request_receipt_id": expected_request_receipt_id,
        "provided_request_receipt_id": provided_request_receipt_id,
        "request_fingerprint": request_fingerprint,
        "request_receipt_aligned": request_receipt_aligned,
        "request_payload_fingerprints_matched": request_receipt_aligned,
        "request_field_presence": field_presence,
        "request_field_fingerprints": field_fingerprints,
        "managed_copy_law_ready": managed_copy_law_ready,
        "managed_copy_law_checks": managed_copy_law_checks,
        "managed_copy_law_ready_count": sum(1 for check in managed_copy_law_checks if check["ready"]),
        "managed_copy_law_required_count": len(managed_copy_law_checks),
        "stage17_closure_receipt_id": stage17_receipt_id,
        "preflight_contract_ready": not blockers,
        "blockers": blockers,
        "preflight_fingerprint": preflight_fingerprint,
        "dry_run_confirmation": {
            "required_for_record": True,
            "fingerprint": preflight_fingerprint,
            "fingerprint_contract": MANAGED_COPY_PREFLIGHT_CONTRACT,
        },
        "contains_raw_tenant_payload": False,
        "writes_receipt": False,
        "writes_tenant_state": False,
        "creates_copy_plan": False,
        "creates_copy": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def record_managed_copy_preflight(
    plan: dict[str, Any],
    *,
    provided_fingerprint: str,
    confirm_preflight_recording: bool,
) -> dict[str, Any]:
    expected_fingerprint = _safe_text(plan.get("preflight_fingerprint"))
    if not plan.get("preflight_contract_ready"):
        return _record_preflight_blocked(
            "blocked_copy_preflight_contract",
            "copy_preflight_contract_not_ready",
            plan,
        )
    if not confirm_preflight_recording:
        return _record_preflight_blocked(
            "blocked_preflight_recording_confirmation",
            "copy_preflight_recording_confirmation_required",
            plan,
        )
    if not expected_fingerprint or _safe_text(provided_fingerprint) != expected_fingerprint:
        return _record_preflight_blocked(
            "blocked_preflight_dry_run_confirmation",
            "copy_preflight_fingerprint_mismatch",
            plan,
        )

    request_receipt_id = _safe_text(plan.get("request_receipt_id"))
    with _PREFLIGHT_WRITE_LOCK:
        existing = _preflight_receipt_by_fingerprint(
            expected_fingerprint,
            request_receipt_id=request_receipt_id,
        )
        if existing:
            return {
                "ok": True,
                "status": "already_recorded",
                "error": "",
                "receipt": existing,
                "receipt_id": _safe_text(existing.get("receipt_id")),
                "copy_preflight_recorded": True,
                "copy_plan_created": False,
                "copy_created": False,
                "writes_receipt": False,
                "writes_tenant_state": False,
                "starts_runtime": False,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            }

        receipt_id = f"managed_copy_preflight_{uuid.uuid4().hex[:12]}"
        receipt = {
            "ok": True,
            "kind": MANAGED_COPY_PREFLIGHT_RECEIPT_KIND,
            "receipt_id": receipt_id,
            "contract": MANAGED_COPY_PREFLIGHT_CONTRACT,
            "status": "preflight_passed",
            "actor": _safe_text(plan.get("actor")),
            "tenant_key": _safe_text(plan.get("tenant_key")),
            "preflight_fingerprint": expected_fingerprint,
            "request_receipt_id": request_receipt_id,
            "request_fingerprint": _safe_text(plan.get("request_fingerprint")),
            "request_field_presence": dict(plan.get("request_field_presence") or {}),
            "request_field_fingerprints": dict(plan.get("request_field_fingerprints") or {}),
            "managed_copy_law_ready": bool(plan.get("managed_copy_law_ready")),
            "managed_copy_law_checks": list(plan.get("managed_copy_law_checks") or []),
            "managed_copy_law_ready_count": int(plan.get("managed_copy_law_ready_count") or 0),
            "managed_copy_law_required_count": int(plan.get("managed_copy_law_required_count") or 0),
            "stage17_closure_receipt_id": _safe_text(plan.get("stage17_closure_receipt_id")),
            "request_receipt_aligned": True,
            "request_payload_fingerprints_matched": True,
            "preflight_passed": True,
            "copy_plan_created": False,
            "copy_created": False,
            "tenant_state_written": False,
            "runtime_started": False,
            "recorded_ts": int(time.time()),
            "governance": {
                "copy_preflight_receipt": True,
                "permission_checked_by_route": True,
                "dry_run_fingerprint_matched": True,
                "explicit_preflight_confirmation": True,
                "copy_request_receipt_required": True,
                "copy_request_receipt_aligned": True,
                "request_payload_fingerprints_matched": True,
                "managed_copy_law_checked": True,
                "managed_copy_law_ready": True,
                "contains_raw_tenant_payload": False,
                "does_not_create_copy_plan": True,
                "does_not_create_copy": True,
                "does_not_write_tenant_state": True,
                "does_not_start_runtime": True,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
        }
        _append_jsonl(_preflight_receipts_path(), receipt)

    audit_record(
        "managed_copies.copy_preflight_recorded",
        actor=receipt["actor"],
        receipt_id=receipt_id,
        tenant_key=receipt["tenant_key"],
        request_receipt_id=request_receipt_id,
        preflight_fingerprint=expected_fingerprint,
        stage17_closure_receipt_id=receipt["stage17_closure_receipt_id"],
    )
    return {
        "ok": True,
        "status": "recorded",
        "error": "",
        "receipt": receipt,
        "receipt_id": receipt_id,
        "copy_preflight_recorded": True,
        "copy_plan_created": False,
        "copy_created": False,
        "writes_receipt": True,
        "writes_tenant_state": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def managed_copy_preflight_receipts_readback(*, limit: int = 20) -> dict[str, Any]:
    path = _preflight_receipts_path()
    items = _read_jsonl_tail(path, limit=_safe_limit(limit))
    valid_count, latest_valid_receipt = _valid_preflight_receipt_summary(path)
    latest = items[-1] if items else {}
    latest_valid = _valid_preflight_receipt(latest)
    return {
        "ok": True,
        "kind": MANAGED_COPY_PREFLIGHT_RECEIPTS_KIND,
        "status": "ready" if valid_count else "empty",
        "items": items,
        "count": len(items),
        "valid_count": valid_count,
        "latest_receipt": latest,
        "latest_receipt_id": _safe_text(latest.get("receipt_id")),
        "latest_receipt_valid": latest_valid,
        "latest_valid_receipt": latest_valid_receipt,
        "latest_valid_receipt_id": _safe_text(latest_valid_receipt.get("receipt_id")),
        "copy_preflight_recording_ready": bool(valid_count),
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_tenant_state": False,
        "creates_copy_plan": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "expected_receipt_path": "logs/managed_copies/copy_preflights.jsonl",
        "next_smallest_truthful_gap": (
            "stage18_copy_creation_plan_process" if valid_count else "stage18_copy_creation_preflight_process"
        ),
    }


def managed_copy_creation_plan_dry_run(
    payload: dict[str, Any],
    *,
    actor: str,
    request_receipt: dict[str, Any],
    preflight_receipt: dict[str, Any],
) -> dict[str, Any]:
    safe_actor = _redacted_text(actor)[:240]
    provided_request_receipt_id = _safe_text(payload.get("request_receipt_id"))
    provided_preflight_receipt_id = _safe_text(payload.get("preflight_receipt_id"))
    expected_request_receipt_id = _safe_text(request_receipt.get("receipt_id"))
    expected_preflight_receipt_id = _safe_text(preflight_receipt.get("receipt_id"))
    request_fingerprint = _safe_text(request_receipt.get("request_fingerprint"))
    preflight_fingerprint = _safe_text(preflight_receipt.get("preflight_fingerprint"))
    stage17_receipt_id = _safe_text(request_receipt.get("stage17_closure_receipt_id"))
    tenant_key = _safe_text(request_receipt.get("tenant_key"))
    raw_request_fingerprints = request_receipt.get("request_field_fingerprints")
    request_field_fingerprints = dict(raw_request_fingerprints) if isinstance(raw_request_fingerprints, dict) else {}
    raw_preflight_fingerprints = preflight_receipt.get("request_field_fingerprints")
    preflight_field_fingerprints = (
        dict(raw_preflight_fingerprints) if isinstance(raw_preflight_fingerprints, dict) else {}
    )

    receipts_aligned = bool(
        request_receipt
        and preflight_receipt
        and expected_request_receipt_id
        and expected_preflight_receipt_id
        and _safe_text(preflight_receipt.get("request_receipt_id")) == expected_request_receipt_id
        and _safe_text(preflight_receipt.get("request_fingerprint")) == request_fingerprint
        and _safe_text(preflight_receipt.get("stage17_closure_receipt_id")) == stage17_receipt_id
        and _safe_text(preflight_receipt.get("tenant_key")) == tenant_key
        and all(
            _safe_text(preflight_field_fingerprints.get(field)) == _safe_text(request_field_fingerprints.get(field))
            for field in _REQUEST_MAPPING_FIELDS
        )
    )

    blockers: list[str] = []
    if not request_receipt:
        blockers.append("copy_request_receipt_missing")
    if not preflight_receipt:
        blockers.append("copy_preflight_receipt_missing")
    if not safe_actor:
        blockers.append("copy_plan_actor_missing")
    if not provided_request_receipt_id:
        blockers.append("copy_request_receipt_id_missing")
    elif expected_request_receipt_id and provided_request_receipt_id != expected_request_receipt_id:
        blockers.append("copy_request_receipt_id_mismatch")
    if not provided_preflight_receipt_id:
        blockers.append("copy_preflight_receipt_id_missing")
    elif expected_preflight_receipt_id and provided_preflight_receipt_id != expected_preflight_receipt_id:
        blockers.append("copy_preflight_receipt_id_mismatch")
    if request_receipt and preflight_receipt and not receipts_aligned:
        blockers.append("copy_request_preflight_receipts_not_aligned")
    if request_receipt and not all(
        _is_sha256(request_field_fingerprints.get(field)) for field in _REQUEST_MAPPING_FIELDS
    ):
        blockers.append("copy_request_field_fingerprints_invalid")

    plan_steps = _creation_plan_steps(request_field_fingerprints)
    fingerprint_evidence = {
        "contract": MANAGED_COPY_CREATION_PLAN_CONTRACT,
        "actor": safe_actor,
        "tenant_key": tenant_key,
        "request_receipt_id": expected_request_receipt_id,
        "request_fingerprint": request_fingerprint,
        "preflight_receipt_id": expected_preflight_receipt_id,
        "preflight_fingerprint": preflight_fingerprint,
        "stage17_closure_receipt_id": stage17_receipt_id,
        "plan_steps": plan_steps,
    }
    plan_fingerprint = _fingerprint(fingerprint_evidence) if not blockers else ""
    return {
        "ok": not blockers,
        "kind": "francis.stage18.managed_copies.copy_creation_plan_dry_run",
        "contract": MANAGED_COPY_CREATION_PLAN_CONTRACT,
        "status": "copy_plan_ready" if not blockers else "blocked",
        "actor": safe_actor,
        "tenant_key": tenant_key,
        "request_receipt_id": expected_request_receipt_id,
        "provided_request_receipt_id": provided_request_receipt_id,
        "request_fingerprint": request_fingerprint,
        "preflight_receipt_id": expected_preflight_receipt_id,
        "provided_preflight_receipt_id": provided_preflight_receipt_id,
        "preflight_fingerprint": preflight_fingerprint,
        "stage17_closure_receipt_id": stage17_receipt_id,
        "request_and_preflight_receipts_aligned": receipts_aligned,
        "request_field_fingerprints": request_field_fingerprints,
        "plan_steps": plan_steps,
        "plan_contract_ready": not blockers,
        "blockers": blockers,
        "plan_fingerprint": plan_fingerprint,
        "dry_run_confirmation": {
            "required_for_record": True,
            "fingerprint": plan_fingerprint,
            "fingerprint_contract": MANAGED_COPY_CREATION_PLAN_CONTRACT,
        },
        "approval_required_before_provisioning": True,
        "contains_raw_tenant_payload": False,
        "writes_receipt": False,
        "writes_tenant_state": False,
        "creates_copy": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def record_managed_copy_creation_plan(
    plan: dict[str, Any],
    *,
    provided_fingerprint: str,
    confirm_plan_recording: bool,
) -> dict[str, Any]:
    expected_fingerprint = _safe_text(plan.get("plan_fingerprint"))
    if not plan.get("plan_contract_ready"):
        return _record_plan_blocked("blocked_copy_plan_contract", "copy_plan_contract_not_ready", plan)
    if not confirm_plan_recording:
        return _record_plan_blocked(
            "blocked_copy_plan_recording_confirmation",
            "copy_plan_recording_confirmation_required",
            plan,
        )
    if not expected_fingerprint or _safe_text(provided_fingerprint) != expected_fingerprint:
        return _record_plan_blocked(
            "blocked_copy_plan_dry_run_confirmation",
            "copy_plan_fingerprint_mismatch",
            plan,
        )

    preflight_receipt_id = _safe_text(plan.get("preflight_receipt_id"))
    with _PLAN_WRITE_LOCK:
        existing = _plan_receipt_by_fingerprint(
            expected_fingerprint,
            preflight_receipt_id=preflight_receipt_id,
        )
        if existing:
            return {
                "ok": True,
                "status": "already_recorded",
                "error": "",
                "receipt": existing,
                "receipt_id": _safe_text(existing.get("receipt_id")),
                "copy_plan_recorded": True,
                "copy_created": False,
                "writes_receipt": False,
                "writes_tenant_state": False,
                "starts_runtime": False,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            }

        receipt_id = f"managed_copy_creation_plan_{uuid.uuid4().hex[:12]}"
        receipt = {
            "ok": True,
            "kind": MANAGED_COPY_CREATION_PLAN_RECEIPT_KIND,
            "receipt_id": receipt_id,
            "contract": MANAGED_COPY_CREATION_PLAN_CONTRACT,
            "status": "planned",
            "actor": _safe_text(plan.get("actor")),
            "tenant_key": _safe_text(plan.get("tenant_key")),
            "plan_fingerprint": expected_fingerprint,
            "request_receipt_id": _safe_text(plan.get("request_receipt_id")),
            "request_fingerprint": _safe_text(plan.get("request_fingerprint")),
            "preflight_receipt_id": preflight_receipt_id,
            "preflight_fingerprint": _safe_text(plan.get("preflight_fingerprint")),
            "stage17_closure_receipt_id": _safe_text(plan.get("stage17_closure_receipt_id")),
            "request_field_fingerprints": dict(plan.get("request_field_fingerprints") or {}),
            "plan_steps": list(plan.get("plan_steps") or []),
            "request_and_preflight_receipts_aligned": True,
            "copy_plan_recorded": True,
            "operator_approval_recorded": False,
            "copy_created": False,
            "tenant_state_written": False,
            "runtime_started": False,
            "recorded_ts": int(time.time()),
            "governance": {
                "copy_creation_plan_receipt": True,
                "permission_checked_by_route": True,
                "dry_run_fingerprint_matched": True,
                "explicit_plan_recording_confirmation": True,
                "copy_request_receipt_required": True,
                "copy_preflight_receipt_required": True,
                "request_and_preflight_receipts_aligned": True,
                "operator_approval_required_before_provisioning": True,
                "contains_raw_tenant_payload": False,
                "does_not_provision_copy": True,
                "does_not_write_tenant_state": True,
                "does_not_start_runtime": True,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
        }
        _append_jsonl(_plan_receipts_path(), receipt)

    audit_record(
        "managed_copies.copy_creation_plan_recorded",
        actor=receipt["actor"],
        receipt_id=receipt_id,
        tenant_key=receipt["tenant_key"],
        request_receipt_id=receipt["request_receipt_id"],
        preflight_receipt_id=preflight_receipt_id,
        plan_fingerprint=expected_fingerprint,
        stage17_closure_receipt_id=receipt["stage17_closure_receipt_id"],
    )
    return {
        "ok": True,
        "status": "recorded",
        "error": "",
        "receipt": receipt,
        "receipt_id": receipt_id,
        "copy_plan_recorded": True,
        "copy_created": False,
        "writes_receipt": True,
        "writes_tenant_state": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def managed_copy_creation_plan_receipts_readback(*, limit: int = 20) -> dict[str, Any]:
    path = _plan_receipts_path()
    items = _read_jsonl_tail(path, limit=_safe_limit(limit))
    valid_count, latest_valid_receipt = _valid_plan_receipt_summary(path)
    latest = items[-1] if items else {}
    latest_valid = _valid_plan_receipt(latest)
    return {
        "ok": True,
        "kind": MANAGED_COPY_CREATION_PLAN_RECEIPTS_KIND,
        "status": "ready" if valid_count else "empty",
        "items": items,
        "count": len(items),
        "valid_count": valid_count,
        "latest_receipt": latest,
        "latest_receipt_id": _safe_text(latest.get("receipt_id")),
        "latest_receipt_valid": latest_valid,
        "latest_valid_receipt": latest_valid_receipt,
        "latest_valid_receipt_id": _safe_text(latest_valid_receipt.get("receipt_id")),
        "copy_plan_recording_ready": bool(valid_count),
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_tenant_state": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "expected_receipt_path": "logs/managed_copies/copy_plans.jsonl",
        "next_smallest_truthful_gap": (
            "stage18_copy_creation_approval_request" if valid_count else "stage18_copy_creation_plan_process"
        ),
    }


def latest_managed_copy_creation_plan_receipt_for_preflight(
    preflight_receipt_id: str,
    *,
    preflight_fingerprint: str = "",
    request_receipt_id: str = "",
    request_fingerprint: str = "",
    stage17_receipt_id: str = "",
) -> dict[str, Any]:
    expected_preflight_receipt_id = _safe_text(preflight_receipt_id)
    if not expected_preflight_receipt_id:
        return {}
    expected = {
        "preflight_fingerprint": _safe_text(preflight_fingerprint),
        "request_receipt_id": _safe_text(request_receipt_id),
        "request_fingerprint": _safe_text(request_fingerprint),
        "stage17_closure_receipt_id": _safe_text(stage17_receipt_id),
    }
    latest: dict[str, Any] = {}
    for item in _iter_jsonl_objects(_plan_receipts_path()):
        if (
            _safe_text(item.get("preflight_receipt_id")) == expected_preflight_receipt_id
            and all(not value or _safe_text(item.get(field)) == value for field, value in expected.items())
            and _valid_plan_receipt(item)
        ):
            latest = item
    return latest


def latest_managed_copy_preflight_receipt_for_request(
    request_receipt_id: str,
    *,
    request_fingerprint: str = "",
    stage17_receipt_id: str = "",
) -> dict[str, Any]:
    expected_request_receipt_id = _safe_text(request_receipt_id)
    expected_request_fingerprint = _safe_text(request_fingerprint)
    expected_stage17_receipt_id = _safe_text(stage17_receipt_id)
    if not expected_request_receipt_id:
        return {}
    latest: dict[str, Any] = {}
    for item in _iter_jsonl_objects(_preflight_receipts_path()):
        if (
            _safe_text(item.get("request_receipt_id")) == expected_request_receipt_id
            and (
                not expected_request_fingerprint
                or _safe_text(item.get("request_fingerprint")) == expected_request_fingerprint
            )
            and (
                not expected_stage17_receipt_id
                or _safe_text(item.get("stage17_closure_receipt_id")) == expected_stage17_receipt_id
            )
            and _valid_preflight_receipt(item)
        ):
            latest = item
    return latest


def latest_managed_copy_request_receipt_for_stage17(stage17_receipt_id: str) -> dict[str, Any]:
    expected_stage17_receipt_id = _safe_text(stage17_receipt_id)
    if not expected_stage17_receipt_id:
        return {}
    latest: dict[str, Any] = {}
    for item in _iter_jsonl_objects(_request_receipts_path()):
        if _safe_text(item.get("stage17_closure_receipt_id")) == expected_stage17_receipt_id and _valid_request_receipt(
            item
        ):
            latest = item
    return latest


def _record_blocked(status: str, error: str, plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "status": status,
        "error": error,
        "receipt": None,
        "receipt_id": "",
        "copy_request_recorded": False,
        "copy_created": False,
        "writes_receipt": False,
        "writes_tenant_state": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "plan": plan,
    }


def _record_preflight_blocked(status: str, error: str, plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "status": status,
        "error": error,
        "receipt": None,
        "receipt_id": "",
        "copy_preflight_recorded": False,
        "copy_plan_created": False,
        "copy_created": False,
        "writes_receipt": False,
        "writes_tenant_state": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "plan": plan,
    }


def _record_plan_blocked(status: str, error: str, plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "status": status,
        "error": error,
        "receipt": None,
        "receipt_id": "",
        "copy_plan_recorded": False,
        "copy_created": False,
        "writes_receipt": False,
        "writes_tenant_state": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "plan": plan,
    }


def _valid_request_receipt(item: dict[str, Any]) -> bool:
    raw_governance = item.get("governance")
    governance: dict[str, Any] = raw_governance if isinstance(raw_governance, dict) else {}
    raw_field_presence = item.get("request_field_presence")
    field_presence: dict[str, Any] = raw_field_presence if isinstance(raw_field_presence, dict) else {}
    raw_field_fingerprints = item.get("request_field_fingerprints")
    field_fingerprints: dict[str, Any] = raw_field_fingerprints if isinstance(raw_field_fingerprints, dict) else {}
    return (
        _safe_text(item.get("kind")) == MANAGED_COPY_REQUEST_RECEIPT_KIND
        and bool(_safe_text(item.get("receipt_id")))
        and bool(_safe_text(item.get("actor")))
        and _is_sha256(item.get("tenant_key"))
        and _is_sha256(item.get("request_fingerprint"))
        and _safe_text(item.get("stage17_closure_receipt_id")).startswith("stage17_capability_economy_closure_")
        and bool(field_presence.get("tenant_id"))
        and all(bool(field_presence.get(field)) for field in _REQUEST_MAPPING_FIELDS)
        and all(_is_sha256(field_fingerprints.get(field)) for field in _REQUEST_MAPPING_FIELDS)
        and bool(item.get("request_contract_ready"))
        and bool(item.get("copy_request_recorded"))
        and not bool(item.get("copy_created"))
        and not bool(item.get("tenant_state_written"))
        and not bool(item.get("runtime_started"))
        and _safe_int(item.get("recorded_ts")) > 0
        and bool(governance.get("copy_request_receipt"))
        and bool(governance.get("permission_checked_by_route"))
        and bool(governance.get("dry_run_fingerprint_matched"))
        and bool(governance.get("explicit_recording_confirmation"))
        and bool(governance.get("stage17_closure_receipt_required"))
        and not bool(governance.get("contains_raw_tenant_payload"))
        and bool(governance.get("does_not_create_copy"))
        and bool(governance.get("does_not_write_tenant_state"))
        and bool(governance.get("does_not_start_runtime"))
        and not bool(governance.get("grants_execution_authority"))
        and not bool(governance.get("grants_mutation_authority"))
    )


def _valid_preflight_receipt(item: dict[str, Any]) -> bool:
    raw_governance = item.get("governance")
    governance: dict[str, Any] = raw_governance if isinstance(raw_governance, dict) else {}
    raw_field_presence = item.get("request_field_presence")
    field_presence: dict[str, Any] = raw_field_presence if isinstance(raw_field_presence, dict) else {}
    raw_field_fingerprints = item.get("request_field_fingerprints")
    field_fingerprints: dict[str, Any] = raw_field_fingerprints if isinstance(raw_field_fingerprints, dict) else {}
    managed_copy_law_checks = item.get("managed_copy_law_checks")
    preflight_fingerprint = _safe_text(item.get("preflight_fingerprint"))
    expected_preflight_fingerprint = _fingerprint(
        {
            "contract": _safe_text(item.get("contract")),
            "actor": _safe_text(item.get("actor")),
            "tenant_key": _safe_text(item.get("tenant_key")),
            "request_receipt_id": _safe_text(item.get("request_receipt_id")),
            "request_fingerprint": _safe_text(item.get("request_fingerprint")),
            "stage17_closure_receipt_id": _safe_text(item.get("stage17_closure_receipt_id")),
            "request_field_presence": field_presence,
            "request_field_fingerprints": field_fingerprints,
            "managed_copy_law_checks": managed_copy_law_checks,
        }
    )
    return (
        _safe_text(item.get("kind")) == MANAGED_COPY_PREFLIGHT_RECEIPT_KIND
        and _safe_text(item.get("receipt_id")).startswith("managed_copy_preflight_")
        and _safe_text(item.get("contract")) == MANAGED_COPY_PREFLIGHT_CONTRACT
        and _safe_text(item.get("status")) == "preflight_passed"
        and bool(_safe_text(item.get("actor")))
        and _is_sha256(item.get("tenant_key"))
        and _is_sha256(preflight_fingerprint)
        and preflight_fingerprint == expected_preflight_fingerprint
        and _safe_text(item.get("request_receipt_id")).startswith("managed_copy_request_")
        and _is_sha256(item.get("request_fingerprint"))
        and _safe_text(item.get("stage17_closure_receipt_id")).startswith("stage17_capability_economy_closure_")
        and bool(field_presence.get("tenant_id"))
        and all(bool(field_presence.get(field)) for field in _REQUEST_MAPPING_FIELDS)
        and all(_is_sha256(field_fingerprints.get(field)) for field in _REQUEST_MAPPING_FIELDS)
        and bool(item.get("managed_copy_law_ready"))
        and _valid_managed_copy_law_checks(managed_copy_law_checks)
        and _safe_int(item.get("managed_copy_law_ready_count")) == len(_MANAGED_COPY_LAW_CHECK_IDS)
        and _safe_int(item.get("managed_copy_law_required_count")) == len(_MANAGED_COPY_LAW_CHECK_IDS)
        and bool(item.get("request_receipt_aligned"))
        and bool(item.get("request_payload_fingerprints_matched"))
        and bool(item.get("preflight_passed"))
        and not bool(item.get("copy_plan_created"))
        and not bool(item.get("copy_created"))
        and not bool(item.get("tenant_state_written"))
        and not bool(item.get("runtime_started"))
        and _safe_int(item.get("recorded_ts")) > 0
        and bool(governance.get("copy_preflight_receipt"))
        and bool(governance.get("permission_checked_by_route"))
        and bool(governance.get("dry_run_fingerprint_matched"))
        and bool(governance.get("explicit_preflight_confirmation"))
        and bool(governance.get("copy_request_receipt_required"))
        and bool(governance.get("copy_request_receipt_aligned"))
        and bool(governance.get("request_payload_fingerprints_matched"))
        and bool(governance.get("managed_copy_law_checked"))
        and bool(governance.get("managed_copy_law_ready"))
        and not bool(governance.get("contains_raw_tenant_payload"))
        and bool(governance.get("does_not_create_copy_plan"))
        and bool(governance.get("does_not_create_copy"))
        and bool(governance.get("does_not_write_tenant_state"))
        and bool(governance.get("does_not_start_runtime"))
        and not bool(governance.get("grants_execution_authority"))
        and not bool(governance.get("grants_mutation_authority"))
    )


def _valid_plan_receipt(item: dict[str, Any]) -> bool:
    raw_governance = item.get("governance")
    governance: dict[str, Any] = raw_governance if isinstance(raw_governance, dict) else {}
    raw_field_fingerprints = item.get("request_field_fingerprints")
    field_fingerprints: dict[str, Any] = raw_field_fingerprints if isinstance(raw_field_fingerprints, dict) else {}
    plan_fingerprint = _safe_text(item.get("plan_fingerprint"))
    expected_plan_fingerprint = _fingerprint(
        {
            "contract": _safe_text(item.get("contract")),
            "actor": _safe_text(item.get("actor")),
            "tenant_key": _safe_text(item.get("tenant_key")),
            "request_receipt_id": _safe_text(item.get("request_receipt_id")),
            "request_fingerprint": _safe_text(item.get("request_fingerprint")),
            "preflight_receipt_id": _safe_text(item.get("preflight_receipt_id")),
            "preflight_fingerprint": _safe_text(item.get("preflight_fingerprint")),
            "stage17_closure_receipt_id": _safe_text(item.get("stage17_closure_receipt_id")),
            "plan_steps": item.get("plan_steps"),
        }
    )
    return (
        _safe_text(item.get("kind")) == MANAGED_COPY_CREATION_PLAN_RECEIPT_KIND
        and _safe_text(item.get("receipt_id")).startswith("managed_copy_creation_plan_")
        and _safe_text(item.get("contract")) == MANAGED_COPY_CREATION_PLAN_CONTRACT
        and _safe_text(item.get("status")) == "planned"
        and bool(_safe_text(item.get("actor")))
        and _is_sha256(item.get("tenant_key"))
        and _is_sha256(plan_fingerprint)
        and plan_fingerprint == expected_plan_fingerprint
        and _safe_text(item.get("request_receipt_id")).startswith("managed_copy_request_")
        and _is_sha256(item.get("request_fingerprint"))
        and _safe_text(item.get("preflight_receipt_id")).startswith("managed_copy_preflight_")
        and _is_sha256(item.get("preflight_fingerprint"))
        and _safe_text(item.get("stage17_closure_receipt_id")).startswith("stage17_capability_economy_closure_")
        and all(_is_sha256(field_fingerprints.get(field)) for field in _REQUEST_MAPPING_FIELDS)
        and _valid_creation_plan_steps(item.get("plan_steps"), field_fingerprints)
        and bool(item.get("request_and_preflight_receipts_aligned"))
        and bool(item.get("copy_plan_recorded"))
        and not bool(item.get("operator_approval_recorded"))
        and not bool(item.get("copy_created"))
        and not bool(item.get("tenant_state_written"))
        and not bool(item.get("runtime_started"))
        and _safe_int(item.get("recorded_ts")) > 0
        and bool(governance.get("copy_creation_plan_receipt"))
        and bool(governance.get("permission_checked_by_route"))
        and bool(governance.get("dry_run_fingerprint_matched"))
        and bool(governance.get("explicit_plan_recording_confirmation"))
        and bool(governance.get("copy_request_receipt_required"))
        and bool(governance.get("copy_preflight_receipt_required"))
        and bool(governance.get("request_and_preflight_receipts_aligned"))
        and bool(governance.get("operator_approval_required_before_provisioning"))
        and not bool(governance.get("contains_raw_tenant_payload"))
        and bool(governance.get("does_not_provision_copy"))
        and bool(governance.get("does_not_write_tenant_state"))
        and bool(governance.get("does_not_start_runtime"))
        and not bool(governance.get("grants_execution_authority"))
        and not bool(governance.get("grants_mutation_authority"))
    )


def _receipt_by_fingerprint(fingerprint: str, *, stage17_receipt_id: str) -> dict[str, Any]:
    matched: dict[str, Any] = {}
    for item in _iter_jsonl_objects(_request_receipts_path()):
        if (
            _safe_text(item.get("request_fingerprint")) == fingerprint
            and _safe_text(item.get("stage17_closure_receipt_id")) == stage17_receipt_id
            and _valid_request_receipt(item)
        ):
            matched = item
    return matched


def _preflight_receipt_by_fingerprint(fingerprint: str, *, request_receipt_id: str) -> dict[str, Any]:
    matched: dict[str, Any] = {}
    for item in _iter_jsonl_objects(_preflight_receipts_path()):
        if (
            _safe_text(item.get("preflight_fingerprint")) == fingerprint
            and _safe_text(item.get("request_receipt_id")) == request_receipt_id
            and _valid_preflight_receipt(item)
        ):
            matched = item
    return matched


def _plan_receipt_by_fingerprint(fingerprint: str, *, preflight_receipt_id: str) -> dict[str, Any]:
    matched: dict[str, Any] = {}
    for item in _iter_jsonl_objects(_plan_receipts_path()):
        if (
            _safe_text(item.get("plan_fingerprint")) == fingerprint
            and _safe_text(item.get("preflight_receipt_id")) == preflight_receipt_id
            and _valid_plan_receipt(item)
        ):
            matched = item
    return matched


def _valid_receipt_summary(path: Path) -> tuple[int, dict[str, Any]]:
    valid_count = 0
    latest_valid: dict[str, Any] = {}
    for item in _iter_jsonl_objects(path):
        if _valid_request_receipt(item):
            valid_count += 1
            latest_valid = item
    return (valid_count, latest_valid)


def _valid_preflight_receipt_summary(path: Path) -> tuple[int, dict[str, Any]]:
    valid_count = 0
    latest_valid: dict[str, Any] = {}
    for item in _iter_jsonl_objects(path):
        if _valid_preflight_receipt(item):
            valid_count += 1
            latest_valid = item
    return (valid_count, latest_valid)


def _valid_plan_receipt_summary(path: Path) -> tuple[int, dict[str, Any]]:
    valid_count = 0
    latest_valid: dict[str, Any] = {}
    for item in _iter_jsonl_objects(path):
        if _valid_plan_receipt(item):
            valid_count += 1
            latest_valid = item
    return (valid_count, latest_valid)


def _iter_jsonl_objects(path: Path) -> Iterator[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                yield item


def _request_receipts_path() -> Path:
    return data_dir() / "logs" / "managed_copies" / "copy_requests.jsonl"


def _preflight_receipts_path() -> Path:
    return data_dir() / "logs" / "managed_copies" / "copy_preflights.jsonl"


def _plan_receipts_path() -> Path:
    return data_dir() / "logs" / "managed_copies" / "copy_plans.jsonl"


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def _read_jsonl_tail(path: Path, *, limit: int) -> list[dict[str, Any]]:
    rows: deque[dict[str, Any]] = deque(maxlen=limit)
    for item in _iter_jsonl_objects(path):
        rows.append(item)
    return list(rows)


def _fingerprint(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _request_field_evidence(payload: dict[str, Any]) -> tuple[str, dict[str, bool], dict[str, str]]:
    tenant_id = _safe_text(payload.get("tenant_id"))
    field_presence = {"tenant_id": bool(tenant_id)}
    field_fingerprints: dict[str, str] = {}
    for field in _REQUEST_MAPPING_FIELDS:
        value = payload.get(field)
        present = isinstance(value, dict) and bool(value)
        field_presence[field] = present
        if present:
            field_fingerprints[field] = _fingerprint(value)
    return tenant_id, field_presence, field_fingerprints


def _managed_copy_law_checks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    tenant_identity = _mapping(payload.get("tenant_identity"))
    tenant_policy = _mapping(payload.get("tenant_policy"))
    isolation_profile = _mapping(payload.get("isolation_profile"))
    capability_lineage = _mapping(payload.get("capability_lineage"))
    safe_delta_policy = _mapping(payload.get("safe_delta_policy"))
    support_boundary = _mapping(payload.get("support_boundary"))
    decommission_policy = _mapping(payload.get("decommission_policy"))
    checks = [
        _managed_copy_law_check(
            "tenant_identity_named",
            bool(_safe_text(tenant_identity.get("tenant_name"))),
            "tenant_identity_name_required",
        ),
        _managed_copy_law_check(
            "tenant_admin_declared",
            bool(_safe_text(tenant_identity.get("tenant_admin_actor"))),
            "tenant_admin_actor_required",
        ),
        _managed_copy_law_check(
            "core_surrender_blocked",
            tenant_policy.get("core_surrender_allowed") is False,
            "core_surrender_must_remain_blocked",
        ),
        _managed_copy_law_check(
            "privacy_weak_pooling_blocked",
            tenant_policy.get("privacy_weak_pooling_allowed") is False,
            "privacy_weak_pooling_must_remain_blocked",
        ),
    ]
    checks.extend(
        _managed_copy_law_check(
            f"{domain}_isolated",
            _safe_text(isolation_profile.get(domain)).casefold() == "isolated",
            f"{domain}_must_be_isolated",
        )
        for domain in _ISOLATION_DOMAINS
    )
    checks.extend(
        [
            _managed_copy_law_check(
                "capability_base_lineage_declared",
                bool(_safe_text(capability_lineage.get("base_pack"))),
                "capability_base_lineage_required",
            ),
            _managed_copy_law_check(
                "customization_layer_tenant_scoped",
                _safe_text(capability_lineage.get("customization_layer")).casefold() == "tenant",
                "customization_layer_must_be_tenant_scoped",
            ),
            _managed_copy_law_check(
                "raw_private_pooling_blocked",
                safe_delta_policy.get("raw_private_pooling_allowed") is False,
                "raw_private_pooling_must_remain_blocked",
            ),
            _managed_copy_law_check(
                "safe_delta_operator_review_required",
                safe_delta_policy.get("operator_review_required") is True,
                "safe_delta_operator_review_required",
            ),
            _managed_copy_law_check(
                "support_default_denied",
                _safe_text(support_boundary.get("support_access_default")).casefold() == "denied",
                "support_access_default_must_be_denied",
            ),
            _managed_copy_law_check(
                "support_time_bounded",
                support_boundary.get("time_bound") is True,
                "support_access_must_be_time_bounded",
            ),
            _managed_copy_law_check(
                "decommission_export_required",
                decommission_policy.get("export_required") is True,
                "decommission_export_must_be_required",
            ),
            _managed_copy_law_check(
                "decommission_proof_receipts_required",
                decommission_policy.get("proof_receipts_required") is True,
                "decommission_proof_receipts_must_be_required",
            ),
        ]
    )
    return checks


def _managed_copy_law_check(check_id: str, ready: bool, blocker: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "ready": ready,
        "status": "ready" if ready else "blocked",
        "blocker": "" if ready else blocker,
    }


def _valid_managed_copy_law_checks(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != len(_MANAGED_COPY_LAW_CHECK_IDS):
        return False
    return all(
        isinstance(item, dict)
        and _safe_text(item.get("id")) == expected_id
        and item.get("ready") is True
        and _safe_text(item.get("status")) == "ready"
        and not _safe_text(item.get("blocker"))
        for item, expected_id in zip(value, _MANAGED_COPY_LAW_CHECK_IDS, strict=True)
    )


def _creation_plan_steps(field_fingerprints: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": step_id,
            "source_field": source_field,
            "source_fingerprint": _safe_text(field_fingerprints.get(source_field)),
            "status": "planned",
            "requires_governed_approval": True,
        }
        for step_id, source_field in _PLAN_STEP_FIELDS
    ]


def _valid_creation_plan_steps(value: Any, field_fingerprints: dict[str, Any]) -> bool:
    if not isinstance(value, list) or len(value) != len(_PLAN_STEP_FIELDS):
        return False
    for item, (expected_id, expected_source_field) in zip(value, _PLAN_STEP_FIELDS, strict=True):
        if not isinstance(item, dict):
            return False
        expected_fingerprint = _safe_text(field_fingerprints.get(expected_source_field))
        if not (
            _safe_text(item.get("id")) == expected_id
            and _safe_text(item.get("source_field")) == expected_source_field
            and _safe_text(item.get("source_fingerprint")) == expected_fingerprint
            and _is_sha256(expected_fingerprint)
            and _safe_text(item.get("status")) == "planned"
            and bool(item.get("requires_governed_approval"))
        ):
            return False
    return True


def _safe_limit(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 20
    return min(max(parsed, 1), 500)


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _is_sha256(value: Any) -> bool:
    text = _safe_text(value)
    return len(text) == 64 and all(character in "0123456789abcdef" for character in text.casefold())


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _redacted_text(value: Any) -> str:
    return redact_secret_text(_safe_text(value))
