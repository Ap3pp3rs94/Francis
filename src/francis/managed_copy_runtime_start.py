from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir, repo_root
from francis.managed_copy_isolation import (
    latest_managed_copy_isolation_verification_for_provision,
    managed_copy_isolation_guarded_subpath,
)
from francis.managed_copy_provisioning import managed_copy_provision_for_copy
from francis.process_identity import process_identity, terminate_owned_process

RUNTIME_START_SCOPE = "managed_copies.runtime_start.execute"
RUNTIME_START_ACTION = "managed_copies.runtime_start"
RUNTIME_START_CONTRACT = "stage18_managed_copy_runtime_start_v1"
RUNTIME_IDENTITY = "stage18_fixed_fixture_runtime_v1"
HEARTBEAT_IDENTITY = "stage18_fixed_fixture_heartbeat_v1"
HEARTBEAT_STALE_MS = 3_000
FIXTURE_EVIDENCE_CLASS = "fixture_software_only"
PRODUCTION_RUNTIME_IDENTITY = "stage18_managed_copy_runtime_v1_inactive"

_PAYLOAD_FIELDS = frozenset(
    {
        "request_actor",
        "approval_id",
        "copy_id",
        "provisioning_receipt_id",
        "isolation_verification_receipt_id",
        "action_nonce",
        "trace_id",
        "startup_timeout_ms",
        "lease_seconds",
        "confirm_runtime_start",
    }
)
_APPROVAL_FIELDS = frozenset(
    {"id", "ts", "action", "reason", "payload", "status", "decision", "decision_actor", "decided_ts"}
)
_APPROVAL_PAYLOAD_FIELDS = frozenset(
    {
        "contract",
        "action",
        "request_actor",
        "descriptor",
        "descriptor_fingerprint",
        "action_nonce",
        "trace_id",
        "expires_at_unix_ms",
        "revoked",
        "proposal_lineage",
    }
)
_DESCRIPTOR_FIELDS = frozenset(
    {
        "contract",
        "tenant_key",
        "copy_id",
        "provisioning_receipt_id",
        "provision_fingerprint",
        "isolation_verification_receipt_id",
        "isolation_verification_fingerprint",
        "runtime_identity",
        "executable_identity",
        "executable_fingerprint",
        "argument_fingerprint",
        "working_directory_identity",
        "environment",
        "tenant_roots",
        "endpoint_identity",
        "network_posture",
        "startup_timeout_ms",
        "lease_seconds",
        "expected_handshake_identity",
        "action_nonce",
        "trace_id",
        "proposal_lineage",
        "fixture_runtime",
    }
)
_STARTUP_RECEIPT_FIELDS = frozenset(
    {
        "kind",
        "contract",
        "receipt_id",
        "status",
        "actor",
        "approval_id",
        "copy_id",
        "tenant_key",
        "provisioning_receipt_id",
        "provision_fingerprint",
        "isolation_verification_receipt_id",
        "isolation_verification_fingerprint",
        "descriptor_fingerprint",
        "runtime_identity",
        "executable_fingerprint",
        "argument_fingerprint",
        "lease_id",
        "runtime_nonce_hash",
        "pid",
        "process_creation_token",
        "parent_pid",
        "handshake_identity",
        "heartbeat_identity",
        "state_path",
        "trace_id",
        "evidence_class",
        "fixture_runtime",
        "runtime_gate_ready",
        "stage18_ready",
        "recorded_at_unix_ms",
        "startup_fingerprint",
    }
)
_START_LOCK = threading.Lock()
_IDENTIFIER_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-")


def runtime_start_contract_snapshot() -> dict[str, Any]:
    return {
        "ok": True,
        "kind": "francis.stage18.managed_copies.runtime_start_contract",
        "contract": RUNTIME_START_CONTRACT,
        "status": "fixture_software_available",
        "required_scope": RUNTIME_START_SCOPE,
        "approval_action": RUNTIME_START_ACTION,
        "runtime_identity": RUNTIME_IDENTITY,
        "production_runtime_identity": PRODUCTION_RUNTIME_IDENTITY,
        "production_runtime_active": False,
        "fixed_executable": True,
        "shell_allowed": False,
        "arbitrary_arguments_allowed": False,
        "arbitrary_environment_allowed": False,
        "persistent_actor_grant_present": False,
        "live_runtime_started": False,
        "fixture_only": True,
        "routes": {
            "contract": "/managed-copies/runtime-start-contract",
            "status": "/managed-copies/runtime-start-status",
            "start": "/managed-copies/runtime-start",
        },
    }


def runtime_start_status_snapshot(*, copy_id: str = "") -> dict[str, Any]:
    receipts = _startup_receipts(copy_id=copy_id)
    items = [{**item, "current_state": _current_state(item)} for item in receipts]
    ready = [item for item in items if item["current_state"].get("ready") is True]
    return {
        "ok": True,
        "kind": "francis.stage18.managed_copies.runtime_start_status",
        "status": "fixture_ready" if ready else "no_current_fixture_runtime",
        "fixture_runtime": True,
        "production_runtime": False,
        "count": len(items),
        "ready_count": len(ready),
        "items": items,
        "runtime_gate_ready": False,
        "stage18_ready": False,
    }


