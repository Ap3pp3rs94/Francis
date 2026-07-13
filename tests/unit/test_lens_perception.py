from __future__ import annotations

import json
import os
from pathlib import Path

from francis.lens import perception as perception_module
from francis.lens.perception import lens_perception_runtime_readback
from francis.lens.perception_capture import DesktopFrame, PerceptionRingBuffer


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
                "supervisor_pid": os.getpid(),
                "supervisor_process_alive": True,
                "observed_pid": os.getpid(),
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_ring_frame(*, receipt_id: str, captured_at: float) -> None:
    PerceptionRingBuffer(authority_status=lambda _receipt_id, _now: {"active": True}).append(
        DesktopFrame(
            captured_at=captured_at,
            origin_x=0,
            origin_y=0,
            source_width=1,
            source_height=1,
            width=1,
            height=1,
            bgra=b"\x00\x00\x00\x00",
        ),
        authority_receipt_id=receipt_id,
    )


def _write_situation_heartbeat(
    data_root: Path,
    *,
    revision: str,
    updated_at: float,
    semantic_comprehension_ready: bool,
) -> None:
    path = data_root / "runtime" / "lens-perception" / "situation-model.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "kind": "lens.perception.situation_model",
                "version": 1,
                "status": "heartbeat_partial",
                "revision": revision,
                "updated_at": updated_at,
                "has_current_desktop_state": True,
                "semantic_comprehension_ready": semantic_comprehension_ready,
                "runtime_identity": {
                    "authority_receipt_id": "lens-perception-enable-42",
                    "execution_approval_id": "approved-perception-execution",
                },
                "present": {"plane": "desktop"},
                "sources": {},
                "blockers": [],
                "governance": {
                    "runtime_state_only": True,
                    "observation_only": True,
                    "desktop_capture_authority": True,
                    "execution_authority": True,
                    "camera_capture_authority": False,
                    "microphone_capture_authority": False,
                    "keyboard_content_captured": False,
                    "user_mouse_captured": False,
                    "input_execution_authority": False,
                    "memory_write": False,
                    "raw_pixels_in_state": False,
                },
            }
        ),
        encoding="utf-8",
    )


