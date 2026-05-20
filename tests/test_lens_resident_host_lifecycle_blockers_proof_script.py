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
            str(_repo_root() / "scripts" / "lens-resident-host-lifecycle-blockers-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_resident_host_lifecycle_blockers_proof_consumes_preflight_groups() -> None:
    proc = _run_proof("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.resident_host.lifecycle_blockers_proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["first_blocker_group"] == "runtime"
    assert payload["next_smallest_truthful_gap"] == "resident_host_runtime_blocker_boundary"
    assert payload["recommended_handoff_source"] == "resident_host_lifecycle_first_blocker_group"
    assert payload["recommended_next_slice"] == "run_resident_host_runtime_boundary_proof"
    assert payload["recommended_proof_script"] == "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status"
    assert payload["recommended_route"] == "/lens/host/manifest"
    assert payload["recommended_readiness_route"] == "/lens/host/runtime-loop/readiness"
    assert payload["authority_required"] == "process_supervision_authority"
    assert payload["authority_granted"] is False

    host_preflight = payload["host_preflight"]
    assert host_preflight["ok"] is True
    assert host_preflight["kind"] == "lens.host.lifecycle_preflight"
    assert host_preflight["status"] == "blocked"
    assert host_preflight["ready"] is False
    assert host_preflight["next_smallest_truthful_gap"] == "resident_host_lifecycle_blockers"

    assert set(payload["blocked_groups"]) == {
        "runtime",
        "service_plan",
        "supervision",
        "surface_dependencies",
        "authority",
    } | ({"process_readback"} if "process_readback" in payload["blocked_groups"] else set())
    assert payload["summary"] == {
        "group_total": 6,
        "blocked_group_total": len(payload["blocked_groups"]),
        "required_groups_present": True,
        "lifecycle_handoff_consumed": True,
    }

    groups = payload["lifecycle_blocker_groups"]
    assert groups["runtime"]["status"] == "blocked"
    assert groups["runtime"]["route"] == "/lens/host/manifest"
    assert "lens_host_persistent_supervision_prerequisites_pending" in groups["runtime"]["blockers"]

    recommended_handoff = payload["recommended_handoff"]
    assert recommended_handoff["id"] == "resident_host_runtime_blocker"
    assert recommended_handoff["status"] == "blocked"
    assert recommended_handoff["next_smallest_truthful_gap"] == "resident_host_runtime_blocker_boundary"
    assert recommended_handoff["next_step"] == "run_resident_host_runtime_boundary_proof"
    assert recommended_handoff["proof_script"] == "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status"
    assert recommended_handoff["route"] == "/lens/host/manifest"
    assert recommended_handoff["readiness_route"] == "/lens/host/runtime-loop/readiness"
    assert recommended_handoff["acceptance_criterion"] == "summon_anywhere"
    assert recommended_handoff["blocker_group"] == "runtime"
    assert "lens_host_persistent_supervision_prerequisites_pending" in recommended_handoff["blockers"]
    assert recommended_handoff["authority_required"] == "process_supervision_authority"
    assert recommended_handoff["authority_granted"] is False
    assert recommended_handoff["read_only_contract"] is True
    assert recommended_handoff["diagnostic_only"] is True
    assert recommended_handoff["would_execute"] is False
    assert recommended_handoff["would_mutate"] is False

    assert groups["process_readback"]["status"] in {"blocked", "clear"}
    assert groups["process_readback"]["route"] == "/lens/host/manifest"
    assert isinstance(groups["process_readback"]["blockers"], list)

    assert groups["service_plan"]["status"] == "blocked"
    assert groups["service_plan"]["route"] == "scripts/service-install.ps1 -Mode Plan"
    assert "installable_false" in groups["service_plan"]["blockers"]
    assert "service_install_authority_false" in groups["service_plan"]["blockers"]
    assert "service_control_authority_false" in groups["service_plan"]["blockers"]

    assert groups["supervision"]["status"] == "blocked"
    assert groups["supervision"]["route"] == "/lens/host/supervision/authority/readiness"
    assert "process_supervision_enabled" not in groups["supervision"]["blockers"]
    assert "process_restart_authority" in groups["supervision"]["blockers"]
    assert "persistent_supervision_enabled" not in groups["supervision"]["blockers"]
    assert "process_restart_authority" in groups["supervision"]["blockers"]
    assert "receipt_write_authority" in groups["supervision"]["blockers"]
    assert "resident_claim_authority" in groups["supervision"]["blockers"]

    assert groups["surface_dependencies"]["status"] == "blocked"
    assert groups["surface_dependencies"]["route"] == "/lens/preflight"
    assert "tray_host_missing" in groups["surface_dependencies"]["blockers"]
    assert "global_hotkey_binding_missing" in groups["surface_dependencies"]["blockers"]
    assert "overlay_window_missing" in groups["surface_dependencies"]["blockers"]
    assert "summon_binding_missing" in groups["surface_dependencies"]["blockers"]

    assert groups["authority"]["status"] == "blocked"
    assert groups["authority"]["route"] == "/lens/host/supervision/authority"
    assert "service_control_authority_false" in groups["authority"]["blockers"]
    assert "process_restart_authority" in groups["authority"]["blockers"]
    assert "receipt_write_authority" in groups["authority"]["blockers"]
    assert "resident_claim_authority" in groups["authority"]["blockers"]

    for group in groups.values():
        assert group["readback_only"] is True
        assert group["authority_granted"] is False
        assert group["would_execute"] is False

    assert payload["governance"] == {
        "diagnostic_only": True,
        "wraps_existing_preflight": True,
        "read_only_contract": True,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "hotkey_registration_authority": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "receipt_write_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
    }
