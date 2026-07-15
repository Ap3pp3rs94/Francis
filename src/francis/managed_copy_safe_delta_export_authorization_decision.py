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
from francis.managed_copy_safe_delta_export_authorization import (
    managed_copy_safe_delta_export_authorization_requests_readback,
)

CONTRACT = "stage18_managed_copy_safe_delta_export_authorization_decision_v1"
RECEIPT_KIND = "francis.stage18.managed_copies.safe_delta_export_authorization_decision_receipt"
READBACK_KIND = "francis.stage18.managed_copies.safe_delta_export_authorization_decisions"
_OUTCOMES = {"approved", "rejected"}
_FIELDS = {
    "request_actor",
    "copy_id",
    "provisioning_receipt_id",
    "isolation_verification_receipt_id",
    "review_fingerprint",
    "decision_receipt_id",
    "preflight_fingerprint",
    "request_receipt_id",
    "request_fingerprint",
    "export_class",
    "retention_class",
    "destination_class",
    "purpose_fingerprint",
    "decision",
    "dry_run",
    "authorization_decision_fingerprint",
    "confirm_export_authorization_decision",
}
_NO_EFFECT = {
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
    "grants_export_authority": False,
    "grants_execution_authority": False,
    "grants_mutation_authority": False,
}
RECEIPT_FIELDS = {
    "ok",
    "kind",
    "contract",
    "receipt_id",
    "receipt_fingerprint",
    "status",
    "actor",
    "tenant_key",
    "request_actor",
    "copy_id",
    "provisioning_receipt_id",
    "isolation_verification_receipt_id",
    "review_fingerprint",
    "decision_receipt_id",
    "preflight_fingerprint",
    "request_receipt_id",
    "request_fingerprint",
    "export_class",
    "retention_class",
    "destination_class",
    "purpose_fingerprint",
    "decision",
    "authorization_decision_fingerprint",
    "recorded_ts",
    "governance",
}
_LOCK = threading.Lock()


def managed_copy_safe_delta_export_authorization_decision_plan(
    payload: dict[str, Any], *, actor: str
) -> dict[str, Any]:
    safe_actor = _redacted(actor)[:240]
    request_actor = _redacted(payload.get("request_actor"))[:240]
    unknown = sorted(set(payload) - _FIELDS)
    bounded = {
        key: _text(payload.get(key))
        for key in _FIELDS
        if key not in {"dry_run", "confirm_export_authorization_decision", "authorization_decision_fingerprint"}
    }
    blockers: list[str] = []
    if unknown:
        blockers.append("safe_delta_export_authorization_decision_unknown_fields")
    if not safe_actor or request_actor != safe_actor:
        blockers.append("safe_delta_export_authorization_decision_actor_lineage_mismatch")
    if payload.get("dry_run") is not True and payload.get("dry_run") is not False:
        blockers.append("safe_delta_export_authorization_decision_dry_run_boolean_required")
    if bounded["decision"] not in _OUTCOMES:
        blockers.append("safe_delta_export_authorization_decision_invalid")
    readback = managed_copy_safe_delta_export_authorization_requests_readback(
        copy_id=bounded["copy_id"],
        provisioning_receipt_id=bounded["provisioning_receipt_id"],
        isolation_verification_receipt_id=bounded["isolation_verification_receipt_id"],
        limit=500,
    )
    matches = [
        item
        for item in readback.get("items", [])
        if isinstance(item, dict)
        and item.get("receipt_id") == bounded["request_receipt_id"]
        and item.get("request_fingerprint") == bounded["request_fingerprint"]
    ]
    source = matches[0] if len(matches) == 1 else {}
    provision = managed_copy_provision_for_copy(
        bounded["copy_id"], provisioning_receipt_id=bounded["provisioning_receipt_id"]
    )
    tenant_key = _text(provision.get("tenant_key"))
    source_fields = (
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
        "request_fingerprint",
    )
    if not source or any(source.get(key) != bounded[key] for key in source_fields):
        blockers.append("safe_delta_export_authorization_decision_request_missing_or_mismatch")
    if not _sha(tenant_key) or source.get("tenant_key") != tenant_key:
        blockers.append("safe_delta_export_authorization_decision_tenant_lineage_mismatch")
    binding = {
        "contract": CONTRACT,
        "actor": safe_actor,
        "tenant_key": tenant_key,
        **bounded,
        "request_receipt_fingerprint": _text(source.get("receipt_fingerprint")),
    }
    fingerprint = _fingerprint(binding) if not blockers else ""
    return {
        "ok": not blockers,
        "status": "export_authorization_decision_ready" if not blockers else "blocked",
        "contract": CONTRACT,
        "actor": safe_actor,
        "request": bounded,
        "tenant_key": tenant_key,
        "authorization_decision_fingerprint": fingerprint,
        "blockers": blockers,
        "dry_run": payload.get("dry_run") is True,
        "writes_receipt": False,
        **_NO_EFFECT,
    }


