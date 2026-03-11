from __future__ import annotations

from typing import Any

from services.hud.app.state import build_lens_snapshot


def _receipt_summary(row: dict[str, Any]) -> str:
    summary = row.get("summary")
    if isinstance(summary, dict):
        explicit = str(summary.get("summary_text", "")).strip()
        if explicit:
            return explicit
        action_kind = str(summary.get("action_kind", "")).strip()
        result_status = str(summary.get("result_status", "")).strip()
        if action_kind and result_status:
            return f"{action_kind} {result_status}".strip()
        if action_kind:
            return action_kind
    if isinstance(summary, str):
        return summary.strip()
    return ""


def _latest_receipt_for_run(run_id: str, ledger_tail: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not run_id or run_id == "none":
        return None
    for row in reversed(ledger_tail):
        if not isinstance(row, dict):
            continue
        if str(row.get("run_id", "")).strip() == run_id:
            return row
    return None


def _detail_summary(row: dict[str, Any]) -> str:
    run_id = str(row.get("run_id", "none")).strip() or "none"
    phase = str(row.get("phase", row.get("last_kind", "unknown"))).strip() or "unknown"
    summary = str(row.get("summary", "")).strip()
    if summary:
        return f"{run_id} | {phase} | {summary}"
    return f"{run_id} | {phase}"


def _detail_state(*, run_id: str, active_run_id: str) -> str:
    if run_id and active_run_id and run_id == active_run_id:
        return "current"
    return "historical"


def _detail_cards(
    *,
    run_id: str,
    phase: str,
    summary: str,
    event_count: int = 0,
    receipt_summary: str = "",
    receipt_kind: str = "",
) -> list[dict[str, str]]:
    cards = [
        {"label": "Run", "value": run_id or "none", "tone": "medium" if run_id and run_id != "none" else "low"},
        {"label": "Phase", "value": phase or "unknown", "tone": "medium"},
    ]
    if event_count:
        cards.append({"label": "Events", "value": str(event_count), "tone": "low"})
    elif summary:
        cards.append({"label": "State", "value": "active", "tone": "low"})
    if receipt_kind:
        cards.append({"label": "Receipt", "value": receipt_kind, "tone": "low"})
    if receipt_summary:
        cards.append({"label": "Latest", "value": receipt_summary, "tone": "medium"})
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
    active_receipt = _latest_receipt_for_run(active_run["run_id"], ledger_tail)
    active_receipt_summary = _receipt_summary(active_receipt) if isinstance(active_receipt, dict) else ""
    active_receipt_kind = str(active_receipt.get("kind", "")).strip() if isinstance(active_receipt, dict) else ""
    active_run["detail_summary"] = _detail_summary(active_run)
    if active_receipt_summary:
        active_run["detail_summary"] = f"{active_run['detail_summary']} | {active_receipt_summary}".strip()
    active_run["detail_cards"] = _detail_cards(
        run_id=active_run["run_id"],
        phase=active_run["phase"],
        summary=active_run["summary"],
        receipt_summary=active_receipt_summary,
        receipt_kind=active_receipt_kind,
    )
    active_run["detail_state"] = "current" if active_run["run_id"] != "none" else "idle"
    run_groups: list[dict[str, Any]] = []
    for row in recent:
        if not isinstance(row, dict):
            continue
        run_id = str(row.get("run_id", "")).strip() or "none"
        phase = str(row.get("last_kind", "unknown")).strip() or "unknown"
        event_count = int(row.get("event_count", 0))
        receipt = _latest_receipt_for_run(run_id, ledger_tail)
        receipt_summary = _receipt_summary(receipt) if isinstance(receipt, dict) else ""
        receipt_kind = str(receipt.get("kind", "")).strip() if isinstance(receipt, dict) else ""
        item = dict(row)
        item["detail_summary"] = _detail_summary(
            {
                "run_id": run_id,
                "phase": phase,
                "summary": (
                    f"{event_count} event(s) recorded."
                    + (f" Latest receipt: {receipt_summary}" if receipt_summary else "")
                    if event_count
                    else receipt_summary
                ),
            }
        )
        item["detail_cards"] = _detail_cards(
            run_id=run_id,
            phase=phase,
            summary="",
            event_count=event_count,
            receipt_summary=receipt_summary,
            receipt_kind=receipt_kind,
        )
        item["detail_state"] = _detail_state(run_id=run_id, active_run_id=active_run["run_id"])
        run_groups.append(item)
    return {
        "status": "ok",
        "surface": "runs",
        "summary": active_run["detail_summary"],
        "severity": "medium" if active_run["run_id"] != "none" else "low",
        "cards": [
            {"label": "Run", "value": active_run["run_id"], "tone": "medium" if active_run["run_id"] != "none" else "low"},
            {"label": "Phase", "value": active_run["phase"], "tone": "medium"},
            {"label": "Recent", "value": str(len(recent)), "tone": "low"},
            {"label": "Ledger", "value": str(len(ledger_tail)), "tone": "low"},
            {"label": "Latest Receipt", "value": active_receipt_summary or "none", "tone": "medium" if active_receipt_summary else "low"},
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
