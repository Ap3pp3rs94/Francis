"""Bounded present-tense desktop heartbeat for the Lens Situation Model."""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir
from francis.lens.atomic_io import atomic_write_json as _atomic_write_json
from francis.lens.atomic_io import read_json_object as _read_json
from francis.lens.orb_body_state import lens_orb_body_runtime_readback
from francis.lens.perception_capture import DesktopFrame

LENS_SITUATION_MODEL_KIND = "lens.perception.situation_model"
LENS_SITUATION_MODEL_VERSION = 1
LENS_SITUATION_MODEL_ROUTE = "/lens/perception/now"
_GAME_TEACHING_SESSION_STATUS_KIND = "francis.apprenticeship.game_teaching_session.status"
_GAME_TEACHING_CONTRACT_VERSION = 1

_MAX_HEARTBEAT_AGE_SECONDS = 2.5
_MAX_HEARTBEAT_FUTURE_SKEW_SECONDS = 0.25


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
    game_observation: dict[str, Any] | None = None,
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
    game_state = _as_dict(game_observation)
    game_contract_valid = _game_observation_contract_valid(game_state, frame_id=frame_id, receipt_id=receipt_id)
    game_target = _as_dict(game_state.get("target"))
    game_model = _as_dict(game_state.get("model"))
    game_scene_ready = bool(
        game_contract_valid and game_state.get("ready") is True and game_state.get("semantic_scene_ready") is True
    )
    source_blockers = ["lens_semantic_watcher_not_ready"]
    if not input_stream_ready:
        source_blockers.extend(["lens_window_event_stream_not_connected", "lens_input_event_stream_not_connected"])
    else:
        source_blockers.extend(_string_items(input_stream.get("source_blockers")))
    if orb_body.get("ready") is not True:
        source_blockers.extend(_string_items(orb_body.get("blockers")) or ["lens_orb_body_state_not_connected"])
    if not game_state:
        source_blockers.append("lens_game_observer_not_connected")
    elif not game_contract_valid:
        source_blockers.append("lens_game_observer_contract_invalid")
    else:
        source_blockers.extend(_string_items(game_state.get("blockers")))
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
        "game_scene_ready": game_scene_ready,
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
            "game": _game_observation_present(game_state) if game_contract_valid else {},
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
            "game_observer": {
                "status": (
                    str(game_state.get("status") or "blocked")
                    if game_contract_valid
                    else "not_connected"
                    if not game_state
                    else "invalid"
                ),
                "ready": game_scene_ready,
                "configured": game_target.get("configured") is True if game_contract_valid else False,
                "target_id": str(game_target.get("id") or "") if game_contract_valid else "",
                "model_id": str(game_model.get("id") or "") if game_contract_valid else "",
                "local_inference_only": game_contract_valid,
                "remote_inference": False,
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
            "game_observer_authority_receipt_id": (
                str(_as_dict(game_state.get("runtime_identity")).get("authority_receipt_id") or "")
                if game_contract_valid
                else ""
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
            "local_game_inference": game_contract_valid,
            "remote_frame_transfer": False,
            "learning_authority": False,
            "reward_authority": False,
        },
    }
    _atomic_write_json(_situation_model_path(), payload)
    return lens_situation_model_readback(now=now)


