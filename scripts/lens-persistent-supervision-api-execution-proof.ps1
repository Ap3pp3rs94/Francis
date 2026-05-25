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
  $DataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-persistent-supervision-api-execution-proof\" + [guid]::NewGuid().ToString('N') + "\data")
}

$ProofDataRoot = [System.IO.Path]::GetFullPath($DataDir)
$ProofServiceConfigPath = Join-Path $ProofDataRoot 'config\runtime\services\lens-host.json'
$PythonPath = Get-PythonPath
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
  [ordered]@{
    ok = $false
    kind = 'lens.host.persistent_supervision.api_execution.proof'
    status = 'proof_failed'
    mode = $Mode.ToLowerInvariant()
    repo_root = $RepoRoot
    data_root = $ProofDataRoot
    service_config_path = $ProofServiceConfigPath
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


def _write_temp_service_config(repo_root: Path, service_config_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    live_path = repo_root / "config" / "runtime" / "services" / "lens-host.json"
    live_config = _read_json(live_path)
    if not live_config:
        raise RuntimeError(f"Lens host service config is missing or invalid: {live_path}")
    temp_config = dict(live_config)
    temp_config["process_supervision_enabled"] = False
    temp_config["persistent_supervision_enabled"] = False
    temp_config["supervision_ready"] = False
    temp_config["service_control_authority"] = False
    temp_config["resident_claim_authority"] = False
    service_config_path.parent.mkdir(parents=True, exist_ok=True)
    service_config_path.write_text(json.dumps(temp_config, indent=2) + "\n", encoding="utf-8")
    return live_config, temp_config


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
    service_config_path = Path(os.environ["FRANCIS_LENS_HOST_SERVICE_CONFIG_PATH"]).resolve()
    run_seconds = int(os.environ.get("FRANCIS_PROOF_RUN_SECONDS", "5"))
    proof_global_hotkey = os.environ.get("FRANCIS_PROOF_GLOBAL_HOTKEY", "Ctrl+Alt+Shift+F12").strip()
    # This proof validates a long governed route chain; keep prerequisite runtimes alive
    # long enough for the post-apply status readback instead of racing their lease.
    dependency_run_seconds = max(run_seconds, 60)
    resident_dependency_run_seconds = dependency_run_seconds
    data_root.mkdir(parents=True, exist_ok=True)
    live_service_config_before, temp_service_config_before = _write_temp_service_config(repo_root, service_config_path)

    actor = "test.system.write"
    set_control_mode(
        "assist",
        reason="prove Lens persistent supervision API execution path",
        actor=actor,
    )

    client = TestClient(create_app())
    host_approval_id = ""
    runtime_approval_id = ""
    tray_approval_id = ""
    os_binding_approval_id = ""
    overlay_approval_id = ""
    summon_approval_id = ""
    enablement_approval_id = ""
    execution_approval_id = ""
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
            request_reason="operator wants host supervision authority before persistent supervision API proof",
            approve_comment="approve only host supervision authority for isolated persistent supervision API proof",
            grant_reason="grant bounded host supervision authority for isolated persistent supervision API proof",
        )
        host_receipt = _as_dict(host_grant.get("receipt"))

        runtime_approval_id, runtime_request, runtime_decision, runtime_grant = _request_approve_grant(
            client,
            request_route="/lens/resident-runtime/authority-grant/request",
            grant_route="/lens/resident-runtime/authority-grant",
            actor=actor,
            request_reason="operator wants resident runtime execution authority before persistent supervision API proof",
            approve_comment=(
                "approve only resident runtime execution authority for isolated persistent supervision API proof"
            ),
            grant_reason="grant bounded resident runtime execution authority for isolated persistent supervision API proof",
        )
        runtime_receipt = _as_dict(runtime_grant.get("receipt"))

        tray_approval_id, tray_request, tray_decision, tray_grant = _request_approve_grant(
            client,
            request_route="/lens/tray/authority/request",
            grant_route="/lens/tray/authority",
            actor=actor,
            request_reason="operator wants tray presence authority before persistent supervision API proof",
            approve_comment="approve only tray presence authority for isolated persistent supervision API proof",
            grant_reason="grant bounded tray presence authority for isolated persistent supervision API proof",
        )
        tray_receipt = _as_dict(tray_grant.get("receipt"))

        os_binding_approval_id, os_binding_request, os_binding_decision, os_binding_grant = _request_approve_grant(
            client,
            request_route="/lens/os-binding/authority/request",
            grant_route="/lens/os-binding/authority",
            actor=actor,
            request_reason="operator wants OS-binding authority before persistent supervision API proof",
            approve_comment="approve only OS-binding authority for isolated persistent supervision API proof",
            grant_reason="grant bounded OS-binding authority for isolated persistent supervision API proof",
        )
        os_binding_receipt = _as_dict(os_binding_grant.get("receipt"))

        overlay_approval_id, overlay_request, overlay_decision, overlay_grant = _request_approve_grant(
            client,
            request_route="/lens/overlay/authority/request",
            grant_route="/lens/overlay/authority",
            actor=actor,
            request_reason="operator wants overlay window authority before persistent supervision API proof",
            approve_comment="approve only overlay window authority for isolated persistent supervision API proof",
            grant_reason="grant bounded overlay window authority for isolated persistent supervision API proof",
        )
        overlay_receipt = _as_dict(overlay_grant.get("receipt"))

        summon_approval_id, summon_request, summon_decision, summon_grant = _request_approve_grant(
            client,
            request_route="/lens/summon/authority/request",
            grant_route="/lens/summon/authority",
            actor=actor,
            request_reason="operator wants bounded summon action authority before persistent supervision API proof",
            approve_comment="approve only bounded summon action authority for isolated persistent supervision API proof",
            grant_reason="grant bounded summon action authority for isolated persistent supervision API proof",
        )
        summon_receipt = _as_dict(summon_grant.get("receipt"))

        enablement_approval_id, enablement_request, enablement_decision, enablement_grant = _request_approve_grant(
            client,
            request_route="/lens/host/persistent-supervision/enablement/authority/request",
            grant_route="/lens/host/persistent-supervision/enablement/authority",
            actor=actor,
            request_reason="operator wants persistent supervision enablement authority for API proof",
            approve_comment="approve only persistent supervision enablement authority for isolated API proof",
            grant_reason="grant bounded persistent supervision enablement authority without live service mutation",
        )
        enablement_receipt = _as_dict(enablement_grant.get("receipt"))

        execution_approval_id, execution_request, execution_decision, execution_grant = _request_approve_grant(
            client,
            request_route="/lens/host/persistent-supervision/enablement/execution/request",
            grant_route="/lens/host/persistent-supervision/enablement/execution/authority",
            actor=actor,
            request_reason="operator wants persistent supervision execution authority for API proof",
            approve_comment="approve only persistent supervision execution authority for isolated API proof",
            grant_reason="grant bounded persistent supervision execution authority for isolated temp service config",
        )
        execution_receipt = _as_dict(execution_grant.get("receipt"))

        resident_start = _post(
            client,
            "/lens/resident-runtime/execute",
            {
                "approval_id": runtime_approval_id,
                "actor": actor,
                "reason": "prove governed API path starts resident supervision before persistent supervision",
                "run_seconds": resident_dependency_run_seconds,
            },
        )
        tray_start = _post(
            client,
            "/lens/tray/execute",
            {
                "approval_id": tray_approval_id,
                "actor": actor,
                "reason": "prove governed API path starts tray presence before persistent supervision",
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
                "reason": "prove governed API path starts hotkey before persistent supervision",
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
                "reason": "prove governed API path starts overlay before persistent supervision",
                "mode": "start",
                "run_seconds": dependency_run_seconds,
            },
        )
        summon_execute = _post(
            client,
            "/lens/summon/execute",
            {
                "approval_id": summon_approval_id,
                "actor": actor,
                "reason": "prove governed API path executes bounded summon before persistent supervision",
                "mode": "launch",
                "run_seconds": dependency_run_seconds,
                "allow_launch": False,
            },
        )

        lens_status_after_summon = _get(client, "/lens/status?limit=10")
        resident_host_after_summon = _as_dict(lens_status_after_summon.get("resident_host"))
        persistent_plan_after_summon = _as_dict(resident_host_after_summon.get("persistent_supervision_plan"))
        dependencies_after_summon = _dependency_map(persistent_plan_after_summon)
        persistent_readiness_before_apply = _get(
            client,
            "/lens/host/persistent-supervision/enablement/execution/readiness"
            f"?limit=10&approval_id={execution_approval_id}&actor={actor}",
        )
        persistent_denial_before_apply = _post(
            client,
            "/lens/host/persistent-supervision/enablement/execution",
            {
                "approval_id": execution_approval_id,
                "actor": actor,
                "reason": "prove persistent supervision execution denial boundary before isolated apply",
            },
        )
        persistent_apply = _post(
            client,
            "/lens/host/persistent-supervision/enablement/execution/apply",
            {
                "approval_id": execution_approval_id,
                "actor": actor,
                "reason": "apply persistent supervision enablement against isolated service config",
            },
        )
        persistent_executions_after_apply = _get(
            client,
            f"/lens/host/persistent-supervision/enablement/executions?limit=10&approval_id={execution_approval_id}",
        )
        lens_status_after_apply = _get(client, "/lens/status?limit=10")
        resident_host_after_apply = _as_dict(lens_status_after_apply.get("resident_host"))
        persistent_plan_after_apply = _as_dict(resident_host_after_apply.get("persistent_supervision_plan"))
        persistent_enablement_after_apply = _as_dict(
            resident_host_after_apply.get("persistent_supervision_enablement")
        )
        temp_service_config_after = _read_json(service_config_path)
        live_service_config_after = _read_json(repo_root / "config" / "runtime" / "services" / "lens-host.json")

        summon_runtime_path = data_root / "runtime" / "lens-summon" / "status.json"
        summon_state_after_execute = _read_json(summon_runtime_path)

        overlay_stop = _stop_overlay(
            client,
            approval_id=overlay_approval_id,
            actor=actor,
            reason="stop overlay runtime after isolated persistent supervision API proof",
        )
        overlay_pid_path = data_root / "runtime" / "lens-overlay" / "lens-overlay.pid"
        overlay_pid_file_present_after_stop = overlay_pid_path.is_file()

        hotkey_stop = _stop_hotkey(
            client,
            approval_id=os_binding_approval_id,
            actor=actor,
            reason="stop global hotkey runtime after isolated persistent supervision API proof",
        )
        hotkey_pid_path = data_root / "runtime" / "lens-hotkey" / "lens-hotkey.pid"
        hotkey_pid_file_present_after_stop = hotkey_pid_path.is_file()

        tray_stop = _stop_tray(
            client,
            approval_id=tray_approval_id,
            actor=actor,
            reason="stop tray presence runtime after isolated persistent supervision API proof",
        )
        tray_pid_path = data_root / "runtime" / "lens-tray" / "lens-tray.pid"
        tray_pid_file_present_after_stop = tray_pid_path.is_file()

        resident_stop = _stop_resident(
            client,
            approval_id=host_approval_id,
            actor=actor,
            reason="stop supervised resident host lease after isolated persistent supervision API proof",
        )
        host_pid_path = data_root / "runtime" / "lens-host" / "lens-host.pid"
        host_pid_file_present_after_stop = host_pid_path.is_file()

        host_governance = _as_dict(host_grant.get("governance"))
        runtime_governance = _as_dict(resident_start.get("governance"))
        tray_governance = _as_dict(tray_start.get("governance"))
        hotkey_governance = _as_dict(hotkey_start.get("governance"))
        overlay_governance = _as_dict(overlay_start.get("governance"))
        summon_governance = _as_dict(summon_execute.get("governance"))
        apply_governance = _as_dict(persistent_apply.get("governance"))
        dependencies_ready_after_summon = (
            persistent_plan_after_summon.get("required_before_enable_ready") is True
            and persistent_plan_after_summon.get("missing_required_before_enable") == []
            and all(
                _as_dict(dependencies_after_summon.get(item)).get("ready") is True
                for item in [
                    "resident_host_process",
                    "tray_presence",
                    "global_hotkey_binding",
                    "overlay_window",
                    "summon_binding",
                ]
            )
        )
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
            and summon_state_after_execute.get("opened") is False
            and summon_state_after_execute.get("no_launch") is True
        )
        execution_readiness_observed = (
            persistent_readiness_before_apply.get("execution_authority_granted") is True
            and persistent_readiness_before_apply.get("service_config_write_authority") is True
            and persistent_readiness_before_apply.get("persistent_supervision_execution_authority") is True
            and persistent_readiness_before_apply.get("receipt_write_authority") is True
            and persistent_readiness_before_apply.get("resident_claim_allowed") is False
            and "resident_claim_authority_not_granted"
            in _str_list(persistent_readiness_before_apply.get("blockers"))
        )
        denial_before_apply_observed = (
            persistent_denial_before_apply.get("status") == "denied_no_resident_claim_authority"
            and persistent_denial_before_apply.get("authority_granted") is True
            and persistent_denial_before_apply.get("applied") is False
            and persistent_denial_before_apply.get("executed") is False
            and persistent_denial_before_apply.get("service_config_updated") is False
            and "resident_claim_authority_not_granted"
            in _str_list(persistent_denial_before_apply.get("blockers"))
        )
        service_config_changed_fields = _str_list(_as_dict(persistent_apply.get("service_config")).get("changed_fields"))
        apply_observed = (
            persistent_apply.get("kind") == "lens.host.persistent_supervision_enablement_execution.execution"
            and persistent_apply.get("status") == "service_config_updated"
            and persistent_apply.get("applied") is True
            and persistent_apply.get("executed") is True
            and persistent_apply.get("service_config_updated") is True
            and persistent_apply.get("persistent_supervision_enablement_allowed") is True
            and persistent_apply.get("persistent_supervision_ready") is True
            and persistent_apply.get("resident_claim_allowed") is False
            and persistent_apply.get("receipt_written") is True
            and _as_dict(persistent_apply.get("service_config")).get("path") == str(service_config_path)
            and "process_supervision_enabled" in service_config_changed_fields
            and "persistent_supervision_enabled" in service_config_changed_fields
        )
        post_plan_observed = (
            persistent_plan_after_apply.get("persistent_supervision_ready") is True
            and persistent_plan_after_apply.get("required_before_enable_ready") is True
            and persistent_plan_after_apply.get("missing_required_before_enable") == []
            and persistent_plan_after_apply.get("next_smallest_truthful_gap") == "persistent_supervision_execution_boundary"
            and persistent_enablement_after_apply.get("persistent_supervision_enabled") is True
        )
        receipt_readback_observed = (
            persistent_executions_after_apply.get("status") == "readback_ready"
            and persistent_executions_after_apply.get("total") == 1
            and _as_dict(persistent_executions_after_apply.get("latest")).get("approval_id") == execution_approval_id
            and persistent_executions_after_apply.get("service_config_updated") is True
            and persistent_executions_after_apply.get("persistent_supervision_enablement_allowed") is True
            and persistent_executions_after_apply.get("resident_claim_allowed") is False
        )
        isolated_config_observed = (
            temp_service_config_before.get("process_supervision_enabled") is False
            and temp_service_config_before.get("persistent_supervision_enabled") is False
            and temp_service_config_after.get("process_supervision_enabled") is True
            and temp_service_config_after.get("persistent_supervision_enabled") is True
            and temp_service_config_after.get("installable") is False
            and temp_service_config_after.get("service_control_authority") is False
            and temp_service_config_after.get("resident_claim_authority") is False
            and live_service_config_after == live_service_config_before
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
            host_governance.get("authority_granted") is True
            and runtime_governance.get("resident_claim_authority") is False
            and tray_governance.get("summon_authority") is False
            and hotkey_governance.get("summon_authority") is False
            and overlay_governance.get("summon_authority") is False
            and summon_governance.get("summon_anywhere_authority") is False
            and summon_governance.get("os_level_summon_authority") is False
            and summon_governance.get("local_process_launch_authority") is False
            and summon_governance.get("memory_write") is False
            and apply_governance.get("service_config_write_authority") is True
            and apply_governance.get("persistent_supervision_execution_authority") is True
            and apply_governance.get("service_config_mutation_authority") is True
            and apply_governance.get("service_install_authority") is False
            and apply_governance.get("service_control_authority") is False
            and apply_governance.get("local_process_launch_authority") is False
            and apply_governance.get("memory_write") is False
            and apply_governance.get("resident_claim_authority") is False
            and apply_governance.get("approval_decision_authority") is False
        )
        checks = [
            _check(
                "authority_chain_granted",
                "authority_granted"
                if (
                    host_grant.get("authority_granted") is True
                    and runtime_grant.get("authority_granted") is True
                    and tray_grant.get("authority_granted") is True
                    and os_binding_grant.get("authority_granted") is True
                    and overlay_grant.get("authority_granted") is True
                    and summon_grant.get("authority_granted") is True
                    and enablement_grant.get("authority_granted") is True
                    and execution_grant.get("authority_granted") is True
                )
                else "blocked",
                host_grant.get("authority_granted") is True
                and runtime_grant.get("authority_granted") is True
                and tray_grant.get("authority_granted") is True
                and os_binding_grant.get("authority_granted") is True
                and overlay_grant.get("authority_granted") is True
                and summon_grant.get("authority_granted") is True
                and enablement_grant.get("authority_granted") is True
                and execution_grant.get("authority_granted") is True
                and bool(execution_receipt.get("receipt_id")),
                "/lens/*/authority + /lens/host/persistent-supervision/enablement/execution/authority",
                "The proof must carry exact authority receipts through the persistent-supervision execution route.",
            ),
            _check(
                "resident_tray_hotkey_overlay_started_before_apply",
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
                "The proof must execute persistent supervision only after the resident, tray, hotkey, and overlay paths are live.",
            ),
            _check(
                "api_execute_observed_bounded_summon_handoff",
                "summon_binding_observed" if summon_started else str(summon_execute.get("status") or "blocked"),
                summon_started and runtime_state_observed,
                "/lens/summon/execute",
                "Persistent supervision enablement must consume the already-proved bounded summon runtime handoff.",
            ),
            _check(
                "persistent_plan_consumed_required_runtime_prerequisites",
                "required_before_enable_clear"
                if dependencies_ready_after_summon
                else str(persistent_plan_after_summon.get("first_missing_required_before_enable") or "blocked"),
                dependencies_ready_after_summon,
                "/lens/status resident_host.persistent_supervision_plan",
                "The persistent plan must consume resident, tray, hotkey, overlay, and summon readback before apply.",
            ),
            _check(
                "execution_readiness_reaches_resident_claim_boundary",
                str(persistent_readiness_before_apply.get("status") or ""),
                execution_readiness_observed,
                "/lens/host/persistent-supervision/enablement/execution/readiness",
                "Execution readiness must see execution authority and narrow the remaining boundary to resident claim.",
            ),
            _check(
                "execution_denial_before_apply_preserved",
                str(persistent_denial_before_apply.get("status") or ""),
                denial_before_apply_observed,
                "/lens/host/persistent-supervision/enablement/execution",
                "The non-apply route must remain a denial/readback boundary even after execution authority is granted.",
            ),
            _check(
                "api_apply_updated_isolated_service_config",
                str(persistent_apply.get("status") or ""),
                apply_observed,
                "/lens/host/persistent-supervision/enablement/execution/apply",
                "The apply route must update only the isolated service config and write a bounded execution receipt.",
            ),
            _check(
                "status_plan_consumed_persistent_supervision_enablement",
                str(persistent_plan_after_apply.get("next_smallest_truthful_gap") or ""),
                post_plan_observed,
                "/lens/status resident_host.persistent_supervision_plan",
                "Operator status must expose persistent supervision enablement after the isolated API execution.",
            ),
            _check(
                "persistent_execution_receipt_readback",
                str(persistent_executions_after_apply.get("status") or ""),
                receipt_readback_observed,
                "/lens/host/persistent-supervision/enablement/executions",
                "The persistent-supervision execution receipt must be directly readable after apply.",
            ),
            _check(
                "isolated_service_config_only",
                "isolated_temp_config" if isolated_config_observed else "unexpected_live_config_change",
                isolated_config_observed,
                "FRANCIS_LENS_HOST_SERVICE_CONFIG_PATH",
                "The proof must mutate only the proof service config path and leave the live repo config unchanged.",
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
                "The proof may write isolated service-config and runtime receipts but must not gain launch, service control, memory, approval-decision, or resident-claim authority.",
            ),
        ]
        proof_passed = all(item["passed"] for item in checks)
        route_next_gap = "persistent_supervision_execution_boundary"
        payload = {
            "ok": proof_passed,
            "kind": "lens.host.persistent_supervision.api_execution.proof",
            "status": "proof_passed" if proof_passed else "proof_failed",
            "mode": os.environ.get("FRANCIS_PROOF_MODE", "status"),
            "repo_root": str(repo_root),
            "data_root": str(data_root),
            "stage": "Stage 6 / Lens MVP",
            "stage_state": "active",
            "acceptance_criterion": "persistent_supervision_enablement",
            "global_hotkey": proof_global_hotkey,
            "previous_next_smallest_truthful_gap": "persistent_supervision_execution_boundary",
            "route_next_smallest_truthful_gap": route_next_gap,
            "next_smallest_truthful_gap": "stage6_lens_completion_audit",
            "recommended_next_slice": "run_stage6_lens_completion_audit_after_persistent_supervision_api_execution",
            "recommended_proof_script": "scripts/lens-stage6-completion-audit.ps1 -Mode Status",
            "recommended_handoff_source": "api_persistent_supervision_execution_handoff",
            "service_config_path": str(service_config_path),
            "live_service_config_unchanged": live_service_config_after == live_service_config_before,
            "dependency_run_seconds": dependency_run_seconds,
            "resident_dependency_run_seconds": resident_dependency_run_seconds,
            "host_supervision_approval_id": host_approval_id,
            "resident_runtime_approval_id": runtime_approval_id,
            "tray_presence_approval_id": tray_approval_id,
            "os_binding_approval_id": os_binding_approval_id,
            "overlay_approval_id": overlay_approval_id,
            "summon_approval_id": summon_approval_id,
            "persistent_supervision_enablement_approval_id": enablement_approval_id,
            "persistent_supervision_execution_approval_id": execution_approval_id,
            "host_supervision_authority_grant_receipt_id": str(host_receipt.get("receipt_id") or ""),
            "resident_runtime_authority_grant_receipt_id": str(runtime_receipt.get("receipt_id") or ""),
            "tray_authority_grant_receipt_id": str(tray_receipt.get("receipt_id") or ""),
            "os_binding_authority_grant_receipt_id": str(os_binding_receipt.get("receipt_id") or ""),
            "overlay_authority_grant_receipt_id": str(overlay_receipt.get("receipt_id") or ""),
            "summon_authority_grant_receipt_id": str(summon_receipt.get("receipt_id") or ""),
            "persistent_supervision_enablement_authority_grant_receipt_id": str(
                enablement_receipt.get("receipt_id") or ""
            ),
            "persistent_supervision_execution_authority_grant_receipt_id": str(
                execution_receipt.get("receipt_id") or ""
            ),
            "resident_runtime_execution_authority": runtime_grant.get("authority_granted") is True,
            "host_supervision_authority": host_grant.get("authority_granted") is True,
            "tray_presence_authority": tray_grant.get("authority_granted") is True,
            "os_binding_authority": os_binding_grant.get("authority_granted") is True,
            "overlay_authority": overlay_grant.get("authority_granted") is True,
            "summon_authority": summon_grant.get("authority_granted") is True,
            "persistent_supervision_enablement_authority": enablement_grant.get("authority_granted") is True,
            "service_config_write_authority": execution_grant.get("service_config_write_authority") is True,
            "persistent_supervision_execution_authority": (
                execution_grant.get("persistent_supervision_execution_authority") is True
            ),
            "receipt_write_authority": execution_grant.get("receipt_write_authority") is True,
            "execution_applied": persistent_apply.get("applied") is True,
            "executed": persistent_apply.get("executed") is True,
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
            "summon_runtime_state_observed": runtime_state_observed,
            "required_before_enable_after_summon": _str_list(
                persistent_plan_after_summon.get("missing_required_before_enable")
            ),
            "required_before_enable_ready_after_summon": (
                persistent_plan_after_summon.get("required_before_enable_ready") is True
            ),
            "persistent_supervision_apply_status": str(persistent_apply.get("status") or ""),
            "persistent_supervision_ready_after_apply": persistent_apply.get("persistent_supervision_ready") is True,
            "persistent_supervision_enablement_allowed": (
                persistent_apply.get("persistent_supervision_enablement_allowed") is True
            ),
            "service_config_updated": persistent_apply.get("service_config_updated") is True,
            "receipt_written": persistent_apply.get("receipt_written") is True,
            "resident_claim_allowed": False,
            "service_managed": False,
            "summon_anywhere": False,
            "os_level_summon": False,
            "overlay_stop_observed": overlay_stop_observed,
            "hotkey_stop_observed": hotkey_stop_observed,
            "tray_presence_stop_observed": tray_stop_observed,
            "resident_supervision_stop_observed": resident_stop_observed,
            "overlay_pid_file_present_after_stop": overlay_pid_file_present_after_stop,
            "hotkey_pid_file_present_after_stop": hotkey_pid_file_present_after_stop,
            "tray_pid_file_present_after_stop": tray_pid_file_present_after_stop,
            "host_pid_file_present_after_stop": host_pid_file_present_after_stop,
            "blockers": _str_list(persistent_apply.get("blockers")),
            "checks": checks,
            "proof": {
                "dependency_run_seconds": dependency_run_seconds,
                "resident_dependency_run_seconds": resident_dependency_run_seconds,
                "global_hotkey": proof_global_hotkey,
                "resident_start_status": str(resident_start.get("status") or ""),
                "tray_start_status": str(tray_start.get("status") or ""),
                "hotkey_start_status": str(hotkey_start.get("status") or ""),
                "overlay_start_status": str(overlay_start.get("status") or ""),
                "summon_execute_status": str(summon_execute.get("status") or ""),
                "summon_runtime_state_status": str(summon_state_after_execute.get("status") or ""),
                "persistent_plan_after_summon_status": str(persistent_plan_after_summon.get("status") or ""),
                "persistent_plan_after_summon_next_gap": str(
                    persistent_plan_after_summon.get("next_smallest_truthful_gap") or ""
                ),
                "persistent_readiness_before_apply_status": str(
                    persistent_readiness_before_apply.get("status") or ""
                ),
                "persistent_denial_before_apply_status": str(
                    persistent_denial_before_apply.get("status") or ""
                ),
                "persistent_apply_status": str(persistent_apply.get("status") or ""),
                "persistent_apply_receipt_id": str(_as_dict(persistent_apply.get("receipt")).get("receipt_id") or ""),
                "persistent_executions_readback_status": str(
                    persistent_executions_after_apply.get("status") or ""
                ),
                "persistent_plan_after_apply_status": str(persistent_plan_after_apply.get("status") or ""),
                "persistent_plan_after_apply_next_gap": str(
                    persistent_plan_after_apply.get("next_smallest_truthful_gap") or ""
                ),
                "temp_service_config_process_supervision_enabled": bool(
                    temp_service_config_after.get("process_supervision_enabled")
                ),
                "temp_service_config_persistent_supervision_enabled": bool(
                    temp_service_config_after.get("persistent_supervision_enabled")
                ),
                "overlay_stop_status": str(overlay_stop.get("status") or ""),
                "hotkey_stop_status": str(hotkey_stop.get("status") or ""),
                "tray_stop_status": str(tray_stop.get("status") or ""),
                "resident_stop_status": str(resident_stop.get("status") or ""),
            },
            "handoff": {
                "recommended_handoff_source": "api_persistent_supervision_execution_handoff",
                "status": "audit_needed",
                "previous_next_smallest_truthful_gap": "persistent_supervision_execution_boundary",
                "next_smallest_truthful_gap": "stage6_lens_completion_audit",
                "next_step": "run_stage6_lens_completion_audit_after_persistent_supervision_api_execution",
                "proof_script": "scripts/lens-stage6-completion-audit.ps1 -Mode Status",
                "route": "/lens/host/persistent-supervision/enablement/execution/apply",
                "readiness_route": "/lens/host/persistent-supervision/enablement/execution/readiness",
                "authority_required": "none_new_stage6_completion_audit",
                "authority_granted": False,
                "read_only_contract": True,
                "diagnostic_only": True,
                "would_execute": False,
                "would_mutate": False,
            },
            "governance": {
                "diagnostic_only": True,
                "api_route_proof": True,
                "api_execution_authority": True,
                "approval_request_write": True,
                "test_fixture_approval_decisions": True,
                "approval_decision_authority": False,
                "product_execution_authority": False,
                "execution_authority": False,
                "temporary_runtime_state_write": True,
                "isolated_service_config_write": True,
                "service_config_write_authority": True,
                "service_config_mutation_authority": True,
                "persistent_supervision_enablement_authority": True,
                "persistent_supervision_execution_authority": True,
                "receipt_write_authority": True,
                "local_process_launch_authority": False,
                "process_supervision_authority": True,
                "process_restart_authority": True,
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
                "This proof executes persistent-supervision enablement only against an isolated service config. "
                "It does not claim Stage 6 closure, service install/control, local process launch, memory write, "
                "approval-decision authority, OS-level summon-anywhere readiness, or resident-claim authority."
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
                    reason="fallback cleanup for persistent supervision API execution proof",
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
                    reason="fallback cleanup for persistent supervision API execution proof",
                )
        except Exception as exc:
            cleanup_errors.append(f"hotkey_stop_failed:{exc}")
        try:
            if not (tray_stop.get("status") == "tray_presence_stopped" and tray_stop.get("tray_presence") is False):
                _stop_tray(
                    client,
                    approval_id=tray_approval_id,
                    actor=actor,
                    reason="fallback cleanup for persistent supervision API execution proof",
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
                    reason="fallback cleanup for persistent supervision API execution proof",
                )
        except Exception as exc:
            cleanup_errors.append(f"resident_stop_failed:{exc}")
        if cleanup_errors:
            raise RuntimeError(f"persistent supervision API proof cleanup failed: {cleanup_errors!r}")


try:
    exit_code, payload = _run()
except Exception as exc:
    exit_code = 1
    payload = {
        "ok": False,
        "kind": "lens.host.persistent_supervision.api_execution.proof",
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
$PreviousServiceConfigPath = [string]$env:FRANCIS_LENS_HOST_SERVICE_CONFIG_PATH
$PreviousProofMode = [string]$env:FRANCIS_PROOF_MODE
$PreviousProofRunSeconds = [string]$env:FRANCIS_PROOF_RUN_SECONDS
$PreviousActorScopes = [string]$env:FRANCIS_API_ACTOR_SCOPES
$PreviousPythonPath = [string]$env:PYTHONPATH

try {
  $env:FRANCIS_ROOT = $RepoRoot
  $env:FRANCIS_DATA_DIR = $ProofDataRoot
  $env:FRANCIS_LENS_HOST_SERVICE_CONFIG_PATH = $ProofServiceConfigPath
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
  $ProofRuntimeDir = Join-Path $ProofDataRoot 'runtime\lens-persistent-supervision-api-execution-proof'
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
  if ([string]::IsNullOrWhiteSpace($PreviousServiceConfigPath)) {
    Remove-Item Env:\FRANCIS_LENS_HOST_SERVICE_CONFIG_PATH -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_LENS_HOST_SERVICE_CONFIG_PATH = $PreviousServiceConfigPath
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
