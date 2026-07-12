from __future__ import annotations

import ctypes
import hashlib
import os
import time
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any


WINDOWS_NAMED_MUTEX_MAX_TIMEOUT_MS = 10_000

_WAIT_OBJECT_0 = 0x00000000
_WAIT_ABANDONED = 0x00000080
_WAIT_TIMEOUT = 0x00000102
_WAIT_FAILED = 0xFFFFFFFF


@dataclass(frozen=True, slots=True)
class WindowsNamedMutexAcquireResult:
    acquired: bool
    status: str
    reason: str
    abandoned: bool
    wait_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "acquired": self.acquired,
            "status": self.status,
            "reason": self.reason,
            "abandoned": self.abandoned,
            "wait_ms": self.wait_ms,
        }


class WindowsNamedMutex:
    """Bounded process-shared mutex for one local Francis session boundary."""

    def __init__(self, *, scope: str, timeout_ms: int) -> None:
        normalized_scope = str(scope or "").strip()
        if not normalized_scope or len(normalized_scope) > 512:
            raise ValueError("windows_named_mutex_scope_invalid")
        if (
            not isinstance(timeout_ms, int)
            or isinstance(timeout_ms, bool)
            or timeout_ms < 1
            or timeout_ms > WINDOWS_NAMED_MUTEX_MAX_TIMEOUT_MS
        ):
            raise ValueError("windows_named_mutex_timeout_invalid")
        digest = hashlib.sha256(normalized_scope.encode("utf-8")).hexdigest()[:32]
        self.name = rf"Local\Francis.GroundedPresence.{digest}"
        self.timeout_ms = timeout_ms
        self._handle: int | None = None

    def acquire(self) -> WindowsNamedMutexAcquireResult:
        if os.name != "nt":
            return WindowsNamedMutexAcquireResult(
                acquired=False,
                status="unsupported_platform",
                reason="windows_named_mutex_requires_windows",
                abandoned=False,
                wait_ms=0,
            )
        if self._handle is not None:
            return WindowsNamedMutexAcquireResult(
                acquired=False,
                status="already_acquired",
                reason="windows_named_mutex_already_acquired",
                abandoned=False,
                wait_ms=0,
            )

        kernel32 = _kernel32()
        ctypes.set_last_error(0)
        handle = kernel32.CreateMutexW(None, False, self.name)
        if not handle:
            return WindowsNamedMutexAcquireResult(
                acquired=False,
                status="create_failed",
                reason=f"win32_error_{ctypes.get_last_error()}",
                abandoned=False,
                wait_ms=0,
            )

        started = time.monotonic()
        ctypes.set_last_error(0)
        wait_status = int(kernel32.WaitForSingleObject(handle, self.timeout_ms))
        wait_ms = max(0, round((time.monotonic() - started) * 1_000))
        if wait_status in {_WAIT_OBJECT_0, _WAIT_ABANDONED}:
            self._handle = int(handle)
            abandoned = wait_status == _WAIT_ABANDONED
            return WindowsNamedMutexAcquireResult(
                acquired=True,
                status="acquired_abandoned_owner" if abandoned else "acquired",
                reason="",
                abandoned=abandoned,
                wait_ms=wait_ms,
            )

        kernel32.CloseHandle(handle)
        if wait_status == _WAIT_TIMEOUT:
            reason = "windows_named_mutex_timeout"
            status = "timeout"
        elif wait_status == _WAIT_FAILED:
            reason = f"win32_error_{ctypes.get_last_error()}"
            status = "wait_failed"
        else:
            reason = f"windows_wait_status_{wait_status}"
            status = "wait_failed"
        return WindowsNamedMutexAcquireResult(
            acquired=False,
            status=status,
            reason=reason,
            abandoned=False,
            wait_ms=wait_ms,
        )

    def release(self) -> str:
        handle = self._handle
        self._handle = None
        if handle is None:
            return ""
        kernel32 = _kernel32()
        ctypes.set_last_error(0)
        released = bool(kernel32.ReleaseMutex(handle))
        release_error = "" if released else f"win32_error_{ctypes.get_last_error()}"
        kernel32.CloseHandle(handle)
        return release_error


def _kernel32() -> Any:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.ReleaseMutex.argtypes = [wintypes.HANDLE]
    kernel32.ReleaseMutex.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32