def runtime_start_proposal(
    payload: dict[str, Any],
    *,
    actor: str,
    stage17_closed: bool,
) -> dict[str, Any]:
    blockers: list[str] = []
    if set(payload) != _PAYLOAD_FIELDS:
        blockers.append("managed_copy_runtime_start_payload_schema_invalid")
    safe_actor = _identifier(actor)
    if not safe_actor or _identifier(payload.get("request_actor")) != safe_actor:
        blockers.append("managed_copy_runtime_start_actor_mismatch")
    if not stage17_closed:
        blockers.append("stage17_prerequisite_not_closed")
    if type(payload.get("confirm_runtime_start")) is not bool:
        blockers.append("managed_copy_runtime_start_confirmation_invalid")

    copy_id = _identifier(payload.get("copy_id"))
    provision_id = _identifier(payload.get("provisioning_receipt_id"))
    isolation_id = _identifier(payload.get("isolation_verification_receipt_id"))
    approval_id = _identifier(payload.get("approval_id"))
    action_nonce = _identifier(payload.get("action_nonce"))
    trace_id = _identifier(payload.get("trace_id"))
    startup_timeout_ms = _exact_int(payload.get("startup_timeout_ms"), minimum=250, maximum=10_000)
    lease_seconds = _exact_int(payload.get("lease_seconds"), minimum=1, maximum=30)
    if not all((copy_id, provision_id, isolation_id, approval_id, action_nonce, trace_id)):
        blockers.append("managed_copy_runtime_start_binding_missing")
    if startup_timeout_ms == 0:
        blockers.append("managed_copy_runtime_start_timeout_invalid")
    if lease_seconds == 0:
        blockers.append("managed_copy_runtime_start_lease_invalid")

    provision = managed_copy_provision_for_copy(copy_id, provisioning_receipt_id=provision_id)
    if not provision:
        blockers.append("managed_copy_runtime_start_provision_invalid")
    isolation = latest_managed_copy_isolation_verification_for_provision(
        provision_id,
        provision_fingerprint=_text(provision.get("provision_fingerprint")),
        copy_id=copy_id,
    )
    if (
        not isolation
        or _text(isolation.get("receipt_id")) != isolation_id
        or isolation.get("live_state_aligned") is not True
    ):
        blockers.append("managed_copy_runtime_start_isolation_invalid")

    descriptor: dict[str, Any] = {}
    descriptor_fingerprint = ""
    if not blockers:
        descriptor = _launch_descriptor(
            provision=provision,
            isolation=isolation,
            action_nonce=action_nonce,
            trace_id=trace_id,
            startup_timeout_ms=startup_timeout_ms,
            lease_seconds=lease_seconds,
        )
        descriptor_fingerprint = _fingerprint(descriptor)
        approval = _approved_runtime_start(approval_id)
        approval_blocker = _approval_blocker(
            approval,
            actor=safe_actor,
            descriptor=descriptor,
            descriptor_fingerprint=descriptor_fingerprint,
            action_nonce=action_nonce,
            trace_id=trace_id,
        )
        if approval_blocker:
            blockers.append(approval_blocker)

    return {
        "ok": not blockers,
        "status": "approved" if not blockers else "blocked",
        "error": blockers[0] if blockers else "",
        "blockers": blockers,
        "actor": safe_actor,
        "approval_id": approval_id,
        "copy_id": copy_id,
        "provisioning_receipt_id": provision_id,
        "isolation_verification_receipt_id": isolation_id,
        "action_nonce": action_nonce,
        "trace_id": trace_id,
        "startup_timeout_ms": startup_timeout_ms,
        "lease_seconds": lease_seconds,
        "descriptor": descriptor,
        "descriptor_fingerprint": descriptor_fingerprint,
        "fixture_runtime": True,
        "writes_receipt": False,
        "starts_process": False,
        "runtime_ready": False,
        "runtime_gate_ready": False,
    }


def start_fixture_runtime(
    payload: dict[str, Any],
    *,
    actor: str,
    stage17_closed: bool,
) -> dict[str, Any]:
    initial = runtime_start_proposal(payload, actor=actor, stage17_closed=stage17_closed)
    if not initial["ok"]:
        return initial
    if payload.get("confirm_runtime_start") is not True:
        return _blocked(initial, "managed_copy_runtime_start_confirmation_required")

    with _START_LOCK:
        with _cross_process_lock() as acquired:
            if not acquired:
                return _blocked(initial, "managed_copy_runtime_start_lock_unavailable")
            final = runtime_start_proposal(payload, actor=actor, stage17_closed=stage17_closed)
            if not final["ok"] or final["descriptor_fingerprint"] != initial["descriptor_fingerprint"]:
                return _blocked(initial, "managed_copy_runtime_start_changed_under_lock")
            prior = _startup_receipt_for_approval(final["approval_id"])
            if prior:
                if (
                    prior.get("descriptor_fingerprint") == final["descriptor_fingerprint"]
                    and _current_state(prior).get("ready") is True
                ):
                    return {"ok": True, "status": "already_started", "receipt": prior, "writes_receipt": False}
                return _blocked(final, "managed_copy_runtime_start_approval_already_consumed")
            if _attempt_receipt_for_approval(final["approval_id"]):
                return _blocked(final, "managed_copy_runtime_start_approval_already_consumed")
            if _active_lease_for_copy(final["copy_id"]):
                return _blocked(final, "managed_copy_runtime_start_active_lease_conflict")
            return _launch(final)


