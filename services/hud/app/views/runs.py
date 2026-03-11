from __future__ import annotations

from typing import Any

from services.hud.app.state import build_lens_snapshot


def _detail_summary(row: dict[str, Any]) -> str:
    run_id = str(row.get("run_id", "none")).strip() or "none"
    phase = str(row.get("phase", row.get("last_kind", "unknown"))).strip() or "unknown"
    summary = str(row.get("summary", "")).strip()
    if summary:
        return f"{run_id} | {phase} | {summary}"
    return f"{run_id} | {phase}"


def _detail_cards(*, run_id: str, phase: str, summary: str, event_count: int = 0) -> list[dict[str, str]]:
    cards = [
        {"label": "Run", "value": run_id or "none", "tone": "medium" if run_id and run_id != "none" else "low"},
        {"label": "Phase", "value": phase or "unknown", "tone": "medium"},
    ]
    if event_count:
        cards.append({"label": "Events", "value": str(event_count), "tone": "low"})
    elif summary:
        cards.append({"label": "State", "value": "active", "tone": "low"})
    return cards


def get_runs_view(*, snapshot: dict[str, object] | None = None) -> dict[str, object]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    runs = snapshot["runs"]
    last_run = runs["last_run"] if isinstance(runs["last_run"], dict) else {}
    recent = runs["recent"] if isinstance(runs.get("recent"), list) else []
    ledger_tail = runs["ledger_tail"] if isinstance(runs.get("ledger_tail"), list) else []
    active_run = {
        "run_id": str(last_run.get("run_id", "")).strip() or "none",
        "phase": str(last_run.get("phase", "unknown")).strip() or "unknown",
        "summary": str(last_run.get("summary", "")).strip() or "No active run recorded in workspace/runs/last_run.json.",
    }
    active_run["detail_summary"] = _detail_summary(active_run)
    active_run["detail_cards"] = _detail_cards(
        run_id=active_run["run_id"],
        phase=active_run["phase"],
        summary=active_run["summary"],
    )
    run_groups: list[dict[str, Any]] = []
    for row in recent:
        if not isinstance(row, dict):
            continue
        run_id = str(row.get("run_id", "")).strip() or "none"
        phase = str(row.get("last_kind", "unknown")).strip() or "unknown"
        event_count = int(row.get("event_count", 0))
        item = dict(row)
        item["detail_summary"] = _detail_summary(
            {
                "run_id": run_id,
                "phase": phase,
                "summary": f"{event_count} event(s) recorded." if event_count else "",
            }
        )
        item["detail_cards"] = _detail_cards(
            run_id=run_id,
            phase=phase,
            summary="",
            event_count=event_count,
        )
        run_groups.append(item)
    return {
        "status": "ok",
        "surface": "runs",
        "summary": _detail_summary(active_run),
        "severity": "medium" if active_run["run_id"] != "none" else "low",
        "cards": [
            {"label": "Run", "value": active_run["run_id"], "tone": "medium" if active_run["run_id"] != "none" else "low"},
            {"label": "Phase", "value": active_run["phase"], "tone": "medium"},
            {"label": "Recent", "value": str(len(recent)), "tone": "low"},
            {"label": "Ledger", "value": str(len(ledger_tail)), "tone": "low"},
        ],
        "active_run": active_run,
        "recent": recent,
        "run_groups": run_groups,
        "ledger_tail": ledger_tail,
        "detail": {
            "active_run": active_run,
            "recent": recent,
            "run_groups": run_groups,
            "ledger_tail": ledger_tail,
        },
    }
