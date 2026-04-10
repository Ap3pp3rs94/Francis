from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

from francis.kernel.feature_flags import list_flags
from francis.kernel.paths import config_dir, data_dir, repo_root


def _entry(name: str, path: Path, *, kind: str) -> dict[str, Any]:
    exists = path.exists()
    return {
        "name": name,
        "kind": kind,
        "path": str(path),
        "status": "ready" if exists else "missing",
        "exists": exists,
    }


def stack_summary() -> dict[str, object]:
    """Return a deterministic view of the local Francis runtime surfaces."""

    root = repo_root()
    items = [
        _entry("repo_root", root, kind="root"),
        _entry("source", root / "src" / "francis", kind="code"),
        _entry("config", config_dir(), kind="config"),
        _entry("data", data_dir(), kind="state"),
        _entry("api", root / "src" / "francis" / "api" / "app.py", kind="service"),
        _entry("daemon", root / "src" / "francis" / "daemon" / "runner.py", kind="service"),
        _entry("workers", root / "src" / "francis" / "workers" / "runner.py", kind="service"),
        _entry("chat_ui", root / "apps" / "chat_ui", kind="ui"),
        _entry("plugins", root / "plugins", kind="extensibility"),
    ]
    return {
        "generated_at": time.time(),
        "python_version": sys.version.split()[0],
        "stack": items,
    }


def stack_status(*, probe_runtime: bool = False) -> dict[str, object]:
    """Return a runtime-safe stack report without mutating the host."""

    summary = stack_summary()
    items = list(summary["stack"]) if isinstance(summary.get("stack"), list) else []
    ready = len([item for item in items if isinstance(item, dict) and item.get("status") == "ready"])
    missing = len([item for item in items if isinstance(item, dict) and item.get("status") == "missing"])

    return {
        "status": "ok" if missing == 0 else "degraded",
        "probe_runtime": probe_runtime,
        "generated_at": summary["generated_at"],
        "python_version": summary["python_version"],
        "counts": {
            "total": len(items),
            "ready": ready,
            "missing": missing,
            "feature_flags": len(list_flags()),
        },
        "items": items,
    }
