from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import yaml

from francis.kernel.paths import data_dir, repo_root
from francis.trust.levels import get_state


_PLANE_LABELS = {
    "P1_INTERFACE": "Interface",
    "P4_COGNITION": "Cognition",
    "P3_GOVERNANCE": "Governance",
    "P2_IDENTITY": "Identity",
    "P7_EXECUTION": "Execution",
    "P9_OBSERVABILITY": "Observability",
    "P8_MEMORY": "Memory",
}


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


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
    else:
        plane_id = "P1_INTERFACE"
        reason = "Console is idle and ready for the next operator request."

    return {
        "plane_id": plane_id,
        "label": _PLANE_LABELS.get(plane_id, plane_id),
        "reason": reason,
    }


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
    focus = _focus_plane(backlog)

    operator_notes = profile_meta.get("operator_notes") if isinstance(profile_meta.get("operator_notes"), list) else []
    notes = [_safe_str(item).strip() for item in operator_notes if _safe_str(item).strip()][:3]

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
            "writes": _writes_state(run_mode, runtime_mode, governance_mode, minimum_trust),
            "network_egress": "enabled" if bool(egress.get("enabled")) else "disabled",
        },
        "focus": focus,
        "backlog": backlog,
        "notes": notes,
    }
