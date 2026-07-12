from __future__ import annotations

import ctypes

import pytest

from francis import windows_ctypes


def test_windows_ctypes_fails_closed_without_platform_functions(monkeypatch) -> None:
    monkeypatch.delattr(ctypes, "WinDLL", raising=False)
    monkeypatch.delattr(ctypes, "get_last_error", raising=False)
    monkeypatch.delattr(ctypes, "set_last_error", raising=False)

    with pytest.raises(OSError, match="windows_ctypes_requires_windows"):
        windows_ctypes.load_win_dll("kernel32")
    with pytest.raises(OSError, match="windows_ctypes_requires_windows"):
        windows_ctypes.get_last_error()
    with pytest.raises(OSError, match="windows_ctypes_requires_windows"):
        windows_ctypes.set_last_error(0)
