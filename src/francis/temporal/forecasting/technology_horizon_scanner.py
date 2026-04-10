from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["HorizonScan", "TechnologyHorizonScanner"]


@dataclass(frozen=True)
class HorizonScan:
    signals: list[str]


class TechnologyHorizonScanner:
    def scan(self, topics: list[str]) -> HorizonScan:
        if not isinstance(topics, list):
            logger.warning("scan expected topics list")
            return HorizonScan(signals=[])
        return HorizonScan(signals=[t for t in topics if t])
