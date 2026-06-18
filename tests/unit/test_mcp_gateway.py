from __future__ import annotations

import json
from pathlib import Path

from francis.mcp_gateway.tools import list_tools, run_tool


def test_mcp_gateway_lists_expected_tools(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_MCP_GATEWAY_STATE_DIR", str(tmp_path))
    names = {tool["name"] for tool in list_tools()}

    assert {
        "francis.health",
        "francis.repo.status",
        "francis.git.diff",
        "francis.tests.run_targeted",
        "francis.command.propose",
        "francis.command.execute_approved",
        "francis.receipts.readback",
        "francis.screen.status",
        "francis.screen.session",
        "francis.takeover.status",
        "francis.takeover.propose",
        "francis.takeover.start_approved",
        "francis.takeover.end",
        "francis.input.status",
        "francis.input.propose",
        "francis.input.execute_approved",
        "francis.input.receipts",
        "francis.handoff.audit",
        "francis.chatgpt_voice.contract",
        "francis.chatgpt_voice.ingress",
        "francis.chatgpt_voice.receipts",
    }.issubset(names)


def test_read_only_tools_report_no_raw_shell(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_MCP_GATEWAY_STATE_DIR", str(tmp_path))
    result = run_tool("francis.health", {})

    assert result["ok"] is True
    assert result["governance"]["read_only"] is True
    assert result["governance"]["raw_shell"] is False


def test_screen_session_readback_is_read_only_without_pixels(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_MCP_GATEWAY_STATE_DIR", str(tmp_path / "mcp"))
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path / "input"))

    result = run_tool("francis.screen.session", {})

    assert result["ok"] is True
    assert result["status"] == "ready"
    assert result["governance"]["read_only"] is True
    assert result["governance"]["raw_shell"] is False
    assert result["governance"]["screenshots"] is False
    assert result["governance"]["pixels"] is False
    assert result["data"]["active_window"]["capture"] == "not_performed"
    assert result["data"]["active_window"]["pixels"] is False
    assert result["data"]["active_window"]["screenshot"] is False


def test_takeover_session_proposal_refuses_unapproved_start(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_MCP_GATEWAY_STATE_DIR", str(tmp_path / "mcp"))
    monkeypatch.setenv("FRANCIS_TAKEOVER_SESSION_STATE_DIR", str(tmp_path / "takeover_session"))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))

    proposal = run_tool(
        "francis.takeover.propose",
        {"actor": "test", "reason": "pilot mode test", "mode": "pilot", "duration_sec": 120},
    )

    assert proposal["ok"] is True
    assert proposal["status"] == "approval_required"

    denied = run_tool(
        "francis.takeover.start_approved",
        {"proposal_id": proposal["data"]["proposal_id"], "approval_phrase": "no"},
    )

    assert denied["ok"] is False
    assert denied["status"] == "approval_required"
    assert denied["governance"]["raw_input"] is False
    assert denied["governance"]["raw_shell"] is False


def test_unknown_tool_returns_bounded_error() -> None:
    result = run_tool("francis.nope", {})

    assert result["ok"] is False
    assert result["status"] == "unknown_tool"
    assert result["governance"]["raw_shell"] is False


def test_targeted_tests_refuse_outside_tests_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_MCP_GATEWAY_STATE_DIR", str(tmp_path))
    result = run_tool("francis.tests.run_targeted", {"targets": ["src/francis/__main__.py"]})

    assert result["ok"] is False
    assert result["status"] == "bad_request"
    assert "outside tests" in str(result["error"])


def test_command_propose_requires_allowlisted_kind(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_MCP_GATEWAY_STATE_DIR", str(tmp_path))
    result = run_tool(
        "francis.command.propose",
        {"actor": "test", "objective": "bad raw shell", "kind": "powershell", "targets": []},
    )

    assert result["ok"] is False
    assert result["status"] == "bad_request"
    assert result["governance"]["raw_shell"] is False


def test_execute_approved_refuses_without_manual_phrase(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_MCP_GATEWAY_STATE_DIR", str(tmp_path))
    proposal = run_tool(
        "francis.command.propose",
        {"actor": "test", "objective": "read git status", "kind": "git_status", "targets": []},
    )
    assert proposal["ok"] is True

    proposal_id = proposal["data"]["proposal_id"]
    denied = run_tool(
        "francis.command.execute_approved",
        {"proposal_id": proposal_id, "approval_phrase": "no"},
    )

    assert denied["ok"] is False
    assert denied["status"] == "approval_required"
    assert denied["governance"]["raw_shell"] is False


def test_execute_approved_runs_allowlisted_git_status_and_receipts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_MCP_GATEWAY_STATE_DIR", str(tmp_path))
    proposal = run_tool(
        "francis.command.propose",
        {"actor": "test", "objective": "read git status", "kind": "git_status", "targets": []},
    )
    proposal_id = proposal["data"]["proposal_id"]
    approval_phrase = proposal["data"]["approval_phrase"]

    result = run_tool(
        "francis.command.execute_approved",
        {"proposal_id": proposal_id, "approval_phrase": approval_phrase},
    )

    assert result["ok"] is True
    assert result["status"] == "complete"
    assert result["governance"]["raw_shell"] is False
    assert result["data"]["receipt_id"].startswith("mcp-command-execute-approved-")
    assert Path(result["data"]["receipt_path"]).exists()


def test_receipts_readback_missing_is_truthful(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_MCP_GATEWAY_STATE_DIR", str(tmp_path))
    result = run_tool("francis.receipts.readback", {"receipt_id": "does-not-exist"})

    assert result["ok"] is False
    assert result["status"] == "not_found"
    assert result["governance"]["read_only"] is True


def test_result_is_json_serializable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_MCP_GATEWAY_STATE_DIR", str(tmp_path))
    result = run_tool("francis.repo.status", {})
    json.dumps(result)
