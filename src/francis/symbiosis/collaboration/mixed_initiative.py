from __future__ import annotations

from dataclasses import dataclass

__all__ = ["MixedInitiativePolicy", "MixedInitiativeResult"]


@dataclass(frozen=True)
class MixedInitiativePolicy:
    allow_autonomy: bool = True


@dataclass(frozen=True)
class MixedInitiativeResult:
    allowed: bool
