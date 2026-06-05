from __future__ import annotations

import json

from fastapi.testclient import TestClient

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
    assert body["stage17_blocker"] == "stage17_capability_library_operator_proposal_evidence_refs"
    assert body["next_smallest_truthful_gap"] == "stage17_capability_library_operator_proposal_evidence_refs"
    assert body["ready_count"] == 0
    assert body["required_count"] == len(body["deliverables"])
    assert body["routes"] == {
        "status": "/managed-copies/status",
        "copy_creation_contract": "/managed-copies/copy-creation-contract",
        "copy_creation_request": "/managed-copies/copy-creation-request",
        "isolation_rules_contract": "/managed-copies/isolation-rules-contract",
        "isolation_verification": "/managed-copies/isolation-verification",
        "safe_delta_model_contract": "/managed-copies/safe-delta-model-contract",
        "safe_delta_review": "/managed-copies/safe-delta-review",
        "rogue_recovery_contract": "/managed-copies/rogue-recovery-contract",
        "rogue_recovery_review": "/managed-copies/rogue-recovery-review",
        "sla_framework_contract": "/managed-copies/sla-framework-contract",
        "sla_commitment_review": "/managed-copies/sla-commitment-review",
        "roles_contract": "/managed-copies/roles-contract",
        "role_authority_review": "/managed-copies/role-authority-review",
        "decommission_contract": "/managed-copies/decommission-contract",
        "runtime_evidence_contract": "/managed-copies/runtime-evidence-contract",
        "runtime_evidence_readbacks": "/managed-copies/runtime-evidence-readbacks",
        "runtime_evidence_readback": "/managed-copies/runtime-evidence-readback",
        "completion_review": "/managed-copies/completion-review",
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
    assert body["stage17_blocker"] == "stage17_capability_library_operator_proposal_evidence_refs"
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
    assert body["next_smallest_truthful_gap"] == "stage17_capability_library_operator_proposal_evidence_refs"

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
    assert check_by_id["stage17_ledger_closure_backstop"]["blocker"] == (
        "stage17_capability_library_operator_proposal_evidence_refs"
    )
    assert check_by_id["copy_creation_contract"]["route"] == "/managed-copies/copy-creation-contract"
    assert check_by_id["decommission_contract"]["route"] == "/managed-copies/decommission-contract"
    assert body["blockers"] == [
        "stage17_capability_library_operator_proposal_evidence_refs",
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
    assert body["next_smallest_truthful_gap"] == "stage17_capability_library_operator_proposal_evidence_refs"

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
    assert body["stage17_blocker"] == "stage17_capability_library_operator_proposal_evidence_refs"
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
        "stage17_capability_library_operator_proposal_evidence_refs",
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
    assert body["next_smallest_truthful_gap"] == "stage17_capability_library_operator_proposal_evidence_refs"

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
        "stage17_capability_library_operator_proposal_evidence_refs",
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
    assert body["next_smallest_truthful_gap"] == "stage17_capability_library_operator_proposal_evidence_refs"

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
    assert body["stage17_blocker"] == "stage17_capability_library_operator_proposal_evidence_refs"
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
    assert body["next_smallest_truthful_gap"] == "stage17_capability_library_operator_proposal_evidence_refs"

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
    assert body["stage17_blocker"] == "stage17_capability_library_operator_proposal_evidence_refs"
    assert body["next_smallest_truthful_gap"] == "stage17_capability_library_operator_proposal_evidence_refs"

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
    assert body["stage17_blocker"] == "stage17_capability_library_operator_proposal_evidence_refs"
    assert body["next_smallest_truthful_gap"] == "stage17_capability_library_operator_proposal_evidence_refs"
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
    assert body["stage17_blocker"] == "stage17_capability_library_operator_proposal_evidence_refs"
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
    assert body["next_smallest_truthful_gap"] == "stage17_capability_library_operator_proposal_evidence_refs"

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
    assert body["stage17_blocker"] == "stage17_capability_library_operator_proposal_evidence_refs"
    assert body["next_smallest_truthful_gap"] == "stage17_capability_library_operator_proposal_evidence_refs"
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
    assert body["stage17_blocker"] == "stage17_capability_library_operator_proposal_evidence_refs"
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
    assert body["next_smallest_truthful_gap"] == "stage17_capability_library_operator_proposal_evidence_refs"

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
    assert body["stage17_blocker"] == "stage17_capability_library_operator_proposal_evidence_refs"
    assert body["next_smallest_truthful_gap"] == "stage17_capability_library_operator_proposal_evidence_refs"
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
    assert body["stage17_blocker"] == "stage17_capability_library_operator_proposal_evidence_refs"
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
    assert body["next_smallest_truthful_gap"] == "stage17_capability_library_operator_proposal_evidence_refs"

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
    assert body["stage17_blocker"] == "stage17_capability_library_operator_proposal_evidence_refs"
    assert body["next_smallest_truthful_gap"] == "stage17_capability_library_operator_proposal_evidence_refs"
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
    assert body["stage17_blocker"] == "stage17_capability_library_operator_proposal_evidence_refs"
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
    assert body["expected_review_receipt_path"] == "logs/managed_copies/safe_delta_reviews.jsonl"
    assert body["required_scope"] == "managed_copies.safe_delta.write"
    assert body["routes"]["safe_delta_review"] == "/managed-copies/safe-delta-review"
    assert body["next_smallest_truthful_gap"] == "stage17_capability_library_operator_proposal_evidence_refs"

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
    assert body["stage17_blocker"] == "stage17_capability_library_operator_proposal_evidence_refs"
    assert body["next_smallest_truthful_gap"] == "stage17_capability_library_operator_proposal_evidence_refs"
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
    assert body["stage17_blocker"] == "stage17_capability_library_operator_proposal_evidence_refs"
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
    assert body["next_smallest_truthful_gap"] == "stage17_capability_library_operator_proposal_evidence_refs"

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
    assert body["stage17_blocker"] == "stage17_capability_library_operator_proposal_evidence_refs"
    assert body["next_smallest_truthful_gap"] == "stage17_capability_library_operator_proposal_evidence_refs"
    assert body["copy_creation_request_route"] == "/managed-copies/copy-creation-request"
    assert body["routes"]["copy_creation_request"] == "/managed-copies/copy-creation-request"

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
    assert step_by_id["preflight"]["status"] == "contract_only"
    assert step_by_id["plan"]["status"] == "contract_only"
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
            "requested",
            "preflight_blocked",
            "planned",
            "approved",
            "provisioning",
            "verifying",
            "active",
            "quarantined",
            "decommissioned",
        ],
        "active_transitions_enabled": False,
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
