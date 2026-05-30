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


def _run_proof(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-resident-surface-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=180,
    )


def test_lens_resident_surface_proof_accepts_isolated_data_dir_contract() -> None:
    script = (_repo_root() / "scripts" / "lens-resident-surface-proof.ps1").read_text(encoding="utf-8")

    assert "[string]$DataDir = ''" in script
    assert "$ReadbackDataRoot = [System.IO.Path]::GetFullPath($DataDir)" in script
    assert "Invoke-ResidentSurfaceReadback -DataDir $ReadbackDataRoot" in script


def test_lens_resident_surface_proof_composes_blocked_surface_without_authority() -> None:
    proc = _run_proof("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.resident_surface.readiness_proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    resident_runtime_readback = payload["resident_surface_resident_runtime_readback"]
    assert payload["resident_surface_ready"] is resident_runtime_readback
    assert payload["resident_surface_content_readback"] is True
    assert isinstance(payload["resident_surface_resident_runtime_observed"], bool)
    assert payload["resident_surface_foreground_runtime_readback"] is True
    assert payload["resident_surface_foreground_runtime_observed"] is True
    assert payload["resident_surface_content_contract_ready"] is True
    assert payload["resident_surface_contract_status"] == "readback_ready"
    assert payload["resident_surface_runtime_status"] == (
        "resident_runtime_observed" if resident_runtime_readback else "foreground_runtime_observed"
    )
    assert payload["resident_surface_route"] == "/lens/resident-surface"
    assert isinstance(payload["resident_claim_allowed"], bool)
    assert payload["ready_for_lens_resident_claim"] is payload["resident_claim_allowed"]
    assert isinstance(payload["resident_claim_authority_ready"], bool)
    assert payload["resident_claim_authority"] is payload["resident_claim_authority_ready"]
    assert payload["resident_claim_authority_readiness_route"] == (
        "/lens/host/persistent-supervision/resident-claim/authority/readiness"
    )
    assert isinstance(payload["resident_claim_authority_blockers"], list)
    if payload["resident_claim_allowed"]:
        assert resident_runtime_readback is True
        assert payload["resident_claim_authority_ready"] is True
    assert payload["resident_host_process"] is resident_runtime_readback
    assert payload["foreground_host_process_observed"] is True
    assert payload["foreground_host_runtime_completed"] is True
    assert payload["tray_presence"] is False
    assert payload["tray_icon"] is False
    assert payload["overlay_window"] is False
    assert payload["global_hotkey_bound"] is False
    assert payload["summon_anywhere"] is False
    assert payload["live_http_status_readback"] is True
    assert payload["operator_experience_proof"] is True
    assert payload["live_operator_experience_proof"] is True
    assert payload["live_operator_experience_ready"] is False
    assert payload["next_smallest_truthful_gap"] == (
        "resident_surface_operator_experience_proof"
        if resident_runtime_readback
        else "resident_surface_runtime_not_supervised"
    )
    assert payload["recommended_handoff_source"] == "resident_surface_runtime_supervision_handoff"
    assert payload["recommended_next_slice"] == (
        "prove_resident_surface_operator_experience_before_helpful_not_noisy_claim"
        if resident_runtime_readback
        else "resolve_resident_surface_runtime_supervision_before_helpful_not_noisy_claim"
    )
    assert payload["recommended_proof_script"] == "scripts/lens-resident-surface-proof.ps1 -Mode Status"
    assert payload["authority_required"] == (
        "operator_experience_proof" if resident_runtime_readback else "process_supervision_authority"
    )
    assert payload["authority_granted"] is False
    assert payload["resident_runtime_authority_grant_readiness_route"] == (
        "/lens/resident-runtime/authority-grant/readiness"
    )
    assert payload["resident_runtime_authority_grant_handoff_observed"] is True

    recommended_handoff = payload["recommended_handoff"]
    assert recommended_handoff["id"] == "resident_surface_runtime_supervision"
    assert recommended_handoff["next_smallest_truthful_gap"] == (
        "resident_surface_operator_experience_proof"
        if resident_runtime_readback
        else "resident_surface_runtime_not_supervised"
    )
    assert recommended_handoff["next_step"] == (
        "prove_resident_surface_operator_experience_before_helpful_not_noisy_claim"
        if resident_runtime_readback
        else "resolve_resident_surface_runtime_supervision_before_helpful_not_noisy_claim"
    )
    assert recommended_handoff["proof_script"] == "scripts/lens-resident-surface-proof.ps1 -Mode Status"
    assert recommended_handoff["route"] == "/lens/resident-surface"
    assert recommended_handoff["readiness_route"] == "/lens/resident-runtime/authority-grant/readiness"
    assert recommended_handoff["blocker"] == (
        "resident_surface_operator_experience_proof"
        if resident_runtime_readback
        else "resident_surface_runtime_not_supervised"
    )
    assert recommended_handoff["requirement_state"] == (
        "resident_runtime_observed" if resident_runtime_readback else "foreground_observed_not_supervised"
    )
    assert recommended_handoff["authority_required"] == (
        "operator_experience_proof" if resident_runtime_readback else "process_supervision_authority"
    )
    assert recommended_handoff["authority_granted"] is False
    assert recommended_handoff["read_only_contract"] is True
    assert recommended_handoff["diagnostic_only"] is True
    assert recommended_handoff["would_execute"] is False
    assert recommended_handoff["would_mutate"] is False
    assert recommended_handoff["would_supervise_process"] is False
    assert recommended_handoff["would_restart_process"] is False
    assert recommended_handoff["would_claim_resident"] is False

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["resident_surface_content_readback"]["status"] == "readback_ready"
    assert checks["resident_surface_runtime_readback"]["status"] == (
        "resident_runtime_observed" if resident_runtime_readback else "foreground_runtime_observed"
    )
    assert checks["host_lifecycle_boundary"]["status"] == "blocked_readback_ready"
    assert checks["supervision_proof_available"]["status"] == "available"
    assert checks["live_operator_experience_proof"]["status"] == "proof_passed"
    assert checks["tray_presence_preflight"]["status"] == "blocked_disabled"
    assert checks["overlay_window_preflight"]["status"] == "blocked_disabled"
    assert checks["summon_binding_preflight"]["status"] == "blocked_disabled"
    assert checks["authority_boundary"]["status"] == "blocked"
    assert checks["resident_claim_boundary"]["status"] == (
        "claim_readback_ready" if payload["resident_claim_allowed"] else "blocked"
    )
    assert all(item["passed"] for item in payload["checks"])

    proof = payload["proof"]
    assert proof["resident_surface_readback_status"] == "blocked"
    assert proof["resident_surface_contract_status"] == "readback_ready"
    assert proof["resident_surface_route"] == "/lens/resident-surface"
    assert proof["resident_surface_activation_route"] == "/lens/resident-surface/activation"
    assert proof["resident_surface_content_contract_ready"] is True
    if resident_runtime_readback:
        assert proof["resident_surface_resident_runtime_status"] == "resident_runtime_observed"
        assert proof["resident_surface_resident_runtime_observed"] is True
        assert proof["resident_surface_resident_runtime_blockers"] in ({}, [])
    else:
        assert "resident_surface_runtime_missing" in proof["resident_surface_readback_blockers"]
    assert "resident_surface_missing" not in proof["resident_surface_readback_blockers"]
    assert proof["resident_surface_foreground_runtime_status"] == "foreground_runtime_observed"
    assert proof["resident_surface_foreground_runtime_observed"] is True
    assert "resident_surface_runtime_not_supervised" in proof["resident_surface_foreground_runtime_blockers"]
    assert "resident_surface_not_resident" in proof["resident_surface_foreground_runtime_blockers"]
    assert "resident_surface_runtime_missing" not in proof["resident_surface_foreground_runtime_blockers"]
    assert proof["resident_claim_allowed"] is payload["resident_claim_allowed"]
    assert proof["resident_claim_authority_ready"] is payload["resident_claim_authority_ready"]
    assert proof["resident_claim_authority_readiness_route"] == (
        "/lens/host/persistent-supervision/resident-claim/authority/readiness"
    )
    assert proof["resident_claim_authority_blockers"] == payload["resident_claim_authority_blockers"]
    assert proof["foreground_runtime_running_state"] == "foreground_running"
    assert proof["foreground_runtime_final_state"] == "foreground_stopped"
    assert proof["host_lifecycle_status"] == "blocked"
    assert proof["supervision_proof_available"] is True
    assert proof["live_operator_exit_code"] == 0
    assert proof["live_operator_startup_timeout_seconds"] == 60
    assert proof["live_operator_status"] == "proof_passed"
    assert proof["live_operator_helpful_not_noisy_readback"] is True
    assert proof["live_operator_status_route"] == "/lens/status?limit=5"
    assert proof["live_operator_status_error"] == ""
    assert proof["live_operator_api_pid"] > 0
    assert proof["live_operator_api_stdout_path"].endswith("api-stdout.log")
    assert proof["live_operator_api_stderr_path"].endswith("api-stderr.log")
    assert "resident_surface_runtime_missing" in proof["live_operator_blockers"]
    assert "resident_surface_missing" not in proof["live_operator_blockers"]
    assert proof["tray_status"] == "blocked"
    assert proof["overlay_status"] == "blocked"
    assert proof["summon_status"] == "blocked"
    assert proof["tray_host_enabled"] is False
    assert proof["tray_icon_enabled"] is False
    assert proof["overlay_window_enabled"] is False
    assert proof["overlay_focus_supported"] is False
    assert proof["global_hotkey"] == "Ctrl+Alt+Space"
    assert proof["summon_binding_enabled"] is False
    assert proof["hotkey_registration_enabled"] is False
    assert "tray_host_disabled" in proof["tray_blockers"]
    assert "overlay_window_disabled" in proof["overlay_blockers"]
    assert "global_hotkey_binding_disabled" in proof["summon_blockers"]

    assert "resident_surface_runtime_missing" not in payload["blockers"]
    if resident_runtime_readback:
        assert "resident_surface_runtime_not_supervised" not in payload["blockers"]
        assert "resident_surface_not_resident" not in payload["blockers"]
    else:
        assert "resident_surface_runtime_not_supervised" in payload["blockers"]
        assert "resident_surface_not_resident" in payload["blockers"]
    assert "resident_surface_missing" not in payload["blockers"]
    assert "tray_presence_missing" in payload["blockers"]
    assert "overlay_window_missing" in payload["blockers"]
    assert "summon_anywhere_missing" in payload["blockers"]
    assert "operator_experience_proof_missing" not in payload["blockers"]

    assert payload["governance"] == {
        "read_only_contract": True,
        "diagnostic_only": True,
        "api_route_readback": True,
        "live_http_readback": True,
        "temporary_api_process": True,
        "bounded_foreground_session": True,
        "temporary_runtime_state_write": True,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "window_management_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "local_process_launch_authority": False,
        "api_local_process_launch_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "resident_claim_authority": payload["resident_claim_authority_ready"],
        "resident_claim_allowed": payload["resident_claim_allowed"],
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "tray_icon_authority": False,
        "notification_authority": False,
        "mutation_authority_granted": False,
    }
