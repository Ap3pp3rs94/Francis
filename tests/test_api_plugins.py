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


def _isolate_generated_plugin_root(monkeypatch, plugins_module, tmp_path: Path) -> None:
    from francis.plugin_factory import spec_builder

    generated_root = tmp_path / "generated_plugins"
    monkeypatch.setattr(plugins_module, "_gen_dir", lambda: generated_root)
    monkeypatch.setattr(spec_builder, "_gen_dir", lambda: generated_root)


def _assert_stage17_projection_readback(
    readback: dict[str, object],
    *,
    projection_scope: str,
    global_counts_included: bool,
    selected_capability_ids: list[str] | None = None,
) -> None:
    generated_at = str(readback["generated_at"])
    assert "T" in generated_at
    assert generated_at.endswith("Z")
    assert readback["projection_contract"] == "stage17_capability_library_projection_evidence_v1"
    projection_evidence = readback["projection_evidence"]
    assert isinstance(projection_evidence, dict)
    assert projection_evidence["contract"] == "stage17_capability_library_projection_evidence_v1"
    assert projection_evidence["stage"] == "Stage 17 / Capability Economy"
    assert projection_evidence["projection_scope"] == projection_scope
    assert projection_evidence["global_counts_included"] is global_counts_included
    assert projection_evidence["selected_capability_ids"] == sorted(selected_capability_ids or [])
    assert projection_evidence["read_only_projection"] is True
    assert projection_evidence["writes_repo"] is False
    assert projection_evidence["writes_data"] is False
    assert projection_evidence["grants_execution_authority"] is False
    assert projection_evidence["grants_mutation_authority"] is False


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
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
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


