"""Bounded present-tense desktop heartbeat for the Lens Situation Model."""

from __future__ import annotations

import math
import re
import time
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir
from francis.lens.atomic_io import atomic_write_json as _atomic_write_json
from francis.lens.atomic_io import read_json_object as _read_json
from francis.lens.orb_body_state import lens_orb_body_runtime_readback
from francis.lens.perception_capture import DesktopFrame

LENS_SITUATION_MODEL_KIND = "lens.perception.situation_model"
LENS_SITUATION_MODEL_VERSION = 2
LENS_SITUATION_MODEL_ROUTE = "/lens/perception/now"
_LEGACY_LENS_SITUATION_MODEL_VERSION = 1
_GAME_OBSERVATION_KIND = "lens.game.observation"
_GAME_OBSERVATION_VERSION = 2
_LEGACY_GAME_OBSERVATION_VERSION = 1
_GAME_TEACHING_SESSION_STATUS_KIND = "francis.apprenticeship.game_teaching_session.status"
_GAME_TEACHING_EPISODE_REVIEW_STATUS_KIND = "francis.apprenticeship.game_teaching_episode_review.status"
_GAME_TEACHING_CONTRACT_VERSION = 1

_MAX_HEARTBEAT_AGE_SECONDS = 2.5
_MAX_HEARTBEAT_FUTURE_SKEW_SECONDS = 0.25
_TARGET_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_PROCESS_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_. -]{1,128}\.exe$", re.IGNORECASE)
_SCENE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]{0,47}$")
_FRAME_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$")
_GAME_TEACHING_SESSION_ID_PATTERN = re.compile(r"^game_teaching_[a-f0-9]{16}$")
_GAME_TEACHING_START_RECEIPT_ID_PATTERN = re.compile(r"^game_teaching_start_[a-f0-9]{16}$")
_GAME_TEACHING_EPISODE_RECEIPT_ID_PATTERN = re.compile(r"^game_teaching_episode_[a-f0-9]{16}$")
_GAME_TEACHING_REVIEW_RECEIPT_ID_PATTERN = re.compile(r"^game_teaching_review_[a-f0-9]{16}$")
_SHA256_DIGEST_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_TARGET_MODE_PROCESS_ALLOWLIST = "process_allowlist"
_TARGET_MODE_FOREGROUND_GAME = "foreground_game"
_GAME_TEACHING_CAPTURE_MODE = "explicit_semantic_scene_transition_session"
_MAX_GAME_TEACHING_DURATION_SECONDS = 28_800.0
_MAX_GAME_TEACHING_EVENTS = 1_000
_MAX_GAME_TEACHING_REVIEW_CORRECTIONS = 50
_GAME_OBSERVER_BLOCKERS_BY_STATUS = {
    "configuration_invalid": "lens_game_observer_configuration_invalid",
    "not_configured": "lens_game_observer_target_not_configured",
    "foreground_unavailable": "lens_game_observer_foreground_process_unavailable",
    "foreground_game_verification_unavailable": "lens_game_observer_foreground_game_verification_unavailable",
    "target_not_foreground": "lens_game_target_not_foreground",
    "semantic_model_not_configured": "lens_game_semantic_model_not_configured",
    "semantic_model_missing": "lens_game_observer_model_files_missing",
    "semantic_warming": "lens_game_semantic_inference_pending",
    "scene_uncertain": "lens_game_scene_confidence_below_threshold",
}
_GAME_OBSERVER_INFERENCE_BLOCKERS = {
    "lens_game_observer_dependencies_missing",
    "lens_game_observer_inference_failed",
    "lens_game_observer_model_files_missing",
    "lens_game_observer_model_load_failed",
}
_GAME_OBSERVER_FOREGROUND_REQUIRED_STATUSES = {
    "semantic_inference_failed",
    "semantic_model_missing",
    "semantic_model_not_configured",
    "semantic_warming",
    "scene_uncertain",
}
_GAME_TEACHING_SESSION_BLOCKERS = {
    "game_teaching_duration_limit_reached",
    "game_teaching_event_limit_reached",
    "game_teaching_semantic_event_write_failed",
    "game_teaching_session_finalization_incomplete",
    "game_teaching_session_state_invalid",
}
_GAME_TEACHING_REVIEW_BLOCKERS = {
    "game_teaching_episode_changed_after_review",
    "game_teaching_episode_contract_invalid",
    "game_teaching_episode_digest_mismatch",
    "game_teaching_episode_digest_missing",
    "game_teaching_episode_not_found",
    "game_teaching_episode_not_ready_for_operator_review",
    "game_teaching_episode_receipt_id_invalid",
    "game_teaching_episode_scene_confirmation_invalid",
    "game_teaching_episode_sequence_count_invalid",
    "game_teaching_episode_sequence_invalid",
    "game_teaching_episode_sequence_time_invalid",
}


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
    game_contract_status = _game_observation_contract_status(game_state, frame_id=frame_id, receipt_id=receipt_id)
    game_contract_valid = game_contract_status == "valid"
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
    elif game_contract_status == "legacy_v1":
        source_blockers.append("lens_game_observer_contract_legacy_v1")
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
                    else "legacy_v1_blocked"
                    if game_contract_status == "legacy_v1"
                    else "not_connected"
                    if not game_state
                    else "invalid"
                ),
                "ready": game_scene_ready,
                "configured": game_target.get("configured") is True if game_contract_valid else False,
                "target_id": str(game_target.get("id") or "") if game_contract_valid else "",
                "target_mode": str(game_target.get("mode") or "") if game_contract_valid else "",
                "model_id": str(game_model.get("id") or "") if game_contract_valid else "",
                "local_inference_only": game_contract_valid,
                "remote_inference": False,
                "foreground_game_required": game_contract_valid,
                "local_process_launch_authority": False,
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
            "local_process_launch_authority": False,
            "memory_write": False,
            "raw_pixels_in_state": False,
            "local_game_inference": game_contract_valid,
            "remote_frame_transfer": False,
            "learning_authority": False,
            "reward_authority": False,
            "foreground_game_required": True,
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
    heartbeat_version = payload.get("version")
    current_contract = bool(
        payload.get("kind") == LENS_SITUATION_MODEL_KIND
        and not isinstance(heartbeat_version, bool)
        and heartbeat_version == LENS_SITUATION_MODEL_VERSION
    )
    legacy_contract = bool(
        payload.get("kind") == LENS_SITUATION_MODEL_KIND
        and not isinstance(heartbeat_version, bool)
        and heartbeat_version == _LEGACY_LENS_SITUATION_MODEL_VERSION
    )
    blockers: list[str] = []
    if not payload:
        blockers.append("lens_situation_model_heartbeat_missing")
    else:
        if legacy_contract:
            blockers.append("lens_situation_model_heartbeat_legacy_v1")
        elif not current_contract:
            blockers.append("lens_situation_model_heartbeat_contract_invalid")
        if payload.get("status") != "heartbeat_partial" or payload.get("has_current_desktop_state") is not True:
            blockers.append("lens_situation_model_heartbeat_state_invalid")
        if not fresh:
            blockers.append("lens_situation_model_heartbeat_stale")
        if not str(runtime_identity.get("authority_receipt_id") or "") or not str(
            runtime_identity.get("execution_approval_id") or ""
        ):
            blockers.append("lens_situation_model_heartbeat_authority_missing")
        if current_contract:
            if (
                governance.get("runtime_state_only") is not True
                or governance.get("observation_only") is not True
                or governance.get("desktop_capture_authority") is not True
                or governance.get("execution_authority") is not True
                or governance.get("foreground_game_required") is not True
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
                    "local_process_launch_authority",
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
        "heartbeat_version": _safe_int(heartbeat_version),
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


def _strict_contract_int(value: Any, *, minimum: int, maximum: int) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        return None
    return value


def _strict_contract_float(value: Any, *, minimum: float, maximum: float) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    parsed = float(value)
    if not math.isfinite(parsed) or not minimum <= parsed <= maximum:
        return None
    return parsed


def _bounded_contract_text(value: Any, *, minimum: int, maximum: int) -> str | None:
    if not isinstance(value, str) or value != value.strip() or not minimum <= len(value) <= maximum:
        return None
    return value


def _bounded_contract_blockers(value: Any, *, allowed: set[str], maximum: int = 8) -> list[str] | None:
    if (
        not isinstance(value, list)
        or len(value) > maximum
        or any(not isinstance(item, str) or item not in allowed for item in value)
        or len(set(value)) != len(value)
    ):
        return None
    return value


def _game_observation_contract_status(game_state: dict[str, Any], *, frame_id: str, receipt_id: str) -> str:
    if not game_state or game_state.get("kind") != _GAME_OBSERVATION_KIND:
        return "invalid"
    version = game_state.get("version")
    if isinstance(version, bool):
        return "invalid"
    if version == _LEGACY_GAME_OBSERVATION_VERSION:
        return "legacy_v1"
    if version != _GAME_OBSERVATION_VERSION:
        return "invalid"
    return (
        "valid"
        if _game_observation_v2_contract_valid(game_state, frame_id=frame_id, receipt_id=receipt_id)
        else "invalid"
    )


def _game_observation_contract_valid(game_state: dict[str, Any], *, frame_id: str, receipt_id: str) -> bool:
    return _game_observation_contract_status(game_state, frame_id=frame_id, receipt_id=receipt_id) == "valid"


def _game_observation_v2_contract_valid(
    game_state: dict[str, Any],
    *,
    frame_id: str,
    receipt_id: str,
) -> bool:
    configuration = _as_dict(game_state.get("configuration"))
    governance = _as_dict(game_state.get("governance"))
    runtime_identity = _as_dict(game_state.get("runtime_identity"))
    target = _as_dict(game_state.get("target"))
    model = _as_dict(game_state.get("model"))
    ready = game_state.get("ready") is True
    semantic_ready = game_state.get("semantic_scene_ready") is True
    observed_at = _safe_float(game_state.get("observed_at"))
    blockers = game_state.get("blockers")
    if observed_at is None:
        return False
    base_valid = bool(
        str(game_state.get("source_frame_id") or "") == frame_id
        and _FRAME_ID_PATTERN.fullmatch(frame_id)
        and isinstance(game_state.get("ready"), bool)
        and isinstance(game_state.get("semantic_scene_ready"), bool)
        and ready is semantic_ready
        and str(runtime_identity.get("authority_receipt_id") or "") == receipt_id
        and 1 <= len(receipt_id) <= 256
        and _game_observer_configuration_contract_valid(configuration)
        and _game_target_contract_valid(target, require_ready=ready)
        and _game_model_contract_valid(model, require_ready=ready)
        and isinstance(blockers, list)
        and all(isinstance(item, str) and 1 <= len(item) <= 160 for item in blockers)
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
                "local_process_launch_authority",
                "memory_write",
                "learning_authority",
                "reward_authority",
            )
        )
        and governance.get("foreground_game_required") is True
        and _game_teaching_lineage_valid(game_state, target_id=str(target.get("id") or ""))
    )
    if not base_valid:
        return False
    if not ready:
        return _blocked_game_observation_lineage_valid(
            game_state,
            target=target,
            model=model,
            observed_at=observed_at,
            receipt_id=receipt_id,
        )
    return _ready_game_observation_lineage_valid(
        game_state,
        target=target,
        model=model,
        observed_at=observed_at,
        receipt_id=receipt_id,
    )


