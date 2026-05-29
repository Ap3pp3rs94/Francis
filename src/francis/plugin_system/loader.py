from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

__all__ = ["ToolSpec", "PluginSpec", "PluginLoader"]

_VALID_SPEC_SUFFIXES = {".json", ".yaml", ".yml"}
_RISK_DEFAULT = "normal"
_EXECUTE_ACTIONS = {
    "create",
    "delete",
    "deploy",
    "execute",
    "restart",
    "run",
    "stop",
    "trigger",
    "update",
    "write",
}


def _real_path(value: str | Path) -> Path:
    return Path(os.path.realpath(os.fspath(value)))


def _is_under(root: Path, candidate: Path) -> bool:
    try:
        root_text = os.path.normcase(os.path.realpath(os.fspath(root)))
        candidate_text = os.path.normcase(os.path.realpath(os.fspath(candidate)))
        return os.path.commonpath([root_text, candidate_text]) == root_text
    except (OSError, ValueError):
        return False


def _slugify(value: str, *, separator: str = "_") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", separator, str(value).strip().lower())
    return cleaned.strip(separator) or "plugin"


def _to_str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if isinstance(value, (list, tuple, set)):
        parts: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                parts.append(text)
        return tuple(parts)
    text = str(value).strip()
    return (text,) if text else ()


def _to_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _infer_methods(action: str, declared: Any) -> tuple[str, ...]:
    methods = _to_str_tuple(declared)
    if methods:
        return tuple(method.lower() for method in methods)
    action_name = str(action).strip().lower()
    if action_name in {"get", "inspect", "list", "query", "read", "scan", "status"}:
        return ("read",)
    if action_name in _EXECUTE_ACTIONS:
        return ("execute",)
    return ("execute",)


@dataclass(frozen=True)
class ToolSpec:
    tool_name: str
    action: str
    summary: str
    description: str
    methods: tuple[str, ...] = ()
    resources: tuple[str, ...] = ()
    policy_tags: tuple[str, ...] = ()
    requires_approvals: bool = False
    requires_trust_level: int = 0
    rate_limits: dict[str, Any] = field(default_factory=dict)
    idempotency: bool = False
    dry_run_supported: bool = False
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    risk_class: str = _RISK_DEFAULT
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "action": self.action,
            "summary": self.summary,
            "description": self.description,
            "methods": list(self.methods),
            "resources": list(self.resources),
            "policy_tags": list(self.policy_tags),
            "requires_approvals": self.requires_approvals,
            "requires_trust_level": self.requires_trust_level,
            "rate_limits": self.rate_limits,
            "idempotency": self.idempotency,
            "dry_run_supported": self.dry_run_supported,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "risk_class": self.risk_class,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class PluginSpec:
    plugin_id: str
    name: str
    version: str
    description: str
    origin: str
    entrypoint: str
    tools: tuple[ToolSpec, ...] = ()
    capabilities: tuple[str, ...] = ()
    risk_class: str = _RISK_DEFAULT
    permissions: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    sandbox_profile: str = "default"
    telemetry: dict[str, Any] = field(default_factory=dict)
    compatibility: dict[str, Any] = field(default_factory=dict)
    attestation: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_path: str | None = None

    @property
    def id(self) -> str:
        return self.plugin_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "origin": self.origin,
            "entrypoint": self.entrypoint,
            "tools": [tool.to_dict() for tool in self.tools],
            "capabilities": list(self.capabilities),
            "risk_class": self.risk_class,
            "permissions": self.permissions,
            "constraints": self.constraints,
            "sandbox_profile": self.sandbox_profile,
            "telemetry": self.telemetry,
            "compatibility": self.compatibility,
            "attestation": self.attestation,
            "metadata": self.metadata,
            "source_path": self.source_path,
        }


