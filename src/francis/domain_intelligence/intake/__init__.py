from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["DataSourceType", "DataIntakeRecord", "DataIntakeProcessor"]


class DataSourceType(Enum):
    API = "API"
    FILE = "FILE"
    DATABASE = "DATABASE"


@dataclass(frozen=True)
class DataIntakeRecord:
    source_id: str
    source_type: DataSourceType
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DataIntakeRecord | None":
        try:
            return cls(
                source_id=data["source_id"],
                source_type=DataSourceType(data["source_type"]),
                data=data["data"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
                metadata=data.get("metadata", {}),
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.error("Invalid data intake record payload: %s", exc)
            return None


class DataIntakeProcessor:
    def __init__(self) -> None:
        self.records: list[DataIntakeRecord] = []

    def ingest_data(
        self,
        source_id: str,
        source_type: DataSourceType,
        data: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> DataIntakeRecord | None:
        logger.debug("Ingesting data from %s (%s)", source_id, source_type)

        if not isinstance(source_id, str) or not source_id.strip():
            logger.warning("Source ID must be a non-empty string")
            return None
        if not isinstance(data, dict):
            logger.warning("Data must be a dictionary")
            return None

        record = DataIntakeRecord(
            source_id=source_id,
            source_type=source_type,
            data=data,
            metadata=metadata or {},
        )
        self.records.append(record)
        logger.info("Successfully ingested data from %s (%s)", source_id, source_type)
        return record

    def validate_data(self, data: dict[str, Any]) -> bool:
        required_keys = {"id", "value"}
        if not required_keys.issubset(data.keys()):
            logger.warning("Data missing required keys")
            return False
        if not isinstance(data["id"], int) or data["id"] <= 0:
            logger.warning("Invalid 'id' in data")
            return False
        if not isinstance(data["value"], (int, float)):
            logger.warning("Invalid 'value' type in data")
            return False
        return True

    def process_data(self) -> None:
        logger.debug("Processing all ingested data records")
        for record in self.records:
            if not self.validate_data(record.data):
                logger.warning("Invalid data found in record from %s", record.source_id)
                continue
            try:
                transformed_data = {"processed_value": record.data["value"] * 2}
            except Exception as exc:
                logger.error("Failed to process record from %s: %s", record.source_id, exc)
                continue
            logger.info("Processed data from %s: %s", record.source_id, transformed_data)
