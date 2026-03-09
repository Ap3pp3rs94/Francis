from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from francis_brain.lanes import assign_retention_lane, summarize_lanes
from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS

SOURCE_LIMITS = {
    "runs.ledger": 500,
    "brain.ledger": 500,
    "journals.decisions": 500,
    "missions.missions": 400,
    "missions.history": 300,
    "approvals.requests": 300,
    "incidents.incidents": 300,
    "inbox.messages": 200,
    "forge.catalog": 200,
    "telemetry.events": 200,
    "control.takeover_activity": 300,
    "queue.deadletter": 200,
    "autonomy.dispatch_history": 200,
    "autonomy.tick_history": 200,
    "apprenticeship.sessions": 200,
}
HIGH_SIGNAL_TELEMETRY = {"warn", "warning", "error", "critical"}


def _read_json(fs: WorkspaceFS, rel_path: str, default: Any) -> Any:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _read_jsonl(fs: WorkspaceFS, rel_path: str) -> list[dict[str, Any]]:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
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


def _tail(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    normalized = max(0, min(int(limit), 5000))
    return rows[-normalized:] if normalized else []


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\r", "\n").split())


def _compact_json(value: Any, *, limit: int = 280) -> str:
    try:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        raw = str(value)
    compact = _normalize_text(raw)
    return compact[:limit] + ("..." if len(compact) > limit else "")


def _derive_trace_id(row: dict[str, Any]) -> str:
    explicit = str(row.get("trace_id", "")).strip()
    if explicit:
        return explicit
    run_id = str(row.get("run_id", "")).strip()
    if not run_id:
        return ""
    for marker in (":event:", ":recover", ":observer:", ":mission:", ":worker:", ":worker-recover:"):
        if marker in run_id:
            return run_id.split(marker, 1)[0].strip()
    if ":" in run_id:
        return run_id.split(":", 1)[0].strip()
    return run_id


def _provenance(rel_path: str, *, line: int | None = None, record_index: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"rel_path": rel_path}
    if line is not None:
        payload["line"] = int(line)
    if record_index is not None:
        payload["record_index"] = int(record_index)
    return payload


def _artifact(
    *,
    artifact_id: str,
    source: str,
    kind: str,
    title: str,
    body: str,
    ts: str | None,
    provenance: dict[str, Any],
    relationships: dict[str, Any] | None = None,
    severity: str | None = None,
    status: str | None = None,
    verification_status: str | None = None,
) -> dict[str, Any]:
    item = {
        "id": artifact_id,
        "source": source,
        "kind": kind,
        "title": _normalize_text(title),
        "body": _normalize_text(body),
        "ts": str(ts or "").strip() or None,
        "severity": str(severity or "").strip().lower() or None,
        "status": str(status or "").strip().lower() or None,
        "verification_status": str(verification_status or "").strip().lower() or None,
        "provenance": provenance,
        "relationships": relationships or {},
    }
    item["search_text"] = "\n".join(
        part for part in [item["title"], item["body"], _compact_json(item["relationships"], limit=160)] if part
    )
    item["retention_lane"] = assign_retention_lane(item)
    return item


def _approval_status_by_request(fs: WorkspaceFS) -> dict[str, str]:
    latest: dict[str, str] = {}
    for row in _read_jsonl(fs, "journals/decisions.jsonl"):
        if str(row.get("kind", "")).strip().lower() != "approval.decision":
            continue
        request_id = str(row.get("request_id", "")).strip()
        decision = str(row.get("decision", "")).strip().lower()
        if request_id and decision in {"approved", "rejected"}:
            latest[request_id] = decision
    return latest


def _collect_run_artifacts(fs: WorkspaceFS) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for source, rel_path in (
        ("runs.ledger", "runs/run_ledger.jsonl"),
        ("brain.ledger", "brain/run_ledger.jsonl"),
    ):
        for index, row in enumerate(_tail(_read_jsonl(fs, rel_path), SOURCE_LIMITS[source]), start=1):
            run_id = str(row.get("run_id", "")).strip()
            summary = row.get("summary", {}) if isinstance(row.get("summary"), dict) else {}
            title = f"{row.get('kind', 'run.event')} receipt"
            body = _compact_json(summary, limit=300)
            artifacts.append(
                _artifact(
                    artifact_id=f"{source}:{run_id or index}:{index}",
                    source=source,
                    kind="run.receipt",
                    title=title,
                    body=body,
                    ts=str(row.get("ts", "")).strip() or None,
                    provenance=_provenance(rel_path, line=index),
                    relationships={
                        "run_id": run_id,
                        "trace_id": _derive_trace_id(row),
                        "mission_id": summary.get("mission_id"),
                        "stage_id": summary.get("stage_id"),
                        "session_id": summary.get("session_id"),
                        "approval_id": summary.get("approval_id"),
                    },
                    verification_status=str(summary.get("verification_status", "")).strip() or None,
                )
            )

    last_run = _read_json(fs, "runs/last_run.json", {})
    if isinstance(last_run, dict) and last_run:
        artifacts.append(
            _artifact(
                artifact_id=f"runs.last:{str(last_run.get('run_id', 'last')).strip() or 'last'}",
                source="runs.last",
                kind="run.state",
                title=f"Last run: {str(last_run.get('phase', 'unknown')).strip() or 'unknown'}",
                body=_compact_json(last_run, limit=320),
                ts=str(last_run.get("ts", last_run.get("started_at", ""))).strip() or None,
                provenance=_provenance("runs/last_run.json"),
                relationships={
                    "run_id": last_run.get("run_id"),
                    "trace_id": _derive_trace_id(last_run),
                },
                verification_status=str(last_run.get("verification_status", "")).strip() or None,
            )
        )
    return artifacts


def _collect_decision_artifacts(fs: WorkspaceFS) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for index, row in enumerate(_tail(_read_jsonl(fs, "journals/decisions.jsonl"), SOURCE_LIMITS["journals.decisions"]), start=1):
        headline = str(row.get("headline", row.get("kind", "decision"))).strip() or "decision"
        body = " | ".join(
            part
            for part in [
                str(row.get("decision", "")).strip(),
                str(row.get("reason", "")).strip(),
                _compact_json(row.get("detail", {}), limit=180),
            ]
            if part
        )
        artifacts.append(
            _artifact(
                artifact_id=f"journals.decisions:{str(row.get('id', '')).strip() or index}",
                source="journals.decisions",
                kind=str(row.get("kind", "decision")).strip() or "decision",
                title=headline,
                body=body,
                ts=str(row.get("ts", "")).strip() or None,
                provenance=_provenance("journals/decisions.jsonl", line=index),
                relationships={
                    "run_id": row.get("run_id"),
                    "trace_id": _derive_trace_id(row),
                    "approval_id": row.get("request_id") or row.get("approval_request_id"),
                    "session_id": row.get("session_id"),
                },
                verification_status=str(row.get("verification_status", "")).strip() or None,
            )
        )
    return artifacts


def _collect_mission_artifacts(fs: WorkspaceFS) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    missions_doc = _read_json(fs, "missions/missions.json", {"missions": []})
    rows = missions_doc.get("missions", []) if isinstance(missions_doc, dict) else []
    for index, row in enumerate(rows[: SOURCE_LIMITS["missions.missions"]], start=1):
        if not isinstance(row, dict):
            continue
        steps = row.get("steps", []) if isinstance(row.get("steps"), list) else []
        completed_steps = row.get("completed_steps", []) if isinstance(row.get("completed_steps"), list) else []
        body = " | ".join(
            part
            for part in [
                str(row.get("objective", "")).strip(),
                f"priority={str(row.get('priority', 'normal')).strip().lower() or 'normal'}",
                f"steps={len(steps)} completed={len(completed_steps)}",
                str(row.get("last_error", "")).strip(),
            ]
            if part
        )
        artifacts.append(
            _artifact(
                artifact_id=f"missions.missions:{str(row.get('id', '')).strip() or index}",
                source="missions.missions",
                kind="mission.state",
                title=str(row.get("title", "Untitled mission")).strip() or "Untitled mission",
                body=body,
                ts=str(row.get("updated_at", row.get("created_at", ""))).strip() or None,
                provenance=_provenance("missions/missions.json", record_index=index - 1),
                relationships={"mission_id": row.get("id")},
                status=str(row.get("status", "")).strip() or None,
            )
        )

    for index, row in enumerate(_tail(_read_jsonl(fs, "missions/history.jsonl"), SOURCE_LIMITS["missions.history"]), start=1):
        artifacts.append(
            _artifact(
                artifact_id=f"missions.history:{str(row.get('id', '')).strip() or index}",
                source="missions.history",
                kind=str(row.get("kind", "mission.history")).strip() or "mission.history",
                title=str(row.get("summary", row.get("kind", "mission history"))).strip() or "mission history",
                body=_compact_json(row, limit=280),
                ts=str(row.get("ts", "")).strip() or None,
                provenance=_provenance("missions/history.jsonl", line=index),
                relationships={
                    "run_id": row.get("run_id"),
                    "mission_id": row.get("mission_id"),
                    "trace_id": _derive_trace_id(row),
                },
                status=str(row.get("status", "")).strip() or None,
            )
        )
    return artifacts


def _collect_approval_artifacts(fs: WorkspaceFS) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    decision_status = _approval_status_by_request(fs)
    for index, row in enumerate(_tail(_read_jsonl(fs, "approvals/requests.jsonl"), SOURCE_LIMITS["approvals.requests"]), start=1):
        approval_id = str(row.get("id", "")).strip() or f"approval-{index}"
        metadata = row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {}
        body = " | ".join(
            part
            for part in [
                str(row.get("reason", "")).strip(),
                _compact_json(metadata, limit=160),
            ]
            if part
        )
        artifacts.append(
            _artifact(
                artifact_id=f"approvals.requests:{approval_id}",
                source="approvals.requests",
                kind="approval.request",
                title=str(row.get("action", "approval")).strip() or "approval",
                body=body,
                ts=str(row.get("ts", "")).strip() or None,
                provenance=_provenance("approvals/requests.jsonl", line=index),
                relationships={
                    "approval_id": approval_id,
                    "run_id": row.get("run_id"),
                    "trace_id": _derive_trace_id(row),
                    "stage_id": metadata.get("stage_id"),
                },
                status=decision_status.get(approval_id, "pending"),
            )
        )
    return artifacts


def _collect_incident_artifacts(fs: WorkspaceFS) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for index, row in enumerate(_tail(_read_jsonl(fs, "incidents/incidents.jsonl"), SOURCE_LIMITS["incidents.incidents"]), start=1):
        evidence = row.get("evidence", {}) if isinstance(row.get("evidence"), dict) else {}
        body = " | ".join(
            part
            for part in [
                str(row.get("message", row.get("summary", ""))).strip(),
                _compact_json(evidence, limit=180),
            ]
            if part
        )
        artifacts.append(
            _artifact(
                artifact_id=f"incidents.incidents:{str(row.get('id', '')).strip() or index}",
                source="incidents.incidents",
                kind=str(row.get("kind", "incident")).strip() or "incident",
                title=str(row.get("summary", row.get("kind", "incident"))).strip() or "incident",
                body=body,
                ts=str(row.get("ts", "")).strip() or None,
                provenance=_provenance("incidents/incidents.jsonl", line=index),
                relationships={
                    "run_id": row.get("run_id"),
                    "trace_id": _derive_trace_id(row),
                },
                severity=str(row.get("severity", "")).strip() or None,
                status=str(row.get("status", row.get("state", ""))).strip() or None,
            )
        )
    return artifacts


def _collect_inbox_artifacts(fs: WorkspaceFS) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for index, row in enumerate(_tail(_read_jsonl(fs, "inbox/messages.jsonl"), SOURCE_LIMITS["inbox.messages"]), start=1):
        body = str(row.get("body", row.get("summary", ""))).strip()
        artifacts.append(
            _artifact(
                artifact_id=f"inbox.messages:{str(row.get('id', '')).strip() or index}",
                source="inbox.messages",
                kind="inbox.message",
                title=str(row.get("title", "Inbox item")).strip() or "Inbox item",
                body=body,
                ts=str(row.get("ts", "")).strip() or None,
                provenance=_provenance("inbox/messages.jsonl", line=index),
                severity=str(row.get("severity", "")).strip() or None,
            )
        )
    return artifacts


def _collect_forge_artifacts(fs: WorkspaceFS) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    catalog = _read_json(fs, "forge/catalog.json", {"entries": []})
    rows = catalog.get("entries", []) if isinstance(catalog, dict) else []
    for index, row in enumerate(rows[: SOURCE_LIMITS["forge.catalog"]], start=1):
        if not isinstance(row, dict):
            continue
        validation = row.get("validation", {}) if isinstance(row.get("validation"), dict) else {}
        diff_summary = row.get("diff_summary", {}) if isinstance(row.get("diff_summary"), dict) else {}
        body = " | ".join(
            part
            for part in [
                str(row.get("description", "")).strip(),
                str(row.get("rationale", "")).strip(),
                f"status={str(row.get('status', 'unknown')).strip().lower() or 'unknown'}",
                f"risk={str(row.get('risk_tier', 'low')).strip().lower() or 'low'}",
                f"files={int(diff_summary.get('file_count', 0) or 0)}",
                _compact_json(validation.get("errors", []), limit=180),
            ]
            if part
        )
        artifacts.append(
            _artifact(
                artifact_id=f"forge.catalog:{str(row.get('id', '')).strip() or index}",
                source="forge.catalog",
                kind="forge.capability",
                title=str(row.get("name", row.get("slug", "Forge capability"))).strip() or "Forge capability",
                body=body,
                ts=str(row.get("promoted_at", row.get("created_at", ""))).strip() or None,
                provenance=_provenance("forge/catalog.json", record_index=index - 1),
                relationships={"stage_id": row.get("id")},
                status=str(row.get("status", "")).strip() or None,
                verification_status="verified" if bool(validation.get("ok", False)) else "failed",
            )
        )
    return artifacts


def _collect_telemetry_artifacts(fs: WorkspaceFS) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    rows = [
        row
        for row in _read_jsonl(fs, "telemetry/events.jsonl")
        if str(row.get("severity", "info")).strip().lower() in HIGH_SIGNAL_TELEMETRY
    ]
    for index, row in enumerate(_tail(rows, SOURCE_LIMITS["telemetry.events"]), start=1):
        fields = row.get("fields", {}) if isinstance(row.get("fields"), dict) else {}
        body = " | ".join(
            part
            for part in [
                str(row.get("text", "")).strip(),
                _compact_json(fields, limit=180),
            ]
            if part
        )
        artifacts.append(
            _artifact(
                artifact_id=f"telemetry.events:{str(row.get('id', '')).strip() or index}",
                source="telemetry.events",
                kind="telemetry.event",
                title=f"{str(row.get('stream', 'telemetry')).strip() or 'telemetry'}:{str(row.get('source', 'unknown')).strip() or 'unknown'}",
                body=body,
                ts=str(row.get("ts", "")).strip() or None,
                provenance=_provenance("telemetry/events.jsonl", line=index),
                relationships={
                    "run_id": row.get("run_id"),
                    "trace_id": _derive_trace_id(row),
                },
                severity=str(row.get("severity", "")).strip() or None,
            )
        )
    return artifacts


def _collect_takeover_artifacts(fs: WorkspaceFS) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    rows = _tail(_read_jsonl(fs, "control/takeover_activity.jsonl"), SOURCE_LIMITS["control.takeover_activity"])
    for index, row in enumerate(rows, start=1):
        detail = row.get("detail", {}) if isinstance(row.get("detail"), dict) else {}
        body = " | ".join(
            part
            for part in [
                str(row.get("objective", "")).strip(),
                str(detail.get("summary", detail.get("reason", ""))).strip(),
                _compact_json(detail.get("verification", {}), limit=160),
            ]
            if part
        )
        artifacts.append(
            _artifact(
                artifact_id=f"control.takeover_activity:{str(row.get('id', '')).strip() or index}",
                source="control.takeover_activity",
                kind=str(row.get("kind", "control.takeover")).strip() or "control.takeover",
                title=str(row.get("status", "takeover")).strip() or "takeover",
                body=body,
                ts=str(row.get("ts", "")).strip() or None,
                provenance=_provenance("control/takeover_activity.jsonl", line=index),
                relationships={
                    "run_id": row.get("run_id"),
                    "trace_id": row.get("trace_id") or _derive_trace_id(row),
                    "session_id": row.get("session_id"),
                },
                status=str(row.get("status", "")).strip() or None,
            )
        )
    return artifacts


def _collect_deadletter_artifacts(fs: WorkspaceFS) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for index, row in enumerate(_tail(_read_jsonl(fs, "queue/deadletter.jsonl"), SOURCE_LIMITS["queue.deadletter"]), start=1):
        artifacts.append(
            _artifact(
                artifact_id=f"queue.deadletter:{str(row.get('id', '')).strip() or index}",
                source="queue.deadletter",
                kind=str(row.get("kind", "queue.deadletter")).strip() or "queue.deadletter",
                title=str(row.get("action", row.get("kind", "deadletter"))).strip() or "deadletter",
                body=_compact_json(row, limit=280),
                ts=str(row.get("ts", "")).strip() or None,
                provenance=_provenance("queue/deadletter.jsonl", line=index),
                relationships={
                    "run_id": row.get("run_id"),
                    "trace_id": _derive_trace_id(row),
                    "mission_id": row.get("mission_id"),
                },
                severity=str(row.get("severity", "")).strip() or None,
                status=str(row.get("status", "deadletter")).strip() or None,
            )
        )
    return artifacts


def _collect_autonomy_artifacts(fs: WorkspaceFS) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for source, rel_path, limit in (
        ("autonomy.dispatch_history", "autonomy/dispatch_history.jsonl", SOURCE_LIMITS["autonomy.dispatch_history"]),
        ("autonomy.tick_history", "autonomy/tick_history.jsonl", SOURCE_LIMITS["autonomy.tick_history"]),
    ):
        for index, row in enumerate(_tail(_read_jsonl(fs, rel_path), limit), start=1):
            verification = row.get("verification", {}) if isinstance(row.get("verification"), dict) else {}
            artifacts.append(
                _artifact(
                    artifact_id=f"{source}:{str(row.get('id', '')).strip() or index}",
                    source=source,
                    kind=str(row.get("kind", source)).strip() or source,
                    title=str(row.get("kind", source)).strip() or source,
                    body=_compact_json(row, limit=300),
                    ts=str(row.get("ts", "")).strip() or None,
                    provenance=_provenance(rel_path, line=index),
                    relationships={
                        "run_id": row.get("run_id"),
                        "trace_id": _derive_trace_id(row),
                    },
                    verification_status=str(verification.get("verification_status", "")).strip() or None,
                    status=str(row.get("completion_state", "")).strip() or None,
                )
            )

    for source, rel_path in (("autonomy.last_dispatch", "autonomy/last_dispatch.json"), ("autonomy.last_tick", "autonomy/last_tick.json")):
        row = _read_json(fs, rel_path, {})
        if not isinstance(row, dict) or not row:
            continue
        verification = row.get("verification", {}) if isinstance(row.get("verification"), dict) else {}
        artifacts.append(
            _artifact(
                artifact_id=f"{source}:{str(row.get('run_id', 'last')).strip() or 'last'}",
                source=source,
                kind=str(row.get("kind", source)).strip() or source,
                title=str(row.get("kind", source)).strip() or source,
                body=_compact_json(row, limit=300),
                ts=str(row.get("ts", "")).strip() or None,
                provenance=_provenance(rel_path),
                relationships={"run_id": row.get("run_id"), "trace_id": _derive_trace_id(row)},
                verification_status=str(verification.get("verification_status", "")).strip() or None,
                status=str(row.get("completion_state", "")).strip() or None,
            )
        )
    return artifacts


def _collect_apprenticeship_artifacts(fs: WorkspaceFS) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    sessions_doc = _read_json(fs, "apprenticeship/sessions.json", {"sessions": []})
    rows = sessions_doc.get("sessions", []) if isinstance(sessions_doc, dict) else []
    for index, row in enumerate(rows[: SOURCE_LIMITS["apprenticeship.sessions"]], start=1):
        if not isinstance(row, dict):
            continue
        generalization = row.get("generalization", {}) if isinstance(row.get("generalization"), dict) else {}
        body = " | ".join(
            part
            for part in [
                str(row.get("objective", "")).strip(),
                f"status={str(row.get('status', 'recording')).strip().lower() or 'recording'}",
                f"steps={int(row.get('step_count', 0) or 0)}",
                str(generalization.get("summary", "")).strip(),
            ]
            if part
        )
        session_id = str(row.get("id", "")).strip() or f"session-{index}"
        artifacts.append(
            _artifact(
                artifact_id=f"apprenticeship.sessions:{session_id}",
                source="apprenticeship.sessions",
                kind="apprenticeship.session",
                title=str(row.get("title", "Teaching session")).strip() or "Teaching session",
                body=body,
                ts=str(row.get("updated_at", row.get("created_at", ""))).strip() or None,
                provenance=_provenance("apprenticeship/sessions.json", record_index=index - 1),
                relationships={
                    "session_id": session_id,
                    "mission_id": row.get("mission_id"),
                    "stage_id": row.get("forge_stage_id"),
                },
                status=str(row.get("status", "")).strip() or None,
            )
        )

        skill_path = str(row.get("skill_artifact_path", "")).strip()
        if skill_path:
            skill = _read_json(fs, skill_path, {})
            if isinstance(skill, dict) and skill:
                forge_payload = skill.get("forge_payload", {}) if isinstance(skill.get("forge_payload"), dict) else {}
                artifacts.append(
                    _artifact(
                        artifact_id=f"apprenticeship.skills:{session_id}",
                        source="apprenticeship.skills",
                        kind="apprenticeship.skill",
                        title=str(forge_payload.get("name", row.get("title", "Apprenticeship skill"))).strip() or "Apprenticeship skill",
                        body=_compact_json(skill, limit=320),
                        ts=str(skill.get("created_at", row.get("updated_at", ""))).strip() or None,
                        provenance=_provenance(skill_path),
                        relationships={
                            "session_id": session_id,
                            "mission_id": row.get("mission_id"),
                            "stage_id": row.get("forge_stage_id"),
                        },
                        status="skillized",
                    )
                )
    return artifacts


def build_fabric_snapshot(fs: WorkspaceFS) -> dict[str, Any]:
    artifacts = [
        *_collect_run_artifacts(fs),
        *_collect_decision_artifacts(fs),
        *_collect_mission_artifacts(fs),
        *_collect_approval_artifacts(fs),
        *_collect_incident_artifacts(fs),
        *_collect_inbox_artifacts(fs),
        *_collect_forge_artifacts(fs),
        *_collect_telemetry_artifacts(fs),
        *_collect_takeover_artifacts(fs),
        *_collect_deadletter_artifacts(fs),
        *_collect_autonomy_artifacts(fs),
        *_collect_apprenticeship_artifacts(fs),
    ]
    artifacts.sort(key=lambda item: str(item.get("ts", "")))
    source_counts = Counter(str(item.get("source", "")).strip() for item in artifacts if str(item.get("source", "")).strip())
    citation_ready_count = sum(1 for item in artifacts if isinstance(item.get("provenance"), dict) and item["provenance"].get("rel_path"))
    relationship_count = sum(
        sum(1 for value in (item.get("relationships") or {}).values() if str(value or "").strip()) for item in artifacts
    )
    summary = {
        "artifact_count": len(artifacts),
        "source_counts": dict(sorted(source_counts.items())),
        "lane_counts": summarize_lanes(artifacts),
        "citation_ready_count": citation_ready_count,
        "relationship_count": relationship_count,
    }
    return {
        "version": 1,
        "generated_at": utc_now_iso(),
        "workspace_root": str(Path(fs.roots[0]).resolve()),
        "summary": summary,
        "artifacts": artifacts,
    }