class PluginLoader:
    def __init__(self, *, spec_dir: Path | None = None) -> None:
        self.spec_dir = _real_path(spec_dir) if spec_dir is not None else None

    def load(self, path: Path) -> PluginSpec | None:
        if not isinstance(path, Path):
            logger.warning("load expected Path")
            return None
        resolved_path = self._resolve_spec_path(path)
        if resolved_path is None:
            return None
        if not resolved_path.exists() or not resolved_path.is_file():
            logger.warning("plugin spec not found: %s", resolved_path)
            return None
        if resolved_path.suffix.lower() not in _VALID_SPEC_SUFFIXES:
            logger.warning("unsupported plugin spec suffix: %s", resolved_path.suffix)
            return None
        try:
            payload = self._parse_payload(resolved_path)
            if not isinstance(payload, dict):
                logger.warning("plugin spec must be a mapping: %s", resolved_path)
                return None
            return self._normalize_spec(payload, source_path=resolved_path)
        except Exception as exc:
            logger.error("Failed to load plugin spec %s: %s", resolved_path, exc)
            return None

    def load_directory(self, directory: Path | None = None) -> list[PluginSpec]:
        target = self._resolve_directory(directory)
        if target is None:
            return []
        if not target.exists():
            return []
        specs: list[PluginSpec] = []
        for path in sorted(target.rglob("*")):
            if path.is_file() and path.suffix.lower() in _VALID_SPEC_SUFFIXES:
                spec = self.load(path)
                if spec is not None:
                    specs.append(spec)
        return specs

    def _resolve_spec_path(self, path: Path) -> Path | None:
        if self.spec_dir is None:
            logger.warning("trusted plugin spec_dir is required")
            return None
        candidate = path if path.is_absolute() else self.spec_dir / path
        try:
            resolved = _real_path(candidate)
        except OSError:
            return None
        if not _is_under(self.spec_dir, resolved):
            logger.warning("plugin spec outside trusted root rejected: %s", path)
            return None
        return resolved

    def _resolve_directory(self, directory: Path | None) -> Path | None:
        if self.spec_dir is None:
            logger.warning("trusted plugin spec_dir is required")
            return None
        target = directory or self.spec_dir
        if not isinstance(target, Path):
            target = Path(target)
        candidate = target if target.is_absolute() else self.spec_dir / target
        try:
            resolved = _real_path(candidate)
        except OSError:
            return None
        if not _is_under(self.spec_dir, resolved):
            logger.warning("plugin spec directory outside trusted root rejected: %s", target)
            return None
        return resolved

    def _parse_payload(self, path: Path) -> dict[str, Any]:
        raw = path.read_text(encoding="utf-8")
        suffix = path.suffix.lower()
        if suffix == ".json":
            return json.loads(raw)
        if suffix in {".yaml", ".yml"}:
            payload = yaml.safe_load(raw)
            return payload if isinstance(payload, dict) else {}
        raise ValueError(f"unsupported suffix: {suffix}")

    def _normalize_spec(self, payload: dict[str, Any], *, source_path: Path) -> PluginSpec:
        plugin_id = str(
            payload.get("plugin_id") or payload.get("id") or payload.get("name") or source_path.stem
        ).strip()
        plugin_id = plugin_id or _slugify(source_path.stem, separator=".")

        name = str(payload.get("name") or plugin_id).strip() or plugin_id
        version = str(payload.get("version") or "0.1.0").strip() or "0.1.0"
        description = str(payload.get("description") or "").strip()
        origin = str(payload.get("origin") or payload.get("source_kind") or self._infer_origin(source_path)).strip()
        entrypoint = str(
            payload.get("entrypoint")
            or payload.get("module")
            or _to_dict(payload.get("implementation")).get("entrypoint")
            or ""
        ).strip()
        risk_class = str(payload.get("risk_class") or payload.get("risk_tier") or _RISK_DEFAULT).strip().lower()
        metadata = _to_dict(payload.get("metadata") or payload.get("meta"))
        permissions = _to_dict(payload.get("permissions"))
        constraints = _to_dict(payload.get("constraints"))
        telemetry = _to_dict(payload.get("telemetry"))
        compatibility = _to_dict(payload.get("compatibility"))
        attestation = _to_dict(payload.get("attestation") or payload.get("signing"))
        sandbox_profile = str(payload.get("sandbox_profile") or metadata.get("sandbox_profile") or "default").strip()

        capabilities = self._normalize_capabilities(payload.get("capabilities"))
        tools = self._normalize_tools(
            plugin_id=plugin_id,
            plugin_name=name,
            entrypoint=entrypoint,
            risk_class=risk_class,
            raw_tools=payload.get("tools"),
            raw_capabilities=payload.get("capabilities"),
        )

        return PluginSpec(
            plugin_id=plugin_id,
            name=name,
            version=version,
            description=description,
            origin=origin or "unknown",
            entrypoint=entrypoint,
            tools=tools,
            capabilities=capabilities,
            risk_class=risk_class or _RISK_DEFAULT,
            permissions=permissions,
            constraints=constraints,
            sandbox_profile=sandbox_profile or "default",
            telemetry=telemetry,
            compatibility=compatibility,
            attestation=attestation,
            metadata=metadata,
            source_path=str(source_path),
        )

    def _normalize_capabilities(self, raw_capabilities: Any) -> tuple[str, ...]:
        if isinstance(raw_capabilities, list):
            normalized: list[str] = []
            for item in raw_capabilities:
                if isinstance(item, dict):
                    name = str(item.get("name") or item.get("id") or item.get("action") or "").strip()
                else:
                    name = str(item).strip()
                if name:
                    normalized.append(name)
            return tuple(normalized)
        return _to_str_tuple(raw_capabilities)

    def _normalize_tools(
        self,
        *,
        plugin_id: str,
        plugin_name: str,
        entrypoint: str,
        risk_class: str,
        raw_tools: Any,
        raw_capabilities: Any,
    ) -> tuple[ToolSpec, ...]:
        candidates: list[dict[str, Any]] = []
        if isinstance(raw_tools, list):
            candidates.extend(item for item in raw_tools if isinstance(item, dict))
        elif isinstance(raw_capabilities, list):
            candidates.extend(
                item
                for item in raw_capabilities
                if isinstance(item, dict) and (item.get("kind") == "tool" or item.get("action"))
            )

        if not candidates and entrypoint:
            candidates.append(
                {
                    "tool_name": "run",
                    "action": "run",
                    "summary": f"Run {plugin_name}",
                    "description": f"Execute the primary action for {plugin_name}.",
                    "input_schema": {"type": "object", "additionalProperties": True},
                    "output_schema": {"type": "object", "additionalProperties": True},
                    "methods": ["execute"],
                    "dry_run_supported": False,
                }
            )

        tools: list[ToolSpec] = []
        for idx, candidate in enumerate(candidates):
            tools.append(
                self._normalize_tool(plugin_id=plugin_id, default_risk=risk_class, payload=candidate, index=idx)
            )
        return tuple(tools)

    def _normalize_tool(
        self,
        *,
        plugin_id: str,
        default_risk: str,
        payload: dict[str, Any],
        index: int,
    ) -> ToolSpec:
        meta = _to_dict(payload.get("meta") or payload.get("metadata"))
        action = str(
            payload.get("action") or payload.get("tool_name") or payload.get("name") or f"action_{index}"
        ).strip()
        raw_tool_name = str(payload.get("tool_name") or payload.get("name") or action).strip() or f"action_{index}"
        tool_name = (
            raw_tool_name if "." in raw_tool_name else f"{_slugify(plugin_id, separator='.')}.{_slugify(raw_tool_name)}"
        )
        summary = str(payload.get("summary") or payload.get("description") or raw_tool_name).strip() or raw_tool_name
        description = str(payload.get("description") or summary).strip() or summary
        tool_risk = str(
            payload.get("risk_class") or payload.get("risk_tier") or meta.get("risk_tier") or default_risk
        ).strip()
        requires_approvals = bool(
            payload.get("requires_approvals")
            if "requires_approvals" in payload
            else payload.get("approvals_required", tool_risk in {"critical", "safety_critical"})
        )
        requires_trust_level = int(
            payload.get("requires_trust_level") or payload.get("required_trust") or meta.get("required_trust") or 0
        )
        input_schema = _to_dict(payload.get("input_schema")) or {"type": "object", "additionalProperties": True}
        output_schema = _to_dict(payload.get("output_schema")) or {"type": "object", "additionalProperties": True}
        resources = _to_str_tuple(payload.get("resources"))
        policy_tags = _to_str_tuple(payload.get("policy_tags") or meta.get("policy_tags"))
        rate_limits = _to_dict(payload.get("rate_limits"))
        methods = _infer_methods(action, payload.get("methods"))

        return ToolSpec(
            tool_name=tool_name,
            action=action,
            summary=summary,
            description=description,
            methods=methods,
            resources=resources,
            policy_tags=policy_tags,
            requires_approvals=requires_approvals,
            requires_trust_level=requires_trust_level,
            rate_limits=rate_limits,
            idempotency=bool(payload.get("idempotency", False)),
            dry_run_supported=bool(payload.get("dry_run_supported", tool_risk in {"critical", "safety_critical"})),
            input_schema=input_schema,
            output_schema=output_schema,
            risk_class=tool_risk.lower() or _RISK_DEFAULT,
            metadata=meta,
        )

    def _infer_origin(self, source_path: Path) -> str:
        parts = {part.lower() for part in source_path.parts}
        for candidate in ("builtins", "generated", "packs", "third_party"):
            if candidate in parts:
                return candidate.rstrip("s")
        return "unknown"
