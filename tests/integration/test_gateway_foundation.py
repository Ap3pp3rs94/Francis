from fastapi.testclient import TestClient

from services.gateway.app.main import app


client = TestClient(app)


def test_gateway_health_sets_request_id() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    body = response.json()
    assert body["service"] == "gateway"
    assert body["request_id"] == response.headers["x-request-id"]


def test_gateway_whoami_reads_headers() -> None:
    response = client.get(
        "/auth/whoami",
        headers={
            "x-francis-user": "architect.ap3pp",
            "x-francis-role": "architect",
            "x-francis-scopes": "lens.read,control.write",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["actor"]["user_id"] == "architect.ap3pp"
    assert body["actor"]["role"] == "architect"
    assert body["actor"]["authenticated"] is True
    assert body["actor"]["scopes"] == ["control.write", "lens.read"]


def test_gateway_admin_status_requires_privileged_role() -> None:
    denied = client.get("/admin/status")
    allowed = client.get(
        "/admin/status",
        headers={
            "x-francis-user": "architect.ap3pp",
            "x-francis-role": "architect",
        },
    )

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["governance"]["rbac"] == "enabled"


def test_gateway_panic_mode_blocks_mutating_admin_calls() -> None:
    response = client.post(
        "/admin/probe",
        json={"action": "sync-state", "dry_run": False},
        headers={
            "x-francis-user": "architect.ap3pp",
            "x-francis-role": "architect",
            "x-francis-panic-mode": "1",
        },
    )

    assert response.status_code == 423
    assert response.json()["reason"] == "panic_mode_enabled"
