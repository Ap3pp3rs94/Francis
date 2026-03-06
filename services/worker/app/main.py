from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from francis_brain.ledger import RunLedger
from francis_core.clock import utc_now_iso
from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS

from .executors.forge_executor import execute as execute_forge_job
from .executors.mission_executor import execute as execute_mission_job
from .executors.skill_executor import execute as execute_skill_job
from .queue import list_queued_jobs, queued_count
from .safety.resource_limits import normalize_limits
from .safety.sandbox import ensure_local_first

QUEUE_PATH = "queue/jobs.jsonl"
DEADLETTER_PATH = "queue/deadletter.jsonl"
LAST_WORKER_RUN_PATH = "runs/last_worker_run.json"
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_SECONDS = 10
MAX_BACKOFF_SECONDS = 3600
DEFAULT_LEASE_TTL_SECONDS = 120
DEFAULT_LEASE_HEARTBEAT_SECONDS = 15
DEFAULT_MAX_CONCURRENT_CYCLES = 1
QUEUE_LOCK = threading.RLock()
CYCLE_GATE_LOCK = threading.RLock()
CYCLE_GATE_PATH = "queue/worker_cycle_gate.json"
ACTIVE_WORKER_CYCLES: set[str] = set()
DEFAULT_ACTION_POLICIES: dict[str, dict[str, int | None]] = {
    "forge.propose": {"max_attempts": 2, "base_backoff_seconds": 10, "timeout_seconds": 30},
    "skill.run": {"max_attempts": 3, "base_backoff_seconds": 15, "timeout_seconds": 120},
}


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _normalize_trace_id(trace_id: str | None, *, fallback_run_id: str) -> str:
    normalized = str(trace_id or "").strip()
    return normalized or fallback_run_id


def _action_policy(action: str) -> dict[str, int | None]:
    policy: dict[str, int | None] = {
        "max_attempts": DEFAULT_MAX_ATTEMPTS,
        "base_backoff_seconds": DEFAULT_BACKOFF_SECONDS,
        "timeout_seconds": None,
    }
    if action in DEFAULT_ACTION_POLICIES:
        policy.update(DEFAULT_ACTION_POLICIES[action])
    return policy


def _priority_bucket(value: Any) -> str:
    text = str(value).strip().lower()
    if text in {"critical", "urgent", "high", "normal", "low"}:
        return text
    return "normal"


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


def _write_jsonl(fs: WorkspaceFS, rel_path: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        fs.write_text(rel_path, "")
        return
    fs.write_text(rel_path, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))


def _append_jsonl(fs: WorkspaceFS, rel_path: str, row: dict[str, Any]) -> None:
    rows = _read_jsonl(fs, rel_path)
    rows.append(row)
    _write_jsonl(fs, rel_path, rows)


def _read_json(fs: WorkspaceFS, rel_path: str, default: Any) -> Any:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        return default
    try:
        parsed = json.loads(raw)
    except Exception:
        return default
    return parsed


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _record_deadletter(
    fs: WorkspaceFS,
    *,
    parent_run_id: str,
    job: dict[str, Any],
    reason: str,
    result: dict[str, Any],
    trace_id: str | None = None,
) -> None:
    normalized_trace_id = _normalize_trace_id(
        str(job.get("trace_id", "")).strip() or trace_id,
        fallback_run_id=parent_run_id,
    )
    _append_jsonl(
        fs,
        DEADLETTER_PATH,
        {
            "id": str(uuid4()),
            "ts": utc_now_iso(),
            "run_id": parent_run_id,
            "trace_id": normalized_trace_id,
            "mission_id": job.get("mission_id"),
            "reason": reason,
            "job": job,
            "result": result,
            "kind": "worker.deadletter",
        },
    )


def _action_class(action: Any) -> str:
    text = str(action).strip().lower()
    if not text:
        return "unknown"
    if "." in text:
        head = text.split(".", 1)[0].strip()
        return head or "unknown"
    return text


def _recover_stale_leases(
    fs: WorkspaceFS,
    *,
    action_classes: set[str] | None = None,
) -> tuple[int, dict[str, int], dict[str, int]]:
    normalized_classes = (
        {str(item).strip().lower() for item in action_classes if str(item).strip()}
        if action_classes is not None
        else None
    )
    with QUEUE_LOCK:
        jobs = _read_jsonl(fs, QUEUE_PATH)
        now = datetime.now(timezone.utc)
        recovered = 0
        changed = False
        by_action_class: dict[str, int] = {}
        by_action: dict[str, int] = {}
        for idx, row in enumerate(jobs):
            if str(row.get("status", "")).strip().lower() != "leased":
                continue
            lease_expires_at = _parse_iso(str(row.get("lease_expires_at", "")).strip() or None)
            if lease_expires_at is None or lease_expires_at > now:
                continue
            action = str(row.get("action", "")).strip().lower() or "unknown"
            klass = _action_class(action)
            if normalized_classes is not None and klass not in normalized_classes:
                continue
            updated = dict(row)
            updated["status"] = "queued"
            updated["lease_key"] = None
            updated["lease_owner"] = None
            updated["lease_expires_at"] = None
            jobs[idx] = updated
            recovered += 1
            changed = True
            by_action_class[klass] = by_action_class.get(klass, 0) + 1
            by_action[action] = by_action.get(action, 0) + 1
        if changed:
            _write_jsonl(fs, QUEUE_PATH, jobs)
        return (recovered, by_action_class, by_action)


