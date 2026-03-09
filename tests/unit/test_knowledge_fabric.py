from __future__ import annotations

import json
from pathlib import Path

from francis_brain.calibration import calibrate_fabric_artifact, summarize_fabric_posture
from francis_brain.memory_store import SNAPSHOT_PATH
from francis_brain.recall import query_fabric, rebuild_fabric, summarize_fabric
from francis_brain.snapshots import build_fabric_snapshot
from francis_core.workspace_fs import WorkspaceFS


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")



def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(payload, encoding="utf-8")



def _build_fs(tmp_path: Path) -> WorkspaceFS:
    workspace = (tmp_path / "workspace").resolve()
    return WorkspaceFS(
        roots=[workspace],
        journal_path=(workspace / "journals" / "fs.jsonl").resolve(),
    )



def _seed_workspace(fs: WorkspaceFS) -> None:
    root = Path(fs.roots[0])
    _write_jsonl(
        root / "runs" / "run_ledger.jsonl",
        [
            {
                "ts": "2026-03-09T10:00:00+00:00",
                "kind": "observer.scan",
                "run_id": "run-observer-1",
                "summary": {"level": "healthy", "anomaly_count": 0, "incident_count": 0},
            }
        ],
    )
    _write_json(
        root / "runs" / "last_run.json",
        {
            "run_id": "run-observer-1",
            "phase": "verify",
            "summary": "Observer completed a healthy scan.",
            "started_at": "2026-03-09T10:00:00+00:00",
        },
    )
    _write_jsonl(
        root / "journals" / "decisions.jsonl",
        [
            {
                "id": "decision-1",
                "ts": "2026-03-09T10:00:01+00:00",
                "kind": "observer.decision",
                "run_id": "run-observer-1",
                "headline": "No anomalies detected.",
                "level": "healthy",
                "anomaly_count": 0,
            },
            {
                "id": "decision-2",
                "ts": "2026-03-09T10:10:00+00:00",
                "kind": "approval.decision",
                "request_id": "approval-1",
                "decision": "approved",
                "run_id": "run-approval-1",
            },
        ],
    )
    _write_json(
        root / "missions" / "missions.json",
        {
            "missions": [
                {
                    "id": "mission-1",
                    "title": "Ship Lens Fabric",
                    "objective": "Ground Lens memory in local evidence",
                    "priority": "high",
                    "status": "active",
                    "steps": ["index", "query"],
                    "completed_steps": ["index"],
                    "created_at": "2026-03-09T09:00:00+00:00",
                    "updated_at": "2026-03-09T10:30:00+00:00",
                }
            ]
        },
    )
    _write_jsonl(
        root / "approvals" / "requests.jsonl",
        [
            {
                "id": "approval-1",
                "ts": "2026-03-09T10:05:00+00:00",
                "run_id": "run-approval-1",
                "action": "forge.promote",
                "reason": "Promote repo triage capability",
                "requested_by": "architect",
                "metadata": {"stage_id": "stage-1"},
            }
        ],
    )
    _write_jsonl(
        root / "incidents" / "incidents.jsonl",
        [
            {
                "id": "incident-1",
                "ts": "2026-03-09T10:15:00+00:00",
                "run_id": "run-incident-1",
                "severity": "critical",
                "kind": "dev_server.crash",
                "message": "API service crashed under load.",
                "status": "open",
            }
        ],
    )
    _write_jsonl(
        root / "telemetry" / "events.jsonl",
        [
            {
                "id": "telemetry-1",
                "ts": "2026-03-09T10:16:00+00:00",
                "ingested_at": "2026-03-09T10:16:01+00:00",
                "run_id": "run-incident-1",
                "kind": "telemetry.event",
                "stream": "dev_server",
                "source": "api",
                "severity": "critical",
                "text": "service crashed",
                "fields": {"service": "api"},
            },
            {
                "id": "telemetry-2",
                "ts": "2026-03-09T10:17:00+00:00",
                "ingested_at": "2026-03-09T10:17:01+00:00",
                "run_id": "run-incident-1",
                "kind": "telemetry.event",
                "stream": "terminal",
                "source": "pytest",
                "severity": "info",
                "text": "informational noise",
                "fields": {},
            },
        ],
    )
    _write_json(
        root / "forge" / "catalog.json",
        {
            "entries": [
                {
                    "id": "stage-1",
                    "name": "Repo Triage Capability",
                    "slug": "repo-triage-capability",
                    "description": "Governed repo triage helper",
                    "rationale": "Derived from explicit teaching",
                    "tags": ["forge", "triage"],
                    "risk_tier": "low",
                    "status": "active",
                    "created_at": "2026-03-09T10:20:00+00:00",
                    "validation": {"ok": True, "errors": []},
                    "diff_summary": {"file_count": 3},
                }
            ]
        },
    )
    _write_json(
        root / "apprenticeship" / "sessions.json",
        {
            "sessions": [
                {
                    "id": "teach-1",
                    "title": "Repo triage",
                    "objective": "Teach repeatable repo review",
                    "status": "skillized",
                    "step_count": 2,
                    "tags": ["git", "review"],
                    "created_at": "2026-03-09T09:30:00+00:00",
                    "updated_at": "2026-03-09T10:25:00+00:00",
                    "mission_id": "mission-1",
                    "forge_stage_id": "stage-1",
                    "skill_artifact_path": "apprenticeship/skills/teach-1.json",
                }
            ]
        },
    )
    _write_json(
        root / "apprenticeship" / "skills" / "teach-1.json",
        {
            "created_at": "2026-03-09T10:26:00+00:00",
            "forge_payload": {
                "name": "Repo Triage Capability",
                "description": "Governed repo triage helper",
                "rationale": "Derived from explicit teaching",
                "tags": ["forge", "triage"],
                "risk_tier": "low",
            },
        },
    )
    _write_jsonl(
        root / "control" / "takeover_activity.jsonl",
        [
            {
                "id": "takeover-1",
                "ts": "2026-03-09T10:27:00+00:00",
                "session_id": "session-1",
                "status": "idle",
                "objective": "Review repo state",
                "run_id": "run-observer-1",
                "trace_id": "run-observer-1",
                "kind": "control.takeover.handed_back",
                "detail": {"summary": "Review complete"},
            }
        ],
    )



