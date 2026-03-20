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
    monkeypatch.setattr(orb_view, "resolve_orb_focus_target", lambda: None)
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
    assert operator["target_cue"] is None
    assert operator["receipt_cue"]["state"] == "weak"
    assert operator["receipt_cue"]["title"] == "Receipt Grounding"
    assert "no concrete target cue is grounded now" in operator["receipt_cue"]["summary"].lower()

    interjection = orb["interjection"]
    assert interjection["surface"] == "orb_interjection"
    assert interjection["state"] == "needed_decision"
    assert interjection["level"] == 2
    assert interjection["reason_kind"] == "approval_ready"
    assert interjection["can_defer"] is False
    assert "Approval approval-1 is ready." in interjection["prompt"]
    assert interjection["target_cue"] is None
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
    assert orb["operator"]["target_cue"]["state"] == "weak"
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


def test_get_orb_view_carries_concrete_target_cue_into_interjection(monkeypatch) -> None:
    snapshot = {
        "control": {"mode": "assist"},
        "current_work": {},
        "objective": {},
        "approvals": {},
        "runs": {},
        "takeover": {"active": False, "session_id": ""},
    }
    actions = {"action_chips": [], "blocked_actions": []}

    monkeypatch.setattr(
        orb_view,
        "build_orb_state",
        lambda **_: {"surface": "orb", "mode": "assist", "posture": "resting", "summary": "Ambient"},
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
            "x": 612,
            "y": 402,
            "display_id": 1,
            "surface": {"kind": "francis", "label": "Francis surface"},
            "zone": {"kind": "francis_workspace", "label": "Francis workspace panel"},
            "affordances": [
                {
                    "kind": "focus_click",
                    "label": "Focus Click",
                    "summary": "Click the focused Francis control.",
                    "command": {
                        "kind": "mouse.click",
                        "args": {"x": 612, "y": 402, "button": "left", "coordinate_space": "display"},
                        "reason": "Click the focused Francis control during Orb authority.",
                    },
                }
            ],
            "target": {
                "label": "Francis focus point",
                "confidence": "likely",
                "stability": {"state": "settled"},
                "window": {"in_bounds": True},
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

    assert orb["operator"]["target_cue"]["state"] == "concrete"
    assert orb["operator"]["receipt_cue"]["state"] == "concrete"
    assert orb["operator"]["receipt_cue"]["control_ready"] is True
    assert orb["interjection"]["target_cue"]["state"] == "concrete"
    assert orb["interjection"]["target_cue"]["control_ready"] is True


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
            "zone": {"kind": "francis_workspace", "label": "Francis workspace panel"},
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
            "target": {
                "label": "Francis focus point",
                "confidence": "likely",
                "stability": {"state": "settled"},
                "window": {"in_bounds": True},
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
    assert orb["operator"]["target_cue"]["state"] == "concrete"
    assert orb["operator"]["target_cue"]["control_ready"] is True
    assert controls["desktop_run_enabled"] is True
    assert controls["desktop_run_kind"] == "control.takeover.desktop.enqueue"
    assert controls["desktop_run_args"]["commands"][0]["kind"] == "mouse.click"
    assert controls["desktop_run_args"]["commands"][0]["args"]["x"] == 520
    assert controls["desktop_run_args"]["commands"][0]["args"]["y"] == 340


def test_get_orb_view_auto_plans_repo_tests_request_on_francis_surface(monkeypatch) -> None:
    snapshot = {
        "control": {"mode": "away"},
        "current_work": {},
        "objective": {},
        "approvals": {},
        "runs": {},
        "takeover": {"active": True, "session_id": "session-4"},
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
            "x": 612,
            "y": 402,
            "display_id": 1,
            "surface": {"kind": "francis", "label": "Francis surface"},
            "zone": {"kind": "francis_workspace", "label": "Francis workspace panel"},
            "affordances": [
                {
                    "kind": "focus_click",
                    "label": "Focus Click",
                    "summary": "Click the focused Francis control.",
                    "command": {
                        "kind": "mouse.click",
                        "args": {"x": 612, "y": 402, "button": "left", "coordinate_space": "display"},
                        "reason": "Click the focused Francis control during Orb authority.",
                    },
                }
            ],
            "target": {
                "label": "Francis focus point",
                "confidence": "likely",
                "stability": {"state": "settled"},
                "window": {"in_bounds": True},
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
                "kind": "repo.tests.request_approval",
                "execute_kind": "repo.tests.request_approval",
                "args": {"lane": "fast"},
                "enabled": True,
                "label": "Request Fast Checks Approval",
                "reason": "Tests need operator approval.",
                "risk_tier": "low",
                "state": "ready",
            },
            "next_action": {"kind": "repo.tests.request_approval", "label": "Request Fast Checks Approval"},
            "next_action_resume": {},
            "operator_link": {"action_kind": "repo.tests"},
        },
    )
    monkeypatch.setattr(orb_view, "get_approval_queue_view", lambda **_: {"surface": "approval_queue", "items": []})
    monkeypatch.setattr(orb_view, "get_execution_journal_view", lambda **_: {"surface": "execution_journal", "items": []})

    orb = orb_view.get_orb_view(snapshot=snapshot, actions={"action_chips": [], "blocked_actions": []}, voice={"surface": "voice"})

    controls = orb["operator"]["controls"]
    assert orb["operator"]["target_cue"]["state"] == "concrete"
    assert controls["desktop_run_enabled"] is True
    assert controls["desktop_run_kind"] == "control.takeover.desktop.enqueue"
    assert controls["desktop_run_args"]["commands"][0]["kind"] == "mouse.click"
    assert controls["desktop_run_args"]["commands"][0]["args"]["x"] == 612
    assert controls["desktop_run_args"]["commands"][0]["args"]["y"] == 402


def test_get_orb_view_auto_plans_navigation_open_on_francis_surface(monkeypatch) -> None:
    snapshot = {
        "control": {"mode": "away"},
        "current_work": {},
        "objective": {},
        "approvals": {},
        "runs": {},
        "takeover": {"active": True, "session_id": "session-nav"},
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
            "x": 188,
            "y": 300,
            "display_id": 1,
            "surface": {"kind": "francis", "label": "Francis surface"},
            "zone": {"kind": "francis_navigation", "label": "Francis navigation rail"},
            "affordances": [
                {
                    "kind": "open_key",
                    "label": "Open",
                    "summary": "Press Enter on the selected Francis navigation control.",
                    "command": {
                        "kind": "keyboard.key",
                        "args": {"key": "enter"},
                        "reason": "Press Enter on the selected Francis navigation control during Orb authority.",
                    },
                }
            ],
            "target": {
                "label": "Francis navigation selection",
                "confidence": "likely",
                "stability": {"state": "settled"},
                "window": {"in_bounds": True},
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
                "kind": "control.takeover.confirm",
                "execute_kind": "control.takeover.confirm",
                "args": {"session_id": "session-nav"},
                "enabled": True,
                "label": "Confirm Takeover",
                "reason": "Navigation selection is ready to open.",
                "risk_tier": "low",
                "state": "ready",
            },
            "next_action": {"kind": "control.takeover.confirm", "label": "Confirm Takeover"},
            "next_action_resume": {},
            "operator_link": {"action_kind": "control.takeover.confirm"},
        },
    )
    monkeypatch.setattr(orb_view, "get_approval_queue_view", lambda **_: {"surface": "approval_queue", "items": []})
    monkeypatch.setattr(orb_view, "get_execution_journal_view", lambda **_: {"surface": "execution_journal", "items": []})

    orb = orb_view.get_orb_view(snapshot=snapshot, actions={"action_chips": [], "blocked_actions": []}, voice={"surface": "voice"})

    controls = orb["operator"]["controls"]
    assert orb["operator"]["target_cue"]["state"] == "concrete"
    assert controls["desktop_run_enabled"] is True
    assert controls["desktop_run_kind"] == "control.takeover.desktop.enqueue"
    assert controls["desktop_run_args"]["commands"][0]["kind"] == "keyboard.key"
    assert controls["desktop_run_args"]["commands"][0]["args"]["key"] == "enter"


def test_get_orb_view_auto_plans_reject_on_francis_footer_controls(monkeypatch) -> None:
    snapshot = {
        "control": {"mode": "away"},
        "current_work": {},
        "objective": {},
        "approvals": {},
        "runs": {},
        "takeover": {"active": True, "session_id": "session-reject"},
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
            "x": 622,
            "y": 516,
            "display_id": 1,
            "surface": {"kind": "francis", "label": "Francis surface"},
            "zone": {"kind": "francis_footer_actions", "label": "Francis footer actions"},
            "affordances": [
                {
                    "kind": "cancel_key",
                    "label": "Cancel",
                    "summary": "Press Escape on the Francis footer action controls.",
                    "command": {
                        "kind": "keyboard.key",
                        "args": {"key": "escape"},
                        "reason": "Press Escape on the Francis footer action controls during Orb authority.",
                    },
                }
            ],
            "target": {
                "label": "Francis rejection control",
                "confidence": "likely",
                "stability": {"state": "settled"},
                "window": {"in_bounds": True},
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
                "kind": "control.remote.approval.reject",
                "execute_kind": "control.remote.approval.reject",
                "args": {"approval_id": "approval-9", "reason": "Scope is too broad."},
                "enabled": True,
                "label": "Reject Approval",
                "reason": "The approval needs an explicit rejection path.",
                "risk_tier": "medium",
                "state": "ready",
            },
            "next_action": {"kind": "control.remote.approval.reject", "label": "Reject Approval"},
            "next_action_resume": {},
            "operator_link": {"action_kind": "control.remote.approval.reject"},
        },
    )
    monkeypatch.setattr(orb_view, "get_approval_queue_view", lambda **_: {"surface": "approval_queue", "items": []})
    monkeypatch.setattr(orb_view, "get_execution_journal_view", lambda **_: {"surface": "execution_journal", "items": []})

    orb = orb_view.get_orb_view(snapshot=snapshot, actions={"action_chips": [], "blocked_actions": []}, voice={"surface": "voice"})

    controls = orb["operator"]["controls"]
    assert orb["operator"]["target_cue"]["state"] == "concrete"
    assert controls["desktop_run_enabled"] is True
    assert controls["desktop_run_kind"] == "control.takeover.desktop.enqueue"
    assert controls["desktop_run_args"]["commands"][0]["kind"] == "keyboard.key"
    assert controls["desktop_run_args"]["commands"][0]["args"]["key"] == "escape"