def verify_runtime_startup_source(source_receipt_id: str, source_receipt_fingerprint: str) -> dict[str, Any]:
    receipt = _startup_receipt(source_receipt_id)
    if not receipt:
        return _source_blocked("stage18_copy_creation_runtime_startup_receipt_missing")
    if _fingerprint(receipt) != source_receipt_fingerprint:
        return _source_blocked("stage18_copy_creation_runtime_startup_receipt_hash_mismatch")
    state = _current_state(receipt)
    if state.get("ready") is not True:
        return _source_blocked(_text(state.get("blocker")) or "stage18_copy_creation_runtime_not_current")
    return {
        "valid": True,
        "blocker": "",
        "evidence_class": FIXTURE_EVIDENCE_CLASS,
        "source_lineage_hash": _fingerprint(
            {
                "provisioning_receipt_id": receipt["provisioning_receipt_id"],
                "provision_fingerprint": receipt["provision_fingerprint"],
                "isolation_verification_receipt_id": receipt["isolation_verification_receipt_id"],
                "isolation_verification_fingerprint": receipt["isolation_verification_fingerprint"],
                "approval_id": receipt["approval_id"],
                "descriptor_fingerprint": receipt["descriptor_fingerprint"],
            }
        ),
        "current_state_hash": _fingerprint(
            {
                key: state[key]
                for key in (
                    "ready",
                    "state",
                    "pid",
                    "process_creation_token",
                    "lease_id",
                    "fixture_runtime",
                    "runtime_gate_ready",
                )
            }
        ),
    }


def validate_runtime_start_approval_reference(
    approval_id: str,
    *,
    actor: str,
    copy_id: str,
    provisioning_receipt_id: str,
    provision_fingerprint: str,
    isolation_verification_receipt_id: str,
    isolation_verification_fingerprint: str,
) -> dict[str, Any]:
    """Validate an existing runtime-start approval without consuming it."""
    approval = _approved_runtime_start(_identifier(approval_id))
    raw_payload = approval.get("payload")
    payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
    raw_descriptor = payload.get("descriptor")
    descriptor: dict[str, Any] = raw_descriptor if isinstance(raw_descriptor, dict) else {}
    blocker = _approval_blocker(
        approval,
        actor=_identifier(actor),
        descriptor=descriptor,
        descriptor_fingerprint=_text(payload.get("descriptor_fingerprint")),
        action_nonce=_text(payload.get("action_nonce")),
        trace_id=_text(payload.get("trace_id")),
    )
    if blocker:
        return {"valid": False, "blocker": blocker, "approval_fingerprint": ""}
    expected = {
        "copy_id": _identifier(copy_id),
        "provisioning_receipt_id": _identifier(provisioning_receipt_id),
        "provision_fingerprint": _text(provision_fingerprint),
        "isolation_verification_receipt_id": _identifier(isolation_verification_receipt_id),
        "isolation_verification_fingerprint": _text(isolation_verification_fingerprint),
    }
    if any(descriptor.get(key) != value for key, value in expected.items()):
        return {
            "valid": False,
            "blocker": "managed_copy_runtime_start_approval_lineage_mismatch",
            "approval_fingerprint": "",
        }
    return {
        "valid": True,
        "blocker": "",
        "approval_fingerprint": _fingerprint(approval),
        "descriptor_fingerprint": _text(payload.get("descriptor_fingerprint")),
    }


def cleanup_fixture_runtime(startup_receipt: dict[str, Any], *, timeout_seconds: float = 3.0) -> dict[str, Any]:
    state_dir = _state_dir_from_receipt(startup_receipt)
    process = _owned_process(startup_receipt)
    if state_dir is None or process is None:
        return {"ok": False, "status": "cleanup_denied", "error": "fixture_runtime_identity_mismatch"}
    (state_dir / "cleanup.signal").write_text("fixture cleanup\n", encoding="utf-8")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline and process_identity(startup_receipt["pid"]):
        time.sleep(0.025)
    if process_identity(startup_receipt["pid"]):
        if not terminate_owned_process(
            startup_receipt["pid"],
            creation_token=startup_receipt["process_creation_token"],
            timeout_seconds=1.0,
        ):
            return {"ok": False, "status": "cleanup_required", "error": "fixture_runtime_cleanup_failed"}
    receipt = {
        "kind": "francis.stage18.managed_copies.fixture_runtime_cleanup_receipt",
        "receipt_id": f"mcrc_{startup_receipt['lease_id']}",
        "startup_receipt_id": startup_receipt["receipt_id"],
        "lease_id": startup_receipt["lease_id"],
        "pid": startup_receipt["pid"],
        "process_creation_token": startup_receipt["process_creation_token"],
        "status": "stopped",
        "fixture_runtime": True,
        "recorded_at_unix_ms": int(time.time() * 1000),
    }
    _write_immutable(state_dir / "cleanup.json", receipt)
    return {"ok": True, "status": "stopped", "receipt": receipt}


