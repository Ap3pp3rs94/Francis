from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import francis.api.routes.managed_copies as managed_routes
import francis.managed_copy_pilot_runtime as pilot
from francis.api.app import create_app
from francis.governance.pilot_scope_lease import PilotLeaseBinding, PilotScopeLease, PilotScopeLeaseRegistry
from francis.managed_copy_runtime_evidence import (
    COPY_CREATION_PROOF_KIND,
    COPY_CREATION_REQUIREMENT,
    record_runtime_evidence,
)
from francis.managed_copy_runtime import INPUT_CONTRACT, build_work_briefing
from francis.process_identity import process_identity, terminate_owned_process

_ACTOR = "stage18.pilot-test"
_RUN = "pilot-run-vertical-001"
_LEASE = "pilot-lease-vertical-001"
_HASH_A = "a" * 64
_HASH_B = "b" * 64


def _input() -> dict[str, Any]:
    return {
        "contract": INPUT_CONTRACT,
        "items": [
            {"id": "work-2", "title": "Prepare weekly report", "priority": "normal", "status": "open"},
            {"id": "work-1", "title": "Resolve blocked intake", "priority": "critical", "status": "open"},
            {"id": "work-3", "title": "Archive completed receipt", "priority": "low", "status": "done"},
        ],
    }


def test_work_briefing_is_deterministic_and_actionable() -> None:
    result = build_work_briefing(_input())
    assert result["status_counts"] == {"open": 2, "blocked": 0, "done": 1}
    assert result["next_action"] == {
        "id": "work-1",
        "title": "Resolve blocked intake",
        "priority": "critical",
        "status": "open",
    }
    assert len(result["input_fingerprint"]) == 64
    assert len(result["output_fingerprint"]) == 64


def test_container_entrypoint_layout_executes_real_francis_operation(tmp_path: Path) -> None:
    tenant_root = tmp_path / "tenant"
    input_path = tenant_root / "data" / "work_items.json"
    state_dir = tenant_root / "receipts" / "runtime"
    input_path.parent.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    input_path.write_text(json.dumps(_input()), encoding="utf-8")
    program = Path(pilot.__file__).with_name("managed_copy_runtime.py")

    completed = subprocess.run(
        [
            sys.executable,
            str(program),
            "--tenant-root",
            str(tenant_root),
            "--state-dir",
            str(state_dir),
            "--input-path",
            str(input_path),
            "--copy-id",
            "managed_copy_container_layout",
            "--tenant-key",
            "c" * 64,
            "--pilot-run-id",
            "container-layout-run",
            "--runtime-nonce",
            "container-layout-nonce",
            "--lease-seconds",
            "1",
        ],
        cwd=tmp_path,
        env={"PYTHONNOUSERSITE": "1", "PYTHONUTF8": "1"},
        capture_output=True,
        check=False,
        timeout=5,
    )

    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    briefing = json.loads((state_dir / "briefing.json").read_text(encoding="utf-8"))
    operation = json.loads((state_dir / "operation.json").read_text(encoding="utf-8"))
    assert briefing["next_action"]["id"] == "work-1"
    assert operation["status"] == "completed"
    assert operation["fixture_runtime"] is False


def test_runtime_rejects_paths_outside_explicit_tenant_root(tmp_path: Path) -> None:
    tenant_root = tmp_path / "tenant"
    state_dir = tenant_root / "receipts"
    outside_input = tmp_path / "outside.json"
    tenant_root.mkdir()
    state_dir.mkdir()
    outside_input.write_text(json.dumps(_input()), encoding="utf-8")
    program = Path(pilot.__file__).with_name("managed_copy_runtime.py")

    completed = subprocess.run(
        [
            sys.executable,
            str(program),
            "--tenant-root",
            str(tenant_root),
            "--state-dir",
            str(state_dir),
            "--input-path",
            str(outside_input),
            "--copy-id",
            "managed_copy_container_layout",
            "--tenant-key",
            "c" * 64,
            "--pilot-run-id",
            "container-layout-run",
            "--runtime-nonce",
            "container-layout-nonce",
            "--lease-seconds",
            "1",
        ],
        capture_output=True,
        check=False,
        timeout=5,
    )

    assert completed.returncode == 2
    assert not (state_dir / "handshake.json").exists()


