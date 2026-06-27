"""Grounding tests: Francis1's local-model prompt carries live Francis body state.

These cover the embodiment fix that injects real readbacks (body-map posture, the
next open ORB roadmap gap + artifact, and capability-grant status) into the Ollama
participant's prompt, so Francis1 answers from live state instead of re-asserting
identity. Read-only; no capability authority is granted by any of this.
"""

from __future__ import annotations

from francis.developer_bridge.ollama_participant import (
    _francis_grounding_prompt_lines,
    _ollama_telemetry_context,
)


def test_francis_grounding_prompt_lines_are_bounded_strings() -> None:
    lines = _francis_grounding_prompt_lines()
    assert isinstance(lines, list)
    for line in lines:
        assert isinstance(line, str)
        assert line.strip() == line
        assert line


def test_francis_grounding_includes_self_identity_line() -> None:
    # Grounding now flows from the consolidated self-model: the first line names
    # who Francis is (the seat), proving the self-model readback is reached.
    lines = _francis_grounding_prompt_lines()
    assert any(line.startswith("Self:") for line in lines)


def test_ollama_prompt_lines_inject_self_model_grounding() -> None:
    context = _ollama_telemetry_context("Francis1 turn: name your current gap and artifact")
    prompt_lines = context.get("prompt_lines")
    assert isinstance(prompt_lines, list)
    # The self-model (identity / posture / current need) reaches the model prompt,
    # not just the static contract lines.
    assert any(
        line.startswith("Self:") or line.startswith("Posture:") or line.startswith("Current need:")
        for line in prompt_lines
    )


def test_grounding_is_injected_after_the_context_contract() -> None:
    from francis.developer_bridge.collaboration_contract import CONTEXT_CONTRACT_PROMPT_LINES

    context = _ollama_telemetry_context("Francis1 turn: name your current gap and artifact")
    prompt_lines = context.get("prompt_lines")
    assert isinstance(prompt_lines, list)
    # Governance contract leads; live grounding follows it (and stays within the cap).
    contract = list(CONTEXT_CONTRACT_PROMPT_LINES)
    assert prompt_lines[: len(contract)] == contract
