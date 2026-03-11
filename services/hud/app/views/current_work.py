from __future__ import annotations

from typing import Any

from services.hud.app.orchestrator_bridge import get_lens_actions
from services.hud.app.state import build_lens_snapshot


def _normalize_usage_action_kind(value: object) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    suffix = ".request_approval"
    return raw[: -len(suffix)] if raw.endswith(suffix) else raw


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


def _terminal_breakdown(terminal: dict[str, Any]) -> list[dict[str, str]]:
    command = str(terminal.get("command", "")).strip()
    severity = str(terminal.get("severity", "info")).strip().lower() or "info"
    exit_code = terminal.get("exit_code")
    rows: list[dict[str, str]] = []
    if not command:
        return [_evidence_row(kind="terminal", severity="low", detail="No recent terminal command was captured.")]

    rows.append(
        _evidence_row(
            kind="command",
            severity="high" if severity == "error" or (isinstance(exit_code, int) and exit_code != 0) else "low",
            detail=f"{command}{'' if exit_code is None else f' exited {exit_code}'}",
        )
    )
    cwd = str(terminal.get("cwd", "")).strip()
    if cwd:
        rows.append(_evidence_row(kind="cwd", severity="low", detail=f"Working directory {cwd}"))
    first_failure = _first_meaningful_line(
        terminal.get("stderr", ""),
        terminal.get("stdout", ""),
        terminal.get("text", ""),
    )
    if first_failure:
        rows.append(
            _evidence_row(
                kind="failure",
                severity="high" if severity == "error" or (isinstance(exit_code, int) and exit_code != 0) else "medium",
                detail=first_failure,
            )
        )
    elif severity != "error":
        rows.append(_evidence_row(kind="result", severity="low", detail="No visible failure edge was detected."))
    return rows[:4]


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


def _requested_action_kind(row: dict[str, Any]) -> str:
    metadata = row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {}
    explicit = str(metadata.get("action_kind", "")).strip().lower()
    if explicit:
        return explicit
    skill = str(metadata.get("skill", "")).strip().lower()
    if skill:
        return skill
    return str(row.get("action", "")).strip().lower()


def _build_next_action_resume(
    *,
    snapshot: dict[str, object],
    next_action: dict[str, Any],
) -> dict[str, object]:
    focus_kind = _normalize_usage_action_kind(next_action.get("kind"))
    approvals = snapshot.get("approvals", {}) if isinstance(snapshot.get("approvals"), dict) else {}
    pending = approvals.get("pending", []) if isinstance(approvals.get("pending"), list) else []

    for row in pending:
        if not isinstance(row, dict):
            continue
        requested_action_kind = _requested_action_kind(row)
        if not requested_action_kind or requested_action_kind != focus_kind:
            continue
        metadata = row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {}
        args = metadata.get("args", {}) if isinstance(metadata.get("args"), dict) else {}
        approval_id = str(row.get("id", "")).strip()
        lane = str(args.get("lane", "")).strip().lower()
        target = str(args.get("target", "")).strip()
        reason = str(row.get("reason", "")).strip()
        summary = (
            f"Approval {approval_id or 'pending'} is queued for {requested_action_kind}. "
            "The next move can resume immediately after the operator approves it."
        ).strip()
        detail_parts: list[str] = []
        if lane:
            detail_parts.append(f"lane {lane}")
        if target:
            detail_parts.append(target)
        if reason:
            detail_parts.append(reason)
        return {
            "state": "approval_ready",
            "approval_id": approval_id,
            "action_kind": requested_action_kind,
            "summary": summary,
            "detail": " | ".join(detail_parts).strip(),
            "can_resume": True,
            "args": {**args, "approval_id": approval_id},
        }

    return {
        "state": "idle",
        "approval_id": "",
        "action_kind": focus_kind,
        "summary": "No approval-backed continuation is currently queued for the next move.",
        "detail": "",
        "can_resume": False,
        "args": {},
    }


