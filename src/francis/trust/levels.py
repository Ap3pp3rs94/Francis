from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir


def _state_path() -> Path:
    return data_dir() / "trust" / "levels" / "current_state.json"


def get_state() -> dict[str, Any]:
    state = _state_path()
    if not state.exists():
        return {"global_level": 0, "domain_levels": {}, "last_updated": None}
    try:
        return json.loads(state.read_text(encoding="utf-8"))
    except Exception:
        return {"global_level": 0, "domain_levels": {}, "last_updated": None}


def set_global_level(level: int) -> dict[str, Any]:
    s = get_state()
    s["global_level"] = int(level)
    s["last_updated"] = time.time()
    state = _state_path()
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    return s
