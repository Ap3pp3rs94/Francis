from __future__ import annotations

import json
from pathlib import Path

from francis.reactor.events import enqueue_event, get_event, list_events, reactor_status


def test_reactor_event_queue_records_bounded_trigger_without_dispatch(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    raw_secret = "api_key=sk-" + ("r" * 24)
    created = enqueue_event(
        {
            "trigger_source": "telemetry_event",
            "trigger_type": "ci_failure",
            "summary": f"CI failed for main {raw_secret}",
            "reason": "main branch CI failure",
            "mode": "assist",
            "risk_tier": "normal",
            "action_class": "classify",
            "trace_id": "trace_ci_1",
            "max_actions": 3,
            "max_runtime_seconds": 120,
            "max_retries": 2,
            "backoff_seconds": 30,
            "stop_conditions": ["classified", "approval_required", "budget_exhausted"],
            "metadata": {"token": raw_secret, "workflow": "ci"},
        }
    )

    assert created["ok"] is True
    assert created["applied"] is True
    event = created["event"]
    assert event["kind"] == "reactor.event"
    assert event["status"] == "queued"
    assert event["trigger"]["source"] == "telemetry_event"
    assert event["trigger"]["summary"] == "CI failed for main api_key=[REDACTED:secret]"
    assert event["trigger"]["metadata"]["token"] == "[REDACTED:secret]"
    assert event["classification"]["dispatch_allowed"] is True
    assert event["bounds"]["max_actions"] == 3
    assert event["bounds"]["max_retries"] == 2
    assert event["dispatch"] == {
        "status": "not_started",
        "allowed": True,
        "applied": False,
        "engine": "not_implemented",
    }
    assert event["governance"]["execution_authority"] is False
    assert event["governance"]["approval_authority"] is False
    assert event["governance"]["dispatch_authority"] is False
    assert event["governance"]["memory_write"] is False

    stored_path = Path(str(event["path"]))
    stored_text = stored_path.read_text(encoding="utf-8")
    assert raw_secret not in stored_text
    stored = json.loads(stored_text)
    assert stored["event_id"] == event["event_id"]

    assert get_event(str(event["event_id"]))["event_id"] == event["event_id"]  # type: ignore[index]
    assert [item["event_id"] for item in list_events(trigger_source="telemetry_event")] == [event["event_id"]]
    status = reactor_status()
    assert status["total"] == 1
    assert status["trigger_source_counts"] == {"telemetry_event": 1}


def test_reactor_event_queue_rejects_invalid_trigger_without_writing(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    rejected = enqueue_event({"trigger_source": "self_loop", "summary": "keep going forever"})

    assert rejected["ok"] is False
    assert rejected["applied"] is False
    assert rejected["error"] == "invalid_trigger_source"
    assert not (data_root / "reactor" / "events").exists()
