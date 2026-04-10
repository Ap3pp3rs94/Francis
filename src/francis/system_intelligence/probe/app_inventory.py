from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["AppInventory", "AppProbe"]


@dataclass(frozen=True)
class AppInventory:
    apps: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AppProbe:
    def probe(self, installed: list[str]) -> AppInventory:
        if not isinstance(installed, list):
            logger.warning("probe expected list installed")
            return AppInventory(apps=[])
        apps = sorted({app for app in installed if app})
        return AppInventory(apps=apps)
