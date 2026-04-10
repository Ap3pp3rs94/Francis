from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["AuditEntry", "AuditTrail"]


@dataclass(frozen=True)
class AuditEntry:
    action: str
    actor: str
    recorded_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


class AuditTrail:
    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def record(self, entry: AuditEntry) -> None:
        if not isinstance(entry, AuditEntry):
            logger.warning("record expected AuditEntry")
            return
        self._entries.append(entry)

    def recent(self, limit: int = 50) -> list[AuditEntry]:
        if not isinstance(limit, int) or limit <= 0:
            return []
        return list(self._entries[-limit:])
