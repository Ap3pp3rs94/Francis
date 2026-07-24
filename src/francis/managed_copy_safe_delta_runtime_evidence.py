from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir

SAFE_DELTA_RUNTIME_SOURCE_CONTRACT = "stage18_managed_copy_safe_delta_runtime_source_v3"
SAFE_DELTA_RUNTIME_SOURCE_KIND = "francis.stage18.managed_copies.safe_delta_runtime_source_receipt"
SAFE_DELTA_RUNTIME_SOURCE_MISSING = "stage18_safe_delta_runtime_source_receipt_missing"
SAFE_DELTA_RUNTIME_PROOF_KIND = "safe_delta_runtime_receipt"
_IDENTIFIER_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-")
_FIELDS = frozenset(
    {
        "kind",
        "contract",
        "receipt_id",
        "status",
        "evidence_class",
        "actor",
        "tenant_key",
        "copy_id",
        "provisioning_receipt_id",
        "provisioning_receipt_fingerprint",
        "isolation_verification_receipt_id",
        "isolation_verification_receipt_fingerprint",
        "review_receipt_id",
        "review_receipt_fingerprint",
        "review_fingerprint",
        "safe_delta_decision_receipt_id",
        "safe_delta_decision_receipt_fingerprint",
        "export_authorization_decision_receipt_id",
        "export_authorization_decision_receipt_fingerprint",
        "artifact_plan_fingerprint",
        "export_artifact_receipt_id",
        "export_artifact_receipt_fingerprint",
        "artifact_content_fingerprint",
        "runtime_invocation_receipt_id",
        "runtime_invocation_receipt_fingerprint",
        "runtime_invocation_fingerprint",
        "runtime_invocation_result_fingerprint",
        "pilot_lease_id",
        "package_id",
        "package_fingerprint",
        "pilot_run_id",
        "operator_decision_fingerprint",
        "invocation_lease_authority_fingerprint",
        "source_lease_authority_fingerprint",
        "authority_route",
        "authority_method",
        "authority_action",
        "signal_class",
        "trace_id",
        "fixture_only",
        "runtime_gate_ready",
        "recorded_at_unix_ms",
        "receipt_fingerprint",
    }
)
_IDENTIFIER_FIELDS = (
    "receipt_id",
    "actor",
    "copy_id",
    "provisioning_receipt_id",
    "isolation_verification_receipt_id",
    "review_receipt_id",
    "safe_delta_decision_receipt_id",
    "export_authorization_decision_receipt_id",
    "export_artifact_receipt_id",
    "runtime_invocation_receipt_id",
    "pilot_lease_id",
    "package_id",
    "pilot_run_id",
    "authority_action",
    "signal_class",
    "trace_id",
)
_HASH_FIELDS = (
    "tenant_key",
    "provisioning_receipt_fingerprint",
    "isolation_verification_receipt_fingerprint",
    "review_receipt_fingerprint",
    "review_fingerprint",
    "safe_delta_decision_receipt_fingerprint",
    "export_authorization_decision_receipt_fingerprint",
    "artifact_plan_fingerprint",
    "export_artifact_receipt_fingerprint",
    "artifact_content_fingerprint",
    "runtime_invocation_receipt_fingerprint",
    "runtime_invocation_fingerprint",
    "runtime_invocation_result_fingerprint",
    "package_fingerprint",
    "operator_decision_fingerprint",
    "invocation_lease_authority_fingerprint",
    "source_lease_authority_fingerprint",
    "receipt_fingerprint",
)


def safe_delta_runtime_source_directory() -> Path:
    return data_dir() / "logs" / "managed_copies" / "safe_delta_runtime"


def verify_safe_delta_runtime_source(source_receipt_id: str, source_receipt_fingerprint: str) -> dict[str, Any]:
    """Validate canonical safe-delta lineage without executing or exporting."""
    source = _verify_safe_delta_runtime_source(
        source_receipt_id,
        source_receipt_fingerprint,
        include_runtime_evidence=False,
    )
    if source.get("blocker") != "stage18_safe_delta_runtime_source_authority_lineage_invalid":
        return source
    return verify_safe_delta_runtime_source_for_final_evidence(
        source_receipt_id,
        source_receipt_fingerprint,
    )


