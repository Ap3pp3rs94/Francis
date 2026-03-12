from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.hud.app.orchestrator_bridge import get_lens_actions
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


def _ready_audit(*, state: dict[str, Any], presentation: dict[str, Any]) -> dict[str, Any]:
    cards = presentation.get("cards", []) if isinstance(presentation.get("cards"), list) else []
    evidence = presentation.get("evidence", []) if isinstance(presentation.get("evidence"), list) else []
    return {
        "kind": str(state.get("kind", "")).strip() or "repo",
        "summary": str(presentation.get("summary") or state.get("summary") or "Repo drilldown is available.").strip(),
        "severity": str(presentation.get("severity", "low")).strip().lower() or "low",
        "run_id": str(state.get("run_id", "")).strip(),
        "trace_id": str(state.get("trace_id", "")).strip(),
        "tool": state.get("tool", {}) if isinstance(state.get("tool"), dict) else {},
        "execution_args": state.get("execution_args", {}) if isinstance(state.get("execution_args"), dict) else {},
        "card_count": len(cards),
        "evidence_count": len(evidence),
    }


def _idle_audit(repo: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "repo",
        "branch": str(repo.get("branch", "unknown")).strip() or "unknown",
        "dirty": bool(repo.get("dirty", False)),
        "changed_count": int(repo.get("changed_count", 0)),
        "top_paths": [str(item).strip() for item in repo.get("top_paths", []) if str(item).strip()],
    }


def _normalize_usage_action_kind(value: object) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    suffix = ".request_approval"
    return raw[: -len(suffix)] if raw.endswith(suffix) else raw


def _find_action_chip(actions: dict[str, object], kind: str) -> dict[str, Any] | None:
    chips = actions.get("action_chips", []) if isinstance(actions.get("action_chips"), list) else []
    lowered = str(kind or "").strip().lower()
    for chip in chips:
        if str(chip.get("kind", "")).strip().lower() == lowered:
            return chip
    return None


def _chip_args(chip: dict[str, Any]) -> dict[str, object]:
    execute_via = chip.get("execute_via", {}) if isinstance(chip.get("execute_via"), dict) else {}
    payload = execute_via.get("payload", {}) if isinstance(execute_via.get("payload"), dict) else {}
    if isinstance(payload.get("args"), dict):
        return dict(payload.get("args", {}))
    if isinstance(chip.get("args"), dict):
        return dict(chip.get("args", {}))
    return {}


def _build_control(
    *,
    control_id: str,
    label: str,
    preferred_kind: str,
    actions: dict[str, object],
) -> dict[str, object]:
    direct_chip = _find_action_chip(actions, preferred_kind)
    chip = direct_chip
    if chip is None and preferred_kind == "repo.tests":
        chip = _find_action_chip(actions, "repo.tests.request_approval")
    if chip is None:
        return {
            "id": control_id,
            "label": label,
            "kind": preferred_kind,
            "execute_kind": preferred_kind,
            "enabled": False,
            "state": "unavailable",
            "summary": f"{label} is not available in the current Lens action set.",
            "risk_tier": "low",
            "args": {},
        }

    chip_kind = str(chip.get("kind", "")).strip() or preferred_kind
    enabled = bool(chip.get("enabled", False))
    normalized_kind = _normalize_usage_action_kind(chip_kind)
    state = "ready" if enabled and chip_kind == preferred_kind else "approval_request" if enabled else "blocked"
    if preferred_kind != "repo.tests":
        state = "ready" if enabled else "blocked"
    return {
        "id": control_id,
        "label": str(chip.get("label", "")).strip() or label,
        "kind": normalized_kind or preferred_kind,
        "execute_kind": chip_kind,
        "enabled": enabled,
        "state": state,
        "summary": str(chip.get("policy_reason", "")).strip()
        or str(chip.get("reason", "")).strip()
        or f"{label} is available.",
        "risk_tier": str(chip.get("risk_tier", "low")).strip().lower() or "low",
        "args": _chip_args(chip),
    }


def _controls(actions: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        "status": _build_control(control_id="status", label="Repo Status", preferred_kind="repo.status", actions=actions),
        "diff": _build_control(control_id="diff", label="Local Diff", preferred_kind="repo.diff", actions=actions),
        "lint": _build_control(control_id="lint", label="Ruff Check", preferred_kind="repo.lint", actions=actions),
        "tests": _build_control(control_id="tests", label="Fast Checks", preferred_kind="repo.tests", actions=actions),
    }


def get_repo_drilldown_view(
    *,
    snapshot: dict[str, object] | None = None,
    actions: dict[str, object] | None = None,
) -> dict[str, object]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    if actions is None:
        actions = get_lens_actions(max_actions=8)

    state = _read_json(_repo_drilldown_path())
    current_work = snapshot.get("current_work", {}) if isinstance(snapshot.get("current_work"), dict) else {}
    repo = current_work.get("repo", {}) if isinstance(current_work.get("repo"), dict) else {}
    controls = _controls(actions)

    if state:
        presentation = state.get("presentation", {}) if isinstance(state.get("presentation"), dict) else {}
        return {
            "status": "ok",
            "surface": "repo_drilldown",
            "state": "ready",
            "focus_kind": str(state.get("kind", "")).strip(),
            "kind": str(state.get("kind", "")).strip(),
            "summary": str(presentation.get("summary") or state.get("summary") or "Repo drilldown is available.").strip(),
            "severity": str(presentation.get("severity", "low")).strip().lower() or "low",
            "cards": presentation.get("cards", []) if isinstance(presentation.get("cards"), list) else [],
            "evidence": presentation.get("evidence", []) if isinstance(presentation.get("evidence"), list) else [],
            "controls": controls,
            "audit": _ready_audit(state=state, presentation=presentation),
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
        "focus_kind": "",
        "kind": "",
        "summary": str(repo.get("summary", "Use the repo drilldown controls to inspect current repository state.")).strip()
        or "Use the repo drilldown controls to inspect current repository state.",
        "severity": str(repo.get("severity", "low")).strip().lower() or "low",
        "cards": _idle_cards(repo),
        "evidence": [],
        "controls": controls,
        "audit": _idle_audit(repo),
        "detail": {
            "branch": str(repo.get("branch", "unknown")).strip() or "unknown",
            "dirty": bool(repo.get("dirty", False)),
            "changed_count": int(repo.get("changed_count", 0)),
            "top_paths": [str(item).strip() for item in repo.get("top_paths", []) if str(item).strip()],
        },
    }
