from __future__ import annotations

from francis.api.errors import api_error_message
import csv
from dataclasses import replace
import importlib.util
import io
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from francis.economy.markets.capability_catalog_coherence import analyze_capability_catalog_coherence
from francis.economy.markets.capability_catalog_projection import marketplace_from_plugin_catalog
from francis.economy.markets.capability_pack_lineage import analyze_capability_pack_lineage
from francis.economy.markets.capability_pack_migration_plan import analyze_capability_pack_migration_plan
from francis.economy.markets.capability_pack_operator_review import analyze_capability_pack_operator_review
from francis.economy.markets.capability_pack_promotion_discipline import analyze_capability_pack_promotion_discipline
from francis.economy.markets.capability_pack_promotion_receipts import analyze_capability_pack_promotion_receipts
from francis.economy.markets.capability_pack_promotion_rules import (
    analyze_capability_pack_promotion_rule_remediation,
    analyze_capability_pack_promotion_rules,
    canonical_capability_pack_promotion_rules,
)
from francis.economy.markets.capability_pack_quality_docs import analyze_capability_pack_quality_docs
from francis.economy.markets.capability_pack_quality_standards import analyze_capability_pack_quality_standards
from francis.economy.markets.capability_pack_quality_tests import analyze_capability_pack_quality_tests
from francis.economy.markets.capability_pack_readiness import analyze_capability_pack_readiness
from francis.economy.markets.capability_pack_validation_receipts import analyze_capability_pack_validation_receipts
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
_CAPABILITY_PACK_OPERATOR_REVIEW_DECISIONS = {
    "approve": "approved",
    "approved": "approved",
    "reject": "rejected",
    "rejected": "rejected",
    "deny": "rejected",
    "denied": "rejected",
    "defer": "deferred",
    "deferred": "deferred",
}
_CAPABILITY_PACK_REMEDIATION_METADATA_BLOCKERS = {
    "pack_metadata_receipt_missing",
    "promotion_rules_missing",
    "canonical_promotion_rules_missing",
    "pack_governance_missing",
}
_CAPABILITY_PACK_QUALITY_EVIDENCE_BLOCKERS = {
    "tests_missing",
    "docs_missing",
    "validation_receipt_missing",
    "proposal_id_missing",
}
_CAPABILITY_PACK_QUALITY_EVIDENCE_QUEUE_LIMIT = 50
_CAPABILITY_PACK_ARTIFACT_RECONSTRUCTION_PLAN_LIMIT = 25
_PLUGIN_ARTIFACT_LINK_BODY_MAX_BYTES = 256 * 1024
_CAPABILITY_PACK_QUALITY_TEST_REFERENCE_CANDIDATES = ("tests/test_api_plugins.py",)
_CAPABILITY_PACK_QUALITY_DOC_REFERENCE_CANDIDATES = (
    "README.md",
    "docs/operations/COMPLETION_LEDGER.md",
)


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


def _real_path(value: str | Path) -> Path:
    return Path(os.path.realpath(os.fspath(value)))


def _resolve_under(root: Path, raw: str | Path, *, relative_to_root: bool = True) -> Path | None:
    text = _safe_str(raw).strip()
    if not text or any(ch in text for ch in ("\x00", "\n", "\r")):
        return None
    root_resolved = _real_path(root)
    candidate = text
    if relative_to_root and not os.path.isabs(candidate):
        candidate = os.path.join(os.fspath(root_resolved), candidate)
    try:
        resolved = _real_path(candidate)
    except OSError:
        return None
    return resolved if _is_under(root_resolved, resolved) else None


def _same_path(left: Path, right: Path) -> bool:
    try:
        left_text = os.path.normcase(os.path.realpath(os.fspath(left)))
        right_text = os.path.normcase(os.path.realpath(os.fspath(right)))
        return left_text == right_text
    except OSError:
        return False


def _generated_plugin_dir(plugin_id: str, generated_dir: str = "") -> Path | None:
    try:
        normalized_id = _validate_plugin_id(plugin_id)
    except Exception:
        return None
    root = _real_path(_gen_dir())
    expected = _real_path(root / normalized_id)
    raw = _safe_str(generated_dir).strip()
    if not raw:
        return expected
    resolved = _resolve_under(root, raw)
    return expected if resolved is not None and _same_path(resolved, expected) else None


def _plugin_artifact_path(plugin_id: str, artifact_zip: str = "") -> Path | None:
    try:
        normalized_id = _validate_plugin_id(plugin_id)
    except Exception:
        return None
    root = _real_path(_art_dir())
    expected = _real_path(root / f"{normalized_id}.zip")
    raw = _safe_str(artifact_zip).strip()
    if not raw:
        return expected
    resolved = _resolve_under(root, raw)
    return expected if resolved is not None and _same_path(resolved, expected) else None


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
    meta = plugin.get("meta") if isinstance(plugin.get("meta"), dict) else {}
    generated_dir = _safe_str(plugin.get("generated_dir")).strip()
    if generated_dir:
        plugin_dir = _generated_plugin_dir(plugin_id, generated_dir)
        if plugin_dir is not None and plugin_dir.exists():
            contract = _load_generated_contract(plugin_dir)
            if contract is not None:
                return replace(contract, metadata={**dict(contract.metadata), **dict(meta)})

    capabilities = _capabilities_for_plugin(plugin_id, plugin.get("capabilities"))
    tools = tuple(
        _tool_spec_from_capability(plugin_id, capability) for capability in capabilities if isinstance(capability, dict)
    )
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


def _capability_pack_operator_review_required(meta: dict[str, Any]) -> bool:
    rules = _unique_texts(meta.get("promotion_rules") or meta.get("promotion_rule_ids"), limit=50)
    governance = meta.get("pack_governance") or meta.get("capability_pack_governance")
    governance_obj = governance if isinstance(governance, dict) else {}
    return (
        "operator_review_before_promotion" in rules
        or "explicit_operator_review_before_promotion" in rules
        or "operator_review_required_before_promotion" in rules
        or _to_bool(governance_obj.get("operator_review_required"), default=False)
        or _to_bool(governance_obj.get("requires_operator_review"), default=False)
        or _to_bool(governance_obj.get("approval_required"), default=False)
    )


def _capability_pack_operator_review_state(plugin_id: str, meta: dict[str, Any]) -> dict[str, Any]:
    required = _capability_pack_operator_review_required(meta)
    pack_id = _safe_str(meta.get("pack_id") or meta.get("capability_pack_id")).strip()
    pack_version = _safe_str(meta.get("pack_version") or meta.get("capability_pack_version")).strip()
    if not required:
        return {
            "required": False,
            "status": "not_required",
            "review_status": "not_required",
            "receipt_id": "",
            "approved": True,
            "pack_id": pack_id,
            "pack_version": pack_version,
        }
    if not pack_id:
        return {
            "required": True,
            "status": "pack_id_missing",
            "review_status": "pack_id_missing",
            "receipt_id": "",
            "approved": False,
            "pack_id": "",
            "pack_version": pack_version,
        }
    if not pack_version:
        return {
            "required": True,
            "status": "pack_version_missing",
            "review_status": "pack_version_missing",
            "receipt_id": "",
            "approved": False,
            "pack_id": pack_id,
            "pack_version": "",
        }

    capability_id = _safe_str(plugin_id).strip()
    for receipt in _read_capability_pack_operator_review_decisions(limit=500):
        if _safe_str(receipt.get("pack_id")).strip() != pack_id:
            continue
        if _safe_str(receipt.get("pack_version")).strip() != pack_version:
            continue
        capability_ids = _unique_texts(receipt.get("capability_ids"), limit=500)
        if capability_id and capability_id not in capability_ids:
            continue
        status = _safe_str(receipt.get("status")).strip().lower() or "unknown"
        receipt_id = _safe_str(receipt.get("receipt_id")).strip()
        approved = status == "approved" and bool(receipt_id)
        return {
            "required": True,
            "status": status,
            "review_status": status,
            "receipt_id": receipt_id,
            "approved": approved,
            "pack_id": pack_id,
            "pack_version": pack_version,
            "decided_ts": int(receipt.get("decided_ts") or 0),
        }
    return {
        "required": True,
        "status": "missing",
        "review_status": "missing",
        "receipt_id": "",
        "approved": False,
        "pack_id": pack_id,
        "pack_version": pack_version,
    }


def _plugin_promotion_receipt_path(receipt_id: str) -> Path:
    return _art_dir() / "promotions" / f"{_safe_str(receipt_id).strip()}.json"


def _plugin_promotion_receipt_id(plugin_id: str, promoted_ts: int) -> str:
    return f"plugin_promotion_{promoted_ts}_{_slugify(plugin_id)}"


def _capability_pack_metadata_receipt_id(pack_id: str, recorded_ts: int) -> str:
    return f"capability_pack_metadata_{recorded_ts}_{_slugify(pack_id)}"


def _capability_pack_metadata_receipt_path(receipt_id: str) -> Path:
    return _art_dir() / "capability_packs" / "metadata_receipts" / f"{_safe_str(receipt_id).strip()}.json"


def _capability_pack_operator_review_receipt_id(pack_id: str, decided_ts: int) -> str:
    nonce = time.time_ns() % 1_000_000
    return f"capability_pack_operator_review_{decided_ts}_{_slugify(pack_id)}_{nonce:06d}"


def _capability_pack_operator_review_receipt_path(receipt_id: str) -> Path:
    return _art_dir() / "capability_packs" / "operator_review_decisions" / f"{_safe_str(receipt_id).strip()}.json"


def _read_capability_pack_operator_review_decisions(*, limit: int = 50) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit or 50), 500))
    folder = _art_dir() / "capability_packs" / "operator_review_decisions"
    folder_fs_path = _filesystem_path(folder)
    if not os.path.isdir(folder_fs_path):
        return []

    items: list[dict[str, Any]] = []
    receipt_files: list[tuple[float, str]] = []
    try:
        for entry in os.scandir(folder_fs_path):
            if not entry.name.endswith(".json") or not entry.is_file():
                continue
            receipt_files.append((entry.stat().st_mtime, entry.path))
    except OSError:
        return []

    for _, path in sorted(receipt_files, key=lambda item: item[0], reverse=True)[:safe_limit]:
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                payload = json.load(handle)
        except Exception:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _read_capability_pack_metadata_receipts(*, limit: int = 20) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit or 20), 200))
    folder = _art_dir() / "capability_packs" / "metadata_receipts"
    folder_fs_path = _filesystem_path(folder)
    if not os.path.isdir(folder_fs_path):
        return []

    items: list[dict[str, Any]] = []
    receipt_files: list[tuple[float, str]] = []
    try:
        for entry in os.scandir(folder_fs_path):
            if not entry.name.endswith(".json") or not entry.is_file():
                continue
            receipt_files.append((entry.stat().st_mtime, entry.path))
    except OSError:
        return []

    for _, path in sorted(receipt_files, key=lambda item: item[0]):
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                payload = json.load(handle)
        except Exception:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return items[-safe_limit:]


def _available_capability_pack_validation_receipts() -> dict[str, set[str]]:
    folder = _art_dir() / "validations"
    folder_fs_path = _filesystem_path(folder)
    if not os.path.isdir(folder_fs_path):
        return {"ids": set(), "paths": set()}

    ids: set[str] = set()
    paths: set[str] = set()
    try:
        for entry in os.scandir(folder_fs_path):
            if not entry.name.endswith(".json") or not entry.is_file():
                continue
            receipt_id = entry.name[:-5].strip()
            if not receipt_id:
                continue
            ids.add(receipt_id)
            paths.add(entry.path)
            paths.add(str(folder / entry.name))
            paths.add(f"validations/{entry.name}")
            paths.add(f"artifacts/plugins/validations/{entry.name}")
            paths.add(f"data/artifacts/plugins/validations/{entry.name}")
    except OSError:
        return {"ids": set(), "paths": set()}
    return {"ids": ids, "paths": paths}


def _available_capability_pack_proposals() -> dict[str, set[str]]:
    folder = _art_dir() / "proposals"
    folder_fs_path = _filesystem_path(folder)
    if not os.path.isdir(folder_fs_path):
        return {"ids": set(), "paths": set()}

    ids: set[str] = set()
    paths: set[str] = set()
    try:
        for entry in os.scandir(folder_fs_path):
            if not entry.name.endswith(".json") or not entry.is_file():
                continue
            proposal_id = entry.name[:-5].strip()
            if not proposal_id:
                continue
            ids.add(proposal_id)
            paths.add(entry.path)
            paths.add(str(folder / entry.name))
            paths.add(f"proposals/{entry.name}")
            paths.add(f"artifacts/plugins/proposals/{entry.name}")
            paths.add(f"data/artifacts/plugins/proposals/{entry.name}")
    except OSError:
        return {"ids": set(), "paths": set()}
    return {"ids": ids, "paths": paths}


