"""
Francis import smoke tests.

Why this exists
---------------
Import failures are the fastest way for production to go sideways:

- missing dependency in the lock/build environment
- accidental circular import
- module-level execution that assumes configuration exists
- syntax error in a module not exercised by unit tests

This file is intended to be used by:
  - pre-push hook: "pytest -q tests/unit/test_imports.py"

Design principles
-----------------
1) Default mode must be fast and deterministic:
   - No network calls
   - No daemon loops
   - No filesystem writes
   - No reliance on secrets

2) Core modules are REQUIRED:
   - If a core module cannot import, that is a hard failure.

3) Optional modules are OPTIONAL:
   - We skip optional modules only when the failure is clearly caused by a missing
     external dependency (e.g., "openai", "qdrant_client", "psycopg").
   - If an optional module fails for any other reason (syntax error, internal
     missing module, runtime exception), we still fail.

Opt-in knobs
------------
Set environment variables when you want more coverage:

  FRANCIS_IMPORT_SMOKE_OPTIONAL=1
    Also attempts imports for optional integrations/backends.

  FRANCIS_IMPORT_SMOKE_DEEP=1
    Enables deeper, still-safe checks (e.g., create_app() if present).

These are off by default to preserve developer cadence.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import os
import sys
import textwrap
import traceback
from typing import Sequence

import pytest


# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------

_TRUE = {"1", "true", "yes", "y", "on"}


def _truthy_env(name: str, *, default: bool = False) -> bool:
    """Parse a boolean feature toggle from environment variables.

    Accepts common truthy strings. Any other non-empty value is treated as false
    (explicit is better than surprising).
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE


RUN_OPTIONAL = _truthy_env("FRANCIS_IMPORT_SMOKE_OPTIONAL", default=False)
RUN_DEEP = _truthy_env("FRANCIS_IMPORT_SMOKE_DEEP", default=False)


@dataclass(frozen=True, slots=True)
class ImportTarget:
    """A single import target for smoke validation."""

    module: str
    optional: bool = False
    reason: str = ""


# Core imports: these should ALWAYS work in any valid installation.
#
# Keep this list tight and high-signal:
# - entrypoints
# - settings
# - api/daemon shell modules
# - kernel/telemetry basics
CORE_TARGETS: tuple[ImportTarget, ...] = (
    ImportTarget("francis", reason="Top-level package"),
    ImportTarget("francis.__main__", reason="python -m francis entrypoint"),
    ImportTarget("francis.cli", reason="CLI entrypoint (api/daemon commands)"),
    ImportTarget("francis.settings", reason="Settings/config loader"),
    ImportTarget("francis.telemetry.logging", reason="Logging subsystem"),
    ImportTarget("francis.telemetry.audit", reason="Audit telemetry subsystem"),
    ImportTarget("francis.telemetry.metrics", reason="Metrics telemetry subsystem"),
    ImportTarget("francis.telemetry.tracing", reason="Trace context subsystem"),
    ImportTarget("francis.trust.calculator", reason="Trust decision subsystem"),
    ImportTarget("francis.trust.tracker", reason="Trust persistence subsystem"),
    ImportTarget("francis.trust.boundaries", reason="Authority boundary subsystem"),
    ImportTarget("francis.kernel.health", reason="Kernel health reporting"),
    ImportTarget("francis.world_state.orb", reason="ORB status snapshot"),
    ImportTarget("francis.world_state.snapshot", reason="World state snapshot"),
    ImportTarget("francis.api.app", reason="API app factory/definition"),
    ImportTarget("francis.daemon.runner", reason="Daemon runner (entry module)"),
)

# Optional imports: these may require extras that are not installed in a minimal dev env.
# They are only attempted when FRANCIS_IMPORT_SMOKE_OPTIONAL=1.
OPTIONAL_TARGETS: tuple[ImportTarget, ...] = (
    ImportTarget(
        "francis.llm.providers.openai_provider",
        optional=True,
        reason="Optional OpenAI provider (requires openai client dependency)",
    ),
    ImportTarget(
        "francis.memory.vectorstores.qdrant_store",
        optional=True,
        reason="Optional Qdrant vector store backend",
    ),
    ImportTarget(
        "francis.memory.vectorstores.pgvector_store",
        optional=True,
        reason="Optional PGVector/Postgres vector store backend",
    ),
)


