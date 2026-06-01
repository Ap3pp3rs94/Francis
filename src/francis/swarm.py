from __future__ import annotations

from typing import Any

from francis.adversarial_hardening import adversarial_hardening_stage14_operator_stage_closure_decision_readback
from francis.collective.swarm import CollectiveLearning, EmergentBehavior, SwarmCoordinator

STAGE15_SWARM_STAGE = "Stage 15 / Swarm"
SWARM_STATUS_KIND = "francis.stage15.swarm.status"
SWARM_UNIT_ROLES_CONTRACT_KIND = "francis.stage15.swarm.unit_roles_contract"
SWARM_MESSAGING_MODEL_CONTRACT_KIND = "francis.stage15.swarm.messaging_model_contract"


def swarm_status_snapshot() -> dict[str, Any]:
    stage14 = adversarial_hardening_stage14_operator_stage_closure_decision_readback(limit=5)
    stage14_closed = bool(stage14.get("stage14_closed_by_receipt"))
    unit_roles = swarm_unit_roles_contract()
    unit_roles_ready = bool(unit_roles.get("unit_roles_contract_ready"))
    messaging_model = swarm_messaging_model_contract()
    messaging_model_ready = bool(messaging_model.get("messaging_model_contract_ready"))
    deliverables = [
        _deliverable(
            "stage14_ledger_closure_backstop",
            "Stage 14 Adversarial Hardening closure receipt readback is present",
            stage14_closed,
            "ready" if stage14_closed else "blocked",
            "stage14_ledger_closure",
        ),
        _deliverable(
            "unit_roles",
            "Swarm unit roles are bounded by one-presence identity and no authority multiplication",
            unit_roles_ready,
            "ready" if unit_roles_ready else "pending",
            "stage15_unit_roles_contract",
        ),
        _deliverable(
            "messaging_model",
            "Inter-unit messages use an auditable envelope with identity and trace context",
            messaging_model_ready,
            "ready" if messaging_model_ready else "pending",
            "stage15_messaging_model_contract",
        ),
        _deliverable(
            "delegation_etiquette",
            "Unit handoffs preserve operator authority boundaries and do not create agent-zoo dynamics",
            False,
            "pending",
            "stage15_delegation_etiquette_contract",
        ),
        _deliverable(
            "trace_continuity",
            "Swarm handoffs preserve one trace lineage across specialized units",
            False,
            "pending",
            "stage15_trace_continuity_contract",
        ),
        _deliverable(
            "failure_semantics",
            "Deadletter and retry semantics are explicit across units",
            False,
            "pending",
            "stage15_failure_semantics_contract",
        ),
    ]
    ready_count = sum(1 for item in deliverables if bool(item["ready"]))
    return {
        "ok": True,
        "kind": SWARM_STATUS_KIND,
        "stage": STAGE15_SWARM_STAGE,
        "source_id": "swarm",
        "status": "stage15_messaging_model_contract_ready"
        if stage14_closed and unit_roles_ready and messaging_model_ready
        else "stage15_unit_roles_contract_ready"
        if stage14_closed and unit_roles_ready
        else "awaiting_stage14_ledger_closure"
        if not stage14_closed
        else "stage15_started",
        "stage14_closed_by_receipt": stage14_closed,
        "stage14_latest_closure_receipt_id": _safe_text(stage14.get("latest_receipt_id")),
        "unit_roles_contract_ready": unit_roles_ready,
        "messaging_model_contract_ready": messaging_model_ready,
        "delegation_etiquette_contract_ready": False,
        "trace_continuity_contract_ready": False,
        "failure_semantics_contract_ready": False,
        "deliverables": deliverables,
        "ready_count": ready_count,
        "required_count": len(deliverables),
        "routes": {
            "status": "/swarm/status",
            "unit_roles_contract": "/swarm/unit-roles-contract",
            "messaging_model_contract": "/swarm/messaging-model-contract",
            "stage14_closure_readback": "/adversarial-hardening/stage-closure-decisions",
        },
        "governance": _governance(),
        "next_smallest_truthful_gap": "stage15_delegation_etiquette_contract"
        if stage14_closed and unit_roles_ready and messaging_model_ready
        else "stage15_messaging_model_contract"
        if stage14_closed and unit_roles_ready
        else "stage15_unit_roles_contract"
        if stage14_closed
        else "stage14_ledger_closure",
    }


