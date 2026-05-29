from __future__ import annotations

from francis.api.errors import api_error_message
import csv
import io
import json
import os
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter
from fastapi.responses import Response

from francis.governance import approvals as approval_store
from francis.governance.redaction import (
    redact_governed_display_value,
    redact_governed_metadata,
    redact_governed_value,
    seal_governed_approval_value,
)
from francis.kernel.paths import data_dir

router = APIRouter()
_TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "f", "no", "n", "off"}
_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{1,127}$")


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _redacted_text(value: str, *, key: str) -> str:
    redacted = redact_governed_value(value, key=key)
    return redacted if isinstance(redacted, str) else _safe_str(redacted)


def _to_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = _safe_str(value).strip().lower()
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    return default


def _parse_bool(value: Any) -> tuple[bool, bool]:
    if isinstance(value, bool):
        return True, value
    if isinstance(value, (int, float)):
        return True, bool(value)
    text = _safe_str(value).strip().lower()
    if text in _TRUE_VALUES:
        return True, True
    if text in _FALSE_VALUES:
        return True, False
    return False, False


def _now_s() -> int:
    return int(time.time())


def _new_id(prefix: str, seed: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", seed.strip().lower()).strip("-")[:50] or "item"
    return f"{prefix}_{slug}_{uuid.uuid4().hex[:8]}"


def _path() -> Path:
    return data_dir() / "web_learning" / "_registry.json"


def _default_policy() -> dict[str, Any]:
    return {
        "ts": _now_s(),
        "enabled": True,
        "approvals_required": True,
        "allow_domains": [],
        "deny_domains": ["localhost", "127.0.0.1", "::1"],
        "allow_patterns": [],
        "deny_patterns": [r"^file://", r"^data:", r"^javascript:"],
        "limits": {"concurrency": 2, "max_pages": 20, "max_depth": 2},
        "summary": "Governed web learning with policy checks and quarantine.",
        "meta": {},
    }


def _default_registry() -> dict[str, Any]:
    env_enabled = _to_bool(os.getenv("FRANCIS_WEB_LEARNING_ENABLED"), default=True)
    policy = _default_policy()
    return {
        "version": 1,
        "updated_at": _now_s(),
        "enabled": env_enabled and _to_bool(policy.get("enabled"), default=True),
        "last_run_ts": 0,
        "last_success_ts": 0,
        "last_error_ts": 0,
        "last_error": "",
        "env_profile": _safe_str(os.getenv("FRANCIS_PROFILE")).strip() or "dev",
        "run_mode": _safe_str(os.getenv("FRANCIS_RUN_MODE")).strip() or "api",
        "policy": policy,
        "records": [],
        "events": [],
        "quarantine": [],
        "requests": [],
    }


def _load() -> dict[str, Any]:
    path = _path()
    if not path.exists():
        return _default_registry()
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return _default_registry()
    if not isinstance(raw, dict):
        return _default_registry()
    reg = _default_registry()
    reg["version"] = int(raw.get("version") or 1)
    reg["updated_at"] = int(raw.get("updated_at") or _now_s())
    reg["enabled"] = _to_bool(raw.get("enabled"), default=True)
    reg["last_run_ts"] = int(raw.get("last_run_ts") or 0)
    reg["last_success_ts"] = int(raw.get("last_success_ts") or 0)
    reg["last_error_ts"] = int(raw.get("last_error_ts") or 0)
    reg["last_error"] = _safe_str(raw.get("last_error")).strip()
    reg["env_profile"] = _safe_str(raw.get("env_profile")).strip() or reg["env_profile"]
    reg["run_mode"] = _safe_str(raw.get("run_mode")).strip() or reg["run_mode"]
    policy = raw.get("policy")
    if isinstance(policy, dict):
        reg["policy"] = dict(_default_policy() | policy)
    for key in ("records", "events", "quarantine", "requests"):
        value = raw.get(key)
        if isinstance(value, list):
            reg[key] = [item for item in value if isinstance(item, dict)]
    return reg


def _save(registry: dict[str, Any]) -> None:
    reg = _load()
    reg.update(registry)
    reg["updated_at"] = _now_s()
    reg["records"] = [item for item in reg.get("records", []) if isinstance(item, dict)][-10_000:]
    reg["events"] = [item for item in reg.get("events", []) if isinstance(item, dict)][-20_000:]
    reg["quarantine"] = [item for item in reg.get("quarantine", []) if isinstance(item, dict)][-5_000:]
    reg["requests"] = [item for item in reg.get("requests", []) if isinstance(item, dict)][-10_000:]
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(reg, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, p)


def _effective_enabled(registry: dict[str, Any]) -> bool:
    env_enabled = _to_bool(os.getenv("FRANCIS_WEB_LEARNING_ENABLED"), default=True)
    local_enabled = _to_bool(registry.get("enabled"), default=True)
    policy_enabled = _to_bool((registry.get("policy") or {}).get("enabled"), default=True)
    return env_enabled and local_enabled and policy_enabled


def _append_event(registry: dict[str, Any], event: dict[str, Any]) -> None:
    events = registry.get("events")
    if not isinstance(events, list):
        events = []
        registry["events"] = events
    eid = _safe_str(event.get("id")).strip() or _new_id("wev", _safe_str(event.get("kind")).strip() or "event")
    item = {
        "id": eid,
        "ts": int(event.get("ts") or _now_s()),
        **{k: v for k, v in event.items() if k not in {"id", "ts"}},
    }
    events.append(item)


def _sort_desc(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: (int(item.get("ts") or 0), _safe_str(item.get("id"))), reverse=True)


def _filter(
    items: list[dict[str, Any]],
    *,
    status: str = "",
    domain: str = "",
    search: str = "",
    start_ts: int | None = None,
    end_ts: int | None = None,
) -> list[dict[str, Any]]:
    status_filter = status.strip().lower()
    domain_filter = domain.strip().lower()
    search_filter = search.strip().lower()
    out: list[dict[str, Any]] = []
    for item in items:
        if status_filter and _safe_str(item.get("status")).strip().lower() != status_filter:
            continue
        if domain_filter and _safe_str(item.get("domain")).strip().lower() != domain_filter:
            continue
        ts = int(item.get("ts") or 0)
        if start_ts is not None and ts < int(start_ts):
            continue
        if end_ts is not None and ts > int(end_ts):
            continue
        if search_filter and search_filter not in json.dumps(item, ensure_ascii=False, default=str).lower():
            continue
        out.append(item)
    return out


def _paginate(items: list[dict[str, Any]], limit: int, offset: int, cursor: str | None) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 10_000))
    safe_offset = int(cursor) if cursor and cursor.isdigit() else max(0, int(offset))
    total = len(items)
    page = items[safe_offset : safe_offset + safe_limit]
    next_cursor = str(safe_offset + safe_limit) if safe_offset + safe_limit < total else None
    return {"items": page, "total": total, "limit": safe_limit, "offset": safe_offset, "next_cursor": next_cursor}


