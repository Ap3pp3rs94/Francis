from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest

from francis.kernel.paths import repo_root

_SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")
APPROVAL_DECISION_TEST_ACTOR = "test.approvals.decision"
APPROVAL_DECISION_TEST_SCOPE = "approvals.decide"
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
OPERATION_RUN_TEST_SCOPE = "operations.run"
OPERATION_RUN_TEST_ACTORS = (
    "api.operations",
    "test.operations.run",
)


def _add_actor_scopes(policy: dict[str, list[str]], actors: tuple[str, ...], scope: str) -> None:
    for actor in actors:
        scopes = policy.setdefault(actor, [])
        if scope not in scopes:
            scopes.append(scope)


def _test_actor_scope_policy() -> dict[str, list[str]]:
    policy: dict[str, list[str]] = {APPROVAL_DECISION_TEST_ACTOR: [APPROVAL_DECISION_TEST_SCOPE]}
    _add_actor_scopes(policy, TRUST_WRITE_TEST_ACTORS, TRUST_WRITE_TEST_SCOPE)
    _add_actor_scopes(policy, CREDENTIAL_WRITE_TEST_ACTORS, CREDENTIAL_WRITE_TEST_SCOPE)
    _add_actor_scopes(policy, SYSTEM_WRITE_TEST_ACTORS, SYSTEM_WRITE_TEST_SCOPE)
    _add_actor_scopes(policy, PLUGIN_WRITE_TEST_ACTORS, PLUGIN_WRITE_TEST_SCOPE)
    _add_actor_scopes(policy, MISSION_WRITE_TEST_ACTORS, MISSION_WRITE_TEST_SCOPE)
    _add_actor_scopes(policy, OPERATION_RUN_TEST_ACTORS, OPERATION_RUN_TEST_SCOPE)
    return policy


def _slug(value: str, *, default: str = "case") -> str:
    text = _SAFE_SEGMENT_RE.sub("-", value.strip()).strip("-._")
    return text[:80] or default


@pytest.fixture(scope="session")
def _francis_tmp_root() -> Path:
    """Use a repo-local temp root instead of pytest's Windows temp plugin path.

    The sandboxed environment backing this repo can deny access to pytest's default
    temp/cache paths during fixture setup and cleanup. We keep test temp state in
    `data/test_runs/pytest/` and intentionally do not delete it automatically.
    """

    root = repo_root() / "data" / "test_runs" / "pytest"
    root.mkdir(parents=True, exist_ok=True)

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
