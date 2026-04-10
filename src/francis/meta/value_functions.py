from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)

__all__ = ["ValueFunction", "ValueFunctionSet"]


@dataclass(frozen=True)
class ValueFunction:
    name: str
    fn: Callable[[float], float]


@dataclass
class ValueFunctionSet:
    functions: list[ValueFunction] = field(default_factory=list)

    def evaluate(self, x: float) -> dict[str, float]:
        results: dict[str, float] = {}
        for vf in self.functions:
            try:
                results[vf.name] = float(vf.fn(x))
            except Exception as exc:
                logger.warning("value function %s failed: %s", vf.name, exc)
        return results
