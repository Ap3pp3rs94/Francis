from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from tests.powershell_script_runner import run_powershell_script


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_persistent_supervision_current_gap_proof_consumes_authority_chain_without_audit(
    tmp_path: Path,
) -> None:
    proc = run_powershell_script(
        _powershell(),
        _repo_root() / "scripts" / "lens-persistent-supervision-current-gap-proof.ps1",
        [
            "-Mode",
            "Status",
            "-DataDir",
            str(tmp_path / "data"),
            "-ChildProofTimeoutSeconds",
            "180",
        ],
        cwd=_repo_root(),
        timeout_seconds=210,
    )

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
    assert payload["recommended_handoff_source"] == "persistent_supervision_required_prerequisites_handoff"
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
    assert (
        payload["recommended_first_missing_handoff_source"]
        == "persistent_supervision_plan_first_missing_requirement_handoff"
    )
    if first_missing["next_smallest_truthful_gap"] == "resident_supervision_not_persistent":
        expected_first_missing_next_slice = (
            "resolve_resident_supervision_persistence_before_persistent_supervision_enablement"
        )
        expected_first_missing_authority_required = "persistent_process_supervision_authority"
    elif first_missing.get("blocker") == "resident_host_process_not_supervised":
        expected_first_missing_next_slice = "consume_resident_host_process_supervision_handoff_before_stage6_closure"
        expected_first_missing_authority_required = "process_supervision_authority"
    else:
        expected_first_missing_next_slice = "resolve_resident_host_process_before_persistent_supervision_enablement"
        expected_first_missing_authority_required = "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites"
    assert payload["recommended_first_missing_next_slice"] == first_missing.get(
        "next_step",
        expected_first_missing_next_slice,
    )
    assert payload["recommended_first_missing_proof_script"] == first_missing["proof_script"]
    assert payload["recommended_first_missing_route"] == first_missing["route"]
    assert payload["recommended_first_missing_readiness_route"] == first_missing["readiness_route"]
    assert payload["recommended_first_missing_authority_required"] == first_missing.get(
        "authority_required",
        expected_first_missing_authority_required,
    )

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
    assert payload["persistent_supervision_plan_summary"]["timed_out"] is False
    assert payload["persistent_supervision_plan_summary"]["timeout_seconds"] == 180
    assert payload["persistent_supervision_plan_summary"]["status"] == "blocked"
    assert (
        payload["persistent_supervision_plan_summary"]["next_smallest_truthful_gap"]
        == "persistent_supervision_required_prerequisites_missing"
    )
    assert (
        payload["persistent_supervision_enablement_authority_summary"]["next_smallest_truthful_gap"]
        == "persistent_supervision_execution_authority_or_resident_claim_boundary"
    )
    assert payload["persistent_supervision_enablement_authority_summary"]["timed_out"] is False
    assert (
        payload["persistent_supervision_execution_authority_summary"]["next_smallest_truthful_gap"]
        == "persistent_supervision_resident_claim_authority_boundary"
    )
    assert payload["persistent_supervision_execution_authority_summary"]["timed_out"] is False
    assert (
        payload["persistent_supervision_resident_claim_boundary_summary"]["next_smallest_truthful_gap"]
        == "stage6_lens_completion_audit"
    )
    assert payload["persistent_supervision_resident_claim_boundary_summary"]["timed_out"] is False

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
        "child_proof_timeout_seconds": 180,
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


