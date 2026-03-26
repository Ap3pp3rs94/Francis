from __future__ import annotations

import json
from pathlib import Path

from services.observer.app.emitter import ObserverEmitter


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_emit_cycle_reuses_open_incident_and_resolves_when_clear(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    emitter = ObserverEmitter(workspace)

    opened = emitter.emit_cycle(
        run_id="run-open",
        snapshot={"disk": {"free_percent": 4.0}},
        anomalies=[
            {
                "kind": "disk.low_free_space",
                "severity": "warning",
                "message": "Disk free space is low (4.00%).",
                "evidence": {"free_percent": 4.0},
            }
        ],
        score={"level": "warning", "headline": "1 warning anomaly(s) detected."},
    )
    assert opened["opened_incident_count"] == 1
    assert opened["refreshed_incident_count"] == 0

    incidents_path = workspace / "incidents" / "incidents.jsonl"
    first_rows = _read_jsonl(incidents_path)
    assert len(first_rows) == 1
    first_id = first_rows[0]["id"]
    assert first_rows[0]["status"] == "open"
    assert first_rows[0]["seen_count"] == 1

    refreshed = emitter.emit_cycle(
        run_id="run-refresh",
        snapshot={"disk": {"free_percent": 2.5}},
        anomalies=[
            {
                "kind": "disk.low_free_space",
                "severity": "critical",
                "message": "Disk free space is low (2.50%).",
                "evidence": {"free_percent": 2.5},
            }
        ],
        score={"level": "critical", "headline": "1 critical anomaly(s) detected."},
    )
    assert refreshed["opened_incident_count"] == 0
    assert refreshed["refreshed_incident_count"] == 1
    assert refreshed["incident_ids"] == [first_id]

    second_rows = _read_jsonl(incidents_path)
    assert len(second_rows) == 1
    assert second_rows[0]["id"] == first_id
    assert second_rows[0]["status"] == "open"
    assert second_rows[0]["severity"] == "critical"
    assert second_rows[0]["seen_count"] == 2
    assert second_rows[0]["last_seen_run_id"] == "run-refresh"

    resolved = emitter.emit_cycle(
        run_id="run-resolve",
        snapshot={"disk": {"free_percent": 30.0}},
        anomalies=[],
        score={"level": "healthy", "headline": "No anomalies detected."},
    )
    assert resolved["resolved_incident_count"] == 1

    final_rows = _read_jsonl(incidents_path)
    assert len(final_rows) == 1
    assert final_rows[0]["status"] == "resolved"
    assert final_rows[0]["resolved_by_run_id"] == "run-resolve"
    assert final_rows[0]["resolution_reason"] == "observer_scan_clear"


def test_emit_cycle_dedupes_existing_open_observer_incidents(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    incidents_path = workspace / "incidents" / "incidents.jsonl"
    _write_jsonl(
        incidents_path,
        [
            {
                "id": "observer-1",
                "ts": "2026-03-24T00:00:00+00:00",
                "run_id": "older-open",
                "severity": "warning",
                "kind": "disk.low_free_space",
                "message": "Disk free space is low (4.00%).",
                "evidence": {"free_percent": 4.0},
                "status": "open",
            },
            {
                "id": "observer-2",
                "ts": "2026-03-24T00:05:00+00:00",
                "run_id": "latest-open",
                "severity": "warning",
                "kind": "disk.low_free_space",
                "message": "Disk free space is low (3.50%).",
                "evidence": {"free_percent": 3.5},
                "status": "open",
            },
            {
                "id": "security-1",
                "ts": "2026-03-24T00:10:00+00:00",
                "run_id": "security-run",
                "severity": "critical",
                "kind": "security.untrusted_input",
                "message": "Prompt injection attempt detected.",
                "evidence": {"surface": "mail"},
                "status": "open",
            },
        ],
    )

    emitter = ObserverEmitter(workspace)
    result = emitter.emit_cycle(
        run_id="run-dedupe",
        snapshot={"disk": {"free_percent": 2.0}},
        anomalies=[
            {
                "kind": "disk.low_free_space",
                "severity": "critical",
                "message": "Disk free space is low (2.00%).",
                "evidence": {"free_percent": 2.0},
            }
        ],
        score={"level": "critical", "headline": "1 critical anomaly(s) detected."},
    )
    assert result["opened_incident_count"] == 0
    assert result["refreshed_incident_count"] == 1
    assert result["deduped_incident_count"] == 1

    rows = _read_jsonl(incidents_path)
    observer_rows = [row for row in rows if str(row.get("kind")) == "disk.low_free_space"]
    assert len(observer_rows) == 2
    assert len([row for row in observer_rows if row.get("status") == "open"]) == 1
    assert len([row for row in observer_rows if row.get("status") == "superseded"]) == 1
    canonical = [row for row in observer_rows if row.get("status") == "open"][0]
    duplicate = [row for row in observer_rows if row.get("status") == "superseded"][0]
    assert canonical["id"] == "observer-2"
    assert duplicate["superseded_by"] == "observer-2"

    unrelated = [row for row in rows if row.get("id") == "security-1"][0]
    assert unrelated["status"] == "open"