def _available_capability_pack_promotion_receipts() -> dict[str, set[str]]:
    folder = _art_dir() / "promotions"
    folder_fs_path = _filesystem_path(folder)
    if not os.path.isdir(folder_fs_path):
        return {"ids": set(), "paths": set()}

    ids: set[str] = set()
    paths: set[str] = set()
    try:
        for entry in os.scandir(folder_fs_path):
            if not entry.name.endswith(".json") or not entry.is_file():
                continue
            receipt_id = entry.name[:-5].strip()
            if not receipt_id:
                continue
            ids.add(receipt_id)
            paths.add(entry.path)
            paths.add(str(folder / entry.name))
            paths.add(f"promotions/{entry.name}")
            paths.add(f"artifacts/plugins/promotions/{entry.name}")
            paths.add(f"data/artifacts/plugins/promotions/{entry.name}")
    except OSError:
        return {"ids": set(), "paths": set()}
    return {"ids": ids, "paths": paths}


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
    plugin_dir = _generated_plugin_dir(plugin_id, generated_dir)
    readme_path = _generated_child_path(plugin_dir, "README.md") if plugin_dir is not None else None
    docs: Any = payload_meta.get("docs") or payload_meta.get("documentation") or []
    # CodeQL false positive: readme_path is constrained under the exact generated plugin directory.
    if not docs and readme_path is not None and readme_path.exists():
        # CodeQL false positive: readme_path is constrained under the exact generated plugin directory.
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
            "validation_receipt_id": _safe_str(payload_meta.get("validation_receipt_id")).strip(),
            "validation_receipt_path": _safe_str(payload_meta.get("validation_receipt_path")).strip(),
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
    plugin_dir = _generated_plugin_dir(plugin_id, generated_dir)
    readme_path = _generated_child_path(plugin_dir, "README.md") if plugin_dir is not None else None
    docs = payload_meta.get("docs") or payload_meta.get("documentation") or []
    # CodeQL false positive: readme_path is constrained under the exact generated plugin directory.
    if not _has_readiness_value(docs) and readme_path is not None and readme_path.exists():
        # CodeQL false positive: readme_path is constrained under the exact generated plugin directory.
        docs = [str(readme_path.resolve())]

    risk_tier = _safe_str(payload_meta.get("risk_tier")).strip().lower() or _plugin_risk_tier(staged)
    evidence = payload_meta.get("proposal_evidence") or payload_meta.get("evidence") or []
    tests = payload_meta.get("tests") or payload_meta.get("test_refs") or []
    proposal_id = _safe_str(payload_meta.get("proposal_id") or payload_meta.get("forge_proposal_id")).strip()
    proposal_review = _plugin_proposal_review_state(proposal_id)
    pack_operator_review = _capability_pack_operator_review_state(plugin_id, payload_meta)
    requirements = {
        "proposal_id": bool(proposal_id),
        "proposal_review": bool(proposal_review["approved"]),
        "proposal_evidence": _has_readiness_value(evidence),
        "tests": _has_readiness_value(tests),
        "docs": _has_readiness_value(docs),
        "risk_tier": risk_tier in _RISK_ORDER,
    }
    if bool(pack_operator_review["required"]):
        requirements["pack_operator_review"] = bool(pack_operator_review["approved"])
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
            "validation_receipt_id": _safe_str(payload_meta.get("validation_receipt_id")).strip(),
            "validation_receipt_path": _safe_str(payload_meta.get("validation_receipt_path")).strip(),
            "pack_operator_review_required": bool(pack_operator_review["required"]),
            "pack_operator_review_status": pack_operator_review["review_status"],
            "pack_operator_review_receipt_id": pack_operator_review["receipt_id"],
            "pack_id": pack_operator_review["pack_id"],
            "pack_version": pack_operator_review["pack_version"],
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
            "next_step": (
                "approve_proposal_and_any_required_pack_operator_review_then_attach_friction_evidence_tests_docs_and_risk"
            ),
            "operator_hint": (
                "Promotion requires an approved proposal review, any required capability-pack operator review, "
                "proposal evidence, tests, docs, and a bounded risk tier."
            ),
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
    pack_operator_review = _capability_pack_operator_review_state(plugin_id, payload_meta)
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
        "pack_operator_review": {
            "required": bool(pack_operator_review["required"]),
            "status": pack_operator_review["review_status"],
            "receipt_id": pack_operator_review["receipt_id"],
            "pack_id": pack_operator_review["pack_id"],
            "pack_version": pack_operator_review["pack_version"],
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


def _unique_texts(values: Any, *, limit: int = 500) -> list[str]:
    out: list[str] = []
    for value in values if isinstance(values, list) else [values]:
        text = _safe_str(value).strip()
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _write_capability_pack_metadata_receipt(
    *,
    receipt_id: str,
    receipt_path: Path,
    payload: "CapabilityPackMetadataReceiptIn",
    pack_id: str,
    pack_version: str,
    pack_name: str,
    capability_ids: list[str],
    previous_metadata: dict[str, dict[str, Any]],
    recorded_ts: int,
    route_path: str = "/plugins/capabilities/packs/metadata/receipts",
) -> dict[str, Any]:
    payload_meta = redact_governed_metadata(payload.meta)
    receipt = {
        "kind": "plugin.capability_pack.metadata_receipt",
        "receipt_id": receipt_id,
        "status": "recorded",
        "pack_id": pack_id,
        "pack_version": pack_version,
        "pack_name": pack_name,
        "source_pack_id": _safe_str(payload.source_pack_id).strip(),
        "source_pack_version": _safe_str(payload.source_pack_version).strip(),
        "expanded_from_migration_plan": bool(payload.include_current_pack_capabilities),
        "capability_ids": capability_ids,
        "capability_count": len(capability_ids),
        "actor": redact_governed_value(_safe_str(payload.actor).strip()),
        "reason": redact_governed_value(_safe_str(payload.reason).strip() or "requested"),
        "recorded_ts": recorded_ts,
        "promotion_rules": _unique_texts(payload.promotion_rules, limit=50),
        "pack_governance": redact_governed_display_value(payload.pack_governance),
        "previous_metadata": redact_governed_display_value(previous_metadata),
        "metadata_context": payload_meta,
        "governance": {
            "gate": "permission_gate",
            "scope": _PLUGIN_WRITE_SCOPE,
            "route": route_path,
            "writes_registry_metadata": True,
            "writes_receipt": True,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
            "mutates_generated_artifacts": False,
        },
        "path": str(receipt_path),
    }
    redacted_receipt = _redact_plugin_receipt(receipt)
    _atomic_write_display_json(receipt_path, redacted_receipt)
    return redacted_receipt


def _capability_ids_for_pack(
    entries: list[dict[str, Any]],
    *,
    pack_id: str,
    pack_version: str = "",
) -> list[str]:
    out: list[str] = []
    for entry in entries:
        metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
        if _safe_str(metadata.get("pack_id")).strip() != pack_id:
            continue
        if pack_version and _safe_str(metadata.get("pack_version")).strip() != pack_version:
            continue
        capability_id = _safe_str(entry.get("capability")).strip()
        if capability_id and capability_id not in out:
            out.append(capability_id)
    return sorted(out)


def _entries_for_capability_pack(
    entries: list[dict[str, Any]],
    *,
    pack_id: str,
    pack_version: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in entries:
        metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
        if _safe_str(metadata.get("pack_id")).strip() != pack_id:
            continue
        if _safe_str(metadata.get("pack_version")).strip() != pack_version:
            continue
        out.append(entry)
    return out


def _promotion_rules_for_remediation(
    item: dict[str, Any],
    pack_entries: list[dict[str, Any]],
) -> list[str]:
    rules: list[str] = []
    for entry in pack_entries:
        metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
        rules.extend(_unique_texts(metadata.get("promotion_rules") or metadata.get("promotion_rule_ids"), limit=50))
    rules.extend(_unique_texts(item.get("promotion_rules"), limit=50))
    rules.extend(canonical_capability_pack_promotion_rules())
    return _unique_texts(rules, limit=50)


def _pack_governance_for_remediation(
    item: dict[str, Any],
    pack_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    governance: dict[str, Any] = {}
    for entry in pack_entries:
        metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
        raw_governance = metadata.get("pack_governance") or metadata.get("capability_pack_governance")
        if isinstance(raw_governance, dict):
            governance.update(raw_governance)
    governance.setdefault("scope", "build_dev")
    governance.setdefault("operator_review_required", True)
    governance.setdefault("metadata_receipt_required", True)
    governance.setdefault("quality_standards_required", True)
    governance["promotion_authority"] = False
    governance["execution_authority"] = False
    governance["approval_authority"] = False
    governance["memory_write"] = False
    governance["remediation_source"] = "stage17_capability_pack_promotion_rule_backlog_execution"
    governance["remediated_missing_governance_fields"] = _unique_texts(
        item.get("missing_governance_fields"),
        limit=50,
    )
    return governance


def _supported_metadata_remediation_blockers(item: dict[str, Any]) -> list[str]:
    return [
        blocker
        for blocker in _unique_texts(item.get("blockers"), limit=50)
        if blocker in _CAPABILITY_PACK_REMEDIATION_METADATA_BLOCKERS
    ]


def _count_label(bucket: dict[str, int], value: str) -> None:
    label = _safe_str(value).strip()
    if label:
        bucket[label] = bucket.get(label, 0) + 1


def _candidate_quality_reference_items(
    paths: set[str], candidates: tuple[str, ...], *, kind: str
) -> list[dict[str, Any]]:
    return [
        {
            "kind": kind,
            "path": path,
            "exists": True,
            "claim_scope": "capability_economy_contract_surface_only",
            "pack_specific_coverage_claimed": False,
        }
        for path in candidates
        if path in paths
    ]


def _capability_pack_quality_reference_candidates() -> dict[str, Any]:
    available_test_paths = _available_capability_pack_test_paths()
    available_doc_paths = _available_capability_pack_doc_paths()
    tests = _candidate_quality_reference_items(
        available_test_paths,
        _CAPABILITY_PACK_QUALITY_TEST_REFERENCE_CANDIDATES,
        kind="test",
    )
    docs = _candidate_quality_reference_items(
        available_doc_paths,
        _CAPABILITY_PACK_QUALITY_DOC_REFERENCE_CANDIDATES,
        kind="doc",
    )
    return {
        "tests": tests,
        "docs": docs,
        "available_test_path_count": len(available_test_paths),
        "available_doc_path_count": len(available_doc_paths),
        "candidate_test_reference_count": len(tests),
        "candidate_doc_reference_count": len(docs),
        "selection_policy": "existing_repo_surface_candidates_only",
        "does_not_read_test_contents": True,
        "does_not_read_doc_contents": True,
        "pack_specific_coverage_claimed": False,
    }


def _plugin_artifact_payloads(folder_name: str) -> dict[str, Any]:
    folder = _art_dir() / folder_name
    folder_fs_path = _filesystem_path(folder)
    if not os.path.isdir(folder_fs_path):
        return {
            "items": [],
            "artifact_body_max_bytes": _PLUGIN_ARTIFACT_LINK_BODY_MAX_BYTES,
            "oversized_artifact_count": 0,
            "unreadable_artifact_count": 0,
        }

    items: list[dict[str, Any]] = []
    oversized_artifact_count = 0
    unreadable_artifact_count = 0
    try:
        entries = [entry for entry in os.scandir(folder_fs_path) if entry.name.endswith(".json") and entry.is_file()]
    except OSError:
        return {
            "items": [],
            "artifact_body_max_bytes": _PLUGIN_ARTIFACT_LINK_BODY_MAX_BYTES,
            "oversized_artifact_count": 0,
            "unreadable_artifact_count": 1,
        }

    for entry in sorted(entries, key=lambda item: item.name):
        try:
            if entry.stat().st_size > _PLUGIN_ARTIFACT_LINK_BODY_MAX_BYTES:
                oversized_artifact_count += 1
                continue
            with open(entry.path, encoding="utf-8", errors="replace") as handle:
                payload = json.load(handle)
        except Exception:
            unreadable_artifact_count += 1
            continue
        if not isinstance(payload, dict):
            continue
        artifact_id = entry.name[:-5].strip()
        if not artifact_id or not _PLUGIN_ARTIFACT_ID_RE.match(artifact_id):
            continue
        items.append(
            {
                "artifact_id": artifact_id,
                "artifact_path": f"data/artifacts/plugins/{folder_name}/{entry.name}",
                "payload": payload,
            }
        )
    return {
        "items": items,
        "artifact_body_max_bytes": _PLUGIN_ARTIFACT_LINK_BODY_MAX_BYTES,
        "oversized_artifact_count": oversized_artifact_count,
        "unreadable_artifact_count": unreadable_artifact_count,
    }


def _unique_plugin_artifact_candidates(
    raw_items: list[dict[str, Any]],
    *,
    artifact_id_key: str,
    path_key: str,
    claim_scope: str,
    require_passed_validation: bool = False,
) -> dict[str, Any]:
    by_plugin_id: dict[str, dict[str, Any]] = {}
    ambiguous_plugin_ids: set[str] = set()
    invalid_count = 0
    for item in raw_items:
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        plugin_id = _safe_str(payload.get("plugin_id")).strip()
        artifact_id = _safe_str(
            payload.get(artifact_id_key)
            or payload.get("validation_id")
            or payload.get("proposal_id")
            or payload.get("id")
        ).strip()
        if not artifact_id:
            artifact_id = _safe_str(item.get("artifact_id")).strip()
        if not plugin_id or not artifact_id or not _PLUGIN_ARTIFACT_ID_RE.match(artifact_id):
            invalid_count += 1
            continue
        if require_passed_validation:
            status = _safe_str(payload.get("status")).strip().lower()
            if status != "passed" or payload.get("valid") is not True:
                invalid_count += 1
                continue
        candidate = {
            "plugin_id": plugin_id,
            artifact_id_key: artifact_id,
            path_key: _safe_str(item.get("artifact_path")).strip(),
            "claim_scope": claim_scope,
            "pack_specific_plugin_match": True,
            "writes_artifact": False,
        }
        existing = by_plugin_id.get(plugin_id)
        if existing is not None and existing != candidate:
            ambiguous_plugin_ids.add(plugin_id)
            continue
        by_plugin_id[plugin_id] = candidate

    for plugin_id in ambiguous_plugin_ids:
        by_plugin_id.pop(plugin_id, None)
    return {
        "by_plugin_id": by_plugin_id,
        "candidate_count": len(by_plugin_id),
        "ambiguous_plugin_id_count": len(ambiguous_plugin_ids),
        "invalid_or_unusable_artifact_count": invalid_count,
    }


def _capability_pack_existing_artifact_link_candidates() -> dict[str, Any]:
    validation_payloads = _plugin_artifact_payloads("validations")
    validation = _unique_plugin_artifact_candidates(
        validation_payloads["items"] if isinstance(validation_payloads.get("items"), list) else [],
        artifact_id_key="validation_receipt_id",
        path_key="validation_receipt_path",
        claim_scope="existing_pack_specific_plugin_validation_receipt",
        require_passed_validation=True,
    )
    validation["artifact_body_max_bytes"] = _PLUGIN_ARTIFACT_LINK_BODY_MAX_BYTES
    validation["oversized_artifact_count"] = int(validation_payloads.get("oversized_artifact_count") or 0)
    validation["unreadable_artifact_count"] = int(validation_payloads.get("unreadable_artifact_count") or 0)
    proposal_payloads = _plugin_artifact_payloads("proposals")
    proposals = _unique_plugin_artifact_candidates(
        proposal_payloads["items"] if isinstance(proposal_payloads.get("items"), list) else [],
        artifact_id_key="proposal_id",
        path_key="proposal_path",
        claim_scope="existing_plugin_proposal_lineage_only_not_approval",
    )
    proposals["artifact_body_max_bytes"] = _PLUGIN_ARTIFACT_LINK_BODY_MAX_BYTES
    proposals["oversized_artifact_count"] = int(proposal_payloads.get("oversized_artifact_count") or 0)
    proposals["unreadable_artifact_count"] = int(proposal_payloads.get("unreadable_artifact_count") or 0)
    return {
        "validation_receipts": validation,
        "proposals": proposals,
        "selection_policy": "unique_existing_artifact_with_matching_plugin_id_only",
        "artifact_body_max_bytes": _PLUGIN_ARTIFACT_LINK_BODY_MAX_BYTES,
        "skips_oversized_artifacts": True,
        "reads_validation_receipt_bodies_for_plugin_id_match": True,
        "reads_proposal_bodies_for_plugin_id_match": True,
        "writes_validation_receipts": False,
        "writes_proposals": False,
        "proposal_lineage_does_not_claim_approval": True,
    }


def _artifact_links_for_capabilities(
    capability_ids: list[str],
    candidates: dict[str, Any],
) -> dict[str, Any]:
    raw_by_plugin_id = candidates.get("by_plugin_id")
    by_plugin_id = raw_by_plugin_id if isinstance(raw_by_plugin_id, dict) else {}
    links = {
        capability_id: dict(by_plugin_id[capability_id])
        for capability_id in capability_ids
        if capability_id in by_plugin_id and isinstance(by_plugin_id[capability_id], dict)
    }
    missing = [capability_id for capability_id in capability_ids if capability_id not in links]
    return {
        "links": links,
        "candidate_count": len(links),
        "missing_candidate_count": len(missing),
        "missing_candidate_capability_ids": missing[:25],
        "missing_candidate_capability_ids_truncated": len(missing) > 25,
        "candidate_apply_supported": bool(capability_ids) and not missing,
    }


def _capability_pack_artifact_reconstruction_plan(
    *,
    capability_ids: list[str],
    pack_entries: list[dict[str, Any]],
    blockers: list[str],
    validation_links: dict[str, Any],
    proposal_links: dict[str, Any],
) -> dict[str, Any]:
    validation_link_map = validation_links.get("links") if isinstance(validation_links.get("links"), dict) else {}
    proposal_link_map = proposal_links.get("links") if isinstance(proposal_links.get("links"), dict) else {}
    validation_missing = (
        [capability_id for capability_id in capability_ids if capability_id not in validation_link_map]
        if "validation_receipt_missing" in blockers and not bool(validation_links.get("candidate_apply_supported"))
        else []
    )
    proposal_missing = (
        [capability_id for capability_id in capability_ids if capability_id not in proposal_link_map]
        if "proposal_id_missing" in blockers and not bool(proposal_links.get("candidate_apply_supported"))
        else []
    )
    missing_capability_ids = _unique_texts([*validation_missing, *proposal_missing], limit=500)
    entries_by_capability = {
        _safe_str(entry.get("capability")).strip(): entry
        for entry in pack_entries
        if _safe_str(entry.get("capability")).strip()
    }

    capabilities: list[dict[str, Any]] = []
    for capability_id in missing_capability_ids[:_CAPABILITY_PACK_ARTIFACT_RECONSTRUCTION_PLAN_LIMIT]:
        entry = entries_by_capability.get(capability_id, {})
        metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
        quality = metadata.get("quality") if isinstance(metadata.get("quality"), dict) else {}
        tests = _unique_texts(
            [
                *_unique_texts(quality.get("tests"), limit=50),
                *_unique_texts(metadata.get("tests"), limit=50),
                *_unique_texts(metadata.get("test_refs"), limit=50),
            ],
            limit=50,
        )
        docs = _unique_texts(
            [
                *_unique_texts(quality.get("docs"), limit=50),
                *_unique_texts(metadata.get("docs"), limit=50),
                *_unique_texts(metadata.get("documentation"), limit=50),
            ],
            limit=50,
        )
        needs_validation_receipt = capability_id in validation_missing
        needs_proposal_lineage = capability_id in proposal_missing
        missing_inputs: list[str] = []
        if needs_validation_receipt and not tests:
            missing_inputs.append("quality_test_references")
        if needs_validation_receipt and not docs:
            missing_inputs.append("quality_doc_references")
        if needs_validation_receipt and not _safe_str(metadata.get("pack_metadata_receipt_id")).strip():
            missing_inputs.append("pack_metadata_receipt")
        if needs_proposal_lineage:
            missing_inputs.append("explicit_proposal_lineage_source_or_operator_reconstruction_decision")

        writer_requirements: list[str] = []
        if needs_validation_receipt:
            writer_requirements.append("create_or_attach_pack_specific_validation_receipt_after_validation")
        if needs_proposal_lineage:
            writer_requirements.append("create_or_attach_explicit_proposal_lineage_without_approval_claim")
        if writer_requirements:
            writer_requirements.append("operator_review_before_artifact_write")

        capabilities.append(
            {
                "capability": capability_id,
                "needs_validation_receipt": needs_validation_receipt,
                "needs_proposal_lineage": needs_proposal_lineage,
                "available_inputs": {
                    "registry_metadata": bool(metadata),
                    "pack_metadata_receipt": bool(_safe_str(metadata.get("pack_metadata_receipt_id")).strip()),
                    "registry_snapshot": bool(_safe_str(metadata.get("registry_snapshot_path")).strip()),
                    "artifact_zip": bool(
                        _safe_str(metadata.get("artifact_zip")).strip() or _safe_str(entry.get("artifact_zip")).strip()
                    ),
                    "quality_test_references": bool(tests),
                    "quality_doc_references": bool(docs),
                    "existing_validation_receipt_link": capability_id in validation_link_map,
                    "existing_proposal_lineage_link": capability_id in proposal_link_map,
                },
                "missing_inputs": _unique_texts(missing_inputs, limit=25),
                "next_writer_requirements": _unique_texts(writer_requirements, limit=25),
            }
        )

    required_count = len(missing_capability_ids)
    return {
        "required": required_count > 0,
        "read_only": True,
        "writer_implemented": False,
        "writer_route": "",
        "selection_policy": "missing_pack_specific_artifact_after_existing_link_scan",
        "validation_receipt_reconstruction_required_count": len(validation_missing),
        "proposal_lineage_reconstruction_required_count": len(proposal_missing),
        "capability_count": required_count,
        "capabilities": capabilities,
        "capabilities_truncated": required_count > _CAPABILITY_PACK_ARTIFACT_RECONSTRUCTION_PLAN_LIMIT,
        "does_not_write_validation_receipts": True,
        "does_not_write_proposals": True,
        "does_not_approve_proposals": True,
        "does_not_promote_capabilities": True,
        "next_smallest_truthful_gap": (
            "stage17_capability_pack_artifact_reconstruction_writer" if required_count else ""
        ),
    }


def _capability_pack_quality_remediation_next_action(
    *,
    blockers: list[str],
    quality_reference_candidate: bool,
    validation_receipt_link_candidate: bool = False,
    proposal_lineage_link_candidate: bool = False,
) -> str:
    if quality_reference_candidate and any(blocker in blockers for blocker in ("tests_missing", "docs_missing")):
        return "review_quality_reference_backfill_candidates"
    if validation_receipt_link_candidate and "validation_receipt_missing" in blockers:
        return "review_existing_validation_receipt_links"
    if proposal_lineage_link_candidate and "proposal_id_missing" in blockers:
        return "review_existing_proposal_lineage_links"
    if "validation_receipt_missing" in blockers:
        return "write_pack_specific_validation_receipt"
    if "proposal_id_missing" in blockers:
        return "link_or_reconstruct_forge_proposal_lineage"
    return "review_capability_pack_evidence"


def _capability_pack_quality_remediation_next_gap(
    *,
    quality_backfill_candidate_count: int,
    validation_receipt_link_candidate_count: int = 0,
    proposal_lineage_link_candidate_count: int = 0,
    artifact_reconstruction_required_count: int = 0,
    blocker_counts: dict[str, int],
    fallback: str,
) -> str:
    if (
        quality_backfill_candidate_count
        or validation_receipt_link_candidate_count
        or proposal_lineage_link_candidate_count
    ):
        return "stage17_capability_pack_quality_evidence_remediation_apply"
    if artifact_reconstruction_required_count:
        return "stage17_capability_pack_artifact_reconstruction_writer"
    for blocker, gap in (
        ("tests_missing", "stage17_capability_pack_quality_tests"),
        ("docs_missing", "stage17_capability_pack_quality_docs"),
        ("validation_receipt_missing", "stage17_capability_pack_validation_receipts"),
        ("proposal_id_missing", "stage17_capability_pack_lineage"),
    ):
        if blocker_counts.get(blocker, 0) > 0:
            return gap
    return fallback or "stage17_capability_pack_quality_evidence_review"


def _capability_pack_quality_evidence_remediation_item(
    item: dict[str, Any],
    *,
    entries: list[dict[str, Any]],
    reference_candidates: dict[str, Any],
    artifact_link_candidates: dict[str, Any],
) -> dict[str, Any] | None:
    blockers = [
        blocker
        for blocker in _unique_texts(item.get("blockers"), limit=50)
        if blocker in _CAPABILITY_PACK_QUALITY_EVIDENCE_BLOCKERS
    ]
    if not blockers:
        return None

    pack_id = _safe_str(item.get("pack_id")).strip()
    pack_version = _safe_str(item.get("pack_version")).strip()
    pack_entries = _entries_for_capability_pack(entries, pack_id=pack_id, pack_version=pack_version)
    metadata_items = [
        entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {} for entry in pack_entries
    ]
    sources = sorted(
        {_safe_str(entry.get("source")).strip() for entry in pack_entries if _safe_str(entry.get("source")).strip()}
    )
    statuses = sorted(
        {_safe_str(entry.get("status")).strip() for entry in pack_entries if _safe_str(entry.get("status")).strip()}
    )
    has_metadata_receipts = bool(metadata_items) and all(
        bool(_safe_str(metadata.get("pack_metadata_receipt_id")).strip()) for metadata in metadata_items
    )
    generated_or_legacy = pack_id.startswith("legacy.generated.") or any(source == "generated" for source in sources)
    registry_snapshot_count = sum(
        1 for metadata in metadata_items if _safe_str(metadata.get("registry_snapshot_path")).strip()
    )
    candidate_test_count = int(reference_candidates.get("candidate_test_reference_count") or 0)
    candidate_doc_count = int(reference_candidates.get("candidate_doc_reference_count") or 0)
    test_backfill_candidate = (
        "tests_missing" in blockers and generated_or_legacy and has_metadata_receipts and candidate_test_count > 0
    )
    doc_backfill_candidate = (
        "docs_missing" in blockers and generated_or_legacy and has_metadata_receipts and candidate_doc_count > 0
    )
    quality_reference_candidate = test_backfill_candidate or doc_backfill_candidate
    capability_ids = _capability_ids_for_pack(entries, pack_id=pack_id, pack_version=pack_version)[:50]
    validation_candidates = (
        artifact_link_candidates.get("validation_receipts")
        if isinstance(artifact_link_candidates.get("validation_receipts"), dict)
        else {}
    )
    proposal_candidates = (
        artifact_link_candidates.get("proposals") if isinstance(artifact_link_candidates.get("proposals"), dict) else {}
    )
    validation_links = _artifact_links_for_capabilities(capability_ids, validation_candidates)
    proposal_links = _artifact_links_for_capabilities(capability_ids, proposal_candidates)
    capability_ids_truncated = len(pack_entries) > 50
    validation_receipt_link_candidate = (
        "validation_receipt_missing" in blockers
        and not capability_ids_truncated
        and bool(validation_links["candidate_apply_supported"])
    )
    proposal_lineage_link_candidate = (
        "proposal_id_missing" in blockers
        and not capability_ids_truncated
        and bool(proposal_links["candidate_apply_supported"])
    )
    artifact_reconstruction_plan = _capability_pack_artifact_reconstruction_plan(
        capability_ids=capability_ids,
        pack_entries=pack_entries,
        blockers=blockers,
        validation_links=validation_links,
        proposal_links=proposal_links,
    )
    return {
        "pack_id": pack_id,
        "pack_version": pack_version,
        "pack_name": _safe_str(item.get("pack_name")).strip() or pack_id,
        "status": "blocked",
        "capability_count": int(item.get("capability_count") or len(pack_entries)),
        "capability_ids": capability_ids,
        "capability_ids_truncated": capability_ids_truncated,
        "sources": sources,
        "statuses": statuses,
        "blockers": blockers,
        "eligible_generated_or_legacy_pack": generated_or_legacy,
        "pack_metadata_receipts_present": has_metadata_receipts,
        "registry_snapshot_count": registry_snapshot_count,
        "quality_reference_backfill_candidate": quality_reference_candidate,
        "evidence_backfill": {
            "tests": {
                "required": "tests_missing" in blockers,
                "candidate_reference_count": candidate_test_count,
                "candidate_apply_supported": test_backfill_candidate,
                "claim_scope": "candidate_reference_only_not_pack_specific_proof",
            },
            "docs": {
                "required": "docs_missing" in blockers,
                "candidate_reference_count": candidate_doc_count,
                "candidate_apply_supported": doc_backfill_candidate,
                "claim_scope": "candidate_reference_only_not_pack_specific_proof",
            },
            "validation_receipt": {
                "required": "validation_receipt_missing" in blockers,
                "candidate_reference_count": int(validation_links["candidate_count"]),
                "candidate_apply_supported": validation_receipt_link_candidate,
                "claim_scope": "existing_pack_specific_plugin_validation_receipt",
                "missing_candidate_count": int(validation_links["missing_candidate_count"]),
                "missing_candidate_capability_ids": validation_links["missing_candidate_capability_ids"],
                "missing_candidate_capability_ids_truncated": bool(
                    validation_links["missing_candidate_capability_ids_truncated"]
                ),
                "links": list(validation_links["links"].values())[:25],
                "links_truncated": len(validation_links["links"]) > 25,
                "reason": (
                    "existing_pack_specific_validation_receipt_available"
                    if validation_receipt_link_candidate
                    else "requires_pack_specific_validation_receipt_writer"
                ),
            },
            "forge_proposal": {
                "required": "proposal_id_missing" in blockers,
                "candidate_reference_count": int(proposal_links["candidate_count"]),
                "candidate_apply_supported": proposal_lineage_link_candidate,
                "claim_scope": "existing_plugin_proposal_lineage_only_not_approval",
                "missing_candidate_count": int(proposal_links["missing_candidate_count"]),
                "missing_candidate_capability_ids": proposal_links["missing_candidate_capability_ids"],
                "missing_candidate_capability_ids_truncated": bool(
                    proposal_links["missing_candidate_capability_ids_truncated"]
                ),
                "links": list(proposal_links["links"].values())[:25],
                "links_truncated": len(proposal_links["links"]) > 25,
                "reason": (
                    "existing_plugin_proposal_lineage_available"
                    if proposal_lineage_link_candidate
                    else "requires_explicit_lineage_reconstruction_or_proposal_link"
                ),
            },
        },
        "artifact_reconstruction_plan": artifact_reconstruction_plan,
        "recommended_next_action": _capability_pack_quality_remediation_next_action(
            blockers=blockers,
            quality_reference_candidate=quality_reference_candidate,
            validation_receipt_link_candidate=validation_receipt_link_candidate,
            proposal_lineage_link_candidate=proposal_lineage_link_candidate,
        ),
        "would_mutate": False,
        "writes_registry_metadata": False,
        "writes_receipts": False,
        "failing_capabilities_sample": list(item.get("failing_capabilities_sample") or [])[:25],
    }


def _capability_pack_quality_evidence_remediation_projection(
    entries: list[dict[str, Any]],
    promotion_remediation: dict[str, Any],
) -> dict[str, Any]:
    reference_candidates = _capability_pack_quality_reference_candidates()
    artifact_link_candidates = _capability_pack_existing_artifact_link_candidates()
    raw_queue = promotion_remediation.get("remediation_queue")
    source_queue = [item for item in raw_queue if isinstance(item, dict)] if isinstance(raw_queue, list) else []
    items: list[dict[str, Any]] = []
    blocker_counts: dict[str, int] = {}
    for item in source_queue:
        projected = _capability_pack_quality_evidence_remediation_item(
            item,
            entries=entries,
            reference_candidates=reference_candidates,
            artifact_link_candidates=artifact_link_candidates,
        )
        if projected is None:
            continue
        for blocker in projected["blockers"]:
            _count_label(blocker_counts, _safe_str(blocker))
        items.append(projected)

    quality_backfill_candidate_count = sum(1 for item in items if bool(item["quality_reference_backfill_candidate"]))
    validation_receipt_link_candidate_count = sum(
        1
        for item in items
        if bool(
            (item.get("evidence_backfill") if isinstance(item.get("evidence_backfill"), dict) else {})
            .get("validation_receipt", {})
            .get("candidate_apply_supported")
        )
    )
    proposal_lineage_link_candidate_count = sum(
        1
        for item in items
        if bool(
            (item.get("evidence_backfill") if isinstance(item.get("evidence_backfill"), dict) else {})
            .get("forge_proposal", {})
            .get("candidate_apply_supported")
        )
    )
    artifact_reconstruction_required_count = sum(
        1
        for item in items
        if bool(
            (
                item.get("artifact_reconstruction_plan")
                if isinstance(item.get("artifact_reconstruction_plan"), dict)
                else {}
            ).get("required")
        )
    )
    validation_receipt_reconstruction_required_count = sum(
        int(
            (
                item.get("artifact_reconstruction_plan")
                if isinstance(item.get("artifact_reconstruction_plan"), dict)
                else {}
            ).get("validation_receipt_reconstruction_required_count")
            or 0
        )
        for item in items
    )
    proposal_lineage_reconstruction_required_count = sum(
        int(
            (
                item.get("artifact_reconstruction_plan")
                if isinstance(item.get("artifact_reconstruction_plan"), dict)
                else {}
            ).get("proposal_lineage_reconstruction_required_count")
            or 0
        )
        for item in items
    )
    return {
        "stage": "Stage 17 / Capability Economy",
        "status": "blocked" if items else "ready",
        "pack_total": int(promotion_remediation.get("pack_total") or 0),
        "source_remediation_queue_count": int(
            promotion_remediation.get("remediation_queue_count") or len(source_queue)
        ),
        "source_remediation_queue_truncated": bool(promotion_remediation.get("remediation_queue_truncated")),
        "remediation_queue_count": len(items),
        "remediation_queue_truncated": len(items) > _CAPABILITY_PACK_QUALITY_EVIDENCE_QUEUE_LIMIT,
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "quality_reference_backfill_candidate_count": quality_backfill_candidate_count,
        "validation_receipt_link_candidate_count": validation_receipt_link_candidate_count,
        "proposal_lineage_link_candidate_count": proposal_lineage_link_candidate_count,
        "artifact_reconstruction_required_count": artifact_reconstruction_required_count,
        "validation_receipt_reconstruction_required_count": validation_receipt_reconstruction_required_count,
        "proposal_lineage_reconstruction_required_count": proposal_lineage_reconstruction_required_count,
        "validation_receipt_backfill_required_count": sum(
            1 for item in items if "validation_receipt_missing" in item["blockers"]
        ),
        "proposal_lineage_backfill_required_count": sum(
            1 for item in items if "proposal_id_missing" in item["blockers"]
        ),
        "reference_candidates": reference_candidates,
        "artifact_link_candidates": {
            "validation_receipts": {
                key: value
                for key, value in artifact_link_candidates["validation_receipts"].items()
                if key != "by_plugin_id"
            },
            "proposals": {
                key: value for key, value in artifact_link_candidates["proposals"].items() if key != "by_plugin_id"
            },
            "selection_policy": artifact_link_candidates["selection_policy"],
            "artifact_body_max_bytes": artifact_link_candidates["artifact_body_max_bytes"],
            "skips_oversized_artifacts": True,
            "reads_validation_receipt_bodies_for_plugin_id_match": True,
            "reads_proposal_bodies_for_plugin_id_match": True,
            "writes_validation_receipts": False,
            "writes_proposals": False,
            "proposal_lineage_does_not_claim_approval": True,
        },
        "remediation_queue": items[:_CAPABILITY_PACK_QUALITY_EVIDENCE_QUEUE_LIMIT],
        "requirements": {
            "read_only_remediation_plan": True,
            "quality_references_must_be_existing_repo_paths": True,
            "candidate_references_do_not_claim_pack_specific_coverage": True,
            "validation_receipts_require_pack_specific_writer": True,
            "proposal_lineage_requires_explicit_reconstruction_or_link": True,
            "existing_validation_receipt_links_require_matching_plugin_id": True,
            "existing_proposal_lineage_links_require_matching_plugin_id": True,
            "proposal_lineage_links_do_not_approve_proposals": True,
            "artifact_body_reads_are_bounded": True,
            "artifact_reconstruction_plan_is_read_only": True,
            "artifact_reconstruction_writer_not_implemented": True,
            "generated_or_legacy_pack_only_for_quality_backfill_candidates": True,
        },
        "governance": {
            "read_only": True,
            "operator_facing": True,
            "does_not_read_test_contents": True,
            "does_not_read_doc_contents": True,
            "does_not_read_receipt_bodies": False,
            "does_not_read_proposal_bodies": False,
            "reads_validation_receipt_bodies_for_plugin_id_match": True,
            "reads_proposal_bodies_for_plugin_id_match": True,
            "artifact_body_max_bytes": _PLUGIN_ARTIFACT_LINK_BODY_MAX_BYTES,
            "skips_oversized_artifacts": True,
            "does_not_write_receipts": True,
            "does_not_write_validation_receipts": True,
            "does_not_write_proposals": True,
            "artifact_reconstruction_plan_only": True,
            "artifact_reconstruction_writer_implemented": False,
            "does_not_mutate_registry": True,
            "does_not_mutate_generated_artifacts": True,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
        },
        "next_smallest_truthful_gap": (
            _capability_pack_quality_remediation_next_gap(
                quality_backfill_candidate_count=quality_backfill_candidate_count,
                validation_receipt_link_candidate_count=validation_receipt_link_candidate_count,
                proposal_lineage_link_candidate_count=proposal_lineage_link_candidate_count,
                artifact_reconstruction_required_count=artifact_reconstruction_required_count,
                blocker_counts=blocker_counts,
                fallback=_safe_str(promotion_remediation.get("next_smallest_truthful_gap")).strip(),
            )
        ),
    }


def _quality_reference_paths(reference_candidates: dict[str, Any], key: str) -> list[str]:
    raw_items = reference_candidates.get(key)
    items = raw_items if isinstance(raw_items, list) else []
    return _unique_texts(
        [_safe_str(item.get("path")).strip() for item in items if isinstance(item, dict) and bool(item.get("exists"))],
        limit=50,
    )


def _quality_reference_plan_for_remediation_item(
    item: dict[str, Any],
    reference_candidates: dict[str, Any],
) -> dict[str, list[str]]:
    evidence = item.get("evidence_backfill") if isinstance(item.get("evidence_backfill"), dict) else {}
    tests = evidence.get("tests") if isinstance(evidence.get("tests"), dict) else {}
    docs = evidence.get("docs") if isinstance(evidence.get("docs"), dict) else {}
    return {
        "tests": _quality_reference_paths(reference_candidates, "tests")
        if bool(tests.get("candidate_apply_supported"))
        else [],
        "docs": _quality_reference_paths(reference_candidates, "docs")
        if bool(docs.get("candidate_apply_supported"))
        else [],
    }


def _artifact_link_plan_for_remediation_item(item: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    evidence = item.get("evidence_backfill") if isinstance(item.get("evidence_backfill"), dict) else {}
    raw = evidence.get(key) if isinstance(evidence.get(key), dict) else {}
    if not bool(raw.get("candidate_apply_supported")):
        return {}
    links = raw.get("links") if isinstance(raw.get("links"), list) else []
    planned: dict[str, dict[str, Any]] = {}
    for link in links:
        if not isinstance(link, dict):
            continue
        plugin_id = _safe_str(link.get("plugin_id")).strip()
        if plugin_id:
            planned[plugin_id] = dict(link)
    return planned


def _merge_quality_references(existing: Any, additions: list[str]) -> list[str]:
    return _unique_texts([*_unique_texts(existing, limit=50), *additions], limit=50)


def _record_capability_pack_quality_evidence_remediation_batch(
    *,
    registry: dict[str, Any],
    prepared: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    recorded_ts = _now_s()
    failed: list[dict[str, Any]] = []
    recorded: list[dict[str, Any]] = []
    changed = False

    for item in prepared:
        pack_id = _safe_str(item.get("pack_id")).strip()
        pack_version = _safe_str(item.get("pack_version")).strip()
        capability_ids = _unique_texts(item.get("capability_ids"), limit=500)
        references = item.get("quality_references") if isinstance(item.get("quality_references"), dict) else {}
        test_refs = _unique_texts(references.get("tests"), limit=50)
        doc_refs = _unique_texts(references.get("docs"), limit=50)
        validation_links = (
            item.get("validation_receipt_links") if isinstance(item.get("validation_receipt_links"), dict) else {}
        )
        proposal_links = (
            item.get("proposal_lineage_links") if isinstance(item.get("proposal_lineage_links"), dict) else {}
        )
        missing = [capability_id for capability_id in capability_ids if _read_plugin(registry, capability_id) is None]
        if missing:
            failed.append(
                {
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "status": "blocked",
                    "error": "capability_not_found",
                    "missing_capability_ids": missing,
                }
            )
            continue

        changed_capability_ids: list[str] = []
        for capability_id in capability_ids:
            current = _read_plugin(registry, capability_id)
            if current is None:
                continue
            meta = dict(current.get("meta") or {}) if isinstance(current.get("meta"), dict) else {}
            quality = dict(meta.get("quality") or {}) if isinstance(meta.get("quality"), dict) else {}
            before_quality = dict(quality)
            before_meta = dict(meta)
            if test_refs:
                quality["tests"] = _merge_quality_references(quality.get("tests"), test_refs)
            if doc_refs:
                quality["docs"] = _merge_quality_references(quality.get("docs"), doc_refs)
            if quality != before_quality:
                quality["reference_source"] = "stage17_quality_evidence_remediation_apply"
                quality["claim_scope"] = "candidate_reference_only_not_pack_specific_proof"
                quality["pack_specific_coverage_claimed"] = False
                quality["validation_receipt_written"] = False
                quality["proposal_lineage_written"] = False
                meta["quality"] = quality
                meta["quality_reference_remediation_source"] = (
                    "stage17_capability_pack_quality_evidence_remediation_apply"
                )
            validation_link = validation_links.get(capability_id)
            if isinstance(validation_link, dict):
                validation_receipt_id = _safe_str(validation_link.get("validation_receipt_id")).strip()
                validation_receipt_path = _safe_str(validation_link.get("validation_receipt_path")).strip()
                if validation_receipt_id and validation_receipt_path:
                    meta["validation_receipt_id"] = validation_receipt_id
                    meta["validation_receipt_path"] = validation_receipt_path
                    meta["validation_receipt_link_source"] = (
                        "stage17_capability_pack_quality_evidence_remediation_apply"
                    )
                    meta["validation_receipt_link_claim_scope"] = "existing_pack_specific_plugin_validation_receipt"
            proposal_link = proposal_links.get(capability_id)
            if isinstance(proposal_link, dict):
                proposal_id = _safe_str(proposal_link.get("proposal_id")).strip()
                proposal_path = _safe_str(proposal_link.get("proposal_path")).strip()
                if proposal_id and proposal_path:
                    meta["proposal_id"] = proposal_id
                    meta["proposal_path"] = proposal_path
                    meta["proposal_lineage_link_source"] = "stage17_capability_pack_quality_evidence_remediation_apply"
                    meta["proposal_lineage_claim_scope"] = "existing_plugin_proposal_lineage_only_not_approval"
                    meta["proposal_lineage_approval_claimed"] = False
            if meta == before_meta:
                continue
            current["meta"] = meta
            current["updated_ts"] = recorded_ts
            _write_plugin(registry, _normalize_plugin_record(capability_id, current))
            changed = True
            changed_capability_ids.append(capability_id)

        recorded.append(
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "capability_count": len(capability_ids),
                "changed_capability_count": len(changed_capability_ids),
                "changed_capability_ids": changed_capability_ids[:50],
                "changed_capability_ids_truncated": len(changed_capability_ids) > 50,
                "quality_references": {
                    "tests": test_refs,
                    "docs": doc_refs,
                    "claim_scope": "candidate_reference_only_not_pack_specific_proof",
                    "pack_specific_coverage_claimed": False,
                },
                "validation_receipt_links": {
                    "count": len(validation_links),
                    "claim_scope": "existing_pack_specific_plugin_validation_receipt",
                    "writes_validation_receipts": False,
                },
                "proposal_lineage_links": {
                    "count": len(proposal_links),
                    "claim_scope": "existing_plugin_proposal_lineage_only_not_approval",
                    "proposal_approval_claimed": False,
                    "writes_proposals": False,
                },
                "applied_evidence_blockers": _unique_texts(item.get("evidence_blockers"), limit=50),
                "status": "recorded" if changed_capability_ids else "unchanged",
            }
        )

    if changed:
        _save_registry_and_catalog(registry)
    return {"recorded": recorded, "failed": failed}


def _record_capability_pack_promotion_rule_remediation_batch(
    *,
    registry: dict[str, Any],
    prepared: list[dict[str, Any]],
    payload: "CapabilityPackPromotionRuleRemediationApplyIn",
    route_path: str,
) -> dict[str, list[dict[str, Any]]]:
    recorded_ts = _now_s()
    failed: list[dict[str, Any]] = []
    pending_receipts: list[dict[str, Any]] = []
    for item in prepared:
        pack_id = _safe_str(item.get("pack_id")).strip()
        pack_version = _safe_str(item.get("pack_version")).strip()
        pack_name = _safe_str(item.get("pack_name")).strip() or pack_id
        capability_ids = _unique_texts(item.get("capability_ids"), limit=500)
        missing = [capability_id for capability_id in capability_ids if _read_plugin(registry, capability_id) is None]
        if missing:
            failed.append(
                {
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "status": "blocked",
                    "error": "capability_not_found",
                    "missing_capability_ids": missing,
                }
            )
            continue

        receipt_id = _capability_pack_metadata_receipt_id(pack_id, recorded_ts)
        receipt_path = _capability_pack_metadata_receipt_path(receipt_id)
        promotion_rules = _unique_texts(item.get("promotion_rules"), limit=50)
        pack_governance = dict(item.get("pack_governance") or {})
        source_item = item.get("item") if isinstance(item.get("item"), dict) else {}
        previous_metadata: dict[str, dict[str, Any]] = {}
        for capability_id in capability_ids:
            current = _read_plugin(registry, capability_id)
            if current is None:
                continue
            meta = dict(current.get("meta") or {}) if isinstance(current.get("meta"), dict) else {}
            previous_metadata[capability_id] = {
                "pack_id": _safe_str(meta.get("pack_id")).strip(),
                "pack_version": _safe_str(meta.get("pack_version")).strip(),
                "pack_metadata_source": _safe_str(meta.get("pack_metadata_source")).strip(),
                "pack_metadata_receipt_id": _safe_str(meta.get("pack_metadata_receipt_id")).strip(),
            }
            meta.update(
                {
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "pack_name": pack_name,
                    "pack_metadata_source": "metadata_receipt",
                    "pack_metadata_receipt_id": receipt_id,
                    "pack_metadata_receipt_path": str(receipt_path),
                }
            )
            if promotion_rules:
                meta["promotion_rules"] = promotion_rules
            if pack_governance:
                meta["pack_governance"] = pack_governance
            current["meta"] = meta
            current["updated_ts"] = recorded_ts
            _write_plugin(registry, _normalize_plugin_record(capability_id, current))

        receipt_payload = CapabilityPackMetadataReceiptIn(
            actor=payload.actor,
            reason=f"{_safe_str(payload.reason).strip() or 'stage17_promotion_rule_remediation'}:{pack_id}",
            pack_id=pack_id,
            pack_version=pack_version,
            pack_name=pack_name,
            capability_ids=capability_ids,
            source_pack_id=pack_id,
            source_pack_version=pack_version,
            promotion_rules=promotion_rules,
            pack_governance=pack_governance,
            meta={
                **redact_governed_metadata(payload.meta),
                "promotion_rule_remediation_apply": True,
                "bulk_registry_write": True,
                "source_remediation_blockers": _unique_texts(source_item.get("blockers"), limit=50),
                "applied_metadata_blockers": _unique_texts(item.get("metadata_blockers"), limit=50),
                "missing_promotion_rules": _unique_texts(source_item.get("missing_promotion_rules"), limit=50),
                "missing_governance_fields": _unique_texts(source_item.get("missing_governance_fields"), limit=50),
                "missing_quality_evidence": _unique_texts(source_item.get("missing_quality_evidence"), limit=50),
                "missing_receipt_evidence": _unique_texts(source_item.get("missing_receipt_evidence"), limit=50),
            },
        )
        pending_receipts.append(
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "receipt_id": receipt_id,
                "receipt_path": receipt_path,
                "payload": receipt_payload,
                "pack_name": pack_name,
                "capability_ids": capability_ids,
                "metadata_blockers": _unique_texts(item.get("metadata_blockers"), limit=50),
                "previous_metadata": previous_metadata,
            }
        )

    if pending_receipts:
        _save_registry_and_catalog(registry)

    recorded: list[dict[str, Any]] = []
    for item in pending_receipts:
        receipt = _write_capability_pack_metadata_receipt(
            receipt_id=str(item["receipt_id"]),
            receipt_path=item["receipt_path"],
            payload=item["payload"],
            pack_id=str(item["pack_id"]),
            pack_version=str(item["pack_version"]),
            pack_name=str(item["pack_name"]),
            capability_ids=list(item["capability_ids"]),
            previous_metadata=item["previous_metadata"],
            recorded_ts=recorded_ts,
            route_path=route_path,
        )
        recorded.append(
            {
                "pack_id": item["pack_id"],
                "pack_version": item["pack_version"],
                "receipt_id": item["receipt_id"],
                "receipt_path": str(item["receipt_path"]),
                "capability_count": len(item["capability_ids"]),
                "metadata_blockers": item["metadata_blockers"],
                "receipt_status": receipt.get("status"),
            }
        )
    return {"recorded": recorded, "failed": failed}


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


def _filesystem_path(path: Path) -> str:
    if os.name != "nt":
        return str(path)
    resolved = str(path.resolve())
    if resolved.startswith("\\\\?\\"):
        return resolved
    if resolved.startswith("\\\\"):
        return "\\\\?\\UNC\\" + resolved[2:]
    return "\\\\?\\" + resolved


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    os.makedirs(_filesystem_path(path.parent), exist_ok=True)
    tmp = path.with_name(f".atomic-json-{os.getpid()}-{uuid.uuid4().hex}.tmp")
    tmp_fs_path = _filesystem_path(tmp)
    target_fs_path = _filesystem_path(path)
    try:
        with open(tmp_fs_path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(obj, indent=2, ensure_ascii=False, default=str))
        os.replace(tmp_fs_path, target_fs_path)
    finally:
        if os.path.exists(tmp_fs_path):
            try:
                os.unlink(tmp_fs_path)
            except OSError:
                pass


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


def _read_runtime_catalog_payload(catalog: dict[str, Any]) -> dict[str, Any]:
    path_text = _safe_str(catalog.get("path")).strip()
    if not path_text:
        return {}
    path = _resolve_under(data_dir() / "plugins", path_text)
    if path is None:
        return {}
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _available_capability_pack_test_paths() -> set[str]:
    root = repo_root()
    out: set[str] = set()
    for relative_root, patterns in (
        ("tests", ("test_*.py", "*_test.py")),
        ("apps/chat_ui/src", ("*.test.ts", "*.test.tsx")),
        ("apps/chat_ui/tests", ("*.test.ts", "*.test.tsx")),
    ):
        scan_root = _resolve_under(root, relative_root)
        if scan_root is None or not scan_root.exists() or not scan_root.is_dir():
            continue
        for pattern in patterns:
            try:
                candidates = scan_root.rglob(pattern)
            except OSError:
                continue
            for path in candidates:
                if len(out) >= 10000:
                    return out
                try:
                    resolved = _real_path(path)
                except OSError:
                    continue
                if not _is_under(_real_path(root), resolved) or not resolved.is_file():
                    continue
                try:
                    out.add(resolved.relative_to(root).as_posix())
                except ValueError:
                    continue
    return out


def _available_capability_pack_doc_paths() -> set[str]:
    root = repo_root()
    out: set[str] = set()
    root_resolved = _real_path(root)
    readme = _resolve_under(root, "README.md")
    if readme is not None and readme.exists() and readme.is_file():
        out.add("README.md")

    for relative_root, patterns in (("docs", ("*.md", "*.mdx", "*.rst", "*.txt")),):
        scan_root = _resolve_under(root, relative_root)
        if scan_root is None or not scan_root.exists() or not scan_root.is_dir():
            continue
        for pattern in patterns:
            try:
                candidates = scan_root.rglob(pattern)
            except OSError:
                continue
            for path in candidates:
                if len(out) >= 10000:
                    return out
                try:
                    resolved = _real_path(path)
                except OSError:
                    continue
                if not _is_under(root_resolved, resolved) or not resolved.is_file():
                    continue
                try:
                    out.add(resolved.relative_to(root).as_posix())
                except ValueError:
                    continue
    return out


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
    # CodeQL false positive: callers pass paths returned by _generated_child_path.
    if not path.exists() or not path.is_file():
        return {}
    out: dict[str, str] = {}
    try:
        # CodeQL false positive: callers pass paths returned by _generated_child_path.
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or ":" not in stripped:
                continue
            key, value = stripped.split(":", 1)
            out[key.strip()] = value.strip()
    except Exception:
        return {}
    return out


def _generated_child_path(plugin_dir: Path, *parts: str) -> Path | None:
    clean_parts: list[str] = []
    for part in parts:
        text = _safe_str(part).strip()
        if not text or any(ch in text for ch in ("\x00", "\n", "\r")):
            return None
        clean_parts.append(text)
    root = _real_path(plugin_dir)
    try:
        resolved = _real_path(root.joinpath(*clean_parts))
    except OSError:
        return None
    return resolved if _is_under(root, resolved) else None


def _required_generated_child_path(plugin_dir: Path, *parts: str) -> Path:
    path = _generated_child_path(plugin_dir, *parts)
    if path is None:
        raise ValueError("invalid_generated_child_path")
    return path


def _generated_relative_file(plugin_dir: Path, path: Path) -> str | None:
    root = _real_path(plugin_dir)
    try:
        resolved = _real_path(path)
    except OSError:
        return None
    if not _is_under(root, resolved):
        return None
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return None


def _manifest_for_plugin_dir(plugin_dir: Path) -> dict[str, str]:
    yaml_path = _generated_child_path(plugin_dir, "plugin.yaml")
    manifest = _parse_simple_yaml(yaml_path) if yaml_path is not None else {}
    if "entrypoint" not in manifest:
        manifest["entrypoint"] = "plugin.py"
    return manifest


def _generated_contract_path(plugin_dir: Path) -> Path:
    return _required_generated_child_path(plugin_dir, "plugin.spec.json")


def _generated_registry_snapshot_path(plugin_dir: Path) -> Path:
    return _required_generated_child_path(plugin_dir, "plugin.registry.json")


def _load_generated_contract(plugin_dir: Path) -> PluginSpec | None:
    spec_path = _generated_contract_path(plugin_dir)
    # CodeQL false positive: spec_path is constrained under plugin_dir by _required_generated_child_path.
    if not spec_path.exists() or not spec_path.is_file():
        return None
    return PluginLoader(spec_dir=plugin_dir).load(spec_path)


def _read_generated_registry_snapshot(plugin_dir: Path) -> dict[str, Any]:
    snapshot_path = _generated_registry_snapshot_path(plugin_dir)
    # CodeQL false positive: snapshot_path is constrained under plugin_dir by _required_generated_child_path.
    if not snapshot_path.exists() or not snapshot_path.is_file():
        return {}
    try:
        # CodeQL false positive: snapshot_path is constrained under plugin_dir by _required_generated_child_path.
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
        # CodeQL false positive: snapshot_path is constrained under plugin_dir by _required_generated_child_path.
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
            # CodeQL false positive: plugin_dir is constrained by _generated_plugin_dir to plugins/generated/<plugin_id>.
            "generated_dir": str(plugin_dir.resolve()),
            # CodeQL false positive: artifact_path is constrained by _plugin_artifact_path/artifact-root conventions.
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
    plugin_dir = _generated_plugin_dir(plugin_id, generated_dir)
    if plugin_dir is None:
        return {}
    # CodeQL false positive: plugin_dir is constrained by _generated_plugin_dir to plugins/generated/<plugin_id>.
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
    readme_path = _generated_child_path(plugin_dir, "README.md")
    readme = (
        # CodeQL false positive: readme_path is constrained under plugin_dir by _generated_child_path.
        readme_path.read_text(encoding="utf-8", errors="replace")
        # CodeQL false positive: readme_path is constrained under plugin_dir by _generated_child_path.
        if readme_path is not None and readme_path.exists()
        else ""
    )

    files: list[str] = []
    # CodeQL false positive: plugin_dir is constrained by _generated_plugin_dir to plugins/generated/<plugin_id>.
    for p in plugin_dir.rglob("*"):
        if p.is_file():
            relative_file = _generated_relative_file(plugin_dir, p)
            if relative_file is not None:
                files.append(relative_file)
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
    plugin_dir = _generated_plugin_dir(plugin_id)
    if plugin_dir is None:
        return False
    # CodeQL false positive: plugin_dir is constrained by _generated_plugin_dir to plugins/generated/<plugin_id>.
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
                # CodeQL false positive: plugin_dir is constrained by _generated_plugin_dir to plugins/generated/<plugin_id>.
                "generated_dir": str(plugin_dir.resolve()),
                # CodeQL false positive: artifact_path is constrained by artifact-root/plugin id conventions.
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
        base_text = os.path.normcase(os.path.realpath(os.fspath(base)))
        candidate_text = os.path.normcase(os.path.realpath(os.fspath(candidate)))
        return os.path.commonpath([base_text, candidate_text]) == base_text
    except (OSError, ValueError):
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
    plugin_dir = _generated_plugin_dir(plugin_id, generated_dir)
    if plugin_dir is None:
        return {"echo": payload_input}
    if not plugin_dir.exists():
        return {"echo": payload_input}

    meta = plugin.get("meta")
    meta_obj = meta if isinstance(meta, dict) else {}
    entrypoint = _safe_str(meta_obj.get("entrypoint")).strip() or "plugin.py"
    entrypoint_path = _generated_child_path(plugin_dir, entrypoint)
    if entrypoint_path is None:
        return {"echo": payload_input}
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
    plugin_dir = _generated_plugin_dir(_safe_str(plugin.get("id")).strip(), generated_dir)
    allowed_paths = [str(plugin_dir)] if plugin_dir is not None else []
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


def _forge_staging_requirements(payload: PluginBuildIn, meta: dict[str, Any]) -> dict[str, Any]:
    risk_tier = _safe_str(meta.get("risk_tier")).strip().lower()
    requirements = {
        "friction_summary": _has_readiness_value(meta.get("friction_summary") or meta.get("friction")),
        "proposal_evidence": _has_readiness_value(meta.get("proposal_evidence") or meta.get("evidence")),
        "tests": _has_readiness_value(meta.get("tests") or meta.get("test_refs")),
        "docs": _has_readiness_value(meta.get("docs") or meta.get("documentation")),
        "risk_tier": risk_tier in _RISK_ORDER,
    }
    missing = [key for key, present in requirements.items() if not present]
    return {
        "ready": not missing,
        "missing_requirements": missing,
        "requirements": requirements,
        "evidence": {
            "name": _safe_str(payload.name).strip(),
            "description_present": bool(_safe_str(payload.description).strip()),
            "risk_tier": risk_tier,
        },
    }


def _forge_staging_requirements_blocked(readiness: dict[str, Any]) -> dict[str, object]:
    return {
        "ok": False,
        "applied": False,
        "status": "blocked",
        "error": "forge_staging_requirements_missing",
        "missing_requirements": list(readiness.get("missing_requirements") or []),
        "readiness": redact_governed_display_value(readiness),
        "governance": {
            "plane": "P3_GOVERNANCE",
            "gate": "forge_staging_quality",
            "scope": _PLUGIN_WRITE_SCOPE,
            "route": "/plugins/build",
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
            "next_step": "attach_friction_summary_proposal_evidence_tests_docs_and_risk_before_staging",
            "operator_hint": (
                "Forge staging requires explicit friction summary, proposal evidence, tests, docs, "
                "and a valid risk tier before artifacts are created."
            ),
        },
    }


class PluginToggleIn(BaseModel):
    id: str
    reason: str = "requested"
    actor: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)


class CapabilityPackOperatorReviewDecisionIn(BaseModel):
    pack_id: str
    pack_version: str
    action: str
    actor: str = ""
    reason: str = "requested"
    notes: str = ""
    capability_ids: list[str] = Field(default_factory=list)
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


class CapabilityPackMetadataReceiptIn(BaseModel):
    actor: str = ""
    reason: str = "requested"
    pack_id: str
    pack_version: str
    pack_name: str = ""
    capability_ids: list[str] = Field(default_factory=list)
    include_current_pack_capabilities: bool = False
    source_pack_id: str = ""
    source_pack_version: str = ""
    promotion_rules: list[str] = Field(default_factory=list)
    pack_governance: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)


class CapabilityPackMetadataReceiptBulkFromPlanIn(BaseModel):
    actor: str = ""
    reason: str = "reviewed_stage17_migration_plan"
    pack_ids: list[str] = Field(default_factory=list)
    max_pack_count: int = 50
    max_total_capability_count: int = 5000
    max_capability_count_per_pack: int = 500
    meta: dict[str, Any] = Field(default_factory=dict)


class CapabilityPackPromotionRuleRemediationApplyIn(BaseModel):
    actor: str = ""
    reason: str = "stage17_promotion_rule_remediation"
    pack_ids: list[str] = Field(default_factory=list)
    max_pack_count: int = 10
    max_total_capability_count: int = 1000
    max_capability_count_per_pack: int = 500
    dry_run: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)


