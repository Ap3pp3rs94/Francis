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
  $DataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-stage16-live-runtime-readback-proof\" + [guid]::NewGuid().ToString('N') + "\data")
}

$ProofDataRoot = [System.IO.Path]::GetFullPath($DataDir)
$ProjectDataRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot 'data'))
if ($ProofDataRoot.TrimEnd('\') -ieq $ProjectDataRoot.TrimEnd('\')) {
  [ordered]@{
    ok = $false
    kind = 'francis.stage16.federation.live_runtime_readback_proof'
    status = 'proof_failed'
    mode = $Mode.ToLowerInvariant()
    repo_root = $RepoRoot
    data_root = $ProofDataRoot
    error = 'refusing_to_write_project_data_receipts'
    writes_real_project_receipts = $false
    next_smallest_truthful_gap = 'stage16_live_federation_runtime_readback'
  } | ConvertTo-Json -Depth 6
  exit 1
}

$PythonPath = Get-PythonPath
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
  [ordered]@{
    ok = $false
    kind = 'francis.stage16.federation.live_runtime_readback_proof'
    status = 'proof_failed'
    mode = $Mode.ToLowerInvariant()
    repo_root = $RepoRoot
    data_root = $ProofDataRoot
    error = 'python_unavailable'
    writes_real_project_receipts = $false
    next_smallest_truthful_gap = 'stage16_live_federation_runtime_readback'
  } | ConvertTo-Json -Depth 6
  exit 1
}

$Source = @'
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

READBACK_IDS = [
    "live_pairing_flow_observed",
    "live_selective_sync_observed",
    "live_remote_approval_roundtrip_observed",
    "live_revocation_roundtrip_observed",
    "workstation_sleep_continuity_validated",
]

