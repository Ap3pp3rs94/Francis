from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["RedactionType", "RedactedData", "BaseRedactor", "PIIRedactor", "FinancialRedactor"]


class RedactionType(Enum):
    PII = "pii"
    FINANCIAL = "financial"
    CUSTOM = "custom"


@dataclass(frozen=True)
class RedactedData:
    attachment_id: str
    content_type: RedactionType
    data: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "attachment_id": self.attachment_id,
            "content_type": self.content_type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RedactedData":
        return cls(
            attachment_id=payload["attachment_id"],
            content_type=RedactionType(payload["content_type"]),
            data=payload["data"],
            timestamp=datetime.fromisoformat(payload["timestamp"]),
            metadata=payload.get("metadata", {}),
        )


class BaseRedactor:
    def __init__(self, attachment_id: str, content_type: RedactionType) -> None:
        self.attachment_id = attachment_id
        self.content_type = content_type
        self._patterns: dict[str, re.Pattern[str]] = {}

    def redact(self, content: str | bytes) -> RedactedData:
        text, metadata = self._decode_content(content)
        redacted, matches = self._apply_patterns(text)
        if matches:
            metadata["matches"] = matches
        return RedactedData(
            attachment_id=self.attachment_id,
            content_type=self.content_type,
            data=redacted,
            metadata=metadata,
        )

    def _decode_content(self, content: str | bytes) -> tuple[str, dict[str, Any]]:
        if isinstance(content, str):
            return content, {}
        try:
            return content.decode("utf-8"), {}
        except UnicodeDecodeError as exc:
            logger.error("Failed to decode content for attachment %s: %s", self.attachment_id, exc)
            return "", {"error": "invalid_utf8"}

    def _apply_patterns(self, content: str) -> tuple[str, int]:
        redacted_content = content
        matches = 0
        for key, pattern in self._patterns.items():
            count = len(pattern.findall(content))
            if count:
                redacted_content = pattern.sub(f"[REDACTED_{key.upper()}]", redacted_content)
                matches += count
        return redacted_content, matches


class PIIRedactor(BaseRedactor):
    def __init__(self, attachment_id: str) -> None:
        super().__init__(attachment_id, RedactionType.PII)
        self._patterns = {
            "phone": re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"),
            "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"),
        }


class FinancialRedactor(BaseRedactor):
    def __init__(self, attachment_id: str) -> None:
        super().__init__(attachment_id, RedactionType.FINANCIAL)
        self._patterns = {"credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b")}
