from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

__all__ = ["CapabilityRegistry", "CapabilityDiscovery"]


@dataclass
class CapabilityRegistry:
    capabilities: dict[str, list[str]] = field(default_factory=dict)

    def register(self, instance_id: str, caps: list[str]) -> None:
        if not instance_id:
            logger.warning("register expected instance_id")
            return
        self.capabilities[instance_id] = list(caps)

    def list_capabilities(self, instance_id: str) -> list[str]:
        return list(self.capabilities.get(instance_id, []))


class CapabilityDiscovery:
    def __init__(self, registry: CapabilityRegistry | None = None) -> None:
        self.registry = registry or CapabilityRegistry()

    def discover(self, instance_id: str) -> list[str]:
        if not instance_id:
            logger.warning("discover expected instance_id")
            return []
        return self.registry.list_capabilities(instance_id)
