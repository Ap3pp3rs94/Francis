from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["DomainSourceExport", "DomainSourceExporter"]


@dataclass(frozen=True)
class DomainSourceExport:
    domain: str
    payload: dict[str, Any]
    generated_at: datetime = field(default_factory=datetime.utcnow)


class DomainSourceExporter:
    def export(self, domain: str, signals: dict[str, Any]) -> DomainSourceExport | None:
        if not isinstance(domain, str) or not domain.strip():
            logger.warning("export expected domain")
            return None
        if not isinstance(signals, dict):
            logger.warning("export expected signals dict")
            signals = {}
        return DomainSourceExport(domain=domain.strip(), payload=dict(signals))
