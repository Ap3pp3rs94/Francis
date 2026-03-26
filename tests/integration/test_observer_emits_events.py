from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from fastapi.testclient import TestClient

from apps.api.main import app

OBSERVER_MANAGED_KINDS = {
    "cpu.high_load",
    "disk.low_free_space",
    "memory.low_available",
    "repo.high_drift",
}


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


def test_observer_emits_events() -> None:
    root = Path(__file__).resolve().parents[2]
    workspace = root / "workspace"
    logs_path = workspace / "logs" / "francis.log.jsonl"
    decisions_path = workspace / "journals" / "decisions.jsonl"
    incidents_path = workspace / "incidents" / "incidents.jsonl"

    incidents_before = len(_read_jsonl(incidents_path))

    c = TestClient(app)
    with _pilot_mode(c):
        response = c.get("/observer")
        assert response.status_code == 200
        payload = response.json()

        assert payload["status"] == "ok"
        assert "snapshot" in payload
        assert "anomalies" in payload
        assert "score" in payload
        assert "emitted" in payload

        emitted = payload["emitted"]
        assert emitted["opened_incident_count"] >= 0
        assert emitted["refreshed_incident_count"] >= 0
        assert emitted["resolved_incident_count"] >= 0
        assert emitted["deduped_incident_count"] >= 0
        assert emitted["opened_incident_count"] + emitted["refreshed_incident_count"] == len(emitted["incident_ids"])

        logs_after_rows = _read_jsonl(logs_path)
        assert logs_after_rows
        assert any(str(row.get("kind", "")).strip() == "observer.snapshot" for row in logs_after_rows)

        decision_rows = _read_jsonl(decisions_path)
        assert decision_rows
        assert any(str(row.get("kind", "")).strip() == "observer.decision" for row in decision_rows)

        anomalies = payload.get("anomalies", [])
        incidents_after_rows = _read_jsonl(incidents_path)
        assert len(incidents_after_rows) >= incidents_before
        open_managed_kinds = {
            str(row.get("kind", "")).strip().lower()
            for row in incidents_after_rows
            if str(row.get("status", row.get("state", "open"))).strip().lower() == "open"
            and (
                str(row.get("source", "")).strip().lower() == "observer"
                or str(row.get("kind", "")).strip().lower() in OBSERVER_MANAGED_KINDS
            )
        }
        for anomaly in anomalies:
            assert str(anomaly.get("kind", "")).strip().lower() in open_managed_kinds
