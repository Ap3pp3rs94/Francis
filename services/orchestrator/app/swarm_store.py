from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS

SWARM_UNITS_PATH = "swarm/units.json"
SWARM_DELEGATIONS_PATH = "swarm/delegations.jsonl"
SWARM_DEADLETTER_PATH = "swarm/deadletter.jsonl"
DEFAULT_LEASE_TTL_SECONDS = 300
DEFAULT_RETRY_BACKOFF_SECONDS = 60


def _read_json(fs: WorkspaceFS, rel_path: str, default: object) -> object:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _write_json(fs: WorkspaceFS, rel_path: str, payload: dict[str, Any]) -> None:
    fs.write_text(rel_path, json.dumps(payload, ensure_ascii=False, indent=2))


def _read_jsonl(fs: WorkspaceFS, rel_path: str) -> list[dict[str, Any]]:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except Exception:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _write_jsonl(fs: WorkspaceFS, rel_path: str, rows: list[dict[str, Any]]) -> None:
    payload = ""
    if rows:
        payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    fs.write_text(rel_path, payload)


def _append_jsonl(fs: WorkspaceFS, rel_path: str, row: dict[str, Any]) -> None:
    existing = ""
    try:
        existing = fs.read_text(rel_path)
    except Exception:
        existing = ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    fs.write_text(rel_path, existing + json.dumps(row, ensure_ascii=False) + "\n")


def _normalize_text(value: str | None, *, fallback: str = "", max_length: int = 240) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        normalized = fallback
    return normalized[:max_length]


def _normalize_list(values: list[str] | None, *, max_items: int = 12) -> list[str]:
    items: list[str] = []
    for value in values or []:
        normalized = _normalize_text(value, max_length=120).lower()
        if normalized and normalized not in items:
            items.append(normalized)
        if len(items) >= max(1, min(int(max_items), 32)):
            break
    return items


def _normalize_action_args(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, Any] = {}
    for key, item in value.items():
        normalized_key = _normalize_text(str(key), max_length=80)
        if not normalized_key:
            continue
        if isinstance(item, (str, int, float, bool)) or item is None:
            normalized[normalized_key] = item
        elif isinstance(item, list):
            safe_items: list[Any] = []
            for entry in item[:16]:
                if isinstance(entry, (str, int, float, bool)) or entry is None:
                    safe_items.append(entry)
            normalized[normalized_key] = safe_items
        elif isinstance(item, dict):
            child: dict[str, Any] = {}
            for child_key, child_value in item.items():
                normalized_child_key = _normalize_text(str(child_key), max_length=80)
                if not normalized_child_key:
                    continue
                if isinstance(child_value, (str, int, float, bool)) or child_value is None:
                    child[normalized_child_key] = child_value
            normalized[normalized_key] = child
    return normalized


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _status_rank(value: str | None) -> int:
    normalized = str(value or "").strip().lower()
    ranks = {
        "leased": 0,
        "queued": 1,
        "deadlettered": 2,
        "completed": 3,
    }
    return ranks.get(normalized, 4)


def _is_due(row: dict[str, Any]) -> bool:
    next_run_after = _parse_ts(str(row.get("next_run_after", "")).strip() or None)
    if next_run_after is None:
        return True
    return next_run_after <= datetime.now(timezone.utc)


