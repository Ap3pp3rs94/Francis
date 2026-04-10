from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["IntegrationReport", "IntegrationTester"]


@dataclass(frozen=True)
class IntegrationReport:
    ok: bool
    issues: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class IntegrationTester:
    def test(self, systems: list[str]) -> IntegrationReport:
        if not isinstance(systems, list) or not systems:
            logger.warning("test expected list of systems")
            return IntegrationReport(ok=False, issues=["no_systems"])
        return IntegrationReport(ok=True, issues=[])
