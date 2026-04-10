from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["NetworkMap", "NetworkMapper"]


@dataclass(frozen=True)
class NetworkMap:
    peers: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class NetworkMapper:
    def map(self, peers: list[str]) -> NetworkMap:
        if not isinstance(peers, list):
            logger.warning("map expected peers list")
            return NetworkMap(peers=[])
        return NetworkMap(peers=sorted({p for p in peers if p}))