def _blocked_game_observation_lineage_valid(
    game_state: dict[str, Any],
    *,
    target: dict[str, Any],
    model: dict[str, Any],
    observed_at: float,
    receipt_id: str,
) -> bool:
    status = game_state.get("status")
    blockers = game_state.get("blockers")
    foreground_value = game_state.get("foreground")
    scene_value = game_state.get("scene")
    classification_value = game_state.get("classification")
    if (
        not isinstance(status, str)
        or not isinstance(blockers, list)
        or not isinstance(foreground_value, dict)
        or not isinstance(scene_value, dict)
        or not isinstance(classification_value, dict)
    ):
        return False
    expected_blocker = _GAME_OBSERVER_BLOCKERS_BY_STATUS.get(status)
    if expected_blocker is not None:
        if blockers != [expected_blocker]:
            return False
    elif status == "semantic_inference_failed":
        if len(blockers) != 1 or blockers[0] not in _GAME_OBSERVER_INFERENCE_BLOCKERS:
            return False
    else:
        return False

    foreground_required = status in _GAME_OBSERVER_FOREGROUND_REQUIRED_STATUSES
    if not _blocked_game_foreground_contract_valid(
        foreground_value,
        target=target,
        require_match=foreground_required,
    ):
        return False
    if status == "configuration_invalid":
        configuration = _as_dict(game_state.get("configuration"))
        if (
            configuration.get("source") != "invalid"
            or configuration.get("loaded") is not False
            or configuration.get("enabled") is not False
        ):
            return False
    elif status == "not_configured":
        if target.get("configured") is not False:
            return False
    elif status == "foreground_unavailable":
        if target.get("configured") is not True or foreground_value.get("available") is not False:
            return False
    elif status == "foreground_game_verification_unavailable":
        if (
            target.get("configured") is not True
            or target.get("mode") != _TARGET_MODE_FOREGROUND_GAME
            or foreground_value.get("available") is not True
        ):
            return False
    elif status == "target_not_foreground":
        if target.get("configured") is not True or foreground_value.get("available") is not True:
            return False
    elif status == "semantic_model_not_configured":
        if model.get("configured") is not False:
            return False
    elif status in {"semantic_inference_failed", "semantic_warming", "scene_uncertain"}:
        if model.get("configured") is not True or model.get("local_files_present") is not True:
            return False
    elif status == "semantic_model_missing":
        if model.get("configured") is not True or model.get("local_files_present") is not False:
            return False

    if status != "scene_uncertain":
        return scene_value == {} and classification_value == {}
    process_id = _strict_contract_int(foreground_value.get("process_id"), minimum=1, maximum=4_294_967_295)
    process_name = foreground_value.get("process_name")
    return bool(
        process_id is not None
        and isinstance(process_name, str)
        and _game_uncertain_scene_contract_valid(scene_value)
        and _game_classification_lineage_valid(
            classification_value,
            scene=scene_value,
            observed_at=observed_at,
            target_id=str(target.get("id") or ""),
            process_id=process_id,
            process_name=process_name,
            model_id=str(model.get("id") or ""),
            receipt_id=receipt_id,
        )
    )


