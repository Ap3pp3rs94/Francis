from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["HandoffStep", "HandoffProtocol"]


@dataclass(frozen=True)
class HandoffStep:
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HandoffProtocol:
    steps: list[HandoffStep] = field(default_factory=list)
