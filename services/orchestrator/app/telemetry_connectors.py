from __future__ import annotations

from typing import Any


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _normalize_severity(value: str | None, *, fallback: str = "info") -> str:
    raw = _clean(value).lower()
    mapping = {
        "warning": "warn",
        "err": "error",
        "fatal": "critical",
    }
    normalized = mapping.get(raw, raw or fallback)
    if normalized not in {"debug", "info", "warn", "error", "critical"}:
        return fallback
    return normalized


def adapt_terminal_event(
    *,
    source: str | None,
    command: str | None,
    cwd: str | None,
    exit_code: int | None,
    stdout: str | None,
    stderr: str | None,
    duration_ms: int | None,
    ts: str | None,
) -> dict[str, Any]:
    normalized_command = _clean(command) or "<unknown>"
    normalized_exit = int(exit_code) if isinstance(exit_code, int) else None
    stderr_text = _clean(stderr)
    stdout_text = _clean(stdout)
    severity = "error" if (normalized_exit not in {None, 0} or bool(stderr_text)) else "info"

    headline = f"terminal: {normalized_command}"
    if normalized_exit is not None:
        headline += f" (exit={normalized_exit})"
    detail = stderr_text or stdout_text
    if detail:
        headline += f" :: {detail[:240]}"

    return {
        "stream": "terminal",
        "source": _clean(source) or "terminal",
        "severity": severity,
        "text": headline,
        "fields": {
            "command": normalized_command,
            "cwd": _clean(cwd),
            "exit_code": normalized_exit,
            "duration_ms": int(duration_ms) if isinstance(duration_ms, int) else None,
            "stdout": stdout_text,
            "stderr": stderr_text,
        },
        "ts": ts,
    }


def adapt_git_event(
    *,
    source: str | None,
    action: str | None,
    repo: str | None,
    branch: str | None,
    summary: str | None,
    files: list[str] | None,
    ts: str | None,
) -> dict[str, Any]:
    normalized_action = _clean(action).lower() or "update"
    conflict_actions = {"merge_conflict", "rebase_conflict", "cherry_pick_conflict", "push_rejected"}
    severity = "error" if normalized_action in conflict_actions else "info"
    normalized_files = [str(item).strip() for item in (files or []) if str(item).strip()]
    text = f"git: {normalized_action} on {_clean(branch) or 'unknown-branch'}"
    summary_text = _clean(summary)
    if summary_text:
        text += f" :: {summary_text[:240]}"

    return {
        "stream": "git",
        "source": _clean(source) or "git",
        "severity": severity,
        "text": text,
        "fields": {
            "action": normalized_action,
            "repo": _clean(repo),
            "branch": _clean(branch),
            "summary": summary_text,
            "files": normalized_files,
            "file_count": len(normalized_files),
        },
        "ts": ts,
    }


def adapt_dev_server_event(
    *,
    source: str | None,
    service: str | None,
    level: str | None,
    message: str | None,
    port: int | None,
    ts: str | None,
) -> dict[str, Any]:
    severity = _normalize_severity(level, fallback="info")
    normalized_service = _clean(service) or "dev_server"
    normalized_message = _clean(message)
    text = f"dev_server:{normalized_service}:{severity}"
    if normalized_message:
        text += f" :: {normalized_message[:240]}"
    return {
        "stream": "dev_server",
        "source": _clean(source) or normalized_service,
        "severity": severity,
        "text": text,
        "fields": {
            "service": normalized_service,
            "port": int(port) if isinstance(port, int) else None,
            "level": _clean(level).lower(),
            "message": normalized_message,
        },
        "ts": ts,
    }
