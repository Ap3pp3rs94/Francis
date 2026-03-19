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
            }
        )

        assert perception["state"] == "live"
        assert perception["freshness"]["state"] == "fresh"
        assert perception["display"] == {"width": 1920, "height": 1080}
        assert perception["window"]["pid"] == 7788
        assert perception["focus"]["width"] == 196
        assert perception["sensing"]["scope"] == "active_display_only"
        assert perception["active_surface"]["kind"] == "editor"
        assert perception["active_surface"]["intent"] == "code_editing"
        assert perception["target"]["kind"] == "cursor_focus"
        assert perception["target"]["actionable"] is True
        assert perception["target"]["window"]["in_bounds"] is True
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
