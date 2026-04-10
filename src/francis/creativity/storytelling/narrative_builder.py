from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["NarrativeOutline", "NarrativeBuilder"]


@dataclass(frozen=True)
class NarrativeOutline:
    title: str
    beats: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class NarrativeBuilder:
    def build(self, title: str) -> NarrativeOutline | None:
        if not isinstance(title, str) or not title.strip():
            logger.warning("build expected non-empty title")
            return None
        beats = ["setup", "conflict", "resolution"]
        return NarrativeOutline(title=title.strip(), beats=beats)
