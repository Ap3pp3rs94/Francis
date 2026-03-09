from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .parsing import clamp_int, truncate_text


def _run(cmd: list[str], *, cwd: Path, timeout_seconds: int = 120, max_chars: int = 20000) -> dict[str, Any]:
    started = time.monotonic()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=max(1, timeout_seconds),
        check=False,
    )
    duration_ms = int((time.monotonic() - started) * 1000)
    cap = clamp_int(max_chars, minimum=100, maximum=500000)
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "duration_ms": duration_ms,
        "stdout": truncate_text(proc.stdout, cap),
        "stderr": truncate_text(proc.stderr, cap),
        "cmd": cmd,
    }


def run_pytest(
    repo_root: Path,
    *,
    lane: str = "full",
    target: str = "",
    max_failures: int = 1,
    quiet: bool = True,
    timeout_seconds: int = 600,
) -> dict[str, Any]:
    cmd = [sys.executable, "-m", "pytest"]
    if quiet:
        cmd.append("-q")
    if max_failures > 0:
        cmd.append(f"--maxfail={max_failures}")
    normalized_lane = str(lane).strip().lower() or "full"
    if normalized_lane == "fast":
        cmd.extend(["-m", "not slow and not redteam and not evals"])
    elif normalized_lane == "integration":
        cmd.extend(["-m", "integration and not slow"])
    elif normalized_lane == "redteam":
        cmd.extend(["-m", "redteam"])
    elif normalized_lane == "evals":
        cmd.extend(["-m", "evals"])
    if target.strip():
        cmd.append(target.strip())
    return _run(cmd, cwd=repo_root, timeout_seconds=timeout_seconds)


def run_ruff(repo_root: Path, *, target: str = ".", timeout_seconds: int = 300) -> dict[str, Any]:
    cmd = [sys.executable, "-m", "ruff", "check", target.strip() or "."]
    return _run(cmd, cwd=repo_root, timeout_seconds=timeout_seconds)