def _write_cycle_gate_state(fs: WorkspaceFS, *, max_concurrent_cycles: int) -> None:
    active_ids = sorted(ACTIVE_WORKER_CYCLES)
    active_count = len(active_ids)
    payload = {
        "updated_at": utc_now_iso(),
        "active_run_ids": active_ids,
        "active_count": active_count,
        "max_concurrent_cycles": max(1, int(max_concurrent_cycles)),
        "saturated": active_count >= max(1, int(max_concurrent_cycles)),
    }
    try:
        fs.write_text(CYCLE_GATE_PATH, json.dumps(payload, ensure_ascii=False, indent=2))
    except Exception:
        return


def _acquire_cycle_slot(
    fs: WorkspaceFS,
    *,
    run_id: str,
    max_concurrent_cycles: int,
) -> tuple[bool, int]:
    with CYCLE_GATE_LOCK:
        max_cycles = max(1, int(max_concurrent_cycles))
        if run_id in ACTIVE_WORKER_CYCLES:
            _write_cycle_gate_state(fs, max_concurrent_cycles=max_cycles)
            return (True, len(ACTIVE_WORKER_CYCLES))
        if len(ACTIVE_WORKER_CYCLES) >= max_cycles:
            _write_cycle_gate_state(fs, max_concurrent_cycles=max_cycles)
            return (False, len(ACTIVE_WORKER_CYCLES))
        ACTIVE_WORKER_CYCLES.add(run_id)
        _write_cycle_gate_state(fs, max_concurrent_cycles=max_cycles)
        return (True, len(ACTIVE_WORKER_CYCLES))


def _release_cycle_slot(fs: WorkspaceFS, *, run_id: str, max_concurrent_cycles: int) -> None:
    with CYCLE_GATE_LOCK:
        ACTIVE_WORKER_CYCLES.discard(run_id)
        _write_cycle_gate_state(fs, max_concurrent_cycles=max(1, int(max_concurrent_cycles)))


def _active_cycle_count() -> int:
    with CYCLE_GATE_LOCK:
        return len(ACTIVE_WORKER_CYCLES)


def _reclaim_expired_leases(fs: WorkspaceFS) -> int:
    reclaimed, _by_action_class, _by_action = _recover_stale_leases(fs)
    return reclaimed


def _count_active_leases(fs: WorkspaceFS, *, action_allowlist: set[str] | None) -> int:
    jobs = _read_jsonl(fs, QUEUE_PATH)
    now = datetime.now(timezone.utc)
    count = 0
    for row in jobs:
        if str(row.get("status", "")).strip().lower() != "leased":
            continue
        action = str(row.get("action", "")).strip().lower()
        if action_allowlist is not None and action not in action_allowlist:
            continue
        lease_expires_at = _parse_iso(str(row.get("lease_expires_at", "")).strip() or None)
        if lease_expires_at is not None and lease_expires_at > now:
            count += 1
    return count


def _acquire_non_mission_lease(
    fs: WorkspaceFS,
    *,
    job_id: str,
    lease_owner: str,
    lease_ttl_seconds: int,
    trace_id: str | None = None,
) -> tuple[bool, dict[str, Any] | None, str]:
    with QUEUE_LOCK:
        jobs = _read_jsonl(fs, QUEUE_PATH)
        now = datetime.now(timezone.utc)
        idx: int | None = None
        row: dict[str, Any] | None = None
        for i, candidate in enumerate(jobs):
            if str(candidate.get("id", "")).strip() == job_id:
                idx = i
                row = dict(candidate)
                break
        if idx is None or row is None:
            return (False, None, "missing")

        status = str(row.get("status", "")).strip().lower()
        if status == "leased":
            lease_expires_at = _parse_iso(str(row.get("lease_expires_at", "")).strip() or None)
            if lease_expires_at is not None and lease_expires_at > now:
                return (False, row, "busy")
            row["status"] = "queued"
            row["lease_key"] = None
            row["lease_owner"] = None
            row["lease_expires_at"] = None
            status = "queued"

        if status != "queued":
            return (False, row, status or "not_queued")

        next_run_after = _parse_iso(str(row.get("next_run_after", "")).strip() or None)
        if next_run_after is not None and next_run_after > now:
            return (False, row, "backoff")

        normalized_trace_id = _normalize_trace_id(
            str(row.get("trace_id", "")).strip() or trace_id,
            fallback_run_id=lease_owner,
        )
        row["trace_id"] = normalized_trace_id
        lease_key = str(uuid4())
        row["status"] = "leased"
        row["lease_key"] = lease_key
        row["lease_owner"] = lease_owner
        row["lease_expires_at"] = (now + timedelta(seconds=max(5, min(600, lease_ttl_seconds)))).isoformat()
        jobs[idx] = row
        _write_jsonl(fs, QUEUE_PATH, jobs)
        return (True, row, "leased")


