from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from francis_brain.ledger import RunLedger
from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS
from services.hud.app.orchestrator_bridge import get_lens_actions
from services.hud.app.state import build_lens_snapshot
from services.voice.app.stt import preview_transcription
from services.voice.app.tts import MODE_OPENERS

DEFAULT_WORKSPACE_ROOT = Path(settings.workspace_root).resolve()
_fs = WorkspaceFS(
    roots=[DEFAULT_WORKSPACE_ROOT],
    journal_path=(DEFAULT_WORKSPACE_ROOT / "journals" / "fs.jsonl").resolve(),
)
_ledger = RunLedger(_fs, rel_path="runs/run_ledger.jsonl")

_ACTION_ALIASES = {
    "observer.scan": ("scan", "observer", "health check", "check system", "look around"),
    "worker.cycle": ("worker", "queue", "process queue", "run queue", "jobs"),
    "mission.tick": ("mission", "advance mission", "next step", "tick mission", "continue mission"),
    "forge.propose": ("forge", "proposal", "generate capability", "proposal pass"),
    "control.panic": ("panic", "panic stop", "stop", "halt", "kill switch", "freeze"),
    "control.resume": ("resume", "unpause", "continue"),
    "control.takeover.request": ("takeover", "pilot", "request takeover", "take control"),
    "control.remote.approvals": ("approvals", "pending approvals", "review approvals"),
    "control.remote.approval.approve": ("approve", "approve request", "allow"),
    "control.remote.approval.reject": ("reject", "deny request", "block request"),
    "autonomy.dispatch": ("dispatch", "autonomy", "run autonomy"),
    "autonomy.reactor.tick": ("reactor", "tick reactor", "reactor tick"),
}
_BRIEFING_HINTS = (
    "brief",
    "status",
    "what is going on",
    "what's going on",
    "shift report",
    "report",
    "summary",
    "where are we at",
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _normalize_mode(mode: str) -> str:
    normalized = str(mode).strip().lower()
    if normalized not in MODE_OPENERS:
        raise ValueError(f"Unsupported mode: {mode}")
    return normalized


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(str(text).strip().lower()))


def _log_receipt(*, run_id: str, kind: str, summary: dict[str, Any]) -> None:
    _ledger.append(run_id=run_id, kind=kind, summary=summary)


def _compact_action(chip: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": str(chip.get("kind", "")).strip(),
        "label": str(chip.get("label", "")).strip(),
        "risk_tier": str(chip.get("risk_tier", "")).strip(),
        "trust_badge": str(chip.get("trust_badge", "")).strip(),
        "requires_confirmation": bool(chip.get("requires_confirmation", False)),
        "reason": str(chip.get("reason", "")).strip(),
        "execute_via": chip.get("execute_via", {}),
    }


def _briefing_headline(snapshot: dict[str, Any]) -> str:
    control = snapshot.get("control", {})
    incidents = snapshot.get("incidents", {})
    approvals = snapshot.get("approvals", {})
    missions = snapshot.get("missions", {})
    mode = str(control.get("mode", "pilot")).strip().lower() or "pilot"
    objective = str(snapshot.get("objective", {}).get("label", "Systematically build Francis")).strip()

    if bool(control.get("kill_switch")):
        return f"Kill switch is active. {objective} is paused in {mode} mode."
    if int(incidents.get("open_count", 0)) > 0:
        highest = str(incidents.get("highest_severity", "unknown")).strip() or "unknown"
        return f"Incident pressure is {highest}. {objective} remains the current objective."
    if int(approvals.get("pending_count", 0)) > 0:
        pending = int(approvals.get("pending_count", 0))
        noun = "approval" if pending == 1 else "approvals"
        return f"{pending} pending {noun} are waiting on the current objective: {objective}."
    if int(missions.get("active_count", 0)) > 0:
        return f"Mission focus is active: {objective}."
    return f"System state is stable. Current objective: {objective}."


