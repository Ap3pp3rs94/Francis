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
            str(_repo_root() / "scripts" / "lens-summon-authority-blocker-proof.ps1"),
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
        "ok": True,
        "kind": "lens.status",
        "os_binding_authority_requests": {
            "ok": True,
            "kind": "lens.os_binding.command_palette_binding_authority.request_readback",
            "status": "none",
            "route": "/lens/os-binding/authority/requests",
            "authority_route": "/lens/os-binding/authority",
            "request_route": "/lens/os-binding/authority/request",
            "readiness_route": "/lens/os-binding/readiness",
            "plan_route": "/lens/os-binding/plan",
            "authority_required": "os_level_command_palette_binding_authority",
            "pending_count": 0,
            "approved_count": 0,
            "rejected_count": 0,
            "emergency_count": 0,
            "total_count": 0,
            "authority_granted": False,
            "os_level_command_palette_binding_authority": False,
            "os_level_command_palette": False,
            "summon_anywhere": False,
            "opens_palette": False,
            "registers_hotkey": False,
            "launches_process": False,
            "controls_overlay": False,
            "governance": {
                "read_only_contract": True,
                "approval_request_write": False,
                "execution_authority": False,
                "approval_decision_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
            },
        },
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
            "criteria": [
                {
                    "id": "os_binding_readiness",
                    "authority_request_readback_status": "none",
                    "authority_request_readback_ready": True,
                    "authority_route": "/lens/os-binding/authority",
                    "authority_request_route": "/lens/os-binding/authority/request",
                    "authority_requests_route": "/lens/os-binding/authority/requests",
                    "evidence": [
                        "/lens/os-binding/readiness",
                        "/lens/os-binding/authority/requests",
                        "/lens/os-binding/authority/request",
                        "/lens/status",
                    ],
                }
            ],
            "ready_criteria": [],
            "closure_readback": {"criteria": []},
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_lens_summon_authority_blocker_proof_uses_binding_family_contract() -> None:
    script = (_repo_root() / "scripts" / "lens-summon-authority-blocker-proof.ps1").read_text(encoding="utf-8")

    assert "SummonBindingBridgeScript" not in script
    assert "SummonBindingBridgeResult" not in script
    assert "uses_summon_binding_family_contract_readback" in script
    assert "blocked_family_handoffs[summon_binding]" in script


