from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

__all__ = ["PluginDispatcher"]


class PluginDispatcher:
    def dispatch(self, handler: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if not callable(handler):
            logger.warning("dispatch expected callable handler")
            return None
        try:
            return handler(*args, **kwargs)
        except Exception as exc:
            logger.error("Plugin dispatch failed: %s", exc)
            return None
