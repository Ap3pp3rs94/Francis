from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from francis.unreal_presence_selection import unreal_presence_selection_readback
from francis.windows_ctypes import get_last_error, load_win_dll


UNREAL_PRESENCE_RUNTIME_STATUS_KIND = "francis.grounded_presence.unreal_runtime_status"
UNREAL_PRESENCE_RUNTIME_STATUS_SCHEMA_VERSION = "francis.grounded_presence.unreal_runtime_status.v1"
UNREAL_PRESENCE_RUNTIME_STATUS_SCHEMA_PATH = "schemas/grounded_presence_unreal_runtime_status.schema.json"
UNREAL_PRESENCE_STATUS_PATH_ENV = "FRANCIS_UNREAL_PRESENCE_STATUS_PATH"
UNREAL_PRESENCE_RUNTIME_STALE_AFTER_SECONDS = 10
UNREAL_PRESENCE_RUNTIME_MAX_BYTES = 64 * 1024

_AUTHORITY = {
    "francis_core_authoritative": True,
    "grants_execution_authority": False,
    "grants_desktop_authority": False,
    "grants_network_authority": False,
    "grants_memory_write_authority": False,
    "grants_approval_authority": False,
}


def unreal_presence_runtime_readback(
    *,
    selection: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
    now: str | datetime | None = None,
) -> dict[str, Any]:
    values = os.environ if environ is None else environ
    selection_state = (
        dict(selection) if isinstance(selection, Mapping) else unreal_presence_selection_readback(environ=values)
    )
    status_path = _status_path(selection_state, values)
    if not selection_state.get("valid"):
        return _readback(
            status="selection_required",
            status_path=status_path,
            observed=False,
            fresh=False,
            process_alive=False,
            reasons=("unreal_selection_not_confirmed",),
        )
    if status_path is None:
        return _readback(
            status="runtime_not_observed",
            status_path=None,
            observed=False,
            fresh=False,
            process_alive=False,
            reasons=("runtime_status_path_unavailable",),
        )
    if not status_path.is_file():
        return _readback(
            status="runtime_not_observed",
            status_path=status_path,
            observed=False,
            fresh=False,
            process_alive=False,
            reasons=("runtime_status_missing",),
        )

    try:
        if status_path.stat().st_size > UNREAL_PRESENCE_RUNTIME_MAX_BYTES:
            raise ValueError("runtime_status_too_large")
        payload = json.loads(status_path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("runtime_status_object_required")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _readback(
            status="runtime_status_invalid",
            status_path=status_path,
            observed=False,
            fresh=False,
            process_alive=False,
            reasons=(_bounded_reason(exc),),
        )

    reasons = list(_validate_runtime_status(payload, values))
    observed_at = _parse_timestamp(payload.get("observed_at"))
    now_dt = _parse_timestamp(now) if now is not None else datetime.now(UTC)
    age_seconds = None if observed_at is None or now_dt is None else max(0.0, (now_dt - observed_at).total_seconds())
    fresh = age_seconds is not None and age_seconds <= UNREAL_PRESENCE_RUNTIME_STALE_AFTER_SECONDS
    if not fresh:
        reasons.append("runtime_status_stale")
    process_id = _positive_int(payload.get("process_id"))
    process_alive = _process_alive(process_id)
    if not process_alive:
        reasons.append("runtime_process_not_alive")
    render = _mapping(payload.get("render"))
    observed = (
        not reasons
        and render.get("status") == "applied"
        and render.get("authenticated") is True
        and render.get("runtime_observed") is True
    )
    if not observed and not reasons:
        reasons.append("authenticated_render_not_applied")
    status = "runtime_observed" if observed else "runtime_stale" if not fresh else "runtime_not_ready"
    return _readback(
        status=status,
        status_path=status_path,
        observed=observed,
        fresh=fresh,
        process_alive=process_alive,
        reasons=tuple(dict.fromkeys(reasons)),
        payload=payload,
        age_seconds=age_seconds,
        status_digest=_file_sha256(status_path),
    )


def _validate_runtime_status(payload: Mapping[str, Any], values: Mapping[str, str]) -> tuple[str, ...]:
    reasons: list[str] = []
    required = {
        "kind",
        "schema_version",
        "schema_path",
        "observed_at",
        "process_id",
        "adapter_id",
        "session_id",
        "endpoint_id",
        "authentication_key_id",
        "transport",
        "render",
        "intent",
        "technology",
        "authority",
        "stores_presence_payload",
    }
    if set(payload) != required:
        reasons.append("runtime_status_fields_invalid")
    if payload.get("kind") != UNREAL_PRESENCE_RUNTIME_STATUS_KIND:
        reasons.append("runtime_status_kind_invalid")
    if payload.get("schema_version") != UNREAL_PRESENCE_RUNTIME_STATUS_SCHEMA_VERSION:
        reasons.append("runtime_status_schema_version_invalid")
    if payload.get("schema_path") != UNREAL_PRESENCE_RUNTIME_STATUS_SCHEMA_PATH:
        reasons.append("runtime_status_schema_path_invalid")
    if _parse_timestamp(payload.get("observed_at")) is None:
        reasons.append("runtime_status_timestamp_invalid")
    if _positive_int(payload.get("process_id")) <= 0:
        reasons.append("runtime_status_process_id_invalid")

    expected_adapter = str(values.get("FRANCIS_UNREAL_PRESENCE_ADAPTER_ID") or "unreal_presence_1").strip()
    expected_session = str(values.get("FRANCIS_UNREAL_PRESENCE_SESSION_ID") or "francis_unreal_stage1_v1").strip()
    expected_key = str(values.get("FRANCIS_UNREAL_PRESENCE_IPC_KEY_ID") or "").strip()
    if payload.get("adapter_id") != expected_adapter:
        reasons.append("runtime_status_adapter_mismatch")
    if payload.get("session_id") != expected_session:
        reasons.append("runtime_status_session_mismatch")
    if payload.get("endpoint_id") != f"francis.grounded_presence.{expected_adapter}":
        reasons.append("runtime_status_endpoint_mismatch")
    if expected_key and payload.get("authentication_key_id") != expected_key:
        reasons.append("runtime_status_key_mismatch")

    transport = _mapping(payload.get("transport"))
    render = _mapping(payload.get("render"))
    intent = _mapping(payload.get("intent"))
    technology = _mapping(payload.get("technology"))
    if transport.get("configured") is not True:
        reasons.append("runtime_transport_not_configured")
    if _nonnegative_int(transport.get("accepted_message_count")) < 0:
        reasons.append("runtime_transport_count_invalid")
    if render.get("status") not in {"waiting", "queued", "applied"}:
        reasons.append("runtime_render_status_invalid")
    if _nonnegative_int(render.get("sequence")) < 0:
        reasons.append("runtime_render_sequence_invalid")
    if _nonnegative_int(intent.get("last_sequence")) < 0 or _nonnegative_int(intent.get("sent_count")) < 0:
        reasons.append("runtime_intent_count_invalid")
    if technology.get("engine") != "Unreal Engine" or technology.get("engine_version") != "5.8":
        reasons.append("runtime_engine_version_invalid")
    stack = technology.get("active_stack")
    if not isinstance(stack, list) or not stack or not all(isinstance(item, str) and item for item in stack):
        reasons.append("runtime_technology_stack_invalid")
    if payload.get("authority") != _AUTHORITY:
        reasons.append("runtime_authority_invalid")
    if payload.get("stores_presence_payload") is not False:
        reasons.append("runtime_payload_persistence_drift")
    return tuple(dict.fromkeys(reasons))


def _readback(
    *,
    status: str,
    status_path: Path | None,
    observed: bool,
    fresh: bool,
    process_alive: bool,
    reasons: tuple[str, ...],
    payload: Mapping[str, Any] | None = None,
    age_seconds: float | None = None,
    status_digest: str = "",
) -> dict[str, Any]:
    runtime = dict(payload) if isinstance(payload, Mapping) else {}
    return {
        "kind": "francis.grounded_presence.unreal_runtime_readback",
        "schema_version": UNREAL_PRESENCE_RUNTIME_STATUS_SCHEMA_VERSION,
        "schema_path": UNREAL_PRESENCE_RUNTIME_STATUS_SCHEMA_PATH,
        "status": status,
        "observed": observed,
        "fresh": fresh,
        "process_alive": process_alive,
        "status_path": str(status_path) if status_path is not None else "",
        "status_digest": status_digest,
        "age_seconds": round(age_seconds, 3) if age_seconds is not None else None,
        "runtime": runtime,
        "validation": {"ok": not reasons, "reasons": list(reasons)},
        "authority": dict(_AUTHORITY),
        "stores_presence_payload": False,
        "grants_execution_authority": False,
    }


def _status_path(selection: Mapping[str, Any], values: Mapping[str, str]) -> Path | None:
    override = str(values.get(UNREAL_PRESENCE_STATUS_PATH_ENV) or "").strip()
    if override:
        candidate = Path(override)
    else:
        project = _mapping(selection.get("project"))
        project_path = str(project.get("path") or "").strip()
        if not project_path:
            return None
        candidate = Path(project_path).parent / "Saved" / "FrancisPresence" / "runtime_status.json"
    if not candidate.is_absolute() or str(candidate).startswith(("\\\\", "//")):
        return None
    return candidate.resolve(strict=False)


def _process_alive(process_id: int) -> bool:
    if process_id <= 0:
        return False
    if os.name == "nt":
        return _windows_process_alive(process_id)
    try:
        os.kill(process_id, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _windows_process_alive(process_id: int) -> bool:
    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    still_active = 259
    kernel32 = load_win_dll("kernel32")
    open_process = kernel32.OpenProcess
    open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    open_process.restype = wintypes.HANDLE
    get_exit_code = kernel32.GetExitCodeProcess
    get_exit_code.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    get_exit_code.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    handle = open_process(process_query_limited_information, False, process_id)
    if not handle:
        return get_last_error() == 5
    try:
        exit_code = wintypes.DWORD()
        return bool(get_exit_code(handle, ctypes.byref(exit_code))) and exit_code.value == still_active
    finally:
        close_handle(handle)


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _positive_int(value: Any) -> int:
    parsed = _nonnegative_int(value)
    return parsed if parsed > 0 else 0


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool) or isinstance(value, float) and (not math.isfinite(value) or not value.is_integer()):
        return -1
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return -1
    return parsed if parsed >= 0 else -1


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bounded_reason(exc: BaseException) -> str:
    text = str(exc).strip()
    return (
        text[:120]
        if text and all(character.isalnum() or character in "._-" for character in text)
        else type(exc).__name__
    )
