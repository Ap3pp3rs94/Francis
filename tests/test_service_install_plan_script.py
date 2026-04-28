from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


def _powershell() -> str:
    exe = shutil.which("pwsh")
    if not exe:
        pytest.skip("PowerShell 7 is not available")
    return exe


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_service_install_plan_accepts_lens_host_config_without_mutation(tmp_path: Path) -> None:
    if os.name != "nt":
        pytest.skip("Windows service planning is only asserted on Windows")

    root = tmp_path / "francis-root"
    script_dir = root / "scripts"
    script_dir.mkdir(parents=True)
    (script_dir / "lens-host.ps1").write_text("'status only'\n", encoding="utf-8")

    config_dir = root / "config" / "runtime" / "services"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "lens-host.json"
    config_path.write_text(
        json.dumps(
            {
                "kind": "lens.host.service_config",
                "version": 1,
                "enabled": False,
                "service_name": "Francis-LensHost",
                "display_name": "Francis Lens Host",
                "description": "Disabled readiness baseline for the future resident Lens host.",
                "service_executable": _powershell(),
                "service_arguments": [
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "scripts/lens-host.ps1",
                    "-Mode",
                    "Foreground",
                ],
                "working_dir": str(root),
                "use_wrapper": True,
                "start_type": "Manual",
                "installable": False,
                "install_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "start_after_install": False,
                "blocked_reason": "lens_host_runtime_not_implemented",
            }
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "service-install.ps1"),
            "-Mode",
            "Plan",
            "-Root",
            str(root),
            "-ConfigPath",
            str(config_path),
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 0, proc.stderr
    reports = sorted((root / "data" / "logs" / "operations").glob("service_install_report_*.json"))
    assert reports, proc.stdout
    report = json.loads(reports[-1].read_text(encoding="utf-8-sig"))
    assert report["mode"] == "Plan"
    assert len(report["plans"]) == 1
    plan = report["plans"][0]
    assert plan["kind"] == "service_install.plan"
    assert plan["service"] == "Francis-LensHost"
    assert plan["status"] == "blocked"
    assert plan["ready"] is False
    assert plan["would_install"] is False
    assert plan["would_start"] is False
    assert plan["executable"]["exists"] is True
    assert "-Mode Foreground" in plan["service_command"]
    assert plan["wrapper"]["enabled"] is True
    assert plan["wrapper"]["would_write"] is False
    assert "installable_false" in plan["blocked_by"]
    assert "service_install_authority_false" in plan["blocked_by"]
    assert "service_control_authority_false" in plan["blocked_by"]
    assert plan["governance"] == {
        "read_only_contract": True,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "local_process_launch_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "mutation_authority_granted": False,
    }
    assert not (root / "data" / "runtime" / "services" / "Francis-LensHost" / "run.cmd").exists()