def test_get_orb_view_does_not_auto_plan_transient_francis_targets(monkeypatch) -> None:
    snapshot = {
        "control": {"mode": "away"},
        "current_work": {},
        "objective": {},
        "approvals": {},
        "runs": {},
        "takeover": {"active": True, "session_id": "session-5"},
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
            "x": 612,
            "y": 402,
            "display_id": 1,
            "surface": {"kind": "francis", "label": "Francis surface"},
            "zone": {"kind": "francis_workspace", "label": "Francis workspace panel"},
            "affordances": [
                {
                    "kind": "focus_click",
                    "label": "Focus Click",
                    "summary": "Click the focused Francis control.",
                    "command": {
                        "kind": "mouse.click",
                        "args": {"x": 612, "y": 402, "button": "left", "coordinate_space": "display"},
                        "reason": "Click the focused Francis control during Orb authority.",
                    },
                }
            ],
            "target": {
                "label": "Francis focus point",
                "confidence": "low",
                "stability": {"state": "transient"},
                "window": {"in_bounds": True},
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
                "kind": "repo.tests.request_approval",
                "execute_kind": "repo.tests.request_approval",
                "args": {"lane": "fast"},
                "enabled": True,
                "label": "Request Fast Checks Approval",
                "reason": "Tests need operator approval.",
                "risk_tier": "low",
                "state": "ready",
            },
            "next_action": {"kind": "repo.tests.request_approval", "label": "Request Fast Checks Approval"},
            "next_action_resume": {},
            "operator_link": {"action_kind": "repo.tests"},
        },
    )
    monkeypatch.setattr(orb_view, "get_approval_queue_view", lambda **_: {"surface": "approval_queue", "items": []})
    monkeypatch.setattr(orb_view, "get_execution_journal_view", lambda **_: {"surface": "execution_journal", "items": []})

    orb = orb_view.get_orb_view(snapshot=snapshot, actions={"action_chips": [], "blocked_actions": []}, voice={"surface": "voice"})

    controls = orb["operator"]["controls"]
    assert orb["operator"]["target_cue"]["state"] == "weak"
    assert controls["desktop_run_enabled"] is False


