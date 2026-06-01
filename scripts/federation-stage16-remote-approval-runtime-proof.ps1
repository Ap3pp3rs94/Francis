[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [switch]$CommitReceipts
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

function Write-ProofFailure {
  param(
    [string]$ErrorCode,
    [string]$DataRoot
  )

  [ordered]@{
    ok = $false
    kind = 'francis.stage16.federation.remote_approval_runtime_proof'
    status = 'proof_failed'
    mode = $Mode.ToLowerInvariant()
    repo_root = $RepoRoot
    data_root = $DataRoot
    error = $ErrorCode
    commit_receipts = [bool]$CommitReceipts
    writes_real_project_data = $false
    ready_to_close = $false
    next_smallest_truthful_gap = 'stage16_live_federation_runtime_readback'
  } | ConvertTo-Json -Depth 6
}

$PythonPath = Get-PythonPath
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
  Write-ProofFailure -ErrorCode 'python_unavailable' -DataRoot ''
  exit 1
}

$ProjectDataRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot 'data'))
if ($CommitReceipts) {
  $Profile = ([string]$env:FRANCIS_ENV_PROFILE).Trim().ToLowerInvariant()
  if ([string]::IsNullOrWhiteSpace($Profile)) {
    $Profile = 'dev'
  }
  if (@('production', 'prod', 'regulated') -contains $Profile) {
    Write-ProofFailure -ErrorCode 'commit_receipts_blocked_in_env_profile' -DataRoot $ProjectDataRoot
    exit 1
  }
  $ProofDataRoot = $ProjectDataRoot
} elseif ([string]::IsNullOrWhiteSpace($DataDir)) {
  $ProofDataRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-stage16-remote-approval-runtime-proof\" + [guid]::NewGuid().ToString('N') + "\data")
} else {
  $ProofDataRoot = [System.IO.Path]::GetFullPath($DataDir)
}

$Source = @'
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

READBACK_ID = "live_remote_approval_roundtrip_observed"
SOURCE_NODE = "stage16-local-workstation"
PEER_NODE = "stage16-local-loopback-node"
REQUEST_ACTOR = "stage16.federation.requester"
DECISION_ACTOR = "stage16.local.operator"
STAGE15_RECEIPT_ID = "swarm_stage15_closure_for_stage16_remote_approval_proof"


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


def _get(client: Any, route: str) -> dict[str, Any]:
    response = client.get(route)
    body = response.json()
    if response.status_code != 200:
        raise RuntimeError(f"{route} returned {response.status_code}: {body!r}")
    return body