def _normalize_unit_registry(
    repo_root: Path,
    workspace_root: Path,
) -> list[dict[str, Any]]:
    apps = ["control", "approvals", "lens", "worker", "receipts"]
    repo_scope = [str(repo_root.resolve())]
    workspace_scope = [str(workspace_root.resolve())]
    return [
        {
            "unit_id": "coordinator",
            "label": "Coordinator",
            "role": "coordinator",
            "summary": "Preserves one Francis presence while routing bounded delegation and explicit authority.",
            "capabilities": [
                "delegate.route",
                "approval.queue",
                "scope.check",
                "handoff.summary",
            ],
            "scope_defaults": {"repos": repo_scope, "workspaces": workspace_scope, "apps": apps},
            "delegatable": False,
            "local": True,
        },
        {
            "unit_id": "planner",
            "label": "Planner",
            "role": "planner",
            "summary": "Breaks missions and repo pressure into bounded next moves.",
            "capabilities": [
                "mission.plan",
                "mission.tick",
                "repo.breakdown",
                "approval.route",
                "next_move.selection",
            ],
            "scope_defaults": {"repos": repo_scope, "workspaces": workspace_scope, "apps": apps},
            "delegatable": True,
            "local": True,
        },
        {
            "unit_id": "repo_operator",
            "label": "Repo Operator",
            "role": "repo_operator",
            "summary": "Executes repo and terminal work under bounded scope and receipts.",
            "capabilities": [
                "repo.status",
                "repo.diff",
                "repo.lint",
                "repo.tests",
            ],
            "scope_defaults": {"repos": repo_scope, "workspaces": workspace_scope, "apps": apps},
            "delegatable": True,
            "local": True,
        },
        {
            "unit_id": "verifier",
            "label": "Verifier",
            "role": "verifier",
            "summary": "Checks claims, test posture, diffs, and receipt evidence before handback.",
            "capabilities": [
                "verify.tests",
                "verify.receipts",
                "review.diff",
                "done_claim.check",
            ],
            "scope_defaults": {"repos": repo_scope, "workspaces": workspace_scope, "apps": apps},
            "delegatable": True,
            "local": True,
        },
        {
            "unit_id": "memory_curator",
            "label": "Memory Curator",
            "role": "memory_curator",
            "summary": "Carries recall, continuity, and workflow generalization without broadening authority.",
            "capabilities": [
                "fabric.recall",
                "fabric.refresh",
                "apprenticeship.generalize",
                "handoff.grounding",
            ],
            "scope_defaults": {"repos": repo_scope, "workspaces": workspace_scope, "apps": apps},
            "delegatable": True,
            "local": True,
        },
        {
            "unit_id": "incident_guard",
            "label": "Incident Guard",
            "role": "incident_guard",
            "summary": "Handles hostile-input review, policy pressure, and deadletter escalation.",
            "capabilities": [
                "incident.review",
                "policy.check",
                "security.quarantine.review",
                "deadletter.review",
            ],
            "scope_defaults": {"repos": repo_scope, "workspaces": workspace_scope, "apps": apps},
            "delegatable": True,
            "local": True,
        },
    ]


def load_or_init_units(
    fs: WorkspaceFS,
    *,
    repo_root: Path,
    workspace_root: Path,
) -> list[dict[str, Any]]:
    payload = _read_json(fs, SWARM_UNITS_PATH, {})
    if isinstance(payload, dict):
        rows = payload.get("units", []) if isinstance(payload.get("units"), list) else []
        units = [row for row in rows if isinstance(row, dict)]
        if units:
            return units

    units = _normalize_unit_registry(repo_root, workspace_root)
    _write_json(
        fs,
        SWARM_UNITS_PATH,
        {
            "version": 1,
            "updated_at": utc_now_iso(),
            "units": units,
        },
    )
    return units


def _find_unit(units: list[dict[str, Any]], unit_id: str) -> dict[str, Any] | None:
    normalized = _normalize_text(unit_id, max_length=80).lower()
    for row in units:
        if _normalize_text(str(row.get("unit_id", "")), max_length=80).lower() == normalized:
            return row
    return None