def _blocked_game_foreground_contract_valid(
    foreground: dict[str, Any],
    *,
    target: dict[str, Any],
    require_match: bool,
) -> bool:
    process_id = _strict_contract_int(foreground.get("process_id"), minimum=0, maximum=4_294_967_295)
    window_id = _strict_contract_int(foreground.get("window_id"), minimum=0, maximum=18_446_744_073_709_551_615)
    process_name = foreground.get("process_name")
    verification_basis = foreground.get("verification_basis")
    if (
        process_id is None
        or window_id is None
        or not isinstance(process_name, str)
        or not isinstance(verification_basis, str)
        or not all(
            isinstance(foreground.get(field), bool)
            for field in ("supported", "available", "target_match", "window_title_included", "game_verified")
        )
        or foreground.get("window_title_included") is not False
    ):
        return False
    if not require_match:
        return bool(
            target.get("foreground") is False
            and target.get("visibility_basis") == "not_observed"
            and foreground.get("target_match") is False
            and process_id == 0
            and process_name == ""
            and window_id == 0
            and foreground.get("game_verified") is False
            and verification_basis == ""
        )
    mode = target.get("mode")
    expected_basis = (
        "local_launcher_library_path" if mode == _TARGET_MODE_FOREGROUND_GAME else "foreground_process_match"
    )
    process_names = target.get("process_names")
    return bool(
        target.get("foreground") is True
        and target.get("visibility_basis") == expected_basis
        and foreground.get("supported") is True
        and foreground.get("available") is True
        and foreground.get("target_match") is True
        and process_id > 0
        and window_id > 0
        and _PROCESS_NAME_PATTERN.fullmatch(process_name)
        and verification_basis == expected_basis
        and (
            mode != _TARGET_MODE_PROCESS_ALLOWLIST
            or (
                isinstance(process_names, list)
                and process_name.casefold() in {item.casefold() for item in process_names}
                and foreground.get("game_verified") is False
            )
        )
        and (mode != _TARGET_MODE_FOREGROUND_GAME or foreground.get("game_verified") is True)
    )