def lens_situation_model_readback(*, now: float | None = None) -> dict[str, Any]:
    observed_at = time.time() if now is None else float(now)
    payload = _read_json(_situation_model_path())
    updated_at = _safe_float(payload.get("updated_at"))
    age_seconds = observed_at - updated_at if updated_at is not None else None
    fresh = bool(
        age_seconds is not None and -_MAX_HEARTBEAT_FUTURE_SKEW_SECONDS <= age_seconds <= _MAX_HEARTBEAT_AGE_SECONDS
    )
    runtime_identity = _as_dict(payload.get("runtime_identity"))
    governance = _as_dict(payload.get("governance"))
    sources = _as_dict(payload.get("sources"))
    game_source = _as_dict(sources.get("game_observer"))
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
        ) or any(
            governance.get(field, False) is not False
            for field in (
                "remote_frame_transfer",
                "learning_authority",
                "reward_authority",
            )
        ):
            blockers.append("lens_situation_model_heartbeat_overbroad")
        if payload.get("game_scene_ready") is True and (
            game_source.get("ready") is not True
            or game_source.get("local_inference_only") is not True
            or game_source.get("remote_inference") is not False
            or governance.get("local_game_inference") is not True
        ):
            blockers.append("lens_situation_model_game_observer_contract_invalid")
    heartbeat_ready = not blockers
    return {
        "kind": "lens.perception.situation_model_readback",
        "status": "heartbeat_ready" if heartbeat_ready else "missing" if not payload else "blocked",
        "route": LENS_SITUATION_MODEL_ROUTE,
        "heartbeat_ready": heartbeat_ready,
        "semantic_comprehension_ready": payload.get("semantic_comprehension_ready") is True,
        "game_scene_ready": heartbeat_ready and payload.get("game_scene_ready") is True,
        "has_current_desktop_state": payload.get("has_current_desktop_state") is True,
        "revision": str(payload.get("revision") or ""),
        "updated_at": updated_at,
        "lag_ms": round(age_seconds * 1000.0, 3) if age_seconds is not None else None,
        "max_lag_ms": int(_MAX_HEARTBEAT_AGE_SECONDS * 1000),
        "max_future_skew_ms": int(_MAX_HEARTBEAT_FUTURE_SKEW_SECONDS * 1000),
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
            "local_game_inference": governance.get("local_game_inference") is True,
            "remote_frame_transfer": False,
            "learning_authority": False,
            "reward_authority": False,
        },
    }


def _situation_model_path() -> Path:
    return data_dir() / "runtime" / "lens-perception" / "situation-model.json"


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def _game_observation_contract_valid(game_state: dict[str, Any], *, frame_id: str, receipt_id: str) -> bool:
    if not game_state:
        return False
    governance = _as_dict(game_state.get("governance"))
    runtime_identity = _as_dict(game_state.get("runtime_identity"))
    return bool(
        game_state.get("kind") == "lens.game.observation"
        and game_state.get("version") == 1
        and str(game_state.get("source_frame_id") or "") == frame_id
        and str(runtime_identity.get("authority_receipt_id") or "") == receipt_id
        and governance.get("observation_only") is True
        and governance.get("local_inference_only") is True
        and all(
            governance.get(field) is False
            for field in (
                "remote_frame_transfer",
                "raw_pixels_in_state",
                "window_titles_captured",
                "keyboard_content_captured",
                "user_mouse_captured",
                "input_execution_authority",
                "memory_write",
                "learning_authority",
                "reward_authority",
            )
        )
    )


def _game_observation_present(game_state: dict[str, Any]) -> dict[str, Any]:
    target = _as_dict(game_state.get("target"))
    foreground = _as_dict(game_state.get("foreground"))
    scene = _as_dict(game_state.get("scene"))
    classification = _as_dict(game_state.get("classification"))
    model = _as_dict(game_state.get("model"))
    teaching_session = _as_dict(game_state.get("teaching_session"))
    candidates: list[dict[str, Any]] = []
    raw_candidates = scene.get("candidates")
    if isinstance(raw_candidates, list):
        for raw_candidate in raw_candidates[:3]:
            candidate = _as_dict(raw_candidate)
            scene_id = str(candidate.get("scene_id") or "")
            score = _safe_float(candidate.get("score"))
            if scene_id and score is not None:
                candidates.append({"scene_id": scene_id, "score": score})
    return {
        "status": str(game_state.get("status") or ""),
        "ready": game_state.get("ready") is True,
        "semantic_scene_ready": game_state.get("semantic_scene_ready") is True,
        "source_frame_id": str(game_state.get("source_frame_id") or ""),
        "target": {
            "id": str(target.get("id") or ""),
            "configured": target.get("configured") is True,
            "process_names": _string_items(target.get("process_names")),
            "foreground": target.get("foreground") is True,
            "visibility_basis": str(target.get("visibility_basis") or ""),
        },
        "foreground": {
            "target_match": foreground.get("target_match") is True,
            "process_id": _safe_int(foreground.get("process_id")),
            "process_name": str(foreground.get("process_name") or ""),
            "window_id": _safe_int(foreground.get("window_id")),
            "window_title_included": False,
        },
        "scene": (
            {
                "ready": scene.get("ready") is True,
                "id": str(scene.get("id") or ""),
                "top_candidate_id": str(scene.get("top_candidate_id") or ""),
                "confidence": _safe_float(scene.get("confidence")),
                "margin": _safe_float(scene.get("margin")),
                "min_confidence": _safe_float(scene.get("min_confidence")),
                "min_margin": _safe_float(scene.get("min_margin")),
                "candidates": candidates,
            }
            if scene
            else {}
        ),
        "classification": (
            {
                "source_frame_id": str(classification.get("source_frame_id") or ""),
                "classified_at": _safe_float(classification.get("classified_at")),
                "age_ms": _safe_float(classification.get("age_ms")),
                "inference_ms": _safe_float(classification.get("inference_ms")),
                "device": str(classification.get("device") or ""),
                "backend": str(classification.get("backend") or ""),
                "score_normalization": str(classification.get("score_normalization") or ""),
            }
            if classification
            else {}
        ),
        "model": {
            "id": str(model.get("id") or ""),
            "configured": model.get("configured") is True,
            "local_files_present": model.get("local_files_present") is True,
            "remote_inference": False,
        },
        "teaching_session": (
            _game_teaching_session_present(teaching_session)
            if _game_teaching_session_contract_valid(
                teaching_session,
                target_id=str(target.get("id") or ""),
            )
            else {}
        ),
    }


