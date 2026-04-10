from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["ScopeDecision", "ScopeChecker"]


@dataclass(frozen=True)
class ScopeDecision:
    allowed: bool
    reason: str


class ScopeChecker:
    def __init__(self, allowed_scopes: list[str] | None = None) -> None:
        self.allowed_scopes = set(allowed_scopes or [])

    def check(self, scopes: list[str]) -> ScopeDecision:
        if not isinstance(scopes, list):
            logger.warning("check expected list scopes")
            return ScopeDecision(False, "invalid_scopes")
        if not scopes:
            return ScopeDecision(False, "empty_scopes")
        if not self.allowed_scopes:
            return ScopeDecision(True, "no_policy")
        missing = [scope for scope in scopes if scope not in self.allowed_scopes]
        if missing:
            return ScopeDecision(False, "missing_scopes")
        return ScopeDecision(True, "ok")
