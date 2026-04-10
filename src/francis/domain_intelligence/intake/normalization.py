from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

try:  # pragma: no cover - optional dependency
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None

logger = logging.getLogger(__name__)

__all__ = ["NormalizationType", "DataMetadata", "DataNormalizer", "normalize_data"]


class NormalizationType(Enum):
    MIN_MAX = "min_max"
    Z_SCORE = "z_score"


@dataclass(frozen=True)
class DataMetadata:
    id: str
    timestamp: pd.Timestamp
    source: str


@dataclass
class DataNormalizer:
    data: pd.DataFrame
    metadata: DataMetadata

    def to_dict(self) -> dict[str, Any]:
        if pd is None:
            logger.warning("pandas is not available; cannot serialize DataNormalizer")
            return {"data": {}, "metadata": {}}
        return {
            "data": self.data.to_dict(),
            "metadata": {
                "id": self.metadata.id,
                "timestamp": self.metadata.timestamp.isoformat(),
                "source": self.metadata.source,
            },
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DataNormalizer | None":
        if pd is None:
            logger.warning("pandas is not available; cannot load DataNormalizer")
            return None
        try:
            meta = payload["metadata"]
            return cls(
                data=pd.DataFrame(payload["data"]),
                metadata=DataMetadata(
                    id=str(meta["id"]),
                    timestamp=pd.Timestamp(meta["timestamp"]),
                    source=str(meta["source"]),
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.error("Invalid normalization payload: %s", exc)
            return None

    @property
    def summary(self) -> pd.DataFrame:
        if pd is None:
            logger.warning("pandas is not available; no summary available")
            return None
        return self.data.describe()

    def normalize(self, method: NormalizationType = NormalizationType.MIN_MAX) -> None:
        if pd is None:
            logger.warning("pandas is not available; normalization skipped")
            return
        if method == NormalizationType.MIN_MAX:
            self._min_max_normalize()
            return
        if method == NormalizationType.Z_SCORE:
            self._z_score_normalize()
            return
        logger.warning("Unsupported normalization method: %s", method)

    def _min_max_normalize(self) -> None:
        for column in self.data.columns:
            if pd.api.types.is_numeric_dtype(self.data[column]):
                min_val = self.data[column].min()
                max_val = self.data[column].max()
                if max_val == min_val:
                    logger.warning("Skipping constant column: %s", column)
                    continue
                self.data[column] = (self.data[column] - min_val) / (max_val - min_val)
            else:
                logger.debug("Skipping non-numeric column: %s", column)

    def _z_score_normalize(self) -> None:
        for column in self.data.columns:
            if pd.api.types.is_numeric_dtype(self.data[column]):
                mean = self.data[column].mean()
                std = self.data[column].std()
                if std == 0 or pd.isna(std):
                    logger.warning("Skipping constant column: %s", column)
                    continue
                self.data[column] = (self.data[column] - mean) / std
            else:
                logger.debug("Skipping non-numeric column: %s", column)


def normalize_data(
    data: pd.DataFrame,
    metadata: DataMetadata,
    method: NormalizationType = NormalizationType.MIN_MAX,
) -> DataNormalizer | None:
    """Normalize a dataframe with the chosen method."""
    if pd is None:
        logger.warning("pandas is not available; normalization disabled")
        return None
    if not isinstance(data, pd.DataFrame):
        logger.warning("Input data must be a pandas DataFrame")
        return None

    normalizer = DataNormalizer(data=data.copy(), metadata=metadata)
    normalizer.normalize(method=method)
    return normalizer