def _launch(plan: dict[str, Any]) -> dict[str, Any]:
    descriptor = plan["descriptor"]
    tenant_root = _tenant_root(descriptor["tenant_key"])
    lease_id = (
        f"mcrl_{_fingerprint({'nonce': plan['action_nonce'], 'descriptor': plan['descriptor_fingerprint']})[:20]}"
    )
    state_dir = _guarded_state_directory(plan, lease_id=lease_id)
    if state_dir is None:
        return _blocked(plan, "managed_copy_runtime_start_state_path_invalid")

    runtime_nonce = uuid.uuid4().hex
    attempt = {
        "kind": "francis.stage18.managed_copies.runtime_launch_attempt_receipt",
        "receipt_id": f"mcra_{lease_id[5:]}",
        "status": "starting",
        "actor": plan["actor"],
        "approval_id": plan["approval_id"],
        "copy_id": plan["copy_id"],
        "tenant_key": descriptor["tenant_key"],
        "lease_id": lease_id,
        "runtime_nonce_hash": _sha256(runtime_nonce),
        "descriptor_fingerprint": plan["descriptor_fingerprint"],
        "trace_id": plan["trace_id"],
        "fixture_runtime": True,
        "recorded_at_unix_ms": int(time.time() * 1000),
    }
    _write_immutable(state_dir / "attempt.json", attempt)
    approval_blocker = _approval_blocker(
        _approved_runtime_start(plan["approval_id"]),
        actor=plan["actor"],
        descriptor=descriptor,
        descriptor_fingerprint=plan["descriptor_fingerprint"],
        action_nonce=plan["action_nonce"],
        trace_id=plan["trace_id"],
    )
    if approval_blocker:
        return _failed_before_launch(attempt, state_dir=state_dir, blocker=approval_blocker)
    if (
        _file_hash(_fixture_executable()) != descriptor["executable_fingerprint"]
        or _fingerprint(
            {
                "program_fingerprint": _file_hash(_fixture_program()),
                "argument_contract": "fixed_fixture_v1",
            }
        )
        != descriptor["argument_fingerprint"]
    ):
        return _failed_before_launch(
            attempt,
            state_dir=state_dir,
            blocker="managed_copy_runtime_start_fixed_program_changed_before_launch",
        )
    command = _fixture_command(
        state_dir=state_dir,
        descriptor=descriptor,
        lease_id=lease_id,
        runtime_nonce=runtime_nonce,
    )
    environment = {"PYTHONNOUSERSITE": "1", "PYTHONUTF8": "1"}
    try:
        process = subprocess.Popen(
            command,
            cwd=tenant_root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            close_fds=True,
        )
    except (OSError, ValueError):
        return _failed_before_launch(
            attempt,
            state_dir=state_dir,
            blocker="managed_copy_runtime_start_process_creation_failed",
        )
    observed_process = process_identity(process.pid)
    creation_token = _exact_int(observed_process.get("creation_token"), minimum=1, maximum=2**127)
    if not creation_token:
        _cleanup_created_process(process, creation_token=0, state_dir=state_dir)
        return _blocked(plan, "managed_copy_runtime_start_process_identity_unavailable")
    deadline = time.monotonic() + descriptor["startup_timeout_ms"] / 1000
    try:
        handshake: dict[str, Any] = {}
        heartbeat: dict[str, Any] = {}
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("managed_copy_runtime_start_child_exited")
            handshake = _read_json(state_dir / "handshake.json")
            heartbeat = _read_json(state_dir / "heartbeat.json")
            if handshake and heartbeat:
                break
            time.sleep(0.025)
        record_blocker = _runtime_records_blocker(
            handshake,
            heartbeat,
            descriptor=descriptor,
            lease_id=lease_id,
            runtime_nonce=runtime_nonce,
            pid=process.pid,
            process_creation_token=creation_token,
            parent_pid=os.getpid(),
        )
        if record_blocker:
            raise RuntimeError(record_blocker)
        receipt = _startup_receipt_body(
            plan,
            lease_id=lease_id,
            runtime_nonce=runtime_nonce,
            pid=process.pid,
            process_creation_token=creation_token,
            parent_pid=os.getpid(),
            state_dir=state_dir,
        )
        _write_immutable(state_dir / "startup.json", receipt)
        return {"ok": True, "status": "ready", "receipt": receipt, "writes_receipt": True}
    except Exception:
        _cleanup_created_process(process, creation_token=creation_token, state_dir=state_dir)
        failed = {
            **attempt,
            "kind": "francis.stage18.managed_copies.runtime_start_failed_receipt",
            "status": "failed",
            "error": "managed_copy_runtime_start_runtime_failed",
            "pid": process.pid,
            "process_creation_token": creation_token,
        }
        _write_immutable(state_dir / "failed.json", failed)
        return {"ok": False, "status": "failed", "error": failed["error"], "receipt": failed}


