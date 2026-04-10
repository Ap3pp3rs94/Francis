from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["PluginLifecycle"]


@dataclass(frozen=True)
class PluginLifecycle:
    name: str

    def on_start(self) -> None:
        logger.info("Starting plugin: %s", self.name)

    def on_stop(self) -> None:
        logger.info("Stopping plugin: %s", self.name)