def swarm_unit_roles_contract() -> dict[str, Any]:
    stage14 = adversarial_hardening_stage14_operator_stage_closure_decision_readback(limit=5)
    stage14_closed = bool(stage14.get("stage14_closed_by_receipt"))
    source_contracts = [
        _source_contract(
            "swarm_coordinator_membership",
            "francis.collective.swarm.SwarmCoordinator",
            SwarmCoordinator,
            ["register", "list_members"],
        ),
        _source_contract(
            "collective_learning_observation_buffer",
            "francis.collective.swarm.CollectiveLearning",
            CollectiveLearning,
            ["add_observation"],
        ),
        _source_contract(
            "emergent_behavior_signal_detector",
            "francis.collective.swarm.EmergentBehavior",
            EmergentBehavior,
            ["detect"],
        ),
    ]
    roles = [
        _unit_role(
            "coordinator",
            "routes bounded work between units and preserves the single Francis presence",
            allowed_actions=["classify_task", "select_unit", "emit_handoff_plan"],
        ),
        _unit_role(
            "specialist",
            "analyzes one bounded domain and returns evidence instead of authority",
            allowed_actions=["analyze_context", "produce_evidence", "recommend_next_step"],
        ),
        _unit_role(
            "reviewer",
            "checks unit output against policy, identity, and trace invariants",
            allowed_actions=["verify_evidence", "flag_overreach", "request_rework"],
        ),
        _unit_role(
            "recorder",
            "summarizes handoffs into traceable receipts without storing raw private payloads",
            allowed_actions=["summarize_trace", "record_receipt_metadata", "surface_deadletter"],
        ),
    ]
    role_invariants = {
        "one_francis_presence_preserved": True,
        "unit_roles_do_not_grant_authority": True,
        "specialization_is_internal_not_personality_fragmentation": True,
        "operator_facing_identity_remains_francis": True,
        "handoffs_must_be_traceable": True,
    }
    role_contract_ready = (
        stage14_closed
        and len(roles) >= 4
        and all(bool(role.get("bounded")) for role in roles)
        and all(bool(contract.get("observed")) for contract in source_contracts)
        and all(bool(value) for value in role_invariants.values())
    )
    return {
        "ok": True,
        "kind": SWARM_UNIT_ROLES_CONTRACT_KIND,
        "stage": STAGE15_SWARM_STAGE,
        "source_id": "swarm",
        "status": "ready" if role_contract_ready else "blocked",
        "stage14_closed_by_receipt": stage14_closed,
        "stage14_latest_closure_receipt_id": _safe_text(stage14.get("latest_receipt_id")),
        "unit_roles_contract_ready": role_contract_ready,
        "roles": roles,
        "role_count": len(roles),
        "source_contracts": source_contracts,
        "role_invariants": role_invariants,
        "payload_handling": {
            "returns_raw_private_payloads": False,
            "returns_raw_model_outputs": False,
            "returns_role_contract_only": True,
        },
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": _governance(),
        "next_smallest_truthful_gap": "stage15_messaging_model_contract"
        if role_contract_ready
        else "stage14_ledger_closure"
        if not stage14_closed
        else "stage15_unit_roles_contract",
    }