def verify_safe_delta_runtime_source_for_final_evidence(
    source_receipt_id: str,
    source_receipt_fingerprint: str,
) -> dict[str, Any]:
    """Validate canonical lineage after the final evidence binding is consumed."""
    return _verify_safe_delta_runtime_source(
        source_receipt_id,
        source_receipt_fingerprint,
        include_runtime_evidence=True,
        required_consumed_count=3,
    )


def verify_safe_delta_runtime_source_for_final_plan(
    source_receipt_id: str,
    source_receipt_fingerprint: str,
) -> dict[str, Any]:
    """Validate source lineage and the unconsumed final binding for planning."""
    return _verify_safe_delta_runtime_source(
        source_receipt_id,
        source_receipt_fingerprint,
        include_runtime_evidence=True,
        required_consumed_count=2,
    )


def safe_delta_runtime_source_authority_context(
    source_receipt_id: str,
    source_receipt_fingerprint: str,
    *,
    include_runtime_evidence: bool = False,
    required_consumed_count: int | None = None,
) -> dict[str, Any]:
    """Return redacted authority only after independent source validation."""
    source, blocker = _load_valid_source(
        source_receipt_id,
        source_receipt_fingerprint,
        include_runtime_evidence=include_runtime_evidence,
        required_consumed_count=required_consumed_count,
    )
    if blocker:
        return {"valid": False, "blocker": blocker}
    authority = _authority_snapshot(source, include_runtime_evidence=include_runtime_evidence)
    return {
        "valid": True,
        "blocker": "",
        "actor_id": source["actor"],
        "pilot_lease_id": source["pilot_lease_id"],
        "package_id": source["package_id"],
        "package_fingerprint": source["package_fingerprint"],
        "pilot_run_id": source["pilot_run_id"],
        "operator_decision_fingerprint": source["operator_decision_fingerprint"],
        "lease_authority_fingerprint": authority["lease_authority_fingerprint"],
    }


def _verify_safe_delta_runtime_source(
    source_receipt_id: str,
    source_receipt_fingerprint: str,
    *,
    include_runtime_evidence: bool,
    required_consumed_count: int | None = None,
) -> dict[str, Any]:
    source, blocker = _load_valid_source(
        source_receipt_id,
        source_receipt_fingerprint,
        include_runtime_evidence=include_runtime_evidence,
        required_consumed_count=required_consumed_count,
    )
    if blocker:
        return _blocked(blocker)
    authority = _authority_snapshot(source, include_runtime_evidence=include_runtime_evidence)
    if not include_runtime_evidence:
        return {
            "valid": True,
            "blocker": "",
            "evidence_class": "canonical_runtime",
            "source_lineage_hash": _lineage_hash(source),
            "current_state_hash": source["export_artifact_receipt_fingerprint"],
        }
    final_authority_fingerprint = _final_sequence_fingerprint(authority)
    return {
        "valid": True,
        "blocker": "",
        "evidence_class": "canonical_runtime",
        "source_lineage_hash": _lineage_hash(source, final_authority_fingerprint),
        "current_state_hash": _fingerprint(
            {
                "export_artifact_receipt_fingerprint": source["export_artifact_receipt_fingerprint"],
                "lease_authority_fingerprint": final_authority_fingerprint,
            }
        ),
    }


def _load_valid_source(
    source_receipt_id: str,
    source_receipt_fingerprint: str,
    *,
    include_runtime_evidence: bool,
    required_consumed_count: int | None,
) -> tuple[dict[str, Any], str]:
    if not _identifier(source_receipt_id) or not _is_hash(source_receipt_fingerprint):
        return {}, "stage18_safe_delta_runtime_source_binding_invalid"
    source = _read_json(safe_delta_runtime_source_directory() / f"{source_receipt_id}.json")
    if not source:
        return {}, SAFE_DELTA_RUNTIME_SOURCE_MISSING
    if not _valid_source(source):
        return {}, "stage18_safe_delta_runtime_source_receipt_invalid"
    if source["receipt_fingerprint"] != source_receipt_fingerprint:
        return {}, "stage18_safe_delta_runtime_source_receipt_hash_mismatch"
    blocker = (
        _owned_lineage_blocker(source)
        if not include_runtime_evidence and required_consumed_count is None
        else _owned_lineage_blocker(
            source,
            include_runtime_evidence=include_runtime_evidence,
            required_consumed_count=required_consumed_count,
        )
    )
    if blocker:
        return {}, blocker
    return source, ""


