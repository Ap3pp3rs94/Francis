from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import francis.managed_copy_safe_delta as managed_copy_safe_delta
import francis.managed_copy_safe_delta_approval as safe_delta_approval
import francis.managed_copy_safe_delta_export as safe_delta_export
import francis.managed_copy_safe_delta_export_authorization as safe_delta_export_authorization
from francis.api.app import create_app


def test_managed_copies_status_is_readonly_stage18_prerequisite_contract(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    response = TestClient(create_app()).get("/managed-copies/status")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "francis.stage18.managed_copies.status"
    assert body["stage"] == "Stage 18 / Managed Copies Platform"
    assert body["source_id"] == "managed_copies"
    assert body["status"] == "stage18_prerequisites_blocked"
    assert body["status_readback_ready"] is True
    assert body["stage17_closed_by_receipt"] is False
    assert body["stage17_blocker"] == "stage17_operator_stage_closure_decision"
    assert body["next_smallest_truthful_gap"] == "stage17_operator_stage_closure_decision"
    assert body["ready_count"] == 0
    assert body["required_count"] == len(body["deliverables"])
    assert body["routes"] == {
        "status": "/managed-copies/status",
        "copy_creation_contract": "/managed-copies/copy-creation-contract",
        "copy_creation_request": "/managed-copies/copy-creation-request",
        "copy_creation_requests": "/managed-copies/copy-creation-requests",
        "copy_creation_preflight": "/managed-copies/copy-creation-preflight",
        "copy_creation_preflights": "/managed-copies/copy-creation-preflights",
        "copy_creation_plan": "/managed-copies/copy-creation-plan",
        "copy_creation_plans": "/managed-copies/copy-creation-plans",
        "copy_creation_approval_request": "/managed-copies/copy-creation-approval-request",
        "copy_creation_approval_requests": "/managed-copies/copy-creation-approval-requests",
        "copy_creation_provision": "/managed-copies/copy-creation-provision",
        "copy_creation_provisions": "/managed-copies/copy-creation-provisions",
        "isolation_rules_contract": "/managed-copies/isolation-rules-contract",
        "isolation_verification": "/managed-copies/isolation-verification",
        "isolation_verifications": "/managed-copies/isolation-verifications",
        "safe_delta_model_contract": "/managed-copies/safe-delta-model-contract",
        "safe_delta_review": "/managed-copies/safe-delta-review",
        "safe_delta_reviews": "/managed-copies/safe-delta-reviews",
        "safe_delta_decision": "/managed-copies/safe-delta-decision",
        "safe_delta_decisions": "/managed-copies/safe-delta-decisions",
        "safe_delta_export_preflight": "/managed-copies/safe-delta-export-preflight",
        "safe_delta_export_authorization_request": "/managed-copies/safe-delta-export-authorization-request",
        "safe_delta_export_authorization_requests": "/managed-copies/safe-delta-export-authorization-requests",
        "rogue_recovery_contract": "/managed-copies/rogue-recovery-contract",
        "rogue_recovery_review": "/managed-copies/rogue-recovery-review",
        "sla_framework_contract": "/managed-copies/sla-framework-contract",
        "sla_commitment_review": "/managed-copies/sla-commitment-review",
        "roles_contract": "/managed-copies/roles-contract",
        "role_authority_review": "/managed-copies/role-authority-review",
        "decommission_contract": "/managed-copies/decommission-contract",
        "decommission_review": "/managed-copies/decommission-review",
        "runtime_evidence_contract": "/managed-copies/runtime-evidence-contract",
        "runtime_evidence_readbacks": "/managed-copies/runtime-evidence-readbacks",
        "runtime_evidence_readback": "/managed-copies/runtime-evidence-readback",
        "completion_review": "/managed-copies/completion-review",
        "stage17_closure_decisions": "/plugins/capabilities/stage17/stage-closure-decisions",
    }

    deliverable_ids = {item["id"] for item in body["deliverables"]}
    assert {
        "stage17_ledger_closure_backstop",
        "copy_creation_process",
        "isolation_rules",
        "safe_delta_model",
        "rogue_recovery",
        "sla_framework",
        "managed_copy_roles",
        "exit_rights",
    } <= deliverable_ids
    assert all(item["ready"] is False for item in body["deliverables"])

    assert body["managed_copy_roles_required"] == [
        "end_user",
        "tenant_admin",
        "support_operator",
        "automation_principal",
        "paired_node",
    ]
    assert body["managed_copy_state_classes"] == [
        "managed_copy_configuration",
        "tenant_policy",
        "copy_identity",
        "capability_delta",
        "decommission_receipt",
    ]
    assert body["failure_modes_blocked_by_contract"] == [
        "core_surrender",
        "privacy_weak_pooling",
        "uncontrolled_forks",
        "support_chaos",
        "invisible_vendor_power",
    ]

    assert body["read_only"] is True
    assert body["projection_only"] is True
    assert body["copy_creation_enabled"] is False
    assert body["writes_registry"] is False
    assert body["writes_memory"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["launches_browser"] is False
    assert body["captures_screen"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False

    governance = body["governance"]
    assert governance["read_only"] is True
    assert governance["projection_only"] is True
    assert governance["copy_creation_enabled"] is False
    assert governance["writes_registry"] is False
    assert governance["writes_memory"] is False
    assert governance["writes_receipts"] is False
    assert governance["writes_tenant_state"] is False
    assert governance["runs_tools"] is False
    assert governance["runs_shell"] is False
    assert governance["runs_git"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False
    assert governance["core_surrender_allowed"] is False
    assert governance["privacy_weak_pooling_allowed"] is False
    assert governance["uncontrolled_forks_allowed"] is False
    assert governance["invisible_vendor_power_allowed"] is False
    assert not data_root.exists()


def test_managed_copies_consume_valid_stage17_closure_receipt_without_enabling_runtime(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    actor = "stage18.copy-after-stage17"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({actor: ["managed_copies.copy_creation.write"]}),
    )

    from francis.economy.stage17_closure import record_stage17_operator_stage_closure_decision

    criteria = [{"id": f"criterion_{index}", "status": "ready", "blockers": []} for index in range(1, 7)]
    closure_receipt = record_stage17_operator_stage_closure_decision(
        actor="test.stage17.operator",
        reason="validated Stage 17 closure fixture",
        decision="close_stage17",
        review={
            "status": "ready",
            "stage17_completion_review_ready": True,
            "criteria_ready_count": 6,
            "criteria_required_count": 6,
            "closure_matrix": {
                "kind": "plugin.capability_catalog.stage17_closure_matrix",
                "status": "ready_for_closure_review",
                "all_criteria_ready": True,
                "criteria": criteria,
                "source_readbacks": {"catalog_route": "/plugins/capabilities/catalog"},
            },
        },
    )

    client = TestClient(create_app())
    status = client.get("/managed-copies/status").json()
    assert status["status"] == "stage18_groundwork_open"
    assert status["stage17_closed_by_receipt"] is True
    assert status["stage17_closure_receipt_id"] == closure_receipt["receipt_id"]
    assert status["stage17_closure_receipt_valid"] is True
    assert status["stage17_blocker"] == ""
    assert status["ready_count"] == 1
    assert status["deliverables"][0]["ready"] is True
    assert status["next_smallest_truthful_gap"] == "stage18_copy_creation_request_recording"

    contract_routes = [
        "/managed-copies/copy-creation-contract",
        "/managed-copies/isolation-rules-contract",
        "/managed-copies/safe-delta-model-contract",
        "/managed-copies/rogue-recovery-contract",
        "/managed-copies/sla-framework-contract",
        "/managed-copies/roles-contract",
        "/managed-copies/decommission-contract",
    ]
    for route in contract_routes:
        contract = client.get(route).json()
        assert contract["stage17_closed_by_receipt"] is True, route
        assert contract["stage17_blocker"] == "", route
        assert contract["next_smallest_truthful_gap"] == "stage18_copy_creation_request_recording", route
        assert contract["grants_execution_authority"] is False, route
        assert contract["grants_mutation_authority"] is False, route

    runtime_contract = client.get("/managed-copies/runtime-evidence-contract").json()
    closure_requirement = next(
        item for item in runtime_contract["requirements"] if item["id"] == "stage17_closure_receipt"
    )
    assert closure_requirement["ready"] is True
    assert closure_requirement["receipt_id"] == closure_receipt["receipt_id"]
    assert closure_requirement["blocker"] == ""
    assert runtime_contract["ready_count"] == 1
    assert "stage17_operator_stage_closure_decision" not in runtime_contract["blockers"]

    runtime_readbacks = client.get("/managed-copies/runtime-evidence-readbacks").json()
    closure_check = next(item for item in runtime_readbacks["checks"] if item["id"] == "stage17_closure_receipt")
    assert closure_check["passed"] is True
    assert closure_check["receipt_id"] == closure_receipt["receipt_id"]
    assert "stage17_closure_receipt" not in runtime_readbacks["missing_evidence"]

    completion = client.get("/managed-copies/completion-review").json()
    stage17_check = next(item for item in completion["checks"] if item["id"] == "stage17_ledger_closure_backstop")
    assert stage17_check["passed"] is True
    assert completion["stage18_completion_review_ready"] is False
    assert "stage17_operator_stage_closure_decision" not in completion["blockers"]
    assert completion["next_smallest_truthful_gap"] == "stage18_copy_creation_runtime_not_implemented"

    request = client.post(
        "/managed-copies/copy-creation-request",
        json={
            "request_actor": actor,
            "tenant_id": "tenant-still-not-created",
        },
    ).json()
    assert request["status"] == "blocked_copy_request_contract"
    assert request["error"] == "copy_request_contract_not_ready"
    assert "tenant_identity_missing_or_invalid" in request["blockers"]
    assert request["stage17_closed_by_receipt"] is True
    assert request["stage17_blocker"] == ""
    assert request["copy_created"] is False
    assert request["writes_receipts"] is False
    assert request["writes_tenant_state"] is False
    assert request["grants_execution_authority"] is False
    assert request["grants_mutation_authority"] is False


def test_managed_copy_request_records_redacted_receipt_after_hash_bound_dry_run(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    actor = "stage18.copy-request-recorder"
    raw_tenant_id = "customer-alpha-private-id"
    raw_tenant_name = "Customer Alpha Private Name"
    raw_admin = "customer.alpha.admin@example.test"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({actor: ["managed_copies.copy_creation.write"]}),
    )

    from francis.economy.stage17_closure import record_stage17_operator_stage_closure_decision

    criteria = [{"id": f"criterion_{index}", "status": "ready", "blockers": []} for index in range(1, 7)]
    stage17_receipt = record_stage17_operator_stage_closure_decision(
        actor="test.stage17.operator",
        reason="validated Stage 17 closure fixture",
        decision="close_stage17",
        review={
            "status": "ready",
            "stage17_completion_review_ready": True,
            "criteria_ready_count": 6,
            "criteria_required_count": 6,
            "closure_matrix": {
                "kind": "plugin.capability_catalog.stage17_closure_matrix",
                "status": "ready_for_closure_review",
                "all_criteria_ready": True,
                "criteria": criteria,
                "source_readbacks": {"catalog_route": "/plugins/capabilities/catalog"},
            },
        },
    )
    payload = {
        "request_actor": actor,
        "tenant_id": raw_tenant_id,
        "tenant_identity": {"tenant_name": raw_tenant_name, "tenant_admin_actor": raw_admin},
        "tenant_policy": {
            "core_surrender_allowed": False,
            "privacy_weak_pooling_allowed": False,
        },
        "isolation_profile": {
            "tenant_data": "isolated",
            "tenant_memory": "isolated",
            "tenant_receipts": "isolated",
        },
        "capability_lineage": {"base_pack": "francis-core", "customization_layer": "tenant"},
        "safe_delta_policy": {"raw_private_pooling_allowed": False, "operator_review_required": True},
        "support_boundary": {"support_access_default": "denied", "time_bound": True},
        "decommission_policy": {"export_required": True, "proof_receipts_required": True},
        "dry_run": True,
    }
    client = TestClient(create_app())

    planned = client.post("/managed-copies/copy-creation-request", json=payload).json()

    assert planned["ok"] is True
    assert planned["status"] == "planned"
    assert planned["request_contract_ready"] is True
    assert planned["stage17_closed_by_receipt"] is True
    assert planned["dry_run"] is True
    assert len(planned["dry_run_fingerprint"]) == 64
    assert len(planned["tenant_key"]) == 64
    assert planned["blockers"] == []
    assert planned["copy_request_recording_enabled"] is True
    assert planned["copy_request_recorded"] is False
    assert planned["copy_created"] is False
    assert planned["writes_receipts"] is False
    assert planned["writes_tenant_state"] is False
    assert planned["grants_execution_authority"] is False
    assert planned["grants_mutation_authority"] is False
    assert raw_tenant_id not in json.dumps(planned)
    assert raw_tenant_name not in json.dumps(planned)
    assert raw_admin not in json.dumps(planned)

    receipt_path = data_root / "logs" / "managed_copies" / "copy_requests.jsonl"
    assert not receipt_path.exists()

    mismatched = client.post(
        "/managed-copies/copy-creation-request",
        json={
            **payload,
            "dry_run": False,
            "dry_run_fingerprint": "0" * 64,
            "confirm_request_recording": True,
        },
    ).json()
    assert mismatched["ok"] is False
    assert mismatched["status"] == "blocked_dry_run_confirmation"
    assert mismatched["error"] == "dry_run_fingerprint_mismatch"
    assert mismatched["writes_receipts"] is False
    assert not receipt_path.exists()

    recorded = client.post(
        "/managed-copies/copy-creation-request",
        json={
            **payload,
            "dry_run": False,
            "dry_run_fingerprint": planned["dry_run_fingerprint"],
            "confirm_request_recording": True,
        },
    ).json()

    assert recorded["ok"] is True
    assert recorded["status"] == "recorded"
    assert recorded["copy_request_recorded"] is True
    assert recorded["copy_created"] is False
    assert recorded["receipt_ready"] is True
    assert recorded["receipt_id"].startswith("managed_copy_request_")
    assert recorded["writes_receipts"] is True
    assert recorded["writes_tenant_state"] is False
    assert recorded["grants_execution_authority"] is False
    assert recorded["grants_mutation_authority"] is False
    assert recorded["receipt"]["stage17_closure_receipt_id"] == stage17_receipt["receipt_id"]
    assert recorded["receipt"]["governance"]["dry_run_fingerprint_matched"] is True
    assert recorded["receipt"]["governance"]["contains_raw_tenant_payload"] is False
    assert recorded["receipt"]["governance"]["does_not_create_copy"] is True
    assert recorded["next_smallest_truthful_gap"] == "stage18_copy_creation_preflight_process"

    receipt_text = receipt_path.read_text(encoding="utf-8")
    assert len(receipt_text.splitlines()) == 1
    assert raw_tenant_id not in receipt_text
    assert raw_tenant_name not in receipt_text
    assert raw_admin not in receipt_text

    readback = client.get("/managed-copies/copy-creation-requests").json()
    assert readback["status"] == "ready"
    assert readback["count"] == 1
    assert readback["valid_count"] == 1
    assert readback["latest_receipt_id"] == recorded["receipt_id"]
    assert readback["latest_receipt_valid"] is True
    assert readback["copy_request_recording_ready"] is True
    assert readback["writes_receipts"] is False
    assert readback["writes_tenant_state"] is False
    assert readback["next_smallest_truthful_gap"] == "stage18_copy_creation_preflight_process"

    duplicate = client.post(
        "/managed-copies/copy-creation-request",
        json={
            **payload,
            "dry_run": False,
            "dry_run_fingerprint": planned["dry_run_fingerprint"],
            "confirm_request_recording": True,
        },
    ).json()
    assert duplicate["status"] == "already_recorded"
    assert duplicate["receipt_id"] == recorded["receipt_id"]
    assert duplicate["copy_request_recorded"] is True
    assert duplicate["writes_receipts"] is False
    assert len(receipt_path.read_text(encoding="utf-8").splitlines()) == 1

    status = client.get("/managed-copies/status").json()
    creation = next(item for item in status["deliverables"] if item["id"] == "copy_creation_process")
    assert creation["ready"] is False
    assert creation["status"] == "request_recorded"
    assert status["copy_request_recorded"] is True
    assert status["copy_request_receipt_id"] == recorded["receipt_id"]
    assert status["next_smallest_truthful_gap"] == "stage18_copy_creation_preflight_process"

    contract = client.get("/managed-copies/copy-creation-contract").json()
    assert contract["copy_creation_enabled"] is False
    assert contract["copy_request_recording_enabled"] is True
    assert contract["copy_request_recorded"] is True
    assert contract["copy_request_receipt_id"] == recorded["receipt_id"]
    assert contract["ready_count"] == contract["required_count"]
    step_by_id = {item["id"]: item for item in contract["process_steps"]}
    assert step_by_id["request"]["status"] == "complete"
    assert step_by_id["preflight"]["status"] == "enabled"
    assert step_by_id["plan"]["status"] == "blocked"
    assert step_by_id["provision"]["status"] == "disabled"
    assert contract["state_machine"]["current_state"] == "requested"
    assert contract["state_machine"]["enabled_transitions"] == ["record_preflight"]
    assert not (data_root / "managed_copies").exists()

    foreign_receipt = json.loads(json.dumps(recorded["receipt"]))
    foreign_receipt["receipt_id"] = "managed_copy_request_foreign"
    foreign_receipt["stage17_closure_receipt_id"] = "stage17_capability_economy_closure_foreign"
    with receipt_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(foreign_receipt) + "\n")
        handle.write(json.dumps({"receipt_id": "invalid_trailing_row"}) + "\n")

    mixed_readback = client.get("/managed-copies/copy-creation-requests").json()
    assert mixed_readback["count"] == 3
    assert mixed_readback["valid_count"] == 2
    assert mixed_readback["latest_receipt_valid"] is False
    assert mixed_readback["latest_valid_receipt_id"] == "managed_copy_request_foreign"

    aligned_status = client.get("/managed-copies/status").json()
    assert aligned_status["copy_request_recorded"] is True
    assert aligned_status["copy_request_receipt_id"] == recorded["receipt_id"]
    assert aligned_status["copy_request_stage17_receipt_aligned"] is True

    duplicate_after_foreign = client.post(
        "/managed-copies/copy-creation-request",
        json={
            **payload,
            "dry_run": False,
            "dry_run_fingerprint": planned["dry_run_fingerprint"],
            "confirm_request_recording": True,
        },
    ).json()
    assert duplicate_after_foreign["status"] == "already_recorded"
    assert duplicate_after_foreign["receipt_id"] == recorded["receipt_id"]
    assert duplicate_after_foreign["writes_receipts"] is False


def test_managed_copy_preflight_records_redacted_request_aligned_receipt(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    actor = "stage18.copy-preflight-recorder"
    raw_tenant_id = "customer-preflight-private-id"
    raw_tenant_name = "Customer Preflight Private Name"
    raw_admin = "customer.preflight.admin@example.test"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({actor: ["managed_copies.copy_creation.write"]}),
    )

    from francis.economy.stage17_closure import record_stage17_operator_stage_closure_decision

    criteria = [{"id": f"criterion_{index}", "status": "ready", "blockers": []} for index in range(1, 7)]
    record_stage17_operator_stage_closure_decision(
        actor="test.stage17.operator",
        reason="validated Stage 17 closure fixture",
        decision="close_stage17",
        review={
            "status": "ready",
            "stage17_completion_review_ready": True,
            "criteria_ready_count": 6,
            "criteria_required_count": 6,
            "closure_matrix": {
                "kind": "plugin.capability_catalog.stage17_closure_matrix",
                "status": "ready_for_closure_review",
                "all_criteria_ready": True,
                "criteria": criteria,
                "source_readbacks": {"catalog_route": "/plugins/capabilities/catalog"},
            },
        },
    )
    request_payload = {
        "request_actor": actor,
        "tenant_id": raw_tenant_id,
        "tenant_identity": {"tenant_name": raw_tenant_name, "tenant_admin_actor": raw_admin},
        "tenant_policy": {
            "core_surrender_allowed": False,
            "privacy_weak_pooling_allowed": False,
        },
        "isolation_profile": {
            "tenant_data": "isolated",
            "tenant_memory": "isolated",
            "tenant_receipts": "isolated",
            "tenant_connectors": "isolated",
            "tenant_capability_packs": "isolated",
            "tenant_policy": "isolated",
            "support_operator_authority": "isolated",
        },
        "capability_lineage": {"base_pack": "francis-core", "customization_layer": "tenant"},
        "safe_delta_policy": {"raw_private_pooling_allowed": False, "operator_review_required": True},
        "support_boundary": {"support_access_default": "denied", "time_bound": True},
        "decommission_policy": {"export_required": True, "proof_receipts_required": True},
        "dry_run": True,
    }
    client = TestClient(create_app())
    request_plan = client.post("/managed-copies/copy-creation-request", json=request_payload).json()
    request_record = client.post(
        "/managed-copies/copy-creation-request",
        json={
            **request_payload,
            "dry_run": False,
            "dry_run_fingerprint": request_plan["dry_run_fingerprint"],
            "confirm_request_recording": True,
        },
    ).json()
    preflight_payload = {
        **request_payload,
        "request_receipt_id": request_record["receipt_id"],
        "dry_run": True,
    }

    planned = client.post("/managed-copies/copy-creation-preflight", json=preflight_payload).json()

    assert planned["ok"] is True
    assert planned["kind"] == "francis.stage18.managed_copies.copy_creation_preflight"
    assert planned["status"] == "preflight_planned"
    assert planned["request_receipt_id"] == request_record["receipt_id"]
    assert planned["request_receipt_aligned"] is True
    assert planned["request_payload_fingerprints_matched"] is True
    assert planned["preflight_contract_ready"] is True
    assert planned["managed_copy_law_ready"] is True
    assert planned["managed_copy_law_ready_count"] == planned["managed_copy_law_required_count"]
    assert planned["managed_copy_law_required_count"] == 19
    assert all(check["ready"] is True for check in planned["managed_copy_law_checks"])
    assert all(check["blocker"] == "" for check in planned["managed_copy_law_checks"])
    assert len(planned["preflight_fingerprint"]) == 64
    assert planned["copy_preflight_recorded"] is False
    assert planned["copy_plan_created"] is False
    assert planned["writes_receipts"] is False
    assert planned["writes_tenant_state"] is False
    assert raw_tenant_id not in json.dumps(planned)
    assert raw_tenant_name not in json.dumps(planned)
    assert raw_admin not in json.dumps(planned)

    preflight_path = data_root / "logs" / "managed_copies" / "copy_preflights.jsonl"
    assert not preflight_path.exists()

    mismatched = client.post(
        "/managed-copies/copy-creation-preflight",
        json={
            **preflight_payload,
            "tenant_policy": {
                "core_surrender_allowed": True,
                "privacy_weak_pooling_allowed": False,
            },
        },
    ).json()
    assert mismatched["ok"] is False
    assert mismatched["error"] == "copy_preflight_contract_not_ready"
    assert "tenant_policy_fingerprint_mismatch" in mismatched["blockers"]
    assert "core_surrender_must_remain_blocked" in mismatched["blockers"]
    assert mismatched["managed_copy_law_ready"] is False
    unsafe_check_by_id = {check["id"]: check for check in mismatched["managed_copy_law_checks"]}
    assert unsafe_check_by_id["core_surrender_blocked"]["status"] == "blocked"
    assert mismatched["writes_receipts"] is False
    assert not preflight_path.exists()

    law_violation_cases = (
        ("tenant_identity", "tenant_name", "", "tenant_identity_named", "tenant_identity_name_required"),
        (
            "tenant_identity",
            "tenant_admin_actor",
            "",
            "tenant_admin_declared",
            "tenant_admin_actor_required",
        ),
        (
            "tenant_policy",
            "privacy_weak_pooling_allowed",
            True,
            "privacy_weak_pooling_blocked",
            "privacy_weak_pooling_must_remain_blocked",
        ),
        *(
            (
                "isolation_profile",
                domain,
                "shared",
                f"{domain}_isolated",
                f"{domain}_must_be_isolated",
            )
            for domain in (
                "tenant_data",
                "tenant_memory",
                "tenant_receipts",
                "tenant_connectors",
                "tenant_capability_packs",
                "tenant_policy",
                "support_operator_authority",
            )
        ),
        (
            "capability_lineage",
            "base_pack",
            "",
            "capability_base_lineage_declared",
            "capability_base_lineage_required",
        ),
        (
            "capability_lineage",
            "customization_layer",
            "fork",
            "customization_layer_tenant_scoped",
            "customization_layer_must_be_tenant_scoped",
        ),
        (
            "safe_delta_policy",
            "raw_private_pooling_allowed",
            True,
            "raw_private_pooling_blocked",
            "raw_private_pooling_must_remain_blocked",
        ),
        (
            "safe_delta_policy",
            "operator_review_required",
            False,
            "safe_delta_operator_review_required",
            "safe_delta_operator_review_required",
        ),
        (
            "support_boundary",
            "support_access_default",
            "allowed",
            "support_default_denied",
            "support_access_default_must_be_denied",
        ),
        (
            "support_boundary",
            "time_bound",
            False,
            "support_time_bounded",
            "support_access_must_be_time_bounded",
        ),
        (
            "decommission_policy",
            "export_required",
            False,
            "decommission_export_required",
            "decommission_export_must_be_required",
        ),
        (
            "decommission_policy",
            "proof_receipts_required",
            False,
            "decommission_proof_receipts_required",
            "decommission_proof_receipts_must_be_required",
        ),
    )
    for section, field, unsafe_value, check_id, blocker in law_violation_cases:
        unsafe_payload = json.loads(json.dumps(preflight_payload))
        unsafe_payload[section][field] = unsafe_value
        unsafe = client.post("/managed-copies/copy-creation-preflight", json=unsafe_payload).json()
        unsafe_check_by_id = {check["id"]: check for check in unsafe["managed_copy_law_checks"]}
        assert unsafe["ok"] is False
        assert unsafe["error"] == "copy_preflight_contract_not_ready"
        assert blocker in unsafe["blockers"]
        assert unsafe["managed_copy_law_ready"] is False
        assert unsafe_check_by_id[check_id]["status"] == "blocked"
        assert unsafe["writes_receipts"] is False
        assert not preflight_path.exists()

    wrong_fingerprint = client.post(
        "/managed-copies/copy-creation-preflight",
        json={
            **preflight_payload,
            "dry_run": False,
            "preflight_fingerprint": "0" * 64,
            "confirm_preflight_recording": True,
        },
    ).json()
    assert wrong_fingerprint["ok"] is False
    assert wrong_fingerprint["error"] == "copy_preflight_fingerprint_mismatch"
    assert wrong_fingerprint["writes_receipts"] is False
    assert not preflight_path.exists()

    recorded = client.post(
        "/managed-copies/copy-creation-preflight",
        json={
            **preflight_payload,
            "dry_run": False,
            "preflight_fingerprint": planned["preflight_fingerprint"],
            "confirm_preflight_recording": True,
        },
    ).json()

    assert recorded["ok"] is True
    assert recorded["status"] == "recorded"
    assert recorded["receipt_id"].startswith("managed_copy_preflight_")
    assert recorded["copy_preflight_recorded"] is True
    assert recorded["copy_plan_created"] is False
    assert recorded["copy_created"] is False
    assert recorded["writes_receipts"] is True
    assert recorded["writes_tenant_state"] is False
    assert recorded["grants_execution_authority"] is False
    assert recorded["grants_mutation_authority"] is False
    assert recorded["receipt"]["request_receipt_id"] == request_record["receipt_id"]
    assert recorded["receipt"]["managed_copy_law_ready"] is True
    assert recorded["receipt"]["managed_copy_law_ready_count"] == 19
    assert recorded["receipt"]["governance"]["request_payload_fingerprints_matched"] is True
    assert recorded["receipt"]["governance"]["managed_copy_law_checked"] is True
    assert recorded["receipt"]["governance"]["managed_copy_law_ready"] is True
    assert recorded["receipt"]["governance"]["contains_raw_tenant_payload"] is False
    assert recorded["next_smallest_truthful_gap"] == "stage18_copy_creation_plan_process"

    receipt_text = preflight_path.read_text(encoding="utf-8")
    assert len(receipt_text.splitlines()) == 1
    assert raw_tenant_id not in receipt_text
    assert raw_tenant_name not in receipt_text
    assert raw_admin not in receipt_text

    readback = client.get("/managed-copies/copy-creation-preflights").json()
    assert readback["status"] == "ready"
    assert readback["valid_count"] == 1
    assert readback["latest_valid_receipt_id"] == recorded["receipt_id"]
    assert readback["copy_preflight_recording_ready"] is True
    assert readback["writes_receipts"] is False
    assert readback["writes_tenant_state"] is False
    assert readback["next_smallest_truthful_gap"] == "stage18_copy_creation_plan_process"

    status = client.get("/managed-copies/status").json()
    creation = next(item for item in status["deliverables"] if item["id"] == "copy_creation_process")
    assert creation["status"] == "preflight_recorded"
    assert status["copy_preflight_recorded"] is True
    assert status["copy_preflight_receipt_id"] == recorded["receipt_id"]
    assert status["copy_preflight_request_receipt_aligned"] is True
    assert status["next_smallest_truthful_gap"] == "stage18_copy_creation_plan_process"

    contract = client.get("/managed-copies/copy-creation-contract").json()
    step_by_id = {item["id"]: item for item in contract["process_steps"]}
    assert step_by_id["preflight"]["status"] == "complete"
    assert step_by_id["plan"]["status"] == "enabled"
    assert contract["copy_preflight_recorded"] is True
    assert contract["copy_preflight_receipt_id"] == recorded["receipt_id"]
    assert contract["state_machine"]["current_state"] == "preflighted"
    assert contract["state_machine"]["enabled_transitions"] == ["create_plan"]

    duplicate = client.post(
        "/managed-copies/copy-creation-preflight",
        json={
            **preflight_payload,
            "dry_run": False,
            "preflight_fingerprint": planned["preflight_fingerprint"],
            "confirm_preflight_recording": True,
        },
    ).json()
    assert duplicate["status"] == "already_recorded"
    assert duplicate["receipt_id"] == recorded["receipt_id"]
    assert duplicate["writes_receipts"] is False
    assert len(preflight_path.read_text(encoding="utf-8").splitlines()) == 1

    foreign_preflight = json.loads(json.dumps(recorded["receipt"]))
    foreign_preflight["receipt_id"] = "managed_copy_preflight_foreign"
    foreign_preflight["preflight_fingerprint"] = "e" * 64
    foreign_preflight["request_fingerprint"] = "f" * 64
    with preflight_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(foreign_preflight) + "\n")

    aligned_status = client.get("/managed-copies/status").json()
    assert aligned_status["copy_preflight_recorded"] is True
    assert aligned_status["copy_preflight_receipt_id"] == recorded["receipt_id"]
    assert aligned_status["copy_preflight_request_receipt_aligned"] is True


def test_managed_copy_creation_plan_records_redacted_lineage_bound_receipt(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path.parent / "managed-copy-plan"
    actor = "stage18.copy-plan-recorder"
    decision_actor = "stage18.copy-plan-approver"
    raw_tenant_id = "customer-plan-private-id"
    raw_tenant_name = "Customer Plan Private Name"
    raw_admin = "customer.plan.admin@example.test"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps(
            {
                actor: [
                    "managed_copies.copy_creation.write",
                    "managed_copies.isolation_verification.write",
                    "managed_copies.safe_delta.write",
                ],
                decision_actor: ["approvals.decide"],
            }
        ),
    )

    from francis.economy.stage17_closure import record_stage17_operator_stage_closure_decision

    criteria = [{"id": f"criterion_{index}", "status": "ready", "blockers": []} for index in range(1, 7)]
    record_stage17_operator_stage_closure_decision(
        actor="test.stage17.operator",
        reason="validated Stage 17 closure fixture",
        decision="close_stage17",
        review={
            "status": "ready",
            "stage17_completion_review_ready": True,
            "criteria_ready_count": 6,
            "criteria_required_count": 6,
            "closure_matrix": {
                "kind": "plugin.capability_catalog.stage17_closure_matrix",
                "status": "ready_for_closure_review",
                "all_criteria_ready": True,
                "criteria": criteria,
                "source_readbacks": {"catalog_route": "/plugins/capabilities/catalog"},
            },
        },
    )
    request_payload = {
        "request_actor": actor,
        "tenant_id": raw_tenant_id,
        "tenant_identity": {"tenant_name": raw_tenant_name, "tenant_admin_actor": raw_admin},
        "tenant_policy": {
            "core_surrender_allowed": False,
            "privacy_weak_pooling_allowed": False,
        },
        "isolation_profile": {
            "tenant_data": "isolated",
            "tenant_memory": "isolated",
            "tenant_receipts": "isolated",
            "tenant_connectors": "isolated",
            "tenant_capability_packs": "isolated",
            "tenant_policy": "isolated",
            "support_operator_authority": "isolated",
        },
        "capability_lineage": {"base_pack": "francis-core", "customization_layer": "tenant"},
        "safe_delta_policy": {"raw_private_pooling_allowed": False, "operator_review_required": True},
        "support_boundary": {"support_access_default": "denied", "time_bound": True},
        "decommission_policy": {"export_required": True, "proof_receipts_required": True},
        "dry_run": True,
    }
    client = TestClient(create_app())
    request_plan = client.post("/managed-copies/copy-creation-request", json=request_payload).json()
    request_record = client.post(
        "/managed-copies/copy-creation-request",
        json={
            **request_payload,
            "dry_run": False,
            "dry_run_fingerprint": request_plan["dry_run_fingerprint"],
            "confirm_request_recording": True,
        },
    ).json()
    preflight_payload = {
        **request_payload,
        "request_receipt_id": request_record["receipt_id"],
        "dry_run": True,
    }
    preflight_plan = client.post("/managed-copies/copy-creation-preflight", json=preflight_payload).json()
    preflight_record = client.post(
        "/managed-copies/copy-creation-preflight",
        json={
            **preflight_payload,
            "dry_run": False,
            "preflight_fingerprint": preflight_plan["preflight_fingerprint"],
            "confirm_preflight_recording": True,
        },
    ).json()
    plan_payload = {
        "request_actor": actor,
        "request_receipt_id": request_record["receipt_id"],
        "preflight_receipt_id": preflight_record["receipt_id"],
        "operator_note": f"do not persist {raw_tenant_name} or {raw_admin}",
        "dry_run": True,
    }

    planned = client.post("/managed-copies/copy-creation-plan", json=plan_payload).json()

    assert planned["ok"] is True
    assert planned["kind"] == "francis.stage18.managed_copies.copy_creation_plan"
    assert planned["status"] == "copy_plan_ready"
    assert planned["request_receipt_id"] == request_record["receipt_id"]
    assert planned["preflight_receipt_id"] == preflight_record["receipt_id"]
    assert planned["request_and_preflight_receipts_aligned"] is True
    assert planned["plan_contract_ready"] is True
    assert len(planned["plan_fingerprint"]) == 64
    assert planned["copy_plan_recorded"] is False
    assert planned["copy_created"] is False
    assert planned["writes_receipts"] is False
    assert planned["writes_tenant_state"] is False
    assert [step["id"] for step in planned["plan_steps"]] == [
        "establish_copy_identity",
        "apply_tenant_policy",
        "prepare_isolation_boundaries",
        "bind_capability_lineage",
        "configure_safe_delta_policy",
        "configure_support_boundary",
        "prepare_decommission_policy",
    ]
    assert all(step["status"] == "planned" for step in planned["plan_steps"])
    assert all(step["requires_governed_approval"] is True for step in planned["plan_steps"])
    planned_text = json.dumps(planned)
    assert raw_tenant_id not in planned_text
    assert raw_tenant_name not in planned_text
    assert raw_admin not in planned_text

    plan_path = data_root / "logs" / "managed_copies" / "copy_plans.jsonl"
    assert not plan_path.exists()

    mismatched = client.post(
        "/managed-copies/copy-creation-plan",
        json={**plan_payload, "preflight_receipt_id": "managed_copy_preflight_wrong"},
    ).json()
    assert mismatched["ok"] is False
    assert mismatched["error"] == "copy_plan_contract_not_ready"
    assert "copy_preflight_receipt_id_mismatch" in mismatched["blockers"]
    assert mismatched["writes_receipts"] is False
    assert not plan_path.exists()

    wrong_fingerprint = client.post(
        "/managed-copies/copy-creation-plan",
        json={
            **plan_payload,
            "dry_run": False,
            "plan_fingerprint": "0" * 64,
            "confirm_plan_recording": True,
        },
    ).json()
    assert wrong_fingerprint["ok"] is False
    assert wrong_fingerprint["error"] == "copy_plan_fingerprint_mismatch"
    assert wrong_fingerprint["writes_receipts"] is False
    assert not plan_path.exists()

    recorded = client.post(
        "/managed-copies/copy-creation-plan",
        json={
            **plan_payload,
            "dry_run": False,
            "plan_fingerprint": planned["plan_fingerprint"],
            "confirm_plan_recording": True,
        },
    ).json()

    assert recorded["ok"] is True
    assert recorded["status"] == "recorded"
    assert recorded["receipt_id"].startswith("managed_copy_creation_plan_")
    assert recorded["copy_plan_recorded"] is True
    assert recorded["operator_approval_recorded"] is False
    assert recorded["copy_created"] is False
    assert recorded["writes_receipts"] is True
    assert recorded["writes_tenant_state"] is False
    assert recorded["grants_execution_authority"] is False
    assert recorded["grants_mutation_authority"] is False
    assert recorded["receipt"]["request_receipt_id"] == request_record["receipt_id"]
    assert recorded["receipt"]["preflight_receipt_id"] == preflight_record["receipt_id"]
    receipt_governance = recorded["receipt"]["governance"]
    assert receipt_governance["request_and_preflight_receipts_aligned"] is True
    assert receipt_governance["operator_approval_required_before_provisioning"] is True
    assert receipt_governance["contains_raw_tenant_payload"] is False
    assert receipt_governance["does_not_provision_copy"] is True
    assert recorded["next_smallest_truthful_gap"] == "stage18_copy_creation_approval_request"

    receipt_text = plan_path.read_text(encoding="utf-8")
    assert len(receipt_text.splitlines()) == 1
    assert raw_tenant_id not in receipt_text
    assert raw_tenant_name not in receipt_text
    assert raw_admin not in receipt_text

    readback = client.get("/managed-copies/copy-creation-plans").json()
    assert readback["status"] == "ready"
    assert readback["valid_count"] == 1
    assert readback["latest_valid_receipt_id"] == recorded["receipt_id"]
    assert readback["copy_plan_recording_ready"] is True
    assert readback["writes_receipts"] is False
    assert readback["writes_tenant_state"] is False
    assert readback["next_smallest_truthful_gap"] == "stage18_copy_creation_approval_request"

    status = client.get("/managed-copies/status").json()
    creation = next(item for item in status["deliverables"] if item["id"] == "copy_creation_process")
    assert creation["status"] == "plan_recorded"
    assert status["copy_plan_recorded"] is True
    assert status["copy_plan_receipt_id"] == recorded["receipt_id"]
    assert status["copy_plan_preflight_receipt_aligned"] is True
    assert status["next_smallest_truthful_gap"] == "stage18_copy_creation_approval_request"

    contract = client.get("/managed-copies/copy-creation-contract").json()
    step_by_id = {item["id"]: item for item in contract["process_steps"]}
    assert step_by_id["plan"]["status"] == "complete"
    assert step_by_id["approve"]["status"] == "enabled"
    assert contract["copy_plan_recorded"] is True
    assert contract["copy_plan_receipt_id"] == recorded["receipt_id"]
    assert contract["state_machine"]["current_state"] == "planned"
    assert contract["state_machine"]["enabled_transitions"] == ["request_approval"]

    duplicate = client.post(
        "/managed-copies/copy-creation-plan",
        json={
            **plan_payload,
            "dry_run": False,
            "plan_fingerprint": planned["plan_fingerprint"],
            "confirm_plan_recording": True,
        },
    ).json()
    assert duplicate["status"] == "already_recorded"
    assert duplicate["receipt_id"] == recorded["receipt_id"]
    assert duplicate["writes_receipts"] is False
    assert len(plan_path.read_text(encoding="utf-8").splitlines()) == 1

    foreign_plan = json.loads(json.dumps(recorded["receipt"]))
    foreign_plan["receipt_id"] = "managed_copy_creation_plan_foreign"
    foreign_plan["plan_fingerprint"] = "e" * 64
    foreign_plan["preflight_receipt_id"] = "managed_copy_preflight_foreign"
    foreign_plan["preflight_fingerprint"] = "f" * 64
    with plan_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(foreign_plan) + "\n")

    mixed_readback = client.get("/managed-copies/copy-creation-plans").json()
    assert mixed_readback["count"] == 2
    assert mixed_readback["valid_count"] == 1
    assert mixed_readback["latest_receipt_valid"] is False

    aligned_status = client.get("/managed-copies/status").json()
    assert aligned_status["copy_plan_recorded"] is True
    assert aligned_status["copy_plan_receipt_id"] == recorded["receipt_id"]
    assert aligned_status["copy_plan_preflight_receipt_aligned"] is True

    approval_payload = {
        "request_actor": actor,
        "plan_receipt_id": recorded["receipt_id"],
        "operator_note": f"do not persist {raw_tenant_name} or {raw_admin}",
        "dry_run": True,
    }
    approval_plan = client.post(
        "/managed-copies/copy-creation-approval-request",
        json=approval_payload,
    ).json()

    assert approval_plan["ok"] is True
    assert approval_plan["status"] == "approval_request_ready"
    assert approval_plan["plan_receipt_id"] == recorded["receipt_id"]
    assert approval_plan["plan_receipt_aligned"] is True
    assert approval_plan["approval_request_contract_ready"] is True
    assert len(approval_plan["approval_action_fingerprint"]) == 64
    assert approval_plan["exact_action"]["requested_action"] == "managed_copies.provision_copy"
    assert approval_plan["exact_action"]["requested_transition"] == "planned_to_provisioning"
    assert approval_plan["exact_action"]["future_effects"] == {
        "creates_isolated_copy_state": True,
        "writes_tenant_state": True,
        "writes_registry": True,
        "writes_provisioning_receipt": True,
        "starts_runtime": False,
    }
    assert approval_plan["copy_approval_request_recorded"] is False
    assert approval_plan["writes_approval_request"] is False
    assert approval_plan["writes_receipts"] is False
    assert approval_plan["writes_tenant_state"] is False
    assert approval_plan["consumes_approval"] is False
    assert raw_tenant_id not in json.dumps(approval_plan)
    assert raw_tenant_name not in json.dumps(approval_plan)
    assert raw_admin not in json.dumps(approval_plan)

    approvals_root = data_root / "approvals"
    assert not approvals_root.exists()

    mismatched_approval = client.post(
        "/managed-copies/copy-creation-approval-request",
        json={**approval_payload, "plan_receipt_id": "managed_copy_creation_plan_wrong"},
    ).json()
    assert mismatched_approval["ok"] is False
    assert mismatched_approval["error"] == "copy_approval_request_contract_not_ready"
    assert "copy_creation_plan_receipt_id_mismatch" in mismatched_approval["blockers"]
    assert mismatched_approval["writes_approval_request"] is False
    assert not approvals_root.exists()

    wrong_approval_fingerprint = client.post(
        "/managed-copies/copy-creation-approval-request",
        json={
            **approval_payload,
            "dry_run": False,
            "approval_action_fingerprint": "0" * 64,
            "confirm_approval_request": True,
        },
    ).json()
    assert wrong_approval_fingerprint["ok"] is False
    assert wrong_approval_fingerprint["error"] == "copy_approval_request_fingerprint_mismatch"
    assert wrong_approval_fingerprint["writes_approval_request"] is False
    assert not approvals_root.exists()

    approval_record = client.post(
        "/managed-copies/copy-creation-approval-request",
        json={
            **approval_payload,
            "dry_run": False,
            "approval_action_fingerprint": approval_plan["approval_action_fingerprint"],
            "confirm_approval_request": True,
        },
    ).json()

    assert approval_record["ok"] is True
    assert approval_record["status"] == "approval_pending"
    assert approval_record["copy_approval_request_recorded"] is True
    assert approval_record["copy_approval_status"] == "pending"
    assert approval_record["operator_approval_recorded"] is False
    assert approval_record["operator_approval_consumed"] is False
    assert approval_record["writes_approval_request"] is True
    assert approval_record["writes_receipts"] is False
    assert approval_record["writes_tenant_state"] is False
    assert approval_record["copy_created"] is False
    assert approval_record["consumes_approval"] is False
    assert approval_record["grants_execution_authority"] is False
    assert approval_record["grants_mutation_authority"] is False
    assert approval_record["next_smallest_truthful_gap"] == "stage18_copy_creation_approval_decision"
    approval_id = approval_record["copy_approval_id"]
    pending_path = approvals_root / "pending" / f"{approval_id}.json"
    assert pending_path.exists()
    pending_text = pending_path.read_text(encoding="utf-8")
    assert raw_tenant_id not in pending_text
    assert raw_tenant_name not in pending_text
    assert raw_admin not in pending_text

    approval_readback = client.get("/managed-copies/copy-creation-approval-requests").json()
    assert approval_readback["status"] == "ready"
    assert approval_readback["valid_count"] == 1
    assert approval_readback["latest_valid_approval_id"] == approval_id
    assert approval_readback["latest_valid_approval_status"] == "pending"
    assert approval_readback["writes_approval_requests"] is False
    assert approval_readback["writes_tenant_state"] is False
    assert approval_readback["consumes_approval"] is False
    assert approval_readback["next_smallest_truthful_gap"] == "stage18_copy_creation_approval_decision"

    pending_status = client.get("/managed-copies/status").json()
    creation = next(item for item in pending_status["deliverables"] if item["id"] == "copy_creation_process")
    assert creation["status"] == "approval_pending"
    assert pending_status["copy_approval_request_recorded"] is True
    assert pending_status["copy_approval_id"] == approval_id
    assert pending_status["copy_approval_status"] == "pending"
    assert pending_status["copy_approval_plan_receipt_aligned"] is True
    assert pending_status["next_smallest_truthful_gap"] == "stage18_copy_creation_approval_decision"

    pending_contract = client.get("/managed-copies/copy-creation-contract").json()
    pending_step_by_id = {item["id"]: item for item in pending_contract["process_steps"]}
    assert pending_step_by_id["approve"]["status"] == "pending"
    assert pending_contract["state_machine"]["current_state"] == "approval_pending"
    assert pending_contract["state_machine"]["enabled_transitions"] == []

    duplicate_approval = client.post(
        "/managed-copies/copy-creation-approval-request",
        json={
            **approval_payload,
            "dry_run": False,
            "approval_action_fingerprint": approval_plan["approval_action_fingerprint"],
            "confirm_approval_request": True,
        },
    ).json()
    assert duplicate_approval["status"] == "already_requested"
    assert duplicate_approval["copy_approval_id"] == approval_id
    assert duplicate_approval["writes_approval_request"] is False

    decision = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": decision_actor,
            "reason": "validated exact Stage 18 plan envelope",
        },
    ).json()
    assert decision["ok"] is True
    assert decision["status"] == "approved"
    assert not pending_path.exists()
    assert (approvals_root / "approved" / f"{approval_id}.json").exists()

    approved_status = client.get("/managed-copies/status").json()
    assert approved_status["copy_approval_request_recorded"] is True
    assert approved_status["copy_approval_id"] == approval_id
    assert approved_status["copy_approval_status"] == "approved"
    assert approved_status["copy_creation_enabled"] is False
    assert approved_status["copy_provisioning_enabled"] is True
    assert approved_status["copy_provisioned"] is False
    assert approved_status["writes_tenant_state"] is False
    assert approved_status["next_smallest_truthful_gap"] == "stage18_copy_creation_provision"

    approved_contract = client.get("/managed-copies/copy-creation-contract").json()
    approved_step_by_id = {item["id"]: item for item in approved_contract["process_steps"]}
    assert approved_step_by_id["approve"]["status"] == "approved"
    assert approved_step_by_id["provision"]["status"] == "enabled"
    assert approved_contract["state_machine"]["current_state"] == "approved"
    assert approved_contract["state_machine"]["enabled_transitions"] == ["provision"]

    provision_payload = {
        **request_payload,
        "plan_receipt_id": recorded["receipt_id"],
        "approval_id": approval_id,
        "dry_run": True,
    }
    provision_plan = client.post(
        "/managed-copies/copy-creation-provision",
        json=provision_payload,
    ).json()

    assert provision_plan["ok"] is True
    assert provision_plan["status"] == "provision_ready"
    assert provision_plan["provision_contract_ready"] is True
    assert provision_plan["approval_exact_action_aligned"] is True
    assert provision_plan["approval_status"] == "approved"
    assert len(provision_plan["provision_fingerprint"]) == 64
    assert provision_plan["copy_provisioned"] is False
    assert provision_plan["writes_tenant_state"] is False
    assert provision_plan["writes_registry"] is False
    assert provision_plan["writes_receipts"] is False
    assert provision_plan["starts_runtime"] is False
    assert provision_plan["grants_execution_authority"] is False
    assert provision_plan["grants_mutation_authority"] is False
    provision_plan_text = json.dumps(provision_plan)
    assert raw_tenant_id not in provision_plan_text
    assert raw_tenant_name not in provision_plan_text
    assert raw_admin not in provision_plan_text

    tenant_key = provision_plan["tenant_key"]
    tenant_root = data_root / "managed_copies" / "tenants" / tenant_key
    assert not tenant_root.exists()

    mismatched_provision = client.post(
        "/managed-copies/copy-creation-provision",
        json={
            **provision_payload,
            "tenant_policy": {
                "core_surrender_allowed": True,
                "privacy_weak_pooling_allowed": False,
            },
        },
    ).json()
    assert mismatched_provision["ok"] is False
    assert mismatched_provision["error"] == "copy_provision_contract_not_ready"
    assert "tenant_policy_fingerprint_mismatch" in mismatched_provision["blockers"]
    assert mismatched_provision["writes_tenant_state"] is False
    assert not tenant_root.exists()

    wrong_provision_fingerprint = client.post(
        "/managed-copies/copy-creation-provision",
        json={
            **provision_payload,
            "dry_run": False,
            "provision_fingerprint": "0" * 64,
            "confirm_provisioning": True,
        },
    ).json()
    assert wrong_provision_fingerprint["ok"] is False
    assert wrong_provision_fingerprint["error"] == "copy_provision_fingerprint_mismatch"
    assert wrong_provision_fingerprint["writes_tenant_state"] is False
    assert not tenant_root.exists()

    provisioned = client.post(
        "/managed-copies/copy-creation-provision",
        json={
            **provision_payload,
            "dry_run": False,
            "provision_fingerprint": provision_plan["provision_fingerprint"],
            "confirm_provisioning": True,
        },
    ).json()

    assert provisioned["ok"] is True, (provisioned["status"], provisioned["error"])
    assert provisioned["status"] == "provisioned"
    assert provisioned["copy_provisioned"] is True
    assert provisioned["copy_created"] is True
    assert provisioned["operator_approval_consumed"] is True
    assert provisioned["single_use_enforced"] is True
    assert provisioned["writes_tenant_state"] is True
    assert provisioned["writes_registry"] is True
    assert provisioned["writes_receipts"] is True
    assert provisioned["consumes_approval"] is True
    assert provisioned["starts_runtime"] is False
    assert provisioned["receipt"]["status"] == "provisioned_unverified"
    assert provisioned["receipt"]["registry_written"] is True
    assert provisioned["receipt"]["isolation_verified"] is False
    assert provisioned["next_smallest_truthful_gap"] == "stage18_copy_isolation_verification"

    expected_domains = {
        "data",
        "memory",
        "receipts",
        "connectors",
        "capability_packs",
        "policy",
        "support",
    }
    assert tenant_root.exists()
    assert expected_domains <= {path.name for path in tenant_root.iterdir() if path.is_dir()}
    tenant_config_path = tenant_root / "config" / "managed_copy.json"
    tenant_config_text = tenant_config_path.read_text(encoding="utf-8")
    assert raw_tenant_id in tenant_config_text
    assert raw_tenant_name in tenant_config_text
    assert raw_admin in tenant_config_text

    provisioning_receipt_path = tenant_root / "receipts" / "provisioning.json"
    consumption_receipt_path = tenant_root / "receipts" / "approval_consumption.json"
    registry_path = data_root / "managed_copies" / "registry.json"
    for redacted_path in (provisioning_receipt_path, consumption_receipt_path, registry_path):
        redacted_text = redacted_path.read_text(encoding="utf-8")
        assert raw_tenant_id not in redacted_text
        assert raw_tenant_name not in redacted_text
        assert raw_admin not in redacted_text

    consumption_receipt = json.loads(consumption_receipt_path.read_text(encoding="utf-8"))
    assert consumption_receipt["approval_id"] == approval_id
    assert consumption_receipt["approval_consumed"] is True
    assert consumption_receipt["single_use_enforced"] is True
    assert consumption_receipt["runtime_started"] is False

    pending_receipt = json.loads(provisioning_receipt_path.read_text(encoding="utf-8"))
    pending_receipt["status"] = "tenant_published_pending_registry"
    pending_receipt["registry_written"] = False
    pending_receipt["governance"]["registry_entry_written"] = False
    provisioning_receipt_path.write_text(json.dumps(pending_receipt), encoding="utf-8")
    pending_manifest_path = tenant_root / "manifest.json"
    pending_manifest = json.loads(pending_manifest_path.read_text(encoding="utf-8"))
    pending_manifest["status"] = "tenant_published_pending_registry"
    pending_manifest["registry_written"] = False
    pending_manifest_path.write_text(json.dumps(pending_manifest), encoding="utf-8")
    registry_path.unlink()

    recovery_readback = client.get("/managed-copies/copy-creation-provisions").json()
    assert recovery_readback["status"] == "recovery_required"
    assert recovery_readback["valid_count"] == 0
    assert recovery_readback["pending_recovery_count"] == 1
    assert recovery_readback["next_smallest_truthful_gap"] == "stage18_copy_provision_recovery"
    recovery_status = client.get("/managed-copies/status").json()
    assert recovery_status["copy_provisioned"] is False
    assert recovery_status["copy_provision_recovery_required"] is True
    assert recovery_status["copy_provision_approval_aligned"] is True
    assert recovery_status["next_smallest_truthful_gap"] == "stage18_copy_provision_recovery"
    recovery_contract = client.get("/managed-copies/copy-creation-contract").json()
    recovery_step_by_id = {item["id"]: item for item in recovery_contract["process_steps"]}
    assert recovery_step_by_id["provision"]["status"] == "recovery_required"
    assert recovery_contract["state_machine"]["current_state"] == "provision_recovery_required"
    assert recovery_contract["state_machine"]["enabled_transitions"] == ["recover_provision"]

    recovered_provision = client.post(
        "/managed-copies/copy-creation-provision",
        json={
            **provision_payload,
            "dry_run": False,
            "provision_fingerprint": provision_plan["provision_fingerprint"],
            "confirm_provisioning": True,
        },
    ).json()
    assert recovered_provision["ok"] is True
    assert recovered_provision["status"] == "provision_recovered"
    assert recovered_provision["writes_tenant_state"] is False
    assert recovered_provision["writes_registry"] is True
    assert recovered_provision["writes_receipts"] is True
    assert recovered_provision["consumes_approval"] is False
    assert registry_path.exists()
    recovered_receipt = json.loads(provisioning_receipt_path.read_text(encoding="utf-8"))
    assert recovered_receipt["status"] == "provisioned_unverified"
    assert recovered_receipt["registry_written"] is True
    assert recovered_receipt["governance"]["registry_entry_written"] is True

    provision_readback = client.get("/managed-copies/copy-creation-provisions").json()
    assert provision_readback["status"] == "ready"
    assert provision_readback["valid_count"] == 1
    assert provision_readback["pending_recovery_count"] == 0
    assert provision_readback["latest_valid_receipt_id"] == provisioned["receipt_id"]
    assert provision_readback["copy_provisioned"] is True
    provision_readback_text = json.dumps(provision_readback)
    assert raw_tenant_id not in provision_readback_text
    assert raw_tenant_name not in provision_readback_text
    assert raw_admin not in provision_readback_text

    duplicate_provision = client.post(
        "/managed-copies/copy-creation-provision",
        json={
            **provision_payload,
            "dry_run": False,
            "provision_fingerprint": provision_plan["provision_fingerprint"],
            "confirm_provisioning": True,
        },
    ).json()
    assert duplicate_provision["ok"] is True
    assert duplicate_provision["status"] == "already_provisioned"
    assert duplicate_provision["receipt_id"] == provisioned["receipt_id"]
    assert duplicate_provision["writes_tenant_state"] is False
    assert duplicate_provision["writes_registry"] is False
    assert duplicate_provision["writes_receipts"] is False
    assert duplicate_provision["consumes_approval"] is False

    provisioned_status = client.get("/managed-copies/status").json()
    creation = next(item for item in provisioned_status["deliverables"] if item["id"] == "copy_creation_process")
    assert creation["status"] == "provisioned_unverified"
    assert provisioned_status["copy_provisioning_enabled"] is False
    assert provisioned_status["copy_provisioned"] is True
    assert provisioned_status["copy_provision_recovery_required"] is False
    assert provisioned_status["copy_provision_approval_aligned"] is True
    assert provisioned_status["copy_provision_receipt_id"] == provisioned["receipt_id"]
    assert provisioned_status["provisioned_copy_id"] == provisioned["copy_id"]
    assert provisioned_status["copy_provision_approval_aligned"] is True
    assert provisioned_status["next_smallest_truthful_gap"] == "stage18_copy_isolation_verification"

    provisioned_contract = client.get("/managed-copies/copy-creation-contract").json()
    provisioned_step_by_id = {item["id"]: item for item in provisioned_contract["process_steps"]}
    assert provisioned_step_by_id["provision"]["status"] == "complete"
    assert provisioned_step_by_id["verify"]["status"] == "enabled"
    assert provisioned_contract["state_machine"]["current_state"] == "provisioned_unverified"
    assert provisioned_contract["state_machine"]["enabled_transitions"] == ["verify_isolation"]

    isolation_payload = {
        "request_actor": actor,
        "copy_id": provisioned["copy_id"],
        "provisioning_receipt_id": provisioned["receipt_id"],
        "domains": [
            "tenant_data",
            "tenant_memory",
            "tenant_receipts",
            "tenant_connectors",
            "tenant_capability_packs",
            "tenant_policy",
            "support_operator_authority",
        ],
        "dry_run": True,
    }
    isolation_plan = client.post(
        "/managed-copies/isolation-verification",
        json=isolation_payload,
    ).json()
    assert isolation_plan["ok"] is True
    assert isolation_plan["status"] == "structural_isolation_verification_ready"
    assert isolation_plan["structural_isolation_ready"] is True
    assert isolation_plan["structural_isolation_verified"] is False
    assert isolation_plan["full_customer_isolation_verified"] is False
    assert isolation_plan["filesystem_acl_isolation_verified"] is False
    assert isolation_plan["runtime_access_boundary_verified"] is False
    assert isolation_plan["cross_tenant_denial_executed"] is False
    assert isolation_plan["verified_domain_count"] == 7
    assert isolation_plan["required_domain_count"] == 7
    assert isolation_plan["verified_artifact_count"] == isolation_plan["required_artifact_count"]
    assert all(check["status"] == "verified" for check in isolation_plan["domain_checks"])
    assert all(check["status"] == "verified" for check in isolation_plan["artifact_checks"])
    assert len(isolation_plan["verification_fingerprint"]) == 64
    assert isolation_plan["writes_receipts"] is False
    assert isolation_plan["writes_tenant_state"] is False
    assert isolation_plan["starts_runtime"] is False
    assert isolation_plan["next_smallest_truthful_gap"] == "stage18_copy_isolation_verification"

    isolation_receipt_path = tenant_root / "receipts" / "isolation_verification.json"
    assert not isolation_receipt_path.exists()
    wrong_isolation_fingerprint = client.post(
        "/managed-copies/isolation-verification",
        json={
            **isolation_payload,
            "dry_run": False,
            "verification_fingerprint": "0" * 64,
            "confirm_isolation_verification": True,
        },
    ).json()
    assert wrong_isolation_fingerprint["ok"] is False
    assert wrong_isolation_fingerprint["error"] == "isolation_verification_fingerprint_mismatch"
    assert wrong_isolation_fingerprint["writes_receipts"] is False
    assert not isolation_receipt_path.exists()

    connectors_path = tenant_root / "connectors"
    displaced_connectors_path = tenant_root / "connectors-displaced"
    connectors_path.rename(displaced_connectors_path)
    drifted_plan = client.post(
        "/managed-copies/isolation-verification",
        json=isolation_payload,
    ).json()
    assert drifted_plan["ok"] is False
    assert drifted_plan["error"] == "isolation_verification_contract_not_ready"
    assert "tenant_connectors_directory_missing" in drifted_plan["blockers"]
    connectors_check = {check["id"]: check for check in drifted_plan["domain_checks"]}
    assert connectors_check["tenant_connectors"]["status"] == "blocked"
    assert drifted_plan["writes_receipts"] is False
    displaced_connectors_path.rename(connectors_path)

    isolation_recorded = client.post(
        "/managed-copies/isolation-verification",
        json={
            **isolation_payload,
            "dry_run": False,
            "verification_fingerprint": isolation_plan["verification_fingerprint"],
            "confirm_isolation_verification": True,
        },
    ).json()
    assert isolation_recorded["ok"] is True, (
        isolation_recorded["status"],
        isolation_recorded["error"],
        isolation_recorded["dry_run_confirmation"],
    )
    assert isolation_recorded["status"] == "structural_isolation_verified"
    assert isolation_recorded["structural_isolation_verified"] is True
    assert isolation_recorded["isolation_verified"] is False
    assert isolation_recorded["full_customer_isolation_verified"] is False
    assert isolation_recorded["writes_receipts"] is True
    assert isolation_recorded["writes_tenant_state"] is False
    assert isolation_recorded["starts_runtime"] is False
    assert isolation_recorded["grants_execution_authority"] is False
    assert isolation_recorded["grants_mutation_authority"] is False
    assert isolation_recorded["next_smallest_truthful_gap"] == ("stage18_copy_isolation_runtime_access_boundary")
    assert isolation_receipt_path.exists()
    isolation_receipt_text = isolation_receipt_path.read_text(encoding="utf-8")
    assert raw_tenant_id not in isolation_receipt_text
    assert raw_tenant_name not in isolation_receipt_text
    assert raw_admin not in isolation_receipt_text

    isolation_readback = client.get("/managed-copies/isolation-verifications").json()
    assert isolation_readback["status"] == "ready"
    assert isolation_readback["valid_count"] == 1
    assert isolation_readback["live_aligned_count"] == 1
    assert isolation_readback["structural_isolation_verified"] is True
    assert isolation_readback["full_customer_isolation_verified"] is False
    assert isolation_readback["latest_valid_receipt_id"] == isolation_recorded["receipt_id"]
    assert isolation_readback["next_smallest_truthful_gap"] == ("stage18_copy_isolation_runtime_access_boundary")

    structurally_verified_status = client.get("/managed-copies/status").json()
    creation = next(
        item for item in structurally_verified_status["deliverables"] if item["id"] == "copy_creation_process"
    )
    isolation_deliverable = next(
        item for item in structurally_verified_status["deliverables"] if item["id"] == "isolation_rules"
    )
    assert creation["status"] == "provisioned_structurally_verified"
    assert isolation_deliverable["status"] == "structural_verification_recorded"
    assert structurally_verified_status["copy_structural_isolation_verified"] is True
    assert structurally_verified_status["copy_full_customer_isolation_verified"] is False
    assert structurally_verified_status["copy_isolation_drift_detected"] is False
    assert structurally_verified_status["copy_isolation_receipt_id"] == isolation_recorded["receipt_id"]
    assert structurally_verified_status["next_smallest_truthful_gap"] == (
        "stage18_copy_isolation_runtime_access_boundary"
    )

    structurally_verified_contract = client.get("/managed-copies/copy-creation-contract").json()
    verified_step_by_id = {item["id"]: item for item in structurally_verified_contract["process_steps"]}
    assert verified_step_by_id["verify"]["status"] == "structural_complete"
    assert structurally_verified_contract["state_machine"]["current_state"] == "structurally_verified"
    assert structurally_verified_contract["state_machine"]["enabled_transitions"] == []

    policy_path = tenant_root / "policy"
    displaced_policy_path = tenant_root / "policy-displaced"
    policy_path.rename(displaced_policy_path)
    drifted_status = client.get("/managed-copies/status").json()
    assert drifted_status["copy_structural_isolation_verified"] is False
    assert drifted_status["copy_isolation_drift_detected"] is True
    assert drifted_status["next_smallest_truthful_gap"] == "stage18_copy_isolation_reverification"
    drifted_readback = client.get("/managed-copies/isolation-verifications").json()
    assert drifted_readback["status"] == "drift_detected"
    assert drifted_readback["live_aligned_count"] == 0
    assert "tenant_policy_directory_missing" in drifted_readback["latest_valid_receipt"]["live_blockers"]
    displaced_policy_path.rename(policy_path)

    restored_status = client.get("/managed-copies/status").json()
    assert restored_status["copy_structural_isolation_verified"] is True
    assert restored_status["copy_isolation_drift_detected"] is False

    safe_delta_payload = {
        "request_actor": actor,
        "copy_id": provisioned["copy_id"],
        "provisioning_receipt_id": provisioned["receipt_id"],
        "isolation_verification_receipt_id": isolation_recorded["receipt_id"],
        "signal_class": "quality_gate_learning",
        "direction": "export",
        "candidate": {
            "signal_fingerprint": "1" * 64,
            "summary_fingerprint": "2" * 64,
            "lineage_fingerprint": "3" * 64,
            "source_record_count": 12,
            "contains_raw_private_data": False,
            "contains_tenant_identifiers": False,
            "redaction_review_complete": True,
            "abstraction_level": "class_level",
            "retention_class": "review_receipt_only",
        },
        "dry_run": True,
    }
    safe_delta_plan = client.post("/managed-copies/safe-delta-review", json=safe_delta_payload).json()
    assert safe_delta_plan["ok"] is True
    assert safe_delta_plan["status"] == "safe_delta_review_ready"
    assert safe_delta_plan["review_contract_ready"] is True
    assert safe_delta_plan["signal_allowed_by_contract"] is True
    assert safe_delta_plan["candidate_unknown_field_count"] == 0
    assert all(check["status"] == "ready" for check in safe_delta_plan["candidate_checks"])
    assert all(check["status"] == "ready" for check in safe_delta_plan["tenant_policy_checks"])
    assert len(safe_delta_plan["candidate_fingerprint"]) == 64
    assert len(safe_delta_plan["review_fingerprint"]) == 64
    assert safe_delta_plan["safe_delta_review_recorded"] is False
    assert safe_delta_plan["safe_delta_approved"] is False
    assert safe_delta_plan["safe_delta_exported"] is False
    assert safe_delta_plan["learning_written"] is False
    assert safe_delta_plan["writes_receipts"] is False

    raw_candidate_summary = "private customer summary must never persist"
    unsafe_safe_delta = client.post(
        "/managed-copies/safe-delta-review",
        json={
            **safe_delta_payload,
            "candidate": {
                **safe_delta_payload["candidate"],
                "summary": raw_candidate_summary,
            },
        },
    ).json()
    assert unsafe_safe_delta["ok"] is False
    assert unsafe_safe_delta["error"] == "safe_delta_review_contract_not_ready"
    assert "safe_delta_candidate_unknown_fields" in unsafe_safe_delta["blockers"]
    assert unsafe_safe_delta["candidate_unknown_field_count"] == 1
    assert unsafe_safe_delta["writes_receipts"] is False
    assert raw_candidate_summary not in json.dumps(unsafe_safe_delta)

    safe_delta_reviews_root = tenant_root / "receipts" / "sd"
    wrong_safe_delta_fingerprint = client.post(
        "/managed-copies/safe-delta-review",
        json={
            **safe_delta_payload,
            "dry_run": False,
            "review_fingerprint": "0" * 64,
            "confirm_safe_delta_review": True,
        },
    ).json()
    assert wrong_safe_delta_fingerprint["ok"] is False
    assert wrong_safe_delta_fingerprint["error"] == "safe_delta_review_fingerprint_mismatch"
    assert wrong_safe_delta_fingerprint["writes_receipts"] is False
    assert not safe_delta_reviews_root.exists()

    safe_delta_recorded = client.post(
        "/managed-copies/safe-delta-review",
        json={
            **safe_delta_payload,
            "dry_run": False,
            "review_fingerprint": safe_delta_plan["review_fingerprint"],
            "confirm_safe_delta_review": True,
        },
    ).json()
    assert safe_delta_recorded["ok"] is True, (
        safe_delta_recorded["status"],
        safe_delta_recorded["error"],
        safe_delta_recorded["dry_run_confirmation"],
    )
    assert safe_delta_recorded["status"] == "operator_approval_required"
    assert safe_delta_recorded["safe_delta_review_recorded"] is True
    assert safe_delta_recorded["safe_delta_approved"] is False
    assert safe_delta_recorded["safe_delta_exported"] is False
    assert safe_delta_recorded["learning_written"] is False
    assert safe_delta_recorded["writes_receipts"] is True
    assert safe_delta_recorded["writes_tenant_state"] is False
    assert safe_delta_recorded["grants_execution_authority"] is False
    assert safe_delta_recorded["grants_mutation_authority"] is False
    assert safe_delta_recorded["next_smallest_truthful_gap"] == "stage18_safe_delta_operator_approval"
    safe_delta_receipt_paths = list(safe_delta_reviews_root.glob("*.json"))
    assert len(safe_delta_receipt_paths) == 1
    safe_delta_receipt_text = safe_delta_receipt_paths[0].read_text(encoding="utf-8")
    assert raw_tenant_id not in safe_delta_receipt_text
    assert raw_tenant_name not in safe_delta_receipt_text
    assert raw_admin not in safe_delta_receipt_text
    assert raw_candidate_summary not in safe_delta_receipt_text

    safe_delta_readback = client.get(
        "/managed-copies/safe-delta-reviews",
        params={
            "copy_id": provisioned["copy_id"],
            "provisioning_receipt_id": provisioned["receipt_id"],
            "isolation_verification_receipt_id": isolation_recorded["receipt_id"],
        },
    ).json()
    assert safe_delta_readback["status"] == "operator_approval_required"
    assert safe_delta_readback["valid_count"] == 1
    assert safe_delta_readback["live_aligned_count"] == 1
    assert safe_delta_readback["latest_valid_receipt_id"] == safe_delta_recorded["receipt_id"]
    assert safe_delta_readback["safe_delta_review_recorded"] is True
    assert safe_delta_readback["safe_delta_approved"] is False
    assert safe_delta_readback["safe_delta_exported"] is False
    assert safe_delta_readback["learning_written"] is False
    assert safe_delta_readback["next_smallest_truthful_gap"] == "stage18_safe_delta_operator_approval"

    safe_delta_contract = client.get("/managed-copies/safe-delta-model-contract").json()
    assert safe_delta_contract["status"] == "candidate_review_recorded"
    assert safe_delta_contract["safe_delta_model_ready"] is False
    assert safe_delta_contract["safe_delta_review_recorded"] is True
    assert safe_delta_contract["safe_delta_review_receipt_id"] == safe_delta_recorded["receipt_id"]
    assert safe_delta_contract["delta_export_enabled"] is False
    assert safe_delta_contract["learning_write_enabled"] is False
    assert safe_delta_contract["next_smallest_truthful_gap"] == "stage18_safe_delta_operator_approval"

    safe_delta_status = client.get("/managed-copies/status").json()
    safe_delta_deliverable = next(
        item for item in safe_delta_status["deliverables"] if item["id"] == "safe_delta_model"
    )
    assert safe_delta_deliverable["status"] == "candidate_review_recorded"
    assert safe_delta_deliverable["ready"] is False
    assert safe_delta_status["safe_delta_review_recorded"] is True
    assert safe_delta_status["safe_delta_review_receipt_id"] == safe_delta_recorded["receipt_id"]
    assert safe_delta_status["safe_delta_approved"] is False
    assert safe_delta_status["safe_delta_exported"] is False
    assert safe_delta_status["safe_delta_learning_written"] is False

    duplicate_safe_delta = client.post(
        "/managed-copies/safe-delta-review",
        json={
            **safe_delta_payload,
            "dry_run": False,
            "review_fingerprint": safe_delta_plan["review_fingerprint"],
            "confirm_safe_delta_review": True,
        },
    ).json()
    assert duplicate_safe_delta["ok"] is True
    assert duplicate_safe_delta["status"] == "already_reviewed"
    assert duplicate_safe_delta["receipt_id"] == safe_delta_recorded["receipt_id"]
    assert duplicate_safe_delta["writes_receipts"] is False
    assert len(list(safe_delta_reviews_root.glob("*.json"))) == 1

    invalid_approval_path = approvals_root / "pending" / "managed-copy-invalid.json"
    invalid_approval_path.parent.mkdir(parents=True, exist_ok=True)
    invalid_approval_path.write_text(
        json.dumps(
            {
                "id": "managed-copy-invalid",
                "ts": 9_999_999_999,
                "action": "managed_copies.provision_copy",
                "status": "pending",
                "payload": {},
            }
        ),
        encoding="utf-8",
    )
    mixed_approval_readback = client.get("/managed-copies/copy-creation-approval-requests").json()
    assert mixed_approval_readback["count"] == 2
    assert mixed_approval_readback["valid_count"] == 1
    assert mixed_approval_readback["latest_approval_valid"] is False

    final_status = client.get("/managed-copies/status").json()
    assert final_status["copy_approval_id"] == approval_id
    assert final_status["copy_approval_status"] == "approved"
    assert final_status["copy_provisioned"] is True
    assert tenant_root.exists()


