from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator
from uuid import uuid4
from contextlib import contextmanager

from fastapi.testclient import TestClient

from apps.api.main import app


def _read_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        except Exception:
            continue
    return rows


def _missions_file() -> Path:
    return Path(__file__).resolve().parents[2] / "workspace" / "missions" / "missions.json"


def _history_file() -> Path:
    return Path(__file__).resolve().parents[2] / "workspace" / "missions" / "history.jsonl"


def _jobs_file() -> Path:
    return Path(__file__).resolve().parents[2] / "workspace" / "queue" / "jobs.jsonl"


def _deadletter_file() -> Path:
    return Path(__file__).resolve().parents[2] / "workspace" / "queue" / "deadletter.jsonl"


def _run_ledger_file() -> Path:
    return Path(__file__).resolve().parents[2] / "workspace" / "runs" / "run_ledger.jsonl"


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


@contextmanager
def _pilot_mode(client: TestClient) -> Iterator[None]:
    original_mode = _get_mode(client)
    _set_mode(client, "pilot", kill_switch=False)
    try:
        yield
    finally:
        _set_mode(
            client,
            str(original_mode.get("mode", "pilot")),
            bool(original_mode.get("kill_switch", False)),
        )


def test_create_mission_persists_and_queues() -> None:
    c = TestClient(app)
    title = f"Mission-{uuid4()}"

    with _pilot_mode(c):
        before_jobs = len(_read_jsonl(_jobs_file()))
        before_ledger = len(_read_jsonl(_run_ledger_file()))

        r = c.post(
            "/missions",
            json={
                "title": title,
                "objective": "Ship stage 3",
                "priority": "high",
                "steps": ["design", "implement"],
            },
        )
        assert r.status_code == 200
        payload = r.json()
        mission = payload["mission"]
        mission_id = mission["id"]

        missions_doc = _read_json(_missions_file(), {"missions": []})
        assert isinstance(missions_doc, dict)
        missions = missions_doc.get("missions", [])
        assert any(isinstance(m, dict) and m.get("id") == mission_id for m in missions)

        jobs_after = _read_jsonl(_jobs_file())
        assert len(jobs_after) >= before_jobs + 1
        assert any(job.get("mission_id") == mission_id for job in jobs_after)

        ledger_after = _read_jsonl(_run_ledger_file())
        assert len(ledger_after) >= before_ledger + 1
        assert any(
            row.get("kind") == "mission.created" and row.get("summary", {}).get("mission_id") == mission_id
            for row in ledger_after
        )


def test_tick_advances_mission_and_history() -> None:
    c = TestClient(app)
    title = f"TickMission-{uuid4()}"

    with _pilot_mode(c):
        create = c.post(
            "/missions",
            json={
                "title": title,
                "objective": "Advance mission",
                "steps": ["step-1", "step-2"],
            },
        )
        assert create.status_code == 200
        mission_id = create.json()["mission"]["id"]
        history_before = len(_read_jsonl(_history_file()))

        tick_1 = c.post(f"/missions/{mission_id}/tick")
        assert tick_1.status_code == 200
        m1 = tick_1.json()["mission"]
        assert m1["next_step_index"] == 1
        assert m1["status"] in {"active", "completed"}

        tick_2 = c.post(f"/missions/{mission_id}/tick")
        assert tick_2.status_code == 200
        m2 = tick_2.json()["mission"]
        assert m2["status"] == "completed"
        assert m2["next_step_index"] == 2

        history_after_rows = _read_jsonl(_history_file())
        assert len(history_after_rows) >= history_before + 2
        mission_history = [row for row in history_after_rows if row.get("mission_id") == mission_id]
        kinds = [row.get("event") for row in mission_history]
        assert "mission.tick" in kinds


def test_failed_tick_goes_to_deadletter() -> None:
    c = TestClient(app)
    title = f"FailMission-{uuid4()}"

    with _pilot_mode(c):
        create = c.post(
            "/missions",
            json={
                "title": title,
                "objective": "Fail mission",
                "steps": ["step-1"],
            },
        )
        assert create.status_code == 200
        mission_id = create.json()["mission"]["id"]
        dead_before = len(_read_jsonl(_deadletter_file()))

        tick = c.post(
            f"/missions/{mission_id}/tick",
            json={"force_fail": True, "reason": "test failure path"},
        )
        assert tick.status_code == 200
        payload = tick.json()
        assert payload["mission"]["status"] == "failed"

        dead_after = _read_jsonl(_deadletter_file())
        assert len(dead_after) >= dead_before + 1
        assert any(row.get("mission_id") == mission_id for row in dead_after)


def test_mission_rbac_denies_observer_create() -> None:
    c = TestClient(app)
    with _pilot_mode(c):
        response = c.post(
            "/missions",
            headers={"x-francis-role": "observer"},
            json={"title": f"Denied-{uuid4()}", "steps": ["a"]},
        )
        assert response.status_code == 403
        assert "RBAC denied" in response.json().get("detail", "")


def test_tick_idempotency_replays_without_double_advance() -> None:
    c = TestClient(app)
    with _pilot_mode(c):
        create = c.post(
            "/missions",
            json={"title": f"Idempotent-{uuid4()}", "steps": ["s1", "s2"]},
        )
        assert create.status_code == 200
        mission_id = create.json()["mission"]["id"]

        key = str(uuid4())
        tick_1 = c.post(
            f"/missions/{mission_id}/tick",
            headers={"x-idempotency-key": key},
        )
        assert tick_1.status_code == 200
        payload_1 = tick_1.json()
        assert payload_1["mission"]["next_step_index"] == 1

        tick_2 = c.post(
            f"/missions/{mission_id}/tick",
            headers={"x-idempotency-key": key},
        )
        assert tick_2.status_code == 200
        payload_2 = tick_2.json()
        assert payload_2["mission"]["next_step_index"] == 1
        assert payload_2["step_executed"] == payload_1["step_executed"]


def test_presence_briefing_includes_active_mission_count() -> None:
    c = TestClient(app)
    with _pilot_mode(c):
        create = c.post(
            "/missions",
            json={"title": f"PresenceMission-{uuid4()}", "steps": ["s1", "s2"]},
        )
        assert create.status_code == 200

        briefing = c.post("/presence/briefing")
        assert briefing.status_code == 200
        message = briefing.json()["message"]
        body = str(message.get("body", ""))
        assert "Missions:" in body
