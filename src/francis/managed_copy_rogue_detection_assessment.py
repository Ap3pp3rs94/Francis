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

CONTRACT = "stage18_managed_copy_rogue_detection_assessment_v1"
RECEIPT_KIND = "francis.stage18.managed_copies.rogue_detection_assessment_receipt"
READBACK_KIND = "francis.stage18.managed_copies.rogue_detection_assessments"
_FIELDS = {
    "request_actor",
    "copy_id",
    "provisioning_receipt_id",
    "isolation_verification_receipt_id",
    "signal_id",
    "severity",
    "incident_fingerprint",
    "evidence_reference_hashes",
    "evidence_reference_count",
    "dry_run",
    "assessment_fingerprint",
    "confirm_rogue_signal_assessment",
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
    "isolation_verification_receipt_id",
    "provision_fingerprint",
    "isolation_fingerprint",
    "signal_id",
    "severity",
    "incident_fingerprint",
    "evidence_reference_hashes",
    "evidence_reference_count",
    "assessment_fingerprint",
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
    "grants_execution_authority": False,
    "grants_mutation_authority": False,
}
_GOVERNANCE = {
    "assessment_only": True,
    "contains_raw_incident_material": False,
    "contains_raw_tenant_identity": False,
    "contains_credentials": False,
    **_NO_AUTHORITY,
}
_LOCK = threading.Lock()


