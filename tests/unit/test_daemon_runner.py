from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _record_path(data_root: Path, task_id: str) -> Path:
    return data_root / "tasks" / task_id / "record.json"


def _read_record(data_root: Path, task_id: str) -> dict[str, object]:
    return json.loads(_record_path(data_root, task_id).read_text(encoding="utf-8"))


def test_run_daemon_once_executes_pending_task(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.agent.delegation import DelegationRequest, create_delegation
    from francis.daemon.runner import run_daemon

    record, err = create_delegation(
        DelegationRequest(
            requester_id="daemon-test",
            capability="plan.create",
            objective="daemon should run a worker cycle",
            inputs={"goal": "daemon cycle test"},
        )
    )
    assert err is None
    assert record is not None

    exit_code = run_daemon(run_once=True, tick_interval_s=0.01, heartbeat_s=0.01, max_concurrency=2)
    assert exit_code == 0

    final_record = _read_record(data_root, record.task_id)
    assert final_record["status"] == "complete"

    ledger_path = data_root / "conversations" / "ledger" / "ledger.jsonl"
    assert ledger_path.exists()
    assert "daemon started" in ledger_path.read_text(encoding="utf-8")


def test_daemon_launcher_once_from_source_checkout(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.agent.delegation import DelegationRequest, create_delegation

    record, err = create_delegation(
        DelegationRequest(
            requester_id="daemon-launcher",
            capability="plan.create",
            objective="launcher integration",
            inputs={"goal": "launcher path"},
        )
    )
    assert err is None
    assert record is not None

    env = os.environ.copy()
    env["FRANCIS_DATA_DIR"] = str(data_root)
    env.pop("PYTHONPATH", None)

    proc = subprocess.run(
        [sys.executable, "apps/daemon/main.py", "--once"],
        cwd=str(Path(__file__).resolve().parents[2]),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr

    final_record = _read_record(data_root, record.task_id)
    assert final_record["status"] == "complete"