def _renew_non_mission_lease(
    fs: WorkspaceFS,
    *,
    job_id: str,
    lease_owner: str,
    lease_key: str,
    lease_ttl_seconds: int,
) -> bool:
    with QUEUE_LOCK:
        jobs = _read_jsonl(fs, QUEUE_PATH)
        idx: int | None = None
        row: dict[str, Any] | None = None
        for i, candidate in enumerate(jobs):
            if str(candidate.get("id", "")).strip() == job_id:
                idx = i
                row = dict(candidate)
                break
        if idx is None or row is None:
            return False
        if str(row.get("status", "")).strip().lower() != "leased":
            return False
        if str(row.get("lease_owner", "")).strip() != lease_owner:
            return False
        if str(row.get("lease_key", "")).strip() != lease_key:
            return False
        row["lease_expires_at"] = (
            datetime.now(timezone.utc) + timedelta(seconds=max(5, min(600, lease_ttl_seconds)))
        ).isoformat()
        jobs[idx] = row
        _write_jsonl(fs, QUEUE_PATH, jobs)
        return True


def _execute_with_lease_heartbeat(
    fn: Callable[[], dict[str, Any]],
    *,
    fs: WorkspaceFS,
    job_id: str,
    lease_owner: str,
    lease_key: str,
    lease_ttl_seconds: int,
    heartbeat_seconds: int,
) -> tuple[dict[str, Any], int, bool]:
    renewals = 0
    lease_lost = False
    step_timeout = max(1, heartbeat_seconds)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn)
        while True:
            try:
                result = future.result(timeout=step_timeout)
                if isinstance(result, dict):
                    return (result, renewals, lease_lost)
                return ({"ok": False, "error": "executor returned non-dict result"}, renewals, lease_lost)
            except FutureTimeoutError:
                renewed = _renew_non_mission_lease(
                    fs,
                    job_id=job_id,
                    lease_owner=lease_owner,
                    lease_key=lease_key,
                    lease_ttl_seconds=lease_ttl_seconds,
                )
                if renewed:
                    renewals += 1
                else:
                    lease_lost = True
            except Exception as exc:
                return ({"ok": False, "error": f"executor exception: {exc}"}, renewals, lease_lost)


