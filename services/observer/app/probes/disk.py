from __future__ import annotations

import shutil
from pathlib import Path


def collect(workspace_root: Path) -> dict:
    usage = shutil.disk_usage(workspace_root)
    total = int(usage.total)
    free = int(usage.free)
    used = int(usage.used)
    free_percent = (free / total * 100.0) if total else 0.0
    used_percent = (used / total * 100.0) if total else 0.0
    return {
        "path": str(workspace_root),
        "total_bytes": total,
        "used_bytes": used,
        "free_bytes": free,
        "used_percent": round(used_percent, 2),
        "free_percent": round(free_percent, 2),
    }