def test_plugins_disable_generated_staged_plugin_updates_catalog_lifecycle_status(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    built = client.post(
        "/plugins/build",
        json={
            "name": "Generated Staged Disable Plugin",
            "description": "Stage 17 lifecycle status regression coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": _forge_promotion_meta("generated_staged_disable"),
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    assert built_body["status"] == "staged"
    plugin_id = str(built_body["plugin_id"])

    staged_catalog = client.get("/plugins/capabilities/catalog?limit=5000")
    assert staged_catalog.status_code == 200
    staged_entry = next(item for item in staged_catalog.json()["items"] if item["capability"] == plugin_id)
    assert staged_entry["status"] == "staged"

    staged_remediation = client.get("/plugins/capabilities/packs/promotion/rules/remediation")
    assert staged_remediation.status_code == 200
    assert plugin_id in json.dumps(staged_remediation.json(), sort_keys=True)

    disabled = client.post(
        "/plugins/disable",
        json={
            "id": plugin_id,
            "actor": _PLUGIN_ACTOR,
            "reason": "operator disabled generated staged plugin before promotion",
        },
    )
    assert disabled.status_code == 200
    disabled_body = disabled.json()
    assert disabled_body["ok"] is True
    assert disabled_body["enabled"] is False
    assert disabled_body["status"] == "disabled"

    fetched = client.get(f"/plugins/get?id={plugin_id}")
    assert fetched.status_code == 200
    fetched_item = fetched.json()["item"]
    assert fetched_item["status"] == "disabled"
    assert fetched_item["enabled"] is False
    assert fetched_item["meta"]["status"] == "disabled"
    assert fetched_item["meta"]["promotion_status"] == "disabled"
    assert fetched_item["meta"]["disabled_from_status"] == "staged"
    assert fetched_item["meta"]["disabled_from_promotion_status"] == "staged"

    disabled_catalog = client.get("/plugins/capabilities/catalog?limit=5000")
    assert disabled_catalog.status_code == 200
    disabled_entry = next(item for item in disabled_catalog.json()["items"] if item["capability"] == plugin_id)
    assert disabled_entry["status"] == "disabled"

    remediated = client.get("/plugins/capabilities/packs/promotion/rules/remediation")
    assert remediated.status_code == 200
    remediated_body = remediated.json()
    assert remediated_body["ok"] is True
    assert remediated_body["remediation_queue_count"] == 0
    assert plugin_id not in json.dumps(remediated_body, sort_keys=True)

    reenabled = client.post(
        "/plugins/enable",
        json={
            "id": plugin_id,
            "actor": _PLUGIN_ACTOR,
            "reason": "operator attempted re-enable before proposal review",
        },
    )
    assert reenabled.status_code == 200
    reenabled_body = reenabled.json()
    assert reenabled_body["ok"] is False
    assert reenabled_body["error"] == "promotion_readiness_blocked"
    assert reenabled_body["readiness"]["requirements"]["proposal_review"] is False

    still_disabled = client.get(f"/plugins/get?id={plugin_id}")
    assert still_disabled.status_code == 200
    assert still_disabled.json()["item"]["status"] == "disabled"


def test_plugins_disable_records_quarantine_lifecycle_receipt_and_catalog_readback(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    built = client.post(
        "/plugins/build",
        json={
            "name": "Generated Quarantine Plugin",
            "description": "Stage 17 quarantine lifecycle receipt coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": {
                **_forge_promotion_meta("generated_quarantine_lifecycle"),
                "pack_id": "ops.lifecycle_quarantine",
                "pack_version": "1.0.0",
                "pack_name": "Ops Lifecycle Quarantine Pack",
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
            },
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    quarantined = client.post(
        "/plugins/disable",
        json={
            "id": plugin_id,
            "actor": _PLUGIN_ACTOR,
            "reason": "operator quarantined capability after lifecycle review",
            "meta": {
                "lifecycle_action": "quarantine",
                "finding_ref": "operator.lifecycle.finding.1",
            },
        },
    )

    assert quarantined.status_code == 200
    quarantine_body = quarantined.json()
    assert quarantine_body["ok"] is True
    assert quarantine_body["applied"] is True
    assert quarantine_body["enabled"] is False
    assert quarantine_body["status"] == "disabled"
    assert quarantine_body["lifecycle_action"] == "quarantine"
    assert quarantine_body["lifecycle_status"] == "quarantined"
    assert quarantine_body["governance"]["scope"] == "plugins.write"
    assert quarantine_body["governance"]["writes_registry_metadata"] is True
    assert quarantine_body["governance"]["writes_lifecycle_receipt"] is True
    assert quarantine_body["governance"]["does_not_promote_capabilities"] is True
    assert quarantine_body["governance"]["does_not_enable_capabilities"] is True
    assert quarantine_body["governance"]["does_not_execute_capabilities"] is True
    assert quarantine_body["governance"]["promotion_authority"] is False
    assert quarantine_body["governance"]["execution_authority"] is False
    assert quarantine_body["governance"]["memory_write"] is False

    receipt_path = Path(str(quarantine_body["lifecycle_receipt_path"]))
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["kind"] == "plugin.lifecycle.receipt"
    assert receipt["receipt_id"] == quarantine_body["lifecycle_receipt_id"]
    assert receipt["plugin_id"] == plugin_id
    assert receipt["action"] == "quarantine"
    assert receipt["lifecycle_status"] == "quarantined"
    assert receipt["previous"]["status"] == "staged"
    assert receipt["previous"]["enabled"] is False
    assert receipt["current"]["status"] == "disabled"
    assert receipt["current"]["enabled"] is False
    assert receipt["governance"]["writes_lifecycle_receipt"] is True
    assert receipt["governance"]["does_not_execute_capabilities"] is True

    fetched = client.get(f"/plugins/get?id={plugin_id}")
    assert fetched.status_code == 200
    fetched_item = fetched.json()["item"]
    assert fetched_item["status"] == "disabled"
    assert fetched_item["enabled"] is False
    fetched_meta = fetched_item["meta"]
    assert fetched_meta["lifecycle_action"] == "quarantine"
    assert fetched_meta["lifecycle_status"] == "quarantined"
    assert fetched_meta["lifecycle_receipt_id"] == quarantine_body["lifecycle_receipt_id"]
    assert fetched_meta["lifecycle_receipt_path"] == quarantine_body["lifecycle_receipt_path"]
    assert fetched_meta["disabled_from_status"] == "staged"
    assert fetched_meta["disabled_from_promotion_status"] == "staged"

    run_quarantined = client.post("/plugins/run", json={"id": plugin_id, "action": "run", "input": "hello"})
    assert run_quarantined.status_code == 200
    run_body = run_quarantined.json()
    assert run_body["ok"] is False
    assert run_body["error"] == "plugin_quarantined"
    assert run_body["status"] == "quarantined"
    assert run_body["lifecycle"]["status"] == "quarantined"
    assert run_body["lifecycle"]["blocks_execution"] is True
    assert run_body["governance"]["gate"] == "plugin_lifecycle_gate"
    assert run_body["governance"]["execution_authority"] is False

    catalog = client.get("/plugins/capabilities/catalog?limit=5000")
    assert catalog.status_code == 200
    catalog_body = catalog.json()
    entry = next(item for item in catalog_body["items"] if item["capability"] == plugin_id)
    assert entry["status"] == "disabled"
    assert entry["metadata"]["lifecycle_action"] == "quarantine"
    assert entry["metadata"]["lifecycle_status"] == "quarantined"
    assert entry["metadata"]["lifecycle_receipt_id"] == quarantine_body["lifecycle_receipt_id"]
    assert entry["metadata"]["lifecycle_receipt_path"] == quarantine_body["lifecycle_receipt_path"]


def test_plugins_disable_lifecycle_denies_unscoped_and_refuses_unsupported_actions(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/lifecycle-refusal",
            "reason": "install lifecycle refusal fixture",
            "actor": _PLUGIN_ACTOR,
        },
    )
    assert installed.status_code == 200
    installed_body = installed.json()
    assert installed_body["ok"] is True
    plugin_id = str(installed_body["plugin_id"])

    denied = client.post(
        "/plugins/disable",
        json={
            "id": plugin_id,
            "actor": "unscoped.lifecycle.operator",
            "reason": "unscoped quarantine attempt",
            "meta": {"lifecycle_action": "quarantine"},
        },
    )
    assert denied.status_code == 200
    denied_body = denied.json()
    assert denied_body["ok"] is False
    assert denied_body["applied"] is False
    assert denied_body["status"] == "denied"
    assert denied_body["error"] == "api_permission_denied"
    assert denied_body["governance"]["gate"] == "permission_gate"

    after_denied = client.get(f"/plugins/get?id={plugin_id}")
    assert after_denied.status_code == 200
    after_denied_item = after_denied.json()["item"]
    assert after_denied_item["status"] == "enabled"
    assert after_denied_item["enabled"] is True
    assert "lifecycle_status" not in after_denied_item["meta"]

    unsupported = client.post(
        "/plugins/disable",
        json={
            "id": plugin_id,
            "actor": _PLUGIN_ACTOR,
            "reason": "unsupported lifecycle action",
            "meta": {"lifecycle_action": "archive"},
        },
    )
    assert unsupported.status_code == 200
    unsupported_body = unsupported.json()
    assert unsupported_body["ok"] is False
    assert unsupported_body["applied"] is False
    assert unsupported_body["status"] == "blocked"
    assert unsupported_body["error"] == "unsupported_plugin_lifecycle_action"
    assert unsupported_body["requested_lifecycle_action"] == "archive"
    assert unsupported_body["supported_lifecycle_actions"] == ["disable", "quarantine", "deprecate"]
    assert unsupported_body["governance"]["writes_registry_metadata"] is False
    assert unsupported_body["governance"]["writes_lifecycle_receipt"] is False
    assert unsupported_body["governance"]["does_not_execute_capabilities"] is True

    after_unsupported = client.get(f"/plugins/get?id={plugin_id}")
    assert after_unsupported.status_code == 200
    after_unsupported_item = after_unsupported.json()["item"]
    assert after_unsupported_item["status"] == "enabled"
    assert after_unsupported_item["enabled"] is True
    assert "lifecycle_status" not in after_unsupported_item["meta"]
    lifecycle_dir = data_root / "artifacts" / "plugins" / "lifecycle"
    assert not lifecycle_dir.exists() or list(lifecycle_dir.glob("*.json")) == []


def test_plugins_lifecycle_deprecation_and_unknown_state_block_promotion(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())

    def build_reviewed(label: str) -> str:
        built = client.post(
            "/plugins/build",
            json={
                "name": f"Lifecycle {label}",
                "description": "Stage 17 lifecycle promotion guard coverage",
                "actor": _PLUGIN_ACTOR,
                "meta": _forge_promotion_meta(f"lifecycle_{label}"),
            },
        )
        assert built.status_code == 200
        built_body = built.json()
        assert built_body["ok"] is True
        _approve_forge_proposal(client, str(built_body["proposal_id"]))
        return str(built_body["plugin_id"])

    deprecated_id = build_reviewed("deprecated")
    ambiguous_id = build_reviewed("ambiguous")
    active_id = build_reviewed("active")

    deprecated = client.post(
        "/plugins/disable",
        json={
            "id": deprecated_id,
            "actor": _PLUGIN_ACTOR,
            "reason": "operator superseded staged candidate",
            "meta": {"lifecycle_action": "deprecate"},
        },
    )
    assert deprecated.status_code == 200
    deprecated_body = deprecated.json()
    assert deprecated_body["ok"] is True
    assert deprecated_body["lifecycle_action"] == "deprecate"
    assert deprecated_body["lifecycle_status"] == "deprecated"
    assert deprecated_body["lifecycle_receipt"]["kind"] == "plugin.lifecycle.receipt"

    blocked_deprecated = client.post(
        "/plugins/enable",
        json={
            "id": deprecated_id,
            "actor": _PLUGIN_ACTOR,
            "reason": "attempt deprecated lifecycle promotion",
        },
    )
    assert blocked_deprecated.status_code == 200
    blocked_deprecated_body = blocked_deprecated.json()
    assert blocked_deprecated_body["ok"] is False
    assert blocked_deprecated_body["error"] == "promotion_readiness_blocked"
    assert blocked_deprecated_body["readiness"]["missing_requirements"] == ["lifecycle_state"]
    deprecated_lifecycle = blocked_deprecated_body["readiness"]["evidence"]["lifecycle"]
    assert deprecated_lifecycle["status"] == "deprecated"
    assert deprecated_lifecycle["blocks_promotion"] is True
    assert deprecated_lifecycle["error"] == "plugin_deprecated"

    registry = plugins._load_registry()
    ambiguous = plugins._read_plugin(registry, ambiguous_id)
    assert ambiguous is not None
    ambiguous_meta = dict(ambiguous.get("meta") or {})
    ambiguous_meta["lifecycle_status"] = "operator_review_limbo"
    ambiguous["meta"] = ambiguous_meta
    plugins._write_plugin(registry, plugins._normalize_plugin_record(ambiguous_id, ambiguous))
    plugins._save_registry_and_catalog(registry)

    blocked_ambiguous = client.post(
        "/plugins/enable",
        json={
            "id": ambiguous_id,
            "actor": _PLUGIN_ACTOR,
            "reason": "attempt ambiguous lifecycle promotion",
        },
    )
    assert blocked_ambiguous.status_code == 200
    blocked_ambiguous_body = blocked_ambiguous.json()
    assert blocked_ambiguous_body["ok"] is False
    assert blocked_ambiguous_body["error"] == "promotion_readiness_blocked"
    assert blocked_ambiguous_body["readiness"]["missing_requirements"] == ["lifecycle_state"]
    ambiguous_lifecycle = blocked_ambiguous_body["readiness"]["evidence"]["lifecycle"]
    assert ambiguous_lifecycle["status"] == "operator_review_limbo"
    assert ambiguous_lifecycle["blocks_promotion"] is True
    assert ambiguous_lifecycle["error"] == "plugin_lifecycle_state_unknown"

    enabled = client.post(
        "/plugins/enable",
        json={
            "id": active_id,
            "actor": _PLUGIN_ACTOR,
            "reason": "promote active lifecycle candidate",
        },
    )
    assert enabled.status_code == 200
    enabled_body = enabled.json()
    assert enabled_body["ok"] is True
    assert enabled_body["enabled"] is True
    assert enabled_body["promotion_receipt"]["lifecycle"]["blocks_promotion"] is False

    run_active = client.post("/plugins/run", json={"id": active_id, "action": "run", "input": "hello"})
    assert run_active.status_code == 200
    run_active_body = run_active.json()
    assert run_active_body["ok"] is True
    assert run_active_body["status"] == "ok"


def test_plugins_lifecycle_repair_restores_staged_candidate_without_promoting(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    built = client.post(
        "/plugins/build",
        json={
            "name": "Lifecycle Repair",
            "description": "Stage 17 lifecycle repair coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": _forge_promotion_meta("lifecycle_repair"),
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])
    _approve_forge_proposal(client, str(built_body["proposal_id"]))

    deprecated = client.post(
        "/plugins/disable",
        json={
            "id": plugin_id,
            "actor": _PLUGIN_ACTOR,
            "reason": "operator deprecated staged candidate before repair",
            "meta": {"lifecycle_action": "deprecate"},
        },
    )
    assert deprecated.status_code == 200
    deprecated_body = deprecated.json()
    assert deprecated_body["ok"] is True
    assert deprecated_body["lifecycle_status"] == "deprecated"

    blocked_before_repair = client.post(
        "/plugins/enable",
        json={
            "id": plugin_id,
            "actor": _PLUGIN_ACTOR,
            "reason": "attempt deprecated lifecycle promotion before repair",
        },
    )
    assert blocked_before_repair.status_code == 200
    blocked_before_body = blocked_before_repair.json()
    assert blocked_before_body["ok"] is False
    assert blocked_before_body["error"] == "promotion_readiness_blocked"
    assert blocked_before_body["readiness"]["missing_requirements"] == ["lifecycle_state"]

    lifecycle_dir = data_root / "artifacts" / "plugins" / "lifecycle"
    receipt_count_before_repair = len(list(lifecycle_dir.glob("*.json")))
    repair_payload = {
        "id": plugin_id,
        "actor": _PLUGIN_ACTOR,
        "reason": "operator repaired deprecated lifecycle state after review",
        "meta": {
            "lifecycle_action": "restore",
            "repair_ref": "operator.lifecycle.repair.1",
        },
    }

    repair_dry_run = client.post("/plugins/lifecycle/repair", json=repair_payload)
    assert repair_dry_run.status_code == 200
    dry_run_body = repair_dry_run.json()
    assert dry_run_body["ok"] is True
    assert dry_run_body["applied"] is False
    assert dry_run_body["status"] == "dry_run"
    assert len(dry_run_body["dry_run_fingerprint"]) == 64
    assert dry_run_body["dry_run_confirmation"]["required_for_apply"] is True
    assert dry_run_body["dry_run_confirmation"]["fingerprint"] == dry_run_body["dry_run_fingerprint"]
    assert dry_run_body["dry_run_confirmation"]["fingerprint_contract"] == (
        "stage17_plugin_lifecycle_repair_dry_run_v1"
    )
    assert dry_run_body["planned_lifecycle_repair"]["target"]["status"] == "staged"
    assert dry_run_body["planned_lifecycle_repair"]["target"]["enabled"] is False
    assert dry_run_body["planned_lifecycle_repair"]["target"]["lifecycle_status"] == "active"
    last_non_blocking = dry_run_body["planned_lifecycle_repair"]["last_non_blocking_lifecycle_metadata"]
    assert last_non_blocking["status"] == "staged"
    assert last_non_blocking["safe_registry_status"] == "staged"
    assert last_non_blocking["safe_enabled"] is False
    assert dry_run_body["governance"]["writes_registry_metadata"] is False
    assert dry_run_body["governance"]["writes_lifecycle_receipt"] is False
    assert dry_run_body["governance"]["dry_run_required_before_apply"] is True
    assert len(list(lifecycle_dir.glob("*.json"))) == receipt_count_before_repair

    after_dry_run = client.get(f"/plugins/get?id={plugin_id}")
    assert after_dry_run.status_code == 200
    after_dry_run_item = after_dry_run.json()["item"]
    assert after_dry_run_item["status"] == "disabled"
    assert after_dry_run_item["enabled"] is False
    assert after_dry_run_item["meta"]["lifecycle_status"] == "deprecated"

    blocked_mismatch = client.post(
        "/plugins/lifecycle/repair",
        json={**repair_payload, "dry_run": False, "dry_run_fingerprint": "x" * 64},
    )
    assert blocked_mismatch.status_code == 200
    blocked_mismatch_body = blocked_mismatch.json()
    assert blocked_mismatch_body["ok"] is False
    assert blocked_mismatch_body["applied"] is False
    assert blocked_mismatch_body["status"] == "blocked"
    assert blocked_mismatch_body["error"] == "plugin_lifecycle_repair_dry_run_confirmation_required"
    assert blocked_mismatch_body["dry_run_confirmation"]["fingerprint_matched"] is False
    assert blocked_mismatch_body["governance"]["writes_registry_metadata"] is False
    assert blocked_mismatch_body["governance"]["writes_lifecycle_receipt"] is False
    assert len(list(lifecycle_dir.glob("*.json"))) == receipt_count_before_repair

    repaired = client.post(
        "/plugins/lifecycle/repair",
        json={
            **repair_payload,
            "dry_run": False,
            "dry_run_fingerprint": dry_run_body["dry_run_fingerprint"],
        },
    )
    assert repaired.status_code == 200
    repaired_body = repaired.json()
    assert repaired_body["ok"] is True
    assert repaired_body["applied"] is True
    assert repaired_body["enabled"] is False
    assert repaired_body["status"] == "staged"
    assert repaired_body["lifecycle_action"] == "restore"
    assert repaired_body["lifecycle_status"] == "active"
    assert repaired_body["lifecycle_before"]["status"] == "deprecated"
    assert repaired_body["lifecycle_before"]["blocks_promotion"] is True
    assert repaired_body["lifecycle_after"]["status"] == "active"
    assert repaired_body["lifecycle_after"]["blocks_promotion"] is False
    assert repaired_body["governance"]["gate"] == "plugin_lifecycle_repair"
    assert repaired_body["governance"]["scope"] == "plugins.write"
    assert repaired_body["governance"]["writes_registry_metadata"] is True
    assert repaired_body["governance"]["writes_lifecycle_receipt"] is True
    assert repaired_body["governance"]["does_not_promote_capabilities"] is True
    assert repaired_body["governance"]["does_not_enable_capabilities"] is True
    assert repaired_body["governance"]["does_not_execute_capabilities"] is True
    assert repaired_body["governance"]["promotion_authority"] is False
    assert repaired_body["governance"]["execution_authority"] is False
    assert repaired_body["governance"]["memory_write"] is False
    assert repaired_body["dry_run_confirmation"]["fingerprint_matched"] is True
    assert repaired_body["dry_run_fingerprint"] == dry_run_body["dry_run_fingerprint"]
    assert len(list(lifecycle_dir.glob("*.json"))) == receipt_count_before_repair + 1

    receipt_path = Path(str(repaired_body["lifecycle_receipt_path"]))
    assert receipt_path.exists()
    repair_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert repair_receipt["kind"] == "plugin.lifecycle.receipt"
    assert repair_receipt["receipt_id"] == repaired_body["lifecycle_receipt_id"]
    assert repair_receipt["plugin_id"] == plugin_id
    assert repair_receipt["action"] == "restore"
    assert repair_receipt["lifecycle_status"] == "active"
    assert repair_receipt["previous"]["status"] == "disabled"
    assert repair_receipt["previous"]["lifecycle_status"] == "deprecated"
    assert repair_receipt["current"]["status"] == "staged"
    assert repair_receipt["current"]["enabled"] is False
    assert repair_receipt["current"]["lifecycle_status"] == "active"
    assert repair_receipt["governance"]["route"] == "/plugins/lifecycle/repair"
    assert repair_receipt["governance"]["does_not_enable_capabilities"] is True
    assert repair_receipt["governance"]["does_not_execute_capabilities"] is True

    fetched = client.get(f"/plugins/get?id={plugin_id}")
    assert fetched.status_code == 200
    fetched_item = fetched.json()["item"]
    assert fetched_item["status"] == "staged"
    assert fetched_item["enabled"] is False
    fetched_meta = fetched_item["meta"]
    assert fetched_meta["lifecycle_status"] == "active"
    assert fetched_meta["lifecycle_repair_status"] == "repaired"
    assert fetched_meta["lifecycle_repair_previous_status"] == "deprecated"
    assert fetched_meta["lifecycle_repair_receipt_id"] == repaired_body["lifecycle_receipt_id"]

    run_repaired = client.post("/plugins/run", json={"id": plugin_id, "action": "run", "input": "hello"})
    assert run_repaired.status_code == 200
    run_repaired_body = run_repaired.json()
    assert run_repaired_body["ok"] is False
    assert run_repaired_body["error"] == "plugin_staged"
    assert run_repaired_body["status"] == "staged"

    promoted = client.post(
        "/plugins/enable",
        json={
            "id": plugin_id,
            "actor": _PLUGIN_ACTOR,
            "reason": "promote after explicit lifecycle repair",
        },
    )
    assert promoted.status_code == 200
    promoted_body = promoted.json()
    assert promoted_body["ok"] is True
    assert promoted_body["enabled"] is True
    assert promoted_body["promotion_status"] == "promoted"
    assert promoted_body["promotion_receipt"]["lifecycle"]["status"] == "active"
    assert promoted_body["promotion_receipt"]["lifecycle"]["blocks_promotion"] is False


def test_plugins_lifecycle_repair_denies_unscoped_and_refuses_ambiguous_noop(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/lifecycle-repair-refusal",
            "reason": "install lifecycle repair refusal fixture",
            "actor": _PLUGIN_ACTOR,
        },
    )
    assert installed.status_code == 200
    installed_body = installed.json()
    assert installed_body["ok"] is True
    plugin_id = str(installed_body["plugin_id"])

    quarantined = client.post(
        "/plugins/disable",
        json={
            "id": plugin_id,
            "actor": _PLUGIN_ACTOR,
            "reason": "quarantine before denied repair",
            "meta": {"lifecycle_action": "quarantine"},
        },
    )
    assert quarantined.status_code == 200
    assert quarantined.json()["ok"] is True
    lifecycle_dir = data_root / "artifacts" / "plugins" / "lifecycle"
    receipt_count_before_denied = len(list(lifecycle_dir.glob("*.json")))

    denied = client.post(
        "/plugins/lifecycle/repair",
        json={
            "id": plugin_id,
            "actor": "unscoped.lifecycle.repair.operator",
            "reason": "unscoped lifecycle repair attempt",
            "meta": {"lifecycle_action": "repair"},
        },
    )
    assert denied.status_code == 200
    denied_body = denied.json()
    assert denied_body["ok"] is False
    assert denied_body["applied"] is False
    assert denied_body["status"] == "denied"
    assert denied_body["error"] == "api_permission_denied"
    assert denied_body["governance"]["gate"] == "permission_gate"
    assert len(list(lifecycle_dir.glob("*.json"))) == receipt_count_before_denied

    after_denied = client.get(f"/plugins/get?id={plugin_id}")
    assert after_denied.status_code == 200
    after_denied_item = after_denied.json()["item"]
    assert after_denied_item["status"] == "disabled"
    assert after_denied_item["enabled"] is False
    assert after_denied_item["meta"]["lifecycle_status"] == "quarantined"
    assert "lifecycle_repair_status" not in after_denied_item["meta"]

    unsupported = client.post(
        "/plugins/lifecycle/repair",
        json={
            "id": plugin_id,
            "actor": _PLUGIN_ACTOR,
            "reason": "unsupported lifecycle repair action",
            "meta": {"lifecycle_action": "archive"},
        },
    )
    assert unsupported.status_code == 200
    unsupported_body = unsupported.json()
    assert unsupported_body["ok"] is False
    assert unsupported_body["applied"] is False
    assert unsupported_body["status"] == "blocked"
    assert unsupported_body["error"] == "unsupported_plugin_lifecycle_action"
    assert unsupported_body["requested_lifecycle_action"] == "archive"
    assert unsupported_body["supported_lifecycle_actions"] == ["repair", "restore"]
    assert unsupported_body["governance"]["gate"] == "plugin_lifecycle_repair"
    assert unsupported_body["governance"]["writes_registry_metadata"] is False
    assert unsupported_body["governance"]["writes_lifecycle_receipt"] is False
    assert len(list(lifecycle_dir.glob("*.json"))) == receipt_count_before_denied

    active = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/lifecycle-repair-active",
            "reason": "install active lifecycle repair noop fixture",
            "actor": _PLUGIN_ACTOR,
        },
    )
    assert active.status_code == 200
    active_body = active.json()
    assert active_body["ok"] is True
    active_id = str(active_body["plugin_id"])

    noop = client.post(
        "/plugins/lifecycle/repair",
        json={
            "id": active_id,
            "actor": _PLUGIN_ACTOR,
            "reason": "ambiguous repair with no blocking lifecycle state",
            "meta": {"lifecycle_action": "repair"},
        },
    )
    assert noop.status_code == 200
    noop_body = noop.json()
    assert noop_body["ok"] is False
    assert noop_body["applied"] is False
    assert noop_body["status"] == "not_required"
    assert noop_body["error"] == "lifecycle_repair_not_required"
    assert noop_body["lifecycle_before"]["blocks_promotion"] is False
    assert noop_body["governance"]["gate"] == "plugin_lifecycle_repair"
    assert noop_body["governance"]["writes_registry_metadata"] is False
    assert noop_body["governance"]["writes_lifecycle_receipt"] is False
    assert noop_body["governance"]["does_not_enable_capabilities"] is True
    assert len(list(lifecycle_dir.glob("*.json"))) == receipt_count_before_denied


def test_plugins_lifecycle_repair_history_is_read_only_without_authority(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    readback = client.get("/plugins/lifecycle/repair/history?id=missing.lifecycle")
    assert readback.status_code == 200
    body = readback.json()
    assert body["ok"] is False
    assert body["applied"] is False
    assert body["status"] == "not_found"
    assert body["error"] == "not_found"
    assert body["history_count"] == 0
    assert body["repair_restore_history_count"] == 0
    assert body["apply_readiness"]["safe_to_apply"] is False
    assert body["apply_readiness"]["writes_registry_metadata_if_applied"] is False
    assert body["apply_readiness"]["writes_lifecycle_receipt_if_applied"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["apply_requires_plugins_write_scope"] is True
    assert body["governance"]["writes_registry_metadata"] is False
    assert body["governance"]["writes_lifecycle_receipt"] is False
    assert body["governance"]["writes_data"] is False
    assert body["governance"]["promotion_authority"] is False
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["memory_write"] is False
    assert not (data_root / "plugins" / "_registry.json").exists()
    assert not (data_root / "artifacts" / "plugins" / "lifecycle").exists()


def test_plugins_lifecycle_repair_history_reads_receipts_and_apply_safety(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/lifecycle-history",
            "reason": "install lifecycle history fixture",
            "actor": _PLUGIN_ACTOR,
        },
    )
    assert installed.status_code == 200
    installed_body = installed.json()
    assert installed_body["ok"] is True
    plugin_id = str(installed_body["plugin_id"])

    quarantined = client.post(
        "/plugins/disable",
        json={
            "id": plugin_id,
            "actor": _PLUGIN_ACTOR,
            "reason": "quarantine before lifecycle history readback",
            "meta": {"lifecycle_action": "quarantine"},
        },
    )
    assert quarantined.status_code == 200
    assert quarantined.json()["ok"] is True

    registry_path = data_root / "plugins" / "_registry.json"
    lifecycle_dir = data_root / "artifacts" / "plugins" / "lifecycle"
    registry_before_history = registry_path.read_text(encoding="utf-8")
    receipt_names_before_history = sorted(path.name for path in lifecycle_dir.glob("*.json"))

    history_before = client.get(f"/plugins/lifecycle/repair/history?id={plugin_id}")
    assert history_before.status_code == 200
    before_body = history_before.json()
    assert before_body["ok"] is True
    assert before_body["applied"] is False
    assert before_body["status"] == "repair_available"
    assert before_body["history_count"] == 1
    assert before_body["repair_restore_history_count"] == 0
    assert before_body["current_lifecycle"]["status"] == "quarantined"
    assert before_body["current_lifecycle"]["blocks_promotion"] is True
    assert before_body["last_non_blocking_lifecycle_metadata"]["status"] == "enabled"
    assert before_body["last_non_blocking_lifecycle_metadata"]["safe_registry_status"] == "disabled"
    assert before_body["history"][0]["action"] == "quarantine"
    assert before_body["latest_receipt"]["receipt_id"] == quarantined.json()["lifecycle_receipt_id"]
    assert before_body["apply_readiness"]["safe_to_apply"] is True
    assert before_body["apply_readiness"]["reason"] == (
        "blocking_lifecycle_state_detected_with_non_enabled_restore_target"
    )
    assert before_body["apply_readiness"]["dry_run_fingerprint_available"] is False
    assert before_body["apply_readiness"]["dry_run_confirmation"]["required_for_apply"] is True
    assert before_body["apply_readiness"]["dry_run_confirmation"]["fingerprint_available_from_apply_dry_run"] is True
    assert before_body["apply_readiness"]["planned_lifecycle_repair"]["target"]["status"] == "disabled"
    assert before_body["apply_readiness"]["planned_lifecycle_repair"]["target"]["enabled"] is False
    assert before_body["apply_readiness"]["writes_registry_metadata_if_applied"] is True
    assert before_body["apply_readiness"]["writes_lifecycle_receipt_if_applied"] is True
    assert before_body["governance"]["read_only"] is True
    assert before_body["governance"]["writes_registry_metadata"] is False
    assert before_body["governance"]["writes_lifecycle_receipt"] is False
    assert registry_path.read_text(encoding="utf-8") == registry_before_history
    assert sorted(path.name for path in lifecycle_dir.glob("*.json")) == receipt_names_before_history

    repair_payload = {
        "id": plugin_id,
        "actor": _PLUGIN_ACTOR,
        "reason": "restore after lifecycle history review",
        "meta": {"lifecycle_action": "restore"},
    }
    repair_dry_run = client.post("/plugins/lifecycle/repair", json=repair_payload)
    assert repair_dry_run.status_code == 200
    dry_run_body = repair_dry_run.json()
    assert dry_run_body["ok"] is True
    repaired = client.post(
        "/plugins/lifecycle/repair",
        json={
            **repair_payload,
            "dry_run": False,
            "dry_run_fingerprint": dry_run_body["dry_run_fingerprint"],
        },
    )
    assert repaired.status_code == 200
    repaired_body = repaired.json()
    assert repaired_body["ok"] is True
    assert repaired_body["applied"] is True

    registry_before_second_history = registry_path.read_text(encoding="utf-8")
    receipt_names_before_second_history = sorted(path.name for path in lifecycle_dir.glob("*.json"))

    history_after = client.get(f"/plugins/lifecycle/repair/history?id={plugin_id}&limit=10")
    assert history_after.status_code == 200
    after_body = history_after.json()
    assert after_body["ok"] is True
    assert after_body["applied"] is False
    assert after_body["status"] == "not_required"
    assert after_body["current_lifecycle"]["status"] == "active"
    assert after_body["current_lifecycle"]["blocks_promotion"] is False
    assert after_body["history_count"] == 2
    assert after_body["repair_restore_history_count"] == 1
    assert after_body["latest_receipt"]["receipt_id"] == repaired_body["lifecycle_receipt_id"]
    assert after_body["latest_repair_restore"]["action"] == "restore"
    assert after_body["latest_repair_restore"]["receipt_id"] == repaired_body["lifecycle_receipt_id"]
    assert after_body["last_non_blocking_lifecycle_metadata"]["status"] == "disabled"
    assert after_body["last_non_blocking_lifecycle_metadata"]["source"] == (
        "registry.meta.lifecycle_repair_restored_status"
    )
    assert after_body["apply_readiness"]["safe_to_apply"] is False
    assert after_body["apply_readiness"]["reason"] == "lifecycle_repair_not_required"
    assert after_body["apply_readiness"]["planned_lifecycle_repair"] == {}
    assert after_body["apply_readiness"]["writes_registry_metadata_if_applied"] is False
    assert after_body["apply_readiness"]["writes_lifecycle_receipt_if_applied"] is False
    assert after_body["governance"]["read_only"] is True
    assert after_body["governance"]["lifecycle_authority"] is False
    assert registry_path.read_text(encoding="utf-8") == registry_before_second_history
    assert sorted(path.name for path in lifecycle_dir.glob("*.json")) == receipt_names_before_second_history


def test_plugins_build_requires_forge_staging_quality(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
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


def test_staged_plugin_promotion_readiness_uses_linked_proposal_artifact_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)

    client = TestClient(create_app())

    built = client.post(
        "/plugins/build",
        json={
            "name": "Proposal Artifact Evidence Plugin",
            "description": "complete metadata with proposal artifact evidence fallback",
            "actor": _PLUGIN_ACTOR,
            "meta": _forge_promotion_meta("proposal_artifact_evidence"),
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])
    proposal_id = str(built_body["proposal_id"])

    registry = plugins._load_registry()
    plugin = plugins._read_plugin(registry, plugin_id)
    assert plugin is not None
    meta = dict(plugin.get("meta") or {})
    meta.pop("proposal_evidence", None)
    meta.pop("evidence", None)
    plugin["meta"] = meta
    plugins._write_plugin(registry, plugins._normalize_plugin_record(plugin_id, plugin))
    plugins._save_registry_and_catalog(registry)

    blocked = client.post(
        "/plugins/enable",
        json={"id": plugin_id, "reason": "operator asked before review", "actor": _PLUGIN_ACTOR},
    )
    assert blocked.status_code == 200
    blocked_body = blocked.json()
    assert blocked_body["ok"] is False
    assert blocked_body["error"] == "promotion_readiness_blocked"
    assert blocked_body["readiness"]["missing_requirements"] == ["proposal_review"]
    assert blocked_body["readiness"]["evidence"]["proposal_id"] == proposal_id
    assert blocked_body["readiness"]["evidence"]["proposal_evidence"] == ["mission.proposal_artifact_evidence.repeat"]

    _approve_forge_proposal(client, proposal_id)

    enabled = client.post(
        "/plugins/enable",
        json={"id": plugin_id, "reason": "operator approved proposal artifact evidence", "actor": _PLUGIN_ACTOR},
    )
    assert enabled.status_code == 200
    enabled_body = enabled.json()
    assert enabled_body["ok"] is True
    assert enabled_body["enabled"] is True
    assert enabled_body["promotion_status"] == "promoted"
    assert enabled_body["promotion_receipt"]["proposal_evidence"] == ["mission.proposal_artifact_evidence.repeat"]


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
    closure = body["stage17_closure_matrix"]
    assert closure["kind"] == "plugin.capability_catalog.stage17_closure_matrix"
    assert closure["stage"] == "Stage 17 / Capability Economy"
    assert closure["closure_claimed"] is False
    assert closure["governance"]["read_only"] is True
    assert closure["governance"]["closure_authority"] is False
    assert closure["governance"]["does_not_promote_capabilities"] is True
    assert closure["source_readbacks"]["catalog_route"] == "/plugins/capabilities/catalog"
    criteria = {str(item["id"]): item for item in closure["criteria"]}
    assert set(criteria) == {
        "criterion_1_reusable_operational_assets",
        "criterion_2_pack_evidence_travels",
        "criterion_3_executable_lifecycle",
        "criterion_4_catalog_coherence",
        "criterion_5_governed_operator_paths",
        "criterion_6_reuse_leverage",
    }
    assert closure["weakest_criterion"]["id"] in criteria
    executable_lifecycle = criteria["criterion_3_executable_lifecycle"]
    assert executable_lifecycle["status"] == "ready"
    assert executable_lifecycle["blockers"] == []
    assert executable_lifecycle["evidence"]["plugin_lifecycle_repair_route"] == "/plugins/lifecycle/repair"
    assert executable_lifecycle["evidence"]["lifecycle_repair_contract"] == "plugin.lifecycle.repair_restore_v1"
    assert "/plugins/lifecycle/repair" in executable_lifecycle["routes"]
    catalog_coherence = criteria["criterion_4_catalog_coherence"]
    assert catalog_coherence["routes"] == ["/plugins/capabilities/catalog"]
    assert "stage17_closure_matrix" in catalog_coherence["evidence"]["catalog_readback_fields"]
    assert catalog_coherence["blocker_counts"]["duplicate_capabilities"] == len(
        body["coherence"]["duplicate_capabilities"]
    )
    assert catalog_coherence["blocker_counts"]["duplicate_proposals"] == len(body["coherence"]["duplicate_proposals"])
    assert catalog_coherence["blocker_counts"]["lineage_gaps"] == len(body["coherence"]["lineage_gaps"])
    assert catalog_coherence["blocker_counts"]["validation_lineage_gaps"] == len(
        body["coherence"]["validation_lineage_gaps"]
    )
    assert catalog_coherence["blocker_counts"]["quality_gaps"] == len(body["coherence"]["quality_gaps"])
    reuse_leverage = criteria["criterion_6_reuse_leverage"]
    assert reuse_leverage["evidence"]["claim_boundary"] == (
        "catalog evidence does not prove reuse across real operator contexts"
    )
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
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
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
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
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
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
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
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
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

    receipt_dir = data_root / "artifacts" / "plugins" / "capability_packs" / "metadata_receipts"
    dry_run = client.post(
        "/plugins/capabilities/packs/metadata/receipts/bulk-from-plan",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "dry run reviewed migration plan candidates",
            "pack_ids": [candidate["pack_id"]],
        },
    )

    assert dry_run.status_code == 200
    dry_run_body = dry_run.json()
    assert dry_run_body["ok"] is True
    assert dry_run_body["applied"] is False
    assert dry_run_body["status"] == "dry_run"
    assert dry_run_body["planned_pack_count"] == 1
    assert dry_run_body["planned_capability_count"] == candidate["capability_count"]
    assert len(dry_run_body["dry_run_fingerprint"]) == 64
    assert dry_run_body["dry_run_confirmation"]["required_for_apply"] is True
    assert dry_run_body["dry_run_confirmation"]["fingerprint"] == dry_run_body["dry_run_fingerprint"]
    assert dry_run_body["dry_run_confirmation"]["fingerprint_contract"] == (
        "stage17_capability_pack_metadata_receipts_bulk_from_plan_dry_run_v1"
    )
    assert dry_run_body["planned"][0]["pack_id"] == candidate["pack_id"]
    assert dry_run_body["planned"][0]["writes_registry_metadata"] is False
    assert dry_run_body["planned"][0]["writes_receipt"] is False
    assert dry_run_body["governance"]["dry_run_required_before_apply"] is True
    assert dry_run_body["governance"]["writes_registry_metadata"] is False
    assert dry_run_body["governance"]["writes_receipts"] is False
    assert dry_run_body["governance"]["promotion_authority"] is False
    assert dry_run_body["governance"]["execution_authority"] is False
    assert not receipt_dir.exists()

    after_dry_run = client.get(f"/plugins/get?id={plugin_id}").json()["item"]
    assert "pack_metadata_receipt_id" not in after_dry_run["meta"]

    blocked_without_confirmation = client.post(
        "/plugins/capabilities/packs/metadata/receipts/bulk-from-plan",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "attempt apply without dry run confirmation",
            "pack_ids": [candidate["pack_id"]],
            "dry_run": False,
        },
    )
    assert blocked_without_confirmation.status_code == 200
    blocked_body = blocked_without_confirmation.json()
    assert blocked_body["ok"] is False
    assert blocked_body["applied"] is False
    assert blocked_body["status"] == "blocked"
    assert blocked_body["error"] == "capability_pack_metadata_receipts_bulk_from_plan_dry_run_confirmation_required"
    assert blocked_body["dry_run_confirmation"]["required_for_apply"] is True
    assert blocked_body["dry_run_confirmation"]["fingerprint_matched"] is False
    assert blocked_body["governance"]["writes_registry_metadata"] is False
    assert blocked_body["governance"]["writes_receipts"] is False
    assert not receipt_dir.exists()

    denied = client.post(
        "/plugins/capabilities/packs/metadata/receipts/bulk-from-plan",
        json={
            "actor": "unscoped.migration.apply.operator",
            "reason": "attempt unscoped migration apply",
            "pack_ids": [candidate["pack_id"]],
            "dry_run": False,
            "dry_run_fingerprint": dry_run_body["dry_run_fingerprint"],
        },
    )
    assert denied.status_code == 200
    denied_body = denied.json()
    assert denied_body["ok"] is False
    assert denied_body["error"] == "api_permission_denied"
    assert not receipt_dir.exists()

    recorded = client.post(
        "/plugins/capabilities/packs/metadata/receipts/bulk-from-plan",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "record reviewed migration plan candidates",
            "pack_ids": [candidate["pack_id"]],
            "dry_run": False,
            "dry_run_fingerprint": dry_run_body["dry_run_fingerprint"],
        },
    )

    assert recorded.status_code == 200
    recorded_body = recorded.json()
    assert recorded_body["ok"] is True
    assert recorded_body["status"] == "recorded"
    assert recorded_body["dry_run_fingerprint"] == dry_run_body["dry_run_fingerprint"]
    assert recorded_body["dry_run_confirmation"]["required_for_apply"] is True
    assert recorded_body["dry_run_confirmation"]["fingerprint_matched"] is True
    assert recorded_body["recorded_pack_count"] == 1
    assert recorded_body["recorded_capability_count"] == candidate["capability_count"]
    assert recorded_body["remaining_candidate_total"] < plan["candidate_total"]
    assert recorded_body["governance"]["dry_run_required_before_apply"] is True
    assert recorded_body["governance"]["writes_registry_metadata"] is True
    assert recorded_body["governance"]["writes_receipts"] is True
    assert recorded_body["governance"]["promotion_authority"] is False
    assert recorded_body["governance"]["execution_authority"] is False
    assert recorded_body["governance"]["does_not_approve_proposals"] is True
    assert recorded_body["governance"]["does_not_promote_capabilities"] is True
    assert recorded_body["governance"]["does_not_enable_capabilities"] is True
    assert recorded_body["governance"]["does_not_execute_capabilities"] is True
    receipt_ref = recorded_body["recorded"][0]
    assert receipt_ref["pack_id"] == candidate["pack_id"]

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


def test_plugins_capability_pack_quality_standard_remediation_backfills_candidate_refs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    plugin_ids: list[str] = []
    for index in range(2):
        built = client.post(
            "/plugins/build",
            json={
                "name": f"Capability Quality Standard Remediation Plugin {index}",
                "description": "Stage 17 quality standard remediation coverage",
                "actor": _PLUGIN_ACTOR,
                "meta": _forge_promotion_meta(f"capability_quality_standard_remediation_{index}"),
            },
        )
        assert built.status_code == 200
        built_body = built.json()
        assert built_body["ok"] is True
        plugin_ids.append(str(built_body["plugin_id"]))

    pack_id = "ops.quality_standard_remediation"
    pack_version = "1.0.0"
    recorded = client.post(
        "/plugins/capabilities/packs/metadata/receipts",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "record reviewed pack metadata before quality standard remediation",
            "pack_id": pack_id,
            "pack_version": pack_version,
            "pack_name": "Ops Quality Standard Remediation Pack",
            "capability_ids": plugin_ids,
            "promotion_rules": [
                "metadata_receipt_before_promotion",
                "quality_standards_before_promotion",
                "operator_review_before_promotion",
            ],
            "pack_governance": {
                "risk_tier": "normal",
                "scope": "build_dev",
                "operator_review_required": True,
                "requires_validation_receipt": True,
            },
        },
    )
    assert recorded.status_code == 200
    assert recorded.json()["ok"] is True

    registry = plugins._load_registry()
    plugin = plugins._read_plugin(registry, plugin_ids[1])
    assert plugin is not None
    meta = dict(plugin.get("meta") or {})
    for key in ("tests", "test_refs", "docs", "documentation", "quality"):
        meta.pop(key, None)
    plugin["meta"] = meta
    plugins._write_plugin(registry, plugins._normalize_plugin_record(plugin_ids[1], plugin))
    plugins._save_registry_and_catalog(registry)

    before = client.get("/plugins/capabilities/packs/quality/standards").json()
    before_pack = next(item for item in before["packs"] if item["pack_id"] == pack_id)
    assert before_pack["status"] == "blocked"
    assert before_pack["blockers"] == ["tests_missing", "docs_missing"]
    assert before_pack["tested_count"] == 1
    assert before_pack["documented_count"] == 1

    request_body = {
        "actor": _PLUGIN_ACTOR,
        "reason": "operator reviewed quality standard candidate refs",
        "pack_ids": [pack_id],
        "max_pack_count": 1,
        "max_total_capability_count": 2,
        "max_capability_count_per_pack": 2,
    }
    dry_run = client.post(
        "/plugins/capabilities/packs/quality/standards/remediation/apply",
        json={**request_body, "dry_run": True},
    )
    assert dry_run.status_code == 200
    dry_run_body = dry_run.json()
    assert dry_run_body["ok"] is True
    assert dry_run_body["status"] == "dry_run"
    assert dry_run_body["planned_pack_count"] == 1
    assert dry_run_body["planned_capability_count"] == 2
    planned = dry_run_body["planned"][0]
    assert planned["missing_test_capability_count"] == 1
    assert planned["missing_doc_capability_count"] == 1
    assert planned["quality_references"]["tests"] == ["tests/test_api_plugins.py"]
    assert planned["quality_references"]["docs"] == ["README.md", "docs/operations/COMPLETION_LEDGER.md"]
    assert dry_run_body["governance"]["writes_registry_metadata"] is False
    assert dry_run_body["governance"]["writes_receipts"] is False

    post_dry = plugins._read_plugin(plugins._load_registry(), plugin_ids[1])
    assert post_dry is not None
    assert "quality" not in dict(post_dry.get("meta") or {})

    applied = client.post(
        "/plugins/capabilities/packs/quality/standards/remediation/apply",
        json=request_body,
    )
    assert applied.status_code == 200
    applied_body = applied.json()
    assert applied_body["ok"] is True
    assert applied_body["applied"] is True
    assert applied_body["status"] == "recorded"
    assert applied_body["recorded_pack_count"] == 1
    assert applied_body["recorded_capability_count"] == 1
    assert applied_body["remaining_quality_standard_queue_count"] == 0
    assert applied_body["governance"]["writes_registry_metadata"] is True
    assert applied_body["governance"]["writes_receipts"] is False
    assert applied_body["governance"]["candidate_references_do_not_claim_pack_specific_coverage"] is True
    assert applied_body["governance"]["does_not_write_validation_receipts"] is True
    assert applied_body["governance"]["does_not_write_proposals"] is True
    assert applied_body["governance"]["does_not_promote_capabilities"] is True
    assert applied_body["governance"]["does_not_execute_capabilities"] is True

    stored = plugins._read_plugin(plugins._load_registry(), plugin_ids[1])
    assert stored is not None
    stored_meta = dict(stored.get("meta") or {})
    stored_quality = stored_meta["quality"]
    assert stored_quality["tests"] == ["tests/test_api_plugins.py"]
    assert stored_quality["docs"] == ["README.md", "docs/operations/COMPLETION_LEDGER.md"]
    assert stored_quality["claim_scope"] == "candidate_reference_only_not_pack_specific_proof"
    assert stored_quality["pack_specific_coverage_claimed"] is False
    assert stored_quality["validation_receipt_written"] is False
    assert stored_quality["proposal_lineage_written"] is False
    assert stored_meta["quality_standard_remediation_source"] == (
        "stage17_capability_pack_quality_standard_remediation_apply"
    )

    after = client.get("/plugins/capabilities/packs/quality/standards").json()
    after_pack = next(item for item in after["packs"] if item["pack_id"] == pack_id)
    assert after_pack["status"] == "ready"
    assert after_pack["blockers"] == []

    surface = client.get("/plugins/capabilities/packs/operator/surface").json()
    assert (
        surface["routes"]["quality_standard_remediation_apply_route"]
        == "/plugins/capabilities/packs/quality/standards/remediation/apply"
    )


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

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    expected_pack_id = "ops.quality_evidence_remediation"
    expected_pack_version = "1.0.0"
    meta = {
        **_forge_promotion_meta("capability_quality_evidence_remediation"),
        "pack_id": expected_pack_id,
        "pack_version": expected_pack_version,
        "pack_name": "Ops Quality Evidence Remediation Pack",
    }
    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Quality Evidence Remediation Plugin",
            "description": "Stage 17 quality evidence remediation coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": meta,
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    recorded = client.post(
        "/plugins/capabilities/packs/metadata/receipts",
        json={
            "reason": "record reviewed migration plan candidate before quality remediation readback",
            "actor": _PLUGIN_ACTOR,
            "pack_id": expected_pack_id,
            "pack_version": expected_pack_version,
            "pack_name": "Ops Quality Evidence Remediation Pack",
            "capability_ids": [plugin_id],
            "promotion_rules": [
                "metadata_receipt_before_promotion",
                "quality_standards_before_promotion",
                "operator_review_before_promotion",
            ],
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
    pack_id = str(recorded_body["receipt"]["pack_id"])
    pack_version = str(recorded_body["receipt"]["pack_version"])

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
    assert body["governance"]["does_not_read_receipt_bodies"] is False
    assert body["governance"]["does_not_read_proposal_bodies"] is False
    assert body["governance"]["reads_validation_receipt_bodies_for_plugin_id_match"] is True
    assert body["governance"]["reads_proposal_bodies_for_plugin_id_match"] is True
    assert body["governance"]["does_not_write_receipts"] is True
    assert body["governance"]["does_not_write_validation_receipts"] is True
    assert body["governance"]["does_not_write_proposals"] is True
    assert body["governance"]["does_not_mutate_registry"] is True
    assert body["governance"]["does_not_promote_capabilities"] is True
    assert body["governance"]["promotion_authority"] is False
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["memory_write"] is False
    assert body["reference_candidates"]["pack_specific_coverage_claimed"] is False
    assert body["artifact_link_candidates"]["selection_policy"] == (
        "unique_existing_artifact_with_matching_plugin_id_only"
    )
    assert body["artifact_link_candidates"]["writes_validation_receipts"] is False
    assert body["artifact_link_candidates"]["writes_proposals"] is False
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
    validation_backfill = item["evidence_backfill"]["validation_receipt"]
    assert validation_backfill["candidate_reference_count"] >= 1
    assert validation_backfill["claim_scope"] == "existing_pack_specific_plugin_validation_receipt"
    assert validation_backfill["candidate_apply_supported"] is (validation_backfill["missing_candidate_count"] == 0)
    assert validation_backfill["reason"] in (
        "existing_pack_specific_validation_receipt_available",
        "requires_pack_specific_validation_receipt_writer",
    )
    if validation_backfill["candidate_apply_supported"]:
        assert validation_backfill["links"]
    else:
        assert validation_backfill["missing_candidate_count"] >= 1

    proposal_backfill = item["evidence_backfill"]["forge_proposal"]
    assert proposal_backfill["candidate_reference_count"] >= 1
    assert proposal_backfill["claim_scope"] == "existing_plugin_proposal_lineage_only_not_approval"
    assert proposal_backfill["candidate_apply_supported"] is (proposal_backfill["missing_candidate_count"] == 0)
    assert proposal_backfill["reason"] in (
        "existing_plugin_proposal_lineage_available",
        "requires_explicit_lineage_reconstruction_or_proposal_link",
    )
    if proposal_backfill["candidate_apply_supported"]:
        assert proposal_backfill["links"]
    else:
        assert proposal_backfill["missing_candidate_count"] >= 1
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


def test_plugins_capability_pack_quality_evidence_remediation_skips_oversized_artifact_payloads(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.api.routes import plugins

    proposals_dir = data_root / "artifacts" / "plugins" / "proposals"
    proposals_dir.mkdir(parents=True)
    oversized_body = (
        '{"plugin_id":"'
        + ("x" * plugins._PLUGIN_ARTIFACT_LINK_BODY_MAX_BYTES)
        + '","proposal_id":"proposal_oversized"}'
    )
    (proposals_dir / "proposal_oversized.json").write_text(oversized_body, encoding="utf-8")

    payload_scan = plugins._plugin_artifact_payloads("proposals")
    assert payload_scan["items"] == []
    assert payload_scan["artifact_body_max_bytes"] == plugins._PLUGIN_ARTIFACT_LINK_BODY_MAX_BYTES
    assert payload_scan["oversized_artifact_count"] == 1
    assert payload_scan["unreadable_artifact_count"] == 0

    candidates = plugins._capability_pack_existing_artifact_link_candidates()
    assert candidates["artifact_body_max_bytes"] == plugins._PLUGIN_ARTIFACT_LINK_BODY_MAX_BYTES
    assert candidates["skips_oversized_artifacts"] is True
    assert candidates["proposals"]["candidate_count"] == 0
    assert candidates["proposals"]["oversized_artifact_count"] == 1


def test_plugins_capability_pack_quality_evidence_remediation_projects_artifact_reconstruction_plan(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Artifact Reconstruction Plan Plugin",
            "description": "Stage 17 artifact reconstruction planning coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": _forge_promotion_meta("capability_artifact_reconstruction_plan"),
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    pack_id = "ops.artifact_reconstruction_plan"
    pack_version = "1.0.0"
    recorded = client.post(
        "/plugins/capabilities/packs/metadata/receipts",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "record reviewed pack metadata before artifact reconstruction planning",
            "pack_id": pack_id,
            "pack_version": pack_version,
            "pack_name": "Ops Artifact Reconstruction Plan Pack",
            "capability_ids": [plugin_id],
            "promotion_rules": [
                "metadata_receipt_before_promotion",
                "quality_standards_before_promotion",
                "operator_review_before_promotion",
            ],
            "pack_governance": {
                "risk_tier": "normal",
                "scope": "build_dev",
                "operator_review_required": True,
                "requires_validation_receipt": True,
            },
        },
    )
    assert recorded.status_code == 200
    assert recorded.json()["ok"] is True

    validation_path = (
        data_root / "artifacts" / "plugins" / "validations" / f"{built_body['validation_receipt_id']}.json"
    )
    proposal_path = data_root / "artifacts" / "plugins" / "proposals" / f"{built_body['proposal_id']}.json"
    validation_path.unlink()
    proposal_path.unlink()

    registry = plugins._load_registry()
    plugin = plugins._read_plugin(registry, plugin_id)
    assert plugin is not None
    meta = dict(plugin.get("meta") or {})
    for key in (
        "tests",
        "test_refs",
        "docs",
        "documentation",
        "quality",
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
    assert body["requirements"]["artifact_reconstruction_plan_is_read_only"] is True
    assert body["requirements"]["artifact_reconstruction_writer_not_implemented"] is False
    assert (
        body["requirements"]["artifact_reconstruction_writer_route"]
        == "/plugins/capabilities/packs/quality/evidence/remediation/reconstruct"
    )
    assert body["governance"]["artifact_reconstruction_plan_only"] is True
    assert body["governance"]["artifact_reconstruction_writer_implemented"] is True
    assert body["artifact_reconstruction_required_count"] >= 1
    assert body["validation_receipt_reconstruction_required_count"] >= 1
    assert body["proposal_lineage_reconstruction_required_count"] >= 1

    item = next(entry for entry in body["remediation_queue"] if entry["pack_id"] == pack_id)
    assert item["pack_version"] == pack_version
    validation_backfill = item["evidence_backfill"]["validation_receipt"]
    proposal_backfill = item["evidence_backfill"]["forge_proposal"]
    assert validation_backfill["candidate_apply_supported"] is False
    assert validation_backfill["candidate_reference_count"] == 0
    assert proposal_backfill["candidate_apply_supported"] is False
    assert proposal_backfill["candidate_reference_count"] == 0

    reconstruction = item["artifact_reconstruction_plan"]
    assert reconstruction["required"] is True
    assert reconstruction["read_only"] is True
    assert reconstruction["writer_implemented"] is True
    assert reconstruction["writer_route"] == "/plugins/capabilities/packs/quality/evidence/remediation/reconstruct"
    assert reconstruction["selection_policy"] == "missing_pack_specific_artifact_after_existing_link_scan"
    assert reconstruction["validation_receipt_reconstruction_required_count"] == 1
    assert reconstruction["proposal_lineage_reconstruction_required_count"] == 1
    assert reconstruction["does_not_write_validation_receipts"] is True
    assert reconstruction["does_not_write_proposals"] is True
    assert reconstruction["does_not_approve_proposals"] is True
    assert reconstruction["next_smallest_truthful_gap"] == ("stage17_capability_pack_artifact_reconstruction_apply")

    capability_plan = reconstruction["capabilities"][0]
    assert capability_plan["capability"] == plugin_id
    assert capability_plan["needs_validation_receipt"] is True
    assert capability_plan["needs_proposal_lineage"] is True
    assert capability_plan["available_inputs"]["registry_metadata"] is True
    assert capability_plan["available_inputs"]["pack_metadata_receipt"] is True
    assert capability_plan["available_inputs"]["existing_validation_receipt_link"] is False
    assert capability_plan["available_inputs"]["existing_proposal_lineage_link"] is False
    assert "quality_test_references" in capability_plan["missing_inputs"]
    assert "quality_doc_references" in capability_plan["missing_inputs"]
    assert "explicit_proposal_lineage_source_or_operator_reconstruction_decision" in (capability_plan["missing_inputs"])
    assert (
        "create_or_attach_pack_specific_validation_receipt_after_validation"
        in (capability_plan["next_writer_requirements"])
    )
    assert (
        "create_or_attach_explicit_proposal_lineage_without_approval_claim"
        in (capability_plan["next_writer_requirements"])
    )
    assert "operator_review_before_artifact_write" in capability_plan["next_writer_requirements"]

    post_readback = plugins._read_plugin(plugins._load_registry(), plugin_id)
    assert post_readback is not None
    post_meta = dict(post_readback.get("meta") or {})
    assert "proposal_id" not in post_meta
    assert "validation_receipt_id" not in post_meta
    assert not validation_path.exists()
    assert not proposal_path.exists()


def test_plugins_capability_pack_quality_evidence_remediation_reconstructs_missing_artifacts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Artifact Reconstruction Writer Plugin",
            "description": "Stage 17 governed artifact reconstruction writer coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": _forge_promotion_meta("capability_artifact_reconstruction_writer"),
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    pack_id = "ops.artifact_reconstruction_writer"
    pack_version = "1.0.0"
    recorded = client.post(
        "/plugins/capabilities/packs/metadata/receipts",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "record reviewed pack metadata before artifact reconstruction writer",
            "pack_id": pack_id,
            "pack_version": pack_version,
            "pack_name": "Ops Artifact Reconstruction Writer Pack",
            "capability_ids": [plugin_id],
            "promotion_rules": [
                "metadata_receipt_before_promotion",
                "quality_standards_before_promotion",
                "operator_review_before_promotion",
            ],
            "pack_governance": {
                "risk_tier": "normal",
                "scope": "build_dev",
                "operator_review_required": True,
                "requires_validation_receipt": True,
            },
        },
    )
    assert recorded.status_code == 200
    assert recorded.json()["ok"] is True

    original_validation_path = (
        data_root / "artifacts" / "plugins" / "validations" / f"{built_body['validation_receipt_id']}.json"
    )
    original_proposal_path = data_root / "artifacts" / "plugins" / "proposals" / f"{built_body['proposal_id']}.json"
    original_validation_path.unlink()
    original_proposal_path.unlink()

    registry = plugins._load_registry()
    plugin = plugins._read_plugin(registry, plugin_id)
    assert plugin is not None
    meta = dict(plugin.get("meta") or {})
    for key in (
        "proposal_id",
        "forge_proposal_id",
        "proposal_path",
        "validation_receipt_id",
        "validation_receipt_path",
    ):
        meta.pop(key, None)
    meta["quality"] = {
        "tests": ["tests/test_api_plugins.py"],
        "docs": ["README.md", "docs/operations/COMPLETION_LEDGER.md"],
        "claim_scope": "explicit_reconstruction_fixture_quality_references",
        "pack_specific_coverage_claimed": False,
    }
    plugin["meta"] = meta
    plugins._write_plugin(registry, plugins._normalize_plugin_record(plugin_id, plugin))
    plugins._save_registry_and_catalog(registry)

    before = client.get("/plugins/capabilities/packs/quality/evidence/remediation").json()
    before_item = next(item for item in before["remediation_queue"] if item["pack_id"] == pack_id)
    reconstruction = before_item["artifact_reconstruction_plan"]
    assert reconstruction["required"] is True
    assert reconstruction["writer_implemented"] is True
    assert reconstruction["writer_route"] == "/plugins/capabilities/packs/quality/evidence/remediation/reconstruct"
    capability_plan = reconstruction["capabilities"][0]
    assert capability_plan["capability"] == plugin_id
    assert capability_plan["needs_validation_receipt"] is True
    assert capability_plan["needs_proposal_lineage"] is True
    assert "quality_test_references" not in capability_plan["missing_inputs"]
    assert "quality_doc_references" not in capability_plan["missing_inputs"]

    dry_run = client.post(
        "/plugins/capabilities/packs/quality/evidence/remediation/reconstruct",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "dry run reviewed artifact reconstruction",
            "pack_ids": [pack_id],
            "dry_run": True,
        },
    )
    assert dry_run.status_code == 200
    dry_run_body = dry_run.json()
    assert dry_run_body["ok"] is True
    assert dry_run_body["status"] == "dry_run"
    assert dry_run_body["planned_pack_count"] == 1
    assert dry_run_body["planned"][0]["validation_receipts"]["count"] == 1
    assert dry_run_body["planned"][0]["validation_receipts"]["writes_validation_receipts"] is False
    assert dry_run_body["planned"][0]["proposal_lineages"]["count"] == 1
    assert dry_run_body["planned"][0]["proposal_lineages"]["writes_proposals"] is False
    assert dry_run_body["governance"]["writes_registry_metadata"] is False
    post_dry_run = plugins._read_plugin(plugins._load_registry(), plugin_id)
    assert post_dry_run is not None
    post_dry_meta = dict(post_dry_run.get("meta") or {})
    assert "proposal_id" not in post_dry_meta
    assert "validation_receipt_id" not in post_dry_meta

    blocked = client.post(
        "/plugins/capabilities/packs/quality/evidence/remediation/reconstruct",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "missing operator reconstruction decision",
            "pack_ids": [pack_id],
        },
    )
    assert blocked.status_code == 200
    blocked_body = blocked.json()
    assert blocked_body["ok"] is False
    assert blocked_body["applied"] is False
    assert blocked_body["error"] == "operator_reconstruction_decision_required"
    assert blocked_body["governance"]["writes_validation_receipts"] is False
    assert blocked_body["governance"]["writes_proposals"] is False
    post_blocked = plugins._read_plugin(plugins._load_registry(), plugin_id)
    assert post_blocked is not None
    post_blocked_meta = dict(post_blocked.get("meta") or {})
    assert "proposal_id" not in post_blocked_meta
    assert "validation_receipt_id" not in post_blocked_meta

    applied = client.post(
        "/plugins/capabilities/packs/quality/evidence/remediation/reconstruct",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "operator approved bounded artifact reconstruction",
            "pack_ids": [pack_id],
            "max_pack_count": 1,
            "meta": {"operator_reconstruction_decision": "approved_for_reconstruction"},
        },
    )

    assert applied.status_code == 200
    applied_body = applied.json()
    assert applied_body["ok"] is True
    assert applied_body["applied"] is True
    assert applied_body["status"] == "recorded"
    assert applied_body["planned_pack_count"] == 1
    assert applied_body["recorded_pack_count"] == 1
    assert applied_body["recorded_capability_count"] == 1
    assert applied_body["governance"]["writes_registry_metadata"] is True
    assert applied_body["governance"]["writes_validation_receipts"] is True
    assert applied_body["governance"]["writes_proposals"] is True
    assert applied_body["governance"]["operator_reconstruction_decision_captured"] is True
    assert applied_body["governance"]["proposal_lineage_does_not_approve_proposals"] is True
    assert applied_body["governance"]["does_not_promote_capabilities"] is True
    assert applied_body["governance"]["does_not_execute_capabilities"] is True

    recorded_item = applied_body["recorded"][0]
    assert recorded_item["pack_id"] == pack_id
    assert recorded_item["reconstructed_capability_count"] == 1
    validation_record = recorded_item["validation_receipts"][0]
    proposal_record = recorded_item["proposal_lineages"][0]
    validation_id = validation_record["validation_receipt_id"]
    proposal_id = proposal_record["proposal_id"]
    validation_path = data_root / "artifacts" / "plugins" / "validations" / f"{validation_id}.json"
    proposal_path = data_root / "artifacts" / "plugins" / "proposals" / f"{proposal_id}.json"
    assert validation_path.exists()
    assert proposal_path.exists()

    validation_payload = json.loads(validation_path.read_text(encoding="utf-8"))
    assert validation_payload["kind"] == "plugin.validation.receipt"
    assert validation_payload["plugin_id"] == plugin_id
    assert validation_payload["status"] == "passed"
    assert validation_payload["valid"] is True
    assert validation_payload["governance"]["route"] == (
        "/plugins/capabilities/packs/quality/evidence/remediation/reconstruct"
    )
    assert validation_payload["governance"]["does_not_approve_proposals"] is True
    proposal_payload = json.loads(proposal_path.read_text(encoding="utf-8"))
    assert proposal_payload["kind"] == "plugin.proposal"
    assert proposal_payload["plugin_id"] == plugin_id
    assert proposal_payload["status"] == "reconstructed_lineage"
    assert proposal_payload["review"]["approval_claimed"] is False
    assert proposal_payload["governance"]["does_not_approve_proposals"] is True

    post_apply_plugin = plugins._read_plugin(plugins._load_registry(), plugin_id)
    assert post_apply_plugin is not None
    stored_meta = dict(post_apply_plugin.get("meta") or {})
    assert stored_meta["validation_receipt_id"] == validation_id
    assert stored_meta["validation_receipt_path"] == f"data/artifacts/plugins/validations/{validation_id}.json"
    assert stored_meta["proposal_id"] == proposal_id
    assert stored_meta["proposal_path"] == f"data/artifacts/plugins/proposals/{proposal_id}.json"
    assert stored_meta["proposal_lineage_approval_claimed"] is False
    assert stored_meta["proposal_status"] == "reconstructed_lineage_unreviewed"
    assert stored_meta["artifact_reconstruction_source"] == "stage17_capability_pack_artifact_reconstruction_apply"
    stored_quality = stored_meta["quality"]
    assert stored_quality["validation_receipt_written"] is True
    assert stored_quality["proposal_lineage_written"] is True
    assert stored_quality["pack_specific_coverage_claimed"] is False

    after = client.get("/plugins/capabilities/packs/quality/evidence/remediation").json()
    assert all(item["pack_id"] != pack_id for item in after["remediation_queue"])


