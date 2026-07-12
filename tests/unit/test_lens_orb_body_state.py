from __future__ import annotations

import json
import os
from pathlib import Path

from francis.lens.orb_body_state import lens_orb_body_runtime_readback


def _write_states(data_root: Path, *, native_can_click: bool = False) -> None:
    native_path = data_root / "runtime" / "native-orb-renderer" / "status.json"
    overlay_path = data_root / "runtime" / "lens-overlay" / "status.json"
    native_path.parent.mkdir(parents=True, exist_ok=True)
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    native_path.write_text(
        json.dumps(
            {
                "kind": "francis.native_orb_renderer.runtime_status",
                "status": "running",
                "active_renderer": True,
                "renderer": "native_cpp_orb_renderer",
                "body_renderer_only": True,
                "render_only": True,
                "authority_granted": False,
                "accepts_mutation_events": False,
                "controls_user_os_cursor": False,
                "can_click": native_can_click,
                "can_drag": False,
                "can_type": False,
                "process_id": os.getpid(),
                "x": -400,
                "y": 20,
                "center_x": -265,
                "center_y": 155,
                "size": 270,
            }
        ),
        encoding="utf-8",
    )
    overlay_path.write_text(
        json.dumps(
            {
                "kind": "lens.overlay.runtime_state",
                "status": "overlay_running",
                "pid": os.getpid(),
                "native_renderer": {
                    "pid": os.getpid(),
                    "status_pid": os.getpid(),
                    "pid_matches_status": True,
                    "process_alive": True,
                    "active_renderer": True,
                    "render_only": True,
                    "authority_granted": False,
                    "controls_user_os_cursor": False,
                    "can_click": False,
                    "can_drag": False,
                    "can_type": False,
                },
                "orb_visual": {
                    "visual_contract": "native_cpp_orb.liquid_streamer_identity",
                    "ring_color_contract": {
                        "status": "ready",
                        "visual_lock_status": "locked",
                        "ring_motion_contract": "native_liquid_blob_flow",
                    },
                },
            }
        ),
        encoding="utf-8",
    )


def test_orb_body_readback_is_missing_without_runtime_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))

    payload = lens_orb_body_runtime_readback()

    assert payload["status"] == "missing"
    assert payload["ready"] is False
    assert "lens_orb_body_native_renderer_state_missing" in payload["blockers"]
    assert "lens_orb_body_overlay_state_missing" in payload["blockers"]


def test_orb_body_readback_requires_live_correlated_render_only_identity(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    _write_states(tmp_path)

    payload = lens_orb_body_runtime_readback()

    assert payload["status"] == "ready"
    assert payload["ready"] is True
    assert payload["renderer_pid"] == os.getpid()
    assert payload["overlay_pid"] == os.getpid()
    assert payload["pid_correlated"] is True
    assert payload["position"]["x"] == -400
    assert payload["position"]["center_x"] == -265
    assert payload["ring_color_contract"]["visual_lock_status"] == "locked"
    assert payload["governance"]["render_only"] is True
    assert payload["governance"]["controls_user_os_cursor"] is False
    assert payload["blockers"] == []


def test_orb_body_readback_rejects_native_authority_drift(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    _write_states(tmp_path, native_can_click=True)

    payload = lens_orb_body_runtime_readback()

    assert payload["ready"] is False
    assert "lens_orb_body_native_renderer_authority_drift" in payload["blockers"]
