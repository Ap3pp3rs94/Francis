from __future__ import annotations

from typing import Any

from .contracts import SkillSpec

VALID_PRIMITIVE_TYPES = {"str", "int", "float", "bool", "dict", "list"}


def _normalize_type_decl(type_decl: str) -> tuple[str, bool]:
    normalized = type_decl.strip().lower()
    optional = False
    if normalized.startswith("optional:"):
        optional = True
        normalized = normalized.removeprefix("optional:")
    return normalized, optional


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "str":
        return isinstance(value, str)
    if expected == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "bool":
        return isinstance(value, bool)
    if expected == "dict":
        return isinstance(value, dict)
    if expected == "list":
        return isinstance(value, list)
    return False


def validate_args(spec: SkillSpec, args: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(args, dict):
        return (False, "args must be an object")

    for arg_name, decl in spec.args_schema.items():
        expected, optional = _normalize_type_decl(decl)
        if expected not in VALID_PRIMITIVE_TYPES:
            return (False, f"invalid schema type for {arg_name}: {decl}")
        if arg_name not in args:
            if optional:
                continue
            return (False, f"missing required argument: {arg_name}")
        if not _matches_type(args[arg_name], expected):
            return (False, f"argument {arg_name} must be {expected}")

    return (True, "")
