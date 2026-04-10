from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["TutorResponse", "InteractiveTutor"]


@dataclass(frozen=True)
class TutorResponse:
    answer: str
    follow_ups: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class InteractiveTutor:
    def respond(self, question: str) -> TutorResponse | None:
        if not isinstance(question, str) or not question.strip():
            logger.warning("respond expected question")
            return None
        answer = f"Answer: {question.strip()}"
        return TutorResponse(answer=answer, follow_ups=["Want a worked example?"])
