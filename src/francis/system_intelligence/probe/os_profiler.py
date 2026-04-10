from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["OSProfile", "OSProfiler"]


@dataclass(frozen=True)
class OSProfile:
    name: str
    version: str


class OSProfiler:
    def profile(self, name: str, version: str) -> OSProfile | None:
        if not name or not version:
            logger.warning("profile expected name and version")
            return None
        return OSProfile(name=name, version=version)
