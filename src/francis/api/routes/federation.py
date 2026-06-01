from __future__ import annotations

from francis.api.errors import api_error_message
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request

from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir, repo_root
from francis.swarm import swarm_stage15_operator_stage_closure_decision_readback

router = APIRouter()
_FEDERATION_WRITE_SCOPE = "federation.write"
_FEDERATION_STAGE16_CLOSURE_SCOPE = "federation.stage16.closure.write"
_FEDERATION_SLEEP_RESUME_CONFIRMATION_SCOPE = "federation.stage16.sleep_resume.confirmation.write"
_STAGE16_FEDERATION_STAGE = "Stage 16 / Federation"
_FEDERATION_PAIRING_SCOPED_TRUST_CONTRACT_KIND = "francis.stage16.federation.pairing_scoped_trust_contract"
_FEDERATION_SYNC_MODEL_CONTRACT_KIND = "francis.stage16.federation.sync_model_contract"
_FEDERATION_REMOTE_APPROVAL_CONTRACT_KIND = "francis.stage16.federation.remote_approval_contract"
_FEDERATION_REVOCATION_CONTRACT_KIND = "francis.stage16.federation.revocation_contract"
_FEDERATION_NODE_CONTINUITY_CONTRACT_KIND = "francis.stage16.federation.node_attributed_continuity_contract"
_FEDERATION_COMPLETION_REVIEW_KIND = "francis.stage16.federation.completion_review"
_FEDERATION_LIVE_RUNTIME_READBACK_KIND = "francis.stage16.federation.live_runtime_readback_receipt"
_FEDERATION_LIVE_RUNTIME_READBACKS_KIND = "francis.stage16.federation.live_runtime_readback_receipts"
_FEDERATION_SLEEP_CONTINUITY_RUNBOOK_KIND = "francis.stage16.federation.sleep_continuity_runbook"
_FEDERATION_SLEEP_CONTINUITY_ACTION_KIND = "francis.stage16.federation.sleep_continuity_action"
_FEDERATION_SLEEP_RESUME_CONFIRMATION_KIND = "francis.stage16.federation.sleep_resume_operator_confirmation_receipt"
_FEDERATION_SLEEP_RESUME_CONFIRMATIONS_KIND = "francis.stage16.federation.sleep_resume_operator_confirmation_receipts"
_FEDERATION_SLEEP_RESUME_CONFIRMATION_ACTOR_READINESS_KIND = (
    "francis.stage16.federation.sleep_resume_operator_confirmation_actor_readiness"
)
_FEDERATION_STAGE16_CLOSURE_DECISION_KIND = "francis.stage16.federation.stage16_operator_stage_closure_decision_receipt"
_FEDERATION_STAGE16_CLOSURE_DECISIONS_KIND = (
    "francis.stage16.federation.stage16_operator_stage_closure_decision_receipts"
)
_STAGE16_SLEEP_CONTINUITY_PRE_SLEEP_EVIDENCE_GAP = "stage16_sleep_continuity_pre_sleep_evidence"
_STAGE16_SLEEP_RESUME_CONFIRMATION_ACTOR_GAP = "stage16_sleep_resume_confirmation_actor_readiness"
_STAGE16_SLEEP_RESUME_CONFIRMATION_RECEIPT_GAP = "stage16_sleep_resume_confirmation_receipt"
_STAGE16_SLEEP_CONTINUITY_RUNTIME_READBACK_GAP = "stage16_sleep_continuity_runtime_readback"

_STAGE16_LIVE_READBACK_IDS = (
    "live_pairing_flow_observed",
    "live_selective_sync_observed",
    "live_remote_approval_roundtrip_observed",
    "live_revocation_roundtrip_observed",
    "workstation_sleep_continuity_validated",
)

_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{1,127}$")


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _redacted_text(value: Any) -> str:
    return redact_secret_text(_safe_str(value))


def _federation_write_actor(payload: dict[str, Any]) -> str:
    return (
        _safe_str(payload.get("request_actor")).strip()
        or _safe_str(payload.get("api_actor")).strip()
        or _safe_str(payload.get("actor")).strip()
        or "api.federation"
    )


def _federation_write_permission(
    actor: Any,
    *,
    route: str,
    method: str,
    required_scope: str = _FEDERATION_WRITE_SCOPE,
) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[required_scope],
        route=route,
        method=method,
    )


def _permission_denied(decision: ApiPermissionDecision) -> dict[str, object]:
    return {
        "ok": False,
        "status": "denied",
        "error": "api_permission_denied",
        "governance": {
            "gate": "permission_gate",
            "reason": decision.reason,
            "next_step": "configure_actor_scope_before_writing_federation",
            "evidence": decision.evidence,
        },
    }


def _permission_denied_for_scope(
    decision: ApiPermissionDecision,
    *,
    required_scope: str,
    next_step: str,
) -> dict[str, object]:
    return {
        "ok": False,
        "status": "denied",
        "error": "api_permission_denied",
        "required_scope": required_scope,
        "governance": {
            "gate": "permission_gate",
            "reason": decision.reason,
            "next_step": next_step,
            "evidence": decision.evidence,
        },
    }


def _write_permission_denial(payload: dict[str, Any], request: Request) -> dict[str, object] | None:
    decision = _federation_write_permission(
        _federation_write_actor(payload),
        route=request.url.path,
        method=request.method,
    )
    if decision.allowed:
        return None
    return _permission_denied(decision)


def _now_s() -> int:
    return int(time.time())


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


def _to_bool(value: Any, *, default: bool) -> bool:
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


def _parse_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        candidates = [_safe_str(item).strip() for item in value]
    else:
        return []

    out: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in out:
            out.append(candidate)
    return out


def _meta(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _validate_id(value: str, field: str = "id") -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field} is required")
    if not _ID_RE.match(text):
        raise ValueError(f"invalid {field}")
    return text


def _federation_path() -> Path:
    return data_dir() / "federation" / "_registry.json"


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _default_registry() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": _now_s(),
        "instances": {},
        "delegations": [],
        "consensus_logs": [],
        "shared_knowledge": [],
    }


def _normalize_instance(instance_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    first_seen_ts = int(raw.get("first_seen_ts") or _now_s())
    last_seen_ts = int(raw.get("last_seen_ts") or first_seen_ts)
    trust_level_raw = raw.get("trust_level")
    trust_level = float(trust_level_raw) if isinstance(trust_level_raw, (int, float)) else 0.0
    return {
        "id": instance_id,
        "name": _safe_str(raw.get("name")).strip() or instance_id,
        "status": _safe_str(raw.get("status")).strip() or "unknown",
        "endpoint": _safe_str(raw.get("endpoint")).strip(),
        "region": _safe_str(raw.get("region")).strip(),
        "role": _safe_str(raw.get("role")).strip(),
        "first_seen_ts": first_seen_ts,
        "last_seen_ts": last_seen_ts,
        "capabilities": _parse_list(raw.get("capabilities")),
        "trust_level": trust_level,
        "requires_approval": _to_bool(raw.get("requires_approval"), default=False),
        "tags": _parse_list(raw.get("tags")),
        "health": _meta(raw.get("health")),
        "inventory": _meta(raw.get("inventory")),
        "meta": _meta(raw.get("meta")),
    }


def _normalize_delegation(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _safe_str(raw.get("id")).strip() or _new_id("deleg", _safe_str(raw.get("scope")).strip() or "scope"),
        "ts": int(raw.get("ts") or _now_s()),
        "from": _safe_str(raw.get("from")).strip() or _safe_str(raw.get("from_instance_id")).strip(),
        "to": _safe_str(raw.get("to")).strip() or _safe_str(raw.get("to_instance_id")).strip(),
        "scope": _safe_str(raw.get("scope")).strip() or _safe_str(raw.get("scope_id")).strip(),
        "status": _safe_str(raw.get("status")).strip() or "pending",
        "reason": _safe_str(raw.get("reason")).strip(),
        "meta": _meta(raw.get("meta")),
    }


def _normalize_consensus_log(raw: dict[str, Any]) -> dict[str, Any]:
    term_raw = raw.get("term")
    index_raw = raw.get("index")
    return {
        "id": _safe_str(raw.get("id")).strip() or _new_id("clog", _safe_str(raw.get("kind")).strip() or "entry"),
        "ts": int(raw.get("ts") or _now_s()),
        "level": _safe_str(raw.get("level")).strip() or "info",
        "kind": _safe_str(raw.get("kind")).strip(),
        "instance_id": _safe_str(raw.get("instance_id")).strip(),
        "term": int(term_raw) if isinstance(term_raw, (int, float)) else None,
        "index": int(index_raw) if isinstance(index_raw, (int, float)) else None,
        "message": _safe_str(raw.get("message")).strip(),
        "meta": _meta(raw.get("meta")),
    }


def _normalize_shared_knowledge(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _safe_str(raw.get("id")).strip() or _new_id("know", _safe_str(raw.get("title")).strip() or "knowledge"),
        "ts": int(raw.get("ts") or _now_s()),
        "kind": _safe_str(raw.get("kind")).strip() or "fact",
        "title": _safe_str(raw.get("title")).strip() or _safe_str(raw.get("name")).strip(),
        "source_instance_id": _safe_str(raw.get("source_instance_id")).strip() or _safe_str(raw.get("source")).strip(),
        "domain": _safe_str(raw.get("domain")).strip(),
        "tags": _parse_list(raw.get("tags")),
        "meta": _meta(raw.get("meta")),
    }


def _load_registry() -> dict[str, Any]:
    path = _federation_path()
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

    instances_raw = raw.get("instances")
    if isinstance(instances_raw, dict):
        instances: dict[str, dict[str, Any]] = {}
        for instance_id, item in instances_raw.items():
            normalized_id = _safe_str(instance_id).strip()
            if not normalized_id or not isinstance(item, dict):
                continue
            instances[normalized_id] = _normalize_instance(normalized_id, item)
        out["instances"] = instances

    for key, normalizer, max_items in (
        ("delegations", _normalize_delegation, 20_000),
        ("consensus_logs", _normalize_consensus_log, 50_000),
        ("shared_knowledge", _normalize_shared_knowledge, 20_000),
    ):
        raw_list = raw.get(key)
        if isinstance(raw_list, list):
            out[key] = [normalizer(item) for item in raw_list if isinstance(item, dict)][-max_items:]

    return out


def _save_registry(registry: dict[str, Any]) -> None:
    normalized = _load_registry()
    if isinstance(registry.get("instances"), dict):
        normalized_instances: dict[str, dict[str, Any]] = {}
        for instance_id, item in registry["instances"].items():
            key = _safe_str(instance_id).strip()
            if key and isinstance(item, dict):
                normalized_instances[key] = _normalize_instance(key, item)
        normalized["instances"] = normalized_instances

    for key, normalizer, max_items in (
        ("delegations", _normalize_delegation, 20_000),
        ("consensus_logs", _normalize_consensus_log, 50_000),
        ("shared_knowledge", _normalize_shared_knowledge, 20_000),
    ):
        if isinstance(registry.get(key), list):
            normalized[key] = [normalizer(item) for item in registry[key] if isinstance(item, dict)][-max_items:]

    normalized["version"] = int(registry.get("version") or normalized.get("version") or 1)
    normalized["updated_at"] = _now_s()
    _atomic_write(_federation_path(), normalized)


def _paginate(items: list[dict[str, Any]], limit: int, offset: int) -> tuple[list[dict[str, Any]], int, int, int]:
    safe_limit = max(1, min(int(limit), 5000))
    safe_offset = max(0, int(offset))
    total = len(items)
    return items[safe_offset : safe_offset + safe_limit], total, safe_limit, safe_offset


def _list_instances(
    registry: dict[str, Any],
    *,
    status: str | None,
    limit: int,
    offset: int,
    tags: list[str],
) -> dict[str, Any]:
    status_filter = _safe_str(status).strip().lower()
    tag_filter = set(_parse_list(tags))
    instances_obj = registry.get("instances") if isinstance(registry.get("instances"), dict) else {}

    items: list[dict[str, Any]] = []
    for instance_id, raw in instances_obj.items():
        if not isinstance(raw, dict):
            continue
        item = _normalize_instance(_safe_str(instance_id), raw)
        if status_filter and _safe_str(item.get("status")).strip().lower() != status_filter:
            continue
        if tag_filter and not tag_filter.issubset(set(_parse_list(item.get("tags")))):
            continue
        items.append(item)

    items.sort(key=lambda item: (int(item.get("last_seen_ts") or 0), _safe_str(item.get("id"))), reverse=True)
    page, total, safe_limit, safe_offset = _paginate(items, limit, offset)
    return {"items": page, "instances": page, "total": total, "limit": safe_limit, "offset": safe_offset}


def _list_delegations(registry: dict[str, Any], *, status: str | None, limit: int, offset: int) -> dict[str, Any]:
    status_filter = _safe_str(status).strip().lower()
    entries = registry.get("delegations") if isinstance(registry.get("delegations"), list) else []
    items = [_normalize_delegation(item) for item in entries if isinstance(item, dict)]
    if status_filter:
        items = [item for item in items if _safe_str(item.get("status")).strip().lower() == status_filter]
    items.sort(key=lambda item: (int(item.get("ts") or 0), _safe_str(item.get("id"))), reverse=True)
    page, total, safe_limit, safe_offset = _paginate(items, limit, offset)
    return {"items": page, "delegations": page, "total": total, "limit": safe_limit, "offset": safe_offset}


def _list_consensus_logs(
    registry: dict[str, Any],
    *,
    level: str | None,
    instance_id: str | None,
    start_ts: int | None,
    end_ts: int | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    level_filter = _safe_str(level).strip().lower()
    instance_filter = _safe_str(instance_id).strip()
    entries = registry.get("consensus_logs") if isinstance(registry.get("consensus_logs"), list) else []
    items = [_normalize_consensus_log(item) for item in entries if isinstance(item, dict)]

    out: list[dict[str, Any]] = []
    for item in items:
        if level_filter and _safe_str(item.get("level")).strip().lower() != level_filter:
            continue
        if instance_filter and _safe_str(item.get("instance_id")).strip() != instance_filter:
            continue
        ts = int(item.get("ts") or 0)
        if start_ts is not None and ts < int(start_ts):
            continue
        if end_ts is not None and ts > int(end_ts):
            continue
        out.append(item)

    out.sort(key=lambda item: (int(item.get("ts") or 0), _safe_str(item.get("id"))), reverse=True)
    page, total, safe_limit, safe_offset = _paginate(out, limit, offset)
    return {"items": page, "logs": page, "total": total, "limit": safe_limit, "offset": safe_offset}


def _list_shared_knowledge(
    registry: dict[str, Any],
    *,
    kind: str | None,
    domain: str | None,
    limit: int,
    offset: int,
    tags: list[str],
) -> dict[str, Any]:
    kind_filter = _safe_str(kind).strip().lower()
    domain_filter = _safe_str(domain).strip().lower()
    tag_filter = set(_parse_list(tags))
    entries = registry.get("shared_knowledge") if isinstance(registry.get("shared_knowledge"), list) else []
    items = [_normalize_shared_knowledge(item) for item in entries if isinstance(item, dict)]

    out: list[dict[str, Any]] = []
    for item in items:
        if kind_filter and _safe_str(item.get("kind")).strip().lower() != kind_filter:
            continue
        if domain_filter and _safe_str(item.get("domain")).strip().lower() != domain_filter:
            continue
        if tag_filter and not tag_filter.issubset(set(_parse_list(item.get("tags")))):
            continue
        out.append(item)

    out.sort(key=lambda item: (int(item.get("ts") or 0), _safe_str(item.get("id"))), reverse=True)
    page, total, safe_limit, safe_offset = _paginate(out, limit, offset)
    return {"items": page, "knowledge": page, "total": total, "limit": safe_limit, "offset": safe_offset}


def _federation_routes() -> dict[str, str]:
    return {
        "status": "/federation/status",
        "pairing_scoped_trust_contract": "/federation/pairing-scoped-trust-contract",
        "sync_model_contract": "/federation/sync-model-contract",
        "remote_approval_contract": "/federation/remote-approval-contract",
        "revocation_contract": "/federation/revocation-contract",
        "node_attributed_continuity_contract": "/federation/node-attributed-continuity-contract",
        "completion_review": "/federation/completion-review",
        "sleep_continuity_runbook": "/federation/sleep-continuity-runbook",
        "sleep_continuity_action": "/federation/sleep-continuity-action",
        "sleep_resume_confirmations": "/federation/sleep-resume-confirmations",
        "sleep_resume_confirmation": "/federation/sleep-resume-confirmation",
        "sleep_resume_confirmation_actor_readiness": "/federation/sleep-resume-confirmation/actor-readiness",
        "stage_closure_decisions": "/federation/stage-closure-decisions",
        "stage_closure_decision": "/federation/stage-closure-decision",
        "live_runtime_readbacks": "/federation/live-runtime-readbacks",
        "live_runtime_readback": "/federation/live-runtime-readback",
        "instances_list": "/federation/instances/list",
        "instances_get": "/federation/instances/get",
        "delegations_list": "/federation/delegations/list",
        "consensus_logs_list": "/federation/consensus_logs/list",
        "shared_knowledge_list": "/federation/shared_knowledge/list",
        "instances_upsert": "/federation/instances/upsert",
        "delegations_record": "/federation/delegations/record",
        "consensus_logs_append": "/federation/consensus_logs/append",
        "shared_knowledge_publish": "/federation/shared_knowledge/publish",
        "stage15_closure_readback": "/swarm/stage-closure-decisions",
    }


def _federation_governance(*, read_only: bool = True) -> dict[str, Any]:
    return {
        "read_only": read_only,
        "stage16_contract_only": True,
        "zero_trust_default": True,
        "explicit_pairing_required": True,
        "scoped_trust_required": True,
        "revocation_required": True,
        "node_identity_required": True,
        "trace_lineage_required": True,
        "selective_replication_required": True,
        "raw_private_data_replication_allowed": False,
        "hidden_trust_expansion_allowed": False,
        "cloud_vagueness_allowed": False,
        "writes_registry": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def _runtime_readback_path() -> Path:
    return data_dir() / "logs" / "federation" / "stage16_live_runtime_readbacks.jsonl"


def _stage16_operator_stage_closure_decision_path() -> Path:
    return data_dir() / "logs" / "federation" / "stage16_operator_stage_closure_decisions.jsonl"


def _stage16_sleep_resume_confirmation_path() -> Path:
    return data_dir() / "logs" / "federation" / "stage16_sleep_resume_operator_confirmations.jsonl"


def _stage16_sleep_continuity_evidence_root() -> Path:
    return data_dir() / "test_runs" / "federation-stage16-sleep-continuity-evidence"


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str))
        handle.write("\n")


def _read_jsonl_tail(path: Path, *, limit: int) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 500))
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-safe_limit:]:
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _safe_runtime_readback_id(value: Any) -> str:
    text = _safe_str(value).strip()
    if text in _STAGE16_LIVE_READBACK_IDS:
        return text
    return ""


def _runtime_readback_ready(item: dict[str, Any]) -> bool:
    governance = item.get("governance") if isinstance(item.get("governance"), dict) else {}
    return (
        _safe_runtime_readback_id(item.get("readback_id")) != ""
        and bool(item.get("observed"))
        and _safe_str(item.get("status")).strip() == "observed"
        and _safe_str(item.get("source_node_id")).strip() != ""
        and _safe_str(item.get("paired_node_id")).strip() != ""
        and _safe_str(item.get("trace_id")).strip() != ""
        and _safe_str(item.get("evidence_summary")).strip() != ""
        and _safe_str(item.get("proof_kind")).strip()
        in {"live_runtime_probe", "manual_operator_runtime_readback", "scripted_local_runtime_probe"}
        and bool(governance.get("readback_receipt"))
        and bool(governance.get("node_attributed"))
        and bool(governance.get("trace_linked"))
        and bool(governance.get("redacted"))
        and not bool(governance.get("contains_raw_private_data"))
        and not bool(governance.get("grants_execution_authority"))
        and not bool(governance.get("grants_mutation_authority"))
    )


def _runtime_readback_counts_for_completion(item: dict[str, Any]) -> bool:
    proof_kind = _safe_str(item.get("proof_kind")).strip()
    return _runtime_readback_ready(item) and proof_kind in {"live_runtime_probe", "manual_operator_runtime_readback"}


