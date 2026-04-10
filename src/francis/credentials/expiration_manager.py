from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

__all__ = ["ExpirationStatus", "ExpirationManager"]


@dataclass(frozen=True)
class ExpirationStatus:
    expired: bool
    expires_at: datetime | None


class ExpirationManager:
    def __init__(self, default_ttl_s: int = 3600) -> None:
        self.default_ttl_s = max(1, int(default_ttl_s))

    def expires_at(self, issued_at: datetime | None = None) -> datetime:
        base = issued_at or datetime.utcnow()
        return base + timedelta(seconds=self.default_ttl_s)

    def check(self, expires_at: datetime | None) -> ExpirationStatus:
        if expires_at is None:
            return ExpirationStatus(expired=False, expires_at=None)
        return ExpirationStatus(expired=datetime.utcnow() >= expires_at, expires_at=expires_at)