def _finalize_non_mission_job(
    fs: WorkspaceFS,
    *,
    parent_run_id: str,
    job: dict[str, Any],
    result: dict[str, Any],
    action_policy: dict[str, int | None],
    lease_owner: str,
    lease_key: str,
    trace_id: str | None = None,
) -> tuple[str, dict[str, Any] | None]:
    with QUEUE_LOCK:
        jobs = _read_jsonl(fs, QUEUE_PATH)
        job_id = str(job.get("id", "")).strip()
        if not job_id:
            return ("missing", None)

        idx: int | None = None
        for i, row in enumerate(jobs):
            if str(row.get("id", "")).strip() == job_id:
                idx = i
                break
        if idx is None:
            return ("missing", None)

        now = datetime.now(timezone.utc)
        row = dict(jobs[idx])
        if str(row.get("status", "")).strip().lower() != "leased":
            return ("not_leased", row)
        if str(row.get("lease_owner", "")).strip() != lease_owner:
            return ("lease_owner_mismatch", row)
        if str(row.get("lease_key", "")).strip() != lease_key:
            return ("lease_key_mismatch", row)

        attempts = _safe_int(row.get("attempts", 0), 0) + 1
        row["attempts"] = attempts
        row["last_result"] = result
        row["last_error"] = str(result.get("error", ""))
        row["trace_id"] = _normalize_trace_id(
            str(row.get("trace_id", "")).strip() or trace_id,
            fallback_run_id=parent_run_id,
        )
        row["lease_key"] = None
        row["lease_owner"] = None
        row["lease_expires_at"] = None

        if bool(result.get("ok")):
            row["status"] = "done"
            row["finished_at"] = now.isoformat()
            row["next_run_after"] = None
            jobs[idx] = row
            _write_jsonl(fs, QUEUE_PATH, jobs)
            return ("done", row)

        default_max_attempts = _safe_int(action_policy.get("max_attempts", DEFAULT_MAX_ATTEMPTS), DEFAULT_MAX_ATTEMPTS)
        max_attempts = max(1, _safe_int(row.get("max_attempts", default_max_attempts), default_max_attempts))
        if attempts >= max_attempts:
            row["status"] = "failed"
            row["finished_at"] = now.isoformat()
            row["next_run_after"] = None
            jobs[idx] = row
            _write_jsonl(fs, QUEUE_PATH, jobs)
            _record_deadletter(
                fs,
                parent_run_id=parent_run_id,
                job=row,
                reason=row["last_error"],
                result=result,
                trace_id=str(row.get("trace_id", "")).strip() or trace_id,
            )
            return ("deadlettered", row)

        default_backoff = _safe_int(action_policy.get("base_backoff_seconds", DEFAULT_BACKOFF_SECONDS), DEFAULT_BACKOFF_SECONDS)
        base_backoff = max(1, _safe_int(row.get("base_backoff_seconds", default_backoff), default_backoff))
        wait_seconds = min(MAX_BACKOFF_SECONDS, base_backoff * (2 ** (attempts - 1)))
        row["status"] = "queued"
        row["finished_at"] = None
        row["next_run_after"] = (now + timedelta(seconds=wait_seconds)).isoformat()
        row["backoff_seconds"] = wait_seconds
        jobs[idx] = row
        _write_jsonl(fs, QUEUE_PATH, jobs)
        return ("requeued", row)


def recover_stale_leased_jobs(
    *,
    run_id: str | None = None,
    trace_id: str | None = None,
    action_classes: set[str] | None = None,
) -> dict[str, Any]:
    effective_run_id = (run_id or str(uuid4())).strip()
    normalized_trace_id = _normalize_trace_id(trace_id, fallback_run_id=effective_run_id)
    workspace_root = Path(settings.workspace_root).resolve()
    repo_root = workspace_root.parent.resolve()
    ensure_local_first(repo_root=repo_root, workspace_root=workspace_root)

    fs = WorkspaceFS(
        roots=[workspace_root],
        journal_path=(workspace_root / "journals" / "fs.jsonl").resolve(),
    )
    ledger = RunLedger(fs, rel_path="runs/run_ledger.jsonl")
    recovered_count, by_action_class, by_action = _recover_stale_leases(fs, action_classes=action_classes)
    normalized_classes = (
        sorted({str(item).strip().lower() for item in action_classes if str(item).strip()})
        if action_classes is not None
        else None
    )
    summary = {
        "status": "ok",
        "run_id": effective_run_id,
        "trace_id": normalized_trace_id,
        "recovered_count": recovered_count,
        "action_classes": normalized_classes,
        "recovered_by_action_class": by_action_class,
        "recovered_by_action": by_action,
    }

    _append_jsonl(
        fs,
        "journals/decisions.jsonl",
        {
            "id": str(uuid4()),
            "ts": utc_now_iso(),
            "run_id": effective_run_id,
            "trace_id": normalized_trace_id,
            "kind": "worker.recover_leases",
            "recovered_count": recovered_count,
            "recovered_by_action_class": by_action_class,
            "recovered_by_action": by_action,
            "action_classes": normalized_classes,
        },
    )
    ledger.append(
        run_id=effective_run_id,
        kind="worker.recover_leases",
        summary={
            "recovered_count": recovered_count,
            "recovered_by_action_class": by_action_class,
            "action_classes": normalized_classes,
            "trace_id": normalized_trace_id,
        },
    )
    return summary


