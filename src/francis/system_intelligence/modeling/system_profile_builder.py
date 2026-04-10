from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["SystemProfile", "SystemProfileBuilder"]


@dataclass(frozen=True)
class SystemProfile:
    host_id: str
    os: str
    cpu_cores: int
    memory_gb: float
    services: list[str] = field(default_factory=list)
    apps: list[str] = field(default_factory=list)
    network_peers: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def health_score(self) -> float:
        score = 1.0
        if self.cpu_cores <= 0 or self.memory_gb <= 0:
            score -= 0.5
        if not self.services:
            score -= 0.1
        return max(0.0, min(1.0, score))


class SystemProfileBuilder:
    def build(
        self,
        host_id: str,
        os: str,
        cpu_cores: int,
        memory_gb: float,
        services: list[str] | None = None,
        apps: list[str] | None = None,
        network_peers: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SystemProfile | None:
        if not host_id or not os:
            logger.warning("build expected host_id and os")
            return None
        try:
            cores = int(cpu_cores)
            mem = float(memory_gb)
        except (TypeError, ValueError):
            logger.warning("build expected numeric cpu_cores and memory_gb")
            return None
        return SystemProfile(
            host_id=str(host_id),
            os=str(os),
            cpu_cores=cores,
            memory_gb=mem,
            services=list(services or []),
            apps=list(apps or []),
            network_peers=list(network_peers or []),
            metadata=dict(metadata or {}),
        )
