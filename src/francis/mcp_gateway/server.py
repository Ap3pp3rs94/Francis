from __future__ import annotations

import json
from typing import Any

from .tools import run_tool


def _tool_payload(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2, ensure_ascii=False, default=str)


def run_server(
    *,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8787,
    streamable_http_path: str = "/mcp",
) -> None:
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

    if transport not in {"stdio", "sse", "streamable-http"}:
        raise ValueError(f"unsupported MCP transport: {transport}")

    server = FastMCP(
        "francis-mcp-gateway",
        instructions=(
            "Francis is a local-first governed operator layer. Use chatgpt voice tools for "
            "transcript-only ingress; they record receipts and do not grant execution authority."
        ),
        host=host,
        port=port,
        streamable_http_path=streamable_http_path,
        stateless_http=transport == "streamable-http",
    )

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

    @server.tool(name="francis_screen_status")
    def francis_screen_status() -> str:
        return _tool_payload(run_tool("francis.screen.status", {}))

    @server.tool(name="francis_screen_session")
    def francis_screen_session() -> str:
        return _tool_payload(run_tool("francis.screen.session", {}))

    @server.tool(name="francis_takeover_status")
    def francis_takeover_status() -> str:
        return _tool_payload(run_tool("francis.takeover.status", {}))

    @server.tool(name="francis_takeover_propose")
    def francis_takeover_propose(
        reason: str,
        actor: str = "mcp-client",
        mode: str = "pilot",
        duration_sec: int = 900,
        scope: str = "bounded operator session",
        mission_id: str = "",
    ) -> str:
        return _tool_payload(
            run_tool(
                "francis.takeover.propose",
                {
                    "actor": actor,
                    "reason": reason,
                    "mode": mode,
                    "duration_sec": duration_sec,
                    "scope": scope,
                    "mission_id": mission_id,
                },
            )
        )

    @server.tool(name="francis_takeover_start_approved")
    def francis_takeover_start_approved(proposal_id: str, approval_phrase: str) -> str:
        return _tool_payload(
            run_tool(
                "francis.takeover.start_approved",
                {"proposal_id": proposal_id, "approval_phrase": approval_phrase},
            )
        )

    @server.tool(name="francis_takeover_end")
    def francis_takeover_end(
        reason: str,
        actor: str = "mcp-client",
        summary: str = "Takeover/Pilot session ended by operator request.",
        validation_outcome: str = "not_run",
        remaining_uncertainty: str = "",
        next_recommendation: str = "",
    ) -> str:
        return _tool_payload(
            run_tool(
                "francis.takeover.end",
                {
                    "actor": actor,
                    "reason": reason,
                    "summary": summary,
                    "validation_outcome": validation_outcome,
                    "remaining_uncertainty": remaining_uncertainty,
                    "next_recommendation": next_recommendation,
                },
            )
        )

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

    @server.tool(name="francis_handoff_audit")
    def francis_handoff_audit(input_proposal_id: str = "", limit: int = 10) -> str:
        return _tool_payload(
            run_tool("francis.handoff.audit", {"input_proposal_id": input_proposal_id, "limit": limit})
        )

    @server.tool(name="francis_chatgpt_voice_contract")
    def francis_chatgpt_voice_contract(actor: str = "chatgpt.voice") -> str:
        return _tool_payload(run_tool("francis.chatgpt_voice.contract", {"actor": actor}))

    @server.tool(name="francis_chatgpt_voice_ingress")
    def francis_chatgpt_voice_ingress(
        transcript: str,
        actor: str = "chatgpt.voice",
        source: str = "chatgpt.voice",
        conversation_id: str = "",
        turn_id: str = "",
        locale: str = "",
        forward_to_chat: bool = True,
        use_llm: bool = False,
    ) -> str:
        """Record exact transcribed text and return a top-level Francis reply.

        If the voice client has no transcript, pass an empty string or the
        unavailable marker; do not invent the operator's words.
        """
        return _tool_payload(
            run_tool(
                "francis.chatgpt_voice.ingress",
                {
                    "actor": actor,
                    "transcript": transcript,
                    "source": source,
                    "conversation_id": conversation_id,
                    "turn_id": turn_id,
                    "locale": locale,
                    "forward_to_chat": forward_to_chat,
                    "use_llm": use_llm,
                },
            )
        )

    @server.tool(name="francis_chatgpt_voice_receipts")
    def francis_chatgpt_voice_receipts(actor: str = "chatgpt.voice", limit: int = 10) -> str:
        return _tool_payload(run_tool("francis.chatgpt_voice.receipts", {"actor": actor, "limit": limit}))

    server.run(transport=transport)


def run_stdio_server() -> None:
    run_server(transport="stdio")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run the governed Francis MCP gateway.")
    parser.add_argument(
        "--transport",
        choices=("stdio", "sse", "streamable-http"),
        default="stdio",
        help="MCP transport to expose.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for HTTP transports.")
    parser.add_argument("--port", type=int, default=8787, help="Port for HTTP transports.")
    parser.add_argument("--path", default="/mcp", help="Streamable HTTP MCP path.")
    args = parser.parse_args()

    run_server(
        transport=args.transport,
        host=args.host,
        port=args.port,
        streamable_http_path=args.path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
