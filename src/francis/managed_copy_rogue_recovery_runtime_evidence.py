from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir

ROGUE_RECOVERY_RUNTIME_SOURCE_CONTRACT = "stage18_managed_copy_rogue_recovery_runtime_source_v1"
ROGUE_RECOVERY_RUNTIME_SOURCE_KIND = "francis.stage18.managed_copies.rogue_recovery_runtime_source_receipt"
ROGUE_RECOVERY_RUNTIME_SOURCE_MISSING = "stage18_rogue_recovery_runtime_source_receipt_missing"
ROGUE_RECOVERY_RUNTIME_PROOF_KIND = "rogue_recovery_runtime_receipt"
_IDENTIFIER_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-")
_IDENTIFIER_FIELDS = (
    "receipt_id",
    "actor",
    "copy_id",
    "provisioning_receipt_id",
    "isolation_verification_receipt_id",
    "integrity_evidence_receipt_id",
    "rogue_detection_assessment_receipt_id",
    "disposition_receipt_id",
    "runtime_halt_receipt_id",
    "quarantine_receipt_id",
    "evidence_preservation_receipt_id",
    "support_review_receipt_id",
    "replacement_receipt_id",
    "replacement_verification_receipt_id",
    "continuity_restore_receipt_id",
    "trace_id",
)
_HASH_FIELDS = (
    "tenant_key",
    "provisioning_receipt_fingerprint",
    "isolation_verification_receipt_fingerprint",
    "integrity_evidence_fingerprint",
    "rogue_detection_assessment_receipt_fingerprint",
    "disposition_fingerprint",
    "recovery_intent_fingerprint",
    "recovery_plan_fingerprint",
    "runtime_halt_receipt_fingerprint",
    "quarantine_receipt_fingerprint",
    "evidence_preservation_receipt_fingerprint",
    "support_review_receipt_fingerprint",
    "replacement_receipt_fingerprint",
    "replacement_verification_receipt_fingerprint",
    "continuity_restore_receipt_fingerprint",
    "receipt_fingerprint",
)
_FIELDS = frozenset(
    {
        "kind",
        "contract",
        "status",
        "evidence_class",
        "replacement_source",
        "fixture_only",
        "runtime_gate_ready",
        "recorded_at_unix_ms",
        *_IDENTIFIER_FIELDS,
        *_HASH_FIELDS,
    }
)


def rogue_recovery_runtime_source_directory() -> Path:
    return data_dir() / "logs" / "managed_copies" / "rogue_recovery_runtime"


def verify_rogue_recovery_runtime_source(
    source_receipt_id: str,
    source_receipt_fingerprint: str,
) -> dict[str, Any]:
    """Validate current owned recovery lineage without executing recovery actions."""
    if not _identifier(source_receipt_id) or not _is_hash(source_receipt_fingerprint):
        return _blocked("stage18_rogue_recovery_runtime_source_binding_invalid")
    source = _read_json(rogue_recovery_runtime_source_directory() / f"{source_receipt_id}.json")
    if not source:
        return _blocked(ROGUE_RECOVERY_RUNTIME_SOURCE_MISSING)
    if not _valid_source(source):
        return _blocked("stage18_rogue_recovery_runtime_source_receipt_invalid")
    if source["receipt_fingerprint"] != source_receipt_fingerprint:
        return _blocked("stage18_rogue_recovery_runtime_source_receipt_hash_mismatch")
    blocker = _owned_lineage_blocker(source)
    if blocker:
        return _blocked(blocker)
    return {
        "valid": True,
        "blocker": "",
        "evidence_class": "canonical_runtime",
        "source_lineage_hash": _lineage_hash(source),
        "current_state_hash": source["continuity_restore_receipt_fingerprint"],
    }


