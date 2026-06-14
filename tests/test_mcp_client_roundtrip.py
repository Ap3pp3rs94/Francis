"""End-to-end: an external MCP client drives the Francis gateway over stdio.

This is the protocol-level proof behind "chat with GPT and it works through Francis":
a real MCP client (the same transport Codex/ChatGPT use) spawns the governed gateway
as a subprocess, lists tools, calls a read-only tool, and confirms a mutating tool
still refuses without approval -- governance held over the wire.

Skipped where the optional MCP SDK (`bridge` extra) is not installed.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

import pytest

pytest.importorskip("mcp")

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from francis.kernel.paths import repo_root  # noqa: E402


async def _roundtrip(data_dir: str) -> dict:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "francis.mcp_gateway.server"],
        cwd=str(repo_root()),
        env={**os.environ, "FRANCIS_DATA_DIR": data_dir},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            health = json.loads((await session.call_tool("francis_health", {})).content[0].text)
            denied = json.loads(
                (
                    await session.call_tool(
                        "francis_input_execute_approved",
                        {"proposal_id": "nope", "approval_phrase": "nope"},
                    )
                ).content[0].text
            )
            return {"names": names, "health": health, "denied": denied}


def test_external_mcp_client_roundtrip(tmp_path) -> None:
    out = asyncio.run(_roundtrip(str(tmp_path / "data")))

    # All registry tools are advertised over the wire.
    assert "francis_health" in out["names"]
    assert "francis_handoff_audit" in out["names"]
    assert len(out["names"]) >= 18

    # Read-only tool returns real data over the wire.
    assert out["health"]["ok"] is True
    assert out["health"]["governance"]["read_only"] is True

    # Governance holds over the wire: a mutating tool refuses without approval.
    assert out["denied"]["ok"] is False
    assert out["denied"]["status"] == "approval_required"
