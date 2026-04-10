from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

__all__ = ["CrawlResult", "AcademicCrawler"]


@dataclass(frozen=True)
class CrawlResult:
    url: str
    ok: bool
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class AcademicCrawler:
    def __init__(self, rate_limiter: RateLimiter | None = None) -> None:
        self.rate_limiter = rate_limiter or RateLimiter()

    def crawl(self, url: str) -> CrawlResult:
        if not isinstance(url, str) or not url.strip():
            logger.warning("crawl expected url")
            return CrawlResult(url=str(url), ok=False)
        if not self.rate_limiter.allow():
            return CrawlResult(url=url, ok=False, metadata={"reason": "rate_limited"})
        return CrawlResult(url=url, ok=True, content="")
