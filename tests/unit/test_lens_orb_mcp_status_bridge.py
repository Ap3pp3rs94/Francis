"""Lens/Orb MCP body-state bridge tests.

These tests assert that the visible body-state bridge remains read-only while
surfacing the verified MCP substrate: health, screen/session, takeover, input,
receipts, and handoff status.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import francis.lens.mcp_status_bridge as bridge
from francis.lens import lens_orb_mcp_status_bridge

pytestmark = pytest.mark.unit


def _is_empty_or_missing(path: Path) -> bool:
    return not path.exists() or not any(path.rglob("*.json"))


def test_lens_orb_mcp_status_bridge_reports_read_only_body_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path / "input"))
    monkeypatch.setenv("FRANCIS_TAKEOVER_SESSION_STATE_DIR", str(tmp_path / "takeover"))
    monkeypatch.setenv("FRANCIS_MCP_GATEWAY_STATE_DIR", str(tmp_path / "mcp"))

    out = lens_orb_mcp_status_bridge(actor="test.lens.orb")

    assert out["ok"] is True
    assert out["kind"] == "francis.lens_orb.mcp_status_bridge"
    assert out["status"] == "ready"
    assert out["resident"] is False
    assert out["embodied_posture"] in {"read_only", "pilot_ready", "takeover_ready"}
    assert out["mcp"]["tool_count"] >= 18
    assert out["mcp"]["tool_count_preserved"] is True
    assert out["mcp"]["missing_required_tools"] == []
    assert out["developer_bridge"]["status"] == "ready"

    governance = out["governance"]
    assert governance["read_only"] is True
    assert governance["resident"] is False
    assert governance["raw_shell"] is False
    assert governance["raw_input"] is False
    assert governance["screenshots"] is False
    assert governance["pixels"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False

    components = out["components"]
    assert components["francis.screen.session"]["safe_readback"] is True
    assert components["francis.takeover.status"]["safe_readback"] is True
    assert components["francis.input.status"]["safe_readback"] is True

    # The bridge must not create takeover or input proposals while reading status.
    assert _is_empty_or_missing(tmp_path / "input" / "proposals")
    assert _is_empty_or_missing(tmp_path / "takeover" / "proposals")


def test_lens_orb_mcp_status_bridge_never_claims_implicit_takeover(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path / "input"))
    monkeypatch.setenv("FRANCIS_TAKEOVER_SESSION_STATE_DIR", str(tmp_path / "takeover"))

    out = lens_orb_mcp_status_bridge(actor="test.lens.orb")
    takeover = out["components"]["francis.takeover.status"]["data"]

    assert takeover["control_transfer_active"] is False
    assert takeover["mode"] == "read_only"
    assert out["embodied_posture"] != "takeover_active"


def test_lens_orb_mcp_status_bridge_degrades_when_required_mcp_tool_missing(monkeypatch) -> None:
    monkeypatch.setattr(bridge, "_mcp_list_tools", lambda: [])

    out = bridge.lens_orb_mcp_status_bridge(actor="test.lens.orb")

    assert out["ok"] is False
    assert out["status"] == "degraded"
    assert out["embodied_posture"] == "degraded"
    assert "mcp_required_tools_missing" in out["blockers"]
    assert "mcp_tool_count_below_expected_minimum" in out["blockers"]
    assert out["mcp"]["tool_count"] == 0


def test_lens_orb_mcp_status_bridge_does_not_invoke_mutating_tools(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_tools() -> list[dict[str, Any]]:
        return [
            {"name": "francis.health", "read_only": True, "requires_approval": False},
            {"name": "francis.repo.status", "read_only": True, "requires_approval": False},
            {"name": "francis.screen.status", "read_only": True, "requires_approval": False},
            {"name": "francis.screen.session", "read_only": True, "requires_approval": False},
            {"name": "francis.takeover.status", "read_only": True, "requires_approval": False},
            {"name": "francis.input.status", "read_only": True, "requires_approval": False},
            {"name": "francis.input.propose", "read_only": False, "requires_approval": True},
            {"name": "francis.takeover.start_approved", "read_only": False, "requires_approval": True},
        ]

    def fake_run(tool: str, args: dict[str, Any]) -> dict[str, Any]:
        calls.append((tool, args))
        return {
            "ok": True,
            "status": "ready",
            "tool": tool,
            "data": {},
            "governance": {
                "read_only": True,
                "raw_shell": False,
                "raw_input": False,
                "screenshots": False,
                "pixels": False,
                "authority": "readback",
            },
        }

    monkeypatch.setattr(bridge, "_mcp_list_tools", fake_tools)
    monkeypatch.setattr(bridge, "_mcp_run_tool", fake_run)

    bridge.lens_orb_mcp_status_bridge(actor="test.lens.orb")

    invoked = {tool for tool, _args in calls}
    assert "francis.input.propose" not in invoked
    assert "francis.takeover.start_approved" not in invoked
    assert invoked == {
        "francis.health",
        "francis.repo.status",
        "francis.screen.status",
        "francis.screen.session",
        "francis.takeover.status",
        "francis.input.status",
    }
