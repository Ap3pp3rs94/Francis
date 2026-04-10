from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["BiasDisclosure", "BiasDisclosureEngine"]


@dataclass(frozen=True)
class BiasDisclosure:
    disclosure: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BiasDisclosureEngine:
    def disclose(self, model_name: str) -> BiasDisclosure | None:
        if not isinstance(model_name, str) or not model_name.strip():
            logger.warning("disclose expected model_name")
            return None
        disclosure = f"Bias disclosure for {model_name.strip()}."
        return BiasDisclosure(disclosure=disclosure)