def record_managed_copy_safe_delta_export_authorization_decision(
    plan: dict[str, Any], *, provided_fingerprint: str, confirmed: bool
) -> dict[str, Any]:
    raw = plan.get("request")
    request: dict[str, Any] = dict(raw) if isinstance(raw, dict) else {}
    initial = managed_copy_safe_delta_export_authorization_decision_plan(
        {**request, "dry_run": False}, actor=_text(plan.get("actor"))
    )
    expected = _text(initial.get("authorization_decision_fingerprint"))
    if not initial.get("ok") or expected != _text(plan.get("authorization_decision_fingerprint")):
        return _blocked("safe_delta_export_authorization_decision_plan_drift")
    if not confirmed:
        return _blocked("safe_delta_export_authorization_decision_confirmation_required")
    if not expected or expected != _text(provided_fingerprint):
        return _blocked("safe_delta_export_authorization_decision_fingerprint_mismatch")
    directory = _directory(request, create=True)
    if directory is None:
        return _blocked("safe_delta_export_authorization_decision_path_invalid")
    with _LOCK:
        final = managed_copy_safe_delta_export_authorization_decision_plan(
            {**request, "dry_run": False}, actor=_text(plan.get("actor"))
        )
        final_fp = _text(final.get("authorization_decision_fingerprint"))
        if not final.get("ok") or final_fp != expected or final_fp != _text(provided_fingerprint):
            return _blocked("safe_delta_export_authorization_decision_plan_drift")
        path = directory / f"{request['request_fingerprint'][:16]}.json"
        present, existing = _read(path)
        if present:
            if _valid(existing, path, directory):
                if existing.get("authorization_decision_fingerprint") == final_fp:
                    return _recorded(existing, "already_decided", False)
                return _blocked("safe_delta_export_authorization_decision_conflict")
            return _blocked("safe_delta_export_authorization_decision_receipt_conflict")
        receipt = {
            "ok": True,
            "kind": RECEIPT_KIND,
            "contract": CONTRACT,
            "receipt_id": f"managed_copy_safe_delta_export_authorization_decision_{final_fp[:16]}",
            "receipt_fingerprint": "",
            "status": f"export_authorization_{request['decision']}",
            "actor": _text(final.get("actor")),
            "tenant_key": _text(final.get("tenant_key")),
            **request,
            "authorization_decision_fingerprint": final_fp,
            "recorded_ts": int(time.time()),
            "governance": {"decision_receipt_only": True, **_NO_EFFECT},
        }
        receipt["receipt_fingerprint"] = _receipt_fp(receipt)
        if not _valid(receipt, path, directory):
            return _blocked("safe_delta_export_authorization_decision_receipt_invalid")
        try:
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        except OSError:
            return _blocked("safe_delta_export_authorization_decision_write_failed")
    return _recorded(receipt, receipt["status"], True)


