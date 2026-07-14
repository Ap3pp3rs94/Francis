from __future__ import annotations

import inspect
import json
from pathlib import Path

from fastapi.testclient import TestClient

import francis.api.routes.simulation as simulation_route
from francis.api.app import create_app


def _client(
    monkeypatch,
    tmp_path: Path,
    *,
    actor_scopes: dict[str, list[str]],
) -> TestClient:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "francis_data"))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps(actor_scopes))
    return TestClient(create_app())


def test_simulation_virtual_workfield_requires_read_scope(monkeypatch, tmp_path: Path) -> None:
    client = _client(
        monkeypatch,
        tmp_path,
        actor_scopes={
            "compute.submitter": ["compute:submit"],
            "simulation.reader": ["simulation:virtual-workfield:read"],
        },
    )

    missing_actor = client.get("/simulation/virtual-workfield").json()
    wrong_scope = client.get(
        "/simulation/virtual-workfield",
        params={"actor": "compute.submitter"},
    ).json()

    assert missing_actor["ok"] is False
    assert missing_actor["status"] == "denied"
    assert missing_actor["error"] == "api_permission_denied"
    assert missing_actor["denial_reason"] == "missing_actor"
    assert missing_actor["governance"]["required_scope"] == "simulation:virtual-workfield:read"
    assert missing_actor["governance"]["uses_compute_substrate_service"] is False
    assert wrong_scope["ok"] is False
    assert wrong_scope["error"] == "api_permission_denied"
    assert wrong_scope["governance"]["required_scope"] == "simulation:virtual-workfield:read"
    assert not (tmp_path / "francis_data").exists()


def test_simulation_virtual_workfield_returns_contract_only_projection(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path, actor_scopes={"simulation.reader": ["simulation:virtual-workfield:read"]})

    body = client.get(
        "/simulation/virtual-workfield",
        params={
            "actor": "simulation.reader",
            "plan_id": "orb-vr-workfield",
            "work_units": 120,
            "virtual_node_count": 4,
            "max_runtime_ms": 250,
            "max_memory_mb": 128,
            "cpu_weight": 25,
        },
    ).json()
    plan = body["plan"]

    assert body["ok"] is True
    assert body["status"] == "planned_contract_only"
    assert body["plan_id"] == "orb-vr-workfield"
    assert plan["phase_plane"] == "P6_SIMULATION"
    assert plan["substrate_alignment"] == "compute_substrate_adapter_contract"
    assert plan["contract_only"] is True
    assert plan["simulation_only"] is True
    assert plan["no_free_compute_claim"] is True
    assert plan["real_compute_created"] is False
    assert plan["real_adapter_implementation"] is False
    assert plan["execution_authority"] is False
    assert plan["desktop_mutation_authority"] is False
    assert plan["starts_processes"] is False
    assert plan["uses_network"] is False
    assert plan["uses_gpu"] is False
    assert plan["runs_shell"] is False
    assert plan["starts_daemon"] is False
    assert plan["writes_memory"] is False
    assert plan["virtual_node_count"] == 4
    assert sum(node["assigned_work_units"] for node in plan["virtual_nodes"]) == 120
    assert body["governance"]["virtual_workfield_readback_only"] is True
    assert body["governance"]["uses_compute_substrate_service"] is False
    assert body["governance"]["does_not_trigger_execution"] is True
    assert body["governance"]["does_not_submit_compute_tasks"] is True
    assert body["governance"]["does_not_consume_approval"] is True
    assert body["governance"]["does_not_create_real_compute"] is True
    assert not (tmp_path / "francis_data").exists()


def test_simulation_virtual_workfield_redacts_workload_and_denies_bad_inputs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, actor_scopes={"simulation.reader": ["simulation:virtual-workfield:read"]})

    redacted = client.get(
        "/simulation/virtual-workfield",
        params={
            "actor": "simulation.reader",
            "plan_id": "redaction-plan",
            "workload": "token=RAW_SECRET_SHOULD_NOT_RETURN D:\\Francis\\private",
        },
    ).json()
    invalid_plan = client.get(
        "/simulation/virtual-workfield",
        params={"actor": "simulation.reader", "plan_id": "bad..plan"},
    ).json()
    over_budget = client.get(
        "/simulation/virtual-workfield",
        params={"actor": "simulation.reader", "work_units": 100001},
    ).json()
    serialized = json.dumps({"redacted": redacted, "invalid": invalid_plan, "over_budget": over_budget})

    assert redacted["ok"] is True
    assert redacted["plan"]["workload"] == "redacted_summary"
    assert "RAW_SECRET_SHOULD_NOT_RETURN" not in serialized
    assert "D:\\Francis\\private" not in serialized
    assert invalid_plan["ok"] is False
    assert invalid_plan["error"] == "malformed_request"
    assert invalid_plan["denial_reason"] == "invalid_plan_id"
    assert over_budget["ok"] is False
    assert over_budget["error"] == "malformed_request"
    assert over_budget["denial_reason"] == "work_units_out_of_range"
    assert invalid_plan["governance"]["grants_execution_authority"] is False
    assert over_budget["governance"]["grants_execution_authority"] is False
    assert not (tmp_path / "francis_data").exists()


def test_simulation_virtual_workfield_sanitizes_internal_budget_exception(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, actor_scopes={"simulation.reader": ["simulation:virtual-workfield:read"]})

    def fail_budget(**_kwargs):
        raise ValueError("budget traceback token=simulation-secret")

    monkeypatch.setattr(simulation_route, "VirtualWorkfieldBudget", fail_budget)

    body = client.get(
        "/simulation/virtual-workfield",
        params={"actor": "simulation.reader"},
    ).json()
    serialized = json.dumps(body, sort_keys=True)

    assert body["ok"] is False
    assert body["error"] == "malformed_request"
    assert body["denial_reason"] == "invalid_virtual_workfield_budget"
    assert "simulation-secret" not in serialized
    assert "traceback" not in serialized.lower()


def test_simulation_virtual_workfield_route_has_no_execution_or_persistence_authority() -> None:
    source = inspect.getsource(simulation_route)

    assert "create_virtual_workfield_plan" in source
    assert "ComputeSubstrateService" not in source
    assert "SubstrateGovernor" not in source
    assert "SafeLocalBackend" not in source
    assert "LocalJsonCompute" not in source
    assert ".submit(" not in source
    assert ".consume(" not in source
    assert ".write_receipt(" not in source
    assert ".upsert(" not in source
    assert "import subprocess" not in source
    assert "os.system" not in source
    assert "shell=True" not in source
    assert "asyncio.create_task" not in source
    assert "socket" not in source
    assert "requests" not in source
    assert "urllib" not in source
