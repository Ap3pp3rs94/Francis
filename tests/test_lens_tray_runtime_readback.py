from __future__ import annotations

import json
import os
from pathlib import Path

from francis.lens.host_manifest import lens_host_launch_manifest
from francis.lens.preflight import lens_preflight


def test_lens_preflight_reports_live_tray_runtime_readback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir = tmp_path / "data"
    runtime_dir = data_dir / "runtime" / "lens-tray"
    runtime_dir.mkdir(parents=True)
    pid = os.getpid()
    (runtime_dir / "lens-tray.pid").write_text(str(pid), encoding="utf-8")
    (runtime_dir / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.tray.runtime_state",
                "status": "tray_running",
                "pid": pid,
                "tray_icon_visible": True,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_dir))

    tray = lens_preflight()["surfaces"]["tray"]

    assert tray["status"] == "blocked"
    assert tray["ready"] is False
    assert tray["tray"]["tray_runner"] == "scripts/lens-tray-presence.ps1"
    assert tray["tray_runtime"]["ready"] is True
    assert tray["tray_runtime"]["process_alive"] is True
    assert tray["tray_runtime"]["tray_icon_visible"] is True
    assert tray["tray_runtime"]["requirement_state"] == "running"
    assert tray["tray_runtime"]["blocker"] == ""
    assert "tray_presence_runtime_missing" not in tray["blockers"]
    checks = {item["id"]: item for item in tray["checks"]}
    assert checks["tray_runner"]["status"] == "present"
    assert checks["tray_runtime"]["status"] == "running"


def test_lens_host_manifest_reports_live_tray_runtime_readback_with_bom_pid(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir = tmp_path / "data"
    runtime_dir = data_dir / "runtime" / "lens-tray"
    runtime_dir.mkdir(parents=True)
    pid = os.getpid()
    (runtime_dir / "lens-tray.pid").write_text(str(pid), encoding="utf-8-sig")
    (runtime_dir / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.tray.runtime_state",
                "status": "tray_running",
                "pid": pid,
                "tray_icon_visible": True,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_dir))

    tray = lens_host_launch_manifest()["tray_runtime_readback"]

    assert tray["ready"] is True
    assert tray["pid"] == pid
    assert tray["process_alive"] is True
    assert tray["tray_icon_visible"] is True
    assert tray["requirement_state"] == "ready"
    assert tray["blocker"] == ""
