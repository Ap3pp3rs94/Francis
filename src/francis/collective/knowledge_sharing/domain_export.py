from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["DomainExport"]


@dataclass
class DomainExport:
    domain: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"domain": self.domain, "payload": dict(self.payload or {})}

    def export(self) -> dict[str, Any]:
        if not self.domain:
            logger.warning("export requires domain")
            return {}
        return self.to_dict()
