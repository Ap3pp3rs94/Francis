from __future__ import annotations

import ctypes
import os
import signal
import time
from pathlib import Path
from typing import Any


def process_identity(pid: int) -> dict[str, Any]:
    if type(pid) is not int or pid <= 0:
        return {}
    if os.name == "nt":
        return _windows_process_identity(pid)
    return _proc_process_identity(pid)


def terminate_owned_process(pid: int, *, creation_token: int, timeout_seconds: float = 2.0) -> bool:
    current = process_identity(pid)
    if current.get("creation_token") != creation_token:
        return False
    if os.name == "nt":
        return _windows_terminate(pid, creation_token=creation_token, timeout_seconds=timeout_seconds)
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not process_identity(pid):
            return True
        time.sleep(0.025)
    return False


def _proc_process_identity(pid: int) -> dict[str, Any]:
    proc = Path("/proc") / str(pid)
    try:
        stat = (proc / "stat").read_text(encoding="utf-8")
        closing = stat.rfind(")")
        fields = stat[closing + 2 :].split()
        executable = (proc / "exe").resolve(strict=True)
        command = (proc / "cmdline").read_bytes().split(b"\0")
        return {
            "pid": pid,
            "parent_pid": int(fields[1]),
            "creation_token": int(fields[19]),
            "executable_path": str(executable),
            "command_line": [item.decode("utf-8", errors="replace") for item in command if item],
        }
    except (OSError, ValueError, IndexError):
        return {}


def _windows_process_identity(pid: int) -> dict[str, Any]:
    windll_type = getattr(ctypes, "WinDLL", None)
    if windll_type is None:
        return {}
    from ctypes import wintypes

    kernel32 = windll_type("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    open_process.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    get_times = kernel32.GetProcessTimes
    get_times.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    get_times.restype = wintypes.BOOL
    query_name = kernel32.QueryFullProcessImageNameW
    query_name.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    query_name.restype = wintypes.BOOL
    create_snapshot = kernel32.CreateToolhelp32Snapshot
    create_snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    create_snapshot.restype = wintypes.HANDLE
    process_first = kernel32.Process32FirstW
    process_next = kernel32.Process32NextW

    class ProcessEntry(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    process_first.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    process_first.restype = wintypes.BOOL
    process_next.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    process_next.restype = wintypes.BOOL
    handle = open_process(0x1000, False, pid)
    if not handle:
        return {}
    try:
        creation = wintypes.FILETIME()
        exit_time = wintypes.FILETIME()
        kernel_time = wintypes.FILETIME()
        user_time = wintypes.FILETIME()
        if not get_times(handle, creation, exit_time, kernel_time, user_time):
            return {}
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not query_name(handle, 0, buffer, ctypes.byref(size)):
            return {}
        token = (int(creation.dwHighDateTime) << 32) | int(creation.dwLowDateTime)
        parent_pid = 0
        snapshot = create_snapshot(0x00000002, 0)
        if snapshot and snapshot != wintypes.HANDLE(-1).value:
            try:
                entry = ProcessEntry()
                entry.dwSize = ctypes.sizeof(ProcessEntry)
                present = bool(process_first(snapshot, ctypes.byref(entry)))
                while present:
                    if int(entry.th32ProcessID) == pid:
                        parent_pid = int(entry.th32ParentProcessID)
                        break
                    present = bool(process_next(snapshot, ctypes.byref(entry)))
            finally:
                close_handle(snapshot)
        if parent_pid <= 0:
            return {}
        return {
            "pid": pid,
            "parent_pid": parent_pid,
            "creation_token": token,
            "executable_path": buffer.value,
            "command_line": [],
        }
    finally:
        close_handle(handle)


def _windows_terminate(pid: int, *, creation_token: int, timeout_seconds: float) -> bool:
    windll_type = getattr(ctypes, "WinDLL", None)
    if windll_type is None:
        return False
    kernel32 = windll_type("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(0x0001 | 0x00100000 | 0x1000, False, pid)
    if not handle:
        return not process_identity(pid)
    try:
        if process_identity(pid).get("creation_token") != creation_token:
            return False
        if not kernel32.TerminateProcess(handle, 0):
            return False
        wait_ms = max(1, int(timeout_seconds * 1000))
        return kernel32.WaitForSingleObject(handle, wait_ms) == 0
    finally:
        kernel32.CloseHandle(handle)
