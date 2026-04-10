from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["DomainCombination", "DomainCombiner"]


@dataclass(frozen=True)
class DomainCombination:
    domains: list[str]
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)


class DomainCombiner:
    def combine(self, domains: list[str]) -> DomainCombination | None:
        if not isinstance(domains, list) or not domains:
            logger.warning("combine expected list of domains")
            return None
        summary = " + ".join(domains)
        return DomainCombination(domains=list(domains), summary=summary)