class CapabilityPackQualityEvidenceRemediationApplyIn(BaseModel):
    actor: str = ""
    reason: str = "stage17_quality_evidence_remediation"
    pack_ids: list[str] = Field(default_factory=list)
    max_pack_count: int = 10
    max_total_capability_count: int = 1000
    max_capability_count_per_pack: int = 500
    dry_run: bool = False
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
        return {"ok": False, "route": "plugins", "status": "error", "error": api_error_message(exc)}


@router.post("/build")
def build(payload: PluginBuildIn, request: Request) -> dict[str, object]:
    try:
        permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
        if not permission.allowed:
            return _permission_denied(permission)

        build_meta = redact_governed_metadata(payload.meta)
        staging_readiness = _forge_staging_requirements(payload, build_meta)
        if not staging_readiness["ready"]:
            return _forge_staging_requirements_blocked(staging_readiness)

        res = build_plugin(payload.name, payload.description)
        plugin_id = _validate_plugin_id(_safe_str(res.get("plugin_id")).strip())
        staged_ts = _now_s()
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
                        "pack_id": build_meta.get("pack_id") or build_meta.get("capability_pack_id") or "",
                        "pack_version": build_meta.get("pack_version")
                        or build_meta.get("capability_pack_version")
                        or "",
                        "pack_name": build_meta.get("pack_name") or build_meta.get("capability_pack_name") or "",
                        "promotion_rules": build_meta.get("promotion_rules")
                        or build_meta.get("promotion_rule_ids")
                        or [],
                        "pack_governance": build_meta.get("pack_governance")
                        or build_meta.get("capability_pack_governance")
                        or {},
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
        return {"ok": False, "error": api_error_message(exc)}


