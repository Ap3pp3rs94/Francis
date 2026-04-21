from __future__ import annotations

import importlib.metadata
import json
import logging
import os
import platform
import socket
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from francis.api.routes._operator_posture import posture_write_guard
from francis.kernel import feature_flags
from francis.kernel.health import health_report
from francis.kernel.paths import data_dir
from francis.kernel.services import services_action, services_status
from francis.kernel.stack import stack_status
from francis.settings import Settings
from francis.telemetry.audit import record
from francis.telemetry.tracing import start_span
from francis.world_state.operator_mode import set_control_mode, snapshot as operator_mode_snapshot
from francis.world_state.orb import snapshot as orb_status_snapshot
from francis.world_state.snapshot import (
    observer_incident_snapshot,
    observer_scan_event_projection,
    observer_scan_history,
    observer_summary,
    snapshot as world_state_snapshot,
)

router = APIRouter()
logger = logging.getLogger(__name__)

_APP_STARTED_TS = int(time.time())
_INSTANCE_ID = f"{socket.gethostname()}:{os.getpid()}"
_MUTATION_OPS = {"set", "unset", "merge", "append", "remove"}


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _now_s() -> int:
    return int(time.time())


def _now_ms() -> int:
    return int(time.time() * 1000)


def _runtime_settings_path() -> Path:
    return data_dir() / "runtime" / "system_settings.json"


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _read_runtime_overrides() -> dict[str, Any]:
    path = _runtime_settings_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    cfg = raw.get("config")
    if not isinstance(cfg, dict):
        return {}
    return cfg


def _write_runtime_overrides(config: dict[str, Any]) -> None:
    _atomic_write_json(
        _runtime_settings_path(),
        {
            "version": 1,
            "updated_at": _now_s(),
            "config": config,
        },
    )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = value
    return merged


def _settings_dict() -> dict[str, Any]:
    settings_obj: Any
    try:
        settings_obj = Settings()
    except Exception:
        settings_obj = Settings

    if hasattr(settings_obj, "model_dump") and callable(getattr(settings_obj, "model_dump")):
        dumped = settings_obj.model_dump()  # type: ignore[attr-defined]
        if isinstance(dumped, dict):
            return dumped

    if hasattr(settings_obj, "__dict__"):
        return {
            key: value for key, value in vars(settings_obj).items() if not key.startswith("_") and not callable(value)
        }
    return {}


def _get_version() -> str:
    try:
        return importlib.metadata.version("francis")
    except Exception:
        try:
            import francis  # type: ignore

            return _safe_str(getattr(francis, "__version__", "unknown")) or "unknown"
        except Exception:
            return "unknown"


