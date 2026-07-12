from __future__ import annotations

import ctypes
from typing import Any


def load_win_dll(name: str) -> Any:
    loader = getattr(ctypes, "WinDLL", None)
    if not callable(loader):
        raise OSError("windows_ctypes_requires_windows")
    return loader(name, use_last_error=True)


def get_last_error() -> int:
    reader = getattr(ctypes, "get_last_error", None)
    if not callable(reader):
        raise OSError("windows_ctypes_requires_windows")
    return int(reader())


def set_last_error(value: int) -> None:
    writer = getattr(ctypes, "set_last_error", None)
    if not callable(writer):
        raise OSError("windows_ctypes_requires_windows")
    writer(int(value))
