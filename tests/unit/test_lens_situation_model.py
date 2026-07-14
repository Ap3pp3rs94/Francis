from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from francis.lens import situation_model as situation_model_module
from francis.lens.perception_capture import DesktopFrame
from francis.lens.situation_model import (
    lens_situation_model_readback,
    write_lens_situation_model_heartbeat,
)


def _frame(*, captured_at: float, value: int) -> DesktopFrame:
    return DesktopFrame(
        captured_at=captured_at,
        origin_x=-1920,
        origin_y=0,
        source_width=3840,
        source_height=1080,
        width=2,
        height=2,
        bgra=bytes((value, value, value, 0)) * 4,
        backend="synthetic_situation_model_test",
    )


def _ring(*, frame_id: str, changed: bool) -> dict[str, object]:
    return {
        "ready": True,
        "latest_frame_id": frame_id,
        "latest_frame_sha256": "a" * 64,
        "latest_frame_byte_count": 80,
        "latest_change_detected": changed,
        "latest_change_score": 0.25 if changed else 0.0,
        "latest_difference_hash": "0f" * 8,
        "authority_receipt_id": "capture-receipt",
    }


def _game_observation(*, frame_id: str, learning_authority: bool = False) -> dict[str, Any]:
    return {
        "kind": "lens.game.observation",
        "version": 2,
        "status": "scene_classified",
        "ready": True,
        "semantic_scene_ready": True,
        "source_frame_id": frame_id,
        "observed_at": 100.1,
        "target": {
            "id": "sand",
            "configured": True,
            "mode": "process_allowlist",
            "process_names": ["Sand.exe"],
            "launchers": [],
            "foreground": True,
            "visibility_basis": "foreground_process_match",
        },
        "foreground": {
            "supported": True,
            "available": True,
            "target_match": True,
            "process_id": 55,
            "process_name": "Sand.exe",
            "window_id": 44,
            "window_title_included": False,
            "game_verified": False,
            "verification_basis": "foreground_process_match",
        },
        "scene": {
            "ready": True,
            "id": "active_gameplay",
            "top_candidate_id": "active_gameplay",
            "confidence": 0.78,
            "margin": 0.44,
            "min_confidence": 0.35,
            "min_margin": 0.05,
            "candidates": [
                {"scene_id": "active_gameplay", "score": 0.78},
                {"scene_id": "game_menu", "score": 0.34},
            ],
        },
        "classification": {
            "source_frame_id": f"{frame_id}-source",
            "classified_at": 100.0,
            "age_ms": 100.0,
            "max_age_ms": 6000.0,
            "inference_ms": 12.5,
            "device": "cpu",
            "backend": "test_zero_shot_classifier",
            "score_normalization": "softmax_over_mutually_exclusive_scenes",
            "target_id": "sand",
            "process_id": 55,
            "process_name": "Sand.exe",
            "model_id": "google/siglip-base-patch16-224",
            "scene_id": "active_gameplay",
            "authority_receipt_id": "capture-receipt",
        },
        "configuration": {
            "source": "runtime_config",
            "loaded": True,
            "enabled": True,
            "path": "config/runtime/lens/game-observer.json",
            "fingerprint": f"sha256:{'a' * 64}",
            "environment_override_count": 0,
        },
        "model": {
            "id": "google/siglip-base-patch16-224",
            "configured": True,
            "local_files_present": True,
            "remote_inference": False,
        },
        "runtime_identity": {"authority_receipt_id": "capture-receipt"},
        "blockers": [],
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
            "learning_authority": learning_authority,
            "reward_authority": False,
            "foreground_game_required": True,
            "local_process_launch_authority": False,
        },
    }


def _blocked_game_observation(*, frame_id: str) -> dict[str, Any]:
    observation = _game_observation(frame_id=frame_id)
    observation.update(
        {
            "status": "semantic_warming",
            "ready": False,
            "semantic_scene_ready": False,
            "scene": {},
            "classification": {},
            "blockers": ["lens_game_semantic_inference_pending"],
        }
    )
    return observation


