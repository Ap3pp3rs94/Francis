from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["SimulationBinding", "SimulatorBinder"]


@dataclass(frozen=True)
class SimulationBinding:
    simulator: str
    config: dict[str, Any] = field(default_factory=dict)


class SimulatorBinder:
    def bind(self, simulator: str, config: dict[str, Any] | None = None) -> SimulationBinding | None:
        if not simulator:
            logger.warning("bind expected simulator")
            return None
        return SimulationBinding(simulator=simulator, config=config or {})
