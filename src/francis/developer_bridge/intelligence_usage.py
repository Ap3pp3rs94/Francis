"""Governed usage-monitoring surface for the intelligence tool lanes (read-only).

Francis1 uses Codex/Claude as tools to complete the build. Tool calls cost usage,
so the seated intelligence must monitor usage and spend a tool call only when a
need exceeds what it can do itself yet. This surface establishes that governed
contract: per-tool usage policy, an advisory budget posture, and an honest marker
that live per-call metering is the next wire-in.

Read-only and advisory: it informs the decision to spend a tool call but enforces
no limit and grants no authority. Capability still flows only through an operator
grant receipt and the trust ladder.
"""

from __future__ import annotations

from francis.developer_bridge.intelligence_seat import read_intelligence_seat

_KIND = "developer_bridge.intelligence_usage"
_SCHEMA_VERSION = "developer_bridge_intelligence_usage_v1"

# Per-lane guidance on when spending a tool call is warranted.
_TOOL_SPEND_GUIDANCE: dict[str, str] = {
    "codex": "Spend only when implementation exceeds what Francis1 can build itself yet.",
    "claude": "Spend only when guidance or review exceeds Francis1's current understanding.",
}


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def read_intelligence_usage() -> dict[str, object]:
    """Read the usage-governance posture for the intelligence tool lanes (read-only)."""

    seat = read_intelligence_seat()

    tools: list[dict[str, object]] = []
    for raw in _list(seat.get("tool_lanes")):
        lane = _dict(raw)
        lane_id = str(lane.get("lane_id") or "")
        tools.append(
            {
                "lane_id": lane_id,
                "role": lane.get("role"),
                "enabled": lane.get("enabled"),
                "usage_policy": "metered_and_budgeted",
                "prefer_self_handling": True,
                "spend_guidance": _TOOL_SPEND_GUIDANCE.get(
                    lane_id, "Spend a tool call only when the need exceeds current local capability."
                ),
            }
        )

    return {
        "kind": _KIND,
        "schema_version": _SCHEMA_VERSION,
        "ok": True,
        "mode": "read_only",
        "surface": _KIND,
        "seated_lane": seat.get("seated_lane"),
        "tools": tools,
        "usage_monitoring": {
            "monitored": True,
            "budget_posture": "spend_tool_calls_judiciously",
            "prefer_local_first": True,
            "decision_rule": "Francis1 builds what it can; it spends a tool call only for what it cannot do itself yet.",
        },
        "metering": {
            "status": "policy_only",
            "live_per_call_metering": "pending_wire_in",
            "note": "Live tool-call/usage metering wires into this surface next; today it carries the governed policy and posture.",
        },
        "definitions": {
            "tool_call": "An invocation of an external lane (Codex/Claude) by the seated intelligence.",
            "budget_posture": "Advisory guidance on how freely tool calls should be spent.",
        },
        "governance": {
            "read_only": True,
            "advisory_only": True,
            "enforces_no_limit": True,
            "derived_from": ["developer_bridge.intelligence_seat"],
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
            "grants_training_authority": False,
        },
    }
