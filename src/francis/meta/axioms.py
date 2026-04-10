from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

__all__ = ["Axiom", "AxiomSet"]


@dataclass(frozen=True)
class Axiom:
    statement: str


@dataclass
class AxiomSet:
    axioms: list[Axiom] = field(default_factory=list)

    def add(self, axiom: Axiom) -> None:
        if not isinstance(axiom, Axiom):
            logger.warning("add expected Axiom")
            return
        self.axioms.append(axiom)
