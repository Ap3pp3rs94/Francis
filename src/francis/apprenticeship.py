from __future__ import annotations

from typing import Any

from francis.away import away_stage10_operator_stage_closure_decision_readback

STAGE11_APPRENTICESHIP_STAGE = "Stage 11 / Apprenticeship"
APPRENTICESHIP_STATUS_KIND = "francis.stage11.apprenticeship.status"
APPRENTICESHIP_TEACHING_SESSION_CONTRACT_KIND = "francis.stage11.apprenticeship.teaching_session_contract"
APPRENTICESHIP_REPLAY_GENERALIZATION_CONTRACT_KIND = "francis.stage11.apprenticeship.replay_generalization_contract"


def apprenticeship_status_snapshot() -> dict[str, Any]:
    stage10 = away_stage10_operator_stage_closure_decision_readback(limit=5)
    stage10_closed = bool(stage10.get("stage10_closed_by_receipt"))
    teaching_session = apprenticeship_teaching_session_contract()
    teaching_session_ready = bool(teaching_session.get("teaching_session_contract_ready"))
    replay_generalization = apprenticeship_replay_generalization_contract()
    replay_generalization_ready = bool(replay_generalization.get("replay_generalization_contract_ready"))
    deliverables = _apprenticeship_deliverables(
        stage10_closed=stage10_closed,
        teaching_session_ready=teaching_session_ready,
        replay_generalization_ready=replay_generalization_ready,
    )
    ready_count = sum(1 for item in deliverables if bool(item.get("ready")))
    required_count = len(deliverables)
    return {
        "ok": True,
        "kind": APPRENTICESHIP_STATUS_KIND,
        "stage": STAGE11_APPRENTICESHIP_STAGE,
        "source_id": "apprenticeship",
        "status": "stage11_groundwork_ready" if stage10_closed else "awaiting_stage10_ledger_closure",
        "stage10_closed_by_receipt": stage10_closed,
        "stage10_latest_closure_receipt_id": _safe_text(stage10.get("latest_receipt_id")),
        "stage10_next_smallest_truthful_gap": _safe_text(stage10.get("next_smallest_truthful_gap")),
        "deliverables": deliverables,
        "ready_count": ready_count,
        "required_count": required_count,
        "teaching_session_ready": teaching_session_ready,
        "replay_generalization_ready": replay_generalization_ready,
        "skillization_ready": False,
        "forge_handoff_ready": False,
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
        },
        "next_smallest_truthful_gap": "stage11_skillization_artifact_contract"
        if stage10_closed and replay_generalization_ready
        else "stage11_replay_generalization_contract"
        if stage10_closed and teaching_session_ready
        else "stage11_teaching_session_contract"
        if stage10_closed
        else "stage10_ledger_closure",
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


def _apprenticeship_deliverables(
    *,
    stage10_closed: bool,
    teaching_session_ready: bool,
    replay_generalization_ready: bool,
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
            "ready": False,
            "evidence": "stage11_skillization_artifact_contract",
        },
        {
            "id": "forge_ready_outputs",
            "label": "Forge-ready outputs from demonstration",
            "ready": False,
            "evidence": "stage11_forge_handoff_contract",
        },
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
