from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

__all__ = ["SafetyRule", "InternetSafetyModel"]


@dataclass(frozen=True)
class SafetyRule:
    description: str
    enabled: bool = True


@dataclass
class InternetSafetyModel:
    rules: list[SafetyRule] = field(default_factory=list)

    def allows(self, description: str) -> bool:
        if not description:
            return False
        for rule in self.rules:
            if rule.description == description:
                return rule.enabled
        return True
