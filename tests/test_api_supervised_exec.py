from __future__ import annotations

from pathlib import Path


def test_api_supervised_exec_flow(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.governance import approvals

    client = TestClient(create_app())

    # 1) Initial request should require approval.
    r1 = client.post(
        "/operations/supervised-exec/run",
        json={"objective": "test", "user_command": "echo hello", "cwd": str(tmp_path)},
    )
    assert r1.status_code == 200
    res1 = r1.json()
    assert res1["status"] == "needs_approval"
    approval_id = str(res1["approval_id"])

    # 2) Approve then rerun.
    dec = approvals.decide(approval_id, "approve")
    assert dec["ok"] is True

    r2 = client.post(
        "/operations/supervised-exec/run",
        json={
            "objective": "test",
            "user_command": "echo hello",
            "cwd": str(tmp_path),
            "approval_id": approval_id,
        },
    )
    assert r2.status_code == 200
    res2 = r2.json()
    assert res2["ok"] is True

    art = Path(str(res2["artifact_dir"]))
    assert art.exists()
    assert (art / "plan.json").exists()
    assert (art / "stdout.txt").exists()
    assert (art / "stderr.txt").exists()
    assert (art / "result.json").exists()
