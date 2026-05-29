from __future__ import annotations

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from francis.api.app import create_app
from francis.api.mutation_authority_matrix import (
    MUTATING_METHODS,
    build_mutating_route_authority_matrix,
)


def _mutating_route_total() -> int:
    total = 0
    for route in create_app().routes:
        if not isinstance(route, APIRoute):
            continue
        total += len([method for method in route.methods if method in MUTATING_METHODS])
    return total


def _entry_by_path(entries: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(entry["path"]): entry for entry in entries}


def test_mutating_route_authority_matrix_covers_all_non_get_routes() -> None:
    matrix = build_mutating_route_authority_matrix(create_app().routes)

    assert matrix["ok"] is True
    assert matrix["status"] == "covered"
    assert matrix["missing"] == []
    assert matrix["missing_total"] == 0
    assert matrix["total"] == _mutating_route_total()
    assert matrix["summary"]["read_only_projection"] is True
    assert matrix["summary"]["write_behavior_changed"] is False

    required_fields = {
        "method",
        "path",
        "endpoint",
        "module",
        "family",
        "required_actor",
        "required_scope",
        "approval_requirement",
        "receipt_behavior",
        "denial_behavior",
        "governance_maturity",
    }
    for entry in matrix["entries"]:
        assert required_fields.issubset(entry)
        assert entry["method"] in MUTATING_METHODS
        for field in required_fields - {"method"}:
            assert str(entry[field]).strip()


def test_system_exposes_mutating_route_authority_matrix() -> None:
    client = TestClient(create_app())

    response = client.get("/system/mutating-route-authority-matrix")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.api.mutating_route_authority_matrix"
    assert body["total"] == _mutating_route_total()
    assert body["missing_total"] == 0

    entries = _entry_by_path(body["entries"])
    system_config = entries["/system/config/mutate"]
    assert system_config["family"] == "system"
    assert system_config["required_actor"] == "payload.actor"
    assert system_config["required_scope"] == "system.write"
    assert system_config["governance_maturity"] == "permission_gated"
    assert "permission_gate" in system_config["denial_behavior"]

    terminal = entries["/telemetry/terminal/events"]
    assert terminal["family"] == "telemetry_terminal"
    assert terminal["required_scope"] == "telemetry.terminal.write"
    assert terminal["governance_maturity"] == "permission_gated"

    memory = entries["/memory/timeline/record"]
    assert memory["family"] == "memory_timeline"
    assert memory["required_actor"] == "payload.request_actor, payload.api_actor, or payload.actor"
    assert memory["required_scope"] == "memory.timeline.write"
    assert memory["governance_maturity"] == "permission_gated"
    assert "permission_gate" in memory["denial_behavior"]

    explanation = entries["/explanations/record"]
    assert explanation["family"] == "explanation"
    assert explanation["required_actor"] == "payload.request_actor, payload.api_actor, or payload.actor"
    assert explanation["required_scope"] == "explanation.write"
    assert explanation["governance_maturity"] == "permission_gated"
    assert "permission_gate" in explanation["denial_behavior"]

    read_batch = entries["/operations/get_many"]
    assert read_batch["family"] == "operations_read_batch"
    assert read_batch["required_actor"] == "none"
    assert read_batch["required_scope"] == "none_read_only_batch_lookup"
    assert read_batch["receipt_behavior"] == "none_read_projection"
