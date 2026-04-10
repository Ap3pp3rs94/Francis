from __future__ import annotations

import logging
from typing import Any, Callable

from .limits import SandboxLimits

logger = logging.getLogger(__name__)

__all__ = ["SandboxRunner"]


class SandboxRunner:
    def __init__(self, limits: SandboxLimits | None = None) -> None:
        self.limits = limits or SandboxLimits()

    def run(self, handler: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if not callable(handler):
            logger.warning("run expected callable handler")
            return None
        try:
            return handler(*args, **kwargs)
        except Exception as exc:
            logger.error("Sandbox run failed: %s", exc)
            return None