def _legacy_game_observation(*, frame_id: str) -> dict[str, Any]:
    observation = _game_observation(frame_id=frame_id)
    observation["version"] = 1
    observation["target"].pop("mode")
    observation["target"].pop("launchers")
    observation["foreground"].pop("game_verified")
    observation["foreground"].pop("verification_basis")
    observation["governance"].pop("foreground_game_required")
    observation["governance"].pop("local_process_launch_authority")
    for field in ("target_id", "process_id", "process_name", "model_id", "scene_id", "authority_receipt_id"):
        observation["classification"].pop(field)
    return observation


def _game_teaching_session() -> dict[str, Any]:
    return {
        "kind": "francis.apprenticeship.game_teaching_session.status",
        "version": 1,
        "status": "stopped",
        "session_id": "game_teaching_0123456789abcdef",
        "target_id": "sand",
        "intent_label": "reach active gameplay",
        "declared_scope": "semantic Sand scene transitions only",
        "success_condition": "active gameplay observed",
        "started_at": 90.0,
        "deadline_at": 120.0,
        "remaining_seconds": 0.0,
        "recording_active": False,
        "event_count": 3,
        "max_events": 20,
        "latest_scene_id": "active_gameplay",
        "latest_event_at": 99.0,
        "review_required": True,
        "start_receipt_id": "game_teaching_start_0123456789abcdef",
        "episode_receipt_id": "game_teaching_episode_0123456789abcdef",
        "capture_mode": "explicit_semantic_scene_transition_session",
        "blockers": [],
        "governance": {
            "explicit_start_stop_required": True,
            "semantic_transitions_only": True,
            "raw_pixels_persisted": False,
            "window_titles_persisted": False,
            "keyboard_content_captured": False,
            "user_mouse_captured": False,
            "remote_frame_transfer": False,
            "passive_learning": False,
            "hidden_retention": False,
            "memory_write": False,
            "learning_authority": False,
            "reward_authority": False,
            "input_execution_authority": False,
            "automatic_replay": False,
            "automatic_generalization": False,
            "automatic_skillization": False,
            "automatic_capability_promotion": False,
            "operator_review_required": True,
        },
    }


def _game_teaching_review() -> dict[str, Any]:
    return {
        "kind": "francis.apprenticeship.game_teaching_episode_review.status",
        "version": 1,
        "status": "operator_accepted",
        "episode_receipt_id": "game_teaching_episode_0123456789abcdef",
        "episode_digest": "a" * 64,
        "session_id": "game_teaching_0123456789abcdef",
        "target_id": "sand",
        "intent_label": "reach active gameplay",
        "declared_scope": "semantic Sand scene transitions only",
        "success_condition": "active gameplay observed",
        "event_count": 3,
        "scene_transition_count": 3,
        "ready_for_operator_review": True,
        "replay_ready": True,
        "review_state": "operator_accepted",
        "review_decision": "accepted",
        "review_revision": 1,
        "latest_review_receipt_id": "game_teaching_review_0123456789abcdef",
        "correction_count": 0,
        "operator_review_required": False,
        "generalization_candidate_ready": True,
        "generalization_performed": False,
        "skillization_performed": False,
        "blockers": [],
        "summary": "must-not-project",
        "corrections": [{"note": "must-not-project"}],
        "governance": {
            "source_episode_immutable": True,
            "source_digest_required": True,
            "semantic_replay_only": True,
            "operator_review_required": True,
            "corrections_append_only": True,
            "replay_executes_input": False,
            "replay_runs_tools": False,
            "replay_runs_shell": False,
            "replay_starts_processes": False,
            "raw_pixels_persisted": False,
            "window_titles_persisted": False,
            "keyboard_content_captured": False,
            "user_mouse_captured": False,
            "remote_frame_transfer": False,
            "memory_write": False,
            "learning_authority": False,
            "reward_authority": False,
            "input_execution_authority": False,
            "automatic_generalization": False,
            "automatic_skillization": False,
            "automatic_capability_promotion": False,
        },
    }


def _set_nested(payload: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = payload
    for part in path[:-1]:
        current = current[part]
    current[path[-1]] = value


def test_situation_model_readback_is_missing_without_runtime_write(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))

    readback = lens_situation_model_readback(now=100.0)

    assert readback["status"] == "missing"
    assert readback["heartbeat_ready"] is False
    assert readback["semantic_comprehension_ready"] is False
    assert readback["blockers"] == ["lens_situation_model_heartbeat_missing"]
    assert not (tmp_path / "runtime" / "lens-perception").exists()


