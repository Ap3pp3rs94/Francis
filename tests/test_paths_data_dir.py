from __future__ import annotations

import json
from pathlib import Path


def test_supervised_exec_and_approvals_respect_data_dir_env(monkeypatch, tmp_path: Path) -> None:
    """Ensure data/artifacts writes are anchored under FRANCIS_DATA_DIR when set.

    This prevents surprising writes to the process CWD when running from outside the repo.
    """
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.agent.supervised_exec import run_supervised_exec
    from francis.governance import approvals

    # 1) First call creates an approval request and request artifact.
    res1 = run_supervised_exec(
        {"user_command": "echo hello", "cwd": str(tmp_path)},
        objective="test",
    )
    assert res1["status"] == "needs_approval"
    approval_id = str(res1["approval_id"])

    pending = data_root / "approvals" / "pending" / f"{approval_id}.json"
    assert pending.exists()

    # 2) Approve it, then rerun with the approval id to execute.
    dec = approvals.decide(approval_id, "approve")
    assert dec["ok"] is True

    approved = data_root / "approvals" / "approved" / f"{approval_id}.json"
    assert approved.exists()

    res2 = run_supervised_exec(
        {"user_command": "echo hello", "approval_id": approval_id, "cwd": str(tmp_path)},
        objective="test",
    )
    assert res2["ok"] is True

    art_dir = Path(str(res2["artifact_dir"]))
    assert art_dir.is_dir()
    assert str(art_dir).startswith(str(data_root))

    # Minimal artifact contract
    assert (art_dir / "plan.json").exists()
    assert (art_dir / "stdout.txt").exists()
    assert (art_dir / "stderr.txt").exists()
    assert (art_dir / "result.json").exists()

    result = json.loads((art_dir / "result.json").read_text(encoding="utf-8"))
    assert result.get("exit_code") == 0
