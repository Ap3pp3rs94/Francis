from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from francis.kernel.paths import data_dir, repo_root
from francis.knowledge_fabric import knowledge_fabric_stage12_operator_stage_closure_decision_readback

STAGE13_TRUST_CALIBRATION_STAGE = "Stage 13 / Trust Calibration"
TRUST_CALIBRATION_STATUS_KIND = "francis.stage13.trust_calibration.status"
TRUST_CALIBRATION_CONFIDENCE_RULES_CONTRACT_KIND = "francis.stage13.trust_calibration.confidence_rules_contract"
TRUST_CALIBRATION_VERIFICATION_GATE_CONTRACT_KIND = "francis.stage13.trust_calibration.verification_gate_contract"
TRUST_CALIBRATION_ANTI_OVERCLAIM_POLICY_KIND = "francis.stage13.trust_calibration.anti_overclaim_policy"
TRUST_CALIBRATION_CALIBRATED_CLAIM_LOGIC_KIND = "francis.stage13.trust_calibration.calibrated_claim_logic"
TRUST_CALIBRATION_CLAIM_EVALUATION_KIND = "francis.stage13.trust_calibration.claim_evaluation"
TRUST_CALIBRATION_UI_STATE_COHERENCE_KIND = "francis.stage13.trust_calibration.ui_state_coherence_review"
TRUST_CALIBRATION_OPERATOR_BROWSER_VISUAL_READBACK_RECEIPT_KIND = (
    "francis.stage13.trust_calibration.operator_browser_visual_readback_receipt"
)
TRUST_CALIBRATION_OPERATOR_BROWSER_VISUAL_READBACK_RECEIPTS_KIND = (
    "francis.stage13.trust_calibration.operator_browser_visual_readback_receipts"
)
TRUST_CALIBRATION_BROWSER_VISUAL_READBACK_WRITE_SCOPE = "trust_calibration.browser_visual_readback.write"
_ALLOWED_ENV_PROFILES = {"dev", "workstation"}


