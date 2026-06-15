from __future__ import annotations

import json
from pathlib import Path


def test_lens_mcp_status_route_exposes_read_only_body_state(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.get("/lens/mcp/status?actor=test.lens.mcp.status&receipt_limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "francis.lens_orb.mcp_status_bridge"
    assert body["status"] in {"ready", "degraded"}
    assert body["mcp"]["tool_count"] >= 18
    assert "missing_tools" in body["mcp"]
    assert "missing_required_tools" in body["mcp"]
    assert body["resident"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["raw_input"] is False
    assert body["governance"]["screenshots"] is False
    assert body["governance"]["ocr"] is False
    assert "traceback" not in json.dumps(body, sort_keys=True).lower()


def test_lens_orb_mcp_status_alias_route_is_available(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.get("/lens/orb/mcp-status?actor=test.lens.orb")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "francis.lens_orb.mcp_status_bridge"
    assert body["routes"]["mcp_status"] == "/lens/mcp/status"
