"""Governed tool-dispatch surface (read-only readback + draft-only prepare).

Francis1 uses Codex and Claude as tools. This surface lets the seated intelligence
PREPARE a single task for both tool lanes at once and read the dispatch contract.

It stops exactly where Francis's governance draws the line. Preparing a dispatch is
a propose-level action. Actually SENDING it as the operator is an execution-level
action, and the low-risk capability-grant lane does not permit it -- the allowed
grant modes are observe / read / request / propose_plan only (see
``capability_grants.allowed_capability_access_modes``). So a prepared dispatch is
returned for the operator (or a deliberate, separate higher-authority mechanism) to
send: the operator stays at the gate, and the receiving apps act under their own
governance. Nothing here is sent, executed, or granted authority.
"""

from __future__ import annotations

from francis.developer_bridge.intelligence_seat import read_intelligence_seat

_KIND = "developer_bridge.tool_dispatch"
_SCHEMA_VERSION = "developer_bridge_tool_dispatch_v1"
_RELAY_CHANNEL = "developer_bridge.collaboration_prompt_relay"
_SOURCE_AGENT = "ollama"  # Francis1's provider lane on the relay
_DEFAULT_TARGETS = ("codex", "claude")
_MAX_TASK_CHARS = 8000
_MAX_OBJECTIVE_CHARS = 200


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _tool_target_ids(seat: dict[str, object]) -> list[str]:
    return [str(_dict(tool).get("lane_id") or "") for tool in _list(seat.get("tool_lanes"))]


def read_tool_dispatch() -> dict[str, object]:
    """Read the governed tool-dispatch contract without sending or granting anything."""

    seat = read_intelligence_seat()
    return {
        "kind": _KIND,
        "schema_version": _SCHEMA_VERSION,
        "ok": True,
        "mode": "read_only",
        "surface": _KIND,
        "seated_lane": seat.get("seated_lane"),
        "source_agent": _SOURCE_AGENT,
        "tool_targets": _tool_target_ids(seat),
        "channel": _RELAY_CHANNEL,
        "can_prepare_dispatch_to_both_at_once": True,
        "autonomous_send_supported": False,
        "send_requires_operator": True,
        "usage": {
            "prefer_local_first": True,
            "spend_guidance": "Draft a dispatch only when a need exceeds local capability; the operator sends it.",
        },
        "definitions": {
            "prepare": "Compose the dispatch envelopes for the tool lanes; no send occurs.",
            "send": "Submit a prepared envelope to the operator-visible relay; this is an execution-level action reserved to the operator.",
        },
        "governance": {
            "read_only": True,
            "derived_from": ["developer_bridge.intelligence_seat"],
            "prepare_is_propose_level": True,
            "send_is_execution_level": True,
            "low_risk_grant_lane_permits_send": False,
            "operator_at_the_gate_for_send": True,
            "receiving_apps_act_under_their_own_governance": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
            "grants_training_authority": False,
        },
    }


def prepare_tool_dispatch(
    task: str,
    *,
    targets: tuple[str, ...] | list[str] | None = None,
    objective: str = "",
) -> dict[str, object]:
    """Prepare (NOT send) a dispatch of one task to the tool lanes for operator review/send.

    Returns ready-to-send relay envelopes (one per target) matching the parameters of
    ``collaboration.submit_collaboration_prompt``. This function performs no send and
    has no side effects: the operator submits the envelopes.
    """

    clean_task = str(task or "").strip()[:_MAX_TASK_CHARS]
    clean_objective = (str(objective or "").strip() or "Francis1 tool dispatch")[:_MAX_OBJECTIVE_CHARS]
    requested = tuple(targets) if targets else _DEFAULT_TARGETS
    chosen = [target for target in requested if target in _DEFAULT_TARGETS]

    drafts = [
        {
            "channel": _RELAY_CHANNEL,
            "submit_with": "developer_bridge.collaboration.submit_collaboration_prompt",
            "source_agent": _SOURCE_AGENT,
            "target_agent": target,
            "objective": clean_objective,
            "prompt": clean_task,
            "context": "Drafted by Francis1 (seated intelligence) for operator review; not yet sent.",
        }
        for target in chosen
    ]

    return {
        "kind": "developer_bridge.tool_dispatch_draft",
        "schema_version": _SCHEMA_VERSION,
        "ok": True,
        "mode": "prepared_not_sent",
        "task": clean_task,
        "targets": chosen,
        "dispatches_to_both_at_once": len(chosen) > 1,
        "drafts": drafts,
        "sent": False,
        "send_requires_operator": True,
        "note": (
            "Prepared envelopes only. The operator (or a deliberate higher-authority mechanism) "
            "sends these via submit_collaboration_prompt; this function performs no send."
        ),
        "governance": {
            "performs_send": False,
            "read_only_effect": True,
            "send_is_execution_level": True,
            "operator_at_the_gate_for_send": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
            "grants_training_authority": False,
        },
    }
