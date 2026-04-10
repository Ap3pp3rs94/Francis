from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["CodeAnalysis", "CodeAnalyzer"]


@dataclass(frozen=True)
class CodeAnalysis:
    language: str
    issues: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class CodeAnalyzer:
    def analyze(self, code: str, language: str = "python") -> CodeAnalysis:
        if not isinstance(code, str):
            logger.warning("analyze expected code string")
            return CodeAnalysis(language=language, issues=["invalid_input"])
        return CodeAnalysis(language=language, issues=[])
