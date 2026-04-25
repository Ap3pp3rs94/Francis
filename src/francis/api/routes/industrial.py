from __future__ import annotations

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

from fastapi import APIRouter, Query
from fastapi.responses import Response

from francis.governance import approvals as approval_store
from francis.governance.redaction import (
    redact_governed_metadata,
    redact_governed_value,
    seal_governed_approval_value,
)
from francis.kernel.paths import data_dir

router = APIRouter()
_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{1,127}$")


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _now_s() -> int:
    return int(time.time())


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


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


def _parse_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return [_safe_str(item).strip() for item in value if _safe_str(item).strip()]
    return []


def _normalize_meta(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _redacted_runtime_params(value: Any) -> dict[str, Any]:
    redacted = redact_governed_value(_normalize_meta(value))
    return redacted if isinstance(redacted, dict) else {}


def _validate_id(value: str, field: str = "id") -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field} is required")
    if not _ID_RE.match(text):
        raise ValueError(f"invalid {field}")
    return text


def _industrial_dir() -> Path:
    return data_dir() / "industrial"


def _registry_path() -> Path:
    return _industrial_dir() / "_registry.json"


def _default_registry() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": _now_s(),
        "assets": {},
        "processes": {},
        "simulations": {},
        "runs": {},
        "safety_validations": {},
        "telemetry": [],
        "interventions": [],
        "digital_twin_actions": [],
    }


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _load_registry() -> dict[str, Any]:
    path = _registry_path()
    if not path.exists():
        return _default_registry()
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return _default_registry()
    if not isinstance(raw, dict):
        return _default_registry()
    out = _default_registry()
    out["version"] = int(raw.get("version") or 1)
    out["updated_at"] = int(raw.get("updated_at") or _now_s())
    for key in ("assets", "processes", "simulations", "runs", "safety_validations"):
        if isinstance(raw.get(key), dict):
            out[key] = raw[key]
    for key in ("telemetry", "interventions", "digital_twin_actions"):
        if isinstance(raw.get(key), list):
            out[key] = raw[key]
    return out


def _save_registry(registry: dict[str, Any]) -> None:
    normalized = {
        "version": int(registry.get("version") or 1),
        "updated_at": _now_s(),
        "assets": registry.get("assets") if isinstance(registry.get("assets"), dict) else {},
        "processes": registry.get("processes") if isinstance(registry.get("processes"), dict) else {},
        "simulations": registry.get("simulations") if isinstance(registry.get("simulations"), dict) else {},
        "runs": registry.get("runs") if isinstance(registry.get("runs"), dict) else {},
        "safety_validations": registry.get("safety_validations")
        if isinstance(registry.get("safety_validations"), dict)
        else {},
        "telemetry": registry.get("telemetry") if isinstance(registry.get("telemetry"), list) else [],
        "interventions": registry.get("interventions") if isinstance(registry.get("interventions"), list) else [],
        "digital_twin_actions": registry.get("digital_twin_actions")
        if isinstance(registry.get("digital_twin_actions"), list)
        else [],
    }
    if len(normalized["telemetry"]) > 5000:
        normalized["telemetry"] = normalized["telemetry"][-5000:]
    if len(normalized["interventions"]) > 5000:
        normalized["interventions"] = normalized["interventions"][-5000:]
    if len(normalized["digital_twin_actions"]) > 5000:
        normalized["digital_twin_actions"] = normalized["digital_twin_actions"][-5000:]
    _atomic_write(_registry_path(), normalized)


def _read_section(registry: dict[str, Any], section: str, entity_id: str) -> dict[str, Any] | None:
    section_obj = registry.get(section)
    if not isinstance(section_obj, dict):
        return None
    raw = section_obj.get(entity_id)
    return raw if isinstance(raw, dict) else None


def _write_section(registry: dict[str, Any], section: str, entity_id: str, item: dict[str, Any]) -> None:
    section_obj = registry.get(section)
    if not isinstance(section_obj, dict):
        section_obj = {}
        registry[section] = section_obj
    section_obj[entity_id] = item


def _delete_section(registry: dict[str, Any], section: str, entity_id: str) -> bool:
    section_obj = registry.get(section)
    if not isinstance(section_obj, dict):
        return False
    if entity_id not in section_obj:
        return False
    del section_obj[entity_id]
    return True


