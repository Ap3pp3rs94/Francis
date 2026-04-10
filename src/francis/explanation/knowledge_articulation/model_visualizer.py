from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ModelVisualization", "ModelVisualizer"]


@dataclass(frozen=True)
class ModelVisualization:
    title: str
    nodes: list[str] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelVisualizer:
    def visualize(self, title: str, nodes: list[str], edges: list[tuple[str, str]]) -> ModelVisualization | None:
        if not isinstance(title, str) or not title.strip():
            logger.warning("visualize expected title")
            return None
        nodes = [n for n in nodes if n]
        edges = [e for e in edges if isinstance(e, tuple) and len(e) == 2]
        return ModelVisualization(title=title.strip(), nodes=nodes, edges=edges)