@router.get("/download/{plugin_id}")
def download(plugin_id: str):
    try:
        normalized_id = _validate_plugin_id(plugin_id)
    except Exception:
        return {"ok": False, "error": "invalid_plugin_id"}

    path = _plugin_artifact_path(normalized_id)
    if path is None:
        return {"ok": False, "error": "artifact_path_invalid"}
    # CodeQL false positive: path is constrained by _plugin_artifact_path to data/artifacts/plugins/<plugin_id>.zip.
    if not path.exists():
        return {"ok": False, "error": "not_found"}
    # CodeQL false positive: path is constrained by _plugin_artifact_path to data/artifacts/plugins/<plugin_id>.zip.
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
        return {"items": [], "plugins": [], "total": 0, "offset": 0, "limit": 0, "error": api_error_message(exc)}


@router.get("/capabilities/catalog")
def list_plugin_capabilities(
    limit: int = 200,
    offset: int = 0,
    status: str | None = None,
    risk_tier: str | None = None,
    source: str | None = None,
) -> dict[str, object]:
    try:
        safe_limit = max(1, min(int(limit), 5000))
        safe_offset = max(0, int(offset))
        status_filter = _safe_str(status).strip().lower()
        risk_filter = _safe_str(risk_tier).strip().lower()
        source_filter = _safe_str(source).strip().lower()

        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        all_items = marketplace.catalog()
        filtered_items = marketplace.catalog(
            status=status_filter or None,
            risk_tier=risk_filter or None,
            source=source_filter or None,
        )
        total = len(filtered_items)
        page = filtered_items[safe_offset : safe_offset + safe_limit]

        forge_lineage = runtime_catalog.get("forge_lineage_index")
        if not isinstance(forge_lineage, list):
            forge_lineage = []
        risk_counts = runtime_catalog.get("risk_class_counts")
        lifecycle_counts = runtime_catalog.get("lifecycle_status_counts")
        tool_risk_counts = runtime_catalog.get("tool_risk_class_counts")

        return {
            "ok": True,
            "items": page,
            "capabilities": page,
            "total": total,
            "offset": safe_offset,
            "limit": safe_limit,
            "filters": {
                "status": status_filter,
                "risk_tier": risk_filter,
                "source": source_filter,
            },
            "summary": marketplace.summary(),
            "coherence": analyze_capability_catalog_coherence(all_items),
            "pack_readiness": analyze_capability_pack_readiness(all_items),
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "version": int(runtime_catalog.get("version") or 0),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
                "risk_class_counts": risk_counts if isinstance(risk_counts, dict) else {},
                "lifecycle_status_counts": lifecycle_counts if isinstance(lifecycle_counts, dict) else {},
                "tool_risk_class_counts": tool_risk_counts if isinstance(tool_risk_counts, dict) else {},
                "approval_required_tool_count": int(runtime_catalog.get("approval_required_tool_count") or 0),
                "forge_lineage_index": forge_lineage,
                "rejected": catalog.get("rejected") if isinstance(catalog.get("rejected"), list) else [],
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "items": [],
            "capabilities": [],
            "total": 0,
            "offset": 0,
            "limit": 0,
            "error": api_error_message(exc),
        }


