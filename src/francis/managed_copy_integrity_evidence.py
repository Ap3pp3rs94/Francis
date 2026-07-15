from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

from francis.managed_copy_integrity_scan import managed_copy_integrity_finding_is_valid, managed_copy_integrity_scan
from francis.managed_copy_isolation import (
    latest_managed_copy_isolation_verification_for_provision,
    managed_copy_isolation_guarded_subpath,
)
from francis.managed_copy_provisioning import managed_copy_provision_for_copy

CONTRACT = "stage18_managed_copy_integrity_evidence_v1"
RECEIPT_KIND = "francis.stage18.managed_copies.integrity_evidence_receipt"
READBACK_KIND = "francis.stage18.managed_copies.integrity_evidence"
_FIELDS = {
    "request_actor",
    "copy_id",
    "provisioning_receipt_id",
    "isolation_verification_receipt_id",
    "dry_run",
    "evidence_fingerprint",
    "confirm_integrity_evidence",
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
    "scan_fingerprint",
    "findings",
    "finding_count",
    "evidence_fingerprint",
    "recorded_ts",
    "governance",
}
_NO_AUTHORITY = {
    "rogue_detected": False,
    "halts_copy": False,
    "quarantines_copy": False,
    "replaces_copy": False,
    "restores_copy": False,
    "writes_tenant_state": False,
    "uses_tools": False,
    "uses_shell": False,
    "uses_network": False,
    "grants_execution_authority": False,
    "grants_mutation_authority": False,
}
_GOVERNANCE = {
    "derived_live_integrity_evidence_only": True,
    "contains_raw_tenant_content": False,
    "contains_resolved_paths": False,
    "tenant_local_receipt": True,
    **_NO_AUTHORITY,
}
_LOCK = threading.Lock()


