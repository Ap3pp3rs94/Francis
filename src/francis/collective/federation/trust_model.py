from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["TrustScore", "TrustModel"]


@dataclass(frozen=True)
class TrustScore:
    value: float
    metadata: dict[str, Any] = field(default_factory=dict)


class TrustModel:
    def __init__(self, default: float = 0.5) -> None:
        self.default = float(default)
        self._scores: dict[str, TrustScore] = {}

    def set_score(self, instance_id: str, value: float, metadata: dict[str, Any] | None = None) -> None:
        if not instance_id:
            logger.warning("set_score expected instance_id")
            return
        self._scores[instance_id] = TrustScore(value=float(value), metadata=metadata or {})

    def get_score(self, instance_id: str) -> TrustScore:
        return self._scores.get(instance_id, TrustScore(value=self.default))
