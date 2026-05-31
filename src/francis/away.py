from __future__ import annotations

from typing import Any

from francis.takeover import takeover_stage9_operator_stage_closure_decision_readback
from francis.world_state.operator_mode import snapshot as operator_mode_snapshot

STAGE10_AWAY_STAGE = "Stage 10 / Away Mode"
AWAY_STATUS_KIND = "francis.stage10.away.status"
AWAY_SAFE_TASK_CLASSES_KIND = "francis.stage10.away.safe_task_classes"
AWAY_AUTONOMY_BUDGETS_KIND = "francis.stage10.away.autonomy_budgets"

_AWAY_SAFE_TASK_CLASSES: tuple[dict[str, Any], ...] = (
    {
        "id": "continuity_monitoring",
        "label": "Continuity monitoring",
        "allowed_effect": "read_only",
        "risk_tier": "low",
        "description": "Read mission, operation, approval, and incident state without mutating work.",
    },
    {
        "id": "approval_queue_triage",
        "label": "Approval queue triage",
        "allowed_effect": "read_only_priority_projection",
        "risk_tier": "low",
        "description": "Rank pending approvals for return review without deciding them.",
    },
    {
        "id": "shift_report_draft",
        "label": "Shift report draft",
        "allowed_effect": "draft_only",
        "risk_tier": "low",
        "description": "Prepare a return briefing from existing receipts and mission state.",
    },
    {
        "id": "safe_plan_preparation",
        "label": "Safe plan preparation",
        "allowed_effect": "draft_only",
        "risk_tier": "low",
        "description": "Prepare bounded next-step plans without executing them.",
    },
)

_AWAY_AUTONOMY_BUDGETS: tuple[dict[str, Any], ...] = (
    {
        "id": "read_only_monitoring_budget",
        "class_id": "continuity_monitoring",
        "max_items": 50,
        "max_duration_minutes": 120,
        "allowed_effect": "read_only",
    },
    {
        "id": "approval_triage_budget",
        "class_id": "approval_queue_triage",
        "max_items": 25,
        "max_duration_minutes": 60,
        "allowed_effect": "read_only_priority_projection",
    },
    {
        "id": "shift_report_draft_budget",
        "class_id": "shift_report_draft",
        "max_items": 3,
        "max_duration_minutes": 90,
        "allowed_effect": "draft_only",
    },
    {
        "id": "safe_plan_preparation_budget",
        "class_id": "safe_plan_preparation",
        "max_items": 3,
        "max_duration_minutes": 90,
        "allowed_effect": "draft_only",
    },
)


def away_status_snapshot() -> dict[str, Any]:
    stage9 = takeover_stage9_operator_stage_closure_decision_readback(limit=5)
    operator = operator_mode_snapshot()
    safe_task_classes = away_safe_task_classes_review()
    autonomy_budgets = away_autonomy_budgets_review()
    control_mode = _as_dict(operator.get("control_mode"))
    backlog = _as_dict(operator.get("backlog"))
    continuity = _as_dict(operator.get("continuity"))
    stage9_closed = bool(stage9.get("stage9_closed_by_receipt"))
    deliverables = _away_deliverables(
        stage9_closed=stage9_closed,
        safe_task_classes_ready=bool(safe_task_classes.get("away_safe_task_classes_ready")),
        autonomy_budgets_ready=bool(autonomy_budgets.get("autonomy_budgets_ready")),
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
            "safe_task_classes": "/away/safe-task-classes",
            "autonomy_budgets": "/away/autonomy-budgets",
        },
        "next_smallest_truthful_gap": "stage10_shift_reports"
        if stage9_closed and bool(autonomy_budgets.get("autonomy_budgets_ready"))
        else "stage10_autonomy_budgets"
        if stage9_closed and bool(safe_task_classes.get("away_safe_task_classes_ready"))
        else "stage10_away_safe_task_classes"
        if stage9_closed
        else "stage9_ledger_closure",
    }