def _briefing_lines(snapshot: dict[str, Any], actions: list[dict[str, Any]], *, mode: str) -> list[str]:
    control = snapshot.get("control", {})
    incidents = snapshot.get("incidents", {})
    approvals = snapshot.get("approvals", {})
    missions = snapshot.get("missions", {})
    inbox = snapshot.get("inbox", {})
    runs = snapshot.get("runs", {})

    active_mission = missions.get("active", [])
    top_mission = active_mission[0] if active_mission else {}
    last_run = runs.get("last_run", {})
    lines = [
        f"Control mode is {str(control.get('mode', mode)).strip().lower()} with kill switch "
        f"{'engaged' if bool(control.get('kill_switch')) else 'disengaged'}.",
        f"Incidents: {int(incidents.get('open_count', 0))} open, highest severity "
        f"{str(incidents.get('highest_severity', 'nominal')).strip() or 'nominal'}.",
        f"Approvals: {int(approvals.get('pending_count', 0))} pending. Inbox alerts: {int(inbox.get('alert_count', 0))}.",
    ]
    if top_mission:
        title = str(top_mission.get("title", "Untitled mission")).strip() or "Untitled mission"
        status = str(top_mission.get("status", "active")).strip().lower() or "active"
        lines.append(f"Primary mission is {title} with status {status}.")
    if isinstance(last_run, dict) and last_run:
        summary = str(last_run.get("summary", "")).strip()
        if summary:
            lines.append(f"Latest recorded run: {summary}")
    if actions:
        action_labels = ", ".join(str(action.get("label", "")).strip() for action in actions[:3] if action.get("label"))
        if action_labels:
            lines.append(f"Recommended next actions: {action_labels}.")
    lines.append("Claims remain tied to visible receipts and current scope.")
    return lines


def build_live_operator_briefing(*, mode: str = "assist", max_actions: int = 3) -> dict[str, Any]:
    normalized_mode = _normalize_mode(mode)
    snapshot = build_lens_snapshot()
    actions_payload = get_lens_actions(max_actions=max_actions)
    action_chips = [
        _compact_action(chip)
        for chip in actions_payload.get("action_chips", [])
        if isinstance(chip, dict)
    ][: max(0, min(int(max_actions), 8))]

    opener = MODE_OPENERS[normalized_mode]
    headline = _briefing_headline(snapshot)
    lines = _briefing_lines(snapshot, action_chips, mode=normalized_mode)
    body = " ".join([opener, headline, *lines])
    run_id = str(uuid4())
    grounding = {
        "trust": "Confirmed",
        "workspace_root": snapshot.get("workspace_root"),
        "objective": snapshot.get("objective", {}),
        "incident_count": int(snapshot.get("incidents", {}).get("open_count", 0)),
        "pending_approvals": int(snapshot.get("approvals", {}).get("pending_count", 0)),
        "active_missions": int(snapshot.get("missions", {}).get("active_count", 0)),
    }

    _log_receipt(
        run_id=run_id,
        kind="voice.live_briefing",
        summary={
            "mode": normalized_mode,
            "headline": headline,
            "incident_count": grounding["incident_count"],
            "pending_approvals": grounding["pending_approvals"],
            "active_missions": grounding["active_missions"],
            "suggested_action_kind": action_chips[0]["kind"] if action_chips else "",
        },
    )

    return {
        "status": "ok",
        "run_id": run_id,
        "briefing": {
            "mode": normalized_mode,
            "headline": headline,
            "body": body,
            "lines": lines,
            "grounding": grounding,
            "actions": action_chips,
        },
    }


