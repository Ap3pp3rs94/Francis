from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .loader import PluginSpec, ToolSpec

logger = logging.getLogger(__name__)

__all__ = ["ValidationResult", "PluginValidator"]

_ALLOWED_RISK_CLASSES = {"readonly", "normal", "critical", "safety_critical"}
_ALLOWED_METHODS = {"read", "write", "delete", "execute"}


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    reason: str
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "reason": self.reason,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


class PluginValidator:
    def validate(self, spec: PluginSpec) -> ValidationResult:
        if not isinstance(spec, PluginSpec):
            logger.warning("validate expected PluginSpec")
            return ValidationResult(valid=False, reason="invalid_spec", errors=("invalid_spec",))

        errors: list[str] = []
        warnings: list[str] = []

        if not spec.plugin_id.strip():
            errors.append("missing_plugin_id")
        if not spec.name.strip():
            errors.append("missing_name")
        if not spec.version.strip():
            errors.append("missing_version")
        if spec.risk_class not in _ALLOWED_RISK_CLASSES:
            errors.append(f"invalid_risk_class:{spec.risk_class}")
        if not spec.tools:
            errors.append("missing_tools")

        seen_tool_names: set[str] = set()
        for tool in spec.tools:
            self._validate_tool(tool, errors=errors, warnings=warnings, seen_tool_names=seen_tool_names)

        if errors:
            return ValidationResult(valid=False, reason=errors[0], errors=tuple(errors), warnings=tuple(warnings))
        return ValidationResult(valid=True, reason="ok", errors=(), warnings=tuple(warnings))

    def _validate_tool(
        self,
        tool: ToolSpec,
        *,
        errors: list[str],
        warnings: list[str],
        seen_tool_names: set[str],
    ) -> None:
        if not tool.tool_name.strip():
            errors.append("missing_tool_name")
            return
        if "." not in tool.tool_name:
            errors.append(f"tool_not_namespaced:{tool.tool_name}")
        if tool.tool_name in seen_tool_names:
            errors.append(f"duplicate_tool_name:{tool.tool_name}")
        seen_tool_names.add(tool.tool_name)

        if not tool.action.strip():
            errors.append(f"missing_action:{tool.tool_name}")
        if tool.risk_class not in _ALLOWED_RISK_CLASSES:
            errors.append(f"invalid_tool_risk_class:{tool.tool_name}:{tool.risk_class}")
        if not tool.input_schema:
            errors.append(f"missing_input_schema:{tool.tool_name}")
        if not tool.output_schema:
            warnings.append(f"missing_output_schema:{tool.tool_name}")

        for method in tool.methods:
            if method not in _ALLOWED_METHODS:
                errors.append(f"invalid_method:{tool.tool_name}:{method}")

        if tool.requires_trust_level < 0:
            errors.append(f"negative_trust_level:{tool.tool_name}")

        if tool.risk_class in {"critical", "safety_critical"}:
            if not tool.requires_approvals:
                errors.append(f"approval_required:{tool.tool_name}")
            if not tool.policy_tags:
                errors.append(f"policy_tags_required:{tool.tool_name}")
            if tool.requires_trust_level <= 0:
                warnings.append(f"trust_level_recommended:{tool.tool_name}")
            if not tool.dry_run_supported:
                warnings.append(f"dry_run_recommended:{tool.tool_name}")

        if tool.risk_class == "safety_critical" and "safety_critical" not in set(tool.policy_tags):
            errors.append(f"safety_tag_required:{tool.tool_name}")
