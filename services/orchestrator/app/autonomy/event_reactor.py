from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from francis_core.workspace_fs import WorkspaceFS
from services.orchestrator.app.runtime_hygiene import (
    count_active_deadletters,
    count_active_inbox_alerts,
    is_open_incident,
    runtime_hygiene_candidate_breakdown,
    runtime_hygiene_candidate_count,
    summarize_runtime_hygiene_candidates,
)

EVENT_REACTOR_SUMMARY_VERSION = 1
EVENT_REACTOR_SUMMARY_PATH = "autonomy/reactor_events_summary.json"
EVENT_REACTOR_SOURCE_PATHS = (
    "missions/missions.json",
    "queue/jobs.jsonl",
    "queue/deadletter.jsonl",
    "incidents/incidents.jsonl",
    "inbox/messages.jsonl",
    "telemetry/events.jsonl",
    "runs/last_run.json",
    "runs/last_worker_run.json",
    "queue/worker_cycle_gate.json",
)


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


def _resolve_workspace_path(fs: WorkspaceFS, rel_path: str) -> Path:
    return (fs.roots[0] / rel_path).resolve()


def _path_signature(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    stat = path.stat()
    return {
        "exists": True,
        "mtime_ns": int(stat.st_mtime_ns),
        "size": int(stat.st_size),
    }


def _source_signature(fs: WorkspaceFS) -> dict[str, dict[str, Any]]:
    return {
        rel_path: _path_signature(_resolve_workspace_path(fs, rel_path))
        for rel_path in EVENT_REACTOR_SOURCE_PATHS
    }


def _load_summary_doc(fs: WorkspaceFS) -> dict[str, Any] | None:
    try:
        raw = fs.read_text(EVENT_REACTOR_SUMMARY_PATH)
    except Exception:
        return None
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _write_summary_doc(
    fs: WorkspaceFS,
    *,
    payload: dict[str, Any],
    source_signature: dict[str, dict[str, Any]],
    scan_interval_seconds: int,
    telemetry_horizon_hours: int,
    refresh_after: datetime | None,
) -> dict[str, Any]:
    doc = {
        "version": EVENT_REACTOR_SUMMARY_VERSION,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "params": {
            "scan_interval_seconds": int(scan_interval_seconds),
            "telemetry_horizon_hours": int(telemetry_horizon_hours),
        },
        "refresh_after": refresh_after.isoformat() if refresh_after is not None else None,
        "source_signature": source_signature,
        "payload": payload,
    }
    fs.write_text(EVENT_REACTOR_SUMMARY_PATH, json.dumps(doc, ensure_ascii=False, indent=2))
    return doc


def _summary_is_usable(
    doc: dict[str, Any] | None,
    *,
    source_signature: dict[str, dict[str, Any]],
    scan_interval_seconds: int,
    telemetry_horizon_hours: int,
    now: datetime,
) -> bool:
    if not isinstance(doc, dict):
        return False
    if int(doc.get("version", 0) or 0) != EVENT_REACTOR_SUMMARY_VERSION:
        return False
    params = doc.get("params", {}) if isinstance(doc.get("params"), dict) else {}
    if int(params.get("scan_interval_seconds", 0) or 0) != int(scan_interval_seconds):
        return False
    if int(params.get("telemetry_horizon_hours", 0) or 0) != int(telemetry_horizon_hours):
        return False
    if doc.get("source_signature") != source_signature:
        return False
    refresh_after = _parse_ts(str(doc.get("refresh_after", "")).strip() or None)
    if refresh_after is not None and refresh_after <= now:
        return False
    return isinstance(doc.get("payload"), dict)


def _earliest_future_ts(
    current: datetime | None,
    candidate: datetime | None,
    *,
    now: datetime,
) -> datetime | None:
    if candidate is None or candidate <= now:
        return current
    if current is None or candidate < current:
        return candidate
    return current


def collect_events(
    fs: WorkspaceFS,
    *,
    scan_interval_seconds: int = 300,
    telemetry_horizon_hours: int = 24,
    now: datetime | None = None,
) -> dict[str, Any]:
    reference_now = now or datetime.now(timezone.utc)
    signature = _source_signature(fs)
    cached = _load_summary_doc(fs)
    if _summary_is_usable(
        cached,
        source_signature=signature,
        scan_interval_seconds=scan_interval_seconds,
        telemetry_horizon_hours=telemetry_horizon_hours,
        now=reference_now,
    ):
        payload = cached.get("payload", {})
        return dict(payload) if isinstance(payload, dict) else {}

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
    refresh_after: datetime | None = None
    queued_due_jobs: list[dict[str, Any]] = []
    queued_backoff_jobs: list[dict[str, Any]] = []
    leased_expired_jobs: list[dict[str, Any]] = []
    for job in queued_jobs:
        next_run_after = _parse_ts(str(job.get("next_run_after", "")).strip() or None)
        if next_run_after is None or next_run_after <= reference_now:
            queued_due_jobs.append(job)
        else:
            queued_backoff_jobs.append(job)
            refresh_after = _earliest_future_ts(refresh_after, next_run_after, now=reference_now)
    for job in leased_jobs:
        lease_expires_at = _parse_ts(str(job.get("lease_expires_at", "")).strip() or None)
        if lease_expires_at is not None and lease_expires_at <= reference_now:
            leased_expired_jobs.append(job)
        else:
            refresh_after = _earliest_future_ts(refresh_after, lease_expires_at, now=reference_now)
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
    active_deadletter_count = count_active_deadletters(deadletters)
    incidents = _read_jsonl(fs, "incidents/incidents.jsonl")
    open_incidents = [i for i in incidents if is_open_incident(i)]
    critical_incidents = [i for i in open_incidents if str(i.get("severity", "")).lower() == "critical"]

    inbox_rows = _read_jsonl(fs, "inbox/messages.jsonl")
    inbox_alert_count = count_active_inbox_alerts(inbox_rows)
    telemetry_rows = _read_jsonl(fs, "telemetry/events.jsonl")
    horizon_delta = timedelta(hours=max(1, min(168, _safe_int(telemetry_horizon_hours, 24))))
    telemetry_horizon = reference_now - horizon_delta
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
        refresh_after = _earliest_future_ts(refresh_after, ts + horizon_delta if ts is not None else None, now=reference_now)
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
    hygiene_preview = summarize_runtime_hygiene_candidates(
        missions_doc=missions_doc if isinstance(missions_doc, dict) else {"missions": []},
        jobs=jobs,
        deadletters=deadletters,
        incidents=incidents,
        inbox=inbox_rows,
        telemetry_events=telemetry_rows,
        now=reference_now,
    )
    refresh_after = _earliest_future_ts(
        refresh_after,
        _parse_ts(str(hygiene_preview.get("next_refresh_after", "")).strip() or None),
        now=reference_now,
    )
    hygiene_breakdown = runtime_hygiene_candidate_breakdown(hygiene_preview)
    hygiene_candidate_count = runtime_hygiene_candidate_count(hygiene_preview)
    hygiene_categories_top = [
        {"key": key, "count": count}
        for key, count in sorted(hygiene_breakdown.items(), key=lambda kv: kv[1], reverse=True)[:5]
    ]

    last_run = _read_json(fs, "runs/last_run.json", {})
    last_run_ts = _parse_ts(last_run.get("ts")) if isinstance(last_run, dict) else None
    observer_scan_due = last_run_ts is None or (reference_now - last_run_ts).total_seconds() >= scan_interval_seconds
    if last_run_ts is not None and not observer_scan_due:
        refresh_after = _earliest_future_ts(
            refresh_after,
            last_run_ts + timedelta(seconds=max(1, int(scan_interval_seconds))),
            now=reference_now,
        )
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
    if active_deadletter_count > 0:
        events.append({"type": "queue.deadletter_present", "count": active_deadletter_count})
    if inbox_alert_count > 0:
        events.append({"type": "inbox.alerts_present", "count": inbox_alert_count})
    if telemetry_error_count > 0:
        events.append({"type": "telemetry.errors_present", "count": telemetry_error_count})
    if telemetry_critical_count > 0:
        events.append({"type": "telemetry.critical_present", "count": telemetry_critical_count})
    if hygiene_candidate_count > 0:
        events.append(
            {
                "type": "runtime.hygiene_due",
                "count": hygiene_candidate_count,
                "categories": hygiene_categories_top,
            }
        )

    payload = {
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
        "deadletter_count": active_deadletter_count,
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
        "runtime_hygiene_candidate_count": hygiene_candidate_count,
        "runtime_hygiene_categories_top": hygiene_categories_top,
        "runtime_hygiene_min_age_hours": hygiene_preview.get("min_age_hours", 24),
        "observer_scan_due": observer_scan_due,
    }
    _write_summary_doc(
        fs,
        payload=payload,
        source_signature=signature,
        scan_interval_seconds=scan_interval_seconds,
        telemetry_horizon_hours=telemetry_horizon_hours,
        refresh_after=refresh_after,
    )
    return payload