def test_perception_readback_fails_closed_when_runtime_state_is_missing(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    payload = lens_perception_runtime_readback(now=100.0)

    assert payload["status"] == "not_observed"
    assert payload["ready"] is False
    assert payload["blockers"] == ["lens_perception_runtime_state_missing"]
    assert payload["capture"]["desktop"]["active"] is False
    assert not (data_root / "runtime" / "lens-perception").exists()


def test_perception_snapshot_retries_a_concurrent_situation_revision(monkeypatch) -> None:
    revisions = iter(("frame-1", "frame-2"))
    sleeps: list[float] = []

    monkeypatch.setattr(
        perception_module,
        "_read_runtime_state",
        lambda _path: {"situation_model": {"revision": next(revisions)}},
    )
    monkeypatch.setattr(
        perception_module,
        "lens_situation_model_readback",
        lambda now=None: {"revision": "frame-2", "heartbeat_ready": True},
    )
    monkeypatch.setattr(perception_module.time, "sleep", sleeps.append)

    runtime, heartbeat = perception_module._read_runtime_situation_snapshot(Path("status.json"), 100.0)

    assert runtime["situation_model"]["revision"] == "frame-2"
    assert heartbeat["revision"] == "frame-2"
    assert len(sleeps) == 1


def test_perception_readback_requires_fresh_supervised_authorized_situation_model(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setattr(
        perception_module,
        "lens_perception_desktop_authority_receipt_status",
        lambda receipt_id, now=None: {
            "status": "active",
            "valid": True,
            "active": True,
            "receipt_id": receipt_id,
            "approval_id": "approved-desktop-capture",
            "approval_status": "approved",
            "plane": "desktop",
            "expires_ts": int(now or 0) + 60,
            "blockers": [],
        },
    )
    monkeypatch.setattr(
        perception_module,
        "lens_perception_execution_approval_status",
        lambda approval_id, authority_receipt_id: {
            "status": "approved",
            "active": True,
            "approval_id": approval_id,
            "authority_receipt_id": authority_receipt_id,
            "blockers": [],
        },
    )
    _write_supervisor_state(data_root)
    _write_situation_heartbeat(
        data_root,
        revision="42",
        updated_at=100.0,
        semantic_comprehension_ready=True,
    )
    _write_runtime_state(
        data_root,
        {
            "kind": "lens.perception.runtime_state",
            "version": 1,
            "owner": "lens_supervisor",
            "state": "running",
            "pid": os.getpid(),
            "host_pid": os.getpid(),
            "supervisor_pid": os.getpid(),
            "updated_at": 100.0,
            "situation_model": {
                "status": "heartbeat_ready",
                "revision": "42",
                "heartbeat_ready": True,
                "fresh": True,
                "has_current_desktop_state": True,
                "semantic_comprehension_ready": True,
            },
            "execution": {
                "active": True,
                "approval_id": "approved-perception-execution",
                "authority_receipt_id": "lens-perception-enable-42",
            },
            "governance": {
                "execution_authority": True,
                "camera_capture_authority": False,
                "microphone_capture_authority": False,
                "keyboard_capture_authority": False,
                "user_mouse_capture_authority": False,
                "input_execution_authority": False,
                "memory_write": False,
            },
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
    _write_ring_frame(receipt_id="lens-perception-enable-42", captured_at=100.0)

    payload = lens_perception_runtime_readback(now=102.0)

    assert payload["status"] == "ready"
    assert payload["ready"] is True
    assert payload["fresh"] is True
    assert payload["worker"]["process_alive"] is True
    assert payload["supervision"]["active"] is True
    assert payload["supervision"]["host_pid_matches"] is True
    assert payload["supervision"]["supervisor_pid_matches"] is True
    assert payload["execution"]["active"] is True
    assert payload["execution"]["authority_receipt_matches_capture"] is True
    assert payload["situation_model"]["revision"] == "42"
    assert payload["situation_model"]["heartbeat_ready"] is True
    assert payload["situation_model"]["semantic_comprehension_ready"] is True
    assert payload["ring_buffer"]["ready"] is True
    assert payload["ring_buffer"]["raw_pixels_in_readback"] is False
    assert payload["capture"]["desktop"]["pixels_in_readback"] is False
    assert payload["capture"]["desktop"]["authority_receipt"]["active"] is True
    assert payload["capture"]["keyboard_content_captured"] is False

    concurrent = lens_perception_runtime_readback(now=99.9)

    assert concurrent["ready"] is True
    assert concurrent["fresh"] is True
    assert concurrent["age_ms"] == -100.0
    assert concurrent["max_future_skew_ms"] == 250
    assert concurrent["ring_buffer"]["fresh"] is True
    assert concurrent["situation_model"]["heartbeat_ready"] is True

    situation_path = data_root / "runtime" / "lens-perception" / "situation-model.json"
    situation_state = json.loads(situation_path.read_text(encoding="utf-8"))
    situation_state["semantic_comprehension_ready"] = False
    situation_path.write_text(json.dumps(situation_state), encoding="utf-8")
    runtime_path = data_root / "runtime" / "lens-perception" / "status.json"
    runtime_state = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime_state["situation_model"]["semantic_comprehension_ready"] = False
    runtime_path.write_text(json.dumps(runtime_state), encoding="utf-8")

    partial = lens_perception_runtime_readback(now=102.0)

    assert partial["status"] == "blocked"
    assert partial["situation_model"]["heartbeat_ready"] is True
    assert partial["situation_model"]["has_current_desktop_state"] is True
    assert partial["situation_model"]["semantic_comprehension_ready"] is False
    assert "lens_situation_model_semantic_comprehension_not_ready" in partial["blockers"]


def test_perception_readback_rejects_self_reported_execution_without_exact_approval(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setattr(
        perception_module,
        "lens_perception_desktop_authority_receipt_status",
        lambda receipt_id, now=None: {
            "active": True,
            "receipt_id": receipt_id,
            "expires_ts": int(now or 0) + 60,
            "blockers": [],
        },
    )
    _write_supervisor_state(data_root)
    _write_runtime_state(
        data_root,
        {
            "kind": "lens.perception.runtime_state",
            "version": 1,
            "owner": "lens_supervisor",
            "state": "running",
            "pid": os.getpid(),
            "host_pid": os.getpid(),
            "supervisor_pid": os.getpid(),
            "updated_at": 100.0,
            "situation_model": {"status": "ready", "revision": "forged-execution"},
            "execution": {
                "active": True,
                "approval_id": "missing-approval",
                "authority_receipt_id": "capture-receipt",
            },
            "governance": {
                "execution_authority": True,
                "camera_capture_authority": False,
                "microphone_capture_authority": False,
                "keyboard_capture_authority": False,
                "user_mouse_capture_authority": False,
                "input_execution_authority": False,
                "memory_write": False,
            },
            "capture": {
                "desktop": {
                    "authority_granted": True,
                    "active": True,
                    "receipt_id": "capture-receipt",
                    "source": "desktop_ring_buffer",
                }
            },
        },
    )
    _write_ring_frame(receipt_id="capture-receipt", captured_at=100.0)

    payload = lens_perception_runtime_readback(now=101.0)

    assert payload["ready"] is False
    assert payload["execution"]["reported_active"] is True
    assert payload["execution"]["active"] is False
    assert "desktop_capture_execution_approval_not_found" in payload["blockers"]


def test_perception_readback_rejects_an_unresolved_authority_receipt(tmp_path: Path, monkeypatch) -> None:
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
            "pid": os.getpid(),
            "host_pid": os.getpid(),
            "supervisor_pid": os.getpid(),
            "updated_at": 100.0,
            "situation_model": {"status": "ready", "revision": "forged"},
            "capture": {
                "desktop": {
                    "authority_granted": True,
                    "active": True,
                    "receipt_id": "receipt-shaped-but-unresolved",
                    "source": "desktop_ring_buffer",
                }
            },
        },
    )

    payload = lens_perception_runtime_readback(now=101.0)

    assert payload["ready"] is False
    assert payload["capture"]["desktop"]["authority_receipt"]["active"] is False
    assert "desktop_capture_authority_receipt_not_found" in payload["blockers"]


def test_perception_readback_rejects_ring_buffer_from_another_authority_receipt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setattr(
        perception_module,
        "lens_perception_desktop_authority_receipt_status",
        lambda receipt_id, now=None: {
            "status": "active",
            "valid": True,
            "active": True,
            "receipt_id": receipt_id,
            "approval_id": "approved-desktop-capture",
            "approval_status": "approved",
            "plane": "desktop",
            "expires_ts": int(now or 0) + 60,
            "blockers": [],
        },
    )
    _write_supervisor_state(data_root)
    _write_runtime_state(
        data_root,
        {
            "kind": "lens.perception.runtime_state",
            "version": 1,
            "owner": "lens_supervisor",
            "state": "running",
            "pid": os.getpid(),
            "host_pid": os.getpid(),
            "supervisor_pid": os.getpid(),
            "updated_at": 100.0,
            "situation_model": {"status": "ready", "revision": "mismatch"},
            "capture": {
                "desktop": {
                    "authority_granted": True,
                    "active": True,
                    "receipt_id": "runtime-receipt",
                    "source": "desktop_ring_buffer",
                }
            },
        },
    )
    _write_ring_frame(receipt_id="another-receipt", captured_at=100.0)

    payload = lens_perception_runtime_readback(now=101.0)

    assert payload["ring_buffer"]["ready"] is True
    assert payload["ready"] is False
    assert "lens_perception_ring_buffer_authority_receipt_mismatch" in payload["blockers"]


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


def test_perception_readback_rejects_a_stale_supervisor_pid(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_supervisor_state(data_root)
    supervisor_path = data_root / "runtime" / "lens-host-supervisor" / "status.json"
    supervisor = json.loads(supervisor_path.read_text(encoding="utf-8"))
    supervisor["supervisor_pid"] = 999_999_999
    supervisor_path.write_text(json.dumps(supervisor), encoding="utf-8")
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

    assert payload["supervision"]["reported_process_alive"] is True
    assert payload["supervision"]["process_alive"] is False
    assert payload["ready"] is False