def test_situation_model_heartbeat_rewrites_one_current_state_without_pixels(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        situation_model_module,
        "lens_orb_body_runtime_readback",
        lambda: {
            "status": "ready",
            "ready": True,
            "body": "francis_orb",
            "renderer_pid": 800,
            "blockers": [],
        },
    )
    path = tmp_path / "runtime" / "lens-perception" / "situation-model.json"

    first = write_lens_situation_model_heartbeat(
        frame=_frame(captured_at=100.0, value=0),
        ring_buffer=_ring(frame_id="frame-1", changed=True),
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        observed_at=100.1,
    )
    second = write_lens_situation_model_heartbeat(
        frame=_frame(captured_at=100.5, value=32),
        ring_buffer=_ring(frame_id="frame-2", changed=False),
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        observed_at=100.6,
    )

    assert first["heartbeat_ready"] is True
    assert first["semantic_comprehension_ready"] is False
    assert second["status"] == "heartbeat_ready"
    assert second["revision"] == "frame-2"
    assert second["has_current_desktop_state"] is True
    assert second["present"]["change"]["detected"] is False
    assert second["sources"]["window_events"]["ready"] is False
    assert second["sources"]["input_events"]["ready"] is False
    assert second["sources"]["orb_body"]["ready"] is True
    assert second["present"]["orb_activity"] == "visible"
    assert second["present"]["orb_body"]["body"] == "francis_orb"
    assert "lens_semantic_watcher_not_ready" in second["source_blockers"]
    assert "lens_orb_body_state_not_connected" not in second["source_blockers"]
    assert second["governance"]["raw_pixels_in_readback"] is False
    assert list(path.parent.glob("situation-model*.json")) == [path]
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["version"] == 2
    assert stored["revision"] == "frame-2"
    assert stored["governance"]["keyboard_content_captured"] is False
    assert "bgra" not in json.dumps(stored).lower()


def test_situation_model_accepts_authority_correlated_local_game_scene(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        situation_model_module,
        "lens_orb_body_runtime_readback",
        lambda: {"status": "ready", "ready": True, "body": "francis_orb", "blockers": []},
    )

    readback = write_lens_situation_model_heartbeat(
        frame=_frame(captured_at=100.0, value=0),
        ring_buffer=_ring(frame_id="frame-game", changed=True),
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        game_observation=_game_observation(frame_id="frame-game"),
        observed_at=100.1,
    )

    assert readback["heartbeat_ready"] is True
    assert readback["semantic_comprehension_ready"] is False
    assert readback["game_scene_ready"] is True
    assert readback["sources"]["game_observer"]["ready"] is True
    assert readback["sources"]["game_observer"]["target_id"] == "sand"
    assert readback["sources"]["game_observer"]["target_mode"] == "process_allowlist"
    assert readback["sources"]["game_observer"]["local_process_launch_authority"] is False
    assert readback["present"]["game"]["scene"]["id"] == "active_gameplay"
    assert readback["present"]["game"]["configuration"] == {
        "source": "runtime_config",
        "loaded": True,
        "enabled": True,
        "path": "config/runtime/lens/game-observer.json",
        "fingerprint": f"sha256:{'a' * 64}",
        "environment_override_count": 0,
    }
    assert readback["present"]["game"]["foreground"]["window_title_included"] is False
    assert "lens_game_observer_contract_invalid" not in readback["source_blockers"]
    assert readback["governance"]["learning_authority"] is False
    assert readback["governance"]["reward_authority"] is False


