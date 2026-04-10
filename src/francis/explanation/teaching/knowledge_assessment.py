from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["AssessmentResult", "KnowledgeAssessment"]


@dataclass(frozen=True)
class AssessmentResult:
    score: float
    passed: bool


class KnowledgeAssessment:
    def assess(self, answers: list[bool]) -> AssessmentResult:
        if not isinstance(answers, list) or not answers:
            logger.warning("assess expected list answers")
            return AssessmentResult(score=0.0, passed=False)
        score = sum(1 for a in answers if a) / len(answers)
        return AssessmentResult(score=score, passed=score >= 0.7)
