from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from francis.away import away_stage10_operator_stage_closure_decision_readback
from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir
from francis.telemetry.audit import record as audit_record

STAGE11_APPRENTICESHIP_STAGE = "Stage 11 / Apprenticeship"
APPRENTICESHIP_STATUS_KIND = "francis.stage11.apprenticeship.status"
APPRENTICESHIP_TEACHING_SESSION_CONTRACT_KIND = "francis.stage11.apprenticeship.teaching_session_contract"
APPRENTICESHIP_REPLAY_GENERALIZATION_CONTRACT_KIND = "francis.stage11.apprenticeship.replay_generalization_contract"
APPRENTICESHIP_SKILLIZATION_ARTIFACT_CONTRACT_KIND = "francis.stage11.apprenticeship.skillization_artifact_contract"
APPRENTICESHIP_FORGE_HANDOFF_CONTRACT_KIND = "francis.stage11.apprenticeship.forge_handoff_contract"
APPRENTICESHIP_LIVE_TEACHING_SESSION_UX_KIND = "francis.stage11.apprenticeship.live_teaching_session_ux"
APPRENTICESHIP_TEACHING_SESSION_RECEIPT_KIND = "francis.stage11.apprenticeship.teaching_session_receipt"
APPRENTICESHIP_TEACHING_SESSION_RECEIPTS_KIND = "francis.stage11.apprenticeship.teaching_session_receipts"
APPRENTICESHIP_REPLAY_RECEIPT_KIND = "francis.stage11.apprenticeship.replay_receipt"
APPRENTICESHIP_REPLAY_RECEIPTS_KIND = "francis.stage11.apprenticeship.replay_receipts"
APPRENTICESHIP_SKILLIZATION_ARTIFACT_RECEIPT_KIND = "francis.stage11.apprenticeship.skillization_artifact_receipt"
APPRENTICESHIP_SKILLIZATION_ARTIFACT_RECEIPTS_KIND = "francis.stage11.apprenticeship.skillization_artifact_receipts"
APPRENTICESHIP_FORGE_HANDOFF_RECEIPT_KIND = "francis.stage11.apprenticeship.forge_handoff_receipt"
APPRENTICESHIP_FORGE_HANDOFF_RECEIPTS_KIND = "francis.stage11.apprenticeship.forge_handoff_receipts"

APPRENTICESHIP_TEACHING_SESSION_WRITE_SCOPE = "apprenticeship.teaching_session.write"
APPRENTICESHIP_REPLAY_RECEIPT_WRITE_SCOPE = "apprenticeship.replay_receipt.write"
APPRENTICESHIP_SKILLIZATION_ARTIFACT_WRITE_SCOPE = "apprenticeship.skillization_artifact.write"
APPRENTICESHIP_FORGE_HANDOFF_WRITE_SCOPE = "apprenticeship.forge_handoff.write"

_ALLOWED_ENV_PROFILES = {"dev", "workstation", "local", "test"}
_ALLOWED_TEACHING_SESSION_ACTIONS = {
    "start_teaching_session",
    "stop_teaching_session",
    "label_intent",
    "record_demonstration_summary",
    "review_replay",
    "review_generalization",
    "prepare_skillization_artifact",
}
_ALLOWED_REPLAY_RECEIPT_ACTIONS = {
    "review_replay",
    "approve_replay",
    "request_replay_changes",
    "review_generalization",
    "approve_generalization",
}
_ALLOWED_SKILLIZATION_ARTIFACT_ACTIONS = {
    "prepare_skillization_artifact",
    "review_skillization_artifact",
    "request_skillization_changes",
    "approve_forge_candidate",
}
_ALLOWED_FORGE_HANDOFF_ACTIONS = {
    "review_forge_handoff",
    "stage_forge_handoff",
    "request_forge_handoff_changes",
    "approve_forge_proposal_candidate",
}


def apprenticeship_status_snapshot() -> dict[str, Any]:
    stage10 = away_stage10_operator_stage_closure_decision_readback(limit=5)
    stage10_closed = bool(stage10.get("stage10_closed_by_receipt"))
    teaching_session = apprenticeship_teaching_session_contract()
    teaching_session_ready = bool(teaching_session.get("teaching_session_contract_ready"))
    replay_generalization = apprenticeship_replay_generalization_contract()
    replay_generalization_ready = bool(replay_generalization.get("replay_generalization_contract_ready"))
    skillization_artifact = apprenticeship_skillization_artifact_contract()
    skillization_ready = bool(skillization_artifact.get("skillization_artifact_contract_ready"))
    forge_handoff = apprenticeship_forge_handoff_contract()
    forge_handoff_ready = bool(forge_handoff.get("forge_handoff_contract_ready"))
    live_teaching_session_ux = apprenticeship_live_teaching_session_ux()
    live_teaching_session_ux_ready = bool(live_teaching_session_ux.get("live_teaching_session_ux_ready"))
    teaching_session_receipts = read_apprenticeship_teaching_session_receipts(limit=5)
    latest_teaching_session_receipt_id = (
        _safe_text(teaching_session_receipts[-1].get("receipt_id")) if teaching_session_receipts else ""
    )
    teaching_session_receipt_ready = bool(latest_teaching_session_receipt_id)
    replay_receipts = read_apprenticeship_replay_receipts(limit=5)
    latest_replay_receipt_id = _safe_text(replay_receipts[-1].get("receipt_id")) if replay_receipts else ""
    replay_receipt_ready = bool(latest_replay_receipt_id)
    skillization_artifact_receipts = read_apprenticeship_skillization_artifact_receipts(limit=5)
    latest_skillization_artifact_receipt_id = (
        _safe_text(skillization_artifact_receipts[-1].get("receipt_id")) if skillization_artifact_receipts else ""
    )
    skillization_artifact_receipt_ready = bool(latest_skillization_artifact_receipt_id)
    forge_handoff_receipts = read_apprenticeship_forge_handoff_receipts(limit=5)
    latest_forge_handoff_receipt_id = (
        _safe_text(forge_handoff_receipts[-1].get("receipt_id")) if forge_handoff_receipts else ""
    )
    forge_handoff_receipt_ready = bool(latest_forge_handoff_receipt_id)
    deliverables = _apprenticeship_deliverables(
        stage10_closed=stage10_closed,
        teaching_session_ready=teaching_session_ready,
        replay_generalization_ready=replay_generalization_ready,
        skillization_ready=skillization_ready,
        forge_handoff_ready=forge_handoff_ready,
    )
    ready_count = sum(1 for item in deliverables if bool(item.get("ready")))
    required_count = len(deliverables)
    return {
        "ok": True,
        "kind": APPRENTICESHIP_STATUS_KIND,
        "stage": STAGE11_APPRENTICESHIP_STAGE,
        "source_id": "apprenticeship",
        "status": "stage11_forge_handoff_receipt_ready"
        if stage10_closed
        and live_teaching_session_ux_ready
        and teaching_session_receipt_ready
        and replay_receipt_ready
        and skillization_artifact_receipt_ready
        and forge_handoff_receipt_ready
        else "stage11_skillization_artifact_receipt_ready"
        if stage10_closed
        and live_teaching_session_ux_ready
        and teaching_session_receipt_ready
        and replay_receipt_ready
        and skillization_artifact_receipt_ready
        else "stage11_replay_receipt_ready"
        if stage10_closed and live_teaching_session_ux_ready and teaching_session_receipt_ready and replay_receipt_ready
        else "stage11_teaching_session_receipt_ready"
        if stage10_closed and live_teaching_session_ux_ready and teaching_session_receipt_ready
        else "stage11_operator_surface_ready"
        if stage10_closed and live_teaching_session_ux_ready
        else "stage11_contracts_ready"
        if stage10_closed and forge_handoff_ready
        else "stage11_groundwork_ready"
        if stage10_closed
        else "awaiting_stage10_ledger_closure",
        "stage10_closed_by_receipt": stage10_closed,
        "stage10_latest_closure_receipt_id": _safe_text(stage10.get("latest_receipt_id")),
        "stage10_next_smallest_truthful_gap": _safe_text(stage10.get("next_smallest_truthful_gap")),
        "deliverables": deliverables,
        "ready_count": ready_count,
        "required_count": required_count,
        "teaching_session_ready": teaching_session_ready,
        "replay_generalization_ready": replay_generalization_ready,
        "skillization_ready": skillization_ready,
        "forge_handoff_ready": forge_handoff_ready,
        "live_teaching_session_ux_ready": live_teaching_session_ux_ready,
        "teaching_session_receipt_ready": teaching_session_receipt_ready,
        "latest_teaching_session_receipt_id": latest_teaching_session_receipt_id,
        "replay_receipt_ready": replay_receipt_ready,
        "latest_replay_receipt_id": latest_replay_receipt_id,
        "skillization_artifact_receipt_ready": skillization_artifact_receipt_ready,
        "latest_skillization_artifact_receipt_id": latest_skillization_artifact_receipt_id,
        "forge_handoff_receipt_ready": forge_handoff_receipt_ready,
        "latest_forge_handoff_receipt_id": latest_forge_handoff_receipt_id,
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_memory": False,
        "captures_screen": False,
        "captures_audio": False,
        "captures_keystrokes": False,
        "passive_learning_enabled": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "requires_stage10_ledger_closure": True,
            "explicit_teaching_session_required": True,
            "teaching_session_receipt_required_before_learning": True,
            "replay_receipt_required_before_skillization": True,
            "skillization_artifact_receipt_required_before_forge_handoff": True,
            "forge_handoff_receipt_required_before_completion_review": True,
            "passive_capture_denied": True,
            "surveillance_like_learning_denied": True,
            "learned_skills_must_be_reviewable": True,
            "forge_handoff_must_be_governed": True,
            "does_not_write_receipts": True,
            "does_not_write_memory": True,
            "does_not_capture_screen": True,
            "does_not_capture_audio": True,
            "does_not_capture_keystrokes": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "routes": {
            "status": "/apprenticeship/status",
            "stage10_closure_readback": "/away/stage-closure-decisions",
            "teaching_session_contract": "/apprenticeship/teaching-session-contract",
            "replay_generalization_contract": "/apprenticeship/replay-generalization-contract",
            "skillization_artifact_contract": "/apprenticeship/skillization-artifact-contract",
            "forge_handoff_contract": "/apprenticeship/forge-handoff-contract",
            "live_teaching_session_ux": "/apprenticeship/live-teaching-session-ux",
            "teaching_session_receipts": "/apprenticeship/teaching-session-receipts",
            "teaching_session_record": "/apprenticeship/teaching-session",
            "replay_receipts": "/apprenticeship/replay-receipts",
            "replay_receipt_record": "/apprenticeship/replay-receipt",
            "skillization_artifact_receipts": "/apprenticeship/skillization-artifact-receipts",
            "skillization_artifact_record": "/apprenticeship/skillization-artifact-receipt",
            "forge_handoff_receipts": "/apprenticeship/forge-handoff-receipts",
            "forge_handoff_record": "/apprenticeship/forge-handoff-receipt",
        },
        "next_smallest_truthful_gap": _apprenticeship_next_gap(
            stage10_closed=stage10_closed,
            teaching_session_ready=teaching_session_ready,
            replay_generalization_ready=replay_generalization_ready,
            skillization_ready=skillization_ready,
            forge_handoff_ready=forge_handoff_ready,
            live_teaching_session_ux_ready=live_teaching_session_ux_ready,
            teaching_session_receipt_ready=teaching_session_receipt_ready,
            replay_receipt_ready=replay_receipt_ready,
            skillization_artifact_receipt_ready=skillization_artifact_receipt_ready,
            forge_handoff_receipt_ready=forge_handoff_receipt_ready,
        ),
    }


