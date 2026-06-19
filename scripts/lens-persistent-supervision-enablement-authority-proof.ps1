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
  $DataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-persistent-supervision-enablement-authority-proof\" + [guid]::NewGuid().ToString('N') + "\data")
}

$ProofDataRoot = [System.IO.Path]::GetFullPath($DataDir)
$PythonPath = Get-PythonPath
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
  [ordered]@{
    ok = $false
    kind = 'lens.host.persistent_supervision_enablement_authority.proof'
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
import warnings
from pathlib import Path
from typing import Any

warnings.filterwarnings(
    "ignore",
    message=r"Using `httpx` with `starlette\.testclient` is deprecated; install `httpx2` instead\.",
    category=Warning,
)


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
        reason="prove persistent supervision enablement authority boundary",
        actor="test.system.write",
    )

    client = TestClient(create_app())
    host_request = _post(
        client,
        "/lens/host/supervision/authority/request",
        {
            "actor": "test.system.write",
            "reason": "operator wants host supervision authority before persistent supervision enablement proof",
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

    preflight = _get(client, "/lens/host/persistent-supervision/enablement")
    enablement_request = _post(
        client,
        "/lens/host/persistent-supervision/enablement/authority/request",
        {
            "actor": "test.system.write",
            "reason": "operator wants persistent supervision enablement authority reviewed",
        },
    )
    enablement_approval_id = str(enablement_request["approval_id"])
    pending_grant = _post(
        client,
        "/lens/host/persistent-supervision/enablement/authority",
        {
            "approval_id": enablement_approval_id,
            "actor": "test.system.write",
            "reason": "prove pending enablement authority request does not grant authority",
        },
    )
    enablement_decision = _post(
        client,
        "/approvals/decision",
        {
            "id": enablement_approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approve only persistent supervision enablement authority lease",
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

    grants = _get(
        client,
        f"/lens/host/persistent-supervision/enablement/authority/grants?limit=10&approval_id={enablement_approval_id}",
    )
    readiness = _get(
        client,
        "/lens/host/persistent-supervision/enablement/authority/readiness"
        f"?limit=10&approval_id={enablement_approval_id}&actor=test.system.write",
    )
    enablement_denial = _post(
        client,
        "/lens/host/persistent-supervision/enablement",
        {
            "actor": "test.system.write",
            "reason": "prove enablement authority still cannot mutate service config or resident state",
        },
    )
    lens_status = _get(client, "/lens/status?limit=10")

    active_grant = _as_dict(grants.get("active_latest"))
    resident_host = _as_dict(lens_status.get("resident_host"))
    status_grants = _as_dict(resident_host.get("persistent_supervision_enablement_authority_grants"))
    readiness_criterion = _criterion(lens_status, "persistent_supervision_enablement_authority_readiness_audit")
    grant_readback_criterion = _criterion(
        lens_status,
        "persistent_supervision_enablement_authority_grant_receipt_readback",
    )
    denial_criterion = _criterion(lens_status, "persistent_supervision_enablement_denial_boundary")
    denial_blockers = list(dict.fromkeys(str(item) for item in _as_list(enablement_denial.get("blockers")) if str(item)))

    runtime_status_path = data_root / "runtime" / "lens-host" / "status.json"
    runtime_pid_path = data_root / "runtime" / "lens-host" / "lens-host.pid"
    supervisor_status_path = data_root / "runtime" / "lens-host-supervisor" / "status.json"
    no_runtime_files = not runtime_status_path.exists() and not runtime_pid_path.exists() and not supervisor_status_path.exists()
    authority_boundaries_intact = (
        _as_dict(enablement_grant.get("governance")).get("execution_authority") is False
        and _as_dict(enablement_grant.get("governance")).get("service_config_write_authority") is False
        and _as_dict(enablement_grant.get("governance")).get("persistent_supervision_execution_authority") is False
        and _as_dict(enablement_grant.get("governance")).get("memory_write") is False
        and _as_dict(enablement_grant.get("governance")).get("resident_claim_authority") is False
        and _as_dict(enablement_denial.get("governance")).get("execution_authority") is False
        and _as_dict(enablement_denial.get("governance")).get("service_config_write_authority") is False
        and _as_dict(enablement_denial.get("governance")).get("persistent_supervision_execution_authority") is False
        and _as_dict(enablement_denial.get("governance")).get("memory_write") is False
        and _as_dict(enablement_denial.get("governance")).get("resident_claim_authority") is False
    )

    checks = [
        _check(
            "host_supervision_authority_granted",
            "authority_granted" if host_grant.get("status") == "authority_granted" else "failed",
            host_decision.get("status") == "approved"
            and host_grant.get("status") == "authority_granted"
            and bool(host_receipt.get("receipt_id")),
            "/lens/host/supervision/authority",
            "Persistent supervision enablement authority requires an active host supervision authority grant.",
        ),
        _check(
            "enablement_preflight_bound_to_host_grant",
            "blocked" if preflight.get("status") == "blocked" else str(preflight.get("status")),
            preflight.get("authority_grant_active") is True
            and preflight.get("active_grant_receipt_id") == host_receipt.get("receipt_id"),
            "/lens/host/persistent-supervision/enablement",
            "The enablement preflight must see the host grant but remain non-mutating.",
        ),
        _check(
            "enablement_authority_request_ready",
            "approval_requested" if enablement_request.get("status") == "approval_requested" else "failed",
            enablement_request.get("status") == "approval_requested"
            and bool(enablement_approval_id)
            and enablement_request.get("authority_granted") is False,
            "/lens/host/persistent-supervision/enablement/authority/request",
            "The authority route must create a review request before grant.",
        ),
        _check(
            "pending_enablement_grant_blocked",
            "blocked" if pending_grant.get("status") == "blocked" else str(pending_grant.get("status")),
            pending_grant.get("status") == "blocked"
            and pending_grant.get("receipt_written") is False
            and "persistent_supervision_enablement_authority_approval_not_approved" in pending_grant.get("blockers", []),
            "/lens/host/persistent-supervision/enablement/authority",
            "A pending approval must not grant persistent supervision enablement authority.",
        ),
        _check(
            "enablement_authority_granted",
            "authority_granted" if enablement_grant.get("status") == "authority_granted" else "failed",
            enablement_decision.get("status") == "approved"
            and enablement_grant.get("status") == "authority_granted"
            and enablement_grant.get("receipt_written") is True
            and enablement_receipt.get("status") == "authority_granted",
            "/lens/host/persistent-supervision/enablement/authority",
            "The exact approved request must produce a bounded authority grant receipt.",
        ),
        _check(
            "grant_receipt_readback",
            "readback_ready" if grants.get("status") == "readback_ready" else str(grants.get("status")),
            grants.get("total") == 1
            and _as_dict(grants.get("active_latest")).get("receipt_id") == enablement_receipt_id
            and grants.get("authority_granted") is True,
            "/lens/host/persistent-supervision/enablement/authority/grants",
            "The authority grant receipt must be directly readable.",
        ),
        _check(
            "authority_readiness_readback",
            "blocked_authority_granted" if readiness.get("enablement_authority_granted") is True else "failed",
            readiness.get("enablement_authority_granted") is True
            and readiness.get("active_enablement_authority_grant_receipt_id") == enablement_receipt_id
            and readiness.get("service_config_write_authority") is False
            and readiness.get("persistent_supervision_execution_authority") is False
            and "persistent_supervision_enablement_authority_not_granted" not in readiness.get("blockers", []),
            "/lens/host/persistent-supervision/enablement/authority/readiness",
            "Readiness must promote the enablement authority grant while keeping execution blockers visible.",
        ),
        _check(
            "enablement_denial_boundary_after_grant",
            str(enablement_denial.get("status")),
            enablement_denial.get("status") == "denied_no_service_config_write_authority"
            and enablement_denial.get("persistent_supervision_enablement_authority_granted") is True
            and enablement_denial.get("active_enablement_authority_grant_receipt_id") == enablement_receipt_id
            and enablement_denial.get("applied") is False
            and enablement_denial.get("executed") is False
            and enablement_denial.get("service_config_updated") is False
            and "persistent_supervision_enablement_authority_not_granted" not in denial_blockers,
            "/lens/host/persistent-supervision/enablement",
            "The enablement route must still deny config mutation after the authority grant.",
        ),
        _check(
            "lens_status_readback",
            "readback_ready" if status_grants.get("authority_granted") is True else "failed",
            status_grants.get("authority_granted") is True
            and readiness_criterion.get("enablement_authority_granted") is True
            and grant_readback_criterion.get("active_receipt_id") == enablement_receipt_id
            and denial_criterion.get("boundary_ready") is True
            and denial_criterion.get("authority_grant_active") is True
            and denial_criterion.get("service_config_write_authority") is False,
            "/lens/status",
            "Operator status must expose the authority grant and denial boundary as readback.",
        ),
        _check(
            "no_runtime_started",
            "no_runtime_files" if no_runtime_files else "unexpected_runtime_state",
            no_runtime_files,
            "data/runtime/lens-host",
            "The proof must not start or claim a resident runtime.",
        ),
        _check(
            "authority_boundaries_intact",
            "bounded" if authority_boundaries_intact else "unexpected_authority",
            authority_boundaries_intact,
            "grant.governance",
            "The proof must not grant execution, service-config write, persistent execution, memory, or resident-claim authority.",
        ),
    ]
    proof_passed = all(bool(item["passed"]) for item in checks)
    payload = {
        "ok": proof_passed,
        "kind": "lens.host.persistent_supervision_enablement_authority.proof",
        "status": "proof_passed" if proof_passed else "proof_failed",
        "mode": os.environ.get("FRANCIS_PROOF_MODE", "status"),
        "repo_root": str(repo_root),
        "data_root": str(data_root),
        "host_supervision_authority_approval_id": host_approval_id,
        "host_supervision_authority_grant_receipt_id": str(host_receipt.get("receipt_id") or ""),
        "persistent_supervision_enablement_authority_approval_id": enablement_approval_id,
        "persistent_supervision_enablement_authority_grant_receipt_id": enablement_receipt_id,
        "persistent_supervision_enablement_authority": True,
        "service_config_write_authority": False,
        "persistent_supervision_execution_authority": False,
        "persistent_supervision_enablement_allowed": False,
        "resident_claim_allowed": False,
        "grant_applied": enablement_grant.get("applied") is True,
        "enablement_applied": False,
        "executed": False,
        "service_config_updated": False,
        "would_update_service_config": False,
        "would_enable_process_supervision": False,
        "would_enable_persistent_supervision": False,
        "would_install_service": False,
        "would_start_service": False,
        "would_supervise_process": False,
        "would_restart_process": False,
        "would_write_memory": False,
        "would_claim_resident": False,
        "checks": checks,
        "blockers": denial_blockers,
        "proof": {
            "host_grant_status": host_grant.get("status"),
            "preflight_status": preflight.get("status"),
            "preflight_active_grant_receipt_id": preflight.get("active_grant_receipt_id"),
            "pending_grant_status": pending_grant.get("status"),
            "authority_grant_status": enablement_grant.get("status"),
            "authority_grant_receipt_written": enablement_grant.get("receipt_written") is True,
            "grant_receipts_status": grants.get("status"),
            "grant_receipts_total": grants.get("total"),
            "readiness_status": readiness.get("status"),
            "readiness_enablement_authority_granted": readiness.get("enablement_authority_granted"),
            "readiness_service_config_write_authority": readiness.get("service_config_write_authority"),
            "readiness_persistent_supervision_execution_authority": readiness.get(
                "persistent_supervision_execution_authority"
            ),
            "enablement_denial_status": enablement_denial.get("status"),
            "enablement_denial_reason": _as_dict(enablement_denial.get("denial")).get("reason"),
            "status_grants_authority_granted": status_grants.get("authority_granted"),
            "status_readiness_enablement_authority_granted": readiness_criterion.get(
                "enablement_authority_granted"
            ),
            "status_denial_boundary_status": denial_criterion.get("status"),
        },
        "previous_next_smallest_truthful_gap": "persistent_supervision_enablement_disabled",
        "next_smallest_truthful_gap": "persistent_supervision_execution_authority_or_resident_claim_boundary",
        "recommended_next_slice": (
            "review_persistent_supervision_execution_and_resident_claim_boundary_without_runtime_start"
        ),
        "recommended_proof_script": "scripts/lens-persistent-supervision-execution-authority-proof.ps1 -Mode Status",
        "recommended_handoff_source": "persistent_supervision_enablement_authority_handoff",
        "authority_required": "persistent_supervision_execution_authority_and_resident_claim_authority",
        "authority_granted": False,
        "recommended_route": "/lens/host/persistent-supervision/enablement",
        "recommended_readiness_route": "/lens/host/persistent-supervision/enablement/execution/readiness",
        "persistent_supervision_enablement_route": "/lens/host/persistent-supervision/enablement",
        "enablement_authority_request_route": "/lens/host/persistent-supervision/enablement/authority/request",
        "enablement_authority_grants_route": "/lens/host/persistent-supervision/enablement/authority/grants",
        "enablement_authority_readiness_route": "/lens/host/persistent-supervision/enablement/authority/readiness",
        "persistent_supervision_execution_readiness_route": (
            "/lens/host/persistent-supervision/enablement/execution/readiness"
        ),
        "handoff": {
            "recommended_handoff_source": "persistent_supervision_enablement_authority_handoff",
            "status": "blocked",
            "previous_next_smallest_truthful_gap": "persistent_supervision_enablement_disabled",
            "next_smallest_truthful_gap": "persistent_supervision_execution_authority_or_resident_claim_boundary",
            "next_step": (
                "review_persistent_supervision_execution_and_resident_claim_boundary_without_runtime_start"
            ),
            "proof_script": "scripts/lens-persistent-supervision-execution-authority-proof.ps1 -Mode Status",
            "route": "/lens/host/persistent-supervision/enablement",
            "readiness_route": "/lens/host/persistent-supervision/enablement/execution/readiness",
            "authority_required": (
                "persistent_supervision_execution_authority_and_resident_claim_authority"
            ),
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
            "service_config_write_authority": False,
            "persistent_supervision_execution_authority": False,
            "receipt_write_authority": True,
            "memory_write": False,
            "resident_claim_authority": False,
            "mutation_authority_granted": False,
        },
        "message": (
            "A valid host supervision authority grant and approved persistent supervision enablement "
            "authority request now produce a bounded grant receipt and readback, while service-config "
            "mutation, persistent execution, memory writes, runtime launch, and resident claim stay denied."
        ),
    }
    return (0 if proof_passed else 1), payload


try:
    exit_code, payload = _run()
except Exception as exc:
    exit_code = 1
    payload = {
        "ok": False,
        "kind": "lens.host.persistent_supervision_enablement_authority.proof",
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
  $ProofRuntimeDir = Join-Path $ProofDataRoot 'runtime\lens-persistent-supervision-enablement-authority-proof'
  New-Item -ItemType Directory -Force -Path $ProofRuntimeDir | Out-Null
  $PythonScriptPath = Join-Path $ProofRuntimeDir 'proof.py'
  $PythonStderrPath = Join-Path $ProofRuntimeDir 'python-stderr.txt'
  Set-Content -LiteralPath $PythonScriptPath -Value $Source -Encoding UTF8
  $Output = & $PythonPath $PythonScriptPath 2> $PythonStderrPath
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

$OutputText = ($Output | ForEach-Object { [string]$_ }) -join "`n"
if ([string]::IsNullOrWhiteSpace($OutputText) -and $ExitCode -ne 0) {
  $StderrText = ''
  try {
    if (Test-Path -LiteralPath $PythonStderrPath -PathType Leaf) {
      $StderrText = Get-Content -LiteralPath $PythonStderrPath -Raw -ErrorAction Stop
    }
  } catch {
    $StderrText = ''
  }
  [ordered]@{
    ok = $false
    kind = 'lens.host.persistent_supervision_enablement_authority.proof'
    status = 'proof_failed'
    mode = $Mode.ToLowerInvariant()
    repo_root = $RepoRoot
    data_root = $ProofDataRoot
    error = 'python_proof_failed_without_json'
    stderr = $StderrText
  } | ConvertTo-Json -Depth 5
} else {
  $OutputText
}
exit $ExitCode
