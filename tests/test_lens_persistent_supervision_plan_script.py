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
    expected_required_before_enable = [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert payload["required_before_enable_ready"] is False
    assert payload["required_before_enable"] == expected_required_before_enable
    assert payload["missing_required_before_enable"] == expected_required_before_enable
    assert payload["first_missing_required_before_enable"] == "resident_host_process"
    assert (
        payload["required_before_enable_guard_next_smallest_truthful_gap"]
        == "persistent_supervision_required_prerequisites_missing"
    )

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

    dependencies = {item["id"]: item for item in payload["enablement_dependency_readback"]}
    assert set(dependencies) == set(expected_required_before_enable)
    resident_host = dependencies["resident_host_process"]
    assert resident_host["family"] == "resident_host"
    assert resident_host["route"] == "/lens/host"
    assert resident_host["readiness_route"] == "/lens/host/runtime-loop/readiness"
    assert resident_host["proof_script"] == "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status"
    assert resident_host["ready"] is False
    assert resident_host["status"] == "blocked"
    assert resident_host["blocker"] == "resident_host_process_missing"
    assert resident_host["requirement_state"] == "missing"
    assert resident_host["blocked_reason"] == "resident_host_process_missing"
    assert resident_host["process_alive"] is False
    assert resident_host["next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert resident_host["read_only_contract"] is True
    assert resident_host["diagnostic_only"] is True
    assert resident_host["would_execute"] is False
    assert resident_host["would_mutate"] is False

    tray = dependencies["tray_presence"]
    assert tray["route"] == "/lens/tray"
    assert tray["readiness_route"] == "/lens/tray/readiness"
    assert tray["blocker"] == "tray_host_missing"
    assert tray["requirement_state"] == "tray_host_disabled"
    assert tray["blocked_reason"] == "lens_tray_presence_not_implemented"
    assert tray["tray_registration_authority"] is False
    assert tray["tray_icon_authority"] is False

    hotkey = dependencies["global_hotkey_binding"]
    assert hotkey["route"] == "/lens/summon"
    assert hotkey["readiness_route"] == "/lens/summon/readiness"
    assert hotkey["blocker"] == "global_hotkey_binding_missing"
    assert hotkey["requirement_state"] == "binding_disabled"
    assert hotkey["global_hotkey"] == "Ctrl+Alt+Space"
    assert hotkey["hotkey_registration_authority"] is False

    overlay = dependencies["overlay_window"]
    assert overlay["route"] == "/lens/overlay"
    assert overlay["readiness_route"] == "/lens/overlay/readiness"
    assert overlay["blocker"] == "overlay_window_missing"
    assert overlay["requirement_state"] == "window_disabled"
    assert overlay["overlay_control_authority"] is False
    assert overlay["window_management_authority"] is False

    summon = dependencies["summon_binding"]
    assert summon["route"] == "/lens/summon"
    assert summon["readiness_route"] == "/lens/summon/readiness"
    assert summon["blocker"] == "summon_binding_missing"
    assert summon["requirement_state"] == "not_implemented"
    assert summon["summon_authority"] is False
    assert summon["local_process_launch_authority"] is False

    assert payload["first_missing_requirement_handoff"] == resident_host

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
    assert payload["required_before_enable_ready"] is False
    assert payload["missing_required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert (
        payload["required_before_enable_guard_next_smallest_truthful_gap"]
        == "persistent_supervision_required_prerequisites_missing"
    )

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
