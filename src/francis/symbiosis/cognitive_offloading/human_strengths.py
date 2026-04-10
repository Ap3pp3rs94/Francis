from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["HumanStrengthsProfile"]


@dataclass(frozen=True)
class HumanStrengthsProfile:
    strengths: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
