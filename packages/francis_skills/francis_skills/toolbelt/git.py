from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .parsing import clamp_int, truncate_text


def _run_git(repo_root: Path, args: list[str], *, timeout_seconds: int = 20) -> dict[str, Any]:
    cmd = ["git", "-C", str(repo_root)] + args
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=max(1, timeout_seconds),
        check=False,
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "cmd": cmd,
    }


def repo_status(repo_root: Path, *, max_chars: int = 8000) -> dict[str, Any]:
    result = _run_git(repo_root, ["status", "--short", "--branch"])
    limit = clamp_int(max_chars, minimum=100, maximum=200000)
    result["stdout"] = truncate_text(str(result.get("stdout", "")), limit)
    result["stderr"] = truncate_text(str(result.get("stderr", "")), limit)
    return result


def repo_diff(repo_root: Path, *, path: str = "", max_chars: int = 12000) -> dict[str, Any]:
    args = ["diff", "--no-ext-diff", "--"]
    if path.strip():
        args.append(path.strip())
    result = _run_git(repo_root, args)
    limit = clamp_int(max_chars, minimum=100, maximum=200000)
    result["stdout"] = truncate_text(str(result.get("stdout", "")), limit)
    result["stderr"] = truncate_text(str(result.get("stderr", "")), limit)
    return result
