from fastapi.testclient import TestClient

from apps.api.main import app


def test_api_health() -> None:
    c = TestClient(app)
    r = c.get('/health')
    assert r.status_code == 200
