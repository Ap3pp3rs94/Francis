from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from francis_brain.ledger import RunLedger
from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS

from .action_budget import (
    check_action_budget,
    load_state as load_budget_state,
    register_action_execution,
    save_state as save_budget_state,
)
from .decision_engine import build_plan
from .event_reactor import collect_events
from .executor import execute_action
from .intent_engine import collect_intents


def _append_jsonl(fs: WorkspaceFS, rel_path: str, item: dict[str, Any]) -> None:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        raw = ""
    if raw and not raw.endswith("\n"):
        raw += "\n"
    fs.write_text(rel_path, raw + json.dumps(item, ensure_ascii=False) + "\n")


def _write_last_run(fs: WorkspaceFS, payload: dict[str, Any]) -> None:
    fs.write_text("runs/last_run.json", json.dumps(payload, ensure_ascii=False, indent=2))


def run_cycle(
    *,
    run_id: str,
    trace_id: str | None = None,
    workspace_root: Path,
    repo_root: Path,
    max_actions: int = 2,
    max_runtime_seconds: int = 10,
    allow_medium: bool = False,
    allow_high: bool = False,
    stop_on_critical: bool = True,
) -> dict[str, Any]:
    fs = WorkspaceFS(
        roots=[workspace_root],
        journal_path=(workspace_root / "journals" / "fs.jsonl").resolve(),
    )
    ledger = RunLedger(fs, rel_path="runs/run_ledger.jsonl")

    started_at = utc_now_iso()
    start_monotonic = time.monotonic()
    normalized_trace_id = str(trace_id or "").strip() or run_id

    event_state = collect_events(fs)
    intent_state = collect_intents(fs)
    plan = build_plan(
        event_state=event_state,
        intent_state=intent_state,
        max_actions=max_actions,
        allow_medium=allow_medium,
        allow_high=allow_high,
    )
    critical_at_start = int(event_state.get("critical_incident_count", 0)) > 0
    budget_state = load_budget_state(fs)
    selected_actions: list[dict[str, Any]] = []
    budget_blocked_actions: list[dict[str, Any]] = []
    for action in plan.get("selected_actions", []):
        allowed, reason, action_key = check_action_budget(action, state=budget_state)
        if not allowed:
            budget_blocked_actions.append(
                {
                    **action,
                    "allowed": False,
                    "policy_reason": reason,
                    "blocked_by": "action_budget",
                    "action_key": action_key,
                }
            )
            continue
        selected_actions.append(action)

    _append_jsonl(
        fs,
        "journals/decisions.jsonl",
        {
            "id": str(uuid4()),
            "ts": started_at,
            "run_id": run_id,
            "trace_id": normalized_trace_id,
            "kind": "autonomy.plan",
            "event_state": event_state,
            "intent_count": intent_state.get("intent_count", 0),
            "candidate_count": len(plan.get("candidate_actions", [])),
            "selected_count": len(selected_actions),
            "blocked_count": len(plan.get("blocked_actions", [])) + len(budget_blocked_actions),
            "budget_blocked_count": len(budget_blocked_actions),
        },
    )

    executed_actions: list[dict[str, Any]] = []
    halted_after_critical = False
    halted_reason = "completed"

    for action in selected_actions:
        elapsed = time.monotonic() - start_monotonic
        if elapsed >= max_runtime_seconds:
            halted_reason = "runtime_budget_exceeded"
            break

        result = execute_action(
            action=action,
            run_id=run_id,
            trace_id=normalized_trace_id,
            fs=fs,
            workspace_root=workspace_root,
            repo_root=repo_root,
        )
        executed_actions.append(result)

        _append_jsonl(
            fs,
            "logs/francis.log.jsonl",
            {
                "id": str(uuid4()),
                "ts": utc_now_iso(),
                "run_id": run_id,
                "trace_id": normalized_trace_id,
                "kind": "autonomy.action",
                "action": action,
                "result": result,
            },
        )

        ledger.append(
            run_id=run_id,
            kind="autonomy.action",
            summary={
                "action_kind": action.get("kind"),
                "ok": result.get("ok"),
                "trace_id": normalized_trace_id,
            },
        )
        budget_state = register_action_execution(budget_state, action=action)

        if (
            stop_on_critical
            and action.get("kind") == "observer.scan"
            and (
                critical_at_start
                or (
                    isinstance(result.get("result"), dict)
                    and isinstance(result["result"].get("score"), dict)
                    and str(result["result"]["score"].get("level")) == "critical"
                )
            )
        ):
            halted_after_critical = True
            halted_reason = "critical_anomaly"
            break

    completed_at = utc_now_iso()
    duration_ms = int((time.monotonic() - start_monotonic) * 1000)
    budget_state = save_budget_state(fs, budget_state)
    summary = {
        "status": "ok",
        "run_id": run_id,
        "trace_id": normalized_trace_id,
        "ts": completed_at,
        "started_at": started_at,
        "duration_ms": duration_ms,
        "event_state": event_state,
        "intent_state": intent_state,
        "candidate_actions": plan.get("candidate_actions", []),
        "blocked_actions": [*plan.get("blocked_actions", []), *budget_blocked_actions],
        "selected_actions": selected_actions,
        "executed_actions": executed_actions,
        "budget_blocked_count": len(budget_blocked_actions),
        "action_budget_state": budget_state,
        "halted_after_critical": halted_after_critical,
        "halted_reason": halted_reason,
        "config": {
            "max_actions": max_actions,
            "max_runtime_seconds": max_runtime_seconds,
            "allow_medium": allow_medium,
            "allow_high": allow_high,
            "stop_on_critical": stop_on_critical,
        },
    }

    _write_last_run(fs, summary)
    ledger.append(
        run_id=run_id,
        kind="autonomy.cycle",
        summary={
            "executed_count": len(executed_actions),
            "blocked_count": len(summary["blocked_actions"]),
            "halted_reason": halted_reason,
            "trace_id": normalized_trace_id,
        },
    )
    return summary
