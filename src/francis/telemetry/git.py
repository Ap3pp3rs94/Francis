from __future__ import annotations

import subprocess
import time
import logging
from pathlib import Path
from typing import Any

from francis.kernel.paths import repo_root
from francis.telemetry.status import STAGE7_TELEMETRY_STAGE, redact_telemetry_value

GIT_STATUS_KIND = "francis.stage7.telemetry.git_status"
_INTERNAL_API_ERROR = "internal_api_error"
_LOG = logging.getLogger("francis.telemetry.git")
_GIT_TIMEOUT_SECONDS = 5
_GIT_STATUS_ARGS = ["status", "--porcelain=v1", "-b", "--untracked-files=no"]
_MAX_CHANGED_PATHS = 50


def git_status_snapshot(*, cwd: Any = None, limit: int = _MAX_CHANGED_PATHS) -> dict[str, Any]:
    root = _repo_root(cwd)
    safe_limit = _safe_limit(limit)
    base = {
        "ok": True,
        "kind": GIT_STATUS_KIND,
        "stage": STAGE7_TELEMETRY_STAGE,
        "source_id": "git",
        "capture_mode": "explicit_git_status_snapshot",
        "watch_mode": "on_request_snapshot",
        "hidden_sensing": False,
        "visible_indicator": True,
        "untracked_files_included": False,
        "status_scope": "tracked_changes_only",
        "redacted": True,
        "stores_raw_events": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "ts": _now_s(),
        "root": _redact_text(root),
        "limit": safe_limit,
    }

    status = _git(_GIT_STATUS_ARGS, cwd=root)
    if not status["ok"]:
        return {
            **base,
            "status": "unavailable",
            "active": False,
            "error": status["error"],
            "branch": "",
            "head": "",
            "upstream": "",
            "ahead": 0,
            "behind": 0,
            "dirty": False,
            "changed_count": 0,
            "changed_paths": [],
            "governance": _governance(),
            "next_smallest_truthful_gap": "stage7_git_watcher_background_policy",
        }

    branch_line, changed_count, changed_paths = _parse_status(status["stdout"], limit=safe_limit)
    branch_info = _parse_branch_line(branch_line)
    head = _git_text(["rev-parse", "--verify", "HEAD"], cwd=root)
    top_level = _git_text(["rev-parse", "--show-toplevel"], cwd=root)
    dirty = changed_count > 0

    return {
        **base,
        "status": "snapshot_ready",
        "active": True,
        "root": _redact_text(top_level or root),
        "branch": branch_info["branch"],
        "head": (head or "")[:12],
        "upstream": branch_info["upstream"],
        "ahead": branch_info["ahead"],
        "behind": branch_info["behind"],
        "dirty": dirty,
        "changed_count": changed_count,
        "changed_paths": changed_paths,
        "governance": _governance(),
        "next_smallest_truthful_gap": "stage7_git_watcher_background_policy",
    }


def git_source_snapshot() -> dict[str, Any]:
    snapshot = git_status_snapshot()
    active = bool(snapshot.get("active"))
    changed_count = _safe_int(snapshot.get("changed_count"), 0)
    signals = ["branch", "dirty_state", "changed_paths", "remote_alignment"] if active else []
    return {
        "status": "snapshot_ready" if active else "unavailable",
        "active": active,
        "blocked_by": [] if active else ["git_status_unavailable"],
        "signals": signals,
        "retention": {
            "status": "read_only_snapshot" if active else "none",
            "stores_raw_events": False,
            "event_count": 0,
        },
        "scope": {
            "status": "repo_root_only" if active else "not_granted",
            "allowed_paths": [snapshot["root"]] if active else [],
            "allowed_processes": ["git status --untracked-files=no", "git rev-parse"] if active else [],
            "denied_by_default": True,
        },
        "latest_snapshot": {
            "branch": snapshot.get("branch", ""),
            "head": snapshot.get("head", ""),
            "upstream": snapshot.get("upstream", ""),
            "ahead": snapshot.get("ahead", 0),
            "behind": snapshot.get("behind", 0),
            "dirty": snapshot.get("dirty", False),
            "changed_count": changed_count,
            "changed_paths": snapshot.get("changed_paths", []),
            "ts": snapshot.get("ts"),
        }
        if active
        else None,
        "routes": {
            "status": "/telemetry/git/status",
        },
    }


def _repo_root(cwd: Any) -> Path:
    text = _safe_str(cwd).strip()
    if not text:
        return repo_root()
    try:
        return Path(text).expanduser().resolve()
    except Exception:
        return repo_root()


def _git(args: list[str], *, cwd: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except Exception:
        _LOG.exception("Git telemetry snapshot command failed", exc_info=True)
        return {"ok": False, "stdout": "", "stderr": "", "error": _INTERNAL_API_ERROR}

    return {
        "ok": completed.returncode == 0,
        "stdout": _redact_text(completed.stdout),
        "stderr": _redact_text(completed.stderr),
        "error": "" if completed.returncode == 0 else _redact_text(completed.stderr or completed.stdout),
    }


def _git_text(args: list[str], *, cwd: Path) -> str:
    result = _git(args, cwd=cwd)
    if not result["ok"]:
        return ""
    return _safe_str(result["stdout"]).strip()


def _parse_status(stdout: Any, *, limit: int) -> tuple[str, int, list[dict[str, str]]]:
    branch_line = ""
    changed_count = 0
    changed: list[dict[str, str]] = []
    for line in _safe_str(stdout).splitlines():
        if line.startswith("## "):
            branch_line = line[3:].strip()
            continue
        if not line.strip():
            continue
        changed_count += 1
        if len(changed) >= limit:
            continue
        status = line[:2].strip() or "changed"
        raw_path = line[3:].strip() if len(line) > 3 else line.strip()
        path = raw_path.split(" -> ")[-1].strip()
        changed.append({"status": _redact_text(status), "path": _redact_text(path)})
    return branch_line, changed_count, changed


def _parse_branch_line(line: str) -> dict[str, Any]:
    branch = line
    meta = ""
    if " [" in line and line.endswith("]"):
        branch, meta = line.rsplit(" [", 1)
        meta = meta[:-1]

    upstream = ""
    if "..." in branch:
        branch, upstream = branch.split("...", 1)
    elif branch.startswith("No commits yet on "):
        branch = branch.replace("No commits yet on ", "", 1)

    return {
        "branch": _redact_text(branch.strip()),
        "upstream": _redact_text(upstream.strip()),
        "ahead": _parse_count(meta, "ahead"),
        "behind": _parse_count(meta, "behind"),
    }


def _parse_count(meta: str, key: str) -> int:
    for part in meta.split(","):
        text = part.strip()
        prefix = f"{key} "
        if text.startswith(prefix):
            return _safe_int(text[len(prefix) :], 0)
    return 0


def _governance() -> dict[str, bool]:
    return {
        "read_only": True,
        "on_request_only": True,
        "background_watcher": False,
        "git_fetch": False,
        "git_pull": False,
        "git_push": False,
        "untracked_file_scan": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "telemetry_is_untrusted_input": True,
    }


def _redact_text(value: Any) -> str:
    redacted = redact_telemetry_value(_safe_str(value))
    return _safe_str(redacted)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except Exception:
        return fallback


def _safe_limit(value: int) -> int:
    try:
        limit = int(value)
    except Exception:
        return _MAX_CHANGED_PATHS
    if limit <= 0:
        return _MAX_CHANGED_PATHS
    return min(limit, _MAX_CHANGED_PATHS)


def _now_s() -> int:
    return int(time.time())
