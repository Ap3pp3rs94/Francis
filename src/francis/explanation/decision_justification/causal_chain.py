from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["CausalLink", "CausalChain"]


@dataclass(frozen=True)
class CausalLink:
    cause: str
    effect: str
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)


class CausalChain:
    def __init__(self) -> None:
        self._links: list[CausalLink] = []

    def add_link(self, link: CausalLink) -> None:
        if not isinstance(link, CausalLink):
            logger.warning("add_link expected CausalLink")
            return
        self._links.append(link)

    def explain(self) -> list[CausalLink]:
        return list(self._links)
