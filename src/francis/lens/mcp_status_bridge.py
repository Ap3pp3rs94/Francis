"""Lens/Orb MCP body-state bridge (read-only).

This is the smallest truthful bridge from the visible Lens/Orb body layer to the
verified MCP substrate. It aggregates safe MCP readbacks into one body-state
projection without claiming residency or granting control authority.
"""

from __future__ import annotations

from typing import Any

from francis.governance.redaction import redact_governed_display_value
from francis.mcp_gateway.tools import list_tools as _mcp_list_tools
from francis.mcp_gateway.tools import run_tool as _mcp_run_tool
from francis.world_state.orb import snapshot as _orb_status_snapshot

EXPECTED_MIN_TOOL_COUNT = 18
LENS_ORB_MCP_STATUS_KIND = "francis.lens_orb.mcp_status_bridge"

_REQUIRED_STATUS_TOOLS = {
    "francis.health",
    "francis.repo.status",
    "francis.screen.status",
    "francis.screen.session",
    "francis.takeover.status",
    "francis.input.status",
}

_OPTIONAL_READBACK_TOOLS = {
    "francis.receipts.readback": {},
    "francis.policy.receipts": {"limit": 5},
    "francis.handoff.audit": {"limit": 5},
}


_KIND_TO_LABEL = {
    "francis.health": "MCP gateway",
    "francis.repo.status": "Repository",
    "francis.screen.status": "Screen readback",
    "francis.screen.session": "Screen/session",
    "francis.takeover.status": "Takeover/session",
    "francis.input.status": "Input actuator",
    "francis.receipts.readback": "MCP receipts",
    "francis.policy.receipts": "Tool policy receipts",
    "francis.handoff.audit": "Takeover/input handoff",
}


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        return str(value).strip()
    except Exception:
        return default


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _redacted(value: dict[str, Any]) -> dict[str, Any]:
    display = redact_governed_display_value(value)
    return display if isinstance(display, dict) else value


def _honesty() -> dict[str, Any]:
    return {
        "bridge": "lens_orb_mcp_status_bridge_v0",
        "read_only": True,
        "resident": False,
        "resident_claim": False,
        "supervision": False,
        "mutates_repo": False,
        "raw_shell": False,
        "raw_input": False,
        "screenshots": False,
        "pixels": False,
        "ocr": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "approval_decision_authority": False,
    }


def _safe_mcp_result(result: dict[str, Any]) -> bool:
    governance = _as_dict(result.get("governance"))
    return (
        bool(governance.get("read_only"))
        and governance.get("raw_shell") is False
        and governance.get("raw_input") is not True
        and governance.get("screenshots") is not True
        and governance.get("pixels") is not True
    )


def _component_from_result(tool: str, result: dict[str, Any] | None) -> dict[str, Any]:
    if result is None:
        return {
            "tool": tool,
            "label": _KIND_TO_LABEL.get(tool, tool),
            "ok": False,
            "status": "missing",
            "safe_readback": False,
            "authority": "none",
            "error": "tool_not_registered",
            "data": {},
        }

    governance = _as_dict(result.get("governance"))
    component = {
        "tool": tool,
        "label": _KIND_TO_LABEL.get(tool, tool),
        "ok": bool(result.get("ok")),
        "status": _safe_str(result.get("status"), "unknown"),
        "safe_readback": _safe_mcp_result(result),
        "authority": _safe_str(governance.get("authority"), "unknown"),
        "error": _safe_str(result.get("error")),
        "data": _as_dict(result.get("data")),
    }
    return _redacted(component)


def _call_readback(tool: str, args: dict[str, Any], available: set[str]) -> dict[str, Any] | None:
    if tool not in available:
        return None
    return _mcp_run_tool(tool, args)


def _latest_receipt_id(receipts_component: dict[str, Any]) -> str:
    data = _as_dict(receipts_component.get("data"))
    receipts = data.get("receipts")
    if isinstance(receipts, list) and receipts:
        return _safe_str(receipts[0])
    return ""


def _developer_bridge_status() -> dict[str, Any]:
    try:
        import francis.developer_bridge.repo_tools as repo_tools  # noqa: F401
    except Exception as exc:  # pragma: no cover - defensive import fallback
        return {
            "ok": False,
            "status": "unavailable",
            "surface": "developer_bridge",
            "error": type(exc).__name__,
            "governance": _honesty(),
        }
    return {
        "ok": True,
        "status": "ready",
        "surface": "developer_bridge",
        "route": "/developer-bridge",
        "governance": _honesty(),
    }


def _orb_semantic_state() -> dict[str, Any]:
    try:
        payload = _orb_status_snapshot()
    except Exception as exc:  # pragma: no cover - defensive readback fallback
        return {
            "ok": False,
            "status": "unavailable",
            "semantic_state": "unknown",
            "source": "francis.world_state.orb",
            "error": type(exc).__name__,
            "read_only": True,
            "private_ui_state": False,
            "visual_change": False,
            "governance": _honesty(),
        }

    state = _as_dict(payload.get("state"))
    semantic = _as_dict(state.get("semantic_operator_state"))
    operator_input = _as_dict(state.get("operator_input"))
    semantic_state = _safe_str(semantic.get("state") or state.get("semantic_state"), "unknown") or "unknown"
    return _redacted(
        {
            "ok": bool(payload.get("ok")) and bool(semantic),
            "status": semantic_state if semantic else "unavailable",
            "semantic_state": semantic_state,
            "source": _safe_str(semantic.get("source"), "francis.world_state.orb"),
            "truth_source": _safe_str(semantic.get("truth_source"), "mission_operation_readback"),
            "render_state": _safe_str(state.get("render_state")),
            "activity_intensity": _as_dict(state.get("activity_intensity")),
            "semantic_operator_state": semantic,
            "operator_input": operator_input,
            "read_only": True,
            "private_ui_state": False,
            "visual_change": False,
            "governance": _honesty(),
        }
    )


