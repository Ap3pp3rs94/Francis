from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["CredentialRule", "CredentialPolicy"]


@dataclass(frozen=True)
class CredentialRule:
    scope: str
    allowed: bool


class CredentialPolicy:
    def __init__(self, rules: list[CredentialRule] | None = None) -> None:
        self.rules = rules or []

    def allows(self, scope: str) -> bool:
        if not scope:
            return False
        for rule in self.rules:
            if rule.scope == scope:
                return rule.allowed
        return False
