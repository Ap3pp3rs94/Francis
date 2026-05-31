from __future__ import annotations

from typing import Any

from francis.takeover import takeover_stage9_operator_stage_closure_decision_readback
from francis.world_state.operator_mode import snapshot as operator_mode_snapshot

STAGE10_AWAY_STAGE = "Stage 10 / Away Mode"
AWAY_STATUS_KIND = "francis.stage10.away.status"


def away_status_snapshot() -> dict[str, Any]:
    stage9 = takeover_stage9_operator_stage_closure_decision_readback(limit=5)
    operator = operator_mode_snapshot()
    control_mode = _as_dict(operator.get("control_mode"))
    backlog = _as_dict(operator.get("backlog"))
    continuity = _as_dict(operator.get("continuity"))
    stage9_closed = bool(stage9.get("stage9_closed_by_receipt"))
    deliverables = _away_deliverables(
        stage9_closed=stage9_closed,
        operator=operator,
        backlog=backlog,
        continuity=continuity,
    )
    ready_count = sum(1 for item in deliverables if bool(item.get("ready")))
    required_count = len(deliverables)
    return {
        "ok": True,
        "kind": AWAY_STATUS_KIND,
        "stage": STAGE10_AWAY_STAGE,
        "source_id": "away",
        "status": "stage10_groundwork_ready" if stage9_closed else "awaiting_stage9_ledger_closure",
        "stage9_closed_by_receipt": stage9_closed,
        "stage9_latest_closure_receipt_id": _safe_text(stage9.get("latest_receipt_id")),
        "stage9_next_smallest_truthful_gap": _safe_text(stage9.get("next_smallest_truthful_gap")),
        "control_mode": control_mode,
        "away_declared": _safe_text(control_mode.get("id")).lower() == "away",
        "deliverables": deliverables,
        "ready_count": ready_count,
        "required_count": required_count,
        "away_mode_ready": stage9_closed and ready_count == required_count,
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_tasks": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "requires_stage9_ledger_closure": True,
            "away_autonomy_not_enabled_by_status": True,
            "risky_actions_remain_gated": True,
            "does_not_start_background_work": True,
            "does_not_write_receipts": True,
            "does_not_write_tasks": True,
            "does_not_write_memory": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "routes": {
            "status": "/away/status",
            "operator_mode": "/system/operator_mode",
            "stage9_closure_readback": "/takeover/stage-closure-decisions",
        },
        "next_smallest_truthful_gap": "stage10_away_safe_task_classes" if stage9_closed else "stage9_ledger_closure",
    }


def _away_deliverables(
    *,
    stage9_closed: bool,
    operator: dict[str, Any],
    backlog: dict[str, Any],
    continuity: dict[str, Any],
) -> list[dict[str, Any]]:
    available_modes = [
        _safe_text(item.get("id")).lower()
        for item in _as_list(operator.get("available_modes"))
        if isinstance(item, dict)
    ]
    return [
        {
            "id": "stage9_ledger_closure_backstop",
            "label": "Stage 9 ledger closure backstop",
            "ready": stage9_closed,
            "evidence": "/takeover/stage-closure-decisions",
        },
        {
            "id": "away_mode_visibility",
            "label": "Away mode visibility",
            "ready": "away" in available_modes,
            "evidence": "/system/operator_mode",
        },
        {
            "id": "approvals_queue_visibility",
            "label": "Approvals queue visibility",
            "ready": "pending_approvals" in backlog and "approval_pending_tasks" in backlog,
            "evidence": "operator_mode.backlog",
        },
        {
            "id": "mission_return_briefing_source",
            "label": "Mission return briefing source",
            "ready": bool(_safe_text(continuity.get("headline"))),
            "evidence": "operator_mode.continuity.headline",
        },
        {
            "id": "away_safe_task_classes",
            "label": "Away-safe task classes",
            "ready": False,
            "evidence": "not_implemented_yet",
        },
        {
            "id": "autonomy_budgets",
            "label": "Autonomy budgets",
            "ready": False,
            "evidence": "not_implemented_yet",
        },
        {
            "id": "shift_reports",
            "label": "Shift reports",
            "ready": False,
            "evidence": "not_implemented_yet",
        },
        {
            "id": "return_briefing_flow",
            "label": "Return briefing flow",
            "ready": False,
            "evidence": "not_implemented_yet",
        },
    ]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""
