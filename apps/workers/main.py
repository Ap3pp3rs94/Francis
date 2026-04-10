"""
Francis 2.0 — Workers Entrypoint (apps/workers/main.py)

Design contract
---------------
1) Thin wrapper:
   - No job logic, no scheduling policy, no business rules.
   - Resolve and invoke worker runner(s) inside `francis.workers.*` (or similar).

2) Deterministic & observable:
   - Config precedence: CLI > ENV > defaults.
   - Startup banner prints normalized configuration and runtime context.

3) Forward-minded:
   - Worker internals may change name/signature; this launcher adapts:
       * Resolves a runner target via CLI/ENV or auto-detection.
       * Inspects callable signature and forwards only accepted kwargs.
       * Supports sync or async run functions.

Usage (examples)
----------------
From repo root:

  python apps/workers/main.py
  python apps/workers/main.py --concurrency 8
  python apps/workers/main.py --once
  python apps/workers/main.py --queue default
  python apps/workers/main.py --runner francis.workers.runner:run_workers

Environment variables (selected)
--------------------------------
Worker toggles:
  FRANCIS_WORKERS_ENABLED=true|false
  FRANCIS_WORKERS_RUN_ONCE=true|false
  FRANCIS_WORKERS_FAIL_FAST=true|false

Concurrency / polling:
  FRANCIS_WORKERS_CONCURRENCY=4
  FRANCIS_WORKERS_POLL_INTERVAL_S=0.25
  FRANCIS_WORKERS_HEARTBEAT_S=10.0

Queue / routing (backend-defined):
  FRANCIS_WORKERS_QUEUE=default
  FRANCIS_WORKERS_KIND=default

Runtime context:
  FRANCIS_ENV_PROFILE=dev|production|...
  FRANCIS_RUN_MODE=local|edge|...
  FRANCIS_LOG_LEVEL=INFO|DEBUG|...

Runner override:
  FRANCIS_WORKERS_RUNNER=module:callable

Notes
-----
- Mutations, approvals, credential usage etc. must be enforced server-side.
- This file is a launcher only and is intentionally dependency-light.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import inspect
import logging
import os
import platform
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

_LOG = logging.getLogger("francis.apps.workers")


# -------------------------------------------------------------------------------------------------
# helpers: env parsing (defensive, deterministic)
# -------------------------------------------------------------------------------------------------


_TRUE = {"1", "true", "t", "yes", "y", "on", "enable", "enabled"}
_FALSE = {"0", "false", "f", "no", "n", "off", "disable", "disabled"}


def _env(key: str, default: str | None = None) -> str | None:
    v = os.getenv(key)
    if v is None:
        return default
    s = v.strip()
    return s if s != "" else default


def _env_bool(key: str, default: bool) -> bool:
    v = _env(key)
    if v is None:
        return default
    s = v.strip().lower()
    if s in _TRUE:
        return True
    if s in _FALSE:
        return False
    return default


def _env_int(key: str, default: int, *, min_: int | None = None, max_: int | None = None) -> int:
    v = _env(key)
    if v is None:
        return default
    try:
        n = int(v.strip())
    except ValueError:
        return default
    if min_ is not None and n < min_:
        return default
    if max_ is not None and n > max_:
        return default
    return n


def _env_float(
    key: str,
    default: float,
    *,
    min_: float | None = None,
    max_: float | None = None,
) -> float:
    v = _env(key)
    if v is None:
        return default
    try:
        n = float(v.strip())
    except ValueError:
        return default
    if min_ is not None and n < min_:
        return default
    if max_ is not None and n > max_:
        return default
    return n


def _normalize_log_level(level: str) -> str:
    s = (level or "").strip().upper()
    if not s:
        return "INFO"
    if s == "WARN":
        return "WARNING"
    if s == "FATAL":
        return "CRITICAL"
    return s


# -------------------------------------------------------------------------------------------------
# repo root
# -------------------------------------------------------------------------------------------------


def _repo_root_from_here() -> Path:
    """apps/workers/main.py -> repo root is two parents up."""
    return Path(__file__).resolve().parents[2]


def _ensure_importable_francis() -> None:
    """
    Ensure `import francis` works in a source checkout.

    If the package is not installed, prepend `<repo_root>/src` to `sys.path`.
    """
    try:
        import francis  # noqa: F401

        return
    except Exception:  # noqa: BLE001
        pass

    src_dir = _repo_root_from_here() / "src"
    if src_dir.is_dir():
        sys.path.insert(0, str(src_dir))

    import francis  # noqa: F401  # type: ignore[unused-ignore]


# -------------------------------------------------------------------------------------------------
# configuration model
# -------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WorkersConfig:
    """
    Normalized worker configuration for the launcher view.

    The internal worker engine may have a richer config; this entrypoint passes
    only safe, commonly-used parameters.
    """

    enabled: bool
    concurrency: int
    poll_interval_s: float
    heartbeat_s: float

    queue: str
    kind: str

    run_once: bool
    fail_fast: bool

    env_profile: str
    run_mode: str
    log_level: str

    runner_target: str  # module:function

    def redacted_dict(self) -> Mapping[str, Any]:
        return dataclasses.asdict(self)


# -------------------------------------------------------------------------------------------------
# logging bootstrap + delegation
# -------------------------------------------------------------------------------------------------


def _basic_bootstrap_logging(level: str) -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    lvl = getattr(logging, _normalize_log_level(level), logging.INFO)
    logging.basicConfig(
        level=lvl,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


def _try_delegate_to_francis_logging(level: str) -> None:
    candidates: tuple[tuple[str, str], ...] = (
        ("francis.telemetry.logging", "configure_logging"),
        ("francis.telemetry.logging", "setup_logging"),
        ("francis.telemetry.logging", "init_logging"),
        ("francis.telemetry.logging", "configure"),
    )
    for mod_name, fn_name in candidates:
        try:
            mod = import_module(mod_name)
            fn = getattr(mod, fn_name, None)
            if callable(fn):
                try:
                    sig = inspect.signature(fn)
                except (TypeError, ValueError):
                    sig = None
                if sig and "level" in sig.parameters:
                    fn(level=_normalize_log_level(level))
                else:
                    fn()
                _LOG.debug("Delegated logging to %s:%s", mod_name, fn_name)
                return
        except Exception:  # noqa: BLE001
            continue


# -------------------------------------------------------------------------------------------------
# runner resolution + invocation (forward-compatible)
# -------------------------------------------------------------------------------------------------


def _parse_target(target: str) -> tuple[str, str]:
    if not target or ":" not in target:
        raise ValueError(
            "Invalid runner target. Expected format 'module:callable' (e.g., 'francis.workers.runner:run_workers')."
        )
    mod, attr = target.split(":", 1)
    mod = mod.strip()
    attr = attr.strip()
    if not mod or not attr:
        raise ValueError("Invalid runner target: empty module or attribute.")
    return mod, attr


def _resolve_workers_target(explicit: str | None) -> str:
    """
    Resolve worker runner target.

    Preference order:
      1) Explicit (CLI/ENV)
      2) Try common internal locations
    """
    if explicit:
        return explicit

    # Canonical guesses; runner module/name may evolve.
    # We keep the first in the list as default, but will validate at import time.
    fallbacks = (
        "francis.workers.runner:run_workers",
        "francis.workers.runner:main",
        "francis.worker.runner:run_workers",
        "francis.worker.runner:main",
        "francis.workers:run",
        "francis.workers:main",
    )
    return fallbacks[0]


def _import_callable(target: str) -> Callable[..., Any]:
    mod_name, attr = _parse_target(target)
    mod = import_module(mod_name)
    fn = getattr(mod, attr, None)
    if not callable(fn):
        raise TypeError(f"Resolved target is not callable: {target}")
    return fn


def _filter_kwargs_for_callable(fn: Callable[..., Any], kwargs: Mapping[str, Any]) -> dict[str, Any]:
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return dict(kwargs)

    params = sig.parameters
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return dict(kwargs)

    accepted: dict[str, Any] = {}
    for k, v in kwargs.items():
        if k in params:
            accepted[k] = v
    return accepted


async def _maybe_await(v: Any) -> Any:
    if inspect.isawaitable(v):
        return await v
    return v


def _runner_kwargs_from_config(cfg: WorkersConfig, repo_root: Path) -> dict[str, Any]:
    """
    Provide a conservative, alias-rich kwargs bag.
    Only accepted kwargs will be forwarded.
    """
    return {
        # primary
        "concurrency": cfg.concurrency,
        "poll_interval_s": cfg.poll_interval_s,
        "heartbeat_s": cfg.heartbeat_s,
        "queue": cfg.queue,
        "kind": cfg.kind,
        "run_once": cfg.run_once,
        "fail_fast": cfg.fail_fast,
        "env_profile": cfg.env_profile,
        "run_mode": cfg.run_mode,
        "log_level": cfg.log_level,
        "repo_root": str(repo_root),
        # aliases
        "workers": cfg.concurrency,
        "max_concurrency": cfg.concurrency,
        "poll_interval": cfg.poll_interval_s,
        "interval_s": cfg.poll_interval_s,
        "heartbeat": cfg.heartbeat_s,
        "once": cfg.run_once,
        "profile": cfg.env_profile,
        "mode": cfg.run_mode,
        "queue_name": cfg.queue,
        "worker_kind": cfg.kind,
    }


# -------------------------------------------------------------------------------------------------
# UX: banner
# -------------------------------------------------------------------------------------------------


def _get_francis_version() -> str:
    try:
        import francis  # type: ignore

        return str(getattr(francis, "__version__", "unknown"))
    except Exception:  # noqa: BLE001
        return "unknown"


def _startup_banner(cfg: WorkersConfig, repo_root: Path) -> None:
    _LOG.info("Francis workers starting")
    _LOG.info("version=%s", _get_francis_version())
    _LOG.info("repo_root=%s", repo_root)
    _LOG.info("cwd=%s", Path.cwd())
    _LOG.info("pid=%s", os.getpid())
    _LOG.info(
        "python=%s (%s) platform=%s",
        sys.version.split()[0],
        sys.executable,
        platform.platform(),
    )
    _LOG.info("profile=%s run_mode=%s", cfg.env_profile, cfg.run_mode)
    for k, v in cfg.redacted_dict().items():
        _LOG.info("config.%s=%s", k, v)


# -------------------------------------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="francis-workers",
        description="Francis 2.0 workers launcher (thin wrapper around internal worker runner).",
    )

    p.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_francis_version()}",
        help="Show version and exit.",
    )

    p.add_argument(
        "--enabled",
        dest="enabled",
        action="store_true",
        help="Force workers enabled (overrides FRANCIS_WORKERS_ENABLED).",
    )
    p.add_argument(
        "--disabled",
        dest="disabled",
        action="store_true",
        help="Force workers disabled (overrides FRANCIS_WORKERS_ENABLED).",
    )
    p.add_argument(
        "--once",
        action="store_true",
        help="Run a single poll/dispatch cycle (if supported by runner) then exit.",
    )
    p.add_argument(
        "--fail-fast",
        action="store_true",
        help="Crash on first unrecoverable error (if supported by runner).",
    )

    p.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Max worker concurrency (ENV: FRANCIS_WORKERS_CONCURRENCY).",
    )
    p.add_argument(
        "--poll",
        type=float,
        default=None,
        help="Poll interval seconds (ENV: FRANCIS_WORKERS_POLL_INTERVAL_S).",
    )
    p.add_argument(
        "--heartbeat",
        type=float,
        default=None,
        help="Heartbeat interval seconds (ENV: FRANCIS_WORKERS_HEARTBEAT_S).",
    )

    p.add_argument(
        "--queue",
        type=str,
        default=None,
        help="Queue name / routing key (ENV: FRANCIS_WORKERS_QUEUE).",
    )
    p.add_argument(
        "--kind",
        type=str,
        default=None,
        help="Worker kind (ENV: FRANCIS_WORKERS_KIND).",
    )

    p.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Environment profile (ENV: FRANCIS_ENV_PROFILE).",
    )
    p.add_argument(
        "--run-mode",
        type=str,
        default=None,
        help="Run mode (ENV: FRANCIS_RUN_MODE).",
    )
    p.add_argument(
        "--log-level",
        type=str,
        default=None,
        help="Bootstrap log level (ENV: FRANCIS_LOG_LEVEL).",
    )

    p.add_argument(
        "--runner",
        type=str,
        default=None,
        help="Explicit runner target 'module:callable' (ENV: FRANCIS_WORKERS_RUNNER).",
    )

    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved configuration and exit (no runner invocation).",
    )

    return p


def _validate_config(cfg: WorkersConfig) -> None:
    if cfg.concurrency <= 0:
        raise ValueError(f"concurrency must be > 0 (got {cfg.concurrency})")
    if cfg.poll_interval_s <= 0:
        raise ValueError(f"poll_interval_s must be > 0 (got {cfg.poll_interval_s})")
    if cfg.heartbeat_s <= 0:
        raise ValueError(f"heartbeat_s must be > 0 (got {cfg.heartbeat_s})")

    if cfg.poll_interval_s > 60:
        _LOG.warning("poll_interval_s=%s is unusually high; check config.", cfg.poll_interval_s)
    if cfg.concurrency > 256:
        _LOG.warning("concurrency=%s is unusually high; check config.", cfg.concurrency)


def _resolve_config(argv: Sequence[str] | None) -> WorkersConfig:
    args = _build_arg_parser().parse_args(argv)

    log_level = _normalize_log_level(args.log_level or _env("FRANCIS_LOG_LEVEL", "INFO") or "INFO")
    _basic_bootstrap_logging(log_level)
    _try_delegate_to_francis_logging(log_level)

    env_enabled = _env_bool("FRANCIS_WORKERS_ENABLED", True)
    enabled = env_enabled
    if args.enabled:
        enabled = True
    if args.disabled:
        enabled = False

    conc = (
        args.concurrency
        if args.concurrency is not None
        else _env_int("FRANCIS_WORKERS_CONCURRENCY", 4, min_=1, max_=1024)
    )
    poll = (
        args.poll
        if args.poll is not None
        else _env_float("FRANCIS_WORKERS_POLL_INTERVAL_S", 0.25, min_=0.01, max_=60.0)
    )
    hb = (
        args.heartbeat
        if args.heartbeat is not None
        else _env_float("FRANCIS_WORKERS_HEARTBEAT_S", 10.0, min_=0.1, max_=3600.0)
    )

    env_once = _env_bool("FRANCIS_WORKERS_RUN_ONCE", False)
    run_once = bool(args.once or env_once)

    env_fail_fast = _env_bool("FRANCIS_WORKERS_FAIL_FAST", False)
    fail_fast = bool(args.fail_fast or env_fail_fast)

    queue = args.queue if args.queue is not None else (_env("FRANCIS_WORKERS_QUEUE", "default") or "default")
    kind = args.kind if args.kind is not None else (_env("FRANCIS_WORKERS_KIND", "default") or "default")

    env_profile = args.profile if args.profile is not None else (_env("FRANCIS_ENV_PROFILE", "dev") or "dev")
    run_mode = args.run_mode if args.run_mode is not None else (_env("FRANCIS_RUN_MODE", "local") or "local")

    runner_explicit = args.runner if args.runner is not None else _env("FRANCIS_WORKERS_RUNNER", None)
    runner_target = _resolve_workers_target(runner_explicit)

    cfg = WorkersConfig(
        enabled=enabled,
        concurrency=int(conc),
        poll_interval_s=float(poll),
        heartbeat_s=float(hb),
        queue=str(queue),
        kind=str(kind),
        run_once=run_once,
        fail_fast=fail_fast,
        env_profile=str(env_profile),
        run_mode=str(run_mode),
        log_level=log_level,
        runner_target=runner_target,
    )

    _validate_config(cfg)

    if args.dry_run:
        repo_root = _repo_root_from_here()
        _startup_banner(cfg, repo_root)
        _LOG.info("dry_run=true (exiting without invoking runner)")
        raise SystemExit(0)

    return cfg


# -------------------------------------------------------------------------------------------------
# main
# -------------------------------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    """
    Exit codes:
      0 = success / clean exit
      2 = configuration error
      3 = runner resolution/import error
      4 = runner failure
    """
    try:
        cfg = _resolve_config(argv)
    except SystemExit as e:
        return int(e.code or 0)
    except Exception as exc:  # noqa: BLE001
        _basic_bootstrap_logging(_normalize_log_level(_env("FRANCIS_LOG_LEVEL", "INFO") or "INFO"))
        _LOG.error("Configuration error: %s", exc)
        _LOG.exception(exc)
        return 2

    repo_root = _repo_root_from_here()

    if not cfg.enabled:
        _startup_banner(cfg, repo_root)
        _LOG.warning("Workers disabled (enabled=false). Exiting cleanly.")
        return 0

    _startup_banner(cfg, repo_root)

    try:
        _ensure_importable_francis()
    except Exception as exc:  # noqa: BLE001
        _LOG.error("Failed to import 'francis' package.")
        _LOG.exception(exc)
        return 3

    # Resolve runner callable
    # We try a small list of fallbacks if the default target doesn't import.
    targets_to_try = [cfg.runner_target]
    if cfg.runner_target == "francis.workers.runner:run_workers":
        targets_to_try.extend(
            [
                "francis.workers.runner:main",
                "francis.worker.runner:run_workers",
                "francis.worker.runner:main",
                "francis.workers:run",
                "francis.workers:main",
            ]
        )

    fn: Callable[..., Any] | None = None
    last_import_err: Exception | None = None
    for t in targets_to_try:
        try:
            fn = _import_callable(t)
            if t != cfg.runner_target:
                _LOG.info("Runner fallback selected: %s (instead of %s)", t, cfg.runner_target)
            break
        except Exception as exc:  # noqa: BLE001
            last_import_err = exc
            continue

    if fn is None:
        _LOG.error("Failed to resolve any worker runner target.")
        if last_import_err:
            _LOG.exception(last_import_err)
        return 3

    # Invoke runner safely
    try:
        kwargs = _runner_kwargs_from_config(cfg, repo_root)
        filtered = _filter_kwargs_for_callable(fn, kwargs)

        _LOG.info("Invoking workers runner with %d forwarded kwargs", len(filtered))
        _LOG.debug("runner_kwargs=%s", filtered)

        result = asyncio.run(_maybe_await(fn(**filtered)))  # type: ignore[arg-type]
        if isinstance(result, int):
            return result
        return 0
    except KeyboardInterrupt:
        _LOG.warning("Interrupted (Ctrl+C). Exiting cleanly.")
        return 0
    except Exception as exc:  # noqa: BLE001
        _LOG.error("Workers runner failed")
        _LOG.exception(exc)
        return 4 if cfg.fail_fast else 4


if __name__ == "__main__":
    raise SystemExit(main())
