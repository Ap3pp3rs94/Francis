from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["HardwareProfile", "HardwareProfiler"]


@dataclass(frozen=True)
class HardwareProfile:
    cpu_cores: int
    memory_gb: float
    disk_gb: float


class HardwareProfiler:
    def profile(self, cpu_cores: int, memory_gb: float, disk_gb: float) -> HardwareProfile | None:
        try:
            cores = int(cpu_cores)
            mem = float(memory_gb)
            disk = float(disk_gb)
        except (TypeError, ValueError):
            logger.warning("profile expected numeric inputs")
            return None
        return HardwareProfile(cpu_cores=cores, memory_gb=mem, disk_gb=disk)
