from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir
from francis.telemetry.audit import record as audit_record
from francis.trust.calculator import evaluate, normalize_risk_tier
from francis.trust.levels import get_state, set_global_level


def _state_path() -> Path:
    return data_dir() / "trust" / "levels" / "current_state.json"


def _history_path() -> Path:
    return data_dir() / "trust" / "levels" / "history.jsonl"


def _policy_path() -> Path:
    return data_dir() / "trust" / "policy.json"


def _now_s() -> int:
    return int(time.time())


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _redact_free_text(value: Any) -> str:
    return redact_secret_text(_safe_str(value).strip())


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def default_policy() -> dict[str, Any]:
    return {
        "mode": "policy",
        "thresholds": {
            "min_level": -10,
            "max_level": 10,
            "warning_level": -3,
            "high_trust_level": 7,
        },
        "gates": {
            "approvals_required": False,
        },
        "meta": {},
        "ts": _now_s(),
    }


def load_policy() -> dict[str, Any]:
    path = _policy_path()
    if not path.exists():
        return default_policy()
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default_policy()
    if not isinstance(payload, dict):
        return default_policy()

    policy = default_policy()
    policy.update(payload)
    if not isinstance(policy.get("thresholds"), dict):
        policy["thresholds"] = default_policy()["thresholds"]
    if not isinstance(policy.get("gates"), dict):
        policy["gates"] = default_policy()["gates"]
    if not isinstance(policy.get("meta"), dict):
        policy["meta"] = {}
    policy["ts"] = int(policy.get("ts") or _now_s())
    return policy


def save_policy(policy: dict[str, Any]) -> dict[str, Any]:
    merged = default_policy()
    merged.update(policy)
    if not isinstance(merged.get("thresholds"), dict):
        merged["thresholds"] = default_policy()["thresholds"]
    if not isinstance(merged.get("gates"), dict):
        merged["gates"] = default_policy()["gates"]
    if not isinstance(merged.get("meta"), dict):
        merged["meta"] = {}
    merged["ts"] = _now_s()
    _atomic_write_json(_policy_path(), merged)
    return merged


def load_state() -> dict[str, Any]:
    payload = get_state()
    if not isinstance(payload, dict):
        return {"global_level": 0, "domain_levels": {}, "last_updated": None}
    payload.setdefault("global_level", 0)
    payload.setdefault("domain_levels", {})
    payload.setdefault("last_updated", None)
    return payload


def current_level() -> int:
    payload = load_state()
    value = payload.get("global_level", payload.get("level", 0))
    try:
        return int(value)
    except Exception:
        return 0


def save_state(payload: dict[str, Any]) -> dict[str, Any]:
    state = {
        "global_level": int(payload.get("global_level", payload.get("level", 0)) or 0),
        "domain_levels": payload.get("domain_levels") if isinstance(payload.get("domain_levels"), dict) else {},
        "last_updated": int(payload.get("last_updated") or _now_s()),
    }
    _atomic_write_json(_state_path(), state)
    return state


def append_event(
    *,
    kind: str,
    before_level: int,
    after_level: int,
    reason: str = "",
    actor: str = "system",
    domain: str = "",
    ts: int | None = None,
    idempotency_key: str = "",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "id": f"tev_{uuid.uuid4().hex[:10]}",
        "ts": int(ts or _now_s()),
        "kind": kind.strip() or "adjust",
        "before_level": int(before_level),
        "after_level": int(after_level),
        "level": int(after_level),
        "delta": int(after_level) - int(before_level),
        "reason": _redact_free_text(reason),
        "actor": actor.strip() or "system",
        "domain": domain.strip(),
        "idempotency_key": idempotency_key.strip(),
        "meta": dict(meta or {}),
    }
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    audit_record(
        "trust.adjusted",
        actor=payload["actor"],
        domain=payload["domain"],
        before_level=payload["before_level"],
        after_level=payload["after_level"],
        idempotency_key=payload["idempotency_key"],
    )
    return payload


def list_history(
    *,
    limit: int = 100,
    actor: str | None = None,
    domain: str | None = None,
    kind: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    path = _history_path()
    if not path.exists():
        return []

    actor_filter = _safe_str(actor).strip().lower()
    domain_filter = _safe_str(domain).strip().lower()
    kind_filter = _safe_str(kind).strip().lower()
    search_filter = _safe_str(search).strip().lower()

    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        if actor_filter and str(payload.get("actor", "")).strip().lower() != actor_filter:
            continue
        if domain_filter and str(payload.get("domain", "")).strip().lower() != domain_filter:
            continue
        if kind_filter and str(payload.get("kind", "")).strip().lower() != kind_filter:
            continue
        if search_filter:
            haystack = json.dumps(payload, ensure_ascii=False).lower()
            if search_filter not in haystack:
                continue
        items.append(payload)
    if limit <= 0:
        return items
    return items[-limit:]


def _existing_idempotent_event(idempotency_key: str) -> dict[str, Any] | None:
    if not idempotency_key:
        return None
    for item in reversed(list_history(limit=10_000)):
        if str(item.get("idempotency_key", "")).strip() == idempotency_key:
            return item
    return None


def _clamp_level(level: int, policy: dict[str, Any]) -> int:
    thresholds = policy.get("thresholds") if isinstance(policy.get("thresholds"), dict) else {}
    min_level = int(thresholds.get("min_level", -10))
    max_level = int(thresholds.get("max_level", 10))
    return max(min_level, min(max_level, int(level)))


def adjust_level(
    *,
    op: str,
    value: int | None = None,
    delta: int | None = None,
    reason: str = "",
    actor: str = "system",
    domain: str = "",
    ts: int | None = None,
    meta: dict[str, Any] | None = None,
    idempotency_key: str = "",
    risk_tier: str = "normal",
) -> dict[str, Any]:
    existing = _existing_idempotent_event(idempotency_key.strip())
    if existing is not None:
        level = int(existing.get("after_level", existing.get("level", current_level())) or 0)
        policy = load_policy()
        return {
            "ok": True,
            "applied": False,
            "level": level,
            "state": load_state(),
            "event": existing,
            "policy": policy,
            "decision": evaluate(
                level,
                normalize_risk_tier(risk_tier),
                policy_requires_approval=bool(policy["gates"].get("approvals_required")),
            ).to_dict(),
        }

    before = current_level()
    op_normalized = _safe_str(op).strip().lower() or "set"
    if op_normalized == "increase":
        after = before + int(delta if delta is not None else value if value is not None else 1)
    elif op_normalized == "decrease":
        after = before - int(delta if delta is not None else value if value is not None else 1)
    else:
        after = int(value if value is not None else before)

    policy = load_policy()
    after = _clamp_level(after, policy)
    state = save_state(
        {
            "global_level": after,
            "domain_levels": load_state().get("domain_levels", {}),
            "last_updated": int(ts or _now_s()),
        }
    )
    set_global_level(after)

    event = append_event(
        kind="adjust",
        before_level=before,
        after_level=after,
        reason=reason,
        actor=actor,
        domain=domain,
        ts=ts,
        idempotency_key=idempotency_key,
        meta=meta,
    )
    decision = evaluate(
        after,
        normalize_risk_tier(risk_tier),
        policy_requires_approval=bool(policy.get("gates", {}).get("approvals_required")),
    ).to_dict()
    return {
        "ok": True,
        "applied": True,
        "level": after,
        "state": state,
        "event": event,
        "policy": policy,
        "decision": decision,
    }
