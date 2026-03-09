from francis_presence.triggers import detect_presence_triggers


def test_detect_presence_triggers_captures_rising_pressure() -> None:
    triggers = detect_presence_triggers(
        previous={
            "control": {"mode": "assist", "kill_switch": False},
            "incidents": {"open_count": 0},
            "approvals": {"pending_count": 0},
            "inbox": {"alert_count": 0},
            "missions": {"active_count": 0},
        },
        current={
            "control": {"mode": "pilot", "kill_switch": True},
            "incidents": {"open_count": 2, "highest_severity": "high"},
            "approvals": {"pending_count": 1},
            "inbox": {"alert_count": 3},
            "missions": {"active_count": 1},
        },
    )

    kinds = [trigger["kind"] for trigger in triggers]
    assert "control.kill_switch.engaged" in kinds
    assert "incident.pressure.increased" in kinds
    assert "approvals.pending.increased" in kinds
    assert "inbox.alerts.increased" in kinds
    assert "missions.active.increased" in kinds