def _game_teaching_session_contract_valid(teaching: dict[str, Any], *, target_id: str) -> bool:
    governance = _as_dict(teaching.get("governance"))
    return bool(
        teaching.get("kind") == _GAME_TEACHING_SESSION_STATUS_KIND
        and teaching.get("version") == _GAME_TEACHING_CONTRACT_VERSION
        and str(teaching.get("target_id") or "") == target_id
        and governance.get("explicit_start_stop_required") is True
        and governance.get("semantic_transitions_only") is True
        and all(
            governance.get(field) is False
            for field in (
                "raw_pixels_persisted",
                "window_titles_persisted",
                "keyboard_content_captured",
                "user_mouse_captured",
                "remote_frame_transfer",
                "passive_learning",
                "hidden_retention",
                "memory_write",
                "learning_authority",
                "reward_authority",
                "input_execution_authority",
                "automatic_replay",
                "automatic_generalization",
                "automatic_skillization",
                "automatic_capability_promotion",
            )
        )
        and governance.get("operator_review_required") is True
    )


def _game_teaching_session_present(teaching: dict[str, Any]) -> dict[str, Any]:
    governance = _as_dict(teaching.get("governance"))
    return {
        "status": str(teaching.get("status") or ""),
        "session_id": str(teaching.get("session_id") or ""),
        "target_id": str(teaching.get("target_id") or ""),
        "intent_label": str(teaching.get("intent_label") or ""),
        "declared_scope": str(teaching.get("declared_scope") or ""),
        "success_condition": str(teaching.get("success_condition") or ""),
        "started_at": _safe_float(teaching.get("started_at")),
        "deadline_at": _safe_float(teaching.get("deadline_at")),
        "remaining_seconds": _safe_float(teaching.get("remaining_seconds")),
        "recording_active": teaching.get("recording_active") is True,
        "event_count": _safe_int(teaching.get("event_count")),
        "max_events": _safe_int(teaching.get("max_events")),
        "latest_scene_id": str(teaching.get("latest_scene_id") or ""),
        "latest_event_at": _safe_float(teaching.get("latest_event_at")),
        "review_required": teaching.get("review_required") is True,
        "start_receipt_id": str(teaching.get("start_receipt_id") or ""),
        "episode_receipt_id": str(teaching.get("episode_receipt_id") or ""),
        "capture_mode": str(teaching.get("capture_mode") or ""),
        "blockers": _string_items(teaching.get("blockers")),
        "governance": {
            "explicit_start_stop_required": governance.get("explicit_start_stop_required") is True,
            "semantic_transitions_only": governance.get("semantic_transitions_only") is True,
            "raw_pixels_persisted": False,
            "window_titles_persisted": False,
            "keyboard_content_captured": False,
            "user_mouse_captured": False,
            "memory_write": False,
            "learning_authority": False,
            "reward_authority": False,
            "input_execution_authority": False,
            "automatic_capability_promotion": False,
            "operator_review_required": True,
        },
    }


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
