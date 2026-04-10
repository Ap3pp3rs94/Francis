from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["AuthorityModel", "AuthorityBuilder"]


@dataclass(frozen=True)
class AuthorityModel:
    authority_level: float
    evidence: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AuthorityBuilder:
    def build(self, evidence: list[str]) -> AuthorityModel:
        if not isinstance(evidence, list):
            logger.warning("build expected list evidence")
            return AuthorityModel(authority_level=0.0, evidence=[])
        score = min(1.0, len(evidence) / 10.0) if evidence else 0.0
        return AuthorityModel(authority_level=score, evidence=list(evidence))
