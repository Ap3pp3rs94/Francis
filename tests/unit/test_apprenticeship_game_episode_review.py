from __future__ import annotations

import json
from pathlib import Path

from francis.apprenticeship_game_episode_review import (
    game_teaching_episode_replay,
    game_teaching_episode_review_receipts,
    game_teaching_episode_review_status,
    record_game_teaching_episode_review,
)
from francis.apprenticeship_game_teaching import (
    GameTeachingObservationRecorder,
    start_game_teaching_session,
    stop_game_teaching_session,
)


def _observation(*, scene_id: str, observed_at: float) -> dict[str, object]:
    return {
        "kind": "lens.game.observation",
        "version": 1,
        "ready": True,
        "semantic_scene_ready": True,
        "source_frame_id": f"frame-{scene_id}",
        "target": {"id": "sand", "configured": True, "foreground": True},
        "foreground": {"target_match": True},
        "scene": {
            "ready": True,
            "id": scene_id,
            "confidence": 0.9,
            "margin": 0.7,
        },
        "classification": {
            "source_frame_id": f"classified-{scene_id}",
            "classified_at": observed_at,
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


def _episode(*, scenes: tuple[str, ...] = ("loading", "main_menu", "active_gameplay")) -> dict[str, object]:
    started = start_game_teaching_session(
        actor="test.game.teacher",
        reason="teach visible Sand flow",
        target_id="sand",
        intent_label="reach active gameplay",
        declared_scope="semantic Sand scene transitions only",
        success_condition="loading transitions to active gameplay",
        max_duration_seconds=300,
        max_events=10,
        now=100.0,
    )
    recorder = GameTeachingObservationRecorder()
    for index, scene_id in enumerate(scenes, start=1):
        observed_at = 100.0 + index
        recorder.record(
            _observation(scene_id=scene_id, observed_at=observed_at),
            observed_at=observed_at,
        )
    return stop_game_teaching_session(
        actor="test.game.teacher",
        reason="demonstration complete",
        session_id=started["session_id"],
        outcome="completed",
        notes="review before generalization",
        now=110.0,
    )


def test_game_episode_replay_is_digest_pinned_deterministic_and_read_only(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "test")
    episode = _episode()

    status = game_teaching_episode_review_status(episode_receipt_id=episode["receipt_id"])
    first = game_teaching_episode_replay(
        episode_receipt_id=episode["receipt_id"],
        cursor=0,
        limit=2,
    )
    second = game_teaching_episode_replay(
        episode_receipt_id=episode["receipt_id"],
        cursor=0,
        limit=2,
    )

    assert episode["integrity_algorithm"] == "sha256"
    assert len(episode["episode_digest"]) == 64
    assert status["status"] == "pending_operator_review"
    assert status["replay_ready"] is True
    assert status["operator_review_required"] is True
    assert first["replay_digest"] == second["replay_digest"]
    assert first["steps"] == second["steps"]
    assert first["total_steps"] == 3
    assert first["next_cursor"] == 2
    assert first["complete"] is False
    assert [item["to_scene_id"] for item in first["steps"]] == ["loading", "main_menu"]
    assert first["steps"][0]["transition_kind"] == "initial_scene"
    assert first["steps"][1]["offset_ms"] == 1_000.0
    assert first["executes_replay"] is False
    assert first["runs_tools"] is False
    assert first["writes_memory"] is False
    assert first["learning_authority"] is False
    assert first["input_execution_authority"] is False


def test_game_episode_review_is_append_only_correctable_and_idempotent(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "test")
    episode = _episode()

    accepted = record_game_teaching_episode_review(
        actor="test.game.reviewer",
        reason="review semantic replay",
        episode_receipt_id=episode["receipt_id"],
        decision="accepted",
        summary="The semantic transition order matches the demonstration.",
        now=120.0,
    )
    duplicate = record_game_teaching_episode_review(
        actor="test.game.reviewer",
        reason="review semantic replay",
        episode_receipt_id=episode["receipt_id"],
        decision="accepted",
        summary="The semantic transition order matches the demonstration.",
        now=121.0,
    )
    correction = record_game_teaching_episode_review(
        actor="test.game.reviewer",
        reason="correct semantic replay",
        episode_receipt_id=episode["receipt_id"],
        decision="needs_correction",
        summary="The menu transition is optional and must not become a required step.",
        corrections=[
            {
                "correction_type": "optional_transition",
                "sequence": 2,
                "note": "Treat main_menu as optional.",
                "replacement": "optional_main_menu",
            }
        ],
        now=122.0,
    )
    status = game_teaching_episode_review_status(episode_receipt_id=episode["receipt_id"])
    receipts = game_teaching_episode_review_receipts(
        limit=10,
        episode_receipt_id=episode["receipt_id"],
    )

    assert accepted["review_revision"] == 1
    assert accepted["generalization_candidate_ready"] is True
    assert accepted["generalization_performed"] is False
    assert accepted["learning_authority"] is False
    assert duplicate["receipt_id"] == accepted["receipt_id"]
    assert duplicate["idempotent"] is True
    assert correction["review_revision"] == 2
    assert correction["correction_count"] == 1
    assert correction["generalization_candidate_ready"] is False
    assert status["status"] == "correction_required"
    assert status["review_revision"] == 2
    assert status["operator_review_required"] is True
    assert receipts["count"] == 2

    receipt_path = tmp_path / "logs" / "apprenticeship" / "game_teaching_episode_review_receipts.jsonl"
    assert len(receipt_path.read_text(encoding="utf-8").splitlines()) == 2


def test_game_episode_review_rejects_digest_tampering_without_receipt_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "test")
    episode = _episode()
    episode_path = tmp_path / "logs" / "apprenticeship" / "game_teaching_episode_receipts.jsonl"
    row = json.loads(episode_path.read_text(encoding="utf-8"))
    row["scene_sequence"][0]["scene_id"] = "tampered_scene"
    episode_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    status = game_teaching_episode_review_status(episode_receipt_id=episode["receipt_id"])
    replay = game_teaching_episode_replay(episode_receipt_id=episode["receipt_id"])
    review = record_game_teaching_episode_review(
        actor="test.game.reviewer",
        reason="review semantic replay",
        episode_receipt_id=episode["receipt_id"],
        decision="accepted",
        summary="This should be rejected because the source changed.",
        now=120.0,
    )

    assert status["status"] == "episode_invalid"
    assert "game_teaching_episode_digest_mismatch" in status["blockers"]
    assert replay["ok"] is False
    assert replay["steps"] == []
    assert review["ok"] is False
    assert review["writes_receipt"] is False
    assert not (tmp_path / "logs" / "apprenticeship" / "game_teaching_episode_review_receipts.jsonl").exists()
