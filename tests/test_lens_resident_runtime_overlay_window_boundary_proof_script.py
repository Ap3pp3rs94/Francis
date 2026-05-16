from __future__ import annotations

import json
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


def _run_proof(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-resident-runtime-overlay-window-boundary-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_resident_runtime_overlay_window_boundary_is_readback_only() -> None:
    proc = _run_proof("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.resident_runtime.overlay_window_boundary.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["authority_family"] == "overlay_window"
    assert payload["previous_authority_family"] == "hotkey_summon"
    assert payload["next_authority_family"] == "resident_claim"
    assert payload["authority_required"] == "overlay_control_window_management_capture_authority"
    assert payload["authority_granted"] is False
    assert payload["overlay_window_boundary_observed"] is True
    assert payload["previous_hotkey_summon_family_observed"] is True
    assert payload["overlay_preflight_observed"] is True
    assert payload["authority_blockers_proof_observed"] is True
    assert payload["side_effects_denied"] is True
    assert payload["fifth_authority_family_consumed"] is True
    assert payload["local_process_launch_authority"] is False
    assert payload["process_supervision_authority"] is False
    assert payload["process_restart_authority"] is False
    assert payload["service_install_authority"] is False
    assert payload["service_control_authority"] is False
    assert payload["tray_registration_authority"] is False
    assert payload["tray_icon_authority"] is False
    assert payload["notification_authority"] is False
    assert payload["summon_authority"] is False
    assert payload["hotkey_registration_authority"] is False
    assert payload["overlay_control_authority"] is False
    assert payload["window_management_authority"] is False
    assert payload["capture_authority"] is False
    assert payload["new_sensing_authority"] is False
    assert payload["resident_claim_authority"] is False
    assert payload["would_launch_process"] is False
    assert payload["would_supervise_process"] is False
    assert payload["would_restart_process"] is False
    assert payload["would_install_service"] is False
    assert payload["would_start_service"] is False
    assert payload["would_register_tray"] is False
    assert payload["would_register_hotkey"] is False
    assert payload["would_open_overlay"] is False
    assert payload["would_write_memory"] is False
    assert payload["would_claim_resident"] is False

    overlay_window = payload["overlay_window"]
    assert overlay_window["status"] == "blocked"
    assert overlay_window["ready"] is False
    assert overlay_window["authority_granted"] is False
    assert overlay_window["would_execute"] is False
    assert overlay_window["route"] == "/lens/overlay"
    assert "/lens/overlay" in overlay_window["evidence"]
    assert overlay_window["required_before"] == ["resident_claim"]
    assert "overlay_window_disabled" in overlay_window["blockers"]
    assert "overlay_control_authority_not_granted" in overlay_window["blockers"]
    assert "window_management_authority_not_granted" in overlay_window["blockers"]
    assert "capture_authority_not_granted" in overlay_window["blockers"]
    assert payload["blockers"] == overlay_window["blockers"]

    overlay_preflight = payload["overlay_preflight"]
    assert overlay_preflight["status"] == "blocked"
    assert overlay_preflight["ready"] is False
    assert overlay_preflight["overlay_name"] == "Francis Lens Overlay"
    assert overlay_preflight["config_path"] == "config/runtime/lens/overlay.json"
    assert overlay_preflight["overlay_scope"] == "user_session"
    assert overlay_preflight["window_enabled"] is False
    assert overlay_preflight["always_on_top"] is False
    assert "overlay_window_disabled" in overlay_preflight["blockers"]
    assert "overlay_control_authority_not_granted" in overlay_preflight["blockers"]
    assert "window_management_authority_not_granted" in overlay_preflight["blockers"]
    assert "capture_authority_not_granted" in overlay_preflight["blockers"]

    assert payload["remaining_authority_families_after_this_boundary"] == ["resident_claim"]
    assert payload["next_smallest_truthful_gap"] == "resident_runtime_resident_claim_authority_boundary"

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["resident_runtime_authority_blockers_proof"]["status"] == "proof_observed"
    assert checks["previous_hotkey_summon_family"]["status"] == "blocked"
    assert checks["overlay_preflight_readback"]["status"] == "blocked_readback_ready"
    assert checks["overlay_window_family"]["status"] == "blocked"
    assert checks["overlay_window_side_effects_denied"]["status"] == "denied_no_overlay_window"
    assert checks["authority_boundary"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    governance = payload["governance"]
    assert governance["diagnostic_only"] is True
    assert governance["wraps_existing_authority_blockers_proof"] is True
    assert governance["hotkey_summon_boundary_readback"] is True
    assert governance["overlay_preflight_readback"] is True
    assert governance["execution_authority"] is False
    assert governance["approval_decision_authority"] is False
    assert governance["local_process_launch_authority"] is False
    assert governance["overlay_control_authority"] is False
    assert governance["window_management_authority"] is False
    assert governance["capture_authority"] is False
    assert governance["new_sensing_authority"] is False
    assert governance["memory_write"] is False
    assert governance["resident_claim_authority"] is False
    assert governance["mutation_authority_granted"] is False


def test_lens_resident_runtime_overlay_window_boundary_passes_isolated_data_dir(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    runtime_dir = data_dir / "runtime" / "lens-host"

    proc = _run_proof("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_passed"
    overlay_preflight = payload["overlay_preflight"]
    assert "resident_host_process_missing" in overlay_preflight["blockers"]
    process = overlay_preflight["resident_host_process"]
    assert Path(process["status_path"]) == runtime_dir / "status.json"
    assert Path(process["pid_path"]) == runtime_dir / "lens-host.pid"
    assert process["process_alive"] is False
    assert process["runtime_state_exists"] is False
    assert process["runtime_status_kind"] == ""
    assert process["runtime_status"] == ""
    assert process["runtime_status_pid"] == 0
    assert process["pid"] == 0
    assert process["runtime_status_pid_matches_pid_file"] is False
    assert process["requirement_state"] == "missing"
    assert process["blocker"] == "resident_host_process_missing"
    assert payload["overlay_preflight_observed"] is True
    assert payload["side_effects_denied"] is True
