from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

import pytest

_PROOF_GLOBAL_HOTKEY = "Ctrl+Alt+Shift+F13"


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_proof(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["FRANCIS_PROOF_GLOBAL_HOTKEY"] = _PROOF_GLOBAL_HOTKEY
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-persistent-supervision-api-execution-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        env=env,
        check=False,
        text=True,
        capture_output=True,
        timeout=420,
    )


def test_lens_persistent_supervision_api_execution_proof_uses_governed_routes() -> None:
    script = (_repo_root() / "scripts" / "lens-persistent-supervision-api-execution-proof.ps1").read_text(
        encoding="utf-8"
    )

    assert '"/lens/host/supervision/authority/request"' in script
    assert '"/lens/resident-runtime/authority-grant/request"' in script
    assert '"/lens/resident-runtime/execute"' in script
    assert '"/lens/tray/authority/request"' in script
    assert '"/lens/tray/execute"' in script
    assert '"/lens/os-binding/authority/request"' in script
    assert '"/lens/os-binding/execute"' in script
    assert '"/lens/overlay/authority/request"' in script
    assert '"/lens/overlay/execute"' in script
    assert '"/lens/summon/authority/request"' in script
    assert '"/lens/summon/execute"' in script
    assert '"/lens/host/persistent-supervision/enablement/authority/request"' in script
    assert '"/lens/host/persistent-supervision/enablement/authority"' in script
    assert '"/lens/host/persistent-supervision/enablement/execution/request"' in script
    assert '"/lens/host/persistent-supervision/enablement/execution/authority"' in script
    assert '"/lens/host/persistent-supervision/enablement/execution/readiness"' in script
    assert '"/lens/host/persistent-supervision/enablement/execution"' in script
    assert '"/lens/host/persistent-supervision/enablement/execution/apply"' in script
    assert (
        '"/lens/host/persistent-supervision/enablement/executions?limit=10&approval_id={execution_approval_id}"'
        in script
    )
    assert "dependency_run_seconds = max(run_seconds, 60)" in script
    assert 'proof_global_hotkey = os.environ.get("FRANCIS_PROOF_GLOBAL_HOTKEY", "Ctrl+Alt+Shift+F12").strip()' in script
    assert '"global_hotkey": proof_global_hotkey' in script
    assert "FRANCIS_LENS_HOST_SERVICE_CONFIG_PATH" in script
    assert '"allow_launch": False' in script
    assert '"local_process_launch_authority": False' in script
    assert '"service_control_authority": False' in script
    assert '"memory_write": False' in script
    assert '"resident_claim_authority": False' in script


