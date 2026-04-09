from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable

from francis_brain.apprenticeship import summarize_apprenticeship
from francis_brain.ledger import RunLedger
from francis_brain.memory_store import load_snapshot, summarize_snapshot
from francis_brain.recall import summarize_fabric
from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS

from services.orchestrator.app.approvals_store import ApprovalSnapshot, load_approval_snapshot
from services.orchestrator.app.capability_state import build_capability_state
from services.orchestrator.app.control_state import DEFAULT_ALLOWED_APPS
from services.orchestrator.app.federation_store import load_or_init_topology
from services.orchestrator.app.managed_copy_store import build_managed_copy_state
from services.orchestrator.app.portability_store import build_portability_state
from services.orchestrator.app.runtime_hygiene import is_active_inbox_message
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
_JSONL_CACHE_LOCK = threading.Lock()
_JSONL_CACHE: dict[str, tuple[tuple[int, int] | None, tuple[dict[str, Any], ...]]] = {}


def get_workspace_root() -> Path:
    return DEFAULT_WORKSPACE_ROOT


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    resolved_path = path.resolve()
    cache_key = str(resolved_path)
    try:
        stat = resolved_path.stat()
        signature: tuple[int, int] | None = (int(stat.st_mtime_ns), int(stat.st_size))
    except Exception:
        signature = None
    with _JSONL_CACHE_LOCK:
        cached = _JSONL_CACHE.get(cache_key)
        if cached is not None and cached[0] == signature:
            return list(cached[1])
    if signature is None:
        with _JSONL_CACHE_LOCK:
            _JSONL_CACHE[cache_key] = (None, tuple())
        return []
    try:
        raw = resolved_path.read_text(encoding="utf-8")
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
    cached_rows = tuple(rows)
    with _JSONL_CACHE_LOCK:
        _JSONL_CACHE[cache_key] = (signature, cached_rows)
    return list(cached_rows)


