from fastapi.testclient import TestClient

from apps.api.main import app


def test_inbox_pipeline() -> None:
    c = TestClient(app)
    r = c.post('/inbox', json={'severity': 'info', 'title': 'hello', 'body': 'world'})
    assert r.status_code == 200
