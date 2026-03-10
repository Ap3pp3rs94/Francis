from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from francis_brain.ledger import RunLedger
from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS
from francis_presence.narrator import compose_operator_presence
from francis_presence.tone import normalize_mode
from services.orchestrator.app.lens_operator import compact_action_chip, get_lens_actions
from services.orchestrator.app.lens_snapshot import build_lens_snapshot
from services.voice.app.stt import preview_transcription

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
    "apprenticeship.generalize": ("teach", "generalize lesson", "review teaching", "distill workflow"),
    "apprenticeship.skillize": ("skillize", "turn into skill", "stage taught skill", "forge learned skill"),
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


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(str(text).strip().lower()))


def _log_receipt(*, run_id: str, kind: str, summary: dict[str, Any]) -> None:
    _ledger.append(run_id=run_id, kind=kind, summary=summary)


def build_operator_presence(
    *,
    mode: str = "assist",
    max_actions: int = 3,
    snapshot: dict[str, Any] | None = None,
    actions_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_mode = normalize_mode(mode)
    snapshot = snapshot if isinstance(snapshot, dict) else build_lens_snapshot()
    actions_payload = actions_payload if isinstance(actions_payload, dict) else get_lens_actions(max_actions=max_actions)
    action_chips = [
        compact_action_chip(chip)
        for chip in actions_payload.get("action_chips", [])
        if isinstance(chip, dict)
    ][: max(0, min(int(max_actions), 8))]
    return compose_operator_presence(
        mode=normalized_mode,
        snapshot=snapshot,
        actions=action_chips,
        surface="voice",
        receipt_mode="explicit",
    )


def build_live_operator_briefing(*, mode: str = "assist", max_actions: int = 3) -> dict[str, Any]:
    briefing = build_operator_presence(mode=mode, max_actions=max_actions)
    run_id = str(uuid4())

    _log_receipt(
        run_id=run_id,
        kind="voice.live_briefing",
        summary={
            "mode": briefing["mode"],
            "headline": briefing["headline"],
            "trust": briefing["grounding"]["trust"],
            "incident_count": briefing["grounding"]["incident_count"],
            "pending_approvals": briefing["grounding"]["pending_approvals"],
            "active_missions": briefing["grounding"]["active_missions"],
            "fabric_uncertain_count": briefing["grounding"].get("fabric", {}).get("uncertain_count", 0),
            "fabric_stale_current_state_count": briefing["grounding"].get("fabric", {}).get(
                "stale_current_state_count",
                0,
            ),
            "handback_available": briefing["grounding"].get("handback", {}).get("available", False),
            "handback_run_id": briefing["grounding"].get("handback", {}).get("run_id"),
            "handback_trust": briefing["grounding"].get("handback", {}).get("trust"),
            "suggested_action_kind": briefing["actions"][0]["kind"] if briefing["actions"] else "",
        },
    )

    return {
        "status": "ok",
        "run_id": run_id,
        "briefing": briefing,
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
        briefing = build_operator_presence(mode="assist", max_actions=max_actions)
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
            "briefing": briefing,
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
        compact = compact_action_chip(chip)
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
