from __future__ import annotations

import json
import platform
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
            str(_repo_root() / "scripts" / "lens-resident-runtime-api-execution-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=240,
    )


def test_lens_resident_runtime_api_execution_proof_uses_governed_routes() -> None:
    script = (_repo_root() / "scripts" / "lens-resident-runtime-api-execution-proof.ps1").read_text(encoding="utf-8")

    assert '"/lens/host/supervision/authority/request"' in script
    assert '"/lens/resident-runtime/authority-grant/request"' in script
    assert '"/lens/resident-runtime/execute"' in script
    assert '"/lens/host/supervision/execute"' in script
    assert '"mode": "resident_stop"' in script
    assert '"summon_anywhere": False' in script
    assert '"resident_claim_authority": False' in script


def test_lens_resident_runtime_api_execution_proof_starts_and_stops_real_supervisor(
    tmp_path: Path,
) -> None:
    if platform.system() != "Windows":
        pytest.skip("Live Lens resident runtime API execution proof is Windows-hosted.")

    data_dir = tmp_path / "data"
    proc = _run_proof(
        "-Mode",
        "Status",
        "-RunSeconds",
        "1",
        "-DataDir",
        str(data_dir),
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.resident_runtime.api_execution.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["acceptance_criterion"] == "summon_anywhere"
    assert payload["previous_next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert payload["next_smallest_truthful_gap"] == "summon_tray_presence_blocker_boundary"
    assert payload["recommended_next_slice"] == "prove_governed_tray_presence_api_execution_after_resident_supervision"
    assert payload["recommended_proof_script"] == "scripts/lens-tray-presence-api-execution-proof.ps1 -Mode Status"
    assert payload["recommended_handoff_source"] == "api_resident_runtime_execution_tray_presence_handoff"
    handoff = payload["recommended_handoff"]
    assert handoff["id"] == "tray_presence"
    assert handoff["status"] == "blocked"
    assert handoff["authority_required"] == "tray_registration_authority"
    assert handoff["authority_granted"] is False
    assert handoff["would_execute"] is False
    assert handoff["would_mutate"] is False

    assert payload["host_supervision_authority_grant_receipt_id"]
    assert payload["resident_runtime_authority_grant_receipt_id"]
    assert payload["resident_runtime_execution_authority"] is True
    assert payload["host_supervision_authority"] is True
    assert payload["resident_runtime_plan_ready"] is True
    assert payload["execution_applied"] is True
    assert payload["executed"] is True
    assert payload["resident_host_process_started"] is True
    assert payload["resident_supervised_runtime_started"] is True
    assert payload["resident_supervision_stop_observed"] is True
    assert payload["resident_host_process_after_stop"] is False
    assert payload["resident_supervised_runtime_after_stop"] is False
    assert payload["pid_file_present_after_start"] is True
    assert payload["pid_file_present_after_stop"] is False
    assert payload["tray_presence"] is False
    assert payload["global_hotkey"] is False
    assert payload["overlay_window"] is False
    assert payload["summon_anywhere"] is False
    assert payload["service_managed"] is False
    assert payload["resident_claim_allowed"] is False

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["host_supervision_authority_granted"]["status"] == "authority_granted"
    assert checks["resident_runtime_authority_granted"]["status"] == "authority_granted"
    assert checks["runtime_plan_ready_for_bounded_candidate"]["status"] == "ready"
    assert checks["api_execute_started_real_resident_supervision"]["status"] == "resident_supervision_started"
    assert checks["runtime_receipt_readback_after_start"]["status"] == "readback_ready"
    assert checks["api_stop_cleaned_real_resident_supervision"]["status"] == "resident_supervision_stopped"
    assert checks["status_receipt_readback_observed"]["status"] == "readback_ready"
    assert checks["authority_boundaries_intact"]["status"] == "bounded"
    assert checks["surface_claims_false"]["status"] == "bounded"
    assert all(item["passed"] for item in payload["checks"])

    assert "tray_host_missing" in payload["blockers"]
    assert "global_hotkey_binding_missing" in payload["blockers"]
    assert "overlay_window_missing" in payload["blockers"]
    assert "summon_binding_missing" in payload["blockers"]
    assert "service_control_authority_not_granted" in payload["blockers"]

    proof = payload["proof"]
    assert proof["start_status"] == "resident_supervision_started"
    assert proof["host_supervision_execution_status"] == "resident_supervision_started"
    assert proof["runner_status"] == "resident_supervision_started"
    assert proof["host_state_after_start"] == "resident_running"
    assert proof["supervisor_state_after_start"] == "resident_supervising"
    assert proof["stop_status"] == "resident_supervision_stopped"
    assert proof["host_state_after_stop"] == "resident_stopped"
    assert proof["supervisor_state_after_stop"] == "resident_supervision_stopped"
    assert proof["receipt_readback_status"] == "readback_ready"
    assert proof["receipt_readback_next_gap"] == "summon_tray_presence_blocker_boundary"
    assert proof["status_receipt_readback_status"] == "readback_ready"
    assert proof["status_receipt_count"] >= 1

    assert payload["start_execution"] == {
        "status": "resident_supervision_started",
        "next_smallest_truthful_gap": "summon_tray_presence_blocker_boundary",
        "resident_host_process": True,
        "resident_supervised_runtime": True,
        "resident_claim_allowed": False,
        "stop_command": "scripts/lens-host-supervisor.ps1 -Mode StopResident",
    }
    assert payload["stop_execution"] == {
        "status": "resident_supervision_stopped",
        "resident_host_process": False,
        "resident_supervised_runtime": False,
        "resident_claim_allowed": False,
    }
    assert payload["governance"] == {
        "diagnostic_only": True,
        "api_route_proof": True,
        "api_execution_authority": True,
        "approval_request_write": True,
        "test_fixture_approval_decisions": True,
        "approval_decision_authority": False,
        "product_execution_authority": False,
        "execution_authority": True,
        "temporary_runtime_state_write": True,
        "local_process_launch_authority": True,
        "process_supervision_authority": True,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "tray_registration_authority": False,
        "hotkey_registration_authority": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "memory_write": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": True,
    }

    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()
    supervisor_state = json.loads(
        (data_dir / "runtime" / "lens-host-supervisor" / "status.json").read_text(encoding="utf-8-sig")
    )
    assert supervisor_state["resident_supervised_runtime"] is False
