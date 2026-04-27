from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .loader import PluginLoader, PluginSpec, ToolSpec
from .validator import PluginValidator, ValidationResult

logger = logging.getLogger(__name__)

__all__ = ["PluginRegistry"]


class PluginRegistry:
    def __init__(self, *, validator: PluginValidator | None = None) -> None:
        self._plugins: dict[str, PluginSpec] = {}
        self._name_index: dict[str, str] = {}
        self.validator = validator or PluginValidator()

    def register(self, spec: PluginSpec) -> ValidationResult:
        result = self.validator.validate(spec)
        if not result.valid:
            logger.warning("plugin registration rejected for %s: %s", getattr(spec, "plugin_id", "?"), result.reason)
            return result
        self._plugins[spec.plugin_id] = spec
        self._name_index[spec.name.lower()] = spec.plugin_id
        return result

    def bulk_register(self, specs: list[PluginSpec]) -> dict[str, Any]:
        loaded = 0
        rejected: list[dict[str, Any]] = []
        for spec in specs:
            result = self.register(spec)
            if result.valid:
                loaded += 1
            else:
                rejected.append({"plugin_id": spec.plugin_id, "reason": result.reason, "errors": list(result.errors)})
        return {"loaded": loaded, "rejected": rejected, "total": len(specs)}

    def load_from_directory(self, loader: PluginLoader, directory: Path) -> dict[str, Any]:
        specs = loader.load_directory(directory)
        return self.bulk_register(specs)

    def get(self, name: str) -> PluginSpec | None:
        if not isinstance(name, str) or not name.strip():
            return None
        key = name.strip()
        if key in self._plugins:
            return self._plugins[key]
        plugin_id = self._name_index.get(key.lower())
        return self._plugins.get(plugin_id) if plugin_id else None

    def list(self) -> list[str]:
        return sorted(self._plugins.keys())

    def items(self) -> list[PluginSpec]:
        return [self._plugins[plugin_id] for plugin_id in self.list()]

    def find_tool(self, tool_name: str) -> tuple[PluginSpec, ToolSpec] | None:
        target = str(tool_name).strip()
        if not target:
            return None
        for plugin in self.items():
            for tool in plugin.tools:
                if tool.tool_name == target:
                    return plugin, tool
        return None

    def to_dict(self) -> dict[str, Any]:
        plugins = [plugin.to_dict() for plugin in self.items()]
        tool_index: list[dict[str, Any]] = []
        risk_class_counts: dict[str, int] = {}
        lifecycle_status_counts: dict[str, int] = {}
        tool_risk_class_counts: dict[str, int] = {}
        approval_required_tool_count = 0
        forge_lineage_index: list[dict[str, Any]] = []

        def _normalized_label(value: Any, *, fallback: str = "unknown") -> str:
            text = str(value or "").strip().lower()
            return text or fallback

        def _metadata_text(metadata: dict[str, Any], key: str) -> str | None:
            value = metadata.get(key)
            if value is None:
                return None
            text = str(value).strip()
            return text or None

        def _increment(bucket: dict[str, int], value: Any) -> None:
            label = _normalized_label(value)
            bucket[label] = bucket.get(label, 0) + 1

        for plugin in self.items():
            _increment(risk_class_counts, plugin.risk_class)
            lifecycle_status = plugin.metadata.get("promotion_status") or plugin.metadata.get("status")
            _increment(lifecycle_status_counts, lifecycle_status)

            lineage = {
                "promotion_status": _metadata_text(plugin.metadata, "promotion_status"),
                "proposal_id": _metadata_text(plugin.metadata, "proposal_id"),
                "proposal_path": _metadata_text(plugin.metadata, "proposal_path"),
                "promotion_receipt_id": _metadata_text(plugin.metadata, "promotion_receipt_id"),
                "promotion_receipt_path": _metadata_text(plugin.metadata, "promotion_receipt_path"),
            }
            if any(lineage.values()):
                forge_lineage_index.append(
                    {
                        "plugin_id": plugin.plugin_id,
                        "plugin_name": plugin.name,
                        **{key: value for key, value in lineage.items() if value is not None},
                    }
                )

            for tool in sorted(plugin.tools, key=lambda item: item.tool_name):
                _increment(tool_risk_class_counts, tool.risk_class)
                if tool.requires_approvals:
                    approval_required_tool_count += 1
                tool_index.append(
                    {
                        "plugin_id": plugin.plugin_id,
                        "plugin_name": plugin.name,
                        "tool_name": tool.tool_name,
                        "action": tool.action,
                        "risk_class": tool.risk_class,
                        "requires_approvals": tool.requires_approvals,
                        "requires_trust_level": tool.requires_trust_level,
                        "policy_tags": list(tool.policy_tags),
                    }
                )
        return {
            "version": 1,
            "plugins": plugins,
            "tool_index": tool_index,
            "total_plugins": len(plugins),
            "total_tools": len(tool_index),
            "risk_class_counts": dict(sorted(risk_class_counts.items())),
            "lifecycle_status_counts": dict(sorted(lifecycle_status_counts.items())),
            "tool_risk_class_counts": dict(sorted(tool_risk_class_counts.items())),
            "approval_required_tool_count": approval_required_tool_count,
            "forge_lineage_index": forge_lineage_index,
        }

    def write_catalog(self, path: Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target
