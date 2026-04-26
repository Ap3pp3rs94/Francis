from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import yaml

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir, repo_root
from francis.trust.levels import get_state
from francis.world_state.snapshot import mission_continuity_snapshot


_PLANE_LABELS = {
    "P1_INTERFACE": "Interface",
    "P4_COGNITION": "Cognition",
    "P3_GOVERNANCE": "Governance",
    "P2_IDENTITY": "Identity",
    "P7_EXECUTION": "Execution",
    "P9_OBSERVABILITY": "Observability",
    "P8_MEMORY": "Memory",
}

_CONTROL_MODE_DEFS: dict[str, dict[str, str]] = {
    "observe": {
        "id": "observe",
        "label": "Observe",
        "summary": "Read-only posture. Francis watches, briefs, and keeps authority visibly constrained.",
        "implementation_status": "active",
    },
    "assist": {
        "id": "assist",
        "label": "Assist",
        "summary": "Collaborative posture. Francis can prepare work and route bounded actions through governance.",
        "implementation_status": "active",
    },
    "pilot": {
        "id": "pilot",
        "label": "Pilot",
        "summary": "Declared takeover posture. Live handoff rituals still remain approval-bounded in this build.",
        "implementation_status": "groundwork",
    },
    "away": {
        "id": "away",
        "label": "Away",
        "summary": "Declared away posture. Continuity stays visible while full away automation remains gated.",
        "implementation_status": "groundwork",
    },
}

