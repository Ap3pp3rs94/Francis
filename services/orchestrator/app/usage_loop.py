from __future__ import annotations

import json
from pathlib import Path
import threading
import time
from typing import Any

from francis_skills.toolbelt.git import repo_status
from services.orchestrator.app.approvals_store import ApprovalSnapshot
from services.orchestrator.app.capability_state import build_capability_focus, build_capability_state
from services.orchestrator.app.control_state import AWAY_MUTATING_ACTIONS

SEVERITY_ORDER = {
    "critical": 4,
    "error": 3,
    "high": 3,
    "warn": 2,
    "warning": 2,
    "medium": 2,
    "info": 1,
    "low": 1,
    "debug": 0,
    "nominal": 0,
}
REPO_FOCUS_CACHE_TTL_SECONDS = 1.0
_repo_focus_cache_lock = threading.Lock()
_repo_focus_cache: dict[tuple[str, int], tuple[float, dict[str, Any]]] = {}


def _mode_allows_mutating_action(mode: str, action: str) -> tuple[bool, str]:
    normalized_mode = str(mode or "").strip().lower() or "assist"
    normalized_action = str(action or "").strip().lower()
    away_action = {
        "mission.tick": "missions.tick",
        "worker.recover_leases": "worker.recover",
    }.get(normalized_action, normalized_action)
    if normalized_mode == "pilot":
        return (True, "")
    if normalized_mode == "away" and away_action in AWAY_MUTATING_ACTIONS:
        return (True, "")
    return (False, f"mutating action {normalized_action} not allowed in {normalized_mode} mode")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _parse_branch_header(line: str) -> dict[str, Any]:
    header = str(line or "").strip()
    if header.startswith("## "):
        header = header[3:]
    ahead = 0
    behind = 0
    if " [" in header and header.endswith("]"):
        header, detail = header.rsplit(" [", 1)
        detail = detail[:-1]
        for item in detail.split(","):
            normalized = item.strip().lower()
            if normalized.startswith("ahead "):
                try:
                    ahead = int(normalized.split(" ", 1)[1])
                except Exception:
                    ahead = 0
            elif normalized.startswith("behind "):
                try:
                    behind = int(normalized.split(" ", 1)[1])
                except Exception:
                    behind = 0
    branch = header.split("...", 1)[0].strip() or "unknown"
    if branch.lower().startswith("no commits yet on "):
        branch = branch[18:].strip() or branch
    return {"branch": branch, "ahead": ahead, "behind": behind}


