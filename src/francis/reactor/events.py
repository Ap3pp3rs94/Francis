from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_governed_display_value, redact_governed_value
from francis.kernel.paths import data_dir

VALID_TRIGGER_SOURCES = frozenset(
    {
        "approval_decision",
        "federated_handoff",
        "forge_proposal",
        "mission_queue",
        "observer_anomaly",
        "schedule_window",
        "telemetry_event",
        "user_request",
    }
)
_VALID_MODES = frozenset({"observe", "assist", "pilot", "away"})
_VALID_RISK_TIERS = frozenset({"readonly", "normal", "critical", "safety_critical"})
_EXECUTION_ACTION_CLASSES = frozenset({"dispatch", "execute", "mutate", "operation_run", "plugin_run"})
_DEFAULT_STOP_CONDITIONS = (
    "objective_reached",
    "approval_required",
    "budget_exhausted",
    "verification_failed",
    "policy_denied",
    "user_interrupted",
)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _safe_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        return [text for item in value if (text := _safe_str(item).strip())]
    text = _safe_str(value).strip()
    return [text] if text else []


def _now_s() -> int:
    return int(time.time())


def _event_root() -> Path:
    return data_dir() / "reactor" / "events"


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _event_id(payload: dict[str, Any], created_ts: int) -> str:
    seed = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    digest = hashlib.sha256(f"{created_ts}:{time.time_ns()}:{seed}".encode("utf-8")).hexdigest()[:12]
    return f"reactor_evt_{created_ts}_{digest}"


def _bounds(payload: dict[str, Any]) -> dict[str, Any]:
    stop_conditions = _as_list(payload.get("stop_conditions")) or list(_DEFAULT_STOP_CONDITIONS)
    return {
        "max_actions": _safe_int(payload.get("max_actions"), default=1, minimum=1, maximum=50),
        "max_runtime_seconds": _safe_int(payload.get("max_runtime_seconds"), default=60, minimum=1, maximum=86_400),
        "max_retries": _safe_int(payload.get("max_retries"), default=0, minimum=0, maximum=10),
        "backoff_seconds": _safe_int(payload.get("backoff_seconds"), default=0, minimum=0, maximum=3_600),
        "resource_budget": _safe_str(payload.get("resource_budget")).strip(),
        "stop_conditions": stop_conditions,
    }


def _classification(payload: dict[str, Any], bounds: dict[str, Any]) -> dict[str, Any]:
    trigger_source = _safe_str(payload.get("trigger_source") or payload.get("source")).strip().lower()
    trigger_type = _safe_str(payload.get("trigger_type") or payload.get("type")).strip().lower() or trigger_source
    risk_tier = _safe_str(payload.get("risk_tier")).strip().lower() or "normal"
    if risk_tier not in _VALID_RISK_TIERS:
        risk_tier = "normal"
    mode = _safe_str(payload.get("mode")).strip().lower() or "assist"
    if mode not in _VALID_MODES:
        mode = "assist"
    action_class = _safe_str(payload.get("action_class")).strip().lower() or _default_action_class(trigger_source)
    approval_required = bool(payload.get("approval_required")) or risk_tier in {"critical", "safety_critical"}
    dispatch_allowed = not approval_required
    stable_state = "awaiting_dispatch"
    next_step = "dispatch_with_explicit_budget_and_receipt"

    if mode == "observe" and action_class in _EXECUTION_ACTION_CLASSES:
        dispatch_allowed = False
        stable_state = "blocked_by_mode"
        next_step = "switch_mode_or_create_approval_before_dispatch"
    elif approval_required:
        stable_state = "awaiting_approval"
        next_step = "request_or_attach_approval_before_dispatch"
    elif bounds["max_actions"] <= 0:
        dispatch_allowed = False
        stable_state = "blocked_by_budget"
        next_step = "set_positive_action_budget_before_dispatch"

    return {
        "trigger_source": trigger_source,
        "trigger_type": trigger_type,
        "mode": mode,
        "risk_tier": risk_tier,
        "action_class": action_class,
        "approval_required": approval_required,
        "dispatch_allowed": dispatch_allowed,
        "stable_state": stable_state,
        "next_step": next_step,
    }


def _default_action_class(trigger_source: str) -> str:
    if trigger_source in {"observer_anomaly", "telemetry_event"}:
        return "classify"
    if trigger_source == "approval_decision":
        return "resume"
    if trigger_source == "mission_queue":
        return "mission_tick"
    if trigger_source == "forge_proposal":
        return "proposal_review"
    return "classify"


def _validation_error(payload: dict[str, Any]) -> str:
    trigger_source = _safe_str(payload.get("trigger_source") or payload.get("source")).strip().lower()
    summary = _safe_str(payload.get("summary") or payload.get("reason")).strip()
    if trigger_source not in VALID_TRIGGER_SOURCES:
        return "invalid_trigger_source"
    if not summary:
        return "summary_required"
    return ""


