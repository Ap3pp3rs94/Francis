from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from francis.governance.pilot_scope_lease import PilotLeaseBinding
from francis.managed_copy_isolation import managed_copy_isolation_guarded_subpath

CONTRACT = "stage18_managed_copy_safe_delta_runtime_invocation_v2"
KIND = "francis.stage18.managed_copies.safe_delta_runtime_invocation"
RECEIPT_KIND = "francis.stage18.managed_copies.safe_delta_runtime_invocation_receipt"
READBACK_KIND = "francis.stage18.managed_copies.safe_delta_runtime_invocations"
ELIGIBLE = "eligible_for_core_review"
INELIGIBLE = "ineligible_for_core_review"
PREFLIGHT_SCOPE = "managed_copies.safe_delta.runtime_invocation.preflight"
WRITE_SCOPE = "managed_copies.safe_delta.runtime_invocation.write"
WRITE_ROUTE = "/managed-copies/safe-delta-runtime-invocation"
WRITE_ACTION = "managed_copies.safe_delta.runtime_invocation.record"
SOURCE_SCOPE = "managed_copies.safe_delta.runtime_source.write"
SOURCE_ROUTE = "/managed-copies/safe-delta-runtime-source"
SOURCE_ACTION = "managed_copies.safe_delta.runtime_source.record"
RUNTIME_EVIDENCE_SCOPE = "managed_copies.runtime_evidence.write"
RUNTIME_EVIDENCE_ROUTE = "/managed-copies/runtime-evidence-readback"
RUNTIME_EVIDENCE_ACTION = "managed_copies.runtime_evidence.record"
_INPUT_FIELDS = {
    "request_actor",
    "copy_id",
    "provisioning_receipt_id",
    "isolation_verification_receipt_id",
    "artifact_plan_fingerprint",
    "export_artifact_receipt_id",
    "export_artifact_receipt_fingerprint",
    "artifact_content_fingerprint",
    "dry_run",
    "invocation_fingerprint",
    "confirm_runtime_invocation",
    "pilot_lease_id",
    "package_id",
    "pilot_run_id",
    "trace_id",
}
_RECEIPT_FIELDS = {
    "ok",
    "kind",
    "contract",
    "receipt_id",
    "receipt_fingerprint",
    "status",
    "actor",
    "pilot_lease_id",
    "package_id",
    "package_fingerprint",
    "pilot_run_id",
    "operator_decision_fingerprint",
    "lease_authority_fingerprint",
    "authority_route",
    "authority_method",
    "authority_action",
    "trace_id",
    "tenant_key",
    "copy_id",
    "provisioning_receipt_id",
    "provisioning_receipt_fingerprint",
    "isolation_verification_receipt_id",
    "isolation_verification_receipt_fingerprint",
    "artifact_plan_fingerprint",
    "export_artifact_receipt_id",
    "export_artifact_receipt_fingerprint",
    "artifact_content_fingerprint",
    "invocation_fingerprint",
    "invocation_result",
    "invocation_result_fingerprint",
    "recorded_ts",
    "governance",
}
_RESULT_FIELDS = {
    "operation",
    "classification",
    "eligible_for_core_review",
    "reason_codes",
    "source_record_count",
    "abstraction_level",
    "retention_class",
}
GOVERNANCE = {
    "internal_component_only": True,
    "canonical_runtime_evidence": False,
    "runtime_gate_ready": False,
    "metadata_only": True,
    "executes_local_invocation": True,
    "writes_invocation_receipt": True,
    "writes_tenant_state": False,
    "writes_memory": False,
    "writes_registry": False,
    "writes_learning": False,
    "mutates_core": False,
    "uses_network": False,
    "uses_destination": False,
    "uses_connector": False,
    "imports_artifact": False,
    "runs_tools": False,
    "runs_shell": False,
    "runs_git": False,
    "uses_orb": False,
    "uses_docker": False,
    "grants_authority": False,
}
_LOCK = threading.Lock()


