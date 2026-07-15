from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_secret_text
from francis.managed_copy_isolation import (
    latest_managed_copy_isolation_verification_for_provision,
    managed_copy_isolation_guarded_subpath,
)
from francis.managed_copy_provisioning import managed_copy_provision_for_copy
from francis.managed_copy_safe_delta import (
    _tenant_safe_delta_policy_checks,
    managed_copy_safe_delta_review_receipts_readback,
)
from francis.telemetry.audit import record as audit_record

MANAGED_COPY_SAFE_DELTA_APPROVAL_CONTRACT = "stage18_managed_copy_safe_delta_approval_v1"
MANAGED_COPY_SAFE_DELTA_APPROVAL_RECEIPT_KIND = "francis.stage18.managed_copies.safe_delta_approval_receipt"
MANAGED_COPY_SAFE_DELTA_APPROVAL_RECEIPTS_KIND = "francis.stage18.managed_copies.safe_delta_approval_receipts"

_DECISIONS = ("approved", "rejected")
_PAYLOAD_FIELDS = {
    "request_actor",
    "api_actor",
    "actor",
    "copy_id",
    "provisioning_receipt_id",
    "isolation_verification_receipt_id",
    "review_fingerprint",
    "decision",
    "dry_run",
    "decision_fingerprint",
    "confirm_safe_delta_decision",
}
_GOVERNANCE = {
    "exact_review_hash_bound": True,
    "current_lineage_hash_bound": True,
    "current_tenant_policy_hash_bound": True,
    "operator_decision_only": True,
    "eligible_for_future_export_preflight_only": True,
    "exports_delta": False,
    "imports_delta": False,
    "writes_learning": False,
    "executes_action": False,
    "writes_memory": False,
    "writes_registry": False,
    "writes_tenant_state": False,
    "uses_network": False,
    "grants_execution_authority": False,
    "grants_mutation_authority": False,
}
_RECEIPT_FIELDS = (
    "ok",
    "kind",
    "contract",
    "receipt_id",
    "receipt_fingerprint",
    "status",
    "actor",
    "decision",
    "decision_fingerprint",
    "copy_id",
    "tenant_key",
    "provisioning_receipt_id",
    "provision_fingerprint",
    "isolation_verification_receipt_id",
    "isolation_verification_fingerprint",
    "review_receipt_id",
    "review_receipt_fingerprint",
    "review_fingerprint",
    "tenant_policy_checks",
    "tenant_policy_fingerprint",
    "recorded_ts",
    "governance",
)
_LOCK = threading.Lock()


