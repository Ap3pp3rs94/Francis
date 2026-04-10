from __future__ import annotations

from dataclasses import dataclass

__all__ = ["SandboxLimits"]


@dataclass(frozen=True)
class SandboxLimits:
    cpu_seconds: int = 5
    memory_mb: int = 256
    allow_network: bool = False
