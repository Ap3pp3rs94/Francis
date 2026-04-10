from __future__ import annotations

import os
from pathlib import Path


def _find_repo_root(start: Path) -> Path | None:
    """Best-effort upward search for the repo root in a source checkout."""
    for p in (start, *start.parents):
        try:
            if (p / "pyproject.toml").is_file() and (p / "src" / "francis").is_dir():
                return p
            if (p / ".git").exists() and (p / "pyproject.toml").is_file():
                return p
        except OSError:
            continue
    return None


def repo_root() -> Path:
    """Return the Francis workspace root.

    Precedence:
    1) `FRANCIS_ROOT` env var (explicit override)
    2) upward search from CWD (works when running from inside the repo)
    3) upward search from this file (works in editable/source checkouts)
    4) CWD fallback
    """
    env = (os.getenv("FRANCIS_ROOT") or "").strip()
    if env:
        return Path(env).expanduser().resolve()

    cwd_root = _find_repo_root(Path.cwd().resolve())
    if cwd_root is not None:
        return cwd_root

    file_root = _find_repo_root(Path(__file__).resolve())
    if file_root is not None:
        return file_root

    return Path.cwd().resolve()


def data_dir() -> Path:
    env = (os.getenv("FRANCIS_DATA_DIR") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return repo_root() / "data"


def config_dir() -> Path:
    env = (os.getenv("FRANCIS_CONFIG_DIR") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return repo_root() / "config"
