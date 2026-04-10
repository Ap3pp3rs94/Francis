from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["TopicGraph", "RelationshipType", "TopicNode"]


class RelationshipType(Enum):
    RELATED = "related"
    SUB_TOPIC = "sub_topic"
    SUPER_TOPIC = "super_topic"


@dataclass(frozen=True, slots=True)
class TopicNode:
    id: str
    name: str
    created_at: float


@dataclass(slots=True)
class TopicGraph:
    nodes: dict[str, TopicNode] = field(default_factory=dict)
    edges: dict[tuple[str, str], RelationshipType] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_node(self, name: str) -> TopicNode | None:
        nm = str(name).strip()
        if not nm:
            logger.warning("name must be non-empty")
            return None
        if any(n.name == nm for n in self.nodes.values()):
            logger.warning("A node with the name '%s' already exists", nm)
            return None

        node_id = str(uuid.uuid4())
        new_node = TopicNode(id=node_id, name=nm, created_at=float(time.time()))
        self.nodes[node_id] = new_node
        logger.debug("Added node: %s", new_node)
        return new_node

    def _find_node_by_name(self, name: str) -> TopicNode | None:
        nm = str(name).strip()
        for n in self.nodes.values():
            if n.name == nm:
                return n
        return None

    def add_edge(self, from_name: str, to_name: str, relationship_type: RelationshipType) -> bool:
        if not isinstance(relationship_type, RelationshipType):
            logger.warning("relationship_type must be a RelationshipType")
            return False

        from_node = self._find_node_by_name(from_name)
        to_node = self._find_node_by_name(to_name)

        if not from_node:
            logger.warning("Node with name '%s' does not exist", from_name)
            return False
        if not to_node:
            logger.warning("Node with name '%s' does not exist", to_name)
            return False

        edge_key = (from_node.id, to_node.id)
        if edge_key in self.edges:
            logger.warning("An edge already exists between '%s' and '%s'", from_name, to_name)
            return False

        self.edges[edge_key] = relationship_type
        logger.debug("Added edge: %s -> %s (%s)", from_node.id, to_node.id, relationship_type.value)
        return True

    def remove_node(self, name: str) -> bool:
        node = self._find_node_by_name(name)
        if not node:
            logger.warning("Node with name '%s' does not exist", name)
            return False

        node_id = node.id
        for k in [k for k in self.edges.keys() if node_id in k]:
            del self.edges[k]
        del self.nodes[node_id]
        logger.debug("Removed node %s and connected edges", node_id)
        return True

    def remove_edge(self, from_name: str, to_name: str) -> bool:
        from_node = self._find_node_by_name(from_name)
        to_node = self._find_node_by_name(to_name)
        if not from_node:
            logger.warning("Node with name '%s' does not exist", from_name)
            return False
        if not to_node:
            logger.warning("Node with name '%s' does not exist", to_name)
            return False

        edge_key = (from_node.id, to_node.id)
        if edge_key not in self.edges:
            logger.warning("No edge exists between '%s' and '%s'", from_name, to_name)
            return False
        del self.edges[edge_key]
        logger.debug("Removed edge %s", edge_key)
        return True

    def get_neighbors(self, name: str) -> list[TopicNode]:
        node = self._find_node_by_name(name)
        if not node:
            logger.warning("Node with name '%s' does not exist", name)
            return []
        node_id = node.id

        neighbor_ids: set[str] = set()
        for a, b in self.edges.keys():
            if a == node_id:
                neighbor_ids.add(b)
            elif b == node_id:
                neighbor_ids.add(a)

        return [self.nodes[nid] for nid in neighbor_ids if nid in self.nodes]

    def to_dict(self) -> dict[str, Any]:
        nodes_dict = {nid: {"name": n.name, "created_at": float(n.created_at)} for nid, n in self.nodes.items()}
        edges_dict = {f"{a},{b}": rel.value for (a, b), rel in self.edges.items()}
        return {"nodes": nodes_dict, "edges": edges_dict, "metadata": dict(self.metadata or {})}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TopicGraph":
        raw_nodes = data.get("nodes") or {}
        raw_edges = data.get("edges") or {}
        meta = data.get("metadata") or {}

        nodes: dict[str, TopicNode] = {}
        for nid, nd in raw_nodes.items():
            nodes[str(nid)] = TopicNode(
                id=str(nid),
                name=str(nd.get("name", "")),
                created_at=float(nd.get("created_at", 0.0)),
            )

        edges: dict[tuple[str, str], RelationshipType] = {}
        for k, v in raw_edges.items():
            a, b = str(k).split(",", 1)
            edges[(a, b)] = RelationshipType(str(v))

        return cls(nodes=nodes, edges=edges, metadata=dict(meta))

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)
