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
            str(_repo_root() / "scripts" / "lens-persistent-supervision-prerequisites-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=210,
    )


def test_lens_persistent_supervision_prerequisites_align_to_summon_family_chain(
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
    assert payload["family_chain_next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert payload["next_smallest_truthful_gap"] == "persistent_supervision_enablement_disabled"
    assert payload["persistent_supervision_plan_readback_observed"] is True
    assert payload["persistent_supervision_enablement_readback_observed"] is True
    assert payload["required_before_enable_observed"] is True
    assert payload["missing_required_before_enable_observed"] is True
    assert payload["dependency_readback_observed"] is True
    assert payload["family_chain_observed"] is True
    assert payload["prerequisites_mapped_to_family_chain"] is True
    assert payload["lens_status_operator_readback_observed"] is True
    assert payload["side_effects_denied"] is True

    expected_prerequisites = [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert payload["required_before_enable"] == expected_prerequisites
    assert payload["missing_required_before_enable"] == expected_prerequisites

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

    family_chain = payload["family_chain"]
    assert family_chain["status"] == "proof_passed"
    assert family_chain["exit_code"] == 0
    assert family_chain["timed_out"] is False
    assert family_chain["blocked_families"] == [
        "resident_host",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
        "authority",
    ]
    assert family_chain["handoff_count"] == 6
    assert family_chain["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert family_chain["side_effects_denied"] is True

    route_readback = payload["route_readback"]
    assert route_readback["status"] == "readback_ready"
    assert route_readback["exit_code"] == 0
    assert route_readback["timed_out"] is False
    assert route_readback["plan_status"] == "blocked"
    assert route_readback["enablement_status"] == "blocked"
    assert route_readback["plan_next_smallest_truthful_gap"] == "persistent_supervision_authority_not_granted"
    assert route_readback["enablement_next_smallest_truthful_gap"] == ("persistent_supervision_authority_not_granted")

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["persistent_supervision_plan_route_readback"]["status"] == "blocked_readback_ready"
    assert checks["persistent_supervision_enablement_route_readback"]["status"] == "blocked_readback_ready"
    assert checks["required_before_enable_readback"]["status"] == "prerequisites_projected"
    assert checks["missing_required_before_enable_readback"]["status"] == "missing_prerequisites_projected"
    assert checks["enablement_dependency_readback"]["status"] == "dependency_routes_bound"
    assert checks["summon_family_chain_alignment"]["status"] == "family_chain_aligned"
    assert checks["lens_status_operator_readback"]["status"] == "operator_readback_ready"
    assert checks["side_effects_denied"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    assert payload["governance"] == {
        "diagnostic_only": True,
        "read_only_contract": True,
        "wraps_persistent_supervision_plan_route": True,
        "wraps_persistent_supervision_enablement_route": True,
        "wraps_lens_status": True,
        "wraps_summon_anywhere_family_chain_proof": True,
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
