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


def test_lens_surfaces_autonomy_event_queue_and_dispatch_chip() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    autonomy_events_path = workspace / "autonomy" / "events.jsonl"
    events_before = autonomy_events_path.read_text(encoding="utf-8") if autonomy_events_path.exists() else ""
    try:
        autonomy_events_path.parent.mkdir(parents=True, exist_ok=True)
        queued_event = {
            "id": str(uuid4()),
            "ts": "2026-01-01T00:00:00+00:00",
            "run_id": str(uuid4()),
            "kind": "autonomy.event",
            "event_type": "telemetry.critical_present",
            "source": "telemetry:dev_server",
            "priority": "critical",
            "risk_tier": "high",
            "payload": {"count": 1},
            "status": "queued",
            "attempts": 0,
            "next_run_after": "2020-01-01T00:00:00+00:00",
            "dedupe_key": "test-autonomy-high-risk",
            "lease_id": None,
            "lease_owner": None,
            "leased_at": None,
            "completed_at": None,
            "dispatch_run_id": None,
            "error": None,
        }
        autonomy_events_path.write_text(json.dumps(queued_event, ensure_ascii=False) + "\n", encoding="utf-8")

        c = TestClient(app)
        mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
        assert mode.status_code == 200

        state = c.get("/lens/state")
        assert state.status_code == 200
        payload = state.json()
        autonomy_queue = payload.get("autonomy_queue", {})
        assert int(autonomy_queue.get("queued_count", 0)) >= 1
        assert int(autonomy_queue.get("high_risk_due_count", 0)) >= 1
        blockers = payload.get("blockers", {})
        assert int(blockers.get("autonomy_queue_due", 0)) >= 1
        assert int(blockers.get("autonomy_queue_high_risk_due", 0)) >= 1

        actions = c.get("/lens/actions")
        assert actions.status_code == 200
        chips = actions.json().get("action_chips", [])
        dispatch_chip = [chip for chip in chips if chip.get("kind") == "autonomy.dispatch"]
        assert dispatch_chip
        assert dispatch_chip[0].get("enabled") is True
        telemetry = dispatch_chip[0].get("queue_telemetry", {})
        assert int(telemetry.get("queued_count", 0)) >= 1
        assert int(telemetry.get("high_risk_due_count", 0)) >= 1
        assert "approval required" in str(dispatch_chip[0].get("policy_reason", "")).lower()
    finally:
        autonomy_events_path.write_text(events_before, encoding="utf-8")


def test_lens_surfaces_autonomy_stale_lease_recovery_chip() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    autonomy_events_path = workspace / "autonomy" / "events.jsonl"
    events_before = autonomy_events_path.read_text(encoding="utf-8") if autonomy_events_path.exists() else ""
    try:
        autonomy_events_path.parent.mkdir(parents=True, exist_ok=True)
        leased_expired_event = {
            "id": str(uuid4()),
            "ts": "2026-01-01T00:00:00+00:00",
            "run_id": str(uuid4()),
            "kind": "autonomy.event",
            "event_type": "manual.recover_test",
            "source": "pytest",
            "priority": "high",
            "risk_tier": "medium",
            "payload": {"x": 1},
            "status": "leased",
            "attempts": 1,
            "next_run_after": "2026-01-01T00:00:00+00:00",
            "dedupe_key": "lens-recover-test",
            "lease_id": str(uuid4()),
            "lease_owner": "worker-x",
            "leased_at": "2020-01-01T00:00:00+00:00",
            "lease_expires_at": "2020-01-01T00:05:00+00:00",
            "completed_at": None,
            "dispatch_run_id": None,
            "error": None,
        }
        autonomy_events_path.write_text(json.dumps(leased_expired_event, ensure_ascii=False) + "\n", encoding="utf-8")

        c = TestClient(app)
        mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
        assert mode.status_code == 200

        state = c.get("/lens/state")
        assert state.status_code == 200
        payload = state.json()
        autonomy_queue = payload.get("autonomy_queue", {})
        assert int(autonomy_queue.get("leased_expired_count", 0)) >= 1
        blockers = payload.get("blockers", {})
        assert int(blockers.get("autonomy_queue_leased_expired", 0)) >= 1

        actions = c.get("/lens/actions")
        assert actions.status_code == 200
        chips = actions.json().get("action_chips", [])
        recover_chip = [chip for chip in chips if chip.get("kind") == "autonomy.recover"]
        assert recover_chip
        assert recover_chip[0].get("enabled") is True
        telemetry = recover_chip[0].get("queue_telemetry", {})
        assert int(telemetry.get("leased_expired_count", 0)) >= 1
    finally:
        autonomy_events_path.write_text(events_before, encoding="utf-8")


