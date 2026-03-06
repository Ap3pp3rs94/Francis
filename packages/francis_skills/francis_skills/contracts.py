from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SkillSpec:
    name: str
    description: str
    risk_tier: str = "low"
    mutating: bool = False
    requires_approval: bool = False
    args_schema: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "risk_tier": self.risk_tier,
            "mutating": self.mutating,
            "requires_approval": self.requires_approval,
            "args_schema": dict(self.args_schema),
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class SkillCall:
    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillResult:
    ok: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    receipts: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "output": dict(self.output),
            "error": self.error,
            "receipts": dict(self.receipts),
        }