STAGE15_RECEIPT_ID = "swarm_stage15_closure_for_stage16_live_readback_proof"


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
        "delegation_id": "opdel_stage16_live_readback_proof",
        "completion_review_ready": True,
        "stage15_completion_review_ready": True,
        "stage15_closed_by_receipt": True,
        "ready_count": 6,
        "required_count": 6,
        "blockers": [],
        "marks_runtime_stage_state": False,
        "recorded_ts": 1_800_016_000,
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
    sys.path.insert(0, str(repo_root / "src"))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    data_root.mkdir(parents=True, exist_ok=True)
    _write_stage15_closure_receipt(data_root)

    client = TestClient(create_app())
    before_readbacks = _get(client, "/federation/live-runtime-readbacks")
    before_review = _get(client, "/federation/completion-review")

    denied = _post(
        client,
        "/federation/live-runtime-readback",
        {
            "request_actor": "unscoped.federation.writer",
            "readback_id": READBACK_IDS[0],
            "observed": True,
            "proof_kind": "scripted_local_runtime_probe",
            "source_node_id": "stage16-local-workstation",
            "paired_node_id": "stage16-local-loopback-node",
            "trace_id": "trace-stage16-denied",
            "parent_receipt_id": STAGE15_RECEIPT_ID,
            "evidence_summary": "denied receipt must not persist",
        },
    )

    receipts: list[dict[str, Any]] = []
    for index, readback_id in enumerate(READBACK_IDS, start=1):
        receipts.append(
            _post(
                client,
                "/federation/live-runtime-readback",
                {
                    "request_actor": "test.federation.write",
                    "reason": f"prove isolated stage16 receipt path for {readback_id}",
                    "readback_id": readback_id,
                    "observed": True,
                    "proof_kind": "scripted_local_runtime_probe",
                    "source_node_id": "stage16-local-workstation",
                    "paired_node_id": "stage16-local-loopback-node",
                    "trace_id": f"trace-stage16-live-readback-proof-{index}",
                    "parent_receipt_id": STAGE15_RECEIPT_ID,
                    "evidence_summary": f"isolated local-loopback API proof recorded {readback_id}",
                    "recorded_ts": 1_800_016_100 + index,
                },
            )
        )

    after_readbacks = _get(client, "/federation/live-runtime-readbacks")
    after_review = _get(client, "/federation/completion-review")
    status = _get(client, "/federation/status")
    receipt_path = data_root / "logs" / "federation" / "stage16_live_runtime_readbacks.jsonl"
    receipt_lines = receipt_path.read_text(encoding="utf-8").splitlines() if receipt_path.exists() else []

    denied_ok = (
        denied.get("ok") is False
        and denied.get("status") == "denied"
        and denied.get("error") == "api_permission_denied"
    )
    receipt_ready = all(
        item.get("ok") is True
        and item.get("readback_ready") is True
        and item.get("readback_id") == readback_id
        and _as_dict(item.get("governance")).get("permission_scope") == "federation.write"
        and item.get("writes_registry") is False
        and item.get("writes_memory") is False
        and item.get("grants_execution_authority") is False
        and item.get("grants_mutation_authority") is False
        for item, readback_id in zip(receipts, READBACK_IDS)
    )
    after_checks = _as_list(after_readbacks.get("checks"))
    readback_checks_ready = (
        after_readbacks.get("status") == "partial"
        and after_readbacks.get("receipt_ready_count") == len(READBACK_IDS)
        and after_readbacks.get("ready_count") == 0
        and after_readbacks.get("required_count") == len(READBACK_IDS)
        and after_readbacks.get("readback_receipts_ready") is True
        and after_readbacks.get("live_runtime_readback_ready") is False
        and after_readbacks.get("missing_readbacks") == READBACK_IDS
        and {str(item.get("id")) for item in after_checks if isinstance(item, dict)} == set(READBACK_IDS)
        and all(item.get("receipt_ready") is True for item in after_checks if isinstance(item, dict))
        and all(item.get("completion_evidence") is False for item in after_checks if isinstance(item, dict))
    )
    completion_ready = (
        after_review.get("status") == "blocked"
        and after_review.get("contract_readiness_ready") is True
        and after_review.get("live_runtime_readback_ready") is False
        and after_review.get("stage16_completion_review_ready") is False
        and after_review.get("ready_to_close") is False
        and after_review.get("next_smallest_truthful_gap") == "stage16_live_federation_runtime_readback"
    )
    status_ready = (
        status.get("stage16_status") == "stage16_contracts_ready_completion_blocked"
        and status.get("stage16_completion_review_ready") is False
        and status.get("live_runtime_readback_ready") is False
        and status.get("next_smallest_truthful_gap") == "stage16_live_federation_runtime_readback"
    )
    receipt_file_ready = len(receipt_lines) == len(READBACK_IDS)

    checks = [
        _check(
            "isolated_data_root",
            "isolated",
            data_root != repo_root / "data",
            str(data_root),
            "proof must not write the repo's real data/logs receipts",
        ),
        _check(
            "precheck_blocks_without_live_readbacks",
            str(before_review.get("status")),
            before_readbacks.get("status") == "empty"
            and before_review.get("live_runtime_readback_ready") is False
            and before_review.get("stage16_completion_review_ready") is False,
            "/federation/completion-review before receipts",
            "Stage 16 completion must remain blocked before live readback receipts exist",
        ),
        _check(
            "permission_gate_blocks_unscoped_write",
            str(denied.get("status")),
            denied_ok,
            "/federation/live-runtime-readback unscoped actor",
            "unscoped actors must not write federation runtime readback receipts",
        ),
        _check(
            "five_readback_receipts_written",
            "receipts_ready" if receipt_ready else "missing_or_unexpected",
            receipt_ready and len(receipts) == len(READBACK_IDS),
            "/federation/live-runtime-readback",
            "all required Stage 16 live readback IDs must produce ready receipts",
        ),
        _check(
            "receipt_file_readback",
            "jsonl_ready" if receipt_file_ready else "missing_or_unexpected",
            receipt_file_ready,
            str(receipt_path),
            "accepted readbacks must be auditable through the JSONL receipt file",
        ),
        _check(
            "readback_summary_consumes_receipts",
            str(after_readbacks.get("status")),
            readback_checks_ready,
            "/federation/live-runtime-readbacks",
            "the readback summary must consume all five latest valid receipts",
        ),
        _check(
            "completion_review_consumes_receipts",
            str(after_review.get("status")),
            completion_ready,
            "/federation/completion-review",
            "completion review must move to ready inside isolated proof data only",
        ),
        _check(
            "status_surface_reflects_isolated_readiness",
            str(status.get("stage16_status")),
            status_ready,
            "/federation/status",
            "status must reflect receipt-backed Stage 16 readiness in isolated proof data",
        ),
    ]
    ok = all(bool(item["passed"]) for item in checks)

    return (
        0 if ok else 1,
        {
            "ok": ok,
            "kind": "francis.stage16.federation.live_runtime_readback_proof",
            "status": "proof_passed" if ok else "proof_failed",
            "stage": "Stage 16 / Federation",
            "mode": os.environ.get("FRANCIS_PROOF_MODE", "status"),
            "repo_root": str(repo_root),
            "data_root": str(data_root),
            "isolated_data_dir": True,
            "writes_real_project_receipts": False,
            "readback_ids": READBACK_IDS,
            "readback_receipts_recorded": len(receipts),
            "receipt_path": str(receipt_path),
            "receipt_line_count": len(receipt_lines),
            "denied_unscoped_write": denied_ok,
            "before_live_runtime_readback_ready": before_readbacks.get("live_runtime_readback_ready"),
            "before_completion_review_ready": before_review.get("stage16_completion_review_ready"),
            "readback_receipts_ready": after_readbacks.get("readback_receipts_ready"),
            "live_runtime_readback_ready": after_readbacks.get("live_runtime_readback_ready"),
            "completion_eligible_readback_count": after_readbacks.get("completion_eligible_readback_count"),
            "completion_review_ready": after_review.get("stage16_completion_review_ready"),
            "isolated_completion_review_next_smallest_truthful_gap": after_review.get("next_smallest_truthful_gap"),
            "project_stage_closure_changed": False,
            "governance": {
                "isolated_proof": True,
                "readback_receipt_path_only": True,
                "requires_federation_write_scope": True,
                "does_not_execute_pairing": True,
                "does_not_execute_sync": True,
                "does_not_execute_remote_approval": True,
                "does_not_execute_revocation": True,
                "does_not_probe_sleep_resume": True,
                "writes_real_project_receipts": False,
                "writes_registry": False,
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
            "recommended_next_slice": "collect_real_live_federation_runtime_readbacks",
            "recommended_proof_script": "real runtime probe required; this script is isolated receipt-path proof only",
            "next_smallest_truthful_gap": "stage16_live_federation_runtime_readback",
        },
    )


try:
    code, payload = _run()
except Exception as exc:
    code = 1
    payload = {
        "ok": False,
        "kind": "francis.stage16.federation.live_runtime_readback_proof",
        "status": "proof_failed",
        "error": str(exc),
        "error_type": type(exc).__name__,
        "next_smallest_truthful_gap": "stage16_live_federation_runtime_readback",
    }

print(json.dumps(payload, indent=2, sort_keys=True))
sys.exit(code)
'@

$PreviousRoot = [string]$env:FRANCIS_ROOT
$PreviousDataDir = [string]$env:FRANCIS_DATA_DIR
$PreviousActorScopes = [string]$env:FRANCIS_API_ACTOR_SCOPES
$PreviousProofMode = [string]$env:FRANCIS_PROOF_MODE

try {
  $env:FRANCIS_ROOT = $RepoRoot
  $env:FRANCIS_DATA_DIR = $ProofDataRoot
  $env:FRANCIS_API_ACTOR_SCOPES = '{"test.federation.write":["federation.write"]}'
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
}
