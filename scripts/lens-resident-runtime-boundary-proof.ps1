[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

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
  $DataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-resident-runtime-boundary-proof\" + [guid]::NewGuid().ToString('N') + "\data")
}

$ProofDataRoot = [System.IO.Path]::GetFullPath($DataDir)
$PythonPath = Get-PythonPath
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
  [ordered]@{
    ok = $false
    kind = 'lens.resident_runtime.granted_boundary_proof'
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
    data_root.mkdir(parents=True, exist_ok=True)
    set_control_mode("assist", reason="prove Lens resident runtime boundary", actor="test.system.write")

    client = TestClient(create_app())
    activation_request = _post(
        client,
        "/lens/host/activation/request",
        {
            "actor": "test.system.write",
            "reason": "operator wants to review Lens host activation before resident runtime proof",
            "mode": "foreground_status_session",
        },
    )
    activation_approval_id = str(activation_request["approval_id"])
    activation_decision = _post(
        client,
        "/approvals/decision",
        {
            "id": activation_approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approve host activation review only for resident runtime proof",
        },
    )

    authority_request = _post(
        client,
        "/lens/resident-runtime/authority-grant/request",
        {
            "actor": "test.system.write",
            "reason": "operator wants to review resident runtime execution authority",
        },
    )
    authority_approval_id = str(authority_request["approval_id"])
    authority_decision = _post(
        client,
        "/approvals/decision",
        {
            "id": authority_approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approve only the resident runtime execution authority lease",
        },
    )
    authority_grant = _post(
        client,
        "/lens/resident-runtime/authority-grant",
        {
            "approval_id": authority_approval_id,
            "actor": "test.system.write",
            "reason": "grant resident runtime execution authority lease for boundary proof",
        },
    )
    runtime_plan = _get(
        client,
        f"/lens/resident-runtime/plan?approval_id={activation_approval_id}&actor=test.system.write",
    )
    runtime_denial = _post(
        client,
        "/lens/resident-runtime/execute",
        {
            "approval_id": activation_approval_id,
            "actor": "test.system.write",
            "reason": "prove granted resident runtime authority still denies runtime execution",
        },
    )
    denial_receipts = _get(client, f"/lens/resident-runtime/denials?limit=10&approval_id={activation_approval_id}")
    lens_status = _get(client, "/lens/status")

    grant_receipt = _as_dict(authority_grant.get("receipt"))
    denial_receipt = _as_dict(runtime_denial.get("receipt"))
    runtime_boundary_criterion = _criterion(lens_status, "resident_runtime_authority_boundary")
    grant_readiness_criterion = _criterion(lens_status, "resident_runtime_authority_grant_readiness_audit")
    blockers = list(dict.fromkeys(str(item) for item in _as_list(runtime_denial.get("blockers")) if str(item)))

    runtime_status_path = data_root / "runtime" / "lens-host" / "status.json"
    runtime_pid_path = data_root / "runtime" / "lens-host" / "lens-host.pid"
    no_runtime_files = not runtime_status_path.exists() and not runtime_pid_path.exists()
    authority_granted = bool(runtime_denial.get("resident_runtime_execution_authority"))
    execution_denied_after_grant = (
        runtime_denial.get("status") == "denied_no_resident_runtime_execution_boundary"
        and authority_granted
        and "resident_runtime_execution_authority_not_granted" not in blockers
    )
    launch_supervision_denied = (
        "local_process_launch_authority_not_granted" in blockers
        and "process_supervision_authority_not_granted" in blockers
        and "service_control_authority_not_granted" in blockers
    )
    surface_authority_denied = (
        "tray_registration_authority_not_granted" in blockers
        and "hotkey_registration_authority_not_granted" in blockers
        and "overlay_control_authority_not_granted" in blockers
        and "resident_claim_authority_not_granted" in blockers
    )
    receipt_readback_ready = (
        runtime_denial.get("receipt_written") is True
        and denial_receipts.get("status") == "readback_ready"
        and denial_receipts.get("total") == 1
        and _as_dict(denial_receipts.get("latest")).get("receipt_id") == denial_receipt.get("receipt_id")
    )
    authority_boundaries_intact = (
        _as_dict(runtime_denial.get("governance")).get("execution_authority") is False
        and _as_dict(runtime_denial.get("governance")).get("process_supervision_authority") is False
        and _as_dict(runtime_denial.get("governance")).get("service_control_authority") is False
        and _as_dict(runtime_denial.get("governance")).get("overlay_control_authority") is False
        and _as_dict(runtime_denial.get("governance")).get("memory_write") is False
        and _as_dict(runtime_denial.get("governance")).get("resident_claim_authority") is False
    )

    checks = [
        _check(
            "activation_approval_ready",
            "approved" if activation_decision.get("status") == "approved" else "failed",
            activation_decision.get("status") == "approved",
            "/approvals/decision",
            "The resident runtime execution attempt must reference an approved host activation request.",
        ),
        _check(
            "authority_grant_ready",
            "authority_granted" if authority_grant.get("status") == "authority_granted" else "failed",
            authority_grant.get("status") == "authority_granted" and grant_receipt.get("status") == "authority_granted",
            "/lens/resident-runtime/authority-grant",
            "The proof must first grant only resident runtime execution authority.",
        ),
        _check(
            "runtime_plan_still_blocked",
            "blocked" if runtime_plan.get("status") == "blocked" else "unexpected_ready",
            runtime_plan.get("status") == "blocked" and runtime_plan.get("resident_claim_allowed") is False,
            "/lens/resident-runtime/plan",
            "The plan must stay blocked after the authority lease.",
        ),
        _check(
            "execute_denied_after_grant",
            "denied_no_resident_runtime_execution_boundary" if execution_denied_after_grant else "failed",
            execution_denied_after_grant,
            "/lens/resident-runtime/execute",
            "Execution authority lease must not become process-launch or resident-runtime authority.",
        ),
        _check(
            "launch_supervision_boundary",
            "blocked" if launch_supervision_denied else "unexpected_authority",
            launch_supervision_denied,
            "/lens/resident-runtime/execute",
            "Process launch, supervision, and service control must remain blocked.",
        ),
        _check(
            "tray_hotkey_overlay_claim_boundary",
            "blocked" if surface_authority_denied else "unexpected_authority",
            surface_authority_denied,
            "/lens/resident-runtime/execute",
            "Tray, hotkey, overlay, and resident claim authority must remain blocked.",
        ),
        _check(
            "denial_receipt_readback",
            "readback_ready" if receipt_readback_ready else "failed",
            receipt_readback_ready,
            "/lens/resident-runtime/denials",
            "The granted-boundary denial must produce a local denial receipt and readback.",
        ),
        _check(
            "no_runtime_started",
            "no_runtime_files" if no_runtime_files else "unexpected_runtime_state",
            no_runtime_files,
            "data/runtime/lens-host",
            "The proof must not start or claim a Lens host runtime.",
        ),
        _check(
            "authority_boundaries_intact",
            "bounded" if authority_boundaries_intact else "unexpected_authority",
            authority_boundaries_intact,
            "execution.governance",
            "The proof must not grant execution, process supervision, service, overlay, memory, or resident-claim authority.",
        ),
    ]
    proof_passed = all(bool(item["passed"]) for item in checks)
    payload = {
        "ok": proof_passed,
        "kind": "lens.resident_runtime.granted_boundary_proof",
        "status": "proof_passed" if proof_passed else "proof_failed",
        "mode": os.environ.get("FRANCIS_PROOF_MODE", "status"),
        "repo_root": str(repo_root),
        "data_root": str(data_root),
        "activation_approval_id": activation_approval_id,
        "resident_runtime_authority_approval_id": authority_approval_id,
        "authority_grant_receipt_id": str(grant_receipt.get("receipt_id") or ""),
        "runtime_denial_receipt_id": str(denial_receipt.get("receipt_id") or ""),
        "authority_required": "resident_runtime_execution_authority",
        "authority_granted": authority_granted,
        "resident_runtime_execution_authority": authority_granted,
        "runtime_ready": False,
        "resident_claim_allowed": False,
        "applied": False,
        "executed": False,
        "would_launch_process": False,
        "would_supervise_process": False,
        "would_restart_process": False,
        "would_install_service": False,
        "would_start_service": False,
        "would_register_tray": False,
        "would_register_hotkey": False,
        "would_open_overlay": False,
        "would_write_memory": False,
        "would_claim_resident": False,
        "checks": checks,
        "blockers": blockers,
        "proof": {
            "authority_grant_status": authority_grant.get("status"),
            "authority_grant_receipt_written": authority_grant.get("receipt_written") is True,
            "runtime_plan_status": runtime_plan.get("status"),
            "runtime_plan_active_authority_grant_receipt_id": runtime_plan.get("active_authority_grant_receipt_id"),
            "runtime_denial_status": runtime_denial.get("status"),
            "runtime_denial_reason": _as_dict(runtime_denial.get("denial")).get("reason"),
            "runtime_denial_receipt_written": runtime_denial.get("receipt_written") is True,
            "runtime_denial_receipts_status": denial_receipts.get("status"),
            "runtime_denial_receipts_total": denial_receipts.get("total"),
            "status_runtime_boundary_status": runtime_boundary_criterion.get("status"),
            "status_runtime_boundary_executed": runtime_boundary_criterion.get("executed"),
            "status_authority_grant_readiness_status": grant_readiness_criterion.get("status"),
            "status_authority_grant_readiness_authority_granted": grant_readiness_criterion.get("authority_granted"),
        },
        "next_smallest_truthful_gap": "supervised_resident_runtime_process_service_tray_hotkey_overlay_authority",
        "governance": {
            "diagnostic_only": True,
            "api_route_proof": True,
            "approval_request_write": True,
            "approval_decision_authority": False,
            "resident_runtime_execution_authority": authority_granted,
            "execution_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "tray_registration_authority": False,
            "hotkey_registration_authority": False,
            "overlay_control_authority": False,
            "memory_write": False,
            "receipt_write_authority": False,
            "denial_receipt_write_authority": runtime_denial.get("receipt_written") is True,
            "resident_claim_authority": False,
            "mutation_authority_granted": False,
        },
        "message": (
            "A valid resident runtime execution authority lease reaches the execution route, "
            "but activation is still denied by supervised process, service, tray, hotkey, overlay, "
            "receipt, and resident-claim boundaries without launching or claiming a resident runtime."
        ),
    }
    return (0 if proof_passed else 1), payload


try:
    exit_code, payload = _run()
except Exception as exc:
    exit_code = 1
    payload = {
        "ok": False,
        "kind": "lens.resident_runtime.granted_boundary_proof",
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
$PreviousActorScopes = [string]$env:FRANCIS_API_ACTOR_SCOPES
$PreviousPythonPath = [string]$env:PYTHONPATH
$PreviousPythonWarnings = [string]$env:PYTHONWARNINGS

try {
  $env:FRANCIS_ROOT = $RepoRoot
  $env:FRANCIS_DATA_DIR = $ProofDataRoot
  $env:FRANCIS_ENV_PROFILE = 'dev'
  $env:FRANCIS_RUN_MODE = 'api'
  $env:FRANCIS_PROOF_MODE = $Mode.ToLowerInvariant()
  $env:FRANCIS_API_ACTOR_SCOPES = '{"test.system.write":["system.write"],"test.approvals.decision":["approvals.decide"]}'
  $SourceRoot = Join-Path $RepoRoot 'src'
  if ([string]::IsNullOrWhiteSpace($PreviousPythonPath)) {
    $env:PYTHONPATH = $SourceRoot
  } else {
    $env:PYTHONPATH = $SourceRoot + [System.IO.Path]::PathSeparator + $PreviousPythonPath
  }
  $env:PYTHONWARNINGS = if ([string]::IsNullOrWhiteSpace($PreviousPythonWarnings)) {
    'ignore'
  } else {
    'ignore,' + $PreviousPythonWarnings
  }
  $ProofRuntimeDir = Join-Path $ProofDataRoot 'runtime\lens-resident-runtime-boundary-proof'
  New-Item -ItemType Directory -Force -Path $ProofRuntimeDir | Out-Null
  $PythonScriptPath = Join-Path $ProofRuntimeDir 'proof.py'
  Set-Content -LiteralPath $PythonScriptPath -Value $Source -Encoding UTF8
  $Output = & $PythonPath $PythonScriptPath 2>&1
  $ExitCode = $LASTEXITCODE
} finally {
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
  if ([string]::IsNullOrWhiteSpace($PreviousPythonWarnings)) {
    Remove-Item Env:\PYTHONWARNINGS -ErrorAction SilentlyContinue
  } else {
    $env:PYTHONWARNINGS = $PreviousPythonWarnings
  }
}

($Output | ForEach-Object { [string]$_ }) -join "`n"
exit $ExitCode