def run_worker_cycle(
    *,
    run_id: str | None = None,
    trace_id: str | None = None,
    max_jobs: int = 20,
    max_runtime_seconds: int = 60,
    action_allowlist: set[str] | None = None,
    action_limits: dict[str, int] | None = None,
    action_timeouts: dict[str, int] | None = None,
    lease_ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
    lease_heartbeat_seconds: int = DEFAULT_LEASE_HEARTBEAT_SECONDS,
    max_concurrent_cycles: int = DEFAULT_MAX_CONCURRENT_CYCLES,
) -> dict[str, Any]:
    effective_run_id = (run_id or str(uuid4())).strip()
    normalized_trace_id = _normalize_trace_id(trace_id, fallback_run_id=effective_run_id)
    workspace_root = Path(settings.workspace_root).resolve()
    repo_root = workspace_root.parent.resolve()
    ensure_local_first(repo_root=repo_root, workspace_root=workspace_root)

    fs = WorkspaceFS(
        roots=[workspace_root],
        journal_path=(workspace_root / "journals" / "fs.jsonl").resolve(),
    )
    ledger = RunLedger(fs, rel_path="runs/run_ledger.jsonl")
    limits = normalize_limits(max_jobs_per_cycle=max_jobs, max_runtime_seconds=max_runtime_seconds)
    allowlist = {a.strip().lower() for a in action_allowlist} if action_allowlist else None
    lease_ttl_seconds = max(5, min(600, _safe_int(lease_ttl_seconds, DEFAULT_LEASE_TTL_SECONDS)))
    lease_heartbeat_seconds = max(
        1,
        min(
            300,
            _safe_int(
                lease_heartbeat_seconds,
                min(DEFAULT_LEASE_HEARTBEAT_SECONDS, max(1, lease_ttl_seconds - 1)),
            ),
        ),
    )
    action_limits_norm = (
        {str(k).strip().lower(): max(1, _safe_int(v, 1)) for k, v in action_limits.items() if str(k).strip()}
        if isinstance(action_limits, dict)
        else {}
    )
    action_timeouts_norm = (
        {str(k).strip().lower(): max(0, _safe_int(v, 0)) for k, v in action_timeouts.items() if str(k).strip()}
        if isinstance(action_timeouts, dict)
        else {}
    )
    max_concurrent_cycles = max(1, min(32, _safe_int(max_concurrent_cycles, DEFAULT_MAX_CONCURRENT_CYCLES)))

    acquired_slot, active_cycles = _acquire_cycle_slot(
        fs,
        run_id=effective_run_id,
        max_concurrent_cycles=max_concurrent_cycles,
    )
    if not acquired_slot:
        queue_before = queued_count(fs, action_allowlist=allowlist, due_only=False)
        queue_due_before = queued_count(fs, action_allowlist=allowlist, due_only=True)
        summary = {
            "status": "blocked",
            "run_id": effective_run_id,
            "trace_id": normalized_trace_id,
            "reason": "max concurrent worker cycles reached",
            "active_worker_cycles": active_cycles,
            "max_concurrent_cycles": max_concurrent_cycles,
            "queue_before": queue_before,
            "queue_due_before": queue_due_before,
            "processed_count": 0,
            "success_count": 0,
            "error_count": 0,
            "requeued_count": 0,
            "deadlettered_count": 0,
            "deferred_count": 0,
            "deferred_by_action": {},
            "lease_busy_count": 0,
            "lease_renewed_count": 0,
            "lease_lost_count": 0,
            "lease_finalize_conflict_count": 0,
            "reclaimed_leases_count": 0,
            "recovered_leases_by_action_class": {},
            "recovered_leases_by_action": {},
            "halted_reason": "concurrency_gate",
            "jobs": [],
        }
        _append_jsonl(
            fs,
            "journals/decisions.jsonl",
            {
                "id": str(uuid4()),
                "ts": utc_now_iso(),
                "run_id": effective_run_id,
                "trace_id": normalized_trace_id,
                "kind": "worker.cycle.blocked",
                "reason": summary["reason"],
                "active_worker_cycles": active_cycles,
                "max_concurrent_cycles": max_concurrent_cycles,
            },
        )
        ledger.append(
            run_id=effective_run_id,
            kind="worker.cycle.blocked",
            summary={
                "reason": summary["reason"],
                "active_worker_cycles": active_cycles,
                "max_concurrent_cycles": max_concurrent_cycles,
                "trace_id": normalized_trace_id,
            },
        )
        return summary

    try:
        started_at = utc_now_iso()
        started_monotonic = time.monotonic()
        reclaimed_leases_count, recovered_by_action_class, recovered_by_action = _recover_stale_leases(fs)
        queue_before = queued_count(fs, action_allowlist=allowlist, due_only=False)
        queue_due_before = queued_count(fs, action_allowlist=allowlist, due_only=True)
        queued = list_queued_jobs(fs, limit=limits.max_jobs_per_cycle, action_allowlist=allowlist, due_only=True)

        processed: list[dict[str, Any]] = []
        success_count = 0
        error_count = 0
        requeued_count = 0
        deadlettered_count = 0
        deferred_by_action: dict[str, int] = {}
        action_processed_counts: dict[str, int] = {}
        lease_busy_count = _count_active_leases(fs, action_allowlist=allowlist)
        lease_renewed_count = 0
        lease_lost_count = 0
        lease_finalize_conflict_count = 0
        halted_reason = "completed"

        for job in queued:
            if (time.monotonic() - started_monotonic) >= limits.max_runtime_seconds:
                halted_reason = "runtime_budget_exceeded"
                break

            action = str(job.get("action", "")).strip().lower()
            job_trace_id = _normalize_trace_id(
                str(job.get("trace_id", "")).strip() or normalized_trace_id,
                fallback_run_id=normalized_trace_id,
            )
            job_run_id = f"{effective_run_id}:job:{job.get('id', uuid4())}"
            action_policy = _action_policy(action)

            if action in action_limits_norm:
                current = action_processed_counts.get(action, 0)
                if current >= action_limits_norm[action]:
                    deferred_by_action[action] = deferred_by_action.get(action, 0) + 1
                    continue
            action_processed_counts[action] = action_processed_counts.get(action, 0) + 1
            action_started = time.monotonic()

            if action == "mission.tick":
                result = execute_mission_job(job, run_id=job_run_id, trace_id=job_trace_id)
                queue_outcome = "delegated"
            else:
                leased, leased_job, lease_state = _acquire_non_mission_lease(
                    fs,
                    job_id=str(job.get("id", "")),
                    lease_owner=effective_run_id,
                    lease_ttl_seconds=lease_ttl_seconds,
                    trace_id=job_trace_id,
                )
                if not leased:
                    if lease_state == "busy":
                        lease_busy_count += 1
                    deferred_by_action[action] = deferred_by_action.get(action, 0) + 1
                    continue

                leased_ref = dict(leased_job or job)
                leased_ref["trace_id"] = _normalize_trace_id(
                    str(leased_ref.get("trace_id", "")).strip() or job_trace_id,
                    fallback_run_id=normalized_trace_id,
                )
                lease_key = str(leased_ref.get("lease_key", ""))
                leased_job_id = str(leased_ref.get("id", "")) or str(job.get("id", ""))

                if action.startswith("forge."):
                    result, renewals, lease_lost = _execute_with_lease_heartbeat(
                        lambda: execute_forge_job(leased_ref, run_id=job_run_id, fs=fs),
                        fs=fs,
                        job_id=leased_job_id,
                        lease_owner=effective_run_id,
                        lease_key=lease_key,
                        lease_ttl_seconds=lease_ttl_seconds,
                        heartbeat_seconds=lease_heartbeat_seconds,
                    )
                elif action == "skill.run":
                    result, renewals, lease_lost = _execute_with_lease_heartbeat(
                        lambda: execute_skill_job(leased_ref, run_id=job_run_id, fs=fs, repo_root=repo_root),
                        fs=fs,
                        job_id=leased_job_id,
                        lease_owner=effective_run_id,
                        lease_key=lease_key,
                        lease_ttl_seconds=lease_ttl_seconds,
                        heartbeat_seconds=lease_heartbeat_seconds,
                    )
                else:
                    result = {
                        "ok": False,
                        "run_id": job_run_id,
                        "trace_id": job_trace_id,
                        "job_id": str(job.get("id", "")),
                        "action": action,
                        "error": f"unsupported action: {action}",
                    }
                    renewals = 0
                    lease_lost = False

                lease_renewed_count += renewals
                if lease_lost:
                    lease_lost_count += 1
                    existing_error = str(result.get("error", "")).strip()
                    lease_error = f"lease lost during execution for job {leased_job_id}"
                    result = {
                        **result,
                        "ok": False,
                        "lease_lost": True,
                        "error": f"{existing_error}; {lease_error}" if existing_error else lease_error,
                    }

                timeout_seconds = action_timeouts_norm.get(
                    action,
                    _safe_int(action_policy.get("timeout_seconds", -1), -1),
                )
                elapsed_ms = int((time.monotonic() - action_started) * 1000)
                if timeout_seconds >= 0 and elapsed_ms >= timeout_seconds * 1000:
                    result = {
                        **result,
                        "ok": False,
                        "timed_out": True,
                        "error": f"action runtime exceeded timeout ({elapsed_ms}ms >= {timeout_seconds * 1000}ms)",
                    }
                result.setdefault("trace_id", job_trace_id)
                queue_outcome, _job_after = _finalize_non_mission_job(
                    fs,
                    parent_run_id=effective_run_id,
                    job=leased_ref,
                    result=result,
                    action_policy=action_policy,
                    lease_owner=effective_run_id,
                    lease_key=lease_key,
                    trace_id=job_trace_id,
                )
                if queue_outcome in {"missing", "not_leased", "lease_owner_mismatch", "lease_key_mismatch"}:
                    lease_finalize_conflict_count += 1
                    existing_error = str(result.get("error", "")).strip()
                    finalize_error = f"lease finalize conflict: {queue_outcome}"
                    result = {
                        **result,
                        "ok": False,
                        "lease_finalize_conflict": True,
                        "error": f"{existing_error}; {finalize_error}" if existing_error else finalize_error,
                    }

            result.setdefault("trace_id", job_trace_id)
            if bool(result.get("ok")):
                success_count += 1
            else:
                error_count += 1
            if queue_outcome == "requeued":
                requeued_count += 1
            if queue_outcome == "deadlettered":
                deadlettered_count += 1

            _append_jsonl(
                fs,
                "logs/francis.log.jsonl",
                {
                    "id": str(uuid4()),
                    "ts": utc_now_iso(),
                    "run_id": effective_run_id,
                    "trace_id": job_trace_id,
                    "kind": "worker.job",
                    "action": action,
                    "job_id": str(job.get("id", "")),
                    "mission_id": str(job.get("mission_id", "")),
                    "queue_outcome": queue_outcome,
                    "ok": bool(result.get("ok")),
                    "error": str(result.get("error", "")),
                },
            )
            processed.append(
                {
                    "job_id": str(job.get("id", "")),
                    "trace_id": job_trace_id,
                    "action": action,
                    "mission_id": str(job.get("mission_id", "")),
                    "queue_outcome": queue_outcome,
                    "ok": bool(result.get("ok")),
                    "error": str(result.get("error", "")),
                    "result": result,
                }
            )

        completed_at = utc_now_iso()
        duration_ms = int((time.monotonic() - started_monotonic) * 1000)
        queue_after = queued_count(fs, action_allowlist=allowlist, due_only=False)
        queue_due_after = queued_count(fs, action_allowlist=allowlist, due_only=True)

        summary = {
            "status": "ok",
            "run_id": effective_run_id,
            "trace_id": normalized_trace_id,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "limits": {
                "max_jobs": limits.max_jobs_per_cycle,
                "max_runtime_seconds": limits.max_runtime_seconds,
                "lease_ttl_seconds": lease_ttl_seconds,
                "lease_heartbeat_seconds": lease_heartbeat_seconds,
                "max_concurrent_cycles": max_concurrent_cycles,
                "action_allowlist": sorted(allowlist) if allowlist else None,
                "action_limits": action_limits_norm or None,
                "action_timeouts": action_timeouts_norm or None,
            },
            "queue_before": queue_before,
            "queue_due_before": queue_due_before,
            "queue_after": queue_after,
            "queue_due_after": queue_due_after,
            "processed_count": len(processed),
            "success_count": success_count,
            "error_count": error_count,
            "requeued_count": requeued_count,
            "deadlettered_count": deadlettered_count,
            "deferred_count": sum(deferred_by_action.values()),
            "deferred_by_action": deferred_by_action,
            "lease_busy_count": lease_busy_count,
            "lease_renewed_count": lease_renewed_count,
            "lease_lost_count": lease_lost_count,
            "lease_finalize_conflict_count": lease_finalize_conflict_count,
            "reclaimed_leases_count": reclaimed_leases_count,
            "recovered_leases_by_action_class": recovered_by_action_class,
            "recovered_leases_by_action": recovered_by_action,
            "active_worker_cycles": active_cycles,
            "max_concurrent_cycles": max_concurrent_cycles,
            "halted_reason": halted_reason,
            "jobs": processed,
        }

        _append_jsonl(
            fs,
            "journals/decisions.jsonl",
            {
                "id": str(uuid4()),
                "ts": utc_now_iso(),
                "run_id": effective_run_id,
                "trace_id": normalized_trace_id,
                "kind": "worker.cycle",
                "queue_before": queue_before,
                "queue_due_before": queue_due_before,
                "queue_after": queue_after,
                "queue_due_after": queue_due_after,
                "processed_count": len(processed),
                "success_count": success_count,
                "error_count": error_count,
                "requeued_count": requeued_count,
                "deadlettered_count": deadlettered_count,
                "deferred_count": sum(deferred_by_action.values()),
                "lease_busy_count": lease_busy_count,
                "lease_renewed_count": lease_renewed_count,
                "lease_lost_count": lease_lost_count,
                "lease_finalize_conflict_count": lease_finalize_conflict_count,
                "reclaimed_leases_count": reclaimed_leases_count,
                "recovered_leases_by_action_class": recovered_by_action_class,
                "halted_reason": halted_reason,
            },
        )
        fs.write_text(LAST_WORKER_RUN_PATH, json.dumps(summary, ensure_ascii=False, indent=2))
        ledger.append(
            run_id=effective_run_id,
            kind="worker.cycle",
            summary={
                "queue_before": queue_before,
                "queue_due_before": queue_due_before,
                "queue_after": queue_after,
                "queue_due_after": queue_due_after,
                "processed_count": len(processed),
                "success_count": success_count,
                "error_count": error_count,
                "requeued_count": requeued_count,
                "deadlettered_count": deadlettered_count,
                "deferred_count": sum(deferred_by_action.values()),
                "lease_busy_count": lease_busy_count,
                "lease_renewed_count": lease_renewed_count,
                "lease_lost_count": lease_lost_count,
                "lease_finalize_conflict_count": lease_finalize_conflict_count,
                "reclaimed_leases_count": reclaimed_leases_count,
                "recovered_leases_by_action_class": recovered_by_action_class,
                "halted_reason": halted_reason,
                "trace_id": normalized_trace_id,
            },
        )
        return summary
    finally:
        _release_cycle_slot(
            fs,
            run_id=effective_run_id,
            max_concurrent_cycles=max_concurrent_cycles,
        )


