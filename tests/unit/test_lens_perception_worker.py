from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from francis.governance.approvals import approved_dir
from francis.lens import perception_worker as perception_worker_module
from francis.lens.perception_capture import DesktopFrame
from francis.lens.perception_worker import (
    LENS_PERCEPTION_EXECUTION_ACTION,
    LENS_PERCEPTION_EXECUTION_REQUEST_KIND,
    LensPerceptionWorker,
    LensPerceptionWorkerConfig,
    lens_perception_execution_approval_status,
    lens_perception_worker_supervision_readback,
)


class _FrameSource:
    def __init__(self) -> None:
        self.capture_count = 0

    def capture(self) -> DesktopFrame:
        captured_at = 100.0 + (self.capture_count * 0.5)
        value = self.capture_count * 32
        self.capture_count += 1
        return DesktopFrame(
            captured_at=captured_at,
            origin_x=-1920,
            origin_y=0,
            source_width=3840,
            source_height=1080,
            width=2,
            height=2,
            bgra=bytes((value, value, value, 0)) * 4,
            backend="synthetic_worker_test",
        )


class _GameObserver:
    def __init__(self) -> None:
        self.calls = 0

    def observe(
        self,
        *,
        frame: DesktopFrame,
        source_frame_id: str,
        authority_receipt_id: str,
        observed_at: float | None = None,
    ) -> dict[str, Any]:
        self.calls += 1
        assert observed_at is not None and observed_at >= frame.captured_at
        return {
            "kind": "lens.game.observation",
            "version": 1,
            "status": "scene_classified",
            "ready": True,
            "semantic_scene_ready": True,
            "source_frame_id": source_frame_id,
            "target": {
                "id": "sand",
                "configured": True,
                "process_names": ["Sand.exe"],
                "foreground": True,
                "visibility_basis": "foreground_process_match",
            },
            "foreground": {
                "target_match": True,
                "process_id": 55,
                "process_name": "Sand.exe",
                "window_id": 44,
                "window_title_included": False,
            },
            "scene": {"ready": True, "id": "active_gameplay", "confidence": 0.8, "margin": 0.5},
            "classification": {
                "source_frame_id": source_frame_id,
                "classified_at": observed_at,
                "device": "cpu",
            },
            "model": {"id": "test/siglip", "remote_inference": False},
            "runtime_identity": {"authority_receipt_id": authority_receipt_id},
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
                "learning_authority": False,
                "reward_authority": False,
            },
        }

    def close(self) -> None:
        return None


def _active_authority(receipt_id: str, _now: int) -> dict[str, Any]:
    return {"status": "active", "active": True, "receipt_id": receipt_id, "blockers": []}


def _active_execution(approval_id: str, receipt_id: str) -> dict[str, Any]:
    return {
        "status": "approved",
        "active": True,
        "approval_id": approval_id,
        "authority_receipt_id": receipt_id,
        "blockers": [],
    }


def _active_supervision(parent_pid: int, _now: float) -> dict[str, Any]:
    return {
        "status": "ready",
        "active": True,
        "supervisor_pid": 700,
        "observed_pid": parent_pid,
        "parent_process_id": parent_pid,
        "blockers": [],
    }


def _config() -> LensPerceptionWorkerConfig:
    return LensPerceptionWorkerConfig(
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
    )