def test_managed_copy_runtime_image_is_fixed_to_real_francis_entrypoint() -> None:
    dockerfile = Path(pilot.__file__).parents[2] / "infra" / "managed-copy-runtime" / "Dockerfile"
    lines = dockerfile.read_text(encoding="utf-8").splitlines()

    assert lines == [
        "FROM python:3.12-alpine@sha256:dbb1970cc04ce7d381c65efe8309c0c03d463e5b35c88f14d721796ad24cfbfd",
        "",
        'LABEL francis.runtime.contract="stage18_managed_copy_runtime_v1"',
        'LABEL francis.runtime.program_sha256="aa0802b54f102f70ac21e3388a9c48837ed68f5d1ec5aa15d76403f3af1c4b2a"',
        "",
        "COPY --chown=65532:65532 src/francis/managed_copy_runtime.py /opt/francis/managed_copy_runtime.py",
        "",
        "USER 65532:65532",
        'ENTRYPOINT ["python", "/opt/francis/managed_copy_runtime.py"]',
    ]
    assert not any(token in dockerfile.read_text(encoding="utf-8") for token in ("busybox", "sh -c", "latest"))


@pytest.fixture
def vertical_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    data_root = Path(pilot.__file__).parents[2] / "data" / "test_runs" / f"mpr_{uuid.uuid4().hex[:8]}"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_ACTOR: [pilot.PILOT_RUNTIME_SCOPE]}))
    tenant_key = "c" * 64
    copy_id = "managed_copy_vertical_runtime"
    provision_id = "managed_copy_provision_vertical"
    isolation_id = "managed_copy_isolation_vertical"
    tenant_root = data_root / "managed_copies" / "tenants" / tenant_key
    for name in ("data", "memory", "receipts", "connectors", "capability_packs", "policy", "support"):
        (tenant_root / name).mkdir(parents=True, exist_ok=True)
    provision = {
        "copy_id": copy_id,
        "tenant_key": tenant_key,
        "receipt_id": provision_id,
        "provision_fingerprint": "d" * 64,
        "state_root": f"managed_copies/tenants/{tenant_key}",
    }
    isolation = {
        "copy_id": copy_id,
        "tenant_key": tenant_key,
        "receipt_id": isolation_id,
        "provisioning_receipt_id": provision_id,
        "provision_fingerprint": provision["provision_fingerprint"],
        "verification_fingerprint": "e" * 64,
        "live_state_aligned": True,
        "state_root": provision["state_root"],
    }

    def provision_lookup(requested_copy: str, *, provisioning_receipt_id: str = "") -> dict[str, Any]:
        return dict(provision) if (requested_copy, provisioning_receipt_id) == (copy_id, provision_id) else {}

    def isolation_lookup(
        requested_provision: str, *, provision_fingerprint: str = "", copy_id: str = ""
    ) -> dict[str, Any]:
        return (
            dict(isolation)
            if (requested_provision, provision_fingerprint, copy_id)
            == (provision_id, provision["provision_fingerprint"], provision["copy_id"])
            else {}
        )

    monkeypatch.setattr(pilot, "managed_copy_provision_for_copy", provision_lookup)
    monkeypatch.setattr(pilot, "latest_managed_copy_isolation_verification_for_provision", isolation_lookup)
    monkeypatch.setattr(managed_routes, "managed_copies_status_snapshot", lambda: {"stage17_closed_by_receipt": True})
    registry = PilotScopeLeaseRegistry()
    monkeypatch.setattr(pilot, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(managed_routes, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(pilot, "_PILOT_LEASES", {})
    now = int(time.time() * 1000)
    lease = PilotScopeLease(
        lease_id=_LEASE,
        actor_id=_ACTOR,
        package_id="stage18-local-pilot-package",
        package_fingerprint=_HASH_A,
        pilot_run_id=_RUN,
        bindings=(
            PilotLeaseBinding(
                pilot.PILOT_RUNTIME_SCOPE,
                pilot.PILOT_RUNTIME_START_ROUTE,
                "POST",
                pilot.PILOT_RUNTIME_START_ACTION,
            ),
            PilotLeaseBinding(
                pilot.PILOT_RUNTIME_SCOPE,
                pilot.PILOT_RUNTIME_STOP_ROUTE,
                "POST",
                pilot.PILOT_RUNTIME_STOP_ACTION,
            ),
            PilotLeaseBinding(
                pilot.PILOT_RUNTIME_SCOPE,
                pilot.PILOT_RUNTIME_PROPOSAL_ROUTE,
                "POST",
                pilot.PILOT_RUNTIME_PROPOSAL_ACTION,
            ),
        ),
        issued_at_ms=now - 1_000,
        expires_at_ms=now + 60_000,
        runtime_nonce="runtime-nonce-vertical-001",
        operator_decision_fingerprint=_HASH_B,
    )
    registry.issue(lease)
    pilot._PILOT_LEASES[_LEASE] = lease
    payload = {
        "request_actor": _ACTOR,
        "pilot_lease_id": _LEASE,
        "approval_id": "pilot-runtime-approval-001",
        "copy_id": copy_id,
        "provisioning_receipt_id": provision_id,
        "isolation_verification_receipt_id": isolation_id,
        "pilot_run_id": _RUN,
        "trace_id": "trace-pilot-runtime-001",
        "startup_timeout_ms": 5_000,
        "lease_seconds": 30,
        "operation_input": _input(),
        "confirm_start": True,
    }
    proposal = pilot.pilot_runtime_proposal(payload, actor=_ACTOR, stage17_closed=True)
    assert proposal["ok"] is True
    approval = {
        "id": payload["approval_id"],
        "ts": time.time(),
        "action": pilot.PILOT_RUNTIME_START_ACTION,
        "reason": "isolated synthetic local managed-copy runtime",
        "payload": {
            "contract": pilot.PILOT_RUNTIME_CONTRACT,
            "descriptor": proposal["descriptor"],
            "descriptor_fingerprint": proposal["descriptor_fingerprint"],
            "expires_at_unix_ms": now + 60_000,
            "revoked": False,
        },
        "status": "approved",
        "decision": "approve",
        "decision_actor": "test.operator",
        "decided_ts": time.time(),
    }
    approval_path = data_root / "approvals" / "approved" / f"{payload['approval_id']}.json"
    approval_path.parent.mkdir(parents=True)
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    return {"data_root": data_root, "tenant_root": tenant_root, "payload": payload, "registry": registry}


def test_unleased_request_denies_before_runtime_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_root = tmp_path / "denied-data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_ACTOR: [pilot.PILOT_RUNTIME_SCOPE]}))
    response = TestClient(create_app()).post(
        pilot.PILOT_RUNTIME_START_ROUTE,
        json={"request_actor": _ACTOR, "pilot_lease_id": "missing"},
    )
    assert response.json()["error"] == "api_permission_denied"
    assert not data_root.exists()


def test_lease_issue_denies_without_scope_before_registry_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    data_root = tmp_path / "lease-denied"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")
    registry = PilotScopeLeaseRegistry()
    monkeypatch.setattr(pilot, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(managed_routes, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(pilot, "_PILOT_LEASES", {})

    response = TestClient(create_app()).post(
        "/managed-copies/pilot-runtime-lease-issue",
        json={"request_actor": "lease.operator"},
    )

    assert response.json()["error"] == "api_permission_denied"
    assert pilot._PILOT_LEASES == {}
    assert not data_root.exists()


def test_process_local_lease_lifecycle_and_restart_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    operator = "lease.operator"
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({operator: [pilot.PILOT_LEASE_MANAGE_SCOPE]}))
    registry = PilotScopeLeaseRegistry()
    monkeypatch.setattr(pilot, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(managed_routes, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(pilot, "_PILOT_LEASES", {})
    now = int(time.time() * 1000)
    payload = {
        "request_actor": operator,
        "lease_id": "lease-api-001",
        "actor_id": _ACTOR,
        "package_id": "package-api-001",
        "package_fingerprint": _HASH_A,
        "pilot_run_id": "run-api-001",
        "bindings": [
            {
                "scope": pilot.PILOT_RUNTIME_SCOPE,
                "route": pilot.PILOT_RUNTIME_START_ROUTE,
                "method": "POST",
                "action": pilot.PILOT_RUNTIME_START_ACTION,
            },
            {
                "scope": pilot.PILOT_RUNTIME_SCOPE,
                "route": pilot.PILOT_RUNTIME_PROPOSAL_ROUTE,
                "method": "POST",
                "action": pilot.PILOT_RUNTIME_PROPOSAL_ACTION,
            },
        ],
        "issued_at_ms": now - 1,
        "expires_at_ms": now + 60_000,
        "runtime_nonce": "runtime-nonce-api-001",
        "operator_decision_fingerprint": _HASH_B,
    }
    client = TestClient(create_app())

    issued = client.post("/managed-copies/pilot-runtime-lease-issue", json=payload).json()
    assert issued["ok"] is True
    assert issued["writes_persistent_state"] is False
    status = client.post(
        "/managed-copies/pilot-runtime-lease-status",
        json={"request_actor": operator, "lease_id": payload["lease_id"]},
    ).json()
    assert status["status"] == "active"
    revoked = client.post(
        "/managed-copies/pilot-runtime-lease-revoke",
        json={"request_actor": operator, "lease_id": payload["lease_id"]},
    ).json()
    assert revoked["status"] == "revoked"

    monkeypatch.setattr(pilot, "PILOT_RUNTIME_LEASES", PilotScopeLeaseRegistry())
    monkeypatch.setattr(pilot, "_PILOT_LEASES", {})
    assert (
        pilot.pilot_runtime_lease_status({"request_actor": operator, "lease_id": payload["lease_id"]})["error"]
        == "missing_pilot_lease"
    )


def test_proposal_authorization_does_not_consume_start_binding(vertical_runtime: dict[str, Any]) -> None:
    payload = {**vertical_runtime["payload"], "confirm_start": False}
    before = vertical_runtime["registry"].state(_LEASE)
    proposed = TestClient(create_app()).post(pilot.PILOT_RUNTIME_PROPOSAL_ROUTE, json=payload).json()
    after = vertical_runtime["registry"].state(_LEASE)

    assert proposed["ok"] is True, proposed
    assert proposed["starts_runtime"] is False
    assert before == after
    assert vertical_runtime["registry"].state(_LEASE).value == "active"


def test_real_francis_process_vertical_path_and_exact_cleanup(vertical_runtime: dict[str, Any]) -> None:
    client = TestClient(create_app())
    started = client.post(pilot.PILOT_RUNTIME_START_ROUTE, json=vertical_runtime["payload"]).json()
    assert started["ok"] is True, started
    receipt = started["receipt"]
    assert receipt["fixture_runtime"] is False
    assert receipt["evidence_class"] == pilot.PILOT_RUNTIME_EVIDENCE_CLASS
    assert receipt["canonical_runtime_evidence_recorded"] is False
    assert started["output"]["next_action"]["id"] == "work-1"
    observed = process_identity(receipt["pid"])
    assert observed["creation_token"] == receipt["process_creation_token"]
    assert observed["parent_pid"] == receipt["parent_pid"]
    assert receipt["parent_pid"] == os.getpid()

    status = client.get("/managed-copies/pilot-runtime-status", params={"copy_id": receipt["copy_id"]}).json()
    assert status["ready_count"] == 1
    assert status["items"][0]["current_state"]["ready"] is True

    source = pilot.verify_pilot_runtime_source(receipt["receipt_id"], receipt["startup_fingerprint"])
    assert source["valid"] is True
    assert source["evidence_class"] == "canonical_runtime"
    evidence_payload = {
        "request_actor": _ACTOR,
        "requirement_id": COPY_CREATION_REQUIREMENT,
        "proof_kind": COPY_CREATION_PROOF_KIND,
        "source_receipt_id": receipt["receipt_id"],
        "source_receipt_fingerprint": receipt["startup_fingerprint"],
        "trace_id": "trace-canonical-runtime-evidence",
        "dry_run": True,
        "record_fingerprint": "",
        "confirm_runtime_evidence": False,
    }
    evidence_plan = record_runtime_evidence(evidence_payload, actor=_ACTOR, stage17_closed=True)
    assert evidence_plan["ok"] is True
    recorded = record_runtime_evidence(
        {
            **evidence_payload,
            "dry_run": False,
            "record_fingerprint": evidence_plan["record_fingerprint"],
            "confirm_runtime_evidence": True,
        },
        actor=_ACTOR,
        stage17_closed=True,
    )
    assert recorded["writes_receipt"] is True

    stopped = client.post(
        pilot.PILOT_RUNTIME_STOP_ROUTE,
        json={
            "request_actor": _ACTOR,
            "pilot_lease_id": _LEASE,
            "startup_receipt_id": receipt["receipt_id"],
            "confirm_stop": True,
        },
    ).json()
    assert stopped["ok"] is True, stopped
    assert stopped["status"] == "stopped"
    assert process_identity(receipt["pid"]) == {}
    assert vertical_runtime["registry"].state(_LEASE).value == "sealed"
    assert not (vertical_runtime["tenant_root"] / "data" / "pilot_inputs" / _RUN / "work_items.json").is_symlink()

    replay = client.post(pilot.PILOT_RUNTIME_START_ROUTE, json=vertical_runtime["payload"]).json()
    assert replay["error"] == "api_permission_denied"


@pytest.mark.parametrize("observed_parent", [4100, 4200])
def test_runtime_parent_accepts_direct_controller_or_trusted_launcher(observed_parent: int) -> None:
    assert pilot._trusted_parent_identity(
        observed_parent,
        observed_parent_pid=observed_parent,
        launcher_pid=4100,
        controller_pid=4200,
    )


def test_runtime_parent_rejects_unobserved_or_untrusted_parent() -> None:
    assert not pilot._trusted_parent_identity(
        4100,
        observed_parent_pid=4200,
        launcher_pid=4100,
        controller_pid=4200,
    )
    assert not pilot._trusted_parent_identity(
        4300,
        observed_parent_pid=4300,
        launcher_pid=4100,
        controller_pid=4200,
    )


def test_approval_schema_failure_seals_consumed_lease_without_start(vertical_runtime: dict[str, Any]) -> None:
    approval_path = (
        vertical_runtime["data_root"] / "approvals" / "approved" / f"{vertical_runtime['payload']['approval_id']}.json"
    )
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["injected"] = True
    approval_path.write_text(json.dumps(approval), encoding="utf-8")

    result = TestClient(create_app()).post(pilot.PILOT_RUNTIME_START_ROUTE, json=vertical_runtime["payload"]).json()
    assert result["error"] == "managed_copy_pilot_runtime_approval_binding_mismatch"
    assert vertical_runtime["registry"].state(_LEASE).value == "sealed"
    assert not list(vertical_runtime["tenant_root"].glob("receipts/pilot_runtime/*/startup.json"))


def test_canonical_source_rejects_tamper_stale_process_and_lineage(
    vertical_runtime: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    started = TestClient(create_app()).post(pilot.PILOT_RUNTIME_START_ROUTE, json=vertical_runtime["payload"]).json()
    receipt = started["receipt"]

    def current_identity(_pid: int) -> dict[str, int]:
        return {
            "creation_token": receipt["process_creation_token"],
            "parent_pid": receipt["parent_pid"],
        }

    monkeypatch.setattr(pilot, "process_identity", current_identity)
    state_dir = vertical_runtime["data_root"] / receipt["state_path"]
    heartbeat_path = state_dir / "heartbeat.json"
    heartbeat = json.loads(heartbeat_path.read_text(encoding="utf-8"))
    heartbeat["observed_at_unix_ms"] = int(time.time() * 1000)
    heartbeat_path.write_text(json.dumps(heartbeat), encoding="utf-8")
    operation_path = state_dir / "operation.json"
    original_operation = operation_path.read_text(encoding="utf-8")
    operation_path.write_text('{"status":"completed"}', encoding="utf-8")
    assert (
        "operation"
        in pilot.verify_pilot_runtime_source(receipt["receipt_id"], receipt["startup_fingerprint"])["blocker"]
    )
    operation_path.write_text(original_operation, encoding="utf-8")

    original_heartbeat = heartbeat_path.read_text(encoding="utf-8")
    heartbeat = json.loads(heartbeat_path.read_text(encoding="utf-8"))
    heartbeat["observed_at_unix_ms"] = 1
    heartbeat_path.write_text(json.dumps(heartbeat), encoding="utf-8")
    assert (
        pilot.verify_pilot_runtime_source(receipt["receipt_id"], receipt["startup_fingerprint"])["blocker"]
        == "managed_copy_pilot_runtime_source_heartbeat_stale"
    )
    heartbeat_path.write_text(original_heartbeat, encoding="utf-8")

    monkeypatch.setattr(pilot, "process_identity", lambda _pid: {"creation_token": 1, "parent_pid": os.getpid()})
    assert (
        pilot.verify_pilot_runtime_source(receipt["receipt_id"], receipt["startup_fingerprint"])["blocker"]
        == "managed_copy_pilot_runtime_source_process_mismatch"
    )
    monkeypatch.setattr(pilot, "process_identity", current_identity)

    pilot._PILOT_LEASES.pop(_LEASE)
    assert (
        pilot.verify_pilot_runtime_source(receipt["receipt_id"], receipt["startup_fingerprint"])["blocker"]
        == "managed_copy_pilot_runtime_source_lineage_mismatch"
    )


def test_interrupted_owned_process_can_be_finalized_without_pid_reuse(vertical_runtime: dict[str, Any]) -> None:
    client = TestClient(create_app())
    started = client.post(pilot.PILOT_RUNTIME_START_ROUTE, json=vertical_runtime["payload"]).json()
    receipt = started["receipt"]
    assert terminate_owned_process(
        receipt["pid"], creation_token=receipt["process_creation_token"], timeout_seconds=2.0
    )
    assert process_identity(receipt["pid"]) == {}

    stopped = client.post(
        pilot.PILOT_RUNTIME_STOP_ROUTE,
        json={
            "request_actor": _ACTOR,
            "pilot_lease_id": _LEASE,
            "startup_receipt_id": receipt["receipt_id"],
            "confirm_stop": True,
        },
    ).json()
    assert stopped["ok"] is True
    assert stopped["status"] == "already_exited"
    assert vertical_runtime["registry"].state(_LEASE).value == "sealed"