def test_plugins_capability_pack_quality_evidence_remediation_reconstructs_truncated_plan_chunk(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    capability_limit = plugins._CAPABILITY_PACK_ARTIFACT_RECONSTRUCTION_PLAN_LIMIT
    plugin_ids: list[str] = []
    built_bodies: list[dict[str, object]] = []
    for index in range(capability_limit + 1):
        built = client.post(
            "/plugins/build",
            json={
                "name": f"Capability Artifact Reconstruction Chunk Plugin {index}",
                "description": "Stage 17 bounded chunk reconstruction coverage",
                "actor": _PLUGIN_ACTOR,
                "meta": _forge_promotion_meta(f"capability_artifact_reconstruction_chunk_{index}"),
            },
        )
        assert built.status_code == 200
        built_body = built.json()
        assert built_body["ok"] is True
        plugin_ids.append(str(built_body["plugin_id"]))
        built_bodies.append(built_body)

    pack_id = "ops.artifact_reconstruction_chunk"
    pack_version = "1.0.0"
    recorded = client.post(
        "/plugins/capabilities/packs/metadata/receipts",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "record reviewed large pack metadata before chunk reconstruction",
            "pack_id": pack_id,
            "pack_version": pack_version,
            "pack_name": "Ops Artifact Reconstruction Chunk Pack",
            "capability_ids": plugin_ids,
            "promotion_rules": [
                "metadata_receipt_before_promotion",
                "quality_standards_before_promotion",
                "operator_review_before_promotion",
            ],
            "pack_governance": {
                "risk_tier": "normal",
                "scope": "build_dev",
                "operator_review_required": True,
                "requires_validation_receipt": True,
            },
        },
    )
    assert recorded.status_code == 200
    assert recorded.json()["ok"] is True

    registry = plugins._load_registry()
    for plugin_id, built_body in zip(plugin_ids, built_bodies, strict=True):
        validation_id = str(built_body["validation_receipt_id"])
        proposal_id = str(built_body["proposal_id"])
        (data_root / "artifacts" / "plugins" / "validations" / f"{validation_id}.json").unlink(missing_ok=True)
        (data_root / "artifacts" / "plugins" / "proposals" / f"{proposal_id}.json").unlink(missing_ok=True)

        plugin = plugins._read_plugin(registry, plugin_id)
        assert plugin is not None
        meta = dict(plugin.get("meta") or {})
        for key in (
            "proposal_id",
            "forge_proposal_id",
            "proposal_path",
            "validation_receipt_id",
            "validation_receipt_path",
        ):
            meta.pop(key, None)
        meta["quality"] = {
            "tests": ["tests/test_api_plugins.py"],
            "docs": ["README.md", "docs/operations/COMPLETION_LEDGER.md"],
            "claim_scope": "explicit_reconstruction_chunk_fixture_quality_references",
            "pack_specific_coverage_claimed": False,
        }
        plugin["meta"] = meta
        plugins._write_plugin(registry, plugins._normalize_plugin_record(plugin_id, plugin))
    plugins._save_registry_and_catalog(registry)

    before = client.get("/plugins/capabilities/packs/quality/evidence/remediation").json()
    before_item = next(item for item in before["remediation_queue"] if item["pack_id"] == pack_id)
    reconstruction = before_item["artifact_reconstruction_plan"]
    assert reconstruction["required"] is True
    assert reconstruction["capability_count"] == capability_limit + 1
    assert reconstruction["capabilities_truncated"] is True
    assert len(reconstruction["capabilities"]) == capability_limit

    request_body = {
        "actor": _PLUGIN_ACTOR,
        "reason": "operator approved bounded artifact reconstruction chunk",
        "pack_ids": [pack_id],
        "max_pack_count": 1,
        "max_total_capability_count": capability_limit,
        "max_capability_count_per_pack": capability_limit,
    }
    dry_run = client.post(
        "/plugins/capabilities/packs/quality/evidence/remediation/reconstruct",
        json={**request_body, "dry_run": True},
    )
    assert dry_run.status_code == 200
    dry_run_body = dry_run.json()
    assert dry_run_body["ok"] is True
    assert dry_run_body["status"] == "dry_run"
    assert dry_run_body["planned_capability_count"] == capability_limit
    assert dry_run_body["partial_reconstruction_count"] == 1
    planned_item = dry_run_body["planned"][0]
    assert planned_item["capability_count"] == capability_limit
    assert planned_item["required_capability_count"] == capability_limit + 1
    assert planned_item["capabilities_truncated"] is True
    assert planned_item["partial_reconstruction"] is True
    assert planned_item["partial_reconstruction_does_not_claim_pack_complete"] is True
    assert dry_run_body["governance"]["writes_validation_receipts"] is False
    assert dry_run_body["governance"]["writes_proposals"] is False
    assert dry_run_body["governance"]["partial_reconstruction_does_not_claim_pack_complete"] is True

    applied = client.post(
        "/plugins/capabilities/packs/quality/evidence/remediation/reconstruct",
        json={
            **request_body,
            "meta": {"operator_reconstruction_decision": "approved_for_reconstruction"},
        },
    )
    assert applied.status_code == 200
    applied_body = applied.json()
    assert applied_body["ok"] is True
    assert applied_body["applied"] is True
    assert applied_body["status"] == "recorded"
    assert applied_body["planned_pack_count"] == 1
    assert applied_body["recorded_capability_count"] == capability_limit
    assert applied_body["partial_reconstruction_count"] == 1
    assert applied_body["governance"]["partial_reconstruction_does_not_claim_pack_complete"] is True

    recorded_item = applied_body["recorded"][0]
    assert recorded_item["capability_count"] == capability_limit
    assert recorded_item["required_capability_count"] == capability_limit + 1
    assert recorded_item["capabilities_truncated"] is True
    assert recorded_item["partial_reconstruction"] is True
    assert recorded_item["partial_reconstruction_does_not_claim_pack_complete"] is True
    assert recorded_item["reconstructed_capability_count"] == capability_limit

    post_registry = plugins._load_registry()
    reconstructed_ids: list[str] = []
    unreconstructed_ids: list[str] = []
    for plugin_id in plugin_ids:
        plugin = plugins._read_plugin(post_registry, plugin_id)
        assert plugin is not None
        meta = dict(plugin.get("meta") or {})
        if meta.get("validation_receipt_id") and meta.get("proposal_id"):
            reconstructed_ids.append(plugin_id)
            assert meta["artifact_reconstruction_partial_pack"] is True
            assert meta["artifact_reconstruction_pack_required_capability_count"] == capability_limit + 1
            assert meta["artifact_reconstruction_pack_chunk_capability_count"] == capability_limit
        else:
            unreconstructed_ids.append(plugin_id)
    assert len(reconstructed_ids) == capability_limit
    assert len(unreconstructed_ids) == 1

    remaining_item = next(item for item in applied_body["remaining_remediation_queue"] if item["pack_id"] == pack_id)
    remaining_plan = remaining_item["artifact_reconstruction_plan"]
    assert remaining_plan["required"] is True
    assert remaining_plan["capability_count"] == 1
    assert remaining_plan["capabilities_truncated"] is False


def test_plugins_capability_pack_quality_evidence_remediation_apply_backfills_candidate_refs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Quality Evidence Remediation Apply Plugin",
            "description": "Stage 17 quality evidence remediation apply coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": _forge_promotion_meta("capability_quality_evidence_remediation_apply"),
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])

    pack_id = "ops.quality_evidence_remediation_apply"
    pack_version = "1.0.0"
    recorded = client.post(
        "/plugins/capabilities/packs/metadata/receipts",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "record reviewed pack metadata before quality remediation apply",
            "pack_id": pack_id,
            "pack_version": pack_version,
            "pack_name": "Ops Quality Evidence Remediation Apply Pack",
            "capability_ids": [plugin_id],
            "promotion_rules": [
                "metadata_receipt_before_promotion",
                "quality_standards_before_promotion",
                "operator_review_before_promotion",
            ],
            "pack_governance": {
                "risk_tier": "normal",
                "scope": "build_dev",
                "operator_review_required": True,
                "requires_validation_receipt": True,
            },
        },
    )
    assert recorded.status_code == 200
    recorded_body = recorded.json()
    assert recorded_body["ok"] is True

    registry = plugins._load_registry()
    plugin = plugins._read_plugin(registry, plugin_id)
    assert plugin is not None
    meta = dict(plugin.get("meta") or {})
    for key in (
        "tests",
        "test_refs",
        "docs",
        "documentation",
        "quality",
        "quality_reference_remediation_source",
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

    before = client.get("/plugins/capabilities/packs/quality/evidence/remediation").json()
    before_item = next(item for item in before["remediation_queue"] if item["pack_id"] == pack_id)
    assert before_item["pack_version"] == pack_version
    assert before_item["blockers"] == [
        "tests_missing",
        "docs_missing",
        "validation_receipt_missing",
        "proposal_id_missing",
    ]
    assert before_item["quality_reference_backfill_candidate"] is True
    receipts_before = client.get("/plugins/capabilities/packs/metadata/receipts?limit=20").json()["items"]

    dry_run = client.post(
        "/plugins/capabilities/packs/quality/evidence/remediation/apply",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "dry run reviewed quality reference remediation",
            "pack_ids": [pack_id],
            "dry_run": True,
        },
    )
    assert dry_run.status_code == 200
    dry_run_body = dry_run.json()
    assert dry_run_body["ok"] is True
    assert dry_run_body["status"] == "dry_run"
    assert dry_run_body["planned_pack_count"] == 1
    assert dry_run_body["planned"][0]["validation_receipt_links"]["count"] == 1
    assert dry_run_body["planned"][0]["proposal_lineage_links"]["count"] == 1
    assert dry_run_body["governance"]["writes_registry_metadata"] is False
    post_dry_run = plugins._read_plugin(plugins._load_registry(), plugin_id)
    assert post_dry_run is not None
    assert "quality" not in dict(post_dry_run.get("meta") or {})

    applied = client.post(
        "/plugins/capabilities/packs/quality/evidence/remediation/apply",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "apply reviewed quality reference remediation",
            "pack_ids": [pack_id],
            "max_pack_count": 1,
        },
    )

    assert applied.status_code == 200
    applied_body = applied.json()
    assert applied_body["ok"] is True
    assert applied_body["applied"] is True
    assert applied_body["status"] == "recorded"
    assert applied_body["planned_pack_count"] == 1
    assert applied_body["recorded_pack_count"] == 1
    assert applied_body["recorded_capability_count"] == 1
    assert applied_body["governance"]["writes_registry_metadata"] is True
    assert applied_body["governance"]["writes_receipts"] is False
    assert applied_body["governance"]["quality_reference_backfill_only"] is False
    assert applied_body["governance"]["existing_artifact_link_backfill_supported"] is True
    assert applied_body["governance"]["candidate_references_do_not_claim_pack_specific_coverage"] is True
    assert applied_body["governance"]["does_not_write_validation_receipts"] is True
    assert applied_body["governance"]["does_not_write_proposals"] is True
    assert applied_body["governance"]["validation_receipt_links_require_existing_artifacts"] is True
    assert applied_body["governance"]["proposal_lineage_links_require_existing_artifacts"] is True
    assert applied_body["governance"]["proposal_lineage_links_do_not_approve_proposals"] is True
    assert applied_body["governance"]["does_not_promote_capabilities"] is True
    assert applied_body["governance"]["does_not_execute_capabilities"] is True
    assert applied_body["governance"]["promotion_authority"] is False
    assert applied_body["governance"]["execution_authority"] is False

    recorded_item = applied_body["recorded"][0]
    assert recorded_item["pack_id"] == pack_id
    assert recorded_item["applied_evidence_blockers"] == [
        "tests_missing",
        "docs_missing",
        "validation_receipt_missing",
        "proposal_id_missing",
    ]
    assert recorded_item["quality_references"]["tests"] == ["tests/test_api_plugins.py"]
    assert recorded_item["quality_references"]["docs"] == ["README.md", "docs/operations/COMPLETION_LEDGER.md"]
    assert recorded_item["quality_references"]["pack_specific_coverage_claimed"] is False
    assert recorded_item["validation_receipt_links"]["count"] == 1
    assert recorded_item["validation_receipt_links"]["writes_validation_receipts"] is False
    assert recorded_item["proposal_lineage_links"]["count"] == 1
    assert recorded_item["proposal_lineage_links"]["proposal_approval_claimed"] is False
    assert recorded_item["proposal_lineage_links"]["writes_proposals"] is False

    catalog = client.get("/plugins/capabilities/catalog?limit=5000").json()
    entry = next(item for item in catalog["items"] if item["capability"] == plugin_id)
    metadata = entry["metadata"]
    catalog_quality = entry["quality"]
    assert catalog_quality["tests"] == ["tests/test_api_plugins.py"]
    assert catalog_quality["docs"] == ["README.md", "docs/operations/COMPLETION_LEDGER.md"]
    assert entry["proposal_id"] == built_body["proposal_id"]
    assert metadata["validation_receipt_id"] == built_body["validation_receipt_id"]
    post_apply_plugin = plugins._read_plugin(plugins._load_registry(), plugin_id)
    assert post_apply_plugin is not None
    stored_meta = dict(post_apply_plugin.get("meta") or {})
    stored_quality = stored_meta["quality"]
    assert stored_quality["tests"] == ["tests/test_api_plugins.py"]
    assert stored_quality["docs"] == ["README.md", "docs/operations/COMPLETION_LEDGER.md"]
    assert stored_quality["claim_scope"] == "candidate_reference_only_not_pack_specific_proof"
    assert stored_quality["pack_specific_coverage_claimed"] is False
    assert stored_quality["validation_receipt_written"] is False
    assert stored_quality["proposal_lineage_written"] is False
    assert stored_meta["quality_reference_remediation_source"] == (
        "stage17_capability_pack_quality_evidence_remediation_apply"
    )
    assert stored_meta["proposal_id"] == built_body["proposal_id"]
    assert stored_meta["proposal_path"] == f"data/artifacts/plugins/proposals/{built_body['proposal_id']}.json"
    assert stored_meta["proposal_lineage_link_source"] == "stage17_capability_pack_quality_evidence_remediation_apply"
    assert stored_meta["proposal_lineage_approval_claimed"] is False
    assert stored_meta["validation_receipt_id"] == built_body["validation_receipt_id"]
    assert stored_meta["validation_receipt_path"] == (
        f"data/artifacts/plugins/validations/{built_body['validation_receipt_id']}.json"
    )
    assert stored_meta["validation_receipt_link_source"] == (
        "stage17_capability_pack_quality_evidence_remediation_apply"
    )

    receipts_after = client.get("/plugins/capabilities/packs/metadata/receipts?limit=20").json()["items"]
    assert [item["receipt_id"] for item in receipts_after] == [item["receipt_id"] for item in receipts_before]

    assert all(item["pack_id"] != pack_id for item in applied_body["remaining_remediation_queue"])

    after = client.get("/plugins/capabilities/packs/quality/evidence/remediation").json()
    assert all(item["pack_id"] != pack_id for item in after["remediation_queue"])


