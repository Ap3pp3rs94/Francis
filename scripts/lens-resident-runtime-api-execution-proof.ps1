[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(1, 15)]
  [int]$RunSeconds = 1,

  [string]$DataDir = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

function Get-PythonPath {
  $Python = Get-Command python -ErrorAction SilentlyContinue
  if ($null -ne $Python) {
    return [string]$Python.Source
  }
  $Py = Get-Command py -ErrorAction SilentlyContinue
  if ($null -ne $Py) {
    return [string]$Py.Source
  }
  return ''
}

if ([string]::IsNullOrWhiteSpace($DataDir)) {
  $DataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-resident-runtime-api-execution-proof\" + [guid]::NewGuid().ToString('N') + "\data")
}

$ProofDataRoot = [System.IO.Path]::GetFullPath($DataDir)
$PythonPath = Get-PythonPath
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
  [ordered]@{
    ok = $false
    kind = 'lens.resident_runtime.api_execution.proof'
    status = 'proof_failed'
    mode = $Mode.ToLowerInvariant()
    repo_root = $RepoRoot
    data_root = $ProofDataRoot
    error = 'python_unavailable'
  } | ConvertTo-Json -Depth 5
  exit 1
}

$Source = @'
from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _check(check_id: str, status: str, passed: bool, evidence: str, reason: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": status,
        "passed": passed,
        "evidence": evidence,
        "reason": reason,
    }