def _launch_descriptor(
    *,
    provision: dict[str, Any],
    isolation: dict[str, Any],
    action_nonce: str,
    trace_id: str,
    startup_timeout_ms: int,
    lease_seconds: int,
) -> dict[str, Any]:
    tenant_key = _text(provision.get("tenant_key"))
    executable = _fixture_executable()
    fixture_program = _fixture_program()
    environment = {"PYTHONNOUSERSITE": "1", "PYTHONUTF8": "1"}
    roots = {
        "tenant_root": f"managed_copies/tenants/{tenant_key}",
        "data_root": f"managed_copies/tenants/{tenant_key}/data",
        "config_root": f"managed_copies/tenants/{tenant_key}/config",
        "log_root": f"managed_copies/tenants/{tenant_key}/receipts/runtime_start",
        "runtime_root": f"managed_copies/tenants/{tenant_key}/receipts/runtime_start",
    }
    descriptor = {
        "contract": RUNTIME_START_CONTRACT,
        "tenant_key": tenant_key,
        "copy_id": _text(provision.get("copy_id")),
        "provisioning_receipt_id": _text(provision.get("receipt_id")),
        "provision_fingerprint": _text(provision.get("provision_fingerprint")),
        "isolation_verification_receipt_id": _text(isolation.get("receipt_id")),
        "isolation_verification_fingerprint": _text(isolation.get("verification_fingerprint")),
        "runtime_identity": RUNTIME_IDENTITY,
        "executable_identity": executable.name,
        "executable_fingerprint": _file_hash(executable),
        "argument_fingerprint": _fingerprint(
            {"program_fingerprint": _file_hash(fixture_program), "argument_contract": "fixed_fixture_v1"}
        ),
        "working_directory_identity": roots["tenant_root"],
        "environment": {key: {"value_hash": _sha256(value)} for key, value in environment.items()},
        "tenant_roots": roots,
        "endpoint_identity": "tenant_local_filesystem_handshake_v1",
        "network_posture": "disabled_no_socket",
        "startup_timeout_ms": startup_timeout_ms,
        "lease_seconds": lease_seconds,
        "expected_handshake_identity": RUNTIME_IDENTITY,
        "action_nonce": action_nonce,
        "trace_id": trace_id,
        "proposal_lineage": [
            _text(provision.get("receipt_id")),
            _text(isolation.get("receipt_id")),
        ],
        "fixture_runtime": True,
    }
    assert set(descriptor) == _DESCRIPTOR_FIELDS
    return descriptor


def _approval_blocker(
    approval: dict[str, Any],
    *,
    actor: str,
    descriptor: dict[str, Any],
    descriptor_fingerprint: str,
    action_nonce: str,
    trace_id: str,
) -> str:
    if not approval:
        return "managed_copy_runtime_start_approval_missing"
    if set(approval) != _APPROVAL_FIELDS:
        return "managed_copy_runtime_start_approval_schema_invalid"
    payload = approval.get("payload")
    if not isinstance(payload, dict) or set(payload) != _APPROVAL_PAYLOAD_FIELDS:
        return "managed_copy_runtime_start_approval_schema_invalid"
    if approval.get("status") != "approved" or approval.get("decision") not in {"approve", "approved"}:
        return "managed_copy_runtime_start_approval_not_approved"
    if approval.get("action") != RUNTIME_START_ACTION or payload.get("action") != RUNTIME_START_ACTION:
        return "managed_copy_runtime_start_approval_action_mismatch"
    if payload.get("revoked") is not False:
        return "managed_copy_runtime_start_approval_revoked"
    expires = _exact_int(payload.get("expires_at_unix_ms"), minimum=1, maximum=2**63 - 1)
    if not expires or expires <= int(time.time() * 1000):
        return "managed_copy_runtime_start_approval_expired"
    if (
        payload.get("contract") != RUNTIME_START_CONTRACT
        or payload.get("request_actor") != actor
        or payload.get("descriptor") != descriptor
        or payload.get("descriptor_fingerprint") != descriptor_fingerprint
        or payload.get("action_nonce") != action_nonce
        or payload.get("trace_id") != trace_id
        or payload.get("proposal_lineage") != descriptor["proposal_lineage"]
    ):
        return "managed_copy_runtime_start_approval_binding_mismatch"
    if _fingerprint(descriptor) != descriptor_fingerprint:
        return "managed_copy_runtime_start_descriptor_hash_mismatch"
    return ""


def _approved_runtime_start(approval_id: str) -> dict[str, Any]:
    if not approval_id:
        return {}
    return _read_json(data_dir() / "approvals" / "approved" / f"{approval_id}.json")