def away_safe_task_classes_review() -> dict[str, Any]:
    stage9 = takeover_stage9_operator_stage_closure_decision_readback(limit=5)
    stage9_closed = bool(stage9.get("stage9_closed_by_receipt"))
    classes = [_safe_task_class_item(item) for item in _AWAY_SAFE_TASK_CLASSES]
    checks = _safe_task_class_checks(stage9_closed=stage9_closed, classes=classes)
    ready = all(bool(check.get("passed")) for check in checks)
    return {
        "ok": True,
        "kind": AWAY_SAFE_TASK_CLASSES_KIND,
        "stage": STAGE10_AWAY_STAGE,
        "source_id": "away",
        "status": "ready" if ready else "blocked",
        "stage9_closed_by_receipt": stage9_closed,
        "stage9_latest_closure_receipt_id": _safe_text(stage9.get("latest_receipt_id")),
        "away_safe_task_classes_ready": ready,
        "classes": classes,
        "class_count": len(classes),
        "checks": checks,
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
            "safe_task_class_contract_only": True,
            "does_not_enable_away_autonomy": True,
            "risky_actions_remain_gated": True,
            "approval_decisions_remain_operator_gated": True,
            "external_sends_remain_gated": True,
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
        "next_smallest_truthful_gap": "stage10_autonomy_budgets"
        if ready
        else "stage10_away_safe_task_classes"
        if stage9_closed
        else "stage9_ledger_closure",
    }


def away_autonomy_budgets_review() -> dict[str, Any]:
    safe_classes = away_safe_task_classes_review()
    safe_classes_ready = bool(safe_classes.get("away_safe_task_classes_ready"))
    safe_class_ids = {
        _safe_text(item.get("id")) for item in _as_list(safe_classes.get("classes")) if isinstance(item, dict)
    }
    budgets = [_autonomy_budget_item(item) for item in _AWAY_AUTONOMY_BUDGETS]
    checks = _autonomy_budget_checks(
        safe_classes_ready=safe_classes_ready,
        safe_class_ids=safe_class_ids,
        budgets=budgets,
    )
    ready = all(bool(check.get("passed")) for check in checks)
    return {
        "ok": True,
        "kind": AWAY_AUTONOMY_BUDGETS_KIND,
        "stage": STAGE10_AWAY_STAGE,
        "source_id": "away",
        "status": "ready" if ready else "blocked",
        "safe_task_classes_ready": safe_classes_ready,
        "autonomy_budgets_ready": ready,
        "budgets": budgets,
        "budget_count": len(budgets),
        "checks": checks,
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
        "activates_away_autonomy": False,
        "governance": {
            "read_only": True,
            "autonomy_budget_contract_only": True,
            "does_not_activate_away_autonomy": True,
            "requires_safe_task_classes": True,
            "approval_required_before_execution": True,
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
        "next_smallest_truthful_gap": "stage10_shift_reports" if ready else "stage10_autonomy_budgets",
    }


def _away_deliverables(
    *,
    stage9_closed: bool,
    safe_task_classes_ready: bool,
    autonomy_budgets_ready: bool,
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
            "ready": safe_task_classes_ready,
            "evidence": "/away/safe-task-classes",
        },
        {
            "id": "autonomy_budgets",
            "label": "Autonomy budgets",
            "ready": autonomy_budgets_ready,
            "evidence": "/away/autonomy-budgets",
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


def _safe_task_class_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _safe_text(item.get("id")),
        "label": _safe_text(item.get("label")),
        "allowed_effect": _safe_text(item.get("allowed_effect")),
        "risk_tier": _safe_text(item.get("risk_tier")),
        "description": _safe_text(item.get("description")),
        "may_execute_tools": False,
        "may_run_shell": False,
        "may_run_git": False,
        "may_start_processes": False,
        "may_write_memory": False,
        "may_write_files": False,
        "may_send_external_messages": False,
        "may_decide_approvals": False,
        "requires_operator_approval_for_execution": True,
        "requires_autonomy_budget_before_execution": True,
    }


def _safe_task_class_checks(*, stage9_closed: bool, classes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _check(
            "stage9_closure_backstop",
            passed=stage9_closed,
            evidence="/takeover/stage-closure-decisions",
        ),
        _check(
            "classes_declared",
            passed=len(classes) >= 4 and all(bool(item.get("id")) for item in classes),
            evidence=str(len(classes)),
        ),
        _check(
            "effects_limited_to_read_or_draft",
            passed=all(
                _safe_text(item.get("allowed_effect")) in {"read_only", "read_only_priority_projection", "draft_only"}
                for item in classes
            ),
            evidence="read_or_draft_only",
        ),
        _check(
            "execution_requires_future_budget_and_approval",
            passed=all(
                bool(item.get("requires_operator_approval_for_execution"))
                and bool(item.get("requires_autonomy_budget_before_execution"))
                for item in classes
            ),
            evidence="approval_and_budget_required",
        ),
        _check(
            "risky_actions_denied",
            passed=all(
                not bool(item.get(key))
                for item in classes
                for key in (
                    "may_execute_tools",
                    "may_run_shell",
                    "may_run_git",
                    "may_start_processes",
                    "may_write_memory",
                    "may_write_files",
                    "may_send_external_messages",
                    "may_decide_approvals",
                )
            ),
            evidence="no_risky_actions_allowed",
        ),
    ]


def _autonomy_budget_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _safe_text(item.get("id")),
        "class_id": _safe_text(item.get("class_id")),
        "allowed_effect": _safe_text(item.get("allowed_effect")),
        "max_items": _safe_int(item.get("max_items")),
        "max_duration_minutes": _safe_int(item.get("max_duration_minutes")),
        "may_execute_tools": False,
        "may_run_shell": False,
        "may_run_git": False,
        "may_start_processes": False,
        "may_write_memory": False,
        "may_write_files": False,
        "may_send_external_messages": False,
        "may_decide_approvals": False,
        "requires_operator_approval_for_execution": True,
        "budget_activation_required": True,
    }