def managed_copy_integrity_evidence_plan(payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    scan_payload = {
        key: payload.get(key)
        for key in ("request_actor", "copy_id", "provisioning_receipt_id", "isolation_verification_receipt_id")
    }
    scan = managed_copy_integrity_scan(scan_payload, actor=actor)
    blockers: list[str] = []
    if set(payload) - _FIELDS:
        blockers.append("integrity_evidence_unknown_fields")
    if type(payload.get("dry_run")) is not bool:
        blockers.append("integrity_evidence_dry_run_boolean_required")
    if scan.get("status") != "integrity_drift_detected" or scan.get("finding_count", 0) < 1:
        blockers.append("integrity_evidence_live_drift_required")
    provision = managed_copy_provision_for_copy(
        _text(payload.get("copy_id")),
        provisioning_receipt_id=_text(payload.get("provisioning_receipt_id")),
    )
    isolation = (
        latest_managed_copy_isolation_verification_for_provision(
            _text(payload.get("provisioning_receipt_id")),
            provision_fingerprint=_text(provision.get("provision_fingerprint")),
            copy_id=_text(payload.get("copy_id")),
        )
        if provision
        else {}
    )
    tenant_key = _text(provision.get("tenant_key"))
    binding = {
        "contract": CONTRACT,
        "actor": _text(scan.get("actor")),
        "tenant_key": tenant_key,
        "copy_id": _text(scan.get("copy_id")),
        "provisioning_receipt_id": _text(scan.get("provisioning_receipt_id")),
        "provision_fingerprint": _text(provision.get("provision_fingerprint")),
        "isolation_verification_receipt_id": _text(scan.get("isolation_verification_receipt_id")),
        "isolation_verification_fingerprint": _text(isolation.get("verification_fingerprint")),
        "scan_fingerprint": _text(scan.get("scan_fingerprint")),
        "findings": list(scan.get("findings") or []),
        "finding_count": int(scan.get("finding_count") or 0),
    }
    evidence_fingerprint = _fingerprint(binding) if not blockers else ""
    return {
        "ok": not blockers,
        "kind": "francis.stage18.managed_copies.integrity_evidence_plan",
        "contract": CONTRACT,
        "status": "integrity_evidence_ready" if not blockers else "blocked",
        **binding,
        "evidence_fingerprint": evidence_fingerprint,
        "blockers": blockers,
        "dry_run": payload.get("dry_run") is True,
        "writes_receipt": False,
        **_NO_AUTHORITY,
    }


def record_managed_copy_integrity_evidence(
    plan: dict[str, Any], *, provided_fingerprint: str, confirmed: bool
) -> dict[str, Any]:
    if not confirmed:
        return _blocked("integrity_evidence_confirmation_required")
    expected = _text(plan.get("evidence_fingerprint"))
    if not expected or expected != _text(provided_fingerprint):
        return _blocked("integrity_evidence_fingerprint_mismatch")
    with _LOCK:
        payload = {
            "request_actor": plan.get("actor"),
            "copy_id": plan.get("copy_id"),
            "provisioning_receipt_id": plan.get("provisioning_receipt_id"),
            "isolation_verification_receipt_id": plan.get("isolation_verification_receipt_id"),
            "dry_run": False,
        }
        current = managed_copy_integrity_evidence_plan(payload, actor=_text(plan.get("actor")))
        if not current.get("ok") or current.get("evidence_fingerprint") != expected:
            return _blocked("integrity_evidence_live_state_changed")
        # Drift invalidates live access, but preserving its evidence still uses
        # the exact provision/isolation lineage and the contained receipts domain.
        directory, provision, isolation = _directory(current, create=True, require_live=False)
        if directory is None:
            return _blocked("integrity_evidence_path_invalid")
        path = directory / f"{expected[:16]}.json"
        existing = _read(path)
        if existing:
            if (
                _valid(existing, path, directory, provision=provision, isolation=isolation)
                and existing.get("evidence_fingerprint") == expected
            ):
                return _recorded(existing, writes=False)
            return _blocked("integrity_evidence_receipt_conflict")
        receipt = {
            "ok": True,
            "kind": RECEIPT_KIND,
            "contract": CONTRACT,
            "receipt_id": f"managed_copy_integrity_evidence_{expected[:16]}",
            "receipt_fingerprint": "",
            "status": "integrity_evidence_recorded",
            "actor": _text(current.get("actor")),
            "tenant_key": _text(current.get("tenant_key")),
            "copy_id": _text(current.get("copy_id")),
            "provisioning_receipt_id": _text(current.get("provisioning_receipt_id")),
            "provision_fingerprint": _text(current.get("provision_fingerprint")),
            "isolation_verification_receipt_id": _text(current.get("isolation_verification_receipt_id")),
            "isolation_verification_fingerprint": _text(current.get("isolation_verification_fingerprint")),
            "scan_fingerprint": _text(current.get("scan_fingerprint")),
            "findings": list(current.get("findings") or []),
            "finding_count": int(current.get("finding_count") or 0),
            "evidence_fingerprint": expected,
            "recorded_ts": int(time.time()),
            "governance": dict(_GOVERNANCE),
        }
        receipt["receipt_fingerprint"] = _receipt_fingerprint(receipt)
        if not _valid(receipt, path, directory, provision=provision, isolation=isolation):
            return _blocked("integrity_evidence_receipt_invalid")
        try:
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        except OSError:
            return _blocked("integrity_evidence_write_failed")
    return _recorded(receipt, writes=True)


def managed_copy_integrity_evidence_readback(
    *,
    copy_id: str,
    provisioning_receipt_id: str,
    isolation_verification_receipt_id: str,
    limit: int = 20,
) -> dict[str, Any]:
    request = {
        "copy_id": _text(copy_id),
        "provisioning_receipt_id": _text(provisioning_receipt_id),
        "isolation_verification_receipt_id": _text(isolation_verification_receipt_id),
    }
    directory, provision, isolation = _directory(request, create=False, require_live=False)
    items: list[dict[str, Any]] = []
    if directory and directory.is_dir():
        for path in sorted(directory.glob("*.json")):
            item = _read(path)
            if _valid(item, path, directory, provision=provision, isolation=isolation):
                items.append(item)
    items.sort(key=lambda item: (int(item["recorded_ts"]), _text(item.get("receipt_id"))))
    bounded = items[-max(1, min(int(limit), 500)) :]
    latest = bounded[-1] if bounded else {}
    live = (
        managed_copy_integrity_scan({"request_actor": latest.get("actor"), **request}, actor=_text(latest.get("actor")))
        if latest
        else {}
    )
    live_drift_matches_latest = bool(
        latest
        and live.get("status") == "integrity_drift_detected"
        and live.get("scan_fingerprint") == latest.get("scan_fingerprint")
    )
    incident_state = "active_drift" if live_drift_matches_latest else "historical_or_changed" if bounded else "empty"
    return {
        "ok": True,
        "kind": READBACK_KIND,
        "status": "integrity_evidence_recorded" if bounded else "empty",
        "items": [_readback_item(item) for item in bounded],
        "count": len(bounded),
        "valid_count": len(bounded),
        "latest_receipt_id": _text(latest.get("receipt_id")),
        "latest_evidence_fingerprint": _text(latest.get("evidence_fingerprint")),
        "live_drift_matches_latest": live_drift_matches_latest,
        "integrity_incident_state": incident_state,
        "triage_required": live_drift_matches_latest,
        "highest_severity": "high" if live_drift_matches_latest else "",
        "latest_finding_count": int(latest.get("finding_count") or 0) if latest else 0,
        "latest_evidence_recorded_ts": int(latest.get("recorded_ts") or 0) if latest else 0,
        "incident_opened": False,
        "incident_resolved": False,
        "writes_receipts": False,
        **_NO_AUTHORITY,
    }


def _directory(
    request: dict[str, Any], *, create: bool, require_live: bool
) -> tuple[Path | None, dict[str, Any], dict[str, Any]]:
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
    if _text(isolation.get("receipt_id")) != _text(request.get("isolation_verification_receipt_id")):
        return None, provision, isolation
    return (
        managed_copy_isolation_guarded_subpath(
            provision,
            isolation,
            domain="tenant_receipts",
            relative_parts=("ri",),
            create_leaf_directory=create,
            require_live=require_live,
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
    evidence_fingerprint = _text(item.get("evidence_fingerprint"))
    evidence_binding = {
        "contract": item.get("contract"),
        "actor": item.get("actor"),
        "tenant_key": item.get("tenant_key"),
        "copy_id": item.get("copy_id"),
        "provisioning_receipt_id": item.get("provisioning_receipt_id"),
        "provision_fingerprint": item.get("provision_fingerprint"),
        "isolation_verification_receipt_id": item.get("isolation_verification_receipt_id"),
        "isolation_verification_fingerprint": item.get("isolation_verification_fingerprint"),
        "scan_fingerprint": item.get("scan_fingerprint"),
        "findings": item.get("findings"),
        "finding_count": item.get("finding_count"),
    }
    return bool(
        set(item) == _RECEIPT_FIELDS
        and item.get("ok") is True
        and item.get("kind") == RECEIPT_KIND
        and item.get("contract") == CONTRACT
        and item.get("status") == "integrity_evidence_recorded"
        and item.get("receipt_id") == f"managed_copy_integrity_evidence_{evidence_fingerprint[:16]}"
        and _sha(item.get("tenant_key"))
        and item.get("tenant_key") == provision.get("tenant_key")
        and item.get("tenant_key") == isolation.get("tenant_key")
        and _text(item.get("actor"))
        and _text(item.get("copy_id"))
        and item.get("copy_id") == provision.get("copy_id")
        and item.get("copy_id") == isolation.get("copy_id")
        and _text(item.get("provisioning_receipt_id"))
        and item.get("provisioning_receipt_id") == provision.get("receipt_id")
        and item.get("provisioning_receipt_id") == isolation.get("provisioning_receipt_id")
        and item.get("provision_fingerprint") == provision.get("provision_fingerprint")
        and _text(item.get("isolation_verification_receipt_id"))
        and item.get("isolation_verification_receipt_id") == isolation.get("receipt_id")
        and item.get("isolation_verification_fingerprint") == isolation.get("verification_fingerprint")
        and _sha(item.get("scan_fingerprint"))
        and _sha(evidence_fingerprint)
        and evidence_fingerprint == _fingerprint(evidence_binding)
        and _valid_findings(item.get("findings"))
        and _matches_positive_count(item.get("finding_count"), len(item["findings"]))
        and item.get("governance") == _GOVERNANCE
        and item.get("receipt_fingerprint") == _receipt_fingerprint(item)
        and _positive_exact_int(item.get("recorded_ts"))
        and path == directory / f"{evidence_fingerprint[:16]}.json"
    )


def _valid_findings(value: Any) -> bool:
    return (
        isinstance(value, list) and bool(value) and all(managed_copy_integrity_finding_is_valid(item) for item in value)
    )


def _readback_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item[key]
        for key in (
            "receipt_id",
            "receipt_fingerprint",
            "copy_id",
            "provisioning_receipt_id",
            "provision_fingerprint",
            "isolation_verification_receipt_id",
            "isolation_verification_fingerprint",
            "scan_fingerprint",
            "finding_count",
            "evidence_fingerprint",
            "recorded_ts",
        )
    }


def _matches_positive_count(value: Any, expected: int) -> bool:
    return type(value) is int and value > 0 and value == expected


def _positive_exact_int(value: Any) -> bool:
    return type(value) is int and value > 0


def _recorded(receipt: dict[str, Any], *, writes: bool) -> dict[str, Any]:
    return {
        "ok": True,
        "status": "integrity_evidence_recorded",
        "receipt": receipt,
        "receipt_id": _text(receipt.get("receipt_id")),
        "writes_receipt": writes,
        **_NO_AUTHORITY,
    }


def _blocked(error: str) -> dict[str, Any]:
    return {"ok": False, "status": "blocked", "error": error, "writes_receipt": False, **_NO_AUTHORITY}


def _receipt_fingerprint(item: dict[str, Any]) -> str:
    return _fingerprint({key: value for key, value in item.items() if key != "receipt_fingerprint"})


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _sha(value: Any) -> bool:
    text = _text(value)
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
