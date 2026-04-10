from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["PreferenceModel", "PreferenceLearner"]


@dataclass(frozen=True)
class PreferenceModel:
    preference: str


class PreferenceLearner:
    def learn(self, preference: str) -> PreferenceModel | None:
        if not isinstance(preference, str) or not preference.strip():
            logger.warning("learn expected preference")
            return None
        return PreferenceModel(preference=preference.strip())