def _system_info_record() -> dict[str, Any]:
    return {
        "service": "francis-api",
        "instance_id": _INSTANCE_ID,
        "version": _get_version(),
        "env_profile": _safe_str(os.getenv("FRANCIS_ENV_PROFILE")).strip() or "dev",
        "run_mode": _safe_str(os.getenv("FRANCIS_RUN_MODE")).strip() or "api",
        "started_ts": _APP_STARTED_TS,
        "uptime_s": max(0, _now_s() - _APP_STARTED_TS),
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "python": {
            "version": sys.version.split()[0],
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
    }


def _effective_config_snapshot() -> dict[str, Any]:
    base = _settings_dict()
    runtime_overrides = _read_runtime_overrides()
    merged = _deep_merge(base, runtime_overrides)

    merged["francis_env_profile"] = _safe_str(os.getenv("FRANCIS_ENV_PROFILE")).strip() or "dev"
    merged["francis_run_mode"] = _safe_str(os.getenv("FRANCIS_RUN_MODE")).strip() or "api"
    merged["francis_log_level"] = (
        _safe_str(os.getenv("FRANCIS_LOG_LEVEL")).strip() or _safe_str(merged.get("francis_log_level")) or "INFO"
    )

    merged["feature_flags"] = {
        _safe_str(item.get("key")): bool(item.get("enabled"))
        for item in feature_flags.list_flags()
        if _safe_str(item.get("key"))
    }
    return merged


def _parse_mutation_path(path: str) -> list[str]:
    raw = _safe_str(path).strip()
    if not raw:
        raise ValueError("path is required")
    if raw.startswith("/"):
        tokens: list[str] = []
        for part in raw.split("/")[1:]:
            token = part.replace("~1", "/").replace("~0", "~").strip()
            if token:
                tokens.append(token)
        if not tokens:
            raise ValueError("path must target at least one key")
        return tokens
    tokens = [part.strip() for part in raw.split(".") if part.strip()]
    if not tokens:
        raise ValueError("path must target at least one key")
    return tokens


def _get_parent_node(root: dict[str, Any], tokens: list[str], *, create_missing: bool) -> tuple[dict[str, Any], str]:
    if not tokens:
        raise ValueError("path tokens are required")
    if len(tokens) == 1:
        return root, tokens[0]

    node: dict[str, Any] = root
    for token in tokens[:-1]:
        current = node.get(token)
        if isinstance(current, dict):
            node = current
            continue
        if current is None:
            if not create_missing:
                raise KeyError(token)
            node[token] = {}
            node = node[token]
            continue
        if not create_missing:
            raise TypeError(f"path segment is not an object: {token}")
        node[token] = {}
        node = node[token]
    return node, tokens[-1]


def _deep_copy_dict(obj: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(obj, ensure_ascii=False, default=str))


def _observer_receipt_id() -> str:
    return f"obs_scan_{_now_ms()}_{uuid.uuid4().hex[:8]}"


def _system_write_posture_guard(action_label: str) -> str:
    return posture_write_guard(
        action_label,
        verification_prefix="System mutation is blocked until operator posture can be verified",
        observe_message="Observe mode keeps system mutations read-only.",
        writes_blocked_message="Current operator posture blocks system mutations.",
    )


def _observer_state_payload(*, recent_limit: int = 10) -> dict[str, Any]:
    snapshot = observer_incident_snapshot()
    summary = observer_summary(snapshot)
    return {
        "ok": bool(snapshot.get("ok")),
        "subsystem": "observer",
        "generated_at": float(snapshot.get("generated_at") or 0.0),
        "observed_at": float(snapshot.get("generated_at") or 0.0),
        "headline": summary["headline"],
        "decision": summary["decision"],
        "counts": summary["counts"],
        "focus": summary["focus"],
        "probes": summary["probe_statuses"],
        "anomaly": summary["anomaly"],
        "incidents": snapshot.get("incidents") if isinstance(snapshot.get("incidents"), list) else [],
        "task_status_counts": snapshot.get("task_status_counts")
        if isinstance(snapshot.get("task_status_counts"), dict)
        else {},
        "recent_tasks": snapshot.get("recent_tasks") if isinstance(snapshot.get("recent_tasks"), list) else [],
        "pending_approvals": snapshot.get("pending_approvals")
        if isinstance(snapshot.get("pending_approvals"), list)
        else [],
        "recent_scans": observer_scan_history(limit=recent_limit),
    }


def _apply_mutation(config: dict[str, Any], *, op: str, path: str, value: Any) -> tuple[dict[str, Any], Any]:
    op_normalized = _safe_str(op).strip().lower()
    if op_normalized not in _MUTATION_OPS:
        raise ValueError(f"unsupported op: {op}")

    tokens = _parse_mutation_path(path)
    updated = _deep_copy_dict(config)

    if op_normalized == "set":
        parent, leaf = _get_parent_node(updated, tokens, create_missing=True)
        parent[leaf] = value
        return updated, parent[leaf]

    if op_normalized == "unset":
        parent, leaf = _get_parent_node(updated, tokens, create_missing=False)
        removed = parent.pop(leaf, None)
        return updated, removed

    if op_normalized == "merge":
        if not isinstance(value, dict):
            raise ValueError("merge op requires value to be an object")
        parent, leaf = _get_parent_node(updated, tokens, create_missing=True)
        current = parent.get(leaf)
        if current is None:
            parent[leaf] = dict(value)
            return updated, parent[leaf]
        if not isinstance(current, dict):
            raise TypeError("merge target is not an object")
        merged = dict(current)
        merged.update(value)
        parent[leaf] = merged
        return updated, parent[leaf]

    if op_normalized == "append":
        parent, leaf = _get_parent_node(updated, tokens, create_missing=True)
        current = parent.get(leaf)
        if current is None:
            parent[leaf] = [value]
            return updated, parent[leaf]
        if not isinstance(current, list):
            raise TypeError("append target is not a list")
        current.append(value)
        parent[leaf] = current
        return updated, parent[leaf]

    # remove
    parent, leaf = _get_parent_node(updated, tokens, create_missing=False)
    current = parent.get(leaf)
    if current is None:
        return updated, None
    if isinstance(current, list):
        if value is None:
            if current:
                current.pop()
        elif isinstance(value, int):
            if -len(current) <= value < len(current):
                current.pop(value)
        else:
            try:
                current.remove(value)
            except ValueError:
                pass
        parent[leaf] = current
        return updated, current
    if isinstance(current, dict):
        if value is None:
            return updated, current
        remove_key = _safe_str(value).strip()
        if remove_key:
            current.pop(remove_key, None)
        parent[leaf] = current
        return updated, current
    removed = parent.pop(leaf, None)
    return updated, removed


class ServiceActionIn(BaseModel):
    action: str
    services: list[str] = Field(default_factory=list)


class ConfigMutationIn(BaseModel):
    op: str
    path: str
    value: Any = None
    reason: str | None = None
    domain: str | None = None
    actor: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class FlagSetIn(BaseModel):
    enabled: bool
    reason: str | None = None
    source: str = "api"
    description: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)


