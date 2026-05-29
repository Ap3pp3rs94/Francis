from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
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
            str(_repo_root() / "scripts" / "lens-persistent-supervision-prerequisites-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=1200,
    )


def test_lens_persistent_supervision_prerequisites_uses_summon_family_contract_readback() -> None:
    script = (_repo_root() / "scripts" / "lens-persistent-supervision-prerequisites-proof.ps1").read_text(
        encoding="utf-8"
    )

    assert "lens-summon-anywhere-family-chain-proof.ps1" not in script
    assert "FamilyChainResult" not in script
    assert "FamilyChainProofDataRoot" not in script
    assert "uses_summon_family_contract_readback = $true" in script
    assert "wraps_summon_anywhere_family_chain_proof = $false" in script
    assert "summon_family_contract_observed = $SummonFamilyContractObserved" in script
    assert "prerequisites_mapped_to_summon_family_contract" in script
    assert "$FirstMissingRequirementForegroundRunSeconds = 2" in script
    assert "$FirstMissingRequirementHostLaunchRunSeconds = 3" in script
    assert "$FirstMissingRequirementResidentCandidateRunSeconds = 3" in script
    assert "[string]$FirstMissingRequirementForegroundRunSeconds" in script
    assert "[string]$FirstMissingRequirementHostLaunchRunSeconds" in script
    assert "[string]$FirstMissingRequirementResidentCandidateRunSeconds" in script
    assert "[switch]$SeededRuntimeReadbackAllowed" in script
    assert (
        "$FirstMissingRequirementProofRequired = $PreflightFirstMissingRequiredBeforeEnable -eq 'resident_host_process'"
        in script
    )
    assert "skipped_resident_host_process_ready" in script
    assert "function Test-StringArraySubset" in script
    assert "function Test-StringArrayContainsAll" in script
    assert "$ExpectedFirstMissingRequiredBeforeEnable = [string](@($EnablementMissing)[0])" in script
    assert "$PlanCoversEnablementMissingRequirements" in script
    assert "$EnablementFirstMissingRequirementObserved" in script
    assert "$PlanFirstMissingRequirementObserved" in script
    assert "including partially advanced seeded-runtime postures" in script
    denied_keys_block = script[
        script.index("$DeniedKeys = @(") : script.index("$PlanGovernance =", script.index("$DeniedKeys = @("))
    ]
    assert "'local_process_launch_authority'" not in denied_keys_block
    assert "with delegated local process launch" in script


