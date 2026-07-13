from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from francis.lens import atomic_io


def test_atomic_write_json_retries_transient_replace_denial(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "status.json"
    path.write_text('{"revision":"old"}\n', encoding="utf-8")
    original_replace = os.replace
    attempts = 0
    sleeps: list[float] = []

    def flaky_replace(source: Path, destination: Path) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError(13, "destination is being read")
        original_replace(source, destination)

    monkeypatch.setattr(atomic_io.os, "replace", flaky_replace)
    monkeypatch.setattr(atomic_io.time, "sleep", sleeps.append)

    atomic_io.atomic_write_json(path, {"revision": "new"})

    assert attempts == 3
    assert len(sleeps) == 2
    assert json.loads(path.read_text(encoding="utf-8")) == {"revision": "new"}
    assert list(tmp_path.glob(".*.tmp")) == []


def test_atomic_write_bytes_reraises_after_bounded_replace_denials(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "status.json"
    path.write_bytes(b"old")
    attempts = 0
    sleeps: list[float] = []

    def denied_replace(_source: Path, _destination: Path) -> None:
        nonlocal attempts
        attempts += 1
        raise PermissionError(13, "destination remains locked")

    monkeypatch.setattr(atomic_io.os, "replace", denied_replace)
    monkeypatch.setattr(atomic_io.time, "sleep", sleeps.append)

    with pytest.raises(PermissionError, match="destination remains locked"):
        atomic_io.atomic_write_bytes(path, b"new")

    assert attempts == 20
    assert len(sleeps) == 19
    assert path.read_bytes() == b"old"
    assert list(tmp_path.glob(".*.tmp")) == []


def test_read_json_object_retries_transient_read_denial(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "status.json"
    path.write_text('{"ready":true}\n', encoding="utf-8")
    original_read_text = Path.read_text
    attempts = 0
    sleeps: list[float] = []

    def flaky_read_text(target: Path, *args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError(13, "file is being replaced")
        return original_read_text(target, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", flaky_read_text)
    monkeypatch.setattr(atomic_io.time, "sleep", sleeps.append)

    assert atomic_io.read_json_object(path) == {"ready": True}
    assert attempts == 3
    assert len(sleeps) == 2
