from __future__ import annotations

from pathlib import Path

from francis.developer_bridge.mcp_server import create_mcp_server
from francis.developer_bridge.tool_dispatch import prepare_tool_dispatch, read_tool_dispatch

_AUTHORITY_FLAGS = (
    "grants_execution_authority",
    "grants_mutation_authority",
    "grants_approval_authority",
    "grants_memory_write_authority",
    "grants_training_authority",
)


def test_tool_dispatch_contract_is_read_only_and_operator_gated(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))

    contract = read_tool_dispatch()

    assert contract["ok"] is True
    assert contract["mode"] == "read_only"
    assert contract["can_prepare_dispatch_to_both_at_once"] is True
    assert contract["autonomous_send_supported"] is False
    assert contract["send_requires_operator"] is True
    assert contract["tool_targets"] == ["codex", "claude"]
    governance = contract["governance"]
    assert governance["read_only"] is True
    assert governance["prepare_is_propose_level"] is True
    assert governance["send_is_execution_level"] is True
    assert governance["operator_at_the_gate_for_send"] is True
    for flag in _AUTHORITY_FLAGS:
        assert governance[flag] is False


def test_prepare_tool_dispatch_creates_unsent_codex_and_claude_drafts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))

    draft = prepare_tool_dispatch(
        "Review the current Francis self-model and name the next gap.",
        objective="review self-model",
    )

    assert draft["ok"] is True
    assert draft["mode"] == "prepared_not_sent"
    assert draft["sent"] is False
    assert draft["send_requires_operator"] is True
    assert draft["targets"] == ["codex", "claude"]
    assert draft["dispatches_to_both_at_once"] is True
    drafts = draft["drafts"]
    assert isinstance(drafts, list)
    assert {item["target_agent"] for item in drafts} == {"codex", "claude"}
    assert all(item["source_agent"] == "ollama" for item in drafts)
    assert all(item["submit_with"] == "developer_bridge.collaboration.submit_collaboration_prompt" for item in drafts)
    assert all("operator review" in item["context"] for item in drafts)
    assert not (tmp_path / "data" / "integrations" / "developer_bridge" / "collaboration_prompts").exists()
    for flag in _AUTHORITY_FLAGS:
        assert draft["governance"][flag] is False


def test_prepare_tool_dispatch_filters_unknown_targets(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))

    draft = prepare_tool_dispatch("One lane only", targets=("claude", "shell", "codex"))

    assert draft["targets"] == ["claude", "codex"]
    assert draft["dispatches_to_both_at_once"] is True
    assert all(item["target_agent"] in {"codex", "claude"} for item in draft["drafts"])


def test_developer_bridge_mcp_registers_tool_dispatch_tools() -> None:
    server = create_mcp_server()

    names = set(server._tool_manager._tools)

    assert "tool_dispatch_tool" in names
    assert "prepare_tool_dispatch_tool" in names
