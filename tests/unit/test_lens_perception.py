from __future__ import annotations

import json
from pathlib import Path

from francis.lens.perception import lens_perception_runtime_readback


def _write_runtime_state(data_root: Path, payload: dict[str, object]) -> Path:
    path = data_root / "runtime" / "lens-perception" / "status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_supervisor_state(data_root: Path) -> Path:
    path = data_root / "runtime" / "lens-host-supervisor" / "status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "kind": "lens.host.supervisor_state",
                "status": "resident_supervising",
                "supervisor_pid": 42,
                "supervisor_process_alive": True,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_perception_readback_fails_closed_when_runtime_state_is_missing(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    payload = lens_perception_runtime_readback(now=100.0)

    assert payload["status"] == "not_observed"
    assert payload["ready"] is False
    assert payload["blockers"] == ["lens_perception_runtime_state_missing"]
    assert payload["capture"]["desktop"]["active"] is False
    assert not (data_root / "runtime" / "lens-perception").exists()


def test_perception_readback_requires_fresh_supervised_authorized_situation_model(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_supervisor_state(data_root)
    _write_runtime_state(
        data_root,
        {
            "kind": "lens.perception.runtime_state",
            "version": 1,
            "owner": "lens_supervisor",
            "state": "running",
            "updated_at": 100.0,
            "situation_model": {"status": "ready", "revision": "42"},
            "capture": {
                "desktop": {
                    "authority_granted": True,
                    "active": True,
                    "receipt_id": "lens-perception-enable-42",
                    "source": "desktop_ring_buffer",
                }
            },
        },
    )

    payload = lens_perception_runtime_readback(now=102.0)

    assert payload["status"] == "ready"
    assert payload["ready"] is True
    assert payload["fresh"] is True
    assert payload["supervision"]["active"] is True
    assert payload["situation_model"]["revision"] == "42"
    assert payload["capture"]["desktop"]["pixels_in_readback"] is False
    assert payload["capture"]["keyboard_content_captured"] is False


def test_perception_readback_rejects_stale_or_unauthorized_state(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_supervisor_state(data_root)
    _write_runtime_state(
        data_root,
        {
            "kind": "lens.perception.runtime_state",
            "version": 1,
            "owner": "lens_supervisor",
            "state": "running",
            "updated_at": 10.0,
            "situation_model": {"status": "ready"},
            "capture": {"desktop": {"authority_granted": False, "active": False}},
        },
    )

    payload = lens_perception_runtime_readback(now=20.0)

    assert payload["ready"] is False
    assert "lens_perception_runtime_state_stale" in payload["blockers"]
    assert "desktop_capture_authority_not_granted" in payload["blockers"]
    assert "desktop_capture_not_active" in payload["blockers"]


def test_perception_readback_rejects_a_self_labeled_owner_without_live_supervisor(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_runtime_state(
        data_root,
        {
            "kind": "lens.perception.runtime_state",
            "version": 1,
            "owner": "lens_supervisor",
            "state": "running",
            "updated_at": 100.0,
            "situation_model": {"status": "ready"},
            "capture": {"desktop": {"authority_granted": True, "active": True, "receipt_id": "r1"}},
        },
    )

    payload = lens_perception_runtime_readback(now=101.0)

    assert payload["ready"] is False
    assert payload["supervision"]["active"] is False
    assert "lens_perception_supervisor_not_observed" in payload["blockers"]
