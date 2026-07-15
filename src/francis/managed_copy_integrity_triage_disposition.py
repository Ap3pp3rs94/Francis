from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_secret_text
from francis.managed_copy_integrity_evidence import managed_copy_integrity_evidence_readback
from francis.managed_copy_isolation import (
    latest_managed_copy_isolation_verification_for_provision,
    managed_copy_isolation_guarded_subpath,
)
from francis.managed_copy_provisioning import managed_copy_provision_for_copy

CONTRACT = "stage18_managed_copy_integrity_triage_disposition_v1"
RECEIPT_KIND = "francis.stage18.managed_copies.integrity_triage_disposition_receipt"
READBACK_KIND = "francis.stage18.managed_copies.integrity_triage_dispositions"
DISPOSITIONS = frozenset(
    {
        "investigation_required",
        "no_rogue_determination",
        "containment_authorization_required",
    }
)
_FIELDS = {
    "request_actor",
    "copy_id",
    "provisioning_receipt_id",
    "isolation_verification_receipt_id",
    "integrity_evidence_receipt_id",
    "integrity_evidence_fingerprint",
    "disposition",
    "rationale_fingerprint",
    "dry_run",
    "disposition_fingerprint",
    "confirm_integrity_triage_disposition",
}
_RECEIPT_FIELDS = {
    "ok",
    "kind",
    "contract",
    "receipt_id",
    "receipt_fingerprint",
    "status",
    "actor",
    "tenant_key",
    "copy_id",
    "provisioning_receipt_id",
    "provision_fingerprint",
    "isolation_verification_receipt_id",
    "isolation_verification_fingerprint",
    "integrity_evidence_receipt_id",
    "integrity_evidence_fingerprint",
    "integrity_scan_fingerprint",
    "disposition",
    "rationale_fingerprint",
    "disposition_fingerprint",
    "recorded_ts",
    "governance",
}
_NO_AUTHORITY = {
    "rogue_detected": False,
    "halts_copy": False,
    "quarantines_copy": False,
    "replaces_copy": False,
    "restores_copy": False,
    "uses_tools": False,
    "uses_shell": False,
    "uses_network": False,
    "writes_tenant_state": False,
    "starts_runtime": False,
    "incident_resolved": False,
    "grants_new_authority": False,
    "grants_execution_authority": False,
    "grants_mutation_authority": False,
}
_GOVERNANCE = {
    "operator_triage_disposition_only": True,
    "tenant_local_receipt": True,
    "contains_raw_rationale": False,
    "contains_raw_incident_material": False,
    "contains_raw_tenant_identity": False,
    "contains_credentials": False,
    **_NO_AUTHORITY,
}
_LOCK = threading.Lock()