def get_worker_status() -> dict[str, Any]:
    workspace_root = Path(settings.workspace_root).resolve()
    repo_root = workspace_root.parent.resolve()
    ensure_local_first(repo_root=repo_root, workspace_root=workspace_root)
    fs = WorkspaceFS(
        roots=[workspace_root],
        journal_path=(workspace_root / "journals" / "fs.jsonl").resolve(),
    )

    now = datetime.now(timezone.utc)
    jobs = _read_jsonl(fs, QUEUE_PATH)
    deadletters = _read_jsonl(fs, DEADLETTER_PATH)
    last_run = _read_json(fs, LAST_WORKER_RUN_PATH, {})
    cycle_gate_doc = _read_json(fs, CYCLE_GATE_PATH, {})
    if not isinstance(last_run, dict):
        last_run = {}
    if not isinstance(cycle_gate_doc, dict):
        cycle_gate_doc = {}

    counts = {
        "total_jobs": len(jobs),
        "queued_total": 0,
        "queued_due": 0,
        "queued_backoff": 0,
        "leased": 0,
        "leased_expired": 0,
        "done": 0,
        "failed": 0,
        "other": 0,
    }
    due_by_action: dict[str, int] = {}
    due_by_priority: dict[str, int] = {}
    failed_by_action: dict[str, int] = {}

    for job in jobs:
        action = str(job.get("action", "")).strip().lower() or "unknown"
        status = str(job.get("status", "")).strip().lower() or "unknown"
        if status == "queued":
            counts["queued_total"] += 1
            priority = _priority_bucket(job.get("priority", "normal"))
            next_run_after = _parse_iso(str(job.get("next_run_after", "")).strip() or None)
            if next_run_after is None or next_run_after <= now:
                counts["queued_due"] += 1
                due_by_action[action] = due_by_action.get(action, 0) + 1
                due_by_priority[priority] = due_by_priority.get(priority, 0) + 1
            else:
                counts["queued_backoff"] += 1
        elif status == "leased":
            counts["leased"] += 1
            lease_expires_at = _parse_iso(str(job.get("lease_expires_at", "")).strip() or None)
            if lease_expires_at is not None and lease_expires_at <= now:
                counts["leased_expired"] += 1
        elif status == "done":
            counts["done"] += 1
        elif status == "failed":
            counts["failed"] += 1
            failed_by_action[action] = failed_by_action.get(action, 0) + 1
        else:
            counts["other"] += 1

    deadletter_by_action: dict[str, int] = {}
    for item in deadletters:
        job = item.get("job", {})
        action = ""
        if isinstance(job, dict):
            action = str(job.get("action", "")).strip().lower()
        if not action:
            action = "unknown"
        deadletter_by_action[action] = deadletter_by_action.get(action, 0) + 1

    def _top(d: dict[str, int], n: int = 5) -> list[dict[str, Any]]:
        return [{"key": key, "count": count} for key, count in sorted(d.items(), key=lambda kv: kv[1], reverse=True)[:n]]

    gate_max = max(
        1,
        _safe_int(cycle_gate_doc.get("max_concurrent_cycles", DEFAULT_MAX_CONCURRENT_CYCLES), DEFAULT_MAX_CONCURRENT_CYCLES),
    )
    gate_active = max(0, _safe_int(cycle_gate_doc.get("active_count", _active_cycle_count()), _active_cycle_count()))

    return {
        "status": "ok",
        "utc_now": utc_now_iso(),
        "queue": {
            **counts,
            "due_by_action_top": _top(due_by_action),
            "due_by_priority_top": _top(due_by_priority),
            "failed_by_action_top": _top(failed_by_action),
        },
        "deadletter": {
            "count": len(deadletters),
            "by_action_top": _top(deadletter_by_action),
        },
        "cycle_gate": {
            "active_count": gate_active,
            "max_concurrent_cycles": gate_max,
            "saturated": gate_active >= gate_max,
            "active_run_ids": cycle_gate_doc.get("active_run_ids", []),
            "updated_at": cycle_gate_doc.get("updated_at"),
        },
        "last_worker_run": last_run,
    }


def main() -> None:
    summary = run_worker_cycle()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