def _body_posture(components: dict[str, dict[str, Any]], blockers: list[str]) -> str:
    takeover = components.get("francis.takeover.status", {})
    takeover_data = _as_dict(takeover.get("data"))
    if bool(takeover_data.get("control_transfer_active")):
        return "takeover_active"
    if blockers:
        return "degraded"
    screen_ready = bool(components.get("francis.screen.session", {}).get("ok"))
    takeover_ready = bool(takeover.get("ok"))
    input_ready = bool(components.get("francis.input.status", {}).get("ok"))
    if screen_ready and takeover_ready and input_ready:
        return "takeover_ready"
    if screen_ready and input_ready:
        return "pilot_ready"
    return "read_only"


def _component_badges(components: dict[str, dict[str, Any]], *, tool_count: int) -> list[dict[str, Any]]:
    def status_for(tool: str) -> str:
        return _safe_str(components.get(tool, {}).get("status"), "missing")

    return [
        {
            "label": "MCP tools",
            "value": tool_count,
            "severity": "ok" if tool_count >= EXPECTED_MIN_TOOL_COUNT else "warn",
        },
        {"label": "Screen", "value": status_for("francis.screen.session"), "severity": "ok"},
        {"label": "Takeover", "value": status_for("francis.takeover.status"), "severity": "ok"},
        {"label": "Input", "value": status_for("francis.input.status"), "severity": "ok"},
    ]


def lens_orb_mcp_status_bridge(*, actor: str = "lens-orb", receipt_limit: int = 10) -> dict[str, Any]:
    """Project Lens/Orb body state from safe MCP readbacks.

    The bridge is intentionally read-only. It never proposes or executes input,
    takeover, shell, or repo mutations. It does not claim the Lens/Orb is resident.
    """

    tools = _mcp_list_tools()
    tool_names = {_safe_str(tool.get("name")) for tool in tools if isinstance(tool, dict)}
    missing_required = sorted(_REQUIRED_STATUS_TOOLS - tool_names)
    tool_count = len(tools)

    components: dict[str, dict[str, Any]] = {}
    for tool in sorted(_REQUIRED_STATUS_TOOLS):
        components[tool] = _component_from_result(tool, _call_readback(tool, {}, tool_names))

    optional_components: dict[str, dict[str, Any]] = {}
    for tool, args in sorted(_OPTIONAL_READBACK_TOOLS.items()):
        call_args = dict(args)
        if tool == "francis.receipts.readback":
            call_args["limit"] = max(1, min(int(receipt_limit or 10), 100))
        optional_components[tool] = _component_from_result(tool, _call_readback(tool, call_args, tool_names))

    developer_bridge = _developer_bridge_status()
    blockers: list[str] = []
    if missing_required:
        blockers.append("mcp_required_tools_missing")
    if tool_count < EXPECTED_MIN_TOOL_COUNT:
        blockers.append("mcp_tool_count_below_expected_minimum")
    for tool, component in components.items():
        if not bool(component.get("ok")):
            blockers.append(f"{tool}.not_ready")
        if not bool(component.get("safe_readback")):
            blockers.append(f"{tool}.unsafe_readback")

    posture = _body_posture(components, blockers)
    latest_receipt = _latest_receipt_id(optional_components.get("francis.receipts.readback", {}))
    orb_semantic_state = _orb_semantic_state()

    return {
        "kind": LENS_ORB_MCP_STATUS_KIND,
        "ok": not blockers,
        "status": "ready" if not blockers else "degraded",
        "actor": _safe_str(actor, "lens-orb"),
        "surface": "lens_orb_mcp_status_bridge_v0",
        "embodied_posture": posture,
        "resident": False,
        "resident_claim": "not_enabled_by_mcp_status_bridge",
        "orb_semantic_state": orb_semantic_state,
        "mcp": {
            # UI/operator-friendly alias paired with the explicit minimum contract.
            "expected_tool_count": EXPECTED_MIN_TOOL_COUNT,
            "expected_min_tool_count": EXPECTED_MIN_TOOL_COUNT,
            "tool_count": tool_count,
            "tool_count_preserved": tool_count >= EXPECTED_MIN_TOOL_COUNT,
            # Compatibility alias for the MCP gateway smoke output and operator scripts.
            "missing_tools": missing_required,
            "missing_required_tools": missing_required,
            "all_tools": sorted(tool_names),
        },
        "components": components,
        "optional_readbacks": optional_components,
        "developer_bridge": developer_bridge,
        "latest_receipt_id": latest_receipt,
        "badges": _component_badges(components, tool_count=tool_count),
        "blockers": blockers,
        "routes": {
            "mcp_status": "/lens/mcp/status",
            "orb_mcp_status": "/lens/orb/mcp-status",
            "mcp_contract": "/lens/mcp/contract",
            "mcp_perceive": "/lens/mcp/perceive",
            "mcp_observe": "/lens/mcp/observe",
            "mcp_receipts": "/lens/mcp/receipts",
            "developer_bridge": "/developer-bridge",
        },
        "governance": _honesty(),
    }


__all__ = ["EXPECTED_MIN_TOOL_COUNT", "LENS_ORB_MCP_STATUS_KIND", "lens_orb_mcp_status_bridge"]
