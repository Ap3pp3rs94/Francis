from __future__ import annotations

from pathlib import Path

import yaml


def _dependabot_config() -> dict:
    config_path = Path(__file__).resolve().parents[1] / ".github" / "dependabot.yml"
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def test_dependabot_uv_scan_excludes_legacy_requirements_profiles() -> None:
    config = _dependabot_config()
    updates = config["updates"]
    uv_entries = [
        entry
        for entry in updates
        if entry["package-ecosystem"] == "uv" and entry["directory"] == "/"
    ]

    assert config["version"] == 2
    assert len(uv_entries) == 1
    assert uv_entries[0]["schedule"] == {"interval": "weekly"}
    assert uv_entries[0]["exclude-paths"] == ["requirements/**"]
    assert all(entry["directory"] != "/requirements" for entry in updates)
