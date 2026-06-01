from __future__ import annotations

import logging
from collections.abc import Callable

from francis.kernel.paths import repo_root

logger = logging.getLogger(__name__)

load_dotenv: Callable[..., bool] | None
try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None


def bootstrap() -> bool:
    if load_dotenv is None:
        logger.warning("dotenv not available; skipping .env load")
        return False
    env_path = repo_root() / ".env"
    if not env_path.is_file():
        return False
    return bool(load_dotenv(dotenv_path=env_path, override=False))
