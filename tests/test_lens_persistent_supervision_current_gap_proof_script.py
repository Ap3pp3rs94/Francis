from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from tests.powershell_script_runner import run_powershell_script


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_persistent_supervision_current_gap_proof_consumes_authority_chain_without_audit(
    tmp_path: Path,
) -> None:
    env = os.environ.copy()
    env["FRANCIS_DATA_DIR"] = str(tmp_path / "data")
    old_env = os.environ.copy()
    try:
        os.environ.update(env)
        proc = run_powershell_script(
            _powershell(),
            _repo_root() / "scripts" / "lens-persistent-supervision-current-gap-proof.ps1",
            ["-Mode", "Status"],
            cwd=_repo_root(),
            timeout_seconds=180,
        )
    finally:
        os.environ.clear()
        os.environ.update(old_env)

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.persistent_supervision_current_gap.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["mode"] == "status"
    assert payload["stage"] == "Stage 6 / Lens MVP"

    assert payload["persistent_supervision_plan_observed"] is True
    assert payload["persistent_supervision_enablement_authority_proof_observed"] is True
    assert payload["persistent_supervision_execution_authority_proof_observed"] is True
    assert payload["persistent_supervision_resident_claim_boundary_proof_observed"] is True
    assert payload["persistent_supervision_authority_chain_consumed"] is True
    assert payload["persistent_supervision_current_gap_observed"] is True
    assert payload["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    assert payload["recommended_handoff_source"] == "persistent_supervision_plan_first_missing_requirement_handoff"
    assert payload["recommended_next_slice"] == (
        "resolve_persistent_supervision_required_prerequisites_before_enablement"
    )
    assert payload["recommended_proof_script"] == (
        "scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status"
    )
    assert payload["recommended_route"] == "/lens/host/persistent-supervision"
    assert payload["recommended_readiness_route"] == "/lens/host/persistent-supervision/enablement"
    assert payload["authority_required"] == ("resident_host_process_tray_hotkey_overlay_and_summon_prerequisites")
    assert payload["authority_granted"] is False
    assert payload["missing_required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert payload["first_missing_required_before_enable"] == "resident_host_process"

    first_missing = payload["first_missing_requirement_handoff"]
    assert first_missing["id"] == "resident_host_process"
    assert first_missing["family"] == "resident_host"
    assert first_missing["route"] == "/lens/host"
    assert first_missing["readiness_route"] == "/lens/host/runtime-loop/readiness"
    assert first_missing["proof_script"].startswith("scripts/lens-resident-")
    assert first_missing["proof_script"].endswith("-proof.ps1 -Mode Status")
    assert first_missing["next_smallest_truthful_gap"] in {
        "resident_host_process_not_supervised",
        "resident_supervision_not_persistent",
    }
    assert first_missing["read_only_contract"] is True
    assert first_missing["diagnostic_only"] is True
    assert first_missing["would_execute"] is False
    assert first_missing["would_mutate"] is False

    handoff = payload["handoff"]
    assert handoff["status"] == "blocked"
    assert handoff["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    assert handoff["first_missing_required_before_enable"] == "resident_host_process"
    assert handoff["first_missing_requirement_handoff"] == first_missing
    assert handoff["proof_script"] == "scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status"
    assert handoff["route"] == "/lens/host/persistent-supervision"
    assert handoff["readiness_route"] == "/lens/host/persistent-supervision/enablement"
    assert handoff["authority_granted"] is False
    assert handoff["read_only_contract"] is True
    assert handoff["diagnostic_only"] is True
    assert handoff["would_execute"] is False
    assert handoff["would_mutate"] is False

    authority_chain = payload["authority_chain"]
    assert authority_chain["enablement_authority_consumed"] is True
    assert authority_chain["execution_authority_consumed"] is True
    assert authority_chain["resident_claim_boundary_consumed"] is True
    assert authority_chain["final_authority_family_consumed"] is True
    assert authority_chain["next_audit_gap_after_authority_chain"] == "stage6_lens_completion_audit"
    assert payload["stage6_completion_audit_required"] is True
    assert payload["stage6_completion_audit_not_run"] is True
    assert payload["stage6_completion_audit_script"] == "scripts/lens-stage6-completion-audit.ps1"

    assert payload["persistent_supervision_plan_summary"]["kind"] == "lens.host.persistent_supervision_plan"
    assert payload["persistent_supervision_plan_summary"]["status"] == "blocked"
    assert (
        payload["persistent_supervision_plan_summary"]["next_smallest_truthful_gap"]
        == "persistent_supervision_required_prerequisites_missing"
    )
    assert (
        payload["persistent_supervision_enablement_authority_summary"]["next_smallest_truthful_gap"]
        == "persistent_supervision_execution_authority_or_resident_claim_boundary"
    )
    assert (
        payload["persistent_supervision_execution_authority_summary"]["next_smallest_truthful_gap"]
        == "persistent_supervision_resident_claim_authority_boundary"
    )
    assert (
        payload["persistent_supervision_resident_claim_boundary_summary"]["next_smallest_truthful_gap"]
        == "stage6_lens_completion_audit"
    )

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["persistent_supervision_plan_readback"]["status"] == "required_prerequisites_missing"
    assert checks["enablement_authority_proof"]["status"] == "proof_passed"
    assert checks["execution_authority_proof"]["status"] == "proof_passed"
    assert checks["resident_claim_boundary_proof"]["status"] == "proof_passed"
    assert checks["authority_chain_consumed"]["status"] == "consumed"
    assert checks["current_gap"]["status"] == "persistent_supervision_required_prerequisites_missing"
    assert checks["first_missing_requirement_handoff"]["status"] == "resident_host_process_handoff_ready"
    assert checks["product_side_effects_denied"]["status"] == "product_read_only"
    assert all(item["passed"] for item in payload["checks"])

    assert payload["governance"] == {
        "diagnostic_only": True,
        "product_read_only_contract": True,
        "runs_child_proofs": True,
        "child_proofs_use_test_fixture_approval_decisions": True,
        "child_proofs_write_temp_fixture_receipts": True,
        "stage6_completion_audit_not_run": True,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "service_config_write_authority": False,
        "persistent_supervision_enablement_authority": False,
        "persistent_supervision_execution_authority": False,
        "memory_write": False,
        "product_receipt_write_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
        "would_execute_product_path": False,
        "would_mutate_product_path": False,
    }
