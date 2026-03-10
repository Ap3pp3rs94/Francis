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
            "fabric": {
                "citation_ready_count": 5,
                "calibration": {
                    "confidence_counts": {"confirmed": 2, "likely": 3, "uncertain": 1},
                    "stale_current_state_count": 1,
                },
            },
            "objective": {"label": "Live Lens"},
        },
        actions=[{"kind": "observer.scan", "label": "Run Observer Scan"}],
    )

    assert payload["mode"] == "away"
    assert "Incident pressure is high." in payload["headline"]
    assert payload["notification"]["kind"] == "incident.pressure"
    assert payload["notification"]["severity"] == "high"
    assert any(trigger["kind"] == "incident.pressure.increased" for trigger in payload["triggers"])
    assert payload["grounding"]["trust"] == "Likely"
    assert any("Fabric trust is likely" in line for line in payload["lines"])
    assert any("Refresh 1 stale current-state artifact" in line for line in payload["lines"])
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
    assert payload["grounding"]["trust"] == "Uncertain"
    assert any("Knowledge Fabric has no citation-ready evidence yet" in line for line in payload["lines"])


def test_operator_presence_surfaces_handback_language() -> None:
    payload = compose_operator_presence(
        mode="assist",
        snapshot={
            "workspace_root": "D:/francis/workspace",
            "control": {"mode": "assist", "kill_switch": False},
            "takeover": {
                "status": "idle",
                "handed_back_at": "2026-03-10T04:10:00+00:00",
                "handback_available": True,
                "handback": {
                    "summary": "Returned authority after verification.",
                    "pending_approvals": 1,
                    "run_id": "run-handback",
                    "trace_id": "trace-handback",
                    "fabric_posture": {"trust": "Likely"},
                },
            },
            "incidents": {"open_count": 0, "highest_severity": "nominal"},
            "approvals": {"pending_count": 0},
            "missions": {"active_count": 0, "active": []},
            "inbox": {"alert_count": 0},
            "runs": {"last_run": {"summary": "Pilot work completed."}},
            "fabric": {
                "citation_ready_count": 2,
                "calibration": {
                    "confidence_counts": {"confirmed": 1, "likely": 1, "uncertain": 0},
                    "stale_current_state_count": 0,
                },
            },
            "objective": {"label": "Return control cleanly"},
        },
        actions=[],
    )

    assert "Handback is complete." in payload["headline"]
    assert payload["notification"]["kind"] == "control.handback"
    assert any(trigger["kind"] == "control.takeover.handed_back" for trigger in payload["triggers"])
    assert payload["grounding"]["handback"]["available"] is True
    assert payload["grounding"]["handback"]["run_id"] == "run-handback"
    assert any("Handback summary: Returned authority after verification." in line for line in payload["lines"])
    assert any("Handback trust is likely with 1 pending approval." in line for line in payload["lines"])
