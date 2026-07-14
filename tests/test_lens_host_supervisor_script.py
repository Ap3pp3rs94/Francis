from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path

import pytest


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_script(script_name: str, *args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / script_name),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def _wait_for_runtime_status(path: Path, status: str, timeout_seconds: int = 15) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    latest: dict[str, object] = {}
    while time.monotonic() < deadline:
        if path.is_file():
            latest = json.loads(path.read_text(encoding="utf-8-sig"))
            if latest.get("status") == status:
                return latest
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for {status}; latest={latest!r}")


def _wait_for_supervisor_heartbeat(
    path: Path,
    *,
    initial_updated_at: str,
    initial_heartbeat_count: int,
    timeout_seconds: int = 8,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    latest: dict[str, object] = {}
    while time.monotonic() < deadline:
        if path.is_file():
            try:
                latest = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                time.sleep(0.1)
                continue
            heartbeat_count = int(latest.get("heartbeat_count") or 0)
            if (
                latest.get("status") == "resident_supervising"
                and latest.get("updated_at") != initial_updated_at
                and heartbeat_count > initial_heartbeat_count
            ):
                return latest
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for supervisor heartbeat; latest={latest!r}")


def test_lens_host_supervisor_status_is_observation_only(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    proc = _run_script(
        "lens-host-supervisor.ps1",
        "-Mode",
        "Status",
        "-DataDir",
        str(data_dir),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.supervisor_runner"
    assert payload["status"] == "blocked"
    assert payload["mode"] == "status"
    assert payload["observer_ready"] is True
    assert payload["bounded_supervisor_observed"] is False
    assert payload["supervisor_observed_running_state"] is False
    assert payload["supervisor_observed_stopped_state"] is False
    assert payload["supervisor_restarted_process"] is False
    assert payload["supervisor_managed_service"] is False
    assert payload["ready_for_resident_claim"] is False
    assert payload["resident_claim_allowed"] is False
    assert payload["resident_host_process"] is False
    assert payload["supervised"] is False
    assert "resident_host_process_missing" in payload["blockers"]
    assert "process_supervision_authority_not_granted" in payload["blockers"]
    assert payload["next_smallest_truthful_gap"] == "resident_host_process_supervision_authority_boundary"
    assert payload["recommended_handoff_source"] == "lens_host_supervisor_status_process_supervision_handoff"
    assert payload["recommended_next_slice"] == "run_host_supervision_authority_request_proof_before_resident_start"
    assert (
        payload["recommended_proof_script"] == "scripts/lens-host-supervision-authority-request-proof.ps1 -Mode Status"
    )
    assert payload["authority_required"] == "process_supervision_authority"
    assert payload["authority_granted"] is False
    handoff = payload["recommended_handoff"]
    assert handoff["id"] == "resident_host_process_supervision_authority_boundary"
    assert handoff["status"] == "blocked"
    assert handoff["next_smallest_truthful_gap"] == "host_supervision_authority_exact_approval_request"
    assert handoff["next_step"] == "run_host_supervision_authority_request_proof_before_resident_start"
    assert handoff["proof_script"] == "scripts/lens-host-supervision-authority-request-proof.ps1 -Mode Status"
    assert handoff["route"] == "/lens/host/supervision/authority"
    assert handoff["readiness_route"] == "/lens/host/supervision/authority/readiness"
    assert handoff["request_route"] == "/lens/host/supervision/authority/request"
    assert handoff["requests_route"] == "/lens/host/supervision/authority/requests"
    assert handoff["grant_route"] == "/lens/host/supervision/authority"
    assert handoff["grants_route"] == "/lens/host/supervision/authority/grants"
    assert handoff["denials_route"] == "/lens/host/supervision/authority/denials"
    assert handoff["execution_route"] == "/lens/resident-runtime/execute"
    assert handoff["authority_required"] == "process_supervision_authority"
    assert handoff["authority_granted"] is False
    assert handoff["read_only_contract"] is True
    assert handoff["diagnostic_only"] is True
    assert handoff["would_execute"] is False
    assert handoff["would_mutate"] is False
    assert handoff["would_launch_process"] is False
    assert handoff["would_supervise_process"] is False
    assert handoff["would_decide_approval"] is False
    assert "process_supervision_authority_not_granted" in handoff["blockers"]
    assert payload["host_readback"]["state_exists"] is False
    assert payload["host_readback"]["process_alive"] is False
    assert not (data_dir / "runtime" / "lens-host-supervisor" / "status.json").exists()
    assert payload["governance"] == {
        "diagnostic_only": True,
        "read_only_contract": True,
        "bounded_supervisor_observation": False,
        "temporary_runtime_state_write": False,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "local_process_launch_authority": False,
        "api_local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "overlay_control_authority": False,
        "window_management_authority": False,
        "summon_authority": False,
        "resident_claim_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "mutation_authority_granted": False,
    }


def test_lens_host_supervisor_explicit_stop_tracks_observed_host_pid() -> None:
    script = (_repo_root() / "scripts" / "lens-host-supervisor.ps1").read_text(encoding="utf-8")

    assert "while (Test-ProcessAlive -ProcessId $RunningPid)" in script
    assert "while (-not $Process.HasExited)" not in script


def test_lens_host_supervisor_runtime_state_write_retries_atomic_move() -> None:
    script = (_repo_root() / "scripts" / "lens-host-supervisor.ps1").read_text(encoding="utf-8")
    write_json = script[script.index("function Write-JsonFile") : script.index("function Get-PropertyValue")]

    assert "for ($Attempt = 0; $Attempt -lt 20 -and -not $Moved; $Attempt += 1)" in write_json
    assert "[System.IO.File]::Replace($TempPath, $Path, $BackupPath, $true)" in write_json
    assert "Move-Item -LiteralPath $TempPath -Destination $Path -Force -ErrorAction Stop" in write_json
    assert "Remove-Item -LiteralPath $Path" not in write_json
    assert "Start-Sleep -Milliseconds 50" in write_json


def test_lens_host_supervisor_observes_existing_bounded_host_without_restart(tmp_path: Path) -> None:
    if platform.system() != "Windows":
        pytest.skip("Live Lens host lifecycle process-exit proof is Windows-hosted.")

    data_dir = tmp_path / "data"
    host = subprocess.Popen(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-host.ps1"),
            "-Mode",
            "Foreground",
            "-RunSeconds",
            "4",
        ],
        cwd=_repo_root(),
        env={**os.environ, "FRANCIS_DATA_DIR": str(data_dir)},
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    observed = _run_script(
        "lens-host-supervisor.ps1",
        "-Mode",
        "Observe",
        "-RunSeconds",
        "10",
        "-DataDir",
        str(data_dir),
        timeout=150,
    )
    _, host_stderr = host.communicate(timeout=30)

    assert host.returncode == 0, host_stderr

    assert observed.returncode == 0, observed.stderr
    payload = json.loads(observed.stdout)
    assert payload["kind"] == "lens.host.supervisor_runner"
    assert payload["status"] == "observation_completed"
    assert payload["mode"] == "observe"
    assert payload["ok"] is True
    assert payload["bounded_supervisor_observed"] is True
    assert payload["supervisor_observed_running_state"] is True
    assert payload["supervisor_observed_stopped_state"] is True
    assert payload["supervisor_restarted_process"] is False
    assert payload["supervisor_managed_service"] is False
    assert payload["resident_host_process"] is False
    assert payload["supervised"] is False
    assert payload["ready_for_resident_claim"] is False
    assert payload["resident_claim_allowed"] is False
    assert "resident_host_process_not_supervised" in payload["blockers"]
    assert "process_restart_authority_not_granted" in payload["blockers"]
    assert "service_control_authority_not_granted" in payload["blockers"]

    proof = payload["proof"]
    assert proof["running_state_status"] == "foreground_running"
    assert proof["running_pid"] > 0
    assert proof["running_process_alive"] is True
    assert proof["stopped_state_status"] == "foreground_stopped"
    assert proof["stopped_pid"] == proof["running_pid"]
    assert proof["stopped_process_alive"] is False
    assert proof["same_process_observed"] is True
    assert proof["pid_file_present_after_stop"] is False

    assert payload["governance"] == {
        "diagnostic_only": True,
        "read_only_contract": False,
        "bounded_supervisor_observation": True,
        "temporary_runtime_state_write": True,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "local_process_launch_authority": False,
        "api_local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "overlay_control_authority": False,
        "window_management_authority": False,
        "summon_authority": False,
        "resident_claim_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "mutation_authority_granted": False,
    }
    assert (data_dir / "runtime" / "lens-host-supervisor" / "status.json").is_file()
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_host_supervisor_supervises_one_bounded_host_without_resident_claim(tmp_path: Path) -> None:
    if platform.system() != "Windows":
        pytest.skip("Live Lens host lifecycle process-exit proof is Windows-hosted.")

    data_dir = tmp_path / "data"
    proc = _run_script(
        "lens-host-supervisor.ps1",
        "-Mode",
        "SuperviseOnce",
        "-RunSeconds",
        "5",
        "-DataDir",
        str(data_dir),
        timeout=90,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.supervisor_runner"
    assert payload["status"] == "supervised_session_completed"
    assert payload["mode"] == "superviseonce"
    assert payload["ok"] is True
    assert payload["supervisor_started_process"] is True
    assert payload["bounded_supervised_session"] is True
    assert payload["bounded_supervisor_observed"] is True
    assert payload["supervisor_observed_running_state"] is True
    assert payload["supervisor_observed_stopped_state"] is True
    assert payload["temporary_host_process_observed"] is True
    assert payload["supervisor_restarted_process"] is False
    assert payload["supervisor_managed_service"] is False
    assert payload["ready_for_resident_claim"] is False
    assert payload["resident_claim_allowed"] is False
    assert payload["resident_host_process"] is False
    assert payload["resident_supervised_runtime"] is False
    assert payload["supervised"] is False
    assert payload["next_smallest_truthful_gap"] == "resident_supervised_session_checkpoint_readback"
    assert "resident_host_process_missing" not in payload["blockers"]
    assert "resident_host_process_not_resident" in payload["blockers"]
    assert "resident_supervision_not_persistent" in payload["blockers"]
    assert "process_supervision_authority_not_granted" in payload["blockers"]
    assert "process_restart_authority_not_granted" in payload["blockers"]
    assert "service_control_authority_not_granted" in payload["blockers"]

    proof = payload["proof"]
    assert proof["running_state_status"] == "foreground_running"
    assert proof["running_pid"] > 0
    assert proof["running_process_alive"] is True
    assert proof["stopped_state_status"] == "foreground_stopped"
    assert proof["stopped_pid"] == proof["running_pid"]
    assert proof["stopped_process_alive"] is False
    assert proof["same_process_observed"] is True
    assert proof["pid_file_present_after_stop"] is False
    assert proof["supervisor_owned_launch"] is True
    assert proof["host_exit_code"] == 0

    assert payload["governance"] == {
        "diagnostic_only": True,
        "read_only_contract": False,
        "bounded_supervisor_observation": True,
        "temporary_runtime_state_write": True,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "local_process_launch_authority": True,
        "api_local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "overlay_control_authority": False,
        "window_management_authority": False,
        "summon_authority": False,
        "resident_claim_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "mutation_authority_granted": False,
    }
    assert (data_dir / "runtime" / "lens-host-supervisor" / "status.json").is_file()
    assert (data_dir / "runtime" / "lens-host" / "status.json").is_file()
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_host_supervisor_supervises_bounded_resident_candidate_without_claim(tmp_path: Path) -> None:
    if platform.system() != "Windows":
        pytest.skip("Live Lens resident candidate lifecycle proof is Windows-hosted.")

    data_dir = tmp_path / "data"
    proc = _run_script(
        "lens-host-supervisor.ps1",
        "-Mode",
        "SuperviseResidentOnce",
        "-RunSeconds",
        "5",
        "-DataDir",
        str(data_dir),
        timeout=90,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.supervisor_runner"
    assert payload["status"] == "supervised_session_completed"
    assert payload["mode"] == "superviseresidentonce"
    assert payload["ok"] is True
    assert payload["supervisor_started_process"] is True
    assert payload["bounded_supervised_session"] is True
    assert payload["bounded_supervisor_observed"] is True
    assert payload["supervisor_observed_running_state"] is True
    assert payload["supervisor_observed_stopped_state"] is True
    assert payload["temporary_host_process_observed"] is True
    assert payload["resident_runtime_candidate_supervised"] is True
    assert payload["resident_supervised_runtime"] is False
    assert payload["ready_for_resident_claim"] is False
    assert payload["resident_claim_allowed"] is False
    assert payload["resident_host_process"] is False
    assert payload["supervised"] is False
    assert payload["next_smallest_truthful_gap"] == "resident_supervision_not_persistent"
    assert "resident_host_process_missing" not in payload["blockers"]
    assert "resident_runtime_candidate_not_persistent" in payload["blockers"]
    assert "resident_supervision_not_persistent" in payload["blockers"]
    assert "process_supervision_authority_not_granted" in payload["blockers"]
    assert "service_control_authority_not_granted" in payload["blockers"]

    proof = payload["proof"]
    assert proof["host_mode"] == "resident"
    assert proof["running_state_status"] == "resident_running"
    assert proof["running_pid"] > 0
    assert proof["running_process_alive"] is True
    assert proof["stopped_state_status"] == "resident_stopped"
    assert proof["stopped_pid"] == proof["running_pid"]
    assert proof["stopped_process_alive"] is False
    assert proof["same_process_observed"] is True
    assert proof["pid_file_present_after_stop"] is False
    assert proof["supervisor_owned_launch"] is True
    assert proof["host_exit_code"] == 0

    assert payload["governance"] == {
        "diagnostic_only": True,
        "read_only_contract": False,
        "bounded_supervisor_observation": True,
        "temporary_runtime_state_write": True,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "local_process_launch_authority": True,
        "api_local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "overlay_control_authority": False,
        "window_management_authority": False,
        "summon_authority": False,
        "resident_claim_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "mutation_authority_granted": False,
    }

    supervisor_state = json.loads(
        (data_dir / "runtime" / "lens-host-supervisor" / "status.json").read_text(encoding="utf-8-sig")
    )
    assert supervisor_state["status"] == "supervised_session_completed"
    assert supervisor_state["mode"] == "supervise_resident_once"
    assert supervisor_state["host_mode"] == "resident"
    assert supervisor_state["observed_state"] == "resident_stopped"
    assert (data_dir / "runtime" / "lens-host" / "status.json").is_file()
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_host_supervisor_observes_existing_resident_candidate_without_relaunch(tmp_path: Path) -> None:
    if platform.system() != "Windows":
        pytest.skip("Live Lens resident candidate observation proof is Windows-hosted.")

    data_dir = tmp_path / "data"
    host = subprocess.Popen(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-host.ps1"),
            "-Mode",
            "Resident",
            "-RunSeconds",
            "0",
        ],
        cwd=_repo_root(),
        env={**os.environ, "FRANCIS_DATA_DIR": str(data_dir)},
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    stopped: subprocess.CompletedProcess[str] | None = None
    try:
        running_state = _wait_for_runtime_status(
            data_dir / "runtime" / "lens-host" / "status.json",
            "resident_running",
        )
        proc = _run_script(
            "lens-host-supervisor.ps1",
            "-Mode",
            "SuperviseResidentOnce",
            "-RunSeconds",
            "2",
            "-DataDir",
            str(data_dir),
            timeout=90,
        )

        assert proc.returncode == 0, proc.stderr or proc.stdout
        payload = json.loads(proc.stdout)
        assert payload["kind"] == "lens.host.supervisor_runner"
        assert payload["status"] == "resident_candidate_already_running_observed"
        assert payload["mode"] == "superviseresidentonce"
        assert payload["ok"] is True
        assert payload["supervisor_started_process"] is False
        assert payload["bounded_supervised_session"] is False
        assert payload["bounded_supervisor_observed"] is False
        assert payload["supervisor_observed_running_state"] is True
        assert payload["supervisor_observed_stopped_state"] is False
        assert payload["temporary_host_process_observed"] is True
        assert payload["resident_runtime_candidate_supervised"] is False
        assert payload["resident_supervised_runtime"] is False
        assert payload["ready_for_resident_claim"] is False
        assert payload["resident_claim_allowed"] is False
        assert payload["resident_host_process"] is False
        assert payload["supervised"] is False
        assert payload["next_smallest_truthful_gap"] == "resident_supervision_not_persistent"
        assert "resident_host_process_missing" not in payload["blockers"]
        assert "resident_host_process_not_supervised" in payload["blockers"]
        assert "resident_runtime_candidate_not_persistent" in payload["blockers"]
        assert "resident_supervision_not_persistent" in payload["blockers"]
        assert "process_supervision_authority_not_granted" in payload["blockers"]
        assert "service_control_authority_not_granted" in payload["blockers"]

        proof = payload["proof"]
        assert proof["existing_resident_candidate_observed"] is True
        assert proof["host_mode"] == "resident"
        assert proof["running_state_status"] == "resident_running"
        assert proof["running_pid"] == running_state["pid"]
        assert proof["running_process_alive"] is True
        assert proof["stopped_state_status"] == ""
        assert proof["stopped_pid"] == 0
        assert proof["stopped_process_alive"] is False
        assert proof["same_process_observed"] is False
        assert proof["pid_file_present_after_stop"] is True
        assert proof["supervisor_owned_launch"] is False
        assert proof["host_exit_code"] == -1

        assert (data_dir / "runtime" / "lens-host" / "lens-host.pid").is_file()
        assert not (data_dir / "runtime" / "lens-host-supervisor" / "status.json").exists()
    finally:
        stopped = _run_script(
            "lens-host-supervisor.ps1",
            "-Mode",
            "StopResident",
            "-DataDir",
            str(data_dir),
            timeout=90,
        )
        if host.poll() is None:
            host.terminate()
        try:
            host.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            host.kill()
            host.communicate(timeout=30)

    assert stopped.returncode == 0, stopped.stderr or stopped.stdout
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_host_supervisor_probes_supervised_resident_runtime_without_claim(tmp_path: Path) -> None:
    if platform.system() != "Windows":
        pytest.skip("Live Lens resident supervision proof is Windows-hosted.")

    data_dir = tmp_path / "data"
    proc = _run_script(
        "lens-host-supervisor.ps1",
        "-Mode",
        "SuperviseResident",
        "-RunSeconds",
        "2",
        "-DataDir",
        str(data_dir),
        timeout=90,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.supervisor_runner"
    assert payload["status"] == "resident_supervision_probe_completed"
    assert payload["ok"] is True
    assert payload["supervisor_started_process"] is True
    assert payload["resident_host_process"] is True
    assert payload["resident_supervised_runtime"] is True
    assert payload["resident_runtime_candidate_supervised"] is True
    assert payload["resident_claim_allowed"] is False
    assert payload["service_managed"] is False
    assert payload["tray_presence"] is False
    assert payload["global_hotkey"] is False
    assert payload["overlay_window"] is False
    assert payload["summon_anywhere"] is False
    assert payload["next_smallest_truthful_gap"] == "summon_tray_presence_blocker_boundary"
    assert "tray_host_missing" in payload["blockers"]
    assert "global_hotkey_binding_missing" in payload["blockers"]
    assert "overlay_window_missing" in payload["blockers"]
    assert "summon_binding_missing" in payload["blockers"]

    proof = payload["proof"]
    assert proof["running_state_status"] == "resident_running"
    assert proof["running_pid"] > 0
    assert proof["running_process_alive"] is True
    assert proof["stopped_state_status"] == "resident_stopped"
    assert proof["stopped_process_alive"] is False
    assert proof["same_process_observed"] is True
    assert proof["pid_file_present_after_stop"] is False

    governance = payload["governance"]
    assert governance["product_execution_authority"] is False
    assert governance["approval_decision_authority"] is False
    assert governance["local_process_launch_authority"] is True
    assert governance["process_supervision_authority"] is True
    assert governance["process_restart_authority"] is False
    assert governance["service_install_authority"] is False
    assert governance["service_control_authority"] is False
    assert governance["tray_registration_authority"] is False
    assert governance["hotkey_registration_authority"] is False
    assert governance["overlay_control_authority"] is False
    assert governance["summon_authority"] is False
    assert governance["memory_write"] is False
    assert governance["resident_claim_authority"] is False


def test_lens_host_supervisor_starts_and_stops_live_resident_lease(tmp_path: Path) -> None:
    if platform.system() != "Windows":
        pytest.skip("Live Lens resident supervision lease is Windows-hosted.")

    data_dir = tmp_path / "data"
    started = _run_script(
        "lens-host-supervisor.ps1",
        "-Mode",
        "StartResident",
        "-DataDir",
        str(data_dir),
        timeout=90,
    )

    stopped: subprocess.CompletedProcess[str] | None = None
    try:
        assert started.returncode == 0, started.stderr or started.stdout
        payload = json.loads(started.stdout)
        assert payload["kind"] == "lens.host.supervisor_runner"
        assert payload["status"] == "resident_supervision_started"
        assert payload["ok"] is True
        assert payload["supervisor_started_process"] is True
        assert payload["supervisor_pid"] > 0
        assert payload["supervisor_process_alive"] is True
        assert payload["bounded_supervised_session"] is False
        assert payload["temporary_host_process_observed"] is True
        assert payload["resident_host_process"] is True
        assert payload["resident_supervised_runtime"] is True
        assert payload["resident_runtime_candidate_supervised"] is True
        assert payload["resident_claim_allowed"] is False
        assert payload["service_managed"] is False
        assert payload["tray_presence"] is False
        assert payload["global_hotkey"] is False
        assert payload["overlay_window"] is False
        assert payload["summon_anywhere"] is False
        assert payload["next_smallest_truthful_gap"] == "summon_tray_presence_blocker_boundary"
        assert "tray_host_missing" in payload["blockers"]
        assert "global_hotkey_binding_missing" in payload["blockers"]
        assert "overlay_window_missing" in payload["blockers"]
        assert "summon_binding_missing" in payload["blockers"]
        assert "service_control_authority_not_granted" in payload["blockers"]

        host_readback = payload["host_readback"]
        assert host_readback["state_status"] == "resident_running"
        assert host_readback["process_alive"] is True
        assert host_readback["pid"] > 0
        assert (data_dir / "runtime" / "lens-host" / "lens-host.pid").is_file()

        supervisor_state = json.loads(
            (data_dir / "runtime" / "lens-host-supervisor" / "status.json").read_text(encoding="utf-8-sig")
        )
        assert supervisor_state["status"] == "resident_supervising"
        assert supervisor_state["host_mode"] == "resident"
        assert supervisor_state["supervisor_pid"] == payload["supervisor_pid"]
        assert supervisor_state["supervisor_process_alive"] is True
        assert supervisor_state["resident_supervised_runtime"] is True
        assert supervisor_state["resident_claim_allowed"] is False
        assert supervisor_state["lease_mode"] == "explicit_stop"
        assert supervisor_state["heartbeat_interval_ms"] == 500
        assert supervisor_state["heartbeat_count"] >= 0
        assert supervisor_state["last_heartbeat_at"] == supervisor_state["updated_at"]

        supervisor_heartbeat = _wait_for_supervisor_heartbeat(
            data_dir / "runtime" / "lens-host-supervisor" / "status.json",
            initial_updated_at=str(supervisor_state["updated_at"]),
            initial_heartbeat_count=int(supervisor_state["heartbeat_count"]),
        )
        assert supervisor_heartbeat["status"] == "resident_supervising"
        assert supervisor_heartbeat["host_mode"] == "resident"
        assert supervisor_heartbeat["supervisor_pid"] == payload["supervisor_pid"]
        assert supervisor_heartbeat["supervisor_process_alive"] is True
        assert supervisor_heartbeat["observed_pid"] == supervisor_state["observed_pid"]
        assert supervisor_heartbeat["resident_supervised_runtime"] is True
        assert supervisor_heartbeat["resident_claim_allowed"] is False
        assert supervisor_heartbeat["lease_mode"] == "explicit_stop"
        assert supervisor_heartbeat["supervision_started_at"] == supervisor_state["supervision_started_at"]
        assert supervisor_heartbeat["last_heartbeat_at"] == supervisor_heartbeat["updated_at"]

        governance = payload["governance"]
        assert governance["product_execution_authority"] is False
        assert governance["approval_decision_authority"] is False
        assert governance["local_process_launch_authority"] is True
        assert governance["process_supervision_authority"] is True
        assert governance["process_restart_authority"] is False
        assert governance["service_install_authority"] is False
        assert governance["service_control_authority"] is False
        assert governance["tray_registration_authority"] is False
        assert governance["hotkey_registration_authority"] is False
        assert governance["overlay_control_authority"] is False
        assert governance["summon_authority"] is False
        assert governance["memory_write"] is False
        assert governance["resident_claim_authority"] is False
    finally:
        stopped = _run_script(
            "lens-host-supervisor.ps1",
            "-Mode",
            "StopResident",
            "-DataDir",
            str(data_dir),
            timeout=90,
        )

    assert stopped.returncode == 0, stopped.stderr or stopped.stdout
    stop_payload = json.loads(stopped.stdout)
    assert stop_payload["status"] == "resident_supervision_stopped"
    assert stop_payload["ok"] is True
    assert stop_payload["supervisor_pid"] == payload["supervisor_pid"]
    assert stop_payload["resident_host_process"] is False
    assert stop_payload["resident_supervised_runtime"] is False
    assert stop_payload["supervisor_process_alive"] is False
    assert stop_payload["proof"]["stopped_state_status"] == "resident_stopped"
    assert stop_payload["proof"]["stopped_process_alive"] is False
    assert stop_payload["proof"]["pid_file_present_after_stop"] is False
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()

    stopped_supervisor_state = json.loads(
        (data_dir / "runtime" / "lens-host-supervisor" / "status.json").read_text(encoding="utf-8-sig")
    )
    assert stopped_supervisor_state["status"] == "resident_supervision_stopped"
    assert stopped_supervisor_state["supervisor_pid"] == payload["supervisor_pid"]
    assert stopped_supervisor_state["resident_supervised_runtime"] is False