_DEFAULT_CONTROL_MODE = "assist"


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _redact_free_text(value: Any) -> str:
    return redact_secret_text(_safe_str(value).strip())


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0
        try:
            return int(float(text))
        except Exception:
            return 0
    return 0


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _briefing_list(briefing: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return [dict(item) for item in _as_list(briefing.get(key)) if isinstance(item, dict)]


def _continuity_handoff_focus(briefing: dict[str, Any]) -> dict[str, Any]:
    for source in ("focus", "failed_preview", "deadletter_preview", "recently_completed"):
        items = _briefing_list(briefing, source)
        if items:
            return {"source": source, "item": items[0]}
    return {"source": "", "item": {}}


def _control_mode_state_path(data: Path) -> Path:
    return data / "runtime" / "control_mode.json"


def _normalize_control_mode(value: Any) -> str:
    normalized = _safe_str(value).strip().lower()
    if normalized in _CONTROL_MODE_DEFS:
        return normalized
    return _DEFAULT_CONTROL_MODE


def _read_control_mode_state(data: Path) -> dict[str, Any]:
    path = _control_mode_state_path(data)
    state = _read_json(path)
    return {
        "mode": _normalize_control_mode(state.get("mode")),
        "changed_at": _safe_int(state.get("changed_at")),
        "changed_by": _safe_str(state.get("changed_by")).strip(),
        "reason": _redact_free_text(state.get("reason")),
        "source": _safe_str(state.get("source")).strip() or ("persisted" if state else "default"),
    }


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def set_control_mode(
    mode: str,
    *,
    reason: str = "",
    actor: str = "",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_mode = _safe_str(mode).strip().lower()
    if normalized_mode not in _CONTROL_MODE_DEFS:
        allowed = ", ".join(sorted(_CONTROL_MODE_DEFS))
        raise ValueError(f"unsupported control mode: {mode} (allowed: {allowed})")

    payload = {
        "version": 1,
        "mode": normalized_mode,
        "reason": _redact_free_text(reason),
        "changed_by": _safe_str(actor).strip(),
        "changed_at": int(time.time()),
        "source": "operator_override",
        "meta": meta if isinstance(meta, dict) else {},
    }
    _atomic_write_json(_control_mode_state_path(data_dir()), payload)
    return payload


def _environment_profile_path(root: Path, profile_id: str) -> Path | None:
    env_dir = root / "config" / "environments"
    preferred = env_dir / f"{profile_id}.yaml"
    if preferred.exists():
        return preferred
    fallback = env_dir / "dev.yaml"
    if fallback.exists():
        return fallback
    return None


def _normalize_task_status(value: Any) -> str:
    status = _safe_str(value).strip().lower()
    if status == "complete":
        return "completed"
    if status == "canceled":
        return "cancelled"
    return status or "pending"


def _result_status(record: dict[str, Any]) -> str:
    result = record.get("result")
    if not isinstance(result, dict):
        return ""
    payload = result.get("data")
    if not isinstance(payload, dict):
        return ""
    return _safe_str(payload.get("status")).strip().lower()


def _pluralize(count: int, singular: str, plural: str | None = None) -> str:
    if count == 1:
        return singular
    return plural or f"{singular}s"


def _backlog_snapshot(tasks_root: Path, approvals_root: Path) -> dict[str, int]:
    backlog = {
        "pending_approvals": 0,
        "approval_pending_tasks": 0,
        "blocked_tasks": 0,
        "queued_tasks": 0,
        "running_tasks": 0,
    }

    pending_dir = approvals_root / "pending"
    if pending_dir.exists():
        try:
            backlog["pending_approvals"] = len([item for item in pending_dir.iterdir() if item.is_file()])
        except Exception:
            backlog["pending_approvals"] = 0

    if not tasks_root.exists():
        return backlog

    try:
        for item in tasks_root.iterdir():
            record_path = item if item.is_file() else item / "record.json"
            if not record_path.is_file():
                continue
            record = _read_json(record_path)
            if not record:
                continue

            raw_status = _normalize_task_status(record.get("status"))
            result_status = _result_status(record)

            if result_status in {"blocked", "denied"}:
                backlog["blocked_tasks"] += 1
                continue
            if result_status in {"pending", "needs_approval"}:
                backlog["approval_pending_tasks"] += 1
                continue
            if raw_status == "running":
                backlog["running_tasks"] += 1
                continue
            if raw_status in {"pending", "accepted"}:
                backlog["queued_tasks"] += 1
    except Exception:
        return backlog

    return backlog


def _focus_plane(backlog: dict[str, int]) -> dict[str, str]:
    pending_approvals = int(backlog.get("pending_approvals") or 0)
    approval_pending_tasks = int(backlog.get("approval_pending_tasks") or 0)
    blocked_tasks = int(backlog.get("blocked_tasks") or 0)
    running_tasks = int(backlog.get("running_tasks") or 0)
    queued_tasks = int(backlog.get("queued_tasks") or 0)
    blocked_missions = int(backlog.get("blocked_missions") or 0)
    deadlettered_missions = int(backlog.get("deadlettered_missions") or 0)
    active_missions = int(backlog.get("active_missions") or 0)
    queued_missions = int(backlog.get("queued_missions") or 0)
    completed_missions = int(backlog.get("completed_missions") or 0)

    if pending_approvals > 0:
        plane_id = "P3_GOVERNANCE"
        reason = f"{pending_approvals} {_pluralize(pending_approvals, 'approval')} waiting for operator review."
    elif approval_pending_tasks > 0:
        plane_id = "P3_GOVERNANCE"
        reason = f"{approval_pending_tasks} {_pluralize(approval_pending_tasks, 'task')} waiting for approval before execution."
    elif blocked_tasks > 0:
        plane_id = "P3_GOVERNANCE"
        reason = f"{blocked_tasks} {_pluralize(blocked_tasks, 'task')} blocked by policy or trust gates."
    elif running_tasks > 0:
        plane_id = "P7_EXECUTION"
        reason = f"{running_tasks} {_pluralize(running_tasks, 'task')} running through execution."
    elif queued_tasks > 0:
        plane_id = "P7_EXECUTION"
        reason = f"{queued_tasks} {_pluralize(queued_tasks, 'task')} queued for execution."
    elif blocked_missions > 0:
        plane_id = "P3_GOVERNANCE"
        reason = (
            f"{blocked_missions} {_pluralize(blocked_missions, 'mission')} blocked and waiting for operator handback."
        )
    elif deadlettered_missions > 0:
        plane_id = "P3_GOVERNANCE"
        reason = f"{deadlettered_missions} {_pluralize(deadlettered_missions, 'mission')} sitting in deadletter review."
    elif active_missions > 0:
        plane_id = "P7_EXECUTION"
        reason = f"{active_missions} {_pluralize(active_missions, 'mission')} actively carrying work forward."
    elif queued_missions > 0:
        plane_id = "P8_MEMORY"
        reason = f"{queued_missions} {_pluralize(queued_missions, 'mission')} queued and carrying continuity forward."
    elif completed_missions > 0:
        plane_id = "P8_MEMORY"
        reason = f"{completed_missions} completed {_pluralize(completed_missions, 'mission')} ready for review."
    else:
        plane_id = "P1_INTERFACE"
        reason = "Console is idle and ready for the next operator request."

    return {
        "plane_id": plane_id,
        "label": _PLANE_LABELS.get(plane_id, plane_id),
        "reason": reason,
    }


def _control_mode_detail(
    mode_id: str, writes_state: str, backlog: dict[str, int], state: dict[str, Any]
) -> dict[str, Any]:
    definition = _CONTROL_MODE_DEFS.get(mode_id, _CONTROL_MODE_DEFS[_DEFAULT_CONTROL_MODE])
    pending_approvals = int(backlog.get("pending_approvals") or 0)
    approval_pending_tasks = int(backlog.get("approval_pending_tasks") or 0)
    queued_tasks = int(backlog.get("queued_tasks") or 0)
    blocked_tasks = int(backlog.get("blocked_tasks") or 0)

    summary = definition["summary"]
    if mode_id == "observe":
        summary = "Read-only posture. Francis stays visible, cites state, and does not claim write authority."
    elif mode_id == "assist" and pending_approvals > 0:
        summary = (
            f"Assist posture with {pending_approvals} {_pluralize(pending_approvals, 'approval')} waiting for review."
        )
    elif mode_id == "pilot":
        summary = "Pilot is declared and visible. Approval gates still hold until the takeover flow ships."
    elif mode_id == "away":
        summary = "Away is declared and visible. Francis can hold continuity, but risky work remains approval-gated."
    elif queued_tasks > 0 or approval_pending_tasks > 0 or blocked_tasks > 0:
        total = queued_tasks + approval_pending_tasks + blocked_tasks
        summary = f"{definition['summary']} {total} {_pluralize(total, 'task')} currently sit in the governed backlog."

    return {
        "id": definition["id"],
        "label": definition["label"],
        "summary": summary,
        "writes": "blocked" if mode_id == "observe" else writes_state,
        "implementation_status": definition["implementation_status"],
        "changed_at": _safe_int(state.get("changed_at")),
        "changed_by": _safe_str(state.get("changed_by")).strip(),
        "reason": _safe_str(state.get("reason")).strip(),
        "source": _safe_str(state.get("source")).strip() or "default",
    }


def _available_control_modes(active_mode_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for mode_id in ("observe", "assist", "pilot", "away"):
        definition = _CONTROL_MODE_DEFS[mode_id]
        items.append(
            {
                "id": definition["id"],
                "label": definition["label"],
                "summary": definition["summary"],
                "implementation_status": definition["implementation_status"],
                "active": mode_id == active_mode_id,
            }
        )
    return items


def _trust_posture(governance_mode: str, minimum_trust: int) -> str:
    normalized = governance_mode.strip().lower()
    if normalized == "strict" or minimum_trust >= 2:
        return "strict"
    if normalized == "policy" or minimum_trust == 1:
        return "standard"
    return "relaxed"


def _web_access_state(profile: dict[str, Any]) -> str:
    features = profile.get("features") if isinstance(profile.get("features"), dict) else {}
    web_learning = features.get("web_learning") if isinstance(features.get("web_learning"), dict) else {}
    network = profile.get("network") if isinstance(profile.get("network"), dict) else {}
    egress = network.get("egress") if isinstance(network.get("egress"), dict) else {}

    if not bool(web_learning.get("enabled")):
        return "disabled"
    if not bool(egress.get("enabled")):
        return "disabled"

    allow_search = bool(web_learning.get("allow_search"))
    allow_fetch = bool(web_learning.get("allow_fetch"))
    allow_ingest = bool(web_learning.get("allow_ingest"))

    if allow_search and allow_fetch and allow_ingest:
        return "enabled"
    if allow_search or allow_fetch or allow_ingest:
        return "limited"
    return "disabled"


def _writes_state(run_mode: str, runtime_mode: str, governance_mode: str, minimum_trust: int) -> str:
    normalized_run_mode = run_mode.strip().lower()
    normalized_runtime_mode = runtime_mode.strip().lower()
    normalized_governance_mode = governance_mode.strip().lower()

    if normalized_run_mode in {"readonly", "read_only"}:
        return "blocked"
    if normalized_runtime_mode in {"airgapped", "regulated", "safety_critical"}:
        return "restricted"
    if normalized_governance_mode == "strict" or minimum_trust > 0:
        return "restricted"
    return "enabled"


def snapshot() -> dict[str, Any]:
    root = repo_root()
    data = data_dir()
    env_profile = _safe_str(os.getenv("FRANCIS_ENV_PROFILE")).strip() or "dev"
    run_mode = _safe_str(os.getenv("FRANCIS_RUN_MODE")).strip() or "api"

    profile_path = _environment_profile_path(root, env_profile)
    profile = _read_yaml(profile_path) if isinstance(profile_path, Path) else {}
    profile_meta = profile.get("profile") if isinstance(profile.get("profile"), dict) else {}
    runtime = profile.get("runtime") if isinstance(profile.get("runtime"), dict) else {}
    governance = profile.get("governance") if isinstance(profile.get("governance"), dict) else {}
    approvals = governance.get("approvals") if isinstance(governance.get("approvals"), dict) else {}
    trust_cfg = governance.get("trust") if isinstance(governance.get("trust"), dict) else {}
    network = profile.get("network") if isinstance(profile.get("network"), dict) else {}
    egress = network.get("egress") if isinstance(network.get("egress"), dict) else {}
    ui = profile.get("ui") if isinstance(profile.get("ui"), dict) else {}
    banner = ui.get("banner") if isinstance(ui.get("banner"), dict) else {}

    state = get_state()
    trust_level = _safe_int(state.get("global_level"))
    minimum_trust = _safe_int(trust_cfg.get("minimum_operational_trust"))
    governance_mode = _safe_str(approvals.get("mode")).strip().lower()
    runtime_mode = _safe_str(runtime.get("mode")).strip() or env_profile

    backlog = _backlog_snapshot(data / "tasks", data / "approvals")
    continuity = mission_continuity_snapshot(recent_limit=5, queue_limit=3, deadletter_limit=2, activity_log_limit=20)
    mission_counts = (
        continuity.get("mission_status_counts") if isinstance(continuity.get("mission_status_counts"), dict) else {}
    )
    backlog.update(
        {
            "queued_missions": _safe_int(mission_counts.get("queued")),
            "blocked_missions": _safe_int(mission_counts.get("blocked")),
            "active_missions": _safe_int(mission_counts.get("active")),
            "completed_missions": _safe_int(mission_counts.get("completed")),
            "deadlettered_missions": _safe_int(mission_counts.get("deadlettered")),
        }
    )
    focus = _focus_plane(backlog)
    control_mode_state = _read_control_mode_state(data)
    writes_state = _writes_state(run_mode, runtime_mode, governance_mode, minimum_trust)
    control_mode = _control_mode_detail(control_mode_state["mode"], writes_state, backlog, control_mode_state)

    operator_notes = profile_meta.get("operator_notes") if isinstance(profile_meta.get("operator_notes"), list) else []
    notes = [_safe_str(item).strip() for item in operator_notes if _safe_str(item).strip()][:3]
    mission_briefing = _as_dict(continuity.get("mission_briefing"))
    handoff_focus = _continuity_handoff_focus(mission_briefing)

    return {
        "ok": True,
        "subsystem": "operator_mode",
        "generated_at": time.time(),
        "environment": {
            "id": _safe_str(profile_meta.get("id")).strip() or env_profile,
            "name": _safe_str(profile_meta.get("name")).strip() or env_profile.title(),
            "description": _safe_str(profile_meta.get("description")).strip(),
            "label": _safe_str(ui.get("label")).strip() or env_profile.upper(),
            "banner_text": _safe_str(banner.get("text")).strip(),
            "run_mode": run_mode,
            "runtime_mode": runtime_mode,
            "profile_path": str(profile_path) if isinstance(profile_path, Path) else "",
        },
        "posture": {
            "governance_mode": governance_mode or "unknown",
            "trust_posture": _trust_posture(governance_mode, minimum_trust),
            "trust_level": trust_level,
            "minimum_operational_trust": minimum_trust,
            "web_access": _web_access_state(profile),
            "writes": writes_state,
            "network_egress": "enabled" if bool(egress.get("enabled")) else "disabled",
        },
        "control_mode": control_mode,
        "available_modes": _available_control_modes(control_mode["id"]),
        "focus": focus,
        "backlog": backlog,
        "continuity": {
            "headline": _safe_str(mission_briefing.get("headline")).strip(),
            "mission_counts": _as_dict(mission_briefing.get("counts")),
            "focus": _briefing_list(mission_briefing, "focus"),
            "recently_completed": _briefing_list(mission_briefing, "recently_completed"),
            "failed_preview": _briefing_list(mission_briefing, "failed_preview"),
            "deadletter_preview": _briefing_list(mission_briefing, "deadletter_preview"),
            "handoff_focus": _as_dict(handoff_focus.get("item")),
            "handoff_focus_source": _safe_str(handoff_focus.get("source")).strip(),
        },
        "notes": notes,
    }
