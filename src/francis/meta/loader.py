from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["MetaLoader"]


class MetaLoader:
    def load(self, path: Path) -> dict[str, Any]:
        if not isinstance(path, Path):
            logger.warning("load expected Path")
            return {}
        if not path.exists():
            logger.warning("meta file not found: %s", path)
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error("Failed to load meta file: %s", exc)
            return {}
