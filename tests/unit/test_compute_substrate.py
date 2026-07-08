from __future__ import annotations

import pytest

from francis.compute_substrate import (
    COMPUTE_RECEIPT_KIND,
    LIVE_LEARNING_EVENT_KIND,
    CapabilityReceiptAdapter,
    ResourceBudget,
    SafeLocalBackend,
    SubstrateGovernor,
    TaskEnvelope,
    WorkerDescriptor,
    WorkerRegistry,
    create_task_envelope,
    execute_registered_function,
)


def test_task_envelope_creation_carries_budget_and_payload() -> None:
    budget = ResourceBudget(
        max_runtime_ms=500,
        max_memory_mb=64,
        cpu_weight=10,
        priority="low",
        max_compute_units=50,
    )

    envelope = create_task_envelope(
        "echo",
        task_id="task-echo-contract",
        payload={"message": "hello"},
        budget=budget,
        actor="codex.local",
        trace_id="trace-compute-substrate",
    )

    assert envelope.task_id == "task-echo-contract"
    assert envelope.function_name == "echo"
    assert envelope.payload == {"message": "hello"}
    assert envelope.actor == "codex.local"
    assert envelope.trace_id == "trace-compute-substrate"
    assert envelope.budget.max_runtime_ms == 500
    assert envelope.budget.filesystem_scope == ("none",)
    assert envelope.to_dict()["budget"]["allow_network"] is False


def test_worker_registry_registers_safe_local_backend() -> None:
    registry = WorkerRegistry()
    backend = SafeLocalBackend(worker_id="safe-local-test")

    registry.register(backend)

    descriptors = registry.descriptors()
    assert len(descriptors) == 1
    assert descriptors[0].worker_id == "safe-local-test"
    assert descriptors[0].backend_name == "safe_local"
    assert descriptors[0].starts_processes is False
    assert descriptors[0].allow_network is False
    assert descriptors[0].filesystem_access == "none"
    assert set(descriptors[0].capabilities) == {
        "compute_test",
        "echo",
        "health_check",
        "summarize_status",
    }
    assert registry.backend_for("echo") is backend


def test_worker_registry_rejects_duplicate_worker_ids() -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend(worker_id="safe-local-duplicate"))

    with pytest.raises(ValueError, match="worker_already_registered"):
        registry.register(SafeLocalBackend(worker_id="safe-local-duplicate"))


class _DisabledBackend:
    @property
    def descriptor(self) -> WorkerDescriptor:
        return WorkerDescriptor(
            worker_id="disabled-worker",
            backend_name="disabled_test",
            capabilities=("echo",),
            enabled=False,
        )

    def execute(self, envelope: TaskEnvelope) -> dict[str, object]:
        raise AssertionError("disabled worker should not execute")


def test_governor_rejects_disabled_workers_before_backend_execution() -> None:
    registry = WorkerRegistry()
    registry.register(_DisabledBackend())
    result = SubstrateGovernor().execute(create_task_envelope("echo"), registry)

    assert result.ok is False
    assert result.status == "denied"
    assert result.error == "worker_enabled"
    assert result.output["decision"]["checks"]["worker_enabled"] is False
    assert result.receipt.governance["worker_enabled"] is False


def test_budget_validation_rejects_over_budget_values() -> None:
    governor = SubstrateGovernor()
    budget = ResourceBudget(
        max_runtime_ms=6000,
        max_memory_mb=64,
        cpu_weight=10,
        priority="normal",
    )

    decision = governor.validate_budget(budget)

    assert decision.allowed is False
    assert decision.reason == "runtime_within_limit"
    assert decision.checks["runtime_within_limit"] is False
    assert decision.governance["resource_enforcement"] == "validated_boundaries_not_os_cgroups"


