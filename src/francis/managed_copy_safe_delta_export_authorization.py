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
from francis.managed_copy_safe_delta_export import managed_copy_safe_delta_export_preflight

MANAGED_COPY_SAFE_DELTA_EXPORT_AUTHORIZATION_REQUEST_CONTRACT = (
    "stage18_managed_copy_safe_delta_export_authorization_request_v1"
)
MANAGED_COPY_SAFE_DELTA_EXPORT_AUTHORIZATION_REQUEST_KIND = (
    "francis.stage18.managed_copies.safe_delta_export_authorization_request_receipt"
)
MANAGED_COPY_SAFE_DELTA_EXPORT_AUTHORIZATION_REQUESTS_KIND = (
    "francis.stage18.managed_copies.safe_delta_export_authorization_requests"
)

_EXPORT_CLASS = "safe_delta_signal"
_RETENTION_CLASS = "authorization_request_receipt_only"
_DESTINATION_CLASS = "governed_export_boundary"
_REQUEST_FIELDS = {
    "request_actor",
    "copy_id",
    "provisioning_receipt_id",
    "isolation_verification_receipt_id",
    "review_fingerprint",
    "decision_receipt_id",
    "preflight_fingerprint",
    "export_class",
    "retention_class",
    "destination_class",
    "purpose_fingerprint",
    "dry_run",
    "request_fingerprint",
    "confirm_export_authorization_request",
}
_NO_AUTHORITY = {
    "export_approved": False,
    "export_executed": False,
    "safe_delta_exported": False,
    "safe_delta_flow_active": False,
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
_RECEIPT_FIELDS = (
    "ok",
    "kind",
    "contract",
    "receipt_id",
    "receipt_fingerprint",
    "status",
    "actor",
    "copy_id",
    "tenant_key",
    "provisioning_receipt_id",
    "isolation_verification_receipt_id",
    "review_fingerprint",
    "decision_receipt_id",
    "preflight_fingerprint",
    "export_class",
    "retention_class",
    "destination_class",
    "purpose_fingerprint",
    "request_fingerprint",
    "recorded_ts",
    "governance",
)
_GOVERNANCE = {
    "pending_request_only": True,
    "exact_action_hash_bound": True,
    "fresh_preflight_required": True,
    "contains_raw_candidate_material": False,
    "contains_raw_tenant_identity": False,
    "contains_credentials": False,
    "contains_concrete_destination": False,
    **_NO_AUTHORITY,
}
_LOCK = threading.Lock()


def managed_copy_safe_delta_export_authorization_request_plan(payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    safe_actor = _redacted(actor)[:240]
    request_actor = _redacted(payload.get("request_actor"))[:240]
    unknown = sorted(set(payload) - _REQUEST_FIELDS)
    bounded = {
        "request_actor": request_actor,
        "copy_id": _text(payload.get("copy_id")),
        "provisioning_receipt_id": _text(payload.get("provisioning_receipt_id")),
        "isolation_verification_receipt_id": _text(payload.get("isolation_verification_receipt_id")),
        "review_fingerprint": _text(payload.get("review_fingerprint")),
        "decision_receipt_id": _text(payload.get("decision_receipt_id")),
        "preflight_fingerprint": _text(payload.get("preflight_fingerprint")),
        "export_class": _text(payload.get("export_class")),
        "retention_class": _text(payload.get("retention_class")),
        "destination_class": _text(payload.get("destination_class")),
        "purpose_fingerprint": _text(payload.get("purpose_fingerprint")),
    }
    blockers: list[str] = []
    if unknown:
        blockers.append("safe_delta_export_authorization_request_unknown_fields")
    if not safe_actor or request_actor != safe_actor:
        blockers.append("safe_delta_export_authorization_request_actor_lineage_mismatch")
    if payload.get("dry_run") is not True and payload.get("dry_run") is not False:
        blockers.append("safe_delta_export_authorization_request_dry_run_boolean_required")
    if bounded["export_class"] != _EXPORT_CLASS:
        blockers.append("safe_delta_export_authorization_request_export_class_invalid")
    if bounded["retention_class"] != _RETENTION_CLASS:
        blockers.append("safe_delta_export_authorization_request_retention_class_invalid")
    if bounded["destination_class"] != _DESTINATION_CLASS:
        blockers.append("safe_delta_export_authorization_request_destination_class_invalid")
    if not _sha256(bounded["purpose_fingerprint"]):
        blockers.append("safe_delta_export_authorization_request_purpose_fingerprint_invalid")

    preflight = managed_copy_safe_delta_export_preflight(
        {
            "request_actor": safe_actor,
            "copy_id": bounded["copy_id"],
            "provisioning_receipt_id": bounded["provisioning_receipt_id"],
            "isolation_verification_receipt_id": bounded["isolation_verification_receipt_id"],
            "review_fingerprint": bounded["review_fingerprint"],
            "decision_receipt_id": bounded["decision_receipt_id"],
            "dry_run": True,
        },
        actor=safe_actor,
    )
    fresh_preflight = _text(preflight.get("export_preflight_fingerprint"))
    if preflight.get("status") != "export_preflight_ready" or not fresh_preflight:
        blockers.append("safe_delta_export_authorization_request_preflight_not_ready")
    elif bounded["preflight_fingerprint"] != fresh_preflight:
        blockers.append("safe_delta_export_authorization_request_preflight_fingerprint_mismatch")

    binding = {
        "contract": MANAGED_COPY_SAFE_DELTA_EXPORT_AUTHORIZATION_REQUEST_CONTRACT,
        **bounded,
        "actor": safe_actor,
        "preflight_fingerprint": fresh_preflight,
        "signal_class": _text(preflight.get("signal_class")),
        "direction": _text(preflight.get("direction")),
    }
    fingerprint = _fingerprint(binding) if not blockers else ""
    return {
        "ok": not blockers,
        "status": "export_authorization_request_ready" if not blockers else "blocked",
        "contract": MANAGED_COPY_SAFE_DELTA_EXPORT_AUTHORIZATION_REQUEST_CONTRACT,
        "actor": safe_actor,
        "request": bounded,
        "preflight_fingerprint": fresh_preflight,
        "request_fingerprint": fingerprint,
        "blockers": blockers,
        "unknown_fields": unknown,
        "dry_run": payload.get("dry_run") is True,
        "writes_receipt": False,
        **_NO_AUTHORITY,
    }


def record_managed_copy_safe_delta_export_authorization_request(
    plan: dict[str, Any], *, provided_fingerprint: str, confirmed: bool
) -> dict[str, Any]:
    raw_request = plan.get("request")
    request: dict[str, Any] = dict(raw_request) if isinstance(raw_request, dict) else {}
    replanned = managed_copy_safe_delta_export_authorization_request_plan(
        {**request, "dry_run": False}, actor=_text(plan.get("actor"))
    )
    expected = _text(replanned.get("request_fingerprint"))
    if not replanned.get("ok") or expected != _text(plan.get("request_fingerprint")):
        return _blocked("safe_delta_export_authorization_request_plan_drift")
    if not confirmed:
        return _blocked("safe_delta_export_authorization_request_confirmation_required")
    if not expected or expected != _text(provided_fingerprint):
        return _blocked("safe_delta_export_authorization_request_fingerprint_mismatch")
    directory = _request_directory(request, create=True)
    if directory is None:
        return _blocked("safe_delta_export_authorization_request_path_invalid")
    with _LOCK:
        final_plan = managed_copy_safe_delta_export_authorization_request_plan(
            {**request, "dry_run": False}, actor=_text(plan.get("actor"))
        )
        final_fingerprint = _text(final_plan.get("request_fingerprint"))
        if (
            not final_plan.get("ok")
            or not final_fingerprint
            or final_fingerprint != _text(plan.get("request_fingerprint"))
            or final_fingerprint != _text(provided_fingerprint)
        ):
            return _blocked("safe_delta_export_authorization_request_plan_drift")
        path = directory / f"{final_fingerprint[:16]}.json"
        present, existing = _read(path)
        if present:
            if _valid_receipt(existing, path=path, directory=directory):
                if _text(existing.get("request_fingerprint")) == expected:
                    return _recorded(existing, "already_requested", False)
            return _blocked("safe_delta_export_authorization_request_receipt_conflict")
        provision = managed_copy_provision_for_copy(
            _text(request.get("copy_id")), provisioning_receipt_id=_text(request.get("provisioning_receipt_id"))
        )
        receipt = {
            "ok": True,
            "kind": MANAGED_COPY_SAFE_DELTA_EXPORT_AUTHORIZATION_REQUEST_KIND,
            "contract": MANAGED_COPY_SAFE_DELTA_EXPORT_AUTHORIZATION_REQUEST_CONTRACT,
            "receipt_id": f"managed_copy_safe_delta_export_authorization_request_{final_fingerprint[:16]}",
            "receipt_fingerprint": "",
            "status": "export_authorization_pending",
            "actor": _text(final_plan.get("actor")),
            "copy_id": _text(request.get("copy_id")),
            "tenant_key": _text(provision.get("tenant_key")),
            "provisioning_receipt_id": _text(request.get("provisioning_receipt_id")),
            "isolation_verification_receipt_id": _text(request.get("isolation_verification_receipt_id")),
            "review_fingerprint": _text(request.get("review_fingerprint")),
            "decision_receipt_id": _text(request.get("decision_receipt_id")),
            "preflight_fingerprint": _text(final_plan.get("preflight_fingerprint")),
            "export_class": _text(request.get("export_class")),
            "retention_class": _text(request.get("retention_class")),
            "destination_class": _text(request.get("destination_class")),
            "purpose_fingerprint": _text(request.get("purpose_fingerprint")),
            "request_fingerprint": final_fingerprint,
            "recorded_ts": int(time.time()),
            "governance": dict(_GOVERNANCE),
        }
        receipt["receipt_fingerprint"] = _receipt_fingerprint(receipt)
        if not _valid_receipt(receipt, path=path, directory=directory):
            return _blocked("safe_delta_export_authorization_request_receipt_invalid")
        try:
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        except OSError:
            return _blocked("safe_delta_export_authorization_request_write_failed")
    return _recorded(receipt, "export_authorization_pending", True)


def managed_copy_safe_delta_export_authorization_requests_readback(
    *, copy_id: str, provisioning_receipt_id: str, isolation_verification_receipt_id: str, limit: int = 20
) -> dict[str, Any]:
    request = {
        "copy_id": _text(copy_id),
        "provisioning_receipt_id": _text(provisioning_receipt_id),
        "isolation_verification_receipt_id": _text(isolation_verification_receipt_id),
    }
    directory = _request_directory(request, create=False)
    if directory is None or not directory.is_dir():
        return _readback([], "empty")
    valid = []
    for path in sorted(directory.glob("*.json")):
        _, item = _read(path)
        if _valid_receipt(item, path=path, directory=directory) and _receipt_live(item):
            valid.append(item)
    valid.sort(key=lambda item: (int(item["recorded_ts"]), _text(item.get("receipt_id"))))
    return _readback(
        valid[-max(1, min(int(limit), 500)) :], "export_authorization_pending" if valid else "invalid_or_drifted"
    )


def _receipt_live(item: dict[str, Any]) -> bool:
    payload = {field: item.get(field) for field in _REQUEST_FIELDS if field in item}
    payload["request_actor"] = item.get("actor")
    payload["dry_run"] = True
    plan = managed_copy_safe_delta_export_authorization_request_plan(payload, actor=_text(item.get("actor")))
    return bool(plan.get("ok") and plan.get("request_fingerprint") == item.get("request_fingerprint"))


def _valid_receipt(item: dict[str, Any], *, path: Path, directory: Path) -> bool:
    return bool(
        set(item) == set(_RECEIPT_FIELDS)
        and item.get("ok") is True
        and item.get("kind") == MANAGED_COPY_SAFE_DELTA_EXPORT_AUTHORIZATION_REQUEST_KIND
        and item.get("contract") == MANAGED_COPY_SAFE_DELTA_EXPORT_AUTHORIZATION_REQUEST_CONTRACT
        and item.get("status") == "export_authorization_pending"
        and _sha256(item.get("tenant_key"))
        and _sha256(item.get("request_fingerprint"))
        and _sha256(item.get("receipt_fingerprint"))
        and item.get("receipt_fingerprint") == _receipt_fingerprint(item)
        and item.get("receipt_id")
        == f"managed_copy_safe_delta_export_authorization_request_{item['request_fingerprint'][:16]}"
        and item.get("export_class") == _EXPORT_CLASS
        and item.get("retention_class") == _RETENTION_CLASS
        and item.get("destination_class") == _DESTINATION_CLASS
        and _sha256(item.get("purpose_fingerprint"))
        and item.get("governance") == _GOVERNANCE
        and isinstance(item.get("recorded_ts"), int)
        and not isinstance(item.get("recorded_ts"), bool)
        and item["recorded_ts"] > 0
        and path == directory / f"{item['request_fingerprint'][:16]}.json"
    )


def _request_directory(request: dict[str, Any], *, create: bool) -> Path | None:
    provision = managed_copy_provision_for_copy(
        _text(request.get("copy_id")), provisioning_receipt_id=_text(request.get("provisioning_receipt_id"))
    )
    isolation = (
        latest_managed_copy_isolation_verification_for_provision(
            _text(request.get("provisioning_receipt_id")),
            provision_fingerprint=_text(provision.get("provision_fingerprint")),
            copy_id=_text(request.get("copy_id")),
        )
        if provision
        else {}
    )
    return managed_copy_isolation_guarded_subpath(
        provision,
        isolation,
        domain="tenant_receipts",
        relative_parts=("sx",),
        create_leaf_directory=create,
        require_live=True,
    )


def _recorded(receipt: dict[str, Any], status: str, writes: bool) -> dict[str, Any]:
    return {
        "ok": True,
        "status": status,
        "error": "",
        "receipt": receipt,
        "receipt_id": _text(receipt.get("receipt_id")),
        "writes_receipt": writes,
        "export_authorization_pending": True,
        **_NO_AUTHORITY,
    }


def _blocked(error: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "blocked",
        "error": error,
        "receipt": None,
        "receipt_id": "",
        "writes_receipt": False,
        "export_authorization_pending": False,
        **_NO_AUTHORITY,
    }


def _readback(items: list[dict[str, Any]], status: str) -> dict[str, Any]:
    latest = items[-1] if items else {}
    return {
        "ok": True,
        "kind": MANAGED_COPY_SAFE_DELTA_EXPORT_AUTHORIZATION_REQUESTS_KIND,
        "status": status,
        "items": items,
        "count": len(items),
        "valid_count": len(items),
        "latest_valid_receipt": latest,
        "latest_valid_receipt_id": _text(latest.get("receipt_id")),
        "export_authorization_pending": bool(latest),
        "writes_receipt": False,
        **_NO_AUTHORITY,
    }


def _read(path: Path) -> tuple[bool, dict[str, Any]]:
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


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _redacted(value: Any) -> str:
    return redact_secret_text(_text(value)).strip()
