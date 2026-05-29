from __future__ import annotations

from pathlib import Path


def test_attachment_upload_requires_scoped_actor_and_sanitizes_filename(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    uploaded = client.post(
        "/attachments/upload",
        data={"request_actor": "test.attachments.write"},
        files={"file": ("../unsafe:name.txt", b"attachment-bytes", "text/plain")},
    )

    assert uploaded.status_code == 200
    body = uploaded.json()
    assert body["ok"] is True
    assert body["bytes"] == len(b"attachment-bytes")
    stored = Path(str(body["stored"]))
    assert stored.name == "unsafe_name.txt"
    assert stored.read_bytes() == b"attachment-bytes"
    assert stored.parent == data_root / "uploads" / "inbox"


def test_attachment_upload_denies_unscoped_actor_before_persisting(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    denied = client.post(
        "/attachments/upload",
        data={"request_actor": "unscoped.attachments.writer"},
        files={"file": ("denied.txt", b"do-not-store", "text/plain")},
    )

    assert denied.status_code == 200
    body = denied.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["governance"]["gate"] == "permission_gate"
    assert body["governance"]["reason"] == "missing_scopes"
    assert body["governance"]["next_step"] == "configure_actor_scope_before_uploading_attachments"
    assert body["governance"]["evidence"]["actor_present"] is True
    assert body["governance"]["evidence"]["required_scope_count"] == 1
    assert not (data_root / "uploads").exists()
