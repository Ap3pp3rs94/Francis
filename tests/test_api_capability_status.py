from __future__ import annotations

from fastapi.testclient import TestClient

from francis.api.app import create_app


def test_unimplemented_capability_routes_report_truthful_status() -> None:
    client = TestClient(create_app())

    for route in ("digital_twin", "resilience", "evolution"):
        response = client.get(f"/{route}/status")

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["route"] == route
        assert body["status"] == "not_implemented"
        assert body["ready"] is False
        assert body["implemented_operations"] == ["status_readback"]
        assert body["blockers"] == [f"{route}_api_route_operations_not_implemented"]
        assert body["governance"] == {
            "read_only": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        }


def test_partial_simulation_route_reports_implemented_contract_boundary() -> None:
    response = TestClient(create_app()).get("/simulation/status")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["route"] == "simulation"
    assert body["status"] == "partial"
    assert body["ready"] is False
    assert body["implemented_operations"] == [
        "status_readback",
        "virtual_workfield_contract_readback",
    ]
    assert body["blockers"] == ["simulation_execution_adapter_not_implemented"]
    assert body["governance"] == {
        "read_only": True,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }
