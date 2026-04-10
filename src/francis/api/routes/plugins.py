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

from fastapi import APIRouter
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from francis.governance import approvals as approval_store
from francis.kernel.paths import data_dir, repo_root
from francis.plugin_factory.spec_builder import build_plugin
from francis.plugin_system import PluginLoader, PluginSpec, ToolSpec
from francis.trust.levels import get_state

router = APIRouter()

_PLUGIN_LOADER = PluginLoader()


def _art_dir() -> Path:
    return data_dir() / "artifacts" / "plugins"


def _gen_dir() -> Path:
    return repo_root() / "plugins" / "generated"


def _registry_path() -> Path:
    return data_dir() / "plugins" / "_registry.json"

_PLUGIN_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{1,127}$")
_ALLOWED_STATUSES = {"enabled", "disabled", "error", "installing", "uninstalling", "updating", "unknown", "uninstalled"}
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
        return {"version": int(raw.get("version") or 1), "updated_at": int(raw.get("updated_at") or _now_s()), "plugins": plugins}

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


def _normalize_plugin_record(plugin_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    status_raw = _safe_str(raw.get("status")).strip().lower()
    enabled = raw.get("enabled")
    enabled_bool: bool | None = enabled if isinstance(enabled, bool) else None

    if enabled_bool is None and status_raw:
        if status_raw in {"enabled"}:
            enabled_bool = True
        elif status_raw in {"disabled", "uninstalled"}:
            enabled_bool = False

    status = _normalize_status(raw.get("status"), enabled_bool)
    if enabled_bool is None:
        enabled_bool = status != "disabled" and status != "uninstalled"

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
                "description": _safe_str(manifest.get("description")).strip() or _safe_str(current.get("description")).strip(),
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

    tools.sort(key=lambda item: (_safe_str(item.get("plugin_id")), _safe_str(item.get("name")), _safe_str(item.get("id"))))
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


def _approval_matches_plugin_action(approval_record: dict[str, Any] | None, plugin_id: str, action: str) -> bool:
    if not isinstance(approval_record, dict):
        return False

    approval_action = _safe_str(approval_record.get("action")).strip().lower()
    if approval_action and approval_action != "plugin.run":
        return False

    payload = approval_record.get("payload")
    if not isinstance(payload, dict):
        return False

    approved_plugin = _safe_str(payload.get("plugin_id")).strip()
    approved_action = _safe_str(payload.get("action")).strip()
    if not approved_plugin or not approved_action:
        return False
    if approved_plugin.lower() != plugin_id.lower():
        return False
    if approved_action.lower() != action.lower():
        return False
    return True


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


class PluginToggleIn(BaseModel):
    id: str
    reason: str = "requested"
    meta: dict[str, Any] = Field(default_factory=dict)


class PluginInstallIn(BaseModel):
    source_kind: str
    source_ref: str
    version: str | None = None
    ref: str | None = None
    sha256: str | None = None
    capabilities: list[dict[str, Any]] = Field(default_factory=list)
    reason: str = "requested"
    dry_run: bool = False
    force: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)


class PluginUninstallIn(BaseModel):
    id: str
    reason: str = "requested"
    force: bool = False
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
        if synced:
            _save_registry(registry)
        plugins = registry.get("plugins")
        total = len(plugins) if isinstance(plugins, dict) else 0
        return {"ok": True, "route": "plugins", "status": "ready", "total": total}
    except Exception as exc:
        return {"ok": False, "route": "plugins", "status": "error", "error": str(exc)}


