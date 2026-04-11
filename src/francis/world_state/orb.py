from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import yaml

from francis.kernel.paths import repo_root


_CORE_LOOP_IDS = (
    "P1_INTERFACE",
    "P4_COGNITION",
    "P3_GOVERNANCE",
    "P2_IDENTITY",
    "P7_EXECUTION",
    "P9_OBSERVABILITY",
    "P8_MEMORY",
)

_PREFERRED_GATES = (
    "permission_gate",
    "trust_gate",
    "approvals_gate",
    "audit_log",
    "sandbox_execute",
)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0
        try:
            return int(float(text))
        except Exception:
            return 0
    return 0


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path.as_posix())
    raw = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(raw, dict):
        raise ValueError(f"invalid_yaml_root:{path.as_posix()}")
    return raw


def _string_list(value: Any, *, limit: int | None = None) -> list[str]:
    if not isinstance(value, list):
        return []
    out = [_safe_str(item).strip() for item in value]
    cleaned = [item for item in out if item]
    if limit is None:
        return cleaned
    return cleaned[: max(0, int(limit))]


def _plane_summaries(plane_map: dict[str, Any]) -> list[dict[str, Any]]:
    raw_planes = plane_map.get("planes")
    if not isinstance(raw_planes, list):
        return []

    out: list[dict[str, Any]] = []
    for item in raw_planes:
        if not isinstance(item, dict):
            continue
        plane_id = _safe_str(item.get("id")).strip()
        if not plane_id:
            continue
        out.append(
            {
                "id": plane_id,
                "name": _safe_str(item.get("name")).strip(),
                "category": _safe_str(item.get("category")).strip(),
                "purpose": _safe_str(item.get("purpose")).strip(),
                "side_effects_allowed": bool(item.get("side_effects_allowed")),
                "default_risk_class": _safe_str(item.get("default_risk_class")).strip(),
                "primary_modules": _string_list(item.get("primary_modules"), limit=4),
            }
        )
    return out


def _transition_summaries(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        from_plane = _safe_str(item.get("from")).strip()
        to_plane = _safe_str(item.get("to")).strip()
        if not from_plane or not to_plane:
            continue
        out.append(
            {
                "from": from_plane,
                "to": to_plane,
                "conditions": _string_list(item.get("conditions"), limit=5),
                "reason": _safe_str(item.get("reason")).strip(),
            }
        )
    return out


def _gate_summaries(action_taxonomy: dict[str, Any]) -> list[dict[str, Any]]:
    raw_controls = action_taxonomy.get("controls")
    if not isinstance(raw_controls, list):
        return []

    by_id: dict[str, dict[str, Any]] = {}
    for item in raw_controls:
        if not isinstance(item, dict):
            continue
        control_id = _safe_str(item.get("id")).strip()
        if not control_id:
            continue
        by_id[control_id] = {
            "id": control_id,
            "description": _safe_str(item.get("description")).strip(),
        }

    ordered = [by_id[gate_id] for gate_id in _PREFERRED_GATES if gate_id in by_id]
    for control_id, summary in by_id.items():
        if control_id in _PREFERRED_GATES:
            continue
        ordered.append(summary)
    return ordered


def snapshot() -> dict[str, Any]:
    root = repo_root()
    plane_map_path = root / "meta" / "plane_map.yaml"
    action_taxonomy_path = root / "meta" / "action_taxonomy.yaml"

    plane_map = _read_yaml(plane_map_path)
    action_taxonomy = _read_yaml(action_taxonomy_path)

    planes = _plane_summaries(plane_map)
    plane_by_id = {item["id"]: item for item in planes if item.get("id")}

    return {
        "ok": True,
        "subsystem": "orb_status",
        "generated_at": time.time(),
        "repo_root": str(root),
        "model": {
            "plane_map_id": _safe_str(plane_map.get("meta", {}).get("model_id") if isinstance(plane_map.get("meta"), dict) else ""),
            "plane_map_version": _safe_int(plane_map.get("meta", {}).get("version")) if isinstance(plane_map.get("meta"), dict) else 0,
            "action_taxonomy_id": _safe_str(action_taxonomy.get("meta", {}).get("taxonomy_id") if isinstance(action_taxonomy.get("meta"), dict) else ""),
            "action_taxonomy_version": _safe_int(action_taxonomy.get("meta", {}).get("version")) if isinstance(action_taxonomy.get("meta"), dict) else 0,
        },
        "core_loop": [plane_by_id[plane_id] for plane_id in _CORE_LOOP_IDS if plane_id in plane_by_id],
        "planes": planes,
        "gates": _gate_summaries(action_taxonomy),
        "transitions": {
            "allowed": _transition_summaries(plane_map.get("transitions")),
            "forbidden": _transition_summaries(plane_map.get("forbidden_transitions")),
        },
    }
