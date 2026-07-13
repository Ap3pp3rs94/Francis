from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from francis.compute_substrate_types import (
    _NO_FILESYSTEM_SCOPE,
    _now_ms,
    _safe_text,
    _scope_tuple,
    ResourceBudget,
)
from francis.compute_substrate_workers import (
    ManagedWorkerCapabilities,
    ManagedWorkerDescriptor,
    ManagedWorkerExecutionPlan,
    ManagedWorkerKind,
    ManagedWorkerPolicy,
    ManagedWorkerResourceEnvelope,
    ManagedWorkerSandboxProfile,
    create_managed_worker_execution_plan,
)

VIRTUAL_WORKFIELD_PLAN_KIND = "francis.compute_substrate.virtual_workfield_plan"
VIRTUAL_WORKFIELD_CAPABILITY = "virtual_workfield_plan"
MAX_VIRTUAL_WORKFIELD_NODES = 32
MAX_VIRTUAL_WORKFIELD_UNITS = 100_000
MAX_VIRTUAL_WORKFIELD_RUNTIME_MS = 1_000


@dataclass(frozen=True, slots=True)
class VirtualWorkfieldBudget:
    work_units: int = 2_400
    virtual_node_count: int = 8
    max_runtime_ms: int = 250
    max_memory_mb: int = 128
    cpu_weight: int = 25
    allow_network: bool = False
    allow_gpu: bool = False
    filesystem_scope: tuple[str, ...] = _NO_FILESYSTEM_SCOPE
    claim_free_compute: bool = False
    allow_host_execution: bool = False
    approval_required: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "work_units",
            _bounded_int(
                self.work_units,
                minimum=1,
                maximum=MAX_VIRTUAL_WORKFIELD_UNITS,
                field_name="work_units",
            ),
        )
        object.__setattr__(
            self,
            "virtual_node_count",
            _bounded_int(
                self.virtual_node_count,
                minimum=1,
                maximum=MAX_VIRTUAL_WORKFIELD_NODES,
                field_name="virtual_node_count",
            ),
        )
        object.__setattr__(
            self,
            "max_runtime_ms",
            _bounded_int(
                self.max_runtime_ms,
                minimum=1,
                maximum=MAX_VIRTUAL_WORKFIELD_RUNTIME_MS,
                field_name="max_runtime_ms",
            ),
        )
        object.__setattr__(
            self,
            "max_memory_mb",
            _bounded_int(self.max_memory_mb, minimum=1, maximum=1024, field_name="max_memory_mb"),
        )
        object.__setattr__(
            self, "cpu_weight", _bounded_int(self.cpu_weight, minimum=1, maximum=100, field_name="cpu_weight")
        )
        object.__setattr__(self, "filesystem_scope", _scope_tuple(self.filesystem_scope))
        if self.claim_free_compute:
            raise ValueError("virtual_workfield_does_not_create_free_compute")
        if self.allow_host_execution:
            raise ValueError("virtual_workfield_host_execution_not_allowed")
        if self.allow_network:
            raise ValueError("virtual_workfield_network_not_allowed")
        if self.allow_gpu:
            raise ValueError("virtual_workfield_gpu_not_allowed")
        if self.filesystem_scope != _NO_FILESYSTEM_SCOPE:
            raise ValueError("virtual_workfield_filesystem_scope_not_allowed")

    def to_resource_budget(self) -> ResourceBudget:
        return ResourceBudget(
            max_runtime_ms=self.max_runtime_ms,
            max_memory_mb=self.max_memory_mb,
            cpu_weight=self.cpu_weight,
            allow_network=False,
            filesystem_scope=_NO_FILESYSTEM_SCOPE,
            allow_gpu=False,
            approval_required=self.approval_required,
            max_compute_units=self.work_units,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "work_units": self.work_units,
            "virtual_node_count": self.virtual_node_count,
            "max_runtime_ms": self.max_runtime_ms,
            "max_memory_mb": self.max_memory_mb,
            "cpu_weight": self.cpu_weight,
            "allow_network": False,
            "allow_gpu": False,
            "filesystem_scope": ["none"],
            "claim_free_compute": False,
            "allow_host_execution": False,
            "approval_required": self.approval_required,
            "max_work_units": MAX_VIRTUAL_WORKFIELD_UNITS,
            "max_virtual_nodes": MAX_VIRTUAL_WORKFIELD_NODES,
            "max_runtime_ms_allowed": MAX_VIRTUAL_WORKFIELD_RUNTIME_MS,
        }


