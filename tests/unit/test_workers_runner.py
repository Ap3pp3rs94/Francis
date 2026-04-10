from __future__ import annotations

import json
from pathlib import Path


def _read_record(data_root: Path, task_id: str) -> dict[str, object]:
    record_path = data_root / "tasks" / task_id / "record.json"
    return json.loads(record_path.read_text(encoding="utf-8"))


def _write_record(data_root: Path, task_id: str, record: dict[str, object]) -> None:
    record_path = data_root / "tasks" / task_id / "record.json"
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")


def test_run_workers_once_executes_pending_task(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.agent.delegation import DelegationRequest, create_delegation
    from francis.workers.runner import run_workers

    request = DelegationRequest(
        requester_id="tester",
        capability="plan.create",
        objective="create a short plan",
        inputs={"goal": "ship worker runner"},
    )
    record, err = create_delegation(request)
    assert err is None
    assert record is not None

    exit_code = run_workers(run_once=True, queue="default", kind="default")
    assert exit_code == 0

    final_record = _read_record(data_root, record.task_id)
    assert final_record["status"] == "complete"
    result = final_record.get("result")
    assert isinstance(result, dict)
    assert result.get("ok") is True


def test_run_workers_once_respects_queue_filter(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.agent.delegation import DelegationRequest, create_delegation
    from francis.workers.runner import run_workers

    request_default = DelegationRequest(
        requester_id="tester",
        capability="plan.create",
        objective="default route",
        inputs={"goal": "default queue"},
    )
    request_other = DelegationRequest(
        requester_id="tester",
        capability="plan.create",
        objective="other route",
        inputs={"goal": "other queue"},
    )

    default_record, err = create_delegation(request_default)
    assert err is None
    assert default_record is not None

    other_record, err = create_delegation(request_other)
    assert err is None
    assert other_record is not None

    record = _read_record(data_root, other_record.task_id)
    record["queue"] = "other"
    _write_record(data_root, other_record.task_id, record)

    exit_code = run_workers(
        run_once=True,
        queue="default",
        kind="default",
        concurrency=4,
    )
    assert exit_code == 0

    default_after = _read_record(data_root, default_record.task_id)
    other_after = _read_record(data_root, other_record.task_id)
    assert default_after["status"] == "complete"
    assert other_after["status"] == "pending"
