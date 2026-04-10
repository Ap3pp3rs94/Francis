from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["DriftFinding", "SystemDriftDetector"]


@dataclass(frozen=True)
class DriftFinding:
    changed: bool
    changes: dict[str, Any] = field(default_factory=dict)


class SystemDriftDetector:
    def detect(self, baseline: dict[str, Any], current: dict[str, Any]) -> DriftFinding:
        if not isinstance(baseline, dict) or not isinstance(current, dict):
            logger.warning("detect expected baseline and current dict")
            return DriftFinding(changed=False, changes={})
        changes = {k: current.get(k) for k, v in baseline.items() if current.get(k) != v}
        return DriftFinding(changed=bool(changes), changes=changes)