def build_repo_focus(
    repo_root: Path,
    *,
    max_paths: int = 5,
    max_age_seconds: float | None = REPO_FOCUS_CACHE_TTL_SECONDS,
) -> dict[str, Any]:
    resolved_repo_root = repo_root.resolve()
    normalized_max_paths = max(1, min(int(max_paths), 10))
    cache_ttl = None if max_age_seconds is None else max(0.0, float(max_age_seconds))
    cache_key = (str(resolved_repo_root), normalized_max_paths)
    if cache_ttl is not None and cache_ttl > 0.0:
        now_mono = time.monotonic()
        with _repo_focus_cache_lock:
            cached = _repo_focus_cache.get(cache_key)
            if cached is not None and cached[0] > now_mono:
                return dict(cached[1])

    result = repo_status(repo_root)
    stdout = str(result.get("stdout", "")).strip()
    if not bool(result.get("ok")):
        payload = {
            "available": False,
            "branch": "unknown",
            "dirty": False,
            "ahead": 0,
            "behind": 0,
            "staged_count": 0,
            "unstaged_count": 0,
            "untracked_count": 0,
            "changed_count": 0,
            "top_paths": [],
            "summary": str(result.get("stderr", "")).strip() or "Repository status unavailable.",
            "status_excerpt": stdout,
        }
        if cache_ttl is not None and cache_ttl > 0.0:
            with _repo_focus_cache_lock:
                _repo_focus_cache[cache_key] = (time.monotonic() + cache_ttl, dict(payload))
        return payload

    lines = [line for line in stdout.splitlines() if line.strip()]
    branch_info = _parse_branch_header(lines[0] if lines else "")
    staged_count = 0
    unstaged_count = 0
    untracked_count = 0
    top_paths: list[str] = []

    for line in lines[1:]:
        if len(line) < 3:
            continue
        status = line[:2]
        rel_path = line[3:].strip()
        if not rel_path:
            continue
        if status == "??":
            untracked_count += 1
        else:
            if status[0] not in {" ", "?"}:
                staged_count += 1
            if status[1] not in {" ", "?"}:
                unstaged_count += 1
        if len(top_paths) < normalized_max_paths:
            top_paths.append(rel_path)

    changed_count = staged_count + unstaged_count + untracked_count
    branch = str(branch_info.get("branch", "unknown")).strip() or "unknown"
    summary_parts = [f"Branch {branch}"]
    if int(branch_info.get("ahead", 0)) > 0 or int(branch_info.get("behind", 0)) > 0:
        summary_parts.append(
            f"ahead {int(branch_info.get('ahead', 0))} / behind {int(branch_info.get('behind', 0))}"
        )
    if changed_count:
        summary_parts.append(
            f"{changed_count} change(s): {staged_count} staged, {unstaged_count} unstaged, {untracked_count} untracked"
        )
    else:
        summary_parts.append("working tree clean")

    payload = {
        "available": True,
        "branch": branch,
        "dirty": changed_count > 0,
        "ahead": int(branch_info.get("ahead", 0)),
        "behind": int(branch_info.get("behind", 0)),
        "staged_count": staged_count,
        "unstaged_count": unstaged_count,
        "untracked_count": untracked_count,
        "changed_count": changed_count,
        "top_paths": top_paths,
        "summary": " | ".join(summary_parts),
        "status_excerpt": stdout,
    }
    if cache_ttl is not None and cache_ttl > 0.0:
        with _repo_focus_cache_lock:
            _repo_focus_cache[cache_key] = (time.monotonic() + cache_ttl, dict(payload))
    return payload


def build_telemetry_focus(workspace_root: Path, *, limit: int = 25) -> dict[str, Any]:
    rows = _read_jsonl(workspace_root / "telemetry" / "events.jsonl")
    limited = rows[-max(1, min(int(limit), 100)) :] if rows else []
    active_streams = sorted(
        {
            str(item.get("stream", "")).strip().lower()
            for item in limited
            if str(item.get("stream", "")).strip()
        }
    )
    recent = list(reversed(limited))

    latest_terminal = next(
        (
            row
            for row in recent
            if str(row.get("stream", "")).strip().lower() == "terminal"
            and isinstance(row.get("fields"), dict)
        ),
        None,
    )
    latest_error = next(
        (
            row
            for row in recent
            if SEVERITY_ORDER.get(str(row.get("severity", "")).strip().lower(), 0) >= 3
        ),
        None,
    )
    terminal_focus = None
    if latest_terminal is not None:
        fields = latest_terminal.get("fields", {}) if isinstance(latest_terminal.get("fields"), dict) else {}
        terminal_focus = {
            "command": str(fields.get("command", "")).strip(),
            "cwd": str(fields.get("cwd", "")).strip(),
            "exit_code": fields.get("exit_code"),
            "stderr": str(fields.get("stderr", "")).strip(),
            "stdout": str(fields.get("stdout", "")).strip(),
            "severity": str(latest_terminal.get("severity", "info")).strip().lower() or "info",
            "text": str(latest_terminal.get("text", "")).strip(),
            "ts": latest_terminal.get("ts"),
        }

    error_focus = None
    if latest_error is not None:
        error_focus = {
            "stream": str(latest_error.get("stream", "")).strip().lower(),
            "severity": str(latest_error.get("severity", "")).strip().lower(),
            "text": str(latest_error.get("text", "")).strip(),
            "ts": latest_error.get("ts"),
        }

    return {
        "event_count": len(rows),
        "recent_count": len(limited),
        "active_streams": active_streams,
        "last_terminal": terminal_focus,
        "last_error": error_focus,
        "recent": [
            {
                "stream": str(row.get("stream", "")).strip().lower(),
                "severity": str(row.get("severity", "")).strip().lower(),
                "text": str(row.get("text", "")).strip(),
                "ts": row.get("ts"),
            }
            for row in recent[:5]
        ],
    }


