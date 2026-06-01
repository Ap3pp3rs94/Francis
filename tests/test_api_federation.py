from __future__ import annotations

import json
from pathlib import Path


def _write_stage15_closure_receipt(
    data_root: Path,
    *,
    receipt_id: str = "swarm_stage15_closure_test",
) -> None:
    path = data_root / "logs" / "swarm" / "stage15_operator_stage_closure_decisions.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "ok": True,
                "kind": "francis.stage15.swarm.stage15_closure_decision_receipt",
                "receipt_id": receipt_id,
                "stage": "Stage 15 / Swarm",
                "source_id": "swarm",
                "target": "stage15_swarm",
                "actor": "test.operator",
                "decision": "close_stage15",
                "authority": "delegated_operator",
                "delegation_id": "opdel_test_stage15",
                "completion_review_ready": True,
                "stage15_completion_review_ready": True,
                "stage15_closed_by_receipt": True,
                "ready_count": 6,
                "required_count": 6,
                "blockers": [],
                "marks_runtime_stage_state": False,
                "recorded_ts": 1_800_004_000,
                "governance": {
                    "explicit_operator_decision": True,
                    "stage_closure_decision": True,
                    "completion_review_ready": True,
                    "does_not_mutate_runtime_stage_state": True,
                    "grants_execution_authority": False,
                    "grants_mutation_authority": False,
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_federation_hub_contract_lifecycle(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    health = client.get("/federation/status")
    assert health.status_code == 200
    health_body = health.json()
    assert health_body["ok"] is True
    assert health_body["route"] == "federation"

    first = client.post(
        "/federation/instances/upsert",
        json={
            "id": "node-alpha",
            "name": "Alpha Node",
            "status": "online",
            "endpoint": "https://alpha.example.net",
            "region": "us-east",
            "role": "coordinator",
            "capabilities": ["api", "workers", "web_learning"],
            "tags": ["prod", "us"],
            "trust_level": 8,
            "requires_approval": True,
            "health": {"cpu": 0.22, "latency_ms": 14},
            "inventory": {"plugins": 12, "workers": 4},
            "meta": {"owner": "ops"},
        },
    )
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["ok"] is True
    assert first_body["id"] == "node-alpha"

    second = client.post(
        "/federation/instances/upsert",
        json={
            "id": "node-beta",
            "name": "Beta Node",
            "status": "degraded",
            "endpoint": "https://beta.example.net",
            "region": "eu-west",
            "capabilities": ["api"],
            "tags": ["staging", "eu"],
        },
    )
    assert second.status_code == 200
    assert second.json()["ok"] is True

    list_online = client.get("/federation/instances/list?status=online")
    assert list_online.status_code == 200
    online_items = list_online.json()["items"]
    assert any(str(item.get("id")) == "node-alpha" for item in online_items)
    assert all(str(item.get("status", "")).lower() == "online" for item in online_items)

    list_tags = client.get("/federation/instances/list?tags=prod,us")
    assert list_tags.status_code == 200
    list_tags_body = list_tags.json()
    assert any(str(item.get("id")) == "node-alpha" for item in list_tags_body["items"])
    assert all(str(item.get("id")) != "node-beta" for item in list_tags_body["items"])

    fetched = client.get("/federation/instances/get?id=node-alpha")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["item"]["id"] == "node-alpha"
    assert fetched_body["health"]["latency_ms"] == 14
    assert fetched_body["inventory"]["workers"] == 4

    delegation = client.post(
        "/federation/delegations/record",
        json={
            "from": "node-alpha",
            "to": "node-beta",
            "scope": "ops.deploy",
            "status": "active",
            "reason": "rollout",
        },
    )
    assert delegation.status_code == 200
    delegation_body = delegation.json()
    assert delegation_body["ok"] is True
    delegation_id = str(delegation_body["id"])

    delegations = client.get("/federation/delegations/list?status=active")
    assert delegations.status_code == 200
    delegations_body = delegations.json()
    assert any(str(item.get("id")) == delegation_id for item in delegations_body["items"])

    log = client.post(
        "/federation/consensus_logs/append",
        json={
            "level": "warning",
            "kind": "split_vote",
            "instance_id": "node-alpha",
            "message": "Split vote observed",
            "term": 12,
            "index": 418,
        },
    )
    assert log.status_code == 200
    log_body = log.json()
    assert log_body["ok"] is True
    log_id = str(log_body["id"])

    logs = client.get("/federation/consensus_logs/list?level=warning&instance_id=node-alpha")
    assert logs.status_code == 200
    logs_body = logs.json()
    assert any(str(item.get("id")) == log_id for item in logs_body["items"])

    knowledge = client.post(
        "/federation/shared_knowledge/publish",
        json={
            "kind": "policy",
            "title": "Incident Escalation Policy",
            "source_instance_id": "node-alpha",
            "domain": "operations",
            "tags": ["runbook", "incident"],
        },
    )
    assert knowledge.status_code == 200
    knowledge_body = knowledge.json()
    assert knowledge_body["ok"] is True
    knowledge_id = str(knowledge_body["id"])

    listed_knowledge = client.get("/federation/shared_knowledge/list?kind=policy&domain=operations&tags=incident")
    assert listed_knowledge.status_code == 200
    listed_knowledge_body = listed_knowledge.json()
    assert any(str(item.get("id")) == knowledge_id for item in listed_knowledge_body["items"])

    final_status = client.get("/federation/status")
    assert final_status.status_code == 200
    final_counts = final_status.json()["counts"]
    assert final_counts["instances"] >= 2
    assert final_counts["delegations"] >= 1
    assert final_counts["consensus_logs"] >= 1
    assert final_counts["shared_knowledge"] >= 1


def test_federation_write_denies_unscoped_actor_before_persisting(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    denied = client.post(
        "/federation/instances/upsert",
        json={
            "request_actor": "unscoped.federation.writer",
            "id": "node-denied",
            "status": "online",
        },
    )

    assert denied.status_code == 200
    body = denied.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["governance"]["gate"] == "permission_gate"
    assert body["governance"]["reason"] == "missing_scopes"
    assert body["governance"]["next_step"] == "configure_actor_scope_before_writing_federation"
    assert body["governance"]["evidence"]["actor_present"] is True
    assert body["governance"]["evidence"]["required_scope_count"] == 1
    assert not (data_root / "federation" / "_registry.json").exists()


def test_federation_pagination_time_filters_and_persistence(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    client.post("/federation/instances/upsert", json={"id": "node-a", "status": "online", "tags": ["alpha"]})
    client.post("/federation/instances/upsert", json={"id": "node-b", "status": "offline", "tags": ["beta"]})
    client.post("/federation/instances/upsert", json={"id": "node-c", "status": "joining", "tags": ["alpha", "beta"]})

    page = client.get("/federation/instances/list?limit=2&offset=0")
    assert page.status_code == 200
    page_body = page.json()
    assert page_body["limit"] == 2
    assert page_body["offset"] == 0
    assert page_body["total"] >= 3
    assert len(page_body["items"]) == 2

    for idx, level in enumerate(["info", "warning", "error"], start=1):
        client.post(
            "/federation/consensus_logs/append",
            json={
                "id": f"log-{idx}",
                "ts": 1_700_000_000 + idx,
                "level": level,
                "instance_id": "node-a",
                "message": f"log {idx}",
            },
        )

    logs_window = client.get("/federation/consensus_logs/list?start_ts=1700000001&end_ts=1700000002")
    assert logs_window.status_code == 200
    logs_window_body = logs_window.json()
    ids = {str(item.get("id")) for item in logs_window_body["items"]}
    assert "log-1" in ids
    assert "log-2" in ids
    assert "log-3" not in ids

    client.post(
        "/federation/shared_knowledge/publish",
        json={"id": "k-1", "kind": "schema", "title": "API Schema", "domain": "platform", "tags": ["api", "schema"]},
    )
    client.post(
        "/federation/shared_knowledge/publish",
        json={"id": "k-2", "kind": "fact", "title": "Ops Fact", "domain": "operations", "tags": ["ops"]},
    )

    knowledge = client.get("/federation/shared_knowledge/list?tags=api")
    assert knowledge.status_code == 200
    knowledge_ids = {str(item.get("id")) for item in knowledge.json()["items"]}
    assert "k-1" in knowledge_ids
    assert "k-2" not in knowledge_ids

    registry_path = data_root / "federation" / "_registry.json"
    assert registry_path.exists()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert isinstance(registry.get("instances"), dict)
    assert isinstance(registry.get("delegations"), list)
    assert isinstance(registry.get("consensus_logs"), list)
    assert isinstance(registry.get("shared_knowledge"), list)


def test_federation_stage16_pairing_scoped_trust_contract_is_read_only_after_stage15_closure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage15_closure_receipt(data_root, receipt_id="swarm_stage15_closure_for_stage16")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    response = client.get("/federation/pairing-scoped-trust-contract")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage16.federation.pairing_scoped_trust_contract"
    assert body["stage"] == "Stage 16 / Federation"
    assert body["status"] == "ready"
    assert body["stage15_closed_by_receipt"] is True
    assert body["stage15_latest_closure_receipt_id"] == "swarm_stage15_closure_for_stage16"
    assert body["pairing_scoped_trust_contract_ready"] is True
    assert body["pairing_states"] == [
        "unpaired",
        "pairing_requested",
        "paired",
        "degraded",
        "revoked",
    ]
    assert body["required_pairing_fields"] == [
        "pairing_request_id",
        "local_node_id",
        "remote_node_id",
        "remote_public_key_fingerprint",
        "requested_scopes",
        "operator_approval_receipt_id",
        "expiry_policy",
        "revocation_route",
    ]
    assert {level["id"] for level in body["scoped_trust_levels"]} == {
        "presence",
        "continuity_summary",
        "approval_relay",
    }
    assert "raw_private_data" in body["selective_replication"]["blocked_classes"]
    assert "secrets" in body["selective_replication"]["blocked_classes"]
    assert body["invariants"]["pairing_is_explicit_not_ambient"] is True
    assert body["invariants"]["trust_is_scoped_not_global"] is True
    assert body["invariants"]["federation_does_not_expand_authority"] is True
    assert body["governance"]["read_only"] is True
    assert body["governance"]["zero_trust_default"] is True
    assert body["governance"]["raw_private_data_replication_allowed"] is False
    assert body["governance"]["hidden_trust_expansion_allowed"] is False
    assert body["writes_registry"] is False
    assert body["writes_memory"] is False
    assert body["runs_tools"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["next_smallest_truthful_gap"] == "stage16_sync_model_contract"

    status = client.get("/federation/status").json()
    assert status["stage"] == "Stage 16 / Federation"
    assert status["stage16_status"] == "stage16_contracts_ready_completion_blocked"
    assert status["pairing_scoped_trust_contract_ready"] is True
    assert status["sync_model_contract_ready"] is True
    assert status["remote_approval_contract_ready"] is True
    assert status["revocation_contract_ready"] is True
    assert status["node_attributed_continuity_contract_ready"] is True
    assert status["ready_count"] == 6
    assert status["required_count"] == 6
    assert status["routes"]["pairing_scoped_trust_contract"] == "/federation/pairing-scoped-trust-contract"
    assert status["routes"]["sync_model_contract"] == "/federation/sync-model-contract"
    assert status["routes"]["remote_approval_contract"] == "/federation/remote-approval-contract"
    assert status["routes"]["revocation_contract"] == "/federation/revocation-contract"
    assert status["routes"]["node_attributed_continuity_contract"] == "/federation/node-attributed-continuity-contract"
    assert status["stage16_completion_review_ready"] is False
    assert status["live_runtime_readback_ready"] is False
    assert "live_pairing_flow_observed" in status["completion_review_blockers"]
    assert status["next_smallest_truthful_gap"] == "stage16_live_federation_runtime_readback"


def test_federation_stage16_sync_model_contract_blocks_over_replication_and_stale_authority(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage15_closure_receipt(data_root, receipt_id="swarm_stage15_closure_for_sync")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    response = client.get("/federation/sync-model-contract")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage16.federation.sync_model_contract"
    assert body["stage"] == "Stage 16 / Federation"
    assert body["status"] == "ready"
    assert body["stage15_closed_by_receipt"] is True
    assert body["stage15_latest_closure_receipt_id"] == "swarm_stage15_closure_for_sync"
    assert body["pairing_scoped_trust_contract_ready"] is True
    assert body["sync_model_contract_ready"] is True
    assert [lane["id"] for lane in body["sync_lanes"]] == [
        "presence",
        "continuity_summary",
        "approval_relay_metadata",
        "shared_knowledge_index",
    ]
    assert all(lane["requires_encryption"] is True for lane in body["sync_lanes"])
    assert all(lane["requires_node_scope"] is True for lane in body["sync_lanes"])
    assert body["replication_rules"]["allowlist_only"] is True
    assert body["replication_rules"]["per_node_scope_required"] is True
    assert body["replication_rules"]["raw_private_data_replication_allowed"] is False
    assert body["replication_rules"]["raw_memory_body_replication_allowed"] is False
    assert body["replication_rules"]["credential_material_replication_allowed"] is False
    assert body["replication_rules"]["execution_token_replication_allowed"] is False
    assert body["replication_rules"]["ambient_cloud_sync_allowed"] is False
    assert body["conflict_policy"]["silent_overwrite_allowed"] is False
    assert body["conflict_policy"]["authority_or_approval_conflict_requires_operator_review"] is True
    assert body["conflict_policy"]["deadletter_unmergeable_conflicts"] is True
    assert body["staleness_policy"]["stale_badge_required"] is True
    assert body["staleness_policy"]["stale_state_cannot_imply_current_authority"] is True
    assert body["invariants"]["sync_is_selective_not_sync_everything"] is True
    assert body["invariants"]["raw_private_data_is_blocked"] is True
    assert body["invariants"]["raw_memory_body_is_blocked"] is True
    assert body["sync_execution_enabled"] is False
    assert body["writes_registry"] is False
    assert body["writes_memory"] is False
    assert body["runs_tools"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["next_smallest_truthful_gap"] == "stage16_remote_approval_support"


def test_federation_stage16_remote_approval_contract_is_receipt_referenced_and_non_executing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage15_closure_receipt(data_root, receipt_id="swarm_stage15_closure_for_remote_approval")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    response = client.get("/federation/remote-approval-contract")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage16.federation.remote_approval_contract"
    assert body["stage"] == "Stage 16 / Federation"
    assert body["status"] == "ready"
    assert body["stage15_closed_by_receipt"] is True
    assert body["stage15_latest_closure_receipt_id"] == "swarm_stage15_closure_for_remote_approval"
    assert body["pairing_scoped_trust_contract_ready"] is True
    assert body["sync_model_contract_ready"] is True
    assert body["remote_approval_contract_ready"] is True
    assert body["request_envelope_fields"] == [
        "remote_approval_request_id",
        "source_node_id",
        "paired_node_id",
        "target_operator_id",
        "requested_action",
        "requested_scope",
        "trace_id",
        "parent_receipt_id",
        "sync_lane_id",
        "recorded_ts",
        "expires_at",
    ]
    assert body["decision_receipt_fields"] == [
        "decision_receipt_id",
        "remote_approval_request_id",
        "decision",
        "decision_actor",
        "decision_authority",
        "decision_recorded_ts",
        "source_node_id",
        "paired_node_id",
        "trace_id",
        "parent_receipt_id",
    ]
    assert body["relay_states"] == [
        "queued",
        "delivered",
        "decided",
        "denied",
        "expired",
        "deadlettered",
    ]
    assert "approval_request_metadata" in body["allowed_request_classes"]
    assert "decision_receipt_reference" in body["allowed_request_classes"]
    assert "remote_operator_impersonation" in body["blocked_request_classes"]
    assert "raw_private_payload" in body["blocked_request_classes"]
    assert body["safety_rules"]["operator_decision_receipt_required"] is True
    assert body["safety_rules"]["remote_node_cannot_impersonate_operator"] is True
    assert body["safety_rules"]["remote_node_cannot_expand_scope"] is True
    assert body["safety_rules"]["stale_request_must_expire"] is True
    assert body["governance_flags"]["remote_approval_execution_enabled"] is False
    assert body["governance_flags"]["request_metadata_only"] is True
    assert body["governance_flags"]["decision_receipt_reference_only"] is True
    assert body["governance_flags"]["silent_approval_allowed"] is False
    assert body["remote_approval_execution_enabled"] is False
    assert body["writes_registry"] is False
    assert body["writes_memory"] is False
    assert body["runs_tools"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["next_smallest_truthful_gap"] == "stage16_revocation_surfaces"

    status = client.get("/federation/status").json()
    assert status["stage16_status"] == "stage16_contracts_ready_completion_blocked"
    assert status["remote_approval_contract_ready"] is True
    assert status["revocation_contract_ready"] is True
    assert status["node_attributed_continuity_contract_ready"] is True
    assert status["ready_count"] == 6
    assert status["required_count"] == 6
    assert status["stage16_completion_review_ready"] is False
    assert status["live_runtime_readback_ready"] is False
    assert status["next_smallest_truthful_gap"] == "stage16_live_federation_runtime_readback"


def test_federation_stage16_revocation_contract_is_scoped_and_propagation_bounded(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage15_closure_receipt(data_root, receipt_id="swarm_stage15_closure_for_revocation")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    response = client.get("/federation/revocation-contract")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage16.federation.revocation_contract"
    assert body["status"] == "ready"
    assert body["stage15_latest_closure_receipt_id"] == "swarm_stage15_closure_for_revocation"
    assert body["remote_approval_contract_ready"] is True
    assert body["revocation_contract_ready"] is True
    assert body["revocation_request_fields"] == [
        "revocation_id",
        "pairing_request_id",
        "source_node_id",
        "paired_node_id",
        "revoked_scope",
        "reason",
        "trace_id",
        "operator_receipt_id",
        "recorded_ts",
        "effective_ts",
    ]
    assert body["revocation_states"] == [
        "requested",
        "propagating",
        "revoked",
        "denied",
        "deadlettered",
    ]
    assert body["propagation_rules"]["operator_receipt_required"] is True
    assert body["propagation_rules"]["per_node_scope_required"] is True
    assert body["propagation_rules"]["revocation_before_reuse_required"] is True
    assert body["propagation_rules"]["stale_pairing_reuse_blocked"] is True
    assert body["propagation_rules"]["remote_approval_relays_must_stop_after_revocation"] is True
    assert body["propagation_rules"]["sync_lanes_must_stop_after_revocation"] is True
    assert body["propagation_rules"]["subdelegation_allowed"] is False
    assert body["propagation_rules"]["silent_reactivation_allowed"] is False
    assert body["propagation_rules"]["authority_expansion_allowed"] is False
    assert body["denial_behavior"]["unknown_pairing"] == "deadletter_unknown_pairing"
    assert body["revocation_execution_enabled"] is False
    assert body["writes_registry"] is False
    assert body["writes_memory"] is False
    assert body["runs_tools"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["next_smallest_truthful_gap"] == "stage16_node_attributed_continuity"


def test_federation_stage16_node_attributed_continuity_contract_preserves_trace_and_freshness(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage15_closure_receipt(data_root, receipt_id="swarm_stage15_closure_for_node_continuity")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    response = client.get("/federation/node-attributed-continuity-contract")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage16.federation.node_attributed_continuity_contract"
    assert body["status"] == "ready"
    assert body["stage15_latest_closure_receipt_id"] == "swarm_stage15_closure_for_node_continuity"
    assert body["revocation_contract_ready"] is True
    assert body["node_attributed_continuity_contract_ready"] is True
    assert body["continuity_record_fields"] == [
        "continuity_record_id",
        "source_node_id",
        "source_node_role",
        "paired_node_id",
        "sync_lane_id",
        "trace_id",
        "parent_receipt_id",
        "source_recorded_ts",
        "received_ts",
        "freshness_state",
        "redaction_summary",
        "authority_snapshot_id",
    ]
    assert body["freshness_states"] == [
        "fresh",
        "stale",
        "revoked",
        "conflicted",
        "deadlettered",
    ]
    assert body["continuity_rules"]["source_node_id_required"] is True
    assert body["continuity_rules"]["trace_id_required"] is True
    assert body["continuity_rules"]["freshness_badge_required"] is True
    assert body["continuity_rules"]["redaction_summary_required"] is True
    assert body["continuity_rules"]["revoked_links_cannot_present_current_state"] is True
    assert body["continuity_rules"]["stale_state_cannot_imply_current_authority"] is True
    assert body["continuity_rules"]["raw_private_data_allowed"] is False
    assert body["continuity_rules"]["node_ambiguous_receipts_allowed"] is False
    assert body["handback_policy"]["operator_visible_node_source"] is True
    assert body["handback_policy"]["operator_visible_freshness"] is True
    assert body["handback_policy"]["operator_visible_trace"] is True
    assert body["handback_policy"]["operator_visible_redaction"] is True
    assert body["handback_policy"]["hidden_federation_source_allowed"] is False
    assert body["continuity_sync_execution_enabled"] is False
    assert body["writes_registry"] is False
    assert body["writes_memory"] is False
    assert body["runs_tools"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["next_smallest_truthful_gap"] == "stage16_completion_review"

    status = client.get("/federation/status").json()
    assert status["stage16_status"] == "stage16_contracts_ready_completion_blocked"
    assert status["ready_count"] == 6
    assert status["required_count"] == 6
    assert status["stage16_completion_review_ready"] is False
    assert status["live_runtime_readback_ready"] is False
    assert status["next_smallest_truthful_gap"] == "stage16_live_federation_runtime_readback"


def test_federation_stage16_completion_review_blocks_closure_until_live_runtime_readbacks(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage15_closure_receipt(data_root, receipt_id="swarm_stage15_closure_for_completion_review")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    response = client.get("/federation/completion-review")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage16.federation.completion_review"
    assert body["stage"] == "Stage 16 / Federation"
    assert body["status"] == "blocked"
    assert body["stage15_closed_by_receipt"] is True
    assert body["stage15_latest_closure_receipt_id"] == "swarm_stage15_closure_for_completion_review"
    assert body["contract_readiness_ready"] is True
    assert body["live_runtime_readback_ready"] is False
    assert body["stage16_completion_review_ready"] is False
    assert body["ready_to_close"] is False
    assert body["stage_closure_decision_required"] is False
    assert body["ready_count"] == 6
    assert body["required_count"] == 6
    assert body["live_ready_count"] == 0
    assert body["live_required_count"] == 5
    assert {item["id"] for item in body["contract_checks"] if item["passed"]} == {
        "stage15_ledger_closure_backstop",
        "pairing_scoped_trust_contract_ready",
        "sync_model_contract_ready",
        "remote_approval_contract_ready",
        "revocation_contract_ready",
        "node_attributed_continuity_contract_ready",
    }
    assert body["blockers"] == [
        "live_pairing_flow_observed",
        "live_selective_sync_observed",
        "live_remote_approval_roundtrip_observed",
        "live_revocation_roundtrip_observed",
        "workstation_sleep_continuity_validated",
    ]
    assert body["done_criteria"]["workstation_sleep_does_not_destroy_continuity"] is False
    assert body["done_criteria"]["remote_approval_is_safe_and_traceable"] is False
    assert body["done_criteria"]["raw_private_data_does_not_leak_across_nodes"] is True
    assert body["done_criteria"]["multi_device_francis_feels_like_one_governed_system"] is False
    assert body["governance"]["completion_review_only"] is True
    assert body["governance"]["requires_live_runtime_readback"] is True
    assert body["writes_registry"] is False
    assert body["writes_memory"] is False
    assert body["runs_tools"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["next_smallest_truthful_gap"] == "stage16_live_federation_runtime_readback"
