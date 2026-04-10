from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ProvenanceType", "DataProvenance", "capture_provenance"]


class ProvenanceType(Enum):
    SOURCE = "SOURCE"
    TRANSFORMATION = "TRANSFORMATION"
    STORAGE = "STORAGE"


@dataclass(frozen=True)
class DataProvenance:
    data_id: uuid.UUID
    source: str
    type: ProvenanceType
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_id": str(self.data_id),
            "source": self.source,
            "type": self.type.value,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DataProvenance | None":
        try:
            return cls(
                data_id=uuid.UUID(data["data_id"]),
                source=data["source"],
                type=ProvenanceType(data["type"]),
                metadata=data.get("metadata", {}),
                timestamp=datetime.fromisoformat(data["timestamp"]),
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.error("Invalid provenance payload: %s", exc)
            return None

    @property
    def audit_trail(self) -> str:
        return f"{self.timestamp} - {self.type.value}: {self.source} ({self.data_id})"


def capture_provenance(
    data_id: uuid.UUID,
    source: str,
    type: ProvenanceType,
    metadata: dict[str, Any] | None = None,
) -> DataProvenance | None:
    if not isinstance(data_id, uuid.UUID):
        logger.error("Invalid data_id provided: %s", data_id)
        return None
    if not source:
        logger.error("Source cannot be empty.")
        return None

    provenance = DataProvenance(
        data_id=data_id,
        source=source,
        type=type,
        metadata=metadata or {},
    )
    logger.info("Captured provenance: %s", provenance.audit_trail)
    return provenance