def _owned_lineage_blocker(source: dict[str, Any]) -> str:
    from francis.managed_copy_integrity_evidence import managed_copy_integrity_evidence_readback
    from francis.managed_copy_integrity_triage_disposition import (
        managed_copy_integrity_triage_dispositions_readback,
    )
    from francis.managed_copy_isolation import latest_managed_copy_isolation_verification_for_provision
    from francis.managed_copy_provisioning import managed_copy_provision_for_copy
    from francis.managed_copy_rogue_recovery_plan import managed_copy_rogue_recovery_plan
    from francis.managed_copy_rogue_detection_assessment import managed_copy_rogue_detection_assessments_readback

    provision = managed_copy_provision_for_copy(
        source["copy_id"], provisioning_receipt_id=source["provisioning_receipt_id"]
    )
    if (
        not provision
        or provision.get("tenant_key") != source["tenant_key"]
        or provision.get("provision_fingerprint") != source["provisioning_receipt_fingerprint"]
    ):
        return "stage18_rogue_recovery_runtime_provisioning_lineage_invalid"
    isolation = latest_managed_copy_isolation_verification_for_provision(
        source["provisioning_receipt_id"],
        provision_fingerprint=source["provisioning_receipt_fingerprint"],
        copy_id=source["copy_id"],
    )
    if (
        not isolation
        or isolation.get("receipt_id") != source["isolation_verification_receipt_id"]
        or isolation.get("verification_fingerprint") != source["isolation_verification_receipt_fingerprint"]
        or isolation.get("live_state_aligned") is not True
    ):
        return "stage18_rogue_recovery_runtime_isolation_lineage_invalid"

    evidence = managed_copy_integrity_evidence_readback(
        copy_id=source["copy_id"],
        provisioning_receipt_id=source["provisioning_receipt_id"],
        isolation_verification_receipt_id=source["isolation_verification_receipt_id"],
    )
    evidence_matches = [
        item
        for item in evidence.get("items", [])
        if isinstance(item, dict)
        and item.get("receipt_id") == source["integrity_evidence_receipt_id"]
        and item.get("evidence_fingerprint") == source["integrity_evidence_fingerprint"]
    ]
    if (
        evidence.get("live_drift_matches_latest") is not True
        or evidence.get("latest_receipt_id") != source["integrity_evidence_receipt_id"]
        or evidence.get("latest_evidence_fingerprint") != source["integrity_evidence_fingerprint"]
        or len(evidence_matches) != 1
    ):
        return "stage18_rogue_recovery_runtime_integrity_lineage_invalid"

    assessments = managed_copy_rogue_detection_assessments_readback(
        copy_id=source["copy_id"],
        provisioning_receipt_id=source["provisioning_receipt_id"],
        isolation_verification_receipt_id=source["isolation_verification_receipt_id"],
        limit=500,
    )
    if not _assessment_lineage_current(source, assessments):
        return "stage18_rogue_recovery_runtime_assessment_lineage_invalid"

    dispositions = managed_copy_integrity_triage_dispositions_readback(
        copy_id=source["copy_id"],
        provisioning_receipt_id=source["provisioning_receipt_id"],
        isolation_verification_receipt_id=source["isolation_verification_receipt_id"],
        limit=500,
    )
    disposition_matches = [
        item
        for item in dispositions.get("items", [])
        if isinstance(item, dict)
        and item.get("receipt_id") == source["disposition_receipt_id"]
        and item.get("disposition_fingerprint") == source["disposition_fingerprint"]
        and item.get("integrity_evidence_receipt_id") == source["integrity_evidence_receipt_id"]
        and item.get("integrity_evidence_fingerprint") == source["integrity_evidence_fingerprint"]
    ]
    if (
        dispositions.get("ok") is not True
        or dispositions.get("latest_receipt_id") != source["disposition_receipt_id"]
        or dispositions.get("latest_disposition_fingerprint") != source["disposition_fingerprint"]
        or dispositions.get("latest_disposition") != "containment_authorization_required"
        or len(disposition_matches) != 1
    ):
        return "stage18_rogue_recovery_runtime_disposition_lineage_invalid"

    plan = managed_copy_rogue_recovery_plan(
        {
            "request_actor": source["actor"],
            "copy_id": source["copy_id"],
            "provisioning_receipt_id": source["provisioning_receipt_id"],
            "isolation_verification_receipt_id": source["isolation_verification_receipt_id"],
            "integrity_evidence_receipt_id": source["integrity_evidence_receipt_id"],
            "integrity_evidence_fingerprint": source["integrity_evidence_fingerprint"],
            "disposition_receipt_id": source["disposition_receipt_id"],
            "disposition_fingerprint": source["disposition_fingerprint"],
            "replacement_source": source["replacement_source"],
            "recovery_intent_fingerprint": source["recovery_intent_fingerprint"],
            "dry_run": True,
        },
        actor=source["actor"],
    )
    if plan.get("ok") is not True or plan.get("plan_fingerprint") != source["recovery_plan_fingerprint"]:
        return "stage18_rogue_recovery_runtime_plan_lineage_invalid"
    return "stage18_rogue_recovery_runtime_halt_receipt_not_implemented"


