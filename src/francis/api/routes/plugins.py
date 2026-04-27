from __future__ import annotations

import csv
import importlib.util
import io
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from francis.governance import approvals as approval_store
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.governance.redaction import (
    redact_governed_display_value,
    redact_governed_metadata,
    redact_governed_value,
    seal_governed_approval_value,
)
from francis.kernel.paths import data_dir, repo_root
from francis.plugin_factory.spec_builder import build_plugin
from francis.plugin_system import (
    PluginDispatcher,
    PluginLoader,
    PluginRegistry,
    PluginSpec,
    PluginValidator,
    SandboxLimits,
    SandboxRunner,
    ToolSpec,
)
from francis.trust.levels import get_state

router = APIRouter()

_PLUGIN_LOADER = PluginLoader()
_PLUGIN_VALIDATOR = PluginValidator()
_RISK_ORDER = {"readonly": 0, "normal": 1, "critical": 2, "safety_critical": 3}
_PLUGIN_WRITE_SCOPE = "plugins.write"


def _art_dir() -> Path:
    return data_dir() / "artifacts" / "plugins"


def _gen_dir() -> Path:
    return repo_root() / "plugins" / "generated"


def _registry_path() -> Path:
    return data_dir() / "plugins" / "_registry.json"


def _runtime_catalog_path() -> Path:
    return data_dir() / "plugins" / "catalog.json"


_PLUGIN_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{1,127}$")
_PLUGIN_ARTIFACT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,191}$")
_ALLOWED_STATUSES = {
    "enabled",
    "disabled",
    "error",
    "installing",
    "staged",
    "uninstalling",
    "updating",
    "unknown",
    "uninstalled",
}
_RISK_APPROVAL_REQUIRED = {"critical", "safety_critical"}
_RISK_DEFAULT_MIN_TRUST: dict[str, int] = {
    "readonly": 0,
    "normal": 0,
    "critical": 5,
    "safety_critical": 8,
}


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _write_permission(actor: Any, *, route: str, method: str) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_PLUGIN_WRITE_SCOPE],
        route=route,
        method=method,
    )


def _permission_denied(decision: ApiPermissionDecision) -> dict[str, object]:
    return {
        "ok": False,
        "applied": False,
        "status": "denied",
        "error": "api_permission_denied",
        "governance": {
            "gate": "permission_gate",
            "reason": decision.reason,
            "next_step": "configure_actor_scope_before_mutating_plugins",
            "evidence": decision.evidence,
        },
    }


def _now_s() -> int:
    return int(time.time())


def _to_bool(value: Any, *, default: bool = False) -> bool:
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


def _parse_tags(value: Any) -> list[str]:
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


def _slugify(value: str) -> str:
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
    return slug[:64] or "plugin"


def _normalize_status(raw_status: Any, enabled: bool | None) -> str:
    status = _safe_str(raw_status).strip().lower()
    if not status:
        if enabled is True:
            return "enabled"
        if enabled is False:
            return "disabled"
        return "unknown"
    if status in _ALLOWED_STATUSES:
        return status
    return status


