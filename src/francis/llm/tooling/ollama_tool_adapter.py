from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["OllamaTool", "OllamaToolAdapter"]


@dataclass(frozen=True)
class OllamaTool:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


class OllamaToolAdapter:
    def adapt(self, tool: dict[str, Any]) -> OllamaTool | None:
        if not isinstance(tool, dict):
            logger.warning("adapt expected tool dict")
            return None
        name = str(tool.get("name", "")).strip()
        description = str(tool.get("description", "")).strip()
        if not name:
            logger.warning("adapt missing name")
            return None
        return OllamaTool(name=name, description=description, parameters=dict(tool.get("parameters") or {}))
