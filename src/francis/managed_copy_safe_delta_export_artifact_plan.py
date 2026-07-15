from __future__ import annotations

import hashlib
import json
from typing import Any

from francis.governance.redaction import redact_secret_text
from francis.managed_copy_safe_delta_export_authorization_decision import (
    managed_copy_safe_delta_export_authorization_decisions_readback,
)

CONTRACT = "stage18_managed_copy_safe_delta_export_artifact_plan_v1"
KIND = "francis.stage18.managed_copies.safe_delta_export_artifact_plan"
MEDIA_TYPE = "application/vnd.francis.safe-delta+json"
SCHEMA_CLASS = "safe_delta_signal_v1"
RETENTION_CLASS = "transient_operator_export"
_FIELDS = {
    "request_actor",
    "copy_id",
    "provisioning_receipt_id",
    "isolation_verification_receipt_id",
    "review_fingerprint",
    "preflight_fingerprint",
    "request_fingerprint",
    "authorization_decision_receipt_id",
    "authorization_decision_fingerprint",
    "artifact_media_type",
    "artifact_schema_class",
    "retention_class",
    "artifact_count",
    "dry_run",
}
_NO_EFFECT = {
    "export_approved": False,
    "export_executed": False,
    "safe_delta_exported": False,
    "safe_delta_flow_active": False,
    "writes_file": False,
    "writes_receipt": False,
    "writes_plan": False,
    "writes_artifact": False,
    "writes_manifest": False,
    "writes_payload": False,
    "writes_tenant_state": False,
    "writes_memory": False,
    "writes_registry": False,
    "writes_learning": False,
    "uses_network": False,
    "grants_approval_authority": False,
    "grants_export_authority": False,
    "grants_execution_authority": False,
    "grants_mutation_authority": False,
}


def managed_copy_safe_delta_export_artifact_plan(payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    safe_actor = _redacted(actor)[:240]
    request_actor = _redacted(payload.get("request_actor"))[:240]
    unknown = sorted(set(payload) - _FIELDS)
    bounded = {key: _text(payload.get(key)) for key in _FIELDS if key not in {"dry_run", "artifact_count"}}
    artifact_count = payload.get("artifact_count")
    blockers: list[str] = []
    if unknown:
        blockers.append("safe_delta_export_artifact_plan_unknown_fields")
    if not safe_actor or request_actor != safe_actor:
        blockers.append("safe_delta_export_artifact_plan_actor_lineage_mismatch")
    if payload.get("dry_run") is not True:
        blockers.append("safe_delta_export_artifact_plan_dry_run_true_required")
    if artifact_count != 1 or isinstance(artifact_count, bool):
        blockers.append("safe_delta_export_artifact_plan_artifact_count_invalid")
    if bounded["artifact_media_type"] != MEDIA_TYPE:
        blockers.append("safe_delta_export_artifact_plan_media_type_invalid")
    if bounded["artifact_schema_class"] != SCHEMA_CLASS:
        blockers.append("safe_delta_export_artifact_plan_schema_class_invalid")
    if bounded["retention_class"] != RETENTION_CLASS:
        blockers.append("safe_delta_export_artifact_plan_retention_class_invalid")
    readback = managed_copy_safe_delta_export_authorization_decisions_readback(
        copy_id=bounded["copy_id"],
        provisioning_receipt_id=bounded["provisioning_receipt_id"],
        isolation_verification_receipt_id=bounded["isolation_verification_receipt_id"],
        limit=500,
    )
    matches = [
        item
        for item in readback.get("items", [])
        if isinstance(item, dict)
        and item.get("receipt_id") == bounded["authorization_decision_receipt_id"]
        and item.get("authorization_decision_fingerprint") == bounded["authorization_decision_fingerprint"]
    ]
    decision = matches[0] if len(matches) == 1 else {}
    lineage = (
        "copy_id",
        "provisioning_receipt_id",
        "isolation_verification_receipt_id",
        "review_fingerprint",
        "preflight_fingerprint",
        "request_fingerprint",
    )
    if not decision or any(decision.get(key) != bounded[key] for key in lineage):
        blockers.append("safe_delta_export_artifact_plan_decision_missing_or_mismatch")
    elif decision.get("decision") != "approved" or decision.get("status") != "export_authorization_approved":
        blockers.append("safe_delta_export_artifact_plan_decision_not_approved")
    binding = {
        "contract": CONTRACT,
        "actor": safe_actor,
        **bounded,
        "artifact_count": artifact_count,
        "tenant_key": _text(decision.get("tenant_key")),
        "decision_receipt_fingerprint": _text(decision.get("receipt_fingerprint")),
    }
    fingerprint = _fingerprint(binding) if not blockers else ""
    return {
        "ok": not blockers,
        "kind": KIND,
        "status": "export_artifact_plan_ready" if not blockers else "blocked",
        "error": "" if not blockers else "safe_delta_export_artifact_plan_not_ready",
        "contract": CONTRACT,
        "actor": safe_actor,
        "copy_id": bounded["copy_id"],
        "provisioning_receipt_id": bounded["provisioning_receipt_id"],
        "isolation_verification_receipt_id": bounded["isolation_verification_receipt_id"],
        "review_fingerprint": bounded["review_fingerprint"],
        "preflight_fingerprint": bounded["preflight_fingerprint"],
        "request_fingerprint": bounded["request_fingerprint"],
        "authorization_decision_receipt_id": bounded["authorization_decision_receipt_id"],
        "authorization_decision_fingerprint": bounded["authorization_decision_fingerprint"],
        "artifact_media_type": bounded["artifact_media_type"],
        "artifact_schema_class": bounded["artifact_schema_class"],
        "retention_class": bounded["retention_class"],
        "artifact_count": artifact_count if artifact_count == 1 else 0,
        "manifest_entry_count": 0,
        "payload_byte_count": 0,
        "artifact_plan_fingerprint": fingerprint,
        "blockers": blockers,
        "unknown_fields": unknown,
        "dry_run": payload.get("dry_run") is True,
        **_NO_EFFECT,
    }


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _redacted(value: Any) -> str:
    return redact_secret_text(value).strip() if isinstance(value, str) else ""
