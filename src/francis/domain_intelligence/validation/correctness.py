from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["CorrectnessCheck", "CorrectnessChecker"]


@dataclass(frozen=True)
class CorrectnessCheck:
    ok: bool
    reason: str


class CorrectnessChecker:
    def check(self, result: object) -> CorrectnessCheck:
        if result is None:
            return CorrectnessCheck(ok=False, reason="none")
        return CorrectnessCheck(ok=True, reason="ok")
