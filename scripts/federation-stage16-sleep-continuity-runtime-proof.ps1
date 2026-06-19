[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [string]$PreSleepEvidencePath = '',

  [string]$PostResumeEvidencePath = '',

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
    kind = 'francis.stage16.federation.sleep_continuity_runtime_proof'
    status = 'proof_failed'
    mode = $Mode.ToLowerInvariant()
    repo_root = $RepoRoot
    data_root = $DataRoot
    error = $ErrorCode
    evidence_required = $true
    commit_receipts = [bool]$CommitReceipts
    writes_real_project_data = $false
    ready_to_close = $false
    next_smallest_truthful_gap = 'stage16_sleep_continuity_runtime_readback'
  } | ConvertTo-Json -Depth 6
}

function Test-PathInsideRoot {
  param(
    [string]$Path,
    [string]$Root
  )
  $FullPath = [System.IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
  $FullRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
  return (
    $FullPath.Equals($FullRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
    $FullPath.StartsWith(($FullRoot + [System.IO.Path]::DirectorySeparatorChar), [System.StringComparison]::OrdinalIgnoreCase)
  )
}

$PythonPath = Get-PythonPath
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
  Write-ProofFailure -ErrorCode 'python_unavailable' -DataRoot ''
  exit 1
}

$ProjectDataRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot 'data'))
$ProjectEvidenceRoot = [System.IO.Path]::GetFullPath((Join-Path $ProjectDataRoot 'test_runs\federation-stage16-sleep-continuity-evidence'))
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
  $ProofDataRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-stage16-sleep-continuity-runtime-proof\" + [guid]::NewGuid().ToString('N') + "\data")
} else {
  $ProofDataRoot = [System.IO.Path]::GetFullPath($DataDir)
}

if ([string]::IsNullOrWhiteSpace($PreSleepEvidencePath) -or [string]::IsNullOrWhiteSpace($PostResumeEvidencePath)) {
  Write-ProofFailure -ErrorCode 'pre_and_post_sleep_evidence_required' -DataRoot $ProofDataRoot
  exit 1
}

$PreEvidenceFullPath = [System.IO.Path]::GetFullPath($PreSleepEvidencePath)
$PostEvidenceFullPath = [System.IO.Path]::GetFullPath($PostResumeEvidencePath)
if (-not (Test-Path -LiteralPath $PreEvidenceFullPath -PathType Leaf) -or -not (Test-Path -LiteralPath $PostEvidenceFullPath -PathType Leaf)) {
  Write-ProofFailure -ErrorCode 'sleep_evidence_file_missing' -DataRoot $ProofDataRoot
  exit 1
}
if ($CommitReceipts -and (
    -not (Test-PathInsideRoot -Path $PreEvidenceFullPath -Root $ProjectEvidenceRoot) -or
    -not (Test-PathInsideRoot -Path $PostEvidenceFullPath -Root $ProjectEvidenceRoot)
  )) {
  Write-ProofFailure -ErrorCode 'sleep_evidence_path_outside_commit_root' -DataRoot $ProofDataRoot
  exit 1
}

$Source = @'
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

READBACK_ID = "workstation_sleep_continuity_validated"
REQUEST_ACTOR = "stage16.federation.sleep_continuity"
STAGE15_RECEIPT_ID = "swarm_stage15_closure_for_stage16_sleep_continuity_proof"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_text(value: Any) -> str:
    try:
        return str(value or "").strip()
    except Exception:
        return ""


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


