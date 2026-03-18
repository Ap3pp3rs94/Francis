from __future__ import annotations

from francis_presence.orb import build_orb_state


def test_orb_state_escalates_to_interjection_on_quarantine_pressure() -> None:
    snapshot = {
        "control": {"mode": "assist", "kill_switch": False},
        "objective": {"label": "Orb test"},
        "approvals": {"pending_count": 1},
        "missions": {"active_count": 1},
        "incidents": {"open_count": 1, "highest_severity": "high"},
        "security": {"quarantine_count": 1, "top_categories": {"policy_bypass": 1}},
        "inbox": {"alert_count": 1},
        "runs": {"last_run": {"phase": "verify"}},
    }
    actions = {"action_chips": [{"kind": "control.panic", "enabled": True}], "blocked_actions": []}
    voice = {"lines": ["Approvals are waiting."]}

    orb = build_orb_state(mode="assist", snapshot=snapshot, actions_payload=actions, voice=voice)

    assert orb["surface"] == "orb"
    assert orb["posture"] == "interjecting"
    assert orb["interjection_level"] == 3
    assert orb["visual"]["pulse_kind"] == "interjection"
    assert orb["state"]["security_quarantines"] == 1


def test_orb_state_keeps_user_cursor_during_pilot_execution() -> None:
    snapshot = {
        "control": {"mode": "pilot", "kill_switch": False},
        "objective": {"label": "Take over"},
        "approvals": {"pending_count": 0},
        "missions": {"active_count": 1},
        "incidents": {"open_count": 0, "highest_severity": "nominal"},
        "security": {"quarantine_count": 0, "top_categories": {}},
        "inbox": {"alert_count": 0},
        "runs": {"last_run": {"phase": "execute"}},
    }
    actions = {"action_chips": [{"kind": "mission.tick", "enabled": True}], "blocked_actions": []}

    orb = build_orb_state(mode="pilot", snapshot=snapshot, actions_payload=actions, voice={})

    assert orb["posture"] == "acting"
    assert orb["operator_cursor"] is False
    assert orb["movement"]["anchor"] == "ambient"
    assert orb["movement"]["profile"] == "focus_orbit"
    assert orb["movement"]["cursor_lock"] is False
    assert orb["movement"]["lead_style"] == "focus_orbit"
    assert orb["movement"]["orbit_bias"] > 0.1
    assert orb["panic_ready"] is False
    assert orb["visual"]["pulse_kind"] == "execution"
    assert orb["handback_visible"] is True
    assert orb["handback"]["ritual"] == "return_to_ambient"
    assert orb["handback"]["return_profile"] == "release_arc"
    assert orb["handback"]["linger_ms"] >= 100
    assert "leaving your mouse under your control" in orb["summary"]


def test_orb_state_becomes_operator_cursor_during_away_execution() -> None:
    snapshot = {
        "control": {"mode": "away", "kill_switch": False},
        "objective": {"label": "Ship task"},
        "approvals": {"pending_count": 0},
        "missions": {"active_count": 1},
        "incidents": {"open_count": 0, "highest_severity": "nominal"},
        "security": {"quarantine_count": 0, "top_categories": {}},
        "inbox": {"alert_count": 0},
        "runs": {"last_run": {"phase": "execute"}},
    }
    actions = {"action_chips": [{"kind": "mission.tick", "enabled": True}], "blocked_actions": []}

    orb = build_orb_state(mode="away", snapshot=snapshot, actions_payload=actions, voice={})

    assert orb["posture"] == "acting"
    assert orb["operator_cursor"] is True
    assert orb["movement"]["anchor"] == "cursor"
    assert orb["movement"]["profile"] == "cursor_ride"
    assert orb["movement"]["cursor_lock"] is True
    assert orb["movement"]["lead_style"] == "predictive_commit"
    assert orb["movement"]["lock_radius"] < 1
    assert "Cursor authority is live" in orb["summary"]


def test_orb_state_enters_panic_when_kill_switch_is_live() -> None:
    snapshot = {
        "control": {"mode": "pilot", "kill_switch": True},
        "objective": {"label": "Stop"},
        "approvals": {"pending_count": 0},
        "missions": {"active_count": 0},
        "incidents": {"open_count": 0, "highest_severity": "nominal"},
        "security": {"quarantine_count": 0, "top_categories": {}},
        "inbox": {"alert_count": 0},
        "runs": {"last_run": {"phase": "verify"}},
    }

    orb = build_orb_state(mode="pilot", snapshot=snapshot, actions_payload={}, voice={})

    assert orb["posture"] == "panic"
    assert orb["panic_ready"] is True
    assert orb["movement"]["profile"] == "guard_orbit"
    assert orb["movement"]["cursor_lock"] is False
    assert orb["visual"]["pulse_kind"] == "panic"


def test_orb_state_exposes_handback_profile_for_ambient_modes() -> None:
    snapshot = {
        "control": {"mode": "assist", "kill_switch": False},
        "objective": {"label": "Return"},
        "approvals": {"pending_count": 0},
        "missions": {"active_count": 0},
        "incidents": {"open_count": 0, "highest_severity": "nominal"},
        "security": {"quarantine_count": 0, "top_categories": {}},
        "inbox": {"alert_count": 0},
        "runs": {"last_run": {"phase": "report"}},
    }

    orb = build_orb_state(mode="assist", snapshot=snapshot, actions_payload={}, voice={})

    assert orb["posture"] == "resting"
    assert orb["operator_cursor"] is False
    assert orb["movement"]["anchor"] == "ambient"
    assert orb["movement"]["profile"] == "ambient_float"
    assert orb["handback"]["ritual"] == "return_to_ambient"
    assert orb["handback"]["anchor"] == "ambient_rest"
    assert orb["handback"]["return_profile"] == "release_arc"
    assert orb["handback"]["duration_ms"] == 1180
    assert orb["handback"]["linger_ms"] == 90
