from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from francis.input_actuator.orb_operator import (
    ORB_FEEDBACK_STATES,
    ORB_OPERATOR_SURFACE,
    ORB_POINTER_MODE,
    ORB_VIRTUAL_POINTER_ID,
    latest_orb_operator_state,
)

NATIVE_ORB_STATE_SNAPSHOT_KIND = "francis.native_orb.state_snapshot"
NATIVE_ORB_STATE_SCHEMA_VERSION = "francis.native_orb.state_snapshot.v1"
NATIVE_ORB_STATE_SCHEMA_PATH = "schemas/native_orb_state_snapshot.schema.json"
NATIVE_ORB_VISUAL_LOCK_PATH = "docs/operations/ORB_VISUAL_LOCK.md"

_ACTIVE_FEEDBACK_STATES = frozenset({"moving", "clicking", "typing", "complete"})
_BLOCKED_FEEDBACK_STATES = frozenset({"blocked", "failed"})


def build_native_orb_state_snapshot(
    operator_state: Mapping[str, Any] | None = None,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build the read-only state contract consumed by a future native Orb body."""

    raw_operator_state = (
        dict(operator_state) if operator_state is not None else latest_orb_operator_state(create_dirs=False)
    )
    feedback_state = _feedback_state(raw_operator_state.get("feedback_state") or raw_operator_state.get("state"))
    raw_virtual_pointer = _mapping(raw_operator_state.get("virtual_pointer"))
    virtual_pointer = _virtual_pointer_snapshot(raw_virtual_pointer)
    unsafe_flags = _unsafe_source_flags(raw_operator_state, raw_virtual_pointer)
    authority = _authority_snapshot(unsafe_source_flags=unsafe_flags)
    return {
        "kind": NATIVE_ORB_STATE_SNAPSHOT_KIND,
        "schema_version": NATIVE_ORB_STATE_SCHEMA_VERSION,
        "schema_path": NATIVE_ORB_STATE_SCHEMA_PATH,
        "generated_at": _clean_text(generated_at) or datetime.now(UTC).isoformat(),
        "source": {
            "kind": "francis.core.readback",
            "operator_surface": ORB_OPERATOR_SURFACE,
            "operator_state_read_only": bool(raw_operator_state.get("read_only", True)),
            "receipt_observed": bool(_clean_text(raw_operator_state.get("receipt_id"))),
        },
        "runtime_contract": {
            "native_runtime": "cpp",
            "status": "contract_ready",
            "implemented": False,
            "active_renderer": False,
            "body_renderer_only": True,
            "authority_layer": "francis_core",
            "francis_core_remains_authority": True,
        },
        "visual_lock": {
            "source": NATIVE_ORB_VISUAL_LOCK_PATH,
            "parity_required": True,
            "redesign_allowed": False,
            "current_renderer": "wpf_3d_animated_energy_orb",
            "native_renderer_active": False,
            "visual_baseline_replacement_required_for_changes": True,
        },
        "render_state": {
            "posture": _render_posture(feedback_state),
            "feedback_state": feedback_state,
            "speaking": False,
            "listening": False,
            "interjecting": False,
            "approval_required": feedback_state == "blocked",
            "handback": feedback_state == "complete",
            "panic_stop_ready": True,
        },
        "virtual_pointer": virtual_pointer,
        "authority": authority,
        "ipc": {
            "state_channel": "read_only_snapshot",
            "event_channel": "not_implemented",
            "local_only": True,
            "network_transport_required": False,
            "accepts_mutation_events": False,
            "schema_versioned": True,
        },
        "event_contract": {
            "emits_intent_events": False,
            "mutation_events_default_denied": True,
            "panic_stop_event_requires_francis_core_routing": True,
            "desktop_action_events_require_governed_path": True,
        },
        "limitations": [
            "no_native_window_implemented",
            "no_cpp_renderer_implemented",
            "no_desktop_mutation_authority",
            "no_user_os_cursor_control",
            "no_lens_semantic_targeting",
            "no_plan_approval",
            "no_reversibility_proof",
        ],
    }


def _virtual_pointer_snapshot(pointer: Mapping[str, Any]) -> dict[str, Any]:
    available = bool(pointer.get("available"))
    return {
        "available": available,
        "pointer_id": _clean_text(pointer.get("pointer_id")) or ORB_VIRTUAL_POINTER_ID,
        "mode": _clean_text(pointer.get("mode")) or ORB_POINTER_MODE,
        "x": _safe_int(pointer.get("x")) if available else None,
        "y": _safe_int(pointer.get("y")) if available else None,
        "controls_user_os_cursor": False,
        "user_mouse_taken": False,
        "physical_input_performed": False,
        "desktop_effect_performed": False,
        "presentation_only": True,
    }


def _authority_snapshot(*, unsafe_source_flags: dict[str, bool]) -> dict[str, Any]:
    return {
        "read_only": True,
        "render_only": True,
        "francis_core_authority": True,
        "native_runtime_authority": False,
        "grants_execution_authority": False,
        "grants_capability_authority": False,
        "grants_input_authority": False,
        "grants_desktop_bridge_authority": False,
        "can_move_user_os_cursor": False,
        "can_click": False,
        "can_drag": False,
        "can_type": False,
        "can_enable_desktop_bridge": False,
        "can_persist_memory": False,
        "can_train_model": False,
        "unsafe_source_flags_observed": unsafe_source_flags,
        "unsafe_source_flags_denied": any(unsafe_source_flags.values()),
    }


def _unsafe_source_flags(raw_operator_state: Mapping[str, Any], virtual_pointer: Mapping[str, Any]) -> dict[str, bool]:
    return {
        "uses_user_os_cursor": bool(raw_operator_state.get("uses_user_os_cursor")),
        "user_mouse_taken": bool(raw_operator_state.get("user_mouse_taken"))
        or bool(virtual_pointer.get("user_mouse_taken")),
        "physical_input_performed": bool(raw_operator_state.get("physical_input_performed"))
        or bool(virtual_pointer.get("physical_input_performed")),
        "grants_execution_authority": bool(raw_operator_state.get("grants_execution_authority")),
        "desktop_effect_performed": bool(virtual_pointer.get("desktop_effect_performed")),
    }


def _feedback_state(value: Any) -> str:
    state = _clean_text(value) or "idle"
    if state in ORB_FEEDBACK_STATES:
        return state
    return "idle"


def _render_posture(feedback_state: str) -> str:
    if feedback_state in _BLOCKED_FEEDBACK_STATES:
        return "blocked"
    if feedback_state in _ACTIVE_FEEDBACK_STATES:
        return "active_feedback"
    return "ambient_rest"


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _clean_text(value: Any, *, limit: int = 160) -> str:
    if value is None:
        return ""
    return str(value).strip()[:limit]


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