def _game_uncertain_scene_contract_valid(scene: dict[str, Any]) -> bool:
    raw_candidates = scene.get("candidates")
    confidence = _strict_contract_float(scene.get("confidence"), minimum=0.0, maximum=1.0)
    margin = _strict_contract_float(scene.get("margin"), minimum=0.0, maximum=1.0)
    if scene.get("ready") is not False or confidence is None or margin is None or not isinstance(raw_candidates, list):
        return False
    if not raw_candidates:
        return bool(
            scene.get("id") == ""
            and scene.get("top_candidate_id") in {None, ""}
            and confidence == 0.0
            and margin == 0.0
            and scene.get("min_confidence") is None
            and scene.get("min_margin") is None
        )
    min_confidence = _strict_contract_float(scene.get("min_confidence"), minimum=0.0, maximum=1.0)
    min_margin = _strict_contract_float(scene.get("min_margin"), minimum=0.0, maximum=1.0)
    top_candidate_id = scene.get("top_candidate_id")
    if (
        scene.get("id") != "uncertain"
        or not isinstance(top_candidate_id, str)
        or not _SCENE_ID_PATTERN.fullmatch(top_candidate_id)
        or min_confidence is None
        or min_margin is None
        or not 1 <= len(raw_candidates) <= 3
    ):
        return False
    candidates: list[tuple[str, float]] = []
    for raw_candidate in raw_candidates:
        candidate = _as_dict(raw_candidate)
        candidate_id = candidate.get("scene_id")
        score = _strict_contract_float(candidate.get("score"), minimum=0.0, maximum=1.0)
        if not isinstance(candidate_id, str) or not _SCENE_ID_PATTERN.fullmatch(candidate_id) or score is None:
            return False
        candidates.append((candidate_id, score))
    if len({candidate_id for candidate_id, _score in candidates}) != len(candidates):
        return False
    expected_margin = max(0.0, candidates[0][1] - (candidates[1][1] if len(candidates) > 1 else 0.0))
    return bool(
        candidates == sorted(candidates, key=lambda item: item[1], reverse=True)
        and candidates[0][0] == top_candidate_id
        and abs(candidates[0][1] - confidence) <= 1e-6
        and abs(expected_margin - margin) <= 1e-6
        and (confidence < min_confidence or margin < min_margin)
    )


def _game_target_contract_valid(target: dict[str, Any], *, require_ready: bool) -> bool:
    if not target:
        return False
    target_id = str(target.get("id") or "")
    mode = str(target.get("mode") or "")
    process_names = target.get("process_names")
    launchers = target.get("launchers")
    if (
        not isinstance(target.get("configured"), bool)
        or not isinstance(target.get("foreground"), bool)
        or not isinstance(process_names, list)
        or not isinstance(launchers, list)
        or any(not isinstance(item, str) or not _PROCESS_NAME_PATTERN.fullmatch(item) for item in process_names)
        or any(not isinstance(item, str) or item != "steam" for item in launchers)
        or len({item.casefold() for item in process_names}) != len(process_names)
        or len(set(launchers)) != len(launchers)
        or (target_id and not _TARGET_ID_PATTERN.fullmatch(target_id))
    ):
        return False
    if mode == _TARGET_MODE_PROCESS_ALLOWLIST:
        configured = bool(target_id and process_names and not launchers)
        expected_basis = "foreground_process_match"
    elif mode == _TARGET_MODE_FOREGROUND_GAME:
        configured = bool(target_id and launchers and not process_names)
        expected_basis = "local_launcher_library_path"
    else:
        return False
    foreground = target.get("foreground") is True
    visibility_basis = str(target.get("visibility_basis") or "")
    return bool(
        target.get("configured") is configured
        and (visibility_basis == expected_basis if foreground else visibility_basis == "not_observed")
        and (not require_ready or (configured and foreground))
    )


def _game_model_contract_valid(model: dict[str, Any], *, require_ready: bool) -> bool:
    if not model:
        return False
    model_id = str(model.get("id") or "")
    if (
        not isinstance(model.get("configured"), bool)
        or not isinstance(model.get("local_files_present"), bool)
        or model.get("remote_inference") is not False
        or (model_id and not _MODEL_ID_PATTERN.fullmatch(model_id))
        or ".." in model_id.split("/")
    ):
        return False
    if model.get("configured") is True and not model_id:
        return False
    return bool(
        not require_ready
        or (model.get("configured") is True and model.get("local_files_present") is True and bool(model_id))
    )


def _ready_game_observation_lineage_valid(
    game_state: dict[str, Any],
    *,
    target: dict[str, Any],
    model: dict[str, Any],
    observed_at: float,
    receipt_id: str,
) -> bool:
    foreground = _as_dict(game_state.get("foreground"))
    scene = _as_dict(game_state.get("scene"))
    classification = _as_dict(game_state.get("classification"))
    process_id = _safe_int(foreground.get("process_id"))
    process_name = str(foreground.get("process_name") or "")
    target_id = str(target.get("id") or "")
    mode = str(target.get("mode") or "")
    expected_basis = (
        "local_launcher_library_path" if mode == _TARGET_MODE_FOREGROUND_GAME else "foreground_process_match"
    )
    process_names = target.get("process_names")
    if not isinstance(process_names, list):
        return False
    if (
        game_state.get("status") != "scene_classified"
        or game_state.get("blockers") != []
        or foreground.get("supported") is not True
        or foreground.get("available") is not True
        or foreground.get("target_match") is not True
        or process_id <= 0
        or _safe_int(foreground.get("window_id")) <= 0
        or not _PROCESS_NAME_PATTERN.fullmatch(process_name)
        or foreground.get("window_title_included") is not False
        or str(foreground.get("verification_basis") or "") != expected_basis
        or (
            mode == _TARGET_MODE_PROCESS_ALLOWLIST
            and process_name.casefold() not in {item.casefold() for item in process_names}
        )
        or (mode == _TARGET_MODE_PROCESS_ALLOWLIST and foreground.get("game_verified") is not False)
        or (mode == _TARGET_MODE_FOREGROUND_GAME and foreground.get("game_verified") is not True)
    ):
        return False
    return _game_scene_contract_valid(scene) and _game_classification_lineage_valid(
        classification,
        scene=scene,
        observed_at=observed_at,
        target_id=target_id,
        process_id=process_id,
        process_name=process_name,
        model_id=str(model.get("id") or ""),
        receipt_id=receipt_id,
    )


