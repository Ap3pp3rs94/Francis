from __future__ import annotations

import json
from pathlib import Path


def test_credentials_request_revoke_and_scopes(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    scopes_dir = data_root / "credentials" / "scopes"
    scopes_dir.mkdir(parents=True, exist_ok=True)
    (scopes_dir / "custom.scopes.yaml").write_text(
        "\n".join(
            [
                "schema:",
                '  name: "francis.credentials.scopes"',
                '  version: "1.0"',
                "scopes:",
                '  - scope_id: "openai_readonly"',
                '    name: "OpenAI Readonly"',
                '    status: "active"',
                '    provider: "openai"',
                "    audit:",
                '      risk_level: "low"',
                '  - scope_id: "github_repo_readonly"',
                '    name: "GitHub Repo Readonly"',
                '    status: "active"',
                '    provider: "github"',
                "    audit:",
                '      risk_level: "medium"',
            ]
        ),
        encoding="utf-8",
    )

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    scopes = client.get("/credentials/scopes")
    assert scopes.status_code == 200
    scopes_body = scopes.json()
    assert isinstance(scopes_body.get("items"), list)
    scope_ids = {str(item.get("id")) for item in scopes_body["items"]}
    assert "openai_readonly" in scope_ids
    assert "github_repo_readonly" in scope_ids

    requested = client.post(
        "/credentials/request",
        json={
            "scope_id": "openai_readonly",
            "provider": "openai",
            "type": "api_key",
            "label": "OpenAI Primary",
            "reason": "integration_test",
            "meta": {"ticket": "FR-123"},
        },
    )
    assert requested.status_code == 200
    requested_body = requested.json()
    assert requested_body["ok"] is True
    credential_id = str(requested_body["id"])
    approval_id = str(requested_body["approval_id"])
    assert requested_body["status"] == "pending"
    assert requested_body["request_id"]

    approval_file = data_root / "approvals" / "pending" / f"{approval_id}.json"
    assert approval_file.exists()

    listed_pending = client.get("/credentials/list?status=pending")
    assert listed_pending.status_code == 200
    listed_pending_body = listed_pending.json()
    pending_ids = {str(item.get("id")) for item in listed_pending_body["items"]}
    assert credential_id in pending_ids

    revoked = client.post("/credentials/revoke", json={"id": credential_id, "reason": "cleanup"})
    assert revoked.status_code == 200
    revoked_body = revoked.json()
    assert revoked_body["ok"] is True
    assert revoked_body["id"] == credential_id
    assert revoked_body["status"] == "pending"
    assert revoked_body["approval_id"]

    delegations = client.get("/credentials/delegations")
    assert delegations.status_code == 200
    delegations_body = delegations.json()
    assert isinstance(delegations_body.get("items"), list)
    delegation_ids = {str(item.get("id")) for item in delegations_body["items"]}
    assert approval_id in delegation_ids
    assert str(revoked_body["approval_id"]) in delegation_ids

    registry_path = data_root / "credentials" / "_registry.json"
    assert registry_path.exists()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert credential_id in registry["credentials"]


def test_credentials_request_approval_reconciles_active_status(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    requested = client.post(
        "/credentials/request",
        json={
            "scope_id": "openai_readonly",
            "provider": "openai",
            "type": "api_key",
            "label": "OpenAI Active",
            "reason": "integration_test",
        },
    )
    assert requested.status_code == 200
    requested_body = requested.json()
    assert requested_body["ok"] is True
    credential_id = str(requested_body["id"])
    approval_id = str(requested_body["approval_id"])
    assert requested_body["status"] == "pending"

    approved = client.post("/approvals/decision", json={"id": approval_id, "action": "approve"})
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    listed = client.get("/credentials/list?status=active")
    assert listed.status_code == 200
    listed_body = listed.json()
    items = [item for item in listed_body["items"] if item.get("id") == credential_id]
    assert len(items) == 1
    assert items[0]["status"] == "active"
    assert items[0]["meta"]["approval_status"] == "approved"

    registry = json.loads((data_root / "credentials" / "_registry.json").read_text(encoding="utf-8"))
    record = registry["credentials"][credential_id]
    assert record["status"] == "active"
    assert record["meta"]["approval_status"] == "approved"


def test_credentials_revocation_approval_reconciles_revoked_status(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    requested = client.post(
        "/credentials/request",
        json={
            "scope_id": "openai_readonly",
            "provider": "openai",
            "type": "api_key",
            "label": "OpenAI Revoked",
            "reason": "integration_test",
        },
    )
    assert requested.status_code == 200
    requested_body = requested.json()
    credential_id = str(requested_body["id"])
    request_approval_id = str(requested_body["approval_id"])

    approved_request = client.post("/approvals/decision", json={"id": request_approval_id, "action": "approve"})
    assert approved_request.status_code == 200
    assert approved_request.json()["ok"] is True

    active = client.get("/credentials/list?status=active")
    assert active.status_code == 200
    active_items = [item for item in active.json()["items"] if item.get("id") == credential_id]
    assert len(active_items) == 1
    assert active_items[0]["status"] == "active"

    revoked = client.post("/credentials/revoke", json={"id": credential_id, "reason": "cleanup"})
    assert revoked.status_code == 200
    revoked_body = revoked.json()
    assert revoked_body["ok"] is True
    revoke_approval_id = str(revoked_body["approval_id"])

    approved_revoke = client.post("/approvals/decision", json={"id": revoke_approval_id, "action": "approve"})
    assert approved_revoke.status_code == 200
    assert approved_revoke.json()["ok"] is True

    listed = client.get("/credentials/list?status=revoked")
    assert listed.status_code == 200
    listed_body = listed.json()
    items = [item for item in listed_body["items"] if item.get("id") == credential_id]
    assert len(items) == 1
    assert items[0]["status"] == "revoked"
    assert items[0]["meta"]["revocation_approval_status"] == "approved"
    assert items[0]["meta"]["revocation_requested"] is False

    registry = json.loads((data_root / "credentials" / "_registry.json").read_text(encoding="utf-8"))
    record = registry["credentials"][credential_id]
    assert record["status"] == "revoked"
    assert record["meta"]["revocation_approval_status"] == "approved"
    assert record["meta"]["revocation_requested"] is False


def test_credentials_seed_from_vault_and_parse_delegation_files(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    credentials_dir = data_root / "credentials"
    credentials_dir.mkdir(parents=True, exist_ok=True)

    vault_lines = [
        {
            "emitted_at": "2026-01-01T00:01:12Z",
            "event_type": "credential.use",
            "actor": {"id": "francis"},
            "request": {"domain_id": "operations"},
            "credential": {
                "credential_id": "openai_api_key_default",
                "credential_type": "api_key",
                "provider": "openai",
                "scope_set_id": "llm.generate",
                "delegation_id": "del_ops_read",
            },
        },
        {
            "emitted_at": "2026-01-01T00:05:00Z",
            "event_type": "credential.use",
            "actor": {"id": "francis"},
            "request": {"domain_id": "operations"},
            "credential": {
                "credential_id": "openai_api_key_default",
                "credential_type": "api_key",
                "provider": "openai",
                "scope_set_id": "llm.generate",
                "delegation_id": "del_ops_read",
            },
        },
    ]
    (credentials_dir / "vault.db").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in vault_lines),
        encoding="utf-8",
    )

    delegations_dir = credentials_dir / "delegations"
    delegations_dir.mkdir(parents=True, exist_ok=True)
    (delegations_dir / "ops.delegate.yaml").write_text(
        "\n".join(
            [
                "delegation:",
                '  id: "del_ops_read"',
                '  status: "active"',
                "  actors:",
                "    grantor:",
                '      id: "operator:alice"',
                "    delegate:",
                '      id: "agent:francis"',
                "  scopes:",
                '    - scope_id: "llm.generate"',
                "  audit:",
                '    created_at: "2026-01-01T00:00:00Z"',
                "  meta:",
                '    description: "Allow llm.generate for ops tasks"',
            ]
        ),
        encoding="utf-8",
    )

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    listed = client.get("/credentials/list")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert isinstance(listed_body.get("items"), list)
    seeded = [item for item in listed_body["items"] if item.get("id") == "openai_api_key_default"]
    assert seeded
    assert seeded[0]["provider"] == "openai"
    assert seeded[0]["scope_id"] == "llm.generate"
    assert seeded[0]["status"] == "active"

    scopes = client.get("/credentials/scopes")
    assert scopes.status_code == 200
    scope_ids = {str(item.get("id")) for item in scopes.json()["items"]}
    assert "llm.generate" in scope_ids

    delegations = client.get("/credentials/delegations")
    assert delegations.status_code == 200
    delegations_body = delegations.json()
    assert isinstance(delegations_body.get("items"), list)
    target = [item for item in delegations_body["items"] if item.get("id") == "del_ops_read"]
    assert target
    assert target[0]["from"] == "operator:alice"
    assert target[0]["to"] == "agent:francis"
    assert target[0]["scope_id"] == "llm.generate"

    status = client.get("/credentials/status")
    assert status.status_code == 200
    status_body = status.json()
    assert status_body["ok"] is True
    assert status_body["status"] == "ready"
    assert status_body["credentials"] >= 1
