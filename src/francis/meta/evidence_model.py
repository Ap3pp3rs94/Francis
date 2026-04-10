from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["EvidenceItem", "EvidenceModel"]


@dataclass(frozen=True)
class EvidenceItem:
    source: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class EvidenceModel:
    def __init__(self) -> None:
        self._items: list[EvidenceItem] = []

    def add(self, item: EvidenceItem) -> None:
        if not isinstance(item, EvidenceItem):
            logger.warning("add expected EvidenceItem")
            return
        self._items.append(item)

    def list(self) -> list[EvidenceItem]:
        return list(self._items)
