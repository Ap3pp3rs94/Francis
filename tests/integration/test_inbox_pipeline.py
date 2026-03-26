from fastapi.testclient import TestClient

from apps.api.main import app
from tests.integration.workspace_state import INBOX_RUNTIME_PATHS, isolated_workspace_files


def test_inbox_pipeline() -> None:
    with isolated_workspace_files(INBOX_RUNTIME_PATHS):
        c = TestClient(app)
        r = c.post('/inbox', json={'severity': 'info', 'title': 'hello', 'body': 'world'})
        assert r.status_code == 200