def _latest_live_readback_by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for item in items:
        readback_id = _safe_runtime_readback_id(item.get("readback_id"))
        if readback_id:
            latest[readback_id] = item
    return latest


def _next_stage16_live_readback_gap(*, missing_readbacks: list[str], ready_count: int) -> str:
    if not missing_readbacks:
        return "stage16_completion_review"
    if ready_count <= 0:
        return "stage16_live_federation_runtime_readback"
    first_missing = _safe_str(missing_readbacks[0]).strip()
    return {
        "live_pairing_flow_observed": "stage16_pairing_runtime_readback",
        "live_selective_sync_observed": "stage16_selective_sync_runtime_readback",
        "live_remote_approval_roundtrip_observed": "stage16_remote_approval_runtime_readback",
        "live_revocation_roundtrip_observed": "stage16_revocation_runtime_readback",
        "workstation_sleep_continuity_validated": "stage16_sleep_continuity_runtime_readback",
    }.get(first_missing, "stage16_live_federation_runtime_readback")


def read_live_runtime_readbacks(*, limit: int = 100) -> list[dict[str, Any]]:
    return _read_jsonl_tail(_runtime_readback_path(), limit=limit)


def live_runtime_readback_summary(*, limit: int = 100) -> dict[str, Any]:
    items = read_live_runtime_readbacks(limit=limit)
    latest_by_id = _latest_live_readback_by_id(items)
    checks: list[dict[str, Any]] = []
    for readback_id in _STAGE16_LIVE_READBACK_IDS:
        item = latest_by_id.get(readback_id, {})
        receipt_ready = _runtime_readback_ready(item)
        completion_evidence = _runtime_readback_counts_for_completion(item)
        checks.append(
            {
                "id": readback_id,
                "passed": completion_evidence,
                "receipt_ready": receipt_ready,
                "completion_evidence": completion_evidence,
                "status": "observed" if completion_evidence else "receipt_only" if receipt_ready else "not_observed",
                "receipt_id": _safe_str(item.get("receipt_id")).strip(),
                "proof_kind": _safe_str(item.get("proof_kind")).strip(),
                "source_node_id": _safe_str(item.get("source_node_id")).strip(),
                "paired_node_id": _safe_str(item.get("paired_node_id")).strip(),
                "trace_id": _safe_str(item.get("trace_id")).strip(),
                "evidence": _safe_str(item.get("evidence_summary")).strip()
                or f"no {readback_id} receipt has been recorded",
            }
        )
    ready_count = sum(1 for item in checks if bool(item["completion_evidence"]))
    missing_readbacks = [item["id"] for item in checks if not bool(item["completion_evidence"])]
    return {
        "ok": True,
        "kind": _FEDERATION_LIVE_RUNTIME_READBACKS_KIND,
        "stage": _STAGE16_FEDERATION_STAGE,
        "source_id": "federation",
        "status": "ready" if all(bool(item["passed"]) for item in checks) else "partial" if items else "empty",
        "items": items,
        "checks": checks,
        "count": len(items),
        "receipt_ready_count": sum(1 for item in checks if bool(item["receipt_ready"])),
        "ready_count": ready_count,
        "completion_eligible_readback_count": ready_count,
        "required_count": len(checks),
        "readback_receipts_ready": all(bool(item["receipt_ready"]) for item in checks),
        "live_runtime_readback_ready": all(bool(item["completion_evidence"]) for item in checks),
        "missing_readbacks": missing_readbacks,
        "routes": _federation_routes(),
        "governance": {
            **_federation_governance(),
            "readback_receipt_readback": True,
            "read_only": True,
        },
        "writes_registry": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "next_smallest_truthful_gap": "stage16_completion_review"
        if all(bool(item["passed"]) for item in checks)
        else _next_stage16_live_readback_gap(missing_readbacks=missing_readbacks, ready_count=ready_count),
    }


def record_live_runtime_readback(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    if denial := _write_permission_denial(payload, request):
        return denial

    readback_id = _safe_runtime_readback_id(payload.get("readback_id") or payload.get("id"))
    if not readback_id:
        return {
            "ok": False,
            "status": "denied",
            "error": "invalid_live_runtime_readback_id",
            "allowed_readback_ids": list(_STAGE16_LIVE_READBACK_IDS),
        }

    proof_kind = _safe_str(payload.get("proof_kind")).strip() or "manual_operator_runtime_readback"
    item = {
        "ok": True,
        "kind": _FEDERATION_LIVE_RUNTIME_READBACK_KIND,
        "receipt_id": f"fedlive_{readback_id}_{uuid.uuid4().hex[:12]}",
        "stage": _STAGE16_FEDERATION_STAGE,
        "source_id": "federation",
        "readback_id": readback_id,
        "status": "observed" if _to_bool(payload.get("observed"), default=False) else "not_observed",
        "observed": _to_bool(payload.get("observed"), default=False),
        "actor": _safe_str(payload.get("request_actor") or payload.get("api_actor") or payload.get("actor")).strip()
        or "api.federation",
        "reason": _safe_str(payload.get("reason")).strip()[:500],
        "proof_kind": proof_kind,
        "source_node_id": _safe_str(payload.get("source_node_id")).strip()[:160],
        "paired_node_id": _safe_str(payload.get("paired_node_id")).strip()[:160],
        "trace_id": _safe_str(payload.get("trace_id")).strip()[:240],
        "parent_receipt_id": _safe_str(payload.get("parent_receipt_id")).strip()[:240],
        "evidence_summary": _safe_str(payload.get("evidence_summary")).strip()[:800],
        "recorded_ts": int(payload.get("recorded_ts") or _now_s()),
        "writes_registry": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            **_federation_governance(read_only=False),
            "readback_receipt": True,
            "read_only": False,
            "permission_scope": _FEDERATION_WRITE_SCOPE,
            "node_attributed": True,
            "trace_linked": True,
            "redacted": True,
            "contains_raw_private_data": False,
            "contains_raw_prompt_body": False,
            "contains_raw_model_response": False,
            "writes_receipt": True,
        },
    }
    item["readback_ready"] = _runtime_readback_ready(item)
    _append_jsonl(_runtime_readback_path(), item)
    return item


def _safe_stage16_closure_decision(value: Any) -> str:
    text = _safe_str(value).strip()
    if text in {"close_stage16", "do_not_close_stage16", "needs_more_evidence"}:
        return text
    return "needs_more_evidence"


def read_stage16_operator_stage_closure_decisions(*, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl_tail(_stage16_operator_stage_closure_decision_path(), limit=limit)


def stage16_operator_stage_closure_decision_count() -> int:
    path = _stage16_operator_stage_closure_decision_path()
    if not path.exists() or not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())


def record_stage16_operator_stage_closure_decision(payload: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    safe_decision = _safe_stage16_closure_decision(payload.get("decision"))
    stage16_closed_by_receipt = bool(review.get("stage16_completion_review_ready")) and safe_decision == "close_stage16"
    review_live_checks = review.get("live_checks") if isinstance(review.get("live_checks"), list) else []
    latest_live_runtime_readback_receipt_ids = [
        _safe_str(item.get("receipt_id")).strip()
        for item in review_live_checks
        if isinstance(item, dict) and _safe_str(item.get("receipt_id")).strip()
    ]
    receipt = {
        "ok": True,
        "kind": _FEDERATION_STAGE16_CLOSURE_DECISION_KIND,
        "receipt_id": f"fedstage16close_{uuid.uuid4().hex[:12]}",
        "stage": _STAGE16_FEDERATION_STAGE,
        "source_id": "federation",
        "target": "stage16_federation",
        "actor": _redacted_text(payload.get("actor") or payload.get("request_actor") or payload.get("api_actor"))[:240],
        "reason": _redacted_text(payload.get("reason"))[:500],
        "decision": safe_decision,
        "notes": _redacted_text(payload.get("notes"))[:500],
        "completion_review_ready": bool(review.get("stage16_completion_review_ready")),
        "stage16_completion_review_ready": bool(review.get("stage16_completion_review_ready")),
        "contract_readiness_ready": bool(review.get("contract_readiness_ready")),
        "live_runtime_readback_ready": bool(review.get("live_runtime_readback_ready")),
        "ready_to_close": bool(review.get("ready_to_close")),
        "stage16_closed_by_receipt": stage16_closed_by_receipt,
        "stage15_closed_by_receipt": bool(review.get("stage15_closed_by_receipt")),
        "stage15_latest_closure_receipt_id": _safe_str(review.get("stage15_latest_closure_receipt_id")).strip(),
        "ready_count": int(review.get("ready_count") or 0),
        "required_count": int(review.get("required_count") or 0),
        "live_ready_count": int(review.get("live_ready_count") or 0),
        "live_required_count": int(review.get("live_required_count") or 0),
        "blockers": _parse_list(review.get("blockers")),
        "latest_live_runtime_readback_receipt_ids": latest_live_runtime_readback_receipt_ids,
        "marks_runtime_stage_state": False,
        "recorded_ts": _now_s(),
        "governance": {
            **_federation_governance(read_only=False),
            "permission_scope": _FEDERATION_STAGE16_CLOSURE_SCOPE,
            "explicit_operator_decision": True,
            "stage_closure_decision": True,
            "requires_completion_review_ready": True,
            "requires_live_runtime_readback": True,
            "does_not_mutate_runtime_stage_state": True,
            "does_not_write_tasks": True,
            "does_not_write_memory": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "writes_receipt": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }
    _append_jsonl(_stage16_operator_stage_closure_decision_path(), receipt)
    return receipt


def stage16_operator_stage_closure_decision_readback(*, limit: int = 20) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 100))
    items = read_stage16_operator_stage_closure_decisions(limit=safe_limit)
    latest_receipt = items[-1] if items else {}
    decision_counts = {"close_stage16": 0, "do_not_close_stage16": 0, "needs_more_evidence": 0}
    for item in items:
        decision = _safe_str(item.get("decision")).strip()
        if decision in decision_counts:
            decision_counts[decision] += 1
    stage16_closed_by_receipt = bool(latest_receipt.get("stage16_closed_by_receipt"))
    return {
        "ok": True,
        "kind": _FEDERATION_STAGE16_CLOSURE_DECISIONS_KIND,
        "stage": _STAGE16_FEDERATION_STAGE,
        "source_id": "federation",
        "status": "stage_closure_decision_readback_ready" if items else "empty",
        "target": "stage16_federation",
        "items": items,
        "count": len(items),
        "total": stage16_operator_stage_closure_decision_count(),
        "limit": safe_limit,
        "latest_receipt": latest_receipt,
        "latest_receipt_id": _safe_str(latest_receipt.get("receipt_id")).strip(),
        "latest_decision": _safe_str(latest_receipt.get("decision")).strip(),
        "latest_recorded_ts": int(latest_receipt.get("recorded_ts") or 0),
        "decision_counts": decision_counts,
        "receipt_readback_ready": bool(latest_receipt),
        "stage16_closed_by_receipt": stage16_closed_by_receipt,
        "marks_runtime_stage_state": False,
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_registry": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            **_federation_governance(),
            "read_only": True,
            "stage_closure_decision_receipt_readback": True,
            "receipt_readback_ready": bool(latest_receipt),
            "does_not_mutate_runtime_stage_state": True,
            "does_not_write_receipts": True,
            "does_not_write_tasks": True,
            "does_not_write_memory": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage16_ledger_closure"
        if stage16_closed_by_receipt
        else "stage16_operator_stage_closure_decision",
    }


def read_stage16_sleep_resume_confirmations(*, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl_tail(_stage16_sleep_resume_confirmation_path(), limit=limit)


def stage16_sleep_resume_confirmation_count() -> int:
    path = _stage16_sleep_resume_confirmation_path()
    if not path.exists() or not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())