def _game_scene_contract_valid(scene: dict[str, Any]) -> bool:
    confidence = _safe_float(scene.get("confidence"))
    margin = _safe_float(scene.get("margin"))
    min_confidence = _safe_float(scene.get("min_confidence"))
    min_margin = _safe_float(scene.get("min_margin"))
    scene_id = str(scene.get("id") or "")
    top_candidate_id = str(scene.get("top_candidate_id") or "")
    raw_candidates = scene.get("candidates")
    if (
        scene.get("ready") is not True
        or not _SCENE_ID_PATTERN.fullmatch(scene_id)
        or top_candidate_id != scene_id
        or confidence is None
        or margin is None
        or min_confidence is None
        or min_margin is None
        or not all(0.0 <= value <= 1.0 for value in (confidence, margin, min_confidence, min_margin))
        or confidence < min_confidence
        or margin < min_margin
        or not isinstance(raw_candidates, list)
        or not 1 <= len(raw_candidates) <= 3
    ):
        return False
    candidates: list[tuple[str, float]] = []
    for raw_candidate in raw_candidates:
        candidate = _as_dict(raw_candidate)
        candidate_id = str(candidate.get("scene_id") or "")
        score = _safe_float(candidate.get("score"))
        if not _SCENE_ID_PATTERN.fullmatch(candidate_id) or score is None or not 0.0 <= score <= 1.0:
            return False
        candidates.append((candidate_id, score))
    if len({candidate_id for candidate_id, _score in candidates}) != len(candidates):
        return False
    expected_margin = max(0.0, candidates[0][1] - (candidates[1][1] if len(candidates) > 1 else 0.0))
    return bool(
        candidates == sorted(candidates, key=lambda item: item[1], reverse=True)
        and candidates[0][0] == scene_id
        and abs(candidates[0][1] - confidence) <= 1e-6
        and abs(expected_margin - margin) <= 1e-6
    )


def _game_classification_lineage_valid(
    classification: dict[str, Any],
    *,
    scene: dict[str, Any],
    observed_at: float,
    target_id: str,
    process_id: int,
    process_name: str,
    model_id: str,
    receipt_id: str,
) -> bool:
    source_frame_id = str(classification.get("source_frame_id") or "")
    classified_at = _safe_float(classification.get("classified_at"))
    age_ms = _safe_float(classification.get("age_ms"))
    max_age_ms = _safe_float(classification.get("max_age_ms"))
    inference_ms = _safe_float(classification.get("inference_ms"))
    if (
        not _FRAME_ID_PATTERN.fullmatch(source_frame_id)
        or classified_at is None
        or age_ms is None
        or max_age_ms is None
        or inference_ms is None
        or not 0.0 <= classified_at <= observed_at
        or age_ms < 0.0
        or not 500.0 <= max_age_ms <= 60000.0
        or age_ms > max_age_ms
        or inference_ms < 0.0
        or abs(((observed_at - classified_at) * 1000.0) - age_ms) > 1.0
        or not 1 <= len(str(classification.get("device") or "")) <= 80
        or not 1 <= len(str(classification.get("backend") or "")) <= 120
        or not 1 <= len(str(classification.get("score_normalization") or "")) <= 120
    ):
        return False
    return bool(
        str(classification.get("target_id") or "") == target_id
        and _safe_int(classification.get("process_id")) == process_id
        and str(classification.get("process_name") or "").casefold() == process_name.casefold()
        and str(classification.get("model_id") or "") == model_id
        and str(classification.get("scene_id") or "") == str(scene.get("id") or "")
        and str(classification.get("authority_receipt_id") or "") == receipt_id
    )


def _game_teaching_lineage_valid(game_state: dict[str, Any], *, target_id: str) -> bool:
    teaching_session = _as_dict(game_state.get("teaching_session"))
    teaching_review = _as_dict(game_state.get("teaching_review"))
    if game_state.get("teaching_session") is not None and not isinstance(game_state.get("teaching_session"), dict):
        return False
    if game_state.get("teaching_review") is not None and not isinstance(game_state.get("teaching_review"), dict):
        return False
    if teaching_session and not _game_teaching_session_contract_valid(teaching_session, target_id=target_id):
        return False
    if teaching_review and not _game_teaching_review_contract_valid(teaching_review, target_id=target_id):
        return False
    session_episode_id = str(teaching_session.get("episode_receipt_id") or "")
    review_episode_id = str(teaching_review.get("episode_receipt_id") or "")
    if session_episode_id and review_episode_id:
        return bool(
            session_episode_id == review_episode_id
            and str(teaching_session.get("session_id") or "") == str(teaching_review.get("session_id") or "")
            and str(teaching_session.get("target_id") or "") == str(teaching_review.get("target_id") or "")
        )
    return True


def _game_observation_present(game_state: dict[str, Any]) -> dict[str, Any]:
    target = _as_dict(game_state.get("target"))
    foreground = _as_dict(game_state.get("foreground"))
    scene = _as_dict(game_state.get("scene"))
    classification = _as_dict(game_state.get("classification"))
    configuration = _as_dict(game_state.get("configuration"))
    model = _as_dict(game_state.get("model"))
    teaching_session = _as_dict(game_state.get("teaching_session"))
    teaching_review = _as_dict(game_state.get("teaching_review"))
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
            "mode": str(target.get("mode") or ""),
            "process_names": _string_items(target.get("process_names")),
            "launchers": _string_items(target.get("launchers")),
            "foreground": target.get("foreground") is True,
            "visibility_basis": str(target.get("visibility_basis") or ""),
        },
        "foreground": {
            "supported": foreground.get("supported") is True,
            "available": foreground.get("available") is True,
            "target_match": foreground.get("target_match") is True,
            "process_id": _safe_int(foreground.get("process_id")),
            "process_name": str(foreground.get("process_name") or ""),
            "window_id": _safe_int(foreground.get("window_id")),
            "window_title_included": False,
            "game_verified": foreground.get("game_verified") is True,
            "verification_basis": str(foreground.get("verification_basis") or ""),
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
                "max_age_ms": _safe_float(classification.get("max_age_ms")),
                "inference_ms": _safe_float(classification.get("inference_ms")),
                "device": str(classification.get("device") or ""),
                "backend": str(classification.get("backend") or ""),
                "score_normalization": str(classification.get("score_normalization") or ""),
                "target_id": str(classification.get("target_id") or ""),
                "process_id": _safe_int(classification.get("process_id")),
                "process_name": str(classification.get("process_name") or ""),
                "model_id": str(classification.get("model_id") or ""),
                "scene_id": str(classification.get("scene_id") or ""),
                "authority_receipt_id": str(classification.get("authority_receipt_id") or ""),
            }
            if classification
            else {}
        ),
        "configuration": (
            {
                "source": str(configuration.get("source") or ""),
                "loaded": configuration.get("loaded") is True,
                "enabled": configuration.get("enabled") is True,
                "path": str(configuration.get("path") or ""),
                "fingerprint": str(configuration.get("fingerprint") or ""),
                "environment_override_count": _safe_int(configuration.get("environment_override_count")),
            }
            if configuration
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
        "teaching_review": (
            _game_teaching_review_present(teaching_review)
            if _game_teaching_review_contract_valid(
                teaching_review,
                target_id=str(target.get("id") or ""),
            )
            else {}
        ),
    }


