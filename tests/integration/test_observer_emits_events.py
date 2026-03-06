from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def test_observer_emits_events() -> None:
    root = Path(__file__).resolve().parents[2]
    workspace = root / "workspace"
    logs_path = workspace / "logs" / "francis.log.jsonl"
    decisions_path = workspace / "journals" / "decisions.jsonl"
    incidents_path = workspace / "incidents" / "incidents.jsonl"

    logs_before = len(_read_jsonl(logs_path))
    decisions_before = len(_read_jsonl(decisions_path))
    incidents_before = len(_read_jsonl(incidents_path))

    c = TestClient(app)
    response = c.get("/observer")
    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "ok"
    assert "snapshot" in payload
    assert "anomalies" in payload
    assert "score" in payload
    assert "emitted" in payload

    logs_after_rows = _read_jsonl(logs_path)
    assert len(logs_after_rows) >= logs_before + 1
    assert logs_after_rows[-1].get("kind") == "observer.snapshot"

    decisions_after = len(_read_jsonl(decisions_path))
    assert decisions_after >= decisions_before + 1

    anomalies = payload.get("anomalies", [])
    incidents_after = len(_read_jsonl(incidents_path))
    assert incidents_after >= incidents_before + len(anomalies)

