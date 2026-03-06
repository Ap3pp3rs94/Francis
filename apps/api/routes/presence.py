from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Request

from francis.core.config import settings
from francis.core.run_context import ActorKind, RunContext
from francis.core.workspace_fs import WorkspaceFS

from francis.brain.ledger import RunLedger
from francis.presence.briefing import compose_briefing
from francis.presence.state import compute_state

from apps.api.routes.inbox import write_system_message

router = APIRouter(tags=["presence"])

# Workspace wiring (local-first)
_workspace_root = Path(settings.workspace_root).resolve()
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)
_ledger = RunLedger(_fs, rel_path="brain/run_ledger.jsonl")


def _active_missions_count() -> int:
    ctx = RunContext(
        run_id=uuid4(),
        actor_kind=ActorKind.SYSTEM,
        actor_name="francis",
        reason="presence.active_missions_count",
    )
    try:
        raw = _fs.read_text(ctx, "missions/missions.json")
    except Exception:
        return 0

    try:
        parsed = json.loads(raw)
    except Exception:
        return 0
    if not isinstance(parsed, dict):
        return 0
    missions = parsed.get("missions", [])
    if not isinstance(missions, list):
        return 0
    inactive = {"completed", "failed", "cancelled", "canceled"}
    return sum(
        1 for mission in missions if isinstance(mission, dict) and str(mission.get("status", "")).lower() not in inactive
    )


@router.get("/presence/state")
def presence_state(request: Request) -> dict:
    """
    Returns a truthful snapshot of the current local state:
    - inbox counts
    - last ledger events
    """
    run_id = getattr(request.state, "run_id", uuid4())
    st = compute_state(_fs, _ledger, _workspace_root)

    _ledger.append(
        run_id=str(run_id),
        kind="presence.state",
        summary={
            "inbox_count": st.inbox_count,
            "inbox_alerts": st.inbox_alerts,
        },
        reason="presence.state",
    )

    return {"status": "ok", "run_id": str(run_id), "state": st.to_dict()}


@router.post("/presence/briefing")
def generate_briefing(request: Request) -> dict:
    """
    Writes a grounded morning briefing into inbox:
    - headline reflects real alert/message counts
    - bullets include last ledger event if available
    """
    run_id = getattr(request.state, "run_id", uuid4())
    st = compute_state(_fs, _ledger, _workspace_root)
    active_missions = _active_missions_count()

    # Grounded headline logic (non-negotiable)
    if st.inbox_alerts > 0:
        headline = f"Attention required: {st.inbox_alerts} alerts in your inbox."
    elif st.inbox_count == 0:
        headline = "Quiet morning. No messages waiting."
    else:
        headline = f"Inbox active: {st.inbox_count} messages waiting."

    last = st.last_ledger[-1] if st.last_ledger else None
    last_line = (
        f"Last action: {last.get('kind')} @ {last.get('ts')}"
        if isinstance(last, dict) and last.get("kind") and last.get("ts")
        else "Last action: none recorded yet."
    )

    # Grounded recommendation
    if st.inbox_alerts > 0:
        rec = "Recommendation: open the inbox and clear alerts first (highest signal)."
    elif active_missions > 0:
        rec = f"Recommendation: advance your {active_missions} active mission(s) before opening new work."
    elif st.inbox_count > 0:
        rec = "Recommendation: skim messages, convert the top 13 into actionable tasks."
    else:
        rec = "Recommendation: define one standing mission for today and let Francis scaffold it."

    bullets = [
        f"Inbox: {st.inbox_count} total  {st.inbox_alerts} alerts",
        f"Missions: {active_missions} active",
        last_line,
        rec,
        "If you want: I can generate a mission plan once you name the target (project/goal).",
    ]

    b = compose_briefing(headline=headline, bullets=bullets)

    # Write to inbox (existing pipeline)
    entry = write_system_message(title=b["headline"], body=b["body"], severity="alert" if st.inbox_alerts > 0 else "info")

    # Write to ledger (durable continuity)
    _ledger.append(
        run_id=str(run_id),
        kind="presence.briefing",
        summary={
            "headline": headline,
            "inbox_count": st.inbox_count,
            "inbox_alerts": st.inbox_alerts,
            "active_missions": active_missions,
            "wrote_inbox_id": entry.get("id"),
        },
        reason="presence.briefing",
    )

    return {"status": "ok", "run_id": str(run_id), "message": entry, "state_used": st.to_dict()}