def test_build_orb_chat_reply_answers_status_directly(monkeypatch) -> None:
    conversation = {
        "conversation_id": "default",
        "recent_turns": [],
        "messages": [],
        "short_term_memory": {"message_count": 0, "window_count": 0},
        "long_term_memory": {"summary": ""},
    }

    monkeypatch.setattr(orb_view, "build_lens_snapshot", lambda: {"control": {"mode": "assist"}})
    monkeypatch.setattr(orb_view, "get_lens_actions", lambda max_actions=4: {"action_chips": []})
    monkeypatch.setattr(orb_view, "build_operator_presence", lambda **_: {"surface": "voice"})
    monkeypatch.setattr(orb_view, "build_orb_chat_history", lambda conversation_id="default": conversation)
    monkeypatch.setattr(orb_view, "append_orb_turn", lambda **kwargs: conversation)
    monkeypatch.setattr(orb_view, "refresh_orb_long_term_memory", lambda **kwargs: conversation["long_term_memory"])
    monkeypatch.setattr(
        orb_view,
        "get_orb_view",
        lambda **_: {
            "mode": "assist",
            "posture": "resting",
            "summary": "Francis is ambient on the desktop.",
            "authority": {
                "summary": "No Orb authority commands are waiting. Human control remains primary.",
                "recent": [],
            },
            "operator": {
                "summary": "Run Fast Checks | Terminal failure needs verification.",
                "meta": "Approval approval-1 is ready. The Orb can approve and continue this move.",
                "receipt_summary": "Fast checks failed on the workspace test gate.",
                "controls": {"run_enabled": True, "run_mode": "approve_and_run"},
            },
            "interjection": {"state": "idle"},
            "thought": {"visible": False},
        },
    )
    monkeypatch.setattr(
        orb_view,
        "get_orb_perception_view",
        lambda include_frame_data=False: {
            "state": "live",
            "summary": "Francis sees the active terminal surface.",
            "detail_summary": "Cursor is over the terminal input line.",
        },
    )
    monkeypatch.setattr(orb_view, "chat", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("chat should not be called")))

    payload = orb_view.build_orb_chat_reply(message="status?")

    assert payload["status"] == "ok"
    assert payload["reply_kind"] == "direct"
    assert payload["plan"] is None
    assert payload["memory"]["conversation_id"] == "default"
    assert "Mode is assist and posture is resting." in payload["reply"]
    assert "Current move: Run Fast Checks | Terminal failure needs verification." in payload["reply"]
    assert "Human control remains primary." in payload["reply"]


