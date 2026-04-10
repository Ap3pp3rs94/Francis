from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ModelVersion", "ModelVersionRegistry"]


@dataclass(frozen=True)
class ModelVersion:
    version_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelVersionRegistry:
    def __init__(self) -> None:
        self._versions: dict[str, ModelVersion] = {}

    def register(self, version_id: str, metadata: dict[str, Any] | None = None) -> ModelVersion | None:
        if not version_id:
            logger.warning("register expected version_id")
            return None
        version = ModelVersion(version_id=version_id, metadata=metadata or {})
        self._versions[version_id] = version
        return version

    def get(self, version_id: str) -> ModelVersion | None:
        return self._versions.get(version_id)
