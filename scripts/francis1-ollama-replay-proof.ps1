param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$Root = '',

  [ValidateRange(30, 300)]
  [int]$TimeoutSeconds = 180,

  [switch]$SkipLiveStatus
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = if ([string]::IsNullOrWhiteSpace($Root)) {
  (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
} else {
  (Resolve-Path $Root).Path
}

& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
  $Python = (Get-Command python -ErrorAction Stop).Source
}

$ProofRoot = Join-Path $RepoRoot 'data\logs\operations\francis1_ollama_replay_proof'
New-Item -ItemType Directory -Force -Path $ProofRoot | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$ProofPath = Join-Path $ProofRoot ("francis1_ollama_replay_proof_{0}.json" -f $Stamp)

$env:FRANCIS_ROOT = $RepoRoot
$env:FRANCIS_LLM_REQUEST_TIMEOUT_S = [string]$TimeoutSeconds
$env:FRANCIS1_REPLAY_PROOF_PATH = $ProofPath
$env:FRANCIS1_REPLAY_SKIP_LIVE_STATUS = if ($SkipLiveStatus) { '1' } else { '0' }
if ([string]::IsNullOrWhiteSpace($env:FRANCIS_LLM_READABLE_FALLBACK_MODELS)) {
  $env:FRANCIS_LLM_READABLE_FALLBACK_MODELS = 'llama3.2:3b'
}

$PythonSource = @'
from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from francis.developer_bridge import ollama_participant
from francis.developer_bridge.collaboration import (
    read_collaboration_transcript,
    submit_collaboration_prompt,
)

GARBAGE_REPLY = (
    "/.)>,|-,#7%D11155%6.+2+)}+{;%B%3FS<+G;H,FHH'H:#8-)C74'12,55* "
    "<G3!4%22!B&GD9A!\"$+C;H,!FBH*H:#8-#)C74'12,55*<G3!4%22!B&GD9A!\"$+5!"
    "GCD728$-D$#>C7*4/=CFBA3C9*"
)
GARBAGE_MARKER = "/.)>,|-,#7%D11155"


def _trace_value(result: dict[str, Any], section: str, key: str) -> str:
    trace = result.get("execution_trace")
    if not isinstance(trace, dict):
        return ""
    value = trace.get(section)
    if not isinstance(value, dict):
        return ""
    return str(value.get(key) or "")


def _reply_is_readable(reply: str) -> bool:
    if not reply:
        return False
    quality = ollama_participant._reply_quality_metrics(reply)
    return not ollama_participant._reply_is_unreadable(reply, quality=quality)


def _live_status_proof() -> dict[str, Any]:
    if os.getenv("FRANCIS1_REPLAY_SKIP_LIVE_STATUS") == "1":
        return {
            "status": "skipped",
            "skip_reason": "SkipLiveStatus specified",
            "readable_reply_observed": False,
        }
    source = submit_collaboration_prompt(
        source_agent="operator",
        target_agent="ollama",
        objective="Milestone 4 live Francis1 readable status replay proof",
        prompt=(
            "Francis1 status check for Orb embodiment voice lane. Reply in one short plain-English paragraph "
            "with your current operational status and one remaining blocker. Do not use symbol salad, code, "
            "or protocol text."
        ),
        context=(
            "milestone=orb_embodiment_voice_replay; live_ollama_after_doctor=true; "
            "readability_repair_allowed_same_provider=true; no_execution_authority=true; "
            "no_mutation_authority=true; no_memory_write_authority=true"
        ),
    )
    result = ollama_participant.respond_once(source_agent="operator", cooldown_seconds=0)
    transcript = read_collaboration_transcript(source_agent="ollama", target_agent="operator", limit=8)
    response = next(
        (item for item in transcript.get("items", []) if item.get("id") == result.get("response_prompt_id")),
        {},
    )
    reply = str(response.get("prompt") or "")
    context = str(response.get("context") or "")
    return {
        "status": "passed" if result.get("status") == "responded" and _reply_is_readable(reply) else "blocked",
        "source_prompt_id": source.get("prompt_id"),
        "response_prompt_id": result.get("response_prompt_id"),
        "result_status": result.get("status"),
        "model_response_observed": bool(result.get("model_response_observed")),
        "output_guard_status": _trace_value(result, "output_guard", "status"),
        "readability_repair_status": _trace_value(result, "readability_repair", "status"),
        "fallback_model_used": _trace_value(result, "readability_repair", "fallback_model_used"),
        "readable_reply_observed": _reply_is_readable(reply),
        "reply_length": len(reply),
        "reply_preview": reply[:700],
        "context_preview": context[:900],
        "raw_unreadable_output_stored": False,
    }


