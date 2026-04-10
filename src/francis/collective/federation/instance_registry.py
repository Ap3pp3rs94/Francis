from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["InstanceInfo", "InstanceRegistry"]


@dataclass(frozen=True)
class InstanceInfo:
    instance_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


class InstanceRegistry:
    def __init__(self) -> None:
        self.instances: dict[str, InstanceInfo] = {}

    def register(self, instance_id: str, metadata: dict[str, Any] | None = None) -> InstanceInfo | None:
        if not instance_id:
            logger.warning("register expected instance_id")
            return None
        info = InstanceInfo(instance_id=instance_id, metadata=metadata or {})
        self.instances[instance_id] = info
        return info

    def get(self, instance_id: str) -> InstanceInfo | None:
        return self.instances.get(instance_id)