@router.get("/capabilities/packs/metadata/receipts")
def capability_pack_metadata_receipts(limit: int = 20) -> dict[str, object]:
    try:
        items = _read_capability_pack_metadata_receipts(limit=limit)
        return {
            "ok": True,
            "kind": "plugin.capability_pack.metadata_receipts",
            "total": len(items),
            "items": items,
            "governance": {
                "read_only": True,
                "writes_registry_metadata": False,
                "writes_receipts": False,
                "promotion_authority": False,
                "execution_authority": False,
            },
        }
    except Exception as exc:
        return {"ok": False, "kind": "plugin.capability_pack.metadata_receipts", "error": api_error_message(exc)}


@router.get("/capabilities/packs/migration/plan")
def capability_pack_migration_plan() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        plan = analyze_capability_pack_migration_plan(marketplace.catalog())
        return {
            "ok": True,
            "kind": "plugin.capability_pack.migration_plan",
            **plan,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {"ok": False, "kind": "plugin.capability_pack.migration_plan", "error": api_error_message(exc)}


@router.get("/capabilities/packs/quality/standards")
def capability_pack_quality_standards() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        standards = analyze_capability_pack_quality_standards(marketplace.catalog())
        return {
            "ok": True,
            "kind": "plugin.capability_pack.quality_standards",
            **standards,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {"ok": False, "kind": "plugin.capability_pack.quality_standards", "error": api_error_message(exc)}


@router.get("/capabilities/packs/quality/tests")
def capability_pack_quality_tests() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        analysis = analyze_capability_pack_quality_tests(
            marketplace.catalog(),
            available_test_paths=_available_capability_pack_test_paths(),
        )
        return {
            "ok": True,
            "kind": "plugin.capability_pack.quality_tests",
            **analysis,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {"ok": False, "kind": "plugin.capability_pack.quality_tests", "error": api_error_message(exc)}


@router.get("/capabilities/packs/quality/docs")
def capability_pack_quality_docs() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        analysis = analyze_capability_pack_quality_docs(
            marketplace.catalog(),
            available_doc_paths=_available_capability_pack_doc_paths(),
        )
        return {
            "ok": True,
            "kind": "plugin.capability_pack.quality_docs",
            **analysis,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {"ok": False, "kind": "plugin.capability_pack.quality_docs", "error": api_error_message(exc)}


@router.get("/capabilities/packs/validation/receipts")
def capability_pack_validation_receipts() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        available_receipts = _available_capability_pack_validation_receipts()
        analysis = analyze_capability_pack_validation_receipts(
            marketplace.catalog(),
            available_receipt_ids=available_receipts["ids"],
            available_receipt_paths=available_receipts["paths"],
        )
        return {
            "ok": True,
            "kind": "plugin.capability_pack.validation_receipts",
            **analysis,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {"ok": False, "kind": "plugin.capability_pack.validation_receipts", "error": api_error_message(exc)}


@router.get("/capabilities/packs/lineage/proposals")
def capability_pack_lineage_proposals() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        available_proposals = _available_capability_pack_proposals()
        analysis = analyze_capability_pack_lineage(
            marketplace.catalog(),
            available_proposal_ids=available_proposals["ids"],
            available_proposal_paths=available_proposals["paths"],
        )
        return {
            "ok": True,
            "kind": "plugin.capability_pack.lineage.proposals",
            **analysis,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {"ok": False, "kind": "plugin.capability_pack.lineage.proposals", "error": api_error_message(exc)}


@router.get("/capabilities/packs/quality/evidence/remediation")
def capability_pack_quality_evidence_remediation() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        entries = marketplace.catalog()
        promotion_remediation = analyze_capability_pack_promotion_rule_remediation(entries)
        projection = _capability_pack_quality_evidence_remediation_projection(entries, promotion_remediation)
        return {
            "ok": True,
            "kind": "plugin.capability_pack.quality_evidence.remediation",
            **projection,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "plugin.capability_pack.quality_evidence.remediation",
            "error": api_error_message(exc),
        }


@router.post("/capabilities/packs/quality/evidence/remediation/apply")
def apply_capability_pack_quality_evidence_remediation(
    payload: CapabilityPackQualityEvidenceRemediationApplyIn,
    request: Request,
) -> dict[str, object]:
    try:
        permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
        if not permission.allowed:
            return _permission_denied(permission)

        safe_max_pack_count = max(1, min(int(payload.max_pack_count or 10), 50))
        safe_max_total_capability_count = max(1, min(int(payload.max_total_capability_count or 1000), 10000))
        safe_max_capability_count_per_pack = max(1, min(int(payload.max_capability_count_per_pack or 500), 500))
        try:
            selected_pack_ids = {_validate_plugin_id(raw_id) for raw_id in _unique_texts(payload.pack_ids, limit=100)}
        except Exception:
            return {"ok": False, "applied": False, "status": "blocked", "error": "invalid_pack_id"}

        registry = _load_registry()
        _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        entries = marketplace.catalog()
        promotion_remediation = analyze_capability_pack_promotion_rule_remediation(entries)
        before = _capability_pack_quality_evidence_remediation_projection(entries, promotion_remediation)
        reference_candidates = (
            before.get("reference_candidates") if isinstance(before.get("reference_candidates"), dict) else {}
        )
        raw_queue = before.get("remediation_queue")
        queue = [item for item in raw_queue if isinstance(item, dict)] if isinstance(raw_queue, list) else []
        if selected_pack_ids:
            queue = [item for item in queue if _safe_str(item.get("pack_id")).strip() in selected_pack_ids]
        if not queue:
            return {
                "ok": True,
                "applied": False,
                "status": "no_candidates",
                "planned_pack_count": 0,
                "recorded_pack_count": 0,
                "recorded_capability_count": 0,
                "before": before,
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "writes_registry_metadata": False,
                    "writes_receipts": False,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                    "mutates_generated_artifacts": False,
                },
            }
        if len(queue) > safe_max_pack_count:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "remediation_pack_limit_exceeded",
                "candidate_total": len(queue),
                "limit": safe_max_pack_count,
            }

        prepared: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        total_capability_count = 0
        for item in queue:
            pack_id = _safe_str(item.get("pack_id")).strip()
            pack_version = _safe_str(item.get("pack_version")).strip()
            if not pack_id or not pack_version:
                skipped.append(
                    {"pack_id": pack_id, "pack_version": pack_version, "error": "pack_id_or_version_missing"}
                )
                continue
            try:
                pack_id = _validate_plugin_id(pack_id)
            except Exception:
                skipped.append({"pack_id": pack_id, "pack_version": pack_version, "error": "invalid_pack_id"})
                continue
            references = _quality_reference_plan_for_remediation_item(item, reference_candidates)
            validation_receipt_links = _artifact_link_plan_for_remediation_item(item, "validation_receipt")
            proposal_lineage_links = _artifact_link_plan_for_remediation_item(item, "forge_proposal")
            evidence_blockers = []
            for blocker, supported in (
                ("tests_missing", bool(references["tests"])),
                ("docs_missing", bool(references["docs"])),
                ("validation_receipt_missing", bool(validation_receipt_links)),
                ("proposal_id_missing", bool(proposal_lineage_links)),
            ):
                if supported and blocker in _unique_texts(item.get("blockers"), limit=50):
                    evidence_blockers.append(blocker)
            if not evidence_blockers:
                skipped.append(
                    {
                        "pack_id": pack_id,
                        "pack_version": pack_version,
                        "error": "no_supported_quality_evidence_backfill",
                        "blockers": _unique_texts(item.get("blockers"), limit=50),
                    }
                )
                continue
            capability_ids = _capability_ids_for_pack(entries, pack_id=pack_id, pack_version=pack_version)
            capability_count = len(capability_ids)
            total_capability_count += capability_count
            if capability_count <= 0:
                skipped.append({"pack_id": pack_id, "pack_version": pack_version, "error": "capability_ids_required"})
                continue
            if capability_count > safe_max_capability_count_per_pack:
                skipped.append(
                    {
                        "pack_id": pack_id,
                        "pack_version": pack_version,
                        "error": "candidate_capability_limit_exceeded",
                        "capability_count": capability_count,
                        "limit": safe_max_capability_count_per_pack,
                    }
                )
                continue
            prepared.append(
                {
                    "item": item,
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "pack_name": _safe_str(item.get("pack_name")).strip() or pack_id,
                    "capability_ids": capability_ids,
                    "quality_references": references,
                    "validation_receipt_links": validation_receipt_links,
                    "proposal_lineage_links": proposal_lineage_links,
                    "evidence_blockers": evidence_blockers,
                }
            )
        if total_capability_count > safe_max_total_capability_count:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "total_capability_limit_exceeded",
                "capability_count": total_capability_count,
                "limit": safe_max_total_capability_count,
            }
        if not prepared:
            return {
                "ok": True,
                "applied": False,
                "status": "no_supported_quality_evidence_backfill",
                "planned_pack_count": 0,
                "recorded_pack_count": 0,
                "recorded_capability_count": 0,
                "skipped": skipped,
                "before": before,
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "writes_registry_metadata": False,
                    "writes_receipts": False,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                    "mutates_generated_artifacts": False,
                },
            }

        planned = [
            {
                "pack_id": item["pack_id"],
                "pack_version": item["pack_version"],
                "pack_name": item["pack_name"],
                "capability_count": len(item["capability_ids"]),
                "quality_references": item["quality_references"],
                "validation_receipt_links": {
                    "count": len(item["validation_receipt_links"]),
                    "claim_scope": "existing_pack_specific_plugin_validation_receipt",
                    "writes_validation_receipts": False,
                },
                "proposal_lineage_links": {
                    "count": len(item["proposal_lineage_links"]),
                    "claim_scope": "existing_plugin_proposal_lineage_only_not_approval",
                    "proposal_approval_claimed": False,
                    "writes_proposals": False,
                },
                "applied_evidence_blockers": item["evidence_blockers"],
                "claim_scope": "bounded_quality_reference_and_existing_artifact_links_only",
            }
            for item in prepared
        ]
        if payload.dry_run:
            return {
                "ok": True,
                "applied": False,
                "status": "dry_run",
                "planned_pack_count": len(planned),
                "planned_capability_count": sum(int(item.get("capability_count") or 0) for item in planned),
                "planned": planned,
                "skipped": skipped,
                "before": before,
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "writes_registry_metadata": False,
                    "writes_receipts": False,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                    "mutates_generated_artifacts": False,
                },
            }

        batch = _record_capability_pack_quality_evidence_remediation_batch(
            registry=registry,
            prepared=prepared,
        )
        recorded = batch["recorded"]
        failed = batch["failed"]
        changed_records = [item for item in recorded if item.get("status") == "recorded"]

        refreshed_registry = _load_registry()
        refreshed_catalog = _compile_runtime_catalog(refreshed_registry)
        refreshed_runtime_catalog = _read_runtime_catalog_payload(refreshed_catalog)
        refreshed_marketplace = marketplace_from_plugin_catalog(refreshed_runtime_catalog)
        refreshed_entries = refreshed_marketplace.catalog()
        refreshed_promotion_remediation = analyze_capability_pack_promotion_rule_remediation(refreshed_entries)
        after = _capability_pack_quality_evidence_remediation_projection(
            refreshed_entries,
            refreshed_promotion_remediation,
        )
        selected_after_queue = [
            item
            for item in after.get("remediation_queue", [])
            if isinstance(item, dict)
            and (
                not selected_pack_ids
                or _safe_str(item.get("pack_id")).strip() in selected_pack_ids
                or _safe_str(item.get("pack_id")).strip() in {str(record.get("pack_id")) for record in recorded}
            )
        ]
        applied = bool(changed_records)
        return {
            "ok": not failed,
            "applied": applied,
            "status": "recorded" if not failed and applied else ("partial" if applied else "blocked"),
            "planned_pack_count": len(prepared),
            "recorded_pack_count": len(changed_records),
            "recorded_capability_count": sum(
                int(item.get("changed_capability_count") or 0) for item in changed_records
            ),
            "recorded": recorded,
            "failed": failed,
            "skipped": skipped,
            "remaining_remediation_queue": selected_after_queue,
            "remaining_remediation_queue_count": int(after.get("remediation_queue_count") or 0),
            "next_smallest_truthful_gap": _safe_str(after.get("next_smallest_truthful_gap")).strip(),
            "governance": {
                "scope": _PLUGIN_WRITE_SCOPE,
                "route": request.url.path,
                "writes_registry_metadata": applied,
                "writes_receipts": False,
                "quality_reference_backfill_only": all(
                    not item.get("validation_receipt_links") and not item.get("proposal_lineage_links")
                    for item in prepared
                ),
                "existing_artifact_link_backfill_supported": True,
                "candidate_references_do_not_claim_pack_specific_coverage": True,
                "does_not_write_validation_receipts": True,
                "does_not_write_proposals": True,
                "validation_receipt_links_require_existing_artifacts": True,
                "proposal_lineage_links_require_existing_artifacts": True,
                "proposal_lineage_links_do_not_approve_proposals": True,
                "does_not_approve_proposals": True,
                "does_not_promote_capabilities": True,
                "does_not_enable_capabilities": True,
                "does_not_execute_capabilities": True,
                "promotion_authority": False,
                "execution_authority": False,
                "approval_authority": False,
                "memory_write": False,
                "mutates_generated_artifacts": False,
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "plugin.capability_pack.quality_evidence.remediation.apply",
            "error": api_error_message(exc),
        }


@router.get("/capabilities/packs/promotion/receipts")
def capability_pack_promotion_receipts() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        available_receipts = _available_capability_pack_promotion_receipts()
        analysis = analyze_capability_pack_promotion_receipts(
            marketplace.catalog(),
            available_receipt_ids=available_receipts["ids"],
            available_receipt_paths=available_receipts["paths"],
        )
        return {
            "ok": True,
            "kind": "plugin.capability_pack.promotion_receipts",
            **analysis,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {"ok": False, "kind": "plugin.capability_pack.promotion_receipts", "error": api_error_message(exc)}


@router.get("/capabilities/packs/promotion/discipline")
def capability_pack_promotion_discipline() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        available_proposals = _available_capability_pack_proposals()
        available_validation_receipts = _available_capability_pack_validation_receipts()
        available_promotion_receipts = _available_capability_pack_promotion_receipts()
        analysis = analyze_capability_pack_promotion_discipline(
            marketplace.catalog(),
            available_proposal_ids=available_proposals["ids"],
            available_validation_receipt_ids=available_validation_receipts["ids"],
            available_promotion_receipt_ids=available_promotion_receipts["ids"],
            operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
        )
        return {
            "ok": True,
            "kind": "plugin.capability_pack.promotion_discipline",
            **analysis,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {"ok": False, "kind": "plugin.capability_pack.promotion_discipline", "error": api_error_message(exc)}


@router.get("/capabilities/packs/operator/review")
def capability_pack_operator_review() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        review = analyze_capability_pack_operator_review(marketplace.catalog())
        return {
            "ok": True,
            "kind": "plugin.capability_pack.operator_review",
            **review,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {"ok": False, "kind": "plugin.capability_pack.operator_review", "error": api_error_message(exc)}


@router.get("/capabilities/packs/operator/review/decisions")
def capability_pack_operator_review_decisions(
    limit: int = 50,
    pack_id: str = "",
    pack_version: str = "",
) -> dict[str, object]:
    try:
        safe_pack_id = _safe_str(pack_id).strip()
        safe_pack_version = _safe_str(pack_version).strip()
        items = [
            item
            for item in _read_capability_pack_operator_review_decisions(limit=limit)
            if (not safe_pack_id or _safe_str(item.get("pack_id")).strip() == safe_pack_id)
            and (not safe_pack_version or _safe_str(item.get("pack_version")).strip() == safe_pack_version)
        ]
        return {
            "ok": True,
            "kind": "plugin.capability_pack.operator_review.decisions",
            "stage": "Stage 17 / Capability Economy",
            "items": items,
            "total": len(items),
            "limit": max(1, min(int(limit or 50), 500)),
            "governance": {
                "read_only": True,
                "operator_facing": True,
                "does_not_write_receipts": True,
                "does_not_mutate_registry": True,
                "does_not_approve_proposals": True,
                "does_not_promote_capabilities": True,
                "does_not_enable_capabilities": True,
                "does_not_execute_capabilities": True,
                "promotion_authority": False,
                "execution_authority": False,
            },
            "write_route": "/plugins/capabilities/packs/operator/review/decisions",
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "plugin.capability_pack.operator_review.decisions",
            "error": api_error_message(exc),
        }


@router.post("/capabilities/packs/operator/review/decisions")
def decide_capability_pack_operator_review(
    payload: CapabilityPackOperatorReviewDecisionIn,
    request: Request,
) -> dict[str, object]:
    try:
        permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
        if not permission.allowed:
            return _permission_denied(permission)

        try:
            pack_id = _validate_plugin_id(_safe_str(payload.pack_id).strip())
        except Exception:
            return {"ok": False, "applied": False, "status": "blocked", "error": "invalid_pack_id"}
        pack_version = _safe_str(payload.pack_version).strip()
        if not pack_version or any(ch in pack_version for ch in ("\x00", "\n", "\r")):
            return {"ok": False, "applied": False, "status": "blocked", "error": "pack_version_required"}

        action = _safe_str(payload.action).strip().lower()
        decided_status = _CAPABILITY_PACK_OPERATOR_REVIEW_DECISIONS.get(action)
        if decided_status is None:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "invalid_decision",
                "allowed_actions": sorted(_CAPABILITY_PACK_OPERATOR_REVIEW_DECISIONS),
            }

        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        entries = marketplace.catalog()
        review = analyze_capability_pack_operator_review(entries)
        pack = next(
            (
                item
                for item in review["packs"]
                if _safe_str(item.get("pack_id")).strip() == pack_id
                and _safe_str(item.get("pack_version")).strip() == pack_version
            ),
            None,
        )
        if not isinstance(pack, dict):
            return {"ok": False, "applied": False, "status": "blocked", "error": "pack_not_found"}
        if not bool(pack.get("operator_review_ready")):
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "pack_operator_review_not_ready",
                "blockers": list(pack.get("blockers") or []),
                "pack": pack,
            }
        if not bool(pack.get("decision_required")):
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "pack_operator_review_decision_not_required",
                "pack": pack,
            }

        staged_capability_ids: list[str] = []
        for entry in entries:
            capability_id = _safe_str(entry.get("capability")).strip()
            if not capability_id or _safe_str(entry.get("status")).strip().lower() != "staged":
                continue
            metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
            if _safe_str(metadata.get("pack_id")).strip() != pack_id:
                continue
            if _safe_str(metadata.get("pack_version")).strip() != pack_version:
                continue
            staged_capability_ids.append(capability_id)
        staged_capability_ids = sorted(set(staged_capability_ids))
        if not staged_capability_ids:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "staged_capabilities_required",
                "pack": pack,
            }

        try:
            requested_ids = [_validate_plugin_id(raw_id) for raw_id in _unique_texts(payload.capability_ids, limit=500)]
        except Exception:
            return {"ok": False, "applied": False, "status": "blocked", "error": "invalid_capability_id"}
        capability_ids = requested_ids or staged_capability_ids
        outside_pack = [capability_id for capability_id in capability_ids if capability_id not in staged_capability_ids]
        if outside_pack:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "capability_not_in_review_pack",
                "capability_ids": outside_pack,
            }

        decided_ts = _now_s()
        receipt_id = _capability_pack_operator_review_receipt_id(pack_id, decided_ts)
        receipt_path = _capability_pack_operator_review_receipt_path(receipt_id)
        receipt = {
            "kind": "plugin.capability_pack.operator_review.decision_receipt",
            "receipt_id": receipt_id,
            "status": decided_status,
            "decision": action,
            "pack_id": pack_id,
            "pack_version": pack_version,
            "pack_name": _safe_str(pack.get("pack_name")).strip(),
            "capability_ids": capability_ids,
            "capability_count": len(capability_ids),
            "staged_capability_count": int(pack.get("staged_capability_count") or 0),
            "actor": redact_governed_value(_safe_str(payload.actor).strip()),
            "reason": redact_governed_value(_safe_str(payload.reason).strip() or "requested"),
            "notes": redact_governed_value(_safe_str(payload.notes).strip()),
            "decided_ts": decided_ts,
            "meta": redact_governed_metadata(payload.meta),
            "review_snapshot": {
                "status": _safe_str(pack.get("status")).strip(),
                "decision_kind": _safe_str(pack.get("decision_kind")).strip(),
                "blockers": list(pack.get("blockers") or []),
                "quality_evidence_ready": bool(pack.get("quality_evidence_ready")),
                "proposal_lineage_ready": bool(pack.get("proposal_lineage_ready")),
                "validation_receipts_ready": bool(pack.get("validation_receipts_ready")),
                "operator_review_rule_declared": bool(pack.get("operator_review_rule_declared")),
                "operator_review_governance_declared": bool(pack.get("operator_review_governance_declared")),
            },
            "governance": {
                "gate": "capability_pack_operator_review",
                "scope": _PLUGIN_WRITE_SCOPE,
                "route": "/plugins/capabilities/packs/operator/review/decisions",
                "writes_receipt": True,
                "does_not_mutate_registry": True,
                "does_not_approve_proposals": True,
                "does_not_promote_capabilities": True,
                "does_not_enable_capabilities": True,
                "does_not_execute_capabilities": True,
                "promotion_authority": False,
                "execution_authority": False,
                "approval_authority": False,
                "memory_write": False,
            },
            "path": str(receipt_path),
        }
        redacted_receipt = _redact_plugin_receipt(receipt)
        _atomic_write_display_json(receipt_path, redacted_receipt)
        return {
            "ok": True,
            "applied": True,
            "status": decided_status,
            "pack_id": pack_id,
            "pack_version": pack_version,
            "receipt_id": receipt_id,
            "receipt_path": str(receipt_path),
            "receipt": redacted_receipt,
            "pack": pack,
            "governance": {
                "gate": "capability_pack_operator_review",
                "promotion_authority": False,
                "execution_authority": False,
                "next_step": "explicit_promotion_can_reference_pack_operator_review_receipt",
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "applied": False,
            "status": "error",
            "error": api_error_message(exc),
        }


@router.get("/capabilities/packs/promotion/rules")
def capability_pack_promotion_rules() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        rules = analyze_capability_pack_promotion_rules(marketplace.catalog())
        return {
            "ok": True,
            "kind": "plugin.capability_pack.promotion_rules",
            **rules,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {"ok": False, "kind": "plugin.capability_pack.promotion_rules", "error": api_error_message(exc)}


@router.get("/capabilities/packs/promotion/rules/remediation")
def capability_pack_promotion_rule_remediation() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        remediation = analyze_capability_pack_promotion_rule_remediation(marketplace.catalog())
        return {
            "ok": True,
            "kind": "plugin.capability_pack.promotion_rules.remediation",
            **remediation,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "plugin.capability_pack.promotion_rules.remediation",
            "error": api_error_message(exc),
        }


@router.post("/capabilities/packs/promotion/rules/remediation/apply")
def apply_capability_pack_promotion_rule_remediation(
    payload: CapabilityPackPromotionRuleRemediationApplyIn,
    request: Request,
) -> dict[str, object]:
    try:
        permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
        if not permission.allowed:
            return _permission_denied(permission)

        safe_max_pack_count = max(1, min(int(payload.max_pack_count or 10), 50))
        safe_max_total_capability_count = max(1, min(int(payload.max_total_capability_count or 1000), 10000))
        safe_max_capability_count_per_pack = max(1, min(int(payload.max_capability_count_per_pack or 500), 500))
        try:
            selected_pack_ids = {_validate_plugin_id(raw_id) for raw_id in _unique_texts(payload.pack_ids, limit=100)}
        except Exception:
            return {"ok": False, "applied": False, "status": "blocked", "error": "invalid_pack_id"}

        registry = _load_registry()
        _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        entries = marketplace.catalog()
        before = analyze_capability_pack_promotion_rule_remediation(entries)
        raw_queue = before.get("remediation_queue")
        queue = [item for item in raw_queue if isinstance(item, dict)] if isinstance(raw_queue, list) else []
        if selected_pack_ids:
            queue = [item for item in queue if _safe_str(item.get("pack_id")).strip() in selected_pack_ids]
        if not queue:
            return {
                "ok": True,
                "applied": False,
                "status": "no_candidates",
                "planned_pack_count": 0,
                "recorded_pack_count": 0,
                "recorded_capability_count": 0,
                "before": before,
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "writes_registry_metadata": False,
                    "writes_receipts": False,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                    "mutates_generated_artifacts": False,
                },
            }
        if len(queue) > safe_max_pack_count:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "remediation_pack_limit_exceeded",
                "candidate_total": len(queue),
                "limit": safe_max_pack_count,
            }

        prepared: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        total_capability_count = 0
        for item in queue:
            pack_id = _safe_str(item.get("pack_id")).strip()
            pack_version = _safe_str(item.get("pack_version")).strip()
            if not pack_id or not pack_version:
                skipped.append(
                    {"pack_id": pack_id, "pack_version": pack_version, "error": "pack_id_or_version_missing"}
                )
                continue
            try:
                pack_id = _validate_plugin_id(pack_id)
            except Exception:
                skipped.append({"pack_id": pack_id, "pack_version": pack_version, "error": "invalid_pack_id"})
                continue
            metadata_blockers = _supported_metadata_remediation_blockers(item)
            if not metadata_blockers:
                skipped.append(
                    {
                        "pack_id": pack_id,
                        "pack_version": pack_version,
                        "error": "no_supported_metadata_remediation",
                        "blockers": _unique_texts(item.get("blockers"), limit=50),
                    }
                )
                continue
            capability_ids = _capability_ids_for_pack(entries, pack_id=pack_id, pack_version=pack_version)
            capability_count = len(capability_ids)
            total_capability_count += capability_count
            if capability_count <= 0:
                skipped.append({"pack_id": pack_id, "pack_version": pack_version, "error": "capability_ids_required"})
                continue
            if capability_count > safe_max_capability_count_per_pack:
                skipped.append(
                    {
                        "pack_id": pack_id,
                        "pack_version": pack_version,
                        "error": "candidate_capability_limit_exceeded",
                        "capability_count": capability_count,
                        "limit": safe_max_capability_count_per_pack,
                    }
                )
                continue
            pack_entries = _entries_for_capability_pack(entries, pack_id=pack_id, pack_version=pack_version)
            prepared.append(
                {
                    "item": item,
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "pack_name": _safe_str(item.get("pack_name")).strip() or pack_id,
                    "capability_ids": capability_ids,
                    "metadata_blockers": metadata_blockers,
                    "promotion_rules": _promotion_rules_for_remediation(item, pack_entries),
                    "pack_governance": _pack_governance_for_remediation(item, pack_entries),
                }
            )
        if total_capability_count > safe_max_total_capability_count:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "total_capability_limit_exceeded",
                "capability_count": total_capability_count,
                "limit": safe_max_total_capability_count,
            }
        if not prepared:
            return {
                "ok": True,
                "applied": False,
                "status": "no_supported_metadata_remediation",
                "planned_pack_count": 0,
                "recorded_pack_count": 0,
                "recorded_capability_count": 0,
                "skipped": skipped,
                "before": before,
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "writes_registry_metadata": False,
                    "writes_receipts": False,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                    "mutates_generated_artifacts": False,
                },
            }
        planned = [
            {
                "pack_id": item["pack_id"],
                "pack_version": item["pack_version"],
                "pack_name": item["pack_name"],
                "capability_count": len(item["capability_ids"]),
                "metadata_blockers": item["metadata_blockers"],
                "promotion_rules": item["promotion_rules"],
                "pack_governance": redact_governed_display_value(item["pack_governance"]),
            }
            for item in prepared
        ]
        if payload.dry_run:
            return {
                "ok": True,
                "applied": False,
                "status": "dry_run",
                "planned_pack_count": len(planned),
                "planned_capability_count": sum(int(item.get("capability_count") or 0) for item in planned),
                "planned": planned,
                "skipped": skipped,
                "before": before,
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "writes_registry_metadata": False,
                    "writes_receipts": False,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                    "mutates_generated_artifacts": False,
                },
            }

        batch = _record_capability_pack_promotion_rule_remediation_batch(
            registry=registry,
            prepared=prepared,
            payload=payload,
            route_path=request.url.path,
        )
        recorded = batch["recorded"]
        failed = batch["failed"]

        refreshed_registry = _load_registry()
        refreshed_catalog = _compile_runtime_catalog(refreshed_registry)
        refreshed_runtime_catalog = _read_runtime_catalog_payload(refreshed_catalog)
        refreshed_marketplace = marketplace_from_plugin_catalog(refreshed_runtime_catalog)
        after = analyze_capability_pack_promotion_rule_remediation(refreshed_marketplace.catalog())
        selected_after_queue = [
            item
            for item in after.get("remediation_queue", [])
            if isinstance(item, dict)
            and (
                not selected_pack_ids
                or _safe_str(item.get("pack_id")).strip() in selected_pack_ids
                or _safe_str(item.get("pack_id")).strip() in {str(record.get("pack_id")) for record in recorded}
            )
        ]
        applied = bool(recorded)
        return {
            "ok": not failed,
            "applied": applied,
            "status": "recorded" if not failed else ("partial" if applied else "blocked"),
            "planned_pack_count": len(prepared),
            "recorded_pack_count": len(recorded),
            "recorded_capability_count": sum(int(item.get("capability_count") or 0) for item in recorded),
            "recorded": recorded,
            "failed": failed,
            "skipped": skipped,
            "remaining_remediation_queue": selected_after_queue,
            "remaining_remediation_queue_count": int(after.get("remediation_queue_count") or 0),
            "next_smallest_truthful_gap": _safe_str(after.get("next_smallest_truthful_gap")).strip(),
            "governance": {
                "scope": _PLUGIN_WRITE_SCOPE,
                "route": request.url.path,
                "writes_registry_metadata": applied,
                "writes_receipts": applied,
                "metadata_rule_governance_remediation_only": True,
                "does_not_write_quality_evidence": True,
                "does_not_write_validation_receipts": True,
                "does_not_approve_proposals": True,
                "does_not_promote_capabilities": True,
                "does_not_enable_capabilities": True,
                "does_not_execute_capabilities": True,
                "promotion_authority": False,
                "execution_authority": False,
                "approval_authority": False,
                "memory_write": False,
                "mutates_generated_artifacts": False,
            },
        }
    except Exception as exc:
        return {"ok": False, "applied": False, "status": "error", "error": api_error_message(exc)}


