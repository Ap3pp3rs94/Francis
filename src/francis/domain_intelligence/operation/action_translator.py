from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ActionTranslation", "ActionTranslator"]


@dataclass(frozen=True)
class ActionTranslation:
    intent: str
    action: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ActionTranslator:
    def translate(self, intent: str) -> ActionTranslation | None:
        if not isinstance(intent, str) or not intent.strip():
            logger.warning("translate expected intent")
            return None
        action = f"execute:{intent.strip()}"
        return ActionTranslation(intent=intent.strip(), action=action)
