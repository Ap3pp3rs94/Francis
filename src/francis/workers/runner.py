from __future__ import annotations

import logging
import os
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from francis.agent import executor as agent_executor
from francis.telemetry.logging import log as telemetry_log

logger = logging.getLogger(__name__)

_TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "f", "no", "n", "off"}

__all__ = ["run_workers", "run", "main"]


@dataclass(frozen=True, slots=True)
class TaskExecutionOutcome:
    task_id: str
    worker_id: str
    status: str
    ok: bool
    duration_s: float
    error: str | None = None


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _to_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = _safe_str(value).strip().lower()
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    return default


def _to_int(value: Any, *, default: int, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    if parsed < minimum:
        return default
    return parsed


def _to_float(value: Any, *, default: float, minimum: float = 0.0) -> float:
    try:
        parsed = float(value)
    except Exception:
        return default
    if parsed <= minimum:
        return default
    return parsed


def _normalize_selector(value: Any, *, default: str = "default") -> str:
    text = _safe_str(value).strip().lower()
    if not text:
        return default
    return text


def _normalize_log_level(level: str) -> str:
    s = (level or "").strip().upper()
    if not s:
        return "INFO"
    if s == "WARN":
        return "WARNING"
    if s == "FATAL":
        return "CRITICAL"
    return s


def _ensure_logging(level: str) -> None:
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=getattr(logging, _normalize_log_level(level), logging.INFO),
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        )


def _emit_telemetry(event: str, **fields: Any) -> None:
    try:
        telemetry_log(event, **fields)
    except Exception:
        logger.debug("telemetry_write_failed event=%s", event, exc_info=True)


def _configure_runtime_paths(repo_root: str | Path | None) -> None:
    if repo_root is not None:
        root = _safe_str(repo_root).strip()
        if root:
            os.environ["FRANCIS_ROOT"] = str(Path(root).resolve())


def _extract_route_value(task: dict[str, Any], key: str) -> str:
    candidates: list[Any] = [
        task.get(key),
        task.get(f"route_{key}"),
        task.get(f"worker_{key}"),
    ]
    route = task.get("route")
    if isinstance(route, dict):
        candidates.append(route.get(key))
    routing = task.get("routing")
    if isinstance(routing, dict):
        candidates.append(routing.get(key))
    for value in candidates:
        normalized = _normalize_selector(value, default="")
        if normalized:
            return normalized
    return "default"


def _selector_matches(task_value: str, selected_value: str) -> bool:
    if selected_value == "*":
        return True
    if task_value == "*":
        return True
    return task_value == selected_value


def _task_matches_route(task: dict[str, Any], *, queue: str, kind: str) -> bool:
    task_queue = _extract_route_value(task, "queue")
    task_kind = _extract_route_value(task, "kind")
    return _selector_matches(task_queue, queue) and _selector_matches(
        task_kind, kind
    )


def _candidate_task_ids(*, queue: str, kind: str) -> list[str]:
    candidates: list[tuple[int, str, str]] = []
    for task_id in agent_executor._iter_task_ids():
        try:
            task = agent_executor.load_task(task_id)
        except Exception:
            continue
        if not agent_executor._is_runnable(task):
            continue
        if not _task_matches_route(task, queue=queue, kind=kind):
            continue
        priority = _to_int(task.get("priority"), default=0, minimum=0)
        updated_at = _safe_str(task.get("updated_at", ""))
        candidates.append((priority, updated_at, task_id))
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [task_id for _, _, task_id in candidates]


def _claim_next_task(*, worker_id: str, queue: str, kind: str) -> str | None:
    for task_id in _candidate_task_ids(queue=queue, kind=kind):
        if agent_executor._try_acquire_lock(task_id, worker_id):
            return task_id
    return None


