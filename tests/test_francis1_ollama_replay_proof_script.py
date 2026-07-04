from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "francis1-ollama-replay-proof.ps1"


def _script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_francis1_ollama_replay_proof_runs_live_status_and_forced_garbage_paths() -> None:
    script = _script_text()

    assert "francis1_ollama_replay_proof" in script
    assert "Milestone 4 live Francis1 readable status replay proof" in script
    assert "Milestone 4 forced garbage injection proof" in script
    assert "readability_repair_allowed_same_provider=true" in script
    assert "forced_garbage_injection=true" in script
    assert "fallback_rewritten_observed" in script
    assert "raw_garbage_leaked" in script
    assert "unreadable_rewritten" in script
    assert "FRANCIS_LLM_READABLE_FALLBACK_MODELS = 'llama3.2:3b'" in script


def test_francis1_ollama_replay_proof_is_bounded_and_non_authorizing() -> None:
    script = _script_text()

    assert "[ValidateRange(30, 300)]" in script
    assert "$env:FRANCIS_LLM_REQUEST_TIMEOUT_S = [string]$TimeoutSeconds" in script
    assert "same_provider_fallback_only" in script
    assert "stores_raw_unreadable_output" in script
    assert "raw_unreadable_output_stored" in script
    assert "no_execution_authority=true" in script
    assert "no_mutation_authority=true" in script
    assert "no_memory_write_authority=true" in script
    assert "grants_execution_authority" in script
    assert "grants_mutation_authority" in script
    assert "grants_memory_write_authority" in script
