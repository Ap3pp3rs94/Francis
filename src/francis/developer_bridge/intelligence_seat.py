"""Governed operator-intelligence seat readback (read-only, grants no authority).

Models Francis's shared-intelligence substrate. Francis1 (the local, Ollama-backed
intelligence) is the embodied operator-intelligence that holds the seat and uses
the external lanes -- Codex (implementation toolbelt) and Claude (guidance) -- as
TOOLS to complete the build. All lanes share the same governed substrate (relay,
body map, capability grants, trust ladder), and that shared substrate is what
maintains one shared experience across the intelligences.

Francis1 stays registered even when Ollama is toggled off; if the local seat is
unavailable an external lane may hold the seat as a governed fallback. Holding the
seat -- or being used as a tool -- grants no capability or execution authority on
its own. Capability flows only through an operator grant receipt and the trust
ladder, with the operator at the gate.

This module is read-only and derived: switching the seat or toggling a lane happens
through the primitives the operator already controls
(``set_collaboration_agent_enabled`` and ``set_francis_capability_grant``).
"""

from __future__ import annotations

from francis.developer_bridge.agents import collaboration_agent_enabled
from francis.developer_bridge.capability_grants import read_francis_capability_grants

_KIND = "developer_bridge.intelligence_seat"
_SCHEMA_VERSION = "developer_bridge_intelligence_seat_v1"

# The embodied local intelligence that holds the seat by default.
_SEAT_LANE: dict[str, object] = {
    "lane_id": "francis1_local",
    "label": "Francis1 (local, Ollama-backed)",
    "role": "embodied_operator_intelligence",
    "agents": ("ollama",),
    "provider_lane": "ollama",
    "identity": "francis1",
}

# External lanes the seated intelligence uses as tools to complete the build.
_TOOL_LANES: tuple[dict[str, object], ...] = (
    {
        "lane_id": "codex",
        "label": "Codex",
        "role": "implementation_toolbelt",
        "agents": ("codex",),
        "provider_lane": "external",
        "identity": "external_guidance_source",
    },
    {
        "lane_id": "claude",
        "label": "Claude",
        "role": "guidance_tool",
        "agents": ("claude",),
        "provider_lane": "external",
        "identity": "external_guidance_source",
    },
)


def known_intelligence_lanes() -> tuple[str, ...]:
    """Return the seat lane id followed by the external tool lane ids."""

    return tuple([str(_SEAT_LANE["lane_id"])] + [str(lane["lane_id"]) for lane in _TOOL_LANES])


def _lane_agents(lane: dict[str, object]) -> tuple[str, ...]:
    agents = lane.get("agents")
    if isinstance(agents, (tuple, list)):
        return tuple(str(agent) for agent in agents)
    return ()


def _lane_enabled(lane: dict[str, object]) -> bool:
    return any(collaboration_agent_enabled(agent) for agent in _lane_agents(lane))


def _active_grant_count() -> int:
    grants = read_francis_capability_grants()
    summary = grants.get("summary") if isinstance(grants, dict) else None
    if isinstance(summary, dict):
        try:
            return int(summary.get("granted_count", 0) or 0)
        except (TypeError, ValueError):
            return 0
    return 0


def _lane_record(lane: dict[str, object], *, lane_kind: str) -> dict[str, object]:
    return {
        "lane_id": lane["lane_id"],
        "label": lane["label"],
        "role": lane["role"],
        "lane_kind": lane_kind,  # "seat" or "tool"
        "provider_lane": lane["provider_lane"],
        "identity": lane["identity"],
        "backing_agents": list(_lane_agents(lane)),
        "enabled": _lane_enabled(lane),
        "registered": True,  # toggling a lane off never removes it
        "capability_granted": False,
        "capability_requires_grant_receipt": True,
        "grants_execution_authority": False,
    }


def read_intelligence_seat() -> dict[str, object]:
    """Read the current operator-intelligence seat without granting any authority."""

    seat_record = _lane_record(_SEAT_LANE, lane_kind="seat")
    tool_records = [_lane_record(lane, lane_kind="tool") for lane in _TOOL_LANES]

    local_enabled = bool(seat_record["enabled"])
    # Francis1 holds the seat by default. If the local seat is toggled off, the
    # first enabled external lane holds it as a governed fallback.
    if local_enabled:
        seated_lane_id = str(_SEAT_LANE["lane_id"])
        seat_is_fallback = False
    else:
        fallback = next((tool for tool in tool_records if tool["enabled"]), None)
        seated_lane_id = str(fallback["lane_id"]) if fallback else "none"
        seat_is_fallback = fallback is not None

    return {
        "kind": _KIND,
        "schema_version": _SCHEMA_VERSION,
        "ok": True,
        "mode": "read_only",
        "surface": _KIND,
        "seat_lane": seat_record,
        "tool_lanes": tool_records,
        "lanes": [seat_record, *tool_records],
        "seated_lane": seated_lane_id,
        "seat_is_external_fallback": seat_is_fallback,
        "seated_intelligence_uses_tools": True,
        "available_tools": [
            {"lane_id": tool["lane_id"], "role": tool["role"], "enabled": tool["enabled"]} for tool in tool_records
        ],
        "local_lane_registered": True,
        "local_lane_enabled": local_enabled,
        "local_lane_toggled_off_but_retained": not local_enabled,
        "active_capability_grant_count": _active_grant_count(),
        "shared_substrate": {
            "maintains_one_shared_experience": True,
            "model": "Francis1 holds the seat and uses Codex/Claude as tools; all lanes share one governed substrate.",
            "shared_surfaces": [
                "developer_bridge.collaboration_prompt_relay",
                "developer_bridge.francis_body_map",
                "developer_bridge.capability_grants",
                "developer_bridge.francis_trust_ladder",
            ],
        },
        "definitions": {
            "seat": "The embodied intelligence acting as Francis's operator-intelligence; Francis1 by default.",
            "tool": "An external lane (Codex implementation toolbelt, Claude guidance) the seated intelligence uses to complete the build.",
            "registered": "A lane stays known to Francis even when toggled off; toggling off does not remove it.",
            "external_fallback": "If the local seat is toggled off, an enabled external lane may hold the seat under operator gating.",
        },
        "governance": {
            "read_only": True,
            "derived_from": [
                "developer_bridge.agents.collaboration_agents",
                "developer_bridge.capability_grants",
            ],
            "seat_selection": "operator_gated",
            "default_seat": "francis1_local",
            "change_seat_requires_operator_decision": True,
            "change_seat_mechanism": [
                "developer_bridge.agents.set_collaboration_agent_enabled",
                "developer_bridge.capability_grants.set_francis_capability_grant",
            ],
            "occupying_seat_grants_no_capability": True,
            "tools_grant_no_capability": True,
            "capability_requires_grant_receipt": True,
            "requires_codex_or_operator_review_before_capability_exposure": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
            "grants_training_authority": False,
        },
    }
