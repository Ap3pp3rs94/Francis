from francis_presence.narrator import compose_operator_presence


def test_operator_presence_includes_notification_and_triggers() -> None:
    payload = compose_operator_presence(
        mode="away",
        snapshot={
            "workspace_root": "D:/francis/workspace",
            "control": {"mode": "away", "kill_switch": False},
            "incidents": {"open_count": 2, "highest_severity": "high"},
            "approvals": {"pending_count": 1},
            "missions": {"active_count": 1, "active": [{"title": "Live Lens", "status": "active"}]},
            "inbox": {"alert_count": 1},
            "runs": {"last_run": {"summary": "Lens state is flowing live."}},
            "objective": {"label": "Live Lens"},
        },
        actions=[{"kind": "observer.scan", "label": "Run Observer Scan"}],
    )

    assert payload["mode"] == "away"
    assert "Incident pressure is high." in payload["headline"]
    assert payload["notification"]["kind"] == "incident.pressure"
    assert payload["notification"]["severity"] == "high"
    assert any(trigger["kind"] == "incident.pressure.increased" for trigger in payload["triggers"])
    assert any("Recommended next actions: Run Observer Scan." in line for line in payload["lines"])


def test_operator_presence_reports_stable_state_without_triggers() -> None:
    payload = compose_operator_presence(
        mode="assist",
        snapshot={
            "workspace_root": "D:/francis/workspace",
            "control": {"mode": "assist", "kill_switch": False},
            "incidents": {"open_count": 0, "highest_severity": "nominal"},
            "approvals": {"pending_count": 0},
            "missions": {"active_count": 0, "active": []},
            "inbox": {"alert_count": 0},
            "runs": {"last_run": {}},
            "objective": {"label": "Systematically build Francis"},
        },
        actions=[],
    )

    assert payload["notification"]["kind"] == "system.stable"
    assert payload["triggers"] == []
