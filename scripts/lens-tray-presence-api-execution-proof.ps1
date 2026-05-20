[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(1, 60)]
  [int]$RunSeconds = 10,

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
  $DataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-tray-presence-api-execution-proof\" + [guid]::NewGuid().ToString('N') + "\data")
}

$ProofDataRoot = [System.IO.Path]::GetFullPath($DataDir)
$PythonPath = Get-PythonPath
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
  [ordered]@{
    ok = $false
    kind = 'lens.tray_presence.api_execution.proof'
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


def _str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str) and value:
        return [value]
    return []


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


def _approve(client: Any, *, approval_id: str, comment: str) -> dict[str, Any]:
    return _post(
        client,
        "/approvals/decision",
        {
            "id": approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": comment,
        },
    )


def _stop_tray(client: Any, *, approval_id: str, actor: str, reason: str) -> dict[str, Any]:
    if not approval_id:
        return {"ok": False, "status": "stop_skipped_no_tray_approval_id", "tray_presence": True}
    return _post(
        client,
        "/lens/tray/execute",
        {
            "approval_id": approval_id,
            "actor": actor,
            "reason": reason,
            "mode": "stop",
        },
    )


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


def _dependency_map(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in _as_list(plan.get("enablement_dependency_readback")):
        if isinstance(item, dict) and item.get("id"):
            out[str(item["id"])] = item
    return out


def _remaining_blockers(plan: dict[str, Any]) -> list[str]:
    dependencies = _dependency_map(plan)
    blockers: list[str] = []
    for requirement in _str_list(plan.get("missing_required_before_enable")):
        dependency = dependencies.get(requirement, {})
        blocker = str(dependency.get("blocker") or "")
        blockers.append(blocker or f"{requirement}_missing")
    return list(dict.fromkeys(item for item in blockers if item))


def _run() -> tuple[int, dict[str, Any]]:
    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.world_state.operator_mode import set_control_mode

    repo_root = Path(os.environ["FRANCIS_ROOT"]).resolve()
    data_root = Path(os.environ["FRANCIS_DATA_DIR"]).resolve()
    run_seconds = int(os.environ.get("FRANCIS_PROOF_RUN_SECONDS", "5"))
    dependency_run_seconds = max(run_seconds, 20)
    data_root.mkdir(parents=True, exist_ok=True)

    actor = "test.system.write"
    set_control_mode(
        "assist",
        reason="prove Lens tray presence API execution path",
        actor=actor,
    )

    client = TestClient(create_app())
    host_approval_id = ""
    runtime_approval_id = ""
    tray_approval_id = ""
    tray_stop: dict[str, Any] = {}
    resident_stop: dict[str, Any] = {}
    fallback_stop: dict[str, Any] = {}
    try:
        host_request = _post(
            client,
            "/lens/host/supervision/authority/request",
            {
                "actor": actor,
                "reason": "operator wants host supervision authority before tray API proof",
            },
        )
        host_approval_id = str(host_request["approval_id"])
        host_decision = _approve(
            client,
            approval_id=host_approval_id,
            comment="approve only host supervision authority for isolated tray API proof",
        )
        host_grant = _post(
            client,
            "/lens/host/supervision/authority",
            {
                "approval_id": host_approval_id,
                "actor": actor,
                "reason": "grant bounded host supervision authority for isolated tray API proof",
                "lease_seconds": 600,
            },
        )
        host_receipt = _as_dict(host_grant.get("receipt"))

        runtime_request = _post(
            client,
            "/lens/resident-runtime/authority-grant/request",
            {
                "actor": actor,
                "reason": "operator wants resident runtime execution authority before tray API proof",
            },
        )
        runtime_approval_id = str(runtime_request["approval_id"])
        runtime_decision = _approve(
            client,
            approval_id=runtime_approval_id,
            comment="approve only resident runtime execution authority for isolated tray API proof",
        )
        runtime_grant = _post(
            client,
            "/lens/resident-runtime/authority-grant",
            {
                "approval_id": runtime_approval_id,
                "actor": actor,
                "reason": "grant bounded resident runtime execution authority for isolated tray API proof",
                "lease_seconds": 600,
            },
        )
        runtime_receipt = _as_dict(runtime_grant.get("receipt"))

        runtime_plan = _get(
            client,
            f"/lens/resident-runtime/plan?approval_id={runtime_approval_id}&actor={actor}",
        )
        resident_start = _post(
            client,
            "/lens/resident-runtime/execute",
            {
                "approval_id": runtime_approval_id,
                "actor": actor,
                "reason": "prove governed API path starts resident supervision before tray presence",
                "run_seconds": dependency_run_seconds,
            },
        )

        tray_request = _post(
            client,
            "/lens/tray/authority/request",
            {
                "actor": actor,
                "reason": "operator wants tray presence authority for API proof",
            },
        )
        tray_approval_id = str(tray_request["approval_id"])
        tray_decision = _approve(
            client,
            approval_id=tray_approval_id,
            comment="approve only tray presence authority for isolated API proof",
        )
        tray_grant = _post(
            client,
            "/lens/tray/authority",
            {
                "approval_id": tray_approval_id,
                "actor": actor,
                "reason": "grant bounded tray presence authority for isolated API proof",
                "lease_seconds": 600,
            },
        )
        tray_receipt = _as_dict(tray_grant.get("receipt"))

        tray_start = _post(
            client,
            "/lens/tray/execute",
            {
                "approval_id": tray_approval_id,
                "actor": actor,
                "reason": "prove governed API path starts the real tray presence runtime",
                "mode": "start",
                "run_seconds": dependency_run_seconds,
            },
        )
        tray_executions_after_start = _get(client, "/lens/tray/executions?limit=10")
        lens_status_after_tray_start = _get(client, "/lens/status?limit=10")
        resident_host = _as_dict(lens_status_after_tray_start.get("resident_host"))
        persistent_plan = _as_dict(resident_host.get("persistent_supervision_plan"))
        dependencies = _dependency_map(persistent_plan)
        tray_dependency = _as_dict(dependencies.get("tray_presence"))
        recommended_handoff = _as_dict(persistent_plan.get("first_missing_requirement_handoff"))

        tray_runtime_path = data_root / "runtime" / "lens-tray" / "status.json"
        tray_pid_path = data_root / "runtime" / "lens-tray" / "lens-tray.pid"
        tray_state_after_start = _read_json(tray_runtime_path)
        tray_pid_file_present_after_start = tray_pid_path.is_file()

        tray_stop = _stop_tray(
            client,
            approval_id=tray_approval_id,
            actor=actor,
            reason="stop tray presence runtime after isolated API proof",
        )
        tray_state_after_stop = _read_json(tray_runtime_path)
        tray_pid_file_present_after_stop = tray_pid_path.is_file()

        resident_stop = _stop_resident(
            client,
            approval_id=host_approval_id,
            actor=actor,
            reason="stop supervised resident host lease after isolated tray API proof",
        )
        host_pid_path = data_root / "runtime" / "lens-host" / "lens-host.pid"
        host_pid_file_present_after_stop = host_pid_path.is_file()

        host_governance = _as_dict(resident_start.get("governance"))
        tray_start_governance = _as_dict(tray_start.get("governance"))
        tray_stop_governance = _as_dict(tray_stop.get("governance"))
        next_gap = str(tray_start.get("next_smallest_truthful_gap") or "os_level_command_palette_binding")
        remaining_required = _str_list(persistent_plan.get("missing_required_before_enable"))
        blockers = _remaining_blockers(persistent_plan)
        tray_started = (
            tray_start.get("status") in {"tray_presence_started", "tray_presence_already_running"}
            and tray_start.get("executed") is True
            and tray_start.get("tray_presence") is True
            and tray_start.get("tray_runtime_ready") is True
            and tray_start.get("tray_icon_visible") is True
            and tray_state_after_start.get("status") == "tray_running"
            and tray_pid_file_present_after_start
        )
        plan_consumed_tray = (
            tray_dependency.get("ready") is True
            and tray_dependency.get("tray_presence_source") == "live_runtime_readback"
            and persistent_plan.get("first_missing_required_before_enable") == "global_hotkey_binding"
            and remaining_required == ["global_hotkey_binding", "overlay_window", "summon_binding"]
        )
        tray_stop_observed = (
            tray_stop.get("status") == "tray_presence_stopped"
            and tray_stop.get("executed") is True
            and tray_stop.get("tray_presence") is False
            and tray_pid_file_present_after_stop is False
        )
        resident_stop_observed = (
            resident_stop.get("status") == "resident_supervision_stopped"
            and resident_stop.get("resident_host_process") is False
            and resident_stop.get("resident_supervised_runtime") is False
            and host_pid_file_present_after_stop is False
        )
        authority_boundaries_intact = (
            host_governance.get("service_control_authority") is False
            and host_governance.get("resident_claim_authority") is False
            and tray_start_governance.get("tray_registration_authority") is True
            and tray_start_governance.get("tray_icon_authority") is True
            and tray_start_governance.get("hotkey_registration_authority") is False
            and tray_start_governance.get("overlay_control_authority") is False
            and tray_start_governance.get("summon_authority") is False
            and tray_start_governance.get("service_control_authority") is False
            and tray_start_governance.get("memory_write") is False
            and tray_start_governance.get("resident_claim_authority") is False
            and tray_stop_governance.get("memory_write") is False
            and tray_stop_governance.get("resident_claim_authority") is False
        )

        checks = [
            _check(
                "host_supervision_authority_granted",
                str(host_grant.get("status")),
                host_decision.get("status") == "approved"
                and host_grant.get("status") == "authority_granted"
                and bool(host_receipt.get("receipt_id")),
                "/lens/host/supervision/authority",
                "The proof must start from an exact host supervision authority grant.",
            ),
            _check(
                "resident_runtime_authority_granted",
                str(runtime_grant.get("status")),
                runtime_decision.get("status") == "approved"
                and runtime_grant.get("status") == "authority_granted"
                and bool(runtime_receipt.get("receipt_id")),
                "/lens/resident-runtime/authority-grant",
                "The resident runtime route requires a distinct execution authority grant.",
            ),
            _check(
                "resident_runtime_started_before_tray",
                str(resident_start.get("status")),
                resident_start.get("status") == "resident_supervision_started"
                and resident_start.get("resident_supervised_runtime") is True,
                "/lens/resident-runtime/execute",
                "Tray execution must be preceded by live resident supervision.",
            ),
            _check(
                "tray_authority_granted",
                str(tray_grant.get("status")),
                tray_decision.get("status") == "approved"
                and tray_grant.get("status") == "authority_granted"
                and bool(tray_receipt.get("receipt_id")),
                "/lens/tray/authority",
                "The tray route requires a distinct tray presence authority grant.",
            ),
            _check(
                "api_execute_started_real_tray_presence",
                str(tray_start.get("status")),
                tray_started,
                "/lens/tray/execute",
                "The API route must drive the real tray presence entrypoint in the isolated data root.",
            ),
            _check(
                "status_plan_consumed_live_tray_runtime",
                str(persistent_plan.get("first_missing_required_before_enable")),
                plan_consumed_tray,
                "/lens/status",
                "The persistent-supervision plan must consume live tray runtime readback and move to global hotkey.",
            ),
            _check(
                "tray_receipt_readback_after_start",
                str(tray_executions_after_start.get("status")),
                tray_executions_after_start.get("latest_tray_presence") is True
                and tray_executions_after_start.get("latest_next_smallest_truthful_gap")
                == "os_level_command_palette_binding",
                "/lens/tray/executions",
                "The tray execution readback must preserve the started-tray receipt.",
            ),
            _check(
                "api_stop_cleaned_real_tray_presence",
                str(tray_stop.get("status")),
                tray_stop_observed,
                "/lens/tray/execute",
                "The proof must stop the tray runtime and remove the tray pid file before returning.",
            ),
            _check(
                "resident_supervision_stop_observed",
                str(resident_stop.get("status")),
                resident_stop_observed,
                "/lens/host/supervision/execute",
                "The proof must stop the live resident supervisor after tray cleanup.",
            ),
            _check(
                "authority_boundaries_intact",
                "bounded" if authority_boundaries_intact else "leaked",
                authority_boundaries_intact,
                "response.governance",
                "The proof may start resident supervision and tray presence but must not gain hotkey, overlay, summon, service, memory, or resident-claim authority.",
            ),
        ]
        proof_passed = all(item["passed"] for item in checks)
        payload = {
            "ok": proof_passed,
            "kind": "lens.tray_presence.api_execution.proof",
            "status": "proof_passed" if proof_passed else "proof_failed",
            "mode": os.environ.get("FRANCIS_PROOF_MODE", "status"),
            "repo_root": str(repo_root),
            "data_root": str(data_root),
            "stage": "Stage 6 / Lens MVP",
            "stage_state": "active",
            "acceptance_criterion": "summon_anywhere",
            "previous_next_smallest_truthful_gap": "summon_tray_presence_blocker_boundary",
            "next_smallest_truthful_gap": next_gap,
            "recommended_next_slice": "prove_governed_os_binding_api_execution_after_tray_presence",
            "recommended_proof_script": "scripts/lens-os-binding-api-execution-proof.ps1 -Mode Status",
            "recommended_handoff_source": "api_tray_presence_execution_global_hotkey_handoff",
            "recommended_handoff": recommended_handoff,
            "host_supervision_approval_id": host_approval_id,
            "resident_runtime_approval_id": runtime_approval_id,
            "tray_presence_approval_id": tray_approval_id,
            "host_supervision_authority_grant_receipt_id": str(host_receipt.get("receipt_id") or ""),
            "resident_runtime_authority_grant_receipt_id": str(runtime_receipt.get("receipt_id") or ""),
            "tray_authority_grant_receipt_id": str(tray_receipt.get("receipt_id") or ""),
            "resident_runtime_plan_ready": runtime_plan.get("bounded_resident_candidate_ready") is True,
            "resident_runtime_execution_authority": runtime_grant.get("authority_granted") is True,
            "host_supervision_authority": host_grant.get("authority_granted") is True,
            "tray_presence_authority": tray_grant.get("authority_granted") is True,
            "execution_applied": tray_start.get("applied") is True,
            "executed": tray_start.get("executed") is True,
            "resident_host_process_started": resident_start.get("resident_host_process") is True,
            "resident_supervised_runtime_started": resident_start.get("resident_supervised_runtime") is True,
            "tray_presence_started": tray_start.get("tray_presence") is True,
            "tray_runtime_ready": tray_start.get("tray_runtime_ready") is True,
            "tray_icon_visible": tray_start.get("tray_icon_visible") is True,
            "tray_presence_stop_observed": tray_stop_observed,
            "resident_supervision_stop_observed": resident_stop_observed,
            "tray_pid_file_present_after_start": tray_pid_file_present_after_start,
            "tray_pid_file_present_after_stop": tray_pid_file_present_after_stop,
            "host_pid_file_present_after_stop": host_pid_file_present_after_stop,
            "required_before_enable_after_tray": remaining_required,
            "global_hotkey": False,
            "overlay_window": False,
            "summon_anywhere": False,
            "service_managed": False,
            "resident_claim_allowed": False,
            "checks": checks,
            "blockers": blockers,
            "proof": {
                "resident_start_status": str(resident_start.get("status") or ""),
                "tray_start_status": str(tray_start.get("status") or ""),
                "tray_runtime_status_after_start": str(tray_state_after_start.get("status") or ""),
                "tray_runtime_pid_after_start": int(tray_state_after_start.get("pid") or 0),
                "tray_stop_status": str(tray_stop.get("status") or ""),
                "tray_runtime_status_after_stop": str(tray_state_after_stop.get("status") or ""),
                "resident_stop_status": str(resident_stop.get("status") or ""),
                "tray_receipt_readback_status": str(tray_executions_after_start.get("status") or ""),
                "tray_receipt_readback_next_gap": str(
                    tray_executions_after_start.get("latest_next_smallest_truthful_gap") or ""
                ),
                "persistent_plan_first_missing_after_tray": str(
                    persistent_plan.get("first_missing_required_before_enable") or ""
                ),
                "tray_dependency_source": str(tray_dependency.get("tray_presence_source") or ""),
            },
            "start_execution": {
                "status": tray_start.get("status"),
                "next_smallest_truthful_gap": tray_start.get("next_smallest_truthful_gap"),
                "tray_presence": tray_start.get("tray_presence"),
                "tray_runtime_ready": tray_start.get("tray_runtime_ready"),
                "tray_icon_visible": tray_start.get("tray_icon_visible"),
                "resident_claim_allowed": tray_start.get("resident_claim_allowed"),
                "stop_command": tray_start.get("stop_command"),
            },
            "stop_execution": {
                "status": tray_stop.get("status"),
                "tray_presence": tray_stop.get("tray_presence"),
                "tray_runtime_ready": tray_stop.get("tray_runtime_ready"),
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
                "tray_registration_authority": True,
                "tray_icon_authority": True,
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
                "The governed API path can start and stop real Lens tray presence in an isolated data root "
                "after resident supervision is live. The proof still stops before global hotkey, overlay, "
                "summon-anywhere, service management, memory writes, and resident-claim authority."
            ),
        }
        return (0 if proof_passed else 1), payload
    finally:
        if not (tray_stop.get("status") == "tray_presence_stopped" and tray_stop.get("tray_presence") is False):
            try:
                fallback_stop = _stop_tray(
                    client,
                    approval_id=tray_approval_id,
                    actor=actor,
                    reason="fallback cleanup for tray presence API execution proof",
                )
            except Exception as exc:
                fallback_stop = {
                    "ok": False,
                    "status": "fallback_tray_stop_failed",
                    "error": str(exc),
                }
        if not (
            resident_stop.get("status") == "resident_supervision_stopped"
            and resident_stop.get("resident_host_process") is False
            and resident_stop.get("resident_supervised_runtime") is False
        ):
            try:
                fallback_stop = _stop_resident(
                    client,
                    approval_id=host_approval_id,
                    actor=actor,
                    reason="fallback cleanup for tray presence API execution proof",
                )
            except Exception as exc:
                fallback_stop = {
                    "ok": False,
                    "status": "fallback_resident_stop_failed",
                    "error": str(exc),
                }
        if str(fallback_stop.get("status", "")).endswith("_failed"):
            raise RuntimeError(f"tray presence API proof cleanup failed: {fallback_stop!r}")


try:
    exit_code, payload = _run()
except Exception as exc:
    exit_code = 1
    payload = {
        "ok": False,
        "kind": "lens.tray_presence.api_execution.proof",
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
  $ProofRuntimeDir = Join-Path $ProofDataRoot 'runtime\lens-tray-presence-api-execution-proof'
  New-Item -ItemType Directory -Force -Path $ProofRuntimeDir | Out-Null
  $PythonScriptPath = Join-Path $ProofRuntimeDir 'proof.py'
  Set-Content -LiteralPath $PythonScriptPath -Value $Source -Encoding UTF8
  $Output = & $PythonPath $PythonScriptPath 2>&1
  $ExitCode = $LASTEXITCODE
} finally {
  & (Join-Path $PSScriptRoot 'lens-tray-presence.ps1') -Mode Stop -DataDir $ProofDataRoot *> $null
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