def _apprenticeship_focus(apprenticeship: dict[str, Any]) -> dict[str, Any]:
    recent = apprenticeship.get("recent_sessions", []) if isinstance(apprenticeship.get("recent_sessions"), list) else []
    review_ready = apprenticeship.get("review_ready", []) if isinstance(apprenticeship.get("review_ready"), list) else []

    focus: dict[str, Any] | None = None
    if review_ready and isinstance(review_ready[0], dict):
        focus = review_ready[0]
    else:
        focus = next(
            (
                row
                for row in recent
                if isinstance(row, dict)
                and str(row.get("status", "")).strip().lower() == "recording"
                and int(row.get("step_count", 0) or 0) > 0
            ),
            None,
        )
    if focus is None:
        focus = next((row for row in recent if isinstance(row, dict)), None)

    if focus is None:
        return {
            "session_count": int(apprenticeship.get("session_count", 0) or 0),
            "recording_count": int(apprenticeship.get("recording_count", 0) or 0),
            "review_count": int(apprenticeship.get("review_count", 0) or 0),
            "skillized_count": int(apprenticeship.get("skillized_count", 0) or 0),
            "focus_session": None,
        }

    status = str(focus.get("status", "")).strip().lower() or "recording"
    step_count = int(focus.get("step_count", 0) or 0)
    title = str(focus.get("title", "Teaching session")).strip() or "Teaching session"
    if status == "review":
        summary = f"{title} is ready to become a reusable workflow and staged skill."
        recommended_action = "apprenticeship.skillize"
    elif status == "recording" and step_count > 0:
        summary = f"{title} has {step_count} demonstrated step(s) ready for generalization review."
        recommended_action = "apprenticeship.generalize"
    elif status == "skillized":
        summary = f"{title} has already been skillized."
        recommended_action = ""
    else:
        summary = f"{title} is recording and waiting for demonstrated steps."
        recommended_action = ""

    return {
        "session_count": int(apprenticeship.get("session_count", 0) or 0),
        "recording_count": int(apprenticeship.get("recording_count", 0) or 0),
        "review_count": int(apprenticeship.get("review_count", 0) or 0),
        "skillized_count": int(apprenticeship.get("skillized_count", 0) or 0),
        "focus_session": {
            "id": str(focus.get("id", "")).strip(),
            "title": title,
            "objective": str(focus.get("objective", "")).strip(),
            "status": status,
            "step_count": step_count,
            "mission_id": str(focus.get("mission_id", "")).strip(),
            "skill_artifact_path": str(focus.get("skill_artifact_path", "")).strip(),
            "forge_stage_id": str(focus.get("forge_stage_id", "")).strip(),
            "summary": summary,
            "recommended_action": recommended_action,
            "actionable": bool(recommended_action),
        },
    }


def _first_failed_rule_detail(rules: dict[str, Any]) -> str:
    for row in rules.get("rules", []) if isinstance(rules.get("rules"), list) else []:
        if not isinstance(row, dict):
            continue
        if bool(row.get("ok")):
            continue
        detail = str(row.get("detail", "")).strip()
        if detail:
            return detail
    return ""


