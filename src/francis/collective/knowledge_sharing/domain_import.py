from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["DomainImport"]


@dataclass
class DomainImport:
    domain: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DomainImport | None":
        if not isinstance(data, dict):
            logger.warning("from_dict expected dict")
            return None
        return cls(domain=data.get("domain"), payload=dict(data.get("payload") or {}))

    def apply(self) -> bool:
        if not self.domain:
            logger.warning("apply requires domain")
            return False
        return True
