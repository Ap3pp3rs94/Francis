from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["InteractionModel", "InteractionModeler"]


@dataclass(frozen=True)
class InteractionModel:
    description: str
    participants: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class InteractionModeler:
    def model(self, participants: list[str]) -> InteractionModel | None:
        if not isinstance(participants, list) or not participants:
            logger.warning("model expected list participants")
            return None
        description = f"Interaction among {', '.join(participants)}"
        return InteractionModel(description=description, participants=list(participants))
