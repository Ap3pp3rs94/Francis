from __future__ import annotations

import asyncio
import sys
import types

from francis.mcp_gateway import connector_probe


def test_connector_probe_refuses_empty_url_without_network() -> None:
    result = asyncio.run(connector_probe.probe_connector("", expected_tool="francis_chatgpt_voice_ingress"))

    assert result["ok"] is False
    assert result["status"] == "connector_url_required"
    assert result["timeout_seconds"] == 5.0
    assert result["reachability_verified"] is False
    assert result["tool_list_observed"] is False
    assert result["governance"]["read_only"] is True
    assert result["governance"]["writes_receipts"] is False
    assert result["governance"]["calls_francis_tools"] is False
    assert result["governance"]["grants_execution_authority"] is False
    assert result["governance"]["grants_mutation_authority"] is False


def test_connector_probe_timeout_is_bounded(monkeypatch) -> None:
    mcp_module = types.ModuleType("mcp")
    mcp_module.ClientSession = object
    streamable_http_module = types.ModuleType("mcp.client.streamable_http")
    streamable_http_module.streamablehttp_client = object
    monkeypatch.setitem(sys.modules, "mcp", mcp_module)
    monkeypatch.setitem(sys.modules, "mcp.client", types.ModuleType("mcp.client"))
    monkeypatch.setitem(sys.modules, "mcp.client.streamable_http", streamable_http_module)

    async def fake_wait_for(awaitable, *, timeout):
        assert timeout == 0.1
        awaitable.close()
        raise TimeoutError

    monkeypatch.setattr(connector_probe.asyncio, "wait_for", fake_wait_for)

    result = asyncio.run(
        connector_probe.probe_connector(
            "https://francis.example.test/mcp",
            expected_tool="francis_chatgpt_voice_ingress",
            timeout_seconds=-1,
        )
    )

    assert result["ok"] is False
    assert result["status"] == "connector_probe_timeout"
    assert result["timeout_seconds"] == 0.1
    assert result["error"] == "timeout_seconds=0.1"
    assert result["reachability_verified"] is False
    assert result["tool_list_observed"] is False
