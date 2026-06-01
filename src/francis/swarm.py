from __future__ import annotations

from typing import Any

from francis.adversarial_hardening import adversarial_hardening_stage14_operator_stage_closure_decision_readback
from francis.collective.swarm import CollectiveLearning, EmergentBehavior, SwarmCoordinator

STAGE15_SWARM_STAGE = "Stage 15 / Swarm"
SWARM_STATUS_KIND = "francis.stage15.swarm.status"
SWARM_UNIT_ROLES_CONTRACT_KIND = "francis.stage15.swarm.unit_roles_contract"
SWARM_MESSAGING_MODEL_CONTRACT_KIND = "francis.stage15.swarm.messaging_model_contract"
SWARM_DELEGATION_ETIQUETTE_CONTRACT_KIND = "francis.stage15.swarm.delegation_etiquette_contract"
SWARM_TRACE_CONTINUITY_CONTRACT_KIND = "francis.stage15.swarm.trace_continuity_contract"


def swarm_status_snapshot() -> dict[str, Any]:
    stage14 = adversarial_hardening_stage14_operator_stage_closure_decision_readback(limit=5)
    stage14_closed = bool(stage14.get("stage14_closed_by_receipt"))
    unit_roles = swarm_unit_roles_contract()
    unit_roles_ready = bool(unit_roles.get("unit_roles_contract_ready"))
    messaging_model = swarm_messaging_model_contract()
    messaging_model_ready = bool(messaging_model.get("messaging_model_contract_ready"))
    delegation_etiquette = swarm_delegation_etiquette_contract()
    delegation_etiquette_ready = bool(delegation_etiquette.get("delegation_etiquette_contract_ready"))
    trace_continuity = swarm_trace_continuity_contract()
    trace_continuity_ready = bool(trace_continuity.get("trace_continuity_contract_ready"))
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
            delegation_etiquette_ready,
            "ready" if delegation_etiquette_ready else "pending",
            "stage15_delegation_etiquette_contract",
        ),
        _deliverable(
            "trace_continuity",
            "Swarm handoffs preserve one trace lineage across specialized units",
            trace_continuity_ready,
            "ready" if trace_continuity_ready else "pending",
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
        "status": "stage15_trace_continuity_contract_ready"
        if stage14_closed
        and unit_roles_ready
        and messaging_model_ready
        and delegation_etiquette_ready
        and trace_continuity_ready
        else "stage15_delegation_etiquette_contract_ready"
        if stage14_closed and unit_roles_ready and messaging_model_ready and delegation_etiquette_ready
        else "stage15_messaging_model_contract_ready"
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
        "delegation_etiquette_contract_ready": delegation_etiquette_ready,
        "trace_continuity_contract_ready": trace_continuity_ready,
        "failure_semantics_contract_ready": False,
        "deliverables": deliverables,
        "ready_count": ready_count,
        "required_count": len(deliverables),
        "routes": {
            "status": "/swarm/status",
            "unit_roles_contract": "/swarm/unit-roles-contract",
            "messaging_model_contract": "/swarm/messaging-model-contract",
            "delegation_etiquette_contract": "/swarm/delegation-etiquette-contract",
            "trace_continuity_contract": "/swarm/trace-continuity-contract",
            "stage14_closure_readback": "/adversarial-hardening/stage-closure-decisions",
        },
        "governance": _governance(),
        "next_smallest_truthful_gap": "stage15_failure_semantics_contract"
        if stage14_closed
        and unit_roles_ready
        and messaging_model_ready
        and delegation_etiquette_ready
        and trace_continuity_ready
        else "stage15_trace_continuity_contract"
        if stage14_closed and unit_roles_ready and messaging_model_ready and delegation_etiquette_ready
        else "stage15_delegation_etiquette_contract"
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


def swarm_delegation_etiquette_contract() -> dict[str, Any]:
    messaging = swarm_messaging_model_contract()
    messaging_ready = bool(messaging.get("messaging_model_contract_ready"))
    etiquette_rules = [
        _etiquette_rule(
            "handoff_requires_message_envelope",
            "Every unit handoff must use the Stage 15 message envelope.",
        ),
        _etiquette_rule(
            "handoff_requires_known_roles",
            "Sender and receiver must be known bounded roles from the unit-roles contract.",
        ),
        _etiquette_rule(
            "handoff_cannot_claim_operator_identity",
            "Units do not present as separate operator-facing agents.",
        ),
        _etiquette_rule(
            "handoff_cannot_grant_authority",
            "Delegation etiquette cannot approve execution or mutate governance state.",
        ),
        _etiquette_rule(
            "handoff_requires_evidence_refs",
            "Units pass evidence references rather than raw private payloads.",
        ),
        _etiquette_rule(
            "handoff_conflicts_route_to_reviewer",
            "Role conflicts go to reviewer or deadletter instead of ad hoc subdelegation.",
        ),
    ]
    forbidden_patterns = [
        "agent_zoo_dynamics",
        "authority_multiplication",
        "personality_fragmentation",
        "unbounded_subdelegation",
        "operator_identity_splitting",
        "silent_handoff_without_trace",
    ]
    etiquette_ready = (
        messaging_ready
        and len(etiquette_rules) >= 6
        and all(bool(rule.get("enforced_by_contract")) for rule in etiquette_rules)
        and len(forbidden_patterns) >= 6
    )
    return {
        "ok": True,
        "kind": SWARM_DELEGATION_ETIQUETTE_CONTRACT_KIND,
        "stage": STAGE15_SWARM_STAGE,
        "source_id": "swarm",
        "status": "ready" if etiquette_ready else "blocked",
        "messaging_model_contract_ready": messaging_ready,
        "delegation_etiquette_contract_ready": etiquette_ready,
        "etiquette_rules": etiquette_rules,
        "rule_count": len(etiquette_rules),
        "forbidden_patterns": forbidden_patterns,
        "authority_boundaries": {
            "units_can_recommend": True,
            "units_can_approve": False,
            "units_can_execute": False,
            "units_can_mutate_runtime": False,
            "units_can_subdelegate": False,
            "operator_facing_presence": "Francis",
        },
        "delivery_semantics": {
            "contract_only": True,
            "sends_messages": False,
            "starts_workers": False,
            "requires_message_envelope": True,
            "requires_trace_context": True,
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
        "next_smallest_truthful_gap": "stage15_trace_continuity_contract"
        if etiquette_ready
        else "stage15_messaging_model_contract",
    }


def swarm_trace_continuity_contract() -> dict[str, Any]:
    etiquette = swarm_delegation_etiquette_contract()
    etiquette_ready = bool(etiquette.get("delegation_etiquette_contract_ready"))
    trace_fields = [
        _trace_field("swarm_trace_id", "stable lineage for the whole swarm task", required=True),
        _trace_field("message_id", "current handoff envelope id", required=True),
        _trace_field("parent_message_id", "immediate causal predecessor", required=True),
        _trace_field("root_objective_id", "operator-facing objective id", required=True),
        _trace_field("sender_role", "bounded sender role", required=True),
        _trace_field("receiver_role", "bounded receiver role", required=True),
        _trace_field("handoff_reason", "why the handoff exists", required=True),
        _trace_field("evidence_refs", "bounded evidence references", required=True),
        _trace_field("decision_state", "accepted, rejected, deadlettered, or retry_requested", required=True),
    ]
    trace_states = ["accepted", "rejected", "deadlettered", "retry_requested"]
    invariants = {
        "one_trace_lineage_required": True,
        "parent_child_links_required_after_first_message": True,
        "root_objective_preserved": True,
        "operator_facing_presence_remains_francis": True,
        "handoff_reason_required": True,
        "trace_fields_do_not_grant_authority": True,
    }
    trace_ready = (
        etiquette_ready
        and len(trace_fields) >= 9
        and all(bool(field.get("field")) for field in trace_fields)
        and all(bool(value) for value in invariants.values())
        and set(trace_states) == {"accepted", "rejected", "deadlettered", "retry_requested"}
    )
    return {
        "ok": True,
        "kind": SWARM_TRACE_CONTINUITY_CONTRACT_KIND,
        "stage": STAGE15_SWARM_STAGE,
        "source_id": "swarm",
        "status": "ready" if trace_ready else "blocked",
        "delegation_etiquette_contract_ready": etiquette_ready,
        "trace_continuity_contract_ready": trace_ready,
        "trace_fields": trace_fields,
        "required_trace_field_count": sum(1 for field in trace_fields if bool(field.get("required"))),
        "trace_states": trace_states,
        "trace_invariants": invariants,
        "sample_trace_projection": {
            "root_objective_id": "operator_objective",
            "swarm_trace_id": "trace_stage15_contract",
            "message_count": 3,
            "roles": ["coordinator", "specialist", "reviewer"],
            "operator_facing_presence": "Francis",
            "authority_granted": False,
        },
        "delivery_semantics": {
            "contract_only": True,
            "sends_messages": False,
            "starts_workers": False,
            "requires_failure_semantics_before_retry_execution": True,
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
        "next_smallest_truthful_gap": "stage15_failure_semantics_contract"
        if trace_ready
        else "stage15_delegation_etiquette_contract",
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


def _etiquette_rule(rule_id: str, summary: str) -> dict[str, Any]:
    return {
        "id": rule_id,
        "summary": summary,
        "enforced_by_contract": True,
        "authority_granted": False,
        "operator_identity_split": False,
        "subdelegation_allowed": False,
        "requires_trace_context": True,
    }


def _trace_field(field: str, description: str, *, required: bool) -> dict[str, Any]:
    return {
        "field": field,
        "description": description,
        "required": required,
        "authority_bearing": False,
        "operator_visible": field in {"swarm_trace_id", "root_objective_id", "decision_state"},
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
