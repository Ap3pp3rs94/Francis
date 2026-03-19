from __future__ import annotations

import services.hud.app.orb as orb_view


def test_get_orb_view_builds_canonical_operator_surface(monkeypatch) -> None:
    snapshot = {
        "control": {"mode": "assist"},
        "current_work": {},
        "objective": {},
        "approvals": {},
        "runs": {},
        "takeover": {"active": True, "session_id": "session-1"},
    }
    actions = {"action_chips": [], "blocked_actions": []}

    monkeypatch.setattr(
        orb_view,
        "build_orb_state",
        lambda **_: {
            "surface": "orb",
            "mode": "assist",
            "posture": "resting",
            "summary": "Ambient",
        },
    )
    monkeypatch.setattr(
        orb_view,
        "get_orb_authority_view",
        lambda: {"surface": "orb_authority", "pending_count": 0},
    )
    monkeypatch.setattr(
        orb_view,
        "get_orb_perception_view",
        lambda include_frame_data=False: {
            "surface": "orb_perception",
            "state": "live",
            "summary": "Active desktop attached.",
        },
    )
    monkeypatch.setattr(
        orb_view,
        "get_current_work_view",
        lambda **_: {
            "surface": "current_work",
            "focus_action": {
                "kind": "repo.tests.request_approval",
                "execute_kind": "repo.tests",
                "args": {"lane": "fast"},
                "enabled": True,
                "label": "Run Fast Checks",
                "reason": "Terminal failure needs verification.",
                "risk_tier": "medium",
                "state": "ready",
            },
            "next_action": {
                "kind": "repo.tests.request_approval",
                "label": "Request Fast Checks Approval",
                "reason": "Tests need operator approval.",
            },
            "next_action_resume": {
                "summary": "Approval is ready to resume the fast-check run.",
            },
            "operator_link": {
                "action_kind": "repo.tests",
                "approval_id": "approval-1",
                "run_id": "run-1",
            },
        },
    )
    monkeypatch.setattr(
        orb_view,
        "get_approval_queue_view",
        lambda **_: {
            "surface": "approval_queue",
            "items": [
                {
                    "id": "approval-1",
                    "requested_action_kind": "repo.tests",
                    "can_execute_after_approval": True,
                }
            ],
        },
    )
    monkeypatch.setattr(
        orb_view,
        "get_execution_journal_view",
        lambda **_: {
            "surface": "execution_journal",
            "items": [
                {
                    "run_id": "run-1",
                    "action_kind": "repo.tests",
                    "detail_summary": "Fast checks failed on the workspace test gate.",
                }
            ],
        },
    )

    orb = orb_view.get_orb_view(snapshot=snapshot, actions=actions, voice={"surface": "voice"})

    operator = orb["operator"]
    assert operator["surface"] == "orb_operator"
    assert operator["state"] == "approval_ready"
    assert operator["focus_kind"] == "repo.tests"
    assert operator["summary"] == "Run Fast Checks | Terminal failure needs verification."
    assert operator["meta"] == "Approval approval-1 is ready. The Orb can approve and continue this move."
    assert operator["receipt_summary"] == "Fast checks failed on the workspace test gate."
    assert operator["controls"]["preview_enabled"] is True
    assert operator["controls"]["preview_kind"] == "repo.tests.request_approval"
    assert operator["controls"]["run_mode"] == "approve_and_run"
    assert operator["controls"]["run_kind"] == "repo.tests"
    assert operator["controls"]["approval_id"] == "approval-1"
    assert operator["controls"]["receipt_available"] is True
    assert operator["controls"]["takeover_active"] is True
    assert operator["controls"]["takeover_session_id"] == "session-1"

    interjection = orb["interjection"]
    assert interjection["surface"] == "orb_interjection"
    assert interjection["state"] == "needed_decision"
    assert interjection["level"] == 2
    assert interjection["reason_kind"] == "approval_ready"
    assert interjection["can_defer"] is False
    assert "Approval approval-1 is ready." in interjection["prompt"]
    assert interjection["controls"]["primary_action"] == "run"
    assert interjection["controls"]["primary_label"] == "Approve + Run"
    assert interjection["controls"]["secondary_action"] == "preview"


