from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ServiceInventory", "ServiceProbe"]


@dataclass(frozen=True)
class ServiceInventory:
    services: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ServiceProbe:
    def probe(self, services: list[str]) -> ServiceInventory:
        if not isinstance(services, list):
            logger.warning("probe expected services list")
            return ServiceInventory(services=[])
        return ServiceInventory(services=sorted({s for s in services if s}))
