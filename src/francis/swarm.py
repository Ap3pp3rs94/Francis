from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from francis.adversarial_hardening import adversarial_hardening_stage14_operator_stage_closure_decision_readback
from francis.collective.swarm import CollectiveLearning, EmergentBehavior, SwarmCoordinator
from francis.kernel.paths import data_dir
from francis.telemetry.audit import record as audit_record

STAGE15_SWARM_STAGE = "Stage 15 / Swarm"
SWARM_STATUS_KIND = "francis.stage15.swarm.status"
SWARM_UNIT_ROLES_CONTRACT_KIND = "francis.stage15.swarm.unit_roles_contract"
SWARM_MESSAGING_MODEL_CONTRACT_KIND = "francis.stage15.swarm.messaging_model_contract"
SWARM_DELEGATION_ETIQUETTE_CONTRACT_KIND = "francis.stage15.swarm.delegation_etiquette_contract"
SWARM_TRACE_CONTINUITY_CONTRACT_KIND = "francis.stage15.swarm.trace_continuity_contract"
SWARM_FAILURE_SEMANTICS_CONTRACT_KIND = "francis.stage15.swarm.failure_semantics_contract"
SWARM_COMPLETION_REVIEW_KIND = "francis.stage15.swarm.completion_review"
SWARM_STAGE_CLOSURE_DECISION_KIND = "francis.stage15.swarm.stage15_closure_decision_receipt"
SWARM_STAGE_CLOSURE_DECISIONS_KIND = "francis.stage15.swarm.stage15_closure_decision_receipts"
SWARM_STAGE_CLOSURE_SCOPE = "swarm.stage15.closure.write"


