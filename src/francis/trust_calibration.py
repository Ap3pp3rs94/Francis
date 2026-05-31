from __future__ import annotations

from typing import Any

from francis.knowledge_fabric import knowledge_fabric_stage12_operator_stage_closure_decision_readback

STAGE13_TRUST_CALIBRATION_STAGE = "Stage 13 / Trust Calibration"
TRUST_CALIBRATION_STATUS_KIND = "francis.stage13.trust_calibration.status"
TRUST_CALIBRATION_CONFIDENCE_RULES_CONTRACT_KIND = "francis.stage13.trust_calibration.confidence_rules_contract"
TRUST_CALIBRATION_VERIFICATION_GATE_CONTRACT_KIND = "francis.stage13.trust_calibration.verification_gate_contract"


def trust_calibration_status_snapshot() -> dict[str, Any]:
    stage12 = knowledge_fabric_stage12_operator_stage_closure_decision_readback(limit=5)
    stage12_closed = bool(stage12.get("stage12_closed_by_receipt"))
    confidence_rules = trust_calibration_confidence_rules_contract()
    confidence_rules_ready = bool(confidence_rules.get("confidence_rules_contract_ready"))
    verification_gates = trust_calibration_verification_gate_contract()
    verification_gates_ready = bool(verification_gates.get("verification_gate_contract_ready"))
    deliverables = [
        _deliverable(
            "stage12_ledger_closure_backstop",
            "Stage 12 Knowledge Fabric closure receipt readback is present",
            stage12_closed,
            "ready" if stage12_closed else "blocked",
            "stage12_ledger_closure",
        ),
        _deliverable(
            "confidence_rules",
            "Claim-strength rules define confirmed, likely, uncertain, and blocked states",
            confidence_rules_ready,
            "ready" if confidence_rules_ready else "blocked",
            "stage13_confidence_rules_contract",
        ),
        _deliverable(
            "verification_gates",
            "Trust-sensitive claims pass through explicit verification gates",
            verification_gates_ready,
            "ready" if verification_gates_ready else "pending",
            "stage13_verification_gate_contract",
        ),
        _deliverable(
            "anti_overclaim_policy",
            "Anti-hallucination and anti-overclaim policy is inspectable",
            False,
            "pending",
            "stage13_anti_overclaim_policy",
        ),
        _deliverable(
            "calibrated_claim_logic",
            "Runtime claim logic maps evidence strength to calibrated wording",
            False,
            "pending",
            "stage13_calibrated_claim_logic",
        ),
    ]
    ready_count = sum(1 for item in deliverables if bool(item["ready"]))
    return {
        "ok": True,
        "kind": TRUST_CALIBRATION_STATUS_KIND,
        "stage": STAGE13_TRUST_CALIBRATION_STAGE,
        "source_id": "trust_calibration",
        "status": "stage13_verification_gate_contract_ready"
        if stage12_closed and confidence_rules_ready and verification_gates_ready
        else "stage13_confidence_rules_contract_ready"
        if stage12_closed and confidence_rules_ready
        else "awaiting_stage12_ledger_closure",
        "stage12_closed_by_receipt": stage12_closed,
        "stage12_latest_closure_receipt_id": _safe_text(stage12.get("latest_receipt_id")),
        "confidence_rules_contract_ready": confidence_rules_ready,
        "verification_gates_ready": verification_gates_ready,
        "anti_overclaim_policy_ready": False,
        "calibrated_claim_logic_ready": False,
        "deliverables": deliverables,
        "ready_count": ready_count,
        "required_count": len(deliverables),
        "routes": {
            "status": "/trust-calibration/status",
            "confidence_rules_contract": "/trust-calibration/confidence-rules-contract",
            "verification_gate_contract": "/trust-calibration/verification-gate-contract",
            "stage12_closure_readback": "/knowledge-fabric/stage-closure-decisions",
        },
        "governance": _trust_calibration_governance(),
        "next_smallest_truthful_gap": "stage13_anti_overclaim_policy"
        if stage12_closed and confidence_rules_ready and verification_gates_ready
        else "stage13_verification_gate_contract"
        if stage12_closed and confidence_rules_ready
        else "stage12_ledger_closure",
    }


