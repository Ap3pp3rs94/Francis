from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["Tool", "ToolSelection", "ToolSelector"]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    available: bool = True


@dataclass(frozen=True)
class ToolSelection:
    tool: Tool | None
    reason: str


class ToolSelector:
    def __init__(self) -> None:
        self.tools: list[Tool] = []

    def add_tool(self, tool: Tool) -> None:
        if not isinstance(tool, Tool):
            raise ValueError("Invalid tool type")
        self.tools.append(tool)

    def get_available_tools(self) -> list[str]:
        return [tool.name for tool in self.tools if tool.available]

    def select_tool(self, tool_name: str) -> ToolSelection:
        try:
            selected = next((tool for tool in self.tools if tool.name == tool_name), None)
        except Exception as exc:
            logger.error("Error selecting tool %s: %s", tool_name, exc)
            return ToolSelection(tool=None, reason="selection_error")

        if not selected:
            return ToolSelection(tool=None, reason="not_found")
        if not selected.available:
            logger.warning("Tool %s not available", tool_name)
            return ToolSelection(tool=None, reason="not_available")
        return ToolSelection(tool=selected, reason="ok")
