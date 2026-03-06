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


def load_or_init(fs: WorkspaceFS, rel_path: str = "observer/baselines.json") -> dict[str, Any]:
    try:
        raw = fs.read_text(rel_path)
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return {**DEFAULT_BASELINE, **parsed}
    except Exception:
        pass

    fs.write_text(rel_path, json.dumps(DEFAULT_BASELINE, ensure_ascii=False, indent=2))
    return dict(DEFAULT_BASELINE)
