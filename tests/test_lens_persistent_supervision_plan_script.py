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


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-persistent-supervision-plan.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )


def test_lens_persistent_supervision_plan_stays_blocked_without_authority() -> None:
    proc = _run_script("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.persistent_supervision_plan"
    assert payload["status"] == "blocked"
    assert payload["plan_available"] is True
    assert payload["persistent_supervision_ready"] is False
    assert payload["resident_claim_allowed"] is False
    assert payload["config_present"] is True
    assert payload["host_entrypoint_present"] is True
    assert payload["service_manager_present"] is True
    assert payload["service_name"] == "Francis-LensHost"
    assert "scripts/lens-host.ps1" in payload["planned_command"]
    assert payload["requirements_total"] >= 10
    assert payload["requirements_ready_total"] >= 3
    assert payload["requirements_blocked_total"] >= 7

    requirements = {item["id"]: item for item in payload["requirements"]}
    assert requirements["service_config"]["ready"] is True
    assert requirements["host_entrypoint"]["ready"] is True
    assert requirements["service_manager"]["ready"] is True
    assert requirements["process_supervision_enabled"]["ready"] is False
    assert requirements["persistent_supervision_enabled"]["ready"] is False
    assert requirements["process_restart_authority"]["ready"] is False
    assert requirements["service_install_authority"]["ready"] is False
    assert requirements["service_control_authority"]["ready"] is False
    assert requirements["receipt_write_authority"]["ready"] is False
    assert requirements["resident_claim_authority"]["ready"] is False

    assert "process_supervision_disabled" in payload["blockers"]
    assert "persistent_supervision_disabled" in payload["blockers"]
    assert "process_restart_authority_not_granted" in payload["blockers"]
    assert "service_install_authority_not_granted" in payload["blockers"]
    assert "service_control_authority_not_granted" in payload["blockers"]
    assert "receipt_write_authority_not_granted" in payload["blockers"]
    assert "resident_claim_authority_not_granted" in payload["blockers"]
    assert payload["next_smallest_truthful_gap"] == "persistent_supervision_authority_not_granted"

    plan = payload["plan"]
    assert plan["would_install_service"] is False
    assert plan["would_update_service"] is False
    assert plan["would_start_service"] is False
    assert plan["would_restart_process"] is False
    assert plan["would_supervise_process"] is False
    assert plan["would_write_receipt"] is False
    assert plan["would_write_memory"] is False
    assert plan["would_claim_resident"] is False

    assert payload["governance"] == {
        "diagnostic_only": True,
        "read_only_contract": True,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "receipt_write_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
    }
