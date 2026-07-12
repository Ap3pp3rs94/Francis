from __future__ import annotations

import time
from pathlib import Path

from francis.lens.perception_capture import DesktopFrame
from francis.lens.situation_model import write_lens_situation_model_heartbeat


def _client(monkeypatch, tmp_path: Path):
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    repo_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    return TestClient(create_app())


def test_situation_model_now_route_reports_only_current_bounded_heartbeat(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    missing = client.get("/lens/perception/now")
    assert missing.status_code == 200
    assert missing.json()["status"] == "missing"

    observed_at = time.time()
    write_lens_situation_model_heartbeat(
        frame=DesktopFrame(
            captured_at=observed_at,
            origin_x=0,
            origin_y=0,
            source_width=1920,
            source_height=1080,
            width=2,
            height=2,
            bgra=b"\x00\x00\x00\x00" * 4,
            backend="synthetic_api_test",
        ),
        ring_buffer={
            "ready": True,
            "latest_frame_id": "api-frame-1",
            "latest_frame_sha256": "a" * 64,
            "latest_frame_byte_count": 80,
            "latest_change_detected": True,
            "latest_change_score": 1.0,
            "latest_difference_hash": "f" * 16,
            "authority_receipt_id": "capture-receipt",
        },
        authority_receipt_id="capture-receipt",
        execution_approval_id="execution-approval",
        worker_pid=800,
        host_pid=900,
        supervisor_pid=700,
        observed_at=observed_at,
    )

    ready = client.get("/lens/perception/now")
    assert ready.status_code == 200
    body = ready.json()
    assert body["status"] == "heartbeat_ready"
    assert body["heartbeat_ready"] is True
    assert body["semantic_comprehension_ready"] is False
    assert body["governance"]["raw_pixels_in_readback"] is False
