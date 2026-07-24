from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

from francis.governance.pilot_scope_lease import (
    PilotLeaseBinding,
    PilotLeaseState,
    PilotScopeLease,
    PilotScopeLeaseRegistry,
)
from francis.kernel.paths import data_dir, repo_root
from francis.managed_copy_isolation import (
    latest_managed_copy_isolation_verification_for_provision,
    managed_copy_isolation_guarded_subpath,
)
from francis.managed_copy_provisioning import managed_copy_provision_for_copy
from francis.managed_copy_runtime import HEARTBEAT_IDENTITY, INPUT_CONTRACT, RUNTIME_IDENTITY
from francis.process_identity import process_identity, terminate_owned_process

PILOT_RUNTIME_SCOPE = "managed_copies.pilot_runtime.execute"
PILOT_LEASE_MANAGE_SCOPE = "managed_copies.pilot_lease.manage"
PILOT_LEASE_ISSUE_ACTION = "managed_copies.pilot_lease.issue"
PILOT_LEASE_ISSUE_CONTRACT = "stage18_managed_copy_pilot_lease_issue_v1"
PILOT_RUNTIME_PROPOSAL_ACTION = "managed_copies.pilot_runtime.propose"
PILOT_RUNTIME_START_ACTION = "managed_copies.pilot_runtime.start"
PILOT_RUNTIME_STOP_ACTION = "managed_copies.pilot_runtime.stop"
PILOT_RUNTIME_CONTRACT = "stage18_managed_copy_pilot_runtime_v1"
PILOT_RUNTIME_PROPOSAL_ROUTE = "/managed-copies/pilot-runtime-proposal"
PILOT_RUNTIME_START_ROUTE = "/managed-copies/pilot-runtime-start"
PILOT_RUNTIME_STOP_ROUTE = "/managed-copies/pilot-runtime-stop"
PILOT_RUNTIME_EVIDENCE_CLASS = "local_non_fixture_runtime"

PILOT_RUNTIME_LEASES = PilotScopeLeaseRegistry()
_PILOT_LEASES: dict[str, PilotScopeLease] = {}
_PILOT_LEASE_APPROVAL_FINGERPRINTS: dict[str, str] = {}
_PILOT_LEASE_ISSUERS: dict[str, str] = {}
_LOCK = threading.RLock()
_LEASE_ISSUE_FIELDS = {"request_actor", "approval_id", "confirm_issue"}
_LEASE_DESCRIPTOR_FIELDS = {
    "contract",
    "issuer_actor",
    "lease_id",
    "actor_id",
    "package_id",
    "package_fingerprint",
    "pilot_run_id",
    "bindings",
    "issued_at_ms",
    "expires_at_ms",
    "runtime_nonce",
    "operator_decision_fingerprint",
}
_LEASE_APPROVAL_PAYLOAD_FIELDS = {
    "contract",
    "descriptor",
    "descriptor_fingerprint",
    "expires_at_unix_ms",
    "revoked",
}
_LEASE_LOOKUP_FIELDS = {"request_actor", "lease_id"}
_PAYLOAD_FIELDS = {
    "request_actor",
    "pilot_lease_id",
    "approval_id",
    "copy_id",
    "provisioning_receipt_id",
    "isolation_verification_receipt_id",
    "pilot_run_id",
    "trace_id",
    "startup_timeout_ms",
    "lease_seconds",
    "operation_input",
    "confirm_start",
}
_APPROVAL_FIELDS = {"id", "ts", "action", "reason", "payload", "status", "decision", "decision_actor", "decided_ts"}
_APPROVAL_PAYLOAD_FIELDS = {
    "contract",
    "descriptor",
    "descriptor_fingerprint",
    "expires_at_unix_ms",
    "revoked",
}
_STARTUP_RECEIPT_FIELDS = {
    "kind",
    "contract",
    "receipt_id",
    "status",
    "actor",
    "copy_id",
    "tenant_key",
    "pilot_run_id",
    "pilot_lease_id",
    "approval_id",
    "provisioning_receipt_id",
    "isolation_verification_receipt_id",
    "descriptor_fingerprint",
    "runtime_identity",
    "pid",
    "process_creation_token",
    "parent_pid",
    "launcher_pid",
    "launcher_creation_token",
    "controller_pid",
    "controller_creation_token",
    "operation",
    "operation_receipt_fingerprint",
    "output_fingerprint",
    "state_path",
    "trace_id",
    "evidence_class",
    "fixture_runtime",
    "docker_isolation",
    "canonical_runtime_evidence_recorded",
    "stage18_ready",
    "recorded_at_unix_ms",
    "startup_fingerprint",
}


def pilot_runtime_contract_snapshot() -> dict[str, Any]:
    return {
        "ok": True,
        "kind": "francis.stage18.managed_copies.pilot_runtime_contract",
        "contract": PILOT_RUNTIME_CONTRACT,
        "status": "local_process_software_available",
        "required_scope": PILOT_RUNTIME_SCOPE,
        "lease_manage_scope": PILOT_LEASE_MANAGE_SCOPE,
        "lease_issue_action": PILOT_LEASE_ISSUE_ACTION,
        "proposal_action": PILOT_RUNTIME_PROPOSAL_ACTION,
        "start_action": PILOT_RUNTIME_START_ACTION,
        "stop_action": PILOT_RUNTIME_STOP_ACTION,
        "runtime_identity": RUNTIME_IDENTITY,
        "operation": "tenant_work_briefing",
        "fixture_runtime": False,
        "docker_isolation": False,
        "persistent_actor_grant_present": False,
        "canonical_runtime_evidence_recorded": False,
        "stage18_ready": False,
    }


