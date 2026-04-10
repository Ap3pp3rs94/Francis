from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["CombinationResult", "CombinationExplorer"]


@dataclass(frozen=True)
class CombinationResult:
    items: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


class CombinationExplorer:
    def explore(self, items: list[str], size: int = 2, limit: int = 10) -> list[CombinationResult]:
        if not isinstance(items, list) or size <= 0 or limit <= 0:
            logger.warning("explore received invalid inputs")
            return []
        combos = itertools.islice(itertools.combinations(items, size), limit)
        return [CombinationResult(items=tuple(combo)) for combo in combos]
