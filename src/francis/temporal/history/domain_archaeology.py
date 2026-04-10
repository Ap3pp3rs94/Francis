from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["ArchaeologyResult", "DomainArchaeology"]


@dataclass(frozen=True)
class ArchaeologyResult:
    findings: list[str]


class DomainArchaeology:
    def excavate(self, domain: str) -> ArchaeologyResult | None:
        if not isinstance(domain, str) or not domain.strip():
            logger.warning("excavate expected domain")
            return None
        return ArchaeologyResult(findings=[f"History of {domain.strip()}"])
