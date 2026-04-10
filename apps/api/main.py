"""
Francis API service entrypoint.

This module is the thin operational wrapper for running the Francis ASGI API service.
It is deliberately *not* where the API is defined.

Canonical API implementation:
    - src/francis/api/app.py  -> "francis.api.app" (app factory / FastAPI instance)

Design contract
---------------
1) Keep this file thin:
   - No route wiring
   - No business logic
   - No side-effectful imports beyond bootstrap + app resolution

2) Deterministic & observable:
   - Early validation of bind configuration
   - Clear logging on startup and fatal failures
   - Exit codes that mean something

3) Forward-minded:
   - Supports dev reload without breaking production worker models
   - Supports reverse-proxy deployments (proxy headers, root path)
   - Allows overriding the ASGI import target for advanced deployments

Operational usage
-----------------
From repo root (recommended):
    python apps/api/main.py

Typical dev:
    python apps/api/main.py --reload

Production-like:
    python apps/api/main.py --host 0.0.0.0 --port 8080 --workers 2

Environment variables (subset; runner-level only)
-------------------------------------------------
These are intentionally limited to "server wrapper" controls.
App behavior/configuration should be owned by francis.settings / config YAML.

    FRANCIS_API_HOST                 default: 127.0.0.1
    FRANCIS_API_PORT                 default: 8000
    FRANCIS_API_RELOAD               default: false
    FRANCIS_API_WORKERS              default: 1
    FRANCIS_API_LOG_LEVEL            default: INFO (fallback to FRANCIS_LOG_LEVEL)
    FRANCIS_API_ACCESS_LOG           default: true
    FRANCIS_API_PROXY_HEADERS        default: false
    FRANCIS_API_FORWARDED_ALLOW_IPS  default: 127.0.0.1,::1
    FRANCIS_API_ROOT_PATH            default: ""
    FRANCIS_API_APP                  default: auto-detected
        - auto chooses:
            - francis.api.app:create_app (factory=True) if available, else
            - francis.api.app:app        (factory=False)

Notes
-----
- If you are using a venv and see import issues, ensure you're invoking the correct Python:
    .\\.venv\\Scripts\\python.exe apps\\api\\main.py
"""

from __future__ import annotations

import argparse
import importlib
import logging
import os
import platform
import sys

# Python 3.11+ stdlib TOML parser (aligned with repo's pinned modern interpreter).
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

# -----------------------------------------------------------------------------
# Logging (bootstrap-friendly)
# -----------------------------------------------------------------------------

_LOG = logging.getLogger("francis.apps.api")


def _basic_bootstrap_logging(level: str) -> None:
    """Minimal, dependency-free logging for the entrypoint.

    If the main Francis logging system is available, we delegate to it later.
    This bootstrap logger ensures we can always emit meaningful diagnostics.
    """
    root = logging.getLogger()
    if root.handlers:
        # Respect any logging that a parent runner already configured.
        return

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def _try_delegate_to_francis_logging(level: str) -> None:
    """Attempt to hand off to the project's logging subsystem if present.

    We intentionally do this *after* bootstrap logging so failures are visible.
    This function is defensive: if telemetry logging is not ready yet, we keep
    bootstrap logging and continue.
    """
    try:
        from francis.telemetry import logging as telemetry_logging  # type: ignore
    except Exception:  # noqa: BLE001 - best-effort delegation only
        return

    # Common initializer names (bootstrap may change over time).
    candidates: tuple[str, ...] = (
        "configure_logging",
        "setup_logging",
        "init_logging",
        "initialize_logging",
        "configure",
        "setup",
    )

    for name in candidates:
        fn = getattr(telemetry_logging, name, None)
        if callable(fn):
            try:
                # Prefer keyword usage if supported; fall back to positional.
                fn(level=level)  # type: ignore[misc]
            except TypeError:
                fn(level)  # type: ignore[misc]
            except Exception:  # noqa: BLE001 - logging must never prevent start
                return
            return


# -----------------------------------------------------------------------------
# Environment parsing utilities
# -----------------------------------------------------------------------------

_TRUE = {"1", "true", "yes", "y", "on"}
_FALSE = {"0", "false", "no", "n", "off"}


def _env_str(name: str, default: str) -> str:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip()
    return v if v else default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip(), 10)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    val = raw.strip().lower()
    if val in _TRUE:
        return True
    if val in _FALSE:
        return False
    # Unknown -> default (explicit is better than surprising)
    return default


# -----------------------------------------------------------------------------
# Repo root + version utilities
# -----------------------------------------------------------------------------


