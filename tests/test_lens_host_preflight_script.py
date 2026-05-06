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


def _run_preflight(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-host-preflight.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_host_preflight_reports_blockers_without_authority() -> None:
    proc = _run_preflight("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.lifecycle_preflight"
    assert payload["status"] == "blocked"
    assert payload["ready"] is False
    assert payload["next_smallest_truthful_gap"] == "resident_host_lifecycle_blockers"
    assert payload["service_name"] == "Francis-LensHost"
    assert "lens_host_service_control_not_authorized" in payload["blockers"]
    assert "global_hotkey_binding_missing" in payload["blockers"]
    blocker_groups = payload["blocker_groups"]
    assert "lens_host_runtime_not_implemented" in blocker_groups["runtime"]
    assert isinstance(blocker_groups["process_readback"], list)
    assert "service_control_authority_false" in blocker_groups["service_plan"]
    assert "process_supervision_enabled" in blocker_groups["supervision"]
    assert "persistent_supervision_enabled" in blocker_groups["supervision"]
    assert "process_restart_authority" in blocker_groups["supervision"]
    assert "receipt_write_authority" in blocker_groups["supervision"]
    assert "resident_claim_authority" in blocker_groups["supervision"]
    assert "service_control_authority_false" in blocker_groups["authority"]
    assert "process_restart_authority" in blocker_groups["authority"]
    assert "receipt_write_authority" in blocker_groups["authority"]
    assert "resident_claim_authority" in blocker_groups["authority"]
    assert "tray_host_missing" in blocker_groups["surface_dependencies"]
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["service_config"]["status"] == "present_disabled"
    assert checks["host_entrypoint"]["status"] == "present"
    assert checks["service_manager"]["status"] == "present"
    assert checks["service_status_readback"]["status"] == "ready"
    assert checks["service_plan"]["status"] == "blocked"
    assert checks["install_authority"]["status"] == "blocked"
    assert checks["service_control_authority"]["status"] == "blocked"
    service_plan = payload["service_plan"]
    assert service_plan["kind"] == "service_install.plan_projection"
    assert service_plan["status"] == "blocked"
    assert service_plan["ready"] is False
    assert service_plan["manager"] == "scripts/service-install.ps1"
    assert service_plan["manager_exists"] is True
    assert service_plan["plan_mode"] == "Plan"
    assert service_plan["would_install"] is False
    assert service_plan["would_start"] is False
    assert service_plan["wrapper_would_write"] is False
    assert "-Mode Resident" in service_plan["planned_command"]
    assert "installable_false" in service_plan["blocked_by"]
    assert "service_install_authority_false" in service_plan["blocked_by"]
    assert "service_control_authority_false" in service_plan["blocked_by"]
    assert service_plan["governance"] == {
        "read_only_contract": True,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "local_process_launch_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "wrapper_write_authority": False,
        "mutation_authority_granted": False,
    }
    assert payload["governance"] == {
        "read_only_contract": True,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "local_process_launch_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "mutation_authority_granted": False,
    }


def test_lens_host_preflight_refuses_lifecycle_actions() -> None:
    proc = _run_preflight("-Mode", "Start")

    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.lifecycle_preflight"
    assert payload["status"] == "refused"
    assert payload["ok"] is False
    assert payload["error"] == "lens_host_lifecycle_action_not_authorized"
    assert payload["governance"]["service_control_authority"] is False
    assert payload["governance"]["local_process_launch_authority"] is False
