from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from francis.compute_substrate import (
    COMPUTE_RECEIPT_KIND,
    LIVE_LEARNING_EVENT_KIND,
    CapabilityReceipt,
    CapabilityReceiptAdapter,
    LocalJsonComputeReceiptStore,
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
    assert result.receipt.receipt_error == ""
    assert result.receipt.governance["receipt_persistence"] == "in_memory_only"
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
    assert receipt.receipt_path == ""
    assert receipt.receipt_error == ""
    assert receipt.governance["registered_function_only"] is True
    assert receipt.governance["arbitrary_subprocess"] is False
    assert receipt.governance["shell"] is False
    assert receipt.governance["background_daemon"] is False


def test_local_json_compute_receipt_store_writes_and_reads_receipt(tmp_path: Path) -> None:
    receipt_root = tmp_path / "compute-receipts"
    store = LocalJsonComputeReceiptStore(receipt_root)
    receipt = CapabilityReceiptAdapter().create(
        envelope=create_task_envelope(
            "echo",
            task_id="task-durable-receipt",
            payload={"message": "raw payload should not be persisted"},
            trace_id="trace-durable-receipt",
        ),
        descriptor=SafeLocalBackend(worker_id="safe-local-durable").descriptor,
        status="success",
        reason="executed_registered_function",
    )

    assert receipt.persisted is False
    assert receipt.receipt_path == ""

    persisted = store.write_receipt(receipt)

    assert persisted.persisted is True
    assert persisted.receipt_path
    receipt_path = Path(persisted.receipt_path)
    assert receipt_path.exists()
    assert receipt_path.parent == receipt_root
    assert persisted.governance["receipt_persistence"] == "persisted_local_json"
    assert persisted.governance["durable_compute_receipt"] is True
    assert persisted.governance["approval_consumption"] == "not_implemented_first_slice"
    assert persisted.governance["long_term_memory_persistence"] is False

    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["receipt"]["receipt_id"] == persisted.receipt_id
    assert payload["receipt"]["trace_id"] == "trace-durable-receipt"
    assert payload["governance"]["does_not_persist_task_payload"] is True
    assert payload["governance"]["does_not_persist_task_output"] is True
    receipt_text = json.dumps(payload, sort_keys=True)
    assert "raw payload should not be persisted" not in receipt_text
    assert "payload" not in payload["receipt"]

    readback = store.read_receipt(persisted.receipt_id)

    assert readback == persisted

    filesystem_scope_receipt = CapabilityReceiptAdapter().create(
        envelope=create_task_envelope(
            "echo",
            task_id="task-filesystem-scope-summary",
            budget=ResourceBudget(filesystem_scope=("C:/secret/private",)),
        ),
        descriptor=SafeLocalBackend(worker_id="safe-local-filesystem-summary").descriptor,
        status="denied",
        reason="filesystem_scope_allowed",
    )
    filesystem_scope_persisted = store.write_receipt(filesystem_scope_receipt)
    assert filesystem_scope_persisted.budget["filesystem_scope"] == ["non_default_scope_requested"]
    assert "C:/secret/private" not in Path(filesystem_scope_persisted.receipt_path).read_text(encoding="utf-8")


def test_local_json_compute_receipt_store_rejects_unsafe_receipt_ids(tmp_path: Path) -> None:
    store = LocalJsonComputeReceiptStore(tmp_path / "compute-receipts")
    receipt = CapabilityReceiptAdapter().create(
        envelope=create_task_envelope("echo", task_id="task-unsafe-receipt"),
        descriptor=SafeLocalBackend(worker_id="safe-local-unsafe").descriptor,
        status="success",
        reason="executed_registered_function",
    )

    with pytest.raises(ValueError, match="unsafe_receipt_id"):
        store.write_receipt(replace(receipt, receipt_id="../escape"))

    with pytest.raises(ValueError, match="unsafe_receipt_id"):
        store.read_receipt("..\\escape")


@pytest.mark.parametrize(
    "receipt_id",
    [
        "../escape",
        "..\\escape",
        "nested/escape",
        "nested\\escape",
        "/absolute/path",
        "\\absolute\\path",
        "C:/absolute/path",
        "C:\\absolute\\path",
        "receipt.with.dot",
        "receipt:with:colon",
        "receipt\u2215with\u2215unicode-separator",
        "",
    ],
)
def test_local_json_compute_receipt_store_rejects_path_like_receipt_ids(
    tmp_path: Path,
    receipt_id: str,
) -> None:
    store = LocalJsonComputeReceiptStore(tmp_path / "compute-receipts")
    receipt = CapabilityReceiptAdapter().create(
        envelope=create_task_envelope("echo", task_id="task-path-like-receipt"),
        descriptor=SafeLocalBackend(worker_id="safe-local-path-like").descriptor,
        status="success",
        reason="executed_registered_function",
    )

    with pytest.raises(ValueError, match="unsafe_receipt_id"):
        store.write_receipt(replace(receipt, receipt_id=receipt_id))

    with pytest.raises(ValueError, match="unsafe_receipt_id"):
        store.read_receipt(receipt_id)


def test_local_json_compute_receipt_store_accepts_safe_receipt_id(tmp_path: Path) -> None:
    store = LocalJsonComputeReceiptStore(tmp_path / "compute-receipts")
    receipt = CapabilityReceiptAdapter().create(
        envelope=create_task_envelope("echo", task_id="task-safe-receipt-id"),
        descriptor=SafeLocalBackend(worker_id="safe-local-safe-id").descriptor,
        status="success",
        reason="executed_registered_function",
    )
    safe_receipt = replace(receipt, receipt_id="compute_capability-safe_ID_123")

    persisted = store.write_receipt(safe_receipt)

    assert persisted.receipt_id == "compute_capability-safe_ID_123"
    assert Path(persisted.receipt_path).parent == store.receipt_root
    assert store.read_receipt("compute_capability-safe_ID_123") == persisted


class _FailingReceiptStore:
    def write_receipt(self, receipt: CapabilityReceipt) -> CapabilityReceipt:
        raise OSError("receipt store unavailable")

    def read_receipt(self, receipt_id: str) -> CapabilityReceipt | None:
        return None

    def describe(self) -> dict[str, object]:
        return {"kind": "test.failing_compute_receipt_store"}


def test_failed_receipt_persistence_does_not_fake_success() -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    governor = SubstrateGovernor(receipt_store=_FailingReceiptStore())

    result = governor.execute(create_task_envelope("echo", payload={"message": "persist me"}), registry)

    assert result.ok is False
    assert result.status == "receipt_persistence_failed"
    assert result.error.startswith("OSError: receipt store unavailable")
    assert result.output == {"ok": True, "function": "echo", "message": "persist me"}
    assert result.receipt.persisted is False
    assert result.receipt.receipt_path == ""
    assert result.receipt.receipt_error.startswith("OSError: receipt store unavailable")
    assert result.receipt.governance["receipt_persistence"] == "persistence_failed"
    assert result.receipt.governance["receipt_store_configured"] is True
    assert result.live_learning_event.persisted is False
    assert result.live_learning_event.result_status == "receipt_persistence_failed"


def test_governor_without_receipt_store_preserves_in_memory_behavior() -> None:
    result = execute_registered_function(create_task_envelope("echo", payload={"message": "memory only"}))

    assert result.ok is True
    assert result.status == "success"
    assert result.receipt.persisted is False
    assert result.receipt.receipt_path == ""
    assert result.receipt.receipt_error == ""
    assert result.receipt.governance["receipt_persistence"] == "in_memory_only"
    assert result.receipt.governance["receipt_store_configured"] is False


def test_governor_with_receipt_store_persists_compute_receipt_and_not_learning(
    tmp_path: Path,
) -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    store = LocalJsonComputeReceiptStore(tmp_path / "compute-receipts")
    governor = SubstrateGovernor(receipt_store=store)

    result = governor.execute(
        create_task_envelope(
            "compute_test",
            payload={"iterations": 4, "secret": "secret-token-should-not-persist"},
            budget=ResourceBudget(max_compute_units=4),
        ),
        registry,
    )

    assert result.ok is True
    assert result.status == "success"
    assert result.receipt.persisted is True
    assert result.receipt.receipt_path
    assert result.receipt.receipt_error == ""
    assert result.receipt.governance["receipt_persistence"] == "persisted_local_json"
    assert result.receipt.governance["arbitrary_subprocess"] is False
    assert result.receipt.governance["shell"] is False
    assert result.receipt.governance["background_daemon"] is False
    assert result.receipt.governance["unrestricted_filesystem_write"] is False
    assert result.receipt.governance["unrestricted_network"] is False
    assert result.receipt.governance["uses_network"] is False
    assert result.receipt.governance["uses_gpu"] is False
    assert result.receipt.governance["writes_memory"] is False
    assert result.receipt.governance["long_term_memory_persistence"] is False
    assert result.receipt.governance["approval_consumption"] == "not_implemented_first_slice"
    assert result.receipt.governance["os_level_cpu_memory_enforcement"] is False
    assert result.live_learning_event.persistence_requested is False
    assert result.live_learning_event.persisted is False

    receipt_text = Path(result.receipt.receipt_path).read_text(encoding="utf-8")
    assert "secret-token-should-not-persist" not in receipt_text
    assert "iterations" not in receipt_text
    assert "checksum" not in receipt_text
    assert store.read_receipt(result.receipt.receipt_id) == result.receipt