def test_lens_summon_authority_blocker_proof_is_readback_only(tmp_path: Path) -> None:
    proc = _run_proof("-Mode", "Status", "-DataDir", str(tmp_path / "data"))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon_authority_blocker.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["acceptance_criterion"] == "summon_anywhere"
    assert payload["previous_summon_blocker_family"] == "summon_binding"
    assert payload["summon_authority_blocker_family"] == "authority"
    assert payload["sixth_summon_blocker_family"] == "authority"
    assert payload["next_summon_blocker_family"] == "stage6_lens_completion_audit"
    assert payload["summon_next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert payload["previous_binding_next_smallest_truthful_gap"] == "summon_authority_blocker_boundary"
    assert payload["direct_summon_preflight_next_smallest_truthful_gap"] == ("summon_anywhere_blockers")
    assert payload["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert payload["authority_required"] == "summon_hotkey_overlay_and_process_authority"
    assert payload["authority_granted"] is False
    assert payload["recommended_handoff_source"] == "summon_authority_handoff"
    assert payload["recommended_next_slice"] == "run_stage6_lens_completion_audit_after_summon_authority_handoff"
    assert payload["recommended_proof_script"] == "scripts/lens-stage6-completion-audit.ps1 -Mode Status"
    assert payload["recommended_route"] == "/lens/status"
    assert payload["recommended_readiness_route"] == "/lens/status"
    recommended_handoff = payload["recommended_handoff"]
    assert recommended_handoff["id"] == "stage6_lens_completion_audit"
    assert recommended_handoff["status"] == "audit_needed"
    assert recommended_handoff["next_step"] == "run_stage6_lens_completion_audit_after_summon_authority_handoff"
    assert recommended_handoff["proof_script"] == "scripts/lens-stage6-completion-audit.ps1 -Mode Status"
    assert recommended_handoff["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert recommended_handoff["authority_required"] == "none_new_stage6_completion_audit"
    assert recommended_handoff["authority_granted"] is False
    assert recommended_handoff["read_only_contract"] is True
    assert recommended_handoff["diagnostic_only"] is True
    assert recommended_handoff["would_execute"] is False
    assert recommended_handoff["would_mutate"] is False
    assert payload["summon_authority_family_observed"] is True
    assert payload["summon_authority_family_observed_after_resolved_summon_binding"] is False
    assert payload["previous_summon_binding_contract_observed"] is True
    assert payload["previous_summon_binding_contract_readback_observed"] is True
    assert payload["summon_binding_runtime_readback_observed"] is False
    assert payload["summon_binding_resolved_by_runtime_readback"] is False
    assert payload["summon_preflight_authority_observed"] is True
    assert payload["all_summon_blocker_families_consumed"] is True
    assert payload["handoff_aligned"] is True
    assert payload["side_effects_denied"] is True
    assert payload["summon_authority_blockers"] == [
        "summon_authority_not_granted",
        "hotkey_registration_authority_not_granted",
        "overlay_control_authority_not_granted",
        "local_process_launch_authority_not_granted",
    ]
    assert payload["direct_summon_preflight_authority_blockers"] == payload["summon_authority_blockers"]
    assert payload["direct_summon_preflight_binding_blockers"] == [
        "lens_summon_binding_disabled_pending_authority",
        "summon_authority_not_granted",
    ]

    previous_binding = payload["previous_binding_handoff"]
    assert previous_binding["source"] == "summon_anywhere_blockers.blocked_family_handoffs"
    assert previous_binding["status"] == "contract_projected"
    assert previous_binding["contract_status"] == "blocked"
    assert previous_binding["proof_script"] == "scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status"
    assert previous_binding["previous_summon_blocker_family"] == "global_hotkey_binding"
    assert previous_binding["summon_binding_blocker_family"] == "summon_binding"
    assert previous_binding["next_summon_blocker_family"] == "authority"
    assert previous_binding["next_smallest_truthful_gap"] == "summon_authority_blocker_boundary"
    assert previous_binding["authority_required"] == "summon_authority"
    assert previous_binding["authority_granted"] is False
    assert previous_binding["read_only_contract"] is True
    assert previous_binding["diagnostic_only"] is True
    assert previous_binding["would_execute"] is False
    assert previous_binding["would_mutate"] is False
    assert previous_binding["handoff_aligned"] is True
    assert previous_binding["side_effects_denied"] is True
    assert previous_binding["blockers"] == [
        "lens_summon_binding_disabled_pending_authority",
        "summon_authority_not_granted",
    ]

    boundary = payload["summon_authority_boundary"]
    assert boundary["status"] == "blocked"
    assert boundary["ready"] is False
    assert boundary["summon_name"] == "Francis Lens Summon"
    assert boundary["config_path"] == "config/runtime/lens/summon.json"
    assert boundary["global_hotkey"] == "Ctrl+Alt+Space"
    assert boundary["binding_scope"] == "global"
    assert boundary["palette_route"] == "/lens/status"
    assert boundary["required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
    ]
    assert boundary["binding_enabled"] is False
    assert boundary["register_hotkey"] is False
    assert boundary["startup_register"] is False
    assert "summon_authority_not_granted" in boundary["blockers"]
    assert "hotkey_registration_authority_not_granted" in boundary["blockers"]
    assert "overlay_control_authority_not_granted" in boundary["blockers"]
    assert "local_process_launch_authority_not_granted" in boundary["blockers"]
    assert boundary["summon_binding_blockers"] == payload["direct_summon_preflight_binding_blockers"]
    assert boundary["authority_blockers"] == payload["direct_summon_preflight_authority_blockers"]

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["summon_authority_family"]["status"] == "sixth_family_projected"
    assert checks["previous_summon_binding_contract"]["status"] == "previous_family_contract_observed"
    assert checks["previous_summon_binding_contract_readback"]["status"] == "previous_contract_readback_observed"
    assert checks["summon_preflight_authority"]["status"] == "blocked_readback_ready"
    assert checks["handoff_alignment"]["status"] == "handoff_aligned"
    assert checks["side_effects_denied"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    assert payload["governance"] == {
        "diagnostic_only": True,
        "wraps_summon_anywhere_blockers_proof": True,
        "wraps_summon_binding_blocker_proof": False,
        "uses_summon_binding_family_contract_readback": True,
        "summon_binding_contract_readback": True,
        "summon_binding_runtime_readback_observed": False,
        "summon_binding_resolved_by_runtime_readback": False,
        "wraps_summon_preflight": True,
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


def test_lens_summon_authority_blocker_accepts_resolved_summon_binding_runtime_readback(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    _write_summon_binding_runtime_readback(data_root)

    proc = _run_proof("-Mode", "Status", "-DataDir", str(data_root))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon_authority_blocker.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["previous_summon_blocker_family"] == "global_hotkey_binding"
    assert payload["previous_binding_next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert payload["summon_authority_family_observed"] is True
    assert payload["summon_authority_family_observed_after_resolved_summon_binding"] is True
    assert payload["previous_summon_binding_contract_observed"] is True
    assert payload["previous_summon_binding_contract_readback_observed"] is True
    assert payload["summon_binding_runtime_readback_observed"] is True
    assert payload["summon_binding_resolved_by_runtime_readback"] is True
    assert payload["summon_preflight_authority_observed"] is True
    assert payload["all_summon_blocker_families_consumed"] is True
    assert payload["handoff_aligned"] is True
    assert payload["side_effects_denied"] is True
    assert payload["next_summon_blocker_family"] == "stage6_lens_completion_audit"
    assert payload["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert payload["authority_required"] == "summon_hotkey_overlay_and_process_authority"
    assert payload["authority_granted"] is False
    assert "summon_authority_not_granted" in payload["summon_authority_blockers"]
    assert "hotkey_registration_authority_not_granted" in payload["summon_authority_blockers"]
    assert "overlay_control_authority_not_granted" in payload["summon_authority_blockers"]

    previous_binding = payload["previous_binding_handoff"]
    assert previous_binding["source"] == "summon_anywhere_blockers.surface_runtime_readback_observed"
    assert previous_binding["status"] == "runtime_readback_resolved"
    assert previous_binding["contract_status"] == "resolved"
    assert previous_binding["proof_script"] == "scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status"
    assert previous_binding["previous_summon_blocker_family"] == "global_hotkey_binding"
    assert previous_binding["summon_binding_blocker_family"] == "summon_binding"
    assert previous_binding["next_summon_blocker_family"] == "authority"
    assert previous_binding["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert previous_binding["authority_required"] == "summon_hotkey_overlay_and_process_authority"
    assert previous_binding["authority_granted"] is False
    assert previous_binding["read_only_contract"] is True
    assert previous_binding["diagnostic_only"] is True
    assert previous_binding["would_execute"] is False
    assert previous_binding["would_mutate"] is False
    assert previous_binding["handoff_aligned"] is True
    assert previous_binding["side_effects_denied"] is True
    assert previous_binding["blockers"] == []
    assert "lens_summon_binding_disabled_pending_authority" in previous_binding["suppressed_blockers"]
    assert "summon_authority_not_granted" in previous_binding["suppressed_blockers"]

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["summon_authority_family"]["status"] == "authority_family_after_resolved_summon_binding"
    assert checks["previous_summon_binding_contract"]["status"] == "summon_binding_runtime_readback_resolved"
    assert checks["previous_summon_binding_contract_readback"]["status"] == "runtime_readback_resolved"
    assert checks["summon_preflight_authority"]["status"] == "blocked_readback_ready"
    assert checks["handoff_alignment"]["status"] == "handoff_aligned"
    assert checks["side_effects_denied"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    governance = payload["governance"]
    assert governance["uses_summon_binding_family_contract_readback"] is True
    assert governance["summon_binding_contract_readback"] is True
    assert governance["summon_binding_runtime_readback_observed"] is True
    assert governance["summon_binding_resolved_by_runtime_readback"] is True
    assert governance["execution_authority"] is False
    assert governance["summon_authority"] is False
    assert governance["hotkey_registration_authority"] is False
    assert governance["overlay_control_authority"] is False
    assert governance["mutation_authority_granted"] is False


def test_lens_summon_authority_blocker_accepts_overlay_remaining_after_surface_runtime_readback(
    tmp_path: Path,
) -> None:
    status_path = tmp_path / "lens-status.json"
    _write_lens_status_with_overlay_missing_surface_readbacks(status_path)

    proc = _run_proof("-Mode", "Status", "-StatusPath", str(status_path))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon_authority_blocker.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["previous_summon_blocker_family"] == "global_hotkey_binding"
    assert payload["summon_authority_family_observed"] is True
    assert payload["summon_authority_family_observed_after_resolved_summon_binding"] is True
    assert payload["previous_summon_binding_contract_observed"] is True
    assert payload["previous_summon_binding_contract_readback_observed"] is True
    assert payload["summon_binding_runtime_readback_observed"] is True
    assert payload["summon_binding_resolved_by_runtime_readback"] is True
    assert payload["resident_host_supervised_runtime_observed"] is True
    assert payload["all_summon_blocker_families_consumed"] is True
    assert payload["handoff_aligned"] is True
    assert payload["side_effects_denied"] is True
    assert payload["summon_authority_blockers"] == [
        "summon_authority_not_granted",
        "hotkey_registration_authority_not_granted",
        "overlay_control_authority_not_granted",
    ]

    previous_binding = payload["previous_binding_handoff"]
    assert previous_binding["source"] == "summon_anywhere_blockers.surface_runtime_readback_observed"
    assert previous_binding["status"] == "runtime_readback_resolved"
    assert previous_binding["contract_status"] == "resolved"
    assert previous_binding["proof_script"] == "scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status"
    assert previous_binding["previous_summon_blocker_family"] == "global_hotkey_binding"
    assert previous_binding["summon_binding_blocker_family"] == "summon_binding"
    assert previous_binding["next_summon_blocker_family"] == "authority"
    assert previous_binding["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert previous_binding["read_only_contract"] is True
    assert previous_binding["diagnostic_only"] is True
    assert previous_binding["would_execute"] is False
    assert previous_binding["would_mutate"] is False
    assert previous_binding["side_effects_denied"] is True
    assert "lens_summon_binding_disabled_pending_authority" in previous_binding["suppressed_blockers"]
    assert "summon_authority_not_granted" in previous_binding["suppressed_blockers"]

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["summon_authority_family"]["status"] == "authority_family_after_resolved_summon_binding"
    assert checks["previous_summon_binding_contract"]["status"] == "summon_binding_runtime_readback_resolved"
    assert checks["previous_summon_binding_contract_readback"]["status"] == "runtime_readback_resolved"
    assert checks["summon_preflight_authority"]["status"] == "blocked_readback_ready"
    assert checks["handoff_alignment"]["status"] == "handoff_aligned"
    assert checks["side_effects_denied"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])
