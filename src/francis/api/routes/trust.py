from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir
from francis.trust.levels import get_state, set_global_level

router = APIRouter()
_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{1,127}$")


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _redact_free_text(value: Any) -> str:
    return redact_secret_text(_safe_str(value).strip())


def _now_s() -> int:
    return int(time.time())


def _normalize_ts(value: Any) -> int:
    if isinstance(value, (int, float)):
        ts = int(value)
    else:
        text = _safe_str(value).strip()
        if not text:
            return _now_s()
        try:
            ts = int(float(text))
        except Exception:
            return _now_s()
    if ts > 10_000_000_000:
        return int(ts / 1000)
    return ts


def _slug(value: str) -> str:
    out = []
    last_sep = False
    for ch in value.strip().lower():
        if ch.isalnum():
            out.append(ch)
            last_sep = False
            continue
        if ch in {" ", "-", "_", ".", ":"} and not last_sep:
            out.append("-")
            last_sep = True
    slug = "".join(out).strip("-")
    return slug[:64] or "item"


def _new_id(prefix: str, seed: str) -> str:
    return f"{prefix}_{_slug(seed)}_{uuid.uuid4().hex[:8]}"


def _validate_id(value: str, field: str = "id") -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field} is required")
    if not _ID_RE.match(text):
        raise ValueError(f"invalid {field}")
    return text


def _parse_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = _safe_str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


def _history_path() -> Path:
    return data_dir() / "trust" / "levels" / "history.jsonl"


def _policy_path() -> Path:
    return data_dir() / "trust" / "policy.json"


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _default_policy() -> dict[str, Any]:
    return {
        "mode": "policy",
        "thresholds": {
            "min_level": -10,
            "max_level": 10,
            "warning_level": -3,
            "high_trust_level": 7,
        },
        "summary": "Trust level governs operational confidence and risk posture.",
        "gates": {
            "mutations_enabled": True,
            "approvals_required": False,
        },
        "ts": _now_s(),
        "meta": {},
    }


def _load_policy() -> dict[str, Any]:
    path = _policy_path()
    if not path.exists():
        return _default_policy()
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return _default_policy()
    if not isinstance(raw, dict):
        return _default_policy()
    out = _default_policy()
    out.update(raw)
    if not isinstance(out.get("thresholds"), dict):
        out["thresholds"] = _default_policy()["thresholds"]
    if not isinstance(out.get("gates"), dict):
        out["gates"] = _default_policy()["gates"]
    if not isinstance(out.get("meta"), dict):
        out["meta"] = {}
    out["ts"] = _normalize_ts(out.get("ts") or _now_s())
    return out


def _save_policy(policy: dict[str, Any]) -> None:
    normalized = _default_policy()
    normalized.update(policy)
    if not isinstance(normalized.get("thresholds"), dict):
        normalized["thresholds"] = _default_policy()["thresholds"]
    if not isinstance(normalized.get("gates"), dict):
        normalized["gates"] = _default_policy()["gates"]
    if not isinstance(normalized.get("meta"), dict):
        normalized["meta"] = {}
    normalized["ts"] = _normalize_ts(normalized.get("ts") or _now_s())
    _atomic_write(_policy_path(), normalized)


def _tier(level: float) -> str:
    if level <= -5:
        return "critical"
    if level <= -1:
        return "low"
    if level >= 7:
        return "high"
    if level >= 3:
        return "medium"
    return "neutral"


def _current_level(state: dict[str, Any]) -> int:
    if isinstance(state.get("global_level"), (int, float)):
        return int(state.get("global_level") or 0)
    if isinstance(state.get("level"), (int, float)):
        return int(state.get("level") or 0)
    return 0


