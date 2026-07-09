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
            str(_repo_root() / "scripts" / "lens-summon-anywhere-blockers-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def _write_lens_status(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
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
                    ]
                },
            }
        ),
        encoding="utf-8",
    )


def test_lens_summon_anywhere_blockers_proof_bounds_live_readback_children() -> None:
    script = (_repo_root() / "scripts" / "lens-summon-anywhere-blockers-proof.ps1").read_text(encoding="utf-8")

    assert "[int]$ChildProofTimeoutSeconds = 120" in script
    assert "[int]$LensStatusTimeoutSeconds = 120" in script
    assert "function Invoke-JsonProcess" in script
    assert "Stop-ProcessTree -Process $Process" in script
    assert "error = 'lens_status_timeout'" in script
    assert "-TimeoutSeconds $LensStatusTimeoutSeconds" in script
    assert "timed_out = [bool](Get-PropertyValue -Payload $LensStatusRead -Name 'timed_out'" in script
    assert "timeout_seconds = [int](Get-PropertyValue -Payload $LensStatusRead -Name 'timeout_seconds'" in script


def _write_lens_status_with_active_os_binding_grant(path: Path) -> None:
    _write_lens_status(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    authority = payload["os_binding_authority_requests"]
    authority.update(
        {
            "status": "authority_granted",
            "approved_count": 1,
            "total_count": 1,
            "authority_granted": True,
            "os_level_command_palette_binding_authority": True,
            "active_grant_receipt_id": "losbag_test",
        }
    )
    criterion = payload["stage6_readiness"]["criteria"][0]
    criterion.update(
        {
            "authority_request_readback_status": "authority_granted",
            "authority_granted": True,
            "os_level_command_palette_binding_authority": True,
            "active_grant_receipt_id": "losbag_test",
        }
    )
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_lens_status_with_supervised_resident_host(path: Path) -> None:
    _write_lens_status(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["resident_host"] = {
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
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_lens_status_with_supervised_resident_host_and_live_surface_readbacks(
    path: Path,
) -> None:
    _write_lens_status_with_supervised_resident_host(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    readbacks = {
        "tray_runtime_readback": {
            "ready": True,
            "status": "running",
            "runtime_state_path": "data/runtime/lens-tray/status.json",
            "state_kind": "lens.tray.runtime_state",
            "state_status": "tray_running",
            "process_alive": True,
            "tray_icon_visible": True,
            "requirement_state": "ready",
            "blocker": "",
        },
        "hotkey_runtime_readback": {
            "ready": True,
            "status": "running",
            "runtime_state_path": "data/runtime/lens-hotkey/status.json",
            "state_kind": "lens.hotkey.runtime_state",
            "state_status": "hotkey_bound",
            "process_alive": True,
            "hotkey_bound": True,
            "global_hotkey": "Ctrl+Alt+F",
            "expected_global_hotkey": "Ctrl+Alt+F",
            "binding_scope": "global",
            "expected_binding_scope": "global",
            "launch_on_hotkey": True,
            "requirement_state": "bound",
            "blocker": "",
        },
        "overlay_runtime_readback": {
            "ready": True,
            "status": "running",
            "runtime_state_path": "data/runtime/lens-overlay/status.json",
            "state_kind": "lens.overlay.runtime_state",
            "state_status": "overlay_running",
            "process_alive": True,
            "overlay_window_visible": True,
            "always_on_top": True,
            "overlay_name": "Francis Lens Overlay",
            "expected_overlay_name": "Francis Lens Overlay",
            "overlay_scope": "user_session",
            "expected_overlay_scope": "user_session",
            "requirement_state": "visible",
            "blocker": "",
        },
        "summon_runtime_readback": {
            "ready": True,
            "status": "observed",
            "runtime_state_path": "data/runtime/lens-summon/status.json",
            "state_kind": "lens.summon.runtime_state",
            "state_status": "summon_binding_observed",
            "global_hotkey": "Ctrl+Alt+F",
            "expected_global_hotkey": "Ctrl+Alt+F",
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
    payload["resident_host"].update(readbacks)
    payload["resident_host"]["launch_manifest"] = readbacks
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_lens_status_with_live_summon_anywhere_readback(path: Path) -> None:
    _write_lens_status_with_supervised_resident_host_and_live_surface_readbacks(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    summon_runtime = payload["resident_host"]["summon_runtime_readback"]
    summon_runtime["summon_anywhere"] = True
    summon_runtime["os_level_summon"] = True
    payload["resident_host"]["launch_manifest"]["summon_runtime_readback"] = summon_runtime
    payload["summon_enablement_gate"] = {
        "status": "ready_for_operator_review",
        "ready": True,
        "summon_anywhere": True,
        "summon_anywhere_runtime_ready": True,
        "next_smallest_truthful_gap": "summon_anywhere_blockers",
        "blockers": [],
    }
    payload["os_binding_readiness"] = {
        "status": "ready",
        "ready": True,
        "blockers": [],
        "next_smallest_truthful_gap": "stage6_lens_completion_audit",
    }
    payload["stage6_readiness"]["ready_criteria"] = ["summon_anywhere"]
    payload["stage6_readiness"]["closure_readback"] = {
        "kind": "lens.stage6.closure_readback",
        "status": "blocked",
        "ready_to_close": False,
        "criteria": [
            {
                "id": "summon_anywhere",
                "status": "ready",
                "ready": True,
                "next_smallest_truthful_gap": "",
                "handoff": {},
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_lens_status_with_approved_os_binding_request_without_authority(path: Path) -> None:
    _write_lens_status(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    authority = payload["os_binding_authority_requests"]
    authority.update(
        {
            "status": "approved_no_authority",
            "approved_count": 1,
            "total_count": 1,
            "authority_granted": False,
            "os_level_command_palette_binding_authority": False,
        }
    )
    criterion = payload["stage6_readiness"]["criteria"][0]
    criterion.update(
        {
            "authority_request_readback_status": "approved_no_authority",
            "authority_granted": False,
            "os_level_command_palette_binding_authority": False,
        }
    )
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_lens_status_with_applied_stage6_prerequisite_bringup(path: Path) -> None:
    _write_lens_status(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stage6_readiness"]["prerequisite_bringup"] = {
        "ok": True,
        "kind": "lens.stage6.prerequisite_bringup.plan",
        "status": "persistent_supervision_enablement_applied",
        "stage": "Stage 6 / Lens MVP",
        "stage_state": "active",
        "ready_to_close": False,
        "acceptance_criterion": "system_resident_presence",
        "current_truthful_gap": "persistent_supervision_execution_boundary",
        "current_truthful_gap_basis": (
            "persistent_supervision_enablement_execution_receipt.post_plan.next_smallest_truthful_gap"
        ),
        "current_first_missing_requirement": "",
        "current_first_missing_truthful_gap": "",
        "next_operator_action_requirement": "persistent_supervision_enablement_receipt",
        "next_operator_action": {
            "id": "review_persistent_supervision_enablement_receipt",
            "method": "GET",
            "route": "/lens/host/persistent-supervision/enablement/executions",
            "script_would_execute": False,
            "script_would_mutate": False,
        },
        "next_operator_command": {
            "mode": "Status",
            "command": ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
        },
        "required_before_enable": [
            "resident_host_process",
            "tray_presence",
            "global_hotkey_binding",
            "overlay_window",
            "summon_binding",
        ],
        "missing_required_before_enable": [],
        "required_before_enable_ready": True,
        "recommended_next_slice": "run_stage6_prerequisite_bringup_review_persistent_supervision_enablement_receipt",
        "recommended_proof_script": "scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
        "governance": {
            "read_only_contract": True,
            "diagnostic_only": True,
            "plan_only": True,
            "requires_explicit_operator_execution": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "mutation_authority_granted": False,
            "would_execute": False,
            "would_mutate": False,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_lens_status_with_summon_closure_completion_audit_handoff(path: Path) -> None:
    _write_lens_status(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stage6_readiness"]["closure_readback"] = {
        "kind": "lens.stage6.closure_readback",
        "status": "blocked",
        "ready_to_close": False,
        "criteria": [
            {
                "id": "summon_anywhere",
                "status": "blocked",
                "ready": False,
                "next_smallest_truthful_gap": "summon_anywhere_blockers",
                "handoff": {
                    "first_blocker_family": "resident_host",
                    "first_blocker_family_completion_audit_handoff": {
                        "authority_granted": False,
                        "authority_required": "process_supervision_authority",
                        "diagnostic_only": True,
                        "next_smallest_truthful_gap": "stage6_lens_completion_audit",
                        "next_step": "consume_resident_host_process_supervision_handoff_before_stage6_closure",
                        "previous_next_smallest_truthful_gap": "resident_host_process_not_supervised",
                        "proof_script": (
                            "scripts/lens-summon-resident-host-blocker-proof.ps1 "
                            "-Mode Status -ConsumeProcessSupervisionHandoff"
                        ),
                        "read_only_contract": True,
                        "would_execute": False,
                        "would_mutate": False,
                    },
                },
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_lens_summon_anywhere_blockers_proof_is_readback_only(tmp_path: Path) -> None:
    status_path = tmp_path / "lens-status.json"
    _write_lens_status(status_path)

    proc = _run_proof("-Mode", "Status", "-StatusPath", str(status_path))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon_anywhere_blockers.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["acceptance_criterion"] == "summon_anywhere"
    assert payload["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert payload["summon_preflight_observed"] is True
    assert payload["stage6_family_projection_observed"] is True
    assert payload["side_effects_denied"] is True
    assert payload["os_binding_authority_request_readback_observed"] is True
    assert payload["first_blocker_family_handoff_observed"] is True
    assert payload["first_blocker_family"] == "tray_presence"
    assert payload["recommended_handoff_source"] == "first_blocker_family_handoff"
    assert payload["recommended_next_slice"] == "run_tray_presence_blocker_proof"
    assert payload["recommended_proof_script"] == "scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status"
    assert payload["recommended_route"] == "/lens/tray"
    assert payload["recommended_readiness_route"] == "/lens/tray/readiness"
    assert payload["recommended_authority_required"] == "tray_registration_authority"
    assert payload["recommended_authority_granted"] is False
    assert payload["authority_required"] == "tray_registration_authority"
    assert payload["authority_granted"] is False
    assert payload["first_blocker_family_completion_audit_handoff_observed"] is False
    assert payload["recommended_concrete_handoff_source"] == "first_blocker_family_handoff"
    assert payload["recommended_concrete_next_slice"] == "run_tray_presence_blocker_proof"
    assert payload["recommended_concrete_proof_script"] == (
        "scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status"
    )
    assert payload["recommended_concrete_next_smallest_truthful_gap"] == "summon_overlay_window_blocker_boundary"
    assert payload["recommended_concrete_authority_required"] == "tray_registration_authority"
    assert payload["recommended_concrete_authority_granted"] is False
    assert payload["first_blocker_family_handoff"] == {
        "id": "tray_presence",
        "label": "Tray presence",
        "status": "blocked",
        "blockers": ["tray_host_missing"],
        "proof_script": "scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status",
        "route": "/lens/tray",
        "readiness_route": "/lens/tray/readiness",
        "next_step": "run_tray_presence_blocker_proof",
        "next_smallest_truthful_gap": "summon_overlay_window_blocker_boundary",
        "authority_required": "tray_registration_authority",
        "authority_granted": False,
        "read_only_contract": True,
        "diagnostic_only": True,
        "would_execute": False,
        "would_mutate": False,
    }
    assert payload["recommended_handoff"] == payload["first_blocker_family_handoff"]
    assert payload["stage6_prerequisite_bringup_plan_observed"] is False
    assert payload["blocked_families"] == [
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
    ]
    assert [handoff["id"] for handoff in payload["blocked_family_handoffs"]] == payload["blocked_families"]
    assert [handoff["proof_script"] for handoff in payload["blocked_family_handoffs"]] == [
        "scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status",
        "scripts/lens-summon-overlay-window-blocker-proof.ps1 -Mode Status",
        "scripts/lens-summon-global-hotkey-binding-blocker-proof.ps1 -Mode Status",
        "scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status",
    ]
    assert [handoff["next_smallest_truthful_gap"] for handoff in payload["blocked_family_handoffs"]] == [
        "summon_overlay_window_blocker_boundary",
        "summon_global_hotkey_binding_blocker_boundary",
        "summon_binding_blocker_boundary",
        "summon_authority_blocker_boundary",
    ]
    assert all(handoff["read_only_contract"] is True for handoff in payload["blocked_family_handoffs"])
    assert all(handoff["diagnostic_only"] is True for handoff in payload["blocked_family_handoffs"])
    assert all(handoff["authority_granted"] is False for handoff in payload["blocked_family_handoffs"])
    assert all(handoff["would_execute"] is False for handoff in payload["blocked_family_handoffs"])
    assert all(handoff["would_mutate"] is False for handoff in payload["blocked_family_handoffs"])

    blocker_groups = payload["blocker_groups"]
    assert blocker_groups["resident_host"] == []
    assert blocker_groups["tray_presence"] == ["tray_host_missing"]
    assert blocker_groups["overlay_window"] == ["overlay_window_missing"]
    assert blocker_groups["global_hotkey_binding"] == [
        "global_hotkey_binding_disabled",
        "global_hotkey_registration_disabled",
    ]
    assert blocker_groups["summon_binding"] == [
        "lens_summon_binding_disabled_pending_authority",
    ]
    assert blocker_groups["authority"] == []

    summon_preflight = payload["summon_preflight"]
    assert summon_preflight["status"] == "blocked"
    assert summon_preflight["ready"] is False
    assert summon_preflight["summon_name"] == "Francis Lens Summon"
    assert summon_preflight["config_path"] == "config/runtime/lens/summon.json"
    assert summon_preflight["global_hotkey"] == "Ctrl+Alt+F"
    assert summon_preflight["binding_scope"] == "global"
    assert summon_preflight["palette_route"] == "/lens/status"
    assert summon_preflight["required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
    ]

    lens_status_readback = payload["lens_status_readback"]
    assert lens_status_readback["ok"] is True
    assert lens_status_readback["source"] == "status_path"
    assert lens_status_readback["evidence"] == str(status_path)
    assert lens_status_readback["error"] == ""

    authority_request_readback = payload["os_binding_authority_request_readback"]
    assert authority_request_readback["status"] == "none"
    assert authority_request_readback["ok"] is True
    assert authority_request_readback["kind"] == "lens.os_binding.command_palette_binding_authority.request_readback"
    assert authority_request_readback["route"] == "/lens/os-binding/authority/requests"
    assert authority_request_readback["authority_route"] == "/lens/os-binding/authority"
    assert authority_request_readback["request_route"] == "/lens/os-binding/authority/request"
    assert authority_request_readback["readiness_route"] == "/lens/os-binding/readiness"
    assert authority_request_readback["plan_route"] == "/lens/os-binding/plan"
    assert authority_request_readback["stage6_criterion_status"] == "none"
    assert authority_request_readback["stage6_criterion_readback_ready"] is True
    assert authority_request_readback["authority_required"] == "os_level_command_palette_binding_authority"
    assert authority_request_readback["pending_count"] == 0
    assert authority_request_readback["approved_count"] == 0
    assert authority_request_readback["total_count"] == 0
    assert authority_request_readback["authority_granted"] is False
    assert authority_request_readback["os_level_command_palette_binding_authority"] is False
    assert authority_request_readback["os_level_command_palette"] is False
    assert authority_request_readback["summon_anywhere"] is False
    assert authority_request_readback["opens_palette"] is False
    assert authority_request_readback["registers_hotkey"] is False
    assert authority_request_readback["launches_process"] is False
    assert authority_request_readback["controls_overlay"] is False


def test_lens_summon_anywhere_blockers_proof_advances_past_supervised_resident_host(
    tmp_path: Path,
) -> None:
    status_path = tmp_path / "lens-status.json"
    _write_lens_status_with_supervised_resident_host(status_path)

    proc = _run_proof("-Mode", "Status", "-StatusPath", str(status_path))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["resident_host_supervised_runtime_observed"] is True
    assert payload["stage6_family_projection_observed"] is True
    assert payload["first_blocker_family_handoff_observed"] is True
    assert payload["first_blocker_family"] == "tray_presence"
    assert payload["recommended_handoff_source"] == "first_blocker_family_handoff"
    assert payload["recommended_next_slice"] == "run_tray_presence_blocker_proof"
    assert payload["recommended_proof_script"] == "scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status"
    assert payload["recommended_route"] == "/lens/tray"
    assert payload["recommended_readiness_route"] == "/lens/tray/readiness"
    assert payload["recommended_authority_required"] == "tray_registration_authority"
    assert payload["recommended_authority_granted"] is False
    assert payload["recommended_concrete_handoff_source"] == "first_blocker_family_handoff"
    assert payload["recommended_concrete_next_slice"] == "run_tray_presence_blocker_proof"
    assert payload["recommended_concrete_next_smallest_truthful_gap"] == "summon_overlay_window_blocker_boundary"

    assert payload["blocked_families"] == [
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
    ]
    assert [handoff["id"] for handoff in payload["blocked_family_handoffs"]] == payload["blocked_families"]

    first_handoff = payload["first_blocker_family_handoff"]
    assert first_handoff == {
        "id": "tray_presence",
        "label": "Tray presence",
        "status": "blocked",
        "blockers": ["tray_host_missing"],
        "proof_script": "scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status",
        "route": "/lens/tray",
        "readiness_route": "/lens/tray/readiness",
        "next_step": "run_tray_presence_blocker_proof",
        "next_smallest_truthful_gap": "summon_overlay_window_blocker_boundary",
        "authority_required": "tray_registration_authority",
        "authority_granted": False,
        "read_only_contract": True,
        "diagnostic_only": True,
        "would_execute": False,
        "would_mutate": False,
    }

    blocker_groups = payload["blocker_groups"]
    assert blocker_groups["resident_host"] == []
    assert blocker_groups["tray_presence"] == ["tray_host_missing"]
    assert blocker_groups["authority"] == []

    supervision = payload["resident_host_supervision_readback"]
    assert supervision["process_observed"] is True
    assert supervision["supervision_gate_observed"] is True
    assert supervision["supervisor_fresh_observed"] is True
    assert supervision["process_status"] == "process_observed"
    assert supervision["state_status"] == "resident_running"
    assert supervision["process_alive"] is True
    assert supervision["resident_supervised_runtime"] is True
    assert supervision["resident_host_supervised"] is True
    assert supervision["supervisor_status"] == "resident_supervising"
    assert supervision["fresh_supervisor_readback"] is True
    assert supervision["observed_process_alive"] is True
    assert supervision["observed_pid_matches_host_process"] is True

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["stage6_family_projection"]["status"] == "blocked_families_projected"
    assert checks["first_blocker_family_handoff"]["status"] == "handoff_ready"
    assert all(item["passed"] for item in payload["checks"])


def test_lens_summon_anywhere_blockers_proof_consumes_live_surface_runtime_readback(
    tmp_path: Path,
) -> None:
    status_path = tmp_path / "lens-status.json"
    _write_lens_status_with_supervised_resident_host_and_live_surface_readbacks(status_path)

    proc = _run_proof("-Mode", "Status", "-StatusPath", str(status_path))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["resident_host_supervised_runtime_observed"] is True
    assert payload["surface_runtime_readback_observed"] == {
        "tray_presence": True,
        "overlay_window": True,
        "global_hotkey_binding": True,
        "summon_binding": True,
    }
    assert payload["stage6_family_projection_observed"] is True
    assert payload["first_blocker_family_handoff_observed"] is False
    assert payload["no_blocker_family_handoff_observed"] is True
    assert payload["first_blocker_family"] == ""
    assert payload["recommended_handoff_source"] == "no_blocker_family_handoff"
    assert payload["recommended_next_slice"] == "run_stage6_lens_completion_audit_after_no_summon_blocker_families"
    assert payload["recommended_proof_script"] == "scripts/lens-stage6-completion-audit.ps1 -Mode Status"
    assert payload["recommended_route"] == "/lens/summon"
    assert payload["recommended_readiness_route"] == "/lens/summon/readiness"
    assert payload["recommended_authority_required"] == "none_readback_only"
    assert payload["recommended_authority_granted"] is False
    assert payload["recommended_concrete_next_smallest_truthful_gap"] == "stage6_lens_completion_audit"

    assert payload["blocked_families"] == []
    assert payload["blocked_family_handoffs"] == []
    assert payload["no_blocker_family_handoff"] == {
        "status": "no_blocker_family_remaining",
        "previous_next_smallest_truthful_gap": "summon_anywhere_blockers",
        "next_smallest_truthful_gap": "stage6_lens_completion_audit",
        "next_step": "run_stage6_lens_completion_audit_after_no_summon_blocker_families",
        "proof_script": "scripts/lens-stage6-completion-audit.ps1 -Mode Status",
        "route": "/lens/summon",
        "readiness_route": "/lens/summon/readiness",
        "acceptance_criterion": "summon_anywhere",
        "authority_required": "none_readback_only",
        "authority_granted": False,
        "read_only_contract": True,
        "diagnostic_only": True,
        "would_execute": False,
        "would_mutate": False,
    }

    blocker_groups = payload["blocker_groups"]
    assert blocker_groups["resident_host"] == []
    assert blocker_groups["tray_presence"] == []
    assert blocker_groups["overlay_window"] == []
    assert blocker_groups["global_hotkey_binding"] == []
    assert blocker_groups["summon_binding"] == []
    assert blocker_groups["authority"] == []

    assert payload["surface_runtime_suppressed_blockers"] == {
        "tray_presence": ["tray_host_missing"],
        "overlay_window": ["overlay_window_missing"],
        "global_hotkey_binding": [
            "global_hotkey_binding_disabled",
            "global_hotkey_registration_disabled",
        ],
        "summon_binding": ["lens_summon_binding_disabled_pending_authority"],
    }

    readback = payload["surface_runtime_readback"]
    assert readback["tray_presence"]["requirement_state"] == "ready"
    assert readback["overlay_window"]["requirement_state"] == "visible"
    assert readback["global_hotkey_binding"]["requirement_state"] == "bound"
    assert readback["global_hotkey_binding"]["launch_on_hotkey"] is True
    assert readback["summon_binding"]["requirement_state"] == "bounded_handoff_observed"
    assert readback["summon_binding"]["summon_anywhere"] is False
    assert readback["summon_binding"]["os_level_summon"] is False

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["surface_runtime_readback"]["status"] == "readback_consumed"
    assert checks["stage6_family_projection"]["status"] == "blocked_families_projected"
    assert checks["first_blocker_family_handoff"]["status"] == "no_blocker_family_remaining"
    assert all(item["passed"] for item in payload["checks"])


def test_lens_summon_anywhere_blockers_proof_consumes_live_summon_anywhere_readback(
    tmp_path: Path,
) -> None:
    status_path = tmp_path / "lens-status.json"
    _write_lens_status_with_live_summon_anywhere_readback(status_path)

    proc = _run_proof("-Mode", "Status", "-StatusPath", str(status_path))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert payload["consumed_live_summon_anywhere_readback"] is True
    assert payload["blocked_families"] == []
    assert payload["blocked_family_handoffs"] == []
    assert payload["first_blocker_family"] == ""
    assert payload["recommended_handoff_source"] == "live_summon_anywhere_readback_handoff"
    assert payload["recommended_next_slice"] == "run_stage6_lens_completion_audit_after_live_summon_anywhere_readback"
    assert payload["recommended_proof_script"] == "scripts/lens-stage6-completion-audit.ps1 -Mode Status"
    assert payload["recommended_authority_required"] == "none_readback_only"
    assert payload["recommended_authority_granted"] is False
    assert payload["recommended_concrete_handoff_source"] == "live_summon_anywhere_readback_handoff"
    assert payload["recommended_concrete_next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert payload["recommended_handoff"]["consumed_live_summon_anywhere_readback"] is True

    live_readback = payload["live_summon_anywhere_readback"]
    assert live_readback["summon_gate_ready"] is True
    assert live_readback["os_binding_readiness_ready"] is True
    assert live_readback["summon_runtime_readback_ready"] is True
    assert live_readback["stage6_closure_ready"] is True
    assert live_readback["summon_runtime_summon_anywhere"] is True
    assert live_readback["summon_runtime_os_level_summon"] is True

    assert payload["blockers"] != []
    assert payload["live_summon_anywhere_suppressed_blockers"]["authority"] == []
    assert payload["blocker_groups"] == {
        "resident_host": [],
        "tray_presence": [],
        "overlay_window": [],
        "global_hotkey_binding": [],
        "summon_binding": [],
        "authority": [],
    }

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["first_blocker_family_handoff"]["status"] == "live_readback_consumed"
    assert checks["live_summon_anywhere_readback"]["status"] == "readback_consumed"
    assert all(item["passed"] for item in payload["checks"])

    governance = payload["governance"]
    assert governance["live_summon_anywhere_readback_consumed"] is True
    assert governance["read_only_contract"] is True
    assert governance["execution_authority"] is False
    assert governance["summon_authority"] is False
    assert governance["hotkey_registration_authority"] is False


def test_lens_summon_anywhere_blockers_proof_projects_closure_completion_handoff(
    tmp_path: Path,
) -> None:
    status_path = tmp_path / "lens-status.json"
    _write_lens_status_with_summon_closure_completion_audit_handoff(status_path)

    proc = _run_proof("-Mode", "Status", "-StatusPath", str(status_path))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert payload["recommended_handoff_source"] == "first_blocker_family_handoff"
    assert payload["recommended_next_slice"] == "run_tray_presence_blocker_proof"
    assert payload["recommended_proof_script"] == "scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status"
    assert payload["first_blocker_family_completion_audit_handoff_observed"] is True
    assert payload["recommended_concrete_handoff_source"] == "first_blocker_family_completion_audit_handoff"
    assert payload["recommended_concrete_next_slice"] == (
        "consume_resident_host_process_supervision_handoff_before_stage6_closure"
    )
    assert payload["recommended_concrete_proof_script"] == (
        "scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status -ConsumeProcessSupervisionHandoff"
    )
    assert payload["recommended_concrete_next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert payload["recommended_concrete_authority_required"] == "process_supervision_authority"
    assert payload["recommended_concrete_authority_granted"] is False

    concrete = payload["first_blocker_family_completion_audit_handoff"]
    assert payload["recommended_concrete_handoff"] == concrete
    assert concrete["previous_next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert concrete["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert concrete["authority_required"] == "process_supervision_authority"
    assert concrete["authority_granted"] is False
    assert concrete["read_only_contract"] is True
    assert concrete["diagnostic_only"] is True
    assert concrete["would_execute"] is False
    assert concrete["would_mutate"] is False

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["first_blocker_family_handoff"]["status"] == "handoff_ready"
    assert checks["first_blocker_family_completion_audit_handoff"]["status"] == "closure_handoff_ready"
    assert all(item["passed"] for item in payload["checks"])
    assert payload["governance"]["first_blocker_family_completion_audit_handoff_readback"] is True
    assert payload["governance"]["execution_authority"] is False
    assert payload["governance"]["mutation_authority_granted"] is False


def test_lens_summon_anywhere_blockers_proof_keeps_applied_prerequisite_bringup_out_of_next_handoff(
    tmp_path: Path,
) -> None:
    status_path = tmp_path / "lens-status.json"
    _write_lens_status_with_applied_stage6_prerequisite_bringup(status_path)

    proc = _run_proof("-Mode", "Status", "-StatusPath", str(status_path))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert payload["first_blocker_family"] == "tray_presence"
    assert payload["first_blocker_family_handoff_observed"] is True
    assert payload["recommended_handoff_source"] == "first_blocker_family_handoff"
    assert payload["recommended_next_slice"] == "run_tray_presence_blocker_proof"
    assert payload["recommended_proof_script"] == "scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status"
    assert payload["recommended_route"] == "/lens/tray"
    assert payload["recommended_readiness_route"] == "/lens/tray/readiness"
    assert payload["recommended_authority_required"] == "tray_registration_authority"
    assert payload["recommended_authority_granted"] is False
    assert payload["authority_required"] == "tray_registration_authority"
    assert payload["authority_granted"] is False
    assert payload["stage6_prerequisite_bringup_plan_observed"] is True
    assert payload["stage6_prerequisite_bringup_plan_applied"] is True

    handoff = payload["stage6_prerequisite_bringup_operator_plan_handoff"]
    assert payload["recommended_handoff"] == payload["first_blocker_family_handoff"]
    assert handoff["status"] == "persistent_supervision_enablement_applied"
    assert handoff["applied"] is True
    assert handoff["previous_next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert handoff["next_smallest_truthful_gap"] == "persistent_supervision_execution_boundary"
    assert handoff["next_step"] == ("run_stage6_prerequisite_bringup_review_persistent_supervision_enablement_receipt")
    assert handoff["proof_script"] == "scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status"
    assert handoff["current_truthful_gap_basis"] == (
        "persistent_supervision_enablement_execution_receipt.post_plan.next_smallest_truthful_gap"
    )
    assert handoff["next_operator_action_requirement"] == "persistent_supervision_enablement_receipt"
    assert handoff["next_operator_action"]["id"] == "review_persistent_supervision_enablement_receipt"
    assert handoff["next_operator_command"]["mode"] == "Status"
    assert handoff["required_before_enable_ready"] is True
    assert handoff["missing_required_before_enable"] == []
    assert handoff["read_only_contract"] is True
    assert handoff["diagnostic_only"] is True
    assert handoff["plan_only"] is True
    assert handoff["requires_explicit_operator_execution"] is True
    assert handoff["would_execute"] is False
    assert handoff["would_mutate"] is False

    plan = payload["stage6_prerequisite_bringup_plan"]
    assert plan["present"] is True
    assert plan["status"] == "persistent_supervision_enablement_applied"
    assert plan["required_before_enable_ready"] is True
    assert plan["missing_required_before_enable"] == []
    assert plan["applied"] is True

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["first_blocker_family_handoff"]["status"] == "handoff_ready"
    assert checks["stage6_prerequisite_bringup_plan"]["status"] == "applied_readback_ready"
    assert all(item["passed"] for item in payload["checks"])

    assert payload["governance"]["stage6_prerequisite_bringup_plan_readback"] is True
    assert payload["governance"]["execution_authority"] is False
    assert payload["governance"]["mutation_authority_granted"] is False


def test_lens_summon_anywhere_blockers_proof_accepts_approved_request_without_authority(
    tmp_path: Path,
) -> None:
    status_path = tmp_path / "lens-status.json"
    _write_lens_status_with_approved_os_binding_request_without_authority(status_path)

    proc = _run_proof("-Mode", "Status", "-StatusPath", str(status_path))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_passed"
    assert payload["os_binding_authority_request_readback_observed"] is True
    assert payload["first_blocker_family"] == "tray_presence"
    assert payload["first_blocker_family_handoff_observed"] is True

    authority_request_readback = payload["os_binding_authority_request_readback"]
    assert authority_request_readback["status"] == "approved_no_authority"
    assert authority_request_readback["stage6_criterion_status"] == "approved_no_authority"
    assert authority_request_readback["approved_count"] == 1
    assert authority_request_readback["total_count"] == 1
    assert authority_request_readback["authority_granted"] is False
    assert authority_request_readback["os_level_command_palette_binding_authority"] is False
    assert authority_request_readback["os_level_command_palette"] is False
    assert authority_request_readback["summon_anywhere"] is False
    assert authority_request_readback["opens_palette"] is False
    assert authority_request_readback["registers_hotkey"] is False
    assert authority_request_readback["launches_process"] is False
    assert authority_request_readback["controls_overlay"] is False
    assert authority_request_readback["governance"]["read_only_contract"] is True
    assert authority_request_readback["governance"]["approval_request_write"] is False
    assert authority_request_readback["governance"]["execution_authority"] is False
    assert authority_request_readback["governance"]["approval_decision_authority"] is False
    assert authority_request_readback["governance"]["memory_write"] is False
    assert authority_request_readback["governance"]["resident_claim_authority"] is False

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["summon_preflight_readback"]["status"] == "blocked_readback_ready"
    assert checks["stage6_family_projection"]["status"] == "blocked_families_projected"
    assert checks["first_blocker_family_handoff"]["status"] == "handoff_ready"
    assert checks["summon_side_effects_denied"]["status"] == "diagnostic_bounded"
    assert checks["os_binding_authority_request_readback"]["status"] == "readback_ready"
    assert all(item["passed"] for item in payload["checks"])

    assert payload["governance"] == {
        "diagnostic_only": True,
        "wraps_summon_preflight": True,
        "wraps_lens_status": True,
        "read_only_contract": True,
        "os_binding_authority_request_readback": True,
        "live_summon_anywhere_readback_consumed": False,
        "first_blocker_family_handoff_readback": True,
        "first_blocker_family_completion_audit_handoff_readback": False,
        "stage6_prerequisite_bringup_plan_readback": False,
        "approval_request_write": False,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "local_process_launch_authority": False,
        "hotkey_registration_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
    }


def test_lens_summon_anywhere_blockers_proof_accepts_granted_os_binding_authority(
    tmp_path: Path,
) -> None:
    status_path = tmp_path / "lens-status.json"
    _write_lens_status_with_active_os_binding_grant(status_path)

    proc = _run_proof("-Mode", "Status", "-StatusPath", str(status_path))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_passed"
    assert payload["os_binding_authority_request_readback_observed"] is True

    authority_request_readback = payload["os_binding_authority_request_readback"]
    assert authority_request_readback["status"] == "authority_granted"
    assert authority_request_readback["stage6_criterion_status"] == "authority_granted"
    assert authority_request_readback["authority_granted"] is True
    assert authority_request_readback["os_level_command_palette_binding_authority"] is True
    assert authority_request_readback["os_level_command_palette"] is False
    assert authority_request_readback["summon_anywhere"] is False
    assert authority_request_readback["opens_palette"] is False
    assert authority_request_readback["registers_hotkey"] is False
    assert authority_request_readback["launches_process"] is False
    assert authority_request_readback["controls_overlay"] is False
