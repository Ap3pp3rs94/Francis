from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app
from francis_brain.ledger import RunLedger
from francis_core.workspace_fs import WorkspaceFS
import services.orchestrator.app.lens_snapshot as lens_snapshot
import services.orchestrator.app.routes.fabric as fabric_routes

client = TestClient(app)



def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")



def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(payload, encoding="utf-8")



def _wire_workspace(monkeypatch, tmp_path: Path) -> Path:
    workspace = (tmp_path / "workspace").resolve()
    repo_root = workspace.parent.resolve()
    fs = WorkspaceFS(
        roots=[workspace],
        journal_path=(workspace / "journals" / "fs.jsonl").resolve(),
    )
    monkeypatch.setattr(fabric_routes, "_workspace_root", workspace)
    monkeypatch.setattr(fabric_routes, "_repo_root", repo_root)
    monkeypatch.setattr(fabric_routes, "_fs", fs)
    monkeypatch.setattr(fabric_routes, "_ledger", RunLedger(fs, rel_path="runs/run_ledger.jsonl"))
    monkeypatch.setattr(lens_snapshot, "DEFAULT_WORKSPACE_ROOT", workspace)
    return workspace



def _seed_workspace(workspace: Path) -> None:
    _write_jsonl(
        workspace / "runs" / "run_ledger.jsonl",
        [
            {
                "ts": "2026-03-09T11:00:00+00:00",
                "kind": "observer.scan",
                "run_id": "run-observer-2",
                "summary": {"level": "healthy", "anomaly_count": 0, "incident_count": 0},
            }
        ],
    )
    _write_json(
        workspace / "runs" / "last_run.json",
        {
            "run_id": "run-observer-2",
            "phase": "report",
            "summary": "Fabric route test run.",
            "started_at": "2026-03-09T11:00:00+00:00",
        },
    )
    _write_jsonl(
        workspace / "journals" / "decisions.jsonl",
        [
            {
                "id": "decision-route-1",
                "ts": "2026-03-09T11:00:01+00:00",
                "kind": "observer.decision",
                "run_id": "run-observer-2",
                "headline": "No anomalies detected.",
            }
        ],
    )
    _write_json(
        workspace / "missions" / "missions.json",
        {
            "missions": [
                {
                    "id": "mission-route-1",
                    "title": "Fabric Route",
                    "objective": "Prove the orchestrator fabric endpoint",
                    "priority": "high",
                    "status": "active",
                    "steps": ["index", "query"],
                    "completed_steps": [],
                    "created_at": "2026-03-09T10:30:00+00:00",
                    "updated_at": "2026-03-09T11:01:00+00:00",
                }
            ]
        },
    )
    _write_jsonl(
        workspace / "telemetry" / "events.jsonl",
        [
            {
                "id": "telemetry-route-1",
                "ts": "2026-03-09T11:02:00+00:00",
                "ingested_at": "2026-03-09T11:02:01+00:00",
                "run_id": "run-observer-2",
                "kind": "telemetry.event",
                "stream": "dev_server",
                "source": "api",
                "severity": "critical",
                "text": "api service crashed",
                "fields": {"service": "api"},
            }
        ],
    )
    _write_jsonl(
        workspace / "security" / "quarantine.jsonl",
        [
            {
                "id": "quarantine-route-1",
                "ts": "2026-03-09T11:02:30+00:00",
                "severity": "high",
                "surface": "telemetry",
                "action": "telemetry.events",
                "categories": ["prompt_injection"],
            }
        ],
    )
    _write_json(
        workspace / "forge" / "catalog.json",
        {
            "entries": [
                {
                    "id": "stage-route-1",
                    "name": "Route Capability",
                    "slug": "route-capability",
                    "description": "Capability for route validation",
                    "rationale": "integration coverage",
                    "tags": ["forge"],
                    "risk_tier": "low",
                    "status": "active",
                    "created_at": "2026-03-09T11:03:00+00:00",
                    "validation": {"ok": True, "errors": []},
                    "diff_summary": {"file_count": 2},
                }
            ]
        },
    )



def test_fabric_routes_support_summary_query_and_rebuild(monkeypatch, tmp_path: Path) -> None:
    workspace = _wire_workspace(monkeypatch, tmp_path)
    _seed_workspace(workspace)

    summary = client.get("/fabric")
    assert summary.status_code == 200
    payload = summary.json()
    assert payload["summary"]["artifact_count"] >= 4
    assert payload["summary"]["source_count"] >= 3
    assert payload["summary"]["calibration"]["confidence_counts"]["likely"] >= 1

    query = client.post(
        "/fabric/query",
        json={"query": "no anomalies detected", "limit": 5, "include_related": True},
    )
    assert query.status_code == 200
    query_payload = query.json()
    assert query_payload["result_count"] >= 1
    assert query_payload["results"][0]["citation"]["rel_path"] == "journals/decisions.jsonl"
    assert query_payload["results"][0]["confidence"] == "likely"
    assert query_payload["results"][0]["trust_badge"] == "Likely"
    assert query_payload["results"][0]["calibration"]["has_local_provenance"] is True

    rebuild = client.post("/fabric/rebuild", json={"reason": "integration rebuild"})
    assert rebuild.status_code == 200
    rebuild_payload = rebuild.json()
    assert rebuild_payload["summary"]["artifact_count"] >= 4
    assert (workspace / "brain" / "fabric" / "snapshot.json").exists()



def test_lens_snapshot_surfaces_fabric_summary(monkeypatch, tmp_path: Path) -> None:
    workspace = _wire_workspace(monkeypatch, tmp_path)
    _seed_workspace(workspace)

    snapshot = lens_snapshot.build_lens_snapshot(workspace)

    assert snapshot["fabric"]["artifact_count"] >= 4
    assert snapshot["fabric"]["citation_ready_count"] >= 1
    assert snapshot["fabric"]["calibration"]["confidence_counts"]["likely"] >= 1
    assert snapshot["security"]["quarantine_count"] == 1
    assert snapshot["security"]["top_categories"]["prompt_injection"] == 1