def test_worker_refuses_before_frame_capture_when_execution_is_not_approved(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    source = _FrameSource()
    worker = LensPerceptionWorker(
        _config(),
        frame_source=source,
        authority_status=_active_authority,
        execution_status=lambda _approval_id, _receipt_id: {
            "active": False,
            "blockers": ["desktop_capture_execution_approval_not_found"],
        },
        supervision_status=_active_supervision,
        clock=lambda: 100.0,
        process_id=800,
        parent_process_id=900,
    )

    state = worker.capture_once()

    assert state["state"] == "blocked"
    assert state["capture"]["desktop"]["active"] is False
    assert "desktop_capture_execution_approval_not_found" in state["blockers"]
    assert source.capture_count == 0
    assert not (tmp_path / "runtime" / "lens-perception" / "frames").exists()


def test_worker_captures_on_supervised_approved_cadence_and_updates_partial_situation_heartbeat(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    source = _FrameSource()
    game_observer = _GameObserver()
    monotonic_values = iter((0.0, 0.0, 0.1, 0.5, 0.6, 0.7))
    worker = LensPerceptionWorker(
        _config(),
        frame_source=source,
        authority_status=_active_authority,
        execution_status=_active_execution,
        supervision_status=_active_supervision,
        game_observer=game_observer,
        clock=iter((100.0, 100.0, 100.5, 100.5, 101.0)).__next__,
        monotonic_clock=monotonic_values.__next__,
        sleeper=lambda _seconds: None,
        process_id=800,
        parent_process_id=900,
    )

    result = worker.run(max_frames=2)

    assert result["ok"] is True
    assert result["captured_frames"] == 2
    assert source.capture_count == 2
    latest = result["latest_running"]
    assert latest["state"] == "running"
    assert latest["situation_model"]["status"] == "heartbeat_ready"
    assert latest["situation_model"]["heartbeat_ready"] is True
    assert latest["situation_model"]["has_current_desktop_state"] is True
    assert latest["situation_model"]["semantic_comprehension_ready"] is False
    assert latest["situation_model"]["game_scene_ready"] is True
    assert latest["situation_model"]["present"]["game"]["scene"]["id"] == "active_gameplay"
    assert latest["situation_model"]["revision"]
    assert latest["capture"]["desktop"]["active"] is True
    assert latest["capture"]["camera"]["active"] is False
    assert latest["ring_buffer"]["frame_count"] == 2
    assert latest["ring_buffer"]["raw_pixels_in_readback"] is False
    assert game_observer.calls == 2
    assert "lens_situation_model_not_ready" in latest["blockers"]
    situation_path = tmp_path / "runtime" / "lens-perception" / "situation-model.json"
    situation = json.loads(situation_path.read_text(encoding="utf-8"))
    assert situation["status"] == "heartbeat_partial"
    assert situation["governance"]["raw_pixels_in_state"] is False
    stopped = json.loads((tmp_path / "runtime" / "lens-perception" / "status.json").read_text(encoding="utf-8"))
    assert stopped["state"] == "stopped"
    assert stopped["capture"]["desktop"]["active"] is False
    assert stopped["governance"]["user_mouse_capture_authority"] is False


def test_worker_records_explicit_game_teaching_transition_and_exposes_lens_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from francis.apprenticeship_game_teaching import start_game_teaching_session

    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "test")
    started = start_game_teaching_session(
        actor="test.game.teacher",
        reason="teach the current game flow",
        target_id="sand",
        intent_label="recognize active gameplay",
        declared_scope="semantic Sand scene transitions only",
        success_condition="active gameplay is observed",
        max_duration_seconds=300,
        max_events=10,
        now=99.0,
    )
    worker = LensPerceptionWorker(
        _config(),
        frame_source=_FrameSource(),
        authority_status=_active_authority,
        execution_status=_active_execution,
        supervision_status=_active_supervision,
        game_observer=_GameObserver(),
        clock=iter((100.0, 100.1, 100.5, 100.6)).__next__,
        process_id=800,
        parent_process_id=900,
    )

    pending_state = worker.capture_once()
    state = worker.capture_once()

    pending_teaching = pending_state["situation_model"]["present"]["game"]["teaching_session"]
    teaching = state["situation_model"]["present"]["game"]["teaching_session"]
    review = state["situation_model"]["present"]["game"]["teaching_review"]
    assert started["status"] == "active"
    assert state["state"] == "running"
    assert teaching["status"] == "active"
    assert teaching["session_id"] == started["session_id"]
    assert teaching["target_id"] == "sand"
    assert teaching["recording_active"] is True
    assert pending_teaching["event_count"] == 0
    assert teaching["event_count"] == 1
    assert teaching["latest_scene_id"] == "active_gameplay"
    assert review["status"] == "awaiting_episode"
    assert review["replay_ready"] is False
    assert review["governance"]["learning_authority"] is False
    assert teaching["governance"]["raw_pixels_persisted"] is False
    assert teaching["governance"]["learning_authority"] is False
    assert teaching["governance"]["input_execution_authority"] is False


@pytest.mark.parametrize(
    "transient_blocker",
    [
        "lens_perception_supervisor_state_stale",
        "lens_perception_supervisor_state_unavailable",
    ],
)
def test_worker_pauses_capture_during_bounded_supervisor_readback_gap_then_recovers(
    transient_blocker: str,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    source = _FrameSource()
    supervision_calls = 0
    sleep_calls: list[float] = []

    def recovering_supervision(parent_pid: int, _now: float) -> dict[str, Any]:
        nonlocal supervision_calls
        supervision_calls += 1
        if supervision_calls <= 2:
            return {
                "status": "blocked",
                "active": False,
                "supervisor_pid": 700,
                "observed_pid": parent_pid,
                "blockers": [transient_blocker],
            }
        return _active_supervision(parent_pid, _now)

    worker = LensPerceptionWorker(
        _config(),
        frame_source=source,
        authority_status=_active_authority,
        execution_status=_active_execution,
        supervision_status=recovering_supervision,
        clock=iter((100.0, 100.5, 101.0, 101.0, 101.5)).__next__,
        monotonic_clock=iter((0.0, 0.0, 0.1, 0.5, 0.6, 1.0)).__next__,
        sleeper=sleep_calls.append,
        process_id=800,
        parent_process_id=900,
    )

    result = worker.run(max_frames=1)

    assert result["ok"] is True
    assert result["captured_frames"] == 1
    assert supervision_calls == 3
    assert source.capture_count == 1
    assert sleep_calls == [0.4, 0.4]


def test_worker_exits_when_supervisor_staleness_exceeds_grace(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    source = _FrameSource()

    def stale_supervision(parent_pid: int, _now: float) -> dict[str, Any]:
        return {
            "status": "blocked",
            "active": False,
            "supervisor_pid": 700,
            "observed_pid": parent_pid,
            "blockers": ["lens_perception_supervisor_state_stale"],
        }

    worker = LensPerceptionWorker(
        _config(),
        frame_source=source,
        authority_status=_active_authority,
        execution_status=_active_execution,
        supervision_status=stale_supervision,
        clock=iter((100.0, 111.0)).__next__,
        monotonic_clock=iter((0.0, 0.0, 0.1, 10.9, 11.0)).__next__,
        sleeper=lambda _seconds: None,
        process_id=800,
        parent_process_id=900,
    )

    result = worker.run()

    assert result["ok"] is False
    assert result["exit_code"] == 2
    assert result["latest"]["blockers"] == ["lens_perception_supervisor_state_stale"]
    assert source.capture_count == 0


def test_execution_approval_status_requires_exact_capture_receipt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    approval_id = "approved-execution"
    path = approved_dir() / f"{approval_id}.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "id": approval_id,
                "status": "approved",
                "action": LENS_PERCEPTION_EXECUTION_ACTION,
                "payload": {
                    "kind": LENS_PERCEPTION_EXECUTION_REQUEST_KIND,
                    "authority_receipt_id": "capture-receipt",
                    "source": "desktop_ring_buffer",
                    "mode": "resident",
                    "camera_capture_authority": False,
                    "microphone_capture_authority": False,
                    "keyboard_capture_authority": False,
                    "user_mouse_capture_authority": False,
                    "input_execution_authority": False,
                    "memory_write": False,
                },
            }
        ),
        encoding="utf-8",
    )

    ready = lens_perception_execution_approval_status(approval_id, "capture-receipt")
    mismatch = lens_perception_execution_approval_status(approval_id, "another-receipt")
    record = json.loads(path.read_text(encoding="utf-8"))
    record["id"] = "another-approval"
    path.write_text(json.dumps(record), encoding="utf-8")
    id_mismatch = lens_perception_execution_approval_status(approval_id, "capture-receipt")

    assert ready["active"] is True
    assert mismatch["active"] is False
    assert "desktop_capture_execution_authority_receipt_mismatch" in mismatch["blockers"]
    assert id_mismatch["active"] is False
    assert "desktop_capture_execution_approval_id_mismatch" in id_mismatch["blockers"]


