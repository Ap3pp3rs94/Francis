from __future__ import annotations

import json
import os
from pathlib import Path

from conftest import _pytest_session_retention_root, run_pytest_session_retention
from francis.kernel.paths import repo_root


def _write_session(root: Path, name: str, *, now: float, age_days: float, payload: str) -> Path:
    session = root / name
    session.mkdir(parents=True, exist_ok=False)
    marker = session / "marker.txt"
    marker.write_text(payload, encoding="utf-8")
    timestamp = now - (age_days * 24 * 60 * 60)
    os.utime(session, (timestamp, timestamp))
    os.utime(marker, (timestamp, timestamp))
    return session


def test_pytest_session_retention_applies_keep_50_and_age_floor(tmp_path: Path) -> None:
    root = tmp_path / "data" / "test_runs" / "pytest"
    root.mkdir(parents=True, exist_ok=True)
    now = 1_700_000_000.0

    _write_session(root, "not_a_session", now=now, age_days=30, payload="control")

    kept_sessions = []
    for index in range(50):
        kept_sessions.append(
            _write_session(
                root,
                f"session_keep_{index:03d}",
                now=now,
                age_days=30.0 + index,
                payload="k" * 4,
            )
        )
    removed_sessions = []
    for index in range(5):
        removed_sessions.append(
            _write_session(
                root,
                f"session_remove_{index:03d}",
                now=now,
                age_days=100.0 + index,
                payload="r" * 16,
            )
        )

    receipt_path = root / "receipts" / "retention.execution.receipt.test.json"
    payload = run_pytest_session_retention(pytest_root=root, now=now, receipt_path=receipt_path)

    assert payload["deleted_count"] == 5
    assert payload["considered_count"] == 5
    assert payload["retained_by_floor_count"] == 50
    assert receipt_path.exists()
    assert Path(payload["receipt_path"]) == receipt_path.resolve()

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["kind"] == "retention.execution.receipt"
    assert receipt["deleted_count"] == 5
    assert receipt["bytes_freed"] == payload["bytes_freed"]
    assert receipt["scope"] == "pytest_session_retention"
    assert receipt["policy"]["keep_most_recent_sessions"] == 50

    for session in kept_sessions:
        assert session.exists()

    for session in removed_sessions:
        assert not session.exists()

    for entry in sorted(root.iterdir()):
        if entry.name == "receipts":
            continue
        assert entry.name == "not_a_session" or entry.name.startswith("session_")
        if entry.name.startswith("session_"):
            assert entry.exists()

    assert "not_a_session" in [entry.name for entry in root.iterdir()]


def test_pytest_session_retention_root_rejects_path_outside_allowlist(monkeypatch) -> None:
    external_root = repo_root() / "stage6_diagnostics_root"
    monkeypatch.setenv("FRANCIS_PYTEST_SESSION_RETENTION_ROOT", str(external_root))

    try:
        _pytest_session_retention_root()
    except RuntimeError:
        return
    raise AssertionError("Expected retention root override outside policy to be rejected")
