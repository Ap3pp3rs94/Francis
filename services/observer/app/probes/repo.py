from __future__ import annotations

import subprocess
from pathlib import Path


def _run_git(repo_root: Path, args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    return proc.returncode, (proc.stdout or "").strip()


def collect(repo_root: Path) -> dict:
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        return {"is_repo": False, "dirty_files": 0, "branch": None}

    rc_branch, branch = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    rc_status, status = _run_git(repo_root, ["status", "--porcelain"])
    dirty_files = len([line for line in status.splitlines() if line.strip()]) if rc_status == 0 else 0

    return {
        "is_repo": True,
        "branch": branch if rc_branch == 0 else None,
        "dirty_files": dirty_files,
    }
