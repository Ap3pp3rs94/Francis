from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["SandboxLimits"]


@dataclass(frozen=True)
class SandboxLimits:
    cpu_seconds: int = 5
    memory_mb: int = 256
    allow_network: bool = False
    max_payload_bytes: int = 65536
    allow_filesystem_write: bool = False
    allowed_paths: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cpu_seconds": self.cpu_seconds,
            "memory_mb": self.memory_mb,
            "allow_network": self.allow_network,
            "max_payload_bytes": self.max_payload_bytes,
            "allow_filesystem_write": self.allow_filesystem_write,
            "allowed_paths": list(self.allowed_paths),
        }