def test_governor_rejects_unauthorized_scope_gpu_network_and_compute_overrun() -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    governor = SubstrateGovernor()

    network_envelope = create_task_envelope(
        "echo",
        payload={"message": "blocked"},
        budget=ResourceBudget(allow_network=True),
    )
    network_result = governor.execute(network_envelope, registry)

    assert network_result.ok is False
    assert network_result.status == "denied"
    assert network_result.error == "network_allowed"
    assert network_result.receipt.kind == COMPUTE_RECEIPT_KIND
    assert network_result.receipt.persisted is False
    assert network_result.receipt.governance["unrestricted_network"] is False
    assert network_result.receipt.governance["network_requested"] is True
    assert network_result.receipt.governance["uses_network"] is False

    gpu_result = governor.execute(
        create_task_envelope("echo", budget=ResourceBudget(allow_gpu=True)),
        registry,
    )
    assert gpu_result.ok is False
    assert gpu_result.status == "denied"
    assert gpu_result.error == "gpu_allowed"

    filesystem_result = governor.execute(
        create_task_envelope("echo", budget=ResourceBudget(filesystem_scope=("D:/Francis",))),
        registry,
    )
    assert filesystem_result.ok is False
    assert filesystem_result.status == "denied"
    assert filesystem_result.error == "filesystem_scope_allowed"

    compute_envelope = create_task_envelope(
        "compute_test",
        payload={"iterations": 11},
        budget=ResourceBudget(max_compute_units=10),
    )
    compute_result = governor.execute(compute_envelope, registry)

    assert compute_result.ok is False
    assert compute_result.status == "denied"
    assert compute_result.error == "payload_compute_units_within_budget"
    assert compute_result.output["decision"]["checks"]["payload_compute_units_within_budget"] is False


def test_governor_rejects_unknown_capability_and_approval_required_tasks() -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    governor = SubstrateGovernor()

    unknown = governor.execute(create_task_envelope("shell"), registry)
    assert unknown.ok is False
    assert unknown.status == "denied"
    assert unknown.error == "unregistered_function"
    assert unknown.receipt.persisted is False

    approval_required = governor.execute(
        create_task_envelope("echo", budget=ResourceBudget(approval_required=True)),
        registry,
    )
    assert approval_required.ok is False
    assert approval_required.status == "denied"
    assert approval_required.error == "approval_not_required_first_slice"
    assert approval_required.output["decision"]["checks"]["approval_not_required_first_slice"] is False


def test_safe_local_backend_executes_registered_function_only() -> None:
    result = execute_registered_function(
        create_task_envelope(
            "compute_test",
            payload={"iterations": 5},
            budget=ResourceBudget(max_runtime_ms=1000, max_compute_units=5),
        )
    )

    assert result.ok is True
    assert result.status == "success"
    assert result.backend_name == "safe_local"
    assert result.function_name == "compute_test"
    assert result.output == {
        "ok": True,
        "function": "compute_test",
        "iterations": 5,
        "checksum": 30,
    }
    assert result.elapsed_ms >= 0
    assert result.receipt.status == "success"


def test_execution_result_contains_receipt_and_live_learning_event() -> None:
    envelope = TaskEnvelope(
        task_id="task-live-learning",
        function_name="echo",
        payload={"message": "event"},
    )

    result = execute_registered_function(envelope)

    assert result.ok is True
    assert result.receipt.kind == COMPUTE_RECEIPT_KIND
    assert result.receipt.receipt_id.startswith("compute_capability_")
    assert result.receipt.task_id == "task-live-learning"
    assert result.receipt.function_name == "echo"
    assert result.receipt.persisted is False
    assert result.receipt.receipt_path == ""
    assert result.receipt.governance["receipt_persistence"] == "not_persisted_first_slice"
    assert result.receipt.governance["os_level_cpu_memory_enforcement"] is False
    assert result.receipt.governance["long_term_memory_persistence"] is False

    event = result.live_learning_event
    assert event.kind == LIVE_LEARNING_EVENT_KIND
    assert event.event_id.startswith("compute_learning_")
    assert event.task_id == "task-live-learning"
    assert event.result_status == "success"
    assert event.persistence_requested is False
    assert event.persisted is False
    assert event.persistence_follow_up == "requires_governance_review_before_long_term_memory_write"


def test_receipt_adapter_creates_non_persisted_capability_receipt() -> None:
    envelope = create_task_envelope("echo", task_id="task-receipt")
    descriptor = SafeLocalBackend(worker_id="safe-local-receipt").descriptor

    receipt = CapabilityReceiptAdapter().create(
        envelope=envelope,
        descriptor=descriptor,
        status="success",
        reason="executed_registered_function",
    )

    assert receipt.kind == COMPUTE_RECEIPT_KIND
    assert receipt.receipt_id.startswith("compute_capability_")
    assert receipt.task_id == "task-receipt"
    assert receipt.worker_id == "safe-local-receipt"
    assert receipt.persisted is False
    assert receipt.governance["registered_function_only"] is True
    assert receipt.governance["arbitrary_subprocess"] is False
    assert receipt.governance["shell"] is False
    assert receipt.governance["background_daemon"] is False
