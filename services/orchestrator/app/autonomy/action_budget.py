from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from francis_core.workspace_fs import WorkspaceFS

BUDGET_STATE_PATH = "autonomy/action_budget_state.json"
DEFAULT_ACTION_POLICIES: dict[str, dict[str, int]] = {
    "observer.scan": {"daily_cap": 500, "cooldown_seconds": 300},
    "worker.cycle": {"daily_cap": 500, "cooldown_seconds": 120},
    "mission.tick": {"daily_cap": 2000, "cooldown_seconds": 0},
    "forge.propose": {"daily_cap": 300, "cooldown_seconds": 300},
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _date_key(dt: datetime) -> str:
    return dt.date().isoformat()


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _default_state(now: datetime) -> dict[str, Any]:
    return {
        "date": _date_key(now),
        "counts": {},
        "last_executed_at": {},
        "updated_at": now.isoformat(),
    }


def _sanitize_state(raw: dict[str, Any], now: datetime) -> dict[str, Any]:
    date = str(raw.get("date", "")).strip()
    today = _date_key(now)
    if date != today:
        return _default_state(now)

    counts = raw.get("counts", {})
    if not isinstance(counts, dict):
        counts = {}
    last_executed = raw.get("last_executed_at", {})
    if not isinstance(last_executed, dict):
        last_executed = {}

    out_counts: dict[str, int] = {}
    for key, value in counts.items():
        k = str(key).strip().lower()
        if not k:
            continue
        try:
            out_counts[k] = max(0, int(value))
        except Exception:
            continue

    out_last: dict[str, str] = {}
    for key, value in last_executed.items():
        k = str(key).strip().lower()
        if not k:
            continue
        ts = _parse_iso(str(value))
        if ts is None:
            continue
        out_last[k] = ts.isoformat()

    return {
        "date": today,
        "counts": out_counts,
        "last_executed_at": out_last,
        "updated_at": now.isoformat(),
    }


def load_state(fs: WorkspaceFS, *, now: datetime | None = None) -> dict[str, Any]:
    current = now or _utc_now()
    try:
        raw = fs.read_text(BUDGET_STATE_PATH)
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            state = _sanitize_state(parsed, current)
            fs.write_text(BUDGET_STATE_PATH, json.dumps(state, ensure_ascii=False, indent=2))
            return state
    except Exception:
        pass
    state = _default_state(current)
    fs.write_text(BUDGET_STATE_PATH, json.dumps(state, ensure_ascii=False, indent=2))
    return state


def save_state(fs: WorkspaceFS, state: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    current = now or _utc_now()
    normalized = _sanitize_state(state, current)
    normalized["updated_at"] = current.isoformat()
    fs.write_text(BUDGET_STATE_PATH, json.dumps(normalized, ensure_ascii=False, indent=2))
    return normalized


def _action_key(action: dict[str, Any]) -> str:
    kind = str(action.get("kind", "")).strip().lower()
    if kind == "mission.tick":
        mission_id = str(action.get("mission_id", "")).strip()
        if mission_id:
            return f"{kind}:{mission_id}"
    return kind


def _policy_for(action: dict[str, Any]) -> dict[str, int]:
    kind = str(action.get("kind", "")).strip().lower()
    return dict(DEFAULT_ACTION_POLICIES.get(kind, {"daily_cap": 999_999, "cooldown_seconds": 0}))


def check_action_budget(
    action: dict[str, Any],
    *,
    state: dict[str, Any],
    now: datetime | None = None,
) -> tuple[bool, str, str]:
    current = now or _utc_now()
    action_key = _action_key(action)
    if not action_key:
        return (False, "missing action key", action_key)

    policy = _policy_for(action)
    daily_cap = max(1, int(policy.get("daily_cap", 999_999)))
    cooldown_seconds = max(0, int(policy.get("cooldown_seconds", 0)))

    counts = state.get("counts", {})
    if not isinstance(counts, dict):
        counts = {}
    count = int(counts.get(action_key, 0))
    if count >= daily_cap:
        return (False, f"daily cap reached for {action_key} ({count}/{daily_cap})", action_key)

    last_executed = state.get("last_executed_at", {})
    if not isinstance(last_executed, dict):
        last_executed = {}
    last_ts = _parse_iso(str(last_executed.get(action_key, "")).strip() or None)
    if cooldown_seconds > 0 and last_ts is not None:
        elapsed = int((current - last_ts).total_seconds())
        if elapsed < cooldown_seconds:
            remaining = cooldown_seconds - elapsed
            return (False, f"cooldown active for {action_key} ({remaining}s remaining)", action_key)

    return (True, "allowed", action_key)


def register_action_execution(
    state: dict[str, Any],
    *,
    action: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or _utc_now()
    action_key = _action_key(action)
    if not action_key:
        return state
    counts = state.setdefault("counts", {})
    if not isinstance(counts, dict):
        counts = {}
        state["counts"] = counts
    counts[action_key] = int(counts.get(action_key, 0)) + 1

    last_executed = state.setdefault("last_executed_at", {})
    if not isinstance(last_executed, dict):
        last_executed = {}
        state["last_executed_at"] = last_executed
    last_executed[action_key] = current.isoformat()
    state["updated_at"] = current.isoformat()
    return state


def apply_budget_gates(
    actions: list[dict[str, Any]],
    *,
    state: dict[str, Any],
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    current = now or _utc_now()
    allowed: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for action in actions:
        if not bool(action.get("allowed", True)):
            blocked.append({**action})
            continue
        ok, reason, key = check_action_budget(action, state=state, now=current)
        if ok:
            allowed.append({**action})
        else:
            blocked.append(
                {
                    **action,
                    "allowed": False,
                    "policy_reason": reason,
                    "blocked_by": "action_budget",
                    "action_key": key,
                }
            )
    return (allowed, blocked)
