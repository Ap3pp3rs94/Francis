from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from francis.governance.approvals import approved_dir
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
    monotonic_values = iter((0.0, 0.0, 0.1, 0.5, 0.6, 0.7))
    worker = LensPerceptionWorker(
        _config(),
        frame_source=source,
        authority_status=_active_authority,
        execution_status=_active_execution,
        supervision_status=_active_supervision,
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
    assert latest["situation_model"]["revision"]
    assert latest["capture"]["desktop"]["active"] is True
    assert latest["capture"]["camera"]["active"] is False
    assert latest["ring_buffer"]["frame_count"] == 2
    assert latest["ring_buffer"]["raw_pixels_in_readback"] is False
    assert "lens_situation_model_not_ready" in latest["blockers"]
    situation_path = tmp_path / "runtime" / "lens-perception" / "situation-model.json"
    situation = json.loads(situation_path.read_text(encoding="utf-8"))
    assert situation["status"] == "heartbeat_partial"
    assert situation["governance"]["raw_pixels_in_state"] is False
    stopped = json.loads((tmp_path / "runtime" / "lens-perception" / "status.json").read_text(encoding="utf-8"))
    assert stopped["state"] == "stopped"
    assert stopped["capture"]["desktop"]["active"] is False
    assert stopped["governance"]["user_mouse_capture_authority"] is False


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
