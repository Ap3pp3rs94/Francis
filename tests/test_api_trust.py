from __future__ import annotations

import json
from pathlib import Path


def test_trust_state_history_events_and_adjust_lifecycle(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    state_initial = client.get("/trust/state")
    assert state_initial.status_code == 200
    state_initial_body = state_initial.json()
    assert state_initial_body["ok"] is True
    assert isinstance(state_initial_body.get("level"), int)

    policy = client.get("/trust/policy")
    assert policy.status_code == 200
    policy_body = policy.json()
    assert policy_body["ok"] is True
    assert isinstance(policy_body["policy"], dict)

    first = client.post(
        "/trust/adjust",
        json={
            "op": "set",
            "value": 4,
            "reason": "bootstrap trust",
            "actor": "ops",
            "domain": "platform",
            "idempotency_key": "corr-a",
            "ts": 1_700_000_001,
        },
    )
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["ok"] is True
    assert first_body["applied"] is True
    assert first_body["level"] == 4

    second = client.post(
        "/trust/adjust",
        json={
            "op": "increase",
            "delta": 3,
            "reason": "good streak",
            "actor": "ops",
            "domain": "platform",
            "idempotency_key": "corr-b",
            "ts": 1_700_000_002,
        },
    )
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["ok"] is True
    assert second_body["level"] == 7

    third = client.post(
        "/trust/adjust",
        json={
            "op": "decrease",
            "delta": 2,
            "reason": "regression observed",
            "actor": "sre",
            "domain": "security",
            "idempotency_key": "corr-c",
            "ts": 1_700_000_003,
        },
    )
    assert third.status_code == 200
    third_body = third.json()
    assert third_body["ok"] is True
    assert third_body["level"] == 5

    state_after = client.get("/trust/state")
    assert state_after.status_code == 200
    state_after_body = state_after.json()
    assert state_after_body["level"] == 5
    assert state_after_body["global_level"] == 5

    history_page1 = client.get("/trust/history?limit=2")
    assert history_page1.status_code == 200
    history_page1_body = history_page1.json()
    assert len(history_page1_body["items"]) == 2
    assert history_page1_body["total"] >= 3
    assert history_page1_body["next_cursor"] is not None

    history_page2 = client.get(f"/trust/history?limit=2&cursor={history_page1_body['next_cursor']}")
    assert history_page2.status_code == 200
    history_page2_body = history_page2.json()
    assert history_page2_body["items"]

    events_filtered = client.get("/trust/events?actor=ops&domain=platform&search=streak")
    assert events_filtered.status_code == 200
    events_filtered_body = events_filtered.json()
    assert events_filtered_body["items"]
    assert all(str(item.get("actor")).lower() == "ops" for item in events_filtered_body["items"])
    assert all(str(item.get("domain")).lower() == "platform" for item in events_filtered_body["items"])

    legacy_set = client.post("/trust/set", json={"level": 1, "reason": "legacy_api", "ts": 1_700_000_004})
    assert legacy_set.status_code == 200
    legacy_set_body = legacy_set.json()
    assert legacy_set_body["ok"] is True
    assert legacy_set_body["level"] == 1


def test_trust_aliases_policy_update_and_persistence(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mutate = client.post(
        "/trust/mutate",
        json={
            "op": "set",
            "value": 2,
            "reason": "alias_mutate",
            "actor": "api-test",
            "domain": "ops",
            "ts": 1_700_000_010,
        },
    )
    assert mutate.status_code == 200
    mutate_body = mutate.json()
    assert mutate_body["ok"] is True
    assert mutate_body["level"] == 2

    history_alias = client.get("/trust/timeline?limit=10")
    assert history_alias.status_code == 200
    history_alias_body = history_alias.json()
    assert isinstance(history_alias_body["items"], list)
    assert history_alias_body["items"]

    events_alias = client.get("/trust/log?kind=adjust")
    assert events_alias.status_code == 200
    events_alias_body = events_alias.json()
    assert isinstance(events_alias_body["items"], list)
    assert events_alias_body["items"]
    assert all(str(item.get("kind")).lower() == "adjust" for item in events_alias_body["items"])

    config_alias = client.get("/trust/config")
    assert config_alias.status_code == 200
    assert config_alias.json()["ok"] is True

    policy_update = client.post(
        "/trust/policy",
        json={
            "mode": "strict",
            "thresholds": {"max_level": 8},
            "gates": {"approvals_required": True},
            "meta": {"updated_by": "test"},
        },
    )
    assert policy_update.status_code == 200
    policy_update_body = policy_update.json()
    assert policy_update_body["ok"] is True
    assert policy_update_body["policy"]["mode"] == "strict"
    assert policy_update_body["policy"]["thresholds"]["max_level"] == 8
    assert policy_update_body["policy"]["gates"]["approvals_required"] is True

    state_path = data_root / "trust" / "levels" / "current_state.json"
    history_path = data_root / "trust" / "levels" / "history.jsonl"
    policy_path = data_root / "trust" / "policy.json"
    assert state_path.exists()
    assert history_path.exists()
    assert policy_path.exists()

    state_data = json.loads(state_path.read_text(encoding="utf-8"))
    assert int(state_data["global_level"]) == 2

    history_lines = [line for line in history_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert history_lines
    parsed_events = [json.loads(line) for line in history_lines]
    assert any(str(item.get("kind")).lower() == "adjust" for item in parsed_events)

    policy_data = json.loads(policy_path.read_text(encoding="utf-8"))
    assert policy_data["mode"] == "strict"


def test_system_trust_prefix_aliases(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    set_via_system = client.post(
        "/system/trust/adjust",
        json={
            "op": "set",
            "value": 6,
            "reason": "system prefix set",
            "actor": "system-ui",
            "domain": "platform",
            "ts": 1_700_000_020,
        },
    )
    assert set_via_system.status_code == 200
    set_via_system_body = set_via_system.json()
    assert set_via_system_body["ok"] is True
    assert set_via_system_body["level"] == 6

    state = client.get("/system/trust/state")
    assert state.status_code == 200
    state_body = state.json()
    assert state_body["ok"] is True
    assert state_body["level"] == 6

    history = client.get("/system/trust/history?limit=5")
    assert history.status_code == 200
    history_body = history.json()
    assert isinstance(history_body["items"], list)
    assert history_body["items"]
    assert any(int(item.get("level")) == 6 for item in history_body["items"])

    events = client.get("/system/trust/events?actor=system-ui")
    assert events.status_code == 200
    events_body = events.json()
    assert isinstance(events_body["items"], list)
    assert events_body["items"]
    assert all(str(item.get("actor")).lower() == "system-ui" for item in events_body["items"])

    policy_get = client.get("/system/trust/policy")
    assert policy_get.status_code == 200
    assert policy_get.json()["ok"] is True

    policy_post = client.post("/system/trust/policy", json={"mode": "learning", "meta": {"source": "system-prefix"}})
    assert policy_post.status_code == 200
    policy_post_body = policy_post.json()
    assert policy_post_body["ok"] is True
    assert policy_post_body["policy"]["mode"] == "learning"