def test_plugins_capability_pack_quality_evidence_remediation_links_existing_artifacts_in_chunks(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    capability_count = plugins._CAPABILITY_PACK_QUALITY_EVIDENCE_CAPABILITY_PREVIEW_LIMIT + 1
    link_chunk_limit = plugins._CAPABILITY_PACK_QUALITY_EVIDENCE_LINK_PREVIEW_LIMIT
    plugin_ids: list[str] = []
    for index in range(capability_count):
        built = client.post(
            "/plugins/build",
            json={
                "name": f"Capability Quality Existing Link Chunk Plugin {index}",
                "description": "Stage 17 existing artifact chunk link coverage",
                "actor": _PLUGIN_ACTOR,
                "meta": _forge_promotion_meta(f"capability_quality_existing_link_chunk_{index}"),
            },
        )
        assert built.status_code == 200
        built_body = built.json()
        assert built_body["ok"] is True
        plugin_ids.append(str(built_body["plugin_id"]))

    pack_id = "ops.quality_existing_link_chunk"
    pack_version = "1.0.0"
    recorded = client.post(
        "/plugins/capabilities/packs/metadata/receipts",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "record reviewed large pack metadata before existing artifact link chunking",
            "pack_id": pack_id,
            "pack_version": pack_version,
            "pack_name": "Ops Quality Existing Link Chunk Pack",
            "capability_ids": plugin_ids,
            "promotion_rules": [
                "metadata_receipt_before_promotion",
                "quality_standards_before_promotion",
                "operator_review_before_promotion",
            ],
            "pack_governance": {
                "risk_tier": "normal",
                "scope": "build_dev",
                "operator_review_required": True,
                "requires_validation_receipt": True,
            },
        },
    )
    assert recorded.status_code == 200
    assert recorded.json()["ok"] is True

    registry = plugins._load_registry()
    for plugin_id in plugin_ids:
        plugin = plugins._read_plugin(registry, plugin_id)
        assert plugin is not None
        meta = dict(plugin.get("meta") or {})
        for key in (
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

    before = client.get("/plugins/capabilities/packs/quality/evidence/remediation").json()
    before_item = next(item for item in before["remediation_queue"] if item["pack_id"] == pack_id)
    assert before_item["capability_count"] == capability_count
    assert len(before_item["capability_ids"]) == plugins._CAPABILITY_PACK_QUALITY_EVIDENCE_CAPABILITY_PREVIEW_LIMIT
    assert before_item["capability_ids_truncated"] is True
    assert before_item["quality_reference_backfill_candidate"] is False
    validation_backfill = before_item["evidence_backfill"]["validation_receipt"]
    proposal_backfill = before_item["evidence_backfill"]["forge_proposal"]
    assert validation_backfill["candidate_reference_count"] == capability_count
    assert validation_backfill["candidate_apply_supported"] is True
    assert validation_backfill["missing_candidate_count"] == 0
    assert len(validation_backfill["links"]) == link_chunk_limit
    assert validation_backfill["links_truncated"] is True
    assert proposal_backfill["candidate_reference_count"] == capability_count
    assert proposal_backfill["candidate_apply_supported"] is True
    assert proposal_backfill["missing_candidate_count"] == 0
    assert len(proposal_backfill["links"]) == link_chunk_limit
    assert proposal_backfill["links_truncated"] is True
    assert before_item["artifact_reconstruction_plan"]["required"] is False

    chunk_request = {
        "actor": _PLUGIN_ACTOR,
        "reason": "apply bounded existing artifact link chunk",
        "pack_ids": [pack_id],
        "max_pack_count": 1,
        "max_total_capability_count": link_chunk_limit,
        "max_capability_count_per_pack": link_chunk_limit,
    }
    dry_run = client.post(
        "/plugins/capabilities/packs/quality/evidence/remediation/apply",
        json={**chunk_request, "dry_run": True},
    )
    assert dry_run.status_code == 200
    dry_run_body = dry_run.json()
    assert dry_run_body["ok"] is True
    assert dry_run_body["status"] == "dry_run"
    assert dry_run_body["planned_capability_count"] == link_chunk_limit
    planned_item = dry_run_body["planned"][0]
    assert planned_item["capability_count"] == capability_count
    assert planned_item["planned_registry_metadata_capability_count"] == link_chunk_limit
    assert planned_item["validation_receipt_links"]["count"] == link_chunk_limit
    assert planned_item["proposal_lineage_links"]["count"] == link_chunk_limit
    assert planned_item["partial_existing_artifact_link_backfill"] is True
    assert planned_item["partial_link_backfill_does_not_claim_pack_complete"] is True
    assert dry_run_body["governance"]["writes_registry_metadata"] is False
    assert dry_run_body["governance"]["partial_existing_artifact_link_backfill_count"] == 1
    assert dry_run_body["governance"]["partial_link_backfill_does_not_claim_pack_complete"] is True

    applied = client.post(
        "/plugins/capabilities/packs/quality/evidence/remediation/apply",
        json=chunk_request,
    )
    assert applied.status_code == 200
    applied_body = applied.json()
    assert applied_body["ok"] is True
    assert applied_body["applied"] is True
    assert applied_body["status"] == "recorded"
    assert applied_body["recorded_capability_count"] == link_chunk_limit
    assert applied_body["governance"]["writes_registry_metadata"] is True
    assert applied_body["governance"]["partial_existing_artifact_link_backfill_count"] == 1
    recorded_item = applied_body["recorded"][0]
    assert recorded_item["partial_existing_artifact_link_backfill"] is True
    assert recorded_item["partial_link_backfill_does_not_claim_pack_complete"] is True

    remaining_item = next(item for item in applied_body["remaining_remediation_queue"] if item["pack_id"] == pack_id)
    assert remaining_item["artifact_reconstruction_plan"]["required"] is False

    post_chunk_registry = plugins._load_registry()
    linked_count = 0
    unlinked_count = 0
    for plugin_id in plugin_ids:
        plugin = plugins._read_plugin(post_chunk_registry, plugin_id)
        assert plugin is not None
        meta = dict(plugin.get("meta") or {})
        if meta.get("validation_receipt_id") and meta.get("proposal_id"):
            linked_count += 1
            assert meta["validation_receipt_link_source"] == (
                "stage17_capability_pack_quality_evidence_remediation_apply"
            )
            assert meta["proposal_lineage_link_source"] == (
                "stage17_capability_pack_quality_evidence_remediation_apply"
            )
            assert meta["proposal_lineage_approval_claimed"] is False
        else:
            unlinked_count += 1
    assert linked_count == link_chunk_limit
    assert unlinked_count == capability_count - link_chunk_limit

    finish_request = {
        **chunk_request,
        "max_total_capability_count": capability_count,
        "max_capability_count_per_pack": capability_count,
    }
    finished = client.post(
        "/plugins/capabilities/packs/quality/evidence/remediation/apply",
        json=finish_request,
    )
    assert finished.status_code == 200
    finished_body = finished.json()
    assert finished_body["ok"] is True
    assert finished_body["applied"] is True
    assert finished_body["recorded_capability_count"] == capability_count - link_chunk_limit
    assert all(item["pack_id"] != pack_id for item in finished_body["remaining_remediation_queue"])

    after = client.get("/plugins/capabilities/packs/quality/evidence/remediation").json()
    assert all(item["pack_id"] != pack_id for item in after["remediation_queue"])


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
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
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
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
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

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
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


def test_plugins_capability_pack_operator_surface_projects_stage17_review_handoff(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    pack_id = "ops.operator_surface"
    pack_version = "1.0.0"
    meta = {
        **_forge_promotion_meta("capability_operator_surface"),
        "pack_id": pack_id,
        "pack_version": pack_version,
        "pack_name": "Ops Operator Surface Pack",
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
            "name": "Capability Operator Surface Plugin",
            "description": "Stage 17 operator surface coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": meta,
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True

    response = client.get("/plugins/capabilities/packs/operator/surface")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "plugin.capability_pack.operator_surface"
    assert body["stage"] == "Stage 17 / Capability Economy"
    assert body["status"] == "ready_for_operator_review"
    assert body["operator_surface_readback_ready"] is True
    assert body["pack_total"] == 1
    assert body["next_smallest_truthful_gap"] == "stage17_capability_pack_review_decisions"
    assert body["remediation_backlog"]["status"] == "clear"
    assert body["remediation_backlog"]["open_count"] == 0
    assert body["remediation_backlog"]["metadata_receipt_review_candidate_count"] == 0
    assert body["remediation_backlog"]["promotion_rule_remediation_queue_count"] == 0
    assert body["remediation_backlog"]["quality_evidence_remediation_queue_count"] == 0
    assert body["remediation_backlog"]["artifact_reconstruction_required_count"] == 0
    assert body["operator_review"]["review_queue_count"] == 1
    assert body["operator_review"]["pending_review_queue_count"] == 1
    assert body["operator_review"]["decision_recorded_pack_count"] == 0
    assert body["operator_review"]["decision_required_pack_count"] == 1
    assert body["promotion_discipline"]["blocked_pack_count"] == 1
    assert body["promotion_discipline"]["ready_pack_count"] == 0
    assert body["promotion_discipline"]["approved_pack_operator_review_count"] == 0
    assert body["routes"]["operator_review_route"] == "/plugins/capabilities/packs/operator/review"
    assert body["routes"]["operator_review_decision_route"] == "/plugins/capabilities/packs/operator/review/decisions"
    assert (
        body["routes"]["operator_review_bulk_decision_route"]
        == "/plugins/capabilities/packs/operator/review/decisions/bulk-from-surface"
    )
    assert body["routes"]["promotion_discipline_route"] == "/plugins/capabilities/packs/promotion/discipline"
    assert body["routes"]["promotion_route_after_review"] == "/plugins/enable"
    assert body["requirements"]["single_operator_readback_for_stage17_pack_handoff"] is True
    assert body["requirements"]["composes_existing_stage17_readbacks"] is True
    assert body["requirements"]["operator_review_remains_explicit_governed_decision"] is True
    assert body["requirements"]["promotion_remains_separate_governed_action"] is True
    assert body["requirements"]["no_fake_progress_status"] is True
    assert body["governance"]["read_only"] is True
    assert body["governance"]["operator_facing"] is True
    assert body["governance"]["generated_plugin_registry_sync_performed"] is False
    assert body["governance"]["does_not_mutate_registry"] is True
    assert body["governance"]["does_not_write_operator_review_decisions"] is True
    assert body["governance"]["does_not_write_metadata_receipts"] is True
    assert body["governance"]["does_not_write_validation_receipts"] is True
    assert body["governance"]["does_not_write_promotion_receipts"] is True
    assert body["governance"]["does_not_write_proposals"] is True
    assert body["governance"]["does_not_approve_proposals"] is True
    assert body["governance"]["does_not_promote_capabilities"] is True
    assert body["governance"]["does_not_enable_capabilities"] is True
    assert body["governance"]["does_not_execute_capabilities"] is True
    assert body["governance"]["promotion_authority"] is False
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["approval_authority"] is False
    assert body["governance"]["memory_write"] is False

    review_pack = next(item for item in body["operator_review"]["packs"] if item["pack_id"] == pack_id)
    assert review_pack["status"] == "ready_for_operator_review"
    assert review_pack["operator_review_ready"] is True
    assert review_pack["decision_required"] is True
    assert review_pack["blockers"] == []

    discipline_pack = next(item for item in body["promotion_discipline"]["packs"] if item["pack_id"] == pack_id)
    assert discipline_pack["status"] == "blocked"
    assert discipline_pack["ready"] is False
    assert "operator_review_decision_missing" in discipline_pack["blockers"]


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


def test_plugins_capability_pack_operator_review_bulk_from_surface_dry_runs_and_records_receipts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    pack_ids = ["ops.bulk_operator_review_a", "ops.bulk_operator_review_b"]
    for index, pack_id in enumerate(pack_ids, start=1):
        meta = {
            **_forge_promotion_meta(f"capability_operator_review_bulk_{index}"),
            "pack_id": pack_id,
            "pack_version": "1.0.0",
            "pack_name": f"Ops Bulk Operator Review Pack {index}",
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
                "name": f"Capability Bulk Operator Review Plugin {index}",
                "description": "Stage 17 bulk operator review decision coverage",
                "actor": _PLUGIN_ACTOR,
                "meta": meta,
            },
        )
        assert built.status_code == 200
        assert built.json()["ok"] is True

    dry_run = client.post(
        "/plugins/capabilities/packs/operator/review/decisions/bulk-from-surface",
        json={
            "actor": _PLUGIN_ACTOR,
            "action": "approve",
            "reason": "dry run bulk operator review decision receipts",
            "pack_ids": pack_ids,
            "max_pack_count": 2,
            "max_total_capability_count": 2,
            "dry_run": True,
        },
    )

    assert dry_run.status_code == 200
    dry_run_body = dry_run.json()
    assert dry_run_body["ok"] is True
    assert dry_run_body["kind"] == "plugin.capability_pack.operator_review.bulk_decision"
    assert dry_run_body["applied"] is False
    assert dry_run_body["status"] == "dry_run"
    assert dry_run_body["planned_pack_count"] == 2
    assert dry_run_body["planned_capability_count"] == 2
    assert dry_run_body["planned"][0]["writes_receipt"] is False
    assert dry_run_body["governance"]["dry_run_default"] is True
    assert dry_run_body["governance"]["writes_receipts"] is False
    assert dry_run_body["governance"]["does_not_mutate_registry"] is True
    assert dry_run_body["governance"]["does_not_approve_proposals"] is True
    assert dry_run_body["governance"]["does_not_promote_capabilities"] is True
    assert dry_run_body["governance"]["does_not_enable_capabilities"] is True
    assert dry_run_body["governance"]["does_not_execute_capabilities"] is True
    assert dry_run_body["governance"]["memory_write"] is False

    no_receipts = client.get("/plugins/capabilities/packs/operator/review/decisions", params={"limit": 10})
    assert no_receipts.status_code == 200
    assert no_receipts.json()["total"] == 0

    applied = client.post(
        "/plugins/capabilities/packs/operator/review/decisions/bulk-from-surface",
        json={
            "actor": _PLUGIN_ACTOR,
            "action": "approve",
            "reason": "explicit bulk operator review approval",
            "pack_ids": pack_ids,
            "max_pack_count": 2,
            "max_total_capability_count": 2,
            "dry_run": False,
            "meta": {"operator_review_batch_test": True},
        },
    )

    assert applied.status_code == 200
    applied_body = applied.json()
    assert applied_body["ok"] is True
    assert applied_body["applied"] is True
    assert applied_body["status"] == "recorded"
    assert applied_body["recorded_pack_count"] == 2
    assert applied_body["recorded_capability_count"] == 2
    assert applied_body["promotion_discipline"]["ready_pack_count"] == 2
    assert applied_body["promotion_discipline"]["blocked_pack_count"] == 0
    assert applied_body["promotion_discipline"]["approved_pack_operator_review_count"] == 2
    assert applied_body["governance"]["writes_receipts"] is True
    assert applied_body["governance"]["receipt_write_count"] == 2
    assert applied_body["governance"]["does_not_mutate_registry"] is True
    assert applied_body["governance"]["does_not_approve_proposals"] is True
    assert applied_body["governance"]["does_not_promote_capabilities"] is True
    assert applied_body["governance"]["does_not_enable_capabilities"] is True
    assert applied_body["governance"]["does_not_execute_capabilities"] is True
    assert applied_body["governance"]["promotion_authority"] is False
    assert applied_body["governance"]["execution_authority"] is False
    assert applied_body["governance"]["approval_authority"] is False
    assert applied_body["governance"]["memory_write"] is False

    receipts = client.get("/plugins/capabilities/packs/operator/review/decisions", params={"limit": 10})
    assert receipts.status_code == 200
    receipts_body = receipts.json()
    assert receipts_body["total"] == 2
    assert {item["pack_id"] for item in receipts_body["items"]} == set(pack_ids)
    assert all(item["status"] == "approved" for item in receipts_body["items"])

    surface = client.get("/plugins/capabilities/packs/operator/surface")
    assert surface.status_code == 200
    surface_body = surface.json()
    assert surface_body["status"] == "ready_for_explicit_promotion"
    assert surface_body["operator_review"]["review_queue_count"] == 2
    assert surface_body["operator_review"]["pending_review_queue_count"] == 0
    assert surface_body["operator_review"]["decision_recorded_pack_count"] == 2
    assert surface_body["promotion_discipline"]["ready_pack_count"] == 2
    assert surface_body["promotion_discipline"]["blocked_pack_count"] == 0


def test_plugins_capability_pack_operator_review_bulk_reopens_stale_capability_coverage(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    pack_id = "ops.bulk_operator_review_changed"
    pack_version = "1.0.0"
    base_meta = {
        **_forge_promotion_meta("capability_operator_review_bulk_changed"),
        "pack_id": pack_id,
        "pack_version": pack_version,
        "pack_name": "Ops Bulk Operator Review Changed Pack",
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
    first = client.post(
        "/plugins/build",
        json={
            "name": "Capability Bulk Operator Review Changed Plugin One",
            "description": "Stage 17 stale operator review coverage one",
            "actor": _PLUGIN_ACTOR,
            "meta": base_meta,
        },
    )
    assert first.status_code == 200
    assert first.json()["ok"] is True

    first_approval = client.post(
        "/plugins/capabilities/packs/operator/review/decisions/bulk-from-surface",
        json={
            "actor": _PLUGIN_ACTOR,
            "action": "approve",
            "reason": "approve first pack shape",
            "pack_ids": [pack_id],
            "max_pack_count": 1,
            "max_total_capability_count": 1,
            "dry_run": False,
        },
    )
    assert first_approval.status_code == 200
    first_approval_body = first_approval.json()
    assert first_approval_body["ok"] is True
    assert first_approval_body["recorded_pack_count"] == 1
    assert first_approval_body["recorded_capability_count"] == 1

    no_candidates = client.post(
        "/plugins/capabilities/packs/operator/review/decisions/bulk-from-surface",
        json={
            "actor": _PLUGIN_ACTOR,
            "action": "approve",
            "reason": "first shape already covered",
            "pack_ids": [pack_id],
            "max_pack_count": 1,
            "max_total_capability_count": 1,
            "dry_run": True,
        },
    ).json()
    assert no_candidates["status"] == "no_candidates"

    second = client.post(
        "/plugins/build",
        json={
            "name": "Capability Bulk Operator Review Changed Plugin Two",
            "description": "Stage 17 stale operator review coverage two",
            "actor": _PLUGIN_ACTOR,
            "meta": base_meta,
        },
    )
    assert second.status_code == 200
    assert second.json()["ok"] is True

    reopened = client.post(
        "/plugins/capabilities/packs/operator/review/decisions/bulk-from-surface",
        json={
            "actor": _PLUGIN_ACTOR,
            "action": "approve",
            "reason": "dry run changed pack shape",
            "pack_ids": [pack_id],
            "max_pack_count": 1,
            "max_total_capability_count": 2,
            "dry_run": True,
        },
    )

    assert reopened.status_code == 200
    reopened_body = reopened.json()
    assert reopened_body["ok"] is True
    assert reopened_body["status"] == "dry_run"
    assert reopened_body["planned_pack_count"] == 1
    assert reopened_body["planned_capability_count"] == 2
    assert reopened_body["planned"][0]["capability_count"] == 2

    applied = client.post(
        "/plugins/capabilities/packs/operator/review/decisions/bulk-from-surface",
        json={
            "actor": _PLUGIN_ACTOR,
            "action": "approve",
            "reason": "approve changed pack shape",
            "pack_ids": [pack_id],
            "max_pack_count": 1,
            "max_total_capability_count": 2,
            "dry_run": False,
        },
    )
    assert applied.status_code == 200
    applied_body = applied.json()
    assert applied_body["ok"] is True
    assert applied_body["recorded_pack_count"] == 1
    assert applied_body["recorded_capability_count"] == 2
    assert applied_body["promotion_discipline"]["ready_pack_count"] == 1
    assert applied_body["promotion_discipline"]["blocked_pack_count"] == 0

    decisions = client.get(
        "/plugins/capabilities/packs/operator/review/decisions",
        params={"pack_id": pack_id, "pack_version": pack_version, "limit": 10},
    ).json()
    assert decisions["total"] == 2
    assert max(item["capability_count"] for item in decisions["items"]) == 2

    final_dry_run = client.post(
        "/plugins/capabilities/packs/operator/review/decisions/bulk-from-surface",
        json={
            "actor": _PLUGIN_ACTOR,
            "action": "approve",
            "reason": "changed shape covered",
            "pack_ids": [pack_id],
            "max_pack_count": 1,
            "max_total_capability_count": 2,
            "dry_run": True,
        },
    ).json()
    assert final_dry_run["status"] == "no_candidates"


def test_plugins_capability_pack_promotion_discipline_projects_pack_gate(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
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
    assert pack["operator_review_approved_capability_count"] == 1
    assert pack["operator_review_missing_capability_count"] == 0
    assert pack["operator_review_missing_capabilities_sample"] == []
    assert pack["promotion_rules_ready"] is True
    assert pack["pack_governance_ready"] is True
    assert pack["quality_evidence_ready"] is True
    assert pack["validation_receipts_ready"] is True
    assert pack["proposal_lineage_ready"] is True
    assert pack["promotion_receipts_ready"] is True
    assert pack["lifecycle_mixed"] is False
    assert all(item["capability"] != plugin_id for item in pack["failing_capabilities_sample"])


def test_plugins_capability_library_operator_surface_projects_ready_pack_library(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    pack_id = "ops.capability_library_surface"
    pack_version = "1.0.0"
    meta = {
        **_forge_promotion_meta("capability_library_surface"),
        "pack_id": pack_id,
        "pack_version": pack_version,
        "pack_name": "Ops Capability Library Surface Pack",
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
            "name": "Capability Library Surface Plugin",
            "description": "Stage 17 capability library operator surface coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": meta,
        },
    )
    assert built.status_code == 200
    assert built.json()["ok"] is True

    _approve_capability_pack_operator_review(
        client,
        pack_id=pack_id,
        pack_version=pack_version,
    )

    response = client.get("/plugins/capabilities/library/operator/surface")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "plugin.capability_library.operator_surface"
    assert body["stage"] == "Stage 17 / Capability Economy"
    assert body["status"] == "ready_for_explicit_promotion"
    assert body["library_operator_surface_ready"] is True
    assert body["pack_total"] == 1
    assert body["ready_pack_count"] == 1
    assert body["blocked_pack_count"] == 0
    assert body["approved_pack_operator_review_count"] == 1
    assert body["ready_staged_capability_count"] == 1
    assert body["ready_promoted_capability_count"] == 0
    assert body["packs_truncated"] is False
    assert body["pack_preview_limit"] == 50
    assert body["next_smallest_truthful_gap"] == "stage17_capability_library_explicit_promotion"
    assert body["routes"]["source_promotion_discipline_route"] == "/plugins/capabilities/packs/promotion/discipline"
    assert body["routes"]["operator_surface_route"] == "/plugins/capabilities/packs/operator/surface"
    assert body["routes"]["proposal_review_route"] == "/forge/proposals/decision"
    assert body["routes"]["promotion_route"] == "/plugins/enable"
    assert body["routes"]["promotion_receipts_route"] == "/plugins/capabilities/packs/promotion/receipts"
    assert body["requirements"]["derived_from_promotion_discipline"] is True
    assert body["requirements"]["lists_only_ready_packs"] is True
    assert body["requirements"]["ready_pack_requires_current_operator_review_coverage"] is True
    assert body["requirements"]["ready_pack_requires_quality_and_lineage_evidence"] is True
    assert body["requirements"]["explicit_promotion_remains_separate"] is True
    assert body["requirements"]["proposal_approval_remains_separate"] is True
    assert body["requirements"]["no_fake_progress_status"] is True
    assert body["governance"]["read_only"] is True
    assert body["governance"]["operator_facing"] is True
    assert body["governance"]["generated_plugin_registry_sync_performed"] is True
    assert body["governance"]["does_not_mutate_registry"] is False
    assert body["governance"]["does_not_write_receipts"] is True
    assert body["governance"]["does_not_write_metadata_receipts"] is True
    assert body["governance"]["does_not_write_validation_receipts"] is True
    assert body["governance"]["does_not_write_promotion_receipts"] is True
    assert body["governance"]["does_not_write_proposals"] is True
    assert body["governance"]["does_not_approve_proposals"] is True
    assert body["governance"]["does_not_promote_capabilities"] is True
    assert body["governance"]["does_not_enable_capabilities"] is True
    assert body["governance"]["does_not_execute_capabilities"] is True
    assert body["governance"]["promotion_authority"] is False
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["approval_authority"] is False
    assert body["governance"]["memory_write"] is False

    pack = body["packs"][0]
    assert pack["pack_id"] == pack_id
    assert pack["pack_version"] == pack_version
    assert pack["pack_name"] == "Ops Capability Library Surface Pack"
    assert pack["status"] == "ready"
    assert pack["ready"] is True
    assert pack["blockers"] == []
    assert pack["capability_count"] == 1
    assert pack["staged_capability_count"] == 1
    assert pack["promoted_capability_count"] == 0
    assert pack["operator_review_approved"] is True
    assert pack["quality_evidence_ready"] is True
    assert pack["validation_receipts_ready"] is True
    assert pack["proposal_lineage_ready"] is True


def test_plugins_capability_library_promotion_plan_uses_existing_promotion_readiness(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    promoted_pack_id = "ops.capability_library_promoted_only"
    pack_id = "ops.capability_library_promotion_plan"
    pack_version = "1.0.0"
    promoted_meta = {
        **_forge_promotion_meta("capability_library_promotion_plan_promoted_only"),
        "pack_id": promoted_pack_id,
        "pack_version": pack_version,
        "pack_name": "Ops Capability Library Promoted Only Pack",
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
    meta = {
        **_forge_promotion_meta("capability_library_promotion_plan"),
        "pack_id": pack_id,
        "pack_version": pack_version,
        "pack_name": "Ops Capability Library Promotion Plan Pack",
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
    promoted_built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Library Promoted Only Plugin",
            "description": "Stage 17 capability library promoted-only pack coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": promoted_meta,
        },
    )
    assert promoted_built.status_code == 200
    promoted_built_body = promoted_built.json()
    assert promoted_built_body["ok"] is True
    promoted_plugin_id = str(promoted_built_body["plugin_id"])
    promoted_proposal_id = str(promoted_built_body["proposal_id"])

    _approve_capability_pack_operator_review(
        client,
        pack_id=promoted_pack_id,
        pack_version=pack_version,
    )
    _approve_forge_proposal(client, promoted_proposal_id)
    promoted = client.post(
        "/plugins/enable",
        json={
            "id": promoted_plugin_id,
            "reason": "test promoted-only pack is not a staged promotion candidate",
            "actor": _PLUGIN_ACTOR,
        },
    )
    assert promoted.status_code == 200
    promoted_body = promoted.json()
    assert promoted_body["ok"] is True
    assert promoted_body["promotion_status"] == "promoted"

    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Library Promotion Plan Plugin",
            "description": "Stage 17 capability library explicit promotion planning coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": meta,
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])
    proposal_id = str(built_body["proposal_id"])

    _approve_capability_pack_operator_review(
        client,
        pack_id=pack_id,
        pack_version=pack_version,
    )

    blocked = client.get("/plugins/capabilities/library/promotion/plan")

    assert blocked.status_code == 200
    blocked_body = blocked.json()
    assert blocked_body["ok"] is True
    assert blocked_body["kind"] == "plugin.capability_library.promotion_plan"
    assert blocked_body["stage"] == "Stage 17 / Capability Economy"
    assert blocked_body["status"] == "blocked"
    assert blocked_body["promotion_plan_ready"] is False
    assert blocked_body["pack_total"] == 2
    assert blocked_body["ready_pack_count"] == 2
    assert blocked_body["blocked_pack_count"] == 0
    assert blocked_body["candidate_pack_count"] == 1
    assert blocked_body["candidate_capability_count"] == 1
    assert blocked_body["promotable_capability_count"] == 0
    assert blocked_body["blocked_capability_count"] == 1
    assert blocked_body["packs_truncated"] is False
    assert blocked_body["missing_requirement_counts"]["proposal_review"] == 1
    assert blocked_body["next_smallest_truthful_gap"] == "stage17_capability_library_proposal_review"
    assert blocked_body["routes"]["promotion_route"] == "/plugins/enable"
    assert blocked_body["routes"]["proposal_review_route"] == "/forge/proposals/decision"
    assert blocked_body["requirements"]["uses_existing_plugin_promotion_readiness"] is True
    assert blocked_body["requirements"]["proposal_review_required_before_promotion"] is True
    assert blocked_body["requirements"]["promotion_requires_plugins_write_scope"] is True
    assert blocked_body["requirements"]["explicit_operator_action_required"] is True
    assert blocked_body["requirements"]["no_auto_promotion"] is True
    assert blocked_body["governance"]["read_only"] is True
    assert blocked_body["governance"]["operator_facing"] is True
    assert blocked_body["governance"]["generated_plugin_registry_sync_performed"] is True
    assert blocked_body["governance"]["does_not_mutate_registry"] is False
    assert blocked_body["governance"]["does_not_write_promotion_receipts"] is True
    assert blocked_body["governance"]["does_not_approve_proposals"] is True
    assert blocked_body["governance"]["does_not_promote_capabilities"] is True
    assert blocked_body["governance"]["does_not_enable_capabilities"] is True
    assert blocked_body["governance"]["does_not_execute_capabilities"] is True
    assert blocked_body["governance"]["promotion_authority"] is False
    assert blocked_body["governance"]["execution_authority"] is False
    assert blocked_body["governance"]["approval_authority"] is False
    assert blocked_body["governance"]["memory_write"] is False

    blocked_pack = blocked_body["packs"][0]
    assert blocked_pack["pack_id"] == pack_id
    assert promoted_pack_id not in {pack["pack_id"] for pack in blocked_body["packs"]}
    assert blocked_pack["staged_capability_count"] == 1
    assert blocked_pack["promotable_capability_count"] == 0
    assert blocked_pack["blocked_capability_count"] == 1
    blocked_capability = blocked_pack["capabilities"][0]
    assert blocked_capability["capability"] == plugin_id
    assert blocked_capability["promotion_ready"] is False
    assert blocked_capability["proposal_id"] == proposal_id
    assert blocked_capability["proposal_review_status"] == "staged"
    assert blocked_capability["pack_operator_review_status"] == "approved"
    assert blocked_capability["promotion_route"] == "/plugins/enable"
    assert blocked_capability["promotion_would_write_receipt"] is True
    assert blocked_capability["promotion_would_enable_capability"] is True

    review_plan = client.get("/plugins/capabilities/library/proposal-review/plan")

    assert review_plan.status_code == 200
    review_plan_body = review_plan.json()
    assert review_plan_body["ok"] is True
    assert review_plan_body["kind"] == "plugin.capability_library.proposal_review_plan"
    assert review_plan_body["stage"] == "Stage 17 / Capability Economy"
    assert review_plan_body["status"] == "ready_for_proposal_review"
    assert review_plan_body["proposal_review_plan_ready"] is True
    assert review_plan_body["pack_total"] == 2
    assert review_plan_body["ready_pack_count"] == 2
    assert review_plan_body["blocked_pack_count"] == 0
    assert review_plan_body["candidate_pack_count"] == 1
    assert review_plan_body["candidate_capability_count"] == 1
    assert review_plan_body["unique_proposal_count"] == 1
    assert review_plan_body["proposal_review_missing_count"] == 1
    assert review_plan_body["reviewable_capability_count"] == 1
    assert review_plan_body["reviewable_proposal_count"] == 1
    assert review_plan_body["blocked_before_review_capability_count"] == 0
    assert review_plan_body["blocked_proposal_count"] == 0
    assert review_plan_body["packs_truncated"] is False
    assert review_plan_body["next_smallest_truthful_gap"] == "stage17_capability_library_proposal_review_apply"
    assert review_plan_body["routes"]["proposal_review_apply_route"] == (
        "/plugins/capabilities/library/proposal-review/apply"
    )
    assert review_plan_body["routes"]["proposal_review_route"] == "/forge/proposals/decision"
    assert review_plan_body["routes"]["promotion_plan_route"] == "/plugins/capabilities/library/promotion/plan"
    assert review_plan_body["requirements"]["uses_existing_plugin_promotion_readiness"] is True
    assert review_plan_body["requirements"]["proposal_evidence_required_before_review"] is True
    assert review_plan_body["requirements"]["tests_required_before_review"] is True
    assert review_plan_body["requirements"]["proposal_review_uses_forge_decision_receipt_schema"] is True
    assert review_plan_body["requirements"]["bulk_proposal_review_apply_requires_dry_run_fingerprint"] is True
    assert review_plan_body["requirements"]["proposal_review_does_not_promote_or_enable_capabilities"] is True
    assert review_plan_body["requirements"]["no_auto_approval"] is True
    assert review_plan_body["governance"]["read_only"] is True
    assert review_plan_body["governance"]["does_not_write_proposal_review_receipts"] is True
    assert review_plan_body["governance"]["does_not_approve_proposals"] is True
    assert review_plan_body["governance"]["does_not_promote_capabilities"] is True
    assert review_plan_body["governance"]["does_not_enable_capabilities"] is True
    assert review_plan_body["governance"]["proposal_review_authority"] is False

    review_pack = review_plan_body["packs"][0]
    assert review_pack["pack_id"] == pack_id
    assert promoted_pack_id not in {pack["pack_id"] for pack in review_plan_body["packs"]}
    assert review_pack["reviewable_capability_count"] == 1
    assert review_pack["blocked_before_review_capability_count"] == 0
    review_proposal = review_pack["proposals"][0]
    assert review_proposal["capability"] == plugin_id
    assert review_proposal["proposal_id"] == proposal_id
    assert review_proposal["proposal_review_missing"] is True
    assert review_proposal["review_ready"] is True
    assert review_proposal["approved_review"] is False
    assert review_proposal["blockers_before_review"] == []
    assert review_proposal["proposal_review_would_write_receipt"] is True
    assert review_proposal["proposal_review_would_promote_capability"] is False
    assert review_proposal["proposal_review_would_enable_capability"] is False

    readiness = client.get("/plugins/capabilities/library/proposal-review/apply-readiness")

    assert readiness.status_code == 200
    readiness_body = readiness.json()
    assert readiness_body["ok"] is True
    assert readiness_body["kind"] == "plugin.capability_library.proposal_review_apply_readiness"
    assert readiness_body["stage"] == "Stage 17 / Capability Economy"
    assert readiness_body["status"] == "ready_for_proposal_review_apply"
    assert readiness_body["proposal_review_apply_ready"] is True
    assert readiness_body["reviewable_pack_count"] == 1
    assert readiness_body["blocked_pack_count"] == 0
    assert readiness_body["reviewable_capability_count"] == 1
    assert readiness_body["proposal_review_missing_count"] == 1
    assert readiness_body["blocked_before_review_capability_count"] == 0
    assert readiness_body["source_proposal_evidence_plan"]["proposal_evidence_missing_count"] == 0
    assert readiness_body["source_proposal_evidence_plan"]["proposal_evidence_ready_count"] == 1
    assert readiness_body["source_operator_evidence_intake_audit"]["recorded_capability_count"] == 0
    assert readiness_body["source_proposal_review_plan"]["proposal_review_plan_ready"] is True
    assert readiness_body["source_proposal_review_plan"]["reviewable_capability_count"] == 1
    assert readiness_body["routes"]["proposal_review_apply_readiness_route"] == (
        "/plugins/capabilities/library/proposal-review/apply-readiness"
    )
    assert (
        readiness_body["routes"]["proposal_review_apply_route"] == "/plugins/capabilities/library/proposal-review/apply"
    )
    assert readiness_body["routes"]["proposal_review_route"] == "/forge/proposals/decision"
    assert readiness_body["routes"]["operator_intake_audit_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/audit"
    )
    assert readiness_body["requirements"]["proposal_evidence_required_before_review"] is True
    assert readiness_body["requirements"]["forge_decision_route_required"] is True
    assert readiness_body["requirements"]["proposal_review_uses_forge_decision_receipt_schema"] is True
    assert readiness_body["requirements"]["bulk_proposal_review_apply_requires_dry_run_fingerprint"] is True
    assert readiness_body["requirements"]["does_not_apply_reviews"] is True
    assert readiness_body["governance"]["read_only"] is True
    assert readiness_body["governance"]["does_not_write_proposal_review_receipts"] is True
    assert readiness_body["governance"]["does_not_approve_proposals"] is True
    assert readiness_body["governance"]["does_not_promote_capabilities"] is True
    assert readiness_body["governance"]["does_not_enable_capabilities"] is True
    assert readiness_body["governance"]["proposal_review_authority"] is False
    readiness_pack = readiness_body["packs"][0]
    assert readiness_pack["pack_id"] == pack_id
    assert readiness_pack["reviewable_capability_count"] == 1
    assert readiness_pack["blocked_before_review_capability_count"] == 0
    readiness_proposal = readiness_pack["proposals"][0]
    assert readiness_proposal["capability"] == plugin_id
    assert readiness_proposal["proposal_id"] == proposal_id
    assert readiness_proposal["review_ready"] is True
    assert readiness_proposal["proposal_review_would_write_receipt"] is True
    assert readiness_proposal["proposal_review_would_promote_capability"] is False
    assert readiness_proposal["proposal_review_would_enable_capability"] is False

    review_dry_run = client.post(
        "/plugins/capabilities/library/proposal-review/apply",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "dry run capability-library proposal review",
            "pack_ids": [pack_id],
            "capability_ids": [plugin_id],
            "max_pack_count": 1,
            "max_total_capability_count": 1,
            "max_capability_count_per_pack": 1,
            "dry_run": True,
        },
    )

    assert review_dry_run.status_code == 200
    review_dry_run_body = review_dry_run.json()
    assert review_dry_run_body["ok"] is True
    assert review_dry_run_body["applied"] is False
    assert review_dry_run_body["kind"] == "plugin.capability_library.proposal_review.apply"
    assert review_dry_run_body["status"] == "dry_run"
    assert review_dry_run_body["planned_pack_count"] == 1
    assert review_dry_run_body["planned_capability_count"] == 1
    assert review_dry_run_body["planned_proposal_count"] == 1
    assert len(review_dry_run_body["dry_run_fingerprint"]) == 64
    assert review_dry_run_body["before"]["projection_scope"] == "selected_capabilities"
    assert review_dry_run_body["before"]["global_counts_included"] is False
    assert review_dry_run_body["dry_run_confirmation"]["required_for_apply"] is True
    assert review_dry_run_body["dry_run_confirmation"]["fingerprint"] == review_dry_run_body["dry_run_fingerprint"]
    assert review_dry_run_body["dry_run_confirmation"]["fingerprint_contract"] == (
        "stage17_capability_library_proposal_review_apply_dry_run_v1"
    )
    assert review_dry_run_body["planned"][0]["pack_id"] == pack_id
    planned_review = review_dry_run_body["planned"][0]["proposals"][0]
    assert planned_review["proposal_id"] == proposal_id
    assert planned_review["capability_ids"] == [plugin_id]
    assert planned_review["writes_proposal_review_receipt"] is False
    assert planned_review["updates_proposal_record"] is False
    assert planned_review["approves_proposal"] is True
    assert planned_review["promotes_capability"] is False
    assert planned_review["enables_capability"] is False
    assert review_dry_run_body["governance"]["writes_proposal_review_receipts"] is False
    assert review_dry_run_body["governance"]["updates_proposal_records"] is False
    assert review_dry_run_body["governance"]["uses_forge_decision_receipt_schema"] is True
    assert review_dry_run_body["governance"]["dry_run_required_before_apply"] is True
    assert review_dry_run_body["governance"]["would_approve_proposals"] is True
    assert review_dry_run_body["governance"]["approves_proposals"] is False
    assert review_dry_run_body["governance"]["does_not_promote_capabilities"] is True
    assert review_dry_run_body["governance"]["does_not_enable_capabilities"] is True
    assert review_dry_run_body["governance"]["proposal_review_authority"] is False
    assert review_dry_run_body["governance"]["promotion_authority"] is False

    proposal_after_review_dry_run = client.get(f"/forge/proposals/get?id={proposal_id}").json()["item"]
    assert proposal_after_review_dry_run["status"] == "staged"

    review_blocked_without_confirmation = client.post(
        "/plugins/capabilities/library/proposal-review/apply",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "apply capability-library proposal review without dry run confirmation",
            "pack_ids": [pack_id],
            "capability_ids": [plugin_id],
            "max_pack_count": 1,
            "max_total_capability_count": 1,
            "max_capability_count_per_pack": 1,
            "dry_run": False,
        },
    )

    assert review_blocked_without_confirmation.status_code == 200
    review_blocked_body = review_blocked_without_confirmation.json()
    assert review_blocked_body["ok"] is False
    assert review_blocked_body["applied"] is False
    assert review_blocked_body["status"] == "blocked"
    assert review_blocked_body["error"] == "capability_library_proposal_review_dry_run_confirmation_required"
    assert review_blocked_body["dry_run_confirmation"]["required_for_apply"] is True
    assert review_blocked_body["dry_run_confirmation"]["fingerprint_matched"] is False
    assert review_blocked_body["governance"]["writes_proposal_review_receipts"] is False
    assert review_blocked_body["governance"]["updates_proposal_records"] is False
    assert review_blocked_body["governance"]["proposal_review_authority"] is False

    proposal_after_blocked_review = client.get(f"/forge/proposals/get?id={proposal_id}").json()["item"]
    assert proposal_after_blocked_review["status"] == "staged"

    review_applied = client.post(
        "/plugins/capabilities/library/proposal-review/apply",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "apply capability-library proposal review",
            "pack_ids": [pack_id],
            "capability_ids": [plugin_id],
            "max_pack_count": 1,
            "max_total_capability_count": 1,
            "max_capability_count_per_pack": 1,
            "dry_run": False,
            "dry_run_fingerprint": review_dry_run_body["dry_run_fingerprint"],
        },
    )

    assert review_applied.status_code == 200
    review_applied_body = review_applied.json()
    assert review_applied_body["ok"] is True
    assert review_applied_body["applied"] is True
    assert review_applied_body["kind"] == "plugin.capability_library.proposal_review.apply"
    assert review_applied_body["status"] == "reviewed"
    assert review_applied_body["planned_pack_count"] == 1
    assert review_applied_body["planned_capability_count"] == 1
    assert review_applied_body["planned_proposal_count"] == 1
    assert review_applied_body["recorded_proposal_count"] == 1
    assert review_applied_body["recorded_capability_count"] == 1
    assert review_applied_body["recorded"][0]["proposal_id"] == proposal_id
    assert review_applied_body["recorded"][0]["capability_ids"] == [plugin_id]
    assert Path(review_applied_body["recorded"][0]["receipt_path"]).exists()
    assert review_applied_body["dry_run_confirmation"]["fingerprint_matched"] is True
    assert review_applied_body["remaining_proposal_review_missing_count"] == 0
    assert review_applied_body["remaining_reviewable_capability_count"] == 0
    assert review_applied_body["promotable_capability_count"] == 1
    assert review_applied_body["next_smallest_truthful_gap"] == "stage17_capability_library_explicit_promotion_apply"
    assert review_applied_body["governance"]["writes_proposal_review_receipts"] is True
    assert review_applied_body["governance"]["updates_proposal_records"] is True
    assert review_applied_body["governance"]["approves_proposals"] is True
    assert review_applied_body["governance"]["does_not_promote_capabilities"] is True
    assert review_applied_body["governance"]["does_not_enable_capabilities"] is True
    assert review_applied_body["governance"]["proposal_review_authority"] is True
    assert review_applied_body["governance"]["promotion_authority"] is False

    review_receipt = json.loads(Path(review_applied_body["recorded"][0]["receipt_path"]).read_text(encoding="utf-8"))
    assert review_receipt["kind"] == "plugin.proposal.review.receipt"
    assert review_receipt["proposal_id"] == proposal_id
    assert review_receipt["status"] == "approved"
    assert review_receipt["governance"]["uses_forge_decision_receipt_schema"] is True

    reviewed = client.get("/plugins/capabilities/library/proposal-review/plan")

    assert reviewed.status_code == 200
    reviewed_body = reviewed.json()
    assert reviewed_body["ok"] is True
    assert reviewed_body["status"] == "proposal_review_complete"
    assert reviewed_body["proposal_review_plan_ready"] is False
    assert reviewed_body["candidate_capability_count"] == 1
    assert reviewed_body["proposal_review_missing_count"] == 0
    assert reviewed_body["approved_proposal_review_count"] == 1
    assert reviewed_body["approved_proposal_count"] == 1
    assert reviewed_body["reviewable_capability_count"] == 0
    assert reviewed_body["blocked_before_review_capability_count"] == 0
    assert reviewed_body["missing_requirement_counts"] == {}
    assert reviewed_body["next_smallest_truthful_gap"] == "stage17_capability_library_explicit_promotion_apply"

    ready = client.get("/plugins/capabilities/library/promotion/plan")

    assert ready.status_code == 200
    ready_body = ready.json()
    assert ready_body["ok"] is True
    assert ready_body["status"] == "ready_for_explicit_promotion"
    assert ready_body["promotion_plan_ready"] is True
    assert ready_body["candidate_pack_count"] == 1
    assert ready_body["candidate_capability_count"] == 1
    assert ready_body["promotable_capability_count"] == 1
    assert ready_body["blocked_capability_count"] == 0
    assert ready_body["packs_truncated"] is False
    assert ready_body["missing_requirement_counts"] == {}
    assert ready_body["next_smallest_truthful_gap"] == "stage17_capability_library_explicit_promotion_apply"
    assert ready_body["routes"]["promotion_apply_route"] == "/plugins/capabilities/library/promotion/apply"
    assert ready_body["requirements"]["bulk_promotion_apply_requires_dry_run_fingerprint"] is True
    assert ready_body["requirements"]["core_compatibility_required_before_promotion"] is True

    ready_capability = ready_body["packs"][0]["capabilities"][0]
    assert ready_capability["capability"] == plugin_id
    assert ready_capability["promotion_ready"] is True
    assert ready_capability["proposal_review_status"] == "approved"
    assert ready_capability["compatibility"]["compatible"] is True
    assert ready_capability["compatibility"]["status"] == "compatible"
    assert ready_capability["compatibility"]["min_core_version"] == "0.3.0"

    fetched = client.get(f"/plugins/get?id={plugin_id}")
    assert fetched.status_code == 200
    fetched_item = fetched.json()["item"]
    assert fetched_item["status"] == "staged"
    assert fetched_item["enabled"] is False

    dry_run = client.post(
        "/plugins/capabilities/library/promotion/apply",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "dry run explicit capability-library promotion",
            "pack_ids": [pack_id],
            "capability_ids": [plugin_id],
            "max_pack_count": 1,
            "max_total_capability_count": 1,
            "max_capability_count_per_pack": 1,
            "dry_run": True,
        },
    )

    assert dry_run.status_code == 200
    dry_run_body = dry_run.json()
    assert dry_run_body["ok"] is True
    assert dry_run_body["applied"] is False
    assert dry_run_body["kind"] == "plugin.capability_library.explicit_promotion.apply"
    assert dry_run_body["status"] == "dry_run"
    assert dry_run_body["planned_pack_count"] == 1
    assert dry_run_body["planned_capability_count"] == 1
    assert len(dry_run_body["dry_run_fingerprint"]) == 64
    assert dry_run_body["dry_run_confirmation"]["required_for_apply"] is True
    assert dry_run_body["dry_run_confirmation"]["fingerprint"] == dry_run_body["dry_run_fingerprint"]
    assert dry_run_body["dry_run_confirmation"]["fingerprint_contract"] == (
        "stage17_capability_library_explicit_promotion_dry_run_v1"
    )
    assert dry_run_body["planned"][0]["pack_id"] == pack_id
    planned_promotion_capability = dry_run_body["planned"][0]["capabilities"][0]
    assert planned_promotion_capability["capability"] == plugin_id
    assert planned_promotion_capability["compatibility"]["compatible"] is True
    assert planned_promotion_capability["compatibility"]["status"] == "compatible"
    assert dry_run_body["planned"][0]["writes_promotion_receipts"] is False
    assert dry_run_body["planned"][0]["promotes_capabilities"] is False
    assert dry_run_body["planned"][0]["enables_capabilities"] is False
    assert dry_run_body["governance"]["writes_registry_metadata"] is False
    assert dry_run_body["governance"]["writes_promotion_receipts"] is False
    assert dry_run_body["governance"]["lifecycle_operation"] == "explicit_promotion_apply"
    assert dry_run_body["governance"]["policy_gate"] == "plugins.write"
    assert dry_run_body["governance"]["receipt_contract"] == "plugin.promotion.receipt"
    assert dry_run_body["governance"]["uses_existing_plugin_promotion_readiness"] is True
    assert dry_run_body["governance"]["uses_plugin_promotion_receipt_schema"] is True
    assert isinstance(dry_run_body["governance"]["generated_plugin_registry_sync_performed"], bool)
    assert isinstance(dry_run_body["governance"]["does_not_mutate_registry"], bool)
    assert dry_run_body["governance"]["dry_run_required_before_apply"] is True
    assert dry_run_body["governance"]["does_not_approve_proposals"] is True
    assert dry_run_body["governance"]["does_not_execute_capabilities"] is True
    assert dry_run_body["governance"]["promotion_authority"] is False
    assert dry_run_body["governance"]["execution_authority"] is False
    assert dry_run_body["governance"]["memory_write"] is False

    fetched_after_dry_run = client.get(f"/plugins/get?id={plugin_id}").json()["item"]
    assert fetched_after_dry_run["status"] == "staged"
    assert fetched_after_dry_run["enabled"] is False

    blocked_without_confirmation = client.post(
        "/plugins/capabilities/library/promotion/apply",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "apply explicit capability-library promotion without dry run confirmation",
            "pack_ids": [pack_id],
            "capability_ids": [plugin_id],
            "max_pack_count": 1,
            "max_total_capability_count": 1,
            "max_capability_count_per_pack": 1,
            "dry_run": False,
        },
    )

    assert blocked_without_confirmation.status_code == 200
    blocked_body = blocked_without_confirmation.json()
    assert blocked_body["ok"] is False
    assert blocked_body["applied"] is False
    assert blocked_body["status"] == "blocked"
    assert blocked_body["error"] == "capability_library_explicit_promotion_dry_run_confirmation_required"
    assert blocked_body["dry_run_confirmation"]["required_for_apply"] is True
    assert blocked_body["dry_run_confirmation"]["fingerprint_matched"] is False
    assert blocked_body["governance"]["writes_registry_metadata"] is False
    assert blocked_body["governance"]["writes_promotion_receipts"] is False
    assert blocked_body["governance"]["lifecycle_operation"] == "explicit_promotion_apply"
    assert blocked_body["governance"]["receipt_contract"] == "plugin.promotion.receipt"
    assert blocked_body["governance"]["uses_plugin_promotion_receipt_schema"] is True
    assert blocked_body["governance"]["promotion_authority"] is False

    fetched_after_blocked_apply = client.get(f"/plugins/get?id={plugin_id}").json()["item"]
    assert fetched_after_blocked_apply["status"] == "staged"
    assert fetched_after_blocked_apply["enabled"] is False

    applied = client.post(
        "/plugins/capabilities/library/promotion/apply",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "apply explicit capability-library promotion",
            "pack_ids": [pack_id],
            "capability_ids": [plugin_id],
            "max_pack_count": 1,
            "max_total_capability_count": 1,
            "max_capability_count_per_pack": 1,
            "dry_run": False,
            "dry_run_fingerprint": dry_run_body["dry_run_fingerprint"],
        },
    )

    assert applied.status_code == 200
    applied_body = applied.json()
    assert applied_body["ok"] is True
    assert applied_body["applied"] is True
    assert applied_body["status"] == "promoted"
    assert applied_body["planned_pack_count"] == 1
    assert applied_body["planned_capability_count"] == 1
    assert applied_body["promoted_capability_count"] == 1
    assert applied_body["promotion_receipt_count"] == 1
    assert applied_body["promoted"][0]["capability"] == plugin_id
    assert applied_body["promoted"][0]["pack_id"] == pack_id
    assert applied_body["promotion_receipts"][0]["kind"] == "plugin.promotion.receipt"
    assert applied_body["promotion_receipts"][0]["plugin_id"] == plugin_id
    assert applied_body["promotion_receipts"][0]["status"] == "promoted"
    assert applied_body["promotion_receipts"][0]["proposal_review"]["status"] == "approved"
    assert applied_body["promotion_receipts"][0]["compatibility"]["compatible"] is True
    assert applied_body["promotion_receipts"][0]["compatibility"]["status"] == "compatible"
    assert applied_body["dry_run_fingerprint"] == dry_run_body["dry_run_fingerprint"]
    assert applied_body["dry_run_confirmation"]["fingerprint_matched"] is True
    assert applied_body["remaining_candidate_capability_count"] == 0
    assert applied_body["remaining_promotable_capability_count"] == 0
    assert applied_body["next_smallest_truthful_gap"] == "stage17_capability_library_promotion_receipts"
    assert applied_body["governance"]["writes_registry_metadata"] is True
    assert applied_body["governance"]["writes_promotion_receipts"] is True
    assert applied_body["governance"]["lifecycle_operation"] == "explicit_promotion_apply"
    assert applied_body["governance"]["policy_gate"] == "plugins.write"
    assert applied_body["governance"]["receipt_contract"] == "plugin.promotion.receipt"
    assert applied_body["governance"]["uses_existing_plugin_promotion_readiness"] is True
    assert applied_body["governance"]["uses_plugin_promotion_receipt_schema"] is True
    assert isinstance(applied_body["governance"]["generated_plugin_registry_sync_performed"], bool)
    assert applied_body["governance"]["does_not_mutate_registry"] is False
    assert applied_body["governance"]["dry_run_required_before_apply"] is True
    assert applied_body["governance"]["does_not_approve_proposals"] is True
    assert applied_body["governance"]["does_not_promote_capabilities"] is False
    assert applied_body["governance"]["does_not_enable_capabilities"] is False
    assert applied_body["governance"]["does_not_execute_capabilities"] is True
    assert applied_body["governance"]["promotion_authority"] is True
    assert applied_body["governance"]["execution_authority"] is False
    assert applied_body["governance"]["memory_write"] is False

    promoted_item = client.get(f"/plugins/get?id={plugin_id}").json()["item"]
    assert promoted_item["status"] == "enabled"
    assert promoted_item["enabled"] is True
    promoted_meta = promoted_item["meta"]
    assert promoted_meta["promotion_status"] == "promoted"
    assert promoted_meta["promotion_receipt_id"] == applied_body["promotion_receipts"][0]["receipt_id"]
    assert Path(promoted_meta["promotion_receipt_path"]).exists()


