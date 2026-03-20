from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app
from francis_brain.ledger import RunLedger
from francis_core.workspace_fs import WorkspaceFS
import services.orchestrator.app.routes.dependencies as dependency_routes


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


def _enable_apps(scope: dict, required_apps: list[str]) -> dict:
    apps = [str(item) for item in scope.get("apps", []) if isinstance(item, str)]
    lowered = [item.lower() for item in apps]
    for app_name in required_apps:
        if app_name.lower() not in lowered:
            apps.append(app_name)
            lowered.append(app_name.lower())
    repo_root = str(Path(__file__).resolve().parents[2])
    workspace_root = str((Path(__file__).resolve().parents[2] / "workspace").resolve())
    return {
        "repos": [repo_root],
        "workspaces": [workspace_root],
        "apps": apps,
    }


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in _read_text(path).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _restore_text(path: Path, content: str, existed: bool) -> None:
    if existed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    elif path.exists():
        path.unlink()


def test_dependency_library_route_returns_structured_surface() -> None:
    with TestClient(app) as client:
        original_mode = _get_mode(client)
        original_scope = _get_scope(client)
        try:
            _set_mode(client, "observe", kill_switch=False)
            _set_scope(client, _enable_apps(original_scope, ["dependencies"]))
            response = client.get("/dependencies/library")
        finally:
            _set_scope(client, original_scope)
            _set_mode(
                client,
                str(original_mode.get("mode", "pilot")),
                bool(original_mode.get("kill_switch", False)),
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "dependency_library"
    assert "summary" in payload
    assert "library" in payload
    assert "entries" in payload
    assert payload["library"]["dependency_count"] >= 9


def test_dependency_quarantine_and_revoke_workflow() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    repo_root = workspace.parent.resolve()
    registry_path = workspace / "dependencies" / "registry.json"
    approvals_path = workspace / "approvals" / "requests.jsonl"
    decisions_path = workspace / "journals" / "decisions.jsonl"
    run_ledger_path = workspace / "runs" / "run_ledger.jsonl"
    registry_before_exists = registry_path.exists()
    registry_before = _read_text(registry_path)
    approvals_before_exists = approvals_path.exists()
    approvals_before = _read_text(approvals_path)
    decisions_before_exists = decisions_path.exists()
    decisions_before = _read_text(decisions_path)
    run_ledger_before_exists = run_ledger_path.exists()
    run_ledger_before = _read_text(run_ledger_path)
    route_workspace_before = dependency_routes._workspace_root
    route_repo_before = dependency_routes._repo_root
    route_fs_before = dependency_routes._fs
    route_ledger_before = dependency_routes._ledger
    fs = WorkspaceFS(
        roots=[workspace.resolve()],
        journal_path=(workspace / "journals" / "fs.jsonl").resolve(),
    )
    ledger = RunLedger(fs, rel_path="runs/run_ledger.jsonl")

    try:
        dependency_routes._workspace_root = workspace.resolve()
        dependency_routes._repo_root = repo_root
        dependency_routes._fs = fs
        dependency_routes._ledger = ledger
        approvals_path.parent.mkdir(parents=True, exist_ok=True)
        approvals_path.write_text("", encoding="utf-8")
        decisions_path.parent.mkdir(parents=True, exist_ok=True)
        decisions_path.write_text("", encoding="utf-8")

        with TestClient(app) as client:
            original_mode = _get_mode(client)
            original_scope = _get_scope(client)
            try:
                _set_mode(client, "pilot", kill_switch=False)
                _set_scope(client, _enable_apps(original_scope, ["dependencies", "approvals"]))

                quarantine = client.post(
                    "/dependencies/python:francis:fastapi/quarantine",
                    json={"reason": "Dependency is unpinned on the governed runtime path."},
                )
                assert quarantine.status_code == 200
                assert quarantine.json()["dependency"]["status"] == "quarantined"

                request_revoke = client.post(
                    "/dependencies/python:francis:fastapi/revoke/request-approval",
                    json={"reason": "Dependency should be revoked after quarantine."},
                )
                assert request_revoke.status_code == 200
                approval_id = str(request_revoke.json()["approval"]["id"]).strip()
                assert approval_id

                decision = client.post(
                    f"/approvals/{approval_id}/decision",
                    json={"decision": "approved", "note": "Dependency must be revoked."},
                )
                assert decision.status_code == 200

                revoke = client.post(
                    "/dependencies/python:francis:fastapi/revoke",
                    json={
                        "reason": "Dependency is no longer trusted for governed use.",
                        "approval_id": approval_id,
                    },
                )
            finally:
                _set_scope(client, original_scope)
                _set_mode(
                    client,
                    str(original_mode.get("mode", "pilot")),
                    bool(original_mode.get("kill_switch", False)),
                )

        assert revoke.status_code == 200
        payload = revoke.json()
        assert payload["dependency"]["status"] == "revoked"
        assert payload["approval_id"] == approval_id
        assert payload["presentation"]["kind"] == "dependencies.lifecycle"
        registry = json.loads(_read_text(registry_path))
        fastapi = next(row for row in registry["dependencies"] if row["id"] == "python:francis:fastapi")
        assert fastapi["status"] == "revoked"
        assert fastapi["quarantined_at"]
        assert fastapi["revoked_at"]
        ledger_rows = _read_jsonl(run_ledger_path)
        revoke_receipt = next(
            row for row in reversed(ledger_rows) if str(row.get("kind", "")).strip() == "dependencies.revoke"
        )
        quarantine_receipt = next(
            row for row in reversed(ledger_rows) if str(row.get("kind", "")).strip() == "dependencies.quarantine"
        )
        revoke_summary = revoke_receipt.get("summary", {}) if isinstance(revoke_receipt.get("summary"), dict) else {}
        quarantine_summary = (
            quarantine_receipt.get("summary", {}) if isinstance(quarantine_receipt.get("summary"), dict) else {}
        )
        assert revoke_summary["dependency_id"] == "python:francis:fastapi"
        assert revoke_summary["approval_id"] == approval_id
        assert quarantine_summary["dependency_id"] == "python:francis:fastapi"
        assert quarantine_summary["status"] == "quarantined"
    finally:
        dependency_routes._workspace_root = route_workspace_before
        dependency_routes._repo_root = route_repo_before
        dependency_routes._fs = route_fs_before
        dependency_routes._ledger = route_ledger_before
        _restore_text(registry_path, registry_before, registry_before_exists)
        _restore_text(approvals_path, approvals_before, approvals_before_exists)
        _restore_text(decisions_path, decisions_before, decisions_before_exists)
        _restore_text(run_ledger_path, run_ledger_before, run_ledger_before_exists)