def _iter_targets() -> Sequence[ImportTarget]:
    """Return the ordered list of import targets for this run."""
    if RUN_OPTIONAL:
        return (*CORE_TARGETS, *OPTIONAL_TARGETS)
    return CORE_TARGETS


# ------------------------------------------------------------------------------
# Import helpers
# ------------------------------------------------------------------------------


def _is_internal_missing_module(target: ImportTarget, exc: ModuleNotFoundError) -> bool:
    """Heuristic: decide whether a ModuleNotFoundError indicates an internal defect.

    - If the missing name is within the francis namespace, that's internal.
    - If the missing name is exactly the target module, that's internal.
    - Otherwise it is likely an external dependency not installed.
    """
    missing = getattr(exc, "name", "") or ""
    if not missing:
        return True
    if missing == target.module:
        return True
    return missing.startswith("francis")


def _fail_import(target: ImportTarget, exc: BaseException) -> None:
    """Fail with a high-signal diagnostic payload for import errors."""
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    sys_path_preview = "\n".join(f"  - {p}" for p in sys.path[:12])

    message = textwrap.dedent(
        f"""
        Import smoke test failed.

        Target:
          module:   {target.module}
          optional: {target.optional}
          reason:   {target.reason or "(none)"}

        Environment:
          python:      {sys.version.replace(os.linesep, " ")}
          executable:  {sys.executable}
          cwd:         {os.getcwd()}

        sys.path (first 12):
        {sys_path_preview}

        Exception:
        {tb}
        """
    ).strip()

    # pytest.fail gives nicer output control than raising AssertionError directly.
    pytest.fail(message, pytrace=False)


def _import_module(target: ImportTarget) -> object:
    """Attempt to import a module; apply optional-skip policy where appropriate."""
    try:
        return importlib.import_module(target.module)
    except ModuleNotFoundError as exc:
        # Optional modules may fail due to missing *external* dependencies.
        if target.optional and not _is_internal_missing_module(target, exc):
            missing = getattr(exc, "name", "") or "unknown"
            pytest.skip(f"Optional import skipped: {target.module} (missing external dependency: {missing})")
        _fail_import(target, exc)
    except Exception as exc:  # noqa: BLE001 - we want a full diagnostic for any import-time failure
        _fail_import(target, exc)

    # Unreachable, but keeps type-checkers happy.
    raise RuntimeError("Unreachable: import handler did not return or fail.")  # pragma: no cover


# ------------------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.unit
@pytest.mark.parametrize("target", _iter_targets(), ids=lambda t: t.module)
def test_import_targets(target: ImportTarget) -> None:
    """Import smoke test: core modules must import; optional modules are controlled."""
    _import_module(target)


@pytest.mark.smoke
@pytest.mark.unit
def test_deep_smoke_create_app_if_enabled() -> None:
    """Optional deeper check: ensure API app factory can be constructed (if present).

    This is guarded because some app factories may intentionally read config on
    construction; we don't want to force that requirement at pre-push time.
    """
    if not RUN_DEEP:
        pytest.skip("Deep smoke disabled (set FRANCIS_IMPORT_SMOKE_DEEP=1 to enable).")

    api_app = _import_module(ImportTarget("francis.api.app", reason="API app module"))
    create_app = getattr(api_app, "create_app", None)

    if not callable(create_app):
        pytest.skip("create_app() not found in francis.api.app; deep smoke not applicable.")

    try:
        app = create_app()
    except Exception as exc:  # noqa: BLE001 - diagnostic clarity > narrow exceptions
        _fail_import(
            ImportTarget(
                "francis.api.app:create_app",
                reason="API app factory must be constructible in deep smoke mode",
            ),
            exc,
        )

    assert app is not None
