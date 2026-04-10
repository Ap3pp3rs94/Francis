from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from francis.kernel.feature_flags import list_flags
from francis.kernel.paths import data_dir, repo_root
from francis.kernel.services import services_status
from francis.kernel.stack import stack_status
from francis.trust.levels import get_state


def _count_json_entries(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return len([item for item in path.iterdir() if item.is_file()])
    except Exception:
        return 0


def _path_state(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
    }


def snapshot() -> dict[str, Any]:
    root = repo_root()
    data = data_dir()

    approvals_root = data / "approvals"
    tasks_root = data / "tasks"
    logs_root = data / "logs"
    plugins_root = root / "plugins" / "generated"

    return {
        "ok": True,
        "subsystem": "world_state",
        "generated_at": time.time(),
        "repo_root": str(root),
        "data_dir": str(data),
        "trust": get_state(),
        "stack": stack_status(),
        "services": services_status(),
        "feature_flags": list_flags(),
        "paths": {
            "data": _path_state(data),
            "logs": _path_state(logs_root),
            "tasks": _path_state(tasks_root),
            "approvals": _path_state(approvals_root),
            "plugins_generated": _path_state(plugins_root),
        },
        "counts": {
            "pending_approvals": _count_json_entries(approvals_root / "pending"),
            "approved_approvals": _count_json_entries(approvals_root / "approved"),
            "rejected_approvals": _count_json_entries(approvals_root / "rejected"),
            "tasks": _count_json_entries(tasks_root),
            "generated_plugins": _count_json_entries(plugins_root),
        },
    }
