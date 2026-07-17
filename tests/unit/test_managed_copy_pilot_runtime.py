from __future__ import annotations

import json
import os
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


@pytest.fixture
def vertical_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    data_root = tmp_path.parent / f"mpr_{uuid.uuid4().hex[:8]}"
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
    now = int(time.time() * 1000)
    registry.issue(
        PilotScopeLease(
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
            ),
            issued_at_ms=now - 1_000,
            expires_at_ms=now + 60_000,
            runtime_nonce="runtime-nonce-vertical-001",
            operator_decision_fingerprint=_HASH_B,
        )
    )
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