def test_plugins_promotion_readiness_blocks_incompatible_core_versions(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    pack_id = "ops.capability_library_incompatible_core"
    pack_version = "1.0.0"
    compatibility_cases = {
        "requires_future_core": {"min_core_version": "99.0.0"},
        "malformed_core_version": {"min_core_version": "not-a-version"},
    }
    built_items: dict[str, tuple[str, str]] = {}

    for label, compatibility in compatibility_cases.items():
        meta = {
            **_forge_promotion_meta(label),
            "pack_id": pack_id,
            "pack_version": pack_version,
            "pack_name": "Ops Capability Library Incompatible Core Pack",
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
                "name": f"Incompatible Core {label}",
                "description": "Stage 17 compatibility refusal coverage",
                "actor": _PLUGIN_ACTOR,
                "meta": meta,
            },
        )
        assert built.status_code == 200
        built_body = built.json()
        assert built_body["ok"] is True
        plugin_id = str(built_body["plugin_id"])
        proposal_id = str(built_body["proposal_id"])
        built_items[label] = (plugin_id, proposal_id)

        registry = plugins._load_registry()
        plugin = plugins._read_plugin(registry, plugin_id)
        assert plugin is not None
        generated_dir = Path(str(plugin["generated_dir"]))
        spec_path = generated_dir / "plugin.spec.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec["compatibility"] = compatibility
        spec_path.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        plugin_meta = dict(plugin.get("meta") or {})
        plugin_meta["compatibility"] = compatibility
        plugin["meta"] = plugin_meta
        plugins._write_plugin(registry, plugins._normalize_plugin_record(plugin_id, plugin))
        plugins._save_registry_and_catalog(registry)

        _approve_forge_proposal(client, proposal_id)

    _approve_capability_pack_operator_review(
        client,
        pack_id=pack_id,
        pack_version=pack_version,
    )

    plan = client.get("/plugins/capabilities/library/promotion/plan")

    assert plan.status_code == 200
    plan_body = plan.json()
    assert plan_body["ok"] is True
    assert plan_body["status"] == "blocked"
    assert plan_body["promotion_plan_ready"] is False
    assert plan_body["candidate_pack_count"] == 1
    assert plan_body["candidate_capability_count"] == 2
    assert plan_body["promotable_capability_count"] == 0
    assert plan_body["blocked_capability_count"] == 2
    assert plan_body["missing_requirement_counts"]["core_compatibility"] == 2
    assert plan_body["requirements"]["core_compatibility_required_before_promotion"] is True
    assert plan_body["governance"]["does_not_promote_capabilities"] is True

    capabilities = {item["capability"]: item for pack in plan_body["packs"] for item in pack["capabilities"]}
    future_plugin_id, _ = built_items["requires_future_core"]
    malformed_plugin_id, _ = built_items["malformed_core_version"]
    assert capabilities[future_plugin_id]["promotion_ready"] is False
    assert "core_compatibility" in capabilities[future_plugin_id]["missing_requirements"]
    assert capabilities[future_plugin_id]["compatibility"]["status"] == "requires_newer_core"
    assert capabilities[future_plugin_id]["compatibility"]["min_core_version"] == "99.0.0"
    assert capabilities[malformed_plugin_id]["promotion_ready"] is False
    assert "core_compatibility" in capabilities[malformed_plugin_id]["missing_requirements"]
    assert capabilities[malformed_plugin_id]["compatibility"]["status"] == "invalid_min_core_version"
    assert capabilities[malformed_plugin_id]["compatibility"]["min_core_version"] == "not-a-version"

    blocked_enable = client.post(
        "/plugins/enable",
        json={
            "id": future_plugin_id,
            "reason": "attempt incompatible staged promotion",
            "actor": _PLUGIN_ACTOR,
        },
    )

    assert blocked_enable.status_code == 200
    blocked_body = blocked_enable.json()
    assert blocked_body["ok"] is False
    assert blocked_body["applied"] is False
    assert blocked_body["error"] == "promotion_readiness_blocked"
    assert blocked_body["status"] == "staged"
    assert "core_compatibility" in blocked_body["readiness"]["missing_requirements"]
    assert blocked_body["readiness"]["evidence"]["compatibility"]["status"] == "requires_newer_core"
    assert blocked_body["readiness"]["evidence"]["compatibility"]["compatible"] is False
    assert blocked_body["governance"]["scope"] == "plugins.write"

    fetched_after_block = client.get(f"/plugins/get?id={future_plugin_id}")
    assert fetched_after_block.status_code == 200
    fetched_item = fetched_after_block.json()["item"]
    assert fetched_item["status"] == "staged"
    assert fetched_item["enabled"] is False