def test_get_orb_view_exposes_takeover_desktop_run_contract(monkeypatch) -> None:
    snapshot = {
        "control": {"mode": "away"},
        "current_work": {},
        "objective": {},
        "approvals": {},
        "runs": {},
        "takeover": {"active": True, "session_id": "session-2"},
    }

    monkeypatch.setattr(
        orb_view,
        "build_orb_state",
        lambda **_: {"surface": "orb", "mode": "away", "posture": "acting", "summary": "Active"},
    )
    monkeypatch.setattr(
        orb_view,
        "get_orb_authority_view",
        lambda: {"surface": "orb_authority", "pending_count": 1},
    )
    monkeypatch.setattr(
        orb_view,
        "get_orb_perception_view",
        lambda include_frame_data=False: {"surface": "orb_perception", "state": "live", "summary": "Live"},
    )
    monkeypatch.setattr(
        orb_view,
        "resolve_orb_focus_target",
        lambda: {
            "x": 420,
            "y": 260,
            "display_id": 1,
            "target": {
                "label": "Editor focus point",
                "affordances": [
                    {
                        "kind": "save_shortcut",
                        "label": "Save",
                        "summary": "Press Ctrl+S on the active editor surface.",
                        "command": {
                            "kind": "keyboard.shortcut",
                            "args": {"keys": ["ctrl", "s"]},
                            "reason": "Press Ctrl+S on the active editor surface during Orb authority.",
                        },
                    }
                ],
            },
            "freshness": {"state": "fresh", "age_ms": 120},
        },
    )
    monkeypatch.setattr(
        orb_view,
        "get_current_work_view",
        lambda **_: {
            "surface": "current_work",
            "focus_action": {
                "kind": "orb.authority.queue_focus_click",
                "execute_kind": "orb.authority.queue_focus_click",
                "args": {"button": "left"},
                "enabled": True,
                "label": "Click Focus Point",
                "reason": "Desktop focus needs a click.",
                "risk_tier": "medium",
                "state": "ready",
            },
            "next_action": {"kind": "orb.authority.queue_focus_click", "label": "Click Focus Point"},
            "next_action_resume": {},
            "operator_link": {"action_kind": "orb.authority.queue_focus_click"},
        },
    )
    monkeypatch.setattr(orb_view, "get_approval_queue_view", lambda **_: {"surface": "approval_queue", "items": []})
    monkeypatch.setattr(orb_view, "get_execution_journal_view", lambda **_: {"surface": "execution_journal", "items": []})

    orb = orb_view.get_orb_view(snapshot=snapshot, actions={"action_chips": [], "blocked_actions": []}, voice={"surface": "voice"})

    controls = orb["operator"]["controls"]
    assert controls["desktop_run_enabled"] is True
    assert controls["desktop_run_kind"] == "control.takeover.desktop.enqueue"
    assert controls["desktop_run_args"]["commands"][0]["kind"] == "mouse.click"
    assert controls["desktop_run_args"]["commands"][0]["args"]["x"] == 420
    assert controls["desktop_run_args"]["commands"][0]["args"]["y"] == 260
    assert controls["desktop_run_args"]["commands"][0]["args"]["button"] == "left"
    assert controls["surface_action_enabled"] is True
    assert controls["surface_action_kind"] == "save_shortcut"
    assert controls["surface_action_label"] == "Save"
    assert controls["surface_action_command_kind"] == "keyboard.shortcut"
    assert controls["surface_action_command_args"]["keys"] == ["ctrl", "s"]


def test_get_orb_view_auto_plans_francis_surface_actions_for_takeover(monkeypatch) -> None:
    snapshot = {
        "control": {"mode": "away"},
        "current_work": {},
        "objective": {},
        "approvals": {},
        "runs": {},
        "takeover": {"active": True, "session_id": "session-3"},
    }

    monkeypatch.setattr(
        orb_view,
        "build_orb_state",
        lambda **_: {"surface": "orb", "mode": "away", "posture": "acting", "summary": "Active"},
    )
    monkeypatch.setattr(
        orb_view,
        "get_orb_authority_view",
        lambda: {"surface": "orb_authority", "pending_count": 0},
    )
    monkeypatch.setattr(
        orb_view,
        "get_orb_perception_view",
        lambda include_frame_data=False: {"surface": "orb_perception", "state": "live", "summary": "Live"},
    )
    monkeypatch.setattr(
        orb_view,
        "resolve_orb_focus_target",
        lambda: {
            "x": 520,
            "y": 340,
            "display_id": 1,
            "surface": {"kind": "francis", "label": "Francis surface"},
            "zone": {"kind": "francis_panel", "label": "Francis control panel"},
            "affordances": [
                {
                    "kind": "focus_click",
                    "label": "Focus Click",
                    "summary": "Click the focused Francis control.",
                    "command": {
                        "kind": "mouse.click",
                        "args": {"x": 520, "y": 340, "button": "left", "coordinate_space": "display"},
                        "reason": "Click the focused Francis control during Orb authority.",
                    },
                }
            ],
            "target": {"label": "Francis focus point"},
            "freshness": {"state": "fresh", "age_ms": 120},
        },
    )
    monkeypatch.setattr(
        orb_view,
        "get_current_work_view",
        lambda **_: {
            "surface": "current_work",
            "focus_action": {
                "kind": "forge.promote",
                "execute_kind": "forge.promote",
                "args": {"stage_id": "cap-promote", "approval_id": "approval-cap"},
                "enabled": True,
                "label": "Promote Capability",
                "reason": "Capability is approved and ready to promote.",
                "risk_tier": "medium",
                "state": "ready",
            },
            "next_action": {"kind": "forge.promote", "label": "Promote Capability"},
            "next_action_resume": {},
            "operator_link": {"action_kind": "forge.promote"},
        },
    )
    monkeypatch.setattr(orb_view, "get_approval_queue_view", lambda **_: {"surface": "approval_queue", "items": []})
    monkeypatch.setattr(orb_view, "get_execution_journal_view", lambda **_: {"surface": "execution_journal", "items": []})

    orb = orb_view.get_orb_view(snapshot=snapshot, actions={"action_chips": [], "blocked_actions": []}, voice={"surface": "voice"})

    controls = orb["operator"]["controls"]
    assert controls["desktop_run_enabled"] is True
    assert controls["desktop_run_kind"] == "control.takeover.desktop.enqueue"
    assert controls["desktop_run_args"]["commands"][0]["kind"] == "mouse.click"
    assert controls["desktop_run_args"]["commands"][0]["args"]["x"] == 520
    assert controls["desktop_run_args"]["commands"][0]["args"]["y"] == 340
