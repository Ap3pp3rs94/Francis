from __future__ import annotations

import hashlib
import json
from typing import Any

from francis.governance.redaction import redact_secret_text
from francis.managed_copy_safe_delta import managed_copy_safe_delta_review_receipts_readback
from francis.managed_copy_safe_delta_approval import managed_copy_safe_delta_decisions_readback

MANAGED_COPY_SAFE_DELTA_EXPORT_PREFLIGHT_CONTRACT = "stage18_managed_copy_safe_delta_export_preflight_v1"
MANAGED_COPY_SAFE_DELTA_EXPORT_PREFLIGHT_KIND = "francis.stage18.managed_copies.safe_delta_export_preflight"

_REQUEST_FIELDS = {
    "request_actor",
    "api_actor",
    "actor",
    "copy_id",
    "provisioning_receipt_id",
    "isolation_verification_receipt_id",
    "review_fingerprint",
    "decision_receipt_id",
    "dry_run",
}
_NO_EFFECTS = {
    "writes_file": False,
    "writes_receipt": False,
    "writes_receipts": False,
    "writes_artifact": False,
    "writes_manifest": False,
    "exports_delta": False,
    "imports_delta": False,
    "writes_learning": False,
    "writes_memory": False,
    "writes_registry": False,
    "writes_tenant_state": False,
    "uses_network": False,
    "executes_action": False,
    "grants_export_authority": False,
    "grants_execution_authority": False,
    "grants_mutation_authority": False,
}


