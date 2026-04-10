from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["AdversarySystem", "DefenseManager", "initialize_adversary", "update_defenses"]


class AdversarySystem:
    def __init__(self, defense_manager: DefenseManager | None = None) -> None:
        self.defense_manager = defense_manager or DefenseManager()

    def analyze_threats(self, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            logger.warning("Threat analysis received non-dict input")
            return {"status": "error", "reason": "invalid_input"}

        indicators = [key for key, value in data.items() if value]
        return {
            "status": "ok",
            "indicator_count": len(indicators),
            "indicators": indicators,
        }

    def mitigate_risks(self, risks: list[dict[str, Any]]) -> dict[str, Any]:
        if not isinstance(risks, list):
            logger.warning("Risk mitigation received non-list input")
            return {"status": "error", "reason": "invalid_input"}

        mitigated = [{**risk, "mitigated": True} for risk in risks if isinstance(risk, dict)]
        return {
            "status": "ok",
            "mitigated": len(mitigated),
            "details": mitigated,
        }


class DefenseManager:
    def update_defenses(self, updates: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(updates, dict):
            logger.warning("Defense updates received non-dict input")
            return {"status": "error", "reason": "invalid_input"}

        keys = list(updates.keys())
        return {"status": "ok", "updated": len(keys), "keys": keys}


def initialize_adversary() -> AdversarySystem:
    """Create a ready-to-use adversarial defense system."""
    logger.info("Initializing adversarial system")
    return AdversarySystem()


def update_defenses(updates: dict[str, Any]) -> dict[str, Any]:
    """Apply defense updates through a default manager."""
    return DefenseManager().update_defenses(updates)