def _tail(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    normalized_limit = max(0, min(int(limit), 50))
    return rows[-normalized_limit:] if normalized_limit else []


def _normalize_mode(raw_mode: Any) -> str:
    normalized = str(raw_mode or "").strip().lower()
    return normalized if normalized in DEFAULT_MODES else "pilot"


def _profiled_snapshot_step(
    timings: list[dict[str, object]] | None,
    name: str,
    builder: Callable[[], object],
) -> object:
    started = time.perf_counter()
    result = builder()
    if isinstance(timings, list):
        timings.append(
            {
                "name": name,
                "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
            }
        )
    return result


def _build_lens_snapshot_profile(
    *,
    phases: list[dict[str, object]],
    total_ms: float,
    approval_snapshot_loaded: bool,
) -> dict[str, Any]:
    ordered_phases = [dict(phase) for phase in phases]
    slowest = sorted(
        ordered_phases,
        key=lambda phase: float(phase.get("elapsed_ms", 0.0) or 0.0),
        reverse=True,
    )[:5]
    return {
        "surface": "lens_snapshot_profile",
        "total_ms": round(total_ms, 3),
        "phase_count": len(ordered_phases),
        "phases": ordered_phases,
        "slowest": slowest,
        "reused": {
            "approval_snapshot": not approval_snapshot_loaded,
        },
    }


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

def _materialize_approvals(
    workspace_root: Path,
    *,
    approval_snapshot: ApprovalSnapshot | None = None,
) -> dict[str, Any]:
    fs = WorkspaceFS(
        roots=[workspace_root],
        journal_path=(workspace_root / "journals" / "fs.jsonl").resolve(),
    )
    snapshot = approval_snapshot if isinstance(approval_snapshot, ApprovalSnapshot) else load_approval_snapshot(fs)
    materialized = [
        {
            "id": str(row.get("id", "")).strip(),
            "ts": row.get("ts"),
            "action": str(row.get("action", "")).strip(),
            "reason": str(row.get("reason", "")).strip(),
            "requested_by": str(row.get("requested_by", "")).strip(),
            "status": str(row.get("status", "")).strip().lower() or "pending",
        }
        for row in snapshot.approvals
        if isinstance(row, dict)
    ]
    pending = [row for row in materialized if row["status"] == "pending"]
    pending.sort(key=lambda row: str(row.get("ts", "")))
    return {
        "count": len(materialized),
        "pending_count": snapshot.pending_count,
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
        if not is_active_inbox_message(row):
            continue
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


def _merge_run_summaries(*summary_lists: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for rows in summary_lists:
        for row in rows:
            if not isinstance(row, dict):
                continue
            run_id = str(row.get("run_id", "")).strip()
            if not run_id:
                continue
            bucket = grouped.setdefault(
                run_id,
                {
                    "run_id": run_id,
                    "first_ts": str(row.get("first_ts", "")).strip(),
                    "last_ts": str(row.get("last_ts", "")).strip(),
                    "event_count": 0,
                    "last_kind": str(row.get("last_kind", "")).strip(),
                },
            )
            event_count = int(row.get("event_count", 0) or 0)
            bucket["event_count"] = max(0, int(bucket.get("event_count", 0) or 0)) + event_count
            first_ts = str(row.get("first_ts", "")).strip()
            if first_ts and (
                not str(bucket.get("first_ts", "")).strip() or first_ts < str(bucket.get("first_ts", "")).strip()
            ):
                bucket["first_ts"] = first_ts
            last_ts = str(row.get("last_ts", "")).strip()
            if last_ts and (
                not str(bucket.get("last_ts", "")).strip() or last_ts >= str(bucket.get("last_ts", "")).strip()
            ):
                bucket["last_ts"] = last_ts
                if str(row.get("last_kind", "")).strip():
                    bucket["last_kind"] = str(row.get("last_kind", "")).strip()
    ordered = sorted(grouped.values(), key=lambda row: str(row.get("last_ts", "")), reverse=True)
    return ordered[: max(0, min(limit, 10))]


def _materialize_runs(workspace_root: Path) -> dict[str, Any]:
    fs = WorkspaceFS(
        roots=[workspace_root],
        journal_path=(workspace_root / "journals" / "fs.jsonl").resolve(),
    )
    ledger_primary = RunLedger(fs, rel_path="runs/run_ledger.jsonl").summary(recent_limit=10, tail_limit=5)
    ledger_legacy = _read_jsonl(workspace_root / "brain" / "run_ledger.jsonl")
    last_run = _read_json(workspace_root / "runs" / "last_run.json", {})
    if not isinstance(last_run, dict):
        last_run = {}
    legacy_recent = _summarize_runs(ledger_legacy, limit=10)
    merged_recent = _merge_run_summaries(
        [row for row in ledger_primary.get("recent", []) if isinstance(row, dict)],
        legacy_recent,
        limit=5,
    )
    merged_tail = sorted(
        [
            *[row for row in ledger_primary.get("tail", []) if isinstance(row, dict)],
            *_tail(ledger_legacy, 5),
        ],
        key=lambda row: str(row.get("ts", "")),
    )
    return {
        "last_run": last_run,
        "recent": merged_recent,
        "ledger_tail": _tail(merged_tail, 5),
        "ledger_count": int(ledger_primary.get("count", 0) or 0) + len(ledger_legacy),
    }


def _materialize_apprenticeship(workspace_root: Path) -> dict[str, Any]:
    fs = WorkspaceFS(
        roots=[workspace_root],
        journal_path=(workspace_root / "journals" / "fs.jsonl").resolve(),
    )
    return summarize_apprenticeship(fs, limit=5)


def _deferred_fabric_summary() -> dict[str, Any]:
    summary = summarize_snapshot(None)
    summary["pending"] = True
    summary["note"] = "Fabric summary is deferred until a cached snapshot exists or a full fabric request is made."
    summary["calibration"] = {
        "confidence_counts": {"confirmed": 0, "likely": 0, "uncertain": 0},
        "done_claim_ready_count": 0,
        "stale_current_state_count": 0,
        "local_provenance_count": 0,
        "anchored_provenance_count": 0,
    }
    return summary


def _materialize_fabric(workspace_root: Path) -> dict[str, Any]:
    fs = WorkspaceFS(
        roots=[workspace_root],
        journal_path=(workspace_root / "journals" / "fs.jsonl").resolve(),
    )
    if load_snapshot(fs) is None:
        return _deferred_fabric_summary()
    return summarize_fabric(fs, refresh=False)


def _materialize_federation(
    workspace_root: Path,
    *,
    approval_snapshot: ApprovalSnapshot | None = None,
) -> dict[str, Any]:
    repo_root = workspace_root.parent.resolve()
    fs = WorkspaceFS(
        roots=[workspace_root],
        journal_path=(workspace_root / "journals" / "fs.jsonl").resolve(),
    )
    snapshot = approval_snapshot if isinstance(approval_snapshot, ApprovalSnapshot) else load_approval_snapshot(fs)
    topology = load_or_init_topology(fs, repo_root=repo_root, workspace_root=workspace_root)
    local_node = topology.get("local_node", {}) if isinstance(topology.get("local_node"), dict) else {}
    paired_nodes = [row for row in topology.get("paired_nodes", []) if isinstance(row, dict)]
    active_count = sum(1 for row in paired_nodes if str(row.get("status", "")).strip().lower() == "active")
    stale_count = sum(1 for row in paired_nodes if str(row.get("status", "")).strip().lower() == "stale")
    revoked_count = sum(1 for row in paired_nodes if str(row.get("status", "")).strip().lower() == "revoked")
    remote_pending_preview = [
        {
            "id": str(row.get("id", "")).strip(),
            "action": str(row.get("action", "")).strip(),
            "reason": str(row.get("reason", "")).strip(),
            "requested_by": str(row.get("requested_by", "")).strip(),
            "run_id": str(row.get("run_id", "")).strip(),
            "status": str(row.get("status", "")).strip(),
        }
        for row in snapshot.approvals
        if isinstance(row, dict)
        and str(row.get("status", "")).strip().lower() == "pending"
    ]
    return {
        "local_node": local_node,
        "paired_nodes": paired_nodes,
        "paired_count": len(paired_nodes),
        "active_count": active_count,
        "stale_count": stale_count,
        "revoked_count": revoked_count,
        "remote_pending_count": snapshot.pending_count,
        "remote_pending_preview": _tail(remote_pending_preview, 3),
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


def _materialize_managed_copies(workspace_root: Path) -> dict[str, Any]:
    fs = WorkspaceFS(
        roots=[workspace_root],
        journal_path=(workspace_root / "journals" / "fs.jsonl").resolve(),
    )
    state = build_managed_copy_state(fs)
    return {
        "copies": state["copies"],
        "deltas": state["deltas"],
        "copy_count": state["copy_count"],
        "active_count": state["active_count"],
        "quarantined_count": state["quarantined_count"],
        "replaced_count": state["replaced_count"],
        "delta_count": state["delta_count"],
        "materialized_count": state["materialized_count"],
        "unmaterialized_count": state["unmaterialized_count"],
        "summary": state["summary"],
        "updated_at": state.get("updated_at"),
    }


def _materialize_portability(
    workspace_root: Path,
    *,
    control: dict[str, Any] | None = None,
    missions: dict[str, Any] | None = None,
    approvals: dict[str, Any] | None = None,
    federation: dict[str, Any] | None = None,
    managed_copies: dict[str, Any] | None = None,
    swarm: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repo_root = workspace_root.parent.resolve()
    fs = WorkspaceFS(
        roots=[workspace_root],
        journal_path=(workspace_root / "journals" / "fs.jsonl").resolve(),
    )
    continuity: dict[str, Any] | None = None
    if (
        isinstance(control, dict)
        and isinstance(missions, dict)
        and isinstance(approvals, dict)
        and isinstance(federation, dict)
        and isinstance(managed_copies, dict)
        and isinstance(swarm, dict)
    ):
        catalog_doc = _read_json(workspace_root / "forge" / "catalog.json", {"entries": []})
        catalog_entries = catalog_doc.get("entries", []) if isinstance(catalog_doc, dict) else []
        continuity = {
            "mode": str(control.get("mode", "assist")).strip().lower() or "assist",
            "kill_switch": bool(control.get("kill_switch", False)),
            "mission_count": (
                int(missions.get("active_count", 0) or 0)
                + int(missions.get("backlog_count", 0) or 0)
                + int(missions.get("completed_count", 0) or 0)
            ),
            "pending_approvals": int(approvals.get("pending_count", 0) or 0),
            "capability_count": len(catalog_entries) if isinstance(catalog_entries, list) else 0,
            "paired_node_count": int(
                federation.get("paired_count", len(federation.get("paired_nodes", [])))
                if isinstance(federation.get("paired_nodes", []), list)
                else federation.get("paired_count", 0)
            ),
            "managed_copy_count": int(managed_copies.get("copy_count", 0) or 0),
            "swarm_unit_count": int(swarm.get("unit_count", 0) or 0),
        }
    return build_portability_state(
        fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
        continuity=continuity,
    )


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


def build_lens_snapshot(
    workspace_root: Path | None = None,
    *,
    approval_snapshot: ApprovalSnapshot | None = None,
    capability_state: dict[str, Any] | None = None,
    profile: bool = False,
) -> dict[str, Any]:
    build_started = time.perf_counter()
    timings: list[dict[str, object]] | None = [] if profile else None
    resolved_workspace = (workspace_root or get_workspace_root()).resolve()
    approval_fs = WorkspaceFS(
        roots=[resolved_workspace],
        journal_path=(resolved_workspace / "journals" / "fs.jsonl").resolve(),
    )
    approval_snapshot_loaded = False
    if isinstance(approval_snapshot, ApprovalSnapshot):
        snapshot = approval_snapshot
    else:
        snapshot = _profiled_snapshot_step(
            timings,
            "approval_snapshot",
            lambda: load_approval_snapshot(approval_fs),
        )
        approval_snapshot_loaded = True
    control = _profiled_snapshot_step(timings, "control", lambda: _control_state(resolved_workspace))
    takeover = _profiled_snapshot_step(timings, "takeover", lambda: load_takeover_state(resolved_workspace))
    missions = _profiled_snapshot_step(timings, "missions", lambda: _materialize_missions(resolved_workspace))
    approvals = _profiled_snapshot_step(
        timings,
        "approvals",
        lambda: _materialize_approvals(resolved_workspace, approval_snapshot=snapshot),
    )
    inbox = _profiled_snapshot_step(timings, "inbox", lambda: _materialize_inbox(resolved_workspace))
    incidents = _profiled_snapshot_step(timings, "incidents", lambda: _materialize_incidents(resolved_workspace))
    security = _profiled_snapshot_step(timings, "security", lambda: _materialize_security(resolved_workspace))
    runs = _profiled_snapshot_step(timings, "runs", lambda: _materialize_runs(resolved_workspace))
    autonomy = _profiled_snapshot_step(timings, "autonomy", lambda: _materialize_autonomy(resolved_workspace))
    swarm = _profiled_snapshot_step(timings, "swarm", lambda: _materialize_swarm(resolved_workspace))
    federation = _profiled_snapshot_step(
        timings,
        "federation",
        lambda: _materialize_federation(resolved_workspace, approval_snapshot=snapshot),
    )
    managed_copies = _profiled_snapshot_step(
        timings,
        "managed_copies",
        lambda: _materialize_managed_copies(resolved_workspace),
    )
    portability = _profiled_snapshot_step(
        timings,
        "portability",
        lambda: _materialize_portability(
            resolved_workspace,
            control=control,
            missions=missions,
            approvals=approvals,
            federation=federation,
            managed_copies=managed_copies,
            swarm=swarm,
        ),
    )
    apprenticeship = _profiled_snapshot_step(
        timings,
        "apprenticeship",
        lambda: _materialize_apprenticeship(resolved_workspace),
    )
    fabric = _profiled_snapshot_step(timings, "fabric", lambda: _materialize_fabric(resolved_workspace))
    resolved_capability_state = capability_state
    if not isinstance(resolved_capability_state, dict):
        resolved_capability_state = _profiled_snapshot_step(
            timings,
            "capability_state",
            lambda: build_capability_state(resolved_workspace, approval_snapshot=snapshot),
        )
    current_work = _profiled_snapshot_step(
        timings,
        "current_work",
        lambda: build_current_work(
            repo_root=resolved_workspace.parent.resolve(),
            workspace_root=resolved_workspace,
            control=control,
            missions=missions,
            approvals=approvals,
            incidents=incidents,
            inbox=inbox,
            runs=runs,
            apprenticeship=apprenticeship,
            approval_snapshot=snapshot,
            capability_state=resolved_capability_state,
        ),
    )
    next_best_action = _profiled_snapshot_step(
        timings,
        "next_best_action",
        lambda: build_next_best_action(current_work=current_work, control=control),
    )

    active_mission = missions["active"][0] if missions["active"] else None
    if active_mission is not None:
        objective_label = active_mission["title"]
    else:
        objective_label = "Systematically build Francis"

    payload = {
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
        "managed_copies": managed_copies,
        "portability": portability,
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
    if isinstance(timings, list):
        payload["build_profile"] = _build_lens_snapshot_profile(
            phases=timings,
            total_ms=(time.perf_counter() - build_started) * 1000.0,
            approval_snapshot_loaded=approval_snapshot_loaded,
        )
    return payload
