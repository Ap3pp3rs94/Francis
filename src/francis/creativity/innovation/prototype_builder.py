from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["PrototypeSpec", "PrototypeBuilder"]


@dataclass(frozen=True)
class PrototypeSpec:
    name: str
    components: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class PrototypeBuilder:
    def build(self, spec: PrototypeSpec) -> dict[str, Any]:
        if not isinstance(spec, PrototypeSpec):
            logger.warning("build expected PrototypeSpec")
            return {}
        if not spec.name:
            return {}
        return {"name": spec.name, "components": list(spec.components)}
