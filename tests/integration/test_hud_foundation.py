import json
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app as orchestrator_app
import services.hud.app.main as hud_main
import services.hud.app.state as hud_state
from services.hud.app.main import app


client = TestClient(app)
orchestrator = TestClient(orchestrator_app)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(payload, encoding="utf-8")


def _get_mode() -> dict:
    response = orchestrator.get("/control/mode")
    assert response.status_code == 200
    return response.json()


def _set_mode(mode: str, kill_switch: bool | None = None) -> None:
    payload: dict[str, object] = {"mode": mode}
    if kill_switch is not None:
        payload["kill_switch"] = kill_switch
    response = orchestrator.put("/control/mode", json=payload)
    assert response.status_code == 200


def _get_scope() -> dict:
    response = orchestrator.get("/control/scope")
    assert response.status_code == 200
    return response.json()["scope"]


def _set_scope(scope: dict) -> None:
    response = orchestrator.put("/control/scope", json=scope)
    assert response.status_code == 200


def _enable_apps(scope: dict, required_apps: list[str]) -> dict:
    apps = [str(item) for item in scope.get("apps", []) if isinstance(item, str)]
    lowered = [item.lower() for item in apps]
    for app_name in required_apps:
        if app_name.lower() not in lowered:
            apps.append(app_name)
            lowered.append(app_name.lower())
    return {
        "repos": scope.get("repos", []),
        "workspaces": scope.get("workspaces", []),
        "apps": apps,
    }


def test_hud_root_serves_operator_surface() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Francis Lens" in response.text
    assert "Operator overlay for live work." in response.text


def test_hud_dashboard_exposes_mode_and_cards() -> None:
    response = client.get("/api/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"]["current"] in {"observe", "assist", "pilot", "away"}
    assert "pilot" in body["mode"]["available"]
    assert len(body["cards"]) == 3


def test_hud_bootstrap_aggregates_core_surfaces() -> None:
    response = client.get("/api/bootstrap")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "hud"
    assert body["dashboard"]["surface"] == "dashboard"
    assert body["actions"]["status"] == "ok"
    assert body["missions"]["surface"] == "missions"
    assert body["inbox"]["surface"] == "inbox"
    assert body["runs"]["surface"] == "runs"


def test_hud_bootstrap_reads_live_workspace_state(monkeypatch, tmp_path: Path) -> None:
    workspace_root = (tmp_path / "workspace").resolve()
    monkeypatch.setattr(hud_state, "DEFAULT_WORKSPACE_ROOT", workspace_root)

    _write_json(
        workspace_root / "control" / "state.json",
        {
            "mode": "away",
            "kill_switch": False,
            "scopes": {
                "repos": [str(workspace_root.parent)],
                "workspaces": [str(workspace_root)],
                "apps": ["control", "approvals", "receipts", "lens", "missions"],
            },
        },
    )
    _write_json(
        workspace_root / "missions" / "missions.json",
        {
            "missions": [
                {
                    "id": "mission-live-lens",
                    "title": "Live Lens",
                    "objective": "Show real workspace state in the HUD",
                    "status": "active",
                    "priority": "high",
                    "updated_at": "2026-03-08T12:00:00+00:00",
                },
                {
                    "id": "mission-backlog",
                    "title": "Voice backend",
                    "status": "planned",
                    "updated_at": "2026-03-08T11:00:00+00:00",
                },
            ]
        },
    )
    _write_jsonl(
        workspace_root / "approvals" / "requests.jsonl",
        [
            {
                "id": "approval-1",
                "ts": "2026-03-08T12:01:00+00:00",
                "action": "forge.promote",
                "reason": "Promote a staged capability",
                "requested_by": "architect.ap3pp",
            }
        ],
    )
    _write_jsonl(
        workspace_root / "incidents" / "incidents.jsonl",
        [
            {
                "id": "incident-1",
                "ts": "2026-03-08T12:02:00+00:00",
                "severity": "high",
                "state": "open",
                "summary": "Observer detected sustained error pressure.",
                "source": "observer",
            }
        ],
    )
    _write_jsonl(
        workspace_root / "inbox" / "messages.jsonl",
        [
            {
                "id": "msg-1",
                "ts": "2026-03-08T12:03:00+00:00",
                "title": "Approval waiting",
                "summary": "A forge promotion is awaiting approval.",
                "severity": "alert",
            }
        ],
    )
    _write_json(
        workspace_root / "runs" / "last_run.json",
        {
            "run_id": "run-live",
            "phase": "verify",
            "summary": "Lens is now reading live workspace state.",
        },
    )
    _write_jsonl(
        workspace_root / "runs" / "run_ledger.jsonl",
        [
            {
                "run_id": "run-live",
                "ts": "2026-03-08T12:04:00+00:00",
                "kind": "hud.bootstrap",
            }
        ],
    )

    response = client.get("/api/bootstrap")

    assert response.status_code == 200
    body = response.json()
    assert body["snapshot"]["control"]["mode"] == "away"
    assert body["snapshot"]["objective"]["label"] == "Live Lens"
    assert body["dashboard"]["mode"]["current"] == "away"
    assert body["missions"]["active_count"] == 1
    assert body["missions"]["backlog_count"] == 1
    assert body["incidents"]["open_count"] == 1
    assert body["inbox"]["alert_count"] == 1
    assert body["runs"]["active_run"]["run_id"] == "run-live"


