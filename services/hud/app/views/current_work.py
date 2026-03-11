from __future__ import annotations

from typing import Any

from services.hud.app.state import build_lens_snapshot


def _first_meaningful_line(*values: object) -> str:
    for value in values:
        text = str(value or "")
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lowered = line.lower()
            if lowered in {"traceback", "stack trace"}:
                continue
            if lowered.startswith("line "):
                continue
            if lowered.startswith("collected ") and lowered.endswith(" items"):
                continue
            return line
    return ""


def _terminal_summary(terminal: dict[str, Any]) -> str:
    command = str(terminal.get("command", "")).strip()
    severity = str(terminal.get("severity", "info")).strip().lower() or "info"
    exit_code = terminal.get("exit_code")
    if not command:
        return "Terminal anchor: no recent command."
    if severity == "error" or (isinstance(exit_code, int) and exit_code != 0):
        first_failure = _first_meaningful_line(
            terminal.get("stderr", ""),
            terminal.get("stdout", ""),
            terminal.get("text", ""),
        )
        if first_failure:
            return f'Terminal failure anchor: {command} failed first on "{first_failure}".'
        return f"Terminal failure anchor: {command} exited {exit_code}."
    return f"Terminal anchor: {command} completed without a visible failure edge."


def _evidence_row(*, kind: str, severity: str, detail: str) -> dict[str, str]:
    return {
        "kind": kind,
        "severity": severity,
        "detail": detail.strip(),
    }


def _severity_rank(severity: str) -> int:
    normalized = str(severity or "").strip().lower()
    if normalized == "high":
        return 3
    if normalized == "medium":
        return 2
    if normalized == "low":
        return 1
    return 0


def _max_evidence_severity(evidence: list[dict[str, str]]) -> str:
    highest = "low"
    for row in evidence:
        severity = str(row.get("severity", "low")).strip().lower() or "low"
        if _severity_rank(severity) > _severity_rank(highest):
            highest = severity
    return highest if evidence else "low"


def _repo_severity(repo: dict[str, Any]) -> str:
    if not bool(repo.get("available", False)):
        return "unknown"
    changed_count = int(repo.get("changed_count", 0))
    if not bool(repo.get("dirty", False)) and changed_count <= 0:
        return "low"
    if changed_count >= 8 or int(repo.get("unstaged_count", 0)) >= 5:
        return "high"
    return "medium"


def _build_next_action_evidence(
    *,
    snapshot: dict[str, object],
    blockers: list[str],
    terminal: dict[str, Any],
) -> list[dict[str, str]]:
    evidence: list[dict[str, str]] = []
    terminal_summary = _terminal_summary(terminal)
    if terminal_summary.startswith("Terminal failure anchor:"):
        evidence.append(_evidence_row(kind="terminal", severity="high", detail=terminal_summary))

    lowered_blockers = [item.lower() for item in blockers]
    for blocker in blockers[:2]:
        severity = "high" if "approval" in blocker.lower() or "blocked" in blocker.lower() else "medium"
        evidence.append(_evidence_row(kind="blocker", severity=severity, detail=blocker))

    approvals = snapshot.get("approvals", {}) if isinstance(snapshot.get("approvals"), dict) else {}
    pending_count = int(approvals.get("pending_count", 0))
    if pending_count and not any("approval" in item for item in lowered_blockers):
        evidence.append(
            _evidence_row(
                kind="approval",
                severity="high" if pending_count > 0 else "medium",
                detail=f"{pending_count} approval(s) are pending in the current workspace.",
            )
        )

    fabric = snapshot.get("fabric", {}) if isinstance(snapshot.get("fabric"), dict) else {}
    calibration = fabric.get("calibration", {}) if isinstance(fabric.get("calibration"), dict) else {}
    confidence_counts = (
        calibration.get("confidence_counts", {}) if isinstance(calibration.get("confidence_counts"), dict) else {}
    )
    stale_count = int(calibration.get("stale_current_state_count", 0))
    uncertain_count = int(confidence_counts.get("uncertain", 0))
    if stale_count > 0:
        evidence.append(
            _evidence_row(
                kind="fabric",
                severity="medium",
                detail=f"{stale_count} current-state artifact(s) are stale and need refresh before they count as proof.",
            )
        )
    elif uncertain_count > 0:
        evidence.append(
            _evidence_row(
                kind="fabric",
                severity="medium",
                detail=f"{uncertain_count} fabric artifact(s) remain uncertain.",
            )
        )

    if not evidence:
        summary = str(snapshot.get("next_best_action", {}).get("reason", "")).strip()
        if summary:
            evidence.append(_evidence_row(kind="context", severity="low", detail=summary))

    return evidence[:4]


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
    next_action_evidence = _build_next_action_evidence(
        snapshot=snapshot,
        blockers=[str(item).strip() for item in blockers if str(item).strip()],
        terminal=terminal,
    )
    next_action_severity = _max_evidence_severity(next_action_evidence)

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
            "severity": _repo_severity(repo),
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
        "terminal_summary": _terminal_summary(terminal),
        "mission": mission,
        "last_run": last_run,
        "blockers": [str(item).strip() for item in blockers if str(item).strip()],
        "next_action": next_best_action,
        "next_action_signal": {
            "severity": next_action_severity,
            "summary": (
                "High-pressure evidence is driving the next operator move."
                if next_action_severity == "high"
                else "Medium-pressure evidence is shaping the next operator move."
                if next_action_severity == "medium"
                else "Low-pressure evidence is shaping the next operator move."
            ),
        },
        "next_action_evidence": next_action_evidence,
    }