def _normalize_event(raw: dict[str, Any]) -> dict[str, Any]:
    event_id = _safe_str(raw.get("id")).strip() or _new_id(
        "tev", _safe_str(raw.get("kind") or "adjust").strip() or "adjust"
    )
    ts = _normalize_ts(raw.get("ts") or _now_s())
    before_level = int(raw.get("before_level") or raw.get("before") or 0)
    after_level = int(raw.get("after_level") or raw.get("after") or raw.get("level") or before_level)
    delta = int(raw.get("delta") or (after_level - before_level))
    return {
        "id": event_id,
        "ts": ts,
        "kind": _safe_str(raw.get("kind")).strip() or "adjust",
        "op": _safe_str(raw.get("op")).strip() or "set",
        "level": after_level,
        "before_level": before_level,
        "after_level": after_level,
        "delta": delta,
        "tier": _tier(float(after_level)),
        "reason": _redact_free_text(raw.get("reason")),
        "actor": _safe_str(raw.get("actor")).strip() or "api",
        "domain": _safe_str(raw.get("domain")).strip(),
        "source": _safe_str(raw.get("source")).strip() or "api.trust",
        "correlation_id": _safe_str(raw.get("correlation_id")).strip(),
        "approval_id": _safe_str(raw.get("approval_id")).strip(),
        "operation_id": _safe_str(raw.get("operation_id")).strip(),
        "meta": dict(raw.get("meta")) if isinstance(raw.get("meta"), dict) else {},
    }


def _read_history() -> list[dict[str, Any]]:
    path = _history_path()
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except Exception:
            continue
        if not isinstance(raw, dict):
            continue
        out.append(_normalize_event(raw))
    return out


def _append_history(event: dict[str, Any]) -> dict[str, Any]:
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    item = _normalize_event(event)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
    return item


def _paginate(
    items: list[dict[str, Any]], limit: int, cursor: str | None
) -> tuple[list[dict[str, Any]], int, int, int, str | None]:
    safe_limit = max(1, min(int(limit), 10_000))
    safe_offset = int(cursor) if cursor and cursor.isdigit() else 0
    total = len(items)
    page = items[safe_offset : safe_offset + safe_limit]
    next_cursor = str(safe_offset + safe_limit) if safe_offset + safe_limit < total else None
    return page, total, safe_limit, safe_offset, next_cursor


def _state_body() -> dict[str, Any]:
    base = get_state()
    if not isinstance(base, dict):
        base = {"global_level": 0, "domain_levels": {}, "last_updated": None}
    level = _current_level(base)
    ts = _normalize_ts(base.get("last_updated") or _now_s())
    policy = _load_policy()
    thresholds = policy.get("thresholds") if isinstance(policy.get("thresholds"), dict) else {}
    body = {
        "ok": True,
        "level": level,
        "global_level": level,
        "domain_levels": base.get("domain_levels") if isinstance(base.get("domain_levels"), dict) else {},
        "ts": ts,
        "last_updated": ts,
        "mode": _safe_str(policy.get("mode")).strip() or "policy",
        "tier": _tier(float(level)),
        "decay_enabled": _parse_bool((policy.get("gates") or {}).get("decay_enabled"), default=True),
        "growth_enabled": _parse_bool((policy.get("gates") or {}).get("growth_enabled"), default=True),
        "min_level": int(thresholds.get("min_level"))
        if isinstance(thresholds.get("min_level"), (int, float))
        else None,
        "max_level": int(thresholds.get("max_level"))
        if isinstance(thresholds.get("max_level"), (int, float))
        else None,
        "source": "trust.levels",
        "meta": {"policy_ts": _normalize_ts(policy.get("ts") or _now_s())},
    }
    body["state"] = {k: v for k, v in body.items() if k != "state"}
    return body


