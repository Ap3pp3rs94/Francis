from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class McpGatewayError(ValueError):
    """Bounded user-facing MCP gateway error."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    read_only: bool
    requires_approval: bool = False


@dataclass
class ToolResult:
    ok: bool
    status: str
    tool: str
    data: dict[str, Any] = field(default_factory=dict)
    governance: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": self.ok,
            "status": self.status,
            "tool": self.tool,
            "data": self.data,
            "governance": self.governance,
        }
        if self.error:
            payload["error"] = self.error
        return payload
