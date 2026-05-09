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
  $DataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-stage6-prerequisite-gap-proof\" + [guid]::NewGuid().ToString('N') + "\data")
}

$ProofDataRoot = [System.IO.Path]::GetFullPath($DataDir)
$PythonPath = Get-PythonPath
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
  [ordered]@{
    ok = $false
    kind = 'lens.stage6.prerequisite_gap.proof'
    status = 'proof_failed'
    mode = $Mode.ToLowerInvariant()
    repo_root = $RepoRoot
    data_root = $ProofDataRoot
    error = 'python_unavailable'
  } | ConvertTo-Json -Depth 6
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


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if str(item).strip()]


def _check(check_id: str, status: str, passed: bool, evidence: str, reason: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": status,
        "passed": passed,
        "evidence": evidence,
        "reason": reason,
    }


def _all_false(payload: dict[str, Any], names: list[str]) -> bool:
    return all(payload.get(name) is False for name in names)


def _run() -> tuple[int, dict[str, Any]]:
    from francis.lens.status import lens_status

    repo_root = Path(os.environ["FRANCIS_ROOT"]).resolve()
    data_root = Path(os.environ["FRANCIS_DATA_DIR"]).resolve()
    data_root.mkdir(parents=True, exist_ok=True)

    status = lens_status(limit=10)
    readiness = _as_dict(status.get("stage6_readiness"))
    closure = _as_dict(readiness.get("closure_readback"))
    resident_host = _as_dict(status.get("resident_host"))
    persistent_plan = _as_dict(resident_host.get("persistent_supervision_plan"))
    summon_gate = _as_dict(status.get("summon_enablement_gate"))
    handoff = _as_dict(persistent_plan.get("first_missing_requirement_handoff"))
    status_governance = _as_dict(status.get("governance"))
    handoff_governance = {
        "read_only_contract": handoff.get("read_only_contract") is True,
        "diagnostic_only": handoff.get("diagnostic_only") is True,
        "would_execute": handoff.get("would_execute") is False,
        "would_mutate": handoff.get("would_mutate") is False,
    }

    missing_required = _string_list(persistent_plan.get("missing_required_before_enable"))
    required_before_enable = _string_list(persistent_plan.get("required_before_enable"))
    blocked_criteria = _string_list(closure.get("blocked_criteria"))
    blocked_families = _string_list(summon_gate.get("blocked_families"))
    first_missing = str(persistent_plan.get("first_missing_required_before_enable") or "")
    first_handoff_gap = str(handoff.get("next_smallest_truthful_gap") or "")
    expected_missing = [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    authority_fields = [
        "execution_authority",
        "approval_decision_authority",
        "memory_write",
        "overlay_control_authority",
        "capture_authority",
        "new_sensing_authority",
    ]
    side_effects_denied = (
        _all_false(status_governance, authority_fields)
        and handoff_governance["read_only_contract"]
        and handoff_governance["diagnostic_only"]
        and handoff_governance["would_execute"]
        and handoff_governance["would_mutate"]
    )

    checks = [
        _check(
            "stage6_active",
            str(readiness.get("stage_state") or "unknown"),
            readiness.get("stage_state") == "active" and readiness.get("ready_to_close") is False,
            "/lens/status stage6_readiness",
            "Stage 6 prerequisite-gap proof only applies while Stage 6 is active and not ready to close.",
        ),
        _check(
            "acceptance_blockers",
            str(closure.get("next_smallest_truthful_gap") or "missing"),
            blocked_criteria == ["summon_anywhere", "helpful_not_noisy", "system_resident_presence"],
            "/lens/status stage6_readiness.closure_readback",
            "The remaining Stage 6 acceptance blockers must stay explicit before transition.",
        ),
        _check(
            "persistent_supervision_prerequisites",
            str(persistent_plan.get("status") or "missing"),
            all(item in missing_required for item in expected_missing)
            and first_missing == "resident_host_process",
            "/lens/status resident_host.persistent_supervision_plan",
            "Persistent supervision must name the exact prerequisite family still blocking resident presence.",
        ),
        _check(
            "first_missing_requirement_handoff",
            first_handoff_gap or "missing",
            handoff.get("id") == "resident_host_process"
            and handoff.get("route") == "/lens/host"
            and handoff.get("readiness_route") == "/lens/host/runtime-loop/readiness"
            and bool(handoff.get("proof_script")),
            "persistent_supervision_plan.first_missing_requirement_handoff",
            "The first missing prerequisite must hand off to the resident host runtime boundary.",
        ),
        _check(
            "summon_family_alignment",
            str(summon_gate.get("first_blocker_family") or "missing"),
            "resident_host" in blocked_families
            and summon_gate.get("first_blocker_family") == "resident_host",
            "/lens/status summon_enablement_gate",
            "Summon-anywhere must still align to the resident-host family before tray, overlay, hotkey, and summon.",
        ),
        _check(
            "side_effects_denied",
            "readback_only" if side_effects_denied else "unexpected_authority",
            side_effects_denied,
            "/lens/status governance + first handoff governance",
            "The proof must not grant execution, approval-decision, memory, sensing, overlay, or mutation authority.",
        ),
    ]
    proof_passed = all(item["passed"] for item in checks)
    payload = {
        "ok": proof_passed,
        "kind": "lens.stage6.prerequisite_gap.proof",
        "status": "proof_passed" if proof_passed else "proof_failed",
        "mode": os.environ.get("FRANCIS_PROOF_MODE", "status"),
        "repo_root": str(repo_root),
        "data_root": str(data_root),
        "stage": "Stage 6 / Lens MVP",
        "stage_state": str(readiness.get("stage_state") or ""),
        "ready_to_close": bool(readiness.get("ready_to_close")),
        "stage_claim": str(status.get("stage_claim") or readiness.get("stage_claim") or "backend_readback_contract_only"),
        "acceptance_criterion": "system_resident_presence",
        "blocked_criteria": blocked_criteria,
        "closure_next_smallest_truthful_gap": str(closure.get("next_smallest_truthful_gap") or ""),
        "next_smallest_truthful_gap": "persistent_supervision_required_prerequisites_missing",
        "required_before_enable": required_before_enable,
        "missing_required_before_enable": missing_required,
        "first_missing_required_before_enable": first_missing,
        "first_missing_requirement_handoff": handoff,
        "first_missing_handoff_next_smallest_truthful_gap": first_handoff_gap,
        "summon_anywhere_blocked_families": blocked_families,
        "summon_anywhere_first_blocker_family": str(summon_gate.get("first_blocker_family") or ""),
        "recommended_next_slice": str(
            handoff.get("next_step")
            or "resolve_resident_host_process_before_persistent_supervision_enablement"
        ),
        "recommended_proof_script": str(
            handoff.get("proof_script") or "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status"
        ),
        "recommended_route": str(handoff.get("route") or "/lens/host"),
        "recommended_readiness_route": str(handoff.get("readiness_route") or "/lens/host/runtime-loop/readiness"),
        "checks": checks,
        "evidence": [
            "/lens/status",
            "/lens/status stage6_readiness.closure_readback",
            "/lens/status resident_host.persistent_supervision_plan",
            "/lens/status summon_enablement_gate",
        ],
        "governance": {
            "diagnostic_only": True,
            "read_only_contract": True,
            "uses_lens_status_readback": True,
            "would_execute": False,
            "would_mutate": False,
            "product_execution_authority": False,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
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
            "receipt_write_authority": False,
            "resident_claim_authority": False,
            "mutation_authority_granted": False,
        },
        "message": (
            "Stage 6 remains active: the proof extracts the current resident-prerequisite gap from "
            "Lens status readback so the next slice can continue at the resident-host prerequisite "
            "without granting process, tray, hotkey, overlay, summon, memory, receipt, or resident-claim authority."
        ),
    }
    return (0 if proof_passed else 1), payload


try:
    exit_code, payload = _run()
except Exception as exc:
    exit_code = 1
    payload = {
        "ok": False,
        "kind": "lens.stage6.prerequisite_gap.proof",
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
$PreviousPythonPath = [string]$env:PYTHONPATH

try {
  $env:FRANCIS_ROOT = $RepoRoot
  $env:FRANCIS_DATA_DIR = $ProofDataRoot
  $env:FRANCIS_ENV_PROFILE = 'dev'
  $env:FRANCIS_RUN_MODE = 'api'
  $env:FRANCIS_PROOF_MODE = $Mode.ToLowerInvariant()
  $SourceRoot = Join-Path $RepoRoot 'src'
  if ([string]::IsNullOrWhiteSpace($PreviousPythonPath)) {
    $env:PYTHONPATH = $SourceRoot
  } else {
    $env:PYTHONPATH = $SourceRoot + [System.IO.Path]::PathSeparator + $PreviousPythonPath
  }
  $ProofRuntimeDir = Join-Path $ProofDataRoot 'runtime\lens-stage6-prerequisite-gap-proof'
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
  if ([string]::IsNullOrWhiteSpace($PreviousPythonPath)) {
    Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
  } else {
    $env:PYTHONPATH = $PreviousPythonPath
  }
}

($Output | ForEach-Object { [string]$_ }) -join "`n"
exit $ExitCode
