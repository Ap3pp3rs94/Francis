from __future__ import annotations

import json
from pathlib import Path

from francis.apprenticeship_game_episode_review import (
    game_teaching_episode_replay,
    game_teaching_episode_review_receipts,
    game_teaching_episode_review_status,
    game_teaching_generalization_contract,
    game_teaching_generalization_proposals,
    game_teaching_generalization_status,
    record_game_teaching_episode_review,
    record_game_teaching_generalization_proposal,
)
from francis.apprenticeship_game_teaching import (
    GameTeachingObservationRecorder,
    game_teaching_episode_digest,
    start_game_teaching_session,
    stop_game_teaching_session,
)


def _observation(*, scene_id: str, frame_id: str, observed_at: float) -> dict[str, object]:
    return {
        "kind": "lens.game.observation",
        "version": 2,
        "ready": True,
        "semantic_scene_ready": True,
        "source_frame_id": f"frame-{scene_id}-{frame_id}",
        "target": {"id": "sand", "configured": True, "foreground": True},
        "foreground": {"target_match": True, "process_id": 55, "process_name": "Sand.exe"},
        "scene": {
            "ready": True,
            "id": scene_id,
            "confidence": 0.9,
            "margin": 0.7,
        },
        "classification": {
            "source_frame_id": f"classified-{scene_id}-{frame_id}",
            "classified_at": observed_at,
            "target_id": "sand",
            "process_id": 55,
            "process_name": "Sand.exe",
            "model_id": "test/siglip",
            "scene_id": scene_id,
            "authority_receipt_id": "capture-receipt",
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
            _observation(
                scene_id=scene_id,
                frame_id=f"{index}-pending",
                observed_at=observed_at - 0.25,
            ),
            observed_at=observed_at - 0.25,
        )
        recorder.record(
            _observation(
                scene_id=scene_id,
                frame_id=f"{index}-confirmed",
                observed_at=observed_at,
            ),
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


def test_game_generalization_extracts_reviewable_hypothesis_without_learning_policy(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "test")
    episode = _episode(scenes=("loading", "active_gameplay"))
    review = record_game_teaching_episode_review(
        actor="test.game.reviewer",
        reason="accept semantic replay",
        episode_receipt_id=episode["receipt_id"],
        decision="accepted",
        summary="The semantic transition order matches the demonstration.",
        now=120.0,
    )

    contract = game_teaching_generalization_contract()
    before = game_teaching_generalization_status(episode_receipt_id=episode["receipt_id"])
    proposal = record_game_teaching_generalization_proposal(
        actor="test.game.generalizer",
        reason="extract bounded semantic progression hypothesis",
        episode_receipt_id=episode["receipt_id"],
        now=121.0,
    )
    duplicate = record_game_teaching_generalization_proposal(
        actor="test.game.generalizer",
        reason="repeat bounded semantic progression hypothesis",
        episode_receipt_id=episode["receipt_id"],
        now=122.0,
    )
    after = game_teaching_generalization_status(episode_receipt_id=episode["receipt_id"])
    proposals = game_teaching_generalization_proposals(
        limit=10,
        episode_receipt_id=episode["receipt_id"],
    )

    assert contract["pipeline_stage"] == "generalize"
    assert contract["extracts_causal_input_policy"] is False
    assert contract["additional_demonstration_required_before_skillization"] is True
    assert before["status"] == "ready_to_generate"
    assert before["ready_to_generate"] is True
    assert before["additional_demonstration_required"] is True
    assert proposal["status"] == "proposal_ready_for_operator_review"
    assert proposal["source_lineage"]["episode_digest"] == episode["episode_digest"]
    assert proposal["source_lineage"]["review_receipt_id"] == review["receipt_id"]
    assert proposal["source_lineage"]["replay_digest"] == review["replay_digest"]
    assert proposal["pattern"]["observed_scene_sequence"] == ["loading", "active_gameplay"]
    assert proposal["pattern"]["variable_inputs"] == []
    assert "player_input_sequence" in proposal["pattern"]["unresolved_variables"]
    assert proposal["pattern"]["causal_action_policy_observed"] is False
    assert proposal["uncertainty"]["reusable_gameplay_policy_supported"] is False
    assert proposal["uncertainty"]["additional_demonstration_required"] is True
    assert proposal["evidence"]["input_action_event_count"] == 0
    assert len(proposal["proposal_digest"]) == 64
    assert proposal["generalization_hypothesis_extracted"] is True
    assert proposal["generalization_performed"] is False
    assert proposal["generalization_accepted"] is False
    assert proposal["skillization_candidate_ready"] is False
    assert proposal["writes_memory"] is False
    assert proposal["creates_capability"] is False
    assert proposal["learning_authority"] is False
    assert proposal["input_execution_authority"] is False
    assert proposal["governance"]["single_episode_policy_training_denied"] is True
    assert duplicate["receipt_id"] == proposal["receipt_id"]
    assert duplicate["idempotent"] is True
    assert after["status"] == "proposal_ready_for_operator_review"
    assert after["proposal_digest"] == proposal["proposal_digest"]
    assert after["generalization_performed"] is False
    assert proposals["count"] == 1
    assert proposals["integrity_valid"] is True
    assert proposals["items"][0]["integrity_valid"] is True
    proposal_path = tmp_path / "logs" / "apprenticeship" / "game_teaching_generalization_proposals.jsonl"
    assert len(proposal_path.read_text(encoding="utf-8").splitlines()) == 1


def test_game_generalization_detects_proposal_digest_tampering(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "test")
    episode = _episode(scenes=("loading", "active_gameplay"))
    record_game_teaching_episode_review(
        actor="test.game.reviewer",
        reason="accept semantic replay",
        episode_receipt_id=episode["receipt_id"],
        decision="accepted",
        summary="The semantic transition order matches the demonstration.",
        now=120.0,
    )
    record_game_teaching_generalization_proposal(
        actor="test.game.generalizer",
        reason="extract bounded semantic progression hypothesis",
        episode_receipt_id=episode["receipt_id"],
        now=121.0,
    )
    proposal_path = tmp_path / "logs" / "apprenticeship" / "game_teaching_generalization_proposals.jsonl"
    row = json.loads(proposal_path.read_text(encoding="utf-8"))
    row["pattern"]["causal_action_policy_observed"] = True
    proposal_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    status = game_teaching_generalization_status(episode_receipt_id=episode["receipt_id"])
    proposals = game_teaching_generalization_proposals(
        limit=10,
        episode_receipt_id=episode["receipt_id"],
    )
    retry = record_game_teaching_generalization_proposal(
        actor="test.game.generalizer",
        reason="retry after tampering",
        episode_receipt_id=episode["receipt_id"],
        now=122.0,
    )

    assert status["status"] == "proposal_integrity_invalid"
    assert "game_teaching_generalization_proposal_digest_mismatch" in status["blockers"]
    assert proposals["ok"] is False
    assert proposals["status"] == "integrity_invalid"
    assert proposals["integrity_valid"] is False
    assert retry["ok"] is False
    assert retry["writes_receipt"] is False
    assert retry["learning_authority"] is False


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


def test_game_episode_review_rejects_invalid_declared_scene_confirmation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "test")
    episode = _episode(scenes=("loading",))
    episode_path = tmp_path / "logs" / "apprenticeship" / "game_teaching_episode_receipts.jsonl"
    row = json.loads(episode_path.read_text(encoding="utf-8"))
    row["scene_sequence"][0]["confirmation_source_frame_ids"] = ["one-frame-only"]
    row["episode_digest"] = game_teaching_episode_digest(row)
    episode_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    status = game_teaching_episode_review_status(episode_receipt_id=episode["receipt_id"])
    review = record_game_teaching_episode_review(
        actor="test.game.reviewer",
        reason="review malformed confirmation evidence",
        episode_receipt_id=episode["receipt_id"],
        decision="accepted",
        summary="This should be rejected despite the recomputed source digest.",
        now=120.0,
    )

    assert status["status"] == "episode_invalid"
    assert "game_teaching_episode_scene_confirmation_invalid" in status["blockers"]
    assert review["ok"] is False
    assert review["writes_receipt"] is False
