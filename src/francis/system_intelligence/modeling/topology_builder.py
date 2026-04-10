from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["TopologyGraph", "TopologyBuilder"]


@dataclass
class TopologyGraph:
    nodes: set[str] = field(default_factory=set)
    edges: set[tuple[str, str]] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)

    def adjacency(self) -> dict[str, list[str]]:
        graph: dict[str, list[str]] = {node: [] for node in self.nodes}
        for a, b in self.edges:
            graph.setdefault(a, []).append(b)
        return graph


class TopologyBuilder:
    def add_node(self, graph: TopologyGraph, node: str) -> None:
        if not isinstance(graph, TopologyGraph):
            logger.warning("add_node expected TopologyGraph")
            return
        if not node:
            return
        graph.nodes.add(node)

    def add_edge(self, graph: TopologyGraph, src: str, dst: str) -> None:
        if not isinstance(graph, TopologyGraph):
            logger.warning("add_edge expected TopologyGraph")
            return
        if not src or not dst:
            return
        graph.nodes.add(src)
        graph.nodes.add(dst)
        graph.edges.add((src, dst))
