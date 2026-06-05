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
    assert body["routes"] == {"status": "/managed-copies/status"}

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
