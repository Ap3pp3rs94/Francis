from __future__ import annotations

import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest

from francis.kernel.paths import repo_root

_SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


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