def _adjust(payload: dict[str, Any], *, default_op: str) -> dict[str, Any]:
    op = _safe_str(payload.get("op")).strip().lower() or default_op
    level_raw = payload.get("level")
    value_raw = payload.get("value")
    delta_raw = payload.get("delta")
    reason = _safe_str(payload.get("reason")).strip() or "requested"
    actor = _safe_str(payload.get("actor")).strip() or "api"
    domain = _safe_str(payload.get("domain")).strip()
    correlation_id = _safe_str(payload.get("idempotency_key") or payload.get("correlation_id")).strip()
    meta = dict(payload.get("meta")) if isinstance(payload.get("meta"), dict) else {}
    ts = _normalize_ts(payload.get("ts") or _now_s())

    current = _state_body()
    before_level = int(current.get("level") or 0)

    if op in {"set", "override"}:
        target_value = value_raw if value_raw is not None else level_raw
        if not isinstance(target_value, (int, float)):
            return {"ok": False, "error": "value_or_level_required"}
        target_level = int(target_value)
    elif op in {"increase", "inc", "up"}:
        if not isinstance(delta_raw, (int, float)):
            return {"ok": False, "error": "delta_required"}
        target_level = before_level + abs(int(delta_raw))
    elif op in {"decrease", "dec", "down"}:
        if not isinstance(delta_raw, (int, float)):
            return {"ok": False, "error": "delta_required"}
        target_level = before_level - abs(int(delta_raw))
    else:
        return {"ok": False, "error": "unsupported_op"}

    policy = _load_policy()
    thresholds = policy.get("thresholds") if isinstance(policy.get("thresholds"), dict) else {}
    min_level = int(thresholds.get("min_level")) if isinstance(thresholds.get("min_level"), (int, float)) else -10
    max_level = int(thresholds.get("max_level")) if isinstance(thresholds.get("max_level"), (int, float)) else 10
    clamped_level = max(min_level, min(max_level, target_level))

    set_global_level(clamped_level)

    event = _append_history(
        {
            "id": payload.get("id"),
            "ts": ts,
            "kind": "adjust",
            "op": op,
            "before_level": before_level,
            "after_level": clamped_level,
            "delta": clamped_level - before_level,
            "reason": reason,
            "actor": actor,
            "domain": domain,
            "source": "api.trust.adjust",
            "correlation_id": correlation_id,
            "meta": meta,
        }
    )

    updated = _state_body()
    return {
        "ok": True,
        "status": "applied",
        "applied": True,
        "level": int(updated.get("level") or clamped_level),
        "ts": _normalize_ts(updated.get("ts") or ts),
        "message": "trust updated",
        "item": updated,
        "event": event,
        "meta": {"min_level": min_level, "max_level": max_level, "requested_level": target_level},
    }


@router.get("/")
@router.get("/current")
@router.get("/state")
def state() -> dict[str, Any]:
    try:
        return _state_body()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/policy")
@router.get("/config")
@router.get("/settings")
def policy() -> dict[str, Any]:
    try:
        loaded = _load_policy()
        return {"ok": True, "policy": loaded}
    except Exception as exc:
        return {"ok": False, "policy": _default_policy(), "error": str(exc)}


@router.get("/history")
@router.get("/levels/history")
@router.get("/timeline")
def history(
    start_ts: int | None = None,
    end_ts: int | None = None,
    limit: int = 200,
    cursor: str | None = None,
) -> dict[str, Any]:
    try:
        events = _read_history()
        out: list[dict[str, Any]] = []
        for item in events:
            ts = int(item.get("ts") or 0)
            if start_ts is not None and ts < int(start_ts):
                continue
            if end_ts is not None and ts > int(end_ts):
                continue
            out.append(
                {
                    "ts": ts,
                    "level": int(item.get("after_level") or item.get("level") or 0),
                    "tier": _safe_str(item.get("tier")).strip(),
                    "reason": _safe_str(item.get("reason")).strip(),
                    "source": _safe_str(item.get("source")).strip(),
                    "actor": _safe_str(item.get("actor")).strip(),
                    "domain": _safe_str(item.get("domain")).strip(),
                    "meta": dict(item.get("meta")) if isinstance(item.get("meta"), dict) else {},
                }
            )
        out.sort(key=lambda item: (int(item.get("ts") or 0), _safe_str(item.get("actor"))))
        page, total, safe_limit, _, next_cursor = _paginate(out, limit, cursor)
        return {"items": page, "history": page, "total": total, "limit": safe_limit, "next_cursor": next_cursor}
    except Exception as exc:
        return {"items": [], "history": [], "total": 0, "limit": 0, "next_cursor": None, "error": str(exc)}


