from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["SwarmCoordinator"]


@dataclass
class SwarmCoordinator:
    members: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def register(self, member_id: str) -> None:
        if not isinstance(member_id, str) or not member_id.strip():
            logger.warning("register expected non-empty member_id")
            return
        if member_id not in self.members:
            self.members.append(member_id)

    def list_members(self) -> list[str]:
        return list(self.members)
