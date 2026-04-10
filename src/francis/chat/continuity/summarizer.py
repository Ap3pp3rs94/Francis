from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["Summarizer", "SummarizerConfig", "SummaryResult", "SummarizationMethod", "SummaryMetadata"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SummarizationMethod(Enum):
    EXTRACTIVE = "extractive"
    ABSTRACTIVE = "abstractive"


@dataclass(frozen=True, slots=True)
class SummaryMetadata:
    summary_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True, slots=True)
class SummarizerConfig:
    method: SummarizationMethod = SummarizationMethod.EXTRACTIVE
    max_length: int = 150


@dataclass(frozen=True, slots=True)
class SummaryResult:
    original_text: str
    summary: str
    metadata: SummaryMetadata

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_text": self.original_text,
            "summary": self.summary,
            "metadata": {
                "summary_id": self.metadata.summary_id,
                "timestamp": self.metadata.timestamp.isoformat(),
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SummaryResult":
        md = data["metadata"]
        metadata = SummaryMetadata(
            summary_id=str(md["summary_id"]),
            timestamp=datetime.fromisoformat(str(md["timestamp"])),
        )
        return cls(
            original_text=str(data["original_text"]),
            summary=str(data["summary"]),
            metadata=metadata,
        )


class Summarizer:
    def __init__(self, config: SummarizerConfig | None = None) -> None:
        if config is not None and not isinstance(config, SummarizerConfig):
            logger.warning("Invalid config provided; using defaults")
            config = None
        self.config = config or SummarizerConfig()
        logger.info("Summarizer initialized with method=%s max_length=%s", self.config.method, self.config.max_length)

    def summarize(self, text: str) -> SummaryResult:
        if not isinstance(text, str):
            logger.warning("summarize received non-string input")
            text = str(text)
        if not text.strip():
            return SummaryResult(original_text=text, summary="", metadata=SummaryMetadata())

        summary = self._perform_summarization(text) or ""
        result = SummaryResult(original_text=text, summary=summary, metadata=SummaryMetadata())
        logger.debug("Generated summary id=%s", result.metadata.summary_id)
        return result

    def _perform_summarization(self, text: str) -> str:
        if self.config.method == SummarizationMethod.EXTRACTIVE:
            return self._extractive_summary(text)
        if self.config.method == SummarizationMethod.ABSTRACTIVE:
            return self._abstractive_summary(text)
        logger.warning("Unsupported summarization method: %s", self.config.method)
        return self._extractive_summary(text)

    def _extractive_summary(self, text: str) -> str:
        parts = [p.strip() for p in text.replace("\n", " ").split(".") if p.strip()]
        if len(parts) <= 3:
            return text.strip()
        return ". ".join(parts[:3]) + "."

    def _abstractive_summary(self, text: str) -> str:
        words = text.split()
        if not words:
            return ""
        max_words = max(5, min(len(words), self.config.max_length // 5))
        out = " ".join(words[:max_words])
        if len(words) > max_words:
            out += "..."
        return out
