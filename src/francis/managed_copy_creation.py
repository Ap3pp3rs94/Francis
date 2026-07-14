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
MANAGED_COPY_PREFLIGHT_CONTRACT = "stage18_managed_copy_preflight_v1"
MANAGED_COPY_PREFLIGHT_RECEIPT_KIND = "francis.stage18.managed_copies.copy_preflight_receipt"
MANAGED_COPY_PREFLIGHT_RECEIPTS_KIND = "francis.stage18.managed_copies.copy_preflight_receipts"

_REQUEST_MAPPING_FIELDS = (
    "tenant_identity",
    "tenant_policy",
    "isolation_profile",
    "capability_lineage",
    "safe_delta_policy",
    "support_boundary",
    "decommission_policy",
)
_REQUEST_WRITE_LOCK = threading.Lock()
_PREFLIGHT_WRITE_LOCK = threading.Lock()


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
    return (
        _safe_text(item.get("kind")) == MANAGED_COPY_PREFLIGHT_RECEIPT_KIND
        and _safe_text(item.get("receipt_id")).startswith("managed_copy_preflight_")
        and _safe_text(item.get("contract")) == MANAGED_COPY_PREFLIGHT_CONTRACT
        and _safe_text(item.get("status")) == "preflight_passed"
        and bool(_safe_text(item.get("actor")))
        and _is_sha256(item.get("tenant_key"))
        and _is_sha256(item.get("preflight_fingerprint"))
        and _safe_text(item.get("request_receipt_id")).startswith("managed_copy_request_")
        and _is_sha256(item.get("request_fingerprint"))
        and _safe_text(item.get("stage17_closure_receipt_id")).startswith("stage17_capability_economy_closure_")
        and bool(field_presence.get("tenant_id"))
        and all(bool(field_presence.get(field)) for field in _REQUEST_MAPPING_FIELDS)
        and all(_is_sha256(field_fingerprints.get(field)) for field in _REQUEST_MAPPING_FIELDS)
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
        and not bool(governance.get("contains_raw_tenant_payload"))
        and bool(governance.get("does_not_create_copy_plan"))
        and bool(governance.get("does_not_create_copy"))
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


def _redacted_text(value: Any) -> str:
    return redact_secret_text(_safe_text(value))
