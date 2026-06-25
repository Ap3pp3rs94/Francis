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
  $DataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-overlay-api-execution-proof\" + [guid]::NewGuid().ToString('N') + "\data")
}

$ProofDataRoot = [System.IO.Path]::GetFullPath($DataDir)
$PythonPath = Get-PythonPath
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
  [ordered]@{
    ok = $false
    kind = 'lens.overlay.api_execution.proof'
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
import time
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


def _overlay_started(result: dict[str, Any]) -> bool:
    return (
        result.get("status") in {"overlay_window_started", "overlay_window_already_running"}
        and result.get("executed") is True
        and result.get("overlay_window") is True
        and result.get("overlay_runtime_ready") is True
    )


def _start_overlay_with_retry(
    client: Any,
    *,
    approval_id: str,
    actor: str,
    reason: str,
    run_seconds: int,
) -> tuple[dict[str, Any], int]:
    payload = {
        "approval_id": approval_id,
        "actor": actor,
        "reason": reason,
        "mode": "start",
        "run_seconds": run_seconds,
    }
    first = _post(client, "/lens/overlay/execute", payload)
    if _overlay_started(first) or first.get("status") != "overlay_window_start_failed":
        return first, 0
    _stop_overlay(
        client,
        approval_id=approval_id,
        actor=actor,
        reason="stop overlay runtime before bounded overlay API proof retry",
    )
    retry_payload = dict(payload)
    retry_payload["reason"] = f"{reason} after bounded overlay start retry"
    return _post(client, "/lens/overlay/execute", retry_payload), 1


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
    proof_global_hotkey = os.environ.get("FRANCIS_PROOF_GLOBAL_HOTKEY", "Ctrl+Alt+Shift+F12").strip()
    # Keep dependency leases within the governed route cap; refresh them before slow readbacks.
    dependency_run_seconds = max(run_seconds, 60)
    data_root.mkdir(parents=True, exist_ok=True)

    actor = "test.system.write"
    set_control_mode(
        "assist",
        reason="prove Lens overlay API execution path",
        actor=actor,
    )

    client = TestClient(create_app())
    host_approval_id = ""
    runtime_approval_id = ""
    tray_approval_id = ""
    os_binding_approval_id = ""
    overlay_approval_id = ""
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
            request_reason="operator wants host supervision authority before overlay API proof",
            approve_comment="approve only host supervision authority for isolated overlay API proof",
            grant_reason="grant bounded host supervision authority for isolated overlay API proof",
        )
        host_receipt = _as_dict(host_grant.get("receipt"))

        runtime_approval_id, runtime_request, runtime_decision, runtime_grant = _request_approve_grant(
            client,
            request_route="/lens/resident-runtime/authority-grant/request",
            grant_route="/lens/resident-runtime/authority-grant",
            actor=actor,
            request_reason="operator wants resident runtime execution authority before overlay API proof",
            approve_comment="approve only resident runtime execution authority for isolated overlay API proof",
            grant_reason="grant bounded resident runtime execution authority for isolated overlay API proof",
        )
        runtime_receipt = _as_dict(runtime_grant.get("receipt"))

        resident_start = _post(
            client,
            "/lens/resident-runtime/execute",
            {
                "approval_id": runtime_approval_id,
                "actor": actor,
                "reason": "prove governed API path starts resident supervision before overlay",
                "run_seconds": dependency_run_seconds,
            },
        )

        tray_approval_id, tray_request, tray_decision, tray_grant = _request_approve_grant(
            client,
            request_route="/lens/tray/authority/request",
            grant_route="/lens/tray/authority",
            actor=actor,
            request_reason="operator wants tray presence authority before overlay API proof",
            approve_comment="approve only tray presence authority for isolated overlay API proof",
            grant_reason="grant bounded tray presence authority for isolated overlay API proof",
        )
        tray_receipt = _as_dict(tray_grant.get("receipt"))
        tray_start = _post(
            client,
            "/lens/tray/execute",
            {
                "approval_id": tray_approval_id,
                "actor": actor,
                "reason": "prove governed API path starts tray presence before overlay",
                "mode": "start",
                "run_seconds": dependency_run_seconds,
            },
        )

        os_binding_approval_id, os_binding_request, os_binding_decision, os_binding_grant = _request_approve_grant(
            client,
            request_route="/lens/os-binding/authority/request",
            grant_route="/lens/os-binding/authority",
            actor=actor,
            request_reason="operator wants OS-binding authority before overlay API proof",
            approve_comment="approve only OS-binding authority for isolated overlay API proof",
            grant_reason="grant bounded OS-binding authority for isolated overlay API proof",
        )
        os_binding_receipt = _as_dict(os_binding_grant.get("receipt"))
        hotkey_start = _post(
            client,
            "/lens/os-binding/execute",
            {
                "approval_id": os_binding_approval_id,
                "actor": actor,
                "reason": "prove governed API path starts hotkey before overlay",
                "mode": "bind",
                "run_seconds": dependency_run_seconds,
                "global_hotkey": proof_global_hotkey,
            },
        )

        overlay_readiness_before_start = _get(client, "/lens/overlay/readiness")
        overlay_approval_id, overlay_request, overlay_decision, overlay_grant = _request_approve_grant(
            client,
            request_route="/lens/overlay/authority/request",
            grant_route="/lens/overlay/authority",
            actor=actor,
            request_reason="operator wants overlay window authority for API proof",
            approve_comment="approve only overlay window authority for isolated overlay API proof",
            grant_reason="grant bounded overlay window authority for isolated overlay API proof",
        )
        overlay_receipt = _as_dict(overlay_grant.get("receipt"))

        overlay_start, overlay_retry_count = _start_overlay_with_retry(
            client,
            approval_id=overlay_approval_id,
            actor=actor,
            reason="prove governed API path starts the real overlay window runtime",
            run_seconds=dependency_run_seconds,
        )
        if _overlay_started(overlay_start):
            resident_start = _post(
                client,
                "/lens/resident-runtime/execute",
                {
                    "approval_id": runtime_approval_id,
                    "actor": actor,
                    "reason": "refresh resident supervision lease before overlay proof readback",
                    "run_seconds": dependency_run_seconds,
                },
            )
            _stop_tray(
                client,
                approval_id=tray_approval_id,
                actor=actor,
                reason="stop stale tray presence before overlay proof readback refresh",
            )
            time.sleep(1.0)
            tray_start = _post(
                client,
                "/lens/tray/execute",
                {
                    "approval_id": tray_approval_id,
                    "actor": actor,
                    "reason": "refresh tray presence lease before overlay proof readback",
                    "mode": "start",
                    "run_seconds": dependency_run_seconds,
                },
            )
            hotkey_start = _post(
                client,
                "/lens/os-binding/execute",
                {
                    "approval_id": os_binding_approval_id,
                    "actor": actor,
                    "reason": "refresh hotkey lease before overlay proof readback",
                    "mode": "bind",
                    "run_seconds": dependency_run_seconds,
                    "global_hotkey": proof_global_hotkey,
                },
            )
            overlay_start = _post(
                client,
                "/lens/overlay/execute",
                {
                    "approval_id": overlay_approval_id,
                    "actor": actor,
                    "reason": "refresh overlay route readback after dependency lease refresh",
                    "mode": "start",
                    "run_seconds": dependency_run_seconds,
                },
            )
        overlay_executions_after_start = _get(client, "/lens/overlay/executions?limit=10")
        lens_status_after_overlay_start = _get(client, "/lens/status?limit=10")
        overlay_readiness_after_start = _get(client, "/lens/overlay/readiness")
        resident_host = _as_dict(lens_status_after_overlay_start.get("resident_host"))
        persistent_plan = _as_dict(resident_host.get("persistent_supervision_plan"))
        dependencies = _dependency_map(persistent_plan)
        overlay_dependency = _as_dict(dependencies.get("overlay_window"))
        recommended_handoff = _as_dict(persistent_plan.get("first_missing_requirement_handoff"))

        overlay_runtime_path = data_root / "runtime" / "lens-overlay" / "status.json"
        overlay_pid_path = data_root / "runtime" / "lens-overlay" / "lens-overlay.pid"
        overlay_state_after_start = _read_json(overlay_runtime_path)
        overlay_pid_file_present_after_start = overlay_pid_path.is_file()

        overlay_stop = _stop_overlay(
            client,
            approval_id=overlay_approval_id,
            actor=actor,
            reason="stop overlay runtime after isolated overlay API proof",
        )
        overlay_state_after_stop = _read_json(overlay_runtime_path)
        overlay_pid_file_present_after_stop = overlay_pid_path.is_file()

        hotkey_stop = _stop_hotkey(
            client,
            approval_id=os_binding_approval_id,
            actor=actor,
            reason="stop global hotkey runtime after isolated overlay API proof",
        )
        hotkey_pid_path = data_root / "runtime" / "lens-hotkey" / "lens-hotkey.pid"
        hotkey_pid_file_present_after_stop = hotkey_pid_path.is_file()

        tray_stop = _stop_tray(
            client,
            approval_id=tray_approval_id,
            actor=actor,
            reason="stop tray presence runtime after isolated overlay API proof",
        )
        tray_pid_path = data_root / "runtime" / "lens-tray" / "lens-tray.pid"
        tray_pid_file_present_after_stop = tray_pid_path.is_file()

        resident_stop = _stop_resident(
            client,
            approval_id=host_approval_id,
            actor=actor,
            reason="stop supervised resident host lease after isolated overlay API proof",
        )
        host_pid_path = data_root / "runtime" / "lens-host" / "lens-host.pid"
        host_pid_file_present_after_stop = host_pid_path.is_file()

        host_governance = _as_dict(resident_start.get("governance"))
        tray_governance = _as_dict(tray_start.get("governance"))
        hotkey_governance = _as_dict(hotkey_start.get("governance"))
        overlay_governance = _as_dict(overlay_start.get("governance"))
        remaining_required = _str_list(persistent_plan.get("missing_required_before_enable"))
        blockers = _remaining_blockers(persistent_plan)
        route_next_gap = str(overlay_start.get("next_smallest_truthful_gap") or "summon_anywhere_blockers")
        plan_next_gap = str(
            recommended_handoff.get("next_smallest_truthful_gap")
            or "summon_binding_blocker_boundary"
        )
        next_gap = (
            "summon_binding_blocker_boundary"
            if remaining_required == ["summon_binding"]
            else plan_next_gap
        )
        overlay_started = (
            overlay_start.get("status") in {"overlay_window_started", "overlay_window_already_running"}
            and overlay_start.get("executed") is True
            and overlay_start.get("overlay_window") is True
            and overlay_start.get("overlay_runtime_ready") is True
            and overlay_state_after_start.get("status") == "overlay_running"
            and overlay_pid_file_present_after_start
        )
        plan_consumed_overlay = (
            overlay_dependency.get("ready") is True
            and overlay_dependency.get("overlay_runtime_ready") is True
            and persistent_plan.get("first_missing_required_before_enable") == "summon_binding"
            and remaining_required == ["summon_binding"]
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
            and hotkey_governance.get("overlay_control_authority") is False
            and overlay_governance.get("overlay_control_authority") is True
            and overlay_governance.get("window_management_authority") is True
            and overlay_governance.get("summon_authority") is False
            and overlay_governance.get("memory_write") is False
            and overlay_governance.get("resident_claim_authority") is False
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
                "resident_runtime_started_before_overlay",
                "resident_supervision_started" if resident_start.get("resident_supervised_runtime") is True else "blocked",
                resident_start.get("resident_supervised_runtime") is True,
                "/lens/resident-runtime/execute",
                "The proof must start a supervised resident host before overlay execution.",
            ),
            _check(
                "tray_and_hotkey_started_before_overlay",
                "ready" if tray_start.get("tray_presence") is True and hotkey_start.get("global_hotkey_binding") is True else "blocked",
                tray_start.get("tray_presence") is True
                and tray_start.get("tray_runtime_ready") is True
                and hotkey_start.get("global_hotkey_binding") is True
                and hotkey_start.get("hotkey_runtime_ready") is True,
                "/lens/tray/execute + /lens/os-binding/execute",
                "The proof must carry forward the previously proved tray and hotkey runtime prerequisites.",
            ),
            _check(
                "overlay_authority_granted",
                "authority_granted" if overlay_grant.get("authority_granted") is True else "blocked",
                overlay_grant.get("authority_granted") is True and bool(overlay_receipt.get("receipt_id")),
                "/lens/overlay/authority",
                "The proof must grant exact bounded overlay authority before execution.",
            ),
            _check(
                "api_execute_started_real_overlay_window",
                "overlay_window_started" if overlay_started else str(overlay_start.get("status") or "blocked"),
                overlay_started,
                "/lens/overlay/execute",
                "The governed route must start a real overlay window runtime.",
            ),
            _check(
                "status_plan_consumed_live_overlay_runtime",
                str(persistent_plan.get("first_missing_required_before_enable") or ""),
                plan_consumed_overlay,
                "/lens/status resident_host.persistent_supervision_plan",
                "The persistent supervision plan must consume live overlay runtime and advance to summon binding.",
            ),
            _check(
                "overlay_receipt_readback_after_start",
                str(overlay_executions_after_start.get("status") or ""),
                overlay_executions_after_start.get("status") == "readback_ready"
                and overlay_executions_after_start.get("latest_overlay_window") is True,
                "/lens/overlay/executions?limit=10",
                "The overlay execution receipt must be readable after start.",
            ),
            _check(
                "overlay_readiness_observed_after_start",
                str(overlay_readiness_after_start.get("status") or ""),
                overlay_readiness_after_start.get("ready") is False
                and overlay_readiness_after_start.get("status") == "blocked"
                and overlay_started,
                "/lens/overlay/readiness",
                "The route must expose live overlay runtime without turning disabled config into product readiness.",
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
                "The proof may start resident supervision, tray, hotkey, and overlay but must not gain summon, service, memory, capture, or resident-claim authority.",
            ),
        ]
        proof_passed = all(item["passed"] for item in checks)
        payload = {
            "ok": proof_passed,
            "kind": "lens.overlay.api_execution.proof",
            "status": "proof_passed" if proof_passed else "proof_failed",
            "mode": os.environ.get("FRANCIS_PROOF_MODE", "status"),
            "repo_root": str(repo_root),
            "data_root": str(data_root),
            "stage": "Stage 6 / Lens MVP",
            "stage_state": "active",
            "acceptance_criterion": "summon_anywhere",
            "global_hotkey": proof_global_hotkey,
            "previous_next_smallest_truthful_gap": "summon_overlay_window_blocker_boundary",
            "route_next_smallest_truthful_gap": route_next_gap,
            "next_smallest_truthful_gap": next_gap,
            "recommended_next_slice": "prove_governed_summon_api_execution_after_overlay_window",
            "recommended_proof_script": "scripts/lens-summon-api-execution-proof.ps1 -Mode Status",
            "recommended_handoff_source": "api_overlay_execution_summon_binding_handoff",
            "recommended_handoff": recommended_handoff,
            "dependency_run_seconds": dependency_run_seconds,
            "overlay_start_retry_count": overlay_retry_count,
            "host_supervision_approval_id": host_approval_id,
            "resident_runtime_approval_id": runtime_approval_id,
            "tray_presence_approval_id": tray_approval_id,
            "os_binding_approval_id": os_binding_approval_id,
            "overlay_approval_id": overlay_approval_id,
            "host_supervision_authority_grant_receipt_id": str(host_receipt.get("receipt_id") or ""),
            "resident_runtime_authority_grant_receipt_id": str(runtime_receipt.get("receipt_id") or ""),
            "tray_authority_grant_receipt_id": str(tray_receipt.get("receipt_id") or ""),
            "os_binding_authority_grant_receipt_id": str(os_binding_receipt.get("receipt_id") or ""),
            "overlay_authority_grant_receipt_id": str(overlay_receipt.get("receipt_id") or ""),
            "resident_runtime_execution_authority": runtime_grant.get("authority_granted") is True,
            "host_supervision_authority": host_grant.get("authority_granted") is True,
            "tray_presence_authority": tray_grant.get("authority_granted") is True,
            "os_binding_authority": os_binding_grant.get("authority_granted") is True,
            "overlay_authority": overlay_grant.get("authority_granted") is True,
            "execution_applied": overlay_start.get("applied") is True,
            "executed": overlay_start.get("executed") is True,
            "resident_host_process_started": resident_start.get("resident_host_process") is True,
            "resident_supervised_runtime_started": resident_start.get("resident_supervised_runtime") is True,
            "tray_presence_started": tray_start.get("tray_presence") is True,
            "tray_runtime_ready": tray_start.get("tray_runtime_ready") is True,
            "global_hotkey_bound": hotkey_start.get("global_hotkey_binding") is True,
            "hotkey_runtime_ready": hotkey_start.get("hotkey_runtime_ready") is True,
            "overlay_window_started": overlay_start.get("overlay_window") is True,
            "overlay_runtime_ready": overlay_start.get("overlay_runtime_ready") is True,
            "overlay_window_visible": overlay_start.get("overlay_window_visible") is True,
            "overlay_always_on_top": overlay_start.get("always_on_top") is True,
            "overlay_stop_observed": overlay_stop_observed,
            "hotkey_stop_observed": hotkey_stop_observed,
            "tray_presence_stop_observed": tray_stop_observed,
            "resident_supervision_stop_observed": resident_stop_observed,
            "overlay_pid_file_present_after_start": overlay_pid_file_present_after_start,
            "overlay_pid_file_present_after_stop": overlay_pid_file_present_after_stop,
            "hotkey_pid_file_present_after_stop": hotkey_pid_file_present_after_stop,
            "tray_pid_file_present_after_stop": tray_pid_file_present_after_stop,
            "host_pid_file_present_after_stop": host_pid_file_present_after_stop,
            "required_before_enable_after_overlay": remaining_required,
            "blockers": blockers,
            "summon_anywhere": False,
            "service_managed": False,
            "resident_claim_allowed": False,
            "checks": checks,
            "proof": {
                "dependency_run_seconds": dependency_run_seconds,
                "overlay_start_retry_count": overlay_retry_count,
                "global_hotkey": proof_global_hotkey,
                "resident_start_status": str(resident_start.get("status") or ""),
                "tray_start_status": str(tray_start.get("status") or ""),
                "hotkey_start_status": str(hotkey_start.get("status") or ""),
                "overlay_start_status": str(overlay_start.get("status") or ""),
                "overlay_runtime_status_after_start": str(overlay_state_after_start.get("status") or ""),
                "overlay_runtime_pid_after_start": int(overlay_state_after_start.get("pid") or 0),
                "overlay_stop_status": str(overlay_stop.get("status") or ""),
                "overlay_runtime_status_after_stop": str(overlay_state_after_stop.get("status") or ""),
                "hotkey_stop_status": str(hotkey_stop.get("status") or ""),
                "tray_stop_status": str(tray_stop.get("status") or ""),
                "resident_stop_status": str(resident_stop.get("status") or ""),
                "overlay_receipt_readback_status": str(overlay_executions_after_start.get("status") or ""),
                "overlay_receipt_readback_next_gap": str(
                    overlay_executions_after_start.get("latest_next_smallest_truthful_gap") or ""
                ),
                "persistent_plan_first_missing_after_overlay": str(
                    persistent_plan.get("first_missing_required_before_enable") or ""
                ),
                "overlay_readiness_before_start_status": str(overlay_readiness_before_start.get("status") or ""),
                "overlay_readiness_after_start_status": str(overlay_readiness_after_start.get("status") or ""),
            },
            "start_execution": {
                "status": str(overlay_start.get("status") or ""),
                "next_smallest_truthful_gap": str(overlay_start.get("next_smallest_truthful_gap") or ""),
                "overlay_window": overlay_start.get("overlay_window") is True,
                "overlay_runtime_ready": overlay_start.get("overlay_runtime_ready") is True,
                "overlay_window_visible": overlay_start.get("overlay_window_visible") is True,
                "always_on_top": overlay_start.get("always_on_top") is True,
                "stop_command": str(overlay_start.get("stop_command") or ""),
            },
            "stop_execution": {
                "status": str(overlay_stop.get("status") or ""),
                "overlay_window": overlay_stop.get("overlay_window") is True,
                "overlay_runtime_ready": overlay_stop.get("overlay_runtime_ready") is True,
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
                "hotkey_registration_authority": True,
                "overlay_control_authority": True,
                "window_management_authority": True,
                "capture_authority": False,
                "new_sensing_authority": False,
                "summon_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
                "mutation_authority_granted": True,
            },
            "notes": (
                "This proof starts a bounded local overlay runtime only. It does not claim "
                "summon-anywhere readiness, memory write, capture, service control, or "
                "resident-claim authority."
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
                    reason="fallback cleanup for overlay API execution proof",
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
                    reason="fallback cleanup for overlay API execution proof",
                )
        except Exception as exc:
            cleanup_errors.append(f"hotkey_stop_failed:{exc}")
        try:
            if not (tray_stop.get("status") == "tray_presence_stopped" and tray_stop.get("tray_presence") is False):
                _stop_tray(
                    client,
                    approval_id=tray_approval_id,
                    actor=actor,
                    reason="fallback cleanup for overlay API execution proof",
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
                    reason="fallback cleanup for overlay API execution proof",
                )
        except Exception as exc:
            cleanup_errors.append(f"resident_stop_failed:{exc}")
        if cleanup_errors:
            raise RuntimeError(f"overlay API proof cleanup failed: {cleanup_errors!r}")


try:
    exit_code, payload = _run()
except Exception as exc:
    exit_code = 1
    payload = {
        "ok": False,
        "kind": "lens.overlay.api_execution.proof",
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
  $ProofRuntimeDir = Join-Path $ProofDataRoot 'runtime\lens-overlay-api-execution-proof'
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
