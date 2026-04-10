from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ResourceAllocation", "ResourceAllocator"]


@dataclass(frozen=True)
class ResourceAllocation:
    allocations: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class ResourceAllocator:
    def allocate(self, resources: dict[str, float]) -> ResourceAllocation:
        if not isinstance(resources, dict) or not resources:
            logger.warning("allocate expected resources dict")
            return ResourceAllocation(allocations={})
        return ResourceAllocation(allocations=dict(resources))
