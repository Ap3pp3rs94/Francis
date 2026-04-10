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
        for plugin in self.items():
            for tool in sorted(plugin.tools, key=lambda item: item.tool_name):
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
        }

    def write_catalog(self, path: Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target
