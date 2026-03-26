from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from fastapi.testclient import TestClient

from apps.api.main import app


def _stash(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _restore(path: Path, content: str | None) -> None:
    if content is None:
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@contextmanager
def _isolated_presence_workspace() -> Iterator[None]:
    root = Path(__file__).resolve().parents[1] / "workspace"
    paths = [
        root / "inbox" / "messages.jsonl",
        root / "brain" / "run_ledger.jsonl",
    ]
    snapshots = {path: _stash(path) for path in paths}
    try:
        yield
    finally:
        for path, content in snapshots.items():
            _restore(path, content)


def test_presence_state_returns_counts_and_ledger():
    with _isolated_presence_workspace():
        c = TestClient(app)

        r = c.get("/presence/state")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        st = data["state"]
        assert "inbox_count" in st
        assert "inbox_alerts" in st
        assert "last_ledger" in st
        assert isinstance(st["last_ledger"], list)


def test_grounded_briefing_headline_changes_with_alerts():
    with _isolated_presence_workspace():
        c = TestClient(app)

        r1 = c.post("/inbox", json={"severity": "alert", "title": "Test Alert", "body": "Something needs attention"})
        assert r1.status_code == 200

        r2 = c.post("/presence/briefing")
        assert r2.status_code == 200
        payload = r2.json()
        msg = payload["message"]

        assert "Attention required" in msg["title"] or "alerts" in msg["title"]

        inbox = c.get("/inbox").json()
        assert len(inbox) >= 1

        st_used = payload["state_used"]
        assert st_used["inbox_alerts"] >= 1


def test_ledger_accumulates_presence_events():
    with _isolated_presence_workspace():
        c = TestClient(app)

        c.get("/presence/state")
        c.post("/presence/briefing")

        r = c.get("/presence/state")
        assert r.status_code == 200
        st = r.json()["state"]
        kinds = [e.get("kind") for e in st.get("last_ledger", []) if isinstance(e, dict)]
        assert any(k in ("presence.state", "presence.briefing") for k in kinds)


def test_presence_briefing_reuses_managed_inbox_message():
    with _isolated_presence_workspace():
        c = TestClient(app)

        c.post("/inbox", json={"severity": "alert", "title": "Test Alert", "body": "Something needs attention"})
        first = c.post("/presence/briefing")
        assert first.status_code == 200
        first_message = first.json()["message"]

        second = c.post("/presence/briefing")
        assert second.status_code == 200
        second_message = second.json()["message"]

        assert first_message["id"] == second_message["id"]

        inbox = c.get("/inbox")
        assert inbox.status_code == 200
        rows = inbox.json()
        briefing_rows = [row for row in rows if str(row.get("message_key", "")) == "presence.briefing"]
        assert len(briefing_rows) == 1
