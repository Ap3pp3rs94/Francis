"""Tests for the governed operator-intelligence seat readback.

Covers the shared-intelligence model the operator asked for: Francis1 holds the
seat and uses Codex/Claude as tools, Francis1 stays registered even when Ollama is
toggled off, an external lane can hold the seat as a governed fallback, and reading
or holding the seat (or being used as a tool) grants no capability or execution
authority.
"""

from __future__ import annotations

import francis.developer_bridge.intelligence_seat as seat_mod
from francis.developer_bridge.intelligence_seat import (
    known_intelligence_lanes,
    read_intelligence_seat,
)

_AUTHORITY_FLAGS = (
    "grants_execution_authority",
    "grants_mutation_authority",
    "grants_approval_authority",
    "grants_memory_write_authority",
    "grants_training_authority",
)


def test_known_intelligence_lanes() -> None:
    assert known_intelligence_lanes() == ("francis1_local", "codex", "claude")


def test_seat_lane_is_francis1_tools_are_external() -> None:
    seat = read_intelligence_seat()
    assert seat["ok"] is True
    assert seat["mode"] == "read_only"

    assert seat["seat_lane"]["lane_id"] == "francis1_local"
    assert seat["seat_lane"]["role"] == "embodied_operator_intelligence"
    assert seat["seat_lane"]["lane_kind"] == "seat"

    tool_ids = {tool["lane_id"]: tool["role"] for tool in seat["tool_lanes"]}
    assert tool_ids == {"codex": "implementation_toolbelt", "claude": "guidance_tool"}
    assert all(tool["lane_kind"] == "tool" for tool in seat["tool_lanes"])

    assert seat["seated_intelligence_uses_tools"] is True
    assert seat["shared_substrate"]["maintains_one_shared_experience"] is True


def test_seat_grants_no_authority() -> None:
    seat = read_intelligence_seat()
    for lane in seat["lanes"]:
        assert lane["registered"] is True
        assert lane["capability_granted"] is False
        assert lane["capability_requires_grant_receipt"] is True
        assert lane["grants_execution_authority"] is False

    gov = seat["governance"]
    assert gov["read_only"] is True
    assert gov["seat_selection"] == "operator_gated"
    assert gov["default_seat"] == "francis1_local"
    assert gov["occupying_seat_grants_no_capability"] is True
    assert gov["tools_grant_no_capability"] is True
    for flag in _AUTHORITY_FLAGS:
        assert gov[flag] is False


def test_seat_defaults_to_local_when_ollama_enabled(monkeypatch) -> None:
    monkeypatch.setattr(seat_mod, "collaboration_agent_enabled", lambda agent: True)
    seat = read_intelligence_seat()
    assert seat["local_lane_enabled"] is True
    assert seat["local_lane_toggled_off_but_retained"] is False
    assert seat["seated_lane"] == "francis1_local"
    assert seat["seat_is_external_fallback"] is False


def test_seat_falls_back_to_external_when_local_toggled_off(monkeypatch) -> None:
    # Ollama (local seat) toggled off, external tool lanes still enabled.
    monkeypatch.setattr(seat_mod, "collaboration_agent_enabled", lambda agent: agent != "ollama")
    seat = read_intelligence_seat()
    assert seat["local_lane_enabled"] is False
    # Toggled off but NOT removed -- the lane stays registered.
    assert seat["local_lane_toggled_off_but_retained"] is True
    assert any(lane["lane_id"] == "francis1_local" and lane["registered"] for lane in seat["lanes"])
    # An external lane now holds the seat, marked as a fallback.
    assert seat["seated_lane"] in {"codex", "claude"}
    assert seat["seat_is_external_fallback"] is True


def test_seat_is_none_when_all_lanes_off(monkeypatch) -> None:
    monkeypatch.setattr(seat_mod, "collaboration_agent_enabled", lambda agent: False)
    seat = read_intelligence_seat()
    assert seat["seated_lane"] == "none"
    assert seat["seat_is_external_fallback"] is False
