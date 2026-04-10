from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["CurriculumPlan", "CurriculumGenerator"]


@dataclass(frozen=True)
class CurriculumPlan:
    topic: str
    lessons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class CurriculumGenerator:
    def generate(self, topic: str) -> CurriculumPlan | None:
        if not isinstance(topic, str) or not topic.strip():
            logger.warning("generate expected topic")
            return None
        lessons = ["overview", "core concepts", "practice"]
        return CurriculumPlan(topic=topic.strip(), lessons=lessons)
