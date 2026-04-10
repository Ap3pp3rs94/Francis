from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["DomainRecord", "DomainRegistry"]


@dataclass(frozen=True)
class DomainRecord:
    domain_id: str
    name: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


class DomainRegistry:
    def __init__(self) -> None:
        self._records: dict[str, DomainRecord] = {}

    def register(self, domain_id: str, name: str, metadata: dict[str, Any] | None = None) -> DomainRecord | None:
        if not domain_id or not name:
            logger.warning("register requires domain_id and name")
            return None
        record = DomainRecord(domain_id=domain_id, name=name, metadata=metadata or {})
        self._records[domain_id] = record
        return record

    def get(self, domain_id: str) -> DomainRecord | None:
        return self._records.get(domain_id)
