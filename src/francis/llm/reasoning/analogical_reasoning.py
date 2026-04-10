from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["AnalogyResult", "AnalogicalReasoner"]


@dataclass(frozen=True)
class AnalogyResult:
    source: str
    target: str
    mapping: str


class AnalogicalReasoner:
    def map(self, source: str, target: str) -> AnalogyResult | None:
        if not source or not target:
            logger.warning("map expected source and target")
            return None
        mapping = f"{source} ~ {target}"
        return AnalogyResult(source=source, target=target, mapping=mapping)