def test_plugins_run_blocks_incompatible_registry_core_versions(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    client = TestClient(create_app())

    def install_with_registry_compatibility(label: str, compatibility: dict[str, object]) -> tuple[str, int]:
        installed = client.post(
            "/plugins/install",
            json={
                "source_kind": "registry",
                "source_ref": f"acme/runtime-compatibility-{label}",
                "actor": _PLUGIN_ACTOR,
                "reason": f"install runtime compatibility {label}",
            },
        )
        assert installed.status_code == 200
        installed_body = installed.json()
        assert installed_body["ok"] is True
        plugin_id = str(installed_body["plugin_id"])

        registry = plugins._load_registry()
        plugin = plugins._read_plugin(registry, plugin_id)
        assert plugin is not None
        meta = dict(plugin.get("meta") or {})
        meta["compatibility"] = compatibility
        plugin["meta"] = meta
        normalized = plugins._normalize_plugin_record(plugin_id, plugin)
        plugins._write_plugin(registry, normalized)
        plugins._save_registry_and_catalog(registry)
        return plugin_id, int(normalized.get("updated_ts") or 0)

    compatible_id, _ = install_with_registry_compatibility("compatible", {"min_core_version": "0.0.0"})
    future_id, future_updated_ts = install_with_registry_compatibility("future", {"min_core_version": "99.0.0"})
    malformed_id, malformed_updated_ts = install_with_registry_compatibility(
        "malformed",
        {"min_core_version": "not-a-version"},
    )

    allowed = client.post("/plugins/run", json={"id": compatible_id, "action": "run", "input": "hello"})
    assert allowed.status_code == 200
    allowed_body = allowed.json()
    assert allowed_body["ok"] is True
    assert allowed_body["status"] == "ok"
    assert allowed_body["receipt"]["ok"] is True

    blocked_future = client.post(
        "/plugins/run",
        json={
            "id": future_id,
            "action": "run",
            "input": "hello",
            "meta": {"compatibility": {"min_core_version": "0.0.0"}},
        },
    )
    assert blocked_future.status_code == 200
    blocked_future_body = blocked_future.json()
    assert blocked_future_body["ok"] is False
    assert blocked_future_body["error"] == "plugin_core_incompatible"
    assert blocked_future_body["status"] == "blocked"
    assert blocked_future_body["compatibility"]["compatible"] is False
    assert blocked_future_body["compatibility"]["status"] == "requires_newer_core"
    assert blocked_future_body["compatibility"]["min_core_version"] == "99.0.0"
    assert blocked_future_body["governance"]["gate"] == "plugin_runtime_compatibility_gate"
    assert blocked_future_body["governance"]["scope"] == "plugin.run"
    assert blocked_future_body["governance"]["does_not_execute_capabilities"] is True
    assert blocked_future_body["governance"]["promotion_authority"] is False
    assert blocked_future_body["governance"]["execution_authority"] is False
    assert "receipt" not in blocked_future_body

    blocked_malformed = client.post(
        "/plugins/run",
        json={"id": malformed_id, "action": "run", "input": "hello"},
    )
    assert blocked_malformed.status_code == 200
    blocked_malformed_body = blocked_malformed.json()
    assert blocked_malformed_body["ok"] is False
    assert blocked_malformed_body["error"] == "plugin_core_incompatible"
    assert blocked_malformed_body["compatibility"]["compatible"] is False
    assert blocked_malformed_body["compatibility"]["status"] == "invalid_min_core_version"
    assert blocked_malformed_body["compatibility"]["min_core_version"] == "not-a-version"
    assert blocked_malformed_body["governance"]["compatibility_status"] == "invalid_min_core_version"
    assert blocked_malformed_body["governance"]["does_not_execute_capabilities"] is True
    assert "receipt" not in blocked_malformed_body

    registry = plugins._load_registry()
    future_after = plugins._read_plugin(registry, future_id)
    malformed_after = plugins._read_plugin(registry, malformed_id)
    assert future_after is not None
    assert malformed_after is not None
    assert int(future_after.get("updated_ts") or 0) == future_updated_ts
    assert int(malformed_after.get("updated_ts") or 0) == malformed_updated_ts


def test_plugins_capability_library_proposal_review_plan_blocks_before_review_when_evidence_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.api.routes import plugins

    pack_id = "ops.capability_library_proposal_review_blocked"
    pack_version = "1.0.0"
    plugin_id = "capability_library_proposal_review_blocked"
    proposal_id = "plugin_proposal_capability_library_proposal_review_blocked"
    registry = {
        "plugins": {
            plugin_id: {
                "id": plugin_id,
                "name": "Capability Library Proposal Review Blocked Plugin",
                "status": "staged",
                "enabled": False,
                "meta": {
                    "proposal_id": proposal_id,
                    "quality": {
                        "tests": ["tests/test_api_plugins.py"],
                        "docs": ["README.md"],
                        "claim_scope": "candidate_reference_only_not_pack_specific_proof",
                    },
                    "risk_tier": "normal",
                },
            }
        }
    }
    entries = [
        {
            "capability": plugin_id,
            "status": "staged",
            "metadata": {
                "pack_id": pack_id,
                "pack_version": pack_version,
            },
        }
    ]
    promotion_discipline = {
        "pack_total": 1,
        "ready_pack_count": 1,
        "blocked_pack_count": 0,
        "packs": [
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "pack_name": "Ops Capability Library Proposal Review Blocked Pack",
                "status": "ready",
                "ready": True,
            }
        ],
    }

    evidence_body = plugins._capability_library_proposal_evidence_plan_projection(
        registry=registry,
        entries=entries,
        promotion_discipline=promotion_discipline,
        generated_plugin_sync_performed=False,
    )

    assert evidence_body["status"] == "blocked"
    assert evidence_body["proposal_evidence_plan_ready"] is True
    assert evidence_body["candidate_capability_count"] == 1
    assert evidence_body["unique_proposal_count"] == 1
    assert evidence_body["proposal_evidence_missing_count"] == 1
    assert evidence_body["proposal_evidence_ready_count"] == 0
    assert evidence_body["missing_proposal_evidence_count"] == 1
    assert evidence_body["evidence_ready_proposal_count"] == 0
    assert evidence_body["proposal_id_missing_count"] == 0
    assert evidence_body["proposal_review_missing_count"] == 1
    assert evidence_body["blocked_before_evidence_count"] == 0
    assert evidence_body["missing_requirement_counts"]["proposal_evidence"] == 1
    assert evidence_body["missing_requirement_counts"]["proposal_review"] == 1
    assert "tests" not in evidence_body["missing_requirement_counts"]
    assert evidence_body["next_smallest_truthful_gap"] == "stage17_capability_library_promotion_readiness"
    assert evidence_body["routes"]["promotion_plan_route"] == "/plugins/capabilities/library/promotion/plan"
    assert evidence_body["routes"]["proposal_review_plan_route"] == "/plugins/capabilities/library/proposal-review/plan"
    assert evidence_body["requirements"]["proposal_evidence_required_before_proposal_review"] is True
    assert evidence_body["requirements"]["empty_reconstructed_lineage_does_not_satisfy_evidence"] is True
    assert evidence_body["requirements"]["no_auto_reconstruction"] is True
    assert evidence_body["governance"]["read_only"] is True
    assert evidence_body["governance"]["does_not_write_proposals"] is True
    assert evidence_body["governance"]["does_not_approve_proposals"] is True
    assert evidence_body["governance"]["does_not_promote_capabilities"] is True
    assert evidence_body["governance"]["does_not_enable_capabilities"] is True
    assert evidence_body["governance"]["memory_write"] is False

    evidence_pack = evidence_body["packs"][0]
    assert evidence_pack["pack_id"] == pack_id
    assert evidence_pack["proposal_evidence_missing_count"] == 1
    assert evidence_pack["proposal_evidence_ready_count"] == 0
    assert evidence_pack["blocked_before_evidence_count"] == 0
    evidence_capability = evidence_pack["capabilities"][0]
    assert evidence_capability["capability"] == plugin_id
    assert evidence_capability["proposal_id"] == proposal_id
    assert evidence_capability["proposal_evidence_missing"] is True
    assert evidence_capability["proposal_evidence_ready"] is False
    assert evidence_capability["proposal_evidence"] == []
    assert evidence_capability["linked_proposal_artifact_evidence"] == []
    assert evidence_capability["evidence_source"] == "missing_in_plugin_metadata_and_linked_proposal_artifact"
    assert evidence_capability["blockers_before_evidence"] == []
    assert evidence_capability["proposal_review_would_write_receipt"] is True
    assert evidence_capability["proposal_review_would_promote_capability"] is False
    assert evidence_capability["proposal_review_would_enable_capability"] is False

    promotion_body = plugins._capability_library_explicit_promotion_plan_projection(
        registry=registry,
        entries=entries,
        promotion_discipline=promotion_discipline,
        generated_plugin_sync_performed=False,
    )

    assert promotion_body["status"] == "blocked"
    assert promotion_body["candidate_capability_count"] == 1
    assert promotion_body["blocked_capability_count"] == 1
    assert promotion_body["missing_requirement_counts"]["proposal_review"] == 1
    assert promotion_body["missing_requirement_counts"]["proposal_evidence"] == 1
    assert "tests" not in promotion_body["missing_requirement_counts"]
    assert promotion_body["next_smallest_truthful_gap"] == "stage17_capability_library_promotion_readiness"

    review_body = plugins._capability_library_proposal_review_plan_projection(
        registry=registry,
        entries=entries,
        promotion_discipline=promotion_discipline,
        generated_plugin_sync_performed=False,
    )

    assert review_body["status"] == "blocked"
    assert review_body["proposal_review_plan_ready"] is False
    assert review_body["candidate_capability_count"] == 1
    assert review_body["proposal_review_missing_count"] == 1
    assert review_body["reviewable_capability_count"] == 0
    assert review_body["reviewable_proposal_count"] == 0
    assert review_body["blocked_before_review_capability_count"] == 1
    assert review_body["blocked_proposal_count"] == 1
    assert review_body["missing_requirement_counts"]["proposal_evidence"] == 1
    assert "tests" not in review_body["missing_requirement_counts"]
    assert review_body["next_smallest_truthful_gap"] == "stage17_capability_library_promotion_readiness"

    proposal = review_body["packs"][0]["proposals"][0]
    assert proposal["review_ready"] is False
    assert proposal["proposal_review_missing"] is True
    assert proposal["blockers_before_review"] == ["proposal_evidence"]
    assert proposal["proposal_review_would_write_receipt"] is True
    assert proposal["proposal_review_would_promote_capability"] is False
    assert proposal["proposal_review_would_enable_capability"] is False

    operator_audit_body = plugins._capability_library_operator_proposal_evidence_intake_audit_projection(
        registry=registry,
        entries=entries,
        promotion_discipline=promotion_discipline,
        source_plan=evidence_body,
        generated_plugin_sync_performed=False,
    )
    readiness_body = plugins._capability_library_proposal_review_apply_readiness_projection(
        proposal_review_plan=review_body,
        proposal_evidence_plan=evidence_body,
        operator_evidence_audit=operator_audit_body,
        generated_plugin_sync_performed=False,
    )

    assert readiness_body["status"] == "blocked_on_operator_evidence_refs"
    assert readiness_body["proposal_review_apply_ready"] is False
    assert readiness_body["reviewable_capability_count"] == 0
    assert readiness_body["blocked_before_review_capability_count"] == 1
    assert readiness_body["source_proposal_evidence_plan"]["proposal_evidence_missing_count"] == 1
    assert readiness_body["source_proposal_evidence_plan"]["proposal_evidence_ready_count"] == 0
    assert readiness_body["source_operator_evidence_intake_audit"]["recorded_capability_count"] == 0
    assert readiness_body["source_proposal_review_plan"]["proposal_review_plan_ready"] is False
    assert readiness_body["source_proposal_review_plan"]["blocked_before_review_capability_count"] == 1
    assert readiness_body["next_smallest_truthful_gap"] == "stage17_capability_library_operator_proposal_evidence_refs"
    assert readiness_body["routes"]["proposal_review_route"] == "/forge/proposals/decision"
    assert readiness_body["routes"]["operator_intake_apply_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/apply"
    )
    assert readiness_body["requirements"]["does_not_apply_reviews"] is True
    assert readiness_body["governance"]["read_only"] is True
    assert readiness_body["governance"]["does_not_write_proposal_review_receipts"] is True
    assert readiness_body["governance"]["does_not_approve_proposals"] is True
    assert readiness_body["governance"]["proposal_review_authority"] is False


def test_plugins_capability_library_proposal_evidence_plan_completes_before_review(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.api.routes import plugins

    pack_id = "ops.capability_library_proposal_evidence_complete"
    pack_version = "1.0.0"
    plugin_id = "capability_library_proposal_evidence_complete"
    proposal_id = "plugin_proposal_capability_library_proposal_evidence_complete"
    registry = {
        "plugins": {
            plugin_id: {
                "id": plugin_id,
                "name": "Capability Library Proposal Evidence Complete Plugin",
                "status": "staged",
                "enabled": False,
                "meta": {
                    "proposal_id": proposal_id,
                    "proposal_evidence": ["mission.capability_library_proposal_evidence_complete.repeat"],
                    "quality": {
                        "tests": ["tests/test_api_plugins.py"],
                        "docs": ["README.md"],
                        "claim_scope": "candidate_reference_only_not_pack_specific_proof",
                    },
                    "risk_tier": "normal",
                },
            }
        }
    }
    entries = [
        {
            "capability": plugin_id,
            "status": "staged",
            "metadata": {
                "pack_id": pack_id,
                "pack_version": pack_version,
            },
        }
    ]
    promotion_discipline = {
        "pack_total": 1,
        "ready_pack_count": 1,
        "blocked_pack_count": 0,
        "packs": [
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "pack_name": "Ops Capability Library Proposal Evidence Complete Pack",
                "status": "ready",
                "ready": True,
            }
        ],
    }

    body = plugins._capability_library_proposal_evidence_plan_projection(
        registry=registry,
        entries=entries,
        promotion_discipline=promotion_discipline,
        generated_plugin_sync_performed=False,
    )

    assert body["status"] == "proposal_evidence_complete"
    assert body["proposal_evidence_plan_ready"] is False
    assert body["candidate_capability_count"] == 1
    assert body["unique_proposal_count"] == 1
    assert body["proposal_evidence_missing_count"] == 0
    assert body["proposal_evidence_ready_count"] == 1
    assert body["missing_proposal_evidence_count"] == 0
    assert body["evidence_ready_proposal_count"] == 1
    assert body["proposal_review_missing_count"] == 1
    assert body["missing_requirement_counts"] == {"proposal_review": 1}
    assert body["next_smallest_truthful_gap"] == "stage17_capability_library_proposal_review_apply"

    pack = body["packs"][0]
    assert pack["pack_id"] == pack_id
    assert pack["proposal_evidence_missing_count"] == 0
    assert pack["proposal_evidence_ready_count"] == 1
    assert pack["capabilities"] == []
    assert pack["capabilities_truncated"] is False


def test_plugins_capability_library_proposal_evidence_remediation_backfills_existing_artifact_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    pack_id = "ops.capability_library_proposal_evidence_remediation"
    pack_version = "1.0.0"
    meta = {
        **_forge_promotion_meta("capability_library_proposal_evidence_remediation"),
        "pack_id": pack_id,
        "pack_version": pack_version,
        "pack_name": "Ops Capability Library Proposal Evidence Remediation Pack",
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
            "name": "Capability Library Proposal Evidence Remediation Plugin",
            "description": "Stage 17 proposal evidence remediation apply coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": meta,
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])
    proposal_id = str(built_body["proposal_id"])

    registry = plugins._load_registry()
    plugin = plugins._read_plugin(registry, plugin_id)
    assert plugin is not None
    plugin_meta = dict(plugin.get("meta") or {})
    plugin_meta.pop("proposal_evidence", None)
    plugin_meta.pop("evidence", None)
    plugin["meta"] = plugin_meta
    plugins._write_plugin(registry, plugins._normalize_plugin_record(plugin_id, plugin))
    plugins._save_registry_and_catalog(registry)

    _approve_capability_pack_operator_review(
        client,
        pack_id=pack_id,
        pack_version=pack_version,
    )

    remediation = client.get("/plugins/capabilities/library/proposal-evidence/remediation")

    assert remediation.status_code == 200
    remediation_body = remediation.json()
    assert remediation_body["ok"] is True
    assert remediation_body["kind"] == "plugin.capability_library.proposal_evidence_remediation"
    assert remediation_body["status"] == "ready_for_proposal_evidence_backfill"
    assert remediation_body["proposal_evidence_remediation_ready"] is True
    assert remediation_body["candidate_pack_count"] == 1
    assert remediation_body["candidate_capability_count"] == 1
    assert remediation_body["source_proposal_evidence_plan"]["proposal_evidence_missing_count"] == 0
    assert remediation_body["source_proposal_evidence_plan"]["proposal_evidence_ready_count"] == 1
    assert remediation_body["next_smallest_truthful_gap"] == (
        "stage17_capability_library_proposal_evidence_remediation_apply"
    )
    assert remediation_body["requirements"]["only_existing_linked_proposal_artifact_evidence"] is True
    assert remediation_body["requirements"]["no_synthetic_evidence"] is True
    assert remediation_body["governance"]["read_only"] is True
    assert remediation_body["governance"]["apply_requires_plugins_write_scope"] is True
    assert remediation_body["governance"]["does_not_approve_proposals"] is True
    assert remediation_body["governance"]["does_not_promote_capabilities"] is True
    assert remediation_body["governance"]["memory_write"] is False

    remediation_pack = remediation_body["packs"][0]
    assert remediation_pack["pack_id"] == pack_id
    assert remediation_pack["candidate_capability_count"] == 1
    remediation_capability = remediation_pack["capabilities"][0]
    assert remediation_capability["capability"] == plugin_id
    assert remediation_capability["proposal_id"] == proposal_id
    assert remediation_capability["metadata_proposal_evidence"] == []
    assert remediation_capability["linked_proposal_artifact_evidence"] == [
        "mission.capability_library_proposal_evidence_remediation.repeat"
    ]
    assert remediation_capability["writes_registry_metadata"] is True
    assert remediation_capability["writes_proposals"] is False
    assert remediation_capability["approves_proposals"] is False
    assert remediation_capability["promotes_capability"] is False

    dry_run = client.post(
        "/plugins/capabilities/library/proposal-evidence/remediation/apply",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "dry run proposal evidence backfill",
            "pack_ids": [pack_id],
            "dry_run": True,
            "max_pack_count": 1,
            "max_total_capability_count": 1,
            "max_capability_count_per_pack": 1,
        },
    )

    assert dry_run.status_code == 200
    dry_run_body = dry_run.json()
    assert dry_run_body["ok"] is True
    assert dry_run_body["applied"] is False
    assert dry_run_body["status"] == "dry_run"
    assert dry_run_body["planned_pack_count"] == 1
    assert dry_run_body["planned_capability_count"] == 1
    assert dry_run_body["governance"]["writes_registry_metadata"] is False
    assert dry_run_body["governance"]["writes_proposals"] is False
    assert dry_run_body["governance"]["does_not_approve_proposals"] is True
    assert dry_run_body["governance"]["does_not_promote_capabilities"] is True

    fetched_after_dry_run = client.get(f"/plugins/get?id={plugin_id}").json()["item"]
    assert "proposal_evidence" not in dict(fetched_after_dry_run.get("meta") or {})

    applied = client.post(
        "/plugins/capabilities/library/proposal-evidence/remediation/apply",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "apply proposal evidence backfill",
            "pack_ids": [pack_id],
            "dry_run": False,
            "max_pack_count": 1,
            "max_total_capability_count": 1,
            "max_capability_count_per_pack": 1,
        },
    )

    assert applied.status_code == 200
    applied_body = applied.json()
    assert applied_body["ok"] is True
    assert applied_body["applied"] is True
    assert applied_body["status"] == "recorded"
    assert applied_body["recorded_pack_count"] == 1
    assert applied_body["recorded_capability_count"] == 1
    assert applied_body["remaining_candidate_capability_count"] == 0
    assert applied_body["governance"]["writes_registry_metadata"] is True
    assert applied_body["governance"]["writes_receipts"] is False
    assert applied_body["governance"]["writes_proposals"] is False
    assert applied_body["governance"]["does_not_approve_proposals"] is True
    assert applied_body["governance"]["does_not_promote_capabilities"] is True
    assert applied_body["governance"]["does_not_enable_capabilities"] is True
    assert applied_body["governance"]["memory_write"] is False

    fetched = client.get(f"/plugins/get?id={plugin_id}")
    assert fetched.status_code == 200
    fetched_item = fetched.json()["item"]
    assert fetched_item["status"] == "staged"
    assert fetched_item["enabled"] is False
    stored_meta = dict(fetched_item.get("meta") or {})
    assert stored_meta["proposal_evidence"] == ["mission.capability_library_proposal_evidence_remediation.repeat"]
    assert stored_meta["proposal_evidence_link_source"] == (
        "stage17_capability_library_proposal_evidence_remediation_apply"
    )
    assert stored_meta["proposal_evidence_claim_scope"] == "existing_linked_proposal_artifact_friction_evidence"
    assert stored_meta["proposal_evidence_artifact_proposal_id"] == proposal_id
    assert stored_meta["proposal_evidence_writes_proposals"] is False
    assert stored_meta["proposal_evidence_approval_claimed"] is False

    proposal_state = plugins._plugin_proposal_review_state(proposal_id)
    assert proposal_state["approved"] is False
    assert proposal_state["review_status"] == "staged"


def test_plugins_capability_library_proposal_evidence_friction_summary_refs_backfill_existing_registry_refs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    pack_id = "ops.capability_library_proposal_evidence_friction_summary_refs"
    pack_version = "1.0.0"
    meta = {
        **_forge_promotion_meta("capability_library_proposal_evidence_friction_summary_refs"),
        "pack_id": pack_id,
        "pack_version": pack_version,
        "pack_name": "Ops Capability Library Proposal Evidence Friction Summary Refs Pack",
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
            "name": "Capability Library Proposal Evidence Friction Summary Refs Plugin",
            "description": "Stage 17 proposal evidence friction-summary refs apply coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": meta,
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])
    proposal_id = str(built_body["proposal_id"])
    expected_ref = f"registry.plugins.{plugin_id}.meta.friction_summary"

    registry = plugins._load_registry()
    plugin = plugins._read_plugin(registry, plugin_id)
    assert plugin is not None
    plugin_meta = dict(plugin.get("meta") or {})
    plugin_meta.pop("proposal_evidence", None)
    plugin_meta.pop("evidence", None)
    plugin_meta["friction_summary"] = meta["friction_summary"]
    plugin["meta"] = plugin_meta
    plugins._write_plugin(registry, plugins._normalize_plugin_record(plugin_id, plugin))
    plugins._save_registry_and_catalog(registry)

    _approve_capability_pack_operator_review(
        client,
        pack_id=pack_id,
        pack_version=pack_version,
    )

    refs = client.get("/plugins/capabilities/library/proposal-evidence/friction-summary-refs")

    assert refs.status_code == 200
    refs_body = refs.json()
    assert refs_body["ok"] is True
    assert refs_body["kind"] == "plugin.capability_library.proposal_evidence_friction_summary_refs"
    assert refs_body["status"] == "ready_for_proposal_evidence_friction_summary_ref_backfill"
    assert refs_body["proposal_evidence_friction_summary_refs_ready"] is True
    assert refs_body["candidate_pack_count"] == 1
    assert refs_body["candidate_capability_count"] == 1
    assert refs_body["requirements"]["only_existing_registry_friction_summary"] is True
    assert refs_body["requirements"]["records_reference_not_friction_summary_body"] is True
    assert refs_body["requirements"]["not_independent_verification"] is True
    assert refs_body["requirements"]["requires_future_review"] is True
    assert refs_body["requirements"]["no_synthetic_evidence"] is True
    assert refs_body["governance"]["read_only"] is True
    assert refs_body["governance"]["apply_requires_plugins_write_scope"] is True
    assert refs_body["governance"]["does_not_approve_proposals"] is True
    assert refs_body["governance"]["does_not_promote_capabilities"] is True
    assert refs_body["governance"]["memory_write"] is False
    assert refs_body["next_smallest_truthful_gap"] == (
        "stage17_capability_library_proposal_evidence_friction_summary_refs_apply"
    )

    refs_pack = refs_body["packs"][0]
    assert refs_pack["pack_id"] == pack_id
    assert refs_pack["candidate_capability_count"] == 1
    refs_capability = refs_pack["capabilities"][0]
    assert refs_capability["capability"] == plugin_id
    assert refs_capability["proposal_id"] == proposal_id
    assert refs_capability["metadata_proposal_evidence"] == []
    assert refs_capability["friction_summary_field"] == "friction_summary"
    assert refs_capability["friction_summary_ref"] == expected_ref
    assert refs_capability["evidence_source"] == "existing_registry_friction_summary_ref"
    assert refs_capability["writes_registry_metadata"] is True
    assert refs_capability["writes_proposals"] is False
    assert refs_capability["approves_proposals"] is False
    assert refs_capability["promotes_capability"] is False
    assert refs_capability["requires_future_review"] is True

    dry_run = client.post(
        "/plugins/capabilities/library/proposal-evidence/friction-summary-refs/apply",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "dry run friction summary ref backfill",
            "pack_ids": [pack_id],
            "dry_run": True,
            "max_pack_count": 1,
            "max_total_capability_count": 1,
            "max_capability_count_per_pack": 1,
        },
    )

    assert dry_run.status_code == 200
    dry_run_body = dry_run.json()
    assert dry_run_body["ok"] is True
    assert dry_run_body["applied"] is False
    assert dry_run_body["status"] == "dry_run"
    assert dry_run_body["planned_pack_count"] == 1
    assert dry_run_body["planned_capability_count"] == 1
    assert dry_run_body["governance"]["writes_registry_metadata"] is False
    assert dry_run_body["governance"]["writes_proposals"] is False
    assert dry_run_body["governance"]["only_existing_registry_friction_summary"] is True
    assert dry_run_body["governance"]["evidence_claim_scope"] == (
        "existing_registry_friction_summary_reference_not_independent_verification"
    )
    assert dry_run_body["governance"]["does_not_approve_proposals"] is True
    assert dry_run_body["governance"]["does_not_promote_capabilities"] is True

    fetched_after_dry_run = client.get(f"/plugins/get?id={plugin_id}").json()["item"]
    assert "proposal_evidence" not in dict(fetched_after_dry_run.get("meta") or {})

    applied = client.post(
        "/plugins/capabilities/library/proposal-evidence/friction-summary-refs/apply",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "apply friction summary ref backfill",
            "pack_ids": [pack_id],
            "dry_run": False,
            "max_pack_count": 1,
            "max_total_capability_count": 1,
            "max_capability_count_per_pack": 1,
        },
    )

    assert applied.status_code == 200
    applied_body = applied.json()
    assert applied_body["ok"] is True
    assert applied_body["applied"] is True
    assert applied_body["status"] == "recorded"
    assert applied_body["recorded_pack_count"] == 1
    assert applied_body["recorded_capability_count"] == 1
    assert applied_body["remaining_candidate_capability_count"] == 0
    assert applied_body["governance"]["writes_registry_metadata"] is True
    assert applied_body["governance"]["writes_receipts"] is False
    assert applied_body["governance"]["writes_proposals"] is False
    assert applied_body["governance"]["only_existing_registry_friction_summary"] is True
    assert applied_body["governance"]["evidence_claim_scope"] == (
        "existing_registry_friction_summary_reference_not_independent_verification"
    )
    assert applied_body["governance"]["does_not_approve_proposals"] is True
    assert applied_body["governance"]["does_not_promote_capabilities"] is True
    assert applied_body["governance"]["does_not_enable_capabilities"] is True
    assert applied_body["governance"]["memory_write"] is False

    fetched = client.get(f"/plugins/get?id={plugin_id}")
    assert fetched.status_code == 200
    fetched_item = fetched.json()["item"]
    assert fetched_item["status"] == "staged"
    assert fetched_item["enabled"] is False
    stored_meta = dict(fetched_item.get("meta") or {})
    assert stored_meta["proposal_evidence"] == [expected_ref]
    assert stored_meta["proposal_evidence_link_source"] == (
        "stage17_capability_library_proposal_evidence_friction_summary_refs_apply"
    )
    assert stored_meta["proposal_evidence_claim_scope"] == (
        "existing_registry_friction_summary_reference_not_independent_verification"
    )
    assert stored_meta["proposal_evidence_friction_summary_ref"] == expected_ref
    assert stored_meta["proposal_evidence_friction_summary_field"] == "friction_summary"
    assert stored_meta["proposal_evidence_friction_summary_ref_route"] == (
        "/plugins/capabilities/library/proposal-evidence/friction-summary-refs/apply"
    )
    assert stored_meta["proposal_evidence_friction_summary_ref_requires_future_review"] is True
    assert stored_meta["proposal_evidence_artifact_proposal_id"] == proposal_id
    assert stored_meta["proposal_evidence_writes_proposals"] is False
    assert stored_meta["proposal_evidence_approval_claimed"] is False

    proposal_state = plugins._plugin_proposal_review_state(proposal_id)
    assert proposal_state["approved"] is False
    assert proposal_state["review_status"] == "staged"


