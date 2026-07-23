from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from francis.managed_copy_isolation import (
    latest_managed_copy_isolation_verification_for_provision,
    managed_copy_isolation_guarded_subpath,
)
from francis.managed_copy_provisioning import managed_copy_provision_for_copy
from francis.managed_copy_safe_delta_export_artifact_plan import (
    MEDIA_TYPE,
    SCHEMA_CLASS,
    managed_copy_safe_delta_export_artifact_plan as build_artifact_plan,
)

CONTRACT = "stage18_managed_copy_safe_delta_export_artifact_v1"
ARTIFACT_KIND = "francis.stage18.managed_copies.safe_delta_export_artifact"
RECEIPT_KIND = "francis.stage18.managed_copies.safe_delta_export_artifact_receipt"
READBACK_KIND = "francis.stage18.managed_copies.safe_delta_export_artifacts"
SIGNAL_CLASS = "approved_non_private_signal"
ARTIFACT_FIELDS = {
    "kind",
    "contract",
    "artifact_media_type",
    "artifact_schema_class",
    "signal_class",
    "review_fingerprint",
    "authorization_decision_fingerprint",
    "artifact_plan_fingerprint",
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
    "copy_id",
    "provisioning_receipt_id",
    "provisioning_receipt_fingerprint",
    "isolation_verification_receipt_id",
    "isolation_verification_receipt_fingerprint",
    "review_fingerprint",
    "preflight_fingerprint",
    "request_fingerprint",
    "authorization_decision_receipt_id",
    "authorization_decision_receipt_fingerprint",
    "authorization_decision_fingerprint",
    "artifact_plan_fingerprint",
    "artifact_filename",
    "artifact_byte_count",
    "artifact_content_fingerprint",
    "recorded_ts",
    "governance",
}
GOVERNANCE = {
    "metadata_only": True,
    "artifact_count": 1,
    "writes_tenant_state": False,
    "writes_learning": False,
    "uses_network": False,
    "uses_destination": False,
    "uses_connector": False,
    "imports_artifact": False,
    "grants_authority": False,
    "invokes_runtime": False,
}
_INPUT_FIELDS = {
    "request_actor",
    "copy_id",
    "provisioning_receipt_id",
    "isolation_verification_receipt_id",
    "review_fingerprint",
    "preflight_fingerprint",
    "request_fingerprint",
    "authorization_decision_receipt_id",
    "authorization_decision_fingerprint",
    "artifact_media_type",
    "artifact_schema_class",
    "retention_class",
    "artifact_count",
    "dry_run",
    "artifact_plan_fingerprint",
    "confirm_export_artifact",
}
_LOCK = threading.Lock()


def managed_copy_safe_delta_export_artifact_plan(payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    unknown = sorted(set(payload) - _INPUT_FIELDS)
    plan_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"artifact_plan_fingerprint", "confirm_export_artifact"}
    }
    plan_payload["dry_run"] = True
    plan = build_artifact_plan(plan_payload, actor=actor)
    blockers = list(plan.get("blockers", []))
    if unknown:
        blockers.append("safe_delta_export_artifact_unknown_fields")
    provided = _text(payload.get("artifact_plan_fingerprint"))
    expected = _text(plan.get("artifact_plan_fingerprint"))
    if not expected or provided != expected:
        blockers.append("safe_delta_export_artifact_plan_fingerprint_mismatch")
    artifact = _artifact(plan) if not blockers else {}
    return {
        "ok": not blockers,
        "status": "export_artifact_ready" if not blockers else "blocked",
        "error": "" if not blockers else "safe_delta_export_artifact_not_ready",
        "actor": _text(plan.get("actor")),
        "request": plan_payload,
        "artifact_plan_fingerprint": expected if not blockers else "",
        "artifact_content_fingerprint": _bytes_fingerprint(_encode(artifact)) if artifact else "",
        "blockers": blockers,
        "dry_run": payload.get("dry_run") is True,
        "writes_artifact": False,
        "writes_receipt": False,
        **GOVERNANCE,
    }


