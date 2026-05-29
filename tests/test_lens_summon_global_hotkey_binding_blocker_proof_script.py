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
            str(_repo_root() / "scripts" / "lens-summon-global-hotkey-binding-blocker-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def _write_summon_binding_runtime_readback(data_root: Path) -> None:
    runtime_root = data_root / "runtime" / "lens-summon"
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.summon.runtime_state",
                "status": "summon_binding_observed",
                "global_hotkey": "Ctrl+Alt+Space",
                "binding_scope": "global",
                "bounded_handoff_ready": True,
                "local_open_ready": True,
                "opened": False,
                "no_launch": True,
                "summon_anywhere": False,
                "os_level_summon": False,
                "updated_at": "2026-05-26T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )


def _write_lens_status_with_overlay_missing_surface_readbacks(path: Path) -> None:
    readbacks = {
        "tray_runtime_readback": {
            "ready": True,
            "status": "running",
            "requirement_state": "ready",
            "blocker": "",
        },
        "hotkey_runtime_readback": {
            "ready": True,
            "status": "running",
            "global_hotkey": "Ctrl+Alt+Space",
            "expected_global_hotkey": "Ctrl+Alt+Space",
            "binding_scope": "global",
            "expected_binding_scope": "global",
            "launch_on_hotkey": True,
            "requirement_state": "bound",
            "blocker": "",
        },
        "summon_runtime_readback": {
            "ready": True,
            "status": "observed",
            "global_hotkey": "Ctrl+Alt+Space",
            "expected_global_hotkey": "Ctrl+Alt+Space",
            "binding_scope": "global",
            "expected_binding_scope": "global",
            "bounded_handoff_ready": True,
            "local_open_ready": True,
            "summon_anywhere": False,
            "os_level_summon": False,
            "requirement_state": "bounded_handoff_observed",
            "blocker": "",
        },
    }
    payload = {
        "kind": "francis.lens.status",
        "resident_host": {
            "process_readback": {
                "status": "process_observed",
                "state_status": "resident_running",
                "process_alive": True,
            },
            "supervision_gate": {
                "resident_supervised_runtime": True,
                "resident_host_supervised": True,
                "fresh_supervisor_readback": True,
                "supervisor_readback": {
                    "status": "resident_supervising",
                    "fresh_readback": True,
                    "observed_process_alive": True,
                    "observed_pid_matches_host_process": True,
                },
            },
            "launch_manifest": readbacks,
            **readbacks,
        },
        "summon_enablement_gate": {"ready": False, "summon_anywhere": False},
        "os_binding_readiness": {"ready": False},
        "stage6_readiness": {
            "ready_criteria": [],
            "closure_readback": {"criteria": []},
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_lens_summon_global_hotkey_binding_blocker_uses_overlay_family_contract() -> None:
    script = (_repo_root() / "scripts" / "lens-summon-global-hotkey-binding-blocker-proof.ps1").read_text(
        encoding="utf-8",
    )

    assert "OverlayWindowBridgeScript" not in script
    assert "OverlayBridgeResult" not in script
    assert "uses_overlay_window_family_contract_readback" in script
    assert "blocked_family_handoffs[overlay_window]" in script
    assert "$GlobalHotkeyResolvedByRuntimeReadbackObserved" in script
    assert "surface_runtime_readback_observed" in script
    assert "'-StatusPath', $StatusPath" in script


def test_lens_summon_global_hotkey_binding_blocker_proof_is_readback_only(
    tmp_path: Path,
) -> None:
    proc = _run_proof("-Mode", "Status", "-DataDir", str(tmp_path / "data"))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon_global_hotkey_binding_blocker.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["acceptance_criterion"] == "summon_anywhere"
    assert payload["previous_summon_blocker_family"] == "overlay_window"
    assert payload["summon_global_hotkey_binding_blocker_family"] == "global_hotkey_binding"
    assert payload["fourth_summon_blocker_family"] == "global_hotkey_binding"
    assert payload["next_summon_blocker_family"] == "summon_binding"
    assert payload["summon_next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert payload["resident_runtime_next_smallest_truthful_gap"] == (
        "resident_runtime_overlay_window_authority_boundary"
    )
    assert payload["next_smallest_truthful_gap"] == "summon_binding_blocker_boundary"
    assert payload["recommended_handoff_source"] == "summon_global_hotkey_binding_handoff"
    assert payload["recommended_next_slice"] == "run_summon_binding_blocker_proof"
    assert payload["recommended_proof_script"] == "scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status"
    assert payload["recommended_route"] == "/lens/summon"
    assert payload["recommended_readiness_route"] == "/lens/summon/readiness"
    assert payload["authority_required"] == "summon_authority"
    assert payload["authority_granted"] is False
    assert payload["summon_global_hotkey_delegated_authority_posture_observed"] is True
    recommended_handoff = payload["recommended_handoff"]
    assert recommended_handoff["id"] == "summon_binding"
    assert recommended_handoff["next_step"] == "run_summon_binding_blocker_proof"
    assert recommended_handoff["proof_script"] == "scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status"
    assert recommended_handoff["next_smallest_truthful_gap"] == "summon_binding_blocker_boundary"
    assert recommended_handoff["authority_required"] == "summon_authority"
    assert recommended_handoff["authority_granted"] is False
    assert recommended_handoff["read_only_contract"] is True
    assert recommended_handoff["diagnostic_only"] is True
    assert recommended_handoff["would_execute"] is False
    assert recommended_handoff["would_mutate"] is False
    assert payload["summon_global_hotkey_family_observed"] is True
    assert payload["previous_overlay_window_contract_observed"] is True
    assert payload["previous_overlay_window_contract_readback_observed"] is True
    previous_overlay = payload["previous_overlay_handoff"]
    assert previous_overlay["source"] == "summon_anywhere_blockers.blocked_family_handoffs"
    assert previous_overlay["status"] == "contract_projected"
    assert previous_overlay["contract_status"] == "blocked"
    assert previous_overlay["proof_script"] == "scripts/lens-summon-overlay-window-blocker-proof.ps1 -Mode Status"
    assert previous_overlay["previous_summon_blocker_family"] == "tray_presence"
    assert previous_overlay["summon_overlay_window_blocker_family"] == "overlay_window"
    assert previous_overlay["next_summon_blocker_family"] == "global_hotkey_binding"
    assert previous_overlay["next_smallest_truthful_gap"] == "summon_global_hotkey_binding_blocker_boundary"
    assert previous_overlay["authority_required"] == "overlay_control_authority"
    assert previous_overlay["authority_granted"] is False
    assert previous_overlay["read_only_contract"] is True
    assert previous_overlay["diagnostic_only"] is True
    assert previous_overlay["would_execute"] is False
    assert previous_overlay["would_mutate"] is False
    assert previous_overlay["handoff_aligned"] is True
    assert previous_overlay["side_effects_denied"] is True
    assert previous_overlay["blockers"] == ["overlay_window_missing"]
    assert payload["hotkey_summon_boundary_observed"] is True
    assert payload["handoff_aligned"] is True
    assert payload["side_effects_denied"] is True
    assert payload["summon_global_hotkey_binding_blockers"] == [
        "global_hotkey_binding_disabled",
        "global_hotkey_registration_disabled",
    ]

    runtime_blockers = payload["resident_runtime_hotkey_summon_blockers"]
    assert "global_hotkey_binding_disabled" in runtime_blockers
    assert "global_hotkey_registration_disabled" in runtime_blockers
    assert "hotkey_registration_authority_not_granted" in runtime_blockers
    assert "summon_authority_not_granted" in runtime_blockers

    boundary = payload["hotkey_summon_boundary"]
    assert boundary["status"] == "proof_passed"
    assert boundary["authority_family"] == "hotkey_summon"
    assert boundary["previous_authority_family"] == "tray_presence"
    assert boundary["next_authority_family"] == "overlay_window"
    assert boundary["hotkey_summon_boundary_observed"] is True
    assert boundary["summon_preflight_observed"] is True
    assert boundary["side_effects_denied"] is True
    assert boundary["fourth_authority_family_consumed"] is True
    assert boundary["route"] == "/lens/summon"
    assert boundary["global_hotkey"] == "Ctrl+Alt+Space"
    assert boundary["binding_scope"] == "global"
    assert boundary["required_before"] == ["resident_claim"]
    assert boundary["summon_preflight_status"] == "blocked"
    assert boundary["blockers"] == runtime_blockers
    assert "global_hotkey_binding_disabled" in boundary["summon_preflight_blockers"]
    assert "global_hotkey_registration_disabled" in boundary["summon_preflight_blockers"]
    assert "hotkey_registration_authority_not_granted" not in boundary["summon_preflight_blockers"]
    assert "summon_authority_not_granted" not in boundary["summon_preflight_blockers"]

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["summon_global_hotkey_binding_family"]["status"] == "delegated_authority_posture"
    assert checks["previous_overlay_window_contract"]["status"] == "previous_family_contract_observed"
    assert checks["previous_overlay_window_contract_readback"]["status"] == "previous_contract_readback_observed"
    assert checks["resident_runtime_hotkey_summon_boundary"]["status"] == "blocked_readback_ready"
    assert checks["handoff_alignment"]["status"] == "handoff_aligned"
    assert checks["side_effects_denied"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    assert payload["governance"] == {
        "diagnostic_only": True,
        "wraps_summon_anywhere_blockers_proof": True,
        "wraps_summon_overlay_window_blocker_proof": False,
        "uses_overlay_window_family_contract_readback": True,
        "overlay_window_contract_readback": True,
        "wraps_resident_runtime_hotkey_summon_boundary_proof": True,
        "summon_preflight_readback": True,
        "wrapped_resident_runtime_execution_authority": True,
        "read_only_contract": True,
        "approval_request_write": False,
        "resident_runtime_execution_authority": False,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "tray_registration_authority": False,
        "tray_icon_authority": False,
        "notification_authority": False,
        "hotkey_registration_authority": False,
        "overlay_control_authority": False,
        "window_management_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "summon_authority": False,
        "memory_write": False,
        "receipt_write_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
    }


def test_lens_summon_global_hotkey_binding_blocker_skips_observed_summon_binding(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    _write_summon_binding_runtime_readback(data_root)

    proc = _run_proof("-Mode", "Status", "-DataDir", str(data_root))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["summon_binding_runtime_readback_observed"] is True
    assert payload["summon_binding_resolved_to_authority_handoff"] is False
    assert payload["summon_global_hotkey_delegated_authority_posture_observed"] is True
    assert payload["next_summon_blocker_family"] == "summon_binding"
    assert payload["next_smallest_truthful_gap"] == "summon_binding_blocker_boundary"
    assert payload["recommended_handoff_source"] == "summon_global_hotkey_binding_handoff"
    assert payload["recommended_next_slice"] == "run_summon_binding_blocker_proof"
    assert payload["recommended_proof_script"] == "scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status"
    assert payload["authority_required"] == "summon_authority"
    assert payload["authority_granted"] is False

    handoff = payload["recommended_handoff"]
    assert handoff["id"] == "summon_binding"
    assert handoff["previous_summon_blocker_family"] == "global_hotkey_binding"
    assert handoff["next_summon_blocker_family"] == "summon_binding"
    assert handoff["next_smallest_truthful_gap"] == "summon_binding_blocker_boundary"
    assert handoff["next_step"] == "run_summon_binding_blocker_proof"
    assert handoff["proof_script"] == "scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status"
    assert handoff["authority_required"] == "summon_authority"
    assert handoff["authority_granted"] is False
    assert handoff["read_only_contract"] is True
    assert handoff["diagnostic_only"] is True
    assert handoff["would_execute"] is False
    assert handoff["would_mutate"] is False

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["summon_binding_runtime_readback"]["status"] == "readback_present_without_authority_handoff"
    assert checks["summon_global_hotkey_binding_family"]["status"] == "delegated_authority_posture"
    assert all(item["passed"] for item in payload["checks"])


def test_lens_summon_global_hotkey_binding_accepts_surface_runtime_resolved_chain(
    tmp_path: Path,
) -> None:
    status_path = tmp_path / "lens-status.json"
    _write_lens_status_with_overlay_missing_surface_readbacks(status_path)

    proc = _run_proof("-Mode", "Status", "-StatusPath", str(status_path))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon_global_hotkey_binding_blocker.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["global_hotkey_runtime_readback_observed"] is True
    assert payload["global_hotkey_resolved_by_runtime_readback"] is True
    assert payload["summon_binding_runtime_readback_observed"] is True
    assert payload["summon_binding_resolved_to_authority_handoff"] is False
    assert payload["summon_global_hotkey_delegated_authority_posture_observed"] is True
    assert payload["summon_global_hotkey_family_observed"] is True
    assert payload["previous_overlay_window_contract_readback_observed"] is True
    assert payload["next_summon_blocker_family"] == "summon_binding"
    assert payload["next_smallest_truthful_gap"] == "summon_binding_blocker_boundary"
    assert payload["recommended_handoff_source"] == "summon_global_hotkey_binding_handoff"
    assert payload["recommended_next_slice"] == "run_summon_binding_blocker_proof"
    assert payload["recommended_proof_script"] == "scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status"

    handoff = payload["recommended_handoff"]
    assert handoff["id"] == "summon_binding"
    assert handoff["previous_summon_blocker_family"] == "global_hotkey_binding"
    assert handoff["next_summon_blocker_family"] == "summon_binding"
    assert handoff["next_smallest_truthful_gap"] == "summon_binding_blocker_boundary"
    assert handoff["authority_granted"] is False

    previous_overlay = payload["previous_overlay_handoff"]
    assert previous_overlay["source"] == "summon_anywhere_blockers.blocked_family_handoffs"
    assert previous_overlay["contract_status"] == "blocked"
    assert previous_overlay["blockers"] == ["overlay_window_missing"]

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["summon_global_hotkey_binding_family"]["status"] == "delegated_authority_posture"
    assert checks["summon_binding_runtime_readback"]["status"] == "readback_present_without_authority_handoff"
    assert checks["previous_overlay_window_contract"]["status"] == "previous_family_contract_observed"
    assert checks["resident_runtime_hotkey_summon_boundary"]["status"] == "blocked_readback_ready"
    assert checks["handoff_alignment"]["status"] == "handoff_aligned"
    assert all(item["passed"] for item in payload["checks"])
