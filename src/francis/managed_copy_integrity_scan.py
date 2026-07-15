from __future__ import annotations

import hashlib
import json
from typing import Any

from francis.governance.redaction import redact_secret_text
from francis.managed_copy_isolation import (
    latest_managed_copy_isolation_verification_for_provision,
    managed_copy_isolation_integrity_checks,
)
from francis.managed_copy_provisioning import managed_copy_provision_for_copy

CONTRACT = "stage18_managed_copy_integrity_scan_v1"
KIND = "francis.stage18.managed_copies.integrity_scan"
_FIELDS = {"request_actor", "copy_id", "provisioning_receipt_id", "isolation_verification_receipt_id"}
_NO_AUTHORITY = {
    "rogue_detected": False,
    "halts_copy": False,
    "quarantines_copy": False,
    "replaces_copy": False,
    "restores_copy": False,
    "writes_receipts": False,
    "writes_tenant_state": False,
    "uses_tools": False,
    "uses_shell": False,
    "uses_network": False,
    "grants_execution_authority": False,
    "grants_mutation_authority": False,
}
_DOMAIN_CHECK_IDS = {
    "tenant_data",
    "tenant_memory",
    "tenant_receipts",
    "tenant_connectors",
    "tenant_capability_packs",
    "tenant_policy",
    "support_operator_authority",
}
_ARTIFACT_BLOCKERS = {
    "tenant_root_canonical": "tenant_root_not_canonical",
    "tenant_root_not_linked": "tenant_root_link_boundary_not_allowed",
    "tenant_layout_exact": "tenant_root_layout_mismatch",
    "tenant_configuration_identity_aligned": "tenant_configuration_identity_mismatch",
    "tenant_configuration_fingerprint_aligned": "tenant_configuration_fingerprint_mismatch",
    "tenant_configuration_fields_aligned": "tenant_configuration_field_fingerprint_mismatch",
    "tenant_manifest_identity_aligned": "tenant_manifest_identity_mismatch",
    "tenant_manifest_lineage_aligned": "tenant_manifest_lineage_mismatch",
    "provisioning_receipt_aligned": "tenant_provisioning_receipt_mismatch",
    "approval_consumption_aligned": "tenant_approval_consumption_mismatch",
    "registry_aligned": "managed_copy_registry_mismatch",
    "copy_identity_unique": "copy_identity_not_unique",
    "tenant_key_unique": "tenant_key_not_unique",
}


def managed_copy_integrity_scan(payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    safe_actor = _text(redact_secret_text(str(actor)))[:240]
    request_actor = _text(redact_secret_text(str(payload.get("request_actor", ""))))[:240]
    copy_id = _text(payload.get("copy_id"))
    provision_id = _text(payload.get("provisioning_receipt_id"))
    isolation_id = _text(payload.get("isolation_verification_receipt_id"))
    blockers: list[str] = []
    if sorted(set(payload) - _FIELDS):
        blockers.append("integrity_scan_unknown_fields")
    if not safe_actor or safe_actor != request_actor:
        blockers.append("integrity_scan_actor_lineage_mismatch")
    if not copy_id or not provision_id or not isolation_id:
        blockers.append("integrity_scan_lineage_required")

    provision = managed_copy_provision_for_copy(copy_id, provisioning_receipt_id=provision_id)
    if not provision:
        blockers.append("integrity_scan_provision_not_found")
        isolation_plan: dict[str, Any] = {}
    else:
        isolation_receipt = latest_managed_copy_isolation_verification_for_provision(
            provision_id,
            provision_fingerprint=_text(provision.get("provision_fingerprint")),
            copy_id=copy_id,
        )
        if _text(isolation_receipt.get("receipt_id")) != isolation_id:
            blockers.append("integrity_scan_isolation_receipt_lineage_mismatch")
        domain_checks, artifact_checks = managed_copy_isolation_integrity_checks(provision)
        isolation_plan = {
            "domain_checks": domain_checks,
            "artifact_checks": artifact_checks,
        }

    findings = _derived_findings(isolation_plan)
    if blockers:
        status = "blocked"
    elif findings:
        status = "integrity_drift_detected"
    else:
        status = "integrity_aligned"
    fingerprint_payload = {
        "contract": CONTRACT,
        "actor": safe_actor,
        "copy_id": copy_id,
        "provisioning_receipt_id": provision_id,
        "isolation_verification_receipt_id": isolation_id,
        "findings": findings,
        "blockers": sorted(set(blockers)),
    }
    return {
        "ok": not blockers,
        "kind": KIND,
        "contract": CONTRACT,
        "status": status,
        "actor": safe_actor,
        "copy_id": copy_id,
        "provisioning_receipt_id": provision_id,
        "isolation_verification_receipt_id": isolation_id,
        "scan_fingerprint": _fingerprint(fingerprint_payload),
        "finding_count": len(findings),
        "findings": findings,
        "blockers": sorted(set(blockers)),
        "integrity_aligned": status == "integrity_aligned",
        "integrity_drift_detected": status == "integrity_drift_detected",
        "governance": {
            "read_only_metadata_scan": True,
            "derived_findings_only": True,
            "does_not_inspect_raw_tenant_payloads": True,
            **_NO_AUTHORITY,
        },
        **_NO_AUTHORITY,
    }


def managed_copy_integrity_finding_is_valid(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"id", "severity", "source_contract", "blocker"}:
        return False
    finding_id = _text(value.get("id"))
    prefix = "managed_copy_integrity:"
    check_id = finding_id[len(prefix) :] if finding_id.startswith(prefix) else ""
    blocker = _text(value.get("blocker"))
    if check_id in _DOMAIN_CHECK_IDS:
        allowed_blockers = {
            f"{check_id}_path_contract_mismatch",
            f"{check_id}_directory_missing",
            f"{check_id}_link_boundary_not_allowed",
            f"{check_id}_path_escapes_tenant_root",
            "tenant_root_invalid",
        }
    else:
        allowed_blockers = {_ARTIFACT_BLOCKERS[check_id]} if check_id in _ARTIFACT_BLOCKERS else set()
    return bool(
        allowed_blockers
        and blocker in allowed_blockers
        and value.get("severity") == "high"
        and value.get("source_contract") == "stage18_managed_copy_structural_isolation_verification_v1"
    )


def _derived_findings(plan: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for check in [*(plan.get("domain_checks") or []), *(plan.get("artifact_checks") or [])]:
        if not isinstance(check, dict) or check.get("ready") is True:
            continue
        check_id = _text(check.get("id")) or "unknown_integrity_check"
        findings.append(
            {
                "id": f"managed_copy_integrity:{check_id}",
                "severity": "high",
                "source_contract": "stage18_managed_copy_structural_isolation_verification_v1",
                "blocker": _text(check.get("blocker")) or f"{check_id}_not_ready",
            }
        )
    return sorted(findings, key=lambda item: item["id"])


def _fingerprint(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""
