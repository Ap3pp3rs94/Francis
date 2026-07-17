from __future__ import annotations

import hashlib
import json
from typing import Any

from francis.governance.redaction import redact_secret_text
from francis.managed_copy_integrity_evidence import managed_copy_integrity_evidence_readback
from francis.managed_copy_integrity_triage_disposition import managed_copy_integrity_triage_dispositions_readback
from francis.managed_copy_isolation import latest_managed_copy_isolation_verification_for_provision
from francis.managed_copy_provisioning import managed_copy_provision_for_copy

CONTRACT = "stage18_managed_copy_rogue_recovery_plan_v1"
KIND = "francis.stage18.managed_copies.rogue_recovery_plan"
REPLACEMENT_SOURCES = frozenset(
    {
        "clean_core_baseline",
        "trusted_known_good_snapshot",
        "validated_global_state",
        "controlled_customer_configuration_state",
    }
)
_FIELDS = frozenset(
    {
        "request_actor",
        "copy_id",
        "provisioning_receipt_id",
        "isolation_verification_receipt_id",
        "integrity_evidence_receipt_id",
        "integrity_evidence_fingerprint",
        "disposition_receipt_id",
        "disposition_fingerprint",
        "replacement_source",
        "recovery_intent_fingerprint",
        "dry_run",
    }
)
_NO_EFFECT = {
    "rogue_detected": False,
    "incident_opened": False,
    "incident_resolved": False,
    "halts_copy": False,
    "quarantines_copy": False,
    "preserves_evidence": False,
    "replaces_copy": False,
    "restores_copy": False,
    "starts_runtime": False,
    "writes_receipt": False,
    "writes_receipts": False,
    "writes_tenant_state": False,
    "writes_registry": False,
    "writes_memory": False,
    "uses_tools": False,
    "uses_shell": False,
    "uses_git": False,
    "uses_network": False,
    "grants_execution_authority": False,
    "grants_mutation_authority": False,
}
_STEPS = (
    ("halt", "operator_approval_required"),
    ("quarantine", "blocked_by_halt_receipt"),
    ("preserve_evidence", "blocked_by_quarantine_receipt"),
    ("support_review", "blocked_by_evidence_preservation_receipt"),
    ("replace", "blocked_by_support_review_and_clean_baseline_receipts"),
    ("verify_replacement", "blocked_by_replacement_receipt"),
    ("restore_continuity", "blocked_by_replacement_verification_receipt"),
)


