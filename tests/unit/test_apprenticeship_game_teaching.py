from __future__ import annotations

import json
from pathlib import Path

from francis.apprenticeship_game_teaching import (
    GameTeachingObservationRecorder,
    game_teaching_episode_receipts,
    game_teaching_session_status,
    start_game_teaching_session,
    stop_game_teaching_session,
)


def _observation(*, scene_id: str = "loading", target_id: str = "sand") -> dict[str, object]:
    return {
        "kind": "lens.game.observation",
        "version": 1,
        "status": "scene_classified",
        "ready": True,
        "semantic_scene_ready": True,
        "source_frame_id": f"frame-{scene_id}",
        "target": {
            "id": target_id,
            "configured": True,
            "foreground": True,
        },
        "foreground": {
            "target_match": True,
            "process_name": "Sand.exe",
            "window_title": "must-not-persist",
        },
        "scene": {
            "ready": True,
            "id": scene_id,
            "confidence": 0.9,
            "margin": 0.7,
            "raw_pixels": "must-not-persist",
        },
        "classification": {
            "source_frame_id": f"classified-{scene_id}",
            "classified_at": 100.0,
            "frame_bytes": "must-not-persist",
        },
        "model": {
            "id": "google/siglip-base-patch16-224",
            "remote_inference": False,
            "access_token": "must-not-persist",
        },
        "runtime_identity": {"authority_receipt_id": "capture-receipt"},
        "governance": {
            "observation_only": True,
            "local_inference_only": True,
            "remote_frame_transfer": False,
            "raw_pixels_in_state": False,
            "window_titles_captured": False,
            "keyboard_content_captured": False,
            "user_mouse_captured": False,
            "input_execution_authority": False,
            "memory_write": False,
            "learning_authority": False,
            "reward_authority": False,
        },
    }


def _start(*, now: float = 100.0, max_events: int = 5) -> dict[str, object]:
    return start_game_teaching_session(
        actor="test.game.teacher",
        reason="teach the visible game flow",
        target_id="sand",
        intent_label="reach active gameplay",
        declared_scope="semantic Sand scene transitions only",
        success_condition="loading transitions to active gameplay",
        max_duration_seconds=300,
        max_events=max_events,
        now=now,
    )


def test_game_teaching_session_requires_explicit_stop_before_another_start(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "test")

    started = _start()
    duplicate = _start(now=101.0)
    status = game_teaching_session_status(now=102.0)

    assert started["ok"] is True
    assert started["status"] == "active"
    assert started["recording_active"] is True
    assert started["writes_receipt"] is True
    assert started["starts_teaching_session"] is True
    assert duplicate["ok"] is False
    assert duplicate["status"] == "active_session_exists"
    assert duplicate["writes_receipt"] is False
    assert status["session_id"] == started["session_id"]
    assert status["target_id"] == "sand"
    assert status["event_count"] == 0
    assert status["governance"]["learning_authority"] is False
    assert status["governance"]["input_execution_authority"] is False


def test_game_teaching_records_only_semantic_transitions_and_finalizes_for_review(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "test")
    started = _start()
    recorder = GameTeachingObservationRecorder()

    first = recorder.record(_observation(scene_id="loading"), observed_at=101.0)
    duplicate = recorder.record(_observation(scene_id="loading"), observed_at=102.0)
    second = recorder.record(_observation(scene_id="active_gameplay"), observed_at=103.0)
    receipt = stop_game_teaching_session(
        actor="test.game.teacher",
        reason="demonstration complete",
        session_id=started["session_id"],
        outcome="completed",
        notes="review before replay",
        now=110.0,
    )

    assert first["event_written"] is True
    assert duplicate["event_written"] is False
    assert duplicate["capture_status"] == "scene_unchanged"
    assert second["event_written"] is True
    assert second["event_count"] == 2
    assert receipt["ok"] is True
    assert receipt["event_count"] == 2
    assert receipt["integrity_algorithm"] == "sha256"
    assert len(receipt["episode_digest"]) == 64
    assert [item["scene_id"] for item in receipt["scene_sequence"]] == ["loading", "active_gameplay"]
    assert receipt["review_state"] == "pending_operator_review"
    assert receipt["ready_for_operator_review"] is True
    assert receipt["eligible_for_replay"] is False
    assert receipt["eligible_for_generalization"] is False
    assert receipt["eligible_for_skillization"] is False
    assert receipt["writes_memory"] is False
    assert receipt["creates_capability"] is False
    assert receipt["promotes_skill"] is False

    event_path = tmp_path / "logs" / "apprenticeship" / "game-teaching-events" / f"{started['session_id']}.jsonl"
    events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()]
    assert len(events) == 2
    assert all("raw_pixels" not in event for event in events)
    assert all("window_title" not in event for event in events)
    assert all("process_name" not in event for event in events)
    assert "must-not-persist" not in event_path.read_text(encoding="utf-8")

    stopped = game_teaching_session_status(now=111.0)
    assert stopped["status"] == "stopped"
    assert stopped["recording_active"] is False
    assert stopped["event_count"] == 2
    assert stopped["episode_receipt_id"] == receipt["receipt_id"]
    receipts = game_teaching_episode_receipts(limit=5)
    assert receipts["count"] == 1
    assert receipts["items"][0]["receipt_id"] == receipt["receipt_id"]


def test_game_teaching_rejects_target_and_governance_mismatches(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "test")
    started = _start()
    recorder = GameTeachingObservationRecorder()

    wrong_target = recorder.record(_observation(target_id="another-game"), observed_at=101.0)
    overbroad = _observation()
    overbroad["governance"]["learning_authority"] = True
    governance_blocked = recorder.record(overbroad, observed_at=102.0)

    assert wrong_target["capture_status"] == "observation_blocked"
    assert wrong_target["blockers"] == ["game_teaching_observation_target_mismatch"]
    assert governance_blocked["capture_status"] == "observation_blocked"
    assert governance_blocked["blockers"] == ["game_teaching_observation_governance_invalid"]
    assert game_teaching_session_status(now=103.0)["event_count"] == 0
    event_path = tmp_path / "logs" / "apprenticeship" / "game-teaching-events" / f"{started['session_id']}.jsonl"
    assert not event_path.exists()


def test_game_teaching_stops_recording_at_declared_limits_until_explicit_stop(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "test")
    started = _start(max_events=1)
    recorder = GameTeachingObservationRecorder()

    recorded = recorder.record(_observation(), observed_at=101.0)
    limited = recorder.record(_observation(scene_id="active_gameplay"), observed_at=102.0)

    assert recorded["event_written"] is True
    assert limited["recording_active"] is False
    assert limited["status"] == "awaiting_explicit_stop"
    assert limited["blockers"] == ["game_teaching_event_limit_reached"]
    assert game_teaching_session_status(now=102.0)["session_id"] == started["session_id"]
