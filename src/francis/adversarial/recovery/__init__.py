from __future__ import annotations

import logging

from .compromise_detector import CompromiseDetector, CompromiseDetectorPolicy, CompromiseFinding
from .containment import ContainmentPlan, ContainmentPlanner
from .forensics import ForensicsReport, ForensicsRunner
from .restoration import RestorationPlan, RestorationRunner

logger = logging.getLogger(__name__)

__all__ = [
    "CompromiseDetector",
    "CompromiseDetectorPolicy",
    "CompromiseFinding",
    "ContainmentPlan",
    "ContainmentPlanner",
    "ForensicsReport",
    "ForensicsRunner",
    "RestorationPlan",
    "RestorationRunner",
    "recovery_module_metadata",
]


def recovery_module_metadata() -> dict[str, str | list[str]]:
    """Return metadata about recovery capabilities."""
    return {
        "module": "francis.adversarial.recovery",
        "purpose": "Local compromise detection, containment guidance, and restoration planning.",
        "boundaries": ["no external network access", "local-only analysis"],
    }
