"""Bounded present-tense desktop heartbeat for the Lens Situation Model."""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir
from francis.lens.orb_body_state import lens_orb_body_runtime_readback
from francis.lens.perception_capture import DesktopFrame

LENS_SITUATION_MODEL_KIND = "lens.perception.situation_model"
LENS_SITUATION_MODEL_VERSION = 1
LENS_SITUATION_MODEL_ROUTE = "/lens/perception/now"

_MAX_HEARTBEAT_AGE_SECONDS = 2.5


def write_lens_situation_model_heartbeat(
    *,
    frame: DesktopFrame,
    ring_buffer: dict[str, Any],
    authority_receipt_id: str,
    execution_approval_id: str,
    worker_pid: int,
    host_pid: int,
    supervisor_pid: int,
    input_events: dict[str, Any] | None = None,
    observed_at: float | None = None,
) -> dict[str, Any]:
    now = time.time() if observed_at is None else float(observed_at)
    if not math.isfinite(now) or now < frame.captured_at:
        raise ValueError("lens_situation_model_observation_time_invalid")
    receipt_id = str(authority_receipt_id or "").strip()
    approval_id = str(execution_approval_id or "").strip()
    frame_id = str(ring_buffer.get("latest_frame_id") or "").strip()
    if ring_buffer.get("ready") is not True or not frame_id:
        raise ValueError("lens_situation_model_ring_buffer_not_ready")
    if str(ring_buffer.get("authority_receipt_id") or "") != receipt_id:
        raise ValueError("lens_situation_model_authority_receipt_mismatch")
    if not receipt_id or not approval_id:
        raise ValueError("lens_situation_model_authority_missing")

    lag_seconds = max(0.0, now - frame.captured_at)
    orb_body = lens_orb_body_runtime_readback()
    input_stream = _as_dict(input_events)
    input_governance = _as_dict(input_stream.get("governance"))
    input_authority = _as_dict(input_stream.get("authority"))
    input_authorities = _as_dict(input_authority.get("authorities"))
    input_stream_ready = bool(
        input_stream.get("ready") is True
        and input_authority.get("active") is True
        and input_authorities.get("desktop_input_observation_authority") is True
        and input_governance.get("runtime_state_only") is True
        and all(
            input_governance.get(field) is False
            for field in (
                "keyboard_content_captured",
                "key_codes_captured",
                "typed_characters_captured",
                "window_titles_captured",
                "clipboard_content_captured",
                "input_execution_authority",
                "user_cursor_control_authority",
                "memory_write",
            )
        )
    )
    input_current = _as_dict(input_stream.get("current"))
    pointer_activity = _as_dict(input_stream.get("pointer_activity"))
    foreground = _as_dict(input_current.get("foreground"))
    source_blockers = ["lens_semantic_watcher_not_ready"]
    if not input_stream_ready:
        source_blockers.extend(["lens_window_event_stream_not_connected", "lens_input_event_stream_not_connected"])
    else:
        source_blockers.extend(_string_items(input_stream.get("source_blockers")))
    if orb_body.get("ready") is not True:
        source_blockers.extend(_string_items(orb_body.get("blockers")) or ["lens_orb_body_state_not_connected"])
    payload = {
        "kind": LENS_SITUATION_MODEL_KIND,
        "version": LENS_SITUATION_MODEL_VERSION,
        "status": "heartbeat_partial",
        "route": LENS_SITUATION_MODEL_ROUTE,
        "revision": frame_id,
        "updated_at": now,
        "source_frame_captured_at": frame.captured_at,
        "lag_ms": round(lag_seconds * 1000.0, 3),
        "max_lag_ms": int(_MAX_HEARTBEAT_AGE_SECONDS * 1000),
        "has_current_desktop_state": True,
        "semantic_comprehension_ready": False,
        "present": {
            "plane": "desktop",
            "coordinate_space": "windows_virtual_screen",
            "source_frame_id": frame_id,
            "source_frame_sha256": str(ring_buffer.get("latest_frame_sha256") or ""),
            "source_bounds": {
                "left": frame.origin_x,
                "top": frame.origin_y,
                "width": frame.source_width,
                "height": frame.source_height,
            },
            "stored_frame": {
                "width": frame.width,
                "height": frame.height,
                "byte_count": int(ring_buffer.get("latest_frame_byte_count") or 0),
            },
            "change": {
                "detected": ring_buffer.get("latest_change_detected") is True,
                "score": ring_buffer.get("latest_change_score"),
                "difference_hash": str(ring_buffer.get("latest_difference_hash") or ""),
            },
            "user_activity": "active" if pointer_activity.get("active") is True else "idle",
            "user_cursor": _as_dict(input_current.get("cursor")) if input_stream_ready else {},
            "foreground": foreground if input_stream_ready else {},
            "orb_yield_required": pointer_activity.get("orb_yield_required") is True,
            "orb_activity": "visible" if orb_body.get("ready") is True else "not_connected",
            "orb_body": orb_body,
        },
        "sources": {
            "desktop_ring_buffer": {"status": "ready", "ready": True},
            "frame_diff": {"status": "ready", "ready": True},
            "window_events": {
                "status": "ready" if input_stream_ready else "not_connected",
                "ready": input_stream_ready,
            },
            "input_events": {
                "status": "ready" if input_stream_ready else "not_connected",
                "ready": input_stream_ready,
                "route": str(input_stream.get("route") or "/lens/perception/input"),
                "event_count": int(input_stream.get("event_count") or 0),
                "gesture_count": int(input_stream.get("gesture_count") or 0),
                "authority_receipt_id": str(input_stream.get("authority_receipt_id") or ""),
            },
            "orb_body": {
                "status": str(orb_body.get("status") or "not_connected"),
                "ready": orb_body.get("ready") is True,
            },
            "semantic_watcher": {"status": "not_connected", "ready": False},
        },
        "runtime_identity": {
            "worker_pid": max(0, int(worker_pid)),
            "host_pid": max(0, int(host_pid)),
            "supervisor_pid": max(0, int(supervisor_pid)),
            "authority_receipt_id": receipt_id,
            "execution_approval_id": approval_id,
            "input_authority_receipt_id": (
                str(input_stream.get("authority_receipt_id") or "") if input_stream_ready else ""
            ),
        },
        "blockers": _dedupe(source_blockers),
        "governance": {
            "runtime_state_only": True,
            "observation_only": True,
            "desktop_capture_authority": True,
            "execution_authority": True,
            "desktop_input_observation_authority": input_stream_ready,
            "camera_capture_authority": False,
            "microphone_capture_authority": False,
            "keyboard_content_captured": False,
            "user_mouse_captured": False,
            "input_execution_authority": False,
            "memory_write": False,
            "raw_pixels_in_state": False,
        },
    }
    _atomic_write_json(_situation_model_path(), payload)
    return lens_situation_model_readback(now=now)