def apprenticeship_teaching_session_contract() -> dict[str, Any]:
    stage10 = away_stage10_operator_stage_closure_decision_readback(limit=5)
    stage10_closed = bool(stage10.get("stage10_closed_by_receipt"))
    requirements = [
        {
            "id": "explicit_start_stop",
            "label": "Explicit start and stop",
            "required": True,
            "status": "declared",
        },
        {
            "id": "declared_scope",
            "label": "Declared workflow scope",
            "required": True,
            "status": "declared",
        },
        {
            "id": "intent_label",
            "label": "Intent label",
            "required": True,
            "status": "declared",
        },
        {
            "id": "success_condition",
            "label": "Success condition",
            "required": True,
            "status": "declared",
        },
        {
            "id": "operator_review_before_learning",
            "label": "Operator review before learning",
            "required": True,
            "status": "declared",
        },
    ]
    capture_boundaries = [
        {
            "id": "operator_supplied_steps_only",
            "allowed": True,
            "description": "Use explicit operator-supplied step summaries instead of ambient capture.",
        },
        {
            "id": "screen_capture",
            "allowed": False,
            "description": "Screen capture is not part of the Stage 11 teaching-session contract.",
        },
        {
            "id": "audio_capture",
            "allowed": False,
            "description": "Audio capture is not part of the Stage 11 teaching-session contract.",
        },
        {
            "id": "keystroke_capture",
            "allowed": False,
            "description": "Keystroke capture is not part of the Stage 11 teaching-session contract.",
        },
        {
            "id": "passive_background_learning",
            "allowed": False,
            "description": "Apprenticeship requires explicit teaching context.",
        },
    ]
    checks = _teaching_session_contract_checks(
        stage10_closed=stage10_closed,
        requirements=requirements,
        capture_boundaries=capture_boundaries,
    )
    ready = all(bool(check.get("passed")) for check in checks)
    return {
        "ok": True,
        "kind": APPRENTICESHIP_TEACHING_SESSION_CONTRACT_KIND,
        "stage": STAGE11_APPRENTICESHIP_STAGE,
        "source_id": "apprenticeship",
        "status": "ready" if ready else "blocked",
        "stage10_closed_by_receipt": stage10_closed,
        "stage10_latest_closure_receipt_id": _safe_text(stage10.get("latest_receipt_id")),
        "teaching_session_contract_ready": ready,
        "canonical_pipeline": ["demonstrate", "label_intent", "replay", "generalize", "skillize"],
        "requirements": requirements,
        "requirement_count": len(requirements),
        "capture_boundaries": capture_boundaries,
        "capture_boundary_count": len(capture_boundaries),
        "checks": checks,
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_memory": False,
        "captures_screen": False,
        "captures_audio": False,
        "captures_keystrokes": False,
        "passive_learning_enabled": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "contract_only": True,
            "requires_stage10_ledger_closure": True,
            "explicit_teaching_session_required": True,
            "operator_supplied_steps_only": True,
            "operator_review_before_learning": True,
            "passive_capture_denied": True,
            "surveillance_like_learning_denied": True,
            "does_not_write_receipts": True,
            "does_not_write_memory": True,
            "does_not_capture_screen": True,
            "does_not_capture_audio": True,
            "does_not_capture_keystrokes": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage11_replay_generalization_contract"
        if ready
        else "stage11_teaching_session_contract"
        if stage10_closed
        else "stage10_ledger_closure",
    }


