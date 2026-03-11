from __future__ import annotations

from services.hud.app.state import build_lens_snapshot


def get_current_work_view(*, snapshot: dict[str, object] | None = None) -> dict[str, object]:
    if snapshot is None:
        snapshot = build_lens_snapshot()

    current_work = snapshot.get("current_work", {}) if isinstance(snapshot.get("current_work"), dict) else {}
    next_best_action = (
        snapshot.get("next_best_action", {}) if isinstance(snapshot.get("next_best_action"), dict) else {}
    )
    repo = current_work.get("repo", {}) if isinstance(current_work.get("repo"), dict) else {}
    telemetry = current_work.get("telemetry", {}) if isinstance(current_work.get("telemetry"), dict) else {}
    terminal = telemetry.get("last_terminal", {}) if isinstance(telemetry.get("last_terminal"), dict) else {}
    attention = current_work.get("attention", {}) if isinstance(current_work.get("attention"), dict) else {}
    blockers = current_work.get("blockers", []) if isinstance(current_work.get("blockers"), list) else []
    mission = current_work.get("mission") if isinstance(current_work.get("mission"), dict) else None
    last_run = current_work.get("last_run", {}) if isinstance(current_work.get("last_run"), dict) else {}

    return {
        "status": "ok",
        "surface": "current_work",
        "summary": str(current_work.get("summary", "Current work context is not available.")),
        "attention": {
            "kind": str(attention.get("kind", "steady_state")).strip() or "steady_state",
            "label": str(attention.get("label", "Stable")).strip() or "Stable",
            "reason": str(attention.get("reason", "No immediate work pressure is visible.")).strip()
            or "No immediate work pressure is visible.",
        },
        "repo": {
            "available": bool(repo.get("available", False)),
            "branch": str(repo.get("branch", "unknown")).strip() or "unknown",
            "dirty": bool(repo.get("dirty", False)),
            "changed_count": int(repo.get("changed_count", 0)),
            "staged_count": int(repo.get("staged_count", 0)),
            "unstaged_count": int(repo.get("unstaged_count", 0)),
            "untracked_count": int(repo.get("untracked_count", 0)),
            "top_paths": [str(item).strip() for item in repo.get("top_paths", []) if str(item).strip()],
            "summary": str(repo.get("summary", "Repository status unavailable.")).strip()
            or "Repository status unavailable.",
        },
        "terminal": {
            "command": str(terminal.get("command", "")).strip(),
            "exit_code": terminal.get("exit_code"),
            "stderr": str(terminal.get("stderr", "")).strip(),
            "stdout": str(terminal.get("stdout", "")).strip(),
            "severity": str(terminal.get("severity", "info")).strip().lower() or "info",
            "text": str(terminal.get("text", "")).strip(),
            "ts": terminal.get("ts"),
        },
        "mission": mission,
        "last_run": last_run,
        "blockers": [str(item).strip() for item in blockers if str(item).strip()],
        "next_action": next_best_action,
    }
