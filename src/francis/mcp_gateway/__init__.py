"""Francis MCP Gateway v0.

This package exposes a contract-first local ingress surface for MCP-capable
clients. The gateway is intentionally not raw PC control. Tools must route
through bounded Francis readback/execution helpers and return structured truth.
"""

from .contracts import McpGatewayError, ToolResult
from .tools import list_tools, run_tool

__all__ = ["McpGatewayError", "ToolResult", "list_tools", "run_tool"]