def record_stage16_sleep_resume_confirmation(
    payload: dict[str, Any],
    action: dict[str, Any],
) -> dict[str, Any]:
    sleep_gate = (
        action.get("operator_sleep_resume_gate") if isinstance(action.get("operator_sleep_resume_gate"), dict) else {}
    )
    operator_handoff = (
        action.get("operator_confirmation_handoff")
        if isinstance(action.get("operator_confirmation_handoff"), dict)
        else {}
    )
    receipt = {
        "ok": True,
        "kind": _FEDERATION_SLEEP_RESUME_CONFIRMATION_KIND,
        "receipt_id": f"fedsleepconfirm_{uuid.uuid4().hex[:12]}",
        "stage": _STAGE16_FEDERATION_STAGE,
        "source_id": "federation",
        "target": "stage16_sleep_continuity",
        "actor": _redacted_text(payload.get("actor") or payload.get("request_actor") or payload.get("api_actor"))[:240],
        "reason": _redacted_text(payload.get("reason"))[:500],
        "decision": "operator_confirmed_sleep_resume",
        "selected_step_id": _safe_str(action.get("selected_step_id")).strip(),
        "operator_confirmed_sleep_resume": True,
        "pre_sleep_evidence_path": _safe_str(sleep_gate.get("pre_sleep_evidence_path")).strip(),
        "pre_sleep_recorded_ts": int(sleep_gate.get("pre_sleep_recorded_ts") or 0),
        "continuity_record_id": _safe_str(sleep_gate.get("continuity_record_id")).strip(),
        "trace_id": _safe_str(sleep_gate.get("trace_id")).strip(),
        "confirmation_requirements": _parse_list(action.get("operator_confirmation_requirements")),
        "post_resume_capture_allowed_after_confirmation": bool(
            action.get("post_confirmation_ready_to_capture")
            or sleep_gate.get("post_resume_capture_allowed_after_operator_confirmation")
        ),
        "post_resume_sequence_available_after_confirmation": bool(
            operator_handoff.get("post_resume_sequence_available_after_confirmation")
        ),
        "recorded_ts": _now_s(),
        "writes_evidence": False,
        "writes_runtime_readback": False,
        "writes_receipt": True,
        "writes_registry": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "marks_stage16_closed": False,
        "governance": {
            **_federation_governance(read_only=False),
            "permission_scope": _FEDERATION_SLEEP_RESUME_CONFIRMATION_SCOPE,
            "explicit_operator_confirmation": True,
            "operator_confirmation_receipt": True,
            "manual_operator_confirmation_after_physical_sleep_resume": True,
            "requires_current_sleep_resume_action": True,
            "requires_pre_sleep_evidence_path_match": True,
            "does_not_infer_sleep_from_delay": True,
            "does_not_capture_post_resume_evidence": True,
            "does_not_write_runtime_readback": True,
            "does_not_mark_stage16_closed": True,
            "writes_receipt": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }
    _append_jsonl(_stage16_sleep_resume_confirmation_path(), receipt)
    return receipt


def stage16_sleep_resume_confirmation_actor_readiness(actor: str) -> dict[str, Any]:
    routes = _federation_routes()
    safe_actor = _redacted_text(actor)[:240]
    actor_present = bool(_safe_str(actor).strip())
    placeholder_actor = _stage16_sleep_resume_confirmation_actor_is_placeholder(actor)
    permission = _federation_write_permission(
        actor,
        route=routes["sleep_resume_confirmation"],
        method="POST",
        required_scope=_FEDERATION_SLEEP_RESUME_CONFIRMATION_SCOPE,
    )
    actor_ready = actor_present and not placeholder_actor and bool(permission.allowed)
    if not actor_present:
        status = "actor_missing"
        next_step = "provide_scoped_operator_or_delegated_builder_actor"
    elif placeholder_actor:
        status = "placeholder_actor_rejected"
        next_step = "replace_actor_placeholder_with_scoped_operator_or_delegated_builder_actor"
    elif actor_ready:
        status = "actor_ready_for_sleep_resume_confirmation"
        next_step = "use_actor_in_confirmation_receipt_command_after_real_sleep_resume"
    else:
        status = "actor_scope_missing"
        next_step = "grant_federation_stage16_sleep_resume_confirmation_write_scope_before_receipt"
    current_pre_sleep = _latest_stage16_pre_sleep_evidence()
    current_pre_sleep_path = _safe_str(current_pre_sleep.get("evidence_path")).strip()
    command_projection = _stage16_sleep_resume_confirmation_command_projection(
        pre_sleep_evidence_path=current_pre_sleep_path,
        ready=actor_ready and bool(current_pre_sleep.get("present")),
        actor=actor if actor_ready else "",
    )
    if not bool(current_pre_sleep.get("present")):
        next_gap = _STAGE16_SLEEP_CONTINUITY_PRE_SLEEP_EVIDENCE_GAP
    elif actor_ready:
        next_gap = _STAGE16_SLEEP_RESUME_CONFIRMATION_RECEIPT_GAP
    else:
        next_gap = _STAGE16_SLEEP_RESUME_CONFIRMATION_ACTOR_GAP

    return {
        "ok": True,
        "kind": _FEDERATION_SLEEP_RESUME_CONFIRMATION_ACTOR_READINESS_KIND,
        "stage": _STAGE16_FEDERATION_STAGE,
        "source_id": "federation",
        "status": status,
        "target": "stage16_sleep_continuity",
        "actor": safe_actor,
        "actor_present": actor_present,
        "actor_placeholder_rejected": placeholder_actor,
        "required_scope": _FEDERATION_SLEEP_RESUME_CONFIRMATION_SCOPE,
        "target_method": "POST",
        "target_route": routes["sleep_resume_confirmation"],
        "readiness_route": routes["sleep_resume_confirmation_actor_readiness"],
        "current_pre_sleep_evidence_present": bool(current_pre_sleep.get("present")),
        "current_pre_sleep_evidence_path": current_pre_sleep_path,
        "permission_allowed": bool(permission.allowed),
        "permission_reason": _safe_str(permission.reason).strip(),
        "permission_evidence": permission.evidence,
        "confirmation_receipt_actor_ready": actor_ready,
        "safe_to_use_in_confirmation_command": actor_ready,
        "next_step": next_step,
        **command_projection,
        "reads_permission_gate": True,
        "writes_receipt": False,
        "writes_evidence": False,
        "writes_runtime_readback": False,
        "writes_registry": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "marks_stage16_closed": False,
        "governance": {
            **_federation_governance(),
            "read_only": True,
            "actor_scope_preflight": True,
            "target_route": routes["sleep_resume_confirmation"],
            "target_method": "POST",
            "required_scope": _FEDERATION_SLEEP_RESUME_CONFIRMATION_SCOPE,
            "rejects_placeholder_actor": True,
            "does_not_write_receipts": True,
            "does_not_write_evidence": True,
            "does_not_write_runtime_readback": True,
            "does_not_mark_stage16_closed": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": next_gap,
    }


def stage16_sleep_resume_confirmation_readback(*, limit: int = 20) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 100))
    items = read_stage16_sleep_resume_confirmations(limit=safe_limit)
    latest_receipt = items[-1] if items else {}
    current_pre_sleep = _latest_stage16_pre_sleep_evidence()
    current_pre_sleep_path = _safe_str(current_pre_sleep.get("evidence_path")).strip()
    latest_pre_sleep_path = _safe_str(latest_receipt.get("pre_sleep_evidence_path")).strip()
    latest_decision = _safe_str(latest_receipt.get("decision")).strip()
    latest_operator_confirmed = bool(latest_receipt.get("operator_confirmed_sleep_resume"))
    latest_matches_current_pre_sleep = bool(
        latest_receipt and current_pre_sleep_path and latest_pre_sleep_path == current_pre_sleep_path
    )
    receipt_backed_sequence_ready = latest_matches_current_pre_sleep and latest_operator_confirmed
    receipt_backed_sequence_blockers: list[str] = []
    if not bool(current_pre_sleep.get("present")):
        receipt_backed_sequence_blockers.append("current_pre_sleep_evidence_missing")
    if not latest_receipt:
        receipt_backed_sequence_blockers.append("sleep_resume_confirmation_receipt_missing")
    elif not latest_operator_confirmed or latest_decision != "operator_confirmed_sleep_resume":
        receipt_backed_sequence_blockers.append("latest_sleep_resume_confirmation_not_operator_confirmed")
    elif not latest_matches_current_pre_sleep:
        receipt_backed_sequence_blockers.append("latest_sleep_resume_confirmation_pre_sleep_path_mismatch")
    pre_sleep_arg = f'"{current_pre_sleep_path}"' if current_pre_sleep_path else "<pre_sleep.json>"
    receipt_id_arg = _safe_str(latest_receipt.get("receipt_id")).strip() or "<confirmation_receipt_id>"
    receipt_backed_sequence_command = (
        "scripts/federation-stage16-sleep-continuity-post-resume-sequence.ps1 -Mode Run "
        f"-CommitEvidence -CommitReceipts -PreSleepEvidencePath {pre_sleep_arg} "
        "-OperatorConfirmedSleepResume -RequireConfirmationReceipt "
        f"-ConfirmationReceiptId {receipt_id_arg}"
    )
    confirmation_command = _stage16_sleep_resume_confirmation_command_projection(
        pre_sleep_evidence_path=current_pre_sleep_path,
        ready=bool(current_pre_sleep.get("present")) and not receipt_backed_sequence_ready,
    )
    confirmation_operator_steps = _stage16_sleep_resume_confirmation_operator_steps(
        confirmation_command_ready=bool(confirmation_command.get("confirmation_receipt_command_ready")),
        receipt_backed_sequence_ready=receipt_backed_sequence_ready,
        receipt_backed_sequence_command_field="receipt_backed_sequence_copyable_command",
    )
    next_gap = _stage16_sleep_resume_confirmation_next_gap(
        receipt_backed_sequence_ready=receipt_backed_sequence_ready,
        blockers=receipt_backed_sequence_blockers,
    )
    return {
        "ok": True,
        "kind": _FEDERATION_SLEEP_RESUME_CONFIRMATIONS_KIND,
        "stage": _STAGE16_FEDERATION_STAGE,
        "source_id": "federation",
        "status": "sleep_resume_confirmation_readback_ready" if items else "empty",
        "target": "stage16_sleep_continuity",
        "items": items,
        "count": len(items),
        "total": stage16_sleep_resume_confirmation_count(),
        "limit": safe_limit,
        "latest_receipt": latest_receipt,
        "latest_receipt_id": _safe_str(latest_receipt.get("receipt_id")).strip(),
        "latest_actor": _safe_str(latest_receipt.get("actor")).strip(),
        "latest_decision": latest_decision,
        "latest_pre_sleep_evidence_path": latest_pre_sleep_path,
        "latest_recorded_ts": int(latest_receipt.get("recorded_ts") or 0),
        "receipt_readback_ready": bool(latest_receipt),
        "current_pre_sleep_evidence_present": bool(current_pre_sleep.get("present")),
        "current_pre_sleep_evidence_path": current_pre_sleep_path,
        "current_pre_sleep_recorded_ts": int(current_pre_sleep.get("recorded_ts") or 0),
        "latest_receipt_is_operator_confirmed": latest_operator_confirmed
        and latest_decision == "operator_confirmed_sleep_resume",
        "latest_receipt_matches_current_pre_sleep": latest_matches_current_pre_sleep,
        "latest_receipt_usable_for_receipt_backed_sequence": receipt_backed_sequence_ready,
        "receipt_backed_sequence_ready": receipt_backed_sequence_ready,
        "receipt_backed_sequence_blockers": receipt_backed_sequence_blockers,
        "receipt_backed_sequence_command": receipt_backed_sequence_command if receipt_backed_sequence_ready else "",
        "receipt_backed_sequence_copyable_command": (
            f"Set-Location -LiteralPath {_powershell_single_quote(str(repo_root()))}; {receipt_backed_sequence_command}"
            if receipt_backed_sequence_ready
            else ""
        ),
        **confirmation_command,
        "confirmation_receipt_operator_steps": confirmation_operator_steps,
        "receipt_backed_sequence_requires_confirmation_receipt": True,
        "receipt_backed_sequence_writes_evidence_when_run": receipt_backed_sequence_ready,
        "receipt_backed_sequence_writes_receipts_when_run": receipt_backed_sequence_ready,
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_evidence": False,
        "writes_runtime_readback": False,
        "writes_registry": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "marks_stage16_closed": False,
        "routes": _federation_routes(),
        "governance": {
            **_federation_governance(),
            "read_only": True,
            "sleep_resume_confirmation_receipt_readback": True,
            "receipt_readback_ready": bool(latest_receipt),
            "checks_current_pre_sleep_evidence_path": True,
            "receipt_backed_sequence_requires_current_matching_confirmation": True,
            "receipt_backed_sequence_next_gap_projected": True,
            "does_not_infer_sleep_from_delay": True,
            "does_not_write_receipts": True,
            "does_not_write_evidence": True,
            "does_not_write_runtime_readback": True,
            "does_not_mark_stage16_closed": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": next_gap,
    }


def _stage16_sleep_resume_confirmation_next_gap(
    *,
    receipt_backed_sequence_ready: bool,
    blockers: list[str],
) -> str:
    if receipt_backed_sequence_ready:
        return _STAGE16_SLEEP_CONTINUITY_RUNTIME_READBACK_GAP
    if "current_pre_sleep_evidence_missing" in blockers:
        return _STAGE16_SLEEP_CONTINUITY_PRE_SLEEP_EVIDENCE_GAP
    if any(
        blocker in blockers
        for blocker in (
            "sleep_resume_confirmation_receipt_missing",
            "latest_sleep_resume_confirmation_not_operator_confirmed",
            "latest_sleep_resume_confirmation_pre_sleep_path_mismatch",
        )
    ):
        return _STAGE16_SLEEP_RESUME_CONFIRMATION_RECEIPT_GAP
    return _STAGE16_SLEEP_CONTINUITY_RUNTIME_READBACK_GAP


def _latest_stage16_pre_sleep_evidence() -> dict[str, Any]:
    evidence_root = _stage16_sleep_continuity_evidence_root()
    if not evidence_root.exists() or not evidence_root.is_dir():
        return {
            "present": False,
            "evidence_root": str(evidence_root),
            "evidence_path": "",
            "status": "missing",
        }

    root_real = evidence_root.resolve()
    candidates = sorted(
        (path for path in evidence_root.glob("pre_sleep_*.json") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            resolved.relative_to(root_real)
            raw = json.loads(resolved.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(raw, dict):
            continue
        governance = raw.get("governance") if isinstance(raw.get("governance"), dict) else {}
        if _safe_str(raw.get("evidence_kind")).strip() != "stage16_sleep_continuity_pre_sleep":
            continue
        return {
            "present": True,
            "status": "pre_sleep_evidence_available",
            "evidence_root": str(root_real),
            "evidence_path": str(resolved),
            "file_name": resolved.name,
            "recorded_ts": int(raw.get("source_recorded_ts") or raw.get("recorded_ts") or 0),
            "continuity_record_id": _safe_str(raw.get("continuity_record_id")).strip(),
            "source_node_id": _safe_str(raw.get("source_node_id")).strip(),
            "paired_node_id": _safe_str(raw.get("paired_node_id")).strip(),
            "trace_id": _safe_str(raw.get("trace_id")).strip(),
            "authority_snapshot_id": _safe_str(raw.get("authority_snapshot_id")).strip(),
            "freshness_state": _safe_str(raw.get("freshness_state")).strip(),
            "metadata_only": bool(governance.get("metadata_only")),
            "contains_raw_private_data": bool(governance.get("contains_raw_private_data")),
            "writes_runtime_readback": bool(governance.get("writes_runtime_readback")),
            "marks_stage16_closed": bool(governance.get("marks_stage16_closed")),
        }

    return {
        "present": False,
        "evidence_root": str(root_real),
        "evidence_path": "",
        "status": "missing",
    }


def _latest_stage16_post_resume_evidence(*, latest_pre_sleep_evidence: dict[str, Any]) -> dict[str, Any]:
    evidence_root = _stage16_sleep_continuity_evidence_root()
    pre_sleep_path = _safe_str(latest_pre_sleep_evidence.get("evidence_path")).strip()
    continuity_record_id = _safe_str(latest_pre_sleep_evidence.get("continuity_record_id")).strip()
    if not bool(latest_pre_sleep_evidence.get("present")) or not continuity_record_id:
        return {
            "present": False,
            "evidence_root": str(evidence_root),
            "evidence_path": "",
            "status": "missing_pre_sleep_evidence",
            "linked_to_latest_pre_sleep": False,
            "conflict_detected": False,
        }
    if not evidence_root.exists() or not evidence_root.is_dir():
        return {
            "present": False,
            "evidence_root": str(evidence_root),
            "evidence_path": "",
            "status": "missing",
            "linked_to_latest_pre_sleep": False,
            "conflict_detected": False,
        }

    root_real = evidence_root.resolve()
    candidates = sorted(
        (path for path in evidence_root.glob("post_resume_*.json") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            resolved.relative_to(root_real)
            raw = json.loads(resolved.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(raw, dict):
            continue
        if _safe_str(raw.get("evidence_kind")).strip() != "stage16_sleep_continuity_post_resume":
            continue
        if _safe_str(raw.get("continuity_record_id")).strip() != continuity_record_id:
            continue
        governance = raw.get("governance") if isinstance(raw.get("governance"), dict) else {}
        raw_pre_path = _safe_str(raw.get("pre_sleep_evidence_path")).strip()
        linked_to_latest_pre_sleep = not raw_pre_path or raw_pre_path == pre_sleep_path
        return {
            "present": linked_to_latest_pre_sleep,
            "status": "post_resume_evidence_available" if linked_to_latest_pre_sleep else "pre_sleep_path_mismatch",
            "evidence_root": str(root_real),
            "evidence_path": str(resolved) if linked_to_latest_pre_sleep else "",
            "file_name": resolved.name if linked_to_latest_pre_sleep else "",
            "candidate_evidence_path": str(resolved),
            "candidate_file_name": resolved.name,
            "candidate_pre_sleep_evidence_path": raw_pre_path,
            "expected_pre_sleep_evidence_path": pre_sleep_path,
            "pre_sleep_evidence_path": raw_pre_path,
            "linked_to_latest_pre_sleep": linked_to_latest_pre_sleep,
            "conflict_detected": not linked_to_latest_pre_sleep,
            "stale_state_confusion_blocker": "post_resume_pre_sleep_path_mismatch"
            if not linked_to_latest_pre_sleep
            else "",
            "recorded_ts": int(raw.get("received_ts") or raw.get("recorded_ts") or 0),
            "continuity_record_id": _safe_str(raw.get("continuity_record_id")).strip(),
            "source_node_id": _safe_str(raw.get("source_node_id")).strip(),
            "paired_node_id": _safe_str(raw.get("paired_node_id")).strip(),
            "trace_id": _safe_str(raw.get("trace_id")).strip(),
            "authority_snapshot_id": _safe_str(raw.get("authority_snapshot_id")).strip(),
            "freshness_state": _safe_str(raw.get("freshness_state")).strip(),
            "operator_confirmed_sleep_resume": bool(raw.get("sleep_observed")) and bool(raw.get("resume_observed")),
            "continuity_available_after_resume": bool(raw.get("continuity_available_after_resume")),
            "metadata_only": bool(governance.get("metadata_only")),
            "contains_raw_private_data": bool(governance.get("contains_raw_private_data")),
            "writes_runtime_readback": bool(governance.get("writes_runtime_readback")),
            "marks_stage16_closed": bool(governance.get("marks_stage16_closed")),
        }

    return {
        "present": False,
        "evidence_root": str(root_real),
        "evidence_path": "",
        "status": "missing",
        "linked_to_latest_pre_sleep": False,
        "conflict_detected": False,
    }


def _stage16_sleep_continuity_runbook_steps(
    *,
    latest_pre_sleep_evidence: dict[str, Any],
    latest_post_resume_evidence: dict[str, Any],
) -> list[dict[str, Any]]:
    pre_sleep_path = _safe_str(latest_pre_sleep_evidence.get("evidence_path")).strip()
    pre_sleep_arg = f'"{pre_sleep_path}"' if pre_sleep_path else "<pre_sleep.json>"
    post_resume_path = _safe_str(latest_post_resume_evidence.get("evidence_path")).strip()
    post_resume_arg = f'"{post_resume_path}"' if post_resume_path else "<post_resume.json>"
    return [
        {
            "id": "capture_pre_sleep_evidence",
            "title": "Capture pre-sleep evidence",
            "command": "scripts/federation-stage16-sleep-continuity-evidence.ps1 -Mode PreSleep -CommitEvidence",
            "latest_evidence_path": pre_sleep_path,
            "expected_output": "pre-sleep evidence JSON path",
            "operator_action_required": True,
            "writes_evidence_when_run": True,
            "writes_receipts_when_run": False,
            "operator_confirmation_required": False,
        },
        {
            "id": "capture_post_resume_evidence",
            "title": "Capture post-resume evidence",
            "command": (
                "scripts/federation-stage16-sleep-continuity-evidence.ps1 -Mode PostResume -CommitEvidence "
                f"-PreSleepEvidencePath {pre_sleep_arg} -OperatorConfirmedSleepResume"
            ),
            "pre_sleep_evidence_path": pre_sleep_path,
            "pre_sleep_evidence_required": True,
            "pre_sleep_evidence_available": bool(latest_pre_sleep_evidence.get("present")),
            "expected_output": "post-resume evidence JSON path",
            "operator_action_required": True,
            "writes_evidence_when_run": True,
            "writes_receipts_when_run": False,
            "operator_confirmation_required": True,
        },
        {
            "id": "commit_sleep_continuity_readback",
            "title": "Commit sleep continuity runtime proof receipt",
            "command": (
                "scripts/federation-stage16-sleep-continuity-runtime-proof.ps1 -Mode Status -CommitReceipts "
                f"-PreSleepEvidencePath {pre_sleep_arg} -PostResumeEvidencePath {post_resume_arg}"
            ),
            "pre_sleep_evidence_path": pre_sleep_path,
            "post_resume_evidence_path": post_resume_path,
            "pre_sleep_evidence_required": True,
            "pre_sleep_evidence_available": bool(latest_pre_sleep_evidence.get("present")),
            "post_resume_evidence_required": True,
            "post_resume_evidence_available": bool(latest_post_resume_evidence.get("present")),
            "expected_output": "workstation_sleep_continuity_validated live runtime readback receipt",
            "operator_action_required": False,
            "writes_evidence_when_run": False,
            "writes_receipts_when_run": True,
            "operator_confirmation_required": False,
        },
        {
            "id": "record_operator_stage_closure_decision",
            "title": "Record operator Stage 16 closure decision after completion review is ready",
            "method": "POST",
            "route": "/federation/stage-closure-decision",
            "required_scope": _FEDERATION_STAGE16_CLOSURE_SCOPE,
            "payload_contract": {
                "actor": "operator or delegated builder actor with federation.stage16.closure.write",
                "decision": "close_stage16",
                "reason": "operator reviewed Stage 16 completion evidence",
            },
            "operator_action_required": True,
            "writes_evidence_when_run": False,
            "writes_receipts_when_run": True,
            "operator_confirmation_required": True,
        },
    ]


def stage16_sleep_continuity_runbook() -> dict[str, Any]:
    live_readbacks = live_runtime_readback_summary(limit=200)
    review = completion_review()
    closure = stage16_operator_stage_closure_decision_readback(limit=1)
    latest_pre_sleep_evidence = _latest_stage16_pre_sleep_evidence()
    latest_post_resume_evidence = _latest_stage16_post_resume_evidence(
        latest_pre_sleep_evidence=latest_pre_sleep_evidence
    )
    post_resume_evidence_conflict = bool(latest_post_resume_evidence.get("conflict_detected"))
    checks_by_id = {
        _safe_str(item.get("id")).strip(): item for item in live_readbacks.get("checks", []) if isinstance(item, dict)
    }
    prerequisite_ids = [
        "live_pairing_flow_observed",
        "live_selective_sync_observed",
        "live_remote_approval_roundtrip_observed",
        "live_revocation_roundtrip_observed",
    ]
    prerequisite_readbacks_ready = all(
        bool(checks_by_id.get(readback_id, {}).get("completion_evidence")) for readback_id in prerequisite_ids
    )
    sleep_check = checks_by_id.get("workstation_sleep_continuity_validated", {})
    sleep_continuity_ready = bool(sleep_check.get("completion_evidence"))
    ready_to_close = bool(review.get("ready_to_close"))
    stage16_closed_by_receipt = bool(closure.get("stage16_closed_by_receipt"))
    missing_readbacks = _parse_list(live_readbacks.get("missing_readbacks"))
    selected_action_summary = _stage16_sleep_continuity_status_action_summary(
        completion_review_blockers=_parse_list(review.get("blockers")),
        pre_sleep_evidence_ready=bool(latest_pre_sleep_evidence.get("present")),
        post_resume_evidence_ready=bool(latest_post_resume_evidence.get("present")),
        post_resume_evidence_conflict=post_resume_evidence_conflict,
        sleep_continuity_ready=sleep_continuity_ready,
        completion_ready=ready_to_close,
    )

    if stage16_closed_by_receipt:
        status_text = "stage16_closed_by_receipt"
        next_gap = "stage16_ledger_closure"
    elif ready_to_close:
        status_text = "ready_for_operator_stage_closure_decision"
        next_gap = "stage16_operator_stage_closure_decision"
    elif (
        prerequisite_readbacks_ready and bool(latest_post_resume_evidence.get("present")) and not sleep_continuity_ready
    ):
        status_text = "post_resume_evidence_ready"
        next_gap = _STAGE16_SLEEP_CONTINUITY_RUNTIME_READBACK_GAP
    elif prerequisite_readbacks_ready and post_resume_evidence_conflict and not sleep_continuity_ready:
        status_text = "post_resume_evidence_conflict"
        next_gap = _STAGE16_SLEEP_RESUME_CONFIRMATION_RECEIPT_GAP
    elif prerequisite_readbacks_ready and bool(latest_pre_sleep_evidence.get("present")) and not sleep_continuity_ready:
        status_text = "pre_sleep_evidence_ready"
        next_gap = _STAGE16_SLEEP_RESUME_CONFIRMATION_RECEIPT_GAP
    elif prerequisite_readbacks_ready and not sleep_continuity_ready:
        status_text = "ready_for_pre_sleep_evidence"
        next_gap = _STAGE16_SLEEP_CONTINUITY_PRE_SLEEP_EVIDENCE_GAP
    else:
        status_text = "blocked_on_prior_live_readbacks"
        next_gap = (
            _safe_str(live_readbacks.get("next_smallest_truthful_gap")).strip()
            or "stage16_live_federation_runtime_readback"
        )

    return {
        "ok": True,
        "kind": _FEDERATION_SLEEP_CONTINUITY_RUNBOOK_KIND,
        "stage": _STAGE16_FEDERATION_STAGE,
        "source_id": "federation",
        "status": status_text,
        "runbook_only": True,
        "prerequisite_readback_ids": prerequisite_ids,
        "prerequisite_readbacks_ready": prerequisite_readbacks_ready,
        "sleep_continuity_readback_id": "workstation_sleep_continuity_validated",
        "sleep_continuity_ready": sleep_continuity_ready,
        "sleep_continuity_check": sleep_check,
        "pre_sleep_evidence": latest_pre_sleep_evidence,
        "pre_sleep_evidence_ready": bool(latest_pre_sleep_evidence.get("present")),
        "post_resume_evidence": latest_post_resume_evidence,
        "post_resume_evidence_ready": bool(latest_post_resume_evidence.get("present")),
        "post_resume_evidence_conflict": post_resume_evidence_conflict,
        "ready_to_close": ready_to_close,
        "stage16_closed_by_receipt": stage16_closed_by_receipt,
        "missing_readbacks": missing_readbacks,
        "selected_action_summary": selected_action_summary,
        "current_readback": {
            "status": _safe_str(live_readbacks.get("status")).strip(),
            "ready_count": int(live_readbacks.get("ready_count") or 0),
            "required_count": int(live_readbacks.get("required_count") or 0),
            "missing_readbacks": missing_readbacks,
            "next_smallest_truthful_gap": _safe_str(live_readbacks.get("next_smallest_truthful_gap")).strip(),
        },
        "completion_review": {
            "status": _safe_str(review.get("status")).strip(),
            "ready_to_close": ready_to_close,
            "stage16_completion_review_ready": bool(review.get("stage16_completion_review_ready")),
            "live_runtime_readback_ready": bool(review.get("live_runtime_readback_ready")),
            "blockers": _parse_list(review.get("blockers")),
            "next_smallest_truthful_gap": _safe_str(review.get("next_smallest_truthful_gap")).strip(),
        },
        "stage_closure_decision": {
            "status": _safe_str(closure.get("status")).strip(),
            "receipt_readback_ready": bool(closure.get("receipt_readback_ready")),
            "stage16_closed_by_receipt": stage16_closed_by_receipt,
            "latest_receipt_id": _safe_str(closure.get("latest_receipt_id")).strip(),
        },
        "steps": _stage16_sleep_continuity_runbook_steps(
            latest_pre_sleep_evidence=latest_pre_sleep_evidence,
            latest_post_resume_evidence=latest_post_resume_evidence,
        ),
        "routes": _federation_routes(),
        "governance": {
            **_federation_governance(),
            "read_only": True,
            "runbook_only": True,
            "reads_pre_sleep_evidence_metadata": True,
            "reads_post_resume_evidence_metadata": True,
            "does_not_infer_sleep_from_delay": True,
            "operator_confirmation_required": True,
            "requires_explicit_sleep_resume_confirmation": True,
            "selected_action_summary_projected": True,
            "writes_evidence": False,
            "writes_receipts": False,
            "writes_registry": False,
            "writes_memory": False,
            "runs_tools": False,
            "runs_shell": False,
            "runs_git": False,
            "launches_browser": False,
            "captures_screen": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "marks_stage16_closed": False,
        },
        "writes_evidence": False,
        "writes_receipts": False,
        "writes_registry": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "marks_stage16_closed": False,
        "next_smallest_truthful_gap": next_gap,
    }


def _stage16_sleep_continuity_step(runbook: dict[str, Any], step_id: str) -> dict[str, Any]:
    steps = runbook.get("steps") if isinstance(runbook.get("steps"), list) else []
    for step in steps:
        if isinstance(step, dict) and _safe_str(step.get("id")).strip() == step_id:
            return step
    return {}


def _stage16_prior_live_readback_blockers(blockers: list[str]) -> list[str]:
    return [blocker for blocker in blockers if blocker != "workstation_sleep_continuity_validated"]


def _stage16_sleep_continuity_confirmation_requirements(step_id: str) -> list[str]:
    if step_id == "capture_post_resume_evidence":
        return [
            "operator_confirms_workstation_entered_sleep_or_suspend_after_pre_sleep_evidence",
            "operator_confirms_workstation_resumed_before_post_resume_capture",
            "pre_sleep_evidence_path_matches_latest_pre_sleep_artifact",
            "post_resume_capture_uses_operator_confirmed_sleep_resume_flag",
        ]
    if step_id == "record_operator_stage_closure_decision":
        return [
            "operator_reviewed_stage16_completion_evidence",
            "completion_review_ready_to_close",
            "stage16_closure_receipt_not_already_recorded",
        ]
    return []


def _powershell_single_quote(value: Any) -> str:
    return "'" + _safe_str(value).replace("'", "''") + "'"


def _stage16_sleep_resume_confirmation_command_projection(
    *,
    pre_sleep_evidence_path: str,
    ready: bool,
    actor: str = "",
) -> dict[str, Any]:
    actor_placeholder = f"<actor_with_{_FEDERATION_SLEEP_RESUME_CONFIRMATION_SCOPE}>"
    command_actor = _safe_str(actor).strip()
    command_actor_bound = bool(command_actor)
    command_actor_value = command_actor or actor_placeholder
    reason = "operator confirms physical sleep/suspend and resume after the pre-sleep marker"
    routes = _federation_routes()
    confirmation_uri = f"http://127.0.0.1:8000{routes['sleep_resume_confirmation']}"
    command = ""
    copyable_command = ""
    if ready:
        command = (
            "$body = @{ "
            f"actor = {_powershell_single_quote(command_actor_value)}; "
            f"reason = {_powershell_single_quote(reason)}; "
            "operator_confirmed_sleep_resume = $true; "
            f"pre_sleep_evidence_path = {_powershell_single_quote(pre_sleep_evidence_path)} "
            "} | ConvertTo-Json -Depth 6; "
            f"Invoke-RestMethod -Method Post -Uri {_powershell_single_quote(confirmation_uri)} "
            "-ContentType 'application/json' -Body $body"
        )
        copyable_command = f"Set-Location -LiteralPath {_powershell_single_quote(str(repo_root()))}; {command}"
    return {
        "confirmation_receipt_command_ready": ready,
        "confirmation_receipt_actor": _redacted_text(command_actor)[:240] if ready and command_actor_bound else "",
        "confirmation_receipt_actor_bound": ready and command_actor_bound,
        "confirmation_receipt_actor_placeholder": actor_placeholder if ready and not command_actor_bound else "",
        "confirmation_receipt_command": command,
        "confirmation_receipt_copyable_command": copyable_command,
        "confirmation_receipt_command_requires_scope": _FEDERATION_SLEEP_RESUME_CONFIRMATION_SCOPE,
        "confirmation_receipt_command_requires_actor_substitution": ready and not command_actor_bound,
        "confirmation_receipt_command_actor_scope": _FEDERATION_SLEEP_RESUME_CONFIRMATION_SCOPE if ready else "",
        "confirmation_receipt_actor_readiness_route": routes["sleep_resume_confirmation_actor_readiness"],
        "confirmation_receipt_actor_readiness_query_param": "actor",
        "confirmation_receipt_command_next_readback_route": routes["sleep_resume_confirmations"] if ready else "",
        "confirmation_receipt_command_receipt_id_readback_field": "latest_receipt_id" if ready else "",
        "confirmation_receipt_command_next_operator_step": (
            "refresh_sleep_resume_confirmations_for_current_receipt_id" if ready else ""
        ),
        "confirmation_receipt_command_records_receipt": ready,
        "confirmation_receipt_command_writes_evidence": False,
        "confirmation_receipt_command_marks_stage16_closed": False,
        "confirmation_receipt_command_projection_only": True,
    }


def _stage16_sleep_resume_confirmation_actor_is_placeholder(actor: str) -> bool:
    return _safe_str(actor).strip() == f"<actor_with_{_FEDERATION_SLEEP_RESUME_CONFIRMATION_SCOPE}>"


def _stage16_sleep_resume_confirmation_operator_steps(
    *,
    confirmation_command_ready: bool,
    receipt_backed_sequence_ready: bool,
    receipt_backed_sequence_command_field: str,
) -> list[dict[str, Any]]:
    routes = _federation_routes()
    readback_available = confirmation_command_ready or receipt_backed_sequence_ready
    return [
        {
            "id": "replace_actor_placeholder",
            "order": 1,
            "status": "ready" if confirmation_command_ready else "blocked",
            "command_field": "confirmation_receipt_copyable_command",
            "required_scope": _FEDERATION_SLEEP_RESUME_CONFIRMATION_SCOPE,
            "requires_actor_substitution": confirmation_command_ready,
            "requires_current_receipt": False,
            "writes_receipts_when_run": False,
            "writes_evidence_when_run": False,
            "marks_stage16_closed_when_run": False,
            "operator_action_required": confirmation_command_ready,
            "read_only_projection": True,
        },
        {
            "id": "write_sleep_resume_confirmation_receipt",
            "order": 2,
            "status": "ready" if confirmation_command_ready else "blocked",
            "method": "POST",
            "route": routes["sleep_resume_confirmation"],
            "command_field": "confirmation_receipt_copyable_command",
            "required_scope": _FEDERATION_SLEEP_RESUME_CONFIRMATION_SCOPE,
            "requires_actor_substitution": confirmation_command_ready,
            "requires_current_receipt": False,
            "writes_receipts_when_run": confirmation_command_ready,
            "writes_evidence_when_run": False,
            "marks_stage16_closed_when_run": False,
            "operator_action_required": confirmation_command_ready,
            "read_only_projection": True,
        },
        {
            "id": "refresh_sleep_resume_confirmation_readback",
            "order": 3,
            "status": "ready" if readback_available else "blocked",
            "method": "GET",
            "route": routes["sleep_resume_confirmations"],
            "readback_field": "latest_receipt_id",
            "requires_actor_substitution": False,
            "requires_current_receipt": False,
            "writes_receipts_when_run": False,
            "writes_evidence_when_run": False,
            "marks_stage16_closed_when_run": False,
            "operator_action_required": readback_available,
            "read_only_projection": True,
        },
        {
            "id": "run_receipt_backed_post_resume_sequence",
            "order": 4,
            "status": "ready" if receipt_backed_sequence_ready else "blocked_until_current_confirmation_receipt",
            "command_field": receipt_backed_sequence_command_field,
            "requires_actor_substitution": False,
            "requires_current_receipt": True,
            "required_readback_field": "latest_receipt_id",
            "writes_receipts_when_run": receipt_backed_sequence_ready,
            "writes_evidence_when_run": receipt_backed_sequence_ready,
            "marks_stage16_closed_when_run": False,
            "operator_action_required": receipt_backed_sequence_ready,
            "read_only_projection": True,
        },
    ]


def _stage16_sleep_continuity_selected_action_readiness(
    *,
    state: str,
    selected_step: dict[str, Any],
    prior_live_blockers: list[str],
    pre_sleep_evidence_ready: bool,
    post_resume_evidence_ready: bool,
    post_resume_evidence_conflict: bool,
) -> dict[str, Any]:
    step_id = _safe_str(selected_step.get("id")).strip()
    command = _safe_str(selected_step.get("command")).strip()
    operator_confirmation_required = bool(selected_step.get("operator_confirmation_required"))
    run_blockers: list[str] = []
    remaining_evidence_gates: list[str] = []
    met_conditions: list[str] = []
    command_validation: list[str] = []
    command_validation_blockers: list[str] = []

    if command:
        command_validation.append("selected_command_projected")
    else:
        command_validation_blockers.append("selected_command_missing")
    if prior_live_blockers:
        command_validation_blockers.extend(f"prior_live_readback_missing:{blocker}" for blocker in prior_live_blockers)

    if prior_live_blockers:
        run_blockers.extend(f"prior_live_readback_missing:{blocker}" for blocker in prior_live_blockers)
    if step_id == "capture_pre_sleep_evidence":
        if pre_sleep_evidence_ready:
            met_conditions.append("pre_sleep_evidence_already_available")
        else:
            remaining_evidence_gates.append("pre_sleep_evidence_missing")
        if "-Mode PreSleep" in command and "-CommitEvidence" in command:
            command_validation.append("pre_sleep_evidence_capture_command_bound")
        else:
            command_validation_blockers.append("pre_sleep_evidence_capture_command_missing")
        status = "ready_to_capture_pre_sleep_evidence" if not run_blockers else "blocked_on_prior_live_readbacks"
    elif step_id == "capture_post_resume_evidence":
        if pre_sleep_evidence_ready:
            met_conditions.append("pre_sleep_evidence_available")
            if "-PreSleepEvidencePath" in command:
                command_validation.append("latest_pre_sleep_evidence_path_bound")
            else:
                command_validation_blockers.append("latest_pre_sleep_evidence_path_missing")
        else:
            run_blockers.append("pre_sleep_evidence_missing")
            command_validation_blockers.append("pre_sleep_evidence_missing")
        if "-OperatorConfirmedSleepResume" in command:
            met_conditions.append("selected_command_requires_operator_confirmed_sleep_resume_flag")
            command_validation.append("operator_confirmed_sleep_resume_flag_bound")
        else:
            run_blockers.append("operator_confirmed_sleep_resume_flag_missing")
            command_validation_blockers.append("operator_confirmed_sleep_resume_flag_missing")
        if "-Mode PostResume" in command and "-CommitEvidence" in command:
            command_validation.append("post_resume_evidence_capture_command_bound")
        else:
            command_validation_blockers.append("post_resume_evidence_capture_command_missing")
        if operator_confirmation_required:
            run_blockers.append("operator_confirmed_sleep_resume_missing")
        if post_resume_evidence_ready:
            met_conditions.append("post_resume_evidence_available")
        elif post_resume_evidence_conflict:
            remaining_evidence_gates.append("post_resume_evidence_pre_sleep_path_mismatch")
        else:
            remaining_evidence_gates.append("post_resume_evidence_missing")
        status = "waiting_for_operator_confirmation" if run_blockers else "ready_to_capture_post_resume_evidence"
    elif step_id == "commit_sleep_continuity_readback":
        if pre_sleep_evidence_ready:
            met_conditions.append("pre_sleep_evidence_available")
            if "-PreSleepEvidencePath" in command:
                command_validation.append("pre_sleep_evidence_path_bound")
            else:
                command_validation_blockers.append("pre_sleep_evidence_path_missing")
        else:
            run_blockers.append("pre_sleep_evidence_missing")
            command_validation_blockers.append("pre_sleep_evidence_missing")
        if post_resume_evidence_ready:
            met_conditions.append("post_resume_evidence_available")
            if "-PostResumeEvidencePath" in command:
                command_validation.append("post_resume_evidence_path_bound")
            else:
                command_validation_blockers.append("post_resume_evidence_path_missing")
        else:
            run_blockers.append("post_resume_evidence_missing")
            command_validation_blockers.append("post_resume_evidence_missing")
        if "-CommitReceipts" in command:
            command_validation.append("runtime_receipt_commit_command_bound")
        else:
            command_validation_blockers.append("runtime_receipt_commit_command_missing")
        status = "ready_to_commit_sleep_continuity_readback" if not run_blockers else "blocked_on_missing_evidence"
    elif step_id == "record_operator_stage_closure_decision":
        if operator_confirmation_required:
            run_blockers.append("operator_stage_closure_decision_required")
        if selected_step.get("method") == "POST" and selected_step.get("route") == "/federation/stage-closure-decision":
            command_validation.append("stage_closure_route_bound")
        else:
            command_validation_blockers.append("stage_closure_route_missing")
        status = "waiting_for_operator_stage_closure_decision" if run_blockers else "ready_to_record_stage_closure"
    else:
        status = state or "blocked"

    ready_to_run = not run_blockers
    return {
        "status": status,
        "ready_to_run": ready_to_run,
        "run_blockers": run_blockers,
        "remaining_evidence_gates": remaining_evidence_gates,
        "met_conditions": met_conditions,
        "operator_terminal_command_ready": bool(command_validation) and not command_validation_blockers,
        "command_validation": command_validation,
        "command_validation_blockers": command_validation_blockers,
        "next_operator_step": "operator_recapture_post_resume_evidence_for_latest_pre_sleep"
        if step_id == "capture_post_resume_evidence" and post_resume_evidence_conflict
        else "operator_confirm_sleep_resume_then_capture_post_resume_evidence"
        if step_id == "capture_post_resume_evidence" and run_blockers
        else _safe_str(selected_step.get("title")).strip(),
        "selected_step_id": step_id,
        "pre_sleep_evidence_ready": pre_sleep_evidence_ready,
        "post_resume_evidence_ready": post_resume_evidence_ready,
        "post_resume_evidence_conflict": post_resume_evidence_conflict,
        "operator_confirmation_required": operator_confirmation_required,
        "writes_evidence_when_run": bool(selected_step.get("writes_evidence_when_run")),
        "writes_receipts_when_run": bool(selected_step.get("writes_receipts_when_run")),
    }


def _stage16_sleep_continuity_operator_terminal_invocation(
    *,
    selected_step: dict[str, Any],
    selected_action_readiness: dict[str, Any],
    confirmation_requirements: list[str],
) -> dict[str, Any]:
    command = _safe_str(selected_step.get("command")).strip()
    step_id = _safe_str(selected_step.get("id")).strip()
    working_directory = str(repo_root())
    command_ready = bool(selected_action_readiness.get("operator_terminal_command_ready"))
    ready_to_run = bool(selected_action_readiness.get("ready_to_run"))
    run_blockers = _parse_list(selected_action_readiness.get("run_blockers"))
    operator_confirmation_required = bool(selected_step.get("operator_confirmation_required"))
    operator_confirmation_pending = (
        command_ready
        and operator_confirmation_required
        and "operator_confirmed_sleep_resume_missing" in run_blockers
        and not ready_to_run
    )
    if not command_ready:
        status = "command_not_ready_for_operator_terminal"
    elif operator_confirmation_pending:
        status = "command_waiting_for_operator_confirmation"
    elif not ready_to_run:
        status = "command_waiting_on_readiness"
    else:
        status = "command_ready_for_operator_terminal"
    return {
        "status": status,
        "shell": "powershell",
        "working_directory": working_directory,
        "command": command,
        "copyable_command": f"Set-Location -LiteralPath {_powershell_single_quote(working_directory)}; {command}"
        if command
        else "",
        "selected_step_id": step_id,
        "operator_confirmation_required": operator_confirmation_required,
        "operator_confirmation_pending": operator_confirmation_pending,
        "copyable_after_operator_confirmation": operator_confirmation_pending,
        "should_not_run_before_confirmation": operator_confirmation_pending,
        "must_run_after_sleep_resume": step_id == "capture_post_resume_evidence",
        "preconditions": confirmation_requirements,
        "command_validation": _parse_list(selected_action_readiness.get("command_validation")),
        "command_validation_blockers": _parse_list(selected_action_readiness.get("command_validation_blockers")),
        "run_blockers": run_blockers,
        "ready_to_run": ready_to_run,
        "operator_terminal_command_ready": command_ready,
        "manual_execution_writes_evidence": bool(selected_step.get("writes_evidence_when_run")),
        "manual_execution_writes_receipts": bool(selected_step.get("writes_receipts_when_run")),
        "projection_only": True,
        "projection_runs_shell": False,
        "projection_writes_evidence": False,
        "projection_writes_receipts": False,
        "projection_grants_authority": False,
    }


def _stage16_sleep_continuity_operator_sleep_resume_gate(
    *,
    selected_step: dict[str, Any],
    selected_action_readiness: dict[str, Any],
    latest_pre_sleep_evidence: dict[str, Any],
    latest_post_resume_evidence: dict[str, Any],
    confirmation_requirements: list[str],
) -> dict[str, Any]:
    step_id = _safe_str(selected_step.get("id")).strip()
    pre_sleep_recorded_ts = int(latest_pre_sleep_evidence.get("recorded_ts") or 0)
    pre_sleep_age_seconds = max(0, _now_s() - pre_sleep_recorded_ts) if pre_sleep_recorded_ts > 0 else 0
    run_blockers = _parse_list(selected_action_readiness.get("run_blockers"))
    non_confirmation_blockers = [
        blocker for blocker in run_blockers if blocker != "operator_confirmed_sleep_resume_missing"
    ]
    confirmation_required = step_id == "capture_post_resume_evidence"
    pre_sleep_present = bool(latest_pre_sleep_evidence.get("present"))
    post_resume_present = bool(latest_post_resume_evidence.get("present"))
    post_resume_conflict = bool(latest_post_resume_evidence.get("conflict_detected"))
    operator_terminal_command_ready = bool(selected_action_readiness.get("operator_terminal_command_ready"))
    current_ready_to_run = bool(selected_action_readiness.get("ready_to_run"))
    operator_confirmation_blocker_present = "operator_confirmed_sleep_resume_missing" in run_blockers
    ready_after_operator_confirmation = (
        confirmation_required
        and pre_sleep_present
        and operator_terminal_command_ready
        and not non_confirmation_blockers
    )
    operator_confirmation_pending = (
        confirmation_required
        and operator_confirmation_blocker_present
        and ready_after_operator_confirmation
        and not current_ready_to_run
    )
    if not confirmation_required:
        status = "sleep_resume_confirmation_not_required_for_selected_step"
    elif ready_after_operator_confirmation:
        status = "waiting_for_operator_sleep_resume_confirmation"
    else:
        status = "blocked_before_operator_sleep_resume_confirmation"

    return {
        "status": status,
        "selected_step_id": step_id,
        "confirmation_required": confirmation_required,
        "required_confirmation_requirements": confirmation_requirements,
        "confirmation_blocker": "operator_confirmed_sleep_resume_missing" if confirmation_required else "",
        "operator_confirmation_blocker_present": operator_confirmation_blocker_present,
        "operator_confirmation_pending": operator_confirmation_pending,
        "current_ready_to_run": current_ready_to_run,
        "pre_sleep_evidence_present": pre_sleep_present,
        "pre_sleep_evidence_path": _safe_str(latest_pre_sleep_evidence.get("evidence_path")).strip(),
        "pre_sleep_file_name": _safe_str(latest_pre_sleep_evidence.get("file_name")).strip(),
        "pre_sleep_recorded_ts": pre_sleep_recorded_ts,
        "pre_sleep_age_seconds": pre_sleep_age_seconds,
        "pre_sleep_freshness_state": _safe_str(latest_pre_sleep_evidence.get("freshness_state")).strip(),
        "continuity_record_id": _safe_str(latest_pre_sleep_evidence.get("continuity_record_id")).strip(),
        "trace_id": _safe_str(latest_pre_sleep_evidence.get("trace_id")).strip(),
        "post_resume_evidence_present": post_resume_present,
        "post_resume_evidence_status": _safe_str(latest_post_resume_evidence.get("status")).strip(),
        "post_resume_evidence_conflict": post_resume_conflict,
        "post_resume_candidate_evidence_path": _safe_str(
            latest_post_resume_evidence.get("candidate_evidence_path")
        ).strip(),
        "expected_pre_sleep_evidence_path": _safe_str(
            latest_post_resume_evidence.get("expected_pre_sleep_evidence_path")
        ).strip(),
        "candidate_pre_sleep_evidence_path": _safe_str(
            latest_post_resume_evidence.get("candidate_pre_sleep_evidence_path")
        ).strip(),
        "must_sleep_after_pre_sleep_recorded_ts": confirmation_required,
        "must_resume_before_post_resume_capture": confirmation_required,
        "post_resume_capture_allowed_after_operator_confirmation": ready_after_operator_confirmation,
        "post_confirmation_ready_to_capture": ready_after_operator_confirmation,
        "sleep_resume_confirmation_is_current_blocker": operator_confirmation_pending,
        "operator_terminal_command_ready": operator_terminal_command_ready,
        "ready_after_operator_confirmation": ready_after_operator_confirmation,
        "elapsed_time_is_not_confirmation": True,
        "does_not_infer_sleep_from_delay": True,
        "projection_only": True,
        "projection_runs_shell": False,
        "projection_writes_evidence": False,
        "projection_writes_receipts": False,
        "projection_marks_stage16_closed": False,
    }


def _stage16_sleep_continuity_operator_confirmation_handoff(
    *,
    selected_step: dict[str, Any],
    operator_terminal_invocation: dict[str, Any],
    operator_sleep_resume_gate: dict[str, Any],
    confirmation_requirements: list[str],
) -> dict[str, Any]:
    step_id = _safe_str(selected_step.get("id")).strip()
    confirmation_required = bool(operator_sleep_resume_gate.get("confirmation_required"))
    operator_confirmation_pending = bool(operator_sleep_resume_gate.get("operator_confirmation_pending"))
    ready_after_confirmation = bool(operator_sleep_resume_gate.get("ready_after_operator_confirmation"))
    if operator_confirmation_pending:
        status = "waiting_for_operator_sleep_resume_confirmation"
    elif confirmation_required:
        status = "operator_confirmation_not_currently_runnable"
    else:
        status = "operator_confirmation_not_required_for_selected_step"
    copyable_command = _safe_str(operator_terminal_invocation.get("copyable_command")).strip()
    pre_sleep_evidence_path = _safe_str(operator_sleep_resume_gate.get("pre_sleep_evidence_path")).strip()
    pre_sleep_arg = f'"{pre_sleep_evidence_path}"' if pre_sleep_evidence_path else "<pre_sleep.json>"
    routes = _federation_routes()
    sequence_command = (
        "scripts/federation-stage16-sleep-continuity-post-resume-sequence.ps1 -Mode Run "
        f"-CommitEvidence -CommitReceipts -PreSleepEvidencePath {pre_sleep_arg} -OperatorConfirmedSleepResume"
    )
    receipt_id_placeholder = "<confirmation_receipt_id>"
    receipt_backed_sequence_command = (
        f"{sequence_command} -RequireConfirmationReceipt -ConfirmationReceiptId {receipt_id_placeholder}"
    )
    sequence_copyable_command = (
        f"Set-Location -LiteralPath {_powershell_single_quote(str(repo_root()))}; {sequence_command}"
    )
    receipt_backed_sequence_copyable_command = (
        f"Set-Location -LiteralPath {_powershell_single_quote(str(repo_root()))}; {receipt_backed_sequence_command}"
    )
    confirmation_reason = "operator confirms physical sleep/suspend and resume after the pre-sleep marker"
    confirmation_command = _stage16_sleep_resume_confirmation_command_projection(
        pre_sleep_evidence_path=pre_sleep_evidence_path,
        ready=ready_after_confirmation and step_id == "capture_post_resume_evidence",
    )
    confirmation_operator_steps = _stage16_sleep_resume_confirmation_operator_steps(
        confirmation_command_ready=bool(confirmation_command.get("confirmation_receipt_command_ready")),
        receipt_backed_sequence_ready=False,
        receipt_backed_sequence_command_field="post_resume_receipt_backed_sequence_copyable_command",
    )
    return {
        "status": status,
        "selected_step_id": step_id,
        "required_confirmation_requirements": confirmation_requirements,
        "operator_confirmation_source_required": "manual_operator_confirmation_after_physical_sleep_resume"
        if confirmation_required
        else "",
        "operator_confirmation_pending": operator_confirmation_pending,
        "confirmation_blocker": _safe_str(operator_sleep_resume_gate.get("confirmation_blocker")).strip(),
        "pre_sleep_evidence_path": pre_sleep_evidence_path,
        "pre_sleep_recorded_ts": int(operator_sleep_resume_gate.get("pre_sleep_recorded_ts") or 0),
        "must_sleep_after_pre_sleep_recorded_ts": bool(
            operator_sleep_resume_gate.get("must_sleep_after_pre_sleep_recorded_ts")
        ),
        "must_resume_before_post_resume_capture": bool(
            operator_sleep_resume_gate.get("must_resume_before_post_resume_capture")
        ),
        "post_resume_capture_command_ready_after_confirmation": ready_after_confirmation,
        "post_resume_capture_command": _safe_str(operator_terminal_invocation.get("command")).strip()
        if step_id == "capture_post_resume_evidence"
        else "",
        "post_resume_capture_copyable_command": copyable_command if step_id == "capture_post_resume_evidence" else "",
        "post_resume_sequence_available_after_confirmation": ready_after_confirmation,
        "post_resume_sequence_command": sequence_command if step_id == "capture_post_resume_evidence" else "",
        "post_resume_sequence_copyable_command": sequence_copyable_command
        if step_id == "capture_post_resume_evidence"
        else "",
        "post_resume_receipt_backed_sequence_command": receipt_backed_sequence_command
        if step_id == "capture_post_resume_evidence"
        else "",
        "post_resume_receipt_backed_sequence_copyable_command": receipt_backed_sequence_copyable_command
        if step_id == "capture_post_resume_evidence"
        else "",
        "post_resume_receipt_backed_sequence_requires_confirmation_receipt": confirmation_required
        and step_id == "capture_post_resume_evidence",
        "post_resume_receipt_backed_sequence_confirmation_receipt_id_placeholder": receipt_id_placeholder
        if step_id == "capture_post_resume_evidence"
        else "",
        "post_resume_sequence_writes_evidence_when_run": step_id == "capture_post_resume_evidence",
        "post_resume_sequence_writes_receipts_when_run": step_id == "capture_post_resume_evidence",
        "confirmation_receipt_route": routes["sleep_resume_confirmation"],
        "confirmation_receipt_readback_route": routes["sleep_resume_confirmations"],
        "confirmation_receipt_required_scope": _FEDERATION_SLEEP_RESUME_CONFIRMATION_SCOPE,
        "confirmation_receipt_payload_contract": {
            "actor": "operator or delegated builder actor with federation.stage16.sleep_resume.confirmation.write",
            "operator_confirmed_sleep_resume": True,
            "pre_sleep_evidence_path": pre_sleep_evidence_path,
            "reason": confirmation_reason,
        },
        **confirmation_command,
        "confirmation_receipt_operator_steps": confirmation_operator_steps,
        "confirmation_receipt_available_before_sequence": ready_after_confirmation,
        "confirmation_receipt_required_for_receipt_backed_workflow": confirmation_required,
        "confirmation_receipt_writes_receipts": True,
        "confirmation_receipt_writes_evidence": False,
        "confirmation_receipt_marks_stage16_closed": False,
        "should_not_run_before_confirmation": bool(
            operator_terminal_invocation.get("should_not_run_before_confirmation")
        ),
        "operator_terminal_command_ready": bool(operator_terminal_invocation.get("operator_terminal_command_ready")),
        "readback_routes": {
            "status": routes["status"],
            "sleep_continuity_action": routes["sleep_continuity_action"],
            "sleep_continuity_runbook": routes["sleep_continuity_runbook"],
            "sleep_resume_confirmations": routes["sleep_resume_confirmations"],
            "completion_review": routes["completion_review"],
        },
        "proof_boundary": {
            "projection_only": True,
            "requires_manual_operator_confirmation": confirmation_required,
            "does_not_infer_sleep_from_delay": True,
            "does_not_run_shell": True,
            "does_not_write_evidence": True,
            "does_not_write_receipts": True,
            "does_not_mark_stage16_closed": True,
            "does_not_grant_authority": True,
            "confirmation_receipt_command_projection_only": True,
            "receipt_backed_sequence_requires_confirmation_receipt": confirmation_required
            and step_id == "capture_post_resume_evidence",
        },
    }


def _stage16_sleep_continuity_after_manual_execution_readback(
    *,
    selected_step: dict[str, Any],
    selected_action_readiness: dict[str, Any],
) -> dict[str, Any]:
    step_id = _safe_str(selected_step.get("id")).strip()
    routes = _federation_routes()
    ready_to_run = bool(selected_action_readiness.get("ready_to_run"))
    run_blockers = _parse_list(selected_action_readiness.get("run_blockers"))
    operator_confirmation_pending = (
        bool(selected_step.get("operator_confirmation_required"))
        and "operator_confirmed_sleep_resume_missing" in run_blockers
        and not ready_to_run
    )
    if not step_id:
        status = "no_selected_manual_execution"
    elif operator_confirmation_pending:
        status = "manual_execution_waiting_for_operator_confirmation"
    elif not ready_to_run:
        status = "manual_execution_not_ready"
    else:
        status = "manual_execution_projection_ready"
    base = {
        "status": status,
        "selected_step_id": step_id,
        "expected_output": _safe_str(selected_step.get("expected_output")).strip(),
        "operator_terminal_command_ready": bool(selected_action_readiness.get("operator_terminal_command_ready")),
        "ready_to_run": ready_to_run,
        "run_blockers": run_blockers,
        "operator_confirmation_pending": operator_confirmation_pending,
        "should_not_expect_success_before_confirmation": operator_confirmation_pending,
        "refresh_routes": {
            "status": routes["status"],
            "sleep_continuity_runbook": routes["sleep_continuity_runbook"],
            "sleep_continuity_action": routes["sleep_continuity_action"],
            "completion_review": routes["completion_review"],
        },
        "manual_execution_writes_evidence": bool(selected_step.get("writes_evidence_when_run")),
        "manual_execution_writes_receipts": bool(selected_step.get("writes_receipts_when_run")),
        "projection_only": True,
        "projection_runs_shell": False,
        "projection_writes_evidence": False,
        "projection_writes_receipts": False,
        "projection_marks_stage16_closed": False,
    }
    if step_id == "capture_post_resume_evidence":
        return {
            **base,
            "expected_artifact_root": str(_stage16_sleep_continuity_evidence_root()),
            "expected_artifact_prefix": "post_resume_",
            "expected_artifact_kind": "stage16_sleep_continuity_post_resume",
            "expected_status_after_success": "post_resume_evidence_ready",
            "expected_action_status_after_success": "run_sleep_continuity_runtime_proof",
            "expected_selected_step_id_after_success": "commit_sleep_continuity_readback",
            "expected_next_step_after_success": "run_sleep_continuity_runtime_proof_with_committed_evidence",
        }
    if step_id == "commit_sleep_continuity_readback":
        return {
            **base,
            "expected_artifact_root": str(data_dir() / "logs" / "federation"),
            "expected_artifact_prefix": "live_runtime_readback",
            "expected_artifact_kind": "francis.stage16.federation.live_runtime_readback_receipt",
            "expected_status_after_success": "validated",
            "expected_action_status_after_success": "record_stage16_closure_decision",
            "expected_selected_step_id_after_success": "record_operator_stage_closure_decision",
            "expected_next_step_after_success": "record_operator_stage_closure_decision_after_completion_review",
        }
    return {
        **base,
        "expected_artifact_root": "",
        "expected_artifact_prefix": "",
        "expected_artifact_kind": "",
        "expected_status_after_success": "",
        "expected_action_status_after_success": "",
        "expected_selected_step_id_after_success": "",
        "expected_next_step_after_success": "",
    }


def _stage16_sleep_continuity_status_action_summary(
    *,
    completion_review_blockers: list[str],
    pre_sleep_evidence_ready: bool,
    post_resume_evidence_ready: bool,
    post_resume_evidence_conflict: bool,
    sleep_continuity_ready: bool,
    completion_ready: bool,
) -> dict[str, Any]:
    selected_action_id = ""
    current_ready_to_run = False
    operator_confirmation_pending = False
    post_confirmation_ready_to_capture = False
    confirmation_blocker = ""
    blocked_reason = ""

    if sleep_continuity_ready and completion_ready:
        selected_action_id = "record_operator_stage_closure_decision"
        blocked_reason = "operator_stage_closure_decision_required"
    elif post_resume_evidence_ready and not sleep_continuity_ready:
        selected_action_id = "commit_sleep_continuity_readback"
        current_ready_to_run = True
    elif (pre_sleep_evidence_ready or post_resume_evidence_conflict) and not sleep_continuity_ready:
        selected_action_id = "capture_post_resume_evidence"
        operator_confirmation_pending = pre_sleep_evidence_ready
        post_confirmation_ready_to_capture = pre_sleep_evidence_ready
        confirmation_blocker = "operator_confirmed_sleep_resume_missing" if pre_sleep_evidence_ready else ""
        blocked_reason = confirmation_blocker or "pre_sleep_evidence_missing"
    elif completion_review_blockers == ["workstation_sleep_continuity_validated"]:
        selected_action_id = "capture_pre_sleep_evidence"
        current_ready_to_run = True
    else:
        blocked_reason = "prior_live_readback_missing"

    return {
        "selected_action_id": selected_action_id,
        "current_ready_to_run": current_ready_to_run,
        "operator_confirmation_pending": operator_confirmation_pending,
        "post_confirmation_ready_to_capture": post_confirmation_ready_to_capture,
        "sleep_resume_confirmation_is_current_blocker": operator_confirmation_pending,
        "confirmation_blocker": confirmation_blocker,
        "blocked_reason": blocked_reason,
    }


def stage16_sleep_continuity_action() -> dict[str, Any]:
    runbook = stage16_sleep_continuity_runbook()
    blockers = _parse_list(runbook.get("missing_readbacks"))
    prior_live_blockers = _stage16_prior_live_readback_blockers(blockers)
    pre_sleep_evidence_ready = bool(runbook.get("pre_sleep_evidence_ready"))
    post_resume_evidence_ready = bool(runbook.get("post_resume_evidence_ready"))
    post_resume_evidence_conflict = bool(runbook.get("post_resume_evidence_conflict"))
    sleep_continuity_ready = bool(runbook.get("sleep_continuity_ready"))
    ready_to_close = bool(runbook.get("ready_to_close"))
    stage16_closed_by_receipt = bool(runbook.get("stage16_closed_by_receipt"))

    state = "blocked_on_prior_live_readbacks"
    selected_step: dict[str, Any] = {}
    if stage16_closed_by_receipt:
        state = "stage16_closed"
    elif prior_live_blockers:
        state = "blocked_on_prior_live_readbacks"
    elif ready_to_close:
        state = "record_stage16_closure_decision"
        selected_step = _stage16_sleep_continuity_step(runbook, "record_operator_stage_closure_decision")
    elif post_resume_evidence_ready:
        state = "run_sleep_continuity_runtime_proof"
        selected_step = _stage16_sleep_continuity_step(runbook, "commit_sleep_continuity_readback")
    elif pre_sleep_evidence_ready:
        state = "capture_post_resume_evidence"
        selected_step = _stage16_sleep_continuity_step(runbook, "capture_post_resume_evidence")
    elif blockers == ["workstation_sleep_continuity_validated"] or runbook.get("status") in {
        "ready_for_operator_sleep_resume",
        "ready_for_pre_sleep_evidence",
    }:
        state = "capture_pre_sleep_evidence"
        selected_step = _stage16_sleep_continuity_step(runbook, "capture_pre_sleep_evidence")
    selected_step_id = _safe_str(selected_step.get("id")).strip()
    confirmation_requirements = _stage16_sleep_continuity_confirmation_requirements(selected_step_id)
    selected_action_readiness = _stage16_sleep_continuity_selected_action_readiness(
        state=state,
        selected_step=selected_step,
        prior_live_blockers=prior_live_blockers,
        pre_sleep_evidence_ready=pre_sleep_evidence_ready,
        post_resume_evidence_ready=post_resume_evidence_ready,
        post_resume_evidence_conflict=post_resume_evidence_conflict,
    )
    operator_terminal_invocation = _stage16_sleep_continuity_operator_terminal_invocation(
        selected_step=selected_step,
        selected_action_readiness=selected_action_readiness,
        confirmation_requirements=confirmation_requirements,
    )
    operator_sleep_resume_gate = _stage16_sleep_continuity_operator_sleep_resume_gate(
        selected_step=selected_step,
        selected_action_readiness=selected_action_readiness,
        latest_pre_sleep_evidence=runbook.get("pre_sleep_evidence")
        if isinstance(runbook.get("pre_sleep_evidence"), dict)
        else {},
        latest_post_resume_evidence=runbook.get("post_resume_evidence")
        if isinstance(runbook.get("post_resume_evidence"), dict)
        else {},
        confirmation_requirements=confirmation_requirements,
    )
    operator_confirmation_handoff = _stage16_sleep_continuity_operator_confirmation_handoff(
        selected_step=selected_step,
        operator_terminal_invocation=operator_terminal_invocation,
        operator_sleep_resume_gate=operator_sleep_resume_gate,
        confirmation_requirements=confirmation_requirements,
    )
    after_manual_execution_readback = _stage16_sleep_continuity_after_manual_execution_readback(
        selected_step=selected_step,
        selected_action_readiness=selected_action_readiness,
    )
    current_ready_to_run = bool(selected_action_readiness.get("ready_to_run"))
    operator_confirmation_pending = any(
        bool(readback.get("operator_confirmation_pending"))
        for readback in (
            operator_terminal_invocation,
            operator_sleep_resume_gate,
            after_manual_execution_readback,
        )
    )
    post_confirmation_ready_to_capture = bool(operator_sleep_resume_gate.get("post_confirmation_ready_to_capture"))

    return {
        "ok": True,
        "kind": _FEDERATION_SLEEP_CONTINUITY_ACTION_KIND,
        "stage": _STAGE16_FEDERATION_STAGE,
        "source_id": "federation",
        "status": state,
        "action_projection_only": True,
        "selected_step_id": selected_step_id,
        "selected_step_title": _safe_str(selected_step.get("title")).strip(),
        "selected_action": selected_step,
        "primary_command": _safe_str(selected_step.get("command")).strip(),
        "primary_route": _safe_str(selected_step.get("route")).strip(),
        "method": _safe_str(selected_step.get("method")).strip(),
        "required_scope": _safe_str(selected_step.get("required_scope")).strip(),
        "expected_output": _safe_str(selected_step.get("expected_output")).strip(),
        "evidence_path": _safe_str(selected_step.get("latest_evidence_path")).strip(),
        "pre_sleep_evidence_path": _safe_str(selected_step.get("pre_sleep_evidence_path")).strip(),
        "post_resume_evidence_path": _safe_str(selected_step.get("post_resume_evidence_path")).strip(),
        "blockers": blockers,
        "prior_live_readback_blockers": prior_live_blockers,
        "pre_sleep_evidence_ready": pre_sleep_evidence_ready,
        "post_resume_evidence_ready": post_resume_evidence_ready,
        "post_resume_evidence_conflict": post_resume_evidence_conflict,
        "sleep_continuity_ready": sleep_continuity_ready,
        "ready_to_close": ready_to_close,
        "stage16_closed_by_receipt": stage16_closed_by_receipt,
        "operator_action_required": bool(selected_step.get("operator_action_required")),
        "operator_confirmation_required": bool(selected_step.get("operator_confirmation_required")),
        "operator_confirmation_requirements": confirmation_requirements,
        "current_ready_to_run": current_ready_to_run,
        "operator_confirmation_pending": operator_confirmation_pending,
        "post_confirmation_ready_to_capture": post_confirmation_ready_to_capture,
        "sleep_resume_confirmation_is_current_blocker": bool(
            operator_sleep_resume_gate.get("sleep_resume_confirmation_is_current_blocker")
        ),
        "selected_action_readiness": selected_action_readiness,
        "operator_terminal_invocation": operator_terminal_invocation,
        "operator_sleep_resume_gate": operator_sleep_resume_gate,
        "operator_confirmation_handoff": operator_confirmation_handoff,
        "after_manual_execution_readback": after_manual_execution_readback,
        "writes_evidence_when_run": bool(selected_step.get("writes_evidence_when_run")),
        "writes_receipts_when_run": bool(selected_step.get("writes_receipts_when_run")),
        "mutation_available_from_ui": False,
        "routes": _federation_routes(),
        "governance": {
            **_federation_governance(),
            "read_only": True,
            "action_projection_only": True,
            "uses_status_and_runbook_readbacks": True,
            "prior_live_readback_blockers_take_precedence": True,
            "does_not_infer_sleep_from_delay": True,
            "confirmation_requirements_projected": bool(confirmation_requirements),
            "selected_action_readiness_projected": True,
            "operator_terminal_invocation_projected": True,
            "operator_sleep_resume_gate_projected": True,
            "operator_confirmation_handoff_projected": True,
            "after_manual_execution_readback_projected": True,
            "does_not_run_selected_command": True,
            "does_not_post_selected_route": True,
            "writes_evidence": False,
            "writes_receipts": False,
            "writes_registry": False,
            "writes_memory": False,
            "runs_tools": False,
            "runs_shell": False,
            "runs_git": False,
            "launches_browser": False,
            "captures_screen": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "marks_stage16_closed": False,
        },
        "writes_evidence": False,
        "writes_receipts": False,
        "writes_registry": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "marks_stage16_closed": False,
        "next_smallest_truthful_gap": _safe_str(runbook.get("next_smallest_truthful_gap")).strip(),
    }


def _federation_deliverable(
    deliverable_id: str,
    summary: str,
    ready: bool,
    status: str,
    next_gap: str,
) -> dict[str, Any]:
    return {
        "id": deliverable_id,
        "summary": summary,
        "ready": ready,
        "status": status,
        "next_smallest_truthful_gap": next_gap,
    }


def _stage16_deliverables(
    *,
    pairing_contract_ready: bool,
    sync_model_contract_ready: bool,
    remote_approval_contract_ready: bool,
    revocation_contract_ready: bool,
    node_attributed_continuity_contract_ready: bool,
    stage15_closed: bool,
) -> list[dict[str, Any]]:
    return [
        _federation_deliverable(
            "stage15_ledger_closure_backstop",
            "Stage 15 Swarm closure receipt readback is present before federation topology expands",
            stage15_closed,
            "ready" if stage15_closed else "blocked",
            "stage15_ledger_closure",
        ),
        _federation_deliverable(
            "pairing_scoped_trust_contract",
            "Pairing and scoped trust are explicit, node-attributed, revocable, and read-only",
            pairing_contract_ready,
            "ready" if pairing_contract_ready else "pending",
            "stage16_pairing_scoped_trust_contract",
        ),
        _federation_deliverable(
            "sync_model",
            "Selective replication model is allowlist-only, encrypted, scoped, and stale-state aware",
            sync_model_contract_ready,
            "ready" if sync_model_contract_ready else "pending",
            "stage16_sync_model_contract",
        ),
        _federation_deliverable(
            "remote_approval_support",
            "Remote approval support is receipt-referenced, traceable, and cannot impersonate the operator",
            remote_approval_contract_ready,
            "ready" if remote_approval_contract_ready else "pending",
            "stage16_remote_approval_support",
        ),
        _federation_deliverable(
            "revocation_surfaces",
            "Revocation contract is explicit, receipt-bound, scoped, and propagated before reuse",
            revocation_contract_ready,
            "ready" if revocation_contract_ready else "pending",
            "stage16_revocation_surfaces",
        ),
        _federation_deliverable(
            "node_attributed_continuity",
            "Continuity records are node-attributed, freshness-badged, redacted, and trace-linked",
            node_attributed_continuity_contract_ready,
            "ready" if node_attributed_continuity_contract_ready else "pending",
            "stage16_node_attributed_continuity",
        ),
    ]


def pairing_scoped_trust_contract() -> dict[str, Any]:
    stage15 = swarm_stage15_operator_stage_closure_decision_readback(limit=5)
    stage15_closed = bool(stage15.get("stage15_closed_by_receipt"))
    pairing_states = [
        "unpaired",
        "pairing_requested",
        "paired",
        "degraded",
        "revoked",
    ]
    required_pairing_fields = [
        "pairing_request_id",
        "local_node_id",
        "remote_node_id",
        "remote_public_key_fingerprint",
        "requested_scopes",
        "operator_approval_receipt_id",
        "expiry_policy",
        "revocation_route",
    ]
    scoped_trust_levels = [
        {
            "id": "presence",
            "allows": ["health_presence", "capability_inventory"],
            "disallows": ["raw_private_data", "approval_decisions", "execution_authority"],
        },
        {
            "id": "continuity_summary",
            "allows": ["redacted_continuity_summary", "trace_metadata"],
            "disallows": ["raw_memory_body", "secrets", "unscoped_replication"],
        },
        {
            "id": "approval_relay",
            "allows": ["approval_request_metadata", "decision_receipt_reference"],
            "disallows": ["operator_impersonation", "silent_approval", "authority_expansion"],
        },
    ]
    selective_replication = {
        "allowed_classes": [
            "node_identity",
            "health_presence",
            "capability_inventory",
            "redacted_continuity_summary",
            "trace_metadata",
            "approval_request_metadata",
            "decision_receipt_reference",
        ],
        "blocked_classes": [
            "raw_private_data",
            "raw_prompt_body",
            "raw_model_response",
            "secrets",
            "credential_material",
            "raw_memory_body",
            "execution_tokens",
            "operator_unredacted_payloads",
        ],
    }
    invariants = {
        "stage15_swarm_closed_before_federation": stage15_closed,
        "pairing_is_explicit_not_ambient": True,
        "trust_is_scoped_not_global": True,
        "trust_is_revocable": True,
        "node_identity_is_required": True,
        "trace_lineage_is_preserved": True,
        "remote_approval_cannot_impersonate_operator": True,
        "raw_private_data_does_not_replicate_by_default": True,
        "federation_does_not_expand_authority": True,
        "cloud_vagueness_is_rejected": True,
    }
    contract_ready = (
        stage15_closed
        and len(pairing_states) == 5
        and len(required_pairing_fields) == 8
        and len(scoped_trust_levels) == 3
        and all(bool(value) for value in invariants.values())
    )
    return {
        "ok": True,
        "kind": _FEDERATION_PAIRING_SCOPED_TRUST_CONTRACT_KIND,
        "stage": _STAGE16_FEDERATION_STAGE,
        "source_id": "federation",
        "status": "ready" if contract_ready else "blocked",
        "stage15_closed_by_receipt": stage15_closed,
        "stage15_latest_closure_receipt_id": _safe_str(stage15.get("latest_receipt_id")).strip(),
        "pairing_scoped_trust_contract_ready": contract_ready,
        "pairing_states": pairing_states,
        "required_pairing_fields": required_pairing_fields,
        "scoped_trust_levels": scoped_trust_levels,
        "selective_replication": selective_replication,
        "invariants": invariants,
        "routes": _federation_routes(),
        "governance": _federation_governance(),
        "writes_registry": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "next_smallest_truthful_gap": "stage16_sync_model_contract"
        if contract_ready
        else "stage15_ledger_closure"
        if not stage15_closed
        else "stage16_pairing_scoped_trust_contract",
    }


def sync_model_contract() -> dict[str, Any]:
    pairing = pairing_scoped_trust_contract()
    pairing_ready = bool(pairing.get("pairing_scoped_trust_contract_ready"))
    selective_replication = (
        pairing.get("selective_replication") if isinstance(pairing.get("selective_replication"), dict) else {}
    )
    sync_lanes = [
        {
            "id": "presence",
            "allowed_classes": ["node_identity", "health_presence", "capability_inventory"],
            "consistency": "eventual",
            "max_staleness_seconds": 300,
            "requires_encryption": True,
            "requires_node_scope": True,
        },
        {
            "id": "continuity_summary",
            "allowed_classes": ["redacted_continuity_summary", "trace_metadata"],
            "consistency": "eventual_with_stale_badge",
            "max_staleness_seconds": 900,
            "requires_encryption": True,
            "requires_node_scope": True,
        },
        {
            "id": "approval_relay_metadata",
            "allowed_classes": ["approval_request_metadata", "decision_receipt_reference"],
            "consistency": "receipt_ordered",
            "max_staleness_seconds": 120,
            "requires_encryption": True,
            "requires_node_scope": True,
        },
        {
            "id": "shared_knowledge_index",
            "allowed_classes": ["shared_knowledge_metadata", "source_instance_id", "domain", "tags"],
            "consistency": "eventual",
            "max_staleness_seconds": 1800,
            "requires_encryption": True,
            "requires_node_scope": True,
        },
    ]
    replication_rules = {
        "allowlist_only": True,
        "per_node_scope_required": True,
        "pairing_contract_required": True,
        "encryption_required": True,
        "node_attribution_required": True,
        "trace_lineage_required": True,
        "operator_receipt_reference_required_for_approval_relay": True,
        "raw_private_data_replication_allowed": False,
        "raw_memory_body_replication_allowed": False,
        "credential_material_replication_allowed": False,
        "execution_token_replication_allowed": False,
        "unscoped_sync_allowed": False,
        "ambient_cloud_sync_allowed": False,
    }
    conflict_policy = {
        "silent_overwrite_allowed": False,
        "node_attributed_conflicts_required": True,
        "authority_or_approval_conflict_requires_operator_review": True,
        "stale_continuity_must_be_badged": True,
        "receipt_order_preserved": True,
        "deadletter_unmergeable_conflicts": True,
    }
    staleness_policy = {
        "source_node_id_required": True,
        "source_recorded_ts_required": True,
        "received_ts_required": True,
        "stale_badge_required": True,
        "stale_state_cannot_imply_current_authority": True,
        "workstation_sleep_continuity_requires_fresh_readback": True,
    }
    invariants = {
        "pairing_scoped_trust_contract_ready": pairing_ready,
        "sync_is_selective_not_sync_everything": True,
        "sync_is_encrypted_by_default": True,
        "sync_is_node_scoped": True,
        "sync_preserves_trace_lineage": True,
        "sync_preserves_node_attribution": True,
        "raw_private_data_is_blocked": "raw_private_data" in _parse_list(selective_replication.get("blocked_classes")),
        "raw_memory_body_is_blocked": "raw_memory_body" in _parse_list(selective_replication.get("blocked_classes")),
        "secrets_are_blocked": "secrets" in _parse_list(selective_replication.get("blocked_classes")),
        "stale_state_cannot_expand_authority": True,
    }
    replication_rules_observed = (
        bool(replication_rules["allowlist_only"])
        and bool(replication_rules["per_node_scope_required"])
        and bool(replication_rules["pairing_contract_required"])
        and bool(replication_rules["encryption_required"])
        and bool(replication_rules["node_attribution_required"])
        and bool(replication_rules["trace_lineage_required"])
        and bool(replication_rules["operator_receipt_reference_required_for_approval_relay"])
        and not bool(replication_rules["raw_private_data_replication_allowed"])
        and not bool(replication_rules["raw_memory_body_replication_allowed"])
        and not bool(replication_rules["credential_material_replication_allowed"])
        and not bool(replication_rules["execution_token_replication_allowed"])
        and not bool(replication_rules["unscoped_sync_allowed"])
        and not bool(replication_rules["ambient_cloud_sync_allowed"])
    )
    conflict_policy_observed = (
        not bool(conflict_policy["silent_overwrite_allowed"])
        and bool(conflict_policy["node_attributed_conflicts_required"])
        and bool(conflict_policy["authority_or_approval_conflict_requires_operator_review"])
        and bool(conflict_policy["stale_continuity_must_be_badged"])
        and bool(conflict_policy["receipt_order_preserved"])
        and bool(conflict_policy["deadletter_unmergeable_conflicts"])
    )
    contract_ready = (
        pairing_ready
        and len(sync_lanes) == 4
        and all(bool(lane.get("requires_encryption")) for lane in sync_lanes)
        and all(bool(lane.get("requires_node_scope")) for lane in sync_lanes)
        and replication_rules_observed
        and conflict_policy_observed
        and all(bool(value) for value in staleness_policy.values())
        and all(bool(value) for value in invariants.values())
    )
    return {
        "ok": True,
        "kind": _FEDERATION_SYNC_MODEL_CONTRACT_KIND,
        "stage": _STAGE16_FEDERATION_STAGE,
        "source_id": "federation",
        "status": "ready" if contract_ready else "blocked",
        "stage15_closed_by_receipt": bool(pairing.get("stage15_closed_by_receipt")),
        "stage15_latest_closure_receipt_id": _safe_str(pairing.get("stage15_latest_closure_receipt_id")).strip(),
        "pairing_scoped_trust_contract_ready": pairing_ready,
        "sync_model_contract_ready": contract_ready,
        "sync_lanes": sync_lanes,
        "replication_rules": replication_rules,
        "conflict_policy": conflict_policy,
        "staleness_policy": staleness_policy,
        "invariants": invariants,
        "routes": _federation_routes(),
        "governance": _federation_governance(),
        "sync_execution_enabled": False,
        "writes_registry": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "next_smallest_truthful_gap": "stage16_remote_approval_support"
        if contract_ready
        else _safe_str(pairing.get("next_smallest_truthful_gap")).strip() or "stage16_pairing_scoped_trust_contract",
    }


def remote_approval_contract() -> dict[str, Any]:
    sync = sync_model_contract()
    sync_ready = bool(sync.get("sync_model_contract_ready"))
    request_envelope_fields = [
        "remote_approval_request_id",
        "source_node_id",
        "paired_node_id",
        "target_operator_id",
        "requested_action",
        "requested_scope",
        "trace_id",
        "parent_receipt_id",
        "sync_lane_id",
        "recorded_ts",
        "expires_at",
    ]
    decision_receipt_fields = [
        "decision_receipt_id",
        "remote_approval_request_id",
        "decision",
        "decision_actor",
        "decision_authority",
        "decision_recorded_ts",
        "source_node_id",
        "paired_node_id",
        "trace_id",
        "parent_receipt_id",
    ]
    allowed_request_classes = [
        "approval_request_metadata",
        "decision_receipt_reference",
        "denial_receipt_reference",
        "trace_metadata",
        "node_identity",
    ]
    blocked_request_classes = [
        "raw_private_payload",
        "raw_prompt_body",
        "raw_model_response",
        "credential_material",
        "execution_tokens",
        "operator_unredacted_payloads",
        "remote_operator_impersonation",
    ]
    relay_states = [
        "queued",
        "delivered",
        "decided",
        "denied",
        "expired",
        "deadlettered",
    ]
    safety_rules = {
        "sync_model_contract_required": sync_ready,
        "operator_decision_receipt_required": True,
        "delegated_operator_receipt_allowed_if_governed": True,
        "remote_node_cannot_impersonate_operator": True,
        "remote_node_cannot_expand_scope": True,
        "remote_node_cannot_grant_execution_authority": True,
        "stale_request_must_expire": True,
        "denial_receipt_required_for_rejected_or_expired": True,
        "trace_id_required": True,
        "source_node_id_required": True,
        "paired_node_id_required": True,
    }
    governance_flags = {
        "remote_approval_execution_enabled": False,
        "request_metadata_only": True,
        "decision_receipt_reference_only": True,
        "raw_payload_replication_allowed": False,
        "silent_approval_allowed": False,
        "operator_impersonation_allowed": False,
        "approval_scope_expansion_allowed": False,
    }
    safety_rules_observed = (
        bool(safety_rules["sync_model_contract_required"])
        and bool(safety_rules["operator_decision_receipt_required"])
        and bool(safety_rules["delegated_operator_receipt_allowed_if_governed"])
        and bool(safety_rules["remote_node_cannot_impersonate_operator"])
        and bool(safety_rules["remote_node_cannot_expand_scope"])
        and bool(safety_rules["remote_node_cannot_grant_execution_authority"])
        and bool(safety_rules["stale_request_must_expire"])
        and bool(safety_rules["denial_receipt_required_for_rejected_or_expired"])
        and bool(safety_rules["trace_id_required"])
        and bool(safety_rules["source_node_id_required"])
        and bool(safety_rules["paired_node_id_required"])
    )
    governance_observed = (
        not bool(governance_flags["remote_approval_execution_enabled"])
        and bool(governance_flags["request_metadata_only"])
        and bool(governance_flags["decision_receipt_reference_only"])
        and not bool(governance_flags["raw_payload_replication_allowed"])
        and not bool(governance_flags["silent_approval_allowed"])
        and not bool(governance_flags["operator_impersonation_allowed"])
        and not bool(governance_flags["approval_scope_expansion_allowed"])
    )
    contract_ready = (
        sync_ready
        and len(request_envelope_fields) == 11
        and len(decision_receipt_fields) == 10
        and len(relay_states) == 6
        and "approval_request_metadata" in allowed_request_classes
        and "decision_receipt_reference" in allowed_request_classes
        and "remote_operator_impersonation" in blocked_request_classes
        and safety_rules_observed
        and governance_observed
    )
    return {
        "ok": True,
        "kind": _FEDERATION_REMOTE_APPROVAL_CONTRACT_KIND,
        "stage": _STAGE16_FEDERATION_STAGE,
        "source_id": "federation",
        "status": "ready" if contract_ready else "blocked",
        "stage15_closed_by_receipt": bool(sync.get("stage15_closed_by_receipt")),
        "stage15_latest_closure_receipt_id": _safe_str(sync.get("stage15_latest_closure_receipt_id")).strip(),
        "pairing_scoped_trust_contract_ready": bool(sync.get("pairing_scoped_trust_contract_ready")),
        "sync_model_contract_ready": sync_ready,
        "remote_approval_contract_ready": contract_ready,
        "request_envelope_fields": request_envelope_fields,
        "decision_receipt_fields": decision_receipt_fields,
        "allowed_request_classes": allowed_request_classes,
        "blocked_request_classes": blocked_request_classes,
        "relay_states": relay_states,
        "safety_rules": safety_rules,
        "governance_flags": governance_flags,
        "routes": _federation_routes(),
        "governance": _federation_governance(),
        "remote_approval_execution_enabled": False,
        "writes_registry": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "next_smallest_truthful_gap": "stage16_revocation_surfaces"
        if contract_ready
        else _safe_str(sync.get("next_smallest_truthful_gap")).strip() or "stage16_sync_model_contract",
    }


def revocation_contract() -> dict[str, Any]:
    remote = remote_approval_contract()
    remote_ready = bool(remote.get("remote_approval_contract_ready"))
    revocation_request_fields = [
        "revocation_id",
        "pairing_request_id",
        "source_node_id",
        "paired_node_id",
        "revoked_scope",
        "reason",
        "trace_id",
        "operator_receipt_id",
        "recorded_ts",
        "effective_ts",
    ]
    revocation_states = [
        "requested",
        "propagating",
        "revoked",
        "denied",
        "deadlettered",
    ]
    propagation_rules = {
        "operator_receipt_required": True,
        "per_node_scope_required": True,
        "revocation_before_reuse_required": True,
        "stale_pairing_reuse_blocked": True,
        "remote_approval_relays_must_stop_after_revocation": True,
        "sync_lanes_must_stop_after_revocation": True,
        "node_attributed_receipt_required": True,
        "trace_lineage_required": True,
        "subdelegation_allowed": False,
        "silent_reactivation_allowed": False,
        "authority_expansion_allowed": False,
    }
    denial_behavior = {
        "missing_operator_receipt": "deny_revocation_and_surface_receipt_gap",
        "unknown_pairing": "deadletter_unknown_pairing",
        "stale_pairing": "deny_reuse_and_require_repair",
        "scope_mismatch": "deny_and_surface_scope_mismatch",
        "propagation_failure": "deadletter_and_keep_scope_revoked_locally",
    }
    propagation_observed = (
        bool(propagation_rules["operator_receipt_required"])
        and bool(propagation_rules["per_node_scope_required"])
        and bool(propagation_rules["revocation_before_reuse_required"])
        and bool(propagation_rules["stale_pairing_reuse_blocked"])
        and bool(propagation_rules["remote_approval_relays_must_stop_after_revocation"])
        and bool(propagation_rules["sync_lanes_must_stop_after_revocation"])
        and bool(propagation_rules["node_attributed_receipt_required"])
        and bool(propagation_rules["trace_lineage_required"])
        and not bool(propagation_rules["subdelegation_allowed"])
        and not bool(propagation_rules["silent_reactivation_allowed"])
        and not bool(propagation_rules["authority_expansion_allowed"])
    )
    contract_ready = (
        remote_ready
        and len(revocation_request_fields) == 10
        and len(revocation_states) == 5
        and propagation_observed
        and len(denial_behavior) == 5
    )
    return {
        "ok": True,
        "kind": _FEDERATION_REVOCATION_CONTRACT_KIND,
        "stage": _STAGE16_FEDERATION_STAGE,
        "source_id": "federation",
        "status": "ready" if contract_ready else "blocked",
        "stage15_closed_by_receipt": bool(remote.get("stage15_closed_by_receipt")),
        "stage15_latest_closure_receipt_id": _safe_str(remote.get("stage15_latest_closure_receipt_id")).strip(),
        "remote_approval_contract_ready": remote_ready,
        "revocation_contract_ready": contract_ready,
        "revocation_request_fields": revocation_request_fields,
        "revocation_states": revocation_states,
        "propagation_rules": propagation_rules,
        "denial_behavior": denial_behavior,
        "routes": _federation_routes(),
        "governance": _federation_governance(),
        "revocation_execution_enabled": False,
        "writes_registry": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "next_smallest_truthful_gap": "stage16_node_attributed_continuity"
        if contract_ready
        else _safe_str(remote.get("next_smallest_truthful_gap")).strip() or "stage16_remote_approval_support",
    }


def node_attributed_continuity_contract() -> dict[str, Any]:
    revocation = revocation_contract()
    revocation_ready = bool(revocation.get("revocation_contract_ready"))
    continuity_record_fields = [
        "continuity_record_id",
        "source_node_id",
        "source_node_role",
        "paired_node_id",
        "sync_lane_id",
        "trace_id",
        "parent_receipt_id",
        "source_recorded_ts",
        "received_ts",
        "freshness_state",
        "redaction_summary",
        "authority_snapshot_id",
    ]
    freshness_states = [
        "fresh",
        "stale",
        "revoked",
        "conflicted",
        "deadlettered",
    ]
    continuity_rules = {
        "source_node_id_required": True,
        "paired_node_id_required": True,
        "trace_id_required": True,
        "parent_receipt_required": True,
        "freshness_badge_required": True,
        "redaction_summary_required": True,
        "authority_snapshot_required": True,
        "revoked_links_cannot_present_current_state": True,
        "stale_state_cannot_imply_current_authority": True,
        "raw_private_data_allowed": False,
        "node_ambiguous_receipts_allowed": False,
    }
    handback_policy = {
        "operator_visible_node_source": True,
        "operator_visible_freshness": True,
        "operator_visible_trace": True,
        "operator_visible_redaction": True,
        "hidden_federation_source_allowed": False,
    }
    continuity_rules_observed = (
        bool(continuity_rules["source_node_id_required"])
        and bool(continuity_rules["paired_node_id_required"])
        and bool(continuity_rules["trace_id_required"])
        and bool(continuity_rules["parent_receipt_required"])
        and bool(continuity_rules["freshness_badge_required"])
        and bool(continuity_rules["redaction_summary_required"])
        and bool(continuity_rules["authority_snapshot_required"])
        and bool(continuity_rules["revoked_links_cannot_present_current_state"])
        and bool(continuity_rules["stale_state_cannot_imply_current_authority"])
        and not bool(continuity_rules["raw_private_data_allowed"])
        and not bool(continuity_rules["node_ambiguous_receipts_allowed"])
    )
    handback_policy_observed = (
        bool(handback_policy["operator_visible_node_source"])
        and bool(handback_policy["operator_visible_freshness"])
        and bool(handback_policy["operator_visible_trace"])
        and bool(handback_policy["operator_visible_redaction"])
        and not bool(handback_policy["hidden_federation_source_allowed"])
    )
    contract_ready = (
        revocation_ready
        and len(continuity_record_fields) == 12
        and len(freshness_states) == 5
        and continuity_rules_observed
        and handback_policy_observed
    )
    return {
        "ok": True,
        "kind": _FEDERATION_NODE_CONTINUITY_CONTRACT_KIND,
        "stage": _STAGE16_FEDERATION_STAGE,
        "source_id": "federation",
        "status": "ready" if contract_ready else "blocked",
        "stage15_closed_by_receipt": bool(revocation.get("stage15_closed_by_receipt")),
        "stage15_latest_closure_receipt_id": _safe_str(revocation.get("stage15_latest_closure_receipt_id")).strip(),
        "revocation_contract_ready": revocation_ready,
        "node_attributed_continuity_contract_ready": contract_ready,
        "continuity_record_fields": continuity_record_fields,
        "freshness_states": freshness_states,
        "continuity_rules": continuity_rules,
        "handback_policy": handback_policy,
        "routes": _federation_routes(),
        "governance": _federation_governance(),
        "continuity_sync_execution_enabled": False,
        "writes_registry": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "next_smallest_truthful_gap": "stage16_completion_review"
        if contract_ready
        else _safe_str(revocation.get("next_smallest_truthful_gap")).strip() or "stage16_revocation_surfaces",
    }


def completion_review() -> dict[str, Any]:
    pairing = pairing_scoped_trust_contract()
    sync = sync_model_contract()
    remote = remote_approval_contract()
    revocation = revocation_contract()
    node_continuity = node_attributed_continuity_contract()
    live_readbacks = live_runtime_readback_summary(limit=200)
    latest_live_checks = {
        _safe_str(item.get("id")).strip(): item for item in live_readbacks.get("checks", []) if isinstance(item, dict)
    }
    contract_checks = [
        {
            "id": "stage15_ledger_closure_backstop",
            "passed": bool(pairing.get("stage15_closed_by_receipt")),
            "status": "passed" if bool(pairing.get("stage15_closed_by_receipt")) else "blocked",
            "evidence": _safe_str(pairing.get("stage15_latest_closure_receipt_id")).strip(),
        },
        {
            "id": "pairing_scoped_trust_contract_ready",
            "passed": bool(pairing.get("pairing_scoped_trust_contract_ready")),
            "status": "passed" if bool(pairing.get("pairing_scoped_trust_contract_ready")) else "blocked",
            "evidence": "/federation/pairing-scoped-trust-contract",
        },
        {
            "id": "sync_model_contract_ready",
            "passed": bool(sync.get("sync_model_contract_ready")),
            "status": "passed" if bool(sync.get("sync_model_contract_ready")) else "blocked",
            "evidence": "/federation/sync-model-contract",
        },
        {
            "id": "remote_approval_contract_ready",
            "passed": bool(remote.get("remote_approval_contract_ready")),
            "status": "passed" if bool(remote.get("remote_approval_contract_ready")) else "blocked",
            "evidence": "/federation/remote-approval-contract",
        },
        {
            "id": "revocation_contract_ready",
            "passed": bool(revocation.get("revocation_contract_ready")),
            "status": "passed" if bool(revocation.get("revocation_contract_ready")) else "blocked",
            "evidence": "/federation/revocation-contract",
        },
        {
            "id": "node_attributed_continuity_contract_ready",
            "passed": bool(node_continuity.get("node_attributed_continuity_contract_ready")),
            "status": "passed" if bool(node_continuity.get("node_attributed_continuity_contract_ready")) else "blocked",
            "evidence": "/federation/node-attributed-continuity-contract",
        },
    ]
    live_checks = [
        latest_live_checks.get("live_pairing_flow_observed", {}),
        latest_live_checks.get("live_selective_sync_observed", {}),
        latest_live_checks.get("live_remote_approval_roundtrip_observed", {}),
        latest_live_checks.get("live_revocation_roundtrip_observed", {}),
        latest_live_checks.get("workstation_sleep_continuity_validated", {}),
    ]
    contract_ready = all(bool(item.get("passed")) for item in contract_checks)
    live_ready = all(bool(item.get("passed")) for item in live_checks)
    ready_to_close = contract_ready and live_ready
    blockers = [item["id"] for item in live_checks if not bool(item.get("passed"))]
    return {
        "ok": True,
        "kind": _FEDERATION_COMPLETION_REVIEW_KIND,
        "stage": _STAGE16_FEDERATION_STAGE,
        "source_id": "federation",
        "status": "ready" if ready_to_close else "blocked",
        "stage15_closed_by_receipt": bool(pairing.get("stage15_closed_by_receipt")),
        "stage15_latest_closure_receipt_id": _safe_str(pairing.get("stage15_latest_closure_receipt_id")).strip(),
        "contract_readiness_ready": contract_ready,
        "live_runtime_readback_ready": live_ready,
        "stage16_completion_review_ready": ready_to_close,
        "ready_to_close": ready_to_close,
        "stage_closure_decision_required": ready_to_close,
        "contract_checks": contract_checks,
        "live_checks": live_checks,
        "live_runtime_readbacks": {
            "status": _safe_str(live_readbacks.get("status")).strip(),
            "count": int(live_readbacks.get("count") or 0),
            "ready_count": int(live_readbacks.get("ready_count") or 0),
            "required_count": int(live_readbacks.get("required_count") or 0),
            "missing_readbacks": _parse_list(live_readbacks.get("missing_readbacks")),
        },
        "blockers": blockers,
        "ready_count": sum(1 for item in contract_checks if bool(item.get("passed"))),
        "required_count": len(contract_checks),
        "live_ready_count": sum(1 for item in live_checks if bool(item.get("passed"))),
        "live_required_count": len(live_checks),
        "done_criteria": {
            "workstation_sleep_does_not_destroy_continuity": bool(
                latest_live_checks.get("workstation_sleep_continuity_validated", {}).get("passed")
            ),
            "remote_approval_is_safe_and_traceable": bool(
                latest_live_checks.get("live_remote_approval_roundtrip_observed", {}).get("passed")
            ),
            "raw_private_data_does_not_leak_across_nodes": contract_ready,
            "multi_device_francis_feels_like_one_governed_system": live_ready,
        },
        "routes": _federation_routes(),
        "governance": {
            **_federation_governance(),
            "completion_review_only": True,
            "does_not_mark_stage_closed": True,
            "requires_live_runtime_readback": True,
            "stage_closure_decision_required": ready_to_close,
        },
        "writes_registry": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "next_smallest_truthful_gap": "stage16_operator_stage_closure_decision"
        if ready_to_close
        else _safe_str(live_readbacks.get("next_smallest_truthful_gap")).strip()
        or "stage16_live_federation_runtime_readback",
    }


@router.get("/status")
def status() -> dict[str, Any]:
    try:
        registry = _load_registry()
        instances_obj = registry.get("instances") if isinstance(registry.get("instances"), dict) else {}
        instances = [
            _normalize_instance(_safe_str(instance_id), item)
            for instance_id, item in instances_obj.items()
            if isinstance(item, dict)
        ]
        online = len([i for i in instances if _safe_str(i.get("status")).strip().lower() == "online"])
        degraded = len([i for i in instances if _safe_str(i.get("status")).strip().lower() == "degraded"])
        pairing_contract = pairing_scoped_trust_contract()
        pairing_ready = bool(pairing_contract.get("pairing_scoped_trust_contract_ready"))
        sync_contract = sync_model_contract()
        sync_ready = bool(sync_contract.get("sync_model_contract_ready"))
        remote_approval = remote_approval_contract()
        remote_approval_ready = bool(remote_approval.get("remote_approval_contract_ready"))
        revocation = revocation_contract()
        revocation_ready = bool(revocation.get("revocation_contract_ready"))
        node_continuity = node_attributed_continuity_contract()
        node_continuity_ready = bool(node_continuity.get("node_attributed_continuity_contract_ready"))
        review = completion_review()
        completion_ready = bool(review.get("stage16_completion_review_ready"))
        completion_next_gap = (
            _safe_str(review.get("next_smallest_truthful_gap")).strip() or "stage16_live_federation_runtime_readback"
        )
        closure_readback = stage16_operator_stage_closure_decision_readback(limit=1)
        stage16_closed_by_receipt = bool(closure_readback.get("stage16_closed_by_receipt"))
        latest_pre_sleep_evidence = _latest_stage16_pre_sleep_evidence()
        latest_post_resume_evidence = _latest_stage16_post_resume_evidence(
            latest_pre_sleep_evidence=latest_pre_sleep_evidence
        )
        pre_sleep_evidence_ready = bool(latest_pre_sleep_evidence.get("present"))
        post_resume_evidence_ready = bool(latest_post_resume_evidence.get("present"))
        post_resume_evidence_conflict = bool(latest_post_resume_evidence.get("conflict_detected"))
        completion_review_blockers = _parse_list(review.get("blockers"))
        sleep_continuity_ready = bool(
            _meta(review.get("done_criteria")).get("workstation_sleep_does_not_destroy_continuity")
        )
        sleep_continuity_status = (
            "validated"
            if sleep_continuity_ready
            else "post_resume_evidence_ready"
            if post_resume_evidence_ready
            else "post_resume_evidence_conflict"
            if post_resume_evidence_conflict
            else "pre_sleep_evidence_ready"
            if pre_sleep_evidence_ready
            else "ready_for_pre_sleep_evidence"
            if completion_review_blockers == ["workstation_sleep_continuity_validated"]
            else "blocked_on_prior_live_readbacks"
            if "workstation_sleep_continuity_validated" in completion_review_blockers
            else "not_applicable"
        )
        sleep_continuity_action_summary = _stage16_sleep_continuity_status_action_summary(
            completion_review_blockers=completion_review_blockers,
            pre_sleep_evidence_ready=pre_sleep_evidence_ready,
            post_resume_evidence_ready=post_resume_evidence_ready,
            post_resume_evidence_conflict=post_resume_evidence_conflict,
            sleep_continuity_ready=sleep_continuity_ready,
            completion_ready=completion_ready,
        )
        stage15_closed = bool(pairing_contract.get("stage15_closed_by_receipt"))
        deliverables = _stage16_deliverables(
            pairing_contract_ready=pairing_ready,
            sync_model_contract_ready=sync_ready,
            remote_approval_contract_ready=remote_approval_ready,
            revocation_contract_ready=revocation_ready,
            node_attributed_continuity_contract_ready=node_continuity_ready,
            stage15_closed=stage15_closed,
        )
        return {
            "ok": True,
            "route": "federation",
            "status": "ready",
            "stage": _STAGE16_FEDERATION_STAGE,
            "stage16_status": "stage16_closed_by_receipt"
            if stage16_closed_by_receipt
            else "stage16_completion_review_ready"
            if completion_ready
            else "stage16_contracts_ready_completion_blocked"
            if node_continuity_ready
            else "stage16_revocation_contract_ready"
            if revocation_ready
            else "stage16_remote_approval_contract_ready"
            if remote_approval_ready
            else "stage16_sync_model_contract_ready"
            if sync_ready
            else "stage16_pairing_scoped_trust_contract_ready"
            if pairing_ready
            else "awaiting_stage15_ledger_closure"
            if not stage15_closed
            else "stage16_started",
            "stage15_closed_by_receipt": stage15_closed,
            "stage15_latest_closure_receipt_id": _safe_str(
                pairing_contract.get("stage15_latest_closure_receipt_id")
            ).strip(),
            "pairing_scoped_trust_contract_ready": pairing_ready,
            "sync_model_contract_ready": sync_ready,
            "remote_approval_contract_ready": remote_approval_ready,
            "revocation_contract_ready": revocation_ready,
            "node_attributed_continuity_contract_ready": node_continuity_ready,
            "stage16_completion_review_ready": completion_ready,
            "stage16_closed_by_receipt": stage16_closed_by_receipt,
            "latest_stage_closure_decision_receipt": closure_readback.get("latest_receipt", {}),
            "live_runtime_readback_ready": bool(review.get("live_runtime_readback_ready")),
            "completion_review_blockers": completion_review_blockers,
            "sleep_continuity_status": sleep_continuity_status,
            "sleep_continuity_ready": sleep_continuity_ready,
            "pre_sleep_evidence_ready": pre_sleep_evidence_ready,
            "post_resume_evidence_ready": post_resume_evidence_ready,
            "post_resume_evidence_conflict": post_resume_evidence_conflict,
            "latest_pre_sleep_evidence": latest_pre_sleep_evidence,
            "latest_post_resume_evidence": latest_post_resume_evidence,
            "sleep_continuity_selected_action_id": _safe_str(
                sleep_continuity_action_summary.get("selected_action_id")
            ).strip(),
            "sleep_continuity_action_current_ready_to_run": bool(
                sleep_continuity_action_summary.get("current_ready_to_run")
            ),
            "sleep_continuity_operator_confirmation_pending": bool(
                sleep_continuity_action_summary.get("operator_confirmation_pending")
            ),
            "sleep_continuity_post_confirmation_ready_to_capture": bool(
                sleep_continuity_action_summary.get("post_confirmation_ready_to_capture")
            ),
            "sleep_continuity_confirmation_blocker": _safe_str(
                sleep_continuity_action_summary.get("confirmation_blocker")
            ).strip(),
            "sleep_continuity_blocked_reason": _safe_str(sleep_continuity_action_summary.get("blocked_reason")).strip(),
            "sleep_continuity_sleep_resume_confirmation_is_current_blocker": bool(
                sleep_continuity_action_summary.get("sleep_resume_confirmation_is_current_blocker")
            ),
            "sleep_continuity_next_step": "record_stage16_operator_stage_closure_decision"
            if sleep_continuity_ready and completion_ready
            else "run_sleep_continuity_runtime_proof_with_committed_evidence"
            if post_resume_evidence_ready and not sleep_continuity_ready
            else "recapture_post_resume_evidence_for_latest_pre_sleep"
            if post_resume_evidence_conflict and pre_sleep_evidence_ready and not sleep_continuity_ready
            else "run_post_resume_evidence_with_operator_confirmation"
            if pre_sleep_evidence_ready and not sleep_continuity_ready
            else "capture_pre_sleep_evidence"
            if completion_review_blockers == ["workstation_sleep_continuity_validated"]
            else completion_next_gap,
            "ready_count": sum(1 for item in deliverables if bool(item.get("ready"))),
            "required_count": len(deliverables),
            "deliverables": deliverables,
            "routes": _federation_routes(),
            "governance": _federation_governance(),
            "next_smallest_truthful_gap": "stage16_ledger_closure"
            if stage16_closed_by_receipt
            else "stage16_operator_stage_closure_decision"
            if completion_ready
            else completion_next_gap
            if node_continuity_ready
            else "stage16_node_attributed_continuity"
            if revocation_ready
            else "stage16_revocation_surfaces"
            if remote_approval_ready
            else "stage16_remote_approval_support"
            if sync_ready
            else "stage16_sync_model_contract"
            if pairing_ready
            else "stage15_ledger_closure"
            if not stage15_closed
            else "stage16_pairing_scoped_trust_contract",
            "ts": _now_s(),
            "counts": {
                "instances": len(instances),
                "online": online,
                "degraded": degraded,
                "delegations": len(registry.get("delegations") or []),
                "consensus_logs": len(registry.get("consensus_logs") or []),
                "shared_knowledge": len(registry.get("shared_knowledge") or []),
            },
        }
    except Exception as exc:
        return {"ok": False, "route": "federation", "status": "error", "error": api_error_message(exc)}


@router.get("/health")
def health() -> dict[str, Any]:
    body = status()
    body["route"] = "federation.health"
    return body


@router.get("/pairing-scoped-trust-contract")
def get_pairing_scoped_trust_contract() -> dict[str, Any]:
    return pairing_scoped_trust_contract()


@router.get("/sync-model-contract")
def get_sync_model_contract() -> dict[str, Any]:
    return sync_model_contract()


@router.get("/remote-approval-contract")
def get_remote_approval_contract() -> dict[str, Any]:
    return remote_approval_contract()


@router.get("/revocation-contract")
def get_revocation_contract() -> dict[str, Any]:
    return revocation_contract()


@router.get("/node-attributed-continuity-contract")
def get_node_attributed_continuity_contract() -> dict[str, Any]:
    return node_attributed_continuity_contract()


@router.get("/completion-review")
def get_completion_review() -> dict[str, Any]:
    return completion_review()


@router.get("/sleep-continuity-runbook")
def get_sleep_continuity_runbook() -> dict[str, Any]:
    return stage16_sleep_continuity_runbook()


@router.get("/sleep-continuity-action")
def get_sleep_continuity_action() -> dict[str, Any]:
    return stage16_sleep_continuity_action()


@router.get("/sleep-resume-confirmations")
def get_sleep_resume_confirmations(limit: int = 20) -> dict[str, Any]:
    return stage16_sleep_resume_confirmation_readback(limit=limit)


@router.get("/sleep-resume-confirmation/actor-readiness")
def get_sleep_resume_confirmation_actor_readiness(actor: str = "") -> dict[str, Any]:
    return stage16_sleep_resume_confirmation_actor_readiness(actor)


@router.post("/sleep-resume-confirmation")
def post_sleep_resume_confirmation(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    route = "/federation/sleep-resume-confirmation"
    actor = _federation_write_actor(payload)
    if _stage16_sleep_resume_confirmation_actor_is_placeholder(actor):
        return {
            "ok": False,
            "kind": "francis.stage16.federation.sleep_resume_operator_confirmation.record",
            "status": "denied",
            "error": "confirmation_receipt_actor_placeholder_must_be_replaced",
            "source_id": "federation",
            "target": "stage16_sleep_continuity",
            "actor": actor,
            "actor_placeholder": actor,
            "required_scope": _FEDERATION_SLEEP_RESUME_CONFIRMATION_SCOPE,
            "next_step": "replace_actor_placeholder_with_scoped_operator_or_delegated_builder_actor",
            "receipt": None,
            "receipt_id": "",
            "writes_receipt": False,
            "writes_evidence": False,
            "writes_runtime_readback": False,
            "marks_stage16_closed": False,
            "governance": {
                **_federation_governance(read_only=False),
                "required_scope": _FEDERATION_SLEEP_RESUME_CONFIRMATION_SCOPE,
                "route": str(request.url.path),
                "placeholder_actor_rejected": True,
                "requires_real_scoped_actor": True,
                "does_not_write_receipt_on_denial": True,
                "does_not_write_evidence": True,
                "does_not_write_runtime_readback": True,
                "does_not_mark_stage16_closed": True,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
            "next_smallest_truthful_gap": _STAGE16_SLEEP_RESUME_CONFIRMATION_ACTOR_GAP,
        }
    permission = _federation_write_permission(
        actor,
        route=route,
        method=request.method,
        required_scope=_FEDERATION_SLEEP_RESUME_CONFIRMATION_SCOPE,
    )
    if not permission.allowed:
        return _permission_denied_for_scope(
            permission,
            required_scope=_FEDERATION_SLEEP_RESUME_CONFIRMATION_SCOPE,
            next_step="configure_sleep_resume_confirmation_write_scope_before_operator_confirmation",
        )

    action = stage16_sleep_continuity_action()
    if not _to_bool(payload.get("operator_confirmed_sleep_resume"), default=False):
        return {
            "ok": False,
            "kind": "francis.stage16.federation.sleep_resume_operator_confirmation.record",
            "status": "denied",
            "error": "operator_confirmed_sleep_resume_required",
            "source_id": "federation",
            "target": "stage16_sleep_continuity",
            "action": action,
            "receipt": None,
            "receipt_id": "",
            "writes_receipt": False,
            "writes_evidence": False,
            "writes_runtime_readback": False,
            "marks_stage16_closed": False,
            "governance": {
                **_federation_governance(read_only=False),
                "required_scope": _FEDERATION_SLEEP_RESUME_CONFIRMATION_SCOPE,
                "route": str(request.url.path),
                "explicit_operator_confirmation": True,
                "requires_true_operator_confirmed_sleep_resume": True,
                "does_not_infer_sleep_from_delay": True,
                "does_not_write_receipt_on_denial": True,
                "does_not_write_evidence": True,
                "does_not_write_runtime_readback": True,
                "does_not_mark_stage16_closed": True,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
            "next_smallest_truthful_gap": _STAGE16_SLEEP_RESUME_CONFIRMATION_RECEIPT_GAP,
        }

    sleep_gate = (
        action.get("operator_sleep_resume_gate") if isinstance(action.get("operator_sleep_resume_gate"), dict) else {}
    )
    current_pre_sleep_path = _safe_str(sleep_gate.get("pre_sleep_evidence_path")).strip()
    requested_pre_sleep_path = _safe_str(payload.get("pre_sleep_evidence_path")).strip()
    pre_sleep_path_matches = not requested_pre_sleep_path or requested_pre_sleep_path == current_pre_sleep_path
    action_pending = (
        _safe_str(action.get("selected_step_id")).strip() == "capture_post_resume_evidence"
        and bool(action.get("operator_confirmation_pending"))
        and bool(action.get("post_confirmation_ready_to_capture"))
        and bool(action.get("pre_sleep_evidence_ready"))
        and bool(sleep_gate.get("operator_confirmation_pending"))
        and current_pre_sleep_path != ""
    )
    if not action_pending or not pre_sleep_path_matches:
        return {
            "ok": True,
            "kind": "francis.stage16.federation.sleep_resume_operator_confirmation.record",
            "status": "blocked",
            "source_id": "federation",
            "target": "stage16_sleep_continuity",
            "action": action,
            "receipt": None,
            "receipt_id": "",
            "writes_receipt": False,
            "writes_evidence": False,
            "writes_runtime_readback": False,
            "marks_stage16_closed": False,
            "blockers": [
                blocker
                for blocker, present in (
                    ("sleep_resume_confirmation_not_current_selected_action", not action_pending),
                    ("pre_sleep_evidence_path_mismatch", not pre_sleep_path_matches),
                )
                if present
            ],
            "current_pre_sleep_evidence_path": current_pre_sleep_path,
            "requested_pre_sleep_evidence_path": requested_pre_sleep_path,
            "governance": {
                **_federation_governance(read_only=False),
                "required_scope": _FEDERATION_SLEEP_RESUME_CONFIRMATION_SCOPE,
                "route": str(request.url.path),
                "explicit_operator_confirmation": True,
                "requires_current_sleep_resume_action": True,
                "requires_pre_sleep_evidence_path_match": True,
                "does_not_write_receipt_when_not_current": True,
                "does_not_write_evidence": True,
                "does_not_write_runtime_readback": True,
                "does_not_mark_stage16_closed": True,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
            "next_smallest_truthful_gap": _STAGE16_SLEEP_RESUME_CONFIRMATION_RECEIPT_GAP,
        }

    receipt = record_stage16_sleep_resume_confirmation(payload, action)
    return {
        "ok": True,
        "kind": "francis.stage16.federation.sleep_resume_operator_confirmation.record",
        "status": "recorded",
        "source_id": "federation",
        "target": "stage16_sleep_continuity",
        "action": action,
        "receipt": receipt,
        "receipt_id": receipt.get("receipt_id", ""),
        "decision": receipt.get("decision", ""),
        "writes_receipt": True,
        "writes_evidence": False,
        "writes_runtime_readback": False,
        "writes_registry": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "marks_stage16_closed": False,
        "governance": {
            **_federation_governance(read_only=False),
            "required_scope": _FEDERATION_SLEEP_RESUME_CONFIRMATION_SCOPE,
            "route": str(request.url.path),
            "explicit_operator_confirmation": True,
            "does_not_infer_sleep_from_delay": True,
            "does_not_write_evidence": True,
            "does_not_write_runtime_readback": True,
            "does_not_mark_stage16_closed": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": _STAGE16_SLEEP_CONTINUITY_RUNTIME_READBACK_GAP,
    }


@router.get("/stage-closure-decisions")
def get_stage_closure_decisions(limit: int = 20) -> dict[str, Any]:
    return stage16_operator_stage_closure_decision_readback(limit=limit)


@router.post("/stage-closure-decision")
def post_stage_closure_decision(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    route = "/federation/stage-closure-decision"
    actor = _federation_write_actor(payload)
    permission = _federation_write_permission(
        actor,
        route=route,
        method=request.method,
        required_scope=_FEDERATION_STAGE16_CLOSURE_SCOPE,
    )
    if not permission.allowed:
        return _permission_denied_for_scope(
            permission,
            required_scope=_FEDERATION_STAGE16_CLOSURE_SCOPE,
            next_step="configure_stage16_closure_write_scope_before_operator_stage_closure_decision",
        )

    review = completion_review()
    if not bool(review.get("stage16_completion_review_ready")):
        return {
            "ok": True,
            "kind": "francis.stage16.federation.stage16_operator_stage_closure_decision.record",
            "status": "awaiting_stage16_closure_readiness",
            "source_id": "federation",
            "target": "stage16_federation",
            "review": review,
            "receipt": None,
            "receipt_id": "",
            "writes_receipt": False,
            "writes_registry": False,
            "writes_memory": False,
            "runs_tools": False,
            "runs_shell": False,
            "runs_git": False,
            "launches_browser": False,
            "captures_screen": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "marks_runtime_stage_state": False,
            "governance": {
                **_federation_governance(read_only=False),
                "required_scope": _FEDERATION_STAGE16_CLOSURE_SCOPE,
                "route": str(request.url.path),
                "explicit_operator_decision": True,
                "does_not_record_when_review_not_ready": True,
                "does_not_mutate_runtime_stage_state": True,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
            "next_smallest_truthful_gap": _safe_str(review.get("next_smallest_truthful_gap")).strip()
            or "stage16_completion_review",
        }

    receipt = record_stage16_operator_stage_closure_decision(payload, review)
    return {
        "ok": True,
        "kind": "francis.stage16.federation.stage16_operator_stage_closure_decision.record",
        "status": "recorded",
        "source_id": "federation",
        "target": "stage16_federation",
        "review": review,
        "receipt": receipt,
        "receipt_id": receipt.get("receipt_id", ""),
        "decision": receipt.get("decision", ""),
        "stage16_closed_by_receipt": bool(receipt.get("stage16_closed_by_receipt")),
        "writes_receipt": True,
        "writes_registry": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "marks_runtime_stage_state": False,
        "governance": {
            **_federation_governance(read_only=False),
            "required_scope": _FEDERATION_STAGE16_CLOSURE_SCOPE,
            "route": str(request.url.path),
            "explicit_operator_decision": True,
            "does_not_mutate_runtime_stage_state": True,
            "does_not_write_memory": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage16_ledger_closure"
        if receipt.get("stage16_closed_by_receipt")
        else "stage16_operator_stage_closure_decision",
    }


@router.get("/live-runtime-readbacks")
def get_live_runtime_readbacks(limit: int = 100) -> dict[str, Any]:
    return live_runtime_readback_summary(limit=limit)


@router.post("/live-runtime-readback")
def post_live_runtime_readback(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    return record_live_runtime_readback(payload, request)


@router.get("/instances/list")
def list_instances(
    status: str | None = None,
    limit: int = 200,
    offset: int = 0,
    tags: str | None = None,
) -> dict[str, Any]:
    try:
        registry = _load_registry()
        return _list_instances(registry, status=status, limit=limit, offset=offset, tags=_parse_list(tags))
    except Exception as exc:
        return {"items": [], "instances": [], "total": 0, "limit": 0, "offset": 0, "error": api_error_message(exc)}


@router.get("/instances/get")
def get_instance(id: str) -> dict[str, Any]:
    try:
        instance_id = _validate_id(id, "instance id")
        registry = _load_registry()
        instances_obj = registry.get("instances") if isinstance(registry.get("instances"), dict) else {}
        raw = instances_obj.get(instance_id)
        if not isinstance(raw, dict):
            return {"ok": False, "error": "not_found"}
        full = _normalize_instance(instance_id, raw)
        item = {k: v for k, v in full.items() if k not in {"health", "inventory"}}
        return {"ok": True, "item": item, "health": full.get("health") or {}, "inventory": full.get("inventory") or {}}
    except Exception as exc:
        return {"ok": False, "error": api_error_message(exc)}


@router.get("/delegations/list")
def list_delegations(
    status: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    try:
        return _list_delegations(_load_registry(), status=status, limit=limit, offset=offset)
    except Exception as exc:
        return {"items": [], "delegations": [], "total": 0, "limit": 0, "offset": 0, "error": api_error_message(exc)}


@router.get("/consensus_logs/list")
def list_consensus_logs(
    level: str | None = None,
    instance_id: str | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    try:
        return _list_consensus_logs(
            _load_registry(),
            level=level,
            instance_id=instance_id,
            start_ts=start_ts,
            end_ts=end_ts,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        return {"items": [], "logs": [], "total": 0, "limit": 0, "offset": 0, "error": api_error_message(exc)}


@router.get("/shared_knowledge/list")
def list_shared_knowledge(
    kind: str | None = None,
    domain: str | None = None,
    limit: int = 200,
    offset: int = 0,
    tags: str | None = None,
) -> dict[str, Any]:
    try:
        return _list_shared_knowledge(
            _load_registry(), kind=kind, domain=domain, limit=limit, offset=offset, tags=_parse_list(tags)
        )
    except Exception as exc:
        return {"items": [], "knowledge": [], "total": 0, "limit": 0, "offset": 0, "error": api_error_message(exc)}


@router.post("/instances/upsert")
def upsert_instance(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    try:
        if denial := _write_permission_denial(payload, request):
            return denial

        requested_id = _safe_str(payload.get("id")).strip()
        name = _safe_str(payload.get("name")).strip()
        if not requested_id and not name:
            return {"ok": False, "error": "id_or_name_required"}

        instance_id = requested_id or _new_id("inst", name)
        instance_id = _validate_id(instance_id, "instance id")

        registry = _load_registry()
        instances_obj = registry.get("instances")
        if not isinstance(instances_obj, dict):
            instances_obj = {}
            registry["instances"] = instances_obj

        existing = instances_obj.get(instance_id) if isinstance(instances_obj.get(instance_id), dict) else {}
        now_s = _now_s()
        first_seen_ts = int(existing.get("first_seen_ts") or payload.get("first_seen_ts") or now_s)

        merged = {
            **existing,
            "id": instance_id,
            "name": name or _safe_str(existing.get("name")).strip() or instance_id,
            "status": _safe_str(payload.get("status")).strip()
            or _safe_str(existing.get("status")).strip()
            or "unknown",
            "endpoint": _safe_str(payload.get("endpoint")).strip() or _safe_str(existing.get("endpoint")).strip(),
            "region": _safe_str(payload.get("region")).strip() or _safe_str(existing.get("region")).strip(),
            "role": _safe_str(payload.get("role")).strip() or _safe_str(existing.get("role")).strip(),
            "first_seen_ts": first_seen_ts,
            "last_seen_ts": int(payload.get("last_seen_ts") or now_s),
            "capabilities": _parse_list(
                payload.get("capabilities") if "capabilities" in payload else existing.get("capabilities")
            ),
            "trust_level": payload.get("trust_level")
            if isinstance(payload.get("trust_level"), (int, float))
            else existing.get("trust_level", 0),
            "requires_approval": _to_bool(
                payload.get("requires_approval"), default=_to_bool(existing.get("requires_approval"), default=False)
            ),
            "tags": _parse_list(payload.get("tags") if "tags" in payload else existing.get("tags")),
            "health": _meta(payload.get("health") if "health" in payload else existing.get("health")),
            "inventory": _meta(payload.get("inventory") if "inventory" in payload else existing.get("inventory")),
            "meta": {**_meta(existing.get("meta")), **_meta(payload.get("meta"))},
        }
        item = _normalize_instance(instance_id, merged)
        instances_obj[instance_id] = item

        _append = {
            "ts": now_s,
            "level": "info",
            "kind": "instance_upsert",
            "instance_id": instance_id,
            "message": f"Federation instance upserted: {instance_id}",
            "meta": {"status": item.get("status")},
        }
        logs = registry.get("consensus_logs") if isinstance(registry.get("consensus_logs"), list) else []
        logs.append(_normalize_consensus_log(_append))
        registry["consensus_logs"] = logs

        _save_registry(registry)
        return {"ok": True, "id": instance_id, "item": item}
    except Exception as exc:
        return {"ok": False, "error": api_error_message(exc)}


@router.post("/delegations/record")
def record_delegation(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    try:
        if denial := _write_permission_denial(payload, request):
            return denial

        scope = _safe_str(payload.get("scope")).strip() or _safe_str(payload.get("scope_id")).strip()
        if not scope:
            return {"ok": False, "error": "scope_required"}

        registry = _load_registry()
        delegations = registry.get("delegations") if isinstance(registry.get("delegations"), list) else []
        item = _normalize_delegation(
            {
                "id": payload.get("id"),
                "ts": payload.get("ts") or _now_s(),
                "from": payload.get("from") or payload.get("from_instance_id"),
                "to": payload.get("to") or payload.get("to_instance_id"),
                "scope": scope,
                "status": payload.get("status") or "pending",
                "reason": payload.get("reason"),
                "meta": payload.get("meta"),
            }
        )
        delegations.append(item)
        registry["delegations"] = delegations
        _save_registry(registry)
        return {"ok": True, "id": item.get("id"), "item": item}
    except Exception as exc:
        return {"ok": False, "error": api_error_message(exc)}


@router.post("/consensus_logs/append")
def append_consensus_log(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    try:
        if denial := _write_permission_denial(payload, request):
            return denial

        message = _safe_str(payload.get("message")).strip() or _safe_str(payload.get("msg")).strip()
        if not message:
            return {"ok": False, "error": "message_required"}

        registry = _load_registry()
        logs = registry.get("consensus_logs") if isinstance(registry.get("consensus_logs"), list) else []
        item = _normalize_consensus_log(
            {
                "id": payload.get("id"),
                "ts": payload.get("ts") or _now_s(),
                "level": payload.get("level") or "info",
                "kind": payload.get("kind"),
                "instance_id": payload.get("instance_id"),
                "term": payload.get("term"),
                "index": payload.get("index"),
                "message": message,
                "meta": payload.get("meta"),
            }
        )
        logs.append(item)
        registry["consensus_logs"] = logs
        _save_registry(registry)
        return {"ok": True, "id": item.get("id"), "item": item}
    except Exception as exc:
        return {"ok": False, "error": api_error_message(exc)}


@router.post("/shared_knowledge/publish")
def publish_shared_knowledge(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    try:
        if denial := _write_permission_denial(payload, request):
            return denial

        title = _safe_str(payload.get("title")).strip() or _safe_str(payload.get("name")).strip()
        if not title and not _safe_str(payload.get("id")).strip():
            return {"ok": False, "error": "title_or_id_required"}

        registry = _load_registry()
        knowledge = registry.get("shared_knowledge") if isinstance(registry.get("shared_knowledge"), list) else []
        item = _normalize_shared_knowledge(
            {
                "id": payload.get("id"),
                "ts": payload.get("ts") or _now_s(),
                "kind": payload.get("kind") or "fact",
                "title": title,
                "source_instance_id": payload.get("source_instance_id") or payload.get("source"),
                "domain": payload.get("domain"),
                "tags": payload.get("tags"),
                "meta": payload.get("meta"),
            }
        )
        knowledge.append(item)
        registry["shared_knowledge"] = knowledge
        _save_registry(registry)
        return {"ok": True, "id": item.get("id"), "item": item}
    except Exception as exc:
        return {"ok": False, "error": api_error_message(exc)}
