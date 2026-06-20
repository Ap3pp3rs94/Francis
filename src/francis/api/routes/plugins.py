from __future__ import annotations

from francis.api.errors import api_error_message
import csv
from dataclasses import replace
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import time
import tomllib
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
_CAPABILITY_PACK_QUALITY_EVIDENCE_CAPABILITY_PREVIEW_LIMIT = 50
_CAPABILITY_PACK_QUALITY_EVIDENCE_LINK_PREVIEW_LIMIT = 25
_CAPABILITY_PACK_ARTIFACT_RECONSTRUCTION_PLAN_LIMIT = 25
_CAPABILITY_PACK_OPERATOR_SURFACE_PACK_PREVIEW_LIMIT = 25
_CAPABILITY_LIBRARY_OPERATOR_SURFACE_PACK_PREVIEW_LIMIT = 50
_CAPABILITY_LIBRARY_PROMOTION_PLAN_CAPABILITY_PREVIEW_LIMIT = 100
_CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_PLAN_PREVIEW_LIMIT = 100
_CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_REMEDIATION_PREVIEW_LIMIT = 100
_CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_FRICTION_REF_PREVIEW_LIMIT = 100
_CAPABILITY_LIBRARY_PROPOSAL_REVIEW_PLAN_PREVIEW_LIMIT = 100
_CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_EXPORT_ROW_LIMIT = 5000
_PLUGIN_ARTIFACT_LINK_BODY_MAX_BYTES = 256 * 1024
_CAPABILITY_PACK_QUALITY_TEST_REFERENCE_CANDIDATES = ("tests/test_api_plugins.py",)
_CAPABILITY_PACK_QUALITY_DOC_REFERENCE_CANDIDATES = (
    "README.md",
    "docs/operations/COMPLETION_LEDGER.md",
)
_CAPABILITY_PACK_ARTIFACT_RECONSTRUCTION_ROUTE = "/plugins/capabilities/packs/quality/evidence/remediation/reconstruct"
_CAPABILITY_PACK_ARTIFACT_RECONSTRUCTION_SOURCE = "stage17_capability_pack_artifact_reconstruction_apply"
_CAPABILITY_PACK_QUALITY_STANDARD_REMEDIATION_SOURCE = "stage17_capability_pack_quality_standard_remediation_apply"
_CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_REMEDIATION_APPLY_ROUTE = (
    "/plugins/capabilities/library/proposal-evidence/remediation/apply"
)
_CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_REMEDIATION_SOURCE = (
    "stage17_capability_library_proposal_evidence_remediation_apply"
)
_CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_SOURCE_READINESS_ROUTE = (
    "/plugins/capabilities/library/proposal-evidence/source-readiness"
)
_CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_FRICTION_REF_APPLY_ROUTE = (
    "/plugins/capabilities/library/proposal-evidence/friction-summary-refs/apply"
)
_CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_FRICTION_REF_SOURCE = (
    "stage17_capability_library_proposal_evidence_friction_summary_refs_apply"
)
_CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_FRICTION_REF_CLAIM_SCOPE = (
    "existing_registry_friction_summary_reference_not_independent_verification"
)
_CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_APPLY_ROUTE = (
    "/plugins/capabilities/library/proposal-evidence/operator-intake/apply"
)
_CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_PREVIEW_ROUTE = (
    "/plugins/capabilities/library/proposal-evidence/operator-intake/preview"
)
_CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_CHECKLIST_ROUTE = (
    "/plugins/capabilities/library/proposal-evidence/operator-intake/checklist"
)
_CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_WORKSHEET_ROUTE = (
    "/plugins/capabilities/library/proposal-evidence/operator-intake/worksheet"
)
_CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_EXPORT_ROUTE = (
    "/plugins/capabilities/library/proposal-evidence/operator-intake/export"
)
_CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_IMPORT_PREVIEW_ROUTE = (
    "/plugins/capabilities/library/proposal-evidence/operator-intake/import-preview"
)
_CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_AUDIT_ROUTE = (
    "/plugins/capabilities/library/proposal-evidence/operator-intake/audit"
)
_CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_SOURCE = (
    "stage17_capability_library_operator_proposal_evidence_intake_apply"
)
_CAPABILITY_LIBRARY_PROPOSAL_REVIEW_APPLY_READINESS_ROUTE = (
    "/plugins/capabilities/library/proposal-review/apply-readiness"
)
_CAPABILITY_LIBRARY_PROPOSAL_REVIEW_APPLY_ROUTE = "/plugins/capabilities/library/proposal-review/apply"
_CAPABILITY_LIBRARY_EXPLICIT_PROMOTION_APPLY_ROUTE = "/plugins/capabilities/library/promotion/apply"
_PLUGIN_LIFECYCLE_REPAIR_ROUTE = "/plugins/lifecycle/repair"
_PLUGIN_LIFECYCLE_REPAIR_HISTORY_ROUTE = "/plugins/lifecycle/repair/history"
_CAPABILITY_LIBRARY_PROPOSAL_REVIEW_DECISIONS = {
    "approve": "approved",
    "approved": "approved",
    "reject": "rejected",
    "rejected": "rejected",
    "request_changes": "needs_revision",
    "needs_revision": "needs_revision",
}
_PLUGIN_DISABLE_LIFECYCLE_ACTIONS = {
    "disable": ("disable", "disabled"),
    "disabled": ("disable", "disabled"),
    "quarantine": ("quarantine", "quarantined"),
    "quarantined": ("quarantine", "quarantined"),
    "deprecate": ("deprecate", "deprecated"),
    "deprecated": ("deprecate", "deprecated"),
    "deprecation": ("deprecate", "deprecated"),
}
_PLUGIN_REPAIR_LIFECYCLE_ACTIONS = {
    "repair": "repair",
    "repaired": "repair",
    "restore": "restore",
    "restored": "restore",
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


def _now_utc_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _stage17_projection_evidence(
    *,
    projection_scope: str,
    global_counts_included: bool,
    selected_pack_ids: set[str] | None = None,
    selected_capability_ids: set[str] | None = None,
    generated_plugin_sync_performed: bool = False,
) -> dict[str, object]:
    selected_packs = sorted(_unique_texts(sorted(selected_pack_ids or set()), limit=1000))
    selected_capabilities = sorted(_unique_texts(sorted(selected_capability_ids or set()), limit=10000))
    return {
        "generated_at": _now_utc_iso(),
        "projection_contract": "stage17_capability_library_projection_evidence_v1",
        "projection_evidence": {
            "contract": "stage17_capability_library_projection_evidence_v1",
            "stage": "Stage 17 / Capability Economy",
            "projection_scope": _safe_str(projection_scope).strip() or "full_library",
            "global_counts_included": bool(global_counts_included),
            "selected_pack_ids": selected_packs,
            "selected_capability_ids": selected_capabilities,
            "selected_pack_count": len(selected_packs),
            "selected_capability_count": len(selected_capabilities),
            "generated_plugin_registry_sync_performed": bool(generated_plugin_sync_performed),
            "read_only_projection": True,
            "writes_repo": False,
            "writes_data": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }


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


def _plugin_proposal_friction_evidence(proposal_id: str) -> list[str]:
    resolved_id = _safe_str(proposal_id).strip()
    if not resolved_id or not _PLUGIN_ARTIFACT_ID_RE.match(resolved_id):
        return []

    proposal_root = _art_dir() / "proposals"
    proposal_path = _plugin_proposal_path(resolved_id)
    if not _is_under(proposal_root, proposal_path):
        return []
    if not proposal_path.exists() or not proposal_path.is_file():
        return []

    try:
        raw = json.loads(proposal_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []
    if not isinstance(raw, dict):
        return []
    friction = raw.get("friction") if isinstance(raw.get("friction"), dict) else {}
    return _unique_texts(friction.get("evidence"), limit=50)


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


def _plugin_lifecycle_receipt_path(receipt_id: str) -> Path:
    return _art_dir() / "lifecycle" / f"{_safe_str(receipt_id).strip()}.json"


def _plugin_lifecycle_receipt_id(plugin_id: str, action: str, recorded_ts: int) -> str:
    return f"plugin_lifecycle_{recorded_ts}_{_slugify(plugin_id)}_{_slugify(action)}"


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


def _capability_pack_review_staged_capability_ids(
    entries: list[dict[str, Any]],
    *,
    pack_id: str,
    pack_version: str,
) -> list[str]:
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
    return sorted(set(staged_capability_ids))


def _write_capability_pack_operator_review_decision_receipt(
    *,
    pack: dict[str, Any],
    pack_id: str,
    pack_version: str,
    action: str,
    decided_status: str,
    actor: Any,
    reason: str,
    notes: str,
    meta: dict[str, Any],
    capability_ids: list[str],
    route: str = "/plugins/capabilities/packs/operator/review/decisions",
) -> dict[str, Any]:
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
        "actor": redact_governed_value(_safe_str(actor).strip()),
        "reason": redact_governed_value(reason or "requested"),
        "notes": redact_governed_value(notes),
        "decided_ts": decided_ts,
        "meta": redact_governed_metadata(meta),
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
            "route": route,
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
    return {"receipt_id": receipt_id, "receipt_path": str(receipt_path), "receipt": redacted_receipt}


def _capability_pack_operator_review_decision_keys(
    decisions: list[dict[str, Any]],
) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for decision in decisions:
        if not isinstance(decision, dict):
            continue
        pack_id = _safe_str(decision.get("pack_id")).strip()
        pack_version = _safe_str(decision.get("pack_version")).strip()
        status = _safe_str(decision.get("status")).strip().lower()
        receipt_id = _safe_str(decision.get("receipt_id")).strip()
        if pack_id and pack_version and status in {"approved", "rejected", "deferred"} and receipt_id:
            out.add((pack_id, pack_version))
    return out


def _capability_pack_operator_review_decision_coverage(
    decisions: list[dict[str, Any]],
) -> dict[tuple[str, str], set[str]]:
    coverage: dict[tuple[str, str], set[str]] = {}
    for decision in decisions:
        if not isinstance(decision, dict):
            continue
        pack_id = _safe_str(decision.get("pack_id")).strip()
        pack_version = _safe_str(decision.get("pack_version")).strip()
        status = _safe_str(decision.get("status")).strip().lower()
        receipt_id = _safe_str(decision.get("receipt_id")).strip()
        if pack_id and pack_version and status == "approved" and receipt_id:
            coverage.setdefault((pack_id, pack_version), set()).update(
                _unique_texts(decision.get("capability_ids"), limit=500)
            )
    return coverage


def _capability_pack_operator_review_decision_covers(
    coverage: dict[tuple[str, str], set[str]],
    *,
    pack_id: str,
    pack_version: str,
    capability_ids: list[str],
) -> bool:
    required = set(_unique_texts(capability_ids, limit=500))
    return bool(required) and required.issubset(coverage.get((pack_id, pack_version), set()))


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
    quality_meta = payload_meta.get("quality") if isinstance(payload_meta.get("quality"), dict) else {}
    generated_dir = _safe_str(promoted.get("generated_dir")).strip()
    plugin_dir = _generated_plugin_dir(plugin_id, generated_dir)
    readme_path = _generated_child_path(plugin_dir, "README.md") if plugin_dir is not None else None
    tests: Any = payload_meta.get("tests") or payload_meta.get("test_refs") or quality_meta.get("tests") or []
    docs: Any = payload_meta.get("docs") or payload_meta.get("documentation") or quality_meta.get("docs") or []
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
        "tests": tests,
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


def _current_core_version() -> str:
    try:
        payload = tomllib.loads((repo_root() / "pyproject.toml").read_text(encoding="utf-8"))
        project = payload.get("project") if isinstance(payload, dict) else {}
        version = _safe_str(project.get("version") if isinstance(project, dict) else "").strip()
        if version:
            return version
    except Exception:
        pass
    return "0.0.0+dev"


def _version_triplet(value: Any) -> tuple[int, int, int] | None:
    text = _safe_str(value).strip().lower()
    if text.startswith("v"):
        text = text[1:]
    text = re.split(r"[+-]", text, maxsplit=1)[0]
    parts = text.split(".")
    if not 1 <= len(parts) <= 3:
        return None
    if any(not part.isdigit() for part in parts):
        return None
    numbers = [int(part) for part in parts]
    while len(numbers) < 3:
        numbers.append(0)
    return numbers[0], numbers[1], numbers[2]


def _plugin_core_compatibility(payload_meta: dict[str, Any]) -> dict[str, Any]:
    compatibility = payload_meta.get("compatibility") if isinstance(payload_meta.get("compatibility"), dict) else {}
    min_core_version = _safe_str(
        compatibility.get("min_core_version")
        or compatibility.get("minimum_core_version")
        or compatibility.get("min_francis_version")
    ).strip()
    current_core_version = _current_core_version()
    contract = "plugin.compatibility.min_core_version"
    if not min_core_version:
        return {
            "compatible": True,
            "status": "no_min_core_version_declared",
            "contract": contract,
            "current_core_version": current_core_version,
            "min_core_version": "",
            "source": "pyproject.toml",
        }

    current_triplet = _version_triplet(current_core_version)
    minimum_triplet = _version_triplet(min_core_version)
    if minimum_triplet is None:
        return {
            "compatible": False,
            "status": "invalid_min_core_version",
            "contract": contract,
            "current_core_version": current_core_version,
            "min_core_version": min_core_version,
            "source": "pyproject.toml",
        }
    if current_triplet is None:
        return {
            "compatible": False,
            "status": "current_core_version_unknown",
            "contract": contract,
            "current_core_version": current_core_version,
            "min_core_version": min_core_version,
            "source": "pyproject.toml",
        }

    compatible = current_triplet >= minimum_triplet
    return {
        "compatible": compatible,
        "status": "compatible" if compatible else "requires_newer_core",
        "contract": contract,
        "current_core_version": current_core_version,
        "min_core_version": min_core_version,
        "source": "pyproject.toml",
    }


_PLUGIN_LIFECYCLE_BLOCKING_STATES = {
    "archived",
    "deprecated",
    "quarantined",
    "retired",
}
_PLUGIN_LIFECYCLE_REGISTRY_BLOCKING_STATES = {
    "archived",
    "deprecated",
    "quarantined",
    "retired",
}
_PLUGIN_LIFECYCLE_NON_BLOCKING_STATES = {
    "active",
    "beta",
    "disabled",
    "enabled",
    "experimental",
    "preview",
    "promoted",
    "stable",
    "staged",
    "uninstalled",
}


def _normalize_lifecycle_state(value: Any) -> str:
    text = _safe_str(value).strip().lower()
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _plugin_lifecycle_state(plugin: dict[str, Any], payload_meta: dict[str, Any]) -> dict[str, Any]:
    plugin_meta = dict(plugin.get("meta") or {}) if isinstance(plugin.get("meta"), dict) else {}
    candidates: list[dict[str, Any]] = []

    def add_candidate(source: str, value: Any, *, explicit: bool) -> None:
        raw = _safe_str(value).strip()
        normalized = _normalize_lifecycle_state(raw)
        if normalized:
            candidates.append(
                {
                    "source": source,
                    "raw": raw,
                    "state": normalized,
                    "explicit_lifecycle_metadata": explicit,
                }
            )

    for key in (
        "lifecycle_status",
        "lifecycle_state",
        "capability_lifecycle_status",
        "deprecation_status",
        "quarantine_status",
    ):
        add_candidate(f"registry.meta.{key}", plugin_meta.get(key), explicit=True)

    add_candidate("registry.status", plugin.get("status"), explicit=False)
    add_candidate("registry.meta.status", plugin_meta.get("status"), explicit=False)
    add_candidate("registry.meta.promotion_status", plugin_meta.get("promotion_status"), explicit=False)

    for key in (
        "lifecycle_status",
        "lifecycle_state",
        "capability_lifecycle_status",
        "deprecation_status",
        "quarantine_status",
    ):
        add_candidate(f"request.meta.{key}", payload_meta.get(key), explicit=True)

    blocking = next(
        (
            item
            for item in candidates
            if (
                bool(item["explicit_lifecycle_metadata"])
                and _safe_str(item.get("state")).strip() in _PLUGIN_LIFECYCLE_BLOCKING_STATES
            )
            or (
                not bool(item["explicit_lifecycle_metadata"])
                and _safe_str(item.get("state")).strip() in _PLUGIN_LIFECYCLE_REGISTRY_BLOCKING_STATES
            )
        ),
        None,
    )
    unknown = next(
        (
            item
            for item in candidates
            if bool(item["explicit_lifecycle_metadata"])
            and _safe_str(item.get("state")).strip() not in _PLUGIN_LIFECYCLE_BLOCKING_STATES
            and _safe_str(item.get("state")).strip() not in _PLUGIN_LIFECYCLE_NON_BLOCKING_STATES
        ),
        None,
    )
    selected = blocking or unknown or (candidates[0] if candidates else None)
    status = _safe_str(selected.get("state") if isinstance(selected, dict) else "").strip() or "active"
    source = _safe_str(selected.get("source") if isinstance(selected, dict) else "").strip()
    blocks = bool(blocking or unknown)
    error = (
        "plugin_lifecycle_state_unknown"
        if unknown is not None and blocking is None
        else f"plugin_{status}"
        if blocks
        else ""
    )
    reason = (
        "explicit_unknown_lifecycle_state"
        if unknown is not None and blocking is None
        else "explicit_or_registry_lifecycle_block"
        if blocks
        else "lifecycle_state_allows_promotion_and_execution"
    )
    return {
        "status": status,
        "source": source,
        "contract": "plugin.lifecycle.quarantine_deprecation_v1",
        "blocks_promotion": blocks,
        "blocks_execution": blocks,
        "error": error,
        "reason": reason,
        "known_blocking_states": sorted(_PLUGIN_LIFECYCLE_BLOCKING_STATES),
        "known_non_blocking_states": sorted(_PLUGIN_LIFECYCLE_NON_BLOCKING_STATES),
        "observed_states": candidates,
    }


def _plugin_promotion_readiness(
    plugin_id: str,
    staged: dict[str, Any],
    payload: "PluginToggleIn",
) -> dict[str, Any]:
    staged_meta = dict(staged.get("meta") or {}) if isinstance(staged.get("meta"), dict) else {}
    payload_meta = {**staged_meta, **redact_governed_metadata(payload.meta)}
    quality_meta = payload_meta.get("quality") if isinstance(payload_meta.get("quality"), dict) else {}
    generated_dir = _safe_str(staged.get("generated_dir")).strip()
    plugin_dir = _generated_plugin_dir(plugin_id, generated_dir)
    readme_path = _generated_child_path(plugin_dir, "README.md") if plugin_dir is not None else None
    docs = payload_meta.get("docs") or payload_meta.get("documentation") or quality_meta.get("docs") or []
    # CodeQL false positive: readme_path is constrained under the exact generated plugin directory.
    if not _has_readiness_value(docs) and readme_path is not None and readme_path.exists():
        # CodeQL false positive: readme_path is constrained under the exact generated plugin directory.
        docs = [str(readme_path.resolve())]

    proposal_id = _safe_str(payload_meta.get("proposal_id") or payload_meta.get("forge_proposal_id")).strip()
    artifact_evidence = _plugin_proposal_friction_evidence(proposal_id)
    risk_tier = _safe_str(payload_meta.get("risk_tier")).strip().lower() or _plugin_risk_tier(staged)
    evidence = payload_meta.get("proposal_evidence") or payload_meta.get("evidence") or artifact_evidence
    tests = payload_meta.get("tests") or payload_meta.get("test_refs") or quality_meta.get("tests") or []
    proposal_review = _plugin_proposal_review_state(proposal_id)
    pack_operator_review = _capability_pack_operator_review_state(plugin_id, payload_meta)
    compatibility = _plugin_core_compatibility(payload_meta)
    lifecycle = _plugin_lifecycle_state(staged, payload_meta)
    requirements = {
        "proposal_id": bool(proposal_id),
        "proposal_review": bool(proposal_review["approved"]),
        "proposal_evidence": _has_readiness_value(evidence),
        "tests": _has_readiness_value(tests),
        "docs": _has_readiness_value(docs),
        "risk_tier": risk_tier in _RISK_ORDER,
        "core_compatibility": bool(compatibility["compatible"]),
        "lifecycle_state": not bool(lifecycle["blocks_promotion"]),
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
            "compatibility": compatibility,
            "lifecycle": lifecycle,
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
                "proposal evidence, tests, docs, a bounded risk tier, core compatibility, and a non-blocking "
                "lifecycle state."
            ),
        },
    }


def _plugin_runtime_compatibility_blocked(
    *,
    plugin_id: str,
    action: str,
    compatibility: dict[str, Any],
) -> dict[str, object]:
    status = _safe_str(compatibility.get("status")).strip() or "incompatible"
    return {
        "ok": False,
        "error": "plugin_core_incompatible",
        "id": plugin_id,
        "status": "blocked",
        "compatibility": redact_governed_display_value(compatibility),
        "message": "Plugin execution is blocked by the recorded core compatibility requirement.",
        "governance": {
            "plane": "P3_GOVERNANCE",
            "gate": "plugin_runtime_compatibility_gate",
            "scope": "plugin.run",
            "route": "/plugins/run",
            "next_step": "review_plugin_compatibility_before_execution",
            "operator_hint": (
                "A plugin requiring a newer or malformed Francis core version must be migrated or repaired before "
                "execution."
            ),
            "action": _safe_str(action).strip(),
            "compatibility_status": status,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
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
    proposal_evidence = (
        payload_meta.get("proposal_evidence")
        or payload_meta.get("evidence")
        or (_plugin_proposal_friction_evidence(proposal_id))
    )
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
        "compatibility": _plugin_core_compatibility(payload_meta),
        "lifecycle": _plugin_lifecycle_state(promoted, payload_meta),
        "proposal_evidence": proposal_evidence,
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


def _plugin_disable_lifecycle(raw_meta: dict[str, Any]) -> dict[str, Any]:
    raw_action = (
        _safe_str(raw_meta.get("lifecycle_action")).strip()
        or _safe_str(raw_meta.get("lifecycle_status")).strip()
        or "disable"
    )
    normalized = raw_action.lower().replace("-", "_")
    if normalized not in _PLUGIN_DISABLE_LIFECYCLE_ACTIONS:
        return {
            "supported": False,
            "requested_action": raw_action,
            "action": normalized,
            "lifecycle_status": "",
        }
    action, lifecycle_status = _PLUGIN_DISABLE_LIFECYCLE_ACTIONS[normalized]
    return {
        "supported": True,
        "requested_action": raw_action,
        "action": action,
        "lifecycle_status": lifecycle_status,
    }


def _plugin_repair_lifecycle(raw_meta: dict[str, Any]) -> dict[str, Any]:
    raw_action = (
        _safe_str(raw_meta.get("lifecycle_repair_action")).strip()
        or _safe_str(raw_meta.get("repair_action")).strip()
        or _safe_str(raw_meta.get("lifecycle_action")).strip()
        or "repair"
    )
    normalized = raw_action.lower().replace("-", "_")
    if normalized not in _PLUGIN_REPAIR_LIFECYCLE_ACTIONS:
        return {
            "supported": False,
            "requested_action": raw_action,
            "action": normalized,
        }
    return {
        "supported": True,
        "requested_action": raw_action,
        "action": _PLUGIN_REPAIR_LIFECYCLE_ACTIONS[normalized],
    }


def _plugin_lifecycle_repair_status(
    current: dict[str, Any],
    meta: dict[str, Any],
    lifecycle: dict[str, Any],
) -> str:
    lifecycle_status = _safe_str(lifecycle.get("status")).strip()
    candidates = [
        meta.get(f"{lifecycle_status}_from_status"),
        meta.get("disabled_from_status"),
        current.get("status"),
    ]
    for candidate in candidates:
        status = _normalize_lifecycle_state(candidate)
        if status == "staged":
            return "staged"
        if status in {"disabled", "enabled", "promoted"}:
            return "disabled"
    return "disabled"


def _plugin_lifecycle_repair_promotion_status(
    meta: dict[str, Any],
    lifecycle: dict[str, Any],
    restored_status: str,
) -> str:
    lifecycle_status = _safe_str(lifecycle.get("status")).strip()
    candidates = [
        meta.get(f"{lifecycle_status}_from_promotion_status"),
        meta.get("disabled_from_promotion_status"),
        meta.get("promotion_status"),
        restored_status,
    ]
    for candidate in candidates:
        status = _normalize_lifecycle_state(candidate)
        if status == "staged":
            return "staged"
        if status in {"disabled", "enabled", "promoted"}:
            return "disabled"
    return "staged" if restored_status == "staged" else "disabled"


def _plugin_lifecycle_last_non_blocking_metadata(
    current: dict[str, Any],
    meta: dict[str, Any],
    lifecycle: dict[str, Any],
    *,
    restored_status: str,
    restored_promotion_status: str,
) -> dict[str, Any]:
    lifecycle_status = _safe_str(lifecycle.get("status")).strip()
    candidates = [
        (f"registry.meta.{lifecycle_status}_from_status", meta.get(f"{lifecycle_status}_from_status")),
        ("registry.meta.disabled_from_status", meta.get("disabled_from_status")),
        ("registry.meta.status", meta.get("status")),
        ("registry.status", current.get("status")),
        (
            f"registry.meta.{lifecycle_status}_from_promotion_status",
            meta.get(f"{lifecycle_status}_from_promotion_status"),
        ),
        ("registry.meta.disabled_from_promotion_status", meta.get("disabled_from_promotion_status")),
        ("registry.meta.promotion_status", meta.get("promotion_status")),
    ]
    selected = {"source": "", "raw": "", "status": ""}
    for source, value in candidates:
        normalized = _normalize_lifecycle_state(value)
        if normalized in _PLUGIN_LIFECYCLE_NON_BLOCKING_STATES:
            selected = {
                "source": source,
                "raw": _safe_str(value).strip(),
                "status": normalized,
            }
            break
    return {
        **selected,
        "safe_registry_status": restored_status,
        "safe_promotion_status": restored_promotion_status,
        "target_lifecycle_status": "active",
        "safe_enabled": False,
    }


def _plugin_lifecycle_repair_plan(
    *,
    plugin_id: str,
    current: dict[str, Any],
    meta: dict[str, Any],
    lifecycle_before: dict[str, Any],
    lifecycle_action: str,
) -> dict[str, Any]:
    restored_status = _plugin_lifecycle_repair_status(current, meta, lifecycle_before)
    restored_promotion_status = _plugin_lifecycle_repair_promotion_status(
        meta,
        lifecycle_before,
        restored_status,
    )
    current_lifecycle_status = _safe_str(meta.get("lifecycle_status")).strip()
    current_promotion_status = _safe_str(meta.get("promotion_status")).strip()
    return {
        "contract": "plugin.lifecycle.repair_restore_dry_run_v1",
        "plugin_id": plugin_id,
        "lifecycle_action": lifecycle_action,
        "current": {
            "status": _safe_str(current.get("status")).strip(),
            "enabled": bool(current.get("enabled", False)),
            "promotion_status": current_promotion_status,
            "lifecycle_status": current_lifecycle_status,
            "lifecycle_receipt_id": _safe_str(meta.get("lifecycle_receipt_id")).strip(),
            "updated_ts": int(current.get("updated_ts") or 0),
        },
        "lifecycle_before": redact_governed_display_value(lifecycle_before),
        "target": {
            "status": restored_status,
            "enabled": False,
            "promotion_status": restored_promotion_status,
            "lifecycle_status": "active",
            "lifecycle_state": "active",
        },
        "metadata_clears": [
            "capability_lifecycle_status",
            "deprecation_status",
            "quarantine_status",
        ],
        "last_non_blocking_lifecycle_metadata": _plugin_lifecycle_last_non_blocking_metadata(
            current,
            meta,
            lifecycle_before,
            restored_status=restored_status,
            restored_promotion_status=restored_promotion_status,
        ),
        "writes": {
            "registry_metadata": True,
            "lifecycle_receipt": True,
            "promotion": False,
            "enablement": False,
            "execution": False,
            "memory": False,
        },
    }


def _plugin_lifecycle_repair_fingerprint(*, plan: dict[str, Any]) -> str:
    body = {
        "contract": "stage17_plugin_lifecycle_repair_dry_run_v1",
        "route": _PLUGIN_LIFECYCLE_REPAIR_ROUTE,
        "plan": redact_governed_display_value(plan),
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_plugin_lifecycle_receipts(*, plugin_id: str = "", limit: int = 20) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit or 20), 200))
    folder = _art_dir() / "lifecycle"
    folder_fs_path = _filesystem_path(folder)
    if not os.path.isdir(folder_fs_path):
        return []

    receipt_files: list[tuple[float, str]] = []
    try:
        for entry in os.scandir(folder_fs_path):
            if not entry.name.endswith(".json") or not entry.is_file():
                continue
            try:
                receipt_files.append((entry.stat().st_mtime, entry.path))
            except OSError:
                continue
    except OSError:
        return []

    safe_plugin_id = _safe_str(plugin_id).strip()
    items: list[dict[str, Any]] = []
    for _, path in sorted(receipt_files, key=lambda item: item[0], reverse=True)[:1000]:
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                payload = json.load(handle)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        if _safe_str(payload.get("kind")).strip() != "plugin.lifecycle.receipt":
            continue
        if safe_plugin_id and _safe_str(payload.get("plugin_id")).strip() != safe_plugin_id:
            continue
        items.append(payload)
        if len(items) >= safe_limit:
            break

    return sorted(
        items,
        key=lambda receipt: (
            int(receipt.get("recorded_ts") or 0),
            _safe_str(receipt.get("receipt_id")).strip(),
        ),
        reverse=True,
    )


def _plugin_lifecycle_receipt_summary(receipt: dict[str, Any]) -> dict[str, Any]:
    previous = receipt.get("previous") if isinstance(receipt.get("previous"), dict) else {}
    current = receipt.get("current") if isinstance(receipt.get("current"), dict) else {}
    governance = receipt.get("governance") if isinstance(receipt.get("governance"), dict) else {}
    action = _safe_str(receipt.get("action")).strip()
    summary = {
        "kind": _safe_str(receipt.get("kind")).strip(),
        "receipt_id": _safe_str(receipt.get("receipt_id")).strip(),
        "plugin_id": _safe_str(receipt.get("plugin_id")).strip(),
        "action": action,
        "repair_restore_action": action in {"repair", "restore"},
        "lifecycle_status": _safe_str(receipt.get("lifecycle_status")).strip(),
        "registry_status": _safe_str(receipt.get("registry_status")).strip(),
        "enabled": bool(receipt.get("enabled", False)),
        "recorded_ts": int(receipt.get("recorded_ts") or 0),
        "actor": _safe_str(receipt.get("actor")).strip(),
        "reason": _safe_str(receipt.get("reason")).strip(),
        "path": _safe_str(receipt.get("path")).strip(),
        "previous": {
            "status": _safe_str(previous.get("status")).strip(),
            "enabled": bool(previous.get("enabled", False)),
            "promotion_status": _safe_str(previous.get("promotion_status")).strip(),
            "lifecycle_status": _safe_str(previous.get("lifecycle_status")).strip(),
        },
        "current": {
            "status": _safe_str(current.get("status")).strip(),
            "enabled": bool(current.get("enabled", False)),
            "promotion_status": _safe_str(current.get("promotion_status")).strip(),
            "lifecycle_status": _safe_str(current.get("lifecycle_status")).strip(),
        },
        "governance": {
            "gate": _safe_str(governance.get("gate")).strip(),
            "scope": _safe_str(governance.get("scope")).strip(),
            "route": _safe_str(governance.get("route")).strip(),
            "promotion_authority": bool(governance.get("promotion_authority", False)),
            "execution_authority": bool(governance.get("execution_authority", False)),
            "approval_authority": bool(governance.get("approval_authority", False)),
            "memory_write": bool(governance.get("memory_write", False)),
        },
    }
    redacted = redact_governed_display_value(summary)
    return redacted if isinstance(redacted, dict) else {}


def _plugin_lifecycle_current_non_blocking_metadata(
    current: dict[str, Any],
    meta: dict[str, Any],
    lifecycle: dict[str, Any],
) -> dict[str, Any]:
    candidates: list[tuple[str, Any]] = [
        ("registry.meta.lifecycle_repair_restored_status", meta.get("lifecycle_repair_restored_status")),
        (
            "registry.meta.lifecycle_repair_restored_promotion_status",
            meta.get("lifecycle_repair_restored_promotion_status"),
        ),
        ("registry.meta.disabled_from_status", meta.get("disabled_from_status")),
        ("registry.meta.disabled_from_promotion_status", meta.get("disabled_from_promotion_status")),
    ]
    observed = lifecycle.get("observed_states") if isinstance(lifecycle.get("observed_states"), list) else []
    for item in observed:
        if not isinstance(item, dict):
            continue
        candidates.append((_safe_str(item.get("source")).strip(), item.get("raw")))

    selected = {"source": "", "raw": "", "status": ""}
    for source, value in candidates:
        normalized = _normalize_lifecycle_state(value)
        if normalized in _PLUGIN_LIFECYCLE_NON_BLOCKING_STATES:
            selected = {
                "source": source,
                "raw": _safe_str(value).strip(),
                "status": normalized,
            }
            break

    return {
        **selected,
        "safe_registry_status": _safe_str(current.get("status")).strip(),
        "safe_promotion_status": _safe_str(meta.get("promotion_status")).strip(),
        "target_lifecycle_status": _safe_str(lifecycle.get("status")).strip() or "active",
        "safe_enabled": bool(current.get("enabled", False)),
    }


def _plugin_lifecycle_repair_history_governance() -> dict[str, Any]:
    return {
        "plane": "P3_GOVERNANCE",
        "route": _PLUGIN_LIFECYCLE_REPAIR_HISTORY_ROUTE,
        "read_only": True,
        "source_receipt_contract": "plugin.lifecycle.receipt",
        "source_routes": ["/plugins/disable", _PLUGIN_LIFECYCLE_REPAIR_ROUTE],
        "apply_route": _PLUGIN_LIFECYCLE_REPAIR_ROUTE,
        "apply_requires_plugins_write_scope": True,
        "dry_run_fingerprint_does_not_authorize_without_plugins_write": True,
        "writes_registry_metadata": False,
        "writes_lifecycle_receipt": False,
        "writes_data": False,
        "does_not_promote_capabilities": True,
        "does_not_enable_capabilities": True,
        "does_not_execute_capabilities": True,
        "does_not_approve_proposals": True,
        "promotion_authority": False,
        "execution_authority": False,
        "approval_authority": False,
        "memory_write": False,
        "lifecycle_authority": False,
    }


def _plugin_lifecycle_repair_history_projection(
    *,
    plugin_id: str,
    current: dict[str, Any] | None,
    receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    receipt_history = [_plugin_lifecycle_receipt_summary(receipt) for receipt in receipts]
    repair_restore_history = [
        item for item in receipt_history if _safe_str(item.get("action")).strip() in {"repair", "restore"}
    ]
    latest_receipt = receipt_history[0] if receipt_history else {}
    latest_repair_restore = repair_restore_history[0] if repair_restore_history else {}
    governance = _plugin_lifecycle_repair_history_governance()
    if current is None:
        return {
            "ok": False,
            "applied": False,
            "kind": "plugin.lifecycle.repair_history_readback",
            "stage": "Stage 17 / Capability Economy",
            "status": "not_found",
            "error": "not_found",
            "id": plugin_id,
            "history_count": len(receipt_history),
            "repair_restore_history_count": len(repair_restore_history),
            "history": receipt_history,
            "repair_restore_history": repair_restore_history,
            "latest_receipt": latest_receipt,
            "latest_repair_restore": latest_repair_restore,
            "apply_readiness": {
                "safe_to_apply": False,
                "status": "blocked",
                "reason": "plugin_not_found",
                "apply_route": _PLUGIN_LIFECYCLE_REPAIR_ROUTE,
                "requires_dry_run_confirmation": True,
                "writes_registry_metadata_if_applied": False,
                "writes_lifecycle_receipt_if_applied": False,
                "promotion_authority": False,
                "execution_authority": False,
                "memory_write": False,
            },
            "governance": governance,
        }

    meta = dict(current.get("meta") or {}) if isinstance(current.get("meta"), dict) else {}
    lifecycle = _plugin_lifecycle_state(current, {})
    repair_required = bool(lifecycle.get("blocks_promotion")) or bool(lifecycle.get("blocks_execution"))
    repair_plan: dict[str, Any] = {}
    dry_run_confirmation: dict[str, Any] = {
        "required_for_apply": True,
        "fingerprint_contract": "stage17_plugin_lifecycle_repair_dry_run_v1",
        "apply_route": _PLUGIN_LIFECYCLE_REPAIR_ROUTE,
        "fingerprint_available_from_apply_dry_run": True,
    }
    last_non_blocking = _plugin_lifecycle_current_non_blocking_metadata(current, meta, lifecycle)
    safe_to_apply = False
    readiness_status = "not_required"
    readiness_reason = "lifecycle_repair_not_required"

    if repair_required:
        repair_plan = _plugin_lifecycle_repair_plan(
            plugin_id=plugin_id,
            current=current,
            meta=meta,
            lifecycle_before=lifecycle,
            lifecycle_action="restore",
        )
        target = repair_plan.get("target") if isinstance(repair_plan.get("target"), dict) else {}
        target_status = _normalize_lifecycle_state(target.get("status"))
        target_lifecycle = _normalize_lifecycle_state(target.get("lifecycle_status"))
        target_enabled = bool(target.get("enabled", False))
        safe_to_apply = (
            target_status in _PLUGIN_LIFECYCLE_NON_BLOCKING_STATES
            and target_lifecycle in _PLUGIN_LIFECYCLE_NON_BLOCKING_STATES
            and not target_enabled
        )
        readiness_status = "repair_available" if safe_to_apply else "blocked"
        readiness_reason = (
            "blocking_lifecycle_state_detected_with_non_enabled_restore_target"
            if safe_to_apply
            else "repair_plan_target_not_safe"
        )
        if isinstance(repair_plan.get("last_non_blocking_lifecycle_metadata"), dict):
            last_non_blocking = repair_plan["last_non_blocking_lifecycle_metadata"]

    return {
        "ok": True,
        "applied": False,
        "kind": "plugin.lifecycle.repair_history_readback",
        "stage": "Stage 17 / Capability Economy",
        "status": readiness_status,
        "id": plugin_id,
        "plugin": {
            "id": plugin_id,
            "status": _safe_str(current.get("status")).strip(),
            "enabled": bool(current.get("enabled", False)),
            "updated_ts": int(current.get("updated_ts") or 0),
        },
        "current_lifecycle": redact_governed_display_value(lifecycle),
        "last_non_blocking_lifecycle_metadata": redact_governed_display_value(last_non_blocking),
        "history_count": len(receipt_history),
        "repair_restore_history_count": len(repair_restore_history),
        "history": receipt_history,
        "repair_restore_history": repair_restore_history,
        "latest_receipt": latest_receipt,
        "latest_repair_restore": latest_repair_restore,
        "apply_readiness": {
            "safe_to_apply": safe_to_apply,
            "status": readiness_status,
            "reason": readiness_reason,
            "apply_route": _PLUGIN_LIFECYCLE_REPAIR_ROUTE,
            "recommended_lifecycle_action": "restore",
            "requires_dry_run_confirmation": True,
            "dry_run_fingerprint_available": False,
            "dry_run_confirmation": dry_run_confirmation,
            "planned_lifecycle_repair": repair_plan,
            "writes_registry_metadata_if_applied": safe_to_apply,
            "writes_lifecycle_receipt_if_applied": safe_to_apply,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "promotion_authority": False,
            "execution_authority": False,
            "memory_write": False,
        },
        "governance": governance,
    }


def _plugin_lifecycle_governance(
    *,
    gate: str = "plugin_lifecycle_disable",
    route: str = "/plugins/disable",
    lifecycle_action: str,
    lifecycle_status: str,
    writes_registry_metadata: bool,
    writes_lifecycle_receipt: bool,
    dry_run_required_before_apply: bool = False,
) -> dict[str, Any]:
    lifecycle_authority = bool(writes_registry_metadata or writes_lifecycle_receipt)
    return {
        "plane": "P3_GOVERNANCE",
        "gate": gate,
        "scope": _PLUGIN_WRITE_SCOPE,
        "route": route,
        "lifecycle_action": lifecycle_action,
        "lifecycle_status": lifecycle_status,
        "writes_registry_metadata": writes_registry_metadata,
        "writes_lifecycle_receipt": writes_lifecycle_receipt,
        "dry_run_required_before_apply": dry_run_required_before_apply,
        "does_not_promote_capabilities": True,
        "does_not_enable_capabilities": True,
        "does_not_execute_capabilities": True,
        "does_not_approve_proposals": True,
        "promotion_authority": False,
        "execution_authority": False,
        "approval_authority": False,
        "memory_write": False,
        "lifecycle_authority": lifecycle_authority,
    }


def _unsupported_plugin_lifecycle_action(
    *,
    plugin_id: str,
    requested_action: str,
    route: str = "/plugins/disable",
    gate: str = "plugin_lifecycle_disable",
    supported_actions: list[str] | None = None,
    dry_run_required_before_apply: bool = False,
) -> dict[str, object]:
    return {
        "ok": False,
        "applied": False,
        "id": plugin_id,
        "status": "blocked",
        "error": "unsupported_plugin_lifecycle_action",
        "requested_lifecycle_action": requested_action,
        "supported_lifecycle_actions": supported_actions or ["disable", "quarantine", "deprecate"],
        "governance": _plugin_lifecycle_governance(
            gate=gate,
            route=route,
            lifecycle_action=_safe_str(requested_action).strip(),
            lifecycle_status="unsupported",
            writes_registry_metadata=False,
            writes_lifecycle_receipt=False,
            dry_run_required_before_apply=dry_run_required_before_apply,
        ),
    }


def _write_plugin_lifecycle_receipt(
    *,
    plugin_id: str,
    receipt_id: str,
    receipt_path: Path,
    previous: dict[str, Any],
    current: dict[str, Any],
    payload: "PluginToggleIn",
    recorded_ts: int,
    lifecycle_action: str,
    lifecycle_status: str,
    catalog: dict[str, Any],
    route: str = "/plugins/disable",
    gate: str = "plugin_lifecycle_disable",
) -> dict[str, Any]:
    previous_meta = dict(previous.get("meta") or {}) if isinstance(previous.get("meta"), dict) else {}
    current_meta = dict(current.get("meta") or {}) if isinstance(current.get("meta"), dict) else {}
    receipt = {
        "kind": "plugin.lifecycle.receipt",
        "receipt_id": receipt_id,
        "plugin_id": plugin_id,
        "action": lifecycle_action,
        "lifecycle_status": lifecycle_status,
        "registry_status": _safe_str(current.get("status")).strip() or "disabled",
        "enabled": bool(current.get("enabled", False)),
        "previous": {
            "status": _safe_str(previous.get("status")).strip() or "unknown",
            "enabled": bool(previous.get("enabled", False)),
            "promotion_status": _safe_str(previous_meta.get("promotion_status")).strip(),
            "lifecycle_status": _safe_str(previous_meta.get("lifecycle_status")).strip(),
        },
        "current": {
            "status": _safe_str(current.get("status")).strip() or "disabled",
            "enabled": bool(current.get("enabled", False)),
            "promotion_status": _safe_str(current_meta.get("promotion_status")).strip(),
            "lifecycle_status": _safe_str(current_meta.get("lifecycle_status")).strip(),
        },
        "recorded_ts": recorded_ts,
        "actor": redact_governed_value(_safe_str(payload.actor).strip()),
        "reason": redact_governed_value(_safe_str(payload.reason).strip() or "requested"),
        "lifecycle_context": redact_governed_metadata(payload.meta),
        "catalog": {
            "path": _safe_str(catalog.get("path")).strip(),
            "total_plugins": int(catalog.get("total_plugins") or 0),
            "total_tools": int(catalog.get("total_tools") or 0),
        },
        "governance": _plugin_lifecycle_governance(
            gate=gate,
            route=route,
            lifecycle_action=lifecycle_action,
            lifecycle_status=lifecycle_status,
            writes_registry_metadata=True,
            writes_lifecycle_receipt=True,
        ),
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
        entry_quality = entry.get("quality") if isinstance(entry.get("quality"), dict) else {}
        metadata_quality = metadata.get("quality") if isinstance(metadata.get("quality"), dict) else {}
        tests = _unique_texts(
            [
                *_unique_texts(entry_quality.get("tests"), limit=50),
                *_unique_texts(metadata_quality.get("tests"), limit=50),
                *_unique_texts(metadata.get("tests"), limit=50),
                *_unique_texts(metadata.get("test_refs"), limit=50),
            ],
            limit=50,
        )
        docs = _unique_texts(
            [
                *_unique_texts(entry_quality.get("docs"), limit=50),
                *_unique_texts(metadata_quality.get("docs"), limit=50),
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
                "quality_test_references": tests,
                "quality_doc_references": docs,
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
        "writer_implemented": True,
        "writer_route": _CAPABILITY_PACK_ARTIFACT_RECONSTRUCTION_ROUTE,
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
            "stage17_capability_pack_artifact_reconstruction_apply" if required_count else ""
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
        return "stage17_capability_pack_artifact_reconstruction_apply"
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
    pack_capability_ids = _capability_ids_for_pack(entries, pack_id=pack_id, pack_version=pack_version)
    capability_ids = pack_capability_ids[:_CAPABILITY_PACK_QUALITY_EVIDENCE_CAPABILITY_PREVIEW_LIMIT]
    validation_candidates = (
        artifact_link_candidates.get("validation_receipts")
        if isinstance(artifact_link_candidates.get("validation_receipts"), dict)
        else {}
    )
    proposal_candidates = (
        artifact_link_candidates.get("proposals") if isinstance(artifact_link_candidates.get("proposals"), dict) else {}
    )
    validation_links = _artifact_links_for_capabilities(pack_capability_ids, validation_candidates)
    proposal_links = _artifact_links_for_capabilities(pack_capability_ids, proposal_candidates)
    capability_ids_truncated = len(pack_capability_ids) > len(capability_ids)
    validation_receipt_link_candidate = "validation_receipt_missing" in blockers and bool(
        validation_links["candidate_apply_supported"]
    )
    proposal_lineage_link_candidate = "proposal_id_missing" in blockers and bool(
        proposal_links["candidate_apply_supported"]
    )
    artifact_reconstruction_plan = _capability_pack_artifact_reconstruction_plan(
        capability_ids=pack_capability_ids,
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
                "links": list(validation_links["links"].values())[
                    :_CAPABILITY_PACK_QUALITY_EVIDENCE_LINK_PREVIEW_LIMIT
                ],
                "links_truncated": len(validation_links["links"])
                > _CAPABILITY_PACK_QUALITY_EVIDENCE_LINK_PREVIEW_LIMIT,
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
                "links": list(proposal_links["links"].values())[:_CAPABILITY_PACK_QUALITY_EVIDENCE_LINK_PREVIEW_LIMIT],
                "links_truncated": len(proposal_links["links"]) > _CAPABILITY_PACK_QUALITY_EVIDENCE_LINK_PREVIEW_LIMIT,
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
            "artifact_reconstruction_writer_not_implemented": False,
            "artifact_reconstruction_writer_route": _CAPABILITY_PACK_ARTIFACT_RECONSTRUCTION_ROUTE,
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
            "artifact_reconstruction_writer_implemented": True,
            "artifact_reconstruction_writer_route": _CAPABILITY_PACK_ARTIFACT_RECONSTRUCTION_ROUTE,
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


def _count_value(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0


def _capability_pack_operator_surface_status(
    *,
    pack_total: int,
    unpacked_entry_count: int,
    metadata_candidate_count: int,
    promotion_rule_remediation_queue_count: int,
    quality_remediation_queue_count: int,
    artifact_reconstruction_required_count: int,
    pending_operator_review_queue_count: int,
    promotion_discipline_blocked_pack_count: int,
    promotion_discipline_ready_pack_count: int,
) -> str:
    if pack_total <= 0:
        return "empty"
    if (
        unpacked_entry_count
        or metadata_candidate_count
        or promotion_rule_remediation_queue_count
        or quality_remediation_queue_count
        or artifact_reconstruction_required_count
    ):
        return "blocked"
    if pending_operator_review_queue_count:
        return "ready_for_operator_review"
    if promotion_discipline_blocked_pack_count:
        return "blocked"
    if promotion_discipline_ready_pack_count:
        return "ready_for_explicit_promotion"
    return "ready"


def _capability_pack_operator_surface_next_gap(
    *,
    migration_plan: dict[str, Any],
    readiness: dict[str, Any],
    promotion_remediation: dict[str, Any],
    quality: dict[str, Any],
    operator_review: dict[str, Any],
    promotion_discipline: dict[str, Any],
    unpacked_entry_count: int,
    metadata_candidate_count: int,
    promotion_rule_remediation_queue_count: int,
    quality_remediation_queue_count: int,
    artifact_reconstruction_required_count: int,
    pending_operator_review_queue_count: int,
    promotion_discipline_blocked_pack_count: int,
) -> str:
    if unpacked_entry_count or metadata_candidate_count:
        return (
            _safe_str(migration_plan.get("next_smallest_truthful_gap")).strip()
            or _safe_str(readiness.get("next_smallest_truthful_gap")).strip()
            or "stage17_versioned_capability_pack_metadata"
        )
    if promotion_rule_remediation_queue_count:
        return (
            _safe_str(promotion_remediation.get("next_smallest_truthful_gap")).strip()
            or "stage17_capability_pack_promotion_rule_backlog_execution"
        )
    if quality_remediation_queue_count or artifact_reconstruction_required_count:
        return (
            _safe_str(quality.get("next_smallest_truthful_gap")).strip()
            or "stage17_capability_pack_quality_evidence_remediation_apply"
        )
    if pending_operator_review_queue_count:
        return (
            _safe_str(operator_review.get("next_smallest_truthful_gap")).strip()
            or "stage17_capability_pack_review_decisions"
        )
    if promotion_discipline_blocked_pack_count:
        return (
            _safe_str(promotion_discipline.get("next_smallest_truthful_gap")).strip()
            or "stage17_capability_pack_promotion_discipline"
        )
    return (
        _safe_str(promotion_discipline.get("next_smallest_truthful_gap")).strip()
        or "stage17_capability_library_operator_surface"
    )


def _capability_pack_operator_surface_pack_preview(raw_packs: Any) -> dict[str, Any]:
    packs = raw_packs if isinstance(raw_packs, list) else []
    visible = packs[:_CAPABILITY_PACK_OPERATOR_SURFACE_PACK_PREVIEW_LIMIT]
    out: list[dict[str, Any]] = []
    for raw_pack in visible:
        if not isinstance(raw_pack, dict):
            continue
        item: dict[str, Any] = {
            "pack_id": _safe_str(raw_pack.get("pack_id")).strip(),
            "pack_version": _safe_str(raw_pack.get("pack_version")).strip(),
            "pack_name": _safe_str(raw_pack.get("pack_name")).strip(),
            "status": _safe_str(raw_pack.get("status")).strip(),
            "capability_count": _count_value(raw_pack.get("capability_count")),
            "staged_capability_count": _count_value(raw_pack.get("staged_capability_count")),
            "promoted_capability_count": _count_value(raw_pack.get("promoted_capability_count")),
            "blockers": _unique_texts(raw_pack.get("blockers"), limit=25),
        }
        for flag in (
            "operator_review_ready",
            "decision_required",
            "ready",
            "operator_review_approved",
            "promotion_rules_ready",
            "quality_evidence_ready",
            "proposal_lineage_ready",
            "validation_receipts_ready",
            "promotion_receipts_ready",
        ):
            if flag in raw_pack:
                item[flag] = _to_bool(raw_pack.get(flag))
        out.append(item)
    return {
        "packs": out,
        "packs_truncated": len(packs) > len(visible),
        "pack_preview_limit": _CAPABILITY_PACK_OPERATOR_SURFACE_PACK_PREVIEW_LIMIT,
    }


def _capability_pack_operator_surface_projection(
    *,
    entries: list[dict[str, Any]],
    migration_plan: dict[str, Any],
    readiness: dict[str, Any],
    promotion_rules: dict[str, Any],
    promotion_remediation: dict[str, Any],
    quality: dict[str, Any],
    operator_review: dict[str, Any],
    operator_review_decisions: list[dict[str, Any]],
    promotion_discipline: dict[str, Any],
    generated_plugin_sync_performed: bool,
) -> dict[str, Any]:
    pack_total = max(
        _count_value(readiness.get("pack_total")),
        _count_value(promotion_rules.get("pack_total")),
        _count_value(quality.get("pack_total")),
        _count_value(operator_review.get("pack_total")),
        _count_value(promotion_discipline.get("pack_total")),
    )
    unpacked_entry_count = max(
        _count_value(readiness.get("unpacked_entry_count")),
        _count_value(promotion_remediation.get("unpacked_entry_count")),
        _count_value(promotion_discipline.get("unpacked_entry_count")),
    )
    metadata_candidate_count = _count_value(migration_plan.get("candidate_total"))
    promotion_rule_remediation_queue_count = _count_value(promotion_remediation.get("remediation_queue_count"))
    quality_remediation_queue_count = _count_value(quality.get("remediation_queue_count"))
    artifact_reconstruction_required_count = _count_value(quality.get("artifact_reconstruction_required_count"))
    operator_review_queue_count = _count_value(operator_review.get("review_queue_count"))
    decision_keys = _capability_pack_operator_review_decision_keys(operator_review_decisions)
    decision_coverage = _capability_pack_operator_review_decision_coverage(operator_review_decisions)
    review_packs = operator_review.get("packs") if isinstance(operator_review.get("packs"), list) else []
    pending_operator_review_queue_count = sum(
        1
        for pack in review_packs
        if isinstance(pack, dict)
        and bool(pack.get("decision_required"))
        and not _capability_pack_operator_review_decision_covers(
            decision_coverage,
            pack_id=_safe_str(pack.get("pack_id")).strip(),
            pack_version=_safe_str(pack.get("pack_version")).strip(),
            capability_ids=_capability_pack_review_staged_capability_ids(
                entries,
                pack_id=_safe_str(pack.get("pack_id")).strip(),
                pack_version=_safe_str(pack.get("pack_version")).strip(),
            ),
        )
    )
    promotion_discipline_blocked_pack_count = _count_value(promotion_discipline.get("blocked_pack_count"))
    promotion_discipline_ready_pack_count = _count_value(promotion_discipline.get("ready_pack_count"))
    remediation_open_count = (
        unpacked_entry_count
        + metadata_candidate_count
        + promotion_rule_remediation_queue_count
        + quality_remediation_queue_count
        + artifact_reconstruction_required_count
    )
    status = _capability_pack_operator_surface_status(
        pack_total=pack_total,
        unpacked_entry_count=unpacked_entry_count,
        metadata_candidate_count=metadata_candidate_count,
        promotion_rule_remediation_queue_count=promotion_rule_remediation_queue_count,
        quality_remediation_queue_count=quality_remediation_queue_count,
        artifact_reconstruction_required_count=artifact_reconstruction_required_count,
        pending_operator_review_queue_count=pending_operator_review_queue_count,
        promotion_discipline_blocked_pack_count=promotion_discipline_blocked_pack_count,
        promotion_discipline_ready_pack_count=promotion_discipline_ready_pack_count,
    )
    next_gap = _capability_pack_operator_surface_next_gap(
        migration_plan=migration_plan,
        readiness=readiness,
        promotion_remediation=promotion_remediation,
        quality=quality,
        operator_review=operator_review,
        promotion_discipline=promotion_discipline,
        unpacked_entry_count=unpacked_entry_count,
        metadata_candidate_count=metadata_candidate_count,
        promotion_rule_remediation_queue_count=promotion_rule_remediation_queue_count,
        quality_remediation_queue_count=quality_remediation_queue_count,
        artifact_reconstruction_required_count=artifact_reconstruction_required_count,
        pending_operator_review_queue_count=pending_operator_review_queue_count,
        promotion_discipline_blocked_pack_count=promotion_discipline_blocked_pack_count,
    )
    operator_review_preview = _capability_pack_operator_surface_pack_preview(operator_review.get("packs"))
    promotion_discipline_preview = _capability_pack_operator_surface_pack_preview(promotion_discipline.get("packs"))
    return {
        "stage": "Stage 17 / Capability Economy",
        "status": status,
        "operator_surface_readback_ready": True,
        "pack_total": pack_total,
        "remediation_backlog": {
            "status": "blocked" if remediation_open_count else "clear",
            "open_count": remediation_open_count,
            "unpacked_entry_count": unpacked_entry_count,
            "metadata_receipt_review_candidate_count": metadata_candidate_count,
            "promotion_rule_remediation_queue_count": promotion_rule_remediation_queue_count,
            "quality_evidence_remediation_queue_count": quality_remediation_queue_count,
            "artifact_reconstruction_required_count": artifact_reconstruction_required_count,
            "source_quality_remediation_queue_count": _count_value(quality.get("source_remediation_queue_count")),
        },
        "readiness": {
            "status": _safe_str(readiness.get("status")).strip(),
            "pack_total": _count_value(readiness.get("pack_total")),
            "ready_pack_count": _count_value(readiness.get("ready_pack_count")),
            "blocked_pack_count": _count_value(readiness.get("blocked_pack_count")),
            "unpacked_entry_count": _count_value(readiness.get("unpacked_entry_count")),
            "next_smallest_truthful_gap": _safe_str(readiness.get("next_smallest_truthful_gap")).strip(),
        },
        "promotion_rules": {
            "status": _safe_str(promotion_rules.get("status")).strip(),
            "pack_total": _count_value(promotion_rules.get("pack_total")),
            "ready_pack_count": _count_value(promotion_rules.get("ready_pack_count")),
            "blocked_pack_count": _count_value(promotion_rules.get("blocked_pack_count")),
            "remediation_queue_count": promotion_rule_remediation_queue_count,
            "next_smallest_truthful_gap": _safe_str(promotion_remediation.get("next_smallest_truthful_gap")).strip(),
        },
        "quality_evidence": {
            "status": _safe_str(quality.get("status")).strip(),
            "pack_total": _count_value(quality.get("pack_total")),
            "remediation_queue_count": quality_remediation_queue_count,
            "artifact_reconstruction_required_count": artifact_reconstruction_required_count,
            "quality_reference_backfill_candidate_count": _count_value(
                quality.get("quality_reference_backfill_candidate_count")
            ),
            "validation_receipt_link_candidate_count": _count_value(
                quality.get("validation_receipt_link_candidate_count")
            ),
            "proposal_lineage_link_candidate_count": _count_value(quality.get("proposal_lineage_link_candidate_count")),
            "next_smallest_truthful_gap": _safe_str(quality.get("next_smallest_truthful_gap")).strip(),
        },
        "operator_review": {
            "status": _safe_str(operator_review.get("status")).strip(),
            "pack_total": _count_value(operator_review.get("pack_total")),
            "ready_pack_count": _count_value(operator_review.get("ready_pack_count")),
            "blocked_pack_count": _count_value(operator_review.get("blocked_pack_count")),
            "review_queue_count": operator_review_queue_count,
            "pending_review_queue_count": pending_operator_review_queue_count,
            "decision_recorded_pack_count": len(decision_keys),
            "decision_required_pack_count": _count_value(operator_review.get("decision_required_pack_count")),
            "decision_routes": operator_review.get("decision_routes")
            if isinstance(operator_review.get("decision_routes"), dict)
            else {},
            **operator_review_preview,
        },
        "promotion_discipline": {
            "status": _safe_str(promotion_discipline.get("status")).strip(),
            "pack_total": _count_value(promotion_discipline.get("pack_total")),
            "ready_pack_count": promotion_discipline_ready_pack_count,
            "blocked_pack_count": promotion_discipline_blocked_pack_count,
            "approved_pack_operator_review_count": _count_value(
                promotion_discipline.get("approved_pack_operator_review_count")
            ),
            "available_proposal_count": _count_value(promotion_discipline.get("available_proposal_count")),
            "available_validation_receipt_count": _count_value(
                promotion_discipline.get("available_validation_receipt_count")
            ),
            "available_promotion_receipt_count": _count_value(
                promotion_discipline.get("available_promotion_receipt_count")
            ),
            "next_smallest_truthful_gap": _safe_str(promotion_discipline.get("next_smallest_truthful_gap")).strip(),
            **promotion_discipline_preview,
        },
        "routes": {
            "metadata_receipt_review_route": "/plugins/capabilities/packs/metadata/receipts",
            "metadata_receipt_bulk_apply_route": "/plugins/capabilities/packs/metadata/receipts/bulk-from-plan",
            "promotion_rule_remediation_route": "/plugins/capabilities/packs/promotion/rules/remediation",
            "promotion_rule_remediation_apply_route": "/plugins/capabilities/packs/promotion/rules/remediation/apply",
            "quality_evidence_remediation_route": "/plugins/capabilities/packs/quality/evidence/remediation",
            "quality_evidence_apply_route": "/plugins/capabilities/packs/quality/evidence/remediation/apply",
            "quality_standard_remediation_apply_route": (
                "/plugins/capabilities/packs/quality/standards/remediation/apply"
            ),
            "artifact_reconstruction_route": _CAPABILITY_PACK_ARTIFACT_RECONSTRUCTION_ROUTE,
            "operator_review_route": "/plugins/capabilities/packs/operator/review",
            "operator_review_decision_route": "/plugins/capabilities/packs/operator/review/decisions",
            "operator_review_decision_readback_route": "/plugins/capabilities/packs/operator/review/decisions",
            "operator_review_bulk_decision_route": (
                "/plugins/capabilities/packs/operator/review/decisions/bulk-from-surface"
            ),
            "promotion_discipline_route": "/plugins/capabilities/packs/promotion/discipline",
            "promotion_receipts_route": "/plugins/capabilities/packs/promotion/receipts",
            "promotion_route_after_review": "/plugins/enable",
        },
        "requirements": {
            "single_operator_readback_for_stage17_pack_handoff": True,
            "composes_existing_stage17_readbacks": True,
            "remediation_backlog_must_be_clear_before_review_decisions": True,
            "operator_review_remains_explicit_governed_decision": True,
            "promotion_remains_separate_governed_action": True,
            "surface_status_is_derived_from_readbacks": True,
            "no_fake_progress_status": True,
        },
        "governance": {
            "read_only": True,
            "operator_facing": True,
            "generated_plugin_registry_sync_performed": generated_plugin_sync_performed,
            "catalog_readback_refreshed": True,
            "does_not_mutate_registry": not generated_plugin_sync_performed,
            "does_not_write_operator_review_decisions": True,
            "does_not_write_metadata_receipts": True,
            "does_not_write_validation_receipts": True,
            "does_not_write_promotion_receipts": True,
            "does_not_write_proposals": True,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "reads_existing_artifact_bodies_for_quality_link_candidates": True,
            "artifact_body_max_bytes": _PLUGIN_ARTIFACT_LINK_BODY_MAX_BYTES,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
        },
        "next_smallest_truthful_gap": next_gap,
    }


def _capability_library_operator_surface_projection(
    *,
    promotion_discipline: dict[str, Any],
    generated_plugin_sync_performed: bool,
) -> dict[str, Any]:
    sync_performed = bool(generated_plugin_sync_performed)
    raw_packs = promotion_discipline.get("packs") if isinstance(promotion_discipline.get("packs"), list) else []
    ready_packs = [
        pack
        for pack in raw_packs
        if isinstance(pack, dict) and bool(pack.get("ready")) and _safe_str(pack.get("status")).strip() == "ready"
    ]
    visible = ready_packs[:_CAPABILITY_LIBRARY_OPERATOR_SURFACE_PACK_PREVIEW_LIMIT]
    library_packs: list[dict[str, Any]] = []
    for pack in visible:
        item = {
            "pack_id": _safe_str(pack.get("pack_id")).strip(),
            "pack_version": _safe_str(pack.get("pack_version")).strip(),
            "pack_name": _safe_str(pack.get("pack_name")).strip(),
            "status": _safe_str(pack.get("status")).strip(),
            "ready": _to_bool(pack.get("ready")),
            "capability_count": _count_value(pack.get("capability_count")),
            "staged_capability_count": _count_value(pack.get("staged_capability_count")),
            "promoted_capability_count": _count_value(pack.get("promoted_capability_count")),
            "blockers": _unique_texts(pack.get("blockers"), limit=50),
        }
        for flag in (
            "operator_review_approved",
            "promotion_rules_ready",
            "pack_governance_ready",
            "quality_evidence_ready",
            "validation_receipts_ready",
            "proposal_lineage_ready",
            "promotion_receipts_ready",
            "lifecycle_mixed",
        ):
            if flag in pack:
                item[flag] = _to_bool(pack.get(flag))
        library_packs.append(item)

    pack_total = _count_value(promotion_discipline.get("pack_total"))
    ready_pack_count = _count_value(promotion_discipline.get("ready_pack_count"))
    blocked_pack_count = _count_value(promotion_discipline.get("blocked_pack_count"))
    status = "ready_for_explicit_promotion" if ready_pack_count and not blocked_pack_count else "blocked"
    if not pack_total:
        status = "no_capability_packs"
    next_gap = (
        "stage17_capability_library_explicit_promotion"
        if status == "ready_for_explicit_promotion"
        else _safe_str(promotion_discipline.get("next_smallest_truthful_gap")).strip()
    )
    return {
        "stage": "Stage 17 / Capability Economy",
        "status": status,
        "library_operator_surface_ready": status == "ready_for_explicit_promotion",
        "pack_total": pack_total,
        "ready_pack_count": ready_pack_count,
        "blocked_pack_count": blocked_pack_count,
        "approved_pack_operator_review_count": _count_value(
            promotion_discipline.get("approved_pack_operator_review_count")
        ),
        "available_proposal_count": _count_value(promotion_discipline.get("available_proposal_count")),
        "available_validation_receipt_count": _count_value(
            promotion_discipline.get("available_validation_receipt_count")
        ),
        "available_promotion_receipt_count": _count_value(
            promotion_discipline.get("available_promotion_receipt_count")
        ),
        "ready_staged_capability_count": sum(_count_value(pack.get("staged_capability_count")) for pack in ready_packs),
        "ready_promoted_capability_count": sum(
            _count_value(pack.get("promoted_capability_count")) for pack in ready_packs
        ),
        "packs": library_packs,
        "packs_truncated": len(ready_packs) > len(library_packs),
        "pack_preview_limit": _CAPABILITY_LIBRARY_OPERATOR_SURFACE_PACK_PREVIEW_LIMIT,
        "routes": {
            "source_promotion_discipline_route": "/plugins/capabilities/packs/promotion/discipline",
            "operator_surface_route": "/plugins/capabilities/packs/operator/surface",
            "proposal_review_route": "/forge/proposals/decision",
            "promotion_route": "/plugins/enable",
            "promotion_receipts_route": "/plugins/capabilities/packs/promotion/receipts",
        },
        "requirements": {
            "derived_from_promotion_discipline": True,
            "lists_only_ready_packs": True,
            "ready_pack_requires_current_operator_review_coverage": True,
            "ready_pack_requires_quality_and_lineage_evidence": True,
            "ready_pack_requires_explicit_promotion_rules": True,
            "explicit_promotion_remains_separate": True,
            "proposal_approval_remains_separate": True,
            "surface_status_is_derived_from_readbacks": True,
            "no_fake_progress_status": True,
        },
        "governance": {
            "read_only": True,
            "operator_facing": True,
            "generated_plugin_registry_sync_performed": sync_performed,
            "does_not_mutate_registry": not sync_performed,
            "does_not_write_receipts": True,
            "does_not_write_metadata_receipts": True,
            "does_not_write_validation_receipts": True,
            "does_not_write_promotion_receipts": True,
            "does_not_write_proposals": True,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
        },
        "next_smallest_truthful_gap": next_gap,
    }


def _capability_library_explicit_promotion_plan_projection(
    *,
    registry: dict[str, Any],
    entries: list[dict[str, Any]],
    promotion_discipline: dict[str, Any],
    generated_plugin_sync_performed: bool,
) -> dict[str, Any]:
    sync_performed = bool(generated_plugin_sync_performed)
    raw_packs = promotion_discipline.get("packs") if isinstance(promotion_discipline.get("packs"), list) else []
    ready_packs = [
        pack
        for pack in raw_packs
        if isinstance(pack, dict) and bool(pack.get("ready")) and _safe_str(pack.get("status")).strip() == "ready"
    ]
    planned_packs: list[dict[str, Any]] = []
    preview_remaining = _CAPABILITY_LIBRARY_PROMOTION_PLAN_CAPABILITY_PREVIEW_LIMIT
    candidate_pack_count = 0
    candidate_capability_count = 0
    promotable_capability_count = 0
    blocked_capability_count = 0
    missing_requirement_counts: dict[str, int] = {}

    for pack in ready_packs:
        pack_id = _safe_str(pack.get("pack_id")).strip()
        pack_version = _safe_str(pack.get("pack_version")).strip()
        pack_entries = _entries_for_capability_pack(entries, pack_id=pack_id, pack_version=pack_version)
        staged_ids = _unique_texts(
            [
                _safe_str(entry.get("capability")).strip()
                for entry in pack_entries
                if _safe_str(entry.get("status")).strip() == "staged"
            ],
            limit=10000,
        )
        if not staged_ids:
            continue
        candidate_pack_count += 1
        include_pack_preview = len(planned_packs) < _CAPABILITY_LIBRARY_OPERATOR_SURFACE_PACK_PREVIEW_LIMIT
        pack_capabilities: list[dict[str, Any]] = []
        pack_promotable_count = 0
        pack_blocked_count = 0
        for capability_id in staged_ids:
            candidate_capability_count += 1
            plugin = _read_plugin(registry, capability_id)
            if plugin is None:
                readiness = {
                    "ready": False,
                    "missing_requirements": ["plugin_record"],
                    "requirements": {"plugin_record": False},
                    "evidence": {},
                }
            else:
                readiness = _plugin_promotion_readiness(
                    capability_id,
                    plugin,
                    PluginToggleIn(id=capability_id, reason="capability_library_explicit_promotion_plan"),
                )
            missing = _unique_texts(readiness.get("missing_requirements"), limit=25)
            ready = bool(readiness.get("ready")) and not missing
            if ready:
                promotable_capability_count += 1
                pack_promotable_count += 1
            else:
                blocked_capability_count += 1
                pack_blocked_count += 1
                for requirement in missing:
                    missing_requirement_counts[requirement] = missing_requirement_counts.get(requirement, 0) + 1
            if include_pack_preview and preview_remaining > 0:
                evidence = readiness.get("evidence") if isinstance(readiness.get("evidence"), dict) else {}
                compatibility = evidence.get("compatibility") if isinstance(evidence.get("compatibility"), dict) else {}
                lifecycle = evidence.get("lifecycle") if isinstance(evidence.get("lifecycle"), dict) else {}
                pack_capabilities.append(
                    {
                        "capability": capability_id,
                        "status": _safe_str(plugin.get("status") if isinstance(plugin, dict) else "missing").strip(),
                        "enabled": bool(plugin.get("enabled")) if isinstance(plugin, dict) else False,
                        "promotion_ready": ready,
                        "missing_requirements": missing,
                        "proposal_id": _safe_str(evidence.get("proposal_id")).strip(),
                        "proposal_review_status": _safe_str(evidence.get("proposal_review_status")).strip(),
                        "proposal_review_receipt_id": _safe_str(evidence.get("proposal_review_receipt_id")).strip(),
                        "validation_receipt_id": _safe_str(evidence.get("validation_receipt_id")).strip(),
                        "compatibility": compatibility,
                        "lifecycle": lifecycle,
                        "pack_operator_review_required": _to_bool(evidence.get("pack_operator_review_required")),
                        "pack_operator_review_status": _safe_str(evidence.get("pack_operator_review_status")).strip(),
                        "pack_operator_review_receipt_id": _safe_str(
                            evidence.get("pack_operator_review_receipt_id")
                        ).strip(),
                        "promotion_route": "/plugins/enable",
                        "promotion_would_write_receipt": True,
                        "promotion_would_enable_capability": True,
                    }
                )
                preview_remaining -= 1
        if include_pack_preview:
            planned_packs.append(
                {
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "pack_name": _safe_str(pack.get("pack_name")).strip(),
                    "staged_capability_count": len(staged_ids),
                    "promotable_capability_count": pack_promotable_count,
                    "blocked_capability_count": pack_blocked_count,
                    "capabilities": pack_capabilities,
                    "capabilities_truncated": len(pack_capabilities) < len(staged_ids),
                }
            )

    discipline_blocked_pack_count = _count_value(promotion_discipline.get("blocked_pack_count"))
    if discipline_blocked_pack_count:
        status = "blocked"
        next_gap = (
            _safe_str(promotion_discipline.get("next_smallest_truthful_gap")).strip()
            or "stage17_capability_pack_promotion_rules"
        )
    elif not candidate_capability_count:
        status = "no_staged_promotion_candidates"
        next_gap = "stage17_capability_library_promotion_receipts"
    elif blocked_capability_count:
        status = "blocked"
        missing_before_review = {
            requirement: count
            for requirement, count in missing_requirement_counts.items()
            if requirement != "proposal_review"
        }
        next_gap = (
            "stage17_pack_lifecycle_quarantine_deprecation_contract"
            if "lifecycle_state" in missing_requirement_counts
            else "stage17_capability_library_promotion_readiness"
            if missing_before_review
            else "stage17_capability_library_proposal_review"
        )
    else:
        status = "ready_for_explicit_promotion"
        next_gap = "stage17_capability_library_explicit_promotion_apply"

    return {
        "stage": "Stage 17 / Capability Economy",
        "status": status,
        "promotion_plan_ready": status == "ready_for_explicit_promotion",
        "pack_total": _count_value(promotion_discipline.get("pack_total")),
        "ready_pack_count": _count_value(promotion_discipline.get("ready_pack_count")),
        "blocked_pack_count": discipline_blocked_pack_count,
        "candidate_pack_count": candidate_pack_count,
        "candidate_capability_count": candidate_capability_count,
        "promotable_capability_count": promotable_capability_count,
        "blocked_capability_count": blocked_capability_count,
        "missing_requirement_counts": missing_requirement_counts,
        "packs": planned_packs,
        "packs_truncated": candidate_pack_count > len(planned_packs),
        "capability_preview_limit": _CAPABILITY_LIBRARY_PROMOTION_PLAN_CAPABILITY_PREVIEW_LIMIT,
        "routes": {
            "library_operator_surface_route": "/plugins/capabilities/library/operator/surface",
            "source_promotion_discipline_route": "/plugins/capabilities/packs/promotion/discipline",
            "proposal_evidence_plan_route": "/plugins/capabilities/library/proposal-evidence/plan",
            "proposal_review_route": "/forge/proposals/decision",
            "promotion_route": "/plugins/enable",
            "promotion_receipts_route": "/plugins/capabilities/packs/promotion/receipts",
            "promotion_apply_route": _CAPABILITY_LIBRARY_EXPLICIT_PROMOTION_APPLY_ROUTE,
        },
        "requirements": {
            "derived_from_capability_library_operator_surface": True,
            "uses_existing_plugin_promotion_readiness": True,
            "proposal_review_required_before_promotion": True,
            "pack_operator_review_required_when_declared": True,
            "core_compatibility_required_before_promotion": True,
            "quarantine_deprecation_blocks_promotion": True,
            "unknown_explicit_lifecycle_state_blocks_promotion": True,
            "promotion_requires_plugins_write_scope": True,
            "promotion_writes_receipts_only_through_enable_route": True,
            "bulk_promotion_apply_requires_dry_run_fingerprint": True,
            "explicit_operator_action_required": True,
            "no_auto_promotion": True,
        },
        "governance": {
            "read_only": True,
            "operator_facing": True,
            "generated_plugin_registry_sync_performed": sync_performed,
            "does_not_mutate_registry": not sync_performed,
            "does_not_write_receipts": True,
            "does_not_write_promotion_receipts": True,
            "does_not_write_proposals": True,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
        },
        "next_smallest_truthful_gap": next_gap,
    }


def _capability_library_explicit_promotion_candidates(
    *,
    registry: dict[str, Any],
    entries: list[dict[str, Any]],
    promotion_discipline: dict[str, Any],
    selected_pack_ids: set[str],
    selected_capability_ids: set[str],
) -> list[dict[str, Any]]:
    raw_packs = promotion_discipline.get("packs") if isinstance(promotion_discipline.get("packs"), list) else []
    candidates: list[dict[str, Any]] = []
    for pack in raw_packs:
        if not isinstance(pack, dict):
            continue
        if not bool(pack.get("ready")) or _safe_str(pack.get("status")).strip() != "ready":
            continue
        pack_id = _safe_str(pack.get("pack_id")).strip()
        pack_version = _safe_str(pack.get("pack_version")).strip()
        if selected_pack_ids and pack_id not in selected_pack_ids:
            continue
        pack_entries = _entries_for_capability_pack(entries, pack_id=pack_id, pack_version=pack_version)
        staged_ids = _unique_texts(
            [
                _safe_str(entry.get("capability")).strip()
                for entry in pack_entries
                if _safe_str(entry.get("status")).strip() == "staged"
            ],
            limit=10000,
        )
        capabilities: list[dict[str, Any]] = []
        for capability_id in staged_ids:
            if selected_capability_ids and capability_id not in selected_capability_ids:
                continue
            plugin = _read_plugin(registry, capability_id)
            if plugin is None:
                continue
            readiness = _plugin_promotion_readiness(
                capability_id,
                plugin,
                PluginToggleIn(id=capability_id, reason="capability_library_explicit_promotion_apply"),
            )
            if not readiness["ready"]:
                continue
            evidence = readiness.get("evidence") if isinstance(readiness.get("evidence"), dict) else {}
            compatibility = evidence.get("compatibility") if isinstance(evidence.get("compatibility"), dict) else {}
            lifecycle = evidence.get("lifecycle") if isinstance(evidence.get("lifecycle"), dict) else {}
            capabilities.append(
                {
                    "capability": capability_id,
                    "proposal_id": _safe_str(evidence.get("proposal_id")).strip(),
                    "proposal_review_status": _safe_str(evidence.get("proposal_review_status")).strip(),
                    "proposal_review_receipt_id": _safe_str(evidence.get("proposal_review_receipt_id")).strip(),
                    "pack_operator_review_required": _to_bool(evidence.get("pack_operator_review_required")),
                    "pack_operator_review_status": _safe_str(evidence.get("pack_operator_review_status")).strip(),
                    "pack_operator_review_receipt_id": _safe_str(
                        evidence.get("pack_operator_review_receipt_id")
                    ).strip(),
                    "compatibility": compatibility,
                    "lifecycle": lifecycle,
                    "promotion_route": "/plugins/enable",
                    "promotion_would_write_receipt": True,
                    "promotion_would_enable_capability": True,
                }
            )
        if capabilities:
            candidates.append(
                {
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "pack_name": _safe_str(pack.get("pack_name")).strip(),
                    "capabilities": capabilities,
                }
            )
    return candidates


def _capability_library_explicit_promotion_fingerprint(*, planned: list[dict[str, Any]]) -> str:
    canonical_packs: list[dict[str, Any]] = []
    for pack in planned:
        raw_capabilities = pack.get("capabilities") if isinstance(pack.get("capabilities"), list) else []
        capabilities = [
            {
                "capability": _safe_str(capability.get("capability")).strip(),
                "proposal_id": _safe_str(capability.get("proposal_id")).strip(),
            }
            for capability in raw_capabilities
            if isinstance(capability, dict)
        ]
        capabilities.sort(key=lambda item: (item["capability"], item["proposal_id"]))
        canonical_packs.append(
            {
                "pack_id": _safe_str(pack.get("pack_id")).strip(),
                "pack_version": _safe_str(pack.get("pack_version")).strip(),
                "capabilities": capabilities,
            }
        )
    canonical_packs.sort(key=lambda item: (item["pack_id"], item["pack_version"]))
    body = {
        "contract": "stage17_capability_library_explicit_promotion_dry_run_v1",
        "route": _CAPABILITY_LIBRARY_EXPLICIT_PROMOTION_APPLY_ROUTE,
        "planned": canonical_packs,
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _prepare_capability_library_explicit_promotion_plan(
    *,
    payload: "CapabilityLibraryExplicitPromotionApplyIn",
) -> dict[str, Any]:
    safe_max_pack_count = max(1, min(int(payload.max_pack_count or 10), 100))
    safe_max_total_capability_count = max(1, min(int(payload.max_total_capability_count or 1000), 10000))
    safe_max_capability_count_per_pack = max(1, min(int(payload.max_capability_count_per_pack or 500), 1000))
    try:
        selected_pack_ids = {_validate_plugin_id(raw_id) for raw_id in _unique_texts(payload.pack_ids, limit=100)}
        selected_capability_ids = {
            _validate_plugin_id(raw_id) for raw_id in _unique_texts(payload.capability_ids, limit=10000)
        }
    except Exception:
        return {"ok": False, "status": "blocked", "error": "invalid_selector_id"}

    registry = _load_registry()
    synced = _sync_generated_plugins(registry)
    catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
    runtime_catalog = _read_runtime_catalog_payload(catalog)
    marketplace = marketplace_from_plugin_catalog(runtime_catalog)
    entries = list(marketplace.catalog())
    available_proposals = _available_capability_pack_proposals()
    available_validation_receipts = _available_capability_pack_validation_receipts()
    available_promotion_receipts = _available_capability_pack_promotion_receipts()
    promotion_discipline = analyze_capability_pack_promotion_discipline(
        entries,
        available_proposal_ids=available_proposals["ids"],
        available_validation_receipt_ids=available_validation_receipts["ids"],
        available_promotion_receipt_ids=available_promotion_receipts["ids"],
        operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
    )
    before = _capability_library_explicit_promotion_plan_projection(
        registry=registry,
        entries=entries,
        promotion_discipline=promotion_discipline,
        generated_plugin_sync_performed=bool(synced),
    )
    candidates = _capability_library_explicit_promotion_candidates(
        registry=registry,
        entries=entries,
        promotion_discipline=promotion_discipline,
        selected_pack_ids=selected_pack_ids,
        selected_capability_ids=selected_capability_ids,
    )
    if not candidates:
        return {
            "ok": True,
            "status": "no_candidates",
            "planned_pack_count": 0,
            "planned_capability_count": 0,
            "before": before,
            "registry": registry,
            "catalog": catalog,
            "generated_plugin_registry_sync_performed": bool(synced),
        }
    if len(candidates) > safe_max_pack_count:
        return {
            "ok": False,
            "status": "blocked",
            "error": "capability_library_promotion_pack_limit_exceeded",
            "candidate_total": len(candidates),
            "limit": safe_max_pack_count,
            "before": before,
            "generated_plugin_registry_sync_performed": bool(synced),
        }

    planned: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    total_capability_count = 0
    for pack in candidates:
        raw_capabilities = pack.get("capabilities") if isinstance(pack.get("capabilities"), list) else []
        capabilities = [capability for capability in raw_capabilities if isinstance(capability, dict)]
        capability_count = len(capabilities)
        if capability_count > safe_max_capability_count_per_pack:
            skipped.append(
                {
                    "pack_id": _safe_str(pack.get("pack_id")).strip(),
                    "pack_version": _safe_str(pack.get("pack_version")).strip(),
                    "error": "candidate_capability_limit_exceeded",
                    "capability_count": capability_count,
                    "limit": safe_max_capability_count_per_pack,
                }
            )
            continue
        total_capability_count += capability_count
        planned.append(
            {
                "pack_id": _safe_str(pack.get("pack_id")).strip(),
                "pack_version": _safe_str(pack.get("pack_version")).strip(),
                "pack_name": _safe_str(pack.get("pack_name")).strip(),
                "capability_count": capability_count,
                "capabilities": capabilities,
                "writes_promotion_receipts": not payload.dry_run,
                "promotes_capabilities": not payload.dry_run,
                "enables_capabilities": not payload.dry_run,
            }
        )
    if total_capability_count > safe_max_total_capability_count:
        return {
            "ok": False,
            "status": "blocked",
            "error": "capability_library_promotion_total_capability_limit_exceeded",
            "capability_count": total_capability_count,
            "limit": safe_max_total_capability_count,
            "before": before,
            "generated_plugin_registry_sync_performed": bool(synced),
        }
    if not planned:
        return {
            "ok": True,
            "status": "no_supported_promotion_candidates",
            "planned_pack_count": 0,
            "planned_capability_count": 0,
            "skipped": skipped,
            "before": before,
            "registry": registry,
            "catalog": catalog,
            "generated_plugin_registry_sync_performed": bool(synced),
        }
    return {
        "ok": True,
        "status": "planned",
        "planned": planned,
        "skipped": skipped,
        "planned_pack_count": len(planned),
        "planned_capability_count": total_capability_count,
        "dry_run_fingerprint": _capability_library_explicit_promotion_fingerprint(planned=planned),
        "before": before,
        "registry": registry,
        "catalog": catalog,
        "generated_plugin_registry_sync_performed": bool(synced),
    }


def _capability_library_explicit_promotion_apply_governance(
    *,
    route_path: str,
    writes_registry_metadata: bool,
    writes_promotion_receipts: bool,
    generated_plugin_registry_sync_performed: bool,
) -> dict[str, object]:
    promotion_authority = bool(writes_registry_metadata or writes_promotion_receipts)
    return {
        "scope": _PLUGIN_WRITE_SCOPE,
        "route": route_path,
        "lifecycle_operation": "explicit_promotion_apply",
        "policy_gate": _PLUGIN_WRITE_SCOPE,
        "receipt_contract": "plugin.promotion.receipt",
        "uses_existing_plugin_promotion_readiness": True,
        "uses_plugin_promotion_receipt_schema": True,
        "writes_registry_metadata": writes_registry_metadata,
        "writes_promotion_receipts": writes_promotion_receipts,
        "generated_plugin_registry_sync_performed": generated_plugin_registry_sync_performed,
        "does_not_mutate_registry": not (
            generated_plugin_registry_sync_performed or writes_registry_metadata or writes_promotion_receipts
        ),
        "dry_run_required_before_apply": True,
        "does_not_approve_proposals": True,
        "does_not_promote_capabilities": not promotion_authority,
        "does_not_enable_capabilities": not promotion_authority,
        "does_not_execute_capabilities": True,
        "promotion_authority": promotion_authority,
        "execution_authority": False,
        "approval_authority": False,
        "memory_write": False,
    }


def _capability_library_proposal_evidence_plan_projection(
    *,
    registry: dict[str, Any],
    entries: list[dict[str, Any]],
    promotion_discipline: dict[str, Any],
    generated_plugin_sync_performed: bool,
) -> dict[str, Any]:
    sync_performed = bool(generated_plugin_sync_performed)
    raw_packs = promotion_discipline.get("packs") if isinstance(promotion_discipline.get("packs"), list) else []
    ready_packs = [
        pack
        for pack in raw_packs
        if isinstance(pack, dict) and bool(pack.get("ready")) and _safe_str(pack.get("status")).strip() == "ready"
    ]
    planned_packs: list[dict[str, Any]] = []
    preview_remaining = _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_PLAN_PREVIEW_LIMIT
    candidate_pack_count = 0
    candidate_capability_count = 0
    proposal_evidence_missing_count = 0
    proposal_evidence_ready_count = 0
    proposal_id_missing_count = 0
    proposal_review_missing_count = 0
    blocked_before_evidence_count = 0
    missing_requirement_counts: dict[str, int] = {}
    unique_proposal_ids: set[str] = set()
    missing_proposal_evidence_ids: set[str] = set()
    evidence_ready_proposal_ids: set[str] = set()

    for pack in ready_packs:
        pack_id = _safe_str(pack.get("pack_id")).strip()
        pack_version = _safe_str(pack.get("pack_version")).strip()
        pack_entries = _entries_for_capability_pack(entries, pack_id=pack_id, pack_version=pack_version)
        staged_ids = _unique_texts(
            [
                _safe_str(entry.get("capability")).strip()
                for entry in pack_entries
                if _safe_str(entry.get("status")).strip() == "staged"
            ],
            limit=10000,
        )
        if not staged_ids:
            continue

        candidate_pack_count += 1
        include_pack_preview = len(planned_packs) < _CAPABILITY_LIBRARY_OPERATOR_SURFACE_PACK_PREVIEW_LIMIT
        pack_missing_count = 0
        pack_ready_count = 0
        pack_blocked_before_evidence_count = 0
        pack_capabilities: list[dict[str, Any]] = []

        for capability_id in staged_ids:
            candidate_capability_count += 1
            plugin = _read_plugin(registry, capability_id)
            if plugin is None:
                readiness = {
                    "ready": False,
                    "missing_requirements": ["plugin_record"],
                    "requirements": {"plugin_record": False},
                    "evidence": {},
                }
            else:
                readiness = _plugin_promotion_readiness(
                    capability_id,
                    plugin,
                    PluginToggleIn(id=capability_id, reason="capability_library_proposal_evidence_plan"),
                )

            missing = _unique_texts(readiness.get("missing_requirements"), limit=25)
            evidence = readiness.get("evidence") if isinstance(readiness.get("evidence"), dict) else {}
            proposal_id = _safe_str(evidence.get("proposal_id")).strip()
            proposal_evidence = _unique_texts(evidence.get("proposal_evidence"), limit=50)
            artifact_evidence = _plugin_proposal_friction_evidence(proposal_id)
            proposal_evidence_missing = "proposal_evidence" in missing
            proposal_evidence_ready = not proposal_evidence_missing and _has_readiness_value(proposal_evidence)
            blockers_before_evidence = [
                requirement for requirement in missing if requirement not in {"proposal_evidence", "proposal_review"}
            ]
            if proposal_id:
                unique_proposal_ids.add(proposal_id)
            else:
                proposal_id_missing_count += 1
            for requirement in missing:
                missing_requirement_counts[requirement] = missing_requirement_counts.get(requirement, 0) + 1
            if "proposal_review" in missing:
                proposal_review_missing_count += 1
            if blockers_before_evidence:
                blocked_before_evidence_count += 1
                pack_blocked_before_evidence_count += 1
            if proposal_evidence_missing:
                proposal_evidence_missing_count += 1
                pack_missing_count += 1
                if proposal_id:
                    missing_proposal_evidence_ids.add(proposal_id)
            elif proposal_evidence_ready:
                proposal_evidence_ready_count += 1
                pack_ready_count += 1
                if proposal_id:
                    evidence_ready_proposal_ids.add(proposal_id)

            if proposal_evidence_ready and artifact_evidence and proposal_evidence == artifact_evidence:
                evidence_source = "linked_proposal_artifact"
            elif proposal_evidence_ready:
                evidence_source = "plugin_metadata"
            elif proposal_id:
                evidence_source = "missing_in_plugin_metadata_and_linked_proposal_artifact"
            else:
                evidence_source = "proposal_id_missing"

            include_capability_preview = (
                include_pack_preview
                and preview_remaining > 0
                and (proposal_evidence_missing or bool(blockers_before_evidence))
            )
            if include_capability_preview:
                pack_capabilities.append(
                    {
                        "capability": capability_id,
                        "status": _safe_str(plugin.get("status") if isinstance(plugin, dict) else "missing").strip(),
                        "proposal_id": proposal_id,
                        "proposal_review_status": _safe_str(evidence.get("proposal_review_status")).strip(),
                        "proposal_review_receipt_id": _safe_str(evidence.get("proposal_review_receipt_id")).strip(),
                        "proposal_evidence_ready": proposal_evidence_ready,
                        "proposal_evidence_missing": proposal_evidence_missing,
                        "proposal_evidence": proposal_evidence,
                        "linked_proposal_artifact_evidence": artifact_evidence,
                        "evidence_source": evidence_source,
                        "missing_requirements": missing,
                        "blockers_before_evidence": blockers_before_evidence,
                        "proposal_review_would_write_receipt": True,
                        "proposal_review_would_promote_capability": False,
                        "proposal_review_would_enable_capability": False,
                    }
                )
                preview_remaining -= 1

        if include_pack_preview:
            planned_packs.append(
                {
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "pack_name": _safe_str(pack.get("pack_name")).strip(),
                    "staged_capability_count": len(staged_ids),
                    "proposal_evidence_missing_count": pack_missing_count,
                    "proposal_evidence_ready_count": pack_ready_count,
                    "blocked_before_evidence_count": pack_blocked_before_evidence_count,
                    "capabilities": pack_capabilities,
                    "capabilities_truncated": len(pack_capabilities)
                    < (pack_missing_count + pack_blocked_before_evidence_count),
                }
            )

    discipline_blocked_pack_count = _count_value(promotion_discipline.get("blocked_pack_count"))
    if discipline_blocked_pack_count:
        status = "blocked"
        next_gap = (
            _safe_str(promotion_discipline.get("next_smallest_truthful_gap")).strip()
            or "stage17_capability_pack_promotion_rules"
        )
    elif not candidate_capability_count:
        status = "no_staged_promotion_candidates"
        next_gap = "stage17_capability_library_promotion_receipts"
    elif proposal_evidence_missing_count or blocked_before_evidence_count:
        status = "blocked"
        next_gap = "stage17_capability_library_promotion_readiness"
    elif proposal_review_missing_count:
        status = "proposal_evidence_complete"
        next_gap = "stage17_capability_library_proposal_review_apply"
    else:
        status = "proposal_evidence_complete"
        next_gap = "stage17_capability_library_explicit_promotion_apply"

    return {
        "stage": "Stage 17 / Capability Economy",
        "status": status,
        **_stage17_projection_evidence(
            projection_scope="full_library",
            global_counts_included=True,
            generated_plugin_sync_performed=sync_performed,
        ),
        "proposal_evidence_plan_ready": bool(proposal_evidence_missing_count or blocked_before_evidence_count)
        and not discipline_blocked_pack_count,
        "pack_total": _count_value(promotion_discipline.get("pack_total")),
        "ready_pack_count": _count_value(promotion_discipline.get("ready_pack_count")),
        "blocked_pack_count": discipline_blocked_pack_count,
        "candidate_pack_count": candidate_pack_count,
        "candidate_capability_count": candidate_capability_count,
        "unique_proposal_count": len(unique_proposal_ids),
        "proposal_evidence_missing_count": proposal_evidence_missing_count,
        "proposal_evidence_ready_count": proposal_evidence_ready_count,
        "missing_proposal_evidence_count": len(missing_proposal_evidence_ids),
        "evidence_ready_proposal_count": len(evidence_ready_proposal_ids),
        "proposal_id_missing_count": proposal_id_missing_count,
        "proposal_review_missing_count": proposal_review_missing_count,
        "blocked_before_evidence_count": blocked_before_evidence_count,
        "missing_requirement_counts": missing_requirement_counts,
        "packs": planned_packs,
        "packs_truncated": candidate_pack_count > len(planned_packs),
        "capability_preview_limit": _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_PLAN_PREVIEW_LIMIT,
        "routes": {
            "promotion_plan_route": "/plugins/capabilities/library/promotion/plan",
            "proposal_evidence_source_readiness_route": (_CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_SOURCE_READINESS_ROUTE),
            "proposal_review_plan_route": "/plugins/capabilities/library/proposal-review/plan",
            "proposal_review_route": "/forge/proposals/decision",
            "promotion_route": "/plugins/enable",
        },
        "requirements": {
            "derived_from_capability_library_promotion_readiness": True,
            "uses_existing_plugin_promotion_readiness": True,
            "proposal_id_required_before_evidence": True,
            "proposal_evidence_required_before_proposal_review": True,
            "proposal_evidence_must_be_existing_non_empty_metadata_or_linked_artifact": True,
            "empty_reconstructed_lineage_does_not_satisfy_evidence": True,
            "proposal_review_does_not_promote_or_enable_capabilities": True,
            "read_only_gap_projection": True,
            "no_auto_reconstruction": True,
            "no_auto_approval": True,
        },
        "governance": {
            "read_only": True,
            "operator_facing": True,
            "generated_plugin_registry_sync_performed": sync_performed,
            "does_not_mutate_registry": not sync_performed,
            "does_not_write_receipts": True,
            "does_not_write_validation_receipts": True,
            "does_not_write_proposals": True,
            "does_not_write_proposal_review_receipts": True,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "proposal_review_authority": False,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
        },
        "next_smallest_truthful_gap": next_gap,
    }


def _capability_library_selected_capability_readiness_projection(
    *,
    registry: dict[str, Any],
    entries: list[dict[str, Any]],
    promotion_discipline: dict[str, Any],
    selected_pack_ids: set[str],
    selected_capability_ids: set[str],
    generated_plugin_sync_performed: bool,
) -> dict[str, Any]:
    raw_packs = promotion_discipline.get("packs") if isinstance(promotion_discipline.get("packs"), list) else []
    ready_packs = [
        pack
        for pack in raw_packs
        if isinstance(pack, dict) and bool(pack.get("ready")) and _safe_str(pack.get("status")).strip() == "ready"
    ]
    planned_packs: list[dict[str, Any]] = []
    candidate_pack_count = 0
    candidate_capability_count = 0
    proposal_evidence_missing_count = 0
    proposal_evidence_ready_count = 0
    proposal_review_missing_count = 0
    approved_proposal_review_count = 0
    reviewable_capability_count = 0
    blocked_before_evidence_count = 0
    blocked_before_review_capability_count = 0
    promotable_capability_count = 0
    missing_requirement_counts: dict[str, int] = {}
    unique_proposal_ids: set[str] = set()

    for pack in ready_packs:
        pack_id = _safe_str(pack.get("pack_id")).strip()
        pack_version = _safe_str(pack.get("pack_version")).strip()
        if selected_pack_ids and pack_id not in selected_pack_ids:
            continue
        pack_entries = _entries_for_capability_pack(entries, pack_id=pack_id, pack_version=pack_version)
        staged_ids = _unique_texts(
            [
                _safe_str(entry.get("capability")).strip()
                for entry in pack_entries
                if _safe_str(entry.get("status")).strip() == "staged"
            ],
            limit=10000,
        )
        staged_ids = [capability_id for capability_id in staged_ids if capability_id in selected_capability_ids]
        if not staged_ids:
            continue

        candidate_pack_count += 1
        pack_capabilities: list[dict[str, Any]] = []
        pack_missing_evidence_count = 0
        pack_ready_evidence_count = 0
        pack_reviewable_count = 0
        pack_blocked_before_evidence_count = 0
        pack_blocked_before_review_count = 0
        pack_approved_review_count = 0
        pack_promotable_count = 0

        for capability_id in staged_ids:
            candidate_capability_count += 1
            plugin = _read_plugin(registry, capability_id)
            if plugin is None:
                readiness = {
                    "ready": False,
                    "missing_requirements": ["plugin_record"],
                    "requirements": {"plugin_record": False},
                    "evidence": {},
                }
            else:
                readiness = _plugin_promotion_readiness(
                    capability_id,
                    plugin,
                    PluginToggleIn(id=capability_id, reason="capability_library_selected_readiness"),
                )

            missing = _unique_texts(readiness.get("missing_requirements"), limit=25)
            evidence = readiness.get("evidence") if isinstance(readiness.get("evidence"), dict) else {}
            proposal_id = _safe_str(evidence.get("proposal_id")).strip()
            proposal_review_status = _safe_str(evidence.get("proposal_review_status")).strip()
            proposal_review_receipt_id = _safe_str(evidence.get("proposal_review_receipt_id")).strip()
            compatibility = evidence.get("compatibility") if isinstance(evidence.get("compatibility"), dict) else {}
            proposal_evidence = _unique_texts(evidence.get("proposal_evidence"), limit=50)
            proposal_evidence_missing = "proposal_evidence" in missing
            proposal_evidence_ready = not proposal_evidence_missing and _has_readiness_value(proposal_evidence)
            blockers_before_evidence = [
                requirement for requirement in missing if requirement not in {"proposal_evidence", "proposal_review"}
            ]
            blockers_before_review = [requirement for requirement in missing if requirement != "proposal_review"]
            proposal_review_missing = "proposal_review" in missing
            approved_review = proposal_review_status == "approved" and bool(proposal_review_receipt_id)
            reviewable = proposal_review_missing and bool(proposal_id) and not blockers_before_review
            promotable = bool(readiness.get("ready"))

            if proposal_id:
                unique_proposal_ids.add(proposal_id)
            for requirement in missing:
                missing_requirement_counts[requirement] = missing_requirement_counts.get(requirement, 0) + 1
            if proposal_evidence_missing:
                proposal_evidence_missing_count += 1
                pack_missing_evidence_count += 1
            elif proposal_evidence_ready:
                proposal_evidence_ready_count += 1
                pack_ready_evidence_count += 1
            if proposal_review_missing:
                proposal_review_missing_count += 1
            if approved_review:
                approved_proposal_review_count += 1
                pack_approved_review_count += 1
            elif reviewable:
                reviewable_capability_count += 1
                pack_reviewable_count += 1
            if blockers_before_evidence:
                blocked_before_evidence_count += 1
                pack_blocked_before_evidence_count += 1
            if blockers_before_review:
                blocked_before_review_capability_count += 1
                pack_blocked_before_review_count += 1
            if promotable:
                promotable_capability_count += 1
                pack_promotable_count += 1

            pack_capabilities.append(
                {
                    "capability": capability_id,
                    "status": _safe_str(plugin.get("status") if isinstance(plugin, dict) else "missing").strip(),
                    "proposal_id": proposal_id,
                    "proposal_evidence_ready": proposal_evidence_ready,
                    "proposal_evidence_missing": proposal_evidence_missing,
                    "proposal_review_status": proposal_review_status,
                    "proposal_review_receipt_id": proposal_review_receipt_id,
                    "proposal_review_missing": proposal_review_missing,
                    "compatibility": compatibility,
                    "review_ready": reviewable,
                    "approved_review": approved_review,
                    "promotion_ready": promotable,
                    "missing_requirements": missing,
                    "blockers_before_evidence": blockers_before_evidence,
                    "blockers_before_review": blockers_before_review,
                }
            )

        planned_packs.append(
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "pack_name": _safe_str(pack.get("pack_name")).strip(),
                "staged_capability_count": len(staged_ids),
                "candidate_capability_count": len(staged_ids),
                "proposal_evidence_missing_count": pack_missing_evidence_count,
                "proposal_evidence_ready_count": pack_ready_evidence_count,
                "reviewable_capability_count": pack_reviewable_count,
                "blocked_before_evidence_count": pack_blocked_before_evidence_count,
                "blocked_before_review_capability_count": pack_blocked_before_review_count,
                "approved_proposal_review_count": pack_approved_review_count,
                "promotable_capability_count": pack_promotable_count,
                "capabilities": pack_capabilities,
                "capabilities_truncated": False,
            }
        )

    if not candidate_capability_count:
        status = "no_selected_staged_capabilities"
        next_gap = "stage17_capability_library_selected_capability_readback"
    elif blocked_before_evidence_count or proposal_evidence_missing_count:
        status = "blocked"
        next_gap = "stage17_capability_library_operator_proposal_evidence_refs"
    elif blocked_before_review_capability_count:
        status = "blocked"
        next_gap = "stage17_capability_library_promotion_readiness"
    elif reviewable_capability_count:
        status = "ready_for_proposal_review"
        next_gap = "stage17_capability_library_proposal_review_apply"
    elif promotable_capability_count:
        status = "selected_capabilities_ready_for_explicit_promotion"
        next_gap = "stage17_capability_library_explicit_promotion_apply"
    elif proposal_review_missing_count == 0 and approved_proposal_review_count:
        status = "proposal_review_complete"
        next_gap = "stage17_capability_library_explicit_promotion_apply"
    else:
        status = "selected_capability_review_state_unknown"
        next_gap = "stage17_capability_library_selected_capability_readback"

    return {
        "stage": "Stage 17 / Capability Economy",
        "status": status,
        "projection_scope": "selected_capabilities",
        "global_counts_included": False,
        **_stage17_projection_evidence(
            projection_scope="selected_capabilities",
            global_counts_included=False,
            selected_pack_ids=selected_pack_ids,
            selected_capability_ids=selected_capability_ids,
            generated_plugin_sync_performed=bool(generated_plugin_sync_performed),
        ),
        "selected_capability_ids": sorted(selected_capability_ids),
        "selected_pack_ids": sorted(selected_pack_ids),
        "candidate_pack_count": candidate_pack_count,
        "candidate_capability_count": candidate_capability_count,
        "unique_proposal_count": len(unique_proposal_ids),
        "proposal_evidence_missing_count": proposal_evidence_missing_count,
        "proposal_evidence_ready_count": proposal_evidence_ready_count,
        "missing_proposal_evidence_count": proposal_evidence_missing_count,
        "evidence_ready_proposal_count": proposal_evidence_ready_count,
        "proposal_review_missing_count": proposal_review_missing_count,
        "approved_proposal_review_count": approved_proposal_review_count,
        "reviewable_capability_count": reviewable_capability_count,
        "blocked_before_evidence_count": blocked_before_evidence_count,
        "blocked_before_review_capability_count": blocked_before_review_capability_count,
        "promotable_capability_count": promotable_capability_count,
        "missing_requirement_counts": missing_requirement_counts,
        "packs": planned_packs,
        "packs_truncated": False,
        "requirements": {
            "selected_scope_readback_only": True,
            "does_not_replace_full_stage17_projection": True,
            "selected_capability_ids_required_for_fast_scope": True,
            "core_compatibility_required_before_promotion": True,
        },
        "governance": {
            "read_only": True,
            "operator_facing": True,
            "generated_plugin_registry_sync_performed": bool(generated_plugin_sync_performed),
            "does_not_write_receipts": True,
            "does_not_write_validation_receipts": True,
            "does_not_write_proposals": True,
            "does_not_write_proposal_review_receipts": True,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "proposal_review_authority": False,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
        },
        "next_smallest_truthful_gap": next_gap,
    }


def _capability_library_selected_catalog_entries_from_registry(
    *,
    registry: dict[str, Any],
    selected_capability_ids: set[str],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for capability_id in sorted(selected_capability_ids):
        plugin = _read_plugin(registry, capability_id)
        if plugin is None:
            continue
        spec = _spec_from_plugin_record(plugin)
        metadata = dict(spec.metadata) if isinstance(spec.metadata, dict) else {}
        status = _safe_str(metadata.get("promotion_status") or metadata.get("status")).strip().lower() or "unknown"
        quality = metadata.get("quality") if isinstance(metadata.get("quality"), dict) else {}
        tests = _unique_texts(metadata.get("tests") or metadata.get("test_refs") or quality.get("tests"), limit=50)
        docs = _unique_texts(metadata.get("docs") or metadata.get("documentation") or quality.get("docs"), limit=50)
        entries.append(
            {
                "capability": capability_id,
                "version": _safe_str(spec.version).strip() or _safe_str(plugin.get("version")).strip() or "0.1.0",
                "status": status,
                "risk_tier": _safe_str(metadata.get("risk_tier")).strip().lower()
                or _safe_str(spec.risk_class).strip().lower()
                or _plugin_risk_tier(plugin),
                "source": _safe_str(spec.origin).strip().lower()
                or _safe_str(plugin.get("source_kind")).strip().lower()
                or "unknown",
                "proposal_id": _safe_str(metadata.get("proposal_id") or metadata.get("forge_proposal_id")).strip(),
                "promotion_receipt_id": _safe_str(metadata.get("promotion_receipt_id")).strip(),
                "quality": {"tests": tests, "docs": docs},
                "metadata": metadata,
            }
        )
    return entries


def _capability_library_selected_promotion_discipline_context(
    *,
    registry: dict[str, Any],
    selected_capability_ids: set[str],
) -> dict[str, Any]:
    for capability_id in sorted(selected_capability_ids):
        _ensure_plugin_from_generated(registry, capability_id)
    entries = _capability_library_selected_catalog_entries_from_registry(
        registry=registry,
        selected_capability_ids=selected_capability_ids,
    )
    available_proposals = _available_capability_pack_proposals()
    available_validation_receipts = _available_capability_pack_validation_receipts()
    available_promotion_receipts = _available_capability_pack_promotion_receipts()
    promotion_discipline = analyze_capability_pack_promotion_discipline(
        entries,
        available_proposal_ids=available_proposals["ids"],
        available_validation_receipt_ids=available_validation_receipts["ids"],
        available_promotion_receipt_ids=available_promotion_receipts["ids"],
        operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
    )
    return {
        "entries": entries,
        "promotion_discipline": promotion_discipline,
        "generated_plugin_registry_sync_performed": bool(selected_capability_ids),
    }


def _capability_library_proposal_evidence_remediation_projection(
    *,
    registry: dict[str, Any],
    entries: list[dict[str, Any]],
    promotion_discipline: dict[str, Any],
    generated_plugin_sync_performed: bool,
) -> dict[str, Any]:
    source_plan = _capability_library_proposal_evidence_plan_projection(
        registry=registry,
        entries=entries,
        promotion_discipline=promotion_discipline,
        generated_plugin_sync_performed=generated_plugin_sync_performed,
    )
    sync_performed = bool(generated_plugin_sync_performed)
    raw_packs = promotion_discipline.get("packs") if isinstance(promotion_discipline.get("packs"), list) else []
    ready_packs = [
        pack
        for pack in raw_packs
        if isinstance(pack, dict) and bool(pack.get("ready")) and _safe_str(pack.get("status")).strip() == "ready"
    ]
    planned_packs: list[dict[str, Any]] = []
    preview_remaining = _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_REMEDIATION_PREVIEW_LIMIT
    candidate_pack_count = 0
    candidate_capability_count = 0
    existing_metadata_evidence_count = 0
    proposal_id_missing_count = 0
    plugin_record_missing_count = 0

    for pack in ready_packs:
        pack_id = _safe_str(pack.get("pack_id")).strip()
        pack_version = _safe_str(pack.get("pack_version")).strip()
        pack_entries = _entries_for_capability_pack(entries, pack_id=pack_id, pack_version=pack_version)
        staged_ids = _unique_texts(
            [
                _safe_str(entry.get("capability")).strip()
                for entry in pack_entries
                if _safe_str(entry.get("status")).strip() == "staged"
            ],
            limit=10000,
        )
        if not staged_ids:
            continue

        include_pack_preview = len(planned_packs) < _CAPABILITY_LIBRARY_OPERATOR_SURFACE_PACK_PREVIEW_LIMIT
        pack_candidate_count = 0
        pack_capabilities: list[dict[str, Any]] = []

        for capability_id in staged_ids:
            plugin = _read_plugin(registry, capability_id)
            if plugin is None:
                plugin_record_missing_count += 1
                continue
            meta = dict(plugin.get("meta") or {}) if isinstance(plugin.get("meta"), dict) else {}
            proposal_id = _safe_str(meta.get("proposal_id") or meta.get("forge_proposal_id")).strip()
            if not proposal_id:
                proposal_id_missing_count += 1
                continue
            metadata_evidence = _unique_texts(meta.get("proposal_evidence") or meta.get("evidence"), limit=50)
            if _has_readiness_value(metadata_evidence):
                existing_metadata_evidence_count += 1
                continue
            linked_evidence = _plugin_proposal_friction_evidence(proposal_id)
            if not linked_evidence:
                continue

            candidate_capability_count += 1
            pack_candidate_count += 1
            if include_pack_preview and preview_remaining > 0:
                pack_capabilities.append(
                    {
                        "capability": capability_id,
                        "status": _safe_str(plugin.get("status")).strip(),
                        "proposal_id": proposal_id,
                        "metadata_proposal_evidence": metadata_evidence,
                        "linked_proposal_artifact_evidence": linked_evidence,
                        "evidence_source": "linked_proposal_artifact",
                        "writes_registry_metadata": True,
                        "writes_proposals": False,
                        "approves_proposals": False,
                        "promotes_capability": False,
                    }
                )
                preview_remaining -= 1

        if pack_candidate_count:
            candidate_pack_count += 1
            if include_pack_preview:
                planned_packs.append(
                    {
                        "pack_id": pack_id,
                        "pack_version": pack_version,
                        "pack_name": _safe_str(pack.get("pack_name")).strip(),
                        "staged_capability_count": len(staged_ids),
                        "candidate_capability_count": pack_candidate_count,
                        "capabilities": pack_capabilities,
                        "capabilities_truncated": len(pack_capabilities) < pack_candidate_count,
                    }
                )

    discipline_blocked_pack_count = _count_value(promotion_discipline.get("blocked_pack_count"))
    source_missing_count = _count_value(source_plan.get("proposal_evidence_missing_count"))
    if discipline_blocked_pack_count:
        status = "blocked"
        next_gap = (
            _safe_str(promotion_discipline.get("next_smallest_truthful_gap")).strip()
            or "stage17_capability_pack_promotion_rules"
        )
    elif candidate_capability_count:
        status = "ready_for_proposal_evidence_backfill"
        next_gap = "stage17_capability_library_proposal_evidence_remediation_apply"
    elif source_missing_count:
        status = "no_existing_artifact_evidence_candidates"
        next_gap = _safe_str(source_plan.get("next_smallest_truthful_gap")).strip()
    else:
        status = "proposal_evidence_complete"
        next_gap = _safe_str(source_plan.get("next_smallest_truthful_gap")).strip()

    return {
        "stage": "Stage 17 / Capability Economy",
        "status": status,
        "proposal_evidence_remediation_ready": bool(candidate_capability_count) and not discipline_blocked_pack_count,
        "pack_total": _count_value(promotion_discipline.get("pack_total")),
        "ready_pack_count": _count_value(promotion_discipline.get("ready_pack_count")),
        "blocked_pack_count": discipline_blocked_pack_count,
        "candidate_pack_count": candidate_pack_count,
        "candidate_capability_count": candidate_capability_count,
        "existing_metadata_evidence_count": existing_metadata_evidence_count,
        "proposal_id_missing_count": proposal_id_missing_count,
        "plugin_record_missing_count": plugin_record_missing_count,
        "source_proposal_evidence_plan": {
            "status": _safe_str(source_plan.get("status")).strip(),
            "candidate_capability_count": _count_value(source_plan.get("candidate_capability_count")),
            "proposal_evidence_missing_count": source_missing_count,
            "proposal_evidence_ready_count": _count_value(source_plan.get("proposal_evidence_ready_count")),
            "proposal_review_missing_count": _count_value(source_plan.get("proposal_review_missing_count")),
            "next_smallest_truthful_gap": _safe_str(source_plan.get("next_smallest_truthful_gap")).strip(),
        },
        "packs": planned_packs,
        "packs_truncated": candidate_pack_count > len(planned_packs),
        "capability_preview_limit": _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_REMEDIATION_PREVIEW_LIMIT,
        "routes": {
            "proposal_evidence_plan_route": "/plugins/capabilities/library/proposal-evidence/plan",
            "proposal_evidence_remediation_apply_route": _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_REMEDIATION_APPLY_ROUTE,
            "proposal_review_plan_route": "/plugins/capabilities/library/proposal-review/plan",
            "proposal_review_route": "/forge/proposals/decision",
            "promotion_plan_route": "/plugins/capabilities/library/promotion/plan",
            "promotion_route": "/plugins/enable",
        },
        "requirements": {
            "uses_existing_plugin_promotion_readiness": True,
            "only_existing_linked_proposal_artifact_evidence": True,
            "non_empty_artifact_friction_evidence_required": True,
            "empty_reconstructed_lineage_does_not_satisfy_evidence": True,
            "explicit_operator_action_required": True,
            "dry_run_supported": True,
            "no_synthetic_evidence": True,
            "does_not_review_or_approve_proposals": True,
            "does_not_promote_or_enable_capabilities": True,
        },
        "governance": {
            "read_only": True,
            "operator_facing": True,
            "generated_plugin_registry_sync_performed": sync_performed,
            "does_not_mutate_registry": not sync_performed,
            "apply_requires_plugins_write_scope": True,
            "apply_route": _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_REMEDIATION_APPLY_ROUTE,
            "does_not_write_receipts": True,
            "does_not_write_validation_receipts": True,
            "does_not_write_proposals": True,
            "does_not_write_proposal_review_receipts": True,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "proposal_review_authority": False,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
        },
        "next_smallest_truthful_gap": next_gap,
    }


def _capability_library_existing_friction_summary_field(meta: dict[str, Any]) -> tuple[str, Any]:
    for field in ("friction_summary", "friction"):
        value = meta.get(field)
        if _has_readiness_value(value):
            return field, value
    return "", None


def _capability_library_proposal_evidence_friction_summary_ref(
    *,
    capability_id: str,
    field_name: str,
) -> str:
    safe_field = _safe_str(field_name).strip() or "friction_summary"
    return f"registry.plugins.{capability_id}.meta.{safe_field}"


def _capability_library_proposal_evidence_friction_summary_ref_projection(
    *,
    registry: dict[str, Any],
    entries: list[dict[str, Any]],
    promotion_discipline: dict[str, Any],
    generated_plugin_sync_performed: bool,
) -> dict[str, Any]:
    source_plan = _capability_library_proposal_evidence_plan_projection(
        registry=registry,
        entries=entries,
        promotion_discipline=promotion_discipline,
        generated_plugin_sync_performed=generated_plugin_sync_performed,
    )
    sync_performed = bool(generated_plugin_sync_performed)
    raw_packs = promotion_discipline.get("packs") if isinstance(promotion_discipline.get("packs"), list) else []
    ready_packs = [
        pack
        for pack in raw_packs
        if isinstance(pack, dict) and bool(pack.get("ready")) and _safe_str(pack.get("status")).strip() == "ready"
    ]
    planned_packs: list[dict[str, Any]] = []
    preview_remaining = _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_FRICTION_REF_PREVIEW_LIMIT
    candidate_pack_count = 0
    candidate_capability_count = 0
    existing_metadata_evidence_count = 0
    friction_summary_missing_count = 0
    proposal_id_missing_count = 0
    plugin_record_missing_count = 0

    for pack in ready_packs:
        pack_id = _safe_str(pack.get("pack_id")).strip()
        pack_version = _safe_str(pack.get("pack_version")).strip()
        pack_entries = _entries_for_capability_pack(entries, pack_id=pack_id, pack_version=pack_version)
        staged_ids = _unique_texts(
            [
                _safe_str(entry.get("capability")).strip()
                for entry in pack_entries
                if _safe_str(entry.get("status")).strip() == "staged"
            ],
            limit=10000,
        )
        if not staged_ids:
            continue

        include_pack_preview = len(planned_packs) < _CAPABILITY_LIBRARY_OPERATOR_SURFACE_PACK_PREVIEW_LIMIT
        pack_candidate_count = 0
        pack_capabilities: list[dict[str, Any]] = []

        for capability_id in staged_ids:
            plugin = _read_plugin(registry, capability_id)
            if plugin is None:
                plugin_record_missing_count += 1
                continue
            meta = dict(plugin.get("meta") or {}) if isinstance(plugin.get("meta"), dict) else {}
            proposal_id = _safe_str(meta.get("proposal_id") or meta.get("forge_proposal_id")).strip()
            if not proposal_id:
                proposal_id_missing_count += 1
                continue
            metadata_evidence = _unique_texts(meta.get("proposal_evidence") or meta.get("evidence"), limit=50)
            if _has_readiness_value(metadata_evidence):
                existing_metadata_evidence_count += 1
                continue
            friction_field, friction_summary = _capability_library_existing_friction_summary_field(meta)
            if not friction_field:
                friction_summary_missing_count += 1
                continue

            friction_summary_ref = _capability_library_proposal_evidence_friction_summary_ref(
                capability_id=capability_id,
                field_name=friction_field,
            )
            candidate_capability_count += 1
            pack_candidate_count += 1
            if include_pack_preview and preview_remaining > 0:
                pack_capabilities.append(
                    {
                        "capability": capability_id,
                        "status": _safe_str(plugin.get("status")).strip(),
                        "proposal_id": proposal_id,
                        "metadata_proposal_evidence": metadata_evidence,
                        "friction_summary_field": friction_field,
                        "friction_summary_ref": friction_summary_ref,
                        "friction_summary_preview": redact_governed_value(
                            _safe_str(friction_summary).strip(),
                        )[:240],
                        "evidence_source": "existing_registry_friction_summary_ref",
                        "writes_registry_metadata": True,
                        "writes_proposals": False,
                        "approves_proposals": False,
                        "promotes_capability": False,
                        "requires_future_review": True,
                    }
                )
                preview_remaining -= 1

        if pack_candidate_count:
            candidate_pack_count += 1
            if include_pack_preview:
                planned_packs.append(
                    {
                        "pack_id": pack_id,
                        "pack_version": pack_version,
                        "pack_name": _safe_str(pack.get("pack_name")).strip(),
                        "staged_capability_count": len(staged_ids),
                        "candidate_capability_count": pack_candidate_count,
                        "capabilities": pack_capabilities,
                        "capabilities_truncated": len(pack_capabilities) < pack_candidate_count,
                    }
                )

    discipline_blocked_pack_count = _count_value(promotion_discipline.get("blocked_pack_count"))
    source_missing_count = _count_value(source_plan.get("proposal_evidence_missing_count"))
    if discipline_blocked_pack_count:
        status = "blocked"
        next_gap = (
            _safe_str(promotion_discipline.get("next_smallest_truthful_gap")).strip()
            or "stage17_capability_pack_promotion_rules"
        )
    elif candidate_capability_count:
        status = "ready_for_proposal_evidence_friction_summary_ref_backfill"
        next_gap = "stage17_capability_library_proposal_evidence_friction_summary_refs_apply"
    elif source_missing_count:
        status = "no_existing_friction_summary_ref_candidates"
        next_gap = _safe_str(source_plan.get("next_smallest_truthful_gap")).strip()
    else:
        status = "proposal_evidence_complete"
        next_gap = _safe_str(source_plan.get("next_smallest_truthful_gap")).strip()

    return {
        "stage": "Stage 17 / Capability Economy",
        "status": status,
        "proposal_evidence_friction_summary_refs_ready": bool(candidate_capability_count)
        and not discipline_blocked_pack_count,
        "pack_total": _count_value(promotion_discipline.get("pack_total")),
        "ready_pack_count": _count_value(promotion_discipline.get("ready_pack_count")),
        "blocked_pack_count": discipline_blocked_pack_count,
        "candidate_pack_count": candidate_pack_count,
        "candidate_capability_count": candidate_capability_count,
        "existing_metadata_evidence_count": existing_metadata_evidence_count,
        "friction_summary_missing_count": friction_summary_missing_count,
        "proposal_id_missing_count": proposal_id_missing_count,
        "plugin_record_missing_count": plugin_record_missing_count,
        "source_proposal_evidence_plan": {
            "status": _safe_str(source_plan.get("status")).strip(),
            "candidate_capability_count": _count_value(source_plan.get("candidate_capability_count")),
            "proposal_evidence_missing_count": source_missing_count,
            "proposal_evidence_ready_count": _count_value(source_plan.get("proposal_evidence_ready_count")),
            "proposal_review_missing_count": _count_value(source_plan.get("proposal_review_missing_count")),
            "next_smallest_truthful_gap": _safe_str(source_plan.get("next_smallest_truthful_gap")).strip(),
        },
        "packs": planned_packs,
        "packs_truncated": candidate_pack_count > len(planned_packs),
        "capability_preview_limit": _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_FRICTION_REF_PREVIEW_LIMIT,
        "routes": {
            "proposal_evidence_plan_route": "/plugins/capabilities/library/proposal-evidence/plan",
            "proposal_evidence_friction_summary_refs_apply_route": (
                _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_FRICTION_REF_APPLY_ROUTE
            ),
            "proposal_review_plan_route": "/plugins/capabilities/library/proposal-review/plan",
            "proposal_review_route": "/forge/proposals/decision",
            "promotion_plan_route": "/plugins/capabilities/library/promotion/plan",
            "promotion_route": "/plugins/enable",
        },
        "requirements": {
            "uses_existing_plugin_promotion_readiness": True,
            "only_existing_registry_friction_summary": True,
            "records_reference_not_friction_summary_body": True,
            "non_empty_friction_summary_required": True,
            "explicit_operator_action_required": True,
            "dry_run_supported": True,
            "no_synthetic_evidence": True,
            "not_independent_verification": True,
            "requires_future_review": True,
            "does_not_review_or_approve_proposals": True,
            "does_not_promote_or_enable_capabilities": True,
        },
        "governance": {
            "read_only": True,
            "operator_facing": True,
            "generated_plugin_registry_sync_performed": sync_performed,
            "does_not_mutate_registry": not sync_performed,
            "apply_requires_plugins_write_scope": True,
            "apply_route": _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_FRICTION_REF_APPLY_ROUTE,
            "does_not_write_receipts": True,
            "does_not_write_validation_receipts": True,
            "does_not_write_proposals": True,
            "does_not_write_proposal_review_receipts": True,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "proposal_review_authority": False,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
        },
        "next_smallest_truthful_gap": next_gap,
    }


def _merge_proposal_evidence(existing: Any, additions: list[str]) -> list[str]:
    return _unique_texts([*_unique_texts(existing, limit=50), *additions], limit=50)


def _record_capability_library_proposal_evidence_friction_summary_ref_batch(
    *,
    registry: dict[str, Any],
    prepared: list[dict[str, Any]],
    route_path: str,
) -> dict[str, list[dict[str, Any]]]:
    recorded_ts = _now_s()
    recorded: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    changed = False

    for item in prepared:
        pack_id = _safe_str(item.get("pack_id")).strip()
        pack_version = _safe_str(item.get("pack_version")).strip()
        raw_capabilities = item.get("capabilities") if isinstance(item.get("capabilities"), list) else []
        capabilities = [capability for capability in raw_capabilities if isinstance(capability, dict)]
        changed_capability_ids: list[str] = []
        blocked_capabilities: list[dict[str, Any]] = []

        for capability in capabilities:
            capability_id = _safe_str(capability.get("capability")).strip()
            proposal_id = _safe_str(capability.get("proposal_id")).strip()
            current = _read_plugin(registry, capability_id)
            if current is None:
                blocked_capabilities.append({"capability": capability_id, "error": "capability_not_found"})
                continue
            meta = dict(current.get("meta") or {}) if isinstance(current.get("meta"), dict) else {}
            existing = _unique_texts(meta.get("proposal_evidence") or meta.get("evidence"), limit=50)
            if _has_readiness_value(existing):
                continue
            current_proposal_id = _safe_str(meta.get("proposal_id") or meta.get("forge_proposal_id")).strip()
            if not proposal_id or current_proposal_id != proposal_id:
                blocked_capabilities.append(
                    {
                        "capability": capability_id,
                        "error": "proposal_id_mismatch",
                        "proposal_id": proposal_id,
                        "current_proposal_id": current_proposal_id,
                    }
                )
                continue
            friction_field, _friction_summary = _capability_library_existing_friction_summary_field(meta)
            if not friction_field:
                blocked_capabilities.append(
                    {
                        "capability": capability_id,
                        "error": "friction_summary_required",
                        "proposal_id": proposal_id,
                    }
                )
                continue
            friction_summary_ref = _capability_library_proposal_evidence_friction_summary_ref(
                capability_id=capability_id,
                field_name=friction_field,
            )
            planned_ref = _safe_str(capability.get("friction_summary_ref")).strip()
            if planned_ref and planned_ref != friction_summary_ref:
                blocked_capabilities.append(
                    {
                        "capability": capability_id,
                        "error": "friction_summary_ref_mismatch",
                        "proposal_id": proposal_id,
                        "planned_ref": planned_ref,
                        "current_ref": friction_summary_ref,
                    }
                )
                continue

            meta["proposal_evidence"] = _merge_proposal_evidence(existing, [friction_summary_ref])
            meta["proposal_evidence_link_source"] = _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_FRICTION_REF_SOURCE
            meta["proposal_evidence_claim_scope"] = _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_FRICTION_REF_CLAIM_SCOPE
            meta["proposal_evidence_friction_summary_ref"] = friction_summary_ref
            meta["proposal_evidence_friction_summary_field"] = friction_field
            meta["proposal_evidence_friction_summary_ref_ts"] = recorded_ts
            meta["proposal_evidence_friction_summary_ref_route"] = route_path
            meta["proposal_evidence_friction_summary_ref_requires_future_review"] = True
            meta["proposal_evidence_artifact_proposal_id"] = proposal_id
            meta["proposal_evidence_writes_proposals"] = False
            meta["proposal_evidence_approval_claimed"] = False
            current["meta"] = meta
            current["updated_ts"] = recorded_ts
            _write_plugin(registry, _normalize_plugin_record(capability_id, current))
            changed = True
            changed_capability_ids.append(capability_id)

        if blocked_capabilities:
            failed.append(
                {
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "status": "blocked",
                    "error": "proposal_evidence_friction_summary_ref_backfill_blocked",
                    "capabilities": blocked_capabilities,
                }
            )
        recorded.append(
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "pack_name": _safe_str(item.get("pack_name")).strip() or pack_id,
                "capability_count": len(capabilities),
                "changed_capability_count": len(changed_capability_ids),
                "changed_capability_ids": changed_capability_ids[:50],
                "changed_capability_ids_truncated": len(changed_capability_ids) > 50,
                "evidence_source": "existing_registry_friction_summary_ref",
                "writes_registry_metadata": bool(changed_capability_ids),
                "writes_proposals": False,
                "approves_proposals": False,
                "promotes_capabilities": False,
                "enables_capabilities": False,
                "requires_future_review": True,
                "status": "recorded" if changed_capability_ids else "unchanged",
            }
        )

    if changed:
        _save_registry_and_catalog(registry)
    return {"recorded": recorded, "failed": failed}


def _record_capability_library_proposal_evidence_remediation_batch(
    *,
    registry: dict[str, Any],
    prepared: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    recorded_ts = _now_s()
    recorded: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    changed = False

    for item in prepared:
        pack_id = _safe_str(item.get("pack_id")).strip()
        pack_version = _safe_str(item.get("pack_version")).strip()
        raw_capabilities = item.get("capabilities") if isinstance(item.get("capabilities"), list) else []
        capabilities = [capability for capability in raw_capabilities if isinstance(capability, dict)]
        changed_capability_ids: list[str] = []
        blocked_capabilities: list[dict[str, Any]] = []

        for capability in capabilities:
            capability_id = _safe_str(capability.get("capability")).strip()
            linked_evidence = _unique_texts(capability.get("linked_proposal_artifact_evidence"), limit=50)
            proposal_id = _safe_str(capability.get("proposal_id")).strip()
            current = _read_plugin(registry, capability_id)
            if current is None:
                blocked_capabilities.append({"capability": capability_id, "error": "capability_not_found"})
                continue
            meta = dict(current.get("meta") or {}) if isinstance(current.get("meta"), dict) else {}
            existing = _unique_texts(meta.get("proposal_evidence") or meta.get("evidence"), limit=50)
            if _has_readiness_value(existing):
                continue
            if not proposal_id or not linked_evidence:
                blocked_capabilities.append(
                    {
                        "capability": capability_id,
                        "error": "linked_proposal_artifact_evidence_required",
                        "proposal_id": proposal_id,
                    }
                )
                continue

            meta["proposal_evidence"] = _merge_proposal_evidence(existing, linked_evidence)
            meta["proposal_evidence_link_source"] = _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_REMEDIATION_SOURCE
            meta["proposal_evidence_claim_scope"] = "existing_linked_proposal_artifact_friction_evidence"
            meta["proposal_evidence_artifact_proposal_id"] = proposal_id
            meta["proposal_evidence_writes_proposals"] = False
            meta["proposal_evidence_approval_claimed"] = False
            current["meta"] = meta
            current["updated_ts"] = recorded_ts
            _write_plugin(registry, _normalize_plugin_record(capability_id, current))
            changed = True
            changed_capability_ids.append(capability_id)

        if blocked_capabilities:
            failed.append(
                {
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "status": "blocked",
                    "error": "proposal_evidence_backfill_blocked",
                    "capabilities": blocked_capabilities,
                }
            )
        recorded.append(
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "pack_name": _safe_str(item.get("pack_name")).strip() or pack_id,
                "capability_count": len(capabilities),
                "changed_capability_count": len(changed_capability_ids),
                "changed_capability_ids": changed_capability_ids[:50],
                "changed_capability_ids_truncated": len(changed_capability_ids) > 50,
                "evidence_source": "existing_linked_proposal_artifact_friction_evidence",
                "writes_registry_metadata": bool(changed_capability_ids),
                "writes_proposals": False,
                "approves_proposals": False,
                "promotes_capabilities": False,
                "enables_capabilities": False,
                "status": "recorded" if changed_capability_ids else "unchanged",
            }
        )

    if changed:
        _save_registry_and_catalog(registry)
    return {"recorded": recorded, "failed": failed}


def _capability_library_operator_proposal_evidence_local_artifact_ref_hint(
    *,
    plugin: dict[str, Any],
    proposal_id: str,
) -> dict[str, Any]:
    meta = dict(plugin.get("meta") or {}) if isinstance(plugin.get("meta"), dict) else {}
    proposal_ref_id = _safe_str(proposal_id or meta.get("proposal_id") or meta.get("forge_proposal_id")).strip()
    validation_ref_id = _safe_str(meta.get("validation_receipt_id")).strip()
    refs: list[str] = []
    proposal_path = ""
    validation_receipt_path = ""

    if proposal_ref_id and _PLUGIN_ARTIFACT_ID_RE.match(proposal_ref_id):
        resolved_proposal_path = _plugin_proposal_path(proposal_ref_id)
        if _is_under(_art_dir() / "proposals", resolved_proposal_path) and resolved_proposal_path.is_file():
            proposal_path = _plugin_artifact_relative_path("proposals", proposal_ref_id)
            refs.extend([proposal_ref_id, proposal_path])

    if validation_ref_id and _PLUGIN_ARTIFACT_ID_RE.match(validation_ref_id):
        resolved_validation_path = _plugin_validation_receipt_path(validation_ref_id)
        if _is_under(_art_dir() / "validations", resolved_validation_path) and resolved_validation_path.is_file():
            validation_receipt_path = _plugin_artifact_relative_path("validations", validation_ref_id)
            refs.extend([validation_ref_id, validation_receipt_path])

    evidence_refs = _unique_texts(refs, limit=10)
    return {
        "ready": bool(evidence_refs),
        "source": "local_proposal_validation_artifact_refs",
        "claim_scope": "local_artifact_reference_hint_not_independent_evidence_verification",
        "operator_must_review_before_apply": True,
        "does_not_validate_evidence_truth": True,
        "proposal_id": proposal_ref_id if proposal_path else "",
        "proposal_artifact_path": proposal_path,
        "validation_receipt_id": validation_ref_id if validation_receipt_path else "",
        "validation_receipt_path": validation_receipt_path,
        "evidence_refs": evidence_refs,
        "evidence_ref_count": len(evidence_refs),
    }


def _capability_library_operator_proposal_evidence_intake_candidates(
    *,
    registry: dict[str, Any],
    entries: list[dict[str, Any]],
    promotion_discipline: dict[str, Any],
    selected_pack_ids: set[str],
    selected_capability_ids: set[str],
) -> list[dict[str, Any]]:
    raw_packs = promotion_discipline.get("packs") if isinstance(promotion_discipline.get("packs"), list) else []
    ready_packs = [
        pack
        for pack in raw_packs
        if isinstance(pack, dict) and bool(pack.get("ready")) and _safe_str(pack.get("status")).strip() == "ready"
    ]
    candidates: list[dict[str, Any]] = []

    for pack in ready_packs:
        pack_id = _safe_str(pack.get("pack_id")).strip()
        pack_version = _safe_str(pack.get("pack_version")).strip()
        if selected_pack_ids and pack_id not in selected_pack_ids:
            continue
        pack_entries = _entries_for_capability_pack(entries, pack_id=pack_id, pack_version=pack_version)
        staged_ids = _unique_texts(
            [
                _safe_str(entry.get("capability")).strip()
                for entry in pack_entries
                if _safe_str(entry.get("status")).strip() == "staged"
            ],
            limit=10000,
        )
        if selected_capability_ids:
            staged_ids = [capability_id for capability_id in staged_ids if capability_id in selected_capability_ids]
        if not staged_ids:
            continue

        capabilities: list[dict[str, Any]] = []
        for capability_id in staged_ids:
            plugin = _read_plugin(registry, capability_id)
            if plugin is None:
                continue
            readiness = _plugin_promotion_readiness(
                capability_id,
                plugin,
                PluginToggleIn(id=capability_id, reason="capability_library_operator_proposal_evidence_intake"),
            )
            missing = _unique_texts(readiness.get("missing_requirements"), limit=25)
            evidence = readiness.get("evidence") if isinstance(readiness.get("evidence"), dict) else {}
            proposal_id = _safe_str(evidence.get("proposal_id")).strip()
            blockers_before_evidence = [
                requirement for requirement in missing if requirement not in {"proposal_evidence", "proposal_review"}
            ]
            if "proposal_evidence" not in missing or not proposal_id or blockers_before_evidence:
                continue
            local_artifact_ref_hint = _capability_library_operator_proposal_evidence_local_artifact_ref_hint(
                plugin=plugin,
                proposal_id=proposal_id,
            )
            capabilities.append(
                {
                    "capability": capability_id,
                    "status": _safe_str(plugin.get("status")).strip(),
                    "proposal_id": proposal_id,
                    "proposal_review_status": _safe_str(evidence.get("proposal_review_status")).strip(),
                    "proposal_review_receipt_id": _safe_str(evidence.get("proposal_review_receipt_id")).strip(),
                    "missing_requirements": missing,
                    "blockers_before_evidence": blockers_before_evidence,
                    "local_artifact_ref_hint": local_artifact_ref_hint,
                }
            )

        if capabilities:
            candidates.append(
                {
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "pack_name": _safe_str(pack.get("pack_name")).strip() or pack_id,
                    "staged_capability_count": len(staged_ids),
                    "capabilities": capabilities,
                }
            )

    return candidates


def _capability_library_operator_proposal_evidence_intake_checklist_projection(
    *,
    registry: dict[str, Any],
    entries: list[dict[str, Any]],
    promotion_discipline: dict[str, Any],
    source_plan: dict[str, Any],
    generated_plugin_sync_performed: bool,
) -> dict[str, Any]:
    candidates = _capability_library_operator_proposal_evidence_intake_candidates(
        registry=registry,
        entries=entries,
        promotion_discipline=promotion_discipline,
        selected_pack_ids=set(),
        selected_capability_ids=set(),
    )
    candidate_pack_count = len(candidates)
    candidate_capability_count = sum(
        len(item.get("capabilities") if isinstance(item.get("capabilities"), list) else []) for item in candidates
    )
    preview_remaining = _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_PLAN_PREVIEW_LIMIT
    packs: list[dict[str, Any]] = []
    for item in candidates[:_CAPABILITY_LIBRARY_OPERATOR_SURFACE_PACK_PREVIEW_LIMIT]:
        raw_capabilities = item.get("capabilities") if isinstance(item.get("capabilities"), list) else []
        capabilities = [capability for capability in raw_capabilities if isinstance(capability, dict)]
        visible_capabilities = capabilities[:preview_remaining]
        preview_remaining = max(0, preview_remaining - len(visible_capabilities))
        packs.append(
            {
                "pack_id": _safe_str(item.get("pack_id")).strip(),
                "pack_version": _safe_str(item.get("pack_version")).strip(),
                "pack_name": _safe_str(item.get("pack_name")).strip(),
                "staged_capability_count": _count_value(item.get("staged_capability_count")),
                "candidate_capability_count": len(capabilities),
                "evidence_ref_required_count": len(capabilities),
                "claim_scope": "operator_supplied_friction_evidence_reference_not_independent_verification",
                "capabilities": [
                    {
                        "capability": _safe_str(capability.get("capability")).strip(),
                        "status": _safe_str(capability.get("status")).strip(),
                        "proposal_id": _safe_str(capability.get("proposal_id")).strip(),
                        "proposal_review_status": _safe_str(capability.get("proposal_review_status")).strip(),
                        "proposal_review_receipt_id": _safe_str(capability.get("proposal_review_receipt_id")).strip(),
                        "missing_requirements": _unique_texts(capability.get("missing_requirements"), limit=25),
                        "blockers_before_evidence": _unique_texts(
                            capability.get("blockers_before_evidence"),
                            limit=25,
                        ),
                        "evidence_refs_required": True,
                        "operator_supplied_evidence_not_independently_verified": True,
                        "local_artifact_ref_hint": capability.get("local_artifact_ref_hint")
                        if isinstance(capability.get("local_artifact_ref_hint"), dict)
                        else {},
                        "intake_apply_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_APPLY_ROUTE,
                    }
                    for capability in visible_capabilities
                ],
                "capabilities_truncated": len(visible_capabilities) < len(capabilities),
            }
        )

    status = (
        "ready_for_operator_evidence_refs" if candidate_capability_count else "no_operator_evidence_intake_candidates"
    )
    next_gap = (
        "stage17_capability_library_operator_proposal_evidence_refs"
        if candidate_capability_count
        else _safe_str(source_plan.get("next_smallest_truthful_gap")).strip()
    )
    sync_performed = bool(generated_plugin_sync_performed)
    return {
        "stage": "Stage 17 / Capability Economy",
        "status": status,
        "operator_evidence_intake_checklist_ready": bool(candidate_capability_count),
        "candidate_pack_count": candidate_pack_count,
        "candidate_capability_count": candidate_capability_count,
        "evidence_ref_required_count": candidate_capability_count,
        "source_proposal_evidence_plan": {
            "status": _safe_str(source_plan.get("status")).strip(),
            "candidate_capability_count": _count_value(source_plan.get("candidate_capability_count")),
            "proposal_evidence_missing_count": _count_value(source_plan.get("proposal_evidence_missing_count")),
            "proposal_evidence_ready_count": _count_value(source_plan.get("proposal_evidence_ready_count")),
            "proposal_review_missing_count": _count_value(source_plan.get("proposal_review_missing_count")),
            "next_smallest_truthful_gap": _safe_str(source_plan.get("next_smallest_truthful_gap")).strip(),
        },
        "packs": packs,
        "packs_truncated": candidate_pack_count > len(packs),
        "capability_preview_limit": _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_PLAN_PREVIEW_LIMIT,
        "routes": {
            "proposal_evidence_plan_route": "/plugins/capabilities/library/proposal-evidence/plan",
            "operator_intake_apply_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_APPLY_ROUTE,
            "operator_intake_preview_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_PREVIEW_ROUTE,
            "operator_intake_import_preview_route": (
                _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_IMPORT_PREVIEW_ROUTE
            ),
            "proposal_review_plan_route": "/plugins/capabilities/library/proposal-review/plan",
            "promotion_plan_route": "/plugins/capabilities/library/promotion/plan",
        },
        "requirements": {
            "operator_evidence_refs_required": True,
            "operator_supplied_evidence_not_independently_verified": True,
            "dry_run_required_before_apply": True,
            "pack_scoped_apply_recommended": True,
            "no_synthetic_evidence": True,
            "proposal_evidence_required_before_proposal_review": True,
        },
        "governance": {
            "read_only": True,
            "operator_facing": True,
            "generated_plugin_registry_sync_performed": sync_performed,
            "does_not_mutate_registry": not sync_performed,
            "apply_requires_plugins_write_scope": True,
            "apply_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_APPLY_ROUTE,
            "writes_registry_metadata": False,
            "writes_proposals": False,
            "does_not_write_proposal_review_receipts": True,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
        },
        "next_smallest_truthful_gap": next_gap,
    }


def _capability_library_operator_proposal_evidence_intake_worksheet_projection(
    *,
    registry: dict[str, Any],
    entries: list[dict[str, Any]],
    promotion_discipline: dict[str, Any],
    source_plan: dict[str, Any],
    generated_plugin_sync_performed: bool,
) -> dict[str, Any]:
    candidates = _capability_library_operator_proposal_evidence_intake_candidates(
        registry=registry,
        entries=entries,
        promotion_discipline=promotion_discipline,
        selected_pack_ids=set(),
        selected_capability_ids=set(),
    )
    worksheet_pack_count = len(candidates)
    worksheet_row_count = sum(
        len(item.get("capabilities") if isinstance(item.get("capabilities"), list) else []) for item in candidates
    )
    preview_remaining = _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_PLAN_PREVIEW_LIMIT
    packs: list[dict[str, Any]] = []
    for item in candidates[:_CAPABILITY_LIBRARY_OPERATOR_SURFACE_PACK_PREVIEW_LIMIT]:
        raw_capabilities = item.get("capabilities") if isinstance(item.get("capabilities"), list) else []
        capabilities = [capability for capability in raw_capabilities if isinstance(capability, dict)]
        visible_capabilities = capabilities[:preview_remaining]
        preview_remaining = max(0, preview_remaining - len(visible_capabilities))
        pack_id = _safe_str(item.get("pack_id")).strip()
        pack_version = _safe_str(item.get("pack_version")).strip()
        packs.append(
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "pack_name": _safe_str(item.get("pack_name")).strip(),
                "staged_capability_count": _count_value(item.get("staged_capability_count")),
                "worksheet_row_count": len(capabilities),
                "evidence_ref_required_count": len(capabilities),
                "claim_scope": "operator_supplied_friction_evidence_reference_not_independent_verification",
                "rows": [
                    {
                        "capability": _safe_str(capability.get("capability")).strip(),
                        "status": _safe_str(capability.get("status")).strip(),
                        "proposal_id": _safe_str(capability.get("proposal_id")).strip(),
                        "proposal_review_status": _safe_str(capability.get("proposal_review_status")).strip(),
                        "proposal_review_receipt_id": _safe_str(capability.get("proposal_review_receipt_id")).strip(),
                        "missing_requirements": _unique_texts(capability.get("missing_requirements"), limit=25),
                        "blockers_before_evidence": _unique_texts(
                            capability.get("blockers_before_evidence"),
                            limit=25,
                        ),
                        "operator_evidence_refs": [],
                        "operator_evidence_ref_count": 0,
                        "operator_evidence_refs_required": True,
                        "evidence_ref_collection_status": "pending_operator_input",
                        "claim_scope": "operator_supplied_friction_evidence_reference_not_independent_verification",
                        "apply_payload_hint": {
                            "pack_ids": [pack_id],
                            "capability_ids": [_safe_str(capability.get("capability")).strip()],
                            "evidence_refs": [],
                            "dry_run": True,
                        },
                        "operator_supplied_evidence_not_independently_verified": True,
                        "requires_future_proposal_review": True,
                        "intake_apply_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_APPLY_ROUTE,
                    }
                    for capability in visible_capabilities
                ],
                "rows_truncated": len(visible_capabilities) < len(capabilities),
            }
        )

    status = "ready_for_operator_evidence_collection" if worksheet_row_count else "no_operator_evidence_worksheet_rows"
    next_gap = (
        "stage17_capability_library_operator_proposal_evidence_refs"
        if worksheet_row_count
        else _safe_str(source_plan.get("next_smallest_truthful_gap")).strip()
    )
    sync_performed = bool(generated_plugin_sync_performed)
    return {
        "stage": "Stage 17 / Capability Economy",
        "status": status,
        "operator_evidence_intake_worksheet_ready": bool(worksheet_row_count),
        "worksheet_pack_count": worksheet_pack_count,
        "worksheet_row_count": worksheet_row_count,
        "evidence_ref_required_count": worksheet_row_count,
        "source_proposal_evidence_plan": {
            "status": _safe_str(source_plan.get("status")).strip(),
            "candidate_capability_count": _count_value(source_plan.get("candidate_capability_count")),
            "proposal_evidence_missing_count": _count_value(source_plan.get("proposal_evidence_missing_count")),
            "proposal_evidence_ready_count": _count_value(source_plan.get("proposal_evidence_ready_count")),
            "proposal_review_missing_count": _count_value(source_plan.get("proposal_review_missing_count")),
            "next_smallest_truthful_gap": _safe_str(source_plan.get("next_smallest_truthful_gap")).strip(),
        },
        "packs": packs,
        "packs_truncated": worksheet_pack_count > len(packs),
        "row_preview_limit": _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_PLAN_PREVIEW_LIMIT,
        "routes": {
            "proposal_evidence_plan_route": "/plugins/capabilities/library/proposal-evidence/plan",
            "operator_intake_checklist_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_CHECKLIST_ROUTE,
            "operator_intake_worksheet_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_WORKSHEET_ROUTE,
            "operator_intake_audit_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_AUDIT_ROUTE,
            "operator_intake_apply_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_APPLY_ROUTE,
            "operator_intake_preview_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_PREVIEW_ROUTE,
            "operator_intake_import_preview_route": (
                _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_IMPORT_PREVIEW_ROUTE
            ),
            "proposal_review_apply_readiness_route": _CAPABILITY_LIBRARY_PROPOSAL_REVIEW_APPLY_READINESS_ROUTE,
            "proposal_review_plan_route": "/plugins/capabilities/library/proposal-review/plan",
            "promotion_plan_route": "/plugins/capabilities/library/promotion/plan",
        },
        "requirements": {
            "operator_evidence_refs_required": True,
            "operator_supplied_evidence_not_independently_verified": True,
            "worksheet_contains_blank_evidence_slots": True,
            "no_synthetic_evidence": True,
            "dry_run_required_before_apply": True,
            "pack_or_capability_scoped_apply_required": True,
            "future_proposal_review_required": True,
        },
        "governance": {
            "read_only": True,
            "operator_facing": True,
            "generated_plugin_registry_sync_performed": sync_performed,
            "does_not_mutate_registry": not sync_performed,
            "apply_requires_plugins_write_scope": True,
            "apply_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_APPLY_ROUTE,
            "writes_registry_metadata": False,
            "writes_proposals": False,
            "does_not_write_proposal_review_receipts": True,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
        },
        "next_smallest_truthful_gap": next_gap,
    }


def _capability_library_operator_proposal_evidence_intake_export_projection(
    *,
    registry: dict[str, Any],
    entries: list[dict[str, Any]],
    promotion_discipline: dict[str, Any],
    source_plan: dict[str, Any],
    generated_plugin_sync_performed: bool,
) -> dict[str, Any]:
    candidates = _capability_library_operator_proposal_evidence_intake_candidates(
        registry=registry,
        entries=entries,
        promotion_discipline=promotion_discipline,
        selected_pack_ids=set(),
        selected_capability_ids=set(),
    )
    export_pack_count = len(candidates)
    candidate_row_count = sum(
        len(item.get("capabilities") if isinstance(item.get("capabilities"), list) else []) for item in candidates
    )
    row_limit = _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_EXPORT_ROW_LIMIT
    remaining = row_limit
    exported_row_count = 0
    packs: list[dict[str, Any]] = []

    for item in candidates:
        if remaining <= 0:
            break
        raw_capabilities = item.get("capabilities") if isinstance(item.get("capabilities"), list) else []
        capabilities = [capability for capability in raw_capabilities if isinstance(capability, dict)]
        visible_capabilities = capabilities[:remaining]
        remaining = max(0, remaining - len(visible_capabilities))
        exported_row_count += len(visible_capabilities)
        pack_id = _safe_str(item.get("pack_id")).strip()
        pack_version = _safe_str(item.get("pack_version")).strip()
        rows: list[dict[str, Any]] = []
        for capability in visible_capabilities:
            capability_id = _safe_str(capability.get("capability")).strip()
            local_artifact_ref_hint = (
                capability.get("local_artifact_ref_hint")
                if isinstance(capability.get("local_artifact_ref_hint"), dict)
                else {}
            )
            suggested_evidence_refs = (
                _unique_texts(local_artifact_ref_hint.get("evidence_refs"), limit=10)
                if bool(local_artifact_ref_hint.get("ready"))
                else []
            )
            rows.append(
                {
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "pack_name": _safe_str(item.get("pack_name")).strip(),
                    "capability": capability_id,
                    "status": _safe_str(capability.get("status")).strip(),
                    "proposal_id": _safe_str(capability.get("proposal_id")).strip(),
                    "proposal_review_status": _safe_str(capability.get("proposal_review_status")).strip(),
                    "proposal_review_receipt_id": _safe_str(capability.get("proposal_review_receipt_id")).strip(),
                    "missing_requirements": _unique_texts(capability.get("missing_requirements"), limit=25),
                    "blockers_before_evidence": _unique_texts(
                        capability.get("blockers_before_evidence"),
                        limit=25,
                    ),
                    "evidence_refs_input": "",
                    "evidence_refs_input_format": "comma_separated_or_json_array",
                    "suggested_evidence_refs": suggested_evidence_refs,
                    "suggested_evidence_refs_input": json.dumps(suggested_evidence_refs)
                    if suggested_evidence_refs
                    else "",
                    "suggested_evidence_ref_count": len(suggested_evidence_refs),
                    "suggested_evidence_ref_source": (
                        "local_proposal_validation_artifact_refs" if suggested_evidence_refs else ""
                    ),
                    "suggested_evidence_refs_require_operator_confirmation": True,
                    "local_artifact_ref_hint": local_artifact_ref_hint,
                    "operator_evidence_refs_required": True,
                    "evidence_ref_collection_status": "pending_operator_input",
                    "claim_scope": "operator_supplied_friction_evidence_reference_not_independent_verification",
                    "dry_run_required": True,
                    "apply_payload_hint": {
                        "pack_ids": [pack_id],
                        "capability_ids": [capability_id],
                        "evidence_refs": [],
                        "evidence_refs_by_capability": (
                            {capability_id: suggested_evidence_refs} if suggested_evidence_refs else {}
                        ),
                        "dry_run": True,
                    },
                    "operator_supplied_evidence_not_independently_verified": True,
                    "requires_future_proposal_review": True,
                    "intake_apply_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_APPLY_ROUTE,
                }
            )
        packs.append(
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "pack_name": _safe_str(item.get("pack_name")).strip(),
                "staged_capability_count": _count_value(item.get("staged_capability_count")),
                "export_row_count": len(capabilities),
                "exported_row_count": len(rows),
                "evidence_ref_required_count": len(capabilities),
                "suggested_evidence_ref_capability_count": sum(
                    1 for row in rows if int(row.get("suggested_evidence_ref_count") or 0) > 0
                ),
                "suggested_evidence_ref_count": sum(int(row.get("suggested_evidence_ref_count") or 0) for row in rows),
                "claim_scope": "operator_supplied_friction_evidence_reference_not_independent_verification",
                "rows": rows,
                "rows_truncated": len(rows) < len(capabilities),
            }
        )

    status = "ready_for_operator_evidence_export" if candidate_row_count else "no_operator_evidence_export_rows"
    next_gap = (
        "stage17_capability_library_operator_proposal_evidence_refs"
        if candidate_row_count
        else _safe_str(source_plan.get("next_smallest_truthful_gap")).strip()
    )
    sync_performed = bool(generated_plugin_sync_performed)
    return {
        "stage": "Stage 17 / Capability Economy",
        "status": status,
        "operator_evidence_intake_export_ready": bool(candidate_row_count),
        "export_pack_count": export_pack_count,
        "export_row_count": candidate_row_count,
        "exported_row_count": exported_row_count,
        "evidence_ref_required_count": candidate_row_count,
        "export_rows_truncated": exported_row_count < candidate_row_count,
        "row_limit": row_limit,
        "source_proposal_evidence_plan": {
            "status": _safe_str(source_plan.get("status")).strip(),
            "candidate_capability_count": _count_value(source_plan.get("candidate_capability_count")),
            "proposal_evidence_missing_count": _count_value(source_plan.get("proposal_evidence_missing_count")),
            "proposal_evidence_ready_count": _count_value(source_plan.get("proposal_evidence_ready_count")),
            "proposal_review_missing_count": _count_value(source_plan.get("proposal_review_missing_count")),
            "next_smallest_truthful_gap": _safe_str(source_plan.get("next_smallest_truthful_gap")).strip(),
        },
        "export_schema": {
            "format": "json",
            "evidence_refs_input_format": "comma_separated_or_json_array",
            "columns": [
                "pack_id",
                "pack_version",
                "capability",
                "proposal_id",
                "evidence_refs_input",
                "suggested_evidence_refs_input",
            ],
            "blank_evidence_refs_input_means_not_ready_for_apply": True,
        },
        "packs": packs,
        "packs_truncated": export_pack_count > len(packs),
        "routes": {
            "proposal_evidence_plan_route": "/plugins/capabilities/library/proposal-evidence/plan",
            "operator_intake_checklist_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_CHECKLIST_ROUTE,
            "operator_intake_worksheet_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_WORKSHEET_ROUTE,
            "operator_intake_export_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_EXPORT_ROUTE,
            "operator_intake_audit_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_AUDIT_ROUTE,
            "operator_intake_apply_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_APPLY_ROUTE,
            "operator_intake_preview_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_PREVIEW_ROUTE,
            "operator_intake_import_preview_route": (
                _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_IMPORT_PREVIEW_ROUTE
            ),
            "proposal_review_apply_readiness_route": _CAPABILITY_LIBRARY_PROPOSAL_REVIEW_APPLY_READINESS_ROUTE,
            "proposal_review_plan_route": "/plugins/capabilities/library/proposal-review/plan",
            "promotion_plan_route": "/plugins/capabilities/library/promotion/plan",
        },
        "requirements": {
            "operator_evidence_refs_required": True,
            "operator_supplied_evidence_not_independently_verified": True,
            "export_contains_blank_evidence_slots": True,
            "no_synthetic_evidence": True,
            "dry_run_required_before_apply": True,
            "pack_or_capability_scoped_apply_required": True,
            "future_proposal_review_required": True,
            "does_not_validate_evidence_truth": True,
            "import_requires_governed_apply_route": True,
            "suggested_local_artifact_refs_require_operator_confirmation": True,
            "suggested_refs_do_not_validate_evidence_truth": True,
        },
        "governance": {
            "read_only": True,
            "operator_facing": True,
            "generated_plugin_registry_sync_performed": sync_performed,
            "does_not_mutate_registry": not sync_performed,
            "apply_requires_plugins_write_scope": True,
            "apply_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_APPLY_ROUTE,
            "writes_registry_metadata": False,
            "writes_proposals": False,
            "does_not_write_proposal_review_receipts": True,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
        },
        "next_smallest_truthful_gap": next_gap,
    }


def _parse_operator_proposal_evidence_refs_input(value: Any) -> tuple[list[str], str]:
    if isinstance(value, list):
        refs = _unique_texts(value, limit=50)
        return refs, "" if refs else "evidence_refs_input_required"

    raw = _safe_str(value).strip()
    if not raw:
        return [], "evidence_refs_input_required"

    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except Exception:
            return [], "evidence_refs_input_invalid_json_array"
        if not isinstance(parsed, list):
            return [], "evidence_refs_input_invalid_json_array"
        refs = _unique_texts(parsed, limit=50)
        return refs, "" if refs else "evidence_refs_input_required"

    refs = _unique_texts(raw.replace("\r", "\n").replace("\n", ",").split(","), limit=50)
    return refs, "" if refs else "evidence_refs_input_required"


def _operator_proposal_evidence_refs_input_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return not _unique_texts(value, limit=50)
    return not _safe_str(value).strip()


def _capability_library_operator_proposal_evidence_intake_import_preview_projection(
    *,
    rows: list[dict[str, Any]],
    registry: dict[str, Any],
    entries: list[dict[str, Any]],
    promotion_discipline: dict[str, Any],
    source_plan: dict[str, Any],
    generated_plugin_sync_performed: bool,
    max_row_count: int,
    max_apply_group_count: int,
    use_suggested_evidence_refs: bool = False,
) -> dict[str, Any]:
    candidates = _capability_library_operator_proposal_evidence_intake_candidates(
        registry=registry,
        entries=entries,
        promotion_discipline=promotion_discipline,
        selected_pack_ids=set(),
        selected_capability_ids=set(),
    )
    candidate_keys: set[tuple[str, str, str]] = set()
    for pack in candidates:
        pack_id = _safe_str(pack.get("pack_id")).strip()
        pack_version = _safe_str(pack.get("pack_version")).strip()
        raw_capabilities = pack.get("capabilities") if isinstance(pack.get("capabilities"), list) else []
        for capability in raw_capabilities:
            if not isinstance(capability, dict):
                continue
            capability_id = _safe_str(capability.get("capability")).strip()
            if pack_id and pack_version and capability_id:
                candidate_keys.add((pack_id, pack_version, capability_id))

    row_limit = max(1, min(int(max_row_count or _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_EXPORT_ROW_LIMIT), 5000))
    apply_group_limit = max(1, min(int(max_apply_group_count or 500), 500))
    raw_rows = rows[:row_limit]
    row_input_truncated = len(rows) > len(raw_rows)
    ready_rows: list[dict[str, Any]] = []
    pending_rows: list[dict[str, Any]] = []
    invalid_rows: list[dict[str, Any]] = []
    groups_by_key: dict[tuple[str, str], dict[str, Any]] = {}

    for index, row in enumerate(raw_rows):
        if not isinstance(row, dict):
            invalid_rows.append({"row_index": index, "status": "invalid", "error": "row_object_required"})
            continue

        pack_id = _safe_str(row.get("pack_id")).strip()
        pack_version = _safe_str(row.get("pack_version")).strip()
        capability_id = _safe_str(row.get("capability") or row.get("capability_id")).strip()
        proposal_id = _safe_str(row.get("proposal_id")).strip()
        evidence_refs_input = row.get("evidence_refs_input")
        evidence_refs_source = "operator_supplied_evidence_refs"
        if bool(use_suggested_evidence_refs) and _operator_proposal_evidence_refs_input_empty(evidence_refs_input):
            suggested_input = row.get("suggested_evidence_refs_input")
            if _operator_proposal_evidence_refs_input_empty(suggested_input):
                suggested_input = row.get("suggested_evidence_refs")
            if not _operator_proposal_evidence_refs_input_empty(suggested_input):
                evidence_refs_input = suggested_input
                evidence_refs_source = "suggested_local_artifact_refs"
        evidence_refs, parse_error = _parse_operator_proposal_evidence_refs_input(evidence_refs_input)
        base_row = {
            "row_index": index,
            "pack_id": pack_id,
            "pack_version": pack_version,
            "capability": capability_id,
            "proposal_id": proposal_id,
        }
        if not pack_id or not pack_version or not capability_id:
            invalid_rows.append({**base_row, "status": "invalid", "error": "pack_version_capability_required"})
            continue
        if (pack_id, pack_version, capability_id) not in candidate_keys:
            invalid_rows.append(
                {**base_row, "status": "invalid", "error": "row_not_current_operator_evidence_candidate"}
            )
            continue
        if parse_error:
            pending_rows.append({**base_row, "status": "pending_operator_input", "error": parse_error})
            continue

        ready = {
            **base_row,
            "status": "ready_for_preview",
            "evidence_refs": evidence_refs,
            "evidence_ref_count": len(evidence_refs),
            "evidence_refs_source": evidence_refs_source,
            "suggested_evidence_refs_used": evidence_refs_source == "suggested_local_artifact_refs",
            "claim_scope": "operator_supplied_friction_evidence_reference_not_independent_verification",
            "operator_supplied_evidence_not_independently_verified": True,
            "requires_future_proposal_review": True,
        }
        ready_rows.append(ready)
        group_key = (pack_id, pack_version)
        group = groups_by_key.setdefault(
            group_key,
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "capability_ids": [],
                "evidence_refs_by_capability": {},
                "row_indexes": [],
            },
        )
        group["capability_ids"].append(capability_id)
        refs_by_capability = group.get("evidence_refs_by_capability")
        if not isinstance(refs_by_capability, dict):
            refs_by_capability = {}
            group["evidence_refs_by_capability"] = refs_by_capability
        existing_refs = _unique_texts(refs_by_capability.get(capability_id), limit=50)
        refs_by_capability[capability_id] = _unique_texts([*existing_refs, *evidence_refs], limit=50)
        group["row_indexes"].append(index)

    apply_payload_groups: list[dict[str, Any]] = []
    for group in groups_by_key.values():
        capability_ids = _unique_texts(group.get("capability_ids"), limit=1000)
        row_indexes = [int(item) for item in group.get("row_indexes", []) if isinstance(item, int)]
        raw_refs_by_capability = (
            group.get("evidence_refs_by_capability")
            if isinstance(group.get("evidence_refs_by_capability"), dict)
            else {}
        )
        evidence_refs_by_capability: dict[str, list[str]] = {}
        for capability_id in capability_ids:
            refs = _unique_texts(raw_refs_by_capability.get(capability_id), limit=50)
            if refs:
                evidence_refs_by_capability[capability_id] = refs
        evidence_ref_count = sum(len(refs) for refs in evidence_refs_by_capability.values())
        apply_payload_groups.append(
            {
                "pack_id": _safe_str(group.get("pack_id")).strip(),
                "pack_version": _safe_str(group.get("pack_version")).strip(),
                "capability_count": len(capability_ids),
                "evidence_ref_count": evidence_ref_count,
                "shared_evidence_ref_count": 0,
                "capability_specific_evidence_ref_count": evidence_ref_count,
                "row_indexes": row_indexes[:100],
                "row_indexes_truncated": len(row_indexes) > 100,
                "capability_scoped_evidence_refs_supported": True,
                "preview_payload": {
                    "pack_ids": [_safe_str(group.get("pack_id")).strip()],
                    "capability_ids": capability_ids,
                    "evidence_refs": [],
                    "evidence_refs_by_capability": evidence_refs_by_capability,
                    "dry_run": True,
                    "max_pack_count": 1,
                    "max_total_capability_count": len(capability_ids),
                    "max_capability_count_per_pack": len(capability_ids),
                },
                "apply_payload_hint": {
                    "pack_ids": [_safe_str(group.get("pack_id")).strip()],
                    "capability_ids": capability_ids,
                    "evidence_refs": [],
                    "evidence_refs_by_capability": evidence_refs_by_capability,
                    "dry_run": True,
                    "dry_run_fingerprint_required": True,
                    "max_pack_count": 1,
                    "max_total_capability_count": len(capability_ids),
                    "max_capability_count_per_pack": len(capability_ids),
                },
                "preview_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_PREVIEW_ROUTE,
                "apply_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_APPLY_ROUTE,
            }
        )

    apply_payload_groups.sort(key=lambda item: (_safe_str(item.get("pack_id")), _safe_str(item.get("pack_version"))))
    apply_groups_truncated = len(apply_payload_groups) > apply_group_limit
    visible_groups = apply_payload_groups[:apply_group_limit]
    status = (
        "ready_for_operator_evidence_import_preview" if visible_groups else "no_operator_evidence_rows_ready_for_import"
    )
    sync_performed = bool(generated_plugin_sync_performed)
    return {
        "stage": "Stage 17 / Capability Economy",
        "status": status,
        "operator_evidence_intake_import_preview_ready": bool(visible_groups),
        "input_row_count": len(rows),
        "processed_row_count": len(raw_rows),
        "row_input_truncated": row_input_truncated,
        "ready_row_count": len(ready_rows),
        "pending_row_count": len(pending_rows),
        "invalid_row_count": len(invalid_rows),
        "use_suggested_evidence_refs": bool(use_suggested_evidence_refs),
        "suggested_evidence_refs_used_count": sum(
            1 for row in ready_rows if bool(row.get("suggested_evidence_refs_used"))
        ),
        "apply_group_count": len(apply_payload_groups),
        "apply_groups_truncated": apply_groups_truncated,
        "row_limit": row_limit,
        "apply_group_limit": apply_group_limit,
        "ready_rows": ready_rows[:100],
        "ready_rows_truncated": len(ready_rows) > 100,
        "pending_rows": pending_rows[:100],
        "pending_rows_truncated": len(pending_rows) > 100,
        "invalid_rows": invalid_rows[:100],
        "invalid_rows_truncated": len(invalid_rows) > 100,
        "apply_payload_groups": visible_groups,
        "source_proposal_evidence_plan": {
            "status": _safe_str(source_plan.get("status")).strip(),
            "candidate_capability_count": _count_value(source_plan.get("candidate_capability_count")),
            "proposal_evidence_missing_count": _count_value(source_plan.get("proposal_evidence_missing_count")),
            "proposal_evidence_ready_count": _count_value(source_plan.get("proposal_evidence_ready_count")),
            "proposal_review_missing_count": _count_value(source_plan.get("proposal_review_missing_count")),
            "next_smallest_truthful_gap": _safe_str(source_plan.get("next_smallest_truthful_gap")).strip(),
        },
        "routes": {
            "operator_intake_export_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_EXPORT_ROUTE,
            "operator_intake_import_preview_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_IMPORT_PREVIEW_ROUTE,
            "operator_intake_preview_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_PREVIEW_ROUTE,
            "operator_intake_apply_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_APPLY_ROUTE,
        },
        "requirements": {
            "operator_supplied_evidence_refs_required": True,
            "does_not_validate_evidence_truth": True,
            "no_synthetic_evidence": True,
            "dry_run_required_before_apply": True,
            "apply_requires_plugins_write_scope": True,
            "capability_scoped_evidence_refs_supported": True,
            "future_proposal_review_required": True,
            "suggested_local_artifact_refs_require_explicit_opt_in": True,
            "suggested_refs_do_not_validate_evidence_truth": True,
        },
        "governance": {
            "read_only": True,
            "operator_facing": True,
            "generated_plugin_registry_sync_performed": sync_performed,
            "does_not_mutate_registry": not sync_performed,
            "preview_only": True,
            "write_authority": False,
            "writes_registry_metadata": False,
            "writes_operator_evidence_metadata": False,
            "writes_proposals": False,
            "does_not_write_proposal_review_receipts": True,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
        },
        "next_smallest_truthful_gap": "stage17_capability_library_operator_proposal_evidence_refs",
    }


def _capability_library_operator_proposal_evidence_intake_audit_projection(
    *,
    registry: dict[str, Any],
    entries: list[dict[str, Any]],
    promotion_discipline: dict[str, Any],
    source_plan: dict[str, Any],
    generated_plugin_sync_performed: bool,
) -> dict[str, Any]:
    raw_packs = promotion_discipline.get("packs") if isinstance(promotion_discipline.get("packs"), list) else []
    ready_packs = [
        pack
        for pack in raw_packs
        if isinstance(pack, dict) and bool(pack.get("ready")) and _safe_str(pack.get("status")).strip() == "ready"
    ]
    audited_packs: list[dict[str, Any]] = []
    preview_remaining = _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_PLAN_PREVIEW_LIMIT
    recorded_pack_count = 0
    recorded_capability_count = 0
    evidence_ref_count = 0
    future_review_required_count = 0
    source_missing_count = _count_value(source_plan.get("proposal_evidence_missing_count"))
    source_ready_count = _count_value(source_plan.get("proposal_evidence_ready_count"))
    source_review_missing_count = _count_value(source_plan.get("proposal_review_missing_count"))

    for pack in ready_packs:
        pack_id = _safe_str(pack.get("pack_id")).strip()
        pack_version = _safe_str(pack.get("pack_version")).strip()
        pack_entries = _entries_for_capability_pack(entries, pack_id=pack_id, pack_version=pack_version)
        staged_ids = _unique_texts(
            [
                _safe_str(entry.get("capability")).strip()
                for entry in pack_entries
                if _safe_str(entry.get("status")).strip() == "staged"
            ],
            limit=10000,
        )
        if not staged_ids:
            continue

        capabilities: list[dict[str, Any]] = []
        for capability_id in staged_ids:
            plugin = _read_plugin(registry, capability_id)
            if plugin is None:
                continue
            meta = dict(plugin.get("meta") or {}) if isinstance(plugin.get("meta"), dict) else {}
            if (
                _safe_str(meta.get("proposal_evidence_link_source")).strip()
                != _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_SOURCE
            ):
                continue
            evidence_refs = _unique_texts(meta.get("proposal_evidence") or meta.get("evidence"), limit=50)
            if not evidence_refs:
                continue

            requires_future_review = bool(meta.get("proposal_evidence_operator_intake_requires_future_review"))
            if requires_future_review:
                future_review_required_count += 1
            capabilities.append(
                {
                    "capability": capability_id,
                    "status": _safe_str(plugin.get("status")).strip(),
                    "proposal_id": _safe_str(
                        meta.get("proposal_id")
                        or meta.get("forge_proposal_id")
                        or meta.get("proposal_evidence_artifact_proposal_id")
                    ).strip(),
                    "evidence_ref_count": len(evidence_refs),
                    "evidence_refs": evidence_refs[:10],
                    "evidence_refs_truncated": len(evidence_refs) > 10,
                    "claim_scope": _safe_str(meta.get("proposal_evidence_claim_scope")).strip(),
                    "operator_intake_actor": _safe_str(meta.get("proposal_evidence_operator_intake_actor")).strip(),
                    "operator_intake_reason": _safe_str(meta.get("proposal_evidence_operator_intake_reason")).strip(),
                    "operator_intake_ts": _count_value(meta.get("proposal_evidence_operator_intake_ts")),
                    "operator_intake_route": _safe_str(meta.get("proposal_evidence_operator_intake_route")).strip(),
                    "operator_supplied_evidence_not_independently_verified": True,
                    "requires_future_proposal_review": requires_future_review,
                    "writes_proposals": bool(meta.get("proposal_evidence_writes_proposals")),
                    "approval_claimed": bool(meta.get("proposal_evidence_approval_claimed")),
                }
            )

        if not capabilities:
            continue

        recorded_pack_count += 1
        recorded_capability_count += len(capabilities)
        pack_evidence_ref_count = sum(int(item.get("evidence_ref_count") or 0) for item in capabilities)
        evidence_ref_count += pack_evidence_ref_count

        if len(audited_packs) >= _CAPABILITY_LIBRARY_OPERATOR_SURFACE_PACK_PREVIEW_LIMIT:
            continue
        visible_capabilities = capabilities[:preview_remaining]
        preview_remaining = max(0, preview_remaining - len(visible_capabilities))
        audited_packs.append(
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "pack_name": _safe_str(pack.get("pack_name")).strip() or pack_id,
                "staged_capability_count": len(staged_ids),
                "recorded_capability_count": len(capabilities),
                "evidence_ref_count": pack_evidence_ref_count,
                "claim_scope": "operator_supplied_friction_evidence_reference_not_independent_verification",
                "capabilities": visible_capabilities,
                "capabilities_truncated": len(visible_capabilities) < len(capabilities),
            }
        )

    source_next_gap = _safe_str(source_plan.get("next_smallest_truthful_gap")).strip()
    if recorded_capability_count and source_missing_count:
        status = "operator_evidence_refs_partially_recorded"
        next_gap = "stage17_capability_library_operator_proposal_evidence_refs"
    elif recorded_capability_count:
        status = "operator_evidence_refs_recorded"
        next_gap = source_next_gap or (
            "stage17_capability_library_proposal_review_apply"
            if source_review_missing_count
            else "stage17_capability_library_explicit_promotion_apply"
        )
    elif source_missing_count:
        status = "no_operator_evidence_refs_recorded"
        next_gap = "stage17_capability_library_operator_proposal_evidence_refs"
    else:
        status = "no_operator_evidence_refs_recorded"
        next_gap = source_next_gap

    sync_performed = bool(generated_plugin_sync_performed)
    return {
        "stage": "Stage 17 / Capability Economy",
        "status": status,
        "operator_evidence_intake_audit_ready": bool(recorded_capability_count),
        "recorded_pack_count": recorded_pack_count,
        "recorded_capability_count": recorded_capability_count,
        "evidence_ref_count": evidence_ref_count,
        "future_review_required_count": future_review_required_count,
        "source_proposal_evidence_plan": {
            "status": _safe_str(source_plan.get("status")).strip(),
            "candidate_capability_count": _count_value(source_plan.get("candidate_capability_count")),
            "proposal_evidence_missing_count": source_missing_count,
            "proposal_evidence_ready_count": source_ready_count,
            "proposal_review_missing_count": source_review_missing_count,
            "next_smallest_truthful_gap": source_next_gap,
        },
        "packs": audited_packs,
        "packs_truncated": recorded_pack_count > len(audited_packs),
        "capability_preview_limit": _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_PLAN_PREVIEW_LIMIT,
        "routes": {
            "proposal_evidence_plan_route": "/plugins/capabilities/library/proposal-evidence/plan",
            "operator_intake_checklist_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_CHECKLIST_ROUTE,
            "operator_intake_audit_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_AUDIT_ROUTE,
            "operator_intake_apply_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_APPLY_ROUTE,
            "operator_intake_preview_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_PREVIEW_ROUTE,
            "operator_intake_import_preview_route": (
                _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_IMPORT_PREVIEW_ROUTE
            ),
            "proposal_review_plan_route": "/plugins/capabilities/library/proposal-review/plan",
            "promotion_plan_route": "/plugins/capabilities/library/promotion/plan",
        },
        "requirements": {
            "operator_supplied_evidence_not_independently_verified": True,
            "future_proposal_review_required": True,
            "audit_only": True,
            "no_synthetic_evidence": True,
            "does_not_validate_evidence_truth": True,
            "proposal_evidence_required_before_proposal_review": True,
        },
        "governance": {
            "read_only": True,
            "operator_facing": True,
            "generated_plugin_registry_sync_performed": sync_performed,
            "does_not_mutate_registry": not sync_performed,
            "apply_requires_plugins_write_scope": True,
            "apply_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_APPLY_ROUTE,
            "writes_registry_metadata": False,
            "writes_proposals": False,
            "does_not_write_proposal_review_receipts": True,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
        },
        "next_smallest_truthful_gap": next_gap,
    }


def _capability_library_operator_proposal_evidence_intake_plan_fingerprint(
    *,
    planned: list[dict[str, Any]],
    evidence_refs: list[str],
    evidence_refs_by_capability: dict[str, list[str]] | None = None,
) -> str:
    refs_by_capability = evidence_refs_by_capability or {}
    canonical_packs: list[dict[str, Any]] = []
    for pack in planned:
        raw_capabilities = pack.get("capabilities") if isinstance(pack.get("capabilities"), list) else []
        capabilities = [
            {
                "capability": _safe_str(capability.get("capability")).strip(),
                "proposal_id": _safe_str(capability.get("proposal_id")).strip(),
                "evidence_refs": _operator_proposal_evidence_refs_for_capability(
                    evidence_refs,
                    refs_by_capability,
                    _safe_str(capability.get("capability")).strip(),
                ),
            }
            for capability in raw_capabilities
            if isinstance(capability, dict)
        ]
        capabilities.sort(key=lambda item: (item["capability"], item["proposal_id"]))
        canonical_packs.append(
            {
                "pack_id": _safe_str(pack.get("pack_id")).strip(),
                "pack_version": _safe_str(pack.get("pack_version")).strip(),
                "capabilities": capabilities,
            }
        )
    canonical_packs.sort(key=lambda item: (item["pack_id"], item["pack_version"]))
    body = {
        "contract": "stage17_operator_proposal_evidence_intake_dry_run_v1",
        "claim_scope": "operator_supplied_friction_evidence_reference_not_independent_verification",
        "evidence_refs": _unique_texts(evidence_refs, limit=50),
        "evidence_refs_by_capability": {
            capability_id: _unique_texts(refs, limit=50) for capability_id, refs in sorted(refs_by_capability.items())
        },
        "planned": canonical_packs,
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _operator_proposal_evidence_refs_by_capability(raw: Any) -> dict[str, list[str]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("evidence refs by capability must be an object")
    out: dict[str, list[str]] = {}
    for raw_capability_id, raw_refs in raw.items():
        capability_id = _validate_plugin_id(_safe_str(raw_capability_id).strip())
        refs = _unique_texts(raw_refs, limit=50)
        if refs:
            out[capability_id] = refs
        if len(out) >= 1000:
            break
    return out


def _operator_proposal_evidence_refs_for_capability(
    shared_refs: list[str],
    refs_by_capability: dict[str, list[str]],
    capability_id: str,
) -> list[str]:
    return _unique_texts([*shared_refs, *refs_by_capability.get(capability_id, [])], limit=50)


def _operator_proposal_evidence_planned_capability_ids(planned: list[dict[str, Any]]) -> list[str]:
    capability_ids: list[str] = []
    for pack in planned:
        raw_capabilities = pack.get("capabilities") if isinstance(pack.get("capabilities"), list) else []
        for capability in raw_capabilities:
            if not isinstance(capability, dict):
                continue
            capability_id = _safe_str(capability.get("capability")).strip()
            if capability_id and capability_id not in capability_ids:
                capability_ids.append(capability_id)
    return capability_ids


def _operator_proposal_evidence_ref_count_for_planned(
    planned: list[dict[str, Any]],
    shared_refs: list[str],
    refs_by_capability: dict[str, list[str]],
) -> int:
    return sum(
        len(_operator_proposal_evidence_refs_for_capability(shared_refs, refs_by_capability, capability_id))
        for capability_id in _operator_proposal_evidence_planned_capability_ids(planned)
    )


def _capability_library_operator_proposal_evidence_intake_governance(
    *,
    route_path: str,
    writes_registry_metadata: bool,
    scope: str = "",
    read_only: bool = False,
    generated_plugin_registry_sync_performed: bool = False,
    preview_only: bool = False,
) -> dict[str, object]:
    governance: dict[str, object] = {
        "route": route_path,
        "writes_registry_metadata": writes_registry_metadata,
        "writes_proposals": False,
        "dry_run_required_before_apply": True,
        "capability_scoped_evidence_refs_supported": True,
        "operator_supplied_evidence_not_independently_verified": True,
        "does_not_approve_proposals": True,
        "does_not_promote_capabilities": True,
        "does_not_enable_capabilities": True,
        "does_not_execute_capabilities": True,
        "promotion_authority": False,
        "execution_authority": False,
        "approval_authority": False,
        "memory_write": False,
    }
    if scope:
        governance["scope"] = scope
    if read_only:
        governance.update(
            {
                "read_only": True,
                "preview_only": preview_only,
                "write_authority": False,
                "apply_requires_plugins_write_scope": True,
                "apply_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_APPLY_ROUTE,
                "writes_operator_evidence_metadata": False,
                "does_not_mutate_operator_evidence": True,
                "dry_run_fingerprint_does_not_authorize_without_plugins_write": True,
                "generated_plugin_registry_sync_performed": generated_plugin_registry_sync_performed,
            }
        )
    return governance


def _prepare_capability_library_operator_proposal_evidence_intake_plan(
    *,
    payload: CapabilityLibraryOperatorProposalEvidenceIntakeApplyIn,
    planned_writes_registry_metadata: bool,
) -> dict[str, Any]:
    evidence_refs = _unique_texts(payload.evidence_refs, limit=50)
    try:
        evidence_refs_by_capability = _operator_proposal_evidence_refs_by_capability(
            payload.evidence_refs_by_capability
        )
    except Exception:
        return {
            "ok": False,
            "status": "blocked",
            "error": "invalid_evidence_refs_by_capability",
            "evidence_refs": evidence_refs,
        }
    if not evidence_refs and not evidence_refs_by_capability:
        return {
            "ok": False,
            "status": "blocked",
            "error": "operator_evidence_refs_required",
            "evidence_refs": evidence_refs,
        }

    safe_max_pack_count = max(1, min(int(payload.max_pack_count or 10), 50))
    safe_max_total_capability_count = max(1, min(int(payload.max_total_capability_count or 1000), 10000))
    safe_max_capability_count_per_pack = max(1, min(int(payload.max_capability_count_per_pack or 500), 500))
    try:
        selected_pack_ids = {_validate_plugin_id(raw_id) for raw_id in _unique_texts(payload.pack_ids, limit=100)}
        selected_capability_ids = {
            _validate_plugin_id(raw_id) for raw_id in _unique_texts(payload.capability_ids, limit=1000)
        }
    except Exception:
        return {
            "ok": False,
            "status": "blocked",
            "error": "invalid_selector_id",
            "evidence_refs": evidence_refs,
        }

    registry = _load_registry()
    synced = _sync_generated_plugins(registry)
    catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
    runtime_catalog = _read_runtime_catalog_payload(catalog)
    marketplace = marketplace_from_plugin_catalog(runtime_catalog)
    entries = list(marketplace.catalog())
    available_proposals = _available_capability_pack_proposals()
    available_validation_receipts = _available_capability_pack_validation_receipts()
    available_promotion_receipts = _available_capability_pack_promotion_receipts()
    promotion_discipline = analyze_capability_pack_promotion_discipline(
        entries,
        available_proposal_ids=available_proposals["ids"],
        available_validation_receipt_ids=available_validation_receipts["ids"],
        available_promotion_receipt_ids=available_promotion_receipts["ids"],
        operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
    )
    before = _capability_library_proposal_evidence_plan_projection(
        registry=registry,
        entries=entries,
        promotion_discipline=promotion_discipline,
        generated_plugin_sync_performed=bool(synced),
    )
    candidates = _capability_library_operator_proposal_evidence_intake_candidates(
        registry=registry,
        entries=entries,
        promotion_discipline=promotion_discipline,
        selected_pack_ids=selected_pack_ids,
        selected_capability_ids=selected_capability_ids,
    )
    if not candidates:
        return {
            "ok": True,
            "status": "no_candidates",
            "evidence_refs": evidence_refs,
            "planned_pack_count": 0,
            "recorded_pack_count": 0,
            "recorded_capability_count": 0,
            "before": before,
            "generated_plugin_registry_sync_performed": bool(synced),
        }
    if len(candidates) > safe_max_pack_count:
        return {
            "ok": False,
            "status": "blocked",
            "error": "operator_evidence_intake_pack_limit_exceeded",
            "candidate_total": len(candidates),
            "limit": safe_max_pack_count,
            "before": before,
            "evidence_refs": evidence_refs,
            "generated_plugin_registry_sync_performed": bool(synced),
        }

    prepared: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    total_capability_count = 0
    for pack in candidates:
        raw_capabilities = pack.get("capabilities") if isinstance(pack.get("capabilities"), list) else []
        capabilities = [capability for capability in raw_capabilities if isinstance(capability, dict)]
        capability_count = len(capabilities)
        if capability_count <= 0:
            skipped.append(
                {
                    "pack_id": _safe_str(pack.get("pack_id")).strip(),
                    "pack_version": _safe_str(pack.get("pack_version")).strip(),
                    "error": "capability_ids_required",
                }
            )
            continue
        if capability_count > safe_max_capability_count_per_pack:
            skipped.append(
                {
                    "pack_id": _safe_str(pack.get("pack_id")).strip(),
                    "pack_version": _safe_str(pack.get("pack_version")).strip(),
                    "error": "candidate_capability_limit_exceeded",
                    "capability_count": capability_count,
                    "limit": safe_max_capability_count_per_pack,
                }
            )
            continue
        total_capability_count += capability_count
        prepared.append(pack)
    if total_capability_count > safe_max_total_capability_count:
        return {
            "ok": False,
            "status": "blocked",
            "error": "total_capability_limit_exceeded",
            "capability_count": total_capability_count,
            "limit": safe_max_total_capability_count,
            "before": before,
            "evidence_refs": evidence_refs,
            "generated_plugin_registry_sync_performed": bool(synced),
        }

    planned = [
        {
            "pack_id": _safe_str(item.get("pack_id")).strip(),
            "pack_version": _safe_str(item.get("pack_version")).strip(),
            "pack_name": _safe_str(item.get("pack_name")).strip(),
            "capability_count": len(item.get("capabilities") if isinstance(item.get("capabilities"), list) else []),
            "evidence_ref_count": sum(
                len(
                    _operator_proposal_evidence_refs_for_capability(
                        evidence_refs,
                        evidence_refs_by_capability,
                        _safe_str(capability.get("capability")).strip(),
                    )
                )
                for capability in (item.get("capabilities") if isinstance(item.get("capabilities"), list) else [])
                if isinstance(capability, dict)
            ),
            "shared_evidence_ref_count": len(evidence_refs),
            "capability_specific_evidence_ref_count": sum(
                len(evidence_refs_by_capability.get(_safe_str(capability.get("capability")).strip(), []))
                for capability in (item.get("capabilities") if isinstance(item.get("capabilities"), list) else [])
                if isinstance(capability, dict)
            ),
            "claim_scope": "operator_supplied_friction_evidence_reference_not_independent_verification",
            "capabilities": [
                {
                    "capability": _safe_str(capability.get("capability")).strip(),
                    "proposal_id": _safe_str(capability.get("proposal_id")).strip(),
                    "missing_requirements": _unique_texts(capability.get("missing_requirements"), limit=25),
                    "evidence_ref_count": len(
                        _operator_proposal_evidence_refs_for_capability(
                            evidence_refs,
                            evidence_refs_by_capability,
                            _safe_str(capability.get("capability")).strip(),
                        )
                    ),
                    "shared_evidence_ref_count": len(evidence_refs),
                    "capability_specific_evidence_ref_count": len(
                        evidence_refs_by_capability.get(_safe_str(capability.get("capability")).strip(), [])
                    ),
                }
                for capability in (item.get("capabilities") if isinstance(item.get("capabilities"), list) else [])
                if isinstance(capability, dict)
            ],
            "writes_registry_metadata": planned_writes_registry_metadata,
            "writes_proposals": False,
            "approves_proposals": False,
            "promotes_capabilities": False,
            "enables_capabilities": False,
        }
        for item in prepared
    ]
    planned_capability_ids = _operator_proposal_evidence_planned_capability_ids(planned)
    unplanned_ref_ids = sorted(set(evidence_refs_by_capability) - set(planned_capability_ids))
    if unplanned_ref_ids:
        return {
            "ok": False,
            "status": "blocked",
            "error": "operator_evidence_refs_capability_not_planned",
            "unplanned_capability_ids": unplanned_ref_ids[:50],
            "unplanned_capability_ids_truncated": len(unplanned_ref_ids) > 50,
            "planned_capability_count": len(planned_capability_ids),
            "before": before,
            "evidence_refs": evidence_refs,
            "generated_plugin_registry_sync_performed": bool(synced),
        }
    missing_ref_capability_ids = [
        capability_id
        for capability_id in planned_capability_ids
        if not _operator_proposal_evidence_refs_for_capability(
            evidence_refs,
            evidence_refs_by_capability,
            capability_id,
        )
    ]
    if missing_ref_capability_ids:
        return {
            "ok": False,
            "status": "blocked",
            "error": "operator_evidence_refs_required_for_capabilities",
            "missing_capability_ids": missing_ref_capability_ids[:50],
            "missing_capability_ids_truncated": len(missing_ref_capability_ids) > 50,
            "planned_capability_count": len(planned_capability_ids),
            "before": before,
            "evidence_refs": evidence_refs,
            "generated_plugin_registry_sync_performed": bool(synced),
        }
    if not prepared:
        return {
            "ok": True,
            "status": "no_supported_operator_evidence_intake",
            "evidence_refs": evidence_refs,
            "planned_pack_count": 0,
            "recorded_pack_count": 0,
            "recorded_capability_count": 0,
            "skipped": skipped,
            "before": before,
            "generated_plugin_registry_sync_performed": bool(synced),
        }

    dry_run_fingerprint = _capability_library_operator_proposal_evidence_intake_plan_fingerprint(
        planned=planned,
        evidence_refs=evidence_refs,
        evidence_refs_by_capability=evidence_refs_by_capability,
    )
    return {
        "ok": True,
        "status": "planned",
        "evidence_refs": evidence_refs,
        "registry": registry,
        "before": before,
        "prepared": prepared,
        "planned": planned,
        "skipped": skipped,
        "dry_run_fingerprint": dry_run_fingerprint,
        "planned_pack_count": len(planned),
        "planned_capability_count": sum(int(item.get("capability_count") or 0) for item in planned),
        "evidence_ref_count": _operator_proposal_evidence_ref_count_for_planned(
            planned,
            evidence_refs,
            evidence_refs_by_capability,
        ),
        "shared_evidence_ref_count": len(evidence_refs),
        "capability_specific_evidence_ref_count": sum(
            len(evidence_refs_by_capability.get(capability_id, [])) for capability_id in planned_capability_ids
        ),
        "evidence_refs_by_capability": evidence_refs_by_capability,
        "generated_plugin_registry_sync_performed": bool(synced),
    }


def _capability_library_operator_proposal_evidence_intake_problem_response(
    *,
    plan: dict[str, Any],
    route_path: str,
    scope: str = "",
    read_only: bool = False,
    preview_only: bool = False,
) -> dict[str, object]:
    response: dict[str, object] = {
        "ok": bool(plan.get("ok")),
        "applied": False,
        "status": _safe_str(plan.get("status")).strip() or "blocked",
    }
    for key in (
        "error",
        "candidate_total",
        "limit",
        "capability_count",
        "planned_pack_count",
        "planned_capability_count",
        "recorded_pack_count",
        "recorded_capability_count",
        "missing_capability_ids",
        "missing_capability_ids_truncated",
        "unplanned_capability_ids",
        "unplanned_capability_ids_truncated",
        "skipped",
        "before",
    ):
        if key in plan:
            response[key] = plan[key]
    response["governance"] = _capability_library_operator_proposal_evidence_intake_governance(
        route_path=route_path,
        scope=scope,
        read_only=read_only,
        preview_only=preview_only,
        writes_registry_metadata=False,
        generated_plugin_registry_sync_performed=bool(plan.get("generated_plugin_registry_sync_performed")),
    )
    return response


def _record_capability_library_operator_proposal_evidence_intake_batch(
    *,
    registry: dict[str, Any],
    prepared: list[dict[str, Any]],
    evidence_refs: list[str],
    evidence_refs_by_capability: dict[str, list[str]] | None = None,
    payload: CapabilityLibraryOperatorProposalEvidenceIntakeApplyIn,
    route_path: str,
    update_runtime_catalog: bool = True,
) -> dict[str, list[dict[str, Any]]]:
    recorded_ts = _now_s()
    recorded: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    changed = False
    actor = redact_governed_value(_safe_str(payload.actor).strip())
    reason = redact_governed_value(_safe_str(payload.reason).strip() or "stage17_operator_proposal_evidence_intake")
    refs_by_capability = evidence_refs_by_capability or {}

    for item in prepared:
        pack_id = _safe_str(item.get("pack_id")).strip()
        pack_version = _safe_str(item.get("pack_version")).strip()
        raw_capabilities = item.get("capabilities") if isinstance(item.get("capabilities"), list) else []
        capabilities = [capability for capability in raw_capabilities if isinstance(capability, dict)]
        changed_capability_ids: list[str] = []
        blocked_capabilities: list[dict[str, Any]] = []

        for capability in capabilities:
            capability_id = _safe_str(capability.get("capability")).strip()
            proposal_id = _safe_str(capability.get("proposal_id")).strip()
            current = _read_plugin(registry, capability_id)
            if current is None:
                blocked_capabilities.append({"capability": capability_id, "error": "capability_not_found"})
                continue
            if not proposal_id:
                blocked_capabilities.append({"capability": capability_id, "error": "proposal_id_required"})
                continue
            capability_evidence_refs = _operator_proposal_evidence_refs_for_capability(
                evidence_refs,
                refs_by_capability,
                capability_id,
            )
            if not capability_evidence_refs:
                blocked_capabilities.append({"capability": capability_id, "error": "operator_evidence_refs_required"})
                continue
            meta = dict(current.get("meta") or {}) if isinstance(current.get("meta"), dict) else {}
            existing = _unique_texts(meta.get("proposal_evidence") or meta.get("evidence"), limit=50)
            merged = _merge_proposal_evidence(existing, capability_evidence_refs)
            if merged == existing:
                continue

            meta["proposal_evidence"] = merged
            meta["proposal_evidence_link_source"] = _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_SOURCE
            meta["proposal_evidence_claim_scope"] = (
                "operator_supplied_friction_evidence_reference_not_independent_verification"
            )
            meta["proposal_evidence_operator_intake_actor"] = actor
            meta["proposal_evidence_operator_intake_reason"] = reason
            meta["proposal_evidence_operator_intake_ts"] = recorded_ts
            meta["proposal_evidence_operator_intake_route"] = route_path
            meta["proposal_evidence_operator_intake_requires_future_review"] = True
            meta["proposal_evidence_artifact_proposal_id"] = proposal_id
            meta["proposal_evidence_writes_proposals"] = False
            meta["proposal_evidence_approval_claimed"] = False
            current["meta"] = meta
            current["updated_ts"] = recorded_ts
            _write_plugin(registry, _normalize_plugin_record(capability_id, current))
            changed = True
            changed_capability_ids.append(capability_id)

        if blocked_capabilities:
            failed.append(
                {
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "status": "blocked",
                    "error": "operator_proposal_evidence_intake_blocked",
                    "capabilities": blocked_capabilities,
                }
            )
        recorded.append(
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "pack_name": _safe_str(item.get("pack_name")).strip() or pack_id,
                "capability_count": len(capabilities),
                "changed_capability_count": len(changed_capability_ids),
                "changed_capability_ids": changed_capability_ids[:50],
                "changed_capability_ids_truncated": len(changed_capability_ids) > 50,
                "evidence_ref_count": sum(
                    len(
                        _operator_proposal_evidence_refs_for_capability(
                            evidence_refs,
                            refs_by_capability,
                            _safe_str(capability.get("capability")).strip(),
                        )
                    )
                    for capability in capabilities
                ),
                "shared_evidence_ref_count": len(evidence_refs),
                "capability_specific_evidence_ref_count": sum(
                    len(refs_by_capability.get(_safe_str(capability.get("capability")).strip(), []))
                    for capability in capabilities
                ),
                "claim_scope": "operator_supplied_friction_evidence_reference_not_independent_verification",
                "writes_registry_metadata": bool(changed_capability_ids),
                "writes_proposals": False,
                "approves_proposals": False,
                "promotes_capabilities": False,
                "enables_capabilities": False,
                "status": "recorded" if changed_capability_ids else "unchanged",
            }
        )

    if changed:
        if update_runtime_catalog:
            _save_registry_and_catalog(registry)
        else:
            _save_registry(registry)
    return {"recorded": recorded, "failed": failed}


def _capability_library_proposal_review_plan_projection(
    *,
    registry: dict[str, Any],
    entries: list[dict[str, Any]],
    promotion_discipline: dict[str, Any],
    generated_plugin_sync_performed: bool,
) -> dict[str, Any]:
    sync_performed = bool(generated_plugin_sync_performed)
    raw_packs = promotion_discipline.get("packs") if isinstance(promotion_discipline.get("packs"), list) else []
    ready_packs = [
        pack
        for pack in raw_packs
        if isinstance(pack, dict) and bool(pack.get("ready")) and _safe_str(pack.get("status")).strip() == "ready"
    ]
    planned_packs: list[dict[str, Any]] = []
    preview_remaining = _CAPABILITY_LIBRARY_PROPOSAL_REVIEW_PLAN_PREVIEW_LIMIT
    candidate_pack_count = 0
    candidate_capability_count = 0
    proposal_review_missing_count = 0
    approved_proposal_review_count = 0
    reviewable_capability_count = 0
    blocked_before_review_capability_count = 0
    missing_requirement_counts: dict[str, int] = {}
    unique_proposal_ids: set[str] = set()
    reviewable_proposal_ids: set[str] = set()
    blocked_proposal_ids: set[str] = set()
    approved_proposal_review_ids: set[str] = set()

    for pack in ready_packs:
        pack_id = _safe_str(pack.get("pack_id")).strip()
        pack_version = _safe_str(pack.get("pack_version")).strip()
        pack_entries = _entries_for_capability_pack(entries, pack_id=pack_id, pack_version=pack_version)
        staged_ids = _unique_texts(
            [
                _safe_str(entry.get("capability")).strip()
                for entry in pack_entries
                if _safe_str(entry.get("status")).strip() == "staged"
            ],
            limit=10000,
        )
        if not staged_ids:
            continue

        candidate_pack_count += 1
        include_pack_preview = len(planned_packs) < _CAPABILITY_LIBRARY_OPERATOR_SURFACE_PACK_PREVIEW_LIMIT
        pack_reviewable_count = 0
        pack_blocked_before_review_count = 0
        pack_approved_review_count = 0
        pack_proposals: list[dict[str, Any]] = []

        for capability_id in staged_ids:
            candidate_capability_count += 1
            plugin = _read_plugin(registry, capability_id)
            if plugin is None:
                readiness = {
                    "ready": False,
                    "missing_requirements": ["plugin_record"],
                    "requirements": {"plugin_record": False},
                    "evidence": {},
                }
            else:
                readiness = _plugin_promotion_readiness(
                    capability_id,
                    plugin,
                    PluginToggleIn(id=capability_id, reason="capability_library_proposal_review_plan"),
                )

            missing = _unique_texts(readiness.get("missing_requirements"), limit=25)
            evidence = readiness.get("evidence") if isinstance(readiness.get("evidence"), dict) else {}
            proposal_id = _safe_str(evidence.get("proposal_id")).strip()
            proposal_review_status = _safe_str(evidence.get("proposal_review_status")).strip()
            proposal_review_receipt_id = _safe_str(evidence.get("proposal_review_receipt_id")).strip()
            blockers_before_review = [requirement for requirement in missing if requirement != "proposal_review"]
            proposal_review_missing = "proposal_review" in missing
            approved_review = proposal_review_status == "approved" and bool(proposal_review_receipt_id)
            reviewable = proposal_review_missing and bool(proposal_id) and not blockers_before_review

            if proposal_id:
                unique_proposal_ids.add(proposal_id)
            for requirement in missing:
                missing_requirement_counts[requirement] = missing_requirement_counts.get(requirement, 0) + 1
            if proposal_review_missing:
                proposal_review_missing_count += 1
            if approved_review:
                approved_proposal_review_count += 1
                pack_approved_review_count += 1
                if proposal_id:
                    approved_proposal_review_ids.add(proposal_id)
            elif reviewable:
                reviewable_capability_count += 1
                pack_reviewable_count += 1
                reviewable_proposal_ids.add(proposal_id)
            if blockers_before_review:
                blocked_before_review_capability_count += 1
                pack_blocked_before_review_count += 1
                if proposal_id:
                    blocked_proposal_ids.add(proposal_id)

            if include_pack_preview and preview_remaining > 0:
                pack_proposals.append(
                    {
                        "capability": capability_id,
                        "status": _safe_str(plugin.get("status") if isinstance(plugin, dict) else "missing").strip(),
                        "proposal_id": proposal_id,
                        "proposal_review_status": proposal_review_status,
                        "proposal_review_receipt_id": proposal_review_receipt_id,
                        "proposal_review_missing": proposal_review_missing,
                        "review_ready": reviewable,
                        "approved_review": approved_review,
                        "missing_requirements": missing,
                        "blockers_before_review": blockers_before_review,
                        "proposal_review_route": "/forge/proposals/decision",
                        "proposal_review_would_write_receipt": True,
                        "proposal_review_would_promote_capability": False,
                        "proposal_review_would_enable_capability": False,
                    }
                )
                preview_remaining -= 1

        if include_pack_preview:
            planned_packs.append(
                {
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "pack_name": _safe_str(pack.get("pack_name")).strip(),
                    "staged_capability_count": len(staged_ids),
                    "reviewable_capability_count": pack_reviewable_count,
                    "blocked_before_review_capability_count": pack_blocked_before_review_count,
                    "approved_proposal_review_count": pack_approved_review_count,
                    "proposals": pack_proposals,
                    "proposals_truncated": len(pack_proposals) < len(staged_ids),
                }
            )

    discipline_blocked_pack_count = _count_value(promotion_discipline.get("blocked_pack_count"))
    if discipline_blocked_pack_count:
        status = "blocked"
        next_gap = (
            _safe_str(promotion_discipline.get("next_smallest_truthful_gap")).strip()
            or "stage17_capability_pack_promotion_rules"
        )
    elif not candidate_capability_count:
        status = "no_staged_promotion_candidates"
        next_gap = "stage17_capability_library_promotion_receipts"
    elif blocked_before_review_capability_count:
        status = "blocked"
        next_gap = "stage17_capability_library_promotion_readiness"
    elif reviewable_capability_count:
        status = "ready_for_proposal_review"
        next_gap = "stage17_capability_library_proposal_review_apply"
    elif proposal_review_missing_count == 0:
        status = "proposal_review_complete"
        next_gap = "stage17_capability_library_explicit_promotion_apply"
    else:
        status = "blocked"
        next_gap = "stage17_capability_library_proposal_review"

    return {
        "stage": "Stage 17 / Capability Economy",
        "status": status,
        **_stage17_projection_evidence(
            projection_scope="full_library",
            global_counts_included=True,
            generated_plugin_sync_performed=sync_performed,
        ),
        "proposal_review_plan_ready": status == "ready_for_proposal_review",
        "pack_total": _count_value(promotion_discipline.get("pack_total")),
        "ready_pack_count": _count_value(promotion_discipline.get("ready_pack_count")),
        "blocked_pack_count": discipline_blocked_pack_count,
        "candidate_pack_count": candidate_pack_count,
        "candidate_capability_count": candidate_capability_count,
        "unique_proposal_count": len(unique_proposal_ids),
        "proposal_review_missing_count": proposal_review_missing_count,
        "approved_proposal_review_count": approved_proposal_review_count,
        "reviewable_capability_count": reviewable_capability_count,
        "reviewable_proposal_count": len(reviewable_proposal_ids),
        "blocked_before_review_capability_count": blocked_before_review_capability_count,
        "blocked_proposal_count": len(blocked_proposal_ids),
        "approved_proposal_count": len(approved_proposal_review_ids),
        "missing_requirement_counts": missing_requirement_counts,
        "packs": planned_packs,
        "packs_truncated": candidate_pack_count > len(planned_packs),
        "proposal_preview_limit": _CAPABILITY_LIBRARY_PROPOSAL_REVIEW_PLAN_PREVIEW_LIMIT,
        "routes": {
            "promotion_plan_route": "/plugins/capabilities/library/promotion/plan",
            "proposal_evidence_plan_route": "/plugins/capabilities/library/proposal-evidence/plan",
            "proposal_review_apply_route": _CAPABILITY_LIBRARY_PROPOSAL_REVIEW_APPLY_ROUTE,
            "proposal_review_route": "/forge/proposals/decision",
            "proposal_reviews_route": "/forge/proposal_reviews/list",
            "promotion_readiness_route": "/forge/promotion_readiness/list",
            "promotion_route": "/plugins/enable",
        },
        "requirements": {
            "derived_from_capability_library_promotion_plan": True,
            "uses_existing_plugin_promotion_readiness": True,
            "proposal_id_required_before_review": True,
            "proposal_evidence_required_before_review": True,
            "tests_required_before_review": True,
            "docs_required_before_review": True,
            "risk_tier_required_before_review": True,
            "pack_operator_review_required_when_declared": True,
            "proposal_review_uses_forge_decision_receipt_schema": True,
            "bulk_proposal_review_apply_requires_dry_run_fingerprint": True,
            "proposal_review_does_not_promote_or_enable_capabilities": True,
            "explicit_operator_action_required": True,
            "no_auto_approval": True,
        },
        "governance": {
            "read_only": True,
            "operator_facing": True,
            "generated_plugin_registry_sync_performed": sync_performed,
            "does_not_mutate_registry": not sync_performed,
            "does_not_write_receipts": True,
            "does_not_write_proposal_review_receipts": True,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "proposal_review_authority": False,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
        },
        "next_smallest_truthful_gap": next_gap,
    }


def _capability_library_proposal_review_apply_readiness_projection(
    *,
    proposal_review_plan: dict[str, Any],
    proposal_evidence_plan: dict[str, Any],
    operator_evidence_audit: dict[str, Any],
    generated_plugin_sync_performed: bool,
) -> dict[str, Any]:
    reviewable_capability_count = _count_value(proposal_review_plan.get("reviewable_capability_count"))
    proposal_review_missing_count = _count_value(proposal_review_plan.get("proposal_review_missing_count"))
    blocked_before_review_count = _count_value(proposal_review_plan.get("blocked_before_review_capability_count"))
    approved_proposal_review_count = _count_value(proposal_review_plan.get("approved_proposal_review_count"))
    proposal_evidence_missing_count = _count_value(proposal_evidence_plan.get("proposal_evidence_missing_count"))
    proposal_evidence_ready_count = _count_value(proposal_evidence_plan.get("proposal_evidence_ready_count"))
    operator_recorded_capability_count = _count_value(operator_evidence_audit.get("recorded_capability_count"))
    proposal_review_plan_ready = bool(proposal_review_plan.get("proposal_review_plan_ready"))
    apply_ready = proposal_review_plan_ready and reviewable_capability_count > 0

    if apply_ready:
        status = "ready_for_proposal_review_apply"
        next_gap = "stage17_capability_library_proposal_review_apply"
    elif proposal_evidence_missing_count:
        status = "blocked_on_operator_evidence_refs"
        next_gap = (
            _safe_str(operator_evidence_audit.get("next_smallest_truthful_gap")).strip()
            or "stage17_capability_library_operator_proposal_evidence_refs"
        )
    elif blocked_before_review_count:
        status = "blocked_before_proposal_review"
        next_gap = _safe_str(proposal_review_plan.get("next_smallest_truthful_gap")).strip()
    elif proposal_review_missing_count == 0 and approved_proposal_review_count:
        status = "proposal_review_complete"
        next_gap = "stage17_capability_library_explicit_promotion_apply"
    else:
        status = "blocked"
        next_gap = _safe_str(proposal_review_plan.get("next_smallest_truthful_gap")).strip()

    raw_packs = proposal_review_plan.get("packs")
    review_packs = [pack for pack in raw_packs if isinstance(pack, dict)] if isinstance(raw_packs, list) else []
    ready_pack_count = sum(1 for pack in review_packs if _count_value(pack.get("reviewable_capability_count")) > 0)
    blocked_pack_count = sum(
        1 for pack in review_packs if _count_value(pack.get("blocked_before_review_capability_count")) > 0
    )
    sync_performed = bool(generated_plugin_sync_performed)

    return {
        "stage": "Stage 17 / Capability Economy",
        "status": status,
        "proposal_review_apply_ready": apply_ready,
        "reviewable_pack_count": ready_pack_count,
        "blocked_pack_count": blocked_pack_count,
        "reviewable_capability_count": reviewable_capability_count,
        "proposal_review_missing_count": proposal_review_missing_count,
        "blocked_before_review_capability_count": blocked_before_review_count,
        "approved_proposal_review_count": approved_proposal_review_count,
        "source_proposal_evidence_plan": {
            "status": _safe_str(proposal_evidence_plan.get("status")).strip(),
            "proposal_evidence_missing_count": proposal_evidence_missing_count,
            "proposal_evidence_ready_count": proposal_evidence_ready_count,
            "proposal_review_missing_count": _count_value(proposal_evidence_plan.get("proposal_review_missing_count")),
            "next_smallest_truthful_gap": _safe_str(proposal_evidence_plan.get("next_smallest_truthful_gap")).strip(),
        },
        "source_operator_evidence_intake_audit": {
            "status": _safe_str(operator_evidence_audit.get("status")).strip(),
            "operator_evidence_intake_audit_ready": bool(
                operator_evidence_audit.get("operator_evidence_intake_audit_ready")
            ),
            "recorded_pack_count": _count_value(operator_evidence_audit.get("recorded_pack_count")),
            "recorded_capability_count": operator_recorded_capability_count,
            "evidence_ref_count": _count_value(operator_evidence_audit.get("evidence_ref_count")),
            "future_review_required_count": _count_value(operator_evidence_audit.get("future_review_required_count")),
            "next_smallest_truthful_gap": _safe_str(operator_evidence_audit.get("next_smallest_truthful_gap")).strip(),
        },
        "source_proposal_review_plan": {
            "status": _safe_str(proposal_review_plan.get("status")).strip(),
            "proposal_review_plan_ready": proposal_review_plan_ready,
            "candidate_capability_count": _count_value(proposal_review_plan.get("candidate_capability_count")),
            "reviewable_capability_count": reviewable_capability_count,
            "blocked_before_review_capability_count": blocked_before_review_count,
            "proposal_review_missing_count": proposal_review_missing_count,
            "approved_proposal_review_count": approved_proposal_review_count,
            "next_smallest_truthful_gap": _safe_str(proposal_review_plan.get("next_smallest_truthful_gap")).strip(),
        },
        "packs": [
            {
                "pack_id": _safe_str(pack.get("pack_id")).strip(),
                "pack_version": _safe_str(pack.get("pack_version")).strip(),
                "pack_name": _safe_str(pack.get("pack_name")).strip(),
                "staged_capability_count": _count_value(pack.get("staged_capability_count")),
                "reviewable_capability_count": _count_value(pack.get("reviewable_capability_count")),
                "blocked_before_review_capability_count": _count_value(
                    pack.get("blocked_before_review_capability_count")
                ),
                "approved_proposal_review_count": _count_value(pack.get("approved_proposal_review_count")),
                "proposals": [
                    {
                        "capability": _safe_str(proposal.get("capability")).strip(),
                        "proposal_id": _safe_str(proposal.get("proposal_id")).strip(),
                        "review_ready": bool(proposal.get("review_ready")),
                        "proposal_review_missing": bool(proposal.get("proposal_review_missing")),
                        "proposal_review_status": _safe_str(proposal.get("proposal_review_status")).strip(),
                        "proposal_review_receipt_id": _safe_str(proposal.get("proposal_review_receipt_id")).strip(),
                        "blockers_before_review": _unique_texts(proposal.get("blockers_before_review"), limit=25),
                        "proposal_review_route": "/forge/proposals/decision",
                        "proposal_review_would_write_receipt": True,
                        "proposal_review_would_promote_capability": False,
                        "proposal_review_would_enable_capability": False,
                    }
                    for proposal in (pack.get("proposals") if isinstance(pack.get("proposals"), list) else [])
                    if isinstance(proposal, dict)
                ],
                "proposals_truncated": bool(pack.get("proposals_truncated")),
            }
            for pack in review_packs[:_CAPABILITY_LIBRARY_OPERATOR_SURFACE_PACK_PREVIEW_LIMIT]
        ],
        "packs_truncated": _count_value(proposal_review_plan.get("candidate_pack_count")) > len(review_packs),
        "routes": {
            "proposal_review_apply_readiness_route": _CAPABILITY_LIBRARY_PROPOSAL_REVIEW_APPLY_READINESS_ROUTE,
            "proposal_review_apply_route": _CAPABILITY_LIBRARY_PROPOSAL_REVIEW_APPLY_ROUTE,
            "proposal_review_plan_route": "/plugins/capabilities/library/proposal-review/plan",
            "proposal_review_route": "/forge/proposals/decision",
            "proposal_reviews_route": "/forge/proposal_reviews/list",
            "proposal_evidence_plan_route": "/plugins/capabilities/library/proposal-evidence/plan",
            "operator_intake_checklist_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_CHECKLIST_ROUTE,
            "operator_intake_audit_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_AUDIT_ROUTE,
            "operator_intake_apply_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_APPLY_ROUTE,
            "operator_intake_preview_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_PREVIEW_ROUTE,
            "operator_intake_import_preview_route": (
                _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_IMPORT_PREVIEW_ROUTE
            ),
            "promotion_plan_route": "/plugins/capabilities/library/promotion/plan",
        },
        "requirements": {
            "proposal_evidence_required_before_review": True,
            "operator_evidence_refs_may_satisfy_proposal_evidence": True,
            "proposal_id_required_before_review": True,
            "review_ready_capabilities_only": True,
            "explicit_operator_action_required": True,
            "forge_decision_route_required": True,
            "proposal_review_uses_forge_decision_receipt_schema": True,
            "bulk_proposal_review_apply_requires_dry_run_fingerprint": True,
            "no_auto_approval": True,
            "does_not_apply_reviews": True,
        },
        "governance": {
            "read_only": True,
            "operator_facing": True,
            "generated_plugin_registry_sync_performed": sync_performed,
            "does_not_mutate_registry": not sync_performed,
            "does_not_write_receipts": True,
            "does_not_write_proposal_review_receipts": True,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "proposal_review_authority": False,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
        },
        "next_smallest_truthful_gap": next_gap,
    }


def _validate_plugin_artifact_id(value: Any) -> str:
    text = _safe_str(value).strip()
    if not text or not _PLUGIN_ARTIFACT_ID_RE.match(text):
        raise ValueError("invalid plugin artifact id")
    return text


def _plugin_proposal_review_receipt_id(proposal_id: str, decided_ts: int) -> str:
    digest = hashlib.sha256(_safe_str(proposal_id).strip().encode("utf-8")).hexdigest()[:12]
    nonce = time.time_ns() % 1_000_000
    return f"plugin_proposal_review_{decided_ts}_{digest}_{nonce:06d}"


def _plugin_proposal_review_receipt_path(receipt_id: str) -> Path:
    return _art_dir() / "proposal_reviews" / f"{_safe_str(receipt_id).strip()}.json"


def _read_plugin_proposal_for_review(proposal_id: str) -> tuple[Path | None, dict[str, Any] | None]:
    safe_id = _safe_str(proposal_id).strip()
    if not safe_id or not _PLUGIN_ARTIFACT_ID_RE.match(safe_id):
        return None, None
    proposal_root = _art_dir() / "proposals"
    proposal_path = _plugin_proposal_path(safe_id)
    if not _is_under(proposal_root, proposal_path):
        return None, None
    if not proposal_path.exists() or not proposal_path.is_file():
        return proposal_path, None
    try:
        raw = json.loads(proposal_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return proposal_path, None
    if not isinstance(raw, dict):
        return proposal_path, None
    raw["proposal_id"] = safe_id
    return proposal_path, raw


def _capability_library_proposal_review_apply_candidates(
    *,
    registry: dict[str, Any],
    entries: list[dict[str, Any]],
    promotion_discipline: dict[str, Any],
    selected_pack_ids: set[str],
    selected_capability_ids: set[str],
    selected_proposal_ids: set[str],
) -> list[dict[str, Any]]:
    raw_packs = promotion_discipline.get("packs") if isinstance(promotion_discipline.get("packs"), list) else []
    ready_packs = [
        pack
        for pack in raw_packs
        if isinstance(pack, dict) and bool(pack.get("ready")) and _safe_str(pack.get("status")).strip() == "ready"
    ]
    candidates: list[dict[str, Any]] = []

    for pack in ready_packs:
        pack_id = _safe_str(pack.get("pack_id")).strip()
        pack_version = _safe_str(pack.get("pack_version")).strip()
        if selected_pack_ids and pack_id not in selected_pack_ids:
            continue
        pack_entries = _entries_for_capability_pack(entries, pack_id=pack_id, pack_version=pack_version)
        staged_ids = _unique_texts(
            [
                _safe_str(entry.get("capability")).strip()
                for entry in pack_entries
                if _safe_str(entry.get("status")).strip() == "staged"
            ],
            limit=10000,
        )
        if selected_capability_ids:
            staged_ids = [capability_id for capability_id in staged_ids if capability_id in selected_capability_ids]
        if not staged_ids:
            continue

        capabilities: list[dict[str, Any]] = []
        for capability_id in staged_ids:
            plugin = _read_plugin(registry, capability_id)
            if plugin is None:
                continue
            readiness = _plugin_promotion_readiness(
                capability_id,
                plugin,
                PluginToggleIn(id=capability_id, reason="capability_library_proposal_review_apply"),
            )
            missing = _unique_texts(readiness.get("missing_requirements"), limit=25)
            evidence = readiness.get("evidence") if isinstance(readiness.get("evidence"), dict) else {}
            proposal_id = _safe_str(evidence.get("proposal_id")).strip()
            if selected_proposal_ids and proposal_id not in selected_proposal_ids:
                continue
            blockers_before_review = [requirement for requirement in missing if requirement != "proposal_review"]
            if "proposal_review" not in missing or not proposal_id or blockers_before_review:
                continue
            capabilities.append(
                {
                    "capability": capability_id,
                    "status": _safe_str(plugin.get("status")).strip(),
                    "proposal_id": proposal_id,
                    "proposal_review_status": _safe_str(evidence.get("proposal_review_status")).strip(),
                    "proposal_review_receipt_id": _safe_str(evidence.get("proposal_review_receipt_id")).strip(),
                    "missing_requirements": missing,
                    "blockers_before_review": blockers_before_review,
                }
            )

        if capabilities:
            candidates.append(
                {
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "pack_name": _safe_str(pack.get("pack_name")).strip() or pack_id,
                    "staged_capability_count": len(staged_ids),
                    "capabilities": capabilities,
                }
            )

    return candidates


def _capability_library_proposal_review_apply_plan_fingerprint(
    *,
    planned: list[dict[str, Any]],
    action: str,
    decision_status: str,
) -> str:
    canonical_packs: list[dict[str, Any]] = []
    for pack in planned:
        raw_proposals = pack.get("proposals") if isinstance(pack.get("proposals"), list) else []
        proposals: list[dict[str, Any]] = []
        for proposal in raw_proposals:
            if not isinstance(proposal, dict):
                continue
            capabilities = _unique_texts(proposal.get("capability_ids"), limit=10000)
            proposals.append(
                {
                    "proposal_id": _safe_str(proposal.get("proposal_id")).strip(),
                    "capability_ids": sorted(capabilities),
                }
            )
        proposals.sort(key=lambda item: item["proposal_id"])
        canonical_packs.append(
            {
                "pack_id": _safe_str(pack.get("pack_id")).strip(),
                "pack_version": _safe_str(pack.get("pack_version")).strip(),
                "proposals": proposals,
            }
        )
    canonical_packs.sort(key=lambda item: (item["pack_id"], item["pack_version"]))
    body = {
        "contract": "stage17_capability_library_proposal_review_apply_dry_run_v1",
        "action": _safe_str(action).strip().lower(),
        "decision_status": _safe_str(decision_status).strip().lower(),
        "planned": canonical_packs,
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _capability_library_proposal_review_apply_governance(
    *,
    route_path: str,
    action: str,
    decision_status: str,
    writes_proposal_review_receipts: bool,
    updates_proposal_records: bool,
    generated_plugin_registry_sync_performed: bool = False,
) -> dict[str, object]:
    approved_decision = _safe_str(decision_status).strip().lower() == "approved"
    return {
        "scope": _PLUGIN_WRITE_SCOPE,
        "route": route_path,
        "single_decision_route": "/forge/proposals/decision",
        "uses_forge_decision_receipt_schema": True,
        "dry_run_required_before_apply": True,
        "action": _safe_str(action).strip().lower(),
        "decision_status": _safe_str(decision_status).strip().lower(),
        "writes_proposal_review_receipts": writes_proposal_review_receipts,
        "updates_proposal_records": updates_proposal_records,
        "writes_registry_metadata": False,
        "does_not_mutate_registry": not generated_plugin_registry_sync_performed,
        "generated_plugin_registry_sync_performed": generated_plugin_registry_sync_performed,
        "approves_proposals": bool(writes_proposal_review_receipts and approved_decision),
        "would_approve_proposals": approved_decision,
        "does_not_promote_capabilities": True,
        "does_not_enable_capabilities": True,
        "does_not_execute_capabilities": True,
        "proposal_review_authority": writes_proposal_review_receipts,
        "promotion_authority": False,
        "execution_authority": False,
        "memory_write": False,
    }


def _prepare_capability_library_proposal_review_apply_plan(
    *,
    payload: CapabilityLibraryProposalReviewApplyIn,
) -> dict[str, Any]:
    action = _safe_str(payload.action).strip().lower()
    decided_status = _CAPABILITY_LIBRARY_PROPOSAL_REVIEW_DECISIONS.get(action)
    if decided_status is None:
        return {
            "ok": False,
            "status": "blocked",
            "error": "invalid_decision",
            "allowed_actions": sorted(_CAPABILITY_LIBRARY_PROPOSAL_REVIEW_DECISIONS),
        }

    safe_max_pack_count = max(1, min(int(payload.max_pack_count or 10), 50))
    safe_max_total_capability_count = max(1, min(int(payload.max_total_capability_count or 1000), 10000))
    safe_max_capability_count_per_pack = max(1, min(int(payload.max_capability_count_per_pack or 500), 500))
    try:
        selected_pack_ids = {_validate_plugin_id(raw_id) for raw_id in _unique_texts(payload.pack_ids, limit=100)}
        selected_capability_ids = {
            _validate_plugin_id(raw_id) for raw_id in _unique_texts(payload.capability_ids, limit=1000)
        }
        selected_proposal_ids = {
            _validate_plugin_artifact_id(raw_id) for raw_id in _unique_texts(payload.proposal_ids, limit=1000)
        }
    except Exception:
        return {
            "ok": False,
            "status": "blocked",
            "error": "invalid_selector_id",
            "action": action,
            "decision_status": decided_status,
        }

    registry = _load_registry()
    if selected_capability_ids:
        context = _capability_library_selected_promotion_discipline_context(
            registry=registry,
            selected_capability_ids=selected_capability_ids,
        )
        entries = context["entries"] if isinstance(context.get("entries"), list) else []
        promotion_discipline = (
            context["promotion_discipline"] if isinstance(context.get("promotion_discipline"), dict) else {}
        )
        before = _capability_library_selected_capability_readiness_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            selected_pack_ids=selected_pack_ids,
            selected_capability_ids=selected_capability_ids,
            generated_plugin_sync_performed=bool(context.get("generated_plugin_registry_sync_performed")),
        )
        synced = bool(context.get("generated_plugin_registry_sync_performed"))
    else:
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        entries = list(marketplace.catalog())
        available_proposals = _available_capability_pack_proposals()
        available_validation_receipts = _available_capability_pack_validation_receipts()
        available_promotion_receipts = _available_capability_pack_promotion_receipts()
        promotion_discipline = analyze_capability_pack_promotion_discipline(
            entries,
            available_proposal_ids=available_proposals["ids"],
            available_validation_receipt_ids=available_validation_receipts["ids"],
            available_promotion_receipt_ids=available_promotion_receipts["ids"],
            operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
        )
        before = _capability_library_proposal_review_plan_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            generated_plugin_sync_performed=bool(synced),
        )
    candidates = _capability_library_proposal_review_apply_candidates(
        registry=registry,
        entries=entries,
        promotion_discipline=promotion_discipline,
        selected_pack_ids=selected_pack_ids,
        selected_capability_ids=selected_capability_ids,
        selected_proposal_ids=selected_proposal_ids,
    )
    if not candidates:
        return {
            "ok": True,
            "status": "no_candidates",
            "action": action,
            "decision_status": decided_status,
            "planned_pack_count": 0,
            "planned_capability_count": 0,
            "planned_proposal_count": 0,
            "recorded_proposal_count": 0,
            "before": before,
            "generated_plugin_registry_sync_performed": bool(synced),
        }
    if len(candidates) > safe_max_pack_count:
        return {
            "ok": False,
            "status": "blocked",
            "error": "proposal_review_apply_pack_limit_exceeded",
            "candidate_total": len(candidates),
            "limit": safe_max_pack_count,
            "action": action,
            "decision_status": decided_status,
            "before": before,
            "generated_plugin_registry_sync_performed": bool(synced),
        }

    prepared: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    total_capability_count = 0
    unique_proposal_ids: set[str] = set()
    for pack in candidates:
        raw_capabilities = pack.get("capabilities") if isinstance(pack.get("capabilities"), list) else []
        capabilities = [capability for capability in raw_capabilities if isinstance(capability, dict)]
        capability_count = len(capabilities)
        if capability_count <= 0:
            skipped.append(
                {
                    "pack_id": _safe_str(pack.get("pack_id")).strip(),
                    "pack_version": _safe_str(pack.get("pack_version")).strip(),
                    "error": "capability_ids_required",
                }
            )
            continue
        if capability_count > safe_max_capability_count_per_pack:
            skipped.append(
                {
                    "pack_id": _safe_str(pack.get("pack_id")).strip(),
                    "pack_version": _safe_str(pack.get("pack_version")).strip(),
                    "error": "candidate_capability_limit_exceeded",
                    "capability_count": capability_count,
                    "limit": safe_max_capability_count_per_pack,
                }
            )
            continue

        proposals_by_id: dict[str, dict[str, Any]] = {}
        blocked_capabilities: list[dict[str, Any]] = []
        for capability in capabilities:
            proposal_id = _safe_str(capability.get("proposal_id")).strip()
            capability_id = _safe_str(capability.get("capability")).strip()
            proposal_path, proposal = _read_plugin_proposal_for_review(proposal_id)
            if proposal_path is None or proposal is None:
                blocked_capabilities.append(
                    {
                        "capability": capability_id,
                        "proposal_id": proposal_id,
                        "error": "proposal_record_required",
                    }
                )
                continue
            bucket = proposals_by_id.setdefault(
                proposal_id,
                {
                    "proposal_id": proposal_id,
                    "proposal_path": str(proposal_path),
                    "plugin_id": _safe_str(proposal.get("plugin_id")).strip(),
                    "capability_ids": [],
                },
            )
            bucket["capability_ids"].append(capability_id)
            unique_proposal_ids.add(proposal_id)

        if blocked_capabilities:
            skipped.append(
                {
                    "pack_id": _safe_str(pack.get("pack_id")).strip(),
                    "pack_version": _safe_str(pack.get("pack_version")).strip(),
                    "error": "proposal_review_apply_blocked",
                    "capabilities": blocked_capabilities,
                }
            )
        proposals = list(proposals_by_id.values())
        if not proposals:
            continue

        total_capability_count += sum(len(_unique_texts(item.get("capability_ids"), limit=10000)) for item in proposals)
        prepared.append(
            {
                "pack_id": _safe_str(pack.get("pack_id")).strip(),
                "pack_version": _safe_str(pack.get("pack_version")).strip(),
                "pack_name": _safe_str(pack.get("pack_name")).strip() or _safe_str(pack.get("pack_id")).strip(),
                "staged_capability_count": int(pack.get("staged_capability_count") or 0),
                "proposals": proposals,
            }
        )

    if total_capability_count > safe_max_total_capability_count:
        return {
            "ok": False,
            "status": "blocked",
            "error": "proposal_review_apply_total_capability_limit_exceeded",
            "capability_count": total_capability_count,
            "limit": safe_max_total_capability_count,
            "action": action,
            "decision_status": decided_status,
            "before": before,
            "generated_plugin_registry_sync_performed": bool(synced),
        }
    if not prepared:
        return {
            "ok": True,
            "status": "no_supported_proposal_reviews",
            "action": action,
            "decision_status": decided_status,
            "planned_pack_count": 0,
            "planned_capability_count": 0,
            "planned_proposal_count": 0,
            "recorded_proposal_count": 0,
            "skipped": skipped,
            "before": before,
            "generated_plugin_registry_sync_performed": bool(synced),
        }

    planned = [
        {
            "pack_id": _safe_str(pack.get("pack_id")).strip(),
            "pack_version": _safe_str(pack.get("pack_version")).strip(),
            "pack_name": _safe_str(pack.get("pack_name")).strip(),
            "action": action,
            "decision_status": decided_status,
            "proposal_count": len(pack.get("proposals") if isinstance(pack.get("proposals"), list) else []),
            "capability_count": sum(
                len(_unique_texts(proposal.get("capability_ids"), limit=10000))
                for proposal in (pack.get("proposals") if isinstance(pack.get("proposals"), list) else [])
                if isinstance(proposal, dict)
            ),
            "proposals": [
                {
                    "proposal_id": _safe_str(proposal.get("proposal_id")).strip(),
                    "proposal_path": _safe_str(proposal.get("proposal_path")).strip(),
                    "plugin_id": _safe_str(proposal.get("plugin_id")).strip(),
                    "capability_ids": _unique_texts(proposal.get("capability_ids"), limit=10000),
                    "writes_proposal_review_receipt": False,
                    "updates_proposal_record": False,
                    "approves_proposal": decided_status == "approved",
                    "promotes_capability": False,
                    "enables_capability": False,
                }
                for proposal in (pack.get("proposals") if isinstance(pack.get("proposals"), list) else [])
                if isinstance(proposal, dict)
            ],
        }
        for pack in prepared
    ]
    dry_run_fingerprint = _capability_library_proposal_review_apply_plan_fingerprint(
        planned=planned,
        action=action,
        decision_status=decided_status,
    )
    return {
        "ok": True,
        "status": "planned",
        "action": action,
        "decision_status": decided_status,
        "before": before,
        "prepared": prepared,
        "planned": planned,
        "skipped": skipped,
        "dry_run_fingerprint": dry_run_fingerprint,
        "planned_pack_count": len(planned),
        "planned_capability_count": total_capability_count,
        "planned_proposal_count": len(unique_proposal_ids),
        "selected_pack_ids": sorted(selected_pack_ids),
        "selected_capability_ids": sorted(selected_capability_ids),
        "selected_proposal_ids": sorted(selected_proposal_ids),
        "generated_plugin_registry_sync_performed": bool(synced),
    }


def _write_capability_library_proposal_review_decision_receipt(
    *,
    proposal_id: str,
    action: str,
    decided_status: str,
    actor: Any,
    reason: str,
    notes: str,
    meta: dict[str, Any],
    route_path: str,
) -> dict[str, Any]:
    proposal_path, proposal = _read_plugin_proposal_for_review(proposal_id)
    if proposal_path is None:
        return {"ok": False, "error": "invalid_proposal_id", "proposal_id": proposal_id}
    if proposal is None:
        return {"ok": False, "error": "proposal_record_required", "proposal_id": proposal_id}

    previous_status = _safe_str(proposal.get("status")).strip() or "unknown"
    decided_ts = _now_s()
    receipt_id = _plugin_proposal_review_receipt_id(proposal_id, decided_ts)
    receipt_path = _plugin_proposal_review_receipt_path(receipt_id)
    receipt_root = _art_dir() / "proposal_reviews"
    if not _is_under(receipt_root, receipt_path):
        return {"ok": False, "error": "invalid_receipt_path", "proposal_id": proposal_id}

    receipt = {
        "kind": "plugin.proposal.review.receipt",
        "receipt_id": receipt_id,
        "proposal_id": proposal_id,
        "plugin_id": _safe_str(proposal.get("plugin_id")).strip(),
        "previous_status": previous_status,
        "status": decided_status,
        "decision": action,
        "decided_ts": decided_ts,
        "actor": _safe_str(actor).strip(),
        "reason": _safe_str(reason).strip() or "stage17_capability_library_proposal_review",
        "notes": _safe_str(notes).strip(),
        "meta": meta if isinstance(meta, dict) else {},
        "proposal_path": str(proposal_path),
        "governance": {
            "gate": "permission_gate",
            "scope": _PLUGIN_WRITE_SCOPE,
            "route": route_path,
            "single_decision_route": "/forge/proposals/decision",
            "uses_forge_decision_receipt_schema": True,
            "promotion_authority": False,
            "execution_authority": False,
        },
        "path": str(receipt_path),
    }
    redacted_receipt = redact_governed_display_value(receipt)
    receipt_out = redacted_receipt if isinstance(redacted_receipt, dict) else {}

    history = proposal.get("review_history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "receipt_id": receipt_id,
            "status": decided_status,
            "decision": action,
            "decided_ts": decided_ts,
            "actor": receipt_out.get("actor", ""),
        }
    )
    proposal["status"] = decided_status
    proposal["updated_ts"] = decided_ts
    proposal["review_receipt_id"] = receipt_id
    proposal["review_receipt_path"] = str(receipt_path)
    proposal["review"] = {
        "status": decided_status,
        "decision": action,
        "reason": receipt_out.get("reason", ""),
        "notes": receipt_out.get("notes", ""),
        "actor": receipt_out.get("actor", ""),
        "decided_ts": decided_ts,
        "receipt_id": receipt_id,
    }
    proposal["review_history"] = history

    redacted_proposal = redact_governed_display_value(proposal)
    proposal_out = redacted_proposal if isinstance(redacted_proposal, dict) else {}
    _atomic_write_display_json(receipt_path, receipt_out)
    _atomic_write_display_json(proposal_path, proposal_out)
    return {
        "ok": True,
        "proposal_id": proposal_id,
        "plugin_id": _safe_str(proposal.get("plugin_id")).strip(),
        "receipt_id": receipt_id,
        "receipt_path": str(receipt_path),
        "receipt": receipt_out,
        "status": decided_status,
    }


def _record_capability_library_proposal_review_apply_batch(
    *,
    prepared: list[dict[str, Any]],
    payload: CapabilityLibraryProposalReviewApplyIn,
    action: str,
    decided_status: str,
    route_path: str,
) -> dict[str, Any]:
    batch_id = f"capability_library_proposal_review_batch_{_now_s()}_{uuid.uuid4().hex[:8]}"
    batch_meta = {
        **payload.meta,
        "stage": "Stage 17 / Capability Economy",
        "capability_library_bulk_review": True,
        "bulk_review_batch_id": batch_id,
        "bulk_review_route": route_path,
        "single_decision_route": "/forge/proposals/decision",
        "uses_forge_decision_receipt_schema": True,
        "dry_run": False,
    }
    recorded: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    seen_proposal_ids: set[str] = set()

    for pack in prepared:
        pack_id = _safe_str(pack.get("pack_id")).strip()
        pack_version = _safe_str(pack.get("pack_version")).strip()
        raw_proposals = pack.get("proposals") if isinstance(pack.get("proposals"), list) else []
        for proposal in raw_proposals:
            if not isinstance(proposal, dict):
                continue
            proposal_id = _safe_str(proposal.get("proposal_id")).strip()
            if not proposal_id or proposal_id in seen_proposal_ids:
                continue
            seen_proposal_ids.add(proposal_id)
            capability_ids = _unique_texts(proposal.get("capability_ids"), limit=10000)
            meta = {
                **batch_meta,
                "pack_id": pack_id,
                "pack_version": pack_version,
                "capability_ids": capability_ids,
                "capability_count": len(capability_ids),
            }
            result = _write_capability_library_proposal_review_decision_receipt(
                proposal_id=proposal_id,
                action=action,
                decided_status=decided_status,
                actor=payload.actor,
                reason=_safe_str(payload.reason).strip() or "stage17_capability_library_proposal_review",
                notes=_safe_str(payload.notes).strip(),
                meta=meta,
                route_path=route_path,
            )
            if not result.get("ok"):
                failed.append(
                    {
                        "pack_id": pack_id,
                        "pack_version": pack_version,
                        "proposal_id": proposal_id,
                        "capability_ids": capability_ids,
                        "error": _safe_str(result.get("error")).strip() or "proposal_review_write_failed",
                    }
                )
                continue
            recorded.append(
                {
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "proposal_id": proposal_id,
                    "plugin_id": _safe_str(result.get("plugin_id")).strip(),
                    "receipt_id": _safe_str(result.get("receipt_id")).strip(),
                    "receipt_path": _safe_str(result.get("receipt_path")).strip(),
                    "capability_ids": capability_ids,
                    "capability_count": len(capability_ids),
                    "status": decided_status,
                }
            )

    return {"batch_id": batch_id, "recorded": recorded, "failed": failed}


def _capability_library_operator_proposal_evidence_next_batch(operator_checklist: dict[str, Any]) -> dict[str, Any]:
    raw_packs = operator_checklist.get("packs") if isinstance(operator_checklist.get("packs"), list) else []
    pack = next((item for item in raw_packs if isinstance(item, dict)), None)
    if pack is None:
        return {
            "status": "no_operator_evidence_batch",
            "ready": False,
            "batch_capability_count": 0,
            "batch_evidence_ref_required_count": 0,
            "operator_must_supply_evidence_refs": True,
            "no_synthetic_evidence": True,
        }

    pack_id = _safe_str(pack.get("pack_id")).strip()
    pack_version = _safe_str(pack.get("pack_version")).strip()
    raw_capabilities = pack.get("capabilities") if isinstance(pack.get("capabilities"), list) else []
    capabilities = [item for item in raw_capabilities if isinstance(item, dict)]
    capability_ids = [
        capability_id
        for capability in capabilities
        if (capability_id := _safe_str(capability.get("capability")).strip())
    ]
    batch_capability_count = len(capability_ids)
    pack_candidate_count = _count_value(pack.get("candidate_capability_count"))
    batch_truncated = bool(pack.get("capabilities_truncated")) or batch_capability_count < pack_candidate_count
    local_artifact_ref_hints = {
        _safe_str(capability.get("capability")).strip(): capability.get("local_artifact_ref_hint")
        for capability in capabilities
        if isinstance(capability.get("local_artifact_ref_hint"), dict)
        and _safe_str(capability.get("capability")).strip()
    }
    local_artifact_refs_by_capability = {
        capability_id: _unique_texts(hint.get("evidence_refs"), limit=10)
        for capability_id, hint in local_artifact_ref_hints.items()
        if bool(hint.get("ready"))
    }
    local_artifact_ref_hint_capability_count = len(local_artifact_refs_by_capability)
    local_artifact_ref_hint_evidence_ref_count = sum(len(refs) for refs in local_artifact_refs_by_capability.values())
    local_artifact_ref_hints_complete = bool(batch_capability_count) and (
        local_artifact_ref_hint_capability_count == batch_capability_count
    )
    apply_payload_refs_by_capability = local_artifact_refs_by_capability if local_artifact_ref_hints_complete else {}
    return {
        "status": "ready_for_operator_evidence_batch" if batch_capability_count else "no_operator_evidence_batch",
        "ready": bool(batch_capability_count),
        "batch_source": "operator_evidence_intake_checklist_first_visible_pack",
        "pack_id": pack_id,
        "pack_version": pack_version,
        "pack_name": _safe_str(pack.get("pack_name")).strip(),
        "pack_candidate_capability_count": pack_candidate_count,
        "pack_evidence_ref_required_count": _count_value(pack.get("evidence_ref_required_count")),
        "batch_capability_count": batch_capability_count,
        "batch_evidence_ref_required_count": batch_capability_count,
        "batch_capabilities_truncated": batch_truncated,
        "claim_scope": "operator_supplied_friction_evidence_reference_not_independent_verification",
        "operator_must_supply_evidence_refs": True,
        "operator_supplied_evidence_not_independently_verified": True,
        "does_not_validate_evidence_truth": True,
        "requires_future_proposal_review": True,
        "dry_run_required_before_apply": True,
        "no_synthetic_evidence": True,
        "local_artifact_ref_hints_ready": local_artifact_ref_hints_complete,
        "local_artifact_ref_hint_capability_count": local_artifact_ref_hint_capability_count,
        "local_artifact_ref_hint_evidence_ref_count": local_artifact_ref_hint_evidence_ref_count,
        "local_artifact_ref_hints_complete": local_artifact_ref_hints_complete,
        "operator_must_review_local_artifact_refs_before_apply": True,
        "local_artifact_refs_by_capability": local_artifact_refs_by_capability,
        "capabilities": [
            {
                "capability": _safe_str(capability.get("capability")).strip(),
                "status": _safe_str(capability.get("status")).strip(),
                "proposal_id": _safe_str(capability.get("proposal_id")).strip(),
                "proposal_review_status": _safe_str(capability.get("proposal_review_status")).strip(),
                "proposal_review_receipt_id": _safe_str(capability.get("proposal_review_receipt_id")).strip(),
                "missing_requirements": _unique_texts(capability.get("missing_requirements"), limit=25),
                "blockers_before_evidence": _unique_texts(capability.get("blockers_before_evidence"), limit=25),
                "evidence_refs_required": True,
                "operator_supplied_evidence_not_independently_verified": True,
                "local_artifact_ref_hint": capability.get("local_artifact_ref_hint")
                if isinstance(capability.get("local_artifact_ref_hint"), dict)
                else {},
                "intake_apply_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_APPLY_ROUTE,
            }
            for capability in capabilities
        ],
        "apply_payload_hint": {
            "pack_ids": [pack_id] if pack_id else [],
            "capability_ids": capability_ids,
            "evidence_refs": [],
            "evidence_refs_by_capability": apply_payload_refs_by_capability,
            "dry_run": True,
            "max_pack_count": 1,
            "max_total_capability_count": max(1, batch_capability_count),
            "max_capability_count_per_pack": max(1, batch_capability_count),
        },
        "routes": {
            "operator_intake_worksheet_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_WORKSHEET_ROUTE,
            "operator_intake_export_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_EXPORT_ROUTE,
            "operator_intake_import_preview_route": (
                _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_IMPORT_PREVIEW_ROUTE
            ),
            "operator_intake_preview_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_PREVIEW_ROUTE,
            "operator_intake_apply_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_APPLY_ROUTE,
        },
    }


def _capability_library_proposal_evidence_source_readiness_projection(
    *,
    proposal_evidence_plan: dict[str, Any],
    artifact_remediation: dict[str, Any],
    friction_summary_refs: dict[str, Any],
    operator_checklist: dict[str, Any],
    operator_audit: dict[str, Any],
    proposal_review_apply_readiness: dict[str, Any],
    generated_plugin_sync_performed: bool,
) -> dict[str, Any]:
    discipline_blocked_pack_count = _count_value(proposal_evidence_plan.get("blocked_pack_count"))
    proposal_evidence_missing_count = _count_value(proposal_evidence_plan.get("proposal_evidence_missing_count"))
    proposal_evidence_ready_count = _count_value(proposal_evidence_plan.get("proposal_evidence_ready_count"))
    blocked_before_evidence_count = _count_value(proposal_evidence_plan.get("blocked_before_evidence_count"))
    proposal_review_missing_count = _count_value(proposal_evidence_plan.get("proposal_review_missing_count"))
    artifact_candidate_pack_count = _count_value(artifact_remediation.get("candidate_pack_count"))
    artifact_candidate_capability_count = _count_value(artifact_remediation.get("candidate_capability_count"))
    friction_candidate_pack_count = _count_value(friction_summary_refs.get("candidate_pack_count"))
    friction_candidate_capability_count = _count_value(friction_summary_refs.get("candidate_capability_count"))
    operator_candidate_pack_count = _count_value(operator_checklist.get("candidate_pack_count"))
    operator_candidate_capability_count = _count_value(operator_checklist.get("candidate_capability_count"))
    operator_evidence_ref_required_count = _count_value(operator_checklist.get("evidence_ref_required_count"))
    recorded_operator_pack_count = _count_value(operator_audit.get("recorded_pack_count"))
    recorded_operator_capability_count = _count_value(operator_audit.get("recorded_capability_count"))
    recorded_operator_evidence_ref_count = _count_value(operator_audit.get("evidence_ref_count"))
    automatic_source_candidate_pack_count = artifact_candidate_pack_count + friction_candidate_pack_count
    automatic_source_candidate_capability_count = (
        artifact_candidate_capability_count + friction_candidate_capability_count
    )
    automatic_sources_exhausted = (
        proposal_evidence_missing_count > 0 and automatic_source_candidate_capability_count == 0
    )
    next_operator_batch = _capability_library_operator_proposal_evidence_next_batch(operator_checklist)
    next_operator_batch_count = _count_value(next_operator_batch.get("batch_capability_count"))

    if discipline_blocked_pack_count:
        status = "blocked"
        next_gap = _safe_str(proposal_evidence_plan.get("next_smallest_truthful_gap")).strip()
    elif proposal_evidence_missing_count == 0:
        status = "proposal_evidence_complete"
        next_gap = _safe_str(proposal_review_apply_readiness.get("next_smallest_truthful_gap")).strip()
    elif artifact_candidate_capability_count:
        status = "ready_for_existing_artifact_evidence_backfill"
        next_gap = _safe_str(artifact_remediation.get("next_smallest_truthful_gap")).strip()
    elif friction_candidate_capability_count:
        status = "ready_for_friction_summary_ref_backfill"
        next_gap = _safe_str(friction_summary_refs.get("next_smallest_truthful_gap")).strip()
    elif operator_candidate_capability_count:
        status = "operator_evidence_refs_required"
        next_gap = "stage17_capability_library_operator_proposal_evidence_refs"
    elif blocked_before_evidence_count:
        status = "blocked_before_operator_evidence_refs"
        next_gap = _safe_str(proposal_evidence_plan.get("next_smallest_truthful_gap")).strip()
    else:
        status = "blocked_no_current_evidence_source"
        next_gap = _safe_str(proposal_evidence_plan.get("next_smallest_truthful_gap")).strip()

    sync_performed = bool(generated_plugin_sync_performed)
    return {
        "stage": "Stage 17 / Capability Economy",
        "status": status,
        **_stage17_projection_evidence(
            projection_scope="full_library",
            global_counts_included=True,
            generated_plugin_sync_performed=sync_performed,
        ),
        "proposal_evidence_source_readiness_ready": not bool(discipline_blocked_pack_count),
        "proposal_evidence_missing_count": proposal_evidence_missing_count,
        "proposal_evidence_ready_count": proposal_evidence_ready_count,
        "proposal_review_missing_count": proposal_review_missing_count,
        "blocked_before_evidence_count": blocked_before_evidence_count,
        "automatic_source_candidate_pack_count": automatic_source_candidate_pack_count,
        "automatic_source_candidate_capability_count": automatic_source_candidate_capability_count,
        "automatic_sources_exhausted": automatic_sources_exhausted,
        "operator_evidence_intake_candidate_pack_count": operator_candidate_pack_count,
        "operator_evidence_intake_candidate_capability_count": operator_candidate_capability_count,
        "operator_evidence_ref_required_count": operator_evidence_ref_required_count,
        "recorded_operator_evidence_pack_count": recorded_operator_pack_count,
        "recorded_operator_evidence_capability_count": recorded_operator_capability_count,
        "recorded_operator_evidence_ref_count": recorded_operator_evidence_ref_count,
        "next_operator_evidence_batch_ready": bool(next_operator_batch.get("ready")),
        "next_operator_evidence_batch_capability_count": next_operator_batch_count,
        "next_operator_evidence_batch": next_operator_batch,
        "proposal_review_apply_status": _safe_str(proposal_review_apply_readiness.get("status")).strip(),
        "source_proposal_evidence_plan": {
            "status": _safe_str(proposal_evidence_plan.get("status")).strip(),
            "candidate_pack_count": _count_value(proposal_evidence_plan.get("candidate_pack_count")),
            "candidate_capability_count": _count_value(proposal_evidence_plan.get("candidate_capability_count")),
            "proposal_evidence_missing_count": proposal_evidence_missing_count,
            "proposal_evidence_ready_count": proposal_evidence_ready_count,
            "proposal_review_missing_count": proposal_review_missing_count,
            "blocked_before_evidence_count": blocked_before_evidence_count,
            "next_smallest_truthful_gap": _safe_str(proposal_evidence_plan.get("next_smallest_truthful_gap")).strip(),
        },
        "source_inventory": {
            "existing_linked_proposal_artifact": {
                "status": _safe_str(artifact_remediation.get("status")).strip(),
                "ready": bool(artifact_remediation.get("proposal_evidence_remediation_ready")),
                "candidate_pack_count": artifact_candidate_pack_count,
                "candidate_capability_count": artifact_candidate_capability_count,
                "claim_scope": "existing_linked_proposal_artifact_friction_evidence",
                "apply_route": _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_REMEDIATION_APPLY_ROUTE,
                "requires_plugins_write_scope": True,
                "writes_registry_metadata_on_apply": True,
                "writes_proposals": False,
            },
            "existing_registry_friction_summary_ref": {
                "status": _safe_str(friction_summary_refs.get("status")).strip(),
                "ready": bool(friction_summary_refs.get("proposal_evidence_friction_summary_refs_ready")),
                "candidate_pack_count": friction_candidate_pack_count,
                "candidate_capability_count": friction_candidate_capability_count,
                "claim_scope": _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_FRICTION_REF_CLAIM_SCOPE,
                "apply_route": _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_FRICTION_REF_APPLY_ROUTE,
                "requires_plugins_write_scope": True,
                "records_reference_not_friction_summary_body": True,
                "requires_future_review": True,
                "writes_registry_metadata_on_apply": True,
                "writes_proposals": False,
            },
            "operator_supplied_evidence_refs": {
                "status": _safe_str(operator_checklist.get("status")).strip(),
                "ready": bool(operator_checklist.get("operator_evidence_intake_checklist_ready")),
                "candidate_pack_count": operator_candidate_pack_count,
                "candidate_capability_count": operator_candidate_capability_count,
                "evidence_ref_required_count": operator_evidence_ref_required_count,
                "claim_scope": "operator_supplied_friction_evidence_reference_not_independent_verification",
                "apply_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_APPLY_ROUTE,
                "preview_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_PREVIEW_ROUTE,
                "worksheet_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_WORKSHEET_ROUTE,
                "export_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_EXPORT_ROUTE,
                "requires_plugins_write_scope": True,
                "dry_run_required_before_apply": True,
                "does_not_validate_evidence_truth": True,
                "requires_future_review": True,
            },
            "recorded_operator_evidence_refs": {
                "status": _safe_str(operator_audit.get("status")).strip(),
                "ready": bool(operator_audit.get("operator_evidence_intake_audit_ready")),
                "recorded_pack_count": recorded_operator_pack_count,
                "recorded_capability_count": recorded_operator_capability_count,
                "evidence_ref_count": recorded_operator_evidence_ref_count,
                "future_review_required_count": _count_value(operator_audit.get("future_review_required_count")),
                "audit_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_AUDIT_ROUTE,
            },
            "synthetic_evidence": {
                "status": "disallowed",
                "ready": False,
                "candidate_capability_count": 0,
                "no_synthetic_evidence": True,
            },
        },
        "routes": {
            "proposal_evidence_source_readiness_route": (_CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_SOURCE_READINESS_ROUTE),
            "proposal_evidence_plan_route": "/plugins/capabilities/library/proposal-evidence/plan",
            "proposal_evidence_remediation_route": "/plugins/capabilities/library/proposal-evidence/remediation",
            "proposal_evidence_remediation_apply_route": (
                _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_REMEDIATION_APPLY_ROUTE
            ),
            "proposal_evidence_friction_summary_refs_route": (
                "/plugins/capabilities/library/proposal-evidence/friction-summary-refs"
            ),
            "proposal_evidence_friction_summary_refs_apply_route": (
                _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_FRICTION_REF_APPLY_ROUTE
            ),
            "operator_intake_checklist_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_CHECKLIST_ROUTE,
            "operator_intake_worksheet_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_WORKSHEET_ROUTE,
            "operator_intake_export_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_EXPORT_ROUTE,
            "operator_intake_import_preview_route": (
                _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_IMPORT_PREVIEW_ROUTE
            ),
            "operator_intake_audit_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_AUDIT_ROUTE,
            "operator_intake_preview_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_PREVIEW_ROUTE,
            "operator_intake_apply_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_APPLY_ROUTE,
            "proposal_review_apply_readiness_route": _CAPABILITY_LIBRARY_PROPOSAL_REVIEW_APPLY_READINESS_ROUTE,
            "proposal_review_route": "/forge/proposals/decision",
        },
        "requirements": {
            "read_only_source_inventory": True,
            "proposal_evidence_required_before_proposal_review": True,
            "automatic_sources_must_be_existing_artifacts_or_registry_refs": True,
            "operator_supplied_refs_required_when_automatic_sources_exhausted": True,
            "operator_supplied_refs_are_not_independently_verified": True,
            "future_proposal_review_required_after_evidence": True,
            "dry_run_required_before_any_apply": True,
            "no_synthetic_evidence": True,
            "does_not_validate_evidence_truth": True,
            "does_not_review_or_approve_proposals": True,
            "does_not_promote_or_enable_capabilities": True,
        },
        "governance": {
            "read_only": True,
            "operator_facing": True,
            "generated_plugin_registry_sync_performed": sync_performed,
            "does_not_mutate_registry": not sync_performed,
            "does_not_write_receipts": True,
            "does_not_write_validation_receipts": True,
            "does_not_write_proposals": True,
            "does_not_write_proposal_review_receipts": True,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "proposal_review_authority": False,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
        },
        "next_smallest_truthful_gap": next_gap,
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


def _artifact_link_plan_for_pack_capabilities(
    *,
    registry: dict[str, Any],
    capability_ids: list[str],
    candidates: dict[str, Any],
    artifact_id_key: str,
    path_key: str,
    limit: int,
) -> dict[str, dict[str, Any]]:
    raw_by_plugin_id = candidates.get("by_plugin_id")
    by_plugin_id = raw_by_plugin_id if isinstance(raw_by_plugin_id, dict) else {}
    planned: dict[str, dict[str, Any]] = {}
    safe_limit = max(1, limit)
    for capability_id in capability_ids:
        current = _read_plugin(registry, capability_id)
        if current is None:
            continue
        meta = dict(current.get("meta") or {}) if isinstance(current.get("meta"), dict) else {}
        if _safe_str(meta.get(artifact_id_key)).strip() and _safe_str(meta.get(path_key)).strip():
            continue
        raw_link = by_plugin_id.get(capability_id)
        link = raw_link if isinstance(raw_link, dict) else {}
        artifact_id = _safe_str(link.get(artifact_id_key)).strip()
        artifact_path = _safe_str(link.get(path_key)).strip()
        if not artifact_id or not artifact_path:
            continue
        planned[capability_id] = dict(link)
        if len(planned) >= safe_limit:
            break
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
        partial_existing_artifact_link_backfill = bool(item.get("partial_existing_artifact_link_backfill"))
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
                "partial_existing_artifact_link_backfill": partial_existing_artifact_link_backfill,
                "partial_link_backfill_does_not_claim_pack_complete": partial_existing_artifact_link_backfill,
                "applied_evidence_blockers": _unique_texts(item.get("evidence_blockers"), limit=50),
                "status": "recorded" if changed_capability_ids else "unchanged",
            }
        )

    if changed:
        _save_registry_and_catalog(registry)
    return {"recorded": recorded, "failed": failed}


def _quality_standard_reference_candidates() -> dict[str, list[str]]:
    available_tests = _available_capability_pack_test_paths()
    available_docs = _available_capability_pack_doc_paths()

    def existing_repo_ref(ref: str) -> bool:
        candidate = _resolve_under(repo_root(), ref)
        return candidate is not None and candidate.is_file()

    return {
        "tests": [
            ref
            for ref in _unique_texts(list(_CAPABILITY_PACK_QUALITY_TEST_REFERENCE_CANDIDATES), limit=50)
            if ref in available_tests or existing_repo_ref(ref)
        ],
        "docs": [
            ref
            for ref in _unique_texts(list(_CAPABILITY_PACK_QUALITY_DOC_REFERENCE_CANDIDATES), limit=50)
            if ref in available_docs or existing_repo_ref(ref)
        ],
    }


def _quality_standard_missing_capability_ids(
    pack_entries: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    missing_tests: list[str] = []
    missing_docs: list[str] = []
    for entry in pack_entries:
        capability_id = _safe_str(entry.get("capability")).strip()
        if not capability_id:
            continue
        quality = entry.get("quality") if isinstance(entry.get("quality"), dict) else {}
        if not _unique_texts(quality.get("tests"), limit=50):
            missing_tests.append(capability_id)
        if not _unique_texts(quality.get("docs"), limit=50):
            missing_docs.append(capability_id)
    return (_unique_texts(missing_tests, limit=500), _unique_texts(missing_docs, limit=500))


def _record_capability_pack_quality_standard_remediation_batch(
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
        test_refs = _unique_texts(item.get("test_refs"), limit=50)
        doc_refs = _unique_texts(item.get("doc_refs"), limit=50)
        missing_test_ids = set(_unique_texts(item.get("missing_test_capability_ids"), limit=500))
        missing_doc_ids = set(_unique_texts(item.get("missing_doc_capability_ids"), limit=500))
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
            if capability_id in missing_test_ids and test_refs and not _unique_texts(quality.get("tests"), limit=50):
                quality["tests"] = _merge_quality_references(quality.get("tests"), test_refs)
            if capability_id in missing_doc_ids and doc_refs and not _unique_texts(quality.get("docs"), limit=50):
                quality["docs"] = _merge_quality_references(quality.get("docs"), doc_refs)
            if quality != before_quality:
                quality["reference_source"] = _CAPABILITY_PACK_QUALITY_STANDARD_REMEDIATION_SOURCE
                quality["claim_scope"] = "candidate_reference_only_not_pack_specific_proof"
                quality["pack_specific_coverage_claimed"] = False
                quality["validation_receipt_written"] = False
                quality["proposal_lineage_written"] = False
                meta["quality"] = quality
                meta["quality_standard_remediation_source"] = _CAPABILITY_PACK_QUALITY_STANDARD_REMEDIATION_SOURCE
                meta["quality_reference_remediation_source"] = _CAPABILITY_PACK_QUALITY_STANDARD_REMEDIATION_SOURCE
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
                "writes_validation_receipts": False,
                "writes_proposals": False,
                "applied_quality_blockers": _unique_texts(item.get("quality_blockers"), limit=50),
                "status": "recorded" if changed_capability_ids else "unchanged",
            }
        )

    if changed:
        _save_registry_and_catalog(registry)
    return {"recorded": recorded, "failed": failed}


def _plugin_artifact_relative_path(folder_name: str, artifact_id: str) -> str:
    safe_folder = _safe_str(folder_name).strip().strip("/\\")
    safe_id = _safe_str(artifact_id).strip()
    return f"data/artifacts/plugins/{safe_folder}/{safe_id}.json"


def _quality_references_from_reconstruction_capability(capability: dict[str, Any]) -> tuple[list[str], list[str]]:
    tests = _unique_texts(capability.get("quality_test_references"), limit=50)
    docs = _unique_texts(capability.get("quality_doc_references"), limit=50)
    if tests and docs:
        return (tests, docs)

    available = capability.get("available_inputs") if isinstance(capability.get("available_inputs"), dict) else {}
    if not bool(available.get("quality_test_references")) or not bool(available.get("quality_doc_references")):
        return ([], [])
    return (
        list(_CAPABILITY_PACK_QUALITY_TEST_REFERENCE_CANDIDATES),
        list(_CAPABILITY_PACK_QUALITY_DOC_REFERENCE_CANDIDATES),
    )


def _stage17_closure_matrix(
    *,
    all_items: list[dict[str, Any]],
    coherence: dict[str, Any],
    pack_readiness: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    pack_total = _count_value(pack_readiness.get("pack_total"))
    ready_pack_count = _count_value(pack_readiness.get("ready_pack_count"))
    blocked_pack_count = _count_value(pack_readiness.get("blocked_pack_count"))
    unpacked_entry_count = _count_value(pack_readiness.get("unpacked_entry_count"))
    duplicate_capability_count = _stage17_list_count(coherence, "duplicate_capabilities")
    duplicate_proposal_count = _stage17_list_count(coherence, "duplicate_proposals")
    lineage_gap_count = _stage17_list_count(coherence, "lineage_gaps")
    validation_lineage_gap_count = _stage17_list_count(coherence, "validation_lineage_gaps")
    quality_gap_count = _stage17_list_count(coherence, "quality_gaps")
    pack_blockers = _stage17_pack_blocker_counts(pack_readiness)

    criteria = [
        _stage17_closure_criterion(
            criterion_id="criterion_1_reusable_operational_assets",
            title="Packs are reusable operational assets.",
            status=_stage17_status(
                pack_total > 0,
                [
                    *(["no_versioned_packs_detected"] if pack_total <= 0 else []),
                    *(["blocked_packs_present"] if blocked_pack_count else []),
                    *(["unpacked_capabilities_present"] if unpacked_entry_count else []),
                ],
            ),
            blockers=[
                *(["no_versioned_packs_detected"] if pack_total <= 0 else []),
                *(["blocked_packs_present"] if blocked_pack_count else []),
                *(["unpacked_capabilities_present"] if unpacked_entry_count else []),
            ],
            evidence={
                "pack_total": pack_total,
                "ready_pack_count": ready_pack_count,
                "blocked_pack_count": blocked_pack_count,
                "unpacked_entry_count": unpacked_entry_count,
            },
            routes=["/plugins/capabilities/catalog", "/plugins/capabilities/packs/migration/plan"],
            next_step=_safe_str(pack_readiness.get("next_smallest_truthful_gap")).strip(),
        ),
        _stage17_closure_criterion(
            criterion_id="criterion_2_pack_evidence_travels",
            title="Governance, permissions, risks, receipts, and validation travel with each pack.",
            status=_stage17_status(
                pack_total > 0,
                [
                    *(
                        ["pack_governance_or_rules_gap_present"]
                        if any(
                            key in pack_blockers
                            for key in (
                                "pack_governance_missing",
                                "promotion_rules_missing",
                                "pack_metadata_receipt_missing",
                            )
                        )
                        else []
                    ),
                    *(["validation_lineage_gap_present"] if validation_lineage_gap_count else []),
                ],
            ),
            blockers=[
                *(
                    ["pack_governance_or_rules_gap_present"]
                    if any(
                        key in pack_blockers
                        for key in (
                            "pack_governance_missing",
                            "promotion_rules_missing",
                            "pack_metadata_receipt_missing",
                        )
                    )
                    else []
                ),
                *(["validation_lineage_gap_present"] if validation_lineage_gap_count else []),
            ],
            evidence={
                "pack_blocker_counts": pack_blockers,
                "validation_lineage_gap_count": validation_lineage_gap_count,
            },
            routes=[
                "/plugins/capabilities/packs/metadata/receipts",
                "/plugins/capabilities/packs/validation/receipts",
                "/plugins/capabilities/packs/promotion/discipline",
            ],
            next_step=_safe_str(pack_readiness.get("next_smallest_truthful_gap")).strip(),
        ),
        _stage17_closure_criterion(
            criterion_id="criterion_3_executable_lifecycle",
            title=(
                "Versioning, migration, testing, promotion, quarantine, deprecation, "
                "and documentation are executable lifecycle behavior."
            ),
            status=_stage17_status(True, []),
            blockers=[],
            evidence={
                "migration_route": "/plugins/capabilities/packs/migration/plan",
                "quality_routes": [
                    "/plugins/capabilities/packs/quality/standards",
                    "/plugins/capabilities/packs/quality/tests",
                    "/plugins/capabilities/packs/quality/docs",
                ],
                "promotion_routes": [
                    "/plugins/capabilities/library/promotion/plan",
                    _CAPABILITY_LIBRARY_EXPLICIT_PROMOTION_APPLY_ROUTE,
                ],
                "plugin_quarantine_deprecation_routes": ["/plugins/disable", "/plugins/uninstall"],
                "plugin_lifecycle_repair_route": _PLUGIN_LIFECYCLE_REPAIR_ROUTE,
                "lifecycle_guard_contract": "plugin.lifecycle.quarantine_deprecation_v1",
                "lifecycle_repair_contract": "plugin.lifecycle.repair_restore_v1",
                "lifecycle_guard_readback_fields": [
                    "readiness.evidence.lifecycle",
                    "promotion_plan.packs.capabilities.lifecycle",
                    "promotion_receipt.lifecycle",
                    "run_denial.lifecycle",
                ],
                "lifecycle_guard_blocks": [
                    "explicit_quarantine",
                    "explicit_deprecation",
                    "unknown_explicit_lifecycle_state",
                ],
            },
            routes=[
                "/plugins/capabilities/packs/migration/plan",
                "/plugins/capabilities/packs/quality/standards",
                "/plugins/capabilities/library/promotion/plan",
                _CAPABILITY_LIBRARY_EXPLICIT_PROMOTION_APPLY_ROUTE,
                "/plugins/disable",
                _PLUGIN_LIFECYCLE_REPAIR_ROUTE,
                "/plugins/run",
            ],
            next_step="continue_stage17_remaining_non_lifecycle_blockers",
        ),
        _stage17_closure_criterion(
            criterion_id="criterion_4_catalog_coherence",
            title="The catalog is discoverable, deduplicated, curated, and maintainable.",
            status=_stage17_status(
                bool(all_items),
                [
                    *(["duplicate_capabilities_present"] if duplicate_capability_count else []),
                    *(["duplicate_proposal_lineage_present"] if duplicate_proposal_count else []),
                    *(["lineage_gaps_present"] if lineage_gap_count else []),
                    *(["validation_lineage_gaps_present"] if validation_lineage_gap_count else []),
                    *(["quality_gaps_present"] if quality_gap_count else []),
                ],
            ),
            blockers=[
                *(["duplicate_capabilities_present"] if duplicate_capability_count else []),
                *(["duplicate_proposal_lineage_present"] if duplicate_proposal_count else []),
                *(["lineage_gaps_present"] if lineage_gap_count else []),
                *(["validation_lineage_gaps_present"] if validation_lineage_gap_count else []),
                *(["quality_gaps_present"] if quality_gap_count else []),
            ],
            evidence={
                "catalog_readback_fields": [
                    "summary",
                    "coherence",
                    "pack_readiness",
                    "stage17_closure_matrix",
                ],
                "catalog_path": _safe_str(catalog.get("path")).strip(),
                "catalog_total_plugins": _count_value(catalog.get("total_plugins")),
                "coherence_report": "/plugins/capabilities/catalog",
            },
            blocker_counts={
                "duplicate_capabilities": duplicate_capability_count,
                "duplicate_proposals": duplicate_proposal_count,
                "lineage_gaps": lineage_gap_count,
                "validation_lineage_gaps": validation_lineage_gap_count,
                "quality_gaps": quality_gap_count,
            },
            routes=["/plugins/capabilities/catalog"],
            next_step="stage17_catalog_coherence_remediation",
        ),
        _stage17_closure_criterion(
            criterion_id="criterion_5_governed_operator_paths",
            title="Operators can inspect, evaluate, promote, invoke, and maintain packs through governed paths.",
            status=_stage17_status(bool(all_items), []),
            blockers=[] if all_items else ["no_capability_catalog_entries"],
            evidence={
                "inspect_routes": [
                    "/plugins/capabilities/catalog",
                    "/plugins/capabilities/packs/operator/surface",
                ],
                "evaluate_routes": [
                    "/plugins/capabilities/packs/promotion/discipline",
                    "/plugins/capabilities/library/proposal-review/plan",
                ],
                "promote_routes": [
                    "/plugins/enable",
                    _CAPABILITY_LIBRARY_EXPLICIT_PROMOTION_APPLY_ROUTE,
                ],
                "invoke_route": "/plugins/run",
                "maintain_routes": ["/plugins/disable", "/plugins/uninstall"],
            },
            routes=[
                "/plugins/capabilities/packs/operator/surface",
                "/plugins/capabilities/library/proposal-review/plan",
                _CAPABILITY_LIBRARY_EXPLICIT_PROMOTION_APPLY_ROUTE,
                "/plugins/run",
            ],
            next_step="stage17_operator_surface_end_to_end_receipts",
        ),
        _stage17_closure_criterion(
            criterion_id="criterion_6_reuse_leverage",
            title="Reuse creates visible leverage across multiple real contexts.",
            status="partial" if all_items else "blocked",
            blockers=(
                ["multi_context_reuse_receipts_not_proven_by_catalog_readback"]
                if all_items
                else ["no_capability_catalog_entries"]
            ),
            evidence={
                "catalog_entry_count": len(all_items),
                "distinct_sources": sorted(
                    {
                        _safe_str(item.get("source")).strip()
                        for item in all_items
                        if _safe_str(item.get("source")).strip()
                    }
                ),
                "distinct_statuses": sorted(
                    {
                        _safe_str(item.get("status")).strip()
                        for item in all_items
                        if _safe_str(item.get("status")).strip()
                    }
                ),
                "claim_boundary": "catalog evidence does not prove reuse across real operator contexts",
            },
            routes=["/plugins/capabilities/catalog"],
            next_step="stage17_reuse_leverage_receipts",
        ),
    ]

    weakest = _stage17_weakest_closure_criterion(criteria)
    all_criteria_ready = all(_safe_str(item.get("status")).strip() == "ready" for item in criteria)
    return {
        "kind": "plugin.capability_catalog.stage17_closure_matrix",
        "stage": "Stage 17 / Capability Economy",
        "status": "ready_for_closure_review" if all_criteria_ready else "open",
        "closure_claimed": False,
        "all_criteria_ready": all_criteria_ready,
        "weakest_criterion": weakest,
        "criteria": criteria,
        "governance": {
            "read_only": True,
            "derived_from_existing_catalog_readbacks": True,
            "writes_repo": False,
            "writes_data": False,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "does_not_claim_stage17_closure": True,
            "closure_authority": False,
            "promotion_authority": False,
            "execution_authority": False,
        },
        "source_readbacks": {
            "catalog_route": "/plugins/capabilities/catalog",
            "coherence_field": "coherence",
            "pack_readiness_field": "pack_readiness",
        },
    }


def _stage17_list_count(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    return len(value) if isinstance(value, list) else _count_value(value)


def _stage17_status(evidence_present: bool, blockers: list[str]) -> str:
    if not evidence_present:
        return "blocked"
    return "ready" if not blockers else "partial"


def _stage17_pack_blocker_counts(pack_readiness: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    packs = pack_readiness.get("packs") if isinstance(pack_readiness.get("packs"), list) else []
    for pack in packs:
        if not isinstance(pack, dict):
            continue
        for blocker in _unique_texts(pack.get("blockers"), limit=100):
            counts[blocker] = counts.get(blocker, 0) + 1
    return dict(sorted(counts.items()))


def _stage17_closure_criterion(
    *,
    criterion_id: str,
    title: str,
    status: str,
    blockers: list[str],
    evidence: dict[str, Any],
    routes: list[str],
    next_step: str,
    blocker_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    out = {
        "id": criterion_id,
        "criterion": title,
        "status": status,
        "blockers": blockers,
        "blocker_counts": blocker_counts or {},
        "evidence": evidence,
        "routes": routes,
        "next_step": next_step,
    }
    return out


def _stage17_weakest_closure_criterion(criteria: list[dict[str, Any]]) -> dict[str, Any]:
    severity = {"blocked": 3, "partial": 2, "ready": 1}
    weakest = max(
        criteria,
        key=lambda item: (
            severity.get(_safe_str(item.get("status")).strip(), 0),
            len(item.get("blockers") if isinstance(item.get("blockers"), list) else []),
        ),
    )
    return {
        "id": _safe_str(weakest.get("id")).strip(),
        "criterion": _safe_str(weakest.get("criterion")).strip(),
        "status": _safe_str(weakest.get("status")).strip(),
        "blockers": weakest.get("blockers") if isinstance(weakest.get("blockers"), list) else [],
        "next_step": _safe_str(weakest.get("next_step")).strip(),
    }


def _write_reconstructed_validation_receipt(
    *,
    plugin_id: str,
    validation_id: str,
    validation_path: Path,
    proposal_id: str,
    proposal_path: str,
    pack_id: str,
    pack_version: str,
    pack_name: str,
    current: dict[str, Any],
    meta: dict[str, Any],
    tests: list[str],
    docs: list[str],
    actor: str,
    reason: str,
    recorded_ts: int,
    route_path: str,
) -> dict[str, Any]:
    receipt = {
        "kind": "plugin.validation.receipt",
        "validation_id": validation_id,
        "validation_receipt_id": validation_id,
        "plugin_id": plugin_id,
        "proposal_id": proposal_id,
        "status": "passed",
        "valid": True,
        "validated_ts": recorded_ts,
        "actor": redact_governed_value(_safe_str(actor).strip()),
        "reason": redact_governed_value(_safe_str(reason).strip() or "stage17_artifact_reconstruction"),
        "proposal_path": proposal_path,
        "artifact_zip": _safe_str(meta.get("artifact_zip") or current.get("artifact_zip")).strip(),
        "spec_path": _safe_str(meta.get("spec_path") or current.get("spec_path")).strip(),
        "registry_snapshot": _safe_str(meta.get("registry_snapshot_path")).strip(),
        "pack": {
            "pack_id": pack_id,
            "pack_version": pack_version,
            "pack_name": pack_name,
            "pack_metadata_receipt_id": _safe_str(meta.get("pack_metadata_receipt_id")).strip(),
        },
        "validation": {
            "valid": True,
            "status": "reconstructed_from_existing_registry_evidence",
            "tests": tests,
            "docs": docs,
            "claim_scope": "pack_specific_validation_receipt_reconstructed_from_registry_evidence",
            "new_test_execution_claimed": False,
        },
        "governance": {
            "gate": "capability_pack_artifact_reconstruction",
            "scope": _PLUGIN_WRITE_SCOPE,
            "route": route_path,
            "writes_validation_receipt": True,
            "writes_proposal": False,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
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


def _write_reconstructed_proposal_lineage(
    *,
    plugin_id: str,
    proposal_id: str,
    proposal_path: Path,
    pack_id: str,
    pack_version: str,
    pack_name: str,
    current: dict[str, Any],
    meta: dict[str, Any],
    tests: list[str],
    docs: list[str],
    actor: str,
    reason: str,
    recorded_ts: int,
    route_path: str,
) -> dict[str, Any]:
    record = {
        "kind": "plugin.proposal",
        "proposal_id": proposal_id,
        "plugin_id": plugin_id,
        "status": "reconstructed_lineage",
        "created_ts": recorded_ts,
        "actor": redact_governed_value(_safe_str(actor).strip()),
        "friction": {
            "summary": _safe_str(meta.get("friction_summary")).strip()
            or f"Reconstructed proposal lineage for {plugin_id}",
            "evidence": _unique_texts(meta.get("proposal_evidence") or meta.get("evidence"), limit=50),
            "recurrence_count": meta.get("recurrence_count"),
        },
        "proposed_capability": {
            "name": _safe_str(current.get("name") or plugin_id).strip(),
            "description": _safe_str(current.get("description")).strip(),
            "inputs": _unique_texts(meta.get("inputs") or meta.get("input_requirements"), limit=50),
            "scope": _safe_str(meta.get("scope") or meta.get("expected_scope")).strip() or "local_generated_plugin",
            "expected_benefit": _safe_str(meta.get("expected_benefit") or meta.get("benefit")).strip(),
        },
        "quality_requirements": {
            "risk_tier": _safe_str(meta.get("risk_tier")).strip().lower() or _plugin_risk_tier(current),
            "tests": tests,
            "docs": docs,
            "known_limits": _unique_texts(meta.get("known_limits") or meta.get("limits"), limit=50),
        },
        "staged_implementation": {
            "status": _safe_str(current.get("status")).strip(),
            "enabled": bool(current.get("enabled")),
            "artifact_zip": _safe_str(meta.get("artifact_zip") or current.get("artifact_zip")).strip(),
            "spec_path": _safe_str(meta.get("spec_path") or current.get("spec_path")).strip(),
            "registry_snapshot": _safe_str(meta.get("registry_snapshot_path")).strip(),
        },
        "pack": {
            "pack_id": pack_id,
            "pack_version": pack_version,
            "pack_name": pack_name,
            "pack_metadata_receipt_id": _safe_str(meta.get("pack_metadata_receipt_id")).strip(),
        },
        "review": {
            "status": "not_reviewed",
            "approval_claimed": False,
            "review_receipt_id": "",
        },
        "proposal_context": {
            "reconstruction_source": _CAPABILITY_PACK_ARTIFACT_RECONSTRUCTION_SOURCE,
            "reason": redact_governed_value(_safe_str(reason).strip() or "stage17_artifact_reconstruction"),
            "original_proposal_claimed": False,
        },
        "governance": {
            "gate": "capability_pack_artifact_reconstruction",
            "scope": _PLUGIN_WRITE_SCOPE,
            "route": route_path,
            "writes_proposal_lineage": True,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "memory_write": False,
        },
        "path": str(proposal_path),
    }
    redacted_record = redact_governed_display_value(record)
    out = redacted_record if isinstance(redacted_record, dict) else {}
    _atomic_write_json(proposal_path, out)
    return out


def _record_capability_pack_artifact_reconstruction_batch(
    *,
    registry: dict[str, Any],
    prepared: list[dict[str, Any]],
    payload: "CapabilityPackQualityEvidenceReconstructionApplyIn",
    route_path: str,
) -> dict[str, list[dict[str, Any]]]:
    recorded_ts = _now_s()
    failed: list[dict[str, Any]] = []
    recorded: list[dict[str, Any]] = []
    changed = False

    for item in prepared:
        pack_id = _safe_str(item.get("pack_id")).strip()
        pack_version = _safe_str(item.get("pack_version")).strip()
        pack_name = _safe_str(item.get("pack_name")).strip() or pack_id
        capabilities = item.get("capabilities") if isinstance(item.get("capabilities"), list) else []
        required_capability_count = int(item.get("required_capability_count") or len(capabilities))
        capabilities_truncated = bool(item.get("capabilities_truncated"))
        partial_reconstruction = bool(item.get("partial_reconstruction"))
        reconstructed_capability_ids: list[str] = []
        validation_receipts: list[dict[str, str]] = []
        proposal_lineages: list[dict[str, str]] = []

        for capability in capabilities:
            if not isinstance(capability, dict):
                continue
            capability_id = _safe_str(capability.get("capability")).strip()
            current = _read_plugin(registry, capability_id)
            if current is None:
                failed.append(
                    {
                        "pack_id": pack_id,
                        "pack_version": pack_version,
                        "capability": capability_id,
                        "status": "blocked",
                        "error": "capability_not_found",
                    }
                )
                continue
            meta = dict(current.get("meta") or {}) if isinstance(current.get("meta"), dict) else {}
            quality = dict(meta.get("quality") or {}) if isinstance(meta.get("quality"), dict) else {}
            tests, docs = _quality_references_from_reconstruction_capability(capability)
            needs_validation = bool(capability.get("needs_validation_receipt"))
            needs_proposal = bool(capability.get("needs_proposal_lineage"))
            changed_capability = False

            proposal_id = _safe_str(meta.get("proposal_id") or meta.get("forge_proposal_id")).strip()
            proposal_link_path = _safe_str(meta.get("proposal_path")).strip()
            if needs_proposal and not proposal_id:
                proposal_id = _plugin_proposal_id(capability_id, recorded_ts)
                proposal_path = _plugin_proposal_path(proposal_id)
                proposal_link_path = _plugin_artifact_relative_path("proposals", proposal_id)
                _write_reconstructed_proposal_lineage(
                    plugin_id=capability_id,
                    proposal_id=proposal_id,
                    proposal_path=proposal_path,
                    pack_id=pack_id,
                    pack_version=pack_version,
                    pack_name=pack_name,
                    current=current,
                    meta=meta,
                    tests=tests,
                    docs=docs,
                    actor=payload.actor,
                    reason=payload.reason,
                    recorded_ts=recorded_ts,
                    route_path=route_path,
                )
                meta["proposal_id"] = proposal_id
                meta["proposal_path"] = proposal_link_path
                meta["proposal_lineage_reconstruction_source"] = _CAPABILITY_PACK_ARTIFACT_RECONSTRUCTION_SOURCE
                meta["proposal_lineage_claim_scope"] = "reconstructed_plugin_proposal_lineage_only_not_approval"
                meta["proposal_lineage_approval_claimed"] = False
                meta["proposal_status"] = "reconstructed_lineage_unreviewed"
                proposal_lineages.append(
                    {"capability": capability_id, "proposal_id": proposal_id, "path": proposal_link_path}
                )
                changed_capability = True

            validation_id = _safe_str(meta.get("validation_receipt_id")).strip()
            if needs_validation and not validation_id:
                validation_id = _plugin_validation_receipt_id(capability_id, recorded_ts)
                validation_path = _plugin_validation_receipt_path(validation_id)
                validation_link_path = _plugin_artifact_relative_path("validations", validation_id)
                _write_reconstructed_validation_receipt(
                    plugin_id=capability_id,
                    validation_id=validation_id,
                    validation_path=validation_path,
                    proposal_id=proposal_id,
                    proposal_path=proposal_link_path,
                    pack_id=pack_id,
                    pack_version=pack_version,
                    pack_name=pack_name,
                    current=current,
                    meta=meta,
                    tests=tests,
                    docs=docs,
                    actor=payload.actor,
                    reason=payload.reason,
                    recorded_ts=recorded_ts,
                    route_path=route_path,
                )
                meta["validation_receipt_id"] = validation_id
                meta["validation_receipt_path"] = validation_link_path
                meta["validation_receipt_reconstruction_source"] = _CAPABILITY_PACK_ARTIFACT_RECONSTRUCTION_SOURCE
                meta["validation_receipt_link_claim_scope"] = (
                    "pack_specific_validation_receipt_reconstructed_from_registry_evidence"
                )
                meta["validation_receipt_reconstructed"] = True
                quality["validation_receipt_written"] = True
                validation_receipts.append(
                    {"capability": capability_id, "validation_receipt_id": validation_id, "path": validation_link_path}
                )
                changed_capability = True

            if changed_capability:
                quality["proposal_lineage_written"] = bool(meta.get("proposal_id"))
                quality["pack_specific_coverage_claimed"] = False
                quality["reconstruction_source"] = _CAPABILITY_PACK_ARTIFACT_RECONSTRUCTION_SOURCE
                meta["quality"] = quality
                meta["artifact_reconstruction_source"] = _CAPABILITY_PACK_ARTIFACT_RECONSTRUCTION_SOURCE
                meta["artifact_reconstruction_route"] = route_path
                meta["artifact_reconstruction_ts"] = recorded_ts
                meta["artifact_reconstruction_decision"] = "approved_for_reconstruction"
                if partial_reconstruction:
                    meta["artifact_reconstruction_partial_pack"] = True
                    meta["artifact_reconstruction_pack_required_capability_count"] = required_capability_count
                    meta["artifact_reconstruction_pack_chunk_capability_count"] = len(capabilities)
                current["meta"] = meta
                current["updated_ts"] = recorded_ts
                _write_plugin(registry, _normalize_plugin_record(capability_id, current))
                changed = True
                reconstructed_capability_ids.append(capability_id)

        recorded.append(
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "capability_count": len(capabilities),
                "required_capability_count": required_capability_count,
                "capabilities_truncated": capabilities_truncated,
                "partial_reconstruction": partial_reconstruction,
                "partial_reconstruction_does_not_claim_pack_complete": partial_reconstruction,
                "reconstructed_capability_count": len(reconstructed_capability_ids),
                "reconstructed_capability_ids": reconstructed_capability_ids[:50],
                "reconstructed_capability_ids_truncated": len(reconstructed_capability_ids) > 50,
                "validation_receipts": validation_receipts,
                "proposal_lineages": proposal_lineages,
                "status": "recorded" if reconstructed_capability_ids else "unchanged",
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


_CAPABILITY_PACK_INVOCATION_RECEIPT_KIND = "plugin.capability_pack.invocation_receipt"
_CAPABILITY_PACK_INVOCATION_RECEIPT_CONTRACT = "stage17_capability_pack_reusable_invocation_receipt_v1"
_CAPABILITY_PACK_INVOCATION_ROUTING_GUARD_CONTRACT = "stage17_capability_pack_invocation_routing_guard_v1"
_MISSION_OPERATION_CONTEXT_BY_CAPABILITY = {
    "plugin.run": "mission_linked_operation",
    "plugin.tool.run": "mission_linked_tool_operation",
}


def _capability_pack_invocation_selection(
    *,
    plugin: dict[str, Any],
    capability: dict[str, Any],
    action: str,
) -> dict[str, object]:
    plugin_id = _safe_str(plugin.get("id")).strip()
    plugin_meta = dict(plugin.get("meta") or {}) if isinstance(plugin.get("meta"), dict) else {}
    cap_meta = dict(capability.get("meta") or {}) if isinstance(capability.get("meta"), dict) else {}
    pack_id = _safe_str(plugin_meta.get("pack_id") or plugin_meta.get("capability_pack_id")).strip()
    pack_version = _safe_str(plugin_meta.get("pack_version") or plugin_meta.get("capability_pack_version")).strip()
    capability_id = _safe_str(capability.get("id")).strip() or f"{plugin_id}.{action or 'run'}"
    pack_reuse_key = (
        f"{pack_id}@{pack_version}:{capability_id}" if pack_id or pack_version else f"unpacked:{capability_id}"
    )
    pack_name = redact_governed_value(_safe_str(plugin_meta.get("pack_name") or pack_id).strip())
    return {
        "contract": "stage17_capability_pack_invocation_selection_v1",
        "source": "plugin_registry_metadata",
        "plugin_id": plugin_id,
        "capability_id": capability_id,
        "action": _safe_str(action).strip(),
        "tool_name": _safe_str(cap_meta.get("tool_name")).strip() or capability_id,
        "pack_id": pack_id,
        "pack_version": pack_version,
        "pack_name": _safe_str(pack_name).strip(),
        "pack_reuse_key": pack_reuse_key,
        "supported_caller_contexts": [
            "direct_plugin_route",
            "plugin_tool_route",
            "mission_linked_operation",
            "mission_linked_tool_operation",
        ],
        "duplicates_plugin_execution_logic": False,
    }


def _capability_pack_invocation_receipt(
    *,
    plugin: dict[str, Any],
    capability: dict[str, Any],
    action: str,
    payload_meta: dict[str, Any],
    receipt: dict[str, Any],
    risk_tier: str,
    required_trust: int,
    current_trust: int,
    dry_run: bool,
) -> dict[str, object]:
    plugin_meta = dict(plugin.get("meta") or {}) if isinstance(plugin.get("meta"), dict) else {}
    selection = _capability_pack_invocation_selection(plugin=plugin, capability=capability, action=action)
    plugin_id = _safe_str(selection.get("plugin_id")).strip()
    capability_id = _safe_str(selection.get("capability_id")).strip()
    tool_name = _safe_str(selection.get("tool_name")).strip()
    pack_id = _safe_str(selection.get("pack_id")).strip()
    pack_version = _safe_str(selection.get("pack_version")).strip()
    pack_name = _safe_str(selection.get("pack_name")).strip()
    pack_reuse_key = _safe_str(selection.get("pack_reuse_key")).strip()
    sandbox = receipt.get("sandbox") if isinstance(receipt.get("sandbox"), dict) else {}
    caller_context = redact_governed_value(_safe_str(payload_meta.get("caller_context")).strip())
    promotion_receipt_id = _safe_str(plugin_meta.get("promotion_receipt_id")).strip()
    proposal_review_receipt_id = _safe_str(plugin_meta.get("proposal_review_receipt_id")).strip()
    pack_operator_review_receipt_id = _safe_str(plugin_meta.get("pack_operator_review_receipt_id")).strip()
    validation_receipt_id = _safe_str(plugin_meta.get("validation_receipt_id")).strip()
    supported_caller_contexts = selection.get("supported_caller_contexts")
    if not isinstance(supported_caller_contexts, list):
        supported_caller_contexts = []
    invocation_mode = "dry_run" if dry_run else "live_dispatch"
    return {
        "kind": _CAPABILITY_PACK_INVOCATION_RECEIPT_KIND,
        "stage": "Stage 17 / Capability Economy",
        "contract": _CAPABILITY_PACK_INVOCATION_RECEIPT_CONTRACT,
        "status": _safe_str(receipt.get("status")).strip() or ("dry_run" if dry_run else "unknown"),
        "invocation_mode": invocation_mode,
        "dry_run": dry_run,
        "caller_context": _safe_str(caller_context).strip(),
        "plugin_id": plugin_id,
        "capability_id": capability_id,
        "action": _safe_str(action).strip(),
        "tool_name": tool_name,
        "pack_id": pack_id,
        "pack_version": pack_version,
        "pack_name": pack_name,
        "pack_reuse_key": pack_reuse_key,
        "pack_selection": selection,
        "receipt_linkage": {
            "dispatch_receipt_present": True,
            "dispatch_status": _safe_str(receipt.get("status")).strip(),
            "run_id": _safe_str(receipt.get("run_id")).strip(),
            "trace_id": _safe_str(receipt.get("trace_id")).strip(),
            "sandbox_status": _safe_str(sandbox.get("status")).strip(),
            "sandbox_run_id": _safe_str(sandbox.get("run_id")).strip(),
            "sandbox_trace_id": _safe_str(sandbox.get("trace_id")).strip(),
        },
        "evidence": {
            "promotion_status": _safe_str(plugin_meta.get("promotion_status")).strip(),
            "promotion_receipt_id": promotion_receipt_id,
            "proposal_id": _safe_str(plugin_meta.get("proposal_id") or plugin_meta.get("forge_proposal_id")).strip(),
            "proposal_review_receipt_id": proposal_review_receipt_id,
            "validation_receipt_id": validation_receipt_id,
            "pack_operator_review_receipt_id": pack_operator_review_receipt_id,
        },
        "reuse": {
            "pack_selection_source": _safe_str(selection.get("source")).strip(),
            "pack_selection_contract": _safe_str(selection.get("contract")).strip(),
            "supported_caller_contexts": list(supported_caller_contexts),
            "direct_plugin_route": "/plugins/run",
            "plugin_tool_route": "/plugins/tools/run",
            "operation_capability": "plugin.run",
            "operation_tool_capability": "plugin.tool.run",
            "mission_context": "mission_linked_operation",
            "mission_tool_context": "mission_linked_tool_operation",
            "duplicates_plugin_execution_logic": False,
        },
        "governance": {
            "plane": "P3_GOVERNANCE",
            "permission_model": "plugin_runtime_trust_and_approval_gates",
            "uses_existing_plugin_dispatcher": True,
            "uses_existing_sandbox_runner": True,
            "promotion_required_before_invocation": True,
            "risk_tier": risk_tier,
            "required_trust": required_trust,
            "current_trust": current_trust,
            "approval_required_when_risk_requires": True,
            "new_authority_granted_by_receipt": False,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "memory_write": False,
        },
    }


def _capability_pack_invocation_routing_guard(
    *,
    operation_capability: str,
    invocation: dict[str, Any],
) -> dict[str, object]:
    capability = _safe_str(operation_capability).strip()
    caller_context = _safe_str(invocation.get("caller_context")).strip()
    expected_context = _MISSION_OPERATION_CONTEXT_BY_CAPABILITY.get(capability, "")
    governance = invocation.get("governance") if isinstance(invocation.get("governance"), dict) else {}

    receipt_kind_supported = _safe_str(invocation.get("kind")).strip() == _CAPABILITY_PACK_INVOCATION_RECEIPT_KIND
    receipt_contract_supported = (
        _safe_str(invocation.get("contract")).strip() == _CAPABILITY_PACK_INVOCATION_RECEIPT_CONTRACT
    )
    operation_capability_supported = bool(expected_context)
    caller_context_matches_operation_capability = bool(expected_context and caller_context == expected_context)
    uses_existing_plugin_dispatcher = _to_bool(governance.get("uses_existing_plugin_dispatcher"))
    new_authority_granted_by_receipt = _to_bool(governance.get("new_authority_granted_by_receipt"))
    promotes_capabilities = not _to_bool(governance.get("does_not_promote_capabilities"))
    enables_capabilities = not _to_bool(governance.get("does_not_enable_capabilities"))
    memory_write = _to_bool(governance.get("memory_write"))
    governance_bound = (
        uses_existing_plugin_dispatcher
        and not new_authority_granted_by_receipt
        and not promotes_capabilities
        and not enables_capabilities
        and not memory_write
    )

    reject_reasons: list[str] = []
    if not operation_capability_supported:
        reject_reasons.append("unsupported_operation_capability")
    if not receipt_kind_supported:
        reject_reasons.append("unsupported_receipt_kind")
    if not receipt_contract_supported:
        reject_reasons.append("unsupported_receipt_contract")
    if not caller_context_matches_operation_capability:
        reject_reasons.append("caller_context_operation_capability_mismatch")
    if not governance_bound:
        reject_reasons.append("governance_boundary_missing")

    return {
        "contract": _CAPABILITY_PACK_INVOCATION_ROUTING_GUARD_CONTRACT,
        "operation_capability": capability,
        "caller_context": caller_context,
        "expected_caller_context": expected_context,
        "operation_capability_supported": operation_capability_supported,
        "receipt_kind_supported": receipt_kind_supported,
        "receipt_contract_supported": receipt_contract_supported,
        "caller_context_matches_operation_capability": caller_context_matches_operation_capability,
        "governance_bound": governance_bound,
        "uses_existing_plugin_dispatcher": uses_existing_plugin_dispatcher,
        "new_authority_granted_by_receipt": new_authority_granted_by_receipt,
        "promotes_capabilities": promotes_capabilities,
        "enables_capabilities": enables_capabilities,
        "memory_write": memory_write,
        "eligible_for_reuse_proof": not reject_reasons,
        "reject_reasons": reject_reasons,
    }


def _capability_pack_invocation_audit_task_records(*, scan_limit: int) -> list[dict[str, Any]]:
    root = data_dir() / "tasks"
    if not root.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        task_dirs = [item for item in root.iterdir() if item.is_dir()]
        task_dirs.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    except Exception:
        return []

    for task_dir in task_dirs[: max(1, min(int(scan_limit), 5000))]:
        record_path = task_dir / "record.json"
        if not record_path.exists():
            continue
        try:
            raw = json.loads(record_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(raw, dict):
            records.append(raw)
    return records


def _capability_pack_invocation_from_task(task: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    result = task.get("result") if isinstance(task.get("result"), dict) else {}
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    invocation = (
        data.get("capability_pack_invocation") if isinstance(data.get("capability_pack_invocation"), dict) else {}
    )
    receipt = data.get("receipt") if isinstance(data.get("receipt"), dict) else {}
    if not invocation and isinstance(receipt.get("capability_pack_invocation"), dict):
        invocation = receipt["capability_pack_invocation"]
    return data, invocation if isinstance(invocation, dict) else {}


def _capability_pack_invocation_audit_projection(
    *,
    pack_id: str = "",
    pack_version: str = "",
    plugin_id: str = "",
    capability_id: str = "",
    limit: int = 200,
    scan_limit: int = 5000,
) -> dict[str, object]:
    safe_limit = max(1, min(int(limit), 500))
    safe_scan_limit = max(safe_limit, min(int(scan_limit), 5000))
    filter_pack_id = _safe_str(pack_id).strip()
    filter_pack_version = _safe_str(pack_version).strip()
    filter_plugin_id = _safe_str(plugin_id).strip()
    filter_capability_id = _safe_str(capability_id).strip()

    items: list[dict[str, object]] = []
    rejected_items: list[dict[str, object]] = []
    for task in _capability_pack_invocation_audit_task_records(scan_limit=safe_scan_limit):
        operation_capability = _safe_str(task.get("capability")).strip()
        if operation_capability not in _MISSION_OPERATION_CONTEXT_BY_CAPABILITY:
            continue
        data, invocation = _capability_pack_invocation_from_task(task)
        if not invocation:
            continue
        item_pack_id = _safe_str(invocation.get("pack_id")).strip()
        item_pack_version = _safe_str(invocation.get("pack_version")).strip()
        item_plugin_id = _safe_str(invocation.get("plugin_id")).strip()
        item_capability_id = _safe_str(invocation.get("capability_id")).strip()
        if filter_pack_id and item_pack_id != filter_pack_id:
            continue
        if filter_pack_version and item_pack_version != filter_pack_version:
            continue
        if filter_plugin_id and item_plugin_id != filter_plugin_id:
            continue
        if filter_capability_id and item_capability_id != filter_capability_id:
            continue

        routing_guard = _capability_pack_invocation_routing_guard(
            operation_capability=operation_capability,
            invocation=invocation,
        )
        inputs = task.get("inputs") if isinstance(task.get("inputs"), dict) else {}
        input_meta = inputs.get("meta") if isinstance(inputs.get("meta"), dict) else {}
        receipt_linkage = (
            invocation.get("receipt_linkage") if isinstance(invocation.get("receipt_linkage"), dict) else {}
        )
        selection = invocation.get("pack_selection") if isinstance(invocation.get("pack_selection"), dict) else {}
        reuse = invocation.get("reuse") if isinstance(invocation.get("reuse"), dict) else {}
        governance = invocation.get("governance") if isinstance(invocation.get("governance"), dict) else {}
        item = {
            "operation_id": _safe_str(task.get("task_id")).strip(),
            "operation_status": _safe_str(task.get("status")).strip(),
            "operation_capability": operation_capability,
            "mission_id": _safe_str(inputs.get("mission_id") or input_meta.get("mission_id")).strip(),
            "receipt_kind": _safe_str(invocation.get("kind")).strip(),
            "receipt_contract": _safe_str(invocation.get("contract")).strip(),
            "receipt_embedded_in_operation_output": True,
            "invocation_mode": _safe_str(invocation.get("invocation_mode")).strip(),
            "caller_context": _safe_str(invocation.get("caller_context")).strip(),
            "plugin_id": item_plugin_id,
            "capability_id": item_capability_id,
            "action": _safe_str(invocation.get("action")).strip(),
            "pack_id": item_pack_id,
            "pack_version": item_pack_version,
            "pack_reuse_key": _safe_str(invocation.get("pack_reuse_key")).strip(),
            "pack_selection_contract": _safe_str(
                selection.get("contract") or reuse.get("pack_selection_contract")
            ).strip(),
            "pack_selection_source": _safe_str(selection.get("source") or reuse.get("pack_selection_source")).strip(),
            "dispatch_status": _safe_str(receipt_linkage.get("dispatch_status")).strip(),
            "run_id": _safe_str(receipt_linkage.get("run_id") or data.get("run_id")).strip(),
            "trace_id": _safe_str(receipt_linkage.get("trace_id") or data.get("trace_id")).strip(),
            "routing_guard": routing_guard,
            "governance": {
                "permission_model": _safe_str(governance.get("permission_model")).strip(),
                "uses_existing_plugin_dispatcher": _to_bool(governance.get("uses_existing_plugin_dispatcher")),
                "promotion_required_before_invocation": _to_bool(
                    governance.get("promotion_required_before_invocation")
                ),
                "new_authority_granted_by_receipt": _to_bool(governance.get("new_authority_granted_by_receipt")),
                "does_not_promote_capabilities": _to_bool(governance.get("does_not_promote_capabilities")),
                "does_not_enable_capabilities": _to_bool(governance.get("does_not_enable_capabilities")),
                "memory_write": _to_bool(governance.get("memory_write")),
            },
        }
        if bool(routing_guard.get("eligible_for_reuse_proof")):
            items.append(item)
        else:
            rejected_items.append(item)

    returned = items[:safe_limit]
    returned_rejected = rejected_items[:safe_limit]
    contexts = sorted(
        {
            str(item.get("caller_context") or "").strip()
            for item in items
            if str(item.get("caller_context") or "").strip()
        }
    )
    pack_reuse_keys = sorted(
        {
            str(item.get("pack_reuse_key") or "").strip()
            for item in items
            if str(item.get("pack_reuse_key") or "").strip()
        }
    )
    pack_ids = sorted(
        {str(item.get("pack_id") or "").strip() for item in items if str(item.get("pack_id") or "").strip()}
    )
    contexts_by_reuse_key: dict[str, set[str]] = {}
    for item in items:
        reuse_key = str(item.get("pack_reuse_key") or "").strip()
        caller_context = str(item.get("caller_context") or "").strip()
        if reuse_key and caller_context:
            contexts_by_reuse_key.setdefault(reuse_key, set()).add(caller_context)
    context_lists_by_reuse_key = {key: sorted(value) for key, value in sorted(contexts_by_reuse_key.items())}
    capabilities_by_reuse_key: dict[str, set[str]] = {}
    for item in items:
        reuse_key = str(item.get("pack_reuse_key") or "").strip()
        operation_capability = str(item.get("operation_capability") or "").strip()
        if reuse_key and operation_capability:
            capabilities_by_reuse_key.setdefault(reuse_key, set()).add(operation_capability)
    capability_lists_by_reuse_key = {key: sorted(value) for key, value in sorted(capabilities_by_reuse_key.items())}
    reused_pack_reuse_keys = [
        key for key, caller_contexts in context_lists_by_reuse_key.items() if len(caller_contexts) >= 2
    ]
    mission_linked_contexts = {"mission_linked_operation", "mission_linked_tool_operation"}
    mission_linked_reuse_keys = [
        key
        for key, caller_contexts in context_lists_by_reuse_key.items()
        if len(mission_linked_contexts.intersection(caller_contexts)) >= 2
    ]
    mission_shape_capabilities = set(_MISSION_OPERATION_CONTEXT_BY_CAPABILITY)
    mission_shape_reuse_keys = [
        key
        for key, operation_capabilities in capability_lists_by_reuse_key.items()
        if mission_shape_capabilities.issubset(operation_capabilities)
    ]
    return {
        "ok": True,
        "kind": "plugin.capability_library.invocations.audit",
        "stage": "Stage 17 / Capability Economy",
        "status": "ready" if items else "no_invocation_receipts",
        "readback_scope": "operation_outputs_with_embedded_capability_pack_invocation_receipts",
        "filters": {
            "pack_id": filter_pack_id,
            "pack_version": filter_pack_version,
            "plugin_id": filter_plugin_id,
            "capability_id": filter_capability_id,
            "limit": safe_limit,
            "scan_limit": safe_scan_limit,
        },
        "total_invocation_count": len(items),
        "rejected_invocation_count": len(rejected_items),
        "returned_invocation_count": len(returned),
        "returned_rejected_invocation_count": len(returned_rejected),
        "pack_count": len(pack_ids),
        "context_count": len(contexts),
        "contexts": contexts,
        "pack_reuse_keys": pack_reuse_keys,
        "reuse_proof": {
            "contract": "stage17_capability_pack_invocation_audit_reuse_proof_v1",
            "minimum_contexts_per_reuse_key": 2,
            "contexts_by_pack_reuse_key": context_lists_by_reuse_key,
            "operation_capabilities_by_pack_reuse_key": capability_lists_by_reuse_key,
            "cross_context_reuse_proven": bool(reused_pack_reuse_keys),
            "reused_pack_reuse_keys": reused_pack_reuse_keys,
            "mission_linked_contexts_required": sorted(mission_linked_contexts),
            "mission_linked_reuse_proven": bool(mission_linked_reuse_keys),
            "mission_linked_reuse_keys": mission_linked_reuse_keys,
            "mission_shape_capabilities_required": sorted(mission_shape_capabilities),
            "mission_shape_reuse_proven": bool(mission_shape_reuse_keys),
            "mission_shape_reuse_keys": mission_shape_reuse_keys,
        },
        "items": returned,
        "rejected_items": returned_rejected,
        "requirements": {
            "embedded_invocation_receipt_required": True,
            "embedded_invocation_receipt_contract_required": _CAPABILITY_PACK_INVOCATION_RECEIPT_CONTRACT,
            "reads_existing_operation_records": True,
            "reads_existing_plugin_run_and_tool_run_operation_records": True,
            "routing_guard_contract": _CAPABILITY_PACK_INVOCATION_ROUTING_GUARD_CONTRACT,
            "routing_guard_required_for_reuse_proof": True,
            "mission_plugin_run_context_required": _MISSION_OPERATION_CONTEXT_BY_CAPABILITY["plugin.run"],
            "mission_tool_run_context_required": _MISSION_OPERATION_CONTEXT_BY_CAPABILITY["plugin.tool.run"],
            "cross_context_reuse_claim_requires_matching_pack_reuse_key": True,
            "cross_context_reuse_proof_is_machine_readable": True,
            "mission_linked_reuse_requires_both_mission_contexts": True,
            "mission_shape_reuse_requires_plugin_run_and_plugin_tool_run": True,
            "does_not_infer_missing_direct_route_receipts": True,
        },
        "governance": {
            "read_only": True,
            "writes_repo": False,
            "writes_data": False,
            "writes_receipts": False,
            "approves_proposals": False,
            "promotes_capabilities": False,
            "enables_capabilities": False,
            "executes_capabilities": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "memory_write": False,
        },
    }


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


class PluginLifecycleRepairIn(PluginToggleIn):
    dry_run: bool = True
    dry_run_fingerprint: str = ""


class CapabilityPackOperatorReviewDecisionIn(BaseModel):
    pack_id: str
    pack_version: str
    action: str
    actor: str = ""
    reason: str = "requested"
    notes: str = ""
    capability_ids: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class CapabilityPackOperatorReviewBulkDecisionFromSurfaceIn(BaseModel):
    action: str
    actor: str = ""
    reason: str = "stage17_capability_pack_operator_review_bulk_decision"
    notes: str = ""
    pack_ids: list[str] = Field(default_factory=list)
    max_pack_count: int = 10
    max_total_capability_count: int = 5000
    dry_run: bool = True
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
    dry_run: bool = True
    dry_run_fingerprint: str = ""
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


class CapabilityPackQualityStandardRemediationApplyIn(BaseModel):
    actor: str = ""
    reason: str = "stage17_quality_standard_remediation"
    pack_ids: list[str] = Field(default_factory=list)
    max_pack_count: int = 10
    max_total_capability_count: int = 1000
    max_capability_count_per_pack: int = 500
    dry_run: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)


class CapabilityPackQualityEvidenceReconstructionApplyIn(BaseModel):
    actor: str = ""
    reason: str = "stage17_artifact_reconstruction"
    pack_ids: list[str] = Field(default_factory=list)
    max_pack_count: int = 5
    max_total_capability_count: int = 100
    max_capability_count_per_pack: int = 50
    dry_run: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)


class CapabilityLibraryProposalEvidenceRemediationApplyIn(BaseModel):
    actor: str = ""
    reason: str = "stage17_proposal_evidence_remediation"
    pack_ids: list[str] = Field(default_factory=list)
    max_pack_count: int = 10
    max_total_capability_count: int = 1000
    max_capability_count_per_pack: int = 500
    dry_run: bool = True
    meta: dict[str, Any] = Field(default_factory=dict)


class CapabilityLibraryProposalEvidenceFrictionSummaryRefApplyIn(BaseModel):
    actor: str = ""
    reason: str = "stage17_proposal_evidence_friction_summary_refs"
    pack_ids: list[str] = Field(default_factory=list)
    max_pack_count: int = 10
    max_total_capability_count: int = 1000
    max_capability_count_per_pack: int = 500
    dry_run: bool = True
    meta: dict[str, Any] = Field(default_factory=dict)


class CapabilityLibraryOperatorProposalEvidenceIntakeApplyIn(BaseModel):
    actor: str = ""
    reason: str = "stage17_operator_proposal_evidence_intake"
    pack_ids: list[str] = Field(default_factory=list)
    capability_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    evidence_refs_by_capability: dict[str, list[str]] = Field(default_factory=dict)
    max_pack_count: int = 10
    max_total_capability_count: int = 1000
    max_capability_count_per_pack: int = 500
    dry_run: bool = True
    dry_run_fingerprint: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)


class CapabilityLibraryProposalReviewApplyIn(BaseModel):
    actor: str = ""
    reason: str = "stage17_capability_library_proposal_review"
    action: str = "approve"
    notes: str = ""
    pack_ids: list[str] = Field(default_factory=list)
    capability_ids: list[str] = Field(default_factory=list)
    proposal_ids: list[str] = Field(default_factory=list)
    max_pack_count: int = 10
    max_total_capability_count: int = 1000
    max_capability_count_per_pack: int = 500
    dry_run: bool = True
    dry_run_fingerprint: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)


class CapabilityLibraryExplicitPromotionApplyIn(BaseModel):
    actor: str = ""
    reason: str = "stage17_capability_library_explicit_promotion"
    pack_ids: list[str] = Field(default_factory=list)
    capability_ids: list[str] = Field(default_factory=list)
    max_pack_count: int = 10
    max_total_capability_count: int = 1000
    max_capability_count_per_pack: int = 500
    dry_run: bool = True
    dry_run_fingerprint: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)


class CapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewIn(BaseModel):
    actor: str = ""
    rows: list[dict[str, Any]] = Field(default_factory=list)
    max_row_count: int = _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_EXPORT_ROW_LIMIT
    max_apply_group_count: int = 500
    use_suggested_evidence_refs: bool = False
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
        coherence = analyze_capability_catalog_coherence(all_items)
        pack_readiness = analyze_capability_pack_readiness(all_items)

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
            "coherence": coherence,
            "pack_readiness": pack_readiness,
            "stage17_closure_matrix": _stage17_closure_matrix(
                all_items=all_items,
                coherence=coherence,
                pack_readiness=pack_readiness,
                catalog=catalog,
            ),
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


@router.post("/capabilities/packs/quality/standards/remediation/apply")
def apply_capability_pack_quality_standard_remediation(
    payload: CapabilityPackQualityStandardRemediationApplyIn,
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
        standards = analyze_capability_pack_quality_standards(entries)
        references = _quality_standard_reference_candidates()
        raw_packs = standards.get("packs") if isinstance(standards.get("packs"), list) else []
        queue = [
            item
            for item in raw_packs
            if isinstance(item, dict)
            and any(
                blocker in _unique_texts(item.get("blockers"), limit=50)
                for blocker in ("tests_missing", "docs_missing")
            )
        ]
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
                "before": standards,
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "writes_registry_metadata": False,
                    "writes_receipts": False,
                    "does_not_write_validation_receipts": True,
                    "does_not_write_proposals": True,
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
        if len(queue) > safe_max_pack_count:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "quality_standard_pack_limit_exceeded",
                "candidate_total": len(queue),
                "limit": safe_max_pack_count,
            }

        prepared: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        total_capability_count = 0
        for item in queue:
            pack_id = _safe_str(item.get("pack_id")).strip()
            pack_version = _safe_str(item.get("pack_version")).strip()
            try:
                pack_id = _validate_plugin_id(pack_id)
            except Exception:
                skipped.append({"pack_id": pack_id, "pack_version": pack_version, "error": "invalid_pack_id"})
                continue
            pack_entries = _entries_for_capability_pack(entries, pack_id=pack_id, pack_version=pack_version)
            capability_ids = _capability_ids_for_pack(entries, pack_id=pack_id, pack_version=pack_version)
            capability_count = len(capability_ids)
            total_capability_count += capability_count
            blockers = _unique_texts(item.get("blockers"), limit=50)
            test_refs = references["tests"] if "tests_missing" in blockers else []
            doc_refs = references["docs"] if "docs_missing" in blockers else []
            missing_test_ids, missing_doc_ids = _quality_standard_missing_capability_ids(pack_entries)
            if not test_refs and not doc_refs:
                skipped.append(
                    {
                        "pack_id": pack_id,
                        "pack_version": pack_version,
                        "error": "no_supported_quality_standard_references",
                        "blockers": blockers,
                    }
                )
                continue
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
                    "missing_test_capability_ids": missing_test_ids,
                    "missing_doc_capability_ids": missing_doc_ids,
                    "test_refs": test_refs,
                    "doc_refs": doc_refs,
                    "quality_blockers": [
                        blocker for blocker in blockers if blocker in {"tests_missing", "docs_missing"}
                    ],
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
                "status": "no_supported_quality_standard_references",
                "planned_pack_count": 0,
                "recorded_pack_count": 0,
                "recorded_capability_count": 0,
                "skipped": skipped,
                "before": standards,
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "writes_registry_metadata": False,
                    "writes_receipts": False,
                    "does_not_write_validation_receipts": True,
                    "does_not_write_proposals": True,
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

        planned = [
            {
                "pack_id": item["pack_id"],
                "pack_version": item["pack_version"],
                "pack_name": item["pack_name"],
                "capability_count": len(item["capability_ids"]),
                "missing_test_capability_count": len(item["missing_test_capability_ids"]),
                "missing_doc_capability_count": len(item["missing_doc_capability_ids"]),
                "quality_blockers": item["quality_blockers"],
                "quality_references": {
                    "tests": item["test_refs"],
                    "docs": item["doc_refs"],
                    "claim_scope": "candidate_reference_only_not_pack_specific_proof",
                    "pack_specific_coverage_claimed": False,
                },
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
                "before": standards,
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "writes_registry_metadata": False,
                    "writes_receipts": False,
                    "quality_reference_backfill_only": True,
                    "candidate_references_do_not_claim_pack_specific_coverage": True,
                    "does_not_write_validation_receipts": True,
                    "does_not_write_proposals": True,
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

        batch = _record_capability_pack_quality_standard_remediation_batch(
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
        after = analyze_capability_pack_quality_standards(refreshed_marketplace.catalog())
        selected_after_queue = [
            item
            for item in after.get("packs", [])
            if isinstance(item, dict)
            and _safe_str(item.get("pack_id")).strip()
            in {_safe_str(record.get("pack_id")).strip() for record in recorded}
            and item.get("status") != "ready"
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
            "remaining_quality_standard_queue": selected_after_queue,
            "remaining_quality_standard_queue_count": len(selected_after_queue),
            "next_smallest_truthful_gap": _safe_str(after.get("next_smallest_truthful_gap")).strip(),
            "governance": {
                "scope": _PLUGIN_WRITE_SCOPE,
                "route": request.url.path,
                "writes_registry_metadata": applied,
                "writes_receipts": False,
                "quality_reference_backfill_only": True,
                "candidate_references_do_not_claim_pack_specific_coverage": True,
                "does_not_write_validation_receipts": True,
                "does_not_write_proposals": True,
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
            "applied": False,
            "kind": "plugin.capability_pack.quality_standard.remediation.apply",
            "status": "error",
            "error": api_error_message(exc),
        }


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
        artifact_link_candidates = _capability_pack_existing_artifact_link_candidates()
        validation_candidates = (
            artifact_link_candidates.get("validation_receipts")
            if isinstance(artifact_link_candidates.get("validation_receipts"), dict)
            else {}
        )
        proposal_candidates = (
            artifact_link_candidates.get("proposals")
            if isinstance(artifact_link_candidates.get("proposals"), dict)
            else {}
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
            capability_ids = _capability_ids_for_pack(entries, pack_id=pack_id, pack_version=pack_version)
            capability_count = len(capability_ids)
            references = _quality_reference_plan_for_remediation_item(item, reference_candidates)
            quality_reference_backfill = bool(references["tests"] or references["docs"])
            validation_receipt_links = _artifact_link_plan_for_pack_capabilities(
                registry=registry,
                capability_ids=capability_ids,
                candidates=validation_candidates,
                artifact_id_key="validation_receipt_id",
                path_key="validation_receipt_path",
                limit=safe_max_capability_count_per_pack,
            )
            proposal_lineage_links = _artifact_link_plan_for_pack_capabilities(
                registry=registry,
                capability_ids=capability_ids,
                candidates=proposal_candidates,
                artifact_id_key="proposal_id",
                path_key="proposal_path",
                limit=safe_max_capability_count_per_pack,
            )
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
            if capability_count <= 0:
                skipped.append({"pack_id": pack_id, "pack_version": pack_version, "error": "capability_ids_required"})
                continue
            if quality_reference_backfill and capability_count > safe_max_capability_count_per_pack:
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
            planned_link_capability_count = len(
                set(validation_receipt_links.keys()) | set(proposal_lineage_links.keys())
            )
            effective_capability_count = (
                capability_count if quality_reference_backfill else planned_link_capability_count
            )
            total_capability_count += effective_capability_count
            prepared.append(
                {
                    "item": item,
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "pack_name": _safe_str(item.get("pack_name")).strip() or pack_id,
                    "capability_ids": capability_ids,
                    "partial_existing_artifact_link_backfill": (
                        not quality_reference_backfill
                        and planned_link_capability_count > 0
                        and planned_link_capability_count < capability_count
                    ),
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
                "planned_registry_metadata_capability_count": (
                    len(item["capability_ids"])
                    if (item["quality_references"]["tests"] or item["quality_references"]["docs"])
                    else len(set(item["validation_receipt_links"].keys()) | set(item["proposal_lineage_links"].keys()))
                ),
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
                "partial_existing_artifact_link_backfill": bool(item.get("partial_existing_artifact_link_backfill")),
                "partial_link_backfill_does_not_claim_pack_complete": bool(
                    item.get("partial_existing_artifact_link_backfill")
                ),
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
                "planned_capability_count": sum(
                    int(item.get("planned_registry_metadata_capability_count") or 0) for item in planned
                ),
                "planned": planned,
                "skipped": skipped,
                "before": before,
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "writes_registry_metadata": False,
                    "writes_receipts": False,
                    "partial_existing_artifact_link_backfill_count": sum(
                        1 for item in prepared if bool(item.get("partial_existing_artifact_link_backfill"))
                    ),
                    "partial_link_backfill_does_not_claim_pack_complete": any(
                        bool(item.get("partial_existing_artifact_link_backfill")) for item in prepared
                    ),
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
                "partial_existing_artifact_link_backfill_count": sum(
                    1 for item in prepared if bool(item.get("partial_existing_artifact_link_backfill"))
                ),
                "partial_link_backfill_does_not_claim_pack_complete": any(
                    bool(item.get("partial_existing_artifact_link_backfill")) for item in prepared
                ),
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


@router.post("/capabilities/packs/quality/evidence/remediation/reconstruct")
def reconstruct_capability_pack_quality_evidence_artifacts(
    payload: CapabilityPackQualityEvidenceReconstructionApplyIn,
    request: Request,
) -> dict[str, object]:
    try:
        permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
        if not permission.allowed:
            return _permission_denied(permission)

        safe_max_pack_count = max(1, min(int(payload.max_pack_count or 5), 25))
        safe_max_total_capability_count = max(1, min(int(payload.max_total_capability_count or 100), 500))
        safe_max_capability_count_per_pack = max(1, min(int(payload.max_capability_count_per_pack or 50), 100))
        try:
            selected_pack_ids = {_validate_plugin_id(raw_id) for raw_id in _unique_texts(payload.pack_ids, limit=100)}
        except Exception:
            return {"ok": False, "applied": False, "status": "blocked", "error": "invalid_pack_id"}

        operator_decision = _safe_str((payload.meta or {}).get("operator_reconstruction_decision")).strip().lower()
        operator_decision_approved = operator_decision in {"approve", "approved", "approved_for_reconstruction"}

        registry = _load_registry()
        _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        entries = marketplace.catalog()
        promotion_remediation = analyze_capability_pack_promotion_rule_remediation(entries)
        before = _capability_pack_quality_evidence_remediation_projection(entries, promotion_remediation)
        raw_queue = before.get("remediation_queue")
        queue = [item for item in raw_queue if isinstance(item, dict)] if isinstance(raw_queue, list) else []
        queue = [
            item
            for item in queue
            if bool(
                (
                    item.get("artifact_reconstruction_plan")
                    if isinstance(item.get("artifact_reconstruction_plan"), dict)
                    else {}
                ).get("required")
            )
        ]
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
                    "writes_validation_receipts": False,
                    "writes_proposals": False,
                    "does_not_approve_proposals": True,
                    "does_not_promote_capabilities": True,
                    "does_not_execute_capabilities": True,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                },
            }
        if len(queue) > safe_max_pack_count:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "reconstruction_pack_limit_exceeded",
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
            plan = (
                item.get("artifact_reconstruction_plan")
                if isinstance(item.get("artifact_reconstruction_plan"), dict)
                else {}
            )
            raw_capabilities = plan.get("capabilities") if isinstance(plan.get("capabilities"), list) else []
            capabilities = [capability for capability in raw_capabilities if isinstance(capability, dict)]
            capabilities_truncated = bool(plan.get("capabilities_truncated"))
            required_capability_count = int(plan.get("capability_count") or len(capabilities))
            unsupported_inputs: list[dict[str, object]] = []
            for capability in capabilities:
                missing_inputs = [
                    value
                    for value in _unique_texts(capability.get("missing_inputs"), limit=25)
                    if value != "explicit_proposal_lineage_source_or_operator_reconstruction_decision"
                ]
                if missing_inputs:
                    unsupported_inputs.append(
                        {
                            "capability": _safe_str(capability.get("capability")).strip(),
                            "missing_inputs": missing_inputs,
                        }
                    )
            if unsupported_inputs:
                skipped.append(
                    {
                        "pack_id": pack_id,
                        "pack_version": pack_version,
                        "error": "required_reconstruction_inputs_missing",
                        "capabilities": unsupported_inputs,
                    }
                )
                continue
            capability_count = len(capabilities)
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
                    "capabilities": capabilities,
                    "required_capability_count": required_capability_count,
                    "capabilities_truncated": capabilities_truncated,
                    "partial_reconstruction": capabilities_truncated,
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

        planned = [
            {
                "pack_id": item["pack_id"],
                "pack_version": item["pack_version"],
                "pack_name": item["pack_name"],
                "capability_count": len(item["capabilities"]),
                "required_capability_count": int(item.get("required_capability_count") or 0),
                "capabilities_truncated": bool(item.get("capabilities_truncated")),
                "partial_reconstruction": bool(item.get("partial_reconstruction")),
                "partial_reconstruction_does_not_claim_pack_complete": bool(item.get("partial_reconstruction")),
                "validation_receipts": {
                    "count": sum(
                        1 for capability in item["capabilities"] if bool(capability.get("needs_validation_receipt"))
                    ),
                    "claim_scope": "pack_specific_validation_receipt_reconstructed_from_registry_evidence",
                    "writes_validation_receipts": not payload.dry_run,
                },
                "proposal_lineages": {
                    "count": sum(
                        1 for capability in item["capabilities"] if bool(capability.get("needs_proposal_lineage"))
                    ),
                    "claim_scope": "reconstructed_plugin_proposal_lineage_only_not_approval",
                    "writes_proposals": not payload.dry_run,
                    "proposal_approval_claimed": False,
                },
                "capabilities": [
                    {
                        "capability": _safe_str(capability.get("capability")).strip(),
                        "needs_validation_receipt": bool(capability.get("needs_validation_receipt")),
                        "needs_proposal_lineage": bool(capability.get("needs_proposal_lineage")),
                    }
                    for capability in item["capabilities"]
                ],
                "requires_operator_reconstruction_decision": True,
                "operator_reconstruction_decision_present": operator_decision_approved,
            }
            for item in prepared
        ]
        partial_reconstruction_count = sum(1 for item in planned if bool(item.get("partial_reconstruction")))
        if not prepared:
            return {
                "ok": True,
                "applied": False,
                "status": "no_supported_artifact_reconstruction",
                "planned_pack_count": 0,
                "recorded_pack_count": 0,
                "recorded_capability_count": 0,
                "skipped": skipped,
                "before": before,
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "writes_registry_metadata": False,
                    "writes_validation_receipts": False,
                    "writes_proposals": False,
                    "does_not_approve_proposals": True,
                    "does_not_promote_capabilities": True,
                    "does_not_execute_capabilities": True,
                    "partial_reconstruction_count": 0,
                    "partial_reconstruction_does_not_claim_pack_complete": False,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                },
            }
        if payload.dry_run:
            return {
                "ok": True,
                "applied": False,
                "status": "dry_run",
                "planned_pack_count": len(planned),
                "planned_capability_count": sum(int(item.get("capability_count") or 0) for item in planned),
                "partial_reconstruction_count": partial_reconstruction_count,
                "planned": planned,
                "skipped": skipped,
                "before": before,
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "writes_registry_metadata": False,
                    "writes_validation_receipts": False,
                    "writes_proposals": False,
                    "does_not_approve_proposals": True,
                    "does_not_promote_capabilities": True,
                    "does_not_execute_capabilities": True,
                    "partial_reconstruction_count": partial_reconstruction_count,
                    "partial_reconstruction_does_not_claim_pack_complete": partial_reconstruction_count > 0,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                },
            }
        if not operator_decision_approved:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "operator_reconstruction_decision_required",
                "planned_pack_count": len(planned),
                "planned_capability_count": sum(int(item.get("capability_count") or 0) for item in planned),
                "partial_reconstruction_count": partial_reconstruction_count,
                "planned": planned,
                "skipped": skipped,
                "before": before,
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "writes_registry_metadata": False,
                    "writes_validation_receipts": False,
                    "writes_proposals": False,
                    "requires_operator_reconstruction_decision": True,
                    "partial_reconstruction_count": partial_reconstruction_count,
                    "partial_reconstruction_does_not_claim_pack_complete": partial_reconstruction_count > 0,
                    "does_not_approve_proposals": True,
                    "does_not_promote_capabilities": True,
                    "does_not_execute_capabilities": True,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                },
            }

        batch = _record_capability_pack_artifact_reconstruction_batch(
            registry=registry,
            prepared=prepared,
            payload=payload,
            route_path=request.url.path,
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
        validation_write_count = sum(
            len(item.get("validation_receipts") or []) for item in changed_records if isinstance(item, dict)
        )
        proposal_write_count = sum(
            len(item.get("proposal_lineages") or []) for item in changed_records if isinstance(item, dict)
        )
        applied = bool(changed_records)
        return {
            "ok": not failed,
            "applied": applied,
            "status": "recorded" if not failed and applied else ("partial" if applied else "blocked"),
            "planned_pack_count": len(prepared),
            "recorded_pack_count": len(changed_records),
            "recorded_capability_count": sum(
                int(item.get("reconstructed_capability_count") or 0) for item in changed_records
            ),
            "partial_reconstruction_count": partial_reconstruction_count,
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
                "writes_validation_receipts": validation_write_count > 0,
                "writes_proposals": proposal_write_count > 0,
                "validation_receipt_write_count": validation_write_count,
                "proposal_lineage_write_count": proposal_write_count,
                "requires_operator_reconstruction_decision": True,
                "operator_reconstruction_decision_captured": operator_decision_approved,
                "partial_reconstruction_count": partial_reconstruction_count,
                "partial_reconstruction_does_not_claim_pack_complete": partial_reconstruction_count > 0,
                "validation_claim_scope": "pack_specific_validation_receipt_reconstructed_from_registry_evidence",
                "proposal_lineage_claim_scope": "reconstructed_plugin_proposal_lineage_only_not_approval",
                "proposal_lineage_does_not_approve_proposals": True,
                "does_not_approve_proposals": True,
                "does_not_promote_capabilities": True,
                "does_not_enable_capabilities": True,
                "does_not_execute_capabilities": True,
                "promotion_authority": False,
                "execution_authority": False,
                "approval_authority": False,
                "memory_write": False,
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "plugin.capability_pack.quality_evidence.artifact_reconstruction.apply",
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


@router.get("/capabilities/packs/operator/surface")
def capability_pack_operator_surface() -> dict[str, object]:
    try:
        registry = _load_registry()
        catalog = _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        entries = list(marketplace.catalog())
        available_proposals = _available_capability_pack_proposals()
        available_validation_receipts = _available_capability_pack_validation_receipts()
        available_promotion_receipts = _available_capability_pack_promotion_receipts()
        operator_review_decisions = _read_capability_pack_operator_review_decisions(limit=500)
        migration_plan = analyze_capability_pack_migration_plan(entries)
        readiness = analyze_capability_pack_readiness(entries)
        promotion_rules = analyze_capability_pack_promotion_rules(entries)
        promotion_remediation = analyze_capability_pack_promotion_rule_remediation(entries)
        quality = _capability_pack_quality_evidence_remediation_projection(entries, promotion_remediation)
        operator_review = analyze_capability_pack_operator_review(entries)
        promotion_discipline = analyze_capability_pack_promotion_discipline(
            entries,
            available_proposal_ids=available_proposals["ids"],
            available_validation_receipt_ids=available_validation_receipts["ids"],
            available_promotion_receipt_ids=available_promotion_receipts["ids"],
            operator_review_decisions=operator_review_decisions,
        )
        surface = _capability_pack_operator_surface_projection(
            entries=entries,
            migration_plan=migration_plan,
            readiness=readiness,
            promotion_rules=promotion_rules,
            promotion_remediation=promotion_remediation,
            quality=quality,
            operator_review=operator_review,
            operator_review_decisions=operator_review_decisions,
            promotion_discipline=promotion_discipline,
            generated_plugin_sync_performed=False,
        )
        return {
            "ok": True,
            "kind": "plugin.capability_pack.operator_surface",
            **surface,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {"ok": False, "kind": "plugin.capability_pack.operator_surface", "error": api_error_message(exc)}


@router.get("/capabilities/library/operator/surface")
def capability_library_operator_surface() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        available_proposals = _available_capability_pack_proposals()
        available_validation_receipts = _available_capability_pack_validation_receipts()
        available_promotion_receipts = _available_capability_pack_promotion_receipts()
        promotion_discipline = analyze_capability_pack_promotion_discipline(
            marketplace.catalog(),
            available_proposal_ids=available_proposals["ids"],
            available_validation_receipt_ids=available_validation_receipts["ids"],
            available_promotion_receipt_ids=available_promotion_receipts["ids"],
            operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
        )
        surface = _capability_library_operator_surface_projection(
            promotion_discipline=promotion_discipline,
            generated_plugin_sync_performed=synced,
        )
        return {
            "ok": True,
            "kind": "plugin.capability_library.operator_surface",
            **surface,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {"ok": False, "kind": "plugin.capability_library.operator_surface", "error": api_error_message(exc)}


@router.get("/capabilities/library/invocations/audit")
def capability_library_invocations_audit(
    request: Request,
    pack_id: str | None = None,
    pack_version: str | None = None,
    plugin_id: str | None = None,
    capability_id: str | None = None,
    limit: int = 200,
    scan_limit: int = 5000,
) -> dict[str, object]:
    try:
        audit = _capability_pack_invocation_audit_projection(
            pack_id=pack_id or "",
            pack_version=pack_version or "",
            plugin_id=plugin_id or "",
            capability_id=capability_id or "",
            limit=limit,
            scan_limit=scan_limit,
        )
        governance = audit.get("governance") if isinstance(audit.get("governance"), dict) else {}
        audit["governance"] = {**governance, "route": request.url.path}
        return audit
    except Exception as exc:
        return {"ok": False, "kind": "plugin.capability_library.invocations.audit", "error": api_error_message(exc)}


@router.get("/capabilities/library/promotion/plan")
def capability_library_promotion_plan() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        entries = list(marketplace.catalog())
        available_proposals = _available_capability_pack_proposals()
        available_validation_receipts = _available_capability_pack_validation_receipts()
        available_promotion_receipts = _available_capability_pack_promotion_receipts()
        promotion_discipline = analyze_capability_pack_promotion_discipline(
            entries,
            available_proposal_ids=available_proposals["ids"],
            available_validation_receipt_ids=available_validation_receipts["ids"],
            available_promotion_receipt_ids=available_promotion_receipts["ids"],
            operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
        )
        plan = _capability_library_explicit_promotion_plan_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            generated_plugin_sync_performed=synced,
        )
        return {
            "ok": True,
            "kind": "plugin.capability_library.promotion_plan",
            **plan,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {"ok": False, "kind": "plugin.capability_library.promotion_plan", "error": api_error_message(exc)}


@router.post("/capabilities/library/promotion/apply")
def apply_capability_library_explicit_promotion(
    payload: CapabilityLibraryExplicitPromotionApplyIn,
    request: Request,
) -> dict[str, object]:
    try:
        permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
        if not permission.allowed:
            return _permission_denied(permission)

        plan = _prepare_capability_library_explicit_promotion_plan(payload=payload)
        generated_sync = bool(plan.get("generated_plugin_registry_sync_performed"))
        if plan.get("status") != "planned":
            return {
                "ok": bool(plan.get("ok")),
                "applied": False,
                "kind": "plugin.capability_library.explicit_promotion.apply",
                "status": _safe_str(plan.get("status")).strip() or "blocked",
                "error": _safe_str(plan.get("error")).strip(),
                "planned_pack_count": int(plan.get("planned_pack_count") or 0),
                "planned_capability_count": int(plan.get("planned_capability_count") or 0),
                "before": plan.get("before") if isinstance(plan.get("before"), dict) else {},
                "governance": _capability_library_explicit_promotion_apply_governance(
                    route_path=request.url.path,
                    writes_registry_metadata=False,
                    writes_promotion_receipts=False,
                    generated_plugin_registry_sync_performed=generated_sync,
                ),
            }

        dry_run_fingerprint = _safe_str(plan.get("dry_run_fingerprint")).strip()
        planned = plan.get("planned") if isinstance(plan.get("planned"), list) else []
        skipped = plan.get("skipped") if isinstance(plan.get("skipped"), list) else []
        planned_pack_count = int(plan.get("planned_pack_count") or 0)
        planned_capability_count = int(plan.get("planned_capability_count") or 0)
        if payload.dry_run:
            return {
                "ok": True,
                "applied": False,
                "kind": "plugin.capability_library.explicit_promotion.apply",
                "status": "dry_run",
                "planned_pack_count": planned_pack_count,
                "planned_capability_count": planned_capability_count,
                "dry_run_fingerprint": dry_run_fingerprint,
                "dry_run_confirmation": {
                    "required_for_apply": True,
                    "fingerprint": dry_run_fingerprint,
                    "fingerprint_contract": "stage17_capability_library_explicit_promotion_dry_run_v1",
                    "planned_pack_count": planned_pack_count,
                    "planned_capability_count": planned_capability_count,
                    "apply_route": request.url.path,
                },
                "planned": planned,
                "skipped": skipped,
                "before": plan.get("before") if isinstance(plan.get("before"), dict) else {},
                "governance": _capability_library_explicit_promotion_apply_governance(
                    route_path=request.url.path,
                    writes_registry_metadata=False,
                    writes_promotion_receipts=False,
                    generated_plugin_registry_sync_performed=generated_sync,
                ),
            }

        provided_dry_run_fingerprint = _safe_str(payload.dry_run_fingerprint).strip()
        if provided_dry_run_fingerprint != dry_run_fingerprint:
            return {
                "ok": False,
                "applied": False,
                "kind": "plugin.capability_library.explicit_promotion.apply",
                "status": "blocked",
                "error": "capability_library_explicit_promotion_dry_run_confirmation_required",
                "planned_pack_count": planned_pack_count,
                "planned_capability_count": planned_capability_count,
                "dry_run_confirmation": {
                    "required_for_apply": True,
                    "fingerprint_contract": "stage17_capability_library_explicit_promotion_dry_run_v1",
                    "fingerprint_matched": False,
                    "apply_route": request.url.path,
                },
                "governance": _capability_library_explicit_promotion_apply_governance(
                    route_path=request.url.path,
                    writes_registry_metadata=False,
                    writes_promotion_receipts=False,
                    generated_plugin_registry_sync_performed=generated_sync,
                ),
            }

        registry = plan.get("registry") if isinstance(plan.get("registry"), dict) else _load_registry()
        actor = redact_governed_value(_safe_str(payload.actor).strip())
        promoted_items: list[dict[str, Any]] = []
        failed_items: list[dict[str, Any]] = []
        pending_receipts: list[dict[str, Any]] = []
        for pack in planned:
            raw_capabilities = pack.get("capabilities") if isinstance(pack.get("capabilities"), list) else []
            for capability in raw_capabilities:
                if not isinstance(capability, dict):
                    continue
                plugin_id = _safe_str(capability.get("capability")).strip()
                current = _read_plugin(registry, plugin_id)
                if current is None:
                    failed_items.append({"capability": plugin_id, "error": "plugin_not_found"})
                    continue
                toggle_payload = PluginToggleIn(
                    id=plugin_id,
                    reason=payload.reason,
                    actor=payload.actor,
                    meta=payload.meta,
                )
                readiness = _plugin_promotion_readiness(plugin_id, current, toggle_payload)
                if not readiness["ready"]:
                    failed_items.append(
                        {
                            "capability": plugin_id,
                            "error": "promotion_readiness_blocked",
                            "missing_requirements": _unique_texts(readiness.get("missing_requirements"), limit=25),
                        }
                    )
                    continue

                previous = dict(current)
                promoted_ts = _now_s()
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
                        "promoted_by": actor,
                    }
                )
                current["meta"] = meta
                current["enabled"] = True
                current["status"] = "enabled"
                current["updated_ts"] = promoted_ts
                promoted = _normalize_plugin_record(plugin_id, current)
                _write_plugin(registry, promoted)
                promoted_items.append(
                    {
                        "capability": plugin_id,
                        "pack_id": _safe_str(pack.get("pack_id")).strip(),
                        "pack_version": _safe_str(pack.get("pack_version")).strip(),
                        "promotion_receipt_id": promotion_receipt_id,
                        "promotion_receipt_path": str(promotion_receipt_path),
                        "status": "promoted",
                    }
                )
                pending_receipts.append(
                    {
                        "plugin_id": plugin_id,
                        "receipt_id": promotion_receipt_id,
                        "receipt_path": promotion_receipt_path,
                        "previous": previous,
                        "promoted": promoted,
                        "payload": toggle_payload,
                        "promoted_ts": promoted_ts,
                    }
                )

        catalog = _save_registry_and_catalog(registry)
        promotion_receipts = [
            _write_plugin_promotion_receipt(
                plugin_id=_safe_str(item.get("plugin_id")).strip(),
                receipt_id=_safe_str(item.get("receipt_id")).strip(),
                receipt_path=item["receipt_path"],
                previous=item["previous"],
                promoted=item["promoted"],
                payload=item["payload"],
                promoted_ts=int(item.get("promoted_ts") or 0),
                catalog=catalog,
            )
            for item in pending_receipts
        ]

        refreshed_registry = _load_registry()
        refreshed_catalog = _compile_runtime_catalog(refreshed_registry)
        refreshed_runtime_catalog = _read_runtime_catalog_payload(refreshed_catalog)
        refreshed_marketplace = marketplace_from_plugin_catalog(refreshed_runtime_catalog)
        refreshed_entries = list(refreshed_marketplace.catalog())
        refreshed_available_proposals = _available_capability_pack_proposals()
        refreshed_available_validation_receipts = _available_capability_pack_validation_receipts()
        refreshed_available_promotion_receipts = _available_capability_pack_promotion_receipts()
        refreshed_promotion_discipline = analyze_capability_pack_promotion_discipline(
            refreshed_entries,
            available_proposal_ids=refreshed_available_proposals["ids"],
            available_validation_receipt_ids=refreshed_available_validation_receipts["ids"],
            available_promotion_receipt_ids=refreshed_available_promotion_receipts["ids"],
            operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
        )
        after = _capability_library_explicit_promotion_plan_projection(
            registry=refreshed_registry,
            entries=refreshed_entries,
            promotion_discipline=refreshed_promotion_discipline,
            generated_plugin_sync_performed=False,
        )
        applied = bool(promoted_items)
        return {
            "ok": not failed_items,
            "applied": applied,
            "kind": "plugin.capability_library.explicit_promotion.apply",
            "status": "promoted" if applied and not failed_items else ("partial" if applied else "blocked"),
            "planned_pack_count": planned_pack_count,
            "planned_capability_count": planned_capability_count,
            "promoted_capability_count": len(promoted_items),
            "promotion_receipt_count": len(promotion_receipts),
            "promoted": promoted_items,
            "failed": failed_items,
            "skipped": skipped,
            "dry_run_fingerprint": dry_run_fingerprint,
            "dry_run_confirmation": {
                "required_for_apply": True,
                "fingerprint_matched": True,
                "fingerprint_contract": "stage17_capability_library_explicit_promotion_dry_run_v1",
                "apply_route": request.url.path,
            },
            "remaining_candidate_capability_count": int(after.get("candidate_capability_count") or 0),
            "remaining_promotable_capability_count": int(after.get("promotable_capability_count") or 0),
            "next_smallest_truthful_gap": _safe_str(after.get("next_smallest_truthful_gap")).strip(),
            "promotion_receipts": promotion_receipts,
            "governance": _capability_library_explicit_promotion_apply_governance(
                route_path=request.url.path,
                writes_registry_metadata=applied,
                writes_promotion_receipts=bool(promotion_receipts),
                generated_plugin_registry_sync_performed=generated_sync,
            ),
        }
    except Exception as exc:
        return {
            "ok": False,
            "applied": False,
            "kind": "plugin.capability_library.explicit_promotion.apply",
            "error": api_error_message(exc),
        }


@router.get("/capabilities/library/proposal-evidence/plan")
def capability_library_proposal_evidence_plan() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        entries = list(marketplace.catalog())
        available_proposals = _available_capability_pack_proposals()
        available_validation_receipts = _available_capability_pack_validation_receipts()
        available_promotion_receipts = _available_capability_pack_promotion_receipts()
        promotion_discipline = analyze_capability_pack_promotion_discipline(
            entries,
            available_proposal_ids=available_proposals["ids"],
            available_validation_receipt_ids=available_validation_receipts["ids"],
            available_promotion_receipt_ids=available_promotion_receipts["ids"],
            operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
        )
        plan = _capability_library_proposal_evidence_plan_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            generated_plugin_sync_performed=synced,
        )
        return {
            "ok": True,
            "kind": "plugin.capability_library.proposal_evidence_plan",
            **plan,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "plugin.capability_library.proposal_evidence_plan",
            "error": api_error_message(exc),
        }


@router.get("/capabilities/library/proposal-evidence/source-readiness")
def capability_library_proposal_evidence_source_readiness() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        entries = list(marketplace.catalog())
        available_proposals = _available_capability_pack_proposals()
        available_validation_receipts = _available_capability_pack_validation_receipts()
        available_promotion_receipts = _available_capability_pack_promotion_receipts()
        promotion_discipline = analyze_capability_pack_promotion_discipline(
            entries,
            available_proposal_ids=available_proposals["ids"],
            available_validation_receipt_ids=available_validation_receipts["ids"],
            available_promotion_receipt_ids=available_promotion_receipts["ids"],
            operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
        )
        source_plan = _capability_library_proposal_evidence_plan_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            generated_plugin_sync_performed=bool(synced),
        )
        artifact_remediation = _capability_library_proposal_evidence_remediation_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            generated_plugin_sync_performed=bool(synced),
        )
        friction_summary_refs = _capability_library_proposal_evidence_friction_summary_ref_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            generated_plugin_sync_performed=bool(synced),
        )
        operator_checklist = _capability_library_operator_proposal_evidence_intake_checklist_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            source_plan=source_plan,
            generated_plugin_sync_performed=bool(synced),
        )
        operator_audit = _capability_library_operator_proposal_evidence_intake_audit_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            source_plan=source_plan,
            generated_plugin_sync_performed=bool(synced),
        )
        proposal_review_plan = _capability_library_proposal_review_plan_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            generated_plugin_sync_performed=bool(synced),
        )
        proposal_review_apply_readiness = _capability_library_proposal_review_apply_readiness_projection(
            proposal_review_plan=proposal_review_plan,
            proposal_evidence_plan=source_plan,
            operator_evidence_audit=operator_audit,
            generated_plugin_sync_performed=bool(synced),
        )
        readiness = _capability_library_proposal_evidence_source_readiness_projection(
            proposal_evidence_plan=source_plan,
            artifact_remediation=artifact_remediation,
            friction_summary_refs=friction_summary_refs,
            operator_checklist=operator_checklist,
            operator_audit=operator_audit,
            proposal_review_apply_readiness=proposal_review_apply_readiness,
            generated_plugin_sync_performed=bool(synced),
        )
        return {
            "ok": True,
            "kind": "plugin.capability_library.proposal_evidence_source_readiness",
            **readiness,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "plugin.capability_library.proposal_evidence_source_readiness",
            "error": api_error_message(exc),
        }


@router.get("/capabilities/library/proposal-evidence/remediation")
def capability_library_proposal_evidence_remediation() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        entries = list(marketplace.catalog())
        available_proposals = _available_capability_pack_proposals()
        available_validation_receipts = _available_capability_pack_validation_receipts()
        available_promotion_receipts = _available_capability_pack_promotion_receipts()
        promotion_discipline = analyze_capability_pack_promotion_discipline(
            entries,
            available_proposal_ids=available_proposals["ids"],
            available_validation_receipt_ids=available_validation_receipts["ids"],
            available_promotion_receipt_ids=available_promotion_receipts["ids"],
            operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
        )
        plan = _capability_library_proposal_evidence_remediation_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            generated_plugin_sync_performed=bool(synced),
        )
        return {
            "ok": True,
            "kind": "plugin.capability_library.proposal_evidence_remediation",
            **plan,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "plugin.capability_library.proposal_evidence_remediation",
            "error": api_error_message(exc),
        }


@router.post("/capabilities/library/proposal-evidence/remediation/apply")
def apply_capability_library_proposal_evidence_remediation(
    payload: CapabilityLibraryProposalEvidenceRemediationApplyIn,
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
        entries = list(marketplace.catalog())
        available_proposals = _available_capability_pack_proposals()
        available_validation_receipts = _available_capability_pack_validation_receipts()
        available_promotion_receipts = _available_capability_pack_promotion_receipts()
        promotion_discipline = analyze_capability_pack_promotion_discipline(
            entries,
            available_proposal_ids=available_proposals["ids"],
            available_validation_receipt_ids=available_validation_receipts["ids"],
            available_promotion_receipt_ids=available_promotion_receipts["ids"],
            operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
        )
        before = _capability_library_proposal_evidence_remediation_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            generated_plugin_sync_performed=True,
        )
        raw_packs = before.get("packs")
        packs = [pack for pack in raw_packs if isinstance(pack, dict)] if isinstance(raw_packs, list) else []
        if selected_pack_ids:
            packs = [pack for pack in packs if _safe_str(pack.get("pack_id")).strip() in selected_pack_ids]
        if not packs:
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
                    "writes_proposals": False,
                    "does_not_approve_proposals": True,
                    "does_not_promote_capabilities": True,
                    "does_not_enable_capabilities": True,
                    "does_not_execute_capabilities": True,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                },
            }
        if len(packs) > safe_max_pack_count:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "proposal_evidence_remediation_pack_limit_exceeded",
                "candidate_total": len(packs),
                "limit": safe_max_pack_count,
            }

        prepared: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        total_capability_count = 0
        for pack in packs:
            pack_id = _safe_str(pack.get("pack_id")).strip()
            pack_version = _safe_str(pack.get("pack_version")).strip()
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
            raw_capabilities = pack.get("capabilities") if isinstance(pack.get("capabilities"), list) else []
            capabilities = [
                capability
                for capability in raw_capabilities
                if isinstance(capability, dict)
                and _has_readiness_value(capability.get("linked_proposal_artifact_evidence"))
            ]
            capability_count = len(capabilities)
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
            total_capability_count += capability_count
            prepared.append(
                {
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "pack_name": _safe_str(pack.get("pack_name")).strip() or pack_id,
                    "capabilities": capabilities,
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

        planned = [
            {
                "pack_id": item["pack_id"],
                "pack_version": item["pack_version"],
                "pack_name": item["pack_name"],
                "capability_count": len(item["capabilities"]),
                "evidence_source": "existing_linked_proposal_artifact_friction_evidence",
                "capabilities": [
                    {
                        "capability": _safe_str(capability.get("capability")).strip(),
                        "proposal_id": _safe_str(capability.get("proposal_id")).strip(),
                        "linked_proposal_artifact_evidence": _unique_texts(
                            capability.get("linked_proposal_artifact_evidence"),
                            limit=50,
                        ),
                    }
                    for capability in item["capabilities"]
                ],
                "writes_registry_metadata": not payload.dry_run,
                "writes_proposals": False,
                "approves_proposals": False,
                "promotes_capabilities": False,
                "enables_capabilities": False,
            }
            for item in prepared
        ]
        if not prepared:
            return {
                "ok": True,
                "applied": False,
                "status": "no_supported_proposal_evidence_backfill",
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
                    "writes_proposals": False,
                    "does_not_approve_proposals": True,
                    "does_not_promote_capabilities": True,
                    "does_not_enable_capabilities": True,
                    "does_not_execute_capabilities": True,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                },
            }
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
                    "writes_proposals": False,
                    "only_existing_linked_proposal_artifact_evidence": True,
                    "does_not_approve_proposals": True,
                    "does_not_promote_capabilities": True,
                    "does_not_enable_capabilities": True,
                    "does_not_execute_capabilities": True,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                },
            }

        batch = _record_capability_library_proposal_evidence_remediation_batch(
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
        refreshed_entries = list(refreshed_marketplace.catalog())
        refreshed_available_proposals = _available_capability_pack_proposals()
        refreshed_available_validation_receipts = _available_capability_pack_validation_receipts()
        refreshed_available_promotion_receipts = _available_capability_pack_promotion_receipts()
        refreshed_promotion_discipline = analyze_capability_pack_promotion_discipline(
            refreshed_entries,
            available_proposal_ids=refreshed_available_proposals["ids"],
            available_validation_receipt_ids=refreshed_available_validation_receipts["ids"],
            available_promotion_receipt_ids=refreshed_available_promotion_receipts["ids"],
            operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
        )
        after = _capability_library_proposal_evidence_remediation_projection(
            registry=refreshed_registry,
            entries=refreshed_entries,
            promotion_discipline=refreshed_promotion_discipline,
            generated_plugin_sync_performed=False,
        )
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
            "remaining_candidate_pack_count": int(after.get("candidate_pack_count") or 0),
            "remaining_candidate_capability_count": int(after.get("candidate_capability_count") or 0),
            "next_smallest_truthful_gap": _safe_str(after.get("next_smallest_truthful_gap")).strip(),
            "governance": {
                "scope": _PLUGIN_WRITE_SCOPE,
                "route": request.url.path,
                "writes_registry_metadata": applied,
                "writes_receipts": False,
                "writes_proposals": False,
                "only_existing_linked_proposal_artifact_evidence": True,
                "evidence_claim_scope": "existing_linked_proposal_artifact_friction_evidence",
                "does_not_write_validation_receipts": True,
                "does_not_write_proposal_review_receipts": True,
                "does_not_approve_proposals": True,
                "does_not_promote_capabilities": True,
                "does_not_enable_capabilities": True,
                "does_not_execute_capabilities": True,
                "promotion_authority": False,
                "execution_authority": False,
                "approval_authority": False,
                "memory_write": False,
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "plugin.capability_library.proposal_evidence_remediation.apply",
            "error": api_error_message(exc),
        }


@router.get("/capabilities/library/proposal-evidence/friction-summary-refs")
def capability_library_proposal_evidence_friction_summary_refs() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        entries = list(marketplace.catalog())
        available_proposals = _available_capability_pack_proposals()
        available_validation_receipts = _available_capability_pack_validation_receipts()
        available_promotion_receipts = _available_capability_pack_promotion_receipts()
        promotion_discipline = analyze_capability_pack_promotion_discipline(
            entries,
            available_proposal_ids=available_proposals["ids"],
            available_validation_receipt_ids=available_validation_receipts["ids"],
            available_promotion_receipt_ids=available_promotion_receipts["ids"],
            operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
        )
        plan = _capability_library_proposal_evidence_friction_summary_ref_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            generated_plugin_sync_performed=bool(synced),
        )
        return {
            "ok": True,
            "kind": "plugin.capability_library.proposal_evidence_friction_summary_refs",
            **plan,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "plugin.capability_library.proposal_evidence_friction_summary_refs",
            "error": api_error_message(exc),
        }


@router.post("/capabilities/library/proposal-evidence/friction-summary-refs/apply")
def apply_capability_library_proposal_evidence_friction_summary_refs(
    payload: CapabilityLibraryProposalEvidenceFrictionSummaryRefApplyIn,
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
        entries = list(marketplace.catalog())
        available_proposals = _available_capability_pack_proposals()
        available_validation_receipts = _available_capability_pack_validation_receipts()
        available_promotion_receipts = _available_capability_pack_promotion_receipts()
        promotion_discipline = analyze_capability_pack_promotion_discipline(
            entries,
            available_proposal_ids=available_proposals["ids"],
            available_validation_receipt_ids=available_validation_receipts["ids"],
            available_promotion_receipt_ids=available_promotion_receipts["ids"],
            operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
        )
        before = _capability_library_proposal_evidence_friction_summary_ref_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            generated_plugin_sync_performed=True,
        )
        raw_packs = before.get("packs")
        packs = [pack for pack in raw_packs if isinstance(pack, dict)] if isinstance(raw_packs, list) else []
        if selected_pack_ids:
            packs = [pack for pack in packs if _safe_str(pack.get("pack_id")).strip() in selected_pack_ids]
        if not packs:
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
                    "writes_proposals": False,
                    "only_existing_registry_friction_summary": True,
                    "does_not_approve_proposals": True,
                    "does_not_promote_capabilities": True,
                    "does_not_enable_capabilities": True,
                    "does_not_execute_capabilities": True,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                },
            }
        if len(packs) > safe_max_pack_count:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "proposal_evidence_friction_summary_ref_pack_limit_exceeded",
                "candidate_total": len(packs),
                "limit": safe_max_pack_count,
            }

        prepared: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        total_capability_count = 0
        for pack in packs:
            pack_id = _safe_str(pack.get("pack_id")).strip()
            pack_version = _safe_str(pack.get("pack_version")).strip()
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
            raw_capabilities = pack.get("capabilities") if isinstance(pack.get("capabilities"), list) else []
            capabilities = [
                capability
                for capability in raw_capabilities
                if isinstance(capability, dict) and _has_readiness_value(capability.get("friction_summary_ref"))
            ]
            capability_count = len(capabilities)
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
            total_capability_count += capability_count
            prepared.append(
                {
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "pack_name": _safe_str(pack.get("pack_name")).strip() or pack_id,
                    "capabilities": capabilities,
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

        planned = [
            {
                "pack_id": item["pack_id"],
                "pack_version": item["pack_version"],
                "pack_name": item["pack_name"],
                "capability_count": len(item["capabilities"]),
                "evidence_source": "existing_registry_friction_summary_ref",
                "capabilities": [
                    {
                        "capability": _safe_str(capability.get("capability")).strip(),
                        "proposal_id": _safe_str(capability.get("proposal_id")).strip(),
                        "friction_summary_field": _safe_str(capability.get("friction_summary_field")).strip(),
                        "friction_summary_ref": _safe_str(capability.get("friction_summary_ref")).strip(),
                    }
                    for capability in item["capabilities"]
                ],
                "writes_registry_metadata": not payload.dry_run,
                "writes_proposals": False,
                "approves_proposals": False,
                "promotes_capabilities": False,
                "enables_capabilities": False,
                "requires_future_review": True,
            }
            for item in prepared
        ]
        if not prepared:
            return {
                "ok": True,
                "applied": False,
                "status": "no_supported_proposal_evidence_friction_summary_ref_backfill",
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
                    "writes_proposals": False,
                    "only_existing_registry_friction_summary": True,
                    "does_not_approve_proposals": True,
                    "does_not_promote_capabilities": True,
                    "does_not_enable_capabilities": True,
                    "does_not_execute_capabilities": True,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                },
            }
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
                    "writes_proposals": False,
                    "only_existing_registry_friction_summary": True,
                    "evidence_claim_scope": _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_FRICTION_REF_CLAIM_SCOPE,
                    "does_not_approve_proposals": True,
                    "does_not_promote_capabilities": True,
                    "does_not_enable_capabilities": True,
                    "does_not_execute_capabilities": True,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                },
            }

        batch = _record_capability_library_proposal_evidence_friction_summary_ref_batch(
            registry=registry,
            prepared=prepared,
            route_path=request.url.path,
        )
        recorded = batch["recorded"]
        failed = batch["failed"]
        changed_records = [item for item in recorded if item.get("status") == "recorded"]

        refreshed_registry = _load_registry()
        refreshed_catalog = _compile_runtime_catalog(refreshed_registry)
        refreshed_runtime_catalog = _read_runtime_catalog_payload(refreshed_catalog)
        refreshed_marketplace = marketplace_from_plugin_catalog(refreshed_runtime_catalog)
        refreshed_entries = list(refreshed_marketplace.catalog())
        refreshed_available_proposals = _available_capability_pack_proposals()
        refreshed_available_validation_receipts = _available_capability_pack_validation_receipts()
        refreshed_available_promotion_receipts = _available_capability_pack_promotion_receipts()
        refreshed_promotion_discipline = analyze_capability_pack_promotion_discipline(
            refreshed_entries,
            available_proposal_ids=refreshed_available_proposals["ids"],
            available_validation_receipt_ids=refreshed_available_validation_receipts["ids"],
            available_promotion_receipt_ids=refreshed_available_promotion_receipts["ids"],
            operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
        )
        after = _capability_library_proposal_evidence_friction_summary_ref_projection(
            registry=refreshed_registry,
            entries=refreshed_entries,
            promotion_discipline=refreshed_promotion_discipline,
            generated_plugin_sync_performed=False,
        )
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
            "remaining_candidate_pack_count": int(after.get("candidate_pack_count") or 0),
            "remaining_candidate_capability_count": int(after.get("candidate_capability_count") or 0),
            "next_smallest_truthful_gap": _safe_str(after.get("next_smallest_truthful_gap")).strip(),
            "governance": {
                "scope": _PLUGIN_WRITE_SCOPE,
                "route": request.url.path,
                "writes_registry_metadata": applied,
                "writes_receipts": False,
                "writes_proposals": False,
                "only_existing_registry_friction_summary": True,
                "evidence_claim_scope": _CAPABILITY_LIBRARY_PROPOSAL_EVIDENCE_FRICTION_REF_CLAIM_SCOPE,
                "does_not_write_validation_receipts": True,
                "does_not_write_proposal_review_receipts": True,
                "does_not_approve_proposals": True,
                "does_not_promote_capabilities": True,
                "does_not_enable_capabilities": True,
                "does_not_execute_capabilities": True,
                "promotion_authority": False,
                "execution_authority": False,
                "approval_authority": False,
                "memory_write": False,
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "plugin.capability_library.proposal_evidence_friction_summary_refs.apply",
            "error": api_error_message(exc),
        }


@router.get("/capabilities/library/proposal-evidence/operator-intake/checklist")
def capability_library_operator_proposal_evidence_intake_checklist() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        entries = list(marketplace.catalog())
        available_proposals = _available_capability_pack_proposals()
        available_validation_receipts = _available_capability_pack_validation_receipts()
        available_promotion_receipts = _available_capability_pack_promotion_receipts()
        promotion_discipline = analyze_capability_pack_promotion_discipline(
            entries,
            available_proposal_ids=available_proposals["ids"],
            available_validation_receipt_ids=available_validation_receipts["ids"],
            available_promotion_receipt_ids=available_promotion_receipts["ids"],
            operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
        )
        source_plan = _capability_library_proposal_evidence_plan_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            generated_plugin_sync_performed=bool(synced),
        )
        checklist = _capability_library_operator_proposal_evidence_intake_checklist_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            source_plan=source_plan,
            generated_plugin_sync_performed=bool(synced),
        )
        return {
            "ok": True,
            "kind": "plugin.capability_library.operator_proposal_evidence_intake.checklist",
            **checklist,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "plugin.capability_library.operator_proposal_evidence_intake.checklist",
            "error": api_error_message(exc),
        }


@router.get("/capabilities/library/proposal-evidence/operator-intake/worksheet")
def capability_library_operator_proposal_evidence_intake_worksheet() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        entries = list(marketplace.catalog())
        available_proposals = _available_capability_pack_proposals()
        available_validation_receipts = _available_capability_pack_validation_receipts()
        available_promotion_receipts = _available_capability_pack_promotion_receipts()
        promotion_discipline = analyze_capability_pack_promotion_discipline(
            entries,
            available_proposal_ids=available_proposals["ids"],
            available_validation_receipt_ids=available_validation_receipts["ids"],
            available_promotion_receipt_ids=available_promotion_receipts["ids"],
            operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
        )
        source_plan = _capability_library_proposal_evidence_plan_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            generated_plugin_sync_performed=bool(synced),
        )
        worksheet = _capability_library_operator_proposal_evidence_intake_worksheet_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            source_plan=source_plan,
            generated_plugin_sync_performed=bool(synced),
        )
        return {
            "ok": True,
            "kind": "plugin.capability_library.operator_proposal_evidence_intake.worksheet",
            **worksheet,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "plugin.capability_library.operator_proposal_evidence_intake.worksheet",
            "error": api_error_message(exc),
        }


@router.get("/capabilities/library/proposal-evidence/operator-intake/export")
def capability_library_operator_proposal_evidence_intake_export() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        entries = list(marketplace.catalog())
        available_proposals = _available_capability_pack_proposals()
        available_validation_receipts = _available_capability_pack_validation_receipts()
        available_promotion_receipts = _available_capability_pack_promotion_receipts()
        promotion_discipline = analyze_capability_pack_promotion_discipline(
            entries,
            available_proposal_ids=available_proposals["ids"],
            available_validation_receipt_ids=available_validation_receipts["ids"],
            available_promotion_receipt_ids=available_promotion_receipts["ids"],
            operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
        )
        source_plan = _capability_library_proposal_evidence_plan_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            generated_plugin_sync_performed=bool(synced),
        )
        export = _capability_library_operator_proposal_evidence_intake_export_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            source_plan=source_plan,
            generated_plugin_sync_performed=bool(synced),
        )
        return {
            "ok": True,
            "kind": "plugin.capability_library.operator_proposal_evidence_intake.export",
            **export,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "plugin.capability_library.operator_proposal_evidence_intake.export",
            "error": api_error_message(exc),
        }


@router.post("/capabilities/library/proposal-evidence/operator-intake/import-preview")
def capability_library_operator_proposal_evidence_intake_import_preview(
    payload: CapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewIn,
) -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        entries = list(marketplace.catalog())
        available_proposals = _available_capability_pack_proposals()
        available_validation_receipts = _available_capability_pack_validation_receipts()
        available_promotion_receipts = _available_capability_pack_promotion_receipts()
        promotion_discipline = analyze_capability_pack_promotion_discipline(
            entries,
            available_proposal_ids=available_proposals["ids"],
            available_validation_receipt_ids=available_validation_receipts["ids"],
            available_promotion_receipt_ids=available_promotion_receipts["ids"],
            operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
        )
        source_plan = _capability_library_proposal_evidence_plan_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            generated_plugin_sync_performed=bool(synced),
        )
        preview = _capability_library_operator_proposal_evidence_intake_import_preview_projection(
            rows=payload.rows,
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            source_plan=source_plan,
            generated_plugin_sync_performed=bool(synced),
            max_row_count=payload.max_row_count,
            max_apply_group_count=payload.max_apply_group_count,
            use_suggested_evidence_refs=payload.use_suggested_evidence_refs,
        )
        return {
            "ok": True,
            "kind": "plugin.capability_library.operator_proposal_evidence_intake.import_preview",
            **preview,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "plugin.capability_library.operator_proposal_evidence_intake.import_preview",
            "error": api_error_message(exc),
        }


@router.get("/capabilities/library/proposal-evidence/operator-intake/audit")
def capability_library_operator_proposal_evidence_intake_audit() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        entries = list(marketplace.catalog())
        available_proposals = _available_capability_pack_proposals()
        available_validation_receipts = _available_capability_pack_validation_receipts()
        available_promotion_receipts = _available_capability_pack_promotion_receipts()
        promotion_discipline = analyze_capability_pack_promotion_discipline(
            entries,
            available_proposal_ids=available_proposals["ids"],
            available_validation_receipt_ids=available_validation_receipts["ids"],
            available_promotion_receipt_ids=available_promotion_receipts["ids"],
            operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
        )
        source_plan = _capability_library_proposal_evidence_plan_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            generated_plugin_sync_performed=bool(synced),
        )
        audit = _capability_library_operator_proposal_evidence_intake_audit_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            source_plan=source_plan,
            generated_plugin_sync_performed=bool(synced),
        )
        return {
            "ok": True,
            "kind": "plugin.capability_library.operator_proposal_evidence_intake.audit",
            **audit,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "plugin.capability_library.operator_proposal_evidence_intake.audit",
            "error": api_error_message(exc),
        }


@router.post("/capabilities/library/proposal-evidence/operator-intake/preview")
def preview_capability_library_operator_proposal_evidence_intake(
    payload: CapabilityLibraryOperatorProposalEvidenceIntakeApplyIn,
    request: Request,
) -> dict[str, object]:
    try:
        plan = _prepare_capability_library_operator_proposal_evidence_intake_plan(
            payload=payload,
            planned_writes_registry_metadata=False,
        )
        if plan.get("status") != "planned":
            response = _capability_library_operator_proposal_evidence_intake_problem_response(
                plan=plan,
                route_path=request.url.path,
                read_only=True,
                preview_only=True,
            )
            response["kind"] = "plugin.capability_library.operator_proposal_evidence_intake.preview"
            return response

        dry_run_fingerprint = _safe_str(plan.get("dry_run_fingerprint")).strip()
        planned_pack_count = int(plan.get("planned_pack_count") or 0)
        planned_capability_count = int(plan.get("planned_capability_count") or 0)
        evidence_ref_count = int(plan.get("evidence_ref_count") or 0)
        return {
            "ok": True,
            "applied": False,
            "kind": "plugin.capability_library.operator_proposal_evidence_intake.preview",
            "status": "preview",
            "dry_run": True,
            "planned_pack_count": planned_pack_count,
            "planned_capability_count": planned_capability_count,
            "evidence_ref_count": evidence_ref_count,
            "dry_run_fingerprint": dry_run_fingerprint,
            "dry_run_confirmation": {
                "required_for_apply": True,
                "fingerprint": dry_run_fingerprint,
                "fingerprint_contract": "stage17_operator_proposal_evidence_intake_dry_run_v1",
                "claim_scope": "operator_supplied_friction_evidence_reference_not_independent_verification",
                "planned_pack_count": planned_pack_count,
                "planned_capability_count": planned_capability_count,
                "evidence_ref_count": evidence_ref_count,
                "preview_route": request.url.path,
                "apply_route": _CAPABILITY_LIBRARY_OPERATOR_PROPOSAL_EVIDENCE_INTAKE_APPLY_ROUTE,
            },
            "planned": plan.get("planned") if isinstance(plan.get("planned"), list) else [],
            "skipped": plan.get("skipped") if isinstance(plan.get("skipped"), list) else [],
            "before": plan.get("before") if isinstance(plan.get("before"), dict) else {},
            "governance": _capability_library_operator_proposal_evidence_intake_governance(
                route_path=request.url.path,
                read_only=True,
                preview_only=True,
                writes_registry_metadata=False,
                generated_plugin_registry_sync_performed=bool(plan.get("generated_plugin_registry_sync_performed")),
            ),
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "plugin.capability_library.operator_proposal_evidence_intake.preview",
            "error": api_error_message(exc),
        }


@router.post("/capabilities/library/proposal-evidence/operator-intake/apply")
def apply_capability_library_operator_proposal_evidence_intake(
    payload: CapabilityLibraryOperatorProposalEvidenceIntakeApplyIn,
    request: Request,
) -> dict[str, object]:
    try:
        permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
        if not permission.allowed:
            return _permission_denied(permission)

        evidence_refs = _unique_texts(payload.evidence_refs, limit=50)
        try:
            evidence_refs_by_capability = _operator_proposal_evidence_refs_by_capability(
                payload.evidence_refs_by_capability
            )
        except Exception:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "invalid_evidence_refs_by_capability",
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "writes_registry_metadata": False,
                    "writes_proposals": False,
                    "does_not_approve_proposals": True,
                    "does_not_promote_capabilities": True,
                    "does_not_enable_capabilities": True,
                    "does_not_execute_capabilities": True,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                },
            }
        if not evidence_refs and not evidence_refs_by_capability:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "operator_evidence_refs_required",
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "writes_registry_metadata": False,
                    "writes_proposals": False,
                    "does_not_approve_proposals": True,
                    "does_not_promote_capabilities": True,
                    "does_not_enable_capabilities": True,
                    "does_not_execute_capabilities": True,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                },
            }

        safe_max_pack_count = max(1, min(int(payload.max_pack_count or 10), 50))
        safe_max_total_capability_count = max(1, min(int(payload.max_total_capability_count or 1000), 10000))
        safe_max_capability_count_per_pack = max(1, min(int(payload.max_capability_count_per_pack or 500), 500))
        try:
            selected_pack_ids = {_validate_plugin_id(raw_id) for raw_id in _unique_texts(payload.pack_ids, limit=100)}
            selected_capability_ids = {
                _validate_plugin_id(raw_id) for raw_id in _unique_texts(payload.capability_ids, limit=1000)
            }
        except Exception:
            return {"ok": False, "applied": False, "status": "blocked", "error": "invalid_selector_id"}

        registry = _load_registry()
        if selected_capability_ids:
            context = _capability_library_selected_promotion_discipline_context(
                registry=registry,
                selected_capability_ids=selected_capability_ids,
            )
            entries = context["entries"] if isinstance(context.get("entries"), list) else []
            promotion_discipline = (
                context["promotion_discipline"] if isinstance(context.get("promotion_discipline"), dict) else {}
            )
            before = _capability_library_selected_capability_readiness_projection(
                registry=registry,
                entries=entries,
                promotion_discipline=promotion_discipline,
                selected_pack_ids=selected_pack_ids,
                selected_capability_ids=selected_capability_ids,
                generated_plugin_sync_performed=bool(context.get("generated_plugin_registry_sync_performed")),
            )
        else:
            _sync_generated_plugins(registry)
            catalog = _save_registry_and_catalog(registry)
            runtime_catalog = _read_runtime_catalog_payload(catalog)
            marketplace = marketplace_from_plugin_catalog(runtime_catalog)
            entries = list(marketplace.catalog())
            available_proposals = _available_capability_pack_proposals()
            available_validation_receipts = _available_capability_pack_validation_receipts()
            available_promotion_receipts = _available_capability_pack_promotion_receipts()
            promotion_discipline = analyze_capability_pack_promotion_discipline(
                entries,
                available_proposal_ids=available_proposals["ids"],
                available_validation_receipt_ids=available_validation_receipts["ids"],
                available_promotion_receipt_ids=available_promotion_receipts["ids"],
                operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
            )
            before = _capability_library_proposal_evidence_plan_projection(
                registry=registry,
                entries=entries,
                promotion_discipline=promotion_discipline,
                generated_plugin_sync_performed=True,
            )
        candidates = _capability_library_operator_proposal_evidence_intake_candidates(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            selected_pack_ids=selected_pack_ids,
            selected_capability_ids=selected_capability_ids,
        )
        if not candidates:
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
                    "writes_proposals": False,
                    "does_not_approve_proposals": True,
                    "does_not_promote_capabilities": True,
                    "does_not_enable_capabilities": True,
                    "does_not_execute_capabilities": True,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                },
            }
        if len(candidates) > safe_max_pack_count:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "operator_evidence_intake_pack_limit_exceeded",
                "candidate_total": len(candidates),
                "limit": safe_max_pack_count,
            }

        prepared: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        total_capability_count = 0
        for pack in candidates:
            raw_capabilities = pack.get("capabilities") if isinstance(pack.get("capabilities"), list) else []
            capabilities = [capability for capability in raw_capabilities if isinstance(capability, dict)]
            capability_count = len(capabilities)
            if capability_count <= 0:
                skipped.append(
                    {
                        "pack_id": _safe_str(pack.get("pack_id")).strip(),
                        "pack_version": _safe_str(pack.get("pack_version")).strip(),
                        "error": "capability_ids_required",
                    }
                )
                continue
            if capability_count > safe_max_capability_count_per_pack:
                skipped.append(
                    {
                        "pack_id": _safe_str(pack.get("pack_id")).strip(),
                        "pack_version": _safe_str(pack.get("pack_version")).strip(),
                        "error": "candidate_capability_limit_exceeded",
                        "capability_count": capability_count,
                        "limit": safe_max_capability_count_per_pack,
                    }
                )
                continue
            total_capability_count += capability_count
            prepared.append(pack)
        if total_capability_count > safe_max_total_capability_count:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "total_capability_limit_exceeded",
                "capability_count": total_capability_count,
                "limit": safe_max_total_capability_count,
            }

        planned = [
            {
                "pack_id": _safe_str(item.get("pack_id")).strip(),
                "pack_version": _safe_str(item.get("pack_version")).strip(),
                "pack_name": _safe_str(item.get("pack_name")).strip(),
                "capability_count": len(item.get("capabilities") if isinstance(item.get("capabilities"), list) else []),
                "evidence_ref_count": sum(
                    len(
                        _operator_proposal_evidence_refs_for_capability(
                            evidence_refs,
                            evidence_refs_by_capability,
                            _safe_str(capability.get("capability")).strip(),
                        )
                    )
                    for capability in (item.get("capabilities") if isinstance(item.get("capabilities"), list) else [])
                    if isinstance(capability, dict)
                ),
                "shared_evidence_ref_count": len(evidence_refs),
                "capability_specific_evidence_ref_count": sum(
                    len(evidence_refs_by_capability.get(_safe_str(capability.get("capability")).strip(), []))
                    for capability in (item.get("capabilities") if isinstance(item.get("capabilities"), list) else [])
                    if isinstance(capability, dict)
                ),
                "claim_scope": "operator_supplied_friction_evidence_reference_not_independent_verification",
                "capabilities": [
                    {
                        "capability": _safe_str(capability.get("capability")).strip(),
                        "proposal_id": _safe_str(capability.get("proposal_id")).strip(),
                        "missing_requirements": _unique_texts(capability.get("missing_requirements"), limit=25),
                        "evidence_ref_count": len(
                            _operator_proposal_evidence_refs_for_capability(
                                evidence_refs,
                                evidence_refs_by_capability,
                                _safe_str(capability.get("capability")).strip(),
                            )
                        ),
                        "shared_evidence_ref_count": len(evidence_refs),
                        "capability_specific_evidence_ref_count": len(
                            evidence_refs_by_capability.get(_safe_str(capability.get("capability")).strip(), [])
                        ),
                    }
                    for capability in (item.get("capabilities") if isinstance(item.get("capabilities"), list) else [])
                    if isinstance(capability, dict)
                ],
                "writes_registry_metadata": not payload.dry_run,
                "writes_proposals": False,
                "approves_proposals": False,
                "promotes_capabilities": False,
                "enables_capabilities": False,
            }
            for item in prepared
        ]
        if not prepared:
            return {
                "ok": True,
                "applied": False,
                "status": "no_supported_operator_evidence_intake",
                "planned_pack_count": 0,
                "recorded_pack_count": 0,
                "recorded_capability_count": 0,
                "skipped": skipped,
                "before": before,
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "writes_registry_metadata": False,
                    "writes_proposals": False,
                    "does_not_approve_proposals": True,
                    "does_not_promote_capabilities": True,
                    "does_not_enable_capabilities": True,
                    "does_not_execute_capabilities": True,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                },
            }
        planned_capability_ids = _operator_proposal_evidence_planned_capability_ids(planned)
        unplanned_ref_ids = sorted(set(evidence_refs_by_capability) - set(planned_capability_ids))
        if unplanned_ref_ids:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "operator_evidence_refs_capability_not_planned",
                "unplanned_capability_ids": unplanned_ref_ids[:50],
                "unplanned_capability_ids_truncated": len(unplanned_ref_ids) > 50,
                "planned_capability_count": len(planned_capability_ids),
                "before": before,
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "writes_registry_metadata": False,
                    "writes_proposals": False,
                    "dry_run_required_before_apply": True,
                    "capability_scoped_evidence_refs_supported": True,
                    "does_not_approve_proposals": True,
                    "does_not_promote_capabilities": True,
                    "does_not_enable_capabilities": True,
                    "does_not_execute_capabilities": True,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                },
            }
        missing_ref_capability_ids = [
            capability_id
            for capability_id in planned_capability_ids
            if not _operator_proposal_evidence_refs_for_capability(
                evidence_refs,
                evidence_refs_by_capability,
                capability_id,
            )
        ]
        if missing_ref_capability_ids:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "operator_evidence_refs_required_for_capabilities",
                "missing_capability_ids": missing_ref_capability_ids[:50],
                "missing_capability_ids_truncated": len(missing_ref_capability_ids) > 50,
                "planned_capability_count": len(planned_capability_ids),
                "before": before,
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "writes_registry_metadata": False,
                    "writes_proposals": False,
                    "dry_run_required_before_apply": True,
                    "capability_scoped_evidence_refs_supported": True,
                    "does_not_approve_proposals": True,
                    "does_not_promote_capabilities": True,
                    "does_not_enable_capabilities": True,
                    "does_not_execute_capabilities": True,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                },
            }
        planned_evidence_ref_count = _operator_proposal_evidence_ref_count_for_planned(
            planned,
            evidence_refs,
            evidence_refs_by_capability,
        )
        capability_specific_evidence_ref_count = sum(
            len(evidence_refs_by_capability.get(capability_id, [])) for capability_id in planned_capability_ids
        )
        dry_run_fingerprint = _capability_library_operator_proposal_evidence_intake_plan_fingerprint(
            planned=planned,
            evidence_refs=evidence_refs,
            evidence_refs_by_capability=evidence_refs_by_capability,
        )
        if payload.dry_run:
            return {
                "ok": True,
                "applied": False,
                "status": "dry_run",
                "planned_pack_count": len(planned),
                "planned_capability_count": sum(int(item.get("capability_count") or 0) for item in planned),
                "evidence_ref_count": planned_evidence_ref_count,
                "shared_evidence_ref_count": len(evidence_refs),
                "capability_specific_evidence_ref_count": capability_specific_evidence_ref_count,
                "dry_run_fingerprint": dry_run_fingerprint,
                "projection_scope": _safe_str(before.get("projection_scope")).strip() or "full_library",
                "global_counts_included": bool(before.get("global_counts_included", True)),
                "projection_generated_at": _safe_str(before.get("generated_at")).strip(),
                "projection_evidence": before.get("projection_evidence")
                if isinstance(before.get("projection_evidence"), dict)
                else {},
                "dry_run_confirmation": {
                    "required_for_apply": True,
                    "fingerprint": dry_run_fingerprint,
                    "fingerprint_contract": "stage17_operator_proposal_evidence_intake_dry_run_v1",
                    "claim_scope": "operator_supplied_friction_evidence_reference_not_independent_verification",
                    "planned_pack_count": len(planned),
                    "planned_capability_count": sum(int(item.get("capability_count") or 0) for item in planned),
                    "evidence_ref_count": planned_evidence_ref_count,
                    "shared_evidence_ref_count": len(evidence_refs),
                    "capability_specific_evidence_ref_count": capability_specific_evidence_ref_count,
                    "apply_route": request.url.path,
                },
                "planned": planned,
                "skipped": skipped,
                "before": before,
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "writes_registry_metadata": False,
                    "writes_proposals": False,
                    "dry_run_required_before_apply": True,
                    "capability_scoped_evidence_refs_supported": True,
                    "operator_supplied_evidence_not_independently_verified": True,
                    "does_not_approve_proposals": True,
                    "does_not_promote_capabilities": True,
                    "does_not_enable_capabilities": True,
                    "does_not_execute_capabilities": True,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                },
            }
        provided_dry_run_fingerprint = _safe_str(payload.dry_run_fingerprint).strip()
        if provided_dry_run_fingerprint != dry_run_fingerprint:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "operator_evidence_intake_dry_run_confirmation_required",
                "planned_pack_count": len(planned),
                "planned_capability_count": sum(int(item.get("capability_count") or 0) for item in planned),
                "evidence_ref_count": planned_evidence_ref_count,
                "shared_evidence_ref_count": len(evidence_refs),
                "capability_specific_evidence_ref_count": capability_specific_evidence_ref_count,
                "dry_run_confirmation": {
                    "required_for_apply": True,
                    "fingerprint_contract": "stage17_operator_proposal_evidence_intake_dry_run_v1",
                    "fingerprint_matched": False,
                    "apply_route": request.url.path,
                },
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "writes_registry_metadata": False,
                    "writes_proposals": False,
                    "dry_run_required_before_apply": True,
                    "capability_scoped_evidence_refs_supported": True,
                    "operator_supplied_evidence_not_independently_verified": True,
                    "does_not_approve_proposals": True,
                    "does_not_promote_capabilities": True,
                    "does_not_enable_capabilities": True,
                    "does_not_execute_capabilities": True,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                },
            }

        batch = _record_capability_library_operator_proposal_evidence_intake_batch(
            registry=registry,
            prepared=prepared,
            evidence_refs=evidence_refs,
            evidence_refs_by_capability=evidence_refs_by_capability,
            payload=payload,
            route_path=request.url.path,
            update_runtime_catalog=not bool(selected_capability_ids),
        )
        recorded = batch["recorded"]
        failed = batch["failed"]
        changed_records = [item for item in recorded if item.get("status") == "recorded"]

        refreshed_registry = _load_registry()
        if selected_capability_ids:
            refreshed_context = _capability_library_selected_promotion_discipline_context(
                registry=refreshed_registry,
                selected_capability_ids=selected_capability_ids,
            )
            refreshed_entries = (
                refreshed_context["entries"] if isinstance(refreshed_context.get("entries"), list) else []
            )
            refreshed_promotion_discipline = (
                refreshed_context["promotion_discipline"]
                if isinstance(refreshed_context.get("promotion_discipline"), dict)
                else {}
            )
            after = _capability_library_selected_capability_readiness_projection(
                registry=refreshed_registry,
                entries=refreshed_entries,
                promotion_discipline=refreshed_promotion_discipline,
                selected_pack_ids=selected_pack_ids,
                selected_capability_ids=selected_capability_ids,
                generated_plugin_sync_performed=bool(refreshed_context.get("generated_plugin_registry_sync_performed")),
            )
        else:
            refreshed_catalog = _compile_runtime_catalog(refreshed_registry)
            refreshed_runtime_catalog = _read_runtime_catalog_payload(refreshed_catalog)
            refreshed_marketplace = marketplace_from_plugin_catalog(refreshed_runtime_catalog)
            refreshed_entries = list(refreshed_marketplace.catalog())
            refreshed_available_proposals = _available_capability_pack_proposals()
            refreshed_available_validation_receipts = _available_capability_pack_validation_receipts()
            refreshed_available_promotion_receipts = _available_capability_pack_promotion_receipts()
            refreshed_promotion_discipline = analyze_capability_pack_promotion_discipline(
                refreshed_entries,
                available_proposal_ids=refreshed_available_proposals["ids"],
                available_validation_receipt_ids=refreshed_available_validation_receipts["ids"],
                available_promotion_receipt_ids=refreshed_available_promotion_receipts["ids"],
                operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
            )
            after = _capability_library_proposal_evidence_plan_projection(
                registry=refreshed_registry,
                entries=refreshed_entries,
                promotion_discipline=refreshed_promotion_discipline,
                generated_plugin_sync_performed=False,
            )
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
            "evidence_ref_count": planned_evidence_ref_count,
            "shared_evidence_ref_count": len(evidence_refs),
            "capability_specific_evidence_ref_count": capability_specific_evidence_ref_count,
            "recorded": recorded,
            "failed": failed,
            "skipped": skipped,
            "dry_run_fingerprint": dry_run_fingerprint,
            "dry_run_confirmation": {
                "required_for_apply": True,
                "fingerprint_matched": True,
                "fingerprint_contract": "stage17_operator_proposal_evidence_intake_dry_run_v1",
                "apply_route": request.url.path,
            },
            "remaining_proposal_evidence_missing_count": int(after.get("proposal_evidence_missing_count") or 0),
            "remaining_proposal_evidence_ready_count": int(after.get("proposal_evidence_ready_count") or 0),
            "projection_scope": _safe_str(after.get("projection_scope")).strip() or "full_library",
            "global_counts_included": bool(after.get("global_counts_included", True)),
            "before_projection_generated_at": _safe_str(before.get("generated_at")).strip(),
            "after_projection_generated_at": _safe_str(after.get("generated_at")).strip(),
            "projection_evidence": after.get("projection_evidence")
            if isinstance(after.get("projection_evidence"), dict)
            else {},
            "next_smallest_truthful_gap": _safe_str(after.get("next_smallest_truthful_gap")).strip(),
            "governance": {
                "scope": _PLUGIN_WRITE_SCOPE,
                "route": request.url.path,
                "writes_registry_metadata": applied,
                "writes_proposals": False,
                "dry_run_required_before_apply": True,
                "capability_scoped_evidence_refs_supported": True,
                "operator_supplied_evidence_not_independently_verified": True,
                "evidence_claim_scope": "operator_supplied_friction_evidence_reference_not_independent_verification",
                "does_not_write_validation_receipts": True,
                "does_not_write_proposal_review_receipts": True,
                "does_not_approve_proposals": True,
                "does_not_promote_capabilities": True,
                "does_not_enable_capabilities": True,
                "does_not_execute_capabilities": True,
                "promotion_authority": False,
                "execution_authority": False,
                "approval_authority": False,
                "memory_write": False,
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "plugin.capability_library.operator_proposal_evidence_intake.apply",
            "error": api_error_message(exc),
        }


@router.get("/capabilities/library/proposal-review/plan")
def capability_library_proposal_review_plan() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        entries = list(marketplace.catalog())
        available_proposals = _available_capability_pack_proposals()
        available_validation_receipts = _available_capability_pack_validation_receipts()
        available_promotion_receipts = _available_capability_pack_promotion_receipts()
        promotion_discipline = analyze_capability_pack_promotion_discipline(
            entries,
            available_proposal_ids=available_proposals["ids"],
            available_validation_receipt_ids=available_validation_receipts["ids"],
            available_promotion_receipt_ids=available_promotion_receipts["ids"],
            operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
        )
        plan = _capability_library_proposal_review_plan_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            generated_plugin_sync_performed=synced,
        )
        return {
            "ok": True,
            "kind": "plugin.capability_library.proposal_review_plan",
            **plan,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "plugin.capability_library.proposal_review_plan",
            "error": api_error_message(exc),
        }


@router.get("/capabilities/library/proposal-review/apply-readiness")
def capability_library_proposal_review_apply_readiness() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        catalog = _save_registry_and_catalog(registry) if synced else _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        entries = list(marketplace.catalog())
        available_proposals = _available_capability_pack_proposals()
        available_validation_receipts = _available_capability_pack_validation_receipts()
        available_promotion_receipts = _available_capability_pack_promotion_receipts()
        promotion_discipline = analyze_capability_pack_promotion_discipline(
            entries,
            available_proposal_ids=available_proposals["ids"],
            available_validation_receipt_ids=available_validation_receipts["ids"],
            available_promotion_receipt_ids=available_promotion_receipts["ids"],
            operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
        )
        proposal_evidence_plan = _capability_library_proposal_evidence_plan_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            generated_plugin_sync_performed=bool(synced),
        )
        operator_evidence_audit = _capability_library_operator_proposal_evidence_intake_audit_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            source_plan=proposal_evidence_plan,
            generated_plugin_sync_performed=bool(synced),
        )
        proposal_review_plan = _capability_library_proposal_review_plan_projection(
            registry=registry,
            entries=entries,
            promotion_discipline=promotion_discipline,
            generated_plugin_sync_performed=bool(synced),
        )
        readiness = _capability_library_proposal_review_apply_readiness_projection(
            proposal_review_plan=proposal_review_plan,
            proposal_evidence_plan=proposal_evidence_plan,
            operator_evidence_audit=operator_evidence_audit,
            generated_plugin_sync_performed=bool(synced),
        )
        return {
            "ok": True,
            "kind": "plugin.capability_library.proposal_review_apply_readiness",
            **readiness,
            "catalog": {
                "path": _safe_str(catalog.get("path")).strip(),
                "total_plugins": int(runtime_catalog.get("total_plugins") or catalog.get("total_plugins") or 0),
                "total_tools": int(runtime_catalog.get("total_tools") or catalog.get("total_tools") or 0),
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "plugin.capability_library.proposal_review_apply_readiness",
            "error": api_error_message(exc),
        }


@router.post("/capabilities/library/proposal-review/apply")
def apply_capability_library_proposal_review(
    payload: CapabilityLibraryProposalReviewApplyIn,
    request: Request,
) -> dict[str, object]:
    try:
        permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
        if not permission.allowed:
            return _permission_denied(permission)

        plan = _prepare_capability_library_proposal_review_apply_plan(payload=payload)
        generated_sync = bool(plan.get("generated_plugin_registry_sync_performed"))
        action = _safe_str(plan.get("action")).strip() or _safe_str(payload.action).strip().lower()
        decided_status = _safe_str(plan.get("decision_status")).strip()
        if plan.get("status") != "planned":
            response: dict[str, object] = {
                "ok": bool(plan.get("ok")),
                "applied": False,
                "kind": "plugin.capability_library.proposal_review.apply",
                "status": _safe_str(plan.get("status")).strip() or "blocked",
                "planned_pack_count": int(plan.get("planned_pack_count") or 0),
                "planned_capability_count": int(plan.get("planned_capability_count") or 0),
                "planned_proposal_count": int(plan.get("planned_proposal_count") or 0),
                "before": plan.get("before") if isinstance(plan.get("before"), dict) else {},
                "governance": _capability_library_proposal_review_apply_governance(
                    route_path=request.url.path,
                    action=action,
                    decision_status=decided_status,
                    writes_proposal_review_receipts=False,
                    updates_proposal_records=False,
                    generated_plugin_registry_sync_performed=generated_sync,
                ),
            }
            for key in ("error", "allowed_actions", "candidate_total", "limit", "capability_count", "skipped"):
                if key in plan:
                    response[key] = plan[key]
            return response

        dry_run_fingerprint = _safe_str(plan.get("dry_run_fingerprint")).strip()
        planned = plan.get("planned") if isinstance(plan.get("planned"), list) else []
        skipped = plan.get("skipped") if isinstance(plan.get("skipped"), list) else []
        planned_pack_count = int(plan.get("planned_pack_count") or 0)
        planned_capability_count = int(plan.get("planned_capability_count") or 0)
        planned_proposal_count = int(plan.get("planned_proposal_count") or 0)
        if payload.dry_run:
            return {
                "ok": True,
                "applied": False,
                "kind": "plugin.capability_library.proposal_review.apply",
                "status": "dry_run",
                "planned_pack_count": planned_pack_count,
                "planned_capability_count": planned_capability_count,
                "planned_proposal_count": planned_proposal_count,
                "dry_run_fingerprint": dry_run_fingerprint,
                "projection_scope": _safe_str(plan.get("before", {}).get("projection_scope")).strip()
                if isinstance(plan.get("before"), dict)
                else "full_library",
                "global_counts_included": bool(
                    plan.get("before", {}).get("global_counts_included", True)
                    if isinstance(plan.get("before"), dict)
                    else True
                ),
                "projection_generated_at": _safe_str(plan.get("before", {}).get("generated_at")).strip()
                if isinstance(plan.get("before"), dict)
                else "",
                "projection_evidence": plan.get("before", {}).get("projection_evidence")
                if isinstance(plan.get("before"), dict)
                and isinstance(plan.get("before", {}).get("projection_evidence"), dict)
                else {},
                "dry_run_confirmation": {
                    "required_for_apply": True,
                    "fingerprint": dry_run_fingerprint,
                    "fingerprint_contract": "stage17_capability_library_proposal_review_apply_dry_run_v1",
                    "planned_pack_count": planned_pack_count,
                    "planned_capability_count": planned_capability_count,
                    "planned_proposal_count": planned_proposal_count,
                    "apply_route": request.url.path,
                },
                "planned": planned,
                "skipped": skipped,
                "before": plan.get("before") if isinstance(plan.get("before"), dict) else {},
                "governance": _capability_library_proposal_review_apply_governance(
                    route_path=request.url.path,
                    action=action,
                    decision_status=decided_status,
                    writes_proposal_review_receipts=False,
                    updates_proposal_records=False,
                    generated_plugin_registry_sync_performed=generated_sync,
                ),
            }

        provided_dry_run_fingerprint = _safe_str(payload.dry_run_fingerprint).strip()
        if provided_dry_run_fingerprint != dry_run_fingerprint:
            return {
                "ok": False,
                "applied": False,
                "kind": "plugin.capability_library.proposal_review.apply",
                "status": "blocked",
                "error": "capability_library_proposal_review_dry_run_confirmation_required",
                "planned_pack_count": planned_pack_count,
                "planned_capability_count": planned_capability_count,
                "planned_proposal_count": planned_proposal_count,
                "dry_run_confirmation": {
                    "required_for_apply": True,
                    "fingerprint_contract": "stage17_capability_library_proposal_review_apply_dry_run_v1",
                    "fingerprint_matched": False,
                    "apply_route": request.url.path,
                },
                "governance": _capability_library_proposal_review_apply_governance(
                    route_path=request.url.path,
                    action=action,
                    decision_status=decided_status,
                    writes_proposal_review_receipts=False,
                    updates_proposal_records=False,
                    generated_plugin_registry_sync_performed=generated_sync,
                ),
            }

        prepared = plan.get("prepared") if isinstance(plan.get("prepared"), list) else []
        batch = _record_capability_library_proposal_review_apply_batch(
            prepared=prepared,
            payload=payload,
            action=action,
            decided_status=decided_status,
            route_path=request.url.path,
        )
        recorded = batch["recorded"] if isinstance(batch.get("recorded"), list) else []
        failed = batch["failed"] if isinstance(batch.get("failed"), list) else []
        applied = bool(recorded)

        refreshed_registry = _load_registry()
        selected_capability_ids = set(_unique_texts(plan.get("selected_capability_ids"), limit=1000))
        selected_pack_ids = set(_unique_texts(plan.get("selected_pack_ids"), limit=100))
        if selected_capability_ids:
            refreshed_context = _capability_library_selected_promotion_discipline_context(
                registry=refreshed_registry,
                selected_capability_ids=selected_capability_ids,
            )
            refreshed_entries = (
                refreshed_context["entries"] if isinstance(refreshed_context.get("entries"), list) else []
            )
            refreshed_promotion_discipline = (
                refreshed_context["promotion_discipline"]
                if isinstance(refreshed_context.get("promotion_discipline"), dict)
                else {}
            )
            after_review = _capability_library_selected_capability_readiness_projection(
                registry=refreshed_registry,
                entries=refreshed_entries,
                promotion_discipline=refreshed_promotion_discipline,
                selected_pack_ids=selected_pack_ids,
                selected_capability_ids=selected_capability_ids,
                generated_plugin_sync_performed=bool(refreshed_context.get("generated_plugin_registry_sync_performed")),
            )
            after_promotion = after_review
        else:
            refreshed_catalog = _compile_runtime_catalog(refreshed_registry)
            refreshed_runtime_catalog = _read_runtime_catalog_payload(refreshed_catalog)
            refreshed_marketplace = marketplace_from_plugin_catalog(refreshed_runtime_catalog)
            refreshed_entries = list(refreshed_marketplace.catalog())
            refreshed_available_proposals = _available_capability_pack_proposals()
            refreshed_available_validation_receipts = _available_capability_pack_validation_receipts()
            refreshed_available_promotion_receipts = _available_capability_pack_promotion_receipts()
            refreshed_promotion_discipline = analyze_capability_pack_promotion_discipline(
                refreshed_entries,
                available_proposal_ids=refreshed_available_proposals["ids"],
                available_validation_receipt_ids=refreshed_available_validation_receipts["ids"],
                available_promotion_receipt_ids=refreshed_available_promotion_receipts["ids"],
                operator_review_decisions=_read_capability_pack_operator_review_decisions(limit=500),
            )
            after_review = _capability_library_proposal_review_plan_projection(
                registry=refreshed_registry,
                entries=refreshed_entries,
                promotion_discipline=refreshed_promotion_discipline,
                generated_plugin_sync_performed=False,
            )
            after_promotion = _capability_library_explicit_promotion_plan_projection(
                registry=refreshed_registry,
                entries=refreshed_entries,
                promotion_discipline=refreshed_promotion_discipline,
                generated_plugin_sync_performed=False,
            )
        review_complete = _safe_str(after_review.get("status")).strip() == "proposal_review_complete"
        next_gap = (
            _safe_str(after_promotion.get("next_smallest_truthful_gap")).strip()
            if review_complete
            else _safe_str(after_review.get("next_smallest_truthful_gap")).strip()
        )
        return {
            "ok": not failed,
            "applied": applied,
            "kind": "plugin.capability_library.proposal_review.apply",
            "status": "reviewed" if applied and not failed else ("partial" if applied else "blocked"),
            "dry_run": False,
            "batch_id": _safe_str(batch.get("batch_id")).strip(),
            "planned_pack_count": planned_pack_count,
            "planned_capability_count": planned_capability_count,
            "planned_proposal_count": planned_proposal_count,
            "recorded_proposal_count": len(recorded),
            "recorded_capability_count": sum(int(item.get("capability_count") or 0) for item in recorded),
            "recorded": recorded,
            "failed": failed,
            "skipped": skipped,
            "dry_run_fingerprint": dry_run_fingerprint,
            "dry_run_confirmation": {
                "required_for_apply": True,
                "fingerprint_matched": True,
                "fingerprint_contract": "stage17_capability_library_proposal_review_apply_dry_run_v1",
                "apply_route": request.url.path,
            },
            "remaining_proposal_review_missing_count": int(after_review.get("proposal_review_missing_count") or 0),
            "remaining_reviewable_capability_count": int(after_review.get("reviewable_capability_count") or 0),
            "promotable_capability_count": int(after_promotion.get("promotable_capability_count") or 0),
            "projection_scope": _safe_str(after_review.get("projection_scope")).strip() or "full_library",
            "global_counts_included": bool(after_review.get("global_counts_included", True)),
            "before_projection_generated_at": _safe_str(plan.get("before", {}).get("generated_at")).strip()
            if isinstance(plan.get("before"), dict)
            else "",
            "after_projection_generated_at": _safe_str(after_review.get("generated_at")).strip(),
            "projection_evidence": after_review.get("projection_evidence")
            if isinstance(after_review.get("projection_evidence"), dict)
            else {},
            "next_smallest_truthful_gap": next_gap,
            "governance": _capability_library_proposal_review_apply_governance(
                route_path=request.url.path,
                action=action,
                decision_status=decided_status,
                writes_proposal_review_receipts=applied,
                updates_proposal_records=applied,
                generated_plugin_registry_sync_performed=generated_sync,
            ),
        }
    except Exception as exc:
        return {
            "ok": False,
            "applied": False,
            "kind": "plugin.capability_library.proposal_review.apply",
            "status": "error",
            "error": api_error_message(exc),
        }


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


@router.post("/capabilities/packs/operator/review/decisions/bulk-from-surface")
def decide_capability_pack_operator_review_bulk_from_surface(
    payload: CapabilityPackOperatorReviewBulkDecisionFromSurfaceIn,
    request: Request,
) -> dict[str, object]:
    try:
        permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
        if not permission.allowed:
            return _permission_denied(permission)

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
        try:
            selected_pack_ids = {_validate_plugin_id(raw_id) for raw_id in _unique_texts(payload.pack_ids, limit=100)}
        except Exception:
            return {"ok": False, "applied": False, "status": "blocked", "error": "invalid_pack_id"}

        safe_max_pack_count = max(1, min(int(payload.max_pack_count or 10), 50))
        safe_max_total_capability_count = max(1, min(int(payload.max_total_capability_count or 5000), 10000))
        registry = _load_registry()
        catalog = _compile_runtime_catalog(registry)
        runtime_catalog = _read_runtime_catalog_payload(catalog)
        marketplace = marketplace_from_plugin_catalog(runtime_catalog)
        entries = list(marketplace.catalog())
        review = analyze_capability_pack_operator_review(entries)
        raw_packs = review.get("packs") if isinstance(review.get("packs"), list) else []
        operator_review_decisions = _read_capability_pack_operator_review_decisions(limit=500)
        already_decided = _capability_pack_operator_review_decision_keys(operator_review_decisions)
        decision_coverage = _capability_pack_operator_review_decision_coverage(operator_review_decisions)
        queue: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for raw_pack in raw_packs:
            if not isinstance(raw_pack, dict):
                continue
            pack_id = _safe_str(raw_pack.get("pack_id")).strip()
            pack_version = _safe_str(raw_pack.get("pack_version")).strip()
            if selected_pack_ids and pack_id not in selected_pack_ids:
                continue
            if not bool(raw_pack.get("operator_review_ready")) or not bool(raw_pack.get("decision_required")):
                skipped.append(
                    {
                        "pack_id": pack_id,
                        "pack_version": pack_version,
                        "error": "pack_operator_review_decision_not_required",
                        "blockers": _unique_texts(raw_pack.get("blockers"), limit=25),
                    }
                )
                continue
            capability_ids = _capability_pack_review_staged_capability_ids(
                entries,
                pack_id=pack_id,
                pack_version=pack_version,
            )
            if not capability_ids:
                skipped.append(
                    {"pack_id": pack_id, "pack_version": pack_version, "error": "staged_capabilities_required"}
                )
                continue
            if _capability_pack_operator_review_decision_covers(
                decision_coverage,
                pack_id=pack_id,
                pack_version=pack_version,
                capability_ids=capability_ids,
            ):
                skipped.append(
                    {
                        "pack_id": pack_id,
                        "pack_version": pack_version,
                        "error": "pack_operator_review_decision_already_recorded",
                    }
                )
                continue
            queue.append(
                {
                    "pack": raw_pack,
                    "pack_id": pack_id,
                    "pack_version": pack_version,
                    "capability_ids": capability_ids,
                }
            )

        missing_selected_pack_ids = sorted(
            selected_pack_ids
            - {
                _safe_str(pack.get("pack_id")).strip()
                for pack in raw_packs
                if isinstance(pack, dict) and _safe_str(pack.get("pack_id")).strip()
            }
        )
        for pack_id in missing_selected_pack_ids:
            skipped.append({"pack_id": pack_id, "pack_version": "", "error": "pack_not_found"})

        if not queue:
            return {
                "ok": True,
                "applied": False,
                "kind": "plugin.capability_pack.operator_review.bulk_decision",
                "status": "no_candidates",
                "planned_pack_count": 0,
                "recorded_pack_count": 0,
                "recorded_capability_count": 0,
                "skipped": skipped,
                "before": {
                    "operator_review_status": _safe_str(review.get("status")).strip(),
                    "review_queue_count": _count_value(review.get("review_queue_count")),
                    "decision_recorded_pack_count": len(already_decided),
                },
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "dry_run_default": True,
                    "writes_receipts": False,
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
            }
        if len(queue) > safe_max_pack_count:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "operator_review_decision_pack_limit_exceeded",
                "candidate_total": len(queue),
                "limit": safe_max_pack_count,
                "dry_run": payload.dry_run,
            }

        prepared: list[dict[str, Any]] = []
        total_capability_count = 0
        for item in queue:
            pack = item["pack"]
            pack_id = item["pack_id"]
            pack_version = item["pack_version"]
            capability_ids = item["capability_ids"]
            total_capability_count += len(capability_ids)
            prepared.append(
                {"pack": pack, "pack_id": pack_id, "pack_version": pack_version, "capability_ids": capability_ids}
            )
        if total_capability_count > safe_max_total_capability_count:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "operator_review_decision_capability_limit_exceeded",
                "capability_count": total_capability_count,
                "limit": safe_max_total_capability_count,
                "dry_run": payload.dry_run,
            }

        planned = [
            {
                "pack_id": item["pack_id"],
                "pack_version": item["pack_version"],
                "pack_name": _safe_str(item["pack"].get("pack_name")).strip(),
                "action": action,
                "decision_status": decided_status,
                "capability_count": len(item["capability_ids"]),
                "staged_capability_count": _count_value(item["pack"].get("staged_capability_count")),
                "quality_evidence_ready": bool(item["pack"].get("quality_evidence_ready")),
                "proposal_lineage_ready": bool(item["pack"].get("proposal_lineage_ready")),
                "validation_receipts_ready": bool(item["pack"].get("validation_receipts_ready")),
                "operator_review_rule_declared": bool(item["pack"].get("operator_review_rule_declared")),
                "operator_review_governance_declared": bool(item["pack"].get("operator_review_governance_declared")),
                "writes_receipt": not payload.dry_run,
            }
            for item in prepared
        ]
        if payload.dry_run:
            return {
                "ok": True,
                "applied": False,
                "kind": "plugin.capability_pack.operator_review.bulk_decision",
                "status": "dry_run",
                "dry_run": True,
                "planned_pack_count": len(prepared),
                "planned_capability_count": total_capability_count,
                "planned": planned,
                "skipped": skipped,
                "before": {
                    "operator_review_status": _safe_str(review.get("status")).strip(),
                    "review_queue_count": _count_value(review.get("review_queue_count")),
                    "decision_recorded_pack_count": len(already_decided),
                },
                "governance": {
                    "scope": _PLUGIN_WRITE_SCOPE,
                    "route": request.url.path,
                    "dry_run_default": True,
                    "writes_receipts": False,
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
            }

        batch_id = f"capability_pack_operator_review_batch_{_now_s()}_{uuid.uuid4().hex[:8]}"
        recorded: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        batch_meta = {
            **payload.meta,
            "bulk_from_operator_surface": True,
            "bulk_decision_batch_id": batch_id,
            "dry_run": False,
        }
        for item in prepared:
            try:
                receipt = _write_capability_pack_operator_review_decision_receipt(
                    pack=item["pack"],
                    pack_id=item["pack_id"],
                    pack_version=item["pack_version"],
                    action=action,
                    decided_status=decided_status,
                    actor=payload.actor,
                    reason=_safe_str(payload.reason).strip() or "stage17_capability_pack_operator_review_bulk_decision",
                    notes=_safe_str(payload.notes).strip(),
                    meta=batch_meta,
                    capability_ids=item["capability_ids"],
                    route=request.url.path,
                )
            except Exception as exc:
                failed.append(
                    {
                        "pack_id": item["pack_id"],
                        "pack_version": item["pack_version"],
                        "error": api_error_message(exc),
                    }
                )
                continue
            recorded.append(
                {
                    "pack_id": item["pack_id"],
                    "pack_version": item["pack_version"],
                    "receipt_id": receipt["receipt_id"],
                    "receipt_path": receipt["receipt_path"],
                    "capability_count": len(item["capability_ids"]),
                    "status": decided_status,
                }
            )

        refreshed_decisions = _read_capability_pack_operator_review_decisions(limit=500)
        available_proposals = _available_capability_pack_proposals()
        available_validation_receipts = _available_capability_pack_validation_receipts()
        available_promotion_receipts = _available_capability_pack_promotion_receipts()
        after_discipline = analyze_capability_pack_promotion_discipline(
            entries,
            available_proposal_ids=available_proposals["ids"],
            available_validation_receipt_ids=available_validation_receipts["ids"],
            available_promotion_receipt_ids=available_promotion_receipts["ids"],
            operator_review_decisions=refreshed_decisions,
        )
        applied = bool(recorded)
        return {
            "ok": not failed,
            "applied": applied,
            "kind": "plugin.capability_pack.operator_review.bulk_decision",
            "status": "recorded" if applied and not failed else ("partial" if applied else "blocked"),
            "dry_run": False,
            "batch_id": batch_id,
            "planned_pack_count": len(prepared),
            "planned_capability_count": total_capability_count,
            "recorded_pack_count": len(recorded),
            "recorded_capability_count": sum(int(item.get("capability_count") or 0) for item in recorded),
            "recorded": recorded,
            "failed": failed,
            "skipped": skipped,
            "promotion_discipline": {
                "status": _safe_str(after_discipline.get("status")).strip(),
                "pack_total": _count_value(after_discipline.get("pack_total")),
                "ready_pack_count": _count_value(after_discipline.get("ready_pack_count")),
                "blocked_pack_count": _count_value(after_discipline.get("blocked_pack_count")),
                "approved_pack_operator_review_count": _count_value(
                    after_discipline.get("approved_pack_operator_review_count")
                ),
                "next_smallest_truthful_gap": _safe_str(after_discipline.get("next_smallest_truthful_gap")).strip(),
            },
            "next_smallest_truthful_gap": _safe_str(after_discipline.get("next_smallest_truthful_gap")).strip(),
            "governance": {
                "scope": _PLUGIN_WRITE_SCOPE,
                "route": request.url.path,
                "dry_run_default": True,
                "writes_receipts": applied,
                "receipt_write_count": len(recorded),
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
        }
    except Exception as exc:
        return {
            "ok": False,
            "applied": False,
            "kind": "plugin.capability_pack.operator_review.bulk_decision",
            "status": "error",
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

        staged_capability_ids = _capability_pack_review_staged_capability_ids(
            list(entries),
            pack_id=pack_id,
            pack_version=pack_version,
        )
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

        recorded = _write_capability_pack_operator_review_decision_receipt(
            pack=pack,
            pack_id=pack_id,
            pack_version=pack_version,
            action=action,
            decided_status=decided_status,
            actor=payload.actor,
            reason=_safe_str(payload.reason).strip() or "requested",
            notes=_safe_str(payload.notes).strip(),
            meta=payload.meta,
            capability_ids=capability_ids,
        )
        return {
            "ok": True,
            "applied": True,
            "status": decided_status,
            "pack_id": pack_id,
            "pack_version": pack_version,
            "receipt_id": recorded["receipt_id"],
            "receipt_path": recorded["receipt_path"],
            "receipt": recorded["receipt"],
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


def _capability_pack_metadata_receipts_bulk_from_plan_fingerprint(*, planned: list[dict[str, Any]]) -> str:
    canonical_packs: list[dict[str, Any]] = []
    for item in planned:
        canonical_packs.append(
            {
                "pack_id": _safe_str(item.get("pack_id")).strip(),
                "pack_version": _safe_str(item.get("pack_version")).strip(),
                "capability_ids": sorted(_unique_texts(item.get("capability_ids"), limit=10000)),
                "promotion_rules": sorted(_unique_texts(item.get("promotion_rules"), limit=200)),
                "pack_governance": redact_governed_display_value(item.get("pack_governance")),
            }
        )
    canonical_packs.sort(key=lambda item: (item["pack_id"], item["pack_version"]))
    body = {
        "contract": "stage17_capability_pack_metadata_receipts_bulk_from_plan_dry_run_v1",
        "route": "/plugins/capabilities/packs/metadata/receipts/bulk-from-plan",
        "planned": canonical_packs,
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _capability_pack_metadata_receipts_bulk_governance(
    *,
    route_path: str,
    writes_registry_metadata: bool,
    writes_receipts: bool,
) -> dict[str, object]:
    return {
        "scope": _PLUGIN_WRITE_SCOPE,
        "route": route_path,
        "lifecycle_operation": "capability_pack_metadata_receipts_bulk_from_migration_plan",
        "policy_gate": _PLUGIN_WRITE_SCOPE,
        "receipt_contract": "plugin.capability_pack.metadata_receipt",
        "writes_registry_metadata": writes_registry_metadata,
        "writes_receipts": writes_receipts,
        "dry_run_required_before_apply": True,
        "does_not_approve_proposals": True,
        "does_not_promote_capabilities": True,
        "does_not_enable_capabilities": True,
        "does_not_execute_capabilities": True,
        "promotion_authority": False,
        "execution_authority": False,
        "approval_authority": False,
        "memory_write": False,
        "mutates_generated_artifacts": False,
    }


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
                "governance": _capability_pack_metadata_receipts_bulk_governance(
                    route_path=request.url.path,
                    writes_registry_metadata=False,
                    writes_receipts=False,
                ),
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

        planned: list[dict[str, Any]] = []
        for item in prepared:
            candidate = item["candidate"]
            promotion_rules = _unique_texts(candidate.get("suggested_promotion_rules"), limit=50)
            pack_governance = dict(candidate.get("suggested_pack_governance") or {})
            capability_ids = list(item["capability_ids"])
            planned.append(
                {
                    "pack_id": item["pack_id"],
                    "pack_version": item["pack_version"],
                    "pack_name": _safe_str(candidate.get("pack_name")).strip() or item["pack_id"],
                    "capability_count": len(capability_ids),
                    "capability_ids": capability_ids,
                    "promotion_rules": promotion_rules,
                    "pack_governance": redact_governed_display_value(pack_governance),
                    "writes_registry_metadata": not payload.dry_run,
                    "writes_receipt": not payload.dry_run,
                }
            )
        planned_capability_count = sum(int(item.get("capability_count") or 0) for item in planned)
        dry_run_fingerprint = _capability_pack_metadata_receipts_bulk_from_plan_fingerprint(planned=planned)
        if payload.dry_run:
            return {
                "ok": True,
                "applied": False,
                "status": "dry_run",
                "planned_pack_count": len(planned),
                "planned_capability_count": planned_capability_count,
                "dry_run_fingerprint": dry_run_fingerprint,
                "dry_run_confirmation": {
                    "required_for_apply": True,
                    "fingerprint": dry_run_fingerprint,
                    "fingerprint_contract": "stage17_capability_pack_metadata_receipts_bulk_from_plan_dry_run_v1",
                    "planned_pack_count": len(planned),
                    "planned_capability_count": planned_capability_count,
                    "apply_route": request.url.path,
                },
                "planned": planned,
                "plan": plan,
                "governance": _capability_pack_metadata_receipts_bulk_governance(
                    route_path=request.url.path,
                    writes_registry_metadata=False,
                    writes_receipts=False,
                ),
            }
        provided_dry_run_fingerprint = _safe_str(payload.dry_run_fingerprint).strip()
        if provided_dry_run_fingerprint != dry_run_fingerprint:
            return {
                "ok": False,
                "applied": False,
                "status": "blocked",
                "error": "capability_pack_metadata_receipts_bulk_from_plan_dry_run_confirmation_required",
                "planned_pack_count": len(planned),
                "planned_capability_count": planned_capability_count,
                "dry_run_confirmation": {
                    "required_for_apply": True,
                    "fingerprint_contract": "stage17_capability_pack_metadata_receipts_bulk_from_plan_dry_run_v1",
                    "fingerprint_matched": False,
                    "apply_route": request.url.path,
                },
                "planned": planned,
                "governance": _capability_pack_metadata_receipts_bulk_governance(
                    route_path=request.url.path,
                    writes_registry_metadata=False,
                    writes_receipts=False,
                ),
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
            "dry_run_fingerprint": dry_run_fingerprint,
            "dry_run_confirmation": {
                "required_for_apply": True,
                "fingerprint_matched": True,
                "fingerprint_contract": "stage17_capability_pack_metadata_receipts_bulk_from_plan_dry_run_v1",
                "apply_route": request.url.path,
            },
            "recorded_pack_count": len(recorded),
            "recorded_capability_count": sum(int(item.get("capability_count") or 0) for item in recorded),
            "recorded": recorded,
            "remaining_candidate_total": int(refreshed_plan.get("candidate_total") or 0),
            "next_smallest_truthful_gap": str(refreshed_plan.get("next_smallest_truthful_gap") or ""),
            "governance": _capability_pack_metadata_receipts_bulk_governance(
                route_path=request.url.path,
                writes_registry_metadata=True,
                writes_receipts=True,
            ),
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
        run_meta = dict(payload.meta or {})
        if not _safe_str(run_meta.get("caller_context")).strip():
            run_meta["caller_context"] = "plugin_tool_route"
        run_payload = PluginRunIn(
            id=plugin_id,
            action=action,
            input=payload.input,
            reason=payload.reason,
            approval_id=payload.approval_id,
            idempotency_key=payload.idempotency_key,
            meta=run_meta,
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
        previous_meta = dict(previous.get("meta") or {}) if isinstance(previous.get("meta"), dict) else {}
        previous_status = _safe_str(previous.get("status")).strip().lower()
        previous_promotion_status = _safe_str(previous_meta.get("promotion_status")).strip().lower()
        disabled_from_promotion_status = _safe_str(previous_meta.get("disabled_from_promotion_status")).strip().lower()
        has_promotion_receipt = bool(_safe_str(previous_meta.get("promotion_receipt_id")).strip())
        was_staged = (
            previous_status == "staged"
            or previous_promotion_status == "staged"
            or (
                previous_status == "disabled"
                and disabled_from_promotion_status == "staged"
                and not has_promotion_receipt
            )
        )
        promoted_ts = _now_s()
        actor = redact_governed_value(_safe_str(payload.actor).strip())
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
                    "promoted_by": actor,
                }
            )
            current["meta"] = meta
        else:
            meta = dict(current.get("meta") or {}) if isinstance(current.get("meta"), dict) else {}
            promotion_status = _safe_str(meta.get("promotion_status")).strip().lower()
            if promotion_status in {"disabled", "uninstalled"}:
                restored_status = _safe_str(meta.get("disabled_from_promotion_status")).strip().lower()
                meta["promotion_status"] = restored_status if restored_status == "promoted" else "enabled"
            meta["status"] = "enabled"
            meta["enabled_ts"] = promoted_ts
            meta["enabled_by"] = actor
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

        payload_meta = redact_governed_metadata(payload.meta)
        lifecycle = _plugin_disable_lifecycle(payload_meta)
        requested_lifecycle_action = _safe_str(lifecycle.get("requested_action")).strip()
        if not bool(lifecycle.get("supported")):
            return _unsupported_plugin_lifecycle_action(
                plugin_id=plugin_id,
                requested_action=requested_lifecycle_action,
                route=request.url.path,
            )

        disabled_ts = _now_s()
        actor = redact_governed_value(_safe_str(payload.actor).strip())
        previous = dict(current)
        meta = dict(current.get("meta") or {}) if isinstance(current.get("meta"), dict) else {}
        previous_status = _safe_str(current.get("status")).strip().lower()
        promotion_status = _safe_str(meta.get("promotion_status")).strip().lower()
        lifecycle_action = _safe_str(lifecycle.get("action")).strip() or "disable"
        lifecycle_status = _safe_str(lifecycle.get("lifecycle_status")).strip() or "disabled"
        lifecycle_receipt_id = _plugin_lifecycle_receipt_id(plugin_id, lifecycle_action, disabled_ts)
        lifecycle_receipt_path = _plugin_lifecycle_receipt_path(lifecycle_receipt_id)
        if promotion_status:
            meta["disabled_from_promotion_status"] = promotion_status
        if previous_status:
            meta["disabled_from_status"] = previous_status
        meta[f"{lifecycle_status}_from_status"] = previous_status
        meta[f"{lifecycle_status}_from_promotion_status"] = promotion_status
        meta["promotion_status"] = "disabled"
        meta["status"] = "disabled"
        meta["disabled_ts"] = disabled_ts
        meta["disabled_by"] = actor
        meta["lifecycle_action"] = lifecycle_action
        meta["lifecycle_status"] = lifecycle_status
        meta["lifecycle_status_ts"] = disabled_ts
        meta["lifecycle_status_by"] = actor
        meta["lifecycle_reason"] = redact_governed_value(_safe_str(payload.reason).strip() or "requested")
        meta["lifecycle_receipt_id"] = lifecycle_receipt_id
        meta["lifecycle_receipt_path"] = str(lifecycle_receipt_path)
        meta["lifecycle_receipt_kind"] = "plugin.lifecycle.receipt"
        current["meta"] = meta
        current["enabled"] = False
        current["status"] = "disabled"
        current["updated_ts"] = disabled_ts
        disabled = _normalize_plugin_record(plugin_id, current)
        _write_plugin(registry, disabled)
        catalog = _save_registry_and_catalog(registry)
        lifecycle_receipt = _write_plugin_lifecycle_receipt(
            plugin_id=plugin_id,
            receipt_id=lifecycle_receipt_id,
            receipt_path=lifecycle_receipt_path,
            previous=previous,
            current=disabled,
            payload=payload,
            recorded_ts=disabled_ts,
            lifecycle_action=lifecycle_action,
            lifecycle_status=lifecycle_status,
            catalog=catalog,
        )

        return {
            "ok": True,
            "applied": True,
            "id": plugin_id,
            "enabled": False,
            "status": "disabled",
            "message": lifecycle_status,
            "lifecycle_action": lifecycle_action,
            "lifecycle_status": lifecycle_status,
            "lifecycle_receipt_id": lifecycle_receipt_id,
            "lifecycle_receipt_path": str(lifecycle_receipt_path),
            "lifecycle_receipt": lifecycle_receipt,
            "governance": _plugin_lifecycle_governance(
                route=request.url.path,
                lifecycle_action=lifecycle_action,
                lifecycle_status=lifecycle_status,
                writes_registry_metadata=True,
                writes_lifecycle_receipt=True,
            ),
            "catalog": catalog,
        }
    except Exception as exc:
        return {"ok": False, "error": api_error_message(exc)}


@router.get("/lifecycle/repair/history")
def plugin_lifecycle_repair_history(id: str, limit: int = 20) -> dict[str, object]:
    try:
        plugin_id = _validate_plugin_id(id)
        safe_limit = max(1, min(int(limit or 20), 200))
        registry = _load_registry()
        current = _read_plugin(registry, plugin_id)
        receipts = _read_plugin_lifecycle_receipts(plugin_id=plugin_id, limit=safe_limit)
        return _plugin_lifecycle_repair_history_projection(
            plugin_id=plugin_id,
            current=current,
            receipts=receipts,
        )
    except Exception as exc:
        return {
            "ok": False,
            "applied": False,
            "kind": "plugin.lifecycle.repair_history_readback",
            "status": "error",
            "error": api_error_message(exc),
            "governance": _plugin_lifecycle_repair_history_governance(),
        }


@router.post("/lifecycle/repair")
def repair_plugin_lifecycle(payload: PluginLifecycleRepairIn, request: Request) -> dict[str, object]:
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

        payload_meta = redact_governed_metadata(payload.meta)
        repair = _plugin_repair_lifecycle(payload_meta)
        requested_lifecycle_action = _safe_str(repair.get("requested_action")).strip()
        if not bool(repair.get("supported")):
            return _unsupported_plugin_lifecycle_action(
                plugin_id=plugin_id,
                requested_action=requested_lifecycle_action,
                route=request.url.path,
                gate="plugin_lifecycle_repair",
                supported_actions=["repair", "restore"],
                dry_run_required_before_apply=True,
            )

        lifecycle_before = _plugin_lifecycle_state(current, payload_meta)
        lifecycle_action = _safe_str(repair.get("action")).strip() or "repair"
        if not bool(lifecycle_before.get("blocks_promotion")) and not bool(lifecycle_before.get("blocks_execution")):
            return {
                "ok": False,
                "applied": False,
                "id": plugin_id,
                "status": "not_required",
                "error": "lifecycle_repair_not_required",
                "lifecycle_before": redact_governed_display_value(lifecycle_before),
                "governance": _plugin_lifecycle_governance(
                    gate="plugin_lifecycle_repair",
                    route=request.url.path,
                    lifecycle_action=lifecycle_action,
                    lifecycle_status="active",
                    writes_registry_metadata=False,
                    writes_lifecycle_receipt=False,
                    dry_run_required_before_apply=True,
                ),
            }

        meta = dict(current.get("meta") or {}) if isinstance(current.get("meta"), dict) else {}
        repair_plan = _plugin_lifecycle_repair_plan(
            plugin_id=plugin_id,
            current=current,
            meta=meta,
            lifecycle_before=lifecycle_before,
            lifecycle_action=lifecycle_action,
        )
        dry_run_fingerprint = _plugin_lifecycle_repair_fingerprint(plan=repair_plan)
        if payload.dry_run:
            return {
                "ok": True,
                "applied": False,
                "id": plugin_id,
                "status": "dry_run",
                "current_status": _safe_str(current.get("status")).strip(),
                "target_status": _safe_str(repair_plan.get("target", {}).get("status")).strip(),
                "lifecycle_action": lifecycle_action,
                "lifecycle_before": redact_governed_display_value(lifecycle_before),
                "planned_lifecycle_repair": repair_plan,
                "dry_run_fingerprint": dry_run_fingerprint,
                "dry_run_confirmation": {
                    "required_for_apply": True,
                    "fingerprint": dry_run_fingerprint,
                    "fingerprint_contract": "stage17_plugin_lifecycle_repair_dry_run_v1",
                    "apply_route": request.url.path,
                },
                "governance": _plugin_lifecycle_governance(
                    gate="plugin_lifecycle_repair",
                    route=request.url.path,
                    lifecycle_action=lifecycle_action,
                    lifecycle_status="active",
                    writes_registry_metadata=False,
                    writes_lifecycle_receipt=False,
                    dry_run_required_before_apply=True,
                ),
            }
        provided_dry_run_fingerprint = _safe_str(payload.dry_run_fingerprint).strip()
        if provided_dry_run_fingerprint != dry_run_fingerprint:
            return {
                "ok": False,
                "applied": False,
                "id": plugin_id,
                "status": "blocked",
                "error": "plugin_lifecycle_repair_dry_run_confirmation_required",
                "current_status": _safe_str(current.get("status")).strip(),
                "target_status": _safe_str(repair_plan.get("target", {}).get("status")).strip(),
                "lifecycle_action": lifecycle_action,
                "planned_lifecycle_repair": repair_plan,
                "dry_run_confirmation": {
                    "required_for_apply": True,
                    "fingerprint_contract": "stage17_plugin_lifecycle_repair_dry_run_v1",
                    "fingerprint_matched": False,
                    "apply_route": request.url.path,
                },
                "governance": _plugin_lifecycle_governance(
                    gate="plugin_lifecycle_repair",
                    route=request.url.path,
                    lifecycle_action=lifecycle_action,
                    lifecycle_status="active",
                    writes_registry_metadata=False,
                    writes_lifecycle_receipt=False,
                    dry_run_required_before_apply=True,
                ),
            }

        repaired_ts = _now_s()
        actor = redact_governed_value(_safe_str(payload.actor).strip())
        previous = dict(current)
        previous_status = _safe_str(current.get("status")).strip().lower()
        previous_lifecycle_status = _safe_str(lifecycle_before.get("status")).strip()
        previous_lifecycle_source = _safe_str(lifecycle_before.get("source")).strip()
        previous_lifecycle_error = _safe_str(lifecycle_before.get("error")).strip()
        previous_lifecycle_receipt_id = _safe_str(meta.get("lifecycle_receipt_id")).strip()
        target = repair_plan.get("target") if isinstance(repair_plan.get("target"), dict) else {}
        restored_status = _safe_str(target.get("status")).strip() or "disabled"
        restored_promotion_status = _safe_str(target.get("promotion_status")).strip() or "disabled"
        lifecycle_receipt_id = _plugin_lifecycle_receipt_id(plugin_id, lifecycle_action, repaired_ts)
        lifecycle_receipt_path = _plugin_lifecycle_receipt_path(lifecycle_receipt_id)

        for key in (
            "capability_lifecycle_status",
            "deprecation_status",
            "quarantine_status",
        ):
            meta.pop(key, None)
        meta["status"] = restored_status
        meta["promotion_status"] = restored_promotion_status
        meta["lifecycle_action"] = lifecycle_action
        meta["lifecycle_status"] = "active"
        meta["lifecycle_state"] = "active"
        meta["lifecycle_status_ts"] = repaired_ts
        meta["lifecycle_status_by"] = actor
        meta["lifecycle_reason"] = redact_governed_value(_safe_str(payload.reason).strip() or "requested")
        meta["lifecycle_repair_action"] = lifecycle_action
        meta["lifecycle_repair_status"] = "repaired"
        meta["lifecycle_repair_ts"] = repaired_ts
        meta["lifecycle_repair_by"] = actor
        meta["lifecycle_repair_reason"] = redact_governed_value(_safe_str(payload.reason).strip() or "requested")
        meta["lifecycle_repair_previous_status"] = previous_lifecycle_status
        meta["lifecycle_repair_previous_source"] = previous_lifecycle_source
        meta["lifecycle_repair_previous_error"] = previous_lifecycle_error
        meta["lifecycle_repair_previous_receipt_id"] = previous_lifecycle_receipt_id
        meta["lifecycle_repair_restored_status"] = restored_status
        meta["lifecycle_repair_restored_promotion_status"] = restored_promotion_status
        meta["lifecycle_repair_receipt_id"] = lifecycle_receipt_id
        meta["lifecycle_repair_receipt_path"] = str(lifecycle_receipt_path)
        meta["lifecycle_receipt_id"] = lifecycle_receipt_id
        meta["lifecycle_receipt_path"] = str(lifecycle_receipt_path)
        meta["lifecycle_receipt_kind"] = "plugin.lifecycle.receipt"
        current["meta"] = meta
        current["enabled"] = False
        current["status"] = restored_status
        current["updated_ts"] = repaired_ts
        repaired = _normalize_plugin_record(plugin_id, current)
        _write_plugin(registry, repaired)
        catalog = _save_registry_and_catalog(registry)
        lifecycle_receipt = _write_plugin_lifecycle_receipt(
            plugin_id=plugin_id,
            receipt_id=lifecycle_receipt_id,
            receipt_path=lifecycle_receipt_path,
            previous=previous,
            current=repaired,
            payload=payload,
            recorded_ts=repaired_ts,
            lifecycle_action=lifecycle_action,
            lifecycle_status="active",
            catalog=catalog,
            route=request.url.path,
            gate="plugin_lifecycle_repair",
        )
        lifecycle_after = _plugin_lifecycle_state(repaired, {})

        return {
            "ok": True,
            "applied": True,
            "id": plugin_id,
            "enabled": False,
            "status": restored_status,
            "previous_status": previous_status,
            "message": "lifecycle_repaired",
            "lifecycle_action": lifecycle_action,
            "lifecycle_status": "active",
            "lifecycle_repair_status": "repaired",
            "lifecycle_before": redact_governed_display_value(lifecycle_before),
            "lifecycle_after": redact_governed_display_value(lifecycle_after),
            "planned_lifecycle_repair": repair_plan,
            "dry_run_fingerprint": dry_run_fingerprint,
            "dry_run_confirmation": {
                "required_for_apply": True,
                "fingerprint_matched": True,
                "fingerprint_contract": "stage17_plugin_lifecycle_repair_dry_run_v1",
                "apply_route": request.url.path,
            },
            "lifecycle_receipt_id": lifecycle_receipt_id,
            "lifecycle_receipt_path": str(lifecycle_receipt_path),
            "lifecycle_receipt": lifecycle_receipt,
            "governance": _plugin_lifecycle_governance(
                gate="plugin_lifecycle_repair",
                route=request.url.path,
                lifecycle_action=lifecycle_action,
                lifecycle_status="active",
                writes_registry_metadata=True,
                writes_lifecycle_receipt=True,
                dry_run_required_before_apply=True,
            ),
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
        payload_meta = dict(payload.meta or {}) if isinstance(payload.meta, dict) else {}
        if not _safe_str(payload_meta.get("caller_context")).strip():
            payload_meta["caller_context"] = "direct_plugin_route"
        lifecycle = _plugin_lifecycle_state(current, payload_meta)
        if bool(lifecycle.get("blocks_execution")):
            lifecycle_status = _safe_str(lifecycle.get("status")).strip() or "blocked"
            return {
                "ok": False,
                "error": _safe_str(lifecycle.get("error")).strip() or "plugin_lifecycle_blocked",
                "id": plugin_id,
                "status": lifecycle_status,
                "lifecycle": redact_governed_display_value(lifecycle),
                "message": "Plugin execution is blocked by the recorded lifecycle state.",
                "governance": {
                    "plane": "P3_GOVERNANCE",
                    "gate": "plugin_lifecycle_gate",
                    "scope": "plugin.run",
                    "route": "/plugins/run",
                    "next_step": "review_plugin_lifecycle_receipt_before_execution",
                    "operator_hint": "A quarantined, deprecated, archived, retired, or unknown lifecycle state must be reviewed before execution.",
                    "does_not_execute_capabilities": True,
                    "promotion_authority": False,
                    "execution_authority": False,
                    "approval_authority": False,
                    "memory_write": False,
                },
            }
        if not bool(current.get("enabled", False)):
            current_status = _safe_str(current.get("status")).strip() or "disabled"
            error = "plugin_staged" if current_status == "staged" else "plugin_disabled"
            return {"ok": False, "error": error, "id": plugin_id, "status": current_status}
        registry_meta = dict(current.get("meta") or {}) if isinstance(current.get("meta"), dict) else {}
        compatibility = _plugin_core_compatibility(registry_meta)
        if not bool(compatibility.get("compatible")):
            return _plugin_runtime_compatibility_blocked(
                plugin_id=plugin_id,
                action=requested_action,
                compatibility=compatibility,
            )
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

        dry_run = _to_bool(payload_meta.get("dry_run"), default=False)
        receipt = _redact_plugin_receipt(_execute_plugin_action(current, capability, payload.input, dry_run=dry_run))
        invocation_receipt = _capability_pack_invocation_receipt(
            plugin=current,
            capability=capability,
            action=action,
            payload_meta=payload_meta,
            receipt=receipt,
            risk_tier=risk_tier,
            required_trust=required_trust,
            current_trust=trust_level,
            dry_run=dry_run,
        )
        receipt["capability_pack_invocation"] = invocation_receipt
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
                "capability_pack_invocation": invocation_receipt,
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
            "capability_pack_invocation": invocation_receipt,
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
