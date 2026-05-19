[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(1, 60)]
  [int]$RunSeconds = 5,

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
  $DataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-summon-api-execution-proof\" + [guid]::NewGuid().ToString('N') + "\data")
}

$ProofDataRoot = [System.IO.Path]::GetFullPath($DataDir)
$PythonPath = Get-PythonPath
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
  [ordered]@{
    ok = $false
    kind = 'lens.summon.api_execution.proof'
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


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return _as_dict(json.loads(path.read_text(encoding="utf-8-sig")))


def _stop_overlay(client: Any, *, approval_id: str, actor: str, reason: str) -> dict[str, Any]:
    if not approval_id:
        return {"ok": False, "status": "stop_skipped_no_overlay_approval_id", "overlay_window": True}
    return _post(
        client,
        "/lens/overlay/execute",
        {
            "approval_id": approval_id,
            "actor": actor,
            "reason": reason,
            "mode": "stop",
            "run_seconds": 1,
        },
    )


def _stop_hotkey(client: Any, *, approval_id: str, actor: str, reason: str) -> dict[str, Any]:
    if not approval_id:
        return {"ok": False, "status": "stop_skipped_no_os_binding_approval_id", "global_hotkey_binding": True}
    return _post(
        client,
        "/lens/os-binding/execute",
        {
            "approval_id": approval_id,
            "actor": actor,
            "reason": reason,
            "mode": "stop",
            "run_seconds": 1,
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


def _request_approve_grant(
    client: Any,
    *,
    request_route: str,
    grant_route: str,
    actor: str,
    request_reason: str,
    approve_comment: str,
    grant_reason: str,
) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    request = _post(client, request_route, {"actor": actor, "reason": request_reason})
    approval_id = str(request["approval_id"])
    decision = _approve(client, approval_id=approval_id, comment=approve_comment)
    grant = _post(
        client,
        grant_route,
        {
            "approval_id": approval_id,
            "actor": actor,
            "reason": grant_reason,
            "lease_seconds": 600,
        },
    )
    return approval_id, request, decision, grant


def _run() -> tuple[int, dict[str, Any]]:
    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.world_state.operator_mode import set_control_mode

    repo_root = Path(os.environ["FRANCIS_ROOT"]).resolve()
    data_root = Path(os.environ["FRANCIS_DATA_DIR"]).resolve()
    run_seconds = int(os.environ.get("FRANCIS_PROOF_RUN_SECONDS", "5"))
    resident_dependency_run_seconds = 10
    dependency_run_seconds = max(run_seconds, 20)
    data_root.mkdir(parents=True, exist_ok=True)

    actor = "test.system.write"
    set_control_mode(
        "assist",
        reason="prove Lens summon API execution path",
        actor=actor,
    )

    client = TestClient(create_app())
    host_approval_id = ""
    runtime_approval_id = ""
    tray_approval_id = ""
    os_binding_approval_id = ""
    overlay_approval_id = ""
    summon_approval_id = ""
    overlay_stop: dict[str, Any] = {}
    hotkey_stop: dict[str, Any] = {}
    tray_stop: dict[str, Any] = {}
    resident_stop: dict[str, Any] = {}
    cleanup_errors: list[str] = []
    try:
        host_approval_id, host_request, host_decision, host_grant = _request_approve_grant(
            client,
            request_route="/lens/host/supervision/authority/request",
            grant_route="/lens/host/supervision/authority",
            actor=actor,
            request_reason="operator wants host supervision authority before summon API proof",
            approve_comment="approve only host supervision authority for isolated summon API proof",
            grant_reason="grant bounded host supervision authority for isolated summon API proof",
        )
        host_receipt = _as_dict(host_grant.get("receipt"))

        runtime_approval_id, runtime_request, runtime_decision, runtime_grant = _request_approve_grant(
            client,
            request_route="/lens/resident-runtime/authority-grant/request",
            grant_route="/lens/resident-runtime/authority-grant",
            actor=actor,
            request_reason="operator wants resident runtime execution authority before summon API proof",
            approve_comment="approve only resident runtime execution authority for isolated summon API proof",
            grant_reason="grant bounded resident runtime execution authority for isolated summon API proof",
        )
        runtime_receipt = _as_dict(runtime_grant.get("receipt"))

        resident_start = _post(
            client,
            "/lens/resident-runtime/execute",
            {
                "approval_id": runtime_approval_id,
                "actor": actor,
                "reason": "prove governed API path starts resident supervision before summon",
                "run_seconds": resident_dependency_run_seconds,
            },
        )

        tray_approval_id, tray_request, tray_decision, tray_grant = _request_approve_grant(
            client,
            request_route="/lens/tray/authority/request",
            grant_route="/lens/tray/authority",
            actor=actor,
            request_reason="operator wants tray presence authority before summon API proof",
            approve_comment="approve only tray presence authority for isolated summon API proof",
            grant_reason="grant bounded tray presence authority for isolated summon API proof",
        )
        tray_receipt = _as_dict(tray_grant.get("receipt"))
        tray_start = _post(
            client,
            "/lens/tray/execute",
            {
                "approval_id": tray_approval_id,
                "actor": actor,
                "reason": "prove governed API path starts tray presence before summon",
                "mode": "start",
                "run_seconds": dependency_run_seconds,
            },
        )

        os_binding_approval_id, os_binding_request, os_binding_decision, os_binding_grant = _request_approve_grant(
            client,
            request_route="/lens/os-binding/authority/request",
            grant_route="/lens/os-binding/authority",
            actor=actor,
            request_reason="operator wants OS-binding authority before summon API proof",
            approve_comment="approve only OS-binding authority for isolated summon API proof",
            grant_reason="grant bounded OS-binding authority for isolated summon API proof",
        )
        os_binding_receipt = _as_dict(os_binding_grant.get("receipt"))
        hotkey_start = _post(
            client,
            "/lens/os-binding/execute",
            {
                "approval_id": os_binding_approval_id,
                "actor": actor,
                "reason": "prove governed API path starts hotkey before summon",
                "mode": "bind",
                "run_seconds": dependency_run_seconds,
            },
        )

        overlay_approval_id, overlay_request, overlay_decision, overlay_grant = _request_approve_grant(
            client,
            request_route="/lens/overlay/authority/request",
            grant_route="/lens/overlay/authority",
            actor=actor,
            request_reason="operator wants overlay window authority before summon API proof",
            approve_comment="approve only overlay window authority for isolated summon API proof",
            grant_reason="grant bounded overlay window authority for isolated summon API proof",
        )
        overlay_receipt = _as_dict(overlay_grant.get("receipt"))
        overlay_start = _post(
            client,
            "/lens/overlay/execute",
            {
                "approval_id": overlay_approval_id,
                "actor": actor,
                "reason": "prove governed API path starts overlay before summon",
                "mode": "start",
                "run_seconds": dependency_run_seconds,
            },
        )

        summon_readiness_before_execute = _get(client, "/lens/summon/readiness")
        summon_approval_id, summon_request, summon_decision, summon_grant = _request_approve_grant(
            client,
            request_route="/lens/summon/authority/request",
            grant_route="/lens/summon/authority",
            actor=actor,
            request_reason="operator wants bounded summon action authority for API proof",
            approve_comment="approve only bounded local summon action authority for isolated summon API proof",
            grant_reason="grant bounded local summon action authority for isolated summon API proof",
        )
        summon_receipt = _as_dict(summon_grant.get("receipt"))

        summon_execute = _post(
            client,
            "/lens/summon/execute",
            {
                "approval_id": summon_approval_id,
                "actor": actor,
                "reason": "prove governed API path executes bounded local summon handoff without launch",
                "mode": "launch",
                "run_seconds": run_seconds,
                "allow_launch": False,
            },
        )
        summon_executions_after_execute = _get(client, "/lens/summon/executions?limit=10")
        summon_readiness_after_execute = _get(client, "/lens/summon/readiness")
        lens_status_after_summon = _get(client, "/lens/status?limit=10")
        resident_host = _as_dict(lens_status_after_summon.get("resident_host"))
        persistent_plan = _as_dict(resident_host.get("persistent_supervision_plan"))
        dependencies = _dependency_map(persistent_plan)
        summon_dependency = _as_dict(dependencies.get("summon_binding"))

        summon_runtime_path = data_root / "runtime" / "lens-summon" / "status.json"
        summon_state_after_execute = _read_json(summon_runtime_path)
        summon_override_path = data_root / "runtime" / "lens-summon" / "summon-action-override.json"
        summon_override_present = summon_override_path.is_file()

        overlay_stop = _stop_overlay(
            client,
            approval_id=overlay_approval_id,
            actor=actor,
            reason="stop overlay runtime after isolated summon API proof",
        )
        overlay_pid_path = data_root / "runtime" / "lens-overlay" / "lens-overlay.pid"
        overlay_pid_file_present_after_stop = overlay_pid_path.is_file()

        hotkey_stop = _stop_hotkey(
            client,
            approval_id=os_binding_approval_id,
            actor=actor,
            reason="stop global hotkey runtime after isolated summon API proof",
        )
        hotkey_pid_path = data_root / "runtime" / "lens-hotkey" / "lens-hotkey.pid"
        hotkey_pid_file_present_after_stop = hotkey_pid_path.is_file()

        tray_stop = _stop_tray(
            client,
            approval_id=tray_approval_id,
            actor=actor,
            reason="stop tray presence runtime after isolated summon API proof",
        )
        tray_pid_path = data_root / "runtime" / "lens-tray" / "lens-tray.pid"
        tray_pid_file_present_after_stop = tray_pid_path.is_file()

        resident_stop = _stop_resident(
            client,
            approval_id=host_approval_id,
            actor=actor,
            reason="stop supervised resident host lease after isolated summon API proof",
        )
        host_pid_path = data_root / "runtime" / "lens-host" / "lens-host.pid"
        host_pid_file_present_after_stop = host_pid_path.is_file()

        host_governance = _as_dict(resident_start.get("governance"))
        tray_governance = _as_dict(tray_start.get("governance"))
        hotkey_governance = _as_dict(hotkey_start.get("governance"))
        overlay_governance = _as_dict(overlay_start.get("governance"))
        summon_governance = _as_dict(summon_execute.get("governance"))
        remaining_required = _str_list(persistent_plan.get("missing_required_before_enable"))
        route_next_gap = str(summon_execute.get("next_smallest_truthful_gap") or "summon_anywhere_runtime_readback")
        persistent_plan_next_gap = str(
            persistent_plan.get("next_smallest_truthful_gap") or "persistent_supervision_authority_not_granted"
        )
        next_gap = route_next_gap or persistent_plan_next_gap
        summon_runtime_readback = _as_dict(summon_execute.get("summon_runtime_readback"))
        summon_started = (
            summon_execute.get("status") == "summon_binding_observed"
            and summon_execute.get("executed") is True
            and summon_execute.get("summon_binding") is True
            and summon_execute.get("summon_runtime_ready") is True
            and summon_execute.get("bounded_handoff_ready") is True
            and summon_execute.get("local_open_ready") is True
            and summon_execute.get("opened") is False
            and summon_execute.get("no_launch") is True
        )
        runtime_state_observed = (
            summon_state_after_execute.get("kind") == "lens.summon.runtime_state"
            and summon_state_after_execute.get("status") == "summon_binding_observed"
            and summon_state_after_execute.get("bounded_handoff_ready") is True
            and summon_state_after_execute.get("local_open_ready") is True
            and summon_state_after_execute.get("opened") is False
            and summon_state_after_execute.get("no_launch") is True
            and summon_state_after_execute.get("summon_anywhere") is False
            and summon_state_after_execute.get("os_level_summon") is False
        )
        plan_consumed_summon = (
            summon_dependency.get("ready") is True
            and summon_dependency.get("summon_runtime_ready") is True
            and remaining_required == []
            and persistent_plan.get("required_before_enable_ready") is True
        )
        summon_receipt_readback = (
            summon_executions_after_execute.get("status") == "readback_ready"
            and summon_executions_after_execute.get("latest_summon_binding") is True
            and summon_executions_after_execute.get("latest_summon_anywhere") is False
        )
        summon_readiness_observed = (
            summon_readiness_after_execute.get("summon_binding_ready") is True
            and summon_readiness_after_execute.get("summon_runtime_ready") is True
            and summon_readiness_after_execute.get("summon_runtime_bounded_handoff_ready") is True
            and summon_readiness_after_execute.get("summon_runtime_local_open_ready") is True
            and "summon_anywhere_runtime_readback" in _str_list(summon_readiness_after_execute.get("blockers"))
        )
        overlay_stop_observed = (
            overlay_stop.get("status") == "overlay_window_stopped"
            and overlay_stop.get("executed") is True
            and overlay_stop.get("overlay_window") is False
            and overlay_pid_file_present_after_stop is False
        )
        hotkey_stop_observed = (
            hotkey_stop.get("status") == "global_hotkey_binding_stopped"
            and hotkey_stop.get("executed") is True
            and hotkey_stop.get("global_hotkey_binding") is False
            and hotkey_pid_file_present_after_stop is False
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
            and tray_governance.get("summon_authority") is False
            and hotkey_governance.get("summon_authority") is False
            and overlay_governance.get("summon_authority") is False
            and summon_governance.get("execution_authority") is True
            and summon_governance.get("summon_authority") is True
            and summon_governance.get("bounded_local_open_handoff_authority") is True
            and summon_governance.get("local_process_launch_authority") is False
            and summon_governance.get("mutation_authority_granted") is False
            and summon_governance.get("hotkey_registration_authority") is False
            and summon_governance.get("overlay_control_authority") is False
            and summon_governance.get("summon_anywhere_authority") is False
            and summon_governance.get("os_level_summon_authority") is False
            and summon_governance.get("memory_write") is False
            and summon_governance.get("resident_claim_authority") is False
            and summon_governance.get("approval_decision_authority") is False
        )
        checks = [
            _check(
                "host_supervision_authority_granted",
                "authority_granted" if host_grant.get("authority_granted") is True else "blocked",
                host_grant.get("authority_granted") is True and bool(host_receipt.get("receipt_id")),
                "/lens/host/supervision/authority",
                "The proof must start from explicit host supervision authority.",
            ),
            _check(
                "resident_tray_hotkey_overlay_started_before_summon",
                "ready"
                if (
                    resident_start.get("resident_supervised_runtime") is True
                    and tray_start.get("tray_presence") is True
                    and hotkey_start.get("global_hotkey_binding") is True
                    and overlay_start.get("overlay_window") is True
                )
                else "blocked",
                resident_start.get("resident_supervised_runtime") is True
                and tray_start.get("tray_runtime_ready") is True
                and hotkey_start.get("hotkey_runtime_ready") is True
                and overlay_start.get("overlay_runtime_ready") is True,
                "/lens/resident-runtime/execute + /lens/tray/execute + /lens/os-binding/execute + /lens/overlay/execute",
                "The proof must carry forward the previously proved resident, tray, hotkey, and overlay runtimes.",
            ),
            _check(
                "summon_authority_granted",
                "authority_granted" if summon_grant.get("authority_granted") is True else "blocked",
                summon_grant.get("authority_granted") is True and bool(summon_receipt.get("receipt_id")),
                "/lens/summon/authority",
                "The proof must grant exact bounded summon action authority before execution.",
            ),
            _check(
                "api_execute_observed_bounded_summon_handoff",
                "summon_binding_observed" if summon_started else str(summon_execute.get("status") or "blocked"),
                summon_started,
                "/lens/summon/execute",
                "The governed route must execute a bounded local summon handoff without launching a process.",
            ),
            _check(
                "summon_runtime_state_written",
                str(summon_state_after_execute.get("status") or ""),
                runtime_state_observed,
                "data/runtime/lens-summon/status.json",
                "The proof must write isolated summon runtime readback for the host plan to consume.",
            ),
            _check(
                "status_plan_consumed_live_summon_runtime",
                str(persistent_plan.get("first_missing_required_before_enable") or ""),
                plan_consumed_summon,
                "/lens/status resident_host.persistent_supervision_plan",
                "The persistent supervision plan must consume live summon runtime and clear required-before-enable blockers.",
            ),
            _check(
                "summon_receipt_readback_after_execute",
                str(summon_executions_after_execute.get("status") or ""),
                summon_receipt_readback,
                "/lens/summon/executions?limit=10",
                "The summon execution receipt must be readable after execution.",
            ),
            _check(
                "summon_readiness_consumes_runtime_without_closure",
                str(summon_readiness_after_execute.get("status") or ""),
                summon_readiness_observed,
                "/lens/summon/readiness",
                "The route must expose summon runtime readback while preserving the final summon-anywhere runtime boundary.",
            ),
            _check(
                "api_stop_cleaned_real_overlay_window",
                "overlay_window_stopped" if overlay_stop_observed else str(overlay_stop.get("status") or "blocked"),
                overlay_stop_observed,
                "/lens/overlay/execute",
                "The proof must stop the live overlay window after readback.",
            ),
            _check(
                "api_stop_cleaned_real_global_hotkey",
                "global_hotkey_binding_stopped" if hotkey_stop_observed else str(hotkey_stop.get("status") or "blocked"),
                hotkey_stop_observed,
                "/lens/os-binding/execute",
                "The proof must stop the live global hotkey after cleanup.",
            ),
            _check(
                "api_stop_cleaned_real_tray_presence",
                "tray_presence_stopped" if tray_stop_observed else str(tray_stop.get("status") or "blocked"),
                tray_stop_observed,
                "/lens/tray/execute",
                "The proof must stop the live tray presence after cleanup.",
            ),
            _check(
                "resident_supervision_stop_observed",
                "resident_supervision_stopped" if resident_stop_observed else str(resident_stop.get("status") or "blocked"),
                resident_stop_observed,
                "/lens/host/supervision/execute",
                "The proof must stop the live resident supervisor after cleanup.",
            ),
            _check(
                "authority_boundaries_intact",
                "bounded" if authority_boundaries_intact else "leaked",
                authority_boundaries_intact,
                "response.governance",
                "The proof may execute a bounded local summon handoff but must not launch, write memory, claim OS-level summon, or claim resident authority.",
            ),
        ]
        proof_passed = all(item["passed"] for item in checks)
        payload = {
            "ok": proof_passed,
            "kind": "lens.summon.api_execution.proof",
            "status": "proof_passed" if proof_passed else "proof_failed",
            "mode": os.environ.get("FRANCIS_PROOF_MODE", "status"),
            "repo_root": str(repo_root),
            "data_root": str(data_root),
            "stage": "Stage 6 / Lens MVP",
            "stage_state": "active",
            "acceptance_criterion": "summon_anywhere",
            "previous_next_smallest_truthful_gap": "summon_binding_blocker_boundary",
            "route_next_smallest_truthful_gap": route_next_gap,
            "persistent_plan_next_smallest_truthful_gap": persistent_plan_next_gap,
            "next_smallest_truthful_gap": next_gap,
            "recommended_next_slice": "review_stage6_runtime_readback_after_bounded_summon_handoff",
            "recommended_proof_script": "scripts/lens-stage6-next-handoff.ps1 -Mode Status",
            "recommended_handoff_source": "api_summon_execution_runtime_readback_handoff",
            "host_supervision_approval_id": host_approval_id,
            "resident_runtime_approval_id": runtime_approval_id,
            "tray_presence_approval_id": tray_approval_id,
            "os_binding_approval_id": os_binding_approval_id,
            "overlay_approval_id": overlay_approval_id,
            "summon_approval_id": summon_approval_id,
            "host_supervision_authority_grant_receipt_id": str(host_receipt.get("receipt_id") or ""),
            "resident_runtime_authority_grant_receipt_id": str(runtime_receipt.get("receipt_id") or ""),
            "tray_authority_grant_receipt_id": str(tray_receipt.get("receipt_id") or ""),
            "os_binding_authority_grant_receipt_id": str(os_binding_receipt.get("receipt_id") or ""),
            "overlay_authority_grant_receipt_id": str(overlay_receipt.get("receipt_id") or ""),
            "summon_authority_grant_receipt_id": str(summon_receipt.get("receipt_id") or ""),
            "resident_runtime_execution_authority": runtime_grant.get("authority_granted") is True,
            "host_supervision_authority": host_grant.get("authority_granted") is True,
            "tray_presence_authority": tray_grant.get("authority_granted") is True,
            "os_binding_authority": os_binding_grant.get("authority_granted") is True,
            "overlay_authority": overlay_grant.get("authority_granted") is True,
            "summon_authority": summon_grant.get("authority_granted") is True,
            "execution_applied": summon_execute.get("applied") is True,
            "executed": summon_execute.get("executed") is True,
            "resident_host_process_started": resident_start.get("resident_host_process") is True,
            "resident_supervised_runtime_started": resident_start.get("resident_supervised_runtime") is True,
            "tray_presence_started": tray_start.get("tray_presence") is True,
            "tray_runtime_ready": tray_start.get("tray_runtime_ready") is True,
            "global_hotkey_bound": hotkey_start.get("global_hotkey_binding") is True,
            "hotkey_runtime_ready": hotkey_start.get("hotkey_runtime_ready") is True,
            "overlay_window_started": overlay_start.get("overlay_window") is True,
            "overlay_runtime_ready": overlay_start.get("overlay_runtime_ready") is True,
            "summon_binding_observed": summon_execute.get("summon_binding") is True,
            "summon_runtime_ready": summon_execute.get("summon_runtime_ready") is True,
            "bounded_handoff_ready": summon_execute.get("bounded_handoff_ready") is True,
            "local_open_ready": summon_execute.get("local_open_ready") is True,
            "opened": summon_execute.get("opened") is True,
            "no_launch": summon_execute.get("no_launch") is True,
            "receipt_written": summon_execute.get("receipt_written") is True,
            "summon_runtime_state_observed": runtime_state_observed,
            "summon_runtime_state_path": str(summon_runtime_path),
            "summon_config_override_present": summon_override_present,
            "overlay_stop_observed": overlay_stop_observed,
            "hotkey_stop_observed": hotkey_stop_observed,
            "tray_presence_stop_observed": tray_stop_observed,
            "resident_supervision_stop_observed": resident_stop_observed,
            "overlay_pid_file_present_after_stop": overlay_pid_file_present_after_stop,
            "hotkey_pid_file_present_after_stop": hotkey_pid_file_present_after_stop,
            "tray_pid_file_present_after_stop": tray_pid_file_present_after_stop,
            "host_pid_file_present_after_stop": host_pid_file_present_after_stop,
            "required_before_enable_after_summon": remaining_required,
            "required_before_enable_ready_after_summon": persistent_plan.get("required_before_enable_ready") is True,
            "summon_readiness_status_after_execute": str(summon_readiness_after_execute.get("status") or ""),
            "summon_readiness_summon_runtime_ready": summon_readiness_after_execute.get("summon_runtime_ready") is True,
            "summon_readiness_blockers_after_execute": _str_list(summon_readiness_after_execute.get("blockers")),
            "blockers": _str_list(summon_execute.get("blockers")),
            "summon_anywhere": False,
            "os_level_summon": False,
            "service_managed": False,
            "resident_claim_allowed": False,
            "checks": checks,
            "proof": {
                "resident_start_status": str(resident_start.get("status") or ""),
                "tray_start_status": str(tray_start.get("status") or ""),
                "hotkey_start_status": str(hotkey_start.get("status") or ""),
                "overlay_start_status": str(overlay_start.get("status") or ""),
                "summon_execute_status": str(summon_execute.get("status") or ""),
                "summon_receipt_readback_status": str(summon_executions_after_execute.get("status") or ""),
                "summon_receipt_readback_next_gap": str(
                    summon_executions_after_execute.get("latest_next_smallest_truthful_gap") or ""
                ),
                "summon_readiness_before_execute_status": str(summon_readiness_before_execute.get("status") or ""),
                "summon_readiness_after_execute_status": str(summon_readiness_after_execute.get("status") or ""),
                "summon_runtime_state_status": str(summon_state_after_execute.get("status") or ""),
                "summon_runtime_readback_status": str(summon_runtime_readback.get("status") or ""),
                "persistent_plan_first_missing_after_summon": str(
                    persistent_plan.get("first_missing_required_before_enable") or ""
                ),
                "persistent_plan_next_smallest_truthful_gap": persistent_plan_next_gap,
                "overlay_stop_status": str(overlay_stop.get("status") or ""),
                "hotkey_stop_status": str(hotkey_stop.get("status") or ""),
                "tray_stop_status": str(tray_stop.get("status") or ""),
                "resident_stop_status": str(resident_stop.get("status") or ""),
            },
            "start_execution": {
                "status": str(summon_execute.get("status") or ""),
                "next_smallest_truthful_gap": str(summon_execute.get("next_smallest_truthful_gap") or ""),
                "summon_binding": summon_execute.get("summon_binding") is True,
                "summon_runtime_ready": summon_execute.get("summon_runtime_ready") is True,
                "bounded_handoff_ready": summon_execute.get("bounded_handoff_ready") is True,
                "local_open_ready": summon_execute.get("local_open_ready") is True,
                "opened": summon_execute.get("opened") is True,
                "no_launch": summon_execute.get("no_launch") is True,
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
                "local_process_launch_authority": False,
                "process_supervision_authority": True,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": True,
                "tray_icon_authority": True,
                "hotkey_registration_authority": True,
                "overlay_control_authority": True,
                "window_management_authority": True,
                "bounded_local_open_handoff_authority": True,
                "summon_authority": True,
                "summon_anywhere_authority": False,
                "os_level_summon_authority": False,
                "capture_authority": False,
                "new_sensing_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
                "mutation_authority_granted": True,
            },
            "notes": (
                "This proof executes a bounded local summon handoff only. It does not claim "
                "Stage 6 closure, OS-wide summon-anywhere readiness, memory write, capture, "
                "service control, product approval-decision authority, or resident-claim authority."
            ),
        }
        return (0 if proof_passed else 1), payload
    finally:
        try:
            if not (
                overlay_stop.get("status") == "overlay_window_stopped"
                and overlay_stop.get("overlay_window") is False
            ):
                _stop_overlay(
                    client,
                    approval_id=overlay_approval_id,
                    actor=actor,
                    reason="fallback cleanup for summon API execution proof",
                )
        except Exception as exc:
            cleanup_errors.append(f"overlay_stop_failed:{exc}")
        try:
            if not (
                hotkey_stop.get("status") == "global_hotkey_binding_stopped"
                and hotkey_stop.get("global_hotkey_binding") is False
            ):
                _stop_hotkey(
                    client,
                    approval_id=os_binding_approval_id,
                    actor=actor,
                    reason="fallback cleanup for summon API execution proof",
                )
        except Exception as exc:
            cleanup_errors.append(f"hotkey_stop_failed:{exc}")
        try:
            if not (tray_stop.get("status") == "tray_presence_stopped" and tray_stop.get("tray_presence") is False):
                _stop_tray(
                    client,
                    approval_id=tray_approval_id,
                    actor=actor,
                    reason="fallback cleanup for summon API execution proof",
                )
        except Exception as exc:
            cleanup_errors.append(f"tray_stop_failed:{exc}")
        try:
            if not (
                resident_stop.get("status") == "resident_supervision_stopped"
                and resident_stop.get("resident_host_process") is False
                and resident_stop.get("resident_supervised_runtime") is False
            ):
                _stop_resident(
                    client,
                    approval_id=host_approval_id,
                    actor=actor,
                    reason="fallback cleanup for summon API execution proof",
                )
        except Exception as exc:
            cleanup_errors.append(f"resident_stop_failed:{exc}")
        if cleanup_errors:
            raise RuntimeError(f"summon API proof cleanup failed: {cleanup_errors!r}")


try:
    exit_code, payload = _run()
except Exception as exc:
    exit_code = 1
    payload = {
        "ok": False,
        "kind": "lens.summon.api_execution.proof",
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
  $ProofRuntimeDir = Join-Path $ProofDataRoot 'runtime\lens-summon-api-execution-proof'
  New-Item -ItemType Directory -Force -Path $ProofRuntimeDir | Out-Null
  $PythonScriptPath = Join-Path $ProofRuntimeDir 'proof.py'
  Set-Content -LiteralPath $PythonScriptPath -Value $Source -Encoding UTF8
  $Output = & $PythonPath $PythonScriptPath 2>&1
  $ExitCode = $LASTEXITCODE
} finally {
  & (Join-Path $PSScriptRoot 'lens-overlay-window.ps1') -Mode Stop -DataDir $ProofDataRoot *> $null
  & (Join-Path $PSScriptRoot 'lens-hotkey-binding.ps1') -Mode Stop -DataDir $ProofDataRoot *> $null
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