def swarm_status_snapshot() -> dict[str, Any]:
    stage14 = adversarial_hardening_stage14_operator_stage_closure_decision_readback(limit=5)
    stage14_closed = bool(stage14.get("stage14_closed_by_receipt"))
    stage15_closure = swarm_stage15_operator_stage_closure_decision_readback(limit=5)
    stage15_closed = bool(stage15_closure.get("stage15_closed_by_receipt"))
    unit_roles = swarm_unit_roles_contract()
    unit_roles_ready = bool(unit_roles.get("unit_roles_contract_ready"))
    messaging_model = swarm_messaging_model_contract()
    messaging_model_ready = bool(messaging_model.get("messaging_model_contract_ready"))
    delegation_etiquette = swarm_delegation_etiquette_contract()
    delegation_etiquette_ready = bool(delegation_etiquette.get("delegation_etiquette_contract_ready"))
    trace_continuity = swarm_trace_continuity_contract()
    trace_continuity_ready = bool(trace_continuity.get("trace_continuity_contract_ready"))
    failure_semantics = swarm_failure_semantics_contract()
    failure_semantics_ready = bool(failure_semantics.get("failure_semantics_contract_ready"))
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
            failure_semantics_ready,
            "ready" if failure_semantics_ready else "pending",
            "stage15_failure_semantics_contract",
        ),
    ]
    ready_count = sum(1 for item in deliverables if bool(item["ready"]))
    return {
        "ok": True,
        "kind": SWARM_STATUS_KIND,
        "stage": STAGE15_SWARM_STAGE,
        "source_id": "swarm",
        "status": "stage15_closed_by_receipt"
        if stage15_closed
        else "stage15_failure_semantics_contract_ready"
        if stage14_closed
        and unit_roles_ready
        and messaging_model_ready
        and delegation_etiquette_ready
        and trace_continuity_ready
        and failure_semantics_ready
        else "stage15_trace_continuity_contract_ready"
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
        "stage15_closed_by_receipt": stage15_closed,
        "stage15_latest_closure_receipt_id": _safe_text(stage15_closure.get("latest_receipt_id")),
        "unit_roles_contract_ready": unit_roles_ready,
        "messaging_model_contract_ready": messaging_model_ready,
        "delegation_etiquette_contract_ready": delegation_etiquette_ready,
        "trace_continuity_contract_ready": trace_continuity_ready,
        "failure_semantics_contract_ready": failure_semantics_ready,
        "deliverables": deliverables,
        "ready_count": ready_count,
        "required_count": len(deliverables),
        "routes": {
            "status": "/swarm/status",
            "unit_roles_contract": "/swarm/unit-roles-contract",
            "messaging_model_contract": "/swarm/messaging-model-contract",
            "delegation_etiquette_contract": "/swarm/delegation-etiquette-contract",
            "trace_continuity_contract": "/swarm/trace-continuity-contract",
            "failure_semantics_contract": "/swarm/failure-semantics-contract",
            "completion_review": "/swarm/completion-review",
            "stage_closure_decisions": "/swarm/stage-closure-decisions",
            "stage_closure_decision": "/swarm/stage-closure-decision",
            "stage14_closure_readback": "/adversarial-hardening/stage-closure-decisions",
        },
        "governance": _governance(),
        "next_smallest_truthful_gap": "stage15_ledger_closure"
        if stage15_closed
        else "stage15_completion_review"
        if stage14_closed
        and unit_roles_ready
        and messaging_model_ready
        and delegation_etiquette_ready
        and trace_continuity_ready
        and failure_semantics_ready
        else "stage15_failure_semantics_contract"
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


def swarm_failure_semantics_contract() -> dict[str, Any]:
    trace = swarm_trace_continuity_contract()
    trace_ready = bool(trace.get("trace_continuity_contract_ready"))
    failure_states = [
        _failure_state("accepted", "handoff accepted by receiver", terminal=False, retryable=False),
        _failure_state("rejected", "handoff rejected with reason and evidence refs", terminal=True, retryable=False),
        _failure_state(
            "deadlettered",
            "handoff cannot be processed without operator-visible review",
            terminal=True,
            retryable=False,
        ),
        _failure_state(
            "retry_requested", "bounded retry requested without executing automatically", terminal=False, retryable=True
        ),
        _failure_state(
            "timed_out",
            "handoff exceeded bounded wait and must be deadlettered or reviewed",
            terminal=True,
            retryable=False,
        ),
    ]
    retry_policy = {
        "automatic_retry_executes": False,
        "max_contract_retry_attempts": 1,
        "retry_requires_same_swarm_trace_id": True,
        "retry_requires_parent_message_id": True,
        "retry_requires_reason": True,
        "retry_can_grant_authority": False,
    }
    deadletter_policy = {
        "deadletter_requires_trace_context": True,
        "deadletter_requires_failure_reason": True,
        "deadletter_operator_visible": True,
        "deadletter_preserves_one_francis_presence": True,
        "deadletter_writes_memory": False,
        "deadletter_runs_tools": False,
    }
    failure_ready = (
        trace_ready
        and len(failure_states) >= 5
        and all(bool(state.get("state")) for state in failure_states)
        and all(
            value is False
            for key, value in retry_policy.items()
            if key.endswith("executes") or key.endswith("authority")
        )
        and all(
            bool(value)
            for key, value in deadletter_policy.items()
            if key not in {"deadletter_writes_memory", "deadletter_runs_tools"}
        )
        and not bool(deadletter_policy.get("deadletter_writes_memory"))
        and not bool(deadletter_policy.get("deadletter_runs_tools"))
    )
    return {
        "ok": True,
        "kind": SWARM_FAILURE_SEMANTICS_CONTRACT_KIND,
        "stage": STAGE15_SWARM_STAGE,
        "source_id": "swarm",
        "status": "ready" if failure_ready else "blocked",
        "trace_continuity_contract_ready": trace_ready,
        "failure_semantics_contract_ready": failure_ready,
        "failure_states": failure_states,
        "failure_state_count": len(failure_states),
        "retry_policy": retry_policy,
        "deadletter_policy": deadletter_policy,
        "delivery_semantics": {
            "contract_only": True,
            "sends_messages": False,
            "starts_workers": False,
            "executes_retries": False,
            "writes_deadletters": False,
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
        "next_smallest_truthful_gap": "stage15_completion_review"
        if failure_ready
        else "stage15_trace_continuity_contract",
    }


def swarm_completion_review() -> dict[str, Any]:
    status = swarm_status_snapshot()
    unit_roles = swarm_unit_roles_contract()
    messaging = swarm_messaging_model_contract()
    etiquette = swarm_delegation_etiquette_contract()
    trace = swarm_trace_continuity_contract()
    failure = swarm_failure_semantics_contract()
    stage15_closed = bool(status.get("stage15_closed_by_receipt"))
    deliverables = [item for item in status.get("deliverables", []) if isinstance(item, dict)]
    ready_count = _safe_int(status.get("ready_count"))
    required_count = _safe_int(status.get("required_count"))
    checks = [
        _review_check(
            "stage14_ledger_closure_backstop",
            passed=bool(status.get("stage14_closed_by_receipt")),
            evidence=_safe_text(status.get("stage14_latest_closure_receipt_id"))
            or "/adversarial-hardening/stage-closure-decisions",
        ),
        _review_check(
            "unit_roles_contract_ready",
            passed=bool(status.get("unit_roles_contract_ready")),
            evidence="/swarm/unit-roles-contract",
        ),
        _review_check(
            "messaging_model_contract_ready",
            passed=bool(status.get("messaging_model_contract_ready")),
            evidence="/swarm/messaging-model-contract",
        ),
        _review_check(
            "delegation_etiquette_contract_ready",
            passed=bool(status.get("delegation_etiquette_contract_ready")),
            evidence="/swarm/delegation-etiquette-contract",
        ),
        _review_check(
            "trace_continuity_contract_ready",
            passed=bool(status.get("trace_continuity_contract_ready")),
            evidence="/swarm/trace-continuity-contract",
        ),
        _review_check(
            "failure_semantics_contract_ready",
            passed=bool(status.get("failure_semantics_contract_ready")),
            evidence="/swarm/failure-semantics-contract",
        ),
        _review_check(
            "all_deliverables_ready",
            passed=bool(deliverables)
            and ready_count == required_count
            and required_count >= 1
            and all(bool(item.get("ready")) for item in deliverables),
            evidence="swarm.status.deliverables",
        ),
        _review_check(
            "one_francis_presence_preserved",
            passed=bool(unit_roles.get("role_invariants", {}).get("operator_facing_identity_remains_francis"))
            and bool(etiquette.get("authority_boundaries", {}).get("operator_facing_presence") == "Francis")
            and bool(trace.get("sample_trace_projection", {}).get("operator_facing_presence") == "Francis"),
            evidence="unit_roles + delegation_etiquette + trace_continuity",
        ),
        _review_check(
            "handoffs_visible_and_auditable",
            passed=bool(messaging.get("message_invariants", {}).get("swarm_trace_id_required"))
            and bool(trace.get("trace_invariants", {}).get("one_trace_lineage_required"))
            and bool(failure.get("deadletter_policy", {}).get("deadletter_operator_visible")),
            evidence="messaging_model + trace_continuity + failure_semantics",
        ),
        _review_check(
            "specialization_does_not_multiply_authority",
            passed=bool(etiquette.get("authority_boundaries", {}).get("units_can_approve") is False)
            and bool(failure.get("retry_policy", {}).get("retry_can_grant_authority") is False)
            and bool(unit_roles.get("role_invariants", {}).get("unit_roles_do_not_grant_authority")),
            evidence="unit_roles + delegation_etiquette + failure_semantics",
        ),
    ]
    review_ready = all(bool(check.get("passed")) for check in checks)
    blockers = [str(check["id"]) for check in checks if not bool(check.get("passed"))]
    return {
        "ok": True,
        "kind": SWARM_COMPLETION_REVIEW_KIND,
        "stage": STAGE15_SWARM_STAGE,
        "source_id": "swarm",
        "status": "ready" if review_ready else "blocked",
        "stage15_completion_review_ready": review_ready,
        "stage_closure_decision_required": review_ready and not stage15_closed,
        "stage14_closed_by_receipt": bool(status.get("stage14_closed_by_receipt")),
        "stage14_latest_closure_receipt_id": _safe_text(status.get("stage14_latest_closure_receipt_id")),
        "stage15_closed_by_receipt": stage15_closed,
        "stage15_latest_closure_receipt_id": _safe_text(status.get("stage15_latest_closure_receipt_id")),
        "ready_count": ready_count,
        "required_count": required_count,
        "checks": checks,
        "blockers": blockers,
        "done_criteria": {
            "units_collaborate_safely": bool(unit_roles.get("unit_roles_contract_ready"))
            and bool(etiquette.get("delegation_etiquette_contract_ready"))
            and bool(failure.get("failure_semantics_contract_ready")),
            "handoffs_visible_and_auditable": bool(trace.get("trace_continuity_contract_ready"))
            and bool(failure.get("failure_semantics_contract_ready")),
            "one_francis_presence_preserved": bool(
                unit_roles.get("role_invariants", {}).get("operator_facing_identity_remains_francis")
            )
            and bool(etiquette.get("authority_boundaries", {}).get("operator_facing_presence") == "Francis"),
            "specialization_adds_precision_instead_of_chaos": bool(unit_roles.get("unit_roles_contract_ready"))
            and bool(etiquette.get("delegation_etiquette_contract_ready")),
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
        "marks_stage_closed": False,
        "governance": {
            **_governance(),
            "completion_review_only": True,
            "stage_closure_decision_required": review_ready and not stage15_closed,
            "requires_stage14_ledger_closure": True,
            "requires_unit_roles": True,
            "requires_messaging_model": True,
            "requires_delegation_etiquette": True,
            "requires_trace_continuity": True,
            "requires_failure_semantics": True,
            "does_not_mark_stage_closed": True,
        },
        "routes": status.get("routes", {}),
        "next_smallest_truthful_gap": "stage15_operator_stage_closure_decision"
        if review_ready and not stage15_closed
        else "stage15_ledger_closure"
        if stage15_closed
        else _safe_text(status.get("next_smallest_truthful_gap")) or "stage15_completion_review",
    }


def read_swarm_stage15_operator_stage_closure_decisions(*, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl_tail(_stage15_operator_stage_closure_decision_path(), limit=_safe_limit(limit))


def swarm_stage15_operator_stage_closure_decision_readback(*, limit: int = 20) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    items = read_swarm_stage15_operator_stage_closure_decisions(limit=safe_limit)
    latest = items[-1] if items else {}
    stage15_closed = bool(latest.get("stage15_closed_by_receipt"))
    return {
        "ok": True,
        "kind": SWARM_STAGE_CLOSURE_DECISIONS_KIND,
        "stage": STAGE15_SWARM_STAGE,
        "source_id": "swarm",
        "status": "closed" if stage15_closed else "open" if items else "empty",
        "items": items,
        "count": len(items),
        "limit": safe_limit,
        "latest_receipt_id": _safe_text(latest.get("receipt_id")),
        "latest_decision": _safe_text(latest.get("decision")),
        "stage15_closed_by_receipt": stage15_closed,
        "marks_runtime_stage_state": False,
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
        "governance": {
            **_governance(),
            "stage_closure_decision_receipt_readback": True,
            "does_not_mutate_runtime_stage_state": True,
            "does_not_mark_stage_closed": True,
        },
        "next_smallest_truthful_gap": "stage15_ledger_closure"
        if stage15_closed
        else "stage15_operator_stage_closure_decision"
        if items
        else "stage15_completion_review",
    }


def record_swarm_stage15_operator_stage_closure_decision(
    *,
    actor: Any,
    reason: Any,
    decision: Any,
    review: dict[str, Any],
    notes: Any = "",
    authority: Any = "operator",
    delegation_id: Any = "",
    delegated_operator: bool = False,
) -> dict[str, Any]:
    safe_decision = _safe_stage15_closure_decision(decision)
    closure_ready = bool(review.get("stage15_completion_review_ready"))
    stage15_closed_by_receipt = safe_decision == "close_stage15" and closure_ready
    receipt_id = f"swarm_stage15_closure_{uuid.uuid4().hex[:12]}"
    clean_authority = _safe_text(authority) or "operator"
    clean_delegation_id = _safe_text(delegation_id)
    payload = {
        "ok": True,
        "kind": SWARM_STAGE_CLOSURE_DECISION_KIND,
        "receipt_id": receipt_id,
        "stage": STAGE15_SWARM_STAGE,
        "source_id": "swarm",
        "capture_mode": "explicit_operator_stage_closure_decision",
        "target": "stage15_swarm",
        "actor": _redacted_text(actor)[:240],
        "reason": _redacted_text(reason)[:500],
        "decision": safe_decision,
        "notes": _redacted_text(notes)[:500],
        "authority": clean_authority,
        "delegation_id": clean_delegation_id,
        "delegated_operator_approval": bool(delegated_operator),
        "review_status": _safe_text(review.get("status")),
        "completion_review_ready": closure_ready,
        "stage15_completion_review_ready": closure_ready,
        "stage14_closure_receipt_id": _safe_text(review.get("stage14_latest_closure_receipt_id")),
        "ready_count": _safe_int(review.get("ready_count")),
        "required_count": _safe_int(review.get("required_count")),
        "blockers": _safe_text_list(review.get("blockers"), limit=20),
        "done_criteria": _as_dict(review.get("done_criteria")),
        "stage15_closed_by_receipt": stage15_closed_by_receipt,
        "marks_runtime_stage_state": False,
        "recorded_ts": _now_s(),
        "writes_receipt": True,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            **_governance(),
            "read_only": False,
            "permission_scope": SWARM_STAGE_CLOSURE_SCOPE,
            "explicit_operator_decision": True,
            "stage_closure_decision": True,
            "authority": clean_authority,
            "delegation_id": clean_delegation_id,
            "delegated_operator_authority": bool(delegated_operator),
            "completion_review_ready": closure_ready,
            "writes_receipt": True,
            "does_not_write_receipts": False,
            "does_not_mutate_runtime_stage_state": True,
            "does_not_mark_stage_closed": True,
        },
        "next_smallest_truthful_gap": "stage15_ledger_closure"
        if stage15_closed_by_receipt
        else "stage15_operator_stage_closure_decision",
    }
    _append_jsonl(_stage15_operator_stage_closure_decision_path(), payload)
    audit_record(
        "swarm.stage15_closure_decision_recorded",
        actor=payload["actor"],
        reason=payload["reason"],
        receipt_id=receipt_id,
        decision=safe_decision,
        authority=clean_authority,
        delegation_id=clean_delegation_id,
        stage15_closed_by_receipt=stage15_closed_by_receipt,
    )
    return payload


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


def _failure_state(state: str, summary: str, *, terminal: bool, retryable: bool) -> dict[str, Any]:
    return {
        "state": state,
        "summary": summary,
        "terminal": terminal,
        "retryable": retryable,
        "requires_trace_context": True,
        "requires_evidence_refs": True,
        "authority_granted": False,
        "executes_action": False,
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


def _review_check(check_id: str, *, passed: bool, evidence: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "passed": passed,
        "status": "passed" if passed else "blocked",
        "evidence": evidence,
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


def _stage15_operator_stage_closure_decision_path() -> Path:
    return data_dir() / "logs" / "swarm" / "stage15_operator_stage_closure_decisions.jsonl"


def _append_jsonl(path: Path, item: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(item, sort_keys=True, separators=(",", ":")))
        handle.write("\n")


def _read_jsonl_tail(path: Path, *, limit: int = 20) -> list[dict[str, Any]]:
    if limit <= 0 or not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    items: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            items.append(parsed)
    return items


def _safe_limit(value: Any, *, default: int = 20, maximum: int = 100) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, 1), maximum)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_stage15_closure_decision(value: Any) -> str:
    text = _safe_text(value)
    if text in {"close_stage15", "do_not_close_stage15", "needs_more_evidence"}:
        return text
    return "needs_more_evidence"


def _safe_text_list(value: Any, *, limit: int = 20) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value[:limit]:
        text = _safe_text(item)
        if text:
            items.append(text[:240])
    return items


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now_s() -> int:
    return int(time.time())


def _redacted_text(value: Any) -> str:
    return " ".join(_safe_text(value).split())


def _safe_text(value: Any) -> str:
    return str(value or "").strip()
