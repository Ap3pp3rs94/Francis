from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ScopeDecision", "ScopeChecker"]


@dataclass(frozen=True)
class ScopeDecision:
    allowed: bool
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)


class ScopeChecker:
    def __init__(self, allowed_scopes: list[str] | None = None) -> None:
        self.allowed_scopes = set(allowed_scopes or [])

    def check(self, scopes: list[str]) -> ScopeDecision:
        if not isinstance(scopes, list):
            logger.warning("check expected list scopes")
            return ScopeDecision(
                False,
                "invalid_scopes",
                {
                    "requested_scope_count": 0,
                    "allowed_scope_count": len(self.allowed_scopes),
                },
            )
        if not scopes:
            return ScopeDecision(
                False,
                "empty_scopes",
                {
                    "requested_scope_count": 0,
                    "allowed_scope_count": len(self.allowed_scopes),
                },
            )
        evidence = {
            "requested_scope_count": len(scopes),
            "allowed_scope_count": len(self.allowed_scopes),
        }
        if not self.allowed_scopes:
            return ScopeDecision(True, "no_policy", evidence)
        missing = [scope for scope in scopes if scope not in self.allowed_scopes]
        if missing:
            return ScopeDecision(False, "missing_scopes", {**evidence, "missing_scope_count": len(missing)})
        return ScopeDecision(True, "ok", {**evidence, "missing_scope_count": 0})
