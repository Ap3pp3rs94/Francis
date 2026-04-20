from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

from francis.chat.continuity.ledger import append
from francis.telemetry.logging import log
from francis.workers.runner import run_workers

logger = logging.getLogger(__name__)

_TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "f", "no", "n", "off"}

__all__ = ["run_daemon", "run", "main"]


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
    if root.handlers:
        return
    logging.basicConfig(
        level=getattr(logging, _normalize_log_level(level), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


def _emit_log(event: str, level: str = "INFO", **fields: Any) -> None:
    try:
        log(event, level=level, **fields)
    except Exception:
        logger.debug("telemetry_write_failed event=%s", event, exc_info=True)


def _append_ledger(content: str, meta: dict[str, Any]) -> None:
    try:
        append("system", content, meta)
    except Exception:
        logger.debug("ledger_append_failed content=%s", content, exc_info=True)


def _configure_repo_root(repo_root: str | Path | None) -> None:
    if repo_root is None:
        return
    root = _safe_str(repo_root).strip()
    if root:
        os.environ["FRANCIS_ROOT"] = str(Path(root).resolve())


def _run_worker_cycle(
    *,
    max_concurrency: int,
    heartbeat_s: float,
    env_profile: str,
    run_mode: str,
    log_level: str,
    repo_root: str | Path | None,
    queue: str,
    kind: str,
    fail_fast: bool,
) -> int:
    return int(
        run_workers(
            concurrency=max_concurrency,
            heartbeat_s=heartbeat_s,
            run_once=True,
            fail_fast=fail_fast,
            env_profile=env_profile,
            run_mode=run_mode,
            log_level=log_level,
            repo_root=repo_root,
            queue=queue,
            kind=kind,
        )
    )


def run_daemon(
    *,
    tick_interval_s: float = 1.0,
    max_concurrency: int = 4,
    heartbeat_s: float = 10.0,
    fail_fast: bool = False,
    run_once: bool = False,
    env_profile: str = "dev",
    run_mode: str = "local",
    log_level: str = "INFO",
    repo_root: str | Path | None = None,
    tick_interval: float | None = None,
    interval_s: float | None = None,
    tick_s: float | None = None,
    concurrency: int | None = None,
    workers: int | None = None,
    heartbeat_interval_s: float | None = None,
    heartbeat: float | None = None,
    once: bool | None = None,
    profile: str | None = None,
    mode: str | None = None,
    queue: str = "default",
    kind: str = "default",
    queue_name: str | None = None,
    worker_kind: str | None = None,
    **_: Any,
) -> int:
    _configure_repo_root(repo_root)
    _ensure_logging(log_level)

    effective_tick = _to_float(
        tick_s
        if tick_s is not None
        else interval_s
        if interval_s is not None
        else tick_interval
        if tick_interval is not None
        else tick_interval_s,
        default=1.0,
        minimum=0.0,
    )
    effective_concurrency = _to_int(
        workers if workers is not None else concurrency if concurrency is not None else max_concurrency,
        default=4,
        minimum=1,
    )
    effective_heartbeat = _to_float(
        heartbeat
        if heartbeat is not None
        else heartbeat_interval_s
        if heartbeat_interval_s is not None
        else heartbeat_s,
        default=10.0,
        minimum=0.0,
    )
    effective_once = _to_bool(once if once is not None else run_once, default=False)
    effective_fail_fast = _to_bool(fail_fast, default=False)
    effective_profile = _safe_str(profile if profile is not None else env_profile).strip() or "dev"
    effective_mode = _safe_str(mode if mode is not None else run_mode).strip() or "local"
    effective_queue = _normalize_selector(queue_name if queue_name is not None else queue)
    effective_kind = _normalize_selector(worker_kind if worker_kind is not None else kind)

    logger.info(
        "daemon started tick_interval_s=%s max_concurrency=%s heartbeat_s=%s run_once=%s fail_fast=%s "
        "profile=%s mode=%s queue=%s kind=%s",
        effective_tick,
        effective_concurrency,
        effective_heartbeat,
        effective_once,
        effective_fail_fast,
        effective_profile,
        effective_mode,
        effective_queue,
        effective_kind,
    )
    _emit_log(
        "daemon.started",
        tick_interval_s=effective_tick,
        max_concurrency=effective_concurrency,
        heartbeat_s=effective_heartbeat,
        run_once=effective_once,
        fail_fast=effective_fail_fast,
        profile=effective_profile,
        run_mode=effective_mode,
        queue=effective_queue,
        kind=effective_kind,
    )
    _append_ledger(
        "daemon started",
        {
            "subsystem": "daemon",
            "profile": effective_profile,
            "run_mode": effective_mode,
            "queue": effective_queue,
            "kind": effective_kind,
        },
    )

    cycles = 0
    failures = 0
    last_heartbeat_at = 0.0

    try:
        while True:
            cycle_started = time.monotonic()
            cycles += 1

            exit_code = _run_worker_cycle(
                max_concurrency=effective_concurrency,
                heartbeat_s=effective_heartbeat,
                env_profile=effective_profile,
                run_mode=effective_mode,
                log_level=log_level,
                repo_root=repo_root,
                queue=effective_queue,
                kind=effective_kind,
                fail_fast=effective_fail_fast,
            )

            if exit_code != 0:
                failures += 1
                logger.warning("daemon cycle failed cycle=%s exit_code=%s", cycles, exit_code)
                _emit_log("daemon.cycle_failed", cycle=cycles, exit_code=exit_code, failures=failures)
                if effective_fail_fast:
                    _emit_log("daemon.stopped", reason="fail_fast", cycles=cycles, failures=failures)
                    return 1

            now = time.monotonic()
            if now - last_heartbeat_at >= effective_heartbeat:
                logger.info("daemon heartbeat cycles=%s failures=%s", cycles, failures)
                _emit_log("daemon.heartbeat", cycles=cycles, failures=failures)
                _append_ledger("heartbeat", {"subsystem": "daemon", "cycles": cycles, "failures": failures})
                last_heartbeat_at = now

            if effective_once:
                _emit_log("daemon.stopped", reason="run_once", cycles=cycles, failures=failures)
                return 0 if failures == 0 else 1

            elapsed = time.monotonic() - cycle_started
            sleep_for = effective_tick - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)
    except KeyboardInterrupt:
        logger.warning("daemon interrupted")
        _emit_log("daemon.stopped", reason="keyboard_interrupt", cycles=cycles, failures=failures)
        return 0


def run(**kwargs: Any) -> int:
    return run_daemon(**kwargs)


def main(**kwargs: Any) -> int:
    return run_daemon(**kwargs)
