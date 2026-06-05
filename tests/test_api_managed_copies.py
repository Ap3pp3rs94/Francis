from __future__ import annotations

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