def delegate_work(
    fs: WorkspaceFS,
    *,
    repo_root: Path,
    workspace_root: Path,
    run_id: str,
    trace_id: str,
    source_unit_id: str,
    target_unit_id: str,
    action_kind: str,
    summary: str,
    handoff_note: str = "",
    scope_apps: list[str] | None = None,
    action_args: dict[str, Any] | None = None,
    mission_id: str | None = None,
    approval_id: str | None = None,
    max_attempts: int = 2,
    authority_basis: str = "",
) -> dict[str, Any]:
    units = load_or_init_units(fs, repo_root=repo_root, workspace_root=workspace_root)
    target = _find_unit(units, target_unit_id)
    if target is None:
        raise ValueError(f"Unknown target unit: {target_unit_id}")

    source = _find_unit(units, source_unit_id)
    scope_defaults = target.get("scope_defaults", {}) if isinstance(target.get("scope_defaults"), dict) else {}
    normalized_scope_apps = _normalize_list(scope_apps)
    if not normalized_scope_apps:
        normalized_scope_apps = _normalize_list(scope_defaults.get("apps", []))

    row = {
        "id": str(uuid4()),
        "ts": utc_now_iso(),
        "kind": "swarm.delegation",
        "run_id": _normalize_text(run_id, max_length=80),
        "trace_id": _normalize_text(trace_id, max_length=80),
        "source_unit_id": _normalize_text(source_unit_id, fallback="coordinator", max_length=80).lower(),
        "target_unit_id": _normalize_text(target_unit_id, max_length=80).lower(),
        "source_label": _normalize_text(str((source or {}).get("label", "")), max_length=120),
        "target_label": _normalize_text(str(target.get("label", "")), max_length=120),
        "action_kind": _normalize_text(action_kind, max_length=120).lower(),
        "summary": _normalize_text(summary, max_length=240),
        "handoff_note": _normalize_text(handoff_note, max_length=240),
        "scope_apps": normalized_scope_apps,
        "action_args": _normalize_action_args(action_args),
        "mission_id": _normalize_text(mission_id, max_length=80) or None,
        "approval_id": _normalize_text(approval_id, max_length=80) or None,
        "authority_basis": _normalize_text(authority_basis, max_length=240),
        "status": "queued",
        "attempts": 0,
        "max_attempts": max(1, min(int(max_attempts), 5)),
        "next_run_after": utc_now_iso(),
        "lease_owner": None,
        "lease_expires_at": None,
        "leased_at": None,
        "completed_at": None,
        "completed_by_unit_id": None,
        "deadlettered_at": None,
        "result_summary": "",
        "last_error": "",
        "last_failure_reason": "",
    }
    rows = _read_jsonl(fs, SWARM_DELEGATIONS_PATH)
    rows.append(row)
    _write_jsonl(fs, SWARM_DELEGATIONS_PATH, rows)
    return row


def get_delegation(fs: WorkspaceFS, delegation_id: str) -> dict[str, Any] | None:
    normalized_id = _normalize_text(delegation_id, max_length=80)
    if not normalized_id:
        return None
    for row in _read_jsonl(fs, SWARM_DELEGATIONS_PATH):
        if _normalize_text(str(row.get("id", "")), max_length=80) == normalized_id:
            return row
    return None


