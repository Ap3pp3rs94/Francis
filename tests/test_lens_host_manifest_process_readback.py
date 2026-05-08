from __future__ import annotations

import json
import os
from pathlib import Path

from francis.lens.host_manifest import lens_host_launch_manifest


def _write_host_state(
    data_root: Path,
    *,
    pid_file_value: int,
    runtime_pid: int,
    runtime_status: str = "foreground_running",
) -> None:
    runtime_root = data_root / "runtime" / "lens-host"
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "lens-host.pid").write_text(str(pid_file_value), encoding="ascii")
    (runtime_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.runtime_state",
                "status": runtime_status,
                "mode": "foreground",
                "pid": runtime_pid,
                "process_alive": True,
                "updated_at": "2026-05-08T22:45:00Z",
            }
        ),
        encoding="utf-8",
    )


def test_lens_host_manifest_rejects_live_pid_with_mismatched_runtime_state(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    live_pid = os.getpid()
    _write_host_state(data_root, pid_file_value=live_pid, runtime_pid=live_pid + 100000)
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    body = lens_host_launch_manifest()
    process = body["process_readback"]

    assert process["status"] == "state_present_process_not_running"
    assert process["pid"] == live_pid
    assert process["state_pid"] == live_pid + 100000
    assert process["state_pid_matches_pid_file"] is False
    assert process["process_alive"] is False
    assert process["process_alive_check"] == "not_attempted_runtime_state_pid_mismatch"
    assert process["blocked_reason"] == "resident_host_process_missing"
    assert body["blocker_groups"]["process_readback"] == ["resident_host_process_missing"]


def test_lens_host_manifest_observes_matching_running_runtime_state(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    live_pid = os.getpid()
    _write_host_state(data_root, pid_file_value=live_pid, runtime_pid=live_pid)
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    body = lens_host_launch_manifest()
    process = body["process_readback"]

    assert process["status"] == "process_observed"
    assert process["pid"] == live_pid
    assert process["state_pid"] == live_pid
    assert process["state_pid_matches_pid_file"] is True
    assert process["process_alive"] is True
    assert process["blocked_reason"] == "resident_host_not_supervised"
    assert body["blocker_groups"]["process_readback"] == ["resident_host_not_supervised"]
