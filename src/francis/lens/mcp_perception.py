"""Lens <-> MCP perception bridge (read-only).

This is the first conduit from the Lens/Orb body to the MCP nervous system. It is
deliberately a SMALL, read-only rung toward embodiment:

- It lets the Lens surface *perceive* through MCP read-only tools (the senses):
  health, repo/git readback, screen/session readback, takeover/input status, and
  receipt readback.
- It is NOT a residency claim, NOT supervision, and grants NO execution authority.
  Every payload says so explicitly (``resident: False``).
- It refuses any mutating / approval-gated MCP tool AT THE BRIDGE. It never offers a
  second path around a gate: mutating tools must go through their own MCP approval
  surface, not through perception. The allowlist is derived structurally from the
  MCP tool registry (``read_only and not requires_approval``), so it cannot drift
  open silently.
- Every perception (and every refusal) writes a receipt with provenance, so a live
  caller leaves auditable evidence that the body reached the nervous system.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_governed_display_value
from francis.kernel.paths import data_dir
from francis.mcp_gateway.tools import list_tools as _mcp_list_tools
from francis.mcp_gateway.tools import run_tool as _mcp_run_tool

LENS_MCP_PERCEPTION_SURFACE = "lens.mcp.perception"
LENS_MCP_PERCEIVE_ROUTE = "/lens/mcp/perceive"
LENS_MCP_OBSERVE_ROUTE = "/lens/mcp/observe"
LENS_MCP_CONTRACT_ROUTE = "/lens/mcp/contract"
LENS_MCP_RECEIPTS_ROUTE = "/lens/mcp/receipts"
LENS_OVERLAY_OBSERVATION_SURFACE = "lens.overlay.observation"

_OVERLAY_OBSERVATION_TOOLS = {"francis.screen.session", "francis.screen.status"}


def _now_s() -> int:
    return int(time.time())


def _safe_str(value: Any, default: str = "") -> str:
    return str(value if value is not None else default).strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _receipt_root() -> Path:
    return data_dir() / "lens" / "mcp_perception"


def _overlay_runtime_state_path() -> Path:
    return data_dir() / "runtime" / "lens-overlay" / "status.json"


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _display(record: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_governed_display_value(record)
    return redacted if isinstance(redacted, dict) else {}


def _perceivable_tools() -> list[dict[str, Any]]:
    """Read-only, non-approval MCP tools the body may perceive through.

    Derived structurally from the MCP registry so the perception surface tracks the
    nervous system and never silently widens to a mutating tool.
    """

    return [
        tool for tool in _mcp_list_tools() if bool(tool.get("read_only")) and not bool(tool.get("requires_approval"))
    ]


def _perceivable_tool_names() -> set[str]:
    return {_safe_str(tool.get("name")) for tool in _perceivable_tools()}


def _honesty() -> dict[str, Any]:
    return {
        "bridge": "lens_mcp_perception_v0",
        "read_only": True,
        "resident": False,
        "supervision": False,
        "mutates_repo": False,
        "raw_shell": False,
        "raw_input": False,
        "screenshots": False,
        "pixels": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "approval_path": "mutating_tools_use_their_own_mcp_approval_surface_not_perception",
    }


def _observation_honesty() -> dict[str, Any]:
    return {
        **_honesty(),
        "surface": LENS_OVERLAY_OBSERVATION_SURFACE,
        "uses_existing_overlay": True,
        "creates_overlay": False,
        "creates_lens_app": False,
        "requires_overlay_coordinate_model": True,
        "observation_sources": sorted(_OVERLAY_OBSERVATION_TOOLS),
        "ocr": False,
        "accessibility_tree": False,
        "visual_similarity": False,
    }


def lens_mcp_perception_contract() -> dict[str, Any]:
    """Read-only contract: which MCP tools the Lens body may perceive through."""

    perceivable = _perceivable_tools()
    return {
        "kind": "francis.lens.mcp.perception.contract",
        "ok": True,
        "status": "ready",
        "surface": LENS_MCP_PERCEPTION_SURFACE,
        "perceivable_tools": [
            {"name": _safe_str(t.get("name")), "description": _safe_str(t.get("description"))} for t in perceivable
        ],
        "perceivable_tool_count": len(perceivable),
        "overlay_observation": {
            "route": LENS_MCP_OBSERVE_ROUTE,
            "surface": LENS_OVERLAY_OBSERVATION_SURFACE,
            "requires_overlay_coordinate_model": True,
            "uses_existing_overlay": True,
            "creates_overlay": False,
            "creates_lens_app": False,
            "observation_sources": sorted(_OVERLAY_OBSERVATION_TOOLS),
            "screenshots": False,
            "pixels": False,
            "ocr": False,
            "accessibility_tree": False,
            "visual_similarity": False,
            "limitations": [
                "metadata_only_screen_session_readback",
                "screenshot_capture_unsupported",
                "pixel_capture_unsupported",
                "ocr_unsupported",
                "accessibility_tree_unsupported",
                "visual_similarity_unsupported",
            ],
        },
        "refused_tool_note": (
            "mutating or approval-gated MCP tools are refused at the bridge; use the tool's own MCP approval surface"
        ),
        "governance": _honesty(),
    }


def _receipt_optional_fields(payload: dict[str, Any]) -> dict[str, Any]:
    optional: dict[str, Any] = {}
    for key in (
        "correlation_id",
        "parent_receipt_id",
        "session_id",
        "mission_id",
        "requested_region",
        "mapped_overlay_region",
        "actual_inspected_region",
        "actual_observed_region",
        "actual_captured_region",
        "observation_source",
        "observation_status",
        "observation_mode",
        "structured_observation_receipt",
        "evidence_reference",
        "confidence",
        "unknown_information",
        "limitations",
        "failure_or_refusal_reason",
    ):
        if key in payload:
            optional[key] = payload[key]
    return optional


def _record_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    ts = _now_s()
    actor = _safe_str(payload.get("actor"), "unknown")
    tool = _safe_str(payload.get("tool"))
    decision = _safe_str(payload.get("decision"))
    digest_src = json.dumps(payload, sort_keys=True, default=str).encode("utf-8", errors="ignore")
    digest = hashlib.sha256(digest_src).hexdigest()[:16]
    receipt_id = f"lens-mcp-{decision}-{digest}"
    receipt = {
        "kind": "francis.lens.mcp.perception.receipt",
        "receipt_id": receipt_id,
        "id": receipt_id,
        "created_ts": ts,
        "surface": LENS_MCP_PERCEPTION_SURFACE,
        "actor": actor,
        "tool": tool,
        "decision": decision,
        "mcp_status": _safe_str(payload.get("mcp_status")),
        "mcp_authority": _safe_str(payload.get("mcp_authority")),
        "reason": _safe_str(payload.get("reason")),
        **_receipt_optional_fields(payload),
        "governance": _honesty(),
    }
    path = _receipt_root() / f"{receipt_id}.json"
    display = _display(receipt)
    _atomic_write_json(path, display)
    display["receipt_path"] = str(path)
    return display


def _region_payload(value: dict[str, Any] | None) -> dict[str, Any]:
    raw = _as_dict(value)
    x = _safe_float(raw.get("x"))
    y = _safe_float(raw.get("y"))
    width = _safe_float(raw.get("width"))
    height = _safe_float(raw.get("height"))
    numeric = x is not None and y is not None and width is not None and height is not None
    return {
        "space": _safe_str(raw.get("space"), "desktop") or "desktop",
        "label": _safe_str(raw.get("label")),
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "numeric_bounds": numeric,
        "status": "bounded" if numeric else "unbounded",
    }


def _bounds_from(value: dict[str, Any]) -> dict[str, Any]:
    for key in ("bounds", "overlay_bounds", "window_bounds", "viewport", "viewport_bounds", "screen_bounds"):
        bounds = _as_dict(value.get(key))
        if bounds:
            return bounds
    return {}


def _overlay_runtime_context(provided_context: dict[str, Any] | None) -> dict[str, Any]:
    runtime_path = _overlay_runtime_state_path()
    runtime = _read_json_object(runtime_path)
    provided = _as_dict(provided_context)
    runtime_present = bool(runtime)
    runtime_valid = (
        runtime.get("kind") == "lens.overlay.runtime_state"
        and _safe_str(runtime.get("overlay_name")) == "Francis Lens Overlay"
        and _safe_str(runtime.get("overlay_scope")) == "user_session"
    )
    runtime_visible = bool(runtime.get("overlay_window_visible"))
    provided_bounds = _bounds_from(provided)
    runtime_bounds = _bounds_from(runtime)
    bounds = provided_bounds or runtime_bounds
    coordinate_space = (
        _safe_str(provided.get("coordinate_space"))
        or _safe_str(runtime.get("coordinate_space"))
        or "desktop_logical_pixels"
    )
    source_parts = []
    if provided:
        source_parts.append("caller_supplied_overlay_context")
    if runtime_present:
        source_parts.append("existing_overlay_runtime_state")

    return {
        "available": bool(provided or runtime_valid),
        "source": "+".join(source_parts) if source_parts else "missing",
        "runtime_state_path": str(runtime_path),
        "runtime_state_present": runtime_present,
        "runtime_state_valid": runtime_valid,
        "overlay_name": _safe_str(runtime.get("overlay_name") or provided.get("overlay_name")),
        "overlay_scope": _safe_str(runtime.get("overlay_scope") or provided.get("overlay_scope")),
        "overlay_window_visible": runtime_visible,
        "always_on_top": bool(runtime.get("always_on_top")),
        "coordinate_model": {
            "status": "available" if bounds else "missing_bounds",
            "coordinate_space": coordinate_space,
            "bounds": bounds,
            "bounds_source": "caller_supplied_overlay_context"
            if provided_bounds
            else "existing_overlay_runtime_state"
            if runtime_bounds
            else "missing",
            "transform": "identity_desktop_logical" if bounds else "unavailable",
        },
        "limitations": [] if bounds else ["overlay_bounds_unavailable"],
    }


def _contains(bounds: dict[str, Any], region: dict[str, Any]) -> bool:
    bx = _safe_float(bounds.get("x")) or 0.0
    by = _safe_float(bounds.get("y")) or 0.0
    bw = _safe_float(bounds.get("width"))
    bh = _safe_float(bounds.get("height"))
    rx = _safe_float(region.get("x"))
    ry = _safe_float(region.get("y"))
    rw = _safe_float(region.get("width"))
    rh = _safe_float(region.get("height"))
    if bw is None or bh is None or rx is None or ry is None or rw is None or rh is None:
        return False
    return rx >= bx and ry >= by and (rx + rw) <= (bx + bw) and (ry + rh) <= (by + bh)


def _region_edges(region: dict[str, Any]) -> dict[str, float]:
    x = _safe_float(region.get("x"))
    y = _safe_float(region.get("y"))
    width = _safe_float(region.get("width"))
    height = _safe_float(region.get("height"))
    if x is None or y is None or width is None or height is None:
        return {}
    return {"left": x, "top": y, "right": x + width, "bottom": y + height}


def _outside_edges(bounds: dict[str, Any], region: dict[str, Any]) -> list[str]:
    bound_edges = _region_edges(bounds)
    region_edges = _region_edges(region)
    if not bound_edges or not region_edges:
        return []
    outside = []
    if region_edges["left"] < bound_edges["left"]:
        outside.append("left")
    if region_edges["top"] < bound_edges["top"]:
        outside.append("top")
    if region_edges["right"] > bound_edges["right"]:
        outside.append("right")
    if region_edges["bottom"] > bound_edges["bottom"]:
        outside.append("bottom")
    return outside


def _intersection_region(
    *,
    bounds: dict[str, Any],
    region: dict[str, Any],
    coordinate_space: str,
) -> dict[str, Any]:
    bound_edges = _region_edges(bounds)
    region_edges = _region_edges(region)
    if not bound_edges or not region_edges:
        return {}
    left = max(bound_edges["left"], region_edges["left"])
    top = max(bound_edges["top"], region_edges["top"])
    right = min(bound_edges["right"], region_edges["right"])
    bottom = min(bound_edges["bottom"], region_edges["bottom"])
    if right <= left or bottom <= top:
        return {}
    return {
        "space": coordinate_space,
        "x": left,
        "y": top,
        "width": right - left,
        "height": bottom - top,
    }


def _overlay_origin(bounds: dict[str, Any], coordinate_space: str) -> dict[str, Any]:
    bound_edges = _region_edges(bounds)
    if not bound_edges:
        return {}
    return {
        "space": coordinate_space,
        "x": bound_edges["left"],
        "y": bound_edges["top"],
        "source": "overlay_coordinate_model.bounds",
    }


def _overlay_local_region(
    *,
    bounds: dict[str, Any],
    region: dict[str, Any],
) -> dict[str, Any]:
    bound_edges = _region_edges(bounds)
    region_edges = _region_edges(region)
    width = _safe_float(region.get("width"))
    height = _safe_float(region.get("height"))
    if not bound_edges or not region_edges or width is None or height is None:
        return {}
    return {
        "space": "overlay_local_logical_pixels",
        "x": region_edges["left"] - bound_edges["left"],
        "y": region_edges["top"] - bound_edges["top"],
        "width": width,
        "height": height,
    }


def _region_delta(source: dict[str, Any], target: dict[str, Any]) -> dict[str, float]:
    deltas: dict[str, float] = {}
    for key in ("x", "y", "width", "height"):
        source_value = _safe_float(source.get(key))
        target_value = _safe_float(target.get(key))
        if source_value is None or target_value is None:
            return {}
        deltas[key] = target_value - source_value
    return deltas


def _coordinate_transform_readback(
    *,
    requested: dict[str, Any],
    bounds: dict[str, Any],
    region: dict[str, Any],
    boundary: dict[str, Any],
    coordinate_space: str,
    transform: str,
    reason: str = "",
) -> dict[str, Any]:
    clean_transform = _safe_str(transform, "unavailable")
    source_space = _safe_str(requested.get("space"), "desktop")
    clean_reason = _safe_str(reason) or _safe_str(boundary.get("reason"))
    limitations = [
        "metadata_only_coordinate_transform",
        "visual_registration_unsupported",
        "capture_adapter_unavailable",
    ]
    if not region or not _region_edges(region):
        return {
            "status": "unavailable",
            "reason": clean_reason or "mapped_region_unavailable",
            "source_space": source_space,
            "target_space": coordinate_space,
            "transform": clean_transform,
            "transform_applied": False,
            "requested_to_mapped_delta": {},
            "overlay_origin": _overlay_origin(bounds, coordinate_space),
            "overlay_local_region": {},
            "intersection_overlay_local_region": {},
            "bounds_checked": False,
            "within_overlay_bounds": False,
            "clipped_by_overlay": False,
            "confidence": 0.0,
            "confidence_basis": "coordinate_transform_unavailable",
            "limitations": limitations,
        }

    bounds_checked = bool(boundary.get("bounds_checked"))
    within_bounds = bool(boundary.get("within_overlay_bounds"))
    intersection = _as_dict(boundary.get("intersection_region"))
    return {
        "status": "mapped" if within_bounds else "blocked_after_mapping",
        "reason": "" if within_bounds else clean_reason or "requested_region_outside_overlay_bounds",
        "source_space": source_space,
        "target_space": coordinate_space,
        "mapped_region_space": _safe_str(region.get("space"), coordinate_space),
        "transform": clean_transform,
        "transform_applied": clean_transform != "unavailable",
        "requested_to_mapped_delta": _region_delta(requested, region),
        "overlay_origin": _overlay_origin(bounds, coordinate_space),
        "overlay_local_region": _overlay_local_region(bounds=bounds, region=region),
        "intersection_overlay_local_region": _overlay_local_region(bounds=bounds, region=intersection),
        "bounds_checked": bounds_checked,
        "within_overlay_bounds": within_bounds,
        "clipped_by_overlay": bool(boundary.get("clipped_by_overlay")),
        "confidence": 1.0 if bounds_checked and clean_transform != "unavailable" else 0.0,
        "confidence_basis": "declared_overlay_coordinate_model_not_visual_perception",
        "limitations": limitations,
    }


def _coordinate_boundary(
    *,
    bounds: dict[str, Any],
    region: dict[str, Any],
    coordinate_space: str,
    reason: str = "",
) -> dict[str, Any]:
    clean_reason = _safe_str(reason)
    bound_edges = _region_edges(bounds)
    region_edges = _region_edges(region)
    if not bounds or not bound_edges:
        return {
            "status": "unavailable",
            "reason": clean_reason or "overlay_coordinate_model_missing",
            "coordinate_space": coordinate_space,
            "overlay_bounds": {},
            "overlay_edges": {},
            "requested_edges": region_edges,
            "intersection_region": {},
            "within_overlay_bounds": False,
            "clipped_by_overlay": False,
            "outside_edges": [],
            "bounds_checked": False,
        }
    if not region or not region_edges:
        return {
            "status": "unavailable",
            "reason": clean_reason or "requested_region_missing_numeric_bounds",
            "coordinate_space": coordinate_space,
            "overlay_bounds": bounds,
            "overlay_edges": bound_edges,
            "requested_edges": {},
            "intersection_region": {},
            "within_overlay_bounds": False,
            "clipped_by_overlay": False,
            "outside_edges": [],
            "bounds_checked": False,
        }

    contained = _contains(bounds, region)
    outside = _outside_edges(bounds, region)
    return {
        "status": "within_bounds" if contained else "outside_bounds",
        "reason": "" if contained else clean_reason or "requested_region_outside_overlay_bounds",
        "coordinate_space": coordinate_space,
        "overlay_bounds": bounds,
        "overlay_edges": bound_edges,
        "requested_edges": region_edges,
        "intersection_region": _intersection_region(
            bounds=bounds,
            region=region,
            coordinate_space=coordinate_space,
        ),
        "within_overlay_bounds": contained,
        "clipped_by_overlay": bool(outside),
        "outside_edges": outside,
        "bounds_checked": True,
    }


def _map_overlay_region(requested: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    coordinate_model = _as_dict(overlay.get("coordinate_model"))
    bounds = _as_dict(coordinate_model.get("bounds"))
    coordinate_space = _safe_str(coordinate_model.get("coordinate_space"), "desktop_logical_pixels")
    transform = _safe_str(coordinate_model.get("transform"), "unavailable")
    if not bool(overlay.get("available")):
        reason = "overlay_context_missing"
        boundary = _coordinate_boundary(
            bounds=bounds,
            region={},
            coordinate_space=coordinate_space,
            reason=reason,
        )
        return {
            "status": "blocked",
            "reason": reason,
            "region": {},
            "transform": "unavailable",
            "coordinate_boundary": boundary,
            "coordinate_transform": _coordinate_transform_readback(
                requested=requested,
                bounds=bounds,
                region={},
                boundary=boundary,
                coordinate_space=coordinate_space,
                transform="unavailable",
                reason=reason,
            ),
        }
    if not bool(requested.get("numeric_bounds")):
        reason = "requested_region_missing_numeric_bounds"
        boundary = _coordinate_boundary(
            bounds=bounds,
            region={},
            coordinate_space=coordinate_space,
            reason=reason,
        )
        return {
            "status": "blocked",
            "reason": reason,
            "region": {},
            "transform": "unavailable",
            "coordinate_boundary": boundary,
            "coordinate_transform": _coordinate_transform_readback(
                requested=requested,
                bounds=bounds,
                region={},
                boundary=boundary,
                coordinate_space=coordinate_space,
                transform="unavailable",
                reason=reason,
            ),
        }
    if not bounds:
        reason = "overlay_coordinate_model_missing"
        boundary = _coordinate_boundary(
            bounds=bounds,
            region={},
            coordinate_space=coordinate_space,
            reason=reason,
        )
        return {
            "status": "blocked",
            "reason": reason,
            "region": {},
            "transform": "unavailable",
            "coordinate_boundary": boundary,
            "coordinate_transform": _coordinate_transform_readback(
                requested=requested,
                bounds=bounds,
                region={},
                boundary=boundary,
                coordinate_space=coordinate_space,
                transform="unavailable",
                reason=reason,
            ),
        }
    if _safe_str(requested.get("space")).lower() == "canvas":
        reason = "canvas_transform_unavailable"
        boundary = _coordinate_boundary(
            bounds=bounds,
            region={},
            coordinate_space=coordinate_space,
            reason=reason,
        )
        return {
            "status": "blocked",
            "reason": reason,
            "region": {},
            "transform": "unavailable",
            "coordinate_boundary": boundary,
            "coordinate_transform": _coordinate_transform_readback(
                requested=requested,
                bounds=bounds,
                region={},
                boundary=boundary,
                coordinate_space=coordinate_space,
                transform="unavailable",
                reason=reason,
            ),
        }

    region = {
        "space": coordinate_space,
        "x": requested["x"],
        "y": requested["y"],
        "width": requested["width"],
        "height": requested["height"],
    }
    boundary = _coordinate_boundary(
        bounds=bounds,
        region=region,
        coordinate_space=coordinate_space,
        reason="requested_region_outside_overlay_bounds",
    )
    contained = bool(boundary.get("within_overlay_bounds"))
    return {
        "status": "mapped" if contained else "blocked",
        "reason": "" if contained else "requested_region_outside_overlay_bounds",
        "region": region,
        "transform": transform if transform != "unavailable" else "identity_desktop_logical",
        "bounds_checked": True,
        "within_overlay_bounds": contained,
        "coordinate_boundary": boundary,
        "coordinate_transform": _coordinate_transform_readback(
            requested=requested,
            bounds=bounds,
            region=region,
            boundary=boundary,
            coordinate_space=coordinate_space,
            transform=transform if transform != "unavailable" else "identity_desktop_logical",
            reason="requested_region_outside_overlay_bounds",
        ),
    }


def _active_window_summary(data: dict[str, Any]) -> dict[str, Any]:
    active_window = _as_dict(data.get("active_window"))
    if not active_window:
        return {"available": False}
    return {
        "available": bool(active_window.get("available")),
        "supported": bool(active_window.get("supported")),
        "platform": _safe_str(active_window.get("platform")),
        "capture": _safe_str(active_window.get("capture")),
        "has_title": "title" in active_window,
        "reason": _safe_str(active_window.get("reason")),
    }


def _observation_unknowns(result: dict[str, Any] | None = None) -> list[str]:
    governance = _as_dict((result or {}).get("governance"))
    unknowns = []
    if not bool(governance.get("screenshots")):
        unknowns.append("screenshot_pixels")
    if not bool(governance.get("pixels")):
        unknowns.append("pixel_content")
    unknowns.extend(["ocr_text", "accessibility_tree", "visual_similarity"])
    return unknowns


def _observation_limitations(
    *,
    mapped_overlay_region: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    failure_or_refusal_reason: str = "",
) -> list[str]:
    governance = _as_dict((result or {}).get("governance"))
    limitations = ["metadata_only_screen_session_readback"]
    if not bool(governance.get("screenshots")):
        limitations.append("screenshot_capture_unsupported")
    if not bool(governance.get("pixels")):
        limitations.append("pixel_capture_unsupported")
    limitations.extend(["ocr_unsupported", "accessibility_tree_unsupported", "visual_similarity_unsupported"])
    mapped = _as_dict(mapped_overlay_region)
    if mapped and _safe_str(mapped.get("status")) != "mapped":
        reason = _safe_str(mapped.get("reason"), "overlay_region_not_mapped")
        limitations.append(reason)
    reason = _safe_str(failure_or_refusal_reason)
    if reason and reason not in limitations:
        limitations.append(reason)
    return limitations


def _not_observed_region(reason: str) -> dict[str, Any]:
    return {
        "status": "not_observed",
        "region": {},
        "source": "none",
        "reason": _safe_str(reason),
    }


def _not_captured_region(mapped_overlay_region: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "status": "not_captured",
        "region": {},
        "mapped_region": _as_dict(mapped_overlay_region.get("region")),
        "capture": "not_performed",
        "screenshots": False,
        "pixels": False,
        "ocr": False,
        "accessibility_tree": False,
        "reason": _safe_str(reason, "capture_adapter_unavailable"),
    }


def _structured_observation_receipt(
    *,
    decision: str,
    status: str,
    requested_region: dict[str, Any],
    mapped_overlay_region: dict[str, Any],
    actual_inspected_region: dict[str, Any],
    actual_observed_region: dict[str, Any],
    actual_captured_region: dict[str, Any],
    source: dict[str, Any],
    evidence_reference: dict[str, Any],
    inferred_information: dict[str, Any],
    confidence: float,
    unknown_information: list[str],
    limitations: list[str],
    failure_or_refusal_reason: str = "",
) -> dict[str, Any]:
    return {
        "kind": "francis.lens.overlay.structured_observation_receipt",
        "schema_version": 1,
        "decision": _safe_str(decision),
        "status": _safe_str(status),
        "requested_region": requested_region,
        "mapped_overlay_region": mapped_overlay_region,
        "actual_inspected_region": actual_inspected_region,
        "actual_observed_region": actual_observed_region,
        "actual_captured_region": actual_captured_region,
        "source": source,
        "evidence_reference": evidence_reference,
        "inferred_information": inferred_information,
        "confidence": confidence,
        "unknowns": unknown_information,
        "limitations": limitations,
        "failure_or_refusal_reason": _safe_str(failure_or_refusal_reason),
        "governance": _observation_honesty(),
    }


def lens_observe_overlay_region(
    requested_region: dict[str, Any] | None = None,
    overlay_context: dict[str, Any] | None = None,
    *,
    actor: str = "unknown",
    observation_source: str = "francis.screen.session",
    correlation_id: str = "",
    parent_receipt_id: str = "",
    session_id: str = "",
    mission_id: str = "",
) -> dict[str, Any]:
    """Observe desktop context through the existing overlay/lens path.

    This does not capture pixels. It binds the request to the existing overlay
    coordinate model, then uses only safe read-only screen/session MCP readbacks.
    If the overlay model is missing, it refuses before calling a perception tool.
    """

    clean_actor = _safe_str(actor, "unknown")
    clean_source = _safe_str(observation_source, "francis.screen.session")
    requested = _region_payload(requested_region)
    overlay = _overlay_runtime_context(overlay_context)
    mapped = _map_overlay_region(requested, overlay)
    base_receipt = {
        "actor": clean_actor,
        "tool": clean_source,
        "correlation_id": _safe_str(correlation_id),
        "parent_receipt_id": _safe_str(parent_receipt_id),
        "session_id": _safe_str(session_id),
        "mission_id": _safe_str(mission_id),
        "requested_region": requested,
        "mapped_overlay_region": mapped,
        "observation_source": clean_source,
        "observation_mode": "live_readback",
    }

    if clean_source not in _OVERLAY_OBSERVATION_TOOLS:
        reason = "unsupported_overlay_observation_source"
        actual_observed_region = _not_observed_region(reason)
        actual_captured_region = _not_captured_region(mapped, reason)
        limitations = _observation_limitations(
            mapped_overlay_region=mapped,
            failure_or_refusal_reason=reason,
        )
        structured = _structured_observation_receipt(
            decision="refused",
            status="refused",
            requested_region=requested,
            mapped_overlay_region=mapped,
            actual_inspected_region={},
            actual_observed_region=actual_observed_region,
            actual_captured_region=actual_captured_region,
            source={
                "name": clean_source,
                "status": "refused",
                "mode": "live_readback",
                "live_simulated_fixture_or_replay": "live",
                "read_only": True,
            },
            evidence_reference={},
            inferred_information={},
            confidence=0.0,
            unknown_information=_observation_unknowns(),
            limitations=limitations,
            failure_or_refusal_reason=reason,
        )
        receipt = _record_receipt(
            {
                **base_receipt,
                "decision": "refused",
                "reason": reason,
                "actual_observed_region": actual_observed_region,
                "actual_captured_region": actual_captured_region,
                "limitations": limitations,
                "structured_observation_receipt": structured,
            }
        )
        return {
            "kind": "francis.lens.overlay.observation",
            "ok": False,
            "status": "refused",
            "surface": LENS_OVERLAY_OBSERVATION_SURFACE,
            "actor": clean_actor,
            "requested_region": requested,
            "overlay_context": overlay,
            "mapped_overlay_region": mapped,
            "actual_inspected_region": {},
            "actual_observed_region": actual_observed_region,
            "actual_captured_region": actual_captured_region,
            "observation_source": {"tool": clean_source, "status": "refused"},
            "evidence_reference": {},
            "inferred_information": {},
            "structured_observation_receipt": structured,
            "confidence": 0.0,
            "unknown_information": _observation_unknowns(),
            "limitations": limitations,
            "failure_or_refusal_reason": reason,
            "receipt": receipt,
            "governance": _observation_honesty(),
        }

    if mapped["status"] != "mapped":
        reason = _safe_str(mapped.get("reason"), "overlay_region_not_mapped")
        actual_observed_region = _not_observed_region(reason)
        actual_captured_region = _not_captured_region(mapped, reason)
        limitations = _observation_limitations(
            mapped_overlay_region=mapped,
            failure_or_refusal_reason=reason,
        )
        structured = _structured_observation_receipt(
            decision="refused",
            status="blocked",
            requested_region=requested,
            mapped_overlay_region=mapped,
            actual_inspected_region={},
            actual_observed_region=actual_observed_region,
            actual_captured_region=actual_captured_region,
            source={
                "name": clean_source,
                "status": "not_called",
                "mode": "live_readback",
                "live_simulated_fixture_or_replay": "live",
                "read_only": True,
            },
            evidence_reference={},
            inferred_information={},
            confidence=0.0,
            unknown_information=_observation_unknowns(),
            limitations=limitations,
            failure_or_refusal_reason=reason,
        )
        receipt = _record_receipt(
            {
                **base_receipt,
                "decision": "refused",
                "reason": reason,
                "actual_observed_region": actual_observed_region,
                "actual_captured_region": actual_captured_region,
                "limitations": limitations,
                "structured_observation_receipt": structured,
            }
        )
        return {
            "kind": "francis.lens.overlay.observation",
            "ok": False,
            "status": "blocked",
            "surface": LENS_OVERLAY_OBSERVATION_SURFACE,
            "actor": clean_actor,
            "requested_region": requested,
            "overlay_context": overlay,
            "mapped_overlay_region": mapped,
            "actual_inspected_region": {},
            "actual_observed_region": actual_observed_region,
            "actual_captured_region": actual_captured_region,
            "observation_source": {"tool": clean_source, "status": "not_called"},
            "evidence_reference": {},
            "inferred_information": {},
            "structured_observation_receipt": structured,
            "confidence": 0.0,
            "unknown_information": _observation_unknowns(),
            "limitations": limitations,
            "failure_or_refusal_reason": reason,
            "receipt": receipt,
            "governance": _observation_honesty(),
        }

    result = _mcp_run_tool(clean_source, {})
    data = _as_dict(result.get("data"))
    governance = _as_dict(result.get("governance"))
    ok = bool(result.get("ok"))
    actual_region = {
        "status": "inspected_metadata_only" if ok else "failed",
        "region": mapped["region"],
        "capture": "not_performed",
        "screenshots": bool(governance.get("screenshots")),
        "pixels": bool(governance.get("pixels")),
        "ocr": False,
    }
    evidence = {
        "status": "metadata_readback",
        "source": clean_source,
        "mcp_status": _safe_str(result.get("status")),
        "artifact_ref": "",
        "content_included": False,
    }
    inferred = {
        "active_window": _active_window_summary(data),
        "takeover": _as_dict(data.get("takeover")),
        "session": _as_dict(data.get("session")),
    }
    confidence = 0.35 if ok else 0.0
    unknowns = _observation_unknowns(result)
    failure_or_refusal_reason = "" if ok else _safe_str(result.get("error"), "observation_source_failed")
    actual_observed_region = (
        {
            "status": "observed_metadata_only",
            "region": mapped["region"],
            "source": clean_source,
            "readback": "mcp_metadata",
            "capture": "not_performed",
            "reason": "",
        }
        if ok
        else {
            "status": "failed",
            "region": {},
            "mapped_region": mapped["region"],
            "source": clean_source,
            "readback": "mcp_metadata",
            "capture": "not_performed",
            "reason": failure_or_refusal_reason,
        }
    )
    actual_captured_region = _not_captured_region(
        mapped,
        "capture_adapter_unavailable" if ok else failure_or_refusal_reason,
    )
    limitations = _observation_limitations(
        mapped_overlay_region=mapped,
        result=result,
        failure_or_refusal_reason=failure_or_refusal_reason,
    )
    source = {
        "name": clean_source,
        "status": _safe_str(result.get("status")),
        "mode": "live_readback",
        "live_simulated_fixture_or_replay": "live",
        "read_only": bool(governance.get("read_only")),
    }
    structured = _structured_observation_receipt(
        decision="observed" if ok else "failed",
        status="observed" if ok else "failed",
        requested_region=requested,
        mapped_overlay_region=mapped,
        actual_inspected_region=actual_region,
        actual_observed_region=actual_observed_region,
        actual_captured_region=actual_captured_region,
        source=source,
        evidence_reference=evidence,
        inferred_information=inferred,
        confidence=confidence,
        unknown_information=unknowns,
        limitations=limitations,
        failure_or_refusal_reason=failure_or_refusal_reason,
    )
    receipt = _record_receipt(
        {
            **base_receipt,
            "decision": "observed" if ok else "failed",
            "mcp_status": result.get("status"),
            "mcp_authority": governance.get("authority"),
            "actual_inspected_region": actual_region,
            "actual_observed_region": actual_observed_region,
            "actual_captured_region": actual_captured_region,
            "observation_status": "observed" if ok else "failed",
            "structured_observation_receipt": structured,
            "evidence_reference": evidence,
            "confidence": confidence,
            "unknown_information": unknowns,
            "limitations": limitations,
            "failure_or_refusal_reason": failure_or_refusal_reason,
        }
    )
    return {
        "kind": "francis.lens.overlay.observation",
        "ok": ok,
        "status": "observed" if ok else "failed",
        "surface": LENS_OVERLAY_OBSERVATION_SURFACE,
        "actor": clean_actor,
        "requested_region": requested,
        "overlay_context": overlay,
        "mapped_overlay_region": mapped,
        "actual_inspected_region": actual_region,
        "actual_observed_region": actual_observed_region,
        "actual_captured_region": actual_captured_region,
        "observation_source": {
            "tool": clean_source,
            "status": _safe_str(result.get("status")),
            "live_simulated_fixture_or_replay": "live",
            "read_only": bool(governance.get("read_only")),
        },
        "evidence_reference": evidence,
        "inferred_information": inferred,
        "structured_observation_receipt": structured,
        "confidence": confidence,
        "unknown_information": unknowns,
        "limitations": limitations,
        "failure_or_refusal_reason": failure_or_refusal_reason,
        "receipt": receipt,
        "governance": _observation_honesty(),
    }


def lens_perceive_via_mcp(tool: str, args: dict[str, Any] | None = None, *, actor: str = "unknown") -> dict[str, Any]:
    """Perceive through one read-only MCP tool, leaving a receipt.

    Refuses any tool not on the structurally-derived read-only allowlist. Never calls
    a mutating or approval-gated MCP tool. Never claims residency.
    """

    clean_tool = _safe_str(tool)
    clean_actor = _safe_str(actor, "unknown")
    allow = _perceivable_tool_names()

    if clean_tool not in allow:
        known = {_safe_str(t.get("name")) for t in _mcp_list_tools()}
        reason = "tool_not_read_only_perceivable" if clean_tool in known else "unknown_tool"
        receipt = _record_receipt({"actor": clean_actor, "tool": clean_tool, "decision": "refused", "reason": reason})
        return {
            "kind": "francis.lens.mcp.perception",
            "ok": False,
            "status": "refused",
            "surface": LENS_MCP_PERCEPTION_SURFACE,
            "tool": clean_tool,
            "actor": clean_actor,
            "error": reason,
            "perceivable_tools": sorted(allow),
            "receipt": receipt,
            "governance": _honesty(),
        }

    result = _mcp_run_tool(clean_tool, args or {})
    raw_governance = result.get("governance")
    governance = raw_governance if isinstance(raw_governance, dict) else {}
    receipt = _record_receipt(
        {
            "actor": clean_actor,
            "tool": clean_tool,
            "decision": "perceived",
            "mcp_status": result.get("status"),
            "mcp_authority": governance.get("authority"),
        }
    )
    return {
        "kind": "francis.lens.mcp.perception",
        "ok": bool(result.get("ok")),
        "status": "perceived",
        "surface": LENS_MCP_PERCEPTION_SURFACE,
        "tool": clean_tool,
        "actor": clean_actor,
        "mcp_result": result,
        "receipt": receipt,
        "governance": _honesty(),
    }


def lens_mcp_perception_receipts(limit: int = 10) -> dict[str, Any]:
    """Read newest perception receipts (auditable evidence of body->nervous-system calls)."""

    root = _receipt_root()
    safe_limit = max(1, min(int(limit or 10), 100))
    receipts: list[dict[str, Any]] = []
    if root.exists():
        paths = sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:safe_limit]
        for path in paths:
            try:
                receipts.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
    return {
        "kind": "francis.lens.mcp.perception.receipts",
        "ok": True,
        "status": "ready",
        "surface": LENS_MCP_PERCEPTION_SURFACE,
        "count": len(receipts),
        "receipts": receipts,
        "governance": _honesty(),
    }


__all__ = [
    "LENS_MCP_PERCEPTION_SURFACE",
    "LENS_MCP_PERCEIVE_ROUTE",
    "LENS_MCP_OBSERVE_ROUTE",
    "LENS_MCP_CONTRACT_ROUTE",
    "LENS_MCP_RECEIPTS_ROUTE",
    "LENS_OVERLAY_OBSERVATION_SURFACE",
    "lens_mcp_perception_contract",
    "lens_observe_overlay_region",
    "lens_perceive_via_mcp",
    "lens_mcp_perception_receipts",
]
