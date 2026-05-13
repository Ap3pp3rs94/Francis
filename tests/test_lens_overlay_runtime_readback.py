from __future__ import annotations

import json
import os
from pathlib import Path

from francis.lens.preflight import lens_preflight


def test_lens_preflight_reports_live_overlay_runtime_readback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir = tmp_path / "data"
    runtime_dir = data_dir / "runtime" / "lens-overlay"
    runtime_dir.mkdir(parents=True)
    pid = os.getpid()
    (runtime_dir / "lens-overlay.pid").write_text(str(pid), encoding="utf-8")
    (runtime_dir / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.overlay.runtime_state",
                "status": "overlay_running",
                "pid": pid,
                "overlay_name": "Francis Lens Overlay",
                "overlay_scope": "user_session",
                "overlay_window_visible": True,
                "always_on_top": True,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_dir))

    overlay = lens_preflight()["surfaces"]["overlay"]

    assert overlay["status"] == "blocked"
    assert overlay["ready"] is False
    assert overlay["overlay"]["overlay_runner"] == "scripts/lens-overlay-window.ps1"
    assert overlay["overlay_runtime"]["ready"] is True
    assert overlay["overlay_runtime"]["process_alive"] is True
    assert overlay["overlay_runtime"]["overlay_window_visible"] is True
    assert overlay["overlay_runtime"]["always_on_top"] is True
    assert overlay["overlay_runtime"]["requirement_state"] == "visible"
    assert overlay["overlay_runtime"]["blocker"] == ""
    assert "lens_overlay_window_not_implemented" not in overlay["blockers"]
    assert "overlay_window_disabled" in overlay["blockers"]
    assert "overlay_control_authority_not_granted" in overlay["blockers"]
    checks = {item["id"]: item for item in overlay["checks"]}
    assert checks["overlay_runner"]["status"] == "present"
    assert checks["overlay_runtime"]["status"] == "visible"
