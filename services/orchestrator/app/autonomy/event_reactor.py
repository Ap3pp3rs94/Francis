from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from francis_core.workspace_fs import WorkspaceFS


def _read_json(fs: WorkspaceFS, rel_path: str, default: object) -> object:
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
            if isinstance(parsed, dict):
                rows.append(parsed)
        except Exception:
            continue
    return rows


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def collect_events(
    fs: WorkspaceFS,
    *,
    scan_interval_seconds: int = 300,
    telemetry_horizon_hours: int = 24,
) -> dict[str, Any]:
    missions_doc = _read_json(fs, "missions/missions.json", {"missions": []})
    missions = missions_doc.get("missions", []) if isinstance(missions_doc, dict) else []
    inactive = {"completed", "failed", "cancelled", "canceled"}
    active_missions = [
        mission
        for mission in missions
        if isinstance(mission, dict) and str(mission.get("status", "")).lower() not in inactive
    ]

    jobs = _read_jsonl(fs, "queue/jobs.jsonl")
    queued_jobs = [job for job in jobs if str(job.get("status", "")).lower() == "queued"]
    leased_jobs = [job for job in jobs if str(job.get("status", "")).lower() == "leased"]
    now = datetime.now(timezone.utc)
    queued_due_jobs: list[dict[str, Any]] = []
    queued_backoff_jobs: list[dict[str, Any]] = []
    leased_expired_jobs: list[dict[str, Any]] = []
    for job in queued_jobs:
        next_run_after = _parse_ts(str(job.get("next_run_after", "")).strip() or None)
        if next_run_after is None or next_run_after <= now:
            queued_due_jobs.append(job)
        else:
            queued_backoff_jobs.append(job)
    for job in leased_jobs:
        lease_expires_at = _parse_ts(str(job.get("lease_expires_at", "")).strip() or None)
        if lease_expires_at is not None and lease_expires_at <= now:
            leased_expired_jobs.append(job)
    leased_expired_classes: dict[str, int] = {}
    for job in leased_expired_jobs:
        action = str(job.get("action", "")).strip().lower()
        if "." in action:
            klass = action.split(".", 1)[0].strip() or "unknown"
        else:
            klass = action or "unknown"
        leased_expired_classes[klass] = leased_expired_classes.get(klass, 0) + 1
    leased_expired_classes_top = [
        {"key": klass, "count": count}
        for klass, count in sorted(leased_expired_classes.items(), key=lambda kv: kv[1], reverse=True)[:5]
    ]

    queued_mission_ids = [str(job.get("mission_id")) for job in queued_due_jobs if job.get("mission_id")]
    worker_due_actions: dict[str, int] = {}
    for job in queued_due_jobs:
        action = str(job.get("action", "")).strip().lower()
        if not action:
            continue
        worker_due_actions[action] = worker_due_actions.get(action, 0) + 1
    worker_due_actions_top = [
        {"key": action, "count": count}
        for action, count in sorted(worker_due_actions.items(), key=lambda kv: kv[1], reverse=True)[:5]
    ]

    deadletters = _read_jsonl(fs, "queue/deadletter.jsonl")
    incidents = _read_jsonl(fs, "incidents/incidents.jsonl")
    open_incidents = [i for i in incidents if str(i.get("status", "")).lower() == "open"]
    critical_incidents = [i for i in open_incidents if str(i.get("severity", "")).lower() == "critical"]

    inbox_alert_count = sum(
        1 for row in _read_jsonl(fs, "inbox/messages.jsonl") if str(row.get("severity", "")).lower() == "alert"
    )
    telemetry_rows = _read_jsonl(fs, "telemetry/events.jsonl")
    telemetry_horizon = now - timedelta(hours=max(1, min(168, _safe_int(telemetry_horizon_hours, 24))))
    telemetry_in_horizon: list[dict[str, Any]] = []
    telemetry_warn_count = 0
    telemetry_error_count = 0
    telemetry_critical_count = 0
    telemetry_stream_counts: dict[str, int] = {}
    for row in telemetry_rows:
        ts = _parse_ts(str(row.get("ts", "")).strip() or None)
        if ts is not None and ts < telemetry_horizon:
            continue
        telemetry_in_horizon.append(row)
        stream = str(row.get("stream", "")).strip().lower()
        if stream:
            telemetry_stream_counts[stream] = telemetry_stream_counts.get(stream, 0) + 1
        severity = str(row.get("severity", "")).strip().lower()
        if severity == "warning":
            severity = "warn"
        if severity == "warn":
            telemetry_warn_count += 1
        elif severity == "error":
            telemetry_error_count += 1
        elif severity == "critical":
            telemetry_critical_count += 1
    telemetry_streams_top = [
        {"key": stream, "count": count}
        for stream, count in sorted(telemetry_stream_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
    ]
    last_telemetry = telemetry_rows[-1] if telemetry_rows else None

    last_run = _read_json(fs, "runs/last_run.json", {})
    last_run_ts = _parse_ts(last_run.get("ts")) if isinstance(last_run, dict) else None
    observer_scan_due = last_run_ts is None or (now - last_run_ts).total_seconds() >= scan_interval_seconds
    last_worker_run = _read_json(fs, "runs/last_worker_run.json", {})
    if not isinstance(last_worker_run, dict):
        last_worker_run = {}
    worker_gate = _read_json(fs, "queue/worker_cycle_gate.json", {})
    if not isinstance(worker_gate, dict):
        worker_gate = {}
    worker_cycle_active = _safe_int(worker_gate.get("active_count", 0), 0)
    worker_cycle_max = max(1, _safe_int(worker_gate.get("max_concurrent_cycles", 1), 1))
    worker_cycle_saturated = worker_cycle_active >= worker_cycle_max
    worker_last_lease_renewed_count = _safe_int(last_worker_run.get("lease_renewed_count", 0), 0)
    worker_last_lease_lost_count = _safe_int(last_worker_run.get("lease_lost_count", 0), 0)
    worker_last_lease_conflict_count = _safe_int(last_worker_run.get("lease_finalize_conflict_count", 0), 0)
    worker_last_recovered_count = _safe_int(last_worker_run.get("reclaimed_leases_count", 0), 0)

    events: list[dict[str, Any]] = []
    if observer_scan_due:
        events.append({"type": "observer.scan_due", "reason": "scan_interval_elapsed"})
    if critical_incidents:
        events.append({"type": "incident.critical_open", "count": len(critical_incidents)})
    if queued_mission_ids:
        events.append({"type": "mission.jobs_queued", "count": len(queued_mission_ids)})
    if queued_due_jobs:
        events.append({"type": "worker.queue_due", "count": len(queued_due_jobs)})
    if queued_backoff_jobs:
        events.append({"type": "worker.queue_backoff", "count": len(queued_backoff_jobs)})
    if leased_expired_jobs:
        events.append({"type": "worker.lease_expired", "count": len(leased_expired_jobs)})
    if worker_cycle_saturated:
        events.append(
            {
                "type": "worker.cycle_gate_saturated",
                "active_count": worker_cycle_active,
                "max_concurrent_cycles": worker_cycle_max,
            }
        )
    if deadletters:
        events.append({"type": "queue.deadletter_present", "count": len(deadletters)})
    if inbox_alert_count > 0:
        events.append({"type": "inbox.alerts_present", "count": inbox_alert_count})
    if telemetry_error_count > 0:
        events.append({"type": "telemetry.errors_present", "count": telemetry_error_count})
    if telemetry_critical_count > 0:
        events.append({"type": "telemetry.critical_present", "count": telemetry_critical_count})

    return {
        "events": events,
        "active_mission_count": len(active_missions),
        "queued_mission_ids": queued_mission_ids,
        "worker_queue_due_count": len(queued_due_jobs),
        "worker_queue_backoff_count": len(queued_backoff_jobs),
        "worker_leased_count": len(leased_jobs),
        "worker_leased_expired_count": len(leased_expired_jobs),
        "worker_leased_expired_classes_top": leased_expired_classes_top,
        "worker_due_actions_top": worker_due_actions_top,
        "worker_cycle_active_count": worker_cycle_active,
        "worker_cycle_max_concurrent": worker_cycle_max,
        "worker_cycle_gate_saturated": worker_cycle_saturated,
        "worker_last_lease_renewed_count": worker_last_lease_renewed_count,
        "worker_last_lease_lost_count": worker_last_lease_lost_count,
        "worker_last_lease_conflict_count": worker_last_lease_conflict_count,
        "worker_last_recovered_count": worker_last_recovered_count,
        "deadletter_count": len(deadletters),
        "open_incident_count": len(open_incidents),
        "critical_incident_count": len(critical_incidents),
        "inbox_alert_count": inbox_alert_count,
        "telemetry_event_count_horizon": len(telemetry_in_horizon),
        "telemetry_warn_count_horizon": telemetry_warn_count,
        "telemetry_error_count_horizon": telemetry_error_count,
        "telemetry_critical_count_horizon": telemetry_critical_count,
        "telemetry_streams_top": telemetry_streams_top,
        "telemetry_last_event_ts": last_telemetry.get("ts") if isinstance(last_telemetry, dict) else None,
        "telemetry_last_event_stream": last_telemetry.get("stream") if isinstance(last_telemetry, dict) else None,
        "observer_scan_due": observer_scan_due,
    }