def _autonomy_budget_checks(
    *,
    safe_classes_ready: bool,
    safe_class_ids: set[str],
    budgets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        _check(
            "safe_task_classes_ready",
            passed=safe_classes_ready,
            evidence="/away/safe-task-classes",
        ),
        _check(
            "budgets_declared_for_each_safe_class",
            passed=bool(safe_class_ids) and {_safe_text(item.get("class_id")) for item in budgets} == safe_class_ids,
            evidence=str(len(budgets)),
        ),
        _check(
            "budgets_are_bounded",
            passed=all(
                0 < _safe_int(item.get("max_items")) <= 50 and 0 < _safe_int(item.get("max_duration_minutes")) <= 120
                for item in budgets
            ),
            evidence="bounded_items_and_duration",
        ),
        _check(
            "budget_effects_match_safe_classes",
            passed=all(
                _safe_text(item.get("allowed_effect")) in {"read_only", "read_only_priority_projection", "draft_only"}
                for item in budgets
            ),
            evidence="read_or_draft_only",
        ),
        _check(
            "budget_activation_gated",
            passed=all(
                bool(item.get("requires_operator_approval_for_execution"))
                and bool(item.get("budget_activation_required"))
                for item in budgets
            ),
            evidence="approval_required_before_execution",
        ),
        _check(
            "risky_actions_denied",
            passed=all(
                not bool(item.get(key))
                for item in budgets
                for key in (
                    "may_execute_tools",
                    "may_run_shell",
                    "may_run_git",
                    "may_start_processes",
                    "may_write_memory",
                    "may_write_files",
                    "may_send_external_messages",
                    "may_decide_approvals",
                )
            ),
            evidence="no_risky_actions_allowed",
        ),
    ]


def _check(check_id: str, *, passed: bool, evidence: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "passed": passed,
        "status": "ready" if passed else "blocked",
        "evidence": evidence,
    }


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


def _safe_int(value: Any) -> int:
    try:
        parsed = int(value)
    except Exception:
        return 0
    return parsed
