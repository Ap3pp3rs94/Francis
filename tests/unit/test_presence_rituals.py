from francis_presence.rituals import build_handback_ritual, build_shift_report


def test_build_handback_ritual_includes_run_and_verification() -> None:
    ritual = build_handback_ritual(
        mode="pilot",
        run_id="run-123",
        summary="Validated the shared presence slice.",
        pending_approvals=2,
        verification={"pytest": "pass", "ruff": "pass"},
        fabric_summary={
            "citation_ready_count": 3,
            "calibration": {
                "confidence_counts": {"confirmed": 1, "likely": 2, "uncertain": 0},
                "stale_current_state_count": 0,
            },
        },
    )

    assert ritual["title"] == "Pilot handback ready."
    assert any("Run ID: run-123" in line for line in ritual["lines"])
    assert any("Verification: pytest=pass, ruff=pass" in line for line in ritual["lines"])
    assert any("Fabric trust: Confirmed" in line for line in ritual["lines"])


def test_build_shift_report_lists_deltas_and_next_action() -> None:
    report = build_shift_report(
        completed_actions=3,
        staged_actions=1,
        pending_approvals=1,
        top_deltas=["Lens contract shared", "Voice presence grounded"],
        next_action="Review the queued approval.",
        fabric_summary={
            "citation_ready_count": 1,
            "calibration": {
                "confidence_counts": {"confirmed": 0, "likely": 1, "uncertain": 1},
                "stale_current_state_count": 1,
            },
        },
    )

    assert report["title"] == "Shift complete."
    assert any("Top deltas: Lens contract shared, Voice presence grounded" in line for line in report["lines"])
    assert any("Recommended next action: Review the queued approval." in line for line in report["lines"])
    assert any("Fabric trust: Likely" in line for line in report["lines"])
    assert any("Trust note: Refresh 1 stale current-state artifact" in line for line in report["lines"])