def apprenticeship_replay_generalization_contract() -> dict[str, Any]:
    teaching_session = apprenticeship_teaching_session_contract()
    teaching_ready = bool(teaching_session.get("teaching_session_contract_ready"))
    replay_requirements = [
        {
            "id": "operator_supplied_demonstration_steps",
            "label": "Operator-supplied demonstration steps",
            "required": True,
            "status": "declared",
        },
        {
            "id": "intent_label_readback",
            "label": "Intent label readback",
            "required": True,
            "status": "declared",
        },
        {
            "id": "bounded_replay_plan",
            "label": "Bounded replay plan",
            "required": True,
            "status": "declared",
        },
        {
            "id": "assumption_register",
            "label": "Assumption register",
            "required": True,
            "status": "declared",
        },
        {
            "id": "operator_replay_review",
            "label": "Operator replay review",
            "required": True,
            "status": "declared",
        },
    ]
    generalization_requirements = [
        {
            "id": "variable_inputs",
            "label": "Variable inputs",
            "required": True,
            "status": "declared",
        },
        {
            "id": "stable_steps",
            "label": "Stable steps",
            "required": True,
            "status": "declared",
        },
        {
            "id": "optional_branches",
            "label": "Optional branches",
            "required": True,
            "status": "declared",
        },
        {
            "id": "validation_checkpoints",
            "label": "Validation checkpoints",
            "required": True,
            "status": "declared",
        },
        {
            "id": "failure_handling",
            "label": "Failure handling",
            "required": True,
            "status": "declared",
        },
    ]
    denied_modes = [
        "literal_macro_playback",
        "unreviewed_generalization",
        "background_replay_execution",
        "silent_skill_promotion",
    ]
    checks = _replay_generalization_contract_checks(
        teaching_ready=teaching_ready,
        replay_requirements=replay_requirements,
        generalization_requirements=generalization_requirements,
        denied_modes=denied_modes,
    )
    ready = all(bool(check.get("passed")) for check in checks)
    return {
        "ok": True,
        "kind": APPRENTICESHIP_REPLAY_GENERALIZATION_CONTRACT_KIND,
        "stage": STAGE11_APPRENTICESHIP_STAGE,
        "source_id": "apprenticeship",
        "status": "ready" if ready else "blocked",
        "teaching_session_contract_ready": teaching_ready,
        "replay_generalization_contract_ready": ready,
        "pipeline_position": ["replay", "generalize"],
        "replay_requirements": replay_requirements,
        "replay_requirement_count": len(replay_requirements),
        "generalization_requirements": generalization_requirements,
        "generalization_requirement_count": len(generalization_requirements),
        "denied_modes": denied_modes,
        "checks": checks,
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_memory": False,
        "captures_screen": False,
        "captures_audio": False,
        "captures_keystrokes": False,
        "passive_learning_enabled": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "executes_replay": False,
        "promotes_skill": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "contract_only": True,
            "requires_teaching_session_contract": True,
            "bounded_replay_only": True,
            "operator_replay_review_required": True,
            "generalization_review_required": True,
            "literal_macro_playback_denied": True,
            "background_replay_execution_denied": True,
            "silent_skill_promotion_denied": True,
            "does_not_write_receipts": True,
            "does_not_write_memory": True,
            "does_not_capture_screen": True,
            "does_not_capture_audio": True,
            "does_not_capture_keystrokes": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage11_skillization_artifact_contract"
        if ready
        else "stage11_replay_generalization_contract",
    }


def apprenticeship_skillization_artifact_contract() -> dict[str, Any]:
    replay_generalization = apprenticeship_replay_generalization_contract()
    replay_ready = bool(replay_generalization.get("replay_generalization_contract_ready"))
    artifact_schema = [
        {
            "id": "pattern_summary",
            "label": "Pattern summary",
            "required": True,
            "status": "declared",
        },
        {
            "id": "parameterization",
            "label": "Parameterization",
            "required": True,
            "status": "declared",
        },
        {
            "id": "usage_scope",
            "label": "Usage scope",
            "required": True,
            "status": "declared",
        },
        {
            "id": "decision_logic",
            "label": "Decision logic",
            "required": True,
            "status": "declared",
        },
        {
            "id": "validation_expectations",
            "label": "Validation expectations",
            "required": True,
            "status": "declared",
        },
        {
            "id": "risk_tier_candidate",
            "label": "Risk-tier candidate",
            "required": True,
            "status": "declared",
        },
        {
            "id": "documentation_draft",
            "label": "Documentation draft",
            "required": True,
            "status": "declared",
        },
        {
            "id": "test_candidate_structure",
            "label": "Test candidate structure",
            "required": True,
            "status": "declared",
        },
    ]
    classification_options = [
        "preference_adaptation",
        "workflow_understanding",
        "candidate_reusable_skill",
        "forge_worthy_promoted_capability",
    ]
    denied_modes = [
        "automatic_promotion",
        "silent_authority_growth",
        "unreviewed_capability_creation",
        "memory_write_without_operator_review",
    ]
    checks = _skillization_artifact_contract_checks(
        replay_ready=replay_ready,
        artifact_schema=artifact_schema,
        classification_options=classification_options,
        denied_modes=denied_modes,
    )
    ready = all(bool(check.get("passed")) for check in checks)
    return {
        "ok": True,
        "kind": APPRENTICESHIP_SKILLIZATION_ARTIFACT_CONTRACT_KIND,
        "stage": STAGE11_APPRENTICESHIP_STAGE,
        "source_id": "apprenticeship",
        "status": "ready" if ready else "blocked",
        "replay_generalization_contract_ready": replay_ready,
        "skillization_artifact_contract_ready": ready,
        "pipeline_position": ["skillize"],
        "artifact_schema": artifact_schema,
        "artifact_field_count": len(artifact_schema),
        "classification_options": classification_options,
        "classification_option_count": len(classification_options),
        "denied_modes": denied_modes,
        "checks": checks,
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_memory": False,
        "writes_skill_artifact": False,
        "captures_screen": False,
        "captures_audio": False,
        "captures_keystrokes": False,
        "passive_learning_enabled": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "creates_capability": False,
        "promotes_to_forge": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "contract_only": True,
            "requires_replay_generalization_contract": True,
            "operator_review_required_before_artifact_write": True,
            "forge_promotion_requires_governed_handoff": True,
            "automatic_promotion_denied": True,
            "silent_authority_growth_denied": True,
            "unreviewed_capability_creation_denied": True,
            "does_not_write_receipts": True,
            "does_not_write_memory": True,
            "does_not_write_skill_artifact": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage11_forge_handoff_contract"
        if ready
        else "stage11_skillization_artifact_contract",
    }


def apprenticeship_forge_handoff_contract() -> dict[str, Any]:
    skillization = apprenticeship_skillization_artifact_contract()
    skillization_ready = bool(skillization.get("skillization_artifact_contract_ready"))
    handoff_payload_schema = [
        {
            "id": "pattern_summary",
            "label": "Pattern summary",
            "required": True,
            "status": "declared",
        },
        {
            "id": "parameterization",
            "label": "Parameterization",
            "required": True,
            "status": "declared",
        },
        {
            "id": "usage_scope",
            "label": "Usage scope",
            "required": True,
            "status": "declared",
        },
        {
            "id": "decision_logic",
            "label": "Decision logic",
            "required": True,
            "status": "declared",
        },
        {
            "id": "validation_expectations",
            "label": "Validation expectations",
            "required": True,
            "status": "declared",
        },
        {
            "id": "risk_tier_candidate",
            "label": "Risk-tier candidate",
            "required": True,
            "status": "declared",
        },
        {
            "id": "documentation_draft",
            "label": "Documentation draft",
            "required": True,
            "status": "declared",
        },
        {
            "id": "test_candidate_structure",
            "label": "Test candidate structure",
            "required": True,
            "status": "declared",
        },
        {
            "id": "operator_review_state",
            "label": "Operator review state",
            "required": True,
            "status": "declared",
        },
        {
            "id": "promotion_boundary",
            "label": "Promotion boundary",
            "required": True,
            "status": "declared",
        },
    ]
    required_reviews = [
        "operator_review",
        "risk_tier_review",
        "documentation_review",
        "test_candidate_review",
        "explicit_promotion_decision",
    ]
    denied_modes = [
        "direct_forge_promotion",
        "proposal_write_without_operator_review",
        "automatic_capability_registration",
        "authority_grant_from_teaching",
    ]
    checks = _forge_handoff_contract_checks(
        skillization_ready=skillization_ready,
        handoff_payload_schema=handoff_payload_schema,
        required_reviews=required_reviews,
        denied_modes=denied_modes,
    )
    ready = all(bool(check.get("passed")) for check in checks)
    return {
        "ok": True,
        "kind": APPRENTICESHIP_FORGE_HANDOFF_CONTRACT_KIND,
        "stage": STAGE11_APPRENTICESHIP_STAGE,
        "source_id": "apprenticeship",
        "status": "ready" if ready else "blocked",
        "skillization_artifact_contract_ready": skillization_ready,
        "forge_handoff_contract_ready": ready,
        "handoff_target": "forge_proposal_candidate",
        "handoff_payload_schema": handoff_payload_schema,
        "handoff_payload_field_count": len(handoff_payload_schema),
        "required_reviews": required_reviews,
        "required_review_count": len(required_reviews),
        "denied_modes": denied_modes,
        "checks": checks,
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_memory": False,
        "writes_forge_proposal": False,
        "creates_capability": False,
        "promotes_to_forge": False,
        "registers_capability": False,
        "captures_screen": False,
        "captures_audio": False,
        "captures_keystrokes": False,
        "passive_learning_enabled": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "contract_only": True,
            "requires_skillization_artifact_contract": True,
            "operator_review_required_before_forge_write": True,
            "explicit_promotion_decision_required": True,
            "direct_forge_promotion_denied": True,
            "automatic_capability_registration_denied": True,
            "authority_grant_from_teaching_denied": True,
            "does_not_write_receipts": True,
            "does_not_write_memory": True,
            "does_not_write_forge_proposal": True,
            "does_not_create_capability": True,
            "does_not_promote_to_forge": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage11_live_teaching_session_ux" if ready else "stage11_forge_handoff_contract",
    }


