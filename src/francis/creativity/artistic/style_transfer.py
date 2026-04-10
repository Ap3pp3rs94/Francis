from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["StyleTransferRequest", "StyleTransfer"]


@dataclass(frozen=True)
class StyleTransferRequest:
    content: str
    style: str
    metadata: dict[str, Any] = field(default_factory=dict)


class StyleTransfer:
    def apply(self, request: StyleTransferRequest) -> str:
        if not isinstance(request, StyleTransferRequest):
            logger.warning("apply expected StyleTransferRequest")
            return ""
        content = request.content.strip() if isinstance(request.content, str) else ""
        style = request.style.strip() if isinstance(request.style, str) else ""
        if not content or not style:
            return content
        return f"{content} ({style} style)"