def _score_action(utterance: str, utterance_tokens: set[str], chip: dict[str, Any]) -> tuple[int, list[str]]:
    kind = str(chip.get("kind", "")).strip().lower()
    label = str(chip.get("label", "")).strip().lower()
    reason = str(chip.get("reason", "")).strip().lower()
    kind_tokens = _tokenize(kind.replace(".", " "))
    label_tokens = _tokenize(label)
    reason_tokens = _tokenize(reason)

    score = 0
    why: list[str] = []
    for alias in _ACTION_ALIASES.get(kind, ()):
        alias_text = str(alias).strip().lower()
        if alias_text and alias_text in utterance:
            score += 6
            why.append(f"matched alias '{alias_text}'")
    token_overlap = utterance_tokens & kind_tokens
    if token_overlap:
        score += 3 * len(token_overlap)
        why.append(f"matched kind tokens {sorted(token_overlap)}")
    label_overlap = utterance_tokens & label_tokens
    if label_overlap:
        score += 2 * len(label_overlap)
        why.append(f"matched label tokens {sorted(label_overlap)}")
    reason_overlap = utterance_tokens & reason_tokens
    if reason_overlap:
        score += len(reason_overlap)
        why.append(f"matched reason tokens {sorted(reason_overlap)}")
    return (score, why)


def preview_operator_command(*, utterance: str, locale: str = "en-US", max_actions: int = 5) -> dict[str, Any]:
    preview = preview_transcription(utterance, locale=locale)
    normalized_text = str(preview.get("normalized_text", "")).strip().lower()
    run_id = str(uuid4())

    if not normalized_text:
        _log_receipt(
            run_id=run_id,
            kind="voice.command.preview",
            summary={"normalized_text": "", "intent": "empty", "top_match_kind": ""},
        )
        return {
            "status": "ok",
            "run_id": run_id,
            "preview": preview,
            "intent": {"kind": "empty", "trust": "Uncertain"},
            "matches": [],
            "governance": {
                "execution": "not_performed",
                "requires_explicit_execution": True,
                "reason": "No command text remained after normalization.",
            },
        }

    if any(hint in normalized_text for hint in _BRIEFING_HINTS):
        briefing = build_live_operator_briefing(mode="assist", max_actions=max_actions)
        _log_receipt(
            run_id=run_id,
            kind="voice.command.preview",
            summary={
                "normalized_text": normalized_text,
                "intent": "briefing.request",
                "top_match_kind": "",
            },
        )
        return {
            "status": "ok",
            "run_id": run_id,
            "preview": preview,
            "intent": {"kind": "briefing.request", "trust": "Likely"},
            "matches": [],
            "briefing": briefing["briefing"],
            "governance": {
                "execution": "not_performed",
                "requires_explicit_execution": True,
                "reason": "Status requests return a briefing, not hidden action execution.",
            },
        }

    utterance_tokens = _tokenize(normalized_text)
    actions_payload = get_lens_actions(max_actions=max_actions)
    ranked: list[tuple[int, dict[str, Any], list[str]]] = []
    for raw_chip in actions_payload.get("action_chips", []):
        if not isinstance(raw_chip, dict):
            continue
        score, why = _score_action(normalized_text, utterance_tokens, raw_chip)
        if score <= 0:
            continue
        ranked.append((score, raw_chip, why))
    ranked.sort(
        key=lambda item: (
            item[0],
            1 if bool(item[1].get("enabled", False)) else 0,
            str(item[1].get("trust_badge", "")),
        ),
        reverse=True,
    )

    matches = []
    for score, chip, why in ranked[: max(1, min(int(max_actions), 5))]:
        compact = _compact_action(chip)
        compact["match_score"] = score
        compact["why"] = why
        matches.append(compact)

    top_kind = str(matches[0].get("kind", "")).strip() if matches else ""
    _log_receipt(
        run_id=run_id,
        kind="voice.command.preview",
        summary={
            "normalized_text": normalized_text,
            "intent": "action.suggestion" if matches else "unresolved",
            "top_match_kind": top_kind,
        },
    )

    return {
        "status": "ok",
        "run_id": run_id,
        "preview": preview,
        "intent": {
            "kind": "action.suggestion" if matches else "unresolved",
            "trust": "Likely" if matches else "Uncertain",
        },
        "matches": matches,
        "governance": {
            "execution": "not_performed",
            "requires_explicit_execution": True,
            "reason": "Voice preview can rank Lens actions but cannot execute them implicitly.",
        },
    }
