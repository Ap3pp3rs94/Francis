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
    assert payload["requirements_ready_total"] >= 5
    assert payload["requirements_blocked_total"] >= 5
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
    assert requirements["process_supervision_enabled"]["ready"] is True
    assert requirements["persistent_supervision_enabled"]["ready"] is True
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
    assert resident_host["resident_runtime_candidate_supervised"] is False
    assert resident_host["fresh_resident_runtime_candidate_supervised"] is False
    assert resident_host["supervision_execution_receipt_observed"] is False
    assert resident_host["supervision_execution_receipt_id"] == ""
    assert resident_host["supervision_execution_readback_status"] == "empty"
    assert resident_host["supervision_execution_next_smallest_truthful_gap"] == ""
    assert resident_host["read_only_contract"] is True
    assert resident_host["diagnostic_only"] is True
    assert resident_host["would_execute"] is False
    assert resident_host["would_mutate"] is False

    tray = dependencies["tray_presence"]
    assert tray["route"] == "/lens/tray"
    assert tray["readiness_route"] == "/lens/tray/readiness"
    assert tray["blocker"] == "tray_host_missing"
    assert tray["requirement_state"] == "tray_host_disabled"
    assert tray["blocked_reason"] == "lens_tray_presence_disabled_pending_authority"
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
    assert summon["requirement_state"] == "disabled_pending_authority"
    assert summon["blocked_reason"] == "lens_summon_binding_disabled_pending_authority"
    assert summon["summon_runner"] == "scripts/lens-summon.ps1"
    assert summon["local_palette_launcher"] == "scripts/lens-command-palette.ps1 -Mode LocalOpen"
    assert summon["summon_authority"] is False
    assert summon["local_process_launch_authority"] is False

    assert payload["first_missing_requirement_handoff"] == resident_host

    assert "persistent_supervision_required_prerequisites_missing" in payload["blockers"]
    assert "process_restart_authority_not_granted" in payload["blockers"]
    assert "service_install_authority_not_granted" in payload["blockers"]
    assert "service_control_authority_not_granted" in payload["blockers"]
    assert "receipt_write_authority_not_granted" in payload["blockers"]
    assert "resident_claim_authority_not_granted" in payload["blockers"]
    assert payload["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    assert payload["current_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    assert payload["current_truthful_gap_basis"] == "missing_required_before_enable"
    assert payload["current_first_missing_requirement"] == "resident_host_process"
    assert payload["current_first_missing_truthful_gap"] == "resident_host_process_not_supervised"
    assert (
        payload["raw_persistent_supervision_next_smallest_truthful_gap"]
        == "persistent_supervision_required_prerequisites_missing"
    )

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


def test_lens_persistent_supervision_plan_accepts_supervised_resident_host_readback(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    host_root = data_root / "runtime" / "lens-host"
    supervisor_root = data_root / "runtime" / "lens-host-supervisor"
    host_root.mkdir(parents=True)
    supervisor_root.mkdir(parents=True)
    now = int(time.time())
    pid = os.getpid()

    (host_root / "lens-host.pid").write_text(str(pid), encoding="utf-8")
    (host_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.runtime_state",
                "status": "resident_running",
                "mode": "resident",
                "pid": pid,
                "process_alive": True,
                "resident": True,
                "updated_at": now,
            }
        ),
        encoding="utf-8",
    )
    (supervisor_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.supervisor_state",
                "status": "resident_supervising",
                "mode": "supervise_resident",
                "host_mode": "resident",
                "observed_pid": pid,
                "observed_state": "resident_running",
                "resident_supervised_runtime": True,
                "process_supervision_authority": True,
                "updated_at": now,
            }
        ),
        encoding="utf-8",
    )

    proc = _run_script("-Mode", "Status", env={**os.environ, "FRANCIS_DATA_DIR": str(data_root)})

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "blocked"
    assert payload["required_before_enable_ready"] is False
    assert payload["missing_required_before_enable"] == [
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert payload["first_missing_required_before_enable"] == "tray_presence"
    assert payload["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"

    dependencies = {item["id"]: item for item in payload["enablement_dependency_readback"]}
    resident_host = dependencies["resident_host_process"]
    assert resident_host["ready"] is True
    assert resident_host["status"] == "ready"
    assert resident_host["blocker"] == ""
    assert resident_host["requirement_state"] == "ready"
    assert resident_host["blocked_reason"] == ""
    assert resident_host["proof_script"] == ""
    assert resident_host["process_alive"] is True
    assert resident_host["pid"] == pid
    assert resident_host["runtime_status"] == "resident_running"
    assert resident_host["next_smallest_truthful_gap"] == ""
    assert resident_host["resident_supervised_runtime"] is True
    assert resident_host["supervision_observed_pid"] == pid
    assert resident_host["resident_runtime_candidate_supervised"] is False
    assert resident_host["fresh_resident_runtime_candidate_supervised"] is False
    assert resident_host["supervision_execution_receipt_observed"] is False
    assert resident_host["supervisor_freshness_status"] == "fresh"
    assert resident_host["read_only_contract"] is True
    assert resident_host["diagnostic_only"] is True
    assert resident_host["would_execute"] is False
    assert resident_host["would_mutate"] is False

    assert payload["first_missing_requirement_handoff"]["id"] == "tray_presence"


def test_lens_persistent_supervision_plan_accepts_live_tray_runtime_readback(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    host_root = data_root / "runtime" / "lens-host"
    supervisor_root = data_root / "runtime" / "lens-host-supervisor"
    tray_root = data_root / "runtime" / "lens-tray"
    host_root.mkdir(parents=True)
    supervisor_root.mkdir(parents=True)
    tray_root.mkdir(parents=True)
    now = int(time.time())
    pid = os.getpid()

    (host_root / "lens-host.pid").write_text(str(pid), encoding="utf-8")
    (host_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.runtime_state",
                "status": "resident_running",
                "mode": "resident",
                "pid": pid,
                "process_alive": True,
                "resident": True,
                "updated_at": now,
            }
        ),
        encoding="utf-8",
    )
    (supervisor_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.supervisor_state",
                "status": "resident_supervising",
                "mode": "supervise_resident",
                "host_mode": "resident",
                "observed_pid": pid,
                "observed_state": "resident_running",
                "resident_supervised_runtime": True,
                "process_supervision_authority": True,
                "updated_at": now,
            }
        ),
        encoding="utf-8",
    )
    (tray_root / "lens-tray.pid").write_text(str(pid), encoding="utf-8")
    (tray_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.tray.runtime_state",
                "status": "tray_running",
                "pid": pid,
                "tray_icon_visible": True,
                "updated_at": now,
            }
        ),
        encoding="utf-8",
    )

    proc = _run_script("-Mode", "Status", env={**os.environ, "FRANCIS_DATA_DIR": str(data_root)})

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "blocked"
    assert payload["required_before_enable_ready"] is False
    assert payload["missing_required_before_enable"] == [
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert payload["first_missing_required_before_enable"] == "global_hotkey_binding"
    assert payload["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"

    dependencies = {item["id"]: item for item in payload["enablement_dependency_readback"]}
    resident_host = dependencies["resident_host_process"]
    assert resident_host["ready"] is True
    assert resident_host["resident_supervised_runtime"] is True

    tray = dependencies["tray_presence"]
    assert tray["ready"] is True
    assert tray["status"] == "ready"
    assert tray["blocker"] == ""
    assert tray["requirement_state"] == "ready"
    assert tray["blocked_reason"] == ""
    assert tray["tray_presence_source"] == "live_runtime_readback"
    assert tray["tray_config_ready"] is False
    assert tray["tray_runtime_ready"] is True
    assert tray["tray_runtime_process_alive"] is True
    assert tray["tray_runtime_icon_visible"] is True
    assert tray["tray_runtime_pid"] == pid
    assert tray["tray_runtime_status"] == "tray_running"
    assert tray["tray_runtime_status_kind"] == "lens.tray.runtime_state"
    assert tray["tray_runtime_state_exists"] is True
    assert tray["tray_runtime_status_pid_matches_pid_file"] is True
    assert payload["first_missing_requirement_handoff"]["id"] == "global_hotkey_binding"


def test_lens_persistent_supervision_plan_accepts_live_surface_runtime_readbacks(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    host_root = data_root / "runtime" / "lens-host"
    supervisor_root = data_root / "runtime" / "lens-host-supervisor"
    tray_root = data_root / "runtime" / "lens-tray"
    hotkey_root = data_root / "runtime" / "lens-hotkey"
    overlay_root = data_root / "runtime" / "lens-overlay"
    host_root.mkdir(parents=True)
    supervisor_root.mkdir(parents=True)
    tray_root.mkdir(parents=True)
    hotkey_root.mkdir(parents=True)
    overlay_root.mkdir(parents=True)
    now = int(time.time())
    pid = os.getpid()

    (host_root / "lens-host.pid").write_text(str(pid), encoding="utf-8")
    (host_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.runtime_state",
                "status": "resident_running",
                "mode": "resident",
                "pid": pid,
                "process_alive": True,
                "resident": True,
                "updated_at": now,
            }
        ),
        encoding="utf-8",
    )
    (supervisor_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.supervisor_state",
                "status": "resident_supervising",
                "mode": "supervise_resident",
                "host_mode": "resident",
                "observed_pid": pid,
                "observed_state": "resident_running",
                "resident_supervised_runtime": True,
                "process_supervision_authority": True,
                "updated_at": now,
            }
        ),
        encoding="utf-8",
    )
    (tray_root / "lens-tray.pid").write_text(str(pid), encoding="utf-8")
    (tray_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.tray.runtime_state",
                "status": "tray_running",
                "pid": pid,
                "tray_icon_visible": True,
                "updated_at": now,
            }
        ),
        encoding="utf-8",
    )
    (hotkey_root / "lens-hotkey.pid").write_text(str(pid), encoding="utf-8")
    (hotkey_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.hotkey.runtime_state",
                "status": "hotkey_bound",
                "pid": pid,
                "global_hotkey": "Ctrl+Alt+Space",
                "binding_scope": "global",
                "hotkey_bound": True,
                "launch_on_hotkey": False,
                "updated_at": now,
            }
        ),
        encoding="utf-8",
    )
    (overlay_root / "lens-overlay.pid").write_text(str(pid), encoding="utf-8")
    (overlay_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.overlay.runtime_state",
                "status": "overlay_running",
                "pid": pid,
                "overlay_name": "Francis Lens Overlay",
                "overlay_scope": "user_session",
                "overlay_window_visible": True,
                "always_on_top": True,
                "updated_at": now,
            }
        ),
        encoding="utf-8",
    )

    proc = _run_script("-Mode", "Status", env={**os.environ, "FRANCIS_DATA_DIR": str(data_root)})

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "blocked"
    assert payload["required_before_enable_ready"] is False
    assert payload["missing_required_before_enable"] == ["summon_binding"]
    assert payload["first_missing_required_before_enable"] == "summon_binding"

    dependencies = {item["id"]: item for item in payload["enablement_dependency_readback"]}
    hotkey = dependencies["global_hotkey_binding"]
    assert hotkey["ready"] is True
    assert hotkey["status"] == "ready"
    assert hotkey["blocker"] == ""
    assert hotkey["requirement_state"] == "ready"
    assert hotkey["global_hotkey_source"] == "live_runtime_readback"
    assert hotkey["hotkey_config_ready"] is False
    assert hotkey["hotkey_runtime_ready"] is True
    assert hotkey["hotkey_runtime_process_alive"] is True
    assert hotkey["hotkey_runtime_bound"] is True
    assert hotkey["hotkey_runtime_pid"] == pid
    assert hotkey["hotkey_runtime_status"] == "hotkey_bound"
    assert hotkey["hotkey_runtime_state_exists"] is True
    assert hotkey["hotkey_runtime_status_pid_matches_pid_file"] is True

    overlay = dependencies["overlay_window"]
    assert overlay["ready"] is True
    assert overlay["status"] == "ready"
    assert overlay["blocker"] == ""
    assert overlay["requirement_state"] == "ready"
    assert overlay["overlay_window_source"] == "live_runtime_readback"
    assert overlay["overlay_config_ready"] is False
    assert overlay["overlay_runtime_ready"] is True
    assert overlay["overlay_runtime_process_alive"] is True
    assert overlay["overlay_runtime_window_visible"] is True
    assert overlay["overlay_runtime_always_on_top"] is True
    assert overlay["overlay_runtime_pid"] == pid
    assert overlay["overlay_runtime_status"] == "overlay_running"
    assert overlay["overlay_runtime_state_exists"] is True
    assert overlay["overlay_runtime_status_pid_matches_pid_file"] is True

    assert payload["first_missing_requirement_handoff"]["id"] == "summon_binding"


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
    assert payload["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
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
    assert requirements["process_supervision_enabled"]["ready"] is True
    assert requirements["persistent_supervision_enabled"]["ready"] is True
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

    assert payload["blocked_requirements"] == []
    assert payload["requirements_ready_total"] == payload["requirements_total"]
    assert "persistent_supervision_required_prerequisites_missing" in payload["blockers"]
    assert "process_supervision_disabled" not in payload["blockers"]
    assert "persistent_supervision_disabled" not in payload["blockers"]
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


def test_lens_persistent_supervision_plan_promotes_supervision_execution_receipt_handoff(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    receipt_root = data_root / "lens" / "host_supervision_executions"
    receipt_root.mkdir(parents=True)
    receipt_id = "lens-host-supervision-execution-test"
    (receipt_root / f"{receipt_id}.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.supervision.execution.receipt",
                "receipt_id": receipt_id,
                "status": "resident_candidate_supervised_not_persistent",
                "created_ts": int(time.time()),
                "execution": {
                    "bounded_supervised_session": True,
                    "temporary_host_process_observed": True,
                    "resident_runtime_candidate_supervised": True,
                    "resident_supervised_runtime": False,
                    "resident_claim_allowed": False,
                    "next_smallest_truthful_gap": "resident_supervision_not_persistent",
                },
                "resident_claim": {
                    "resident_host_process_claimed": False,
                    "resident_runtime_claimed": False,
                    "resident_claim_authority": False,
                },
            }
        ),
        encoding="utf-8",
    )

    proc = _run_script("-Mode", "Status", env={**os.environ, "FRANCIS_DATA_DIR": str(data_root)})

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "blocked"
    assert payload["required_before_enable_ready"] is False
    assert payload["missing_required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert payload["first_missing_required_before_enable"] == "resident_host_process"
    assert payload["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"

    resident_host = {item["id"]: item for item in payload["enablement_dependency_readback"]}["resident_host_process"]
    assert payload["first_missing_requirement_handoff"] == resident_host
    assert resident_host["blocker"] == "resident_supervision_not_persistent"
    assert resident_host["requirement_state"] == "resident_candidate_observed_not_persistent"
    assert resident_host["blocked_reason"] == "resident_supervision_not_persistent"
    assert resident_host["proof_script"] == (
        "scripts/lens-resident-supervision-persistence-boundary-proof.ps1 -Mode Status"
    )
    assert resident_host["next_smallest_truthful_gap"] == "resident_supervision_not_persistent"
    assert resident_host["resident_runtime_candidate_supervised"] is True
    assert resident_host["fresh_resident_runtime_candidate_supervised"] is False
    assert resident_host["supervision_execution_receipt_observed"] is True
    assert resident_host["supervision_execution_receipt_id"] == receipt_id
    assert resident_host["supervision_execution_readback_status"] == "receipt_observed"
    assert resident_host["supervision_execution_next_smallest_truthful_gap"] == ("resident_supervision_not_persistent")
    assert resident_host["read_only_contract"] is True
    assert resident_host["diagnostic_only"] is True
    assert resident_host["would_execute"] is False
    assert resident_host["would_mutate"] is False

    plan = payload["plan"]
    assert plan["would_install_service"] is False
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