def list_delegations(
    fs: WorkspaceFS,
    *,
    statuses: set[str] | None = None,
    due_only: bool = False,
    target_unit_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    normalized_statuses = {str(item).strip().lower() for item in statuses or set() if str(item).strip()}
    normalized_target = _normalize_text(target_unit_id, max_length=80).lower() if target_unit_id else ""
    rows = _read_jsonl(fs, SWARM_DELEGATIONS_PATH)
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = _normalize_text(str(row.get("status", "")), max_length=40).lower()
        if normalized_statuses and status not in normalized_statuses:
            continue
        if due_only and not _is_due(row):
            continue
        if normalized_target and _normalize_text(str(row.get("target_unit_id", "")), max_length=80).lower() != normalized_target:
            continue
        filtered.append(row)
    filtered.sort(
        key=lambda row: (
            _status_rank(str(row.get("status", ""))),
            str(row.get("next_run_after", row.get("ts", ""))),
            str(row.get("ts", "")),
        )
    )
    if limit is not None:
        capped = max(0, min(int(limit), 50))
        return filtered[:capped]
    return filtered


def lease_delegation(
    fs: WorkspaceFS,
    *,
    repo_root: Path,
    workspace_root: Path,
    delegation_id: str,
    unit_id: str,
    lease_owner: str,
    lease_ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
) -> dict[str, Any] | None:
    load_or_init_units(fs, repo_root=repo_root, workspace_root=workspace_root)
    rows = _read_jsonl(fs, SWARM_DELEGATIONS_PATH)
    normalized_id = _normalize_text(delegation_id, max_length=80)
    normalized_unit_id = _normalize_text(unit_id, max_length=80).lower()
    ttl = max(15, min(int(lease_ttl_seconds), 3600))
    leased_at = datetime.now(timezone.utc)
    lease_expires_at = (leased_at + timedelta(seconds=ttl)).isoformat()
    updated_rows: list[dict[str, Any]] = []
    leased_row: dict[str, Any] | None = None
    for row in rows:
        if _normalize_text(str(row.get("id", "")), max_length=80) != normalized_id:
            updated_rows.append(row)
            continue
        if _normalize_text(str(row.get("target_unit_id", "")), max_length=80).lower() != normalized_unit_id:
            raise ValueError(f"Delegation {delegation_id} is not assigned to unit {unit_id}")
        status = _normalize_text(str(row.get("status", "")), max_length=40).lower()
        if status != "queued":
            raise ValueError(f"Delegation {delegation_id} is not queued")
        if not _is_due(row):
            raise ValueError(f"Delegation {delegation_id} is waiting for its retry window")
        leased_row = {
            **row,
            "status": "leased",
            "lease_owner": _normalize_text(lease_owner, fallback=normalized_unit_id, max_length=120),
            "leased_at": leased_at.isoformat(),
            "lease_expires_at": lease_expires_at,
        }
        updated_rows.append(leased_row)
    if leased_row is None:
        return None
    _write_jsonl(fs, SWARM_DELEGATIONS_PATH, updated_rows)
    return leased_row


def complete_delegation(
    fs: WorkspaceFS,
    *,
    repo_root: Path,
    workspace_root: Path,
    delegation_id: str,
    completed_by_unit_id: str,
    result_summary: str,
) -> dict[str, Any] | None:
    load_or_init_units(fs, repo_root=repo_root, workspace_root=workspace_root)
    rows = _read_jsonl(fs, SWARM_DELEGATIONS_PATH)
    normalized_id = _normalize_text(delegation_id, max_length=80)
    normalized_unit_id = _normalize_text(completed_by_unit_id, max_length=80).lower()
    completed_at = utc_now_iso()
    updated_rows: list[dict[str, Any]] = []
    completed_row: dict[str, Any] | None = None
    for row in rows:
        if _normalize_text(str(row.get("id", "")), max_length=80) != normalized_id:
            updated_rows.append(row)
            continue
        if _normalize_text(str(row.get("target_unit_id", "")), max_length=80).lower() != normalized_unit_id:
            raise ValueError(f"Delegation {delegation_id} is not assigned to unit {completed_by_unit_id}")
        status = _normalize_text(str(row.get("status", "")), max_length=40).lower()
        if status not in {"queued", "leased"}:
            raise ValueError(f"Delegation {delegation_id} cannot be completed from status {status}")
        completed_row = {
            **row,
            "status": "completed",
            "completed_at": completed_at,
            "completed_by_unit_id": normalized_unit_id,
            "result_summary": _normalize_text(result_summary, fallback="Delegation completed.", max_length=240),
            "lease_owner": None,
            "lease_expires_at": None,
        }
        updated_rows.append(completed_row)
    if completed_row is None:
        return None
    _write_jsonl(fs, SWARM_DELEGATIONS_PATH, updated_rows)
    return completed_row


def fail_delegation(
    fs: WorkspaceFS,
    *,
    repo_root: Path,
    workspace_root: Path,
    delegation_id: str,
    failed_by_unit_id: str,
    error: str,
    retryable: bool = True,
    retry_backoff_seconds: int = DEFAULT_RETRY_BACKOFF_SECONDS,
) -> dict[str, Any] | None:
    load_or_init_units(fs, repo_root=repo_root, workspace_root=workspace_root)
    rows = _read_jsonl(fs, SWARM_DELEGATIONS_PATH)
    normalized_id = _normalize_text(delegation_id, max_length=80)
    normalized_unit_id = _normalize_text(failed_by_unit_id, max_length=80).lower()
    updated_rows: list[dict[str, Any]] = []
    failed_row: dict[str, Any] | None = None
    for row in rows:
        if _normalize_text(str(row.get("id", "")), max_length=80) != normalized_id:
            updated_rows.append(row)
            continue
        if _normalize_text(str(row.get("target_unit_id", "")), max_length=80).lower() != normalized_unit_id:
            raise ValueError(f"Delegation {delegation_id} is not assigned to unit {failed_by_unit_id}")
        status = _normalize_text(str(row.get("status", "")), max_length=40).lower()
        if status not in {"queued", "leased"}:
            raise ValueError(f"Delegation {delegation_id} cannot fail from status {status}")
        attempts = int(row.get("attempts", 0) or 0) + 1
        max_attempts = max(1, min(int(row.get("max_attempts", 2) or 2), 5))
        normalized_error = _normalize_text(error, fallback="Delegation failed.", max_length=240)
        if retryable and attempts < max_attempts:
            next_run_after = (datetime.now(timezone.utc) + timedelta(seconds=max(0, min(int(retry_backoff_seconds), 3600)))).isoformat()
            failed_row = {
                **row,
                "status": "queued",
                "attempts": attempts,
                "next_run_after": next_run_after,
                "lease_owner": None,
                "lease_expires_at": None,
                "last_error": normalized_error,
                "last_failure_reason": "retry_scheduled",
            }
        else:
            failed_row = {
                **row,
                "status": "deadlettered",
                "attempts": attempts,
                "lease_owner": None,
                "lease_expires_at": None,
                "deadlettered_at": utc_now_iso(),
                "last_error": normalized_error,
                "last_failure_reason": "deadlettered",
            }
            _append_jsonl(fs, SWARM_DEADLETTER_PATH, failed_row)
        updated_rows.append(failed_row)
    if failed_row is None:
        return None
    _write_jsonl(fs, SWARM_DELEGATIONS_PATH, updated_rows)
    return failed_row


def build_swarm_state(
    fs: WorkspaceFS,
    *,
    repo_root: Path,
    workspace_root: Path,
) -> dict[str, Any]:
    units = load_or_init_units(fs, repo_root=repo_root, workspace_root=workspace_root)
    delegations = _read_jsonl(fs, SWARM_DELEGATIONS_PATH)
    deadletter = _read_jsonl(fs, SWARM_DEADLETTER_PATH)
    ordered_delegations = sorted(
        [row for row in delegations if isinstance(row, dict)],
        key=lambda row: (
            _status_rank(str(row.get("status", ""))),
            str(row.get("ts", "")),
        ),
    )
    ordered_deadletter = sorted(
        [row for row in deadletter if isinstance(row, dict)],
        key=lambda row: str(row.get("deadlettered_at", row.get("ts", ""))),
        reverse=True,
    )
    queued_count = sum(1 for row in ordered_delegations if str(row.get("status", "")).strip().lower() == "queued")
    leased_count = sum(1 for row in ordered_delegations if str(row.get("status", "")).strip().lower() == "leased")
    completed_count = sum(
        1 for row in ordered_delegations if str(row.get("status", "")).strip().lower() == "completed"
    )
    deadletter_count = sum(
        1 for row in ordered_delegations if str(row.get("status", "")).strip().lower() == "deadlettered"
    )

    materialized_units: list[dict[str, Any]] = []
    for unit in units:
        unit_id = _normalize_text(str(unit.get("unit_id", "")), max_length=80).lower()
        unit_rows = [
            row
            for row in ordered_delegations
            if _normalize_text(str(row.get("target_unit_id", "")), max_length=80).lower() == unit_id
        ]
        unit_deadletter = [
            row
            for row in unit_rows
            if _normalize_text(str(row.get("status", "")), max_length=40).lower() == "deadlettered"
        ]
        active_rows = [
            row
            for row in unit_rows
            if _normalize_text(str(row.get("status", "")), max_length=40).lower() == "leased"
        ]
        queued_rows = [
            row
            for row in unit_rows
            if _normalize_text(str(row.get("status", "")), max_length=40).lower() == "queued"
        ]
        completed_rows = [
            row
            for row in unit_rows
            if _normalize_text(str(row.get("status", "")), max_length=40).lower() == "completed"
        ]
        if unit_deadletter:
            unit_state = "attention"
        elif active_rows:
            unit_state = "active"
        elif queued_rows:
            unit_state = "queued"
        else:
            unit_state = "ready"
        latest = unit_rows[-1] if unit_rows else None
        materialized_units.append(
            {
                **unit,
                "queued_count": len(queued_rows),
                "active_count": len(active_rows),
                "completed_count": len(completed_rows),
                "deadletter_count": len(unit_deadletter),
                "state": unit_state,
                "last_delegation_at": latest.get("ts") if isinstance(latest, dict) else None,
                "last_delegation_summary": (
                    _normalize_text(str(latest.get("summary", "")), max_length=240) if isinstance(latest, dict) else ""
                ),
            }
        )

    summary = (
        f"{len(materialized_units)} unit(s) advertised, "
        f"{queued_count} queued delegation(s), "
        f"{leased_count} active, "
        f"{deadletter_count} deadlettered."
    )
    return {
        "units": materialized_units,
        "delegations": ordered_delegations[:20],
        "deadletter": ordered_deadletter[:10],
        "unit_count": len(materialized_units),
        "queued_count": queued_count,
        "leased_count": leased_count,
        "completed_count": completed_count,
        "deadletter_count": deadletter_count,
        "summary": summary,
        "updated_at": utc_now_iso(),
    }