def managed_copy_rogue_detection_assessment_plan(payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    safe_actor = _redacted(actor)[:240]
    request_actor = _redacted(payload.get("request_actor"))[:240]
    unknown = sorted(set(payload) - _FIELDS)
    evidence = payload.get("evidence_reference_hashes")
    refs = list(evidence) if isinstance(evidence, list) else []
    count = payload.get("evidence_reference_count")
    bounded = {
        key: _text(payload.get(key))
        for key in (
            "copy_id",
            "provisioning_receipt_id",
            "isolation_verification_receipt_id",
            "signal_id",
            "severity",
            "incident_fingerprint",
        )
    }
    blockers: list[str] = []
    if unknown:
        blockers.append("rogue_detection_assessment_unknown_fields")
    if not safe_actor or request_actor != safe_actor:
        blockers.append("rogue_detection_assessment_actor_lineage_mismatch")
    if payload.get("dry_run") is not True and payload.get("dry_run") is not False:
        blockers.append("rogue_detection_assessment_dry_run_boolean_required")
    if type(count) is not int or count != len(refs) or not 1 <= count <= 16:
        blockers.append("rogue_detection_assessment_evidence_count_invalid")
    if len(refs) != len(set(refs)) or any(not _sha(item) for item in refs):
        blockers.append("rogue_detection_assessment_evidence_references_invalid")
    if not _sha(bounded["incident_fingerprint"]):
        blockers.append("rogue_detection_assessment_incident_fingerprint_invalid")
    signals = {item["id"]: item["severity"] for item in _signal_catalog()}
    if signals.get(bounded["signal_id"]) != bounded["severity"]:
        blockers.append("rogue_detection_assessment_signal_invalid")
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
        blockers.append("rogue_detection_assessment_live_lineage_required")
    tenant_key = _text(provision.get("tenant_key"))
    binding = {
        "contract": CONTRACT,
        "actor": safe_actor,
        **bounded,
        "tenant_key": tenant_key,
        "provision_fingerprint": _text(provision.get("provision_fingerprint")),
        "isolation_fingerprint": _text(isolation.get("verification_fingerprint")),
        "evidence_reference_hashes": refs,
        "evidence_reference_count": count,
    }
    fingerprint = _fingerprint(binding) if not blockers else ""
    return {
        "ok": not blockers,
        "status": "rogue_signal_assessed" if not blockers else "blocked",
        "contract": CONTRACT,
        "actor": safe_actor,
        "assessment": {**bounded, "evidence_reference_hashes": refs, "evidence_reference_count": count},
        "tenant_key": tenant_key,
        "provision_fingerprint": _text(provision.get("provision_fingerprint")),
        "isolation_fingerprint": _text(isolation.get("verification_fingerprint")),
        "assessment_fingerprint": fingerprint,
        "blockers": blockers,
        "dry_run": payload.get("dry_run") is True,
        "writes_receipt": False,
        **_NO_AUTHORITY,
    }


def record_managed_copy_rogue_detection_assessment(
    plan: dict[str, Any], *, provided_fingerprint: str, confirmed: bool
) -> dict[str, Any]:
    raw = plan.get("assessment")
    assessment: dict[str, Any] = dict(raw) if isinstance(raw, dict) else {}
    replanned = managed_copy_rogue_detection_assessment_plan(
        {**assessment, "request_actor": _text(plan.get("actor")), "dry_run": False}, actor=_text(plan.get("actor"))
    )
    expected = _text(replanned.get("assessment_fingerprint"))
    if not replanned.get("ok") or expected != _text(plan.get("assessment_fingerprint")):
        return _blocked("rogue_detection_assessment_plan_drift")
    if not confirmed:
        return _blocked("rogue_detection_assessment_confirmation_required")
    if not expected or expected != _text(provided_fingerprint):
        return _blocked("rogue_detection_assessment_fingerprint_mismatch")
    directory = _directory(assessment, create=True)
    if directory is None:
        return _blocked("rogue_detection_assessment_path_invalid")
    with _LOCK:
        final = managed_copy_rogue_detection_assessment_plan(
            {**assessment, "request_actor": _text(plan.get("actor")), "dry_run": False}, actor=_text(plan.get("actor"))
        )
        final_fp = _text(final.get("assessment_fingerprint"))
        if not final.get("ok") or final_fp != expected or final_fp != _text(provided_fingerprint):
            return _blocked("rogue_detection_assessment_plan_drift")
        path = directory / f"{final_fp[:16]}.json"
        present, existing = _read(path)
        if present:
            if _valid(existing, path, directory) and existing.get("assessment_fingerprint") == final_fp:
                return _recorded(existing, False)
            return _blocked("rogue_detection_assessment_receipt_conflict")
        receipt = {
            "ok": True,
            "kind": RECEIPT_KIND,
            "contract": CONTRACT,
            "receipt_id": f"managed_copy_rogue_detection_assessment_{final_fp[:16]}",
            "receipt_fingerprint": "",
            "status": "rogue_signal_assessed",
            "actor": _text(final.get("actor")),
            "tenant_key": _text(final.get("tenant_key")),
            **assessment,
            "provision_fingerprint": _text(final.get("provision_fingerprint")),
            "isolation_fingerprint": _text(final.get("isolation_fingerprint")),
            "assessment_fingerprint": final_fp,
            "recorded_ts": int(time.time()),
            "governance": dict(_GOVERNANCE),
        }
        receipt["receipt_fingerprint"] = _receipt_fp(receipt)
        if not _valid(receipt, path, directory):
            return _blocked("rogue_detection_assessment_receipt_invalid")
        try:
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        except OSError:
            return _blocked("rogue_detection_assessment_write_failed")
    return _recorded(receipt, True)


def managed_copy_rogue_detection_assessments_readback(
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
        payload.update(request_actor=item.get("actor"), dry_run=True)
        live = managed_copy_rogue_detection_assessment_plan(payload, actor=_text(item.get("actor")))
        if _valid(item, path, directory) and live.get("assessment_fingerprint") == item.get("assessment_fingerprint"):
            valid.append(item)
    valid.sort(key=lambda item: (int(item["recorded_ts"]), _text(item.get("receipt_id"))))
    return _readback(valid[-max(1, min(int(limit), 500)) :], "rogue_signal_assessed" if valid else "invalid_or_drifted")


def _signal_catalog() -> list[dict[str, Any]]:
    from francis.managed_copies import managed_copy_rogue_recovery_contract_snapshot

    value = managed_copy_rogue_recovery_contract_snapshot().get("detection_signals")
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


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
        relative_parts=("rz",),
        create_leaf_directory=create,
        require_live=True,
    )


def _valid(item: dict[str, Any], path: Path, directory: Path) -> bool:
    fp = _text(item.get("assessment_fingerprint"))
    actor = _text(item.get("actor"))
    return bool(
        set(item) == _RECEIPT_FIELDS
        and item.get("ok") is True
        and item.get("kind") == RECEIPT_KIND
        and item.get("contract") == CONTRACT
        and item.get("status") == "rogue_signal_assessed"
        and item.get("receipt_id") == f"managed_copy_rogue_detection_assessment_{fp[:16]}"
        and actor
        and len(actor) <= 240
        and actor == _redacted(actor)[:240]
        and all(
            _sha(item.get(key))
            for key in (
                "tenant_key",
                "provision_fingerprint",
                "isolation_fingerprint",
                "incident_fingerprint",
                "assessment_fingerprint",
                "receipt_fingerprint",
            )
        )
        and isinstance(item.get("evidence_reference_hashes"), list)
        and type(item.get("evidence_reference_count")) is int
        and item.get("evidence_reference_count") == len(item["evidence_reference_hashes"])
        and 1 <= item["evidence_reference_count"] <= 16
        and len(item["evidence_reference_hashes"]) == len(set(item["evidence_reference_hashes"]))
        and all(_sha(value) for value in item["evidence_reference_hashes"])
        and item.get("governance") == _GOVERNANCE
        and item.get("receipt_fingerprint") == _receipt_fp(item)
        and isinstance(item.get("recorded_ts"), int)
        and not isinstance(item.get("recorded_ts"), bool)
        and path == directory / f"{fp[:16]}.json"
    )


def _recorded(receipt: dict[str, Any], writes: bool) -> dict[str, Any]:
    return {
        "ok": True,
        "status": "rogue_signal_assessed",
        "error": "",
        "receipt": receipt,
        "receipt_id": _text(receipt.get("receipt_id")),
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


def _readback(items: list[dict[str, Any]], status: str) -> dict[str, Any]:
    return {
        "ok": True,
        "kind": READBACK_KIND,
        "status": status,
        "items": items,
        "count": len(items),
        "valid_count": len(items),
        "rogue_signal_assessed": bool(items),
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


def _receipt_fp(item: dict[str, Any]) -> str:
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
