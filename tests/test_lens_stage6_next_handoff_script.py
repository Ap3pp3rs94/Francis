from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _script_text() -> str:
    return (_repo_root() / "scripts" / "lens-stage6-next-handoff.ps1").read_text(encoding="utf-8")


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


def _run_bringup(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
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
            str(_repo_root() / "scripts" / "lens-stage6-prerequisite-bringup-plan.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=60,
        env=run_env,
    )


def test_lens_stage6_next_handoff_uses_explicit_completion_audit_readback() -> None:
    script = _script_text()

    assert "[string]$CompletionAuditJsonPath" in script
    assert "Get-Content -LiteralPath $ResolvedCompletionAuditJsonPath -Raw | ConvertFrom-Json" in script
    assert "$Stage6CompletionAuditHelpfulNotNoisyResidentSurfaceRuntimeHandoffObserved = (" in script
    assert "'stage6_helpful_not_noisy_resident_surface_runtime_handoff'" in script
    assert "$Stage6CompletionAuditResidentRuntimeTrayPresenceHandoffObserved = (" in script
    assert "'api_resident_runtime_execution_tray_presence_handoff'" in script
    assert "'summon_tray_presence_blocker_boundary'" in script
    assert "'prove_governed_tray_presence_api_execution_after_resident_supervision'" in script
    assert "'scripts/lens-tray-presence-api-execution-proof.ps1 -Mode Status'" in script
    assert "stage6_completion_audit_resident_runtime_tray_presence_handoff_observed" in script
    assert "$Stage6CompletionAuditPersistentSupervisionApiExecutionHandoffObserved = (" in script
    assert "'stage6_persistent_supervision_api_execution_readback_required'" in script
    assert "'run_persistent_supervision_api_execution_proof_after_bounded_summon'" in script
    assert "'scripts/lens-persistent-supervision-api-execution-proof.ps1 -Mode Status'" in script
    assert "stage6_completion_audit_persistent_supervision_api_execution_handoff_observed" in script
    assert "$Stage6CompletionAuditPersistentSupervisionResidentClaimBoundaryHandoffObserved = (" in script
    assert "'persistent_supervision_execution_authority_handoff'" in script
    assert "'stage6_persistent_supervision_api_execution_resident_claim_boundary'" in script
    assert "'review_persistent_supervision_resident_claim_boundary_without_runtime_start'" in script
    assert "'resolve_resident_claim_authority_before_persistent_supervision_resident_claim'" in script
    assert "stage6_completion_audit_persistent_supervision_resident_claim_boundary_handoff_observed" in script
    assert "$Stage6CompletionAuditPersistentSupervisionFirstMissingRequirementHandoffObserved = (" in script
    assert "'persistent_supervision_prerequisites_first_missing_requirement_handoff'" in script
    assert "'resolve_resident_host_process_before_persistent_supervision_enablement'" in script
    assert "'resolve_tray_presence_before_persistent_supervision_enablement'" in script
    assert "'scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status'" in script
    assert "$Stage6CompletionAuditPersistentSupervisionFirstMissingRequirementTrayPresenceObserved = (" in script
    assert "stage6_completion_audit_persistent_supervision_first_missing_requirement_handoff_observed" in script
    assert "$Stage6CompletionAuditPrerequisiteBringupOperatorPlanHandoffObserved = (" in script
    assert "'stage6_prerequisite_bringup_operator_plan'" in script
    assert "'stage6_closure_readback_summon_resident_host_blocker'" in script
    assert "$Stage6CompletionAuditPrerequisiteBringupOperatorPlanSourceObserved = (" in script
    assert "$Stage6CompletionAuditPrerequisiteBringupOperatorPlanEffectiveFirstMissingRequirement" in script
    assert "'grant_resident_runtime_execution_authority'" in script
    assert "'execute_supervised_resident_host_start'" in script
    assert "$Stage6CompletionAuditPrerequisiteBringupOperatorPlanNextSliceObserved = (" in script
    assert "$Stage6CompletionAuditPrerequisiteBringupOperatorPlanSurfaceGrantActionObserved = (" in script
    assert "$Stage6CompletionAuditPrerequisiteBringupOperatorPlanAuthorityObserved = (" in script
    assert "run_stage6_prerequisite_bringup_$Stage6CompletionAuditPrerequisiteBringupOperatorPlanActionId" in script
    assert "stage6_completion_audit_prerequisite_bringup_operator_plan_handoff_observed" in script
    assert "$Stage6CompletionAuditPrerequisiteBringupEnablementReceiptHandoffObserved = (" in script
    assert "'stage6_prerequisite_bringup_enablement_receipt_review'" in script
    assert "'run_stage6_prerequisite_bringup_review_persistent_supervision_enablement_receipt'" in script
    assert "stage6_completion_audit_enablement_receipt_review_handoff_observed" in script
    assert "New-Stage6CompletionAuditReadbackOperatorHandoff" in script
    assert "$Stage6CompletionAuditRuntimeReadbackRequired = (" in script
    assert "'stage6_completion_audit_launch_on_hotkey_readback_required'" in script
    assert "'scripts/lens-stage6-completion-audit.ps1 -Mode Status -AllowLaunchOnHotkey'" in script
    assert "Invoke-JsonScriptReadback `\n    -ScriptPath $Stage6CompletionAuditScript" not in script


def _write_lens_host_runtime_state(data_root: Path, *, pid: int) -> None:
    runtime_root = data_root / "runtime" / "lens-host"
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "lens-host.pid").write_text(str(pid), encoding="ascii")
    (runtime_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.runtime_state",
                "status": "resident_running",
                "mode": "resident",
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


def _write_lens_host_supervisor_state(
    data_root: Path,
    *,
    pid: int,
    updated_at: str | None = None,
) -> None:
    runtime_root = data_root / "runtime" / "lens-host-supervisor"
    runtime_root.mkdir(parents=True, exist_ok=True)
    observed_at = updated_at or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    (runtime_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.supervisor_state",
                "status": "resident_supervising",
                "mode": "resident_start",
                "host_mode": "resident",
                "supervisor_pid": pid,
                "observed_pid": pid,
                "observed_state": "resident_running",
                "restarted_process": False,
                "managed_service": False,
                "resident_supervised_runtime": True,
                "resident_claim_allowed": False,
                "process_supervision_authority": True,
                "process_restart_authority": False,
                "service_control_authority": False,
                "updated_at": observed_at,
                "governance": {
                    "memory_write": False,
                    "service_control_authority": False,
                    "local_process_launch_authority": False,
                },
            }
        ),
        encoding="utf-8",
    )


def _write_lens_host_supervised_runtime_receipt(data_root: Path) -> None:
    receipt_root = data_root / "lens" / "host_supervision_executions"
    receipt_root.mkdir(parents=True, exist_ok=True)
    receipt_id = "lhse_test_supervised_runtime"
    (receipt_root / f"{receipt_id}.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.supervision.execution.receipt",
                "receipt_id": receipt_id,
                "status": "resident_supervision_started",
                "created_ts": int(datetime.now(UTC).timestamp()),
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
            }
        ),
        encoding="utf-8",
    )


def _assert_actor_scope_policy_contract(
    readiness: dict[str, Any],
    *,
    scope_required: bool,
) -> None:
    contract = readiness["actor_scope_policy_contract"]
    assert contract["env_var"] == "FRANCIS_API_ACTOR_SCOPES"
    assert contract["json_shape"] == {"<actor>": ["system.write"]}
    assert contract["required_scope"] == ("system.write" if scope_required else "")
    assert contract["actor_placeholder"] == "<actor>"
    assert contract["scope_required"] is scope_required
    assert contract["powershell_example"] == ('$env:FRANCIS_API_ACTOR_SCOPES = \'{"<actor>":["system.write"]}\'')


def _expected_approval_request_powershell(route: str) -> str:
    return (
        "$body = @{ actor = '<actor>'; reason = '<reason>' } | ConvertTo-Json -Compress; "
        + "Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000"
        + route
        + "' -ContentType 'application/json' -Body $body"
    )


def _assert_approval_request_contract(
    action: dict[str, Any],
    *,
    action_id: str,
    route: str,
    approval_action: str,
) -> None:
    assert action["approval_request_contract"] == {
        "route": route,
        "method": "POST",
        "action_id": action_id,
        "approval_action": approval_action,
        "payload_shape": {
            "actor": "<actor>",
            "reason": "<reason>",
        },
        "required_scope": "system.write",
        "actor_scope_policy_contract": {
            "env_var": "FRANCIS_API_ACTOR_SCOPES",
            "json_shape": {"<actor>": ["system.write"]},
            "required_scope": "system.write",
            "actor_placeholder": "<actor>",
            "scope_required": True,
            "powershell_example": '$env:FRANCIS_API_ACTOR_SCOPES = \'{"<actor>":["system.write"]}\'',
        },
        "creates": "approval_request",
        "would_request_approval": False,
        "would_grant_authority": False,
        "would_execute": False,
        "would_mutate_runtime": False,
    }


def _assert_approval_request_command(
    command: dict[str, Any],
    *,
    route: str,
) -> None:
    assert command == {
        "command": _expected_approval_request_powershell(route),
        "route": route,
        "method": "POST",
        "api_base_url": "http://127.0.0.1:8000",
        "payload_shape": {
            "actor": "<actor>",
            "reason": "<reason>",
        },
        "required_scope": "system.write",
        "requires_running_api": True,
        "requires_operator_actor": True,
        "would_request_approval_if_run": True,
        "status_readback_would_request_approval": False,
    }


def _assert_approval_decision_contract(
    action: dict[str, Any],
    *,
    approval_id: str,
) -> None:
    contract = action["approval_decision_contract"]
    assert contract["route"] == "/approvals/decision"
    assert contract["method"] == "POST"
    assert contract["payload_shape"] == {
        "id": approval_id,
        "action": "approve",
        "comment": "<comment>",
        "actor": "<actor>",
    }
    assert contract["allowed_actions"] == ["approve", "reject", "emergency"]
    assert contract["required_scope"] == "approvals.decide"
    assert contract["actor_scope_policy_contract"] == {
        "env_var": "FRANCIS_API_ACTOR_SCOPES",
        "json_shape": {"<actor>": ["approvals.decide"]},
        "required_scope": "approvals.decide",
        "actor_placeholder": "<actor>",
        "scope_required": True,
        "powershell_example": '$env:FRANCIS_API_ACTOR_SCOPES = \'{"<actor>":["approvals.decide"]}\'',
    }
    assert contract["local_caller_required_unless_remote_enabled"] is True
    assert contract["remote_enable_env_var"] == "FRANCIS_APPROVALS_ALLOW_REMOTE_DECISIONS"
    assert contract["would_decide_approval"] is False


def _expected_approval_decision_powershell(approval_id: str) -> str:
    return (
        "$body = @{ id = '"
        + approval_id
        + "'; action = 'approve'; comment = '<comment>'; actor = '<actor>' } | ConvertTo-Json -Compress; "
        + "Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/approvals/decision' "
        + "-ContentType 'application/json' -Body $body"
    )


def _assert_approval_decision_command(
    command: dict[str, Any],
    *,
    approval_id: str,
) -> None:
    assert command == {
        "command": _expected_approval_decision_powershell(approval_id),
        "route": "/approvals/decision",
        "method": "POST",
        "api_base_url": "http://127.0.0.1:8000",
        "payload_shape": {
            "id": approval_id,
            "action": "approve",
            "comment": "<comment>",
            "actor": "<actor>",
        },
        "required_scope": "approvals.decide",
        "requires_running_api": True,
        "requires_local_caller_unless_remote_enabled": True,
        "remote_enable_env_var": "FRANCIS_APPROVALS_ALLOW_REMOTE_DECISIONS",
        "requires_operator_actor": True,
        "would_decide_approval_if_run": True,
        "status_readback_would_decide_approval": False,
    }