@dataclass(frozen=True, slots=True)
class VirtualWorkfieldNode:
    node_id: str
    role: str
    weight: int
    assigned_work_units: int
    metadata_summary: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", _contract_id(self.node_id))
        object.__setattr__(self, "role", _bounded_text(self.role, limit=80) or "virtual_lane")
        object.__setattr__(
            self,
            "weight",
            _bounded_int(self.weight, minimum=1, maximum=MAX_VIRTUAL_WORKFIELD_NODES, field_name="weight"),
        )
        object.__setattr__(
            self,
            "assigned_work_units",
            _bounded_int(
                self.assigned_work_units,
                minimum=0,
                maximum=MAX_VIRTUAL_WORKFIELD_UNITS,
                field_name="assigned_work_units",
            ),
        )
        object.__setattr__(self, "metadata_summary", _metadata_summary(self.metadata_summary))

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "role": self.role,
            "weight": self.weight,
            "assigned_work_units": self.assigned_work_units,
            "metadata_summary": dict(self.metadata_summary),
            "virtual_only": True,
            "real_compute_created": False,
            "execution_authority": False,
            "network_authority": False,
            "gpu_authority": False,
            "filesystem_authority": False,
        }


@dataclass(frozen=True, slots=True)
class VirtualWorkfieldPlan:
    plan_id: str
    workload: str
    budget: VirtualWorkfieldBudget = field(default_factory=VirtualWorkfieldBudget)
    nodes: tuple[VirtualWorkfieldNode, ...] = ()
    managed_worker_plan: ManagedWorkerExecutionPlan | None = None
    created_at_ms: int = field(default_factory=_now_ms)

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", _contract_id(self.plan_id) or f"virtual_workfield_{uuid.uuid4().hex[:12]}")
        object.__setattr__(self, "workload", _summary_text(self.workload, limit=120) or "virtual_workfield")
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(self, "created_at_ms", max(0, int(self.created_at_ms)))

    @property
    def status(self) -> str:
        if self.managed_worker_plan is not None and not self.managed_worker_plan.ok:
            return "denied"
        return "planned_contract_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": VIRTUAL_WORKFIELD_PLAN_KIND,
            "status": self.status,
            "plan_id": self.plan_id,
            "workload": self.workload,
            "phase_plane": "P6_SIMULATION",
            "substrate_alignment": "compute_substrate_adapter_contract",
            "thesis": (
                "Improve useful work per watt through local-first scheduling, sandboxing, reusable capability paths, "
                "receipts, and VR-readable state. This does not create free compute."
            ),
            "budget": self.budget.to_dict(),
            "virtual_nodes": [node.to_dict() for node in self.nodes],
            "virtual_node_count": len(self.nodes),
            "managed_worker_plan": self.managed_worker_plan.to_dict() if self.managed_worker_plan is not None else {},
            "future_adapter_obligations": [
                "semantic_lens_targeting_before_desktop_mutation",
                "plan_level_approval_before_batch_action",
                "reversibility_proof_before_mutating_desktop_reorganization",
                "compute_substrate_gateway_before_execution",
                "receipt_and_status_readback_for_every_execution_attempt",
            ],
            "contract_only": True,
            "simulation_only": True,
            "no_free_compute_claim": True,
            "real_compute_created": False,
            "real_adapter_implementation": False,
            "starts_processes": False,
            "uses_network": False,
            "uses_gpu": False,
            "runs_shell": False,
            "starts_daemon": False,
            "stores_payload": False,
            "stores_output": False,
            "stores_secrets": False,
            "writes_memory": False,
            "live_learning_persistence": False,
            "execution_authority": False,
            "desktop_mutation_authority": False,
            "os_level_cpu_memory_enforcement": False,
            "created_at_ms": self.created_at_ms,
        }


def create_virtual_workfield_plan(
    *,
    plan_id: str | None = None,
    workload: str = "francis_vr_compute_concept",
    budget: VirtualWorkfieldBudget | None = None,
) -> VirtualWorkfieldPlan:
    resolved_budget = budget or VirtualWorkfieldBudget()
    nodes = _virtual_nodes(resolved_budget)
    resolved_plan_id = _contract_id(plan_id) if plan_id is not None else f"virtual_workfield_{uuid.uuid4().hex[:12]}"
    if not resolved_plan_id:
        resolved_plan_id = f"virtual_workfield_{uuid.uuid4().hex[:12]}"
    managed_plan = create_managed_worker_execution_plan(
        _virtual_worker_descriptor(resolved_budget),
        _virtual_worker_policy(resolved_budget),
        ManagedWorkerResourceEnvelope(
            task_id=resolved_plan_id,
            requested_capability=VIRTUAL_WORKFIELD_CAPABILITY,
            resource_budget=resolved_budget.to_resource_budget(),
            approval_required=resolved_budget.approval_required,
        ),
        plan_id=f"{resolved_plan_id}_managed_worker",
        sandbox_profile=ManagedWorkerSandboxProfile(
            isolation_kind="simulation_contract_only",
            filesystem_policy="none",
            network_policy="deny",
            gpu_policy="deny",
            process_policy="not_implemented",
            memory_policy="validation_only",
            cpu_policy="validation_only",
        ),
    )
    return VirtualWorkfieldPlan(
        plan_id=resolved_plan_id,
        workload=workload,
        budget=resolved_budget,
        nodes=nodes,
        managed_worker_plan=managed_plan,
    )