def build_current_work(
    *,
    repo_root: Path,
    workspace_root: Path,
    control: dict[str, Any],
    missions: dict[str, Any],
    approvals: dict[str, Any],
    incidents: dict[str, Any],
    inbox: dict[str, Any],
    runs: dict[str, Any],
    apprenticeship: dict[str, Any],
    approval_snapshot: ApprovalSnapshot | None = None,
    capability_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repo = build_repo_focus(repo_root)
    telemetry = build_telemetry_focus(workspace_root)
    resolved_capability_state = (
        capability_state
        if isinstance(capability_state, dict)
        else build_capability_state(workspace_root, approval_snapshot=approval_snapshot)
    )
    capabilities = build_capability_focus(resolved_capability_state)
    active_missions = missions.get("active", []) if isinstance(missions.get("active"), list) else []
    active_mission = active_missions[0] if active_missions else None
    last_run = runs.get("last_run", {}) if isinstance(runs.get("last_run"), dict) else {}
    apprenticeship_focus = _apprenticeship_focus(apprenticeship)
    focus_session = (
        apprenticeship_focus.get("focus_session", {})
        if isinstance(apprenticeship_focus.get("focus_session"), dict)
        else {}
    )
    focus_capability = (
        capabilities.get("focus_entry", {})
        if isinstance(capabilities.get("focus_entry"), dict)
        else {}
    )
    mode = str(control.get("mode", "assist")).strip().lower() or "assist"
    kill_switch = bool(control.get("kill_switch", False))

    attention_kind = "steady_state"
    attention_label = "Stable"
    attention_reason = "No immediate repo or runtime pressure is visible."

    last_terminal = telemetry.get("last_terminal", {}) if isinstance(telemetry.get("last_terminal"), dict) else {}
    last_error = telemetry.get("last_error", {}) if isinstance(telemetry.get("last_error"), dict) else {}

    if kill_switch:
        attention_kind = "kill_switch"
        attention_label = "Kill Switch Active"
        attention_reason = "Mutating work is paused until the operator resumes control."
    elif str(focus_session.get("recommended_action", "")).strip() == "apprenticeship.skillize":
        attention_kind = "teaching_review"
        attention_label = "Teaching Review"
        attention_reason = str(focus_session.get("summary", "")).strip() or "A teaching session is ready for review."
    elif str(focus_session.get("recommended_action", "")).strip() == "apprenticeship.generalize":
        attention_kind = "teaching_capture"
        attention_label = "Teaching Capture"
        attention_reason = str(focus_session.get("summary", "")).strip() or "A teaching session has captured reusable steps."
    elif str(focus_capability.get("recommended_action", "")).strip() in {
        "forge.promote",
        "forge.quarantine",
        "forge.revoke",
    }:
        attention_kind = "capability_review"
        attention_label = "Capability Review"
        attention_reason = str(focus_capability.get("summary", "")).strip() or "A staged capability is ready for governed review."
    elif last_terminal and str(last_terminal.get("severity", "")).lower() in {"error", "critical"}:
        command = str(last_terminal.get("command", "")).strip() or "terminal command"
        attention_kind = "terminal_failure"
        attention_label = "Terminal Failure"
        attention_reason = f"The latest terminal command failed: {command}."
    elif int(incidents.get("open_count", 0)) > 0:
        attention_kind = "incident_pressure"
        attention_label = "Incident Pressure"
        attention_reason = (
            f"{int(incidents.get('open_count', 0))} open incident(s) at "
            f"{incidents.get('highest_severity', 'medium')} severity."
        )
    elif int(approvals.get("pending_count", 0)) > 0:
        attention_kind = "approval_pressure"
        attention_label = "Approval Pressure"
        attention_reason = f"{int(approvals.get('pending_count', 0))} approval request(s) are waiting."
    elif bool(repo.get("dirty", False)):
        attention_kind = "dirty_repo"
        attention_label = "Dirty Repo"
        attention_reason = str(repo.get("summary", "Repository changes are present."))
    elif active_mission is not None:
        attention_kind = "active_mission"
        attention_label = "Active Mission"
        attention_reason = f"Mission {str(active_mission.get('title', 'Untitled mission')).strip()} is in progress."

    summary_parts = [f"Mode {mode}."]
    if active_mission is not None:
        summary_parts.append(f"Mission {str(active_mission.get('title', 'Untitled mission')).strip()}.")
    summary_parts.append(str(repo.get("summary", "Repository status unavailable.")))
    if focus_session:
        summary_parts.append(str(focus_session.get("summary", "")).strip())
    if focus_capability:
        summary_parts.append(str(focus_capability.get("summary", "")).strip())
    if last_terminal:
        terminal_line = str(last_terminal.get("command", "")).strip() or "terminal activity"
        exit_code = last_terminal.get("exit_code")
        if exit_code is not None:
            terminal_line += f" (exit {exit_code})"
        summary_parts.append(f"Last terminal: {terminal_line}.")
    elif last_error:
        summary_parts.append(f"Last runtime issue: {str(last_error.get('text', '')).strip()}.")
    elif str(last_run.get("summary", "")).strip():
        summary_parts.append(f"Last run: {str(last_run.get('summary', '')).strip()}.")

    blockers: list[str] = []
    if kill_switch:
        blockers.append("Mutations are paused by the kill switch.")
    if int(approvals.get("pending_count", 0)) > 0:
        blockers.append(f"{int(approvals.get('pending_count', 0))} approval(s) are pending.")
    if int(incidents.get("open_count", 0)) > 0:
        blockers.append(
            f"{int(incidents.get('open_count', 0))} incident(s) remain open at {incidents.get('highest_severity', 'medium')} severity."
        )
    if last_terminal and str(last_terminal.get("severity", "")).lower() in {"error", "critical"}:
        blockers.append(str(last_terminal.get("text", "")).strip() or "Recent terminal failure detected.")
    if int(inbox.get("alert_count", 0)) > 0:
        blockers.append(f"{int(inbox.get('alert_count', 0))} inbox alert(s) need review.")
    capability_approval_status = str(focus_capability.get("approval_status", "")).strip().lower()
    capability_approval_action = str(focus_capability.get("approval_action", "")).strip().lower()
    if capability_approval_status == "pending":
        action_label = capability_approval_action.split(".")[-1] if capability_approval_action else "capability"
        blockers.append(f"Capability {action_label} approval is pending.")
    capability_provenance = (
        focus_capability.get("provenance", {}) if isinstance(focus_capability.get("provenance"), dict) else {}
    )
    if bool(capability_provenance.get("review_required")):
        blockers.append(
            str(capability_provenance.get("promotion_rule_detail", "")).strip()
            or str(capability_provenance.get("summary", "")).strip()
            or "Capability provenance review is still required."
        )
    elif bool(capability_provenance.get("quarantined")) or bool(capability_provenance.get("revoked")):
        blockers.append(
            str(capability_provenance.get("summary", "")).strip()
            or "Capability provenance blocks promotion."
        )

    return {
        "summary": " ".join(part for part in summary_parts if part),
        "mode": mode,
        "repo": repo,
        "telemetry": telemetry,
        "mission": active_mission,
        "last_run": last_run,
        "apprenticeship": apprenticeship_focus,
        "capabilities": capabilities,
        "attention": {
            "kind": attention_kind,
            "label": attention_label,
            "reason": attention_reason,
        },
        "blockers": blockers,
    }


def build_next_best_action(
    *,
    current_work: dict[str, Any],
    control: dict[str, Any],
) -> dict[str, Any]:
    mode = str(control.get("mode", "assist")).strip().lower() or "assist"
    kill_switch = bool(control.get("kill_switch", False))
    scopes = control.get("scopes", {}) if isinstance(control.get("scopes"), dict) else {}
    allowed_apps = {
        str(item).strip().lower()
        for item in scopes.get("apps", [])
        if isinstance(item, str) and str(item).strip()
    }
    tools_allowed = not allowed_apps or "tools" in allowed_apps
    missions_allowed = not allowed_apps or "missions" in allowed_apps
    observer_allowed = not allowed_apps or "observer" in allowed_apps
    apprenticeship_allowed = not allowed_apps or "apprenticeship" in allowed_apps
    forge_allowed = not allowed_apps or "forge" in allowed_apps
    generalize_mode_allowed, generalize_mode_reason = _mode_allows_mutating_action(
        mode,
        "apprenticeship.generalize",
    )
    skillize_mode_allowed, skillize_mode_reason = _mode_allows_mutating_action(
        mode,
        "apprenticeship.skillize",
    )
    mission_tick_mode_allowed, mission_tick_mode_reason = _mode_allows_mutating_action(mode, "mission.tick")
    forge_promote_mode_allowed, forge_promote_mode_reason = _mode_allows_mutating_action(mode, "forge.promote")
    forge_quarantine_mode_allowed, forge_quarantine_mode_reason = _mode_allows_mutating_action(
        mode,
        "forge.quarantine",
    )
    forge_revoke_mode_allowed, forge_revoke_mode_reason = _mode_allows_mutating_action(mode, "forge.revoke")
    repo = current_work.get("repo", {}) if isinstance(current_work.get("repo"), dict) else {}
    telemetry = current_work.get("telemetry", {}) if isinstance(current_work.get("telemetry"), dict) else {}
    mission = current_work.get("mission") if isinstance(current_work.get("mission"), dict) else None
    apprenticeship = (
        current_work.get("apprenticeship", {}) if isinstance(current_work.get("apprenticeship"), dict) else {}
    )
    focus_session = (
        apprenticeship.get("focus_session", {}) if isinstance(apprenticeship.get("focus_session"), dict) else {}
    )
    capabilities = (
        current_work.get("capabilities", {}) if isinstance(current_work.get("capabilities"), dict) else {}
    )
    focus_capability = (
        capabilities.get("focus_entry", {}) if isinstance(capabilities.get("focus_entry"), dict) else {}
    )
    attention = current_work.get("attention", {}) if isinstance(current_work.get("attention"), dict) else {}
    last_terminal = telemetry.get("last_terminal", {}) if isinstance(telemetry.get("last_terminal"), dict) else {}
    command = str(last_terminal.get("command", "")).strip().lower()

    if kill_switch:
        return {
            "kind": "control.resume",
            "label": "Resume Mutations",
            "reason": "The kill switch is active. Resume before expecting Francis to change code or advance missions.",
            "risk_tier": "medium",
            "trust_badge": "Confirmed",
            "args": {"mode": mode},
            "enabled": True,
        }

    if attention.get("kind") == "terminal_failure":
        if "pytest" in command or "test" in command:
            return {
                "kind": "repo.tests",
                "label": "Run Fast Checks",
                "reason": "The latest test command failed. Re-run the fast lane after inspecting the current state.",
                "risk_tier": "low",
                "trust_badge": "Likely",
                "args": {"lane": "fast"},
                "enabled": False,
                "policy_reason": (
                    "Repository test execution requires approval."
                    if tools_allowed
                    else "app tools not in allowed scope"
                ),
            }
        if "ruff" in command or "lint" in command:
            return {
                "kind": "repo.lint",
                "label": "Run Ruff Check",
                "reason": "The latest lint-style command failed. Re-run lint against the current repo state.",
                "risk_tier": "low",
                "trust_badge": "Likely",
                "args": {"target": "."},
                "enabled": tools_allowed,
                "policy_reason": "" if tools_allowed else "app tools not in allowed scope",
            }

    apprenticeship_action = str(focus_session.get("recommended_action", "")).strip().lower()
    session_id = str(focus_session.get("id", "")).strip()
    session_title = str(focus_session.get("title", "Teaching session")).strip() or "Teaching session"
    step_count = int(focus_session.get("step_count", 0) or 0)
    if apprenticeship_action == "apprenticeship.generalize":
        return {
            "kind": "apprenticeship.generalize",
            "label": "Generalize Teaching Session",
            "reason": (
                f"{session_title} has {step_count} demonstrated step(s) and is ready for workflow review."
            ),
            "risk_tier": "low",
            "trust_badge": "Likely",
            "args": {"session_id": session_id} if session_id else {},
            "enabled": bool(session_id) and apprenticeship_allowed and generalize_mode_allowed,
            "policy_reason": (
                ""
                if session_id and apprenticeship_allowed and generalize_mode_allowed
                else "Teaching session id is missing."
                if not session_id
                else "app apprenticeship not in allowed scope"
                if not apprenticeship_allowed
                else generalize_mode_reason
            ),
        }

    if apprenticeship_action == "apprenticeship.skillize":
        return {
            "kind": "apprenticeship.skillize",
            "label": "Skillize Teaching Session",
            "reason": f"{session_title} has review-ready structure and can be staged into Forge now.",
            "risk_tier": "medium",
            "trust_badge": "Likely",
            "args": {"session_id": session_id} if session_id else {},
            "enabled": bool(session_id) and apprenticeship_allowed and skillize_mode_allowed,
            "policy_reason": (
                ""
                if session_id and apprenticeship_allowed and skillize_mode_allowed
                else "Teaching session id is missing."
                if not session_id
                else "app apprenticeship not in allowed scope"
                if not apprenticeship_allowed
                else skillize_mode_reason
            ),
        }

    capability_action = str(focus_capability.get("recommended_action", "")).strip().lower()
    stage_id = str(focus_capability.get("id", "")).strip()
    approval_status = str(focus_capability.get("approval_status", "")).strip().lower()
    approval_id = str(focus_capability.get("approval_id", "")).strip()
    promotion_rules = (
        focus_capability.get("promotion_rules", {}) if isinstance(focus_capability.get("promotion_rules"), dict) else {}
    )
    promotion_ready = bool(promotion_rules.get("ready"))
    promotion_blocker = _first_failed_rule_detail(promotion_rules)
    if capability_action == "forge.promote":
        if approval_status == "approved" and approval_id and promotion_ready:
            return {
                "kind": "forge.promote",
                "label": "Promote Capability",
                "reason": str(focus_capability.get("summary", "")).strip()
                or "The staged capability is ready to enter the active library.",
                "risk_tier": str(focus_capability.get("risk_tier", "medium")).strip().lower() or "medium",
                "trust_badge": "Confirmed",
                "args": {"stage_id": stage_id, "approval_id": approval_id} if stage_id else {},
                "enabled": bool(stage_id) and forge_allowed and forge_promote_mode_allowed,
                "policy_reason": (
                    ""
                    if stage_id and forge_allowed and forge_promote_mode_allowed
                    else "Stage id is missing."
                    if not stage_id
                    else "app forge not in allowed scope"
                    if not forge_allowed
                    else forge_promote_mode_reason
                ),
            }
        pending_reason = (
            f"Promotion approval {approval_id} is still pending."
            if approval_status == "pending" and approval_id
            else "Promotion requires approval before execution."
        )
        if approval_status == "rejected":
            pending_reason = "Promotion approval was rejected and needs a fresh operator decision."
        elif approval_status == "approved" and approval_id and not promotion_ready:
            pending_reason = promotion_blocker or "Capability provenance still needs review before promotion."
        return {
            "kind": "forge.promote",
            "label": "Promote Capability",
            "reason": str(focus_capability.get("summary", "")).strip()
            or "The staged capability is ready for governed promotion.",
            "risk_tier": str(focus_capability.get("risk_tier", "medium")).strip().lower() or "medium",
            "trust_badge": "Likely",
            "args": {"stage_id": stage_id} if stage_id else {},
            "enabled": False,
            "policy_reason": pending_reason if forge_allowed else "app forge not in allowed scope",
        }

    if capability_action == "forge.quarantine":
        return {
            "kind": "forge.quarantine",
            "label": "Quarantine Capability",
            "reason": str(focus_capability.get("summary", "")).strip()
            or "The capability should be quarantined before further governed use.",
            "risk_tier": str(focus_capability.get("risk_tier", "medium")).strip().lower() or "medium",
            "trust_badge": "Likely",
            "args": {"entry_id": stage_id} if stage_id else {},
            "enabled": bool(stage_id) and forge_allowed and forge_quarantine_mode_allowed,
            "policy_reason": (
                ""
                if stage_id and forge_allowed and forge_quarantine_mode_allowed
                else "Capability id is missing."
                if not stage_id
                else "app forge not in allowed scope"
                if not forge_allowed
                else forge_quarantine_mode_reason
            ),
        }

    if capability_action == "forge.revoke":
        if approval_status == "approved" and approval_id:
            return {
                "kind": "forge.revoke",
                "label": "Revoke Capability",
                "reason": str(focus_capability.get("summary", "")).strip()
                or "This capability should be revoked from governed use.",
                "risk_tier": str(focus_capability.get("risk_tier", "medium")).strip().lower() or "medium",
                "trust_badge": "Confirmed",
                "args": {"entry_id": stage_id, "approval_id": approval_id} if stage_id else {},
                "enabled": bool(stage_id) and forge_allowed and forge_revoke_mode_allowed,
                "policy_reason": (
                    ""
                    if stage_id and forge_allowed and forge_revoke_mode_allowed
                    else "Capability id is missing."
                    if not stage_id
                    else "app forge not in allowed scope"
                    if not forge_allowed
                    else forge_revoke_mode_reason
                ),
            }
        revoke_reason = (
            f"Revocation approval {approval_id} is still pending."
            if approval_status == "pending" and approval_id
            else "Revocation approval was rejected and needs a fresh operator decision."
            if approval_status == "rejected"
            else "Capability revocation requires approval."
        )
        return {
            "kind": "forge.revoke",
            "label": "Revoke Capability",
            "reason": str(focus_capability.get("summary", "")).strip()
            or "This capability should be revoked from governed use.",
            "risk_tier": str(focus_capability.get("risk_tier", "medium")).strip().lower() or "medium",
            "trust_badge": "Likely",
            "args": {"entry_id": stage_id} if stage_id else {},
            "enabled": False,
            "policy_reason": revoke_reason if forge_allowed else "app forge not in allowed scope",
        }

    if bool(repo.get("dirty", False)) and int(repo.get("changed_count", 0)) > 0:
        return {
            "kind": "repo.diff",
            "label": "Summarize Local Diff",
            "reason": (
                f"{int(repo.get('changed_count', 0))} repo change(s) are present. "
                "Inspect the diff before another execution pass."
            ),
            "risk_tier": "low",
            "trust_badge": "Confirmed",
            "args": {},
            "enabled": tools_allowed,
            "policy_reason": "" if tools_allowed else "app tools not in allowed scope",
        }

    if mission is not None:
        mission_id = str(mission.get("id", "")).strip()
        return {
            "kind": "mission.tick",
            "label": "Advance Active Mission",
            "reason": f"Mission {str(mission.get('title', 'Untitled mission')).strip()} is the active work focus.",
            "risk_tier": "medium",
            "trust_badge": "Likely",
            "args": {"mission_id": mission_id} if mission_id else {},
            "enabled": bool(mission_id) and missions_allowed and mission_tick_mode_allowed,
            "policy_reason": (
                ""
                if mission_id and missions_allowed and mission_tick_mode_allowed
                else "Active mission id is missing."
                if not mission_id
                else "app missions not in allowed scope"
                if not missions_allowed
                else mission_tick_mode_reason
            ),
        }

    return {
        "kind": "observer.scan",
        "label": "Run Observer Scan",
        "reason": "No stronger repo pressure is visible. Refresh live context before choosing a mutating path.",
        "risk_tier": "low",
        "trust_badge": "Likely",
        "args": {},
        "enabled": observer_allowed,
        "policy_reason": "" if observer_allowed else "app observer not in allowed scope",
    }
