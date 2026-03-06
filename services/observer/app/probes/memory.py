from __future__ import annotations

import os
from ctypes import Structure, byref, c_ulong, c_ulonglong, sizeof
import ctypes


class _MemoryStatusEx(Structure):
    _fields_ = [
        ("dwLength", c_ulong),
        ("dwMemoryLoad", c_ulong),
        ("ullTotalPhys", c_ulonglong),
        ("ullAvailPhys", c_ulonglong),
        ("ullTotalPageFile", c_ulonglong),
        ("ullAvailPageFile", c_ulonglong),
        ("ullTotalVirtual", c_ulonglong),
        ("ullAvailVirtual", c_ulonglong),
        ("sullAvailExtendedVirtual", c_ulonglong),
    ]


def _memory_windows() -> tuple[int, int]:
    status = _MemoryStatusEx()
    status.dwLength = sizeof(_MemoryStatusEx)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(byref(status))
    return int(status.ullTotalPhys), int(status.ullAvailPhys)


def _memory_posix() -> tuple[int, int]:
    page_size = int(os.sysconf("SC_PAGE_SIZE"))
    total_pages = int(os.sysconf("SC_PHYS_PAGES"))
    avail_pages = int(os.sysconf("SC_AVPHYS_PAGES"))
    total = page_size * total_pages
    available = page_size * avail_pages
    return total, available


def collect() -> dict:
    if os.name == "nt":
        total, available = _memory_windows()
    else:
        total, available = _memory_posix()
    used = max(total - available, 0)
    used_percent = (used / total * 100.0) if total else 0.0
    available_percent = (available / total * 100.0) if total else 0.0
    return {
        "total_bytes": total,
        "available_bytes": available,
        "used_bytes": used,
        "used_percent": round(used_percent, 2),
        "available_percent": round(available_percent, 2),
    }
