from __future__ import annotations

import json
from pathlib import Path

from francis_brain.ledger import RunLedger
from francis_core.workspace_fs import WorkspaceFS
import services.orchestrator.app.orb_authority as orb_authority


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
    workspace_root = _bind_temp_authority_store(monkeypatch, tmp_path)

    queued = orb_authority.queue_orb_authority_command(
        kind="mouse.move",
        args={"x": 320, "y": 240},
        reason="Move to the current target.",
        grounding={
            "state": "concrete",
            "control_ready": True,
            "surface_kind": "francis",
            "surface_label": "Francis surface",
            "zone_kind": "francis_action_row",
            "zone_label": "Francis action row",
            "target_label": "Francis focus point",
            "confidence": "likely",
            "stability": "settled",
            "window_match": "inside_foreground_window",
            "primary_action_label": "Focus Click",
            "summary": "Concrete Francis action row target. Focus Click is grounded from the Orb.",
            "detail": "Francis focus point is inside the foreground Francis surface and stable enough for precise handoff.",
        },
    )

    assert queued["status"] == "ok"
    assert queued["command"]["status"] == "queued"
    assert queued["command"]["grounding"]["state"] == "concrete"
    assert queued["command"]["policy"]["state"] == "allowed"
    assert queued["command"]["policy"]["scope"] == "navigation"
    assert queued["command"]["execution"]["phase"] == "commit_move"
    assert queued["authority"]["pending_count"] == 1

    claimed = orb_authority.claim_next_orb_authority_command(
        authority_live=True,
        idle_seconds=31.0,
        threshold_seconds=30.0,
    )

    assert claimed["status"] == "ok"
    assert claimed["command"]["status"] == "claimed"
    assert claimed["command"]["execution"]["phase"] == "commit_move"
    assert claimed["authority"]["state"]["state"] == "francis_authority"
    command_id = claimed["command"]["id"]

    completed = orb_authority.complete_orb_authority_command(
        command_id=command_id,
        status="completed",
        detail="Move completed cleanly.",
        result={
            "cursor": {"x": 320, "y": 240},
            "foreground_window": {
                "title": "Francis Lens",
                "process": "electron.exe",
                "pid": 4242,
                "elevated": False,
            },
            "desktop_authority": {
                "mode": "desktop_authority_bounded",
                "summary": "The foreground app is elevated. Non-elevated overlays and input bridges can lose authority on this surface.",
                "activeLimitations": [
                    {
                        "key": "elevated_foreground",
                        "scope": "elevated_apps",
                        "severity": "bounded",
                        "summary": "The foreground app is elevated. Non-elevated overlays and input bridges can lose authority on this surface.",
                        "fallback": "Francis stays resident and documents the limit honestly.",
                    }
                ],
                "fallbackPosture": {
                    "mode": "resident_reinforced_hold",
                    "summary": "Francis stays resident and documents the limit honestly.",
                },
            },
            "execution": {
                "kind": "mouse.move",
                "phase": "commit_move",
                "summary": "Move completed cleanly.",
                "detail": "Francis is physically travelling to the grounded execution point.",
                "target": {"x": 320, "y": 240, "coordinate_space": "screen"},
            },
        },
    )

    assert completed["status"] == "ok"
    assert completed["command"]["status"] == "completed"
    assert completed["command"]["execution"]["phase"] == "commit_move"
    assert completed["authority"]["state"]["live"] is False
    assert completed["authority"]["pending_count"] == 0

    ledger_path = workspace_root / "runs" / "run_ledger.jsonl"
    rows = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    queued_summary = next(
        row.get("summary", {})
        for row in rows
        if str(row.get("kind", "")).strip() == "orb.authority.command.queued"
    )
    claimed_summary = next(
        row.get("summary", {})
        for row in rows
        if str(row.get("kind", "")).strip() == "orb.authority.command.claimed"
    )
    completed_summary = next(
        row.get("summary", {})
        for row in rows
        if str(row.get("kind", "")).strip() == "orb.authority.command.completed"
    )
    assert queued_summary["grounding_state"] == "concrete"
    assert queued_summary["grounding_control_ready"] is True
    assert queued_summary["policy_state"] == "allowed"
    assert queued_summary["policy_scope"] == "navigation"
    assert queued_summary["execution_phase"] == "commit_move"
    assert any(card["label"] == "Grounding" for card in queued_summary["presentation_cards"])
    assert claimed_summary["grounding_state"] == "concrete"
    assert claimed_summary["policy_state"] == "allowed"
    assert claimed_summary["execution_phase"] == "commit_move"
    assert completed_summary["grounding_state"] == "concrete"
    assert completed_summary["policy_state"] == "allowed"
    assert completed_summary["execution_phase"] == "commit_move"
    assert completed_summary["receipt_version"] == 2
    assert completed_summary["receipt_priority"] >= 700
    assert completed_summary["review_summary"] == "mouse.move is completed. Move to the current target. Concrete Francis action row target. Focus Click is grounded from the Orb."
    assert completed_summary["receipt_flags"]["desktop_fallback"] is True
    assert completed_summary["receipt_context"]["window"]["title"] == "Francis Lens"
    assert completed_summary["receipt_context"]["desktop_authority"]["active_limitations"][0]["key"] == "elevated_foreground"
    assert completed_summary["replay"]["step_count"] == 1
    assert any(card["label"] == "Execution" for card in completed_summary["presentation_cards"])
    assert any(card["label"] == "Desktop" for card in completed_summary["presentation_cards"])
    authority_view = orb_authority.get_orb_authority_view()
    assert authority_view["recent"]
    assert authority_view["recent"][0]["summary_text"]
    assert authority_view["recent"][0]["grounding_state"] == "concrete"
    assert authority_view["recent"][0]["policy_scope"] == "navigation"
    assert authority_view["recent"][0]["execution_phase"] == "commit_move"
    assert authority_view["recent"][0]["receipt_flags"]["desktop_fallback"] is True
    assert any(card["label"] == "Grounding" for card in authority_view["recent"][0]["presentation_cards"])


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


def test_orb_authority_preserves_explicit_policy_metadata(monkeypatch, tmp_path: Path) -> None:
    _bind_temp_authority_store(monkeypatch, tmp_path)

    queued = orb_authority.queue_orb_authority_command(
        kind="keyboard.type",
        args={"text": "deploy token", "sensitive": True},
        reason="Sensitive typing requires an operator boundary.",
        policy={
            "state": "approval_required",
            "scope": "sensitive",
            "risk_tier": "high",
            "summary": "Waiting approval before sensitive typing.",
            "detail": "Sensitive typing is held at the policy boundary until approval is granted.",
            "requires_approval": True,
        },
    )

    command = queued["command"]
    assert command["policy"]["state"] == "approval_required"
    assert command["policy"]["scope"] == "sensitive"
    assert command["policy"]["risk_tier"] == "high"
    assert command["policy"]["requires_approval"] is True
    assert command["policy"]["summary"] == "Waiting approval before sensitive typing."