def test_lens_persistent_supervision_api_execution_proof_executes_isolated_apply(
    tmp_path: Path,
) -> None:
    if platform.system() != "Windows":
        pytest.skip("Live Lens persistent-supervision API execution proof is Windows-hosted.")
    if os.environ.get("CI", "").lower() == "true":
        pytest.skip("Live persistent-supervision proof requires an interactive Windows user session.")

    data_dir = tmp_path / "data"
    live_service_config = _repo_root() / "config" / "runtime" / "services" / "lens-host.json"
    live_service_config_before = live_service_config.read_text(encoding="utf-8")
    proc = _run_proof(
        "-Mode",
        "Status",
        "-RunSeconds",
        "10",
        "-DataDir",
        str(data_dir),
    )
    live_service_config_after = live_service_config.read_text(encoding="utf-8")

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.persistent_supervision.api_execution.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["acceptance_criterion"] == "persistent_supervision_enablement"
    assert payload["global_hotkey"] == _PROOF_GLOBAL_HOTKEY
    assert payload["previous_next_smallest_truthful_gap"] == "persistent_supervision_execution_boundary"
    assert payload["route_next_smallest_truthful_gap"] == "persistent_supervision_execution_boundary"
    assert payload["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert payload["recommended_proof_script"] == "scripts/lens-stage6-completion-audit.ps1 -Mode Status"
    assert payload["recommended_handoff_source"] == "api_persistent_supervision_execution_handoff"
    assert payload["live_service_config_unchanged"] is True
    assert payload["dependency_run_seconds"] == 60
    assert payload["resident_dependency_run_seconds"] == 60
    assert live_service_config_after == live_service_config_before

    assert payload["host_supervision_authority_grant_receipt_id"]
    assert payload["resident_runtime_authority_grant_receipt_id"]
    assert payload["tray_authority_grant_receipt_id"]
    assert payload["os_binding_authority_grant_receipt_id"]
    assert payload["overlay_authority_grant_receipt_id"]
    assert payload["summon_authority_grant_receipt_id"]
    assert payload["persistent_supervision_enablement_authority_grant_receipt_id"]
    assert payload["persistent_supervision_execution_authority_grant_receipt_id"]
    assert payload["resident_runtime_execution_authority"] is True
    assert payload["host_supervision_authority"] is True
    assert payload["tray_presence_authority"] is True
    assert payload["os_binding_authority"] is True
    assert payload["overlay_authority"] is True
    assert payload["summon_authority"] is True
    assert payload["persistent_supervision_enablement_authority"] is True
    assert payload["service_config_write_authority"] is True
    assert payload["persistent_supervision_execution_authority"] is True
    assert payload["receipt_write_authority"] is True
    assert payload["execution_applied"] is True
    assert payload["executed"] is True
    assert payload["resident_host_process_started"] is True
    assert payload["resident_supervised_runtime_started"] is True
    assert payload["tray_presence_started"] is True
    assert payload["tray_runtime_ready"] is True
    assert payload["global_hotkey_bound"] is True
    assert payload["hotkey_runtime_ready"] is True
    assert payload["overlay_window_started"] is True
    assert payload["overlay_runtime_ready"] is True
    assert payload["summon_binding_observed"] is True
    assert payload["summon_runtime_ready"] is True
    assert payload["bounded_handoff_ready"] is True
    assert payload["local_open_ready"] is True
    assert payload["opened"] is False
    assert payload["no_launch"] is True
    assert payload["summon_runtime_state_observed"] is True
    assert payload["required_before_enable_after_summon"] == []
    assert payload["required_before_enable_ready_after_summon"] is True
    assert payload["persistent_supervision_apply_status"] == "service_config_updated"
    assert payload["persistent_supervision_ready_after_apply"] is True
    assert payload["persistent_supervision_enablement_allowed"] is True
    assert payload["service_config_updated"] is True
    assert payload["receipt_written"] is True
    assert payload["resident_claim_allowed"] is False
    assert payload["service_managed"] is False
    assert payload["summon_anywhere"] is False
    assert payload["os_level_summon"] is False
    assert payload["overlay_stop_observed"] is True
    assert payload["hotkey_stop_observed"] is True
    assert payload["tray_presence_stop_observed"] is True
    assert payload["resident_supervision_stop_observed"] is True
    assert payload["overlay_pid_file_present_after_stop"] is False
    assert payload["hotkey_pid_file_present_after_stop"] is False
    assert payload["tray_pid_file_present_after_stop"] is False
    assert payload["host_pid_file_present_after_stop"] is False
    assert "resident_claim_authority_not_granted" in payload["blockers"]

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["authority_chain_granted"]["status"] == "authority_granted"
    assert checks["resident_tray_hotkey_overlay_started_before_apply"]["status"] == "ready"
    assert checks["api_execute_observed_bounded_summon_handoff"]["status"] == "summon_binding_observed"
    assert checks["persistent_plan_consumed_required_runtime_prerequisites"]["status"] == "required_before_enable_clear"
    assert checks["execution_readiness_reaches_resident_claim_boundary"]["status"] == "blocked"
    assert checks["execution_denial_before_apply_preserved"]["status"] == "denied_no_resident_claim_authority"
    assert checks["api_apply_updated_isolated_service_config"]["status"] == "service_config_updated"
    assert checks["status_plan_consumed_persistent_supervision_enablement"]["status"] == (
        "persistent_supervision_execution_boundary"
    )
    assert checks["persistent_execution_receipt_readback"]["status"] == "readback_ready"
    assert checks["isolated_service_config_only"]["status"] == "isolated_temp_config"
    assert checks["api_stop_cleaned_real_overlay_window"]["status"] == "overlay_window_stopped"
    assert checks["api_stop_cleaned_real_global_hotkey"]["status"] == "global_hotkey_binding_stopped"
    assert checks["api_stop_cleaned_real_tray_presence"]["status"] == "tray_presence_stopped"
    assert checks["resident_supervision_stop_observed"]["status"] == "resident_supervision_stopped"
    assert checks["authority_boundaries_intact"]["status"] == "bounded"
    assert all(item["passed"] for item in payload["checks"])

    proof = payload["proof"]
    assert proof["dependency_run_seconds"] == 60
    assert proof["resident_dependency_run_seconds"] == 60
    assert proof["global_hotkey"] == _PROOF_GLOBAL_HOTKEY
    assert proof["resident_start_status"] == "resident_supervision_started"
    assert proof["tray_start_status"] == "tray_presence_started"
    assert proof["hotkey_start_status"] == "global_hotkey_bound"
    assert proof["overlay_start_status"] == "overlay_window_started"
    assert proof["summon_execute_status"] == "summon_binding_observed"
    assert proof["summon_runtime_state_status"] == "summon_binding_observed"
    assert proof["persistent_apply_status"] == "service_config_updated"
    assert proof["persistent_apply_receipt_id"]
    assert proof["persistent_executions_readback_status"] == "readback_ready"
    assert proof["persistent_plan_after_apply_status"] == "ready_for_operator_review"
    assert proof["persistent_plan_after_apply_next_gap"] == "persistent_supervision_execution_boundary"
    assert proof["temp_service_config_process_supervision_enabled"] is True
    assert proof["temp_service_config_persistent_supervision_enabled"] is True
    assert proof["overlay_stop_status"] == "overlay_window_stopped"
    assert proof["hotkey_stop_status"] == "global_hotkey_binding_stopped"
    assert proof["tray_stop_status"] == "tray_presence_stopped"
    assert proof["resident_stop_status"] == "resident_supervision_stopped"

    assert payload["handoff"] == {
        "recommended_handoff_source": "api_persistent_supervision_execution_handoff",
        "status": "audit_needed",
        "previous_next_smallest_truthful_gap": "persistent_supervision_execution_boundary",
        "next_smallest_truthful_gap": "stage6_lens_completion_audit",
        "next_step": "run_stage6_lens_completion_audit_after_persistent_supervision_api_execution",
        "proof_script": "scripts/lens-stage6-completion-audit.ps1 -Mode Status",
        "route": "/lens/host/persistent-supervision/enablement/execution/apply",
        "readiness_route": "/lens/host/persistent-supervision/enablement/execution/readiness",
        "authority_required": "none_new_stage6_completion_audit",
        "authority_granted": False,
        "read_only_contract": True,
        "diagnostic_only": True,
        "would_execute": False,
        "would_mutate": False,
    }
    assert payload["governance"] == {
        "diagnostic_only": True,
        "api_route_proof": True,
        "api_execution_authority": True,
        "approval_request_write": True,
        "test_fixture_approval_decisions": True,
        "approval_decision_authority": False,
        "product_execution_authority": False,
        "execution_authority": False,
        "temporary_runtime_state_write": True,
        "isolated_service_config_write": True,
        "service_config_write_authority": True,
        "service_config_mutation_authority": True,
        "persistent_supervision_enablement_authority": True,
        "persistent_supervision_execution_authority": True,
        "receipt_write_authority": True,
        "local_process_launch_authority": False,
        "process_supervision_authority": True,
        "process_restart_authority": True,
        "service_install_authority": False,
        "service_control_authority": False,
        "tray_registration_authority": True,
        "tray_icon_authority": True,
        "hotkey_registration_authority": True,
        "overlay_control_authority": True,
        "window_management_authority": True,
        "bounded_local_open_handoff_authority": True,
        "summon_authority": True,
        "summon_anywhere_authority": False,
        "os_level_summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "memory_write": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": True,
    }

    temp_service_config = json.loads(Path(payload["service_config_path"]).read_text(encoding="utf-8"))
    assert temp_service_config["process_supervision_enabled"] is True
    assert temp_service_config["persistent_supervision_enabled"] is True
    assert temp_service_config["installable"] is False
    assert temp_service_config["service_control_authority"] is False
    assert temp_service_config["resident_claim_authority"] is False
    assert (data_dir / "runtime" / "lens-summon" / "status.json").exists()
    assert not (data_dir / "runtime" / "lens-overlay" / "lens-overlay.pid").exists()
    assert not (data_dir / "runtime" / "lens-hotkey" / "lens-hotkey.pid").exists()
    assert not (data_dir / "runtime" / "lens-tray" / "lens-tray.pid").exists()
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()
