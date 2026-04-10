from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

try:  # pragma: no cover - optional dependency
    import numpy as np
except Exception:  # pragma: no cover
    np = None

logger = logging.getLogger(__name__)

__all__ = [
    "ActiveLearningStrategy",
    "SampleEfficiencyOptimizer",
    "UncertaintyType",
    "Sample",
]


class UncertaintyType(Enum):
    ENTROPY = "entropy"
    VARIANCE = "variance"


class ActiveLearningStrategy(Enum):
    UNCERTAINTY_SAMPLING = "uncertainty_sampling"
    QUERY_BY_COMMITTEE = "query_by_committee"


@dataclass(frozen=True)
class Sample:
    id: str
    features: np.ndarray
    label: Any = None
    timestamp: float = field(default_factory=time.time)


def _validate_features(features: np.ndarray) -> bool:
    if np is None:
        logger.warning("numpy is not available; sample efficiency disabled")
        return False
    if not isinstance(features, np.ndarray):
        logger.warning("Features must be a numpy array, got %s", type(features))
        return False
    if features.ndim != 2:
        logger.warning("Features must be a 2D array, got shape %s", getattr(features, "shape", None))
        return False
    return True


def _validate_labels(labels: list[Any]) -> bool:
    if not isinstance(labels, list):
        logger.warning("Labels must be a list, got %s", type(labels))
        return False
    return True


@dataclass
class SampleEfficiencyOptimizer:
    model: Any
    strategy: ActiveLearningStrategy = ActiveLearningStrategy.UNCERTAINTY_SAMPLING
    uncertainty_type: UncertaintyType = UncertaintyType.ENTROPY

    def __post_init__(self) -> None:
        if not hasattr(self.model, "predict_proba"):
            logger.warning("Model must have a predict_proba method")

    @property
    def strategy_name(self) -> str:
        return self.strategy.value

    @property
    def uncertainty_measure(self) -> str:
        return self.uncertainty_type.value

    def to_dict(self) -> dict[str, Any]:
        return {"strategy": self.strategy_name, "uncertainty_type": self.uncertainty_measure}

    @classmethod
    def from_dict(cls, config: dict[str, Any], model: Any) -> "SampleEfficiencyOptimizer | None":
        try:
            strategy = ActiveLearningStrategy(config["strategy"])
            uncertainty_type = UncertaintyType(config["uncertainty_type"])
            return cls(model=model, strategy=strategy, uncertainty_type=uncertainty_type)
        except (KeyError, ValueError, TypeError) as exc:
            logger.error("Invalid sample efficiency config: %s", exc)
            return None

    def _calculate_entropy(self, probabilities: np.ndarray) -> np.ndarray:
        logger.debug("Calculating entropy")
        return -np.sum(probabilities * np.log2(probabilities + 1e-9), axis=1)

    def _calculate_variance(self, predictions: list[np.ndarray]) -> np.ndarray:
        logger.debug("Calculating variance")
        mean_predictions = np.mean(predictions, axis=0)
        squared_diffs = [(pred - mean_predictions) ** 2 for pred in predictions]
        return np.mean(squared_diffs, axis=0)

    def select_samples(self, samples: list[Sample], n_to_select: int) -> list[str]:
        logger.info("Selecting %s samples using %s", n_to_select, self.strategy_name)
        if np is None:
            logger.warning("numpy is not available; cannot select samples")
            return []
        if not isinstance(samples, list):
            logger.warning("Samples must be a list, got %s", type(samples))
            return []
        if n_to_select <= 0:
            logger.warning("Number of samples to select must be positive")
            return []

        features = np.array([sample.features for sample in samples])
        if not _validate_features(features):
            return []

        if self.strategy == ActiveLearningStrategy.UNCERTAINTY_SAMPLING:
            try:
                probabilities = self.model.predict_proba(features)
            except Exception as exc:
                logger.error("predict_proba failed: %s", exc)
                return []
            if self.uncertainty_type == UncertaintyType.ENTROPY:
                uncertainty_scores = self._calculate_entropy(probabilities)
            elif self.uncertainty_type == UncertaintyType.VARIANCE:
                logger.warning("Variance is not applicable for single model predictions")
                return []
        elif self.strategy == ActiveLearningStrategy.QUERY_BY_COMMITTEE:
            if not hasattr(self.model, "models"):
                logger.warning("Model must have a 'models' attribute for query by committee")
                return []
            try:
                predictions = [model.predict_proba(features) for model in self.model.models]
            except Exception as exc:
                logger.error("Committee predict_proba failed: %s", exc)
                return []
            if self.uncertainty_type == UncertaintyType.VARIANCE:
                uncertainty_scores = self._calculate_variance(predictions)
            elif self.uncertainty_type == UncertaintyType.ENTROPY:
                logger.warning("Entropy is not applicable for ensemble predictions")
                return []
        else:
            logger.warning("Unknown strategy: %s", self.strategy)
            return []

        selected_indices = np.argsort(uncertainty_scores)[-n_to_select:]
        selected_sample_ids = [samples[i].id for i in selected_indices]
        logger.info("Selected samples with IDs: %s", selected_sample_ids)
        return selected_sample_ids
