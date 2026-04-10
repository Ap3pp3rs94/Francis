from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ArtPrompt", "ArtGenerator"]


@dataclass(frozen=True)
class ArtPrompt:
    subject: str
    style: str = "abstract"
    metadata: dict[str, Any] = field(default_factory=dict)


class ArtGenerator:
    def generate(self, prompt: ArtPrompt) -> str:
        if not isinstance(prompt, ArtPrompt):
            logger.warning("generate expected ArtPrompt")
            return ""
        subject = prompt.subject.strip()
        style = prompt.style.strip()
        if not subject:
            return ""
        return f"{style} depiction of {subject}".strip()
