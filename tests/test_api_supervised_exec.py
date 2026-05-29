from __future__ import annotations

import json
from pathlib import Path

import pytest

_SUPERVISED_ACTOR = "test.supervised_exec"


def _allow_supervised_exec(monkeypatch) -> None:
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({_SUPERVISED_ACTOR: ["codex.supervised_exec"]}),
    )


def test_api_supervised_exec_direct_run_denies_without_actor_scope(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    denied = client.post(
        "/operations/supervised-exec/run",
        json={
            "objective": "test",
            "user_command": "echo denied",
            "cwd": str(tmp_path),
            "actor": _SUPERVISED_ACTOR,
        },
    )

    assert denied.status_code == 200
    body = denied.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["governance"]["gate"] == "permission_gate"
    assert body["governance"]["reason"] == "missing_scopes"
    assert body["governance"]["evidence"]["actor_present"] is True
    assert body["governance"]["evidence"]["required_scope_count"] == 1
    assert not (data_root / "approvals").exists()


def test_api_supervised_exec_flow(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _allow_supervised_exec(monkeypatch)

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.governance import approvals

    client = TestClient(create_app())

    # 1) Initial request should require approval.
    r1 = client.post(
        "/operations/supervised-exec/run",
        json={
            "objective": "test",
            "user_command": "echo hello",
            "cwd": str(tmp_path),
            "actor": _SUPERVISED_ACTOR,
        },
    )
    assert r1.status_code == 200
    res1 = r1.json()
    assert res1["status"] == "needs_approval"
    assert res1["governance"]["gate"] == "approvals_gate"
    approval_id = str(res1["approval_id"])

    # 2) Approve then rerun.
    dec = approvals.decide(approval_id, "approve")
    assert dec["ok"] is True

    r2 = client.post(
        "/operations/supervised-exec/run",
        json={
            "objective": "test",
            "user_command": "echo hello",
            "cwd": str(tmp_path),
            "approval_id": approval_id,
            "actor": _SUPERVISED_ACTOR,
        },
    )
    assert r2.status_code == 200
    res2 = r2.json()
    assert res2["ok"] is True

    art = Path(str(res2["artifact_dir"]))
    assert art.exists()
    assert (art / "plan.json").exists()
    assert (art / "stdout.txt").exists()
    assert (art / "stderr.txt").exists()
    assert (art / "result.json").exists()


def test_api_supervised_exec_rejects_shell_metacharacters_before_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _allow_supervised_exec(monkeypatch)

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    response = client.post(
        "/operations/supervised-exec/run",
        json={
            "objective": "test",
            "user_command": "echo hello && whoami",
            "cwd": str(tmp_path),
            "actor": _SUPERVISED_ACTOR,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "invalid"
    assert body["error"] == "unsupported_shell_syntax"
    assert not (data_root / "approvals").exists()


def test_api_supervised_exec_rejects_cwd_outside_allowed_roots(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    outside_root = Path.cwd().parent / f"{Path.cwd().name}_outside_cwd"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _allow_supervised_exec(monkeypatch)

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    response = client.post(
        "/operations/supervised-exec/run",
        json={
            "objective": "test",
            "user_command": "echo hello",
            "cwd": str(outside_root),
            "actor": _SUPERVISED_ACTOR,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "invalid"
    assert body["error"] == "cwd_outside_allowed_root"
    assert not (data_root / "approvals").exists()


def test_supervised_exec_artifact_writers_reject_paths_outside_artifact_root(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.agent import supervised_exec

    outside_json = tmp_path / "outside" / "escape.json"
    with pytest.raises(ValueError, match="artifact_path_outside_allowed_root"):
        supervised_exec._write_json(outside_json, {"password": "artifactsecret123"})
    assert not outside_json.exists()

    outside_text = tmp_path / "outside" / "stdout.txt"
    with pytest.raises(ValueError, match="artifact_path_outside_allowed_root"):
        supervised_exec._write_redacted_text(outside_text, "token=artifacttextsecret123")
    assert not outside_text.exists()

    artifact_dir = supervised_exec._artifact_dir("run_artifact_guard")
    supervised_exec._write_json(artifact_dir / "request.json", {"password": "artifactsecret123"})
    supervised_exec._write_redacted_text(artifact_dir / "stdout.txt", "token=artifacttextsecret123")

    request_text = (artifact_dir / "request.json").read_text(encoding="utf-8")
    stdout_text = (artifact_dir / "stdout.txt").read_text(encoding="utf-8")
    assert "artifactsecret123" not in request_text
    assert "artifacttextsecret123" not in stdout_text
    assert "[REDACTED:secret]" in request_text
    assert "[REDACTED:secret]" in stdout_text


def test_api_supervised_exec_rejects_approval_payload_mismatch(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _allow_supervised_exec(monkeypatch)

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.governance import approvals

    client = TestClient(create_app())

    requested = client.post(
        "/operations/supervised-exec/run",
        json={
            "objective": "test",
            "user_command": "echo approved",
            "cwd": str(tmp_path),
            "actor": _SUPERVISED_ACTOR,
        },
    )
    assert requested.status_code == 200
    requested_body = requested.json()
    assert requested_body["status"] == "needs_approval"
    assert requested_body["governance"]["gate"] == "approvals_gate"
    approval_id = str(requested_body["approval_id"])
    requested_art = Path(str(requested_body["artifact_dir"]))

    approved = approvals.decide(approval_id, "approve")
    assert approved["ok"] is True

    mismatched = client.post(
        "/operations/supervised-exec/run",
        json={
            "objective": "test",
            "user_command": "echo MALICIOUS",
            "cwd": str(tmp_path),
            "approval_id": approval_id,
            "actor": _SUPERVISED_ACTOR,
        },
    )
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["ok"] is False
    assert mismatched_body["status"] == "needs_approval"
    assert mismatched_body["error"] == "approval_payload_mismatch"
    refreshed_approval_id = str(mismatched_body["approval_id"])
    assert refreshed_approval_id
    assert refreshed_approval_id != approval_id
    assert mismatched_body["previous_approval_id"] == approval_id
    assert mismatched_body["governance"]["gate"] == "approvals_gate"

    art = Path(str(mismatched_body["artifact_dir"]))
    assert (art / "request.json").exists()
    assert (art / "mismatch.json").exists()
    assert not (art / "result.json").exists()
    assert (requested_art / "mismatch.json").exists()


def test_api_supervised_exec_refreshes_missing_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _allow_supervised_exec(monkeypatch)

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    requested = client.post(
        "/operations/supervised-exec/run",
        json={
            "objective": "test",
            "user_command": "echo missing",
            "cwd": str(tmp_path),
            "actor": _SUPERVISED_ACTOR,
        },
    )
    assert requested.status_code == 200
    requested_body = requested.json()
    assert requested_body["status"] == "needs_approval"
    approval_id = str(requested_body["approval_id"])

    pending_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    assert pending_path.exists()
    pending_path.unlink()

    retried = client.post(
        "/operations/supervised-exec/run",
        json={
            "objective": "test",
            "user_command": "echo missing",
            "cwd": str(tmp_path),
            "approval_id": approval_id,
            "actor": _SUPERVISED_ACTOR,
        },
    )
    assert retried.status_code == 200
    retried_body = retried.json()
    assert retried_body["ok"] is False
    assert retried_body["status"] == "needs_approval"
    assert retried_body["error"] == "approval_not_found"
    refreshed_approval_id = str(retried_body["approval_id"])
    assert refreshed_approval_id
    assert refreshed_approval_id != approval_id
    assert retried_body["previous_approval_id"] == approval_id
    assert retried_body["governance"]["gate"] == "approvals_gate"

    art = Path(str(retried_body["artifact_dir"]))
    assert (art / "request.json").exists()
    assert (art / "error.json").exists()
    assert not (art / "result.json").exists()