def test_hud_actions_endpoint_proxies_lens_actions() -> None:
    original_mode = _get_mode()
    original_scope = _get_scope()
    try:
        _set_mode("pilot", kill_switch=False)
        _set_scope(_enable_apps(original_scope, ["lens", "control", "receipts", "approvals", "worker"]))

        response = client.get("/api/actions")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert any(chip.get("kind") == "control.panic" for chip in payload.get("action_chips", []))
        assert any(
            chip.get("execute_via", {}).get("endpoint") == "/lens/actions/execute"
            for chip in payload.get("action_chips", [])
        )
    finally:
        _set_scope(original_scope)
        _set_mode(str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_hud_action_execute_can_mutate_and_refresh_snapshot() -> None:
    original_mode = _get_mode()
    original_scope = _get_scope()
    try:
        _set_mode("pilot", kill_switch=False)
        _set_scope(_enable_apps(original_scope, ["lens", "control", "receipts", "approvals"]))

        panic = client.post("/api/actions/execute", json={"kind": "control.panic"})

        assert panic.status_code == 200
        payload = panic.json()
        assert payload["execution"]["status"] == "ok"
        assert payload["execution"]["result"]["after"]["kill_switch"] is True
        assert payload["snapshot"]["control"]["kill_switch"] is True
        assert payload["actions"]["status"] == "ok"
    finally:
        _set_scope(original_scope)
        _set_mode(str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_hud_stream_emits_sse_bootstrap_updates(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_bootstrap_payload(*, max_actions: int = 8) -> dict[str, object]:
        calls["count"] += 1
        return {
            "status": "ok",
            "service": "hud",
            "version": "0.2.0",
            "snapshot": {"count": calls["count"], "max_actions": max_actions},
            "actions": {"status": "ok", "action_chips": [], "blocked_actions": []},
            "dashboard": {"surface": "dashboard", "mode": {"current": "pilot", "available": ["pilot"]}, "cards": []},
            "missions": {"surface": "missions", "active": [], "backlog": []},
            "incidents": {"surface": "incidents", "items": [{"summary": "none"}]},
            "inbox": {"surface": "inbox", "messages": []},
            "runs": {"surface": "runs", "active_run": {"run_id": "r1", "phase": "verify"}},
        }

    monkeypatch.setattr(hud_main, "_build_bootstrap_payload", fake_bootstrap_payload)

    response = client.get("/api/stream", params={"max_seconds": 1, "poll_interval_ms": 50})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.count("event: bootstrap") >= 2
    assert "event: end" in response.text
