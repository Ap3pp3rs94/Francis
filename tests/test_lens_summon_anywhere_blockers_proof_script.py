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
    assert payload["first_blocker_family"] == "resident_host"
    assert payload["first_blocker_family_handoff"] == {
        "id": "resident_host",
        "label": "Resident host",
        "status": "blocked",
        "blockers": ["local_process_launch_authority_not_granted"],
        "proof_script": "scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status",
        "route": "/lens/host",
        "readiness_route": "/lens/host/runtime-loop/readiness",
        "next_step": "run_resident_host_blocker_proof",
        "next_smallest_truthful_gap": "resident_host_runtime_blocker_boundary",
        "authority_required": "resident_runtime_execution_authority",
        "authority_granted": False,
        "read_only_contract": True,
        "diagnostic_only": True,
        "would_execute": False,
        "would_mutate": False,
    }
    assert payload["blocked_families"] == [
        "resident_host",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
        "authority",
    ]
    assert [handoff["id"] for handoff in payload["blocked_family_handoffs"]] == payload["blocked_families"]
    assert [handoff["proof_script"] for handoff in payload["blocked_family_handoffs"]] == [
        "scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status",
        "scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status",
        "scripts/lens-summon-overlay-window-blocker-proof.ps1 -Mode Status",
        "scripts/lens-summon-global-hotkey-binding-blocker-proof.ps1 -Mode Status",
        "scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status",
        "scripts/lens-summon-authority-blocker-proof.ps1 -Mode Status",
    ]
    assert [handoff["next_smallest_truthful_gap"] for handoff in payload["blocked_family_handoffs"]] == [
        "resident_host_runtime_blocker_boundary",
        "summon_overlay_window_blocker_boundary",
        "summon_global_hotkey_binding_blocker_boundary",
        "summon_binding_blocker_boundary",
        "summon_authority_blocker_boundary",
        "stage6_lens_completion_audit",
    ]
    assert all(handoff["read_only_contract"] is True for handoff in payload["blocked_family_handoffs"])
    assert all(handoff["diagnostic_only"] is True for handoff in payload["blocked_family_handoffs"])
    assert all(handoff["authority_granted"] is False for handoff in payload["blocked_family_handoffs"])
    assert all(handoff["would_execute"] is False for handoff in payload["blocked_family_handoffs"])
    assert all(handoff["would_mutate"] is False for handoff in payload["blocked_family_handoffs"])

    blocker_groups = payload["blocker_groups"]
    assert blocker_groups["resident_host"] == ["local_process_launch_authority_not_granted"]
    assert blocker_groups["tray_presence"] == ["tray_host_missing"]
    assert blocker_groups["overlay_window"] == ["overlay_window_missing"]
    assert blocker_groups["global_hotkey_binding"] == [
        "global_hotkey_binding_disabled",
        "global_hotkey_registration_disabled",
        "hotkey_registration_authority_not_granted",
    ]
    assert blocker_groups["summon_binding"] == [
        "lens_summon_binding_disabled_pending_authority",
        "summon_authority_not_granted",
    ]
    assert blocker_groups["authority"] == [
        "summon_authority_not_granted",
        "hotkey_registration_authority_not_granted",
        "overlay_control_authority_not_granted",
        "local_process_launch_authority_not_granted",
    ]

    summon_preflight = payload["summon_preflight"]
    assert summon_preflight["status"] == "blocked"
    assert summon_preflight["ready"] is False
    assert summon_preflight["summon_name"] == "Francis Lens Summon"
    assert summon_preflight["config_path"] == "config/runtime/lens/summon.json"
    assert summon_preflight["global_hotkey"] == "Ctrl+Alt+Space"
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
        "first_blocker_family_handoff_readback": True,
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
