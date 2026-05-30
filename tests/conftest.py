from __future__ import annotations

import json
import os
import re
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from francis.kernel.paths import repo_root

_SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")
_PYTEST_SESSION_RETENTION_ROOT = repo_root() / "data" / "test_runs" / "pytest"
_PYTEST_SESSION_RETENTION_KEEP_COUNT = 50
_PYTEST_SESSION_RETENTION_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
_PYTEST_SESSION_RETENTION_KIND = "retention.execution.receipt"
_PYTEST_SESSION_RETENTION_ENV = "FRANCIS_PYTEST_SESSION_RETENTION_ROOT"
APPROVAL_DECISION_TEST_ACTOR = "test.approvals.decision"
APPROVAL_DECISION_TEST_SCOPE = "approvals.decide"
APPROVAL_REQUEST_TEST_SCOPE = "approvals.request"
APPROVAL_REQUEST_TEST_ACTORS = (
    "test.approvals.request",
    "test.api.security",
    "test.lens.approval_request",
)
TRUST_WRITE_TEST_SCOPE = "trust.write"
TRUST_WRITE_TEST_ACTORS = (
    "test.trust.write",
    "ops",
    "sre",
    "api-test",
    "system-ui",
)
CREDENTIAL_WRITE_TEST_SCOPE = "credentials.write"
CREDENTIAL_WRITE_TEST_ACTORS = (
    "test.credentials.write",
    "operator.credentials",
    "operator.cleanup",
    "credential_manager_api",
)
SYSTEM_WRITE_TEST_SCOPE = "system.write"
SYSTEM_WRITE_TEST_ACTORS = (
    "chat_ui.command_palette",
    "chat_ui.shift_briefing",
    "chat_ui.system",
    "test.system.write",
    "test.system.observer",
    "test.system.redaction",
    "test.continuity.briefing",
    "chat_ui",
    "chat_ui_alias_test",
    "tests",
)
PLUGIN_WRITE_TEST_SCOPE = "plugins.write"
PLUGIN_WRITE_TEST_ACTORS = (
    "test.plugins.write",
    "chat_ui.plugins",
    "plugin_browser_api",
)
MISSION_WRITE_TEST_SCOPE = "missions.write"
MISSION_WRITE_TEST_ACTORS = (
    "chat.send",
    "chat_ui.operations",
    "test.missions",
    "test.missions.permission_gate",
    "test.missions.write",
    "test.missions.approval_projection",
    "test.missions.redaction",
    "test.missions.observe",
    "test.missions.queue",
    "test.missions.tick",
    "test.missions.deadletter",
    "test.missions.replace",
    "test.missions.dependencies",
    "test.missions.advance",
    "test.missions.linked",
    "test.missions.failed_memory_receipt",
    "test.missions.trace",
    "test.missions.artifact",
    "test.missions.governance",
    "test.missions.current_task",
    "test.missions.store",
    "test.approvals.loop_handles",
    "test.operations.artifact_filter",
    "test.operations.memory_receipt",
    "test.operations.failed_memory_receipt",
    "test.operations.approved_mission_receipt",
    "test.memory.timeline.mission_receipt",
    "test.memory.timeline.approval_receipt",
    "test.continuity.briefing",
    "test.continuity.deadletter",
    "test.continuity.dependencies",
    "test.continuity.stage3.ready",
    "test.continuity.failed",
    "test.continuity.replacement",
    "test.continuity.approval_projection",
    "test.continuity.approved_gate",
    "test.continuity.deadletter_approval_projection",
    "test.system.world_state",
    "test.system.queue",
    "test.system.current_activity",
    "test.system.approval_projection",
    "test.system.briefing",
    "test.system.orb",
    "test.system.operator_mode",
    "test.system.deadletter_approval_projection",
    "tests",
    "chat_ui.orb",
)
CHAT_WRITE_TEST_SCOPE = "chat.write"
CHAT_WRITE_TEST_ACTORS = (
    "api.chat",
    "chat_ui.chat",
    "test.chat.write",
)
OPERATION_RUN_TEST_SCOPE = "operations.run"
OPERATION_RUN_TEST_ACTORS = (
    "api.operations",
    "test.operations.run",
)
OPERATION_WRITE_TEST_SCOPE = "operations.write"
OPERATION_WRITE_TEST_ACTORS = (
    "api.operations",
    "test.operations.write",
)
MEMORY_TIMELINE_WRITE_TEST_SCOPE = "memory.timeline.write"
MEMORY_TIMELINE_WRITE_TEST_ACTORS = ("test.memory.timeline.write",)
EXPLANATION_WRITE_TEST_SCOPE = "explanation.write"
EXPLANATION_WRITE_TEST_ACTORS = ("test.explanation.write",)
WEB_LEARNING_WRITE_TEST_SCOPE = "web_learning.write"
WEB_LEARNING_WRITE_TEST_ACTORS = (
    "api",
    "operator:a",
    "operator:b",
    "operator:redaction",
    "operator:sealed",
    "test.web_learning.write",
)
ATTACHMENTS_WRITE_TEST_SCOPE = "attachments.write"
ATTACHMENTS_WRITE_TEST_ACTORS = (
    "api.attachments",
    "test.attachments.write",
)
FEDERATION_WRITE_TEST_SCOPE = "federation.write"
FEDERATION_WRITE_TEST_ACTORS = (
    "api.federation",
    "test.federation.write",
)
INDUSTRIAL_WRITE_TEST_SCOPE = "industrial.write"
INDUSTRIAL_WRITE_TEST_ACTORS = (
    "api.industrial",
    "industrial_api",
    "operator:a",
    "operator:b",
    "operator:queue",
    "operator:redaction",
    "operator:params",
    "operator:world_state",
    "test.industrial.write",
)