def _validate_plugin_id(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("plugin id is required")
    if not _PLUGIN_ID_RE.match(text):
        raise ValueError("invalid plugin id")
    return text


def _normalize_capability(plugin_id: str, raw: dict[str, Any]) -> dict[str, Any] | None:
    action = _safe_str(raw.get("action")).strip()
    name = _safe_str(raw.get("name")).strip()
    cap_id = _safe_str(raw.get("id")).strip()
    kind = _safe_str(raw.get("kind")).strip().lower() or "tool"

    if not action:
        if name:
            action = name
        elif cap_id:
            action = cap_id.split(".")[-1]
        else:
            action = "run"
    if not name:
        name = action
    if not cap_id:
        suffix = _slugify(action).replace("-", "_")
        cap_id = f"{plugin_id}.{suffix or 'run'}"

    meta = dict(raw.get("meta") or {}) if isinstance(raw.get("meta"), dict) else {}
    if "risk_tier" in raw and "risk_tier" not in meta:
        meta["risk_tier"] = _safe_str(raw.get("risk_tier")).strip().lower()
    if "required_trust" in raw and "required_trust" not in meta and isinstance(raw.get("required_trust"), (int, float)):
        meta["required_trust"] = int(raw.get("required_trust"))
    if "approvals_required" in raw and "approvals_required" not in meta:
        meta["approvals_required"] = _to_bool(raw.get("approvals_required"), default=False)
    tags = _parse_tags(raw.get("tags"))

    input_schema = raw.get("input_schema")
    if not isinstance(input_schema, dict):
        input_schema = raw.get("parameters")
    if not isinstance(input_schema, dict):
        input_schema = {"type": "object", "additionalProperties": True}

    output_schema = raw.get("output_schema")
    if not isinstance(output_schema, dict):
        output_schema = {}

    description = _safe_str(raw.get("description")).strip() or f"{name} action for plugin {plugin_id}."

    return {
        "id": cap_id,
        "kind": kind,
        "name": name,
        "action": action,
        "description": description,
        "tags": tags,
        "meta": meta,
        "input_schema": input_schema,
        "output_schema": output_schema,
        "parameters": input_schema,
    }


def _default_capabilities(plugin_id: str) -> list[dict[str, Any]]:
    default = _normalize_capability(
        plugin_id,
        {
            "id": f"{plugin_id}.run",
            "kind": "tool",
            "name": "run",
            "action": "run",
            "description": "Execute the plugin entrypoint.",
            "meta": {"risk_tier": "normal"},
            "input_schema": {"type": "object", "additionalProperties": True},
            "output_schema": {"type": "object", "additionalProperties": True},
            "tags": ["plugin", "runtime"],
        },
    )
    return [default] if isinstance(default, dict) else []


def _capabilities_for_plugin(plugin_id: str, raw_capabilities: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    if isinstance(raw_capabilities, list):
        for raw in raw_capabilities:
            if not isinstance(raw, dict):
                continue
            normalized = _normalize_capability(plugin_id, raw)
            if not isinstance(normalized, dict):
                continue
            normalized_id = _safe_str(normalized.get("id")).strip()
            if normalized_id and normalized_id in seen:
                continue
            if normalized_id:
                seen.add(normalized_id)
            items.append(normalized)
    if items:
        return items
    return _default_capabilities(plugin_id)


def _plugin_actions(plugin: dict[str, Any]) -> list[str]:
    capabilities = plugin.get("capabilities")
    if not isinstance(capabilities, list):
        return ["run"]
    out: list[str] = []
    for cap in capabilities:
        if not isinstance(cap, dict):
            continue
        action = _safe_str(cap.get("action")).strip()
        if not action:
            action = _safe_str(cap.get("name")).strip()
        if not action and _safe_str(cap.get("id")).strip():
            action = _safe_str(cap.get("id")).strip().split(".")[-1]
        if action and action not in out:
            out.append(action)
    if "run" not in out:
        out.append("run")
    return out


def _resolve_plugin_action(plugin: dict[str, Any], requested_action: str) -> str | None:
    candidate = _safe_str(requested_action).strip()
    if not candidate:
        return None

    capabilities = plugin.get("capabilities")
    if isinstance(capabilities, list):
        for cap in capabilities:
            if not isinstance(cap, dict):
                continue
            action = _safe_str(cap.get("action")).strip() or _safe_str(cap.get("name")).strip()
            if not action and _safe_str(cap.get("id")).strip():
                action = _safe_str(cap.get("id")).strip().split(".")[-1]
            if not action:
                continue
            candidates = [
                action,
                _safe_str(cap.get("name")).strip(),
                _safe_str(cap.get("id")).strip(),
            ]
            for value in candidates:
                if value and value.lower() == candidate.lower():
                    return action
    if candidate.lower() == "run":
        return "run"
    return None


def _find_capability_for_action(plugin: dict[str, Any], action: str) -> dict[str, Any]:
    resolved = _safe_str(action).strip()
    capabilities = plugin.get("capabilities")
    if isinstance(capabilities, list):
        for cap in capabilities:
            if not isinstance(cap, dict):
                continue
            cap_action = _safe_str(cap.get("action")).strip() or _safe_str(cap.get("name")).strip()
            if not cap_action and _safe_str(cap.get("id")).strip():
                cap_action = _safe_str(cap.get("id")).strip().split(".")[-1]
            if cap_action and cap_action.lower() == resolved.lower():
                return cap
    for cap in _default_capabilities(_safe_str(plugin.get("id")).strip() or "plugin"):
        if _safe_str(cap.get("action")).strip().lower() == resolved.lower():
            return cap
    return {
        "id": f"{_safe_str(plugin.get('id')).strip()}.{_slugify(resolved).replace('-', '_') or 'run'}",
        "kind": "tool",
        "name": resolved or "run",
        "action": resolved or "run",
        "meta": {"risk_tier": "normal"},
    }


def _max_risk_tier(values: list[str]) -> str:
    best = "normal"
    best_rank = _RISK_ORDER.get(best, 1)
    for raw in values:
        candidate = _safe_str(raw).strip().lower() or "normal"
        rank = _RISK_ORDER.get(candidate, 1)
        if rank > best_rank:
            best = candidate
            best_rank = rank
    return best


def _tool_spec_from_capability(plugin_id: str, capability: dict[str, Any]) -> ToolSpec:
    action = _safe_str(capability.get("action")).strip() or _safe_str(capability.get("name")).strip() or "run"
    cap_id = _safe_str(capability.get("id")).strip() or f"{plugin_id}.{_slugify(action).replace('-', '_') or 'run'}"
    meta = capability.get("meta") if isinstance(capability.get("meta"), dict) else {}
    risk_tier = _safe_str(meta.get("risk_tier")).strip().lower() or "normal"
    tool_name = _safe_str(meta.get("tool_name")).strip() or cap_id
    input_schema = capability.get("input_schema")
    if not isinstance(input_schema, dict):
        input_schema = capability.get("parameters")
    if not isinstance(input_schema, dict):
        input_schema = {"type": "object", "additionalProperties": True}
    output_schema = capability.get("output_schema") if isinstance(capability.get("output_schema"), dict) else {}
    resources = meta.get("resources")
    if not isinstance(resources, list):
        resources = []
    policy_tags = meta.get("policy_tags")
    if not isinstance(policy_tags, list):
        policy_tags = _parse_tags(capability.get("tags"))
    if not policy_tags:
        policy_tags = ["installed_plugin"]
    if risk_tier == "safety_critical" and "safety_critical" not in policy_tags:
        policy_tags.append("safety_critical")
    methods = meta.get("methods")
    if not isinstance(methods, list):
        if action.lower() in {"get", "inspect", "list", "query", "read", "scan", "status"}:
            methods = ["read"]
        else:
            methods = ["execute"]
    rate_limits = meta.get("rate_limits") if isinstance(meta.get("rate_limits"), dict) else {}
    required_trust = meta.get("required_trust")
    required_trust_level = (
        int(required_trust) if isinstance(required_trust, (int, float)) else _RISK_DEFAULT_MIN_TRUST.get(risk_tier, 0)
    )
    return ToolSpec(
        tool_name=tool_name,
        action=action,
        summary=_safe_str(capability.get("name")).strip() or action,
        description=_safe_str(capability.get("description")).strip() or f"{action} for {plugin_id}",
        methods=tuple(_safe_str(item).strip().lower() for item in methods if _safe_str(item).strip()),
        resources=tuple(_safe_str(item).strip() for item in resources if _safe_str(item).strip()),
        policy_tags=tuple(_safe_str(item).strip() for item in policy_tags if _safe_str(item).strip()),
        requires_approvals=_to_bool(meta.get("approvals_required"), default=risk_tier in _RISK_APPROVAL_REQUIRED),
        requires_trust_level=required_trust_level,
        rate_limits=dict(rate_limits),
        idempotency=_to_bool(meta.get("idempotency"), default=False),
        dry_run_supported=_to_bool(meta.get("dry_run_supported"), default=risk_tier in {"critical", "safety_critical"}),
        input_schema=input_schema,
        output_schema=output_schema,
        risk_class=risk_tier,
        metadata=dict(meta),
    )


def _spec_from_plugin_record(plugin: dict[str, Any]) -> PluginSpec:
    plugin_id = _safe_str(plugin.get("id")).strip()
    generated_dir = _safe_str(plugin.get("generated_dir")).strip()
    if generated_dir:
        plugin_dir = Path(generated_dir)
        if plugin_dir.exists():
            contract = _load_generated_contract(plugin_dir)
            if contract is not None:
                return contract

    capabilities = _capabilities_for_plugin(plugin_id, plugin.get("capabilities"))
    tools = tuple(
        _tool_spec_from_capability(plugin_id, capability) for capability in capabilities if isinstance(capability, dict)
    )
    meta = plugin.get("meta") if isinstance(plugin.get("meta"), dict) else {}
    contract_summary = meta.get("contract") if isinstance(meta.get("contract"), dict) else {}
    permissions = meta.get("permissions") if isinstance(meta.get("permissions"), dict) else {}
    constraints = meta.get("constraints") if isinstance(meta.get("constraints"), dict) else {}
    telemetry = meta.get("telemetry") if isinstance(meta.get("telemetry"), dict) else {}
    compatibility = meta.get("compatibility") if isinstance(meta.get("compatibility"), dict) else {}
    attestation = meta.get("attestation") if isinstance(meta.get("attestation"), dict) else {}
    sandbox_profile = _safe_str(meta.get("sandbox_profile")).strip() or "default"
    source_path = _safe_str(contract_summary.get("source_path")).strip() or _safe_str(plugin.get("source_ref")).strip()
    risk_class = _max_risk_tier([_safe_str(tool.risk_class).strip() for tool in tools]) if tools else "normal"
    return PluginSpec(
        plugin_id=plugin_id,
        name=_safe_str(plugin.get("name")).strip() or plugin_id,
        version=_safe_str(plugin.get("version")).strip() or "0.1.0",
        description=_safe_str(plugin.get("description")).strip(),
        origin=_safe_str(plugin.get("source_kind")).strip() or "unknown",
        entrypoint=_safe_str(meta.get("entrypoint")).strip() or "plugin.py",
        tools=tools,
        capabilities=tuple(_parse_tags(plugin.get("tags"))),
        risk_class=risk_class,
        permissions=dict(permissions),
        constraints=dict(constraints),
        sandbox_profile=sandbox_profile,
        telemetry=dict(telemetry),
        compatibility=dict(compatibility),
        attestation=dict(attestation),
        metadata=dict(meta),
        source_path=source_path or None,
    )


def _contract_summary_from_spec(spec: PluginSpec) -> dict[str, Any]:
    return {
        "plugin_id": spec.plugin_id,
        "version": spec.version,
        "origin": spec.origin,
        "tool_count": len(spec.tools),
        "capabilities": list(spec.capabilities),
        "risk_class": spec.risk_class,
        "sandbox_profile": spec.sandbox_profile,
        "source_path": spec.source_path or "",
    }


def _build_install_contract_spec(plugin_id: str, payload: "PluginInstallIn") -> PluginSpec:
    source_kind = _safe_str(payload.source_kind).strip().lower()
    source_ref = _safe_str(payload.source_ref).strip()
    version = _safe_str(payload.version).strip() or "0.1.0"
    description = f"Installed from {source_kind}:{source_ref}"
    normalized_capabilities = _capabilities_for_plugin(
        plugin_id, [item for item in payload.capabilities if isinstance(item, dict)]
    )
    tools = tuple(
        _tool_spec_from_capability(plugin_id, capability)
        for capability in normalized_capabilities
        if isinstance(capability, dict)
    )
    meta = dict(payload.meta or {}) if isinstance(payload.meta, dict) else {}
    meta["reason"] = _safe_str(payload.reason).strip()
    ref = _safe_str(payload.ref).strip()
    sha256 = _safe_str(payload.sha256).strip()
    if ref:
        meta["ref"] = ref
    if sha256:
        meta["sha256"] = sha256
    risk_class = _max_risk_tier([tool.risk_class for tool in tools]) if tools else "normal"
    return PluginSpec(
        plugin_id=plugin_id,
        name=_safe_str(source_ref.split("/")[-1] if "/" in source_ref else source_ref).strip() or plugin_id,
        version=version,
        description=description,
        origin=source_kind or "registry",
        entrypoint="plugin.py",
        tools=tools,
        capabilities=tuple(_parse_tags(["installed", source_kind])),
        risk_class=risk_class,
        permissions={},
        constraints={},
        sandbox_profile="default",
        telemetry={},
        compatibility={},
        attestation={},
        metadata=meta,
        source_path=f"{source_kind}:{source_ref}",
    )


def _current_trust_level() -> int:
    state = get_state()
    if not isinstance(state, dict):
        return 0
    if isinstance(state.get("global_level"), (int, float)):
        return int(state.get("global_level") or 0)
    if isinstance(state.get("level"), (int, float)):
        return int(state.get("level") or 0)
    return 0


def _required_trust_for_capability(capability: dict[str, Any], risk_tier: str) -> int:
    meta = capability.get("meta")
    meta_obj = meta if isinstance(meta, dict) else {}
    raw_required = meta_obj.get("required_trust")
    if isinstance(raw_required, (int, float)):
        return int(raw_required)
    return _RISK_DEFAULT_MIN_TRUST.get(risk_tier, 0)


def _approval_required_for_capability(capability: dict[str, Any], risk_tier: str) -> bool:
    meta = capability.get("meta")
    meta_obj = meta if isinstance(meta, dict) else {}
    if "approvals_required" in meta_obj:
        return _to_bool(meta_obj.get("approvals_required"), default=False)
    return risk_tier in _RISK_APPROVAL_REQUIRED


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


def _plugin_run_approval_id(payload: "PluginRunIn") -> str:
    explicit = _safe_str(payload.approval_id).strip()
    if explicit:
        return explicit
    meta_obj = payload.meta if isinstance(payload.meta, dict) else {}
    return _safe_str(meta_obj.get("approval_id")).strip()


def _normalize_approval_value(value: Any) -> Any:
    return seal_governed_approval_value(value)


def _redact_plugin_receipt(receipt: Any) -> dict[str, Any]:
    redacted = redact_governed_value(receipt)
    return redacted if isinstance(redacted, dict) else {}


def _plugin_approval_meta(meta: Any) -> dict[str, Any]:
    return redact_governed_metadata(meta, drop_control_keys=True)


def _plugin_approval_payload(
    *,
    plugin_id: str,
    action: str,
    risk_tier: str,
    required_trust: int,
    idempotency_key: str,
    payload_input: Any,
    meta: Any,
) -> dict[str, Any]:
    return {
        "plugin_id": _safe_str(plugin_id).strip(),
        "action": _safe_str(action).strip(),
        "risk_tier": _safe_str(risk_tier).strip().lower() or "normal",
        "required_trust": int(required_trust),
        "idempotency_key": _safe_str(idempotency_key).strip(),
        "input": _normalize_approval_value(payload_input),
        "meta": _plugin_approval_meta(meta),
    }


def _plugin_approval_artifact_dir(approval_id: str) -> Path:
    return _art_dir() / "approvals" / _safe_str(approval_id).strip()


def _plugin_proposal_id(plugin_id: str, staged_ts: int) -> str:
    return f"plugin_proposal_{staged_ts}_{_slugify(plugin_id)}"


def _plugin_proposal_path(proposal_id: str) -> Path:
    return _art_dir() / "proposals" / f"{_safe_str(proposal_id).strip()}.json"


def _plugin_validation_receipt_id(plugin_id: str, staged_ts: int) -> str:
    return f"plugin_validation_{staged_ts}_{_slugify(plugin_id)}"


def _plugin_validation_receipt_path(validation_id: str) -> Path:
    return _art_dir() / "validations" / f"{_safe_str(validation_id).strip()}.json"


def _plugin_proposal_review_state(proposal_id: str) -> dict[str, Any]:
    resolved_id = _safe_str(proposal_id).strip()
    if not resolved_id:
        return {"status": "missing", "review_status": "missing", "receipt_id": "", "approved": False}
    if not _PLUGIN_ARTIFACT_ID_RE.match(resolved_id):
        return {"status": "invalid", "review_status": "invalid", "receipt_id": "", "approved": False}

    proposal_root = _art_dir() / "proposals"
    proposal_path = _plugin_proposal_path(resolved_id)
    if not _is_under(proposal_root, proposal_path):
        return {"status": "invalid", "review_status": "invalid", "receipt_id": "", "approved": False}
    if not proposal_path.exists() or not proposal_path.is_file():
        return {"status": "missing", "review_status": "missing", "receipt_id": "", "approved": False}

    try:
        proposal = json.loads(proposal_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"status": "unreadable", "review_status": "unreadable", "receipt_id": "", "approved": False}
    if not isinstance(proposal, dict):
        return {"status": "unreadable", "review_status": "unreadable", "receipt_id": "", "approved": False}

    review = proposal.get("review") if isinstance(proposal.get("review"), dict) else {}
    status = _safe_str(proposal.get("status")).strip().lower() or "unknown"
    review_status = _safe_str(review.get("status")).strip().lower() or status
    receipt_id = _safe_str(proposal.get("review_receipt_id") or review.get("receipt_id")).strip()
    approved = status == "approved" and review_status == "approved" and bool(receipt_id)
    return {
        "status": status,
        "review_status": review_status,
        "receipt_id": receipt_id,
        "approved": approved,
    }


def _plugin_promotion_receipt_path(receipt_id: str) -> Path:
    return _art_dir() / "promotions" / f"{_safe_str(receipt_id).strip()}.json"


def _plugin_promotion_receipt_id(plugin_id: str, promoted_ts: int) -> str:
    return f"plugin_promotion_{promoted_ts}_{_slugify(plugin_id)}"


def _plugin_risk_tier(plugin: dict[str, Any]) -> str:
    highest = "normal"
    highest_order = _RISK_ORDER.get(highest, 1)
    for capability in _capabilities_for_plugin(_safe_str(plugin.get("id")).strip(), plugin.get("capabilities")):
        meta = capability.get("meta") if isinstance(capability, dict) else {}
        meta_obj = meta if isinstance(meta, dict) else {}
        risk_tier = _safe_str(meta_obj.get("risk_tier")).strip().lower() or "normal"
        risk_order = _RISK_ORDER.get(risk_tier, highest_order)
        if risk_order > highest_order:
            highest = risk_tier
            highest_order = risk_order
    return highest


def _plugin_promotion_quality(
    plugin_id: str,
    promoted: dict[str, Any],
    payload_meta: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    promoted_meta = promoted.get("meta") if isinstance(promoted.get("meta"), dict) else {}
    generated_dir = _safe_str(promoted.get("generated_dir")).strip()
    readme_path = Path(generated_dir) / "README.md" if generated_dir else _gen_dir() / plugin_id / "README.md"
    docs: Any = payload_meta.get("docs") or payload_meta.get("documentation") or []
    if not docs and readme_path.exists():
        docs = [str(readme_path.resolve())]
    return {
        "summary": payload_meta.get("summary")
        or _safe_str(promoted.get("description")).strip()
        or _safe_str(promoted.get("name")).strip()
        or plugin_id,
        "risk_tier": _safe_str(payload_meta.get("risk_tier")).strip().lower() or _plugin_risk_tier(promoted),
        "tests": payload_meta.get("tests") or payload_meta.get("test_refs") or [],
        "docs": docs,
        "known_limits": payload_meta.get("known_limits") or payload_meta.get("limits") or [],
        "validation": {
            "contract_source_path": _safe_str(promoted_meta.get("contract_source_path")).strip(),
            "registry_snapshot_path": _safe_str(promoted_meta.get("registry_snapshot_path")).strip(),
            "catalog_path": _safe_str(catalog.get("path")).strip(),
            "catalog_total_plugins": int(catalog.get("total_plugins") or 0),
            "catalog_total_tools": int(catalog.get("total_tools") or 0),
        },
    }


def _has_readiness_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_has_readiness_value(item) for item in value)
    if isinstance(value, tuple | set):
        return any(_has_readiness_value(item) for item in value)
    if isinstance(value, dict):
        return any(_has_readiness_value(item) for item in value.values())
    return value is not None


def _plugin_promotion_readiness(
    plugin_id: str,
    staged: dict[str, Any],
    payload: "PluginToggleIn",
) -> dict[str, Any]:
    staged_meta = dict(staged.get("meta") or {}) if isinstance(staged.get("meta"), dict) else {}
    payload_meta = {**staged_meta, **redact_governed_metadata(payload.meta)}
    generated_dir = _safe_str(staged.get("generated_dir")).strip()
    readme_path = Path(generated_dir) / "README.md" if generated_dir else _gen_dir() / plugin_id / "README.md"
    docs = payload_meta.get("docs") or payload_meta.get("documentation") or []
    if not _has_readiness_value(docs) and readme_path.exists():
        docs = [str(readme_path.resolve())]

    risk_tier = _safe_str(payload_meta.get("risk_tier")).strip().lower() or _plugin_risk_tier(staged)
    evidence = payload_meta.get("proposal_evidence") or payload_meta.get("evidence") or []
    tests = payload_meta.get("tests") or payload_meta.get("test_refs") or []
    proposal_id = _safe_str(payload_meta.get("proposal_id") or payload_meta.get("forge_proposal_id")).strip()
    proposal_review = _plugin_proposal_review_state(proposal_id)
    requirements = {
        "proposal_id": bool(proposal_id),
        "proposal_review": bool(proposal_review["approved"]),
        "proposal_evidence": _has_readiness_value(evidence),
        "tests": _has_readiness_value(tests),
        "docs": _has_readiness_value(docs),
        "risk_tier": risk_tier in _RISK_ORDER,
    }
    missing = [key for key, present in requirements.items() if not present]
    return {
        "ready": not missing,
        "missing_requirements": missing,
        "requirements": requirements,
        "evidence": {
            "proposal_id": proposal_id,
            "proposal_review_status": proposal_review["review_status"],
            "proposal_review_receipt_id": proposal_review["receipt_id"],
            "proposal_evidence": evidence,
            "tests": tests,
            "docs": docs,
            "risk_tier": risk_tier,
        },
    }


def _promotion_readiness_blocked(
    *,
    plugin_id: str,
    staged: dict[str, Any],
    readiness: dict[str, Any],
) -> dict[str, object]:
    return {
        "ok": False,
        "applied": False,
        "id": plugin_id,
        "enabled": False,
        "status": "staged",
        "promotion_status": "staged",
        "error": "promotion_readiness_blocked",
        "readiness": redact_governed_display_value(readiness),
        "plugin": {
            "id": plugin_id,
            "status": _safe_str(staged.get("status")).strip() or "staged",
            "enabled": bool(staged.get("enabled", False)),
        },
        "governance": {
            "plane": "P3_GOVERNANCE",
            "gate": "forge_promotion_readiness",
            "scope": _PLUGIN_WRITE_SCOPE,
            "route": "/plugins/enable",
            "next_step": "approve_proposal_and_attach_friction_evidence_tests_docs_and_risk_before_promotion",
            "operator_hint": "Promotion requires an approved proposal review, proposal evidence, tests, docs, and a bounded risk tier.",
        },
    }


def _write_plugin_proposal_record(
    *,
    plugin_id: str,
    proposal_id: str,
    proposal_path: Path,
    staged: dict[str, Any],
    payload: "PluginBuildIn",
    staged_ts: int,
    artifact_zip: str,
    spec_path: str,
    registry_snapshot: str,
    validation: dict[str, Any],
    validation_receipt: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    payload_meta = redact_governed_metadata(payload.meta)
    staged_meta = staged.get("meta") if isinstance(staged.get("meta"), dict) else {}
    record = {
        "kind": "plugin.proposal",
        "proposal_id": proposal_id,
        "plugin_id": plugin_id,
        "status": "staged",
        "created_ts": staged_ts,
        "actor": redact_governed_value(_safe_str(payload.actor).strip()),
        "friction": {
            "summary": payload_meta.get("friction_summary")
            or payload_meta.get("friction")
            or _safe_str(payload.description).strip()
            or _safe_str(payload.name).strip(),
            "evidence": payload_meta.get("proposal_evidence") or payload_meta.get("evidence") or [],
            "recurrence_count": payload_meta.get("recurrence_count"),
        },
        "proposed_capability": {
            "name": _safe_str(payload.name).strip() or plugin_id,
            "description": _safe_str(payload.description).strip(),
            "inputs": payload_meta.get("inputs") or payload_meta.get("input_requirements") or [],
            "scope": payload_meta.get("scope") or payload_meta.get("expected_scope") or "local_generated_plugin",
            "expected_benefit": payload_meta.get("expected_benefit") or payload_meta.get("benefit") or "",
        },
        "quality_requirements": {
            "risk_tier": _safe_str(payload_meta.get("risk_tier")).strip().lower() or _plugin_risk_tier(staged),
            "tests": payload_meta.get("tests") or payload_meta.get("test_refs") or [],
            "docs": payload_meta.get("docs") or payload_meta.get("documentation") or [],
            "validation_path": payload_meta.get("validation_path") or [],
            "known_limits": payload_meta.get("known_limits") or payload_meta.get("limits") or [],
        },
        "staged_implementation": {
            "status": "staged",
            "enabled": False,
            "artifact_zip": artifact_zip,
            "spec_path": spec_path,
            "registry_snapshot": registry_snapshot,
            "contract_source_path": _safe_str(staged_meta.get("contract_source_path")).strip(),
            "catalog_path": _safe_str(catalog.get("path")).strip(),
        },
        "validation": {
            "build": validation,
            "validation_receipt_id": _safe_str(validation_receipt.get("validation_id")).strip(),
            "validation_receipt_path": _safe_str(validation_receipt.get("path")).strip(),
            "catalog_total_plugins": int(catalog.get("total_plugins") or 0),
            "catalog_total_tools": int(catalog.get("total_tools") or 0),
        },
        "proposal_context": payload_meta,
        "governance": {
            "gate": "permission_gate",
            "scope": _PLUGIN_WRITE_SCOPE,
            "route": "/plugins/build",
            "explicit_staging": True,
            "auto_promoted": False,
        },
        "path": str(proposal_path),
    }
    redacted_record = redact_governed_display_value(record)
    out = redacted_record if isinstance(redacted_record, dict) else {}
    _atomic_write_json(proposal_path, out)
    return out


def _write_plugin_validation_receipt(
    *,
    plugin_id: str,
    validation_id: str,
    validation_path: Path,
    proposal_id: str,
    proposal_path: Path,
    payload: "PluginBuildIn",
    staged_ts: int,
    artifact_zip: str,
    spec_path: str,
    registry_snapshot: str,
    validation: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    valid = bool(validation.get("valid"))
    receipt = {
        "kind": "plugin.validation.receipt",
        "validation_id": validation_id,
        "plugin_id": plugin_id,
        "proposal_id": proposal_id,
        "status": "passed" if valid else "failed",
        "valid": valid,
        "validated_ts": staged_ts,
        "actor": redact_governed_value(_safe_str(payload.actor).strip()),
        "proposal_path": str(proposal_path),
        "artifact_zip": artifact_zip,
        "spec_path": spec_path,
        "registry_snapshot": registry_snapshot,
        "validation": validation,
        "catalog": {
            "path": _safe_str(catalog.get("path")).strip(),
            "total_plugins": int(catalog.get("total_plugins") or 0),
            "total_tools": int(catalog.get("total_tools") or 0),
        },
        "governance": {
            "gate": "plugin_build_validation",
            "scope": _PLUGIN_WRITE_SCOPE,
            "route": "/plugins/build",
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
        },
        "path": str(validation_path),
    }
    redacted_receipt = redact_governed_display_value(receipt)
    out = redacted_receipt if isinstance(redacted_receipt, dict) else {}
    _atomic_write_json(validation_path, out)
    return out


def _write_plugin_promotion_receipt(
    *,
    plugin_id: str,
    receipt_id: str,
    receipt_path: Path,
    previous: dict[str, Any],
    promoted: dict[str, Any],
    payload: "PluginToggleIn",
    promoted_ts: int,
    catalog: dict[str, Any],
) -> dict[str, Any]:
    previous_meta = dict(previous.get("meta") or {}) if isinstance(previous.get("meta"), dict) else {}
    payload_meta = {**previous_meta, **redact_governed_metadata(payload.meta)}
    proposal_id = _safe_str(payload_meta.get("proposal_id") or payload_meta.get("forge_proposal_id") or "").strip()
    proposal_review = _plugin_proposal_review_state(proposal_id)
    receipt = {
        "kind": "plugin.promotion.receipt",
        "receipt_id": receipt_id,
        "plugin_id": plugin_id,
        "status": "promoted",
        "previous_status": _safe_str(previous.get("status")).strip() or "unknown",
        "previous_enabled": bool(previous.get("enabled", False)),
        "promoted_status": "enabled",
        "promoted_enabled": True,
        "staged_ts": previous.get("updated_ts") or previous.get("installed_ts"),
        "promoted_ts": promoted_ts,
        "actor": redact_governed_value(_safe_str(payload.actor).strip()),
        "reason": redact_governed_value(_safe_str(payload.reason).strip() or "requested"),
        "proposal_id": proposal_id,
        "proposal_review": {
            "status": proposal_review["review_status"],
            "receipt_id": proposal_review["receipt_id"],
        },
        "proposal_evidence": payload_meta.get("proposal_evidence") or payload_meta.get("evidence") or [],
        "quality": _plugin_promotion_quality(plugin_id, promoted, payload_meta, catalog),
        "promotion_context": payload_meta,
        "governance": {
            "gate": "permission_gate",
            "scope": _PLUGIN_WRITE_SCOPE,
            "route": "/plugins/enable",
            "explicit": True,
        },
        "path": str(receipt_path),
    }
    redacted_receipt = _redact_plugin_receipt(receipt)
    _atomic_write_display_json(receipt_path, redacted_receipt)
    return redacted_receipt


def _request_plugin_approval(
    *,
    plugin_id: str,
    action: str,
    request_payload: dict[str, Any],
    reason: str,
    previous_approval_id: str = "",
    previous_status: str = "",
    previous_record: dict[str, Any] | None = None,
) -> tuple[str, Path]:
    approval = approval_store.request(
        action="plugin.run",
        reason=reason,
        payload=request_payload,
    )
    approval_id = _safe_str(approval.get("id")).strip()
    art = _plugin_approval_artifact_dir(approval_id)
    request_body: dict[str, Any] = {
        "kind": "plugin.run.request",
        "approval": approval,
        "plugin_id": plugin_id,
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


def _plugin_governance(
    *,
    gate: str,
    next_step: str,
    operator_hint: str,
    action: str,
    risk_tier: str,
    required_trust: int,
    current_trust: int | None = None,
    approval_status: str = "",
) -> dict[str, object]:
    out: dict[str, object] = {
        "plane": "P3_GOVERNANCE",
        "gate": gate,
        "next_step": next_step,
        "operator_hint": operator_hint,
        "action": action,
        "risk_tier": risk_tier,
        "required_trust": required_trust,
    }
    if current_trust is not None:
        out["current_trust"] = current_trust
    if approval_status:
        out["approval_status"] = approval_status
    return out


def _tool_item(plugin: dict[str, Any], capability: dict[str, Any]) -> dict[str, Any]:
    plugin_id = _safe_str(plugin.get("id")).strip()
    cap_id = _safe_str(capability.get("id")).strip() or _safe_str(capability.get("action")).strip() or "run"
    action = _safe_str(capability.get("action")).strip() or _safe_str(capability.get("name")).strip() or "run"
    tags = _parse_tags(plugin.get("tags"))
    for extra in _parse_tags(capability.get("tags")):
        if extra not in tags:
            tags.append(extra)
    meta = capability.get("meta")
    meta_obj = dict(meta) if isinstance(meta, dict) else {}
    risk_tier = _safe_str(meta_obj.get("risk_tier")).strip().lower() or "normal"
    required_trust = _required_trust_for_capability(capability, risk_tier)
    approvals_required = _approval_required_for_capability(capability, risk_tier)
    return {
        "id": f"{plugin_id}:{cap_id}",
        "plugin_id": plugin_id,
        "plugin_name": _safe_str(plugin.get("name")).strip() or plugin_id,
        "name": _safe_str(capability.get("name")).strip() or action,
        "action": action,
        "kind": _safe_str(capability.get("kind")).strip().lower() or "tool",
        "description": _safe_str(capability.get("description")).strip(),
        "enabled": bool(plugin.get("enabled", False)),
        "status": _safe_str(plugin.get("status")).strip() or "unknown",
        "source_kind": _safe_str(plugin.get("source_kind")).strip() or "unknown",
        "risk_tier": risk_tier,
        "required_trust": required_trust,
        "approvals_required": approvals_required,
        "input_schema": capability.get("input_schema")
        if isinstance(capability.get("input_schema"), dict)
        else (
            capability.get("parameters")
            if isinstance(capability.get("parameters"), dict)
            else {"type": "object", "additionalProperties": True}
        ),
        "output_schema": capability.get("output_schema") if isinstance(capability.get("output_schema"), dict) else {},
        "tags": tags,
        "meta": meta_obj,
    }


def _plugin_tools(plugin: dict[str, Any]) -> list[dict[str, Any]]:
    plugin_id = _safe_str(plugin.get("id")).strip()
    caps = plugin.get("capabilities")
    capabilities = _capabilities_for_plugin(plugin_id, caps)
    return [_tool_item(plugin, cap) for cap in capabilities if isinstance(cap, dict)]


def _match_tool(
    item: dict[str, Any],
    plugin_filter: str,
    enabled_filter: bool | None,
    kind_filter: str,
    tag_filters: list[str],
    search_filter: str,
) -> bool:
    if plugin_filter and _safe_str(item.get("plugin_id")).strip().lower() != plugin_filter:
        return False
    if enabled_filter is not None and bool(item.get("enabled")) != enabled_filter:
        return False
    if kind_filter and _safe_str(item.get("kind")).strip().lower() != kind_filter:
        return False
    if tag_filters:
        existing = set(_parse_tags(item.get("tags")))
        if not set(tag_filters).issubset(existing):
            return False
    if search_filter:
        haystack = " ".join(
            [
                _safe_str(item.get("id")),
                _safe_str(item.get("plugin_id")),
                _safe_str(item.get("plugin_name")),
                _safe_str(item.get("name")),
                _safe_str(item.get("action")),
                _safe_str(item.get("description")),
                _safe_str(item.get("kind")),
                _safe_str(item.get("risk_tier")),
            ]
        ).lower()
        if search_filter not in haystack:
            return False
    return True


def _default_registry() -> dict[str, Any]:
    return {"version": 1, "updated_at": _now_s(), "plugins": {}}


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _atomic_write_display_json(path: Path, obj: dict[str, Any]) -> None:
    display_obj = redact_governed_display_value(obj)
    _atomic_write_json(path, display_obj if isinstance(display_obj, dict) else {})


def _load_registry() -> dict[str, Any]:
    registry_path = _registry_path()
    if not registry_path.exists():
        return _default_registry()
    try:
        raw = json.loads(registry_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return _default_registry()
    if not isinstance(raw, dict):
        return _default_registry()

    plugins = raw.get("plugins")
    if isinstance(plugins, dict):
        return {
            "version": int(raw.get("version") or 1),
            "updated_at": int(raw.get("updated_at") or _now_s()),
            "plugins": plugins,
        }

    legacy_plugins = {k: v for k, v in raw.items() if isinstance(v, dict)}
    if legacy_plugins:
        return {"version": 1, "updated_at": _now_s(), "plugins": legacy_plugins}
    return _default_registry()


def _save_registry(registry: dict[str, Any]) -> None:
    plugins = registry.get("plugins")
    if not isinstance(plugins, dict):
        plugins = {}
    normalized: dict[str, Any] = {
        "version": int(registry.get("version") or 1),
        "updated_at": _now_s(),
        "plugins": plugins,
    }
    _atomic_write_json(_registry_path(), normalized)


def _compile_runtime_catalog(registry: dict[str, Any]) -> dict[str, Any]:
    runtime_registry = PluginRegistry()
    rejected: list[dict[str, Any]] = []
    plugins = registry.get("plugins")
    if not isinstance(plugins, dict):
        plugins = {}
    for plugin_id, raw in plugins.items():
        if not isinstance(raw, dict):
            continue
        normalized = _normalize_plugin_record(_safe_str(plugin_id), raw)
        spec = _spec_from_plugin_record(normalized)
        result = runtime_registry.register(spec)
        if not result.valid:
            rejected.append({"plugin_id": normalized["id"], "reason": result.reason, "errors": list(result.errors)})
    path = runtime_registry.write_catalog(_runtime_catalog_path())
    catalog = runtime_registry.to_dict()
    return {
        "path": str(path),
        "total_plugins": int(catalog.get("total_plugins") or 0),
        "total_tools": int(catalog.get("total_tools") or 0),
        "rejected": rejected,
    }


def _save_registry_and_catalog(registry: dict[str, Any]) -> dict[str, Any]:
    _save_registry(registry)
    return _compile_runtime_catalog(registry)


def _normalize_plugin_record(plugin_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    status_raw = _safe_str(raw.get("status")).strip().lower()
    enabled = raw.get("enabled")
    enabled_bool: bool | None = enabled if isinstance(enabled, bool) else None

    if enabled_bool is None and status_raw:
        if status_raw in {"enabled"}:
            enabled_bool = True
        elif status_raw in {"disabled", "staged", "uninstalled"}:
            enabled_bool = False

    status = _normalize_status(raw.get("status"), enabled_bool)
    if enabled_bool is None:
        enabled_bool = status not in {"disabled", "staged", "uninstalled"}

    installed_ts = int(raw.get("installed_ts") or _now_s())
    updated_ts = int(raw.get("updated_ts") or installed_ts)
    tags = _parse_tags(raw.get("tags"))
    meta = dict(raw.get("meta") or {}) if isinstance(raw.get("meta"), dict) else {}
    capabilities = _capabilities_for_plugin(plugin_id, raw.get("capabilities"))

    out = {
        "id": plugin_id,
        "name": _safe_str(raw.get("name")).strip() or plugin_id,
        "version": _safe_str(raw.get("version")).strip() or "",
        "status": status,
        "enabled": bool(enabled_bool),
        "description": _safe_str(raw.get("description")).strip() or "",
        "author": _safe_str(raw.get("author")).strip() or "",
        "homepage": _safe_str(raw.get("homepage")).strip() or "",
        "license": _safe_str(raw.get("license")).strip() or "",
        "source_kind": _safe_str(raw.get("source_kind")).strip() or "unknown",
        "source_ref": _safe_str(raw.get("source_ref")).strip() or "",
        "installed_ts": installed_ts,
        "updated_ts": updated_ts,
        "tags": tags,
        "signed": bool(raw.get("signed", False)),
        "verified": bool(raw.get("verified", False)),
        "capabilities": capabilities,
        "actions": [action for action in _plugin_actions({"capabilities": capabilities}) if action],
        "meta": meta,
        "generated_dir": _safe_str(raw.get("generated_dir")).strip() or "",
        "artifact_zip": _safe_str(raw.get("artifact_zip")).strip() or "",
    }
    return out


def _read_plugin(registry: dict[str, Any], plugin_id: str) -> dict[str, Any] | None:
    plugins = registry.get("plugins")
    if not isinstance(plugins, dict):
        return None
    raw = plugins.get(plugin_id)
    if not isinstance(raw, dict):
        return None
    return _normalize_plugin_record(plugin_id, raw)


def _write_plugin(registry: dict[str, Any], plugin: dict[str, Any]) -> None:
    plugins = registry.get("plugins")
    if not isinstance(plugins, dict):
        plugins = {}
        registry["plugins"] = plugins
    plugins[plugin["id"]] = plugin


def _delete_plugin(registry: dict[str, Any], plugin_id: str) -> bool:
    plugins = registry.get("plugins")
    if not isinstance(plugins, dict):
        return False
    if plugin_id not in plugins:
        return False
    del plugins[plugin_id]
    return True


def _parse_simple_yaml(path: Path) -> dict[str, str]:
    if not path.exists() or not path.is_file():
        return {}
    out: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or ":" not in stripped:
                continue
            key, value = stripped.split(":", 1)
            out[key.strip()] = value.strip()
    except Exception:
        return {}
    return out


def _manifest_for_plugin_dir(plugin_dir: Path) -> dict[str, str]:
    yaml_path = plugin_dir / "plugin.yaml"
    manifest = _parse_simple_yaml(yaml_path)
    if "entrypoint" not in manifest:
        manifest["entrypoint"] = "plugin.py"
    return manifest


def _generated_contract_path(plugin_dir: Path) -> Path:
    return plugin_dir / "plugin.spec.json"


def _generated_registry_snapshot_path(plugin_dir: Path) -> Path:
    return plugin_dir / "plugin.registry.json"


def _load_generated_contract(plugin_dir: Path) -> PluginSpec | None:
    spec_path = _generated_contract_path(plugin_dir)
    if not spec_path.exists() or not spec_path.is_file():
        return None
    return _PLUGIN_LOADER.load(spec_path)


def _read_generated_registry_snapshot(plugin_dir: Path) -> dict[str, Any]:
    snapshot_path = _generated_registry_snapshot_path(plugin_dir)
    if not snapshot_path.exists() or not snapshot_path.is_file():
        return {}
    try:
        raw = json.loads(snapshot_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _merge_unique_tags(*groups: Any) -> list[str]:
    out: list[str] = []
    for group in groups:
        for tag in _parse_tags(group):
            if tag and tag not in out:
                out.append(tag)
    return out


def _capability_from_contract_tool(plugin_id: str, tool: ToolSpec, plugin_tags: list[str]) -> dict[str, Any] | None:
    suffix = _slugify(tool.action or tool.tool_name.split(".")[-1]).replace("-", "_") or "run"
    meta = dict(tool.metadata)
    meta.setdefault("risk_tier", tool.risk_class)
    meta.setdefault("approvals_required", tool.requires_approvals)
    if tool.requires_trust_level:
        meta.setdefault("required_trust", tool.requires_trust_level)
    if tool.rate_limits:
        meta["rate_limits"] = dict(tool.rate_limits)
    meta["tool_name"] = tool.tool_name
    if tool.resources:
        meta["resources"] = list(tool.resources)
    if tool.policy_tags:
        meta["policy_tags"] = list(tool.policy_tags)
    meta["dry_run_supported"] = bool(tool.dry_run_supported)
    meta["idempotency"] = bool(tool.idempotency)

    return _normalize_capability(
        plugin_id,
        {
            "id": f"{plugin_id}.{suffix}",
            "kind": "tool",
            "name": tool.action or suffix,
            "action": tool.action or suffix,
            "description": tool.description or tool.summary,
            "tags": _merge_unique_tags(plugin_tags, list(tool.policy_tags)),
            "meta": meta,
            "input_schema": dict(tool.input_schema or {"type": "object", "additionalProperties": True}),
            "output_schema": dict(tool.output_schema or {}),
        },
    )


def _capabilities_from_contract(plugin_id: str, spec: PluginSpec) -> list[dict[str, Any]]:
    plugin_tags = _merge_unique_tags([spec.origin], list(spec.capabilities))
    capabilities: list[dict[str, Any]] = []
    for tool in spec.tools:
        capability = _capability_from_contract_tool(plugin_id, tool, plugin_tags)
        if isinstance(capability, dict):
            capabilities.append(capability)
    return capabilities or _default_capabilities(plugin_id)


def _record_from_generated_contract(
    plugin_id: str,
    *,
    current: dict[str, Any],
    plugin_dir: Path,
    artifact_path: Path,
    spec: PluginSpec,
) -> dict[str, Any]:
    now_s = _now_s()
    snapshot_path = _generated_registry_snapshot_path(plugin_dir)
    merged_meta = {
        **(dict(current.get("meta") or {}) if isinstance(current.get("meta"), dict) else {}),
        "entrypoint": spec.entrypoint or "plugin.py",
        "sandbox_profile": spec.sandbox_profile,
        "permissions": spec.permissions,
        "constraints": spec.constraints,
        "telemetry": spec.telemetry,
        "compatibility": spec.compatibility,
        "attestation": spec.attestation,
        "contract_source_path": spec.source_path or str(_generated_contract_path(plugin_dir)),
        "registry_snapshot_path": str(snapshot_path.resolve()) if snapshot_path.exists() else "",
    }
    tags = _merge_unique_tags(current.get("tags"), [spec.origin], list(spec.capabilities), ["generated"])
    return _normalize_plugin_record(
        plugin_id,
        {
            **current,
            "id": plugin_id,
            "name": spec.name or _safe_str(current.get("name")).strip() or plugin_id,
            "version": spec.version or _safe_str(current.get("version")).strip(),
            "description": spec.description or _safe_str(current.get("description")).strip(),
            "status": current.get("status") or "enabled",
            "enabled": current.get("enabled", True),
            "source_kind": _safe_str(current.get("source_kind")).strip() or spec.origin or "generated",
            "source_ref": _safe_str(current.get("source_ref")).strip() or (spec.source_path or plugin_id),
            "installed_ts": int(current.get("installed_ts") or now_s),
            "updated_ts": now_s,
            "generated_dir": str(plugin_dir.resolve()),
            "artifact_zip": str(artifact_path.resolve()) if artifact_path.exists() else "",
            "capabilities": _capabilities_from_contract(plugin_id, spec),
            "tags": tags,
            "meta": merged_meta,
            "verified": bool(current.get("verified", False)),
            "signed": bool(current.get("signed", False)),
        },
    )


def _read_generated_details(plugin_id: str, plugin: dict[str, Any]) -> dict[str, Any]:
    generated_dir = _safe_str(plugin.get("generated_dir")).strip()
    plugin_dir = Path(generated_dir) if generated_dir else (_gen_dir() / plugin_id)
    if not plugin_dir.exists() or not plugin_dir.is_dir():
        return {}

    manifest = _manifest_for_plugin_dir(plugin_dir)
    contract_spec = _load_generated_contract(plugin_dir)
    registry_snapshot = _read_generated_registry_snapshot(plugin_dir)
    if contract_spec is not None:
        manifest = {
            "id": contract_spec.plugin_id or plugin_id,
            "name": contract_spec.name or _safe_str(plugin.get("name")).strip() or plugin_id,
            "description": contract_spec.description or _safe_str(plugin.get("description")).strip(),
            "entrypoint": contract_spec.entrypoint or "plugin.py",
        }
    entrypoint = _safe_str(manifest.get("entrypoint")).strip() or "plugin.py"
    readme_path = plugin_dir / "README.md"
    readme = readme_path.read_text(encoding="utf-8", errors="replace") if readme_path.exists() else ""

    files: list[str] = []
    for p in plugin_dir.rglob("*"):
        if p.is_file():
            try:
                files.append(p.relative_to(plugin_dir).as_posix())
            except ValueError:
                continue
    files.sort()

    contract_summary: dict[str, Any] = {}
    if contract_spec is not None:
        contract_summary = {
            "plugin_id": contract_spec.plugin_id,
            "version": contract_spec.version,
            "origin": contract_spec.origin,
            "tool_count": len(contract_spec.tools),
            "capabilities": list(contract_spec.capabilities),
            "sandbox_profile": contract_spec.sandbox_profile,
            "source_path": contract_spec.source_path or str(_generated_contract_path(plugin_dir)),
        }

    registry_summary: dict[str, Any] = {}
    if registry_snapshot:
        registry_summary = {
            "path": str(_generated_registry_snapshot_path(plugin_dir)),
            "total_plugins": int(registry_snapshot.get("total_plugins") or 0),
            "total_tools": int(registry_snapshot.get("total_tools") or 0),
        }

    return {
        "manifest": {
            "id": _safe_str(manifest.get("id")).strip() or plugin_id,
            "name": _safe_str(manifest.get("name")).strip() or plugin.get("name") or plugin_id,
            "description": _safe_str(manifest.get("description")).strip() or plugin.get("description") or "",
            "entrypoint": entrypoint,
        },
        "entrypoint": entrypoint,
        "readme": readme,
        "files": files,
        "contract": contract_summary,
        "registry_snapshot": registry_summary,
    }


def _ensure_plugin_from_generated(registry: dict[str, Any], plugin_id: str) -> bool:
    plugin_dir = _gen_dir() / plugin_id
    if not plugin_dir.exists() or not plugin_dir.is_dir():
        return False

    current = _read_plugin(registry, plugin_id) or {}
    artifact_path = _art_dir() / f"{plugin_id}.zip"
    contract_spec = _load_generated_contract(plugin_dir)
    if contract_spec is not None:
        record = _record_from_generated_contract(
            plugin_id,
            current=current,
            plugin_dir=plugin_dir,
            artifact_path=artifact_path,
            spec=contract_spec,
        )
    else:
        manifest = _manifest_for_plugin_dir(plugin_dir)
        now_s = _now_s()
        record = _normalize_plugin_record(
            plugin_id,
            {
                **current,
                "id": plugin_id,
                "name": _safe_str(manifest.get("name")).strip() or _safe_str(current.get("name")).strip() or plugin_id,
                "description": _safe_str(manifest.get("description")).strip()
                or _safe_str(current.get("description")).strip(),
                "status": current.get("status") or "enabled",
                "enabled": current.get("enabled", True),
                "source_kind": _safe_str(current.get("source_kind")).strip() or "generated",
                "source_ref": _safe_str(current.get("source_ref")).strip() or plugin_id,
                "installed_ts": int(current.get("installed_ts") or now_s),
                "updated_ts": now_s,
                "generated_dir": str(plugin_dir.resolve()),
                "artifact_zip": str(artifact_path.resolve()) if artifact_path.exists() else "",
                "tags": _parse_tags(current.get("tags")) or ["generated"],
                "meta": {
                    **(dict(current.get("meta") or {}) if isinstance(current.get("meta"), dict) else {}),
                    "entrypoint": _safe_str(manifest.get("entrypoint")).strip() or "plugin.py",
                },
            },
        )
    _write_plugin(registry, record)
    return True


def _sync_generated_plugins(registry: dict[str, Any]) -> int:
    gen_dir = _gen_dir()
    if not gen_dir.exists() or not gen_dir.is_dir():
        return 0

    synced = 0
    for child in sorted(gen_dir.iterdir()):
        if not child.is_dir():
            continue
        plugin_id = child.name
        try:
            _validate_plugin_id(plugin_id)
        except Exception:
            continue
        if _ensure_plugin_from_generated(registry, plugin_id):
            synced += 1
    return synced


def _is_under(base: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(base.resolve())
        return True
    except Exception:
        return False


def _coerce_run_input(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return _safe_str(value)


def _run_generated_plugin(plugin: dict[str, Any], payload_input: Any) -> Any:
    plugin_id = _safe_str(plugin.get("id")).strip()
    generated_dir = _safe_str(plugin.get("generated_dir")).strip()
    plugin_dir = Path(generated_dir) if generated_dir else (_gen_dir() / plugin_id)
    if not plugin_dir.exists():
        return {"echo": payload_input}

    meta = plugin.get("meta")
    meta_obj = meta if isinstance(meta, dict) else {}
    entrypoint = _safe_str(meta_obj.get("entrypoint")).strip() or "plugin.py"
    entrypoint_path = plugin_dir / entrypoint
    if not entrypoint_path.exists() or not entrypoint_path.is_file():
        return {"echo": payload_input}

    module_name = f"francis_plugin_{plugin_id}_{int(time.time() * 1000)}"
    spec = importlib.util.spec_from_file_location(module_name, str(entrypoint_path))
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load plugin entrypoint")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    handler = getattr(module, "run", None)
    if not callable(handler):
        return {"echo": payload_input}

    serialized_input = _coerce_run_input(payload_input)
    try:
        return handler(serialized_input)
    except TypeError:
        return handler()


def _sandbox_limits_for_plugin(plugin: dict[str, Any], capability: dict[str, Any]) -> SandboxLimits:
    meta = capability.get("meta") if isinstance(capability.get("meta"), dict) else {}
    plugin_meta = plugin.get("meta") if isinstance(plugin.get("meta"), dict) else {}
    constraints = plugin_meta.get("constraints") if isinstance(plugin_meta.get("constraints"), dict) else {}
    raw_payload_limit = constraints.get("max_payload_bytes")
    max_payload_bytes = int(raw_payload_limit) if isinstance(raw_payload_limit, (int, float)) else 65536
    risk_tier = _safe_str(meta.get("risk_tier")).strip().lower() or "normal"
    generated_dir = _safe_str(plugin.get("generated_dir")).strip()
    allowed_paths = [generated_dir] if generated_dir else []
    return SandboxLimits(
        max_payload_bytes=max_payload_bytes,
        allow_network="web_access" in _parse_tags(meta.get("policy_tags")),
        allow_filesystem_write=risk_tier in {"normal", "critical", "safety_critical"},
        allowed_paths=tuple(path for path in allowed_paths if path),
    )


def _execute_plugin_action(
    plugin: dict[str, Any], capability: dict[str, Any], payload_input: Any, *, dry_run: bool
) -> dict[str, Any]:
    plugin_id = _safe_str(plugin.get("id")).strip()
    cap_meta = capability.get("meta") if isinstance(capability.get("meta"), dict) else {}
    tool_name = (
        _safe_str(cap_meta.get("tool_name")).strip() or _safe_str(capability.get("id")).strip() or f"{plugin_id}.run"
    )
    dispatcher = PluginDispatcher(sandbox=SandboxRunner(_sandbox_limits_for_plugin(plugin, capability)))

    def _handler() -> Any:
        return _run_generated_plugin(plugin, payload_input)

    result = dispatcher.dispatch_with_receipt(
        _handler,
        plugin_id=plugin_id,
        tool_name=tool_name,
        dry_run=dry_run,
    )
    return result.to_dict()


def _match_plugin(
    item: dict[str, Any],
    status_filter: str,
    enabled_filter: bool | None,
    source_kind_filter: str,
    tag_filters: list[str],
    search_filter: str,
) -> bool:
    if status_filter and _safe_str(item.get("status")).strip().lower() != status_filter:
        return False
    if enabled_filter is not None and bool(item.get("enabled")) != enabled_filter:
        return False
    if source_kind_filter and _safe_str(item.get("source_kind")).strip().lower() != source_kind_filter:
        return False
    if tag_filters:
        existing = set(_parse_tags(item.get("tags")))
        if not set(tag_filters).issubset(existing):
            return False
    if search_filter:
        haystack = " ".join(
            [
                _safe_str(item.get("id")),
                _safe_str(item.get("name")),
                _safe_str(item.get("description")),
                _safe_str(item.get("source_ref")),
            ]
        ).lower()
        if search_filter not in haystack:
            return False
    return True


def _query_tools(
    *,
    registry: dict[str, Any],
    limit: int,
    offset: int,
    plugin_id: str | None,
    enabled: bool | None,
    kind: str | None,
    tag: str | None,
    tags: list[str] | None,
    search: str | None,
) -> tuple[list[dict[str, Any]], int]:
    safe_limit = max(1, min(int(limit), 5000))
    safe_offset = max(0, int(offset))
    plugin_filter = _safe_str(plugin_id).strip().lower()
    kind_filter = _safe_str(kind).strip().lower()
    search_filter = _safe_str(search).strip().lower()
    tag_filters = _parse_tags(tag)
    for extra in tags or []:
        normalized = _safe_str(extra).strip()
        if normalized and normalized not in tag_filters:
            tag_filters.append(normalized)

    tools: list[dict[str, Any]] = []
    plugins_obj = registry.get("plugins")
    if not isinstance(plugins_obj, dict):
        plugins_obj = {}
    for raw_id, raw_plugin in plugins_obj.items():
        if not isinstance(raw_plugin, dict):
            continue
        plugin = _normalize_plugin_record(_safe_str(raw_id), raw_plugin)
        for tool in _plugin_tools(plugin):
            if _match_tool(tool, plugin_filter, enabled, kind_filter, tag_filters, search_filter):
                tools.append(tool)

    tools.sort(
        key=lambda item: (_safe_str(item.get("plugin_id")), _safe_str(item.get("name")), _safe_str(item.get("id")))
    )
    total = len(tools)
    return tools[safe_offset : safe_offset + safe_limit], total


def _find_tool_by_id(registry: dict[str, Any], tool_id: str) -> dict[str, Any] | None:
    resolved_id = _safe_str(tool_id).strip()
    if not resolved_id:
        return None

    prefix, _, _ = resolved_id.partition(":")
    if prefix:
        try:
            normalized_plugin_id = _validate_plugin_id(prefix)
        except Exception:
            normalized_plugin_id = ""
        if normalized_plugin_id:
            plugin = _read_plugin(registry, normalized_plugin_id)
            if isinstance(plugin, dict):
                for item in _plugin_tools(plugin):
                    if _safe_str(item.get("id")).strip() == resolved_id:
                        return item

    page, _ = _query_tools(
        registry=registry,
        limit=100_000,
        offset=0,
        plugin_id=None,
        enabled=None,
        kind=None,
        tag=None,
        tags=None,
        search=None,
    )
    for item in page:
        if _safe_str(item.get("id")).strip() == resolved_id:
            return item
    return None


def _approval_matches_plugin_action(approval_record: dict[str, Any] | None, expected_payload: dict[str, Any]) -> bool:
    if not isinstance(approval_record, dict):
        return False

    approval_action = _safe_str(approval_record.get("action")).strip().lower()
    if approval_action and approval_action != "plugin.run":
        return False

    payload = approval_record.get("payload")
    if not isinstance(payload, dict):
        return False

    approved_payload = _plugin_approval_payload(
        plugin_id=_safe_str(payload.get("plugin_id")),
        action=_safe_str(payload.get("action")),
        risk_tier=_safe_str(payload.get("risk_tier")) or _safe_str(expected_payload.get("risk_tier")),
        required_trust=(
            int(payload.get("required_trust"))
            if isinstance(payload.get("required_trust"), (int, float))
            else int(expected_payload.get("required_trust") or 0)
        ),
        idempotency_key=_safe_str(payload.get("idempotency_key")),
        payload_input=payload.get("input"),
        meta=payload.get("meta"),
    )
    return approved_payload == expected_payload


def _find_plugin_by_source(registry: dict[str, Any], source_kind: str, source_ref: str) -> dict[str, Any] | None:
    plugins = registry.get("plugins")
    if not isinstance(plugins, dict):
        return None
    for plugin_id, raw in plugins.items():
        if not isinstance(raw, dict):
            continue
        item = _normalize_plugin_record(_safe_str(plugin_id), raw)
        if item.get("source_kind") == source_kind and item.get("source_ref") == source_ref:
            return item
    return None


class PluginBuildIn(BaseModel):
    name: str
    description: str = ""
    actor: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)


class PluginToggleIn(BaseModel):
    id: str
    reason: str = "requested"
    actor: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)


class PluginInstallIn(BaseModel):
    source_kind: str
    source_ref: str
    version: str | None = None
    ref: str | None = None
    sha256: str | None = None
    capabilities: list[dict[str, Any]] = Field(default_factory=list)
    reason: str = "requested"
    actor: str = ""
    dry_run: bool = False
    force: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)


class PluginUninstallIn(BaseModel):
    id: str
    reason: str = "requested"
    actor: str = ""
    force: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)


class PluginReloadIn(BaseModel):
    reason: str = "requested"
    actor: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)


class PluginRunIn(BaseModel):
    id: str
    action: str
    input: Any = None
    reason: str = "requested"
    approval_id: str | None = None
    idempotency_key: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class PluginToolRunIn(BaseModel):
    id: str
    input: Any = None
    reason: str = "requested"
    approval_id: str | None = None
    idempotency_key: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


@router.get("/status")
def status() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        plugins = registry.get("plugins")
        total = len(plugins) if isinstance(plugins, dict) else 0
        return {"ok": True, "route": "plugins", "status": "ready", "total": total, "catalog": catalog}
    except Exception as exc:
        return {"ok": False, "route": "plugins", "status": "error", "error": str(exc)}


@router.post("/build")
def build(payload: PluginBuildIn, request: Request) -> dict[str, object]:
    try:
        permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
        if not permission.allowed:
            return _permission_denied(permission)

        res = build_plugin(payload.name, payload.description)
        plugin_id = _validate_plugin_id(_safe_str(res.get("plugin_id")).strip())
        staged_ts = _now_s()
        build_meta = redact_governed_metadata(payload.meta)
        proposal_id = _plugin_proposal_id(plugin_id, staged_ts)
        proposal_path = _plugin_proposal_path(proposal_id)
        validation_receipt_id = _plugin_validation_receipt_id(plugin_id, staged_ts)
        validation_receipt_path = _plugin_validation_receipt_path(validation_receipt_id)
        artifact_zip = _safe_str(res.get("artifact_zip")).strip()
        spec_path = _safe_str(res.get("spec_path")).strip()
        registry_snapshot = _safe_str(res.get("registry_snapshot")).strip()
        validation = res.get("validation") if isinstance(res.get("validation"), dict) else {}

        registry = _load_registry()
        _write_plugin(
            registry,
            _normalize_plugin_record(
                plugin_id,
                {
                    "id": plugin_id,
                    "status": "staged",
                    "enabled": False,
                    "source_kind": "generated",
                    "source_ref": _safe_str(res.get("spec_path")).strip() or plugin_id,
                    "tags": ["generated", "staged"],
                    "meta": {
                        "promotion_status": "staged",
                        "proposal_id": proposal_id,
                        "proposal_path": str(proposal_path),
                        "validation_receipt_id": validation_receipt_id,
                        "validation_receipt_path": str(validation_receipt_path),
                        "proposal_evidence": build_meta.get("proposal_evidence") or build_meta.get("evidence") or [],
                        "proposal_status": "staged",
                        "risk_tier": _safe_str(build_meta.get("risk_tier")).strip().lower() or "normal",
                        "tests": build_meta.get("tests") or build_meta.get("test_refs") or [],
                        "docs": build_meta.get("docs") or build_meta.get("documentation") or [],
                        "known_limits": build_meta.get("known_limits") or build_meta.get("limits") or [],
                        "next_step": "review_validate_and_explicitly_enable_before_use",
                    },
                },
            ),
        )
        _ensure_plugin_from_generated(registry, plugin_id)
        catalog = _save_registry_and_catalog(registry)
        staged = _read_plugin(registry, plugin_id) or {}
        validation_receipt = _write_plugin_validation_receipt(
            plugin_id=plugin_id,
            validation_id=validation_receipt_id,
            validation_path=validation_receipt_path,
            proposal_id=proposal_id,
            proposal_path=proposal_path,
            payload=payload,
            staged_ts=staged_ts,
            artifact_zip=artifact_zip,
            spec_path=spec_path,
            registry_snapshot=registry_snapshot,
            validation=validation,
            catalog=catalog,
        )
        proposal_record = _write_plugin_proposal_record(
            plugin_id=plugin_id,
            proposal_id=proposal_id,
            proposal_path=proposal_path,
            staged=staged,
            payload=payload,
            staged_ts=staged_ts,
            artifact_zip=artifact_zip,
            spec_path=spec_path,
            registry_snapshot=registry_snapshot,
            validation=validation,
            validation_receipt=validation_receipt,
            catalog=catalog,
        )

        return {
            "ok": True,
            "plugin_id": plugin_id,
            "id": plugin_id,
            "status": "staged",
            "enabled": False,
            "promotion_status": "staged",
            "proposal_id": proposal_id,
            "proposal_path": str(proposal_path),
            "proposal": proposal_record,
            "validation_receipt_id": validation_receipt_id,
            "validation_receipt_path": str(validation_receipt_path),
            "validation_receipt": validation_receipt,
            "next_step": "review_validate_and_explicitly_enable_before_use",
            "artifact_zip": artifact_zip,
            "spec_path": spec_path,
            "registry_snapshot": registry_snapshot,
            "validation": validation,
            "catalog": catalog,
            "download_url": f"/plugins/download/{plugin_id}",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/download/{plugin_id}")
def download(plugin_id: str):
    try:
        normalized_id = _validate_plugin_id(plugin_id)
    except Exception:
        return {"ok": False, "error": "invalid_plugin_id"}

    path = _art_dir() / f"{normalized_id}.zip"
    if not path.exists():
        return {"ok": False, "error": "not_found"}
    return FileResponse(path, filename=path.name)


@router.get("/list")
def list_plugins(
    limit: int = 200,
    offset: int = 0,
    status: str | None = None,
    enabled: bool | None = None,
    source_kind: str | None = None,
    tag: str | None = None,
    tags: list[str] | None = None,
    search: str | None = None,
) -> dict[str, object]:
    try:
        safe_limit = max(1, min(int(limit), 5000))
        safe_offset = max(0, int(offset))
        status_filter = _safe_str(status).strip().lower()
        source_kind_filter = _safe_str(source_kind).strip().lower()
        search_filter = _safe_str(search).strip().lower()
        tag_filters = _parse_tags(tag)
        for extra in tags or []:
            normalized = _safe_str(extra).strip()
            if normalized and normalized not in tag_filters:
                tag_filters.append(normalized)

        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        if synced:
            _save_registry(registry)

        plugins_obj = registry.get("plugins")
        if not isinstance(plugins_obj, dict):
            plugins_obj = {}

        items: list[dict[str, Any]] = []
        for plugin_id, raw in plugins_obj.items():
            if not isinstance(raw, dict):
                continue
            item = _normalize_plugin_record(_safe_str(plugin_id), raw)
            if _match_plugin(item, status_filter, enabled, source_kind_filter, tag_filters, search_filter):
                items.append(item)

        items.sort(key=lambda item: (int(item.get("updated_ts") or 0), _safe_str(item.get("id"))), reverse=True)
        total = len(items)
        page = items[safe_offset : safe_offset + safe_limit]
        return {"items": page, "plugins": page, "total": total, "offset": safe_offset, "limit": safe_limit}
    except Exception as exc:
        return {"items": [], "plugins": [], "total": 0, "offset": 0, "limit": 0, "error": str(exc)}


@router.get("/get")
def get_plugin(id: str) -> dict[str, object]:
    try:
        plugin_id = _validate_plugin_id(id)
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        if synced:
            _save_registry(registry)

        item = _read_plugin(registry, plugin_id)
        if item is None:
            return {"ok": False, "error": "not_found", "item": None}

        details = _read_generated_details(plugin_id, item)
        if details:
            details_manifest = details.get("manifest")
            if isinstance(details_manifest, dict):
                item["manifest"] = details_manifest
            item["readme"] = _safe_str(details.get("readme")).strip()
            item["files"] = details.get("files") if isinstance(details.get("files"), list) else []
            if isinstance(details.get("contract"), dict) and details.get("contract"):
                item["contract"] = details.get("contract")
            if isinstance(details.get("registry_snapshot"), dict) and details.get("registry_snapshot"):
                item["registry_snapshot"] = details.get("registry_snapshot")
            item["runtime"] = {
                "entrypoint": _safe_str(details.get("entrypoint")).strip() or "plugin.py",
                "generated_dir": _safe_str(item.get("generated_dir")).strip(),
                "artifact_exists": bool(
                    _safe_str(item.get("artifact_zip")).strip() and Path(_safe_str(item.get("artifact_zip"))).exists()
                ),
                "spec_exists": bool(isinstance(details.get("contract"), dict) and details.get("contract")),
                "registry_snapshot_exists": bool(
                    isinstance(details.get("registry_snapshot"), dict) and details.get("registry_snapshot")
                ),
            }
        else:
            meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
            if isinstance(meta.get("contract"), dict) and meta.get("contract"):
                item["contract"] = meta.get("contract")
            item["runtime"] = {"generated_dir": _safe_str(item.get("generated_dir")).strip(), "artifact_exists": False}

        return {"ok": True, "item": item}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "item": None}


@router.get("/tools/list")
def list_plugin_tools(
    limit: int = 200,
    offset: int = 0,
    plugin_id: str | None = None,
    enabled: bool | None = None,
    kind: str | None = None,
    tag: str | None = None,
    tags: list[str] | None = None,
    search: str | None = None,
) -> dict[str, object]:
    try:
        if _safe_str(plugin_id).strip():
            _validate_plugin_id(_safe_str(plugin_id).strip())
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        if synced:
            _save_registry(registry)
        safe_limit = max(1, min(int(limit), 5000))
        safe_offset = max(0, int(offset))
        page, total = _query_tools(
            registry=registry,
            limit=safe_limit,
            offset=safe_offset,
            plugin_id=plugin_id,
            enabled=enabled,
            kind=kind,
            tag=tag,
            tags=tags,
            search=search,
        )
        return {"items": page, "tools": page, "total": total, "offset": safe_offset, "limit": safe_limit}
    except Exception as exc:
        return {"items": [], "tools": [], "total": 0, "offset": 0, "limit": 0, "error": str(exc)}


@router.get("/tools/get")
def get_plugin_tool(id: str) -> dict[str, object]:
    try:
        tool_id = _safe_str(id).strip()
        if not tool_id:
            return {"ok": False, "error": "tool_id_required", "item": None}

        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        if synced:
            _save_registry(registry)

        page, _ = _query_tools(
            registry=registry,
            limit=100_000,
            offset=0,
            plugin_id=None,
            enabled=None,
            kind=None,
            tag=None,
            tags=None,
            search=None,
        )
        for item in page:
            if _safe_str(item.get("id")).strip() == tool_id:
                return {"ok": True, "item": item}
        return {"ok": False, "error": "not_found", "item": None}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "item": None}


@router.get("/tools/export")
def export_plugin_tools(
    format: str = "json",
    plugin_id: str | None = None,
    enabled: bool | None = None,
    kind: str | None = None,
    tag: str | None = None,
    tags: list[str] | None = None,
    search: str | None = None,
) -> PlainTextResponse:
    registry = _load_registry()
    synced = _sync_generated_plugins(registry)
    if synced:
        _save_registry(registry)
    items, _ = _query_tools(
        registry=registry,
        limit=100_000,
        offset=0,
        plugin_id=plugin_id,
        enabled=enabled,
        kind=kind,
        tag=tag,
        tags=tags,
        search=search,
    )

    fmt = _safe_str(format).strip().lower() or "json"
    if fmt == "jsonl":
        content = "\n".join(json.dumps(item, ensure_ascii=False, default=str) for item in items)
        return PlainTextResponse(content=content, media_type="application/jsonl")

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "id",
                "plugin_id",
                "plugin_name",
                "name",
                "action",
                "kind",
                "enabled",
                "status",
                "source_kind",
                "risk_tier",
                "description",
                "tags",
            ],
        )
        writer.writeheader()
        for item in items:
            writer.writerow(
                {
                    "id": item.get("id"),
                    "plugin_id": item.get("plugin_id"),
                    "plugin_name": item.get("plugin_name"),
                    "name": item.get("name"),
                    "action": item.get("action"),
                    "kind": item.get("kind"),
                    "enabled": item.get("enabled"),
                    "status": item.get("status"),
                    "source_kind": item.get("source_kind"),
                    "risk_tier": item.get("risk_tier"),
                    "description": item.get("description"),
                    "tags": ",".join(_parse_tags(item.get("tags"))),
                }
            )
        return PlainTextResponse(content=output.getvalue(), media_type="text/csv")

    content = json.dumps({"items": items}, indent=2, ensure_ascii=False, default=str)
    return PlainTextResponse(content=content, media_type="application/json")


@router.post("/tools/run")
def run_plugin_tool(payload: PluginToolRunIn) -> dict[str, object]:
    try:
        tool_id = _safe_str(payload.id).strip()
        if not tool_id:
            return {"ok": False, "error": "tool_id_required", "status": "error"}

        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        if synced:
            _save_registry(registry)
        tool = _find_tool_by_id(registry, tool_id)
        if not isinstance(tool, dict):
            return {"ok": False, "error": "not_found", "status": "error", "tool_id": tool_id}

        plugin_id = _safe_str(tool.get("plugin_id")).strip()
        action = _safe_str(tool.get("action")).strip() or "run"
        if not plugin_id:
            return {"ok": False, "error": "invalid_tool", "status": "error", "tool_id": tool_id}
        run_payload = PluginRunIn(
            id=plugin_id,
            action=action,
            input=payload.input,
            reason=payload.reason,
            approval_id=payload.approval_id,
            idempotency_key=payload.idempotency_key,
            meta=dict(payload.meta or {}),
        )
        result = run_plugin(run_payload)
        if isinstance(result, dict):
            out = dict(result)
            out["tool_id"] = tool_id
            meta = out.get("meta")
            if isinstance(meta, dict):
                merged = dict(meta)
                merged["tool_action"] = action
                out["meta"] = merged
            else:
                out["meta"] = {"tool_action": action}
            return out
        return {"ok": False, "error": "unexpected_result_type", "status": "error", "tool_id": tool_id}
    except Exception as exc:
        return {"ok": False, "status": "error", "error": str(exc)}


@router.post("/enable")
def enable_plugin(payload: PluginToggleIn, request: Request) -> dict[str, object]:
    try:
        permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
        if not permission.allowed:
            return _permission_denied(permission)

        plugin_id = _validate_plugin_id(payload.id)
        registry = _load_registry()
        _sync_generated_plugins(registry)
        current = _read_plugin(registry, plugin_id)
        if current is None:
            return {"ok": False, "error": "not_found", "id": plugin_id}

        previous = dict(current)
        was_staged = _safe_str(previous.get("status")).strip().lower() == "staged"
        promoted_ts = _now_s()
        promotion_receipt_id = ""
        promotion_receipt_path = Path()
        if was_staged:
            readiness = _plugin_promotion_readiness(plugin_id, previous, payload)
            if not readiness["ready"]:
                return _promotion_readiness_blocked(
                    plugin_id=plugin_id,
                    staged=previous,
                    readiness=readiness,
                )
            promotion_receipt_id = _plugin_promotion_receipt_id(plugin_id, promoted_ts)
            promotion_receipt_path = _plugin_promotion_receipt_path(promotion_receipt_id)
            tags = [tag for tag in _parse_tags(current.get("tags")) if tag != "staged"]
            if "promoted" not in tags:
                tags.append("promoted")
            current["tags"] = tags
            meta = dict(current.get("meta") or {}) if isinstance(current.get("meta"), dict) else {}
            meta.update(
                {
                    "promotion_status": "promoted",
                    "promotion_receipt_id": promotion_receipt_id,
                    "promotion_receipt_path": str(promotion_receipt_path),
                    "promoted_ts": promoted_ts,
                    "promoted_by": redact_governed_value(_safe_str(payload.actor).strip()),
                }
            )
            current["meta"] = meta

        current["enabled"] = True
        current["status"] = "enabled"
        current["updated_ts"] = promoted_ts
        promoted = _normalize_plugin_record(plugin_id, current)
        _write_plugin(registry, promoted)
        catalog = _save_registry_and_catalog(registry)

        out: dict[str, object] = {
            "ok": True,
            "id": plugin_id,
            "enabled": True,
            "status": "enabled",
            "message": "enabled",
            "catalog": catalog,
        }
        if was_staged:
            promotion_receipt = _write_plugin_promotion_receipt(
                plugin_id=plugin_id,
                receipt_id=promotion_receipt_id,
                receipt_path=promotion_receipt_path,
                previous=previous,
                promoted=promoted,
                payload=payload,
                promoted_ts=promoted_ts,
                catalog=catalog,
            )
            out["promotion_status"] = "promoted"
            out["promotion_receipt_id"] = promotion_receipt_id
            out["promotion_receipt"] = promotion_receipt
        return out
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/disable")
def disable_plugin(payload: PluginToggleIn, request: Request) -> dict[str, object]:
    try:
        permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
        if not permission.allowed:
            return _permission_denied(permission)

        plugin_id = _validate_plugin_id(payload.id)
        registry = _load_registry()
        _sync_generated_plugins(registry)
        current = _read_plugin(registry, plugin_id)
        if current is None:
            return {"ok": False, "error": "not_found", "id": plugin_id}

        current["enabled"] = False
        current["status"] = "disabled"
        current["updated_ts"] = _now_s()
        _write_plugin(registry, _normalize_plugin_record(plugin_id, current))
        catalog = _save_registry_and_catalog(registry)

        return {
            "ok": True,
            "id": plugin_id,
            "enabled": False,
            "status": "disabled",
            "message": "disabled",
            "catalog": catalog,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/install")
def install_plugin(payload: PluginInstallIn, request: Request) -> dict[str, object]:
    try:
        permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
        if not permission.allowed:
            return _permission_denied(permission)

        source_kind = _safe_str(payload.source_kind).strip().lower()
        source_ref = _safe_str(payload.source_ref).strip()
        if not source_kind:
            return {"ok": False, "error": "source_kind_required"}
        if not source_ref:
            return {"ok": False, "error": "source_ref_required"}

        registry = _load_registry()
        _sync_generated_plugins(registry)
        existing = _find_plugin_by_source(registry, source_kind, source_ref)
        if existing is not None and not payload.force:
            return {
                "ok": True,
                "plugin_id": existing["id"],
                "id": existing["id"],
                "status": existing.get("status", "enabled"),
                "message": "already_installed",
            }

        if payload.dry_run:
            preview_spec = _build_install_contract_spec(
                _validate_plugin_id(
                    f"{int(time.time())}_{_slugify(source_ref.split('/')[-1] if '/' in source_ref else source_ref)}"
                ),
                payload,
            )
            validation = _PLUGIN_VALIDATOR.validate(preview_spec)
            return {
                "ok": validation.valid,
                "status": "installing" if validation.valid else "error",
                "message": "validated" if validation.valid else "invalid_plugin_spec",
                "validation": validation.to_dict(),
            }

        if existing is not None and payload.force:
            plugin_id = _validate_plugin_id(_safe_str(existing.get("id")).strip())
        else:
            seed = _slugify(source_ref.split("/")[-1] if "/" in source_ref else source_ref)
            plugin_id = _validate_plugin_id(f"{int(time.time())}_{seed}")

        spec = _build_install_contract_spec(plugin_id, payload)
        validation = _PLUGIN_VALIDATOR.validate(spec)
        if not validation.valid:
            return {
                "ok": False,
                "error": "invalid_plugin_spec",
                "validation": validation.to_dict(),
                "plugin_id": plugin_id,
            }

        now_s = _now_s()
        current = existing if isinstance(existing, dict) else {}
        record = _normalize_plugin_record(
            plugin_id,
            {
                **current,
                "id": plugin_id,
                "name": spec.name,
                "version": spec.version,
                "status": "enabled",
                "enabled": True,
                "description": spec.description,
                "source_kind": source_kind,
                "source_ref": source_ref,
                "installed_ts": int(current.get("installed_ts") if current else now_s),
                "updated_ts": now_s,
                "tags": _merge_unique_tags(["installed"], list(spec.capabilities)),
                "capabilities": _capabilities_from_contract(plugin_id, spec),
                "meta": {
                    **(dict(spec.metadata) if isinstance(spec.metadata, dict) else {}),
                    "entrypoint": spec.entrypoint,
                    "sandbox_profile": spec.sandbox_profile,
                    "permissions": spec.permissions,
                    "constraints": spec.constraints,
                    "telemetry": spec.telemetry,
                    "compatibility": spec.compatibility,
                    "attestation": spec.attestation,
                    "contract": _contract_summary_from_spec(spec),
                },
            },
        )
        _write_plugin(registry, record)
        catalog = _save_registry_and_catalog(registry)
        return {
            "ok": True,
            "plugin_id": plugin_id,
            "id": plugin_id,
            "status": "enabled",
            "message": "installed",
            "validation": validation.to_dict(),
            "catalog": catalog,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/uninstall")
def uninstall_plugin(payload: PluginUninstallIn, request: Request) -> dict[str, object]:
    try:
        permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
        if not permission.allowed:
            return _permission_denied(permission)

        plugin_id = _validate_plugin_id(payload.id)
        registry = _load_registry()
        _sync_generated_plugins(registry)
        current = _read_plugin(registry, plugin_id)
        if current is None:
            return {"ok": False, "error": "not_found", "id": plugin_id}

        generated_dir = _safe_str(current.get("generated_dir")).strip()
        artifact_zip = _safe_str(current.get("artifact_zip")).strip()

        if generated_dir:
            generated_path = Path(generated_dir)
            if generated_path.exists() and _is_under(_gen_dir(), generated_path):
                shutil.rmtree(generated_path, ignore_errors=True)

        if artifact_zip:
            artifact_path = Path(artifact_zip)
            if artifact_path.exists() and _is_under(_art_dir(), artifact_path):
                try:
                    artifact_path.unlink()
                except OSError:
                    pass

        _delete_plugin(registry, plugin_id)
        catalog = _save_registry_and_catalog(registry)
        return {"ok": True, "id": plugin_id, "status": "uninstalled", "message": "uninstalled", "catalog": catalog}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/run")
def run_plugin(payload: PluginRunIn) -> dict[str, object]:
    try:
        plugin_id = _validate_plugin_id(payload.id)
        requested_action = _safe_str(payload.action).strip()
        if not requested_action:
            return {"ok": False, "error": "action_required"}

        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        if synced:
            _save_registry(registry)
        current = _read_plugin(registry, plugin_id)
        if current is None:
            return {"ok": False, "error": "not_found", "id": plugin_id, "status": "error"}
        if not bool(current.get("enabled", False)):
            current_status = _safe_str(current.get("status")).strip() or "disabled"
            error = "plugin_staged" if current_status == "staged" else "plugin_disabled"
            return {"ok": False, "error": error, "id": plugin_id, "status": current_status}
        action = _resolve_plugin_action(current, requested_action)
        if not action:
            return {
                "ok": False,
                "error": "unsupported_action",
                "id": plugin_id,
                "status": "error",
                "supported_actions": _plugin_actions(current),
            }

        capability = _find_capability_for_action(current, action)
        cap_meta = capability.get("meta") if isinstance(capability.get("meta"), dict) else {}
        risk_tier = _safe_str(cap_meta.get("risk_tier")).strip().lower() or "normal"
        required_trust = _required_trust_for_capability(capability, risk_tier)
        trust_level = _current_trust_level()
        if trust_level < required_trust:
            return {
                "ok": False,
                "error": "insufficient_trust",
                "id": plugin_id,
                "status": "blocked",
                "required_trust": required_trust,
                "current_trust": trust_level,
                "message": f"Trust level {trust_level} is below the required level {required_trust}.",
                "governance": _plugin_governance(
                    gate="trust_gate",
                    next_step="raise_trust_or_reduce_risk",
                    operator_hint=f"Raise trust to {required_trust} or choose a lower-risk action.",
                    action=action,
                    risk_tier=risk_tier,
                    required_trust=required_trust,
                    current_trust=trust_level,
                ),
                "meta": {"action": action, "risk_tier": risk_tier},
            }

        force = _to_bool((payload.meta or {}).get("force"), default=False)
        approval_required = _approval_required_for_capability(capability, risk_tier)
        approval_id = _plugin_run_approval_id(payload)
        request_payload = _plugin_approval_payload(
            plugin_id=plugin_id,
            action=action,
            risk_tier=risk_tier,
            required_trust=required_trust,
            idempotency_key=_safe_str(payload.idempotency_key).strip(),
            payload_input=payload.input,
            meta=payload.meta,
        )
        approval_reason = _safe_str(payload.reason).strip() or "requested"
        if approval_required and not force:
            if not approval_id:
                created_id, art = _request_plugin_approval(
                    plugin_id=plugin_id,
                    action=action,
                    request_payload=request_payload,
                    reason=approval_reason,
                )
                return {
                    "ok": True,
                    "id": plugin_id,
                    "status": "pending",
                    "approval_id": created_id,
                    "artifact_dir": str(art),
                    "message": "Plugin action requires approval.",
                    "governance": _plugin_governance(
                        gate="approvals_gate",
                        next_step="review_pending_approval",
                        operator_hint="Open approvals and review this plugin action before rerunning it.",
                        action=action,
                        risk_tier=risk_tier,
                        required_trust=required_trust,
                        current_trust=trust_level,
                        approval_status="pending",
                    ),
                    "meta": {"action": action, "risk_tier": risk_tier, "required_trust": required_trust},
                }

            approval_status, approval_record = _approval_status(approval_id)
            if approval_status in {"missing", "corrupt"}:
                refreshed_id, art = _request_plugin_approval(
                    plugin_id=plugin_id,
                    action=action,
                    request_payload=request_payload,
                    reason=approval_reason,
                    previous_approval_id=approval_id,
                    previous_status=approval_status,
                    previous_record=approval_record,
                )
                _atomic_write_display_json(
                    art / "error.json",
                    {
                        "kind": "plugin.run.error",
                        "approval_id": refreshed_id,
                        "previous_approval_id": approval_id,
                        "plugin_id": plugin_id,
                        "action": action,
                        "status": approval_status,
                    },
                )
                return {
                    "ok": False,
                    "id": plugin_id,
                    "status": "needs_approval",
                    "error": "approval_not_found",
                    "approval_id": refreshed_id,
                    "previous_approval_id": approval_id,
                    "artifact_dir": str(art),
                    "message": "Approval was missing for this plugin action; a fresh exact-action approval is required.",
                    "governance": _plugin_governance(
                        gate="approvals_gate",
                        next_step="approve_exact_action",
                        operator_hint="Approve the refreshed plugin action request before rerunning it.",
                        action=action,
                        risk_tier=risk_tier,
                        required_trust=required_trust,
                        current_trust=trust_level,
                    ),
                    "meta": {"action": action, "risk_tier": risk_tier, "required_trust": required_trust},
                }
            if approval_status == "pending":
                return {
                    "ok": True,
                    "id": plugin_id,
                    "status": "pending",
                    "approval_id": approval_id,
                    "message": "Plugin action is awaiting approval.",
                    "governance": _plugin_governance(
                        gate="approvals_gate",
                        next_step="review_pending_approval",
                        operator_hint="This action is still waiting on approval. Review or approve it before rerunning.",
                        action=action,
                        risk_tier=risk_tier,
                        required_trust=required_trust,
                        current_trust=trust_level,
                        approval_status="pending",
                    ),
                    "meta": {"action": action, "risk_tier": risk_tier, "required_trust": required_trust},
                }
            if approval_status in {"rejected", "emergency"}:
                return {
                    "ok": False,
                    "id": plugin_id,
                    "status": "denied",
                    "error": "approval_denied",
                    "approval_id": approval_id,
                    "message": "Approval was denied for this plugin action.",
                    "governance": _plugin_governance(
                        gate="approvals_gate",
                        next_step="request_new_approval_or_change_scope",
                        operator_hint="Request a new approval or narrow the requested action before rerunning.",
                        action=action,
                        risk_tier=risk_tier,
                        required_trust=required_trust,
                        current_trust=trust_level,
                        approval_status=approval_status,
                    ),
                    "meta": {
                        "action": action,
                        "risk_tier": risk_tier,
                        "required_trust": required_trust,
                        "approval_status": approval_status,
                        "approval": approval_record if isinstance(approval_record, dict) else {},
                    },
                }
            if approval_status != "approved":
                return {
                    "ok": False,
                    "id": plugin_id,
                    "status": "needs_approval",
                    "error": "approval_not_found",
                    "approval_id": approval_id,
                    "message": "A matching approved request was not found for this plugin action.",
                    "governance": _plugin_governance(
                        gate="approvals_gate",
                        next_step="provide_matching_approval",
                        operator_hint="Use a valid approval for this exact action or request a new approval.",
                        action=action,
                        risk_tier=risk_tier,
                        required_trust=required_trust,
                        current_trust=trust_level,
                    ),
                    "meta": {"action": action, "risk_tier": risk_tier, "required_trust": required_trust},
                }
            if not _approval_matches_plugin_action(approval_record, request_payload):
                refreshed_id, art = _request_plugin_approval(
                    plugin_id=plugin_id,
                    action=action,
                    request_payload=request_payload,
                    reason=approval_reason,
                    previous_approval_id=approval_id,
                    previous_status=approval_status,
                    previous_record=approval_record,
                )
                _atomic_write_display_json(
                    art / "mismatch.json",
                    {
                        "kind": "plugin.run.mismatch",
                        "approval_id": refreshed_id,
                        "previous_approval_id": approval_id,
                        "plugin_id": plugin_id,
                        "action": action,
                        "expected_payload": request_payload,
                        "approval_record": approval_record,
                    },
                )
                _atomic_write_display_json(
                    _plugin_approval_artifact_dir(approval_id) / "mismatch.json",
                    {
                        "kind": "plugin.run.mismatch",
                        "approval_id": approval_id,
                        "plugin_id": plugin_id,
                        "action": action,
                        "expected_payload": request_payload,
                        "approval_record": approval_record,
                    },
                )
                return {
                    "ok": False,
                    "id": plugin_id,
                    "status": "needs_approval",
                    "error": "approval_payload_mismatch",
                    "approval_id": refreshed_id,
                    "previous_approval_id": approval_id,
                    "artifact_dir": str(art),
                    "message": "Approval does not match this exact plugin action request.",
                    "governance": _plugin_governance(
                        gate="approvals_gate",
                        next_step="approve_exact_action",
                        operator_hint="Approve this exact plugin action, not a different tool or payload.",
                        action=action,
                        risk_tier=risk_tier,
                        required_trust=required_trust,
                        current_trust=trust_level,
                        approval_status=approval_status,
                    ),
                    "meta": {
                        "action": action,
                        "risk_tier": risk_tier,
                        "required_trust": required_trust,
                        "approval_status": approval_status,
                    },
                }

        dry_run = _to_bool((payload.meta or {}).get("dry_run"), default=False)
        receipt = _redact_plugin_receipt(_execute_plugin_action(current, capability, payload.input, dry_run=dry_run))
        current["updated_ts"] = _now_s()
        _write_plugin(registry, _normalize_plugin_record(plugin_id, current))
        _save_registry_and_catalog(registry)
        if not receipt.get("ok"):
            return {
                "ok": False,
                "id": plugin_id,
                "status": _safe_str(receipt.get("status")).strip() or "error",
                "error": _safe_str(receipt.get("error")).strip() or "plugin_execution_failed",
                "receipt": receipt,
                "meta": {
                    "action": action,
                    "risk_tier": risk_tier,
                    "required_trust": required_trust,
                    "current_trust": trust_level,
                },
            }
        return {
            "ok": True,
            "id": plugin_id,
            "status": _safe_str(receipt.get("status")).strip() or "ok",
            "output": receipt.get("output"),
            "receipt": receipt,
            "meta": {
                "action": action,
                "risk_tier": risk_tier,
                "required_trust": required_trust,
                "current_trust": trust_level,
                "tool_name": _safe_str((cap_meta or {}).get("tool_name")).strip()
                or _safe_str(capability.get("id")).strip(),
            },
        }
    except Exception as exc:
        return {"ok": False, "status": "error", "error": str(exc)}


@router.post("/reload")
def reload_plugins(request: Request, payload: PluginReloadIn | None = None) -> dict[str, object]:
    try:
        actor = payload.actor if payload is not None else ""
        permission = _write_permission(actor, route=request.url.path, method=request.method)
        if not permission.allowed:
            return _permission_denied(permission)

        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry)
        plugins = registry.get("plugins")
        total = len(plugins) if isinstance(plugins, dict) else 0
        return {"ok": True, "message": "reloaded", "synced": synced, "total": total, "catalog": catalog}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
