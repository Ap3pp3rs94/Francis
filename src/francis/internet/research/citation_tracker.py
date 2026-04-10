from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["CitationEntry", "CitationTracker"]


@dataclass(frozen=True)
class CitationEntry:
    source: str
    title: str
    url: str
    metadata: dict[str, Any] = field(default_factory=dict)


class CitationTracker:
    def __init__(self) -> None:
        self._entries: list[CitationEntry] = []

    def add(self, entry: CitationEntry) -> None:
        if not isinstance(entry, CitationEntry):
            logger.warning("add expected CitationEntry")
            return
        self._entries.append(entry)

    def list(self) -> list[CitationEntry]:
        return list(self._entries)
