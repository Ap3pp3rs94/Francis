from __future__ import annotations

import logging
import statistics
import time
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

__all__ = [
    "SignalType",
    "SignalDiscoveryResult",
    "SignalDiscovery",
]


class SignalType(Enum):
    TREND = "trend"
    ANOMALY = "anomaly"
    PATTERN = "pattern"


@dataclass(frozen=True)
class SignalDiscoveryResult:
    timestamp: float
    signal_type: SignalType
    data_points: list[tuple[float, float]]
    metadata: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp,
            "signal_type": self.signal_type.value,
            "data_points": list(self.data_points),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SignalDiscoveryResult | None":
        try:
            return cls(
                timestamp=float(data["timestamp"]),
                signal_type=SignalType(data["signal_type"]),
                data_points=[tuple(point) for point in data["data_points"]],
                metadata=dict(data["metadata"]),
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.error("Invalid signal discovery payload: %s", exc)
            return None


class SignalDiscovery:
    def __init__(self, data: list[tuple[float, float]]):
        if not self._validate_data(data):
            logger.warning("Invalid data provided; using empty dataset")
            data = []
        self.data = data

    def _validate_data(self, data: list[tuple[float, float]]) -> bool:
        if not isinstance(data, list):
            return False
        for point in data:
            if not isinstance(point, tuple) or len(point) != 2:
                return False
            if not all(isinstance(x, (int, float)) for x in point):
                return False
        return True

    def detect_trend(self) -> SignalDiscoveryResult:
        xs = [p[0] for p in self.data]
        ys = [p[1] for p in self.data]
        if len(xs) < 2:
            return SignalDiscoveryResult(
                timestamp=time.time(),
                signal_type=SignalType.TREND,
                data_points=[],
                metadata={"error": "insufficient_points"},
            )

        mean_x = statistics.mean(xs)
        mean_y = statistics.mean(ys)
        denom = sum((x - mean_x) ** 2 for x in xs)
        slope = 0.0 if denom == 0 else sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom
        intercept = mean_y - slope * mean_x

        metadata = {"slope": str(slope), "intercept": str(intercept)}
        return SignalDiscoveryResult(
            timestamp=time.time(),
            signal_type=SignalType.TREND,
            data_points=self.data,
            metadata=metadata,
        )

    def detect_anomalies(self) -> SignalDiscoveryResult:
        ys = [p[1] for p in self.data]
        if len(ys) < 2:
            return SignalDiscoveryResult(
                timestamp=time.time(),
                signal_type=SignalType.ANOMALY,
                data_points=[],
                metadata={"error": "insufficient_points"},
            )

        mean_y = statistics.mean(ys)
        stdev = statistics.pstdev(ys)
        if stdev == 0:
            anomalies = []
        else:
            anomalies = [p for p in self.data if abs(p[1] - mean_y) > 3 * stdev]

        metadata = {"anomaly_count": str(len(anomalies))}
        return SignalDiscoveryResult(
            timestamp=time.time(),
            signal_type=SignalType.ANOMALY,
            data_points=anomalies,
            metadata=metadata,
        )

    def detect_patterns(self) -> SignalDiscoveryResult:
        pattern = self.data[:5]
        metadata = {"pattern_length": str(len(pattern))}
        return SignalDiscoveryResult(
            timestamp=time.time(),
            signal_type=SignalType.PATTERN,
            data_points=pattern,
            metadata=metadata,
        )
