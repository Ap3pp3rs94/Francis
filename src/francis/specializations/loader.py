from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["SpecializationSpec", "SpecializationLoader"]


@dataclass(frozen=True)
class SpecializationSpec:
    name: str
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)


class SpecializationLoader:
    def load(self, path: Path) -> SpecializationSpec | None:
        if not isinstance(path, Path):
            logger.warning("load expected Path")
            return None
        if not path.exists():
            logger.warning("specialization not found: %s", path)
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            name = str(payload.get("name", "")).strip()
            description = str(payload.get("description", "")).strip()
            if not name:
                return None
            return SpecializationSpec(name=name, description=description, metadata=dict(payload.get("metadata") or {}))
        except Exception as exc:
            logger.error("Failed to load specialization: %s", exc)
            return None