def test_managed_copy_creation_plan_denies_unscoped_actor_without_writing(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.delenv("FRANCIS_API_ACTOR_SCOPES", raising=False)

    body = (
        TestClient(create_app())
        .post(
            "/managed-copies/copy-creation-plan",
            json={
                "request_actor": "stage18.unscoped-plan",
                "request_receipt_id": "managed_copy_request_missing",
                "preflight_receipt_id": "managed_copy_preflight_missing",
            },
        )
        .json()
    )

    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["required_scope"] == "managed_copies.copy_creation.write"
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert not (data_root / "logs" / "managed_copies" / "copy_plans.jsonl").exists()


def test_managed_copy_creation_approval_request_denies_unscoped_actor_without_writing(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.delenv("FRANCIS_API_ACTOR_SCOPES", raising=False)

    body = (
        TestClient(create_app())
        .post(
            "/managed-copies/copy-creation-approval-request",
            json={
                "request_actor": "stage18.unscoped-approval-request",
                "plan_receipt_id": "managed_copy_creation_plan_missing",
            },
        )
        .json()
    )

    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["required_scope"] == "managed_copies.copy_creation.write"
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert not (data_root / "approvals").exists()


def test_managed_copy_creation_provision_denies_unscoped_actor_without_writing(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.delenv("FRANCIS_API_ACTOR_SCOPES", raising=False)

    body = (
        TestClient(create_app())
        .post(
            "/managed-copies/copy-creation-provision",
            json={
                "request_actor": "stage18.unscoped-provisioner",
                "plan_receipt_id": "managed_copy_creation_plan_missing",
                "approval_id": "approval-missing",
            },
        )
        .json()
    )

    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["required_scope"] == "managed_copies.copy_creation.write"
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert not (data_root / "managed_copies").exists()


def test_managed_copy_preflight_denies_unscoped_actor_without_writing(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.delenv("FRANCIS_API_ACTOR_SCOPES", raising=False)

    body = (
        TestClient(create_app())
        .post(
            "/managed-copies/copy-creation-preflight",
            json={"request_actor": "stage18.unscoped-preflight", "request_receipt_id": "missing"},
        )
        .json()
    )

    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["required_scope"] == "managed_copies.copy_creation.write"
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert not (data_root / "logs" / "managed_copies" / "copy_preflights.jsonl").exists()


def test_managed_copy_creation_request_denies_unscoped_actor_without_writing(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")

    response = TestClient(create_app()).post(
        "/managed-copies/copy-creation-request",
        json={
            "request_actor": "stage18.copy-unscoped",
            "tenant_id": "tenant-denied",
            "tenant_identity": {"tenant_name": "Denied Tenant"},
            "tenant_policy": {"support_allowed": False},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["required_scope"] == "managed_copies.copy_creation.write"
    assert body["copy_creation_enabled"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False

    governance = body["governance"]
    assert governance["gate"] == "permission_gate"
    assert governance["reason"] == "missing_scopes"
    assert governance["required_scope"] == "managed_copies.copy_creation.write"
    assert governance["evidence"]["route"] == "/managed-copies/copy-creation-request"
    assert governance["evidence"]["method"] == "POST"
    assert governance["evidence"]["required_scope_count"] == 1
    assert governance["evidence"]["actor_scope_count"] == 0
    assert not data_root.exists()


def test_managed_copy_creation_request_blocks_scoped_actor_until_stage17_closes(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    actor = "stage18.copy-requester"
    raw_tenant_id = "tenant-secret-should-not-echo"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({actor: ["managed_copies.copy_creation.write"]}),
    )

    response = TestClient(create_app()).post(
        "/managed-copies/copy-creation-request",
        json={
            "request_actor": actor,
            "tenant_id": raw_tenant_id,
            "tenant_identity": {"tenant_name": "Customer Alpha"},
            "tenant_policy": {"support_allowed": True},
            "isolation_profile": {"tenant_data": "isolated"},
            "capability_lineage": {"base_pack": "core"},
            "safe_delta_policy": {"raw_private_pooling_allowed": False},
            "support_boundary": {"time_bound": True},
            "decommission_policy": {"export_required": True},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["kind"] == "francis.stage18.managed_copies.copy_creation_request"
    assert body["status"] == "blocked_stage17_prerequisite"
    assert body["error"] == "stage17_prerequisite_not_closed"
    assert body["actor"] == actor
    assert body["request_known"] is True
    assert body["request_field_presence"] == {
        "tenant_id": True,
        "tenant_identity": True,
        "tenant_policy": True,
        "isolation_profile": True,
        "capability_lineage": True,
        "safe_delta_policy": True,
        "support_boundary": True,
        "decommission_policy": True,
    }
    assert raw_tenant_id not in json.dumps(body)
    assert body["stage17_closed_by_receipt"] is False
    assert body["stage17_blocker"] == "stage17_operator_stage_closure_decision"
    assert body["copy_creation_enabled"] is False
    assert body["copy_creation_allowed"] is False
    assert body["copy_request_recording_enabled"] is False
    assert body["copy_request_recorded"] is False
    assert body["copy_created"] is False
    assert body["receipt_ready"] is False
    assert body["writes_registry"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["expected_request_receipt_path"] == "logs/managed_copies/copy_requests.jsonl"
    assert body["required_scope"] == "managed_copies.copy_creation.write"
    assert body["routes"]["copy_creation_request"] == "/managed-copies/copy-creation-request"
    assert body["next_smallest_truthful_gap"] == "stage17_operator_stage_closure_decision"

    governance = body["governance"]
    assert governance["write_route"] is True
    assert governance["preflight_only"] is True
    assert governance["permission_scope"] == "managed_copies.copy_creation.write"
    assert governance["permission_checked"] is True
    assert governance["copy_creation_enabled"] is False
    assert governance["copy_request_recording_enabled"] is False
    assert governance["does_not_record_copy_request"] is True
    assert governance["does_not_create_copy"] is True
    assert governance["does_not_echo_raw_tenant_payload"] is True
    assert governance["requires_stage17_closure_receipt"] is True
    assert governance["writes_receipts"] is False
    assert governance["writes_tenant_state"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False
    assert not data_root.exists()


def test_managed_copy_completion_review_blocks_closure_without_runtime_evidence(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    response = TestClient(create_app()).get("/managed-copies/completion-review")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "francis.stage18.managed_copies.completion_review"
    assert body["stage"] == "Stage 18 / Managed Copies Platform"
    assert body["source_id"] == "managed_copies"
    assert body["status"] == "blocked"
    assert body["stage17_closed_by_receipt"] is False
    assert body["contract_readback_complete"] is True
    assert body["runtime_readiness_ready"] is False
    assert body["stage18_completion_review_ready"] is False
    assert body["ready_to_close"] is False
    assert body["stage_closure_decision_required"] is False
    assert body["runtime_evidence_readback_ready"] is False
    assert body["runtime_evidence_readbacks"]["status"] == "empty"
    assert body["runtime_evidence_readbacks"]["count"] == 0
    assert body["runtime_evidence_readbacks"]["ready_count"] == 0
    assert body["runtime_evidence_readbacks"]["required_count"] == body["required_count"]
    assert body["runtime_evidence_readbacks"]["missing_evidence"] == [
        "stage17_closure_receipt",
        "copy_creation_runtime_proof",
        "tenant_isolation_runtime_proof",
        "safe_delta_runtime_proof",
        "rogue_recovery_runtime_proof",
        "sla_runtime_proof",
        "role_authority_runtime_proof",
        "decommission_runtime_proof",
    ]
    assert body["readback_ready_count"] == body["required_count"]
    assert body["runtime_ready_count"] == 0
    assert body["passed_count"] == 0

    check_by_id = {item["id"]: item for item in body["checks"]}
    assert set(check_by_id) == {
        "stage17_ledger_closure_backstop",
        "copy_creation_contract",
        "isolation_rules_contract",
        "safe_delta_model_contract",
        "rogue_recovery_contract",
        "sla_framework_contract",
        "roles_contract",
        "decommission_contract",
    }
    assert all(item["readback_ready"] is True for item in body["checks"])
    assert all(item["runtime_ready"] is False for item in body["checks"])
    assert all(item["passed"] is False for item in body["checks"])
    assert check_by_id["stage17_ledger_closure_backstop"]["blocker"] == ("stage17_operator_stage_closure_decision")
    assert check_by_id["copy_creation_contract"]["route"] == "/managed-copies/copy-creation-contract"
    assert check_by_id["decommission_contract"]["route"] == "/managed-copies/decommission-contract"
    assert body["blockers"] == [
        "stage17_operator_stage_closure_decision",
        "stage18_copy_creation_runtime_not_implemented",
        "stage18_tenant_isolation_runtime_not_implemented",
        "stage18_safe_delta_runtime_not_implemented",
        "stage18_rogue_recovery_runtime_not_implemented",
        "stage18_sla_runtime_not_implemented",
        "stage18_role_authority_runtime_not_implemented",
        "stage18_decommission_runtime_not_implemented",
    ]
    assert body["done_criteria"] == {
        "customer_instances_are_isolated": False,
        "global_core_improves_through_safe_signals": False,
        "rogue_instances_can_be_detected_and_replaced": False,
        "business_model_aligned_to_product_law": False,
    }
    assert body["routes"]["completion_review"] == "/managed-copies/completion-review"
    assert body["routes"]["copy_creation_request"] == "/managed-copies/copy-creation-request"
    assert body["routes"]["isolation_verification"] == "/managed-copies/isolation-verification"
    assert body["routes"]["safe_delta_review"] == "/managed-copies/safe-delta-review"
    assert body["routes"]["rogue_recovery_review"] == "/managed-copies/rogue-recovery-review"
    assert body["routes"]["runtime_evidence_contract"] == "/managed-copies/runtime-evidence-contract"
    assert body["routes"]["runtime_evidence_readbacks"] == "/managed-copies/runtime-evidence-readbacks"
    assert body["routes"]["runtime_evidence_readback"] == "/managed-copies/runtime-evidence-readback"

    assert body["read_only"] is True
    assert body["projection_only"] is True
    assert body["copy_creation_enabled"] is False
    assert body["writes_registry"] is False
    assert body["writes_memory"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["launches_browser"] is False
    assert body["captures_screen"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["next_smallest_truthful_gap"] == "stage17_operator_stage_closure_decision"

    governance = body["governance"]
    assert governance["completion_review_only"] is True
    assert governance["does_not_mark_stage_closed"] is True
    assert governance["requires_runtime_evidence"] is True
    assert governance["requires_stage17_closure_receipt"] is True
    assert governance["stage_closure_decision_required"] is False
    assert governance["writes_tenant_state"] is False
    assert governance["writes_receipts"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False
    assert not data_root.exists()


def test_managed_copy_runtime_evidence_contract_is_readonly_and_not_recording(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    response = TestClient(create_app()).get("/managed-copies/runtime-evidence-contract")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "francis.stage18.managed_copies.runtime_evidence_contract"
    assert body["stage"] == "Stage 18 / Managed Copies Platform"
    assert body["source_id"] == "managed_copies"
    assert body["status"] == "blocked"
    assert body["contract_readback_ready"] is True
    assert body["runtime_evidence_contract_ready"] is False
    assert body["runtime_evidence_recording_enabled"] is False
    assert body["runtime_evidence_ready"] is False
    assert body["stage17_closed_by_receipt"] is False
    assert body["stage17_blocker"] == "stage17_operator_stage_closure_decision"
    assert body["completion_review_route"] == "/managed-copies/completion-review"
    assert body["routes"]["runtime_evidence_contract"] == "/managed-copies/runtime-evidence-contract"
    assert body["routes"]["runtime_evidence_readbacks"] == "/managed-copies/runtime-evidence-readbacks"
    assert body["routes"]["runtime_evidence_readback"] == "/managed-copies/runtime-evidence-readback"
    assert body["ready_count"] == 0
    assert body["required_count"] == len(body["requirements"])

    requirement_by_id = {item["id"]: item for item in body["requirements"]}
    assert set(requirement_by_id) == {
        "stage17_closure_receipt",
        "copy_creation_runtime_proof",
        "tenant_isolation_runtime_proof",
        "safe_delta_runtime_proof",
        "rogue_recovery_runtime_proof",
        "sla_runtime_proof",
        "role_authority_runtime_proof",
        "decommission_runtime_proof",
    }
    assert all(item["status"] == "required_not_present" for item in body["requirements"])
    assert all(item["ready"] is False for item in body["requirements"])
    assert all(item["requires_receipt"] is True for item in body["requirements"])
    assert all(item["recording_enabled"] is False for item in body["requirements"])
    assert all(item["writes_receipt"] is False for item in body["requirements"])
    assert all(item["mutates_tenant_state"] is False for item in body["requirements"])
    assert all(item["grants_execution_authority"] is False for item in body["requirements"])
    assert all(item["grants_mutation_authority"] is False for item in body["requirements"])
    assert requirement_by_id["copy_creation_runtime_proof"]["source_contract_route"] == (
        "/managed-copies/copy-creation-contract"
    )
    assert requirement_by_id["decommission_runtime_proof"]["proof_kind"] == "decommission_runtime_receipt"

    assert body["blockers"] == [
        "stage17_operator_stage_closure_decision",
        "stage18_copy_creation_runtime_not_implemented",
        "stage18_tenant_isolation_runtime_not_implemented",
        "stage18_safe_delta_runtime_not_implemented",
        "stage18_rogue_recovery_runtime_not_implemented",
        "stage18_sla_runtime_not_implemented",
        "stage18_role_authority_runtime_not_implemented",
        "stage18_decommission_runtime_not_implemented",
    ]
    assert body["accepted_proof_kinds"] == [
        "ledger_closure_receipt",
        "managed_copy_creation_runtime_receipt",
        "tenant_isolation_runtime_receipt",
        "safe_delta_runtime_receipt",
        "rogue_recovery_runtime_receipt",
        "sla_runtime_receipt",
        "managed_copy_role_authority_receipt",
        "decommission_runtime_receipt",
    ]

    assert body["read_only"] is True
    assert body["projection_only"] is True
    assert body["copy_creation_enabled"] is False
    assert body["writes_registry"] is False
    assert body["writes_memory"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["launches_browser"] is False
    assert body["captures_screen"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["next_smallest_truthful_gap"] == "stage17_operator_stage_closure_decision"

    governance = body["governance"]
    assert governance["runtime_evidence_contract_only"] is True
    assert governance["evidence_collection_enabled"] is False
    assert governance["does_not_record_runtime_evidence"] is True
    assert governance["does_not_mark_stage_closed"] is True
    assert governance["requires_stage17_closure_receipt"] is True
    assert governance["writes_tenant_state"] is False
    assert governance["writes_receipts"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False
    assert not data_root.exists()


def test_managed_copy_runtime_evidence_readbacks_are_empty_and_readonly(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    response = TestClient(create_app()).get("/managed-copies/runtime-evidence-readbacks")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "francis.stage18.managed_copies.runtime_evidence_readbacks"
    assert body["stage"] == "Stage 18 / Managed Copies Platform"
    assert body["source_id"] == "managed_copies"
    assert body["status"] == "empty"
    assert body["items"] == []
    assert body["count"] == 0
    assert body["receipt_ready_count"] == 0
    assert body["ready_count"] == 0
    assert body["required_count"] == len(body["checks"])
    assert body["runtime_evidence_readback_ready"] is False
    assert body["runtime_evidence_ready"] is False
    assert body["runtime_evidence_recording_enabled"] is False
    assert body["expected_receipt_path"] == "logs/managed_copies/runtime_evidence.jsonl"
    assert body["routes"]["runtime_evidence_readback"] == "/managed-copies/runtime-evidence-readback"
    assert body["missing_evidence"] == [
        "stage17_closure_receipt",
        "copy_creation_runtime_proof",
        "tenant_isolation_runtime_proof",
        "safe_delta_runtime_proof",
        "rogue_recovery_runtime_proof",
        "sla_runtime_proof",
        "role_authority_runtime_proof",
        "decommission_runtime_proof",
    ]
    assert body["missing_blockers"] == [
        "stage17_operator_stage_closure_decision",
        "stage18_copy_creation_runtime_not_implemented",
        "stage18_tenant_isolation_runtime_not_implemented",
        "stage18_safe_delta_runtime_not_implemented",
        "stage18_rogue_recovery_runtime_not_implemented",
        "stage18_sla_runtime_not_implemented",
        "stage18_role_authority_runtime_not_implemented",
        "stage18_decommission_runtime_not_implemented",
    ]
    assert all(item["passed"] is False for item in body["checks"])
    assert all(item["receipt_ready"] is False for item in body["checks"])
    assert all(item["status"] == "not_observed" for item in body["checks"])

    assert body["read_only"] is True
    assert body["projection_only"] is True
    assert body["writes_registry"] is False
    assert body["writes_memory"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["launches_browser"] is False
    assert body["captures_screen"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["next_smallest_truthful_gap"] == "stage17_operator_stage_closure_decision"

    governance = body["governance"]
    assert governance["runtime_evidence_readback_only"] is True
    assert governance["does_not_record_runtime_evidence"] is True
    assert governance["does_not_mark_stage_closed"] is True
    assert governance["writes_receipts"] is False
    assert governance["writes_tenant_state"] is False
    assert not data_root.exists()


def test_managed_copy_runtime_evidence_readbacks_consume_existing_receipts_without_writing(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    receipt_path = data_root / "logs" / "managed_copies" / "runtime_evidence.jsonl"
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_text(
        json.dumps(
            {
                "requirement_id": "copy_creation_runtime_proof",
                "proof_kind": "managed_copy_creation_runtime_receipt",
                "receipt_id": "mc-copy-runtime-proof-1",
                "trace_id": "trace-managed-copy-runtime-proof-1",
                "status": "observed",
                "observed": True,
                "evidence_summary": "bounded test receipt for managed-copy creation runtime proof",
                "governance": {
                    "runtime_evidence_receipt": True,
                    "trace_linked": True,
                    "redacted": True,
                    "contains_raw_private_data": False,
                    "grants_execution_authority": False,
                    "grants_mutation_authority": False,
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    response = TestClient(create_app()).get("/managed-copies/runtime-evidence-readbacks")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    assert body["count"] == 1
    assert body["receipt_ready_count"] == 1
    assert body["ready_count"] == 1
    assert body["runtime_evidence_readback_ready"] is False
    assert body["missing_evidence"] == [
        "stage17_closure_receipt",
        "tenant_isolation_runtime_proof",
        "safe_delta_runtime_proof",
        "rogue_recovery_runtime_proof",
        "sla_runtime_proof",
        "role_authority_runtime_proof",
        "decommission_runtime_proof",
    ]
    check_by_id = {item["id"]: item for item in body["checks"]}
    assert check_by_id["copy_creation_runtime_proof"]["passed"] is True
    assert check_by_id["copy_creation_runtime_proof"]["receipt_id"] == "mc-copy-runtime-proof-1"
    assert check_by_id["copy_creation_runtime_proof"]["proof_kind"] == "managed_copy_creation_runtime_receipt"
    assert check_by_id["copy_creation_runtime_proof"]["trace_id"] == "trace-managed-copy-runtime-proof-1"
    assert check_by_id["copy_creation_runtime_proof"]["status"] == "observed"
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False


def test_managed_copy_runtime_evidence_readback_denies_unscoped_actor_without_writing(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")

    response = TestClient(create_app()).post(
        "/managed-copies/runtime-evidence-readback",
        json={
            "request_actor": "stage18.unscoped",
            "requirement_id": "copy_creation_runtime_proof",
            "proof_kind": "managed_copy_creation_runtime_receipt",
            "trace_id": "trace-managed-copy-runtime-proof-denied",
            "evidence_summary": "denied path must not create a runtime evidence receipt",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["required_scope"] == "managed_copies.runtime_evidence.write"
    assert body["runtime_evidence_recording_enabled"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False

    governance = body["governance"]
    assert governance["gate"] == "permission_gate"
    assert governance["reason"] == "missing_scopes"
    assert governance["required_scope"] == "managed_copies.runtime_evidence.write"
    assert governance["evidence"]["route"] == "/managed-copies/runtime-evidence-readback"
    assert governance["evidence"]["method"] == "POST"
    assert governance["evidence"]["required_scope_count"] == 1
    assert governance["evidence"]["actor_scope_count"] == 0
    assert not data_root.exists()


def test_managed_copy_runtime_evidence_readback_blocks_scoped_actor_until_stage17_closes(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    actor = "stage18.runtime-writer"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({actor: ["managed_copies.runtime_evidence.write"]}),
    )

    response = TestClient(create_app()).post(
        "/managed-copies/runtime-evidence-readback",
        json={
            "request_actor": actor,
            "requirement_id": "copy_creation_runtime_proof",
            "proof_kind": "managed_copy_creation_runtime_receipt",
            "trace_id": "trace-managed-copy-runtime-proof-blocked",
            "reason": "operator attempted to record runtime proof before Stage 17 closed",
            "evidence_summary": "blocked path must not create a runtime evidence receipt",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["kind"] == "francis.stage18.managed_copies.runtime_evidence_readback"
    assert body["status"] == "blocked_stage17_prerequisite"
    assert body["error"] == "stage17_prerequisite_not_closed"
    assert body["actor"] == actor
    assert body["requirement_id"] == "copy_creation_runtime_proof"
    assert body["requirement_known"] is True
    assert body["proof_kind"] == "managed_copy_creation_runtime_receipt"
    assert body["expected_proof_kind"] == "managed_copy_creation_runtime_receipt"
    assert body["proof_kind_matches_requirement"] is True
    assert body["trace_id"] == "trace-managed-copy-runtime-proof-blocked"
    assert body["evidence_summary_present"] is True
    assert body["stage17_closed_by_receipt"] is False
    assert body["stage17_blocker"] == "stage17_operator_stage_closure_decision"
    assert body["runtime_evidence_recording_enabled"] is False
    assert body["receipt_ready"] is False
    assert body["writes_receipt"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["expected_receipt_path"] == "logs/managed_copies/runtime_evidence.jsonl"
    assert body["required_scope"] == "managed_copies.runtime_evidence.write"
    assert body["routes"]["runtime_evidence_readback"] == "/managed-copies/runtime-evidence-readback"
    assert body["next_smallest_truthful_gap"] == "stage17_operator_stage_closure_decision"

    governance = body["governance"]
    assert governance["write_route"] is True
    assert governance["preflight_only"] is True
    assert governance["permission_scope"] == "managed_copies.runtime_evidence.write"
    assert governance["permission_checked"] is True
    assert governance["runtime_evidence_recording_enabled"] is False
    assert governance["does_not_record_runtime_evidence"] is True
    assert governance["requires_stage17_closure_receipt"] is True
    assert governance["writes_receipts"] is False
    assert governance["writes_tenant_state"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False
    assert not data_root.exists()


def test_managed_copy_decommission_contract_is_projection_only_and_inactive(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    response = TestClient(create_app()).get("/managed-copies/decommission-contract")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "francis.stage18.managed_copies.decommission_contract"
    assert body["stage"] == "Stage 18 / Managed Copies Platform"
    assert body["source_id"] == "managed_copies"
    assert body["status"] == "contract_readback_ready"
    assert body["contract_readback_ready"] is True
    assert body["decommission_contract_ready"] is False
    assert body["decommission_enabled"] is False
    assert body["export_enabled"] is False
    assert body["delete_enabled"] is False
    assert body["purge_enabled"] is False
    assert body["credential_revocation_enabled"] is False
    assert body["node_unpairing_enabled"] is False
    assert body["proof_receipts_enabled"] is False
    assert body["copy_creation_enabled"] is False
    assert body["stage17_closed_by_receipt"] is False
    assert body["stage17_blocker"] == "stage17_operator_stage_closure_decision"
    assert body["next_smallest_truthful_gap"] == "stage17_operator_stage_closure_decision"
    assert body["decommission_review_route"] == "/managed-copies/decommission-review"
    assert body["routes"]["decommission_review"] == "/managed-copies/decommission-review"

    step_by_id = {item["id"]: item for item in body["decommission_steps"]}
    assert set(step_by_id) == {
        "request",
        "export_before_delete",
        "revoke_credentials",
        "unpair_nodes",
        "delete_tenant_state",
        "retain_required_records",
        "prove_outcome",
    }
    assert body["step_count"] == len(body["decommission_steps"])
    assert body["active_step_count"] == 0
    assert step_by_id["request"]["status"] == "contract_only"
    assert step_by_id["request"]["mutates_tenant_state"] is False
    assert step_by_id["export_before_delete"]["status"] == "disabled"
    assert step_by_id["export_before_delete"]["writes_receipt"] is True
    assert step_by_id["revoke_credentials"]["status"] == "disabled"
    assert step_by_id["revoke_credentials"]["mutates_tenant_state"] is True
    assert step_by_id["unpair_nodes"]["status"] == "disabled"
    assert step_by_id["delete_tenant_state"]["status"] == "disabled"
    assert step_by_id["delete_tenant_state"]["mutates_tenant_state"] is True
    assert step_by_id["retain_required_records"]["status"] == "contract_only"
    assert step_by_id["prove_outcome"]["status"] == "disabled"
    assert all(item["requires_operator_approval"] is True for item in body["decommission_steps"])

    assert body["export_scope"] == [
        "tenant_configuration",
        "tenant_policy",
        "tenant_receipts",
        "tenant_memory_exports_where_policy_allows",
        "tenant_capability_pack_lineage",
        "tenant_sla_and_support_history",
        "tenant_safe_delta_lineage",
    ]
    assert body["deletion_scope"] == [
        "tenant_runtime_state",
        "tenant_memory_state",
        "tenant_connector_bindings",
        "tenant_credentials",
        "tenant_support_access",
        "tenant_automation_principals",
        "tenant_pairings",
    ]
    assert body["retention_scope"] == [
        "legal_hold_records",
        "billing_records",
        "security_incident_records",
        "policy_required_audit_summaries",
        "deidentified_platform_safety_metrics_when_allowed",
    ]
    assert body["required_receipts"] == [
        "decommission_request_receipt",
        "export_before_delete_receipt",
        "credential_revocation_receipt",
        "node_unpairing_receipt",
        "tenant_state_delete_receipt",
        "retention_scope_receipt",
        "decommission_proof_receipt",
    ]
    assert body["operator_controls_required"] == [
        "tenant_admin_or_operator_request",
        "export_review_before_delete",
        "deletion_scope_review",
        "retention_policy_review",
        "cross_copy_non_weakening_review",
        "final_proof_review",
    ]
    assert body["blocked_failure_modes"] == [
        "trapped_tenant_state",
        "residual_authority_after_decommission",
        "delete_without_export",
        "cross_copy_state_damage",
        "unproved_deletion",
        "hidden_retention",
        "vendor_gravity_exit_block",
    ]

    assert body["read_only"] is True
    assert body["projection_only"] is True
    assert body["writes_registry"] is False
    assert body["writes_memory"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["launches_browser"] is False
    assert body["captures_screen"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["exports_tenant_data"] is False
    assert body["deletes_tenant_state"] is False
    assert body["revokes_credentials"] is False
    assert body["unpairs_nodes"] is False
    assert body["purges_memory"] is False
    assert body["records_decommission_receipt"] is False
    assert body["weakens_other_copies"] is False

    governance = body["governance"]
    assert governance["read_only"] is True
    assert governance["projection_only"] is True
    assert governance["copy_creation_enabled"] is False
    assert governance["writes_tenant_state"] is False
    assert governance["writes_receipts"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False
    assert not data_root.exists()


def test_managed_copy_decommission_review_denies_unscoped_actor_without_writing(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")

    response = TestClient(create_app()).post(
        "/managed-copies/decommission-review",
        json={
            "request_actor": "stage18.decommission-unscoped",
            "copy_id": "copy-denied",
            "tenant_id": "tenant-denied",
            "action": "revoke_credentials",
            "decommission_request": {"reason": "denied path should not revoke anything"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["required_scope"] == "managed_copies.decommission.write"
    assert body["decommission_contract_ready"] is False
    assert body["decommission_review_enabled"] is False
    assert body["decommission_enabled"] is False
    assert body["export_enabled"] is False
    assert body["delete_enabled"] is False
    assert body["purge_enabled"] is False
    assert body["credential_revocation_enabled"] is False
    assert body["node_unpairing_enabled"] is False
    assert body["proof_receipts_enabled"] is False
    assert body["exports_tenant_data"] is False
    assert body["deletes_tenant_state"] is False
    assert body["revokes_credentials"] is False
    assert body["unpairs_nodes"] is False
    assert body["purges_memory"] is False
    assert body["records_decommission_receipt"] is False
    assert body["weakens_other_copies"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False

    governance = body["governance"]
    assert governance["gate"] == "permission_gate"
    assert governance["reason"] == "missing_scopes"
    assert governance["required_scope"] == "managed_copies.decommission.write"
    assert governance["evidence"]["route"] == "/managed-copies/decommission-review"
    assert governance["evidence"]["method"] == "POST"
    assert governance["evidence"]["required_scope_count"] == 1
    assert governance["evidence"]["actor_scope_count"] == 0
    assert not data_root.exists()


def test_managed_copy_decommission_review_blocks_scoped_actor_until_stage17_closes(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    actor = "stage18.decommission-reviewer"
    raw_tenant_id = "tenant-decommission-secret-should-not-echo"
    raw_request_reason = "raw decommission reason should not echo"
    raw_unknown_scope = "tenant_private_extra_scope_should_not_echo"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({actor: ["managed_copies.decommission.write"]}),
    )

    response = TestClient(create_app()).post(
        "/managed-copies/decommission-review",
        json={
            "request_actor": actor,
            "copy_id": "copy-123",
            "tenant_id": raw_tenant_id,
            "action": "revoke_credentials",
            "decommission_request": {"reason": raw_request_reason},
            "export_scope": [
                "tenant_configuration",
                "tenant_receipts",
                raw_unknown_scope,
            ],
            "deletion_scope": [
                "tenant_credentials",
                "tenant_pairings",
            ],
            "retention_scope": ["legal_hold_records"],
            "evidence_refs": ["receipt-1", "receipt-2", "receipt-3"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    encoded = json.dumps(body)
    assert body["ok"] is False
    assert body["kind"] == "francis.stage18.managed_copies.decommission_review"
    assert body["status"] == "blocked_stage17_prerequisite"
    assert body["error"] == "stage17_prerequisite_not_closed"
    assert body["actor"] == actor
    assert body["copy_id_present"] is True
    assert body["tenant_id_present"] is True
    assert body["request_present"] is True
    assert body["evidence_ref_count"] == 3
    assert raw_tenant_id not in encoded
    assert raw_request_reason not in encoded
    assert raw_unknown_scope not in encoded
    assert body["action"] == "revoke_credentials"
    assert body["action_known"] is True
    assert body["action_writes_receipt"] is True
    assert body["action_mutates_tenant_state"] is True
    assert body["export_scope_requested_count"] == 3
    assert body["export_scope_known_count"] == 2
    assert body["export_scope_unknown_count"] == 1
    assert body["deletion_scope_requested_count"] == 2
    assert body["deletion_scope_known_count"] == 2
    assert body["deletion_scope_unknown_count"] == 0
    assert body["retention_scope_requested_count"] == 1
    assert body["retention_scope_known_count"] == 1
    assert body["retention_scope_unknown_count"] == 0
    assert body["stage17_closed_by_receipt"] is False
    assert body["stage17_blocker"] == "stage17_operator_stage_closure_decision"
    assert body["decommission_contract_ready"] is False
    assert body["decommission_review_enabled"] is False
    assert body["decommission_enabled"] is False
    assert body["export_enabled"] is False
    assert body["delete_enabled"] is False
    assert body["purge_enabled"] is False
    assert body["credential_revocation_enabled"] is False
    assert body["node_unpairing_enabled"] is False
    assert body["proof_receipts_enabled"] is False
    assert body["exports_tenant_data"] is False
    assert body["deletes_tenant_state"] is False
    assert body["revokes_credentials"] is False
    assert body["unpairs_nodes"] is False
    assert body["purges_memory"] is False
    assert body["records_decommission_receipt"] is False
    assert body["weakens_other_copies"] is False
    assert body["receipt_ready"] is False
    assert body["writes_registry"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["expected_review_receipt_path"] == "logs/managed_copies/decommission_reviews.jsonl"
    assert body["required_scope"] == "managed_copies.decommission.write"
    assert body["routes"]["decommission_review"] == "/managed-copies/decommission-review"
    assert body["next_smallest_truthful_gap"] == "stage17_operator_stage_closure_decision"

    governance = body["governance"]
    assert governance["write_route"] is True
    assert governance["preflight_only"] is True
    assert governance["permission_scope"] == "managed_copies.decommission.write"
    assert governance["permission_checked"] is True
    assert governance["decommission_review_enabled"] is False
    assert governance["decommission_enabled"] is False
    assert governance["does_not_export_tenant_data"] is True
    assert governance["does_not_delete_tenant_state"] is True
    assert governance["does_not_revoke_credentials"] is True
    assert governance["does_not_unpair_nodes"] is True
    assert governance["does_not_purge_memory"] is True
    assert governance["does_not_record_decommission_receipt"] is True
    assert governance["does_not_weaken_other_copies"] is True
    assert governance["does_not_echo_raw_decommission_payload"] is True
    assert governance["requires_stage17_closure_receipt"] is True
    assert governance["writes_receipts"] is False
    assert governance["writes_tenant_state"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False
    assert not data_root.exists()


def test_managed_copy_roles_contract_is_projection_only_and_authority_inactive(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    response = TestClient(create_app()).get("/managed-copies/roles-contract")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "francis.stage18.managed_copies.roles_contract"
    assert body["stage"] == "Stage 18 / Managed Copies Platform"
    assert body["source_id"] == "managed_copies"
    assert body["status"] == "contract_readback_ready"
    assert body["contract_readback_ready"] is True
    assert body["roles_contract_ready"] is False
    assert body["role_authority_active"] is False
    assert body["authority_binding_enabled"] is False
    assert body["credential_binding_enabled"] is False
    assert body["support_authority_enabled"] is False
    assert body["automation_principal_enabled"] is False
    assert body["paired_node_authority_enabled"] is False
    assert body["copy_creation_enabled"] is False
    assert body["stage17_closed_by_receipt"] is False
    assert body["stage17_blocker"] == "stage17_operator_stage_closure_decision"
    assert body["next_smallest_truthful_gap"] == "stage17_operator_stage_closure_decision"
    assert body["role_authority_review_route"] == "/managed-copies/role-authority-review"
    assert body["routes"]["role_authority_review"] == "/managed-copies/role-authority-review"

    role_ids = {item["id"] for item in body["roles"]}
    assert role_ids == {
        "end_user",
        "tenant_admin",
        "support_operator",
        "automation_principal",
        "paired_node",
    }
    assert body["required_role_count"] == len(body["roles"])
    assert body["active_role_count"] == 0
    assert all(item["status"] == "contract_only" for item in body["roles"])
    assert all(item["requires_explicit_binding"] is True for item in body["roles"])
    assert all(item["authority_active"] is False for item in body["roles"])
    assert all(item["allowed_authority"] for item in body["roles"])
    assert all(item["denied_authority"] for item in body["roles"])

    assert body["role_separation_rules"] == [
        "human_authority_separate_from_backend_service_authority",
        "support_authority_separate_from_tenant_admin_authority",
        "automation_principal_cannot_impersonate_human_operator",
        "paired_node_authority_is_scoped_and_revocable",
        "tenant_admin_cannot_surrender_core_ip_or_bypass_core_law",
    ]
    assert body["credential_binding_rules"] == [
        "scoped_credentials_only",
        "rotation_and_revocation_required",
        "bind_credentials_to_node_copy_connector_or_capability_class",
        "no_raw_secret_exposure_in_lens_logs_receipts_or_replay",
        "approval_and_audit_required_for_creation_attachment_elevation_and_replacement",
    ]
    assert body["required_receipts"] == [
        "role_binding_receipt",
        "tenant_admin_delegation_receipt",
        "support_authority_receipt",
        "automation_principal_scope_receipt",
        "paired_node_trust_receipt",
        "credential_binding_receipt",
        "role_revocation_receipt",
    ]
    assert body["blocked_failure_modes"] == [
        "fuzzy_role_authority",
        "standing_support_access",
        "backend_service_impersonates_user",
        "paired_node_trust_expansion",
        "automation_principal_scope_creep",
        "raw_secret_exposure",
        "tenant_admin_core_law_bypass",
    ]

    assert body["read_only"] is True
    assert body["projection_only"] is True
    assert body["writes_registry"] is False
    assert body["writes_memory"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["launches_browser"] is False
    assert body["captures_screen"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["creates_role_binding"] is False
    assert body["binds_credentials"] is False
    assert body["grants_support_access"] is False
    assert body["activates_automation_principal"] is False
    assert body["pairs_node"] is False
    assert body["revokes_role"] is False

    governance = body["governance"]
    assert governance["read_only"] is True
    assert governance["projection_only"] is True
    assert governance["copy_creation_enabled"] is False
    assert governance["writes_tenant_state"] is False
    assert governance["writes_receipts"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False
    assert not data_root.exists()


def test_managed_copy_role_authority_review_denies_unscoped_actor_without_writing(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")

    response = TestClient(create_app()).post(
        "/managed-copies/role-authority-review",
        json={
            "request_actor": "stage18.role-unscoped",
            "copy_id": "copy-denied",
            "tenant_id": "tenant-denied",
            "role_id": "support_operator",
            "requested_authority": "inspect_tenant_visible_incident_state",
            "binding_type": "support_authority",
            "support_access": {"reason": "denied path should not grant access"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["required_scope"] == "managed_copies.role_authority.write"
    assert body["roles_contract_ready"] is False
    assert body["role_authority_review_enabled"] is False
    assert body["role_authority_active"] is False
    assert body["authority_binding_enabled"] is False
    assert body["credential_binding_enabled"] is False
    assert body["support_authority_enabled"] is False
    assert body["automation_principal_enabled"] is False
    assert body["paired_node_authority_enabled"] is False
    assert body["creates_role_binding"] is False
    assert body["binds_credentials"] is False
    assert body["grants_support_access"] is False
    assert body["activates_automation_principal"] is False
    assert body["pairs_node"] is False
    assert body["revokes_role"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False

    governance = body["governance"]
    assert governance["gate"] == "permission_gate"
    assert governance["reason"] == "missing_scopes"
    assert governance["required_scope"] == "managed_copies.role_authority.write"
    assert governance["evidence"]["route"] == "/managed-copies/role-authority-review"
    assert governance["evidence"]["method"] == "POST"
    assert governance["evidence"]["required_scope_count"] == 1
    assert governance["evidence"]["actor_scope_count"] == 0
    assert not data_root.exists()


def test_managed_copy_role_authority_review_blocks_scoped_actor_until_stage17_closes(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    actor = "stage18.role-reviewer"
    raw_tenant_id = "tenant-role-secret-should-not-echo"
    raw_credential_secret = "credential-secret-should-not-echo"
    raw_support_reason = "raw support authority context should not echo"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({actor: ["managed_copies.role_authority.write"]}),
    )

    response = TestClient(create_app()).post(
        "/managed-copies/role-authority-review",
        json={
            "request_actor": actor,
            "copy_id": "copy-123",
            "tenant_id": raw_tenant_id,
            "role_id": "support_operator",
            "requested_authority": "inspect_tenant_visible_incident_state",
            "binding_type": "support_authority",
            "credential_binding": {"secret": raw_credential_secret},
            "support_access": {"reason": raw_support_reason},
            "evidence_refs": ["receipt-1", "receipt-2"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    encoded = json.dumps(body)
    assert body["ok"] is False
    assert body["kind"] == "francis.stage18.managed_copies.role_authority_review"
    assert body["status"] == "blocked_stage17_prerequisite"
    assert body["error"] == "stage17_prerequisite_not_closed"
    assert body["actor"] == actor
    assert body["copy_id_present"] is True
    assert body["tenant_id_present"] is True
    assert raw_tenant_id not in encoded
    assert raw_credential_secret not in encoded
    assert raw_support_reason not in encoded
    assert body["role_id"] == "support_operator"
    assert body["role_known"] is True
    assert body["requested_authority"] == "inspect_tenant_visible_incident_state"
    assert body["requested_authority_known"] is True
    assert body["requested_authority_allowed_by_contract"] is True
    assert body["requested_authority_denied_by_contract"] is False
    assert body["binding_type"] == "support_authority"
    assert body["binding_type_known"] is True
    assert body["credential_binding_present"] is True
    assert body["support_access_requested"] is True
    assert body["automation_principal_requested"] is False
    assert body["node_pairing_requested"] is False
    assert body["evidence_ref_count"] == 2
    assert body["stage17_closed_by_receipt"] is False
    assert body["stage17_blocker"] == "stage17_operator_stage_closure_decision"
    assert body["roles_contract_ready"] is False
    assert body["role_authority_review_enabled"] is False
    assert body["role_authority_active"] is False
    assert body["authority_binding_enabled"] is False
    assert body["credential_binding_enabled"] is False
    assert body["support_authority_enabled"] is False
    assert body["automation_principal_enabled"] is False
    assert body["paired_node_authority_enabled"] is False
    assert body["creates_role_binding"] is False
    assert body["binds_credentials"] is False
    assert body["grants_support_access"] is False
    assert body["activates_automation_principal"] is False
    assert body["pairs_node"] is False
    assert body["revokes_role"] is False
    assert body["receipt_ready"] is False
    assert body["writes_registry"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["expected_review_receipt_path"] == "logs/managed_copies/role_authority_reviews.jsonl"
    assert body["required_scope"] == "managed_copies.role_authority.write"
    assert body["routes"]["role_authority_review"] == "/managed-copies/role-authority-review"
    assert body["next_smallest_truthful_gap"] == "stage17_operator_stage_closure_decision"

    governance = body["governance"]
    assert governance["write_route"] is True
    assert governance["preflight_only"] is True
    assert governance["permission_scope"] == "managed_copies.role_authority.write"
    assert governance["permission_checked"] is True
    assert governance["role_authority_review_enabled"] is False
    assert governance["role_authority_active"] is False
    assert governance["does_not_create_role_binding"] is True
    assert governance["does_not_bind_credentials"] is True
    assert governance["does_not_grant_support_access"] is True
    assert governance["does_not_activate_automation_principal"] is True
    assert governance["does_not_pair_node"] is True
    assert governance["does_not_revoke_role"] is True
    assert governance["does_not_record_role_authority_receipt"] is True
    assert governance["does_not_echo_raw_authority_payload"] is True
    assert governance["requires_stage17_closure_receipt"] is True
    assert governance["writes_receipts"] is False
    assert governance["writes_tenant_state"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False
    assert not data_root.exists()


def test_managed_copy_sla_framework_contract_is_projection_only_and_inactive(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    response = TestClient(create_app()).get("/managed-copies/sla-framework-contract")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "francis.stage18.managed_copies.sla_framework_contract"
    assert body["stage"] == "Stage 18 / Managed Copies Platform"
    assert body["source_id"] == "managed_copies"
    assert body["status"] == "contract_readback_ready"
    assert body["contract_readback_ready"] is True
    assert body["sla_framework_ready"] is False
    assert body["sla_commitments_active"] is False
    assert body["monitoring_enabled"] is False
    assert body["paging_enabled"] is False
    assert body["support_tiers_enabled"] is False
    assert body["billing_entitlements_enabled"] is False
    assert body["copy_creation_enabled"] is False
    assert body["stage17_closed_by_receipt"] is False
    assert body["stage17_blocker"] == "stage17_operator_stage_closure_decision"
    assert body["next_smallest_truthful_gap"] == "stage17_operator_stage_closure_decision"
    assert body["sla_commitment_review_route"] == "/managed-copies/sla-commitment-review"
    assert body["routes"]["sla_commitment_review"] == "/managed-copies/sla-commitment-review"

    commitment_ids = {item["id"] for item in body["commitments"]}
    assert commitment_ids == {
        "uptime_commitment",
        "response_commitment",
        "incident_handling_commitment",
        "recovery_commitment",
        "support_tier_commitment",
        "managed_governance_commitment",
    }
    assert body["commitment_count"] == len(body["commitments"])
    assert body["active_commitment_count"] == 0
    assert all(item["status"] == "contract_only" for item in body["commitments"])
    assert all(item["active"] is False for item in body["commitments"])
    assert all(item["requires_receipt"] is True for item in body["commitments"])

    assert body["support_tiers"] == [
        "standard_support",
        "priority_support",
        "premium_governance_support",
        "rogue_recovery_assistance",
    ]
    assert body["required_receipts"] == [
        "sla_plan_receipt",
        "tenant_support_tier_receipt",
        "monitoring_scope_receipt",
        "incident_response_receipt",
        "recovery_commitment_receipt",
        "managed_governance_review_receipt",
        "sla_exception_or_breach_receipt",
    ]
    assert body["service_metrics"] == [
        "uptime_window",
        "response_time_window",
        "incident_acknowledgement_time",
        "recovery_time_objective",
        "recovery_point_objective",
        "governance_review_interval",
        "support_access_audit_interval",
    ]
    assert body["operator_controls_required"] == [
        "tenant_visible_sla_state",
        "support_authority_scope_check",
        "incident_severity_review",
        "recovery_plan_review",
        "breach_exception_review",
        "revocation_or_downgrade_path",
    ]
    assert body["blocked_failure_modes"] == [
        "unbounded_support_obligation",
        "invisible_vendor_power",
        "sla_claim_without_monitoring",
        "incident_handling_without_receipts",
        "recovery_promise_without_recovery_path",
        "support_tier_without_authority_boundary",
    ]

    assert body["read_only"] is True
    assert body["projection_only"] is True
    assert body["writes_registry"] is False
    assert body["writes_memory"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["launches_browser"] is False
    assert body["captures_screen"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["creates_service_commitment"] is False
    assert body["pages_support"] is False
    assert body["opens_incident"] is False
    assert body["records_sla_receipt"] is False
    assert body["grants_support_authority"] is False

    governance = body["governance"]
    assert governance["read_only"] is True
    assert governance["projection_only"] is True
    assert governance["copy_creation_enabled"] is False
    assert governance["writes_tenant_state"] is False
    assert governance["writes_receipts"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False
    assert not data_root.exists()


def test_managed_copy_sla_commitment_review_denies_unscoped_actor_without_writing(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")

    response = TestClient(create_app()).post(
        "/managed-copies/sla-commitment-review",
        json={
            "request_actor": "stage18.sla-unscoped",
            "copy_id": "copy-denied",
            "tenant_id": "tenant-denied",
            "commitment_id": "uptime_commitment",
            "support_tier": "priority_support",
            "metric": "uptime_window",
            "incident": {"summary": "denied path should not open incident"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["required_scope"] == "managed_copies.sla.write"
    assert body["sla_framework_ready"] is False
    assert body["sla_review_enabled"] is False
    assert body["sla_commitments_active"] is False
    assert body["monitoring_enabled"] is False
    assert body["paging_enabled"] is False
    assert body["support_tiers_enabled"] is False
    assert body["billing_entitlements_enabled"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False

    governance = body["governance"]
    assert governance["gate"] == "permission_gate"
    assert governance["reason"] == "missing_scopes"
    assert governance["required_scope"] == "managed_copies.sla.write"
    assert governance["evidence"]["route"] == "/managed-copies/sla-commitment-review"
    assert governance["evidence"]["method"] == "POST"
    assert governance["evidence"]["required_scope_count"] == 1
    assert governance["evidence"]["actor_scope_count"] == 0
    assert not data_root.exists()


def test_managed_copy_sla_commitment_review_blocks_scoped_actor_until_stage17_closes(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    actor = "stage18.sla-reviewer"
    raw_tenant_id = "tenant-sla-secret-should-not-echo"
    raw_incident_text = "raw sla incident payload should not echo"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({actor: ["managed_copies.sla.write"]}),
    )

    response = TestClient(create_app()).post(
        "/managed-copies/sla-commitment-review",
        json={
            "request_actor": actor,
            "copy_id": "copy-123",
            "tenant_id": raw_tenant_id,
            "commitment_id": "uptime_commitment",
            "support_tier": "priority_support",
            "metric": "uptime_window",
            "incident": {"raw_text": raw_incident_text},
            "evidence_refs": ["receipt-1", "receipt-2", "receipt-3"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    encoded = json.dumps(body)
    assert body["ok"] is False
    assert body["kind"] == "francis.stage18.managed_copies.sla_commitment_review"
    assert body["status"] == "blocked_stage17_prerequisite"
    assert body["error"] == "stage17_prerequisite_not_closed"
    assert body["actor"] == actor
    assert body["copy_id_present"] is True
    assert body["tenant_id_present"] is True
    assert body["incident_present"] is True
    assert body["evidence_ref_count"] == 3
    assert raw_tenant_id not in encoded
    assert raw_incident_text not in encoded
    assert body["commitment_id"] == "uptime_commitment"
    assert body["commitment_known"] is True
    assert body["commitment_active"] is False
    assert body["commitment_requires_receipt"] is True
    assert body["support_tier"] == "priority_support"
    assert body["support_tier_known"] is True
    assert body["metric"] == "uptime_window"
    assert body["metric_known"] is True
    assert body["stage17_closed_by_receipt"] is False
    assert body["stage17_blocker"] == "stage17_operator_stage_closure_decision"
    assert body["sla_framework_ready"] is False
    assert body["sla_review_enabled"] is False
    assert body["sla_commitments_active"] is False
    assert body["monitoring_enabled"] is False
    assert body["paging_enabled"] is False
    assert body["support_tiers_enabled"] is False
    assert body["billing_entitlements_enabled"] is False
    assert body["creates_service_commitment"] is False
    assert body["pages_support"] is False
    assert body["opens_incident"] is False
    assert body["records_sla_receipt"] is False
    assert body["grants_support_authority"] is False
    assert body["receipt_ready"] is False
    assert body["writes_registry"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["expected_review_receipt_path"] == "logs/managed_copies/sla_commitment_reviews.jsonl"
    assert body["required_scope"] == "managed_copies.sla.write"
    assert body["routes"]["sla_commitment_review"] == "/managed-copies/sla-commitment-review"
    assert body["next_smallest_truthful_gap"] == "stage17_operator_stage_closure_decision"

    governance = body["governance"]
    assert governance["write_route"] is True
    assert governance["preflight_only"] is True
    assert governance["permission_scope"] == "managed_copies.sla.write"
    assert governance["permission_checked"] is True
    assert governance["sla_review_enabled"] is False
    assert governance["sla_framework_ready"] is False
    assert governance["does_not_create_service_commitment"] is True
    assert governance["does_not_enable_monitoring"] is True
    assert governance["does_not_page_support"] is True
    assert governance["does_not_open_incident"] is True
    assert governance["does_not_record_sla_receipt"] is True
    assert governance["does_not_grant_support_authority"] is True
    assert governance["does_not_echo_raw_sla_payload"] is True
    assert governance["requires_stage17_closure_receipt"] is True
    assert governance["writes_receipts"] is False
    assert governance["writes_tenant_state"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False
    assert not data_root.exists()


def test_managed_copy_rogue_recovery_contract_is_projection_only_and_disabled(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    response = TestClient(create_app()).get("/managed-copies/rogue-recovery-contract")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "francis.stage18.managed_copies.rogue_recovery_contract"
    assert body["stage"] == "Stage 18 / Managed Copies Platform"
    assert body["source_id"] == "managed_copies"
    assert body["status"] == "contract_readback_ready"
    assert body["contract_readback_ready"] is True
    assert body["rogue_recovery_ready"] is False
    assert body["rogue_detection_enabled"] is False
    assert body["halt_enabled"] is False
    assert body["quarantine_enabled"] is False
    assert body["replacement_enabled"] is False
    assert body["restore_enabled"] is False
    assert body["copy_creation_enabled"] is False
    assert body["stage17_closed_by_receipt"] is False
    assert body["stage17_blocker"] == "stage17_operator_stage_closure_decision"
    assert body["next_smallest_truthful_gap"] == "stage17_operator_stage_closure_decision"
    assert body["rogue_recovery_review_route"] == "/managed-copies/rogue-recovery-review"
    assert body["routes"]["rogue_recovery_review"] == "/managed-copies/rogue-recovery-review"

    signal_ids = {item["id"] for item in body["detection_signals"]}
    assert signal_ids == {
        "governance_drift",
        "unexpected_capability_behavior",
        "suspicious_cross_boundary_activity",
        "broken_receipt_discipline",
        "corrupted_continuity_state",
        "repeated_unexplained_failures",
        "unsafe_execution_deviation",
    }
    assert body["detection_signal_count"] == len(body["detection_signals"])
    assert all(item["status"] == "contract_only" for item in body["detection_signals"])
    assert all(item["requires_evidence_preservation"] is True for item in body["detection_signals"])

    step_by_id = {item["id"]: item for item in body["recovery_steps"]}
    assert set(step_by_id) == {"detect", "halt", "quarantine", "review", "replace", "restore"}
    assert step_by_id["detect"]["status"] == "contract_only"
    assert step_by_id["detect"]["mutates_copy_state"] is False
    assert step_by_id["halt"]["status"] == "disabled"
    assert step_by_id["halt"]["writes_receipt"] is True
    assert step_by_id["halt"]["mutates_copy_state"] is True
    assert step_by_id["quarantine"]["status"] == "disabled"
    assert step_by_id["quarantine"]["mutates_copy_state"] is True
    assert step_by_id["review"]["status"] == "contract_only"
    assert step_by_id["replace"]["status"] == "disabled"
    assert step_by_id["restore"]["status"] == "disabled"
    assert all(item["requires_operator_approval"] is True for item in body["recovery_steps"])

    assert body["required_receipts"] == [
        "rogue_detection_receipt",
        "halt_decision_receipt",
        "quarantine_receipt",
        "evidence_preservation_receipt",
        "support_review_receipt",
        "replacement_plan_receipt",
        "clean_baseline_verification_receipt",
        "restore_verification_receipt",
    ]
    assert body["replacement_sources_allowed"] == [
        "clean_core_baseline",
        "trusted_known_good_snapshot",
        "validated_global_state",
        "controlled_customer_configuration_state",
    ]
    assert body["operator_controls_required"] == [
        "explicit_operator_or_tenant_admin_decision",
        "tenant_visible_incident_state",
        "support_authority_scope_check",
        "rollback_or_replace_plan_review",
        "post_restore_verification_review",
        "revocation_path_available",
    ]
    assert body["blocked_failure_modes"] == [
        "uncontained_anomalous_instance",
        "messy_replacement_without_lineage",
        "support_team_improvisation",
        "evidence_loss_after_incident",
        "trust_collapse_after_incident",
        "hidden_vendor_control",
    ]

    assert body["read_only"] is True
    assert body["projection_only"] is True
    assert body["writes_registry"] is False
    assert body["writes_memory"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["launches_browser"] is False
    assert body["captures_screen"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["halts_copy"] is False
    assert body["quarantines_copy"] is False
    assert body["replaces_copy"] is False
    assert body["restores_copy"] is False
    assert body["support_backdoor_allowed"] is False

    governance = body["governance"]
    assert governance["read_only"] is True
    assert governance["projection_only"] is True
    assert governance["copy_creation_enabled"] is False
    assert governance["writes_tenant_state"] is False
    assert governance["writes_receipts"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False
    assert not data_root.exists()


def test_managed_copy_rogue_recovery_review_denies_unscoped_actor_without_writing(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")

    response = TestClient(create_app()).post(
        "/managed-copies/rogue-recovery-review",
        json={
            "request_actor": "stage18.rogue-unscoped",
            "copy_id": "copy-denied",
            "tenant_id": "tenant-denied",
            "signal_id": "suspicious_cross_boundary_activity",
            "action": "quarantine",
            "incident": {"summary": "denied path should not mutate copy state"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["required_scope"] == "managed_copies.rogue_recovery.write"
    assert body["rogue_recovery_review_enabled"] is False
    assert body["rogue_recovery_ready"] is False
    assert body["halt_enabled"] is False
    assert body["quarantine_enabled"] is False
    assert body["replacement_enabled"] is False
    assert body["restore_enabled"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False

    governance = body["governance"]
    assert governance["gate"] == "permission_gate"
    assert governance["reason"] == "missing_scopes"
    assert governance["required_scope"] == "managed_copies.rogue_recovery.write"
    assert governance["evidence"]["route"] == "/managed-copies/rogue-recovery-review"
    assert governance["evidence"]["method"] == "POST"
    assert governance["evidence"]["required_scope_count"] == 1
    assert governance["evidence"]["actor_scope_count"] == 0
    assert not data_root.exists()


def test_managed_copy_rogue_recovery_review_blocks_scoped_actor_until_stage17_closes(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    actor = "stage18.rogue-reviewer"
    raw_tenant_id = "tenant-rogue-secret-should-not-echo"
    raw_incident_text = "raw incident payload should not echo"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({actor: ["managed_copies.rogue_recovery.write"]}),
    )

    response = TestClient(create_app()).post(
        "/managed-copies/rogue-recovery-review",
        json={
            "request_actor": actor,
            "copy_id": "copy-123",
            "tenant_id": raw_tenant_id,
            "signal_id": "suspicious_cross_boundary_activity",
            "action": "quarantine",
            "incident": {"raw_text": raw_incident_text},
            "evidence_refs": ["receipt-1", "receipt-2"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    encoded = json.dumps(body)
    assert body["ok"] is False
    assert body["kind"] == "francis.stage18.managed_copies.rogue_recovery_review"
    assert body["status"] == "blocked_stage17_prerequisite"
    assert body["error"] == "stage17_prerequisite_not_closed"
    assert body["actor"] == actor
    assert body["copy_id_present"] is True
    assert body["tenant_id_present"] is True
    assert body["incident_present"] is True
    assert body["evidence_ref_count"] == 2
    assert raw_tenant_id not in encoded
    assert raw_incident_text not in encoded
    assert body["signal_id"] == "suspicious_cross_boundary_activity"
    assert body["signal_known"] is True
    assert body["signal_severity"] == "critical"
    assert body["action"] == "quarantine"
    assert body["action_known"] is True
    assert body["action_writes_receipt"] is True
    assert body["action_mutates_copy_state"] is True
    assert body["stage17_closed_by_receipt"] is False
    assert body["stage17_blocker"] == "stage17_operator_stage_closure_decision"
    assert body["rogue_recovery_ready"] is False
    assert body["rogue_recovery_review_enabled"] is False
    assert body["rogue_detection_enabled"] is False
    assert body["halt_enabled"] is False
    assert body["quarantine_enabled"] is False
    assert body["replacement_enabled"] is False
    assert body["restore_enabled"] is False
    assert body["halts_copy"] is False
    assert body["quarantines_copy"] is False
    assert body["replaces_copy"] is False
    assert body["restores_copy"] is False
    assert body["support_backdoor_allowed"] is False
    assert body["receipt_ready"] is False
    assert body["writes_registry"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["expected_review_receipt_path"] == "logs/managed_copies/rogue_recovery_reviews.jsonl"
    assert body["required_scope"] == "managed_copies.rogue_recovery.write"
    assert body["routes"]["rogue_recovery_review"] == "/managed-copies/rogue-recovery-review"
    assert body["next_smallest_truthful_gap"] == "stage17_operator_stage_closure_decision"

    governance = body["governance"]
    assert governance["write_route"] is True
    assert governance["preflight_only"] is True
    assert governance["permission_scope"] == "managed_copies.rogue_recovery.write"
    assert governance["permission_checked"] is True
    assert governance["rogue_recovery_review_enabled"] is False
    assert governance["does_not_detect_rogue_copy"] is True
    assert governance["does_not_halt_copy"] is True
    assert governance["does_not_quarantine_copy"] is True
    assert governance["does_not_replace_copy"] is True
    assert governance["does_not_restore_copy"] is True
    assert governance["does_not_record_rogue_recovery_receipt"] is True
    assert governance["does_not_mutate_copy_state"] is True
    assert governance["does_not_echo_raw_incident_payload"] is True
    assert governance["requires_stage17_closure_receipt"] is True
    assert governance["writes_receipts"] is False
    assert governance["writes_tenant_state"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False
    assert not data_root.exists()


def _configure_safe_delta_receipt_test_sources(
    monkeypatch,
    data_root: Path,
) -> tuple[dict[str, dict[str, Any]], Path]:
    tenant_key = "a" * 64
    state_root = f"managed_copies/tenants/{tenant_key}"
    source_state: dict[str, dict[str, Any]] = {
        "provision": {
            "copy_id": "managed_copy_safe_delta_test",
            "tenant_key": tenant_key,
            "receipt_id": "managed_copy_provision_safe_delta_test",
            "provision_fingerprint": "b" * 64,
            "state_root": state_root,
        },
        "isolation": {
            "receipt_id": "managed_copy_isolation_safe_delta_test",
            "copy_id": "managed_copy_safe_delta_test",
            "tenant_key": tenant_key,
            "provisioning_receipt_id": "managed_copy_provision_safe_delta_test",
            "state_root": state_root,
            "live_state_aligned": True,
        },
    }
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    def provision_for_copy(
        copy_id: str,
        *,
        provisioning_receipt_id: str = "",
    ) -> dict[str, Any]:
        receipt = source_state["provision"]
        if copy_id != receipt["copy_id"]:
            return {}
        if provisioning_receipt_id and provisioning_receipt_id != receipt["receipt_id"]:
            return {}
        return dict(receipt)

    def isolation_for_provision(
        provisioning_receipt_id: str,
        *,
        provision_fingerprint: str = "",
        copy_id: str = "",
    ) -> dict[str, Any]:
        provision = source_state["provision"]
        if provisioning_receipt_id != provision["receipt_id"]:
            return {}
        if provision_fingerprint and provision_fingerprint != provision["provision_fingerprint"]:
            return {}
        if copy_id and copy_id != provision["copy_id"]:
            return {}
        return dict(source_state["isolation"])

    monkeypatch.setattr(managed_copy_safe_delta, "managed_copy_provision_for_copy", provision_for_copy)
    monkeypatch.setattr(
        managed_copy_safe_delta,
        "latest_managed_copy_isolation_verification_for_provision",
        isolation_for_provision,
    )
    config_path = data_root / "managed_copies" / "tenants" / tenant_key / "config" / "managed_copy.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    (config_path.parents[1] / "receipts").mkdir(exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "safe_delta_policy": {
                    "raw_private_pooling_allowed": False,
                    "operator_review_required": True,
                }
            }
        ),
        encoding="utf-8",
    )
    return source_state, config_path


def _safe_delta_receipt_test_plan(
    source_state: dict[str, dict[str, Any]],
    *,
    actor: str = "safe-delta.test-reviewer",
    summary_fingerprint: str = "2" * 64,
) -> dict[str, Any]:
    provision = source_state["provision"]
    isolation = source_state["isolation"]
    payload = {
        "copy_id": provision["copy_id"],
        "provisioning_receipt_id": provision["receipt_id"],
        "isolation_verification_receipt_id": isolation["receipt_id"],
        "signal_class": "quality_gate_learning",
        "direction": "export",
        "candidate": {
            "signal_fingerprint": "1" * 64,
            "summary_fingerprint": summary_fingerprint,
            "lineage_fingerprint": "3" * 64,
            "source_record_count": 12,
            "contains_raw_private_data": False,
            "contains_tenant_identifiers": False,
            "redaction_review_complete": True,
            "abstraction_level": "class_level",
            "retention_class": "review_receipt_only",
        },
    }
    plan = managed_copy_safe_delta.managed_copy_safe_delta_review_plan(
        payload,
        actor=actor,
        provision_receipt=dict(provision),
        isolation_receipt=dict(isolation),
    )
    assert plan["review_contract_ready"] is True
    return plan


def _record_safe_delta_receipt(plan: dict[str, Any]) -> dict[str, Any]:
    return managed_copy_safe_delta.record_managed_copy_safe_delta_review(
        plan,
        provided_fingerprint=str(plan["review_fingerprint"]),
        confirm_review=True,
    )


def _safe_delta_receipt_test_path(
    source_state: dict[str, dict[str, Any]],
    plan: dict[str, Any],
) -> Path:
    review_directory = managed_copy_safe_delta._guarded_review_directory(
        source_state["provision"],
        source_state["isolation"],
        create=False,
    )
    assert review_directory is not None
    return managed_copy_safe_delta._review_receipt_path(
        review_directory,
        str(plan["review_fingerprint"]),
    )


def _safe_delta_receipt_test_readback(
    plan: dict[str, Any],
    *,
    review_fingerprint: str = "",
) -> dict[str, Any]:
    return managed_copy_safe_delta.managed_copy_safe_delta_review_receipts_readback(
        copy_id=str(plan["copy_id"]),
        provisioning_receipt_id=str(plan["provisioning_receipt_id"]),
        isolation_verification_receipt_id=str(plan["isolation_verification_receipt_id"]),
        review_fingerprint=review_fingerprint,
    )


def _safe_delta_decision_test_plan(
    monkeypatch,
    source_state: dict[str, dict[str, Any]],
    review: dict[str, Any],
    *,
    decision: Any = "approved",
    actor: str = "safe-delta.test-approver",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    monkeypatch.setattr(
        safe_delta_approval,
        "managed_copy_provision_for_copy",
        managed_copy_safe_delta.managed_copy_provision_for_copy,
    )
    monkeypatch.setattr(
        safe_delta_approval,
        "latest_managed_copy_isolation_verification_for_provision",
        managed_copy_safe_delta.latest_managed_copy_isolation_verification_for_provision,
    )
    payload = {
        "copy_id": source_state["provision"]["copy_id"],
        "provisioning_receipt_id": source_state["provision"]["receipt_id"],
        "isolation_verification_receipt_id": source_state["isolation"]["receipt_id"],
        "review_fingerprint": review["receipt"]["review_fingerprint"],
        "decision": decision,
        **(extra or {}),
    }
    return safe_delta_approval.managed_copy_safe_delta_decision_plan(payload, actor=actor)


@pytest.mark.parametrize("decision", ["approved", "rejected"])
def test_managed_copy_safe_delta_exact_decision_receipt_and_idempotent_replay(
    monkeypatch, tmp_path, decision: str
) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(monkeypatch, tmp_path / decision)
    review = _record_safe_delta_receipt(_safe_delta_receipt_test_plan(source_state))
    review_path = _safe_delta_receipt_test_path(source_state, review["receipt"])
    review_before = review_path.read_bytes()
    plan = _safe_delta_decision_test_plan(monkeypatch, source_state, review, decision=decision)

    assert plan["ok"] is True
    assert plan["status"] == "safe_delta_decision_ready"
    assert len(plan["decision_fingerprint"]) == 64
    wrong = safe_delta_approval.record_managed_copy_safe_delta_decision(
        plan, provided_fingerprint="0" * 64, confirmed=True
    )
    assert wrong["error"] == "safe_delta_decision_fingerprint_mismatch"
    unconfirmed = safe_delta_approval.record_managed_copy_safe_delta_decision(
        plan, provided_fingerprint=plan["decision_fingerprint"], confirmed=False
    )
    assert unconfirmed["error"] == "safe_delta_decision_confirmation_required"

    recorded = safe_delta_approval.record_managed_copy_safe_delta_decision(
        plan, provided_fingerprint=plan["decision_fingerprint"], confirmed=True
    )
    assert recorded["ok"] is True
    assert recorded["status"] == decision
    assert recorded["safe_delta_approved"] is (decision == "approved")
    assert recorded["safe_delta_rejected"] is (decision == "rejected")
    assert recorded["eligible_for_future_export_preflight"] is (decision == "approved")
    for flag in (
        "exports_delta",
        "imports_delta",
        "writes_learning",
        "executes_action",
        "writes_memory",
        "writes_registry",
        "writes_tenant_state",
        "uses_network",
        "grants_execution_authority",
        "grants_mutation_authority",
    ):
        assert recorded[flag] is False
    assert review_path.read_bytes() == review_before

    replay = safe_delta_approval.record_managed_copy_safe_delta_decision(
        plan, provided_fingerprint=plan["decision_fingerprint"], confirmed=True
    )
    assert replay["status"] == "already_decided"
    assert replay["receipt_id"] == recorded["receipt_id"]
    assert replay["writes_receipt"] is False

    readback = safe_delta_approval.managed_copy_safe_delta_decisions_readback(
        copy_id=plan["copy_id"],
        provisioning_receipt_id=plan["provisioning_receipt_id"],
        isolation_verification_receipt_id=plan["isolation_verification_receipt_id"],
        review_fingerprint=plan["review_fingerprint"],
    )
    assert readback["status"] == decision
    assert readback["valid_count"] == 1
    assert readback["latest_valid_receipt_id"] == recorded["receipt_id"]


@pytest.mark.parametrize("decision", [True, False, 0, 1, "Approved", "REJECTED", "approve", ""])
def test_managed_copy_safe_delta_decision_rejects_non_exact_values(monkeypatch, tmp_path, decision: Any) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(monkeypatch, tmp_path / "invalid")
    review = _record_safe_delta_receipt(_safe_delta_receipt_test_plan(source_state))
    plan = _safe_delta_decision_test_plan(monkeypatch, source_state, review, decision=decision)
    assert plan["ok"] is False
    assert "safe_delta_decision_invalid" in plan["blockers"]


def test_managed_copy_safe_delta_decision_rejects_unknown_fields_and_conflict(monkeypatch, tmp_path) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(monkeypatch, tmp_path / "conflict")
    review = _record_safe_delta_receipt(_safe_delta_receipt_test_plan(source_state))
    unknown = _safe_delta_decision_test_plan(monkeypatch, source_state, review, extra={"unexpected": True})
    assert unknown["ok"] is False
    assert unknown["unknown_fields"] == ["unexpected"]
    approved = _safe_delta_decision_test_plan(monkeypatch, source_state, review, decision="approved")
    first = safe_delta_approval.record_managed_copy_safe_delta_decision(
        approved, provided_fingerprint=approved["decision_fingerprint"], confirmed=True
    )
    assert first["ok"] is True, first
    rejected = _safe_delta_decision_test_plan(monkeypatch, source_state, review, decision="rejected")
    conflict = safe_delta_approval.record_managed_copy_safe_delta_decision(
        rejected, provided_fingerprint=rejected["decision_fingerprint"], confirmed=True
    )
    assert conflict["error"] == "safe_delta_decision_conflict"
    assert conflict["writes_receipt"] is False


def test_managed_copy_safe_delta_decision_fails_closed_on_policy_and_live_lineage_drift(monkeypatch, tmp_path) -> None:
    source_state, config_path = _configure_safe_delta_receipt_test_sources(monkeypatch, tmp_path / "drift")
    review = _record_safe_delta_receipt(_safe_delta_receipt_test_plan(source_state))
    baseline = _safe_delta_decision_test_plan(monkeypatch, source_state, review)
    assert baseline["ok"] is True

    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["safe_delta_policy"]["operator_review_required"] = False
    config_path.write_text(json.dumps(config), encoding="utf-8")
    policy_drift = _safe_delta_decision_test_plan(monkeypatch, source_state, review)
    assert policy_drift["ok"] is False
    assert "safe_delta_tenant_policy_not_current" in policy_drift["blockers"]

    config["safe_delta_policy"]["operator_review_required"] = True
    config_path.write_text(json.dumps(config), encoding="utf-8")
    source_state["isolation"]["live_state_aligned"] = False
    lineage_drift = _safe_delta_decision_test_plan(monkeypatch, source_state, review)
    assert lineage_drift["ok"] is False
    assert "safe_delta_isolation_lineage_not_live" in lineage_drift["blockers"]


def test_managed_copy_safe_delta_decision_readback_rejects_tampering_and_production_is_empty(
    monkeypatch, tmp_path
) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(monkeypatch, tmp_path / "readback")
    review = _record_safe_delta_receipt(_safe_delta_receipt_test_plan(source_state))
    plan = _safe_delta_decision_test_plan(monkeypatch, source_state, review)
    recorded = safe_delta_approval.record_managed_copy_safe_delta_decision(
        plan, provided_fingerprint=plan["decision_fingerprint"], confirmed=True
    )
    assert recorded["ok"] is True, recorded
    directory = safe_delta_approval._decision_directory(plan, create=False)
    assert directory is not None
    path = next(directory.glob("*.json"))
    receipt = json.loads(path.read_text(encoding="utf-8"))
    receipt["exports_delta"] = True
    path.write_text(json.dumps(receipt), encoding="utf-8")
    invalid = safe_delta_approval.managed_copy_safe_delta_decisions_readback(
        copy_id=plan["copy_id"],
        provisioning_receipt_id=plan["provisioning_receipt_id"],
        isolation_verification_receipt_id=plan["isolation_verification_receipt_id"],
        review_fingerprint=plan["review_fingerprint"],
    )
    assert invalid["valid_count"] == 0
    assert invalid["safe_delta_approved"] is False
    assert recorded["receipt_id"]

    from francis.managed_copy_isolation import latest_managed_copy_isolation_verification_for_provision
    from francis.managed_copy_provisioning import managed_copy_provision_for_copy

    production_empty_root = tmp_path / "production-empty"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(production_empty_root))
    monkeypatch.setattr(safe_delta_approval, "managed_copy_provision_for_copy", managed_copy_provision_for_copy)
    monkeypatch.setattr(
        safe_delta_approval,
        "latest_managed_copy_isolation_verification_for_provision",
        latest_managed_copy_isolation_verification_for_provision,
    )
    empty = safe_delta_approval.managed_copy_safe_delta_decisions_readback(
        copy_id=plan["copy_id"],
        provisioning_receipt_id=plan["provisioning_receipt_id"],
        isolation_verification_receipt_id=plan["isolation_verification_receipt_id"],
        review_fingerprint=plan["review_fingerprint"],
    )
    assert empty["status"] == "empty"
    assert empty["count"] == 0
    assert empty["valid_count"] == 0
    assert empty["latest_valid_receipt"] == {}
    assert empty["safe_delta_approved"] is False
    assert not production_empty_root.exists()


def test_managed_copy_safe_delta_decision_redacts_actor_before_fingerprint_receipt_audit_and_replay(
    monkeypatch, tmp_path
) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(monkeypatch, tmp_path / "actor-redaction")
    review = _record_safe_delta_receipt(_safe_delta_receipt_test_plan(source_state))
    raw_secret = "super-secret-actor-value-123456"
    raw_actor = f"operator@example.com token={raw_secret}"
    audit_events: list[dict[str, Any]] = []

    def capture_audit(event: str, **fields: Any) -> dict[str, Any]:
        payload = {"event": event, **fields}
        audit_events.append(payload)
        return payload

    monkeypatch.setattr(safe_delta_approval, "audit_record", capture_audit)
    plan = _safe_delta_decision_test_plan(monkeypatch, source_state, review, actor=raw_actor)
    assert plan["ok"] is True
    assert raw_secret not in plan["actor"]
    assert raw_actor not in json.dumps(plan)
    assert len(plan["actor"]) <= 240

    recorded = safe_delta_approval.record_managed_copy_safe_delta_decision(
        plan, provided_fingerprint=plan["decision_fingerprint"], confirmed=True
    )
    replay_plan = _safe_delta_decision_test_plan(monkeypatch, source_state, review, actor=raw_actor)
    replay = safe_delta_approval.record_managed_copy_safe_delta_decision(
        replay_plan, provided_fingerprint=replay_plan["decision_fingerprint"], confirmed=True
    )
    readback = safe_delta_approval.managed_copy_safe_delta_decisions_readback(
        copy_id=plan["copy_id"],
        provisioning_receipt_id=plan["provisioning_receipt_id"],
        isolation_verification_receipt_id=plan["isolation_verification_receipt_id"],
        review_fingerprint=plan["review_fingerprint"],
    )
    directory = safe_delta_approval._decision_directory(plan, create=False)
    assert directory is not None
    serialized = "\n".join(
        [json.dumps(recorded), json.dumps(replay), json.dumps(readback), json.dumps(audit_events)]
        + [path.read_text(encoding="utf-8") for path in directory.glob("*.json")]
    )
    assert raw_secret not in serialized
    assert raw_actor not in serialized
    assert replay["status"] == "already_decided"
    assert replay["receipt_id"] == recorded["receipt_id"]
    assert replay_plan["decision_fingerprint"] == plan["decision_fingerprint"]
    assert audit_events[0]["actor"] == plan["actor"]


def test_managed_copy_safe_delta_decision_rejects_actor_mutated_after_planning_without_writes(
    monkeypatch, tmp_path
) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(monkeypatch, tmp_path / "actor-mutation")
    review = _record_safe_delta_receipt(_safe_delta_receipt_test_plan(source_state))
    plan = _safe_delta_decision_test_plan(monkeypatch, source_state, review)
    audit_events: list[dict[str, Any]] = []
    monkeypatch.setattr(
        safe_delta_approval,
        "audit_record",
        lambda event, **fields: audit_events.append({"event": event, **fields}),
    )
    decision_directory = safe_delta_approval._decision_directory(plan, create=False)
    assert decision_directory is not None
    assert not decision_directory.exists()
    raw_secret = "post-plan-secret-value-123456"
    plan["actor"] = f"attacker@example.com token={raw_secret}"

    result = safe_delta_approval.record_managed_copy_safe_delta_decision(
        plan, provided_fingerprint=plan["decision_fingerprint"], confirmed=True
    )

    assert result["ok"] is False
    assert result["status"] == "blocked_safe_delta_decision_actor"
    assert result["error"] == "safe_delta_decision_actor_not_canonical"
    assert result["writes_receipt"] is False
    assert result["writes_tenant_state"] is False
    assert result["grants_execution_authority"] is False
    assert audit_events == []
    assert not decision_directory.exists()
    assert raw_secret not in json.dumps(result)


def test_managed_copy_safe_delta_decision_rejects_canonical_actor_substitution_without_writes(
    monkeypatch, tmp_path
) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(monkeypatch, tmp_path / "actor-substitution")
    review = _record_safe_delta_receipt(_safe_delta_receipt_test_plan(source_state))
    plan = _safe_delta_decision_test_plan(monkeypatch, source_state, review, actor="safe-delta.original-approver")
    audit_events: list[dict[str, Any]] = []
    monkeypatch.setattr(
        safe_delta_approval,
        "audit_record",
        lambda event, **fields: audit_events.append({"event": event, **fields}),
    )
    decision_directory = safe_delta_approval._decision_directory(plan, create=False)
    assert decision_directory is not None
    assert not decision_directory.exists()
    plan["actor"] = "safe-delta.substituted-approver"

    result = safe_delta_approval.record_managed_copy_safe_delta_decision(
        plan, provided_fingerprint=plan["decision_fingerprint"], confirmed=True
    )

    assert result["ok"] is False
    assert result["status"] == "blocked_safe_delta_decision_fingerprint"
    assert result["error"] == "safe_delta_decision_fingerprint_mismatch"
    assert result["writes_receipt"] is False
    assert result["writes_tenant_state"] is False
    assert result["grants_execution_authority"] is False
    assert audit_events == []
    assert not decision_directory.exists()


def test_managed_copy_safe_delta_decision_readback_filters_exact_requested_review(monkeypatch, tmp_path) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(monkeypatch, tmp_path / "two-reviews")
    review_a = _record_safe_delta_receipt(
        _safe_delta_receipt_test_plan(source_state, actor="safe-delta.reviewer-a", summary_fingerprint="a" * 64)
    )
    review_b = _record_safe_delta_receipt(
        _safe_delta_receipt_test_plan(source_state, actor="safe-delta.reviewer-b", summary_fingerprint="b" * 64)
    )
    plan_a = _safe_delta_decision_test_plan(monkeypatch, source_state, review_a, decision="approved")
    plan_b = _safe_delta_decision_test_plan(monkeypatch, source_state, review_b, decision="rejected")
    recorded_a = safe_delta_approval.record_managed_copy_safe_delta_decision(
        plan_a, provided_fingerprint=plan_a["decision_fingerprint"], confirmed=True
    )
    recorded_b = safe_delta_approval.record_managed_copy_safe_delta_decision(
        plan_b, provided_fingerprint=plan_b["decision_fingerprint"], confirmed=True
    )
    assert recorded_a["ok"] is True
    assert recorded_b["ok"] is True

    readback_a = safe_delta_approval.managed_copy_safe_delta_decisions_readback(
        copy_id=plan_a["copy_id"],
        provisioning_receipt_id=plan_a["provisioning_receipt_id"],
        isolation_verification_receipt_id=plan_a["isolation_verification_receipt_id"],
        review_fingerprint=plan_a["review_fingerprint"],
    )
    readback_b = safe_delta_approval.managed_copy_safe_delta_decisions_readback(
        copy_id=plan_b["copy_id"],
        provisioning_receipt_id=plan_b["provisioning_receipt_id"],
        isolation_verification_receipt_id=plan_b["isolation_verification_receipt_id"],
        review_fingerprint=plan_b["review_fingerprint"],
    )
    assert readback_a["count"] == readback_a["valid_count"] == 1
    assert readback_a["decision"] == "approved"
    assert readback_a["latest_valid_receipt_id"] == recorded_a["receipt_id"]
    assert recorded_b["receipt_id"] not in json.dumps(readback_a)
    assert readback_b["count"] == readback_b["valid_count"] == 1
    assert readback_b["decision"] == "rejected"
    assert readback_b["latest_valid_receipt_id"] == recorded_b["receipt_id"]
    assert recorded_a["receipt_id"] not in json.dumps(readback_b)


def test_managed_copy_safe_delta_decision_short_receipt_path_supports_long_windows_data_root(
    monkeypatch, tmp_path
) -> None:
    tenant_key = "a" * 64
    placeholder_path = (
        tmp_path.parent / "x" / "managed_copies" / "tenants" / tenant_key / "receipts" / "sda" / f"{'f' * 16}.json"
    )
    padding_length = max(1, 238 - len(str(placeholder_path)) + 1)
    data_root = tmp_path.parent / ("l" * padding_length)
    source_state, _ = _configure_safe_delta_receipt_test_sources(monkeypatch, data_root)
    review = _record_safe_delta_receipt(_safe_delta_receipt_test_plan(source_state))
    plan = _safe_delta_decision_test_plan(monkeypatch, source_state, review)
    directory = safe_delta_approval._decision_directory(plan, create=False)
    assert directory is not None
    receipt_path = directory / f"{plan['review_fingerprint'][:16]}.json"
    full_fingerprint_path = receipt_path.with_name(f"{plan['review_fingerprint']}.json")

    result = safe_delta_approval.record_managed_copy_safe_delta_decision(
        plan, provided_fingerprint=plan["decision_fingerprint"], confirmed=True
    )

    assert len(str(receipt_path)) < 260
    assert len(str(full_fingerprint_path)) >= 260
    assert result["ok"] is True
    assert receipt_path.exists()


def test_managed_copy_safe_delta_decision_rejects_cross_tenant_lineage(monkeypatch, tmp_path) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(monkeypatch, tmp_path / "cross-tenant")
    review = _record_safe_delta_receipt(_safe_delta_receipt_test_plan(source_state))
    source_state["provision"]["tenant_key"] = "f" * 64
    plan = _safe_delta_decision_test_plan(monkeypatch, source_state, review)
    assert plan["ok"] is False
    assert "safe_delta_review_receipt_missing_or_invalid" in plan["blockers"]


def test_managed_copy_safe_delta_decision_denies_unscoped_actor_without_writing(monkeypatch, tmp_path) -> None:
    data_root = tmp_path / "denied"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")
    body = (
        TestClient(create_app())
        .post(
            "/managed-copies/safe-delta-decision",
            json={"request_actor": "unscoped", "decision": "approved", "dry_run": True},
        )
        .json()
    )
    assert body["ok"] is False
    assert body["error"] == "api_permission_denied"
    assert body["required_scope"] == "managed_copies.safe_delta.approval.write"
    assert body["writes_receipt"] is False
    assert body["writes_tenant_state"] is False
    assert body["grants_execution_authority"] is False
    assert not data_root.exists()


def _safe_delta_export_preflight_payload(
    plan: dict[str, Any], decision: dict[str, Any], *, actor: str = "safe-delta.export-preflight"
) -> dict[str, Any]:
    return {
        "request_actor": actor,
        "copy_id": plan["copy_id"],
        "provisioning_receipt_id": plan["provisioning_receipt_id"],
        "isolation_verification_receipt_id": plan["isolation_verification_receipt_id"],
        "review_fingerprint": plan["review_fingerprint"],
        "decision_receipt_id": decision["receipt_id"],
        "dry_run": True,
    }


def test_managed_copy_safe_delta_export_preflight_approved_is_deterministic_and_has_no_effects(
    monkeypatch, tmp_path
) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(monkeypatch, tmp_path / "export-ready")
    raw_review_marker = "distinctive-review-marker-must-not-project"
    review = _record_safe_delta_receipt(
        _safe_delta_receipt_test_plan(source_state, actor=f"safe-delta.{raw_review_marker}")
    )
    decision_plan = _safe_delta_decision_test_plan(monkeypatch, source_state, review, decision="approved")
    decision = safe_delta_approval.record_managed_copy_safe_delta_decision(
        decision_plan, provided_fingerprint=decision_plan["decision_fingerprint"], confirmed=True
    )
    payload = _safe_delta_export_preflight_payload(decision_plan, decision)
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))

    first = safe_delta_export.managed_copy_safe_delta_export_preflight(payload, actor=payload["request_actor"])
    second = safe_delta_export.managed_copy_safe_delta_export_preflight(payload, actor=payload["request_actor"])

    assert first["ok"] is True
    assert first["status"] == "export_preflight_ready"
    assert first["contract"] == "stage18_managed_copy_safe_delta_export_preflight_v1"
    assert len(first["export_preflight_fingerprint"]) == 64
    assert second == first
    assert first["decision"] == "approved"
    assert first["approved_for_future_export_preflight"] is True
    assert first["contains_raw_candidate_material"] is False
    assert first["contains_raw_tenant_identity"] is False
    for flag in (
        "writes_file",
        "writes_receipt",
        "writes_artifact",
        "writes_manifest",
        "exports_delta",
        "imports_delta",
        "writes_learning",
        "writes_memory",
        "writes_registry",
        "writes_tenant_state",
        "uses_network",
        "executes_action",
        "grants_export_authority",
        "grants_execution_authority",
        "grants_mutation_authority",
        "safe_delta_exported",
        "safe_delta_flow_active",
    ):
        assert first[flag] is False
    after = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    assert after == before
    assert "candidate" not in first
    assert "source_record_count" not in json.dumps(first)
    assert raw_review_marker not in json.dumps(first)

    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({payload["request_actor"]: ["managed_copies.safe_delta.export.preflight"]}),
    )
    api_body = (
        TestClient(create_app())
        .post(
            "/managed-copies/safe-delta-export-preflight",
            json=payload,
        )
        .json()
    )
    assert api_body["status"] == "export_preflight_ready"
    assert api_body["safe_delta_exported"] is False
    assert api_body["safe_delta_flow_active"] is False
    assert api_body["grants_export_authority"] is False


def test_managed_copy_safe_delta_export_preflight_rejects_direct_actor_substitution_before_readback(
    monkeypatch,
) -> None:
    calls = {"review": 0, "decision": 0}

    def review_readback(**kwargs: Any) -> dict[str, Any]:
        calls["review"] += 1
        return {}

    def decision_readback(**kwargs: Any) -> dict[str, Any]:
        calls["decision"] += 1
        return {}

    monkeypatch.setattr(safe_delta_export, "managed_copy_safe_delta_review_receipts_readback", review_readback)
    monkeypatch.setattr(safe_delta_export, "managed_copy_safe_delta_decisions_readback", decision_readback)
    payload = {
        "request_actor": "safe-delta.payload-actor",
        "copy_id": "managed_copy_actor_lineage",
        "provisioning_receipt_id": "managed_copy_provision_actor_lineage",
        "isolation_verification_receipt_id": "managed_copy_isolation_actor_lineage",
        "review_fingerprint": "a" * 64,
        "decision_receipt_id": "managed_copy_safe_delta_decision_actor_lineage",
        "dry_run": True,
    }

    result = safe_delta_export.managed_copy_safe_delta_export_preflight(
        payload,
        actor="safe-delta.authoritative-actor",
    )

    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert result["blockers"] == ["safe_delta_export_preflight_actor_lineage_mismatch"]
    assert result["export_preflight_fingerprint"] == ""
    assert result["approved_for_future_export_preflight"] is False
    assert result["writes_receipt"] is False
    assert result["exports_delta"] is False
    assert result["grants_export_authority"] is False
    assert calls == {"review": 0, "decision": 0}


def test_managed_copy_safe_delta_export_preflight_rejection_and_schema_fail_closed(monkeypatch, tmp_path) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(monkeypatch, tmp_path / "export-blocked")
    review = _record_safe_delta_receipt(_safe_delta_receipt_test_plan(source_state))
    decision_plan = _safe_delta_decision_test_plan(monkeypatch, source_state, review, decision="rejected")
    decision = safe_delta_approval.record_managed_copy_safe_delta_decision(
        decision_plan, provided_fingerprint=decision_plan["decision_fingerprint"], confirmed=True
    )
    payload = _safe_delta_export_preflight_payload(decision_plan, decision)
    rejected = safe_delta_export.managed_copy_safe_delta_export_preflight(payload, actor=payload["request_actor"])
    assert rejected["ok"] is False
    assert "safe_delta_export_preflight_decision_rejected" in rejected["blockers"]
    assert rejected["grants_export_authority"] is False

    schema_cases = (
        (
            {key: value for key, value in payload.items() if key != "dry_run"},
            "safe_delta_export_preflight_dry_run_true_required",
        ),
        ({**payload, "dry_run": None}, "safe_delta_export_preflight_dry_run_true_required"),
        ({**payload, "dry_run": "true"}, "safe_delta_export_preflight_dry_run_true_required"),
        ({**payload, "dry_run": 0}, "safe_delta_export_preflight_dry_run_true_required"),
        ({**payload, "actor": payload["request_actor"]}, "safe_delta_export_preflight_actor_lineage_mismatch"),
        ({**payload, "copy_id": ""}, "safe_delta_export_preflight_copy_id_required"),
        ({**payload, "provisioning_receipt_id": ""}, "safe_delta_export_preflight_provisioning_receipt_id_required"),
        (
            {**payload, "isolation_verification_receipt_id": ""},
            "safe_delta_export_preflight_isolation_receipt_id_required",
        ),
        ({**payload, "review_fingerprint": "not-sha256"}, "safe_delta_export_preflight_review_fingerprint_invalid"),
        ({**payload, "unexpected": True}, "safe_delta_export_preflight_unknown_fields"),
        ({**payload, "decision_receipt_id": "foreign"}, "safe_delta_export_preflight_decision_receipt_id_invalid"),
    )
    for changes, blocker in schema_cases:
        result = safe_delta_export.managed_copy_safe_delta_export_preflight(changes, actor=payload["request_actor"])
        assert result["ok"] is False
        assert blocker in result["blockers"]
        assert result["writes_receipt"] is False
        assert result["exports_delta"] is False


def test_managed_copy_safe_delta_export_preflight_rejects_cross_review_decision_and_tampering(
    monkeypatch, tmp_path
) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(monkeypatch, tmp_path / "export-cross-review")
    review_a = _record_safe_delta_receipt(
        _safe_delta_receipt_test_plan(source_state, actor="safe-delta.export-review-a", summary_fingerprint="a" * 64)
    )
    review_b = _record_safe_delta_receipt(
        _safe_delta_receipt_test_plan(source_state, actor="safe-delta.export-review-b", summary_fingerprint="b" * 64)
    )
    plan_a = _safe_delta_decision_test_plan(monkeypatch, source_state, review_a, decision="approved")
    plan_b = _safe_delta_decision_test_plan(monkeypatch, source_state, review_b, decision="approved")
    decision_b = safe_delta_approval.record_managed_copy_safe_delta_decision(
        plan_b, provided_fingerprint=plan_b["decision_fingerprint"], confirmed=True
    )
    cross_review_payload = _safe_delta_export_preflight_payload(plan_a, decision_b)
    cross_review = safe_delta_export.managed_copy_safe_delta_export_preflight(
        cross_review_payload, actor=cross_review_payload["request_actor"]
    )
    assert cross_review["ok"] is False
    assert "safe_delta_export_preflight_decision_receipt_missing_or_mismatch" in cross_review["blockers"]
    assert cross_review["export_preflight_fingerprint"] == ""

    valid_payload = _safe_delta_export_preflight_payload(plan_b, decision_b)
    assert (
        safe_delta_export.managed_copy_safe_delta_export_preflight(valid_payload, actor=valid_payload["request_actor"])[
            "ok"
        ]
        is True
    )
    decision_directory = safe_delta_approval._decision_directory(plan_b, create=False)
    assert decision_directory is not None
    decision_path = next(decision_directory.glob(f"{plan_b['review_fingerprint'][:16]}.json"))
    tampered = json.loads(decision_path.read_text(encoding="utf-8"))
    tampered["unexpected"] = True
    decision_path.write_text(json.dumps(tampered), encoding="utf-8")
    blocked = safe_delta_export.managed_copy_safe_delta_export_preflight(
        valid_payload, actor=valid_payload["request_actor"]
    )
    assert blocked["ok"] is False
    assert "safe_delta_export_preflight_decision_receipt_missing_or_mismatch" in blocked["blockers"]
    assert blocked["writes_receipt"] is False
    assert blocked["exports_delta"] is False


def test_managed_copy_safe_delta_export_preflight_blocks_policy_drift_and_real_empty_sources(
    monkeypatch, tmp_path
) -> None:
    source_state, config_path = _configure_safe_delta_receipt_test_sources(monkeypatch, tmp_path / "export-drift")
    review = _record_safe_delta_receipt(_safe_delta_receipt_test_plan(source_state))
    decision_plan = _safe_delta_decision_test_plan(monkeypatch, source_state, review, decision="approved")
    decision = safe_delta_approval.record_managed_copy_safe_delta_decision(
        decision_plan, provided_fingerprint=decision_plan["decision_fingerprint"], confirmed=True
    )
    payload = _safe_delta_export_preflight_payload(decision_plan, decision)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["safe_delta_policy"]["operator_review_required"] = False
    config_path.write_text(json.dumps(config), encoding="utf-8")
    drifted = safe_delta_export.managed_copy_safe_delta_export_preflight(payload, actor=payload["request_actor"])
    assert drifted["ok"] is False
    assert "safe_delta_export_preflight_review_not_live_valid" in drifted["blockers"]

    from francis.managed_copy_isolation import latest_managed_copy_isolation_verification_for_provision
    from francis.managed_copy_provisioning import managed_copy_provision_for_copy

    monkeypatch.setattr(managed_copy_safe_delta, "managed_copy_provision_for_copy", managed_copy_provision_for_copy)
    monkeypatch.setattr(
        managed_copy_safe_delta,
        "latest_managed_copy_isolation_verification_for_provision",
        latest_managed_copy_isolation_verification_for_provision,
    )
    monkeypatch.setattr(safe_delta_approval, "managed_copy_provision_for_copy", managed_copy_provision_for_copy)
    monkeypatch.setattr(
        safe_delta_approval,
        "latest_managed_copy_isolation_verification_for_provision",
        latest_managed_copy_isolation_verification_for_provision,
    )
    empty_root = tmp_path / "export-production-empty"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(empty_root))
    empty = safe_delta_export.managed_copy_safe_delta_export_preflight(payload, actor=payload["request_actor"])
    assert empty["ok"] is False
    assert empty["export_preflight_fingerprint"] == ""
    assert empty["writes_file"] is False
    assert empty["exports_delta"] is False
    assert not empty_root.exists()


def test_managed_copy_safe_delta_export_preflight_denies_unscoped_before_lineage_projection(
    monkeypatch, tmp_path
) -> None:
    data_root = tmp_path / "export-denied"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")
    body = (
        TestClient(create_app())
        .post(
            "/managed-copies/safe-delta-export-preflight",
            json={
                "request_actor": "safe-delta.export-unscoped",
                "copy_id": "secret-copy",
                "provisioning_receipt_id": "secret-provision",
                "isolation_verification_receipt_id": "secret-isolation",
                "review_fingerprint": "a" * 64,
                "decision_receipt_id": "managed_copy_safe_delta_decision_secret",
                "dry_run": True,
            },
        )
        .json()
    )
    assert body["ok"] is False
    assert body["error"] == "api_permission_denied"
    assert body["required_scope"] == "managed_copies.safe_delta.export.preflight"
    assert "secret-copy" not in json.dumps(body)
    assert body["writes_receipt"] is False
    assert body["writes_tenant_state"] is False
    assert body["exports_delta"] is False
    assert body["grants_export_authority"] is False
    assert body["grants_execution_authority"] is False
    assert not data_root.exists()


def _safe_delta_export_authorization_plan(monkeypatch, source_state, decision_plan, decision):
    monkeypatch.setattr(
        safe_delta_export_authorization,
        "managed_copy_provision_for_copy",
        managed_copy_safe_delta.managed_copy_provision_for_copy,
    )
    monkeypatch.setattr(
        safe_delta_export_authorization,
        "latest_managed_copy_isolation_verification_for_provision",
        managed_copy_safe_delta.latest_managed_copy_isolation_verification_for_provision,
    )
    actor = "safe-delta.export-requester"
    preflight_payload = _safe_delta_export_preflight_payload(decision_plan, decision, actor=actor)
    preflight = safe_delta_export.managed_copy_safe_delta_export_preflight(preflight_payload, actor=actor)
    payload = {
        "request_actor": actor,
        "copy_id": decision_plan["copy_id"],
        "provisioning_receipt_id": decision_plan["provisioning_receipt_id"],
        "isolation_verification_receipt_id": decision_plan["isolation_verification_receipt_id"],
        "review_fingerprint": decision_plan["review_fingerprint"],
        "decision_receipt_id": decision["receipt_id"],
        "preflight_fingerprint": preflight["export_preflight_fingerprint"],
        "export_class": "safe_delta_signal",
        "retention_class": "authorization_request_receipt_only",
        "destination_class": "governed_export_boundary",
        "purpose_fingerprint": "9" * 64,
        "dry_run": True,
    }
    plan = safe_delta_export_authorization.managed_copy_safe_delta_export_authorization_request_plan(
        payload, actor=actor
    )
    return payload, plan


def test_managed_copy_safe_delta_export_authorization_request_plan_record_readback_is_pending_only(
    monkeypatch, tmp_path
) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(monkeypatch, tmp_path / "export-request")
    review = _record_safe_delta_receipt(_safe_delta_receipt_test_plan(source_state))
    decision_plan = _safe_delta_decision_test_plan(monkeypatch, source_state, review, decision="approved")
    decision = safe_delta_approval.record_managed_copy_safe_delta_decision(
        decision_plan, provided_fingerprint=decision_plan["decision_fingerprint"], confirmed=True
    )
    payload, plan = _safe_delta_export_authorization_plan(monkeypatch, source_state, decision_plan, decision)
    assert plan["ok"] is True
    assert plan["status"] == "export_authorization_request_ready"
    assert len(plan["request_fingerprint"]) == 64
    assert plan["writes_receipt"] is False

    unconfirmed = safe_delta_export_authorization.record_managed_copy_safe_delta_export_authorization_request(
        plan, provided_fingerprint=plan["request_fingerprint"], confirmed=False
    )
    assert unconfirmed["error"] == "safe_delta_export_authorization_request_confirmation_required"
    recorded = safe_delta_export_authorization.record_managed_copy_safe_delta_export_authorization_request(
        plan, provided_fingerprint=plan["request_fingerprint"], confirmed=True
    )
    assert recorded["status"] == "export_authorization_pending", recorded
    assert recorded["writes_receipt"] is True
    replay = safe_delta_export_authorization.record_managed_copy_safe_delta_export_authorization_request(
        plan, provided_fingerprint=plan["request_fingerprint"], confirmed=True
    )
    assert replay["status"] == "already_requested"
    assert replay["receipt_id"] == recorded["receipt_id"]
    assert replay["writes_receipt"] is False
    for flag in (
        "export_approved",
        "export_executed",
        "safe_delta_exported",
        "safe_delta_flow_active",
        "writes_artifact",
        "writes_manifest",
        "writes_payload",
        "writes_tenant_state",
        "writes_memory",
        "writes_registry",
        "writes_learning",
        "uses_network",
        "grants_approval_authority",
        "grants_export_authority",
        "grants_execution_authority",
        "grants_mutation_authority",
    ):
        assert recorded[flag] is False
    readback = safe_delta_export_authorization.managed_copy_safe_delta_export_authorization_requests_readback(
        copy_id=payload["copy_id"],
        provisioning_receipt_id=payload["provisioning_receipt_id"],
        isolation_verification_receipt_id=payload["isolation_verification_receipt_id"],
    )
    assert readback["status"] == "export_authorization_pending"
    assert readback["valid_count"] == 1
    assert readback["latest_valid_receipt_id"] == recorded["receipt_id"]
    serialized = json.dumps(recorded)
    assert "https://export.example.invalid" not in serialized
    assert "secret-export-credential" not in serialized
    assert recorded["receipt"]["governance"]["contains_credentials"] is False
    assert recorded["receipt"]["governance"]["contains_concrete_destination"] is False


def test_managed_copy_safe_delta_export_authorization_request_schema_and_record_drift_fail_closed(
    monkeypatch, tmp_path
) -> None:
    source_state, config_path = _configure_safe_delta_receipt_test_sources(
        monkeypatch, tmp_path / "export-request-drift"
    )
    review = _record_safe_delta_receipt(_safe_delta_receipt_test_plan(source_state))
    decision_plan = _safe_delta_decision_test_plan(monkeypatch, source_state, review, decision="approved")
    decision = safe_delta_approval.record_managed_copy_safe_delta_decision(
        decision_plan, provided_fingerprint=decision_plan["decision_fingerprint"], confirmed=True
    )
    payload, plan = _safe_delta_export_authorization_plan(monkeypatch, source_state, decision_plan, decision)
    for changes in (
        {"unexpected": True},
        {"export_class": "raw_payload"},
        {"retention_class": "forever"},
        {"destination_class": "https://example.invalid"},
        {"purpose_fingerprint": "bad"},
        {"dry_run": 1},
    ):
        blocked = safe_delta_export_authorization.managed_copy_safe_delta_export_authorization_request_plan(
            {**payload, **changes}, actor=payload["request_actor"]
        )
        assert blocked["ok"] is False
        assert blocked["request_fingerprint"] == ""
        assert blocked["writes_receipt"] is False
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["safe_delta_policy"]["operator_review_required"] = False
    config_path.write_text(json.dumps(config), encoding="utf-8")
    drifted = safe_delta_export_authorization.record_managed_copy_safe_delta_export_authorization_request(
        plan, provided_fingerprint=plan["request_fingerprint"], confirmed=True
    )
    assert drifted["ok"] is False
    assert drifted["error"] == "safe_delta_export_authorization_request_plan_drift"
    assert drifted["writes_receipt"] is False


def test_managed_copy_safe_delta_export_authorization_request_unscoped_and_production_empty(
    monkeypatch, tmp_path
) -> None:
    root = tmp_path / "export-request-empty"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")
    body = (
        TestClient(create_app())
        .post(
            "/managed-copies/safe-delta-export-authorization-request",
            json={"request_actor": "unscoped", "dry_run": True},
        )
        .json()
    )
    assert body["error"] == "api_permission_denied"
    assert body["required_scope"] == "managed_copies.safe_delta.export.authorization.request"
    assert not root.exists()
    readback = safe_delta_export_authorization.managed_copy_safe_delta_export_authorization_requests_readback(
        copy_id="managed_copy_missing",
        provisioning_receipt_id="managed_copy_provision_missing",
        isolation_verification_receipt_id="managed_copy_isolation_missing",
    )
    assert readback["status"] == "empty"
    assert readback["count"] == 0


def test_managed_copy_safe_delta_malformed_existing_receipt_fails_closed(
    monkeypatch,
    tmp_path,
) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(
        monkeypatch,
        tmp_path.parent / "sd-malformed",
    )
    plan = _safe_delta_receipt_test_plan(source_state)
    receipt_path = _safe_delta_receipt_test_path(source_state, plan)
    malformed_receipt = '{"raw_customer_data":"must-not-overwrite"'
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(malformed_receipt, encoding="utf-8")

    result = _record_safe_delta_receipt(plan)

    assert result["ok"] is False
    assert result["status"] == "blocked_safe_delta_review_receipt_conflict"
    assert result["error"] == "safe_delta_review_receipt_conflict"
    assert result["writes_receipt"] is False
    assert receipt_path.read_text(encoding="utf-8") == malformed_receipt
    assert "must-not-overwrite" not in json.dumps(result)


def test_managed_copy_safe_delta_full_fingerprint_prefix_collision_fails_closed(
    monkeypatch,
    tmp_path,
) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(
        monkeypatch,
        tmp_path.parent / "sd-collision",
    )
    first_plan = _safe_delta_receipt_test_plan(source_state)
    colliding_plan = _safe_delta_receipt_test_plan(
        source_state,
        actor="safe-delta.second-reviewer",
        summary_fingerprint="4" * 64,
    )
    assert first_plan["review_fingerprint"] != colliding_plan["review_fingerprint"]
    collision_path = _safe_delta_receipt_test_path(source_state, first_plan)

    def colliding_receipt_path(review_directory: Path, review_fingerprint: str) -> Path:
        assert review_directory == collision_path.parent
        assert review_fingerprint in {
            first_plan["review_fingerprint"],
            colliding_plan["review_fingerprint"],
        }
        return collision_path

    def colliding_guarded_receipt_path(
        provision_receipt: dict[str, Any],
        isolation_receipt: dict[str, Any],
        review_fingerprint: str,
        *,
        require_live: bool,
    ) -> Path:
        assert provision_receipt == source_state["provision"]
        assert isolation_receipt == source_state["isolation"]
        assert require_live is True
        return colliding_receipt_path(collision_path.parent, review_fingerprint)

    monkeypatch.setattr(managed_copy_safe_delta, "_review_receipt_path", colliding_receipt_path)
    monkeypatch.setattr(
        managed_copy_safe_delta,
        "_guarded_review_receipt_path",
        colliding_guarded_receipt_path,
    )
    first_result = _record_safe_delta_receipt(first_plan)
    original_receipt = collision_path.read_text(encoding="utf-8")

    collision_result = _record_safe_delta_receipt(colliding_plan)

    assert first_result["ok"] is True
    assert collision_result["ok"] is False
    assert collision_result["status"] == "blocked_safe_delta_review_receipt_conflict"
    assert collision_result["error"] == "safe_delta_review_receipt_conflict"
    assert collision_result["writes_receipt"] is False
    assert collision_path.read_text(encoding="utf-8") == original_receipt


def test_managed_copy_safe_delta_readback_rejects_same_prefix_full_fingerprint_collision(
    monkeypatch,
    tmp_path,
) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(
        monkeypatch,
        tmp_path.parent / "sd-readback-collision",
    )
    plan = _safe_delta_receipt_test_plan(source_state)
    recorded = _record_safe_delta_receipt(plan)
    stored_fingerprint = str(plan["review_fingerprint"])
    replacement = "0" if stored_fingerprint[16] != "0" else "1"
    colliding_fingerprint = f"{stored_fingerprint[:16]}{replacement}{stored_fingerprint[17:]}"
    assert colliding_fingerprint != stored_fingerprint
    assert colliding_fingerprint[:16] == stored_fingerprint[:16]

    readback = _safe_delta_receipt_test_readback(
        plan,
        review_fingerprint=colliding_fingerprint,
    )

    assert recorded["ok"] is True
    assert readback["status"] == "receipt_validation_failed"
    assert readback["count"] == 1
    assert readback["valid_count"] == 0
    assert readback["invalid_receipt_count"] == 1
    assert readback["latest_valid_receipt"] == {}


def test_managed_copy_safe_delta_readback_redacts_invalid_latest_candidate(
    monkeypatch,
    tmp_path,
) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(
        monkeypatch,
        tmp_path.parent / "sd-invalid-latest",
    )
    plan = _safe_delta_receipt_test_plan(source_state)
    recorded = _record_safe_delta_receipt(plan)
    receipt_path = _safe_delta_receipt_test_path(source_state, plan)
    raw_customer_marker = "private-customer-latest-marker"
    invalid_path = receipt_path.with_name("ffffffffffffffff.json")
    invalid_path.write_text(
        json.dumps(
            {
                "kind": "invalid-safe-delta-receipt",
                "receipt_id": "invalid-latest",
                "recorded_ts": int(recorded["receipt"]["recorded_ts"]) + 1,
                "raw_customer_data": raw_customer_marker,
            }
        ),
        encoding="utf-8",
    )

    readback = _safe_delta_receipt_test_readback(plan)

    assert readback["status"] == "receipt_validation_failed"
    assert readback["count"] == 2
    assert readback["valid_count"] == 1
    assert readback["invalid_receipt_count"] == 1
    assert readback["receipt_set_valid"] is False
    assert readback["latest_receipt_valid"] is True
    assert readback["latest_receipt_id"] == recorded["receipt_id"]
    assert raw_customer_marker not in json.dumps(readback)


def test_managed_copy_safe_delta_readback_reports_post_write_source_drift(
    monkeypatch,
    tmp_path,
) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(
        monkeypatch,
        tmp_path.parent / "sd-source-drift",
    )
    plan = _safe_delta_receipt_test_plan(source_state)
    recorded = _record_safe_delta_receipt(plan)
    source_state["isolation"]["live_state_aligned"] = False

    readback = _safe_delta_receipt_test_readback(plan)

    assert recorded["ok"] is True
    assert readback["status"] == "source_drift_detected"
    assert readback["valid_count"] == 1
    assert readback["live_aligned_count"] == 0
    assert readback["latest_receipt_valid"] is True
    assert readback["latest_receipt"]["live_source_boundary_aligned"] is False
    assert readback["latest_receipt"]["live_source_boundary_drift_detected"] is True
    assert readback["next_smallest_truthful_gap"] == "stage18_safe_delta_source_boundary_reverification"


def test_managed_copy_safe_delta_short_receipt_path_supports_long_windows_data_root(
    monkeypatch,
    tmp_path,
) -> None:
    tenant_key = "a" * 64
    placeholder_path = (
        tmp_path.parent / "x" / "managed_copies" / "tenants" / tenant_key / "receipts" / "sd" / f"{'f' * 16}.json"
    )
    padding_length = max(1, 238 - len(str(placeholder_path)) + 1)
    data_root = tmp_path.parent / ("l" * padding_length)
    source_state, _ = _configure_safe_delta_receipt_test_sources(monkeypatch, data_root)
    plan = _safe_delta_receipt_test_plan(source_state)
    receipt_path = _safe_delta_receipt_test_path(source_state, plan)
    full_fingerprint_path = receipt_path.with_name(f"{plan['review_fingerprint']}.json")

    result = _record_safe_delta_receipt(plan)

    assert len(str(receipt_path)) < 260
    assert len(str(full_fingerprint_path)) >= 260
    assert result["ok"] is True
    assert receipt_path.exists()


def test_managed_copy_safe_delta_receipt_creation_is_exclusive(
    monkeypatch,
    tmp_path,
) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(
        monkeypatch,
        tmp_path.parent / "sd-exclusive",
    )
    plan = _safe_delta_receipt_test_plan(source_state)
    original_write = managed_copy_safe_delta._write_json_atomic
    competing_receipt = '{"unknown_receipt":"private-race-marker"}\n'

    def create_competing_receipt_before_write(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(competing_receipt, encoding="utf-8")
        original_write(path, payload)

    monkeypatch.setattr(
        managed_copy_safe_delta,
        "_write_json_atomic",
        create_competing_receipt_before_write,
    )

    result = _record_safe_delta_receipt(plan)
    receipt_path = _safe_delta_receipt_test_path(source_state, plan)

    assert result["ok"] is False
    assert result["status"] == "blocked_safe_delta_review_receipt_conflict"
    assert result["error"] == "safe_delta_review_receipt_conflict"
    assert result["writes_receipt"] is False
    assert receipt_path.read_text(encoding="utf-8") == competing_receipt
    assert "private-race-marker" not in json.dumps(result)


def test_managed_copy_safe_delta_readback_recomputes_candidate_checks(
    monkeypatch,
    tmp_path,
) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(
        monkeypatch,
        tmp_path.parent / "sd-recomputed-checks",
    )
    plan = _safe_delta_receipt_test_plan(source_state)
    recorded = _record_safe_delta_receipt(plan)
    original_path = _safe_delta_receipt_test_path(source_state, plan)
    receipt = dict(recorded["receipt"])
    receipt["candidate"] = dict(receipt["candidate"])
    receipt["candidate"]["contains_raw_private_data"] = True
    receipt["candidate_fingerprint"] = managed_copy_safe_delta._fingerprint(receipt["candidate"])
    receipt["review_fingerprint"] = managed_copy_safe_delta._review_fingerprint(
        actor=str(receipt["actor"]),
        copy_id=str(receipt["copy_id"]),
        tenant_key=str(receipt["tenant_key"]),
        provisioning_receipt_id=str(receipt["provisioning_receipt_id"]),
        isolation_receipt_id=str(receipt["isolation_verification_receipt_id"]),
        signal_class=str(receipt["signal_class"]),
        direction=str(receipt["direction"]),
        candidate=receipt["candidate"],
        candidate_checks=receipt["candidate_checks"],
        tenant_policy_checks=receipt["tenant_policy_checks"],
    )
    receipt["receipt_id"] = f"managed_copy_safe_delta_review_{receipt['review_fingerprint'][:16]}"
    receipt["receipt_fingerprint"] = managed_copy_safe_delta._receipt_fingerprint(receipt)
    tampered_path = original_path.with_name(f"{receipt['review_fingerprint'][:16]}.json")
    original_path.unlink()
    tampered_path.write_text(json.dumps(receipt), encoding="utf-8")

    readback = _safe_delta_receipt_test_readback(plan)

    assert readback["status"] == "receipt_validation_failed"
    assert readback["valid_count"] == 0
    assert readback["invalid_receipt_count"] == 1
    assert readback["items"] == []
    assert "contains_raw_private_data" not in json.dumps(readback)


def test_managed_copy_safe_delta_readback_rejects_unknown_receipt_schema_without_echoing(
    monkeypatch,
    tmp_path,
) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(
        monkeypatch,
        tmp_path.parent / "sd-exact-schema",
    )
    plan = _safe_delta_receipt_test_plan(source_state)
    recorded = _record_safe_delta_receipt(plan)
    receipt_path = _safe_delta_receipt_test_path(source_state, plan)
    receipt = dict(recorded["receipt"])
    raw_marker = "private-receipt-schema-marker"
    receipt["raw_customer_data"] = raw_marker
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    readback = _safe_delta_receipt_test_readback(plan)

    assert readback["status"] == "receipt_validation_failed"
    assert readback["valid_count"] == 0
    assert readback["invalid_receipt_count"] == 1
    assert raw_marker not in json.dumps(readback)


def test_managed_copy_safe_delta_readback_rejects_unknown_governance_schema_without_echoing(
    monkeypatch,
    tmp_path,
) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(
        monkeypatch,
        tmp_path.parent / "sd-governance-schema",
    )
    plan = _safe_delta_receipt_test_plan(source_state)
    recorded = _record_safe_delta_receipt(plan)
    receipt_path = _safe_delta_receipt_test_path(source_state, plan)
    receipt = dict(recorded["receipt"])
    raw_marker = "private-governance-schema-marker"
    receipt["governance"] = dict(receipt["governance"])
    receipt["governance"]["raw_governance_data"] = raw_marker
    receipt["receipt_fingerprint"] = managed_copy_safe_delta._receipt_fingerprint(receipt)
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    readback = _safe_delta_receipt_test_readback(plan)

    assert readback["status"] == "receipt_validation_failed"
    assert readback["valid_count"] == 0
    assert readback["invalid_receipt_count"] == 1
    assert raw_marker not in json.dumps(readback)


def test_managed_copy_safe_delta_readback_rejects_integer_nested_boolean_types(
    monkeypatch,
    tmp_path,
) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(
        monkeypatch,
        tmp_path.parent / "sd-nested-boolean-types",
    )
    plan = _safe_delta_receipt_test_plan(source_state)
    recorded = _record_safe_delta_receipt(plan)
    receipt_path = _safe_delta_receipt_test_path(source_state, plan)
    baseline = _safe_delta_receipt_test_readback(plan)
    mutations = (
        ("governance", "exact_candidate_schema_enforced", 1),
        ("governance", "raw_candidate_payload_stored", 0),
        ("candidate_checks", "ready", 1),
        ("tenant_policy_checks", "ready", 1),
    )

    assert baseline["status"] == "operator_approval_required"
    assert baseline["valid_count"] == 1
    for section, field, integer_value in mutations:
        receipt = json.loads(json.dumps(recorded["receipt"]))
        nested = receipt[section] if section == "governance" else receipt[section][0]
        expected_boolean = nested[field]
        assert isinstance(expected_boolean, bool)
        nested[field] = integer_value
        assert nested[field] == expected_boolean
        assert not isinstance(nested[field], bool)
        assert set(receipt) == set(recorded["receipt"])
        assert receipt["candidate"] == recorded["receipt"]["candidate"]
        receipt["receipt_fingerprint"] = managed_copy_safe_delta._receipt_fingerprint(receipt)
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

        readback = _safe_delta_receipt_test_readback(plan)

        assert readback["status"] == "receipt_validation_failed"
        assert readback["valid_count"] == 0
        assert readback["invalid_receipt_count"] == 1
        assert readback["latest_valid_receipt"] == {}


def test_managed_copy_safe_delta_readback_rejects_malformed_candidate_json_type(
    monkeypatch,
    tmp_path,
) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(
        monkeypatch,
        tmp_path.parent / "sd-candidate-type",
    )
    plan = _safe_delta_receipt_test_plan(source_state)
    recorded = _record_safe_delta_receipt(plan)
    receipt_path = _safe_delta_receipt_test_path(source_state, plan)
    receipt = dict(recorded["receipt"])
    raw_marker = "private-malformed-candidate-marker"
    receipt["candidate"] = [raw_marker]
    receipt["candidate_fingerprint"] = managed_copy_safe_delta._fingerprint(receipt["candidate"])
    receipt["receipt_fingerprint"] = managed_copy_safe_delta._receipt_fingerprint(receipt)
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    readback = _safe_delta_receipt_test_readback(plan)

    assert readback["status"] == "receipt_validation_failed"
    assert readback["valid_count"] == 0
    assert readback["invalid_receipt_count"] == 1
    assert raw_marker not in json.dumps(readback)


def test_managed_copy_safe_delta_receipt_binds_id_timestamp_filename_and_tenant(
    monkeypatch,
    tmp_path,
) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(
        monkeypatch,
        tmp_path.parent / "sd-receipt-binding",
    )
    plan = _safe_delta_receipt_test_plan(source_state)
    recorded = _record_safe_delta_receipt(plan)
    receipt = dict(recorded["receipt"])
    receipt_path = _safe_delta_receipt_test_path(source_state, plan)
    validation = {
        "path": receipt_path,
        "review_directory": receipt_path.parent,
        "copy_id": str(plan["copy_id"]),
        "tenant_key": str(plan["tenant_key"]),
        "provisioning_receipt_id": str(plan["provisioning_receipt_id"]),
        "isolation_receipt_id": str(plan["isolation_verification_receipt_id"]),
    }
    assert managed_copy_safe_delta._valid_review_receipt(receipt, **validation)

    mismatched_id = dict(receipt)
    mismatched_id["receipt_id"] = "managed_copy_safe_delta_review_0000000000000000"
    mismatched_id["receipt_fingerprint"] = managed_copy_safe_delta._receipt_fingerprint(mismatched_id)
    timestamp_changed = dict(receipt)
    timestamp_changed["recorded_ts"] = int(receipt["recorded_ts"]) + 1
    wrong_filename = receipt_path.with_name("ffffffffffffffff.json")
    transplanted_directory = receipt_path.parents[3] / ("b" * 64) / "receipts" / "sd"
    transplanted_path = transplanted_directory / receipt_path.name

    assert not managed_copy_safe_delta._valid_review_receipt(mismatched_id, **validation)
    assert not managed_copy_safe_delta._valid_review_receipt(timestamp_changed, **validation)
    assert not managed_copy_safe_delta._valid_review_receipt(
        receipt,
        **{**validation, "path": wrong_filename},
    )
    assert not managed_copy_safe_delta._valid_review_receipt(
        receipt,
        **{
            **validation,
            "path": transplanted_path,
            "review_directory": transplanted_directory,
            "tenant_key": "b" * 64,
        },
    )


def test_managed_copy_safe_delta_latest_selection_does_not_trust_timestamp(
    monkeypatch,
    tmp_path,
) -> None:
    source_state, _ = _configure_safe_delta_receipt_test_sources(
        monkeypatch,
        tmp_path.parent / "sd-latest-order",
    )
    plans = [
        _safe_delta_receipt_test_plan(source_state),
        _safe_delta_receipt_test_plan(
            source_state,
            actor="safe-delta.timestamp-order-reviewer",
            summary_fingerprint="4" * 64,
        ),
    ]
    recorded = {str(plan["review_fingerprint"]): _record_safe_delta_receipt(plan) for plan in plans}
    canonical_latest_fingerprint = max(recorded)
    for fingerprint, result in recorded.items():
        receipt = dict(result["receipt"])
        receipt["recorded_ts"] = 1 if fingerprint == canonical_latest_fingerprint else 2_000_000_000
        receipt["receipt_fingerprint"] = managed_copy_safe_delta._receipt_fingerprint(receipt)
        plan = next(item for item in plans if item["review_fingerprint"] == fingerprint)
        _safe_delta_receipt_test_path(source_state, plan).write_text(json.dumps(receipt), encoding="utf-8")

    readback = _safe_delta_receipt_test_readback(plans[0])

    assert readback["valid_count"] == 2
    assert readback["latest_valid_receipt_id"] == recorded[canonical_latest_fingerprint]["receipt_id"]


def test_managed_copy_safe_delta_readback_scopes_invalidity_to_requested_lineage(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path.parent / "sd-lineage-scope"
    source_state, _ = _configure_safe_delta_receipt_test_sources(monkeypatch, data_root)
    plan = _safe_delta_receipt_test_plan(source_state)
    recorded = _record_safe_delta_receipt(plan)
    unrelated_marker = "private-unrelated-tenant-marker"
    unrelated_path = data_root / "managed_copies" / "tenants" / ("b" * 64) / "receipts" / "sd" / "ffffffffffffffff.json"
    unrelated_path.parent.mkdir(parents=True)
    unrelated_path.write_text(json.dumps({"raw_customer_data": unrelated_marker}), encoding="utf-8")

    readback = _safe_delta_receipt_test_readback(plan)

    assert readback["status"] == "operator_approval_required"
    assert readback["count"] == 1
    assert readback["valid_count"] == 1
    assert readback["invalid_receipt_count"] == 0
    assert readback["latest_valid_receipt_id"] == recorded["receipt_id"]
    assert unrelated_marker not in json.dumps(readback)


def test_managed_copy_safe_delta_production_source_loaded_readback_is_empty(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "source-loaded-empty"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    readback = managed_copy_safe_delta.managed_copy_safe_delta_review_receipts_readback(
        copy_id="managed_copy_source_loaded_empty",
        provisioning_receipt_id="managed_copy_provision_source_loaded_empty",
        isolation_verification_receipt_id="managed_copy_isolation_source_loaded_empty",
    )

    assert readback["status"] == "source_drift_detected"
    assert readback["count"] == 0
    assert readback["valid_count"] == 0
    assert readback["invalid_receipt_count"] == 0
    assert readback["items"] == []
    assert readback["latest_valid_receipt"] == {}
    assert not data_root.exists()


def _create_directory_redirect_or_skip(link: Path, target: Path) -> str:
    try:
        os.symlink(target, link, target_is_directory=True)
    except OSError as symlink_error:
        if os.name != "nt":
            pytest.skip(f"directory symlink unavailable: {symlink_error}")
        junction = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        if junction.returncode != 0:
            pytest.skip(
                "directory symlink and Windows junction unavailable: "
                f"symlink={symlink_error}; junction_exit={junction.returncode}"
            )
        return "junction"
    return "symlink"


def test_managed_copy_safe_delta_rejects_real_review_directory_redirect(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path.parent / "sd-real-link-boundary"
    source_state, _ = _configure_safe_delta_receipt_test_sources(monkeypatch, data_root)
    plan = _safe_delta_receipt_test_plan(source_state)
    review_directory = _safe_delta_receipt_test_path(source_state, plan).parent
    redirect_target = tmp_path.parent / "sd-real-link-target"
    redirect_target.mkdir()
    link_kind = _create_directory_redirect_or_skip(review_directory, redirect_target)
    try:
        result = _record_safe_delta_receipt(plan)

        assert result["ok"] is False
        assert result["status"] == "blocked_safe_delta_review_path_boundary"
        assert result["error"] == "safe_delta_review_path_boundary_invalid"
        assert result["writes_receipt"] is False
        assert list(redirect_target.glob("*.json")) == []
    finally:
        if link_kind == "symlink":
            review_directory.unlink(missing_ok=True)
        elif review_directory.exists():
            review_directory.rmdir()


def test_managed_copy_safe_delta_model_contract_denies_raw_pooling_and_exports(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    response = TestClient(create_app()).get("/managed-copies/safe-delta-model-contract")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "francis.stage18.managed_copies.safe_delta_model_contract"
    assert body["stage"] == "Stage 18 / Managed Copies Platform"
    assert body["source_id"] == "managed_copies"
    assert body["status"] == "contract_readback_ready"
    assert body["contract_readback_ready"] is True
    assert body["safe_delta_model_ready"] is False
    assert body["delta_export_enabled"] is False
    assert body["delta_import_enabled"] is False
    assert body["learning_write_enabled"] is False
    assert body["copy_creation_enabled"] is False
    assert body["stage17_closed_by_receipt"] is False
    assert body["stage17_blocker"] == "stage17_operator_stage_closure_decision"
    assert body["next_smallest_truthful_gap"] == "stage17_operator_stage_closure_decision"
    assert body["safe_delta_review_route"] == "/managed-copies/safe-delta-review"
    assert body["routes"]["safe_delta_review"] == "/managed-copies/safe-delta-review"

    allowed_ids = {item["id"] for item in body["allowed_signal_classes"]}
    assert allowed_ids == {
        "capability_metadata",
        "policy_hardening_delta",
        "quality_gate_learning",
        "regression_case_summary",
        "performance_signal",
        "class_level_friction_pattern",
        "non_sensitive_outcome_metric",
    }
    assert body["allowed_signal_count"] == len(body["allowed_signal_classes"])
    assert all(item["allowed"] is True for item in body["allowed_signal_classes"])
    assert all(item["status"] == "contract_only" for item in body["allowed_signal_classes"])
    assert all(item["redaction_required"] is True for item in body["allowed_signal_classes"])

    denied_ids = {item["id"] for item in body["denied_signal_classes"]}
    assert denied_ids == {
        "raw_customer_artifact",
        "tenant_memory_trace",
        "tenant_receipt_payload",
        "credential_or_connector_secret",
        "support_session_private_context",
        "tenant_identifying_metadata",
    }
    assert body["denied_signal_count"] == len(body["denied_signal_classes"])
    assert all(item["allowed"] is False for item in body["denied_signal_classes"])
    assert all(item["status"] == "denied" for item in body["denied_signal_classes"])

    assert body["approval_gates_required"] == [
        "tenant_policy_allows_safe_delta_export",
        "tenant_admin_or_operator_approval",
        "redaction_and_abstraction_review",
        "lineage_attribution_review",
        "risk_tier_review",
        "revocation_and_retention_review",
    ]
    assert body["required_receipts"] == [
        "safe_delta_preflight_receipt",
        "redaction_review_receipt",
        "tenant_policy_allowance_receipt",
        "operator_approval_receipt",
        "delta_lineage_receipt",
        "safe_delta_export_receipt",
        "core_learning_ingest_receipt",
    ]
    assert body["flow_states"] == [
        "candidate_detected",
        "redaction_pending",
        "operator_review_required",
        "tenant_policy_blocked",
        "approved_for_delta",
        "export_disabled",
        "ingest_disabled",
        "revoked",
    ]
    assert body["blocked_failure_modes"] == [
        "raw_private_data_pooling",
        "tenant_reidentification",
        "cross_customer_contamination",
        "unattributed_core_learning",
        "policy_bypass_learning",
        "support_confusion",
    ]

    assert body["read_only"] is True
    assert body["projection_only"] is True
    assert body["writes_registry"] is False
    assert body["writes_memory"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["launches_browser"] is False
    assert body["captures_screen"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["raw_private_pooling_allowed"] is False
    assert body["cross_tenant_data_flow_allowed"] is False
    assert body["tenant_reidentification_allowed"] is False
    assert body["unattributed_learning_allowed"] is False
    assert body["safe_delta_flow_active"] is False

    governance = body["governance"]
    assert governance["read_only"] is True
    assert governance["projection_only"] is True
    assert governance["copy_creation_enabled"] is False
    assert governance["writes_tenant_state"] is False
    assert governance["writes_receipts"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False
    assert not data_root.exists()


def test_managed_copy_safe_delta_review_denies_unscoped_actor_without_writing(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")

    response = TestClient(create_app()).post(
        "/managed-copies/safe-delta-review",
        json={
            "request_actor": "stage18.safe-delta-unscoped",
            "copy_id": "copy-denied",
            "tenant_id": "tenant-denied",
            "signal_class": "policy_hardening_delta",
            "direction": "export",
            "candidate": {"summary": "denied path should not write learning"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["required_scope"] == "managed_copies.safe_delta.write"
    assert body["safe_delta_review_enabled"] is False
    assert body["safe_delta_flow_active"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False

    governance = body["governance"]
    assert governance["gate"] == "permission_gate"
    assert governance["reason"] == "missing_scopes"
    assert governance["required_scope"] == "managed_copies.safe_delta.write"
    assert governance["evidence"]["route"] == "/managed-copies/safe-delta-review"
    assert governance["evidence"]["method"] == "POST"
    assert governance["evidence"]["required_scope_count"] == 1
    assert governance["evidence"]["actor_scope_count"] == 0
    assert not data_root.exists()


def test_managed_copy_safe_delta_review_blocks_scoped_actor_until_stage17_closes(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    actor = "stage18.safe-delta-reviewer"
    raw_tenant_id = "tenant-safe-delta-secret-should-not-echo"
    raw_candidate_text = "raw customer artifact text should not echo"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({actor: ["managed_copies.safe_delta.write"]}),
    )

    response = TestClient(create_app()).post(
        "/managed-copies/safe-delta-review",
        json={
            "request_actor": actor,
            "copy_id": "copy-123",
            "tenant_id": raw_tenant_id,
            "signal_class": "policy_hardening_delta",
            "direction": "export",
            "candidate": {"raw_text": raw_candidate_text},
        },
    )

    assert response.status_code == 200
    body = response.json()
    encoded = json.dumps(body)
    assert body["ok"] is False
    assert body["kind"] == "francis.stage18.managed_copies.safe_delta_review"
    assert body["status"] == "blocked_stage17_prerequisite"
    assert body["error"] == "stage17_prerequisite_not_closed"
    assert body["actor"] == actor
    assert body["copy_id_present"] is True
    assert body["tenant_id_present"] is True
    assert body["candidate_present"] is True
    assert raw_tenant_id not in encoded
    assert raw_candidate_text not in encoded
    assert body["signal_class"] == "policy_hardening_delta"
    assert body["signal_class_known"] is True
    assert body["signal_allowed_by_contract"] is True
    assert body["signal_denied_by_contract"] is False
    assert body["direction"] == "export"
    assert body["stage17_closed_by_receipt"] is False
    assert body["stage17_blocker"] == "stage17_operator_stage_closure_decision"
    assert body["safe_delta_model_ready"] is False
    assert body["safe_delta_review_enabled"] is False
    assert body["safe_delta_approved"] is False
    assert body["safe_delta_flow_active"] is False
    assert body["delta_export_enabled"] is False
    assert body["delta_import_enabled"] is False
    assert body["learning_write_enabled"] is False
    assert body["raw_private_pooling_allowed"] is False
    assert body["cross_tenant_data_flow_allowed"] is False
    assert body["tenant_reidentification_allowed"] is False
    assert body["unattributed_learning_allowed"] is False
    assert body["receipt_ready"] is False
    assert body["writes_registry"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["expected_review_receipt_path"] == (
        "managed_copies/tenants/{tenant_key}/receipts/sd/{review_fingerprint_prefix}.json"
    )
    assert body["required_scope"] == "managed_copies.safe_delta.write"
    assert body["routes"]["safe_delta_review"] == "/managed-copies/safe-delta-review"
    assert body["next_smallest_truthful_gap"] == "stage17_operator_stage_closure_decision"

    unknown_signal = "private-signal-class-marker"
    unknown_direction = "private-direction-marker"
    redacted_unknowns = (
        TestClient(create_app())
        .post(
            "/managed-copies/safe-delta-review",
            json={
                "request_actor": actor,
                "signal_class": unknown_signal,
                "direction": unknown_direction,
            },
        )
        .json()
    )
    assert redacted_unknowns["signal_class"] == "unknown"
    assert redacted_unknowns["signal_class_known"] is False
    assert redacted_unknowns["direction"] == "unknown"
    assert unknown_signal not in json.dumps(redacted_unknowns)
    assert unknown_direction not in json.dumps(redacted_unknowns)

    governance = body["governance"]
    assert governance["write_route"] is True
    assert governance["preflight_only"] is True
    assert governance["permission_scope"] == "managed_copies.safe_delta.write"
    assert governance["permission_checked"] is True
    assert governance["safe_delta_review_enabled"] is False
    assert governance["safe_delta_flow_active"] is False
    assert governance["does_not_export_delta"] is True
    assert governance["does_not_import_delta"] is True
    assert governance["does_not_write_learning"] is True
    assert governance["does_not_record_safe_delta_receipt"] is True
    assert governance["does_not_echo_raw_signal_payload"] is True
    assert governance["requires_stage17_closure_receipt"] is True
    assert governance["raw_private_pooling_allowed"] is False
    assert governance["cross_tenant_data_flow_allowed"] is False
    assert governance["tenant_reidentification_allowed"] is False
    assert governance["unattributed_learning_allowed"] is False
    assert governance["writes_receipts"] is False
    assert governance["writes_tenant_state"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False
    assert not data_root.exists()


def test_managed_copy_isolation_rules_contract_is_projection_only_and_unenforced(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    response = TestClient(create_app()).get("/managed-copies/isolation-rules-contract")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "francis.stage18.managed_copies.isolation_rules_contract"
    assert body["stage"] == "Stage 18 / Managed Copies Platform"
    assert body["source_id"] == "managed_copies"
    assert body["status"] == "contract_readback_ready"
    assert body["contract_readback_ready"] is True
    assert body["isolation_rules_ready"] is False
    assert body["isolation_enforcement_enabled"] is False
    assert body["copy_creation_enabled"] is False
    assert body["stage17_closed_by_receipt"] is False
    assert body["stage17_blocker"] == "stage17_operator_stage_closure_decision"
    assert body["next_smallest_truthful_gap"] == "stage17_operator_stage_closure_decision"
    assert body["isolation_verification_route"] == "/managed-copies/isolation-verification"
    assert body["routes"]["isolation_verification"] == "/managed-copies/isolation-verification"

    domain_ids = {item["id"] for item in body["isolation_domains"]}
    assert {
        "tenant_data",
        "tenant_memory",
        "tenant_receipts",
        "tenant_connectors",
        "tenant_capability_packs",
        "tenant_policy",
        "support_operator_authority",
    } == domain_ids
    assert body["required_domain_count"] == len(body["isolation_domains"])
    assert body["enforced_domain_count"] == 0
    assert all(item["isolated"] is False for item in body["isolation_domains"])
    assert all(item["enforcement_status"] == "contract_only" for item in body["isolation_domains"])

    assert body["support_access_rules"] == [
        "support_operator_identity_required",
        "tenant_admin_approval_required",
        "scope_limited_support_session_required",
        "time_bound_support_access_required",
        "support_action_receipts_required",
        "tenant_visible_support_activity_required",
        "support_revocation_required",
    ]
    assert body["cross_tenant_rules"] == [
        "no_raw_private_data_pooling",
        "no_cross_tenant_memory_reads",
        "no_cross_tenant_receipt_writes",
        "no_cross_tenant_connector_reuse",
        "no_unattributed_safe_delta_flow",
        "no_uncontrolled_capability_pack_forks",
    ]
    assert body["verification_receipts_required"] == [
        "tenant_data_isolation_receipt",
        "tenant_memory_isolation_receipt",
        "tenant_receipt_isolation_receipt",
        "tenant_connector_isolation_receipt",
        "tenant_policy_overlay_receipt",
        "support_authority_boundary_receipt",
        "cross_tenant_flow_denial_receipt",
    ]
    assert body["blocked_failure_modes"] == [
        "privacy_weak_pooling",
        "cross_customer_leakage",
        "support_backdoor",
        "ambiguous_operator_rights",
        "uncontrolled_forks",
        "policy_thin_managed_service",
    ]

    assert body["read_only"] is True
    assert body["projection_only"] is True
    assert body["writes_registry"] is False
    assert body["writes_memory"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["launches_browser"] is False
    assert body["captures_screen"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["cross_tenant_data_flow_allowed"] is False
    assert body["raw_private_pooling_allowed"] is False
    assert body["support_backdoor_allowed"] is False
    assert body["tenant_state_shared"] is False

    governance = body["governance"]
    assert governance["read_only"] is True
    assert governance["projection_only"] is True
    assert governance["copy_creation_enabled"] is False
    assert governance["writes_tenant_state"] is False
    assert governance["writes_receipts"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False
    assert not data_root.exists()


def test_managed_copy_isolation_verification_denies_unscoped_actor_without_writing(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")

    response = TestClient(create_app()).post(
        "/managed-copies/isolation-verification",
        json={
            "request_actor": "stage18.isolation-unscoped",
            "copy_id": "copy-denied",
            "tenant_id": "tenant-denied",
            "domains": ["tenant_data", "tenant_memory"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["required_scope"] == "managed_copies.isolation_verification.write"
    assert body["isolation_enforcement_enabled"] is False
    assert body["isolation_verification_enabled"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False

    governance = body["governance"]
    assert governance["gate"] == "permission_gate"
    assert governance["reason"] == "missing_scopes"
    assert governance["required_scope"] == "managed_copies.isolation_verification.write"
    assert governance["evidence"]["route"] == "/managed-copies/isolation-verification"
    assert governance["evidence"]["method"] == "POST"
    assert governance["evidence"]["required_scope_count"] == 1
    assert governance["evidence"]["actor_scope_count"] == 0
    assert not data_root.exists()


def test_managed_copy_isolation_verification_blocks_scoped_actor_until_stage17_closes(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    actor = "stage18.isolation-verifier"
    raw_tenant_id = "tenant-isolation-secret-should-not-echo"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({actor: ["managed_copies.isolation_verification.write"]}),
    )

    response = TestClient(create_app()).post(
        "/managed-copies/isolation-verification",
        json={
            "request_actor": actor,
            "copy_id": "copy-123",
            "tenant_id": raw_tenant_id,
            "domains": [
                "tenant_data",
                "tenant_memory",
                "tenant_receipts",
                "tenant_connectors",
                "tenant_capability_packs",
                "tenant_policy",
                "support_operator_authority",
                "unexpected_cross_tenant_domain",
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["kind"] == "francis.stage18.managed_copies.isolation_verification"
    assert body["status"] == "blocked_stage17_prerequisite"
    assert body["error"] == "stage17_prerequisite_not_closed"
    assert body["actor"] == actor
    assert body["copy_id_present"] is True
    assert body["tenant_id_present"] is True
    assert raw_tenant_id not in json.dumps(body)
    assert body["requested_domain_count"] == 8
    assert body["requested_unknown_domains"] == ["unexpected_cross_tenant_domain"]
    assert body["required_domain_count"] == 7
    assert body["verified_domain_count"] == 0
    assert all(item["requested"] is True for item in body["domain_checks"])
    assert all(item["verified"] is False for item in body["domain_checks"])
    assert all(item["status"] == "blocked_stage17_prerequisite" for item in body["domain_checks"])
    assert body["stage17_closed_by_receipt"] is False
    assert body["stage17_blocker"] == "stage17_operator_stage_closure_decision"
    assert body["isolation_rules_ready"] is False
    assert body["isolation_enforcement_enabled"] is False
    assert body["isolation_verification_enabled"] is False
    assert body["isolation_verified"] is False
    assert body["tenant_state_shared"] is False
    assert body["cross_tenant_data_flow_allowed"] is False
    assert body["raw_private_pooling_allowed"] is False
    assert body["support_backdoor_allowed"] is False
    assert body["receipt_ready"] is False
    assert body["writes_registry"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["expected_verification_receipt_path"] == "logs/managed_copies/isolation_verifications.jsonl"
    assert body["required_scope"] == "managed_copies.isolation_verification.write"
    assert body["routes"]["isolation_verification"] == "/managed-copies/isolation-verification"
    assert body["next_smallest_truthful_gap"] == "stage17_operator_stage_closure_decision"

    governance = body["governance"]
    assert governance["write_route"] is True
    assert governance["preflight_only"] is True
    assert governance["permission_scope"] == "managed_copies.isolation_verification.write"
    assert governance["permission_checked"] is True
    assert governance["isolation_enforcement_enabled"] is False
    assert governance["isolation_verification_enabled"] is False
    assert governance["does_not_enforce_isolation"] is True
    assert governance["does_not_record_isolation_receipt"] is True
    assert governance["does_not_mutate_tenant_state"] is True
    assert governance["does_not_echo_raw_tenant_payload"] is True
    assert governance["requires_stage17_closure_receipt"] is True
    assert governance["writes_receipts"] is False
    assert governance["writes_tenant_state"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False
    assert not data_root.exists()


def test_managed_copy_creation_contract_is_projection_only_and_disabled(
    monkeypatch,
    tmp_path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    response = TestClient(create_app()).get("/managed-copies/copy-creation-contract")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "francis.stage18.managed_copies.copy_creation_contract"
    assert body["stage"] == "Stage 18 / Managed Copies Platform"
    assert body["source_id"] == "managed_copies"
    assert body["status"] == "contract_readback_ready"
    assert body["contract_readback_ready"] is True
    assert body["copy_creation_enabled"] is False
    assert body["copy_creation_allowed"] is False
    assert body["stage17_closed_by_receipt"] is False
    assert body["stage17_blocker"] == "stage17_operator_stage_closure_decision"
    assert body["next_smallest_truthful_gap"] == "stage17_operator_stage_closure_decision"
    assert body["copy_creation_request_route"] == "/managed-copies/copy-creation-request"
    assert body["routes"]["copy_creation_request"] == "/managed-copies/copy-creation-request"
    assert body["routes"]["copy_creation_preflight"] == "/managed-copies/copy-creation-preflight"
    assert body["routes"]["copy_creation_preflights"] == "/managed-copies/copy-creation-preflights"
    assert body["routes"]["copy_creation_plan"] == "/managed-copies/copy-creation-plan"
    assert body["routes"]["copy_creation_plans"] == "/managed-copies/copy-creation-plans"
    assert body["routes"]["copy_creation_approval_request"] == ("/managed-copies/copy-creation-approval-request")
    assert body["routes"]["copy_creation_approval_requests"] == ("/managed-copies/copy-creation-approval-requests")
    assert body["routes"]["copy_creation_provision"] == "/managed-copies/copy-creation-provision"
    assert body["routes"]["copy_creation_provisions"] == "/managed-copies/copy-creation-provisions"

    requirement_ids = {item["id"] for item in body["requirements"]}
    assert {
        "stage17_closed_by_receipt",
        "tenant_identity_contract",
        "tenant_policy_contract",
        "isolation_profile_contract",
        "capability_lineage_contract",
        "safe_delta_policy_contract",
        "rogue_recovery_contract",
        "decommission_contract",
    } <= requirement_ids
    assert body["required_count"] == len(body["requirements"])
    assert body["ready_count"] == 0
    assert all(item["required"] is True for item in body["requirements"])
    assert all(item["ready"] is False for item in body["requirements"])

    step_by_id = {item["id"]: item for item in body["process_steps"]}
    assert step_by_id["request"]["status"] == "blocked"
    assert step_by_id["preflight"]["status"] == "blocked"
    assert step_by_id["plan"]["status"] == "blocked"
    assert step_by_id["approve"]["status"] == "contract_only"
    assert step_by_id["provision"]["status"] == "disabled"
    assert step_by_id["provision"]["writes_tenant_state"] is True
    assert step_by_id["provision"]["writes_registry"] is True
    assert step_by_id["provision"]["writes_receipt"] is True
    assert step_by_id["verify"]["status"] == "disabled"
    assert step_by_id["handoff"]["status"] == "disabled"
    assert all(item["requires_operator_approval"] is True for item in body["process_steps"])

    assert body["state_machine"] == {
        "current_state": "not_implemented",
        "states": [
            "request_recording_enabled",
            "requested",
            "preflight_blocked",
            "preflighted",
            "planned",
            "approval_pending",
            "approval_decided",
            "approval_rejected",
            "approval_emergency",
            "approved",
            "provisioning",
            "provision_recovery_required",
            "provisioned_unverified",
            "verifying",
            "structurally_verified",
            "active",
            "quarantined",
            "decommissioned",
        ],
        "active_transitions_enabled": False,
        "enabled_transitions": [],
    }
    assert body["required_receipts"] == [
        "copy_request_receipt",
        "preflight_receipt",
        "copy_creation_plan_receipt",
        "operator_approval_receipt",
        "provisioning_receipt",
        "isolation_verification_receipt",
        "support_handoff_receipt",
    ]
    assert body["isolation_boundaries"] == [
        "tenant_data",
        "tenant_memory",
        "tenant_receipts",
        "tenant_connectors",
        "tenant_capability_packs",
        "tenant_policy",
        "support_operator_authority",
    ]
    assert body["blocked_failure_modes"] == [
        "core_surrender",
        "privacy_weak_pooling",
        "uncontrolled_forks",
        "support_chaos",
        "invisible_vendor_power",
    ]

    assert body["read_only"] is True
    assert body["projection_only"] is True
    assert body["writes_registry"] is False
    assert body["writes_memory"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tenant_state"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["launches_browser"] is False
    assert body["captures_screen"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False

    governance = body["governance"]
    assert governance["copy_creation_enabled"] is False
    assert governance["writes_tenant_state"] is False
    assert governance["writes_receipts"] is False
    assert governance["core_surrender_allowed"] is False
    assert governance["privacy_weak_pooling_allowed"] is False
    assert governance["uncontrolled_forks_allowed"] is False
    assert governance["invisible_vendor_power_allowed"] is False
    assert not data_root.exists()
