from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["AIStrengthsProfile"]


@dataclass(frozen=True)
class AIStrengthsProfile:
    strengths: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