def materialize_managed_copy_safe_delta_export_artifact(
    plan: dict[str, Any], *, provided_fingerprint: str, confirmed: bool
) -> dict[str, Any]:
    if not confirmed:
        return _blocked("safe_delta_export_artifact_confirmation_required")
    expected = _text(plan.get("artifact_plan_fingerprint"))
    if not expected or expected != _text(provided_fingerprint):
        return _blocked("safe_delta_export_artifact_plan_fingerprint_mismatch")
    with _LOCK:
        request = plan.get("request")
        request = dict(request) if isinstance(request, dict) else {}
        fresh = managed_copy_safe_delta_export_artifact_plan(
            {**request, "artifact_plan_fingerprint": expected, "confirm_export_artifact": True},
            actor=_text(plan.get("actor")),
        )
        if not fresh.get("ok") or fresh.get("artifact_plan_fingerprint") != expected:
            return _blocked("safe_delta_export_artifact_plan_drift")
        owned = _owned_paths(request, create=True)
        if owned is None:
            return _blocked("safe_delta_export_artifact_path_invalid")
        artifact_directory, receipt_directory, provision, isolation = owned
        artifact_path = artifact_directory / f"{expected[:16]}.json"
        receipt_path = receipt_directory / f"{expected[:16]}.json"
        artifact = _artifact(fresh)
        artifact_bytes = _encode(artifact)
        artifact_fp = _bytes_fingerprint(artifact_bytes)
        receipt = _receipt(
            fresh,
            request,
            provision,
            isolation,
            artifact_path.name,
            len(artifact_bytes),
            artifact_fp,
        )
        present_artifact, existing_artifact = _read(artifact_path)
        present_receipt, existing_receipt = _read(receipt_path)
        if present_artifact or present_receipt:
            if (
                present_artifact
                and present_receipt
                and existing_artifact == artifact
                and _valid_receipt(existing_receipt, receipt_path, receipt_directory)
                and _receipt_matches_artifact(existing_receipt, artifact_path, artifact)
                and _same_receipt_binding(existing_receipt, receipt)
            ):
                return _recorded(existing_receipt, False)
            return _blocked("safe_delta_export_artifact_conflict")
        try:
            _publish_exclusive(artifact_path, artifact_bytes)
            _publish_exclusive(receipt_path, _encode(receipt))
        except OSError:
            return _blocked("safe_delta_export_artifact_write_failed")
        if not _receipt_matches_artifact(receipt, artifact_path, artifact):
            return _blocked("safe_delta_export_artifact_write_verification_failed")
        return _recorded(receipt, True)