def test_plugins_capability_library_proposal_evidence_source_readiness_inventory(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    pack_id = "ops.capability_library_proposal_evidence_source_readiness"
    pack_version = "1.0.0"
    meta = {
        **_forge_promotion_meta("capability_library_proposal_evidence_source_readiness"),
        "pack_id": pack_id,
        "pack_version": pack_version,
        "pack_name": "Ops Capability Library Proposal Evidence Source Readiness Pack",
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
            "name": "Capability Library Proposal Evidence Source Readiness Plugin",
            "description": "Stage 17 proposal evidence source readiness coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": meta,
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])
    proposal_id = str(built_body["proposal_id"])
    validation_receipt_id = str(built_body["validation_receipt_id"])
    local_artifact_refs = [
        proposal_id,
        f"data/artifacts/plugins/proposals/{proposal_id}.json",
        validation_receipt_id,
        f"data/artifacts/plugins/validations/{validation_receipt_id}.json",
    ]

    registry = plugins._load_registry()
    plugin = plugins._read_plugin(registry, plugin_id)
    assert plugin is not None
    plugin_meta = dict(plugin.get("meta") or {})
    plugin_meta.pop("proposal_evidence", None)
    plugin_meta.pop("evidence", None)
    plugin_meta.pop("friction_summary", None)
    plugin_meta.pop("friction", None)
    plugin["meta"] = plugin_meta
    plugins._write_plugin(registry, plugins._normalize_plugin_record(plugin_id, plugin))
    plugins._save_registry_and_catalog(registry)
    proposal_path = plugins._plugin_proposal_path(proposal_id)
    proposal_record = json.loads(proposal_path.read_text(encoding="utf-8"))
    assert isinstance(proposal_record, dict)
    friction = dict(proposal_record.get("friction") or {})
    friction["evidence"] = []
    proposal_record["friction"] = friction
    proposal_path.write_text(json.dumps(proposal_record, indent=2, sort_keys=True), encoding="utf-8")

    _approve_capability_pack_operator_review(
        client,
        pack_id=pack_id,
        pack_version=pack_version,
    )

    readiness = client.get("/plugins/capabilities/library/proposal-evidence/source-readiness")

    assert readiness.status_code == 200
    readiness_body = readiness.json()
    assert readiness_body["ok"] is True
    assert readiness_body["kind"] == "plugin.capability_library.proposal_evidence_source_readiness"
    assert readiness_body["stage"] == "Stage 17 / Capability Economy"
    assert readiness_body["status"] == "operator_evidence_refs_required"
    _assert_stage17_projection_readback(
        readiness_body,
        projection_scope="full_library",
        global_counts_included=True,
    )
    assert readiness_body["proposal_evidence_source_readiness_ready"] is True
    assert readiness_body["proposal_evidence_missing_count"] == 1
    assert readiness_body["proposal_evidence_ready_count"] == 0
    assert readiness_body["automatic_source_candidate_capability_count"] == 0
    assert readiness_body["automatic_sources_exhausted"] is True
    assert readiness_body["operator_evidence_intake_candidate_capability_count"] == 1
    assert readiness_body["operator_evidence_ref_required_count"] == 1
    assert readiness_body["recorded_operator_evidence_capability_count"] == 0
    assert readiness_body["next_operator_evidence_batch_ready"] is True
    assert readiness_body["next_operator_evidence_batch_capability_count"] == 1
    assert readiness_body["next_smallest_truthful_gap"] == (
        "stage17_capability_library_operator_proposal_evidence_refs"
    )
    assert readiness_body["routes"]["proposal_evidence_source_readiness_route"] == (
        "/plugins/capabilities/library/proposal-evidence/source-readiness"
    )
    assert readiness_body["routes"]["operator_intake_export_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/export"
    )
    assert readiness_body["requirements"]["read_only_source_inventory"] is True
    assert readiness_body["requirements"]["no_synthetic_evidence"] is True
    assert readiness_body["requirements"]["does_not_validate_evidence_truth"] is True
    assert readiness_body["governance"]["read_only"] is True
    assert readiness_body["governance"]["does_not_write_proposals"] is True
    assert readiness_body["governance"]["does_not_approve_proposals"] is True
    assert readiness_body["governance"]["does_not_promote_capabilities"] is True
    assert readiness_body["governance"]["memory_write"] is False

    inventory = readiness_body["source_inventory"]
    assert inventory["existing_linked_proposal_artifact"]["candidate_capability_count"] == 0
    assert inventory["existing_linked_proposal_artifact"]["writes_proposals"] is False
    assert inventory["existing_registry_friction_summary_ref"]["candidate_capability_count"] == 0
    assert inventory["existing_registry_friction_summary_ref"]["records_reference_not_friction_summary_body"] is True
    assert inventory["operator_supplied_evidence_refs"]["ready"] is True
    assert inventory["operator_supplied_evidence_refs"]["candidate_capability_count"] == 1
    assert inventory["operator_supplied_evidence_refs"]["does_not_validate_evidence_truth"] is True
    assert inventory["recorded_operator_evidence_refs"]["recorded_capability_count"] == 0
    assert inventory["synthetic_evidence"]["status"] == "disallowed"
    next_batch = readiness_body["next_operator_evidence_batch"]
    assert next_batch["status"] == "ready_for_operator_evidence_batch"
    assert next_batch["ready"] is True
    assert next_batch["batch_source"] == "operator_evidence_intake_checklist_first_visible_pack"
    assert next_batch["pack_id"] == pack_id
    assert next_batch["pack_version"] == pack_version
    assert next_batch["pack_candidate_capability_count"] == 1
    assert next_batch["batch_capability_count"] == 1
    assert next_batch["batch_evidence_ref_required_count"] == 1
    assert next_batch["batch_capabilities_truncated"] is False
    assert next_batch["operator_must_supply_evidence_refs"] is True
    assert next_batch["operator_supplied_evidence_not_independently_verified"] is True
    assert next_batch["does_not_validate_evidence_truth"] is True
    assert next_batch["dry_run_required_before_apply"] is True
    assert next_batch["no_synthetic_evidence"] is True
    assert next_batch["local_artifact_ref_hints_ready"] is True
    assert next_batch["local_artifact_ref_hint_capability_count"] == 1
    assert next_batch["local_artifact_ref_hint_evidence_ref_count"] == 4
    assert next_batch["local_artifact_ref_hints_complete"] is True
    assert next_batch["operator_must_review_local_artifact_refs_before_apply"] is True
    assert next_batch["local_artifact_refs_by_capability"] == {plugin_id: local_artifact_refs}
    assert next_batch["apply_payload_hint"] == {
        "pack_ids": [pack_id],
        "capability_ids": [plugin_id],
        "evidence_refs": [],
        "evidence_refs_by_capability": {plugin_id: local_artifact_refs},
        "dry_run": True,
        "max_pack_count": 1,
        "max_total_capability_count": 1,
        "max_capability_count_per_pack": 1,
    }
    assert next_batch["routes"]["operator_intake_apply_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/apply"
    )
    next_batch_capability = next_batch["capabilities"][0]
    assert next_batch_capability["capability"] == plugin_id
    assert next_batch_capability["proposal_id"] == proposal_id
    assert next_batch_capability["evidence_refs_required"] is True
    assert next_batch_capability["local_artifact_ref_hint"]["ready"] is True
    assert next_batch_capability["local_artifact_ref_hint"]["claim_scope"] == (
        "local_artifact_reference_hint_not_independent_evidence_verification"
    )
    assert next_batch_capability["local_artifact_ref_hint"]["evidence_refs"] == local_artifact_refs
    assert next_batch_capability["intake_apply_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/apply"
    )

    friction_pack_id = "ops.capability_library_proposal_evidence_source_readiness_friction"
    friction_meta = {
        **_forge_promotion_meta("capability_library_proposal_evidence_source_readiness_friction"),
        "pack_id": friction_pack_id,
        "pack_version": pack_version,
        "pack_name": "Ops Capability Library Proposal Evidence Source Readiness Friction Pack",
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
    friction_built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Library Proposal Evidence Source Readiness Friction Plugin",
            "description": "Stage 17 proposal evidence source readiness friction coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": friction_meta,
        },
    )
    assert friction_built.status_code == 200
    friction_body = friction_built.json()
    assert friction_body["ok"] is True
    friction_plugin_id = str(friction_body["plugin_id"])
    friction_proposal_id = str(friction_body["proposal_id"])

    registry = plugins._load_registry()
    friction_plugin = plugins._read_plugin(registry, friction_plugin_id)
    assert friction_plugin is not None
    friction_plugin_meta = dict(friction_plugin.get("meta") or {})
    friction_plugin_meta.pop("proposal_evidence", None)
    friction_plugin_meta.pop("evidence", None)
    friction_plugin_meta["friction_summary"] = friction_meta["friction_summary"]
    friction_plugin["meta"] = friction_plugin_meta
    plugins._write_plugin(registry, plugins._normalize_plugin_record(friction_plugin_id, friction_plugin))
    plugins._save_registry_and_catalog(registry)
    friction_proposal_path = plugins._plugin_proposal_path(friction_proposal_id)
    friction_proposal_record = json.loads(friction_proposal_path.read_text(encoding="utf-8"))
    assert isinstance(friction_proposal_record, dict)
    friction_proposal = dict(friction_proposal_record.get("friction") or {})
    friction_proposal["evidence"] = []
    friction_proposal_record["friction"] = friction_proposal
    friction_proposal_path.write_text(
        json.dumps(friction_proposal_record, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    _approve_capability_pack_operator_review(
        client,
        pack_id=friction_pack_id,
        pack_version=pack_version,
    )

    readiness_with_friction = client.get("/plugins/capabilities/library/proposal-evidence/source-readiness")

    assert readiness_with_friction.status_code == 200
    friction_readiness_body = readiness_with_friction.json()
    assert friction_readiness_body["ok"] is True
    assert friction_readiness_body["status"] == "ready_for_friction_summary_ref_backfill"
    assert friction_readiness_body["proposal_evidence_missing_count"] == 2
    assert friction_readiness_body["automatic_source_candidate_capability_count"] == 1
    assert friction_readiness_body["automatic_sources_exhausted"] is False
    assert friction_readiness_body["operator_evidence_intake_candidate_capability_count"] == 2
    assert friction_readiness_body["source_inventory"]["existing_registry_friction_summary_ref"]["ready"] is True
    assert (
        friction_readiness_body["source_inventory"]["existing_registry_friction_summary_ref"][
            "candidate_capability_count"
        ]
        == 1
    )
    assert friction_readiness_body["source_inventory"]["operator_supplied_evidence_refs"]["ready"] is True


def test_plugins_capability_library_operator_proposal_evidence_source_readiness_hints_apply_local_refs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    pack_id = "ops.capability_library_operator_proposal_evidence_local_hints"
    pack_version = "1.0.0"
    built = client.post(
        "/plugins/build",
        json={
            "name": "Capability Library Operator Proposal Evidence Local Hints Plugin",
            "description": "Stage 17 local artifact evidence hint coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": {
                **_forge_promotion_meta("capability_library_operator_proposal_evidence_local_hints"),
                "pack_id": pack_id,
                "pack_version": pack_version,
                "pack_name": "Ops Capability Library Operator Proposal Evidence Local Hints Pack",
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
            },
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])
    proposal_id = str(built_body["proposal_id"])
    validation_receipt_id = str(built_body["validation_receipt_id"])
    local_artifact_refs = [
        proposal_id,
        f"data/artifacts/plugins/proposals/{proposal_id}.json",
        validation_receipt_id,
        f"data/artifacts/plugins/validations/{validation_receipt_id}.json",
    ]

    registry = plugins._load_registry()
    plugin = plugins._read_plugin(registry, plugin_id)
    assert plugin is not None
    plugin_meta = dict(plugin.get("meta") or {})
    plugin_meta.pop("proposal_evidence", None)
    plugin_meta.pop("evidence", None)
    plugin["meta"] = plugin_meta
    plugins._write_plugin(registry, plugins._normalize_plugin_record(plugin_id, plugin))
    plugins._save_registry_and_catalog(registry)

    proposal_path = plugins._plugin_proposal_path(proposal_id)
    proposal_record = json.loads(proposal_path.read_text(encoding="utf-8"))
    proposal_record["friction"]["evidence"] = []
    proposal_path.write_text(json.dumps(proposal_record, indent=2, sort_keys=True), encoding="utf-8")

    _approve_capability_pack_operator_review(
        client,
        pack_id=pack_id,
        pack_version=pack_version,
    )

    before = client.get("/plugins/capabilities/library/proposal-evidence/source-readiness")
    assert before.status_code == 200
    before_body = before.json()
    assert before_body["proposal_evidence_missing_count"] == 1
    assert before_body["operator_evidence_intake_candidate_capability_count"] == 1
    next_batch = before_body["next_operator_evidence_batch"]
    assert next_batch["local_artifact_ref_hints_ready"] is True
    assert next_batch["local_artifact_refs_by_capability"] == {plugin_id: local_artifact_refs}
    assert next_batch["apply_payload_hint"]["evidence_refs"] == []
    assert next_batch["apply_payload_hint"]["evidence_refs_by_capability"] == {plugin_id: local_artifact_refs}

    export = client.get("/plugins/capabilities/library/proposal-evidence/operator-intake/export")
    assert export.status_code == 200
    export_body = export.json()
    export_row = export_body["packs"][0]["rows"][0]
    assert export_row["capability"] == plugin_id
    assert export_row["evidence_refs_input"] == ""
    assert export_row["suggested_evidence_refs"] == local_artifact_refs
    assert json.loads(export_row["suggested_evidence_refs_input"]) == local_artifact_refs
    assert export_row["suggested_evidence_ref_source"] == "local_proposal_validation_artifact_refs"
    assert export_row["suggested_evidence_refs_require_operator_confirmation"] is True
    assert export_row["apply_payload_hint"]["evidence_refs"] == []
    assert export_row["apply_payload_hint"]["evidence_refs_by_capability"] == {plugin_id: local_artifact_refs}

    suggested_import_preview = client.post(
        "/plugins/capabilities/library/proposal-evidence/operator-intake/import-preview",
        json={
            "actor": _PLUGIN_ACTOR,
            "rows": [export_row],
            "use_suggested_evidence_refs": True,
            "max_row_count": 1,
            "max_apply_group_count": 1,
        },
    )

    assert suggested_import_preview.status_code == 200
    suggested_import_preview_body = suggested_import_preview.json()
    assert suggested_import_preview_body["ok"] is True
    assert suggested_import_preview_body["ready_row_count"] == 1
    assert suggested_import_preview_body["pending_row_count"] == 0
    assert suggested_import_preview_body["invalid_row_count"] == 0
    assert suggested_import_preview_body["use_suggested_evidence_refs"] is True
    assert suggested_import_preview_body["suggested_evidence_refs_used_count"] == 1
    assert suggested_import_preview_body["ready_rows"][0]["evidence_refs_source"] == "suggested_local_artifact_refs"
    assert suggested_import_preview_body["ready_rows"][0]["suggested_evidence_refs_used"] is True
    suggested_apply_group = suggested_import_preview_body["apply_payload_groups"][0]
    assert suggested_apply_group["preview_payload"]["evidence_refs"] == []
    assert suggested_apply_group["preview_payload"]["evidence_refs_by_capability"] == {plugin_id: local_artifact_refs}
    fetched_after_suggested_preview = client.get(f"/plugins/get?id={plugin_id}").json()["item"]
    assert "proposal_evidence" not in dict(fetched_after_suggested_preview.get("meta") or {})

    evidence_payload = {
        "actor": _PLUGIN_ACTOR,
        "reason": "dry run local artifact proposal evidence hints",
        **next_batch["apply_payload_hint"],
    }
    dry_run = client.post(
        "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
        json=evidence_payload,
    )
    assert dry_run.status_code == 200
    dry_run_body = dry_run.json()
    assert dry_run_body["ok"] is True
    assert dry_run_body["applied"] is False
    assert dry_run_body["status"] == "dry_run"
    assert dry_run_body["planned_capability_count"] == 1
    assert dry_run_body["evidence_ref_count"] == 4
    assert dry_run_body["shared_evidence_ref_count"] == 0
    assert dry_run_body["capability_specific_evidence_ref_count"] == 4
    assert dry_run_body["before"]["proposal_evidence_missing_count"] == 1
    assert dry_run_body["before"]["projection_scope"] == "selected_capabilities"
    assert dry_run_body["before"]["global_counts_included"] is False
    assert dry_run_body["governance"]["writes_registry_metadata"] is False
    assert dry_run_body["governance"]["does_not_promote_capabilities"] is True
    assert dry_run_body["governance"]["does_not_execute_capabilities"] is True

    evidence_payload["dry_run"] = False
    evidence_payload["dry_run_fingerprint"] = dry_run_body["dry_run_fingerprint"]
    applied = client.post(
        "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
        json=evidence_payload,
    )
    assert applied.status_code == 200
    applied_body = applied.json()
    assert applied_body["ok"] is True
    assert applied_body["applied"] is True
    assert applied_body["status"] == "recorded"
    assert applied_body["recorded_capability_count"] == 1
    assert applied_body["evidence_ref_count"] == 4
    assert applied_body["remaining_proposal_evidence_missing_count"] == 0
    assert applied_body["remaining_proposal_evidence_ready_count"] == 1
    assert applied_body["governance"]["writes_registry_metadata"] is True
    assert applied_body["governance"]["writes_proposals"] is False
    assert applied_body["governance"]["does_not_approve_proposals"] is True
    assert applied_body["governance"]["does_not_promote_capabilities"] is True
    assert applied_body["governance"]["does_not_enable_capabilities"] is True
    assert applied_body["governance"]["does_not_execute_capabilities"] is True

    after = client.get("/plugins/capabilities/library/proposal-evidence/source-readiness")
    assert after.status_code == 200
    after_body = after.json()
    assert after_body["proposal_evidence_missing_count"] == 0
    assert after_body["recorded_operator_evidence_capability_count"] == 1
    assert after_body["recorded_operator_evidence_ref_count"] == 4

    fetched = client.get(f"/plugins/get?id={plugin_id}")
    assert fetched.status_code == 200
    fetched_meta = dict(fetched.json()["item"].get("meta") or {})
    assert fetched_meta["proposal_evidence"] == local_artifact_refs
    assert fetched_meta["proposal_evidence_claim_scope"] == (
        "operator_supplied_friction_evidence_reference_not_independent_verification"
    )
    assert fetched_meta["proposal_evidence_writes_proposals"] is False
    assert fetched_meta["proposal_evidence_approval_claimed"] is False


def test_plugins_capability_library_operator_proposal_evidence_intake_records_operator_refs_only(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    pack_id = "ops.capability_library_operator_proposal_evidence_intake"
    pack_version = "1.0.0"
    evidence_ref = "operator.case.capability_library_operator_proposal_evidence_intake.repeat"
    meta = {
        **_forge_promotion_meta("capability_library_operator_proposal_evidence_intake"),
        "pack_id": pack_id,
        "pack_version": pack_version,
        "pack_name": "Ops Capability Library Operator Proposal Evidence Intake Pack",
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
            "name": "Capability Library Operator Proposal Evidence Intake Plugin",
            "description": "Stage 17 operator proposal evidence intake coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": meta,
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])
    proposal_id = str(built_body["proposal_id"])
    validation_receipt_id = str(built_body["validation_receipt_id"])
    local_artifact_refs = [
        proposal_id,
        f"data/artifacts/plugins/proposals/{proposal_id}.json",
        validation_receipt_id,
        f"data/artifacts/plugins/validations/{validation_receipt_id}.json",
    ]

    registry = plugins._load_registry()
    plugin = plugins._read_plugin(registry, plugin_id)
    assert plugin is not None
    plugin_meta = dict(plugin.get("meta") or {})
    plugin_meta.pop("proposal_evidence", None)
    plugin_meta.pop("evidence", None)
    plugin["meta"] = plugin_meta
    plugins._write_plugin(registry, plugins._normalize_plugin_record(plugin_id, plugin))
    plugins._save_registry_and_catalog(registry)

    proposal_path = plugins._plugin_proposal_path(proposal_id)
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    proposal["friction"]["evidence"] = []
    proposal_path.write_text(json.dumps(proposal, indent=2, sort_keys=True), encoding="utf-8")

    _approve_capability_pack_operator_review(
        client,
        pack_id=pack_id,
        pack_version=pack_version,
    )

    checklist = client.get("/plugins/capabilities/library/proposal-evidence/operator-intake/checklist")
    assert checklist.status_code == 200
    checklist_body = checklist.json()
    assert checklist_body["ok"] is True
    assert checklist_body["kind"] == "plugin.capability_library.operator_proposal_evidence_intake.checklist"
    assert checklist_body["status"] == "ready_for_operator_evidence_refs"
    assert checklist_body["operator_evidence_intake_checklist_ready"] is True
    assert checklist_body["candidate_pack_count"] == 1
    assert checklist_body["candidate_capability_count"] == 1
    assert checklist_body["evidence_ref_required_count"] == 1
    assert checklist_body["source_proposal_evidence_plan"]["proposal_evidence_missing_count"] == 1
    assert checklist_body["routes"]["operator_intake_apply_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/apply"
    )
    assert checklist_body["requirements"]["operator_evidence_refs_required"] is True
    assert checklist_body["requirements"]["dry_run_required_before_apply"] is True
    assert checklist_body["governance"]["read_only"] is True
    assert checklist_body["governance"]["writes_registry_metadata"] is False
    assert checklist_body["governance"]["does_not_approve_proposals"] is True
    assert checklist_body["governance"]["does_not_promote_capabilities"] is True
    assert checklist_body["governance"]["memory_write"] is False
    checklist_pack = checklist_body["packs"][0]
    assert checklist_pack["pack_id"] == pack_id
    assert checklist_pack["candidate_capability_count"] == 1
    assert checklist_pack["evidence_ref_required_count"] == 1
    assert checklist_pack["claim_scope"] == (
        "operator_supplied_friction_evidence_reference_not_independent_verification"
    )
    checklist_capability = checklist_pack["capabilities"][0]
    assert checklist_capability["capability"] == plugin_id
    assert checklist_capability["proposal_id"] == proposal_id
    assert checklist_capability["evidence_refs_required"] is True
    assert checklist_capability["operator_supplied_evidence_not_independently_verified"] is True
    assert checklist_capability["intake_apply_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/apply"
    )

    worksheet = client.get("/plugins/capabilities/library/proposal-evidence/operator-intake/worksheet")
    assert worksheet.status_code == 200
    worksheet_body = worksheet.json()
    assert worksheet_body["ok"] is True
    assert worksheet_body["kind"] == "plugin.capability_library.operator_proposal_evidence_intake.worksheet"
    assert worksheet_body["status"] == "ready_for_operator_evidence_collection"
    assert worksheet_body["operator_evidence_intake_worksheet_ready"] is True
    assert worksheet_body["worksheet_pack_count"] == 1
    assert worksheet_body["worksheet_row_count"] == 1
    assert worksheet_body["evidence_ref_required_count"] == 1
    assert worksheet_body["source_proposal_evidence_plan"]["proposal_evidence_missing_count"] == 1
    assert worksheet_body["routes"]["operator_intake_worksheet_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/worksheet"
    )
    assert worksheet_body["routes"]["operator_intake_apply_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/apply"
    )
    assert worksheet_body["routes"]["proposal_review_apply_readiness_route"] == (
        "/plugins/capabilities/library/proposal-review/apply-readiness"
    )
    assert worksheet_body["requirements"]["worksheet_contains_blank_evidence_slots"] is True
    assert worksheet_body["requirements"]["no_synthetic_evidence"] is True
    assert worksheet_body["requirements"]["pack_or_capability_scoped_apply_required"] is True
    assert worksheet_body["governance"]["read_only"] is True
    assert worksheet_body["governance"]["writes_registry_metadata"] is False
    assert worksheet_body["governance"]["does_not_approve_proposals"] is True
    assert worksheet_body["governance"]["does_not_promote_capabilities"] is True
    assert worksheet_body["governance"]["memory_write"] is False
    worksheet_pack = worksheet_body["packs"][0]
    assert worksheet_pack["pack_id"] == pack_id
    assert worksheet_pack["worksheet_row_count"] == 1
    assert worksheet_pack["evidence_ref_required_count"] == 1
    worksheet_row = worksheet_pack["rows"][0]
    assert worksheet_row["capability"] == plugin_id
    assert worksheet_row["proposal_id"] == proposal_id
    assert worksheet_row["operator_evidence_refs"] == []
    assert worksheet_row["operator_evidence_ref_count"] == 0
    assert worksheet_row["operator_evidence_refs_required"] is True
    assert worksheet_row["evidence_ref_collection_status"] == "pending_operator_input"
    assert worksheet_row["operator_supplied_evidence_not_independently_verified"] is True
    assert worksheet_row["requires_future_proposal_review"] is True
    assert worksheet_row["intake_apply_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/apply"
    )
    assert worksheet_row["apply_payload_hint"] == {
        "pack_ids": [pack_id],
        "capability_ids": [plugin_id],
        "evidence_refs": [],
        "dry_run": True,
    }

    export = client.get("/plugins/capabilities/library/proposal-evidence/operator-intake/export")
    assert export.status_code == 200
    export_body = export.json()
    assert export_body["ok"] is True
    assert export_body["kind"] == "plugin.capability_library.operator_proposal_evidence_intake.export"
    assert export_body["status"] == "ready_for_operator_evidence_export"
    assert export_body["operator_evidence_intake_export_ready"] is True
    assert export_body["export_pack_count"] == 1
    assert export_body["export_row_count"] == 1
    assert export_body["exported_row_count"] == 1
    assert export_body["evidence_ref_required_count"] == 1
    assert export_body["export_rows_truncated"] is False
    assert export_body["row_limit"] >= 1
    assert export_body["source_proposal_evidence_plan"]["proposal_evidence_missing_count"] == 1
    assert export_body["routes"]["operator_intake_export_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/export"
    )
    assert export_body["routes"]["operator_intake_apply_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/apply"
    )
    assert export_body["routes"]["operator_intake_import_preview_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/import-preview"
    )
    assert export_body["requirements"]["export_contains_blank_evidence_slots"] is True
    assert export_body["requirements"]["no_synthetic_evidence"] is True
    assert export_body["requirements"]["import_requires_governed_apply_route"] is True
    assert export_body["requirements"]["does_not_validate_evidence_truth"] is True
    assert export_body["governance"]["read_only"] is True
    assert export_body["governance"]["writes_registry_metadata"] is False
    assert export_body["governance"]["does_not_approve_proposals"] is True
    assert export_body["governance"]["does_not_promote_capabilities"] is True
    assert export_body["governance"]["memory_write"] is False
    assert export_body["export_schema"] == {
        "format": "json",
        "evidence_refs_input_format": "comma_separated_or_json_array",
        "columns": [
            "pack_id",
            "pack_version",
            "capability",
            "proposal_id",
            "evidence_refs_input",
            "suggested_evidence_refs_input",
        ],
        "blank_evidence_refs_input_means_not_ready_for_apply": True,
    }
    export_pack = export_body["packs"][0]
    assert export_pack["pack_id"] == pack_id
    assert export_pack["export_row_count"] == 1
    assert export_pack["exported_row_count"] == 1
    assert export_pack["evidence_ref_required_count"] == 1
    export_row = export_pack["rows"][0]
    assert export_row["pack_id"] == pack_id
    assert export_row["pack_version"] == pack_version
    assert export_row["capability"] == plugin_id
    assert export_row["proposal_id"] == proposal_id
    assert export_row["evidence_refs_input"] == ""
    assert export_row["evidence_refs_input_format"] == "comma_separated_or_json_array"
    assert export_row["suggested_evidence_refs"] == local_artifact_refs
    assert json.loads(export_row["suggested_evidence_refs_input"]) == local_artifact_refs
    assert export_row["suggested_evidence_ref_source"] == "local_proposal_validation_artifact_refs"
    assert export_row["suggested_evidence_refs_require_operator_confirmation"] is True
    assert export_row["operator_evidence_refs_required"] is True
    assert export_row["dry_run_required"] is True
    assert export_row["apply_payload_hint"] == {
        "pack_ids": [pack_id],
        "capability_ids": [plugin_id],
        "evidence_refs": [],
        "evidence_refs_by_capability": {plugin_id: local_artifact_refs},
        "dry_run": True,
    }
    assert export_row["operator_supplied_evidence_not_independently_verified"] is True
    assert export_row["requires_future_proposal_review"] is True
    assert export_row["intake_apply_route"] == ("/plugins/capabilities/library/proposal-evidence/operator-intake/apply")

    import_preview = client.post(
        "/plugins/capabilities/library/proposal-evidence/operator-intake/import-preview",
        json={
            "actor": _PLUGIN_ACTOR,
            "rows": [
                {**export_row, "evidence_refs_input": json.dumps([evidence_ref, evidence_ref])},
                {**export_row, "evidence_refs_input": ""},
                {**export_row, "capability": "missing.operator_import_preview", "evidence_refs_input": evidence_ref},
            ],
            "max_row_count": 10,
            "max_apply_group_count": 10,
        },
    )

    assert import_preview.status_code == 200
    import_preview_body = import_preview.json()
    assert import_preview_body["ok"] is True
    assert import_preview_body["kind"] == ("plugin.capability_library.operator_proposal_evidence_intake.import_preview")
    assert import_preview_body["status"] == "ready_for_operator_evidence_import_preview"
    assert import_preview_body["operator_evidence_intake_import_preview_ready"] is True
    assert import_preview_body["input_row_count"] == 3
    assert import_preview_body["processed_row_count"] == 3
    assert import_preview_body["ready_row_count"] == 1
    assert import_preview_body["pending_row_count"] == 1
    assert import_preview_body["invalid_row_count"] == 1
    assert import_preview_body["apply_group_count"] == 1
    assert import_preview_body["ready_rows"][0]["capability"] == plugin_id
    assert import_preview_body["ready_rows"][0]["evidence_refs"] == [evidence_ref]
    assert import_preview_body["pending_rows"][0]["error"] == "evidence_refs_input_required"
    assert import_preview_body["invalid_rows"][0]["error"] == "row_not_current_operator_evidence_candidate"
    assert import_preview_body["routes"]["operator_intake_import_preview_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/import-preview"
    )
    assert import_preview_body["routes"]["operator_intake_preview_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/preview"
    )
    assert import_preview_body["routes"]["operator_intake_apply_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/apply"
    )
    apply_group = import_preview_body["apply_payload_groups"][0]
    assert apply_group["pack_id"] == pack_id
    assert apply_group["pack_version"] == pack_version
    assert apply_group["capability_count"] == 1
    assert apply_group["evidence_ref_count"] == 1
    assert apply_group["preview_payload"] == {
        "pack_ids": [pack_id],
        "capability_ids": [plugin_id],
        "evidence_refs": [],
        "evidence_refs_by_capability": {plugin_id: [evidence_ref]},
        "dry_run": True,
        "max_pack_count": 1,
        "max_total_capability_count": 1,
        "max_capability_count_per_pack": 1,
    }
    assert apply_group["apply_payload_hint"]["dry_run_fingerprint_required"] is True
    assert apply_group["apply_payload_hint"]["evidence_refs"] == []
    assert apply_group["apply_payload_hint"]["evidence_refs_by_capability"] == {plugin_id: [evidence_ref]}
    assert apply_group["shared_evidence_ref_count"] == 0
    assert apply_group["capability_specific_evidence_ref_count"] == 1
    assert apply_group["capability_scoped_evidence_refs_supported"] is True
    assert import_preview_body["requirements"]["capability_scoped_evidence_refs_supported"] is True
    assert import_preview_body["requirements"]["does_not_validate_evidence_truth"] is True
    assert import_preview_body["requirements"]["no_synthetic_evidence"] is True
    assert import_preview_body["governance"]["read_only"] is True
    assert import_preview_body["governance"]["preview_only"] is True
    assert import_preview_body["governance"]["write_authority"] is False
    assert import_preview_body["governance"]["writes_registry_metadata"] is False
    assert import_preview_body["governance"]["writes_operator_evidence_metadata"] is False
    assert import_preview_body["governance"]["does_not_approve_proposals"] is True
    assert import_preview_body["governance"]["does_not_promote_capabilities"] is True
    assert import_preview_body["governance"]["memory_write"] is False

    fetched_after_import_preview = client.get(f"/plugins/get?id={plugin_id}").json()["item"]
    assert "proposal_evidence" not in dict(fetched_after_import_preview.get("meta") or {})

    preview = client.post(
        "/plugins/capabilities/library/proposal-evidence/operator-intake/preview",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "preview operator supplied proposal evidence",
            "pack_ids": [pack_id],
            "capability_ids": [plugin_id],
            "evidence_refs": [evidence_ref],
            "dry_run": True,
            "max_pack_count": 1,
            "max_total_capability_count": 1,
            "max_capability_count_per_pack": 1,
        },
    )

    assert preview.status_code == 200
    preview_body = preview.json()
    assert preview_body["ok"] is True
    assert preview_body["applied"] is False
    assert preview_body["kind"] == "plugin.capability_library.operator_proposal_evidence_intake.preview"
    assert preview_body["status"] == "preview"
    assert preview_body["dry_run"] is True
    assert preview_body["planned_pack_count"] == 1
    assert preview_body["planned_capability_count"] == 1
    assert preview_body["evidence_ref_count"] == 1
    assert len(preview_body["dry_run_fingerprint"]) == 64
    assert preview_body["dry_run_confirmation"]["required_for_apply"] is True
    assert preview_body["dry_run_confirmation"]["fingerprint"] == preview_body["dry_run_fingerprint"]
    assert preview_body["dry_run_confirmation"]["preview_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/preview"
    )
    assert preview_body["dry_run_confirmation"]["apply_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/apply"
    )
    assert preview_body["planned"][0]["writes_registry_metadata"] is False
    assert preview_body["planned"][0]["writes_proposals"] is False
    assert preview_body["governance"]["read_only"] is True
    assert preview_body["governance"]["preview_only"] is True
    assert preview_body["governance"]["write_authority"] is False
    assert preview_body["governance"]["writes_registry_metadata"] is False
    assert preview_body["governance"]["writes_operator_evidence_metadata"] is False
    assert preview_body["governance"]["apply_requires_plugins_write_scope"] is True
    assert preview_body["governance"]["dry_run_fingerprint_does_not_authorize_without_plugins_write"] is True
    assert preview_body["governance"]["does_not_promote_capabilities"] is True
    assert preview_body["governance"]["memory_write"] is False

    fetched_after_preview = client.get(f"/plugins/get?id={plugin_id}").json()["item"]
    assert "proposal_evidence" not in dict(fetched_after_preview.get("meta") or {})

    dry_run = client.post(
        "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "dry run operator supplied proposal evidence",
            "pack_ids": [pack_id],
            "capability_ids": [plugin_id],
            "evidence_refs": [evidence_ref],
            "dry_run": True,
            "max_pack_count": 1,
            "max_total_capability_count": 1,
            "max_capability_count_per_pack": 1,
        },
    )

    assert dry_run.status_code == 200
    dry_run_body = dry_run.json()
    assert dry_run_body["ok"] is True
    assert dry_run_body["applied"] is False
    assert dry_run_body["status"] == "dry_run"
    assert dry_run_body["planned_pack_count"] == 1
    assert dry_run_body["planned_capability_count"] == 1
    assert dry_run_body["evidence_ref_count"] == 1
    assert len(dry_run_body["dry_run_fingerprint"]) == 64
    assert dry_run_body["dry_run_fingerprint"] == preview_body["dry_run_fingerprint"]
    assert dry_run_body["dry_run_confirmation"]["required_for_apply"] is True
    assert dry_run_body["dry_run_confirmation"]["fingerprint"] == dry_run_body["dry_run_fingerprint"]
    assert dry_run_body["dry_run_confirmation"]["planned_pack_count"] == 1
    assert dry_run_body["dry_run_confirmation"]["planned_capability_count"] == 1
    assert dry_run_body["dry_run_confirmation"]["evidence_ref_count"] == 1
    assert dry_run_body["dry_run_confirmation"]["apply_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/apply"
    )
    assert dry_run_body["before"]["projection_scope"] == "selected_capabilities"
    assert dry_run_body["before"]["global_counts_included"] is False
    assert dry_run_body["before"]["proposal_evidence_missing_count"] == 1
    assert dry_run_body["planned"][0]["claim_scope"] == (
        "operator_supplied_friction_evidence_reference_not_independent_verification"
    )
    assert dry_run_body["planned"][0]["writes_registry_metadata"] is False
    assert dry_run_body["planned"][0]["writes_proposals"] is False
    assert dry_run_body["planned"][0]["approves_proposals"] is False
    assert dry_run_body["planned"][0]["promotes_capabilities"] is False
    assert dry_run_body["governance"]["writes_registry_metadata"] is False
    assert dry_run_body["governance"]["dry_run_required_before_apply"] is True
    assert dry_run_body["governance"]["operator_supplied_evidence_not_independently_verified"] is True
    assert dry_run_body["governance"]["does_not_approve_proposals"] is True
    assert dry_run_body["governance"]["does_not_promote_capabilities"] is True
    assert dry_run_body["governance"]["memory_write"] is False

    fetched_after_dry_run = client.get(f"/plugins/get?id={plugin_id}").json()["item"]
    assert "proposal_evidence" not in dict(fetched_after_dry_run.get("meta") or {})

    blocked_without_confirmation = client.post(
        "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "apply operator supplied proposal evidence without dry run confirmation",
            "pack_ids": [pack_id],
            "capability_ids": [plugin_id],
            "evidence_refs": [evidence_ref],
            "dry_run": False,
            "max_pack_count": 1,
            "max_total_capability_count": 1,
            "max_capability_count_per_pack": 1,
        },
    )

    assert blocked_without_confirmation.status_code == 200
    blocked_without_confirmation_body = blocked_without_confirmation.json()
    assert blocked_without_confirmation_body["ok"] is False
    assert blocked_without_confirmation_body["applied"] is False
    assert blocked_without_confirmation_body["status"] == "blocked"
    assert blocked_without_confirmation_body["error"] == "operator_evidence_intake_dry_run_confirmation_required"
    assert blocked_without_confirmation_body["planned_pack_count"] == 1
    assert blocked_without_confirmation_body["planned_capability_count"] == 1
    assert blocked_without_confirmation_body["dry_run_confirmation"]["required_for_apply"] is True
    assert blocked_without_confirmation_body["dry_run_confirmation"]["fingerprint_matched"] is False
    assert blocked_without_confirmation_body["governance"]["writes_registry_metadata"] is False
    assert blocked_without_confirmation_body["governance"]["dry_run_required_before_apply"] is True

    fetched_after_blocked_apply = client.get(f"/plugins/get?id={plugin_id}").json()["item"]
    assert "proposal_evidence" not in dict(fetched_after_blocked_apply.get("meta") or {})

    applied = client.post(
        "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "apply operator supplied proposal evidence",
            "pack_ids": [pack_id],
            "capability_ids": [plugin_id],
            "evidence_refs": [evidence_ref],
            "dry_run": False,
            "dry_run_fingerprint": dry_run_body["dry_run_fingerprint"],
            "max_pack_count": 1,
            "max_total_capability_count": 1,
            "max_capability_count_per_pack": 1,
        },
    )

    assert applied.status_code == 200
    applied_body = applied.json()
    assert applied_body["ok"] is True
    assert applied_body["applied"] is True
    assert applied_body["status"] == "recorded"
    assert applied_body["recorded_pack_count"] == 1
    assert applied_body["recorded_capability_count"] == 1
    assert applied_body["dry_run_fingerprint"] == dry_run_body["dry_run_fingerprint"]
    assert applied_body["dry_run_confirmation"]["required_for_apply"] is True
    assert applied_body["dry_run_confirmation"]["fingerprint_matched"] is True
    assert applied_body["remaining_proposal_evidence_missing_count"] == 0
    assert applied_body["remaining_proposal_evidence_ready_count"] == 1
    assert applied_body["governance"]["writes_registry_metadata"] is True
    assert applied_body["governance"]["writes_proposals"] is False
    assert applied_body["governance"]["dry_run_required_before_apply"] is True
    assert applied_body["governance"]["operator_supplied_evidence_not_independently_verified"] is True
    assert applied_body["governance"]["does_not_approve_proposals"] is True
    assert applied_body["governance"]["does_not_promote_capabilities"] is True
    assert applied_body["governance"]["does_not_enable_capabilities"] is True
    assert applied_body["governance"]["memory_write"] is False

    audit = client.get("/plugins/capabilities/library/proposal-evidence/operator-intake/audit")
    assert audit.status_code == 200
    audit_body = audit.json()
    assert audit_body["ok"] is True
    assert audit_body["kind"] == "plugin.capability_library.operator_proposal_evidence_intake.audit"
    assert audit_body["status"] == "operator_evidence_refs_recorded"
    assert audit_body["operator_evidence_intake_audit_ready"] is True
    assert audit_body["recorded_pack_count"] == 1
    assert audit_body["recorded_capability_count"] == 1
    assert audit_body["evidence_ref_count"] == 1
    assert audit_body["future_review_required_count"] == 1
    assert audit_body["source_proposal_evidence_plan"]["proposal_evidence_missing_count"] == 0
    assert audit_body["source_proposal_evidence_plan"]["proposal_evidence_ready_count"] == 1
    assert audit_body["routes"]["operator_intake_checklist_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/checklist"
    )
    assert audit_body["routes"]["operator_intake_audit_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/audit"
    )
    assert audit_body["routes"]["operator_intake_apply_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/apply"
    )
    assert audit_body["requirements"]["audit_only"] is True
    assert audit_body["requirements"]["does_not_validate_evidence_truth"] is True
    assert audit_body["requirements"]["no_synthetic_evidence"] is True
    assert audit_body["governance"]["read_only"] is True
    assert audit_body["governance"]["writes_registry_metadata"] is False
    assert audit_body["governance"]["does_not_approve_proposals"] is True
    assert audit_body["governance"]["does_not_promote_capabilities"] is True
    assert audit_body["governance"]["memory_write"] is False
    audit_pack = audit_body["packs"][0]
    assert audit_pack["pack_id"] == pack_id
    assert audit_pack["recorded_capability_count"] == 1
    assert audit_pack["evidence_ref_count"] == 1
    audit_capability = audit_pack["capabilities"][0]
    assert audit_capability["capability"] == plugin_id
    assert audit_capability["proposal_id"] == proposal_id
    assert audit_capability["evidence_ref_count"] == 1
    assert audit_capability["evidence_refs"] == [evidence_ref]
    assert audit_capability["claim_scope"] == (
        "operator_supplied_friction_evidence_reference_not_independent_verification"
    )
    assert audit_capability["operator_supplied_evidence_not_independently_verified"] is True
    assert audit_capability["requires_future_proposal_review"] is True
    assert audit_capability["operator_intake_route"] == (
        "/plugins/capabilities/library/proposal-evidence/operator-intake/apply"
    )
    assert audit_capability["writes_proposals"] is False
    assert audit_capability["approval_claimed"] is False

    fetched = client.get(f"/plugins/get?id={plugin_id}")
    assert fetched.status_code == 200
    fetched_item = fetched.json()["item"]
    assert fetched_item["status"] == "staged"
    assert fetched_item["enabled"] is False
    stored_meta = dict(fetched_item.get("meta") or {})
    assert stored_meta["proposal_evidence"] == [evidence_ref]
    assert stored_meta["proposal_evidence_link_source"] == (
        "stage17_capability_library_operator_proposal_evidence_intake_apply"
    )
    assert stored_meta["proposal_evidence_claim_scope"] == (
        "operator_supplied_friction_evidence_reference_not_independent_verification"
    )
    assert stored_meta["proposal_evidence_operator_intake_requires_future_review"] is True
    assert stored_meta["proposal_evidence_artifact_proposal_id"] == proposal_id
    assert stored_meta["proposal_evidence_writes_proposals"] is False
    assert stored_meta["proposal_evidence_approval_claimed"] is False

    proposal_state = plugins._plugin_proposal_review_state(proposal_id)
    assert proposal_state["approved"] is False
    assert proposal_state["review_status"] == "staged"


