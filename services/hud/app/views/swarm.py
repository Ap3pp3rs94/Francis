from __future__ import annotations

from typing import Any

from services.hud.app.state import build_lens_snapshot


def _detail_state(delegation_id: str, focus_delegation_id: str) -> str:
    if delegation_id and focus_delegation_id and delegation_id == focus_delegation_id:
        return "current"
    return "historical"


def _unit_cards(unit: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"label": "Role", "value": str(unit.get("role", "unit")).strip() or "unit", "tone": "medium"},
        {"label": "State", "value": str(unit.get("state", "ready")).strip() or "ready", "tone": "high" if str(unit.get("state", "")).strip().lower() == "attention" else "low"},
        {"label": "Queued", "value": str(int(unit.get("queued_count", 0) or 0)), "tone": "medium" if int(unit.get("queued_count", 0) or 0) else "low"},
        {"label": "Active", "value": str(int(unit.get("active_count", 0) or 0)), "tone": "medium" if int(unit.get("active_count", 0) or 0) else "low"},
        {"label": "Deadletter", "value": str(int(unit.get("deadletter_count", 0) or 0)), "tone": "high" if int(unit.get("deadletter_count", 0) or 0) else "low"},
    ]


def _delegation_summary(row: dict[str, Any]) -> str:
    target = str(row.get("target_label", row.get("target_unit_id", "unit"))).strip() or "unit"
    action_kind = str(row.get("action_kind", "task")).strip() or "task"
    status = str(row.get("status", "queued")).strip() or "queued"
    summary = str(row.get("summary", "")).strip()
    if summary:
        return f"{target} is carrying {action_kind} as {status}: {summary}"
    return f"{target} is carrying {action_kind} as {status}."


def _delegation_cards(row: dict[str, Any]) -> list[dict[str, str]]:
    status = str(row.get("status", "queued")).strip() or "queued"
    attempts = int(row.get("attempts", 0) or 0)
    max_attempts = int(row.get("max_attempts", 0) or 0)
    return [
        {"label": "Target", "value": str(row.get("target_label", row.get("target_unit_id", "unit"))).strip() or "unit", "tone": "medium"},
        {"label": "Action", "value": str(row.get("action_kind", "task")).strip() or "task", "tone": "low"},
        {"label": "Status", "value": status, "tone": "high" if status == "deadlettered" else "medium" if status == "leased" else "low"},
        {"label": "Attempts", "value": f"{attempts}/{max_attempts or 1}", "tone": "high" if attempts and attempts >= max(max_attempts - 1, 1) else "low"},
        {"label": "Trace", "value": str(row.get("trace_id", "")).strip() or "none", "tone": "low"},
    ]


def _audit(row: dict[str, Any], detail_state: str) -> dict[str, Any]:
    return {
        "delegation_id": str(row.get("id", "")).strip(),
        "source_unit_id": str(row.get("source_unit_id", "")).strip(),
        "target_unit_id": str(row.get("target_unit_id", "")).strip(),
        "action_kind": str(row.get("action_kind", "")).strip(),
        "status": str(row.get("status", "")).strip(),
        "summary": str(row.get("summary", "")).strip(),
        "handoff_note": str(row.get("handoff_note", "")).strip(),
        "authority_basis": str(row.get("authority_basis", "")).strip(),
        "run_id": str(row.get("run_id", "")).strip(),
        "trace_id": str(row.get("trace_id", "")).strip(),
        "mission_id": str(row.get("mission_id", "")).strip(),
        "approval_id": str(row.get("approval_id", "")).strip(),
        "scope_apps": row.get("scope_apps", []) if isinstance(row.get("scope_apps"), list) else [],
        "attempts": int(row.get("attempts", 0) or 0),
        "max_attempts": int(row.get("max_attempts", 0) or 0),
        "detail_state": detail_state,
        "leased_at": row.get("leased_at"),
        "lease_owner": str(row.get("lease_owner", "")).strip(),
        "lease_expires_at": row.get("lease_expires_at"),
        "completed_at": row.get("completed_at"),
        "completed_by_unit_id": str(row.get("completed_by_unit_id", "")).strip(),
        "deadlettered_at": row.get("deadlettered_at"),
        "result_summary": str(row.get("result_summary", "")).strip(),
        "last_error": str(row.get("last_error", "")).strip(),
        "last_failure_reason": str(row.get("last_failure_reason", "")).strip(),
    }


