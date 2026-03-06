from __future__ import annotations

from pathlib import Path

from .network import collect as network_collect


def collect(repo_root: Path) -> dict:
    network = network_collect()
    return {
        "api": {
            "url": "http://127.0.0.1:8000/health",
            "reachable": network.get("loopback_8000_reachable", False),
        },
        "workspace_exists": (repo_root / "workspace").exists(),
        "venv_exists": (repo_root / ".venv").exists(),
    }