def test_build_orb_chat_reply_answers_receipt_directly(monkeypatch) -> None:
    conversation = {
        "conversation_id": "default",
        "recent_turns": [],
        "messages": [],
        "short_term_memory": {"message_count": 0, "window_count": 0},
        "long_term_memory": {"summary": ""},
    }

    monkeypatch.setattr(orb_view, "build_lens_snapshot", lambda: {"control": {"mode": "assist"}})
    monkeypatch.setattr(orb_view, "get_lens_actions", lambda max_actions=4: {"action_chips": []})
    monkeypatch.setattr(orb_view, "build_operator_presence", lambda **_: {"surface": "voice"})
    monkeypatch.setattr(orb_view, "build_orb_chat_history", lambda conversation_id="default": conversation)
    monkeypatch.setattr(orb_view, "append_orb_turn", lambda **kwargs: conversation)
    monkeypatch.setattr(orb_view, "refresh_orb_long_term_memory", lambda **kwargs: conversation["long_term_memory"])
    monkeypatch.setattr(
        orb_view,
        "get_orb_view",
        lambda **_: {
            "mode": "assist",
            "posture": "resting",
            "summary": "Francis is ambient on the desktop.",
            "authority": {
                "summary": "No Orb authority commands are waiting. Human control remains primary.",
                "recent": [
                    {
                        "summary_text": "mouse.click is completed. Concrete Francis footer actions target.",
                    }
                ],
            },
            "operator": {
                "summary": "Reject Approval | The approval needs an explicit rejection path.",
                "receipt_summary": "Receipt run-9 is grounded by a concrete francis footer actions.",
                "receipt_cue": {
                    "summary": "Receipt run-9 is grounded by a concrete francis footer actions.",
                },
                "controls": {"run_enabled": False, "run_mode": "execute"},
            },
            "interjection": {"state": "idle"},
            "thought": {"visible": False},
        },
    )
    monkeypatch.setattr(
        orb_view,
        "get_orb_perception_view",
        lambda include_frame_data=False: {
            "state": "live",
            "summary": "Francis sees the active Francis control surface.",
            "detail_summary": "Cursor is over the footer actions row.",
        },
    )
    monkeypatch.setattr(orb_view, "chat", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("chat should not be called")))

    payload = orb_view.build_orb_chat_reply(message="latest receipt")

    assert payload["status"] == "ok"
    assert payload["reply_kind"] == "direct"
    assert "Receipt run-9 is grounded by a concrete francis footer actions." in payload["reply"]


