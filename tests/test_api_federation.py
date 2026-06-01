from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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


def _record_stage16_live_readback(client: Any, readback_id: str, *, proof_kind: str = "live_runtime_probe") -> None:
    response = client.post(
        "/federation/live-runtime-readback",
        json={
            "request_actor": "test.federation.write",
            "reason": f"record {readback_id}",
            "readback_id": readback_id,
            "observed": True,
            "proof_kind": proof_kind,
            "source_node_id": "workstation-a",
            "paired_node_id": "phone-a",
            "trace_id": f"trace-fed-{readback_id}",
            "parent_receipt_id": "swarm_stage15_closure_for_runbook",
            "evidence_summary": f"bounded live runtime proof for {readback_id}",
        },
    )
    assert response.status_code == 200
    assert response.json()["readback_ready"] is True


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


def test_federation_stage16_closure_decision_denies_without_closure_scope(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({"test.federation.write": ["federation.write"]}),
    )

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.post(
        "/federation/stage-closure-decision",
        json={
            "actor": "test.federation.write",
            "reason": "attempt stage16 closure without closure scope",
            "decision": "close_stage16",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["required_scope"] == "federation.stage16.closure.write"
    assert body["governance"]["reason"] == "missing_scopes"
    assert (
        body["governance"]["next_step"]
        == "configure_stage16_closure_write_scope_before_operator_stage_closure_decision"
    )
    assert not (data_root / "logs" / "federation" / "stage16_operator_stage_closure_decisions.jsonl").exists()


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


def test_federation_stage16_live_runtime_readback_is_permissioned_and_completion_consumes_receipts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage15_closure_receipt(data_root, receipt_id="swarm_stage15_closure_for_live_readbacks")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    denied = client.post(
        "/federation/live-runtime-readback",
        json={
            "request_actor": "unscoped.federation.writer",
            "readback_id": "live_pairing_flow_observed",
            "observed": True,
            "source_node_id": "workstation-a",
            "paired_node_id": "phone-a",
            "trace_id": "trace-fed-denied",
            "evidence_summary": "denied receipt should not persist",
        },
    )
    assert denied.status_code == 200
    denied_body = denied.json()
    assert denied_body["ok"] is False
    assert denied_body["status"] == "denied"
    assert denied_body["error"] == "api_permission_denied"
    assert not (data_root / "logs" / "federation" / "stage16_live_runtime_readbacks.jsonl").exists()

    readback_ids = [
        "live_pairing_flow_observed",
        "live_selective_sync_observed",
        "live_remote_approval_roundtrip_observed",
        "live_revocation_roundtrip_observed",
        "workstation_sleep_continuity_validated",
    ]
    receipt_ids: list[str] = []
    for index, readback_id in enumerate(readback_ids, start=1):
        response = client.post(
            "/federation/live-runtime-readback",
            json={
                "request_actor": "test.federation.write",
                "reason": f"record {readback_id}",
                "readback_id": readback_id,
                "observed": True,
                "proof_kind": "scripted_local_runtime_probe",
                "source_node_id": "workstation-a",
                "paired_node_id": "phone-a",
                "trace_id": f"trace-fed-live-{index}",
                "parent_receipt_id": "swarm_stage15_closure_for_live_readbacks",
                "evidence_summary": f"bounded live runtime proof for {readback_id}",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["kind"] == "francis.stage16.federation.live_runtime_readback_receipt"
        assert body["readback_id"] == readback_id
        assert body["status"] == "observed"
        assert body["observed"] is True
        assert body["readback_ready"] is True
        assert body["actor"] == "test.federation.write"
        assert body["governance"]["permission_scope"] == "federation.write"
        assert body["governance"]["readback_receipt"] is True
        assert body["governance"]["node_attributed"] is True
        assert body["governance"]["trace_linked"] is True
        assert body["governance"]["redacted"] is True
        assert body["governance"]["contains_raw_private_data"] is False
        assert body["writes_registry"] is False
        assert body["writes_memory"] is False
        assert body["runs_tools"] is False
        assert body["grants_execution_authority"] is False
        assert body["grants_mutation_authority"] is False
        receipt_ids.append(body["receipt_id"])

    readbacks = client.get("/federation/live-runtime-readbacks").json()
    assert readbacks["kind"] == "francis.stage16.federation.live_runtime_readback_receipts"
    assert readbacks["status"] == "partial"
    assert readbacks["count"] == 5
    assert readbacks["receipt_ready_count"] == 5
    assert readbacks["ready_count"] == 0
    assert readbacks["completion_eligible_readback_count"] == 0
    assert readbacks["required_count"] == 5
    assert readbacks["readback_receipts_ready"] is True
    assert readbacks["live_runtime_readback_ready"] is False
    assert readbacks["missing_readbacks"] == readback_ids
    assert {item["receipt_id"] for item in readbacks["checks"]} == set(receipt_ids)
    assert all(item["receipt_ready"] is True for item in readbacks["checks"])
    assert all(item["completion_evidence"] is False for item in readbacks["checks"])
    assert all(item["proof_kind"] == "scripted_local_runtime_probe" for item in readbacks["checks"])
    assert readbacks["writes_registry"] is False
    assert readbacks["writes_memory"] is False

    review = client.get("/federation/completion-review").json()
    assert review["status"] == "blocked"
    assert review["contract_readiness_ready"] is True
    assert review["live_runtime_readback_ready"] is False
    assert review["stage16_completion_review_ready"] is False
    assert review["ready_to_close"] is False
    assert review["stage_closure_decision_required"] is False
    assert review["live_ready_count"] == 0
    assert review["live_required_count"] == 5
    assert review["blockers"] == readback_ids
    assert review["done_criteria"]["workstation_sleep_does_not_destroy_continuity"] is False
    assert review["done_criteria"]["remote_approval_is_safe_and_traceable"] is False
    assert review["done_criteria"]["multi_device_francis_feels_like_one_governed_system"] is False
    assert review["next_smallest_truthful_gap"] == "stage16_live_federation_runtime_readback"

    status = client.get("/federation/status").json()
    assert status["stage16_status"] == "stage16_contracts_ready_completion_blocked"
    assert status["stage16_completion_review_ready"] is False
    assert status["live_runtime_readback_ready"] is False
    assert status["completion_review_blockers"] == readback_ids
    assert status["next_smallest_truthful_gap"] == "stage16_live_federation_runtime_readback"


def test_federation_stage16_partial_live_runtime_readbacks_surface_next_missing_gap(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage15_closure_receipt(data_root, receipt_id="swarm_stage15_closure_for_partial_live_readbacks")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    for index, readback_id in enumerate(
        [
            "live_pairing_flow_observed",
            "live_selective_sync_observed",
            "live_remote_approval_roundtrip_observed",
        ],
        start=1,
    ):
        response = client.post(
            "/federation/live-runtime-readback",
            json={
                "request_actor": "test.federation.write",
                "reason": f"record partial live runtime evidence for {readback_id}",
                "readback_id": readback_id,
                "observed": True,
                "proof_kind": "live_runtime_probe",
                "source_node_id": "workstation-a",
                "paired_node_id": "phone-a",
                "trace_id": f"trace-fed-partial-{index}",
                "parent_receipt_id": "swarm_stage15_closure_for_partial_live_readbacks",
                "evidence_summary": f"partial live federation runtime readback for {readback_id}",
            },
        )
        assert response.status_code == 200
        assert response.json()["readback_ready"] is True

    readbacks = client.get("/federation/live-runtime-readbacks").json()
    assert readbacks["status"] == "partial"
    assert readbacks["ready_count"] == 3
    assert readbacks["completion_eligible_readback_count"] == 3
    assert readbacks["missing_readbacks"] == [
        "live_revocation_roundtrip_observed",
        "workstation_sleep_continuity_validated",
    ]
    assert readbacks["next_smallest_truthful_gap"] == "stage16_revocation_runtime_readback"

    review = client.get("/federation/completion-review").json()
    assert review["status"] == "blocked"
    assert review["live_ready_count"] == 3
    assert review["ready_to_close"] is False
    assert review["next_smallest_truthful_gap"] == "stage16_revocation_runtime_readback"

    status = client.get("/federation/status").json()
    assert status["stage16_status"] == "stage16_contracts_ready_completion_blocked"
    assert status["stage16_completion_review_ready"] is False
    assert status["completion_review_blockers"] == [
        "live_revocation_roundtrip_observed",
        "workstation_sleep_continuity_validated",
    ]
    assert status["next_smallest_truthful_gap"] == "stage16_revocation_runtime_readback"


def test_federation_stage16_sleep_continuity_runbook_blocks_on_prior_live_readbacks(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage15_closure_receipt(data_root, receipt_id="swarm_stage15_closure_for_runbook_blocked")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.get("/federation/sleep-continuity-runbook")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage16.federation.sleep_continuity_runbook"
    assert body["status"] == "blocked_on_prior_live_readbacks"
    assert body["runbook_only"] is True
    assert body["prerequisite_readbacks_ready"] is False
    assert body["sleep_continuity_ready"] is False
    assert body["ready_to_close"] is False
    assert body["stage16_closed_by_receipt"] is False
    assert body["current_readback"]["ready_count"] == 0
    assert body["current_readback"]["required_count"] == 5
    assert body["missing_readbacks"] == [
        "live_pairing_flow_observed",
        "live_selective_sync_observed",
        "live_remote_approval_roundtrip_observed",
        "live_revocation_roundtrip_observed",
        "workstation_sleep_continuity_validated",
    ]
    assert body["steps"][0]["id"] == "capture_pre_sleep_evidence"
    assert body["steps"][1]["id"] == "capture_post_resume_evidence"
    assert body["steps"][1]["operator_confirmation_required"] is True
    assert body["steps"][2]["id"] == "commit_sleep_continuity_readback"
    assert body["steps"][3]["id"] == "record_operator_stage_closure_decision"
    assert body["steps"][3]["route"] == "/federation/stage-closure-decision"
    assert body["routes"]["sleep_continuity_runbook"] == "/federation/sleep-continuity-runbook"
    assert body["governance"]["read_only"] is True
    assert body["governance"]["runbook_only"] is True
    assert body["governance"]["does_not_infer_sleep_from_delay"] is True
    assert body["governance"]["requires_explicit_sleep_resume_confirmation"] is True
    assert body["governance"]["writes_evidence"] is False
    assert body["governance"]["writes_receipts"] is False
    assert body["writes_evidence"] is False
    assert body["writes_receipts"] is False
    assert body["runs_shell"] is False
    assert body["grants_execution_authority"] is False
    assert body["marks_stage16_closed"] is False
    assert body["next_smallest_truthful_gap"] == "stage16_live_federation_runtime_readback"
    assert not (data_root / "logs" / "federation" / "stage16_operator_stage_closure_decisions.jsonl").exists()


def test_federation_stage16_sleep_continuity_runbook_reports_ready_for_operator_sleep_resume(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage15_closure_receipt(data_root, receipt_id="swarm_stage15_closure_for_runbook")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    for readback_id in [
        "live_pairing_flow_observed",
        "live_selective_sync_observed",
        "live_remote_approval_roundtrip_observed",
        "live_revocation_roundtrip_observed",
    ]:
        _record_stage16_live_readback(client, readback_id)

    response = client.get("/federation/sleep-continuity-runbook")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "ready_for_operator_sleep_resume"
    assert body["prerequisite_readback_ids"] == [
        "live_pairing_flow_observed",
        "live_selective_sync_observed",
        "live_remote_approval_roundtrip_observed",
        "live_revocation_roundtrip_observed",
    ]
    assert body["prerequisite_readbacks_ready"] is True
    assert body["sleep_continuity_readback_id"] == "workstation_sleep_continuity_validated"
    assert body["sleep_continuity_ready"] is False
    assert body["sleep_continuity_check"]["id"] == "workstation_sleep_continuity_validated"
    assert body["sleep_continuity_check"]["passed"] is False
    assert body["missing_readbacks"] == ["workstation_sleep_continuity_validated"]
    assert body["current_readback"]["ready_count"] == 4
    assert body["current_readback"]["required_count"] == 5
    assert body["completion_review"]["ready_to_close"] is False
    assert body["completion_review"]["stage16_completion_review_ready"] is False
    assert body["completion_review"]["blockers"] == ["workstation_sleep_continuity_validated"]
    assert body["stage_closure_decision"]["status"] == "empty"
    assert body["stage_closure_decision"]["stage16_closed_by_receipt"] is False
    assert [step["id"] for step in body["steps"]] == [
        "capture_pre_sleep_evidence",
        "capture_post_resume_evidence",
        "commit_sleep_continuity_readback",
        "record_operator_stage_closure_decision",
    ]
    assert body["steps"][0]["command"] == (
        "scripts/federation-stage16-sleep-continuity-evidence.ps1 -Mode PreSleep -CommitEvidence"
    )
    assert "-OperatorConfirmedSleepResume" in body["steps"][1]["command"]
    assert "federation-stage16-sleep-continuity-runtime-proof.ps1" in body["steps"][2]["command"]
    assert body["steps"][2]["writes_receipts_when_run"] is True
    assert body["steps"][3]["required_scope"] == "federation.stage16.closure.write"
    assert body["governance"]["read_only"] is True
    assert body["governance"]["runbook_only"] is True
    assert body["governance"]["writes_registry"] is False
    assert body["governance"]["writes_memory"] is False
    assert body["governance"]["runs_tools"] is False
    assert body["governance"]["runs_shell"] is False
    assert body["governance"]["grants_mutation_authority"] is False
    assert body["next_smallest_truthful_gap"] == "stage16_sleep_continuity_runtime_readback"


def test_federation_stage16_completion_review_accepts_live_or_manual_runtime_readback_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage15_closure_receipt(data_root, receipt_id="swarm_stage15_closure_for_live_completion_evidence")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    readback_ids = [
        "live_pairing_flow_observed",
        "live_selective_sync_observed",
        "live_remote_approval_roundtrip_observed",
        "live_revocation_roundtrip_observed",
        "workstation_sleep_continuity_validated",
    ]

    for index, readback_id in enumerate(readback_ids, start=1):
        response = client.post(
            "/federation/live-runtime-readback",
            json={
                "request_actor": "test.federation.write",
                "reason": f"record completion-eligible {readback_id}",
                "readback_id": readback_id,
                "observed": True,
                "proof_kind": "live_runtime_probe" if index < 5 else "manual_operator_runtime_readback",
                "source_node_id": "workstation-a",
                "paired_node_id": "phone-a",
                "trace_id": f"trace-fed-completion-{index}",
                "parent_receipt_id": "swarm_stage15_closure_for_live_completion_evidence",
                "evidence_summary": f"live federation runtime readback for {readback_id}",
            },
        )
        assert response.status_code == 200
        assert response.json()["readback_ready"] is True

    readbacks = client.get("/federation/live-runtime-readbacks").json()
    assert readbacks["status"] == "ready"
    assert readbacks["receipt_ready_count"] == 5
    assert readbacks["ready_count"] == 5
    assert readbacks["completion_eligible_readback_count"] == 5
    assert readbacks["readback_receipts_ready"] is True
    assert readbacks["live_runtime_readback_ready"] is True
    assert readbacks["missing_readbacks"] == []
    assert all(item["receipt_ready"] is True for item in readbacks["checks"])
    assert all(item["completion_evidence"] is True for item in readbacks["checks"])

    review = client.get("/federation/completion-review").json()
    assert review["status"] == "ready"
    assert review["stage16_completion_review_ready"] is True
    assert review["ready_to_close"] is True
    assert review["stage_closure_decision_required"] is True
    assert review["live_ready_count"] == 5
    assert review["blockers"] == []
    assert review["next_smallest_truthful_gap"] == "stage16_operator_stage_closure_decision"


def test_federation_stage16_closure_decision_waits_for_completion_review(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({"test.federation.closure": ["federation.stage16.closure.write"]}),
    )
    _write_stage15_closure_receipt(data_root, receipt_id="swarm_stage15_closure_for_blocked_stage16_closure")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.post(
        "/federation/stage-closure-decision",
        json={
            "actor": "test.federation.closure",
            "reason": "attempt stage16 closure before live runtime readbacks",
            "decision": "close_stage16",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "awaiting_stage16_closure_readiness"
    assert body["receipt"] is None
    assert body["receipt_id"] == ""
    assert body["writes_receipt"] is False
    assert body["marks_runtime_stage_state"] is False
    assert body["review"]["stage16_completion_review_ready"] is False
    assert body["next_smallest_truthful_gap"] == "stage16_live_federation_runtime_readback"
    assert not (data_root / "logs" / "federation" / "stage16_operator_stage_closure_decisions.jsonl").exists()


def test_federation_stage16_closure_decision_records_after_live_readbacks(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps(
            {
                "test.federation.write": ["federation.write"],
                "test.federation.closure": ["federation.stage16.closure.write"],
            }
        ),
    )
    _write_stage15_closure_receipt(data_root, receipt_id="swarm_stage15_closure_for_stage16_closure_decision")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    readback_ids = [
        "live_pairing_flow_observed",
        "live_selective_sync_observed",
        "live_remote_approval_roundtrip_observed",
        "live_revocation_roundtrip_observed",
        "workstation_sleep_continuity_validated",
    ]
    for index, readback_id in enumerate(readback_ids, start=1):
        response = client.post(
            "/federation/live-runtime-readback",
            json={
                "request_actor": "test.federation.write",
                "reason": f"record completion-eligible {readback_id}",
                "readback_id": readback_id,
                "observed": True,
                "proof_kind": "live_runtime_probe" if index < 5 else "manual_operator_runtime_readback",
                "source_node_id": "workstation-a",
                "paired_node_id": "phone-a",
                "trace_id": f"trace-fed-stage16-closure-{index}",
                "parent_receipt_id": "swarm_stage15_closure_for_stage16_closure_decision",
                "evidence_summary": f"live federation runtime readback for {readback_id}",
            },
        )
        assert response.status_code == 200
        assert response.json()["readback_ready"] is True

    empty_readback = client.get("/federation/stage-closure-decisions?limit=10").json()
    assert empty_readback["status"] == "empty"
    assert empty_readback["stage16_closed_by_receipt"] is False

    closure = client.post(
        "/federation/stage-closure-decision",
        json={
            "actor": "test.federation.closure",
            "reason": "close stage16 token=stage16closuresecret123",
            "decision": "close_stage16",
            "notes": "operator stage closure notes token=stage16closurenotesecret123",
        },
    )

    assert closure.status_code == 200
    body = closure.json()
    assert body["ok"] is True
    assert body["status"] == "recorded"
    assert body["writes_receipt"] is True
    assert body["writes_registry"] is False
    assert body["writes_memory"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["launches_browser"] is False
    assert body["captures_screen"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["marks_runtime_stage_state"] is False
    assert body["decision"] == "close_stage16"
    assert body["stage16_closed_by_receipt"] is True
    assert body["next_smallest_truthful_gap"] == "stage16_ledger_closure"

    receipt = body["receipt"]
    assert receipt["kind"] == "francis.stage16.federation.stage16_operator_stage_closure_decision_receipt"
    assert receipt["receipt_id"] == body["receipt_id"]
    assert receipt["actor"] == "test.federation.closure"
    assert receipt["decision"] == "close_stage16"
    assert receipt["completion_review_ready"] is True
    assert receipt["stage16_completion_review_ready"] is True
    assert receipt["contract_readiness_ready"] is True
    assert receipt["live_runtime_readback_ready"] is True
    assert receipt["stage16_closed_by_receipt"] is True
    assert receipt["live_ready_count"] == 5
    assert receipt["live_required_count"] == 5
    assert receipt["blockers"] == []
    assert len(receipt["latest_live_runtime_readback_receipt_ids"]) == 5
    assert receipt["marks_runtime_stage_state"] is False
    assert receipt["governance"]["permission_scope"] == "federation.stage16.closure.write"
    assert receipt["governance"]["explicit_operator_decision"] is True
    assert receipt["governance"]["stage_closure_decision"] is True
    assert receipt["governance"]["requires_completion_review_ready"] is True
    assert receipt["governance"]["requires_live_runtime_readback"] is True
    assert receipt["governance"]["does_not_mutate_runtime_stage_state"] is True
    assert receipt["governance"]["grants_execution_authority"] is False
    assert receipt["governance"]["grants_mutation_authority"] is False
    receipt_text = json.dumps(receipt, sort_keys=True)
    assert "stage16closuresecret123" not in receipt_text
    assert "stage16closurenotesecret123" not in receipt_text

    readback = client.get("/federation/stage-closure-decisions?limit=10").json()
    assert readback["status"] == "stage_closure_decision_readback_ready"
    assert readback["count"] == 1
    assert readback["latest_receipt_id"] == body["receipt_id"]
    assert readback["latest_decision"] == "close_stage16"
    assert readback["decision_counts"] == {
        "close_stage16": 1,
        "do_not_close_stage16": 0,
        "needs_more_evidence": 0,
    }
    assert readback["receipt_readback_ready"] is True
    assert readback["stage16_closed_by_receipt"] is True
    assert readback["marks_runtime_stage_state"] is False
    assert readback["writes_receipts"] is False
    assert readback["writes_registry"] is False
    assert readback["writes_memory"] is False
    assert readback["runs_tools"] is False
    assert readback["runs_shell"] is False
    assert readback["runs_git"] is False
    assert readback["launches_browser"] is False
    assert readback["captures_screen"] is False
    assert readback["grants_execution_authority"] is False
    assert readback["governance"]["stage_closure_decision_receipt_readback"] is True
    assert readback["governance"]["does_not_mutate_runtime_stage_state"] is True
    assert readback["next_smallest_truthful_gap"] == "stage16_ledger_closure"

    status = client.get("/federation/status").json()
    assert status["stage16_status"] == "stage16_closed_by_receipt"
    assert status["stage16_closed_by_receipt"] is True
    assert status["latest_stage_closure_decision_receipt"]["receipt_id"] == body["receipt_id"]
    assert status["next_smallest_truthful_gap"] == "stage16_ledger_closure"