def _build_operator_link(
    *,
    next_action: dict[str, Any],
    next_action_resume: dict[str, object],
    last_run: dict[str, Any],
) -> dict[str, str]:
    action_kind = _normalize_usage_action_kind(next_action.get("kind"))
    approval_id = str(next_action_resume.get("approval_id", "")).strip()
    run_id = str(last_run.get("run_id", "")).strip()
    if not action_kind:
        return {
            "state": "idle",
            "action_kind": "",
            "approval_id": "",
            "run_id": "",
            "summary": "Operator link is idle. Lens is waiting for the next actionable move.",
            "detail": "No current operator move is active.",
        }

    if str(next_action_resume.get("state", "")).strip().lower() == "approval_ready" and approval_id:
        detail = str(next_action_resume.get("detail", "")).strip()
        return {
            "state": "approval_pending",
            "action_kind": action_kind,
            "approval_id": approval_id,
            "run_id": "",
            "summary": f"Operator link: {action_kind} is waiting on approval {approval_id}.",
            "detail": detail or "Approve the queued continuation to resume the current move.",
        }

    if run_id:
        run_phase = str(last_run.get("phase", "")).strip()
        run_summary = str(last_run.get("summary", "")).strip()
        detail_parts = [part for part in [run_phase, run_summary] if part]
        return {
            "state": "receipt_grounded",
            "action_kind": action_kind,
            "approval_id": "",
            "run_id": run_id,
            "summary": f"Operator link: {action_kind} is grounded by run {run_id}.",
            "detail": " | ".join(detail_parts).strip() or "A recent receipt is grounding the current move.",
        }

    reason = str(next_action.get("reason", "")).strip()
    return {
        "state": "following",
        "action_kind": action_kind,
        "approval_id": "",
        "run_id": "",
        "summary": f"Operator link: following {action_kind} as the current move.",
        "detail": reason or "The operator loop is tracking the current next-best action.",
    }


def _chip_args(chip: dict[str, Any]) -> dict[str, object]:
    execute_via = chip.get("execute_via", {}) if isinstance(chip.get("execute_via"), dict) else {}
    payload = execute_via.get("payload", {}) if isinstance(execute_via.get("payload"), dict) else {}
    if isinstance(payload.get("args"), dict):
        return dict(payload.get("args", {}))
    if isinstance(chip.get("args"), dict):
        return dict(chip.get("args", {}))
    return {}


def _find_action_chip(actions: dict[str, object], kind: str) -> dict[str, Any] | None:
    chips = actions.get("action_chips", []) if isinstance(actions.get("action_chips"), list) else []
    lowered = str(kind or "").strip().lower()
    for chip in chips:
        if str(chip.get("kind", "")).strip().lower() == lowered:
            return chip
    return None


