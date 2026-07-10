from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_surface_runtime(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-stage6-surface-runtime.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=60,
    )


def test_lens_stage6_surface_runtime_status_reports_missing_components(tmp_path: Path) -> None:
    proc = _run_surface_runtime("-Mode", "Status", "-DataDir", str(tmp_path / "data"))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.stage6.surface_runtime"
    assert payload["status"] == "missing"
    assert payload["ready"] is False
    assert payload["ready_total"] == 0
    assert payload["component_total"] == 3
    assert payload["blocked_components"] == [
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
    ]
    assert payload["next_smallest_truthful_gap"] == "stage6_surface_runtime_activation"
    assert payload["governance"]["local_runtime_coordinator"] is True
    assert payload["governance"]["execution_authority"] is False
    assert payload["governance"]["memory_write"] is False
    assert payload["governance"]["resident_claim_authority"] is False


@pytest.mark.skipif(os.name != "nt", reason="Native Orb renderer process proof is Windows-hosted")
def test_lens_stage6_surface_runtime_status_reports_coordinated_live_components(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    pid = os.getpid()

    renderer_query = subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-Command",
            "@(Get-Process -Name native_orb_renderer -ErrorAction SilentlyContinue).Id -join ','",
        ],
        check=False,
        text=True,
        capture_output=True,
        timeout=10,
    )
    existing_renderer_pids = [int(value) for value in renderer_query.stdout.strip().split(",") if value.strip()]
    if len(existing_renderer_pids) > 1:
        pytest.skip("coordinated runtime fixture requires zero or one existing native renderer")

    renderer: subprocess.Popen[bytes] | None = None
    if existing_renderer_pids:
        renderer_pid = existing_renderer_pids[0]
    else:
        source = Path(os.environ["SystemRoot"]) / "System32" / "ping.exe"
        renderer_exe = tmp_path / "native_orb_renderer.exe"
        shutil.copy2(source, renderer_exe)
        renderer = subprocess.Popen(
            [str(renderer_exe), "-n", "30", "127.0.0.1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        renderer_pid = renderer.pid

    tray_dir = data_dir / "runtime" / "lens-tray"
    tray_dir.mkdir(parents=True)
    (tray_dir / "lens-tray.pid").write_text(str(pid), encoding="utf-8")
    (tray_dir / "status.json").write_text(
        json.dumps(
            {"kind": "lens.tray.runtime_state", "status": "tray_running", "pid": pid, "tray_icon_visible": True}
        ),
        encoding="utf-8",
    )

    hotkey_dir = data_dir / "runtime" / "lens-hotkey"
    hotkey_dir.mkdir(parents=True)
    (hotkey_dir / "lens-hotkey.pid").write_text(str(pid), encoding="utf-8")
    (hotkey_dir / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.hotkey.runtime_state",
                "status": "hotkey_bound",
                "pid": pid,
                "global_hotkey": "Ctrl+Alt+F",
                "binding_scope": "global",
                "hotkey_bound": True,
                "launch_on_hotkey": False,
                "summon_runner": "scripts/lens-summon.ps1",
                "press_count": 0,
            }
        ),
        encoding="utf-8",
    )

    overlay_dir = data_dir / "runtime" / "lens-overlay"
    overlay_dir.mkdir(parents=True)
    (overlay_dir / "lens-overlay.pid").write_text(str(pid), encoding="utf-8")
    (overlay_dir / "status.json").write_text(
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

    renderer_dir = data_dir / "runtime" / "native-orb-renderer"
    renderer_dir.mkdir(parents=True)
    (renderer_dir / "native-orb-renderer.pid").write_text(str(renderer_pid), encoding="utf-8")
    (renderer_dir / "status.json").write_text(
        json.dumps(
            {
                "kind": "francis.native_orb_renderer.runtime_status",
                "status": "running",
                "renderer": "native_cpp_orb_renderer",
                "process_id": renderer_pid,
                "active_renderer": True,
            }
        ),
        encoding="utf-8",
    )

    try:
        proc = _run_surface_runtime("-Mode", "Status", "-DataDir", str(data_dir))

        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        assert payload["kind"] == "lens.stage6.surface_runtime"
        assert payload["status"] == "running"
        assert payload["ready"] is True
        assert payload["ready_total"] == 3
        assert payload["component_total"] == 3
        assert payload["blocked_components"] == []
        assert payload["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
        components = {item["id"]: item for item in payload["components"]}
        assert components["tray_presence"]["ready"] is True
        assert components["global_hotkey_binding"]["ready"] is True
        assert components["overlay_window"]["ready"] is True
        assert payload["governance"]["tray_registration_authority"] is False
        assert payload["governance"]["hotkey_registration_authority"] is False
        assert payload["governance"]["overlay_control_authority"] is False
        assert payload["governance"]["mutation_authority_granted"] is False
    finally:
        if renderer is not None:
            renderer.terminate()
            renderer.wait(timeout=10)
