from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["ConflictResolution", "ConflictResolver"]


@dataclass(frozen=True)
class ConflictResolution:
    resolved: bool
    choice: str


class ConflictResolver:
    def resolve(self, options: list[str]) -> ConflictResolution:
        if not isinstance(options, list) or not options:
            logger.warning("resolve expected options list")
            return ConflictResolution(resolved=False, choice="")
        return ConflictResolution(resolved=True, choice=options[0])
