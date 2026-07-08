from __future__ import annotations

from francis.compute_substrate_backends import ExecutionBackend, SafeLocalBackend
from francis.compute_substrate_types import _safe_text, WorkerDescriptor


class WorkerRegistry:
    def __init__(self) -> None:
        self._backends_by_worker: dict[str, ExecutionBackend] = {}
        self._worker_by_capability: dict[str, str] = {}

    def register(self, backend: ExecutionBackend) -> None:
        descriptor = backend.descriptor
        if descriptor.worker_id in self._backends_by_worker:
            raise ValueError("worker_already_registered")
        if not descriptor.capabilities:
            raise ValueError("worker_requires_capabilities")
        for capability in descriptor.capabilities:
            if capability in self._worker_by_capability:
                raise ValueError(f"capability_already_registered:{capability}")
        self._backends_by_worker[descriptor.worker_id] = backend
        for capability in descriptor.capabilities:
            self._worker_by_capability[capability] = descriptor.worker_id

    def backend_for(self, function_name: str) -> ExecutionBackend | None:
        worker_id = self._worker_by_capability.get(_safe_text(function_name))
        if not worker_id:
            return None
        return self._backends_by_worker.get(worker_id)

    def descriptors(self) -> list[WorkerDescriptor]:
        return [backend.descriptor for backend in self._backends_by_worker.values()]


def default_registry() -> WorkerRegistry:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    return registry
