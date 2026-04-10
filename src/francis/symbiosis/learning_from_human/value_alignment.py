from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["AlignmentOutcome", "ValueAlignment"]


@dataclass(frozen=True)
class AlignmentOutcome:
    aligned: bool
    summary: str


class ValueAlignment:
    def align(self, values: list[str]) -> AlignmentOutcome:
        if not isinstance(values, list):
            logger.warning("align expected values list")
            return AlignmentOutcome(aligned=False, summary="invalid_input")
        aligned = bool(values)
        return AlignmentOutcome(aligned=aligned, summary="ok" if aligned else "no_values")
