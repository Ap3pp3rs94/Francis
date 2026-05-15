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
  $DataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-persistent-supervision-execution-authority-proof\" + [guid]::NewGuid().ToString('N') + "\data")
}

$ProofDataRoot = [System.IO.Path]::GetFullPath($DataDir)
$PythonPath = Get-PythonPath
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
  [ordered]@{
    ok = $false
    kind = 'lens.host.persistent_supervision_execution_authority.proof'
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
    set_control_mode(
        "assist",
        reason="prove persistent supervision execution authority boundary",
        actor="test.system.write",
    )

    client = TestClient(create_app())
    host_request = _post(
        client,
        "/lens/host/supervision/authority/request",
        {
            "actor": "test.system.write",
            "reason": "operator wants host supervision authority before persistent supervision execution proof",
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
            "comment": "approve only host supervision authority prerequisite for proof",
        },
    )
    host_grant = _post(
        client,
        "/lens/host/supervision/authority",
        {
            "approval_id": host_approval_id,
            "actor": "test.system.write",
            "reason": "grant host supervision authority prerequisite without starting a runtime",
        },
    )
    host_receipt = _as_dict(host_grant.get("receipt"))

    enablement_request = _post(
        client,
        "/lens/host/persistent-supervision/enablement/authority/request",
        {
            "actor": "test.system.write",
            "reason": "operator wants persistent supervision enablement authority reviewed",
        },
    )
    enablement_approval_id = str(enablement_request["approval_id"])
    enablement_decision = _post(
        client,
        "/approvals/decision",
        {
            "id": enablement_approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approve only persistent supervision enablement authority prerequisite",
        },
    )
    enablement_grant = _post(
        client,
        "/lens/host/persistent-supervision/enablement/authority",
        {
            "approval_id": enablement_approval_id,
            "actor": "test.system.write",
            "reason": "grant bounded persistent supervision enablement authority without config mutation",
        },
    )
    enablement_receipt = _as_dict(enablement_grant.get("receipt"))
    enablement_receipt_id = str(enablement_receipt.get("receipt_id") or "")

    execution_request = _post(
        client,
        "/lens/host/persistent-supervision/enablement/execution/request",
        {
            "actor": "test.system.write",
            "reason": "operator wants persistent supervision execution authority reviewed",
        },
    )
    execution_approval_id = str(execution_request["approval_id"])
    pending_denial = _post(
        client,
        "/lens/host/persistent-supervision/enablement/execution",
        {
            "approval_id": execution_approval_id,
            "actor": "test.system.write",
            "reason": "prove pending execution authority request cannot execute",
        },
    )
    execution_decision = _post(
        client,
        "/approvals/decision",
        {
            "id": execution_approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approve only persistent supervision execution authority review decision",
        },
    )
    approved_denial = _post(
        client,
        "/lens/host/persistent-supervision/enablement/execution",
        {
            "approval_id": execution_approval_id,
            "actor": "test.system.write",
            "reason": "prove approved execution request still has no authority receipt",
        },
    )
    execution_grant = _post(
        client,
        "/lens/host/persistent-supervision/enablement/execution/authority",
        {
            "approval_id": execution_approval_id,
            "actor": "test.system.write",
            "reason": "grant bounded persistent supervision execution authority without runtime mutation",
        },
    )
    execution_receipt = _as_dict(execution_grant.get("receipt"))
    execution_receipt_id = str(execution_receipt.get("receipt_id") or "")
    execution_grants = _get(
        client,
        "/lens/host/persistent-supervision/enablement/execution/authority/grants"
        f"?limit=10&approval_id={execution_approval_id}",
    )
    granted_readiness = _get(
        client,
        "/lens/host/persistent-supervision/enablement/execution/readiness"
        f"?limit=10&approval_id={execution_approval_id}&actor=test.system.write",
    )
    granted_denial = _post(
        client,
        "/lens/host/persistent-supervision/enablement/execution",
        {
            "approval_id": execution_approval_id,
            "actor": "test.system.write",
            "reason": "prove execution authority still stops before resident claim",
        },
    )
    lens_status = _get(client, "/lens/status?limit=10")

    resident_host = _as_dict(lens_status.get("resident_host"))
    status_requests = _as_dict(resident_host.get("persistent_supervision_enablement_execution_requests"))
    status_grants = _as_dict(resident_host.get("persistent_supervision_enablement_execution_authority_grants"))
    readiness_criterion = _criterion(lens_status, "persistent_supervision_enablement_execution_readiness_audit")
    grant_readback_criterion = _criterion(
        lens_status,
        "persistent_supervision_enablement_execution_authority_grant_receipt_readback",
    )
    denial_criterion = _criterion(lens_status, "persistent_supervision_enablement_execution_denial_boundary")
    blockers = list(dict.fromkeys(str(item) for item in _as_list(granted_denial.get("blockers")) if str(item)))

    runtime_status_path = data_root / "runtime" / "lens-host" / "status.json"
    runtime_pid_path = data_root / "runtime" / "lens-host" / "lens-host.pid"
    supervisor_status_path = data_root / "runtime" / "lens-host-supervisor" / "status.json"
    no_runtime_files = not runtime_status_path.exists() and not runtime_pid_path.exists() and not supervisor_status_path.exists()
    authority_boundaries_intact = (
        _as_dict(granted_denial.get("governance")).get("execution_authority") is False
        and _as_dict(granted_denial.get("governance")).get("approval_decision_authority") is False
        and _as_dict(granted_denial.get("governance")).get("memory_write") is False
        and _as_dict(granted_denial.get("governance")).get("resident_claim_authority") is False
        and granted_denial.get("service_config_write_authority") is True
        and granted_denial.get("persistent_supervision_execution_authority") is True
        and granted_denial.get("receipt_write_authority") is True
    )

    checks = [
        _check(
            "host_supervision_authority_granted",
            "authority_granted" if host_grant.get("status") == "authority_granted" else "failed",
            host_decision.get("status") == "approved"
            and host_grant.get("status") == "authority_granted"
            and bool(host_receipt.get("receipt_id")),
            "/lens/host/supervision/authority",
            "Persistent supervision execution authority requires an active host supervision authority grant.",
        ),
        _check(
            "enablement_authority_granted",
            "authority_granted" if enablement_grant.get("status") == "authority_granted" else "failed",
            enablement_decision.get("status") == "approved"
            and enablement_grant.get("status") == "authority_granted"
            and enablement_grant.get("receipt_written") is True
            and bool(enablement_receipt_id),
            "/lens/host/persistent-supervision/enablement/authority",
            "Persistent supervision execution authority must be downstream from enablement authority.",
        ),
        _check(
            "execution_authority_request_ready",
            "approval_requested" if execution_request.get("status") == "approval_requested" else "failed",
            execution_request.get("status") == "approval_requested"
            and execution_request.get("persistent_supervision_enablement_authority_granted") is True
            and execution_request.get("authority_granted") is False
            and bool(execution_approval_id),
            "/lens/host/persistent-supervision/enablement/execution/request",
            "The execution authority route must create a review request before grant.",
        ),
        _check(
            "pending_execution_blocked",
            "blocked" if pending_denial.get("status") == "blocked" else str(pending_denial.get("status")),
            pending_denial.get("status") == "blocked"
            and "persistent_supervision_enablement_execution_approval_not_approved"
            in _as_list(pending_denial.get("blockers")),
            "/lens/host/persistent-supervision/enablement/execution",
            "A pending approval must not allow persistent supervision execution.",
        ),
        _check(
            "approved_request_without_grant_blocked",
            str(approved_denial.get("status")),
            execution_decision.get("status") == "approved"
            and approved_denial.get("status") == "denied_no_service_config_write_authority"
            and approved_denial.get("persistent_supervision_execution_authority") is False
            and "persistent_supervision_execution_authority_not_granted" in _as_list(approved_denial.get("blockers")),
            "/lens/host/persistent-supervision/enablement/execution",
            "An approved request still needs a bounded execution authority grant receipt.",
        ),
        _check(
            "execution_authority_granted",
            "authority_granted" if execution_grant.get("status") == "authority_granted" else "failed",
            execution_grant.get("status") == "authority_granted"
            and execution_grant.get("receipt_written") is True
            and execution_grant.get("service_config_write_authority") is True
            and execution_grant.get("persistent_supervision_execution_authority") is True
            and execution_grant.get("persistent_supervision_enablement_allowed") is False
            and bool(execution_receipt_id),
            "/lens/host/persistent-supervision/enablement/execution/authority",
            "The exact approved request must produce a bounded execution authority grant receipt.",
        ),
        _check(
            "grant_receipt_readback",
            "readback_ready" if execution_grants.get("status") == "readback_ready" else str(execution_grants.get("status")),
            execution_grants.get("total") == 1
            and _as_dict(execution_grants.get("active_latest")).get("receipt_id") == execution_receipt_id
            and execution_grants.get("authority_granted") is True,
            "/lens/host/persistent-supervision/enablement/execution/authority/grants",
            "The execution authority grant receipt must be directly readable.",
        ),
        _check(
            "execution_readiness_promoted_to_resident_claim",
            "blocked_authority_granted" if granted_readiness.get("execution_authority_granted") is True else "failed",
            granted_readiness.get("execution_authority_granted") is True
            and granted_readiness.get("service_config_write_authority") is True
            and granted_readiness.get("persistent_supervision_execution_authority") is True
            and granted_readiness.get("receipt_write_authority") is True
            and "service_config_write_authority_not_granted" not in _as_list(granted_readiness.get("blockers"))
            and "persistent_supervision_execution_authority_not_granted"
            not in _as_list(granted_readiness.get("blockers"))
            and "resident_claim_authority_not_granted" in _as_list(granted_readiness.get("blockers")),
            "/lens/host/persistent-supervision/enablement/execution/readiness",
            "Readiness must promote the grant and narrow the blocker to resident claim.",
        ),
        _check(
            "execution_denial_after_grant",
            str(granted_denial.get("status")),
            granted_denial.get("status") == "denied_no_resident_claim_authority"
            and granted_denial.get("authority_granted") is True
            and granted_denial.get("active_execution_authority_grant_receipt_id") == execution_receipt_id
            and granted_denial.get("applied") is False
            and granted_denial.get("executed") is False
            and granted_denial.get("service_config_updated") is False
            and "service_config_write_authority_not_granted" not in blockers
            and "persistent_supervision_execution_authority_not_granted" not in blockers
            and "receipt_write_authority_not_granted" not in blockers
            and "resident_claim_authority_not_granted" in blockers,
            "/lens/host/persistent-supervision/enablement/execution",
            "Execution authority must still stop before resident claim or persistent runtime mutation.",
        ),
        _check(
            "lens_status_readback",
            "readback_ready" if status_grants.get("authority_granted") is True else "failed",
            status_requests.get("authority_granted") is True
            and status_requests.get("active_execution_authority_grant_receipt_id") == execution_receipt_id
            and status_grants.get("authority_granted") is True
            and readiness_criterion.get("execution_authority_granted") is True
            and grant_readback_criterion.get("active_receipt_id") == execution_receipt_id
            and denial_criterion.get("authority_granted") is True,
            "/lens/status",
            "Operator status must expose the execution authority grant and resident-claim denial boundary.",
        ),
        _check(
            "no_runtime_started",
            "no_runtime_files" if no_runtime_files else "unexpected_runtime_state",
            no_runtime_files,
            "data/runtime/lens-host",
            "The proof must not start, supervise, or claim a resident runtime.",
        ),
        _check(
            "authority_boundaries_intact",
            "bounded" if authority_boundaries_intact else "unexpected_authority",
            authority_boundaries_intact,
            "execution.governance",
            "The proof must not grant general execution, approval-decision, memory, or resident-claim authority.",
        ),
    ]
    proof_passed = all(bool(item["passed"]) for item in checks)
    payload = {
        "ok": proof_passed,
        "kind": "lens.host.persistent_supervision_execution_authority.proof",
        "status": "proof_passed" if proof_passed else "proof_failed",
        "mode": os.environ.get("FRANCIS_PROOF_MODE", "status"),
        "repo_root": str(repo_root),
        "data_root": str(data_root),
        "host_supervision_authority_approval_id": host_approval_id,
        "host_supervision_authority_grant_receipt_id": str(host_receipt.get("receipt_id") or ""),
        "persistent_supervision_enablement_authority_approval_id": enablement_approval_id,
        "persistent_supervision_enablement_authority_grant_receipt_id": enablement_receipt_id,
        "persistent_supervision_execution_authority_approval_id": execution_approval_id,
        "persistent_supervision_execution_authority_grant_receipt_id": execution_receipt_id,
        "persistent_supervision_enablement_authority": True,
        "service_config_write_authority": True,
        "persistent_supervision_execution_authority": True,
        "receipt_write_authority": True,
        "persistent_supervision_enablement_allowed": False,
        "resident_claim_allowed": False,
        "grant_applied": execution_grant.get("applied") is True,
        "enablement_applied": False,
        "applied": False,
        "executed": False,
        "service_config_updated": False,
        "would_update_service_config": False,
        "would_enable_persistent_supervision": False,
        "would_start_service": False,
        "would_supervise_process": False,
        "would_restart_process": False,
        "would_write_receipt": False,
        "would_write_memory": False,
        "would_claim_resident": False,
        "checks": checks,
        "blockers": blockers,
        "proof": {
            "host_grant_status": host_grant.get("status"),
            "enablement_authority_grant_status": enablement_grant.get("status"),
            "execution_request_status": execution_request.get("status"),
            "pending_denial_status": pending_denial.get("status"),
            "approved_denial_status": approved_denial.get("status"),
            "execution_authority_grant_status": execution_grant.get("status"),
            "execution_authority_grant_receipt_written": execution_grant.get("receipt_written") is True,
            "grant_receipts_status": execution_grants.get("status"),
            "grant_receipts_total": execution_grants.get("total"),
            "readiness_status": granted_readiness.get("status"),
            "readiness_execution_authority_granted": granted_readiness.get("execution_authority_granted"),
            "readiness_resident_claim_allowed": granted_readiness.get("resident_claim_allowed"),
            "execution_denial_status": granted_denial.get("status"),
            "execution_denial_reason": _as_dict(granted_denial.get("denial")).get("reason"),
            "status_requests_authority_granted": status_requests.get("authority_granted"),
            "status_grants_authority_granted": status_grants.get("authority_granted"),
            "status_readiness_execution_authority_granted": readiness_criterion.get("execution_authority_granted"),
            "status_denial_boundary_status": denial_criterion.get("status"),
        },
        "previous_next_smallest_truthful_gap": (
            "persistent_supervision_execution_authority_or_resident_claim_boundary"
        ),
        "next_smallest_truthful_gap": "persistent_supervision_resident_claim_authority_boundary",
        "recommended_next_slice": "review_persistent_supervision_resident_claim_boundary_without_runtime_start",
        "recommended_proof_script": "scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status",
        "recommended_handoff_source": "persistent_supervision_execution_authority_handoff",
        "persistent_supervision_execution_route": "/lens/host/persistent-supervision/enablement/execution",
        "persistent_supervision_execution_request_route": (
            "/lens/host/persistent-supervision/enablement/execution/request"
        ),
        "persistent_supervision_execution_authority_route": (
            "/lens/host/persistent-supervision/enablement/execution/authority"
        ),
        "persistent_supervision_execution_authority_grants_route": (
            "/lens/host/persistent-supervision/enablement/execution/authority/grants"
        ),
        "persistent_supervision_execution_readiness_route": (
            "/lens/host/persistent-supervision/enablement/execution/readiness"
        ),
        "handoff": {
            "recommended_handoff_source": "persistent_supervision_execution_authority_handoff",
            "status": "blocked",
            "previous_next_smallest_truthful_gap": (
                "persistent_supervision_execution_authority_or_resident_claim_boundary"
            ),
            "next_smallest_truthful_gap": "persistent_supervision_resident_claim_authority_boundary",
            "next_step": "review_persistent_supervision_resident_claim_boundary_without_runtime_start",
            "proof_script": "scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status",
            "route": "/lens/host/persistent-supervision/enablement/execution",
            "readiness_route": "/lens/host/persistent-supervision/enablement/execution/readiness",
            "authority_required": "resident_claim_authority",
            "authority_granted": False,
            "read_only_contract": True,
            "diagnostic_only": True,
            "would_execute": False,
            "would_mutate": False,
        },
        "governance": {
            "diagnostic_only": True,
            "api_route_proof": True,
            "approval_request_write": True,
            "test_fixture_approval_decisions": True,
            "approval_decision_authority": False,
            "execution_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "persistent_supervision_enablement_authority": True,
            "service_config_write_authority": True,
            "persistent_supervision_execution_authority": True,
            "receipt_write_authority": True,
            "memory_write": False,
            "resident_claim_authority": False,
            "mutation_authority_granted": False,
        },
        "message": (
            "A valid persistent supervision execution authority grant is directly readable and reaches "
            "the execution route, but persistent supervision enablement still stops at the resident-claim "
            "boundary without service config mutation, runtime start, memory writes, or resident claim."
        ),
    }
    return (0 if proof_passed else 1), payload


try:
    exit_code, payload = _run()
except Exception as exc:
    exit_code = 1
    payload = {
        "ok": False,
        "kind": "lens.host.persistent_supervision_execution_authority.proof",
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
  $ProofRuntimeDir = Join-Path $ProofDataRoot 'runtime\lens-persistent-supervision-execution-authority-proof'
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
}

($Output | ForEach-Object { [string]$_ }) -join "`n"
exit $ExitCode
