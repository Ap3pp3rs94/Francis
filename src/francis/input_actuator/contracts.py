from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class InputActuatorError(ValueError):
    """Bounded input-actuator error."""


@dataclass(frozen=True)
class InputActionSpec:
    kind: str
    description: str
    requires_approval: bool = True


@dataclass
class InputActionResult:
    ok: bool
    status: str
    data: dict[str, Any] = field(default_factory=dict)
    governance: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": self.ok,
            "status": self.status,
            "data": self.data,
            "governance": self.governance,
        }
        if self.error:
            payload["error"] = self.error
        return payload
