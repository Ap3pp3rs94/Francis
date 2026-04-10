from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["AlignmentProof", "ValueAlignmentProver"]


@dataclass(frozen=True)
class AlignmentProof:
    aligned: bool
    rationale: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ValueAlignmentProver:
    def prove(self, decision: str, values: list[str]) -> AlignmentProof:
        if not decision or not isinstance(values, list):
            logger.warning("prove expected decision and values list")
            return AlignmentProof(aligned=False, rationale="invalid_input")
        aligned = bool(values)
        rationale = "aligned" if aligned else "no_values"
        return AlignmentProof(aligned=aligned, rationale=rationale)