def _post(client: Any, route: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(route, json=payload)
    body = response.json()
    if response.status_code != 200:
        raise RuntimeError(f"{route} returned {response.status_code}: {body!r}")
    if body.get("ok") is False:
        raise RuntimeError(f"{route} denied payload: {body!r}")
    return body


def _write_stage15_closure_receipt(data_root: Path) -> None:
    path = data_root / "logs" / "swarm" / "stage15_operator_stage_closure_decisions.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": True,
        "kind": "francis.stage15.swarm.stage15_closure_decision_receipt",
        "receipt_id": STAGE15_RECEIPT_ID,
        "stage": "Stage 15 / Swarm",
        "source_id": "swarm",
        "target": "stage15_swarm",
        "actor": "test.operator",
        "decision": "close_stage15",
        "authority": "delegated_operator",
        "delegation_id": "opdel_stage16_remote_approval_proof",
        "completion_review_ready": True,
        "stage15_completion_review_ready": True,
        "stage15_closed_by_receipt": True,
        "ready_count": 6,
        "required_count": 6,
        "blockers": [],
        "marks_runtime_stage_state": False,
        "recorded_ts": 1_800_016_700,
        "governance": {
            "explicit_operator_decision": True,
            "stage_closure_decision": True,
            "completion_review_ready": True,
            "does_not_mutate_runtime_stage_state": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _run() -> tuple[int, dict[str, Any]]:
    repo_root = Path(os.environ["FRANCIS_ROOT"]).resolve()
    data_root = Path(os.environ["FRANCIS_DATA_DIR"]).resolve()
    commit_receipts = os.environ.get("FRANCIS_STAGE16_COMMIT_RECEIPTS") == "1"
    sys.path.insert(0, str(repo_root / "src"))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    data_root.mkdir(parents=True, exist_ok=True)
    if not commit_receipts:
        _write_stage15_closure_receipt(data_root)

    client = TestClient(create_app())
    before_readbacks = _get(client, "/federation/live-runtime-readbacks")
    before_review = _get(client, "/federation/completion-review")
    trace_id = f"trace-stage16-remote-approval-{int(time.time())}"

    requested = _post(
        client,
        "/approvals/request",
        {
            "request_actor": REQUEST_ACTOR,
            "action": "federation.remote_approval.local_loopback",
            "reason": "stage16 remote approval local-loopback request metadata",
            "payload": {
                "remote_approval_request_id": trace_id,
                "source_node_id": SOURCE_NODE,
                "paired_node_id": PEER_NODE,
                "target_operator_id": DECISION_ACTOR,
                "requested_action": "stage16.remote_approval.readback",
                "requested_scope": "federation.stage16.local_loopback",
                "trace_id": trace_id,
                "parent_receipt_id": STAGE15_RECEIPT_ID,
                "sync_lane_id": "stage16.approval_metadata",
                "recorded_ts": int(time.time()),
                "expires_at": int(time.time()) + 3600,
                "request_class": "approval_request_metadata",
                "contains_raw_private_data": False,
                "contains_raw_prompt_body": False,
                "contains_raw_model_response": False,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
        },
    )
    approval_id = str(requested.get("id"))
    pending = _get(client, "/approvals/list?status=pending&limit=100")
    pending_items = [_as_dict(item) for item in _as_list(pending.get("items"))]
    pending_observed = any(
        item.get("id") == approval_id
        and item.get("status") == "pending"
        and item.get("action") == "federation.remote_approval.local_loopback"
        for item in pending_items
    )

    decided = _post(
        client,
        "/approvals/decision",
        {
            "id": approval_id,
            "action": "approve",
            "actor": DECISION_ACTOR,
            "reason": "stage16_remote_approval_local_loopback_decision_receipt",
        },
    )
    decided_item = _as_dict(decided.get("item"))
    approved = _get(client, "/approvals/list?status=approved&limit=100")
    approved_items = [_as_dict(item) for item in _as_list(approved.get("items"))]
    approved_observed = any(
        item.get("id") == approval_id
        and item.get("status") == "approved"
        and item.get("decision_actor") == DECISION_ACTOR
        for item in approved_items
    )
    pending_after = _get(client, "/approvals/list?status=pending&limit=100")
    pending_after_items = [_as_dict(item) for item in _as_list(pending_after.get("items"))]
    pending_cleared = not any(item.get("id") == approval_id for item in pending_after_items)

    _post(
        client,
        "/federation/consensus_logs/append",
        {
            "request_actor": REQUEST_ACTOR,
            "id": f"clog-stage16-remote-approval-{approval_id}",
            "level": "info",
            "kind": "stage16_remote_approval_roundtrip",
            "instance_id": SOURCE_NODE,
            "message": "Stage 16 local-loopback remote approval request and decision receipt observed.",
            "meta": {
                "trace_id": trace_id,
                "approval_id": approval_id,
                "decision_actor": DECISION_ACTOR,
                "operator_impersonation": False,
                "scope_expansion": False,
                "authority_expansion": False,
            },
        },
    )
    log_readback = _get(client, f"/federation/consensus_logs/list?instance_id={SOURCE_NODE}&limit=100")
    logs = [_as_dict(item) for item in _as_list(log_readback.get("items"))]
    trace_observed = any(
        item.get("kind") == "stage16_remote_approval_roundtrip"
        and _as_dict(item.get("meta")).get("approval_id") == approval_id
        for item in logs
    )

    roundtrip_observed = (
        requested.get("status") == "pending"
        and pending_observed
        and decided.get("ok") is True
        and decided.get("status") == "approved"
        and decided_item.get("decision_actor") == DECISION_ACTOR
        and approved_observed
        and pending_cleared
        and trace_observed
    )
    receipt = _post(
        client,
        "/federation/live-runtime-readback",
        {
            "request_actor": REQUEST_ACTOR,
            "reason": "stage16_remote_approval_roundtrip_runtime_readback",
            "readback_id": READBACK_ID,
            "observed": roundtrip_observed,
            "proof_kind": "live_runtime_probe",
            "source_node_id": SOURCE_NODE,
            "paired_node_id": PEER_NODE,
            "trace_id": trace_id,
            "parent_receipt_id": approval_id,
            "evidence_summary": "local-loopback approval request, pending readback, operator decision receipt, approved readback, and federation trace observed",
            "recorded_ts": int(time.time()),
        },
    )

    after_readbacks = _get(client, "/federation/live-runtime-readbacks")
    after_review = _get(client, "/federation/completion-review")
    status = _get(client, "/federation/status")
    missing = _as_list(after_readbacks.get("missing_readbacks"))
    next_gap = (
        "stage16_revocation_runtime_readback"
        if READBACK_ID not in missing
        and "live_revocation_roundtrip_observed" in missing
        and "live_pairing_flow_observed" not in missing
        and "live_selective_sync_observed" not in missing
        else "stage16_live_federation_runtime_readback"
    )

    checks = [
        _check(
            "approval_request_written",
            "pending" if pending_observed else "missing_or_unexpected",
            pending_observed,
            "/approvals/request and /approvals/list?status=pending",
            "remote approval proof must create and read back a pending approval request",
        ),
        _check(
            "operator_decision_receipt_written",
            "approved" if approved_observed else "missing_or_unexpected",
            approved_observed and pending_cleared,
            "/approvals/decision and /approvals/list?status=approved",
            "the decision must be made by a local operator actor and clear the pending request",
        ),
        _check(
            "federation_trace_written",
            "observed" if trace_observed else "missing_or_unexpected",
            trace_observed,
            "/federation/consensus_logs/list",
            "the approval roundtrip must have a federation trace record",
        ),
        _check(
            "remote_approval_runtime_receipt_written",
            "observed" if receipt.get("readback_ready") is True else "missing_or_unexpected",
            receipt.get("readback_ready") is True and receipt.get("readback_id") == READBACK_ID,
            "/federation/live-runtime-readback",
            "the roundtrip must be recorded as a completion-eligible live runtime receipt",
        ),
        _check(
            "completion_review_remains_blocked",
            str(after_review.get("status")),
            after_review.get("stage16_completion_review_ready") is False
            and after_review.get("ready_to_close") is False
            and after_readbacks.get("live_runtime_readback_ready") is False,
            "/federation/completion-review",
            "Stage 16 must remain blocked until revocation and sleep continuity are also proven",
        ),
    ]
    ok = all(bool(item["passed"]) for item in checks)

    return (
        0 if ok else 1,
        {
            "ok": ok,
            "kind": "francis.stage16.federation.remote_approval_runtime_proof",
            "status": "proof_passed" if ok else "proof_failed",
            "stage": "Stage 16 / Federation",
            "mode": os.environ.get("FRANCIS_PROOF_MODE", "status"),
            "repo_root": str(repo_root),
            "data_root": str(data_root),
            "commit_receipts": commit_receipts,
            "writes_real_project_data": commit_receipts,
            "actor": REQUEST_ACTOR,
            "decision_actor": DECISION_ACTOR,
            "approval_id": approval_id,
            "receipt_id": receipt.get("receipt_id"),
            "readback_id": READBACK_ID,
            "trace_id": trace_id,
            "before_ready_count": before_readbacks.get("ready_count"),
            "before_completion_review_ready": before_review.get("stage16_completion_review_ready"),
            "readback_summary_status": after_readbacks.get("status"),
            "ready_count": after_readbacks.get("ready_count"),
            "completion_eligible_readback_count": after_readbacks.get("completion_eligible_readback_count"),
            "required_count": after_readbacks.get("required_count"),
            "missing_readbacks": missing,
            "live_runtime_readback_ready": after_readbacks.get("live_runtime_readback_ready"),
            "completion_review_ready": after_review.get("stage16_completion_review_ready"),
            "completion_status": after_review.get("status"),
            "ready_to_close": after_review.get("ready_to_close"),
            "status_next_smallest_truthful_gap": status.get("next_smallest_truthful_gap"),
            "governance": {
                "local_loopback_only": True,
                "request_metadata_only": True,
                "decision_receipt_reference_only": True,
                "operator_impersonation_allowed": False,
                "scope_expansion_allowed": False,
                "contains_raw_private_data": False,
                "contains_raw_prompt_body": False,
                "contains_raw_model_response": False,
                "does_not_mark_stage16_closed": True,
                "writes_memory": False,
                "runs_tools": False,
                "runs_shell": False,
                "runs_git": False,
                "launches_browser": False,
                "captures_screen": False,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
            "checks": checks,
            "blockers": [item["id"] for item in checks if not bool(item["passed"])],
            "recommended_next_slice": "collect_revocation_runtime_readback"
            if next_gap == "stage16_revocation_runtime_readback"
            else "collect_remaining_live_federation_runtime_readbacks",
            "next_smallest_truthful_gap": next_gap if ok else "stage16_live_federation_runtime_readback",
        },
    )


try:
    code, payload = _run()
except Exception as exc:
    code = 1
    payload = {
        "ok": False,
        "kind": "francis.stage16.federation.remote_approval_runtime_proof",
        "status": "proof_failed",
        "error": str(exc),
        "error_type": type(exc).__name__,
        "ready_to_close": False,
        "next_smallest_truthful_gap": "stage16_live_federation_runtime_readback",
    }

print(json.dumps(payload, indent=2, sort_keys=True))
sys.exit(code)
'@

$PreviousRoot = [string]$env:FRANCIS_ROOT
$PreviousDataDir = [string]$env:FRANCIS_DATA_DIR
$PreviousActorScopes = [string]$env:FRANCIS_API_ACTOR_SCOPES
$PreviousProofMode = [string]$env:FRANCIS_PROOF_MODE
$PreviousCommitReceipts = [string]$env:FRANCIS_STAGE16_COMMIT_RECEIPTS

try {
  $env:FRANCIS_ROOT = $RepoRoot
  $env:FRANCIS_DATA_DIR = $ProofDataRoot
  $env:FRANCIS_API_ACTOR_SCOPES = '{"stage16.federation.requester":["approvals.request","federation.write"],"stage16.local.operator":["approvals.decide"]}'
  $env:FRANCIS_STAGE16_COMMIT_RECEIPTS = $(if ($CommitReceipts) { '1' } else { '0' })
  $env:FRANCIS_PROOF_MODE = $Mode.ToLowerInvariant()
  $Output = $Source | & $PythonPath -
  $ExitCode = $LASTEXITCODE
  if (-not [string]::IsNullOrWhiteSpace($Output)) {
    $Output
  }
  exit $ExitCode
}
finally {
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
  if ([string]::IsNullOrWhiteSpace($PreviousActorScopes)) {
    Remove-Item Env:\FRANCIS_API_ACTOR_SCOPES -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_API_ACTOR_SCOPES = $PreviousActorScopes
  }
  if ([string]::IsNullOrWhiteSpace($PreviousProofMode)) {
    Remove-Item Env:\FRANCIS_PROOF_MODE -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_PROOF_MODE = $PreviousProofMode
  }
  if ([string]::IsNullOrWhiteSpace($PreviousCommitReceipts)) {
    Remove-Item Env:\FRANCIS_STAGE16_COMMIT_RECEIPTS -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_STAGE16_COMMIT_RECEIPTS = $PreviousCommitReceipts
  }
}