def test_supervision_readback_rejects_worker_whose_parent_is_not_the_resident_host(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    status_path = tmp_path / "runtime" / "lens-host-supervisor" / "status.json"
    status_path.parent.mkdir(parents=True)
    status_path.write_text(
        json.dumps(
            {
                "kind": "lens.host.supervisor_state",
                "status": "resident_supervising",
                "supervisor_pid": 700,
                "supervisor_process_alive": True,
                "observed_pid": 900,
                "resident_supervised_runtime": True,
                "process_supervision_authority": True,
                "updated_at": 100.0,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("francis.lens.perception_worker.process_is_alive", lambda _pid: True)

    readback = lens_perception_worker_supervision_readback(parent_process_id=901, now=101.0)

    assert readback["active"] is False
    assert readback["parent_matches_resident_host"] is False
    assert "lens_perception_worker_parent_not_resident_host" in readback["blockers"]


def test_supervision_readback_retries_transient_status_replace_race(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    status_path = tmp_path / "runtime" / "lens-host-supervisor" / "status.json"
    status_path.parent.mkdir(parents=True)
    status_path.write_text(
        json.dumps(
            {
                "kind": "lens.host.supervisor_state",
                "status": "resident_supervising",
                "supervisor_pid": 700,
                "supervisor_process_alive": True,
                "observed_pid": 900,
                "resident_supervised_runtime": True,
                "process_supervision_authority": True,
                "updated_at": 100.0,
            }
        ),
        encoding="utf-8",
    )
    original_read_text = Path.read_text
    attempts = 0

    def flaky_read_text(path: Path, *args, **kwargs):
        nonlocal attempts
        if path == status_path and attempts < 2:
            attempts += 1
            raise PermissionError("transient supervisor status replacement")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", flaky_read_text)
    monkeypatch.setattr(perception_worker_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(perception_worker_module, "process_is_alive", lambda _pid: True)

    readback = lens_perception_worker_supervision_readback(parent_process_id=900, now=101.0)

    assert attempts == 2
    assert readback["active"] is True
    assert readback["blockers"] == []


def test_supervision_readback_reports_transient_state_unavailability(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))

    def unexpected_process_lookup(_pid: int) -> bool:
        raise AssertionError("process lookup must not run without state")

    monkeypatch.setattr(perception_worker_module, "_read_json", lambda _path: {})
    monkeypatch.setattr(perception_worker_module, "process_is_alive", unexpected_process_lookup)

    readback = lens_perception_worker_supervision_readback(parent_process_id=900, now=101.0)

    assert readback["active"] is False
    assert readback["observed_pid"] == 0
    assert readback["parent_process_id"] == 900
    assert readback["blockers"] == ["lens_perception_supervisor_state_unavailable"]


def test_supervision_readback_tolerates_bounded_concurrent_heartbeat_skew(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    status_path = tmp_path / "runtime" / "lens-host-supervisor" / "status.json"
    status_path.parent.mkdir(parents=True)
    status_path.write_text(
        json.dumps(
            {
                "kind": "lens.host.supervisor_state",
                "status": "resident_supervising",
                "supervisor_pid": 700,
                "supervisor_process_alive": True,
                "observed_pid": 900,
                "resident_supervised_runtime": True,
                "process_supervision_authority": True,
                "updated_at": 101.005,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(perception_worker_module, "process_is_alive", lambda _pid: True)

    readback = lens_perception_worker_supervision_readback(parent_process_id=900, now=101.0)

    assert readback["active"] is True
    assert readback["age_ms"] == -5.0
    assert readback["max_future_skew_ms"] == 250
    assert readback["blockers"] == []