def _load_json_file(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError(f"{path} did not contain a JSON object")
    return raw


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
        "delegation_id": "opdel_stage16_sleep_continuity_proof",
        "completion_review_ready": True,
        "stage15_completion_review_ready": True,
        "stage15_closed_by_receipt": True,
        "ready_count": 6,
        "required_count": 6,
        "blockers": [],
        "marks_runtime_stage_state": False,
        "recorded_ts": 1_800_017_100,
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


def _evidence_valid(pre: dict[str, Any], post: dict[str, Any], *, pre_path: Path) -> tuple[bool, list[str]]:
    failures: list[str] = []
    pre_meta = _as_dict(pre.get("governance"))
    post_meta = _as_dict(post.get("governance"))
    if pre.get("evidence_kind") != "stage16_sleep_continuity_pre_sleep":
        failures.append("pre_sleep_kind")
    if post.get("evidence_kind") != "stage16_sleep_continuity_post_resume":
        failures.append("post_resume_kind")
    for field in ("continuity_record_id", "source_node_id", "paired_node_id", "trace_id", "authority_snapshot_id"):
        if not _safe_text(pre.get(field)):
            failures.append(f"pre_{field}")
        if _safe_text(pre.get(field)) != _safe_text(post.get(field)):
            failures.append(f"post_{field}_mismatch")
    if _safe_text(pre.get("freshness_state")) != "fresh" or _safe_text(post.get("freshness_state")) != "fresh":
        failures.append("freshness_state")
    if not _safe_text(post.get("redaction_summary")):
        failures.append("redaction_summary")
    post_pre_sleep_path = _safe_text(post.get("pre_sleep_evidence_path"))
    if not post_pre_sleep_path:
        failures.append("post_pre_sleep_evidence_path")
    else:
        try:
            if Path(post_pre_sleep_path).resolve() != pre_path:
                failures.append("post_pre_sleep_evidence_path_mismatch")
        except Exception:
            failures.append("post_pre_sleep_evidence_path_mismatch")
    pre_ts = int(pre.get("source_recorded_ts") or pre.get("recorded_ts") or 0)
    post_ts = int(post.get("received_ts") or post.get("recorded_ts") or 0)
    if pre_ts <= 0 or post_ts <= pre_ts:
        failures.append("sleep_resume_time_order")
    if post.get("sleep_observed") is not True or post.get("resume_observed") is not True:
        failures.append("sleep_resume_observed")
    if post.get("continuity_available_after_resume") is not True:
        failures.append("continuity_available_after_resume")
    if post.get("revoked_links_present_current_state") is not False:
        failures.append("revoked_links_present_current_state")
    if post.get("stale_state_implies_current_authority") is not False:
        failures.append("stale_state_implies_current_authority")
    for key in ("contains_raw_private_data", "contains_raw_prompt_body", "contains_raw_model_response"):
        if pre_meta.get(key) is not False or post_meta.get(key) is not False:
            failures.append(key)
    return not failures, failures


def _run() -> tuple[int, dict[str, Any]]:
    repo_root = Path(os.environ["FRANCIS_ROOT"]).resolve()
    data_root = Path(os.environ["FRANCIS_DATA_DIR"]).resolve()
    pre_path = Path(os.environ["FRANCIS_STAGE16_PRE_SLEEP_EVIDENCE"]).resolve()
    post_path = Path(os.environ["FRANCIS_STAGE16_POST_RESUME_EVIDENCE"]).resolve()
    commit_receipts = os.environ.get("FRANCIS_STAGE16_COMMIT_RECEIPTS") == "1"
    sys.path.insert(0, str(repo_root / "src"))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    data_root.mkdir(parents=True, exist_ok=True)
    if not commit_receipts:
        _write_stage15_closure_receipt(data_root)

    pre = _load_json_file(pre_path)
    post = _load_json_file(post_path)
    evidence_valid, evidence_failures = _evidence_valid(pre, post, pre_path=pre_path)
    client = TestClient(create_app())
    before_readbacks = _get(client, "/federation/live-runtime-readbacks")
    before_review = _get(client, "/federation/completion-review")

    continuity_record_id = _safe_text(post.get("continuity_record_id"))
    source_node_id = _safe_text(post.get("source_node_id"))
    paired_node_id = _safe_text(post.get("paired_node_id"))
    trace_id = _safe_text(post.get("trace_id")) or f"trace-stage16-sleep-continuity-{int(time.time())}"
    authority_snapshot_id = _safe_text(post.get("authority_snapshot_id"))

    knowledge_ready = False
    trace_ready = False
    receipt: dict[str, Any] = {}
    if evidence_valid:
        _post(
            client,
            "/federation/shared_knowledge/publish",
            {
                "request_actor": REQUEST_ACTOR,
                "id": continuity_record_id,
                "kind": "continuity_summary",
                "title": "Stage 16 workstation sleep continuity readback",
                "source_instance_id": source_node_id,
                "domain": "operations",
                "tags": ["stage16", "sleep-continuity", "workstation-resume"],
                "meta": {
                    "trace_id": trace_id,
                    "paired_node_id": paired_node_id,
                    "source_recorded_ts": int(pre.get("source_recorded_ts") or pre.get("recorded_ts")),
                    "received_ts": int(post.get("received_ts") or post.get("recorded_ts")),
                    "freshness_state": "fresh",
                    "redaction_summary": _safe_text(post.get("redaction_summary")),
                    "authority_snapshot_id": authority_snapshot_id,
                    "revoked_links_present_current_state": False,
                    "stale_state_implies_current_authority": False,
                    "contains_raw_private_data": False,
                    "contains_raw_prompt_body": False,
                    "contains_raw_model_response": False,
                },
            },
        )
        knowledge = _get(
            client,
            "/federation/shared_knowledge/list?kind=continuity_summary&domain=operations&tags=stage16,sleep-continuity&limit=100",
        )
        knowledge_items = [_as_dict(item) for item in _as_list(knowledge.get("items"))]
        knowledge_ready = any(
            item.get("id") == continuity_record_id
            and _as_dict(item.get("meta")).get("freshness_state") == "fresh"
            and _as_dict(item.get("meta")).get("revoked_links_present_current_state") is False
            and _as_dict(item.get("meta")).get("stale_state_implies_current_authority") is False
            for item in knowledge_items
        )

        _post(
            client,
            "/federation/consensus_logs/append",
            {
                "request_actor": REQUEST_ACTOR,
                "id": f"clog-stage16-sleep-continuity-{continuity_record_id}",
                "level": "info",
                "kind": "stage16_sleep_continuity_readback",
                "instance_id": source_node_id,
                "message": "Stage 16 workstation sleep/resume continuity readback observed from explicit evidence.",
                "meta": {
                    "trace_id": trace_id,
                    "continuity_record_id": continuity_record_id,
                    "paired_node_id": paired_node_id,
                    "authority_snapshot_id": authority_snapshot_id,
                    "sleep_observed": True,
                    "resume_observed": True,
                    "contains_raw_private_data": False,
                },
            },
        )
        logs = _get(client, f"/federation/consensus_logs/list?instance_id={source_node_id}&limit=100")
        trace_ready = any(
            _as_dict(item).get("kind") == "stage16_sleep_continuity_readback"
            and _as_dict(_as_dict(item).get("meta")).get("continuity_record_id") == continuity_record_id
            for item in _as_list(logs.get("items"))
        )
        receipt = _post(
            client,
            "/federation/live-runtime-readback",
            {
                "request_actor": REQUEST_ACTOR,
                "reason": "stage16_workstation_sleep_continuity_runtime_readback",
                "readback_id": READBACK_ID,
                "observed": knowledge_ready and trace_ready,
                "proof_kind": "manual_operator_runtime_readback",
                "source_node_id": source_node_id,
                "paired_node_id": paired_node_id,
                "trace_id": trace_id,
                "parent_receipt_id": continuity_record_id,
                "evidence_summary": "explicit pre-sleep and post-resume evidence validated continuity freshness, redaction, authority snapshot, and revoked-link safety",
                "recorded_ts": int(post.get("received_ts") or post.get("recorded_ts") or time.time()),
            },
        )

    after_readbacks = _get(client, "/federation/live-runtime-readbacks")
    after_review = _get(client, "/federation/completion-review")
    status = _get(client, "/federation/status")
    ready_to_close = after_review.get("ready_to_close") is True
    checks = [
        _check(
            "explicit_sleep_evidence_valid",
            "valid" if evidence_valid else "missing_or_invalid",
            evidence_valid,
            f"{pre_path}; {post_path}",
            "sleep continuity cannot be inferred from a timed delay; explicit pre/post sleep evidence is required",
        ),
        _check(
            "continuity_summary_readback",
            "observed" if knowledge_ready else "missing_or_unexpected",
            knowledge_ready,
            "/federation/shared_knowledge/list",
            "continuity evidence must be read back as redacted node-attributed metadata",
        ),
        _check(
            "sleep_continuity_trace_written",
            "observed" if trace_ready else "missing_or_unexpected",
            trace_ready,
            "/federation/consensus_logs/list",
            "sleep continuity must have trace lineage",
        ),
        _check(
            "sleep_continuity_runtime_receipt_written",
            "observed" if receipt.get("readback_ready") is True else "missing_or_unexpected",
            receipt.get("readback_ready") is True and receipt.get("readback_id") == READBACK_ID,
            "/federation/live-runtime-readback",
            "valid sleep continuity evidence must be recorded as completion-eligible manual operator readback",
        ),
    ]
    ok = all(bool(item["passed"]) for item in checks)

    return (
        0 if ok else 1,
        {
            "ok": ok,
            "kind": "francis.stage16.federation.sleep_continuity_runtime_proof",
            "status": "proof_passed" if ok else "proof_failed",
            "stage": "Stage 16 / Federation",
            "mode": os.environ.get("FRANCIS_PROOF_MODE", "status"),
            "repo_root": str(repo_root),
            "data_root": str(data_root),
            "commit_receipts": commit_receipts,
            "writes_real_project_data": commit_receipts,
            "evidence_required": True,
            "evidence_failures": evidence_failures,
            "pre_sleep_evidence_path": str(pre_path),
            "post_resume_evidence_path": str(post_path),
            "actor": REQUEST_ACTOR,
            "continuity_record_id": continuity_record_id,
            "source_node_id": source_node_id,
            "paired_node_id": paired_node_id,
            "authority_snapshot_id": authority_snapshot_id,
            "receipt_id": receipt.get("receipt_id", ""),
            "readback_id": READBACK_ID,
            "trace_id": trace_id,
            "before_ready_count": before_readbacks.get("ready_count"),
            "before_completion_review_ready": before_review.get("stage16_completion_review_ready"),
            "readback_summary_status": after_readbacks.get("status"),
            "ready_count": after_readbacks.get("ready_count"),
            "completion_eligible_readback_count": after_readbacks.get("completion_eligible_readback_count"),
            "required_count": after_readbacks.get("required_count"),
            "missing_readbacks": after_readbacks.get("missing_readbacks"),
            "live_runtime_readback_ready": after_readbacks.get("live_runtime_readback_ready"),
            "completion_review_ready": after_review.get("stage16_completion_review_ready"),
            "completion_status": after_review.get("status"),
            "ready_to_close": after_review.get("ready_to_close"),
            "status_next_smallest_truthful_gap": status.get("next_smallest_truthful_gap"),
            "governance": {
                "requires_explicit_pre_sleep_evidence": True,
                "requires_explicit_post_resume_evidence": True,
                "post_resume_pre_sleep_path_link_required": True,
                "committed_evidence_paths_must_stay_under_project_evidence_root": True,
                "committed_evidence_path_traversal_blocked": True,
                "does_not_infer_sleep_from_delay": True,
                "manual_operator_runtime_readback": True,
                "redacted_continuity_summary_only": True,
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
            "recommended_next_slice": "collect_operator_sleep_resume_evidence"
            if not ok
            else (
                "run_stage16_completion_review_and_operator_stage_closure_decision"
                if ready_to_close
                else "collect_remaining_live_federation_runtime_readbacks"
            ),
            "next_smallest_truthful_gap": "stage16_sleep_continuity_runtime_readback"
            if not ok
            else str(after_review.get("next_smallest_truthful_gap")),
        },
    )


try:
    code, payload = _run()
except Exception as exc:
    code = 1
    payload = {
        "ok": False,
        "kind": "francis.stage16.federation.sleep_continuity_runtime_proof",
        "status": "proof_failed",
        "error": str(exc),
        "error_type": type(exc).__name__,
        "evidence_required": True,
        "ready_to_close": False,
        "next_smallest_truthful_gap": "stage16_sleep_continuity_runtime_readback",
    }

print(json.dumps(payload, indent=2, sort_keys=True))
sys.exit(code)
'@

$PreviousRoot = [string]$env:FRANCIS_ROOT
$PreviousDataDir = [string]$env:FRANCIS_DATA_DIR
$PreviousActorScopes = [string]$env:FRANCIS_API_ACTOR_SCOPES
$PreviousProofMode = [string]$env:FRANCIS_PROOF_MODE
$PreviousCommitReceipts = [string]$env:FRANCIS_STAGE16_COMMIT_RECEIPTS
$PreviousPreEvidence = [string]$env:FRANCIS_STAGE16_PRE_SLEEP_EVIDENCE
$PreviousPostEvidence = [string]$env:FRANCIS_STAGE16_POST_RESUME_EVIDENCE

try {
  $env:FRANCIS_ROOT = $RepoRoot
  $env:FRANCIS_DATA_DIR = $ProofDataRoot
  $env:FRANCIS_API_ACTOR_SCOPES = '{"stage16.federation.sleep_continuity":["federation.write"]}'
  $env:FRANCIS_STAGE16_COMMIT_RECEIPTS = $(if ($CommitReceipts) { '1' } else { '0' })
  $env:FRANCIS_PROOF_MODE = $Mode.ToLowerInvariant()
  $env:FRANCIS_STAGE16_PRE_SLEEP_EVIDENCE = $PreEvidenceFullPath
  $env:FRANCIS_STAGE16_POST_RESUME_EVIDENCE = $PostEvidenceFullPath
  $PreviousNativeErrorActionPreference = $ErrorActionPreference
  try {
    # Windows PowerShell can promote native stderr warnings into terminating
    # errors. The Python exit code remains the proof authority.
    $ErrorActionPreference = 'Continue'
    $Output = $Source | & $PythonPath -
    $ExitCode = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $PreviousNativeErrorActionPreference
  }
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
  if ([string]::IsNullOrWhiteSpace($PreviousPreEvidence)) {
    Remove-Item Env:\FRANCIS_STAGE16_PRE_SLEEP_EVIDENCE -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_STAGE16_PRE_SLEEP_EVIDENCE = $PreviousPreEvidence
  }
  if ([string]::IsNullOrWhiteSpace($PreviousPostEvidence)) {
    Remove-Item Env:\FRANCIS_STAGE16_POST_RESUME_EVIDENCE -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_STAGE16_POST_RESUME_EVIDENCE = $PreviousPostEvidence
  }
}