def _game_observer_configuration_contract_valid(configuration: dict[str, Any]) -> bool:
    if not configuration:
        return False
    source = str(configuration.get("source") or "")
    path = str(configuration.get("path") or "")
    fingerprint = str(configuration.get("fingerprint") or "")
    loaded = configuration.get("loaded")
    enabled = configuration.get("enabled")
    override_count = configuration.get("environment_override_count")
    runtime_config_source = source in {"runtime_config", "runtime_config_with_environment_overrides"}
    path_parts = Path(path).parts if path else ()
    return bool(
        source
        in {
            "unconfigured",
            "environment",
            "runtime_config",
            "runtime_config_with_environment_overrides",
            "invalid",
        }
        and isinstance(loaded, bool)
        and isinstance(enabled, bool)
        and isinstance(override_count, int)
        and not isinstance(override_count, bool)
        and 0 <= override_count <= 9
        and (
            not path
            or (len(path) <= 256 and not Path(path).is_absolute() and ".." not in path_parts and ":" not in path)
        )
        and (not fingerprint or _sha256_fingerprint_valid(fingerprint))
        and loaded is bool(fingerprint)
        and (not runtime_config_source or (loaded and bool(path)))
        and (runtime_config_source or (not path and not fingerprint))
    )


def _sha256_fingerprint_valid(value: str) -> bool:
    prefix = "sha256:"
    digest = value.removeprefix(prefix)
    return (
        value.startswith(prefix) and len(digest) == 64 and all(character in "0123456789abcdef" for character in digest)
    )