def plan_safe_delta_runtime_invocation(payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    unknown = sorted(set(payload) - _INPUT_FIELDS)
    request_actor = _text(payload.get("request_actor"))
    dry_run = payload.get("dry_run")
    blockers: list[str] = []
    if unknown:
        blockers.append("safe_delta_runtime_invocation_unknown_fields")
    if not _identifier(actor) or request_actor != actor:
        blockers.append("safe_delta_runtime_invocation_actor_lineage_mismatch")
    if dry_run is not True:
        blockers.append("safe_delta_runtime_invocation_dry_run_true_required")
    request = {
        key: _text(payload.get(key))
        for key in (
            "request_actor",
            "copy_id",
            "provisioning_receipt_id",
            "isolation_verification_receipt_id",
            "artifact_plan_fingerprint",
            "export_artifact_receipt_id",
            "export_artifact_receipt_fingerprint",
            "artifact_content_fingerprint",
            "pilot_lease_id",
            "package_id",
            "pilot_run_id",
            "trace_id",
        )
    }
    if not all(
        _identifier(request[field])
        for field in (
            "request_actor",
            "copy_id",
            "provisioning_receipt_id",
            "isolation_verification_receipt_id",
            "export_artifact_receipt_id",
            "pilot_lease_id",
            "package_id",
            "pilot_run_id",
            "trace_id",
        )
    ):
        blockers.append("safe_delta_runtime_invocation_identifier_invalid")
    if not all(
        _sha(request[field])
        for field in (
            "artifact_plan_fingerprint",
            "export_artifact_receipt_fingerprint",
            "artifact_content_fingerprint",
        )
    ):
        blockers.append("safe_delta_runtime_invocation_fingerprint_invalid")
    lineage, lineage_blocker = _load_artifact_lineage(request)
    if lineage_blocker:
        blockers.append(lineage_blocker)
    result = evaluate_core_review_eligibility(lineage.get("artifact", {})) if not blockers else {}
    binding = {
        "contract": CONTRACT,
        "actor": actor,
        "request": request,
        "tenant_key": _text(lineage.get("tenant_key")),
        "provisioning_receipt_fingerprint": _text(lineage.get("provisioning_receipt_fingerprint")),
        "isolation_verification_receipt_fingerprint": _text(lineage.get("isolation_verification_receipt_fingerprint")),
        "invocation_result": result,
    }
    fingerprint = _fingerprint(binding) if not blockers else ""
    provided = _text(payload.get("invocation_fingerprint"))
    if provided and provided != fingerprint:
        blockers.append("safe_delta_runtime_invocation_fingerprint_mismatch")
        fingerprint = ""
    return {
        "ok": not blockers,
        "kind": KIND,
        "contract": CONTRACT,
        "status": "runtime_invocation_ready" if not blockers else "blocked",
        "error": "" if not blockers else blockers[0],
        "actor": actor if _identifier(actor) else "",
        "request": request,
        "tenant_key": _text(lineage.get("tenant_key")) if not blockers else "",
        "invocation_fingerprint": fingerprint,
        "invocation_result": result,
        "blockers": blockers,
        "dry_run": dry_run is True,
        "writes_receipt": False,
        **_governance(writes=False),
    }


def record_safe_delta_runtime_invocation(
    plan: dict[str, Any],
    *,
    provided_fingerprint: str,
    confirmed: bool,
    authority: dict[str, Any],
) -> dict[str, Any]:
    if not confirmed:
        return _blocked("safe_delta_runtime_invocation_confirmation_required")
    expected = _text(plan.get("invocation_fingerprint"))
    if not expected or provided_fingerprint != expected:
        return _blocked("safe_delta_runtime_invocation_fingerprint_mismatch")
    if not _valid_authority(authority, plan, consumed_count=1):
        return _blocked("safe_delta_runtime_invocation_authority_lineage_invalid")
    with _LOCK:
        from francis.managed_copy_pilot_runtime import execute_pilot_runtime_lease_authority_transaction

        request = plan.get("request")
        request = request if isinstance(request, dict) else {}
        committed, reason, result = execute_pilot_runtime_lease_authority_transaction(
            request.get("pilot_lease_id"),
            actor=plan.get("actor"),
            expected_bindings=lease_bindings(),
            operation=lambda current: (
                _record_under_authority_transaction(plan, expected, current)
                if current == authority
                else _blocked("safe_delta_runtime_invocation_authority_changed_under_lock")
            ),
        )
        if committed:
            return result
        return _transaction_failed(result, reason)


def _record_under_authority_transaction(
    plan: dict[str, Any],
    expected: str,
    authority: dict[str, Any],
) -> dict[str, Any]:
    request = plan.get("request")
    request = dict(request) if isinstance(request, dict) else {}
    fresh = plan_safe_delta_runtime_invocation(
        {
            **request,
            "dry_run": True,
            "invocation_fingerprint": expected,
            "confirm_runtime_invocation": True,
        },
        actor=_text(plan.get("actor")),
    )
    if not fresh.get("ok") or fresh.get("invocation_fingerprint") != expected:
        return _blocked("safe_delta_runtime_invocation_lineage_drift")
    lineage, blocker = _load_artifact_lineage(request)
    if blocker:
        return _blocked(blocker)
    receipt_directory = _receipt_directory(lineage, create=True)
    if receipt_directory is None:
        return _blocked("safe_delta_runtime_invocation_path_invalid")
    receipt_path = receipt_directory / f"{expected[:16]}.json"
    receipt = _receipt(fresh, lineage, authority)
    receipt_bytes = _encode(receipt)
    present, existing = _read(receipt_path)
    if present:
        if _valid_receipt(existing, receipt_path, receipt_directory) and _same_binding(existing, receipt):
            current, current_blocker = _load_artifact_lineage(request)
            if current_blocker or not _receipt_matches_lineage(existing, current):
                return _blocked("safe_delta_runtime_invocation_lineage_drift")
            return _recorded(existing, writes=False)
        return _blocked("safe_delta_runtime_invocation_conflict")
    try:
        _publish_exclusive(receipt_path, receipt_bytes)
    except OSError:
        return _blocked("safe_delta_runtime_invocation_write_failed")
    present, written = _read(receipt_path)
    if (
        not present
        or not _exact_bytes(receipt_path, receipt_bytes)
        or written != receipt
        or not _valid_receipt(written, receipt_path, receipt_directory)
        or not _receipt_matches_lineage(written, lineage)
    ):
        return _cleanup_required(
            "safe_delta_runtime_invocation_write_verification_failed_after_publication",
            receipt,
            receipt_path,
            receipt_bytes,
        )
    current, current_blocker = _load_artifact_lineage(request)
    if current_blocker or not _receipt_matches_lineage(written, current):
        return _cleanup_required(
            "safe_delta_runtime_invocation_post_write_lineage_drift",
            receipt,
            receipt_path,
            receipt_bytes,
        )
    return _recorded(receipt, writes=True)


def safe_delta_runtime_invocations_readback(
    *,
    copy_id: str,
    provisioning_receipt_id: str,
    isolation_verification_receipt_id: str,
    invocation_fingerprint: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    request = {
        "copy_id": _text(copy_id),
        "provisioning_receipt_id": _text(provisioning_receipt_id),
        "isolation_verification_receipt_id": _text(isolation_verification_receipt_id),
    }
    lineage = _base_lineage(request)
    receipt_directory = _receipt_directory(lineage, create=False) if lineage else None
    if receipt_directory is None:
        return _readback([], "empty")
    expected = _text(invocation_fingerprint)
    valid: list[dict[str, Any]] = []
    for path in sorted(receipt_directory.glob("*.json")):
        present, receipt = _read(path)
        if not present or (expected and receipt.get("invocation_fingerprint") != expected):
            continue
        artifact_request = {
            key: _text(receipt.get(key))
            for key in (
                "copy_id",
                "provisioning_receipt_id",
                "isolation_verification_receipt_id",
                "artifact_plan_fingerprint",
                "export_artifact_receipt_id",
                "export_artifact_receipt_fingerprint",
                "artifact_content_fingerprint",
            )
        }
        artifact_request["request_actor"] = _text(receipt.get("actor"))
        current, blocker = _load_artifact_lineage(artifact_request)
        if (
            not blocker
            and _valid_receipt(receipt, path, receipt_directory)
            and _receipt_matches_lineage(receipt, current)
        ):
            valid.append(receipt)
    valid.sort(key=lambda item: (int(item["recorded_ts"]), _text(item.get("receipt_id"))))
    bounded_limit = max(1, min(limit, 500)) if type(limit) is int else 20
    bounded = valid[-bounded_limit:]
    return _readback(bounded, "invocations_present" if bounded else "empty")


def evaluate_core_review_eligibility(artifact: Any) -> dict[str, Any]:
    candidate = artifact.get("candidate") if isinstance(artifact, dict) else None
    candidate = candidate if isinstance(candidate, dict) else {}
    reasons: list[str] = []
    if artifact.get("artifact_schema_class") != "safe_delta_signal_v1":
        reasons.append("artifact_schema_not_metadata_safe_delta")
    if candidate.get("contains_raw_private_data") is not False:
        reasons.append("raw_private_data_present_or_unknown")
    if candidate.get("contains_tenant_identifiers") is not False:
        reasons.append("tenant_identifiers_present_or_unknown")
    if candidate.get("redaction_review_complete") is not True:
        reasons.append("redaction_review_incomplete")
    if candidate.get("abstraction_level") != "metadata_only":
        reasons.append("abstraction_level_not_metadata_only")
    if candidate.get("retention_class") != "review_receipt_only":
        reasons.append("retention_class_not_review_receipt_only")
    source_record_count = candidate.get("source_record_count")
    if type(source_record_count) is not int or source_record_count <= 0:
        reasons.append("source_record_count_not_positive_integer")
    eligible = not reasons
    result = {
        "operation": "evaluate_core_review_handoff",
        "classification": ELIGIBLE if eligible else INELIGIBLE,
        "eligible_for_core_review": eligible,
        "reason_codes": sorted(reasons),
        "source_record_count": source_record_count if type(source_record_count) is int else 0,
        "abstraction_level": _text(candidate.get("abstraction_level")),
        "retention_class": _text(candidate.get("retention_class")),
    }
    return result


def _load_artifact_lineage(request: dict[str, str]) -> tuple[dict[str, Any], str]:
    from francis import managed_copy_safe_delta_export_artifact as export_artifact

    lineage = _base_lineage(request)
    if not lineage:
        return {}, "safe_delta_runtime_invocation_provision_or_isolation_invalid"
    readback = export_artifact.managed_copy_safe_delta_export_artifacts_readback(
        copy_id=request["copy_id"],
        provisioning_receipt_id=request["provisioning_receipt_id"],
        isolation_verification_receipt_id=request["isolation_verification_receipt_id"],
        artifact_plan_fingerprint=request["artifact_plan_fingerprint"],
        limit=20,
    )
    receipt = readback.get("latest_valid_receipt")
    receipt = receipt if isinstance(receipt, dict) else {}
    if (
        readback.get("valid_count") != 1
        or receipt.get("receipt_id") != request["export_artifact_receipt_id"]
        or receipt.get("receipt_fingerprint") != request["export_artifact_receipt_fingerprint"]
        or receipt.get("artifact_content_fingerprint") != request["artifact_content_fingerprint"]
        or receipt.get("artifact_plan_fingerprint") != request["artifact_plan_fingerprint"]
    ):
        return {}, "safe_delta_runtime_invocation_export_artifact_invalid"
    owned = export_artifact._owned_paths(request, create=False)
    if owned is None:
        return {}, "safe_delta_runtime_invocation_artifact_path_invalid"
    artifact_directory, receipt_directory, provision, isolation = owned
    receipt_path = receipt_directory / f"{request['artifact_plan_fingerprint'][:16]}.json"
    artifact_path = artifact_directory / _text(receipt.get("artifact_filename"))
    receipt_present, loaded_receipt = export_artifact._read(receipt_path)
    artifact_present, artifact = export_artifact._read(artifact_path)
    if (
        not receipt_present
        or not artifact_present
        or loaded_receipt != receipt
        or not export_artifact._valid_receipt(loaded_receipt, receipt_path, receipt_directory)
        or not export_artifact._receipt_matches_artifact(loaded_receipt, artifact_path, artifact)
        or not export_artifact._live_plan_matches(loaded_receipt)
    ):
        return {}, "safe_delta_runtime_invocation_artifact_tampered_or_drifted"
    return {
        **lineage,
        "provisioning_receipt_fingerprint": _text(provision.get("provision_fingerprint")),
        "isolation_verification_receipt_fingerprint": _text(isolation.get("verification_fingerprint")),
        "export_artifact_receipt": loaded_receipt,
        "artifact": artifact,
    }, ""


def _base_lineage(request: dict[str, str]) -> dict[str, Any]:
    from francis.managed_copy_isolation import latest_managed_copy_isolation_verification_for_provision
    from francis.managed_copy_provisioning import managed_copy_provision_for_copy

    provision = managed_copy_provision_for_copy(
        request["copy_id"],
        provisioning_receipt_id=request["provisioning_receipt_id"],
    )
    isolation = (
        latest_managed_copy_isolation_verification_for_provision(
            request["provisioning_receipt_id"],
            provision_fingerprint=_text(provision.get("provision_fingerprint")),
            copy_id=request["copy_id"],
        )
        if provision
        else {}
    )
    if (
        not provision
        or not isolation
        or isolation.get("receipt_id") != request["isolation_verification_receipt_id"]
        or isolation.get("live_state_aligned") is not True
        or not _sha(provision.get("tenant_key"))
    ):
        return {}
    return {
        "tenant_key": _text(provision.get("tenant_key")),
        "provision": provision,
        "isolation": isolation,
    }


def _receipt_directory(lineage: dict[str, Any], *, create: bool) -> Path | None:
    provision = lineage.get("provision")
    isolation = lineage.get("isolation")
    if not isinstance(provision, dict) or not isinstance(isolation, dict):
        return None
    return managed_copy_isolation_guarded_subpath(
        provision,
        isolation,
        domain="tenant_receipts",
        relative_parts=("zi",),
        create_leaf_directory=create,
        require_live=True,
    )


def _receipt(plan: dict[str, Any], lineage: dict[str, Any], authority: dict[str, Any]) -> dict[str, Any]:
    request = plan["request"]
    result = plan["invocation_result"]
    fingerprint = plan["invocation_fingerprint"]
    receipt = {
        "ok": True,
        "kind": RECEIPT_KIND,
        "contract": CONTRACT,
        "receipt_id": f"managed_copy_safe_delta_runtime_invocation_{fingerprint[:16]}",
        "receipt_fingerprint": "",
        "status": "runtime_invocation_completed",
        "actor": plan["actor"],
        "pilot_lease_id": authority["lease_id"],
        "package_id": authority["package_id"],
        "package_fingerprint": authority["package_fingerprint"],
        "pilot_run_id": authority["pilot_run_id"],
        "operator_decision_fingerprint": authority["operator_decision_fingerprint"],
        "lease_authority_fingerprint": authority["lease_authority_fingerprint"],
        "authority_route": WRITE_ROUTE,
        "authority_method": "POST",
        "authority_action": WRITE_ACTION,
        "trace_id": request["trace_id"],
        "tenant_key": lineage["tenant_key"],
        "copy_id": request["copy_id"],
        "provisioning_receipt_id": request["provisioning_receipt_id"],
        "provisioning_receipt_fingerprint": lineage["provisioning_receipt_fingerprint"],
        "isolation_verification_receipt_id": request["isolation_verification_receipt_id"],
        "isolation_verification_receipt_fingerprint": lineage["isolation_verification_receipt_fingerprint"],
        "artifact_plan_fingerprint": request["artifact_plan_fingerprint"],
        "export_artifact_receipt_id": request["export_artifact_receipt_id"],
        "export_artifact_receipt_fingerprint": request["export_artifact_receipt_fingerprint"],
        "artifact_content_fingerprint": request["artifact_content_fingerprint"],
        "invocation_fingerprint": fingerprint,
        "invocation_result": result,
        "invocation_result_fingerprint": _fingerprint(result),
        "recorded_ts": int(time.time()),
        "governance": GOVERNANCE,
    }
    receipt["receipt_fingerprint"] = _fingerprint_without(receipt, "receipt_fingerprint")
    return receipt


def _valid_receipt(receipt: dict[str, Any], path: Path, directory: Path) -> bool:
    result = receipt.get("invocation_result")
    result = result if isinstance(result, dict) else {}
    fingerprint = _text(receipt.get("invocation_fingerprint"))
    reasons = result.get("reason_codes")
    return bool(
        set(receipt) == _RECEIPT_FIELDS
        and receipt.get("ok") is True
        and receipt.get("kind") == RECEIPT_KIND
        and receipt.get("contract") == CONTRACT
        and receipt.get("status") == "runtime_invocation_completed"
        and receipt.get("receipt_id") == f"managed_copy_safe_delta_runtime_invocation_{fingerprint[:16]}"
        and all(
            _identifier(receipt.get(field))
            for field in (
                "actor",
                "pilot_lease_id",
                "package_id",
                "pilot_run_id",
                "trace_id",
                "authority_action",
                "copy_id",
                "provisioning_receipt_id",
                "isolation_verification_receipt_id",
                "export_artifact_receipt_id",
            )
        )
        and all(
            _sha(receipt.get(field))
            for field in (
                "tenant_key",
                "package_fingerprint",
                "operator_decision_fingerprint",
                "lease_authority_fingerprint",
                "provisioning_receipt_fingerprint",
                "isolation_verification_receipt_fingerprint",
                "artifact_plan_fingerprint",
                "export_artifact_receipt_fingerprint",
                "artifact_content_fingerprint",
                "invocation_fingerprint",
                "invocation_result_fingerprint",
                "receipt_fingerprint",
            )
        )
        and set(result) == _RESULT_FIELDS
        and result.get("operation") == "evaluate_core_review_handoff"
        and result.get("classification") in {ELIGIBLE, INELIGIBLE}
        and type(result.get("eligible_for_core_review")) is bool
        and isinstance(reasons, list)
        and all(type(item) is str and item for item in reasons)
        and reasons == sorted(set(reasons))
        and type(result.get("source_record_count")) is int
        and result["source_record_count"] >= 0
        and _text(result.get("abstraction_level"))
        and _text(result.get("retention_class"))
        and receipt.get("invocation_result_fingerprint") == _fingerprint(result)
        and type(receipt.get("recorded_ts")) is int
        and receipt["recorded_ts"] > 0
        and receipt.get("governance") == GOVERNANCE
        and receipt.get("authority_route") == WRITE_ROUTE
        and receipt.get("authority_method") == "POST"
        and receipt.get("authority_action") == WRITE_ACTION
        and receipt.get("receipt_fingerprint") == _fingerprint_without(receipt, "receipt_fingerprint")
        and path == directory / f"{fingerprint[:16]}.json"
    )


def _receipt_matches_lineage(receipt: dict[str, Any], lineage: dict[str, Any]) -> bool:
    artifact_receipt = lineage.get("export_artifact_receipt")
    artifact_receipt = artifact_receipt if isinstance(artifact_receipt, dict) else {}
    artifact = lineage.get("artifact")
    result = evaluate_core_review_eligibility(artifact)
    return bool(
        receipt.get("tenant_key") == lineage.get("tenant_key")
        and receipt.get("provisioning_receipt_fingerprint") == lineage.get("provisioning_receipt_fingerprint")
        and receipt.get("isolation_verification_receipt_fingerprint")
        == lineage.get("isolation_verification_receipt_fingerprint")
        and receipt.get("export_artifact_receipt_id") == artifact_receipt.get("receipt_id")
        and receipt.get("export_artifact_receipt_fingerprint") == artifact_receipt.get("receipt_fingerprint")
        and receipt.get("artifact_content_fingerprint") == artifact_receipt.get("artifact_content_fingerprint")
        and receipt.get("invocation_result") == result
        and receipt.get("invocation_result_fingerprint") == _fingerprint(result)
    )


def _same_binding(existing: dict[str, Any], expected: dict[str, Any]) -> bool:
    ignored = {"recorded_ts", "receipt_fingerprint"}
    return all(existing.get(key) == expected.get(key) for key in _RECEIPT_FIELDS - ignored)


def lease_bindings(*, include_runtime_evidence: bool = False) -> tuple[PilotLeaseBinding, ...]:
    bindings = (
        PilotLeaseBinding(WRITE_SCOPE, WRITE_ROUTE, "POST", WRITE_ACTION),
        PilotLeaseBinding(SOURCE_SCOPE, SOURCE_ROUTE, "POST", SOURCE_ACTION),
    )
    if not include_runtime_evidence:
        return bindings
    return (
        *bindings,
        PilotLeaseBinding(
            RUNTIME_EVIDENCE_SCOPE,
            RUNTIME_EVIDENCE_ROUTE,
            "POST",
            RUNTIME_EVIDENCE_ACTION,
        ),
    )


def _valid_authority(
    authority: dict[str, Any],
    plan: dict[str, Any],
    *,
    consumed_count: int,
) -> bool:
    request = plan.get("request")
    request = request if isinstance(request, dict) else {}
    prefixes = authority.get("consumed_prefix_fingerprints")
    return bool(
        authority.get("valid") is True
        and authority.get("actor_id") == plan.get("actor")
        and authority.get("lease_id") == request.get("pilot_lease_id")
        and authority.get("package_id") == request.get("package_id")
        and authority.get("pilot_run_id") == request.get("pilot_run_id")
        and authority.get("operation_consumed_binding_count") == consumed_count
        and isinstance(prefixes, list)
        and len(prefixes) >= consumed_count
        and authority.get("lease_authority_fingerprint") == prefixes[consumed_count - 1]
        and all(
            _sha(authority.get(field))
            for field in (
                "package_fingerprint",
                "operator_decision_fingerprint",
                "lease_authority_fingerprint",
            )
        )
    )


def _transaction_failed(result: dict[str, Any], reason: str) -> dict[str, Any]:
    receipt = result.get("receipt")
    receipt = receipt if isinstance(receipt, dict) else {}
    if result.get("writes_receipt") is not True or not receipt:
        return _blocked(f"safe_delta_runtime_invocation_authority_transaction_{reason}")
    request = {
        key: _text(receipt.get(key))
        for key in (
            "copy_id",
            "provisioning_receipt_id",
            "isolation_verification_receipt_id",
        )
    }
    lineage = _base_lineage(request)
    directory = _receipt_directory(lineage, create=False) if lineage else None
    if directory is None:
        return _blocked("safe_delta_runtime_invocation_authority_transaction_receipt_unresolved")
    path = directory / f"{_text(receipt.get('invocation_fingerprint'))[:16]}.json"
    return _cleanup_required(
        f"safe_delta_runtime_invocation_authority_transaction_{reason}",
        receipt,
        path,
        _encode(receipt),
    )


def _publish_exclusive(path: Path, content: bytes) -> None:
    temp = path.with_name(f".zi-{uuid.uuid4().hex[:8]}.tmp")
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


def _exact_bytes(path: Path, expected: bytes) -> bool:
    try:
        return path.read_bytes() == expected
    except OSError:
        return False


def _recorded(receipt: dict[str, Any], *, writes: bool) -> dict[str, Any]:
    return {
        "ok": True,
        "status": "runtime_invocation_completed" if writes else "already_completed",
        "error": "",
        "receipt": receipt,
        "receipt_id": receipt["receipt_id"],
        "invocation_fingerprint": receipt["invocation_fingerprint"],
        "invocation_result": receipt["invocation_result"],
        "writes_receipt": writes,
        **_governance(writes=writes),
    }


def _blocked(error: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "blocked",
        "error": error,
        "receipt": None,
        "receipt_id": "",
        "invocation_fingerprint": "",
        "invocation_result": {},
        "writes_receipt": False,
        **_governance(writes=False),
    }


def _cleanup_required(
    error: str,
    receipt: dict[str, Any],
    receipt_path: Path,
    intended_bytes: bytes,
) -> dict[str, Any]:
    exact_receipt_preserved = _exact_bytes(receipt_path, intended_bytes)
    return {
        "ok": False,
        "status": "cleanup_required",
        "error": error,
        "receipt": None,
        "receipt_id": "",
        "invocation_fingerprint": "",
        "invocation_result": {},
        "writes_receipt": exact_receipt_preserved,
        "quarantined_receipt_id": _text(receipt.get("receipt_id")) if exact_receipt_preserved else "",
        "quarantined_receipt_fingerprint": (
            _text(receipt.get("receipt_fingerprint")) if exact_receipt_preserved else ""
        ),
        "quarantined_receipt_preserved": exact_receipt_preserved,
        "quarantined_receipt_preservation_status": (
            "exact_receipt_preserved" if exact_receipt_preserved else "preservation_unverified"
        ),
        **_governance(writes=exact_receipt_preserved),
    }


def _readback(items: list[dict[str, Any]], status: str) -> dict[str, Any]:
    return {
        "ok": True,
        "kind": READBACK_KIND,
        "contract": CONTRACT,
        "status": status,
        "items": items,
        "valid_count": len(items),
        "latest_valid_receipt": items[-1] if items else None,
        **_governance(writes=False),
    }


def _governance(*, writes: bool) -> dict[str, Any]:
    return {
        **GOVERNANCE,
        "writes_invocation_receipt": writes,
        "writes_receipt": writes,
    }


def _encode(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def _fingerprint_without(value: dict[str, Any], field: str) -> str:
    return _fingerprint({key: item for key, item in value.items() if key != field})


def _fingerprint(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _identifier(value: Any) -> str:
    if type(value) is not str:
        return ""
    text = value.strip()
    if not text or len(text) > 240:
        return ""
    return text if all(char.isalnum() or char in "._:-" for char in text) else ""


def _sha(value: Any) -> bool:
    return type(value) is str and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
