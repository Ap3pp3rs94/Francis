from __future__ import annotations

from typing import Any

from francis.away import away_stage10_operator_stage_closure_decision_readback

STAGE11_APPRENTICESHIP_STAGE = "Stage 11 / Apprenticeship"
APPRENTICESHIP_STATUS_KIND = "francis.stage11.apprenticeship.status"


def apprenticeship_status_snapshot() -> dict[str, Any]:
    stage10 = away_stage10_operator_stage_closure_decision_readback(limit=5)
    stage10_closed = bool(stage10.get("stage10_closed_by_receipt"))
    deliverables = _apprenticeship_deliverables(stage10_closed=stage10_closed)
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
        "teaching_session_ready": False,
        "replay_generalization_ready": False,
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
        },
        "next_smallest_truthful_gap": "stage11_teaching_session_contract"
        if stage10_closed
        else "stage10_ledger_closure",
    }


def _apprenticeship_deliverables(*, stage10_closed: bool) -> list[dict[str, Any]]:
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
            "ready": False,
            "evidence": "stage11_teaching_session_contract",
        },
        {
            "id": "replay_generalization_flow",
            "label": "Replay and generalization flow",
            "ready": False,
            "evidence": "stage11_replay_generalization_contract",
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


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""