def test_build_orb_chat_reply_returns_planner_payload_with_memory(monkeypatch) -> None:
    conversation = {
        "conversation_id": "desk-1",
        "recent_turns": [{"role": "assistant", "content": "Previous Francis reply.", "kind": "chat"}],
        "messages": [{"role": "assistant", "content": "Previous Francis reply.", "kind": "chat"}],
        "short_term_memory": {"message_count": 1, "window_count": 1},
        "long_term_memory": {
            "summary": "The user likes visible desktop actions.",
            "user_preferences": ["Keep the Orb concise."],
            "operator_context": ["Focus on governed execution."],
            "open_threads": ["Launch tools through visible Windows paths."],
        },
    }
    captured: dict[str, object] = {}
    appended: list[dict[str, object]] = []

    monkeypatch.setattr(
        orb_view,
        "build_lens_snapshot",
        lambda: {
            "control": {"mode": "assist"},
            "runs": {"last_run": {"run_id": "run-42", "summary": "waiting"}},
            "current_work": {"surface": "current_work"},
            "objective": {"label": "Desk help"},
        },
    )
    monkeypatch.setattr(orb_view, "get_lens_actions", lambda max_actions=4: {"action_chips": []})
    monkeypatch.setattr(orb_view, "build_operator_presence", lambda **_: {"surface": "voice"})
    monkeypatch.setattr(orb_view, "build_orb_chat_history", lambda conversation_id="desk-1": conversation)
    monkeypatch.setattr(orb_view, "append_orb_turn", lambda **kwargs: appended.append(kwargs) or conversation)
    monkeypatch.setattr(
        orb_view,
        "refresh_orb_long_term_memory",
        lambda **kwargs: conversation["long_term_memory"],
    )
    monkeypatch.setattr(
        orb_view,
        "get_orb_view",
        lambda **_: {
            "mode": "assist",
            "posture": "resting",
            "summary": "Francis is ambient on the desktop.",
            "detail": "Operator loop is waiting for a desktop instruction.",
            "authority": {"summary": "Human control remains primary.", "recent": []},
            "operator": {"summary": "No current move.", "controls": {"run_enabled": False, "run_mode": "execute"}},
            "interjection": {"state": "idle"},
            "thought": {"visible": False},
        },
    )
    monkeypatch.setattr(
        orb_view,
        "get_orb_perception_view",
        lambda include_frame_data=False: {
            "state": "live",
            "summary": "Francis sees the desktop.",
            "detail_summary": "Cursor is over the editor.",
            "window": {"title": "Editor"},
        },
    )
    monkeypatch.setattr(
        orb_view,
        "build_orb_chat_plan",
        lambda **kwargs: captured.update(kwargs) or {
            "reply": "I can open Notepad through Start search in Pilot mode.",
            "thought": "Ready to open Notepad through Start search.",
            "planner": "ollama",
            "plan": {
                "title": "Open Notepad",
                "summary": "Open Notepad through the Windows Start search path.",
                "mode_requirement": "pilot",
                "reasoning": [
                    "Use Start search so the action stays visible.",
                    "Keyboard navigation is sufficient here.",
                ],
                "steps": [
                    {"kind": "keyboard.shortcut", "args": {"keys": ["ctrl", "esc"]}, "reason": "Open Start.", "delay_ms": 180},
                    {"kind": "keyboard.type", "args": {"text": "notepad"}, "reason": "Search for Notepad.", "delay_ms": 180},
                    {"kind": "keyboard.key", "args": {"key": "enter"}, "reason": "Open Notepad.", "delay_ms": 220},
                ],
            },
        },
    )

    payload = orb_view.build_orb_chat_reply(message="open notepad", conversation_id="desk-1")

    assert payload["status"] == "ok"
    assert payload["reply_kind"] == "planner"
    assert payload["plan"]["title"] == "Open Notepad"
    assert payload["execution"]["auto_execute"] is False
    assert payload["planner"]["provider"] == "ollama"
    assert payload["memory"]["conversation_id"] == "desk-1"
    assert payload["memory"]["long_term"]["summary"] == "The user likes visible desktop actions."
    assert payload["thought"]["summary"] == "Ready to open Notepad through Start search."
    assert captured["short_term_messages"] == conversation["recent_turns"]
    assert captured["long_term_memory"] == conversation["long_term_memory"]
    assert captured["orb_context"]["run_state"]["run_id"] == "run-42"
    assert len(appended) == 2
