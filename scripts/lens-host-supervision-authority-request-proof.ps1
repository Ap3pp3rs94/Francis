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
  $DataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-host-supervision-authority-request-proof\" + [guid]::NewGuid().ToString('N') + "\data")
}

$ProofDataRoot = [System.IO.Path]::GetFullPath($DataDir)
$PythonPath = Get-PythonPath
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
  [ordered]@{
    ok = $false
    kind = 'lens.host.supervision_authority_exact_approval_request.proof'
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
        reason="prove host supervision authority exact approval request boundary",
        actor="test.system.write",
    )

    client = TestClient(create_app())
    readiness_before = _get(
        client,
        "/lens/host/supervision/authority/readiness?limit=10&actor=test.system.write",
    )
    request = _post(
        client,
        "/lens/host/supervision/authority/request",
        {
            "actor": "test.system.write",
            "reason": "operator wants host supervision authority reviewed before resident host supervision",
        },
    )
    approval_id = str(request["approval_id"])
    request_readback = _get(client, f"/lens/host/supervision/authority/requests?limit=10&approval_id={approval_id}")
    pending_grant = _post(
        client,
        "/lens/host/supervision/authority",
        {
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "prove pending host supervision authority request does not grant authority",
        },
    )
    decision = _post(
        client,
        "/approvals/decision",
        {
            "id": approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approve only host supervision authority review decision for proof",
        },
    )
    grant = _post(
        client,
        "/lens/host/supervision/authority",
        {
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "grant bounded host supervision authority without starting runtime",
        },
    )
    receipt = _as_dict(grant.get("receipt"))
    authorities = _as_dict(receipt.get("authorities"))
    receipt_id = str(receipt.get("receipt_id") or "")

    grants = _get(client, f"/lens/host/supervision/authority/grants?limit=10&approval_id={approval_id}")
    denials = _get(client, f"/lens/host/supervision/authority/denials?limit=10&approval_id={approval_id}")
    readiness_after = _get(
        client,
        f"/lens/host/supervision/authority/readiness?limit=10&approval_id={approval_id}&actor=test.system.write",
    )
    persistent_plan = _get(client, "/lens/host/persistent-supervision")
    enablement = _get(client, "/lens/host/persistent-supervision/enablement")
    lens_status = _get(client, "/lens/status?limit=10")

    requirements_before = {str(item.get("id")): item for item in _as_list(readiness_before.get("requirements")) if isinstance(item, dict)}
    requirements_after = {str(item.get("id")): item for item in _as_list(readiness_after.get("requirements")) if isinstance(item, dict)}
    persistent_requirements = {str(item.get("id")): item for item in _as_list(persistent_plan.get("requirements")) if isinstance(item, dict)}
    enablement_requirements = {str(item.get("id")): item for item in _as_list(enablement.get("requirements")) if isinstance(item, dict)}
    resident_host = _as_dict(lens_status.get("resident_host"))
    status_grants = _as_dict(resident_host.get("supervision_authority_grant_receipts"))
    status_active_grant = _as_dict(status_grants.get("active_latest"))
    status_readiness = _as_dict(resident_host.get("supervision_authority_readiness"))
    readiness_criterion = _criterion(lens_status, "resident_host_supervision_authority_preflight")

    runtime_status_path = data_root / "runtime" / "lens-host" / "status.json"
    runtime_pid_path = data_root / "runtime" / "lens-host" / "lens-host.pid"
    supervisor_status_path = data_root / "runtime" / "lens-host-supervisor" / "status.json"
    no_runtime_files = not runtime_status_path.exists() and not runtime_pid_path.exists() and not supervisor_status_path.exists()

    checks = [
        _check(
            "readiness_before_points_to_exact_approval_request",
            str(readiness_before.get("status")),
            readiness_before.get("next_smallest_truthful_gap") == "host_supervision_authority_exact_approval_request"
            and _as_dict(requirements_before.get("exact_supervision_authority_approval")).get("ready") is False,
            "/lens/host/supervision/authority/readiness",
            "readiness must name the exact approved request as the first blocker before a grant",
        ),
        _check(
            "authority_request_created",
            str(request.get("status")),
            request.get("approval_requested") is True
            and bool(approval_id)
            and request.get("authority_granted") is False
            and _as_dict(request.get("governance")).get("approval_request_write") is True,
            "/lens/host/supervision/authority/request",
            "request route must create only an approval request and must not grant authority",
        ),
        _check(
            "request_readback",
            str(request_readback.get("status")),
            request_readback.get("total_count") == 1
            and _as_dict(request_readback.get("latest")).get("id") == approval_id
            and _as_dict(request_readback.get("latest")).get("status") == "pending",
            "/lens/host/supervision/authority/requests",
            "approval request must be directly readable before a decision",
        ),
        _check(
            "pending_grant_blocked",
            str(pending_grant.get("status")),
            pending_grant.get("authority_granted") is False
            and pending_grant.get("receipt_written") is False
            and "supervision_authority_approval_not_approved" in _as_list(pending_grant.get("blockers")),
            "/lens/host/supervision/authority",
            "pending approval must not grant process supervision authority or write a grant receipt",
        ),
        _check(
            "approval_decision_fixture",
            str(decision.get("status")),
            decision.get("status") == "approved",
            "/approvals/decision",
            "test fixture approval decision must be explicit before any authority grant",
        ),
        _check(
            "authority_granted",
            str(grant.get("status")),
            grant.get("authority_granted") is True
            and grant.get("applied") is True
            and grant.get("executed") is False
            and grant.get("receipt_written") is True
            and bool(receipt_id),
            "/lens/host/supervision/authority",
            "approved request must produce a bounded authority grant receipt without execution",
        ),
        _check(
            "grant_receipt_readback",
            str(grants.get("status")),
            grants.get("total") == 1
            and _as_dict(grants.get("active_latest")).get("receipt_id") == receipt_id
            and grants.get("authority_granted") is True,
            "/lens/host/supervision/authority/grants",
            "grant receipt must be directly readable and active for the exact approval id",
        ),
        _check(
            "denial_readback_empty_after_valid_grant",
            str(denials.get("status")),
            denials.get("total") == 0 and _as_list(denials.get("items")) == [],
            "/lens/host/supervision/authority/denials",
            "valid approved grant path should not emit denial receipts",
        ),
        _check(
            "readiness_after_consumes_exact_approval",
            str(readiness_after.get("status")),
            _as_dict(requirements_after.get("exact_supervision_authority_approval")).get("ready") is True
            and _as_dict(requirements_after.get("process_supervision_authority")).get("ready") is True
            and _as_dict(requirements_after.get("service_control_authority")).get("ready") is True
            and readiness_after.get("active_grant_receipt_id") == receipt_id,
            "/lens/host/supervision/authority/readiness",
            "exact approval and bounded host supervision authorities must read back as ready after grant",
        ),
        _check(
            "persistent_enablement_boundary",
            str(enablement.get("status")),
            persistent_plan.get("next_smallest_truthful_gap") == "persistent_supervision_enablement_disabled"
            and enablement.get("next_smallest_truthful_gap") == "persistent_supervision_enablement_disabled"
            and _as_dict(enablement_requirements.get("active_host_supervision_authority_grant")).get("ready") is True
            and _as_dict(persistent_requirements.get("process_supervision_enabled")).get("ready") is False,
            "/lens/host/persistent-supervision/enablement",
            "host supervision authority grant must advance only to the persistent-supervision enablement boundary",
        ),
        _check(
            "lens_status_readback",
            str(status_grants.get("status")),
            status_grants.get("authority_granted") is True
            and status_active_grant.get("receipt_id") == receipt_id
            and status_readiness.get("request_readback_ready") is True
            and status_readiness.get("resident_claim_allowed") is False
            and readiness_criterion.get("ready") is False,
            "/lens/status",
            "operator status must read back granted supervision authority without claiming resident presence",
        ),
        _check(
            "no_runtime_started",
            "no_runtime_files" if no_runtime_files else "runtime_files_present",
            no_runtime_files,
            str(data_root / "runtime"),
            "proof must not start, supervise, or claim a Lens host runtime",
        ),
        _check(
            "authority_boundaries_intact",
            "bounded",
            authorities.get("process_supervision_authority") is True
            and authorities.get("process_restart_authority") is True
            and authorities.get("service_install_authority") is True
            and authorities.get("service_control_authority") is True
            and authorities.get("receipt_write_authority") is True
            and authorities.get("resident_claim_authority") is True
            and _as_dict(receipt.get("governance")).get("execution_authority") is False
            and _as_dict(receipt.get("governance")).get("approval_decision_authority") is False
            and _as_dict(receipt.get("governance")).get("memory_write") is False,
            "grant receipt authorities",
            "grant may lease bounded host supervision authority only; execution, approval decision, and memory writes stay false",
        ),
    ]
    proof_passed = all(item["passed"] for item in checks)

    payload = {
        "ok": proof_passed,
        "kind": "lens.host.supervision_authority_exact_approval_request.proof",
        "status": "proof_passed" if proof_passed else "proof_failed",
        "mode": os.environ.get("FRANCIS_PROOF_MODE", "status"),
        "repo_root": str(repo_root),
        "data_root": str(data_root),
        "host_supervision_authority_approval_id": approval_id,
        "host_supervision_authority_grant_receipt_id": receipt_id,
        "authority_granted": bool(grant.get("authority_granted")),
        "grant_applied": bool(grant.get("applied")),
        "executed": bool(grant.get("executed")),
        "supervision_ready": bool(grant.get("supervision_ready")),
        "resident_claim_allowed": bool(grant.get("resident_claim_allowed")),
        "process_supervision_authority": bool(authorities.get("process_supervision_authority")),
        "process_restart_authority": bool(authorities.get("process_restart_authority")),
        "service_install_authority": bool(authorities.get("service_install_authority")),
        "service_control_authority": bool(authorities.get("service_control_authority")),
        "receipt_write_authority": bool(authorities.get("receipt_write_authority")),
        "resident_claim_authority": bool(authorities.get("resident_claim_authority")),
        "memory_write": bool(_as_dict(receipt.get("governance")).get("memory_write")),
        "next_smallest_truthful_gap": str(persistent_plan.get("next_smallest_truthful_gap") or ""),
        "blockers": _as_list(enablement.get("blockers")),
        "runtime_files": {
            "lens_host_status": runtime_status_path.exists(),
            "lens_host_pid": runtime_pid_path.exists(),
            "lens_host_supervisor_status": supervisor_status_path.exists(),
        },
        "checks": checks,
        "proof": {
            "readiness_before_status": readiness_before.get("status"),
            "readiness_before_next_gap": readiness_before.get("next_smallest_truthful_gap"),
            "request_status": request.get("status"),
            "request_readback_status": request_readback.get("status"),
            "pending_grant_status": pending_grant.get("status"),
            "decision_status": decision.get("status"),
            "grant_status": grant.get("status"),
            "grant_receipt_kind": receipt.get("kind"),
            "grant_receipts_status": grants.get("status"),
            "readiness_after_status": readiness_after.get("status"),
            "readiness_after_active_grant_receipt_id": readiness_after.get("active_grant_receipt_id"),
            "persistent_plan_status": persistent_plan.get("status"),
            "persistent_plan_next_gap": persistent_plan.get("next_smallest_truthful_gap"),
            "enablement_status": enablement.get("status"),
            "enablement_next_gap": enablement.get("next_smallest_truthful_gap"),
            "status_grants_authority_granted": status_grants.get("authority_granted"),
            "status_active_grant_receipt_id": status_active_grant.get("receipt_id"),
            "status_readiness_request_readback_ready": status_readiness.get("request_readback_ready"),
            "status_readiness_resident_claim_allowed": status_readiness.get("resident_claim_allowed"),
            "status_stage6_requirement_ready": readiness_criterion.get("ready"),
        },
        "governance": {
            "diagnostic_only": True,
            "api_route_proof": True,
            "approval_request_write": True,
            "test_fixture_approval_decisions": True,
            "approval_decision_authority": False,
            "execution_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": bool(authorities.get("process_supervision_authority")),
            "process_restart_authority": bool(authorities.get("process_restart_authority")),
            "service_install_authority": bool(authorities.get("service_install_authority")),
            "service_control_authority": bool(authorities.get("service_control_authority")),
            "persistent_supervision_enablement_authority": False,
            "service_config_write_authority": False,
            "persistent_supervision_execution_authority": False,
            "receipt_write_authority": bool(authorities.get("receipt_write_authority")),
            "memory_write": False,
            "resident_claim_authority": bool(authorities.get("resident_claim_authority")),
            "mutation_authority_granted": False,
        },
        "message": (
            "The exact host supervision approval request now drives approval, grant receipt, and readback "
            "in a temp proof, while runtime launch, service-config mutation, memory writes, and resident "
            "claim remain denied."
        ),
    }
    return (0 if proof_passed else 1), payload


try:
    exit_code, payload = _run()
except Exception as exc:
    exit_code = 1
    payload = {
        "ok": False,
        "kind": "lens.host.supervision_authority_exact_approval_request.proof",
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
  $ProofRuntimeDir = Join-Path $ProofDataRoot 'runtime\lens-host-supervision-authority-request-proof'
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