def trust_calibration_status_snapshot() -> dict[str, Any]:
    stage12 = knowledge_fabric_stage12_operator_stage_closure_decision_readback(limit=5)
    stage12_closed = bool(stage12.get("stage12_closed_by_receipt"))
    confidence_rules = trust_calibration_confidence_rules_contract()
    confidence_rules_ready = bool(confidence_rules.get("confidence_rules_contract_ready"))
    verification_gates = trust_calibration_verification_gate_contract()
    verification_gates_ready = bool(verification_gates.get("verification_gate_contract_ready"))
    anti_overclaim_policy = trust_calibration_anti_overclaim_policy()
    anti_overclaim_policy_ready = bool(anti_overclaim_policy.get("anti_overclaim_policy_ready"))
    calibrated_claim_logic = trust_calibration_calibrated_claim_logic()
    calibrated_claim_logic_ready = bool(calibrated_claim_logic.get("calibrated_claim_logic_ready"))
    runtime_claim_integration_ready = calibrated_claim_logic_ready
    ui_state_coherence = trust_calibration_ui_state_coherence_review()
    ui_state_coherence_ready = bool(ui_state_coherence.get("ui_state_coherence_review_ready"))
    browser_visual_readback = trust_calibration_operator_browser_visual_readback_receipts(limit=5)
    browser_visual_readback_ready = bool(browser_visual_readback.get("operator_browser_visual_readback_observed"))
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
            anti_overclaim_policy_ready,
            "ready" if anti_overclaim_policy_ready else "pending",
            "stage13_anti_overclaim_policy",
        ),
        _deliverable(
            "calibrated_claim_logic",
            "Runtime claim logic maps evidence strength to calibrated wording",
            calibrated_claim_logic_ready,
            "ready" if calibrated_claim_logic_ready else "pending",
            "stage13_calibrated_claim_logic",
        ),
        _deliverable(
            "ui_state_coherence",
            "Operator shell exposes calibrated claim state without laundering confidence",
            ui_state_coherence_ready,
            "ready" if ui_state_coherence_ready else "pending",
            "stage13_ui_state_coherence",
        ),
        _deliverable(
            "operator_browser_visual_readback",
            "Operator browser visual readback proves the shell renders calibrated state",
            browser_visual_readback_ready,
            "ready" if browser_visual_readback_ready else "pending",
            "stage13_operator_browser_visual_readback",
        ),
    ]
    ready_count = sum(1 for item in deliverables if bool(item["ready"]))
    return {
        "ok": True,
        "kind": TRUST_CALIBRATION_STATUS_KIND,
        "stage": STAGE13_TRUST_CALIBRATION_STAGE,
        "source_id": "trust_calibration",
        "status": "stage13_operator_browser_visual_readback_ready"
        if (
            stage12_closed
            and confidence_rules_ready
            and verification_gates_ready
            and anti_overclaim_policy_ready
            and calibrated_claim_logic_ready
            and ui_state_coherence_ready
            and browser_visual_readback_ready
        )
        else "stage13_ui_state_coherence_ready"
        if (
            stage12_closed
            and confidence_rules_ready
            and verification_gates_ready
            and anti_overclaim_policy_ready
            and calibrated_claim_logic_ready
            and ui_state_coherence_ready
        )
        else "stage13_runtime_claim_evaluator_ready"
        if (
            stage12_closed
            and confidence_rules_ready
            and verification_gates_ready
            and anti_overclaim_policy_ready
            and calibrated_claim_logic_ready
        )
        else "stage13_anti_overclaim_policy_ready"
        if stage12_closed and confidence_rules_ready and verification_gates_ready and anti_overclaim_policy_ready
        else "stage13_verification_gate_contract_ready"
        if stage12_closed and confidence_rules_ready and verification_gates_ready
        else "stage13_confidence_rules_contract_ready"
        if stage12_closed and confidence_rules_ready
        else "awaiting_stage12_ledger_closure",
        "stage12_closed_by_receipt": stage12_closed,
        "stage12_latest_closure_receipt_id": _safe_text(stage12.get("latest_receipt_id")),
        "confidence_rules_contract_ready": confidence_rules_ready,
        "verification_gates_ready": verification_gates_ready,
        "anti_overclaim_policy_ready": anti_overclaim_policy_ready,
        "calibrated_claim_logic_ready": calibrated_claim_logic_ready,
        "runtime_claim_integration_ready": runtime_claim_integration_ready,
        "ui_state_coherence_review_ready": ui_state_coherence_ready,
        "operator_browser_visual_readback_observed": browser_visual_readback_ready,
        "latest_operator_browser_visual_readback_receipt_id": _safe_text(
            browser_visual_readback.get("latest_receipt_id")
        ),
        "deliverables": deliverables,
        "ready_count": ready_count,
        "required_count": len(deliverables),
        "routes": {
            "status": "/trust-calibration/status",
            "confidence_rules_contract": "/trust-calibration/confidence-rules-contract",
            "verification_gate_contract": "/trust-calibration/verification-gate-contract",
            "anti_overclaim_policy": "/trust-calibration/anti-overclaim-policy",
            "calibrated_claim_logic": "/trust-calibration/calibrated-claim-logic",
            "ui_state_coherence": "/trust-calibration/ui-state-coherence",
            "operator_browser_visual_readbacks": "/trust-calibration/operator-browser-visual-readbacks",
            "operator_browser_visual_readback": "/trust-calibration/operator-browser-visual-readback",
            "claim_evaluation": "/trust-calibration/evaluate-claim",
            "stage12_closure_readback": "/knowledge-fabric/stage-closure-decisions",
        },
        "governance": _trust_calibration_governance(),
        "next_smallest_truthful_gap": "stage13_completion_review"
        if (
            stage12_closed
            and confidence_rules_ready
            and verification_gates_ready
            and anti_overclaim_policy_ready
            and calibrated_claim_logic_ready
            and ui_state_coherence_ready
            and browser_visual_readback_ready
        )
        else "stage13_operator_browser_visual_readback"
        if (
            stage12_closed
            and confidence_rules_ready
            and verification_gates_ready
            and anti_overclaim_policy_ready
            and calibrated_claim_logic_ready
            and ui_state_coherence_ready
        )
        else "stage13_ui_state_coherence"
        if (
            stage12_closed
            and confidence_rules_ready
            and verification_gates_ready
            and anti_overclaim_policy_ready
            and calibrated_claim_logic_ready
        )
        else "stage13_calibrated_claim_logic"
        if stage12_closed and confidence_rules_ready and verification_gates_ready and anti_overclaim_policy_ready
        else "stage13_anti_overclaim_policy"
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


def trust_calibration_anti_overclaim_policy() -> dict[str, Any]:
    verification_gates = trust_calibration_verification_gate_contract()
    gates_ready = bool(verification_gates.get("verification_gate_contract_ready"))
    confidence_rules_ready = bool(verification_gates.get("confidence_rules_contract_ready"))
    stage12_closed = bool(verification_gates.get("stage12_closed_by_receipt"))
    policies = [
        {
            "id": "no_false_done",
            "applies_to": ["task_completion", "stage_closure", "ci_status", "proof_script_status"],
            "required_gate": "done_or_closure_claim_gate",
            "must_do": [
                "require_explicit_receipt_or_completion_readback",
                "name_pending_or_blocked_criteria",
                "keep_status_blocked_when_closure_gate_is_not_ready",
            ],
            "forbidden": [
                "call_done_from_intent",
                "call_done_from_partial_test_pass",
                "call_done_from_stale_ledger_text",
            ],
            "fallback_claim_strength": "blocked",
        },
        {
            "id": "no_fake_certainty",
            "applies_to": ["status_summary", "recommendation", "handoff", "answer"],
            "required_gate": "current_state_claim_gate",
            "must_do": [
                "cite_current_readback_for_confirmed_claims",
                "downgrade_to_likely_or_uncertain_when_inputs_are_incomplete",
                "name_missing_verification",
            ],
            "forbidden": [
                "present_likely_as_confirmed",
                "hide_uncertainty_with_confident_tone",
                "collapse_conflicting_evidence_into_single_fact",
            ],
            "fallback_claim_strength": "uncertain",
        },
        {
            "id": "stale_evidence_guard",
            "applies_to": ["roadmap_posture", "ci_state", "runtime_readback", "completion_claim"],
            "required_gate": "stale_or_conflicting_evidence_gate",
            "must_do": [
                "check_recency_before_confirmed_claim",
                "surface_staleness_or_conflict",
                "prefer_live_readback_over_prior_ledger_when_they_disagree",
            ],
            "forbidden": [
                "treat_old_evidence_as_current_proof",
                "ignore_current_blocked_readback",
                "advance_stage_from_superseded_receipt",
            ],
            "fallback_claim_strength": "uncertain",
        },
        {
            "id": "ui_confidence_laundering_guard",
            "applies_to": ["orb", "hud", "chat_ui", "away_report", "lens_cue"],
            "required_gate": "retrieval_backed_claim_gate",
            "must_do": [
                "keep_ui_signal_strength_aligned_to_claim_strength",
                "show_missing_verification_when_state_is_not_confirmed",
                "avoid_visual_language_that_implies_unearned_progress",
            ],
            "forbidden": [
                "make_uncertain_state_look_confirmed",
                "use_progress_language_for_blocked_state",
                "hide_policy_or_receipt_gap_behind_ui_copy",
            ],
            "fallback_claim_strength": "uncertain",
        },
        {
            "id": "blocked_state_preservation",
            "applies_to": ["authority_gate", "readiness_gate", "stage_transition", "execution_precondition"],
            "required_gate": "blocked_state_preservation_gate",
            "must_do": [
                "preserve_blocked_or_denied_status",
                "name_the_specific_missing_scope_or_precondition",
                "keep_recommendation_bounded_to_next_truthful_gap",
            ],
            "forbidden": [
                "relabel_blocked_as_in_progress",
                "recommend_action_as_if_authority_exists",
                "bury_blocker_in_secondary_detail",
            ],
            "fallback_claim_strength": "blocked",
        },
        {
            "id": "authority_claim_guard",
            "applies_to": ["approval", "delegation", "execution", "mutation", "external_action"],
            "required_gate": "authority_or_action_claim_gate",
            "must_do": [
                "require_operator_decision_or_delegation_receipt",
                "require_permission_gate_readback",
                "record_missing_authority_as_blocked",
            ],
            "forbidden": [
                "imply_authority_from_user_preference",
                "imply_approval_from_local_intent",
                "claim_execution_capability_without_scope_readback",
            ],
            "fallback_claim_strength": "blocked",
        },
        {
            "id": "useful_uncertainty",
            "applies_to": ["handoff", "answer", "plan", "risk_summary"],
            "required_gate": "current_state_claim_gate",
            "must_do": [
                "state_what_is_known",
                "state_what_is_missing",
                "offer_or_run_the_smallest_bounded_verification",
            ],
            "forbidden": [
                "stop_at_vague_uncertainty",
                "overload_operator_with_unranked_possibilities",
                "use_disclaimer_instead_of_next_check",
            ],
            "fallback_claim_strength": "uncertain",
        },
    ]
    return {
        "ok": True,
        "kind": TRUST_CALIBRATION_ANTI_OVERCLAIM_POLICY_KIND,
        "stage": STAGE13_TRUST_CALIBRATION_STAGE,
        "source_id": "trust_calibration",
        "status": "ready" if gates_ready else "blocked",
        "anti_overclaim_policy_ready": gates_ready,
        "verification_gate_contract_ready": gates_ready,
        "confidence_rules_contract_ready": confidence_rules_ready,
        "stage12_closed_by_receipt": stage12_closed,
        "stage12_latest_closure_receipt_id": _safe_text(verification_gates.get("stage12_latest_closure_receipt_id")),
        "policies": policies,
        "policy_count": len(policies),
        "required_verification_gates": [gate.get("id", "") for gate in verification_gates.get("gates", [])],
        "required_claim_strengths": ["confirmed", "likely", "uncertain", "blocked"],
        "failure_modes_prevented": [
            "false_done",
            "fake_certainty",
            "smooth_overclaiming",
            "likely_confirmed_mismatch",
            "ui_confidence_laundering",
            "stale_evidence_as_current_proof",
            "blocked_state_laundered_into_progress",
        ],
        "surface_obligations": {
            "confirmed": "cite_current_evidence_and_receipt_or_readback",
            "likely": "name_missing_verification",
            "uncertain": "state_uncertainty_and_next_bounded_check",
            "blocked": "state_blocker_without_implying_progress",
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
        "next_smallest_truthful_gap": "stage13_calibrated_claim_logic"
        if gates_ready
        else "stage13_verification_gate_contract"
        if confidence_rules_ready
        else "stage12_ledger_closure",
    }


def trust_calibration_calibrated_claim_logic() -> dict[str, Any]:
    anti_overclaim = trust_calibration_anti_overclaim_policy()
    policy_ready = bool(anti_overclaim.get("anti_overclaim_policy_ready"))
    gates_ready = bool(anti_overclaim.get("verification_gate_contract_ready"))
    confidence_rules_ready = bool(anti_overclaim.get("confidence_rules_contract_ready"))
    stage12_closed = bool(anti_overclaim.get("stage12_closed_by_receipt"))
    claim_logic_rules = [
        {
            "claim_strength": "confirmed",
            "allowed_when": [
                "current_direct_readback_or_explicit_receipt_exists",
                "claim_scope_matches_evidence_scope",
                "recency_readback_is_current",
                "no_conflicting_current_evidence_is_known",
            ],
            "required_inputs": [
                "current_route_readback_or_explicit_receipt",
                "source_route_or_receipt_id",
                "recency_readback",
                "conflict_check",
            ],
            "allowed_surface_language": [
                "confirmed",
                "current_readback_shows",
                "receipt_records",
            ],
            "forbidden_surface_language": [
                "probably_done",
                "should_be_done",
                "assumed_confirmed",
            ],
            "ui_state": "strong_signal_allowed_only_with_current_evidence",
            "must_cite": True,
            "must_name_missing_verification": False,
        },
        {
            "claim_strength": "likely",
            "allowed_when": [
                "supporting_evidence_exists",
                "one_or_more_verification_inputs_are_incomplete",
                "no_conflicting_current_evidence_is_known",
            ],
            "required_inputs": [
                "supporting_evidence",
                "missing_verification_list",
                "conflict_check",
            ],
            "allowed_surface_language": [
                "likely",
                "appears",
                "based_on_available_evidence",
            ],
            "forbidden_surface_language": [
                "confirmed",
                "closed",
                "guaranteed",
            ],
            "ui_state": "cautious_signal_only",
            "must_cite": True,
            "must_name_missing_verification": True,
        },
        {
            "claim_strength": "uncertain",
            "allowed_when": [
                "evidence_is_missing",
                "evidence_is_stale",
                "evidence_is_conflicting",
                "intent_or_scope_is_ambiguous",
            ],
            "required_inputs": [
                "uncertainty_reason",
                "next_bounded_verification",
            ],
            "allowed_surface_language": [
                "uncertain",
                "not_enough_current_evidence",
                "needs_verification",
            ],
            "forbidden_surface_language": [
                "done",
                "confirmed",
                "safe_to_advance",
            ],
            "ui_state": "neutral_or_attention_signal",
            "must_cite": False,
            "must_name_missing_verification": True,
        },
        {
            "claim_strength": "blocked",
            "allowed_when": [
                "required_authority_is_absent",
                "required_receipt_or_gate_is_missing",
                "safe_execution_precondition_is_not_met",
                "current_readback_reports_blocked",
            ],
            "required_inputs": [
                "blocker_id_or_missing_scope",
                "blocked_state_readback",
                "next_smallest_truthful_gap",
            ],
            "allowed_surface_language": [
                "blocked",
                "cannot_claim_done",
                "requires_receipt_or_authority",
            ],
            "forbidden_surface_language": [
                "in_progress_as_if_unblocked",
                "approved",
                "ready_to_close",
            ],
            "ui_state": "blocked_signal_required",
            "must_cite": True,
            "must_name_missing_verification": True,
        },
    ]
    return {
        "ok": True,
        "kind": TRUST_CALIBRATION_CALIBRATED_CLAIM_LOGIC_KIND,
        "stage": STAGE13_TRUST_CALIBRATION_STAGE,
        "source_id": "trust_calibration",
        "status": "ready" if policy_ready else "blocked",
        "calibrated_claim_logic_ready": policy_ready,
        "anti_overclaim_policy_ready": policy_ready,
        "verification_gate_contract_ready": gates_ready,
        "confidence_rules_contract_ready": confidence_rules_ready,
        "stage12_closed_by_receipt": stage12_closed,
        "stage12_latest_closure_receipt_id": _safe_text(anti_overclaim.get("stage12_latest_closure_receipt_id")),
        "claim_logic_rules": claim_logic_rules,
        "claim_logic_rule_count": len(claim_logic_rules),
        "decision_order": [
            "blocked_state_preservation_before_progress",
            "authority_and_receipt_gates_before_action_claims",
            "recency_and_conflict_checks_before_confirmed_claims",
            "evidence_scope_match_before_strong_language",
            "missing_verification_named_before_likely_or_uncertain_language",
        ],
        "decision_table": [
            {
                "condition": "current_readback_reports_blocked",
                "claim_strength": "blocked",
                "surface_obligation": "preserve_blocked_state_and_name_next_gap",
            },
            {
                "condition": "authority_or_required_receipt_missing",
                "claim_strength": "blocked",
                "surface_obligation": "state_missing_authority_or_receipt",
            },
            {
                "condition": "current_receipt_or_readback_and_no_conflict",
                "claim_strength": "confirmed",
                "surface_obligation": "cite_current_evidence",
            },
            {
                "condition": "supporting_evidence_with_missing_verification",
                "claim_strength": "likely",
                "surface_obligation": "name_missing_verification",
            },
            {
                "condition": "stale_or_conflicting_or_missing_evidence",
                "claim_strength": "uncertain",
                "surface_obligation": "state_uncertainty_and_next_check",
            },
        ],
        "surface_targets": [
            "missions",
            "handbacks",
            "away_reports",
            "lens_cues",
            "retrieval_backed_claims",
            "capability_promotion",
            "incident_handling",
            "orb",
            "hud",
            "chat_ui",
        ],
        "runtime_integration_status": "contract_only_not_enforced",
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
        "next_smallest_truthful_gap": "stage13_runtime_claim_integration"
        if policy_ready
        else "stage13_calibrated_claim_logic"
        if gates_ready
        else "stage12_ledger_closure",
    }


def trust_calibration_claim_evaluation(payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    body = payload if isinstance(payload, Mapping) else {}
    claim_logic = trust_calibration_calibrated_claim_logic()
    runtime_ready = bool(claim_logic.get("calibrated_claim_logic_ready"))
    evidence = _safe_mapping(body.get("evidence"))
    requested_strength = _safe_claim_strength(body.get("requested_claim_strength"))
    claim_text = _bounded_text(body.get("claim_text"), limit=280)
    claim_scope = _bounded_text(body.get("claim_scope"), limit=120)
    result = _evaluate_claim_strength(evidence=evidence, runtime_ready=runtime_ready)
    rule = _claim_logic_rule(claim_logic, result["claim_strength"])
    missing_verification = _missing_verification(evidence=evidence, claim_strength=result["claim_strength"])
    supplied_missing = _safe_text_list(evidence.get("missing_verification"), limit=8)
    for item in supplied_missing:
        if item not in missing_verification:
            missing_verification.append(item)
    return {
        "ok": True,
        "kind": TRUST_CALIBRATION_CLAIM_EVALUATION_KIND,
        "stage": STAGE13_TRUST_CALIBRATION_STAGE,
        "source_id": "trust_calibration",
        "status": "evaluated" if runtime_ready else "blocked",
        "runtime_claim_integration_ready": runtime_ready,
        "calibrated_claim_logic_ready": runtime_ready,
        "anti_overclaim_policy_ready": bool(claim_logic.get("anti_overclaim_policy_ready")),
        "verification_gate_contract_ready": bool(claim_logic.get("verification_gate_contract_ready")),
        "confidence_rules_contract_ready": bool(claim_logic.get("confidence_rules_contract_ready")),
        "stage12_closed_by_receipt": bool(claim_logic.get("stage12_closed_by_receipt")),
        "stage12_latest_closure_receipt_id": _safe_text(claim_logic.get("stage12_latest_closure_receipt_id")),
        "claim_text": claim_text,
        "claim_scope": claim_scope,
        "requested_claim_strength": requested_strength,
        "claim_strength": result["claim_strength"],
        "condition": result["condition"],
        "reason": result["reason"],
        "downgraded": _strength_rank(result["claim_strength"]) < _strength_rank(requested_strength),
        "missing_verification": missing_verification,
        "surface_obligation": result["surface_obligation"],
        "allowed_surface_language": list(rule.get("allowed_surface_language", [])),
        "forbidden_surface_language": list(rule.get("forbidden_surface_language", [])),
        "ui_state": _safe_text(rule.get("ui_state")),
        "must_cite": bool(rule.get("must_cite")),
        "must_name_missing_verification": bool(rule.get("must_name_missing_verification")),
        "next_smallest_truthful_gap": _bounded_text(evidence.get("next_smallest_truthful_gap"), limit=120)
        or result["next_smallest_truthful_gap"],
        "evaluates_supplied_evidence_only": True,
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
        "governance": {
            **_trust_calibration_governance(),
            "evaluates_supplied_evidence_only": True,
            "read_only_evaluation": True,
            "accepts_untrusted_input": True,
            "does_not_persist_evaluation": True,
        },
    }


def trust_calibration_ui_state_coherence_review() -> dict[str, Any]:
    claim_logic = trust_calibration_calibrated_claim_logic()
    runtime_ready = bool(claim_logic.get("calibrated_claim_logic_ready"))
    browser_visual_readback = trust_calibration_operator_browser_visual_readback_receipts(limit=5)
    browser_visual_observed = bool(browser_visual_readback.get("operator_browser_visual_readback_observed"))
    root = repo_root()
    app_path = root / "apps" / "chat_ui" / "src" / "App.tsx"
    dashboard_path = root / "apps" / "chat_ui" / "src" / "trust_dashboard" / "index.ts"
    app_text = _read_source_text(app_path)
    dashboard_text = _read_source_text(dashboard_path)
    source_contracts = [
        _source_contract(
            "operator_shell_card",
            "apps/chat_ui/src/App.tsx",
            app_text,
            [
                'id="francis-trust-calibration"',
                "Stage 13 calibration",
                "Trust calibration",
            ],
        ),
        _source_contract(
            "bounded_shell_claim_request",
            "apps/chat_ui/src/App.tsx",
            app_text,
            [
                "Stage 13 trust calibration claim state is visible in the operator shell",
                'claim_scope: "stage13_ui_state_coherence"',
                'requested_claim_strength: "likely"',
                'missing_verification: ["operator_browser_visual_readback"]',
            ],
        ),
        _source_contract(
            "claim_guard_readback",
            "apps/chat_ui/src/App.tsx",
            app_text,
            [
                "trustCalibrationPresentation.strong_claim_allowed",
                "trustCalibrationPresentation.must_name_missing_verification",
                "trustCalibrationPresentation.runtime_claim_integration_ready",
                "trustCalibrationPresentation.side_effects_denied",
            ],
        ),
        _source_contract(
            "presentation_model",
            "apps/chat_ui/src/trust_dashboard/index.ts",
            dashboard_text,
            [
                "export type TrustCalibrationPresentation",
                "strong_claim_allowed",
                "must_name_missing_verification",
                "side_effects_denied",
                "stage13_ui_state_coherence",
            ],
        ),
    ]
    source_ready = all(bool(item["observed"]) for item in source_contracts)
    review_ready = runtime_ready and source_ready
    return {
        "ok": True,
        "kind": TRUST_CALIBRATION_UI_STATE_COHERENCE_KIND,
        "stage": STAGE13_TRUST_CALIBRATION_STAGE,
        "source_id": "trust_calibration",
        "status": "ready" if review_ready else "blocked",
        "ui_state_coherence_review_ready": review_ready,
        "runtime_claim_integration_ready": runtime_ready,
        "calibrated_claim_logic_ready": runtime_ready,
        "stage12_closed_by_receipt": bool(claim_logic.get("stage12_closed_by_receipt")),
        "stage12_latest_closure_receipt_id": _safe_text(claim_logic.get("stage12_latest_closure_receipt_id")),
        "source_contracts": source_contracts,
        "source_contract_count": len(source_contracts),
        "source_contract_ready_count": sum(1 for item in source_contracts if bool(item["observed"])),
        "operator_shell_card_observed": bool(source_contracts[0]["observed"]),
        "bounded_shell_claim_request_observed": bool(source_contracts[1]["observed"]),
        "claim_guard_readback_observed": bool(source_contracts[2]["observed"]),
        "presentation_model_observed": bool(source_contracts[3]["observed"]),
        "browser_visual_readback_required": True,
        "operator_browser_visual_readback_observed": browser_visual_observed,
        "latest_operator_browser_visual_readback_receipt_id": _safe_text(
            browser_visual_readback.get("latest_receipt_id")
        ),
        "operator_browser_visual_readback_route": "/trust-calibration/operator-browser-visual-readbacks",
        "missing_verification": [] if browser_visual_observed else ["operator_browser_visual_readback"],
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
        "governance": {
            **_trust_calibration_governance(),
            "static_source_readback_only": True,
            "browser_visual_readback_required": True,
            "does_not_launch_browser": True,
            "does_not_mark_stage_closed": True,
        },
        "next_smallest_truthful_gap": "stage13_completion_review"
        if review_ready and browser_visual_observed
        else "stage13_operator_browser_visual_readback"
        if review_ready
        else "stage13_ui_state_coherence",
    }


def trust_calibration_operator_browser_visual_readback_receipts(*, limit: int = 20) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    items = _read_jsonl_tail(_operator_browser_visual_readback_receipt_path(), limit=safe_limit)
    latest = items[-1] if items else {}
    latest_receipt_id = _safe_text(latest.get("receipt_id"))
    return {
        "ok": True,
        "kind": TRUST_CALIBRATION_OPERATOR_BROWSER_VISUAL_READBACK_RECEIPTS_KIND,
        "stage": STAGE13_TRUST_CALIBRATION_STAGE,
        "source_id": "trust_calibration",
        "status": "ready" if latest_receipt_id else "empty",
        "operator_browser_visual_readback_observed": bool(latest_receipt_id),
        "latest_receipt_id": latest_receipt_id,
        "total": len(items),
        "limit": safe_limit,
        "items": items,
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            **_trust_calibration_governance(),
            "explicit_operator_browser_visual_readback_receipts_only": True,
            "does_not_write_receipts": True,
            "does_not_mark_stage_closed": True,
        },
        "next_smallest_truthful_gap": "stage13_completion_review"
        if latest_receipt_id
        else "stage13_operator_browser_visual_readback",
    }


def record_trust_calibration_operator_browser_visual_readback(
    *,
    actor: Any,
    reason: Any,
    claim_text: Any = "",
    surface_id: Any = "",
    browser_name: Any = "",
    viewport: Any = "",
    artifact_paths: Any = None,
    claim_guard_visible: Any = False,
    missing_verification_visible: Any = False,
    forbidden_language_visible: Any = False,
    side_effect_guard_visible: Any = False,
    next_gap_visible: Any = False,
) -> dict[str, Any]:
    env_profile = _env_profile()
    safe_actor = _redacted_text(actor)[:240]
    safe_reason = _redacted_text(reason)[:500]
    if env_profile not in _ALLOWED_ENV_PROFILES:
        return _blocked_browser_visual_readback(
            status="blocked_environment_profile",
            reason="trust_calibration_browser_visual_readback_dev_or_workstation_only",
        )

    observed_flags = {
        "claim_guard_visible": _safe_bool(claim_guard_visible),
        "missing_verification_visible": _safe_bool(missing_verification_visible),
        "forbidden_language_visible": _safe_bool(forbidden_language_visible),
        "side_effect_guard_visible": _safe_bool(side_effect_guard_visible),
        "next_gap_visible": _safe_bool(next_gap_visible),
    }
    readback_observed = all(observed_flags.values())
    receipt_id = f"trust_calibration_browser_visual_{uuid.uuid4().hex[:12]}"
    receipt = {
        "ok": True,
        "kind": TRUST_CALIBRATION_OPERATOR_BROWSER_VISUAL_READBACK_RECEIPT_KIND,
        "receipt_id": receipt_id,
        "stage": STAGE13_TRUST_CALIBRATION_STAGE,
        "source_id": "trust_calibration",
        "target": "stage13_operator_browser_visual_readback",
        "actor": safe_actor,
        "reason": safe_reason,
        "claim_text": _redacted_text(claim_text)[:280],
        "surface_id": _redacted_text(surface_id)[:160],
        "browser_name": _redacted_text(browser_name)[:120],
        "viewport": _redacted_text(viewport)[:80],
        "artifact_paths": _safe_text_list(artifact_paths, limit=6),
        "env_profile": env_profile,
        "recorded_ts": _now_s(),
        "capture_mode": "explicit_operator_browser_visual_readback_receipt",
        "operator_browser_visual_readback_observed": readback_observed,
        **observed_flags,
        "writes_receipt": True,
        "writes_memory": False,
        "scores_model_output": False,
        "changes_ui_confidence": False,
        "enforces_runtime_claims": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            **_trust_calibration_governance(),
            "required_scope": TRUST_CALIBRATION_BROWSER_VISUAL_READBACK_WRITE_SCOPE,
            "dev_or_workstation_only": True,
            "explicit_operator_browser_visual_readback": True,
            "records_supplied_visual_readback_only": True,
            "does_not_launch_browser": True,
            "does_not_capture_screen": True,
            "does_not_mark_stage_closed": True,
        },
        "next_smallest_truthful_gap": "stage13_completion_review"
        if readback_observed
        else "stage13_operator_browser_visual_readback",
    }
    _append_jsonl(_operator_browser_visual_readback_receipt_path(), receipt)
    return receipt


def _blocked_browser_visual_readback(*, status: str, reason: str) -> dict[str, Any]:
    return {
        "ok": False,
        "kind": TRUST_CALIBRATION_OPERATOR_BROWSER_VISUAL_READBACK_RECEIPT_KIND,
        "stage": STAGE13_TRUST_CALIBRATION_STAGE,
        "source_id": "trust_calibration",
        "status": status,
        "reason": reason,
        "required_scope": TRUST_CALIBRATION_BROWSER_VISUAL_READBACK_WRITE_SCOPE,
        "operator_browser_visual_readback_observed": False,
        "writes_receipt": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            **_trust_calibration_governance(),
            "required_scope": TRUST_CALIBRATION_BROWSER_VISUAL_READBACK_WRITE_SCOPE,
            "dev_or_workstation_only": True,
            "does_not_write_receipts": True,
            "does_not_mark_stage_closed": True,
        },
        "next_smallest_truthful_gap": "stage13_operator_browser_visual_readback",
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


def _source_contract(
    contract_id: str,
    source_path: str,
    source_text: str,
    required_tokens: list[str],
) -> dict[str, Any]:
    missing = [token for token in required_tokens if token not in source_text]
    return {
        "id": contract_id,
        "source_path": source_path,
        "observed": len(missing) == 0,
        "required_tokens": required_tokens,
        "missing_tokens": missing,
    }


def _read_source_text(path: Any, *, limit: int = 800_000) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    return text[:limit]


def _operator_browser_visual_readback_receipt_path() -> Path:
    return data_dir() / "logs" / "trust_calibration" / "operator_browser_visual_readbacks.jsonl"


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


def _env_profile() -> str:
    return (os.getenv("FRANCIS_ENV_PROFILE") or "dev").strip().lower() or "dev"


def _now_s() -> int:
    return int(time.time())


def _redacted_text(value: Any) -> str:
    return " ".join(_safe_text(value).split())


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


def _safe_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return value != 0
    return False


def _bounded_text(value: Any, *, limit: int) -> str:
    text = " ".join(_safe_text(value).split())
    return text[:limit]


def _safe_text_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = _bounded_text(item, limit=80)
        if text and text not in items:
            items.append(text)
        if len(items) >= limit:
            break
    return items


def _safe_claim_strength(value: Any) -> str:
    text = _bounded_text(value, limit=40).lower()
    if text in {"confirmed", "likely", "uncertain", "blocked"}:
        return text
    return ""


def _evaluate_claim_strength(*, evidence: Mapping[str, Any], runtime_ready: bool) -> dict[str, str]:
    if not runtime_ready:
        return {
            "claim_strength": "blocked",
            "condition": "trust_calibration_contracts_not_ready",
            "reason": "stage12_ledger_closure_missing",
            "surface_obligation": "state_blocker_without_implying_progress",
            "next_smallest_truthful_gap": "stage12_ledger_closure",
        }
    if _safe_bool(evidence.get("current_readback_reports_blocked")) or _safe_bool(
        evidence.get("blocked_state_readback")
    ):
        return {
            "claim_strength": "blocked",
            "condition": "current_readback_reports_blocked",
            "reason": "blocked_state_readback_present",
            "surface_obligation": "preserve_blocked_state_and_name_next_gap",
            "next_smallest_truthful_gap": "resolve_blocked_state_before_progress_claim",
        }
    if (
        _safe_bool(evidence.get("required_authority_absent"))
        or _safe_bool(evidence.get("required_receipt_or_gate_missing"))
        or evidence.get("safe_execution_precondition_met") is False
    ):
        return {
            "claim_strength": "blocked",
            "condition": "authority_or_required_receipt_missing",
            "reason": "missing_authority_receipt_or_precondition",
            "surface_obligation": "state_missing_authority_or_receipt",
            "next_smallest_truthful_gap": "obtain_required_authority_or_receipt",
        }
    if (
        (_safe_bool(evidence.get("current_route_readback")) or _safe_bool(evidence.get("explicit_receipt")))
        and _safe_bool(evidence.get("recency_readback"))
        and _safe_bool(evidence.get("claim_scope_matches_evidence_scope"))
        and not _safe_bool(evidence.get("conflicting_evidence"))
        and not _safe_bool(evidence.get("stale_evidence"))
    ):
        return {
            "claim_strength": "confirmed",
            "condition": "current_receipt_or_readback_and_no_conflict",
            "reason": "current_evidence_supports_claim",
            "surface_obligation": "cite_current_evidence",
            "next_smallest_truthful_gap": "none_for_this_claim",
        }
    if _safe_bool(evidence.get("supporting_evidence")) and not _safe_bool(evidence.get("conflicting_evidence")):
        return {
            "claim_strength": "likely",
            "condition": "supporting_evidence_with_missing_verification",
            "reason": "supporting_evidence_missing_full_verification",
            "surface_obligation": "name_missing_verification",
            "next_smallest_truthful_gap": "run_or_cite_missing_verification",
        }
    return {
        "claim_strength": "uncertain",
        "condition": "stale_or_conflicting_or_missing_evidence",
        "reason": "missing_stale_or_conflicting_evidence",
        "surface_obligation": "state_uncertainty_and_next_check",
        "next_smallest_truthful_gap": "collect_current_evidence",
    }


def _claim_logic_rule(claim_logic: Mapping[str, Any], claim_strength: str) -> Mapping[str, Any]:
    rules = claim_logic.get("claim_logic_rules")
    if isinstance(rules, list):
        for rule in rules:
            if isinstance(rule, Mapping) and _safe_text(rule.get("claim_strength")) == claim_strength:
                return rule
    return {}


def _missing_verification(*, evidence: Mapping[str, Any], claim_strength: str) -> list[str]:
    if claim_strength == "confirmed":
        required = {
            "current_route_readback_or_explicit_receipt": _safe_bool(evidence.get("current_route_readback"))
            or _safe_bool(evidence.get("explicit_receipt")),
            "recency_readback": _safe_bool(evidence.get("recency_readback")),
            "claim_scope_matches_evidence_scope": _safe_bool(evidence.get("claim_scope_matches_evidence_scope")),
            "conflict_check": not _safe_bool(evidence.get("conflicting_evidence")),
        }
        return [key for key, present in required.items() if not present]
    if claim_strength == "likely":
        required = {
            "current_route_readback_or_explicit_receipt": _safe_bool(evidence.get("current_route_readback"))
            or _safe_bool(evidence.get("explicit_receipt")),
            "recency_readback": _safe_bool(evidence.get("recency_readback")),
            "claim_scope_matches_evidence_scope": _safe_bool(evidence.get("claim_scope_matches_evidence_scope")),
        }
        return [key for key, present in required.items() if not present]
    if claim_strength == "uncertain":
        return ["current_evidence_or_conflict_resolution"]
    if claim_strength == "blocked":
        if _safe_bool(evidence.get("required_authority_absent")):
            return ["required_authority"]
        if _safe_bool(evidence.get("required_receipt_or_gate_missing")):
            return ["required_receipt_or_gate"]
        return ["blocked_state_resolution"]
    return []


def _strength_rank(value: str) -> int:
    return {"": 0, "blocked": 1, "uncertain": 2, "likely": 3, "confirmed": 4}.get(value, 0)