def _forced_garbage_proof() -> dict[str, Any]:
    previous_data_dir = os.environ.get("FRANCIS_DATA_DIR")
    original_generate = ollama_participant.generate
    with tempfile.TemporaryDirectory(prefix="francis1-garbage-proof-") as temp_dir:
        os.environ["FRANCIS_DATA_DIR"] = str(Path(temp_dir) / "data")

        def fake_generate(_prompt: str, **_kwargs: Any) -> str:
            return GARBAGE_REPLY

        ollama_participant.generate = fake_generate
        try:
            source = submit_collaboration_prompt(
                source_agent="operator",
                target_agent="ollama",
                objective="Milestone 4 forced garbage injection proof",
                prompt="can you update me on your current status",
                context="forced_garbage_injection=true; no_execution_authority=true",
            )
            result = ollama_participant.respond_once(source_agent="operator", cooldown_seconds=0)
            transcript = read_collaboration_transcript(source_agent="ollama", target_agent="operator", limit=5)
            response = next(
                (item for item in transcript.get("items", []) if item.get("id") == result.get("response_prompt_id")),
                {},
            )
            reply = str(response.get("prompt") or "")
            context = str(response.get("context") or "")
        finally:
            ollama_participant.generate = original_generate
            if previous_data_dir is None:
                os.environ.pop("FRANCIS_DATA_DIR", None)
            else:
                os.environ["FRANCIS_DATA_DIR"] = previous_data_dir

    output_guard_status = _trace_value(result, "output_guard", "status")
    raw_garbage_leaked = GARBAGE_MARKER in reply or GARBAGE_MARKER in context
    return {
        "status": "passed" if output_guard_status == "unreadable_rewritten" and not raw_garbage_leaked else "blocked",
        "source_prompt_id": source.get("prompt_id"),
        "response_prompt_id": result.get("response_prompt_id"),
        "result_status": result.get("status"),
        "model_response_observed": bool(result.get("model_response_observed")),
        "output_guard_status": output_guard_status,
        "readability_repair_status": _trace_value(result, "readability_repair", "status"),
        "fallback_rewritten_observed": output_guard_status == "unreadable_rewritten",
        "raw_garbage_leaked": raw_garbage_leaked,
        "raw_unreadable_output_stored": False,
        "reply_preview": reply[:500],
    }


live_status = _live_status_proof()
forced_garbage = _forced_garbage_proof()
live_ok = live_status.get("status") == "passed" or live_status.get("status") == "skipped"
forced_ok = forced_garbage.get("status") == "passed"
proof = {
    "kind": "francis.developer_bridge.francis1_ollama_replay_proof",
    "mode": "Status",
    "created_at": datetime.now(UTC).isoformat(),
    "proof_path": os.getenv("FRANCIS1_REPLAY_PROOF_PATH", ""),
    "status": "passed" if live_ok and forced_ok else "blocked",
    "live_status": live_status,
    "forced_garbage": forced_garbage,
    "governance": {
        "provider_lane": "ollama",
        "same_provider_fallback_only": True,
        "stores_raw_unreadable_output": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_memory_write_authority": False,
    },
}
print(json.dumps(proof, indent=2, ensure_ascii=False, sort_keys=True))
raise SystemExit(0 if proof["status"] == "passed" else 2)
'@

$OutputText = $PythonSource | & $Python -
$ExitCode = $LASTEXITCODE
if ([string]::IsNullOrWhiteSpace($OutputText)) {
  throw 'Francis1 replay proof produced no JSON output.'
}
$OutputText | Set-Content -LiteralPath $ProofPath -Encoding UTF8
$OutputText
if ($ExitCode -ne 0) {
  exit $ExitCode
}
