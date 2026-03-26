from __future__ import annotations

import json
from typing import Any

from francis_core.workspace_fs import WorkspaceFS


DEFAULT_BASELINE: dict[str, Any] = {
    "disk_free_percent_min": 10.0,
    "memory_available_percent_min": 10.0,
    "repo_dirty_files_warn": 200,
    "cpu_normalized_load_warn": 90.0,
}

BASELINE_LIMITS: dict[str, tuple[float, float]] = {
    "disk_free_percent_min": (0.0, 50.0),
    "memory_available_percent_min": (0.0, 50.0),
    "repo_dirty_files_warn": (1.0, 100000.0),
    "cpu_normalized_load_warn": (1.0, 100.0),
}


def _coerce_baseline_value(key: str, value: Any) -> Any:
    default = DEFAULT_BASELINE[key]
    lower, upper = BASELINE_LIMITS[key]
    try:
        numeric = float(value)
    except Exception:
        return default
    if not lower <= numeric <= upper:
        return default
    if isinstance(default, int):
        return int(round(numeric))
    return float(numeric)


def normalize(parsed: dict[str, Any]) -> dict[str, Any]:
    normalized = {**parsed}
    for key, default in DEFAULT_BASELINE.items():
        if key not in normalized:
            normalized[key] = default
            continue
        normalized[key] = _coerce_baseline_value(key, normalized[key])
    return normalized


def load_or_init(fs: WorkspaceFS, rel_path: str = "observer/baselines.json") -> dict[str, Any]:
    try:
        raw = fs.read_text(rel_path)
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            normalized = normalize(parsed)
            if normalized != parsed:
                fs.write_text(rel_path, json.dumps(normalized, ensure_ascii=False, indent=2))
            return normalized
    except Exception:
        pass

    fs.write_text(rel_path, json.dumps(DEFAULT_BASELINE, ensure_ascii=False, indent=2))
    return dict(DEFAULT_BASELINE)