@router.get("/events")
@router.get("/log")
@router.get("/audit")
def events(
    start_ts: int | None = None,
    end_ts: int | None = None,
    limit: int = 100,
    cursor: str | None = None,
    kind: str | None = None,
    actor: str | None = None,
    domain: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    try:
        kind_filter = _safe_str(kind).strip().lower()
        actor_filter = _safe_str(actor).strip().lower()
        domain_filter = _safe_str(domain).strip().lower()
        search_filter = _safe_str(search).strip().lower()

        raw = _read_history()
        filtered: list[dict[str, Any]] = []
        for item in raw:
            ts = int(item.get("ts") or 0)
            if start_ts is not None and ts < int(start_ts):
                continue
            if end_ts is not None and ts > int(end_ts):
                continue
            if kind_filter and _safe_str(item.get("kind")).strip().lower() != kind_filter:
                continue
            if actor_filter and _safe_str(item.get("actor")).strip().lower() != actor_filter:
                continue
            if domain_filter and _safe_str(item.get("domain")).strip().lower() != domain_filter:
                continue
            if search_filter and search_filter not in json.dumps(item, ensure_ascii=False, default=str).lower():
                continue
            filtered.append(item)

        filtered.sort(key=lambda item: (int(item.get("ts") or 0), _safe_str(item.get("id"))), reverse=True)
        page, total, safe_limit, _, next_cursor = _paginate(filtered, limit, cursor)
        return {"items": page, "events": page, "total": total, "limit": safe_limit, "next_cursor": next_cursor}
    except Exception as exc:
        return {"items": [], "events": [], "total": 0, "limit": 0, "next_cursor": None, "error": str(exc)}


@router.post("/adjust")
@router.post("/mutate")
def adjust(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return _adjust(payload, default_op="set")
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/set")
def set_level(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        level_value = payload.get("level")
        if isinstance(level_value, (int, float)):
            adapted = dict(payload)
            adapted["op"] = adapted.get("op") or "set"
            adapted["value"] = adapted.get("value", level_value)
            return _adjust(adapted, default_op="set")

        # Accept legacy shape from strict clients: {"level": <int>}
        if "value" in payload and isinstance(payload.get("value"), (int, float)):
            adapted = dict(payload)
            adapted["op"] = adapted.get("op") or "set"
            return _adjust(adapted, default_op="set")

        # Last-resort backward compatibility for existing callers expecting set_global_level response.
        if "global_level" in payload and isinstance(payload.get("global_level"), (int, float)):
            level = int(payload.get("global_level"))
            state = set_global_level(level)
            _append_history(
                {
                    "id": _new_id("tev", "set"),
                    "ts": _normalize_ts(state.get("last_updated") or _now_s()),
                    "kind": "adjust",
                    "op": "set",
                    "before_level": 0,
                    "after_level": level,
                    "delta": level,
                    "reason": _safe_str(payload.get("reason")).strip() or "requested",
                    "actor": _safe_str(payload.get("actor")).strip() or "api",
                    "source": "api.trust.set",
                }
            )
            return {"ok": True, **state}

        return {"ok": False, "error": "level_or_value_required"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/policy")
def set_policy(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        policy_obj = payload.get("policy") if isinstance(payload.get("policy"), dict) else payload
        if not isinstance(policy_obj, dict):
            return {"ok": False, "error": "invalid_policy"}

        current = _load_policy()
        merged = {
            **current,
            **policy_obj,
            "thresholds": {
                **(current.get("thresholds") if isinstance(current.get("thresholds"), dict) else {}),
                **(policy_obj.get("thresholds") if isinstance(policy_obj.get("thresholds"), dict) else {}),
            },
            "gates": {
                **(current.get("gates") if isinstance(current.get("gates"), dict) else {}),
                **(policy_obj.get("gates") if isinstance(policy_obj.get("gates"), dict) else {}),
            },
            "meta": {
                **(current.get("meta") if isinstance(current.get("meta"), dict) else {}),
                **(policy_obj.get("meta") if isinstance(policy_obj.get("meta"), dict) else {}),
            },
            "ts": _now_s(),
        }

        _save_policy(merged)
        return {"ok": True, "policy": _load_policy()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