def test_plugins_capability_library_operator_proposal_evidence_intake_batches_capability_scoped_refs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
    client = TestClient(create_app())
    pack_id = "ops.capability_library_operator_proposal_evidence_batch"
    pack_version = "1.0.0"
    labels = [
        "capability_library_operator_proposal_evidence_batch_one",
        "capability_library_operator_proposal_evidence_batch_two",
    ]
    built_items: list[tuple[str, str, str]] = []

    for label in labels:
        meta = {
            **_forge_promotion_meta(label),
            "pack_id": pack_id,
            "pack_version": pack_version,
            "pack_name": "Ops Capability Library Operator Proposal Evidence Batch Pack",
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
                "name": f"Scoped Evidence Batch {len(built_items) + 1}",
                "description": "Stage 17 capability-scoped operator evidence batch coverage",
                "actor": _PLUGIN_ACTOR,
                "meta": meta,
            },
        )
        assert built.status_code == 200
        built_body = built.json()
        assert built_body["ok"] is True
        plugin_id = str(built_body["plugin_id"])
        proposal_id = str(built_body["proposal_id"])
        evidence_ref = f"operator.case.{label}.artifact"
        built_items.append((plugin_id, proposal_id, evidence_ref))

        registry = plugins._load_registry()
        plugin = plugins._read_plugin(registry, plugin_id)
        assert plugin is not None
        plugin_meta = dict(plugin.get("meta") or {})
        plugin_meta.pop("proposal_evidence", None)
        plugin_meta.pop("evidence", None)
        plugin["meta"] = plugin_meta
        plugins._write_plugin(registry, plugins._normalize_plugin_record(plugin_id, plugin))
        plugins._save_registry_and_catalog(registry)

        proposal_path = plugins._plugin_proposal_path(proposal_id)
        proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
        proposal["friction"]["evidence"] = []
        proposal_path.write_text(json.dumps(proposal, indent=2, sort_keys=True), encoding="utf-8")

    capability_ids = [plugin_id for plugin_id, _, _ in built_items]
    proposal_ids = [proposal_id for _, proposal_id, _ in built_items]
    evidence_refs_by_capability = {plugin_id: [evidence_ref] for plugin_id, _, evidence_ref in built_items}

    _approve_capability_pack_operator_review(
        client,
        pack_id=pack_id,
        pack_version=pack_version,
    )

    checklist = client.get("/plugins/capabilities/library/proposal-evidence/operator-intake/checklist")
    assert checklist.status_code == 200
    checklist_body = checklist.json()
    assert checklist_body["ok"] is True
    assert checklist_body["candidate_pack_count"] == 1
    assert checklist_body["candidate_capability_count"] == 2
    assert checklist_body["packs"][0]["pack_id"] == pack_id
    assert checklist_body["packs"][0]["candidate_capability_count"] == 2

    export = client.get("/plugins/capabilities/library/proposal-evidence/operator-intake/export")
    assert export.status_code == 200
    export_body = export.json()
    export_rows = export_body["packs"][0]["rows"]
    export_rows_by_capability = {row["capability"]: row for row in export_rows}
    import_preview = client.post(
        "/plugins/capabilities/library/proposal-evidence/operator-intake/import-preview",
        json={
            "actor": _PLUGIN_ACTOR,
            "rows": [
                {**export_rows_by_capability[plugin_id], "evidence_refs_input": evidence_ref}
                for plugin_id, _, evidence_ref in built_items
            ],
            "max_row_count": 10,
            "max_apply_group_count": 10,
        },
    )
    assert import_preview.status_code == 200
    import_preview_body = import_preview.json()
    assert import_preview_body["ok"] is True
    assert import_preview_body["status"] == "ready_for_operator_evidence_import_preview"
    assert import_preview_body["ready_row_count"] == 2
    assert import_preview_body["pending_row_count"] == 0
    assert import_preview_body["invalid_row_count"] == 0
    assert import_preview_body["apply_group_count"] == 1
    apply_group = import_preview_body["apply_payload_groups"][0]
    assert apply_group["pack_id"] == pack_id
    assert apply_group["capability_count"] == 2
    assert apply_group["evidence_ref_count"] == 2
    assert apply_group["shared_evidence_ref_count"] == 0
    assert apply_group["capability_specific_evidence_ref_count"] == 2
    assert apply_group["capability_scoped_evidence_refs_supported"] is True
    assert apply_group["preview_payload"]["evidence_refs"] == []
    assert apply_group["preview_payload"]["evidence_refs_by_capability"] == evidence_refs_by_capability

    evidence_payload = {
        "actor": _PLUGIN_ACTOR,
        "reason": "dry run capability-scoped operator proposal evidence batch",
        **apply_group["preview_payload"],
    }
    dry_run = client.post(
        "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
        json=evidence_payload,
    )

    assert dry_run.status_code == 200
    dry_run_body = dry_run.json()
    assert dry_run_body["ok"] is True
    assert dry_run_body["applied"] is False
    assert dry_run_body["status"] == "dry_run"
    assert dry_run_body["planned_pack_count"] == 1
    assert dry_run_body["planned_capability_count"] == 2
    assert dry_run_body["evidence_ref_count"] == 2
    assert dry_run_body["shared_evidence_ref_count"] == 0
    assert dry_run_body["capability_specific_evidence_ref_count"] == 2
    assert dry_run_body["before"]["projection_scope"] == "selected_capabilities"
    assert dry_run_body["before"]["global_counts_included"] is False
    assert dry_run_body["projection_generated_at"] == dry_run_body["before"]["generated_at"]
    assert dry_run_body["projection_evidence"] == dry_run_body["before"]["projection_evidence"]
    _assert_stage17_projection_readback(
        dry_run_body["before"],
        projection_scope="selected_capabilities",
        global_counts_included=False,
        selected_capability_ids=capability_ids,
    )
    assert dry_run_body["dry_run_confirmation"]["required_for_apply"] is True
    assert dry_run_body["governance"]["capability_scoped_evidence_refs_supported"] is True
    assert dry_run_body["governance"]["writes_registry_metadata"] is False
    planned_pack = dry_run_body["planned"][0]
    assert planned_pack["pack_id"] == pack_id
    assert planned_pack["evidence_ref_count"] == 2
    planned_by_capability = {item["capability"]: item for item in planned_pack["capabilities"]}
    assert set(planned_by_capability) == set(capability_ids)
    assert all(item["evidence_ref_count"] == 1 for item in planned_by_capability.values())

    evidence_payload["dry_run"] = False
    evidence_payload["dry_run_fingerprint"] = dry_run_body["dry_run_fingerprint"]
    applied = client.post(
        "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
        json=evidence_payload,
    )

    assert applied.status_code == 200
    applied_body = applied.json()
    assert applied_body["ok"] is True
    assert applied_body["applied"] is True
    assert applied_body["status"] == "recorded"
    assert applied_body["recorded_pack_count"] == 1
    assert applied_body["recorded_capability_count"] == 2
    assert applied_body["evidence_ref_count"] == 2
    assert applied_body["shared_evidence_ref_count"] == 0
    assert applied_body["capability_specific_evidence_ref_count"] == 2
    assert applied_body["remaining_proposal_evidence_missing_count"] == 0
    assert applied_body["remaining_proposal_evidence_ready_count"] == 2
    assert applied_body["before_projection_generated_at"]
    assert applied_body["after_projection_generated_at"]
    assert applied_body["projection_evidence"]["projection_scope"] == "selected_capabilities"
    assert applied_body["projection_evidence"]["global_counts_included"] is False
    assert applied_body["projection_evidence"]["selected_capability_ids"] == sorted(capability_ids)
    assert applied_body["projection_evidence"]["read_only_projection"] is True
    assert applied_body["projection_evidence"]["writes_data"] is False
    assert applied_body["dry_run_confirmation"]["fingerprint_matched"] is True
    assert applied_body["governance"]["writes_registry_metadata"] is True
    assert applied_body["governance"]["writes_proposals"] is False
    assert applied_body["governance"]["does_not_approve_proposals"] is True
    assert applied_body["governance"]["does_not_promote_capabilities"] is True
    assert applied_body["governance"]["does_not_enable_capabilities"] is True
    assert applied_body["governance"]["memory_write"] is False

    for plugin_id, proposal_id, evidence_ref in built_items:
        fetched = client.get(f"/plugins/get?id={plugin_id}")
        assert fetched.status_code == 200
        item = fetched.json()["item"]
        assert item["status"] == "staged"
        assert item["enabled"] is False
        meta = dict(item.get("meta") or {})
        assert meta["proposal_evidence"] == [evidence_ref]
        assert meta["proposal_evidence_artifact_proposal_id"] == proposal_id
        assert meta["proposal_evidence_writes_proposals"] is False
        assert meta["proposal_evidence_approval_claimed"] is False

    review_dry_run = client.post(
        "/plugins/capabilities/library/proposal-review/apply",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "dry run batched proposal review after capability-scoped evidence",
            "pack_ids": [pack_id],
            "capability_ids": capability_ids,
            "max_pack_count": 1,
            "max_total_capability_count": 2,
            "max_capability_count_per_pack": 2,
            "dry_run": True,
        },
    )

    assert review_dry_run.status_code == 200
    review_dry_run_body = review_dry_run.json()
    assert review_dry_run_body["ok"] is True
    assert review_dry_run_body["applied"] is False
    assert review_dry_run_body["status"] == "dry_run"
    assert review_dry_run_body["planned_pack_count"] == 1
    assert review_dry_run_body["planned_capability_count"] == 2
    assert review_dry_run_body["planned_proposal_count"] == 2
    assert review_dry_run_body["before"]["projection_scope"] == "selected_capabilities"
    assert review_dry_run_body["before"]["global_counts_included"] is False
    assert review_dry_run_body["projection_generated_at"] == review_dry_run_body["before"]["generated_at"]
    assert review_dry_run_body["projection_evidence"] == review_dry_run_body["before"]["projection_evidence"]
    _assert_stage17_projection_readback(
        review_dry_run_body["before"],
        projection_scope="selected_capabilities",
        global_counts_included=False,
        selected_capability_ids=capability_ids,
    )
    assert review_dry_run_body["governance"]["writes_proposal_review_receipts"] is False
    assert review_dry_run_body["governance"]["approves_proposals"] is False
    assert review_dry_run_body["governance"]["proposal_review_authority"] is False

    review_applied = client.post(
        "/plugins/capabilities/library/proposal-review/apply",
        json={
            "actor": _PLUGIN_ACTOR,
            "reason": "apply batched proposal review after capability-scoped evidence",
            "pack_ids": [pack_id],
            "capability_ids": capability_ids,
            "max_pack_count": 1,
            "max_total_capability_count": 2,
            "max_capability_count_per_pack": 2,
            "dry_run": False,
            "dry_run_fingerprint": review_dry_run_body["dry_run_fingerprint"],
        },
    )

    assert review_applied.status_code == 200
    review_applied_body = review_applied.json()
    assert review_applied_body["ok"] is True
    assert review_applied_body["applied"] is True
    assert review_applied_body["status"] == "reviewed"
    assert review_applied_body["recorded_proposal_count"] == 2
    assert review_applied_body["recorded_capability_count"] == 2
    assert review_applied_body["remaining_proposal_review_missing_count"] == 0
    assert review_applied_body["remaining_reviewable_capability_count"] == 0
    assert review_applied_body["promotable_capability_count"] == 2
    assert review_applied_body["before_projection_generated_at"]
    assert review_applied_body["after_projection_generated_at"]
    assert review_applied_body["projection_evidence"]["projection_scope"] == "selected_capabilities"
    assert review_applied_body["projection_evidence"]["global_counts_included"] is False
    assert review_applied_body["projection_evidence"]["selected_capability_ids"] == sorted(capability_ids)
    assert review_applied_body["projection_evidence"]["read_only_projection"] is True
    assert review_applied_body["projection_evidence"]["writes_data"] is False
    assert review_applied_body["dry_run_confirmation"]["fingerprint_matched"] is True
    assert review_applied_body["governance"]["writes_proposal_review_receipts"] is True
    assert review_applied_body["governance"]["updates_proposal_records"] is True
    assert review_applied_body["governance"]["approves_proposals"] is True
    assert review_applied_body["governance"]["does_not_promote_capabilities"] is True
    assert review_applied_body["governance"]["does_not_enable_capabilities"] is True
    assert review_applied_body["governance"]["promotion_authority"] is False

    recorded_by_proposal = {item["proposal_id"]: item for item in review_applied_body["recorded"]}
    assert set(recorded_by_proposal) == set(proposal_ids)
    for proposal_id in proposal_ids:
        receipt_path = Path(recorded_by_proposal[proposal_id]["receipt_path"])
        assert receipt_path.exists()
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert receipt["kind"] == "plugin.proposal.review.receipt"
        assert receipt["proposal_id"] == proposal_id
        assert receipt["status"] == "approved"
        proposal_state = plugins._plugin_proposal_review_state(proposal_id)
        assert proposal_state["approved"] is True
        assert proposal_state["review_status"] == "approved"

    for plugin_id in capability_ids:
        fetched = client.get(f"/plugins/get?id={plugin_id}")
        assert fetched.status_code == 200
        item = fetched.json()["item"]
        assert item["status"] == "staged"
        assert item["enabled"] is False


def test_plugins_capability_pack_metadata_receipt_expands_reviewed_migration_plan_candidate(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import plugins

    _isolate_generated_plugin_root(monkeypatch, plugins, tmp_path)
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