def _owned_lineage_blocker(
    source: dict[str, Any],
    *,
    include_runtime_evidence: bool = False,
    required_consumed_count: int | None = None,
) -> str:
    from francis.managed_copy_isolation import latest_managed_copy_isolation_verification_for_provision
    from francis.managed_copy_provisioning import managed_copy_provision_for_copy
    from francis.managed_copy_safe_delta import managed_copy_safe_delta_review_receipts_readback
    from francis.managed_copy_safe_delta_approval import managed_copy_safe_delta_decisions_readback
    from francis.managed_copy_safe_delta_export_authorization_decision import (
        managed_copy_safe_delta_export_authorization_decisions_readback,
    )
    from francis.managed_copy_safe_delta_export_artifact import (
        managed_copy_safe_delta_export_artifacts_readback,
    )
    from francis.managed_copy_safe_delta_runtime_invocation import (
        SOURCE_ACTION,
        SOURCE_ROUTE,
        lease_bindings,
        safe_delta_runtime_invocations_readback,
    )
    from francis.managed_copy_pilot_runtime import pilot_runtime_lease_authority_snapshot

    provision = managed_copy_provision_for_copy(
        source["copy_id"], provisioning_receipt_id=source["provisioning_receipt_id"]
    )
    if (
        not provision
        or provision.get("tenant_key") != source["tenant_key"]
        or provision.get("provision_fingerprint") != source["provisioning_receipt_fingerprint"]
    ):
        return "stage18_safe_delta_runtime_provisioning_lineage_invalid"
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
        return "stage18_safe_delta_runtime_isolation_lineage_invalid"

    review_readback = managed_copy_safe_delta_review_receipts_readback(
        copy_id=source["copy_id"],
        provisioning_receipt_id=source["provisioning_receipt_id"],
        isolation_verification_receipt_id=source["isolation_verification_receipt_id"],
        review_fingerprint=source["review_fingerprint"],
        limit=20,
    )
    review = review_readback.get("latest_valid_receipt")
    review = review if isinstance(review, dict) else {}
    if (
        review_readback.get("receipt_set_valid") is not True
        or review.get("live_source_boundary_aligned") is not True
        or review.get("receipt_id") != source["review_receipt_id"]
        or review.get("receipt_fingerprint") != source["review_receipt_fingerprint"]
        or review.get("signal_class") != source["signal_class"]
    ):
        return "stage18_safe_delta_runtime_review_lineage_invalid"

    decisions = managed_copy_safe_delta_decisions_readback(
        copy_id=source["copy_id"],
        provisioning_receipt_id=source["provisioning_receipt_id"],
        isolation_verification_receipt_id=source["isolation_verification_receipt_id"],
        review_fingerprint=source["review_fingerprint"],
        limit=20,
    )
    decision = decisions.get("latest_valid_receipt")
    decision = decision if isinstance(decision, dict) else {}
    if (
        decisions.get("safe_delta_approved") is not True
        or decision.get("receipt_id") != source["safe_delta_decision_receipt_id"]
        or decision.get("receipt_fingerprint") != source["safe_delta_decision_receipt_fingerprint"]
    ):
        return "stage18_safe_delta_runtime_decision_lineage_invalid"

    export_decisions = managed_copy_safe_delta_export_authorization_decisions_readback(
        copy_id=source["copy_id"],
        provisioning_receipt_id=source["provisioning_receipt_id"],
        isolation_verification_receipt_id=source["isolation_verification_receipt_id"],
        limit=500,
    )
    matches = [
        item
        for item in export_decisions.get("items", [])
        if isinstance(item, dict)
        and item.get("receipt_id") == source["export_authorization_decision_receipt_id"]
        and item.get("receipt_fingerprint") == source["export_authorization_decision_receipt_fingerprint"]
        and item.get("decision") == "approved"
        and item.get("review_fingerprint") == source["review_fingerprint"]
    ]
    if len(matches) != 1:
        return "stage18_safe_delta_runtime_export_authorization_lineage_invalid"
    artifacts = managed_copy_safe_delta_export_artifacts_readback(
        copy_id=source["copy_id"],
        provisioning_receipt_id=source["provisioning_receipt_id"],
        isolation_verification_receipt_id=source["isolation_verification_receipt_id"],
        artifact_plan_fingerprint=source["artifact_plan_fingerprint"],
        limit=20,
    )
    receipt = artifacts.get("latest_valid_receipt")
    receipt = receipt if isinstance(receipt, dict) else {}
    if (
        artifacts.get("valid_count") != 1
        or receipt.get("receipt_id") != source["export_artifact_receipt_id"]
        or receipt.get("receipt_fingerprint") != source["export_artifact_receipt_fingerprint"]
        or receipt.get("artifact_content_fingerprint") != source["artifact_content_fingerprint"]
        or receipt.get("artifact_plan_fingerprint") != source["artifact_plan_fingerprint"]
        or receipt.get("tenant_key") != source["tenant_key"]
        or receipt.get("copy_id") != source["copy_id"]
        or receipt.get("provisioning_receipt_id") != source["provisioning_receipt_id"]
        or receipt.get("isolation_verification_receipt_id") != source["isolation_verification_receipt_id"]
        or receipt.get("review_fingerprint") != source["review_fingerprint"]
        or receipt.get("authorization_decision_receipt_id") != source["export_authorization_decision_receipt_id"]
        or receipt.get("authorization_decision_receipt_fingerprint")
        != source["export_authorization_decision_receipt_fingerprint"]
    ):
        return "stage18_safe_delta_runtime_export_artifact_lineage_invalid"
    invocations = safe_delta_runtime_invocations_readback(
        copy_id=source["copy_id"],
        provisioning_receipt_id=source["provisioning_receipt_id"],
        isolation_verification_receipt_id=source["isolation_verification_receipt_id"],
        invocation_fingerprint=source["runtime_invocation_fingerprint"],
        limit=20,
    )
    invocation = invocations.get("latest_valid_receipt")
    invocation = invocation if isinstance(invocation, dict) else {}
    result = invocation.get("invocation_result")
    result = result if isinstance(result, dict) else {}
    if (
        invocations.get("valid_count") != 1
        or invocation.get("receipt_id") != source["runtime_invocation_receipt_id"]
        or invocation.get("receipt_fingerprint") != source["runtime_invocation_receipt_fingerprint"]
        or invocation.get("invocation_fingerprint") != source["runtime_invocation_fingerprint"]
        or invocation.get("invocation_result_fingerprint") != source["runtime_invocation_result_fingerprint"]
        or invocation.get("export_artifact_receipt_id") != source["export_artifact_receipt_id"]
        or invocation.get("export_artifact_receipt_fingerprint") != source["export_artifact_receipt_fingerprint"]
        or invocation.get("artifact_content_fingerprint") != source["artifact_content_fingerprint"]
        or invocation.get("pilot_lease_id") != source["pilot_lease_id"]
        or invocation.get("package_id") != source["package_id"]
        or invocation.get("package_fingerprint") != source["package_fingerprint"]
        or invocation.get("pilot_run_id") != source["pilot_run_id"]
        or invocation.get("operator_decision_fingerprint") != source["operator_decision_fingerprint"]
        or invocation.get("lease_authority_fingerprint") != source["invocation_lease_authority_fingerprint"]
        or invocation.get("trace_id") != source["trace_id"]
        or result.get("classification") != "eligible_for_core_review"
        or result.get("eligible_for_core_review") is not True
    ):
        return "stage18_safe_delta_runtime_invocation_lineage_invalid"
    authority = pilot_runtime_lease_authority_snapshot(
        source["pilot_lease_id"],
        actor=source["actor"],
        expected_bindings=lease_bindings(include_runtime_evidence=include_runtime_evidence),
    )
    expected_count = required_consumed_count or (3 if include_runtime_evidence else 2)
    prefixes = authority.get("consumed_prefix_fingerprints")
    if (
        authority.get("valid") is not True
        or authority.get("package_id") != source["package_id"]
        or authority.get("package_fingerprint") != source["package_fingerprint"]
        or authority.get("pilot_run_id") != source["pilot_run_id"]
        or authority.get("operator_decision_fingerprint") != source["operator_decision_fingerprint"]
        or authority.get("operation_consumed_binding_count") != expected_count
        or not isinstance(prefixes, list)
        or len(prefixes) != expected_count
        or prefixes[:2]
        != [
            source["invocation_lease_authority_fingerprint"],
            source["source_lease_authority_fingerprint"],
        ]
        or source.get("authority_route") != SOURCE_ROUTE
        or source.get("authority_method") != "POST"
        or source.get("authority_action") != SOURCE_ACTION
    ):
        return "stage18_safe_delta_runtime_source_authority_lineage_invalid"
    return ""


