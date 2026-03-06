from __future__ import annotations

from dataclasses import replace

from .contracts import SkillSpec


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, SkillSpec] = {}

    def register(self, name: str, meta: dict) -> None:
        if not isinstance(meta, dict):
            raise TypeError("meta must be a dictionary")
        spec = SkillSpec(
            name=name,
            description=str(meta.get("description", meta.get("kind", ""))),
            risk_tier=str(meta.get("risk_tier", "low")),
            mutating=bool(meta.get("mutating", False)),
            requires_approval=bool(meta.get("requires_approval", False)),
            args_schema=dict(meta.get("args_schema", {})) if isinstance(meta.get("args_schema"), dict) else {},
            tags=[str(tag) for tag in meta.get("tags", []) if isinstance(tag, str)],
        )
        self.register_spec(spec)

    def register_spec(self, spec: SkillSpec) -> None:
        if not isinstance(spec, SkillSpec):
            raise TypeError("spec must be SkillSpec")
        normalized_name = spec.name.strip()
        if not normalized_name:
            raise ValueError("skill name cannot be empty")
        if normalized_name != spec.name:
            spec = replace(spec, name=normalized_name)
        self._skills[spec.name] = spec

    def unregister(self, name: str) -> None:
        self._skills.pop(name, None)

    def has(self, name: str) -> bool:
        return name in self._skills

    def get(self, name: str) -> SkillSpec | None:
        return self._skills.get(name)

    def require(self, name: str) -> SkillSpec:
        spec = self.get(name)
        if spec is None:
            raise KeyError(f"Unknown skill: {name}")
        return spec

    def list(self) -> list[str]:
        return sorted(self._skills.keys())

    def list_specs(self) -> list[SkillSpec]:
        return [self._skills[name] for name in self.list()]