def _repo_root_from_here() -> Path:
    """Best-effort repository root resolution.

    We prefer a resilient upward search for `pyproject.toml` or `.git`, then fall
    back to the known layout (apps/api/main.py -> repo root is two parents up).

    This keeps the entrypoint stable if invoked from different working directories.
    """
    start = Path(__file__).resolve().parent
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file() or (candidate / ".git").exists():
            return candidate

    # Fallback: known bootstrap layout
    return Path(__file__).resolve().parents[2]


def _read_pyproject_version(pyproject_path: Path) -> str | None:
    """Extract a version string from pyproject.toml when available.

    Supports both PEP 621 ([project]) and Poetry ([tool.poetry]) styles.
    """
    if not pyproject_path.is_file():
        return None
    try:
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - version probe must never crash runner
        return None

    project = data.get("project")
    if isinstance(project, dict):
        v = project.get("version")
        if isinstance(v, str) and v.strip():
            return v.strip()

    tool = data.get("tool")
    if isinstance(tool, dict):
        poetry = tool.get("poetry")
        if isinstance(poetry, dict):
            v = poetry.get("version")
            if isinstance(v, str) and v.strip():
                return v.strip()

    return None


def _get_francis_version() -> str:
    """Resolve the Francis version for CLI display (best-effort, zero secrets).

    Priority:
      1) pyproject.toml version (works in editable/source checkouts)
      2) installed distribution metadata (works in packaged installs)
      3) francis.__version__ if present (best-effort)
      4) "unknown"
    """
    repo_root = _repo_root_from_here()
    v = _read_pyproject_version(repo_root / "pyproject.toml")
    if v:
        return v

    # Distribution metadata (if installed)
    try:
        return importlib_metadata.version("francis")
    except importlib_metadata.PackageNotFoundError:
        pass
    except Exception:  # noqa: BLE001
        pass

    # Fallback to attribute if defined
    try:
        import francis  # type: ignore

        candidate = getattr(francis, "__version__", None)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    except Exception:  # noqa: BLE001
        pass

    return "unknown"


def _ensure_importable_francis() -> None:
    """Ensure `import francis` works when running from a fresh repo checkout.

    If the package is installed (editable or regular), this is a no-op.
    If not installed, but a ./src directory exists with the package, we insert it.

    This is a convenience for local running and does not affect installed usage.
    """
    try:
        import francis  # noqa: F401

        return
    except Exception:  # noqa: BLE001
        pass

    repo_root = _repo_root_from_here()
    src_dir = repo_root / "src"
    if src_dir.is_dir():
        sys.path.insert(0, str(src_dir))

    # Retry import; if this fails, let it raise naturally in main().
    import francis  # noqa: F401  # type: ignore[unused-ignore]


# -----------------------------------------------------------------------------
# App / server configuration
# -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ApiServerConfig:
    """Normalized configuration for the Uvicorn server wrapper."""

    host: str
    port: int

    reload: bool
    workers: int

    log_level: str
    access_log: bool

    proxy_headers: bool
    forwarded_allow_ips: str
    root_path: str

    # ASGI target resolution
    app_import: str
    app_factory: bool

    # Uvicorn tunables (keep conservative; let app own the rest)
    timeout_keep_alive_s: int

    def redacted_dict(self) -> Mapping[str, Any]:
        """Return a safe representation suitable for logs (no secrets here)."""
        return {
            "host": self.host,
            "port": self.port,
            "reload": self.reload,
            "workers": self.workers,
            "log_level": self.log_level,
            "access_log": self.access_log,
            "proxy_headers": self.proxy_headers,
            "forwarded_allow_ips": self.forwarded_allow_ips,
            "root_path": self.root_path,
            "app_import": self.app_import,
            "app_factory": self.app_factory,
            "timeout_keep_alive_s": self.timeout_keep_alive_s,
        }


def _resolve_api_app_target(explicit: str | None) -> tuple[str, bool]:
    """Resolve the ASGI import target for Uvicorn.

    Returns:
        (import_string, factory_flag)

    Behavior:
      - If explicit is provided, use it as-is.
        * If it endswith ':create_app' or ':factory', set factory=True by heuristic.
        * Otherwise factory=False unless user explicitly uses --factory.
      - If not explicit:
        * Prefer `francis.api.app:create_app` when present and callable.
        * Else fall back to `francis.api.app:app`.
    """
    if explicit:
        # Heuristic: common patterns for factory endpoints.
        if explicit.endswith(":create_app") or explicit.endswith(":factory"):
            return explicit, True
        return explicit, False

    module_name = "francis.api.app"
    try:
        mod = importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Unable to import {module_name!r}. The Francis API package is not importable.") from exc

    create_app = getattr(mod, "create_app", None)
    if callable(create_app):
        return f"{module_name}:create_app", True

    app_obj = getattr(mod, "app", None)
    if app_obj is not None:
        return f"{module_name}:app", False

    # Future-proof: allow other common names without forcing a redesign.
    for alt in ("get_app", "build_app", "make_app"):
        fn = getattr(mod, alt, None)
        if callable(fn):
            return f"{module_name}:{alt}", True

    raise RuntimeError(f"{module_name!r} does not define an ASGI target. Expected create_app() or app.")


