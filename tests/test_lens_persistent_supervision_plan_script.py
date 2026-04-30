from __future__ import annotations

import json
import os
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


def _run_script(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
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
        env=env,
    )


def test_lens_persistent_supervision_plan_stays_blocked_without_authority(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    proc = _run_script("-Mode", "Status", env={**os.environ, "FRANCIS_DATA_DIR": str(data_root)})

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
    assert payload["data_root"] == str(data_root)
    assert payload["authority_grant_active"] is False
    assert payload["authority_grant_receipt_id"] == ""
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


def test_lens_persistent_supervision_plan_consumes_active_authority_grant_receipt(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    grant_root = data_root / "lens" / "host_supervision_authority_grants"
    grant_root.mkdir(parents=True)
    now = int(time.time())
    receipt_id = "lens-host-supervision-authority-grant-test"
    (grant_root / f"{receipt_id}.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.supervision_authority.grant.receipt",
                "receipt_id": receipt_id,
                "status": "authority_granted",
                "created_ts": now,
                "expires_ts": now + 3600,
                "lease": {
                    "active": True,
                    "lease_seconds": 3600,
                    "created_ts": now,
                    "expires_ts": now + 3600,
                },
                "authority_boundary": {
                    "applied": True,
                    "executed": False,
                    "authority_granted": True,
                },
                "authorities": {
                    "process_supervision_authority": True,
                    "process_restart_authority": True,
                    "service_install_authority": True,
                    "service_control_authority": True,
                    "receipt_write_authority": True,
                    "resident_claim_authority": True,
                },
            }
        ),
        encoding="utf-8",
    )

    proc = _run_script("-Mode", "Status", env={**os.environ, "FRANCIS_DATA_DIR": str(data_root)})

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.persistent_supervision_plan"
    assert payload["status"] == "blocked"
    assert payload["persistent_supervision_ready"] is False
    assert payload["resident_claim_allowed"] is False
    assert payload["authority_grant_active"] is True
    assert payload["authority_grant_receipt_id"] == receipt_id
    assert payload["next_smallest_truthful_gap"] == "persistent_supervision_enablement_disabled"

    requirements = {item["id"]: item for item in payload["requirements"]}
    assert requirements["process_supervision_enabled"]["ready"] is False
    assert requirements["persistent_supervision_enabled"]["ready"] is False
    assert requirements["process_restart_authority"]["ready"] is True
    assert requirements["service_install_authority"]["ready"] is True
    assert requirements["service_control_authority"]["ready"] is True
    assert requirements["receipt_write_authority"]["ready"] is True
    assert requirements["resident_claim_authority"]["ready"] is True
    assert requirements["process_restart_authority"]["authority_granted"] is True
    assert requirements["service_install_authority"]["authority_granted"] is True
    assert requirements["service_control_authority"]["authority_granted"] is True
    assert requirements["receipt_write_authority"]["authority_granted"] is True
    assert requirements["resident_claim_authority"]["authority_granted"] is True

    assert payload["blocked_requirements"] == [
        "process_supervision_enabled",
        "persistent_supervision_enabled",
    ]
    assert payload["requirements_ready_total"] == payload["requirements_total"] - 2
    assert "process_supervision_disabled" in payload["blockers"]
    assert "persistent_supervision_disabled" in payload["blockers"]
    assert "process_restart_authority_not_granted" not in payload["blockers"]
    assert "service_install_authority_not_granted" not in payload["blockers"]
    assert "service_control_authority_not_granted" not in payload["blockers"]
    assert "receipt_write_authority_not_granted" not in payload["blockers"]
    assert "resident_claim_authority_not_granted" not in payload["blockers"]

    plan = payload["plan"]
    assert plan["would_install_service"] is False
    assert plan["would_update_service"] is False
    assert plan["would_start_service"] is False
    assert plan["would_restart_process"] is False
    assert plan["would_supervise_process"] is False
    assert plan["would_write_receipt"] is False
    assert plan["would_write_memory"] is False
    assert plan["would_claim_resident"] is False

    assert payload["governance"]["execution_authority"] is False
    assert payload["governance"]["approval_decision_authority"] is False
    assert payload["governance"]["memory_write"] is False
    assert payload["governance"]["mutation_authority_granted"] is False
