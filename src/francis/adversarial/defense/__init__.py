from __future__ import annotations

import logging

from .adversarial_training import AdversarialTraining
from .honeypot_generator import HoneypotGenerator
from .input_sanitizer import InputSanitizer
from .output_verifier import OutputVerifier

logger = logging.getLogger(__name__)

__all__ = [
    "AdversarialTraining",
    "HoneypotGenerator",
    "InputSanitizer",
    "OutputVerifier",
    "initialize_defense_mechanisms",
    "check_defense_mechanisms",
]


def initialize_defense_mechanisms() -> dict[str, bool]:
    """Initialize defense components and return a status map."""
    statuses: dict[str, bool] = {}
    for name, component in (
        ("adversarial_training", AdversarialTraining),
        ("honeypot_generator", HoneypotGenerator),
        ("input_sanitizer", InputSanitizer),
        ("output_verifier", OutputVerifier),
    ):
        try:
            component.initialize()
            statuses[name] = True
        except RuntimeError as exc:
            logger.error("Defense init failed for %s: %s", name, exc)
            statuses[name] = False
    return statuses


def check_defense_mechanisms() -> dict[str, bool]:
    """Return active status for each defense component."""
    results: dict[str, bool] = {}
    for name, component in (
        ("adversarial_training", AdversarialTraining),
        ("honeypot_generator", HoneypotGenerator),
        ("input_sanitizer", InputSanitizer),
        ("output_verifier", OutputVerifier),
    ):
        try:
            results[name] = bool(component.is_active())
        except RuntimeError as exc:
            logger.error("Defense status check failed for %s: %s", name, exc)
            results[name] = False
    return results
