from __future__ import annotations

from typing import Any

from francis.api.errors import api_error_message
from francis.world_state.operator_mode import snapshot as operator_mode_snapshot


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def posture_write_guard(
    action_label: str,
    *,
    verification_prefix: str = "Writes are blocked until operator posture can be verified",
    observe_message: str = "Observe mode keeps Francis read-only.",
    writes_blocked_message: str = "Current operator posture blocks writes.",
) -> str:
    try:
        operator_state = operator_mode_snapshot()
    except Exception as exc:
        return f"{verification_prefix}: {api_error_message(exc, route='operator_posture')}"

    if not bool(operator_state.get("ok")):
        return f"{verification_prefix}."

    control_mode = _as_dict(operator_state.get("control_mode"))
    posture = _as_dict(operator_state.get("posture"))

    control_mode_id = _safe_str(control_mode.get("id")).strip().lower()
    control_writes = _safe_str(control_mode.get("writes")).strip().lower()
    posture_writes = _safe_str(posture.get("writes")).strip().lower()

    if control_mode_id == "observe" or control_writes == "blocked":
        return f"{observe_message} Switch posture before {action_label}."
    if posture_writes == "blocked":
        return f"{writes_blocked_message} Adjust the environment before {action_label}."
    return ""
