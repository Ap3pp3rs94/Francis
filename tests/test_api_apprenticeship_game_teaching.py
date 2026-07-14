from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from francis.api.app import create_app
from francis.apprenticeship_game_teaching import GameTeachingObservationRecorder


def _start_payload() -> dict[str, object]:
    return {
        "actor": "test.game.teacher",
        "reason": "teach Sand scene flow",
        "target_id": "sand",
        "intent_label": "reach active gameplay",
        "declared_scope": "semantic Sand scene transitions only",
        "success_condition": "loading transitions to active gameplay",
        "max_duration_seconds": 300,
        "max_events": 10,
    }


def _observation() -> dict[str, object]:
    return {
        "kind": "lens.game.observation",
        "version": 1,
        "ready": True,
        "semantic_scene_ready": True,
        "source_frame_id": "frame-loading",
        "target": {"id": "sand", "foreground": True},
        "foreground": {"target_match": True},
        "scene": {"ready": True, "id": "loading", "confidence": 0.9, "margin": 0.8},
        "classification": {"source_frame_id": "classified-loading", "classified_at": 100.0},
        "model": {"id": "test/siglip", "remote_inference": False},
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


def test_game_teaching_start_is_permission_denied_without_state_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "test")
    monkeypatch.delenv("FRANCIS_API_ACTOR_SCOPES", raising=False)

    body = (
        TestClient(create_app())
        .post(
            "/apprenticeship/game-teaching-session/start",
            json=_start_payload(),
        )
        .json()
    )

    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["writes_receipt"] is False
    assert body["writes_memory"] is False
    assert body["grants_execution_authority"] is False
    assert not (tmp_path / "runtime" / "apprenticeship" / "game-teaching-session.json").exists()


def test_game_teaching_api_exposes_explicit_session_and_review_only_receipt(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "test")
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({"test.game.teacher": ["apprenticeship.game_teaching_session.write"]}),
    )
    client = TestClient(create_app())

    contract = client.get("/apprenticeship/game-teaching-session/contract").json()
    started = client.post(
        "/apprenticeship/game-teaching-session/start",
        json=_start_payload(),
    ).json()
    status = client.get("/apprenticeship/game-teaching-session/status").json()
    GameTeachingObservationRecorder().record(_observation())
    stopped = client.post(
        "/apprenticeship/game-teaching-session/stop",
        json={
            "actor": "test.game.teacher",
            "reason": "demonstration complete",
            "session_id": started["session_id"],
            "outcome": "completed",
            "notes": "operator review required",
        },
    ).json()
    receipts = client.get("/apprenticeship/game-teaching-session/receipts?limit=5").json()

    assert contract["status"] == "ready"
    assert contract["pipeline_stage"] == "demonstrate"
    assert contract["records_scene_transitions_only"] is True
    assert contract["records_raw_pixels"] is False
    assert contract["learning_authority"] is False
    assert contract["input_execution_authority"] is False
    assert started["ok"] is True
    assert started["kind"] == "francis.apprenticeship.game_teaching_session.start"
    assert started["session_status"] == "active"
    assert started["recording_active"] is True
    assert status["session_id"] == started["session_id"]
    assert status["intent_label"] == "reach active gameplay"
    assert stopped["ok"] is True
    assert stopped["kind"] == "francis.apprenticeship.game_teaching_session.stop"
    assert stopped["receipt_kind"] == "francis.apprenticeship.game_teaching.episode_receipt"
    assert stopped["event_count"] == 1
    assert stopped["review_state"] == "pending_operator_review"
    assert stopped["eligible_for_replay"] is False
    assert stopped["creates_capability"] is False
    assert stopped["promotes_skill"] is False
    assert receipts["count"] == 1
    assert receipts["items"][0]["receipt_id"] == stopped["receipt_id"]
