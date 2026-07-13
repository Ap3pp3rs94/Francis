from __future__ import annotations

import inspect
import json

import pytest

import francis.compute_substrate_virtual_workfield as virtual_workfield_module
from francis.compute_substrate import (
    MAX_VIRTUAL_WORKFIELD_NODES,
    MAX_VIRTUAL_WORKFIELD_RUNTIME_MS,
    MAX_VIRTUAL_WORKFIELD_UNITS,
    VIRTUAL_WORKFIELD_CAPABILITY,
    VIRTUAL_WORKFIELD_PLAN_KIND,
    ManagedWorkerKind,
    VirtualWorkfieldBudget,
    VirtualWorkfieldPlan,
    create_virtual_workfield_plan,
)


def test_virtual_workfield_plan_is_contract_only_and_simulation_only() -> None:
    plan = create_virtual_workfield_plan(
        plan_id="vr-workfield-plan",
        workload="francis_vr_compute_concept",
        budget=VirtualWorkfieldBudget(work_units=120, virtual_node_count=4),
    )
    payload = plan.to_dict()

    assert isinstance(plan, VirtualWorkfieldPlan)
    assert payload["kind"] == VIRTUAL_WORKFIELD_PLAN_KIND
    assert payload["status"] == "planned_contract_only"
    assert payload["phase_plane"] == "P6_SIMULATION"
    assert payload["substrate_alignment"] == "compute_substrate_adapter_contract"
    assert payload["contract_only"] is True
    assert payload["simulation_only"] is True
    assert payload["no_free_compute_claim"] is True
    assert payload["real_compute_created"] is False
    assert payload["real_adapter_implementation"] is False
    assert payload["execution_authority"] is False
    assert payload["desktop_mutation_authority"] is False
    assert payload["starts_processes"] is False
    assert payload["uses_network"] is False
    assert payload["uses_gpu"] is False
    assert payload["runs_shell"] is False
    assert payload["starts_daemon"] is False
    assert payload["writes_memory"] is False
    assert payload["virtual_node_count"] == 4
    assert sum(node["assigned_work_units"] for node in payload["virtual_nodes"]) == 120


def test_virtual_workfield_budget_fails_closed_on_free_compute_or_execution_claims() -> None:
    cases = [
        ("claim_free_compute", "virtual_workfield_does_not_create_free_compute"),
        ("allow_host_execution", "virtual_workfield_host_execution_not_allowed"),
        ("allow_network", "virtual_workfield_network_not_allowed"),
        ("allow_gpu", "virtual_workfield_gpu_not_allowed"),
    ]

    for field_name, expected in cases:
        with pytest.raises(ValueError, match=expected):
            VirtualWorkfieldBudget(**{field_name: True})

    with pytest.raises(ValueError, match="virtual_workfield_filesystem_scope_not_allowed"):
        VirtualWorkfieldBudget(filesystem_scope=("workspace",))


def test_virtual_workfield_budget_bounds_work_nodes_and_runtime() -> None:
    assert MAX_VIRTUAL_WORKFIELD_UNITS == 100_000
    assert MAX_VIRTUAL_WORKFIELD_NODES == 32
    assert MAX_VIRTUAL_WORKFIELD_RUNTIME_MS == 1000

    with pytest.raises(ValueError, match="work_units_out_of_range"):
        VirtualWorkfieldBudget(work_units=MAX_VIRTUAL_WORKFIELD_UNITS + 1)
    with pytest.raises(ValueError, match="virtual_node_count_out_of_range"):
        VirtualWorkfieldBudget(virtual_node_count=MAX_VIRTUAL_WORKFIELD_NODES + 1)
    with pytest.raises(ValueError, match="max_runtime_ms_out_of_range"):
        VirtualWorkfieldBudget(max_runtime_ms=MAX_VIRTUAL_WORKFIELD_RUNTIME_MS + 1)


def test_virtual_workfield_composes_with_managed_worker_contract_without_execution() -> None:
    plan = create_virtual_workfield_plan(
        plan_id="vr-workfield-managed-plan",
        budget=VirtualWorkfieldBudget(work_units=64, virtual_node_count=2, approval_required=True),
    )
    payload = plan.to_dict()
    managed = payload["managed_worker_plan"]

    assert managed["ok"] is True
    assert managed["status"] == "planned_contract_only"
    assert managed["worker_kind"] == ManagedWorkerKind.SIMULATION
    assert managed["requested_capability"] == VIRTUAL_WORKFIELD_CAPABILITY
    assert managed["approval_required"] is True
    assert managed["contract_only"] is True
    assert managed["dry_run"] is True
    assert managed["starts_processes"] is False
    assert managed["uses_network"] is False
    assert managed["uses_gpu"] is False
    assert managed["runs_shell"] is False
    assert managed["real_worker_implementation"] is False
    assert managed["real_container_execution"] is False
    assert managed["real_vm_execution"] is False
    assert managed["readiness"]["evidence"]["requires_substrate_governor_for_execution"] is True
    assert managed["readiness"]["evidence"]["requires_worker_registry_for_execution"] is True


def test_virtual_workfield_summaries_do_not_store_paths_secrets_or_raw_payloads() -> None:
    plan = create_virtual_workfield_plan(
        plan_id="vr-workfield-redaction",
        workload="secret=SHOULD_NOT_APPEAR D:\\Francis\\private",
        budget=VirtualWorkfieldBudget(work_units=12, virtual_node_count=3),
    )
    text = json.dumps(plan.to_dict(), sort_keys=True)

    assert "SHOULD_NOT_APPEAR" not in text
    assert "D:\\Francis\\private" not in text
    assert plan.to_dict()["workload"] == "redacted_summary"
    assert plan.to_dict()["stores_payload"] is False
    assert plan.to_dict()["stores_output"] is False


def test_virtual_workfield_module_has_no_runtime_execution_imports() -> None:
    source = inspect.getsource(virtual_workfield_module)

    for forbidden in (
        "import subprocess",
        "os.system",
        "shell=True",
        "socket",
        "requests",
        "urllib",
        "create_task",
        "Popen",
        "docker",
        "podman",
        "qemu",
        "firecracker",
    ):
        assert forbidden not in source
