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
    assert status["stage16_status"] == "stage16_pairing_scoped_trust_contract_ready"
    assert status["pairing_scoped_trust_contract_ready"] is True
    assert status["ready_count"] == 2
    assert status["required_count"] == 6
    assert status["routes"]["pairing_scoped_trust_contract"] == "/federation/pairing-scoped-trust-contract"
    assert status["next_smallest_truthful_gap"] == "stage16_sync_model_contract"
