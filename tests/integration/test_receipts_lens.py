from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from apps.api.main import app


def test_receipts_and_run_lookup() -> None:
    c = TestClient(app)

    mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
    assert mode.status_code == 200

    create = c.post(
        "/missions",
        json={"title": f"Receipt-{uuid4()}", "objective": "Receipts", "steps": ["s1"]},
    )
    assert create.status_code == 200
    run_id = create.json()["run_id"]

    latest = c.get("/receipts/latest")
    assert latest.status_code == 200
    latest_payload = latest.json()
    assert latest_payload["status"] == "ok"
    receipts = latest_payload["receipts"]
    assert "ledger" in receipts
    assert "decisions" in receipts
    assert "logs" in receipts

    run = c.get(f"/runs/{run_id}")
    assert run.status_code == 200
    run_payload = run.json()
    assert run_payload["status"] == "ok"
    assert run_payload["run_id"] == run_id
    assert run_payload["count"] >= 1


def test_lens_state_and_actions() -> None:
    c = TestClient(app)
    mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
    assert mode.status_code == 200

    state = c.get("/lens/state")
    assert state.status_code == 200
    state_payload = state.json()
    assert state_payload["status"] == "ok"
    assert "mode" in state_payload
    assert "scope" in state_payload
    assert "intent_state" in state_payload
    assert "event_state" in state_payload

    actions = c.get("/lens/actions")
    assert actions.status_code == 200
    actions_payload = actions.json()
    assert actions_payload["status"] == "ok"
    assert isinstance(actions_payload.get("action_chips"), list)
    assert "selected_actions" in actions_payload
    assert "blocked_actions" in actions_payload


def test_lens_surfaces_worker_queue_signals() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    jobs_path = workspace / "queue" / "jobs.jsonl"
    existing = jobs_path.read_text(encoding="utf-8") if jobs_path.exists() else ""
    try:
        jobs_path.parent.mkdir(parents=True, exist_ok=True)
        queued = {
            "id": str(uuid4()),
            "ts": "2026-01-01T00:00:00+00:00",
            "run_id": str(uuid4()),
            "action": "forge.propose",
            "status": "queued",
            "priority": "high",
            "attempts": 0,
        }
        jobs_path.write_text(json.dumps(queued, ensure_ascii=False) + "\n", encoding="utf-8")

        c = TestClient(app)
        mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
        assert mode.status_code == 200

        state = c.get("/lens/state")
        assert state.status_code == 200
        payload = state.json()
        blockers = payload.get("blockers", {})
        assert int(blockers.get("worker_queue_due", 0)) >= 1

        actions = c.get("/lens/actions")
        assert actions.status_code == 200
        action_chips = actions.json().get("action_chips", [])
        assert any(chip.get("kind") == "worker.cycle" for chip in action_chips)
    finally:
        jobs_path.write_text(existing, encoding="utf-8")


def test_lens_surfaces_worker_lease_pressure() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    jobs_path = workspace / "queue" / "jobs.jsonl"
    existing = jobs_path.read_text(encoding="utf-8") if jobs_path.exists() else ""
    try:
        jobs_path.parent.mkdir(parents=True, exist_ok=True)
        leased = {
            "id": str(uuid4()),
            "ts": "2026-01-01T00:00:00+00:00",
            "run_id": str(uuid4()),
            "action": "forge.propose",
            "status": "leased",
            "lease_owner": "worker-a",
            "lease_key": str(uuid4()),
            "lease_expires_at": "2020-01-01T00:00:00+00:00",
            "attempts": 0,
        }
        jobs_path.write_text(json.dumps(leased, ensure_ascii=False) + "\n", encoding="utf-8")

        c = TestClient(app)
        mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
        assert mode.status_code == 200

        state = c.get("/lens/state")
        assert state.status_code == 200
        blockers = state.json().get("blockers", {})
        assert int(blockers.get("worker_leased", 0)) >= 1
        assert int(blockers.get("worker_leased_expired", 0)) >= 1

        actions = c.get("/lens/actions")
        assert actions.status_code == 200
        actions_payload = actions.json()
        selected = actions_payload.get("selected_actions", [])
        blocked = actions_payload.get("blocked_actions", [])
        all_kinds = [item.get("kind") for item in selected] + [item.get("kind") for item in blocked]
        assert "worker.cycle" in all_kinds
    finally:
        jobs_path.write_text(existing, encoding="utf-8")


def test_lens_actions_reflect_action_budget_blocks() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    jobs_path = workspace / "queue" / "jobs.jsonl"
    budget_path = workspace / "autonomy" / "action_budget_state.json"
    jobs_before = jobs_path.read_text(encoding="utf-8") if jobs_path.exists() else ""
    budget_before = budget_path.read_text(encoding="utf-8") if budget_path.exists() else ""
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
                    "status": "queued",
                    "priority": "high",
                    "attempts": 0,
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        budget_path.write_text(
            json.dumps(
                {
                    "date": datetime.now(timezone.utc).date().isoformat(),
                    "counts": {"worker.cycle": 500},
                    "last_executed_at": {},
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        c = TestClient(app)
        mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
        assert mode.status_code == 200
        actions = c.get("/lens/actions")
        assert actions.status_code == 200
        chips = actions.json().get("action_chips", [])
        worker_chip = [chip for chip in chips if chip.get("kind") == "worker.cycle"]
        assert worker_chip
        assert worker_chip[0].get("enabled") is False
        assert "daily cap reached" in str(worker_chip[0].get("policy_reason", ""))
    finally:
        jobs_path.write_text(jobs_before, encoding="utf-8")
        budget_path.write_text(budget_before, encoding="utf-8")


def test_lens_worker_chip_includes_lease_telemetry() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    jobs_path = workspace / "queue" / "jobs.jsonl"
    last_worker_run_path = workspace / "runs" / "last_worker_run.json"
    jobs_before = jobs_path.read_text(encoding="utf-8") if jobs_path.exists() else ""
    last_before = last_worker_run_path.read_text(encoding="utf-8") if last_worker_run_path.exists() else ""
    try:
        jobs_path.parent.mkdir(parents=True, exist_ok=True)
        last_worker_run_path.parent.mkdir(parents=True, exist_ok=True)
        jobs_path.write_text(
            json.dumps(
                {
                    "id": str(uuid4()),
                    "ts": "2026-01-01T00:00:00+00:00",
                    "run_id": str(uuid4()),
                    "action": "forge.propose",
                    "status": "queued",
                    "priority": "high",
                    "attempts": 0,
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        last_worker_run_path.write_text(
            json.dumps(
                {
                    "lease_renewed_count": 3,
                    "lease_lost_count": 1,
                    "lease_finalize_conflict_count": 2,
                    "reclaimed_leases_count": 4,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        c = TestClient(app)
        mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
        assert mode.status_code == 200

        actions = c.get("/lens/actions")
        assert actions.status_code == 200
        chips = actions.json().get("action_chips", [])
        worker_chip = [chip for chip in chips if chip.get("kind") == "worker.cycle"]
        assert worker_chip
        telemetry = worker_chip[0].get("lease_telemetry", {})
        assert int(telemetry.get("renewed_last_cycle", 0)) == 3
        assert int(telemetry.get("lost_last_cycle", 0)) == 1
        assert int(telemetry.get("conflicts_last_cycle", 0)) == 2
        assert int(telemetry.get("recovered_last_cycle", 0)) == 4
    finally:
        jobs_path.write_text(jobs_before, encoding="utf-8")
        last_worker_run_path.write_text(last_before, encoding="utf-8")