def managed_copy_safe_delta_export_preflight(payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    safe_actor = _redacted_text(actor)[:240]
    unknown_fields = sorted(set(payload) - _REQUEST_FIELDS)
    copy_id = _text(payload.get("copy_id"))
    provision_id = _text(payload.get("provisioning_receipt_id"))
    isolation_id = _text(payload.get("isolation_verification_receipt_id"))
    review_fingerprint = _text(payload.get("review_fingerprint"))
    decision_receipt_id = _text(payload.get("decision_receipt_id"))
    dry_run = payload.get("dry_run")
    blockers: list[str] = []

    actor_fields = [field for field in ("request_actor", "api_actor", "actor") if field in payload]
    payload_actor = _redacted_text(payload.get(actor_fields[0]))[:240] if len(actor_fields) == 1 else ""
    if not safe_actor or not payload_actor or payload_actor != safe_actor:
        return _actor_lineage_blocked(
            safe_actor=safe_actor,
            copy_id=copy_id,
            provision_id=provision_id,
            isolation_id=isolation_id,
            review_fingerprint=review_fingerprint,
            decision_receipt_id=decision_receipt_id,
            dry_run=dry_run,
            unknown_fields=unknown_fields,
            actor_field_count=len(actor_fields),
        )
    if unknown_fields:
        blockers.append("safe_delta_export_preflight_unknown_fields")
    if len(actor_fields) != 1 or not safe_actor:
        blockers.append("safe_delta_export_preflight_actor_invalid")
    if dry_run is not True:
        blockers.append("safe_delta_export_preflight_dry_run_true_required")
    if not copy_id:
        blockers.append("safe_delta_export_preflight_copy_id_required")
    if not provision_id:
        blockers.append("safe_delta_export_preflight_provisioning_receipt_id_required")
    if not isolation_id:
        blockers.append("safe_delta_export_preflight_isolation_receipt_id_required")
    if not _is_sha256(review_fingerprint):
        blockers.append("safe_delta_export_preflight_review_fingerprint_invalid")
    if not decision_receipt_id.startswith("managed_copy_safe_delta_decision_"):
        blockers.append("safe_delta_export_preflight_decision_receipt_id_invalid")

    review_readback = managed_copy_safe_delta_review_receipts_readback(
        copy_id=copy_id,
        provisioning_receipt_id=provision_id,
        isolation_verification_receipt_id=isolation_id,
        review_fingerprint=review_fingerprint,
        limit=20,
    )
    review = review_readback.get("latest_valid_receipt")
    review = review if isinstance(review, dict) else {}
    if (
        not review
        or review_readback.get("receipt_set_valid") is not True
        or review.get("live_source_boundary_aligned") is not True
        or _text(review.get("review_fingerprint")) != review_fingerprint
    ):
        blockers.append("safe_delta_export_preflight_review_not_live_valid")

    decision_readback = managed_copy_safe_delta_decisions_readback(
        copy_id=copy_id,
        provisioning_receipt_id=provision_id,
        isolation_verification_receipt_id=isolation_id,
        review_fingerprint=review_fingerprint,
        limit=20,
    )
    decision = decision_readback.get("latest_valid_receipt")
    decision = decision if isinstance(decision, dict) else {}
    if not decision or _text(decision.get("receipt_id")) != decision_receipt_id:
        blockers.append("safe_delta_export_preflight_decision_receipt_missing_or_mismatch")
    elif _text(decision.get("decision")) == "rejected":
        blockers.append("safe_delta_export_preflight_decision_rejected")
    elif _text(decision.get("decision")) != "approved" or decision_readback.get("safe_delta_approved") is not True:
        blockers.append("safe_delta_export_preflight_decision_not_approved")

    fingerprint = ""
    if not blockers:
        candidate = review.get("candidate")
        candidate = candidate if isinstance(candidate, dict) else {}
        fingerprint = _fingerprint(
            {
                "contract": MANAGED_COPY_SAFE_DELTA_EXPORT_PREFLIGHT_CONTRACT,
                "actor": safe_actor,
                "decision_receipt": _without_live_fields(decision),
                "review_receipt": _without_live_fields(review),
                "candidate": candidate,
                "copy_id": copy_id,
                "tenant_key": _text(review.get("tenant_key")),
                "provisioning_receipt_id": provision_id,
                "isolation_verification_receipt_id": isolation_id,
                "tenant_policy_checks": review.get("tenant_policy_checks"),
                "signal_class": _text(review.get("signal_class")),
                "direction": _text(review.get("direction")),
            }
        )

    ready = not blockers
    return {
        "ok": ready,
        "kind": MANAGED_COPY_SAFE_DELTA_EXPORT_PREFLIGHT_KIND,
        "contract": MANAGED_COPY_SAFE_DELTA_EXPORT_PREFLIGHT_CONTRACT,
        "status": "export_preflight_ready" if ready else "blocked",
        "error": "" if ready else "safe_delta_export_preflight_not_ready",
        "actor": safe_actor,
        "copy_id": copy_id,
        "provisioning_receipt_id": provision_id,
        "isolation_verification_receipt_id": isolation_id,
        "review_fingerprint": review_fingerprint,
        "review_receipt_id": _text(review.get("receipt_id")) if ready else "",
        "decision_receipt_id": decision_receipt_id,
        "decision": _text(decision.get("decision")) if decision else "",
        "signal_class": _text(review.get("signal_class")) if ready else "",
        "direction": _text(review.get("direction")) if ready else "",
        "dry_run": dry_run is True,
        "request_schema_exact": not unknown_fields and len(actor_fields) == 1,
        "unknown_fields": unknown_fields,
        "blockers": blockers,
        "export_preflight_fingerprint": fingerprint,
        "approved_for_future_export_preflight": ready,
        "safe_delta_exported": False,
        "safe_delta_flow_active": False,
        "contains_raw_candidate_material": False,
        "contains_raw_tenant_identity": False,
        **_NO_EFFECTS,
    }


def _without_live_fields(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if not key.startswith("live_")}


def _actor_lineage_blocked(
    *,
    safe_actor: str,
    copy_id: str,
    provision_id: str,
    isolation_id: str,
    review_fingerprint: str,
    decision_receipt_id: str,
    dry_run: Any,
    unknown_fields: list[str],
    actor_field_count: int,
) -> dict[str, Any]:
    return {
        "ok": False,
        "kind": MANAGED_COPY_SAFE_DELTA_EXPORT_PREFLIGHT_KIND,
        "contract": MANAGED_COPY_SAFE_DELTA_EXPORT_PREFLIGHT_CONTRACT,
        "status": "blocked",
        "error": "safe_delta_export_preflight_not_ready",
        "actor": safe_actor,
        "copy_id": copy_id,
        "provisioning_receipt_id": provision_id,
        "isolation_verification_receipt_id": isolation_id,
        "review_fingerprint": review_fingerprint,
        "review_receipt_id": "",
        "decision_receipt_id": decision_receipt_id,
        "decision": "",
        "signal_class": "",
        "direction": "",
        "dry_run": dry_run is True,
        "request_schema_exact": not unknown_fields and actor_field_count == 1,
        "unknown_fields": unknown_fields,
        "blockers": ["safe_delta_export_preflight_actor_lineage_mismatch"],
        "export_preflight_fingerprint": "",
        "approved_for_future_export_preflight": False,
        "safe_delta_exported": False,
        "safe_delta_flow_active": False,
        "contains_raw_candidate_material": False,
        "contains_raw_tenant_identity": False,
        **_NO_EFFECTS,
    }


def _fingerprint(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _redacted_text(value: Any) -> str:
    return redact_secret_text(_text(value)).strip()
