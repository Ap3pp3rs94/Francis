from __future__ import annotations

import json
from pathlib import Path

from francis.plugin_system import PluginLoader, PluginRegistry, PluginSpec, PluginValidator, ToolSpec
from francis.plugin_system.execution.dispatcher import PluginDispatcher
from francis.plugin_system.execution.lifecycle import PluginLifecycle
from francis.plugin_system.sandbox.limits import SandboxLimits
from francis.plugin_system.sandbox.runner import SandboxRunner
from francis.telemetry.audit import read_events


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


def test_plugin_loader_rejects_specs_outside_trusted_root(monkeypatch, tmp_path: Path) -> None:
    spec_dir = tmp_path / "spec"
    outside_dir = tmp_path / "outside"
    spec_dir.mkdir(parents=True, exist_ok=True)
    outside_dir.mkdir(parents=True, exist_ok=True)

    trusted_path = spec_dir / "trusted.json"
    trusted_path.write_text(
        json.dumps(
            {
                "plugin_id": "trusted.echo",
                "name": "Trusted Echo",
                "origin": "builtin",
                "entrypoint": "plugin.py",
            }
        ),
        encoding="utf-8",
    )
    outside_path = outside_dir / "outside.json"
    outside_path.write_text(
        json.dumps(
            {
                "plugin_id": "outside.echo",
                "name": "Outside Echo",
                "origin": "generated",
                "entrypoint": "plugin.py",
            }
        ),
        encoding="utf-8",
    )

    loader = PluginLoader(spec_dir=spec_dir)

    assert loader.load(trusted_path) is not None
    assert loader.load(outside_path) is None
    assert loader.load(Path("..") / "outside" / "outside.json") is None
    assert loader.load_directory(outside_dir) == []
    monkeypatch.chdir(spec_dir)
    assert loader.load_directory(Path("..") / "outside") == []
    assert PluginLoader().load(trusted_path) is None


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


def test_plugin_registry_catalog_summarizes_forge_lineage_and_risk() -> None:
    registry = PluginRegistry()

    staged = PluginSpec(
        plugin_id="generated.deploy",
        name="Generated Deploy",
        version="0.1.0",
        description="Stage generated deployment assistance.",
        origin="generated",
        entrypoint="plugin.py",
        risk_class="critical",
        tools=(
            ToolSpec(
                tool_name="generated.deploy.release",
                action="deploy",
                summary="Deploy release",
                description="Deploy a generated release candidate.",
                methods=("execute",),
                policy_tags=("forge_generated", "deployment"),
                requires_approvals=True,
                requires_trust_level=4,
                dry_run_supported=True,
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                risk_class="critical",
            ),
        ),
        metadata={
            "promotion_status": "staged",
            "proposal_id": "proposal_generated_deploy",
            "proposal_path": "data/artifacts/plugins/proposals/proposal_generated_deploy.json",
        },
    )
    promoted = PluginSpec(
        plugin_id="builtin.lookup",
        name="Builtin Lookup",
        version="1.0.0",
        description="Read local catalog data.",
        origin="builtin",
        entrypoint="plugin.py",
        risk_class="readonly",
        tools=(
            ToolSpec(
                tool_name="builtin.lookup.read",
                action="read",
                summary="Read lookup",
                description="Read local lookup data.",
                methods=("read",),
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                risk_class="readonly",
            ),
        ),
        metadata={
            "promotion_status": "promoted",
            "promotion_receipt_id": "receipt_builtin_lookup",
            "promotion_receipt_path": "data/artifacts/plugins/promotions/receipt_builtin_lookup.json",
        },
    )

    assert registry.register(staged).valid is True
    assert registry.register(promoted).valid is True

    catalog = registry.to_dict()

    assert catalog["risk_class_counts"] == {"critical": 1, "readonly": 1}
    assert catalog["tool_risk_class_counts"] == {"critical": 1, "readonly": 1}
    assert catalog["approval_required_tool_count"] == 1
    assert catalog["lifecycle_status_counts"] == {"promoted": 1, "staged": 1}
    assert catalog["forge_lineage_index"] == [
        {
            "plugin_id": "builtin.lookup",
            "plugin_name": "Builtin Lookup",
            "promotion_status": "promoted",
            "promotion_receipt_id": "receipt_builtin_lookup",
            "promotion_receipt_path": "data/artifacts/plugins/promotions/receipt_builtin_lookup.json",
        },
        {
            "plugin_id": "generated.deploy",
            "plugin_name": "Generated Deploy",
            "promotion_status": "staged",
            "proposal_id": "proposal_generated_deploy",
            "proposal_path": "data/artifacts/plugins/proposals/proposal_generated_deploy.json",
        },
    ]


def test_sandbox_runner_emits_receipts_and_blocks_large_payload(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    runner = SandboxRunner(SandboxLimits(max_payload_bytes=32))

    ok = runner.run_with_receipt(lambda text: {"echo": text}, "hi", payload={"text": "hi"})
    assert ok.ok is True
    assert ok.status == "ok"
    assert ok.output == {"echo": "hi"}
    assert ok.run_id
    assert ok.trace_id

    blocked = runner.run_with_receipt(lambda text: text, "x" * 64, payload={"text": "x" * 64})
    assert blocked.ok is False
    assert blocked.status == "blocked"
    assert blocked.error == "payload_too_large"

    events = read_events(limit=10, event="plugin.sandbox.run")
    statuses = [item["status"] for item in events]
    assert "ok" in statuses
    assert "blocked" in statuses


def test_dispatcher_and_lifecycle_produce_audit_receipts(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    dispatcher = PluginDispatcher(sandbox=SandboxRunner(SandboxLimits(max_payload_bytes=256)))
    dispatched = dispatcher.dispatch_with_receipt(
        lambda name: f"hello {name}",
        "francis",
        plugin_id="builtin.echo",
        tool_name="builtin.echo.run",
    )

    assert dispatched.ok is True
    assert dispatched.status == "ok"
    assert dispatched.output == "hello francis"
    assert dispatched.plugin_id == "builtin.echo"
    assert dispatched.tool_name == "builtin.echo.run"
    assert dispatched.run_id
    assert dispatched.trace_id

    lifecycle = PluginLifecycle(name="builtin.echo")
    lifecycle.on_start()
    lifecycle.on_stop(reason="completed")
    snapshot = lifecycle.snapshot()

    assert snapshot["status"] == "stopped"
    assert snapshot["starts"] == 1
    assert snapshot["stops"] == 1

    dispatch_events = read_events(limit=10, event="plugin.dispatch")
    lifecycle_events = read_events(limit=10, event="plugin.lifecycle.stop")
    assert any(item["tool_name"] == "builtin.echo.run" for item in dispatch_events)
    assert any(item["plugin_name"] == "builtin.echo" for item in lifecycle_events)