def test_situation_model_blocks_legacy_v1_game_observation_explicitly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))

    readback = write_lens_situation_model_heartbeat(
        frame=_frame(captured_at=100.0, value=0),
        ring_buffer=_ring(frame_id="frame-legacy-game", changed=True),
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        game_observation=_legacy_game_observation(frame_id="frame-legacy-game"),
        observed_at=100.1,
    )

    assert readback["heartbeat_ready"] is True
    assert readback["game_scene_ready"] is False
    assert readback["sources"]["game_observer"]["status"] == "legacy_v1_blocked"
    assert readback["present"]["game"] == {}
    assert "lens_game_observer_contract_legacy_v1" in readback["source_blockers"]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("target", "id"), "other-target"),
        (("foreground", "process_name"), "Other.exe"),
        (("model", "id"), "other/model"),
        (("scene", "id"), "game_menu"),
        (("classification", "source_frame_id"), ""),
        (("classification", "authority_receipt_id"), "other-receipt"),
    ],
    ids=("target", "process", "model", "scene", "classification-frame", "classification-receipt"),
)
def test_situation_model_rejects_broken_game_observer_identity_lineage(
    tmp_path: Path,
    monkeypatch,
    path: tuple[str, ...],
    value: Any,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    observation = _game_observation(frame_id="frame-lineage")
    _set_nested(observation, path, value)

    readback = write_lens_situation_model_heartbeat(
        frame=_frame(captured_at=100.0, value=0),
        ring_buffer=_ring(frame_id="frame-lineage", changed=True),
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        game_observation=observation,
        observed_at=100.1,
    )

    assert readback["game_scene_ready"] is False
    assert readback["sources"]["game_observer"]["status"] == "invalid"
    assert readback["present"]["game"] == {}
    assert "lens_game_observer_contract_invalid" in readback["source_blockers"]


def test_situation_model_rejects_stale_game_classification_lineage(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    observation = _game_observation(frame_id="frame-stale-classification")
    observation["classification"]["classified_at"] = 90.0
    observation["classification"]["age_ms"] = 10100.0

    readback = write_lens_situation_model_heartbeat(
        frame=_frame(captured_at=100.0, value=0),
        ring_buffer=_ring(frame_id="frame-stale-classification", changed=True),
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        game_observation=observation,
        observed_at=100.1,
    )

    assert readback["game_scene_ready"] is False
    assert readback["present"]["game"] == {}
    assert "lens_game_observer_contract_invalid" in readback["source_blockers"]


def test_situation_model_projects_valid_blocked_game_observer_identity(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))

    readback = write_lens_situation_model_heartbeat(
        frame=_frame(captured_at=100.0, value=0),
        ring_buffer=_ring(frame_id="frame-blocked-game", changed=True),
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        game_observation=_blocked_game_observation(frame_id="frame-blocked-game"),
        observed_at=100.1,
    )

    game = readback["present"]["game"]
    assert readback["game_scene_ready"] is False
    assert readback["sources"]["game_observer"]["status"] == "semantic_warming"
    assert game["foreground"]["process_name"] == "Sand.exe"
    assert game["scene"] == {}
    assert game["classification"] == {}


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("status",), "crafted_blocked_status"),
        (("blockers",), []),
        (("foreground", "process_name"), "Injected.exe"),
        (("foreground", "window_id"), -1),
        (("scene",), {"ready": True, "id": "injected"}),
        (("classification",), {"process_name": "Injected.exe"}),
    ],
    ids=("status", "blocker", "process", "window", "scene", "classification"),
)
def test_situation_model_rejects_malformed_blocked_game_observation(
    tmp_path: Path,
    monkeypatch,
    path: tuple[str, ...],
    value: Any,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    observation = _blocked_game_observation(frame_id="frame-malformed-blocked-game")
    _set_nested(observation, path, value)

    readback = write_lens_situation_model_heartbeat(
        frame=_frame(captured_at=100.0, value=0),
        ring_buffer=_ring(frame_id="frame-malformed-blocked-game", changed=True),
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        game_observation=observation,
        observed_at=100.1,
    )

    assert readback["game_scene_ready"] is False
    assert readback["sources"]["game_observer"]["status"] == "invalid"
    assert readback["present"]["game"] == {}
    assert "lens_game_observer_contract_invalid" in readback["source_blockers"]


def test_situation_model_projects_only_bounded_game_observation_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    observation = _game_observation(frame_id="frame-bounded-game")
    observation["scene"]["raw_pixels"] = "must-not-persist"
    observation["classification"]["frame_bytes"] = "must-not-persist"
    observation["configuration"]["absolute_model_path"] = "must-not-persist"
    observation["model"]["access_token"] = "must-not-persist"

    readback = write_lens_situation_model_heartbeat(
        frame=_frame(captured_at=100.0, value=0),
        ring_buffer=_ring(frame_id="frame-bounded-game", changed=True),
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        game_observation=observation,
        observed_at=100.1,
    )

    projected = json.dumps(readback["present"]["game"])
    assert readback["game_scene_ready"] is True
    assert "must-not-persist" not in projected
    assert "raw_pixels" not in projected
    assert "frame_bytes" not in projected
    assert "absolute_model_path" not in projected


def test_situation_model_rejects_absolute_game_observer_configuration_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    observation = _game_observation(frame_id="frame-overbroad-config")
    observation["configuration"]["path"] = r"C:\private\game-observer.json"

    readback = write_lens_situation_model_heartbeat(
        frame=_frame(captured_at=100.0, value=0),
        ring_buffer=_ring(frame_id="frame-overbroad-config", changed=True),
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        game_observation=observation,
        observed_at=100.1,
    )

    assert readback["game_scene_ready"] is False
    assert readback["present"]["game"] == {}
    assert "lens_game_observer_contract_invalid" in readback["source_blockers"]


def test_situation_model_projects_bounded_game_teaching_review_without_operator_notes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    observation = _game_observation(frame_id="frame-game-review")
    observation["teaching_session"] = _game_teaching_session()
    observation["teaching_review"] = _game_teaching_review()

    readback = write_lens_situation_model_heartbeat(
        frame=_frame(captured_at=100.0, value=0),
        ring_buffer=_ring(frame_id="frame-game-review", changed=True),
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        game_observation=observation,
        observed_at=100.1,
    )

    session = readback["present"]["game"]["teaching_session"]
    review = readback["present"]["game"]["teaching_review"]
    projected = json.dumps(review)
    assert session["status"] == "stopped"
    assert session["episode_receipt_id"] == review["episode_receipt_id"]
    assert review["status"] == "operator_accepted"
    assert review["replay_ready"] is True
    assert review["generalization_candidate_ready"] is True
    assert review["generalization_performed"] is False
    assert review["governance"]["replay_executes_input"] is False
    assert review["governance"]["learning_authority"] is False
    assert "must-not-project" not in projected
    assert "summary" not in review
    assert "corrections" not in review
    assert "access_token" not in projected


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("teaching_review", "session_id"), "game_teaching_ffffffffffffffff"),
        (("teaching_review", "episode_receipt_id"), "game_teaching_episode_ffffffffffffffff"),
        (("teaching_session", "target_id"), "other-target"),
    ],
    ids=("session", "episode", "target"),
)
def test_situation_model_rejects_broken_game_teaching_lineage(
    tmp_path: Path,
    monkeypatch,
    path: tuple[str, ...],
    value: Any,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    observation = _game_observation(frame_id="frame-game-teaching-lineage")
    observation["teaching_session"] = _game_teaching_session()
    observation["teaching_review"] = _game_teaching_review()
    _set_nested(observation, path, value)

    readback = write_lens_situation_model_heartbeat(
        frame=_frame(captured_at=100.0, value=0),
        ring_buffer=_ring(frame_id="frame-game-teaching-lineage", changed=True),
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        game_observation=observation,
        observed_at=100.1,
    )

    assert readback["game_scene_ready"] is False
    assert readback["present"]["game"] == {}
    assert "lens_game_observer_contract_invalid" in readback["source_blockers"]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("status",), "crafted_status"),
        (("session_id",), "unbounded-session"),
        (("start_receipt_id",), "unbounded-start-receipt"),
        (("episode_receipt_id",), "unbounded-episode-receipt"),
        (("started_at",), -1.0),
        (("deadline_at",), 80.0),
        (("event_count",), 21),
        (("intent_label",), "x" * 241),
        (("blockers",), ["crafted_blocker"]),
        (("recording_active",), True),
        (("capture_mode",), "raw_input_capture"),
    ],
    ids=(
        "status",
        "session-id",
        "start-receipt",
        "episode-receipt",
        "started-at",
        "deadline",
        "count",
        "text",
        "blocker",
        "recording-state",
        "capture-mode",
    ),
)
def test_situation_model_rejects_malformed_game_teaching_session_metadata(
    tmp_path: Path,
    monkeypatch,
    path: tuple[str, ...],
    value: Any,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    observation = _game_observation(frame_id="frame-malformed-teaching-session")
    teaching_session = _game_teaching_session()
    _set_nested(teaching_session, path, value)
    observation["teaching_session"] = teaching_session

    readback = write_lens_situation_model_heartbeat(
        frame=_frame(captured_at=100.0, value=0),
        ring_buffer=_ring(frame_id="frame-malformed-teaching-session", changed=True),
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        game_observation=observation,
        observed_at=100.1,
    )

    assert readback["sources"]["game_observer"]["status"] == "invalid"
    assert readback["present"]["game"] == {}
    assert "lens_game_observer_contract_invalid" in readback["source_blockers"]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("status",), "crafted_status"),
        (("episode_receipt_id",), "unbounded-episode-receipt"),
        (("episode_digest",), "not-a-sha256-digest"),
        (("session_id",), "unbounded-session"),
        (("event_count",), 1_001),
        (("scene_transition_count",), 2),
        (("declared_scope",), "x" * 501),
        (("blockers",), ["crafted_blocker"]),
        (("review_state",), "pending_operator_review"),
        (("review_decision",), "crafted_decision"),
        (("review_revision",), 0),
        (("latest_review_receipt_id",), "unbounded-review-receipt"),
        (("operator_review_required",), True),
        (("generalization_candidate_ready",), False),
        (("generalization_performed",), True),
    ],
    ids=(
        "status",
        "episode-receipt",
        "digest",
        "session-id",
        "count",
        "transition-count",
        "text",
        "blocker",
        "review-state",
        "review-decision",
        "review-revision",
        "review-receipt",
        "review-required",
        "generalization-candidate",
        "generalization-performed",
    ),
)
def test_situation_model_rejects_malformed_game_teaching_review_metadata(
    tmp_path: Path,
    monkeypatch,
    path: tuple[str, ...],
    value: Any,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    observation = _game_observation(frame_id="frame-malformed-teaching-review")
    teaching_review = _game_teaching_review()
    _set_nested(teaching_review, path, value)
    observation["teaching_review"] = teaching_review

    readback = write_lens_situation_model_heartbeat(
        frame=_frame(captured_at=100.0, value=0),
        ring_buffer=_ring(frame_id="frame-malformed-teaching-review", changed=True),
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        game_observation=observation,
        observed_at=100.1,
    )

    assert readback["sources"]["game_observer"]["status"] == "invalid"
    assert readback["present"]["game"] == {}
    assert "lens_game_observer_contract_invalid" in readback["source_blockers"]


def test_situation_model_rejects_self_labeled_game_learning_authority(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))

    readback = write_lens_situation_model_heartbeat(
        frame=_frame(captured_at=100.0, value=0),
        ring_buffer=_ring(frame_id="frame-overbroad-game", changed=True),
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        game_observation=_game_observation(frame_id="frame-overbroad-game", learning_authority=True),
        observed_at=100.1,
    )

    assert readback["heartbeat_ready"] is True
    assert readback["game_scene_ready"] is False
    assert readback["sources"]["game_observer"]["status"] == "invalid"
    assert readback["present"]["game"] == {}
    assert "lens_game_observer_contract_invalid" in readback["source_blockers"]


