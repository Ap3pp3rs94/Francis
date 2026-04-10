"""
Francis 2.0 — Daemon Entrypoint (apps/daemon/main.py)

Design contract
---------------
1) Thin wrapper:
   - No business logic (no scheduling policy, no orchestration decisions).
   - Resolve and invoke the daemon runner inside `francis.daemon.runner`.

2) Deterministic & observable:
   - Configuration precedence: CLI > ENV > defaults.
   - Startup banner prints normalized config (safe) and runtime context.

3) Forward-minded:
   - Runner function name/signature may evolve; this launcher adapts safely:
       * Auto-detect common runner symbols (run_daemon, main, start, run)
       * Inspect signature and pass only accepted kwargs
       * Works whether runner is sync or async

Usage (examples)
----------------
From repo root:

  python apps/daemon/main.py
  python apps/daemon/main.py --tick 0.5 --concurrency 4
  python apps/daemon/main.py --once
  python apps/daemon/main.py --dry-run
  python apps/daemon/main.py --runner francis.daemon.runner:run_daemon

Environment variables (selected)
--------------------------------
Daemon toggles:
  FRANCIS_DAEMON_ENABLED=true|false
  FRANCIS_DAEMON_TICK_INTERVAL_S=1.0
  FRANCIS_DAEMON_MAX_CONCURRENCY=4
  FRANCIS_DAEMON_HEARTBEAT_S=10.0
  FRANCIS_DAEMON_FAIL_FAST=true|false
  FRANCIS_DAEMON_RUN_ONCE=true|false

Runtime context:
  FRANCIS_ENV_PROFILE=dev|production|...
  FRANCIS_RUN_MODE=local|edge|...
  FRANCIS_LOG_LEVEL=INFO|DEBUG|...

Notes
-----
- This file is intentionally dependency-light.
- If `francis.telemetry.logging` exposes a logging init function, we delegate to it.
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

_LOG = logging.getLogger("francis.apps.daemon")


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
    # Allow common aliases
    if s == "WARN":
        return "WARNING"
    if s == "FATAL":
        return "CRITICAL"
    return s


# -------------------------------------------------------------------------------------------------
# repo root (stable + low-cost)
# -------------------------------------------------------------------------------------------------


def _repo_root_from_here() -> Path:
    """
    apps/daemon/main.py -> repo root is two parents up.

    We intentionally avoid filesystem searching here to keep this entrypoint fast and deterministic.
    """
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
class DaemonConfig:
    """
    Normalized daemon runtime configuration for this entrypoint.

    This is *not* the daemon's full internal config. It's the launcher view.
    """

    enabled: bool
    tick_interval_s: float
    max_concurrency: int
    heartbeat_s: float
    fail_fast: bool
    run_once: bool

    env_profile: str
    run_mode: str
    log_level: str

    runner_target: str  # module:function

    def redacted_dict(self) -> Mapping[str, Any]:
        # No secrets expected here; keep the method for consistent logging style across apps.
        return dataclasses.asdict(self)


# -------------------------------------------------------------------------------------------------
# logging bootstrap + delegation
# -------------------------------------------------------------------------------------------------


def _basic_bootstrap_logging(level: str) -> None:
    """Minimal, dependency-free logging so we can explain failures clearly."""
    root = logging.getLogger()
    if root.handlers:
        return  # Respect parent runner config (tests, supervisor, etc.)

    lvl = getattr(logging, _normalize_log_level(level), logging.INFO)
    logging.basicConfig(
        level=lvl,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


def _try_delegate_to_francis_logging(level: str) -> None:
    """
    Try to hand off logging to the canonical Francis logging subsystem if present.

    We keep this best-effort and never fail startup due to logging delegation.
    """
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
                # Prefer keyword if accepted; otherwise call with no args.
                sig = None
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
    """
    Parse "module:attr" into (module, attr).
    """
    if not target or ":" not in target:
        raise ValueError(
            "Invalid runner target. Expected format 'module:callable' (e.g., 'francis.daemon.runner:run_daemon')."
        )
    mod, attr = target.split(":", 1)
    mod = mod.strip()
    attr = attr.strip()
    if not mod or not attr:
        raise ValueError("Invalid runner target: empty module or attribute.")
    return mod, attr


def _resolve_daemon_target(explicit: str | None) -> str:
    """
    Resolve the daemon runner callable target string.

    Order:
      1) Explicit (CLI/ENV)
      2) Common canonical entrypoints in francis.daemon.runner
    """
    if explicit:
        return explicit

    # Preferred canonical.
    return "francis.daemon.runner:run_daemon"


def _import_callable(target: str) -> Callable[..., Any]:
    mod_name, attr = _parse_target(target)
    mod = import_module(mod_name)
    fn = getattr(mod, attr, None)
    if not callable(fn):
        raise TypeError(f"Resolved target is not callable: {target}")
    return fn


def _filter_kwargs_for_callable(fn: Callable[..., Any], kwargs: Mapping[str, Any]) -> dict[str, Any]:
    """
    Return only kwargs that `fn` can accept.

    - If fn has **kwargs, pass everything.
    - Otherwise, pass only matching parameter names.
    """
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


def _runner_kwargs_from_config(cfg: DaemonConfig, repo_root: Path) -> dict[str, Any]:
    """
    Build a conservative kwargs bag for the runner.

    We provide multiple naming aliases to maximize compatibility as internals evolve.
    Only accepted kwargs will be forwarded.
    """
    # Canonical values
    tick = cfg.tick_interval_s
    conc = cfg.max_concurrency
    hb = cfg.heartbeat_s

    # Common aliases across codebases
    return {
        # primary
        "tick_interval_s": tick,
        "max_concurrency": conc,
        "heartbeat_s": hb,
        "fail_fast": cfg.fail_fast,
        "run_once": cfg.run_once,
        "env_profile": cfg.env_profile,
        "run_mode": cfg.run_mode,
        "log_level": cfg.log_level,
        "repo_root": str(repo_root),
        # aliases
        "tick_interval": tick,
        "interval_s": tick,
        "tick_s": tick,
        "concurrency": conc,
        "workers": conc,
        "heartbeat_interval_s": hb,
        "heartbeat": hb,
        "once": cfg.run_once,
        "profile": cfg.env_profile,
        "mode": cfg.run_mode,
    }


# -------------------------------------------------------------------------------------------------
# UX: banner + diagnostics
# -------------------------------------------------------------------------------------------------


def _get_francis_version() -> str:
    try:
        import francis  # type: ignore

        return str(getattr(francis, "__version__", "unknown"))
    except Exception:  # noqa: BLE001
        return "unknown"


def _startup_banner(cfg: DaemonConfig, repo_root: Path) -> None:
    _LOG.info("Francis daemon starting")
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
        prog="francis-daemon",
        description="Francis 2.0 daemon launcher (thin wrapper around francis.daemon.runner).",
    )

    p.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_francis_version()}",
        help="Show version and exit.",
    )

    # Behavior toggles
    p.add_argument(
        "--enabled",
        dest="enabled",
        action="store_true",
        help="Force daemon enabled (overrides FRANCIS_DAEMON_ENABLED).",
    )
    p.add_argument(
        "--disabled",
        dest="disabled",
        action="store_true",
        help="Force daemon disabled (overrides FRANCIS_DAEMON_ENABLED).",
    )
    p.add_argument(
        "--once",
        action="store_true",
        help="Run a single tick/cycle (if supported by runner) then exit.",
    )
    p.add_argument(
        "--fail-fast",
        action="store_true",
        help="Crash on first unrecoverable error (if supported by runner).",
    )

    # Timing/concurrency
    p.add_argument(
        "--tick",
        type=float,
        default=None,
        help="Tick interval in seconds (ENV: FRANCIS_DAEMON_TICK_INTERVAL_S).",
    )
    p.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Max concurrency/workers (ENV: FRANCIS_DAEMON_MAX_CONCURRENCY).",
    )
    p.add_argument(
        "--heartbeat",
        type=float,
        default=None,
        help="Heartbeat interval in seconds (ENV: FRANCIS_DAEMON_HEARTBEAT_S).",
    )

    # Context
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

    # Runner resolution
    p.add_argument(
        "--runner",
        type=str,
        default=None,
        help="Explicit runner target 'module:callable' (ENV: FRANCIS_DAEMON_RUNNER).",
    )

    # Operator tools
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved configuration and exit (no runner invocation).",
    )

    return p


def _validate_config(cfg: DaemonConfig) -> None:
    if cfg.tick_interval_s <= 0:
        raise ValueError(f"tick_interval_s must be > 0 (got {cfg.tick_interval_s})")
    if cfg.max_concurrency <= 0:
        raise ValueError(f"max_concurrency must be > 0 (got {cfg.max_concurrency})")
    if cfg.heartbeat_s <= 0:
        raise ValueError(f"heartbeat_s must be > 0 (got {cfg.heartbeat_s})")

    # Guard rails: extreme values usually indicate a mis-typed env.
    if cfg.tick_interval_s > 3600:
        _LOG.warning("tick_interval_s=%s is very high; check your config.", cfg.tick_interval_s)
    if cfg.heartbeat_s > 3600:
        _LOG.warning("heartbeat_s=%s is very high; check your config.", cfg.heartbeat_s)


def _resolve_config(argv: Sequence[str] | None) -> DaemonConfig:
    args = _build_arg_parser().parse_args(argv)

    # Bootstrap logging early.
    log_level = _normalize_log_level(args.log_level or _env("FRANCIS_LOG_LEVEL", "INFO") or "INFO")
    _basic_bootstrap_logging(log_level)

    # Delegate if possible (best-effort).
    _try_delegate_to_francis_logging(log_level)

    # Enabled precedence:
    # - CLI flags override env
    env_enabled = _env_bool("FRANCIS_DAEMON_ENABLED", True)
    enabled = env_enabled
    if args.enabled:
        enabled = True
    if args.disabled:
        enabled = False

    tick = args.tick if args.tick is not None else _env_float("FRANCIS_DAEMON_TICK_INTERVAL_S", 1.0, min_=0.01)
    conc = (
        args.concurrency
        if args.concurrency is not None
        else _env_int("FRANCIS_DAEMON_MAX_CONCURRENCY", 4, min_=1, max_=1024)
    )
    hb = args.heartbeat if args.heartbeat is not None else _env_float("FRANCIS_DAEMON_HEARTBEAT_S", 10.0, min_=0.1)

    # once/fail-fast:
    env_once = _env_bool("FRANCIS_DAEMON_RUN_ONCE", False)
    run_once = bool(args.once or env_once)

    env_fail_fast = _env_bool("FRANCIS_DAEMON_FAIL_FAST", False)
    fail_fast = bool(args.fail_fast or env_fail_fast)

    env_profile = args.profile if args.profile is not None else (_env("FRANCIS_ENV_PROFILE", "dev") or "dev")
    run_mode = args.run_mode if args.run_mode is not None else (_env("FRANCIS_RUN_MODE", "local") or "local")

    runner_explicit = args.runner if args.runner is not None else _env("FRANCIS_DAEMON_RUNNER", None)
    runner_target = _resolve_daemon_target(runner_explicit)

    cfg = DaemonConfig(
        enabled=enabled,
        tick_interval_s=float(tick),
        max_concurrency=int(conc),
        heartbeat_s=float(hb),
        fail_fast=fail_fast,
        run_once=run_once,
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
    Returns a process exit code.

    Exit codes:
      0 = success / clean exit
      2 = configuration error
      3 = import/target resolution error
      4 = runner failure
    """
    try:
        cfg = _resolve_config(argv)
    except SystemExit as e:
        # argparse or dry-run; honor requested code
        return int(e.code or 0)
    except Exception as exc:  # noqa: BLE001
        _basic_bootstrap_logging(_normalize_log_level(_env("FRANCIS_LOG_LEVEL", "INFO") or "INFO"))
        _LOG.error("Configuration error: %s", exc)
        _LOG.exception(exc)
        return 2

    repo_root = _repo_root_from_here()

    if not cfg.enabled:
        _startup_banner(cfg, repo_root)
        _LOG.warning("Daemon disabled (enabled=false). Exiting cleanly.")
        return 0

    _startup_banner(cfg, repo_root)

    try:
        _ensure_importable_francis()
    except Exception as exc:  # noqa: BLE001
        _LOG.error("Failed to import 'francis' package.")
        _LOG.exception(exc)
        return 3

    # Resolve runner callable
    targets_to_try = [cfg.runner_target]
    if cfg.runner_target == "francis.daemon.runner:run_daemon":
        targets_to_try.extend(
            [
                "francis.daemon.runner:main",
                "francis.daemon.runner:start_daemon",
                "francis.daemon.runner:start",
                "francis.daemon.runner:run",
            ]
        )

    fn: Callable[..., Any] | None = None
    last_import_err: Exception | None = None
    for target in targets_to_try:
        try:
            fn = _import_callable(target)
            if target != cfg.runner_target:
                _LOG.info(
                    "Runner fallback selected: %s (instead of %s)",
                    target,
                    cfg.runner_target,
                )
            break
        except Exception as exc:  # noqa: BLE001
            last_import_err = exc
            continue

    if fn is None:
        _LOG.error("Failed to resolve any daemon runner target.")
        if last_import_err:
            _LOG.exception(last_import_err)
        return 3

    # Prepare kwargs and call safely
    try:
        kwargs = _runner_kwargs_from_config(cfg, repo_root)
        filtered = _filter_kwargs_for_callable(fn, kwargs)

        _LOG.info("Invoking runner=%s with %d forwarded kwargs", cfg.runner_target, len(filtered))
        _LOG.debug("runner_kwargs=%s", filtered)

        result = asyncio.run(_maybe_await(fn(**filtered)))  # type: ignore[arg-type]
        if isinstance(result, int):
            return result
        return 0
    except KeyboardInterrupt:
        _LOG.warning("Interrupted (Ctrl+C). Exiting cleanly.")
        return 0
    except Exception as exc:  # noqa: BLE001
        _LOG.error("Daemon runner failed: %s", cfg.runner_target)
        _LOG.exception(exc)
        if cfg.fail_fast:
            return 4
        # If not fail-fast, still return non-zero; the supervisor should decide restarts.
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
