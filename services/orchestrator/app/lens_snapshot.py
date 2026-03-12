from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from francis_brain.apprenticeship import summarize_apprenticeship
from francis_brain.recall import summarize_fabric
from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS

from services.orchestrator.app.control_state import DEFAULT_ALLOWED_APPS
from services.orchestrator.app.federation_store import load_or_init_topology
from services.orchestrator.app.swarm_store import build_swarm_state
from services.orchestrator.app.takeover_snapshot import load_takeover_state
from services.orchestrator.app.usage_loop import build_current_work, build_next_best_action

DEFAULT_MODES = {"observe", "assist", "pilot", "away"}
DEFAULT_WORKSPACE_ROOT = Path(
    os.environ.get(
        "FRANCIS_WORKSPACE_ROOT",
        str((Path(__file__).resolve().parents[3] / "workspace").resolve()),
    )
).resolve()
TERMINAL_MISSION_STATUSES = {"completed", "failed", "cancelled", "canceled"}
TERMINAL_INCIDENT_STATES = {"resolved", "closed", "mitigated"}
SEVERITY_ORDER = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
    "nominal": 0,
}


def get_workspace_root() -> Path:
    return DEFAULT_WORKSPACE_ROOT


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _tail(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    normalized_limit = max(0, min(int(limit), 50))
    return rows[-normalized_limit:] if normalized_limit else []


def _normalize_mode(raw_mode: Any) -> str:
    normalized = str(raw_mode or "").strip().lower()
    return normalized if normalized in DEFAULT_MODES else "pilot"


def _default_control_state(workspace_root: Path) -> dict[str, Any]:
    repo_root = workspace_root.parent.resolve()
    return {
        "mode": "pilot",
        "kill_switch": False,
        "scopes": {
            "repos": [str(repo_root)],
            "workspaces": [str(workspace_root)],
            "apps": list(DEFAULT_ALLOWED_APPS),
        },
    }


def _control_state(workspace_root: Path) -> dict[str, Any]:
    state = _read_json(workspace_root / "control" / "state.json", {})
    if not isinstance(state, dict):
        state = {}
    merged = _default_control_state(workspace_root)
    merged.update({key: value for key, value in state.items() if key in {"mode", "kill_switch", "scopes", "updated_at"}})
    scopes = state.get("scopes", {})
    if isinstance(scopes, dict):
        merged["scopes"] = {
            "repos": list(scopes.get("repos", merged["scopes"]["repos"])),
            "workspaces": list(scopes.get("workspaces", merged["scopes"]["workspaces"])),
            "apps": list(scopes.get("apps", merged["scopes"]["apps"])),
        }
    merged["mode"] = _normalize_mode(merged.get("mode"))
    merged["kill_switch"] = bool(merged.get("kill_switch", False))
    return merged


def _materialize_approvals(workspace_root: Path) -> dict[str, Any]:
    requests = _read_jsonl(workspace_root / "approvals" / "requests.jsonl")
    decisions = _read_jsonl(workspace_root / "journals" / "decisions.jsonl")
    latest_decisions: dict[str, dict[str, Any]] = {}
    for row in decisions:
        if str(row.get("kind", "")).strip().lower() != "approval.decision":
            continue
        request_id = str(row.get("request_id", "")).strip()
        if request_id:
            latest_decisions[request_id] = row

    materialized: list[dict[str, Any]] = []
    for row in requests:
        approval_id = str(row.get("id", "")).strip()
        status = "pending"
        if approval_id and approval_id in latest_decisions:
            decision = str(latest_decisions[approval_id].get("decision", "")).strip().lower()
            if decision in {"approved", "rejected"}:
                status = decision
        materialized.append(
            {
                "id": approval_id,
                "ts": row.get("ts"),
                "action": str(row.get("action", "")).strip(),
                "reason": str(row.get("reason", "")).strip(),
                "requested_by": str(row.get("requested_by", "")).strip(),
                "status": status,
            }
        )

    pending = [row for row in materialized if row["status"] == "pending"]
    pending.sort(key=lambda row: str(row.get("ts", "")))
    return {
        "count": len(materialized),
        "pending_count": len(pending),
        "pending": _tail(pending, 5),
    }


def _materialize_missions(workspace_root: Path) -> dict[str, Any]:
    doc = _read_json(workspace_root / "missions" / "missions.json", {"missions": []})
    rows = doc.get("missions", []) if isinstance(doc, dict) else []
    missions = [row for row in rows if isinstance(row, dict)]

    active: list[dict[str, Any]] = []
    backlog: list[dict[str, Any]] = []
    completed: list[dict[str, Any]] = []
    for row in missions:
        item = {
            "id": str(row.get("id", "")).strip(),
            "title": str(row.get("title", "")).strip() or "Untitled mission",
            "objective": str(row.get("objective", "")).strip(),
            "status": str(row.get("status", "planned")).strip().lower() or "planned",
            "phase": str(row.get("status", "planned")).strip().lower() or "planned",
            "priority": str(row.get("priority", "normal")).strip().lower() or "normal",
            "updated_at": row.get("updated_at") or row.get("ts"),
        }
        if item["status"] in TERMINAL_MISSION_STATUSES:
            completed.append(item)
        elif item["status"] in {"planned", "queued", "backlog"}:
            backlog.append(item)
        else:
            active.append(item)

    active.sort(key=lambda row: str(row.get("updated_at", "")), reverse=True)
    backlog.sort(key=lambda row: str(row.get("updated_at", "")), reverse=True)
    completed.sort(key=lambda row: str(row.get("updated_at", "")), reverse=True)
    history = _read_jsonl(workspace_root / "missions" / "history.jsonl")
    return {
        "active": _tail(active, 5),
        "backlog": _tail(backlog, 5),
        "completed": _tail(completed, 5),
        "history_tail": _tail(history, 5),
        "active_count": len(active),
        "backlog_count": len(backlog),
        "completed_count": len(completed),
    }


def _materialize_inbox(workspace_root: Path) -> dict[str, Any]:
    rows = _read_jsonl(workspace_root / "inbox" / "messages.jsonl")
    items: list[dict[str, Any]] = []
    alerts = 0
    for row in rows:
        severity = str(row.get("severity", "info")).strip().lower() or "info"
        if severity == "alert":
            alerts += 1
        items.append(
            {
                "id": str(row.get("id", "")).strip(),
                "ts": row.get("ts"),
                "title": str(row.get("title", "")).strip() or str(row.get("kind", "Inbox item")).strip(),
                "summary": str(row.get("summary", "")).strip() or str(row.get("message", "")).strip(),
                "severity": severity,
            }
        )
    items.sort(key=lambda row: str(row.get("ts", "")))
    return {
        "count": len(items),
        "alert_count": alerts,
        "items": _tail(items, 5),
    }


def _materialize_incidents(workspace_root: Path) -> dict[str, Any]:
    rows = _read_jsonl(workspace_root / "incidents" / "incidents.jsonl")
    items: list[dict[str, Any]] = []
    for row in rows:
        state = str(row.get("state", row.get("status", "open"))).strip().lower() or "open"
        if state in TERMINAL_INCIDENT_STATES:
            continue
        severity = str(row.get("severity", "medium")).strip().lower() or "medium"
        items.append(
            {
                "id": str(row.get("id", "")).strip(),
                "ts": row.get("ts"),
                "state": state,
                "severity": severity,
                "summary": str(row.get("summary", "")).strip() or str(row.get("message", "Incident")).strip(),
                "source": str(row.get("source", "")).strip(),
            }
        )
    items.sort(
        key=lambda row: (SEVERITY_ORDER.get(str(row.get("severity", "")), 0), str(row.get("ts", ""))),
        reverse=True,
    )
    highest = items[0]["severity"] if items else "nominal"
    if not items:
        items = [
            {
                "id": "incident-none",
                "ts": utc_now_iso(),
                "state": "nominal",
                "severity": "nominal",
                "summary": "No open incidents in the current workspace.",
                "source": "hud",
            }
        ]
    return {
        "open_count": 0 if items[0]["id"] == "incident-none" else len(items),
        "highest_severity": highest,
        "items": _tail(items, 5),
    }


def _materialize_security(workspace_root: Path) -> dict[str, Any]:
    rows = _read_jsonl(workspace_root / "security" / "quarantine.jsonl")
    items: list[dict[str, Any]] = []
    category_counts: dict[str, int] = {}
    for row in rows:
        severity = str(row.get("severity", "medium")).strip().lower() or "medium"
        categories = [
            str(item).strip().lower()
            for item in row.get("categories", [])
            if isinstance(item, str) and str(item).strip()
        ]
        for category in categories:
            category_counts[category] = int(category_counts.get(category, 0)) + 1
        action = str(row.get("action", "")).strip()
        surface = str(row.get("surface", "")).strip()
        items.append(
            {
                "id": str(row.get("id", "")).strip(),
                "ts": row.get("ts"),
                "severity": severity,
                "surface": surface,
                "action": action,
                "categories": categories,
                "summary": (
                    f"{action or 'unknown action'} quarantined on {surface or 'unknown surface'}"
                    + (f" ({', '.join(categories)})" if categories else "")
                ),
            }
        )
    items.sort(
        key=lambda row: (SEVERITY_ORDER.get(str(row.get("severity", "")), 0), str(row.get("ts", ""))),
        reverse=True,
    )
    highest = items[0]["severity"] if items else "nominal"
    latest = max(items, key=lambda row: str(row.get("ts", "")), default=None)
    if not items:
        items = [
            {
                "id": "security-none",
                "ts": utc_now_iso(),
                "severity": "nominal",
                "surface": "lens",
                "action": "",
                "categories": [],
                "summary": "No quarantined ingress detected in the current workspace.",
            }
        ]
    top_categories = dict(
        sorted(category_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))[:4]
    )
    return {
        "quarantine_count": 0 if items[0]["id"] == "security-none" else len(items),
        "highest_severity": highest,
        "top_categories": top_categories,
        "latest": latest,
        "items": _tail(items, 5),
    }