def managed_copy_integrity_triage_disposition_plan(payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    safe_actor = _redacted(actor)[:240]
    request_actor = _redacted(payload.get("request_actor"))[:240]
    copy_id = _text(payload.get("copy_id"))
    provisioning_receipt_id = _text(payload.get("provisioning_receipt_id"))
    isolation_receipt_id = _text(payload.get("isolation_verification_receipt_id"))
    evidence_receipt_id = _text(payload.get("integrity_evidence_receipt_id"))
    evidence_fingerprint = _text(payload.get("integrity_evidence_fingerprint"))
    disposition = _text(payload.get("disposition"))
    rationale_fingerprint = _text(payload.get("rationale_fingerprint"))
    blockers: list[str] = []
    if set(payload) - _FIELDS:
        blockers.append("integrity_triage_disposition_unknown_fields")
    if not safe_actor or request_actor != safe_actor:
        blockers.append("integrity_triage_disposition_actor_lineage_mismatch")
    if type(payload.get("dry_run")) is not bool:
        blockers.append("integrity_triage_disposition_dry_run_boolean_required")
    if disposition not in DISPOSITIONS:
        blockers.append("integrity_triage_disposition_invalid")
    if not _sha(rationale_fingerprint):
        blockers.append("integrity_triage_disposition_rationale_fingerprint_invalid")
    if not _sha(evidence_fingerprint) or not evidence_receipt_id:
        blockers.append("integrity_triage_disposition_evidence_binding_invalid")

    evidence = managed_copy_integrity_evidence_readback(
        copy_id=copy_id,
        provisioning_receipt_id=provisioning_receipt_id,
        isolation_verification_receipt_id=isolation_receipt_id,
    )
    if (
        evidence.get("status") != "integrity_evidence_recorded"
        or evidence.get("valid_count", 0) < 1
        or evidence.get("latest_receipt_id") != evidence_receipt_id
        or evidence.get("latest_evidence_fingerprint") != evidence_fingerprint
    ):
        blockers.append("integrity_triage_disposition_evidence_not_current_valid")
    if evidence.get("triage_required") is not True or evidence.get("live_drift_matches_latest") is not True:
        blockers.append("integrity_triage_disposition_active_drift_required")

    provision = managed_copy_provision_for_copy(copy_id, provisioning_receipt_id=provisioning_receipt_id)
    isolation = (
        latest_managed_copy_isolation_verification_for_provision(
            provisioning_receipt_id,
            provision_fingerprint=_text(provision.get("provision_fingerprint")),
            copy_id=copy_id,
        )
        if provision
        else {}
    )
    if (
        not provision
        or not isolation
        or provision.get("copy_id") != copy_id
        or isolation.get("copy_id") != copy_id
        or provision.get("receipt_id") != provisioning_receipt_id
        or isolation.get("provisioning_receipt_id") != provisioning_receipt_id
        or isolation.get("receipt_id") != isolation_receipt_id
        or provision.get("tenant_key") != isolation.get("tenant_key")
    ):
        blockers.append("integrity_triage_disposition_lineage_invalid")

    binding = {
        "contract": CONTRACT,
        "actor": safe_actor,
        "tenant_key": _text(provision.get("tenant_key")),
        "copy_id": copy_id,
        "provisioning_receipt_id": provisioning_receipt_id,
        "provision_fingerprint": _text(provision.get("provision_fingerprint")),
        "isolation_verification_receipt_id": isolation_receipt_id,
        "isolation_verification_fingerprint": _text(isolation.get("verification_fingerprint")),
        "integrity_evidence_receipt_id": evidence_receipt_id,
        "integrity_evidence_fingerprint": evidence_fingerprint,
        "integrity_scan_fingerprint": _text(evidence.get("items", [{}])[-1].get("scan_fingerprint"))
        if evidence.get("items")
        else "",
        "disposition": disposition,
        "rationale_fingerprint": rationale_fingerprint,
    }
    disposition_fingerprint = _fingerprint(binding) if not blockers else ""
    return {
        "ok": not blockers,
        "kind": "francis.stage18.managed_copies.integrity_triage_disposition_plan",
        "contract": CONTRACT,
        "status": "integrity_triage_disposition_ready" if not blockers else "blocked",
        **binding,
        "disposition_fingerprint": disposition_fingerprint,
        "blockers": blockers,
        "dry_run": payload.get("dry_run") is True,
        "writes_receipt": False,
        **_NO_AUTHORITY,
    }


def record_managed_copy_integrity_triage_disposition(
    plan: dict[str, Any], *, provided_fingerprint: str, confirmed: bool
) -> dict[str, Any]:
    if confirmed is not True:
        return _blocked("integrity_triage_disposition_confirmation_required")
    expected = _text(plan.get("disposition_fingerprint"))
    if not expected or expected != _text(provided_fingerprint):
        return _blocked("integrity_triage_disposition_fingerprint_mismatch")
    with _LOCK:
        payload = {
            "request_actor": plan.get("actor"),
            "copy_id": plan.get("copy_id"),
            "provisioning_receipt_id": plan.get("provisioning_receipt_id"),
            "isolation_verification_receipt_id": plan.get("isolation_verification_receipt_id"),
            "integrity_evidence_receipt_id": plan.get("integrity_evidence_receipt_id"),
            "integrity_evidence_fingerprint": plan.get("integrity_evidence_fingerprint"),
            "disposition": plan.get("disposition"),
            "rationale_fingerprint": plan.get("rationale_fingerprint"),
            "dry_run": False,
        }
        current = managed_copy_integrity_triage_disposition_plan(payload, actor=_text(plan.get("actor")))
        if not current.get("ok") or current.get("disposition_fingerprint") != expected:
            return _blocked("integrity_triage_disposition_live_state_changed")
        directory, provision, isolation = _directory(current, create=True)
        if directory is None:
            return _blocked("integrity_triage_disposition_path_invalid")
        path = directory / f"{expected[:16]}.json"
        exists, existing = _read(path)
        if exists:
            if _valid(existing, path, directory, provision=provision, isolation=isolation):
                return _recorded(existing, writes=False)
            return _blocked("integrity_triage_disposition_receipt_conflict")
        receipt = {
            "ok": True,
            "kind": RECEIPT_KIND,
            "contract": CONTRACT,
            "receipt_id": f"managed_copy_integrity_triage_disposition_{expected[:16]}",
            "receipt_fingerprint": "",
            "status": "integrity_triage_disposition_recorded",
            **{key: current[key] for key in _BINDING_FIELDS},
            "disposition_fingerprint": expected,
            "recorded_ts": int(time.time()),
            "governance": dict(_GOVERNANCE),
        }
        receipt["receipt_fingerprint"] = _receipt_fingerprint(receipt)
        if not _valid(receipt, path, directory, provision=provision, isolation=isolation):
            return _blocked("integrity_triage_disposition_receipt_invalid")
        try:
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        except OSError:
            return _blocked("integrity_triage_disposition_write_failed")
    return _recorded(receipt, writes=True)


def managed_copy_integrity_triage_dispositions_readback(
    *, copy_id: str, provisioning_receipt_id: str, isolation_verification_receipt_id: str, limit: int = 20
) -> dict[str, Any]:
    request = {
        "copy_id": _text(copy_id),
        "provisioning_receipt_id": _text(provisioning_receipt_id),
        "isolation_verification_receipt_id": _text(isolation_verification_receipt_id),
    }
    directory, provision, isolation = _directory(request, create=False)
    items: list[dict[str, Any]] = []
    invalid_count = 0
    if directory and directory.is_dir():
        for path in sorted(directory.glob("*.json")):
            exists, item = _read(path)
            if exists and _valid(item, path, directory, provision=provision, isolation=isolation):
                items.append(item)
            elif exists:
                invalid_count += 1
    items.sort(key=lambda item: (int(item["recorded_ts"]), _text(item.get("receipt_id"))))
    bounded = items[-max(1, min(int(limit), 500)) :]
    latest = bounded[-1] if bounded else {}
    return {
        "ok": invalid_count == 0,
        "kind": READBACK_KIND,
        "status": "integrity_triage_disposition_recorded" if bounded else "empty",
        "items": [_readback_item(item) for item in bounded],
        "count": len(bounded),
        "valid_count": len(bounded),
        "invalid_receipt_count": invalid_count,
        "latest_receipt_id": _text(latest.get("receipt_id")),
        "latest_disposition": _text(latest.get("disposition")),
        "latest_disposition_fingerprint": _text(latest.get("disposition_fingerprint")),
        "latest_integrity_evidence_receipt_id": _text(latest.get("integrity_evidence_receipt_id")),
        "rogue_recovery_ready": False,
        "writes_receipts": False,
        **_NO_AUTHORITY,
    }


_BINDING_FIELDS = (
    "actor",
    "tenant_key",
    "copy_id",
    "provisioning_receipt_id",
    "provision_fingerprint",
    "isolation_verification_receipt_id",
    "isolation_verification_fingerprint",
    "integrity_evidence_receipt_id",
    "integrity_evidence_fingerprint",
    "integrity_scan_fingerprint",
    "disposition",
    "rationale_fingerprint",
)


def _directory(request: dict[str, Any], *, create: bool) -> tuple[Path | None, dict[str, Any], dict[str, Any]]:
    provision = managed_copy_provision_for_copy(
        _text(request.get("copy_id")),
        provisioning_receipt_id=_text(request.get("provisioning_receipt_id")),
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
    if _text(isolation.get("receipt_id")) != _text(request.get("isolation_verification_receipt_id")):
        return None, provision, isolation
    return (
        managed_copy_isolation_guarded_subpath(
            provision,
            isolation,
            domain="tenant_receipts",
            relative_parts=("rtd",),
            create_leaf_directory=create,
            require_live=False,
        ),
        provision,
        isolation,
    )


def _valid(
    item: dict[str, Any],
    path: Path,
    directory: Path,
    *,
    provision: dict[str, Any],
    isolation: dict[str, Any],
) -> bool:
    disposition_fingerprint = _text(item.get("disposition_fingerprint"))
    evidence = managed_copy_integrity_evidence_readback(
        copy_id=_text(item.get("copy_id")),
        provisioning_receipt_id=_text(item.get("provisioning_receipt_id")),
        isolation_verification_receipt_id=_text(item.get("isolation_verification_receipt_id")),
    )
    binding = {"contract": item.get("contract"), **{key: item.get(key) for key in _BINDING_FIELDS}}
    return bool(
        set(item) == _RECEIPT_FIELDS
        and item.get("ok") is True
        and item.get("kind") == RECEIPT_KIND
        and item.get("contract") == CONTRACT
        and item.get("status") == "integrity_triage_disposition_recorded"
        and item.get("receipt_id") == f"managed_copy_integrity_triage_disposition_{disposition_fingerprint[:16]}"
        and item.get("actor") == _redacted(item.get("actor"))[:240]
        and bool(item.get("actor"))
        and item.get("tenant_key") == provision.get("tenant_key") == isolation.get("tenant_key")
        and item.get("copy_id") == provision.get("copy_id") == isolation.get("copy_id")
        and item.get("provisioning_receipt_id") == provision.get("receipt_id")
        and item.get("provisioning_receipt_id") == isolation.get("provisioning_receipt_id")
        and item.get("provision_fingerprint") == provision.get("provision_fingerprint")
        and item.get("isolation_verification_receipt_id") == isolation.get("receipt_id")
        and item.get("isolation_verification_fingerprint") == isolation.get("verification_fingerprint")
        and evidence.get("status") == "integrity_evidence_recorded"
        and evidence.get("valid_count", 0) >= 1
        and any(
            evidence_item.get("receipt_id") == item.get("integrity_evidence_receipt_id")
            and evidence_item.get("evidence_fingerprint") == item.get("integrity_evidence_fingerprint")
            and evidence_item.get("scan_fingerprint") == item.get("integrity_scan_fingerprint")
            for evidence_item in evidence.get("items", [])
        )
        and item.get("disposition") in DISPOSITIONS
        and _sha(item.get("rationale_fingerprint"))
        and _sha(disposition_fingerprint)
        and disposition_fingerprint == _fingerprint(binding)
        and item.get("governance") == _GOVERNANCE
        and item.get("receipt_fingerprint") == _receipt_fingerprint(item)
        and type(item.get("recorded_ts")) is int
        and item.get("recorded_ts", 0) > 0
        and path == directory / f"{disposition_fingerprint[:16]}.json"
    )


def _readback_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item[key]
        for key in (
            "receipt_id",
            "receipt_fingerprint",
            "copy_id",
            "provisioning_receipt_id",
            "isolation_verification_receipt_id",
            "integrity_evidence_receipt_id",
            "integrity_evidence_fingerprint",
            "integrity_scan_fingerprint",
            "disposition",
            "rationale_fingerprint",
            "disposition_fingerprint",
            "recorded_ts",
        )
    }


def _recorded(receipt: dict[str, Any], *, writes: bool) -> dict[str, Any]:
    return {
        "ok": True,
        "status": "integrity_triage_disposition_recorded",
        "receipt": receipt,
        "receipt_id": _text(receipt.get("receipt_id")),
        "disposition": _text(receipt.get("disposition")),
        "writes_receipt": writes,
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
    return _fingerprint({key: value for key, value in item.items() if key != "receipt_fingerprint"})


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _sha(value: Any) -> bool:
    text = _text(value)
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _redacted(value: Any) -> str:
    return redact_secret_text(value).strip() if isinstance(value, str) else ""
