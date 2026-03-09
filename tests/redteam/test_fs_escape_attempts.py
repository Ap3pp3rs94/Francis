from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from apps.api.main import app


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2] / "workspace"


def _quarantine_file() -> Path:
    return _workspace_root() / "security" / "quarantine.jsonl"


def _stash(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _restore(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parsed = json.loads(line)
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _get_mode(client: TestClient) -> dict:
    response = client.get("/control/mode")
    assert response.status_code == 200
    return response.json()


def _set_mode(client: TestClient, mode: str, kill_switch: bool | None = None) -> None:
    payload: dict[str, object] = {"mode": mode}
    if kill_switch is not None:
        payload["kill_switch"] = kill_switch
    response = client.put("/control/mode", json=payload)
    assert response.status_code == 200


def _get_scope(client: TestClient) -> dict:
    response = client.get("/control/scope")
    assert response.status_code == 200
    return response.json()["scope"]


def _set_scope(client: TestClient, scope: dict) -> None:
    response = client.put("/control/scope", json=scope)
    assert response.status_code == 200


def _enable_tools_app(scope: dict) -> dict:
    apps = [str(item) for item in scope.get("apps", []) if isinstance(item, str)]
    if "tools" not in [item.lower() for item in apps]:
        apps.append("tools")
    return {
        "repos": scope.get("repos", []),
        "workspaces": scope.get("workspaces", []),
        "apps": apps,
    }


def test_workspace_path_escape_attempt_is_quarantined_before_tool_execution() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    quarantine_before = _stash(_quarantine_file())
    escape_name = f"redteam_escape_{uuid4()}.txt"
    escaped_path = (Path(__file__).resolve().parents[2] / escape_name).resolve()
    if escaped_path.exists():
        escaped_path.unlink()

    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_tools_app(original_scope))

        response = c.post(
            "/tools/run",
            json={"skill": "workspace.write", "args": {"path": f"../{escape_name}", "content": "owned"}},
        )
        assert response.status_code == 409
        detail = response.json()["detail"]
        assert "filesystem_escape" in detail["quarantine"]["categories"]
        assert not escaped_path.exists()

        quarantine_rows = _read_jsonl(_quarantine_file())
        assert quarantine_rows
        assert quarantine_rows[-1]["action"] == "tools.run"
    finally:
        if escaped_path.exists():
            escaped_path.unlink()
        _restore(_quarantine_file(), quarantine_before)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))
