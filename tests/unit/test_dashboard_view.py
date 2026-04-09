from __future__ import annotations

import services.hud.app.views.dashboard as dashboard_view


def test_dashboard_view_exposes_support_role_card(monkeypatch) -> None:
    def _snapshot() -> dict[str, object]:
        return {
            "control": {"mode": "assist", "kill_switch": False},
            "missions": {"active_count": 1, "backlog_count": 2, "completed_count": 3},
            "approvals": {"pending_count": 1},
            "incidents": {"open_count": 0, "highest_severity": "low"},
            "security": {"quarantine_count": 0, "highest_severity": "nominal", "top_categories": {}},
            "runs": {"ledger_count": 4},
            "apprenticeship": {"review_count": 0},
            "fabric": {
                "citation_ready_count": 2,
                "calibration": {"confidence_counts": {"confirmed": 1, "likely": 1, "uncertain": 0}},
            },
            "current_work": {
                "summary": "Current work stays anchored in the orb-first strip.",
                "terminal_summary": "Terminal anchor unavailable.",
                "attention": {"label": "Stable"},
                "repo": {"branch": "main", "dirty": False, "severity": "low"},
                "next_action_signal": {"severity": "low", "reason": "No pressure"},
            },
            "next_best_action": {
                "label": "Review receipts",
                "reason": "Receipts are ready for deeper inspection.",
                "trust_badge": "Confirmed",
                "risk_tier": "low",
            },
            "objective": {"label": "Keep the orb first."},
        }

    monkeypatch.setattr(dashboard_view, "build_lens_snapshot", _snapshot)

    payload = dashboard_view.get_dashboard_view()

    support_role = next(card for card in payload["cards"] if card["id"] == "surface-role")

    assert support_role["title"] == "Support Role"
    assert "Orb remains the live operator body" in support_role["summary"]
    assert support_role["detail"]["primary_surface"] == "orb"
    assert support_role["detail"]["support_surface"] == "lens_hud"
    assert support_role["detail"]["responsibilities"] == [
        "receipts",
        "diagnostics",
        "expanded_controls",
        "review",
    ]