def managed_copy_safe_delta_export_artifacts_readback(
    *,
    copy_id: str,
    provisioning_receipt_id: str,
    isolation_verification_receipt_id: str,
    artifact_plan_fingerprint: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    request = {
        "copy_id": _text(copy_id),
        "provisioning_receipt_id": _text(provisioning_receipt_id),
        "isolation_verification_receipt_id": _text(isolation_verification_receipt_id),
    }
    owned = _owned_paths(request, create=False)
    if owned is None:
        return _readback([], "empty")
    artifact_directory, receipt_directory, _, _ = owned
    expected_plan = _text(artifact_plan_fingerprint)
    valid: list[dict[str, Any]] = []
    for receipt_path in sorted(receipt_directory.glob("*.json")):
        _, receipt = _read(receipt_path)
        if expected_plan and receipt.get("artifact_plan_fingerprint") != expected_plan:
            continue
        artifact_path = artifact_directory / _text(receipt.get("artifact_filename"))
        _, artifact = _read(artifact_path)
        if (
            _valid_receipt(receipt, receipt_path, receipt_directory)
            and _receipt_matches_artifact(receipt, artifact_path, artifact)
            and _live_plan_matches(receipt)
        ):
            valid.append(receipt)
    valid.sort(key=lambda item: (int(item["recorded_ts"]), _text(item.get("receipt_id"))))
    bounded = valid[-max(1, min(int(limit), 500)) :]
    return _readback(bounded, "artifacts_present" if bounded else "empty")


def _owned_paths(request: dict[str, Any], *, create: bool) -> tuple[Path, Path, dict[str, Any], dict[str, Any]] | None:
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
    artifact_directory = managed_copy_isolation_guarded_subpath(
        provision,
        isolation,
        domain="tenant_receipts",
        relative_parts=("za",),
        create_leaf_directory=create,
        require_live=True,
    )
    receipt_directory = managed_copy_isolation_guarded_subpath(
        provision,
        isolation,
        domain="tenant_receipts",
        relative_parts=("zr",),
        create_leaf_directory=create,
        require_live=True,
    )
    if artifact_directory is None or receipt_directory is None:
        return None
    return artifact_directory, receipt_directory, provision, isolation


def _artifact(plan: dict[str, Any]) -> dict[str, Any]:
    request = plan.get("request")
    request = request if isinstance(request, dict) else {}
    return {
        "kind": ARTIFACT_KIND,
        "contract": CONTRACT,
        "artifact_media_type": MEDIA_TYPE,
        "artifact_schema_class": SCHEMA_CLASS,
        "signal_class": SIGNAL_CLASS,
        "review_fingerprint": _text(request.get("review_fingerprint")),
        "authorization_decision_fingerprint": _text(request.get("authorization_decision_fingerprint")),
        "artifact_plan_fingerprint": _text(plan.get("artifact_plan_fingerprint")),
    }


def _receipt(
    plan: dict[str, Any],
    request: dict[str, Any],
    provision: dict[str, Any],
    isolation: dict[str, Any],
    filename: str,
    byte_count: int,
    artifact_fp: str,
) -> dict[str, Any]:
    plan_fp = _text(plan.get("artifact_plan_fingerprint"))
    receipt = {
        "ok": True,
        "kind": RECEIPT_KIND,
        "contract": CONTRACT,
        "receipt_id": f"managed_copy_safe_delta_export_artifact_{plan_fp[:16]}",
        "receipt_fingerprint": "",
        "status": "export_artifact_materialized",
        "actor": _text(plan.get("actor")),
        "tenant_key": _text(provision.get("tenant_key")),
        "copy_id": _text(request.get("copy_id")),
        "provisioning_receipt_id": _text(request.get("provisioning_receipt_id")),
        "provisioning_receipt_fingerprint": _text(provision.get("provision_fingerprint")),
        "isolation_verification_receipt_id": _text(request.get("isolation_verification_receipt_id")),
        "isolation_verification_receipt_fingerprint": _text(isolation.get("verification_fingerprint")),
        "review_fingerprint": _text(request.get("review_fingerprint")),
        "preflight_fingerprint": _text(request.get("preflight_fingerprint")),
        "request_fingerprint": _text(request.get("request_fingerprint")),
        "authorization_decision_receipt_id": _text(request.get("authorization_decision_receipt_id")),
        "authorization_decision_receipt_fingerprint": _authorization_receipt_fingerprint(request),
        "authorization_decision_fingerprint": _text(request.get("authorization_decision_fingerprint")),
        "artifact_plan_fingerprint": plan_fp,
        "artifact_filename": filename,
        "artifact_byte_count": byte_count,
        "artifact_content_fingerprint": artifact_fp,
        "recorded_ts": int(time.time()),
        "governance": GOVERNANCE,
    }
    receipt["receipt_fingerprint"] = _fingerprint_without(receipt, "receipt_fingerprint")
    return receipt


def _authorization_receipt_fingerprint(request: dict[str, Any]) -> str:
    from francis.managed_copy_safe_delta_export_authorization_decision import (
        managed_copy_safe_delta_export_authorization_decisions_readback,
    )

    readback = managed_copy_safe_delta_export_authorization_decisions_readback(
        copy_id=_text(request.get("copy_id")),
        provisioning_receipt_id=_text(request.get("provisioning_receipt_id")),
        isolation_verification_receipt_id=_text(request.get("isolation_verification_receipt_id")),
        limit=500,
    )
    matches = [
        item
        for item in readback.get("items", [])
        if isinstance(item, dict)
        and item.get("receipt_id") == request.get("authorization_decision_receipt_id")
        and item.get("authorization_decision_fingerprint") == request.get("authorization_decision_fingerprint")
    ]
    return _text(matches[0].get("receipt_fingerprint")) if len(matches) == 1 else ""


def _valid_receipt(item: dict[str, Any], path: Path, directory: Path) -> bool:
    plan_fp = _text(item.get("artifact_plan_fingerprint"))
    return bool(
        set(item) == RECEIPT_FIELDS
        and item.get("ok") is True
        and item.get("kind") == RECEIPT_KIND
        and item.get("contract") == CONTRACT
        and item.get("status") == "export_artifact_materialized"
        and item.get("receipt_id") == f"managed_copy_safe_delta_export_artifact_{plan_fp[:16]}"
        and all(
            _sha(item.get(field))
            for field in (
                "tenant_key",
                "provisioning_receipt_fingerprint",
                "isolation_verification_receipt_fingerprint",
                "review_fingerprint",
                "preflight_fingerprint",
                "request_fingerprint",
                "authorization_decision_receipt_fingerprint",
                "authorization_decision_fingerprint",
                "artifact_plan_fingerprint",
                "artifact_content_fingerprint",
                "receipt_fingerprint",
            )
        )
        and all(
            _text(item.get(field))
            for field in (
                "actor",
                "copy_id",
                "provisioning_receipt_id",
                "isolation_verification_receipt_id",
                "authorization_decision_receipt_id",
            )
        )
        and item.get("artifact_filename") == f"{plan_fp[:16]}.json"
        and type(item.get("artifact_byte_count")) is int
        and item["artifact_byte_count"] > 0
        and type(item.get("recorded_ts")) is int
        and item["recorded_ts"] > 0
        and item.get("governance") == GOVERNANCE
        and item.get("receipt_fingerprint") == _fingerprint_without(item, "receipt_fingerprint")
        and path == directory / f"{plan_fp[:16]}.json"
    )


def _receipt_matches_artifact(receipt: dict[str, Any], path: Path, artifact: dict[str, Any]) -> bool:
    try:
        artifact_bytes = path.read_bytes()
    except OSError:
        return False
    return bool(
        set(artifact) == ARTIFACT_FIELDS
        and artifact.get("kind") == ARTIFACT_KIND
        and artifact.get("contract") == CONTRACT
        and artifact.get("artifact_media_type") == MEDIA_TYPE
        and artifact.get("artifact_schema_class") == SCHEMA_CLASS
        and artifact.get("signal_class") == SIGNAL_CLASS
        and artifact.get("review_fingerprint") == receipt.get("review_fingerprint")
        and artifact.get("authorization_decision_fingerprint") == receipt.get("authorization_decision_fingerprint")
        and artifact.get("artifact_plan_fingerprint") == receipt.get("artifact_plan_fingerprint")
        and artifact_bytes == _encode(artifact)
        and len(artifact_bytes) == receipt.get("artifact_byte_count")
        and _bytes_fingerprint(artifact_bytes) == receipt.get("artifact_content_fingerprint")
    )


def _live_plan_matches(receipt: dict[str, Any]) -> bool:
    payload = {
        "request_actor": receipt.get("actor"),
        "copy_id": receipt.get("copy_id"),
        "provisioning_receipt_id": receipt.get("provisioning_receipt_id"),
        "isolation_verification_receipt_id": receipt.get("isolation_verification_receipt_id"),
        "review_fingerprint": receipt.get("review_fingerprint"),
        "preflight_fingerprint": receipt.get("preflight_fingerprint"),
        "request_fingerprint": receipt.get("request_fingerprint"),
        "authorization_decision_receipt_id": receipt.get("authorization_decision_receipt_id"),
        "authorization_decision_fingerprint": receipt.get("authorization_decision_fingerprint"),
        "artifact_media_type": MEDIA_TYPE,
        "artifact_schema_class": SCHEMA_CLASS,
        "retention_class": "transient_operator_export",
        "artifact_count": 1,
        "dry_run": True,
    }
    plan = build_artifact_plan(payload, actor=_text(receipt.get("actor")))
    return bool(
        plan.get("ok") is True
        and plan.get("artifact_plan_fingerprint") == receipt.get("artifact_plan_fingerprint")
        and _authorization_receipt_fingerprint(payload) == receipt.get("authorization_decision_receipt_fingerprint")
    )


def _same_receipt_binding(existing: dict[str, Any], expected: dict[str, Any]) -> bool:
    ignored = {"recorded_ts", "receipt_fingerprint"}
    return all(existing.get(key) == expected.get(key) for key in RECEIPT_FIELDS - ignored)


def _publish_exclusive(path: Path, content: bytes) -> None:
    temp = path.with_name(f".za-{uuid.uuid4().hex[:8]}.tmp")
    try:
        with temp.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name == "nt":
            os.rename(temp, path)
        else:
            os.link(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _read(path: Path) -> tuple[bool, dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return True, {}
    return True, value if isinstance(value, dict) else {}


def _readback(items: list[dict[str, Any]], status: str) -> dict[str, Any]:
    return {
        "ok": True,
        "kind": READBACK_KIND,
        "status": status,
        "items": items,
        "valid_count": len(items),
        "latest_valid_receipt": items[-1] if items else None,
        **GOVERNANCE,
    }


def _recorded(receipt: dict[str, Any], writes: bool) -> dict[str, Any]:
    return {
        "ok": True,
        "status": "export_artifact_materialized" if writes else "already_materialized",
        "error": "",
        "receipt": receipt,
        "receipt_id": receipt["receipt_id"],
        "artifact_content_fingerprint": receipt["artifact_content_fingerprint"],
        "writes_artifact": writes,
        "writes_receipt": writes,
        **GOVERNANCE,
    }


def _blocked(error: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "blocked",
        "error": error,
        "receipt": None,
        "receipt_id": "",
        "artifact_content_fingerprint": "",
        "writes_artifact": False,
        "writes_receipt": False,
        **GOVERNANCE,
    }


def _encode(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def _fingerprint_without(value: dict[str, Any], field: str) -> str:
    return _bytes_fingerprint(
        json.dumps(
            {key: item for key, item in value.items() if key != field},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    )


def _bytes_fingerprint(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha(value: Any) -> bool:
    return type(value) is str and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
