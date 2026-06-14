from __future__ import annotations

import importlib.util
import os
import tempfile
from collections.abc import Mapping
from typing import Any

from francis.mcp_gateway.tools import list_tools, run_tool

REQUIRED_TOOLS = {
    "francis.health",
    "francis.repo.status",
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
}


def _mcp_sdk_available() -> bool:
    return importlib.util.find_spec("mcp") is not None


def _status(result: Mapping[str, Any]) -> str:
    value = result.get("status")
    return value if isinstance(value, str) else "unknown"


def _proposal_id(result: Mapping[str, Any]) -> str:
    data = result.get("data")
    if not isinstance(data, Mapping):
        return ""

    nested = data.get("data")
    if isinstance(nested, Mapping):
        proposal_id = nested.get("proposal_id")
        if isinstance(proposal_id, str):
            return proposal_id

    proposal_id = data.get("proposal_id")
    return proposal_id if isinstance(proposal_id, str) else ""


def _is_readback_safe(result: Mapping[str, Any]) -> bool:
    governance = result.get("governance")
    if not isinstance(governance, Mapping):
        return False
    return (
        bool(governance.get("read_only"))
        and governance.get("raw_shell") is False
        and governance.get("screenshots") is False
        and governance.get("pixels") is False
    )


def run_smoke() -> dict[str, Any]:
    old_input_dir = os.environ.get("FRANCIS_INPUT_ACTUATOR_STATE_DIR")
    old_takeover_dir = os.environ.get("FRANCIS_TAKEOVER_SESSION_STATE_DIR")
    old_data_dir = os.environ.get("FRANCIS_DATA_DIR")

    with tempfile.TemporaryDirectory(prefix="francis-mcp-smoke-") as state_dir:
        os.environ["FRANCIS_INPUT_ACTUATOR_STATE_DIR"] = os.path.join(state_dir, "input")
        os.environ["FRANCIS_TAKEOVER_SESSION_STATE_DIR"] = os.path.join(state_dir, "takeover_session")
        os.environ["FRANCIS_DATA_DIR"] = os.path.join(state_dir, "data")

        try:
            tools = list_tools()
            names = {tool["name"] for tool in tools}
            missing = sorted(REQUIRED_TOOLS - names)

            health = run_tool("francis.health", {})
            screen_status = run_tool("francis.screen.status", {})
            screen_session = run_tool("francis.screen.session", {})
            takeover_status = run_tool("francis.takeover.status", {})
            takeover_proposal = run_tool(
                "francis.takeover.propose",
                {
                    "actor": "mcp-smoke",
                    "reason": "verify takeover session proposal refusal path",
                    "mode": "pilot",
                    "duration_sec": 120,
                },
            )
            takeover_proposal_id = _proposal_id(takeover_proposal)
            takeover_denied = run_tool(
                "francis.takeover.start_approved",
                {"proposal_id": takeover_proposal_id, "approval_phrase": "not-approved"},
            )
            input_status = run_tool("francis.input.status", {})
            proposal = run_tool(
                "francis.input.propose",
                {
                    "actor": "mcp-smoke",
                    "objective": "verify governed input refusal path",
                    "kind": "mouse.move",
                    "payload": {"x": 1, "y": 2},
                },
            )

            proposal_id = _proposal_id(proposal)
            denied = run_tool(
                "francis.input.execute_approved",
                {
                    "proposal_id": proposal_id,
                    "approval_phrase": "not-approved",
                },
            )

            ok = (
                not missing
                and bool(health.get("ok"))
                and _status(health) == "ready"
                and bool(screen_status.get("ok"))
                and _status(screen_status) == "ready"
                and bool(screen_session.get("ok"))
                and _status(screen_session) == "ready"
                and _is_readback_safe(screen_session)
                and bool(takeover_status.get("ok"))
                and bool(takeover_proposal.get("ok"))
                and bool(takeover_proposal_id)
                and not bool(takeover_denied.get("ok"))
                and _status(takeover_denied) == "approval_required"
                and bool(input_status.get("ok"))
                and _status(input_status) == "ready"
                and bool(proposal.get("ok"))
                and bool(proposal_id)
                and not bool(denied.get("ok"))
                and _status(denied) == "approval_required"
            )

            return {
                "ok": ok,
                "mcp_sdk_available": _mcp_sdk_available(),
                "tool_count": len(tools),
                "missing_tools": missing,
                "health_status": _status(health),
                "screen_status": _status(screen_status),
                "screen_session_status": _status(screen_session),
                "screen_readback_safe": _is_readback_safe(screen_session),
                "takeover_status": _status(takeover_status),
                "takeover_proposal_created": bool(takeover_proposal_id),
                "unapproved_takeover_refused": (
                    not bool(takeover_denied.get("ok")) and _status(takeover_denied) == "approval_required"
                ),
                "input_status": _status(input_status),
                "proposal_created": bool(proposal_id),
                "unapproved_input_refused": (not bool(denied.get("ok")) and _status(denied) == "approval_required"),
            }
        finally:
            _restore_env("FRANCIS_INPUT_ACTUATOR_STATE_DIR", old_input_dir)
            _restore_env("FRANCIS_TAKEOVER_SESSION_STATE_DIR", old_takeover_dir)
            _restore_env("FRANCIS_DATA_DIR", old_data_dir)


def _restore_env(name: str, previous: str | None) -> None:
    if previous is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = previous


def main() -> int:
    result = run_smoke()

    print("Francis MCP smoke")
    print(f"  ok: {result['ok']}")
    print(f"  mcp_sdk_available: {result['mcp_sdk_available']}")
    print(f"  tool_count: {result['tool_count']}")
    print(f"  missing_tools: {result['missing_tools']}")
    print(f"  health_status: {result['health_status']}")
    print(f"  screen_status: {result['screen_status']}")
    print(f"  screen_session_status: {result['screen_session_status']}")
    print(f"  screen_readback_safe: {result['screen_readback_safe']}")
    print(f"  takeover_status: {result['takeover_status']}")
    print(f"  takeover_proposal_created: {result['takeover_proposal_created']}")
    print(f"  unapproved_takeover_refused: {result['unapproved_takeover_refused']}")
    print(f"  input_status: {result['input_status']}")
    print(f"  proposal_created: {result['proposal_created']}")
    print(f"  unapproved_input_refused: {result['unapproved_input_refused']}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