def _record_capability_pack_metadata_receipt_unchecked(
    payload: CapabilityPackMetadataReceiptIn,
    *,
    route_path: str,
) -> dict[str, object]:
    pack_id = _validate_plugin_id(_safe_str(payload.pack_id).strip())
    pack_version = _safe_str(payload.pack_version).strip()
    if not pack_version:
        return {"ok": False, "applied": False, "status": "blocked", "error": "pack_version_required"}

    capability_ids: list[str] = []
    for raw_id in _unique_texts(payload.capability_ids, limit=500):
        capability_ids.append(_validate_plugin_id(raw_id))

    registry = _load_registry()
    _sync_generated_plugins(registry)
    prewrite_catalog = _save_registry_and_catalog(registry)
    prewrite_runtime_catalog = _read_runtime_catalog_payload(prewrite_catalog)
    prewrite_marketplace = marketplace_from_plugin_catalog(prewrite_runtime_catalog)

    source_pack_id = _safe_str(payload.source_pack_id).strip() or pack_id
    source_pack_version = _safe_str(payload.source_pack_version).strip() or pack_version
    if payload.include_current_pack_capabilities and not capability_ids:
        source_pack_id = _validate_plugin_id(source_pack_id)
        expanded_ids = _capability_ids_for_pack(
            prewrite_marketplace.catalog(),
            pack_id=source_pack_id,
            pack_version=source_pack_version,
        )
        if len(expanded_ids) > 500:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "source_pack_capability_limit_exceeded",
                "capability_count": len(expanded_ids),
                "limit": 500,
            }
        capability_ids = expanded_ids
    if not capability_ids:
        return {"ok": False, "applied": False, "status": "blocked", "error": "capability_ids_required"}

    missing = [capability_id for capability_id in capability_ids if _read_plugin(registry, capability_id) is None]
    if missing:
        return {
            "ok": False,
            "applied": False,
            "status": "blocked",
            "error": "capability_not_found",
            "missing_capability_ids": missing,
        }

    recorded_ts = _now_s()
    receipt_id = _capability_pack_metadata_receipt_id(pack_id, recorded_ts)
    receipt_path = _capability_pack_metadata_receipt_path(receipt_id)
    pack_name = _safe_str(payload.pack_name).strip() or pack_id
    promotion_rules = _unique_texts(payload.promotion_rules, limit=50)
    pack_governance = dict(payload.pack_governance or {})
    previous_metadata: dict[str, dict[str, Any]] = {}

    for capability_id in capability_ids:
        current = _read_plugin(registry, capability_id)
        if current is None:
            continue
        meta = dict(current.get("meta") or {}) if isinstance(current.get("meta"), dict) else {}
        previous_metadata[capability_id] = {
            "pack_id": _safe_str(meta.get("pack_id")).strip(),
            "pack_version": _safe_str(meta.get("pack_version")).strip(),
            "pack_metadata_source": _safe_str(meta.get("pack_metadata_source")).strip(),
            "pack_metadata_receipt_id": _safe_str(meta.get("pack_metadata_receipt_id")).strip(),
        }
        meta.update(
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "pack_name": pack_name,
                "pack_metadata_source": "metadata_receipt",
                "pack_metadata_receipt_id": receipt_id,
                "pack_metadata_receipt_path": str(receipt_path),
            }
        )
        if promotion_rules:
            meta["promotion_rules"] = promotion_rules
        if pack_governance:
            meta["pack_governance"] = pack_governance
        current["meta"] = meta
        current["updated_ts"] = recorded_ts
        _write_plugin(registry, _normalize_plugin_record(capability_id, current))

    catalog = _save_registry_and_catalog(registry)
    receipt = _write_capability_pack_metadata_receipt(
        receipt_id=receipt_id,
        receipt_path=receipt_path,
        payload=payload,
        pack_id=pack_id,
        pack_version=pack_version,
        pack_name=pack_name,
        capability_ids=capability_ids,
        previous_metadata=previous_metadata,
        recorded_ts=recorded_ts,
        route_path=route_path,
    )
    runtime_catalog = _read_runtime_catalog_payload(catalog)
    marketplace = marketplace_from_plugin_catalog(runtime_catalog)

    return {
        "ok": True,
        "applied": True,
        "status": "recorded",
        "receipt_id": receipt_id,
        "receipt_path": str(receipt_path),
        "receipt": receipt,
        "capability_count": len(capability_ids),
        "catalog": catalog,
        "pack_readiness": analyze_capability_pack_readiness(marketplace.catalog()),
        "governance": {
            "scope": _PLUGIN_WRITE_SCOPE,
            "route": route_path,
            "writes_registry_metadata": True,
            "writes_receipt": True,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
            "mutates_generated_artifacts": False,
        },
    }


