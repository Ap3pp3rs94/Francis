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

    feedback_memory = entries["/telemetry/context/feedback/memory-quality"]
    assert feedback_memory["family"] == "telemetry_context_feedback_memory_quality"
    assert feedback_memory["required_actor"] == "payload.actor"
    assert feedback_memory["required_scope"] == "memory.timeline.write"
    assert feedback_memory["governance_maturity"] == "permission_gated"
    assert "memory timeline" in feedback_memory["receipt_behavior"]
    assert "permission_gate" in feedback_memory["denial_behavior"]

    attachment = entries["/attachments/upload"]
    assert attachment["family"] == "attachments"
    assert attachment["required_actor"] == "multipart request_actor, actor, or api.attachments default"
    assert attachment["required_scope"] == "attachments.write"
    assert attachment["governance_maturity"] == "permission_gated"
    assert "permission_gate" in attachment["denial_behavior"]

    approval_request = entries["/approvals/request"]
    assert approval_request["family"] == "approval_request"
    assert approval_request["required_actor"] == "payload.request_actor, payload.api_actor, or payload.actor"
    assert approval_request["required_scope"] == "approvals.request"
    assert approval_request["approval_requirement"] == (
        "creates pending approval after request-scope gate; does not decide it"
    )
    assert approval_request["governance_maturity"] == "permission_gated"
    assert "permission_gate" in approval_request["denial_behavior"]
    assert "lower authority than deciding" in approval_request["notes"]

    executor_closure = entries["/executor/substrate/stage-closure-decision"]
    assert executor_closure["family"] == "executor_substrate"
    assert executor_closure["required_actor"] == "payload.actor"
    assert executor_closure["required_scope"] == "executor.stage8.closure.write"
    assert executor_closure["governance_maturity"] == "permission_gated"
    assert "closure receipt" in executor_closure["denial_behavior"]
    assert "does not mutate runtime stage state" in executor_closure["notes"]

    takeover_control = entries["/takeover/control-transfer"]
    assert takeover_control["family"] == "takeover"
    assert takeover_control["required_actor"] == "payload.actor"
    assert takeover_control["required_scope"] == "takeover.control.write"
    assert takeover_control["governance_maturity"] == "permission_gated"
    assert "Stage 8 closure receipt" in takeover_control["approval_requirement"]
    assert "does not run tools" in takeover_control["notes"]

    takeover_panic = entries["/takeover/panic-stop"]
    assert takeover_panic["family"] == "takeover"
    assert takeover_panic["required_actor"] == "payload.actor"
    assert takeover_panic["required_scope"] == "takeover.panic.write"
    assert takeover_panic["governance_maturity"] == "permission_gated"
    assert "panic-stop receipt" in takeover_panic["receipt_behavior"]
    assert "control-transfer action-feed receipt" in takeover_panic["notes"]

    takeover_action = entries["/takeover/delegated-action"]
    assert takeover_action["family"] == "takeover"
    assert takeover_action["required_actor"] == "payload.actor"
    assert takeover_action["required_scope"] == "takeover.action.write"
    assert takeover_action["governance_maturity"] == "permission_gated"
    assert "control-transfer receipt" in takeover_action["approval_requirement"]
    assert "live-action receipt" in takeover_action["receipt_behavior"]
    assert "allowlisted executor operations" in takeover_action["notes"]

    takeover_handback = entries["/takeover/handback-summary"]
    assert takeover_handback["family"] == "takeover"
    assert takeover_handback["required_actor"] == "payload.actor"
    assert takeover_handback["required_scope"] == "takeover.handback.write"
    assert takeover_handback["governance_maturity"] == "permission_gated"
    assert "control-transfer receipt" in takeover_handback["approval_requirement"]
    assert "without executing work" in takeover_handback["notes"]

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

    web_learning = entries["/web_learning/request"]
    assert web_learning["family"] == "web_learning"
    assert web_learning["required_actor"] == "payload.request_actor, payload.api_actor, payload.actor, or api default"
    assert web_learning["required_scope"] == "web_learning.write"
    assert web_learning["governance_maturity"] == "permission_and_policy_gated"
    assert "permission_gate" in web_learning["denial_behavior"]

    federation = entries["/federation/instances/upsert"]
    assert federation["family"] == "federation"
    assert federation["required_actor"] == (
        "payload.request_actor, payload.api_actor, payload.actor, or api.federation default"
    )
    assert federation["required_scope"] == "federation.write"
    assert federation["governance_maturity"] == "permission_gated"
    assert "permission_gate" in federation["denial_behavior"]

    industrial = entries["/industrial/assets"]
    assert industrial["family"] == "industrial"
    assert industrial["required_actor"] == (
        "payload.request_actor, payload.api_actor, payload.actor, payload.requested_by, or api.industrial default"
    )
    assert industrial["required_scope"] == "industrial.write"
    assert industrial["governance_maturity"] == "permission_and_policy_gated"
    assert "permission_gate" in industrial["denial_behavior"]
    assert "exact-action" in industrial["approval_requirement"]

    chat = entries["/chat/send"]
    assert chat["family"] == "chat"
    assert chat["required_actor"] == (
        "payload.request_actor, payload.api_actor, payload.actor, or api.chat default for generic chat; internal "
        "chat.send for /mission ingress"
    )
    assert chat["required_scope"] == "chat.write for generic chat; missions.write for /mission ingress"
    assert chat["governance_maturity"] == "permission_gated"
    assert "generic ledger write" in chat["denial_behavior"]
    assert "mission declaration authority" in chat["notes"]

    read_batch = entries["/operations/get_many"]
    assert read_batch["family"] == "operations_read_batch"
    assert read_batch["required_actor"] == "none"
    assert read_batch["required_scope"] == "none_read_only_batch_lookup"
    assert read_batch["receipt_behavior"] == "none_read_projection"
