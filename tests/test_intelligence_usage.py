"""Tests for the governed usage-monitoring surface.

Francis1 monitors usage and spends a tool call only for what it cannot do itself
yet. This surface carries that governed, advisory policy without enforcing a limit
or granting any authority.
"""

from __future__ import annotations

from francis.developer_bridge.intelligence_usage import read_intelligence_usage

_AUTHORITY_FLAGS = (
    "grants_execution_authority",
    "grants_mutation_authority",
    "grants_approval_authority",
    "grants_memory_write_authority",
    "grants_training_authority",
)


def test_usage_lists_tool_lanes_with_policy() -> None:
    usage = read_intelligence_usage()
    assert usage["ok"] is True
    assert usage["mode"] == "read_only"
    tool_ids = {tool["lane_id"] for tool in usage["tools"]}
    assert tool_ids == {"codex", "claude"}
    for tool in usage["tools"]:
        assert tool["usage_policy"] == "metered_and_budgeted"
        assert tool["prefer_self_handling"] is True
        assert tool["spend_guidance"]


def test_usage_monitoring_posture() -> None:
    usage = read_intelligence_usage()
    monitoring = usage["usage_monitoring"]
    assert monitoring["monitored"] is True
    assert monitoring["prefer_local_first"] is True
    # Live metering is honestly marked as the next wire-in, not faked.
    assert usage["metering"]["status"] == "policy_only"


def test_usage_is_advisory_and_grants_no_authority() -> None:
    gov = read_intelligence_usage()["governance"]
    assert gov["read_only"] is True
    assert gov["advisory_only"] is True
    assert gov["enforces_no_limit"] is True
    for flag in _AUTHORITY_FLAGS:
        assert gov[flag] is False
