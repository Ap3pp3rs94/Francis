from __future__ import annotations

import json
import zipfile
from pathlib import Path

from francis.plugin_factory import spec_builder


def test_build_plugin_writes_contract_spec_and_registry(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = tmp_path / "data"
    repo_root.mkdir(parents=True, exist_ok=True)
    data_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(spec_builder, "repo_root", lambda: repo_root)
    monkeypatch.setattr(spec_builder, "data_dir", lambda: data_root)

    built = spec_builder.build_plugin("Echo Plugin", "Simple echo plugin")
    plugin_id = str(built["plugin_id"])
    generated_dir = Path(str(built["generated_dir"]))
    artifact_zip = Path(str(built["artifact_zip"]))
    spec_path = Path(str(built["spec_path"]))
    registry_snapshot = Path(str(built["registry_snapshot"]))

    assert generated_dir.exists()
    assert artifact_zip.exists()
    assert spec_path.exists()
    assert registry_snapshot.exists()

    spec_payload = json.loads(spec_path.read_text(encoding="utf-8"))
    assert spec_payload["plugin_id"] == plugin_id
    assert spec_payload["origin"] == "generated"
    assert spec_payload["tools"][0]["tool_name"] == f"generated.{plugin_id}.run"

    registry_payload = json.loads(registry_snapshot.read_text(encoding="utf-8"))
    assert registry_payload["total_plugins"] == 1
    assert registry_payload["tool_index"][0]["plugin_id"] == plugin_id

    validation = built["validation"]
    assert validation["valid"] is True
    assert validation["reason"] == "ok"

    with zipfile.ZipFile(artifact_zip) as handle:
        names = set(handle.namelist())
    assert f"{plugin_id}/plugin.spec.json" in names
    assert f"{plugin_id}/plugin.registry.json" in names