def apprenticeship_live_teaching_session_ux() -> dict[str, Any]:
    forge_handoff = apprenticeship_forge_handoff_contract()
    forge_handoff_ready = bool(forge_handoff.get("forge_handoff_contract_ready"))
    visible_sections = [
        {
            "id": "stage_status",
            "label": "Stage status",
            "source_route": "/apprenticeship/status",
            "visible": True,
            "status": "declared",
        },
        {
            "id": "teaching_contract",
            "label": "Teaching contract",
            "source_route": "/apprenticeship/teaching-session-contract",
            "visible": True,
            "status": "declared",
        },
        {
            "id": "replay_generalization",
            "label": "Replay and generalization",
            "source_route": "/apprenticeship/replay-generalization-contract",
            "visible": True,
            "status": "declared",
        },
        {
            "id": "skillization_artifact",
            "label": "Skillization artifact",
            "source_route": "/apprenticeship/skillization-artifact-contract",
            "visible": True,
            "status": "declared",
        },
        {
            "id": "forge_handoff",
            "label": "Forge handoff",
            "source_route": "/apprenticeship/forge-handoff-contract",
            "visible": True,
            "status": "declared",
        },
        {
            "id": "capture_boundaries",
            "label": "Capture boundaries",
            "source_route": "/apprenticeship/teaching-session-contract",
            "visible": True,
            "status": "declared",
        },
        {
            "id": "next_gap",
            "label": "Next gap",
            "source_route": "/apprenticeship/status",
            "visible": True,
            "status": "declared",
        },
    ]
    operator_actions = [
        {
            "id": "start_teaching_session",
            "label": "Start teaching session",
            "enabled": False,
            "status": "requires_receipt_write_path",
        },
        {
            "id": "label_intent",
            "label": "Label intent",
            "enabled": False,
            "status": "requires_teaching_session_receipt",
        },
        {
            "id": "review_replay",
            "label": "Review replay",
            "enabled": False,
            "status": "requires_replay_receipt",
        },
        {
            "id": "prepare_skillization_artifact",
            "label": "Prepare skillization artifact",
            "enabled": False,
            "status": "requires_operator_reviewed_learning_record",
        },
        {
            "id": "stage_forge_handoff",
            "label": "Stage Forge handoff",
            "enabled": False,
            "status": "requires_explicit_promotion_decision",
        },
    ]
    denied_modes = [
        "ambient_capture_start",
        "background_learning_toggle",
        "teaching_session_without_receipt",
        "forge_promotion_from_ui_surface",
    ]
    checks = _live_teaching_session_ux_checks(
        forge_handoff_ready=forge_handoff_ready,
        visible_sections=visible_sections,
        operator_actions=operator_actions,
        denied_modes=denied_modes,
    )
    ready = all(bool(check.get("passed")) for check in checks)
    return {
        "ok": True,
        "kind": APPRENTICESHIP_LIVE_TEACHING_SESSION_UX_KIND,
        "stage": STAGE11_APPRENTICESHIP_STAGE,
        "source_id": "apprenticeship",
        "status": "ready" if ready else "blocked",
        "forge_handoff_contract_ready": forge_handoff_ready,
        "live_teaching_session_ux_ready": ready,
        "surface": "chat_ui.apprenticeship_panel",
        "route": "/apprenticeship/live-teaching-session-ux",
        "visible_sections": visible_sections,
        "visible_section_count": len(visible_sections),
        "operator_actions": operator_actions,
        "operator_action_count": len(operator_actions),
        "denied_modes": denied_modes,
        "checks": checks,
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_memory": False,
        "writes_skill_artifact": False,
        "writes_forge_proposal": False,
        "creates_capability": False,
        "promotes_to_forge": False,
        "starts_teaching_session": False,
        "captures_screen": False,
        "captures_audio": False,
        "captures_keystrokes": False,
        "passive_learning_enabled": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "operator_surface_only": True,
            "requires_forge_handoff_contract": True,
            "requires_receipt_write_path_before_actions_enable": True,
            "ambient_capture_start_denied": True,
            "background_learning_toggle_denied": True,
            "forge_promotion_from_ui_surface_denied": True,
            "does_not_start_teaching_session": True,
            "does_not_write_receipts": True,
            "does_not_write_memory": True,
            "does_not_write_skill_artifact": True,
            "does_not_write_forge_proposal": True,
            "does_not_create_capability": True,
            "does_not_promote_to_forge": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage11_teaching_session_receipt_write_path"
        if ready
        else "stage11_live_teaching_session_ux",
    }