def _normalize_asset(entity_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    created_ts = int(raw.get("created_ts") or _now_s())
    updated_ts = int(raw.get("updated_ts") or created_ts)
    return {
        "id": entity_id,
        "name": _safe_str(raw.get("name")).strip() or entity_id,
        "asset_type": _safe_str(raw.get("asset_type")).strip(),
        "status": _safe_str(raw.get("status")).strip() or "active",
        "risk": _safe_str(raw.get("risk")).strip(),
        "location": _safe_str(raw.get("location")).strip(),
        "tags": _parse_list(raw.get("tags")),
        "created_ts": created_ts,
        "updated_ts": updated_ts,
        "last_seen_ts": int(raw.get("last_seen_ts") or 0),
        "model_ref": _safe_str(raw.get("model_ref")).strip(),
        "connector_ref": _safe_str(raw.get("connector_ref")).strip(),
        "meta": _normalize_meta(raw.get("meta")),
    }


def _normalize_process(entity_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    created_ts = int(raw.get("created_ts") or _now_s())
    updated_ts = int(raw.get("updated_ts") or created_ts)
    return {
        "id": entity_id,
        "name": _safe_str(raw.get("name")).strip() or entity_id,
        "status": _safe_str(raw.get("status")).strip() or "active",
        "risk": _safe_str(raw.get("risk")).strip(),
        "description": _safe_str(raw.get("description")).strip(),
        "domain": _safe_str(raw.get("domain")).strip(),
        "tags": _parse_list(raw.get("tags")),
        "inputs": _parse_list(raw.get("inputs")),
        "outputs": _parse_list(raw.get("outputs")),
        "created_ts": created_ts,
        "updated_ts": updated_ts,
        "meta": _normalize_meta(raw.get("meta")),
    }


def _normalize_simulation(entity_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    created_ts = int(raw.get("created_ts") or _now_s())
    updated_ts = int(raw.get("updated_ts") or created_ts)
    return {
        "id": entity_id,
        "name": _safe_str(raw.get("name")).strip() or entity_id,
        "status": _safe_str(raw.get("status")).strip() or "active",
        "risk": _safe_str(raw.get("risk")).strip(),
        "description": _safe_str(raw.get("description")).strip(),
        "engine": _safe_str(raw.get("engine")).strip(),
        "scenario": _safe_str(raw.get("scenario")).strip(),
        "default_params": _normalize_meta(raw.get("default_params")),
        "asset_id": _safe_str(raw.get("asset_id")).strip(),
        "process_id": _safe_str(raw.get("process_id")).strip(),
        "digital_twin_id": _safe_str(raw.get("digital_twin_id")).strip(),
        "tags": _parse_list(raw.get("tags")),
        "created_ts": created_ts,
        "updated_ts": updated_ts,
        "meta": _normalize_meta(raw.get("meta")),
    }


def _normalize_run(entity_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entity_id,
        "simulation_id": _safe_str(raw.get("simulation_id")).strip(),
        "status": _safe_str(raw.get("status")).strip() or "queued",
        "requested_ts": int(raw.get("requested_ts") or _now_s()),
        "started_ts": int(raw.get("started_ts") or 0),
        "completed_ts": int(raw.get("completed_ts") or 0),
        "requested_by": _safe_str(raw.get("requested_by")).strip(),
        "reason": _safe_str(raw.get("reason")).strip(),
        "params": _normalize_meta(raw.get("params")),
        "metrics": {k: v for k, v in _normalize_meta(raw.get("metrics")).items() if isinstance(v, (int, float))},
        "summary": _safe_str(raw.get("summary")).strip(),
        "artifacts": raw.get("artifacts") if isinstance(raw.get("artifacts"), list) else [],
        "meta": _normalize_meta(raw.get("meta")),
    }


def _normalize_validation(entity_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    violations = raw.get("violations") if isinstance(raw.get("violations"), list) else []
    artifacts = raw.get("artifacts") if isinstance(raw.get("artifacts"), list) else []
    return {
        "id": entity_id,
        "ts": int(raw.get("ts") or _now_s()),
        "target_kind": _safe_str(raw.get("target_kind")).strip(),
        "target_id": _safe_str(raw.get("target_id")).strip(),
        "status": _safe_str(raw.get("status")).strip() or "unknown",
        "risk": _safe_str(raw.get("risk")).strip(),
        "summary": _safe_str(raw.get("summary")).strip(),
        "violations": violations,
        "artifacts": artifacts,
        "meta": _normalize_meta(raw.get("meta")),
    }


def _normalize_telemetry(raw: dict[str, Any]) -> dict[str, Any] | None:
    fields = raw.get("fields")
    if not isinstance(fields, dict):
        return None
    normalized_fields: dict[str, Any] = {}
    for key, value in fields.items():
        if isinstance(value, (int, float, bool, str)) or value is None:
            normalized_fields[_safe_str(key)] = value
    return {
        "ts": int(raw.get("ts") or _now_s()),
        "source_id": _safe_str(raw.get("source_id")).strip(),
        "fields": normalized_fields,
        "quality": _safe_str(raw.get("quality")).strip(),
        "meta": _normalize_meta(raw.get("meta")),
    }


def _append_telemetry(
    registry: dict[str, Any], source_id: str, fields: dict[str, Any], meta: dict[str, Any] | None = None
) -> None:
    telemetry = registry.get("telemetry")
    if not isinstance(telemetry, list):
        telemetry = []
        registry["telemetry"] = telemetry
    point = _normalize_telemetry(
        {"ts": _now_s(), "source_id": source_id, "fields": fields, "quality": "estimated", "meta": meta or {}}
    )
    if point is not None:
        telemetry.append(point)


def _apply_filters(
    items: list[dict[str, Any]],
    *,
    status: str = "",
    risk: str = "",
    search: str = "",
    tags: list[str] | None = None,
    include_archived: bool = False,
    extra: dict[str, str] | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
    time_key: str = "updated_ts",
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    tag_set = set(tags or [])
    for item in items:
        current_status = _safe_str(item.get("status")).strip().lower()
        if status and current_status != status:
            continue
        if not include_archived and current_status == "archived":
            continue
        if risk and _safe_str(item.get("risk")).strip().lower() != risk:
            continue
        if tag_set and not tag_set.issubset(set(_parse_list(item.get("tags")))):
            continue
        if extra:
            mismatch = False
            for key, value in extra.items():
                if value and _safe_str(item.get(key)).strip().lower() != value:
                    mismatch = True
                    break
            if mismatch:
                continue
        if start_ts is not None or end_ts is not None:
            ts = int(item.get(time_key) or 0)
            if start_ts is not None and ts < int(start_ts):
                continue
            if end_ts is not None and ts > int(end_ts):
                continue
        if search:
            haystack = json.dumps(item, ensure_ascii=False, default=str).lower()
            if search not in haystack:
                continue
        out.append(item)
    return out


def _paginate(
    items: list[dict[str, Any]], limit: int, offset: int, cursor: str | None = None
) -> tuple[list[dict[str, Any]], int, int, int, str | None]:
    safe_limit = max(1, min(int(limit), 5000))
    safe_offset = max(0, int(offset))
    if cursor and cursor.isdigit():
        safe_offset = int(cursor)
    total = len(items)
    page = items[safe_offset : safe_offset + safe_limit]
    next_cursor = str(safe_offset + safe_limit) if safe_offset + safe_limit < total else None
    return page, total, safe_limit, safe_offset, next_cursor


def _list_section(registry: dict[str, Any], section: str, normalizer: Any) -> list[dict[str, Any]]:
    section_obj = registry.get(section)
    out: list[dict[str, Any]] = []
    if isinstance(section_obj, dict):
        for entity_id, raw in section_obj.items():
            if isinstance(raw, dict):
                out.append(normalizer(_safe_str(entity_id), raw))
    return out


def _request_approval(action: str, reason: str, payload: dict[str, Any]) -> str:
    try:
        item = approval_store.request(action, reason, payload)
    except Exception:
        return ""
    return _safe_str(item.get("id")).strip()


def _approval_artifact_dir(approval_id: str) -> Path:
    return data_dir() / "artifacts" / "industrial" / "approvals" / _safe_str(approval_id).strip()


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
        "kind": "industrial.approval.request",
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
    _atomic_write(art / "request.json", request_body)
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


def _find_validation_record(
    registry: dict[str, Any],
    *,
    validation_id: str = "",
    approval_id: str = "",
) -> tuple[str, dict[str, Any] | None]:
    validations = registry.get("safety_validations")
    if not isinstance(validations, dict):
        return "", None

    resolved_validation_id = _safe_str(validation_id).strip()
    if resolved_validation_id:
        raw = validations.get(resolved_validation_id)
        return resolved_validation_id, raw if isinstance(raw, dict) else None

    resolved_approval_id = _safe_str(approval_id).strip()
    if not resolved_approval_id:
        return "", None

    for candidate_id, raw in validations.items():
        if not isinstance(raw, dict):
            continue
        meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
        current_approval_id = _safe_str(meta.get("approval_id")).strip()
        previous_approval_id = _safe_str(meta.get("previous_approval_id")).strip()
        if resolved_approval_id and resolved_approval_id in {current_approval_id, previous_approval_id}:
            return _safe_str(candidate_id).strip(), raw

    return "", None


def _find_digital_twin_action_record(
    registry: dict[str, Any],
    *,
    action_id: str = "",
    approval_id: str = "",
) -> tuple[int, dict[str, Any] | None]:
    actions = registry.get("digital_twin_actions")
    if not isinstance(actions, list):
        return -1, None

    resolved_action_id = _safe_str(action_id).strip()
    if resolved_action_id:
        for idx, raw in enumerate(actions):
            if isinstance(raw, dict) and _safe_str(raw.get("id")).strip() == resolved_action_id:
                return idx, raw

    resolved_approval_id = _safe_str(approval_id).strip()
    if not resolved_approval_id:
        return -1, None

    for idx, raw in enumerate(actions):
        if not isinstance(raw, dict):
            continue
        current_approval_id = _safe_str(raw.get("approval_id")).strip()
        previous_approval_id = _safe_str(raw.get("previous_approval_id")).strip()
        if resolved_approval_id and resolved_approval_id in {current_approval_id, previous_approval_id}:
            return idx, raw

    return -1, None


def _find_intervention_record(
    registry: dict[str, Any],
    *,
    intervention_id: str = "",
    request_id: str = "",
    approval_id: str = "",
    mode: str = "",
) -> tuple[int, dict[str, Any] | None]:
    interventions = registry.get("interventions")
    if not isinstance(interventions, list):
        return -1, None

    resolved_intervention_id = _safe_str(intervention_id).strip()
    resolved_request_id = _safe_str(request_id).strip()
    resolved_approval_id = _safe_str(approval_id).strip()
    resolved_mode = _safe_str(mode).strip()

    for idx, raw in enumerate(interventions):
        if not isinstance(raw, dict):
            continue
        if resolved_mode and _safe_str(raw.get("mode")).strip() != resolved_mode:
            continue
        if resolved_intervention_id and _safe_str(raw.get("id")).strip() == resolved_intervention_id:
            return idx, raw
        if resolved_request_id and _safe_str(raw.get("request_id")).strip() == resolved_request_id:
            return idx, raw
        current_approval_id = _safe_str(raw.get("approval_id")).strip()
        previous_approval_id = _safe_str(raw.get("previous_approval_id")).strip()
        if resolved_approval_id and resolved_approval_id in {current_approval_id, previous_approval_id}:
            return idx, raw

    return -1, None


@router.get("/status")
def status() -> dict[str, object]:
    try:
        registry = _load_registry()
        return {
            "ok": True,
            "route": "industrial",
            "status": "ready",
            "ts": _now_s(),
            "counts": {
                "assets": len(registry.get("assets") or {}),
                "processes": len(registry.get("processes") or {}),
                "simulations": len(registry.get("simulations") or {}),
                "runs": len(registry.get("runs") or {}),
                "safety_validations": len(registry.get("safety_validations") or {}),
                "telemetry": len(registry.get("telemetry") or []),
            },
        }
    except Exception:
        return {"ok": False, "route": "industrial", "status": "error"}


@router.get("/health")
def health() -> dict[str, object]:
    body = status()
    body["route"] = "industrial.health"
    return body


@router.get("/assets")
def list_assets(
    limit: int = 200,
    offset: int = 0,
    cursor: str | None = None,
    search: str | None = None,
    status: str | None = None,
    risk: str | None = None,
    include_archived: bool = False,
    asset_type: str | None = None,
    tags: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        registry = _load_registry()
        items = _list_section(registry, "assets", _normalize_asset)
        items = _apply_filters(
            items,
            status=_safe_str(status).strip().lower(),
            risk=_safe_str(risk).strip().lower(),
            search=_safe_str(search).strip().lower(),
            tags=tags or [],
            include_archived=include_archived,
            extra={"asset_type": _safe_str(asset_type).strip().lower()},
        )
        items.sort(key=lambda item: (int(item.get("updated_ts") or 0), _safe_str(item.get("id"))), reverse=True)
        page, total, safe_limit, safe_offset, next_cursor = _paginate(items, limit, offset, cursor)
        return {"items": page, "total": total, "limit": safe_limit, "offset": safe_offset, "next_cursor": next_cursor}
    except Exception as exc:
        return {"items": [], "total": 0, "limit": 0, "offset": 0, "error": str(exc)}


@router.get("/assets/{asset_id}")
def get_asset(asset_id: str) -> dict[str, object]:
    try:
        entity_id = _validate_id(asset_id, "asset id")
        registry = _load_registry()
        raw = _read_section(registry, "assets", entity_id)
        if raw is None:
            return {"ok": False, "error": "not_found"}
        return {"ok": True, "item": _normalize_asset(entity_id, raw)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/assets")
def create_asset(payload: dict[str, Any]) -> dict[str, object]:
    try:
        name = _safe_str(payload.get("name")).strip()
        if not name:
            return {"ok": False, "error": "name_required"}
        entity_id = _safe_str(payload.get("id")).strip() or _new_id("asset", name)
        entity_id = _validate_id(entity_id, "asset id")
        registry = _load_registry()
        if _read_section(registry, "assets", entity_id) is not None:
            return {"ok": False, "error": "already_exists", "id": entity_id}
        now_s = _now_s()
        item = _normalize_asset(
            entity_id,
            {
                "id": entity_id,
                "name": name,
                "asset_type": payload.get("asset_type"),
                "status": payload.get("status"),
                "risk": payload.get("risk"),
                "location": payload.get("location"),
                "tags": payload.get("tags"),
                "created_ts": now_s,
                "updated_ts": now_s,
                "model_ref": payload.get("model_ref"),
                "connector_ref": payload.get("connector_ref"),
                "meta": payload.get("meta"),
            },
        )
        _write_section(registry, "assets", entity_id, item)
        _save_registry(registry)
        return {"ok": True, "id": entity_id, "item": item}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.patch("/assets/{asset_id}")
def update_asset(asset_id: str, payload: dict[str, Any]) -> dict[str, object]:
    try:
        entity_id = _validate_id(asset_id, "asset id")
        registry = _load_registry()
        current = _read_section(registry, "assets", entity_id)
        if current is None:
            return {"ok": False, "error": "not_found", "id": entity_id}
        item = _normalize_asset(entity_id, current)
        for key in ("name", "asset_type", "status", "risk", "location", "model_ref", "connector_ref"):
            if key in payload and payload[key] is not None:
                item[key] = _safe_str(payload[key]).strip()
        if "tags" in payload:
            item["tags"] = _parse_list(payload.get("tags"))
        if "last_seen_ts" in payload:
            item["last_seen_ts"] = int(payload.get("last_seen_ts") or 0)
        if isinstance(payload.get("meta"), dict):
            merged = dict(item.get("meta") or {})
            merged.update(payload["meta"])
            item["meta"] = merged
        item["updated_ts"] = _now_s()
        _write_section(registry, "assets", entity_id, _normalize_asset(entity_id, item))
        _save_registry(registry)
        return {"ok": True, "id": entity_id, "item": item}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.delete("/assets/{asset_id}")
def delete_asset(asset_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    try:
        entity_id = _validate_id(asset_id, "asset id")
        registry = _load_registry()
        removed = _delete_section(registry, "assets", entity_id)
        if not removed:
            return {"ok": False, "error": "not_found", "id": entity_id}
        _save_registry(registry)
        return {
            "ok": True,
            "id": entity_id,
            "status": "deleted",
            "reason": _safe_str((payload or {}).get("reason")).strip(),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/processes")
def list_processes(
    limit: int = 200,
    offset: int = 0,
    cursor: str | None = None,
    search: str | None = None,
    status: str | None = None,
    risk: str | None = None,
    include_archived: bool = False,
    tags: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        registry = _load_registry()
        items = _list_section(registry, "processes", _normalize_process)
        items = _apply_filters(
            items,
            status=_safe_str(status).strip().lower(),
            risk=_safe_str(risk).strip().lower(),
            search=_safe_str(search).strip().lower(),
            tags=tags or [],
            include_archived=include_archived,
        )
        items.sort(key=lambda item: (int(item.get("updated_ts") or 0), _safe_str(item.get("id"))), reverse=True)
        page, total, safe_limit, safe_offset, next_cursor = _paginate(items, limit, offset, cursor)
        return {"items": page, "total": total, "limit": safe_limit, "offset": safe_offset, "next_cursor": next_cursor}
    except Exception as exc:
        return {"items": [], "total": 0, "limit": 0, "offset": 0, "error": str(exc)}


@router.get("/processes/{process_id}")
def get_process(process_id: str) -> dict[str, object]:
    try:
        entity_id = _validate_id(process_id, "process id")
        registry = _load_registry()
        raw = _read_section(registry, "processes", entity_id)
        if raw is None:
            return {"ok": False, "error": "not_found"}
        return {"ok": True, "item": _normalize_process(entity_id, raw)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/processes")
def create_process(payload: dict[str, Any]) -> dict[str, object]:
    try:
        name = _safe_str(payload.get("name")).strip()
        if not name:
            return {"ok": False, "error": "name_required"}
        entity_id = _safe_str(payload.get("id")).strip() or _new_id("process", name)
        entity_id = _validate_id(entity_id, "process id")
        registry = _load_registry()
        if _read_section(registry, "processes", entity_id) is not None:
            return {"ok": False, "error": "already_exists", "id": entity_id}
        now_s = _now_s()
        item = _normalize_process(
            entity_id,
            {
                "id": entity_id,
                "name": name,
                "status": payload.get("status"),
                "risk": payload.get("risk"),
                "description": payload.get("description"),
                "domain": payload.get("domain"),
                "tags": payload.get("tags"),
                "inputs": payload.get("inputs"),
                "outputs": payload.get("outputs"),
                "created_ts": now_s,
                "updated_ts": now_s,
                "meta": payload.get("meta"),
            },
        )
        _write_section(registry, "processes", entity_id, item)
        _save_registry(registry)
        return {"ok": True, "id": entity_id, "item": item}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.patch("/processes/{process_id}")
def update_process(process_id: str, payload: dict[str, Any]) -> dict[str, object]:
    try:
        entity_id = _validate_id(process_id, "process id")
        registry = _load_registry()
        current = _read_section(registry, "processes", entity_id)
        if current is None:
            return {"ok": False, "error": "not_found", "id": entity_id}
        item = _normalize_process(entity_id, current)
        for key in ("name", "status", "risk", "description", "domain"):
            if key in payload and payload[key] is not None:
                item[key] = _safe_str(payload[key]).strip()
        for key in ("tags", "inputs", "outputs"):
            if key in payload:
                item[key] = _parse_list(payload.get(key))
        if isinstance(payload.get("meta"), dict):
            merged = dict(item.get("meta") or {})
            merged.update(payload["meta"])
            item["meta"] = merged
        item["updated_ts"] = _now_s()
        _write_section(registry, "processes", entity_id, _normalize_process(entity_id, item))
        _save_registry(registry)
        return {"ok": True, "id": entity_id, "item": item}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.delete("/processes/{process_id}")
def delete_process(process_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    try:
        entity_id = _validate_id(process_id, "process id")
        registry = _load_registry()
        removed = _delete_section(registry, "processes", entity_id)
        if not removed:
            return {"ok": False, "error": "not_found", "id": entity_id}
        _save_registry(registry)
        return {
            "ok": True,
            "id": entity_id,
            "status": "deleted",
            "reason": _safe_str((payload or {}).get("reason")).strip(),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/simulations")
def list_simulations(
    limit: int = 200,
    offset: int = 0,
    cursor: str | None = None,
    search: str | None = None,
    status: str | None = None,
    risk: str | None = None,
    include_archived: bool = False,
    engine: str | None = None,
    asset_id: str | None = None,
    process_id: str | None = None,
    digital_twin_id: str | None = None,
    tags: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        registry = _load_registry()
        items = _list_section(registry, "simulations", _normalize_simulation)
        items = _apply_filters(
            items,
            status=_safe_str(status).strip().lower(),
            risk=_safe_str(risk).strip().lower(),
            search=_safe_str(search).strip().lower(),
            tags=tags or [],
            include_archived=include_archived,
            extra={
                "engine": _safe_str(engine).strip().lower(),
                "asset_id": _safe_str(asset_id).strip().lower(),
                "process_id": _safe_str(process_id).strip().lower(),
                "digital_twin_id": _safe_str(digital_twin_id).strip().lower(),
            },
        )
        items.sort(key=lambda item: (int(item.get("updated_ts") or 0), _safe_str(item.get("id"))), reverse=True)
        page, total, safe_limit, safe_offset, next_cursor = _paginate(items, limit, offset, cursor)
        return {"items": page, "total": total, "limit": safe_limit, "offset": safe_offset, "next_cursor": next_cursor}
    except Exception as exc:
        return {"items": [], "total": 0, "limit": 0, "offset": 0, "error": str(exc)}


@router.get("/simulations/{simulation_id}")
def get_simulation(simulation_id: str) -> dict[str, object]:
    try:
        entity_id = _validate_id(simulation_id, "simulation id")
        registry = _load_registry()
        raw = _read_section(registry, "simulations", entity_id)
        if raw is None:
            return {"ok": False, "error": "not_found"}
        return {"ok": True, "item": _normalize_simulation(entity_id, raw)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/simulations")
def create_simulation(payload: dict[str, Any]) -> dict[str, object]:
    try:
        name = _safe_str(payload.get("name")).strip()
        if not name:
            return {"ok": False, "error": "name_required"}
        entity_id = _safe_str(payload.get("id")).strip() or _new_id("sim", name)
        entity_id = _validate_id(entity_id, "simulation id")
        registry = _load_registry()
        if _read_section(registry, "simulations", entity_id) is not None:
            return {"ok": False, "error": "already_exists", "id": entity_id}
        now_s = _now_s()
        item = _normalize_simulation(
            entity_id,
            {
                "id": entity_id,
                "name": name,
                "status": payload.get("status"),
                "risk": payload.get("risk"),
                "description": payload.get("description"),
                "engine": payload.get("engine"),
                "scenario": payload.get("scenario"),
                "default_params": payload.get("default_params"),
                "asset_id": payload.get("asset_id"),
                "process_id": payload.get("process_id"),
                "digital_twin_id": payload.get("digital_twin_id"),
                "tags": payload.get("tags"),
                "created_ts": now_s,
                "updated_ts": now_s,
                "meta": payload.get("meta"),
            },
        )
        _write_section(registry, "simulations", entity_id, item)
        _save_registry(registry)
        return {"ok": True, "id": entity_id, "item": item}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.patch("/simulations/{simulation_id}")
def update_simulation(simulation_id: str, payload: dict[str, Any]) -> dict[str, object]:
    try:
        entity_id = _validate_id(simulation_id, "simulation id")
        registry = _load_registry()
        current = _read_section(registry, "simulations", entity_id)
        if current is None:
            return {"ok": False, "error": "not_found", "id": entity_id}
        item = _normalize_simulation(entity_id, current)
        for key in (
            "name",
            "status",
            "risk",
            "description",
            "engine",
            "scenario",
            "asset_id",
            "process_id",
            "digital_twin_id",
        ):
            if key in payload and payload[key] is not None:
                item[key] = _safe_str(payload[key]).strip()
        if "tags" in payload:
            item["tags"] = _parse_list(payload.get("tags"))
        if "default_params" in payload:
            item["default_params"] = _normalize_meta(payload.get("default_params"))
        if isinstance(payload.get("meta"), dict):
            merged = dict(item.get("meta") or {})
            merged.update(payload["meta"])
            item["meta"] = merged
        item["updated_ts"] = _now_s()
        _write_section(registry, "simulations", entity_id, _normalize_simulation(entity_id, item))
        _save_registry(registry)
        return {"ok": True, "id": entity_id, "item": item}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.delete("/simulations/{simulation_id}")
def delete_simulation(simulation_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    try:
        entity_id = _validate_id(simulation_id, "simulation id")
        registry = _load_registry()
        removed = _delete_section(registry, "simulations", entity_id)
        if not removed:
            return {"ok": False, "error": "not_found", "id": entity_id}
        _save_registry(registry)
        return {
            "ok": True,
            "id": entity_id,
            "status": "deleted",
            "reason": _safe_str((payload or {}).get("reason")).strip(),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/runs")
def list_runs(
    limit: int = 200,
    offset: int = 0,
    cursor: str | None = None,
    search: str | None = None,
    status: str | None = None,
    include_archived: bool = False,
    simulation_id: str | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
) -> dict[str, object]:
    try:
        registry = _load_registry()
        items = _list_section(registry, "runs", _normalize_run)
        items = _apply_filters(
            items,
            status=_safe_str(status).strip().lower(),
            search=_safe_str(search).strip().lower(),
            include_archived=include_archived,
            extra={"simulation_id": _safe_str(simulation_id).strip().lower()},
            start_ts=start_ts,
            end_ts=end_ts,
            time_key="requested_ts",
        )
        items.sort(key=lambda item: (int(item.get("requested_ts") or 0), _safe_str(item.get("id"))), reverse=True)
        page, total, safe_limit, safe_offset, next_cursor = _paginate(items, limit, offset, cursor)
        return {"items": page, "total": total, "limit": safe_limit, "offset": safe_offset, "next_cursor": next_cursor}
    except Exception as exc:
        return {"items": [], "total": 0, "limit": 0, "offset": 0, "error": str(exc)}


@router.get("/runs/export")
def export_runs(
    format: str = "json",
    simulation_id: str | None = None,
    status: str | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
) -> Response:
    registry = _load_registry()
    items = _list_section(registry, "runs", _normalize_run)
    items = _apply_filters(
        items,
        status=_safe_str(status).strip().lower(),
        include_archived=True,
        extra={"simulation_id": _safe_str(simulation_id).strip().lower()},
        start_ts=start_ts,
        end_ts=end_ts,
        time_key="requested_ts",
    )
    items.sort(key=lambda item: (int(item.get("requested_ts") or 0), _safe_str(item.get("id"))), reverse=True)

    kind = _safe_str(format).strip().lower()
    if kind == "csv":
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(
            [
                "id",
                "simulation_id",
                "status",
                "requested_ts",
                "started_ts",
                "completed_ts",
                "requested_by",
                "reason",
                "summary",
            ]
        )
        for item in items:
            writer.writerow(
                [
                    _safe_str(item.get("id")),
                    _safe_str(item.get("simulation_id")),
                    _safe_str(item.get("status")),
                    int(item.get("requested_ts") or 0),
                    int(item.get("started_ts") or 0),
                    int(item.get("completed_ts") or 0),
                    _safe_str(item.get("requested_by")),
                    _safe_str(item.get("reason")),
                    _safe_str(item.get("summary")),
                ]
            )
        return Response(content=out.getvalue(), media_type="text/csv")

    return Response(
        content=json.dumps({"items": items, "total": len(items)}, ensure_ascii=False), media_type="application/json"
    )


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, object]:
    try:
        entity_id = _validate_id(run_id, "run id")
        registry = _load_registry()
        raw = _read_section(registry, "runs", entity_id)
        if raw is None:
            return {"ok": False, "error": "not_found"}
        return {"ok": True, "item": _normalize_run(entity_id, raw)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/runs/start")
def start_run(payload: dict[str, Any]) -> dict[str, object]:
    try:
        simulation_id = _validate_id(_safe_str(payload.get("simulation_id")).strip(), "simulation id")
        registry = _load_registry()
        if _read_section(registry, "simulations", simulation_id) is None:
            return {"ok": False, "error": "simulation_not_found", "simulation_id": simulation_id}

        dry_run = bool(payload.get("dry_run", False))
        now_s = _now_s()
        run_id = _new_id("run", simulation_id)
        run = _normalize_run(
            run_id,
            {
                "id": run_id,
                "simulation_id": simulation_id,
                "status": "succeeded" if dry_run else "running",
                "requested_ts": now_s,
                "started_ts": now_s,
                "completed_ts": now_s if dry_run else 0,
                "requested_by": _safe_str(payload.get("requested_by")).strip() or "industrial_api",
                "reason": _safe_str(payload.get("reason")).strip() or "requested",
                "params": _normalize_meta(payload.get("params")),
                "metrics": {"dry_run": 1.0 if dry_run else 0.0},
                "summary": "Dry-run completed without external actuation." if dry_run else "Run started.",
                "artifacts": [
                    {
                        "id": _new_id("artifact", run_id),
                        "kind": "run_report",
                        "path": f"data/artifacts/simulations/{run_id}.json",
                    }
                ],
                "meta": {"created_at": _now_iso(), "dry_run": dry_run},
            },
        )
        _write_section(registry, "runs", run_id, run)
        _append_telemetry(
            registry,
            simulation_id,
            {"run_status": run.get("status"), "dry_run": dry_run},
            {"event": "runs.start", "run_id": run_id},
        )
        _save_registry(registry)
        return {"ok": True, "id": run_id, "run": run, "status": run.get("status")}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str, payload: dict[str, Any]) -> dict[str, object]:
    try:
        entity_id = _validate_id(run_id, "run id")
        registry = _load_registry()
        raw = _read_section(registry, "runs", entity_id)
        if raw is None:
            return {"ok": False, "error": "not_found", "id": entity_id}
        run = _normalize_run(entity_id, raw)
        if _safe_str(run.get("status")).strip().lower() not in {"succeeded", "failed", "canceled"}:
            run["status"] = "canceled"
            run["completed_ts"] = _now_s()
            run["summary"] = _safe_str(payload.get("reason")).strip() or "Run canceled."
        meta = dict(run.get("meta") or {})
        meta["cancel_reason"] = _safe_str(payload.get("reason")).strip() or "requested"
        run["meta"] = meta
        _write_section(registry, "runs", entity_id, run)
        _append_telemetry(
            registry,
            _safe_str(run.get("simulation_id")).strip(),
            {"run_status": run.get("status"), "canceled": True},
            {"event": "runs.cancel", "run_id": entity_id},
        )
        _save_registry(registry)
        return {"ok": True, "id": entity_id, "status": run.get("status")}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/safety/validations")
def list_safety_validations(
    limit: int = 200,
    offset: int = 0,
    cursor: str | None = None,
    status: str | None = None,
    target_kind: str | None = None,
    target_id: str | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
) -> dict[str, object]:
    try:
        registry = _load_registry()
        items = _list_section(registry, "safety_validations", _normalize_validation)
        items = _apply_filters(
            items,
            status=_safe_str(status).strip().lower(),
            include_archived=True,
            extra={
                "target_kind": _safe_str(target_kind).strip().lower(),
                "target_id": _safe_str(target_id).strip().lower(),
            },
            start_ts=start_ts,
            end_ts=end_ts,
            time_key="ts",
        )
        items.sort(key=lambda item: (int(item.get("ts") or 0), _safe_str(item.get("id"))), reverse=True)
        page, total, safe_limit, safe_offset, next_cursor = _paginate(items, limit, offset, cursor)
        return {"items": page, "total": total, "limit": safe_limit, "offset": safe_offset, "next_cursor": next_cursor}
    except Exception as exc:
        return {"items": [], "total": 0, "limit": 0, "offset": 0, "error": str(exc)}


@router.post("/safety/validate")
def validate_safety(payload: dict[str, Any]) -> dict[str, object]:
    try:
        target_kind = _safe_str(payload.get("target_kind")).strip().lower()
        target_id = _validate_id(_safe_str(payload.get("target_id")).strip(), "target id")
        if not target_kind:
            return {"ok": False, "error": "target_kind_required"}

        reason = _safe_str(payload.get("reason")).strip() or "requested"
        params = _normalize_approval_value(_normalize_meta(payload.get("params")))
        runtime_params = _redacted_runtime_params(payload.get("params"))
        dry_run = bool(payload.get("dry_run", True))
        risk = _safe_str(params.get("risk")).strip().lower() or "medium"
        registry = _load_registry()
        approval_action = "industrial.safety.validate"
        supplied_approval_id = _approval_id_from_payload(payload)
        supplied_validation_id = _safe_str(payload.get("validation_id")).strip()
        matched_validation_id, matched_validation_raw = _find_validation_record(
            registry,
            validation_id=supplied_validation_id,
            approval_id=supplied_approval_id,
        )
        validation_id = (
            matched_validation_id or supplied_validation_id or _new_id("validation", f"{target_kind}_{target_id}")
        )
        matched_validation = (
            _normalize_validation(validation_id, matched_validation_raw)
            if isinstance(matched_validation_raw, dict)
            else None
        )
        matched_meta = (
            matched_validation.get("meta")
            if isinstance(matched_validation, dict) and isinstance(matched_validation.get("meta"), dict)
            else {}
        )
        status = "warn" if dry_run else "pass"
        summary = "Dry-run safety validation completed." if dry_run else "Safety validation passed."
        violations: list[dict[str, Any]] = []
        approval_id = supplied_approval_id
        request_id = _safe_str(payload.get("request_id")).strip() or _safe_str(matched_meta.get("request_id")).strip()
        if not request_id:
            request_id = _new_id("safety_req", target_id)

        request_payload = {
            "request_id": request_id,
            "validation_id": validation_id,
            "target_kind": target_kind,
            "target_id": target_id,
            "risk": risk,
            "reason": reason,
            "dry_run": dry_run,
            "params": params,
        }

        if risk in {"high", "safety_critical"} and not dry_run:
            status = "warn"
            summary = "High-risk validation requires approval."
            violations.append(
                {
                    "code": "HIGH_RISK_APPROVAL_REQUIRED",
                    "message": "Approval required for high-risk validation.",
                    "severity": "warning",
                }
            )

            if not approval_id:
                approval_id, _ = _request_exact_approval(
                    action=approval_action,
                    reason=reason,
                    request_payload=request_payload,
                )
            else:
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
                    validation = _normalize_validation(
                        validation_id,
                        {
                            "id": validation_id,
                            "ts": _now_s(),
                            "target_kind": target_kind,
                            "target_id": target_id,
                            "status": status,
                            "risk": risk,
                            "summary": summary,
                            "violations": violations,
                            "meta": {
                                "reason": reason,
                                "params": runtime_params,
                                "dry_run": dry_run,
                                "request_id": request_id,
                                "approval_id": refreshed_id,
                                "previous_approval_id": approval_id,
                            },
                        },
                    )
                    _write_section(registry, "safety_validations", validation_id, validation)
                    _append_telemetry(
                        registry,
                        target_id,
                        {
                            "safety_status": validation.get("status"),
                            "violation_count": len(validation.get("violations") or []),
                        },
                        {"event": "safety.validate", "validation_id": validation_id},
                    )
                    _save_registry(registry)
                    return {
                        "ok": False,
                        "id": validation_id,
                        "validation": validation,
                        "status": "needs_approval",
                        "error": "approval_not_found",
                        "approval_id": refreshed_id,
                        "previous_approval_id": approval_id,
                        "request_id": request_id,
                        "artifact_dir": str(art),
                        "message": "Approval was missing for this safety validation; a fresh exact-action approval is required.",
                    }
                if approval_status == "pending":
                    validation = _normalize_validation(
                        validation_id,
                        {
                            "id": validation_id,
                            "ts": _now_s(),
                            "target_kind": target_kind,
                            "target_id": target_id,
                            "status": status,
                            "risk": risk,
                            "summary": summary,
                            "violations": violations,
                            "meta": {
                                "reason": reason,
                                "params": runtime_params,
                                "dry_run": dry_run,
                                "request_id": request_id,
                                "approval_id": approval_id,
                                "previous_approval_id": _safe_str(matched_meta.get("previous_approval_id")).strip(),
                            },
                        },
                    )
                    _write_section(registry, "safety_validations", validation_id, validation)
                    _append_telemetry(
                        registry,
                        target_id,
                        {
                            "safety_status": validation.get("status"),
                            "violation_count": len(validation.get("violations") or []),
                        },
                        {"event": "safety.validate", "validation_id": validation_id},
                    )
                    _save_registry(registry)
                    return {
                        "ok": False,
                        "id": validation_id,
                        "validation": validation,
                        "status": "needs_approval",
                        "approval_id": approval_id,
                        "request_id": request_id,
                        "message": "Safety validation request is awaiting approval.",
                    }
                if approval_status in {"rejected", "emergency"}:
                    return {
                        "ok": False,
                        "id": validation_id,
                        "status": "denied",
                        "error": "approval_denied",
                        "approval_id": approval_id,
                        "request_id": request_id,
                        "message": "Approval was denied for this safety validation.",
                        "meta": {"approval_status": approval_status},
                    }
                if approval_status != "approved":
                    return {
                        "ok": False,
                        "id": validation_id,
                        "status": "needs_approval",
                        "error": "approval_not_found",
                        "approval_id": approval_id,
                        "request_id": request_id,
                        "message": "A matching approved request was not found for this safety validation.",
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
                        "kind": "industrial.safety.validate.mismatch",
                        "approval_id": refreshed_id,
                        "previous_approval_id": approval_id,
                        "validation_id": validation_id,
                        "request": request_payload,
                        "approval_record": approval_record,
                    }
                    _atomic_write(art / "mismatch.json", mismatch_body)
                    _atomic_write(_approval_artifact_dir(approval_id) / "mismatch.json", mismatch_body)
                    validation = _normalize_validation(
                        validation_id,
                        {
                            "id": validation_id,
                            "ts": _now_s(),
                            "target_kind": target_kind,
                            "target_id": target_id,
                            "status": status,
                            "risk": risk,
                            "summary": summary,
                            "violations": violations,
                            "meta": {
                                "reason": reason,
                                "params": runtime_params,
                                "dry_run": dry_run,
                                "request_id": request_id,
                                "approval_id": refreshed_id,
                                "previous_approval_id": approval_id,
                            },
                        },
                    )
                    _write_section(registry, "safety_validations", validation_id, validation)
                    _append_telemetry(
                        registry,
                        target_id,
                        {
                            "safety_status": validation.get("status"),
                            "violation_count": len(validation.get("violations") or []),
                        },
                        {"event": "safety.validate", "validation_id": validation_id},
                    )
                    _save_registry(registry)
                    return {
                        "ok": False,
                        "id": validation_id,
                        "validation": validation,
                        "status": "needs_approval",
                        "error": "approval_payload_mismatch",
                        "approval_id": refreshed_id,
                        "previous_approval_id": approval_id,
                        "request_id": request_id,
                        "artifact_dir": str(art),
                        "message": "Approval does not match this exact safety validation request.",
                    }

                status = "pass"
                summary = "Safety validation passed."
                violations = []

        validation = _normalize_validation(
            validation_id,
            {
                "id": validation_id,
                "ts": _now_s(),
                "target_kind": target_kind,
                "target_id": target_id,
                "status": status,
                "risk": risk,
                "summary": summary,
                "violations": violations,
                "meta": {
                    "reason": reason,
                    "params": runtime_params,
                    "dry_run": dry_run,
                    "request_id": request_id,
                    "approval_id": approval_id,
                    "previous_approval_id": _safe_str(matched_meta.get("previous_approval_id")).strip(),
                },
            },
        )

        _write_section(registry, "safety_validations", validation_id, validation)
        _append_telemetry(
            registry,
            target_id,
            {"safety_status": validation.get("status"), "violation_count": len(validation.get("violations") or [])},
            {"event": "safety.validate", "validation_id": validation_id},
        )
        _save_registry(registry)
        return {
            "ok": True,
            "id": validation_id,
            "validation": validation,
            "status": validation.get("status"),
            "approval_id": approval_id,
            "request_id": request_id,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/telemetry")
def query_telemetry(
    source_id: str | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
    limit: int = 200,
    metric_keys: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        registry = _load_registry()
        telemetry = registry.get("telemetry")
        if not isinstance(telemetry, list):
            telemetry = []
        source = _safe_str(source_id).strip()
        keys = [key for key in (metric_keys or []) if key]

        items: list[dict[str, Any]] = []
        for raw in telemetry:
            if not isinstance(raw, dict):
                continue
            point = _normalize_telemetry(raw)
            if point is None:
                continue
            ts = int(point.get("ts") or 0)
            if source and _safe_str(point.get("source_id")).strip() != source:
                continue
            if start_ts is not None and ts < int(start_ts):
                continue
            if end_ts is not None and ts > int(end_ts):
                continue
            if keys:
                fields = point.get("fields")
                if isinstance(fields, dict):
                    point["fields"] = {k: v for k, v in fields.items() if k in keys}
            items.append(point)
        items.sort(key=lambda item: int(item.get("ts") or 0), reverse=True)
        safe_limit = max(1, min(int(limit), 5000))
        page = items[:safe_limit]
        next_cursor = str(safe_limit) if safe_limit < len(items) else None
        return {"items": page, "total": len(items), "limit": safe_limit, "next_cursor": next_cursor}
    except Exception as exc:
        return {"items": [], "total": 0, "error": str(exc)}


@router.post("/interventions/request")
def request_intervention(payload: dict[str, Any]) -> dict[str, object]:
    try:
        target_kind = _safe_str(payload.get("target_kind")).strip().lower()
        target_id = _validate_id(_safe_str(payload.get("target_id")).strip(), "target id")
        action = _safe_str(payload.get("action")).strip()
        if not target_kind:
            return {"ok": False, "error": "target_kind_required"}
        if not action:
            return {"ok": False, "error": "action_required"}
        reason = _safe_str(payload.get("reason")).strip() or "requested"
        dry_run = bool(payload.get("dry_run", True))
        risk = _safe_str(payload.get("risk")).strip()
        domain = _safe_str(payload.get("domain")).strip()
        actor = _safe_str(payload.get("actor")).strip()
        params = _normalize_approval_value(_normalize_meta(payload.get("params")))
        runtime_params = _redacted_runtime_params(payload.get("params"))
        meta = redact_governed_metadata(payload.get("meta"))
        approval_action = "industrial.intervention.request"
        approval_id = _approval_id_from_payload(payload)
        request_id = _safe_str(payload.get("request_id")).strip() or _new_id("ireq", f"{target_kind}_{target_id}")
        request_payload = _approval_request_payload(
            approval_action,
            {
                "target_kind": target_kind,
                "target_id": target_id,
                "action": action,
                "dry_run": dry_run,
                "risk": risk,
                "params": params,
                "domain": domain,
                "actor": actor,
                "meta": _approval_meta(meta),
            },
        )

        registry = _load_registry()
        interventions = registry.get("interventions")
        if not isinstance(interventions, list):
            interventions = []
            registry["interventions"] = interventions
        intervention_id = _new_id("intervention", target_id)
        record_idx, request_record = _find_intervention_record(
            registry,
            request_id=request_id,
            approval_id=approval_id,
            mode="request",
        )
        if isinstance(request_record, dict):
            intervention_id = _safe_str(request_record.get("id")).strip() or intervention_id
            request_id = _safe_str(request_record.get("request_id")).strip() or request_id

        if not approval_id:
            approval_id, art = _request_exact_approval(
                action=approval_action,
                reason=reason,
                request_payload=request_payload,
            )
            intervention = {
                "id": intervention_id,
                "ts": _now_s(),
                "mode": "request",
                "target_kind": target_kind,
                "target_id": target_id,
                "action": action,
                "status": "pending",
                "reason": reason,
                "dry_run": dry_run,
                "risk": risk,
                "domain": domain,
                "actor": actor,
                "request_id": request_id,
                "approval_id": approval_id,
                "previous_approval_id": "",
                "params": runtime_params,
                "meta": meta,
            }
            if record_idx >= 0:
                interventions[record_idx] = intervention
            else:
                interventions.append(intervention)
            _append_telemetry(registry, target_id, {"intervention_requested": True}, {"event": "interventions.request"})
            _save_registry(registry)
            return {
                "ok": True,
                "status": "pending",
                "request_id": request_id,
                "approval_id": approval_id,
                "previous_approval_id": "",
                "intervention_id": intervention_id,
                "artifact_dir": str(art),
                "message": "Intervention request submitted for approval.",
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
            intervention = {
                "id": intervention_id,
                "ts": _now_s(),
                "mode": "request",
                "target_kind": target_kind,
                "target_id": target_id,
                "action": action,
                "status": "pending",
                "reason": reason,
                "dry_run": dry_run,
                "risk": risk,
                "domain": domain,
                "actor": actor,
                "request_id": request_id,
                "approval_id": refreshed_id,
                "previous_approval_id": approval_id,
                "params": runtime_params,
                "meta": meta,
            }
            if record_idx >= 0:
                interventions[record_idx] = intervention
            else:
                interventions.append(intervention)
            _atomic_write(
                art / "error.json",
                {
                    "kind": "industrial.intervention.request.error",
                    "approval_id": refreshed_id,
                    "previous_approval_id": approval_id,
                    "status": approval_status,
                    "request": request_payload,
                    "intervention_id": intervention_id,
                    "request_id": request_id,
                },
            )
            _append_telemetry(registry, target_id, {"intervention_requested": True}, {"event": "interventions.request"})
            _save_registry(registry)
            return {
                "ok": False,
                "status": "needs_approval",
                "error": "approval_not_found",
                "request_id": request_id,
                "approval_id": refreshed_id,
                "previous_approval_id": approval_id,
                "intervention_id": intervention_id,
                "artifact_dir": str(art),
                "message": "Approval was missing for this intervention request; a fresh exact-action approval is required.",
            }
        if approval_status == "pending":
            return {
                "ok": True,
                "status": "pending",
                "request_id": request_id,
                "approval_id": approval_id,
                "previous_approval_id": _safe_str(request_record.get("previous_approval_id")).strip()
                if isinstance(request_record, dict)
                else "",
                "intervention_id": intervention_id,
                "message": "Intervention request is awaiting approval.",
            }
        if approval_status in {"rejected", "emergency"}:
            return {
                "ok": False,
                "status": "denied",
                "error": "approval_denied",
                "request_id": request_id,
                "approval_id": approval_id,
                "intervention_id": intervention_id,
                "message": "Approval was denied for this intervention request.",
                "meta": {"approval_status": approval_status},
            }
        if approval_status != "approved":
            return {
                "ok": False,
                "status": "needs_approval",
                "error": "approval_not_found",
                "request_id": request_id,
                "approval_id": approval_id,
                "intervention_id": intervention_id,
                "message": "A matching approved request was not found for this intervention request.",
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
                "kind": "industrial.intervention.request.mismatch",
                "approval_id": refreshed_id,
                "previous_approval_id": approval_id,
                "intervention_id": intervention_id,
                "request_id": request_id,
                "request": request_payload,
                "approval_record": approval_record,
            }
            _atomic_write(art / "mismatch.json", mismatch_body)
            _atomic_write(_approval_artifact_dir(approval_id) / "mismatch.json", mismatch_body)
            intervention = {
                "id": intervention_id,
                "ts": _now_s(),
                "mode": "request",
                "target_kind": target_kind,
                "target_id": target_id,
                "action": action,
                "status": "pending",
                "reason": reason,
                "dry_run": dry_run,
                "risk": risk,
                "domain": domain,
                "actor": actor,
                "request_id": request_id,
                "approval_id": refreshed_id,
                "previous_approval_id": approval_id,
                "params": runtime_params,
                "meta": meta,
            }
            if record_idx >= 0:
                interventions[record_idx] = intervention
            else:
                interventions.append(intervention)
            _append_telemetry(registry, target_id, {"intervention_requested": True}, {"event": "interventions.request"})
            _save_registry(registry)
            return {
                "ok": False,
                "status": "needs_approval",
                "error": "approval_payload_mismatch",
                "request_id": request_id,
                "approval_id": refreshed_id,
                "previous_approval_id": approval_id,
                "intervention_id": intervention_id,
                "artifact_dir": str(art),
                "message": "Approval does not match this exact intervention request.",
            }

        intervention = {
            "id": intervention_id,
            "ts": _now_s(),
            "mode": "request",
            "target_kind": target_kind,
            "target_id": target_id,
            "action": action,
            "status": "approved",
            "reason": reason,
            "dry_run": dry_run,
            "risk": risk,
            "domain": domain,
            "actor": actor,
            "request_id": request_id,
            "approval_id": approval_id,
            "previous_approval_id": _safe_str(request_record.get("previous_approval_id")).strip()
            if isinstance(request_record, dict)
            else "",
            "params": runtime_params,
            "meta": meta,
        }
        if record_idx >= 0:
            interventions[record_idx] = intervention
        else:
            interventions.append(intervention)
        _append_telemetry(registry, target_id, {"intervention_requested": True}, {"event": "interventions.request"})
        _save_registry(registry)
        return {
            "ok": True,
            "status": intervention["status"],
            "request_id": request_id,
            "approval_id": approval_id,
            "previous_approval_id": _safe_str(intervention.get("previous_approval_id")).strip(),
            "intervention_id": intervention_id,
            "message": "Intervention request approved.",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/interventions/execute")
def execute_intervention(payload: dict[str, Any]) -> dict[str, object]:
    try:
        target_kind = _safe_str(payload.get("target_kind")).strip().lower()
        target_id = _validate_id(_safe_str(payload.get("target_id")).strip(), "target id")
        action = _safe_str(payload.get("action")).strip()
        if not target_kind:
            return {"ok": False, "error": "target_kind_required"}
        if not action:
            return {"ok": False, "error": "action_required"}

        risk = _safe_str(payload.get("risk")).strip().lower()
        dry_run = bool(payload.get("dry_run", False))
        reason = _safe_str(payload.get("reason")).strip() or "requested"
        domain = _safe_str(payload.get("domain")).strip()
        actor = _safe_str(payload.get("actor")).strip()
        params = _normalize_approval_value(_normalize_meta(payload.get("params")))
        runtime_params = _redacted_runtime_params(payload.get("params"))
        meta = redact_governed_metadata(payload.get("meta"))
        request_id = _new_id("iexec", f"{target_kind}_{target_id}")
        approval_action = "industrial.intervention.execute"
        approval_id = _approval_id_from_payload(payload)
        request_payload = _approval_request_payload(
            approval_action,
            {
                "target_kind": target_kind,
                "target_id": target_id,
                "action": action,
                "risk": risk,
                "dry_run": dry_run,
                "domain": domain,
                "actor": actor,
                "params": params,
                "meta": _approval_meta(meta),
            },
        )
        registry = _load_registry()
        interventions = registry.get("interventions")
        if not isinstance(interventions, list):
            interventions = []
            registry["interventions"] = interventions
        intervention_id = _new_id("intervention", target_id)
        record_idx = next(
            (
                i
                for i, item in enumerate(interventions)
                if approval_id and _safe_str(item.get("approval_id")).strip() == approval_id
            ),
            -1,
        )
        if record_idx >= 0:
            intervention_id = _safe_str(interventions[record_idx].get("id")).strip() or intervention_id

        status = "dry_run" if dry_run else "executed"
        result_id = _new_id("ires", f"{target_kind}_{target_id}_{action}") if not dry_run else ""
        message = "Intervention executed."

        if risk in {"high", "safety_critical"} and not dry_run:
            status = "pending"
            message = "High-risk intervention requires approval."

            if not approval_id:
                approval_id, art = _request_exact_approval(
                    action=approval_action,
                    reason=reason,
                    request_payload=request_payload,
                )
                intervention = {
                    "id": intervention_id,
                    "ts": _now_s(),
                    "mode": "execute",
                    "target_kind": target_kind,
                    "target_id": target_id,
                    "action": action,
                    "status": "pending",
                    "reason": reason,
                    "dry_run": dry_run,
                    "risk": risk,
                    "domain": domain,
                    "actor": actor,
                    "request_id": request_id,
                    "approval_id": approval_id,
                    "result_id": "",
                    "params": runtime_params,
                    "meta": meta,
                }
                interventions.append(intervention)
                _append_telemetry(
                    registry,
                    target_id,
                    {"intervention_executed": False, "dry_run": dry_run},
                    {"event": "interventions.execute"},
                )
                _save_registry(registry)
                return {
                    "ok": True,
                    "status": "pending",
                    "request_id": request_id,
                    "approval_id": approval_id,
                    "result_id": "",
                    "intervention_id": intervention_id,
                    "artifact_dir": str(art),
                    "message": message,
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
                    interventions[record_idx]["approval_id"] = refreshed_id
                    interventions[record_idx]["status"] = "pending"
                    interventions[record_idx]["request_id"] = request_id
                    interventions[record_idx]["ts"] = _now_s()
                _atomic_write(
                    art / "error.json",
                    {
                        "kind": "industrial.intervention.execute.error",
                        "approval_id": refreshed_id,
                        "previous_approval_id": approval_id,
                        "status": approval_status,
                        "request": request_payload,
                        "intervention_id": intervention_id,
                    },
                )
                _append_telemetry(
                    registry,
                    target_id,
                    {"intervention_executed": False, "dry_run": dry_run},
                    {"event": "interventions.execute"},
                )
                _save_registry(registry)
                return {
                    "ok": False,
                    "status": "needs_approval",
                    "error": "approval_not_found",
                    "request_id": request_id,
                    "approval_id": refreshed_id,
                    "previous_approval_id": approval_id,
                    "result_id": "",
                    "intervention_id": intervention_id,
                    "artifact_dir": str(art),
                    "message": "Approval was missing for this intervention execution; a fresh exact-action approval is required.",
                }
            if approval_status == "pending":
                return {
                    "ok": True,
                    "status": "pending",
                    "request_id": request_id,
                    "approval_id": approval_id,
                    "result_id": "",
                    "intervention_id": intervention_id,
                    "message": "Intervention request is awaiting approval.",
                }
            if approval_status in {"rejected", "emergency"}:
                return {
                    "ok": False,
                    "status": "denied",
                    "error": "approval_denied",
                    "request_id": request_id,
                    "approval_id": approval_id,
                    "result_id": "",
                    "intervention_id": intervention_id,
                    "message": "Approval was denied for this intervention execution.",
                    "meta": {"approval_status": approval_status},
                }
            if approval_status != "approved":
                return {
                    "ok": False,
                    "status": "needs_approval",
                    "error": "approval_not_found",
                    "request_id": request_id,
                    "approval_id": approval_id,
                    "result_id": "",
                    "intervention_id": intervention_id,
                    "message": "A matching approved request was not found for this intervention execution.",
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
                    interventions[record_idx]["approval_id"] = refreshed_id
                    interventions[record_idx]["status"] = "pending"
                    interventions[record_idx]["request_id"] = request_id
                    interventions[record_idx]["ts"] = _now_s()
                mismatch_body = {
                    "kind": "industrial.intervention.execute.mismatch",
                    "approval_id": refreshed_id,
                    "previous_approval_id": approval_id,
                    "intervention_id": intervention_id,
                    "request": request_payload,
                    "approval_record": approval_record,
                }
                _atomic_write(art / "mismatch.json", mismatch_body)
                _atomic_write(_approval_artifact_dir(approval_id) / "mismatch.json", mismatch_body)
                _append_telemetry(
                    registry,
                    target_id,
                    {"intervention_executed": False, "dry_run": dry_run},
                    {"event": "interventions.execute"},
                )
                _save_registry(registry)
                return {
                    "ok": False,
                    "status": "needs_approval",
                    "error": "approval_payload_mismatch",
                    "request_id": request_id,
                    "approval_id": refreshed_id,
                    "previous_approval_id": approval_id,
                    "result_id": "",
                    "intervention_id": intervention_id,
                    "artifact_dir": str(art),
                    "message": "Approval does not match this exact intervention execution request.",
                }

            status = "executed"
            message = "Intervention executed."

        intervention = {
            "id": intervention_id,
            "ts": _now_s(),
            "mode": "execute",
            "target_kind": target_kind,
            "target_id": target_id,
            "action": action,
            "status": status,
            "reason": reason,
            "dry_run": dry_run,
            "risk": risk,
            "domain": domain,
            "actor": actor,
            "request_id": request_id,
            "approval_id": approval_id,
            "result_id": result_id,
            "params": runtime_params,
            "meta": meta,
        }
        if record_idx >= 0:
            interventions[record_idx] = intervention
        else:
            interventions.append(intervention)
        _append_telemetry(
            registry,
            target_id,
            {"intervention_executed": status in {"executed", "dry_run"}, "dry_run": dry_run},
            {"event": "interventions.execute"},
        )
        _save_registry(registry)
        return {
            "ok": True,
            "status": status,
            "request_id": request_id,
            "approval_id": approval_id,
            "result_id": result_id,
            "intervention_id": intervention_id,
            "message": message,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/digital_twins/list")
def list_digital_twins() -> dict[str, object]:
    try:
        registry = _load_registry()
        assets = _list_section(registry, "assets", _normalize_asset)
        items: list[dict[str, Any]] = []
        for asset in assets:
            meta = asset.get("meta") if isinstance(asset.get("meta"), dict) else {}
            items.append(
                {
                    "id": asset.get("id"),
                    "name": asset.get("name"),
                    "kind": asset.get("asset_type") or "asset",
                    "status": asset.get("status") or "unknown",
                    "domain": _safe_str(meta.get("domain")).strip(),
                    "created_ts": asset.get("created_ts"),
                    "updated_ts": asset.get("updated_ts"),
                    "risk": asset.get("risk"),
                    "requires_approval": _safe_str(asset.get("risk")).strip().lower() in {"high", "safety_critical"},
                    "tags": asset.get("tags") or [],
                    "meta": meta,
                }
            )
        items.sort(key=lambda item: (int(item.get("updated_ts") or 0), _safe_str(item.get("id"))), reverse=True)
        return {"items": items, "twins": items, "total": len(items)}
    except Exception as exc:
        return {"items": [], "twins": [], "total": 0, "error": str(exc)}


@router.get("/digital_twins/get")
def get_digital_twin(id: str) -> dict[str, object]:
    try:
        entity_id = _validate_id(id, "twin id")
        registry = _load_registry()
        raw = _read_section(registry, "assets", entity_id)
        if raw is None:
            return {"ok": False, "error": "not_found"}
        asset = _normalize_asset(entity_id, raw)
        meta = asset.get("meta") if isinstance(asset.get("meta"), dict) else {}
        item = {
            "id": asset.get("id"),
            "name": asset.get("name"),
            "kind": asset.get("asset_type") or "asset",
            "status": asset.get("status") or "unknown",
            "domain": _safe_str(meta.get("domain")).strip(),
            "created_ts": asset.get("created_ts"),
            "updated_ts": asset.get("updated_ts"),
            "risk": asset.get("risk"),
            "requires_approval": _safe_str(asset.get("risk")).strip().lower() in {"high", "safety_critical"},
            "tags": asset.get("tags") or [],
            "meta": meta,
        }
        return {"ok": True, "item": item}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/digital_twins/snapshot")
def get_digital_twin_snapshot(id: str) -> dict[str, object]:
    try:
        entity_id = _validate_id(id, "twin id")
        registry = _load_registry()
        raw = _read_section(registry, "assets", entity_id)
        if raw is None:
            return {"ok": False, "error": "not_found"}
        asset = _normalize_asset(entity_id, raw)

        telemetry = registry.get("telemetry")
        source_points: list[dict[str, Any]] = []
        if isinstance(telemetry, list):
            for point_raw in telemetry:
                if isinstance(point_raw, dict) and _safe_str(point_raw.get("source_id")).strip() == entity_id:
                    point = _normalize_telemetry(point_raw)
                    if point is not None:
                        source_points.append(point)
        source_points.sort(key=lambda item: int(item.get("ts") or 0), reverse=True)
        latest = source_points[0] if source_points else None

        runs = _list_section(registry, "runs", _normalize_run)
        run_count = len([run for run in runs if _safe_str(run.get("simulation_id")).strip() == entity_id])
        running_count = len(
            [
                run
                for run in runs
                if _safe_str(run.get("simulation_id")).strip() == entity_id
                and _safe_str(run.get("status")).strip() == "running"
            ]
        )

        snapshot = {
            "id": entity_id,
            "ts": _now_s(),
            "status": asset.get("status") or "unknown",
            "summary": f"Twin snapshot for {asset.get('name') or entity_id}.",
            "state": {
                "asset": asset,
                "latest_telemetry": latest,
                "run_count": run_count,
                "running_count": running_count,
            },
            "health": {
                "telemetry_points": len(source_points),
                "has_recent_telemetry": bool(latest and int(latest.get("ts") or 0) >= _now_s() - 3600),
            },
        }
        return {"ok": True, "snapshot": snapshot}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/digital_twins/action")
def digital_twin_action(payload: dict[str, Any]) -> dict[str, object]:
    try:
        twin_id = _validate_id(_safe_str(payload.get("twin_id")).strip(), "twin id")
        action = _safe_str(payload.get("action")).strip()
        if not action:
            return {"ok": False, "error": "action_required", "twin_id": twin_id}
        registry = _load_registry()
        if _read_section(registry, "assets", twin_id) is None:
            return {"ok": False, "error": "not_found", "twin_id": twin_id}

        supplied_action_id = _safe_str(payload.get("action_id")).strip()
        supplied_approval_id = _approval_id_from_payload(payload)
        action_idx, action_record = _find_digital_twin_action_record(
            registry,
            action_id=supplied_action_id,
            approval_id=supplied_approval_id,
        )
        action_id = supplied_action_id or (
            _safe_str(action_record.get("id")).strip() if isinstance(action_record, dict) else ""
        )
        if not action_id:
            action_id = _new_id("dtact", twin_id)
        request_id = _safe_str(payload.get("request_id")).strip() or (
            _safe_str(action_record.get("request_id")).strip() if isinstance(action_record, dict) else ""
        )
        if not request_id:
            request_id = _new_id("dtreq", twin_id)
        approval_id = supplied_approval_id
        status = "pending"
        reason = _safe_str(payload.get("reason")).strip() or "requested"
        params = _normalize_approval_value(_normalize_meta(payload.get("params")))
        runtime_params = _redacted_runtime_params(payload.get("params"))

        if action == "validate_safety":
            validation_id = _new_id("validation", f"twin_{twin_id}")
            _write_section(
                registry,
                "safety_validations",
                validation_id,
                _normalize_validation(
                    validation_id,
                    {
                        "id": validation_id,
                        "ts": _now_s(),
                        "target_kind": "asset",
                        "target_id": twin_id,
                        "status": "warn",
                        "risk": "medium",
                        "summary": "Digital twin safety validation requested.",
                        "meta": {"reason": reason, "params": runtime_params},
                    },
                ),
            )
            status = "validated"
        else:
            approval_action = "industrial.digital_twin.action"
            request_payload = {
                "request_id": request_id,
                "action_id": action_id,
                "twin_id": twin_id,
                "action": action,
                "reason": reason,
                "params": params,
            }
            actions = registry.get("digital_twin_actions")
            if not isinstance(actions, list):
                actions = []
                registry["digital_twin_actions"] = actions

            if not approval_id:
                approval_id, _ = _request_exact_approval(
                    action=approval_action,
                    reason=reason,
                    request_payload=request_payload,
                )
                record = {
                    "id": action_id,
                    "ts": _now_s(),
                    "twin_id": twin_id,
                    "action": action,
                    "status": "pending",
                    "reason": reason,
                    "request_id": request_id,
                    "approval_id": approval_id,
                    "previous_approval_id": "",
                    "params": runtime_params,
                }
                if action_idx >= 0:
                    actions[action_idx] = record
                else:
                    actions.append(record)
            else:
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
                    record = {
                        "id": action_id,
                        "ts": _now_s(),
                        "twin_id": twin_id,
                        "action": action,
                        "status": "pending",
                        "reason": reason,
                        "request_id": request_id,
                        "approval_id": refreshed_id,
                        "previous_approval_id": approval_id,
                        "params": runtime_params,
                    }
                    if action_idx >= 0:
                        actions[action_idx] = record
                    else:
                        actions.append(record)
                    _atomic_write(
                        art / "error.json",
                        {
                            "kind": "industrial.digital_twin.action.error",
                            "approval_id": refreshed_id,
                            "previous_approval_id": approval_id,
                            "status": approval_status,
                            "request": request_payload,
                            "action_id": action_id,
                        },
                    )
                    _append_telemetry(
                        registry,
                        twin_id,
                        {"digital_twin_action": action},
                        {"event": "digital_twin.action", "action_id": action_id},
                    )
                    _save_registry(registry)
                    return {
                        "ok": False,
                        "twin_id": twin_id,
                        "action": action,
                        "action_id": action_id,
                        "request_id": request_id,
                        "approval_id": refreshed_id,
                        "previous_approval_id": approval_id,
                        "status": "needs_approval",
                        "error": "approval_not_found",
                        "artifact_dir": str(art),
                        "message": "Approval was missing for this digital twin action; a fresh exact-action approval is required.",
                    }
                if approval_status == "pending":
                    record = {
                        "id": action_id,
                        "ts": _now_s(),
                        "twin_id": twin_id,
                        "action": action,
                        "status": "pending",
                        "reason": reason,
                        "request_id": request_id,
                        "approval_id": approval_id,
                        "previous_approval_id": _safe_str(action_record.get("previous_approval_id")).strip()
                        if isinstance(action_record, dict)
                        else "",
                        "params": runtime_params,
                    }
                    if action_idx >= 0:
                        actions[action_idx] = record
                    else:
                        actions.append(record)
                    _append_telemetry(
                        registry,
                        twin_id,
                        {"digital_twin_action": action},
                        {"event": "digital_twin.action", "action_id": action_id},
                    )
                    _save_registry(registry)
                    return {
                        "ok": True,
                        "twin_id": twin_id,
                        "action": action,
                        "action_id": action_id,
                        "request_id": request_id,
                        "approval_id": approval_id,
                        "status": "pending",
                        "message": "Digital twin action is awaiting approval.",
                    }
                if approval_status in {"rejected", "emergency"}:
                    return {
                        "ok": False,
                        "twin_id": twin_id,
                        "action": action,
                        "action_id": action_id,
                        "request_id": request_id,
                        "approval_id": approval_id,
                        "status": "denied",
                        "error": "approval_denied",
                        "message": "Approval was denied for this digital twin action.",
                        "meta": {"approval_status": approval_status},
                    }
                if approval_status != "approved":
                    return {
                        "ok": False,
                        "twin_id": twin_id,
                        "action": action,
                        "action_id": action_id,
                        "request_id": request_id,
                        "approval_id": approval_id,
                        "status": "needs_approval",
                        "error": "approval_not_found",
                        "message": "A matching approved request was not found for this digital twin action.",
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
                        "kind": "industrial.digital_twin.action.mismatch",
                        "approval_id": refreshed_id,
                        "previous_approval_id": approval_id,
                        "action_id": action_id,
                        "request": request_payload,
                        "approval_record": approval_record,
                    }
                    _atomic_write(art / "mismatch.json", mismatch_body)
                    _atomic_write(_approval_artifact_dir(approval_id) / "mismatch.json", mismatch_body)
                    record = {
                        "id": action_id,
                        "ts": _now_s(),
                        "twin_id": twin_id,
                        "action": action,
                        "status": "pending",
                        "reason": reason,
                        "request_id": request_id,
                        "approval_id": refreshed_id,
                        "previous_approval_id": approval_id,
                        "params": runtime_params,
                    }
                    if action_idx >= 0:
                        actions[action_idx] = record
                    else:
                        actions.append(record)
                    _append_telemetry(
                        registry,
                        twin_id,
                        {"digital_twin_action": action},
                        {"event": "digital_twin.action", "action_id": action_id},
                    )
                    _save_registry(registry)
                    return {
                        "ok": False,
                        "twin_id": twin_id,
                        "action": action,
                        "action_id": action_id,
                        "request_id": request_id,
                        "approval_id": refreshed_id,
                        "previous_approval_id": approval_id,
                        "status": "needs_approval",
                        "error": "approval_payload_mismatch",
                        "artifact_dir": str(art),
                        "message": "Approval does not match this exact digital twin action request.",
                    }

                status = "approved"
                record = {
                    "id": action_id,
                    "ts": _now_s(),
                    "twin_id": twin_id,
                    "action": action,
                    "status": status,
                    "reason": reason,
                    "request_id": request_id,
                    "approval_id": approval_id,
                    "previous_approval_id": _safe_str(action_record.get("previous_approval_id")).strip()
                    if isinstance(action_record, dict)
                    else "",
                    "params": runtime_params,
                }
                if action_idx >= 0:
                    actions[action_idx] = record
                else:
                    actions.append(record)

        _append_telemetry(
            registry,
            twin_id,
            {"digital_twin_action": action},
            {"event": "digital_twin.action", "action_id": action_id}
            if action != "validate_safety"
            else {"event": "digital_twin.action"},
        )
        _save_registry(registry)
        return {
            "ok": True,
            "twin_id": twin_id,
            "action": action,
            "action_id": action_id,
            "request_id": request_id,
            "approval_id": approval_id,
            "status": status,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
