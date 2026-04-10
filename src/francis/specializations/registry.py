from __future__ import annotations

import logging

from .loader import SpecializationSpec

logger = logging.getLogger(__name__)

__all__ = ["SpecializationRegistry"]


class SpecializationRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, SpecializationSpec] = {}

    def register(self, spec: SpecializationSpec) -> None:
        if not isinstance(spec, SpecializationSpec):
            logger.warning("register expected SpecializationSpec")
            return
        self._specs[spec.name] = spec

    def get(self, name: str) -> SpecializationSpec | None:
        if not isinstance(name, str) or not name.strip():
            return None
        return self._specs.get(name)

    def list(self) -> list[str]:
        return sorted(self._specs.keys())
