from __future__ import annotations

import json
from pathlib import Path

from francis.plugin_system import PluginLoader, PluginRegistry, PluginSpec, PluginValidator, ToolSpec


def test_plugin_loader_normalizes_canonical_json_and_legacy_yaml(tmp_path: Path) -> None:
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir(parents=True, exist_ok=True)

    canonical_path = spec_dir / "builtin_echo.json"
    canonical_path.write_text(
        json.dumps(
            {
                "plugin_id": "builtin.echo",
                "name": "Builtin Echo",
                "version": "1.0.0",
                "origin": "builtin",
                "entrypoint": "plugin.py",
                "tools": [
                    {
                        "tool_name": "builtin.echo.run",
                        "action": "run",
                        "summary": "Echo",
                        "description": "Echo tool",
                        "methods": ["execute"],
                        "policy_tags": ["local_only"],
                        "input_schema": {"type": "object"},
                        "output_schema": {"type": "object"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    legacy_path = spec_dir / "legacy_echo.yaml"
    legacy_path.write_text(
        "\n".join(
            [
                "id: generated.echo",
                "name: Generated Echo",
                "description: Legacy generator output",
                "entrypoint: plugin.py",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    loader = PluginLoader(spec_dir=spec_dir)
    canonical = loader.load(canonical_path)
    legacy = loader.load(legacy_path)

    assert canonical is not None
    assert canonical.plugin_id == "builtin.echo"
    assert canonical.tools[0].tool_name == "builtin.echo.run"

    assert legacy is not None
    assert legacy.plugin_id == "generated.echo"
    assert legacy.entrypoint == "plugin.py"
    assert legacy.tools[0].tool_name == "generated.echo.run"
    assert legacy.tools[0].action == "run"


def test_plugin_validator_enforces_sensitive_tool_governance() -> None:
    spec = PluginSpec(
        plugin_id="ops.deploy",
        name="Ops Deploy",
        version="1.0.0",
        description="Deploy workloads.",
        origin="builtin",
        entrypoint="plugin.py",
        risk_class="critical",
        tools=(
            ToolSpec(
                tool_name="ops.deploy.release",
                action="deploy",
                summary="Deploy release",
                description="Deploy release to production.",
                methods=("execute",),
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                risk_class="critical",
            ),
        ),
    )

    result = PluginValidator().validate(spec)

    assert result.valid is False
    assert "approval_required:ops.deploy.release" in result.errors
    assert "policy_tags_required:ops.deploy.release" in result.errors


def test_plugin_registry_compiles_directory_deterministically(tmp_path: Path) -> None:
    spec_dir = tmp_path / "spec"
    registry_dir = tmp_path / "registry"
    spec_dir.mkdir(parents=True, exist_ok=True)

    first = {
        "plugin_id": "zeta.tools",
        "name": "Zeta Tools",
        "version": "1.0.0",
        "origin": "builtin",
        "entrypoint": "plugin.py",
        "tools": [
            {
                "tool_name": "zeta.tools.run",
                "action": "run",
                "summary": "Run zeta",
                "description": "Run zeta",
                "methods": ["execute"],
                "policy_tags": ["local_only"],
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
            }
        ],
    }
    second = {
        "plugin_id": "alpha.tools",
        "name": "Alpha Tools",
        "version": "1.0.0",
        "origin": "builtin",
        "entrypoint": "plugin.py",
        "tools": [
            {
                "tool_name": "alpha.tools.run",
                "action": "run",
                "summary": "Run alpha",
                "description": "Run alpha",
                "methods": ["execute"],
                "policy_tags": ["local_only"],
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
            }
        ],
    }

    (spec_dir / "zeta.json").write_text(json.dumps(first), encoding="utf-8")
    (spec_dir / "alpha.json").write_text(json.dumps(second), encoding="utf-8")

    loader = PluginLoader(spec_dir=spec_dir)
    registry = PluginRegistry()
    report = registry.load_from_directory(loader, spec_dir)

    assert report["loaded"] == 2
    assert report["rejected"] == []
    assert registry.list() == ["alpha.tools", "zeta.tools"]
    assert registry.get("Alpha Tools") is not None
    assert registry.find_tool("zeta.tools.run") is not None

    catalog_path = registry.write_catalog(registry_dir / "catalog.json")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

    assert [item["plugin_id"] for item in catalog["plugins"]] == ["alpha.tools", "zeta.tools"]
    assert [item["tool_name"] for item in catalog["tool_index"]] == ["alpha.tools.run", "zeta.tools.run"]
