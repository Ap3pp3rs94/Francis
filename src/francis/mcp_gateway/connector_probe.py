from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any


def _bounded_timeout_seconds(value: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = 5.0
    return min(max(parsed, 0.1), 60.0)


def _base_result(connector_url: str, expected_tool: str, timeout_seconds: float) -> dict[str, Any]:
    return {
        "kind": "francis.mcp_gateway.connector_probe",
        "ok": False,
        "status": "not_run",
        "connector_url": str(connector_url or "").strip(),
        "expected_tool": str(expected_tool or "").strip(),
        "timeout_seconds": timeout_seconds,
        "reachability_verified": False,
        "tool_list_observed": False,
        "tool_count": 0,
        "expected_tool_present": False,
        "error": "",
        "governance": {
            "read_only": True,
            "writes_repo": False,
            "writes_data": False,
            "writes_receipts": False,
            "calls_francis_tools": False,
            "calls_model": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }


async def probe_connector(
    connector_url: str,
    *,
    expected_tool: str = "francis_chatgpt_voice_ingress",
    timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    timeout = _bounded_timeout_seconds(timeout_seconds)
    result = _base_result(connector_url, expected_tool, timeout)
    if not result["connector_url"]:
        result["status"] = "connector_url_required"
        result["error"] = "connector_url_required"
        return result

    try:
        from mcp import ClientSession  # type: ignore[import-not-found]
        from mcp.client.streamable_http import streamablehttp_client  # type: ignore[import-not-found]
    except Exception as exc:
        result["status"] = "mcp_sdk_unavailable"
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    async def _list_tools() -> Any:
        async with streamablehttp_client(result["connector_url"]) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.list_tools()

    try:
        tools = await asyncio.wait_for(_list_tools(), timeout=timeout)
    except TimeoutError:
        result["status"] = "connector_probe_timeout"
        result["error"] = f"timeout_seconds={timeout:g}"
        return result
    except Exception as exc:
        result["status"] = "connector_unreachable"
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    names = [str(tool.name) for tool in tools.tools]
    expected_tool_present = result["expected_tool"] in names
    result.update(
        {
            "ok": expected_tool_present,
            "status": "ready" if expected_tool_present else "expected_tool_missing",
            "reachability_verified": True,
            "tool_list_observed": True,
            "tool_count": len(names),
            "expected_tool_present": expected_tool_present,
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only probe for a public Francis MCP connector URL.")
    parser.add_argument("--connector-url", required=True, help="Public HTTPS MCP URL ending in /mcp.")
    parser.add_argument(
        "--expected-tool",
        default="francis_chatgpt_voice_ingress",
        help="Tool that must be present for this connector to be considered ready.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=5.0,
        help="Maximum seconds to wait for the read-only connector probe.",
    )
    args = parser.parse_args()

    result = asyncio.run(
        probe_connector(
            args.connector_url,
            expected_tool=args.expected_tool,
            timeout_seconds=args.timeout_seconds,
        )
    )
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