def test_lens_persistent_supervision_prerequisites_align_to_summon_family_contract(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    proc = _run_proof(
        "-Mode",
        "Status",
        "-DataDir",
        str(data_dir),
        "-ChildProofTimeoutSeconds",
        "180",
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.persistent_supervision.prerequisites.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["acceptance_criterion"] == "system_resident_presence"
    assert payload["plan_route"] == "/lens/host/persistent-supervision"
    assert payload["enablement_route"] == "/lens/host/persistent-supervision/enablement"
    assert payload["route_next_smallest_truthful_gap"] == "persistent_supervision_authority_not_granted"
    assert payload["guard_next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    assert payload["summon_family_contract_next_smallest_truthful_gap"] == (
        "persistent_supervision_required_prerequisites_missing"
    )
    assert payload["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    assert (
        payload["recommended_handoff_source"]
        == "persistent_supervision_prerequisites_first_missing_requirement_handoff"
    )
    assert payload["recommended_next_slice"] == (
        "resolve_resident_host_process_before_persistent_supervision_enablement"
    )
    assert payload["recommended_proof_script"] == ("scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status")
    assert payload["authority_required"] == "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites"
    assert payload["authority_granted"] is False
    assert payload["persistent_supervision_plan_readback_observed"] is True
    assert payload["persistent_supervision_enablement_readback_observed"] is True
    assert payload["required_before_enable_observed"] is True
    assert payload["missing_required_before_enable_observed"] is True
    assert payload["first_missing_requirement_observed"] is True
    assert payload["required_before_enable_guard_observed"] is True
    assert payload["dependency_readback_observed"] is True
    assert payload["summon_family_contract_observed"] is True
    assert payload["prerequisites_mapped_to_summon_family_contract"] is True
    assert payload["first_missing_requirement_proof_observed"] is True
    assert payload["first_missing_requirement_side_effects_bounded"] is True
    assert payload["lens_status_operator_readback_observed"] is True
    assert payload["side_effects_denied"] is True
    assert payload["side_effects_bounded"] is True

    expected_prerequisites = [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert payload["required_before_enable"] == expected_prerequisites
    assert payload["missing_required_before_enable"] == expected_prerequisites
    assert payload["first_missing_required_before_enable"] == "resident_host_process"
    first_missing_handoff = payload["first_missing_requirement_handoff"]
    assert first_missing_handoff["id"] == "resident_host_process"
    assert first_missing_handoff["family"] == "resident_host"
    assert first_missing_handoff["route"] == "/lens/host"
    assert first_missing_handoff["readiness_route"] == "/lens/host/runtime-loop/readiness"
    assert first_missing_handoff["proof_script"] == (
        "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status"
    )
    assert first_missing_handoff["next_step"] == (
        "resolve_resident_host_process_before_persistent_supervision_enablement"
    )
    assert first_missing_handoff["next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert first_missing_handoff["read_only_contract"] is True
    assert first_missing_handoff["diagnostic_only"] is True
    assert first_missing_handoff["would_execute"] is False
    assert first_missing_handoff["would_mutate"] is False
    assert payload["recommended_handoff"] == first_missing_handoff

    dependency_readback = {item["id"]: item for item in payload["dependency_readback"]}
    assert dependency_readback == {
        "resident_host_process": {
            "id": "resident_host_process",
            "family": "resident_host",
            "route": "/lens/host",
            "blocker": "resident_host_process_missing",
            "observed": True,
        },
        "tray_presence": {
            "id": "tray_presence",
            "family": "tray_presence",
            "route": "/lens/tray",
            "blocker": "tray_host_missing",
            "observed": True,
        },
        "global_hotkey_binding": {
            "id": "global_hotkey_binding",
            "family": "global_hotkey_binding",
            "route": "/lens/summon",
            "blocker": "global_hotkey_binding_missing",
            "observed": True,
        },
        "overlay_window": {
            "id": "overlay_window",
            "family": "overlay_window",
            "route": "/lens/overlay",
            "blocker": "overlay_window_missing",
            "observed": True,
        },
        "summon_binding": {
            "id": "summon_binding",
            "family": "summon_binding",
            "route": "/lens/summon",
            "blocker": "summon_binding_missing",
            "observed": True,
        },
    }

    summon_family_contract = payload["summon_family_contract"]
    assert summon_family_contract["status"] == "readback_ready"
    assert summon_family_contract["source"] == "enablement_dependency_readback"
    assert summon_family_contract["full_family_chain_proof_reexecuted"] is False
    assert summon_family_contract["mapped_families"] == [
        "resident_host",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert summon_family_contract["requirement_count"] == 5
    assert (
        summon_family_contract["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    )
    assert summon_family_contract["side_effects_denied"] is True

    first_missing_proof = payload["first_missing_requirement_proof"]
    assert first_missing_proof["status"] == "proof_passed"
    assert first_missing_proof["exit_code"] == 0
    assert first_missing_proof["timed_out"] is False
    assert first_missing_proof["kind"] == "lens.resident_host.runtime_blocker_boundary.proof"
    assert first_missing_proof["next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert first_missing_proof["resident_host_process_blocker"] == "resident_host_process_not_supervised"
    assert first_missing_proof["runtime_handoff_observed"] is True
    assert first_missing_proof["bounded_runtime_observed"] is True
    assert first_missing_proof["process_supervision_handoff_observed"] is True
    assert first_missing_proof["side_effects_bounded"] is True
    assert "resident_host_process_not_supervised" in first_missing_proof["blockers"]
    assert "process_supervision_authority_not_granted" in first_missing_proof["blockers"]

    route_readback = payload["route_readback"]
    assert route_readback["status"] == "readback_ready"
    assert route_readback["exit_code"] == 0
    assert route_readback["timed_out"] is False
    assert route_readback["plan_status"] == "blocked"
    assert route_readback["enablement_status"] == "blocked"
    assert route_readback["plan_next_smallest_truthful_gap"] == "persistent_supervision_authority_not_granted"
    assert route_readback["enablement_next_smallest_truthful_gap"] == ("persistent_supervision_authority_not_granted")
    assert route_readback["guard_plan_next_smallest_truthful_gap"] == (
        "persistent_supervision_required_prerequisites_missing"
    )
    assert route_readback["guard_enablement_next_smallest_truthful_gap"] == (
        "persistent_supervision_required_prerequisites_missing"
    )
    assert route_readback["guard_plan_status"] == "blocked"
    assert route_readback["guard_enablement_status"] == "blocked"

    guard_readback = payload["guard_readback"]
    assert guard_readback == {
        "projection": "synthetic_manifest_readiness_guard",
        "observed": True,
        "plan_status": "blocked",
        "enablement_status": "blocked",
        "plan_next_smallest_truthful_gap": "persistent_supervision_required_prerequisites_missing",
        "enablement_next_smallest_truthful_gap": "persistent_supervision_required_prerequisites_missing",
        "required_before_enable": expected_prerequisites,
        "missing_required_before_enable": expected_prerequisites,
        "blocked_requirements": ["required_before_enable"],
        "blockers": ["persistent_supervision_required_prerequisites_missing"],
    }

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["persistent_supervision_plan_route_readback"]["status"] == "blocked_readback_ready"
    assert checks["persistent_supervision_enablement_route_readback"]["status"] == "blocked_readback_ready"
    assert checks["required_before_enable_readback"]["status"] == "prerequisites_projected"
    assert checks["missing_required_before_enable_readback"]["status"] == "missing_prerequisites_projected"
    assert checks["first_missing_requirement_handoff"]["status"] == "first_missing_requirement_bound"
    assert checks["required_before_enable_readiness_guard"]["status"] == "prerequisite_guard_blocks_enablement"
    assert checks["enablement_dependency_readback"]["status"] == "dependency_routes_bound"
    assert checks["summon_family_contract_alignment"]["status"] == "family_contract_aligned"
    assert checks["first_missing_requirement_proof_consumed"]["status"] == "proof_consumed"
    assert checks["lens_status_operator_readback"]["status"] == "operator_readback_ready"
    assert checks["side_effects_denied"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    assert payload["governance"] == {
        "diagnostic_only": True,
        "read_only_contract": False,
        "route_readback_contract": True,
        "wraps_persistent_supervision_plan_route": True,
        "wraps_persistent_supervision_enablement_route": True,
        "wraps_lens_status": True,
        "uses_summon_family_contract_readback": True,
        "wraps_summon_anywhere_family_chain_proof": False,
        "wraps_first_missing_requirement_proof": True,
        "readiness_guard_projection": True,
        "bounded_local_process_launch": True,
        "bounded_process_launch": True,
        "temporary_runtime_state_write": True,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "local_process_launch_authority": True,
        "api_local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "persistent_supervision_enablement_authority": False,
        "persistent_supervision_execution_authority": False,
        "service_config_write_authority": False,
        "tray_registration_authority": False,
        "hotkey_registration_authority": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "memory_write": False,
        "receipt_write_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
    }
    assert not (data_dir / "runtime" / "lens-host-supervisor" / "status.json").exists()
    assert not (data_dir / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_persistent_supervision_prerequisites_consumes_seeded_resident_runtime(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    host_dir = data_dir / "runtime" / "lens-host"
    supervisor_dir = data_dir / "runtime" / "lens-host-supervisor"
    host_dir.mkdir(parents=True)
    supervisor_dir.mkdir(parents=True)
    pid = os.getpid()
    now = datetime.now(UTC).isoformat()
    (host_dir / "lens-host.pid").write_text(str(pid), encoding="utf-8")
    (host_dir / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.runtime_state",
                "status": "resident_running",
                "pid": pid,
                "updated_at": now,
            }
        ),
        encoding="utf-8",
    )
    (supervisor_dir / "status.json").write_text(
        json.dumps(
            {
                "status": "resident_supervising",
                "mode": "supervise_resident",
                "host_mode": "resident",
                "supervisor_pid": pid,
                "observed_pid": pid,
                "observed_state": "resident_running",
                "resident_supervised_runtime": True,
                "process_supervision_authority": True,
                "process_restart_authority": False,
                "service_control_authority": False,
                "updated_at": now,
            }
        ),
        encoding="utf-8",
    )

    proc = _run_proof(
        "-Mode",
        "Status",
        "-DataDir",
        str(data_dir),
        "-SeededRuntimeReadbackAllowed",
        "-ChildProofTimeoutSeconds",
        "180",
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["seeded_runtime_readback_allowed"] is True
    assert payload["resident_host_process_ready_in_prerequisites"] is True
    assert payload["first_missing_requirement_proof_required"] is False
    assert payload["first_missing_requirement_proof_observed"] is True
    assert payload["first_missing_requirement_side_effects_bounded"] is True
    assert payload["missing_required_before_enable"] == [
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert payload["first_missing_required_before_enable"] == "tray_presence"
    assert payload["recommended_next_slice"] == "resolve_tray_presence_before_persistent_supervision_enablement"
    assert payload["recommended_proof_script"] == "scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status"
    proof = payload["first_missing_requirement_proof"]
    assert proof["proof_required"] is False
    assert proof["status"] == "skipped_resident_host_process_ready"
    assert proof["kind"] == "lens.persistent_supervision.first_missing_requirement.proof_skipped"
    dependency_readback = {item["id"]: item for item in payload["dependency_readback"]}
    assert dependency_readback["resident_host_process"] == {
        "id": "resident_host_process",
        "family": "resident_host",
        "route": "/lens/host",
        "blocker": "",
        "observed": True,
    }
    assert dependency_readback["tray_presence"]["blocker"] == "tray_host_missing"
