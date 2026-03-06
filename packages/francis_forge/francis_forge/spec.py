from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    description: str
    rationale: str = ""
    tags: list[str] = field(default_factory=list)
    risk_tier: str = "low"

    @property
    def slug(self) -> str:
        return "".join(ch.lower() if ch.isalnum() else "-" for ch in self.name).strip("-") or "capability"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "rationale": self.rationale,
            "tags": self.tags,
            "risk_tier": self.risk_tier,
            "slug": self.slug,
        }
