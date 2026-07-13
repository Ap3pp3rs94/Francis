"""Supervisor-owned Lens desktop perception capture worker.

The worker is executable but fail-closed. It captures only when an active
desktop-sensing lease, an exact approved execution request, and the current
resident-supervisor parent relationship all agree. It does not create or decide
approvals and it does not implement the later semantic situation model.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from francis.kernel.paths import data_dir
from francis.lens.atomic_io import atomic_write_json as _atomic_write_json
from francis.lens.atomic_io import read_json_object as _read_json
from francis.lens.perception import LENS_PERCEPTION_RUNTIME_STATE_KIND, LENS_PERCEPTION_RUNTIME_STATE_VERSION
from francis.lens.perception import _process_is_alive as process_is_alive
from francis.lens.perception_authority import lens_perception_desktop_authority_receipt_status
from francis.lens.perception_capture import (
    DesktopFrame,
    PerceptionCaptureError,
    PerceptionRingBuffer,
    Win32GdiDesktopFrameSource,
)
from francis.lens.perception_execution_contract import (
    LENS_PERCEPTION_EXECUTION_ACTION,
    LENS_PERCEPTION_EXECUTION_REQUEST_KIND,
    lens_perception_execution_approval_status,
)
from francis.lens.situation_model import (
    lens_situation_model_readback,
    write_lens_situation_model_heartbeat,
)

_MAX_SUPERVISOR_STATE_AGE_SECONDS = 5.0
_MAX_SUPERVISOR_FUTURE_SKEW_SECONDS = 0.25
_SUPERVISOR_STALE_GRACE_SECONDS = 10.0
_TRANSIENT_SUPERVISION_BLOCKERS = frozenset({"lens_perception_supervisor_state_stale"})

AuthorityStatusProvider = Callable[[str, int], dict[str, Any]]
ExecutionStatusProvider = Callable[[str, str], dict[str, Any]]
SupervisionStatusProvider = Callable[[int, float], dict[str, Any]]


class DesktopFrameSource(Protocol):
    def capture(self) -> DesktopFrame: ...


@dataclass(frozen=True, slots=True)
class LensPerceptionWorkerConfig:
    authority_receipt_id: str
    execution_approval_id: str
    sample_rate_hz: float = 2.0
    retention_seconds: float = 120.0
    max_frames: int = 240

    def __post_init__(self) -> None:
        if not _safe_identifier(self.authority_receipt_id):
            raise ValueError("desktop_capture_authority_receipt_invalid")
        if not _safe_identifier(self.execution_approval_id):
            raise ValueError("desktop_capture_execution_approval_invalid")
        if not math.isfinite(self.sample_rate_hz) or not 0.5 <= self.sample_rate_hz <= 4.0:
            raise ValueError("lens_perception_sample_rate_invalid")
        if not math.isfinite(self.retention_seconds) or not 60.0 <= self.retention_seconds <= 120.0:
            raise ValueError("lens_perception_retention_invalid")
        if not 1 <= self.max_frames <= 1_200:
            raise ValueError("lens_perception_max_frames_invalid")


class LensPerceptionWorker:
    def __init__(
        self,
        config: LensPerceptionWorkerConfig,
        *,
        frame_source: DesktopFrameSource,
        authority_status: AuthorityStatusProvider | None = None,
        execution_status: ExecutionStatusProvider | None = None,
        supervision_status: SupervisionStatusProvider | None = None,
        clock: Callable[[], float] = time.time,
        monotonic_clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        process_id: int | None = None,
        parent_process_id: int | None = None,
    ) -> None:
        self.config = config
        self.frame_source = frame_source
        self._authority_status = authority_status or _desktop_authority_status
        self._execution_status = execution_status or lens_perception_execution_approval_status
        self._supervision_status = supervision_status or lens_perception_worker_supervision_readback
        self._clock = clock
        self._monotonic = monotonic_clock
        self._sleep = sleeper
        self.process_id = os.getpid() if process_id is None else int(process_id)
        self.parent_process_id = os.getppid() if parent_process_id is None else int(parent_process_id)
        self.status_path = data_dir() / "runtime" / "lens-perception" / "status.json"
        self.ring = PerceptionRingBuffer(
            retention_seconds=config.retention_seconds,
            max_frames=config.max_frames,
            authority_status=self._authority_status,
        )

    def capture_once(self) -> dict[str, Any]:
        observed_at = self._clock()
        authority = self._authority_status(self.config.authority_receipt_id, int(observed_at))
        execution = self._execution_status(
            self.config.execution_approval_id,
            self.config.authority_receipt_id,
        )
        supervision = self._supervision_status(self.parent_process_id, observed_at)
        blockers: list[str] = []
        if authority.get("active") is not True:
            blockers.append("desktop_capture_authority_not_active")
        if execution.get("active") is not True:
            blockers.extend(_string_items(execution.get("blockers")) or ["desktop_capture_execution_not_approved"])
        if supervision.get("active") is not True:
            blockers.extend(_string_items(supervision.get("blockers")) or ["lens_perception_supervision_not_ready"])
        if blockers:
            return self._write_state(
                state="blocked",
                updated_at=observed_at,
                authority=authority,
                execution=execution,
                supervision=supervision,
                ring_buffer=self.ring.readback(now=observed_at),
                blockers=blockers,
                capture_active=False,
            )

        try:
            frame = self.frame_source.capture()
            ring_buffer = self.ring.append(
                frame,
                authority_receipt_id=self.config.authority_receipt_id,
            )
        except PerceptionCaptureError as exc:
            return self._write_state(
                state="blocked",
                updated_at=observed_at,
                authority=authority,
                execution=execution,
                supervision=supervision,
                ring_buffer=self.ring.readback(now=observed_at),
                blockers=[exc.code],
                capture_active=False,
            )
        except (OSError, ValueError):
            return self._write_state(
                state="blocked",
                updated_at=observed_at,
                authority=authority,
                execution=execution,
                supervision=supervision,
                ring_buffer=self.ring.readback(now=observed_at),
                blockers=["lens_perception_frame_persistence_failed"],
                capture_active=False,
            )

        situation_model: dict[str, Any]
        situation_blockers: list[str] = ["lens_situation_model_not_ready"]
        try:
            situation_model = write_lens_situation_model_heartbeat(
                frame=frame,
                ring_buffer=ring_buffer,
                authority_receipt_id=self.config.authority_receipt_id,
                execution_approval_id=self.config.execution_approval_id,
                worker_pid=self.process_id,
                host_pid=_safe_int(supervision.get("observed_pid")),
                supervisor_pid=_safe_int(supervision.get("supervisor_pid")),
                observed_at=max(frame.captured_at, self._clock()),
            )
        except (OSError, ValueError):
            situation_model = lens_situation_model_readback(now=max(frame.captured_at, self._clock()))
            situation_blockers.append("lens_situation_model_heartbeat_write_failed")

        return self._write_state(
            state="running",
            updated_at=frame.captured_at,
            authority=authority,
            execution=execution,
            supervision=supervision,
            ring_buffer=ring_buffer,
            blockers=situation_blockers,
            capture_active=True,
            situation_model=situation_model,
        )

    def run(self, *, max_frames: int = 0, exit_after_seconds: float = 0.0) -> dict[str, Any]:
        if max_frames < 0 or exit_after_seconds < 0.0 or not math.isfinite(exit_after_seconds):
            raise ValueError("lens_perception_worker_run_limit_invalid")
        started = self._monotonic()
        captured = 0
        latest: dict[str, Any] = {}
        supervisor_stale_since: float | None = None
        while True:
            iteration_started = self._monotonic()
            latest = self.capture_once()
            if latest.get("state") != "running":
                blocker_set = frozenset(_string_items(latest.get("blockers")))
                if blocker_set == _TRANSIENT_SUPERVISION_BLOCKERS:
                    retry_observed = self._monotonic()
                    if supervisor_stale_since is None:
                        supervisor_stale_since = retry_observed
                    if retry_observed - supervisor_stale_since < _SUPERVISOR_STALE_GRACE_SECONDS:
                        elapsed = retry_observed - iteration_started
                        self._sleep(max(0.0, (1.0 / self.config.sample_rate_hz) - elapsed))
                        continue
                return {
                    "ok": False,
                    "status": "blocked",
                    "exit_code": 2,
                    "captured_frames": captured,
                    "latest": latest,
                }
            supervisor_stale_since = None
            captured += 1
            if max_frames and captured >= max_frames:
                break
            if exit_after_seconds and self._monotonic() - started >= exit_after_seconds:
                break
            elapsed = self._monotonic() - iteration_started
            self._sleep(max(0.0, (1.0 / self.config.sample_rate_hz) - elapsed))

        stopped_at = self._clock()
        stopped = self._write_state(
            state="stopped",
            updated_at=stopped_at,
            authority=_as_dict(latest.get("capture_authority")),
            execution=_as_dict(latest.get("execution")),
            supervision=_as_dict(latest.get("supervision")),
            ring_buffer=self.ring.readback(now=stopped_at),
            blockers=[],
            capture_active=False,
            situation_model=_as_dict(latest.get("situation_model")),
        )
        return {
            "ok": True,
            "status": "completed",
            "exit_code": 0,
            "captured_frames": captured,
            "latest_running": latest,
            "stopped": stopped,
        }

    def _write_state(
        self,
        *,
        state: str,
        updated_at: float,
        authority: dict[str, Any],
        execution: dict[str, Any],
        supervision: dict[str, Any],
        ring_buffer: dict[str, Any],
        blockers: list[str],
        capture_active: bool,
        situation_model: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        authority_active = authority.get("active") is True
        execution_active = execution.get("active") is True
        supervision_active = supervision.get("active") is True
        heartbeat = situation_model or lens_situation_model_readback(now=updated_at)
        payload = {
            "kind": LENS_PERCEPTION_RUNTIME_STATE_KIND,
            "version": LENS_PERCEPTION_RUNTIME_STATE_VERSION,
            "owner": "lens_supervisor",
            "state": state,
            "pid": self.process_id,
            "host_pid": _safe_int(supervision.get("observed_pid")),
            "supervisor_pid": _safe_int(supervision.get("supervisor_pid")),
            "updated_at": updated_at,
            "sample_rate_hz": self.config.sample_rate_hz,
            "situation_model": {
                "status": str(heartbeat.get("status") or "not_ready"),
                "route": str(heartbeat.get("route") or "/lens/perception/now"),
                "revision": str(heartbeat.get("revision") or ""),
                "updated_at": heartbeat.get("updated_at"),
                "lag_ms": heartbeat.get("lag_ms"),
                "fresh": heartbeat.get("fresh") is True,
                "heartbeat_ready": heartbeat.get("heartbeat_ready") is True,
                "has_current_desktop_state": heartbeat.get("has_current_desktop_state") is True,
                "semantic_comprehension_ready": heartbeat.get("semantic_comprehension_ready") is True,
                "sources": _as_dict(heartbeat.get("sources")),
                "source_blockers": _string_items(heartbeat.get("source_blockers")),
                "blockers": _string_items(heartbeat.get("blockers")),
            },
            "capture": {
                "desktop": {
                    "authority_granted": authority_active,
                    "active": capture_active,
                    "receipt_id": self.config.authority_receipt_id,
                    "source": "desktop_ring_buffer",
                },
                "camera": {
                    "authority_granted": False,
                    "active": False,
                    "receipt_id": "",
                    "source": "",
                },
                "keyboard_content_captured": False,
                "user_mouse_captured": False,
            },
            "capture_authority": authority,
            "execution": execution,
            "supervision": supervision,
            "ring_buffer": ring_buffer,
            "blockers": _dedupe(blockers),
            "governance": {
                "desktop_capture_authority": authority_active,
                "new_sensing_authority": authority_active,
                "execution_authority": execution_active,
                "process_supervision_authority": supervision_active,
                "camera_capture_authority": False,
                "microphone_capture_authority": False,
                "keyboard_capture_authority": False,
                "user_mouse_capture_authority": False,
                "input_execution_authority": False,
                "memory_write": False,
                "raw_pixels_in_status": False,
            },
        }
        _atomic_write_json(self.status_path, payload)
        return payload


def lens_perception_worker_supervision_readback(
    parent_process_id: int,
    now: float,
) -> dict[str, Any]:
    path = data_dir() / "runtime" / "lens-host-supervisor" / "status.json"
    record = _read_json(path)
    supervisor_pid = _safe_int(record.get("supervisor_pid"))
    observed_pid = _safe_int(record.get("observed_pid"))
    updated_at = _timestamp(record.get("updated_at"))
    age_seconds = now - updated_at if updated_at is not None else None
    fresh = bool(
        age_seconds is not None
        and -_MAX_SUPERVISOR_FUTURE_SKEW_SECONDS <= age_seconds <= _MAX_SUPERVISOR_STATE_AGE_SECONDS
    )
    supervisor_alive = process_is_alive(supervisor_pid)
    host_alive = process_is_alive(observed_pid)
    blockers: list[str] = []
    if record.get("kind") != "lens.host.supervisor_state" or record.get("status") != "resident_supervising":
        blockers.append("lens_perception_supervisor_state_invalid")
    if record.get("resident_supervised_runtime") is not True:
        blockers.append("lens_perception_resident_supervision_not_active")
    if record.get("process_supervision_authority") is not True:
        blockers.append("lens_perception_supervision_authority_missing")
    if record.get("supervisor_process_alive") is not True or not supervisor_alive:
        blockers.append("lens_perception_supervisor_process_missing")
    if not host_alive:
        blockers.append("lens_perception_resident_host_process_missing")
    if observed_pid != parent_process_id:
        blockers.append("lens_perception_worker_parent_not_resident_host")
    if not fresh:
        blockers.append("lens_perception_supervisor_state_stale")
    return {
        "status": "ready" if not blockers else "blocked",
        "active": not blockers,
        "state_path": str(path),
        "supervisor_pid": supervisor_pid,
        "observed_pid": observed_pid,
        "parent_process_id": parent_process_id,
        "parent_matches_resident_host": observed_pid == parent_process_id,
        "supervisor_process_alive": supervisor_alive,
        "resident_host_process_alive": host_alive,
        "fresh": fresh,
        "age_ms": round(age_seconds * 1000.0, 3) if age_seconds is not None else None,
        "max_future_skew_ms": int(_MAX_SUPERVISOR_FUTURE_SKEW_SECONDS * 1000),
        "blockers": _dedupe(blockers),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the governed Lens desktop perception worker.")
    parser.add_argument("--authority-receipt-id", required=True)
    parser.add_argument("--execution-approval-id", required=True)
    parser.add_argument("--sample-rate-hz", type=float, default=2.0)
    parser.add_argument("--retention-seconds", type=float, default=120.0)
    parser.add_argument("--max-frames", type=int, default=240)
    parser.add_argument("--exit-after-seconds", type=float, default=0.0)
    args = parser.parse_args(argv)
    config = LensPerceptionWorkerConfig(
        authority_receipt_id=args.authority_receipt_id,
        execution_approval_id=args.execution_approval_id,
        sample_rate_hz=args.sample_rate_hz,
        retention_seconds=args.retention_seconds,
        max_frames=args.max_frames,
    )
    authority_status = _desktop_authority_status
    worker = LensPerceptionWorker(
        config,
        frame_source=Win32GdiDesktopFrameSource(
            authority_receipt_id=config.authority_receipt_id,
            authority_status=authority_status,
        ),
        authority_status=authority_status,
    )
    result = worker.run(exit_after_seconds=args.exit_after_seconds)
    print(json.dumps(_bounded_cli_result(result), indent=2, sort_keys=True))
    return int(result.get("exit_code") or 0)


def _bounded_cli_result(result: dict[str, Any]) -> dict[str, Any]:
    latest = _as_dict(result.get("latest") or result.get("latest_running"))
    return {
        "ok": result.get("ok") is True,
        "status": str(result.get("status") or ""),
        "exit_code": _safe_int(result.get("exit_code")),
        "captured_frames": _safe_int(result.get("captured_frames")),
        "runtime_state": {
            "state": str(latest.get("state") or ""),
            "pid": _safe_int(latest.get("pid")),
            "host_pid": _safe_int(latest.get("host_pid")),
            "supervisor_pid": _safe_int(latest.get("supervisor_pid")),
            "blockers": _string_items(latest.get("blockers")),
        },
        "raw_pixels_in_output": False,
    }


def _desktop_authority_status(receipt_id: str, now: int) -> dict[str, Any]:
    return lens_perception_desktop_authority_receipt_status(receipt_id, now=now)


def _safe_identifier(value: Any) -> bool:
    raw = str(value or "")
    cleaned = raw.strip()
    return bool(
        cleaned
        and raw == cleaned
        and "/" not in cleaned
        and "\\" not in cleaned
        and ".." not in cleaned
        and len(cleaned) <= 180
    )


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _timestamp(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except (ValueError, OverflowError, OSError):
        return None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "LENS_PERCEPTION_EXECUTION_ACTION",
    "LENS_PERCEPTION_EXECUTION_REQUEST_KIND",
    "LensPerceptionWorker",
    "LensPerceptionWorkerConfig",
    "lens_perception_execution_approval_status",
    "lens_perception_worker_supervision_readback",
    "main",
]
