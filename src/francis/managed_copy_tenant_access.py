from __future__ import annotations

import hashlib
import json
from typing import Any

from francis.governance.redaction import redact_secret_text
from francis.managed_copy_isolation import (
    latest_managed_copy_isolation_verification_for_provision,
    managed_copy_isolation_guarded_subpath,
)
from francis.managed_copy_provisioning import managed_copy_provision_for_copy

CONTRACT = "stage18_managed_copy_tenant_access_boundary_v1"
KIND = "francis.stage18.managed_copies.tenant_access_check"
ISOLATION_POLICY_DECISION_CONTRACT = "stage18_managed_copy_isolation_policy_decision_v1"
ISOLATION_POLICY_DECISION_KIND = "francis.stage18.managed_copies.isolation_policy_decision"
_FIELDS = {
    "request_actor",
    "copy_id",
    "tenant_key",
    "provisioning_receipt_id",
    "isolation_verification_receipt_id",
    "domain",
}
ISOLATION_DOMAINS = {
    "tenant_data",
    "tenant_memory",
    "tenant_receipts",
    "tenant_connectors",
    "tenant_capability_packs",
    "tenant_policy",
    "support_operator_authority",
}
ISOLATION_POLICY_OPERATIONS = {"invoke", "read", "write"}
_ISOLATION_POLICY_FIELDS = {
    "source_tenant_key",
    "target_tenant_key",
    "domain",
    "operation",
}
_NO_AUTHORITY = {
    "filesystem_acl_isolation_verified": False,
    "process_isolation_verified": False,
    "network_isolation_verified": False,
    "full_customer_isolation_verified": False,
    "reads_tenant_content": False,
    "writes_receipts": False,
    "writes_tenant_state": False,
    "uses_tools": False,
    "uses_shell": False,
    "uses_network": False,
    "grants_execution_authority": False,
    "grants_mutation_authority": False,
}


