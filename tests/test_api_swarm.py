from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from francis.api.app import create_app


def _write_stage14_closure_receipt(
    data_root: Path,
    *,
    receipt_id: str = "adversarial_hardening_stage14_closure_test",
) -> None:
    path = data_root / "logs" / "adversarial_hardening" / "stage14_operator_stage_closure_decisions.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "ok": True,
                "kind": "francis.stage14.adversarial_hardening.stage14_closure_decision_receipt",
                "receipt_id": receipt_id,
                "stage": "Stage 14 / Adversarial Hardening",
                "source_id": "adversarial_hardening",
                "target": "stage14_adversarial_hardening",
                "actor": "test.operator",
                "decision": "close_stage14",
                "completion_review_ready": True,
                "stage14_completion_review_ready": True,
                "stage14_closed_by_receipt": True,
                "ready_count": 5,
                "required_count": 5,
                "blockers": [],
                "marks_runtime_stage_state": False,
                "recorded_ts": 1_800_003_000,
                "governance": {
                    "explicit_operator_decision": True,
                    "stage_closure_decision": True,
                    "completion_review_ready": True,
                    "does_not_mutate_runtime_stage_state": True,
                    "grants_execution_authority": False,
                    "grants_mutation_authority": False,
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_swarm_status_blocks_until_stage14_closure(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    response = TestClient(create_app()).get("/swarm/status")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage15.swarm.status"
    assert body["stage"] == "Stage 15 / Swarm"
    assert body["status"] == "awaiting_stage14_ledger_closure"
    assert body["stage14_closed_by_receipt"] is False
    assert body["stage14_latest_closure_receipt_id"] == ""
    assert body["unit_roles_contract_ready"] is False
    assert body["ready_count"] == 0
    assert body["required_count"] == 6
    assert body["governance"]["read_only"] is True
    assert body["governance"]["one_francis_presence_preserved"] is True
    assert body["governance"]["does_not_create_agent_zoo"] is True
    assert body["governance"]["does_not_multiply_authority"] is True
    assert body["governance"]["grants_execution_authority"] is False
    assert body["governance"]["grants_mutation_authority"] is False
    assert body["next_smallest_truthful_gap"] == "stage14_ledger_closure"


def test_swarm_unit_roles_contract_is_ready_after_stage14_closure(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage14_closure_receipt(data_root)

    client = TestClient(create_app())
    contract = client.get("/swarm/unit-roles-contract").json()

    assert contract["ok"] is True
    assert contract["kind"] == "francis.stage15.swarm.unit_roles_contract"
    assert contract["stage"] == "Stage 15 / Swarm"
    assert contract["status"] == "ready"
    assert contract["stage14_closed_by_receipt"] is True
    assert contract["stage14_latest_closure_receipt_id"] == "adversarial_hardening_stage14_closure_test"
    assert contract["unit_roles_contract_ready"] is True
    assert contract["role_count"] == 4
    assert contract["role_invariants"]["one_francis_presence_preserved"] is True
    assert contract["role_invariants"]["unit_roles_do_not_grant_authority"] is True
    assert contract["role_invariants"]["specialization_is_internal_not_personality_fragmentation"] is True
    assert contract["role_invariants"]["operator_facing_identity_remains_francis"] is True
    assert contract["role_invariants"]["handoffs_must_be_traceable"] is True
    assert contract["payload_handling"]["returns_raw_private_payloads"] is False
    assert contract["payload_handling"]["returns_raw_model_outputs"] is False
    assert contract["reads_receipts"] is True
    assert contract["writes_receipts"] is False
    assert contract["writes_memory"] is False
    assert contract["runs_tools"] is False
    assert contract["runs_shell"] is False
    assert contract["runs_git"] is False
    assert contract["launches_browser"] is False
    assert contract["captures_screen"] is False
    assert contract["grants_execution_authority"] is False
    assert contract["grants_mutation_authority"] is False
    assert contract["governance"]["read_only"] is True
    assert contract["governance"]["does_not_create_agent_zoo"] is True
    assert contract["governance"]["does_not_multiply_authority"] is True
    assert contract["next_smallest_truthful_gap"] == "stage15_messaging_model_contract"

    roles = {item["id"]: item for item in contract["roles"]}
    assert set(roles) == {"coordinator", "specialist", "reviewer", "recorder"}
    assert all(item["operator_facing_identity"] == "Francis" for item in roles.values())
    assert all(item["bounded"] is True for item in roles.values())
    assert all(item["can_approve"] is False for item in roles.values())
    assert all(item["can_execute"] is False for item in roles.values())
    assert all(item["can_mutate_runtime"] is False for item in roles.values())
    assert all(item["can_subdelegate"] is False for item in roles.values())
    assert all(item["can_override_policy"] is False for item in roles.values())
    assert all(item["requires_trace_context"] is True for item in roles.values())
    assert all(item["requires_handoff_receipt"] is True for item in roles.values())

    source_contracts = {item["id"]: item for item in contract["source_contracts"]}
    assert source_contracts["swarm_coordinator_membership"]["observed"] is True
    assert source_contracts["collective_learning_observation_buffer"]["observed"] is True
    assert source_contracts["emergent_behavior_signal_detector"]["observed"] is True

    status = client.get("/swarm/status").json()
    assert status["status"] == "stage15_trace_continuity_contract_ready"
    assert status["stage14_closed_by_receipt"] is True
    assert status["unit_roles_contract_ready"] is True
    assert status["messaging_model_contract_ready"] is True
    assert status["delegation_etiquette_contract_ready"] is True
    assert status["trace_continuity_contract_ready"] is True
    assert status["failure_semantics_contract_ready"] is False
    assert status["ready_count"] == 5
    assert status["required_count"] == 6
    assert status["routes"]["unit_roles_contract"] == "/swarm/unit-roles-contract"
    assert status["routes"]["messaging_model_contract"] == "/swarm/messaging-model-contract"
    assert status["routes"]["delegation_etiquette_contract"] == "/swarm/delegation-etiquette-contract"
    assert status["routes"]["trace_continuity_contract"] == "/swarm/trace-continuity-contract"
    assert status["next_smallest_truthful_gap"] == "stage15_failure_semantics_contract"


def test_swarm_messaging_model_contract_preserves_trace_and_authority_boundaries(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage14_closure_receipt(data_root)

    client = TestClient(create_app())
    contract = client.get("/swarm/messaging-model-contract").json()

    assert contract["ok"] is True
    assert contract["kind"] == "francis.stage15.swarm.messaging_model_contract"
    assert contract["stage"] == "Stage 15 / Swarm"
    assert contract["status"] == "ready"
    assert contract["unit_roles_contract_ready"] is True
    assert contract["messaging_model_contract_ready"] is True
    assert set(contract["allowed_roles"]) == {"coordinator", "specialist", "reviewer", "recorder"}
    assert contract["required_field_count"] >= 8
    assert contract["optional_field_count"] >= 1
    assert contract["message_invariants"]["message_envelope_required"] is True
    assert contract["message_invariants"]["sender_and_receiver_must_be_known_roles"] is True
    assert contract["message_invariants"]["swarm_trace_id_required"] is True
    assert contract["message_invariants"]["authority_claims_do_not_grant_authority"] is True
    assert contract["message_invariants"]["raw_private_payloads_not_required"] is True
    assert contract["message_invariants"]["operator_facing_identity_remains_francis"] is True
    assert contract["delivery_semantics"]["contract_only"] is True
    assert contract["delivery_semantics"]["sends_messages"] is False
    assert contract["delivery_semantics"]["starts_workers"] is False
    assert contract["delivery_semantics"]["runs_tools"] is False
    assert contract["delivery_semantics"]["requires_deadletter_contract_before_retry"] is True
    assert contract["payload_handling"]["references_evidence_instead_of_raw_private_payloads"] is True
    assert contract["payload_handling"]["returns_raw_private_payloads"] is False
    assert contract["payload_handling"]["returns_raw_model_outputs"] is False
    assert contract["writes_receipts"] is False
    assert contract["writes_memory"] is False
    assert contract["runs_tools"] is False
    assert contract["runs_shell"] is False
    assert contract["runs_git"] is False
    assert contract["launches_browser"] is False
    assert contract["captures_screen"] is False
    assert contract["grants_execution_authority"] is False
    assert contract["grants_mutation_authority"] is False
    assert contract["governance"]["does_not_create_agent_zoo"] is True
    assert contract["governance"]["does_not_multiply_authority"] is True
    assert contract["next_smallest_truthful_gap"] == "stage15_delegation_etiquette_contract"

    fields = {item["field"]: item for item in contract["envelope_fields"]}
    assert {
        "message_id",
        "swarm_trace_id",
        "sender_role",
        "receiver_role",
        "objective",
        "evidence_refs",
        "requested_action",
        "authority_claim",
        "handoff_receipt_required",
    }.issubset(set(fields))
    assert fields["authority_claim"]["authority_bearing"] is False


def test_swarm_delegation_etiquette_contract_blocks_agent_zoo_dynamics(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage14_closure_receipt(data_root)

    client = TestClient(create_app())
    contract = client.get("/swarm/delegation-etiquette-contract").json()

    assert contract["ok"] is True
    assert contract["kind"] == "francis.stage15.swarm.delegation_etiquette_contract"
    assert contract["stage"] == "Stage 15 / Swarm"
    assert contract["status"] == "ready"
    assert contract["messaging_model_contract_ready"] is True
    assert contract["delegation_etiquette_contract_ready"] is True
    assert contract["rule_count"] == 6
    assert "agent_zoo_dynamics" in contract["forbidden_patterns"]
    assert "authority_multiplication" in contract["forbidden_patterns"]
    assert "personality_fragmentation" in contract["forbidden_patterns"]
    assert "unbounded_subdelegation" in contract["forbidden_patterns"]
    assert "operator_identity_splitting" in contract["forbidden_patterns"]
    assert "silent_handoff_without_trace" in contract["forbidden_patterns"]
    assert contract["authority_boundaries"]["units_can_recommend"] is True
    assert contract["authority_boundaries"]["units_can_approve"] is False
    assert contract["authority_boundaries"]["units_can_execute"] is False
    assert contract["authority_boundaries"]["units_can_mutate_runtime"] is False
    assert contract["authority_boundaries"]["units_can_subdelegate"] is False
    assert contract["authority_boundaries"]["operator_facing_presence"] == "Francis"
    assert contract["delivery_semantics"]["contract_only"] is True
    assert contract["delivery_semantics"]["sends_messages"] is False
    assert contract["delivery_semantics"]["starts_workers"] is False
    assert contract["delivery_semantics"]["requires_message_envelope"] is True
    assert contract["delivery_semantics"]["requires_trace_context"] is True
    assert contract["writes_receipts"] is False
    assert contract["writes_memory"] is False
    assert contract["runs_tools"] is False
    assert contract["runs_shell"] is False
    assert contract["runs_git"] is False
    assert contract["launches_browser"] is False
    assert contract["captures_screen"] is False
    assert contract["grants_execution_authority"] is False
    assert contract["grants_mutation_authority"] is False
    assert contract["governance"]["does_not_create_agent_zoo"] is True
    assert contract["governance"]["does_not_multiply_authority"] is True
    assert contract["next_smallest_truthful_gap"] == "stage15_trace_continuity_contract"

    rules = {item["id"]: item for item in contract["etiquette_rules"]}
    assert {
        "handoff_requires_message_envelope",
        "handoff_requires_known_roles",
        "handoff_cannot_claim_operator_identity",
        "handoff_cannot_grant_authority",
        "handoff_requires_evidence_refs",
        "handoff_conflicts_route_to_reviewer",
    } == set(rules)
    assert all(item["enforced_by_contract"] is True for item in rules.values())
    assert all(item["authority_granted"] is False for item in rules.values())
    assert all(item["operator_identity_split"] is False for item in rules.values())
    assert all(item["subdelegation_allowed"] is False for item in rules.values())


def test_swarm_trace_continuity_contract_preserves_one_lineage(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage14_closure_receipt(data_root)

    client = TestClient(create_app())
    contract = client.get("/swarm/trace-continuity-contract").json()

    assert contract["ok"] is True
    assert contract["kind"] == "francis.stage15.swarm.trace_continuity_contract"
    assert contract["stage"] == "Stage 15 / Swarm"
    assert contract["status"] == "ready"
    assert contract["delegation_etiquette_contract_ready"] is True
    assert contract["trace_continuity_contract_ready"] is True
    assert contract["required_trace_field_count"] == 9
    assert set(contract["trace_states"]) == {"accepted", "rejected", "deadlettered", "retry_requested"}
    assert contract["trace_invariants"]["one_trace_lineage_required"] is True
    assert contract["trace_invariants"]["parent_child_links_required_after_first_message"] is True
    assert contract["trace_invariants"]["root_objective_preserved"] is True
    assert contract["trace_invariants"]["operator_facing_presence_remains_francis"] is True
    assert contract["trace_invariants"]["handoff_reason_required"] is True
    assert contract["trace_invariants"]["trace_fields_do_not_grant_authority"] is True
    assert contract["sample_trace_projection"]["message_count"] == 3
    assert contract["sample_trace_projection"]["operator_facing_presence"] == "Francis"
    assert contract["sample_trace_projection"]["authority_granted"] is False
    assert contract["delivery_semantics"]["contract_only"] is True
    assert contract["delivery_semantics"]["sends_messages"] is False
    assert contract["delivery_semantics"]["starts_workers"] is False
    assert contract["delivery_semantics"]["requires_failure_semantics_before_retry_execution"] is True
    assert contract["writes_receipts"] is False
    assert contract["writes_memory"] is False
    assert contract["runs_tools"] is False
    assert contract["runs_shell"] is False
    assert contract["runs_git"] is False
    assert contract["launches_browser"] is False
    assert contract["captures_screen"] is False
    assert contract["grants_execution_authority"] is False
    assert contract["grants_mutation_authority"] is False
    assert contract["governance"]["does_not_create_agent_zoo"] is True
    assert contract["governance"]["does_not_multiply_authority"] is True
    assert contract["next_smallest_truthful_gap"] == "stage15_failure_semantics_contract"

    fields = {item["field"]: item for item in contract["trace_fields"]}
    assert {
        "swarm_trace_id",
        "message_id",
        "parent_message_id",
        "root_objective_id",
        "sender_role",
        "receiver_role",
        "handoff_reason",
        "evidence_refs",
        "decision_state",
    } == set(fields)
    assert all(item["authority_bearing"] is False for item in fields.values())