def _build_focus_action(
    *,
    actions: dict[str, object],
    next_action: dict[str, Any],
    next_action_resume: dict[str, object],
) -> dict[str, object]:
    focus_kind = _normalize_usage_action_kind(next_action.get("kind"))
    label = str(next_action.get("label", "")).strip() or "No next action selected."
    reason = str(next_action.get("reason", "")).strip() or "No next action guidance is available."
    if not focus_kind:
        return {
            "state": "idle",
            "kind": "",
            "execute_kind": "",
            "label": "No next action selected.",
            "reason": reason,
            "enabled": False,
            "risk_tier": "low",
            "args": {},
        }

    if str(next_action_resume.get("state", "")).strip().lower() == "approval_ready":
        return {
            "state": "approval_ready",
            "kind": focus_kind,
            "execute_kind": focus_kind,
            "label": label,
            "reason": str(next_action_resume.get("summary", "")).strip() or reason,
            "enabled": True,
            "risk_tier": "medium",
            "args": next_action_resume.get("args", {}) if isinstance(next_action_resume.get("args"), dict) else {},
        }

    direct_chip = _find_action_chip(actions, focus_kind)
    if direct_chip and bool(direct_chip.get("enabled", False)):
        return {
            "state": "ready",
            "kind": str(direct_chip.get("kind", "")).strip() or focus_kind,
            "execute_kind": str(direct_chip.get("kind", "")).strip() or focus_kind,
            "label": str(direct_chip.get("label", "")).strip() or label,
            "reason": str(direct_chip.get("policy_reason", "")).strip()
            or str(direct_chip.get("reason", "")).strip()
            or reason,
            "enabled": True,
            "risk_tier": str(direct_chip.get("risk_tier", "low")).strip().lower() or "low",
            "args": _chip_args(direct_chip),
        }

    approval_chip = _find_action_chip(actions, f"{focus_kind}.request_approval")
    if approval_chip:
        return {
            "state": "approval_request" if bool(approval_chip.get("enabled", False)) else "blocked",
            "kind": str(approval_chip.get("kind", "")).strip() or f"{focus_kind}.request_approval",
            "execute_kind": str(approval_chip.get("kind", "")).strip() or f"{focus_kind}.request_approval",
            "label": str(approval_chip.get("label", "")).strip() or label,
            "reason": str(approval_chip.get("policy_reason", "")).strip()
            or str(approval_chip.get("reason", "")).strip()
            or reason,
            "enabled": bool(approval_chip.get("enabled", False)),
            "risk_tier": str(approval_chip.get("risk_tier", "medium")).strip().lower() or "medium",
            "args": _chip_args(approval_chip),
        }

    if direct_chip:
        return {
            "state": "blocked",
            "kind": str(direct_chip.get("kind", "")).strip() or focus_kind,
            "execute_kind": str(direct_chip.get("kind", "")).strip() or focus_kind,
            "label": str(direct_chip.get("label", "")).strip() or label,
            "reason": str(direct_chip.get("policy_reason", "")).strip()
            or str(direct_chip.get("reason", "")).strip()
            or reason,
            "enabled": False,
            "risk_tier": str(direct_chip.get("risk_tier", "medium")).strip().lower() or "medium",
            "args": _chip_args(direct_chip),
        }

    return {
        "state": "blocked",
        "kind": focus_kind,
        "execute_kind": focus_kind,
        "label": label,
        "reason": reason,
        "enabled": False,
        "risk_tier": "medium",
        "args": {},
    }


def _build_next_action_evidence(
    *,
    snapshot: dict[str, object],
    blockers: list[str],
    terminal: dict[str, Any],
    next_action_resume: dict[str, object],
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
    if str(next_action_resume.get("state", "")).strip().lower() == "approval_ready":
        detail = str(next_action_resume.get("summary", "")).strip()
        if detail:
            evidence.append(_evidence_row(kind="resume", severity="medium", detail=detail))
        extra = str(next_action_resume.get("detail", "")).strip()
        if extra:
            evidence.append(_evidence_row(kind="resume", severity="medium", detail=extra))

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


def get_current_work_view(
    *,
    snapshot: dict[str, object] | None = None,
    actions: dict[str, object] | None = None,
) -> dict[str, object]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    if actions is None:
        actions = get_lens_actions(max_actions=8)

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
    next_action_resume = _build_next_action_resume(snapshot=snapshot, next_action=next_best_action)
    operator_link = _build_operator_link(
        next_action=next_best_action,
        next_action_resume=next_action_resume,
        last_run=last_run,
    )
    focus_action = _build_focus_action(
        actions=actions,
        next_action=next_best_action,
        next_action_resume=next_action_resume,
    )
    next_action_evidence = _build_next_action_evidence(
        snapshot=snapshot,
        blockers=[str(item).strip() for item in blockers if str(item).strip()],
        terminal=terminal,
        next_action_resume=next_action_resume,
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
        "terminal_breakdown": _terminal_breakdown(terminal),
        "mission": mission,
        "last_run": last_run,
        "blockers": [str(item).strip() for item in blockers if str(item).strip()],
        "next_action": next_best_action,
        "operator_link": operator_link,
        "focus_action": focus_action,
        "next_action_signal": {
            "severity": next_action_severity,
            "summary": (
                "Approval-backed continuation is ready to resume from the queue."
                if str(next_action_resume.get("state", "")).strip().lower() == "approval_ready"
                else
                "High-pressure evidence is driving the next operator move."
                if next_action_severity == "high"
                else "Medium-pressure evidence is shaping the next operator move."
                if next_action_severity == "medium"
                else "Low-pressure evidence is shaping the next operator move."
            ),
        },
        "next_action_resume": next_action_resume,
        "next_action_evidence": next_action_evidence,
    }