@router.post("/capabilities/packs/metadata/receipts")
def record_capability_pack_metadata_receipt(
    payload: CapabilityPackMetadataReceiptIn,
    request: Request,
) -> dict[str, object]:
    try:
        permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
        if not permission.allowed:
            return _permission_denied(permission)
        return _record_capability_pack_metadata_receipt_unchecked(payload, route_path=request.url.path)
    except Exception as exc:
        return {"ok": False, "applied": False, "status": "error", "error": api_error_message(exc)}


@router.post("/capabilities/packs/metadata/receipts/bulk-from-plan")
def record_capability_pack_metadata_receipts_from_plan(
    payload: CapabilityPackMetadataReceiptBulkFromPlanIn,
    request: Request,
) -> dict[str, object]:
    try:
        permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
        if not permission.allowed:
            return _permission_denied(permission)

        safe_max_pack_count = max(1, min(int(payload.max_pack_count or 50), 100))
        safe_max_total_capability_count = max(1, min(int(payload.max_total_capability_count or 5000), 10000))
        safe_max_capability_count_per_pack = max(1, min(int(payload.max_capability_count_per_pack or 500), 500))
        selected_pack_ids = {_validate_plugin_id(raw_id) for raw_id in _unique_texts(payload.pack_ids, limit=100)}

        registry = _load_registry()
        _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        entries = marketplace.catalog()
        plan = analyze_capability_pack_migration_plan(entries)
        raw_candidates = plan.get("candidates")
        candidates = (
            [candidate for candidate in raw_candidates if isinstance(candidate, dict)]
            if isinstance(raw_candidates, list)
            else []
        )
        if selected_pack_ids:
            candidates = [
                candidate
                for candidate in candidates
                if _safe_str(candidate.get("pack_id")).strip() in selected_pack_ids
            ]
        if not candidates:
            return {
                "ok": True,
                "applied": False,
                "status": "no_candidates",
                "recorded_pack_count": 0,
                "recorded_capability_count": 0,
                "plan": plan,
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "writes_registry_metadata": False,
                    "writes_receipts": False,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                },
            }
        if len(candidates) > safe_max_pack_count:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "candidate_pack_limit_exceeded",
                "candidate_total": len(candidates),
                "limit": safe_max_pack_count,
            }

        prepared: list[dict[str, Any]] = []
        total_capability_count = 0
        blocked_candidates: list[dict[str, Any]] = []
        for candidate in candidates:
            pack_id = _validate_plugin_id(_safe_str(candidate.get("pack_id")).strip())
            pack_version = _safe_str(candidate.get("pack_version")).strip()
            capability_ids = _capability_ids_for_pack(entries, pack_id=pack_id, pack_version=pack_version)
            capability_count = len(capability_ids)
            total_capability_count += capability_count
            if capability_count <= 0:
                blocked_candidates.append({"pack_id": pack_id, "error": "capability_ids_required"})
            if capability_count > safe_max_capability_count_per_pack:
                blocked_candidates.append(
                    {
                        "pack_id": pack_id,
                        "error": "candidate_capability_limit_exceeded",
                        "capability_count": capability_count,
                        "limit": safe_max_capability_count_per_pack,
                    }
                )
            prepared.append(
                {
                    "candidate": candidate,
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "capability_ids": capability_ids,
                }
            )
        if total_capability_count > safe_max_total_capability_count:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "total_capability_limit_exceeded",
                "capability_count": total_capability_count,
                "limit": safe_max_total_capability_count,
            }
        if blocked_candidates:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "candidate_preflight_failed",
                "blocked_candidates": blocked_candidates,
            }

        pending_receipts: list[dict[str, Any]] = []
        recorded_ts = _now_s()
        for item in prepared:
            candidate = item["candidate"]
            pack_id = item["pack_id"]
            pack_version = item["pack_version"]
            capability_ids = list(item["capability_ids"])
            receipt_id = _capability_pack_metadata_receipt_id(pack_id, recorded_ts)
            receipt_path = _capability_pack_metadata_receipt_path(receipt_id)
            pack_name = _safe_str(candidate.get("pack_name")).strip() or pack_id
            promotion_rules = _unique_texts(candidate.get("suggested_promotion_rules"), limit=50)
            pack_governance = dict(candidate.get("suggested_pack_governance") or {})
            previous_metadata: dict[str, dict[str, Any]] = {}
            for capability_id in capability_ids:
                current = _read_plugin(registry, capability_id)
                if current is None:
                    return {
                        "ok": False,
                        "applied": False,
                        "status": "blocked",
                        "error": "capability_not_found",
                        "missing_capability_ids": [capability_id],
                    }
                meta = dict(current.get("meta") or {}) if isinstance(current.get("meta"), dict) else {}
                previous_metadata[capability_id] = {
                    "pack_id": _safe_str(meta.get("pack_id")).strip(),
                    "pack_version": _safe_str(meta.get("pack_version")).strip(),
                    "pack_metadata_source": _safe_str(meta.get("pack_metadata_source")).strip(),
                    "pack_metadata_receipt_id": _safe_str(meta.get("pack_metadata_receipt_id")).strip(),
                }
                meta.update(
                    {
                        "pack_id": pack_id,
                        "pack_version": pack_version,
                        "pack_name": pack_name,
                        "pack_metadata_source": "metadata_receipt",
                        "pack_metadata_receipt_id": receipt_id,
                        "pack_metadata_receipt_path": str(receipt_path),
                    }
                )
                if promotion_rules:
                    meta["promotion_rules"] = promotion_rules
                if pack_governance:
                    meta["pack_governance"] = pack_governance
                current["meta"] = meta
                current["updated_ts"] = recorded_ts
                _write_plugin(registry, _normalize_plugin_record(capability_id, current))

            receipt_payload = CapabilityPackMetadataReceiptIn(
                actor=payload.actor,
                reason=f"{payload.reason}:{pack_id}",
                pack_id=pack_id,
                pack_version=pack_version,
                pack_name=pack_name,
                capability_ids=capability_ids,
                source_pack_id=pack_id,
                source_pack_version=pack_version,
                promotion_rules=promotion_rules,
                pack_governance=pack_governance,
                meta={
                    **redact_governed_metadata(payload.meta),
                    "bulk_from_migration_plan": True,
                    "source_candidate_blockers": candidate.get("blockers")
                    if isinstance(candidate.get("blockers"), list)
                    else [],
                },
            )
            pending_receipts.append(
                {
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "receipt_id": receipt_id,
                    "receipt_path": receipt_path,
                    "payload": receipt_payload,
                    "pack_name": pack_name,
                    "capability_ids": capability_ids,
                    "previous_metadata": previous_metadata,
                }
            )

        _save_registry_and_catalog(registry)
        recorded: list[dict[str, Any]] = []
        for item in pending_receipts:
            receipt = _write_capability_pack_metadata_receipt(
                receipt_id=str(item["receipt_id"]),
                receipt_path=item["receipt_path"],
                payload=item["payload"],
                pack_id=str(item["pack_id"]),
                pack_version=str(item["pack_version"]),
                pack_name=str(item["pack_name"]),
                capability_ids=list(item["capability_ids"]),
                previous_metadata=item["previous_metadata"],
                recorded_ts=recorded_ts,
                route_path=request.url.path,
            )
            recorded.append(
                {
                    "pack_id": item["pack_id"],
                    "pack_version": item["pack_version"],
                    "receipt_id": item["receipt_id"],
                    "receipt_path": str(item["receipt_path"]),
                    "capability_count": len(item["capability_ids"]),
                    "receipt_status": receipt.get("status"),
                }
            )

        refreshed_registry = _load_registry()
        refreshed_catalog = _compile_runtime_catalog(refreshed_registry)
        refreshed_runtime_catalog = _read_runtime_catalog_payload(refreshed_catalog)
        refreshed_marketplace = marketplace_from_plugin_catalog(refreshed_runtime_catalog)
        refreshed_plan = analyze_capability_pack_migration_plan(refreshed_marketplace.catalog())
        return {
            "ok": True,
            "applied": True,
            "status": "recorded",
            "recorded_pack_count": len(recorded),
            "recorded_capability_count": sum(int(item.get("capability_count") or 0) for item in recorded),
            "recorded": recorded,
            "remaining_candidate_total": int(refreshed_plan.get("candidate_total") or 0),
            "next_smallest_truthful_gap": str(refreshed_plan.get("next_smallest_truthful_gap") or ""),
            "governance": {
                "scope": _PLUGIN_WRITE_SCOPE,
                "route": request.url.path,
                "writes_registry_metadata": True,
                "writes_receipts": True,
                "promotion_authority": False,
                "execution_authority": False,
                "approval_authority": False,
                "memory_write": False,
                "mutates_generated_artifacts": False,
            },
        }
    except Exception as exc:
        return {"ok": False, "applied": False, "status": "error", "error": api_error_message(exc)}


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
                    (
                        artifact_path := _plugin_artifact_path(
                            plugin_id,
                            _safe_str(item.get("artifact_zip")).strip(),
                        )
                    )
                    is not None
                    # CodeQL false positive: artifact_path is constrained by _plugin_artifact_path.
                    and artifact_path.exists()
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
            item["runtime"] = {
                "generated_dir": _safe_str(item.get("generated_dir")).strip(),
                "artifact_exists": False,
                "spec_exists": False,
                "registry_snapshot_exists": False,
            }

        return {"ok": True, "item": item}
    except Exception as exc:
        return {"ok": False, "error": api_error_message(exc), "item": None}


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
        return {"items": [], "tools": [], "total": 0, "offset": 0, "limit": 0, "error": api_error_message(exc)}


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
        return {"ok": False, "error": api_error_message(exc), "item": None}


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
        return {"ok": False, "status": "error", "error": api_error_message(exc)}


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
        return {"ok": False, "error": api_error_message(exc)}


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
        return {"ok": False, "error": api_error_message(exc)}


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
        return {"ok": False, "error": api_error_message(exc)}


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
            generated_path = _generated_plugin_dir(plugin_id, generated_dir)
            # CodeQL false positive: generated_path is constrained to the exact generated plugin directory.
            if generated_path is not None and generated_path.exists():
                # CodeQL false positive: generated_path is constrained to the exact generated plugin directory.
                shutil.rmtree(generated_path, ignore_errors=True)

        if artifact_zip:
            artifact_path = _plugin_artifact_path(plugin_id, artifact_zip)
            # CodeQL false positive: artifact_path is constrained to data/artifacts/plugins/<plugin_id>.zip.
            if artifact_path is not None and artifact_path.exists():
                try:
                    # CodeQL false positive: artifact_path is constrained to data/artifacts/plugins/<plugin_id>.zip.
                    artifact_path.unlink()
                except OSError:
                    pass

        _delete_plugin(registry, plugin_id)
        catalog = _save_registry_and_catalog(registry)
        return {"ok": True, "id": plugin_id, "status": "uninstalled", "message": "uninstalled", "catalog": catalog}
    except Exception as exc:
        return {"ok": False, "error": api_error_message(exc)}


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
        return {"ok": False, "status": "error", "error": api_error_message(exc)}


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
        return {"ok": False, "error": api_error_message(exc)}