def _startup_receipt_body(
    plan: dict[str, Any],
    *,
    lease_id: str,
    runtime_nonce: str,
    pid: int,
    process_creation_token: int,
    parent_pid: int,
    state_dir: Path,
) -> dict[str, Any]:
    descriptor = plan["descriptor"]
    receipt = {
        "kind": "francis.stage18.managed_copies.runtime_startup_receipt",
        "contract": RUNTIME_START_CONTRACT,
        "receipt_id": f"mcrs_{lease_id[5:]}",
        "status": "ready",
        "actor": plan["actor"],
        "approval_id": plan["approval_id"],
        "copy_id": plan["copy_id"],
        "tenant_key": descriptor["tenant_key"],
        "provisioning_receipt_id": descriptor["provisioning_receipt_id"],
        "provision_fingerprint": descriptor["provision_fingerprint"],
        "isolation_verification_receipt_id": descriptor["isolation_verification_receipt_id"],
        "isolation_verification_fingerprint": descriptor["isolation_verification_fingerprint"],
        "descriptor_fingerprint": plan["descriptor_fingerprint"],
        "runtime_identity": RUNTIME_IDENTITY,
        "executable_fingerprint": descriptor["executable_fingerprint"],
        "argument_fingerprint": descriptor["argument_fingerprint"],
        "lease_id": lease_id,
        "runtime_nonce_hash": _sha256(runtime_nonce),
        "pid": pid,
        "process_creation_token": process_creation_token,
        "parent_pid": parent_pid,
        "handshake_identity": RUNTIME_IDENTITY,
        "heartbeat_identity": HEARTBEAT_IDENTITY,
        "state_path": state_dir.relative_to(data_dir()).as_posix(),
        "trace_id": plan["trace_id"],
        "evidence_class": FIXTURE_EVIDENCE_CLASS,
        "fixture_runtime": True,
        "runtime_gate_ready": False,
        "stage18_ready": False,
        "recorded_at_unix_ms": int(time.time() * 1000),
    }
    receipt["startup_fingerprint"] = _fingerprint(receipt)
    return receipt


def _current_state(receipt: dict[str, Any]) -> dict[str, Any]:
    if not _valid_startup_receipt(receipt):
        return {"ready": False, "state": "failed", "blocker": "runtime_startup_receipt_invalid"}
    process = _owned_process(receipt)
    state_dir = _state_dir_from_receipt(receipt)
    if process is None or state_dir is None:
        return {"ready": False, "state": "exited", "blocker": "runtime_process_identity_mismatch"}
    heartbeat = _current_heartbeat(state_dir, receipt)
    if not heartbeat:
        return {"ready": False, "state": "degraded", "blocker": "runtime_heartbeat_invalid"}
    age_ms = int(time.time() * 1000) - _exact_int(heartbeat.get("observed_at_unix_ms"), minimum=1, maximum=2**63 - 1)
    if age_ms < 0 or age_ms > HEARTBEAT_STALE_MS:
        return {"ready": False, "state": "degraded", "blocker": "runtime_heartbeat_stale"}
    provision = managed_copy_provision_for_copy(
        receipt["copy_id"], provisioning_receipt_id=receipt["provisioning_receipt_id"]
    )
    isolation = latest_managed_copy_isolation_verification_for_provision(
        receipt["provisioning_receipt_id"],
        provision_fingerprint=receipt["provision_fingerprint"],
        copy_id=receipt["copy_id"],
    )
    if (
        not provision
        or provision.get("provision_fingerprint") != receipt["provision_fingerprint"]
        or not isolation
        or isolation.get("receipt_id") != receipt["isolation_verification_receipt_id"]
        or isolation.get("verification_fingerprint") != receipt["isolation_verification_fingerprint"]
        or isolation.get("live_state_aligned") is not True
    ):
        return {"ready": False, "state": "degraded", "blocker": "runtime_lineage_stale"}
    return {
        "ready": True,
        "state": "ready",
        "blocker": "",
        "pid": receipt["pid"],
        "process_creation_token": receipt["process_creation_token"],
        "lease_id": receipt["lease_id"],
        "heartbeat_sequence": heartbeat["sequence"],
        "heartbeat_observed_at_unix_ms": heartbeat["observed_at_unix_ms"],
        "fixture_runtime": True,
        "runtime_gate_ready": False,
    }


def _valid_startup_receipt(receipt: dict[str, Any]) -> bool:
    fingerprint = receipt.get("startup_fingerprint")
    without = {key: value for key, value in receipt.items() if key != "startup_fingerprint"}
    return bool(
        set(receipt) == _STARTUP_RECEIPT_FIELDS
        and receipt.get("kind") == "francis.stage18.managed_copies.runtime_startup_receipt"
        and receipt.get("contract") == RUNTIME_START_CONTRACT
        and receipt.get("status") == "ready"
        and receipt.get("fixture_runtime") is True
        and receipt.get("runtime_gate_ready") is False
        and receipt.get("stage18_ready") is False
        and receipt.get("evidence_class") == FIXTURE_EVIDENCE_CLASS
        and type(receipt.get("pid")) is int
        and type(receipt.get("process_creation_token")) is int
        and _is_hash(fingerprint)
        and fingerprint == _fingerprint(without)
    )