def test_lens_surfaces_autonomy_dispatch_halt_and_budget_telemetry() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    autonomy_events_path = workspace / "autonomy" / "events.jsonl"
    last_dispatch_path = workspace / "autonomy" / "last_dispatch.json"
    events_before = autonomy_events_path.read_text(encoding="utf-8") if autonomy_events_path.exists() else ""
    last_before = last_dispatch_path.read_text(encoding="utf-8") if last_dispatch_path.exists() else ""
    try:
        autonomy_events_path.parent.mkdir(parents=True, exist_ok=True)
        queued_event = {
            "id": str(uuid4()),
            "ts": "2026-01-01T00:00:00+00:00",
            "run_id": str(uuid4()),
            "kind": "autonomy.event",
            "event_type": "manual.lens_dispatch_halt",
            "source": "pytest",
            "priority": "normal",
            "risk_tier": "low",
            "payload": {},
            "status": "queued",
            "attempts": 0,
            "next_run_after": "2020-01-01T00:00:00+00:00",
            "dedupe_key": "lens-dispatch-halt",
            "lease_id": None,
            "lease_owner": None,
            "leased_at": None,
            "completed_at": None,
            "dispatch_run_id": None,
            "error": None,
        }
        autonomy_events_path.write_text(json.dumps(queued_event, ensure_ascii=False) + "\n", encoding="utf-8")
        last_dispatch_path.write_text(
            json.dumps(
                {
                    "run_id": str(uuid4()),
                    "halted_reason": "dispatch_action_budget_exceeded",
                    "processed_count": 0,
                    "failed_count": 0,
                    "retried_count": 1,
                    "released_count": 2,
                    "dispatch_executed_actions": 0,
                    "config": {
                        "max_dispatch_actions": 2,
                        "max_dispatch_runtime_seconds": 45,
                        "max_attempts": 3,
                        "retry_backoff_seconds": 120,
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        c = TestClient(app)
        mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
        assert mode.status_code == 200

        state = c.get("/lens/state")
        assert state.status_code == 200
        payload = state.json()
        dispatch = payload.get("autonomy_dispatch", {})
        assert dispatch.get("halted") is True
        assert dispatch.get("halted_reason") == "dispatch_action_budget_exceeded"
        assert int(dispatch.get("max_dispatch_actions", 0)) == 2
        assert int(dispatch.get("max_dispatch_runtime_seconds", 0)) == 45
        assert int(dispatch.get("max_attempts", 0)) == 3
        assert int(dispatch.get("retry_backoff_seconds", 0)) == 120
        assert "verification_status" in dispatch
        assert "confidence" in dispatch
        assert "can_claim_done" in dispatch
        blockers = payload.get("blockers", {})
        assert blockers.get("autonomy_dispatch_halted") is True
        assert blockers.get("autonomy_dispatch_budget_halt") is True
        assert blockers.get("autonomy_dispatch_critical_halt") is False

        actions = c.get("/lens/actions")
        assert actions.status_code == 200
        chips = actions.json().get("action_chips", [])
        dispatch_chip = [chip for chip in chips if chip.get("kind") == "autonomy.dispatch"]
        assert dispatch_chip
        queue_telemetry = dispatch_chip[0].get("queue_telemetry", {})
        assert queue_telemetry.get("last_halted_reason") == "dispatch_action_budget_exceeded"
        assert int(queue_telemetry.get("last_max_dispatch_actions", 0)) == 2
        assert int(queue_telemetry.get("last_max_dispatch_runtime_seconds", 0)) == 45
        assert "last_verification_status" in queue_telemetry
        assert "last_confidence" in queue_telemetry
        assert "last_can_claim_done" in queue_telemetry
    finally:
        autonomy_events_path.write_text(events_before, encoding="utf-8")
        last_dispatch_path.write_text(last_before, encoding="utf-8")


def test_lens_surfaces_autonomy_reactor_state_and_health_chip() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    autonomy_events_path = workspace / "autonomy" / "events.jsonl"
    last_tick_path = workspace / "autonomy" / "last_tick.json"
    guardrail_path = workspace / "autonomy" / "reactor_guardrail_state.json"
    events_before = autonomy_events_path.read_text(encoding="utf-8") if autonomy_events_path.exists() else ""
    tick_before = last_tick_path.read_text(encoding="utf-8") if last_tick_path.exists() else ""
    guardrail_before = guardrail_path.read_text(encoding="utf-8") if guardrail_path.exists() else ""
    try:
        autonomy_events_path.parent.mkdir(parents=True, exist_ok=True)
        queued_retry_event = {
            "id": str(uuid4()),
            "ts": "2026-01-01T00:00:00+00:00",
            "run_id": str(uuid4()),
            "kind": "autonomy.event",
            "event_type": "manual.retry_pressure",
            "source": "pytest",
            "priority": "normal",
            "risk_tier": "low",
            "payload": {},
            "status": "queued",
            "attempts": 2,
            "next_run_after": "2020-01-01T00:00:00+00:00",
            "dedupe_key": "lens-reactor-retry",
            "lease_id": None,
            "lease_owner": None,
            "leased_at": None,
            "completed_at": None,
            "dispatch_run_id": None,
            "error": "retry pending",
            "last_error": "retry pending",
            "last_failed_at": "2026-01-01T00:00:00+00:00",
            "retry_backoff_seconds": 120,
            "max_attempts": 3,
        }
        autonomy_events_path.write_text(json.dumps(queued_retry_event, ensure_ascii=False) + "\n", encoding="utf-8")
        last_tick_path.write_text(
            json.dumps(
                {
                    "id": str(uuid4()),
                    "ts": "2026-01-01T01:00:00+00:00",
                    "run_id": str(uuid4()),
                    "kind": "autonomy.reactor.tick",
                    "collect": {"seen_count": 5, "queued_count": 2, "duplicate_count": 1},
                    "dispatch": {
                        "leased_count": 2,
                        "processed_count": 0,
                        "failed_count": 1,
                        "retried_count": 1,
                        "released_count": 1,
                        "halted_reason": "dispatch_runtime_budget_exceeded",
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        guardrail_path.write_text(
            json.dumps(
                {
                    "tick_count": 9,
                    "consecutive_retry_pressure_ticks": 0,
                    "cooldown_remaining_ticks": 2,
                    "escalations_count": 3,
                    "last_retry_pressure_count": 1,
                    "last_reason": "retry_pressure_cooldown",
                    "updated_at": "2026-01-01T01:00:00+00:00",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        c = TestClient(app)
        mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
        assert mode.status_code == 200

        state = c.get("/lens/state")
        assert state.status_code == 200
        payload = state.json()
        autonomy_queue = payload.get("autonomy_queue", {})
        assert int(autonomy_queue.get("queued_retry_count", 0)) >= 1
        reactor = payload.get("autonomy_reactor", {})
        assert reactor.get("halted") is True
        assert reactor.get("halted_reason") == "dispatch_runtime_budget_exceeded"
        assert int(reactor.get("collect_seen_count", 0)) == 5
        assert int(reactor.get("dispatch_retried_count", 0)) == 1
        assert "verification_status" in reactor
        assert "confidence" in reactor
        assert "can_claim_done" in reactor
        guardrail = reactor.get("guardrail", {})
        assert int(guardrail.get("cooldown_remaining_ticks", 0)) == 2
        assert int(guardrail.get("escalations_count", 0)) == 3
        assert guardrail.get("last_reason") == "retry_pressure_cooldown"
        assert guardrail.get("manual_reset_available") is True
        blockers = payload.get("blockers", {})
        assert int(blockers.get("autonomy_queue_retry_pressure", 0)) >= 1
        assert blockers.get("autonomy_reactor_halted") is True
        assert blockers.get("autonomy_reactor_halted_reason") == "dispatch_runtime_budget_exceeded"
        assert blockers.get("autonomy_reactor_cooldown_active") is True

        actions = c.get("/lens/actions")
        assert actions.status_code == 200
        chips = actions.json().get("action_chips", [])
        reactor_chip = [chip for chip in chips if chip.get("kind") == "autonomy.reactor.tick"]
        assert reactor_chip
        assert reactor_chip[0].get("enabled") is True
        telemetry = reactor_chip[0].get("queue_telemetry", {})
        assert int(telemetry.get("queued_retry_count", 0)) >= 1
        assert telemetry.get("last_tick_halted_reason") == "dispatch_runtime_budget_exceeded"
        assert "last_tick_verification_status" in telemetry
        assert "last_tick_confidence" in telemetry
        assert "last_tick_can_claim_done" in telemetry
        assert int(telemetry.get("last_tick_retried_count", 0)) == 1
        assert telemetry.get("guardrail_cooldown_active") is True
        assert int(telemetry.get("guardrail_cooldown_remaining_ticks", 0)) == 2
        assert int(telemetry.get("guardrail_escalations_count", 0)) == 3
        assert "guardrail cooldown active" in str(reactor_chip[0].get("policy_reason", "")).lower()
        reset_chip = [chip for chip in chips if chip.get("kind") == "autonomy.reactor.guardrail.reset"]
        assert reset_chip
        assert reset_chip[0].get("enabled") is True
        reset_telemetry = reset_chip[0].get("queue_telemetry", {})
        assert reset_telemetry.get("guardrail_cooldown_active") is True
        assert int(reset_telemetry.get("guardrail_cooldown_remaining_ticks", 0)) == 2
    finally:
        autonomy_events_path.write_text(events_before, encoding="utf-8")
        last_tick_path.write_text(tick_before, encoding="utf-8")
        guardrail_path.write_text(guardrail_before, encoding="utf-8")
