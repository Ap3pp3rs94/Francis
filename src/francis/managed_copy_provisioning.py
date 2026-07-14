from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir
from francis.telemetry.audit import record as audit_record

MANAGED_COPY_PROVISION_CONTRACT = "stage18_managed_copy_provision_v1"
MANAGED_COPY_PROVISION_RECEIPT_KIND = "francis.stage18.managed_copies.provisioning_receipt"
MANAGED_COPY_PROVISION_RECEIPTS_KIND = "francis.stage18.managed_copies.provisioning_receipts"
MANAGED_COPY_APPROVAL_CONSUMPTION_KIND = "francis.stage18.managed_copies.approval_consumption_receipt"

_REQUEST_MAPPING_FIELDS = (
    "tenant_identity",
    "tenant_policy",
    "isolation_profile",
    "capability_lineage",
    "safe_delta_policy",
    "support_boundary",
    "decommission_policy",
)
_ISOLATION_LAYOUT = {
    "tenant_data": "data",
    "tenant_memory": "memory",
    "tenant_receipts": "receipts",
    "tenant_connectors": "connectors",
    "tenant_capability_packs": "capability_packs",
    "tenant_policy": "policy",
    "support_operator_authority": "support",
}
_PROVISION_LOCK = threading.Lock()


def managed_copy_provision_plan(
    payload: dict[str, Any],
    *,
    actor: str,
    plan_receipt: dict[str, Any],
    approval_record: dict[str, Any],
) -> dict[str, Any]:
    safe_actor = _redacted_text(actor)[:240]
    provided_plan_receipt_id = _safe_text(payload.get("plan_receipt_id"))
    provided_approval_id = _safe_text(payload.get("approval_id"))
    expected_plan_receipt_id = _safe_text(plan_receipt.get("receipt_id"))
    expected_approval_id = _safe_text(approval_record.get("id"))
    approval_status = _safe_text(approval_record.get("status"))
    approval_payload = _mapping(approval_record.get("payload"))
    exact_action = _mapping(approval_payload.get("exact_action"))
    approval_action_fingerprint = _safe_text(approval_payload.get("approval_action_fingerprint"))
    tenant_id, field_presence, field_fingerprints, tenant_configuration = _tenant_evidence(payload)
    tenant_key = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest() if tenant_id else ""
    expected_tenant_key = _safe_text(plan_receipt.get("tenant_key"))
    expected_field_fingerprints = _mapping(plan_receipt.get("request_field_fingerprints"))

    blockers: list[str] = []
    if not safe_actor:
        blockers.append("copy_provision_actor_missing")
    if not plan_receipt:
        blockers.append("copy_creation_plan_receipt_missing")
    if not approval_record:
        blockers.append("copy_creation_approval_missing")
    if not provided_plan_receipt_id:
        blockers.append("copy_creation_plan_receipt_id_missing")
    elif expected_plan_receipt_id and provided_plan_receipt_id != expected_plan_receipt_id:
        blockers.append("copy_creation_plan_receipt_id_mismatch")
    if not provided_approval_id:
        blockers.append("copy_creation_approval_id_missing")
    elif expected_approval_id and provided_approval_id != expected_approval_id:
        blockers.append("copy_creation_approval_id_mismatch")
    if approval_record and approval_status != "approved":
        blockers.append("copy_creation_approval_not_approved")
    if approval_record and not _approval_exact_action_ready(
        exact_action,
        approval_action_fingerprint=approval_action_fingerprint,
        plan_receipt=plan_receipt,
    ):
        blockers.append("copy_creation_approval_exact_action_mismatch")
    if not tenant_id:
        blockers.append("tenant_id_missing")
    blockers.extend(f"{field}_missing_or_invalid" for field in _REQUEST_MAPPING_FIELDS if not field_presence[field])
    if tenant_key and expected_tenant_key and tenant_key != expected_tenant_key:
        blockers.append("tenant_key_mismatch")
    for field in _REQUEST_MAPPING_FIELDS:
        fingerprint = field_fingerprints.get(field, "")
        expected_fingerprint = _safe_text(expected_field_fingerprints.get(field))
        if fingerprint and expected_fingerprint and fingerprint != expected_fingerprint:
            blockers.append(f"{field}_fingerprint_mismatch")

    copy_id = f"managed_copy_{tenant_key[:16]}" if tenant_key else ""
    state_root = f"managed_copies/tenants/{tenant_key}" if tenant_key else ""
    isolation_paths = {
        domain: f"{state_root}/{relative_path}" if state_root else ""
        for domain, relative_path in _ISOLATION_LAYOUT.items()
    }
    fingerprint_evidence = {
        "contract": MANAGED_COPY_PROVISION_CONTRACT,
        "actor": safe_actor,
        "tenant_key": tenant_key,
        "plan_receipt_id": expected_plan_receipt_id,
        "plan_fingerprint": _safe_text(plan_receipt.get("plan_fingerprint")),
        "approval_id": expected_approval_id,
        "approval_action_fingerprint": approval_action_fingerprint,
        "request_field_fingerprints": field_fingerprints,
        "isolation_paths": isolation_paths,
    }
    provision_fingerprint = _fingerprint(fingerprint_evidence) if not blockers else ""
    existing_receipt = _provision_receipt_for_tenant(tenant_key) if tenant_key else {}
    existing_matches = bool(
        existing_receipt
        and _safe_text(existing_receipt.get("provision_fingerprint")) == provision_fingerprint
        and _safe_text(existing_receipt.get("approval_id")) == expected_approval_id
        and (_valid_provision_receipt(existing_receipt) or _valid_pending_provision_receipt(existing_receipt))
    )
    if existing_receipt and not existing_matches:
        blockers.append("tenant_key_already_provisioned")
        provision_fingerprint = ""

    return {
        "ok": not blockers,
        "kind": "francis.stage18.managed_copies.provision_plan",
        "contract": MANAGED_COPY_PROVISION_CONTRACT,
        "status": "provision_ready" if not blockers else "blocked",
        "actor": safe_actor,
        "tenant_key": tenant_key,
        "copy_id": copy_id,
        "plan_receipt_id": expected_plan_receipt_id,
        "provided_plan_receipt_id": provided_plan_receipt_id,
        "plan_fingerprint": _safe_text(plan_receipt.get("plan_fingerprint")),
        "approval_id": expected_approval_id,
        "provided_approval_id": provided_approval_id,
        "approval_status": approval_status,
        "approval_action_fingerprint": approval_action_fingerprint,
        "approval_exact_action_aligned": bool(
            approval_record
            and _approval_exact_action_ready(
                exact_action,
                approval_action_fingerprint=approval_action_fingerprint,
                plan_receipt=plan_receipt,
            )
        ),
        "request_field_presence": field_presence,
        "request_field_fingerprints": field_fingerprints,
        "isolation_paths": isolation_paths,
        "state_root": state_root,
        "provision_contract_ready": not blockers,
        "blockers": blockers,
        "provision_fingerprint": provision_fingerprint,
        "existing_provision_matches": existing_matches,
        "dry_run_confirmation": {
            "required_for_provision": True,
            "fingerprint": provision_fingerprint,
            "fingerprint_contract": MANAGED_COPY_PROVISION_CONTRACT,
        },
        "tenant_configuration": tenant_configuration,
        "writes_tenant_state": False,
        "writes_registry": False,
        "writes_receipt": False,
        "consumes_approval": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def record_managed_copy_provision(
    plan: dict[str, Any],
    *,
    provided_fingerprint: str,
    confirm_provisioning: bool,
) -> dict[str, Any]:
    expected_fingerprint = _safe_text(plan.get("provision_fingerprint"))
    if not plan.get("provision_contract_ready"):
        return _blocked("blocked_copy_provision_contract", "copy_provision_contract_not_ready")
    if not confirm_provisioning:
        return _blocked("blocked_copy_provision_confirmation", "copy_provision_confirmation_required")
    if not expected_fingerprint or _safe_text(provided_fingerprint) != expected_fingerprint:
        return _blocked("blocked_copy_provision_dry_run_confirmation", "copy_provision_fingerprint_mismatch")

    tenant_key = _safe_text(plan.get("tenant_key"))
    approval_id = _safe_text(plan.get("approval_id"))
    final_root = _tenant_root(tenant_key)
    with _PROVISION_LOCK:
        existing_receipt = _provision_receipt_for_tenant(tenant_key)
        if existing_receipt:
            if _receipt_matches_plan(existing_receipt, plan):
                if _valid_pending_provision_receipt(existing_receipt):
                    try:
                        receipt = _finalize_published_tenant(final_root, existing_receipt)
                    except (OSError, ValueError):
                        return _blocked("failed_copy_provision_recovery", "copy_provision_recovery_failed")
                    return _recorded_result(
                        receipt,
                        status="provision_recovered",
                        writes_tenant_state=False,
                        writes_registry=True,
                        writes_receipt=True,
                        consumes_approval=False,
                    )
                if not _registry_has_receipt(existing_receipt):
                    _upsert_registry(existing_receipt)
                    return _recorded_result(
                        existing_receipt,
                        status="registry_recovered",
                        writes_tenant_state=False,
                        writes_registry=True,
                        writes_receipt=False,
                        consumes_approval=False,
                    )
                return _recorded_result(
                    existing_receipt,
                    status="already_provisioned",
                    writes_tenant_state=False,
                    writes_registry=False,
                    writes_receipt=False,
                    consumes_approval=False,
                )
            return _blocked("blocked_tenant_key_conflict", "tenant_key_already_provisioned")

        consumed_receipt = _provision_receipt_for_approval(approval_id)
        if consumed_receipt:
            return _blocked("blocked_approval_reuse", "copy_creation_approval_already_consumed")

        staging_root = _staging_root(plan)
        try:
            _write_staged_tenant(staging_root, plan)
            if final_root.exists():
                return _blocked("blocked_tenant_key_conflict", "tenant_key_already_provisioned")
            final_root.parent.mkdir(parents=True, exist_ok=True)
            staging_root.replace(final_root)
            pending_receipt = _read_json(final_root / "receipts" / "provisioning.json")
            if not _valid_pending_provision_receipt(pending_receipt):
                return _blocked("failed_copy_provision_receipt", "copy_provision_receipt_invalid_after_publish")
            receipt = _finalize_published_tenant(final_root, pending_receipt)
        except (OSError, ValueError):
            return _blocked("failed_copy_provision_write", "copy_provisioning_write_failed")

    audit_record(
        "managed_copies.copy_provisioned",
        actor=_safe_text(plan.get("actor")),
        copy_id=_safe_text(plan.get("copy_id")),
        tenant_key=tenant_key,
        approval_id=approval_id,
        plan_receipt_id=_safe_text(plan.get("plan_receipt_id")),
        provision_fingerprint=expected_fingerprint,
    )
    return _recorded_result(
        receipt,
        status="provisioned",
        writes_tenant_state=True,
        writes_registry=True,
        writes_receipt=True,
        consumes_approval=True,
    )


def managed_copy_provision_receipts_readback(*, limit: int = 20) -> dict[str, Any]:
    items = sorted(
        (item for path in _tenant_roots_path().glob("*/receipts/provisioning.json") if (item := _read_json(path))),
        key=lambda item: _safe_int(item.get("recorded_ts")),
        reverse=True,
    )
    valid_items = [item for item in items if _provision_complete(item)]
    pending_items = [item for item in items if _provision_recovery_required(item)]
    latest = items[0] if items else {}
    latest_valid = valid_items[0] if valid_items else {}
    safe_limit = _safe_limit(limit)
    return {
        "ok": True,
        "kind": MANAGED_COPY_PROVISION_RECEIPTS_KIND,
        "status": "ready" if valid_items else "recovery_required" if pending_items else "empty",
        "items": items[:safe_limit],
        "count": len(items),
        "valid_count": len(valid_items),
        "pending_recovery_count": len(pending_items),
        "latest_receipt": latest,
        "latest_receipt_id": _safe_text(latest.get("receipt_id")),
        "latest_receipt_valid": _provision_complete(latest),
        "latest_valid_receipt": latest_valid,
        "latest_valid_receipt_id": _safe_text(latest_valid.get("receipt_id")),
        "copy_provisioned": bool(valid_items),
        "provision_recovery_required": bool(pending_items),
        "reads_tenant_receipts": True,
        "writes_tenant_state": False,
        "writes_registry": False,
        "writes_receipts": False,
        "consumes_approval": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "next_smallest_truthful_gap": (
            "stage18_copy_isolation_verification"
            if valid_items
            else "stage18_copy_provision_recovery"
            if pending_items
            else "stage18_copy_creation_provision"
        ),
    }


def latest_managed_copy_provision_for_approval(
    approval_id: str,
    *,
    plan_receipt_id: str = "",
    plan_fingerprint: str = "",
    include_recovery: bool = False,
) -> dict[str, Any]:
    expected_approval_id = _safe_text(approval_id)
    expected_plan_receipt_id = _safe_text(plan_receipt_id)
    expected_plan_fingerprint = _safe_text(plan_fingerprint)
    if not expected_approval_id:
        return {}
    latest: dict[str, Any] = {}
    for path in _tenant_roots_path().glob("*/receipts/provisioning.json"):
        item = _read_json(path)
        if (
            _safe_text(item.get("approval_id")) == expected_approval_id
            and (not expected_plan_receipt_id or _safe_text(item.get("plan_receipt_id")) == expected_plan_receipt_id)
            and (not expected_plan_fingerprint or _safe_text(item.get("plan_fingerprint")) == expected_plan_fingerprint)
            and (_provision_complete(item) or (include_recovery and _provision_recovery_required(item)))
        ):
            latest = {
                **item,
                "registry_aligned": _registry_has_receipt(item),
                "provision_complete": _provision_complete(item),
                "recovery_required": _provision_recovery_required(item),
            }
    return latest


def managed_copy_provision_for_copy(
    copy_id: str,
    *,
    provisioning_receipt_id: str = "",
) -> dict[str, Any]:
    expected_copy_id = _safe_text(copy_id)
    expected_receipt_id = _safe_text(provisioning_receipt_id)
    if not expected_copy_id:
        return {}
    for path in _tenant_roots_path().glob("*/receipts/provisioning.json"):
        item = _read_json(path)
        if (
            _safe_text(item.get("copy_id")) == expected_copy_id
            and (not expected_receipt_id or _safe_text(item.get("receipt_id")) == expected_receipt_id)
            and _provision_complete(item)
        ):
            return {
                **item,
                "registry_aligned": True,
                "provision_complete": True,
                "recovery_required": False,
            }
    return {}


def _write_staged_tenant(staging_root: Path, plan: dict[str, Any]) -> None:
    staging_root.mkdir(parents=True, exist_ok=False)
    for relative_path in _ISOLATION_LAYOUT.values():
        (staging_root / relative_path).mkdir(parents=True, exist_ok=False)
    config_dir = staging_root / "config"
    config_dir.mkdir(parents=True, exist_ok=False)

    configuration = _mapping(plan.get("tenant_configuration"))
    config_payload = {
        "kind": "francis.stage18.managed_copies.tenant_configuration",
        "contract": "stage18_managed_copy_configuration_v1",
        "copy_id": _safe_text(plan.get("copy_id")),
        "tenant_key": _safe_text(plan.get("tenant_key")),
        "tenant_id": _safe_text(configuration.get("tenant_id")),
        **{field: configuration.get(field) for field in _REQUEST_MAPPING_FIELDS},
        "status": "provisioned_unverified",
    }
    config_fingerprint = _fingerprint(config_payload)
    provision_fingerprint = _safe_text(plan.get("provision_fingerprint"))
    provision_receipt_id = f"managed_copy_provision_{provision_fingerprint[:16]}"
    consumption_id = (
        f"managed_copy_approval_consumption_{_fingerprint([plan.get('approval_id'), provision_fingerprint])[:16]}"
    )
    recorded_ts = int(time.time())
    state_root = _safe_text(plan.get("state_root"))
    isolation_paths = _mapping(plan.get("isolation_paths"))
    receipt = {
        "ok": True,
        "kind": MANAGED_COPY_PROVISION_RECEIPT_KIND,
        "contract": MANAGED_COPY_PROVISION_CONTRACT,
        "receipt_id": provision_receipt_id,
        "status": "tenant_published_pending_registry",
        "actor": _safe_text(plan.get("actor")),
        "copy_id": _safe_text(plan.get("copy_id")),
        "tenant_key": _safe_text(plan.get("tenant_key")),
        "plan_receipt_id": _safe_text(plan.get("plan_receipt_id")),
        "plan_fingerprint": _safe_text(plan.get("plan_fingerprint")),
        "approval_id": _safe_text(plan.get("approval_id")),
        "approval_action_fingerprint": _safe_text(plan.get("approval_action_fingerprint")),
        "approval_consumption_id": consumption_id,
        "provision_fingerprint": provision_fingerprint,
        "request_field_fingerprints": dict(plan.get("request_field_fingerprints") or {}),
        "config_fingerprint": config_fingerprint,
        "state_root": state_root,
        "isolation_paths": isolation_paths,
        "isolation_domains_created": list(_ISOLATION_LAYOUT),
        "tenant_state_written": True,
        "registry_written": False,
        "approval_consumed": True,
        "single_use_enforced": True,
        "isolation_verified": False,
        "runtime_started": False,
        "recorded_ts": recorded_ts,
        "governance": {
            "approved_exact_action_required": True,
            "approval_action_fingerprint_matched": True,
            "request_payload_fingerprints_matched": True,
            "tenant_root_atomically_published": True,
            "registry_entry_written": False,
            "approval_consumed_once": True,
            "raw_tenant_payload_tenant_local_only": True,
            "cross_tenant_state_written": False,
            "runtime_started": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }
    consumption = {
        "ok": True,
        "kind": MANAGED_COPY_APPROVAL_CONSUMPTION_KIND,
        "receipt_id": consumption_id,
        "status": "consumed",
        "actor": _safe_text(plan.get("actor")),
        "approval_id": _safe_text(plan.get("approval_id")),
        "approval_action_fingerprint": _safe_text(plan.get("approval_action_fingerprint")),
        "plan_receipt_id": _safe_text(plan.get("plan_receipt_id")),
        "provision_fingerprint": provision_fingerprint,
        "provisioning_receipt_id": provision_receipt_id,
        "approval_consumed": True,
        "single_use_enforced": True,
        "tenant_state_written": True,
        "runtime_started": False,
        "recorded_ts": recorded_ts,
        "governance": {
            "approved_exact_action_binding_checked": True,
            "consumed_with_atomic_tenant_publish": True,
            "approval_reuse_blocked_by_tenant_receipt": True,
            "runtime_started": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }
    manifest = {
        "kind": "francis.stage18.managed_copies.tenant_manifest",
        "contract": "stage18_managed_copy_tenant_manifest_v1",
        "copy_id": receipt["copy_id"],
        "tenant_key": receipt["tenant_key"],
        "status": receipt["status"],
        "state_root": state_root,
        "configuration_path": f"{state_root}/config/managed_copy.json",
        "config_fingerprint": config_fingerprint,
        "plan_receipt_id": receipt["plan_receipt_id"],
        "approval_id": receipt["approval_id"],
        "approval_consumption_id": consumption_id,
        "provisioning_receipt_id": provision_receipt_id,
        "registry_written": False,
        "isolation_paths": isolation_paths,
        "recorded_ts": recorded_ts,
    }
    _write_json(config_dir / "managed_copy.json", config_payload)
    _write_json(staging_root / "receipts" / "approval_consumption.json", consumption)
    _write_json(staging_root / "receipts" / "provisioning.json", receipt)
    _write_json(staging_root / "manifest.json", manifest)


def _recorded_result(
    receipt: dict[str, Any],
    *,
    status: str,
    writes_tenant_state: bool,
    writes_registry: bool,
    writes_receipt: bool,
    consumes_approval: bool,
) -> dict[str, Any]:
    return {
        "ok": True,
        "status": status,
        "error": "",
        "receipt": receipt,
        "receipt_id": _safe_text(receipt.get("receipt_id")),
        "copy_id": _safe_text(receipt.get("copy_id")),
        "copy_provisioned": True,
        "approval_consumed": True,
        "single_use_enforced": True,
        "writes_tenant_state": writes_tenant_state,
        "writes_registry": writes_registry,
        "writes_receipt": writes_receipt,
        "consumes_approval": consumes_approval,
        "starts_runtime": False,
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
        "copy_id": "",
        "copy_provisioned": False,
        "approval_consumed": False,
        "single_use_enforced": False,
        "writes_tenant_state": False,
        "writes_registry": False,
        "writes_receipt": False,
        "consumes_approval": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def _approval_exact_action_ready(
    exact_action: dict[str, Any],
    *,
    approval_action_fingerprint: str,
    plan_receipt: dict[str, Any],
) -> bool:
    return (
        _is_sha256(approval_action_fingerprint)
        and approval_action_fingerprint == _fingerprint(exact_action)
        and _safe_text(exact_action.get("requested_action")) == "managed_copies.provision_copy"
        and _safe_text(exact_action.get("plan_receipt_id")) == _safe_text(plan_receipt.get("receipt_id"))
        and _safe_text(exact_action.get("plan_fingerprint")) == _safe_text(plan_receipt.get("plan_fingerprint"))
        and _safe_text(exact_action.get("tenant_key")) == _safe_text(plan_receipt.get("tenant_key"))
    )


def _tenant_evidence(
    payload: dict[str, Any],
) -> tuple[str, dict[str, bool], dict[str, str], dict[str, Any]]:
    tenant_id = _safe_text(payload.get("tenant_id"))
    presence = {"tenant_id": bool(tenant_id)}
    fingerprints: dict[str, str] = {}
    configuration: dict[str, Any] = {"tenant_id": tenant_id}
    for field in _REQUEST_MAPPING_FIELDS:
        value = payload.get(field)
        present = isinstance(value, dict) and bool(value)
        presence[field] = present
        configuration[field] = dict(value) if isinstance(value, dict) else {}
        if present:
            fingerprints[field] = _fingerprint(value)
    return tenant_id, presence, fingerprints, configuration


def _valid_provision_receipt(item: dict[str, Any]) -> bool:
    governance = _mapping(item.get("governance"))
    return (
        _valid_provision_receipt_core(item)
        and _safe_text(item.get("status")) == "provisioned_unverified"
        and bool(item.get("registry_written"))
        and bool(governance.get("registry_entry_written"))
    )


def _valid_pending_provision_receipt(item: dict[str, Any]) -> bool:
    governance = _mapping(item.get("governance"))
    return (
        _valid_provision_receipt_core(item)
        and _safe_text(item.get("status")) == "tenant_published_pending_registry"
        and not bool(item.get("registry_written"))
        and not bool(governance.get("registry_entry_written"))
    )


def _provision_complete(item: dict[str, Any]) -> bool:
    return _valid_provision_receipt(item) and _registry_has_receipt(item)


def _provision_recovery_required(item: dict[str, Any]) -> bool:
    return _valid_pending_provision_receipt(item) or (
        _valid_provision_receipt(item) and not _registry_has_receipt(item)
    )


def _valid_provision_receipt_core(item: dict[str, Any]) -> bool:
    governance = _mapping(item.get("governance"))
    field_fingerprints = _mapping(item.get("request_field_fingerprints"))
    isolation_paths = _mapping(item.get("isolation_paths"))
    fingerprint_evidence = {
        "contract": _safe_text(item.get("contract")),
        "actor": _safe_text(item.get("actor")),
        "tenant_key": _safe_text(item.get("tenant_key")),
        "plan_receipt_id": _safe_text(item.get("plan_receipt_id")),
        "plan_fingerprint": _safe_text(item.get("plan_fingerprint")),
        "approval_id": _safe_text(item.get("approval_id")),
        "approval_action_fingerprint": _safe_text(item.get("approval_action_fingerprint")),
        "request_field_fingerprints": field_fingerprints,
        "isolation_paths": isolation_paths,
    }
    return (
        _safe_text(item.get("kind")) == MANAGED_COPY_PROVISION_RECEIPT_KIND
        and _safe_text(item.get("contract")) == MANAGED_COPY_PROVISION_CONTRACT
        and _safe_text(item.get("receipt_id")).startswith("managed_copy_provision_")
        and bool(_safe_text(item.get("actor")))
        and _safe_text(item.get("copy_id")).startswith("managed_copy_")
        and _is_sha256(item.get("tenant_key"))
        and _safe_text(item.get("plan_receipt_id")).startswith("managed_copy_creation_plan_")
        and _is_sha256(item.get("plan_fingerprint"))
        and bool(_safe_text(item.get("approval_id")))
        and _is_sha256(item.get("approval_action_fingerprint"))
        and _safe_text(item.get("approval_consumption_id")).startswith("managed_copy_approval_consumption_")
        and _is_sha256(item.get("provision_fingerprint"))
        and _safe_text(item.get("provision_fingerprint")) == _fingerprint(fingerprint_evidence)
        and all(_is_sha256(field_fingerprints.get(field)) for field in _REQUEST_MAPPING_FIELDS)
        and set(isolation_paths) == set(_ISOLATION_LAYOUT)
        and set(item.get("isolation_domains_created") or []) == set(_ISOLATION_LAYOUT)
        and _is_sha256(item.get("config_fingerprint"))
        and bool(_safe_text(item.get("state_root")))
        and bool(item.get("tenant_state_written"))
        and bool(item.get("approval_consumed"))
        and bool(item.get("single_use_enforced"))
        and not bool(item.get("isolation_verified"))
        and not bool(item.get("runtime_started"))
        and _safe_int(item.get("recorded_ts")) > 0
        and bool(governance.get("approved_exact_action_required"))
        and bool(governance.get("approval_action_fingerprint_matched"))
        and bool(governance.get("request_payload_fingerprints_matched"))
        and bool(governance.get("tenant_root_atomically_published"))
        and bool(governance.get("approval_consumed_once"))
        and bool(governance.get("raw_tenant_payload_tenant_local_only"))
        and not bool(governance.get("cross_tenant_state_written"))
        and not bool(governance.get("runtime_started"))
        and not bool(governance.get("grants_execution_authority"))
        and not bool(governance.get("grants_mutation_authority"))
    )


def _provision_receipt_for_tenant(tenant_key: str) -> dict[str, Any]:
    return _read_json(_tenant_root(tenant_key) / "receipts" / "provisioning.json")


def _provision_receipt_for_approval(approval_id: str) -> dict[str, Any]:
    for path in _tenant_roots_path().glob("*/receipts/provisioning.json"):
        item = _read_json(path)
        if _safe_text(item.get("approval_id")) == approval_id and (
            _valid_provision_receipt(item) or _valid_pending_provision_receipt(item)
        ):
            return item
    return {}


def _receipt_matches_plan(receipt: dict[str, Any], plan: dict[str, Any]) -> bool:
    return (
        _safe_text(receipt.get("provision_fingerprint")) == _safe_text(plan.get("provision_fingerprint"))
        and _safe_text(receipt.get("approval_id")) == _safe_text(plan.get("approval_id"))
        and (_valid_provision_receipt(receipt) or _valid_pending_provision_receipt(receipt))
    )


def _finalize_published_tenant(final_root: Path, pending_receipt: dict[str, Any]) -> dict[str, Any]:
    if not _valid_pending_provision_receipt(pending_receipt):
        raise ValueError("pending provisioning receipt is invalid")

    receipt = dict(pending_receipt)
    receipt["status"] = "provisioned_unverified"
    receipt["registry_written"] = True
    governance = dict(_mapping(receipt.get("governance")))
    governance["registry_entry_written"] = True
    receipt["governance"] = governance

    _upsert_registry(receipt)
    manifest_path = final_root / "manifest.json"
    manifest = _read_json(manifest_path)
    if not manifest:
        raise ValueError("tenant manifest is missing")
    manifest["status"] = "provisioned_unverified"
    manifest["registry_written"] = True
    _write_json_atomic(manifest_path, manifest)
    _write_json_atomic(final_root / "receipts" / "provisioning.json", receipt)
    if not _valid_provision_receipt(receipt):
        raise ValueError("final provisioning receipt is invalid")
    return receipt


def _upsert_registry(receipt: dict[str, Any]) -> None:
    path = _registry_path()
    registry = _read_json(path)
    items = _mapping(registry.get("items"))
    copy_id = _safe_text(receipt.get("copy_id"))
    items[copy_id] = {
        "copy_id": copy_id,
        "tenant_key": _safe_text(receipt.get("tenant_key")),
        "status": "provisioned_unverified",
        "state_root": _safe_text(receipt.get("state_root")),
        "plan_receipt_id": _safe_text(receipt.get("plan_receipt_id")),
        "approval_id": _safe_text(receipt.get("approval_id")),
        "provisioning_receipt_id": _safe_text(receipt.get("receipt_id")),
        "updated_ts": _safe_int(receipt.get("recorded_ts")),
    }
    _write_json_atomic(
        path,
        {
            "kind": "francis.stage18.managed_copies.registry",
            "contract": "stage18_managed_copy_registry_v1",
            "items": items,
        },
    )


def _registry_has_receipt(receipt: dict[str, Any]) -> bool:
    items = _mapping(_read_json(_registry_path()).get("items"))
    item = _mapping(items.get(_safe_text(receipt.get("copy_id"))))
    return (
        _safe_text(item.get("tenant_key")) == _safe_text(receipt.get("tenant_key"))
        and _safe_text(item.get("plan_receipt_id")) == _safe_text(receipt.get("plan_receipt_id"))
        and _safe_text(item.get("approval_id")) == _safe_text(receipt.get("approval_id"))
        and _safe_text(item.get("provisioning_receipt_id")) == _safe_text(receipt.get("receipt_id"))
    )


def _tenant_roots_path() -> Path:
    return data_dir() / "managed_copies" / "tenants"


def _tenant_root(tenant_key: str) -> Path:
    return _tenant_roots_path() / tenant_key


def _staging_root(plan: dict[str, Any]) -> Path:
    name = f"{_safe_text(plan.get('copy_id'))}-{uuid.uuid4().hex}"
    return data_dir() / "managed_copies" / ".staging" / name


def _registry_path() -> Path:
    return data_dir() / "managed_copies" / "registry.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep the sibling name short enough for deep Windows tenant roots.
    temporary = path.with_name(f".{uuid.uuid4().hex[:12]}")
    _write_json(temporary, payload)
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


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


def _fingerprint(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _redacted_text(value: Any) -> str:
    return redact_secret_text(_safe_text(value))
