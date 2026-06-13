from __future__ import annotations

import json
from typing import Any

from .tools import run_tool


def _tool_payload(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2, ensure_ascii=False, default=str)


def run_stdio_server() -> None:
    """Run an MCP server if the optional MCP SDK is installed.

    The contract layer is dependency-free and tested separately. This adapter is
    intentionally thin so the repo can still validate without the MCP package.
    """
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
    except Exception as exc:
        raise RuntimeError(
            "Optional MCP SDK is not installed. Install the package that provides "
            "`mcp.server.fastmcp.FastMCP`, then run this module again."
        ) from exc

    server = FastMCP("francis-mcp-gateway")

    @server.tool(name="francis_health")
    def francis_health() -> str:
        return _tool_payload(run_tool("francis.health", {}))

    @server.tool(name="francis_repo_status")
    def francis_repo_status() -> str:
        return _tool_payload(run_tool("francis.repo.status", {}))

    @server.tool(name="francis_git_diff")
    def francis_git_diff(base: str = "HEAD", head: str = "") -> str:
        return _tool_payload(run_tool("francis.git.diff", {"base": base, "head": head}))

    @server.tool(name="francis_tests_run_targeted")
    def francis_tests_run_targeted(targets: list[str], timeout_sec: int = 900) -> str:
        return _tool_payload(run_tool("francis.tests.run_targeted", {"targets": targets, "timeout_sec": timeout_sec}))

    @server.tool(name="francis_command_propose")
    def francis_command_propose(
        kind: str,
        objective: str,
        actor: str = "mcp-client",
        targets: list[str] | None = None,
    ) -> str:
        return _tool_payload(
            run_tool(
                "francis.command.propose",
                {"kind": kind, "objective": objective, "actor": actor, "targets": targets or []},
            )
        )

    @server.tool(name="francis_command_execute_approved")
    def francis_command_execute_approved(
        proposal_id: str,
        approval_phrase: str,
        timeout_sec: int = 900,
    ) -> str:
        return _tool_payload(
            run_tool(
                "francis.command.execute_approved",
                {
                    "proposal_id": proposal_id,
                    "approval_phrase": approval_phrase,
                    "timeout_sec": timeout_sec,
                },
            )
        )

    @server.tool(name="francis_receipts_readback")
    def francis_receipts_readback(receipt_id: str = "") -> str:
        return _tool_payload(run_tool("francis.receipts.readback", {"receipt_id": receipt_id}))

    @server.tool(name="francis_input_status")
    def francis_input_status() -> str:
        return _tool_payload(run_tool("francis.input.status", {}))

    @server.tool(name="francis_input_propose")
    def francis_input_propose(
        kind: str,
        payload_json: str,
        objective: str,
        actor: str = "mcp-client",
        session_id: str = "",
    ) -> str:
        payload = json.loads(payload_json) if payload_json else {}
        return _tool_payload(
            run_tool(
                "francis.input.propose",
                {
                    "kind": kind,
                    "payload": payload,
                    "objective": objective,
                    "actor": actor,
                    "session_id": session_id,
                },
            )
        )

    @server.tool(name="francis_input_execute_approved")
    def francis_input_execute_approved(proposal_id: str, approval_phrase: str) -> str:
        return _tool_payload(
            run_tool(
                "francis.input.execute_approved",
                {"proposal_id": proposal_id, "approval_phrase": approval_phrase},
            )
        )

    @server.tool(name="francis_input_receipts")
    def francis_input_receipts(receipt_id: str = "") -> str:
        return _tool_payload(run_tool("francis.input.receipts", {"receipt_id": receipt_id}))

    server.run()


def main() -> int:
    run_stdio_server()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
