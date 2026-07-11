"""Fail-closed readback for the future Lens desktop perception runtime.

The Orb can be visibly present before Lens has a current desktop situation model.
This module keeps those states separate: a valid, fresh, supervisor-owned runtime
state is required before any caller may describe the Lens desktop plane as live.
It does not start capture, write state, or grant sensing authority.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir

LENS_PERCEPTION_RUNTIME_STATE_KIND = "lens.perception.runtime_state"
LENS_PERCEPTION_RUNTIME_STATE_VERSION = 1
LENS_PERCEPTION_RUNTIME_READBACK_KIND = "lens.perception.runtime_readback"
_EXPECTED_OWNER = "lens_supervisor"
_MAX_STATE_AGE_SECONDS = 5.0


def _safe_str(value: Any) -> str:
    return str(value if value is not None else "").strip()


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


def _runtime_state_path() -> Path:
    return data_dir() / "runtime" / "lens-perception" / "status.json"


def _read_runtime_state(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _bounded_capture_readback(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "authority_granted": value.get("authority_granted") is True,
        "active": value.get("active") is True,
        "receipt_id": _safe_str(value.get("receipt_id")),
        "source": _safe_str(value.get("source")),
        "pixels_in_readback": False,
    }


def lens_perception_runtime_readback(*, now: float | None = None) -> dict[str, Any]:
    """Return bounded live-perception truth without treating overlay presence as capture.

    A future supervised worker must write the documented runtime state. Until then,
    callers receive an explicit blocked state rather than an inferred desktop view.
    """

    observed_now = time.time() if now is None else float(now)
    path = _runtime_state_path()
    raw = _read_runtime_state(path)
    runtime_present = bool(raw)
    capture = _as_dict(raw.get("capture"))
    desktop_capture = _bounded_capture_readback(_as_dict(capture.get("desktop")))
    camera_capture = _bounded_capture_readback(_as_dict(capture.get("camera")))
    raw_situation = _as_dict(raw.get("situation_model"))
    owner = _safe_str(raw.get("owner"))
    state = _safe_str(raw.get("state"))
    updated_at = _safe_float(raw.get("updated_at"))
    age_seconds = observed_now - updated_at if updated_at is not None else None
    fresh = bool(age_seconds is not None and 0.0 <= age_seconds <= _MAX_STATE_AGE_SECONDS)
    state_kind_valid = _safe_str(raw.get("kind")) == LENS_PERCEPTION_RUNTIME_STATE_KIND
    version_valid = raw.get("version") == LENS_PERCEPTION_RUNTIME_STATE_VERSION
    owner_valid = owner == _EXPECTED_OWNER
    runtime_valid = bool(runtime_present and state_kind_valid and version_valid and owner_valid)
    situation_status = _safe_str(raw_situation.get("status"))
    situation_ready = situation_status == "ready"

    blockers: list[str] = []
    if not runtime_present:
        blockers.append("lens_perception_runtime_state_missing")
    else:
        if not state_kind_valid:
            blockers.append("lens_perception_runtime_state_kind_invalid")
        if not version_valid:
            blockers.append("lens_perception_runtime_state_version_invalid")
        if not owner_valid:
            blockers.append("lens_perception_runtime_owner_not_supervised")
        if state != "running":
            blockers.append("lens_perception_runtime_not_running")
        if not fresh:
            blockers.append("lens_perception_runtime_state_stale")
        if not desktop_capture["authority_granted"]:
            blockers.append("desktop_capture_authority_not_granted")
        if not desktop_capture["active"]:
            blockers.append("desktop_capture_not_active")
        if not desktop_capture["receipt_id"]:
            blockers.append("desktop_capture_receipt_missing")
        if not situation_ready:
            blockers.append("lens_situation_model_not_ready")

    ready = runtime_valid and state == "running" and fresh and situation_ready and not blockers
    return {
        "kind": LENS_PERCEPTION_RUNTIME_READBACK_KIND,
        "status": "ready" if ready else "not_observed" if not runtime_present else "blocked",
        "ready": ready,
        "route": "/lens/perception",
        "runtime_state_path": str(path),
        "runtime_state_present": runtime_present,
        "runtime_state_valid": runtime_valid,
        "owner": owner or "not_observed",
        "expected_owner": _EXPECTED_OWNER,
        "state": state or "not_observed",
        "updated_at": updated_at,
        "age_ms": round(age_seconds * 1000.0, 3) if age_seconds is not None else None,
        "max_age_ms": int(_MAX_STATE_AGE_SECONDS * 1000),
        "fresh": fresh,
        "situation_model": {
            "status": situation_status or "not_observed",
            "revision": _safe_str(raw_situation.get("revision")),
            "has_current_desktop_state": situation_ready,
            "raw_desktop_content_in_readback": False,
        },
        "capture": {
            "desktop": desktop_capture,
            "camera": camera_capture,
            "keyboard_content_captured": False,
            "user_mouse_captured": False,
        },
        "blockers": blockers,
        "limitations": [
            "does_not_start_capture",
            "does_not_grant_capture_authority",
            "does_not_return_pixels",
            "does_not_capture_keyboard_content",
            "does_not_control_user_mouse",
        ],
        "governance": {
            "read_only_contract": True,
            "starts_capture": False,
            "capture_authority": False,
            "execution_authority": False,
            "mutation_authority": False,
            "memory_write": False,
        },
    }
