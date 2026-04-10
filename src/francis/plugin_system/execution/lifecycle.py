from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from francis.telemetry import audit
from francis.telemetry.tracing import current_context

logger = logging.getLogger(__name__)

__all__ = ["PluginLifecycle"]


@dataclass
class PluginLifecycle:
    name: str
    status: str = field(default="created", init=False)
    starts: int = field(default=0, init=False)
    stops: int = field(default=0, init=False)
    last_started_at: float | None = field(default=None, init=False)
    last_stopped_at: float | None = field(default=None, init=False)

    def on_start(self) -> None:
        self.starts += 1
        self.status = "running"
        self.last_started_at = time.time()
        context = current_context().as_dict()
        logger.info("Starting plugin: %s", self.name)
        audit.record("plugin.lifecycle.start", plugin_name=self.name, starts=self.starts, status=self.status, **context)

    def on_stop(self, *, reason: str = "") -> None:
        self.stops += 1
        self.status = "stopped"
        self.last_stopped_at = time.time()
        context = current_context().as_dict()
        logger.info("Stopping plugin: %s", self.name)
        audit.record(
            "plugin.lifecycle.stop",
            plugin_name=self.name,
            stops=self.stops,
            status=self.status,
            reason=reason,
            **context,
        )

    def snapshot(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "starts": self.starts,
            "stops": self.stops,
            "last_started_at": self.last_started_at,
            "last_stopped_at": self.last_stopped_at,
        }