def managed_copy_tenant_access_check(payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    safe_actor = _redacted(actor)
    request_actor = _redacted(payload.get("request_actor"))
    copy_id = _text(payload.get("copy_id"))
    tenant_key = _text(payload.get("tenant_key"))
    provision_id = _text(payload.get("provisioning_receipt_id"))
    isolation_id = _text(payload.get("isolation_verification_receipt_id"))
    domain = _text(payload.get("domain"))
    blockers: list[str] = []
    if set(payload) - _FIELDS:
        blockers.append("tenant_access_unknown_fields")
    if not safe_actor or safe_actor != request_actor:
        blockers.append("tenant_access_actor_lineage_mismatch")
    if not copy_id or not tenant_key or not provision_id or not isolation_id:
        blockers.append("tenant_access_lineage_required")
    if domain not in ISOLATION_DOMAINS:
        blockers.append("tenant_access_domain_not_allowed")

    provision = managed_copy_provision_for_copy(copy_id, provisioning_receipt_id=provision_id)
    if not provision:
        blockers.append("tenant_access_provision_not_found")
    elif _text(provision.get("tenant_key")) != tenant_key:
        blockers.append("tenant_access_cross_tenant_denied")
    isolation = (
        latest_managed_copy_isolation_verification_for_provision(
            provision_id,
            provision_fingerprint=_text(provision.get("provision_fingerprint")),
            copy_id=copy_id,
        )
        if provision
        else {}
    )
    if _text(isolation.get("receipt_id")) != isolation_id:
        blockers.append("tenant_access_isolation_lineage_mismatch")
    if isolation and isolation.get("live_state_aligned") is not True:
        blockers.append("tenant_access_isolation_drift_detected")

    resolved = None
    if not blockers:
        resolved = managed_copy_isolation_guarded_subpath(provision, isolation, domain=domain)
        if resolved is None:
            blockers.append("tenant_access_guard_denied")
    access_allowed = not blockers and resolved is not None
    binding = {
        "contract": CONTRACT,
        "actor": safe_actor,
        "copy_id": copy_id,
        "tenant_key": tenant_key,
        "provisioning_receipt_id": provision_id,
        "isolation_verification_receipt_id": isolation_id,
        "domain": domain,
        "access_allowed": access_allowed,
        "blockers": sorted(set(blockers)),
    }
    return {
        "ok": access_allowed,
        "kind": KIND,
        "contract": CONTRACT,
        "status": "tenant_access_allowed" if access_allowed else "tenant_access_denied",
        "actor": safe_actor,
        "copy_id": copy_id,
        "tenant_key": tenant_key,
        "provisioning_receipt_id": provision_id,
        "isolation_verification_receipt_id": isolation_id,
        "domain": domain if domain in ISOLATION_DOMAINS else "unknown",
        "access_allowed": access_allowed,
        "application_access_boundary_enforced": True,
        "resolved_path_exposed": False,
        "decision_fingerprint": _fingerprint(binding),
        "blockers": sorted(set(blockers)),
        "governance": {
            "exact_live_lineage_required": True,
            "cross_tenant_access_denied": True,
            "guarded_path_resolver_required": True,
            "resolved_path_exposed": False,
            **_NO_AUTHORITY,
        },
        **_NO_AUTHORITY,
    }


def managed_copy_isolation_policy_decision(payload: dict[str, Any]) -> dict[str, Any]:
    """Classify a proposed tenant flow without authorizing or resolving access."""
    source_tenant_key = _exact_text(payload.get("source_tenant_key"))
    target_tenant_key = _exact_text(payload.get("target_tenant_key"))
    domain = _exact_text(payload.get("domain"))
    operation = _exact_text(payload.get("operation"))
    blockers: list[str] = []
    if set(payload) != _ISOLATION_POLICY_FIELDS:
        blockers.append("isolation_policy_exact_schema_required")
    for field in _ISOLATION_POLICY_FIELDS:
        if not _exact_text(payload.get(field)):
            blockers.append(f"isolation_policy_{field}_invalid")
    if domain not in ISOLATION_DOMAINS:
        blockers.append("isolation_policy_domain_not_allowed")
    if operation not in ISOLATION_POLICY_OPERATIONS:
        blockers.append("isolation_policy_operation_not_allowed")
    if source_tenant_key and target_tenant_key and source_tenant_key != target_tenant_key:
        blockers.append("isolation_policy_cross_tenant_flow_denied")
    if domain == "support_operator_authority":
        blockers.append("isolation_policy_support_authority_requires_separate_governed_path")

    normalized_blockers = sorted(set(blockers))
    policy_compatible = not normalized_blockers
    binding = {
        "contract": ISOLATION_POLICY_DECISION_CONTRACT,
        "source_tenant_key": source_tenant_key,
        "target_tenant_key": target_tenant_key,
        "domain": domain,
        "operation": operation,
        "policy_compatible": policy_compatible,
        "blockers": normalized_blockers,
    }
    return {
        "ok": policy_compatible,
        "kind": ISOLATION_POLICY_DECISION_KIND,
        "contract": ISOLATION_POLICY_DECISION_CONTRACT,
        "status": "policy_compatible" if policy_compatible else "policy_denied",
        "policy_compatible": policy_compatible,
        "decision_is_authorization": False,
        "requires_live_lineage_validation": True,
        "requires_guarded_access_boundary": True,
        "domain": domain if domain in ISOLATION_DOMAINS else "unknown",
        "operation": operation if operation in ISOLATION_POLICY_OPERATIONS else "unknown",
        "same_tenant": bool(source_tenant_key and source_tenant_key == target_tenant_key),
        "decision_fingerprint": _fingerprint(binding),
        "blockers": normalized_blockers,
        "reads_tenant_content": False,
        "resolves_lineage": False,
        "accesses_filesystem": False,
        "resolved_path_exposed": False,
        "writes_receipts": False,
        "writes_tenant_state": False,
        "uses_tools": False,
        "uses_shell": False,
        "uses_network": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def _fingerprint(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _redacted(value: Any) -> str:
    return _text(redact_secret_text(str(value) if value is not None else ""))[:240]


def _exact_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""
