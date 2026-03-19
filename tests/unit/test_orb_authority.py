from __future__ import annotations

from pathlib import Path

from francis_brain.ledger import RunLedger
from francis_core.workspace_fs import WorkspaceFS
import services.hud.app.orb_authority as orb_authority


def _bind_temp_authority_store(monkeypatch, tmp_path: Path) -> Path:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    fs = WorkspaceFS(
        roots=[workspace_root],
        journal_path=(workspace_root / "journals" / "fs.jsonl").resolve(),
    )
    ledger = RunLedger(fs, rel_path="runs/run_ledger.jsonl")
    monkeypatch.setattr(orb_authority, "_workspace_root", workspace_root)
    monkeypatch.setattr(orb_authority, "_repo_root", tmp_path)
    monkeypatch.setattr(orb_authority, "_fs", fs)
    monkeypatch.setattr(orb_authority, "_ledger", ledger)
    return workspace_root


def test_orb_authority_queue_claim_complete(monkeypatch, tmp_path: Path) -> None:
    _bind_temp_authority_store(monkeypatch, tmp_path)

    queued = orb_authority.queue_orb_authority_command(
        kind="mouse.move",
        args={"x": 320, "y": 240},
        reason="Move to the current target.",
    )

    assert queued["status"] == "ok"
    assert queued["command"]["status"] == "queued"
    assert queued["authority"]["pending_count"] == 1

    claimed = orb_authority.claim_next_orb_authority_command(
        authority_live=True,
        idle_seconds=31.0,
        threshold_seconds=30.0,
    )

    assert claimed["status"] == "ok"
    assert claimed["command"]["status"] == "claimed"
    assert claimed["authority"]["state"]["state"] == "francis_authority"
    command_id = claimed["command"]["id"]

    completed = orb_authority.complete_orb_authority_command(
        command_id=command_id,
        status="completed",
        detail="Move completed cleanly.",
        result={"cursor": {"x": 320, "y": 240}},
    )

    assert completed["status"] == "ok"
    assert completed["command"]["status"] == "completed"
    assert completed["authority"]["state"]["live"] is False
    assert completed["authority"]["pending_count"] == 0


def test_orb_authority_state_and_cancel(monkeypatch, tmp_path: Path) -> None:
    _bind_temp_authority_store(monkeypatch, tmp_path)

    orb_authority.queue_orb_authority_command(kind="keyboard.shortcut", args={"keys": ["ctrl", "s"]})
    orb_authority.record_orb_authority_state(
        state="idle_armed",
        eligible=True,
        live=False,
        idle_seconds=12.5,
        threshold_seconds=30.0,
        reason="Away authority is arming.",
    )

    view = orb_authority.get_orb_authority_view()
    assert view["state"]["state"] == "idle_armed"
    assert view["pending_count"] == 1
    assert "armed" in view["summary"].lower()

    canceled = orb_authority.cancel_orb_authority_queue(reason="Panic stop")
    assert canceled["status"] == "ok"
    assert canceled["canceled_count"] == 1
    assert canceled["authority"]["state"]["live"] is False
    assert canceled["authority"]["pending_count"] == 0
