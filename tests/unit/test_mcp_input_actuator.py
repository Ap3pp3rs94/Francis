from __future__ import annotations

from pathlib import Path

from francis.mcp_gateway.tools import list_tools, run_tool


def test_mcp_exposes_governed_input_tools(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path))
    names = {tool["name"] for tool in list_tools()}

    assert "francis.input.status" in names
    assert "francis.input.propose" in names
    assert "francis.input.execute_approved" in names
    assert "francis.input.receipts" in names


def test_mcp_input_status_does_not_grant_raw_input(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path))
    result = run_tool("francis.input.status", {})

    assert result["ok"] is True
    assert result["governance"]["raw_shell"] is False
    assert result["data"]["governance"]["raw_mcp_input_authority"] is False


def test_mcp_input_execute_refuses_without_approval(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path))
    proposal = run_tool(
        "francis.input.propose",
        {
            "actor": "test",
            "objective": "move cursor",
            "kind": "mouse.move",
            "payload": {"x": 1, "y": 2},
        },
    )

    denied = run_tool(
        "francis.input.execute_approved",
        {
            "proposal_id": proposal["data"]["data"]["proposal_id"],
            "approval_phrase": "no",
        },
    )

    assert denied["ok"] is False
    assert denied["status"] == "approval_required"
    assert denied["governance"]["raw_shell"] is False
