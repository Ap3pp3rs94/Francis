from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app


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
    return {
        "repos": scope.get("repos", []),
        "workspaces": scope.get("workspaces", []),
        "apps": apps,
    }


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    raw = _read_text(path)
    rows: list[dict[str, object]] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _restore_text(path: Path, content: str, existed: bool) -> None:
    if existed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    elif path.exists():
        path.unlink()


def test_federation_state_initializes_local_node() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    topology_path = workspace / "federation" / "topology.json"
    topology_before_exists = topology_path.exists()
    topology_before = _read_text(topology_path)

    try:
        if topology_path.exists():
            topology_path.unlink()

        with TestClient(app) as client:
            original_scope = _get_scope(client)
            try:
                _set_scope(client, _enable_apps(original_scope, ["federation"]))
                response = client.get("/federation/state")
            finally:
                _set_scope(client, original_scope)

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["counts"]["paired"] == 0
        assert payload["local_node"]["node_id"]
        assert payload["local_node"]["local"] is True
        assert "Local node" in payload["summary"]
    finally:
        _restore_text(topology_path, topology_before, topology_before_exists)


def test_federation_pair_heartbeat_and_revoke_flow() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    topology_path = workspace / "federation" / "topology.json"
    run_ledger_path = workspace / "runs" / "run_ledger.jsonl"
    log_path = workspace / "logs" / "francis.log.jsonl"
    decisions_path = workspace / "journals" / "decisions.jsonl"
    topology_before_exists = topology_path.exists()
    topology_before = _read_text(topology_path)
    run_ledger_before_exists = run_ledger_path.exists()
    run_ledger_before = _read_text(run_ledger_path)
    log_before_exists = log_path.exists()
    log_before = _read_text(log_path)
    decisions_before_exists = decisions_path.exists()
    decisions_before = _read_text(decisions_path)

    try:
        with TestClient(app) as client:
            original_mode = _get_mode(client)
            original_scope = _get_scope(client)
            try:
                _set_mode(client, "assist", kill_switch=False)
                _set_scope(client, _enable_apps(original_scope, ["federation", "control", "approvals", "receipts", "lens"]))

                pair = client.post(
                    "/federation/pair",
                    json={
                        "label": "Home Node",
                        "role": "always_on",
                        "trust_level": "scoped",
                        "apps": ["control", "approvals", "lens"],
                        "remote_approvals": True,
                        "away_continuity": True,
                        "receipt_summary": True,
                        "notes": "Always-on home node for away continuity.",
                    },
                )
                assert pair.status_code == 200
                pair_payload = pair.json()
                node_id = str(pair_payload["node"]["node_id"]).strip()
                local_node_id = str(pair_payload["topology"]["local_node"]["node_id"]).strip()
                assert node_id
                assert local_node_id
                assert pair_payload["node"]["status"] == "active"

                state = client.get("/federation/state")
                assert state.status_code == 200
                state_payload = state.json()
                assert state_payload["counts"]["paired"] >= 1
                assert any(str(row.get("node_id", "")).strip() == node_id for row in state_payload["paired_nodes"])

                heartbeat = client.post(
                    f"/federation/nodes/{node_id}/heartbeat",
                    json={"status": "stale", "sync_summary": "Home node missed its last sync window."},
                )
                assert heartbeat.status_code == 200
                assert heartbeat.json()["node"]["status"] == "stale"

                revoke = client.post(
                    f"/federation/nodes/{node_id}/revoke",
                    json={"reason": "Trust narrowed after stale continuity."},
                )
                assert revoke.status_code == 200
                revoke_payload = revoke.json()
                assert revoke_payload["node"]["status"] == "revoked"
                assert revoke_payload["topology"]["counts"]["revoked"] >= 1
            finally:
                _set_scope(client, original_scope)
                _set_mode(
                    client,
                    str(original_mode.get("mode", "pilot")),
                    bool(original_mode.get("kill_switch", False)),
                )

        ledger_rows = _read_jsonl(run_ledger_path)
        paired_receipt = next(
            row for row in reversed(ledger_rows) if str(row.get("kind", "")).strip() == "federation.node.paired"
        )
        heartbeat_receipt = next(
            row for row in reversed(ledger_rows) if str(row.get("kind", "")).strip() == "federation.node.heartbeat"
        )
        revoked_receipt = next(
            row for row in reversed(ledger_rows) if str(row.get("kind", "")).strip() == "federation.node.revoked"
        )
        paired_summary = paired_receipt.get("summary", {}) if isinstance(paired_receipt.get("summary"), dict) else {}
        heartbeat_summary = (
            heartbeat_receipt.get("summary", {}) if isinstance(heartbeat_receipt.get("summary"), dict) else {}
        )
        revoked_summary = revoked_receipt.get("summary", {}) if isinstance(revoked_receipt.get("summary"), dict) else {}
        assert paired_summary["local_node_id"] == local_node_id
        assert paired_summary["target_node_id"] == node_id
        assert heartbeat_summary["target_node_id"] == node_id
        assert revoked_summary["target_node_id"] == node_id

        topology = json.loads(_read_text(topology_path))
        paired_node = next(row for row in topology["paired_nodes"] if row["node_id"] == node_id)
        assert paired_node["status"] == "revoked"
        assert paired_node["revocation_reason"] == "Trust narrowed after stale continuity."
    finally:
        _restore_text(topology_path, topology_before, topology_before_exists)
        _restore_text(run_ledger_path, run_ledger_before, run_ledger_before_exists)
        _restore_text(log_path, log_before, log_before_exists)
        _restore_text(decisions_path, decisions_before, decisions_before_exists)
