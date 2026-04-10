from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["BlindspotReport", "BlindspotDetector"]


@dataclass(frozen=True)
class BlindspotReport:
    blindspots: list[str]


class BlindspotDetector:
    def detect(self, signals: list[str]) -> BlindspotReport:
        if not isinstance(signals, list):
            logger.warning("detect expected signals list")
            return BlindspotReport(blindspots=[])
        return BlindspotReport(blindspots=[s for s in signals if s])
