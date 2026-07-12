from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from francis.lens.input_events import (
    DesktopInputObservation,
    LensInputEventStream,
    lens_input_event_stream_readback,
)


class _Source:
    def __init__(self, observations: list[DesktopInputObservation]) -> None:
        self.observations = iter(observations)
        self.calls = 0

    def observe(self) -> DesktopInputObservation:
        self.calls += 1
        return next(self.observations)


def _active_authority(receipt_id: str, *, now: int | None = None) -> dict[str, Any]:
    del now
    return {
        "status": "active",
        "active": True,
        "receipt_id": receipt_id,
        "authorities": {"desktop_input_observation_authority": True},
        "blockers": [],
    }


def test_input_event_stream_refuses_before_observing_without_exact_authority(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    source = _Source([DesktopInputObservation(observed_at=100.0, cursor_x=10, cursor_y=20)])
    stream = LensInputEventStream(
        authority_receipt_id="input-receipt",
        authority_status=lambda _receipt_id, now=None: {  # noqa: ARG005
            "active": False,
            "blockers": ["desktop_input_observation_authority_receipt_not_found"],
        },
        clock=lambda: 100.0,
    )

    result = stream.sample_once(source)

    assert result["ready"] is False
    assert source.calls == 0
    assert "desktop_input_observation_authority_not_active" in result["blockers"]
    assert not (tmp_path / "runtime" / "lens-perception" / "input-events.json").exists()


def test_input_event_stream_records_bounded_metadata_and_promotes_gestures(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    observations = [
        DesktopInputObservation(
            observed_at=100.0,
            cursor_x=10,
            cursor_y=20,
            foreground_window_id=40,
            foreground_process_id=80,
        ),
        DesktopInputObservation(
            observed_at=100.1,
            cursor_x=12,
            cursor_y=24,
            foreground_window_id=41,
            foreground_process_id=81,
            buttons_down=("left",),
        ),
        DesktopInputObservation(
            observed_at=100.2,
            cursor_x=12,
            cursor_y=24,
            foreground_window_id=41,
            foreground_process_id=81,
            scroll_delta_y=-120,
            keyboard_activity=True,
            scroll_source_connected=True,
            keyboard_activity_source_connected=True,
        ),
    ]
    source = _Source(observations)
    stream = LensInputEventStream(
        authority_receipt_id="input-receipt",
        authority_status=_active_authority,
    )

    stream.sample_once(source)
    stream.sample_once(source)
    result = stream.sample_once(source)

    assert result["ready"] is True
    assert result["pointer_activity"]["orb_yield_required"] is True
    assert {item["kind"] for item in result["events"]} >= {
        "cursor_position",
        "cursor_move",
        "focus_change",
        "pointer_button",
        "scroll",
        "keyboard_activity",
    }
    assert {item["kind"] for item in result["gestures"]} >= {
        "pointer_click",
        "focus_change",
        "scroll",
        "typing_activity",
    }
    assert result["current"]["foreground"] == {"window_id": 41, "process_id": 81}
    assert result["capabilities"]["scroll_activity"] is True
    assert result["capabilities"]["keyboard_activity_timing"] is True
    assert result["source_blockers"] == []
    assert result["governance"]["keyboard_content_captured"] is False
    assert result["governance"]["key_codes_captured"] is False
    assert result["governance"]["window_titles_captured"] is False
    stored_path = tmp_path / "runtime" / "lens-perception" / "input-events.json"
    stored = json.loads(stored_path.read_text(encoding="utf-8"))
    serialized_events = json.dumps(stored["events"], sort_keys=True)
    assert "key_code" not in serialized_events
    assert "window_title" not in serialized_events
    assert "clipboard" not in serialized_events


def test_input_event_stream_ages_out_raw_events_and_pointer_activity(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    stream = LensInputEventStream(
        authority_receipt_id="input-receipt",
        retention_seconds=2.0,
        pointer_active_seconds=0.5,
        authority_status=_active_authority,
    )
    stream.observe(DesktopInputObservation(observed_at=100.0, cursor_x=0, cursor_y=0))
    stream.observe(DesktopInputObservation(observed_at=100.1, cursor_x=10, cursor_y=10))

    result = stream.observe(DesktopInputObservation(observed_at=103.0, cursor_x=10, cursor_y=10))

    assert result["ready"] is True
    assert result["event_count"] == 0
    assert result["pointer_activity"]["active"] is False
    assert result["pointer_activity"]["orb_yield_required"] is False


def test_input_event_stream_readback_rejects_added_content_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    stream = LensInputEventStream(
        authority_receipt_id="input-receipt",
        authority_status=_active_authority,
    )
    stream.observe(DesktopInputObservation(observed_at=100.0, cursor_x=0, cursor_y=0))
    path = tmp_path / "runtime" / "lens-perception" / "input-events.json"
    stored = json.loads(path.read_text(encoding="utf-8"))
    stored["events"][0]["key_code"] = 65
    path.write_text(json.dumps(stored), encoding="utf-8")
    readback = lens_input_event_stream_readback(now=100.1, authority_status=_active_authority)

    assert readback["ready"] is False
    assert "lens_input_event_stream_content_contract_invalid" in readback["blockers"]
