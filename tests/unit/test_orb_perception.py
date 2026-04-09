from __future__ import annotations

from datetime import UTC, datetime

import services.orchestrator.app.orb_perception as orb_perception


def test_orb_perception_builds_fresh_active_surface_contract() -> None:
    previous = orb_perception.get_orb_perception_view()
    try:
        captured_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        perception = orb_perception.record_orb_perception_view(
            {
                "captured_at": captured_at,
                "display_id": 2,
                "display": {"width": 1920, "height": 1080},
                "idle_seconds": 4,
                "cursor": {"x": 640, "y": 288},
                "target_stability": {
                    "state": "settled",
                    "dwell_ms": 240,
                    "travel_px": 12,
                    "sample_count": 6,
                },
                "window": {
                    "title": "Visual Studio Code",
                    "process": "Code.exe",
                    "pid": 7788,
                    "bounds": {"x": 120, "y": 80, "width": 1440, "height": 900},
                },
                "frame": {
                    "width": 720,
                    "height": 405,
                    "data_url": "data:image/jpeg;base64,frame123",
                },
                "focus": {
                    "width": 196,
                    "height": 196,
                    "data_url": "data:image/jpeg;base64,focus456",
                },
                "accessibility": {
                    "available": True,
                    "attached": True,
                    "status": "attached",
                    "label": "Editor",
                    "name": "Editor",
                    "control_type": "document",
                    "process_id": 7788,
                    "bounds": {"x": 420, "y": 180, "width": 820, "height": 620},
                },
                "environment": {
                    "source_priority": ["accessibility", "window_metadata", "visual_focus", "display_capture"],
                    "primary_source": "accessibility",
                    "sources": {
                        "accessibility": {
                            "attached": True,
                            "process_match": True,
                            "in_window": True,
                            "cursor_inside": True,
                        },
                        "window_metadata": {
                            "attached": True,
                            "in_window": True,
                            "on_display": True,
                            "continuity_state": "anchored",
                        },
                        "visual_focus": {"attached": True},
                        "display_capture": {"attached": True},
                    },
                    "grounding": {
                        "state": "grounded",
                        "score": 0.92,
                        "in_window": True,
                        "on_display": True,
                        "continuity_state": "anchored",
                        "summary": "Accessibility, window, and visual evidence align on the current target.",
                    },
                },
            }
        )

        assert perception["state"] == "live"
        assert perception["freshness"]["state"] == "fresh"
        assert perception["display"] == {"width": 1920, "height": 1080}
        assert perception["window"]["pid"] == 7788
        assert perception["focus"]["width"] == 196
        assert perception["sensing"]["scope"] == "active_display_plus_foreground"
        assert perception["active_surface"]["kind"] == "editor"
        assert perception["active_surface"]["intent"] == "code_editing"
        assert perception["target"]["kind"] == "cursor_focus"
        assert perception["target"]["actionable"] is True
        assert perception["target"]["grounding"]["state"] == "grounded"
        assert perception["target"]["grounding"]["primary_source"] == "accessibility"
        assert perception["target"]["window"]["in_bounds"] is True
        assert perception["target"]["stability"]["state"] == "settled"
        assert perception["target"]["attention"]["state"] == "target_lock"
        assert perception["target"]["attention"]["salience"] == "high"
        assert perception["target"]["attention"]["strength"] >= 0.75
        assert perception["target"]["attention"]["lock_strength"] >= 0.8
        assert perception["accessibility"]["attached"] is True
        assert perception["environment"]["grounding"]["state"] == "grounded"
        assert perception["target"]["zone"]["kind"] == "editor_body"
        assert any(
            item["kind"] == "save_shortcut"
            for item in perception["target"]["affordances"]
            if isinstance(item, dict)
        )
        assert perception["cards"][0]["label"] == "Display"
        assert any(card["label"] == "Surface" for card in perception["cards"])
        assert any(card["label"] == "Target" for card in perception["cards"])
        assert any(card["label"] == "Zone" for card in perception["cards"])
        assert any(card["label"] == "Stability" for card in perception["cards"])
        assert any(card["label"] == "Action" for card in perception["cards"])
        assert "Francis sees Display 2" in perception["summary"]

        compact = orb_perception.get_orb_perception_view(include_frame_data=False)
        assert compact["frame"]["has_image"] is True
        assert compact["focus"]["has_image"] is True
        assert "foreground-window metadata" in compact["detail_summary"]
        target = orb_perception.resolve_orb_focus_target()
        assert target is not None
        assert target["surface"]["kind"] == "editor"
        assert target["target"]["label"] == "Editor focus point"
        assert target["target"]["window"]["in_bounds"] is True
        assert target["zone"]["kind"] == "editor_body"
        assert any(
            item["kind"] == "save_shortcut"
            for item in target["affordances"]
            if isinstance(item, dict)
        )
    finally:
        orb_perception.record_orb_perception_view(previous)


def test_orb_perception_infers_terminal_submit_affordance() -> None:
    previous = orb_perception.get_orb_perception_view()
    try:
        captured_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        perception = orb_perception.record_orb_perception_view(
            {
                "captured_at": captured_at,
                "display_id": 1,
                "display": {"width": 1600, "height": 900},
                "idle_seconds": 2,
                "cursor": {"x": 800, "y": 790},
                "target_stability": {
                    "state": "tracking",
                    "dwell_ms": 96,
                    "travel_px": 68,
                    "sample_count": 5,
                },
                "window": {
                    "title": "Windows Terminal",
                    "process": "Windows Terminal.exe",
                    "pid": 9911,
                    "bounds": {"x": 120, "y": 120, "width": 1200, "height": 760},
                },
                "frame": {"width": 640, "height": 360, "data_url": "data:image/jpeg;base64,frame789"},
                "focus": {"width": 180, "height": 180, "data_url": "data:image/jpeg;base64,focus999"},
            }
        )

        assert perception["active_surface"]["kind"] == "terminal"
        assert perception["target"]["zone"]["kind"] == "terminal_input"
        assert perception["target"]["attention"]["state"] == "investigate"
        assert perception["target"]["attention"]["salience"] in {"medium", "high"}
        assert any(
            item["kind"] == "submit_key"
            for item in perception["target"]["affordances"]
            if isinstance(item, dict)
        )

        target = orb_perception.resolve_orb_focus_target()
        assert target is not None
        assert target["zone"]["kind"] == "terminal_input"
        assert any(
            item["kind"] == "submit_key"
            for item in target["affordances"]
            if isinstance(item, dict)
        )
    finally:
        orb_perception.record_orb_perception_view(previous)


