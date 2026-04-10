from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["DifferentialSync"]


@dataclass
class DifferentialSync:
    last_revision: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def diff(self, local: dict[str, Any], remote: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(local, dict) or not isinstance(remote, dict):
            logger.warning("diff expected dict inputs")
            return {}
        changes = {k: v for k, v in local.items() if remote.get(k) != v}
        return changes

    def apply(self, base: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(base, dict) or not isinstance(changes, dict):
            logger.warning("apply expected dict inputs")
            return dict(base) if isinstance(base, dict) else {}
        merged = dict(base)
        merged.update(changes)
        return merged
