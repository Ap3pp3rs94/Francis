from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import app


def test_presence_state_returns_counts_and_ledger():
    c = TestClient(app)

    # Start clean-ish: state should still work even if inbox/ledger missing
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
    c = TestClient(app)

    # Write an alert message into inbox
    r1 = c.post("/inbox", json={"severity": "alert", "title": "Test Alert", "body": "Something needs attention"})
    assert r1.status_code == 200

    # Generate briefing - should reference real alert count
    r2 = c.post("/presence/briefing")
    assert r2.status_code == 200
    payload = r2.json()
    msg = payload["message"]

    # Grounding: title should mention attention/alerts when alerts exist
    assert "Attention required" in msg["title"] or "alerts" in msg["title"]

    # And briefing should land in inbox
    inbox = c.get("/inbox").json()
    assert len(inbox) >= 1

    # State used should report alerts > 0
    st_used = payload["state_used"]
    assert st_used["inbox_alerts"] >= 1


def test_ledger_accumulates_presence_events():
    c = TestClient(app)

    # Generate a state + briefing (which should append ledger events)
    c.get("/presence/state")
    c.post("/presence/briefing")

    # Call /presence/state again; it should include last_ledger with at least one presence event
    r = c.get("/presence/state")
    assert r.status_code == 200
    st = r.json()["state"]
    kinds = [e.get("kind") for e in st.get("last_ledger", []) if isinstance(e, dict)]
    assert any(k in ("presence.state", "presence.briefing") for k in kinds)

