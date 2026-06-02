from __future__ import annotations

import json
import shutil
from pathlib import Path

_PLUGIN_ACTOR = "test.plugins.write"


def _forge_promotion_meta(label: str) -> dict[str, object]:
    return {
        "friction_summary": f"Repeated {label} plugin review",
        "proposal_evidence": [f"mission.{label}.repeat"],
        "tests": [f"tests/test_api_plugins.py::{label}"],
        "docs": ["README.md"],
        "risk_tier": "normal",
    }


def _approve_forge_proposal(client, proposal_id: str) -> dict[str, object]:
    approved = client.post(
        "/forge/proposals/decision",
        json={
            "id": proposal_id,
            "action": "approve",
            "actor": _PLUGIN_ACTOR,
            "reason": "test proposal approval",
        },
    )
    assert approved.status_code == 200
    approved_body = approved.json()
    assert approved_body["ok"] is True, approved_body
    assert approved_body["status"] == "approved"
    return approved_body


def _approve_capability_pack_operator_review(
    client,
    *,
    pack_id: str,
    pack_version: str,
) -> dict[str, object]:
    approved = client.post(
        "/plugins/capabilities/packs/operator/review/decisions",
        json={
            "pack_id": pack_id,
            "pack_version": pack_version,
            "action": "approve",
            "actor": _PLUGIN_ACTOR,
            "reason": "test pack operator review approval",
        },
    )
    assert approved.status_code == 200
    approved_body = approved.json()
    assert approved_body["ok"] is True, approved_body
    assert approved_body["status"] == "approved"
    return approved_body


def test_plugins_atomic_write_json_uses_unique_temp_siblings(monkeypatch, tmp_path: Path) -> None:
    from francis.api.routes import plugins

    replace_calls: list[Path] = []
    real_replace = plugins.os.replace

    def normalize_spy_path(value: str | Path) -> Path:
        text = str(value)
        if text.startswith("\\\\?\\UNC\\"):
            text = "\\\\" + text.removeprefix("\\\\?\\UNC\\")
        elif text.startswith("\\\\?\\"):
            text = text.removeprefix("\\\\?\\")
        return Path(text)

    def spy_replace(src: str | Path, dst: str | Path) -> None:
        replace_calls.append(normalize_spy_path(src))
        real_replace(src, dst)

    monkeypatch.setattr(plugins.os, "replace", spy_replace)
    path = tmp_path / "plugins" / "_registry.json"

    plugins._atomic_write_json(path, {"write": 1})
    plugins._atomic_write_json(path, {"write": 2})

    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == {"write": 2}
    assert len(replace_calls) == 2
    assert len({item.name for item in replace_calls}) == 2
    assert all(item.parent == path.parent for item in replace_calls)
    assert all(item.name.startswith(".atomic-json-") for item in replace_calls)
    assert all("_registry.json" not in item.name for item in replace_calls)
    assert not any(path.parent.glob(".atomic-json-*.tmp"))


