from __future__ import annotations

import tomllib
from pathlib import Path


def test_security_extra_does_not_ship_unused_paramiko_dependency() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    security_extra = pyproject["project"]["optional-dependencies"]["security"]

    assert "paramiko" not in security_extra
    assert 'name = "paramiko"' not in (repo_root / "uv.lock").read_text(encoding="utf-8")