def trust_calibration_confidence_rules_contract() -> dict[str, Any]:
    stage12 = knowledge_fabric_stage12_operator_stage_closure_decision_readback(limit=5)
    stage12_closed = bool(stage12.get("stage12_closed_by_receipt"))
    claim_strength_rules = [
        {
            "id": "confirmed",
            "label": "Confirmed",
            "allowed_when": [
                "current_direct_readback_or_receipt_exists",
                "source_route_is_known",
                "evidence_is_not_superseded",
                "claim_scope_matches_evidence_scope",
            ],
            "required_surface_behavior": "state_as_confirmed_and_cite_evidence",
            "failure_mode_prevented": "stale_or_indirect_evidence_laundered_into_fact",
        },
        {
            "id": "likely",
            "label": "Likely",
            "allowed_when": [
                "supporting_evidence_exists",
                "one_or_more_verification_inputs_are_incomplete",
                "no_conflicting_current_evidence_is_known",
            ],
            "required_surface_behavior": "state_as_likely_and_name_missing_verification",
            "failure_mode_prevented": "probable_state_presented_as_confirmed",
        },
        {
            "id": "uncertain",
            "label": "Uncertain",
            "allowed_when": [
                "evidence_is_missing",
                "evidence_is_stale",
                "evidence_is_conflicting",
                "intent_or_scope_is_ambiguous",
            ],
            "required_surface_behavior": "state_uncertainty_and_offer_next_verification",
            "failure_mode_prevented": "smooth_overclaiming",
        },
        {
            "id": "blocked",
            "label": "Blocked",
            "allowed_when": [
                "required_authority_is_absent",
                "required_receipt_or_gate_is_missing",
                "safe_execution_precondition_is_not_met",
            ],
            "required_surface_behavior": "state_blocker_without_implying_progress",
            "failure_mode_prevented": "fake_done_or_fake_autonomy",
        },
    ]
    return {
        "ok": True,
        "kind": TRUST_CALIBRATION_CONFIDENCE_RULES_CONTRACT_KIND,
        "stage": STAGE13_TRUST_CALIBRATION_STAGE,
        "source_id": "trust_calibration",
        "status": "ready" if stage12_closed else "blocked",
        "confidence_rules_contract_ready": stage12_closed,
        "stage12_closed_by_receipt": stage12_closed,
        "stage12_latest_closure_receipt_id": _safe_text(stage12.get("latest_receipt_id")),
        "claim_strength_rules": claim_strength_rules,
        "claim_strength_rule_count": len(claim_strength_rules),
        "verification_inputs": [
            "current_route_readback",
            "explicit_receipt",
            "local_evidence_citation",
            "trace_lineage",
            "operator_decision",
            "recency_readback",
        ],
        "anti_overclaim_constraints": {
            "no_false_done": True,
            "no_fake_certainty": True,
            "no_stale_evidence_as_current_proof": True,
            "no_ui_confidence_laundering": True,
            "must_name_missing_verification": True,
            "must_preserve_blocked_state": True,
        },
        "calibration_targets": [
            "missions",
            "handbacks",
            "away_reports",
            "lens_cues",
            "retrieval_backed_claims",
            "capability_promotion",
            "incident_handling",
        ],
        "writes_memory": False,
        "writes_receipts": False,
        "scores_model_output": False,
        "changes_ui_confidence": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": _trust_calibration_governance(),
        "next_smallest_truthful_gap": "stage13_verification_gate_contract"
        if stage12_closed
        else "stage12_ledger_closure",
    }