def managed_copy_rogue_recovery_plan(payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    safe_actor = _redacted(actor)[:240]
    request_actor = _redacted(payload.get("request_actor"))[:240]
    bounded = {key: _text(payload.get(key)) for key in _FIELDS if key not in {"request_actor", "dry_run"}}
    blockers: list[str] = []
    if set(payload) != _FIELDS:
        blockers.append("rogue_recovery_plan_payload_schema_invalid")
    if not safe_actor or request_actor != safe_actor:
        blockers.append("rogue_recovery_plan_actor_lineage_mismatch")
    if payload.get("dry_run") is not True:
        blockers.append("rogue_recovery_plan_dry_run_true_required")
    if bounded["replacement_source"] not in REPLACEMENT_SOURCES:
        blockers.append("rogue_recovery_plan_replacement_source_invalid")
    for field in (
        "copy_id",
        "provisioning_receipt_id",
        "isolation_verification_receipt_id",
        "integrity_evidence_receipt_id",
        "disposition_receipt_id",
    ):
        if not _identifier(bounded[field]):
            blockers.append(f"rogue_recovery_plan_{field}_invalid")
    for field in (
        "integrity_evidence_fingerprint",
        "disposition_fingerprint",
        "recovery_intent_fingerprint",
    ):
        if not _sha(bounded[field]):
            blockers.append(f"rogue_recovery_plan_{field}_invalid")
    if blockers:
        return _blocked_static(safe_actor, bounded, blockers, dry_run=payload.get("dry_run") is True)

    provision = managed_copy_provision_for_copy(
        bounded["copy_id"], provisioning_receipt_id=bounded["provisioning_receipt_id"]
    )
    isolation = (
        latest_managed_copy_isolation_verification_for_provision(
            bounded["provisioning_receipt_id"],
            provision_fingerprint=_text(provision.get("provision_fingerprint")),
            copy_id=bounded["copy_id"],
        )
        if provision
        else {}
    )
    if (
        not provision
        or not isolation
        or isolation.get("live_state_aligned") is not True
        or isolation.get("receipt_id") != bounded["isolation_verification_receipt_id"]
    ):
        blockers.append("rogue_recovery_plan_live_lineage_required")

    evidence = managed_copy_integrity_evidence_readback(
        copy_id=bounded["copy_id"],
        provisioning_receipt_id=bounded["provisioning_receipt_id"],
        isolation_verification_receipt_id=bounded["isolation_verification_receipt_id"],
    )
    evidence_items = evidence.get("items")
    evidence_matches = (
        [
            item
            for item in evidence_items
            if isinstance(item, dict)
            and item.get("receipt_id") == bounded["integrity_evidence_receipt_id"]
            and item.get("evidence_fingerprint") == bounded["integrity_evidence_fingerprint"]
        ]
        if isinstance(evidence_items, list)
        else []
    )
    if (
        evidence.get("live_drift_matches_latest") is not True
        or evidence.get("latest_receipt_id") != bounded["integrity_evidence_receipt_id"]
        or evidence.get("latest_evidence_fingerprint") != bounded["integrity_evidence_fingerprint"]
        or len(evidence_matches) != 1
    ):
        blockers.append("rogue_recovery_plan_current_integrity_evidence_required")

    dispositions = managed_copy_integrity_triage_dispositions_readback(
        copy_id=bounded["copy_id"],
        provisioning_receipt_id=bounded["provisioning_receipt_id"],
        isolation_verification_receipt_id=bounded["isolation_verification_receipt_id"],
        limit=500,
    )
    disposition_items = dispositions.get("items")
    disposition_matches = (
        [
            item
            for item in disposition_items
            if isinstance(item, dict)
            and item.get("receipt_id") == bounded["disposition_receipt_id"]
            and item.get("disposition_fingerprint") == bounded["disposition_fingerprint"]
            and item.get("integrity_evidence_receipt_id") == bounded["integrity_evidence_receipt_id"]
            and item.get("integrity_evidence_fingerprint") == bounded["integrity_evidence_fingerprint"]
        ]
        if isinstance(disposition_items, list)
        else []
    )
    if (
        dispositions.get("ok") is not True
        or dispositions.get("latest_receipt_id") != bounded["disposition_receipt_id"]
        or dispositions.get("latest_disposition_fingerprint") != bounded["disposition_fingerprint"]
        or dispositions.get("latest_disposition") != "containment_authorization_required"
        or len(disposition_matches) != 1
    ):
        blockers.append("rogue_recovery_plan_containment_disposition_required")

    binding = {
        "contract": CONTRACT,
        "actor": safe_actor,
        **bounded,
        "tenant_key": _text(provision.get("tenant_key")),
        "provision_fingerprint": _text(provision.get("provision_fingerprint")),
        "isolation_verification_fingerprint": _text(isolation.get("verification_fingerprint")),
        "integrity_scan_fingerprint": _text(evidence_matches[0].get("scan_fingerprint"))
        if len(evidence_matches) == 1
        else "",
        "steps": _steps(),
    }
    plan_fingerprint = _fingerprint(binding) if not blockers else ""
    return {
        "ok": not blockers,
        "kind": KIND,
        "contract": CONTRACT,
        "status": "ready_for_operator_review" if not blockers else "blocked",
        "error": "" if not blockers else "rogue_recovery_plan_not_ready",
        "actor": safe_actor,
        "copy_id": _identifier(bounded["copy_id"]),
        "tenant_key": _text(provision.get("tenant_key")),
        "provisioning_receipt_id": _identifier(bounded["provisioning_receipt_id"]),
        "provision_fingerprint": _text(provision.get("provision_fingerprint")),
        "isolation_verification_receipt_id": _identifier(bounded["isolation_verification_receipt_id"]),
        "isolation_verification_fingerprint": _text(isolation.get("verification_fingerprint")),
        "integrity_evidence_receipt_id": _identifier(bounded["integrity_evidence_receipt_id"]),
        "integrity_evidence_fingerprint": bounded["integrity_evidence_fingerprint"]
        if _sha(bounded["integrity_evidence_fingerprint"])
        else "",
        "disposition_receipt_id": _identifier(bounded["disposition_receipt_id"]),
        "disposition_fingerprint": bounded["disposition_fingerprint"]
        if _sha(bounded["disposition_fingerprint"])
        else "",
        "replacement_source": bounded["replacement_source"]
        if bounded["replacement_source"] in REPLACEMENT_SOURCES
        else "",
        "recovery_intent_fingerprint": bounded["recovery_intent_fingerprint"]
        if _sha(bounded["recovery_intent_fingerprint"])
        else "",
        "plan_fingerprint": plan_fingerprint,
        "steps": _steps(),
        "step_count": len(_STEPS),
        "blockers": blockers,
        "operator_approval_required": True,
        "next_operator_boundary": "approve_exact_managed_copy_runtime_halt_action" if not blockers else "",
        "evidence_class": "recovery_preflight",
        "runtime_gate_ready": False,
        "dry_run": payload.get("dry_run") is True,
        **_NO_EFFECT,
    }


def _steps() -> list[dict[str, str]]:
    return [{"id": step_id, "status": status} for step_id, status in _STEPS]


def _blocked_static(
    actor: str,
    bounded: dict[str, str],
    blockers: list[str],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    return {
        "ok": False,
        "kind": KIND,
        "contract": CONTRACT,
        "status": "blocked",
        "error": "rogue_recovery_plan_not_ready",
        "actor": actor,
        "copy_id": _identifier(bounded["copy_id"]),
        "tenant_key": "",
        "provisioning_receipt_id": _identifier(bounded["provisioning_receipt_id"]),
        "provision_fingerprint": "",
        "isolation_verification_receipt_id": _identifier(bounded["isolation_verification_receipt_id"]),
        "isolation_verification_fingerprint": "",
        "integrity_evidence_receipt_id": _identifier(bounded["integrity_evidence_receipt_id"]),
        "integrity_evidence_fingerprint": bounded["integrity_evidence_fingerprint"]
        if _sha(bounded["integrity_evidence_fingerprint"])
        else "",
        "disposition_receipt_id": _identifier(bounded["disposition_receipt_id"]),
        "disposition_fingerprint": bounded["disposition_fingerprint"]
        if _sha(bounded["disposition_fingerprint"])
        else "",
        "replacement_source": bounded["replacement_source"]
        if bounded["replacement_source"] in REPLACEMENT_SOURCES
        else "",
        "recovery_intent_fingerprint": bounded["recovery_intent_fingerprint"]
        if _sha(bounded["recovery_intent_fingerprint"])
        else "",
        "plan_fingerprint": "",
        "steps": _steps(),
        "step_count": len(_STEPS),
        "blockers": blockers,
        "operator_approval_required": False,
        "next_operator_boundary": "",
        "evidence_class": "recovery_preflight",
        "runtime_gate_ready": False,
        "dry_run": dry_run,
        **_NO_EFFECT,
    }


def _fingerprint(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _sha(value: Any) -> bool:
    text = _text(value)
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _identifier(value: Any) -> str:
    text = _text(value)
    if not text or len(text) > 240 or not text[0].isalnum():
        return ""
    if not all(char.isascii() and (char.isalnum() or char in "._:-") for char in text):
        return ""
    return text if _redacted(text) == text else ""


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _redacted(value: Any) -> str:
    return redact_secret_text(value).strip() if isinstance(value, str) else ""
