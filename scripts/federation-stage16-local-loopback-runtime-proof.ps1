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
    kind = 'francis.stage16.federation.local_loopback_runtime_proof'
    status = 'proof_failed'
    mode = $Mode.ToLowerInvariant()
    repo_root = $RepoRoot
    data_root = $DataRoot
    error = $ErrorCode
    commit_receipts = [bool]$CommitReceipts
    writes_real_project_data = $false
    ready_to_close = $false
    next_smallest_truthful_gap = 'stage16_remote_approval_runtime_readback'
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
  $ProofDataRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-stage16-local-loopback-runtime-proof\" + [guid]::NewGuid().ToString('N') + "\data")
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

PROVABLE_READBACK_IDS = [
    "live_pairing_flow_observed",
    "live_selective_sync_observed",
]
REMAINING_READBACK_IDS = [
    "live_remote_approval_roundtrip_observed",
    "live_revocation_roundtrip_observed",
    "workstation_sleep_continuity_validated",
]
ALL_READBACK_IDS = PROVABLE_READBACK_IDS + REMAINING_READBACK_IDS
SOURCE_NODE = "stage16-local-workstation"
PEER_NODE = "stage16-local-loopback-node"
PAIRING_SCOPE = "pairing:stage16-local-loopback"
KNOWLEDGE_ID = "stage16-local-loopback-shared-metadata"
STAGE15_RECEIPT_ID = "swarm_stage15_closure_for_stage16_local_loopback_proof"


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
    if body.get("ok") is not True:
        raise RuntimeError(f"{route} did not accept payload: {body!r}")
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
        "delegation_id": "opdel_stage16_local_loopback_proof",
        "completion_review_ready": True,
        "stage15_completion_review_ready": True,
        "stage15_closed_by_receipt": True,
        "ready_count": 6,
        "required_count": 6,
        "blockers": [],
        "marks_runtime_stage_state": False,
        "recorded_ts": 1_800_016_500,
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
    actor = "codex.builder" if commit_receipts else "test.federation.write"
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
    trace_id = f"trace-stage16-local-loopback-{proof_ts}"

    source = _post(
        client,
        "/federation/instances/upsert",
        {
            "request_actor": actor,
            "id": SOURCE_NODE,
            "name": "Stage 16 Local Workstation",
            "status": "online",
            "endpoint": "loopback://stage16/local-workstation",
            "region": "local",
            "role": "operator_workstation",
            "capabilities": ["pairing", "selective_sync", "metadata_readback"],
            "trust_level": 0.25,
            "requires_approval": True,
            "tags": ["stage16", "local-loopback", "federation-runtime-readback"],
            "health": {"status": "observed", "proof_kind": "local_loopback_runtime_probe"},
            "meta": {
                "trace_id": trace_id,
                "contains_raw_private_data": False,
                "contains_raw_prompt_body": False,
                "contains_raw_model_response": False,
            },
        },
    )
    peer = _post(
        client,
        "/federation/instances/upsert",
        {
            "request_actor": actor,
            "id": PEER_NODE,
            "name": "Stage 16 Local Loopback Node",
            "status": "online",
            "endpoint": "loopback://stage16/local-loopback-node",
            "region": "local",
            "role": "loopback_peer",
            "capabilities": ["pairing", "selective_sync", "metadata_readback"],
            "trust_level": 0.25,
            "requires_approval": True,
            "tags": ["stage16", "local-loopback", "federation-runtime-readback"],
            "health": {"status": "observed", "proof_kind": "local_loopback_runtime_probe"},
            "meta": {
                "trace_id": trace_id,
                "contains_raw_private_data": False,
                "contains_raw_prompt_body": False,
                "contains_raw_model_response": False,
            },
        },
    )
    delegation = _post(
        client,
        "/federation/delegations/record",
        {
            "request_actor": actor,
            "id": "deleg-stage16-local-loopback-pairing",
            "from": SOURCE_NODE,
            "to": PEER_NODE,
            "scope": PAIRING_SCOPE,
            "status": "active",
            "reason": "stage16_local_loopback_pairing_readback",
            "meta": {
                "trace_id": trace_id,
                "local_loopback_only": True,
                "authority_expansion": False,
                "contains_raw_private_data": False,
            },
        },
    )
    knowledge = _post(
        client,
        "/federation/shared_knowledge/publish",
        {
            "request_actor": actor,
            "id": KNOWLEDGE_ID,
            "kind": "metadata",
            "title": "Stage 16 local-loopback metadata sync readback",
            "source_instance_id": SOURCE_NODE,
            "domain": "operations",
            "tags": ["stage16", "local-loopback", "selective-sync"],
            "meta": {
                "trace_id": trace_id,
                "sync_scope": "metadata_only",
                "contains_raw_private_data": False,
                "contains_raw_prompt_body": False,
                "contains_raw_model_response": False,
                "selective_sync_only": True,
            },
        },
    )
    _post(
        client,
        "/federation/consensus_logs/append",
        {
            "request_actor": actor,
            "id": f"clog-stage16-local-loopback-{proof_ts}",
            "level": "info",
            "kind": "stage16_local_loopback_runtime_readback",
            "instance_id": SOURCE_NODE,
            "message": "Stage 16 local-loopback pairing and metadata sync readback observed.",
            "meta": {"trace_id": trace_id, "authority_expansion": False},
        },
    )

    source_readback = _get(client, f"/federation/instances/get?id={SOURCE_NODE}")
    peer_readback = _get(client, f"/federation/instances/get?id={PEER_NODE}")
    delegation_readback = _get(client, "/federation/delegations/list?status=active&limit=100")
    knowledge_readback = _get(
        client,
        "/federation/shared_knowledge/list?kind=metadata&domain=operations&tags=stage16,selective-sync&limit=100",
    )
    log_readback = _get(client, f"/federation/consensus_logs/list?instance_id={SOURCE_NODE}&limit=100")

    delegations = [_as_dict(item) for item in _as_list(delegation_readback.get("items"))]
    knowledge_items = [_as_dict(item) for item in _as_list(knowledge_readback.get("items"))]
    logs = [_as_dict(item) for item in _as_list(log_readback.get("items"))]

    pairing_observed = (
        _as_dict(source_readback.get("item")).get("id") == SOURCE_NODE
        and _as_dict(peer_readback.get("item")).get("id") == PEER_NODE
        and any(
            item.get("from") == SOURCE_NODE
            and item.get("to") == PEER_NODE
            and item.get("scope") == PAIRING_SCOPE
            and item.get("status") == "active"
            for item in delegations
        )
    )
    selective_sync_observed = any(
        item.get("id") == KNOWLEDGE_ID
        and item.get("kind") == "metadata"
        and item.get("source_instance_id") == SOURCE_NODE
        and _as_dict(item.get("meta")).get("contains_raw_private_data") is False
        and _as_dict(item.get("meta")).get("contains_raw_prompt_body") is False
        and _as_dict(item.get("meta")).get("contains_raw_model_response") is False
        for item in knowledge_items
    )
    trace_observed = any(item.get("kind") == "stage16_local_loopback_runtime_readback" for item in logs)

    receipts: list[dict[str, Any]] = []
    receipt_specs = [
        (
            "live_pairing_flow_observed",
            pairing_observed,
            "local-loopback API readback observed two federation instances plus an active scoped pairing delegation",
        ),
        (
            "live_selective_sync_observed",
            selective_sync_observed and trace_observed,
            "local-loopback API readback observed metadata-only shared knowledge and trace log without raw private data",
        ),
    ]
    for readback_id, observed, evidence in receipt_specs:
        receipts.append(
            _post(
                client,
                "/federation/live-runtime-readback",
                {
                    "request_actor": actor,
                    "reason": f"stage16_local_loopback_runtime_readback:{readback_id}",
                    "readback_id": readback_id,
                    "observed": observed,
                    "proof_kind": "live_runtime_probe",
                    "source_node_id": SOURCE_NODE,
                    "paired_node_id": PEER_NODE,
                    "trace_id": trace_id,
                    "parent_receipt_id": str(delegation.get("id")),
                    "evidence_summary": evidence,
                    "recorded_ts": proof_ts,
                },
            )
        )

    after_readbacks = _get(client, "/federation/live-runtime-readbacks")
    after_review = _get(client, "/federation/completion-review")
    status = _get(client, "/federation/status")
    registry_path = data_root / "federation" / "_registry.json"
    receipt_path = data_root / "logs" / "federation" / "stage16_live_runtime_readbacks.jsonl"

    checks = [
        _check(
            "env_profile_allows_commit_mode",
            "allowed" if commit_receipts else "isolated",
            True,
            os.environ.get("FRANCIS_ENV_PROFILE", "dev") or "dev",
            "commit mode is blocked before Python when profile is production or regulated",
        ),
        _check(
            "pairing_flow_readback",
            "observed" if pairing_observed else "missing_or_unexpected",
            pairing_observed,
            "/federation/instances/get and /federation/delegations/list",
            "local-loopback pairing evidence must be read back through existing federation routes",
        ),
        _check(
            "selective_sync_readback",
            "observed" if selective_sync_observed else "missing_or_unexpected",
            selective_sync_observed,
            "/federation/shared_knowledge/list",
            "local-loopback sync evidence must be metadata-only and read back through existing federation routes",
        ),
        _check(
            "trace_readback",
            "observed" if trace_observed else "missing_or_unexpected",
            trace_observed,
            "/federation/consensus_logs/list",
            "runtime evidence must have an auditable federation trace",
        ),
        _check(
            "completion_evidence_records_only_provable_readbacks",
            str(after_readbacks.get("status")),
            after_readbacks.get("status") == "partial"
            and after_readbacks.get("completion_eligible_readback_count") == 2
            and after_readbacks.get("ready_count") == 2
            and after_readbacks.get("required_count") == 5
            and after_readbacks.get("live_runtime_readback_ready") is False
            and after_readbacks.get("missing_readbacks") == REMAINING_READBACK_IDS,
            "/federation/live-runtime-readbacks",
            "the proof may only advance pairing and selective-sync readbacks",
        ),
        _check(
            "completion_review_remains_blocked",
            str(after_review.get("status")),
            after_review.get("stage16_completion_review_ready") is False
            and after_review.get("ready_to_close") is False
            and after_review.get("next_smallest_truthful_gap") == "stage16_remote_approval_runtime_readback",
            "/federation/completion-review",
            "Stage 16 must remain blocked until remote approval, revocation, and sleep continuity are proven",
        ),
        _check(
            "status_surface_remains_blocked",
            str(status.get("stage16_status")),
            status.get("stage16_completion_review_ready") is False
            and status.get("live_runtime_readback_ready") is False
            and status.get("next_smallest_truthful_gap") == "stage16_remote_approval_runtime_readback",
            "/federation/status",
            "the public Stage 16 status must not claim closure from local-loopback evidence",
        ),
    ]
    ok = all(bool(item["passed"]) for item in checks)

    return (
        0 if ok else 1,
        {
            "ok": ok,
            "kind": "francis.stage16.federation.local_loopback_runtime_proof",
            "status": "proof_passed" if ok else "proof_failed",
            "stage": "Stage 16 / Federation",
            "mode": os.environ.get("FRANCIS_PROOF_MODE", "status"),
            "repo_root": str(repo_root),
            "data_root": str(data_root),
            "commit_receipts": commit_receipts,
            "writes_real_project_data": commit_receipts,
            "writes_registry": True,
            "writes_live_readback_receipts": True,
            "registry_path": str(registry_path),
            "receipt_path": str(receipt_path),
            "actor": actor,
            "trace_id": trace_id,
            "source_node_id": SOURCE_NODE,
            "paired_node_id": PEER_NODE,
            "pairing_scope": PAIRING_SCOPE,
            "knowledge_id": KNOWLEDGE_ID,
            "recorded_readback_ids": PROVABLE_READBACK_IDS,
            "remaining_readback_ids": REMAINING_READBACK_IDS,
            "all_readback_ids": ALL_READBACK_IDS,
            "receipt_ids": [str(item.get("receipt_id")) for item in receipts],
            "before_readback_status": before_readbacks.get("status"),
            "before_completion_review_ready": before_review.get("stage16_completion_review_ready"),
            "readback_summary_status": after_readbacks.get("status"),
            "receipt_ready_count": after_readbacks.get("receipt_ready_count"),
            "ready_count": after_readbacks.get("ready_count"),
            "completion_eligible_readback_count": after_readbacks.get("completion_eligible_readback_count"),
            "required_count": after_readbacks.get("required_count"),
            "missing_readbacks": after_readbacks.get("missing_readbacks"),
            "live_runtime_readback_ready": after_readbacks.get("live_runtime_readback_ready"),
            "completion_review_ready": after_review.get("stage16_completion_review_ready"),
            "completion_status": after_review.get("status"),
            "ready_to_close": after_review.get("ready_to_close"),
            "governance": {
                "local_loopback_only": True,
                "requires_federation_write_scope": True,
                "commit_mode_requires_dev_or_workstation_profile": True,
                "does_not_mark_stage16_closed": True,
                "does_not_execute_remote_approval": True,
                "does_not_execute_revocation": True,
                "does_not_probe_sleep_resume": True,
                "contains_raw_private_data": False,
                "contains_raw_prompt_body": False,
                "contains_raw_model_response": False,
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
            "recommended_next_slice": "collect_remote_approval_runtime_readback",
            "recommended_proof_script": "remote federation approval/revocation/sleep-continuity proof required",
            "next_smallest_truthful_gap": "stage16_remote_approval_runtime_readback"
            if ok
            else "stage16_live_federation_runtime_readback",
        },
    )


try:
    code, payload = _run()
except Exception as exc:
    code = 1
    payload = {
        "ok": False,
        "kind": "francis.stage16.federation.local_loopback_runtime_proof",
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
  if ($CommitReceipts) {
    $env:FRANCIS_API_ACTOR_SCOPES = '{"codex.builder":["federation.write"]}'
    $env:FRANCIS_STAGE16_COMMIT_RECEIPTS = '1'
  } else {
    $env:FRANCIS_API_ACTOR_SCOPES = '{"test.federation.write":["federation.write"]}'
    $env:FRANCIS_STAGE16_COMMIT_RECEIPTS = '0'
  }
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