def test_persistent_supervision_current_gap_consumes_applied_receipt_resident_claim_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_root = tmp_path / "data"
    service_config_path = tmp_path / "service-config" / "lens-host.json"
    service_config_source = _repo_root() / "config" / "runtime" / "services" / "lens-host.json"
    service_config = json.loads(service_config_source.read_text(encoding="utf-8"))
    service_config.update(
        {
            "process_supervision_enabled": True,
            "persistent_supervision_enabled": True,
            "supervision_ready": True,
            "supervision_blocked_reason": "",
            "blocked_reason": "",
        }
    )
    service_config_path.parent.mkdir(parents=True, exist_ok=True)
    service_config_path.write_text(json.dumps(service_config, indent=2), encoding="utf-8")
    monkeypatch.setenv("FRANCIS_LENS_HOST_SERVICE_CONFIG_PATH", str(service_config_path))

    created_ts = int(datetime.now(UTC).timestamp())
    _write_json(
        data_root / "lens" / "host_supervision_executions" / "lhse_test_resident_start.json",
        {
            "kind": "lens.host.supervision.execution.receipt",
            "receipt_id": "lhse_test_resident_start",
            "status": "resident_supervision_started",
            "created_ts": created_ts,
            "execution": {
                "supervision_mode": "resident_start",
                "bounded_supervised_session": False,
                "temporary_host_process_observed": True,
                "resident_host_process": True,
                "resident_runtime_candidate_supervised": True,
                "resident_supervised_runtime": True,
                "next_smallest_truthful_gap": "summon_tray_presence_blocker_boundary",
                "stop_command": "scripts/lens-host-supervisor.ps1 -Mode StopResident",
            },
            "resident_claim": {
                "resident_host_process_claimed": False,
                "resident_runtime_claimed": False,
                "resident_claim_authority": False,
            },
        },
    )
    _write_json(
        data_root / "lens" / "pse_executions" / "lpsee_test_applied.json",
        {
            "kind": "lens.host.persistent_supervision_enablement_execution.receipt",
            "receipt_id": "lpsee_test_applied",
            "id": "lpsee_test_applied",
            "status": "service_config_updated",
            "route": "/lens/host/persistent-supervision/enablement/execution/apply",
            "method": "POST",
            "source_kind": "lens.host.persistent_supervision_enablement_execution.execution",
            "source_route": "/lens/host/persistent-supervision/enablement/execution/apply",
            "approval_id": "test-execution-approval",
            "actor": "test.system.write",
            "reason": "test applied persistent supervision enablement receipt",
            "created_ts": created_ts,
            "service_config": {
                "path": str(service_config_path.resolve()),
                "updated": True,
                "changed_fields": ["persistent_supervision_enabled"],
                "before": {"persistent_supervision_enabled": False},
                "after": {"persistent_supervision_enabled": True},
            },
            "result": {
                "applied": True,
                "executed": True,
                "service_config_updated": True,
                "persistent_supervision_enablement_allowed": True,
                "persistent_supervision_ready": True,
                "resident_claim_allowed": False,
            },
            "post_plan": {
                "status": "blocked",
                "next_smallest_truthful_gap": "persistent_supervision_execution_boundary",
                "blocked_requirements": [],
                "blockers": [],
            },
            "governance": {
                "gate": "lens_host_persistent_supervision_enablement_execution_receipt",
                "persistent_supervision_boundary": True,
                "execution_authority": False,
                "approval_decision_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
            },
        },
    )

    proc = run_powershell_script(
        _powershell(),
        _repo_root() / "scripts" / "lens-persistent-supervision-current-gap-proof.ps1",
        [
            "-Mode",
            "Status",
            "-DataDir",
            str(data_root),
            "-ChildProofTimeoutSeconds",
            "180",
        ],
        cwd=_repo_root(),
        timeout_seconds=240,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.persistent_supervision_current_gap.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage6_applied_enablement_handoff_observed"] is True
    assert payload["persistent_supervision_resident_claim_boundary_handoff_observed"] is True
    assert payload["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert payload["recommended_handoff_source"] == "persistent_supervision_resident_claim_boundary_handoff"
    assert (
        payload["recommended_next_slice"] == "run_stage6_lens_completion_audit_after_resident_claim_boundary_readback"
    )
    assert payload["recommended_proof_script"] == "scripts/lens-stage6-completion-audit.ps1 -Mode Status"
    assert payload["recommended_route"] == "/lens/host/persistent-supervision/enablement/execution"
    assert payload["recommended_readiness_route"] == "/lens/host/persistent-supervision/enablement/execution/readiness"
    assert payload["authority_required"] == "none_new_stage6_completion_audit"
    assert payload["authority_granted"] is False

    handoff = payload["handoff"]
    assert handoff["status"] == "persistent_supervision_resident_claim_boundary_consumed"
    assert handoff["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert handoff["next_step"] == "run_stage6_lens_completion_audit_after_resident_claim_boundary_readback"
    assert handoff["proof_script"] == "scripts/lens-stage6-completion-audit.ps1 -Mode Status"
    assert handoff["authority_required"] == "none_new_stage6_completion_audit"
    assert handoff["authority_granted"] is False
    assert handoff["read_only_contract"] is True
    assert handoff["diagnostic_only"] is True
    assert handoff["would_execute"] is False
    assert handoff["would_mutate"] is False
    assert handoff["applied_enablement_receipt_handoff"]["latest_receipt_id"] == "lpsee_test_applied"
    assert handoff["resident_claim_boundary_handoff"]["status"] == "audit_needed"

    authority_chain = payload["authority_chain"]
    assert authority_chain["resident_claim_boundary_consumed"] is True
    assert authority_chain["resident_claim_boundary_handoff_consumed_after_applied_receipt"] is True
    assert authority_chain["next_audit_gap_after_authority_chain"] == "stage6_lens_completion_audit"
    assert payload["stage6_completion_audit_required"] is True
    assert payload["stage6_completion_audit_not_run"] is True

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["resident_claim_boundary_handoff"]["status"] == "stage6_completion_audit_handoff_ready"
    assert checks["current_gap"]["status"] == "stage6_lens_completion_audit"
    assert checks["product_side_effects_denied"]["status"] == "product_read_only"
    assert all(item["passed"] for item in payload["checks"])
