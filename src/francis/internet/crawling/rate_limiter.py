from __future__ import annotations

import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["RateLimiter"]


@dataclass
class RateLimiter:
    min_interval_s: float = 1.0
    _last_time: float = 0.0

    def allow(self) -> bool:
        now = time.time()
        if now - self._last_time < self.min_interval_s:
            return False
        self._last_time = now
        return True
