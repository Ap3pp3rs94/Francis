from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["KnowledgeGraph", "KnowledgeGraphBuilder"]


@dataclass
class KnowledgeGraph:
    nodes: set[str] = field(default_factory=set)
    edges: set[tuple[str, str]] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)


class KnowledgeGraphBuilder:
    def add_edge(self, graph: KnowledgeGraph, source: str, target: str) -> None:
        if not isinstance(graph, KnowledgeGraph):
            logger.warning("add_edge expected KnowledgeGraph")
            return
        if not source or not target:
            return
        graph.nodes.add(source)
        graph.nodes.add(target)
        graph.edges.add((source, target))