def test_plugins_build_lifecycle_and_run(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    raw_secret = "sk-" + ("x" * 24)
    built = client.post(
        "/plugins/build",
        json={
            "name": "Echo Plugin",
            "description": "Simple echo",
            "actor": _PLUGIN_ACTOR,
            "meta": {
                "friction_summary": "Repeated echo handoff review",
                "proposal_evidence": ["mission.echo.repeat"],
                "recurrence_count": 2,
                "expected_benefit": "Reduce repeated echo plugin setup.",
                "tests": ["tests/test_api_plugins.py::test_plugins_build_lifecycle_and_run"],
                "docs": ["README.md"],
                "risk_tier": "normal",
                "api_key": raw_secret,
            },
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])
    assert built_body["status"] == "staged"
    assert built_body["enabled"] is False
    assert built_body["promotion_status"] == "staged"
    assert built_body["next_step"] == "review_validate_and_explicitly_enable_before_use"
    assert built_body["validation"]["valid"] is True
    assert str(built_body["proposal_id"]).startswith("plugin_proposal_")
    proposal = built_body["proposal"]
    assert proposal["kind"] == "plugin.proposal"
    assert proposal["plugin_id"] == plugin_id
    assert proposal["status"] == "staged"
    assert proposal["friction"]["summary"] == "Repeated echo handoff review"
    assert proposal["friction"]["evidence"] == ["mission.echo.repeat"]
    assert proposal["quality_requirements"]["risk_tier"] == "normal"
    assert proposal["quality_requirements"]["tests"] == [
        "tests/test_api_plugins.py::test_plugins_build_lifecycle_and_run"
    ]
    assert proposal["proposal_context"]["api_key"] == "[REDACTED:secret]"
    assert proposal["governance"]["auto_promoted"] is False
    proposal_path = Path(str(proposal["path"]))
    assert proposal_path.exists()
    proposal_text = proposal_path.read_text(encoding="utf-8")
    assert raw_secret not in proposal_text
    persisted_proposal = json.loads(proposal_text)
    assert persisted_proposal["proposal_id"] == proposal["proposal_id"]
    assert Path(str(built_body["spec_path"])).exists()
    assert Path(str(built_body["registry_snapshot"])).exists()
    assert Path(str(built_body["catalog"]["path"])).exists()

    listed = client.get("/plugins/list")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert isinstance(listed_body.get("items"), list)
    assert any(str(item.get("id")) == plugin_id for item in listed_body["items"])

    fetched = client.get(f"/plugins/get?id={plugin_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["item"]["id"] == plugin_id
    assert fetched_body["item"]["status"] == "staged"
    assert fetched_body["item"]["enabled"] is False
    assert fetched_body["item"]["source_kind"] in {"generated", "unknown"}
    assert fetched_body["item"]["contract"]["plugin_id"] == plugin_id
    assert fetched_body["item"]["contract"]["tool_count"] >= 1
    assert fetched_body["item"]["registry_snapshot"]["total_plugins"] >= 1
    assert fetched_body["item"]["runtime"]["spec_exists"] is True
    assert fetched_body["item"]["runtime"]["registry_snapshot_exists"] is True
    assert fetched_body["item"]["meta"]["proposal_id"] == proposal["proposal_id"]
    assert fetched_body["item"]["meta"]["proposal_path"] == str(proposal_path)
    assert fetched_body["item"]["meta"]["proposal_evidence"] == ["mission.echo.repeat"]

    run_staged = client.post("/plugins/run", json={"id": plugin_id, "action": "run", "input": "hello"})
    assert run_staged.status_code == 200
    run_staged_body = run_staged.json()
    assert run_staged_body["ok"] is False
    assert run_staged_body["error"] == "plugin_staged"
    assert run_staged_body["status"] == "staged"

    approved = _approve_forge_proposal(client, str(proposal["proposal_id"]))
    review_receipt_id = str(approved["review_receipt_id"])

    enabled = client.post(
        "/plugins/enable",
        json={
            "id": plugin_id,
            "reason": f"test_enable api_key={raw_secret}",
            "actor": _PLUGIN_ACTOR,
        },
    )
    assert enabled.status_code == 200
    enabled_body = enabled.json()
    assert enabled_body["ok"] is True
    assert enabled_body["enabled"] is True
    assert enabled_body["promotion_status"] == "promoted"
    promotion_receipt = enabled_body["promotion_receipt"]
    assert promotion_receipt["kind"] == "plugin.promotion.receipt"
    assert promotion_receipt["plugin_id"] == plugin_id
    assert promotion_receipt["previous_status"] == "staged"
    assert promotion_receipt["promoted_status"] == "enabled"
    assert promotion_receipt["proposal_id"] == proposal["proposal_id"]
    assert promotion_receipt["proposal_review"]["status"] == "approved"
    assert promotion_receipt["proposal_review"]["receipt_id"] == review_receipt_id
    assert promotion_receipt["proposal_evidence"] == ["mission.echo.repeat"]
    assert promotion_receipt["quality"]["risk_tier"] == "normal"
    assert promotion_receipt["quality"]["tests"] == ["tests/test_api_plugins.py::test_plugins_build_lifecycle_and_run"]
    assert promotion_receipt["promotion_context"]["proposal_id"] == proposal["proposal_id"]
    assert "api_key=[REDACTED:secret]" in promotion_receipt["reason"]
    receipt_path = Path(str(promotion_receipt["path"]))
    assert receipt_path.exists()
    receipt_text = receipt_path.read_text(encoding="utf-8")
    assert raw_secret not in receipt_text
    persisted_receipt = json.loads(receipt_text)
    assert persisted_receipt["receipt_id"] == promotion_receipt["receipt_id"]
    assert persisted_receipt["status"] == "promoted"

    promoted = client.get(f"/plugins/get?id={plugin_id}")
    assert promoted.status_code == 200
    promoted_item = promoted.json()["item"]
    assert promoted_item["status"] == "enabled"
    assert promoted_item["enabled"] is True
    assert "staged" not in promoted_item["tags"]
    assert "promoted" in promoted_item["tags"]
    assert promoted_item["meta"]["promotion_status"] == "promoted"
    assert promoted_item["meta"]["promotion_receipt_id"] == promotion_receipt["receipt_id"]

    run_enabled = client.post("/plugins/run", json={"id": plugin_id, "action": "run", "input": "hello"})
    assert run_enabled.status_code == 200
    run_enabled_body = run_enabled.json()
    assert run_enabled_body["ok"] is True
    assert str(run_enabled_body["output"]) == "Plugin response: hello"
    assert run_enabled_body["receipt"]["ok"] is True
    assert run_enabled_body["receipt"]["run_id"]
    assert run_enabled_body["receipt"]["trace_id"]

    disabled = client.post("/plugins/disable", json={"id": plugin_id, "reason": "test_disable", "actor": _PLUGIN_ACTOR})
    assert disabled.status_code == 200
    disabled_body = disabled.json()
    assert disabled_body["ok"] is True
    assert disabled_body["enabled"] is False
    assert disabled_body["status"] == "disabled"

    run_disabled = client.post("/plugins/run", json={"id": plugin_id, "action": "run", "input": "hello"})
    assert run_disabled.status_code == 200
    run_disabled_body = run_disabled.json()
    assert run_disabled_body["ok"] is False
    assert run_disabled_body["status"] == "disabled"

    downloaded = client.get(f"/plugins/download/{plugin_id}")
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] in {
        "application/zip",
        "application/x-zip-compressed",
        "application/octet-stream",
    }

    registry_path = data_root / "plugins" / "_registry.json"
    assert registry_path.exists()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert plugin_id in registry["plugins"]


def test_plugins_build_requires_forge_staging_quality(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    built = client.post(
        "/plugins/build",
        json={"name": "Under Ready Plugin", "description": "missing readiness metadata", "actor": _PLUGIN_ACTOR},
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is False
    assert built_body["applied"] is False
    assert built_body["status"] == "blocked"
    assert built_body["error"] == "forge_staging_requirements_missing"
    assert built_body["missing_requirements"] == [
        "friction_summary",
        "proposal_evidence",
        "tests",
        "docs",
        "risk_tier",
    ]
    assert built_body["readiness"]["requirements"] == {
        "friction_summary": False,
        "proposal_evidence": False,
        "tests": False,
        "docs": False,
        "risk_tier": False,
    }
    assert built_body["governance"]["gate"] == "forge_staging_quality"
    assert built_body["governance"]["promotion_authority"] is False
    assert built_body["governance"]["execution_authority"] is False
    assert built_body["governance"]["approval_authority"] is False
    assert built_body["governance"]["memory_write"] is False

    assert not (data_root / "plugins" / "_registry.json").exists()
    proposal_dir = data_root / "artifacts" / "plugins" / "proposals"
    assert not proposal_dir.exists() or list(proposal_dir.glob("*.json")) == []
    promotion_dir = data_root / "artifacts" / "plugins" / "promotions"
    assert not promotion_dir.exists() or list(promotion_dir.glob("*.json")) == []


def test_staged_plugin_promotion_requires_approved_proposal_review(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    built = client.post(
        "/plugins/build",
        json={
            "name": "Review Required Plugin",
            "description": "complete metadata but missing proposal review",
            "actor": _PLUGIN_ACTOR,
            "meta": _forge_promotion_meta("review_required"),
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    blocked = client.post(
        "/plugins/enable",
        json={"id": plugin_id, "reason": "operator asked before review", "actor": _PLUGIN_ACTOR},
    )
    assert blocked.status_code == 200
    blocked_body = blocked.json()
    assert blocked_body["ok"] is False
    assert blocked_body["applied"] is False
    assert blocked_body["error"] == "promotion_readiness_blocked"
    assert blocked_body["status"] == "staged"
    assert blocked_body["readiness"]["missing_requirements"] == ["proposal_review"]
    assert blocked_body["readiness"]["requirements"]["proposal_review"] is False
    assert blocked_body["readiness"]["evidence"]["proposal_review_status"] == "staged"
    assert blocked_body["readiness"]["evidence"]["proposal_review_receipt_id"] == ""

    fetched = client.get(f"/plugins/get?id={plugin_id}")
    assert fetched.status_code == 200
    fetched_item = fetched.json()["item"]
    assert fetched_item["status"] == "staged"
    assert fetched_item["enabled"] is False

    promotion_dir = data_root / "artifacts" / "plugins" / "promotions"
    assert not promotion_dir.exists() or list(promotion_dir.glob("*.json")) == []


def test_plugins_install_uninstall_reload_and_filters(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/toolkit",
            "version": "1.2.3",
            "reason": "integration_test",
            "actor": _PLUGIN_ACTOR,
        },
    )
    assert installed.status_code == 200
    installed_body = installed.json()
    assert installed_body["ok"] is True
    plugin_id = str(installed_body["plugin_id"])
    assert installed_body["validation"]["valid"] is True
    assert Path(str(installed_body["catalog"]["path"])).exists()

    fetched = client.get(f"/plugins/get?id={plugin_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["item"]["source_kind"] == "registry"
    assert fetched_body["item"]["source_ref"] == "acme/toolkit"
    assert fetched_body["item"]["contract"]["origin"] == "registry"
    assert fetched_body["item"]["contract"]["tool_count"] >= 1

    filtered = client.get("/plugins/list?source_kind=registry&search=tool")
    assert filtered.status_code == 200
    filtered_ids = {str(item.get("id")) for item in filtered.json()["items"]}
    assert plugin_id in filtered_ids

    disabled = client.post("/plugins/disable", json={"id": plugin_id, "actor": _PLUGIN_ACTOR})
    assert disabled.status_code == 200
    assert disabled.json()["ok"] is True

    disabled_list = client.get("/plugins/list?enabled=0")
    assert disabled_list.status_code == 200
    disabled_ids = {str(item.get("id")) for item in disabled_list.json()["items"]}
    assert plugin_id in disabled_ids

    uninstalled = client.post("/plugins/uninstall", json={"id": plugin_id, "reason": "cleanup", "actor": _PLUGIN_ACTOR})
    assert uninstalled.status_code == 200
    uninstalled_body = uninstalled.json()
    assert uninstalled_body["ok"] is True
    assert uninstalled_body["status"] == "uninstalled"

    fetched_after_delete = client.get(f"/plugins/get?id={plugin_id}")
    assert fetched_after_delete.status_code == 200
    assert fetched_after_delete.json()["ok"] is False

    reloaded = client.post("/plugins/reload", json={"reason": "test_reload", "actor": _PLUGIN_ACTOR})
    assert reloaded.status_code == 200
    reloaded_body = reloaded.json()
    assert reloaded_body["ok"] is True
    assert "total" in reloaded_body
    assert Path(str(reloaded_body["catalog"]["path"])).exists()


def test_plugins_tools_catalog_and_action_validation(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    built = client.post(
        "/plugins/build",
        json={
            "name": "Catalog Plugin",
            "description": "Tool catalog coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": _forge_promotion_meta("catalog_plugin"),
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    tools = client.get(f"/plugins/tools/list?plugin_id={plugin_id}")
    assert tools.status_code == 200
    tools_body = tools.json()
    assert isinstance(tools_body.get("items"), list)
    assert tools_body.get("total", 0) >= 1
    first_tool = tools_body["items"][0]
    assert first_tool["plugin_id"] == plugin_id
    assert first_tool["action"] == "run"
    assert first_tool["required_trust"] == 0
    assert first_tool["approvals_required"] is False

    tool_id = str(first_tool["id"])
    fetched_tool = client.get(f"/plugins/tools/get?id={tool_id}")
    assert fetched_tool.status_code == 200
    fetched_tool_body = fetched_tool.json()
    assert fetched_tool_body["ok"] is True
    assert fetched_tool_body["item"]["id"] == tool_id

    _approve_forge_proposal(client, str(built_body["proposal_id"]))
    enabled = client.post("/plugins/enable", json={"id": plugin_id, "reason": "test_enable", "actor": _PLUGIN_ACTOR})
    assert enabled.status_code == 200
    assert enabled.json()["ok"] is True

    bad_action = client.post("/plugins/run", json={"id": plugin_id, "action": "not-supported", "input": "hello"})
    assert bad_action.status_code == 200
    bad_action_body = bad_action.json()
    assert bad_action_body["ok"] is False
    assert bad_action_body["error"] == "unsupported_action"
    assert "run" in bad_action_body["supported_actions"]

    exported = client.get(f"/plugins/tools/export?format=csv&plugin_id={plugin_id}")
    assert exported.status_code == 200
    assert "plugin_id" in exported.text
    assert plugin_id in exported.text


def test_plugins_capability_catalog_readback(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Catalog Plugin",
            "description": "Capability catalog readback coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": _forge_promotion_meta("capability_catalog"),
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    catalog = client.get("/plugins/capabilities/catalog?limit=5000")
    assert catalog.status_code == 200
    body = catalog.json()
    assert body["ok"] is True
    assert body["total"] >= 1
    assert body["summary"]["total"] >= 1
    assert body["summary"]["tested_count"] >= 1
    assert body["summary"]["documented_count"] >= 1
    assert body["catalog"]["total_plugins"] >= 1
    assert body["catalog"]["total_tools"] >= 1
    assert Path(str(body["catalog"]["path"])).exists()
    assert body["coherence"]["total"] >= 1
    assert body["pack_readiness"]["stage"] == "Stage 17 / Capability Economy"
    assert body["pack_readiness"]["governance"]["read_only"] is True
    assert not any(gap["capability"] == plugin_id for gap in body["coherence"]["lineage_gaps"])
    assert not any(gap["capability"] == plugin_id for gap in body["coherence"]["validation_lineage_gaps"])

    entry = next(item for item in body["items"] if item["capability"] == plugin_id)
    assert entry["status"] == "staged"
    assert entry["risk_tier"] == "normal"
    assert entry["proposal_id"] == built_body["proposal_id"]
    assert entry["quality"]["tests"] == ["tests/test_api_plugins.py::capability_catalog"]
    assert entry["quality"]["docs"] == ["README.md"]
    assert entry["metadata"]["validation_receipt_id"] == built_body["validation_receipt_id"]
    assert entry["metadata"]["proposal_evidence"] == ["mission.capability_catalog.repeat"]

    filtered = client.get("/plugins/capabilities/catalog?status=staged&risk_tier=normal&limit=5000")
    assert filtered.status_code == 200
    filtered_body = filtered.json()
    assert filtered_body["ok"] is True
    filtered_ids = {str(item.get("capability")) for item in filtered_body["items"]}
    assert plugin_id in filtered_ids
    assert filtered_body["filters"] == {"status": "staged", "risk_tier": "normal", "source": ""}


def test_plugins_capability_catalog_projects_stage17_pack_readiness(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    meta = {
        **_forge_promotion_meta("capability_pack"),
        "pack_id": "ops.capability_pack",
        "pack_version": "1.0.0",
        "pack_name": "Ops Capability Pack",
        "promotion_rules": ["validated_before_promotion"],
        "pack_governance": {
            "risk_tier": "normal",
            "approval_required": False,
            "scope": "build_dev",
        },
    }
    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Pack Plugin",
            "description": "Stage 17 pack readiness coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": meta,
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    catalog = client.get("/plugins/capabilities/catalog?limit=5000")
    assert catalog.status_code == 200
    body = catalog.json()
    assert body["ok"] is True

    entry = next(item for item in body["items"] if item["capability"] == plugin_id)
    assert entry["metadata"]["pack_id"] == "ops.capability_pack"
    assert entry["metadata"]["pack_version"] == "1.0.0"
    assert entry["metadata"]["promotion_rules"] == ["validated_before_promotion"]
    assert entry["metadata"]["pack_governance"]["scope"] == "build_dev"

    readiness = body["pack_readiness"]
    assert readiness["pack_total"] >= 1
    assert readiness["ready_pack_count"] >= 1
    assert readiness["unpacked_capabilities_truncated"] in {True, False}
    pack = next(item for item in readiness["packs"] if item["pack_id"] == "ops.capability_pack")
    assert pack["pack_id"] == "ops.capability_pack"
    assert pack["pack_version"] == "1.0.0"
    assert pack["pack_name"] == "Ops Capability Pack"
    assert pack["ready"] is True
    assert pack["governance_travels"] is True
    assert pack["promotion_rules_ready"] is True
    assert pack["quality_standards_ready"] is True
    assert pack["capabilities"][0]["capability"] == plugin_id


def test_plugins_capability_pack_metadata_receipt_is_written_and_projected(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Metadata Receipt Plugin",
            "description": "Stage 17 pack metadata receipt coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": _forge_promotion_meta("capability_metadata_receipt"),
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    before = client.get("/plugins/capabilities/catalog?limit=5000").json()
    before_entry = next(item for item in before["items"] if item["capability"] == plugin_id)
    assert before_entry["metadata"]["pack_metadata_source"] == "legacy_generated_projection"

    recorded = client.post(
        "/plugins/capabilities/packs/metadata/receipts",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "record stage17 metadata receipt",
            "pack_id": "ops.metadata_receipt_pack",
            "pack_version": "1.0.0",
            "pack_name": "Ops Metadata Receipt Pack",
            "capability_ids": [plugin_id],
            "promotion_rules": ["metadata_receipt_before_promotion"],
            "pack_governance": {
                "risk_tier": "normal",
                "scope": "build_dev",
                "requires_validation_receipt": True,
            },
        },
    )

    assert recorded.status_code == 200
    recorded_body = recorded.json()
    assert recorded_body["ok"] is True
    assert recorded_body["status"] == "recorded"
    assert recorded_body["capability_count"] == 1
    assert recorded_body["governance"]["writes_registry_metadata"] is True
    assert recorded_body["governance"]["promotion_authority"] is False
    assert recorded_body["governance"]["execution_authority"] is False
    receipt = recorded_body["receipt"]
    assert receipt["kind"] == "plugin.capability_pack.metadata_receipt"
    assert receipt["pack_id"] == "ops.metadata_receipt_pack"
    assert receipt["capability_ids"] == [plugin_id]
    assert Path(str(recorded_body["receipt_path"])).exists()

    catalog = client.get("/plugins/capabilities/catalog?limit=5000")
    assert catalog.status_code == 200
    body = catalog.json()
    entry = next(item for item in body["items"] if item["capability"] == plugin_id)
    assert entry["metadata"]["pack_id"] == "ops.metadata_receipt_pack"
    assert entry["metadata"]["pack_version"] == "1.0.0"
    assert entry["metadata"]["pack_metadata_source"] == "metadata_receipt"
    assert entry["metadata"]["pack_metadata_receipt_id"] == recorded_body["receipt_id"]
    assert entry["metadata"]["pack_metadata_receipt_path"] == recorded_body["receipt_path"]
    assert entry["metadata"]["promotion_rules"] == ["metadata_receipt_before_promotion"]
    assert entry["metadata"]["pack_governance"]["requires_validation_receipt"] is True

    pack = next(item for item in body["pack_readiness"]["packs"] if item["pack_id"] == "ops.metadata_receipt_pack")
    assert pack["ready"] is True
    assert pack["projected_metadata"] is False
    assert pack["metadata_receipts_ready"] is True

    readback = client.get("/plugins/capabilities/packs/metadata/receipts?limit=10")
    assert readback.status_code == 200
    readback_body = readback.json()
    assert readback_body["ok"] is True
    assert readback_body["governance"]["read_only"] is True
    assert any(item["receipt_id"] == recorded_body["receipt_id"] for item in readback_body["items"])


def test_plugins_capability_pack_migration_plan_projects_review_candidates(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Migration Plan Plugin",
            "description": "Stage 17 migration plan coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": _forge_promotion_meta("capability_migration_plan"),
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    response = client.get("/plugins/capabilities/packs/migration/plan")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "plugin.capability_pack.migration_plan"
    assert body["stage"] == "Stage 17 / Capability Economy"
    assert body["status"] == "ready_for_metadata_receipt_review"
    assert body["candidate_total"] >= 1
    assert body["write_route"] == "/plugins/capabilities/packs/metadata/receipts"
    assert body["read_route"] == "/plugins/capabilities/packs/metadata/receipts"
    assert body["governance"]["read_only"] is True
    assert body["governance"]["does_not_write_receipts"] is True
    assert body["governance"]["does_not_mutate_registry"] is True
    assert body["next_smallest_truthful_gap"] == "stage17_capability_pack_metadata_receipt_operator_review"

    candidate = next(
        item
        for item in body["candidates"]
        if plugin_id in item["capability_ids_sample"]
        or (item["capability_ids_truncated"] and item["pack_id"].startswith("legacy.generated."))
    )
    assert "pack_metadata_receipt_missing" in candidate["blockers"]
    assert candidate["write_route"] == "/plugins/capabilities/packs/metadata/receipts"
    assert candidate["requires_explicit_capability_id_selection"] is True
    assert candidate["suggested_pack_governance"]["promotion_authority"] is False
    assert candidate["suggested_pack_governance"]["execution_authority"] is False


def test_plugins_capability_pack_metadata_receipts_bulk_from_migration_plan(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    built = client.post(
        "/plugins/build",
        json={
            "name": "Bulk Migration Plan Plugin",
            "description": "Stage 17 bulk metadata receipt coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": _forge_promotion_meta("bulk_migration_plan"),
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    plan = client.get("/plugins/capabilities/packs/migration/plan").json()
    candidate = next(item for item in plan["candidates"] if plugin_id in item["capability_ids_sample"])

    recorded = client.post(
        "/plugins/capabilities/packs/metadata/receipts/bulk-from-plan",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "record reviewed migration plan candidates",
            "pack_ids": [candidate["pack_id"]],
        },
    )

    assert recorded.status_code == 200
    recorded_body = recorded.json()
    assert recorded_body["ok"] is True
    assert recorded_body["status"] == "recorded"
    assert recorded_body["recorded_pack_count"] == 1
    assert recorded_body["recorded_capability_count"] == candidate["capability_count"]
    assert recorded_body["remaining_candidate_total"] < plan["candidate_total"]
    assert recorded_body["governance"]["writes_registry_metadata"] is True
    assert recorded_body["governance"]["writes_receipts"] is True
    assert recorded_body["governance"]["promotion_authority"] is False
    assert recorded_body["governance"]["execution_authority"] is False
    receipt_ref = recorded_body["recorded"][0]
    assert receipt_ref["pack_id"] == candidate["pack_id"]
    from francis.api.routes import plugins

    assert plugins.os.path.exists(plugins._filesystem_path(Path(str(receipt_ref["receipt_path"]))))

    catalog = client.get("/plugins/capabilities/catalog?limit=5000").json()
    entry = next(item for item in catalog["items"] if item["capability"] == plugin_id)
    assert entry["metadata"]["pack_id"] == candidate["pack_id"]
    assert entry["metadata"]["pack_version"] == candidate["pack_version"]
    assert entry["metadata"]["pack_metadata_source"] == "metadata_receipt"
    assert entry["metadata"]["pack_metadata_receipt_id"] == receipt_ref["receipt_id"]
    assert entry["metadata"]["promotion_rules"] == candidate["suggested_promotion_rules"]
    assert entry["metadata"]["pack_governance"]["operator_review_required"] is True

    receipts = client.get("/plugins/capabilities/packs/metadata/receipts?limit=10").json()
    receipt = next(item for item in receipts["items"] if item["receipt_id"] == receipt_ref["receipt_id"])
    assert receipt["governance"]["route"] == "/plugins/capabilities/packs/metadata/receipts/bulk-from-plan"
    assert receipt["expanded_from_migration_plan"] is False
    assert receipt["metadata_context"]["bulk_from_migration_plan"] is True


def test_plugins_capability_pack_quality_standards_projects_pack_evidence(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    meta = {
        **_forge_promotion_meta("capability_quality_standards"),
        "pack_id": "ops.quality_standards",
        "pack_version": "1.0.0",
        "pack_name": "Ops Quality Standards Pack",
        "known_limits": ["local_only"],
    }
    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Quality Standards Plugin",
            "description": "Stage 17 quality standards coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": meta,
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    response = client.get("/plugins/capabilities/packs/quality/standards")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "plugin.capability_pack.quality_standards"
    assert body["stage"] == "Stage 17 / Capability Economy"
    assert body["standards"]["tests_required"] is True
    assert body["standards"]["docs_required"] is True
    assert body["standards"]["validation_receipts_required_for_generated"] is True
    assert body["governance"]["read_only"] is True
    assert body["governance"]["does_not_promote_capabilities"] is True

    pack = next(item for item in body["packs"] if item["pack_id"] == "ops.quality_standards")
    assert pack["ready"] is True
    assert pack["blockers"] == []
    assert pack["tested_count"] == 1
    assert pack["documented_count"] == 1
    assert pack["validation_receipt_count"] == 1
    assert pack["proposal_lineage_count"] == 1
    assert pack["known_limits_count"] == 1
    assert pack["failing_capabilities_sample"] == []
    assert all(item["capability"] != plugin_id for item in pack["failing_capabilities_sample"])


def test_plugins_capability_pack_quality_tests_projects_read_only_test_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    meta = {
        **_forge_promotion_meta("capability_quality_tests"),
        "tests": [
            "tests/test_api_plugins.py::test_plugins_capability_pack_quality_tests_projects_read_only_test_evidence"
        ],
        "pack_id": "ops.quality_tests",
        "pack_version": "1.0.0",
        "pack_name": "Ops Quality Tests Pack",
    }
    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Quality Tests Plugin",
            "description": "Stage 17 quality tests coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": meta,
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    response = client.get("/plugins/capabilities/packs/quality/tests")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "plugin.capability_pack.quality_tests"
    assert body["stage"] == "Stage 17 / Capability Economy"
    assert body["requirements"]["declared_tests_required"] is True
    assert body["requirements"]["test_paths_must_exist"] is True
    assert body["requirements"]["test_contents_not_read"] is True
    assert body["governance"]["read_only"] is True
    assert body["governance"]["does_not_read_test_contents"] is True
    assert body["governance"]["does_not_write_receipts"] is True
    assert body["governance"]["does_not_mutate_registry"] is True
    assert body["governance"]["does_not_promote_capabilities"] is True
    assert body["governance"]["promotion_authority"] is False
    assert body["available_test_path_count"] > 0

    pack = next(item for item in body["packs"] if item["pack_id"] == "ops.quality_tests")
    assert pack["ready"] is True
    assert pack["blockers"] == []
    assert pack["tested_count"] == 1
    assert pack["declared_test_reference_count"] == 1
    assert pack["existing_test_reference_count"] == 1
    assert pack["missing_test_reference_count"] == 0
    assert pack["invalid_test_reference_count"] == 0
    assert pack["test_files"] == ["tests/test_api_plugins.py"]
    assert all(item["capability"] != plugin_id for item in pack["failing_capabilities_sample"])


def test_plugins_capability_pack_quality_docs_projects_read_only_doc_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    meta = {
        **_forge_promotion_meta("capability_quality_docs"),
        "docs": ["README.md#current-build-posture"],
        "pack_id": "ops.quality_docs",
        "pack_version": "1.0.0",
        "pack_name": "Ops Quality Docs Pack",
    }
    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Quality Docs Plugin",
            "description": "Stage 17 quality docs coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": meta,
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    response = client.get("/plugins/capabilities/packs/quality/docs")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "plugin.capability_pack.quality_docs"
    assert body["stage"] == "Stage 17 / Capability Economy"
    assert body["requirements"]["declared_docs_required"] is True
    assert body["requirements"]["doc_paths_must_exist"] is True
    assert body["requirements"]["doc_contents_not_read"] is True
    assert body["governance"]["read_only"] is True
    assert body["governance"]["does_not_read_doc_contents"] is True
    assert body["governance"]["does_not_write_receipts"] is True
    assert body["governance"]["does_not_mutate_registry"] is True
    assert body["governance"]["does_not_promote_capabilities"] is True
    assert body["governance"]["promotion_authority"] is False
    assert body["available_doc_path_count"] > 0

    pack = next(item for item in body["packs"] if item["pack_id"] == "ops.quality_docs")
    assert pack["ready"] is True
    assert pack["blockers"] == []
    assert pack["documented_count"] == 1
    assert pack["declared_doc_reference_count"] == 1
    assert pack["existing_doc_reference_count"] == 1
    assert pack["missing_doc_reference_count"] == 0
    assert pack["invalid_doc_reference_count"] == 0
    assert pack["doc_files"] == ["README.md"]
    assert all(item["capability"] != plugin_id for item in pack["failing_capabilities_sample"])


def test_plugins_capability_pack_validation_receipts_projects_read_only_receipt_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    meta = {
        **_forge_promotion_meta("capability_validation_receipts"),
        "pack_id": "ops.validation_receipts",
        "pack_version": "1.0.0",
        "pack_name": "Ops Validation Receipts Pack",
    }
    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Validation Receipts Plugin",
            "description": "Stage 17 validation receipt coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": meta,
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    response = client.get("/plugins/capabilities/packs/validation/receipts")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "plugin.capability_pack.validation_receipts"
    assert body["stage"] == "Stage 17 / Capability Economy"
    assert body["requirements"]["validation_receipts_required_for_generated"] is True
    assert body["requirements"]["validation_receipt_paths_must_stay_within_plugin_validations"] is True
    assert body["requirements"]["validation_receipt_bodies_not_read"] is True
    assert body["governance"]["read_only"] is True
    assert body["governance"]["does_not_read_receipt_bodies"] is True
    assert body["governance"]["does_not_write_receipts"] is True
    assert body["governance"]["does_not_mutate_registry"] is True
    assert body["governance"]["does_not_promote_capabilities"] is True
    assert body["governance"]["promotion_authority"] is False
    assert body["available_validation_receipt_count"] >= 1

    pack = next(item for item in body["packs"] if item["pack_id"] == "ops.validation_receipts")
    assert pack["ready"] is True
    assert pack["blockers"] == []
    assert pack["requires_validation_receipt_count"] == 1
    assert pack["validation_receipt_present_count"] == 1
    assert pack["validation_receipt_missing_count"] == 0
    assert pack["validation_receipt_not_found_count"] == 0
    assert pack["validation_receipt_invalid_count"] == 0
    assert pack["validation_receipt_ids"] == [built_body["validation_receipt_id"]]
    assert all(item["capability"] != plugin_id for item in pack["failing_capabilities_sample"])


def test_plugins_capability_pack_lineage_projects_read_only_proposal_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    meta = {
        **_forge_promotion_meta("capability_lineage"),
        "pack_id": "ops.lineage",
        "pack_version": "1.0.0",
        "pack_name": "Ops Lineage Pack",
    }
    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Lineage Plugin",
            "description": "Stage 17 proposal lineage coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": meta,
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    response = client.get("/plugins/capabilities/packs/lineage/proposals")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "plugin.capability_pack.lineage.proposals"
    assert body["stage"] == "Stage 17 / Capability Economy"
    assert body["requirements"]["proposal_lineage_required_for_staged"] is True
    assert body["requirements"]["proposal_paths_must_stay_within_plugin_proposals"] is True
    assert body["requirements"]["proposal_bodies_not_read"] is True
    assert body["requirements"]["operator_review_remains_separate_gate"] is True
    assert body["governance"]["read_only"] is True
    assert body["governance"]["does_not_read_proposal_bodies"] is True
    assert body["governance"]["does_not_write_proposals"] is True
    assert body["governance"]["does_not_write_receipts"] is True
    assert body["governance"]["does_not_mutate_registry"] is True
    assert body["governance"]["does_not_approve_proposals"] is True
    assert body["governance"]["does_not_promote_capabilities"] is True
    assert body["governance"]["proposal_approval_authority"] is False
    assert body["available_proposal_count"] >= 1

    pack = next(item for item in body["packs"] if item["pack_id"] == "ops.lineage")
    assert pack["ready"] is True
    assert pack["blockers"] == []
    assert pack["requires_proposal_lineage_count"] == 1
    assert pack["proposal_lineage_present_count"] == 1
    assert pack["proposal_id_missing_count"] == 0
    assert pack["proposal_not_found_count"] == 0
    assert pack["proposal_invalid_count"] == 0
    assert pack["proposal_ids"] == [built_body["proposal_id"]]
    assert all(item["capability"] != plugin_id for item in pack["failing_capabilities_sample"])


def test_plugins_capability_pack_quality_evidence_remediation_projects_truthful_read_only_plan(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    client = TestClient(create_app())
    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Quality Evidence Remediation Plugin",
            "description": "Stage 17 quality evidence remediation coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": _forge_promotion_meta("capability_quality_evidence_remediation"),
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    plan = client.get("/plugins/capabilities/packs/migration/plan").json()
    candidate = next(item for item in plan["candidates"] if plugin_id in item["capability_ids_sample"])
    recorded = client.post(
        "/plugins/capabilities/packs/metadata/receipts/bulk-from-plan",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "record reviewed migration plan candidate before quality remediation readback",
            "pack_ids": [candidate["pack_id"]],
        },
    )
    assert recorded.status_code == 200
    recorded_body = recorded.json()
    assert recorded_body["ok"] is True
    pack_id = str(recorded_body["recorded"][0]["pack_id"])
    pack_version = str(recorded_body["recorded"][0]["pack_version"])

    registry = plugins._load_registry()
    plugin = plugins._read_plugin(registry, plugin_id)
    assert plugin is not None
    meta = dict(plugin.get("meta") or {})
    for key in (
        "tests",
        "test_refs",
        "docs",
        "documentation",
        "proposal_id",
        "forge_proposal_id",
        "proposal_path",
        "validation_receipt_id",
        "validation_receipt_path",
    ):
        meta.pop(key, None)
    plugin["meta"] = meta
    plugins._write_plugin(registry, plugins._normalize_plugin_record(plugin_id, plugin))
    plugins._save_registry_and_catalog(registry)

    response = client.get("/plugins/capabilities/packs/quality/evidence/remediation")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "plugin.capability_pack.quality_evidence.remediation"
    assert body["stage"] == "Stage 17 / Capability Economy"
    assert body["status"] == "blocked"
    assert body["requirements"]["read_only_remediation_plan"] is True
    assert body["requirements"]["candidate_references_do_not_claim_pack_specific_coverage"] is True
    assert body["requirements"]["validation_receipts_require_pack_specific_writer"] is True
    assert body["requirements"]["proposal_lineage_requires_explicit_reconstruction_or_link"] is True
    assert body["governance"]["read_only"] is True
    assert body["governance"]["does_not_read_test_contents"] is True
    assert body["governance"]["does_not_read_doc_contents"] is True
    assert body["governance"]["does_not_write_receipts"] is True
    assert body["governance"]["does_not_write_validation_receipts"] is True
    assert body["governance"]["does_not_write_proposals"] is True
    assert body["governance"]["does_not_mutate_registry"] is True
    assert body["governance"]["does_not_promote_capabilities"] is True
    assert body["governance"]["promotion_authority"] is False
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["memory_write"] is False
    assert body["reference_candidates"]["pack_specific_coverage_claimed"] is False
    assert body["reference_candidates"]["candidate_test_reference_count"] >= 1
    assert body["reference_candidates"]["candidate_doc_reference_count"] >= 1
    assert body["blocker_counts"]["tests_missing"] >= 1
    assert body["blocker_counts"]["docs_missing"] >= 1
    assert body["blocker_counts"]["validation_receipt_missing"] >= 1
    assert body["blocker_counts"]["proposal_id_missing"] >= 1
    assert body["quality_reference_backfill_candidate_count"] >= 1
    assert body["validation_receipt_backfill_required_count"] >= 1
    assert body["proposal_lineage_backfill_required_count"] >= 1
    assert body["next_smallest_truthful_gap"] == "stage17_capability_pack_quality_evidence_remediation_apply"

    item = next(entry for entry in body["remediation_queue"] if entry["pack_id"] == pack_id)
    assert item["pack_version"] == pack_version
    assert item["blockers"] == [
        "tests_missing",
        "docs_missing",
        "validation_receipt_missing",
        "proposal_id_missing",
    ]
    assert item["eligible_generated_or_legacy_pack"] is True
    assert item["pack_metadata_receipts_present"] is True
    assert item["quality_reference_backfill_candidate"] is True
    assert item["evidence_backfill"]["tests"]["candidate_apply_supported"] is True
    assert item["evidence_backfill"]["docs"]["candidate_apply_supported"] is True
    assert item["evidence_backfill"]["tests"]["claim_scope"] == "candidate_reference_only_not_pack_specific_proof"
    assert item["evidence_backfill"]["docs"]["claim_scope"] == "candidate_reference_only_not_pack_specific_proof"
    assert item["evidence_backfill"]["validation_receipt"]["candidate_apply_supported"] is False
    assert item["evidence_backfill"]["forge_proposal"]["candidate_apply_supported"] is False
    assert item["recommended_next_action"] == "review_quality_reference_backfill_candidates"
    assert item["would_mutate"] is False
    assert item["writes_registry_metadata"] is False
    assert item["writes_receipts"] is False

    post_readback = plugins._read_plugin(plugins._load_registry(), plugin_id)
    assert post_readback is not None
    post_meta = dict(post_readback.get("meta") or {})
    assert "tests" not in post_meta
    assert "docs" not in post_meta
    assert "proposal_id" not in post_meta
    assert "validation_receipt_id" not in post_meta


def test_plugins_capability_pack_promotion_receipts_projects_read_only_receipt_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path.parent / "promotion_receipts_data"
    shutil.rmtree(data_root, ignore_errors=True)
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    meta = {
        **_forge_promotion_meta("capability_promotion_receipts"),
        "pack_id": "ops.promotion_receipts",
        "pack_version": "1.0.0",
        "pack_name": "Ops Promotion Receipts Pack",
    }
    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Promotion Receipts Plugin",
            "description": "Stage 17 promotion receipt coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": meta,
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])
    proposal = built_body["proposal"]
    assert Path(str(proposal["path"])).exists()
    _approve_forge_proposal(client, str(proposal["proposal_id"]))

    enabled = client.post(
        "/plugins/enable",
        json={
            "id": plugin_id,
            "reason": "test promotion receipt readback",
            "actor": _PLUGIN_ACTOR,
        },
    )
    assert enabled.status_code == 200
    enabled_body = enabled.json()
    assert enabled_body["ok"] is True
    assert enabled_body["promotion_status"] == "promoted"

    response = client.get("/plugins/capabilities/packs/promotion/receipts")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "plugin.capability_pack.promotion_receipts"
    assert body["stage"] == "Stage 17 / Capability Economy"
    assert body["requirements"]["promotion_receipts_required_for_promoted"] is True
    assert body["requirements"]["promotion_receipt_paths_must_stay_within_plugin_promotions"] is True
    assert body["requirements"]["promotion_receipt_bodies_not_read"] is True
    assert body["requirements"]["promotion_decisions_remain_separate_governed_actions"] is True
    assert body["governance"]["read_only"] is True
    assert body["governance"]["does_not_read_receipt_bodies"] is True
    assert body["governance"]["does_not_write_receipts"] is True
    assert body["governance"]["does_not_mutate_registry"] is True
    assert body["governance"]["does_not_promote_capabilities"] is True
    assert body["governance"]["promotion_authority"] is False
    assert body["available_promotion_receipt_count"] >= 1

    pack = next(item for item in body["packs"] if item["pack_id"] == "ops.promotion_receipts")
    assert pack["ready"] is True
    assert pack["blockers"] == []
    assert pack["requires_promotion_receipt_count"] == 1
    assert pack["promotion_receipt_present_count"] == 1
    assert pack["promotion_receipt_missing_count"] == 0
    assert pack["promotion_receipt_not_found_count"] == 0
    assert pack["promotion_receipt_invalid_count"] == 0
    assert pack["promotion_receipt_ids"] == [enabled_body["promotion_receipt_id"]]
    assert all(item["capability"] != plugin_id for item in pack["failing_capabilities_sample"])


def test_plugins_capability_pack_promotion_rules_project_governed_rule_readiness(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    meta = {
        **_forge_promotion_meta("capability_promotion_rules"),
        "pack_id": "ops.promotion_rules",
        "pack_version": "1.0.0",
        "pack_name": "Ops Promotion Rules Pack",
        "promotion_rules": [
            "metadata_receipt_before_promotion",
            "quality_standards_before_promotion",
            "operator_review_before_promotion",
        ],
        "pack_governance": {
            "risk_tier": "normal",
            "scope": "build_dev",
            "operator_review_required": True,
        },
    }
    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Promotion Rules Plugin",
            "description": "Stage 17 promotion rules coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": meta,
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    response = client.get("/plugins/capabilities/packs/promotion/rules")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "plugin.capability_pack.promotion_rules"
    assert body["stage"] == "Stage 17 / Capability Economy"
    assert body["requirements"]["explicit_promotion_rules"] is True
    assert body["requirements"]["no_silent_promotion"] is True
    assert body["governance"]["read_only"] is True
    assert body["governance"]["does_not_write_receipts"] is True
    assert body["governance"]["does_not_mutate_registry"] is True
    assert body["governance"]["does_not_promote_capabilities"] is True
    assert body["governance"]["promotion_authority"] is False
    assert body["governance"]["execution_authority"] is False

    pack = next(item for item in body["packs"] if item["pack_id"] == "ops.promotion_rules")
    assert pack["ready"] is True
    assert pack["blockers"] == []
    assert pack["explicit_rules_ready"] is True
    assert pack["metadata_receipts_ready"] is True
    assert pack["quality_standards_ready"] is True
    assert pack["governance_travels"] is True
    assert pack["operator_review_declared"] is True
    assert pack["promoted_capabilities_have_receipts"] is True
    assert "operator_review_before_promotion" in pack["promotion_rules"]
    assert all(item["capability"] != plugin_id for item in pack["failing_capabilities_sample"])


def test_plugins_capability_pack_promotion_rule_remediation_projects_read_only_backlog(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    meta = {
        **_forge_promotion_meta("capability_promotion_rule_remediation"),
        "pack_id": "ops.rule_remediation",
        "pack_version": "1.0.0",
        "pack_name": "Ops Rule Remediation Pack",
        "promotion_rules": ["metadata_receipt_before_promotion"],
    }
    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Rule Remediation Plugin",
            "description": "Stage 17 promotion rule remediation coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": meta,
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True

    response = client.get("/plugins/capabilities/packs/promotion/rules/remediation")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "plugin.capability_pack.promotion_rules.remediation"
    assert body["stage"] == "Stage 17 / Capability Economy"
    assert body["status"] == "blocked"
    assert body["requirements"]["read_only_remediation_queue"] is True
    assert body["requirements"]["canonical_rules_declared_before_promotion"] is True
    assert body["requirements"]["remediation_does_not_write_registry"] is True
    assert body["governance"]["read_only"] is True
    assert body["governance"]["operator_facing"] is True
    assert body["governance"]["does_not_write_receipts"] is True
    assert body["governance"]["does_not_mutate_registry"] is True
    assert body["governance"]["does_not_promote_capabilities"] is True
    assert body["governance"]["promotion_authority"] is False
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["memory_write"] is False

    item = next(entry for entry in body["remediation_queue"] if entry["pack_id"] == "ops.rule_remediation")
    assert item["first_action"] == "declare_canonical_promotion_rules"
    assert item["missing_promotion_rules"] == [
        "quality_standards_before_promotion",
        "operator_review_before_promotion",
    ]
    assert "operator_review_required" in item["missing_governance_fields"]
    assert "canonical_promotion_rules_missing" in item["blockers"]
    assert item["failing_capabilities_sample"][0]["gaps"] == ["pack_governance_missing"]
    assert body["next_smallest_truthful_gap"] == "stage17_capability_pack_promotion_rule_backlog_execution"


def test_plugins_capability_pack_promotion_rule_remediation_apply_writes_metadata_receipt(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    client = TestClient(create_app())
    packs = [
        {
            "pack_id": "ops.rule_remediation_apply",
            "plugin_suffix": "capability_promotion_rule_remediation_apply",
            "name": "Capability Rule Remediation Apply Plugin",
            "pack_name": "Ops Rule Remediation Apply Pack",
        },
        {
            "pack_id": "ops.rule_remediation_apply_two",
            "plugin_suffix": "capability_promotion_rule_remediation_apply_two",
            "name": "Capability Rule Remediation Apply Two Plugin",
            "pack_name": "Ops Rule Remediation Apply Two Pack",
        },
    ]
    plugin_ids: dict[str, str] = {}
    for pack in packs:
        meta = {
            **_forge_promotion_meta(str(pack["plugin_suffix"])),
            "pack_id": pack["pack_id"],
            "pack_version": "1.0.0",
            "pack_name": pack["pack_name"],
            "promotion_rules": ["metadata_receipt_before_promotion"],
        }
        built = client.post(
            "/plugins/build",
            json={
                "name": pack["name"],
                "description": "Stage 17 promotion rule remediation apply coverage",
                "actor": _PLUGIN_ACTOR,
                "meta": meta,
            },
        )
        assert built.status_code == 200
        built_body = built.json()
        assert built_body["ok"] is True
        plugin_ids[str(pack["pack_id"])] = str(built_body["plugin_id"])

    before = client.get("/plugins/capabilities/packs/promotion/rules/remediation").json()
    for pack in packs:
        before_item = next(item for item in before["remediation_queue"] if item["pack_id"] == pack["pack_id"])
        assert before_item["missing_promotion_rules"] == [
            "quality_standards_before_promotion",
            "operator_review_before_promotion",
        ]
        assert before_item["missing_governance_fields"] == ["pack_governance", "operator_review_required"]

    applied = client.post(
        "/plugins/capabilities/packs/promotion/rules/remediation/apply",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "apply reviewed promotion rule remediation",
            "pack_ids": [pack["pack_id"] for pack in packs],
            "max_pack_count": 2,
        },
    )

    assert applied.status_code == 200
    applied_body = applied.json()
    assert applied_body["ok"] is True
    assert applied_body["applied"] is True
    assert applied_body["status"] == "recorded"
    assert applied_body["planned_pack_count"] == 2
    assert applied_body["recorded_pack_count"] == 2
    assert applied_body["recorded_capability_count"] == 2
    assert applied_body["remaining_remediation_queue"] == []
    assert applied_body["governance"]["writes_registry_metadata"] is True
    assert applied_body["governance"]["writes_receipts"] is True
    assert applied_body["governance"]["metadata_rule_governance_remediation_only"] is True
    assert applied_body["governance"]["does_not_promote_capabilities"] is True
    assert applied_body["governance"]["does_not_enable_capabilities"] is True
    assert applied_body["governance"]["does_not_execute_capabilities"] is True
    assert applied_body["governance"]["promotion_authority"] is False
    assert applied_body["governance"]["execution_authority"] is False
    recorded_by_pack = {item["pack_id"]: item for item in applied_body["recorded"]}
    assert sorted(recorded_by_pack) == sorted(pack["pack_id"] for pack in packs)
    for receipt_ref in recorded_by_pack.values():
        assert receipt_ref["metadata_blockers"] == ["pack_governance_missing", "canonical_promotion_rules_missing"]
        assert receipt_ref["receipt_status"] == "recorded"
        assert plugins.os.path.exists(plugins._filesystem_path(Path(str(receipt_ref["receipt_path"]))))

    catalog = client.get("/plugins/capabilities/catalog?limit=5000").json()
    metadata_by_pack = {}
    for pack in packs:
        entry = next(item for item in catalog["items"] if item["capability"] == plugin_ids[str(pack["pack_id"])])
        metadata = entry["metadata"]
        metadata_by_pack[str(pack["pack_id"])] = metadata
        assert metadata["pack_id"] == pack["pack_id"]
        assert metadata["pack_version"] == "1.0.0"
        assert metadata["pack_metadata_source"] == "metadata_receipt"
        assert metadata["pack_metadata_receipt_id"] == recorded_by_pack[str(pack["pack_id"])]["receipt_id"]
        assert metadata["promotion_rules"] == [
            "metadata_receipt_before_promotion",
            "quality_standards_before_promotion",
            "operator_review_before_promotion",
        ]
        assert metadata["pack_governance"]["operator_review_required"] is True
        assert metadata["pack_governance"]["promotion_authority"] is False
        assert metadata["pack_governance"]["execution_authority"] is False
        assert metadata["pack_governance"]["memory_write"] is False

    receipts = client.get("/plugins/capabilities/packs/metadata/receipts?limit=10").json()
    receipts_by_id = {item["receipt_id"]: item for item in receipts["items"]}
    for pack in packs:
        receipt_ref = recorded_by_pack[str(pack["pack_id"])]
        receipt = receipts_by_id[receipt_ref["receipt_id"]]
        metadata = metadata_by_pack[str(pack["pack_id"])]
        assert receipt["governance"]["route"] == "/plugins/capabilities/packs/promotion/rules/remediation/apply"
        assert receipt["promotion_rules"] == metadata["promotion_rules"]
        assert receipt["pack_governance"]["operator_review_required"] is True
        assert receipt["metadata_context"]["promotion_rule_remediation_apply"] is True
        assert receipt["metadata_context"]["bulk_registry_write"] is True
        assert receipt["metadata_context"]["applied_metadata_blockers"] == [
            "pack_governance_missing",
            "canonical_promotion_rules_missing",
        ]

    after = client.get("/plugins/capabilities/packs/promotion/rules/remediation").json()
    assert all(item["pack_id"] not in recorded_by_pack for item in after["remediation_queue"])


def test_plugins_capability_pack_operator_review_projects_read_only_review_queue(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    meta = {
        **_forge_promotion_meta("capability_operator_review"),
        "pack_id": "ops.operator_review",
        "pack_version": "1.0.0",
        "pack_name": "Ops Operator Review Pack",
        "promotion_rules": [
            "metadata_receipt_before_promotion",
            "quality_standards_before_promotion",
            "operator_review_before_promotion",
        ],
        "pack_governance": {
            "risk_tier": "normal",
            "scope": "build_dev",
            "operator_review_required": True,
        },
    }
    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Operator Review Plugin",
            "description": "Stage 17 operator review coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": meta,
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    response = client.get("/plugins/capabilities/packs/operator/review")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "plugin.capability_pack.operator_review"
    assert body["stage"] == "Stage 17 / Capability Economy"
    assert body["requirements"]["operator_review_before_promotion_required"] is True
    assert body["requirements"]["review_decision_remains_separate_governed_action"] is True
    assert body["decision_routes"]["proposal_review_route"] == "/forge/proposals/decision"
    assert (
        body["decision_routes"]["pack_review_decision_route"] == "/plugins/capabilities/packs/operator/review/decisions"
    )
    assert (
        body["decision_routes"]["pack_review_decision_readback_route"]
        == "/plugins/capabilities/packs/operator/review/decisions"
    )
    assert body["decision_routes"]["promotion_route_after_review"] == "/plugins/enable"
    assert body["governance"]["read_only"] is True
    assert body["governance"]["operator_facing"] is True
    assert body["governance"]["does_not_read_proposal_bodies"] is True
    assert body["governance"]["does_not_read_receipt_bodies"] is True
    assert body["governance"]["does_not_write_receipts"] is True
    assert body["governance"]["does_not_mutate_registry"] is True
    assert body["governance"]["does_not_approve_proposals"] is True
    assert body["governance"]["does_not_promote_capabilities"] is True
    assert body["governance"]["promotion_authority"] is False
    assert body["governance"]["execution_authority"] is False
    assert body["review_queue_count"] >= 1

    pack = next(item for item in body["packs"] if item["pack_id"] == "ops.operator_review")
    assert pack["status"] == "ready_for_operator_review"
    assert pack["operator_review_ready"] is True
    assert pack["decision_required"] is True
    assert pack["decision_kind"] == "staged_pack_promotion_review"
    assert pack["blockers"] == []
    assert pack["staged_capability_count"] == 1
    assert pack["promoted_capability_count"] == 0
    assert pack["operator_review_rule_declared"] is True
    assert pack["operator_review_governance_declared"] is True
    assert pack["quality_evidence_ready"] is True
    assert pack["proposal_lineage_ready"] is True
    assert pack["validation_receipts_ready"] is True
    assert pack["review_items_sample"][0]["capability"] == plugin_id
    assert pack["review_items_sample"][0]["proposal_id"] == built_body["proposal_id"]
    assert pack["review_items_sample"][0]["validation_receipt_id"] == built_body["validation_receipt_id"]
    assert all(item["capability"] != plugin_id for item in pack["failing_capabilities_sample"])


def test_plugins_capability_pack_operator_review_decision_receipt_gates_pack_promotion(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    client = TestClient(create_app())
    pack_id = "ops.operator_review_decision"
    pack_version = "1.0.0"
    meta = {
        **_forge_promotion_meta("capability_operator_review_decision"),
        "pack_id": pack_id,
        "pack_version": pack_version,
        "pack_name": "Ops Operator Review Decision Pack",
        "promotion_rules": [
            "metadata_receipt_before_promotion",
            "quality_standards_before_promotion",
            "operator_review_before_promotion",
        ],
        "pack_governance": {
            "risk_tier": "normal",
            "scope": "build_dev",
            "operator_review_required": True,
        },
    }
    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Operator Review Decision Plugin",
            "description": "Stage 17 operator review decision receipt coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": meta,
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])
    _approve_forge_proposal(client, str(built_body["proposal_id"]))

    blocked = client.post(
        "/plugins/enable",
        json={
            "id": plugin_id,
            "reason": "pack promotion before pack operator review",
            "actor": _PLUGIN_ACTOR,
        },
    )
    assert blocked.status_code == 200
    blocked_body = blocked.json()
    assert blocked_body["ok"] is False
    assert blocked_body["error"] == "promotion_readiness_blocked"
    assert "pack_operator_review" in blocked_body["readiness"]["missing_requirements"]
    assert blocked_body["readiness"]["requirements"]["pack_operator_review"] is False
    assert blocked_body["readiness"]["evidence"]["pack_operator_review_status"] == "missing"

    approved = _approve_capability_pack_operator_review(
        client,
        pack_id=pack_id,
        pack_version=pack_version,
    )
    receipt = approved["receipt"]
    assert receipt["kind"] == "plugin.capability_pack.operator_review.decision_receipt"
    assert receipt["status"] == "approved"
    assert receipt["pack_id"] == pack_id
    assert receipt["pack_version"] == pack_version
    assert receipt["capability_ids"] == [plugin_id]
    assert receipt["governance"]["writes_receipt"] is True
    assert receipt["governance"]["does_not_mutate_registry"] is True
    assert receipt["governance"]["does_not_promote_capabilities"] is True
    assert receipt["governance"]["does_not_enable_capabilities"] is True
    assert receipt["governance"]["promotion_authority"] is False
    assert plugins.os.path.exists(plugins._filesystem_path(Path(str(receipt["path"]))))

    decisions = client.get(
        "/plugins/capabilities/packs/operator/review/decisions",
        params={"pack_id": pack_id, "pack_version": pack_version},
    )
    assert decisions.status_code == 200
    decisions_body = decisions.json()
    assert decisions_body["ok"] is True
    assert decisions_body["kind"] == "plugin.capability_pack.operator_review.decisions"
    assert decisions_body["governance"]["read_only"] is True
    assert decisions_body["governance"]["does_not_promote_capabilities"] is True
    assert decisions_body["items"][0]["receipt_id"] == approved["receipt_id"]

    enabled = client.post(
        "/plugins/enable",
        json={
            "id": plugin_id,
            "reason": "pack promotion after pack operator review",
            "actor": _PLUGIN_ACTOR,
        },
    )
    assert enabled.status_code == 200
    enabled_body = enabled.json()
    assert enabled_body["ok"] is True
    assert enabled_body["promotion_status"] == "promoted"
    promotion_receipt = enabled_body["promotion_receipt"]
    assert promotion_receipt["proposal_review"]["status"] == "approved"
    assert promotion_receipt["pack_operator_review"]["required"] is True
    assert promotion_receipt["pack_operator_review"]["status"] == "approved"
    assert promotion_receipt["pack_operator_review"]["receipt_id"] == approved["receipt_id"]
    assert promotion_receipt["pack_operator_review"]["pack_id"] == pack_id
    assert promotion_receipt["governance"]["explicit"] is True


def test_plugins_capability_pack_promotion_discipline_projects_pack_gate(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    pack_id = "ops.promotion_discipline"
    pack_version = "1.0.0"
    meta = {
        **_forge_promotion_meta("capability_promotion_discipline"),
        "pack_id": pack_id,
        "pack_version": pack_version,
        "pack_name": "Ops Promotion Discipline Pack",
        "promotion_rules": [
            "metadata_receipt_before_promotion",
            "quality_standards_before_promotion",
            "operator_review_before_promotion",
        ],
        "pack_governance": {
            "risk_tier": "normal",
            "scope": "build_dev",
            "operator_review_required": True,
        },
    }
    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Promotion Discipline Plugin",
            "description": "Stage 17 promotion discipline coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": meta,
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    blocked = client.get("/plugins/capabilities/packs/promotion/discipline")
    assert blocked.status_code == 200
    blocked_body = blocked.json()
    blocked_pack = next(item for item in blocked_body["packs"] if item["pack_id"] == pack_id)
    assert blocked_pack["ready"] is False
    assert "operator_review_decision_missing" in blocked_pack["blockers"]

    _approve_capability_pack_operator_review(
        client,
        pack_id=pack_id,
        pack_version=pack_version,
    )

    response = client.get("/plugins/capabilities/packs/promotion/discipline")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "plugin.capability_pack.promotion_discipline"
    assert body["stage"] == "Stage 17 / Capability Economy"
    assert body["requirements"]["explicit_promotion_rules_required"] is True
    assert body["requirements"]["mixed_pack_lifecycle_requires_explicit_discipline_readback"] is True
    assert body["governance"]["read_only"] is True
    assert body["governance"]["operator_facing"] is True
    assert body["governance"]["does_not_read_proposal_bodies"] is True
    assert body["governance"]["does_not_read_receipt_bodies"] is True
    assert body["governance"]["does_not_write_receipts"] is True
    assert body["governance"]["does_not_mutate_registry"] is True
    assert body["governance"]["does_not_promote_capabilities"] is True
    assert body["governance"]["promotion_authority"] is False
    assert body["available_proposal_count"] >= 1
    assert body["available_validation_receipt_count"] >= 1
    assert body["approved_pack_operator_review_count"] >= 1

    pack = next(item for item in body["packs"] if item["pack_id"] == pack_id)
    assert pack["ready"] is True
    assert pack["blockers"] == []
    assert pack["staged_capability_count"] == 1
    assert pack["promoted_capability_count"] == 0
    assert pack["operator_review_approved"] is True
    assert pack["promotion_rules_ready"] is True
    assert pack["pack_governance_ready"] is True
    assert pack["quality_evidence_ready"] is True
    assert pack["validation_receipts_ready"] is True
    assert pack["proposal_lineage_ready"] is True
    assert pack["promotion_receipts_ready"] is True
    assert pack["lifecycle_mixed"] is False
    assert all(item["capability"] != plugin_id for item in pack["failing_capabilities_sample"])


def test_plugins_capability_pack_metadata_receipt_expands_reviewed_migration_plan_candidate(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    built = client.post(
        "/plugins/build",
        json={
            "name": "Expandable Migration Plan Plugin",
            "description": "Stage 17 from-plan receipt expansion coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": _forge_promotion_meta("capability_migration_plan_expansion"),
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    plan = client.get("/plugins/capabilities/packs/migration/plan").json()
    candidate = next(item for item in plan["candidates"] if plugin_id in item["capability_ids_sample"])

    recorded = client.post(
        "/plugins/capabilities/packs/metadata/receipts",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "record reviewed migration plan candidate",
            "pack_id": "ops.reviewed_migration_pack",
            "pack_version": "1.0.0",
            "pack_name": "Ops Reviewed Migration Pack",
            "include_current_pack_capabilities": True,
            "source_pack_id": candidate["pack_id"],
            "source_pack_version": candidate["pack_version"],
            "promotion_rules": ["metadata_receipt_before_promotion"],
            "pack_governance": {"scope": "build_dev", "operator_review_required": True},
        },
    )

    assert recorded.status_code == 200
    recorded_body = recorded.json()
    assert recorded_body["ok"] is True
    assert recorded_body["status"] == "recorded"
    assert recorded_body["capability_count"] >= 1
    assert recorded_body["receipt"]["expanded_from_migration_plan"] is True
    assert recorded_body["receipt"]["source_pack_id"] == candidate["pack_id"]
    assert recorded_body["receipt"]["source_pack_version"] == candidate["pack_version"]

    catalog = client.get("/plugins/capabilities/catalog?limit=5000").json()
    entry = next(item for item in catalog["items"] if item["capability"] == plugin_id)
    assert entry["metadata"]["pack_id"] == "ops.reviewed_migration_pack"
    assert entry["metadata"]["pack_metadata_source"] == "metadata_receipt"
    assert entry["metadata"]["pack_metadata_receipt_id"] == recorded_body["receipt_id"]


def test_plugins_run_risk_tier_enforces_trust_and_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/risky",
            "actor": _PLUGIN_ACTOR,
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    installed_body = installed.json()
    assert installed_body["ok"] is True
    plugin_id = str(installed_body["plugin_id"])

    blocked = client.post("/plugins/run", json={"id": plugin_id, "action": "deploy", "input": {"target": "prod"}})
    assert blocked.status_code == 200
    blocked_body = blocked.json()
    assert blocked_body["ok"] is False
    assert blocked_body["error"] == "insufficient_trust"
    assert blocked_body["status"] == "blocked"
    assert blocked_body["required_trust"] == 5
    assert blocked_body["governance"]["gate"] == "trust_gate"
    assert blocked_body["governance"]["next_step"] == "raise_trust_or_reduce_risk"

    raised = client.post("/trust/set", json={"level": 6, "reason": "plugin-risk-test", "actor": "test.trust.write"})
    assert raised.status_code == 200
    assert raised.json()["ok"] is True

    pending = client.post("/plugins/run", json={"id": plugin_id, "action": "deploy", "input": {"target": "prod"}})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "pending"
    assert pending_body["governance"]["gate"] == "approvals_gate"
    assert pending_body["governance"]["approval_status"] == "pending"
    approval_id = str(pending_body["approval_id"])
    assert approval_id

    still_pending = client.post(
        "/plugins/run",
        json={"id": plugin_id, "action": "deploy", "approval_id": approval_id, "input": {"target": "prod"}},
    )
    assert still_pending.status_code == 200
    still_pending_body = still_pending.json()
    assert still_pending_body["ok"] is True
    assert still_pending_body["status"] == "pending"
    assert still_pending_body["governance"]["gate"] == "approvals_gate"
    assert still_pending_body["governance"]["approval_status"] == "pending"

    approved = client.post(
        "/approvals/decision", json={"id": approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    approved_body = approved.json()
    assert approved_body["ok"] is True
    assert approved_body["status"] == "approved"

    mismatched = client.post(
        "/plugins/run",
        json={"id": plugin_id, "action": "deploy", "approval_id": approval_id, "input": {"target": "staging"}},
    )
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["ok"] is False
    assert mismatched_body["status"] == "needs_approval"
    assert mismatched_body["error"] == "approval_payload_mismatch"
    refreshed_approval_id = str(mismatched_body["approval_id"])
    assert refreshed_approval_id
    assert refreshed_approval_id != approval_id
    assert mismatched_body["previous_approval_id"] == approval_id
    assert mismatched_body["governance"]["gate"] == "approvals_gate"
    assert mismatched_body["governance"]["next_step"] == "approve_exact_action"
    refreshed_artifact_dir = Path(str(mismatched_body["artifact_dir"]))
    assert (refreshed_artifact_dir / "request.json").exists()
    assert (refreshed_artifact_dir / "mismatch.json").exists()

    approved_refreshed = client.post(
        "/approvals/decision",
        json={"id": refreshed_approval_id, "action": "approve", "actor": "test.approvals.decision"},
    )
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    executed = client.post(
        "/plugins/run",
        json={
            "id": plugin_id,
            "action": "deploy",
            "approval_id": refreshed_approval_id,
            "input": {"target": "staging"},
        },
    )
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "ok"


def test_plugins_run_redacts_sensitive_approval_metadata(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/risky",
            "actor": _PLUGIN_ACTOR,
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    plugin_id = str(installed.json()["plugin_id"])

    raised = client.post(
        "/trust/set", json={"level": 6, "reason": "approval metadata redaction", "actor": "test.trust.write"}
    )
    assert raised.status_code == 200
    assert raised.json()["ok"] is True

    raw_key = "sk-" + ("c" * 32)
    raw_token = "ghp_" + ("d" * 36)
    raw_password = "pluginsecret123"
    pending = client.post(
        "/plugins/run",
        json={
            "id": plugin_id,
            "action": "deploy",
            "input": {"target": "prod"},
            "meta": {
                "ticket": "FR-PLUGIN",
                "api_key": raw_key,
                "nested": {"refresh_token": raw_token},
                "note": f"operator note password={raw_password}",
                "token_count": 7,
            },
        },
    )
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    approval_id = str(pending_body["approval_id"])

    approval_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    artifact_path = data_root / "artifacts" / "plugins" / "approvals" / approval_id / "request.json"
    approval_payload = json.loads(approval_path.read_text(encoding="utf-8"))
    approval_meta = approval_payload["payload"]["meta"]
    assert approval_meta["ticket"] == "FR-PLUGIN"
    assert approval_meta["api_key"] == "[REDACTED:secret]"
    assert approval_meta["nested"]["refresh_token"] == "[REDACTED:secret]"
    assert approval_meta["note"] == "operator note password=[REDACTED:secret]"
    assert approval_meta["token_count"] == 7

    artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact_payload["request"]["meta"] == approval_meta

    persisted_text = "\n".join(
        [
            approval_path.read_text(encoding="utf-8"),
            artifact_path.read_text(encoding="utf-8"),
        ]
    )
    assert raw_key not in persisted_text
    assert raw_token not in persisted_text
    assert raw_password not in persisted_text


def test_plugins_run_seals_sensitive_input_without_weakening_exact_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/risky",
            "actor": _PLUGIN_ACTOR,
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    plugin_id = str(installed.json()["plugin_id"])

    raised = client.post(
        "/trust/set", json={"level": 6, "reason": "approval input sealing", "actor": "test.trust.write"}
    )
    assert raised.status_code == 200
    assert raised.json()["ok"] is True

    raw_key = "sk-" + ("i" * 32)
    different_key = "sk-" + ("j" * 32)
    pending = client.post(
        "/plugins/run",
        json={
            "id": plugin_id,
            "action": "deploy",
            "input": {"target": "prod", "api_key": raw_key, "token_count": 3},
        },
    )
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    approval_id = str(pending_body["approval_id"])

    approval_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    artifact_path = data_root / "artifacts" / "plugins" / "approvals" / approval_id / "request.json"
    approval_payload = json.loads(approval_path.read_text(encoding="utf-8"))
    sealed_key = approval_payload["payload"]["input"]["api_key"]
    assert sealed_key["kind"] == "sealed_secret"
    assert sealed_key["redacted"] == "[REDACTED:secret]"
    assert str(sealed_key["digest"]).startswith("hmac-sha256:")
    assert approval_payload["payload"]["input"]["target"] == "prod"
    assert approval_payload["payload"]["input"]["token_count"] == 3

    artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact_text = artifact_path.read_text(encoding="utf-8")
    assert artifact_payload["request"]["input"]["api_key"] == "[REDACTED:secret]"
    assert artifact_payload["approval"]["payload"]["input"]["api_key"] == "[REDACTED:secret]"
    assert raw_key not in approval_path.read_text(encoding="utf-8")
    assert raw_key not in artifact_text
    assert "hmac-sha256:" not in artifact_text

    approved = client.post(
        "/approvals/decision", json={"id": approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    mismatched = client.post(
        "/plugins/run",
        json={
            "id": plugin_id,
            "action": "deploy",
            "approval_id": approval_id,
            "input": {"target": "prod", "api_key": different_key, "token_count": 3},
        },
    )
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["ok"] is False
    assert mismatched_body["status"] == "needs_approval"
    assert mismatched_body["error"] == "approval_payload_mismatch"
    assert str(mismatched_body["approval_id"]) != approval_id

    refreshed_approval_id = str(mismatched_body["approval_id"])
    refreshed_artifact_dir = data_root / "artifacts" / "plugins" / "approvals" / refreshed_approval_id
    refreshed_request_text = (refreshed_artifact_dir / "request.json").read_text(encoding="utf-8")
    refreshed_mismatch_text = (refreshed_artifact_dir / "mismatch.json").read_text(encoding="utf-8")
    original_mismatch_text = (
        data_root / "artifacts" / "plugins" / "approvals" / approval_id / "mismatch.json"
    ).read_text(encoding="utf-8")
    for artifact_text in (refreshed_request_text, refreshed_mismatch_text, original_mismatch_text):
        assert raw_key not in artifact_text
        assert different_key not in artifact_text
        assert "hmac-sha256:" not in artifact_text

    approved_refreshed = client.post(
        "/approvals/decision",
        json={"id": refreshed_approval_id, "action": "approve", "actor": "test.approvals.decision"},
    )
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    executed = client.post(
        "/plugins/run",
        json={
            "id": plugin_id,
            "action": "deploy",
            "approval_id": refreshed_approval_id,
            "input": {"target": "prod", "api_key": different_key, "token_count": 3},
        },
    )
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["output"]["echo"]["api_key"] == "[REDACTED:secret]"
    assert executed_body["receipt"]["output"]["echo"]["api_key"] == "[REDACTED:secret]"
    assert executed_body["receipt"]["sandbox"]["output"]["echo"]["api_key"] == "[REDACTED:secret]"
    assert executed_body["output"]["echo"]["token_count"] == 3
    assert different_key not in json.dumps(executed_body, ensure_ascii=False)


def test_plugins_tool_run_requires_matching_approval_payload(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/ops",
            "actor": _PLUGIN_ACTOR,
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Deploy to production.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                },
                {
                    "id": "acme.restart",
                    "kind": "tool",
                    "name": "restart",
                    "action": "restart",
                    "description": "Restart production service.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                },
            ],
        },
    )
    assert installed.status_code == 200
    installed_body = installed.json()
    assert installed_body["ok"] is True
    plugin_id = str(installed_body["plugin_id"])

    tools = client.get(f"/plugins/tools/list?plugin_id={plugin_id}")
    assert tools.status_code == 200
    tools_body = tools.json()
    by_action = {str(item.get("action")): str(item.get("id")) for item in tools_body.get("items", [])}
    deploy_tool_id = by_action["deploy"]
    restart_tool_id = by_action["restart"]

    raised = client.post(
        "/trust/set", json={"level": 6, "reason": "tool-run-approval-binding-test", "actor": "test.trust.write"}
    )
    assert raised.status_code == 200
    assert raised.json()["ok"] is True

    deploy_pending = client.post("/plugins/tools/run", json={"id": deploy_tool_id, "input": {"target": "prod"}})
    assert deploy_pending.status_code == 200
    deploy_pending_body = deploy_pending.json()
    assert deploy_pending_body["ok"] is True
    assert deploy_pending_body["status"] == "pending"
    assert deploy_pending_body["governance"]["gate"] == "approvals_gate"
    deploy_approval_id = str(deploy_pending_body["approval_id"])
    assert deploy_pending_body["tool_id"] == deploy_tool_id

    restart_pending = client.post("/plugins/tools/run", json={"id": restart_tool_id, "input": {"target": "prod"}})
    assert restart_pending.status_code == 200
    restart_pending_body = restart_pending.json()
    assert restart_pending_body["ok"] is True
    assert restart_pending_body["status"] == "pending"
    assert restart_pending_body["governance"]["gate"] == "approvals_gate"
    restart_approval_id = str(restart_pending_body["approval_id"])
    assert restart_pending_body["tool_id"] == restart_tool_id

    approved_restart = client.post(
        "/approvals/decision", json={"id": restart_approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved_restart.status_code == 200
    assert approved_restart.json()["ok"] is True

    mismatched = client.post(
        "/plugins/tools/run",
        json={"id": deploy_tool_id, "approval_id": restart_approval_id, "input": {"target": "prod"}},
    )
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["ok"] is False
    assert mismatched_body["status"] == "needs_approval"
    assert mismatched_body["error"] == "approval_payload_mismatch"
    refreshed_approval_id = str(mismatched_body["approval_id"])
    assert refreshed_approval_id
    assert refreshed_approval_id != restart_approval_id
    assert mismatched_body["previous_approval_id"] == restart_approval_id
    assert mismatched_body["governance"]["gate"] == "approvals_gate"
    assert mismatched_body["governance"]["next_step"] == "approve_exact_action"
    assert mismatched_body["tool_id"] == deploy_tool_id
    refreshed_artifact_dir = Path(str(mismatched_body["artifact_dir"]))
    assert (refreshed_artifact_dir / "request.json").exists()
    assert (refreshed_artifact_dir / "mismatch.json").exists()

    approved_deploy = client.post(
        "/approvals/decision", json={"id": deploy_approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved_deploy.status_code == 200
    assert approved_deploy.json()["ok"] is True

    executed = client.post(
        "/plugins/tools/run",
        json={"id": deploy_tool_id, "approval_id": deploy_approval_id, "input": {"target": "prod"}},
    )
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "ok"
    assert executed_body["tool_id"] == deploy_tool_id
    assert executed_body["meta"]["tool_action"] == "deploy"


def test_plugins_run_refreshes_missing_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/missing-approval",
            "actor": _PLUGIN_ACTOR,
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Deploy to production.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    installed_body = installed.json()
    assert installed_body["ok"] is True
    plugin_id = str(installed_body["plugin_id"])

    raised = client.post(
        "/trust/set", json={"level": 6, "reason": "plugin-missing-approval-test", "actor": "test.trust.write"}
    )
    assert raised.status_code == 200
    assert raised.json()["ok"] is True

    pending = client.post("/plugins/run", json={"id": plugin_id, "action": "deploy", "input": {"target": "prod"}})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "pending"
    approval_id = str(pending_body["approval_id"])
    assert approval_id

    pending_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    assert pending_path.exists()
    pending_path.unlink()

    retried = client.post(
        "/plugins/run",
        json={"id": plugin_id, "action": "deploy", "approval_id": approval_id, "input": {"target": "prod"}},
    )
    assert retried.status_code == 200
    retried_body = retried.json()
    assert retried_body["ok"] is False
    assert retried_body["status"] == "needs_approval"
    assert retried_body["error"] == "approval_not_found"
    refreshed_approval_id = str(retried_body["approval_id"])
    assert refreshed_approval_id
    assert refreshed_approval_id != approval_id
    assert retried_body["previous_approval_id"] == approval_id
    assert retried_body["governance"]["gate"] == "approvals_gate"
    assert retried_body["governance"]["next_step"] == "approve_exact_action"
    refreshed_artifact_dir = Path(str(retried_body["artifact_dir"]))
    assert (refreshed_artifact_dir / "request.json").exists()
    assert (refreshed_artifact_dir / "error.json").exists()