def _authority_snapshot(source: dict[str, Any], *, include_runtime_evidence: bool) -> dict[str, Any]:
    from francis.managed_copy_pilot_runtime import pilot_runtime_lease_authority_snapshot
    from francis.managed_copy_safe_delta_runtime_invocation import lease_bindings

    return pilot_runtime_lease_authority_snapshot(
        source["pilot_lease_id"],
        actor=source["actor"],
        expected_bindings=lease_bindings(include_runtime_evidence=include_runtime_evidence),
    )


def _valid_source(source: dict[str, Any]) -> bool:
    return bool(
        set(source) == _FIELDS
        and source.get("kind") == SAFE_DELTA_RUNTIME_SOURCE_KIND
        and source.get("contract") == SAFE_DELTA_RUNTIME_SOURCE_CONTRACT
        and source.get("status") == "exported"
        and source.get("evidence_class") == "canonical_runtime"
        and source.get("fixture_only") is False
        and source.get("runtime_gate_ready") is True
        and type(source.get("recorded_at_unix_ms")) is int
        and all(_identifier(source.get(field)) for field in _IDENTIFIER_FIELDS)
        and all(_is_hash(source.get(field)) for field in _HASH_FIELDS)
        and source["receipt_fingerprint"] == _fingerprint_without(source, "receipt_fingerprint")
    )


