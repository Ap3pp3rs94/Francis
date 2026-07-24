from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import francis.api.routes.managed_copies as managed_routes
import francis.managed_copies as managed_copies_core
import francis.managed_copy_pilot_runtime as pilot
from francis.api.app import create_app
from francis.governance.pilot_scope_lease import (
    PilotLeaseBinding,
    PilotLeaseState,
    PilotScopeLease,
    PilotScopeLeaseRegistry,
)
from francis.managed_copy_runtime_evidence import (
    COPY_CREATION_PROOF_KIND,
    COPY_CREATION_REQUIREMENT,
)
from francis.managed_copy_runtime import (
    INPUT_CONTRACT,
    TENANT_BOUNDARY_INPUT_CONTRACT,
    build_work_briefing,
)
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


def _lease_descriptor(*, issuer: str, now: int, lease_id: str = "lease-api-001") -> dict[str, Any]:
    return {
        "contract": pilot.PILOT_LEASE_ISSUE_CONTRACT,
        "issuer_actor": issuer,
        "lease_id": lease_id,
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


def _write_lease_approval(
    data_root: Path,
    *,
    issuer: str,
    now: int,
    approval_id: str = "lease-approval-api-001",
    descriptor: dict[str, Any] | None = None,
    changes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    exact_descriptor = descriptor or _lease_descriptor(issuer=issuer, now=now)
    approval = {
        "id": approval_id,
        "ts": time.time(),
        "action": pilot.PILOT_LEASE_ISSUE_ACTION,
        "reason": "exact bounded process-local pilot lease",
        "payload": {
            "contract": pilot.PILOT_LEASE_ISSUE_CONTRACT,
            "descriptor": exact_descriptor,
            "descriptor_fingerprint": pilot._fingerprint(exact_descriptor),
            "expires_at_unix_ms": now + 60_000,
            "revoked": False,
        },
        "status": "approved",
        "decision": "approve",
        "decision_actor": "test.operator",
        "decided_ts": time.time(),
    }
    for key, value in (changes or {}).items():
        if key.startswith("payload."):
            approval["payload"][key.removeprefix("payload.")] = value
        else:
            approval[key] = value
    path = data_root / "approvals" / "approved" / f"{approval_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(approval), encoding="utf-8")
    return approval


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
        timeout=15,
    )

    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    briefing = json.loads((state_dir / "briefing.json").read_text(encoding="utf-8"))
    operation = json.loads((state_dir / "operation.json").read_text(encoding="utf-8"))
    assert briefing["next_action"]["id"] == "work-1"
    assert operation["status"] == "completed"
    assert operation["fixture_runtime"] is False


@pytest.mark.parametrize(
    ("sibling_exists", "expected_absent"),
    [(False, True), (True, False)],
)
def test_container_entrypoint_executes_fixed_tenant_boundary_probe(
    tmp_path: Path,
    sibling_exists: bool,
    expected_absent: bool,
) -> None:
    tenant_root = tmp_path / "francis"
    input_path = tenant_root / "tenant" / "work_items.json"
    state_dir = tenant_root / "state"
    input_path.parent.mkdir(parents=True)
    state_dir.mkdir()
    if sibling_exists:
        (tenant_root.parent / "tenant-b").mkdir()
    input_path.write_text(
        json.dumps(
            {
                "contract": TENANT_BOUNDARY_INPUT_CONTRACT,
                "probe_id": "tenant-boundary-process-001",
                "tenant_marker": "synthetic-tenant-a-marker",
            }
        ),
        encoding="utf-8",
    )
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
            "managed_copy_tenant_boundary",
            "--tenant-key",
            "d" * 64,
            "--pilot-run-id",
            "tenant-boundary-process-run",
            "--runtime-nonce",
            "tenant-boundary-process-nonce",
            "--lease-seconds",
            "1",
        ],
        cwd=tmp_path,
        env={"PYTHONNOUSERSITE": "1", "PYTHONUTF8": "1"},
        capture_output=True,
        check=False,
        timeout=15,
    )

    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    output = json.loads((state_dir / "tenant_boundary_probe.json").read_text(encoding="utf-8"))
    operation = json.loads((state_dir / "operation.json").read_text(encoding="utf-8"))
    assert output["approved_tenant_input_read"] is True
    assert output["sibling_tenant_boundary_absent"] is expected_absent
    assert output["bounded_cross_tenant_denial"] is expected_absent
    assert output["comprehensive_tenant_isolation_proven"] is False
    assert operation["operation"] == "tenant_boundary_probe"


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
        'LABEL francis.runtime.program_sha256="7c939cba3e0ab62fc2c950d7488de852e821294126af20cae7b9b2d4dee04485"',
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
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({_ACTOR: [pilot.PILOT_RUNTIME_SCOPE, "managed_copies.runtime_evidence.write"]}),
    )
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
    original_evidence_contract = managed_copies_core.managed_copy_runtime_evidence_contract_snapshot
    monkeypatch.setattr(
        managed_copies_core,
        "managed_copy_runtime_evidence_contract_snapshot",
        lambda: {
            **original_evidence_contract(),
            "stage17_closed_by_receipt": True,
            "stage17_blocker": "",
        },
    )
    registry = PilotScopeLeaseRegistry()
    monkeypatch.setattr(pilot, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(managed_routes, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(pilot, "_PILOT_LEASES", {})
    monkeypatch.setattr(pilot, "_PILOT_LEASE_APPROVAL_FINGERPRINTS", {})
    monkeypatch.setattr(pilot, "_PILOT_LEASE_ISSUERS", {})
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


def test_process_local_lease_lifecycle_and_restart_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    operator = "lease.operator"
    data_root = tmp_path / "lease-lifecycle"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({operator: [pilot.PILOT_LEASE_MANAGE_SCOPE]}))
    registry = PilotScopeLeaseRegistry()
    monkeypatch.setattr(pilot, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(managed_routes, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(pilot, "_PILOT_LEASES", {})
    monkeypatch.setattr(pilot, "_PILOT_LEASE_APPROVAL_FINGERPRINTS", {})
    monkeypatch.setattr(pilot, "_PILOT_LEASE_ISSUERS", {})
    now = int(time.time() * 1000)
    approval_id = "lease-approval-api-001"
    _write_lease_approval(data_root, issuer=operator, now=now, approval_id=approval_id)
    payload = {
        "request_actor": operator,
        "approval_id": approval_id,
        "confirm_issue": True,
    }
    client = TestClient(create_app())

    issued = client.post("/managed-copies/pilot-runtime-lease-issue", json=payload).json()
    assert issued["ok"] is True
    assert issued["writes_persistent_state"] is False
    assert set(issued["lease"]) == {"lease_id", "actor_id", "pilot_run_id", "expires_at_ms", "state"}
    lease_id = issued["lease"]["lease_id"]
    status = client.post(
        "/managed-copies/pilot-runtime-lease-status",
        json={"request_actor": operator, "lease_id": lease_id},
    ).json()
    assert status["status"] == "active"
    revoked = client.post(
        "/managed-copies/pilot-runtime-lease-revoke",
        json={"request_actor": operator, "lease_id": lease_id},
    ).json()
    assert revoked["status"] == "revoked"

    monkeypatch.setattr(pilot, "PILOT_RUNTIME_LEASES", PilotScopeLeaseRegistry())
    monkeypatch.setattr(pilot, "_PILOT_LEASES", {})
    monkeypatch.setattr(pilot, "_PILOT_LEASE_APPROVAL_FINGERPRINTS", {})
    monkeypatch.setattr(pilot, "_PILOT_LEASE_ISSUERS", {})
    assert (
        pilot.pilot_runtime_lease_status({"request_actor": operator, "lease_id": lease_id})["error"]
        == "missing_pilot_lease"
    )


@pytest.mark.parametrize(
    "forged_field",
    [
        "actor_id",
        "package_id",
        "pilot_run_id",
        "bindings",
        "issued_at_ms",
        "expires_at_ms",
        "runtime_nonce",
        "operator_decision_fingerprint",
    ],
)
def test_lease_issue_rejects_caller_supplied_descriptor_fields_before_registry_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    forged_field: str,
) -> None:
    operator = "lease.operator"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({operator: [pilot.PILOT_LEASE_MANAGE_SCOPE]}))
    registry = PilotScopeLeaseRegistry()
    monkeypatch.setattr(pilot, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(managed_routes, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(pilot, "_PILOT_LEASES", {})

    body = (
        TestClient(create_app())
        .post(
            "/managed-copies/pilot-runtime-lease-issue",
            json={
                "request_actor": operator,
                "approval_id": "lease-approval-api-001",
                "confirm_issue": True,
                forged_field: "forged",
            },
        )
        .json()
    )

    assert body["error"] == "managed_copy_pilot_lease_payload_schema_invalid"
    assert pilot._PILOT_LEASES == {}


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"action": "managed_copies.pilot_lease.wrong"}, "managed_copy_pilot_lease_approval_binding_mismatch"),
        ({"status": "pending"}, "managed_copy_pilot_lease_approval_binding_mismatch"),
        ({"decision": "reject"}, "managed_copy_pilot_lease_approval_binding_mismatch"),
        ({"payload.revoked": True}, "managed_copy_pilot_lease_approval_binding_mismatch"),
        ({"payload.expires_at_unix_ms": 1}, "managed_copy_pilot_lease_approval_expired"),
        ({"injected": True}, "managed_copy_pilot_lease_approval_binding_mismatch"),
    ],
)
def test_lease_issue_rejects_invalid_approval(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    changes: dict[str, Any],
    expected: str,
) -> None:
    operator = "lease.operator"
    now = int(time.time() * 1000)
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    registry = PilotScopeLeaseRegistry()
    monkeypatch.setattr(pilot, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(pilot, "_PILOT_LEASES", {})
    _write_lease_approval(tmp_path, issuer=operator, now=now, changes=changes)

    result = pilot.issue_pilot_runtime_lease(
        {"request_actor": operator, "approval_id": "lease-approval-api-001", "confirm_issue": True}
    )

    assert result["error"] == expected
    assert pilot._PILOT_LEASES == {}


def test_lease_issue_rejects_tampered_descriptor_and_changed_under_lock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    operator = "lease.operator"
    now = int(time.time() * 1000)
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    registry = PilotScopeLeaseRegistry()
    monkeypatch.setattr(pilot, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(pilot, "_PILOT_LEASES", {})
    request = {"request_actor": operator, "approval_id": "lease-approval-api-001", "confirm_issue": True}
    assert pilot.issue_pilot_runtime_lease(request)["error"] == ("managed_copy_pilot_lease_approval_binding_mismatch")
    approval = _write_lease_approval(tmp_path, issuer=operator, now=now)
    approval["payload"]["descriptor"]["package_id"] = "tampered"
    path = tmp_path / "approvals" / "approved" / "lease-approval-api-001.json"
    path.write_text(json.dumps(approval), encoding="utf-8")
    assert pilot.issue_pilot_runtime_lease(request)["error"] == (
        "managed_copy_pilot_lease_approval_descriptor_tampered"
    )

    valid = _write_lease_approval(tmp_path, issuer=operator, now=now)
    changed = json.loads(json.dumps(valid))
    changed["reason"] = "changed under lock"
    reads = iter((valid, changed))
    monkeypatch.setattr(pilot, "_read_json", lambda _path: next(reads))
    assert pilot.issue_pilot_runtime_lease(request)["error"] == ("managed_copy_pilot_lease_approval_changed_under_lock")
    assert pilot._PILOT_LEASES == {}


def test_lease_issue_exact_replay_is_idempotent_and_conflicting_replay_denied(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    operator = "lease.operator"
    now = int(time.time() * 1000)
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    registry = PilotScopeLeaseRegistry()
    monkeypatch.setattr(pilot, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(pilot, "_PILOT_LEASES", {})
    monkeypatch.setattr(pilot, "_PILOT_LEASE_APPROVAL_FINGERPRINTS", {})
    monkeypatch.setattr(pilot, "_PILOT_LEASE_ISSUERS", {})
    request = {"request_actor": operator, "approval_id": "lease-approval-api-001", "confirm_issue": True}
    _write_lease_approval(tmp_path, issuer=operator, now=now)

    assert pilot.issue_pilot_runtime_lease(request)["status"] == "issued"
    assert pilot.issue_pilot_runtime_lease(request)["status"] == "already_issued"
    descriptor = _lease_descriptor(issuer=operator, now=now)
    descriptor["package_id"] = "conflicting-package"
    _write_lease_approval(tmp_path, issuer=operator, now=now, descriptor=descriptor)
    assert pilot.issue_pilot_runtime_lease(request)["error"] == "managed_copy_pilot_lease_conflicting_replay"
    _write_lease_approval(tmp_path, issuer=operator, now=now)
    for route, action in (
        (pilot.PILOT_RUNTIME_START_ROUTE, pilot.PILOT_RUNTIME_START_ACTION),
        (pilot.PILOT_RUNTIME_PROPOSAL_ROUTE, pilot.PILOT_RUNTIME_PROPOSAL_ACTION),
    ):
        decision = registry.authorize_binding(
            lease_id="lease-api-001",
            actor_id=_ACTOR,
            scope=pilot.PILOT_RUNTIME_SCOPE,
            route=route,
            method="POST",
            action=action,
        )
        assert decision.allowed is True
    assert registry.state("lease-api-001") is PilotLeaseState.CONSUMED
    assert pilot.issue_pilot_runtime_lease(request)["error"] == "managed_copy_pilot_lease_conflicting_replay"


def test_lease_status_and_revoke_enforce_issuer_and_do_not_leak(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    operator = "lease.operator"
    other = "lease.other"
    now = int(time.time() * 1000)
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({operator: [pilot.PILOT_LEASE_MANAGE_SCOPE], other: [pilot.PILOT_LEASE_MANAGE_SCOPE]}),
    )
    registry = PilotScopeLeaseRegistry()
    monkeypatch.setattr(pilot, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(managed_routes, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(pilot, "_PILOT_LEASES", {})
    monkeypatch.setattr(pilot, "_PILOT_LEASE_APPROVAL_FINGERPRINTS", {})
    monkeypatch.setattr(pilot, "_PILOT_LEASE_ISSUERS", {})
    _write_lease_approval(tmp_path, issuer=operator, now=now)
    client = TestClient(create_app())
    issued = client.post(
        "/managed-copies/pilot-runtime-lease-issue",
        json={"request_actor": operator, "approval_id": "lease-approval-api-001", "confirm_issue": True},
    ).json()
    lease_id = issued["lease"]["lease_id"]

    for route in ("pilot-runtime-lease-status", "pilot-runtime-lease-revoke"):
        denied = client.post(f"/managed-copies/{route}", json={"request_actor": other, "lease_id": lease_id}).json()
        assert denied["error"] == "managed_copy_pilot_lease_manager_mismatch"
    status = client.post(
        "/managed-copies/pilot-runtime-lease-status",
        json={"request_actor": operator, "lease_id": lease_id},
    ).json()
    serialized = json.dumps(status)
    assert set(status["lease"]) == {"lease_id", "actor_id", "pilot_run_id", "expires_at_ms", "state"}
    assert "package-api-001" not in serialized
    assert _HASH_A not in serialized
    assert _HASH_B not in serialized
    assert "runtime-nonce-api-001" not in serialized


def test_proposal_authorization_does_not_consume_start_binding(vertical_runtime: dict[str, Any]) -> None:
    payload = {**vertical_runtime["payload"], "confirm_start": False}
    before = vertical_runtime["registry"].state(_LEASE)
    proposed = TestClient(create_app()).post(pilot.PILOT_RUNTIME_PROPOSAL_ROUTE, json=payload).json()
    after = vertical_runtime["registry"].state(_LEASE)

    assert proposed["ok"] is True, proposed
    assert proposed["starts_runtime"] is False
    assert before == after
    assert vertical_runtime["registry"].state(_LEASE).value == "active"


def test_start_revalidates_concurrent_revoke_before_launch(
    vertical_runtime: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    original = pilot._pilot_lease_start_blocker

    def revoke_then_check(descriptor: dict[str, Any]) -> str:
        vertical_runtime["registry"].revoke(_LEASE)
        return original(descriptor)

    monkeypatch.setattr(pilot, "_pilot_lease_start_blocker", revoke_then_check)
    monkeypatch.setattr(pilot, "_launch", lambda *_args, **_kwargs: pytest.fail("launch must not run"))

    result = TestClient(create_app()).post(pilot.PILOT_RUNTIME_START_ROUTE, json=vertical_runtime["payload"]).json()

    assert result["error"] == "managed_copy_pilot_runtime_lease_revoked_under_lock"
    assert not list(vertical_runtime["tenant_root"].glob("data/pilot_inputs/*"))


def test_start_revalidates_expiry_before_launch(
    vertical_runtime: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    original = pilot._pilot_lease_start_blocker
    lease = pilot._PILOT_LEASES[_LEASE]

    def expire_then_check(descriptor: dict[str, Any]) -> str:
        vertical_runtime["registry"]._clock_ms = lambda: lease.expires_at_ms + 1
        return original(descriptor)

    monkeypatch.setattr(pilot, "_pilot_lease_start_blocker", expire_then_check)
    monkeypatch.setattr(pilot, "_launch", lambda *_args, **_kwargs: pytest.fail("launch must not run"))

    result = TestClient(create_app()).post(pilot.PILOT_RUNTIME_START_ROUTE, json=vertical_runtime["payload"]).json()

    assert result["error"] == "managed_copy_pilot_runtime_lease_expired_under_lock"
    assert not list(vertical_runtime["tenant_root"].glob("data/pilot_inputs/*"))


def test_start_revalidates_lease_lineage_drift_before_launch(
    vertical_runtime: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    original_context = vertical_runtime["registry"].lease_context

    def drifted_context(lease_id: object) -> dict[str, str]:
        context = original_context(lease_id)
        return {**context, "package_id": "drifted-package"}

    original_blocker = pilot._pilot_lease_start_blocker

    def drift_then_check(descriptor: dict[str, Any]) -> str:
        monkeypatch.setattr(vertical_runtime["registry"], "lease_context", drifted_context)
        return original_blocker(descriptor)

    monkeypatch.setattr(pilot, "_pilot_lease_start_blocker", drift_then_check)
    monkeypatch.setattr(pilot, "_launch", lambda *_args, **_kwargs: pytest.fail("launch must not run"))

    result = TestClient(create_app()).post(pilot.PILOT_RUNTIME_START_ROUTE, json=vertical_runtime["payload"]).json()

    assert result["error"] == "managed_copy_pilot_runtime_lease_lineage_changed_under_lock"
    assert not list(vertical_runtime["tenant_root"].glob("data/pilot_inputs/*"))


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
    evidence_plan = client.post("/managed-copies/runtime-evidence-readback", json=evidence_payload).json()
    assert evidence_plan["ok"] is True, evidence_plan
    recorded = client.post(
        "/managed-copies/runtime-evidence-readback",
        json={
            **evidence_payload,
            "dry_run": False,
            "record_fingerprint": evidence_plan["record_fingerprint"],
            "confirm_runtime_evidence": True,
        },
    ).json()
    assert recorded["writes_receipt"] is True
    readback = client.get("/managed-copies/runtime-evidence-readbacks").json()
    assert readback["count"] == 1
    copy_check = next(item for item in readback["checks"] if item["id"] == COPY_CREATION_REQUIREMENT)
    assert copy_check["passed"] is True

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


@pytest.fixture
def canonical_source(
    vertical_runtime: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> dict[str, Any]:
    started = TestClient(create_app()).post(pilot.PILOT_RUNTIME_START_ROUTE, json=vertical_runtime["payload"]).json()
    assert started.get("ok") is True, started
    receipt = started["receipt"]
    assert started["ok"] is True, started

    def cleanup_child() -> None:
        if process_identity(receipt["pid"]):
            assert terminate_owned_process(
                receipt["pid"],
                creation_token=receipt["process_creation_token"],
                timeout_seconds=2.0,
            )
        assert process_identity(receipt["pid"]) == {}

    request.addfinalizer(cleanup_child)
    state_dir = vertical_runtime["data_root"] / receipt["state_path"]
    approval_path = (
        vertical_runtime["data_root"] / "approvals" / "approved" / f"{vertical_runtime['payload']['approval_id']}.json"
    )
    paths = {
        "startup": state_dir / "startup.json",
        "heartbeat": state_dir / "heartbeat.json",
        "operation": state_dir / "operation.json",
        "briefing": state_dir / "briefing.json",
        "approval": approval_path,
    }

    def read_snapshot(path: Path) -> dict[str, Any]:
        for _ in range(100):
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                time.sleep(0.01)
        pytest.fail(f"could not snapshot runtime source: {path.name}")

    records = {key: read_snapshot(path) for key, path in paths.items()}
    records["heartbeat"]["observed_at_unix_ms"] = int(time.time() * 1000)
    original_read_json = pilot._read_json
    records_by_path = {str(path.resolve()): key for key, path in paths.items()}

    def frozen_read(path: Path) -> dict[str, Any]:
        key = records_by_path.get(str(path.resolve()))
        return json.loads(json.dumps(records[key])) if key else original_read_json(path)

    identities = {
        receipt["pid"]: {
            "creation_token": receipt["process_creation_token"],
            "parent_pid": receipt["parent_pid"],
        },
        receipt["controller_pid"]: {
            "creation_token": receipt["controller_creation_token"],
            "parent_pid": 0,
        },
    }

    monkeypatch.setattr(pilot, "_read_json", frozen_read)
    monkeypatch.setattr(pilot, "process_identity", lambda pid: dict(identities.get(pid, {})))
    fixed_now = records["heartbeat"]["observed_at_unix_ms"] / 1000 + 0.1
    monkeypatch.setattr(pilot.time, "time", lambda: fixed_now)
    yield {
        "receipt": receipt,
        "records": records,
        "identities": identities,
        "vertical_runtime": vertical_runtime,
    }


def _verify_canonical_source(context: dict[str, Any]) -> dict[str, Any]:
    receipt = context["receipt"]
    return pilot.verify_pilot_runtime_source(receipt["receipt_id"], receipt["startup_fingerprint"])


def test_verified_pilot_source_exposes_independent_authority_lineage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    now = int(time.time() * 1000)
    lease = PilotScopeLease(
        lease_id="authority-lineage-lease",
        actor_id=_ACTOR,
        package_id="authority-lineage-package",
        package_fingerprint=_HASH_A,
        pilot_run_id="authority-lineage-run",
        bindings=(
            PilotLeaseBinding(
                scope=pilot.PILOT_RUNTIME_SCOPE,
                route=pilot.PILOT_RUNTIME_START_ROUTE,
                method="POST",
                action=pilot.PILOT_RUNTIME_START_ACTION,
            ),
        ),
        issued_at_ms=now - 1,
        expires_at_ms=now + 60_000,
        runtime_nonce="authority-lineage-nonce",
        operator_decision_fingerprint=_HASH_B,
    )
    registry = PilotScopeLeaseRegistry()
    assert registry.issue(lease).lease_id == lease.lease_id
    monkeypatch.setattr(pilot, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(pilot, "_PILOT_LEASES", {lease.lease_id: lease})
    receipt = {
        "tenant_key": "c" * 64,
        "copy_id": "managed_copy_authority_lineage",
        "pilot_run_id": lease.pilot_run_id,
        "runtime_identity": pilot.RUNTIME_IDENTITY,
        "receipt_id": "pilot-runtime-authority-lineage",
        "startup_fingerprint": _HASH_A,
        "approval_id": "pilot-runtime-authority-approval",
        "pilot_lease_id": lease.lease_id,
    }
    approval = {"id": receipt["approval_id"], "status": "approved"}
    monkeypatch.setattr(pilot, "verify_pilot_runtime_source", lambda *_args: {"valid": True})
    monkeypatch.setattr(pilot, "_raw_startup_receipt", lambda _receipt_id: dict(receipt))
    monkeypatch.setattr(pilot, "_read_json", lambda _path: dict(approval))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))

    result = pilot.verify_pilot_runtime_authority_lineage(receipt["receipt_id"], receipt["startup_fingerprint"])

    assert result["valid"] is True
    assert result["authority_lineage"] == {
        "tenant_key": receipt["tenant_key"],
        "copy_id": receipt["copy_id"],
        "pilot_run_id": receipt["pilot_run_id"],
        "runtime_identity": receipt["runtime_identity"],
        "runtime_start_receipt_id": receipt["receipt_id"],
        "runtime_start_receipt_fingerprint": receipt["startup_fingerprint"],
        "operator_approval_receipt_id": receipt["approval_id"],
        "operator_approval_receipt_fingerprint": pilot._fingerprint(approval),
        "actor_scope_lease_id": receipt["pilot_lease_id"],
        "actor_scope_lease_fingerprint": pilot._pilot_lease_authority_fingerprint(
            lease,
            effective_state=PilotLeaseState.ACTIVE,
        ),
    }


def test_pilot_authority_fingerprint_binds_permissions_expiry_and_consumption() -> None:
    now = int(time.time() * 1000)
    binding = PilotLeaseBinding(
        scope=pilot.PILOT_RUNTIME_SCOPE,
        route=pilot.PILOT_RUNTIME_START_ROUTE,
        method="POST",
        action=pilot.PILOT_RUNTIME_START_ACTION,
    )
    lease = PilotScopeLease(
        lease_id="authority-fingerprint-lease",
        actor_id=_ACTOR,
        package_id="authority-fingerprint-package",
        package_fingerprint=_HASH_A,
        pilot_run_id="authority-fingerprint-run",
        bindings=(binding,),
        issued_at_ms=now,
        expires_at_ms=now + 60_000,
        runtime_nonce="authority-fingerprint-nonce",
        operator_decision_fingerprint=_HASH_B,
    )
    fingerprint = pilot._pilot_lease_authority_fingerprint(
        lease,
        effective_state=PilotLeaseState.ACTIVE,
    )
    changed_binding = replace(
        lease,
        bindings=(
            replace(
                binding,
                route=pilot.PILOT_RUNTIME_STOP_ROUTE,
                action=pilot.PILOT_RUNTIME_STOP_ACTION,
            ),
        ),
    )
    consumed = replace(lease, consumed_bindings=frozenset({binding}))

    assert (
        pilot._pilot_lease_authority_fingerprint(
            changed_binding,
            effective_state=PilotLeaseState.ACTIVE,
        )
        != fingerprint
    )
    assert (
        pilot._pilot_lease_authority_fingerprint(
            replace(lease, expires_at_ms=lease.expires_at_ms + 1),
            effective_state=PilotLeaseState.ACTIVE,
        )
        != fingerprint
    )
    assert (
        pilot._pilot_lease_authority_fingerprint(
            consumed,
            effective_state=PilotLeaseState.CONSUMED,
        )
        != fingerprint
    )


def test_canonical_source_rejects_stale_heartbeat(canonical_source: dict[str, Any]) -> None:
    canonical_source["records"]["heartbeat"]["observed_at_unix_ms"] = 1
    assert _verify_canonical_source(canonical_source)["blocker"] == (
        "managed_copy_pilot_runtime_source_heartbeat_stale"
    )


def test_canonical_source_rejects_operation_tamper(canonical_source: dict[str, Any]) -> None:
    canonical_source["records"]["operation"] = {"status": "completed"}
    assert "operation" in _verify_canonical_source(canonical_source)["blocker"]


def test_canonical_source_rejects_briefing_output_tamper(canonical_source: dict[str, Any]) -> None:
    canonical_source["records"]["briefing"]["next_action"]["title"] = "tampered output"
    assert _verify_canonical_source(canonical_source)["blocker"] == "managed_copy_pilot_runtime_output_tampered"


@pytest.mark.parametrize(("field", "value"), [("expires_at_unix_ms", 1), ("revoked", True)])
def test_canonical_source_rejects_approval_expiry_or_revoke(
    canonical_source: dict[str, Any],
    field: str,
    value: object,
) -> None:
    canonical_source["records"]["approval"]["payload"][field] = value
    assert _verify_canonical_source(canonical_source)["blocker"] == (
        "managed_copy_pilot_runtime_source_approval_lineage_mismatch"
    )


def test_canonical_source_rejects_provision_drift(
    canonical_source: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    original = pilot.managed_copy_provision_for_copy
    monkeypatch.setattr(
        pilot,
        "managed_copy_provision_for_copy",
        lambda *args, **kwargs: {**original(*args, **kwargs), "provision_fingerprint": "0" * 64},
    )
    assert _verify_canonical_source(canonical_source)["blocker"] == (
        "managed_copy_pilot_runtime_source_lineage_mismatch"
    )


def test_canonical_source_rejects_isolation_drift(
    canonical_source: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    original = pilot.latest_managed_copy_isolation_verification_for_provision
    monkeypatch.setattr(
        pilot,
        "latest_managed_copy_isolation_verification_for_provision",
        lambda *args, **kwargs: {**original(*args, **kwargs), "verification_fingerprint": "0" * 64},
    )
    assert _verify_canonical_source(canonical_source)["blocker"] == (
        "managed_copy_pilot_runtime_source_approval_lineage_mismatch"
    )


def test_canonical_source_rejects_unrelated_parent_controller(canonical_source: dict[str, Any]) -> None:
    receipt = canonical_source["receipt"]
    canonical_source["identities"][receipt["pid"]]["parent_pid"] = 2**20
    assert _verify_canonical_source(canonical_source)["blocker"] == (
        "managed_copy_pilot_runtime_source_controller_mismatch"
    )


def test_canonical_source_rejects_exact_schema_injection(canonical_source: dict[str, Any]) -> None:
    startup = canonical_source["records"]["startup"]
    startup["injected"] = True
    startup["startup_fingerprint"] = pilot._fingerprint(
        {key: value for key, value in startup.items() if key != "startup_fingerprint"}
    )
    receipt = canonical_source["receipt"]
    result = pilot.verify_pilot_runtime_source(receipt["receipt_id"], startup["startup_fingerprint"])
    assert result["blocker"] == "managed_copy_pilot_runtime_source_receipt_invalid"


def test_canonical_source_explicitly_rejects_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    data_root = Path(pilot.__file__).parents[2] / "data" / "test_runs" / f"fixture_{uuid.uuid4().hex[:8]}"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    path = data_root / "managed_copies" / "tenants" / ("a" * 64) / "receipts" / "pilot_runtime" / "fixture"
    path.mkdir(parents=True)
    (path / "startup.json").write_text(
        json.dumps({"receipt_id": "fixture-startup-001", "fixture_runtime": True}),
        encoding="utf-8",
    )

    result = pilot.verify_pilot_runtime_source("fixture-startup-001", "0" * 64)

    assert result["blocker"] == "managed_copy_pilot_runtime_fixture_source_rejected"


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
