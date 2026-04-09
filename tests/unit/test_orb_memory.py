from __future__ import annotations

import json
from pathlib import Path

from services.hud.app import orb_memory


def test_record_orb_chat_execution_receipt_writes_canonical_receipt_and_recent_history(tmp_path: Path) -> None:
    workspace_root = (tmp_path / "workspace").resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)

    payload = orb_memory.record_orb_chat_execution_receipt(
        conversation_id="desk-7",
        user_message="open notepad",
        assistant_reply="I can open Notepad through Start search in Pilot mode.",
        plan={
            "title": "Open Notepad",
            "summary": "Open Notepad through the Windows Start search path.",
            "mode_requirement": "pilot",
            "steps": [
                {"kind": "mouse.click", "args": {"x": 40, "y": 1040}, "reason": "Open Start."},
                {"kind": "keyboard.type", "args": {"text": "notepad"}, "reason": "Search for Notepad."},
            ],
        },
        execution={
            "status": "completed",
            "run_id": "run-chat-7",
            "trace_id": "trace-chat-7",
            "summary": "Open Notepad completed through the Orb shell.",
            "step_count": 2,
            "completed_steps": 2,
            "steps": [
                {
                    "index": 0,
                    "kind": "mouse.click",
                    "status": "ok",
                    "reason": "Open Start.",
                    "execution": {
                        "phase": "click_act",
                        "summary": "Click committed cleanly.",
                        "target": {"x": 40, "y": 1040, "coordinate_space": "screen"},
                    },
                },
                {
                    "index": 1,
                    "kind": "keyboard.type",
                    "status": "ok",
                    "reason": "Search for Notepad.",
                    "execution": {
                        "phase": "type_hold",
                        "summary": "Typing completed cleanly.",
                    },
                },
            ],
            "authority": {
                "state": "completed",
                "summary": "Authority execution completed cleanly.",
            },
            "foreground_window": {
                "title": "Desktop",
                "process": "explorer.exe",
                "pid": 1000,
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
        },
        workspace_root=workspace_root,
    )

    summary = payload["receipt"]["summary"]
    assert summary["receipt_version"] == 2
    assert summary["action_kind"] == "mouse.click"
    assert summary["execution_phase"] == "type_hold"
    assert summary["receipt_flags"]["desktop_fallback"] is True
    assert summary["receipt_context"]["window"]["title"] == "Desktop"
    assert summary["receipt_context"]["desktop_authority"]["active_limitations"][0]["key"] == "elevated_foreground"
    assert summary["replay"]["step_count"] == 2
    assert summary["replay"]["completed_steps"] == 2
    assert summary["replay"]["steps"][0]["kind"] == "mouse.click"
    assert any(card["label"] == "Desktop" for card in summary["presentation_cards"])

    history = payload["history"]
    assert history["conversation_id"] == "desk-7"
    assert history["recent_receipts"][0]["run_id"] == "run-chat-7"
    assert history["recent_receipts"][0]["receipt_kind"] == "orb.chat.execution.completed"
    assert history["recent_receipts"][0]["execution_phase"] == "type_hold"

    ledger_rows = [
        json.loads(line)
        for line in (workspace_root / "runs" / "run_ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ledger_summary = next(
        row["summary"]
        for row in ledger_rows
        if str(row.get("kind", "")).strip() == "orb.chat.execution.completed"
    )
    assert ledger_summary["review_summary"]
    assert ledger_summary["receipt_priority"] >= 700