def _controls(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    delegation_id = str(row.get("id", "")).strip()
    unit_id = str(row.get("target_unit_id", "")).strip()
    status = str(row.get("status", "")).strip().lower()
    return {
        "lease": {
            "label": "Lease Delegation",
            "enabled": bool(delegation_id and unit_id) and status == "queued",
            "unit_id": unit_id,
        },
        "complete": {
            "label": "Complete Delegation",
            "enabled": bool(delegation_id and unit_id) and status in {"queued", "leased"},
            "unit_id": unit_id,
        },
        "fail": {
            "label": "Fail Delegation",
            "enabled": bool(delegation_id and unit_id) and status in {"queued", "leased"},
            "unit_id": unit_id,
        },
    }


def get_swarm_view(*, snapshot: dict[str, object] | None = None) -> dict[str, Any]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    swarm = snapshot.get("swarm", {}) if isinstance(snapshot.get("swarm"), dict) else {}
    units = [row for row in swarm.get("units", []) if isinstance(row, dict)]
    delegations = [row for row in swarm.get("delegations", []) if isinstance(row, dict)]
    deadletter = [row for row in swarm.get("deadletter", []) if isinstance(row, dict)]

    focus = next(
        (row for row in delegations if str(row.get("status", "")).strip().lower() == "leased"),
        None,
    )
    if focus is None:
        focus = next(
            (row for row in delegations if str(row.get("status", "")).strip().lower() == "queued"),
            None,
        )
    if focus is None:
        focus = next(
            (row for row in delegations if str(row.get("status", "")).strip().lower() == "deadlettered"),
            None,
        )
    focus_delegation_id = str((focus or {}).get("id", "")).strip()

    delegation_rows: list[dict[str, Any]] = []
    for row in delegations:
        delegation_id = str(row.get("id", "")).strip()
        detail_state = _detail_state(delegation_id, focus_delegation_id)
        delegation_rows.append(
            {
                "delegation_id": delegation_id,
                "target_unit_id": str(row.get("target_unit_id", "")).strip(),
                "target_label": str(row.get("target_label", "")).strip() or str(row.get("target_unit_id", "unit")).strip() or "unit",
                "action_kind": str(row.get("action_kind", "")).strip() or "task",
                "status": str(row.get("status", "")).strip() or "queued",
                "summary": _delegation_summary(row),
                "detail_summary": _delegation_summary(row),
                "detail_state": detail_state,
                "detail_cards": _delegation_cards(row),
                "audit": _audit(row, detail_state),
                "controls": _controls(row),
            }
        )

    unit_rows: list[dict[str, Any]] = []
    for row in units:
        unit_rows.append(
            {
                "unit_id": str(row.get("unit_id", "")).strip(),
                "label": str(row.get("label", "Unit")).strip() or "Unit",
                "role": str(row.get("role", "unit")).strip() or "unit",
                "state": str(row.get("state", "ready")).strip() or "ready",
                "summary": str(row.get("summary", "")).strip() or "No unit summary is available.",
                "detail_cards": _unit_cards(row),
                "audit": {
                    "unit_id": str(row.get("unit_id", "")).strip(),
                    "label": str(row.get("label", "")).strip(),
                    "role": str(row.get("role", "")).strip(),
                    "summary": str(row.get("summary", "")).strip(),
                    "capabilities": row.get("capabilities", []) if isinstance(row.get("capabilities"), list) else [],
                    "queued_count": int(row.get("queued_count", 0) or 0),
                    "active_count": int(row.get("active_count", 0) or 0),
                    "completed_count": int(row.get("completed_count", 0) or 0),
                    "deadletter_count": int(row.get("deadletter_count", 0) or 0),
                    "last_delegation_at": row.get("last_delegation_at"),
                    "last_delegation_summary": str(row.get("last_delegation_summary", "")).strip(),
                },
            }
        )

    focused_row = next(
        (row for row in delegation_rows if str(row.get("delegation_id", "")).strip() == focus_delegation_id),
        None,
    )
    deadletter_count = int(swarm.get("deadletter_count", 0) or 0)
    leased_count = int(swarm.get("leased_count", 0) or 0)
    queued_count = int(swarm.get("queued_count", 0) or 0)
    severity = "high" if deadletter_count > 0 else "medium" if leased_count > 0 or queued_count > 0 else "low"
    return {
        "status": "ok",
        "surface": "swarm",
        "summary": str(swarm.get("summary", "")).strip()
        or "Swarm state is not available yet.",
        "severity": severity,
        "focus_delegation_id": focus_delegation_id,
        "defaults": {
            "default_target_unit_id": "planner",
            "action_kinds": [
                "mission.plan",
                "repo.status",
                "repo.diff",
                "repo.lint",
                "repo.tests",
                "verify.receipts",
                "fabric.recall",
                "incident.review",
            ],
        },
        "cards": [
            {"label": "Units", "value": str(int(swarm.get("unit_count", 0) or 0)), "tone": "low"},
            {"label": "Queued", "value": str(queued_count), "tone": "medium" if queued_count else "low"},
            {"label": "Active", "value": str(leased_count), "tone": "medium" if leased_count else "low"},
            {"label": "Deadletter", "value": str(deadletter_count), "tone": "high" if deadletter_count else "low"},
        ],
        "units": unit_rows,
        "delegations": delegation_rows,
        "deadletter": deadletter[:5],
        "detail": {
            "audit": focused_row.get("audit", {}) if isinstance(focused_row, dict) else {},
            "controls": focused_row.get("controls", {}) if isinstance(focused_row, dict) else {},
        },
    }
