from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["OntologyNode", "Ontology"]


@dataclass(frozen=True)
class OntologyNode:
    name: str
    parents: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class Ontology:
    def __init__(self) -> None:
        self._nodes: dict[str, OntologyNode] = {}

    def add(self, node: OntologyNode) -> None:
        if not isinstance(node, OntologyNode):
            logger.warning("add expected OntologyNode")
            return
        self._nodes[node.name] = node

    def get(self, name: str) -> OntologyNode | None:
        return self._nodes.get(name)
