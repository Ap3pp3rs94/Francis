from __future__ import annotations

import tomllib
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_security_extra_does_not_ship_unused_paramiko_dependency() -> None:
    repo_root = _repo_root()
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    security_extra = pyproject["project"]["optional-dependencies"]["security"]

    assert "paramiko" not in security_extra
    assert 'name = "paramiko"' not in (repo_root / "uv.lock").read_text(encoding="utf-8")


def test_iot_extra_pins_zeroconf_security_floor() -> None:
    repo_root = _repo_root()
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((repo_root / "uv.lock").read_text(encoding="utf-8"))

    iot_extra = pyproject["project"]["optional-dependencies"]["iot"]
    assert "zeroconf>=0.149.7" in iot_extra

    zeroconf_packages = [package for package in lock["package"] if package["name"] == "zeroconf"]
    assert [package["version"] for package in zeroconf_packages] == ["0.149.7"]

    francis_package = next(package for package in lock["package"] if package["name"] == "francis")
    locked_iot_dependencies = francis_package["optional-dependencies"]["iot"]
    locked_iot_zeroconf = [dependency for dependency in locked_iot_dependencies if dependency["name"] == "zeroconf"]
    assert locked_iot_zeroconf == [{"name": "zeroconf", "specifier": ">=0.149.7"}]

    requires_dist = francis_package["metadata"]["requires-dist"]
    assert {
        "name": "zeroconf",
        "marker": "extra == 'iot'",
        "specifier": ">=0.149.7",
    } in requires_dist