def _safe_real_path(path: Path) -> str:
    return str(path.resolve())


def _dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for entry in path.rglob("*"):
        try:
            if entry.is_file():
                total += entry.stat().st_size
        except (OSError, ValueError):
            continue
    return total


def _session_directories(pytest_root: Path) -> list[Path]:
    if not pytest_root.exists():
        return []
    sessions: list[tuple[Path, float]] = []
    for child in pytest_root.iterdir():
        if not child.is_dir() or not child.name.startswith("session_"):
            continue
        try:
            mtime = child.stat().st_mtime
        except OSError:
            continue
        sessions.append((child, mtime))
    sessions.sort(key=lambda item: item[1], reverse=True)
    return [path for path, _ in sessions]


def _build_retention_receipt_path(pytest_root: Path, now_ts: float) -> Path:
    receipts_dir = pytest_root / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now_ts))
    return receipts_dir / f"retention.execution.receipt.{stamp}.json"


def _pytest_session_retention_root() -> Path:
    configured = os.environ.get(_PYTEST_SESSION_RETENTION_ENV)
    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            candidate = repo_root() / configured
        retention_root = _PYTEST_SESSION_RETENTION_ROOT.resolve()
        if not candidate.is_relative_to(repo_root()):
            raise RuntimeError("Invalid pytest retention root path")
        candidate = candidate.resolve()
        try:
            candidate.relative_to(retention_root)
        except ValueError:
            raise RuntimeError("Invalid pytest retention root path")
        return candidate
    return _PYTEST_SESSION_RETENTION_ROOT


def run_pytest_session_retention(
    *, pytest_root: Path, now: float | None = None, receipt_path: Path | None = None
) -> dict[str, Any]:
    now_ts = now if now is not None else time.time()
    pytest_root.mkdir(parents=True, exist_ok=True)

    sessions = _session_directories(pytest_root)
    kept_by_floor = sessions[:_PYTEST_SESSION_RETENTION_KEEP_COUNT]
    stale_cutoff = now_ts - _PYTEST_SESSION_RETENTION_MAX_AGE_SECONDS

    deletion_candidates = sessions[_PYTEST_SESSION_RETENTION_KEEP_COUNT:]
    deleted_sessions: list[Path] = []
    failed_deletions: list[str] = []
    bytes_freed = 0
    for session in deletion_candidates:
        try:
            mtime = session.stat().st_mtime
        except OSError:
            failed_deletions.append(f"{session.resolve()} (unreadable)")
            continue
        if mtime <= stale_cutoff:
            session_size = _dir_size_bytes(session)
            try:
                shutil.rmtree(session)
            except OSError:
                failed_deletions.append(str(session.resolve()))
                continue
            deleted_sessions.append(session)
            bytes_freed += session_size

    if receipt_path is None:
        receipt_path = _build_retention_receipt_path(pytest_root, now_ts)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)

    retained_skip_due_to_floor = [str(session.resolve()) for session in kept_by_floor]
    deleted_names = [str(session.resolve()) for session in deleted_sessions]

    payload = {
        "kind": _PYTEST_SESSION_RETENTION_KIND,
        "scope": "pytest_session_retention",
        "created_at": int(now_ts),
        "pytest_root": _safe_real_path(pytest_root),
        "policy": {
            "keep_most_recent_sessions": _PYTEST_SESSION_RETENTION_KEEP_COUNT,
            "max_age_seconds": _PYTEST_SESSION_RETENTION_MAX_AGE_SECONDS,
        },
        "retained_by_floor_count": len(retained_skip_due_to_floor),
        "considered_count": len(deletion_candidates),
        "deleted_count": len(deleted_sessions),
        "bytes_freed": bytes_freed,
        "deleted_sessions": deleted_names,
        "failed_deletions": failed_deletions,
        "retained_by_floor_sessions": retained_skip_due_to_floor,
        "receipt_path": str(receipt_path.resolve()),
    }
    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    return payload