def _summarize_runs(events: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for event in events:
        run_id = str(event.get("run_id", "")).strip()
        if not run_id:
            continue
        ts = str(event.get("ts", "")).strip()
        kind = str(event.get("kind", "")).strip()
        bucket = grouped.setdefault(
            run_id,
            {
                "run_id": run_id,
                "first_ts": ts,
                "last_ts": ts,
                "event_count": 0,
                "last_kind": "",
            },
        )
        bucket["event_count"] = int(bucket.get("event_count", 0)) + 1
        if ts and (not str(bucket.get("first_ts")) or ts < str(bucket.get("first_ts"))):
            bucket["first_ts"] = ts
        if ts and (not str(bucket.get("last_ts")) or ts >= str(bucket.get("last_ts"))):
            bucket["last_ts"] = ts
            if kind:
                bucket["last_kind"] = kind
    ordered = sorted(grouped.values(), key=lambda row: str(row.get("last_ts", "")), reverse=True)
    return ordered[: max(0, min(limit, 10))]


def _materialize_runs(workspace_root: Path) -> dict[str, Any]:
    ledger_primary = _read_jsonl(workspace_root / "runs" / "run_ledger.jsonl")
    ledger_legacy = _read_jsonl(workspace_root / "brain" / "run_ledger.jsonl")
    ledger = sorted([*ledger_primary, *ledger_legacy], key=lambda row: str(row.get("ts", "")))
    last_run = _read_json(workspace_root / "runs" / "last_run.json", {})
    if not isinstance(last_run, dict):
        last_run = {}
    return {
        "last_run": last_run,
        "recent": _summarize_runs(ledger, limit=5),
        "ledger_tail": _tail(ledger, 5),
        "ledger_count": len(ledger),
    }


def _materialize_apprenticeship(workspace_root: Path) -> dict[str, Any]:
    fs = WorkspaceFS(
        roots=[workspace_root],
        journal_path=(workspace_root / "journals" / "fs.jsonl").resolve(),
    )
    return summarize_apprenticeship(fs, limit=5)


def _materialize_fabric(workspace_root: Path) -> dict[str, Any]:
    fs = WorkspaceFS(
        roots=[workspace_root],
        journal_path=(workspace_root / "journals" / "fs.jsonl").resolve(),
    )
    return summarize_fabric(fs, refresh=False)


def _materialize_federation(workspace_root: Path) -> dict[str, Any]:
    repo_root = workspace_root.parent.resolve()
    fs = WorkspaceFS(
        roots=[workspace_root],
        journal_path=(workspace_root / "journals" / "fs.jsonl").resolve(),
    )
    topology = load_or_init_topology(fs, repo_root=repo_root, workspace_root=workspace_root)
    local_node = topology.get("local_node", {}) if isinstance(topology.get("local_node"), dict) else {}
    paired_nodes = [row for row in topology.get("paired_nodes", []) if isinstance(row, dict)]
    active_count = sum(1 for row in paired_nodes if str(row.get("status", "")).strip().lower() == "active")
    stale_count = sum(1 for row in paired_nodes if str(row.get("status", "")).strip().lower() == "stale")
    revoked_count = sum(1 for row in paired_nodes if str(row.get("status", "")).strip().lower() == "revoked")
    return {
        "local_node": local_node,
        "paired_nodes": paired_nodes,
        "paired_count": len(paired_nodes),
        "active_count": active_count,
        "stale_count": stale_count,
        "revoked_count": revoked_count,
        "summary": (
            f"Local node {str(local_node.get('label', 'Primary Node')).strip() or 'Primary Node'} "
            f"with {len(paired_nodes)} paired node(s), {stale_count} stale, {revoked_count} revoked."
        ),
        "updated_at": topology.get("updated_at"),
    }


def _materialize_swarm(workspace_root: Path) -> dict[str, Any]:
    repo_root = workspace_root.parent.resolve()
    fs = WorkspaceFS(
        roots=[workspace_root],
        journal_path=(workspace_root / "journals" / "fs.jsonl").resolve(),
    )
    state = build_swarm_state(fs, repo_root=repo_root, workspace_root=workspace_root)
    return {
        "units": state["units"],
        "delegations": state["delegations"],
        "deadletter": state["deadletter"],
        "unit_count": state["unit_count"],
        "queued_count": state["queued_count"],
        "leased_count": state["leased_count"],
        "completed_count": state["completed_count"],
        "deadletter_count": state["deadletter_count"],
        "summary": state["summary"],
        "updated_at": state["updated_at"],
    }


def _materialize_autonomy(workspace_root: Path) -> dict[str, Any]:
    budget_raw = _read_json(workspace_root / "autonomy" / "action_budget_state.json", {})
    if not isinstance(budget_raw, dict):
        budget_raw = {}
    budget_counts_raw = budget_raw.get("counts", {}) if isinstance(budget_raw.get("counts"), dict) else {}
    budget_counts: dict[str, int] = {}
    for key, value in budget_counts_raw.items():
        normalized_key = str(key).strip().lower()
        if not normalized_key:
            continue
        try:
            budget_counts[normalized_key] = max(0, int(value))
        except (TypeError, ValueError):
            continue
    top_action = max(
        budget_counts.items(),
        key=lambda item: (int(item[1]), str(item[0])),
        default=None,
    )

    last_tick = _read_json(workspace_root / "autonomy" / "last_tick.json", {})
    if not isinstance(last_tick, dict):
        last_tick = {}
    collect = last_tick.get("collect", {}) if isinstance(last_tick.get("collect"), dict) else {}
    dispatch = last_tick.get("dispatch", {}) if isinstance(last_tick.get("dispatch"), dict) else {}
    halted_reason = str(dispatch.get("halted_reason", "")).strip()

    guardrail_raw = _read_json(workspace_root / "autonomy" / "reactor_guardrail_state.json", {})
    if not isinstance(guardrail_raw, dict):
        guardrail_raw = {}
    cooldown_remaining = int(guardrail_raw.get("cooldown_remaining_ticks", 0) or 0)

    return {
        "budget": {
            "date": str(budget_raw.get("date", "")).strip(),
            "counts": budget_counts,
            "updated_at": budget_raw.get("updated_at"),
            "total_executions": sum(int(value) for value in budget_counts.values()),
            "top_action": (
                {"kind": str(top_action[0]), "count": int(top_action[1])} if top_action is not None else None
            ),
        },
        "reactor": {
            "last_tick_ts": last_tick.get("ts"),
            "run_id": str(last_tick.get("run_id", "")).strip(),
            "halted_reason": halted_reason,
            "budget_halted": halted_reason in {"dispatch_action_budget_exceeded", "dispatch_runtime_budget_exceeded"},
            "collect_queued_count": int(collect.get("queued_count", 0) or 0),
            "collect_seen_count": int(collect.get("seen_count", 0) or 0),
            "dispatch_failed_count": int(dispatch.get("failed_count", 0) or 0),
            "dispatch_retried_count": int(dispatch.get("retried_count", 0) or 0),
            "dispatch_released_count": int(dispatch.get("released_count", 0) or 0),
        },
        "guardrail": {
            "cooldown_active": cooldown_remaining > 0,
            "cooldown_remaining_ticks": cooldown_remaining,
            "escalations_count": int(guardrail_raw.get("escalations_count", 0) or 0),
            "last_reason": str(guardrail_raw.get("last_reason", "")).strip(),
            "updated_at": guardrail_raw.get("updated_at"),
        },
    }


def build_lens_snapshot(workspace_root: Path | None = None) -> dict[str, Any]:
    resolved_workspace = (workspace_root or get_workspace_root()).resolve()
    control = _control_state(resolved_workspace)
    takeover = load_takeover_state(resolved_workspace)
    missions = _materialize_missions(resolved_workspace)
    approvals = _materialize_approvals(resolved_workspace)
    inbox = _materialize_inbox(resolved_workspace)
    incidents = _materialize_incidents(resolved_workspace)
    security = _materialize_security(resolved_workspace)
    runs = _materialize_runs(resolved_workspace)
    autonomy = _materialize_autonomy(resolved_workspace)
    swarm = _materialize_swarm(resolved_workspace)
    federation = _materialize_federation(resolved_workspace)
    apprenticeship = _materialize_apprenticeship(resolved_workspace)
    fabric = _materialize_fabric(resolved_workspace)
    current_work = build_current_work(
        repo_root=resolved_workspace.parent.resolve(),
        workspace_root=resolved_workspace,
        control=control,
        missions=missions,
        approvals=approvals,
        incidents=incidents,
        inbox=inbox,
        runs=runs,
        apprenticeship=apprenticeship,
    )
    next_best_action = build_next_best_action(current_work=current_work, control=control)

    active_mission = missions["active"][0] if missions["active"] else None
    if active_mission is not None:
        objective_label = active_mission["title"]
    else:
        objective_label = "Systematically build Francis"

    return {
        "generated_at": utc_now_iso(),
        "workspace_root": str(resolved_workspace),
        "control": control,
        "takeover": takeover,
        "approvals": approvals,
        "missions": missions,
        "inbox": inbox,
        "incidents": incidents,
        "security": security,
        "runs": runs,
        "autonomy": autonomy,
        "swarm": swarm,
        "federation": federation,
        "apprenticeship": apprenticeship,
        "fabric": fabric,
        "current_work": current_work,
        "next_best_action": next_best_action,
        "objective": {
            "label": objective_label,
            "definition_of_done": (
                "Lens reflects live control, mission, approval, incident, inbox, and receipt state."
            ),
        },
    }