def _assert_stage6_prerequisite_bringup_operator_handoff(
    payload: dict[str, Any],
    *,
    first_missing_truthful_gap: str = "resident_host_process_not_supervised",
) -> None:
    assert payload["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    assert payload["recommended_next_slice"] == "run_stage6_prerequisite_bringup_request_next_for_resident_host_process"
    assert payload["recommended_handoff_source"] == "stage6_prerequisite_bringup_operator_plan"
    assert payload["recommended_proof_script"] == "scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status"
    assert payload["recommended_route"] == "/lens/host/persistent-supervision"
    assert payload["recommended_readiness_route"] == "/lens/host/persistent-supervision/enablement"
    assert payload["authority_required"] == "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites"
    assert payload["authority_granted"] is False
    assert payload["stage6_prerequisite_bringup_plan_observed"] is True
    assert payload["next_operator_action_requirement"] == "resident_host_process"
    assert payload["next_operator_action"]["id"] == "request_resident_runtime_execution_authority"
    assert payload["next_operator_action"]["route"] == "/lens/resident-runtime/authority-grant/request"
    _assert_approval_request_contract(
        payload["next_operator_action"],
        action_id="request_resident_runtime_execution_authority",
        route="/lens/resident-runtime/authority-grant/request",
        approval_action="lens.resident_runtime.execution_authority",
    )
    _assert_approval_request_command(
        payload["next_operator_action"]["approval_request_command"],
        route="/lens/resident-runtime/authority-grant/request",
    )
    assert payload["next_operator_actor_scope_readiness"]["ready"] is False
    assert payload["next_operator_actor_scope_readiness"]["reason"] == "actor_not_supplied"
    assert payload["next_operator_actor_scope_readiness"]["actor_present"] is False
    assert payload["next_operator_actor_scope_readiness"]["scope_required"] is True
    assert payload["next_operator_actor_scope_readiness"]["action_id"] == (
        "request_resident_runtime_execution_authority"
    )
    assert payload["next_operator_actor_scope_readiness"]["operator_must_supply_actor"] is True
    _assert_actor_scope_policy_contract(payload["next_operator_actor_scope_readiness"], scope_required=True)
    assert payload["next_operator_command"] == {
        "command": (
            ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode RequestNext -Actor <actor> -ConfirmRequest"
        ),
        "mode": "RequestNext",
        "requires_confirmation": True,
        "requires_approval_id": False,
        "requires_operator_approval_decision": False,
        "approval_request_command": payload["next_operator_action"]["approval_request_command"],
    }
    assert payload["operator_sequence_command_availability"]["truthful"] is True

    handoff = payload["stage6_prerequisite_bringup_operator_plan_handoff"]
    assert handoff["status"] == "blocked"
    assert handoff["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    assert handoff["next_step"] == "run_stage6_prerequisite_bringup_request_next_for_resident_host_process"
    assert handoff["proof_script"] == "scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status"
    assert handoff["operator_plan_script"] == "scripts/lens-stage6-prerequisite-bringup-plan.ps1"
    assert handoff["current_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    assert handoff["current_truthful_gap_basis"] == "missing_required_before_enable"
    assert handoff["current_first_missing_requirement"] == "resident_host_process"
    assert handoff["current_first_missing_truthful_gap"] == first_missing_truthful_gap
    assert handoff["next_operator_action_requirement"] == "resident_host_process"
    assert handoff["next_operator_action"]["id"] == "request_resident_runtime_execution_authority"
    _assert_approval_request_contract(
        handoff["next_operator_action"],
        action_id="request_resident_runtime_execution_authority",
        route="/lens/resident-runtime/authority-grant/request",
        approval_action="lens.resident_runtime.execution_authority",
    )
    _assert_approval_request_command(
        handoff["next_operator_action"]["approval_request_command"],
        route="/lens/resident-runtime/authority-grant/request",
    )
    assert handoff["next_operator_command"]["mode"] == "RequestNext"
    assert handoff["next_operator_actor_scope_readiness"]["ready"] is False
    assert handoff["next_operator_actor_scope_readiness"]["reason"] == "actor_not_supplied"
    assert handoff["next_operator_actor_scope_readiness"]["scope_required"] is True
    assert handoff["next_operator_actor_scope_readiness"]["action_id"] == (
        "request_resident_runtime_execution_authority"
    )
    _assert_actor_scope_policy_contract(handoff["next_operator_actor_scope_readiness"], scope_required=True)
    assert handoff["operator_sequence_command_availability"]["truthful"] is True
    assert handoff["required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert handoff["missing_required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert handoff["required_before_enable_ready"] is False
    assert handoff["authority_required"] == "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites"
    assert handoff["authority_granted"] is False
    assert handoff["read_only_contract"] is True
    assert handoff["diagnostic_only"] is True
    assert handoff["plan_only"] is True
    assert handoff["requires_explicit_operator_execution"] is True
    assert handoff["would_execute"] is False
    assert handoff["would_mutate"] is False
    assert "persistent_supervision_required_prerequisites_missing" in handoff["blockers"]
    assert first_missing_truthful_gap in handoff["blockers"]

    bringup_plan = payload["stage6_prerequisite_bringup_plan"]
    assert bringup_plan["status"] == "blocked"
    assert bringup_plan["ok"] is True
    assert bringup_plan["current_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    assert bringup_plan["current_truthful_gap_basis"] == "missing_required_before_enable"
    assert bringup_plan["current_first_missing_requirement"] == "resident_host_process"
    assert bringup_plan["current_first_missing_truthful_gap"] == first_missing_truthful_gap
    assert bringup_plan["next_operator_action_requirement"] == "resident_host_process"
    assert bringup_plan["next_operator_action"]["id"] == "request_resident_runtime_execution_authority"
    assert bringup_plan["next_operator_command"]["mode"] == "RequestNext"
    assert bringup_plan["next_operator_actor_scope_readiness"]["ready"] is False
    assert bringup_plan["next_operator_actor_scope_readiness"]["reason"] == "actor_not_supplied"
    assert bringup_plan["next_operator_actor_scope_readiness"]["scope_required"] is True
    assert bringup_plan["next_operator_actor_scope_readiness"]["action_id"] == (
        "request_resident_runtime_execution_authority"
    )
    _assert_actor_scope_policy_contract(bringup_plan["next_operator_actor_scope_readiness"], scope_required=True)
    assert bringup_plan["operator_sequence_command_availability"]["truthful"] is True


def test_lens_stage6_next_handoff_names_approval_wait_after_request(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    actor_env = {"FRANCIS_API_ACTOR_SCOPES": json.dumps({"test.system.write": ["system.write"]})}
    request = _run_bringup(
        "-Mode",
        "RequestNext",
        "-DataDir",
        str(data_root),
        "-Actor",
        "test.system.write",
        "-Reason",
        "test next handoff approval wait",
        "-ConfirmRequest",
        env=actor_env,
    )

    assert request.returncode == 0, request.stderr or request.stdout
    request_payload = json.loads(request.stdout)
    assert request_payload["status"] == "approval_requested"
    assert request_payload["request_result"]["action_id"] == "request_resident_runtime_execution_authority"
    approval_id = request_payload["request_result"]["approval_id"]
    assert approval_id

    proc = _run_proof("-Mode", "Status", env={"FRANCIS_DATA_DIR": str(data_root)})

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_passed"
    assert payload["recommended_handoff_source"] == "stage6_prerequisite_bringup_operator_plan"
    assert (
        payload["recommended_next_slice"] == "run_stage6_prerequisite_bringup_approval_wait_for_resident_host_process"
    )
    assert payload["next_operator_action_requirement"] == "resident_host_process"
    assert payload["next_operator_action"]["id"] == "await_resident_runtime_execution_authority_approval"
    assert payload["next_operator_action"]["method"] == "GET"
    assert payload["next_operator_action"]["approval_decision_required"] is True
    assert payload["next_operator_action"]["pending_approval_count"] == 1
    assert payload["next_operator_action"]["pending_approval_id"] == approval_id
    assert payload["next_operator_action"]["decision_route"] == "/approvals/decision"
    assert payload["next_operator_action"]["request_status"] == "pending_review"
    _assert_approval_decision_contract(payload["next_operator_action"], approval_id=approval_id)
    _assert_approval_decision_command(
        payload["next_operator_action"]["approval_decision_command"],
        approval_id=approval_id,
    )
    assert payload["next_operator_command"] == {
        "command": ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
        "mode": "Status",
        "requires_confirmation": False,
        "requires_approval_id": False,
        "requires_operator_approval_decision": True,
        "approval_decision_command": payload["next_operator_action"]["approval_decision_command"],
    }
    assert payload["next_operator_actor_scope_readiness"]["ready"] is True
    assert payload["next_operator_actor_scope_readiness"]["reason"] == "not_required"
    assert payload["next_operator_actor_scope_readiness"]["scope_required"] is False
    assert payload["next_operator_actor_scope_readiness"]["operator_must_supply_actor"] is False
    assert payload["next_operator_actor_scope_readiness"]["action_id"] == (
        "await_resident_runtime_execution_authority_approval"
    )
    _assert_actor_scope_policy_contract(payload["next_operator_actor_scope_readiness"], scope_required=False)

    handoff = payload["stage6_prerequisite_bringup_operator_plan_handoff"]
    assert handoff["next_step"] == "run_stage6_prerequisite_bringup_approval_wait_for_resident_host_process"
    assert handoff["next_operator_action"]["id"] == "await_resident_runtime_execution_authority_approval"
    assert handoff["next_operator_action"]["pending_approval_id"] == approval_id
    assert handoff["next_operator_action"]["pending_approval_count"] == 1
    assert handoff["next_operator_action"]["decision_route"] == "/approvals/decision"
    _assert_approval_decision_contract(handoff["next_operator_action"], approval_id=approval_id)
    _assert_approval_decision_command(
        handoff["next_operator_action"]["approval_decision_command"],
        approval_id=approval_id,
    )
    assert handoff["next_operator_actor_scope_readiness"]["reason"] == "not_required"
    assert handoff["next_operator_actor_scope_readiness"]["scope_required"] is False
    _assert_actor_scope_policy_contract(handoff["next_operator_actor_scope_readiness"], scope_required=False)


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
    _assert_stage6_prerequisite_bringup_operator_handoff(payload)
    assert payload["recommended_prerequisites_handoff_source"] == (
        "persistent_supervision_required_prerequisites_handoff"
    )
    assert payload["recommended_prerequisites_next_slice"] == (
        "resolve_persistent_supervision_required_prerequisites_before_enablement"
    )
    assert payload["recommended_prerequisites_proof_script"] == (
        "scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status"
    )
    assert payload["recommended_prerequisites_route"] == "/lens/host/persistent-supervision"
    assert payload["recommended_prerequisites_readiness_route"] == "/lens/host/persistent-supervision/enablement"
    assert payload["recommended_prerequisites_authority_required"] == (
        "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites"
    )
    assert payload["recommended_prerequisites_authority_granted"] is False
    assert payload["recommended_first_missing_handoff_source"] == (
        "persistent_supervision_first_missing_requirement_handoff"
    )
    assert payload["recommended_first_missing_next_slice"] == (
        "resolve_resident_host_process_before_persistent_supervision_enablement"
    )
    assert payload["recommended_first_missing_proof_script"] == (
        "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status"
    )
    assert payload["recommended_first_missing_route"] == "/lens/host"
    assert payload["recommended_first_missing_readiness_route"] == "/lens/host/runtime-loop/readiness"
    assert payload["recommended_first_missing_authority_required"] == "process_supervision_authority"
    assert payload["recommended_first_missing_authority_granted"] is False
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
    assert process_handoff["authority_granted"] is False
    assert process_handoff["read_only_contract"] is True
    assert process_handoff["diagnostic_only"] is True
    assert process_handoff["would_execute"] is False
    assert process_handoff["would_mutate"] is False

    family_chain_handoff = payload["summon_anywhere_family_chain_completion_audit_handoff"]
    assert family_chain_handoff["authority_required"] == "resident_runtime_execution_authority"
    assert family_chain_handoff["authority_granted"] is False
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
    assert first_missing_handoff["authority_granted"] is False
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
    assert payload["persistent_supervision_enablement_authority_handoff_observed"] is True
    enablement_handoff = payload["persistent_supervision_enablement_authority_handoff"]
    assert enablement_handoff["status"] == "blocked"
    assert enablement_handoff["previous_next_smallest_truthful_gap"] == "persistent_supervision_authority_not_granted"
    assert (
        enablement_handoff["consumed_audit_next_smallest_truthful_gap"]
        == "persistent_supervision_enablement_denial_boundary"
    )
    assert enablement_handoff["next_smallest_truthful_gap"] == (
        "persistent_supervision_enablement_authority_not_granted"
    )
    assert enablement_handoff["next_step"] == (
        "prove_persistent_supervision_enablement_authority_after_candidate_handoff"
    )
    assert enablement_handoff["proof_script"] == (
        "scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status"
    )
    assert enablement_handoff["request_route"] == "/lens/host/persistent-supervision/enablement/authority/request"
    assert enablement_handoff["grant_route"] == "/lens/host/persistent-supervision/enablement/authority"
    assert enablement_handoff["grants_route"] == "/lens/host/persistent-supervision/enablement/authority/grants"
    assert enablement_handoff["readiness_route"] == ("/lens/host/persistent-supervision/enablement/authority/readiness")
    assert enablement_handoff["execution_readiness_route"] == (
        "/lens/host/persistent-supervision/enablement/execution/readiness"
    )
    assert enablement_handoff["authority_required"] == "persistent_supervision_enablement_authority"
    assert enablement_handoff["authority_granted"] is False
    assert enablement_handoff["enablement_denial_observed"] is True
    assert enablement_handoff["execution_denial_observed"] is True
    assert enablement_handoff["persistent_supervision_enablement_authority"] is False
    assert enablement_handoff["service_config_write_authority"] is False
    assert enablement_handoff["persistent_supervision_execution_authority"] is False
    assert enablement_handoff["receipt_write_authority"] is False
    assert enablement_handoff["resident_claim_authority"] is False
    assert enablement_handoff["resident_claim_allowed"] is False
    assert enablement_handoff["service_config_updated"] is False
    assert enablement_handoff["applied"] is False
    assert enablement_handoff["executed"] is False
    assert enablement_handoff["read_only_contract"] is True
    assert enablement_handoff["diagnostic_only"] is True
    assert enablement_handoff["would_execute"] is False
    assert enablement_handoff["would_mutate"] is False
    assert "persistent_supervision_enablement_authority_not_granted" in enablement_handoff["blockers"]
    assert "persistent_supervision_execution_authority_not_granted" in enablement_handoff["blockers"]
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
    assert checks["persistent_supervision_enablement_authority_handoff"]["status"] == (
        "enablement_authority_handoff_ready"
    )
    assert checks["stage6_prerequisite_bringup_plan"]["status"] == "operator_plan_readback_ready"
    assert checks["stage6_completion_audit_runtime_authority_handoff"]["status"] == "not_requested"
    assert checks["resident_runtime_candidate_handoff"]["status"] == "not_observed"
    assert checks["side_effects_denied"]["status"] == "readback_only"
    assert all(item["passed"] for item in payload["checks"])

    assert payload["governance"] == {
        "diagnostic_only": True,
        "read_only_contract": True,
        "launch_on_hotkey_runtime_readback_opt_in": False,
        "uses_lens_status_readback": True,
        "uses_persistent_supervision_readback": True,
        "uses_stage6_prerequisite_bringup_plan_readback": True,
        "uses_stage6_completion_audit_readback": False,
        "stage6_prerequisite_bringup_plan_readback": True,
        "stage6_prerequisite_bringup_actor_scope_readback": True,
        "stage6_completion_audit_runtime_authority_handoff_observed": False,
        "stage6_completion_audit_resident_surface_runtime_handoff_observed": False,
        "stage6_completion_audit_resident_runtime_tray_presence_handoff_observed": False,
        "stage6_completion_audit_persistent_supervision_api_execution_handoff_observed": False,
        "stage6_completion_audit_persistent_supervision_resident_claim_boundary_handoff_observed": False,
        "stage6_completion_audit_persistent_supervision_first_missing_requirement_handoff_observed": False,
        "stage6_completion_audit_prerequisite_bringup_operator_plan_handoff_observed": False,
        "stage6_completion_audit_enablement_receipt_review_handoff_observed": False,
        "stage6_completion_audit_recommended_handoff_consumed": False,
        "stage6_completion_audit_runtime_readback_required": False,
        "stage6_completion_audit_json_path_supplied": False,
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
    _assert_stage6_prerequisite_bringup_operator_handoff(payload)
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
    _assert_stage6_prerequisite_bringup_operator_handoff(payload)
    assert payload["latest_activation_execution_handoff_observed"] is True
    handoff = payload["latest_activation_execution_handoff"]
    assert handoff["id"] == "resident_host_process"
    assert handoff["receipt_id"] == receipt_id
    assert handoff["activation_execution_evidence_only"] is True
    assert handoff["does_not_satisfy_resident_host_process"] is True
    assert handoff["next_step"] == "consume_resident_host_process_supervision_handoff_before_stage6_closure"
    assert handoff["authority_required"] == "process_supervision_authority"
    assert handoff["authority_granted"] is False
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
    _assert_stage6_prerequisite_bringup_operator_handoff(
        payload,
        first_missing_truthful_gap="resident_supervision_not_persistent",
    )
    assert payload["resident_runtime_candidate_handoff_observed"] is True

    handoff = payload["resident_runtime_candidate_handoff"]
    assert handoff["status"] == "observed_not_persistent"
    assert handoff["proof_script"] == "scripts/lens-resident-supervision-persistence-boundary-proof.ps1 -Mode Status"
    assert handoff["previous_next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert handoff["next_smallest_truthful_gap"] == "resident_supervision_not_persistent"
    assert handoff["previous_diagnostic_proof_observed"] is True
    assert handoff["authority_required"] == "persistent_process_supervision_authority"
    assert handoff["authority_granted"] is False
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


def test_lens_stage6_next_handoff_consumes_persisted_supervision_receipt(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    receipt_root = data_root / "lens" / "host_supervision_executions"
    receipt_root.mkdir(parents=True, exist_ok=True)
    receipt_id = "lhse_test_durable_candidate"
    (receipt_root / f"{receipt_id}.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.supervision.execution.receipt",
                "receipt_id": receipt_id,
                "status": "resident_candidate_supervised_not_persistent",
                "created_ts": int(datetime.now(UTC).timestamp()),
                "execution": {
                    "bounded_supervised_session": True,
                    "temporary_host_process_observed": True,
                    "resident_runtime_candidate_supervised": True,
                    "resident_supervised_runtime": False,
                    "next_smallest_truthful_gap": "resident_supervision_not_persistent",
                },
                "resident_claim": {
                    "resident_host_process_claimed": False,
                    "resident_runtime_claimed": False,
                    "resident_claim_authority": False,
                },
            }
        ),
        encoding="utf-8",
    )

    proc = _run_proof("-Mode", "Status", env={"FRANCIS_DATA_DIR": str(data_root)})

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    _assert_stage6_prerequisite_bringup_operator_handoff(
        payload,
        first_missing_truthful_gap="resident_supervision_not_persistent",
    )
    assert payload["resident_runtime_candidate_handoff_observed"] is True

    handoff = payload["resident_runtime_candidate_handoff"]
    assert handoff["status"] == "observed_not_persistent"
    assert handoff["receipt_id"] == receipt_id
    assert handoff["source"] == (
        "/lens/status resident_host.persistent_supervision_plan.first_missing_requirement_handoff."
        "supervision_execution_receipt_observed"
    )
    assert handoff["candidate_observed_by_fresh_supervisor"] is False
    assert handoff["candidate_observed_by_supervision_execution_receipt"] is True
    assert handoff["next_smallest_truthful_gap"] == "resident_supervision_not_persistent"
    assert handoff["authority_required"] == "persistent_process_supervision_authority"
    assert handoff["authority_granted"] is False
    assert handoff["read_only_contract"] is True
    assert handoff["diagnostic_only"] is True
    assert handoff["would_execute"] is False
    assert handoff["would_mutate"] is False

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["resident_runtime_candidate_handoff"]["status"] == "receipt_candidate_handoff_ready"
    assert all(item["passed"] for item in payload["checks"])
    assert payload["governance"]["local_process_launch_authority"] is False
    assert payload["governance"]["process_supervision_authority"] is False
    assert payload["governance"]["resident_claim_authority"] is False


def test_lens_stage6_next_handoff_does_not_promote_stale_supervised_runtime_receipt_to_tray(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    pid = os.getpid()
    _write_lens_host_runtime_state(data_root, pid=pid)
    _write_lens_host_supervisor_state(data_root, pid=pid, updated_at="2026-01-01T00:00:00Z")
    _write_lens_host_supervised_runtime_receipt(data_root)

    proc = _run_proof("-Mode", "Status", env={"FRANCIS_DATA_DIR": str(data_root)})

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    _assert_stage6_prerequisite_bringup_operator_handoff(
        payload,
        first_missing_truthful_gap="resident_host_process_not_supervised",
    )
    assert payload["recommended_next_slice"] == "run_stage6_prerequisite_bringup_request_next_for_resident_host_process"
    assert payload["next_operator_action_requirement"] == "resident_host_process"
    assert payload["persistent_supervision_first_missing_required_before_enable"] == "resident_host_process"
    assert payload["persistent_supervision_missing_required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]

    first_missing_handoff = payload["persistent_supervision_first_missing_requirement_handoff"]
    assert first_missing_handoff["id"] == "resident_host_process"
    assert first_missing_handoff["blocker"] == "resident_host_process_not_supervised"
    assert first_missing_handoff["supervisor_freshness_status"] == "stale"
    assert first_missing_handoff["supervision_execution_supervised_runtime_receipt_observed"] is True


def test_lens_stage6_next_handoff_promotes_supervised_runtime_receipt_to_tray(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    pid = os.getpid()
    _write_lens_host_runtime_state(data_root, pid=pid)
    _write_lens_host_supervisor_state(data_root, pid=pid)
    _write_lens_host_supervised_runtime_receipt(data_root)

    proc = _run_proof("-Mode", "Status", env={"FRANCIS_DATA_DIR": str(data_root)})

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_passed"
    assert payload["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    assert payload["recommended_handoff_source"] == "stage6_prerequisite_bringup_operator_plan"
    assert payload["recommended_next_slice"] == "run_stage6_prerequisite_bringup_request_next_for_tray_presence"
    assert payload["recommended_proof_script"] == "scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status"
    assert payload["next_operator_action_requirement"] == "tray_presence"
    assert payload["next_operator_action"]["id"] == "request_tray_presence_authority"
    assert payload["persistent_supervision_first_missing_required_before_enable"] == "tray_presence"
    assert payload["persistent_supervision_missing_required_before_enable"] == [
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert payload["resident_runtime_candidate_handoff_observed"] is False
    assert payload["resident_runtime_candidate_handoff"] == {}

    first_missing_handoff = payload["persistent_supervision_first_missing_requirement_handoff"]
    assert first_missing_handoff["id"] == "tray_presence"
    assert first_missing_handoff["next_smallest_truthful_gap"] == "summon_tray_presence_blocker_boundary"
    assert first_missing_handoff["proof_script"] == "scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status"
    assert first_missing_handoff["read_only_contract"] is True
    assert first_missing_handoff["diagnostic_only"] is True
    assert first_missing_handoff["would_execute"] is False
    assert first_missing_handoff["would_mutate"] is False

    bringup_plan = payload["stage6_prerequisite_bringup_plan"]
    assert bringup_plan["current_first_missing_requirement"] == "tray_presence"
    assert bringup_plan["current_first_missing_truthful_gap"] == "summon_tray_presence_blocker_boundary"
    assert bringup_plan["next_operator_action_requirement"] == "tray_presence"
    assert bringup_plan["next_operator_action"]["id"] == "request_tray_presence_authority"
    assert "resident_host_process" not in bringup_plan["missing_required_before_enable"]
    assert (
        "resident_host_process_not_supervised" not in payload["persistent_supervision_missing_required_before_enable"]
    )
    assert "resident_supervision_not_persistent" not in payload["persistent_supervision_missing_required_before_enable"]

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["resident_runtime_candidate_handoff"]["status"] == "not_observed"
    assert all(item["passed"] for item in payload["checks"])
    assert payload["governance"]["local_process_launch_authority"] is False
    assert payload["governance"]["process_supervision_authority"] is False
    assert payload["governance"]["resident_claim_authority"] is False


def test_lens_stage6_next_handoff_consumes_applied_bringup_review_state(
    tmp_path: Path,
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

    summon_config = json.loads((_repo_root() / "config" / "runtime" / "lens" / "summon.json").read_text())
    overlay_config = json.loads((_repo_root() / "config" / "runtime" / "lens" / "overlay.json").read_text())
    pid = os.getpid()
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    created_ts = int(datetime.now(UTC).timestamp())

    def write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    for runtime_name, pid_name in {
        "lens-host": "lens-host.pid",
        "lens-tray": "lens-tray.pid",
        "lens-hotkey": "lens-hotkey.pid",
        "lens-overlay": "lens-overlay.pid",
    }.items():
        pid_path = data_root / "runtime" / runtime_name / pid_name
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text(str(pid), encoding="ascii")

    write_json(
        data_root / "runtime" / "lens-host" / "status.json",
        {
            "kind": "lens.host.runtime_state",
            "status": "resident_running",
            "mode": "resident",
            "pid": pid,
            "updated_at": now,
        },
    )
    _write_lens_host_supervisor_state(data_root, pid=pid, updated_at=now)
    write_json(
        data_root / "runtime" / "lens-tray" / "status.json",
        {
            "kind": "lens.tray.runtime_state",
            "status": "tray_running",
            "pid": pid,
            "tray_icon_visible": True,
            "updated_at": now,
        },
    )
    write_json(
        data_root / "runtime" / "lens-hotkey" / "status.json",
        {
            "kind": "lens.hotkey.runtime_state",
            "status": "hotkey_bound",
            "pid": pid,
            "hotkey_bound": True,
            "global_hotkey": summon_config["global_hotkey"],
            "binding_scope": summon_config["binding_scope"],
            "launch_on_hotkey": False,
            "summon_runner": "scripts/lens-summon.ps1",
            "press_count": 0,
            "updated_at": now,
        },
    )
    write_json(
        data_root / "runtime" / "lens-overlay" / "status.json",
        {
            "kind": "lens.overlay.runtime_state",
            "status": "overlay_running",
            "pid": pid,
            "overlay_window_visible": True,
            "always_on_top": True,
            "overlay_name": overlay_config["overlay_name"],
            "overlay_scope": overlay_config["overlay_scope"],
            "updated_at": now,
        },
    )
    write_json(
        data_root / "runtime" / "lens-summon" / "status.json",
        {
            "kind": "lens.summon.runtime_state",
            "status": "summon_binding_observed",
            "global_hotkey": summon_config["global_hotkey"],
            "binding_scope": summon_config["binding_scope"],
            "bounded_handoff_ready": True,
            "local_open_ready": False,
            "opened": False,
            "no_launch": True,
            "summon_anywhere": False,
            "os_level_summon": False,
            "updated_at": now,
        },
    )
    write_json(
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
    write_json(
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

    proof_env = {
        "FRANCIS_DATA_DIR": str(data_root),
        "FRANCIS_LENS_HOST_SERVICE_CONFIG_PATH": str(service_config_path),
    }
    proc = _run_proof(
        "-Mode",
        "Status",
        env=proof_env,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["recommended_handoff_source"] == "stage6_completion_audit_launch_on_hotkey_readback_required"
    assert payload["next_smallest_truthful_gap"] == "stage6_lens_completion_audit_runtime_readback"
    assert payload["recommended_next_slice"] == "run_stage6_completion_audit_with_launch_on_hotkey_runtime_readback"
    assert payload["recommended_proof_script"] == (
        "scripts/lens-stage6-completion-audit.ps1 -Mode Status -AllowLaunchOnHotkey"
    )
    assert payload["authority_required"] == "launch_on_hotkey_runtime_readback_opt_in"
    assert payload["authority_granted"] is False
    recommended_handoff = payload["recommended_handoff"]
    assert recommended_handoff["status"] == "runtime_readback_required"
    assert recommended_handoff["previous_next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert recommended_handoff["previous_closure_readback_next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert recommended_handoff["next_smallest_truthful_gap"] == "stage6_lens_completion_audit_runtime_readback"
    assert recommended_handoff["next_step"] == "run_stage6_completion_audit_with_launch_on_hotkey_runtime_readback"
    assert recommended_handoff["proof_script"] == (
        "scripts/lens-stage6-completion-audit.ps1 -Mode Status -AllowLaunchOnHotkey"
    )
    assert recommended_handoff["route"] == "/lens/status"
    assert recommended_handoff["readiness_route"] == "/lens/resident-runtime/authority-grant/readiness"
    assert recommended_handoff["acceptance_criterion"] == "helpful_not_noisy"
    assert recommended_handoff["first_blocker_family"] == "resident_host"
    assert recommended_handoff["authority_required"] == "launch_on_hotkey_runtime_readback_opt_in"
    assert recommended_handoff["authority_granted"] is False
    assert recommended_handoff["requires_explicit_operator_opt_in"] is True
    assert recommended_handoff["completion_audit_json_parameter"] == "-CompletionAuditJsonPath"
    assert recommended_handoff["read_only_contract"] is True
    assert recommended_handoff["diagnostic_only"] is True
    assert recommended_handoff["would_execute"] is False
    assert recommended_handoff["would_mutate"] is False
    assert recommended_handoff["would_launch_process"] is False
    assert recommended_handoff["would_supervise_process"] is False
    assert recommended_handoff["would_register_hotkey"] is False
    assert recommended_handoff["would_control_overlay"] is False
    assert recommended_handoff["would_summon"] is False
    assert recommended_handoff["would_decide_approval"] is False
    concrete_handoff = payload["recommended_concrete_handoff"]
    assert payload["recommended_concrete_handoff_source"] == (
        "stage6_completion_audit_launch_on_hotkey_readback_required"
    )
    assert payload["recommended_concrete_next_slice"] == (
        "run_stage6_completion_audit_with_launch_on_hotkey_runtime_readback"
    )
    assert payload["recommended_concrete_proof_script"] == (
        "scripts/lens-stage6-completion-audit.ps1 -Mode Status -AllowLaunchOnHotkey"
    )
    assert payload["recommended_concrete_next_smallest_truthful_gap"] == (
        "stage6_lens_completion_audit_runtime_readback"
    )
    assert payload["recommended_concrete_authority_required"] == "launch_on_hotkey_runtime_readback_opt_in"
    assert payload["recommended_concrete_authority_granted"] is False
    assert concrete_handoff == recommended_handoff
    assert concrete_handoff["read_only_contract"] is True
    assert concrete_handoff["diagnostic_only"] is True
    assert concrete_handoff["would_execute"] is False
    assert concrete_handoff["would_mutate"] is False
    assert payload["next_operator_action_requirement"] == "persistent_supervision_enablement_receipt"
    assert payload["next_operator_action"]["id"] == "review_persistent_supervision_enablement_receipt"
    assert payload["next_operator_action"]["method"] == "GET"
    assert payload["next_operator_command"]["mode"] == "Status"
    assert payload["recommended_operator_handoff"]["source"] == (
        "stage6_completion_audit_launch_on_hotkey_readback_required"
    )
    assert payload["recommended_next_operator_action_requirement"] == "stage6_completion_audit_runtime_readback"
    assert payload["recommended_next_operator_action"]["id"] == (
        "run_stage6_completion_audit_with_launch_on_hotkey_runtime_readback"
    )
    assert payload["recommended_next_operator_action"]["requires_explicit_operator_opt_in"] is True
    assert payload["recommended_next_operator_action"]["script_would_execute"] is False
    assert payload["recommended_next_operator_action"]["script_would_mutate"] is False
    assert payload["recommended_next_operator_command"] == {
        "command": ".\\scripts\\lens-stage6-completion-audit.ps1 -Mode Status -AllowLaunchOnHotkey",
        "mode": "Status",
        "requires_confirmation": False,
        "requires_explicit_operator_opt_in": True,
        "requires_approval_id": False,
        "requires_operator_approval_decision": False,
        "completion_audit_json_parameter": "-CompletionAuditJsonPath",
    }
    assert payload["stage6_prerequisite_bringup_plan_observed"] is True
    assert payload["stage6_prerequisite_bringup_plan"]["status"] == "persistent_supervision_enablement_applied"
    assert payload["stage6_prerequisite_bringup_plan"]["missing_required_before_enable"] == []
    assert payload["stage6_prerequisite_bringup_plan"]["required_before_enable_ready"] is True
    assert payload["stage6_prerequisite_bringup_operator_plan_handoff"]["status"] == (
        "persistent_supervision_enablement_applied"
    )
    assert (
        payload["stage6_prerequisite_bringup_operator_plan_handoff"]["next_smallest_truthful_gap"]
        == (payload["stage6_prerequisite_bringup_plan"]["current_truthful_gap"])
    )
    assert payload["stage6_prerequisite_bringup_operator_plan_handoff"]["next_step"] == (
        "review_persistent_supervision_enablement_receipt"
    )
    assert payload["persistent_supervision_enablement_receipt_review_handoff_observed"] is True
    receipt_review_handoff = payload["persistent_supervision_enablement_receipt_review_handoff"]
    assert receipt_review_handoff["status"] == "receipt_reviewed"
    assert receipt_review_handoff["latest_receipt_id"] == "lpsee_test_applied"
    assert receipt_review_handoff["previous_next_smallest_truthful_gap"] == (
        "persistent_supervision_execution_boundary"
    )
    assert receipt_review_handoff["next_smallest_truthful_gap"] == (
        "persistent_supervision_resident_claim_authority_boundary"
    )
    assert receipt_review_handoff["next_step"] == (
        "review_persistent_supervision_resident_claim_boundary_without_runtime_start"
    )
    assert receipt_review_handoff["authority_required"] == "resident_claim_authority"
    assert receipt_review_handoff["authority_granted"] is False
    assert receipt_review_handoff["read_only_contract"] is True
    assert receipt_review_handoff["diagnostic_only"] is True
    assert receipt_review_handoff["would_execute"] is False
    assert receipt_review_handoff["would_mutate"] is False
    assert payload["persistent_supervision_resident_claim_boundary_handoff_observed"] is True
    assert payload["stage6_completion_audit_handoff_consumed_by_closure_readback"] is True
    assert payload["stage6_completion_audit_runtime_readback_required"] is True
    assert payload["stage6_completion_audit_recommended_handoff_consumed"] is False
    resident_claim_handoff = payload["persistent_supervision_resident_claim_boundary_handoff"]
    assert resident_claim_handoff["recommended_handoff_source"] == (
        "persistent_supervision_resident_claim_boundary_handoff"
    )
    assert resident_claim_handoff["status"] == "audit_needed"
    assert resident_claim_handoff["previous_next_smallest_truthful_gap"] == (
        "persistent_supervision_resident_claim_authority_boundary"
    )
    assert resident_claim_handoff["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert resident_claim_handoff["next_step"] == (
        "run_stage6_lens_completion_audit_after_resident_claim_boundary_readback"
    )
    assert resident_claim_handoff["proof_script"] == "scripts/lens-stage6-completion-audit.ps1 -Mode Status"
    assert resident_claim_handoff["authority_required"] == "none_new_stage6_completion_audit"
    assert resident_claim_handoff["authority_granted"] is False
    assert resident_claim_handoff["read_only_contract"] is True
    assert resident_claim_handoff["diagnostic_only"] is True
    assert resident_claim_handoff["would_execute"] is False
    assert resident_claim_handoff["would_mutate"] is False
    assert payload["persistent_supervision_resident_claim_boundary_proof"]["status"] == "proof_passed"
    assert payload["persistent_supervision_resident_claim_boundary_proof"]["next_smallest_truthful_gap"] == (
        "stage6_lens_completion_audit"
    )
    assert payload["persistent_supervision_enablement_authority_handoff_observed"] is False

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["concrete_handoff"]["status"] == "concrete_handoff_ready"
    assert checks["persistent_supervision_required_prerequisites"]["status"] == "not_applicable_enablement_applied"
    assert checks["persistent_supervision_first_missing_requirement"]["status"] == "not_applicable_enablement_applied"
    assert checks["stage6_prerequisite_bringup_plan"]["status"] == "operator_plan_readback_ready"
    assert checks["persistent_supervision_enablement_receipt_review"]["status"] == "receipt_reviewed"
    assert checks["persistent_supervision_resident_claim_boundary_review"]["status"] == (
        "resident_claim_boundary_consumed"
    )
    assert checks["stage6_completion_audit_runtime_authority_handoff"]["status"] == "runtime_readback_required"
    assert all(item["passed"] for item in payload["checks"])

    resident_claim_audit_json = tmp_path / "stage6-completion-audit-resident-claim.json"
    resident_claim_audit_json.write_text(
        json.dumps(
            {
                "kind": "lens.stage6.completion_audit",
                "ok": True,
                "status": "blocked",
                "audit_status": "complete",
                "allow_launch_on_hotkey": True,
                "next_smallest_truthful_gap": "persistent_supervision_resident_claim_authority_boundary",
                "recommended_handoff_source": "persistent_supervision_execution_authority_handoff",
                "recommended_next_slice": "review_persistent_supervision_resident_claim_boundary_without_runtime_start",
                "recommended_proof_script": (
                    "scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status"
                ),
                "authority_required": "resident_claim_authority",
                "authority_granted": False,
                "recommended_handoff": {
                    "status": "blocked",
                    "previous_next_smallest_truthful_gap": (
                        "persistent_supervision_execution_authority_or_resident_claim_boundary"
                    ),
                    "next_smallest_truthful_gap": "persistent_supervision_resident_claim_authority_boundary",
                    "next_step": "review_persistent_supervision_resident_claim_boundary_without_runtime_start",
                    "proof_script": (
                        "scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status"
                    ),
                    "route": "/lens/host/persistent-supervision/enablement/execution",
                    "readiness_route": "/lens/host/persistent-supervision/enablement/execution/readiness",
                    "authority_required": "resident_claim_authority",
                    "authority_granted": False,
                    "resident_claim_allowed": False,
                    "read_only_contract": True,
                    "diagnostic_only": True,
                    "would_execute": False,
                    "would_mutate": False,
                    "blockers": [
                        "persistent_supervision_required_prerequisites_missing",
                        "resident_claim_authority_not_granted",
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    resident_claim_proc = _run_proof(
        "-Mode",
        "Status",
        "-CompletionAuditJsonPath",
        str(resident_claim_audit_json),
        env=proof_env,
    )

    assert resident_claim_proc.returncode == 0, resident_claim_proc.stderr or resident_claim_proc.stdout
    resident_claim_payload = json.loads(resident_claim_proc.stdout)
    assert resident_claim_payload["recommended_handoff_source"] == "persistent_supervision_execution_authority_handoff"
    assert (
        resident_claim_payload["next_smallest_truthful_gap"]
        == "persistent_supervision_resident_claim_authority_boundary"
    )
    assert resident_claim_payload["recommended_next_slice"] == (
        "review_persistent_supervision_resident_claim_boundary_without_runtime_start"
    )
    assert resident_claim_payload["recommended_proof_script"] == (
        "scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status"
    )
    assert resident_claim_payload["authority_required"] == "resident_claim_authority"
    assert resident_claim_payload["authority_granted"] is False
    assert resident_claim_payload["stage6_completion_audit_recommended_handoff_consumed"] is True
    assert resident_claim_payload["stage6_completion_audit_runtime_readback_required"] is False
    assert (
        resident_claim_payload[
            "stage6_completion_audit_persistent_supervision_resident_claim_boundary_handoff_observed"
        ]
        is True
    )
    assert resident_claim_payload["recommended_operator_handoff"]["source"] == (
        "stage6_completion_audit_recommended_handoff"
    )
    assert resident_claim_payload["recommended_next_operator_command"]["command"] == (
        ".\\scripts\\lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status"
    )

    api_resident_claim_audit_json = tmp_path / "stage6-completion-audit-api-resident-claim.json"
    api_resident_claim_audit_json.write_text(
        json.dumps(
            {
                "kind": "lens.stage6.completion_audit",
                "ok": True,
                "status": "blocked",
                "audit_status": "complete",
                "allow_launch_on_hotkey": True,
                "next_smallest_truthful_gap": "persistent_supervision_resident_claim_authority_boundary",
                "recommended_handoff_source": "stage6_persistent_supervision_api_execution_resident_claim_boundary",
                "recommended_next_slice": (
                    "resolve_resident_claim_authority_before_persistent_supervision_resident_claim"
                ),
                "recommended_proof_script": (
                    "scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status"
                ),
                "authority_required": "resident_claim_authority",
                "authority_granted": False,
                "recommended_handoff": {
                    "status": "blocked",
                    "previous_next_smallest_truthful_gap": "stage6_lens_completion_audit",
                    "consumed_persistent_supervision_api_execution_proof": True,
                    "next_smallest_truthful_gap": "persistent_supervision_resident_claim_authority_boundary",
                    "next_step": "resolve_resident_claim_authority_before_persistent_supervision_resident_claim",
                    "proof_script": (
                        "scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status"
                    ),
                    "route": "/lens/host/persistent-supervision/enablement/execution",
                    "readiness_route": "/lens/host/persistent-supervision/enablement/execution/readiness",
                    "authority_required": "resident_claim_authority",
                    "authority_granted": False,
                    "resident_claim_allowed": False,
                    "read_only_contract": True,
                    "diagnostic_only": True,
                    "would_execute": False,
                    "would_mutate": False,
                    "would_claim_resident": False,
                    "would_write_memory": False,
                    "would_decide_approval": False,
                    "blockers": ["resident_claim_authority_not_granted"],
                },
            }
        ),
        encoding="utf-8",
    )

    api_resident_claim_proc = _run_proof(
        "-Mode",
        "Status",
        "-CompletionAuditJsonPath",
        str(api_resident_claim_audit_json),
        env=proof_env,
    )

    assert api_resident_claim_proc.returncode == 0, api_resident_claim_proc.stderr or api_resident_claim_proc.stdout
    api_resident_claim_payload = json.loads(api_resident_claim_proc.stdout)
    assert api_resident_claim_payload["recommended_handoff_source"] == (
        "stage6_persistent_supervision_api_execution_resident_claim_boundary"
    )
    assert api_resident_claim_payload["next_smallest_truthful_gap"] == (
        "persistent_supervision_resident_claim_authority_boundary"
    )
    assert api_resident_claim_payload["recommended_next_slice"] == (
        "resolve_resident_claim_authority_before_persistent_supervision_resident_claim"
    )
    assert api_resident_claim_payload["recommended_proof_script"] == (
        "scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status"
    )
    assert api_resident_claim_payload["authority_required"] == "resident_claim_authority"
    assert api_resident_claim_payload["authority_granted"] is False
    assert api_resident_claim_payload["stage6_completion_audit_recommended_handoff_consumed"] is True
    assert api_resident_claim_payload["stage6_completion_audit_runtime_readback_required"] is False
    assert (
        api_resident_claim_payload[
            "stage6_completion_audit_persistent_supervision_resident_claim_boundary_handoff_observed"
        ]
        is True
    )
    assert api_resident_claim_payload["recommended_handoff"]["next_step"] == (
        "resolve_resident_claim_authority_before_persistent_supervision_resident_claim"
    )
    assert api_resident_claim_payload["recommended_next_operator_command"]["command"] == (
        ".\\scripts\\lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status"
    )

    resident_surface_audit_json = tmp_path / "stage6-completion-audit-resident-surface.json"
    resident_surface_audit_json.write_text(
        json.dumps(
            {
                "kind": "lens.stage6.completion_audit",
                "ok": True,
                "status": "blocked",
                "audit_status": "complete",
                "allow_launch_on_hotkey": True,
                "next_smallest_truthful_gap": "resident_surface_runtime_not_supervised",
                "recommended_handoff_source": "stage6_helpful_not_noisy_resident_surface_runtime_handoff",
                "recommended_next_slice": (
                    "resolve_resident_surface_runtime_supervision_before_helpful_not_noisy_claim"
                ),
                "recommended_proof_script": "scripts/lens-resident-surface-proof.ps1 -Mode Status",
                "authority_required": "process_supervision_authority",
                "authority_granted": False,
                "recommended_handoff": {
                    "id": "resident_surface_runtime_supervision",
                    "status": "blocked",
                    "previous_next_smallest_truthful_gap": "resident_surface_runtime_missing",
                    "next_smallest_truthful_gap": "resident_surface_runtime_not_supervised",
                    "next_step": "resolve_resident_surface_runtime_supervision_before_helpful_not_noisy_claim",
                    "proof_script": "scripts/lens-resident-surface-proof.ps1 -Mode Status",
                    "route": "/lens/resident-surface",
                    "activation_route": "/lens/resident-surface/activation",
                    "readiness_route": "/lens/resident-runtime/authority-grant/readiness",
                    "acceptance_criterion": "helpful_not_noisy",
                    "blocker": "resident_surface_runtime_not_supervised",
                    "requirement_state": "foreground_observed_not_supervised",
                    "authority_required": "process_supervision_authority",
                    "authority_granted": False,
                    "read_only_contract": True,
                    "diagnostic_only": True,
                    "would_execute": False,
                    "would_mutate": False,
                    "would_supervise_process": False,
                    "would_claim_resident": False,
                    "would_write_memory": False,
                    "would_decide_approval": False,
                },
            }
        ),
        encoding="utf-8",
    )

    resident_surface_proc = _run_proof(
        "-Mode",
        "Status",
        "-CompletionAuditJsonPath",
        str(resident_surface_audit_json),
        env=proof_env,
    )

    assert resident_surface_proc.returncode == 0, resident_surface_proc.stderr or resident_surface_proc.stdout
    resident_surface_payload = json.loads(resident_surface_proc.stdout)
    assert resident_surface_payload["recommended_handoff_source"] == (
        "stage6_helpful_not_noisy_resident_surface_runtime_handoff"
    )
    assert resident_surface_payload["next_smallest_truthful_gap"] == "resident_surface_runtime_not_supervised"
    assert resident_surface_payload["recommended_next_slice"] == (
        "resolve_resident_surface_runtime_supervision_before_helpful_not_noisy_claim"
    )
    assert resident_surface_payload["recommended_proof_script"] == (
        "scripts/lens-resident-surface-proof.ps1 -Mode Status"
    )
    assert resident_surface_payload["authority_required"] == "process_supervision_authority"
    assert resident_surface_payload["authority_granted"] is False
    assert resident_surface_payload["stage6_completion_audit_readback_observed"] is True
    assert resident_surface_payload["stage6_completion_audit_runtime_authority_handoff_observed"] is False
    assert resident_surface_payload["stage6_completion_audit_resident_surface_runtime_handoff_observed"] is True
    assert resident_surface_payload["stage6_completion_audit_recommended_handoff_consumed"] is True
    assert resident_surface_payload["stage6_completion_audit_runtime_readback_required"] is False
    resident_surface_handoff = resident_surface_payload["recommended_handoff"]
    assert resident_surface_handoff["id"] == "resident_surface_runtime_supervision"
    assert resident_surface_handoff["next_step"] == (
        "resolve_resident_surface_runtime_supervision_before_helpful_not_noisy_claim"
    )
    assert resident_surface_handoff["proof_script"] == "scripts/lens-resident-surface-proof.ps1 -Mode Status"
    assert resident_surface_handoff["readiness_route"] == "/lens/resident-runtime/authority-grant/readiness"
    assert resident_surface_handoff["authority_required"] == "process_supervision_authority"
    assert resident_surface_handoff["authority_granted"] is False
    assert resident_surface_handoff["read_only_contract"] is True
    assert resident_surface_handoff["diagnostic_only"] is True
    assert resident_surface_handoff["would_execute"] is False
    assert resident_surface_handoff["would_mutate"] is False
    assert resident_surface_handoff["would_supervise_process"] is False
    assert resident_surface_handoff["would_claim_resident"] is False
    assert resident_surface_payload["recommended_concrete_handoff"] == resident_surface_handoff
    assert resident_surface_payload["recommended_operator_handoff"]["source"] == (
        "stage6_completion_audit_recommended_handoff"
    )
    assert resident_surface_payload["recommended_next_operator_action_requirement"] == (
        "stage6_completion_audit_recommended_readback"
    )
    assert resident_surface_payload["recommended_next_operator_action"]["id"] == (
        "resolve_resident_surface_runtime_supervision_before_helpful_not_noisy_claim"
    )
    assert resident_surface_payload["recommended_next_operator_action"]["method"] == "LOCAL_SCRIPT"
    assert resident_surface_payload["recommended_next_operator_action"]["script_would_execute"] is False
    assert resident_surface_payload["recommended_next_operator_action"]["script_would_mutate"] is False
    assert resident_surface_payload["recommended_next_operator_command"] == {
        "command": ".\\scripts\\lens-resident-surface-proof.ps1 -Mode Status",
        "mode": "Status",
        "requires_confirmation": False,
        "requires_explicit_operator_opt_in": False,
        "requires_actor": False,
        "requires_approval_id": False,
        "requires_operator_approval_decision": False,
    }
    resident_surface_checks = {item["id"]: item for item in resident_surface_payload["checks"]}
    assert resident_surface_checks["stage6_completion_audit_runtime_authority_handoff"]["status"] == (
        "completion_audit_recommended_handoff_consumed"
    )

    summon_launch_audit_json = tmp_path / "stage6-completion-audit-summon-launch-readback.json"
    summon_launch_audit_json.write_text(
        json.dumps(
            {
                "kind": "lens.stage6.completion_audit",
                "ok": True,
                "status": "blocked",
                "audit_status": "complete",
                "allow_launch_on_hotkey": True,
                "next_smallest_truthful_gap": "summon_api_launch_on_hotkey_readback",
                "recommended_handoff_source": "stage6_summon_api_launch_on_hotkey_readback_required",
                "recommended_next_slice": "run_summon_api_launch_on_hotkey_proof_for_runtime_readback",
                "recommended_proof_script": (
                    "scripts/lens-summon-api-execution-proof.ps1 -Mode Status -AllowLaunchOnHotkey"
                ),
                "authority_required": "launch_on_hotkey_runtime_readback_opt_in",
                "authority_granted": False,
                "recommended_handoff": {
                    "status": "proof_readback_required",
                    "previous_next_smallest_truthful_gap": "summon_binding_blocker_boundary",
                    "consumed_summon_api_next_smallest_truthful_gap": "os_level_command_palette_binding",
                    "next_smallest_truthful_gap": "summon_api_launch_on_hotkey_readback",
                    "next_step": "run_summon_api_launch_on_hotkey_proof_for_runtime_readback",
                    "proof_script": ("scripts/lens-summon-api-execution-proof.ps1 -Mode Status -AllowLaunchOnHotkey"),
                    "route": "/lens/summon/execute",
                    "readiness_route": "/lens/summon/readiness",
                    "authority_required": "launch_on_hotkey_runtime_readback_opt_in",
                    "authority_granted": False,
                    "summon_api_launch_on_hotkey_runtime_readback_observed": False,
                    "allow_launch_on_hotkey": True,
                    "opened": True,
                    "no_launch": False,
                    "summon_anywhere": False,
                    "os_level_summon": False,
                    "summon_readiness_status_after_execute": "blocked",
                    "read_only_contract": False,
                    "diagnostic_only": True,
                    "would_execute": True,
                    "would_mutate": True,
                    "would_register_tray": False,
                    "would_register_hotkey": False,
                    "would_open_overlay": False,
                    "would_write_memory": False,
                    "would_claim_resident": False,
                    "blockers": ["summon_anywhere_runtime_readback"],
                },
            }
        ),
        encoding="utf-8",
    )

    summon_launch_proc = _run_proof(
        "-Mode",
        "Status",
        "-CompletionAuditJsonPath",
        str(summon_launch_audit_json),
        env=proof_env,
    )

    assert summon_launch_proc.returncode == 0, summon_launch_proc.stderr or summon_launch_proc.stdout
    summon_launch_payload = json.loads(summon_launch_proc.stdout)
    assert summon_launch_payload["recommended_handoff_source"] == (
        "stage6_summon_api_launch_on_hotkey_readback_required"
    )
    assert summon_launch_payload["next_smallest_truthful_gap"] == "summon_api_launch_on_hotkey_readback"
    assert summon_launch_payload["recommended_next_slice"] == (
        "run_summon_api_launch_on_hotkey_proof_for_runtime_readback"
    )
    assert summon_launch_payload["recommended_proof_script"] == (
        "scripts/lens-summon-api-execution-proof.ps1 -Mode Status -AllowLaunchOnHotkey"
    )
    assert summon_launch_payload["authority_required"] == "launch_on_hotkey_runtime_readback_opt_in"
    assert summon_launch_payload["authority_granted"] is False
    assert summon_launch_payload["stage6_completion_audit_readback_observed"] is True
    assert (
        summon_launch_payload["stage6_completion_audit_summon_api_launch_on_hotkey_readback_handoff_observed"] is True
    )
    assert summon_launch_payload["stage6_completion_audit_recommended_handoff_consumed"] is True
    assert summon_launch_payload["stage6_completion_audit_runtime_readback_required"] is False
    summon_launch_handoff = summon_launch_payload["recommended_handoff"]
    assert summon_launch_handoff["next_step"] == "run_summon_api_launch_on_hotkey_proof_for_runtime_readback"
    assert summon_launch_handoff["proof_script"] == (
        "scripts/lens-summon-api-execution-proof.ps1 -Mode Status -AllowLaunchOnHotkey"
    )
    assert summon_launch_handoff["route"] == "/lens/summon/execute"
    assert summon_launch_handoff["readiness_route"] == "/lens/summon/readiness"
    assert summon_launch_handoff["authority_required"] == "launch_on_hotkey_runtime_readback_opt_in"
    assert summon_launch_handoff["authority_granted"] is False
    assert summon_launch_handoff["read_only_contract"] is False
    assert summon_launch_handoff["diagnostic_only"] is True
    assert summon_launch_handoff["would_execute"] is True
    assert summon_launch_handoff["would_mutate"] is True
    assert summon_launch_handoff["would_write_memory"] is False
    assert summon_launch_handoff["would_claim_resident"] is False
    assert summon_launch_payload["recommended_next_operator_command"] == {
        "command": ".\\scripts\\lens-summon-api-execution-proof.ps1 -Mode Status -AllowLaunchOnHotkey",
        "mode": "Status",
        "requires_confirmation": False,
        "requires_explicit_operator_opt_in": True,
        "requires_actor": False,
        "requires_approval_id": False,
        "requires_operator_approval_decision": False,
    }

    prerequisite_operator_plan_audit_json = tmp_path / "stage6-completion-audit-prereq-operator-plan.json"
    prerequisite_operator_plan_audit_json.write_text(
        json.dumps(
            {
                "kind": "lens.stage6.completion_audit",
                "ok": True,
                "status": "blocked",
                "audit_status": "complete",
                "allow_launch_on_hotkey": True,
                "next_smallest_truthful_gap": "persistent_supervision_required_prerequisites_missing",
                "recommended_handoff_source": "stage6_prerequisite_bringup_operator_plan",
                "recommended_next_slice": "run_stage6_prerequisite_bringup_request_next_for_resident_host_process",
                "recommended_proof_script": "scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
                "authority_required": "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites",
                "authority_granted": False,
                "recommended_handoff": {
                    "status": "blocked",
                    "previous_next_smallest_truthful_gap": "resident_host_process_not_supervised",
                    "consumed_process_supervision_next_smallest_truthful_gap": "stage6_lens_completion_audit",
                    "next_smallest_truthful_gap": "persistent_supervision_required_prerequisites_missing",
                    "next_step": "run_stage6_prerequisite_bringup_request_next_for_resident_host_process",
                    "proof_script": "scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
                    "route": "/lens/host/persistent-supervision",
                    "readiness_route": "/lens/host/persistent-supervision/enablement",
                    "operator_plan_script": "scripts/lens-stage6-prerequisite-bringup-plan.ps1",
                    "next_operator_action_requirement": "resident_host_process",
                    "next_operator_action": {
                        "id": "request_resident_runtime_execution_authority",
                        "route": "/lens/resident-runtime/authority-grant/request",
                        "method": "POST",
                        "approval_action": "lens.resident_runtime.execution_authority",
                        "requires": ["actor with system.write scope"],
                        "mode": "",
                        "live_effect": "approval request receipt only",
                        "operator_supplied_values_required": True,
                        "script_would_execute": False,
                        "script_would_mutate": False,
                    },
                    "next_operator_command": {
                        "command": (
                            ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 "
                            "-Mode RequestNext -Actor <actor> -ConfirmRequest"
                        ),
                        "mode": "RequestNext",
                        "requires_confirmation": True,
                        "requires_approval_id": False,
                        "requires_operator_approval_decision": False,
                    },
                    "authority_required": "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites",
                    "authority_granted": False,
                    "first_missing_required_before_enable": "resident_host_process",
                    "read_only_contract": True,
                    "diagnostic_only": True,
                    "would_execute": False,
                    "would_mutate": False,
                    "would_supervise_process": False,
                    "would_restart_process": False,
                    "would_install_service": False,
                    "would_start_service": False,
                    "would_write_memory": False,
                    "would_decide_approval": False,
                    "blockers": ["resident_host_process_not_supervised"],
                },
            }
        ),
        encoding="utf-8",
    )

    prerequisite_operator_plan_proc = _run_proof(
        "-Mode",
        "Status",
        "-CompletionAuditJsonPath",
        str(prerequisite_operator_plan_audit_json),
        env=proof_env,
    )

    assert prerequisite_operator_plan_proc.returncode == 0, (
        prerequisite_operator_plan_proc.stderr or prerequisite_operator_plan_proc.stdout
    )
    prerequisite_operator_plan_payload = json.loads(prerequisite_operator_plan_proc.stdout)
    assert (
        prerequisite_operator_plan_payload["recommended_handoff_source"] == "stage6_prerequisite_bringup_operator_plan"
    )
    assert prerequisite_operator_plan_payload["next_smallest_truthful_gap"] == (
        "persistent_supervision_required_prerequisites_missing"
    )
    assert prerequisite_operator_plan_payload["recommended_next_slice"] == (
        "run_stage6_prerequisite_bringup_request_next_for_resident_host_process"
    )
    assert prerequisite_operator_plan_payload["recommended_proof_script"] == (
        "scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status"
    )
    assert prerequisite_operator_plan_payload["authority_required"] == (
        "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites"
    )
    assert prerequisite_operator_plan_payload["authority_granted"] is False
    assert prerequisite_operator_plan_payload["stage6_completion_audit_readback_observed"] is True
    assert (
        prerequisite_operator_plan_payload[
            "stage6_completion_audit_prerequisite_bringup_operator_plan_handoff_observed"
        ]
        is True
    )
    assert prerequisite_operator_plan_payload["stage6_completion_audit_recommended_handoff_consumed"] is True
    assert prerequisite_operator_plan_payload["stage6_completion_audit_runtime_readback_required"] is False
    prerequisite_operator_plan_handoff = prerequisite_operator_plan_payload["recommended_handoff"]
    assert prerequisite_operator_plan_handoff["status"] == "blocked"
    assert prerequisite_operator_plan_handoff["next_step"] == (
        "run_stage6_prerequisite_bringup_request_next_for_resident_host_process"
    )
    assert prerequisite_operator_plan_handoff["proof_script"] == (
        "scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status"
    )
    assert prerequisite_operator_plan_handoff["route"] == "/lens/host/persistent-supervision"
    assert prerequisite_operator_plan_handoff["readiness_route"] == ("/lens/host/persistent-supervision/enablement")
    assert prerequisite_operator_plan_handoff["authority_required"] == (
        "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites"
    )
    assert prerequisite_operator_plan_handoff["authority_granted"] is False
    assert prerequisite_operator_plan_handoff["first_missing_required_before_enable"] == "resident_host_process"
    assert prerequisite_operator_plan_handoff["next_operator_action_requirement"] == "resident_host_process"
    assert prerequisite_operator_plan_handoff["next_operator_action"]["id"] == (
        "request_resident_runtime_execution_authority"
    )
    assert prerequisite_operator_plan_handoff["next_operator_action"]["route"] == (
        "/lens/resident-runtime/authority-grant/request"
    )
    assert prerequisite_operator_plan_handoff["next_operator_action"]["method"] == "POST"
    assert prerequisite_operator_plan_handoff["next_operator_action"]["approval_action"] == (
        "lens.resident_runtime.execution_authority"
    )
    assert prerequisite_operator_plan_handoff["next_operator_action"]["operator_supplied_values_required"] is True
    assert prerequisite_operator_plan_handoff["next_operator_command"]["mode"] == "RequestNext"
    assert prerequisite_operator_plan_handoff["next_operator_command"]["requires_confirmation"] is True
    assert prerequisite_operator_plan_handoff["next_operator_command"]["requires_approval_id"] is False
    assert prerequisite_operator_plan_handoff["next_operator_command"]["requires_operator_approval_decision"] is False
    assert prerequisite_operator_plan_handoff["read_only_contract"] is True
    assert prerequisite_operator_plan_handoff["diagnostic_only"] is True
    assert prerequisite_operator_plan_handoff["would_execute"] is False
    assert prerequisite_operator_plan_handoff["would_mutate"] is False
    assert prerequisite_operator_plan_handoff["would_supervise_process"] is False
    assert prerequisite_operator_plan_handoff["would_restart_process"] is False
    assert prerequisite_operator_plan_handoff["would_install_service"] is False
    assert prerequisite_operator_plan_handoff["would_start_service"] is False
    assert prerequisite_operator_plan_handoff["would_write_memory"] is False
    assert prerequisite_operator_plan_handoff["would_decide_approval"] is False
    assert prerequisite_operator_plan_payload["recommended_operator_handoff"]["source"] == (
        "stage6_completion_audit_recommended_handoff"
    )
    assert prerequisite_operator_plan_payload["recommended_next_operator_action_requirement"] == (
        "stage6_completion_audit_recommended_readback"
    )
    assert prerequisite_operator_plan_payload["recommended_next_operator_action"]["id"] == (
        "run_stage6_prerequisite_bringup_request_next_for_resident_host_process"
    )
    assert prerequisite_operator_plan_payload["recommended_next_operator_action"]["method"] == "LOCAL_SCRIPT"
    assert prerequisite_operator_plan_payload["recommended_next_operator_action"]["script_would_execute"] is False
    assert prerequisite_operator_plan_payload["recommended_next_operator_action"]["script_would_mutate"] is False
    assert prerequisite_operator_plan_payload["recommended_next_operator_command"] == {
        "command": ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
        "mode": "Status",
        "requires_confirmation": False,
        "requires_explicit_operator_opt_in": False,
        "requires_actor": False,
        "requires_approval_id": False,
        "requires_operator_approval_decision": False,
    }
    prerequisite_operator_plan_checks = {item["id"]: item for item in prerequisite_operator_plan_payload["checks"]}
    assert prerequisite_operator_plan_checks["stage6_completion_audit_runtime_authority_handoff"]["status"] == (
        "completion_audit_recommended_handoff_consumed"
    )

    closure_operator_plan_audit_json = tmp_path / "stage6-completion-audit-closure-operator-plan.json"
    closure_operator_plan_audit_json.write_text(
        json.dumps(
            {
                "kind": "lens.stage6.completion_audit",
                "ok": True,
                "status": "blocked",
                "audit_status": "complete",
                "allow_launch_on_hotkey": True,
                "stage6_completion_reviewed": True,
                "next_smallest_truthful_gap": "summon_anywhere_blockers",
                "recommended_handoff_source": "stage6_closure_readback_summon_resident_host_blocker",
                "recommended_next_slice": "run_stage6_prerequisite_bringup_request_next_for_resident_host_process",
                "recommended_proof_script": "scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
                "authority_required": "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites",
                "authority_granted": False,
                "recommended_handoff": {
                    "status": "blocked",
                    "previous_next_smallest_truthful_gap": "stage6_lens_completion_audit",
                    "consumed_summon_anywhere_next_smallest_truthful_gap": "summon_anywhere_blockers",
                    "next_smallest_truthful_gap": "persistent_supervision_execution_boundary",
                    "next_step": "run_stage6_prerequisite_bringup_request_next_for_resident_host_process",
                    "proof_script": "scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
                    "route": "/lens/host/persistent-supervision",
                    "readiness_route": "/lens/host/persistent-supervision/enablement",
                    "operator_plan_script": "scripts/lens-stage6-prerequisite-bringup-plan.ps1",
                    "next_operator_action_requirement": "resident_host_process",
                    "next_operator_action": {
                        "id": "request_resident_runtime_execution_authority",
                        "route": "/lens/resident-runtime/authority-grant/request",
                        "method": "POST",
                        "approval_action": "lens.resident_runtime.execution_authority",
                        "requires": ["actor with system.write scope"],
                        "mode": "",
                        "live_effect": "approval request receipt only",
                        "operator_supplied_values_required": True,
                        "script_would_execute": False,
                        "script_would_mutate": False,
                    },
                    "next_operator_command": {
                        "command": (
                            ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 "
                            "-Mode RequestNext -Actor <actor> -ConfirmRequest"
                        ),
                        "mode": "RequestNext",
                        "requires_confirmation": True,
                        "requires_approval_id": False,
                        "requires_operator_approval_decision": False,
                    },
                    "authority_required": "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites",
                    "authority_granted": False,
                    "read_only_contract": True,
                    "diagnostic_only": True,
                    "would_execute": False,
                    "would_mutate": False,
                    "would_supervise_process": False,
                    "would_restart_process": False,
                    "would_install_service": False,
                    "would_start_service": False,
                    "would_write_memory": False,
                    "would_decide_approval": False,
                },
            }
        ),
        encoding="utf-8",
    )

    closure_operator_plan_proc = _run_proof(
        "-Mode",
        "Status",
        "-CompletionAuditJsonPath",
        str(closure_operator_plan_audit_json),
        env=proof_env,
    )

    assert closure_operator_plan_proc.returncode == 0, (
        closure_operator_plan_proc.stderr or closure_operator_plan_proc.stdout
    )
    closure_operator_plan_payload = json.loads(closure_operator_plan_proc.stdout)
    assert (
        closure_operator_plan_payload["recommended_handoff_source"]
        == "stage6_closure_readback_summon_resident_host_blocker"
    )
    assert closure_operator_plan_payload["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert closure_operator_plan_payload["recommended_next_slice"] == (
        "run_stage6_prerequisite_bringup_request_next_for_resident_host_process"
    )
    assert closure_operator_plan_payload["stage6_completion_audit_readback_observed"] is True
    assert (
        closure_operator_plan_payload["stage6_completion_audit_prerequisite_bringup_operator_plan_handoff_observed"]
        is True
    )
    assert closure_operator_plan_payload["stage6_completion_audit_recommended_handoff_consumed"] is True
    assert closure_operator_plan_payload["stage6_completion_audit_runtime_readback_required"] is False
    assert closure_operator_plan_payload["recommended_handoff"]["next_smallest_truthful_gap"] == (
        "persistent_supervision_execution_boundary"
    )
    assert closure_operator_plan_payload["recommended_next_operator_action"]["id"] == (
        "run_stage6_prerequisite_bringup_request_next_for_resident_host_process"
    )

    overlay_operator_plan_audit_json = tmp_path / "stage6-completion-audit-overlay-operator-plan.json"
    overlay_operator_plan_audit_json.write_text(
        json.dumps(
            {
                "kind": "lens.stage6.completion_audit",
                "ok": True,
                "status": "blocked",
                "audit_status": "complete",
                "allow_launch_on_hotkey": False,
                "next_smallest_truthful_gap": "persistent_supervision_required_prerequisites_missing",
                "recommended_handoff_source": "stage6_prerequisite_bringup_operator_plan",
                "recommended_next_slice": "run_stage6_prerequisite_bringup_grant_overlay_window_authority",
                "recommended_proof_script": "scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
                "authority_required": "lens.overlay.window_authority",
                "authority_granted": False,
                "recommended_handoff": {
                    "status": "blocked",
                    "previous_next_smallest_truthful_gap": ("persistent_supervision_required_prerequisites_missing"),
                    "consumed_stage6_prerequisite_bringup_status": "blocked",
                    "consumed_stage6_prerequisite_bringup_current_truthful_gap": (
                        "persistent_supervision_required_prerequisites_missing"
                    ),
                    "consumed_stage6_prerequisite_bringup_current_truthful_gap_basis": (
                        "missing_required_before_enable"
                    ),
                    "next_smallest_truthful_gap": "persistent_supervision_required_prerequisites_missing",
                    "next_step": "run_stage6_prerequisite_bringup_grant_overlay_window_authority",
                    "proof_script": "scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
                    "route": "/lens/host/persistent-supervision",
                    "readiness_route": "/lens/host/persistent-supervision/enablement",
                    "operator_plan_script": "scripts/lens-stage6-prerequisite-bringup-plan.ps1",
                    "next_operator_action_requirement": "overlay_window",
                    "next_operator_action": {
                        "id": "grant_overlay_window_authority",
                        "route": "/lens/overlay/authority",
                        "method": "POST",
                        "approval_action": "lens.overlay.window_authority",
                        "requires": ["exact approved lens.overlay.window_authority approval_id"],
                        "mode": "",
                        "live_effect": "authority grant receipt",
                        "operator_supplied_values_required": True,
                        "script_would_execute": False,
                        "script_would_mutate": False,
                        "approved_approval_id": "83f36f9a-0e8a-42c7-a28f-21b3cbe67a7f",
                    },
                    "next_operator_command": {
                        "command": (
                            ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 "
                            "-Mode GrantNext -Actor <actor> "
                            "-ApprovalId 83f36f9a-0e8a-42c7-a28f-21b3cbe67a7f -ConfirmGrant"
                        ),
                        "mode": "GrantNext",
                        "requires_confirmation": True,
                        "requires_approval_id": True,
                        "requires_operator_approval_decision": True,
                    },
                    "operator_sequence_command_availability": {
                        "available_now_count": 1,
                        "preview_only_count": 0,
                        "sequence_length": 1,
                        "truthful": True,
                    },
                    "authority_required": "lens.overlay.window_authority",
                    "prerequisite_authority_scope": "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites",
                    "authority_granted": False,
                    "first_missing_required_before_enable": "overlay_window",
                    "first_missing_truthful_gap": "summon_overlay_window_blocker_boundary",
                    "first_missing_truthful_gap_expected": ["summon_overlay_window_blocker_boundary"],
                    "first_missing_truthful_gap_paired": True,
                    "first_missing_requirement_handoff": {
                        "id": "grant_overlay_window_authority",
                        "route": "/lens/overlay/authority",
                        "method": "POST",
                        "approval_action": "lens.overlay.window_authority",
                        "operator_supplied_values_required": True,
                        "script_would_execute": False,
                        "script_would_mutate": False,
                    },
                    "read_only_contract": True,
                    "diagnostic_only": True,
                    "would_execute": False,
                    "would_mutate": False,
                    "would_request_authority": False,
                    "would_grant_authority": False,
                    "would_supervise_process": False,
                    "would_restart_process": False,
                    "would_install_service": False,
                    "would_start_service": False,
                    "would_write_memory": False,
                    "would_decide_approval": False,
                    "blockers": [
                        "persistent_supervision_required_prerequisites_missing",
                        "summon_overlay_window_blocker_boundary",
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    overlay_operator_plan_proc = _run_proof(
        "-Mode",
        "Status",
        "-CompletionAuditJsonPath",
        str(overlay_operator_plan_audit_json),
        env=proof_env,
    )

    assert overlay_operator_plan_proc.returncode == 0, (
        overlay_operator_plan_proc.stderr or overlay_operator_plan_proc.stdout
    )
    overlay_operator_plan_payload = json.loads(overlay_operator_plan_proc.stdout)
    assert overlay_operator_plan_payload["recommended_handoff_source"] == "stage6_prerequisite_bringup_operator_plan"
    assert overlay_operator_plan_payload["recommended_next_slice"] == (
        "run_stage6_prerequisite_bringup_grant_overlay_window_authority"
    )
    assert overlay_operator_plan_payload["authority_required"] == "lens.overlay.window_authority"
    assert (
        overlay_operator_plan_payload["stage6_completion_audit_prerequisite_bringup_operator_plan_handoff_observed"]
        is True
    )
    assert overlay_operator_plan_payload["stage6_completion_audit_recommended_handoff_consumed"] is True
    overlay_operator_plan_handoff = overlay_operator_plan_payload["recommended_handoff"]
    assert overlay_operator_plan_handoff["authority_required"] == "lens.overlay.window_authority"
    assert overlay_operator_plan_handoff["next_operator_action_requirement"] == "overlay_window"
    assert overlay_operator_plan_handoff["first_missing_required_before_enable"] == "overlay_window"
    assert overlay_operator_plan_handoff["next_operator_action"]["id"] == "grant_overlay_window_authority"
    assert overlay_operator_plan_handoff["next_operator_command"]["mode"] == "GrantNext"
    assert overlay_operator_plan_handoff["authority_granted"] is False
    assert overlay_operator_plan_handoff["read_only_contract"] is True
    assert overlay_operator_plan_handoff["would_execute"] is False
    assert overlay_operator_plan_handoff["would_mutate"] is False
    assert overlay_operator_plan_payload["recommended_next_operator_action"]["id"] == (
        "run_stage6_prerequisite_bringup_grant_overlay_window_authority"
    )

    tray_audit_json = tmp_path / "stage6-completion-audit-tray-presence.json"
    tray_audit_json.write_text(
        json.dumps(
            {
                "kind": "lens.stage6.completion_audit",
                "ok": True,
                "status": "blocked",
                "audit_status": "complete",
                "allow_launch_on_hotkey": True,
                "next_smallest_truthful_gap": "summon_tray_presence_blocker_boundary",
                "recommended_handoff_source": "api_resident_runtime_execution_tray_presence_handoff",
                "recommended_next_slice": "prove_governed_tray_presence_api_execution_after_resident_supervision",
                "recommended_proof_script": "scripts/lens-tray-presence-api-execution-proof.ps1 -Mode Status",
                "authority_required": "tray_registration_authority",
                "authority_granted": False,
                "recommended_handoff": {
                    "status": "blocked",
                    "previous_next_smallest_truthful_gap": "resident_surface_runtime_not_supervised",
                    "consumed_resident_surface_foreground_runtime_proof": True,
                    "consumed_resident_runtime_api_execution_proof": True,
                    "consumed_resident_runtime_api_next_smallest_truthful_gap": (
                        "summon_tray_presence_blocker_boundary"
                    ),
                    "next_smallest_truthful_gap": "summon_tray_presence_blocker_boundary",
                    "next_step": "prove_governed_tray_presence_api_execution_after_resident_supervision",
                    "proof_script": "scripts/lens-tray-presence-api-execution-proof.ps1 -Mode Status",
                    "route": "/lens/tray",
                    "readiness_route": "/lens/tray/readiness",
                    "acceptance_criterion": "summon_anywhere",
                    "authority_required": "tray_registration_authority",
                    "authority_granted": False,
                    "resident_runtime_execution_authority": True,
                    "host_supervision_authority": True,
                    "resident_runtime_plan_ready": True,
                    "resident_host_process_started": True,
                    "resident_supervised_runtime_started": True,
                    "resident_supervision_stop_observed": True,
                    "tray_presence": False,
                    "global_hotkey": False,
                    "overlay_window": False,
                    "summon_anywhere": False,
                    "service_managed": False,
                    "resident_claim_allowed": False,
                    "read_only_contract": True,
                    "diagnostic_only": True,
                    "would_execute": False,
                    "would_mutate": False,
                    "would_register_tray": False,
                    "would_register_hotkey": False,
                    "would_open_overlay": False,
                    "would_write_memory": False,
                    "would_claim_resident": False,
                },
            }
        ),
        encoding="utf-8",
    )

    tray_proc = _run_proof(
        "-Mode",
        "Status",
        "-CompletionAuditJsonPath",
        str(tray_audit_json),
        env=proof_env,
    )

    assert tray_proc.returncode == 0, tray_proc.stderr or tray_proc.stdout
    tray_payload = json.loads(tray_proc.stdout)
    assert tray_payload["recommended_handoff_source"] == "api_resident_runtime_execution_tray_presence_handoff"
    assert tray_payload["next_smallest_truthful_gap"] == "summon_tray_presence_blocker_boundary"
    assert tray_payload["recommended_next_slice"] == (
        "prove_governed_tray_presence_api_execution_after_resident_supervision"
    )
    assert tray_payload["recommended_proof_script"] == "scripts/lens-tray-presence-api-execution-proof.ps1 -Mode Status"
    assert tray_payload["authority_required"] == "tray_registration_authority"
    assert tray_payload["authority_granted"] is False
    assert tray_payload["stage6_completion_audit_readback_observed"] is True
    assert tray_payload["stage6_completion_audit_resident_runtime_tray_presence_handoff_observed"] is True
    assert tray_payload["stage6_completion_audit_recommended_handoff_consumed"] is True
    assert tray_payload["stage6_completion_audit_runtime_readback_required"] is False
    tray_handoff = tray_payload["recommended_handoff"]
    assert tray_handoff["next_step"] == "prove_governed_tray_presence_api_execution_after_resident_supervision"
    assert tray_handoff["proof_script"] == "scripts/lens-tray-presence-api-execution-proof.ps1 -Mode Status"
    assert tray_handoff["route"] == "/lens/tray"
    assert tray_handoff["readiness_route"] == "/lens/tray/readiness"
    assert tray_handoff["authority_required"] == "tray_registration_authority"
    assert tray_handoff["authority_granted"] is False
    assert tray_handoff["read_only_contract"] is True
    assert tray_handoff["diagnostic_only"] is True
    assert tray_handoff["would_execute"] is False
    assert tray_handoff["would_mutate"] is False
    assert tray_handoff["would_register_tray"] is False
    assert tray_handoff["would_write_memory"] is False
    assert tray_handoff["would_claim_resident"] is False
    assert tray_payload["recommended_operator_handoff"]["source"] == "stage6_completion_audit_recommended_handoff"
    assert tray_payload["recommended_next_operator_action_requirement"] == (
        "stage6_completion_audit_recommended_readback"
    )
    assert tray_payload["recommended_next_operator_action"]["id"] == (
        "prove_governed_tray_presence_api_execution_after_resident_supervision"
    )
    assert tray_payload["recommended_next_operator_command"] == {
        "command": ".\\scripts\\lens-tray-presence-api-execution-proof.ps1 -Mode Status",
        "mode": "Status",
        "requires_confirmation": False,
        "requires_explicit_operator_opt_in": False,
        "requires_actor": False,
        "requires_approval_id": False,
        "requires_operator_approval_decision": False,
    }
    tray_checks = {item["id"]: item for item in tray_payload["checks"]}
    assert tray_checks["stage6_completion_audit_runtime_authority_handoff"]["status"] == (
        "completion_audit_recommended_handoff_consumed"
    )

    enablement_receipt_audit_json = tmp_path / "stage6-completion-audit-enable-receipt.json"
    enablement_receipt_audit_json.write_text(
        json.dumps(
            {
                "kind": "lens.stage6.completion_audit",
                "ok": True,
                "status": "blocked",
                "audit_status": "complete",
                "allow_launch_on_hotkey": True,
                "next_smallest_truthful_gap": "persistent_supervision_execution_boundary",
                "recommended_handoff_source": "stage6_prerequisite_bringup_enablement_receipt_review",
                "recommended_next_slice": (
                    "run_stage6_prerequisite_bringup_review_persistent_supervision_enablement_receipt"
                ),
                "recommended_proof_script": "scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
                "authority_required": "none_readback_only",
                "authority_granted": False,
                "recommended_handoff": {
                    "status": "receipt_review_ready",
                    "previous_next_smallest_truthful_gap": "stage6_lens_completion_audit",
                    "consumed_stage6_prerequisite_bringup_status": "persistent_supervision_enablement_applied",
                    "next_smallest_truthful_gap": "persistent_supervision_execution_boundary",
                    "next_step": ("run_stage6_prerequisite_bringup_review_persistent_supervision_enablement_receipt"),
                    "proof_script": "scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
                    "route": "/lens/host/persistent-supervision/enablement/executions",
                    "operator_plan_script": "scripts/lens-stage6-prerequisite-bringup-plan.ps1",
                    "current_truthful_gap_basis": (
                        "persistent_supervision_enablement_execution_receipt.post_plan.next_smallest_truthful_gap"
                    ),
                    "next_operator_action_requirement": "persistent_supervision_enablement_receipt",
                    "next_operator_action": {
                        "id": "review_persistent_supervision_enablement_receipt",
                        "route": "/lens/host/persistent-supervision/enablement/executions",
                        "method": "GET",
                        "approval_action": "lens.host.persistent_supervision_enablement_execution_authority",
                        "requires": ["persistent supervision enablement execution receipt readback"],
                        "mode": "readback",
                        "live_effect": (
                            "persistent supervision enablement execution receipt is recorded; "
                            "review resident claim boundary next"
                        ),
                        "operator_supplied_values_required": False,
                        "script_would_execute": False,
                        "script_would_mutate": False,
                        "latest_receipt_id": "lpsee_test_receipt",
                    },
                    "next_operator_command": {
                        "command": ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
                        "mode": "Status",
                        "requires_confirmation": False,
                        "requires_approval_id": False,
                        "requires_operator_approval_decision": False,
                    },
                    "latest_receipt_id": "lpsee_test_receipt",
                    "authority_required": "none_readback_only",
                    "authority_granted": False,
                    "read_only_contract": True,
                    "diagnostic_only": True,
                    "would_execute": False,
                    "would_mutate": False,
                    "would_request_authority": False,
                    "would_grant_authority": False,
                    "would_write_memory": False,
                    "would_decide_approval": False,
                },
            }
        ),
        encoding="utf-8",
    )

    enablement_receipt_proc = _run_proof(
        "-Mode",
        "Status",
        "-CompletionAuditJsonPath",
        str(enablement_receipt_audit_json),
        env=proof_env,
    )

    assert enablement_receipt_proc.returncode == 0, enablement_receipt_proc.stderr or enablement_receipt_proc.stdout
    enablement_receipt_payload = json.loads(enablement_receipt_proc.stdout)
    assert enablement_receipt_payload["recommended_handoff_source"] == (
        "stage6_completion_audit_launch_on_hotkey_readback_required"
    )
    assert enablement_receipt_payload["next_smallest_truthful_gap"] == ("stage6_lens_completion_audit_runtime_readback")
    assert enablement_receipt_payload["recommended_next_slice"] == (
        "run_stage6_completion_audit_with_launch_on_hotkey_runtime_readback"
    )
    assert enablement_receipt_payload["recommended_proof_script"] == (
        "scripts/lens-stage6-completion-audit.ps1 -Mode Status -AllowLaunchOnHotkey"
    )
    assert enablement_receipt_payload["authority_required"] == "launch_on_hotkey_runtime_readback_opt_in"
    assert enablement_receipt_payload["authority_granted"] is False
    assert enablement_receipt_payload["stage6_completion_audit_readback_observed"] is True
    assert enablement_receipt_payload["stage6_completion_audit_enablement_receipt_review_handoff_observed"] is True
    assert enablement_receipt_payload["stage6_completion_audit_recommended_handoff_consumed"] is False
    assert enablement_receipt_payload["stage6_completion_audit_runtime_readback_required"] is True
    enablement_receipt_handoff = enablement_receipt_payload["recommended_handoff"]
    assert enablement_receipt_handoff["status"] == "runtime_readback_required"
    assert enablement_receipt_handoff["previous_next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert enablement_receipt_handoff["previous_closure_readback_next_smallest_truthful_gap"] == (
        "summon_anywhere_blockers"
    )
    assert enablement_receipt_handoff["next_smallest_truthful_gap"] == ("stage6_lens_completion_audit_runtime_readback")
    assert enablement_receipt_handoff["next_step"] == (
        "run_stage6_completion_audit_with_launch_on_hotkey_runtime_readback"
    )
    assert enablement_receipt_handoff["proof_script"] == (
        "scripts/lens-stage6-completion-audit.ps1 -Mode Status -AllowLaunchOnHotkey"
    )
    assert enablement_receipt_handoff["route"] == "/lens/status"
    assert enablement_receipt_handoff["readiness_route"] == "/lens/resident-runtime/authority-grant/readiness"
    assert enablement_receipt_handoff["acceptance_criterion"] == "helpful_not_noisy"
    assert enablement_receipt_handoff["first_blocker_family"] == "resident_host"
    assert enablement_receipt_handoff["authority_required"] == "launch_on_hotkey_runtime_readback_opt_in"
    assert enablement_receipt_handoff["authority_granted"] is False
    assert enablement_receipt_handoff["requires_explicit_operator_opt_in"] is True
    assert enablement_receipt_handoff["completion_audit_json_parameter"] == "-CompletionAuditJsonPath"
    assert enablement_receipt_handoff["read_only_contract"] is True
    assert enablement_receipt_handoff["diagnostic_only"] is True
    assert enablement_receipt_handoff["would_execute"] is False
    assert enablement_receipt_handoff["would_mutate"] is False
    assert enablement_receipt_handoff["would_launch_process"] is False
    assert enablement_receipt_handoff["would_supervise_process"] is False
    assert enablement_receipt_handoff["would_register_hotkey"] is False
    assert enablement_receipt_handoff["would_control_overlay"] is False
    assert enablement_receipt_handoff["would_summon"] is False
    assert enablement_receipt_handoff["would_decide_approval"] is False
    assert enablement_receipt_payload["recommended_operator_handoff"]["source"] == (
        "stage6_completion_audit_launch_on_hotkey_readback_required"
    )
    assert enablement_receipt_payload["recommended_next_operator_action_requirement"] == (
        "stage6_completion_audit_runtime_readback"
    )
    assert enablement_receipt_payload["recommended_next_operator_action"]["id"] == (
        "run_stage6_completion_audit_with_launch_on_hotkey_runtime_readback"
    )
    assert enablement_receipt_payload["recommended_next_operator_action"]["requires_explicit_operator_opt_in"] is True
    assert enablement_receipt_payload["recommended_next_operator_action"]["script_would_execute"] is False
    assert enablement_receipt_payload["recommended_next_operator_action"]["script_would_mutate"] is False
    assert enablement_receipt_payload["recommended_next_operator_command"] == {
        "command": ".\\scripts\\lens-stage6-completion-audit.ps1 -Mode Status -AllowLaunchOnHotkey",
        "mode": "Status",
        "requires_confirmation": False,
        "requires_explicit_operator_opt_in": True,
        "requires_approval_id": False,
        "requires_operator_approval_decision": False,
        "completion_audit_json_parameter": "-CompletionAuditJsonPath",
    }
    enablement_receipt_checks = {item["id"]: item for item in enablement_receipt_payload["checks"]}
    assert enablement_receipt_checks["stage6_completion_audit_runtime_authority_handoff"]["status"] == (
        "completion_audit_readback_observed"
    )

    generic_operator_receipt_audit_json = tmp_path / "stage6-completion-audit-operator-receipt.json"
    generic_operator_receipt_audit_json.write_text(
        json.dumps(
            {
                "kind": "lens.stage6.completion_audit",
                "ok": True,
                "status": "blocked",
                "audit_status": "complete",
                "allow_launch_on_hotkey": True,
                "next_smallest_truthful_gap": "summon_anywhere_blockers",
                "recommended_handoff_source": "stage6_prerequisite_bringup_operator_plan",
                "recommended_next_slice": (
                    "run_stage6_prerequisite_bringup_review_persistent_supervision_enablement_receipt"
                ),
                "recommended_proof_script": "scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
                "authority_required": "none_readback_only",
                "authority_granted": False,
                "recommended_handoff": {
                    "status": "blocked",
                    "previous_next_smallest_truthful_gap": "summon_anywhere_blockers",
                    "consumed_stage6_prerequisite_bringup_status": "persistent_supervision_enablement_applied",
                    "next_smallest_truthful_gap": "persistent_supervision_execution_boundary",
                    "next_step": ("run_stage6_prerequisite_bringup_review_persistent_supervision_enablement_receipt"),
                    "proof_script": "scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
                    "route": "/lens/host/persistent-supervision/enablement/executions",
                    "operator_plan_script": "scripts/lens-stage6-prerequisite-bringup-plan.ps1",
                    "current_truthful_gap_basis": (
                        "persistent_supervision_enablement_execution_receipt.post_plan.next_smallest_truthful_gap"
                    ),
                    "next_operator_action_requirement": "persistent_supervision_enablement_receipt",
                    "next_operator_action": {
                        "id": "review_persistent_supervision_enablement_receipt",
                        "route": "/lens/host/persistent-supervision/enablement/executions",
                        "method": "GET",
                        "approval_action": "lens.host.persistent_supervision_enablement_execution_authority",
                        "requires": ["persistent supervision enablement execution receipt readback"],
                        "mode": "readback",
                        "operator_supplied_values_required": False,
                        "script_would_execute": False,
                        "script_would_mutate": False,
                        "latest_receipt_id": "lpsee_test_applied",
                    },
                    "next_operator_command": {
                        "command": ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
                        "mode": "Status",
                        "requires_confirmation": False,
                        "requires_approval_id": False,
                        "requires_operator_approval_decision": False,
                    },
                    "authority_required": "none_readback_only",
                    "authority_granted": False,
                    "read_only_contract": True,
                    "diagnostic_only": True,
                    "would_execute": False,
                    "would_mutate": False,
                    "would_request_authority": False,
                    "would_grant_authority": False,
                    "would_write_memory": False,
                    "would_decide_approval": False,
                },
            }
        ),
        encoding="utf-8",
    )

    generic_operator_receipt_proc = _run_proof(
        "-Mode",
        "Status",
        "-CompletionAuditJsonPath",
        str(generic_operator_receipt_audit_json),
        env=proof_env,
    )

    assert generic_operator_receipt_proc.returncode == 0, (
        generic_operator_receipt_proc.stderr or generic_operator_receipt_proc.stdout
    )
    generic_operator_receipt_payload = json.loads(generic_operator_receipt_proc.stdout)
    assert generic_operator_receipt_payload["recommended_handoff_source"] == (
        "stage6_completion_audit_launch_on_hotkey_readback_required"
    )
    assert generic_operator_receipt_payload["next_smallest_truthful_gap"] == (
        "stage6_lens_completion_audit_runtime_readback"
    )
    assert generic_operator_receipt_payload["recommended_next_slice"] == (
        "run_stage6_completion_audit_with_launch_on_hotkey_runtime_readback"
    )
    assert (
        generic_operator_receipt_payload["stage6_completion_audit_enablement_receipt_review_handoff_observed"] is True
    )
    assert generic_operator_receipt_payload["stage6_completion_audit_recommended_handoff_consumed"] is False
    assert generic_operator_receipt_payload["stage6_completion_audit_runtime_readback_required"] is True
    generic_operator_receipt_handoff = generic_operator_receipt_payload["recommended_handoff"]
    assert generic_operator_receipt_handoff["status"] == "runtime_readback_required"
    assert generic_operator_receipt_handoff["next_smallest_truthful_gap"] == (
        "stage6_lens_completion_audit_runtime_readback"
    )
    assert generic_operator_receipt_payload["recommended_operator_handoff"]["source"] == (
        "stage6_completion_audit_launch_on_hotkey_readback_required"
    )
    assert generic_operator_receipt_payload["recommended_next_operator_action_requirement"] == (
        "stage6_completion_audit_runtime_readback"
    )
    generic_operator_receipt_checks = {item["id"]: item for item in generic_operator_receipt_payload["checks"]}
    assert generic_operator_receipt_checks["stage6_completion_audit_runtime_authority_handoff"]["status"] == (
        "completion_audit_readback_observed"
    )

    runtime_operator_receipt_audit_json = tmp_path / "stage6-completion-audit-operator-receipt-runtime.json"
    runtime_operator_receipt_audit = json.loads(generic_operator_receipt_audit_json.read_text(encoding="utf-8"))
    runtime_operator_receipt_audit["summon_api_launch_on_hotkey_proof"] = {
        "status": "proof_passed",
        "ok": True,
        "allow_launch_on_hotkey": True,
        "opened": True,
        "summon_anywhere": True,
        "os_level_summon": True,
        "next_smallest_truthful_gap": "stage6_lens_completion_audit",
    }
    runtime_operator_receipt_audit_json.write_text(
        json.dumps(runtime_operator_receipt_audit),
        encoding="utf-8",
    )

    runtime_operator_receipt_proc = _run_proof(
        "-Mode",
        "Status",
        "-CompletionAuditJsonPath",
        str(runtime_operator_receipt_audit_json),
        env=proof_env,
    )

    assert runtime_operator_receipt_proc.returncode == 0, (
        runtime_operator_receipt_proc.stderr or runtime_operator_receipt_proc.stdout
    )
    runtime_operator_receipt_payload = json.loads(runtime_operator_receipt_proc.stdout)
    assert runtime_operator_receipt_payload["recommended_handoff_source"] == (
        "stage6_prerequisite_bringup_operator_plan"
    )
    assert runtime_operator_receipt_payload["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert runtime_operator_receipt_payload["recommended_next_slice"] == (
        "run_stage6_prerequisite_bringup_review_persistent_supervision_enablement_receipt"
    )
    assert (
        runtime_operator_receipt_payload["stage6_completion_audit_launch_on_hotkey_runtime_readback_observed"] is True
    )
    assert runtime_operator_receipt_payload["stage6_completion_audit_recommended_handoff_consumed"] is True
    assert runtime_operator_receipt_payload["stage6_completion_audit_runtime_readback_required"] is False
    assert runtime_operator_receipt_payload["recommended_handoff"]["next_smallest_truthful_gap"] == (
        "persistent_supervision_execution_boundary"
    )

    reviewed_first_blocker_audit_json = tmp_path / "stage6-completion-audit-reviewed-first-blocker.json"
    reviewed_first_blocker_audit = json.loads(runtime_operator_receipt_audit_json.read_text(encoding="utf-8"))
    reviewed_first_blocker_audit["recommended_handoff_source"] = "stage6_reviewed_summon_anywhere_first_blocker"
    reviewed_first_blocker_audit["recommended_next_slice"] = "run_resident_host_blocker_proof"
    reviewed_first_blocker_audit["recommended_proof_script"] = (
        "scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status"
    )
    reviewed_first_blocker_audit["authority_required"] = "resident_runtime_execution_authority"
    reviewed_first_blocker_audit["recommended_handoff"] = {
        "status": "blocked",
        "previous_next_smallest_truthful_gap": "stage6_lens_completion_audit",
        "consumed_summon_anywhere_next_smallest_truthful_gap": "summon_anywhere_blockers",
        "consumed_family_chain_next_smallest_truthful_gap": "summon_anywhere_blockers",
        "consumed_persistent_supervision_resident_claim_boundary_next_smallest_truthful_gap": (
            "stage6_lens_completion_audit"
        ),
        "next_smallest_truthful_gap": "resident_host_runtime_blocker_boundary",
        "next_step": "run_resident_host_blocker_proof",
        "proof_script": "scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status",
        "route": "/lens/host",
        "readiness_route": "/lens/host/runtime-loop/readiness",
        "acceptance_criterion": "summon_anywhere",
        "first_blocker_family": "resident_host",
        "authority_required": "resident_runtime_execution_authority",
        "authority_granted": False,
        "read_only_contract": True,
        "diagnostic_only": True,
        "would_execute": False,
        "would_mutate": False,
        "would_supervise_process": False,
        "would_restart_process": False,
        "would_install_service": False,
        "would_start_service": False,
        "would_register_hotkey": False,
        "would_control_overlay": False,
        "would_summon": False,
        "would_write_memory": False,
        "would_decide_approval": False,
        "blockers": ["local_process_launch_authority_not_granted"],
    }
    reviewed_first_blocker_audit_json.write_text(
        json.dumps(reviewed_first_blocker_audit),
        encoding="utf-8",
    )

    reviewed_first_blocker_proc = _run_proof(
        "-Mode",
        "Status",
        "-CompletionAuditJsonPath",
        str(reviewed_first_blocker_audit_json),
        env=proof_env,
    )

    assert reviewed_first_blocker_proc.returncode == 0, (
        reviewed_first_blocker_proc.stderr or reviewed_first_blocker_proc.stdout
    )
    reviewed_first_blocker_payload = json.loads(reviewed_first_blocker_proc.stdout)
    assert (
        reviewed_first_blocker_payload["recommended_handoff_source"] == "stage6_reviewed_summon_anywhere_first_blocker"
    )
    assert reviewed_first_blocker_payload["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert reviewed_first_blocker_payload["recommended_next_slice"] == "run_resident_host_blocker_proof"
    assert reviewed_first_blocker_payload["recommended_proof_script"] == (
        "scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status"
    )
    assert reviewed_first_blocker_payload["authority_required"] == "resident_runtime_execution_authority"
    assert reviewed_first_blocker_payload["authority_granted"] is False
    assert (
        reviewed_first_blocker_payload["stage6_completion_audit_reviewed_summon_first_blocker_handoff_observed"] is True
    )
    assert reviewed_first_blocker_payload["stage6_completion_audit_recommended_handoff_consumed"] is True
    assert reviewed_first_blocker_payload["stage6_completion_audit_runtime_readback_required"] is False
    reviewed_first_blocker_handoff = reviewed_first_blocker_payload["recommended_handoff"]
    assert reviewed_first_blocker_handoff["next_smallest_truthful_gap"] == "resident_host_runtime_blocker_boundary"
    assert reviewed_first_blocker_handoff["next_step"] == "run_resident_host_blocker_proof"
    assert reviewed_first_blocker_handoff["read_only_contract"] is True
    assert reviewed_first_blocker_handoff["diagnostic_only"] is True
    assert reviewed_first_blocker_payload["recommended_concrete_next_smallest_truthful_gap"] == (
        "resident_host_runtime_blocker_boundary"
    )
    assert reviewed_first_blocker_payload["recommended_operator_handoff"]["source"] == (
        "stage6_completion_audit_recommended_handoff"
    )
    assert reviewed_first_blocker_payload["recommended_next_operator_action_requirement"] == (
        "stage6_completion_audit_recommended_readback"
    )
    assert reviewed_first_blocker_payload["recommended_next_operator_action"]["id"] == "run_resident_host_blocker_proof"

    persistent_prereq_audit_json = tmp_path / "stage6-persistent-supervision-first-missing-audit.json"
    persistent_prereq_audit_json.write_text(
        json.dumps(
            {
                "kind": "lens.stage6.completion_audit",
                "ok": True,
                "status": "blocked",
                "audit_status": "complete",
                "allow_launch_on_hotkey": True,
                "next_smallest_truthful_gap": "persistent_supervision_required_prerequisites_missing",
                "recommended_handoff_source": (
                    "persistent_supervision_prerequisites_first_missing_requirement_handoff"
                ),
                "recommended_next_slice": "resolve_resident_host_process_before_persistent_supervision_enablement",
                "recommended_proof_script": "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status",
                "authority_required": "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites",
                "authority_granted": False,
                "recommended_handoff": {
                    "id": "resident_host_process",
                    "family": "resident_host",
                    "status": "blocked",
                    "blocker": "resident_host_process_missing",
                    "requirement_state": "missing",
                    "next_smallest_truthful_gap": "resident_host_process_not_supervised",
                    "next_step": "resolve_resident_host_process_before_persistent_supervision_enablement",
                    "proof_script": "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status",
                    "route": "/lens/host",
                    "readiness_route": "/lens/host/runtime-loop/readiness",
                    "authority_required": "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites",
                    "authority_granted": False,
                    "read_only_contract": True,
                    "diagnostic_only": True,
                    "would_execute": False,
                    "would_mutate": False,
                    "would_write_memory": False,
                    "would_decide_approval": False,
                },
            }
        ),
        encoding="utf-8",
    )

    persistent_prereq_proc = _run_proof(
        "-Mode",
        "Status",
        "-CompletionAuditJsonPath",
        str(persistent_prereq_audit_json),
        env=proof_env,
    )

    assert persistent_prereq_proc.returncode == 0, persistent_prereq_proc.stderr or persistent_prereq_proc.stdout
    persistent_prereq_payload = json.loads(persistent_prereq_proc.stdout)
    assert persistent_prereq_payload["recommended_handoff_source"] == (
        "persistent_supervision_prerequisites_first_missing_requirement_handoff"
    )
    assert persistent_prereq_payload["next_smallest_truthful_gap"] == (
        "persistent_supervision_required_prerequisites_missing"
    )
    assert persistent_prereq_payload["recommended_next_slice"] == (
        "resolve_resident_host_process_before_persistent_supervision_enablement"
    )
    assert persistent_prereq_payload["recommended_proof_script"] == (
        "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status"
    )
    assert persistent_prereq_payload["recommended_route"] == "/lens/host"
    assert persistent_prereq_payload["recommended_readiness_route"] == "/lens/host/runtime-loop/readiness"
    assert persistent_prereq_payload["authority_required"] == (
        "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites"
    )
    assert persistent_prereq_payload["authority_granted"] is False
    assert persistent_prereq_payload["stage6_completion_audit_readback_observed"] is True
    assert (
        persistent_prereq_payload[
            "stage6_completion_audit_persistent_supervision_first_missing_requirement_handoff_observed"
        ]
        is True
    )
    assert persistent_prereq_payload["stage6_completion_audit_recommended_handoff_consumed"] is True
    assert persistent_prereq_payload["stage6_completion_audit_runtime_readback_required"] is False
    assert persistent_prereq_payload["recommended_concrete_next_smallest_truthful_gap"] == (
        "resident_host_process_not_supervised"
    )
    persistent_prereq_handoff = persistent_prereq_payload["recommended_handoff"]
    assert persistent_prereq_handoff["id"] == "resident_host_process"
    assert persistent_prereq_handoff["family"] == "resident_host"
    assert persistent_prereq_handoff["next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert persistent_prereq_handoff["next_step"] == (
        "resolve_resident_host_process_before_persistent_supervision_enablement"
    )
    assert persistent_prereq_handoff["proof_script"] == (
        "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status"
    )
    assert persistent_prereq_handoff["route"] == "/lens/host"
    assert persistent_prereq_handoff["readiness_route"] == "/lens/host/runtime-loop/readiness"
    assert persistent_prereq_handoff["authority_granted"] is False
    assert persistent_prereq_handoff["read_only_contract"] is True
    assert persistent_prereq_handoff["diagnostic_only"] is True
    assert persistent_prereq_handoff["would_execute"] is False
    assert persistent_prereq_handoff["would_mutate"] is False
    assert persistent_prereq_payload["recommended_operator_handoff"]["source"] == (
        "stage6_completion_audit_recommended_handoff"
    )
    assert persistent_prereq_payload["recommended_next_operator_action_requirement"] == (
        "stage6_completion_audit_recommended_readback"
    )
    assert persistent_prereq_payload["recommended_next_operator_action"]["id"] == (
        "resolve_resident_host_process_before_persistent_supervision_enablement"
    )
    assert persistent_prereq_payload["recommended_next_operator_action"]["method"] == "LOCAL_SCRIPT"
    assert persistent_prereq_payload["recommended_next_operator_action"]["script_would_execute"] is False
    assert persistent_prereq_payload["recommended_next_operator_action"]["script_would_mutate"] is False
    assert persistent_prereq_payload["recommended_next_operator_command"] == {
        "command": ".\\scripts\\lens-resident-host-runtime-boundary-proof.ps1 -Mode Status",
        "mode": "Status",
        "requires_confirmation": False,
        "requires_explicit_operator_opt_in": False,
        "requires_actor": False,
        "requires_approval_id": False,
        "requires_operator_approval_decision": False,
    }
    persistent_prereq_checks = {item["id"]: item for item in persistent_prereq_payload["checks"]}
    assert persistent_prereq_checks["stage6_completion_audit_runtime_authority_handoff"]["status"] == (
        "completion_audit_recommended_handoff_consumed"
    )

    persistent_prereq_tray_audit_json = tmp_path / "stage6-persistent-supervision-first-missing-tray-audit.json"
    persistent_prereq_tray_audit_json.write_text(
        json.dumps(
            {
                "kind": "lens.stage6.completion_audit",
                "ok": True,
                "status": "blocked",
                "audit_status": "complete",
                "allow_launch_on_hotkey": True,
                "next_smallest_truthful_gap": "persistent_supervision_required_prerequisites_missing",
                "recommended_handoff_source": (
                    "persistent_supervision_prerequisites_first_missing_requirement_handoff"
                ),
                "recommended_next_slice": "resolve_tray_presence_before_persistent_supervision_enablement",
                "recommended_proof_script": "scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status",
                "authority_required": "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites",
                "authority_granted": False,
                "recommended_handoff": {
                    "id": "tray_presence",
                    "family": "tray_presence",
                    "status": "blocked",
                    "blocker": "tray_host_missing",
                    "requirement_state": "missing",
                    "next_smallest_truthful_gap": "summon_tray_presence_blocker_boundary",
                    "next_step": "resolve_tray_presence_before_persistent_supervision_enablement",
                    "proof_script": "scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status",
                    "route": "/lens/tray",
                    "readiness_route": "/lens/tray/readiness",
                    "authority_required": "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites",
                    "authority_granted": False,
                    "read_only_contract": True,
                    "diagnostic_only": True,
                    "would_execute": False,
                    "would_mutate": False,
                    "would_write_memory": False,
                    "would_decide_approval": False,
                },
            }
        ),
        encoding="utf-8",
    )

    persistent_prereq_tray_proc = _run_proof(
        "-Mode",
        "Status",
        "-CompletionAuditJsonPath",
        str(persistent_prereq_tray_audit_json),
        env=proof_env,
    )

    assert persistent_prereq_tray_proc.returncode == 0, (
        persistent_prereq_tray_proc.stderr or persistent_prereq_tray_proc.stdout
    )
    persistent_prereq_tray_payload = json.loads(persistent_prereq_tray_proc.stdout)
    assert persistent_prereq_tray_payload["recommended_handoff_source"] == (
        "persistent_supervision_prerequisites_first_missing_requirement_handoff"
    )
    assert persistent_prereq_tray_payload["next_smallest_truthful_gap"] == (
        "persistent_supervision_required_prerequisites_missing"
    )
    assert persistent_prereq_tray_payload["recommended_next_slice"] == (
        "resolve_tray_presence_before_persistent_supervision_enablement"
    )
    assert persistent_prereq_tray_payload["recommended_proof_script"] == (
        "scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status"
    )
    assert persistent_prereq_tray_payload["recommended_route"] == "/lens/tray"
    assert persistent_prereq_tray_payload["recommended_readiness_route"] == "/lens/tray/readiness"
    assert persistent_prereq_tray_payload["authority_required"] == (
        "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites"
    )
    assert persistent_prereq_tray_payload["authority_granted"] is False
    assert (
        persistent_prereq_tray_payload[
            "stage6_completion_audit_persistent_supervision_first_missing_requirement_handoff_observed"
        ]
        is True
    )
    assert persistent_prereq_tray_payload["stage6_completion_audit_recommended_handoff_consumed"] is True
    assert persistent_prereq_tray_payload["stage6_completion_audit_runtime_readback_required"] is False
    assert persistent_prereq_tray_payload["recommended_concrete_next_smallest_truthful_gap"] == (
        "summon_tray_presence_blocker_boundary"
    )
    persistent_prereq_tray_handoff = persistent_prereq_tray_payload["recommended_handoff"]
    assert persistent_prereq_tray_handoff["id"] == "tray_presence"
    assert persistent_prereq_tray_handoff["family"] == "tray_presence"
    assert persistent_prereq_tray_handoff["next_smallest_truthful_gap"] == "summon_tray_presence_blocker_boundary"
    assert persistent_prereq_tray_handoff["next_step"] == (
        "resolve_tray_presence_before_persistent_supervision_enablement"
    )
    assert persistent_prereq_tray_handoff["proof_script"] == (
        "scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status"
    )
    assert persistent_prereq_tray_handoff["read_only_contract"] is True
    assert persistent_prereq_tray_handoff["diagnostic_only"] is True
    assert persistent_prereq_tray_handoff["would_execute"] is False
    assert persistent_prereq_tray_handoff["would_mutate"] is False
    assert persistent_prereq_tray_payload["recommended_next_operator_action"]["id"] == (
        "resolve_tray_presence_before_persistent_supervision_enablement"
    )
    assert persistent_prereq_tray_payload["recommended_next_operator_command"] == {
        "command": ".\\scripts\\lens-summon-tray-presence-blocker-proof.ps1 -Mode Status",
        "mode": "Status",
        "requires_confirmation": False,
        "requires_explicit_operator_opt_in": False,
        "requires_actor": False,
        "requires_approval_id": False,
        "requires_operator_approval_decision": False,
    }

    persistent_api_audit_json = tmp_path / "stage6-persistent-supervision-api-audit.json"
    persistent_api_audit_json.write_text(
        json.dumps(
            {
                "kind": "lens.stage6.completion_audit",
                "ok": True,
                "status": "blocked",
                "audit_status": "complete",
                "allow_launch_on_hotkey": True,
                "next_smallest_truthful_gap": "persistent_supervision_api_execution_readback",
                "recommended_handoff_source": "stage6_persistent_supervision_api_execution_readback_required",
                "recommended_next_slice": "run_persistent_supervision_api_execution_proof_after_bounded_summon",
                "recommended_proof_script": "scripts/lens-persistent-supervision-api-execution-proof.ps1 -Mode Status",
                "authority_required": "persistent_supervision_execution_authority",
                "authority_granted": False,
                "recommended_handoff": {
                    "status": "proof_readback_required",
                    "previous_next_smallest_truthful_gap": "summon_anywhere_runtime_readback",
                    "consumed_bounded_summon_api_execution_proof": True,
                    "consumed_bounded_summon_next_smallest_truthful_gap": "summon_anywhere_runtime_readback",
                    "next_smallest_truthful_gap": "persistent_supervision_api_execution_readback",
                    "next_step": "run_persistent_supervision_api_execution_proof_after_bounded_summon",
                    "proof_script": "scripts/lens-persistent-supervision-api-execution-proof.ps1 -Mode Status",
                    "route": "/lens/host/persistent-supervision/enablement/execution/apply",
                    "readiness_route": "/lens/host/persistent-supervision/enablement/execution/readiness",
                    "executions_route": "/lens/host/persistent-supervision/enablement/executions",
                    "acceptance_criterion": "summon_anywhere",
                    "authority_required": "persistent_supervision_execution_authority",
                    "authority_granted": False,
                    "summon_runtime_ready": True,
                    "bounded_handoff_ready": True,
                    "local_open_ready": True,
                    "opened": False,
                    "no_launch": True,
                    "persistent_supervision_api_execution_proof_observed": False,
                    "read_only_contract": False,
                    "diagnostic_only": True,
                    "would_execute": True,
                    "would_mutate": True,
                    "would_write_service_config": True,
                    "would_write_receipt": True,
                    "would_start_service": False,
                    "would_write_memory": False,
                    "would_claim_resident": False,
                    "blockers": [
                        "persistent_supervision_required_prerequisites_missing",
                        "resident_claim_authority_not_granted",
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    persistent_api_proc = _run_proof(
        "-Mode",
        "Status",
        "-CompletionAuditJsonPath",
        str(persistent_api_audit_json),
        env=proof_env,
    )

    assert persistent_api_proc.returncode == 0, persistent_api_proc.stderr or persistent_api_proc.stdout
    persistent_api_payload = json.loads(persistent_api_proc.stdout)
    assert persistent_api_payload["recommended_handoff_source"] == (
        "stage6_persistent_supervision_api_execution_readback_required"
    )
    assert persistent_api_payload["next_smallest_truthful_gap"] == "persistent_supervision_api_execution_readback"
    assert persistent_api_payload["recommended_next_slice"] == (
        "run_persistent_supervision_api_execution_proof_after_bounded_summon"
    )
    assert persistent_api_payload["recommended_proof_script"] == (
        "scripts/lens-persistent-supervision-api-execution-proof.ps1 -Mode Status"
    )
    assert persistent_api_payload["authority_required"] == "persistent_supervision_execution_authority"
    assert persistent_api_payload["authority_granted"] is False
    assert persistent_api_payload["stage6_completion_audit_readback_observed"] is True
    assert persistent_api_payload["stage6_completion_audit_recommended_handoff_consumed"] is True
    assert (
        persistent_api_payload["stage6_completion_audit_persistent_supervision_api_execution_handoff_observed"] is True
    )
    assert persistent_api_payload["stage6_completion_audit_runtime_readback_required"] is False
    persistent_api_handoff = persistent_api_payload["recommended_handoff"]
    assert persistent_api_handoff["status"] == "proof_readback_required"
    assert persistent_api_handoff["would_execute"] is True
    assert persistent_api_handoff["would_mutate"] is True
    assert persistent_api_handoff["would_write_service_config"] is True
    assert persistent_api_handoff["would_write_receipt"] is True
    assert persistent_api_handoff["would_start_service"] is False
    assert persistent_api_handoff["would_write_memory"] is False
    assert persistent_api_handoff["would_claim_resident"] is False
    assert persistent_api_payload["recommended_operator_handoff"]["source"] == (
        "stage6_completion_audit_recommended_handoff"
    )
    assert persistent_api_payload["recommended_operator_handoff"]["read_only_contract"] is False
    assert persistent_api_payload["recommended_operator_handoff"]["diagnostic_only"] is True
    assert persistent_api_payload["recommended_operator_handoff"]["would_execute"] is True
    assert persistent_api_payload["recommended_operator_handoff"]["would_mutate"] is True
    assert persistent_api_payload["recommended_next_operator_action_requirement"] == (
        "stage6_completion_audit_recommended_readback"
    )
    assert persistent_api_payload["recommended_next_operator_action"]["id"] == (
        "run_persistent_supervision_api_execution_proof_after_bounded_summon"
    )
    assert persistent_api_payload["recommended_next_operator_action"]["script_would_execute"] is True
    assert persistent_api_payload["recommended_next_operator_action"]["script_would_mutate"] is True
    assert persistent_api_payload["recommended_next_operator_action"]["script_would_write_service_config"] is True
    assert persistent_api_payload["recommended_next_operator_action"]["script_would_write_receipt"] is True
    assert persistent_api_payload["recommended_next_operator_action"]["script_would_start_service"] is False
    assert persistent_api_payload["recommended_next_operator_action"]["script_would_write_memory"] is False
    assert persistent_api_payload["recommended_next_operator_action"]["script_would_claim_resident"] is False
    assert persistent_api_payload["recommended_next_operator_command"] == {
        "command": ".\\scripts\\lens-persistent-supervision-api-execution-proof.ps1 -Mode Status",
        "mode": "Status",
        "requires_confirmation": False,
        "requires_explicit_operator_opt_in": True,
        "requires_actor": False,
        "requires_approval_id": False,
        "requires_operator_approval_decision": False,
    }
    persistent_api_checks = {item["id"]: item for item in persistent_api_payload["checks"]}
    assert persistent_api_checks["stage6_completion_audit_runtime_authority_handoff"]["status"] == (
        "completion_audit_recommended_handoff_consumed"
    )

    audit_json = tmp_path / "stage6-completion-audit.json"
    audit_json.write_text(
        json.dumps(
            {
                "kind": "lens.stage6.completion_audit",
                "ok": True,
                "status": "blocked",
                "audit_status": "complete",
                "allow_launch_on_hotkey": True,
                "next_smallest_truthful_gap": "resident_surface_runtime_not_supervised",
                "recommended_handoff_source": "stage6_helpful_not_noisy_runtime_authority_readiness_handoff",
                "recommended_next_slice": "create_or_select_exact_approved_resident_runtime_execution_authority_request",
                "recommended_proof_script": "scripts/lens-stage6-checkpoint.ps1 -Mode Status",
                "authority_required": "operator_approval",
                "authority_granted": False,
                "recommended_handoff": {
                    "status": "authority_readiness_handoff_ready",
                    "next_smallest_truthful_gap": "resident_surface_runtime_not_supervised",
                    "next_step": "create_or_select_exact_approved_resident_runtime_execution_authority_request",
                    "proof_script": "scripts/lens-stage6-checkpoint.ps1 -Mode Status",
                    "route": "/lens/resident-runtime/authority-grant/readiness",
                    "readiness_route": "/lens/resident-runtime/authority-grant/readiness",
                    "authority_required": "operator_approval",
                    "authority_granted": False,
                    "consumed_resident_surface_foreground_runtime_proof": True,
                    "resident_runtime_authority_grant_readiness_observed": True,
                    "read_only_contract": True,
                    "diagnostic_only": True,
                    "would_execute": False,
                    "would_mutate": False,
                },
            }
        ),
        encoding="utf-8",
    )

    consumed_proc = _run_proof(
        "-Mode",
        "Status",
        "-CompletionAuditJsonPath",
        str(audit_json),
        env=proof_env,
    )

    assert consumed_proc.returncode == 0, consumed_proc.stderr or consumed_proc.stdout
    consumed_payload = json.loads(consumed_proc.stdout)
    assert consumed_payload["recommended_handoff_source"] == (
        "stage6_helpful_not_noisy_runtime_authority_readiness_handoff"
    )
    assert consumed_payload["next_smallest_truthful_gap"] == "resident_surface_runtime_not_supervised"
    assert consumed_payload["recommended_next_slice"] == (
        "create_or_select_exact_approved_resident_runtime_execution_authority_request"
    )
    assert consumed_payload["recommended_proof_script"] == "scripts/lens-stage6-checkpoint.ps1 -Mode Status"
    assert consumed_payload["authority_required"] == "operator_approval"
    assert consumed_payload["stage6_completion_audit_readback_observed"] is True
    assert consumed_payload["stage6_completion_audit_recommended_handoff_consumed"] is True
    assert consumed_payload["stage6_completion_audit_runtime_readback_required"] is False
    assert consumed_payload["recommended_handoff"]["status"] == "authority_readiness_handoff_ready"
    assert consumed_payload["recommended_operator_handoff"]["source"] == "resident_runtime_authority_readiness_handoff"
    assert consumed_payload["recommended_next_operator_action_requirement"] == (
        "exact_resident_runtime_execution_authority_approval"
    )
    assert consumed_payload["recommended_next_operator_action"]["id"] == (
        "request_resident_runtime_execution_authority"
    )
    assert consumed_payload["recommended_next_operator_action"]["route"] == (
        "/lens/resident-runtime/authority-grant/request"
    )
    assert consumed_payload["recommended_next_operator_action"]["approval_action"] == (
        "lens.resident_runtime.execution_authority"
    )
    assert consumed_payload["recommended_next_operator_action"]["script_would_request_authority"] is True
    assert consumed_payload["recommended_next_operator_action"]["script_would_grant_authority"] is False
    assert consumed_payload["recommended_next_operator_action"]["script_would_decide_approval"] is False
    resident_runtime_request_command = (
        "$body = @{ actor = '<actor>'; reason = '<reason>' } | ConvertTo-Json -Compress; "
        "Invoke-RestMethod -Method Post -Uri "
        "'http://127.0.0.1:8000/lens/resident-runtime/authority-grant/request' "
        "-ContentType 'application/json' -Body $body"
    )
    assert consumed_payload["recommended_next_operator_action"]["approval_request_command"] == {
        "command": resident_runtime_request_command,
        "route": "/lens/resident-runtime/authority-grant/request",
        "method": "POST",
        "api_base_url": "http://127.0.0.1:8000",
        "payload_shape": {
            "actor": "<actor>",
            "reason": "<reason>",
        },
        "required_scope": "system.write",
        "requires_running_api": True,
        "requires_operator_actor": True,
        "would_request_approval_if_run": True,
        "status_readback_would_request_approval": False,
    }
    assert consumed_payload["recommended_next_operator_command"] == {
        "command": resident_runtime_request_command,
        "mode": "ApiRequest",
        "route": "/lens/resident-runtime/authority-grant/request",
        "method": "POST",
        "requires_confirmation": True,
        "requires_explicit_operator_opt_in": True,
        "requires_actor": True,
        "requires_approval_id": False,
        "requires_operator_approval_decision": False,
    }
    assert consumed_payload["recommended_next_operator_actor_scope_readiness"]["required_scope"] == "system.write"
    assert consumed_payload["recommended_next_operator_actor_scope_readiness"]["operator_must_supply_actor"] is True
    consumed_checks = {item["id"]: item for item in consumed_payload["checks"]}
    assert consumed_checks["stage6_completion_audit_runtime_authority_handoff"]["status"] == (
        "runtime_authority_handoff_consumed"
    )

    approved_approval_id = "approved-runtime-authority-test"
    write_json(
        data_root / "approvals" / "approved" / f"{approved_approval_id}.json",
        {
            "id": approved_approval_id,
            "ts": created_ts,
            "action": "lens.resident_runtime.execution_authority",
            "reason": "test approved resident runtime authority",
            "payload": {
                "actor": "test.system.write",
                "route": "/lens/resident-runtime/authority-grant/request",
            },
            "status": "approved",
            "decision": "approve",
            "decision_actor": "test.approvals.decision",
            "decided_ts": created_ts,
        },
    )

    approved_proc = _run_proof(
        "-Mode",
        "Status",
        "-CompletionAuditJsonPath",
        str(audit_json),
        env=proof_env,
    )

    assert approved_proc.returncode == 0, approved_proc.stderr or approved_proc.stdout
    approved_payload = json.loads(approved_proc.stdout)
    assert approved_payload["stage6_completion_audit_recommended_handoff_consumed"] is True
    assert approved_payload["recommended_operator_handoff"]["source"] == "resident_runtime_authority_readiness_handoff"
    assert approved_payload["recommended_operator_handoff"]["status"] == "approved_authority_request_selected"
    assert approved_payload["recommended_next_slice"] == (
        "create_or_select_exact_approved_resident_runtime_execution_authority_request"
    )
    assert approved_payload["recommended_next_operator_action_requirement"] == (
        "exact_resident_runtime_execution_authority_approval"
    )
    assert approved_payload["recommended_next_operator_action"]["id"] == (
        "select_exact_approved_resident_runtime_execution_authority_request"
    )
    assert approved_payload["recommended_next_operator_action"]["route"] == (
        "/lens/resident-runtime/authority-grant/requests"
    )
    assert approved_payload["recommended_next_operator_action"]["method"] == "GET"
    assert approved_payload["recommended_next_operator_action"]["approved_approval_id"] == approved_approval_id
    assert approved_payload["recommended_next_operator_action"]["script_would_request_authority"] is False
    assert approved_payload["recommended_next_operator_action"]["script_would_grant_authority"] is False
    assert approved_payload["recommended_next_operator_action"]["script_would_decide_approval"] is False
    resident_runtime_grant_command = (
        f"$body = @{{ approval_id = '{approved_approval_id}'; actor = '<actor>'; "
        "reason = '<reason>'; lease_seconds = 3600 } | ConvertTo-Json -Compress; "
        "Invoke-RestMethod -Method Post -Uri "
        "'http://127.0.0.1:8000/lens/resident-runtime/authority-grant' "
        "-ContentType 'application/json' -Body $body"
    )
    assert approved_payload["recommended_next_operator_action"]["follow_up_authority_grant_command"] == {
        "command": resident_runtime_grant_command,
        "route": "/lens/resident-runtime/authority-grant",
        "method": "POST",
        "api_base_url": "http://127.0.0.1:8000",
        "payload_shape": {
            "approval_id": approved_approval_id,
            "actor": "<actor>",
            "reason": "<reason>",
            "lease_seconds": 3600,
        },
        "required_scope": "system.write",
        "requires_running_api": True,
        "requires_operator_actor": True,
        "requires_approval_id": True,
        "would_grant_authority_if_run": True,
        "status_readback_would_grant_authority": False,
        "preview_only": True,
        "availability_reason": "approved_request_selected_but_authority_grant_is_separate_operator_step",
    }
    approved_readback_command = (
        f".\\scripts\\lens-stage6-next-handoff.ps1 -Mode Status -CompletionAuditJsonPath '{audit_json.resolve()}'"
    )
    assert approved_payload["recommended_next_operator_command"] == {
        "command": approved_readback_command,
        "mode": "Status",
        "route": "/lens/resident-runtime/authority-grant/requests",
        "method": "GET",
        "requires_confirmation": False,
        "requires_explicit_operator_opt_in": False,
        "requires_actor": False,
        "requires_approval_id": False,
        "requires_operator_approval_decision": False,
    }
    assert approved_payload["recommended_next_operator_actor_scope_readiness"]["required_scope"] == ""
    assert approved_payload["recommended_next_operator_actor_scope_readiness"]["operator_must_supply_actor"] is False
    assert approved_payload["recommended_operator_handoff"]["approval_request_write_if_run"] is False
    assert approved_payload["recommended_operator_handoff"]["authority_grant_receipt_write_if_run"] is False
    assert approved_payload["recommended_operator_handoff"]["approval_decision_authority"] is False
    approved_checks = {item["id"]: item for item in approved_payload["checks"]}
    assert approved_checks["stage6_completion_audit_runtime_authority_handoff"]["status"] == (
        "runtime_authority_handoff_consumed"
    )

    active_grant_receipt_id = "active-runtime-authority-grant-test"
    write_json(
        data_root / "lens" / "resident_runtime_authority_grants" / f"{active_grant_receipt_id}.json",
        {
            "id": active_grant_receipt_id,
            "receipt_id": active_grant_receipt_id,
            "kind": "lens.resident_runtime.execution_authority_grant.grant.receipt",
            "status": "authority_granted",
            "route": "/lens/resident-runtime/authority-grant",
            "method": "POST",
            "approval_id": approved_approval_id,
            "actor": "test.system.write",
            "created_ts": created_ts,
            "expires_ts": created_ts + 3600,
            "lease": {
                "active": True,
                "lease_seconds": 3600,
                "created_ts": created_ts,
                "expires_ts": created_ts + 3600,
            },
            "authority_grant": {
                "authority_granted": True,
                "resident_runtime_execution_authority": True,
            },
            "governance": {
                "resident_runtime_execution_authority": True,
                "authority_granted": True,
            },
        },
    )

    active_grant_proc = _run_proof(
        "-Mode",
        "Status",
        "-CompletionAuditJsonPath",
        str(audit_json),
        env=proof_env,
    )

    assert active_grant_proc.returncode == 0, active_grant_proc.stderr or active_grant_proc.stdout
    active_grant_payload = json.loads(active_grant_proc.stdout)
    assert active_grant_payload["recommended_next_slice"] == (
        "review_resident_runtime_execution_authority_grant_receipt"
    )
    assert active_grant_payload["authority_required"] == "none_readback_only"
    assert active_grant_payload["authority_granted"] is True
    assert active_grant_payload["recommended_operator_handoff"]["status"] == "authority_grant_receipt_already_active"
    assert active_grant_payload["recommended_next_operator_action_requirement"] == (
        "resident_runtime_execution_authority_grant_receipt"
    )
    assert active_grant_payload["recommended_next_operator_action"]["id"] == (
        "review_resident_runtime_execution_authority_grant_receipt"
    )
    assert active_grant_payload["recommended_next_operator_action"]["latest_receipt_id"] == active_grant_receipt_id
    active_grant_readback_command = (
        f".\\scripts\\lens-stage6-next-handoff.ps1 -Mode Status -CompletionAuditJsonPath '{audit_json.resolve()}'"
    )
    assert active_grant_payload["recommended_next_operator_command"] == {
        "command": active_grant_readback_command,
        "mode": "Status",
        "requires_confirmation": False,
        "requires_explicit_operator_opt_in": False,
        "requires_actor": False,
        "requires_approval_id": False,
        "requires_operator_approval_decision": False,
    }
    assert active_grant_payload["recommended_operator_handoff"]["read_only_status_command"] == (
        active_grant_readback_command
    )
    assert active_grant_payload["recommended_operator_handoff"]["authority_grant_receipt_write_if_run"] is False