def _execute_claimed_task(task_id: str, worker_id: str) -> TaskExecutionOutcome:
    started = time.monotonic()
    try:
        record = agent_executor.execute_task(task_id=task_id, worker_id=worker_id)
        status = _safe_str(record.get("status", ""))
        ok = status == "complete"
        reason = _safe_str(record.get("status_reason", "")).strip() or None
        return TaskExecutionOutcome(
            task_id=task_id,
            worker_id=worker_id,
            status=status,
            ok=ok,
            duration_s=time.monotonic() - started,
            error=reason,
        )
    except Exception as exc:
        logger.exception("task execution crashed task_id=%s worker_id=%s", task_id, worker_id)
        return TaskExecutionOutcome(
            task_id=task_id,
            worker_id=worker_id,
            status="failed",
            ok=False,
            duration_s=time.monotonic() - started,
            error=f"{type(exc).__name__}: {exc}",
        )
    finally:
        agent_executor._release_lock(task_id)


def _dispatch_cycle(
    *,
    concurrency: int,
    worker_prefix: str,
    queue: str,
    kind: str,
) -> list[TaskExecutionOutcome]:
    claims: list[tuple[str, str]] = []
    for slot in range(concurrency):
        worker_id = f"{worker_prefix}-{slot + 1}"
        task_id = _claim_next_task(worker_id=worker_id, queue=queue, kind=kind)
        if task_id is None:
            break
        claims.append((task_id, worker_id))
    if not claims:
        return []
    if len(claims) == 1:
        task_id, worker_id = claims[0]
        return [_execute_claimed_task(task_id, worker_id)]

    outcomes: list[TaskExecutionOutcome] = []
    with ThreadPoolExecutor(
        max_workers=len(claims),
        thread_name_prefix="francis-worker",
    ) as pool:
        future_map = {
            pool.submit(_execute_claimed_task, task_id, worker_id): (task_id, worker_id)
            for task_id, worker_id in claims
        }
        for future in as_completed(future_map):
            outcomes.append(future.result())
    return outcomes