def read_apprenticeship_teaching_session_receipts(*, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl_tail(_teaching_session_receipt_path(), limit=_safe_limit(limit, default=20))


def apprenticeship_teaching_session_receipts(*, limit: int = 20) -> dict[str, Any]:
    items = read_apprenticeship_teaching_session_receipts(limit=limit)
    latest_receipt_id = _safe_text(items[-1].get("receipt_id")) if items else ""
    return {
        "ok": True,
        "kind": APPRENTICESHIP_TEACHING_SESSION_RECEIPTS_KIND,
        "stage": STAGE11_APPRENTICESHIP_STAGE,
        "source_id": "apprenticeship",
        "status": "ready" if latest_receipt_id else "empty",
        "items": items,
        "count": len(items),
        "latest_receipt_id": latest_receipt_id,
        "teaching_session_receipt_ready": bool(latest_receipt_id),
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_memory": False,
        "writes_skill_artifact": False,
        "writes_forge_proposal": False,
        "starts_teaching_session": False,
        "captures_screen": False,
        "captures_audio": False,
        "captures_keystrokes": False,
        "passive_learning_enabled": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "receipt_readback_only": True,
            "explicit_teaching_session_receipts_only": True,
            "does_not_write_memory": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage11_replay_receipt_write_path"
        if latest_receipt_id
        else "stage11_teaching_session_receipt_write_path",
    }


def read_apprenticeship_replay_receipts(*, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl_tail(_replay_receipt_path(), limit=_safe_limit(limit, default=20))


def apprenticeship_replay_receipts(*, limit: int = 20) -> dict[str, Any]:
    items = read_apprenticeship_replay_receipts(limit=limit)
    latest_receipt_id = _safe_text(items[-1].get("receipt_id")) if items else ""
    return {
        "ok": True,
        "kind": APPRENTICESHIP_REPLAY_RECEIPTS_KIND,
        "stage": STAGE11_APPRENTICESHIP_STAGE,
        "source_id": "apprenticeship",
        "status": "ready" if latest_receipt_id else "empty",
        "items": items,
        "count": len(items),
        "latest_receipt_id": latest_receipt_id,
        "replay_receipt_ready": bool(latest_receipt_id),
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_memory": False,
        "writes_skill_artifact": False,
        "writes_forge_proposal": False,
        "executes_replay": False,
        "promotes_skill": False,
        "starts_teaching_session": False,
        "captures_screen": False,
        "captures_audio": False,
        "captures_keystrokes": False,
        "passive_learning_enabled": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "receipt_readback_only": True,
            "operator_reviewed_replay_receipts_only": True,
            "does_not_execute_replay": True,
            "does_not_write_memory": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage11_skillization_artifact_receipt_write_path"
        if latest_receipt_id
        else "stage11_replay_receipt_write_path",
    }


def read_apprenticeship_skillization_artifact_receipts(*, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl_tail(_skillization_artifact_receipt_path(), limit=_safe_limit(limit, default=20))


def apprenticeship_skillization_artifact_receipts(*, limit: int = 20) -> dict[str, Any]:
    items = read_apprenticeship_skillization_artifact_receipts(limit=limit)
    latest_receipt_id = _safe_text(items[-1].get("receipt_id")) if items else ""
    return {
        "ok": True,
        "kind": APPRENTICESHIP_SKILLIZATION_ARTIFACT_RECEIPTS_KIND,
        "stage": STAGE11_APPRENTICESHIP_STAGE,
        "source_id": "apprenticeship",
        "status": "ready" if latest_receipt_id else "empty",
        "items": items,
        "count": len(items),
        "latest_receipt_id": latest_receipt_id,
        "skillization_artifact_receipt_ready": bool(latest_receipt_id),
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_memory": False,
        "writes_skill_artifact": False,
        "writes_forge_proposal": False,
        "creates_capability": False,
        "promotes_to_forge": False,
        "registers_capability": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "receipt_readback_only": True,
            "operator_reviewed_skillization_artifacts_only": True,
            "does_not_write_memory": True,
            "does_not_write_skill_artifact": True,
            "does_not_write_forge_proposal": True,
            "does_not_create_capability": True,
            "does_not_promote_to_forge": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage11_forge_handoff_receipt_write_path"
        if latest_receipt_id
        else "stage11_skillization_artifact_receipt_write_path",
    }


def read_apprenticeship_forge_handoff_receipts(*, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl_tail(_forge_handoff_receipt_path(), limit=_safe_limit(limit, default=20))


def apprenticeship_forge_handoff_receipts(*, limit: int = 20) -> dict[str, Any]:
    items = read_apprenticeship_forge_handoff_receipts(limit=limit)
    latest_receipt_id = _safe_text(items[-1].get("receipt_id")) if items else ""
    return {
        "ok": True,
        "kind": APPRENTICESHIP_FORGE_HANDOFF_RECEIPTS_KIND,
        "stage": STAGE11_APPRENTICESHIP_STAGE,
        "source_id": "apprenticeship",
        "status": "ready" if latest_receipt_id else "empty",
        "items": items,
        "count": len(items),
        "latest_receipt_id": latest_receipt_id,
        "forge_handoff_receipt_ready": bool(latest_receipt_id),
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_memory": False,
        "writes_forge_proposal": False,
        "creates_capability": False,
        "promotes_to_forge": False,
        "registers_capability": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "receipt_readback_only": True,
            "operator_reviewed_forge_handoff_receipts_only": True,
            "does_not_write_memory": True,
            "does_not_write_forge_proposal": True,
            "does_not_create_capability": True,
            "does_not_promote_to_forge": True,
            "does_not_register_capability": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage11_completion_review"
        if latest_receipt_id
        else "stage11_forge_handoff_receipt_write_path",
    }


def record_apprenticeship_teaching_session(
    *,
    actor: Any,
    reason: Any,
    action: Any = "start_teaching_session",
    intent_label: Any = "",
    declared_scope: Any = "",
    success_condition: Any = "",
    demonstration_summary: Any = "",
    notes: Any = "",
) -> dict[str, Any]:
    env_profile = _env_profile()
    if env_profile not in _ALLOWED_ENV_PROFILES:
        return _blocked_no_receipt(
            status="blocked_environment_profile",
            reason="apprenticeship_teaching_session_dev_or_workstation_only",
            required_scope=APPRENTICESHIP_TEACHING_SESSION_WRITE_SCOPE,
            next_gap="stage11_teaching_session_receipt_write_path",
        )

    ux = apprenticeship_live_teaching_session_ux()
    if not bool(ux.get("live_teaching_session_ux_ready")):
        return _blocked_no_receipt(
            status="awaiting_live_teaching_session_ux",
            reason="live_teaching_session_ux_required_before_teaching_session_receipt",
            required_scope=APPRENTICESHIP_TEACHING_SESSION_WRITE_SCOPE,
            next_gap=_safe_text(ux.get("next_smallest_truthful_gap")) or "stage11_live_teaching_session_ux",
        )

    stage10 = away_stage10_operator_stage_closure_decision_readback(limit=5)
    safe_action = _safe_teaching_session_action(action)
    safe_actor = _redacted_text(actor)[:240]
    safe_reason = _redacted_text(reason)[:500]
    receipt_id = f"apprenticeship_teaching_session_{uuid.uuid4().hex[:12]}"
    receipt = {
        "ok": True,
        "kind": APPRENTICESHIP_TEACHING_SESSION_RECEIPT_KIND,
        "receipt_id": receipt_id,
        "stage": STAGE11_APPRENTICESHIP_STAGE,
        "source_id": "apprenticeship",
        "target": "stage11_teaching_session",
        "actor": safe_actor,
        "reason": safe_reason,
        "action": safe_action,
        "intent_label": _redacted_text(intent_label)[:240],
        "declared_scope": _redacted_text(declared_scope)[:500],
        "success_condition": _redacted_text(success_condition)[:500],
        "demonstration_summary": _redacted_text(demonstration_summary)[:1000],
        "notes": _redacted_text(notes)[:500],
        "env_profile": env_profile,
        "recorded_ts": _now_s(),
        "live_teaching_session_ux_ready": True,
        "stage10_closed_by_receipt": bool(stage10.get("stage10_closed_by_receipt")),
        "stage10_latest_closure_receipt_id": _safe_text(stage10.get("latest_receipt_id")),
        "capture_mode": "explicit_operator_teaching_session_receipt",
        "teaching_session_receipt_ready": True,
        "writes_receipt": True,
        "writes_memory": False,
        "writes_skill_artifact": False,
        "writes_forge_proposal": False,
        "creates_capability": False,
        "promotes_to_forge": False,
        "starts_teaching_session": safe_action == "start_teaching_session",
        "captures_screen": False,
        "captures_audio": False,
        "captures_keystrokes": False,
        "passive_learning_enabled": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "required_scope": APPRENTICESHIP_TEACHING_SESSION_WRITE_SCOPE,
            "dev_or_workstation_only": True,
            "action_allowlisted": safe_action in _ALLOWED_TEACHING_SESSION_ACTIONS,
            "explicit_operator_teaching_session": True,
            "operator_supplied_steps_only": True,
            "ambient_capture_denied": True,
            "passive_learning_denied": True,
            "does_not_write_memory": True,
            "does_not_write_skill_artifact": True,
            "does_not_write_forge_proposal": True,
            "does_not_create_capability": True,
            "does_not_promote_to_forge": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage11_replay_receipt_write_path",
    }
    _append_jsonl(_teaching_session_receipt_path(), receipt)
    audit_record(
        "apprenticeship.teaching_session_recorded",
        actor=safe_actor,
        reason=safe_reason,
        receipt_id=receipt_id,
        action=safe_action,
    )
    return receipt


def record_apprenticeship_replay_receipt(
    *,
    actor: Any,
    reason: Any,
    action: Any = "review_replay",
    teaching_session_receipt_id: Any = "",
    intent_label: Any = "",
    replay_summary: Any = "",
    generalization_summary: Any = "",
    assumptions: Any = "",
    validation_result: Any = "",
    notes: Any = "",
) -> dict[str, Any]:
    env_profile = _env_profile()
    if env_profile not in _ALLOWED_ENV_PROFILES:
        return _blocked_no_receipt(
            status="blocked_environment_profile",
            reason="apprenticeship_replay_receipt_dev_or_workstation_only",
            required_scope=APPRENTICESHIP_REPLAY_RECEIPT_WRITE_SCOPE,
            next_gap="stage11_replay_receipt_write_path",
        )

    status = apprenticeship_status_snapshot()
    if not bool(status.get("teaching_session_receipt_ready")):
        return _blocked_no_receipt(
            status="awaiting_teaching_session_receipt",
            reason="teaching_session_receipt_required_before_replay_receipt",
            required_scope=APPRENTICESHIP_REPLAY_RECEIPT_WRITE_SCOPE,
            next_gap="stage11_teaching_session_receipt_write_path",
        )

    latest_teaching_session_receipt_id = _safe_text(status.get("latest_teaching_session_receipt_id"))
    supplied_teaching_session_receipt_id = _safe_text(teaching_session_receipt_id)
    linked_teaching_session_receipt_id = supplied_teaching_session_receipt_id or latest_teaching_session_receipt_id
    safe_action = _safe_replay_receipt_action(action)
    safe_actor = _redacted_text(actor)[:240]
    safe_reason = _redacted_text(reason)[:500]
    receipt_id = f"apprenticeship_replay_{uuid.uuid4().hex[:12]}"
    receipt = {
        "ok": True,
        "kind": APPRENTICESHIP_REPLAY_RECEIPT_KIND,
        "receipt_id": receipt_id,
        "stage": STAGE11_APPRENTICESHIP_STAGE,
        "source_id": "apprenticeship",
        "target": "stage11_replay_generalization",
        "actor": safe_actor,
        "reason": safe_reason,
        "action": safe_action,
        "teaching_session_receipt_id": linked_teaching_session_receipt_id,
        "latest_teaching_session_receipt_id": latest_teaching_session_receipt_id,
        "intent_label": _redacted_text(intent_label)[:240],
        "replay_summary": _redacted_text(replay_summary)[:1000],
        "generalization_summary": _redacted_text(generalization_summary)[:1000],
        "assumptions": _redacted_text(assumptions)[:800],
        "validation_result": _redacted_text(validation_result)[:500],
        "notes": _redacted_text(notes)[:500],
        "env_profile": env_profile,
        "recorded_ts": _now_s(),
        "capture_mode": "explicit_operator_replay_review_receipt",
        "replay_receipt_ready": True,
        "writes_receipt": True,
        "writes_memory": False,
        "writes_skill_artifact": False,
        "writes_forge_proposal": False,
        "creates_capability": False,
        "promotes_to_forge": False,
        "starts_teaching_session": False,
        "executes_replay": False,
        "promotes_skill": False,
        "captures_screen": False,
        "captures_audio": False,
        "captures_keystrokes": False,
        "passive_learning_enabled": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "required_scope": APPRENTICESHIP_REPLAY_RECEIPT_WRITE_SCOPE,
            "dev_or_workstation_only": True,
            "action_allowlisted": safe_action in _ALLOWED_REPLAY_RECEIPT_ACTIONS,
            "requires_teaching_session_receipt": True,
            "explicit_operator_replay_review": True,
            "bounded_replay_only": True,
            "literal_macro_playback_denied": True,
            "background_replay_execution_denied": True,
            "unreviewed_generalization_denied": True,
            "does_not_execute_replay": True,
            "does_not_write_memory": True,
            "does_not_write_skill_artifact": True,
            "does_not_write_forge_proposal": True,
            "does_not_create_capability": True,
            "does_not_promote_to_forge": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage11_skillization_artifact_receipt_write_path",
    }
    _append_jsonl(_replay_receipt_path(), receipt)
    audit_record(
        "apprenticeship.replay_receipt_recorded",
        actor=safe_actor,
        reason=safe_reason,
        receipt_id=receipt_id,
        action=safe_action,
        teaching_session_receipt_id=linked_teaching_session_receipt_id,
    )
    return receipt


def record_apprenticeship_skillization_artifact_receipt(
    *,
    actor: Any,
    reason: Any,
    action: Any = "prepare_skillization_artifact",
    replay_receipt_id: Any = "",
    pattern_summary: Any = "",
    parameterization: Any = "",
    usage_scope: Any = "",
    decision_logic: Any = "",
    validation_expectations: Any = "",
    risk_tier_candidate: Any = "",
    documentation_draft: Any = "",
    test_candidate_structure: Any = "",
    classification: Any = "",
    notes: Any = "",
) -> dict[str, Any]:
    env_profile = _env_profile()
    if env_profile not in _ALLOWED_ENV_PROFILES:
        return _blocked_no_receipt(
            status="blocked_environment_profile",
            reason="apprenticeship_skillization_artifact_dev_or_workstation_only",
            required_scope=APPRENTICESHIP_SKILLIZATION_ARTIFACT_WRITE_SCOPE,
            next_gap="stage11_skillization_artifact_receipt_write_path",
        )

    status = apprenticeship_status_snapshot()
    if not bool(status.get("replay_receipt_ready")):
        return _blocked_no_receipt(
            status="awaiting_replay_receipt",
            reason="replay_receipt_required_before_skillization_artifact_receipt",
            required_scope=APPRENTICESHIP_SKILLIZATION_ARTIFACT_WRITE_SCOPE,
            next_gap="stage11_replay_receipt_write_path",
        )

    latest_replay_receipt_id = _safe_text(status.get("latest_replay_receipt_id"))
    supplied_replay_receipt_id = _safe_text(replay_receipt_id)
    linked_replay_receipt_id = supplied_replay_receipt_id or latest_replay_receipt_id
    safe_action = _safe_skillization_artifact_action(action)
    safe_actor = _redacted_text(actor)[:240]
    safe_reason = _redacted_text(reason)[:500]
    receipt_id = f"apprenticeship_skillization_{uuid.uuid4().hex[:12]}"
    receipt = {
        "ok": True,
        "kind": APPRENTICESHIP_SKILLIZATION_ARTIFACT_RECEIPT_KIND,
        "receipt_id": receipt_id,
        "stage": STAGE11_APPRENTICESHIP_STAGE,
        "source_id": "apprenticeship",
        "target": "stage11_skillization_artifact",
        "actor": safe_actor,
        "reason": safe_reason,
        "action": safe_action,
        "replay_receipt_id": linked_replay_receipt_id,
        "latest_replay_receipt_id": latest_replay_receipt_id,
        "pattern_summary": _redacted_text(pattern_summary)[:1000],
        "parameterization": _redacted_text(parameterization)[:1000],
        "usage_scope": _redacted_text(usage_scope)[:800],
        "decision_logic": _redacted_text(decision_logic)[:1000],
        "validation_expectations": _redacted_text(validation_expectations)[:800],
        "risk_tier_candidate": _redacted_text(risk_tier_candidate)[:160],
        "documentation_draft": _redacted_text(documentation_draft)[:1200],
        "test_candidate_structure": _redacted_text(test_candidate_structure)[:1000],
        "classification": _redacted_text(classification)[:240],
        "notes": _redacted_text(notes)[:500],
        "env_profile": env_profile,
        "recorded_ts": _now_s(),
        "capture_mode": "explicit_operator_skillization_artifact_receipt",
        "skillization_artifact_receipt_ready": True,
        "writes_receipt": True,
        "writes_memory": False,
        "writes_skill_artifact": False,
        "writes_forge_proposal": False,
        "creates_capability": False,
        "promotes_to_forge": False,
        "registers_capability": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "required_scope": APPRENTICESHIP_SKILLIZATION_ARTIFACT_WRITE_SCOPE,
            "dev_or_workstation_only": True,
            "action_allowlisted": safe_action in _ALLOWED_SKILLIZATION_ARTIFACT_ACTIONS,
            "requires_replay_receipt": True,
            "explicit_operator_skillization_artifact_review": True,
            "operator_review_required_before_artifact_write": True,
            "forge_promotion_requires_governed_handoff": True,
            "automatic_promotion_denied": True,
            "silent_authority_growth_denied": True,
            "unreviewed_capability_creation_denied": True,
            "does_not_write_memory": True,
            "does_not_write_skill_artifact": True,
            "does_not_write_forge_proposal": True,
            "does_not_create_capability": True,
            "does_not_promote_to_forge": True,
            "does_not_register_capability": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage11_forge_handoff_receipt_write_path",
    }
    _append_jsonl(_skillization_artifact_receipt_path(), receipt)
    audit_record(
        "apprenticeship.skillization_artifact_receipt_recorded",
        actor=safe_actor,
        reason=safe_reason,
        receipt_id=receipt_id,
        action=safe_action,
        replay_receipt_id=linked_replay_receipt_id,
    )
    return receipt


def record_apprenticeship_forge_handoff_receipt(
    *,
    actor: Any,
    reason: Any,
    action: Any = "review_forge_handoff",
    skillization_artifact_receipt_id: Any = "",
    handoff_summary: Any = "",
    operator_review_state: Any = "",
    risk_tier_review: Any = "",
    documentation_review: Any = "",
    test_candidate_review: Any = "",
    promotion_boundary: Any = "",
    explicit_promotion_decision: Any = "",
    notes: Any = "",
) -> dict[str, Any]:
    env_profile = _env_profile()
    if env_profile not in _ALLOWED_ENV_PROFILES:
        return _blocked_no_receipt(
            status="blocked_environment_profile",
            reason="apprenticeship_forge_handoff_dev_or_workstation_only",
            required_scope=APPRENTICESHIP_FORGE_HANDOFF_WRITE_SCOPE,
            next_gap="stage11_forge_handoff_receipt_write_path",
        )

    status = apprenticeship_status_snapshot()
    if not bool(status.get("skillization_artifact_receipt_ready")):
        return _blocked_no_receipt(
            status="awaiting_skillization_artifact_receipt",
            reason="skillization_artifact_receipt_required_before_forge_handoff_receipt",
            required_scope=APPRENTICESHIP_FORGE_HANDOFF_WRITE_SCOPE,
            next_gap="stage11_skillization_artifact_receipt_write_path",
        )

    latest_skillization_artifact_receipt_id = _safe_text(status.get("latest_skillization_artifact_receipt_id"))
    supplied_skillization_artifact_receipt_id = _safe_text(skillization_artifact_receipt_id)
    linked_skillization_artifact_receipt_id = (
        supplied_skillization_artifact_receipt_id or latest_skillization_artifact_receipt_id
    )
    safe_action = _safe_forge_handoff_action(action)
    safe_actor = _redacted_text(actor)[:240]
    safe_reason = _redacted_text(reason)[:500]
    receipt_id = f"apprenticeship_forge_handoff_{uuid.uuid4().hex[:12]}"
    receipt = {
        "ok": True,
        "kind": APPRENTICESHIP_FORGE_HANDOFF_RECEIPT_KIND,
        "receipt_id": receipt_id,
        "stage": STAGE11_APPRENTICESHIP_STAGE,
        "source_id": "apprenticeship",
        "target": "stage11_forge_handoff",
        "actor": safe_actor,
        "reason": safe_reason,
        "action": safe_action,
        "skillization_artifact_receipt_id": linked_skillization_artifact_receipt_id,
        "latest_skillization_artifact_receipt_id": latest_skillization_artifact_receipt_id,
        "handoff_summary": _redacted_text(handoff_summary)[:1000],
        "operator_review_state": _redacted_text(operator_review_state)[:500],
        "risk_tier_review": _redacted_text(risk_tier_review)[:500],
        "documentation_review": _redacted_text(documentation_review)[:500],
        "test_candidate_review": _redacted_text(test_candidate_review)[:500],
        "promotion_boundary": _redacted_text(promotion_boundary)[:500],
        "explicit_promotion_decision": _redacted_text(explicit_promotion_decision)[:240],
        "notes": _redacted_text(notes)[:500],
        "env_profile": env_profile,
        "recorded_ts": _now_s(),
        "capture_mode": "explicit_operator_forge_handoff_receipt",
        "forge_handoff_receipt_ready": True,
        "writes_receipt": True,
        "writes_memory": False,
        "writes_forge_proposal": False,
        "creates_capability": False,
        "promotes_to_forge": False,
        "registers_capability": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "required_scope": APPRENTICESHIP_FORGE_HANDOFF_WRITE_SCOPE,
            "dev_or_workstation_only": True,
            "action_allowlisted": safe_action in _ALLOWED_FORGE_HANDOFF_ACTIONS,
            "requires_skillization_artifact_receipt": True,
            "explicit_operator_forge_handoff_review": True,
            "operator_review_required_before_forge_write": True,
            "explicit_promotion_decision_required": True,
            "direct_forge_promotion_denied": True,
            "automatic_capability_registration_denied": True,
            "authority_grant_from_teaching_denied": True,
            "does_not_write_memory": True,
            "does_not_write_forge_proposal": True,
            "does_not_create_capability": True,
            "does_not_promote_to_forge": True,
            "does_not_register_capability": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage11_completion_review",
    }
    _append_jsonl(_forge_handoff_receipt_path(), receipt)
    audit_record(
        "apprenticeship.forge_handoff_receipt_recorded",
        actor=safe_actor,
        reason=safe_reason,
        receipt_id=receipt_id,
        action=safe_action,
        skillization_artifact_receipt_id=linked_skillization_artifact_receipt_id,
    )
    return receipt


def _apprenticeship_deliverables(
    *,
    stage10_closed: bool,
    teaching_session_ready: bool,
    replay_generalization_ready: bool,
    skillization_ready: bool,
    forge_handoff_ready: bool,
) -> list[dict[str, Any]]:
    return [
        {
            "id": "stage10_ledger_closure_backstop",
            "label": "Stage 10 ledger closure backstop",
            "ready": stage10_closed,
            "evidence": "/away/stage-closure-decisions",
        },
        {
            "id": "teaching_session_ux",
            "label": "Teaching session UX",
            "ready": teaching_session_ready,
            "evidence": "/apprenticeship/teaching-session-contract",
        },
        {
            "id": "replay_generalization_flow",
            "label": "Replay and generalization flow",
            "ready": replay_generalization_ready,
            "evidence": "/apprenticeship/replay-generalization-contract",
        },
        {
            "id": "skillization_artifacts",
            "label": "Skillization artifacts",
            "ready": skillization_ready,
            "evidence": "/apprenticeship/skillization-artifact-contract",
        },
        {
            "id": "forge_ready_outputs",
            "label": "Forge-ready outputs from demonstration",
            "ready": forge_handoff_ready,
            "evidence": "/apprenticeship/forge-handoff-contract",
        },
    ]


def _apprenticeship_next_gap(
    *,
    stage10_closed: bool,
    teaching_session_ready: bool,
    replay_generalization_ready: bool,
    skillization_ready: bool,
    forge_handoff_ready: bool,
    live_teaching_session_ux_ready: bool,
    teaching_session_receipt_ready: bool,
    replay_receipt_ready: bool,
    skillization_artifact_receipt_ready: bool,
    forge_handoff_receipt_ready: bool,
) -> str:
    if not stage10_closed:
        return "stage10_ledger_closure"
    if not teaching_session_ready:
        return "stage11_teaching_session_contract"
    if not replay_generalization_ready:
        return "stage11_replay_generalization_contract"
    if not skillization_ready:
        return "stage11_skillization_artifact_contract"
    if not forge_handoff_ready:
        return "stage11_forge_handoff_contract"
    if not live_teaching_session_ux_ready:
        return "stage11_live_teaching_session_ux"
    if not teaching_session_receipt_ready:
        return "stage11_teaching_session_receipt_write_path"
    if not replay_receipt_ready:
        return "stage11_replay_receipt_write_path"
    if not skillization_artifact_receipt_ready:
        return "stage11_skillization_artifact_receipt_write_path"
    if not forge_handoff_receipt_ready:
        return "stage11_forge_handoff_receipt_write_path"
    return "stage11_completion_review"


def _live_teaching_session_ux_checks(
    *,
    forge_handoff_ready: bool,
    visible_sections: list[dict[str, Any]],
    operator_actions: list[dict[str, Any]],
    denied_modes: list[str],
) -> list[dict[str, Any]]:
    section_ids = {_safe_text(item.get("id")) for item in visible_sections if bool(item.get("visible"))}
    action_ids = {_safe_text(item.get("id")) for item in operator_actions}
    actions_disabled = all(not bool(item.get("enabled")) for item in operator_actions)
    denied = {_safe_text(item) for item in denied_modes}
    return [
        _check(
            "forge_handoff_contract_ready",
            passed=forge_handoff_ready,
            evidence="/apprenticeship/forge-handoff-contract",
        ),
        _check(
            "apprenticeship_sections_visible",
            passed={
                "stage_status",
                "teaching_contract",
                "replay_generalization",
                "skillization_artifact",
                "forge_handoff",
                "capture_boundaries",
                "next_gap",
            }.issubset(section_ids),
            evidence=str(len(visible_sections)),
        ),
        _check(
            "operator_actions_declared_but_disabled",
            passed={
                "start_teaching_session",
                "label_intent",
                "review_replay",
                "prepare_skillization_artifact",
                "stage_forge_handoff",
            }.issubset(action_ids)
            and actions_disabled,
            evidence=str(len(operator_actions)),
        ),
        _check(
            "ambient_capture_controls_denied",
            passed="ambient_capture_start" in denied and "background_learning_toggle" in denied,
            evidence="ambient_capture_and_background_learning_controls_denied",
        ),
        _check(
            "write_and_promotion_controls_denied",
            passed="teaching_session_without_receipt" in denied and "forge_promotion_from_ui_surface" in denied,
            evidence="receiptless_teaching_and_ui_promotion_denied",
        ),
    ]


def _forge_handoff_contract_checks(
    *,
    skillization_ready: bool,
    handoff_payload_schema: list[dict[str, Any]],
    required_reviews: list[str],
    denied_modes: list[str],
) -> list[dict[str, Any]]:
    schema_ids = {_safe_text(item.get("id")) for item in handoff_payload_schema if bool(item.get("required"))}
    reviews = {_safe_text(item) for item in required_reviews}
    denied = {_safe_text(item) for item in denied_modes}
    return [
        _check(
            "skillization_artifact_contract_ready",
            passed=skillization_ready,
            evidence="/apprenticeship/skillization-artifact-contract",
        ),
        _check(
            "forge_handoff_payload_declared",
            passed={
                "pattern_summary",
                "parameterization",
                "usage_scope",
                "decision_logic",
                "validation_expectations",
                "risk_tier_candidate",
                "documentation_draft",
                "test_candidate_structure",
                "operator_review_state",
                "promotion_boundary",
            }.issubset(schema_ids),
            evidence=str(len(handoff_payload_schema)),
        ),
        _check(
            "promotion_reviews_required",
            passed={
                "operator_review",
                "risk_tier_review",
                "documentation_review",
                "test_candidate_review",
                "explicit_promotion_decision",
            }.issubset(reviews),
            evidence=str(len(required_reviews)),
        ),
        _check(
            "direct_promotion_denied",
            passed="direct_forge_promotion" in denied and "proposal_write_without_operator_review" in denied,
            evidence="direct_forge_promotion_and_unreviewed_proposal_write_denied",
        ),
        _check(
            "authority_growth_denied",
            passed="automatic_capability_registration" in denied and "authority_grant_from_teaching" in denied,
            evidence="automatic_registration_and_teaching_authority_denied",
        ),
    ]


def _skillization_artifact_contract_checks(
    *,
    replay_ready: bool,
    artifact_schema: list[dict[str, Any]],
    classification_options: list[str],
    denied_modes: list[str],
) -> list[dict[str, Any]]:
    schema_ids = {_safe_text(item.get("id")) for item in artifact_schema if bool(item.get("required"))}
    classifications = {_safe_text(item) for item in classification_options}
    denied = {_safe_text(item) for item in denied_modes}
    return [
        _check(
            "replay_generalization_contract_ready",
            passed=replay_ready,
            evidence="/apprenticeship/replay-generalization-contract",
        ),
        _check(
            "forge_ready_artifact_schema_declared",
            passed={
                "pattern_summary",
                "parameterization",
                "usage_scope",
                "decision_logic",
                "validation_expectations",
                "risk_tier_candidate",
                "documentation_draft",
                "test_candidate_structure",
            }.issubset(schema_ids),
            evidence=str(len(artifact_schema)),
        ),
        _check(
            "learning_classifications_declared",
            passed={
                "preference_adaptation",
                "workflow_understanding",
                "candidate_reusable_skill",
                "forge_worthy_promoted_capability",
            }.issubset(classifications),
            evidence=str(len(classification_options)),
        ),
        _check(
            "automatic_promotion_denied",
            passed="automatic_promotion" in denied and "silent_authority_growth" in denied,
            evidence="automatic_promotion_and_silent_authority_growth_denied",
        ),
        _check(
            "artifact_write_requires_operator_review",
            passed="unreviewed_capability_creation" in denied and "memory_write_without_operator_review" in denied,
            evidence="unreviewed_artifact_and_memory_write_denied",
        ),
    ]


def _replay_generalization_contract_checks(
    *,
    teaching_ready: bool,
    replay_requirements: list[dict[str, Any]],
    generalization_requirements: list[dict[str, Any]],
    denied_modes: list[str],
) -> list[dict[str, Any]]:
    replay_ids = {_safe_text(item.get("id")) for item in replay_requirements if bool(item.get("required"))}
    generalization_ids = {
        _safe_text(item.get("id")) for item in generalization_requirements if bool(item.get("required"))
    }
    denied = {_safe_text(item) for item in denied_modes}
    return [
        _check(
            "teaching_session_contract_ready",
            passed=teaching_ready,
            evidence="/apprenticeship/teaching-session-contract",
        ),
        _check(
            "bounded_replay_requirements_declared",
            passed={
                "operator_supplied_demonstration_steps",
                "intent_label_readback",
                "bounded_replay_plan",
                "assumption_register",
                "operator_replay_review",
            }.issubset(replay_ids),
            evidence=str(len(replay_requirements)),
        ),
        _check(
            "generalization_requirements_declared",
            passed={
                "variable_inputs",
                "stable_steps",
                "optional_branches",
                "validation_checkpoints",
                "failure_handling",
            }.issubset(generalization_ids),
            evidence=str(len(generalization_requirements)),
        ),
        _check(
            "macro_playback_denied",
            passed="literal_macro_playback" in denied,
            evidence="literal_macro_playback_denied",
        ),
        _check(
            "unreviewed_execution_denied",
            passed="background_replay_execution" in denied and "unreviewed_generalization" in denied,
            evidence="background_replay_and_unreviewed_generalization_denied",
        ),
    ]


def _teaching_session_contract_checks(
    *,
    stage10_closed: bool,
    requirements: list[dict[str, Any]],
    capture_boundaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    required_ids = {_safe_text(item.get("id")) for item in requirements if bool(item.get("required"))}
    boundary_allowed = {_safe_text(item.get("id")): bool(item.get("allowed")) for item in capture_boundaries}
    return [
        _check(
            "stage10_ledger_closure_backstop",
            passed=stage10_closed,
            evidence="/away/stage-closure-decisions",
        ),
        _check(
            "canonical_teaching_requirements_declared",
            passed={
                "explicit_start_stop",
                "declared_scope",
                "intent_label",
                "success_condition",
                "operator_review_before_learning",
            }.issubset(required_ids),
            evidence=str(len(requirements)),
        ),
        _check(
            "capture_boundaries_deny_passive_learning",
            passed=boundary_allowed.get("passive_background_learning") is False,
            evidence="passive_background_learning=false",
        ),
        _check(
            "ambient_capture_denied",
            passed=boundary_allowed.get("screen_capture") is False
            and boundary_allowed.get("audio_capture") is False
            and boundary_allowed.get("keystroke_capture") is False,
            evidence="screen_audio_keystroke_capture=false",
        ),
        _check(
            "operator_supplied_steps_only",
            passed=boundary_allowed.get("operator_supplied_steps_only") is True,
            evidence="operator_supplied_steps_only=true",
        ),
    ]


def _check(check_id: str, *, passed: bool, evidence: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "passed": passed,
        "status": "ready" if passed else "blocked",
        "evidence": evidence,
    }


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def _safe_teaching_session_action(value: Any) -> str:
    text = _safe_text(value)
    if text in _ALLOWED_TEACHING_SESSION_ACTIONS:
        return text
    return "start_teaching_session"


def _safe_replay_receipt_action(value: Any) -> str:
    text = _safe_text(value)
    if text in _ALLOWED_REPLAY_RECEIPT_ACTIONS:
        return text
    return "review_replay"


def _safe_skillization_artifact_action(value: Any) -> str:
    text = _safe_text(value)
    if text in _ALLOWED_SKILLIZATION_ARTIFACT_ACTIONS:
        return text
    return "prepare_skillization_artifact"


def _safe_forge_handoff_action(value: Any) -> str:
    text = _safe_text(value)
    if text in _ALLOWED_FORGE_HANDOFF_ACTIONS:
        return text
    return "review_forge_handoff"


def _teaching_session_receipt_path() -> Path:
    return data_dir() / "logs" / "apprenticeship" / "teaching_session_receipts.jsonl"


def _replay_receipt_path() -> Path:
    return data_dir() / "logs" / "apprenticeship" / "replay_receipts.jsonl"


def _skillization_artifact_receipt_path() -> Path:
    return data_dir() / "logs" / "apprenticeship" / "skillization_artifact_receipts.jsonl"


def _forge_handoff_receipt_path() -> Path:
    return data_dir() / "logs" / "apprenticeship" / "forge_handoff_receipts.jsonl"


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def _read_jsonl_tail(path: Path, *, limit: int) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return items[-limit:]


def _env_profile() -> str:
    return _safe_text(os.getenv("FRANCIS_ENV_PROFILE")).strip().lower() or "dev"


def _now_s() -> int:
    return int(time.time())


def _safe_limit(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(1, min(parsed, 100))


def _redacted_text(value: Any) -> str:
    return redact_secret_text(_safe_text(value))


def _blocked_no_receipt(
    *,
    status: str,
    reason: str,
    required_scope: str,
    next_gap: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "kind": APPRENTICESHIP_TEACHING_SESSION_RECEIPT_KIND,
        "stage": STAGE11_APPRENTICESHIP_STAGE,
        "source_id": "apprenticeship",
        "status": status,
        "reason": reason,
        "receipt_id": "",
        "writes_receipt": False,
        "writes_memory": False,
        "writes_skill_artifact": False,
        "writes_forge_proposal": False,
        "starts_teaching_session": False,
        "captures_screen": False,
        "captures_audio": False,
        "captures_keystrokes": False,
        "passive_learning_enabled": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "required_scope": required_scope,
            "receipt_not_written": True,
            "does_not_write_memory": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": next_gap,
    }