def _game_teaching_session_contract_valid(teaching: dict[str, Any], *, target_id: str) -> bool:
    governance = _as_dict(teaching.get("governance"))
    governance_valid = bool(
        governance.get("explicit_start_stop_required") is True
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
    return bool(
        teaching.get("kind") == _GAME_TEACHING_SESSION_STATUS_KIND
        and type(teaching.get("version")) is int
        and teaching.get("version") == _GAME_TEACHING_CONTRACT_VERSION
        and governance_valid
        and _game_teaching_session_payload_valid(teaching, target_id=target_id)
    )


def _game_teaching_session_payload_valid(teaching: dict[str, Any], *, target_id: str) -> bool:
    status = teaching.get("status")
    blockers = _bounded_contract_blockers(teaching.get("blockers"), allowed=_GAME_TEACHING_SESSION_BLOCKERS)
    recording_active = teaching.get("recording_active")
    review_required = teaching.get("review_required")
    event_count = _strict_contract_int(teaching.get("event_count"), minimum=0, maximum=_MAX_GAME_TEACHING_EVENTS)
    max_events = _strict_contract_int(teaching.get("max_events"), minimum=0, maximum=_MAX_GAME_TEACHING_EVENTS)
    if (
        not isinstance(status, str)
        or blockers is None
        or not isinstance(recording_active, bool)
        or not isinstance(review_required, bool)
        or event_count is None
        or max_events is None
        or teaching.get("capture_mode") != _GAME_TEACHING_CAPTURE_MODE
    ):
        return False
    empty_status_blockers = {
        "idle": [],
        "recording_error": ["game_teaching_semantic_event_write_failed"],
        "unavailable": ["game_teaching_session_state_invalid"],
    }
    if status in empty_status_blockers:
        return bool(
            blockers == empty_status_blockers[status]
            and recording_active is False
            and review_required is False
            and event_count == 0
            and max_events == 0
            and all(
                teaching.get(field) == ""
                for field in (
                    "session_id",
                    "target_id",
                    "intent_label",
                    "declared_scope",
                    "success_condition",
                    "latest_scene_id",
                    "start_receipt_id",
                    "episode_receipt_id",
                )
            )
            and all(
                teaching.get(field) is None
                for field in ("started_at", "deadline_at", "remaining_seconds", "latest_event_at")
            )
        )
    if status not in {"active", "awaiting_explicit_stop", "finalizing", "stopped"}:
        return False

    session_id = _bounded_contract_text(teaching.get("session_id"), minimum=1, maximum=64)
    teaching_target_id = _bounded_contract_text(teaching.get("target_id"), minimum=1, maximum=64)
    intent_label = _bounded_contract_text(teaching.get("intent_label"), minimum=1, maximum=240)
    declared_scope = _bounded_contract_text(teaching.get("declared_scope"), minimum=1, maximum=500)
    success_condition = _bounded_contract_text(teaching.get("success_condition"), minimum=1, maximum=500)
    start_receipt_id = _bounded_contract_text(teaching.get("start_receipt_id"), minimum=1, maximum=64)
    episode_receipt_id = _bounded_contract_text(teaching.get("episode_receipt_id"), minimum=0, maximum=64)
    latest_scene_id = _bounded_contract_text(teaching.get("latest_scene_id"), minimum=0, maximum=48)
    started_at = _strict_contract_float(
        teaching.get("started_at"),
        minimum=0.0,
        maximum=float(2**53),
    )
    deadline_at = _strict_contract_float(
        teaching.get("deadline_at"),
        minimum=0.0,
        maximum=float(2**53),
    )
    remaining_seconds = _strict_contract_float(
        teaching.get("remaining_seconds"),
        minimum=0.0,
        maximum=_MAX_GAME_TEACHING_DURATION_SECONDS,
    )
    latest_event_at_value = teaching.get("latest_event_at")
    latest_event_at = (
        None
        if latest_event_at_value is None
        else _strict_contract_float(latest_event_at_value, minimum=0.0, maximum=float(2**53))
    )
    if (
        session_id is None
        or not _GAME_TEACHING_SESSION_ID_PATTERN.fullmatch(session_id)
        or teaching_target_id is None
        or teaching_target_id != target_id
        or not _TARGET_ID_PATTERN.fullmatch(teaching_target_id)
        or intent_label is None
        or declared_scope is None
        or success_condition is None
        or start_receipt_id is None
        or not _GAME_TEACHING_START_RECEIPT_ID_PATTERN.fullmatch(start_receipt_id)
        or episode_receipt_id is None
        or latest_scene_id is None
        or started_at is None
        or deadline_at is None
        or remaining_seconds is None
        or latest_event_at_value is not None
        and latest_event_at is None
        or not 30.0 <= deadline_at - started_at <= _MAX_GAME_TEACHING_DURATION_SECONDS
        or max_events < 1
        or event_count > max_events
        or review_required is not True
    ):
        return False
    if event_count == 0:
        if latest_scene_id or latest_event_at_value is not None:
            return False
    elif (
        not _SCENE_ID_PATTERN.fullmatch(latest_scene_id)
        or latest_event_at is None
        or not started_at <= latest_event_at <= deadline_at
    ):
        return False
    if status == "active":
        return bool(
            blockers == []
            and recording_active is True
            and event_count < max_events
            and remaining_seconds > 0.0
            and episode_receipt_id == ""
        )
    if status == "awaiting_explicit_stop":
        if recording_active is not False or episode_receipt_id != "" or len(blockers) != 1:
            return False
        return bool(
            blockers == ["game_teaching_event_limit_reached"]
            and event_count >= max_events
            or blockers == ["game_teaching_duration_limit_reached"]
            and remaining_seconds == 0.0
        )
    if status == "finalizing":
        return bool(
            recording_active is False
            and episode_receipt_id == ""
            and blockers == ["game_teaching_session_finalization_incomplete"]
        )
    return bool(
        recording_active is False
        and blockers == []
        and _GAME_TEACHING_EPISODE_RECEIPT_ID_PATTERN.fullmatch(episode_receipt_id)
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


def _game_teaching_review_contract_valid(review: dict[str, Any], *, target_id: str) -> bool:
    governance = _as_dict(review.get("governance"))
    governance_valid = bool(
        governance.get("source_episode_immutable") is True
        and governance.get("source_digest_required") is True
        and governance.get("semantic_replay_only") is True
        and governance.get("operator_review_required") is True
        and all(
            governance.get(field) is False
            for field in (
                "replay_executes_input",
                "replay_runs_tools",
                "replay_runs_shell",
                "replay_starts_processes",
                "raw_pixels_persisted",
                "window_titles_persisted",
                "keyboard_content_captured",
                "user_mouse_captured",
                "remote_frame_transfer",
                "memory_write",
                "learning_authority",
                "reward_authority",
                "input_execution_authority",
                "automatic_generalization",
                "automatic_skillization",
                "automatic_capability_promotion",
            )
        )
    )
    return bool(
        review.get("kind") == _GAME_TEACHING_EPISODE_REVIEW_STATUS_KIND
        and type(review.get("version")) is int
        and review.get("version") == _GAME_TEACHING_CONTRACT_VERSION
        and governance_valid
        and _game_teaching_review_payload_valid(review, target_id=target_id)
    )


def _game_teaching_review_payload_valid(review: dict[str, Any], *, target_id: str) -> bool:
    status = review.get("status")
    blockers = _bounded_contract_blockers(review.get("blockers"), allowed=_GAME_TEACHING_REVIEW_BLOCKERS)
    event_count = _strict_contract_int(review.get("event_count"), minimum=0, maximum=_MAX_GAME_TEACHING_EVENTS)
    transition_count = _strict_contract_int(
        review.get("scene_transition_count"),
        minimum=0,
        maximum=_MAX_GAME_TEACHING_EVENTS,
    )
    review_revision = _strict_contract_int(review.get("review_revision"), minimum=0, maximum=1_000_000)
    correction_count = _strict_contract_int(
        review.get("correction_count"),
        minimum=0,
        maximum=_MAX_GAME_TEACHING_REVIEW_CORRECTIONS,
    )
    if (
        not isinstance(status, str)
        or blockers is None
        or event_count is None
        or transition_count is None
        or review_revision is None
        or correction_count is None
        or not all(
            isinstance(review.get(field), bool)
            for field in (
                "ready_for_operator_review",
                "replay_ready",
                "operator_review_required",
                "generalization_candidate_ready",
                "generalization_performed",
                "skillization_performed",
            )
        )
        or review.get("generalization_performed") is not False
        or review.get("skillization_performed") is not False
    ):
        return False

    episode_receipt_id = _bounded_contract_text(review.get("episode_receipt_id"), minimum=0, maximum=64)
    episode_digest = _bounded_contract_text(review.get("episode_digest"), minimum=0, maximum=64)
    session_id = _bounded_contract_text(review.get("session_id"), minimum=0, maximum=64)
    review_target_id = _bounded_contract_text(review.get("target_id"), minimum=0, maximum=64)
    intent_label = _bounded_contract_text(review.get("intent_label"), minimum=0, maximum=240)
    declared_scope = _bounded_contract_text(review.get("declared_scope"), minimum=0, maximum=500)
    success_condition = _bounded_contract_text(review.get("success_condition"), minimum=0, maximum=500)
    review_state = _bounded_contract_text(review.get("review_state"), minimum=1, maximum=40)
    review_decision = _bounded_contract_text(review.get("review_decision"), minimum=0, maximum=40)
    latest_review_receipt_id = _bounded_contract_text(
        review.get("latest_review_receipt_id"),
        minimum=0,
        maximum=64,
    )
    if (
        episode_receipt_id is None
        or episode_digest is None
        or session_id is None
        or review_target_id is None
        or intent_label is None
        or declared_scope is None
        or success_condition is None
        or review_state is None
        or review_decision is None
        or latest_review_receipt_id is None
    ):
        return False
    no_source_status_blockers = {
        "awaiting_episode": ["game_teaching_episode_not_found"],
        "invalid_request": ["game_teaching_episode_receipt_id_invalid"],
    }
    if status in no_source_status_blockers:
        return bool(
            blockers == no_source_status_blockers[status]
            and all(
                value == ""
                for value in (
                    episode_receipt_id,
                    episode_digest,
                    session_id,
                    review_target_id,
                    intent_label,
                    declared_scope,
                    success_condition,
                    review_decision,
                    latest_review_receipt_id,
                )
            )
            and event_count == 0
            and transition_count == 0
            and review.get("ready_for_operator_review") is False
            and review.get("replay_ready") is False
            and review_state == "pending_operator_review"
            and review_revision == 0
            and correction_count == 0
            and review.get("operator_review_required") is True
            and review.get("generalization_candidate_ready") is False
        )
    if status not in {
        "correction_required",
        "episode_invalid",
        "operator_accepted",
        "operator_rejected",
        "pending_operator_review",
    }:
        return False
    if (
        not _GAME_TEACHING_EPISODE_RECEIPT_ID_PATTERN.fullmatch(episode_receipt_id)
        or not _SHA256_DIGEST_PATTERN.fullmatch(episode_digest)
        or not _GAME_TEACHING_SESSION_ID_PATTERN.fullmatch(session_id)
        or review_target_id != target_id
        or not _TARGET_ID_PATTERN.fullmatch(review_target_id)
        or not intent_label
        or not declared_scope
        or not success_condition
        or event_count != transition_count
        or review.get("ready_for_operator_review") is not (event_count > 0)
    ):
        return False
    review_state_by_decision = {
        "": "pending_operator_review",
        "accepted": "operator_accepted",
        "needs_correction": "correction_required",
        "rejected": "operator_rejected",
    }
    expected_review_state = review_state_by_decision.get(review_decision)
    if expected_review_state is None or review_state != expected_review_state:
        return False
    if review_decision:
        if (
            not 1 <= review_revision <= 1_000_000
            or not _GAME_TEACHING_REVIEW_RECEIPT_ID_PATTERN.fullmatch(latest_review_receipt_id)
            or review_decision == "needs_correction"
            and correction_count < 1
            or review_decision != "needs_correction"
            and correction_count != 0
        ):
            return False
    elif review_revision != 0 or latest_review_receipt_id or correction_count != 0:
        return False

    replay_ready = review.get("replay_ready") is True
    accepted = review_decision == "accepted" and replay_ready
    if (
        review.get("operator_review_required") is not (not accepted)
        or review.get("generalization_candidate_ready") is not accepted
    ):
        return False
    if replay_ready:
        expected_status_by_decision = {
            "": "pending_operator_review",
            "accepted": "operator_accepted",
            "needs_correction": "correction_required",
            "rejected": "operator_rejected",
        }
        return bool(event_count > 0 and blockers == [] and status == expected_status_by_decision[review_decision])
    return bool(status == "episode_invalid" and blockers)


def _game_teaching_review_present(review: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": str(review.get("status") or ""),
        "episode_receipt_id": str(review.get("episode_receipt_id") or ""),
        "episode_digest": str(review.get("episode_digest") or ""),
        "session_id": str(review.get("session_id") or ""),
        "target_id": str(review.get("target_id") or ""),
        "intent_label": str(review.get("intent_label") or ""),
        "declared_scope": str(review.get("declared_scope") or ""),
        "success_condition": str(review.get("success_condition") or ""),
        "event_count": _safe_int(review.get("event_count")),
        "scene_transition_count": _safe_int(review.get("scene_transition_count")),
        "ready_for_operator_review": review.get("ready_for_operator_review") is True,
        "replay_ready": review.get("replay_ready") is True,
        "review_state": str(review.get("review_state") or ""),
        "review_decision": str(review.get("review_decision") or ""),
        "review_revision": _safe_int(review.get("review_revision")),
        "latest_review_receipt_id": str(review.get("latest_review_receipt_id") or ""),
        "correction_count": _safe_int(review.get("correction_count")),
        "operator_review_required": review.get("operator_review_required") is True,
        "generalization_candidate_ready": review.get("generalization_candidate_ready") is True,
        "generalization_performed": False,
        "skillization_performed": False,
        "blockers": _string_items(review.get("blockers")),
        "governance": {
            "source_episode_immutable": True,
            "source_digest_required": True,
            "semantic_replay_only": True,
            "operator_review_required": True,
            "replay_executes_input": False,
            "memory_write": False,
            "learning_authority": False,
            "reward_authority": False,
            "input_execution_authority": False,
            "automatic_generalization": False,
            "automatic_skillization": False,
            "automatic_capability_promotion": False,
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
