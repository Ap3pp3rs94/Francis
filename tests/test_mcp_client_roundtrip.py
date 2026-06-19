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
    actor_scopes = json.dumps(
        {
            "chatgpt.voice": [
                "chatgpt.voice.bridge.read",
                "chatgpt.voice.bridge.write",
                "chat.write",
            ]
        }
    )
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "francis.mcp_gateway.server"],
        cwd=str(repo_root()),
        env={**os.environ, "FRANCIS_DATA_DIR": data_dir, "FRANCIS_API_ACTOR_SCOPES": actor_scopes},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            voice_tool = next(t for t in tools.tools if t.name == "francis_chatgpt_voice_ingress")
            probe_tool = next(t for t in tools.tools if t.name == "francis_chatgpt_voice_mcp_probe")
            health = json.loads((await session.call_tool("francis_health", {})).content[0].text)
            denied = json.loads(
                (
                    await session.call_tool(
                        "francis_input_execute_approved",
                        {"proposal_id": "nope", "approval_phrase": "nope"},
                    )
                )
                .content[0]
                .text
            )
            voice = json.loads(
                (
                    await session.call_tool(
                        "francis_chatgpt_voice_ingress",
                        {
                            "actor": "chatgpt.voice",
                            "transcript": "can you hear me",
                            "turn_id": "mcp-roundtrip-voice",
                            "forward_to_chat": False,
                        },
                    )
                )
                .content[0]
                .text
            )
            probe = json.loads(
                (
                    await session.call_tool(
                        "francis_chatgpt_voice_mcp_probe",
                        {
                            "actor": "chatgpt.voice",
                            "source": "chatgpt.voice",
                            "reason": "mcp roundtrip proof",
                        },
                    )
                )
                .content[0]
                .text
            )
            return {
                "names": names,
                "health": health,
                "denied": denied,
                "voice": voice,
                "probe": probe,
                "voice_tool": {
                    "title": getattr(voice_tool, "title", ""),
                    "description": getattr(voice_tool, "description", ""),
                    "annotations": (
                        voice_tool.annotations.model_dump() if getattr(voice_tool, "annotations", None) else {}
                    ),
                },
                "probe_tool": {
                    "title": getattr(probe_tool, "title", ""),
                    "description": getattr(probe_tool, "description", ""),
                    "annotations": (
                        probe_tool.annotations.model_dump() if getattr(probe_tool, "annotations", None) else {}
                    ),
                },
            }


def test_external_mcp_client_roundtrip(tmp_path) -> None:
    out = asyncio.run(_roundtrip(str(tmp_path / "data")))

    # All registry tools are advertised over the wire.
    assert "francis_health" in out["names"]
    assert "francis_handoff_audit" in out["names"]
    assert "francis_chatgpt_voice_ingress" in out["names"]
    assert "francis_chatgpt_voice_mcp_probe" in out["names"]
    assert len(out["names"]) >= 21
    assert out["voice_tool"]["title"] == "Send transcript to Francis"
    assert "talk to Francis" in out["voice_tool"]["description"]
    assert "speak only the returned top-level `reply`" in out["voice_tool"]["description"]
    assert "Do not answer locally" in out["voice_tool"]["description"]
    assert "Transcript Unavailable" in out["voice_tool"]["description"]
    assert out["voice_tool"]["annotations"]["readOnlyHint"] is False
    assert out["voice_tool"]["annotations"]["destructiveHint"] is False
    assert out["probe_tool"]["title"] == "Validate Francis voice MCP connection"
    assert "connection-proof receipt" in out["probe_tool"]["description"]

    # Read-only tool returns real data over the wire.
    assert out["health"]["ok"] is True
    assert out["health"]["governance"]["read_only"] is True

    # Governance holds over the wire: a mutating tool refuses without approval.
    assert out["denied"]["ok"] is False
    assert out["denied"]["status"] == "approval_required"

    # ChatGPT voice transcript ingress is reachable over the same MCP transport.
    assert out["voice"]["ok"] is True
    assert out["voice"]["status"] == "recorded"
    assert out["voice"]["reply"] == "I recorded the transcript for Francis. Chat forwarding was not requested."
    assert out["voice"]["voice_response"]["speakable"] is True
    assert out["voice"]["chat_forward"]["requested"] is False
    assert out["voice"]["orb_voice_bridge"]["virtual_voice_turn"] is True
    assert out["voice"]["orb_voice_bridge"]["mcp_ingress"] is True
    assert out["voice"]["orb_voice_bridge"]["client_origin"] == "chatgpt_app_voice"
    assert out["voice"]["orb_voice_bridge"]["local_overlay_speech_started"] is False
    assert out["voice"]["orb_voice_bridge"]["microphone_recognition_claimed"] is False
    assert out["voice"]["receipt"]["transcript"] == "can you hear me"
    assert out["voice"]["receipt"]["ingress_transport"] == "mcp_gateway_tool"
    assert out["voice"]["receipt"]["mcp_gateway_tool"] == "francis.chatgpt_voice.ingress"
    assert out["voice"]["receipt"]["mcp_server_tool"] == "francis_chatgpt_voice_ingress"
    assert out["voice"]["receipt"]["mcp_server_transport"] == "stdio"
    assert out["voice"]["receipt"]["client_origin"] == "chatgpt_app_voice"
    assert out["voice"]["data"]["reply"] == "I recorded the transcript for Francis. Chat forwarding was not requested."
    assert out["voice"]["data"]["voice_response"]["speakable"] is True
    assert out["voice"]["data"]["chat_forward"]["requested"] is False
    assert out["voice"]["data"]["orb_voice_bridge"]["virtual_voice_turn"] is True
    assert out["voice"]["data"]["orb_voice_bridge"]["mcp_ingress"] is True
    assert out["voice"]["data"]["orb_voice_bridge"]["client_origin"] == "chatgpt_app_voice"
    assert out["voice"]["data"]["receipt"]["transcript"] == "can you hear me"
    assert out["voice"]["data"]["receipt"]["ingress_transport"] == "mcp_gateway_tool"
    assert out["voice"]["data"]["receipt"]["mcp_gateway_tool"] == "francis.chatgpt_voice.ingress"
    assert out["voice"]["data"]["receipt"]["mcp_server_tool"] == "francis_chatgpt_voice_ingress"
    assert out["voice"]["data"]["receipt"]["mcp_server_transport"] == "stdio"
    assert out["voice"]["data"]["receipt"]["client_origin"] == "chatgpt_app_voice"
    assert out["voice"]["governance"]["raw_audio"] is False
    assert out["voice"]["governance"]["grants_execution_authority"] is False
    assert out["probe"]["ok"] is True
    assert out["probe"]["status"] == "recorded"
    assert out["probe"]["receipt"]["proof_kind"] == "mcp_connection"
    assert out["probe"]["receipt"]["mcp_gateway_tool"] == "francis.chatgpt_voice.mcp_probe"
    assert out["probe"]["receipt"]["mcp_server_tool"] == "francis_chatgpt_voice_mcp_probe"
    assert out["probe"]["receipt"]["mcp_server_transport"] == "stdio"
    assert out["probe"]["receipt"]["transcript"] == ""
    assert out["probe"]["orb_voice_bridge"]["virtual_voice_turn"] is False
    assert out["probe"]["governance"]["grants_execution_authority"] is False