def managed_copy_safe_delta_export_authorization_decisions_readback(
    *, copy_id: str, provisioning_receipt_id: str, isolation_verification_receipt_id: str, limit: int = 20
) -> dict[str, Any]:
    request = {
        "copy_id": _text(copy_id),
        "provisioning_receipt_id": _text(provisioning_receipt_id),
        "isolation_verification_receipt_id": _text(isolation_verification_receipt_id),
    }
    directory = _directory(request, create=False)
    if directory is None or not directory.is_dir():
        return _readback([], "empty")
    valid = []
    for path in sorted(directory.glob("*.json")):
        _, item = _read(path)
        payload = {key: item.get(key) for key in _FIELDS if key in item}
        payload["request_actor"] = item.get("actor")
        payload["dry_run"] = True
        live = managed_copy_safe_delta_export_authorization_decision_plan(payload, actor=_text(item.get("actor")))
        if (
            _valid(item, path, directory)
            and live.get("authorization_decision_fingerprint") == item.get("authorization_decision_fingerprint")
            and live.get("tenant_key") == item.get("tenant_key")
        ):
            valid.append(item)
    valid.sort(key=lambda item: (int(item["recorded_ts"]), _text(item.get("receipt_id"))))
    return _readback(valid[-max(1, min(int(limit), 500)) :], "decisions_present" if valid else "invalid_or_drifted")


def _directory(request: dict[str, Any], *, create: bool) -> Path | None:
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
        relative_parts=("sy",),
        create_leaf_directory=create,
        require_live=True,
    )


def _valid(item: dict[str, Any], path: Path, directory: Path) -> bool:
    fp = _text(item.get("authorization_decision_fingerprint"))
    actor = _text(item.get("actor"))
    return bool(
        set(item) == RECEIPT_FIELDS
        and item.get("ok") is True
        and item.get("kind") == RECEIPT_KIND
        and item.get("contract") == CONTRACT
        and item.get("receipt_id") == f"managed_copy_safe_delta_export_authorization_decision_{fp[:16]}"
        and item.get("decision") in _OUTCOMES
        and item.get("status") == f"export_authorization_{item.get('decision')}"
        and _sha(fp)
        and _sha(item.get("receipt_fingerprint"))
        and _sha(item.get("tenant_key"))
        and _sha(item.get("request_fingerprint"))
        and _sha(item.get("preflight_fingerprint"))
        and _sha(item.get("review_fingerprint"))
        and _sha(item.get("purpose_fingerprint"))
        and actor
        and len(actor) <= 240
        and actor == _redacted(actor)[:240]
        and item.get("request_actor") == actor
        and all(
            _text(item.get(key))
            for key in (
                "copy_id",
                "provisioning_receipt_id",
                "isolation_verification_receipt_id",
                "decision_receipt_id",
                "request_receipt_id",
                "export_class",
                "retention_class",
                "destination_class",
            )
        )
        and item.get("receipt_fingerprint") == _receipt_fp(item)
        and item.get("governance") == {"decision_receipt_only": True, **_NO_EFFECT}
        and isinstance(item.get("recorded_ts"), int)
        and not isinstance(item.get("recorded_ts"), bool)
        and item["recorded_ts"] > 0
        and path == directory / f"{_text(item.get('request_fingerprint'))[:16]}.json"
    )


def _recorded(receipt: dict[str, Any], status: str, writes: bool) -> dict[str, Any]:
    return {
        "ok": True,
        "status": status,
        "error": "",
        "receipt": receipt,
        "receipt_id": _text(receipt.get("receipt_id")),
        "writes_receipt": writes,
        **_NO_EFFECT,
    }


def _blocked(error: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "blocked",
        "error": error,
        "receipt": None,
        "receipt_id": "",
        "writes_receipt": False,
        **_NO_EFFECT,
    }


def _readback(items: list[dict[str, Any]], status: str) -> dict[str, Any]:
    latest = items[-1] if items else {}
    return {
        "ok": True,
        "kind": READBACK_KIND,
        "status": status,
        "items": items,
        "count": len(items),
        "valid_count": len(items),
        "latest_valid_receipt": latest,
        "latest_valid_receipt_id": _text(latest.get("receipt_id")),
        "export_authorization_approved": latest.get("decision") == "approved",
        "export_authorization_rejected": latest.get("decision") == "rejected",
        **_NO_EFFECT,
    }


def _receipt_fp(item: dict[str, Any]) -> str:
    return _fingerprint({key: value for key, value in item.items() if key != "receipt_fingerprint"})


def _read(path: Path) -> tuple[bool, dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, {}
    except (OSError, json.JSONDecodeError):
        return True, {}
    return True, value if isinstance(value, dict) else {}


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _sha(value: Any) -> bool:
    text = _text(value)
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _redacted(value: Any) -> str:
    return redact_secret_text(value).strip() if isinstance(value, str) else ""