def run_workers(
    *,
    concurrency: int = 4,
    poll_interval_s: float = 0.25,
    heartbeat_s: float = 10.0,
    queue: str = "default",
    kind: str = "default",
    run_once: bool = False,
    fail_fast: bool = False,
    env_profile: str = "dev",
    run_mode: str = "local",
    log_level: str = "INFO",
    repo_root: str | Path | None = None,
    workers: int | None = None,
    max_concurrency: int | None = None,
    poll_interval: float | None = None,
    interval_s: float | None = None,
    heartbeat: float | None = None,
    once: bool | None = None,
    profile: str | None = None,
    mode: str | None = None,
    queue_name: str | None = None,
    worker_kind: str | None = None,
    idle_exit_cycles: int | None = None,
    **_: Any,
) -> int:
    """Execute pending task records from data/tasks using lock-safe workers."""
    _configure_runtime_paths(repo_root)
    _ensure_logging(log_level)

    effective_concurrency = _to_int(
        max_concurrency if max_concurrency is not None else workers if workers is not None else concurrency,
        default=4,
        minimum=1,
    )
    effective_poll = _to_float(
        interval_s if interval_s is not None else poll_interval if poll_interval is not None else poll_interval_s,
        default=0.25,
        minimum=0.0,
    )
    effective_heartbeat = _to_float(
        heartbeat if heartbeat is not None else heartbeat_s,
        default=10.0,
        minimum=0.0,
    )
    effective_run_once = _to_bool(once if once is not None else run_once, default=False)
    effective_fail_fast = _to_bool(fail_fast, default=False)
    effective_queue = _normalize_selector(
        queue_name if queue_name is not None else queue
    )
    effective_kind = _normalize_selector(
        worker_kind if worker_kind is not None else kind
    )
    effective_profile = _safe_str(profile if profile is not None else env_profile).strip() or "dev"
    effective_mode = _safe_str(mode if mode is not None else run_mode).strip() or "local"
    effective_idle_exit = (
        _to_int(idle_exit_cycles, default=0, minimum=1) if idle_exit_cycles is not None else None
    )

    host = socket.gethostname()
    pid = os.getpid()
    worker_prefix = f"{effective_kind}@{host}:{pid}"

    logger.info(
        "workers started queue=%s kind=%s concurrency=%s poll_interval_s=%s heartbeat_s=%s run_once=%s "
        "profile=%s mode=%s tasks_dir=%s",
        effective_queue,
        effective_kind,
        effective_concurrency,
        effective_poll,
        effective_heartbeat,
        effective_run_once,
        effective_profile,
        effective_mode,
        agent_executor.tasks_dir(),
    )
    _emit_telemetry(
        "workers.started",
        queue=effective_queue,
        kind=effective_kind,
        concurrency=effective_concurrency,
        poll_interval_s=effective_poll,
        heartbeat_s=effective_heartbeat,
        run_once=effective_run_once,
        profile=effective_profile,
        mode=effective_mode,
    )

    dispatched_total = 0
    failure_total = 0
    idle_cycles = 0
    next_heartbeat_at = time.monotonic() + effective_heartbeat

    try:
        while True:
            outcomes = _dispatch_cycle(
                concurrency=effective_concurrency,
                worker_prefix=worker_prefix,
                queue=effective_queue,
                kind=effective_kind,
            )

            dispatched = len(outcomes)
            failures = sum(1 for item in outcomes if not item.ok)
            dispatched_total += dispatched
            failure_total += failures

            if outcomes:
                idle_cycles = 0
                for outcome in outcomes:
                    level = logging.INFO if outcome.ok else logging.WARNING
                    logger.log(
                        level,
                        "task done task_id=%s worker=%s status=%s duration_s=%.3f error=%s",
                        outcome.task_id,
                        outcome.worker_id,
                        outcome.status,
                        outcome.duration_s,
                        outcome.error or "",
                    )
            else:
                idle_cycles += 1

            now = time.monotonic()
            if now >= next_heartbeat_at:
                logger.info(
                    "workers heartbeat queue=%s kind=%s dispatched_total=%s failure_total=%s idle_cycles=%s",
                    effective_queue,
                    effective_kind,
                    dispatched_total,
                    failure_total,
                    idle_cycles,
                )
                _emit_telemetry(
                    "workers.heartbeat",
                    queue=effective_queue,
                    kind=effective_kind,
                    dispatched_total=dispatched_total,
                    failure_total=failure_total,
                    idle_cycles=idle_cycles,
                )
                next_heartbeat_at = now + effective_heartbeat

            if effective_fail_fast and failures > 0:
                logger.error("fail_fast triggered failures=%s", failures)
                _emit_telemetry(
                    "workers.stopped",
                    reason="fail_fast",
                    dispatched_total=dispatched_total,
                    failure_total=failure_total,
                )
                return 1

            if effective_run_once:
                _emit_telemetry(
                    "workers.stopped",
                    reason="run_once",
                    dispatched_total=dispatched_total,
                    failure_total=failure_total,
                )
                return 0 if failures == 0 else 1

            if effective_idle_exit is not None and idle_cycles >= effective_idle_exit:
                logger.info("idle exit reached idle_cycles=%s", idle_cycles)
                _emit_telemetry(
                    "workers.stopped",
                    reason="idle_exit",
                    idle_cycles=idle_cycles,
                    dispatched_total=dispatched_total,
                    failure_total=failure_total,
                )
                return 0 if failure_total == 0 else 1

            if dispatched == 0:
                time.sleep(effective_poll)
    except KeyboardInterrupt:
        logger.warning("workers interrupted")
        _emit_telemetry(
            "workers.stopped",
            reason="keyboard_interrupt",
            dispatched_total=dispatched_total,
            failure_total=failure_total,
        )
        return 0


def run(**kwargs: Any) -> int:
    return run_workers(**kwargs)


def main(**kwargs: Any) -> int:
    return run_workers(**kwargs)