@router.post("/build")
def build(payload: PluginBuildIn) -> dict[str, object]:
    try:
        res = build_plugin(payload.name, payload.description)
        plugin_id = _validate_plugin_id(_safe_str(res.get("plugin_id")).strip())

        registry = _load_registry()
        _ensure_plugin_from_generated(registry, plugin_id)
        _save_registry(registry)

        artifact_zip = _safe_str(res.get("artifact_zip")).strip()
        spec_path = _safe_str(res.get("spec_path")).strip()
        registry_snapshot = _safe_str(res.get("registry_snapshot")).strip()
        return {
            "ok": True,
            "plugin_id": plugin_id,
            "id": plugin_id,
            "status": "enabled",
            "enabled": True,
            "artifact_zip": artifact_zip,
            "spec_path": spec_path,
            "registry_snapshot": registry_snapshot,
            "validation": res.get("validation") if isinstance(res.get("validation"), dict) else {},
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
                "artifact_exists": bool(_safe_str(item.get("artifact_zip")).strip() and Path(_safe_str(item.get("artifact_zip"))).exists()),
                "spec_exists": bool(isinstance(details.get("contract"), dict) and details.get("contract")),
                "registry_snapshot_exists": bool(isinstance(details.get("registry_snapshot"), dict) and details.get("registry_snapshot")),
            }
        else:
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
def enable_plugin(payload: PluginToggleIn) -> dict[str, object]:
    try:
        plugin_id = _validate_plugin_id(payload.id)
        registry = _load_registry()
        _sync_generated_plugins(registry)
        current = _read_plugin(registry, plugin_id)
        if current is None:
            return {"ok": False, "error": "not_found", "id": plugin_id}

        current["enabled"] = True
        current["status"] = "enabled"
        current["updated_ts"] = _now_s()
        _write_plugin(registry, _normalize_plugin_record(plugin_id, current))
        _save_registry(registry)

        return {"ok": True, "id": plugin_id, "enabled": True, "status": "enabled", "message": "enabled"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/disable")
def disable_plugin(payload: PluginToggleIn) -> dict[str, object]:
    try:
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
        _save_registry(registry)

        return {"ok": True, "id": plugin_id, "enabled": False, "status": "disabled", "message": "disabled"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/install")
def install_plugin(payload: PluginInstallIn) -> dict[str, object]:
    try:
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
            return {"ok": True, "status": "installing", "message": "validated"}

        if existing is not None and payload.force:
            plugin_id = _validate_plugin_id(_safe_str(existing.get("id")).strip())
        else:
            seed = _slugify(source_ref.split("/")[-1] if "/" in source_ref else source_ref)
            plugin_id = _validate_plugin_id(f"{int(time.time())}_{seed}")

        now_s = _now_s()
        record = _normalize_plugin_record(
            plugin_id,
            {
                "id": plugin_id,
                "name": _safe_str(source_ref.split("/")[-1] if "/" in source_ref else source_ref).strip() or plugin_id,
                "version": _safe_str(payload.version).strip(),
                "status": "enabled",
                "enabled": True,
                "description": f"Installed from {source_kind}:{source_ref}",
                "source_kind": source_kind,
                "source_ref": source_ref,
                "installed_ts": int(existing.get("installed_ts") if existing else now_s),
                "updated_ts": now_s,
                "tags": ["installed"],
                "capabilities": [item for item in payload.capabilities if isinstance(item, dict)],
                "meta": {
                    **(dict(payload.meta or {}) if isinstance(payload.meta, dict) else {}),
                    "reason": _safe_str(payload.reason).strip(),
                    "ref": _safe_str(payload.ref).strip(),
                    "sha256": _safe_str(payload.sha256).strip(),
                },
            },
        )
        _write_plugin(registry, record)
        _save_registry(registry)
        return {"ok": True, "plugin_id": plugin_id, "id": plugin_id, "status": "enabled", "message": "installed"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/uninstall")
def uninstall_plugin(payload: PluginUninstallIn) -> dict[str, object]:
    try:
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
        _save_registry(registry)
        return {"ok": True, "id": plugin_id, "status": "uninstalled", "message": "uninstalled"}
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
            return {"ok": False, "error": "plugin_disabled", "id": plugin_id, "status": "disabled"}
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
                "meta": {"action": action, "risk_tier": risk_tier},
            }

        force = _to_bool((payload.meta or {}).get("force"), default=False)
        approval_required = _approval_required_for_capability(capability, risk_tier)
        approval_id = _plugin_run_approval_id(payload)
        if approval_required and not force:
            if not approval_id:
                approval = approval_store.request(
                    action="plugin.run",
                    reason=_safe_str(payload.reason).strip() or "requested",
                    payload={
                        "plugin_id": plugin_id,
                        "action": action,
                        "risk_tier": risk_tier,
                        "required_trust": required_trust,
                        "idempotency_key": _safe_str(payload.idempotency_key).strip(),
                        "meta": payload.meta if isinstance(payload.meta, dict) else {},
                    },
                )
                created_id = _safe_str(approval.get("id")).strip()
                return {
                    "ok": True,
                    "id": plugin_id,
                    "status": "pending",
                    "approval_id": created_id,
                    "message": "Plugin action requires approval.",
                    "meta": {"action": action, "risk_tier": risk_tier, "required_trust": required_trust},
                }

            approval_status, approval_record = _approval_status(approval_id)
            if approval_status == "pending":
                return {
                    "ok": True,
                    "id": plugin_id,
                    "status": "pending",
                    "approval_id": approval_id,
                    "message": "Plugin action is awaiting approval.",
                    "meta": {"action": action, "risk_tier": risk_tier, "required_trust": required_trust},
                }
            if approval_status in {"rejected", "emergency"}:
                return {
                    "ok": False,
                    "id": plugin_id,
                    "status": "denied",
                    "error": "approval_denied",
                    "approval_id": approval_id,
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
                    "meta": {"action": action, "risk_tier": risk_tier, "required_trust": required_trust},
                }
            if not _approval_matches_plugin_action(approval_record, plugin_id, action):
                return {
                    "ok": False,
                    "id": plugin_id,
                    "status": "needs_approval",
                    "error": "approval_payload_mismatch",
                    "approval_id": approval_id,
                    "message": "Approval does not match this plugin action.",
                    "meta": {
                        "action": action,
                        "risk_tier": risk_tier,
                        "required_trust": required_trust,
                        "approval_status": approval_status,
                    },
                }

        output = _run_generated_plugin(current, payload.input)
        current["updated_ts"] = _now_s()
        _write_plugin(registry, _normalize_plugin_record(plugin_id, current))
        _save_registry(registry)
        return {
            "ok": True,
            "id": plugin_id,
            "status": "ok",
            "output": output,
            "meta": {"action": action, "risk_tier": risk_tier, "required_trust": required_trust, "current_trust": trust_level},
        }
    except Exception as exc:
        return {"ok": False, "status": "error", "error": str(exc)}


@router.post("/reload")
def reload_plugins() -> dict[str, object]:
    try:
        registry = _load_registry()
        synced = _sync_generated_plugins(registry)
        _save_registry(registry)
        plugins = registry.get("plugins")
        total = len(plugins) if isinstance(plugins, dict) else 0
        return {"ok": True, "message": "reloaded", "synced": synced, "total": total}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
