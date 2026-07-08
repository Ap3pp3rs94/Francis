[CmdletBinding()]
param(
  [ValidateSet('Status', 'RequestNext', 'GrantNext', 'ExecuteNext')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [string]$ServiceConfigPath = '',

  [string]$Actor = '',

  [string]$ApprovalId = '',

  [string]$Reason = 'request next Stage 6 Lens prerequisite authority review',

  [int]$RunSeconds = 2,

  [ValidateSet('', 'WindowsSapi', 'ElevenLabs')]
  [string]$OverlayVoiceProvider = '',

  [switch]$ConfirmRequest,

  [switch]$ConfirmGrant,

  [switch]$ConfirmExecute
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
  $DataDir = Join-Path $RepoRoot 'data'
}

$PlanDataRoot = [System.IO.Path]::GetFullPath($DataDir)
$PythonPath = Get-PythonPath
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
  [ordered]@{
    ok = $false
    kind = 'lens.stage6.prerequisite_bringup.plan'
    status = 'plan_failed'
    mode = $Mode.ToLowerInvariant()
    repo_root = $RepoRoot
    data_root = $PlanDataRoot
    error = 'python_unavailable'
  } | ConvertTo-Json -Depth 8
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


REQUIREMENT_ORDER = [
    "resident_host_process",
    "tray_presence",
    "global_hotkey_binding",
    "overlay_window",
    "summon_binding",
]

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"

FAMILY_BY_REQUIREMENT = {
    "resident_host_process": "resident_host",
    "tray_presence": "tray_presence",
    "global_hotkey_binding": "global_hotkey_binding",
    "overlay_window": "overlay_window",
    "summon_binding": "summon_binding",
}

PROOF_BY_REQUIREMENT = {
    "resident_host_process": "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status",
    "tray_presence": "scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status",
    "global_hotkey_binding": "scripts/lens-summon-global-hotkey-binding-blocker-proof.ps1 -Mode Status",
    "overlay_window": "scripts/lens-summon-overlay-window-blocker-proof.ps1 -Mode Status",
    "summon_binding": "scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status",
}

READINESS_BY_REQUIREMENT = {
    "resident_host_process": "/lens/host/runtime-loop/readiness",
    "tray_presence": "/lens/tray/readiness",
    "global_hotkey_binding": "/lens/summon/readiness",
    "overlay_window": "/lens/overlay/readiness",
    "summon_binding": "/lens/summon/readiness",
}

DEFAULT_GAP_BY_REQUIREMENT = {
    "resident_host_process": "resident_host_process_not_supervised",
    "tray_presence": "summon_tray_presence_blocker_boundary",
    "global_hotkey_binding": "os_level_command_palette_binding",
    "overlay_window": "summon_overlay_window_blocker_boundary",
    "summon_binding": "summon_anywhere_blockers",
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if str(item).strip()]


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _active_receipt_id(readback: dict[str, Any]) -> str:
    active = _as_dict(readback.get("active_authority_grant"))
    if not active:
        active = _as_dict(readback.get("active_latest"))
    return _safe_str(active.get("receipt_id"))


def _active_approval_id(readback: dict[str, Any]) -> str:
    active = _as_dict(readback.get("active_authority_grant"))
    if not active:
        active = _as_dict(readback.get("active_latest"))
    return _safe_str(active.get("approval_id"))


def _authority_state(readback: dict[str, Any], authority_field: str = "") -> dict[str, Any]:
    authority_granted = bool(readback.get("authority_granted"))
    if authority_field:
        authority_granted = authority_granted or bool(readback.get(authority_field))
    return {
        "status": _safe_str(readback.get("status")),
        "route": _safe_str(readback.get("route")),
        "authority_route": _safe_str(readback.get("authority_route")),
        "request_route": _safe_str(readback.get("request_route")),
        "grants_route": _safe_str(readback.get("grants_route")),
        "execute_route": _safe_str(readback.get("execute_route")),
        "action": _safe_str(readback.get("action")),
        "authority_granted": authority_granted,
        "active_grant_receipt_id": _active_receipt_id(readback),
    }


def _pending_count(readback: dict[str, Any]) -> int:
    raw = readback.get("pending_count")
    if raw is None:
        raw = _as_dict(readback.get("approval_counts")).get("pending")
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def _approved_count(readback: dict[str, Any]) -> int:
    raw = readback.get("approved_count")
    if raw is None:
        raw = _as_dict(readback.get("approval_counts")).get("approved")
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def _latest_approved_id(readback: dict[str, Any]) -> str:
    by_status = _as_dict(readback.get("by_status"))
    for item in _as_list(by_status.get("approved")):
        candidate = _as_dict(item)
        approval_id = _safe_str(candidate.get("id"))
        if approval_id:
            return approval_id
    latest = _as_dict(readback.get("latest"))
    if _safe_str(latest.get("status")) == "approved":
        return _safe_str(latest.get("id"))
    return _safe_str(readback.get("latest_approval_id"))


def _latest_pending_id(readback: dict[str, Any]) -> str:
    by_status = _as_dict(readback.get("by_status"))
    for item in _as_list(by_status.get("pending")):
        candidate = _as_dict(item)
        approval_id = _safe_str(candidate.get("id"))
        if approval_id:
            return approval_id
    latest = _as_dict(readback.get("latest"))
    if _safe_str(latest.get("status")) == "pending":
        return _safe_str(latest.get("id"))
    return _safe_str(readback.get("latest_pending_approval_id"))


def _approval_decision_payload_shape(pending_approval_id: str) -> dict[str, str]:
    return {
        "id": pending_approval_id or "<pending_approval_id>",
        "action": "approve",
        "comment": "<comment>",
        "actor": "<actor>",
    }


def _approval_decision_powershell(pending_approval_id: str) -> str:
    approval_id = pending_approval_id or "<pending_approval_id>"
    return (
        "$body = @{ id = '"
        + approval_id
        + "'; action = 'approve'; comment = '<comment>'; actor = '<actor>' } | ConvertTo-Json -Compress; "
        + "Invoke-RestMethod -Method Post -Uri '"
        + DEFAULT_API_BASE_URL
        + "/approvals/decision' -ContentType 'application/json' -Body $body"
    )


def _approval_decision_command(pending_approval_id: str) -> dict[str, Any]:
    return {
        "command": _approval_decision_powershell(pending_approval_id),
        "route": "/approvals/decision",
        "method": "POST",
        "api_base_url": DEFAULT_API_BASE_URL,
        "payload_shape": _approval_decision_payload_shape(pending_approval_id),
        "required_scope": "approvals.decide",
        "requires_running_api": True,
        "requires_local_caller_unless_remote_enabled": True,
        "remote_enable_env_var": "FRANCIS_APPROVALS_ALLOW_REMOTE_DECISIONS",
        "requires_operator_actor": True,
        "would_decide_approval_if_run": True,
        "status_readback_would_decide_approval": False,
    }


def _approval_request_payload_shape() -> dict[str, str]:
    return {
        "actor": "<actor>",
        "reason": "<reason>",
    }


def _approval_request_powershell(route: str) -> str:
    return (
        "$body = @{ actor = '<actor>'; reason = '<reason>' } | ConvertTo-Json -Compress; "
        + "Invoke-RestMethod -Method Post -Uri '"
        + DEFAULT_API_BASE_URL
        + route
        + "' -ContentType 'application/json' -Body $body"
    )


def _approval_request_command(route: str) -> dict[str, Any]:
    return {
        "command": _approval_request_powershell(route),
        "route": route,
        "method": "POST",
        "api_base_url": DEFAULT_API_BASE_URL,
        "payload_shape": _approval_request_payload_shape(),
        "required_scope": "system.write",
        "requires_running_api": True,
        "requires_operator_actor": True,
        "would_request_approval_if_run": True,
        "status_readback_would_request_approval": False,
    }


def _approval_request_contract(action_id: str, route: str, approval_action: str) -> dict[str, Any]:
    return {
        "route": route,
        "method": "POST",
        "action_id": action_id,
        "approval_action": approval_action,
        "payload_shape": _approval_request_payload_shape(),
        "required_scope": "system.write",
        "actor_scope_policy_contract": _actor_scope_policy_contract(scope_required=True),
        "creates": "approval_request",
        "would_request_approval": False,
        "would_grant_authority": False,
        "would_execute": False,
        "would_mutate_runtime": False,
    }


def _action(
    action_id: str,
    *,
    route: str,
    method: str = "POST",
    approval_action: str = "",
    requires: list[str] | None = None,
    mode: str = "",
    live_effect: str = "",
) -> dict[str, Any]:
    action = {
        "id": action_id,
        "route": route,
        "method": method,
        "approval_action": approval_action,
        "requires": list(requires or []),
        "mode": mode,
        "live_effect": live_effect,
        "operator_supplied_values_required": True,
        "script_would_execute": False,
        "script_would_mutate": False,
    }
    if action_id.startswith("request_"):
        action["approval_request_contract"] = _approval_request_contract(action_id, route, approval_action)
        action["approval_request_command"] = _approval_request_command(route)
    return action


def _await_action(
    action_id: str,
    *,
    route: str,
    approval_action: str,
    readback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_readback = _as_dict(readback)
    pending_approval_id = _latest_pending_id(request_readback)
    return {
        "id": action_id,
        "route": route,
        "method": "GET",
        "approval_action": approval_action,
        "requires": ["operator approval decision"],
        "mode": "",
        "live_effect": "wait for existing approval request decision",
        "operator_supplied_values_required": False,
        "approval_decision_required": True,
        "pending_approval_count": _pending_count(request_readback),
        "pending_approval_id": pending_approval_id,
        "decision_route": _safe_str(request_readback.get("decision_route")) or "/approvals/decision",
        "approval_decision_contract": {
            "route": _safe_str(request_readback.get("decision_route")) or "/approvals/decision",
            "method": "POST",
            "payload_shape": _approval_decision_payload_shape(pending_approval_id),
            "allowed_actions": ["approve", "reject", "emergency"],
            "required_scope": "approvals.decide",
            "actor_scope_policy_contract": {
                "env_var": "FRANCIS_API_ACTOR_SCOPES",
                "json_shape": {"<actor>": ["approvals.decide"]},
                "required_scope": "approvals.decide",
                "actor_placeholder": "<actor>",
                "scope_required": True,
                "powershell_example": "$env:FRANCIS_API_ACTOR_SCOPES = '{\"<actor>\":[\"approvals.decide\"]}'",
            },
            "local_caller_required_unless_remote_enabled": True,
            "remote_enable_env_var": "FRANCIS_APPROVALS_ALLOW_REMOTE_DECISIONS",
            "would_decide_approval": False,
        },
        "approval_decision_command": _approval_decision_command(pending_approval_id),
        "request_status": _safe_str(request_readback.get("status")),
        "script_would_execute": False,
        "script_would_mutate": False,
    }


def _select_approved_request_action(
    *,
    action_id: str,
    route: str,
    approval_action: str,
    approved_approval_id: str,
    grant_action: dict[str, Any],
) -> dict[str, Any]:
    follow_up_grant_action = dict(grant_action)
    follow_up_grant_action["approved_approval_id"] = approved_approval_id
    follow_up_grant_action["preview_only"] = True
    follow_up_grant_action["availability_reason"] = "approved_request_selected_but_authority_grant_is_separate_operator_step"
    return {
        "id": action_id,
        "route": route,
        "method": "GET",
        "approval_action": approval_action,
        "requires": ["exact approved resident runtime authority approval_id"],
        "mode": "approval_readback",
        "live_effect": "select approved resident-runtime authority request without writing a grant receipt",
        "operator_supplied_values_required": False,
        "approval_decision_required": False,
        "approved_approval_id": approved_approval_id,
        "follow_up_grant_action": follow_up_grant_action,
        "script_would_execute": False,
        "script_would_mutate": False,
        "script_would_request_authority": False,
        "script_would_grant_authority": False,
        "script_would_decide_approval": False,
    }


def _resident_actions() -> list[dict[str, Any]]:
    return [
        _action(
            "request_resident_runtime_execution_authority",
            route="/lens/resident-runtime/authority-grant/request",
            approval_action="lens.resident_runtime.execution_authority",
            requires=["actor with system.write scope"],
            live_effect="approval request receipt only",
        ),
        _action(
            "grant_resident_runtime_execution_authority",
            route="/lens/resident-runtime/authority-grant",
            approval_action="lens.resident_runtime.execution_authority",
            requires=["exact approved resident runtime authority approval_id"],
            live_effect="resident runtime authority grant receipt",
        ),
        _action(
            "request_host_supervision_authority",
            route="/lens/host/supervision/authority/request",
            approval_action="lens.host.supervision_authority",
            requires=["actor with system.write scope"],
            live_effect="host supervision authority request receipt only",
        ),
        _action(
            "grant_host_supervision_authority",
            route="/lens/host/supervision/authority",
            approval_action="lens.host.supervision_authority",
            requires=["exact approved host supervision authority approval_id"],
            live_effect="host supervision authority grant receipt",
        ),
        _action(
            "execute_supervised_resident_host_start",
            route="/lens/resident-runtime/execute",
            approval_action="lens.resident_runtime.execution_authority",
            requires=[
                "resident runtime authority grant",
                "host supervision authority grant",
                "actor with system.write scope",
            ],
            mode="resident_start",
            live_effect="bounded supervised resident host lease",
        ),
    ]


def _surface_actions(requirement_id: str, readback: dict[str, Any]) -> list[dict[str, Any]]:
    action = _safe_str(readback.get("action"))
    request_route = _safe_str(readback.get("request_route"))
    authority_route = _safe_str(readback.get("authority_route"))
    execute_route = _safe_str(readback.get("execute_route"))
    if requirement_id == "global_hotkey_binding":
        action = action or "lens.os_binding.command_palette_binding_authority"
        request_route = request_route or "/lens/os-binding/authority/request"
        authority_route = authority_route or "/lens/os-binding/authority"
        execute_route = execute_route or "/lens/os-binding/execute"
        execute_mode = "bind"
        live_effect = "bounded global hotkey binding lease"
    elif requirement_id == "tray_presence":
        action = action or "lens.tray.presence_authority"
        request_route = request_route or "/lens/tray/authority/request"
        authority_route = authority_route or "/lens/tray/authority"
        execute_route = execute_route or "/lens/tray/execute"
        execute_mode = "start"
        live_effect = "bounded tray presence lease"
    elif requirement_id == "overlay_window":
        action = action or "lens.overlay.window_authority"
        request_route = request_route or "/lens/overlay/authority/request"
        authority_route = authority_route or "/lens/overlay/authority"
        execute_route = execute_route or "/lens/overlay/execute"
        execute_mode = "start"
        live_effect = "bounded overlay window lease"
    else:
        action = action or "lens.summon.action_authority"
        request_route = request_route or "/lens/summon/authority/request"
        authority_route = authority_route or "/lens/summon/authority"
        execute_route = execute_route or "/lens/summon/execute"
        execute_mode = "execute"
        live_effect = "bounded summon handoff without summon-anywhere claim"
    return [
        _action(
            f"request_{requirement_id}_authority",
            route=request_route,
            approval_action=action,
            requires=["actor with system.write scope"],
            live_effect="approval request receipt only",
        ),
        _action(
            f"grant_{requirement_id}_authority",
            route=authority_route,
            approval_action=action,
            requires=[f"exact approved {action} approval_id"],
            live_effect="authority grant receipt",
        ),
        _action(
            f"execute_{requirement_id}",
            route=execute_route,
            approval_action=action,
            requires=["active authority grant", "actor with system.write scope"],
            mode=execute_mode,
            live_effect=live_effect,
        ),
    ]


def _next_action(requirement_id: str, status: dict[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any]:
    if requirement_id == "resident_host_process":
        resident_grants = _as_dict(status.get("resident_runtime_authority_grant_receipts"))
        host_grants = _as_dict(status.get("supervision_authority_grant_receipts"))
        resident_granted = bool(resident_grants.get("authority_granted"))
        host_granted = bool(host_grants.get("authority_granted"))
        resident_requests = _as_dict(status.get("resident_runtime_authority_requests"))
        host_requests = _as_dict(_as_dict(status.get("resident_host")).get("supervision_authority_requests"))
        if not resident_granted:
            if _approved_count(resident_requests) > 0:
                return _select_approved_request_action(
                    action_id="select_exact_approved_resident_runtime_execution_authority_request",
                    route="/lens/resident-runtime/authority-grant/requests",
                    approval_action="lens.resident_runtime.execution_authority",
                    approved_approval_id=_latest_approved_id(resident_requests),
                    grant_action=actions[1],
                )
            if _pending_count(resident_requests) > 0:
                return _await_action(
                    "await_resident_runtime_execution_authority_approval",
                    route="/lens/resident-runtime/authority-grant/requests",
                    approval_action="lens.resident_runtime.execution_authority",
                    readback=resident_requests,
                )
            return actions[0]
        if not host_granted:
            if _approved_count(host_requests) > 0:
                grant_action = dict(actions[3])
                grant_action["approved_approval_id"] = _latest_approved_id(host_requests)
                return grant_action
            if _pending_count(host_requests) > 0:
                return _await_action(
                    "await_host_supervision_authority_approval",
                    route="/lens/host/supervision/authority/requests",
                    approval_action="lens.host.supervision_authority",
                    readback=host_requests,
                )
            return actions[2]
        execute_action = dict(actions[-1])
        execute_action["active_approval_id"] = _active_approval_id(resident_grants)
        execute_action["host_supervision_active_approval_id"] = _active_approval_id(host_grants)
        return execute_action
    readback_key = {
        "tray_presence": "tray_authority_requests",
        "global_hotkey_binding": "os_binding_authority_requests",
        "overlay_window": "overlay_authority_requests",
        "summon_binding": "summon_authority_requests",
    }.get(requirement_id, "")
    readback = _as_dict(status.get(readback_key))
    if bool(readback.get("authority_granted")):
        execute_action = dict(actions[-1])
        execute_action["active_approval_id"] = _active_approval_id(readback)
        return execute_action
    if _approved_count(readback) > 0:
        grant_action = dict(actions[1])
        grant_action["approved_approval_id"] = _latest_approved_id(readback)
        return grant_action
    if _pending_count(readback) > 0:
        return _await_action(
            f"await_{requirement_id}_authority_approval",
            route=_safe_str(readback.get("route")) or actions[0]["route"],
            approval_action=_safe_str(readback.get("action")) or actions[0]["approval_action"],
            readback=readback,
        )
    return actions[0]


def _requirement_step(requirement_id: str, dependency: dict[str, Any], handoff: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
    is_first = requirement_id == _safe_str(handoff.get("id"))
    ready = bool(dependency.get("ready"))
    readback_key = {
        "tray_presence": "tray_authority_requests",
        "global_hotkey_binding": "os_binding_authority_requests",
        "overlay_window": "overlay_authority_requests",
        "summon_binding": "summon_authority_requests",
    }.get(requirement_id, "")
    if requirement_id == "resident_host_process":
        authority_state = {
            "resident_runtime": _authority_state(_as_dict(status.get("resident_runtime_authority_grant_receipts")), "resident_runtime_execution_authority"),
            "host_supervision": _authority_state(_as_dict(status.get("supervision_authority_grant_receipts")), "host_supervision_authority"),
        }
        actions = _resident_actions()
    else:
        authority_state = _authority_state(_as_dict(status.get(readback_key)))
        actions = _surface_actions(requirement_id, _as_dict(status.get(readback_key)))
    next_action = _next_action(requirement_id, status, actions)
    return {
        "id": requirement_id,
        "family": _safe_str(dependency.get("family")) or FAMILY_BY_REQUIREMENT[requirement_id],
        "route": _safe_str(dependency.get("route")) or ("/lens/host" if requirement_id == "resident_host_process" else ""),
        "readiness_route": _safe_str(dependency.get("readiness_route")) or READINESS_BY_REQUIREMENT[requirement_id],
        "ready": ready,
        "status": "ready" if ready else "blocked",
        "requirement_state": _safe_str(dependency.get("requirement_state")),
        "blocker": _safe_str(dependency.get("blocker")),
        "blocked_reason": _safe_str(dependency.get("blocked_reason")),
        "proof_script": _safe_str(handoff.get("proof_script")) if is_first else PROOF_BY_REQUIREMENT[requirement_id],
        "next_smallest_truthful_gap": (
            _safe_str(handoff.get("next_smallest_truthful_gap"))
            if is_first
            else DEFAULT_GAP_BY_REQUIREMENT[requirement_id]
        ),
        "authority_state": authority_state,
        "actions": actions,
        "next_operator_action": next_action,
        "script_would_execute": False,
        "script_would_mutate": False,
    }


def _enablement_steps(handoff: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _action(
            "request_persistent_supervision_enablement_authority",
            route=_safe_str(handoff.get("persistent_supervision_enablement_authority_request_route"))
            or "/lens/host/persistent-supervision/enablement/authority/request",
            approval_action="lens.host.persistent_supervision_enablement_authority",
            requires=["all required prerequisite surfaces ready", "actor with system.write scope"],
            live_effect="persistent supervision enablement authority request receipt only",
        ),
        _action(
            "grant_persistent_supervision_enablement_authority",
            route=_safe_str(handoff.get("persistent_supervision_enablement_authority_route"))
            or "/lens/host/persistent-supervision/enablement/authority",
            approval_action="lens.host.persistent_supervision_enablement_authority",
            requires=["exact approved persistent supervision enablement authority approval_id"],
            live_effect="persistent supervision enablement authority grant receipt",
        ),
        _action(
            "request_persistent_supervision_execution_authority",
            route=_safe_str(handoff.get("persistent_supervision_enablement_execution_request_route"))
            or "/lens/host/persistent-supervision/enablement/execution/request",
            approval_action="lens.host.persistent_supervision_enablement_execution_authority",
            requires=["persistent supervision enablement authority grant", "actor with system.write scope"],
            live_effect="persistent supervision execution authority request receipt only",
        ),
        _action(
            "grant_persistent_supervision_execution_authority",
            route=_safe_str(handoff.get("persistent_supervision_enablement_execution_authority_route"))
            or "/lens/host/persistent-supervision/enablement/execution/authority",
            approval_action="lens.host.persistent_supervision_enablement_execution_authority",
            requires=["exact approved persistent supervision execution authority approval_id"],
            live_effect="persistent supervision execution authority grant receipt",
        ),
        _action(
            "apply_persistent_supervision_enablement",
            route="/lens/host/persistent-supervision/enablement/execution/apply",
            approval_action="lens.host.persistent_supervision_enablement_execution_authority",
            requires=[
                "all prerequisite surfaces ready",
                "persistent supervision enablement authority grant",
                "persistent supervision execution authority grant",
                "actor with system.write scope",
            ],
            live_effect="persistent supervision service config update and execution receipt",
        ),
    ]


def _enablement_execution_applied(readback: dict[str, Any]) -> bool:
    latest = _as_dict(readback.get("latest"))
    latest_status = _safe_str(latest.get("status"))
    return (
        latest_status in {"service_config_updated", "service_config_already_enabled"}
        and bool(readback.get("persistent_supervision_enablement_allowed"))
        and bool(readback.get("persistent_supervision_ready"))
    )


def _enablement_execution_review_action(readback: dict[str, Any]) -> dict[str, Any]:
    latest = _as_dict(readback.get("latest"))
    return {
        "id": "review_persistent_supervision_enablement_receipt",
        "route": _safe_str(readback.get("route")) or "/lens/host/persistent-supervision/enablement/executions",
        "method": "GET",
        "approval_action": "lens.host.persistent_supervision_enablement_execution_authority",
        "requires": ["persistent supervision enablement execution receipt readback"],
        "mode": "readback",
        "live_effect": "persistent supervision enablement execution receipt is recorded; review resident claim boundary next",
        "operator_supplied_values_required": False,
        "script_would_execute": False,
        "script_would_mutate": False,
        "latest_receipt_id": _safe_str(latest.get("receipt_id")),
    }


def _next_enablement_action(actions: list[dict[str, Any]], resident_host: dict[str, Any]) -> dict[str, Any]:
    enablement_requests = _as_dict(resident_host.get("persistent_supervision_enablement_authority_requests"))
    enablement_grants = _as_dict(resident_host.get("persistent_supervision_enablement_authority_grants"))
    execution_requests = _as_dict(resident_host.get("persistent_supervision_enablement_execution_requests"))
    execution_grants = _as_dict(resident_host.get("persistent_supervision_enablement_execution_authority_grants"))
    execution_receipts = _as_dict(resident_host.get("persistent_supervision_enablement_execution_receipts"))

    if _enablement_execution_applied(execution_receipts):
        return _enablement_execution_review_action(execution_receipts)

    if not bool(enablement_grants.get("authority_granted")):
        if _approved_count(enablement_requests) > 0:
            grant_action = dict(actions[1])
            grant_action["approved_approval_id"] = _latest_approved_id(enablement_requests)
            return grant_action
        if _pending_count(enablement_requests) > 0:
            return _await_action(
                "await_persistent_supervision_enablement_authority_approval",
                route=_safe_str(enablement_requests.get("route"))
                or "/lens/host/persistent-supervision/enablement/authority/requests",
                approval_action="lens.host.persistent_supervision_enablement_authority",
                readback=enablement_requests,
            )
        return actions[0]

    if not bool(execution_grants.get("authority_granted")):
        if _approved_count(execution_requests) > 0:
            grant_action = dict(actions[3])
            grant_action["approved_approval_id"] = _latest_approved_id(execution_requests)
            return grant_action
        if _pending_count(execution_requests) > 0:
            return _await_action(
                "await_persistent_supervision_execution_authority_approval",
                route=_safe_str(execution_requests.get("route"))
                or "/lens/host/persistent-supervision/enablement/execution/requests",
                approval_action="lens.host.persistent_supervision_enablement_execution_authority",
                readback=execution_requests,
            )
        return actions[2]

    apply_action = dict(actions[-1])
    apply_action["active_approval_id"] = _active_approval_id(execution_grants)
    apply_action["enablement_active_approval_id"] = _active_approval_id(enablement_grants)
    return apply_action


def _current_truthful_gap(plan: dict[str, Any], missing_steps: list[dict[str, Any]]) -> dict[str, Any]:
    if missing_steps:
        first = missing_steps[0]
        first_gap = _safe_str(first.get("next_smallest_truthful_gap"))
        return {
            "gap": "persistent_supervision_required_prerequisites_missing",
            "basis": "missing_required_before_enable",
            "first_missing_requirement": _safe_str(first.get("id")),
            "first_missing_truthful_gap": first_gap,
            "raw_persistent_supervision_gap": _safe_str(plan.get("next_smallest_truthful_gap")),
        }
    return {
        "gap": _safe_str(plan.get("next_smallest_truthful_gap")) or "persistent_supervision_enablement_sequence_ready",
        "basis": "persistent_supervision_plan.next_smallest_truthful_gap",
        "first_missing_requirement": "",
        "first_missing_truthful_gap": "",
        "raw_persistent_supervision_gap": _safe_str(plan.get("next_smallest_truthful_gap")),
    }


def _applied_receipt_truthful_gap(plan: dict[str, Any], execution_receipts: dict[str, Any]) -> dict[str, Any]:
    latest = _as_dict(execution_receipts.get("latest"))
    post_plan = _as_dict(latest.get("post_plan"))
    receipt_gap = _safe_str(post_plan.get("next_smallest_truthful_gap"))
    return {
        "gap": receipt_gap
        or _safe_str(plan.get("next_smallest_truthful_gap"))
        or "persistent_supervision_execution_boundary",
        "basis": (
            "persistent_supervision_enablement_execution_receipt.post_plan.next_smallest_truthful_gap"
            if receipt_gap
            else "persistent_supervision_plan.next_smallest_truthful_gap"
        ),
        "first_missing_requirement": "",
        "first_missing_truthful_gap": "",
        "raw_persistent_supervision_gap": _safe_str(plan.get("next_smallest_truthful_gap")),
    }


def _operator_command(action: dict[str, Any]) -> dict[str, Any]:
    action_id = _safe_str(action.get("id"))
    approval_id = _safe_str(action.get("approved_approval_id")) or _safe_str(action.get("active_approval_id"))
    approval_arg = approval_id if approval_id else "<approval_id>"
    if action_id.startswith("request_"):
        command = ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode RequestNext -Actor <actor> -ConfirmRequest"
        return {
            "command": command,
            "mode": "RequestNext",
            "requires_confirmation": True,
            "requires_approval_id": False,
            "requires_operator_approval_decision": False,
            "approval_request_command": action.get("approval_request_command", {}),
        }
    if action_id.startswith("select_"):
        return {
            "command": ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
            "mode": "Status",
            "requires_confirmation": False,
            "requires_approval_id": False,
            "requires_operator_approval_decision": False,
        }
    if action_id.startswith("grant_"):
        command = (
            ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 "
            f"-Mode GrantNext -Actor <actor> -ApprovalId {approval_arg} -ConfirmGrant"
        )
        return {
            "command": command,
            "mode": "GrantNext",
            "requires_confirmation": True,
            "requires_approval_id": True,
            "requires_operator_approval_decision": True,
        }
    if action_id.startswith("execute_") or action_id.startswith("apply_"):
        voice_provider_arg = ""
        if action_id == "execute_overlay_window":
            voice_provider = _safe_str(action.get("overlay_voice_provider")) or "<WindowsSapi|ElevenLabs>"
            voice_provider_arg = f" -OverlayVoiceProvider {voice_provider}"
        command = (
            ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 "
            f"-Mode ExecuteNext -Actor <actor> -ApprovalId {approval_arg} -RunSeconds 2"
            f"{voice_provider_arg} -ConfirmExecute"
        )
        result = {
            "command": command,
            "mode": "ExecuteNext",
            "requires_confirmation": True,
            "requires_approval_id": True,
            "requires_operator_approval_decision": False,
        }
        if action_id == "execute_overlay_window":
            result["overlay_voice_provider_required"] = True
            result["overlay_voice_provider_options"] = ["WindowsSapi", "ElevenLabs"]
        return result
    if action_id.startswith("await_"):
        return {
            "command": ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
            "mode": "Status",
            "requires_confirmation": False,
            "requires_approval_id": False,
            "requires_operator_approval_decision": True,
            "approval_decision_command": action.get("approval_decision_command", {}),
        }
    return {
        "command": ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
        "mode": "Status",
        "requires_confirmation": False,
        "requires_approval_id": False,
        "requires_operator_approval_decision": False,
    }


def _operator_sequence_with_commands(
    actions: list[dict[str, Any]],
    current_action: dict[str, Any],
) -> list[dict[str, Any]]:
    sequence: list[dict[str, Any]] = []
    current_id = _safe_str(current_action.get("id"))
    current_route = _safe_str(current_action.get("route"))
    for action in actions:
        item = dict(action)
        available_now = (
            bool(current_id)
            and bool(current_route)
            and _safe_str(item.get("id")) == current_id
            and _safe_str(item.get("route")) == current_route
        )
        operator_command = _operator_command(item)
        operator_command["available_now"] = available_now
        operator_command["preview_only"] = not available_now
        operator_command["availability_reason"] = (
            "current_next_operator_action" if available_now else "future_step_waiting_on_prior_prerequisites"
        )
        item["operator_command"] = operator_command
        sequence.append(item)
    return sequence


def _is_grant_action(action: dict[str, Any]) -> bool:
    return _safe_str(action.get("id")).startswith("grant_")


def _follow_up_grant_action(action: dict[str, Any]) -> dict[str, Any]:
    candidate = _as_dict(action.get("follow_up_grant_action"))
    return dict(candidate) if _is_grant_action(candidate) else {}


def _is_execution_action(action: dict[str, Any]) -> bool:
    action_id = _safe_str(action.get("id"))
    return action_id.startswith("execute_") or action_id.startswith("apply_")


def _grant_target_action(
    next_operator_action: dict[str, Any],
    approval_id: str,
    ordered_steps: list[dict[str, Any]],
    enablement_sequence: list[dict[str, Any]],
    resident_host: dict[str, Any],
) -> dict[str, Any]:
    if _is_grant_action(next_operator_action):
        action = dict(next_operator_action)
        action["grant_target_source"] = "current_next_operator_action"
        return action

    requested_approval_id = _safe_str(approval_id).strip()
    if not requested_approval_id:
        return dict(next_operator_action)

    candidates: list[dict[str, Any]] = []
    follow_up_candidate = _follow_up_grant_action(next_operator_action)
    if follow_up_candidate:
        candidates.append(follow_up_candidate)
    for step in ordered_steps:
        candidate = _as_dict(step.get("next_operator_action"))
        if _is_grant_action(candidate):
            candidates.append(dict(candidate))
        follow_up_candidate = _follow_up_grant_action(candidate)
        if follow_up_candidate:
            candidates.append(follow_up_candidate)

    enablement_candidate = _next_enablement_action(enablement_sequence, resident_host)
    if _is_grant_action(enablement_candidate):
        candidates.append(dict(enablement_candidate))

    for candidate in candidates:
        if _safe_str(candidate.get("approved_approval_id")).strip() != requested_approval_id:
            continue
        candidate["grant_target_source"] = (
            "selected_approved_request_handoff"
            if _safe_str(next_operator_action.get("id")).startswith("select_")
            else "approved_approval_id_handoff"
        )
        candidate["selected_instead_of_next_operator_action_id"] = _safe_str(next_operator_action.get("id"))
        return candidate

    return dict(next_operator_action)


def _execute_target_action(
    next_operator_action: dict[str, Any],
    approval_id: str,
    ordered_steps: list[dict[str, Any]],
    enablement_sequence: list[dict[str, Any]],
    resident_host: dict[str, Any],
) -> dict[str, Any]:
    if _is_execution_action(next_operator_action):
        action = dict(next_operator_action)
        action["execute_target_source"] = "current_next_operator_action"
        return action

    requested_approval_id = _safe_str(approval_id).strip()
    if not requested_approval_id:
        return dict(next_operator_action)

    candidates: list[dict[str, Any]] = []
    for step in ordered_steps:
        candidate = _as_dict(step.get("next_operator_action"))
        if _is_execution_action(candidate):
            candidates.append(dict(candidate))

    enablement_candidate = _next_enablement_action(enablement_sequence, resident_host)
    if _is_execution_action(enablement_candidate):
        candidates.append(dict(enablement_candidate))

    for candidate in candidates:
        active_approval_id = _safe_str(candidate.get("active_approval_id")).strip()
        approved_approval_id = _safe_str(candidate.get("approved_approval_id")).strip()
        if active_approval_id == requested_approval_id:
            candidate["execute_target_source"] = "active_approval_id_handoff"
        elif approved_approval_id == requested_approval_id:
            candidate["execute_target_source"] = "approved_approval_id_handoff"
        else:
            continue
        candidate["selected_instead_of_next_operator_action_id"] = _safe_str(next_operator_action.get("id"))
        return candidate

    return dict(next_operator_action)


def _actor_scope_policy_contract(*, scope_required: bool) -> dict[str, Any]:
    return {
        "env_var": "FRANCIS_API_ACTOR_SCOPES",
        "json_shape": {"<actor>": ["system.write"]},
        "required_scope": "system.write" if scope_required else "",
        "actor_placeholder": "<actor>",
        "scope_required": scope_required,
        "powershell_example": "$env:FRANCIS_API_ACTOR_SCOPES = '{\"<actor>\":[\"system.write\"]}'",
    }


def _next_operator_actor_scope_readiness(actor: str, action: dict[str, Any]) -> dict[str, Any]:
    configured_policy = bool(os.environ.get("FRANCIS_API_ACTOR_SCOPES", "").strip())
    action_id = _safe_str(action.get("id"))
    route = _safe_str(action.get("route"))
    method = _safe_str(action.get("method")) or "POST"
    read_only_wait = method.upper() == "GET" or action_id.startswith("await_")
    policy_contract = _actor_scope_policy_contract(scope_required=not read_only_wait)
    if read_only_wait:
        evidence = {
            "actor_present": bool(actor),
            "route": route,
            "method": method,
            "action_id": action_id,
            "required_scope_count": 0,
            "scope_required": False,
        }
        payload = {
            "ready": True,
            "allowed": True,
            "reason": "not_required",
            "actor_present": bool(actor),
            "configured_actor_scope_policy": configured_policy,
            "scope_required": False,
            "required_scope": "",
            "route": route,
            "method": method,
            "action_id": action_id,
            "operator_must_supply_actor": False,
            "actor_scope_policy_contract": policy_contract,
            "evidence": evidence,
        }
        if actor:
            payload["actor"] = actor
        return payload
    if not actor:
        return {
            "ready": False,
            "allowed": False,
            "reason": "actor_not_supplied",
            "actor_present": False,
            "configured_actor_scope_policy": configured_policy,
            "scope_required": True,
            "required_scope": "system.write",
            "route": route,
            "method": method,
            "action_id": action_id,
            "operator_must_supply_actor": True,
            "actor_scope_policy_contract": policy_contract,
            "evidence": {
                "actor_present": False,
                "route": route,
                "method": method,
                "action_id": action_id,
                "required_scope_count": 1,
                "scope_required": True,
            },
        }

    from francis.governance.api_permission_gate import ApiPermissionGate

    decision = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=["system.write"],
        route=route,
        method=method,
    )
    return {
        "ready": bool(decision.allowed),
        "allowed": bool(decision.allowed),
        "reason": _safe_str(decision.reason),
        "actor_present": True,
        "actor": actor,
        "configured_actor_scope_policy": configured_policy,
        "scope_required": True,
        "required_scope": "system.write",
        "route": route,
        "method": method,
        "action_id": action_id,
        "operator_must_supply_actor": False,
        "actor_scope_policy_contract": policy_contract,
        "evidence": decision.evidence,
    }


_MAX_STAGE6_PREREQUISITE_RUN_SECONDS = 15 * 60


def _check(check_id: str, status: str, passed: bool, evidence: str, reason: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": status,
        "passed": passed,
        "evidence": evidence,
        "reason": reason,
    }


def _request_next_action(action: dict[str, Any], actor: str, reason: str) -> dict[str, Any]:
    action_id = _safe_str(action.get("id"))
    route = _safe_str(action.get("route"))
    request_reason = reason or "request next Stage 6 Lens prerequisite authority review"
    if not actor:
        return {
            "ok": False,
            "status": "refused_actor_required",
            "approval_requested": False,
            "action_id": action_id,
            "route": route,
            "reason": "actor_required_for_authority_request",
        }
    if not action_id.startswith("request_"):
        return {
            "ok": False,
            "status": "blocked_next_action_not_request",
            "approval_requested": False,
            "action_id": action_id,
            "route": route,
            "reason": "next_operator_action_is_not_an_authority_request",
        }

    from francis.lens.activation import (
        request_lens_host_persistent_supervision_enablement_authority,
        request_lens_host_persistent_supervision_enablement_execution_authority,
        request_lens_host_supervision_authority,
        request_lens_resident_runtime_execution_authority,
    )
    from francis.lens.os_binding_authority import request_lens_os_binding_authority
    from francis.lens.overlay_authority import request_lens_overlay_authority
    from francis.lens.summon_authority import request_lens_summon_authority
    from francis.lens.tray_authority import request_lens_tray_authority

    requesters = {
        "request_resident_runtime_execution_authority": request_lens_resident_runtime_execution_authority,
        "request_host_supervision_authority": request_lens_host_supervision_authority,
        "request_tray_presence_authority": request_lens_tray_authority,
        "request_global_hotkey_binding_authority": request_lens_os_binding_authority,
        "request_overlay_window_authority": request_lens_overlay_authority,
        "request_summon_binding_authority": request_lens_summon_authority,
        "request_persistent_supervision_enablement_authority": request_lens_host_persistent_supervision_enablement_authority,
        "request_persistent_supervision_execution_authority": request_lens_host_persistent_supervision_enablement_execution_authority,
    }
    requester = requesters.get(action_id)
    if requester is None:
        return {
            "ok": False,
            "status": "blocked_unknown_request_action",
            "approval_requested": False,
            "action_id": action_id,
            "route": route,
            "reason": "unknown_request_action",
        }
    result = requester(actor=actor, reason=request_reason, route=route, method="POST")
    return {
        "ok": bool(result.get("ok")),
        "status": _safe_str(result.get("status")),
        "approval_requested": bool(result.get("approval_requested")),
        "action_id": action_id,
        "route": route,
        "approval_action": _safe_str(result.get("action")) or _safe_str(action.get("approval_action")),
        "approval_id": _safe_str(result.get("approval_id")),
        "actor": actor,
        "result": result,
        "governance": {
            "uses_existing_authority_request_route": True,
            "approval_request_write": bool(result.get("approval_requested")),
            "approval_decision_authority": False,
            "authority_grant": False,
            "execution_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "service_control_authority": False,
            "tray_registration_authority": False,
            "hotkey_registration_authority": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "memory_write": False,
            "resident_claim_authority": False,
            "mutation_authority_granted": bool(result.get("approval_requested")),
        },
    }


def _grant_next_action(action: dict[str, Any], actor: str, approval_id: str, reason: str) -> dict[str, Any]:
    action_id = _safe_str(action.get("id"))
    route = _safe_str(action.get("route"))
    grant_reason = reason or "grant next Stage 6 Lens prerequisite authority receipt"
    if not actor:
        return {
            "ok": False,
            "status": "refused_actor_required",
            "authority_granted": False,
            "receipt_written": False,
            "action_id": action_id,
            "route": route,
            "reason": "actor_required_for_authority_grant",
        }
    if not approval_id:
        return {
            "ok": False,
            "status": "refused_approval_id_required",
            "authority_granted": False,
            "receipt_written": False,
            "action_id": action_id,
            "route": route,
            "reason": "approval_id_required_for_authority_grant",
        }
    if not action_id.startswith("grant_"):
        return {
            "ok": False,
            "status": "blocked_next_action_not_grant",
            "authority_granted": False,
            "receipt_written": False,
            "action_id": action_id,
            "route": route,
            "reason": "next_operator_action_is_not_an_authority_grant",
        }

    from francis.lens.activation import (
        grant_lens_host_persistent_supervision_enablement_authority,
        grant_lens_host_persistent_supervision_enablement_execution_authority,
        grant_lens_host_supervision_authority,
        grant_lens_resident_runtime_execution_authority,
    )
    from francis.lens.os_binding_authority import grant_lens_os_binding_authority
    from francis.lens.overlay_authority import grant_lens_overlay_authority
    from francis.lens.summon_authority import grant_lens_summon_authority
    from francis.lens.tray_authority import grant_lens_tray_authority

    granters = {
        "grant_resident_runtime_execution_authority": grant_lens_resident_runtime_execution_authority,
        "grant_host_supervision_authority": grant_lens_host_supervision_authority,
        "grant_tray_presence_authority": grant_lens_tray_authority,
        "grant_global_hotkey_binding_authority": grant_lens_os_binding_authority,
        "grant_overlay_window_authority": grant_lens_overlay_authority,
        "grant_summon_binding_authority": grant_lens_summon_authority,
        "grant_persistent_supervision_enablement_authority": grant_lens_host_persistent_supervision_enablement_authority,
        "grant_persistent_supervision_execution_authority": (
            grant_lens_host_persistent_supervision_enablement_execution_authority
        ),
    }
    granter = granters.get(action_id)
    if granter is None:
        return {
            "ok": False,
            "status": "blocked_unknown_grant_action",
            "authority_granted": False,
            "receipt_written": False,
            "action_id": action_id,
            "route": route,
            "reason": "unknown_grant_action",
        }
    result = granter(
        approval_id=approval_id,
        actor=actor,
        reason=grant_reason,
        route=route,
        method="POST",
        record_receipt=True,
    )
    authority_granted = bool(result.get("authority_granted"))
    receipt_written = bool(result.get("receipt_written"))
    result_governance = _as_dict(result.get("governance"))
    return {
        "ok": bool(result.get("ok")) and authority_granted,
        "status": _safe_str(result.get("status")),
        "authority_granted": authority_granted,
        "receipt_written": receipt_written,
        "action_id": action_id,
        "route": route,
        "approval_action": _safe_str(action.get("approval_action")),
        "approval_id": approval_id,
        "actor": actor,
        "result": result,
        "governance": {
            "uses_existing_authority_grant_route": True,
            "approval_request_write": False,
            "approval_decision_authority": False,
            "authority_grant": authority_granted,
            "authority_grant_receipt_write": receipt_written,
            "receipt_write_authority": bool(result_governance.get("receipt_write_authority")) or receipt_written,
            "execution_authority": False,
            "local_process_launch_authority": False,
            "would_execute": False,
            "would_mutate_runtime_or_config": False,
            "memory_write": False,
            "resident_claim_authority": False,
            "mutation_authority_granted": bool(result_governance.get("mutation_authority_granted")),
        },
    }


def _safe_run_seconds(value: str) -> int:
    try:
        parsed = int(float(value or "2"))
    except (TypeError, ValueError):
        return 2
    return max(0, min(parsed, _MAX_STAGE6_PREREQUISITE_RUN_SECONDS))


def _execute_next_action(
    action: dict[str, Any],
    actor: str,
    approval_id: str,
    reason: str,
    run_seconds: int,
    overlay_voice_provider: str = "",
) -> dict[str, Any]:
    action_id = _safe_str(action.get("id"))
    route = _safe_str(action.get("route"))
    execute_reason = reason or "execute next Stage 6 Lens prerequisite boundary"
    if not actor:
        return {
            "ok": False,
            "status": "refused_actor_required",
            "executed": False,
            "receipt_written": False,
            "action_id": action_id,
            "route": route,
            "reason": "actor_required_for_execution_boundary",
        }
    if not approval_id:
        return {
            "ok": False,
            "status": "refused_approval_id_required",
            "executed": False,
            "receipt_written": False,
            "action_id": action_id,
            "route": route,
            "reason": "approval_id_required_for_execution_boundary",
        }
    if not (action_id.startswith("execute_") or action_id.startswith("apply_")):
        return {
            "ok": False,
            "status": "blocked_next_action_not_execution",
            "executed": False,
            "receipt_written": False,
            "action_id": action_id,
            "route": route,
            "reason": "next_operator_action_is_not_an_execution_boundary",
        }

    from francis.lens.activation import (
        execute_lens_host_persistent_supervision_enablement,
        execute_lens_resident_runtime_activation,
    )
    from francis.lens.os_binding_authority import execute_lens_os_binding
    from francis.lens.overlay_authority import execute_lens_overlay_window
    from francis.lens.summon_authority import execute_lens_summon_action
    from francis.lens.tray_authority import execute_lens_tray_presence

    safe_seconds = _safe_run_seconds(str(run_seconds))
    if action_id == "execute_supervised_resident_host_start":
        result = execute_lens_resident_runtime_activation(
            approval_id=approval_id,
            actor=actor,
            reason=execute_reason,
            route=route,
            method="POST",
            record_receipt=True,
            run_seconds=safe_seconds,
        )
    elif action_id == "execute_tray_presence":
        result = execute_lens_tray_presence(
            approval_id=approval_id,
            actor=actor,
            reason=execute_reason,
            route=route,
            method="POST",
            record_receipt=True,
            mode=_safe_str(action.get("mode")) or "start",
            run_seconds=safe_seconds,
        )
    elif action_id == "execute_global_hotkey_binding":
        proof_global_hotkey = os.environ.get("FRANCIS_PROOF_GLOBAL_HOTKEY", "").strip()
        result = execute_lens_os_binding(
            approval_id=approval_id,
            actor=actor,
            reason=execute_reason,
            route=route,
            method="POST",
            record_receipt=True,
            mode=_safe_str(action.get("mode")) or "bind",
            run_seconds=safe_seconds,
            global_hotkey=proof_global_hotkey,
        )
    elif action_id == "execute_overlay_window":
        result = execute_lens_overlay_window(
            approval_id=approval_id,
            actor=actor,
            reason=execute_reason,
            route=route,
            method="POST",
            record_receipt=True,
            mode=_safe_str(action.get("mode")) or "start",
            run_seconds=safe_seconds,
            voice_provider=overlay_voice_provider,
        )
    elif action_id == "execute_summon_binding":
        result = execute_lens_summon_action(
            approval_id=approval_id,
            actor=actor,
            reason=execute_reason,
            route=route,
            method="POST",
            record_receipt=True,
            mode=_safe_str(action.get("mode")) or "execute",
            run_seconds=safe_seconds,
            allow_launch=False,
        )
    elif action_id == "apply_persistent_supervision_enablement":
        result = execute_lens_host_persistent_supervision_enablement(
            approval_id=approval_id,
            actor=actor,
            reason=execute_reason,
            route=route,
            method="POST",
            record_receipt=True,
        )
    else:
        return {
            "ok": False,
            "status": "blocked_unknown_execution_action",
            "executed": False,
            "receipt_written": False,
            "action_id": action_id,
            "route": route,
            "reason": "unknown_execution_action",
        }

    result_governance = _as_dict(result.get("governance"))
    executed = bool(result.get("executed") or result.get("applied"))
    receipt_written = bool(result.get("receipt_written"))
    return {
        "ok": bool(result.get("ok")) and executed,
        "status": _safe_str(result.get("status")),
        "executed": executed,
        "receipt_written": receipt_written,
        "action_id": action_id,
        "route": route,
        "approval_action": _safe_str(action.get("approval_action")),
        "approval_id": approval_id,
        "actor": actor,
        "run_seconds": safe_seconds,
        "result": result,
        "governance": {
            "uses_existing_execution_route": True,
            "approval_request_write": False,
            "approval_decision_authority": False,
            "authority_grant": False,
            "execution_receipt_write": receipt_written,
            "execution_authority": executed,
            "local_process_launch_authority": bool(result_governance.get("local_process_launch_authority")),
            "process_supervision_authority": bool(result_governance.get("process_supervision_authority")),
            "service_config_write_authority": bool(result_governance.get("service_config_write_authority")),
            "would_execute": True,
            "would_mutate_runtime_or_config": executed,
            "memory_write": False,
            "resident_claim_authority": False,
            "mutation_authority_granted": bool(result_governance.get("mutation_authority_granted")) or executed,
        },
    }


def _run() -> tuple[int, dict[str, Any]]:
    from francis.lens.status import lens_status

    mode = os.environ.get("FRANCIS_PROOF_MODE", "status")
    actor = os.environ.get("FRANCIS_BRINGUP_ACTOR", "").strip()
    approval_id = os.environ.get("FRANCIS_BRINGUP_APPROVAL_ID", "").strip()
    reason = os.environ.get("FRANCIS_BRINGUP_REASON", "").strip()
    run_seconds = _safe_run_seconds(os.environ.get("FRANCIS_BRINGUP_RUN_SECONDS", "2"))
    overlay_voice_provider = os.environ.get("FRANCIS_BRINGUP_OVERLAY_VOICE_PROVIDER", "").strip()
    confirm_request = os.environ.get("FRANCIS_BRINGUP_CONFIRM_REQUEST", "").strip() == "1"
    confirm_grant = os.environ.get("FRANCIS_BRINGUP_CONFIRM_GRANT", "").strip() == "1"
    confirm_execute = os.environ.get("FRANCIS_BRINGUP_CONFIRM_EXECUTE", "").strip() == "1"
    repo_root = Path(os.environ["FRANCIS_ROOT"]).resolve()
    data_root = Path(os.environ["FRANCIS_DATA_DIR"]).resolve()
    status = lens_status(limit=10)
    readiness = _as_dict(status.get("stage6_readiness"))
    closure = _as_dict(readiness.get("closure_readback"))
    resident_host = _as_dict(status.get("resident_host"))
    plan = _as_dict(resident_host.get("persistent_supervision_plan"))
    enablement = _as_dict(resident_host.get("persistent_supervision_enablement"))
    dependencies = _as_list(plan.get("enablement_dependency_readback")) or _as_list(
        enablement.get("enablement_dependency_readback")
    )
    dependency_by_id = {_safe_str(item.get("id")): _as_dict(item) for item in dependencies if isinstance(item, dict)}
    required = _string_list(plan.get("required_before_enable")) or REQUIREMENT_ORDER
    missing = _string_list(plan.get("missing_required_before_enable"))
    raw_handoff = _as_dict(plan.get("first_missing_requirement_handoff")) or _as_dict(
        enablement.get("first_missing_requirement_handoff")
    )
    ordered_steps = [
        _requirement_step(requirement, dependency_by_id.get(requirement, {}), raw_handoff, status)
        for requirement in REQUIREMENT_ORDER
    ]
    enablement_sequence = _enablement_steps(raw_handoff)
    enablement_execution_receipts = _as_dict(resident_host.get("persistent_supervision_enablement_execution_receipts"))
    runtime_missing_steps = [
        step for step in ordered_steps if step["id"] in missing or not bool(step["ready"])
    ]
    enablement_execution_applied = _enablement_execution_applied(enablement_execution_receipts)
    handoff = {} if enablement_execution_applied and not runtime_missing_steps else raw_handoff
    effective_missing = missing if missing else [_safe_str(step.get("id")) for step in runtime_missing_steps]
    missing_steps = runtime_missing_steps
    next_operator_action = (
        missing_steps[0]["next_operator_action"]
        if missing_steps
        else _next_enablement_action(enablement_sequence, resident_host)
    )
    next_operator_actor_scope_readiness = _next_operator_actor_scope_readiness(actor, next_operator_action)
    current_gap = (
        _current_truthful_gap(plan, missing_steps)
        if missing_steps
        else _applied_receipt_truthful_gap(plan, enablement_execution_receipts)
        if enablement_execution_applied
        else _current_truthful_gap(plan, missing_steps)
    )
    next_operator_command = _operator_command(next_operator_action)
    operator_sequence = _operator_sequence_with_commands(
        [step["next_operator_action"] for step in missing_steps] or [next_operator_action],
        next_operator_action,
    )
    available_now_count = sum(
        1 for item in operator_sequence if bool(_as_dict(item.get("operator_command")).get("available_now"))
    )
    preview_only_count = sum(
        1 for item in operator_sequence if bool(_as_dict(item.get("operator_command")).get("preview_only"))
    )
    command_availability_truthful = (
        bool(operator_sequence)
        and available_now_count == 1
        and available_now_count + preview_only_count == len(operator_sequence)
    )
    next_operator_action_id = _safe_str(next_operator_action.get("id"))
    recommended_next_slice = (
        f"run_stage6_prerequisite_bringup_{next_operator_action_id}"
        if next_operator_action_id
        else "run_stage6_prerequisite_bringup_plan_status"
    )
    recommended_authority_required = "none_readback_only"
    if (
        bool(next_operator_command.get("requires_approval_id"))
        or bool(next_operator_command.get("requires_confirmation"))
        or bool(next_operator_action.get("operator_supplied_values_required"))
    ):
        recommended_authority_required = (
            _safe_str(next_operator_action.get("approval_action")) or "operator_supplied_authority"
        )
    prerequisites_ready = len(missing_steps) == 0
    chain_complete = all(step["actions"] for step in ordered_steps) and len(enablement_sequence) == 5
    no_first_handoff_required = not handoff
    first_handoff_bounded = (
        no_first_handoff_required
        or (
            handoff.get("read_only_contract") is True
            and handoff.get("diagnostic_only") is True
            and handoff.get("would_execute") is False
            and handoff.get("would_mutate") is False
        )
    )
    checks = [
        _check(
            "stage6_status_readback",
            _safe_str(readiness.get("stage_state")) or "unknown",
            _safe_str(readiness.get("stage_state")) == "active",
            "/lens/status stage6_readiness",
            "The bring-up plan is only valid against the active Stage 6 Lens posture.",
        ),
        _check(
            "required_prerequisite_chain",
            "ready" if set(REQUIREMENT_ORDER).issubset(set(required)) else "missing",
            set(REQUIREMENT_ORDER).issubset(set(required)),
            "/lens/status resident_host.persistent_supervision_plan.required_before_enable",
            "The plan must cover every surface required before persistent supervision enablement.",
        ),
        _check(
            "operator_sequence_complete",
            "complete" if chain_complete else "incomplete",
            chain_complete,
            "ordered_prerequisite_steps + persistent_supervision_enablement_steps",
            "Every prerequisite must have explicit request, grant, and execute/apply actions.",
        ),
        _check(
            "first_missing_handoff_bounded",
            (
                "not_applicable"
                if no_first_handoff_required
                else "readback_only"
                if first_handoff_bounded
                else "unexpected_authority"
            ),
            first_handoff_bounded,
            "first_missing_requirement_handoff",
            "The first missing prerequisite handoff must remain read-only and non-mutating.",
        ),
        _check(
            "operator_sequence_command_availability",
            "truthful" if command_availability_truthful else "inconsistent",
            command_availability_truthful,
            "operator_sequence.operator_command",
            "Exactly one operator-sequence command may be available now; all future steps must remain preview-only.",
        ),
        _check(
            "next_operator_actor_scope_readiness",
            "ready"
            if next_operator_actor_scope_readiness["ready"]
            else _safe_str(next_operator_actor_scope_readiness["reason"]) or "not_ready",
            True,
            "FRANCIS_API_ACTOR_SCOPES + -Actor",
            "The runbook reports whether the supplied actor can perform the next request/grant/execute boundary; Status mode does not create that authority.",
        ),
        _check(
            "script_side_effects_denied",
            "readback_only",
            True,
            "script default Mode=Status",
            "Status is read-only; RequestNext and GrantNext require explicit confirmation and never execute, mutate runtime config, write memory, or claim residency.",
        ),
    ]
    request_result: dict[str, Any] = {}
    grant_result: dict[str, Any] = {}
    execute_result: dict[str, Any] = {}
    grant_target_action = (
        _grant_target_action(
            next_operator_action,
            approval_id,
            ordered_steps,
            enablement_sequence,
            resident_host,
        )
        if mode == "grantnext"
        else {}
    )
    execute_target_action = (
        _execute_target_action(
            next_operator_action,
            approval_id,
            ordered_steps,
            enablement_sequence,
            resident_host,
        )
        if mode == "executenext"
        else {}
    )
    if mode == "requestnext":
        if not confirm_request:
            request_result = {
                "ok": False,
                "status": "refused_confirmation_required",
                "approval_requested": False,
                "reason": "confirm_request_required",
            }
        else:
            request_result = _request_next_action(next_operator_action, actor, reason)
    if mode == "grantnext":
        if not confirm_grant:
            grant_result = {
                "ok": False,
                "status": "refused_confirmation_required",
                "authority_granted": False,
                "receipt_written": False,
                "reason": "confirm_grant_required",
            }
        else:
            grant_result = _grant_next_action(grant_target_action, actor, approval_id, reason)
    if mode == "executenext":
        if not confirm_execute:
            execute_result = {
                "ok": False,
                "status": "refused_confirmation_required",
                "executed": False,
                "receipt_written": False,
                "reason": "confirm_execute_required",
            }
        else:
            execute_result = _execute_next_action(
                execute_target_action,
                actor,
                approval_id,
                reason,
                run_seconds,
                overlay_voice_provider=overlay_voice_provider,
            )
    ok = all(item["passed"] for item in checks)
    mode_result = (
        request_result
        if mode == "requestnext"
        else grant_result
        if mode == "grantnext"
        else execute_result
    )
    payload = {
        "ok": ok if mode == "status" else bool(mode_result.get("ok")),
        "kind": "lens.stage6.prerequisite_bringup.plan",
        "status": (
            _safe_str(mode_result.get("status"))
            if mode in {"requestnext", "grantnext", "executenext"}
            else "blocked"
            if missing_steps
            else "persistent_supervision_enablement_applied"
            if enablement_execution_applied
            else "ready_for_persistent_supervision_enablement_sequence"
        ),
        "mode": mode,
        "repo_root": str(repo_root),
        "data_root": str(data_root),
        "stage": "Stage 6 / Lens MVP",
        "stage_state": _safe_str(readiness.get("stage_state")),
        "ready_to_close": bool(readiness.get("ready_to_close")),
        "acceptance_criterion": "system_resident_presence",
        "closure_next_smallest_truthful_gap": _safe_str(closure.get("next_smallest_truthful_gap")),
        "persistent_supervision_next_smallest_truthful_gap": _safe_str(plan.get("next_smallest_truthful_gap")),
        "current_truthful_gap": current_gap["gap"],
        "current_truthful_gap_basis": current_gap["basis"],
        "current_first_missing_requirement": current_gap["first_missing_requirement"],
        "current_first_missing_truthful_gap": current_gap["first_missing_truthful_gap"],
        "raw_persistent_supervision_next_smallest_truthful_gap": current_gap["raw_persistent_supervision_gap"],
        "next_smallest_truthful_gap": current_gap["gap"],
        "next_smallest_truthful_gap_basis": current_gap["basis"],
        "recommended_next_slice": recommended_next_slice,
        "recommended_proof_script": "scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
        "authority_required": recommended_authority_required,
        "authority_granted": mode == "grantnext" and bool(grant_result.get("authority_granted")),
        "operator_supplied_values_required": bool(next_operator_action.get("operator_supplied_values_required")),
        "requires_confirmation": bool(next_operator_command.get("requires_confirmation")),
        "requires_approval_id": bool(next_operator_command.get("requires_approval_id")),
        "requires_operator_approval_decision": bool(next_operator_command.get("requires_operator_approval_decision")),
        "would_execute": mode == "executenext" and confirm_execute,
        "would_mutate": mode == "executenext" and bool(execute_result.get("executed")),
        "required_before_enable": required,
        "missing_required_before_enable": effective_missing,
        "required_before_enable_ready": prerequisites_ready,
        "first_missing_required_before_enable": (
            ""
            if enablement_execution_applied and not missing_steps
            else _safe_str(plan.get("first_missing_required_before_enable"))
            or (_safe_str(missing_steps[0].get("id")) if missing_steps else "")
        ),
        "first_missing_requirement_handoff": handoff,
        "ordered_prerequisite_steps": ordered_steps,
        "persistent_supervision_enablement_steps": enablement_sequence,
        "next_operator_action": next_operator_action,
        "next_operator_action_requirement": (
            missing_steps[0]["id"]
            if missing_steps
            else "persistent_supervision_enablement_receipt"
            if enablement_execution_applied
            else "persistent_supervision_enablement"
        ),
        "next_operator_command": next_operator_command,
        "next_operator_actor_scope_readiness": next_operator_actor_scope_readiness,
        "operator_sequence": operator_sequence,
        "operator_sequence_command_availability": {
            "available_now_count": available_now_count,
            "preview_only_count": preview_only_count,
            "sequence_length": len(operator_sequence),
            "truthful": command_availability_truthful,
        },
        "grant_target_action": grant_target_action,
        "execute_target_action": execute_target_action,
        "request_result": request_result,
        "grant_result": grant_result,
        "execute_result": execute_result,
        "checks": checks,
        "evidence": [
            "/lens/status",
            "/lens/status resident_host.persistent_supervision_plan",
            "/lens/status resident_host.persistent_supervision_enablement",
            "/lens/status stage6_readiness.closure_readback",
        ],
        "governance": {
            "read_only_contract": mode == "status",
            "diagnostic_only": mode == "status",
            "plan_only": mode == "status",
            "requires_explicit_operator_execution": True,
            "request_next_mode_available": True,
            "grant_next_mode_available": True,
            "execute_next_mode_available": True,
            "run_mode_available": False,
            "actor_scope_readback": True,
            "next_operator_actor_ready": bool(next_operator_actor_scope_readiness.get("ready")),
            "operator_actor_required": not bool(next_operator_actor_scope_readiness.get("ready")),
            "approval_request_write": mode == "requestnext" and bool(request_result.get("approval_requested")),
            "authority_grant_receipt_write": mode == "grantnext" and bool(grant_result.get("receipt_written")),
            "execution_receipt_write": mode == "executenext" and bool(execute_result.get("receipt_written")),
            "would_request_authority": mode == "requestnext" and confirm_request,
            "would_grant_authority": mode == "grantnext" and confirm_grant,
            "authority_granted": mode == "grantnext" and bool(grant_result.get("authority_granted")),
            "would_execute": mode == "executenext" and confirm_execute,
            "would_mutate": mode == "executenext" and bool(execute_result.get("executed")),
            "execution_authority": mode == "executenext" and bool(execute_result.get("executed")),
            "approval_decision_authority": False,
            "local_process_launch_authority": mode == "executenext"
            and bool(_as_dict(execute_result.get("governance")).get("local_process_launch_authority")),
            "process_supervision_authority": mode == "executenext"
            and bool(_as_dict(execute_result.get("governance")).get("process_supervision_authority")),
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "tray_registration_authority": False,
            "hotkey_registration_authority": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "memory_write": False,
            "receipt_write_authority": False,
            "resident_claim_authority": False,
            "mutation_authority_granted": (
                (mode == "requestnext" and bool(request_result.get("approval_requested")))
                or (mode == "grantnext" and bool(grant_result.get("receipt_written")))
                or (mode == "executenext" and bool(execute_result.get("executed")))
            ),
        },
        "message": (
            "Stage 6 prerequisite bring-up is now an explicit operator plan. "
            "Status mode does not run the plan; RequestNext can create only the next approval request, "
            "GrantNext can grant only an already approved next authority receipt, and ExecuteNext can run "
            "only the current next bounded execution action when explicit confirmation and approval id are supplied."
        ),
    }
    return (0 if bool(payload["ok"]) else 1), payload


try:
    exit_code, payload = _run()
except Exception as exc:
    exit_code = 1
    payload = {
        "ok": False,
        "kind": "lens.stage6.prerequisite_bringup.plan",
        "status": "plan_failed",
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
$PreviousBringupActor = [string]$env:FRANCIS_BRINGUP_ACTOR
$PreviousBringupApprovalId = [string]$env:FRANCIS_BRINGUP_APPROVAL_ID
$PreviousBringupReason = [string]$env:FRANCIS_BRINGUP_REASON
$PreviousBringupRunSeconds = [string]$env:FRANCIS_BRINGUP_RUN_SECONDS
$PreviousBringupOverlayVoiceProvider = [string]$env:FRANCIS_BRINGUP_OVERLAY_VOICE_PROVIDER
$PreviousBringupConfirmRequest = [string]$env:FRANCIS_BRINGUP_CONFIRM_REQUEST
$PreviousBringupConfirmGrant = [string]$env:FRANCIS_BRINGUP_CONFIRM_GRANT
$PreviousBringupConfirmExecute = [string]$env:FRANCIS_BRINGUP_CONFIRM_EXECUTE
$PreviousPythonPath = [string]$env:PYTHONPATH
$ScriptTempRoot = ''
$PythonScriptPath = ''

try {
  $env:FRANCIS_ROOT = $RepoRoot
  $env:FRANCIS_DATA_DIR = $PlanDataRoot
  $env:FRANCIS_ENV_PROFILE = 'dev'
  $env:FRANCIS_RUN_MODE = 'api'
  if ([string]::IsNullOrWhiteSpace($ServiceConfigPath)) {
    Remove-Item Env:\FRANCIS_LENS_HOST_SERVICE_CONFIG_PATH -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_LENS_HOST_SERVICE_CONFIG_PATH = [System.IO.Path]::GetFullPath($ServiceConfigPath)
  }
  $env:FRANCIS_PROOF_MODE = $Mode.ToLowerInvariant()
  $env:FRANCIS_BRINGUP_ACTOR = $Actor
  $env:FRANCIS_BRINGUP_APPROVAL_ID = $ApprovalId
  $env:FRANCIS_BRINGUP_REASON = $Reason
  $env:FRANCIS_BRINGUP_RUN_SECONDS = [string]$RunSeconds
  $env:FRANCIS_BRINGUP_OVERLAY_VOICE_PROVIDER = $OverlayVoiceProvider
  $env:FRANCIS_BRINGUP_CONFIRM_REQUEST = if ($ConfirmRequest) { '1' } else { '0' }
  $env:FRANCIS_BRINGUP_CONFIRM_GRANT = if ($ConfirmGrant) { '1' } else { '0' }
  $env:FRANCIS_BRINGUP_CONFIRM_EXECUTE = if ($ConfirmExecute) { '1' } else { '0' }
  $SourceRoot = Join-Path $RepoRoot 'src'
  if ([string]::IsNullOrWhiteSpace($PreviousPythonPath)) {
    $env:PYTHONPATH = $SourceRoot
  } else {
    $env:PYTHONPATH = $SourceRoot + [System.IO.Path]::PathSeparator + $PreviousPythonPath
  }
  $ScriptTempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-stage6-prerequisite-bringup-plan-" + [guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Force -Path $ScriptTempRoot | Out-Null
  $PythonScriptPath = Join-Path $ScriptTempRoot 'plan.py'
  Set-Content -LiteralPath $PythonScriptPath -Value $Source -Encoding UTF8
  $Output = & $PythonPath $PythonScriptPath 2>&1
  $ExitCode = $LASTEXITCODE
} finally {
  if (-not [string]::IsNullOrWhiteSpace([string]$PythonScriptPath)) {
    Remove-Item -LiteralPath $PythonScriptPath -Force -ErrorAction SilentlyContinue
  }
  if (-not [string]::IsNullOrWhiteSpace([string]$ScriptTempRoot)) {
    Remove-Item -LiteralPath $ScriptTempRoot -Force -ErrorAction SilentlyContinue
  }
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
  if ([string]::IsNullOrWhiteSpace($PreviousServiceConfigPath)) {
    Remove-Item Env:\FRANCIS_LENS_HOST_SERVICE_CONFIG_PATH -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_LENS_HOST_SERVICE_CONFIG_PATH = $PreviousServiceConfigPath
  }
  if ([string]::IsNullOrWhiteSpace($PreviousProofMode)) {
    Remove-Item Env:\FRANCIS_PROOF_MODE -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_PROOF_MODE = $PreviousProofMode
  }
  if ([string]::IsNullOrWhiteSpace($PreviousBringupActor)) {
    Remove-Item Env:\FRANCIS_BRINGUP_ACTOR -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_BRINGUP_ACTOR = $PreviousBringupActor
  }
  if ([string]::IsNullOrWhiteSpace($PreviousBringupApprovalId)) {
    Remove-Item Env:\FRANCIS_BRINGUP_APPROVAL_ID -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_BRINGUP_APPROVAL_ID = $PreviousBringupApprovalId
  }
  if ([string]::IsNullOrWhiteSpace($PreviousBringupReason)) {
    Remove-Item Env:\FRANCIS_BRINGUP_REASON -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_BRINGUP_REASON = $PreviousBringupReason
  }
  if ([string]::IsNullOrWhiteSpace($PreviousBringupRunSeconds)) {
    Remove-Item Env:\FRANCIS_BRINGUP_RUN_SECONDS -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_BRINGUP_RUN_SECONDS = $PreviousBringupRunSeconds
  }
  if ([string]::IsNullOrWhiteSpace($PreviousBringupOverlayVoiceProvider)) {
    Remove-Item Env:\FRANCIS_BRINGUP_OVERLAY_VOICE_PROVIDER -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_BRINGUP_OVERLAY_VOICE_PROVIDER = $PreviousBringupOverlayVoiceProvider
  }
  if ([string]::IsNullOrWhiteSpace($PreviousBringupConfirmRequest)) {
    Remove-Item Env:\FRANCIS_BRINGUP_CONFIRM_REQUEST -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_BRINGUP_CONFIRM_REQUEST = $PreviousBringupConfirmRequest
  }
  if ([string]::IsNullOrWhiteSpace($PreviousBringupConfirmGrant)) {
    Remove-Item Env:\FRANCIS_BRINGUP_CONFIRM_GRANT -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_BRINGUP_CONFIRM_GRANT = $PreviousBringupConfirmGrant
  }
  if ([string]::IsNullOrWhiteSpace($PreviousBringupConfirmExecute)) {
    Remove-Item Env:\FRANCIS_BRINGUP_CONFIRM_EXECUTE -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_BRINGUP_CONFIRM_EXECUTE = $PreviousBringupConfirmExecute
  }
  if ([string]::IsNullOrWhiteSpace($PreviousPythonPath)) {
    Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
  } else {
    $env:PYTHONPATH = $PreviousPythonPath
  }
}

($Output | ForEach-Object { [string]$_ }) -join "`n"
exit $ExitCode