def trust_calibration_verification_gate_contract() -> dict[str, Any]:
    confidence_rules = trust_calibration_confidence_rules_contract()
    rules_ready = bool(confidence_rules.get("confidence_rules_contract_ready"))
    stage12_closed = bool(confidence_rules.get("stage12_closed_by_receipt"))
    gates = [
        {
            "id": "current_state_claim_gate",
            "claim_scope": "current system state",
            "required_inputs": ["current_route_readback", "recency_readback"],
            "allows_max_strength": "confirmed",
            "downgrade_when_missing": "uncertain",
            "denial_behavior": "name_missing_current_readback",
        },
        {
            "id": "done_or_closure_claim_gate",
            "claim_scope": "done, closed, passed, complete, ready to advance",
            "required_inputs": ["explicit_receipt", "completion_review_or_stage_closure_readback"],
            "allows_max_strength": "confirmed",
            "downgrade_when_missing": "blocked",
            "denial_behavior": "preserve_blocked_or_pending_state",
        },
        {
            "id": "retrieval_backed_claim_gate",
            "claim_scope": "recommendation, summary, or answer based on retrieved evidence",
            "required_inputs": ["local_evidence_citation", "trace_lineage"],
            "allows_max_strength": "likely",
            "downgrade_when_missing": "uncertain",
            "denial_behavior": "ask_for_or_run_bounded_verification_before_stronger_claim",
        },
        {
            "id": "authority_or_action_claim_gate",
            "claim_scope": "authority, approval, execution, or mutation capability",
            "required_inputs": ["operator_decision", "explicit_receipt", "permission_gate_readback"],
            "allows_max_strength": "confirmed",
            "downgrade_when_missing": "blocked",
            "denial_behavior": "do_not_imply_authority_without_receipt",
        },
        {
            "id": "stale_or_conflicting_evidence_gate",
            "claim_scope": "any claim with old, superseded, or conflicting evidence",
            "required_inputs": ["recency_readback", "conflict_check"],
            "allows_max_strength": "uncertain",
            "downgrade_when_missing": "uncertain",
            "denial_behavior": "surface_staleness_or_conflict_before_recommendation",
        },
        {
            "id": "blocked_state_preservation_gate",
            "claim_scope": "blocked, denied, missing-scope, or missing-precondition states",
            "required_inputs": ["blocked_state_readback"],
            "allows_max_strength": "blocked",
            "downgrade_when_missing": "blocked",
            "denial_behavior": "do_not_launder_blocked_state_into_progress",
        },
    ]
    return {
        "ok": True,
        "kind": TRUST_CALIBRATION_VERIFICATION_GATE_CONTRACT_KIND,
        "stage": STAGE13_TRUST_CALIBRATION_STAGE,
        "source_id": "trust_calibration",
        "status": "ready" if rules_ready else "blocked",
        "verification_gate_contract_ready": rules_ready,
        "confidence_rules_contract_ready": rules_ready,
        "stage12_closed_by_receipt": stage12_closed,
        "stage12_latest_closure_receipt_id": _safe_text(confidence_rules.get("stage12_latest_closure_receipt_id")),
        "gates": gates,
        "gate_count": len(gates),
        "required_claim_strengths": ["confirmed", "likely", "uncertain", "blocked"],
        "gate_order": [
            "stage_or_completion_claims_before_progress_claims",
            "authority_claims_before_action_claims",
            "recency_checks_before_confirmed_claims",
            "blocked_state_preservation_before_recommendation",
        ],
        "denial_behavior": {
            "missing_receipt": "blocked",
            "missing_current_readback": "uncertain",
            "stale_evidence": "uncertain",
            "conflicting_evidence": "uncertain",
            "missing_authority": "blocked",
        },
        "writes_memory": False,
        "writes_receipts": False,
        "scores_model_output": False,
        "changes_ui_confidence": False,
        "enforces_runtime_claims": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": _trust_calibration_governance(),
        "next_smallest_truthful_gap": "stage13_anti_overclaim_policy" if rules_ready else "stage12_ledger_closure",
    }


def _trust_calibration_governance() -> dict[str, Any]:
    return {
        "read_only": True,
        "requires_stage12_ledger_closure": True,
        "contract_only": True,
        "does_not_enforce_runtime_claims": True,
        "does_not_score_model_output": True,
        "does_not_change_ui_confidence": True,
        "does_not_write_memory": True,
        "does_not_write_receipts": True,
        "does_not_run_tools": True,
        "does_not_run_shell": True,
        "does_not_run_git": True,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def _deliverable(
    deliverable_id: str,
    label: str,
    ready: bool,
    status: str,
    next_gap: str,
) -> dict[str, Any]:
    return {
        "id": deliverable_id,
        "label": label,
        "ready": ready,
        "status": status,
        "next_smallest_truthful_gap": next_gap,
    }


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""