def lens_situation_model_readback(*, now: float | None = None) -> dict[str, Any]:
    observed_at = time.time() if now is None else float(now)
    payload = _read_json(_situation_model_path())
    updated_at = _safe_float(payload.get("updated_at"))
    age_seconds = observed_at - updated_at if updated_at is not None else None
    fresh = bool(age_seconds is not None and 0.0 <= age_seconds <= _MAX_HEARTBEAT_AGE_SECONDS)
    runtime_identity = _as_dict(payload.get("runtime_identity"))
    governance = _as_dict(payload.get("governance"))
    blockers: list[str] = []
    if not payload:
        blockers.append("lens_situation_model_heartbeat_missing")
    else:
        if payload.get("kind") != LENS_SITUATION_MODEL_KIND or payload.get("version") != LENS_SITUATION_MODEL_VERSION:
            blockers.append("lens_situation_model_heartbeat_contract_invalid")
        if payload.get("status") != "heartbeat_partial" or payload.get("has_current_desktop_state") is not True:
            blockers.append("lens_situation_model_heartbeat_state_invalid")
        if not fresh:
            blockers.append("lens_situation_model_heartbeat_stale")
        if not str(runtime_identity.get("authority_receipt_id") or "") or not str(
            runtime_identity.get("execution_approval_id") or ""
        ):
            blockers.append("lens_situation_model_heartbeat_authority_missing")
        if (
            governance.get("runtime_state_only") is not True
            or governance.get("observation_only") is not True
            or governance.get("desktop_capture_authority") is not True
            or governance.get("execution_authority") is not True
        ):
            blockers.append("lens_situation_model_heartbeat_governance_invalid")
        if any(
            governance.get(field) is not False
            for field in (
                "camera_capture_authority",
                "microphone_capture_authority",
                "keyboard_content_captured",
                "user_mouse_captured",
                "input_execution_authority",
                "memory_write",
                "raw_pixels_in_state",
            )
        ):
            blockers.append("lens_situation_model_heartbeat_overbroad")
    heartbeat_ready = not blockers
    return {
        "kind": "lens.perception.situation_model_readback",
        "status": "heartbeat_ready" if heartbeat_ready else "missing" if not payload else "blocked",
        "route": LENS_SITUATION_MODEL_ROUTE,
        "heartbeat_ready": heartbeat_ready,
        "semantic_comprehension_ready": payload.get("semantic_comprehension_ready") is True,
        "has_current_desktop_state": payload.get("has_current_desktop_state") is True,
        "revision": str(payload.get("revision") or ""),
        "updated_at": updated_at,
        "lag_ms": round(age_seconds * 1000.0, 3) if age_seconds is not None else None,
        "max_lag_ms": int(_MAX_HEARTBEAT_AGE_SECONDS * 1000),
        "fresh": fresh,
        "present": _as_dict(payload.get("present")),
        "sources": _as_dict(payload.get("sources")),
        "runtime_identity": runtime_identity,
        "source_blockers": _string_items(payload.get("blockers")),
        "blockers": _dedupe(blockers),
        "governance": {
            "read_only_contract": True,
            "runtime_state_only": governance.get("runtime_state_only") is True,
            "observation_only": governance.get("observation_only") is True,
            "keyboard_content_captured": False,
            "user_mouse_captured": False,
            "input_execution_authority": False,
            "memory_write": False,
            "raw_pixels_in_readback": False,
        },
    }


def _situation_model_path() -> Path:
    return data_dir() / "runtime" / "lens-perception" / "situation-model.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{os.getpid():x}.{time.time_ns():x}.tmp"
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


__all__ = [
    "LENS_SITUATION_MODEL_KIND",
    "LENS_SITUATION_MODEL_ROUTE",
    "LENS_SITUATION_MODEL_VERSION",
    "lens_situation_model_readback",
    "write_lens_situation_model_heartbeat",
]
