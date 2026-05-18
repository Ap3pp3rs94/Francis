from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from importlib import import_module
from typing import Any
from urllib.parse import urlparse

aiohttp: Any
try:  # pragma: no cover - optional dependency
    aiohttp = import_module("aiohttp")
except Exception:  # pragma: no cover
    aiohttp = None

BeautifulSoup: Any
try:  # pragma: no cover - optional dependency
    BeautifulSoup = getattr(import_module("bs4"), "BeautifulSoup")
except Exception:  # pragma: no cover
    BeautifulSoup = None

logger = logging.getLogger(__name__)

__all__ = [
    "ContentType",
    "SafetyStatus",
    "SourceCredibility",
    "WebLearningResult",
    "KnowledgeFragment",
    "WebLearner",
    "WebLearningError",
    "BlockedContentError",
    "RateLimitError",
]


class WebLearningError(Exception):
    pass


class BlockedContentError(WebLearningError):
    pass


class RateLimitError(WebLearningError):
    pass


class ContentType(Enum):
    HTML = "html"
    TEXT = "text"
    OTHER = "other"


class SafetyStatus(Enum):
    SAFE = "safe"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class SourceCredibility(Enum):
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class KnowledgeFragment:
    source_url: str
    content: str
    extracted_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WebLearningResult:
    url: str
    status: SafetyStatus
    content_type: ContentType
    fragments: list[KnowledgeFragment] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class WebLearner:
    def __init__(self, user_agent: str = "FRANCIS/1.0", timeout_s: int = 20) -> None:
        self.user_agent = user_agent
        self.timeout_s = timeout_s

    async def fetch(self, url: str) -> tuple[str, ContentType]:
        if aiohttp is None:
            logger.warning("aiohttp is not available; web learning disabled")
            return "", ContentType.OTHER
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            logger.warning("url must be absolute: %s", url)
            return "", ContentType.OTHER

        headers = {"User-Agent": self.user_agent}
        timeout = aiohttp.ClientTimeout(total=self.timeout_s)
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(url) as resp:
                    if resp.status == 429:
                        logger.warning("rate limited for url: %s", url)
                        return "", ContentType.OTHER
                    resp.raise_for_status()
                    content_type = resp.headers.get("content-type", "").lower()
                    text = await resp.text()
        except Exception as exc:
            logger.error("Fetch failed for %s: %s", url, exc)
            return "", ContentType.OTHER

        if "text/html" in content_type:
            return text, ContentType.HTML
        if "text/plain" in content_type:
            return text, ContentType.TEXT
        return text, ContentType.OTHER

    def extract_text(self, html: str) -> str:
        if not html:
            return ""
        if BeautifulSoup is None:
            stripped = re.sub(r"<[^>]+>", " ", html)
            return " ".join(stripped.split())
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return " ".join(soup.stripped_strings)

    async def learn(self, url: str) -> WebLearningResult:
        raw, content_type = await self.fetch(url)
        if content_type == ContentType.HTML:
            text = self.extract_text(raw)
        else:
            text = raw

        fragment = KnowledgeFragment(source_url=url, content=text)
        return WebLearningResult(
            url=url,
            status=SafetyStatus.UNKNOWN,
            content_type=content_type,
            fragments=[fragment] if text else [],
            metadata={"empty": not bool(text)},
        )
