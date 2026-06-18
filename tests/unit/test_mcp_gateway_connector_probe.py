from __future__ import annotations

import asyncio

from francis.mcp_gateway.connector_probe import probe_connector


def test_connector_probe_refuses_empty_url_without_network() -> None:
    result = asyncio.run(probe_connector("", expected_tool="francis_chatgpt_voice_ingress"))

    assert result["ok"] is False
    assert result["status"] == "connector_url_required"
    assert result["reachability_verified"] is False
    assert result["tool_list_observed"] is False
    assert result["governance"]["read_only"] is True
    assert result["governance"]["writes_receipts"] is False
    assert result["governance"]["calls_francis_tools"] is False
    assert result["governance"]["grants_execution_authority"] is False
    assert result["governance"]["grants_mutation_authority"] is False