def test_situation_model_rejects_game_observer_process_launch_authority(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    observation = _game_observation(frame_id="frame-game-launch-authority")
    governance = observation["governance"]
    assert isinstance(governance, dict)
    governance["local_process_launch_authority"] = True

    readback = write_lens_situation_model_heartbeat(
        frame=_frame(captured_at=100.0, value=0),
        ring_buffer=_ring(frame_id="frame-game-launch-authority", changed=True),
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        game_observation=observation,
        observed_at=100.1,
    )

    assert readback["heartbeat_ready"] is True
    assert readback["game_scene_ready"] is False
    assert readback["sources"]["game_observer"]["status"] == "invalid"
    assert readback["present"]["game"] == {}
    assert "lens_game_observer_contract_invalid" in readback["source_blockers"]


def test_situation_model_heartbeat_readback_rejects_stale_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    write_lens_situation_model_heartbeat(
        frame=_frame(captured_at=100.0, value=0),
        ring_buffer=_ring(frame_id="frame-stale", changed=True),
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        observed_at=100.0,
    )

    readback = lens_situation_model_readback(now=103.0)

    assert readback["heartbeat_ready"] is False
    assert readback["fresh"] is False
    assert "lens_situation_model_heartbeat_stale" in readback["blockers"]


def test_situation_model_readback_blocks_persisted_legacy_v1_heartbeat(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    write_lens_situation_model_heartbeat(
        frame=_frame(captured_at=100.0, value=0),
        ring_buffer=_ring(frame_id="frame-legacy-heartbeat", changed=True),
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        observed_at=100.1,
    )
    path = tmp_path / "runtime" / "lens-perception" / "situation-model.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = 1
    payload["governance"].pop("foreground_game_required")
    payload["governance"].pop("local_process_launch_authority")
    path.write_text(json.dumps(payload), encoding="utf-8")

    readback = lens_situation_model_readback(now=100.1)

    assert readback["status"] == "blocked"
    assert readback["heartbeat_ready"] is False
    assert readback["heartbeat_version"] == 1
    assert readback["game_scene_ready"] is False
    assert "lens_situation_model_heartbeat_legacy_v1" in readback["blockers"]


def test_situation_model_heartbeat_tolerates_bounded_concurrent_skew(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    write_lens_situation_model_heartbeat(
        frame=_frame(captured_at=100.0, value=0),
        ring_buffer=_ring(frame_id="frame-concurrent", changed=True),
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        observed_at=100.1,
    )

    readback = lens_situation_model_readback(now=100.0)

    assert readback["heartbeat_ready"] is True
    assert readback["fresh"] is True
    assert readback["lag_ms"] == -100.0
    assert readback["max_future_skew_ms"] == 250
    assert readback["blockers"] == []


def test_situation_model_heartbeat_accepts_exact_ready_input_event_stream(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        situation_model_module,
        "lens_orb_body_runtime_readback",
        lambda: {"status": "ready", "ready": True, "body": "francis_orb", "blockers": []},
    )

    readback = write_lens_situation_model_heartbeat(
        frame=_frame(captured_at=100.0, value=0),
        ring_buffer=_ring(frame_id="frame-with-input", changed=True),
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        input_events={
            "ready": True,
            "route": "/lens/perception/input",
            "authority_receipt_id": "input-receipt",
            "authority": {
                "active": True,
                "authorities": {"desktop_input_observation_authority": True},
            },
            "governance": {
                "runtime_state_only": True,
                "keyboard_content_captured": False,
                "key_codes_captured": False,
                "typed_characters_captured": False,
                "window_titles_captured": False,
                "clipboard_content_captured": False,
                "input_execution_authority": False,
                "user_cursor_control_authority": False,
                "memory_write": False,
            },
            "event_count": 4,
            "gesture_count": 2,
            "current": {
                "cursor": {"x": 120, "y": 220},
                "foreground": {"window_id": 42, "process_id": 84},
            },
            "pointer_activity": {"active": True, "orb_yield_required": True},
            "source_blockers": ["lens_input_scroll_source_not_connected"],
        },
        observed_at=100.1,
    )

    assert readback["sources"]["input_events"]["ready"] is True
    assert readback["sources"]["window_events"]["ready"] is True
    assert readback["present"]["user_activity"] == "active"
    assert readback["present"]["user_cursor"] == {"x": 120, "y": 220}
    assert readback["present"]["orb_yield_required"] is True
    assert readback["runtime_identity"]["input_authority_receipt_id"] == "input-receipt"
    assert "lens_input_event_stream_not_connected" not in readback["source_blockers"]
    assert "lens_input_scroll_source_not_connected" in readback["source_blockers"]


def test_situation_model_does_not_accept_self_labeled_input_event_stream(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))

    readback = write_lens_situation_model_heartbeat(
        frame=_frame(captured_at=100.0, value=0),
        ring_buffer=_ring(frame_id="frame-with-fake-input", changed=True),
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        input_events={"ready": True, "authority_receipt_id": "unvalidated-input-receipt"},
        observed_at=100.1,
    )

    assert readback["sources"]["input_events"]["ready"] is False
    assert readback["runtime_identity"]["input_authority_receipt_id"] == ""
    assert "lens_input_event_stream_not_connected" in readback["source_blockers"]
