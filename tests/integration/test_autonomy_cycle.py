from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from apps.api.main import app


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2] / "workspace"


def _read_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _today_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _budget_path() -> Path:
    return _workspace_root() / "autonomy" / "action_budget_state.json"


def _clear_budget_state() -> None:
    path = _budget_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    now_iso = datetime.now(timezone.utc).isoformat()
    path.write_text(
        json.dumps(
            {
                "date": _today_date(),
                "counts": {},
                "last_executed_at": {},
                "updated_at": now_iso,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_autonomy_cycle_writes_last_run() -> None:
    _clear_budget_state()
    c = TestClient(app)

    create = c.post(
        "/missions",
        json={"title": f"Auto-{uuid4()}", "objective": "Autonomy run", "steps": ["s1"]},
    )
    assert create.status_code == 200

    cycle = c.post("/autonomy/cycle", json={"max_actions": 3, "allow_medium": True})
    assert cycle.status_code == 200
    payload = cycle.json()
    assert payload["status"] == "ok"
    assert isinstance(payload.get("candidate_actions"), list)
    assert isinstance(payload.get("executed_actions"), list)
    assert len(payload["executed_actions"]) >= 1

    last_run = _read_json(_workspace_root() / "runs" / "last_run.json", {})
    assert isinstance(last_run, dict)
    assert last_run.get("run_id") == payload.get("run_id")


def test_autonomy_blocks_medium_without_flag() -> None:
    _clear_budget_state()
    c = TestClient(app)
    create = c.post(
        "/missions",
        json={"title": f"Blocked-{uuid4()}", "objective": "Medium risk block", "steps": ["s1"]},
    )
    assert create.status_code == 200

    cycle = c.post("/autonomy/cycle", json={"max_actions": 3, "allow_medium": False})
    assert cycle.status_code == 200
    payload = cycle.json()
    blocked = payload.get("blocked_actions", [])
    assert any(
        action.get("kind") == "mission.tick" and "medium risk disabled" in str(action.get("policy_reason", ""))
        for action in blocked
    )


def test_autonomy_halts_on_critical_observer_result() -> None:
    _clear_budget_state()
    workspace = _workspace_root()
    incidents = workspace / "incidents" / "incidents.jsonl"
    incidents.parent.mkdir(parents=True, exist_ok=True)
    with incidents.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "id": str(uuid4()),
                    "ts": "2026-01-01T00:00:00+00:00",
                    "run_id": str(uuid4()),
                    "severity": "critical",
                    "kind": "test.critical",
                    "message": "critical incident injected for autonomy halt test",
                    "status": "open",
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    # Force observer scan due.
    (workspace / "runs" / "last_run.json").write_text(
        json.dumps({"ts": "2000-01-01T00:00:00+00:00"}, ensure_ascii=False),
        encoding="utf-8",
    )

    c = TestClient(app)
    cycle = c.post(
        "/autonomy/cycle",
        json={"max_actions": 3, "allow_medium": True, "stop_on_critical": True},
    )
    assert cycle.status_code == 200
    payload = cycle.json()
    assert payload["halted_after_critical"] is True
    assert payload["halted_reason"] == "critical_anomaly"


def test_autonomy_can_select_worker_cycle_when_queue_due() -> None:
    _clear_budget_state()
    workspace = _workspace_root()
    now_iso = "2026-01-01T00:00:00+00:00"
    (workspace / "runs" / "last_run.json").write_text(
        json.dumps({"ts": now_iso}, ensure_ascii=False),
        encoding="utf-8",
    )

    jobs_path = workspace / "queue" / "jobs.jsonl"
    existing = jobs_path.read_text(encoding="utf-8") if jobs_path.exists() else ""
    try:
        jobs_path.parent.mkdir(parents=True, exist_ok=True)
        queued_job = {
            "id": str(uuid4()),
            "ts": "2026-01-01T00:00:00+00:00",
            "run_id": str(uuid4()),
            "action": "forge.propose",
            "priority": "high",
            "status": "queued",
            "attempts": 0,
            "context": {"deadletter_count": 0, "open_incident_count": 0, "active_mission_count": 0},
        }
        jobs_path.write_text(json.dumps(queued_job, ensure_ascii=False) + "\n", encoding="utf-8")

        c = TestClient(app)
        cycle = c.post(
            "/autonomy/cycle",
            json={
                "max_actions": 10,
                "max_runtime_seconds": 120,
                "allow_medium": True,
                "stop_on_critical": False,
            },
        )
        assert cycle.status_code == 200
        payload = cycle.json()
        candidate_kinds = [item.get("kind") for item in payload.get("candidate_actions", [])]
        assert "worker.cycle" in candidate_kinds
        selected_kinds = [item.get("kind") for item in payload.get("selected_actions", [])]
        assert "worker.cycle" in selected_kinds
        executed_kinds = [item.get("kind") for item in payload.get("executed_actions", [])]
        assert "worker.cycle" in executed_kinds
    finally:
        jobs_path.write_text(existing, encoding="utf-8")


def test_autonomy_can_select_worker_cycle_when_leases_expired() -> None:
    _clear_budget_state()
    workspace = _workspace_root()
    now_iso = "2026-01-01T00:00:00+00:00"
    (workspace / "runs" / "last_run.json").write_text(
        json.dumps({"ts": now_iso}, ensure_ascii=False),
        encoding="utf-8",
    )

    jobs_path = workspace / "queue" / "jobs.jsonl"
    existing = jobs_path.read_text(encoding="utf-8") if jobs_path.exists() else ""
    try:
        jobs_path.parent.mkdir(parents=True, exist_ok=True)
        leased_job = {
            "id": str(uuid4()),
            "ts": "2026-01-01T00:00:00+00:00",
            "run_id": str(uuid4()),
            "action": "forge.propose",
            "priority": "high",
            "status": "leased",
            "lease_owner": "stale-worker",
            "lease_key": str(uuid4()),
            "lease_expires_at": "2020-01-01T00:00:00+00:00",
            "attempts": 0,
            "context": {"deadletter_count": 0, "open_incident_count": 0, "active_mission_count": 0},
        }
        jobs_path.write_text(json.dumps(leased_job, ensure_ascii=False) + "\n", encoding="utf-8")

        c = TestClient(app)
        cycle = c.post(
            "/autonomy/cycle",
            json={
                "max_actions": 10,
                "max_runtime_seconds": 120,
                "allow_medium": True,
                "stop_on_critical": False,
            },
        )
        assert cycle.status_code == 200
        payload = cycle.json()
        candidate_kinds = [item.get("kind") for item in payload.get("candidate_actions", [])]
        assert "worker.cycle" in candidate_kinds
        executed_kinds = [item.get("kind") for item in payload.get("executed_actions", [])]
        assert any(kind in {"worker.cycle", "worker.recover_leases"} for kind in executed_kinds)
    finally:
        jobs_path.write_text(existing, encoding="utf-8")


def test_autonomy_budget_daily_cap_blocks_worker_cycle() -> None:
    workspace = _workspace_root()
    jobs_path = workspace / "queue" / "jobs.jsonl"
    budget_path = workspace / "autonomy" / "action_budget_state.json"
    existing_jobs = jobs_path.read_text(encoding="utf-8") if jobs_path.exists() else ""
    existing_budget = budget_path.read_text(encoding="utf-8") if budget_path.exists() else ""
    try:
        jobs_path.parent.mkdir(parents=True, exist_ok=True)
        budget_path.parent.mkdir(parents=True, exist_ok=True)
        jobs_path.write_text(
            json.dumps(
                {
                    "id": str(uuid4()),
                    "ts": "2026-01-01T00:00:00+00:00",
                    "run_id": str(uuid4()),
                    "action": "forge.propose",
                    "priority": "high",
                    "status": "queued",
                    "attempts": 0,
                    "context": {"deadletter_count": 0, "open_incident_count": 0, "active_mission_count": 0},
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        budget_path.write_text(
            json.dumps(
                {
                    "date": _today_date(),
                    "counts": {"worker.cycle": 500},
                    "last_executed_at": {},
                    "updated_at": "2026-01-01T00:00:00+00:00",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        c = TestClient(app)
        cycle = c.post("/autonomy/cycle", json={"max_actions": 3, "allow_medium": True, "stop_on_critical": False})
        assert cycle.status_code == 200
        payload = cycle.json()
        blocked = payload.get("blocked_actions", [])
        assert any(
            item.get("kind") == "worker.cycle" and item.get("blocked_by") == "action_budget" for item in blocked
        )
    finally:
        jobs_path.write_text(existing_jobs, encoding="utf-8")
        budget_path.write_text(existing_budget, encoding="utf-8")


def test_autonomy_budget_cooldown_blocks_observer_scan() -> None:
    workspace = _workspace_root()
    budget_path = workspace / "autonomy" / "action_budget_state.json"
    last_run_path = workspace / "runs" / "last_run.json"
    existing_budget = budget_path.read_text(encoding="utf-8") if budget_path.exists() else ""
    existing_last_run = last_run_path.read_text(encoding="utf-8") if last_run_path.exists() else ""
    try:
        budget_path.parent.mkdir(parents=True, exist_ok=True)
        last_run_path.parent.mkdir(parents=True, exist_ok=True)
        last_run_path.write_text(
            json.dumps({"ts": "2000-01-01T00:00:00+00:00"}, ensure_ascii=False),
            encoding="utf-8",
        )
        now_iso = datetime.now(timezone.utc).isoformat()
        budget_path.write_text(
            json.dumps(
                {
                    "date": _today_date(),
                    "counts": {"observer.scan": 1},
                    "last_executed_at": {"observer.scan": now_iso},
                    "updated_at": now_iso,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        c = TestClient(app)
        cycle = c.post("/autonomy/cycle", json={"max_actions": 2, "allow_medium": False, "stop_on_critical": False})
        assert cycle.status_code == 200
        payload = cycle.json()
        blocked = payload.get("blocked_actions", [])
        assert any(
            item.get("kind") == "observer.scan" and item.get("blocked_by") == "action_budget" for item in blocked
        )
        assert payload.get("budget_blocked_count", 0) >= 1
    finally:
        budget_path.write_text(existing_budget, encoding="utf-8")
        last_run_path.write_text(existing_last_run, encoding="utf-8")