def issue_pilot_runtime_lease(payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != _LEASE_ISSUE_FIELDS:
        return _blocked("managed_copy_pilot_lease_payload_schema_invalid")
    if payload.get("confirm_issue") is not True:
        return _blocked("managed_copy_pilot_lease_confirmation_required")
    actor = _identifier(payload.get("request_actor"))
    approval_id = _identifier(payload.get("approval_id"))
    if not actor or not approval_id:
        return _blocked("managed_copy_pilot_lease_issue_binding_missing")
    initial = _pilot_lease_from_approval(approval_id, issuer_actor=actor)
    if initial["error"]:
        return _blocked(initial["error"])
    with _LOCK:
        final = _pilot_lease_from_approval(approval_id, issuer_actor=actor)
        if (
            final["error"]
            or final["approval_fingerprint"] != initial["approval_fingerprint"]
            or final["descriptor_fingerprint"] != initial["descriptor_fingerprint"]
        ):
            return _blocked(final["error"] or "managed_copy_pilot_lease_approval_changed_under_lock")
        lease = final["lease"]
        assert isinstance(lease, PilotScopeLease)
        existing = _PILOT_LEASES.get(lease.lease_id)
        if existing is not None:
            state = PILOT_RUNTIME_LEASES.state(lease.lease_id)
            if (
                existing == lease
                and state is PilotLeaseState.ACTIVE
                and _PILOT_LEASE_APPROVAL_FINGERPRINTS.get(lease.lease_id) == final["approval_fingerprint"]
            ):
                return _lease_result(existing, status="already_issued")
            return _blocked("managed_copy_pilot_lease_conflicting_replay")
        try:
            issued = PILOT_RUNTIME_LEASES.issue(lease)
        except ValueError as exc:
            return _blocked(str(exc))
        _PILOT_LEASES[issued.lease_id] = issued
        _PILOT_LEASE_APPROVAL_FINGERPRINTS[issued.lease_id] = final["approval_fingerprint"]
        _PILOT_LEASE_ISSUERS[issued.lease_id] = actor
    return _lease_result(issued, status="issued")


def _pilot_lease_from_approval(approval_id: str, *, issuer_actor: str) -> dict[str, Any]:
    approval = _read_json(data_dir() / "approvals" / "approved" / f"{approval_id}.json")
    payload = approval.get("payload")
    descriptor = payload.get("descriptor") if isinstance(payload, dict) else None
    if (
        set(approval) != _APPROVAL_FIELDS
        or not isinstance(payload, dict)
        or set(payload) != _LEASE_APPROVAL_PAYLOAD_FIELDS
        or not isinstance(descriptor, dict)
        or set(descriptor) != _LEASE_DESCRIPTOR_FIELDS
        or approval.get("id") != approval_id
        or approval.get("action") != PILOT_LEASE_ISSUE_ACTION
        or approval.get("status") != "approved"
        or approval.get("decision") not in {"approve", "approved"}
        or not _identifier(approval.get("decision_actor"))
        or payload.get("contract") != PILOT_LEASE_ISSUE_CONTRACT
        or descriptor.get("contract") != PILOT_LEASE_ISSUE_CONTRACT
        or descriptor.get("issuer_actor") != issuer_actor
        or payload.get("revoked") is not False
    ):
        return _lease_approval_blocked("managed_copy_pilot_lease_approval_binding_mismatch")
    descriptor_fingerprint = _text(payload.get("descriptor_fingerprint"))
    if _fingerprint(descriptor) != descriptor_fingerprint:
        return _lease_approval_blocked("managed_copy_pilot_lease_approval_descriptor_tampered")
    expires = _exact_int(payload.get("expires_at_unix_ms"), 1, 2**63 - 1)
    if expires <= int(time.time() * 1000):
        return _lease_approval_blocked("managed_copy_pilot_lease_approval_expired")
    try:
        raw_bindings = descriptor.get("bindings")
        if not isinstance(raw_bindings, list):
            raise ValueError("invalid_lease_bindings")
        bindings = tuple(
            PilotLeaseBinding(
                scope=item["scope"],
                route=item["route"],
                method=item["method"],
                action=item["action"],
            )
            for item in raw_bindings
            if isinstance(item, dict) and set(item) == {"scope", "route", "method", "action"}
        )
        if len(bindings) != len(raw_bindings):
            raise ValueError("invalid_lease_bindings")
        lease = PilotScopeLease(
            lease_id=descriptor["lease_id"],
            actor_id=descriptor["actor_id"],
            package_id=descriptor["package_id"],
            package_fingerprint=descriptor["package_fingerprint"],
            pilot_run_id=descriptor["pilot_run_id"],
            bindings=bindings,
            issued_at_ms=descriptor["issued_at_ms"],
            expires_at_ms=descriptor["expires_at_ms"],
            runtime_nonce=descriptor["runtime_nonce"],
            operator_decision_fingerprint=descriptor["operator_decision_fingerprint"],
        ).validated()
    except (KeyError, TypeError, ValueError) as exc:
        return _lease_approval_blocked(str(exc) or "managed_copy_pilot_lease_invalid")
    return {
        "error": "",
        "lease": lease,
        "descriptor_fingerprint": descriptor_fingerprint,
        "approval_fingerprint": _fingerprint(approval),
    }


def _lease_approval_blocked(error: str) -> dict[str, Any]:
    return {"error": error, "lease": None, "descriptor_fingerprint": "", "approval_fingerprint": ""}


def pilot_runtime_lease_status(payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != _LEASE_LOOKUP_FIELDS:
        return _blocked("managed_copy_pilot_lease_status_payload_schema_invalid")
    lease_id = _identifier(payload.get("lease_id"))
    with _LOCK:
        lease = _PILOT_LEASES.get(lease_id)
        state = PILOT_RUNTIME_LEASES.state(lease_id)
        issuer = _PILOT_LEASE_ISSUERS.get(lease_id)
    if lease is None or state is None:
        return _blocked("missing_pilot_lease")
    if issuer != _identifier(payload.get("request_actor")):
        return _blocked("managed_copy_pilot_lease_manager_mismatch")
    return _lease_result(lease, status=state.value)


def revoke_pilot_runtime_lease(payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != _LEASE_LOOKUP_FIELDS:
        return _blocked("managed_copy_pilot_lease_revoke_payload_schema_invalid")
    lease_id = _identifier(payload.get("lease_id"))
    with _LOCK:
        lease = _PILOT_LEASES.get(lease_id)
        issuer = _PILOT_LEASE_ISSUERS.get(lease_id)
        if lease is None:
            return _blocked("missing_pilot_lease")
        if issuer != _identifier(payload.get("request_actor")):
            return _blocked("managed_copy_pilot_lease_manager_mismatch")
        decision = PILOT_RUNTIME_LEASES.revoke(lease_id)
    if lease is None or not decision.allowed:
        return _blocked(decision.reason)
    return _lease_result(lease, status="revoked")


def authorize_pilot_runtime_proposal(*, lease_id: object, actor: object) -> dict[str, Any]:
    safe_lease_id = _identifier(lease_id)
    safe_actor = _identifier(actor)
    with _LOCK:
        lease = _PILOT_LEASES.get(safe_lease_id)
        state = PILOT_RUNTIME_LEASES.state(safe_lease_id)
    if lease is None or state is None:
        return _blocked("missing_pilot_lease")
    if state is not PilotLeaseState.ACTIVE:
        return _blocked(f"pilot_lease_{state.value}")
    if lease.actor_id != safe_actor:
        return _blocked("pilot_lease_actor_mismatch")
    proposal_binding = PilotLeaseBinding(
        PILOT_RUNTIME_SCOPE,
        PILOT_RUNTIME_PROPOSAL_ROUTE,
        "POST",
        PILOT_RUNTIME_PROPOSAL_ACTION,
    )
    start_binding = PilotLeaseBinding(
        PILOT_RUNTIME_SCOPE,
        PILOT_RUNTIME_START_ROUTE,
        "POST",
        PILOT_RUNTIME_START_ACTION,
    )
    if proposal_binding not in lease.bindings or start_binding not in lease.bindings:
        return _blocked("pilot_lease_binding_mismatch")
    return {
        "ok": True,
        "status": "authorized",
        "error": "",
        "lease_id": lease.lease_id,
        "lease_state": state.value,
        "binding_consumed": False,
    }


def pilot_runtime_proposal(payload: dict[str, Any], *, actor: str, stage17_closed: bool) -> dict[str, Any]:
    blockers: list[str] = []
    if set(payload) != _PAYLOAD_FIELDS:
        blockers.append("managed_copy_pilot_runtime_payload_schema_invalid")
    if _identifier(payload.get("request_actor")) != _identifier(actor):
        blockers.append("managed_copy_pilot_runtime_actor_mismatch")
    if not stage17_closed:
        blockers.append("stage17_prerequisite_not_closed")
    if type(payload.get("confirm_start")) is not bool:
        blockers.append("managed_copy_pilot_runtime_confirmation_invalid")
    copy_id = _identifier(payload.get("copy_id"))
    provision_id = _identifier(payload.get("provisioning_receipt_id"))
    isolation_id = _identifier(payload.get("isolation_verification_receipt_id"))
    run_id = _identifier(payload.get("pilot_run_id"))
    trace_id = _identifier(payload.get("trace_id"))
    lease_id = _identifier(payload.get("pilot_lease_id"))
    approval_id = _identifier(payload.get("approval_id"))
    timeout_ms = _exact_int(payload.get("startup_timeout_ms"), 250, 10_000)
    lease_seconds = _exact_int(payload.get("lease_seconds"), 1, 60)
    if not all((copy_id, provision_id, isolation_id, run_id, trace_id, lease_id, approval_id)):
        blockers.append("managed_copy_pilot_runtime_binding_missing")
    if not timeout_ms or not lease_seconds:
        blockers.append("managed_copy_pilot_runtime_timing_invalid")
    operation_input = payload.get("operation_input")
    try:
        from francis.managed_copy_runtime import build_work_briefing

        preview = build_work_briefing(operation_input)
    except ValueError as exc:
        blockers.append(str(exc))
        preview = {}
    provision = managed_copy_provision_for_copy(copy_id, provisioning_receipt_id=provision_id)
    if not provision:
        blockers.append("managed_copy_pilot_runtime_provision_invalid")
    isolation = (
        latest_managed_copy_isolation_verification_for_provision(
            provision_id,
            provision_fingerprint=_text(provision.get("provision_fingerprint")),
            copy_id=copy_id,
        )
        if provision
        else {}
    )
    if _text(isolation.get("receipt_id")) != isolation_id or isolation.get("live_state_aligned") is not True:
        blockers.append("managed_copy_pilot_runtime_isolation_invalid")
    lease_context = PILOT_RUNTIME_LEASES.lease_context(lease_id)
    if not lease_context:
        blockers.append("managed_copy_pilot_runtime_lease_missing")
    elif lease_context.get("actor_id") != _identifier(actor) or lease_context.get("pilot_run_id") != run_id:
        blockers.append("managed_copy_pilot_runtime_lease_lineage_mismatch")
    descriptor = (
        _descriptor(
            actor=_identifier(actor),
            provision=provision,
            isolation=isolation,
            lease_context=lease_context,
            trace_id=trace_id,
            timeout_ms=timeout_ms,
            lease_seconds=lease_seconds,
            input_fingerprint=_text(preview.get("input_fingerprint")),
        )
        if not blockers
        else {}
    )
    descriptor_fingerprint = _fingerprint(descriptor) if descriptor else ""
    approval = _read_json(data_dir() / "approvals" / "approved" / f"{approval_id}.json")
    if descriptor and approval and _approval_blocker(approval, descriptor, descriptor_fingerprint):
        blockers.append(_approval_blocker(approval, descriptor, descriptor_fingerprint))
    return {
        "ok": not blockers,
        "status": "ready" if not blockers else "blocked",
        "error": blockers[0] if blockers else "",
        "blockers": sorted(set(blockers)),
        "actor": _identifier(actor),
        "copy_id": copy_id,
        "pilot_run_id": run_id,
        "approval_id": approval_id,
        "descriptor": descriptor,
        "descriptor_fingerprint": descriptor_fingerprint,
        "operation_preview": preview if not blockers else {},
        "starts_runtime": False,
    }


def verify_pilot_runtime_source(source_receipt_id: str, source_receipt_fingerprint: str) -> dict[str, Any]:
    receipt = _raw_startup_receipt(_identifier(source_receipt_id))
    if not receipt:
        return _source_blocked("stage18_copy_creation_runtime_startup_receipt_missing")
    if receipt.get("fixture_runtime") is not False:
        return _source_blocked("managed_copy_pilot_runtime_fixture_source_rejected")
    if not _valid_startup_receipt(receipt):
        return _source_blocked("managed_copy_pilot_runtime_source_receipt_invalid")
    if receipt.get("startup_fingerprint") != source_receipt_fingerprint:
        return _source_blocked("managed_copy_pilot_runtime_source_fingerprint_mismatch")
    state_dir = _state_dir(receipt)
    if state_dir is None:
        return _source_blocked("managed_copy_pilot_runtime_source_path_invalid")
    handshake = _read_json(state_dir / "handshake.json")
    heartbeat = _read_json(state_dir / "heartbeat.json")
    operation = _read_json(state_dir / "operation.json")
    briefing = _read_json(state_dir / "briefing.json")
    identity = process_identity(_exact_int(receipt.get("pid"), 1, 2**31 - 1))
    if identity.get("creation_token") != receipt.get("process_creation_token"):
        return _source_blocked("managed_copy_pilot_runtime_source_process_mismatch")
    controller_identity = process_identity(_exact_int(receipt.get("controller_pid"), 1, 2**31 - 1))
    if (
        receipt.get("launcher_pid") != receipt.get("pid")
        or receipt.get("launcher_creation_token") != receipt.get("process_creation_token")
        or identity.get("parent_pid") != receipt.get("controller_pid")
        or controller_identity.get("creation_token") != receipt.get("controller_creation_token")
    ):
        return _source_blocked("managed_copy_pilot_runtime_source_controller_mismatch")
    if int(time.time() * 1000) - _exact_int(heartbeat.get("observed_at_unix_ms"), 1, 2**63 - 1) >= 3_000:
        return _source_blocked("managed_copy_pilot_runtime_source_heartbeat_stale")
    provision = managed_copy_provision_for_copy(
        _text(receipt.get("copy_id")),
        provisioning_receipt_id=_text(receipt.get("provisioning_receipt_id")),
    )
    isolation = latest_managed_copy_isolation_verification_for_provision(
        _text(receipt.get("provisioning_receipt_id")),
        provision_fingerprint=_text(provision.get("provision_fingerprint")),
        copy_id=_text(receipt.get("copy_id")),
    )
    lease = _PILOT_LEASES.get(_text(receipt.get("pilot_lease_id")))
    lease_state = PILOT_RUNTIME_LEASES.state(_text(receipt.get("pilot_lease_id")))
    approval = _read_json(data_dir() / "approvals" / "approved" / f"{receipt.get('approval_id')}.json")
    if (
        not provision
        or provision.get("receipt_id") != receipt.get("provisioning_receipt_id")
        or isolation.get("receipt_id") != receipt.get("isolation_verification_receipt_id")
        or isolation.get("live_state_aligned") is not True
        or lease is None
        or lease_state is not PilotLeaseState.ACTIVE
        or lease.actor_id != receipt.get("actor")
        or lease.pilot_run_id != receipt.get("pilot_run_id")
    ):
        return _source_blocked("managed_copy_pilot_runtime_source_lineage_mismatch")
    descriptor = approval.get("payload", {}).get("descriptor", {}) if isinstance(approval.get("payload"), dict) else {}
    if (
        _fingerprint(descriptor) != receipt.get("descriptor_fingerprint")
        or _approval_blocker(approval, descriptor, _text(receipt.get("descriptor_fingerprint")))
        or provision.get("provision_fingerprint") != descriptor.get("provision_fingerprint")
        or isolation.get("verification_fingerprint") != descriptor.get("isolation_verification_fingerprint")
        or descriptor.get("pilot_lease_id") != lease.lease_id
        or descriptor.get("package_id") != lease.package_id
        or descriptor.get("package_fingerprint") != lease.package_fingerprint
        or descriptor.get("runtime_nonce_hash") != _sha256(lease.runtime_nonce)
        or descriptor.get("operator_decision_fingerprint") != lease.operator_decision_fingerprint
    ):
        return _source_blocked("managed_copy_pilot_runtime_source_approval_lineage_mismatch")
    blocker = _runtime_records_blocker(
        handshake,
        heartbeat,
        operation,
        briefing,
        descriptor=descriptor,
        pid=receipt["pid"],
        creation_token=receipt["process_creation_token"],
        runtime_parent_pid=_exact_int(identity.get("parent_pid"), 1, 2**31 - 1),
        launcher_pid=_exact_int(receipt.get("launcher_pid"), 1, 2**31 - 1),
        controller_pid=_exact_int(receipt.get("controller_pid"), 1, 2**31 - 1),
    )
    if blocker:
        return _source_blocked(blocker)
    if operation.get("receipt_fingerprint") != receipt.get("operation_receipt_fingerprint") or briefing.get(
        "output_fingerprint"
    ) != receipt.get("output_fingerprint"):
        return _source_blocked("managed_copy_pilot_runtime_source_output_lineage_mismatch")
    lineage = {
        key: receipt[key]
        for key in (
            "receipt_id",
            "actor",
            "copy_id",
            "tenant_key",
            "pilot_run_id",
            "pilot_lease_id",
            "approval_id",
            "provisioning_receipt_id",
            "isolation_verification_receipt_id",
            "descriptor_fingerprint",
        )
    }
    current = {
        "pid": receipt["pid"],
        "process_creation_token": receipt["process_creation_token"],
        "launcher_pid": receipt["launcher_pid"],
        "launcher_creation_token": receipt["launcher_creation_token"],
        "controller_pid": receipt["controller_pid"],
        "controller_creation_token": receipt["controller_creation_token"],
        "heartbeat": {
            key: heartbeat.get(key)
            for key in (
                "heartbeat_identity",
                "runtime_identity",
                "copy_id",
                "tenant_key",
                "pilot_run_id",
                "runtime_nonce_hash",
                "ready",
                "fixture_runtime",
            )
        },
        "operation_receipt_fingerprint": operation["receipt_fingerprint"],
        "output_fingerprint": briefing["output_fingerprint"],
    }
    return {
        "valid": True,
        "blocker": "",
        "evidence_class": "canonical_runtime",
        "source_lineage_hash": _fingerprint(lineage),
        "current_state_hash": _fingerprint(current),
    }


def verify_pilot_runtime_authority_lineage(source_receipt_id: str, source_receipt_fingerprint: str) -> dict[str, Any]:
    """Return authority bindings only after the canonical runtime remains valid."""
    with _LOCK:
        source = verify_pilot_runtime_source(source_receipt_id, source_receipt_fingerprint)
        if source.get("valid") is not True:
            return {
                "valid": False,
                "blocker": _text(source.get("blocker")),
                "evidence_class": "",
                "authority_lineage": {},
            }
        receipt = _raw_startup_receipt(_identifier(source_receipt_id))
        lease_observation = PILOT_RUNTIME_LEASES.lease_snapshot_with_state(_text(receipt.get("pilot_lease_id")))
        approval = _read_json(data_dir() / "approvals" / "approved" / f"{receipt.get('approval_id')}.json")
        if lease_observation is None:
            return {
                "valid": False,
                "blocker": "managed_copy_pilot_runtime_source_lineage_mismatch",
                "authority_lineage": {},
            }
        lease, lease_state = lease_observation
        if lease_state is not PilotLeaseState.ACTIVE:
            return {
                "valid": False,
                "blocker": "managed_copy_pilot_runtime_source_lineage_mismatch",
                "evidence_class": "",
                "authority_lineage": {},
            }
        return {
            "valid": True,
            "blocker": "",
            "evidence_class": "canonical_runtime",
            "authority_lineage": {
                "tenant_key": receipt["tenant_key"],
                "copy_id": receipt["copy_id"],
                "pilot_run_id": receipt["pilot_run_id"],
                "runtime_identity": receipt["runtime_identity"],
                "runtime_start_receipt_id": receipt["receipt_id"],
                "runtime_start_receipt_fingerprint": receipt["startup_fingerprint"],
                "operator_approval_receipt_id": receipt["approval_id"],
                "operator_approval_receipt_fingerprint": _fingerprint(approval),
                "actor_scope_lease_id": lease.lease_id,
                "actor_scope_lease_fingerprint": _pilot_lease_authority_fingerprint(
                    lease,
                    effective_state=lease_state,
                ),
            },
        }


def _pilot_lease_authority_fingerprint(
    lease: PilotScopeLease,
    *,
    effective_state: PilotLeaseState,
    consumed_bindings: frozenset[PilotLeaseBinding] | None = None,
) -> str:
    def binding_payload(binding: PilotLeaseBinding) -> dict[str, str]:
        return {
            "scope": binding.scope,
            "route": binding.route,
            "method": binding.method,
            "action": binding.action,
        }

    consumed = lease.consumed_bindings if consumed_bindings is None else consumed_bindings
    return _fingerprint(
        {
            "lease_id": lease.lease_id,
            "actor_id": lease.actor_id,
            "package_id": lease.package_id,
            "package_fingerprint": lease.package_fingerprint,
            "pilot_run_id": lease.pilot_run_id,
            "bindings": [binding_payload(binding) for binding in lease.bindings],
            "issued_at_ms": lease.issued_at_ms,
            "expires_at_ms": lease.expires_at_ms,
            "runtime_nonce_hash": _sha256(lease.runtime_nonce),
            "operator_decision_fingerprint": lease.operator_decision_fingerprint,
            "effective_state": effective_state.value,
            "consumed_bindings": [binding_payload(binding) for binding in lease.bindings if binding in consumed],
        }
    )


def pilot_runtime_lease_authority_snapshot(
    lease_id: object,
    *,
    actor: object,
    expected_bindings: tuple[PilotLeaseBinding, ...],
) -> dict[str, Any]:
    """Return a redacted atomic lease observation for an exact action sequence."""
    try:
        bindings = tuple(binding.normalized() for binding in expected_bindings)
    except (AttributeError, ValueError):
        return {"valid": False, "blocker": "managed_copy_pilot_lease_binding_invalid"}
    observation = PILOT_RUNTIME_LEASES.lease_snapshot_with_state(lease_id)
    if observation is None:
        return {"valid": False, "blocker": "missing_pilot_lease"}
    lease, state = observation
    return _lease_authority_snapshot(lease, state, actor=actor, bindings=bindings)


def execute_pilot_runtime_lease_authority_transaction(
    lease_id: object,
    *,
    actor: object,
    expected_bindings: tuple[PilotLeaseBinding, ...],
    operation: Callable[[dict[str, Any]], dict[str, Any]],
) -> tuple[bool, str, dict[str, Any]]:
    """Publish through one lease-held transaction and report commit truth."""
    try:
        bindings = tuple(binding.normalized() for binding in expected_bindings)
    except (AttributeError, ValueError):
        return False, "managed_copy_pilot_lease_binding_invalid", {}

    def guarded(lease: PilotScopeLease, state: PilotLeaseState) -> dict[str, Any]:
        authority = _lease_authority_snapshot(lease, state, actor=actor, bindings=bindings)
        if authority.get("valid") is not True:
            return {"authority": authority, "result": {}}
        return {"authority": authority, "result": operation(authority)}

    registry = PILOT_RUNTIME_LEASES
    decision, transaction = registry.execute_authority_transaction(lease_id, guarded)
    if registry is not PILOT_RUNTIME_LEASES:
        return False, "pilot_lease_registry_replaced_during_transaction", transaction.get("result", {})
    authority = transaction.get("authority")
    result = transaction.get("result")
    if not isinstance(authority, dict) or authority.get("valid") is not True:
        blocker = authority.get("blocker") if isinstance(authority, dict) else decision.reason
        return False, _text(blocker) or decision.reason, {}
    return decision.allowed, decision.reason, result if isinstance(result, dict) else {}


def _lease_authority_snapshot(
    lease: PilotScopeLease,
    state: PilotLeaseState,
    *,
    actor: object,
    bindings: tuple[PilotLeaseBinding, ...],
) -> dict[str, Any]:
    safe_actor = _identifier(actor)
    matching_offsets = [
        index
        for index in range(0, len(lease.bindings) - len(bindings) + 1)
        if lease.bindings[index : index + len(bindings)] == bindings
    ]
    if (
        not safe_actor
        or lease.actor_id != safe_actor
        or len(bindings) not in {2, 3}
        or len(matching_offsets) != 1
        or not lease.consumed_bindings
        or state not in {PilotLeaseState.ACTIVE, PilotLeaseState.CONSUMED}
    ):
        return {"valid": False, "blocker": "managed_copy_pilot_lease_authority_lineage_mismatch"}
    offset = matching_offsets[0]
    consumed_count = len(lease.consumed_bindings)
    valid_consumed_counts = set(range(offset + 1, offset + len(bindings) + 1))
    if (
        lease.consumed_bindings != frozenset(lease.bindings[:consumed_count])
        or consumed_count not in valid_consumed_counts
    ):
        return {"valid": False, "blocker": "managed_copy_pilot_lease_authority_sequence_mismatch"}
    operation_consumed_count = consumed_count - offset
    prefix_fingerprints = [
        _pilot_lease_authority_fingerprint(
            lease,
            effective_state=(PilotLeaseState.CONSUMED if count == len(lease.bindings) else PilotLeaseState.ACTIVE),
            consumed_bindings=frozenset(lease.bindings[:count]),
        )
        for count in range(offset + 1, consumed_count + 1)
    ]
    sequence_prefix_fingerprints = [
        _pilot_lease_authority_fingerprint(
            lease,
            effective_state=(PilotLeaseState.CONSUMED if count == len(lease.bindings) else PilotLeaseState.ACTIVE),
            consumed_bindings=frozenset(lease.bindings[:count]),
        )
        for count in range(offset + 1, offset + len(bindings) + 1)
    ]
    return {
        "valid": True,
        "blocker": "",
        "lease_id": lease.lease_id,
        "actor_id": lease.actor_id,
        "package_id": lease.package_id,
        "package_fingerprint": lease.package_fingerprint,
        "pilot_run_id": lease.pilot_run_id,
        "operator_decision_fingerprint": lease.operator_decision_fingerprint,
        "effective_state": state.value,
        "consumed_binding_count": consumed_count,
        "operation_consumed_binding_count": operation_consumed_count,
        "lease_authority_fingerprint": prefix_fingerprints[-1],
        "consumed_prefix_fingerprints": prefix_fingerprints,
        "sequence_prefix_fingerprints": sequence_prefix_fingerprints,
    }


def start_pilot_runtime(payload: dict[str, Any], *, actor: str, stage17_closed: bool) -> dict[str, Any]:
    plan = pilot_runtime_proposal(payload, actor=actor, stage17_closed=stage17_closed)
    if not plan["ok"]:
        PILOT_RUNTIME_LEASES.seal(_identifier(payload.get("pilot_lease_id")))
        return plan
    if payload.get("confirm_start") is not True:
        PILOT_RUNTIME_LEASES.seal(_identifier(payload.get("pilot_lease_id")))
        return _blocked("managed_copy_pilot_runtime_confirmation_required")
    approval = _read_json(data_dir() / "approvals" / "approved" / f"{plan['approval_id']}.json")
    blocker = _approval_blocker(approval, plan["descriptor"], plan["descriptor_fingerprint"])
    if blocker:
        PILOT_RUNTIME_LEASES.seal(_identifier(payload.get("pilot_lease_id")))
        return _blocked(blocker)
    with _LOCK:
        approval = _read_json(data_dir() / "approvals" / "approved" / f"{plan['approval_id']}.json")
        blocker = _approval_blocker(approval, plan["descriptor"], plan["descriptor_fingerprint"])
        if blocker:
            PILOT_RUNTIME_LEASES.seal(_identifier(payload.get("pilot_lease_id")))
            return _blocked(blocker)
        if any(
            item.get("current_state", {}).get("ready")
            for item in pilot_runtime_status_snapshot(plan["copy_id"])["items"]
        ):
            return _blocked("managed_copy_pilot_runtime_active_conflict")
        lease_blocker = _pilot_lease_start_blocker(plan["descriptor"])
        if lease_blocker:
            return _blocked(lease_blocker)
        result = _launch(plan, payload["operation_input"])
        if result.get("ok") is not True:
            PILOT_RUNTIME_LEASES.seal(_identifier(payload.get("pilot_lease_id")))
        return result


def pilot_runtime_status_snapshot(copy_id: str = "") -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    root = data_dir() / "managed_copies" / "tenants"
    for path in root.glob("*/receipts/pilot_runtime/*/startup.json"):
        receipt = _read_json(path)
        if _valid_startup_receipt(receipt) and (not copy_id or receipt.get("copy_id") == copy_id):
            items.append({**receipt, "current_state": _current_state(receipt)})
    return {
        "ok": True,
        "kind": "francis.stage18.managed_copies.pilot_runtime_status",
        "count": len(items),
        "ready_count": sum(item["current_state"].get("ready") is True for item in items),
        "items": items,
        "fixture_runtime": False,
        "canonical_runtime_evidence_recorded": False,
        "stage18_ready": False,
    }


def stop_pilot_runtime(payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    if set(payload) != {"request_actor", "pilot_lease_id", "startup_receipt_id", "confirm_stop"}:
        return _blocked("managed_copy_pilot_runtime_stop_payload_schema_invalid")
    if _identifier(payload.get("request_actor")) != _identifier(actor) or payload.get("confirm_stop") is not True:
        return _blocked("managed_copy_pilot_runtime_stop_confirmation_invalid")
    receipt = _startup_receipt(_identifier(payload.get("startup_receipt_id")))
    if not receipt or receipt.get("actor") != actor or receipt.get("pilot_lease_id") != payload.get("pilot_lease_id"):
        return _blocked("managed_copy_pilot_runtime_stop_identity_mismatch")
    state_dir = _state_dir(receipt)
    identity = process_identity(_exact_int(receipt.get("pid"), 1, 2**31 - 1))
    if state_dir is None:
        return _blocked("managed_copy_pilot_runtime_stop_process_mismatch")
    already_exited = not identity
    if identity and identity.get("creation_token") != receipt.get("process_creation_token"):
        return _blocked("managed_copy_pilot_runtime_stop_process_mismatch")
    if not already_exited:
        try:
            (state_dir / "stop.signal").write_text("governed pilot stop\n", encoding="utf-8")
        except OSError:
            if not terminate_owned_process(
                receipt["pid"], creation_token=receipt["process_creation_token"], timeout_seconds=1.0
            ):
                return _blocked("managed_copy_pilot_runtime_cleanup_failed")
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and process_identity(receipt["pid"]):
            time.sleep(0.025)
        if process_identity(receipt["pid"]) and not terminate_owned_process(
            receipt["pid"], creation_token=receipt["process_creation_token"], timeout_seconds=1.0
        ):
            return _blocked("managed_copy_pilot_runtime_cleanup_failed")
    cleanup = {
        "kind": "francis.stage18.managed_copies.pilot_runtime_cleanup_receipt",
        "receipt_id": f"mcprc_{receipt['pilot_run_id']}",
        "startup_receipt_id": receipt["receipt_id"],
        "pilot_run_id": receipt["pilot_run_id"],
        "status": "already_exited" if already_exited else "stopped",
        "pid": receipt["pid"],
        "process_creation_token": receipt["process_creation_token"],
        "fixture_runtime": False,
        "recorded_at_unix_ms": int(time.time() * 1000),
    }
    cleanup["receipt_fingerprint"] = _fingerprint(cleanup)
    _write_immutable(state_dir / "cleanup.json", cleanup)
    PILOT_RUNTIME_LEASES.seal(_text(payload.get("pilot_lease_id")))
    return {"ok": True, "status": cleanup["status"], "receipt": cleanup}


def _launch(plan: dict[str, Any], operation_input: object) -> dict[str, Any]:
    descriptor = plan["descriptor"]
    provision = managed_copy_provision_for_copy(
        descriptor["copy_id"], provisioning_receipt_id=descriptor["provisioning_receipt_id"]
    )
    isolation = latest_managed_copy_isolation_verification_for_provision(
        descriptor["provisioning_receipt_id"],
        provision_fingerprint=descriptor["provision_fingerprint"],
        copy_id=descriptor["copy_id"],
    )
    if (
        provision.get("receipt_id") != descriptor["provisioning_receipt_id"]
        or provision.get("provision_fingerprint") != descriptor["provision_fingerprint"]
        or isolation.get("receipt_id") != descriptor["isolation_verification_receipt_id"]
        or isolation.get("verification_fingerprint") != descriptor["isolation_verification_fingerprint"]
        or isolation.get("live_state_aligned") is not True
    ):
        return _blocked("managed_copy_pilot_runtime_lineage_changed_under_lock")
    if _file_hash(_runtime_program()) != descriptor["program_fingerprint"]:
        return _blocked("managed_copy_pilot_runtime_program_changed_under_lock")
    executable = _runtime_executable()
    if (
        str(executable) != descriptor["executable_identity"]
        or _file_hash(executable) != descriptor["executable_fingerprint"]
    ):
        return _blocked("managed_copy_pilot_runtime_executable_changed_under_lock")
    data_root = _guarded_run_dir(provision, isolation, "tenant_data", descriptor["pilot_run_id"])
    state_dir = _guarded_run_dir(provision, isolation, "tenant_receipts", descriptor["pilot_run_id"])
    if data_root is None:
        return _blocked("managed_copy_pilot_runtime_input_path_invalid")
    if state_dir is None:
        return _blocked("managed_copy_pilot_runtime_state_path_invalid")
    input_path = data_root / "work_items.json"
    try:
        _write_immutable(input_path, operation_input)
    except OSError:
        return _blocked("managed_copy_pilot_runtime_input_already_exists")
    lease_context = PILOT_RUNTIME_LEASES.lease_context(descriptor["pilot_lease_id"])
    runtime_nonce = _text(lease_context.get("runtime_nonce"))
    if not runtime_nonce or _sha256(runtime_nonce) != descriptor["runtime_nonce_hash"]:
        return _blocked("managed_copy_pilot_runtime_lease_nonce_mismatch")
    command = [
        str(executable),
        str(_runtime_program()),
        "--tenant-root",
        str(data_dir() / descriptor["working_directory_identity"]),
        "--state-dir",
        str(state_dir),
        "--input-path",
        str(input_path),
        "--copy-id",
        descriptor["copy_id"],
        "--tenant-key",
        descriptor["tenant_key"],
        "--pilot-run-id",
        descriptor["pilot_run_id"],
        "--runtime-nonce",
        runtime_nonce,
        "--lease-seconds",
        str(descriptor["lease_seconds"]),
    ]
    try:
        process = subprocess.Popen(
            command,
            cwd=data_dir() / descriptor["working_directory_identity"],
            env={"PYTHONNOUSERSITE": "1", "PYTHONUTF8": "1"},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            close_fds=True,
        )
    except (OSError, ValueError):
        return _blocked("managed_copy_pilot_runtime_process_creation_failed")
    launcher_identity = process_identity(process.pid)
    launcher_token = _exact_int(launcher_identity.get("creation_token"), 1, 2**127)
    deadline = time.monotonic() + descriptor["startup_timeout_ms"] / 1000
    while time.monotonic() < deadline and process.poll() is None:
        handshake = _read_json(state_dir / "handshake.json")
        heartbeat = _read_json(state_dir / "heartbeat.json")
        operation = _read_json(state_dir / "operation.json")
        briefing = _read_json(state_dir / "briefing.json")
        if handshake and heartbeat and operation and briefing:
            break
        time.sleep(0.025)
    else:
        _cleanup_failed(process, launcher_token, state_dir)
        return _blocked("managed_copy_pilot_runtime_startup_failed")
    runtime_pid = _exact_int(handshake.get("pid"), 1, 2**31 - 1)
    runtime_identity: dict[str, Any] = {}
    while time.monotonic() < deadline and process.poll() is None:
        runtime_identity = process_identity(runtime_pid)
        if runtime_identity.get("creation_token") and runtime_identity.get("parent_pid"):
            break
        time.sleep(0.025)
    creation_token = _exact_int(runtime_identity.get("creation_token"), 1, 2**127)
    runtime_parent_pid = _exact_int(runtime_identity.get("parent_pid"), 1, 2**31 - 1)
    controller_identity = process_identity(os.getpid())
    controller_creation_token = _exact_int(controller_identity.get("creation_token"), 1, 2**127)
    blocker = _runtime_records_blocker(
        handshake,
        heartbeat,
        operation,
        briefing,
        descriptor=descriptor,
        pid=runtime_pid,
        creation_token=creation_token,
        runtime_parent_pid=runtime_parent_pid,
        launcher_pid=process.pid,
        controller_pid=os.getpid(),
    )
    if blocker:
        _cleanup_failed(process, launcher_token, state_dir)
        return _blocked(blocker)
    receipt = {
        "kind": "francis.stage18.managed_copies.pilot_runtime_startup_receipt",
        "contract": PILOT_RUNTIME_CONTRACT,
        "receipt_id": f"mcprs_{descriptor['pilot_run_id']}",
        "status": "ready",
        "actor": descriptor["actor"],
        "copy_id": descriptor["copy_id"],
        "tenant_key": descriptor["tenant_key"],
        "pilot_run_id": descriptor["pilot_run_id"],
        "pilot_lease_id": descriptor["pilot_lease_id"],
        "approval_id": plan["approval_id"],
        "provisioning_receipt_id": descriptor["provisioning_receipt_id"],
        "isolation_verification_receipt_id": descriptor["isolation_verification_receipt_id"],
        "descriptor_fingerprint": plan["descriptor_fingerprint"],
        "runtime_identity": RUNTIME_IDENTITY,
        "pid": runtime_pid,
        "process_creation_token": creation_token,
        "parent_pid": runtime_parent_pid,
        "launcher_pid": process.pid,
        "launcher_creation_token": launcher_token,
        "controller_pid": os.getpid(),
        "controller_creation_token": controller_creation_token,
        "operation": "tenant_work_briefing",
        "operation_receipt_fingerprint": operation["receipt_fingerprint"],
        "output_fingerprint": briefing["output_fingerprint"],
        "state_path": state_dir.relative_to(data_dir()).as_posix(),
        "trace_id": descriptor["trace_id"],
        "evidence_class": PILOT_RUNTIME_EVIDENCE_CLASS,
        "fixture_runtime": False,
        "docker_isolation": False,
        "canonical_runtime_evidence_recorded": False,
        "stage18_ready": False,
        "recorded_at_unix_ms": int(time.time() * 1000),
    }
    receipt["startup_fingerprint"] = _fingerprint(receipt)
    try:
        _write_immutable(state_dir / "startup.json", receipt)
    except OSError:
        _cleanup_failed(process, launcher_token, state_dir)
        return _blocked("managed_copy_pilot_runtime_startup_receipt_write_failed")
    return {"ok": True, "status": "ready", "receipt": receipt, "output": briefing}


def _descriptor(**values: Any) -> dict[str, Any]:
    provision = values["provision"]
    isolation = values["isolation"]
    lease = values["lease_context"]
    return {
        "contract": PILOT_RUNTIME_CONTRACT,
        "actor": values["actor"],
        "copy_id": provision["copy_id"],
        "tenant_key": provision["tenant_key"],
        "provisioning_receipt_id": provision["receipt_id"],
        "provision_fingerprint": provision["provision_fingerprint"],
        "isolation_verification_receipt_id": isolation["receipt_id"],
        "isolation_verification_fingerprint": isolation["verification_fingerprint"],
        "pilot_lease_id": lease["lease_id"],
        "package_id": lease["package_id"],
        "package_fingerprint": lease["package_fingerprint"],
        "pilot_run_id": lease["pilot_run_id"],
        "runtime_nonce_hash": _sha256(lease["runtime_nonce"]),
        "operator_decision_fingerprint": lease["operator_decision_fingerprint"],
        "runtime_identity": RUNTIME_IDENTITY,
        "executable_identity": str(_runtime_executable()),
        "executable_fingerprint": _file_hash(_runtime_executable()),
        "program_fingerprint": _file_hash(_runtime_program()),
        "working_directory_identity": f"managed_copies/tenants/{provision['tenant_key']}",
        "operation": "tenant_work_briefing",
        "input_contract": INPUT_CONTRACT,
        "input_fingerprint": values["input_fingerprint"],
        "operation_network_access": "none_by_implementation_not_os_enforced",
        "startup_timeout_ms": values["timeout_ms"],
        "lease_seconds": values["lease_seconds"],
        "trace_id": values["trace_id"],
    }


def _approval_blocker(approval: dict[str, Any], descriptor: dict[str, Any], fingerprint: str) -> str:
    if not approval:
        return "managed_copy_pilot_runtime_approval_missing"
    payload = approval.get("payload")
    if (
        set(approval) != _APPROVAL_FIELDS
        or not isinstance(payload, dict)
        or set(payload) != _APPROVAL_PAYLOAD_FIELDS
        or approval.get("status") != "approved"
        or approval.get("decision") not in {"approve", "approved"}
        or approval.get("action") != PILOT_RUNTIME_START_ACTION
        or payload.get("contract") != PILOT_RUNTIME_CONTRACT
        or payload.get("descriptor") != descriptor
        or payload.get("descriptor_fingerprint") != fingerprint
        or payload.get("revoked") is not False
    ):
        return "managed_copy_pilot_runtime_approval_binding_mismatch"
    expires = _exact_int(payload.get("expires_at_unix_ms"), 1, 2**63 - 1)
    return "managed_copy_pilot_runtime_approval_expired" if expires <= int(time.time() * 1000) else ""


def _pilot_lease_start_blocker(descriptor: dict[str, Any]) -> str:
    lease_id = _text(descriptor.get("pilot_lease_id"))
    lease = _PILOT_LEASES.get(lease_id)
    context = PILOT_RUNTIME_LEASES.lease_context(lease_id)
    state = PILOT_RUNTIME_LEASES.state(lease_id)
    if lease is None:
        return "managed_copy_pilot_runtime_lease_missing_under_lock"
    if state is not PilotLeaseState.ACTIVE:
        return f"managed_copy_pilot_runtime_lease_{state.value if state else 'missing'}_under_lock"
    expected = {
        "lease_id": lease.lease_id,
        "actor_id": lease.actor_id,
        "package_id": lease.package_id,
        "package_fingerprint": lease.package_fingerprint,
        "pilot_run_id": lease.pilot_run_id,
        "runtime_nonce": lease.runtime_nonce,
        "operator_decision_fingerprint": lease.operator_decision_fingerprint,
    }
    if context != expected or any(
        descriptor.get(key) != value
        for key, value in (
            ("actor", lease.actor_id),
            ("package_id", lease.package_id),
            ("package_fingerprint", lease.package_fingerprint),
            ("pilot_run_id", lease.pilot_run_id),
            ("runtime_nonce_hash", _sha256(lease.runtime_nonce)),
            ("operator_decision_fingerprint", lease.operator_decision_fingerprint),
        )
    ):
        return "managed_copy_pilot_runtime_lease_lineage_changed_under_lock"
    return ""


def _runtime_records_blocker(
    handshake: dict[str, Any],
    heartbeat: dict[str, Any],
    operation: dict[str, Any],
    briefing: dict[str, Any],
    *,
    descriptor: dict[str, Any],
    pid: int,
    creation_token: int,
    runtime_parent_pid: int,
    launcher_pid: int,
    controller_pid: int,
) -> str:
    common = {
        "copy_id": descriptor["copy_id"],
        "tenant_key": descriptor["tenant_key"],
        "pilot_run_id": descriptor["pilot_run_id"],
        "runtime_nonce_hash": descriptor["runtime_nonce_hash"],
    }
    if handshake.get("runtime_identity") != RUNTIME_IDENTITY or handshake.get("fixture_runtime") is not False:
        return "managed_copy_pilot_runtime_handshake_invalid"
    if any(handshake.get(key) != value for key, value in common.items()):
        return "managed_copy_pilot_runtime_handshake_lineage_mismatch"
    if handshake.get("pid") != pid or not creation_token:
        return "managed_copy_pilot_runtime_process_identity_mismatch"
    if not _trusted_parent_identity(
        handshake.get("parent_pid"),
        observed_parent_pid=runtime_parent_pid,
        launcher_pid=launcher_pid,
        controller_pid=controller_pid,
    ):
        return "managed_copy_pilot_runtime_parent_identity_mismatch"
    if heartbeat.get("heartbeat_identity") != HEARTBEAT_IDENTITY or heartbeat.get("ready") is not True:
        return "managed_copy_pilot_runtime_heartbeat_invalid"
    if any(heartbeat.get(key) != value for key, value in common.items()):
        return "managed_copy_pilot_runtime_heartbeat_lineage_mismatch"
    if operation.get("status") != "completed" or operation.get("fixture_runtime") is not False:
        return "managed_copy_pilot_runtime_operation_invalid"
    operation_fingerprint = operation.get("receipt_fingerprint")
    if (
        not isinstance(operation_fingerprint, str)
        or _fingerprint({key: value for key, value in operation.items() if key != "receipt_fingerprint"})
        != operation_fingerprint
    ):
        return "managed_copy_pilot_runtime_operation_tampered"
    if briefing.get("input_fingerprint") != descriptor["input_fingerprint"]:
        return "managed_copy_pilot_runtime_input_mismatch"
    output_fingerprint = briefing.get("output_fingerprint")
    if (
        not isinstance(output_fingerprint, str)
        or _fingerprint({key: value for key, value in briefing.items() if key != "output_fingerprint"})
        != output_fingerprint
    ):
        return "managed_copy_pilot_runtime_output_tampered"
    return ""


def _trusted_parent_identity(
    claimed_parent_pid: object,
    *,
    observed_parent_pid: int,
    launcher_pid: int,
    controller_pid: int,
) -> bool:
    return (
        type(claimed_parent_pid) is int
        and claimed_parent_pid == observed_parent_pid
        and observed_parent_pid in {launcher_pid, controller_pid}
    )


def _current_state(receipt: dict[str, Any]) -> dict[str, Any]:
    state_dir = _state_dir(receipt)
    identity = process_identity(_exact_int(receipt.get("pid"), 1, 2**31 - 1))
    heartbeat = _read_json(state_dir / "heartbeat.json") if state_dir else {}
    ready = bool(
        state_dir
        and identity.get("creation_token") == receipt.get("process_creation_token")
        and heartbeat.get("heartbeat_identity") == HEARTBEAT_IDENTITY
        and heartbeat.get("pilot_run_id") == receipt.get("pilot_run_id")
        and int(time.time() * 1000) - _exact_int(heartbeat.get("observed_at_unix_ms"), 1, 2**63 - 1) < 3_000
    )
    return {"ready": ready, "state": "ready" if ready else "stopped_or_degraded"}


def _guarded_run_dir(provision: dict[str, Any], isolation: dict[str, Any], domain: str, run_id: str) -> Path | None:
    parent_name = "pilot_runtime" if domain == "tenant_receipts" else "pilot_inputs"
    parent = managed_copy_isolation_guarded_subpath(
        provision, isolation, domain=domain, relative_parts=(parent_name,), create_leaf_directory=True
    )
    if parent is None:
        return None
    return managed_copy_isolation_guarded_subpath(
        provision,
        isolation,
        domain=domain,
        relative_parts=(parent_name, run_id),
        create_leaf_directory=True,
    )


def _startup_receipt(receipt_id: str) -> dict[str, Any]:
    item = _raw_startup_receipt(receipt_id)
    return item if _valid_startup_receipt(item) else {}


def _raw_startup_receipt(receipt_id: str) -> dict[str, Any]:
    for path in (data_dir() / "managed_copies" / "tenants").glob("*/receipts/pilot_runtime/*/startup.json"):
        item = _read_json(path)
        if item.get("receipt_id") == receipt_id:
            return item
    return {}


def _valid_startup_receipt(receipt: dict[str, Any]) -> bool:
    fingerprint = receipt.get("startup_fingerprint")
    return bool(
        set(receipt) == _STARTUP_RECEIPT_FIELDS
        and isinstance(fingerprint, str)
        and _fingerprint({key: value for key, value in receipt.items() if key != "startup_fingerprint"}) == fingerprint
        and receipt.get("kind") == "francis.stage18.managed_copies.pilot_runtime_startup_receipt"
        and receipt.get("contract") == PILOT_RUNTIME_CONTRACT
        and receipt.get("runtime_identity") == RUNTIME_IDENTITY
        and receipt.get("evidence_class") == PILOT_RUNTIME_EVIDENCE_CLASS
        and receipt.get("fixture_runtime") is False
        and receipt.get("canonical_runtime_evidence_recorded") is False
        and receipt.get("stage18_ready") is False
        and _identifier(receipt.get("receipt_id"))
        and _identifier(receipt.get("pilot_run_id"))
        and _exact_int(receipt.get("pid"), 1, 2**31 - 1)
        and _exact_int(receipt.get("process_creation_token"), 1, 2**127)
        and receipt.get("launcher_pid") == receipt.get("pid")
        and receipt.get("launcher_creation_token") == receipt.get("process_creation_token")
        and _exact_int(receipt.get("controller_pid"), 1, 2**31 - 1)
        and _exact_int(receipt.get("controller_creation_token"), 1, 2**127)
    )


def _lease_result(lease: PilotScopeLease, *, status: str) -> dict[str, Any]:
    return {
        "ok": True,
        "status": status,
        "error": "",
        "lease": {
            "lease_id": lease.lease_id,
            "actor_id": lease.actor_id,
            "pilot_run_id": lease.pilot_run_id,
            "expires_at_ms": lease.expires_at_ms,
            "state": status,
        },
        "writes_persistent_state": False,
        "grants_default_actor": False,
    }


def _source_blocked(blocker: str) -> dict[str, Any]:
    return {
        "valid": False,
        "blocker": blocker,
        "evidence_class": "",
        "source_lineage_hash": "",
        "current_state_hash": "",
    }


def _state_dir(receipt: dict[str, Any]) -> Path | None:
    relative = receipt.get("state_path")
    if not isinstance(relative, str):
        return None
    try:
        path = (data_dir() / relative).resolve(strict=True)
        path.relative_to(data_dir().resolve(strict=True))
    except (OSError, ValueError):
        return None
    return path


def _cleanup_failed(process: subprocess.Popen[bytes], token: int, state_dir: Path) -> None:
    (state_dir / "stop.signal").write_text("failed startup cleanup\n", encoding="utf-8")
    try:
        process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        if token:
            terminate_owned_process(process.pid, creation_token=token, timeout_seconds=1.0)


def _runtime_program() -> Path:
    return (repo_root() / "src" / "francis" / "managed_copy_runtime.py").resolve(strict=True)


def _runtime_executable() -> Path:
    base_executable = getattr(sys, "_base_executable", sys.executable)
    return Path(base_executable).resolve(strict=True)


def _write_immutable(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, sort_keys=True, separators=(",", ":"))


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _blocked(error: str) -> dict[str, Any]:
    return {"ok": False, "status": "blocked", "error": error, "starts_runtime": False}


def _fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _identifier(value: object) -> str:
    text = value.strip() if isinstance(value, str) else ""
    return text if 0 < len(text) <= 160 and all(char.isalnum() or char in "._:-" for char in text) else ""


def _exact_int(value: object, minimum: int, maximum: int) -> int:
    return value if type(value) is int and minimum <= value <= maximum else 0


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""
