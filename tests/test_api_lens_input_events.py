from __future__ import annotations

from pathlib import Path


def test_lens_input_event_readback_route_is_missing_without_runtime_state(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True)
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(repo_root / "data"))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    response = TestClient(create_app()).get("/lens/perception/input")

    assert response.status_code == 200
    assert response.json()["status"] == "missing"
    assert response.json()["blockers"] == ["lens_input_event_stream_state_missing"]
