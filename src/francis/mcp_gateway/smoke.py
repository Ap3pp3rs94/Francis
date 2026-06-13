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


def run_smoke() -> dict[str, Any]:
    old_state_dir = os.environ.get("FRANCIS_INPUT_ACTUATOR_STATE_DIR")

    with tempfile.TemporaryDirectory(prefix="francis-mcp-smoke-") as state_dir:
        os.environ["FRANCIS_INPUT_ACTUATOR_STATE_DIR"] = state_dir

        try:
            tools = list_tools()
            names = {tool["name"] for tool in tools}
            missing = sorted(REQUIRED_TOOLS - names)

            health = run_tool("francis.health", {})
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
                "input_status": _status(input_status),
                "proposal_created": bool(proposal_id),
                "unapproved_input_refused": (not bool(denied.get("ok")) and _status(denied) == "approval_required"),
            }
        finally:
            if old_state_dir is None:
                os.environ.pop("FRANCIS_INPUT_ACTUATOR_STATE_DIR", None)
            else:
                os.environ["FRANCIS_INPUT_ACTUATOR_STATE_DIR"] = old_state_dir


def main() -> int:
    result = run_smoke()

    print("Francis MCP smoke")
    print(f"  ok: {result['ok']}")
    print(f"  mcp_sdk_available: {result['mcp_sdk_available']}")
    print(f"  tool_count: {result['tool_count']}")
    print(f"  missing_tools: {result['missing_tools']}")
    print(f"  health_status: {result['health_status']}")
    print(f"  input_status: {result['input_status']}")
    print(f"  proposal_created: {result['proposal_created']}")
    print(f"  unapproved_input_refused: {result['unapproved_input_refused']}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
