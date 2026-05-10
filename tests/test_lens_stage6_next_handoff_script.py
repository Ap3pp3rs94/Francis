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


def _run_proof(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-stage6-next-handoff.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=60,
        env=run_env,
    )


def test_lens_stage6_next_handoff_distills_closure_readback_without_authority(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    proc = _run_proof("-Mode", "Status", env={"FRANCIS_DATA_DIR": str(data_root)})

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.stage6.next_handoff.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["mode"] == "status"
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["ready_to_close"] is False
    assert payload["stage_next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert payload["acceptance_criterion"] == "summon_anywhere"
    assert payload["acceptance_criterion_status"] == "blocked"
    assert payload["criterion_next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert payload["first_blocker_family"] == "resident_host"
    assert payload["first_blocker_family_next_smallest_truthful_gap"] == "resident_host_runtime_blocker_boundary"
    assert payload["next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert payload["recommended_next_slice"] == (
        "resolve_resident_host_process_before_persistent_supervision_enablement"
    )
    assert payload["recommended_handoff_source"] == "persistent_supervision_first_missing_requirement_handoff"
    assert payload["recommended_proof_script"] == ("scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status")
    assert payload["recommended_route"] == "/lens/host"
    assert payload["recommended_readiness_route"] == "/lens/host/runtime-loop/readiness"
    assert payload["authority_required"] == "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites"
    assert payload["blocked_criteria"] == [
        "summon_anywhere",
        "helpful_not_noisy",
        "system_resident_presence",
    ]
    assert payload["ready_criteria"] == ["mode_visibility", "pilot_visibility_groundwork"]

    first_handoff = payload["first_blocker_family_handoff"]
    assert first_handoff["id"] == "resident_host"
    assert first_handoff["status"] == "blocked"
    assert first_handoff["read_only_contract"] is True
    assert first_handoff["diagnostic_only"] is True
    assert first_handoff["would_execute"] is False
    assert first_handoff["would_mutate"] is False

    process_handoff = payload["first_blocker_family_completion_audit_handoff"]
    assert process_handoff["authority_required"] == "process_supervision_authority"
    assert process_handoff["read_only_contract"] is True
    assert process_handoff["diagnostic_only"] is True
    assert process_handoff["would_execute"] is False
    assert process_handoff["would_mutate"] is False

    family_chain_handoff = payload["summon_anywhere_family_chain_completion_audit_handoff"]
    assert family_chain_handoff["authority_required"] == "resident_runtime_execution_authority"
    assert family_chain_handoff["blocked_families"] == [
        "resident_host",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
        "authority",
    ]
    assert family_chain_handoff["read_only_contract"] is True
    assert family_chain_handoff["diagnostic_only"] is True
    assert family_chain_handoff["would_execute"] is False
    assert family_chain_handoff["would_mutate"] is False

    assert payload["persistent_supervision_required_prerequisites_observed"] is True
    assert payload["persistent_supervision_missing_required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert payload["persistent_supervision_first_missing_required_before_enable"] == "resident_host_process"
    first_missing_handoff = payload["persistent_supervision_first_missing_requirement_handoff"]
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
    assert first_missing_handoff["authority_route"] == "/lens/host/activation/authority"
    assert first_missing_handoff["authority_request_route"] == "/lens/host/activation/request"
    assert first_missing_handoff["authority_readback_route"] == "/lens/host/activation"
    assert first_missing_handoff["authority_preflight_route"] == "/lens/host/activation/preflight"
    assert first_missing_handoff["authority_plan_route"] == "/lens/host/activation/plan"
    assert first_missing_handoff["authority_execute_route"] == "/lens/host/activation/execute"
    assert first_missing_handoff["authority_executions_route"] == "/lens/host/activation/executions"
    assert first_missing_handoff["authority_grants_route"] == "/lens/host/activation/authority/grants"
    assert first_missing_handoff["execution_denials_route"] == "/lens/host/activation/denials"
    assert first_missing_handoff["approval_action"] == "lens.host.foreground_activation"
    assert first_missing_handoff["authority_scope"] == "system.write"
    assert first_missing_handoff["read_only_contract"] is True
    assert first_missing_handoff["diagnostic_only"] is True
    assert first_missing_handoff["would_execute"] is False
    assert first_missing_handoff["would_mutate"] is False
    persistent_prerequisites_handoff = payload["persistent_supervision_required_prerequisites_handoff"]
    assert (
        persistent_prerequisites_handoff["next_step"]
        == "resolve_persistent_supervision_required_prerequisites_before_enablement"
    )
    assert (
        persistent_prerequisites_handoff["next_smallest_truthful_gap"]
        == "persistent_supervision_required_prerequisites_missing"
    )
    assert persistent_prerequisites_handoff["first_missing_required_before_enable"] == "resident_host_process"
    assert persistent_prerequisites_handoff["first_missing_requirement_handoff"] == first_missing_handoff
    assert persistent_prerequisites_handoff["proof_script"] == (
        "scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status"
    )
    assert persistent_prerequisites_handoff["route"] == "/lens/host/persistent-supervision"
    assert persistent_prerequisites_handoff["readiness_route"] == "/lens/host/persistent-supervision/enablement"
    assert persistent_prerequisites_handoff["authority_required"] == (
        "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites"
    )
    assert persistent_prerequisites_handoff["authority_granted"] is False
    assert persistent_prerequisites_handoff["read_only_contract"] is True
    assert persistent_prerequisites_handoff["diagnostic_only"] is True
    assert persistent_prerequisites_handoff["would_execute"] is False
    assert persistent_prerequisites_handoff["would_mutate"] is False
    assert payload["resident_runtime_candidate_handoff_observed"] is False
    assert payload["resident_runtime_candidate_handoff"] == {}

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["closure_readback"]["status"] == "blocked_closure_readback_observed"
    assert checks["stage_boundary"]["status"] == "stage6_active"
    assert checks["first_blocked_criterion"]["status"] == "summon_anywhere_blocked"
    assert checks["first_blocker_family_handoff"]["status"] == "resident_host_handoff_ready"
    assert checks["completion_audit_handoff"]["status"] == "process_supervision_audit_handoff_ready"
    assert checks["family_chain_handoff"]["status"] == "summon_family_chain_handoff_ready"
    assert checks["persistent_supervision_required_prerequisites"]["status"] == "required_prerequisites_handoff_ready"
    assert (
        checks["persistent_supervision_first_missing_requirement"]["status"]
        == "first_missing_requirement_handoff_ready"
    )
    assert checks["resident_runtime_candidate_handoff"]["status"] == "not_observed"
    assert checks["side_effects_denied"]["status"] == "readback_only"
    assert all(item["passed"] for item in payload["checks"])

    assert payload["governance"] == {
        "diagnostic_only": True,
        "read_only_contract": True,
        "uses_lens_status_readback": True,
        "uses_persistent_supervision_readback": True,
        "proof_script": "scripts/lens-stage6-next-handoff.ps1 -Mode Status",
        "would_execute": False,
        "would_mutate": False,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "approval_request_write": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "hotkey_registration_authority": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "memory_write": False,
        "receipt_write_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
    }


def test_lens_stage6_next_handoff_consumes_unsupervised_process_readback(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    runtime_root = data_root / "runtime" / "lens-host"
    runtime_root.mkdir(parents=True, exist_ok=True)
    pid = os.getpid()
    (runtime_root / "lens-host.pid").write_text(str(pid), encoding="ascii")
    (runtime_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.runtime_state",
                "status": "foreground_running",
                "mode": "foreground",
                "pid": pid,
                "process_alive": True,
                "resident": False,
                "service_managed": False,
                "tray_presence": False,
                "global_hotkey": False,
                "overlay_window": False,
                "summon_anywhere": False,
                "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "governance": {
                    "memory_write": False,
                    "service_control_authority": False,
                    "local_process_launch_authority": False,
                },
            }
        ),
        encoding="utf-8",
    )

    proc = _run_proof("-Mode", "Status", env={"FRANCIS_DATA_DIR": str(data_root)})

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert payload["recommended_next_slice"] == (
        "consume_resident_host_process_supervision_handoff_before_stage6_closure"
    )
    assert payload["recommended_handoff_source"] == "persistent_supervision_first_missing_requirement_handoff"
    assert payload["recommended_proof_script"] == (
        "scripts/lens-resident-host-process-supervision-blocker-proof.ps1 -Mode Status"
    )
    handoff = payload["persistent_supervision_first_missing_requirement_handoff"]
    assert handoff["blocker"] == "resident_host_process_not_supervised"
    assert handoff["requirement_state"] == "foreground_observed_not_supervised"
    assert handoff["proof_script"] == ("scripts/lens-resident-host-process-supervision-blocker-proof.ps1 -Mode Status")
    assert handoff["next_step"] == "consume_resident_host_process_supervision_handoff_before_stage6_closure"
    assert handoff["read_only_contract"] is True
    assert handoff["diagnostic_only"] is True
    assert handoff["would_execute"] is False
    assert handoff["would_mutate"] is False
    assert payload["governance"]["process_supervision_authority"] is False
    assert payload["governance"]["local_process_launch_authority"] is False


def test_lens_stage6_next_handoff_consumes_activation_execution_handoff(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    receipt_root = data_root / "lens" / "host_activation_executions"
    receipt_root.mkdir(parents=True, exist_ok=True)
    receipt_id = "activation-execution-observed"
    (receipt_root / f"{receipt_id}.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.activation.execution.receipt",
                "receipt_id": receipt_id,
                "approval_id": "approval-1",
                "actor": "test.system.write",
                "route": "/lens/host/activation/execute",
                "status": "bounded_foreground_launch_observed",
                "created_ts": datetime.now(UTC).timestamp(),
                "execution": {
                    "bounded_process_launch": True,
                    "observed_process": True,
                },
                "resident_claim": {
                    "resident_host_process_claimed": False,
                },
                "governance": {
                    "execution_authority": True,
                    "local_process_launch_authority": True,
                    "resident_claim_authority": False,
                    "memory_write": False,
                },
            }
        ),
        encoding="utf-8",
    )

    proc = _run_proof("-Mode", "Status", env={"FRANCIS_DATA_DIR": str(data_root)})

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_passed"
    assert payload["next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert payload["recommended_next_slice"] == (
        "consume_resident_host_process_supervision_handoff_before_stage6_closure"
    )
    assert payload["recommended_handoff_source"] == "activation_execution_handoff"
    assert payload["recommended_proof_script"] == (
        "scripts/lens-resident-host-process-supervision-blocker-proof.ps1 -Mode Status"
    )
    assert payload["authority_required"] == "process_supervision_authority"
    assert payload["latest_activation_execution_handoff_observed"] is True
    handoff = payload["latest_activation_execution_handoff"]
    assert handoff["id"] == "resident_host_process"
    assert handoff["receipt_id"] == receipt_id
    assert handoff["activation_execution_evidence_only"] is True
    assert handoff["does_not_satisfy_resident_host_process"] is True
    assert handoff["next_step"] == "consume_resident_host_process_supervision_handoff_before_stage6_closure"
    assert handoff["read_only_contract"] is True
    assert handoff["diagnostic_only"] is True
    assert handoff["would_execute"] is False
    assert handoff["would_mutate"] is False
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["activation_execution_handoff"]["status"] == "activation_execution_handoff_ready"
    assert all(item["passed"] for item in payload["checks"])
    assert payload["governance"]["process_supervision_authority"] is False
    assert payload["governance"]["local_process_launch_authority"] is False
    assert payload["governance"]["resident_claim_authority"] is False


def test_lens_stage6_next_handoff_consumes_fresh_resident_candidate_readback(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    state_path = data_root / "runtime" / "lens-host-supervisor" / "status.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "kind": "lens.host.supervisor_state",
                "status": "supervised_session_completed",
                "mode": "supervise_resident_once",
                "host_mode": "resident",
                "observed_pid": 1234,
                "observed_state": "running",
                "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            }
        ),
        encoding="utf-8",
    )

    proc = _run_proof("-Mode", "Status", env={"FRANCIS_DATA_DIR": str(data_root)})

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["next_smallest_truthful_gap"] == "resident_supervision_not_persistent"
    assert payload["recommended_next_slice"] == (
        "resolve_resident_supervision_persistence_before_persistent_supervision_enablement"
    )
    assert payload["recommended_handoff_source"] == "resident_runtime_candidate_handoff"
    assert (
        payload["recommended_proof_script"]
        == "scripts/lens-resident-supervision-persistence-boundary-proof.ps1 -Mode Status"
    )
    assert payload["recommended_route"] == "/lens/host"
    assert payload["recommended_readiness_route"] == "/lens/host/runtime-loop/readiness"
    assert payload["authority_required"] == "persistent_process_supervision_authority"
    assert payload["resident_runtime_candidate_handoff_observed"] is True

    handoff = payload["resident_runtime_candidate_handoff"]
    assert handoff["status"] == "observed_not_persistent"
    assert handoff["proof_script"] == "scripts/lens-resident-supervision-persistence-boundary-proof.ps1 -Mode Status"
    assert handoff["previous_next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert handoff["next_smallest_truthful_gap"] == "resident_supervision_not_persistent"
    assert handoff["previous_diagnostic_proof_observed"] is True
    assert handoff["read_only_contract"] is True
    assert handoff["diagnostic_only"] is True
    assert handoff["would_execute"] is False
    assert handoff["would_mutate"] is False

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["resident_runtime_candidate_handoff"]["status"] == "fresh_candidate_handoff_ready"
    assert all(item["passed"] for item in payload["checks"])
    assert payload["governance"]["local_process_launch_authority"] is False
    assert payload["governance"]["process_supervision_authority"] is False
    assert payload["governance"]["resident_claim_authority"] is False