def _current_heartbeat(state_dir: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    for _ in range(5):
        heartbeat = _read_json(state_dir / "heartbeat.json")
        if _heartbeat_matches_receipt(heartbeat, receipt):
            return heartbeat
        time.sleep(0.025)
    return {}


def _owned_process(receipt: dict[str, Any]) -> dict[str, Any] | None:
    try:
        process = process_identity(receipt["pid"])
        if process.get("creation_token") != receipt["process_creation_token"]:
            return None
        if process.get("parent_pid") not in {0, receipt["parent_pid"]}:
            return None
        command = process.get("command_line")
        if command and (len(command) < 2 or Path(command[1]).resolve(strict=True) != _fixture_program()):
            return None
        executable_path = process.get("executable_path")
        if not isinstance(executable_path, str):
            return None
        if _file_hash(Path(executable_path).resolve(strict=True)) != receipt["executable_fingerprint"]:
            return None
        return process
    except (OSError, KeyError, TypeError, ValueError):
        return None


def _runtime_records_blocker(
    handshake: dict[str, Any],
    heartbeat: dict[str, Any],
    *,
    descriptor: dict[str, Any],
    lease_id: str,
    runtime_nonce: str,
    pid: int,
    process_creation_token: int,
    parent_pid: int,
) -> str:
    expected = {
        "pid": pid,
        "parent_pid": parent_pid,
        "copy_id": descriptor["copy_id"],
        "tenant_key": descriptor["tenant_key"],
        "lease_id": lease_id,
        "runtime_nonce": runtime_nonce,
        "descriptor_fingerprint": _fingerprint(descriptor),
    }
    if handshake.get("kind") != "francis.stage18.managed_copies.fixture_runtime_handshake":
        return "managed_copy_runtime_start_handshake_schema_invalid"
    if heartbeat.get("kind") != "francis.stage18.managed_copies.fixture_runtime_heartbeat":
        return "managed_copy_runtime_start_heartbeat_schema_invalid"
    if handshake.get("handshake_identity") != RUNTIME_IDENTITY or handshake.get("ready") is not True:
        return "managed_copy_runtime_start_handshake_identity_invalid"
    if heartbeat.get("heartbeat_identity") != HEARTBEAT_IDENTITY or heartbeat.get("ready") is not True:
        return "managed_copy_runtime_start_heartbeat_identity_invalid"
    for key, value in expected.items():
        if handshake.get(key) != value or heartbeat.get(key) != value:
            return f"managed_copy_runtime_start_child_{key}_mismatch"
    if (
        handshake.get("process_creation_token") != process_creation_token
        or heartbeat.get("process_creation_token") != process_creation_token
    ):
        return "managed_copy_runtime_start_process_creation_mismatch"
    return ""


def _heartbeat_matches_receipt(heartbeat: dict[str, Any], receipt: dict[str, Any]) -> bool:
    runtime_nonce = heartbeat.get("runtime_nonce")
    sequence = heartbeat.get("sequence")
    return bool(
        heartbeat.get("kind") == "francis.stage18.managed_copies.fixture_runtime_heartbeat"
        and heartbeat.get("heartbeat_identity") == receipt.get("heartbeat_identity")
        and isinstance(runtime_nonce, str)
        and runtime_nonce
        and _sha256(runtime_nonce) == receipt.get("runtime_nonce_hash")
        and heartbeat.get("pid") == receipt.get("pid")
        and heartbeat.get("process_creation_token") == receipt.get("process_creation_token")
        and heartbeat.get("parent_pid") == receipt.get("parent_pid")
        and heartbeat.get("copy_id") == receipt.get("copy_id")
        and heartbeat.get("tenant_key") == receipt.get("tenant_key")
        and heartbeat.get("lease_id") == receipt.get("lease_id")
        and heartbeat.get("descriptor_fingerprint") == receipt.get("descriptor_fingerprint")
        and type(sequence) is int
        and sequence > 0
        and type(heartbeat.get("observed_at_unix_ms")) is int
    )


def _fixture_command(*, state_dir: Path, descriptor: dict[str, Any], lease_id: str, runtime_nonce: str) -> list[str]:
    return [
        str(_fixture_executable()),
        str(_fixture_program()),
        "--state-dir",
        str(state_dir),
        "--copy-id",
        descriptor["copy_id"],
        "--tenant-key",
        descriptor["tenant_key"],
        "--lease-id",
        lease_id,
        "--runtime-nonce",
        runtime_nonce,
        "--descriptor-fingerprint",
        _fingerprint(descriptor),
        "--lease-seconds",
        str(descriptor["lease_seconds"]),
    ]


def _fixture_executable() -> Path:
    return Path(getattr(sys, "_base_executable", sys.executable)).resolve(strict=True)


def _cleanup_created_process(process: subprocess.Popen[bytes], *, creation_token: int, state_dir: Path) -> None:
    try:
        owned = process_identity(process.pid)
        if creation_token and owned.get("creation_token") != creation_token:
            return
        (state_dir / "cleanup.signal").write_text("failed startup cleanup\n", encoding="utf-8")
        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            terminate_owned_process(process.pid, creation_token=creation_token, timeout_seconds=1.0)
            process.wait(timeout=1.0)
    except (OSError, subprocess.TimeoutExpired):
        return


def _active_lease_for_copy(copy_id: str) -> bool:
    return any(_current_state(receipt).get("ready") is True for receipt in _startup_receipts(copy_id=copy_id))


def _startup_receipts(*, copy_id: str = "") -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    root = data_dir() / "managed_copies" / "tenants"
    if not root.is_dir():
        return items
    for path in root.glob("*/receipts/runtime_start/*/startup.json"):
        item = _read_json(path)
        if _valid_startup_receipt(item) and (not copy_id or item.get("copy_id") == copy_id):
            items.append(item)
    return sorted(items, key=lambda item: item["recorded_at_unix_ms"], reverse=True)


def _startup_receipt(receipt_id: str) -> dict[str, Any]:
    if not _identifier(receipt_id):
        return {}
    for item in _startup_receipts():
        if item.get("receipt_id") == receipt_id:
            return item
    return {}


def _startup_receipt_for_approval(approval_id: str) -> dict[str, Any]:
    for item in _startup_receipts():
        if item.get("approval_id") == approval_id:
            return item
    return {}


def _attempt_receipt_for_approval(approval_id: str) -> dict[str, Any]:
    root = data_dir() / "managed_copies" / "tenants"
    if not root.is_dir():
        return {}
    for path in root.glob("*/receipts/runtime_start/*/attempt.json"):
        item = _read_json(path)
        if item.get("approval_id") == approval_id and item.get("kind") == (
            "francis.stage18.managed_copies.runtime_launch_attempt_receipt"
        ):
            return item
    return {}


def _failed_before_launch(attempt: dict[str, Any], *, state_dir: Path, blocker: str) -> dict[str, Any]:
    failed = {
        **attempt,
        "kind": "francis.stage18.managed_copies.runtime_start_failed_receipt",
        "status": "failed",
        "error": blocker,
        "process_created": False,
    }
    _write_immutable(state_dir / "failed.json", failed)
    return {"ok": False, "status": "failed", "error": blocker, "receipt": failed}


def _guarded_state_directory(plan: dict[str, Any], *, lease_id: str) -> Path | None:
    descriptor = plan["descriptor"]
    provision = managed_copy_provision_for_copy(
        descriptor["copy_id"],
        provisioning_receipt_id=descriptor["provisioning_receipt_id"],
    )
    isolation = latest_managed_copy_isolation_verification_for_provision(
        descriptor["provisioning_receipt_id"],
        provision_fingerprint=descriptor["provision_fingerprint"],
        copy_id=descriptor["copy_id"],
    )
    if (
        not provision
        or not isolation
        or isolation.get("receipt_id") != descriptor["isolation_verification_receipt_id"]
        or isolation.get("verification_fingerprint") != descriptor["isolation_verification_fingerprint"]
    ):
        return None
    parent = managed_copy_isolation_guarded_subpath(
        provision,
        isolation,
        domain="tenant_receipts",
        relative_parts=("runtime_start",),
        create_leaf_directory=True,
    )
    if parent is None:
        return None
    return managed_copy_isolation_guarded_subpath(
        provision,
        isolation,
        domain="tenant_receipts",
        relative_parts=("runtime_start", lease_id),
        create_leaf_directory=True,
    )


def _state_dir_from_receipt(receipt: dict[str, Any]) -> Path | None:
    relative = receipt.get("state_path")
    expected = (
        f"managed_copies/tenants/{receipt.get('tenant_key', '')}/receipts/runtime_start/{receipt.get('lease_id', '')}"
    )
    if relative != expected:
        return None
    provision = managed_copy_provision_for_copy(
        receipt.get("copy_id", ""),
        provisioning_receipt_id=receipt.get("provisioning_receipt_id", ""),
    )
    isolation = latest_managed_copy_isolation_verification_for_provision(
        receipt.get("provisioning_receipt_id", ""),
        provision_fingerprint=receipt.get("provision_fingerprint", ""),
        copy_id=receipt.get("copy_id", ""),
    )
    if (
        not provision
        or not isolation
        or isolation.get("receipt_id") != receipt.get("isolation_verification_receipt_id")
        or isolation.get("verification_fingerprint") != receipt.get("isolation_verification_fingerprint")
    ):
        return None
    return managed_copy_isolation_guarded_subpath(
        provision,
        isolation,
        domain="tenant_receipts",
        relative_parts=("runtime_start", receipt["lease_id"]),
    )


def _tenant_root(tenant_key: str) -> Path:
    return data_dir() / "managed_copies" / "tenants" / tenant_key


def _fixture_program() -> Path:
    return (repo_root() / "src" / "francis" / "managed_copy_fixture_runtime.py").resolve(strict=True)


def _write_immutable(path: Path, payload: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=True)
        handle.write("\n")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fingerprint(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _identifier(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = redact_secret_text(value.strip()).strip()
    if not cleaned or len(cleaned) > 240 or any(character not in _IDENTIFIER_CHARS for character in cleaned):
        return ""
    return cleaned


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _exact_int(value: Any, *, minimum: int, maximum: int) -> int:
    return value if type(value) is int and minimum <= value <= maximum else 0


def _is_hash(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _blocked(plan: dict[str, Any], blocker: str) -> dict[str, Any]:
    return {**plan, "ok": False, "status": "blocked", "error": blocker, "blockers": [blocker]}


def _source_blocked(blocker: str) -> dict[str, Any]:
    return {
        "valid": False,
        "blocker": blocker,
        "evidence_class": FIXTURE_EVIDENCE_CLASS,
        "source_lineage_hash": "",
        "current_state_hash": "",
    }


@contextmanager
def _cross_process_lock() -> Iterator[bool]:
    lock_dir = data_dir() / "locks" / "managed_copy_runtime_start.lock"
    try:
        lock_dir.parent.mkdir(parents=True, exist_ok=True)
        lock_dir.mkdir()
    except FileExistsError:
        yield False
        return
    try:
        yield True
    finally:
        try:
            lock_dir.rmdir()
        except OSError:
            pass