def _normalize_config(args: argparse.Namespace) -> ApiServerConfig:
    """Compute a validated, normalized server config from env + CLI args."""
    env_log_level = _env_str("FRANCIS_API_LOG_LEVEL", _env_str("FRANCIS_LOG_LEVEL", "INFO"))
    env_host = _env_str("FRANCIS_API_HOST", "127.0.0.1")
    env_port = _env_int("FRANCIS_API_PORT", 8000)
    env_reload = _env_bool("FRANCIS_API_RELOAD", False)
    env_workers = _env_int("FRANCIS_API_WORKERS", 1)
    env_access_log = _env_bool("FRANCIS_API_ACCESS_LOG", True)
    env_proxy_headers = _env_bool("FRANCIS_API_PROXY_HEADERS", False)
    env_forwarded_allow_ips = _env_str("FRANCIS_API_FORWARDED_ALLOW_IPS", "127.0.0.1,::1")
    env_root_path = _env_str("FRANCIS_API_ROOT_PATH", "")
    env_timeout_keep_alive = _env_int("FRANCIS_API_TIMEOUT_KEEP_ALIVE_S", 5)
    env_app_import = os.getenv("FRANCIS_API_APP")

    host = args.host if args.host is not None else env_host
    port = args.port if args.port is not None else env_port
    reload_ = bool(args.reload) if args.reload is not None else env_reload
    workers = args.workers if args.workers is not None else env_workers
    log_level = (args.log_level if args.log_level is not None else env_log_level).upper()
    access_log = args.access_log if args.access_log is not None else env_access_log
    proxy_headers = args.proxy_headers if args.proxy_headers is not None else env_proxy_headers
    forwarded_allow_ips = args.forwarded_allow_ips if args.forwarded_allow_ips is not None else env_forwarded_allow_ips
    root_path = args.root_path if args.root_path is not None else env_root_path
    timeout_keep_alive_s = (
        args.timeout_keep_alive_s if args.timeout_keep_alive_s is not None else env_timeout_keep_alive
    )

    # ASGI target: explicit CLI overrides env.
    explicit_app = args.app if args.app is not None else env_app_import
    app_import, inferred_factory = _resolve_api_app_target(explicit_app)

    # User may explicitly set --factory; otherwise use inferred behavior.
    app_factory = bool(args.factory) if args.factory is not None else inferred_factory

    # Validation / normalization:
    if not isinstance(port, int) or port <= 0 or port > 65535:
        raise ValueError(f"Invalid port: {port}. Must be in 1..65535")

    if workers < 1:
        raise ValueError(f"Invalid workers: {workers}. Must be >= 1")

    if timeout_keep_alive_s < 0:
        raise ValueError(f"Invalid timeout_keep_alive_s: {timeout_keep_alive_s}. Must be >= 0")

    # Reload and multi-worker are mutually exclusive (Uvicorn constraint).
    if reload_ and workers != 1:
        _LOG.warning("Reload enabled; forcing workers=1 (was %s)", workers)
        workers = 1

    # Root path should be empty or start with "/" (common reverse-proxy requirement).
    if root_path and not root_path.startswith("/"):
        _LOG.warning(
            "root_path %r does not start with '/'; normalizing to '/%s'",
            root_path,
            root_path,
        )
        root_path = f"/{root_path}"

    return ApiServerConfig(
        host=host,
        port=port,
        reload=reload_,
        workers=workers,
        log_level=log_level,
        access_log=access_log,
        proxy_headers=proxy_headers,
        forwarded_allow_ips=forwarded_allow_ips,
        root_path=root_path,
        app_import=app_import,
        app_factory=app_factory,
        timeout_keep_alive_s=timeout_keep_alive_s,
    )


