from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["EmergenceReport", "EmergenceValidator"]


@dataclass(frozen=True)
class EmergenceReport:
    emerged: bool
    signals: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class EmergenceValidator:
    def validate(self, signals: list[str]) -> EmergenceReport:
        if not isinstance(signals, list):
            logger.warning("validate expected list signals")
            return EmergenceReport(emerged=False, signals=[])
        emerged = any(bool(s) for s in signals)
        return EmergenceReport(emerged=emerged, signals=list(signals))
