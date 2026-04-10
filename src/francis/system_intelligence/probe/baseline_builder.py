from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["Baseline", "BaselineBuilder"]


@dataclass(frozen=True)
class Baseline:
    fingerprint: dict[str, Any] = field(default_factory=dict)
    captured_at: datetime = field(default_factory=datetime.utcnow)


class BaselineBuilder:
    def build(self, profile: dict[str, Any]) -> Baseline:
        if not isinstance(profile, dict):
            logger.warning("build expected profile dict")
            profile = {}
        return Baseline(fingerprint=dict(profile))