def swarm_messaging_model_contract() -> dict[str, Any]:
    unit_roles = swarm_unit_roles_contract()
    unit_roles_ready = bool(unit_roles.get("unit_roles_contract_ready"))
    envelope_fields = [
        _message_field("message_id", "stable unique message identifier", required=True),
        _message_field("swarm_trace_id", "trace lineage shared across the handoff", required=True),
        _message_field("parent_message_id", "optional parent message for causal ordering", required=False),
        _message_field("sender_role", "bounded source unit role", required=True),
        _message_field("receiver_role", "bounded target unit role", required=True),
        _message_field("objective", "bounded task objective", required=True),
        _message_field("evidence_refs", "references to evidence rather than raw private payloads", required=True),
        _message_field("requested_action", "requested read-only analysis or handoff action", required=True),
        _message_field("authority_claim", "must be false unless a separate governance receipt exists", required=True),
        _message_field(
            "handoff_receipt_required", "marks whether receiver must write a handoff receipt", required=True
        ),
    ]
    invariants = {
        "message_envelope_required": True,
        "sender_and_receiver_must_be_known_roles": True,
        "swarm_trace_id_required": True,
        "authority_claims_do_not_grant_authority": True,
        "raw_private_payloads_not_required": True,
        "operator_facing_identity_remains_francis": True,
    }
    allowed_roles = [str(item.get("id")) for item in unit_roles.get("roles", []) if isinstance(item, dict)]
    messaging_ready = (
        unit_roles_ready
        and len(envelope_fields) >= 8
        and {"coordinator", "specialist", "reviewer", "recorder"}.issubset(set(allowed_roles))
        and all(bool(field.get("field")) for field in envelope_fields)
        and all(bool(value) for value in invariants.values())
    )
    return {
        "ok": True,
        "kind": SWARM_MESSAGING_MODEL_CONTRACT_KIND,
        "stage": STAGE15_SWARM_STAGE,
        "source_id": "swarm",
        "status": "ready" if messaging_ready else "blocked",
        "unit_roles_contract_ready": unit_roles_ready,
        "messaging_model_contract_ready": messaging_ready,
        "allowed_roles": allowed_roles,
        "envelope_fields": envelope_fields,
        "required_field_count": sum(1 for field in envelope_fields if bool(field.get("required"))),
        "optional_field_count": sum(1 for field in envelope_fields if not bool(field.get("required"))),
        "message_invariants": invariants,
        "delivery_semantics": {
            "contract_only": True,
            "sends_messages": False,
            "starts_workers": False,
            "runs_tools": False,
            "requires_deadletter_contract_before_retry": True,
        },
        "payload_handling": {
            "references_evidence_instead_of_raw_private_payloads": True,
            "returns_raw_private_payloads": False,
            "returns_raw_model_outputs": False,
        },
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": _governance(),
        "next_smallest_truthful_gap": "stage15_delegation_etiquette_contract"
        if messaging_ready
        else "stage15_unit_roles_contract",
    }


def _unit_role(role_id: str, summary: str, *, allowed_actions: list[str]) -> dict[str, Any]:
    return {
        "id": role_id,
        "summary": summary,
        "allowed_actions": allowed_actions,
        "bounded": True,
        "operator_facing_identity": "Francis",
        "can_approve": False,
        "can_execute": False,
        "can_mutate_runtime": False,
        "can_subdelegate": False,
        "can_override_policy": False,
        "requires_trace_context": True,
        "requires_handoff_receipt": True,
    }


def _message_field(field: str, description: str, *, required: bool) -> dict[str, Any]:
    return {
        "field": field,
        "description": description,
        "required": required,
        "redacted_before_operator_display": field == "objective",
        "authority_bearing": False,
    }


def _source_contract(contract_id: str, source_path: str, source_type: type[Any], methods: list[str]) -> dict[str, Any]:
    missing = [method for method in methods if not callable(getattr(source_type, method, None))]
    return {
        "id": contract_id,
        "source_path": source_path,
        "observed": len(missing) == 0,
        "required_methods": methods,
        "missing_methods": missing,
    }


def _deliverable(
    item_id: str,
    summary: str,
    ready: bool,
    status: str,
    next_gap: str,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "summary": summary,
        "ready": ready,
        "status": status,
        "next_smallest_truthful_gap": next_gap,
    }


def _governance() -> dict[str, Any]:
    return {
        "read_only": True,
        "requires_stage14_ledger_closure": True,
        "one_francis_presence_preserved": True,
        "does_not_create_agent_zoo": True,
        "does_not_multiply_authority": True,
        "does_not_write_receipts": True,
        "does_not_write_memory": True,
        "does_not_run_tools": True,
        "does_not_run_shell": True,
        "does_not_run_git": True,
        "does_not_launch_browser": True,
        "does_not_capture_screen": True,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def _safe_text(value: Any) -> str:
    return str(value or "").strip()