def test_fabric_snapshot_builds_curated_operational_memory(tmp_path: Path) -> None:
    fs = _build_fs(tmp_path)
    _seed_workspace(fs)

    snapshot = build_fabric_snapshot(fs)

    assert snapshot["summary"]["artifact_count"] >= 8
    assert snapshot["summary"]["source_counts"]["forge.catalog"] == 1
    assert snapshot["summary"]["lane_counts"]["hot"] >= 1
    telemetry_artifacts = [item for item in snapshot["artifacts"] if item["source"] == "telemetry.events"]
    assert len(telemetry_artifacts) == 1
    assert telemetry_artifacts[0]["severity"] == "critical"



def test_fabric_query_returns_citations_and_related_artifacts(tmp_path: Path) -> None:
    fs = _build_fs(tmp_path)
    _seed_workspace(fs)

    response = query_fabric(
        fs,
        query="no anomalies detected",
        limit=5,
        include_related=True,
        now="2026-03-09T10:30:00+00:00",
    )

    assert response["status"] == "ok"
    assert response["result_count"] >= 1
    top = response["results"][0]
    assert top["citation"]["rel_path"] == "journals/decisions.jsonl"
    assert top["confidence"] == "likely"
    assert top["trust_badge"] == "Likely"
    assert top["calibration"]["has_local_provenance"] is True
    assert any(item["reason"].startswith("shared run_id=") for item in top["related"])
    assert response["calibration"]["confidence_counts"]["likely"] >= 1

    telemetry = query_fabric(
        fs,
        query="service crashed",
        sources=["telemetry.events"],
        limit=3,
        now="2026-03-09T10:16:30+00:00",
    )
    assert telemetry["result_count"] == 1
    assert telemetry["results"][0]["source"] == "telemetry.events"
    assert telemetry["results"][0]["confidence"] == "likely"
    assert telemetry["results"][0]["calibration"]["freshness"] in {"live", "fresh"}



def test_fabric_rebuild_persists_snapshot(tmp_path: Path) -> None:
    fs = _build_fs(tmp_path)
    _seed_workspace(fs)

    rebuild = rebuild_fabric(fs)
    summary = summarize_fabric(fs, now="2026-03-09T10:30:00+00:00")

    assert rebuild["summary"]["artifact_count"] == summary["artifact_count"]
    assert summary["calibration"]["confidence_counts"]["likely"] >= 1
    assert summary["calibration"]["local_provenance_count"] >= 1
    persisted = Path(fs.roots[0]) / SNAPSHOT_PATH
    assert persisted.exists()



def test_fabric_calibration_degrades_stale_volatile_evidence() -> None:
    artifact = {
        "id": "telemetry.events:1",
        "source": "telemetry.events",
        "kind": "telemetry.event",
        "title": "API crash",
        "body": "service crashed",
        "ts": "2026-03-01T10:16:00+00:00",
        "verification_status": "verified",
        "provenance": {"rel_path": "telemetry/events.jsonl", "line": 1},
        "relationships": {"run_id": "run-incident-1", "trace_id": "run-incident-1"},
    }

    calibration = calibrate_fabric_artifact(
        artifact,
        volatile_sources={"telemetry.events"},
        now="2026-03-09T10:16:30+00:00",
    )

    assert calibration["confidence"] == "likely"
    assert calibration["trust_badge"] == "Likely"
    assert calibration["can_claim_done"] is False
    assert calibration["freshness"] == "stale"
    assert any("current-state source is not fresh enough" in item for item in calibration["caveats"])


def test_summarize_fabric_posture_flags_stale_current_state() -> None:
    posture = summarize_fabric_posture(
        {
            "citation_ready_count": 2,
            "calibration": {
                "confidence_counts": {"confirmed": 1, "likely": 1, "uncertain": 0},
                "stale_current_state_count": 2,
                "done_claim_ready_count": 1,
            },
        }
    )

    assert posture["trust"] == "Likely"
    assert posture["done_claim_ready_count"] == 1
    assert posture["stale_current_state_count"] == 2
    assert "Refresh 2 stale current-state artifact" in posture["warning"]
