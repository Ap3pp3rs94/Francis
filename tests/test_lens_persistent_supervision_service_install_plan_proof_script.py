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


def _run_proof(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-persistent-supervision-service-install-plan-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=60,
    )


def test_lens_persistent_supervision_service_install_plan_proof_reads_disabled_plan() -> None:
    proc = _run_proof("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.persistent_supervision_service_install_plan.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["service_config"] == "config/runtime/services/lens-host.json"
    assert payload["service_install_script"] == "scripts/service-install.ps1"
    assert payload["windows_service_supported"] is (os.name == "nt")
    assert payload["service_install_plan_supported"] is (os.name == "nt")
    if os.name == "nt":
        assert payload["service_install_report"]
    else:
        assert payload["service_install_report"] == ""
    assert payload["service_name"] == "Francis-LensHost"
    expected_service_plan_status = "blocked" if os.name == "nt" else "unsupported_platform"
    assert payload["service_plan_status"] == expected_service_plan_status
    assert payload["service_plan_ready"] is False
    assert payload["service_plan_would_install"] is False
    assert payload["service_plan_would_start"] is False
    assert payload["process_supervision_enabled"] is False
    assert payload["persistent_supervision_enabled"] is False
    assert payload["persistent_supervision_enablement_disabled"] is True
    assert payload["installable"] is False
    assert payload["install_authority"] is False
    assert payload["service_install_authority"] is False
    assert payload["service_control_authority"] is False
    assert payload["wrapper_created_by_proof"] is False
    assert payload["next_smallest_truthful_gap"] == "persistent_supervision_enablement_disabled"
    assert payload["required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    if os.name == "nt":
        assert set(payload["blocked_by"]) == {
            "installable_false",
            "install_authority_false",
            "service_install_authority_false",
            "service_control_authority_false",
        }
    else:
        assert payload["blocked_by"] == ["unsupported_platform"]
    assert all(item["passed"] for item in payload["checks"])

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["lens_host_service_config_disabled"]["status"] == "disabled"
    expected_plan_check_status = "blocked" if os.name == "nt" else "unsupported_platform"
    expected_governance_check_status = "read_only_bounded" if os.name == "nt" else "unsupported_platform"
    assert checks["service_install_plan_blocked"]["status"] == expected_plan_check_status
    assert checks["service_install_plan_governance"]["status"] == expected_governance_check_status
    assert checks["service_wrapper_not_created"]["status"] == "not_created"

    assert payload["governance"] == {
        "diagnostic_only": True,
        "read_only_contract": True,
        "wraps_service_install_plan": os.name == "nt",
        "windows_service_supported": os.name == "nt",
        "service_install_plan_supported": os.name == "nt",
        "service_config_readback": True,
        "execution_authority": False,
        "approval_decision_authority": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "persistent_supervision_enablement_authority": False,
        "persistent_supervision_execution_authority": False,
        "service_config_write_authority": False,
        "memory_write": False,
        "receipt_write_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
    }
