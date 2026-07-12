from __future__ import annotations

from pathlib import Path


def test_operator_snapshot_reuses_supplied_mission_continuity(monkeypatch, tmp_path: Path) -> None:
    from francis.world_state import operator_mode

    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv("FRANCIS_ROOT", str(tmp_path))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setattr(
        operator_mode,
        "mission_continuity_snapshot",
        lambda **_: (_ for _ in ()).throw(AssertionError("mission continuity recomputed")),
    )
    continuity = {
        "mission_status_counts": {"queued": 2, "blocked": 1},
        "mission_briefing": {},
    }

    state = operator_mode.snapshot(continuity=continuity)

    assert state["ok"] is True
    assert state["backlog"]["queued_missions"] == 2
    assert state["backlog"]["blocked_missions"] == 1


def test_orb_snapshot_reuses_supplied_operator_report(monkeypatch) -> None:
    from francis.world_state import orb

    monkeypatch.setattr(
        orb,
        "operator_mode_snapshot",
        lambda: (_ for _ in ()).throw(AssertionError("operator report recomputed")),
    )
    monkeypatch.setattr(orb, "_observer_presence", lambda: ({}, {}))
    operator_report = {
        "control_mode": {"id": "assist"},
        "focus": {},
        "backlog": {},
        "continuity": {},
    }

    state = orb.snapshot(operator_report=operator_report)

    assert state["ok"] is True
    assert state["state"]["mode"]["id"] == "assist"