# -----------------------------------------------------------------------------
# CLI parsing
# -----------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="francis-api",
        description="Run the Francis API service (Uvicorn wrapper).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    p.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_francis_version()}",
        help="Show version and exit.",
    )

    # Bind / server
    p.add_argument("--host", type=str, default=None, help="Bind host (IP/interface).")
    p.add_argument("--port", type=int, default=None, help="Bind port.")
    p.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable auto-reload (development only).",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of worker processes (ignored when reload is enabled).",
    )

    # Logging
    p.add_argument(
        "--log-level",
        type=str,
        default=None,
        help="Uvicorn log level (DEBUG/INFO/WARNING/ERROR/CRITICAL).",
    )
    p.add_argument(
        "--access-log",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable access logs.",
    )

    # Reverse proxy support
    p.add_argument(
        "--proxy-headers",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Trust X-Forwarded-* headers (only behind a trusted proxy).",
    )
    p.add_argument(
        "--forwarded-allow-ips",
        type=str,
        default=None,
        help="Comma-separated list of trusted proxy IPs for forwarded headers.",
    )
    p.add_argument(
        "--root-path",
        type=str,
        default=None,
        help="ASGI root_path (for mounting behind a reverse proxy subpath).",
    )

    # ASGI target
    p.add_argument(
        "--app",
        type=str,
        default=None,
        help=("ASGI import string. Examples: 'francis.api.app:app' or 'francis.api.app:create_app'"),
    )
    p.add_argument(
        "--factory",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Treat --app as a factory function returning an ASGI app.",
    )

    # Keep-alive / connection behavior
    p.add_argument(
        "--timeout-keep-alive-s",
        type=int,
        default=None,
        help="Keep-alive timeout in seconds (0 disables).",
    )

    # Utilities
    p.add_argument(
        "--check",
        action="store_true",
        help="Validate configuration and import target, then exit 0.",
    )

    return p


# -----------------------------------------------------------------------------
# Runner
# -----------------------------------------------------------------------------


def _startup_banner(cfg: ApiServerConfig) -> None:
    """Emit a compact, non-secret startup banner."""
    repo_root = _repo_root_from_here()
    env_profile = os.getenv("FRANCIS_ENV_PROFILE", "").strip() or "default"
    run_mode = os.getenv("FRANCIS_RUN_MODE", "").strip() or "api"

    _LOG.info("Francis API starting")
    _LOG.info("version=%s", _get_francis_version())
    _LOG.info("repo_root=%s", repo_root)
    _LOG.info("env_profile=%s run_mode=%s", env_profile, run_mode)
    _LOG.info(
        "python=%s (%s) platform=%s",
        sys.version.split()[0],
        sys.executable,
        platform.platform(),
    )

    # Safe config dump (no secrets).
    for k, v in cfg.redacted_dict().items():
        _LOG.info("config.%s=%s", k, v)

    # Friendly URL hint
    base_url = f"http://{cfg.host}:{cfg.port}{cfg.root_path or ''}"
    _LOG.info("listening=%s", base_url)


def _run_uvicorn(cfg: ApiServerConfig) -> None:
    """Run the Uvicorn server with a resolved ASGI target."""
    try:
        import uvicorn  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "uvicorn is not installed. Install server dependencies for the API "
            "(e.g., `pip install uvicorn` or `pip install 'fastapi[standard]'`)."
        ) from exc

    # NOTE:
    # - When reload/workers are enabled, Uvicorn will import the target in child processes.
    # - Using an import string is therefore the safest universal approach.
    uvicorn.run(
        cfg.app_import,
        factory=cfg.app_factory,
        host=cfg.host,
        port=cfg.port,
        reload=cfg.reload,
        workers=cfg.workers,
        log_level=cfg.log_level.lower(),
        access_log=cfg.access_log,
        proxy_headers=cfg.proxy_headers,
        forwarded_allow_ips=cfg.forwarded_allow_ips,
        root_path=cfg.root_path,
        timeout_keep_alive=cfg.timeout_keep_alive_s,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint.

    Returns:
        Process exit code.
    """
    argv = list(sys.argv[1:] if argv is None else argv)

    # Bootstrap logging as early as possible.
    bootstrap_level = _env_str(
        "FRANCIS_API_LOG_LEVEL",
        _env_str("FRANCIS_LOG_LEVEL", "INFO"),
    )
    _basic_bootstrap_logging(bootstrap_level)

    # Parse args early so --help/--version work even if imports are broken.
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    # Ensure the package is importable when running from source.
    try:
        _ensure_importable_francis()
    except Exception as exc:  # noqa: BLE001
        _LOG.error("Failed to import 'francis' package. Are you in the repo root?")
        _LOG.exception(exc)
        return 2

    # Now that francis is importable, attempt to delegate to the canonical logging system.
    _try_delegate_to_francis_logging(bootstrap_level)

    try:
        cfg = _normalize_config(args)
    except Exception as exc:  # noqa: BLE001
        _LOG.error("Configuration error: %s", exc)
        return 2

    _startup_banner(cfg)

    if args.check:
        _LOG.info("--check: configuration valid and app target resolvable; exiting 0")
        return 0

    try:
        _run_uvicorn(cfg)
        return 0
    except KeyboardInterrupt:
        _LOG.info("Shutdown requested (KeyboardInterrupt)")
        return 0
    except Exception as exc:  # noqa: BLE001
        _LOG.error("Fatal error while running API server: %s", exc)
        _LOG.exception(exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