def _virtual_nodes(budget: VirtualWorkfieldBudget) -> tuple[VirtualWorkfieldNode, ...]:
    weights = tuple(range(1, budget.virtual_node_count + 1))
    weight_total = sum(weights)
    remaining = budget.work_units
    nodes: list[VirtualWorkfieldNode] = []
    for index, weight in enumerate(weights):
        assigned = remaining if index == len(weights) - 1 else int((budget.work_units * weight) / weight_total)
        remaining -= assigned
        nodes.append(
            VirtualWorkfieldNode(
                node_id=f"vr_node_{index + 1:02d}",
                role="operator_focus_lane" if index == 0 else "virtual_scheduler_lane",
                weight=weight,
                assigned_work_units=assigned,
                metadata_summary={
                    "lane": index + 1,
                    "projection": "vr_readable_compute_state",
                },
            )
        )
    return tuple(nodes)


def _virtual_worker_descriptor(budget: VirtualWorkfieldBudget) -> ManagedWorkerDescriptor:
    return ManagedWorkerDescriptor(
        worker_id="virtual-workfield-simulation",
        name="Virtual workfield simulation contract",
        kind=ManagedWorkerKind.SIMULATION,
        capabilities=ManagedWorkerCapabilities(
            declared_capabilities=(VIRTUAL_WORKFIELD_CAPABILITY,),
            supports_cancellation=True,
            supports_deadline=True,
            supports_receipts=True,
            supports_status=True,
            supports_network=False,
            supports_gpu=False,
            supports_persistent_storage=False,
            supports_remote=False,
        ),
        default_resource_budget=budget.to_resource_budget(),
        max_resource_budget=budget.to_resource_budget(),
        requires_approval_by_default=budget.approval_required,
        metadata_summary={
            "phase_plane": "P6_SIMULATION",
            "adapter_contract": "simulation",
            "free_compute_claim": False,
        },
    )


def _virtual_worker_policy(budget: VirtualWorkfieldBudget) -> ManagedWorkerPolicy:
    return ManagedWorkerPolicy(
        allowed_capabilities=(VIRTUAL_WORKFIELD_CAPABILITY,),
        max_resource_budget=budget.to_resource_budget(),
        allowed_worker_kinds=(ManagedWorkerKind.SIMULATION,),
        max_risk_level="low",
        require_approval=budget.approval_required,
        allow_network=False,
        allow_gpu=False,
        filesystem_scope=_NO_FILESYSTEM_SCOPE,
        require_receipt=True,
        require_status=True,
        require_deadline=False,
        require_cancellation_context=False,
        allow_persistent_storage=False,
        allow_remote=False,
        allow_shell=False,
        metadata_summary={"simulation_only": True},
    )


def _bounded_int(value: Any, *, minimum: int, maximum: int, field_name: str) -> int:
    try:
        parsed = int(value)
    except Exception as exc:
        raise ValueError(f"{field_name}_invalid") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{field_name}_out_of_range")
    return parsed


def _contract_id(value: Any) -> str:
    text = _safe_text(value)
    if not text or len(text) > 160 or text in {".", ".."} or ".." in text:
        return ""
    if all(ch.isalnum() or ch in ("-", "_", ".") for ch in text):
        return text
    return ""


def _bounded_text(value: Any, *, limit: int) -> str:
    return _safe_text(value)[:limit]


def _metadata_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    summary: dict[str, Any] = {}
    for raw_key, raw_value in list(value.items())[:20]:
        key = _bounded_text(raw_key, limit=80)
        if not key:
            continue
        if isinstance(raw_value, bool | int | float):
            summary[key] = raw_value
        else:
            summary[key] = _summary_text(raw_value, limit=160)
    return summary


def _summary_text(value: Any, *, limit: int) -> str:
    text = _safe_text(value)
    normalized = text.lower()
    if any(marker in normalized for marker in ("secret", "token=", "credential", "password", "api_key", "apikey")):
        return "redacted_summary"
    if "\\" in text or "/" in text or (len(text) >= 2 and text[1] == ":" and text[0].isalpha()):
        return "non_default_summary_declared"
    return text[:limit]
