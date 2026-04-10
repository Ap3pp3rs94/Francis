from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["CompatibilityReport", "BackwardCompatibility"]


@dataclass(frozen=True)
class CompatibilityReport:
    compatible: bool
    reason: str


class BackwardCompatibility:
    def check(self, old_version: str, new_version: str) -> CompatibilityReport:
        if not old_version or not new_version:
            logger.warning("check expected versions")
            return CompatibilityReport(compatible=False, reason="invalid_input")
        compatible = old_version.split(".")[0] == new_version.split(".")[0]
        return CompatibilityReport(compatible=compatible, reason="same_major" if compatible else "major_bump")
