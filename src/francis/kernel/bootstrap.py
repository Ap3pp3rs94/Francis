from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

load_dotenv: Callable[..., bool] | None
try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None


def bootstrap() -> None:
    if load_dotenv is None:
        logger.warning("dotenv not available; skipping .env load")
        return
    load_dotenv()
