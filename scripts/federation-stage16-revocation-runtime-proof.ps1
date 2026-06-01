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
    kind = 'francis.stage16.federation.revocation_runtime_proof'
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
  $ProofDataRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-stage16-revocation-runtime-proof\" + [guid]::NewGuid().ToString('N') + "\data")
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

READBACK_ID = "live_revocation_roundtrip_observed"
SOURCE_NODE = "stage16-local-workstation"
PEER_NODE = "stage16-local-loopback-node"
PAIRING_SCOPE = "pairing:stage16-revocation-loopback"
REQUEST_ACTOR = "stage16.federation.revoker"
DECISION_ACTOR = "stage16.local.operator"
STAGE15_RECEIPT_ID = "swarm_stage15_closure_for_stage16_revocation_proof"


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
        "delegation_id": "opdel_stage16_revocation_proof",
        "completion_review_ready": True,
        "stage15_completion_review_ready": True,
        "stage15_closed_by_receipt": True,
        "ready_count": 6,
        "required_count": 6,
        "blockers": [],
        "marks_runtime_stage_state": False,
        "recorded_ts": 1_800_016_900,
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


def _latest_scope_event(items: list[dict[str, Any]], scope: str) -> dict[str, Any]:
    matching = [item for item in items if item.get("scope") == scope]
    if not matching:
        return {}
    return sorted(matching, key=lambda item: int(item.get("ts") or 0), reverse=True)[0]


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
    proof_ts = int(time.time())
    trace_id = f"trace-stage16-revocation-{proof_ts}"

    for node_id, role in ((SOURCE_NODE, "operator_workstation"), (PEER_NODE, "loopback_peer")):
        _post(
            client,
            "/federation/instances/upsert",
            {
                "request_actor": REQUEST_ACTOR,
                "id": node_id,
                "name": node_id,
                "status": "online",
                "endpoint": f"loopback://stage16/{node_id}",
                "region": "local",
                "role": role,
                "capabilities": ["pairing", "revocation", "metadata_readback"],
                "trust_level": 0.25,
                "requires_approval": True,
                "tags": ["stage16", "revocation", "local-loopback"],
                "health": {"status": "observed", "proof_kind": "revocation_runtime_probe"},
                "meta": {"trace_id": trace_id, "contains_raw_private_data": False},
            },
        )

    active = _post(
        client,
        "/federation/delegations/record",
        {
            "request_actor": REQUEST_ACTOR,
            "id": f"deleg-stage16-revocation-active-{proof_ts}",
            "ts": proof_ts,
            "from": SOURCE_NODE,
            "to": PEER_NODE,
            "scope": PAIRING_SCOPE,
            "status": "active",
            "reason": "stage16_revocation_precondition_active_pairing",
            "meta": {
                "trace_id": trace_id,
                "operator_receipt_id": "",
                "revocation_before_reuse_required": True,
                "remote_approval_relays_stopped": False,
                "sync_lanes_stopped": False,
                "authority_expansion": False,
            },
        },
    )
    active_id = str(active.get("id"))
    active_readback = _get(client, "/federation/delegations/list?limit=200")
    active_items = [_as_dict(item) for item in _as_list(active_readback.get("items"))]
    active_latest = _latest_scope_event(active_items, PAIRING_SCOPE)
    active_observed = active_latest.get("status") == "active" and active_latest.get("id") == active_id

    requested = _post(
        client,
        "/approvals/request",
        {
            "request_actor": REQUEST_ACTOR,
            "action": "federation.revocation.local_loopback",
            "reason": "stage16 revocation local-loopback operator receipt request",
            "payload": {
                "revocation_id": f"rev-stage16-{proof_ts}",
                "pairing_request_id": active_id,
                "source_node_id": SOURCE_NODE,
                "paired_node_id": PEER_NODE,
                "revoked_scope": PAIRING_SCOPE,
                "reason": "stage16_revocation_runtime_readback",
                "trace_id": trace_id,
                "operator_receipt_id": "",
                "recorded_ts": proof_ts,
                "effective_ts": proof_ts + 1,
                "request_class": "revocation_metadata",
                "contains_raw_private_data": False,
                "contains_raw_prompt_body": False,
                "contains_raw_model_response": False,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
        },
    )
    approval_id = str(requested.get("id"))
    decided = _post(
        client,
        "/approvals/decision",
        {
            "id": approval_id,
            "action": "approve",
            "actor": DECISION_ACTOR,
            "reason": "stage16_revocation_operator_receipt",
        },
    )
    decision_item = _as_dict(decided.get("item"))
    operator_receipt_observed = (
        decided.get("ok") is True
        and decided.get("status") == "approved"
        and decision_item.get("decision_actor") == DECISION_ACTOR
    )

    revoked = _post(
        client,
        "/federation/delegations/record",
        {
            "request_actor": REQUEST_ACTOR,
            "id": f"deleg-stage16-revocation-revoked-{proof_ts}",
            "ts": proof_ts + 2,
            "from": SOURCE_NODE,
            "to": PEER_NODE,
            "scope": PAIRING_SCOPE,
            "status": "revoked",
            "reason": "stage16_revocation_runtime_readback",
            "meta": {
                "trace_id": trace_id,
                "operator_receipt_id": approval_id,
                "previous_delegation_id": active_id,
                "revocation_before_reuse_required": True,
                "remote_approval_relays_stopped": True,
                "sync_lanes_stopped": True,
                "silent_reactivation_allowed": False,
                "authority_expansion": False,
                "node_attributed_receipt_required": True,
            },
        },
    )
    revoked_id = str(revoked.get("id"))
    all_delegations = _get(client, "/federation/delegations/list?limit=200")
    delegation_items = [_as_dict(item) for item in _as_list(all_delegations.get("items"))]
    latest_scope_event = _latest_scope_event(delegation_items, PAIRING_SCOPE)
    latest_meta = _as_dict(latest_scope_event.get("meta"))
    revoked_observed = (
        latest_scope_event.get("id") == revoked_id
        and latest_scope_event.get("status") == "revoked"
        and latest_meta.get("operator_receipt_id") == approval_id
        and latest_meta.get("remote_approval_relays_stopped") is True
        and latest_meta.get("sync_lanes_stopped") is True
        and latest_meta.get("silent_reactivation_allowed") is False
        and latest_meta.get("authority_expansion") is False
    )

    _post(
        client,
        "/federation/consensus_logs/append",
        {
            "request_actor": REQUEST_ACTOR,
            "id": f"clog-stage16-revocation-{proof_ts}",
            "level": "info",
            "kind": "stage16_revocation_roundtrip",
            "instance_id": SOURCE_NODE,
            "message": "Stage 16 local-loopback revocation request, operator receipt, and revoked scope observed.",
            "meta": {
                "trace_id": trace_id,
                "approval_id": approval_id,
                "revoked_delegation_id": revoked_id,
                "revoked_scope": PAIRING_SCOPE,
                "remote_approval_relays_stopped": True,
                "sync_lanes_stopped": True,
                "authority_expansion": False,
            },
        },
    )
    logs_readback = _get(client, f"/federation/consensus_logs/list?instance_id={SOURCE_NODE}&limit=200")
    logs = [_as_dict(item) for item in _as_list(logs_readback.get("items"))]
    trace_observed = any(
        item.get("kind") == "stage16_revocation_roundtrip"
        and _as_dict(item.get("meta")).get("revoked_delegation_id") == revoked_id
        for item in logs
    )

    roundtrip_observed = active_observed and operator_receipt_observed and revoked_observed and trace_observed
    receipt = _post(
        client,
        "/federation/live-runtime-readback",
        {
            "request_actor": REQUEST_ACTOR,
            "reason": "stage16_revocation_roundtrip_runtime_readback",
            "readback_id": READBACK_ID,
            "observed": roundtrip_observed,
            "proof_kind": "live_runtime_probe",
            "source_node_id": SOURCE_NODE,
            "paired_node_id": PEER_NODE,
            "trace_id": trace_id,
            "parent_receipt_id": approval_id,
            "evidence_summary": "local-loopback active pairing, operator revocation receipt, revoked scope, stopped relay flags, and federation trace observed",
            "recorded_ts": proof_ts,
        },
    )

    after_readbacks = _get(client, "/federation/live-runtime-readbacks")
    after_review = _get(client, "/federation/completion-review")
    status = _get(client, "/federation/status")
    missing = _as_list(after_readbacks.get("missing_readbacks"))
    next_gap = (
        "stage16_sleep_continuity_runtime_readback"
        if READBACK_ID not in missing
        and "workstation_sleep_continuity_validated" in missing
        and "live_pairing_flow_observed" not in missing
        and "live_selective_sync_observed" not in missing
        and "live_remote_approval_roundtrip_observed" not in missing
        else "stage16_live_federation_runtime_readback"
    )

    checks = [
        _check(
            "active_pairing_precondition_readback",
            "active" if active_observed else "missing_or_unexpected",
            active_observed,
            "/federation/delegations/list",
            "revocation proof must start from an active scoped pairing event",
        ),
        _check(
            "operator_revocation_receipt_readback",
            "approved" if operator_receipt_observed else "missing_or_unexpected",
            operator_receipt_observed,
            "/approvals/decision and approved approval readback",
            "revocation requires an operator decision receipt",
        ),
        _check(
            "latest_scope_state_revoked",
            "revoked" if revoked_observed else "missing_or_unexpected",
            revoked_observed,
            "/federation/delegations/list latest event for scope",
            "the latest event for the scoped pairing must be revoked and relay/sync flags must stop",
        ),
        _check(
            "revocation_trace_written",
            "observed" if trace_observed else "missing_or_unexpected",
            trace_observed,
            "/federation/consensus_logs/list",
            "revocation must have node-attributed trace lineage",
        ),
        _check(
            "revocation_runtime_receipt_written",
            "observed" if receipt.get("readback_ready") is True else "missing_or_unexpected",
            receipt.get("readback_ready") is True and receipt.get("readback_id") == READBACK_ID,
            "/federation/live-runtime-readback",
            "the revocation roundtrip must be recorded as completion-eligible live runtime evidence",
        ),
        _check(
            "completion_review_remains_blocked",
            str(after_review.get("status")),
            after_review.get("stage16_completion_review_ready") is False
            and after_review.get("ready_to_close") is False
            and after_readbacks.get("live_runtime_readback_ready") is False,
            "/federation/completion-review",
            "Stage 16 must remain blocked until workstation sleep continuity is proven",
        ),
    ]
    ok = all(bool(item["passed"]) for item in checks)

    return (
        0 if ok else 1,
        {
            "ok": ok,
            "kind": "francis.stage16.federation.revocation_runtime_proof",
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
            "active_delegation_id": active_id,
            "revoked_delegation_id": revoked_id,
            "revoked_scope": PAIRING_SCOPE,
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
                "operator_receipt_required": True,
                "per_node_scope_required": True,
                "latest_scope_event_revoked": True,
                "remote_approval_relays_stopped": True,
                "sync_lanes_stopped": True,
                "silent_reactivation_allowed": False,
                "authority_expansion_allowed": False,
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
            "recommended_next_slice": "collect_sleep_continuity_runtime_readback"
            if next_gap == "stage16_sleep_continuity_runtime_readback"
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
        "kind": "francis.stage16.federation.revocation_runtime_proof",
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
  $env:FRANCIS_API_ACTOR_SCOPES = '{"stage16.federation.revoker":["approvals.request","federation.write"],"stage16.local.operator":["approvals.decide"]}'
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