def _lineage_hash(source: dict[str, Any], final_authority_fingerprint: str = "") -> str:
    lineage = {
        key: source[key]
        for key in (
            "tenant_key",
            "copy_id",
            "provisioning_receipt_id",
            "provisioning_receipt_fingerprint",
            "isolation_verification_receipt_id",
            "isolation_verification_receipt_fingerprint",
            "review_receipt_id",
            "review_receipt_fingerprint",
            "safe_delta_decision_receipt_id",
            "safe_delta_decision_receipt_fingerprint",
            "export_authorization_decision_receipt_id",
            "export_authorization_decision_receipt_fingerprint",
            "artifact_plan_fingerprint",
            "export_artifact_receipt_id",
            "export_artifact_receipt_fingerprint",
            "artifact_content_fingerprint",
            "runtime_invocation_receipt_id",
            "runtime_invocation_receipt_fingerprint",
            "runtime_invocation_fingerprint",
            "runtime_invocation_result_fingerprint",
            "pilot_lease_id",
            "package_id",
            "package_fingerprint",
            "pilot_run_id",
            "operator_decision_fingerprint",
            "invocation_lease_authority_fingerprint",
            "source_lease_authority_fingerprint",
        )
    }
    if final_authority_fingerprint:
        return _fingerprint(
            {
                "source": lineage,
                "lease_authority_fingerprint": final_authority_fingerprint,
            }
        )
    return _fingerprint(lineage)


def _final_sequence_fingerprint(authority: dict[str, Any]) -> str:
    sequence = authority.get("sequence_prefix_fingerprints")
    return sequence[-1] if isinstance(sequence, list) and sequence and _is_hash(sequence[-1]) else ""


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