def pytest_sessionstart(session: pytest.Session) -> None:
    pytest_root = _pytest_session_retention_root()
    if not pytest_root.is_relative_to(repo_root()):
        raise RuntimeError("Invalid pytest root path for retention cleanup")
    run_pytest_session_retention(pytest_root=pytest_root)


def _add_actor_scopes(policy: dict[str, list[str]], actors: tuple[str, ...], scope: str) -> None:
    for actor in actors:
        scopes = policy.setdefault(actor, [])
        if scope not in scopes:
            scopes.append(scope)


def _test_actor_scope_policy() -> dict[str, list[str]]:
    policy: dict[str, list[str]] = {APPROVAL_DECISION_TEST_ACTOR: [APPROVAL_DECISION_TEST_SCOPE]}
    _add_actor_scopes(policy, APPROVAL_REQUEST_TEST_ACTORS, APPROVAL_REQUEST_TEST_SCOPE)
    _add_actor_scopes(policy, TRUST_WRITE_TEST_ACTORS, TRUST_WRITE_TEST_SCOPE)
    _add_actor_scopes(policy, CREDENTIAL_WRITE_TEST_ACTORS, CREDENTIAL_WRITE_TEST_SCOPE)
    _add_actor_scopes(policy, SYSTEM_WRITE_TEST_ACTORS, SYSTEM_WRITE_TEST_SCOPE)
    _add_actor_scopes(policy, PLUGIN_WRITE_TEST_ACTORS, PLUGIN_WRITE_TEST_SCOPE)
    _add_actor_scopes(policy, MISSION_WRITE_TEST_ACTORS, MISSION_WRITE_TEST_SCOPE)
    _add_actor_scopes(policy, CHAT_WRITE_TEST_ACTORS, CHAT_WRITE_TEST_SCOPE)
    _add_actor_scopes(policy, OPERATION_RUN_TEST_ACTORS, OPERATION_RUN_TEST_SCOPE)
    _add_actor_scopes(policy, OPERATION_WRITE_TEST_ACTORS, OPERATION_WRITE_TEST_SCOPE)
    _add_actor_scopes(policy, MEMORY_TIMELINE_WRITE_TEST_ACTORS, MEMORY_TIMELINE_WRITE_TEST_SCOPE)
    _add_actor_scopes(policy, EXPLANATION_WRITE_TEST_ACTORS, EXPLANATION_WRITE_TEST_SCOPE)
    _add_actor_scopes(policy, WEB_LEARNING_WRITE_TEST_ACTORS, WEB_LEARNING_WRITE_TEST_SCOPE)
    _add_actor_scopes(policy, ATTACHMENTS_WRITE_TEST_ACTORS, ATTACHMENTS_WRITE_TEST_SCOPE)
    _add_actor_scopes(policy, FEDERATION_WRITE_TEST_ACTORS, FEDERATION_WRITE_TEST_SCOPE)
    _add_actor_scopes(policy, INDUSTRIAL_WRITE_TEST_ACTORS, INDUSTRIAL_WRITE_TEST_SCOPE)
    return policy


def _slug(value: str, *, default: str = "case") -> str:
    text = _SAFE_SEGMENT_RE.sub("-", value.strip()).strip("-._")
    return text[:80] or default


@pytest.fixture(scope="session")
def _francis_tmp_root() -> Path:
    """Use a repo-local temp root instead of pytest's Windows temp plugin path.

    The sandboxed environment backing this repo can deny access to pytest's default
    temp/cache paths during fixture setup and cleanup. We keep test temp state in
    `data/test_runs/pytest/`.
    """
    root = _pytest_session_retention_root()

    session_root = root / f"session_{int(time.time())}_{os.getpid()}_{uuid.uuid4().hex[:8]}"
    session_root.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("TMPDIR", str(session_root))
    os.environ.setdefault("TEMP", str(session_root))
    os.environ.setdefault("TMP", str(session_root))
    return session_root


@dataclass(slots=True)
class RepoTmpPathFactory:
    base: Path

    def mktemp(self, basename: str, numbered: bool = True) -> Path:
        prefix = _slug(basename, default="tmp")
        suffix = uuid.uuid4().hex[:8] if numbered else "static"
        path = self.base / f"{prefix}_{suffix}"
        path.mkdir(parents=True, exist_ok=False)
        return path

    def getbasetemp(self) -> Path:
        return self.base


@pytest.fixture(scope="session")
def tmp_path_factory(_francis_tmp_root: Path) -> RepoTmpPathFactory:
    return RepoTmpPathFactory(_francis_tmp_root)


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest, tmp_path_factory: RepoTmpPathFactory) -> Path:
    return tmp_path_factory.mktemp(request.node.name)


@pytest.fixture(autouse=True)
def _api_actor_scopes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps(_test_actor_scope_policy()),
    )
