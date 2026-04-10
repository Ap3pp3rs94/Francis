from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["IntegrationResult", "MultiSourceIntegrator"]


@dataclass(frozen=True)
class IntegrationResult:
    merged: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class MultiSourceIntegrator:
    def integrate(self, sources: list[dict[str, Any]]) -> IntegrationResult:
        if not isinstance(sources, list):
            logger.warning("integrate expected list sources")
            return IntegrationResult()
        merged: dict[str, Any] = {}
        for source in sources:
            if isinstance(source, dict):
                merged.update(source)
        return IntegrationResult(merged=merged)