def enqueue_event(payload: dict[str, Any]) -> dict[str, Any]:
    redacted_payload = redact_governed_value(payload)
    data = redacted_payload if isinstance(redacted_payload, dict) else {}
    error = _validation_error(data)
    if error:
        return {
            "ok": False,
            "applied": False,
            "error": error,
            "valid_trigger_sources": sorted(VALID_TRIGGER_SOURCES),
        }

    created_ts = _now_s()
    bounds = _bounds(data)
    classification = _classification(data, bounds)
    event_id = _event_id(data, created_ts)
    status = "queued"
    trigger_source = classification["trigger_source"]
    trigger = {
        "source": trigger_source,
        "type": classification["trigger_type"],
        "summary": _safe_str(data.get("summary") or data.get("reason")).strip(),
        "reason": _safe_str(data.get("reason")).strip(),
        "mission_id": _safe_str(data.get("mission_id")).strip(),
        "operation_id": _safe_str(data.get("operation_id")).strip(),
        "approval_id": _safe_str(data.get("approval_id")).strip(),
        "trace_id": _safe_str(data.get("trace_id")).strip(),
        "run_id": _safe_str(data.get("run_id")).strip(),
        "metadata": data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
    }
    record = {
        "kind": "reactor.event",
        "event_id": event_id,
        "id": event_id,
        "status": status,
        "created_ts": created_ts,
        "updated_ts": created_ts,
        "trigger": {key: value for key, value in trigger.items() if value not in ("", {}, [])},
        "classification": classification,
        "bounds": bounds,
        "dispatch": {
            "status": "not_started",
            "allowed": bool(classification.get("dispatch_allowed")),
            "applied": False,
            "engine": "not_implemented",
        },
        "stable_state": classification["stable_state"],
        "decision_journal": [
            {
                "kind": "reactor.intake.classified",
                "ts": created_ts,
                "decision": status,
                "stable_state": classification["stable_state"],
                "next_step": classification["next_step"],
            }
        ],
        "receipt": {
            "kind": "reactor.intake.receipt",
            "event_id": event_id,
            "status": status,
            "trigger_source": trigger_source,
            "stable_state": classification["stable_state"],
            "next_step": classification["next_step"],
        },
        "governance": {
            "plane": "P4_COGNITION",
            "gate": "reactor_trigger_intake",
            "execution_authority": False,
            "approval_authority": False,
            "promotion_authority": False,
            "memory_write": False,
            "dispatch_authority": False,
            "next_step": classification["next_step"],
        },
    }
    path = _event_root() / f"{event_id}.json"
    record["path"] = str(path)
    _atomic_write_json(path, record)
    return {"ok": True, "applied": True, "event_id": event_id, "event": _display(record)}


def _display(record: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_governed_display_value(record)
    return redacted if isinstance(redacted, dict) else {}


def _read_event(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return _display(raw) if isinstance(raw, dict) else None


def list_events(
    *,
    limit: int = 200,
    status: str | None = None,
    trigger_source: str | None = None,
) -> list[dict[str, Any]]:
    root = _event_root()
    if not root.exists():
        return []
    status_filter = _safe_str(status).strip().lower()
    source_filter = _safe_str(trigger_source).strip().lower()
    items: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        if not path.is_file():
            continue
        item = _read_event(path)
        if not item:
            continue
        raw_trigger = item.get("trigger")
        trigger = raw_trigger if isinstance(raw_trigger, dict) else {}
        if status_filter and _safe_str(item.get("status")).strip().lower() != status_filter:
            continue
        if source_filter and _safe_str(trigger.get("source")).strip().lower() != source_filter:
            continue
        items.append(item)
    items.sort(
        key=lambda item: (
            _safe_int(item.get("created_ts"), default=0, minimum=0, maximum=2_147_483_647),
            _safe_str(item.get("event_id")),
        ),
        reverse=True,
    )
    return items[: max(1, min(int(limit), 5000))]


def get_event(event_id: str) -> dict[str, Any] | None:
    cleaned = _safe_str(event_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return None
    path = _event_root() / f"{cleaned}.json"
    if not path.exists() or not path.is_file():
        return None
    return _read_event(path)


def reactor_status() -> dict[str, Any]:
    items = list_events(limit=5000)
    status_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    stable_state_counts: dict[str, int] = {}
    for item in items:
        status = _safe_str(item.get("status")).strip() or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        stable_state = _safe_str(item.get("stable_state")).strip() or "unknown"
        stable_state_counts[stable_state] = stable_state_counts.get(stable_state, 0) + 1
        raw_trigger = item.get("trigger")
        trigger = raw_trigger if isinstance(raw_trigger, dict) else {}
        source = _safe_str(trigger.get("source")).strip() or "unknown"
        source_counts[source] = source_counts.get(source, 0) + 1
    return {
        "ok": True,
        "status": "ready",
        "total": len(items),
        "status_counts": status_counts,
        "trigger_source_counts": source_counts,
        "stable_state_counts": stable_state_counts,
        "dispatch_engine": "not_implemented",
        "valid_trigger_sources": sorted(VALID_TRIGGER_SOURCES),
        "governance": {
            "gate": "reactor_trigger_intake",
            "execution_authority": False,
            "approval_authority": False,
            "dispatch_authority": False,
        },
    }
