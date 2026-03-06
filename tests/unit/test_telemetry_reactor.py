from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from francis_core.workspace_fs import WorkspaceFS
from services.orchestrator.app.autonomy.decision_engine import build_plan
from services.orchestrator.app.autonomy.event_reactor import collect_events


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = ""
    if rows:
        content = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    path.write_text(content, encoding="utf-8")


def test_event_reactor_surfaces_telemetry_signal_fields(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    fs = WorkspaceFS(roots=[root], journal_path=root / "journals" / "fs.jsonl")
    now_iso = datetime.now(timezone.utc).isoformat()
    _write_jsonl(
        root / "telemetry" / "events.jsonl",
        [
            {
                "id": "e-1",
                "ts": now_iso,
                "ingested_at": now_iso,
                "run_id": "r-1",
                "kind": "telemetry.event",
                "stream": "terminal",
                "source": "pytest",
                "severity": "error",
                "text": "build failed",
                "fields": {},
            },
            {
                "id": "e-2",
                "ts": now_iso,
                "ingested_at": now_iso,
                "run_id": "r-2",
                "kind": "telemetry.event",
                "stream": "dev_server",
                "source": "pytest",
                "severity": "critical",
                "text": "service down",
                "fields": {},
            },
            {
                "id": "e-3",
                "ts": "2000-01-01T00:00:00+00:00",
                "ingested_at": now_iso,
                "run_id": "r-3",
                "kind": "telemetry.event",
                "stream": "terminal",
                "source": "pytest",
                "severity": "warn",
                "text": "very old",
                "fields": {},
            },
        ],
    )

    state = collect_events(fs, telemetry_horizon_hours=24)
    assert state["telemetry_event_count_horizon"] == 2
    assert state["telemetry_error_count_horizon"] == 1
    assert state["telemetry_critical_count_horizon"] == 1
    assert any(event.get("type") == "telemetry.errors_present" for event in state.get("events", []))
    assert any(event.get("type") == "telemetry.critical_present" for event in state.get("events", []))


def test_decision_engine_uses_telemetry_to_trigger_scan_and_forge() -> None:
    event_state = {
        "observer_scan_due": False,
        "critical_incident_count": 0,
        "telemetry_error_count_horizon": 4,
        "telemetry_critical_count_horizon": 0,
        "telemetry_streams_top": [{"key": "terminal", "count": 4}],
        "deadletter_count": 0,
        "worker_queue_due_count": 0,
        "worker_leased_expired_count": 0,
        "active_mission_count": 1,
    }
    intent_state = {"intent_count": 0, "intents": []}

    plan = build_plan(
        event_state=event_state,
        intent_state=intent_state,
        max_actions=5,
        allow_medium=False,
        allow_high=False,
    )
    kinds = [str(item.get("kind", "")) for item in plan.get("candidate_actions", [])]
    assert "observer.scan" in kinds
    assert "forge.propose" in kinds
