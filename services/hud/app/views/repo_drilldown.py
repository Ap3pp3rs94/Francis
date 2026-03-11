from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.hud.app.state import build_lens_snapshot, get_workspace_root


def _repo_drilldown_path(workspace_root: Path | None = None) -> Path:
    root = (workspace_root or get_workspace_root()).resolve()
    return root / "lens" / "repo_drilldown.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _idle_cards(repo: dict[str, Any]) -> list[dict[str, str]]:
    if not repo:
        return [{"label": "Repo", "value": "state unavailable", "tone": "low"}]
    return [
        {
            "label": "Branch",
            "value": str(repo.get("branch", "unknown")).strip() or "unknown",
            "tone": "low",
        },
        {
            "label": "Changes",
            "value": str(int(repo.get("changed_count", 0))),
            "tone": str(repo.get("severity", "low")).strip().lower() or "low",
        },
        {
            "label": "State",
            "value": "dirty" if bool(repo.get("dirty", False)) else "clean",
            "tone": str(repo.get("severity", "low")).strip().lower() or "low",
        },
    ]


def get_repo_drilldown_view(*, snapshot: dict[str, object] | None = None) -> dict[str, object]:
    if snapshot is None:
        snapshot = build_lens_snapshot()

    state = _read_json(_repo_drilldown_path())
    current_work = snapshot.get("current_work", {}) if isinstance(snapshot.get("current_work"), dict) else {}
    repo = current_work.get("repo", {}) if isinstance(current_work.get("repo"), dict) else {}

    if state:
        presentation = state.get("presentation", {}) if isinstance(state.get("presentation"), dict) else {}
        return {
            "status": "ok",
            "surface": "repo_drilldown",
            "state": "ready",
            "kind": str(state.get("kind", "")).strip(),
            "summary": str(presentation.get("summary") or state.get("summary") or "Repo drilldown is available.").strip(),
            "severity": str(presentation.get("severity", "low")).strip().lower() or "low",
            "cards": presentation.get("cards", []) if isinstance(presentation.get("cards"), list) else [],
            "evidence": presentation.get("evidence", []) if isinstance(presentation.get("evidence"), list) else [],
            "detail": {
                "run_id": str(state.get("run_id", "")).strip(),
                "trace_id": str(state.get("trace_id", "")).strip(),
                "ts": state.get("ts"),
                "tool": state.get("tool", {}) if isinstance(state.get("tool"), dict) else {},
                "execution_args": state.get("execution_args", {}) if isinstance(state.get("execution_args"), dict) else {},
                "presentation": presentation,
            },
        }

    return {
        "status": "ok",
        "surface": "repo_drilldown",
        "state": "idle",
        "kind": "",
        "summary": str(repo.get("summary", "Use the repo drilldown controls to inspect current repository state.")).strip()
        or "Use the repo drilldown controls to inspect current repository state.",
        "severity": str(repo.get("severity", "low")).strip().lower() or "low",
        "cards": _idle_cards(repo),
        "evidence": [],
        "detail": {
            "branch": str(repo.get("branch", "unknown")).strip() or "unknown",
            "dirty": bool(repo.get("dirty", False)),
            "changed_count": int(repo.get("changed_count", 0)),
            "top_paths": [str(item).strip() for item in repo.get("top_paths", []) if str(item).strip()],
        },
    }