def _assessment_lineage_current(source: dict[str, Any], assessments: dict[str, Any]) -> bool:
    assessment_items = assessments.get("items", [])
    assessment_items = assessment_items if isinstance(assessment_items, list) else []
    matches = [
        item
        for item in assessment_items
        if isinstance(item, dict)
        and item.get("receipt_id") == source["rogue_detection_assessment_receipt_id"]
        and item.get("receipt_fingerprint") == source["rogue_detection_assessment_receipt_fingerprint"]
        and source["integrity_evidence_fingerprint"] in item.get("evidence_reference_hashes", [])
    ]
    return bool(
        assessments.get("rogue_signal_assessed") is True
        and len(matches) == 1
        and assessment_items
        and assessment_items[-1] is matches[0]
    )


def _valid_source(source: dict[str, Any]) -> bool:
    from francis.managed_copy_rogue_recovery_plan import REPLACEMENT_SOURCES

    return bool(
        set(source) == _FIELDS
        and source.get("kind") == ROGUE_RECOVERY_RUNTIME_SOURCE_KIND
        and source.get("contract") == ROGUE_RECOVERY_RUNTIME_SOURCE_CONTRACT
        and source.get("status") == "recovered"
        and source.get("evidence_class") == "canonical_runtime"
        and source.get("replacement_source") in REPLACEMENT_SOURCES
        and source.get("fixture_only") is False
        and source.get("runtime_gate_ready") is True
        and type(source.get("recorded_at_unix_ms")) is int
        and all(_identifier(source.get(field)) for field in _IDENTIFIER_FIELDS)
        and all(_is_hash(source.get(field)) for field in _HASH_FIELDS)
        and source["receipt_fingerprint"] == _fingerprint_without(source, "receipt_fingerprint")
    )


def _lineage_hash(source: dict[str, Any]) -> str:
    return _fingerprint(
        {
            key: source[key]
            for key in (
                "tenant_key",
                "copy_id",
                "provisioning_receipt_id",
                "provisioning_receipt_fingerprint",
                "isolation_verification_receipt_id",
                "isolation_verification_receipt_fingerprint",
                "integrity_evidence_receipt_id",
                "integrity_evidence_fingerprint",
                "rogue_detection_assessment_receipt_id",
                "rogue_detection_assessment_receipt_fingerprint",
                "disposition_receipt_id",
                "disposition_fingerprint",
                "recovery_plan_fingerprint",
                "runtime_halt_receipt_id",
                "runtime_halt_receipt_fingerprint",
                "quarantine_receipt_id",
                "quarantine_receipt_fingerprint",
                "evidence_preservation_receipt_id",
                "evidence_preservation_receipt_fingerprint",
                "support_review_receipt_id",
                "support_review_receipt_fingerprint",
                "replacement_receipt_id",
                "replacement_receipt_fingerprint",
                "replacement_verification_receipt_id",
                "replacement_verification_receipt_fingerprint",
                "continuity_restore_receipt_id",
                "continuity_restore_receipt_fingerprint",
            )
        }
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _fingerprint_without(value: dict[str, Any], field: str) -> str:
    return _fingerprint({key: item for key, item in value.items() if key != field})


def _fingerprint(value: dict[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _identifier(value: Any) -> str:
    if type(value) is not str:
        return ""
    text = value.strip()
    if not text or len(text) > 240 or any(char not in _IDENTIFIER_CHARS for char in text):
        return ""
    return text if redact_secret_text(text) == text else ""


def _is_hash(value: Any) -> bool:
    return type(value) is str and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _blocked(blocker: str) -> dict[str, Any]:
    return {
        "valid": False,
        "blocker": blocker,
        "evidence_class": "",
        "source_lineage_hash": "",
        "current_state_hash": "",
    }
