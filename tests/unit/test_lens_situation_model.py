from __future__ import annotations

import json
from pathlib import Path

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
    assert stored["revision"] == "frame-2"
    assert stored["governance"]["keyboard_content_captured"] is False
    assert "bgra" not in json.dumps(stored).lower()


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
