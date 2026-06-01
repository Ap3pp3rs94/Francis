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
    assert status["status"] == "stage15_messaging_model_contract_ready"
    assert status["stage14_closed_by_receipt"] is True
    assert status["unit_roles_contract_ready"] is True
    assert status["messaging_model_contract_ready"] is True
    assert status["delegation_etiquette_contract_ready"] is False
    assert status["trace_continuity_contract_ready"] is False
    assert status["failure_semantics_contract_ready"] is False
    assert status["ready_count"] == 3
    assert status["required_count"] == 6
    assert status["routes"]["unit_roles_contract"] == "/swarm/unit-roles-contract"
    assert status["routes"]["messaging_model_contract"] == "/swarm/messaging-model-contract"
    assert status["next_smallest_truthful_gap"] == "stage15_delegation_etiquette_contract"


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
