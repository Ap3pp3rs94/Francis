from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["DelegationGrant", "DelegationPolicy"]


@dataclass(frozen=True)
class DelegationGrant:
    grant_id: str
    issuer_id: str
    subject_id: str
    scopes: list[str] = field(default_factory=list)
    issued_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


class DelegationPolicy:
    def __init__(self, allowed_scopes: list[str] | None = None) -> None:
        self.allowed_scopes = set(allowed_scopes or [])

    def allow(self, grant: DelegationGrant) -> bool:
        if not isinstance(grant, DelegationGrant):
            logger.warning("allow expected DelegationGrant")
            return False
        if not grant.scopes:
            return False
        return all(scope in self.allowed_scopes for scope in grant.scopes) if self.allowed_scopes else True
