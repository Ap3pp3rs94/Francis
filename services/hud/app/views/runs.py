from __future__ import annotations

from services.hud.app.state import build_lens_snapshot


def get_runs_view() -> dict[str, object]:
    snapshot = build_lens_snapshot()
    runs = snapshot["runs"]
    last_run = runs["last_run"] if isinstance(runs["last_run"], dict) else {}
    return {
        "status": "ok",
        "surface": "runs",
        "active_run": {
            "run_id": str(last_run.get("run_id", "")).strip() or "none",
            "phase": str(last_run.get("phase", "unknown")).strip() or "unknown",
            "summary": str(last_run.get("summary", "")).strip() or "No active run recorded in workspace/runs/last_run.json.",
        },
        "recent": runs["recent"],
        "ledger_tail": runs["ledger_tail"],
    }
