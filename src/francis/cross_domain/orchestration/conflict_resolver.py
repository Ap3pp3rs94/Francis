from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ConflictResult", "ConflictResolver"]


@dataclass(frozen=True)
class ConflictResult:
    resolved: bool
    resolution: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ConflictResolver:
    def resolve(self, conflicts: list[str]) -> ConflictResult:
        if not isinstance(conflicts, list):
            logger.warning("resolve expected list conflicts")
            return ConflictResult(resolved=False, resolution="invalid_input")
        if not conflicts:
            return ConflictResult(resolved=True, resolution="none")
        return ConflictResult(resolved=True, resolution="first_wins", metadata={"conflict": conflicts[0]})
