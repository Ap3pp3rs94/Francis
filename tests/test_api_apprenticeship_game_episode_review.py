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


def _observation(*, scene_id: str, frame_id: str, classified_at: float) -> dict[str, object]:
    return {
        "kind": "lens.game.observation",
        "version": 1,
        "ready": True,
        "semantic_scene_ready": True,
        "source_frame_id": f"frame-{scene_id}-{frame_id}",
        "target": {"id": "sand", "foreground": True},
        "foreground": {"target_match": True},
        "scene": {"ready": True, "id": scene_id, "confidence": 0.9, "margin": 0.8},
        "classification": {
            "source_frame_id": f"classified-{scene_id}-{frame_id}",
            "classified_at": classified_at,
        },
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


def _episode(client: TestClient) -> dict[str, object]:
    started = client.post(
        "/apprenticeship/game-teaching-session/start",
        json=_start_payload(),
    ).json()
    recorder = GameTeachingObservationRecorder()
    for index, scene_id in enumerate(("loading", "active_gameplay"), start=1):
        observed_at = 100.0 + index
        recorder.record(
            _observation(
                scene_id=scene_id,
                frame_id=f"{index}-pending",
                classified_at=observed_at - 0.25,
            ),
            observed_at=observed_at - 0.25,
        )
        recorder.record(
            _observation(
                scene_id=scene_id,
                frame_id=f"{index}-confirmed",
                classified_at=observed_at,
            ),
            observed_at=observed_at,
        )
    return client.post(
        "/apprenticeship/game-teaching-session/stop",
        json={
            "actor": "test.game.teacher",
            "reason": "demonstration complete",
            "session_id": started["session_id"],
            "outcome": "completed",
            "notes": "review before generalization",
        },
    ).json()


def test_game_episode_review_permission_denial_writes_nothing(
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
    episode = _episode(client)

    denied = client.post(
        f"/apprenticeship/game-teaching-episode/{episode['receipt_id']}/review",
        json={
            "actor": "test.game.reviewer",
            "reason": "review semantic replay",
            "decision": "accepted",
            "summary": "The semantic replay matches the demonstration.",
        },
    ).json()

    assert denied["ok"] is False
    assert denied["status"] == "denied"
    assert denied["writes_receipt"] is False
    assert denied["writes_memory"] is False
    assert denied["grants_execution_authority"] is False
    assert not (tmp_path / "logs" / "apprenticeship" / "game_teaching_episode_review_receipts.jsonl").exists()


def test_game_episode_review_api_exposes_read_only_replay_and_append_only_review(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "test")
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps(
            {
                "test.game.teacher": ["apprenticeship.game_teaching_session.write"],
                "test.game.reviewer": ["apprenticeship.game_teaching_episode_review.write"],
            }
        ),
    )
    client = TestClient(create_app())
    episode = _episode(client)

    contract = client.get("/apprenticeship/game-teaching-episode-review/contract").json()
    status = client.get(
        "/apprenticeship/game-teaching-episode-review/status",
        params={"episode_receipt_id": episode["receipt_id"]},
    ).json()
    replay = client.get(
        f"/apprenticeship/game-teaching-episode/{episode['receipt_id']}/replay",
        params={"cursor": 0, "limit": 10},
    ).json()
    reviewed = client.post(
        f"/apprenticeship/game-teaching-episode/{episode['receipt_id']}/review",
        json={
            "actor": "test.game.reviewer",
            "reason": "review semantic replay",
            "decision": "accepted",
            "summary": "The semantic replay matches the demonstration.",
        },
    ).json()
    after = client.get(
        "/apprenticeship/game-teaching-episode-review/status",
        params={"episode_receipt_id": episode["receipt_id"]},
    ).json()
    receipts = client.get(
        "/apprenticeship/game-teaching-episode-review/receipts",
        params={"episode_receipt_id": episode["receipt_id"], "limit": 5},
    ).json()

    assert contract["pipeline_stage"] == "replay"
    assert contract["replay_is_read_only"] is True
    assert contract["replay_executes_input"] is False
    assert contract["validates_declared_scene_confirmation_policy"] is True
    assert contract["automatic_generalization"] is False
    assert status["status"] == "pending_operator_review"
    assert status["replay_ready"] is True
    assert replay["status"] == "ready"
    assert [step["to_scene_id"] for step in replay["steps"]] == [
        "loading",
        "active_gameplay",
    ]
    assert replay["executes_replay"] is False
    assert replay["input_execution_authority"] is False
    assert reviewed["ok"] is True
    assert reviewed["kind"] == "francis.apprenticeship.game_teaching_episode_review.record"
    assert reviewed["receipt_kind"] == "francis.apprenticeship.game_teaching_episode_review.receipt"
    assert reviewed["review_state"] == "operator_accepted"
    assert reviewed["generalization_candidate_ready"] is True
    assert reviewed["generalization_performed"] is False
    assert reviewed["writes_memory"] is False
    assert reviewed["learning_authority"] is False
    assert reviewed["input_execution_authority"] is False
    assert after["status"] == "operator_accepted"
    assert after["generalization_candidate_ready"] is True
    assert receipts["count"] == 1
    assert receipts["items"][0]["receipt_id"] == reviewed["receipt_id"]