def _query(
    kind: str,
    *,
    limit: int = 200,
    offset: int = 0,
    cursor: str | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
    status: str | None = None,
    domain: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    registry = _load()
    items = registry.get(kind)
    if not isinstance(items, list):
        return {"items": [], "total": 0, "limit": 0, "offset": 0}
    filtered = _filter(
        items,
        status=_safe_str(status),
        domain=_safe_str(domain),
        search=_safe_str(search),
        start_ts=start_ts,
        end_ts=end_ts,
    )
    return _paginate(_sort_desc(filtered), limit, offset, cursor)


def _parse_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    scheme = _safe_str(parsed.scheme).strip().lower()
    if scheme not in {"http", "https"}:
        raise ValueError("url must use http or https")
    domain = _safe_str(parsed.hostname).strip().lower()
    if not domain:
        raise ValueError("url must include host")
    return url, domain


def _match_domain(domain: str, rule: str) -> bool:
    d = domain.strip().lower()
    r = rule.strip().lower()
    return bool(d and r and (d == r or d.endswith("." + r)))


def _matches_pattern(value: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        text = pattern.strip()
        if not text:
            continue
        try:
            if re.search(text, value, flags=re.IGNORECASE):
                return True
        except re.error:
            continue
    return False


def _policy_verdict(url: str, domain: str, policy: dict[str, Any]) -> tuple[str, str]:
    for deny in policy.get("deny_domains", []) if isinstance(policy.get("deny_domains"), list) else []:
        if _match_domain(domain, _safe_str(deny)):
            return "blocked", f"Domain is deny-listed ({deny})."
    deny_patterns = [
        _safe_str(x) for x in (policy.get("deny_patterns") if isinstance(policy.get("deny_patterns"), list) else [])
    ]
    if _matches_pattern(url, deny_patterns):
        return "blocked", "URL denied by policy pattern."
    allow_domains = [
        _safe_str(x) for x in (policy.get("allow_domains") if isinstance(policy.get("allow_domains"), list) else [])
    ]
    allow_patterns = [
        _safe_str(x) for x in (policy.get("allow_patterns") if isinstance(policy.get("allow_patterns"), list) else [])
    ]
    if allow_domains or allow_patterns:
        domain_ok = any(_match_domain(domain, rule) for rule in allow_domains)
        pattern_ok = _matches_pattern(url, allow_patterns)
        if not (domain_ok or pattern_ok):
            return "quarantined", "URL is not allow-listed by current policy."
    return "allow", ""


def _request_approval(action: str, reason: str, payload: dict[str, Any]) -> str:
    try:
        item = approval_store.request(action, reason, payload)
    except Exception:
        return ""
    return _safe_str(item.get("id")).strip()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _atomic_write_display_json(path: Path, payload: dict[str, Any]) -> None:
    display_payload = redact_governed_display_value(payload)
    _atomic_write_json(path, display_payload if isinstance(display_payload, dict) else {})


def _approval_artifact_dir(approval_id: str) -> Path:
    return data_dir() / "artifacts" / "web_learning" / "approvals" / _safe_str(approval_id).strip()


def _approval_status(approval_id: str) -> tuple[str, dict[str, Any] | None]:
    resolved_id = _safe_str(approval_id).strip()
    if not resolved_id:
        return "missing", None
    candidates: list[tuple[str, Path]] = [
        ("pending", approval_store.pending_dir() / f"{resolved_id}.json"),
        ("approved", approval_store.approved_dir() / f"{resolved_id}.json"),
        ("rejected", approval_store.rejected_dir() / f"{resolved_id}.json"),
        ("emergency", approval_store.emergency_dir() / f"{resolved_id}.json"),
    ]
    for status, path in candidates:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return "corrupt", None
        return status, payload if isinstance(payload, dict) else None
    return "missing", None


def _approval_id_from_payload(payload: dict[str, Any]) -> str:
    explicit = _safe_str(payload.get("approval_id")).strip()
    if explicit:
        return explicit
    meta = payload.get("meta")
    if isinstance(meta, dict):
        return _safe_str(meta.get("approval_id")).strip()
    return ""


def _normalize_approval_value(value: Any) -> Any:
    return seal_governed_approval_value(value)


def _approval_meta(meta: Any) -> dict[str, Any]:
    return redact_governed_metadata(meta, drop_control_keys=True)


def _approval_request_payload(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": action,
        "payload": _normalize_approval_value(payload),
    }


def _request_exact_approval(
    *,
    action: str,
    reason: str,
    request_payload: dict[str, Any],
    previous_approval_id: str = "",
    previous_status: str = "",
    previous_record: dict[str, Any] | None = None,
) -> tuple[str, Path]:
    approval = approval_store.request(action, reason, request_payload)
    approval_id = _safe_str(approval.get("id")).strip()
    art = _approval_artifact_dir(approval_id)
    request_body: dict[str, Any] = {
        "kind": "web_learning.approval.request",
        "approval": approval,
        "action": action,
        "request": request_payload,
    }
    if previous_approval_id:
        request_body["previous_approval_id"] = previous_approval_id
    if previous_status:
        request_body["previous_status"] = previous_status
    if isinstance(previous_record, dict):
        request_body["previous_approval"] = previous_record
    _atomic_write_display_json(art / "request.json", request_body)
    return approval_id, art


def _approval_matches(approval_record: dict[str, Any] | None, *, action: str, request_payload: dict[str, Any]) -> bool:
    if not isinstance(approval_record, dict):
        return False
    if _safe_str(approval_record.get("action")).strip() != action:
        return False
    payload = approval_record.get("payload")
    if not isinstance(payload, dict):
        return False
    return _normalize_approval_value(payload) == _normalize_approval_value(request_payload)


def _request_learn(payload: dict[str, Any]) -> dict[str, Any]:
    url = _safe_str(payload.get("url")).strip()
    if not url:
        return {"ok": False, "error": "url_required", "message": "A valid URL is required."}

    try:
        normalized_url, parsed_domain = _parse_url(url)
    except Exception as exc:
        return {"ok": False, "error": "invalid_url", "message": api_error_message(exc)}

    actor = _safe_str(payload.get("actor")).strip() or "api"
    reason = _safe_str(payload.get("reason")).strip() or "requested"
    source = _safe_str(payload.get("source")).strip() or actor
    domain = _safe_str(payload.get("domain")).strip().lower() or parsed_domain
    req_meta = redact_governed_metadata(payload.get("meta"))
    force = _to_bool(req_meta.get("force"), default=False)
    recorded_url = _redacted_text(normalized_url, key="url")
    recorded_actor = _redacted_text(actor, key="actor")
    recorded_reason = _redacted_text(reason, key="reason")
    recorded_source = _redacted_text(source, key="source")

    request_id = _new_id("wlreq", domain)
    record_id = _new_id("wlr", domain)
    ts = _now_s()

    registry = _load()
    policy = registry.get("policy") if isinstance(registry.get("policy"), dict) else _default_policy()

    requests = registry.get("requests") if isinstance(registry.get("requests"), list) else []
    requests.append(
        {
            "id": request_id,
            "ts": ts,
            "url": recorded_url,
            "status": "received",
            "reason": recorded_reason,
            "domain": domain,
            "actor": recorded_actor,
            "meta": req_meta,
        }
    )
    registry["requests"] = requests

    if not _effective_enabled(registry):
        registry["last_error_ts"] = ts
        registry["last_error"] = "Web learning is disabled."
        _append_event(
            registry,
            {
                "ts": ts,
                "kind": "policy_block",
                "url": recorded_url,
                "record_id": record_id,
                "status": "disabled",
                "message": "Web learning is disabled.",
                "actor": recorded_actor,
                "domain": domain,
                "source": recorded_source,
                "correlation_id": request_id,
            },
        )
        _save(registry)
        return {"ok": False, "request_id": request_id, "status": "disabled", "message": "Web learning is disabled."}

    verdict, verdict_reason = _policy_verdict(normalized_url, domain, policy)
    records = registry.get("records") if isinstance(registry.get("records"), list) else []
    quarantine = registry.get("quarantine") if isinstance(registry.get("quarantine"), list) else []
    if verdict in {"blocked", "quarantined"}:
        quarantine_id = _new_id("wlq", domain)
        record_status = "blocked" if verdict == "blocked" else "quarantined"
        records.append(
            {
                "id": record_id,
                "ts": ts,
                "url": recorded_url,
                "status": record_status,
                "method": "GET",
                "domain": domain,
                "source": recorded_source,
                "summary": "Blocked by policy and held in quarantine.",
                "quarantine_id": quarantine_id,
                "error": verdict_reason,
                "meta": {"reason": recorded_reason, "request_id": request_id, "force": force},
            }
        )
        quarantine.append(
            {
                "id": quarantine_id,
                "ts": ts,
                "url": recorded_url,
                "reason": verdict_reason,
                "status": "quarantined",
                "record_id": record_id,
                "domain": domain,
                "source": recorded_source,
                "evidence": "Policy validation denied this URL.",
                "meta": {"request_id": request_id},
            }
        )
        registry["records"] = records
        registry["quarantine"] = quarantine
        _append_event(
            registry,
            {
                "ts": ts,
                "kind": "policy_block",
                "url": recorded_url,
                "record_id": record_id,
                "status": record_status,
                "message": verdict_reason,
                "quarantine_id": quarantine_id,
                "actor": recorded_actor,
                "domain": domain,
                "source": recorded_source,
                "correlation_id": request_id,
            },
        )
        _append_event(
            registry,
            {
                "ts": ts,
                "kind": "quarantine",
                "url": recorded_url,
                "record_id": record_id,
                "status": "quarantined",
                "message": "Request moved to quarantine.",
                "quarantine_id": quarantine_id,
                "actor": recorded_actor,
                "domain": domain,
                "source": recorded_source,
                "correlation_id": request_id,
            },
        )
        registry["last_run_ts"] = ts
        registry["last_error_ts"] = ts
        registry["last_error"] = verdict_reason
        _save(registry)
        return {
            "ok": False,
            "request_id": request_id,
            "record_id": record_id,
            "status": record_status,
            "message": verdict_reason,
            "meta": {"quarantine_id": quarantine_id},
        }

    duration_ms = int(payload.get("duration_ms") or 120)
    byte_count = int(payload.get("bytes") or 0)
    content_type = _safe_str(payload.get("content_type")).strip() or "text/html"
    title = _safe_str(payload.get("title")).strip() or f"Learned from {domain}"
    summary = _safe_str(payload.get("summary")).strip() or "Learn request accepted and ingested."
    recorded_title = _redacted_text(title, key="title")
    recorded_summary = _redacted_text(summary, key="summary")
    approvals_required = _to_bool(policy.get("approvals_required"), default=True)
    approval_action = "web_learning.request"
    approval_id = _approval_id_from_payload(payload)
    request_payload = _approval_request_payload(
        approval_action,
        {
            "url": normalized_url,
            "domain": domain,
            "actor": actor,
            "source": source,
            "content_type": content_type,
            "bytes": byte_count,
            "duration_ms": duration_ms,
            "title": title,
            "summary": summary,
            "meta": _approval_meta(req_meta),
        },
    )
    record_idx = next(
        (
            i
            for i, item in enumerate(records)
            if approval_id and _safe_str(item.get("approval_id")).strip() == approval_id
        ),
        -1,
    )
    if record_idx >= 0:
        record_id = _safe_str(records[record_idx].get("id")).strip() or record_id

    if approvals_required and not force:
        if not approval_id:
            approval_id, art = _request_exact_approval(
                action=approval_action,
                reason=reason,
                request_payload=request_payload,
            )
            records.append(
                {
                    "id": record_id,
                    "ts": ts,
                    "url": recorded_url,
                    "status": "pending",
                    "method": "GET",
                    "http_status": 202,
                    "domain": domain,
                    "source": recorded_source,
                    "approval_id": approval_id,
                    "summary": "Pending approval before web learning execution.",
                    "meta": {"reason": recorded_reason, "request_id": request_id, "force": force},
                }
            )
            registry["records"] = records
            _append_event(
                registry,
                {
                    "ts": ts,
                    "kind": "approval_requested",
                    "url": recorded_url,
                    "record_id": record_id,
                    "status": "pending",
                    "message": "Learn request requires approval.",
                    "approval_id": approval_id,
                    "actor": recorded_actor,
                    "domain": domain,
                    "source": recorded_source,
                    "correlation_id": request_id,
                },
            )
            registry["last_run_ts"] = ts
            _save(registry)
            return {
                "ok": True,
                "request_id": request_id,
                "approval_id": approval_id,
                "artifact_dir": str(art),
                "status": "pending",
                "record_id": record_id,
                "message": "Submitted for approval.",
                "meta": {"force": force},
            }

        approval_status, approval_record = _approval_status(approval_id)
        if approval_status in {"missing", "corrupt"}:
            refreshed_id, art = _request_exact_approval(
                action=approval_action,
                reason=reason,
                request_payload=request_payload,
                previous_approval_id=approval_id,
                previous_status=approval_status,
                previous_record=approval_record,
            )
            if record_idx >= 0:
                records[record_idx]["approval_id"] = refreshed_id
                registry["records"] = records
            _atomic_write_display_json(
                art / "error.json",
                {
                    "kind": "web_learning.request.error",
                    "approval_id": refreshed_id,
                    "previous_approval_id": approval_id,
                    "status": approval_status,
                    "request": request_payload,
                },
            )
            _append_event(
                registry,
                {
                    "ts": ts,
                    "kind": "approval_requested",
                    "url": recorded_url,
                    "record_id": record_id,
                    "status": "needs_approval",
                    "message": "Learn request approval was missing; a fresh exact-action approval is required.",
                    "approval_id": refreshed_id,
                    "actor": recorded_actor,
                    "domain": domain,
                    "source": recorded_source,
                    "correlation_id": request_id,
                    "meta": {
                        "reason": recorded_reason,
                        "action": approval_action,
                        "previous_approval_id": approval_id,
                        "previous_status": approval_status,
                    },
                },
            )
            registry["last_run_ts"] = ts
            _save(registry)
            return {
                "ok": False,
                "request_id": request_id,
                "record_id": record_id,
                "approval_id": refreshed_id,
                "previous_approval_id": approval_id,
                "artifact_dir": str(art),
                "status": "needs_approval",
                "error": "approval_not_found",
                "message": "Approval was missing for this learn request; a fresh exact-action approval is required.",
                "meta": {"force": force},
            }
        if approval_status == "pending":
            return {
                "ok": True,
                "request_id": request_id,
                "record_id": record_id,
                "approval_id": approval_id,
                "status": "pending",
                "message": "Learn request is awaiting approval.",
                "meta": {"force": force},
            }
        if approval_status in {"rejected", "emergency"}:
            return {
                "ok": False,
                "request_id": request_id,
                "record_id": record_id,
                "approval_id": approval_id,
                "status": "denied",
                "error": "approval_denied",
                "message": "Approval was denied for this learn request.",
                "meta": {"force": force, "approval_status": approval_status},
            }
        if approval_status != "approved":
            return {
                "ok": False,
                "request_id": request_id,
                "record_id": record_id,
                "approval_id": approval_id,
                "status": "needs_approval",
                "error": "approval_not_found",
                "message": "A matching approved request was not found for this learn request.",
                "meta": {"force": force},
            }
        if not _approval_matches(approval_record, action=approval_action, request_payload=request_payload):
            refreshed_id, art = _request_exact_approval(
                action=approval_action,
                reason=reason,
                request_payload=request_payload,
                previous_approval_id=approval_id,
                previous_status=approval_status,
                previous_record=approval_record,
            )
            if record_idx >= 0:
                records[record_idx]["approval_id"] = refreshed_id
                registry["records"] = records
            mismatch_body = {
                "kind": "web_learning.request.mismatch",
                "approval_id": refreshed_id,
                "previous_approval_id": approval_id,
                "request": request_payload,
                "approval_record": approval_record,
            }
            _atomic_write_display_json(art / "mismatch.json", mismatch_body)
            _atomic_write_display_json(_approval_artifact_dir(approval_id) / "mismatch.json", mismatch_body)
            _append_event(
                registry,
                {
                    "ts": ts,
                    "kind": "approval_requested",
                    "url": recorded_url,
                    "record_id": record_id,
                    "status": "needs_approval",
                    "message": "Learn request approval did not match the exact action and was refreshed.",
                    "approval_id": refreshed_id,
                    "actor": recorded_actor,
                    "domain": domain,
                    "source": recorded_source,
                    "correlation_id": request_id,
                    "meta": {
                        "reason": recorded_reason,
                        "action": approval_action,
                        "previous_approval_id": approval_id,
                        "previous_status": approval_status,
                    },
                },
            )
            registry["last_run_ts"] = ts
            _save(registry)
            return {
                "ok": False,
                "request_id": request_id,
                "record_id": record_id,
                "approval_id": refreshed_id,
                "previous_approval_id": approval_id,
                "artifact_dir": str(art),
                "status": "needs_approval",
                "error": "approval_payload_mismatch",
                "message": "Approval does not match this exact learn request.",
                "meta": {"force": force},
            }

    ingested_record = {
        "id": record_id,
        "ts": ts,
        "url": recorded_url,
        "status": "ingested",
        "method": "GET",
        "http_status": 200,
        "content_type": content_type,
        "bytes": byte_count,
        "duration_ms": duration_ms,
        "title": recorded_title,
        "summary": recorded_summary,
        "domain": domain,
        "source": recorded_source,
        "meta": {"reason": recorded_reason, "request_id": request_id, "force": force},
    }
    if approval_id:
        ingested_record["approval_id"] = approval_id
    if record_idx >= 0:
        records[record_idx] = dict(records[record_idx] | ingested_record)
    else:
        records.append(ingested_record)
    registry["records"] = records
    event_meta = {
        "ts": ts,
        "url": recorded_url,
        "record_id": record_id,
        "actor": recorded_actor,
        "domain": domain,
        "source": recorded_source,
        "correlation_id": request_id,
    }
    if approval_id:
        event_meta["approval_id"] = approval_id
    _append_event(registry, {"kind": "fetch_start", "status": "running", "message": "Fetch started.", **event_meta})
    _append_event(
        registry,
        {
            "kind": "fetch_end",
            "status": "fetched",
            "message": "Fetch completed.",
            "http_status": 200,
            "bytes": byte_count,
            "duration_ms": duration_ms,
            **event_meta,
        },
    )
    _append_event(
        registry,
        {
            "kind": "ingest",
            "status": "ingested",
            "message": "Content ingested successfully.",
            "http_status": 200,
            "bytes": byte_count,
            "duration_ms": duration_ms,
            **event_meta,
        },
    )
    registry["last_run_ts"] = ts
    registry["last_success_ts"] = ts
    registry["last_error_ts"] = 0
    registry["last_error"] = ""
    _save(registry)
    result = {
        "ok": True,
        "request_id": request_id,
        "record_id": record_id,
        "status": "ingested",
        "message": "Learn request accepted.",
        "meta": {"force": force},
    }
    if approval_id:
        result["approval_id"] = approval_id
    return result


def _set_enabled(payload: dict[str, Any]) -> dict[str, Any]:
    valid, desired = _parse_bool(payload.get("enabled"))
    if not valid:
        return {"ok": False, "error": "enabled_required", "message": "Payload must include boolean 'enabled'."}

    reason = _safe_str(payload.get("reason")).strip() or "requested"
    actor = _safe_str(payload.get("actor")).strip() or "api"
    domain = _safe_str(payload.get("domain")).strip().lower()
    meta = redact_governed_metadata(payload.get("meta"))
    force = _to_bool(meta.get("force"), default=False)

    registry = _load()
    policy = registry.get("policy") if isinstance(registry.get("policy"), dict) else _default_policy()
    ts = _now_s()
    current = _effective_enabled(registry)
    if desired == current:
        return {
            "ok": True,
            "status": "unchanged",
            "applied": True,
            "enabled": current,
            "ts": ts,
            "message": "No change.",
        }

    approval_required = desired and _to_bool(policy.get("approvals_required"), default=True)
    approval_action = "web_learning.set_enabled"
    approval_id = _approval_id_from_payload(payload)
    request_payload = _approval_request_payload(
        approval_action,
        {"enabled": desired, "actor": actor, "domain": domain, "meta": _approval_meta(meta)},
    )

    if approval_required and not force:
        if not approval_id:
            approval_id, art = _request_exact_approval(
                action=approval_action,
                reason=reason,
                request_payload=request_payload,
            )
            _append_event(
                registry,
                {
                    "ts": ts,
                    "kind": "approval_requested",
                    "status": "pending",
                    "message": "Enable request requires approval.",
                    "approval_id": approval_id,
                    "actor": actor,
                    "domain": domain,
                    "source": actor,
                    "meta": {"reason": reason, "action": approval_action},
                },
            )
            _save(registry)
            return {
                "ok": True,
                "approval_id": approval_id,
                "artifact_dir": str(art),
                "status": "pending",
                "applied": False,
                "enabled": current,
                "ts": ts,
                "message": "Enable request submitted for approval.",
                "meta": {"force": force},
            }

        approval_status, approval_record = _approval_status(approval_id)
        if approval_status in {"missing", "corrupt"}:
            refreshed_id, art = _request_exact_approval(
                action=approval_action,
                reason=reason,
                request_payload=request_payload,
                previous_approval_id=approval_id,
                previous_status=approval_status,
                previous_record=approval_record,
            )
            _atomic_write_display_json(
                art / "error.json",
                {
                    "kind": "web_learning.set_enabled.error",
                    "approval_id": refreshed_id,
                    "previous_approval_id": approval_id,
                    "status": approval_status,
                    "request": request_payload,
                },
            )
            _append_event(
                registry,
                {
                    "ts": ts,
                    "kind": "approval_requested",
                    "status": "needs_approval",
                    "message": "Enable request approval was missing; a fresh exact-action approval is required.",
                    "approval_id": refreshed_id,
                    "actor": actor,
                    "domain": domain,
                    "source": actor,
                    "meta": {
                        "reason": reason,
                        "action": approval_action,
                        "previous_approval_id": approval_id,
                        "previous_status": approval_status,
                    },
                },
            )
            _save(registry)
            return {
                "ok": False,
                "approval_id": refreshed_id,
                "previous_approval_id": approval_id,
                "artifact_dir": str(art),
                "status": "needs_approval",
                "applied": False,
                "enabled": current,
                "ts": ts,
                "error": "approval_not_found",
                "message": "Approval was missing for this enable request; a fresh exact-action approval is required.",
                "meta": {"force": force},
            }
        if approval_status == "pending":
            return {
                "ok": True,
                "approval_id": approval_id,
                "status": "pending",
                "applied": False,
                "enabled": current,
                "ts": ts,
                "message": "Enable request is awaiting approval.",
                "meta": {"force": force},
            }
        if approval_status in {"rejected", "emergency"}:
            return {
                "ok": False,
                "approval_id": approval_id,
                "status": "denied",
                "applied": False,
                "enabled": current,
                "ts": ts,
                "error": "approval_denied",
                "message": "Approval was denied for this enable request.",
                "meta": {"force": force, "approval_status": approval_status},
            }
        if approval_status != "approved":
            return {
                "ok": False,
                "approval_id": approval_id,
                "status": "needs_approval",
                "applied": False,
                "enabled": current,
                "ts": ts,
                "error": "approval_not_found",
                "message": "A matching approved request was not found for this enable request.",
                "meta": {"force": force},
            }
        if not _approval_matches(approval_record, action=approval_action, request_payload=request_payload):
            refreshed_id, art = _request_exact_approval(
                action=approval_action,
                reason=reason,
                request_payload=request_payload,
                previous_approval_id=approval_id,
                previous_status=approval_status,
                previous_record=approval_record,
            )
            mismatch_body = {
                "kind": "web_learning.set_enabled.mismatch",
                "approval_id": refreshed_id,
                "previous_approval_id": approval_id,
                "request": request_payload,
                "approval_record": approval_record,
            }
            _atomic_write_display_json(art / "mismatch.json", mismatch_body)
            _atomic_write_display_json(_approval_artifact_dir(approval_id) / "mismatch.json", mismatch_body)
            _append_event(
                registry,
                {
                    "ts": ts,
                    "kind": "approval_requested",
                    "status": "needs_approval",
                    "message": "Enable request approval did not match the exact action and was refreshed.",
                    "approval_id": refreshed_id,
                    "actor": actor,
                    "domain": domain,
                    "source": actor,
                    "meta": {
                        "reason": reason,
                        "action": approval_action,
                        "previous_approval_id": approval_id,
                        "previous_status": approval_status,
                    },
                },
            )
            _save(registry)
            return {
                "ok": False,
                "approval_id": refreshed_id,
                "previous_approval_id": approval_id,
                "artifact_dir": str(art),
                "status": "needs_approval",
                "applied": False,
                "enabled": current,
                "ts": ts,
                "error": "approval_payload_mismatch",
                "message": "Approval does not match this exact enable request.",
                "meta": {"force": force},
            }

    policy["enabled"] = desired
    policy["ts"] = ts
    registry["policy"] = policy
    registry["enabled"] = desired
    _append_event(
        registry,
        {
            "ts": ts,
            "kind": "approval_resolved",
            "status": "applied",
            "message": f"Web learning {'enabled' if desired else 'disabled'}.",
            "approval_id": approval_id or None,
            "actor": actor,
            "domain": domain,
            "source": actor,
            "meta": {"reason": reason, "force": force},
        },
    )
    _save(registry)
    return {
        "ok": True,
        "approval_id": approval_id or None,
        "status": "applied",
        "applied": True,
        "enabled": desired,
        "ts": ts,
        "message": f"Web learning {'enabled' if desired else 'disabled'}.",
        "meta": {"force": force},
    }


def _decide_quarantine(item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    resolved_id = _safe_str(item_id).strip() or _safe_str(payload.get("id")).strip()
    if not resolved_id:
        return {"ok": False, "error": "id_required"}
    if not _ID_RE.match(resolved_id):
        return {"ok": False, "error": "invalid id"}

    action = _safe_str(payload.get("action")).strip().lower()
    if not action:
        return {"ok": False, "error": "action_required"}

    reason = _safe_str(payload.get("reason")).strip() or "requested"
    actor = _safe_str(payload.get("actor")).strip() or "api"
    domain = _safe_str(payload.get("domain")).strip().lower()
    meta = redact_governed_metadata(payload.get("meta"))
    force = _to_bool(meta.get("force"), default=False)
    ts = _now_s()

    registry = _load()
    quarantine = registry.get("quarantine") if isinstance(registry.get("quarantine"), list) else []
    idx = next((i for i, item in enumerate(quarantine) if _safe_str(item.get("id")).strip() == resolved_id), -1)
    if idx < 0:
        return {"ok": False, "error": "not_found", "id": resolved_id}
    q = quarantine[idx]

    policy = registry.get("policy") if isinstance(registry.get("policy"), dict) else _default_policy()
    approval_required = action == "delete" and _to_bool(policy.get("approvals_required"), default=True)
    approval_action = "web_learning.quarantine.delete"
    approval_domain = domain or _safe_str(q.get("domain")).strip().lower()
    approval_id = _approval_id_from_payload(payload)
    request_payload = _approval_request_payload(
        approval_action,
        {
            "id": resolved_id,
            "url": _safe_str(q.get("url")).strip(),
            "record_id": _safe_str(q.get("record_id")).strip(),
            "actor": actor,
            "domain": approval_domain,
            "meta": _approval_meta(meta),
        },
    )
    if approval_required and not force:
        if not approval_id:
            approval_id, art = _request_exact_approval(
                action=approval_action,
                reason=reason,
                request_payload=request_payload,
            )
            q["approval_id"] = approval_id
            quarantine[idx] = q
            registry["quarantine"] = quarantine
            _append_event(
                registry,
                {
                    "ts": ts,
                    "kind": "approval_requested",
                    "url": q.get("url"),
                    "record_id": q.get("record_id"),
                    "status": "pending",
                    "message": "Delete quarantine item requires approval.",
                    "approval_id": approval_id,
                    "quarantine_id": resolved_id,
                    "actor": actor,
                    "domain": approval_domain,
                    "source": actor,
                    "meta": {"reason": reason, "action": action},
                },
            )
            _save(registry)
            return {
                "ok": True,
                "approval_id": approval_id,
                "artifact_dir": str(art),
                "status": "pending",
                "applied": False,
                "message": "Delete request submitted for approval.",
            }

        approval_status, approval_record = _approval_status(approval_id)
        if approval_status in {"missing", "corrupt"}:
            refreshed_id, art = _request_exact_approval(
                action=approval_action,
                reason=reason,
                request_payload=request_payload,
                previous_approval_id=approval_id,
                previous_status=approval_status,
                previous_record=approval_record,
            )
            q["approval_id"] = refreshed_id
            quarantine[idx] = q
            registry["quarantine"] = quarantine
            _atomic_write_display_json(
                art / "error.json",
                {
                    "kind": "web_learning.quarantine.delete.error",
                    "approval_id": refreshed_id,
                    "previous_approval_id": approval_id,
                    "quarantine_id": resolved_id,
                    "status": approval_status,
                    "request": request_payload,
                },
            )
            _append_event(
                registry,
                {
                    "ts": ts,
                    "kind": "approval_requested",
                    "url": q.get("url"),
                    "record_id": q.get("record_id"),
                    "status": "needs_approval",
                    "message": "Delete approval was missing; a fresh exact-action approval is required.",
                    "approval_id": refreshed_id,
                    "quarantine_id": resolved_id,
                    "actor": actor,
                    "domain": approval_domain,
                    "source": actor,
                    "meta": {
                        "reason": reason,
                        "action": action,
                        "previous_approval_id": approval_id,
                        "previous_status": approval_status,
                    },
                },
            )
            _save(registry)
            return {
                "ok": False,
                "approval_id": refreshed_id,
                "previous_approval_id": approval_id,
                "artifact_dir": str(art),
                "status": "needs_approval",
                "applied": False,
                "error": "approval_not_found",
                "message": "Approval was missing for this delete request; a fresh exact-action approval is required.",
            }
        if approval_status == "pending":
            return {
                "ok": True,
                "approval_id": approval_id,
                "status": "pending",
                "applied": False,
                "message": "Delete request is awaiting approval.",
            }
        if approval_status in {"rejected", "emergency"}:
            return {
                "ok": False,
                "approval_id": approval_id,
                "status": "denied",
                "applied": False,
                "error": "approval_denied",
                "message": "Approval was denied for this delete request.",
                "meta": {"approval_status": approval_status},
            }
        if approval_status != "approved":
            return {
                "ok": False,
                "approval_id": approval_id,
                "status": "needs_approval",
                "applied": False,
                "error": "approval_not_found",
                "message": "A matching approved request was not found for this delete request.",
            }
        if not _approval_matches(approval_record, action=approval_action, request_payload=request_payload):
            refreshed_id, art = _request_exact_approval(
                action=approval_action,
                reason=reason,
                request_payload=request_payload,
                previous_approval_id=approval_id,
                previous_status=approval_status,
                previous_record=approval_record,
            )
            q["approval_id"] = refreshed_id
            quarantine[idx] = q
            registry["quarantine"] = quarantine
            mismatch_body = {
                "kind": "web_learning.quarantine.delete.mismatch",
                "approval_id": refreshed_id,
                "previous_approval_id": approval_id,
                "quarantine_id": resolved_id,
                "request": request_payload,
                "approval_record": approval_record,
            }
            _atomic_write_display_json(art / "mismatch.json", mismatch_body)
            _atomic_write_display_json(_approval_artifact_dir(approval_id) / "mismatch.json", mismatch_body)
            _append_event(
                registry,
                {
                    "ts": ts,
                    "kind": "approval_requested",
                    "url": q.get("url"),
                    "record_id": q.get("record_id"),
                    "status": "needs_approval",
                    "message": "Delete approval did not match the exact action and was refreshed.",
                    "approval_id": refreshed_id,
                    "quarantine_id": resolved_id,
                    "actor": actor,
                    "domain": approval_domain,
                    "source": actor,
                    "meta": {
                        "reason": reason,
                        "action": action,
                        "previous_approval_id": approval_id,
                        "previous_status": approval_status,
                    },
                },
            )
            _save(registry)
            return {
                "ok": False,
                "approval_id": refreshed_id,
                "previous_approval_id": approval_id,
                "artifact_dir": str(art),
                "status": "needs_approval",
                "applied": False,
                "error": "approval_payload_mismatch",
                "message": "Approval does not match this exact delete request.",
            }

    records = registry.get("records") if isinstance(registry.get("records"), list) else []
    record_id = _safe_str(q.get("record_id")).strip()
    ridx = next((i for i, item in enumerate(records) if _safe_str(item.get("id")).strip() == record_id), -1)

    if action == "release":
        quarantine.pop(idx)
        if ridx >= 0:
            records[ridx]["status"] = "pending"
            records[ridx]["quarantine_id"] = ""
            records[ridx]["error"] = ""
        status = "released"
        message = "Quarantine item released."
    elif action == "delete":
        quarantine.pop(idx)
        if ridx >= 0:
            records[ridx]["status"] = "failed"
            records[ridx]["quarantine_id"] = ""
            records[ridx]["error"] = "Deleted from quarantine."
        status = "deleted"
        message = "Quarantine item deleted."
    else:
        q["status"] = "kept" if action == "keep" else action
        q_meta = q.get("meta") if isinstance(q.get("meta"), dict) else {}
        q_meta["decision_reason"] = reason
        q["meta"] = q_meta
        quarantine[idx] = q
        if ridx >= 0:
            records[ridx]["status"] = "quarantined"
            records[ridx]["quarantine_id"] = resolved_id
        status = q["status"]
        message = "Quarantine item updated."

    registry["quarantine"] = quarantine
    registry["records"] = records
    _append_event(
        registry,
        {
            "ts": ts,
            "kind": "approval_resolved" if action in {"release", "delete"} else "quarantine",
            "url": q.get("url"),
            "record_id": q.get("record_id"),
            "status": status,
            "message": message,
            "approval_id": approval_id or _safe_str(q.get("approval_id")).strip(),
            "quarantine_id": resolved_id,
            "actor": actor,
            "domain": approval_domain,
            "source": actor,
            "meta": {"reason": reason, "action": action, "force": force},
        },
    )
    _save(registry)
    return {
        "ok": True,
        "approval_id": approval_id or _safe_str(q.get("approval_id")).strip() or None,
        "status": status,
        "applied": True,
        "message": message,
    }


def _csv_fields(kind: str) -> list[str]:
    if kind == "records":
        return [
            "id",
            "ts",
            "url",
            "status",
            "http_status",
            "method",
            "content_type",
            "bytes",
            "duration_ms",
            "title",
            "summary",
            "domain",
            "source",
            "approval_id",
            "quarantine_id",
            "error",
        ]
    if kind == "events":
        return [
            "id",
            "ts",
            "kind",
            "url",
            "record_id",
            "status",
            "message",
            "http_status",
            "bytes",
            "duration_ms",
            "approval_id",
            "quarantine_id",
            "actor",
            "domain",
            "source",
            "correlation_id",
            "operation_id",
        ]
    return ["id", "ts", "url", "reason", "status", "record_id", "approval_id", "evidence", "domain", "source"]


def _render_export(kind: str, fmt: str, items: list[dict[str, Any]]) -> tuple[str, str]:
    if fmt == "jsonl":
        return "\n".join(json.dumps(item, ensure_ascii=False, default=str) for item in items), "application/jsonl"
    if fmt == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=_csv_fields(kind), extrasaction="ignore")
        writer.writeheader()
        for item in items:
            writer.writerow(item)
        return output.getvalue(), "text/csv"
    return json.dumps({"items": items}, ensure_ascii=False, indent=2, default=str), "application/json"


def _export(
    kind: str,
    format: str = "json",
    start_ts: int | None = None,
    end_ts: int | None = None,
    status: str | None = None,
    domain: str | None = None,
    search: str | None = None,
    limit: int = 10_000,
    cursor: str | None = None,
) -> Response:
    normalized_kind = _safe_str(kind).strip().lower()
    if normalized_kind not in {"records", "events", "quarantine"}:
        return Response(
            content=json.dumps({"ok": False, "error": "unsupported_kind"}, ensure_ascii=False),
            media_type="application/json",
            status_code=400,
        )
    fmt = _safe_str(format).strip().lower() or "json"
    if fmt not in {"json", "jsonl", "csv"}:
        return Response(
            content=json.dumps({"ok": False, "error": "unsupported_format"}, ensure_ascii=False),
            media_type="application/json",
            status_code=400,
        )

    page = _query(
        normalized_kind,
        limit=max(1, min(int(limit), 10_000)),
        offset=0,
        cursor=cursor,
        start_ts=start_ts,
        end_ts=end_ts,
        status=status,
        domain=domain,
        search=search,
    )
    content, media_type = _render_export(
        normalized_kind, fmt, page.get("items") if isinstance(page.get("items"), list) else []
    )
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    ext = "jsonl" if fmt == "jsonl" else fmt
    filename = f"francis-web-learning-{normalized_kind}-{stamp}.{ext}"
    return Response(
        content=content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/")
def root_status() -> dict[str, Any]:
    return status()


@router.get("/status")
def status() -> dict[str, Any]:
    try:
        registry = _load()
        policy = registry.get("policy") if isinstance(registry.get("policy"), dict) else _default_policy()
        records = registry.get("records") if isinstance(registry.get("records"), list) else []
        counts = {
            "records": len(records),
            "events": len(registry.get("events") or []),
            "quarantine": len(registry.get("quarantine") or []),
            "pending": len(
                [r for r in records if _safe_str((r or {}).get("status")).strip().lower() in {"pending", "queued"}]
            ),
            "in_flight": len(
                [
                    r
                    for r in records
                    if _safe_str((r or {}).get("status")).strip().lower() in {"pending", "queued", "fetched", "parsed"}
                ]
            ),
        }
        return {
            "ok": True,
            "route": "web_learning",
            "status": "ready",
            "ts": _now_s(),
            "enabled": _effective_enabled(registry),
            "approvals_required": _to_bool(policy.get("approvals_required"), default=True),
            "queue_depth": counts["pending"],
            "in_flight": counts["in_flight"],
            "concurrency": int((policy.get("limits") or {}).get("concurrency") or 2),
            "last_run_ts": int(registry.get("last_run_ts") or 0),
            "last_success_ts": int(registry.get("last_success_ts") or 0),
            "last_error_ts": int(registry.get("last_error_ts") or 0),
            "last_error": _safe_str(registry.get("last_error")).strip(),
            "env_profile": _safe_str(registry.get("env_profile")).strip() or "dev",
            "run_mode": _safe_str(registry.get("run_mode")).strip() or "api",
            "counts": counts,
            "meta": {"updated_at": int(registry.get("updated_at") or _now_s())},
        }
    except Exception as exc:
        return {"ok": False, "route": "web_learning", "status": "error", "error": api_error_message(exc)}


@router.get("/policy")
@router.get("/config")
def policy() -> dict[str, Any]:
    try:
        registry = _load()
        body = registry.get("policy") if isinstance(registry.get("policy"), dict) else _default_policy()
        body = dict(_default_policy() | body)
        body["enabled"] = _effective_enabled(registry)
        return {"ok": True, "policy": body}
    except Exception as exc:
        return {"ok": False, "policy": _default_policy(), "error": api_error_message(exc)}


@router.get("/records")
@router.get("/recent")
@router.get("/log/records")
def list_records(
    limit: int = 200,
    offset: int = 0,
    cursor: str | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
    status: str | None = None,
    domain: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    return _query(
        "records",
        limit=limit,
        offset=offset,
        cursor=cursor,
        start_ts=start_ts,
        end_ts=end_ts,
        status=status,
        domain=domain,
        search=search,
    )


@router.get("/events")
@router.get("/log")
@router.get("/audit")
def list_events(
    limit: int = 200,
    offset: int = 0,
    cursor: str | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
    status: str | None = None,
    domain: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    return _query(
        "events",
        limit=limit,
        offset=offset,
        cursor=cursor,
        start_ts=start_ts,
        end_ts=end_ts,
        status=status,
        domain=domain,
        search=search,
    )


@router.get("/quarantine")
@router.get("/quarantine/items")
def list_quarantine(
    limit: int = 200,
    offset: int = 0,
    cursor: str | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
    status: str | None = None,
    domain: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    return _query(
        "quarantine",
        limit=limit,
        offset=offset,
        cursor=cursor,
        start_ts=start_ts,
        end_ts=end_ts,
        status=status,
        domain=domain,
        search=search,
    )


@router.post("/request")
@router.post("/learn")
@router.post("/enqueue")
def request_learn(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return _request_learn(payload)
    except Exception as exc:
        return {"ok": False, "error": api_error_message(exc)}


@router.post("/enabled")
@router.post("/toggle")
@router.post("/config")
def set_enabled(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return _set_enabled(payload)
    except Exception as exc:
        return {"ok": False, "error": api_error_message(exc)}


@router.post("/quarantine/decide")
@router.post("/quarantine/resolve")
def decide_quarantine_payload(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return _decide_quarantine("", payload)
    except Exception as exc:
        return {"ok": False, "error": api_error_message(exc)}


@router.post("/quarantine/{item_id}/decide")
@router.post("/quarantine/{item_id}")
def decide_quarantine(item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return _decide_quarantine(item_id, payload)
    except Exception as exc:
        return {"ok": False, "error": api_error_message(exc)}


@router.post("/export")
def export_post(payload: dict[str, Any]) -> Response:
    try:
        return _export(
            kind=_safe_str(payload.get("kind")).strip().lower(),
            format=_safe_str(payload.get("format")).strip().lower() or "json",
            start_ts=int(payload.get("start_ts")) if payload.get("start_ts") is not None else None,
            end_ts=int(payload.get("end_ts")) if payload.get("end_ts") is not None else None,
            status=_safe_str(payload.get("status")).strip() or None,
            domain=_safe_str(payload.get("domain")).strip() or None,
            search=_safe_str(payload.get("search")).strip() or None,
            limit=int(payload.get("limit") or 10_000),
            cursor=_safe_str(payload.get("cursor")).strip() or None,
        )
    except Exception as exc:
        return Response(
            content=json.dumps({"ok": False, "error": api_error_message(exc)}, ensure_ascii=False),
            media_type="application/json",
            status_code=500,
        )


@router.get("/records/export")
def export_records(
    format: str = "json",
    start_ts: int | None = None,
    end_ts: int | None = None,
    status: str | None = None,
    domain: str | None = None,
    search: str | None = None,
    limit: int = 10_000,
    cursor: str | None = None,
) -> Response:
    return _export("records", format, start_ts, end_ts, status, domain, search, limit, cursor)


@router.get("/events/export")
def export_events(
    format: str = "json",
    start_ts: int | None = None,
    end_ts: int | None = None,
    status: str | None = None,
    domain: str | None = None,
    search: str | None = None,
    limit: int = 10_000,
    cursor: str | None = None,
) -> Response:
    return _export("events", format, start_ts, end_ts, status, domain, search, limit, cursor)


@router.get("/quarantine/export")
def export_quarantine(
    format: str = "json",
    start_ts: int | None = None,
    end_ts: int | None = None,
    status: str | None = None,
    domain: str | None = None,
    search: str | None = None,
    limit: int = 10_000,
    cursor: str | None = None,
) -> Response:
    return _export("quarantine", format, start_ts, end_ts, status, domain, search, limit, cursor)


@router.get("/export/{kind}")
@router.get("/{kind}/export")
def export_kind(
    kind: str,
    format: str = "json",
    start_ts: int | None = None,
    end_ts: int | None = None,
    status: str | None = None,
    domain: str | None = None,
    search: str | None = None,
    limit: int = 10_000,
    cursor: str | None = None,
) -> Response:
    return _export(kind, format, start_ts, end_ts, status, domain, search, limit, cursor)