class FlagSetNamedIn(FlagSetIn):
    key: str


class ControlModeSetIn(BaseModel):
    mode: str
    reason: str | None = None
    actor: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class ObserverScanIn(BaseModel):
    reason: str | None = None
    actor: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


@router.get("/health")
def health() -> dict[str, object]:
    try:
        return {"ok": True, "report": health_report()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/info")
def info() -> dict[str, object]:
    try:
        return {"ok": True, "info": _system_info_record()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/status")
def status() -> dict[str, object]:
    try:
        payload = _system_info_record()
        payload["status"] = "ready"
        payload["ok"] = True
        return payload
    except Exception as exc:
        return {"ok": False, "status": "error", "error": str(exc)}


@router.get("/stack")
def stack() -> dict[str, object]:
    try:
        return {"ok": True, "report": stack_status(probe_runtime=True)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/services")
def services() -> dict[str, object]:
    try:
        return {"ok": True, "report": services_status()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/world_state")
@router.get("/world-state")
def world_state() -> dict[str, object]:
    try:
        return world_state_snapshot()
    except Exception as exc:
        return {"ok": False, "error": str(exc), "subsystem": "world_state"}


@router.get("/observer")
def observer(recent_limit: int = 10) -> dict[str, object]:
    try:
        return _observer_state_payload(recent_limit=recent_limit)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "subsystem": "observer"}


@router.get("/observer/events")
@router.get("/observer/log")
@router.get("/observer/audit")
def observer_events(
    limit: int = 20,
    status: str | None = None,
    decision: str | None = None,
) -> dict[str, object]:
    try:
        items = observer_scan_history(limit=limit, status=_safe_str(status), decision=_safe_str(decision))
        return {
            "ok": True,
            "subsystem": "observer_events",
            "items": items,
            "history": items,
            "total": len(items),
            "limit": max(1, min(int(limit), 100)),
        }
    except Exception as exc:
        return {
            "ok": False,
            "subsystem": "observer_events",
            "items": [],
            "history": [],
            "total": 0,
            "limit": max(1, min(int(limit), 100)),
            "error": str(exc),
        }


@router.post("/observer/scan")
def observer_scan(payload: ObserverScanIn | None = None, recent_limit: int = 10) -> dict[str, object]:
    try:
        body = payload or ObserverScanIn()
        with start_span("observer.scan"):
            snapshot = observer_incident_snapshot()
            summary = observer_summary(snapshot)
            receipt = record(
                "observer.scan",
                status="ok" if int(summary["counts"].get("active") or 0) <= 0 else "attention",
                subsystem="observer",
                receipt_id=_observer_receipt_id(),
                generated_at=float(snapshot.get("generated_at") or 0.0),
                decision=summary["decision"],
                headline=summary["headline"],
                incident_count=int(summary["counts"].get("active") or 0),
                counts=summary["counts"],
                incident_ids=summary["incident_ids"],
                probes=summary["probes"],
                focus=summary["focus"],
                probe_statuses=summary["probe_statuses"],
                anomaly=summary["anomaly"],
                actor=body.actor or "operator",
                reason=body.reason or "manual_scan",
                meta=body.meta,
            )
        response = _observer_state_payload(recent_limit=recent_limit)
        response["receipt"] = observer_scan_event_projection(receipt)
        return response
    except Exception as exc:
        return {"ok": False, "error": str(exc), "subsystem": "observer"}


@router.get("/orb_status")
@router.get("/orb-status")
@router.get("/orb")
def orb_status() -> dict[str, object]:
    try:
        return orb_status_snapshot()
    except Exception as exc:
        return {"ok": False, "error": str(exc), "subsystem": "orb_status"}


@router.get("/operator_mode")
@router.get("/operator-mode")
def operator_mode() -> dict[str, object]:
    try:
        return operator_mode_snapshot()
    except Exception as exc:
        return {"ok": False, "error": str(exc), "subsystem": "operator_mode"}


@router.post("/operator_mode")
@router.post("/operator-mode")
def update_operator_mode(payload: ControlModeSetIn) -> dict[str, object]:
    try:
        set_control_mode(
            payload.mode,
            reason=payload.reason or "",
            actor=payload.actor or "",
            meta=payload.meta,
        )
        state = operator_mode_snapshot()
        state["applied"] = True
        state["status"] = "applied"
        state["message"] = "control_mode_updated"
        return state
    except Exception as exc:
        return {
            "ok": False,
            "applied": False,
            "status": "error",
            "message": str(exc),
            "subsystem": "operator_mode",
        }


@router.post("/services/action")
def service_action(payload: ServiceActionIn) -> dict[str, object]:
    blocked_reason = _system_write_posture_guard("requesting service actions")
    if blocked_reason:
        return {"ok": False, "applied": False, "status": "blocked", "error": blocked_reason}
    try:
        return services_action(payload.action, payload.services)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/flags")
@router.get("/feature_flags")
@router.get("/features")
def list_feature_flags() -> dict[str, object]:
    try:
        return {"items": feature_flags.list_flags()}
    except Exception as exc:
        return {"items": [], "error": str(exc)}


@router.post("/flags/set")
@router.post("/feature_flags/set")
def set_feature_flag(payload: FlagSetNamedIn) -> dict[str, object]:
    body = FlagSetIn(
        enabled=payload.enabled,
        reason=payload.reason,
        source=payload.source,
        description=payload.description,
        meta=payload.meta,
    )
    return set_feature_flag_for_key(payload.key, body)


@router.post("/flags/{key}")
@router.post("/feature_flags/{key}")
def set_feature_flag_for_key(key: str, payload: FlagSetIn) -> dict[str, object]:
    blocked_reason = _system_write_posture_guard("changing feature flags")
    if blocked_reason:
        return {"ok": False, "applied": False, "status": "blocked", "error": blocked_reason}
    try:
        item = feature_flags.set_flag(
            key,
            payload.enabled,
            source=payload.source,
            description=payload.description,
            meta={
                **dict(payload.meta or {}),
                "reason": payload.reason or "",
            },
        )
        return {"ok": True, "applied": True, "status": "applied", "item": item}
    except Exception as exc:
        return {"ok": False, "applied": False, "status": "error", "error": str(exc)}


@router.get("/config/effective")
@router.get("/effective_config")
@router.get("/config")
def effective_config() -> dict[str, object]:
    try:
        return {
            "ts": _now_s(),
            "env_profile": _safe_str(os.getenv("FRANCIS_ENV_PROFILE")).strip() or "dev",
            "run_mode": _safe_str(os.getenv("FRANCIS_RUN_MODE")).strip() or "api",
            "config": _effective_config_snapshot(),
            "sources": {
                "base": "settings",
                "overrides": "data/runtime/system_settings.json",
                "flags": "data/runtime/feature_flags.json",
            },
        }
    except Exception as exc:
        return {"config": {}, "error": str(exc)}


@router.post("/config/mutate")
@router.post("/config/patch")
@router.post("/settings/mutate")
@router.post("/settings")
def mutate_config(payload: ConfigMutationIn) -> dict[str, object]:
    blocked_reason = _system_write_posture_guard("mutating runtime settings")
    if blocked_reason:
        return {"ok": False, "applied": False, "status": "blocked", "message": blocked_reason}
    try:
        current = _read_runtime_overrides()
        updated, resulting = _apply_mutation(
            current,
            op=payload.op,
            path=payload.path,
            value=payload.value,
        )
        _write_runtime_overrides(updated)
        return {
            "ok": True,
            "applied": True,
            "status": "applied",
            "resulting_value": resulting,
            "message": "mutation_applied",
            "meta": {
                "op": payload.op,
                "path": payload.path,
                "reason": payload.reason or "",
                "domain": payload.domain or "",
                "actor": payload.actor or "",
                **dict(payload.meta or {}),
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "applied": False,
            "status": "error",
            "message": str(exc),
        }