def managed_copy_safe_delta_decision_plan(payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    unknown_fields = sorted(set(payload) - _PAYLOAD_FIELDS)
    decision_value = payload.get("decision")
    decision = decision_value if isinstance(decision_value, str) else ""
    copy_id = _text(payload.get("copy_id"))
    provision_id = _text(payload.get("provisioning_receipt_id"))
    isolation_id = _text(payload.get("isolation_verification_receipt_id"))
    review_fingerprint = _text(payload.get("review_fingerprint"))
    safe_actor = _redacted_text(actor)[:240]
    blockers: list[str] = []
    if unknown_fields:
        blockers.append("safe_delta_decision_unknown_fields")
    if not safe_actor:
        blockers.append("safe_delta_decision_actor_missing")
    if decision not in _DECISIONS:
        blockers.append("safe_delta_decision_invalid")
    if not _is_sha256(review_fingerprint):
        blockers.append("safe_delta_review_fingerprint_invalid")

    provision = managed_copy_provision_for_copy(copy_id, provisioning_receipt_id=provision_id)
    isolation = (
        latest_managed_copy_isolation_verification_for_provision(
            provision_id,
            provision_fingerprint=_text(provision.get("provision_fingerprint")),
            copy_id=copy_id,
        )
        if provision
        else {}
    )
    if not provision:
        blockers.append("safe_delta_provision_lineage_missing")
    if not isolation or isolation.get("live_state_aligned") is not True:
        blockers.append("safe_delta_isolation_lineage_not_live")
    if isolation_id != _text(isolation.get("receipt_id")):
        blockers.append("safe_delta_isolation_lineage_mismatch")

    readback = managed_copy_safe_delta_review_receipts_readback(
        copy_id=copy_id,
        provisioning_receipt_id=provision_id,
        isolation_verification_receipt_id=isolation_id,
        review_fingerprint=review_fingerprint,
        limit=20,
    )
    review = readback.get("latest_valid_receipt")
    review = review if isinstance(review, dict) else {}
    if not review or not readback.get("receipt_set_valid"):
        blockers.append("safe_delta_review_receipt_missing_or_invalid")
    elif review.get("live_source_boundary_aligned") is not True:
        blockers.append("safe_delta_review_lineage_or_policy_drift")

    tenant_key = _text(provision.get("tenant_key"))
    tenant_root = _tenant_root(provision, isolation)
    policy_checks = _tenant_safe_delta_policy_checks(tenant_root)
    if not policy_checks or not all(check.get("ready") is True for check in policy_checks):
        blockers.append("safe_delta_tenant_policy_not_current")

    review_bound = {key: review[key] for key in review if not key.startswith("live_")} if review else {}
    lineage = {
        "copy_id": copy_id,
        "tenant_key": tenant_key,
        "provisioning_receipt_id": provision_id,
        "provision_fingerprint": _text(provision.get("provision_fingerprint")),
        "isolation_verification_receipt_id": isolation_id,
        "isolation_verification_fingerprint": _fingerprint(isolation) if isolation else "",
    }
    binding = {
        "contract": MANAGED_COPY_SAFE_DELTA_APPROVAL_CONTRACT,
        "actor": safe_actor,
        "decision": decision,
        "review_receipt": review_bound,
        "lineage": lineage,
        "tenant_policy_checks": policy_checks,
    }
    fingerprint = _fingerprint(binding) if not blockers else ""
    return {
        "ok": not blockers,
        "status": "safe_delta_decision_ready" if not blockers else "blocked",
        "contract": MANAGED_COPY_SAFE_DELTA_APPROVAL_CONTRACT,
        "actor": safe_actor,
        "decision": decision,
        "copy_id": copy_id,
        "tenant_key": tenant_key,
        "provisioning_receipt_id": provision_id,
        "provision_fingerprint": lineage["provision_fingerprint"],
        "isolation_verification_receipt_id": isolation_id,
        "isolation_verification_fingerprint": lineage["isolation_verification_fingerprint"],
        "review_receipt_id": _text(review.get("receipt_id")),
        "review_receipt_fingerprint": _text(review.get("receipt_fingerprint")),
        "review_fingerprint": review_fingerprint,
        "tenant_policy_checks": policy_checks,
        "tenant_policy_fingerprint": _fingerprint(policy_checks),
        "decision_fingerprint": fingerprint,
        "blockers": blockers,
        "unknown_fields": unknown_fields,
        "decision_contract_ready": not blockers,
        "dry_run_confirmation": {
            "required": True,
            "fingerprint": fingerprint,
            "fingerprint_contract": MANAGED_COPY_SAFE_DELTA_APPROVAL_CONTRACT,
        },
    }


def record_managed_copy_safe_delta_decision(
    plan: dict[str, Any], *, provided_fingerprint: str, confirmed: bool
) -> dict[str, Any]:
    expected = _text(plan.get("decision_fingerprint"))
    if not plan.get("decision_contract_ready"):
        return _blocked("blocked_safe_delta_decision_contract", "safe_delta_decision_contract_not_ready")
    actor = _text(plan.get("actor"))
    if not actor or actor != _redacted_text(actor)[:240]:
        return _blocked("blocked_safe_delta_decision_actor", "safe_delta_decision_actor_not_canonical")
    replanned = managed_copy_safe_delta_decision_plan(
        {
            "copy_id": plan.get("copy_id"),
            "provisioning_receipt_id": plan.get("provisioning_receipt_id"),
            "isolation_verification_receipt_id": plan.get("isolation_verification_receipt_id"),
            "review_fingerprint": plan.get("review_fingerprint"),
            "decision": plan.get("decision"),
        },
        actor=actor,
    )
    recomputed = _text(replanned.get("decision_fingerprint"))
    if (
        not replanned.get("decision_contract_ready")
        or not recomputed
        or recomputed != expected
        or recomputed != _text(provided_fingerprint)
    ):
        return _blocked("blocked_safe_delta_decision_fingerprint", "safe_delta_decision_fingerprint_mismatch")
    if not confirmed:
        return _blocked("blocked_safe_delta_decision_confirmation", "safe_delta_decision_confirmation_required")
    plan = replanned
    directory = _decision_directory(plan, create=True)
    if directory is None:
        return _blocked("blocked_safe_delta_decision_path", "safe_delta_decision_path_invalid")
    receipt_path = directory / f"{_text(plan['review_fingerprint'])[:16]}.json"
    with _LOCK:
        present, existing = _read_candidate(receipt_path)
        if present:
            if _valid_decision_receipt(existing, path=receipt_path, directory=directory):
                if _text(existing.get("decision_fingerprint")) == expected:
                    return _result(existing, status="already_decided", writes_receipt=False)
                return _blocked("blocked_safe_delta_decision_conflict", "safe_delta_decision_conflict")
            return _blocked("blocked_safe_delta_decision_conflict", "safe_delta_decision_receipt_conflict")
        receipt = {
            "ok": True,
            "kind": MANAGED_COPY_SAFE_DELTA_APPROVAL_RECEIPT_KIND,
            "contract": MANAGED_COPY_SAFE_DELTA_APPROVAL_CONTRACT,
            "receipt_id": f"managed_copy_safe_delta_decision_{expected[:16]}",
            "receipt_fingerprint": "",
            "status": _text(plan["decision"]),
            "actor": _text(plan["actor"]),
            "decision": _text(plan["decision"]),
            "decision_fingerprint": expected,
            "copy_id": _text(plan["copy_id"]),
            "tenant_key": _text(plan["tenant_key"]),
            "provisioning_receipt_id": _text(plan["provisioning_receipt_id"]),
            "provision_fingerprint": _text(plan["provision_fingerprint"]),
            "isolation_verification_receipt_id": _text(plan["isolation_verification_receipt_id"]),
            "isolation_verification_fingerprint": _text(plan["isolation_verification_fingerprint"]),
            "review_receipt_id": _text(plan["review_receipt_id"]),
            "review_receipt_fingerprint": _text(plan["review_receipt_fingerprint"]),
            "review_fingerprint": _text(plan["review_fingerprint"]),
            "tenant_policy_checks": plan["tenant_policy_checks"],
            "tenant_policy_fingerprint": _text(plan["tenant_policy_fingerprint"]),
            "recorded_ts": int(time.time()),
            "governance": dict(_GOVERNANCE),
        }
        receipt["receipt_fingerprint"] = _receipt_fingerprint(receipt)
        if not _valid_decision_receipt(receipt, path=receipt_path, directory=directory):
            return _blocked("failed_safe_delta_decision_receipt", "safe_delta_decision_receipt_invalid")
        try:
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            with receipt_path.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        except OSError:
            return _blocked("failed_safe_delta_decision_write", "safe_delta_decision_receipt_write_failed")
    audit_record(
        "managed_copies.safe_delta_decision_recorded",
        actor=_text(plan["actor"]),
        copy_id=_text(plan["copy_id"]),
        decision=_text(plan["decision"]),
        review_fingerprint=_text(plan["review_fingerprint"]),
    )
    return _result(receipt, status=_text(receipt["status"]), writes_receipt=True)


def managed_copy_safe_delta_decisions_readback(
    *,
    copy_id: str = "",
    provisioning_receipt_id: str = "",
    isolation_verification_receipt_id: str = "",
    review_fingerprint: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    plan_seed = {
        "copy_id": _text(copy_id),
        "provisioning_receipt_id": _text(provisioning_receipt_id),
        "isolation_verification_receipt_id": _text(isolation_verification_receipt_id),
        "review_fingerprint": _text(review_fingerprint),
    }
    if not all(plan_seed.values()):
        return _readback_payload([], [], status="lineage_required")
    provision = managed_copy_provision_for_copy(
        plan_seed["copy_id"], provisioning_receipt_id=plan_seed["provisioning_receipt_id"]
    )
    isolation = (
        latest_managed_copy_isolation_verification_for_provision(
            plan_seed["provisioning_receipt_id"],
            provision_fingerprint=_text(provision.get("provision_fingerprint")),
            copy_id=plan_seed["copy_id"],
        )
        if provision
        else {}
    )
    directory = _decision_directory(
        {
            **plan_seed,
            "tenant_key": _text(provision.get("tenant_key")),
            "provision_fingerprint": _text(provision.get("provision_fingerprint")),
            "isolation_verification_fingerprint": _fingerprint(isolation) if isolation else "",
        },
        create=False,
    )
    if directory is None or not directory.is_dir():
        return _readback_payload([], [], status="empty")
    paths = sorted(directory.glob("*.json"))
    items = [_read_candidate(path)[1] for path in paths]
    valid = [
        item
        for path, item in zip(paths, items, strict=True)
        if _valid_decision_receipt(item, path=path, directory=directory)
        and _text(item.get("review_fingerprint")) == plan_seed["review_fingerprint"]
    ]
    valid.sort(key=_receipt_chronology_key)
    aligned = [item for item in valid if _live_aligned(item)][-_safe_limit(limit) :]
    return _readback_payload(
        [dict(item) for item in valid[-_safe_limit(limit) :]],
        aligned,
        status=_text(aligned[-1].get("decision")) if aligned else "invalid_or_drifted",
    )


def _live_aligned(item: dict[str, Any]) -> bool:
    payload = {
        "copy_id": item.get("copy_id"),
        "provisioning_receipt_id": item.get("provisioning_receipt_id"),
        "isolation_verification_receipt_id": item.get("isolation_verification_receipt_id"),
        "review_fingerprint": item.get("review_fingerprint"),
        "decision": item.get("decision"),
    }
    plan = managed_copy_safe_delta_decision_plan(payload, actor=_text(item.get("actor")))
    return bool(
        plan.get("decision_contract_ready") and plan.get("decision_fingerprint") == item.get("decision_fingerprint")
    )


def _valid_decision_receipt(item: dict[str, Any], *, path: Path, directory: Path) -> bool:
    decision = _text(item.get("decision"))
    return (
        set(item) == set(_RECEIPT_FIELDS)
        and item.get("ok") is True
        and item.get("kind") == MANAGED_COPY_SAFE_DELTA_APPROVAL_RECEIPT_KIND
        and item.get("contract") == MANAGED_COPY_SAFE_DELTA_APPROVAL_CONTRACT
        and bool(_text(item.get("actor")))
        and len(_text(item.get("actor"))) <= 240
        and _text(item.get("actor")) == _redacted_text(item.get("actor"))[:240]
        and decision in _DECISIONS
        and item.get("status") == decision
        and _is_sha256(item.get("decision_fingerprint"))
        and item.get("receipt_id") == f"managed_copy_safe_delta_decision_{item['decision_fingerprint'][:16]}"
        and _is_sha256(item.get("receipt_fingerprint"))
        and item.get("receipt_fingerprint") == _receipt_fingerprint(item)
        and _is_sha256(item.get("tenant_key"))
        and _is_sha256(item.get("provision_fingerprint"))
        and _is_sha256(item.get("isolation_verification_fingerprint"))
        and _is_sha256(item.get("review_receipt_fingerprint"))
        and _is_sha256(item.get("review_fingerprint"))
        and _is_sha256(item.get("tenant_policy_fingerprint"))
        and item.get("tenant_policy_fingerprint") == _fingerprint(item.get("tenant_policy_checks"))
        and isinstance(item.get("recorded_ts"), int)
        and not isinstance(item.get("recorded_ts"), bool)
        and item["recorded_ts"] > 0
        and item.get("governance") == _GOVERNANCE
        and path == directory / f"{item['review_fingerprint'][:16]}.json"
    )


def _decision_directory(plan: dict[str, Any], *, create: bool) -> Path | None:
    provision = managed_copy_provision_for_copy(
        _text(plan.get("copy_id")), provisioning_receipt_id=_text(plan.get("provisioning_receipt_id"))
    )
    isolation = (
        latest_managed_copy_isolation_verification_for_provision(
            _text(plan.get("provisioning_receipt_id")),
            provision_fingerprint=_text(provision.get("provision_fingerprint")),
            copy_id=_text(plan.get("copy_id")),
        )
        if provision
        else {}
    )
    return managed_copy_isolation_guarded_subpath(
        provision,
        isolation,
        domain="tenant_receipts",
        relative_parts=("sda",),
        create_leaf_directory=create,
        require_live=True,
    )


def _tenant_root(provision: dict[str, Any], isolation: dict[str, Any]) -> Path | None:
    directory = managed_copy_isolation_guarded_subpath(
        provision, isolation, domain="tenant_receipts", relative_parts=(), require_live=True
    )
    return directory.parent if directory is not None else None


def _readback_payload(items: list[dict[str, Any]], valid: list[dict[str, Any]], *, status: str) -> dict[str, Any]:
    latest = valid[-1] if valid else {}
    decision = _text(latest.get("decision"))
    return {
        "ok": True,
        "kind": MANAGED_COPY_SAFE_DELTA_APPROVAL_RECEIPTS_KIND,
        "status": status,
        "items": items,
        "count": len(items),
        "valid_count": len(valid),
        "latest_valid_receipt": latest,
        "latest_valid_receipt_id": _text(latest.get("receipt_id")),
        "decision": decision,
        "safe_delta_approved": decision == "approved",
        "safe_delta_rejected": decision == "rejected",
        "eligible_for_future_export_preflight": decision == "approved",
        **_no_authority(writes_receipt=False),
    }


def _receipt_chronology_key(item: dict[str, Any]) -> tuple[int, str, str]:
    recorded_ts = item.get("recorded_ts")
    timestamp = recorded_ts if isinstance(recorded_ts, int) and not isinstance(recorded_ts, bool) else 0
    return timestamp, _text(item.get("receipt_id")), _text(item.get("receipt_fingerprint"))


def _result(receipt: dict[str, Any], *, status: str, writes_receipt: bool) -> dict[str, Any]:
    decision = _text(receipt.get("decision"))
    return {
        "ok": True,
        "status": status,
        "error": "",
        "receipt": receipt,
        "receipt_id": _text(receipt.get("receipt_id")),
        "decision": decision,
        "safe_delta_approved": decision == "approved",
        "safe_delta_rejected": decision == "rejected",
        "eligible_for_future_export_preflight": decision == "approved",
        **_no_authority(writes_receipt=writes_receipt),
    }


def _blocked(status: str, error: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": status,
        "error": error,
        "receipt": None,
        "receipt_id": "",
        "decision": "",
        "safe_delta_approved": False,
        "safe_delta_rejected": False,
        "eligible_for_future_export_preflight": False,
        **_no_authority(writes_receipt=False),
    }


def _no_authority(*, writes_receipt: bool) -> dict[str, bool]:
    return {
        "writes_receipt": writes_receipt,
        "writes_receipts": writes_receipt,
        "exports_delta": False,
        "imports_delta": False,
        "writes_learning": False,
        "executes_action": False,
        "writes_memory": False,
        "writes_registry": False,
        "writes_tenant_state": False,
        "uses_network": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def _read_candidate(path: Path) -> tuple[bool, dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, {}
    except (OSError, json.JSONDecodeError):
        return True, {}
    return True, value if isinstance(value, dict) else {}


def _receipt_fingerprint(item: dict[str, Any]) -> str:
    return _fingerprint({field: item.get(field) for field in _RECEIPT_FIELDS if field != "receipt_fingerprint"})


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _redacted_text(value: Any) -> str:
    return redact_secret_text(_text(value)).strip()


def _safe_limit(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 20
    return min(max(parsed, 1), 500)
