from __future__ import annotations

import json
import os
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
            str(_repo_root() / "scripts" / "lens-persistent-supervision-enablement-transition-plan-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=360,
    )


def test_lens_persistent_supervision_enablement_transition_plan_is_readback_only(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    proc = _run_proof("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.persistent_supervision_enablement_transition_plan.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["transition_plan_observed"] is True
    assert payload["transition_plan_ready"] is False
    assert payload["persistent_supervision_config_gate_enabled"] is True
    assert payload["persistent_supervision_enablement_disabled"] is False
    assert payload["persistent_supervision_prerequisites_proof_observed"] is True
    assert payload["persistent_supervision_required_prerequisites_guard_observed"] is True
    assert payload["persistent_supervision_service_install_plan_proof_observed"] is True
    assert payload["persistent_supervision_resident_claim_boundary_observed"] is True
    assert payload["persistent_supervision_plan_observed"] is True
    assert payload["windows_service_supported"] is (os.name == "nt")
    assert payload["service_install_plan_supported"] is (os.name == "nt")
    assert payload["service_plan_status"] == ("blocked" if os.name == "nt" else "unsupported_platform")
    if os.name == "nt":
        assert set(payload["service_plan_blocked_by"]) == {
            "installable_false",
            "install_authority_false",
            "service_install_authority_false",
            "service_control_authority_false",
        }
    else:
        assert payload["service_plan_blocked_by"] == ["unsupported_platform"]

    assert payload["required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert payload["enabled_config_toggles"] == [
        "process_supervision_enabled",
        "persistent_supervision_enabled",
    ]
    assert payload["disabled_config_toggles"] == []

    authority_chain = payload["authority_chain"]
    assert authority_chain["host_supervision_authority"] is True
    assert authority_chain["persistent_supervision_enablement_authority"] is True
    assert authority_chain["service_config_write_authority"] is True
    assert authority_chain["persistent_supervision_execution_authority"] is True
    assert authority_chain["receipt_write_authority"] is True
    assert authority_chain["resident_claim_authority"] is False
    assert authority_chain["final_authority_family_consumed"] is True

    assert payload["side_effects_denied"] is True
    assert payload["applied"] is False
    assert payload["executed"] is False
    assert payload["service_config_updated"] is False
    assert payload["would_update_service_config"] is False
    assert payload["would_enable_process_supervision"] is False
    assert payload["would_enable_persistent_supervision"] is False
    assert payload["would_install_service"] is False
    assert payload["would_start_service"] is False
    assert payload["would_supervise_process"] is False
    assert payload["would_restart_process"] is False
    assert payload["would_write_receipt"] is False
    assert payload["would_write_memory"] is False
    assert payload["would_claim_resident"] is False
    assert payload["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"

    steps = {item["id"]: item for item in payload["transition_plan"]}
    assert list(steps) == [
        "read_required_prerequisites",
        "verify_service_install_plan_boundary",
        "consume_persistent_supervision_authority_chain",
        "verify_required_prerequisite_guard",
        "keep_runtime_mutation_denied",
    ]
    assert steps["read_required_prerequisites"]["status"] == "readback_ready"
    assert steps["verify_service_install_plan_boundary"]["status"] == payload["service_plan_status"]
    assert steps["consume_persistent_supervision_authority_chain"]["status"] == "resident_claim_boundary_observed"
    assert steps["verify_required_prerequisite_guard"]["status"] == "blocked_prerequisites"
    assert steps["keep_runtime_mutation_denied"]["status"] == "no_side_effects"
    assert all(step["would_execute"] is False for step in steps.values())
    assert all(step["would_mutate"] is False for step in steps.values())

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["persistent_supervision_prerequisites_proof"]["status"] == "proof_observed"
    assert checks["service_install_plan_boundary"]["status"] == payload["service_plan_status"]
    assert checks["persistent_supervision_authority_chain"]["status"] == "resident_claim_boundary_observed"
    assert checks["required_prerequisite_guard_readback"]["status"] == "blocked_prerequisites"
    assert checks["transition_side_effects_denied"]["status"] == "no_side_effects"
    assert all(item["passed"] for item in payload["checks"])

    assert "persistent_supervision_required_prerequisites_missing" in payload["blockers"]
    assert "resident_claim_authority_not_granted" in payload["blockers"]

    assert payload["governance"] == {
        "diagnostic_only": True,
        "read_only_transition_plan": True,
        "wraps_existing_prerequisite_proof": True,
        "wraps_existing_service_install_plan_proof": True,
        "wraps_existing_resident_claim_boundary_proof": True,
        "test_fixture_approval_requests": True,
        "test_fixture_approval_decisions": True,
        "test_fixture_authority_receipts": True,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "persistent_supervision_enablement_authority": False,
        "persistent_supervision_execution_authority": False,
        "service_config_write_authority": False,
        "receipt_write_authority": False,
        "memory_write": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
    }

    assert not (data_dir / "runtime" / "lens-host-supervisor" / "status.json").exists()
    assert not (data_dir / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()
