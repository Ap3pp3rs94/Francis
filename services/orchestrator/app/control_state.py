from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS

CONTROL_STATE_PATH = "control/state.json"
VALID_MODES = {"observe", "assist", "pilot", "away"}
DEFAULT_ALLOWED_APPS = [
    "missions",
    "forge",
    "observer",
    "autonomy",
    "control",
    "approvals",
    "receipts",
    "lens",
    "tools",
    "worker",
    "presence",
    "telemetry",
]
MANDATORY_APPS = {"control", "approvals", "receipts", "lens"}
AWAY_MUTATING_ACTIONS = {
    "missions.tick",
    "observer.scan",
    "forge.stage",
    "autonomy.cycle",
    "autonomy.enqueue",
    "autonomy.dispatch",
    "worker.cycle",
    "worker.recover",
}


def _default_state(repo_root: Path, workspace_root: Path) -> dict[str, Any]:
    return {
        "mode": "pilot",
        "kill_switch": False,
        "scopes": {
            "repos": [str(repo_root.resolve())],
            "workspaces": [str(workspace_root.resolve())],
            "apps": list(DEFAULT_ALLOWED_APPS),
        },
        "updated_at": utc_now_iso(),
    }


def _normalize_scope_paths(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        stripped = value.strip()
        if not stripped:
            continue
        normalized.append(str(Path(stripped).resolve()))
    return sorted(set(normalized))


def _validate_state(state: dict[str, Any], repo_root: Path, workspace_root: Path) -> dict[str, Any]:
    mode = str(state.get("mode", "")).strip().lower()
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid mode: {mode}")

    kill_switch = bool(state.get("kill_switch", False))
    scopes = state.get("scopes", {})
    if not isinstance(scopes, dict):
        raise ValueError("scopes must be an object")

    repos = _normalize_scope_paths(scopes.get("repos", []) if isinstance(scopes.get("repos"), list) else [])
    workspaces = _normalize_scope_paths(
        scopes.get("workspaces", []) if isinstance(scopes.get("workspaces"), list) else []
    )
    apps_raw = scopes.get("apps", []) if isinstance(scopes.get("apps"), list) else []
    apps = sorted(set(str(item).strip().lower() for item in apps_raw if isinstance(item, str) and item.strip()))

    if not repos:
        repos = [str(repo_root.resolve())]
    if not workspaces:
        workspaces = [str(workspace_root.resolve())]
    if not apps:
        apps = list(DEFAULT_ALLOWED_APPS)
    else:
        apps = sorted(set(apps).union(MANDATORY_APPS))

    return {
        "mode": mode,
        "kill_switch": kill_switch,
        "scopes": {"repos": repos, "workspaces": workspaces, "apps": apps},
        "updated_at": utc_now_iso(),
    }


def load_or_init_control_state(fs: WorkspaceFS, repo_root: Path, workspace_root: Path) -> dict[str, Any]:
    try:
        raw = fs.read_text(CONTROL_STATE_PATH)
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            validated = _validate_state(parsed, repo_root, workspace_root)
            fs.write_text(CONTROL_STATE_PATH, json.dumps(validated, ensure_ascii=False, indent=2))
            return validated
    except Exception:
        pass

    state = _default_state(repo_root, workspace_root)
    fs.write_text(CONTROL_STATE_PATH, json.dumps(state, ensure_ascii=False, indent=2))
    return state


def save_control_state(fs: WorkspaceFS, state: dict[str, Any], repo_root: Path, workspace_root: Path) -> dict[str, Any]:
    validated = _validate_state(state, repo_root, workspace_root)
    fs.write_text(CONTROL_STATE_PATH, json.dumps(validated, ensure_ascii=False, indent=2))
    return validated


def set_mode(
    fs: WorkspaceFS,
    *,
    repo_root: Path,
    workspace_root: Path,
    mode: str,
    kill_switch: bool | None = None,
) -> dict[str, Any]:
    state = load_or_init_control_state(fs, repo_root, workspace_root)
    state["mode"] = mode
    if kill_switch is not None:
        state["kill_switch"] = bool(kill_switch)
    return save_control_state(fs, state, repo_root, workspace_root)


def set_scope(
    fs: WorkspaceFS,
    *,
    repo_root: Path,
    workspace_root: Path,
    repos: list[str] | None = None,
    workspaces: list[str] | None = None,
    apps: list[str] | None = None,
) -> dict[str, Any]:
    state = load_or_init_control_state(fs, repo_root, workspace_root)
    scopes = state.setdefault("scopes", {})
    if repos is not None:
        scopes["repos"] = repos
    if workspaces is not None:
        scopes["workspaces"] = workspaces
    if apps is not None:
        scopes["apps"] = apps
    return save_control_state(fs, state, repo_root, workspace_root)


def _path_in_any_scope(target: Path, allowed_roots: list[str]) -> bool:
    resolved_target = target.resolve()
    for root in allowed_roots:
        try:
            resolved_target.relative_to(Path(root).resolve())
            return True
        except Exception:
            continue
    return False


def _mode_allows(*, mode: str, action: str, mutating: bool) -> tuple[bool, str]:
    if not mutating:
        return (True, "allowed")
    if mode == "pilot":
        return (True, "allowed")
    if mode == "away":
        if action in AWAY_MUTATING_ACTIONS:
            return (True, "allowed")
        return (False, f"action {action} not allowed in away mode")
    return (False, f"mutating action {action} not allowed in {mode} mode")


def check_action_allowed(
    fs: WorkspaceFS,
    *,
    repo_root: Path,
    workspace_root: Path,
    app: str,
    action: str,
    mutating: bool,
) -> tuple[bool, str, dict[str, Any]]:
    state = load_or_init_control_state(fs, repo_root, workspace_root)
    mode = str(state.get("mode", "observe")).lower()
    kill_switch = bool(state.get("kill_switch", False))
    scopes = state.get("scopes", {})
    allowed_apps = scopes.get("apps", []) if isinstance(scopes, dict) else []
    allowed_repos = scopes.get("repos", []) if isinstance(scopes, dict) else []
    allowed_workspaces = scopes.get("workspaces", []) if isinstance(scopes, dict) else []

    if kill_switch and mutating:
        return (False, "kill switch active", state)
    if app.lower() not in [str(a).lower() for a in allowed_apps]:
        return (False, f"app {app} not in allowed scope", state)
    if not _path_in_any_scope(repo_root, [str(p) for p in allowed_repos]):
        return (False, "repo outside allowed scope", state)
    if not _path_in_any_scope(workspace_root, [str(p) for p in allowed_workspaces]):
        return (False, "workspace outside allowed scope", state)
    mode_ok, mode_reason = _mode_allows(mode=mode, action=action, mutating=mutating)
    if not mode_ok:
        return (False, mode_reason, state)
    return (True, "allowed", state)