def _post(client: Any, route: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(route, json=payload)
    body = response.json()
    if response.status_code != 200:
        raise RuntimeError(f"{route} returned {response.status_code}: {body!r}")
    return body


def _get(client: Any, route: str) -> dict[str, Any]:
    response = client.get(route)
    body = response.json()
    if response.status_code != 200:
        raise RuntimeError(f"{route} returned {response.status_code}: {body!r}")
    return body


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return _as_dict(json.loads(path.read_text(encoding="utf-8-sig")))


def _stop_resident(client: Any, *, approval_id: str, actor: str, reason: str) -> dict[str, Any]:
    if not approval_id:
        return {
            "ok": False,
            "status": "stop_skipped_no_host_approval_id",
            "resident_host_process": True,
            "resident_supervised_runtime": True,
        }
    return _post(
        client,
        "/lens/host/supervision/execute",
        {
            "approval_id": approval_id,
            "actor": actor,
            "reason": reason,
            "mode": "resident_stop",
            "run_seconds": 1,
        },
    )


def _criterion(body: dict[str, Any], criterion_id: str) -> dict[str, Any]:
    readiness = _as_dict(body.get("stage6_readiness"))
    for item in _as_list(readiness.get("criteria")):
        if isinstance(item, dict) and item.get("id") == criterion_id:
            return item
    return {}


def _run() -> tuple[int, dict[str, Any]]:
    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.world_state.operator_mode import set_control_mode

    repo_root = Path(os.environ["FRANCIS_ROOT"]).resolve()
    data_root = Path(os.environ["FRANCIS_DATA_DIR"]).resolve()
    run_seconds = int(os.environ.get("FRANCIS_PROOF_RUN_SECONDS", "1"))
    data_root.mkdir(parents=True, exist_ok=True)

    actor = "test.system.write"
    set_control_mode(
        "assist",
        reason="prove Lens resident runtime API execution path",
        actor=actor,
    )

    client = TestClient(create_app())
    host_approval_id = ""
    stop_execution: dict[str, Any] = {}
    fallback_stop: dict[str, Any] = {}
    try:
        host_request = _post(
            client,
            "/lens/host/supervision/authority/request",
            {
                "actor": actor,
                "reason": "operator wants host supervision authority before API execution proof",
            },
        )
        host_approval_id = str(host_request["approval_id"])
        host_decision = _post(
            client,
            "/approvals/decision",
            {
                "id": host_approval_id,
                "action": "approve",
                "actor": "test.approvals.decision",
                "comment": "approve only host supervision authority for isolated API proof",
            },
        )
        host_grant = _post(
            client,
            "/lens/host/supervision/authority",
            {
                "approval_id": host_approval_id,
                "actor": actor,
                "reason": "grant bounded host supervision authority for isolated API proof",
                "lease_seconds": 600,
            },
        )
        host_receipt = _as_dict(host_grant.get("receipt"))

        runtime_request = _post(
            client,
            "/lens/resident-runtime/authority-grant/request",
            {
                "actor": actor,
                "reason": "operator wants resident runtime execution authority for API proof",
            },
        )
        runtime_approval_id = str(runtime_request["approval_id"])
        runtime_decision = _post(
            client,
            "/approvals/decision",
            {
                "id": runtime_approval_id,
                "action": "approve",
                "actor": "test.approvals.decision",
                "comment": "approve only resident runtime execution authority for isolated API proof",
            },
        )
        runtime_grant = _post(
            client,
            "/lens/resident-runtime/authority-grant",
            {
                "approval_id": runtime_approval_id,
                "actor": actor,
                "reason": "grant bounded resident runtime execution authority for isolated API proof",
                "lease_seconds": 600,
            },
        )
        runtime_receipt = _as_dict(runtime_grant.get("receipt"))

        plan = _get(
            client,
            f"/lens/resident-runtime/plan?approval_id={runtime_approval_id}&actor={actor}",
        )
        executed = _post(
            client,
            "/lens/resident-runtime/execute",
            {
                "approval_id": runtime_approval_id,
                "actor": actor,
                "reason": "prove governed API path starts a supervised resident host lease",
                "run_seconds": run_seconds,
            },
        )
        executions_after_start = _get(client, "/lens/resident-runtime/executions?limit=10")

        runtime_status_path = data_root / "runtime" / "lens-host" / "status.json"
        runtime_pid_path = data_root / "runtime" / "lens-host" / "lens-host.pid"
        supervisor_status_path = data_root / "runtime" / "lens-host-supervisor" / "status.json"
        host_state_after_start = _read_json(runtime_status_path)
        supervisor_state_after_start = _read_json(supervisor_status_path)
        pid_file_present_after_start = runtime_pid_path.is_file()

        stop_execution = _stop_resident(
            client,
            approval_id=host_approval_id,
            actor=actor,
            reason="stop supervised resident host lease after isolated API proof",
        )
        stopped_host_state = _read_json(runtime_status_path)
        stopped_supervisor_state = _read_json(supervisor_status_path)
        pid_file_present_after_stop = runtime_pid_path.is_file()

        lens_status = _get(client, "/lens/status?limit=10")
        status_execution_criterion = _criterion(lens_status, "resident_runtime_execution_receipt_readback")

        execution_governance = _as_dict(executed.get("governance"))
        stop_governance = _as_dict(stop_execution.get("governance"))
        host_execution = _as_dict(executed.get("host_supervision_execution"))
        host_execution_runner = _as_dict(host_execution.get("runner"))
        host_runner_payload = _as_dict(host_execution_runner.get("runner"))
        start_runtime_observed = (
            executed.get("status") == "resident_supervision_started"
            and executed.get("executed") is True
            and executed.get("resident_host_process") is True
            and executed.get("resident_supervised_runtime") is True
            and host_execution.get("status") == "resident_supervision_started"
            and host_runner_payload.get("status") == "resident_supervision_started"
            and host_state_after_start.get("status") == "resident_running"
            and supervisor_state_after_start.get("status") == "resident_supervising"
            and pid_file_present_after_start
        )
        stop_observed = (
            stop_execution.get("status") == "resident_supervision_stopped"
            and stop_execution.get("executed") is True
            and stop_execution.get("resident_host_process") is False
            and stop_execution.get("resident_supervised_runtime") is False
            and stopped_host_state.get("status") == "resident_stopped"
            and stopped_supervisor_state.get("status") == "resident_supervision_stopped"
            and not pid_file_present_after_stop
        )
        authority_boundaries_intact = (
            execution_governance.get("resident_runtime_execution_authority") is True
            and execution_governance.get("local_process_launch_authority") is True
            and execution_governance.get("process_supervision_authority") is True
            and execution_governance.get("service_install_authority") is False
            and execution_governance.get("service_control_authority") is False
            and execution_governance.get("tray_registration_authority") is False
            and execution_governance.get("hotkey_registration_authority") is False
            and execution_governance.get("overlay_control_authority") is False
            and execution_governance.get("summon_authority") is False
            and execution_governance.get("memory_write") is False
            and execution_governance.get("resident_claim_authority") is False
            and stop_governance.get("memory_write") is False
            and stop_governance.get("resident_claim_authority") is False
        )
        surface_claims_false = (
            executed.get("resident_claim_allowed") is False
            and host_runner_payload.get("resident_claim_allowed") is False
            and host_runner_payload.get("service_managed") is False
            and host_runner_payload.get("tray_presence") is False
            and host_runner_payload.get("global_hotkey") is False
            and host_runner_payload.get("overlay_window") is False
            and host_runner_payload.get("summon_anywhere") is False
        )

        checks = [
            _check(
                "host_supervision_authority_granted",
                str(host_grant.get("status")),
                host_decision.get("status") == "approved"
                and host_grant.get("status") == "authority_granted"
                and bool(host_receipt.get("receipt_id")),
                "/lens/host/supervision/authority",
                "The proof must start from an exact approved host supervision authority grant.",
            ),
            _check(
                "resident_runtime_authority_granted",
                str(runtime_grant.get("status")),
                runtime_decision.get("status") == "approved"
                and runtime_grant.get("status") == "authority_granted"
                and bool(runtime_receipt.get("receipt_id")),
                "/lens/resident-runtime/authority-grant",
                "The runtime execute route requires a distinct resident runtime execution authority grant.",
            ),
            _check(
                "runtime_plan_ready_for_bounded_candidate",
                "ready" if plan.get("bounded_resident_candidate_ready") is True else "blocked",
                plan.get("bounded_resident_candidate_ready") is True
                and plan.get("host_supervision_authority") is True
                and plan.get("process_supervision_authority") is True
                and plan.get("process_restart_authority") is True,
                "/lens/resident-runtime/plan",
                "The governed plan must read both authority grants before execution.",
            ),
            _check(
                "api_execute_started_real_resident_supervision",
                str(executed.get("status")),
                start_runtime_observed,
                "/lens/resident-runtime/execute",
                "The API route must drive the real StartResident supervisor path in the isolated data root.",
            ),
            _check(
                "runtime_receipt_readback_after_start",
                str(executions_after_start.get("status")),
                executions_after_start.get("resident_supervised_runtime_receipt_observed") is True
                and executions_after_start.get("latest_supervision_mode") == "resident_start"
                and executions_after_start.get("latest_next_smallest_truthful_gap")
                == "summon_tray_presence_blocker_boundary",
                "/lens/resident-runtime/executions",
                "The resident runtime readback must preserve the started-supervisor receipt.",
            ),
            _check(
                "api_stop_cleaned_real_resident_supervision",
                str(stop_execution.get("status")),
                stop_observed,
                "/lens/host/supervision/execute",
                "The proof must stop the live resident supervisor and remove the pid file before returning.",
            ),
            _check(
                "status_receipt_readback_observed",
                str(status_execution_criterion.get("status")),
                status_execution_criterion.get("receipt_count", 0) >= 1,
                "/lens/status",
                "Lens status must expose resident runtime execution receipt readback.",
            ),
            _check(
                "authority_boundaries_intact",
                "bounded" if authority_boundaries_intact else "leaked",
                authority_boundaries_intact,
                "response.governance",
                "The route may start and stop a bounded resident supervisor but must not gain tray, hotkey, overlay, summon, service, memory, or resident-claim authority.",
            ),
            _check(
                "surface_claims_false",
                "bounded" if surface_claims_false else "overclaimed",
                surface_claims_false,
                "response.resident_surface_claims",
                "The proof must not claim tray presence, global hotkey, overlay, summon-anywhere, service management, or resident identity.",
            ),
        ]
        proof_passed = all(item["passed"] for item in checks)
        start_blockers = list(dict.fromkeys(str(item) for item in _as_list(executed.get("blockers")) if str(item)))
        payload = {
            "ok": proof_passed,
            "kind": "lens.resident_runtime.api_execution.proof",
            "status": "proof_passed" if proof_passed else "proof_failed",
            "mode": os.environ.get("FRANCIS_PROOF_MODE", "status"),
            "repo_root": str(repo_root),
            "data_root": str(data_root),
            "stage": "Stage 6 / Lens MVP",
            "stage_state": "active",
            "acceptance_criterion": "summon_anywhere",
            "previous_next_smallest_truthful_gap": "resident_host_process_not_supervised",
            "next_smallest_truthful_gap": str(
                executed.get("next_smallest_truthful_gap") or "summon_tray_presence_blocker_boundary"
            ),
            "recommended_next_slice": "consume_tray_presence_runtime_boundary_after_api_resident_supervision",
            "recommended_proof_script": "scripts/lens-tray-plan-consumption-proof.ps1 -Mode Status",
            "recommended_handoff_source": "api_resident_runtime_execution_tray_presence_handoff",
            "recommended_handoff": {
                "id": "tray_presence",
                "status": "blocked",
                "previous_next_smallest_truthful_gap": "resident_host_process_not_supervised",
                "next_smallest_truthful_gap": "summon_tray_presence_blocker_boundary",
                "next_step": "consume_tray_presence_runtime_boundary_after_api_resident_supervision",
                "proof_script": "scripts/lens-tray-plan-consumption-proof.ps1 -Mode Status",
                "route": "/lens/tray",
                "readiness_route": "/lens/tray/readiness",
                "authority_required": "tray_registration_authority",
                "authority_granted": False,
                "read_only_contract": True,
                "diagnostic_only": True,
                "would_execute": False,
                "would_mutate": False,
            },
            "host_supervision_approval_id": host_approval_id,
            "resident_runtime_approval_id": runtime_approval_id,
            "host_supervision_authority_grant_receipt_id": str(host_receipt.get("receipt_id") or ""),
            "resident_runtime_authority_grant_receipt_id": str(runtime_receipt.get("receipt_id") or ""),
            "resident_runtime_execution_authority": runtime_grant.get("authority_granted") is True,
            "host_supervision_authority": host_grant.get("authority_granted") is True,
            "resident_runtime_plan_ready": plan.get("bounded_resident_candidate_ready") is True,
            "execution_applied": executed.get("applied") is True,
            "executed": executed.get("executed") is True,
            "resident_host_process_started": executed.get("resident_host_process") is True,
            "resident_supervised_runtime_started": executed.get("resident_supervised_runtime") is True,
            "resident_supervision_stop_observed": stop_observed,
            "resident_host_process_after_stop": stop_execution.get("resident_host_process") is True,
            "resident_supervised_runtime_after_stop": stop_execution.get("resident_supervised_runtime") is True,
            "pid_file_present_after_start": pid_file_present_after_start,
            "pid_file_present_after_stop": pid_file_present_after_stop,
            "tray_presence": False,
            "global_hotkey": False,
            "overlay_window": False,
            "summon_anywhere": False,
            "service_managed": False,
            "resident_claim_allowed": False,
            "checks": checks,
            "blockers": start_blockers,
            "proof": {
                "start_status": str(executed.get("status")),
                "host_supervision_execution_status": str(host_execution.get("status")),
                "runner_status": str(host_runner_payload.get("status")),
                "host_state_after_start": str(host_state_after_start.get("status") or ""),
                "supervisor_state_after_start": str(supervisor_state_after_start.get("status") or ""),
                "stop_status": str(stop_execution.get("status") or ""),
                "host_state_after_stop": str(stopped_host_state.get("status") or ""),
                "supervisor_state_after_stop": str(stopped_supervisor_state.get("status") or ""),
                "receipt_readback_status": str(executions_after_start.get("status") or ""),
                "receipt_readback_next_gap": str(executions_after_start.get("latest_next_smallest_truthful_gap") or ""),
                "status_receipt_readback_status": str(status_execution_criterion.get("status") or ""),
                "status_receipt_count": int(status_execution_criterion.get("receipt_count") or 0),
            },
            "start_execution": {
                "status": executed.get("status"),
                "next_smallest_truthful_gap": executed.get("next_smallest_truthful_gap"),
                "resident_host_process": executed.get("resident_host_process"),
                "resident_supervised_runtime": executed.get("resident_supervised_runtime"),
                "resident_claim_allowed": executed.get("resident_claim_allowed"),
                "stop_command": executed.get("stop_command"),
            },
            "stop_execution": {
                "status": stop_execution.get("status"),
                "resident_host_process": stop_execution.get("resident_host_process"),
                "resident_supervised_runtime": stop_execution.get("resident_supervised_runtime"),
                "resident_claim_allowed": stop_execution.get("resident_claim_allowed"),
            },
            "governance": {
                "diagnostic_only": True,
                "api_route_proof": True,
                "api_execution_authority": True,
                "approval_request_write": True,
                "test_fixture_approval_decisions": True,
                "approval_decision_authority": False,
                "product_execution_authority": False,
                "execution_authority": True,
                "temporary_runtime_state_write": True,
                "local_process_launch_authority": True,
                "process_supervision_authority": True,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "summon_authority": False,
                "capture_authority": False,
                "new_sensing_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
                "mutation_authority_granted": True,
            },
            "message": (
                "The governed API path can start and stop a supervised resident host lease in an isolated data root. "
                "The proof still stops before tray presence, global hotkey, overlay window, summon-anywhere, memory writes, "
                "service management, and resident-claim authority."
            ),
        }
        return (0 if proof_passed else 1), payload
    finally:
        if not (
            stop_execution.get("status") == "resident_supervision_stopped"
            and stop_execution.get("resident_host_process") is False
            and stop_execution.get("resident_supervised_runtime") is False
        ):
            try:
                fallback_stop = _stop_resident(
                    client,
                    approval_id=host_approval_id,
                    actor=actor,
                    reason="fallback cleanup for resident runtime API execution proof",
                )
            except Exception as exc:
                fallback_stop = {
                    "ok": False,
                    "status": "fallback_stop_failed",
                    "error": str(exc),
                }
            if fallback_stop.get("status") == "fallback_stop_failed":
                raise RuntimeError(f"resident runtime cleanup failed: {fallback_stop!r}")


try:
    exit_code, payload = _run()
except Exception as exc:
    exit_code = 1
    payload = {
        "ok": False,
        "kind": "lens.resident_runtime.api_execution.proof",
        "status": "proof_failed",
        "error": str(exc),
        "traceback": traceback.format_exc(),
    }

print(json.dumps(payload))
sys.exit(exit_code)
'@

$PreviousRoot = [string]$env:FRANCIS_ROOT
$PreviousDataDir = [string]$env:FRANCIS_DATA_DIR
$PreviousProfile = [string]$env:FRANCIS_ENV_PROFILE
$PreviousRunMode = [string]$env:FRANCIS_RUN_MODE
$PreviousProofMode = [string]$env:FRANCIS_PROOF_MODE
$PreviousProofRunSeconds = [string]$env:FRANCIS_PROOF_RUN_SECONDS
$PreviousActorScopes = [string]$env:FRANCIS_API_ACTOR_SCOPES
$PreviousPythonPath = [string]$env:PYTHONPATH

try {
  $env:FRANCIS_ROOT = $RepoRoot
  $env:FRANCIS_DATA_DIR = $ProofDataRoot
  $env:FRANCIS_ENV_PROFILE = 'dev'
  $env:FRANCIS_RUN_MODE = 'api'
  $env:FRANCIS_PROOF_MODE = $Mode.ToLowerInvariant()
  $env:FRANCIS_PROOF_RUN_SECONDS = [string]$RunSeconds
  $env:FRANCIS_API_ACTOR_SCOPES = '{"test.system.write":["system.write"],"test.approvals.decision":["approvals.decide"]}'
  $SourceRoot = Join-Path $RepoRoot 'src'
  if ([string]::IsNullOrWhiteSpace($PreviousPythonPath)) {
    $env:PYTHONPATH = $SourceRoot
  } else {
    $env:PYTHONPATH = $SourceRoot + [System.IO.Path]::PathSeparator + $PreviousPythonPath
  }
  $ProofRuntimeDir = Join-Path $ProofDataRoot 'runtime\lens-resident-runtime-api-execution-proof'
  New-Item -ItemType Directory -Force -Path $ProofRuntimeDir | Out-Null
  $PythonScriptPath = Join-Path $ProofRuntimeDir 'proof.py'
  Set-Content -LiteralPath $PythonScriptPath -Value $Source -Encoding UTF8
  $Output = & $PythonPath $PythonScriptPath 2>&1
  $ExitCode = $LASTEXITCODE
} finally {
  & (Join-Path $PSScriptRoot 'lens-host-supervisor.ps1') -Mode StopResident -DataDir $ProofDataRoot *> $null

  if ([string]::IsNullOrWhiteSpace($PreviousRoot)) {
    Remove-Item Env:\FRANCIS_ROOT -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_ROOT = $PreviousRoot
  }
  if ([string]::IsNullOrWhiteSpace($PreviousDataDir)) {
    Remove-Item Env:\FRANCIS_DATA_DIR -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_DATA_DIR = $PreviousDataDir
  }
  if ([string]::IsNullOrWhiteSpace($PreviousProfile)) {
    Remove-Item Env:\FRANCIS_ENV_PROFILE -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_ENV_PROFILE = $PreviousProfile
  }
  if ([string]::IsNullOrWhiteSpace($PreviousRunMode)) {
    Remove-Item Env:\FRANCIS_RUN_MODE -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_RUN_MODE = $PreviousRunMode
  }
  if ([string]::IsNullOrWhiteSpace($PreviousProofMode)) {
    Remove-Item Env:\FRANCIS_PROOF_MODE -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_PROOF_MODE = $PreviousProofMode
  }
  if ([string]::IsNullOrWhiteSpace($PreviousProofRunSeconds)) {
    Remove-Item Env:\FRANCIS_PROOF_RUN_SECONDS -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_PROOF_RUN_SECONDS = $PreviousProofRunSeconds
  }
  if ([string]::IsNullOrWhiteSpace($PreviousActorScopes)) {
    Remove-Item Env:\FRANCIS_API_ACTOR_SCOPES -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_API_ACTOR_SCOPES = $PreviousActorScopes
  }
  if ([string]::IsNullOrWhiteSpace($PreviousPythonPath)) {
    Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
  } else {
    $env:PYTHONPATH = $PreviousPythonPath
  }
}

($Output | ForEach-Object { [string]$_ }) -join "`n"
exit $ExitCode