def test_orb_perception_downgrades_transient_francis_targets() -> None:
    previous = orb_perception.get_orb_perception_view()
    try:
        captured_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        perception = orb_perception.record_orb_perception_view(
            {
                "captured_at": captured_at,
                "display_id": 1,
                "display": {"width": 1536, "height": 912},
                "idle_seconds": 1,
                "cursor": {"x": 220, "y": 180},
                "target_stability": {
                    "state": "transient",
                    "dwell_ms": 24,
                    "travel_px": 180,
                    "sample_count": 4,
                },
                "window": {
                    "title": "Francis Lens",
                    "process": "electron.exe",
                    "pid": 4242,
                    "bounds": {"x": 100, "y": 80, "width": 1200, "height": 760},
                },
                "frame": {"width": 640, "height": 380, "data_url": "data:image/jpeg;base64,frame"},
                "focus": {"width": 196, "height": 196, "data_url": "data:image/jpeg;base64,focus"},
            }
        )

        assert perception["active_surface"]["kind"] == "francis"
        assert perception["target"]["confidence"] == "low"
        assert perception["target"]["stability"]["state"] == "transient"
        assert perception["target"]["grounding"]["state"] in {"reassess", "weak"}
        assert perception["target"]["attention"]["state"] == "reassess"
        assert perception["target"]["attention"]["uncertainty"] >= 0.5
        assert perception["target"]["zone"]["kind"] == "francis_action_row"
    finally:
        orb_perception.record_orb_perception_view(previous)


def test_orb_perception_infers_francis_navigation_open_affordance() -> None:
    previous = orb_perception.get_orb_perception_view()
    try:
        captured_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        perception = orb_perception.record_orb_perception_view(
            {
                "captured_at": captured_at,
                "display_id": 1,
                "display": {"width": 1536, "height": 912},
                "idle_seconds": 1,
                "cursor": {"x": 220, "y": 420},
                "target_stability": {
                    "state": "settled",
                    "dwell_ms": 212,
                    "travel_px": 18,
                    "sample_count": 6,
                },
                "window": {
                    "title": "Francis Lens",
                    "process": "electron.exe",
                    "pid": 4242,
                    "bounds": {"x": 100, "y": 80, "width": 1200, "height": 760},
                },
                "frame": {"width": 640, "height": 380, "data_url": "data:image/jpeg;base64,frame"},
                "focus": {"width": 196, "height": 196, "data_url": "data:image/jpeg;base64,focus"},
            }
        )

        assert perception["active_surface"]["kind"] == "francis"
        assert perception["target"]["zone"]["kind"] == "francis_navigation"
        assert perception["target"]["attention"]["state"] == "target_lock"
        assert any(
            item["kind"] == "open_key"
            for item in perception["target"]["affordances"]
            if isinstance(item, dict)
        )

        target = orb_perception.resolve_orb_focus_target()
        assert target is not None
        assert target["zone"]["kind"] == "francis_navigation"
        assert any(
            item["kind"] == "open_key"
            for item in target["affordances"]
            if isinstance(item, dict)
        )
    finally:
        orb_perception.record_orb_perception_view(previous)


def test_orb_perception_invalidates_stale_detached_targets() -> None:
    previous = orb_perception.get_orb_perception_view()
    try:
        perception = orb_perception.record_orb_perception_view(
            {
                "captured_at": "2025-01-01T00:00:00Z",
                "display_id": 1,
                "display": {"width": 1920, "height": 1080},
                "idle_seconds": 5,
                "cursor": {"x": 1760, "y": 960},
                "target_stability": {
                    "state": "settled",
                    "dwell_ms": 280,
                    "travel_px": 12,
                    "sample_count": 7,
                },
                "window": {
                    "title": "Visual Studio Code",
                    "process": "Code.exe",
                    "pid": 7788,
                    "bounds": {"x": 120, "y": 80, "width": 1280, "height": 860},
                },
                "frame": {
                    "width": 720,
                    "height": 405,
                    "data_url": "data:image/jpeg;base64,frame123",
                },
                "focus": {
                    "width": 196,
                    "height": 196,
                    "data_url": "data:image/jpeg;base64,focus456",
                },
                "environment": {
                    "source_priority": ["window_metadata", "visual_focus", "display_capture"],
                    "primary_source": "window_metadata",
                    "grounding": {
                        "state": "detached",
                        "score": 0.31,
                        "in_window": False,
                        "on_display": True,
                        "continuity_state": "anchored",
                        "invalidation_reason": "cursor_left_foreground_window",
                    },
                },
            }
        )

        assert perception["freshness"]["state"] == "stale"
        assert perception["target"]["grounding"]["state"] == "stale"
        assert perception["target"]["attention"]["state"] == "reassess"
        assert perception["target"]["actionable"] is False
        assert orb_perception.resolve_orb_focus_target() is None
    finally:
        orb_perception.record_orb_perception_view(previous)
