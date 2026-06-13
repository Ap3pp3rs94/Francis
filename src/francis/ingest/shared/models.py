from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SOURCE_TYPES = {"file", "folder", "repo", "app", "unknown"}
SOURCE_STATUSES = {"incoming", "inspected", "indexed", "needs_permission", "failed", "archived"}
CAPABILITY_STATUSES = {
    "discovered",
    "drafted",
    "buildable",
    "runnable",
    "validated",
    "registered",
    "mature",
    "failed",
    "blocked",
}
RISK_LEVELS = {"low", "medium", "high", "blocked"}
LAB_PLAN_STATUSES = {"planned", "blocked", "needs_permission"}
LAB_WORKSPACE_STATUSES = {"prepared", "failed", "archived"}
LAB_PREFLIGHT_STATUSES = {"blocked", "needs_approval", "ready"}
LAB_APPROVAL_REQUEST_STATUSES = {"needs_approval", "failed"}
LAB_RUNNER_CONTRACT_STATUSES = {"blocked", "ready", "failed"}
LAB_RUNNER_READINESS_STATUSES = {"blocked", "ready", "failed"}
LAB_RUNNER_BINDING_PREFLIGHT_STATUSES = {"blocked", "ready", "failed"}
LAB_RUNNER_ENFORCEMENT_PREFLIGHT_STATUSES = {"blocked", "ready", "failed"}
LAB_APPROVAL_CONSUMPTION_HANDOFF_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_EXECUTION_RECEIPT_SINK_RESERVATION_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_RUNNER_COMMAND_ALLOWLIST_BINDING_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_RUNNER_COMMAND_ALLOWLIST_DECLARATION_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_RUNNER_COMMAND_ALLOWLIST_ENFORCEMENT_PREFLIGHT_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_RUNNER_SANDBOX_READINESS_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_SANDBOX_PROVIDER_CONTRACT_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_SANDBOX_PROVIDER_BINDING_PREFLIGHT_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_SANDBOX_PROVIDER_SELECTION_PREFLIGHT_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_SANDBOX_PROVIDER_VERIFIER_PREFLIGHT_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_PREFLIGHT_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_HARNESS_PREFLIGHT_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_READINESS_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_BINDING_PREFLIGHT_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_ENFORCEMENT_PREFLIGHT_STATUSES = {
    "blocked",
    "ready",
    "refused",
    "failed",
}
LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_EXECUTION_BOUNDARY_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_REFUSAL_STATUSES = {"blocked", "refused", "failed"}
LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_APPROVAL_REQUEST_STATUSES = {"needs_approval", "failed"}
LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_APPROVAL_CONSUMPTION_STATUSES = {"consumed", "failed"}
LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_INVOCATION_BOUNDARY_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_PRE_EXECUTION_BOUNDARY_STATUSES = {
    "blocked",
    "ready",
    "refused",
    "failed",
}
LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_CONTROL_BINDING_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_SANDBOXED_REBUILD_RUN_TEST_BOUNDARY_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_SANDBOXED_REBUILD_RUN_TEST_APPROVAL_REQUEST_STATUSES = {"needs_approval", "failed"}
LAB_SANDBOXED_REBUILD_RUN_TEST_APPROVAL_CONSUMPTION_STATUSES = {"consumed", "failed"}
LAB_SANDBOXED_REBUILD_RUN_TEST_RUNNER_BINDING_PREFLIGHT_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_SANDBOXED_REBUILD_RUN_TEST_SANDBOX_POLICY_PREFLIGHT_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_EXECUTION_RECEIPT_WRITE_READINESS_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_EXECUTION_RECEIPT_PREWRITE_BINDING_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_EXECUTION_RECEIPT_WRITER_PREFLIGHT_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_RUN_BOUNDARY_PREFLIGHT_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_SYNTHETIC_EXECUTION_RECEIPT_STATUSES = {"prewritten", "blocked", "refused", "failed"}
LAB_APPROVAL_CONSUMPTION_RECORD_STATUSES = {"consumed", "blocked", "refused", "failed"}
LAB_NOOP_RUNNER_ENVELOPE_STATUSES = {"completed", "blocked", "refused", "failed"}
LAB_NOOP_RUNNER_TRANSCRIPT_STATUSES = {"completed", "blocked", "refused", "failed"}
LAB_NOOP_RUNNER_IDENTITY_BINDING_STATUSES = {"completed", "blocked", "refused", "failed"}
LAB_SOURCE_MOUNT_READINESS_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_SOURCE_MOUNT_CONTRACT_STATUSES = {"blocked", "ready", "refused", "failed"}
LAB_APPROVAL_CONSUMPTION_PREFLIGHT_STATUSES = {"blocked", "refused", "ready", "failed"}


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _safe_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items() if str(key).strip()}


def _safe_list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    return list(value)


@dataclass(frozen=True)
class SourcePermissionProfile:
    read: bool = True
    execute: bool = False
    network: bool = False
    write: bool = False
    destructive: bool = False

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "SourcePermissionProfile":
        data = _safe_dict(value)
        return cls(
            read=bool(data.get("read", True)),
            execute=bool(data.get("execute", False)),
            network=bool(data.get("network", False)),
            write=bool(data.get("write", False)),
            destructive=bool(data.get("destructive", False)),
        )


@dataclass(frozen=True)
class SourceRecord:
    id: str
    type: str
    original_path: str
    canonical_path: str
    created_at: str
    updated_at: str
    fingerprint: str
    status: str
    permissions: SourcePermissionProfile = field(default_factory=SourcePermissionProfile)
    metadata: dict[str, Any] = field(default_factory=dict)
    derived_artifacts: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["permissions"] = self.permissions.to_dict()
        return data

    @classmethod
    def from_dict(cls, value: Any) -> "SourceRecord | None":
        data = _safe_dict(value)
        source_id = _safe_str(data.get("id")).strip()
        if not source_id:
            return None
        source_type = _safe_str(data.get("type")).strip() or "unknown"
        if source_type not in SOURCE_TYPES:
            source_type = "unknown"
        status = _safe_str(data.get("status")).strip() or "incoming"
        if status not in SOURCE_STATUSES:
            status = "incoming"
        return cls(
            id=source_id,
            type=source_type,
            original_path=_safe_str(data.get("original_path")).strip(),
            canonical_path=_safe_str(data.get("canonical_path")).strip(),
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            fingerprint=_safe_str(data.get("fingerprint")).strip(),
            status=status,
            permissions=SourcePermissionProfile.from_dict(data.get("permissions")),
            metadata=_safe_dict(data.get("metadata")),
            derived_artifacts=[_safe_str(item).strip() for item in _safe_list(data.get("derived_artifacts"))],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class RepoRiskSignal:
    id: str
    severity: str
    path: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RepoMap:
    source_id: str
    repo_root: str
    is_git_repo: bool
    git: dict[str, Any] = field(default_factory=dict)
    detected_languages: list[str] = field(default_factory=list)
    package_managers: list[str] = field(default_factory=list)
    manifest_files: list[str] = field(default_factory=list)
    script_commands: dict[str, dict[str, str]] = field(default_factory=dict)
    test_files: list[str] = field(default_factory=list)
    docs_readmes: list[str] = field(default_factory=list)
    entrypoints: list[dict[str, str]] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    source_directories: list[str] = field(default_factory=list)
    dependency_manifests: list[str] = field(default_factory=list)
    license_file: str = ""
    risk_signals: list[RepoRiskSignal] = field(default_factory=list)
    suggested_validation_commands: list[dict[str, Any]] = field(default_factory=list)
    protected_sensitive_files: list[dict[str, str]] = field(default_factory=list)
    files_inspected_count: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["risk_signals"] = [item.to_dict() for item in self.risk_signals]
        return data

    @classmethod
    def from_dict(cls, value: Any) -> "RepoMap | None":
        data = _safe_dict(value)
        source_id = _safe_str(data.get("source_id")).strip()
        repo_root = _safe_str(data.get("repo_root")).strip()
        if not source_id or not repo_root:
            return None
        signals = []
        for item in _safe_list(data.get("risk_signals")):
            signal = _safe_dict(item)
            signal_id = _safe_str(signal.get("id")).strip()
            if not signal_id:
                continue
            signals.append(
                RepoRiskSignal(
                    id=signal_id,
                    severity=_safe_str(signal.get("severity")).strip() or "medium",
                    path=_safe_str(signal.get("path")).strip(),
                    detail=_safe_str(signal.get("detail")).strip(),
                )
            )
        return cls(
            source_id=source_id,
            repo_root=repo_root,
            is_git_repo=bool(data.get("is_git_repo", False)),
            git=_safe_dict(data.get("git")),
            detected_languages=[_safe_str(item).strip() for item in _safe_list(data.get("detected_languages"))],
            package_managers=[_safe_str(item).strip() for item in _safe_list(data.get("package_managers"))],
            manifest_files=[_safe_str(item).strip() for item in _safe_list(data.get("manifest_files"))],
            script_commands={
                _safe_str(key).strip(): {
                    _safe_str(k).strip(): _safe_str(v).strip() for k, v in _safe_dict(value).items()
                }
                for key, value in _safe_dict(data.get("script_commands")).items()
            },
            test_files=[_safe_str(item).strip() for item in _safe_list(data.get("test_files"))],
            docs_readmes=[_safe_str(item).strip() for item in _safe_list(data.get("docs_readmes"))],
            entrypoints=[_safe_dict(item) for item in _safe_list(data.get("entrypoints"))],
            config_files=[_safe_str(item).strip() for item in _safe_list(data.get("config_files"))],
            source_directories=[_safe_str(item).strip() for item in _safe_list(data.get("source_directories"))],
            dependency_manifests=[_safe_str(item).strip() for item in _safe_list(data.get("dependency_manifests"))],
            license_file=_safe_str(data.get("license_file")).strip(),
            risk_signals=signals,
            suggested_validation_commands=[
                _safe_dict(item) for item in _safe_list(data.get("suggested_validation_commands"))
            ],
            protected_sensitive_files=[_safe_dict(item) for item in _safe_list(data.get("protected_sensitive_files"))],
            files_inspected_count=int(data.get("files_inspected_count") or 0),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings"))],
        )


@dataclass(frozen=True)
class CapabilityCandidate:
    id: str
    name: str
    source_id: str
    source_type: str
    status: str
    description: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    inferred_inputs: list[str] = field(default_factory=list)
    inferred_outputs: list[str] = field(default_factory=list)
    permissions_required: SourcePermissionProfile = field(default_factory=SourcePermissionProfile)
    risk_level: str = "low"
    suggested_validation: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)
    promotion_requirements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["permissions_required"] = self.permissions_required.to_dict()
        return data

    @classmethod
    def from_dict(cls, value: Any) -> "CapabilityCandidate | None":
        data = _safe_dict(value)
        candidate_id = _safe_str(data.get("id")).strip()
        name = _safe_str(data.get("name")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        if not candidate_id or not name or not source_id:
            return None
        status = _safe_str(data.get("status")).strip() or "discovered"
        if status not in CAPABILITY_STATUSES:
            status = "discovered"
        risk_level = _safe_str(data.get("risk_level")).strip() or "low"
        if risk_level not in RISK_LEVELS:
            risk_level = "medium"
        return cls(
            id=candidate_id,
            name=name,
            source_id=source_id,
            source_type=_safe_str(data.get("source_type")).strip() or "unknown",
            status=status,
            description=_safe_str(data.get("description")).strip(),
            evidence=[_safe_dict(item) for item in _safe_list(data.get("evidence"))],
            inferred_inputs=[_safe_str(item).strip() for item in _safe_list(data.get("inferred_inputs"))],
            inferred_outputs=[_safe_str(item).strip() for item in _safe_list(data.get("inferred_outputs"))],
            permissions_required=SourcePermissionProfile.from_dict(data.get("permissions_required")),
            risk_level=risk_level,
            suggested_validation=[_safe_str(item).strip() for item in _safe_list(data.get("suggested_validation"))],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
            promotion_requirements=[_safe_str(item).strip() for item in _safe_list(data.get("promotion_requirements"))],
        )


@dataclass(frozen=True)
class Receipt:
    id: str
    timestamp: str
    operation: str
    source_id: str
    actor: str = "francis/system"
    input_paths: list[str] = field(default_factory=list)
    input_hashes: list[str] = field(default_factory=list)
    files_inspected_count: int = 0
    result_status: str = "ok"
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    generated_artifact_paths: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FrancisLabBoundary:
    status: str = "not_available"
    supports_unknown_repo_execution: bool = False
    supports_network_isolation: bool = False
    supports_filesystem_write_isolation: bool = False
    required_before_build_run_test: list[str] = field(
        default_factory=lambda: [
            "explicit_operator_permission",
            "sandboxed_workspace",
            "network_blocking_policy",
            "filesystem_write_boundary",
            "resource_limits",
            "execution_receipts",
            "promotion_gate",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LabPermissionRequirement:
    read: bool = True
    execute: bool = False
    network: bool = False
    write: bool = False
    destructive: bool = False
    explicit_operator_permission: bool = False
    sandbox_required: bool = False
    network_blocked_by_default: bool = True
    approval_scope: str = "francis.lab.read"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_candidate_permissions(cls, permissions: SourcePermissionProfile) -> "LabPermissionRequirement":
        crosses_execution_boundary = bool(
            permissions.execute or permissions.network or permissions.write or permissions.destructive
        )
        return cls(
            read=permissions.read,
            execute=permissions.execute,
            network=permissions.network,
            write=permissions.write,
            destructive=permissions.destructive,
            explicit_operator_permission=crosses_execution_boundary,
            sandbox_required=crosses_execution_boundary,
            network_blocked_by_default=True,
            approval_scope="francis.lab.execute" if crosses_execution_boundary else "francis.lab.read",
        )

    @classmethod
    def from_dict(cls, value: Any) -> "LabPermissionRequirement":
        data = _safe_dict(value)
        return cls(
            read=bool(data.get("read", True)),
            execute=bool(data.get("execute", False)),
            network=bool(data.get("network", False)),
            write=bool(data.get("write", False)),
            destructive=bool(data.get("destructive", False)),
            explicit_operator_permission=bool(data.get("explicit_operator_permission", False)),
            sandbox_required=bool(data.get("sandbox_required", False)),
            network_blocked_by_default=bool(data.get("network_blocked_by_default", True)),
            approval_scope=_safe_str(data.get("approval_scope")).strip() or "francis.lab.read",
        )


@dataclass(frozen=True)
class LabPlan:
    id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    permissions_required: LabPermissionRequirement
    suggested_commands: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    workspace: dict[str, Any] = field(default_factory=dict)
    boundary: dict[str, Any] = field(default_factory=dict)
    execution_authority: bool = False
    executed: bool = False
    receipts: list[str] = field(default_factory=list)
    promotion_requirements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["permissions_required"] = self.permissions_required.to_dict()
        return data

    @classmethod
    def from_dict(cls, value: Any) -> "LabPlan | None":
        data = _safe_dict(value)
        plan_id = _safe_str(data.get("id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if not plan_id or not source_id or not candidate_id:
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_PLAN_STATUSES:
            status = "blocked"
        return cls(
            id=plan_id,
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            permissions_required=LabPermissionRequirement.from_dict(data.get("permissions_required")),
            suggested_commands=[_safe_str(item).strip() for item in _safe_list(data.get("suggested_commands"))],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers"))],
            workspace=_safe_dict(data.get("workspace")),
            boundary=_safe_dict(data.get("boundary")),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
            promotion_requirements=[_safe_str(item).strip() for item in _safe_list(data.get("promotion_requirements"))],
        )


@dataclass(frozen=True)
class LabExecutionRefusal:
    id: str
    plan_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    timestamp: str
    actor: str
    status: str = "blocked"
    reason: str = "francis_lab_execution_not_available"
    blockers: list[str] = field(default_factory=list)
    permission_scope: str = "francis.lab.execute"
    execution_authority: bool = False
    executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    receipt_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LabWorkspaceRecord:
    id: str
    plan_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    path: str
    manifest_path: str
    source_reference: dict[str, Any] = field(default_factory=dict)
    workspace_policy: dict[str, Any] = field(default_factory=dict)
    preflight: dict[str, Any] = field(default_factory=dict)
    source_copied: bool = False
    execution_authority: bool = False
    executed: bool = False
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabWorkspaceRecord | None":
        data = _safe_dict(value)
        workspace_id = _safe_str(data.get("id")).strip()
        plan_id = _safe_str(data.get("plan_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if not workspace_id or not plan_id or not source_id or not candidate_id:
            return None
        status = _safe_str(data.get("status")).strip() or "failed"
        if status not in LAB_WORKSPACE_STATUSES:
            status = "failed"
        return cls(
            id=workspace_id,
            plan_id=plan_id,
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            path=_safe_str(data.get("path")).strip(),
            manifest_path=_safe_str(data.get("manifest_path")).strip(),
            source_reference=_safe_dict(data.get("source_reference")),
            workspace_policy=_safe_dict(data.get("workspace_policy")),
            preflight=_safe_dict(data.get("preflight")),
            source_copied=bool(data.get("source_copied", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabExecutionPreflight:
    id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    approval: dict[str, Any] = field(default_factory=dict)
    exact_action: dict[str, Any] = field(default_factory=dict)
    action_hash: str = ""
    readiness: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    execution_authority: bool = False
    executed: bool = False
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabExecutionPreflight | None":
        data = _safe_dict(value)
        preflight_id = _safe_str(data.get("id")).strip()
        plan_id = _safe_str(data.get("plan_id")).strip()
        workspace_id = _safe_str(data.get("workspace_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if not preflight_id or not plan_id or not workspace_id or not source_id or not candidate_id:
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_PREFLIGHT_STATUSES:
            status = "blocked"
        return cls(
            id=preflight_id,
            plan_id=plan_id,
            workspace_id=workspace_id,
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            approval=_safe_dict(data.get("approval")),
            exact_action=_safe_dict(data.get("exact_action")),
            action_hash=_safe_str(data.get("action_hash")).strip(),
            readiness=_safe_dict(data.get("readiness")),
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers"))],
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabApprovalRequestRecord:
    id: str
    approval_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    approval_path: str = ""
    approval_payload: dict[str, Any] = field(default_factory=dict)
    approval_created: bool = False
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabApprovalRequestRecord | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        approval_id = _safe_str(data.get("approval_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        if not record_id or not approval_id or not preflight_id:
            return None
        status = _safe_str(data.get("status")).strip() or "failed"
        if status not in LAB_APPROVAL_REQUEST_STATUSES:
            status = "failed"
        return cls(
            id=record_id,
            approval_id=approval_id,
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=_safe_str(data.get("workspace_id")).strip(),
            source_id=_safe_str(data.get("source_id")).strip(),
            candidate_id=_safe_str(data.get("candidate_id")).strip(),
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            approval_path=_safe_str(data.get("approval_path")).strip(),
            approval_payload=_safe_dict(data.get("approval_payload")),
            approval_created=bool(data.get("approval_created", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabRunnerContract:
    id: str
    preflight_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    approval_id: str = ""
    action: str = "francis.lab.execute"
    action_hash: str = ""
    runner_kind: str = "francis.lab.runner"
    runner_bound: bool = False
    execution_enabled: bool = False
    required_controls: list[str] = field(default_factory=list)
    current_controls: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    execution_authority: bool = False
    executed: bool = False
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabRunnerContract | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        workspace_id = _safe_str(data.get("workspace_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if not record_id or not preflight_id or not workspace_id or not source_id or not candidate_id:
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_RUNNER_CONTRACT_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            preflight_id=preflight_id,
            workspace_id=workspace_id,
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            approval_id=_safe_str(data.get("approval_id")).strip(),
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            runner_kind=_safe_str(data.get("runner_kind")).strip() or "francis.lab.runner",
            runner_bound=bool(data.get("runner_bound", False)),
            execution_enabled=bool(data.get("execution_enabled", False)),
            required_controls=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_controls")) if _safe_str(item).strip()
            ],
            current_controls=_safe_dict(data.get("current_controls")),
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabRunnerReadiness:
    id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    approval_id: str = ""
    action: str = "francis.lab.execute"
    action_hash: str = ""
    runner_kind: str = "francis.lab.runner"
    sandbox: dict[str, Any] = field(default_factory=dict)
    required_controls: list[str] = field(default_factory=list)
    current_controls: dict[str, Any] = field(default_factory=dict)
    missing_controls: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    execution_authority: bool = False
    executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabRunnerReadiness | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        workspace_id = _safe_str(data.get("workspace_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if not record_id or not preflight_id or not workspace_id or not source_id or not candidate_id:
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_RUNNER_READINESS_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=workspace_id,
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            approval_id=_safe_str(data.get("approval_id")).strip(),
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            runner_kind=_safe_str(data.get("runner_kind")).strip() or "francis.lab.runner",
            sandbox=_safe_dict(data.get("sandbox")),
            required_controls=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_controls")) if _safe_str(item).strip()
            ],
            current_controls=_safe_dict(data.get("current_controls")),
            missing_controls=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_controls")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabRunnerBindingPreflight:
    id: str
    runner_readiness_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    approval_id: str = ""
    action: str = "francis.lab.execute"
    action_hash: str = ""
    runner_binding: dict[str, Any] = field(default_factory=dict)
    execution_receipt_sink: dict[str, Any] = field(default_factory=dict)
    required_controls: list[str] = field(default_factory=list)
    current_controls: dict[str, Any] = field(default_factory=dict)
    missing_controls: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    approval_consumed: bool = False
    runner_bound: bool = False
    receipt_sink_bound: bool = False
    execution_authority: bool = False
    executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabRunnerBindingPreflight | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        readiness_id = _safe_str(data.get("runner_readiness_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        workspace_id = _safe_str(data.get("workspace_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not readiness_id
            or not preflight_id
            or not workspace_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_RUNNER_BINDING_PREFLIGHT_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            runner_readiness_id=readiness_id,
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=workspace_id,
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            approval_id=_safe_str(data.get("approval_id")).strip(),
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            runner_binding=_safe_dict(data.get("runner_binding")),
            execution_receipt_sink=_safe_dict(data.get("execution_receipt_sink")),
            required_controls=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_controls")) if _safe_str(item).strip()
            ],
            current_controls=_safe_dict(data.get("current_controls")),
            missing_controls=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_controls")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            approval_consumed=bool(data.get("approval_consumed", False)),
            runner_bound=bool(data.get("runner_bound", False)),
            receipt_sink_bound=bool(data.get("receipt_sink_bound", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabRunnerEnforcementPreflight:
    id: str
    runner_binding_id: str
    runner_readiness_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    approval_id: str = ""
    action: str = "francis.lab.execute"
    action_hash: str = ""
    enforcement_interface: dict[str, Any] = field(default_factory=dict)
    runner_binding: dict[str, Any] = field(default_factory=dict)
    execution_receipt_sink: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    approval_consumed: bool = False
    runner_bound: bool = False
    receipt_sink_bound: bool = False
    execution_authority: bool = False
    executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabRunnerEnforcementPreflight | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        binding_id = _safe_str(data.get("runner_binding_id")).strip()
        readiness_id = _safe_str(data.get("runner_readiness_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        workspace_id = _safe_str(data.get("workspace_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not binding_id
            or not readiness_id
            or not preflight_id
            or not workspace_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_RUNNER_ENFORCEMENT_PREFLIGHT_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            runner_binding_id=binding_id,
            runner_readiness_id=readiness_id,
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=workspace_id,
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            approval_id=_safe_str(data.get("approval_id")).strip(),
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            enforcement_interface=_safe_dict(data.get("enforcement_interface")),
            runner_binding=_safe_dict(data.get("runner_binding")),
            execution_receipt_sink=_safe_dict(data.get("execution_receipt_sink")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            approval_consumed=bool(data.get("approval_consumed", False)),
            runner_bound=bool(data.get("runner_bound", False)),
            receipt_sink_bound=bool(data.get("receipt_sink_bound", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabApprovalConsumptionHandoff:
    id: str
    approval_id: str
    runner_enforcement_id: str
    runner_binding_id: str
    runner_readiness_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    approval_status: str = ""
    approval_path: str = ""
    approval_snapshot: dict[str, Any] = field(default_factory=dict)
    approval_binding: dict[str, Any] = field(default_factory=dict)
    handoff_contract: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabApprovalConsumptionHandoff | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        approval_id = _safe_str(data.get("approval_id")).strip()
        enforcement_id = _safe_str(data.get("runner_enforcement_id")).strip()
        binding_id = _safe_str(data.get("runner_binding_id")).strip()
        readiness_id = _safe_str(data.get("runner_readiness_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not approval_id
            or not enforcement_id
            or not binding_id
            or not readiness_id
            or not preflight_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_APPROVAL_CONSUMPTION_HANDOFF_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=approval_id,
            runner_enforcement_id=enforcement_id,
            runner_binding_id=binding_id,
            runner_readiness_id=readiness_id,
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=_safe_str(data.get("workspace_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            approval_status=_safe_str(data.get("approval_status")).strip(),
            approval_path=_safe_str(data.get("approval_path")).strip(),
            approval_snapshot=_safe_dict(data.get("approval_snapshot")),
            approval_binding=_safe_dict(data.get("approval_binding")),
            handoff_contract=_safe_dict(data.get("handoff_contract")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabExecutionReceiptSinkReservation:
    id: str
    approval_id: str
    approval_handoff_id: str
    runner_enforcement_id: str
    runner_binding_id: str
    runner_readiness_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    receipt_sink: dict[str, Any] = field(default_factory=dict)
    reservation_contract: dict[str, Any] = field(default_factory=dict)
    reserved_execution_receipt: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    reservation_created: bool = True
    prewrite_bound: bool = False
    final_write_bound: bool = False
    execution_receipt_written: bool = False
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabExecutionReceiptSinkReservation | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        handoff_id = _safe_str(data.get("approval_handoff_id")).strip()
        enforcement_id = _safe_str(data.get("runner_enforcement_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not handoff_id
            or not enforcement_id
            or not preflight_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_EXECUTION_RECEIPT_SINK_RESERVATION_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            approval_handoff_id=handoff_id,
            runner_enforcement_id=enforcement_id,
            runner_binding_id=_safe_str(data.get("runner_binding_id")).strip(),
            runner_readiness_id=_safe_str(data.get("runner_readiness_id")).strip(),
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=_safe_str(data.get("workspace_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            receipt_sink=_safe_dict(data.get("receipt_sink")),
            reservation_contract=_safe_dict(data.get("reservation_contract")),
            reserved_execution_receipt=_safe_dict(data.get("reserved_execution_receipt")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            reservation_created=bool(data.get("reservation_created", True)),
            prewrite_bound=bool(data.get("prewrite_bound", False)),
            final_write_bound=bool(data.get("final_write_bound", False)),
            execution_receipt_written=bool(data.get("execution_receipt_written", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabRunnerCommandAllowlistBinding:
    id: str
    approval_id: str
    receipt_sink_reservation_id: str
    approval_handoff_id: str
    runner_enforcement_id: str
    runner_binding_id: str
    runner_readiness_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    command_plan: dict[str, Any] = field(default_factory=dict)
    allowlist_contract: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    allowlist_declared: bool = False
    allowlist_bound: bool = False
    command_execution_enabled: bool = False
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabRunnerCommandAllowlistBinding | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        reservation_id = _safe_str(data.get("receipt_sink_reservation_id")).strip()
        handoff_id = _safe_str(data.get("approval_handoff_id")).strip()
        enforcement_id = _safe_str(data.get("runner_enforcement_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not reservation_id
            or not handoff_id
            or not enforcement_id
            or not preflight_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_RUNNER_COMMAND_ALLOWLIST_BINDING_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            receipt_sink_reservation_id=reservation_id,
            approval_handoff_id=handoff_id,
            runner_enforcement_id=enforcement_id,
            runner_binding_id=_safe_str(data.get("runner_binding_id")).strip(),
            runner_readiness_id=_safe_str(data.get("runner_readiness_id")).strip(),
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=_safe_str(data.get("workspace_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            command_plan=_safe_dict(data.get("command_plan")),
            allowlist_contract=_safe_dict(data.get("allowlist_contract")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            allowlist_declared=bool(data.get("allowlist_declared", False)),
            allowlist_bound=bool(data.get("allowlist_bound", False)),
            command_execution_enabled=bool(data.get("command_execution_enabled", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabRunnerCommandAllowlistDeclaration:
    id: str
    approval_id: str
    command_allowlist_binding_id: str
    receipt_sink_reservation_id: str
    approval_handoff_id: str
    runner_enforcement_id: str
    runner_binding_id: str
    runner_readiness_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    command_plan: dict[str, Any] = field(default_factory=dict)
    allowlist_declaration: dict[str, Any] = field(default_factory=dict)
    declaration_contract: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    declaration_created: bool = False
    allowlist_declared: bool = False
    allowlist_bound: bool = False
    command_execution_enabled: bool = False
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabRunnerCommandAllowlistDeclaration | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        binding_id = _safe_str(data.get("command_allowlist_binding_id")).strip()
        reservation_id = _safe_str(data.get("receipt_sink_reservation_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not binding_id
            or not reservation_id
            or not preflight_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_RUNNER_COMMAND_ALLOWLIST_DECLARATION_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            command_allowlist_binding_id=binding_id,
            receipt_sink_reservation_id=reservation_id,
            approval_handoff_id=_safe_str(data.get("approval_handoff_id")).strip(),
            runner_enforcement_id=_safe_str(data.get("runner_enforcement_id")).strip(),
            runner_binding_id=_safe_str(data.get("runner_binding_id")).strip(),
            runner_readiness_id=_safe_str(data.get("runner_readiness_id")).strip(),
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=_safe_str(data.get("workspace_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            command_plan=_safe_dict(data.get("command_plan")),
            allowlist_declaration=_safe_dict(data.get("allowlist_declaration")),
            declaration_contract=_safe_dict(data.get("declaration_contract")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            declaration_created=bool(data.get("declaration_created", False)),
            allowlist_declared=bool(data.get("allowlist_declared", False)),
            allowlist_bound=bool(data.get("allowlist_bound", False)),
            command_execution_enabled=bool(data.get("command_execution_enabled", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabRunnerCommandAllowlistEnforcementPreflight:
    id: str
    approval_id: str
    command_allowlist_declaration_id: str
    command_allowlist_binding_id: str
    receipt_sink_reservation_id: str
    approval_handoff_id: str
    runner_enforcement_id: str
    runner_binding_id: str
    runner_readiness_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    allowlist_declaration: dict[str, Any] = field(default_factory=dict)
    enforcement_projection: dict[str, Any] = field(default_factory=dict)
    enforcement_contract: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    allowlist_declared: bool = False
    allowlist_bound: bool = False
    allowlist_enforced: bool = False
    command_execution_enabled: bool = False
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabRunnerCommandAllowlistEnforcementPreflight | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        declaration_id = _safe_str(data.get("command_allowlist_declaration_id")).strip()
        binding_id = _safe_str(data.get("command_allowlist_binding_id")).strip()
        reservation_id = _safe_str(data.get("receipt_sink_reservation_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not declaration_id
            or not binding_id
            or not reservation_id
            or not preflight_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_RUNNER_COMMAND_ALLOWLIST_ENFORCEMENT_PREFLIGHT_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            command_allowlist_declaration_id=declaration_id,
            command_allowlist_binding_id=binding_id,
            receipt_sink_reservation_id=reservation_id,
            approval_handoff_id=_safe_str(data.get("approval_handoff_id")).strip(),
            runner_enforcement_id=_safe_str(data.get("runner_enforcement_id")).strip(),
            runner_binding_id=_safe_str(data.get("runner_binding_id")).strip(),
            runner_readiness_id=_safe_str(data.get("runner_readiness_id")).strip(),
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=_safe_str(data.get("workspace_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            allowlist_declaration=_safe_dict(data.get("allowlist_declaration")),
            enforcement_projection=_safe_dict(data.get("enforcement_projection")),
            enforcement_contract=_safe_dict(data.get("enforcement_contract")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            allowlist_declared=bool(data.get("allowlist_declared", False)),
            allowlist_bound=bool(data.get("allowlist_bound", False)),
            allowlist_enforced=bool(data.get("allowlist_enforced", False)),
            command_execution_enabled=bool(data.get("command_execution_enabled", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabRunnerSandboxReadiness:
    id: str
    approval_id: str
    command_allowlist_enforcement_id: str
    command_allowlist_declaration_id: str
    command_allowlist_binding_id: str
    receipt_sink_reservation_id: str
    approval_handoff_id: str
    runner_enforcement_id: str
    runner_binding_id: str
    runner_readiness_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    sandbox_profile: dict[str, Any] = field(default_factory=dict)
    sandbox_contract: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    sandbox_bound: bool = False
    sandbox_enforced: bool = False
    runner_bound: bool = False
    runner_identity_verified: bool = False
    allowlist_enforced: bool = False
    receipt_prewrite_bound: bool = False
    receipt_final_write_bound: bool = False
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabRunnerSandboxReadiness | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        allowlist_enforcement_id = _safe_str(data.get("command_allowlist_enforcement_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        workspace_id = _safe_str(data.get("workspace_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not allowlist_enforcement_id
            or not preflight_id
            or not workspace_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_RUNNER_SANDBOX_READINESS_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            command_allowlist_enforcement_id=allowlist_enforcement_id,
            command_allowlist_declaration_id=_safe_str(data.get("command_allowlist_declaration_id")).strip(),
            command_allowlist_binding_id=_safe_str(data.get("command_allowlist_binding_id")).strip(),
            receipt_sink_reservation_id=_safe_str(data.get("receipt_sink_reservation_id")).strip(),
            approval_handoff_id=_safe_str(data.get("approval_handoff_id")).strip(),
            runner_enforcement_id=_safe_str(data.get("runner_enforcement_id")).strip(),
            runner_binding_id=_safe_str(data.get("runner_binding_id")).strip(),
            runner_readiness_id=_safe_str(data.get("runner_readiness_id")).strip(),
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=workspace_id,
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            sandbox_profile=_safe_dict(data.get("sandbox_profile")),
            sandbox_contract=_safe_dict(data.get("sandbox_contract")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            sandbox_bound=bool(data.get("sandbox_bound", False)),
            sandbox_enforced=bool(data.get("sandbox_enforced", False)),
            runner_bound=bool(data.get("runner_bound", False)),
            runner_identity_verified=bool(data.get("runner_identity_verified", False)),
            allowlist_enforced=bool(data.get("allowlist_enforced", False)),
            receipt_prewrite_bound=bool(data.get("receipt_prewrite_bound", False)),
            receipt_final_write_bound=bool(data.get("receipt_final_write_bound", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSandboxProviderContract:
    id: str
    approval_id: str
    sandbox_readiness_id: str
    command_allowlist_enforcement_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    contract_kind: str = "francis.lab.sandbox_provider_contract"
    contract_mode: str = "provider_contract_preflight_only_no_execution"
    provider_kind: str = "unbound"
    provider_contract: dict[str, Any] = field(default_factory=dict)
    runner_sandbox_readiness: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    provider_contract_declared: bool = False
    sandbox_provider_bound: bool = False
    sandbox_bound: bool = False
    sandbox_enforced: bool = False
    workspace_isolation_bound: bool = False
    filesystem_write_policy_bound: bool = False
    network_policy_bound: bool = False
    resource_limits_bound: bool = False
    timeout_policy_bound: bool = False
    stdout_stderr_capture_bound: bool = False
    kill_switch_bound: bool = False
    command_allowlist_enforced: bool = False
    receipt_prewrite_bound: bool = False
    receipt_final_write_bound: bool = False
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    repo_code_executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSandboxProviderContract | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        sandbox_readiness_id = _safe_str(data.get("sandbox_readiness_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        workspace_id = _safe_str(data.get("workspace_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not sandbox_readiness_id
            or not preflight_id
            or not workspace_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_SANDBOX_PROVIDER_CONTRACT_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            sandbox_readiness_id=sandbox_readiness_id,
            command_allowlist_enforcement_id=_safe_str(data.get("command_allowlist_enforcement_id")).strip(),
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=workspace_id,
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            contract_kind=_safe_str(data.get("contract_kind")).strip() or "francis.lab.sandbox_provider_contract",
            contract_mode=_safe_str(data.get("contract_mode")).strip()
            or "provider_contract_preflight_only_no_execution",
            provider_kind=_safe_str(data.get("provider_kind")).strip() or "unbound",
            provider_contract=_safe_dict(data.get("provider_contract")),
            runner_sandbox_readiness=_safe_dict(data.get("runner_sandbox_readiness")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            provider_contract_declared=bool(data.get("provider_contract_declared", False)),
            sandbox_provider_bound=bool(data.get("sandbox_provider_bound", False)),
            sandbox_bound=bool(data.get("sandbox_bound", False)),
            sandbox_enforced=bool(data.get("sandbox_enforced", False)),
            workspace_isolation_bound=bool(data.get("workspace_isolation_bound", False)),
            filesystem_write_policy_bound=bool(data.get("filesystem_write_policy_bound", False)),
            network_policy_bound=bool(data.get("network_policy_bound", False)),
            resource_limits_bound=bool(data.get("resource_limits_bound", False)),
            timeout_policy_bound=bool(data.get("timeout_policy_bound", False)),
            stdout_stderr_capture_bound=bool(data.get("stdout_stderr_capture_bound", False)),
            kill_switch_bound=bool(data.get("kill_switch_bound", False)),
            command_allowlist_enforced=bool(data.get("command_allowlist_enforced", False)),
            receipt_prewrite_bound=bool(data.get("receipt_prewrite_bound", False)),
            receipt_final_write_bound=bool(data.get("receipt_final_write_bound", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSandboxProviderBindingPreflight:
    id: str
    approval_id: str
    sandbox_provider_contract_id: str
    sandbox_readiness_id: str
    command_allowlist_enforcement_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    binding_kind: str = "francis.lab.sandbox_provider_binding_preflight"
    binding_mode: str = "binding_preflight_only_no_execution"
    provider_kind: str = "unbound"
    provider_contract: dict[str, Any] = field(default_factory=dict)
    provider_binding_contract: dict[str, Any] = field(default_factory=dict)
    sandbox_provider_contract: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    provider_contract_present: bool = False
    provider_contract_ready: bool = False
    provider_contract_declared: bool = False
    provider_kind_selected: bool = False
    provider_binary_or_service_verified: bool = False
    provider_policy_manifest_bound: bool = False
    sandbox_provider_bound: bool = False
    sandbox_bound: bool = False
    sandbox_enforced: bool = False
    workspace_isolation_bound: bool = False
    filesystem_write_policy_bound: bool = False
    network_policy_bound: bool = False
    resource_limits_bound: bool = False
    timeout_policy_bound: bool = False
    stdout_stderr_capture_bound: bool = False
    kill_switch_bound: bool = False
    command_allowlist_enforced: bool = False
    receipt_prewrite_bound: bool = False
    receipt_final_write_bound: bool = False
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    repo_code_executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSandboxProviderBindingPreflight | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        provider_contract_id = _safe_str(data.get("sandbox_provider_contract_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        workspace_id = _safe_str(data.get("workspace_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not provider_contract_id
            or not preflight_id
            or not workspace_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_SANDBOX_PROVIDER_BINDING_PREFLIGHT_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            sandbox_provider_contract_id=provider_contract_id,
            sandbox_readiness_id=_safe_str(data.get("sandbox_readiness_id")).strip(),
            command_allowlist_enforcement_id=_safe_str(data.get("command_allowlist_enforcement_id")).strip(),
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=workspace_id,
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            binding_kind=_safe_str(data.get("binding_kind")).strip()
            or "francis.lab.sandbox_provider_binding_preflight",
            binding_mode=_safe_str(data.get("binding_mode")).strip() or "binding_preflight_only_no_execution",
            provider_kind=_safe_str(data.get("provider_kind")).strip() or "unbound",
            provider_contract=_safe_dict(data.get("provider_contract")),
            provider_binding_contract=_safe_dict(data.get("provider_binding_contract")),
            sandbox_provider_contract=_safe_dict(data.get("sandbox_provider_contract")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            provider_contract_present=bool(data.get("provider_contract_present", False)),
            provider_contract_ready=bool(data.get("provider_contract_ready", False)),
            provider_contract_declared=bool(data.get("provider_contract_declared", False)),
            provider_kind_selected=bool(data.get("provider_kind_selected", False)),
            provider_binary_or_service_verified=bool(data.get("provider_binary_or_service_verified", False)),
            provider_policy_manifest_bound=bool(data.get("provider_policy_manifest_bound", False)),
            sandbox_provider_bound=bool(data.get("sandbox_provider_bound", False)),
            sandbox_bound=bool(data.get("sandbox_bound", False)),
            sandbox_enforced=bool(data.get("sandbox_enforced", False)),
            workspace_isolation_bound=bool(data.get("workspace_isolation_bound", False)),
            filesystem_write_policy_bound=bool(data.get("filesystem_write_policy_bound", False)),
            network_policy_bound=bool(data.get("network_policy_bound", False)),
            resource_limits_bound=bool(data.get("resource_limits_bound", False)),
            timeout_policy_bound=bool(data.get("timeout_policy_bound", False)),
            stdout_stderr_capture_bound=bool(data.get("stdout_stderr_capture_bound", False)),
            kill_switch_bound=bool(data.get("kill_switch_bound", False)),
            command_allowlist_enforced=bool(data.get("command_allowlist_enforced", False)),
            receipt_prewrite_bound=bool(data.get("receipt_prewrite_bound", False)),
            receipt_final_write_bound=bool(data.get("receipt_final_write_bound", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSandboxProviderSelectionPreflight:
    id: str
    approval_id: str
    sandbox_provider_binding_id: str
    sandbox_provider_contract_id: str
    sandbox_readiness_id: str
    command_allowlist_enforcement_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    selection_kind: str = "francis.lab.sandbox_provider_selection_preflight"
    selection_mode: str = "selection_verification_preflight_only_no_execution"
    requested_provider_kind: str = "unselected"
    selected_provider_kind: str = "unselected"
    provider_reference: str = ""
    provider_reference_kind: str = "none"
    provider_policy_manifest_path: str = ""
    provider_selection_policy: dict[str, Any] = field(default_factory=dict)
    provider_verification: dict[str, Any] = field(default_factory=dict)
    sandbox_provider_binding: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    provider_binding_present: bool = False
    provider_binding_ready: bool = False
    provider_selection_policy_declared: bool = False
    provider_kind_allowed_by_policy: bool = False
    provider_kind_selected: bool = False
    provider_reference_checked: bool = False
    provider_reference_present: bool = False
    provider_reference_verified: bool = False
    provider_binary_or_service_verified: bool = False
    provider_policy_manifest_present: bool = False
    provider_policy_manifest_bound: bool = False
    sandbox_provider_bound: bool = False
    sandbox_bound: bool = False
    sandbox_enforced: bool = False
    workspace_isolation_bound: bool = False
    filesystem_write_policy_bound: bool = False
    network_policy_bound: bool = False
    resource_limits_bound: bool = False
    timeout_policy_bound: bool = False
    stdout_stderr_capture_bound: bool = False
    kill_switch_bound: bool = False
    command_allowlist_enforced: bool = False
    receipt_prewrite_bound: bool = False
    receipt_final_write_bound: bool = False
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    repo_code_executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSandboxProviderSelectionPreflight | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        provider_binding_id = _safe_str(data.get("sandbox_provider_binding_id")).strip()
        provider_contract_id = _safe_str(data.get("sandbox_provider_contract_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        workspace_id = _safe_str(data.get("workspace_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not provider_binding_id
            or not provider_contract_id
            or not preflight_id
            or not workspace_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_SANDBOX_PROVIDER_SELECTION_PREFLIGHT_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            sandbox_provider_binding_id=provider_binding_id,
            sandbox_provider_contract_id=provider_contract_id,
            sandbox_readiness_id=_safe_str(data.get("sandbox_readiness_id")).strip(),
            command_allowlist_enforcement_id=_safe_str(data.get("command_allowlist_enforcement_id")).strip(),
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=workspace_id,
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            selection_kind=_safe_str(data.get("selection_kind")).strip()
            or "francis.lab.sandbox_provider_selection_preflight",
            selection_mode=_safe_str(data.get("selection_mode")).strip()
            or "selection_verification_preflight_only_no_execution",
            requested_provider_kind=_safe_str(data.get("requested_provider_kind")).strip() or "unselected",
            selected_provider_kind=_safe_str(data.get("selected_provider_kind")).strip() or "unselected",
            provider_reference=_safe_str(data.get("provider_reference")).strip(),
            provider_reference_kind=_safe_str(data.get("provider_reference_kind")).strip() or "none",
            provider_policy_manifest_path=_safe_str(data.get("provider_policy_manifest_path")).strip(),
            provider_selection_policy=_safe_dict(data.get("provider_selection_policy")),
            provider_verification=_safe_dict(data.get("provider_verification")),
            sandbox_provider_binding=_safe_dict(data.get("sandbox_provider_binding")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            provider_binding_present=bool(data.get("provider_binding_present", False)),
            provider_binding_ready=bool(data.get("provider_binding_ready", False)),
            provider_selection_policy_declared=bool(data.get("provider_selection_policy_declared", False)),
            provider_kind_allowed_by_policy=bool(data.get("provider_kind_allowed_by_policy", False)),
            provider_kind_selected=bool(data.get("provider_kind_selected", False)),
            provider_reference_checked=bool(data.get("provider_reference_checked", False)),
            provider_reference_present=bool(data.get("provider_reference_present", False)),
            provider_reference_verified=bool(data.get("provider_reference_verified", False)),
            provider_binary_or_service_verified=bool(data.get("provider_binary_or_service_verified", False)),
            provider_policy_manifest_present=bool(data.get("provider_policy_manifest_present", False)),
            provider_policy_manifest_bound=bool(data.get("provider_policy_manifest_bound", False)),
            sandbox_provider_bound=bool(data.get("sandbox_provider_bound", False)),
            sandbox_bound=bool(data.get("sandbox_bound", False)),
            sandbox_enforced=bool(data.get("sandbox_enforced", False)),
            workspace_isolation_bound=bool(data.get("workspace_isolation_bound", False)),
            filesystem_write_policy_bound=bool(data.get("filesystem_write_policy_bound", False)),
            network_policy_bound=bool(data.get("network_policy_bound", False)),
            resource_limits_bound=bool(data.get("resource_limits_bound", False)),
            timeout_policy_bound=bool(data.get("timeout_policy_bound", False)),
            stdout_stderr_capture_bound=bool(data.get("stdout_stderr_capture_bound", False)),
            kill_switch_bound=bool(data.get("kill_switch_bound", False)),
            command_allowlist_enforced=bool(data.get("command_allowlist_enforced", False)),
            receipt_prewrite_bound=bool(data.get("receipt_prewrite_bound", False)),
            receipt_final_write_bound=bool(data.get("receipt_final_write_bound", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSandboxProviderVerifierPreflight:
    id: str
    approval_id: str
    sandbox_provider_selection_id: str
    sandbox_provider_binding_id: str
    sandbox_provider_contract_id: str
    sandbox_readiness_id: str
    command_allowlist_enforcement_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    verifier_kind: str = "francis.lab.sandbox_provider_verifier_preflight"
    verifier_mode: str = "verifier_contract_preflight_only_no_execution"
    provider_kind: str = "unselected"
    provider_reference: str = ""
    provider_policy_manifest_path: str = ""
    verifier_identity: dict[str, Any] = field(default_factory=dict)
    provider_identity: dict[str, Any] = field(default_factory=dict)
    provider_policy_manifest: dict[str, Any] = field(default_factory=dict)
    provider_runtime_probe: dict[str, Any] = field(default_factory=dict)
    verifier_contract: dict[str, Any] = field(default_factory=dict)
    verifier_boundary: dict[str, Any] = field(default_factory=dict)
    sandbox_provider_selection: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    provider_selection_present: bool = False
    provider_selection_ready: bool = False
    provider_kind_selected: bool = False
    provider_reference_verified: bool = False
    provider_policy_manifest_bound: bool = False
    verifier_contract_declared: bool = False
    verifier_implementation_bound: bool = False
    verifier_identity_bound: bool = False
    verifier_policy_bound: bool = False
    verifier_receipt_contract_bound: bool = False
    static_identity_verification_performed: bool = False
    provider_reference_fingerprint_captured: bool = False
    provider_policy_manifest_hash_captured: bool = False
    provider_binary_or_service_verified: bool = False
    provider_runtime_probe_performed: bool = False
    provider_version_captured: bool = False
    provider_identity_fingerprint_captured: bool = False
    service_query_performed: bool = False
    process_launched: bool = False
    container_launched: bool = False
    sandbox_provider_bound: bool = False
    sandbox_bound: bool = False
    sandbox_enforced: bool = False
    workspace_isolation_bound: bool = False
    filesystem_write_policy_bound: bool = False
    network_policy_bound: bool = False
    resource_limits_bound: bool = False
    timeout_policy_bound: bool = False
    stdout_stderr_capture_bound: bool = False
    kill_switch_bound: bool = False
    command_allowlist_enforced: bool = False
    receipt_prewrite_bound: bool = False
    receipt_final_write_bound: bool = False
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    repo_code_executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSandboxProviderVerifierPreflight | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        selection_id = _safe_str(data.get("sandbox_provider_selection_id")).strip()
        provider_binding_id = _safe_str(data.get("sandbox_provider_binding_id")).strip()
        provider_contract_id = _safe_str(data.get("sandbox_provider_contract_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        workspace_id = _safe_str(data.get("workspace_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not selection_id
            or not provider_binding_id
            or not provider_contract_id
            or not preflight_id
            or not workspace_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_SANDBOX_PROVIDER_VERIFIER_PREFLIGHT_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            sandbox_provider_selection_id=selection_id,
            sandbox_provider_binding_id=provider_binding_id,
            sandbox_provider_contract_id=provider_contract_id,
            sandbox_readiness_id=_safe_str(data.get("sandbox_readiness_id")).strip(),
            command_allowlist_enforcement_id=_safe_str(data.get("command_allowlist_enforcement_id")).strip(),
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=workspace_id,
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            verifier_kind=_safe_str(data.get("verifier_kind")).strip()
            or "francis.lab.sandbox_provider_verifier_preflight",
            verifier_mode=_safe_str(data.get("verifier_mode")).strip()
            or "verifier_contract_preflight_only_no_execution",
            provider_kind=_safe_str(data.get("provider_kind")).strip() or "unselected",
            provider_reference=_safe_str(data.get("provider_reference")).strip(),
            provider_policy_manifest_path=_safe_str(data.get("provider_policy_manifest_path")).strip(),
            verifier_identity=_safe_dict(data.get("verifier_identity")),
            provider_identity=_safe_dict(data.get("provider_identity")),
            provider_policy_manifest=_safe_dict(data.get("provider_policy_manifest")),
            provider_runtime_probe=_safe_dict(data.get("provider_runtime_probe")),
            verifier_contract=_safe_dict(data.get("verifier_contract")),
            verifier_boundary=_safe_dict(data.get("verifier_boundary")),
            sandbox_provider_selection=_safe_dict(data.get("sandbox_provider_selection")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            provider_selection_present=bool(data.get("provider_selection_present", False)),
            provider_selection_ready=bool(data.get("provider_selection_ready", False)),
            provider_kind_selected=bool(data.get("provider_kind_selected", False)),
            provider_reference_verified=bool(data.get("provider_reference_verified", False)),
            provider_policy_manifest_bound=bool(data.get("provider_policy_manifest_bound", False)),
            verifier_contract_declared=bool(data.get("verifier_contract_declared", False)),
            verifier_implementation_bound=bool(data.get("verifier_implementation_bound", False)),
            verifier_identity_bound=bool(data.get("verifier_identity_bound", False)),
            verifier_policy_bound=bool(data.get("verifier_policy_bound", False)),
            verifier_receipt_contract_bound=bool(data.get("verifier_receipt_contract_bound", False)),
            static_identity_verification_performed=bool(data.get("static_identity_verification_performed", False)),
            provider_reference_fingerprint_captured=bool(data.get("provider_reference_fingerprint_captured", False)),
            provider_policy_manifest_hash_captured=bool(data.get("provider_policy_manifest_hash_captured", False)),
            provider_binary_or_service_verified=bool(data.get("provider_binary_or_service_verified", False)),
            provider_runtime_probe_performed=bool(data.get("provider_runtime_probe_performed", False)),
            provider_version_captured=bool(data.get("provider_version_captured", False)),
            provider_identity_fingerprint_captured=bool(data.get("provider_identity_fingerprint_captured", False)),
            service_query_performed=bool(data.get("service_query_performed", False)),
            process_launched=bool(data.get("process_launched", False)),
            container_launched=bool(data.get("container_launched", False)),
            sandbox_provider_bound=bool(data.get("sandbox_provider_bound", False)),
            sandbox_bound=bool(data.get("sandbox_bound", False)),
            sandbox_enforced=bool(data.get("sandbox_enforced", False)),
            workspace_isolation_bound=bool(data.get("workspace_isolation_bound", False)),
            filesystem_write_policy_bound=bool(data.get("filesystem_write_policy_bound", False)),
            network_policy_bound=bool(data.get("network_policy_bound", False)),
            resource_limits_bound=bool(data.get("resource_limits_bound", False)),
            timeout_policy_bound=bool(data.get("timeout_policy_bound", False)),
            stdout_stderr_capture_bound=bool(data.get("stdout_stderr_capture_bound", False)),
            kill_switch_bound=bool(data.get("kill_switch_bound", False)),
            command_allowlist_enforced=bool(data.get("command_allowlist_enforced", False)),
            receipt_prewrite_bound=bool(data.get("receipt_prewrite_bound", False)),
            receipt_final_write_bound=bool(data.get("receipt_final_write_bound", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSandboxProviderRuntimeProbePreflight:
    id: str
    approval_id: str
    sandbox_provider_verifier_id: str
    sandbox_provider_selection_id: str
    sandbox_provider_binding_id: str
    sandbox_provider_contract_id: str
    sandbox_readiness_id: str
    command_allowlist_enforcement_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    probe_kind: str = "francis.lab.sandbox_provider_runtime_probe_preflight"
    probe_mode: str = "runtime_probe_contract_preflight_only_no_provider_execution"
    provider_kind: str = "unselected"
    provider_reference: str = ""
    provider_policy_manifest_path: str = ""
    provider_identity: dict[str, Any] = field(default_factory=dict)
    provider_policy_manifest: dict[str, Any] = field(default_factory=dict)
    runtime_probe_contract: dict[str, Any] = field(default_factory=dict)
    runtime_probe_boundary: dict[str, Any] = field(default_factory=dict)
    sandbox_provider_verifier: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    verifier_present: bool = False
    verifier_static_identity_ready: bool = False
    provider_identity_fingerprint_captured: bool = False
    provider_binary_or_service_verified: bool = False
    runtime_probe_contract_declared: bool = False
    runtime_probe_authorization_required: bool = False
    runtime_probe_policy_bound: bool = False
    runtime_probe_timeout_policy_declared: bool = False
    runtime_probe_network_blocked_by_contract: bool = False
    runtime_probe_workspace_isolation_required: bool = False
    runtime_probe_receipt_contract_declared: bool = False
    runtime_probe_repo_execution_separated: bool = False
    runtime_probe_runner_bound: bool = False
    runtime_probe_sandbox_bound: bool = False
    runtime_probe_service_query_guard_bound: bool = False
    runtime_probe_output_capture_bound: bool = False
    runtime_probe_kill_switch_bound: bool = False
    provider_runtime_probe_performed: bool = False
    service_query_performed: bool = False
    process_launched: bool = False
    container_launched: bool = False
    sandbox_provider_bound: bool = False
    sandbox_bound: bool = False
    sandbox_enforced: bool = False
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    repo_code_executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSandboxProviderRuntimeProbePreflight | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        verifier_id = _safe_str(data.get("sandbox_provider_verifier_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        workspace_id = _safe_str(data.get("workspace_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not verifier_id
            or not preflight_id
            or not workspace_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_PREFLIGHT_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            sandbox_provider_verifier_id=verifier_id,
            sandbox_provider_selection_id=_safe_str(data.get("sandbox_provider_selection_id")).strip(),
            sandbox_provider_binding_id=_safe_str(data.get("sandbox_provider_binding_id")).strip(),
            sandbox_provider_contract_id=_safe_str(data.get("sandbox_provider_contract_id")).strip(),
            sandbox_readiness_id=_safe_str(data.get("sandbox_readiness_id")).strip(),
            command_allowlist_enforcement_id=_safe_str(data.get("command_allowlist_enforcement_id")).strip(),
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=workspace_id,
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            probe_kind=_safe_str(data.get("probe_kind")).strip()
            or "francis.lab.sandbox_provider_runtime_probe_preflight",
            probe_mode=_safe_str(data.get("probe_mode")).strip()
            or "runtime_probe_contract_preflight_only_no_provider_execution",
            provider_kind=_safe_str(data.get("provider_kind")).strip() or "unselected",
            provider_reference=_safe_str(data.get("provider_reference")).strip(),
            provider_policy_manifest_path=_safe_str(data.get("provider_policy_manifest_path")).strip(),
            provider_identity=_safe_dict(data.get("provider_identity")),
            provider_policy_manifest=_safe_dict(data.get("provider_policy_manifest")),
            runtime_probe_contract=_safe_dict(data.get("runtime_probe_contract")),
            runtime_probe_boundary=_safe_dict(data.get("runtime_probe_boundary")),
            sandbox_provider_verifier=_safe_dict(data.get("sandbox_provider_verifier")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            verifier_present=bool(data.get("verifier_present", False)),
            verifier_static_identity_ready=bool(data.get("verifier_static_identity_ready", False)),
            provider_identity_fingerprint_captured=bool(data.get("provider_identity_fingerprint_captured", False)),
            provider_binary_or_service_verified=bool(data.get("provider_binary_or_service_verified", False)),
            runtime_probe_contract_declared=bool(data.get("runtime_probe_contract_declared", False)),
            runtime_probe_authorization_required=bool(data.get("runtime_probe_authorization_required", False)),
            runtime_probe_policy_bound=bool(data.get("runtime_probe_policy_bound", False)),
            runtime_probe_timeout_policy_declared=bool(data.get("runtime_probe_timeout_policy_declared", False)),
            runtime_probe_network_blocked_by_contract=bool(
                data.get("runtime_probe_network_blocked_by_contract", False)
            ),
            runtime_probe_workspace_isolation_required=bool(
                data.get("runtime_probe_workspace_isolation_required", False)
            ),
            runtime_probe_receipt_contract_declared=bool(data.get("runtime_probe_receipt_contract_declared", False)),
            runtime_probe_repo_execution_separated=bool(data.get("runtime_probe_repo_execution_separated", False)),
            runtime_probe_runner_bound=bool(data.get("runtime_probe_runner_bound", False)),
            runtime_probe_sandbox_bound=bool(data.get("runtime_probe_sandbox_bound", False)),
            runtime_probe_service_query_guard_bound=bool(data.get("runtime_probe_service_query_guard_bound", False)),
            runtime_probe_output_capture_bound=bool(data.get("runtime_probe_output_capture_bound", False)),
            runtime_probe_kill_switch_bound=bool(data.get("runtime_probe_kill_switch_bound", False)),
            provider_runtime_probe_performed=bool(data.get("provider_runtime_probe_performed", False)),
            service_query_performed=bool(data.get("service_query_performed", False)),
            process_launched=bool(data.get("process_launched", False)),
            container_launched=bool(data.get("container_launched", False)),
            sandbox_provider_bound=bool(data.get("sandbox_provider_bound", False)),
            sandbox_bound=bool(data.get("sandbox_bound", False)),
            sandbox_enforced=bool(data.get("sandbox_enforced", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSandboxProviderRuntimeProbeHarnessPreflight:
    id: str
    approval_id: str
    sandbox_provider_runtime_probe_id: str
    sandbox_provider_verifier_id: str
    sandbox_provider_selection_id: str
    sandbox_provider_binding_id: str
    sandbox_provider_contract_id: str
    sandbox_readiness_id: str
    command_allowlist_enforcement_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    harness_kind: str = "francis.lab.sandbox_provider_runtime_probe_harness_preflight"
    harness_mode: str = "runtime_probe_harness_preflight_only_no_provider_execution"
    provider_kind: str = "unselected"
    provider_reference: str = ""
    provider_identity: dict[str, Any] = field(default_factory=dict)
    runtime_probe_contract: dict[str, Any] = field(default_factory=dict)
    runtime_probe_harness_contract: dict[str, Any] = field(default_factory=dict)
    sandbox_provider_runtime_probe: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    runtime_probe_preflight_present: bool = False
    runtime_probe_contract_declared: bool = False
    runtime_probe_authorization_required: bool = False
    runtime_probe_network_blocked_by_contract: bool = False
    runtime_probe_workspace_isolation_required: bool = False
    runtime_probe_receipt_contract_declared: bool = False
    runtime_probe_repo_execution_separated: bool = False
    runtime_probe_runner_contract_declared: bool = False
    runtime_probe_runner_bound: bool = False
    runtime_probe_sandbox_contract_declared: bool = False
    runtime_probe_sandbox_bound: bool = False
    runtime_probe_service_query_guard_declared: bool = False
    runtime_probe_service_query_guard_bound: bool = False
    runtime_probe_output_capture_declared: bool = False
    runtime_probe_output_capture_bound: bool = False
    runtime_probe_kill_switch_declared: bool = False
    runtime_probe_kill_switch_bound: bool = False
    provider_runtime_probe_performed: bool = False
    service_query_performed: bool = False
    process_launched: bool = False
    container_launched: bool = False
    sandbox_provider_bound: bool = False
    sandbox_bound: bool = False
    sandbox_enforced: bool = False
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    repo_code_executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSandboxProviderRuntimeProbeHarnessPreflight | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        runtime_probe_id = _safe_str(data.get("sandbox_provider_runtime_probe_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        workspace_id = _safe_str(data.get("workspace_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not runtime_probe_id
            or not preflight_id
            or not workspace_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_HARNESS_PREFLIGHT_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            sandbox_provider_runtime_probe_id=runtime_probe_id,
            sandbox_provider_verifier_id=_safe_str(data.get("sandbox_provider_verifier_id")).strip(),
            sandbox_provider_selection_id=_safe_str(data.get("sandbox_provider_selection_id")).strip(),
            sandbox_provider_binding_id=_safe_str(data.get("sandbox_provider_binding_id")).strip(),
            sandbox_provider_contract_id=_safe_str(data.get("sandbox_provider_contract_id")).strip(),
            sandbox_readiness_id=_safe_str(data.get("sandbox_readiness_id")).strip(),
            command_allowlist_enforcement_id=_safe_str(data.get("command_allowlist_enforcement_id")).strip(),
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=workspace_id,
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            harness_kind=_safe_str(data.get("harness_kind")).strip()
            or "francis.lab.sandbox_provider_runtime_probe_harness_preflight",
            harness_mode=_safe_str(data.get("harness_mode")).strip()
            or "runtime_probe_harness_preflight_only_no_provider_execution",
            provider_kind=_safe_str(data.get("provider_kind")).strip() or "unselected",
            provider_reference=_safe_str(data.get("provider_reference")).strip(),
            provider_identity=_safe_dict(data.get("provider_identity")),
            runtime_probe_contract=_safe_dict(data.get("runtime_probe_contract")),
            runtime_probe_harness_contract=_safe_dict(data.get("runtime_probe_harness_contract")),
            sandbox_provider_runtime_probe=_safe_dict(data.get("sandbox_provider_runtime_probe")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            runtime_probe_preflight_present=bool(data.get("runtime_probe_preflight_present", False)),
            runtime_probe_contract_declared=bool(data.get("runtime_probe_contract_declared", False)),
            runtime_probe_authorization_required=bool(data.get("runtime_probe_authorization_required", False)),
            runtime_probe_network_blocked_by_contract=bool(
                data.get("runtime_probe_network_blocked_by_contract", False)
            ),
            runtime_probe_workspace_isolation_required=bool(
                data.get("runtime_probe_workspace_isolation_required", False)
            ),
            runtime_probe_receipt_contract_declared=bool(data.get("runtime_probe_receipt_contract_declared", False)),
            runtime_probe_repo_execution_separated=bool(data.get("runtime_probe_repo_execution_separated", False)),
            runtime_probe_runner_contract_declared=bool(data.get("runtime_probe_runner_contract_declared", False)),
            runtime_probe_runner_bound=bool(data.get("runtime_probe_runner_bound", False)),
            runtime_probe_sandbox_contract_declared=bool(data.get("runtime_probe_sandbox_contract_declared", False)),
            runtime_probe_sandbox_bound=bool(data.get("runtime_probe_sandbox_bound", False)),
            runtime_probe_service_query_guard_declared=bool(
                data.get("runtime_probe_service_query_guard_declared", False)
            ),
            runtime_probe_service_query_guard_bound=bool(data.get("runtime_probe_service_query_guard_bound", False)),
            runtime_probe_output_capture_declared=bool(data.get("runtime_probe_output_capture_declared", False)),
            runtime_probe_output_capture_bound=bool(data.get("runtime_probe_output_capture_bound", False)),
            runtime_probe_kill_switch_declared=bool(data.get("runtime_probe_kill_switch_declared", False)),
            runtime_probe_kill_switch_bound=bool(data.get("runtime_probe_kill_switch_bound", False)),
            provider_runtime_probe_performed=bool(data.get("provider_runtime_probe_performed", False)),
            service_query_performed=bool(data.get("service_query_performed", False)),
            process_launched=bool(data.get("process_launched", False)),
            container_launched=bool(data.get("container_launched", False)),
            sandbox_provider_bound=bool(data.get("sandbox_provider_bound", False)),
            sandbox_bound=bool(data.get("sandbox_bound", False)),
            sandbox_enforced=bool(data.get("sandbox_enforced", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSandboxProviderRuntimeProbeRunnerReadiness:
    id: str
    approval_id: str
    sandbox_provider_runtime_probe_harness_id: str
    sandbox_provider_runtime_probe_id: str
    sandbox_provider_verifier_id: str
    sandbox_provider_selection_id: str
    sandbox_provider_binding_id: str
    sandbox_provider_contract_id: str
    sandbox_readiness_id: str
    command_allowlist_enforcement_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    runner_kind: str = "francis.lab.sandbox_provider_runtime_probe_runner_readiness"
    runner_mode: str = "probe_runner_interface_readiness_only_no_provider_execution"
    provider_kind: str = "unselected"
    provider_reference: str = ""
    provider_identity: dict[str, Any] = field(default_factory=dict)
    probe_runner_interface: dict[str, Any] = field(default_factory=dict)
    probe_runner_boundary: dict[str, Any] = field(default_factory=dict)
    sandbox_provider_runtime_probe_harness: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    runtime_probe_harness_present: bool = False
    runtime_probe_harness_contract_declared: bool = False
    probe_runner_interface_declared: bool = False
    probe_runner_implementation_bound: bool = False
    probe_runner_identity_bound: bool = False
    probe_runner_policy_bound: bool = False
    probe_runner_sandbox_bound: bool = False
    probe_runner_network_blocked: bool = False
    probe_runner_workspace_isolated: bool = False
    probe_runner_timeout_bound: bool = False
    probe_runner_output_capture_bound: bool = False
    probe_runner_kill_switch_bound: bool = False
    probe_runner_receipt_contract_bound: bool = False
    provider_runtime_probe_performed: bool = False
    service_query_performed: bool = False
    process_launched: bool = False
    container_launched: bool = False
    sandbox_provider_bound: bool = False
    sandbox_bound: bool = False
    sandbox_enforced: bool = False
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    repo_code_executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSandboxProviderRuntimeProbeRunnerReadiness | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        harness_id = _safe_str(data.get("sandbox_provider_runtime_probe_harness_id")).strip()
        runtime_probe_id = _safe_str(data.get("sandbox_provider_runtime_probe_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        workspace_id = _safe_str(data.get("workspace_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not harness_id
            or not runtime_probe_id
            or not preflight_id
            or not workspace_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_READINESS_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            sandbox_provider_runtime_probe_harness_id=harness_id,
            sandbox_provider_runtime_probe_id=runtime_probe_id,
            sandbox_provider_verifier_id=_safe_str(data.get("sandbox_provider_verifier_id")).strip(),
            sandbox_provider_selection_id=_safe_str(data.get("sandbox_provider_selection_id")).strip(),
            sandbox_provider_binding_id=_safe_str(data.get("sandbox_provider_binding_id")).strip(),
            sandbox_provider_contract_id=_safe_str(data.get("sandbox_provider_contract_id")).strip(),
            sandbox_readiness_id=_safe_str(data.get("sandbox_readiness_id")).strip(),
            command_allowlist_enforcement_id=_safe_str(data.get("command_allowlist_enforcement_id")).strip(),
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=workspace_id,
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            runner_kind=_safe_str(data.get("runner_kind")).strip()
            or "francis.lab.sandbox_provider_runtime_probe_runner_readiness",
            runner_mode=_safe_str(data.get("runner_mode")).strip()
            or "probe_runner_interface_readiness_only_no_provider_execution",
            provider_kind=_safe_str(data.get("provider_kind")).strip() or "unselected",
            provider_reference=_safe_str(data.get("provider_reference")).strip(),
            provider_identity=_safe_dict(data.get("provider_identity")),
            probe_runner_interface=_safe_dict(data.get("probe_runner_interface")),
            probe_runner_boundary=_safe_dict(data.get("probe_runner_boundary")),
            sandbox_provider_runtime_probe_harness=_safe_dict(data.get("sandbox_provider_runtime_probe_harness")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            runtime_probe_harness_present=bool(data.get("runtime_probe_harness_present", False)),
            runtime_probe_harness_contract_declared=bool(data.get("runtime_probe_harness_contract_declared", False)),
            probe_runner_interface_declared=bool(data.get("probe_runner_interface_declared", False)),
            probe_runner_implementation_bound=bool(data.get("probe_runner_implementation_bound", False)),
            probe_runner_identity_bound=bool(data.get("probe_runner_identity_bound", False)),
            probe_runner_policy_bound=bool(data.get("probe_runner_policy_bound", False)),
            probe_runner_sandbox_bound=bool(data.get("probe_runner_sandbox_bound", False)),
            probe_runner_network_blocked=bool(data.get("probe_runner_network_blocked", False)),
            probe_runner_workspace_isolated=bool(data.get("probe_runner_workspace_isolated", False)),
            probe_runner_timeout_bound=bool(data.get("probe_runner_timeout_bound", False)),
            probe_runner_output_capture_bound=bool(data.get("probe_runner_output_capture_bound", False)),
            probe_runner_kill_switch_bound=bool(data.get("probe_runner_kill_switch_bound", False)),
            probe_runner_receipt_contract_bound=bool(data.get("probe_runner_receipt_contract_bound", False)),
            provider_runtime_probe_performed=bool(data.get("provider_runtime_probe_performed", False)),
            service_query_performed=bool(data.get("service_query_performed", False)),
            process_launched=bool(data.get("process_launched", False)),
            container_launched=bool(data.get("container_launched", False)),
            sandbox_provider_bound=bool(data.get("sandbox_provider_bound", False)),
            sandbox_bound=bool(data.get("sandbox_bound", False)),
            sandbox_enforced=bool(data.get("sandbox_enforced", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSandboxProviderRuntimeProbeRunnerBindingPreflight:
    id: str
    approval_id: str
    sandbox_provider_runtime_probe_runner_readiness_id: str
    sandbox_provider_runtime_probe_harness_id: str
    sandbox_provider_runtime_probe_id: str
    sandbox_provider_verifier_id: str
    sandbox_provider_selection_id: str
    sandbox_provider_binding_id: str
    sandbox_provider_contract_id: str
    sandbox_readiness_id: str
    command_allowlist_enforcement_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    runner_kind: str = "francis.lab.sandbox_provider_runtime_probe_runner_binding_preflight"
    binding_mode: str = "probe_runner_binding_preflight_no_provider_execution"
    provider_kind: str = "unselected"
    provider_reference: str = ""
    provider_identity: dict[str, Any] = field(default_factory=dict)
    probe_runner_binding_contract: dict[str, Any] = field(default_factory=dict)
    sandbox_provider_runtime_probe_runner_readiness: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    runner_readiness_present: bool = False
    probe_runner_interface_declared: bool = False
    probe_runner_readiness_ready: bool = False
    probe_runner_binding_contract_declared: bool = False
    probe_runner_implementation_bound: bool = False
    probe_runner_identity_bound: bool = False
    probe_runner_policy_bound: bool = False
    probe_runner_sandbox_bound: bool = False
    probe_runner_network_blocked: bool = False
    probe_runner_workspace_isolated: bool = False
    probe_runner_timeout_bound: bool = False
    probe_runner_output_capture_bound: bool = False
    probe_runner_kill_switch_bound: bool = False
    probe_runner_receipt_contract_bound: bool = False
    probe_runner_bound: bool = False
    runtime_probe_bound: bool = False
    provider_runtime_probe_performed: bool = False
    service_query_performed: bool = False
    process_launched: bool = False
    container_launched: bool = False
    sandbox_provider_bound: bool = False
    sandbox_bound: bool = False
    sandbox_enforced: bool = False
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    repo_code_executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSandboxProviderRuntimeProbeRunnerBindingPreflight | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        readiness_id = _safe_str(data.get("sandbox_provider_runtime_probe_runner_readiness_id")).strip()
        harness_id = _safe_str(data.get("sandbox_provider_runtime_probe_harness_id")).strip()
        runtime_probe_id = _safe_str(data.get("sandbox_provider_runtime_probe_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        workspace_id = _safe_str(data.get("workspace_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not readiness_id
            or not harness_id
            or not runtime_probe_id
            or not preflight_id
            or not workspace_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_BINDING_PREFLIGHT_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            sandbox_provider_runtime_probe_runner_readiness_id=readiness_id,
            sandbox_provider_runtime_probe_harness_id=harness_id,
            sandbox_provider_runtime_probe_id=runtime_probe_id,
            sandbox_provider_verifier_id=_safe_str(data.get("sandbox_provider_verifier_id")).strip(),
            sandbox_provider_selection_id=_safe_str(data.get("sandbox_provider_selection_id")).strip(),
            sandbox_provider_binding_id=_safe_str(data.get("sandbox_provider_binding_id")).strip(),
            sandbox_provider_contract_id=_safe_str(data.get("sandbox_provider_contract_id")).strip(),
            sandbox_readiness_id=_safe_str(data.get("sandbox_readiness_id")).strip(),
            command_allowlist_enforcement_id=_safe_str(data.get("command_allowlist_enforcement_id")).strip(),
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=workspace_id,
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            runner_kind=_safe_str(data.get("runner_kind")).strip()
            or "francis.lab.sandbox_provider_runtime_probe_runner_binding_preflight",
            binding_mode=_safe_str(data.get("binding_mode")).strip()
            or "probe_runner_binding_preflight_no_provider_execution",
            provider_kind=_safe_str(data.get("provider_kind")).strip() or "unselected",
            provider_reference=_safe_str(data.get("provider_reference")).strip(),
            provider_identity=_safe_dict(data.get("provider_identity")),
            probe_runner_binding_contract=_safe_dict(data.get("probe_runner_binding_contract")),
            sandbox_provider_runtime_probe_runner_readiness=_safe_dict(
                data.get("sandbox_provider_runtime_probe_runner_readiness")
            ),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            runner_readiness_present=bool(data.get("runner_readiness_present", False)),
            probe_runner_interface_declared=bool(data.get("probe_runner_interface_declared", False)),
            probe_runner_readiness_ready=bool(data.get("probe_runner_readiness_ready", False)),
            probe_runner_binding_contract_declared=bool(data.get("probe_runner_binding_contract_declared", False)),
            probe_runner_implementation_bound=bool(data.get("probe_runner_implementation_bound", False)),
            probe_runner_identity_bound=bool(data.get("probe_runner_identity_bound", False)),
            probe_runner_policy_bound=bool(data.get("probe_runner_policy_bound", False)),
            probe_runner_sandbox_bound=bool(data.get("probe_runner_sandbox_bound", False)),
            probe_runner_network_blocked=bool(data.get("probe_runner_network_blocked", False)),
            probe_runner_workspace_isolated=bool(data.get("probe_runner_workspace_isolated", False)),
            probe_runner_timeout_bound=bool(data.get("probe_runner_timeout_bound", False)),
            probe_runner_output_capture_bound=bool(data.get("probe_runner_output_capture_bound", False)),
            probe_runner_kill_switch_bound=bool(data.get("probe_runner_kill_switch_bound", False)),
            probe_runner_receipt_contract_bound=bool(data.get("probe_runner_receipt_contract_bound", False)),
            probe_runner_bound=bool(data.get("probe_runner_bound", False)),
            runtime_probe_bound=bool(data.get("runtime_probe_bound", False)),
            provider_runtime_probe_performed=bool(data.get("provider_runtime_probe_performed", False)),
            service_query_performed=bool(data.get("service_query_performed", False)),
            process_launched=bool(data.get("process_launched", False)),
            container_launched=bool(data.get("container_launched", False)),
            sandbox_provider_bound=bool(data.get("sandbox_provider_bound", False)),
            sandbox_bound=bool(data.get("sandbox_bound", False)),
            sandbox_enforced=bool(data.get("sandbox_enforced", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSandboxProviderRuntimeProbeRunnerEnforcementPreflight:
    id: str
    approval_id: str
    sandbox_provider_runtime_probe_runner_binding_id: str
    sandbox_provider_runtime_probe_runner_readiness_id: str
    sandbox_provider_runtime_probe_harness_id: str
    sandbox_provider_runtime_probe_id: str
    sandbox_provider_verifier_id: str
    sandbox_provider_selection_id: str
    sandbox_provider_binding_id: str
    sandbox_provider_contract_id: str
    sandbox_readiness_id: str
    command_allowlist_enforcement_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    runner_kind: str = "francis.lab.sandbox_provider_runtime_probe_runner_enforcement_preflight"
    enforcement_mode: str = "probe_runner_enforcement_preflight_no_provider_execution"
    provider_kind: str = "unselected"
    provider_reference: str = ""
    provider_identity: dict[str, Any] = field(default_factory=dict)
    probe_runner_enforcement_contract: dict[str, Any] = field(default_factory=dict)
    sandbox_provider_runtime_probe_runner_binding: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    runner_binding_present: bool = False
    probe_runner_binding_contract_declared: bool = False
    probe_runner_binding_ready: bool = False
    probe_runner_enforcement_contract_declared: bool = False
    probe_runner_enforcement_bound: bool = False
    probe_runner_bound: bool = False
    runtime_probe_bound: bool = False
    probe_runner_identity_bound: bool = False
    probe_runner_policy_bound: bool = False
    probe_runner_sandbox_bound: bool = False
    probe_runner_network_blocked: bool = False
    probe_runner_workspace_isolated: bool = False
    probe_runner_timeout_bound: bool = False
    probe_runner_output_capture_bound: bool = False
    probe_runner_kill_switch_bound: bool = False
    probe_runner_receipt_contract_bound: bool = False
    provider_runtime_probe_performed: bool = False
    service_query_performed: bool = False
    process_launched: bool = False
    container_launched: bool = False
    sandbox_provider_bound: bool = False
    sandbox_bound: bool = False
    sandbox_enforced: bool = False
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    repo_code_executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSandboxProviderRuntimeProbeRunnerEnforcementPreflight | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        binding_id = _safe_str(data.get("sandbox_provider_runtime_probe_runner_binding_id")).strip()
        readiness_id = _safe_str(data.get("sandbox_provider_runtime_probe_runner_readiness_id")).strip()
        harness_id = _safe_str(data.get("sandbox_provider_runtime_probe_harness_id")).strip()
        runtime_probe_id = _safe_str(data.get("sandbox_provider_runtime_probe_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        workspace_id = _safe_str(data.get("workspace_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not binding_id
            or not readiness_id
            or not harness_id
            or not runtime_probe_id
            or not preflight_id
            or not workspace_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_ENFORCEMENT_PREFLIGHT_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            sandbox_provider_runtime_probe_runner_binding_id=binding_id,
            sandbox_provider_runtime_probe_runner_readiness_id=readiness_id,
            sandbox_provider_runtime_probe_harness_id=harness_id,
            sandbox_provider_runtime_probe_id=runtime_probe_id,
            sandbox_provider_verifier_id=_safe_str(data.get("sandbox_provider_verifier_id")).strip(),
            sandbox_provider_selection_id=_safe_str(data.get("sandbox_provider_selection_id")).strip(),
            sandbox_provider_binding_id=_safe_str(data.get("sandbox_provider_binding_id")).strip(),
            sandbox_provider_contract_id=_safe_str(data.get("sandbox_provider_contract_id")).strip(),
            sandbox_readiness_id=_safe_str(data.get("sandbox_readiness_id")).strip(),
            command_allowlist_enforcement_id=_safe_str(data.get("command_allowlist_enforcement_id")).strip(),
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=workspace_id,
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            runner_kind=_safe_str(data.get("runner_kind")).strip()
            or "francis.lab.sandbox_provider_runtime_probe_runner_enforcement_preflight",
            enforcement_mode=_safe_str(data.get("enforcement_mode")).strip()
            or "probe_runner_enforcement_preflight_no_provider_execution",
            provider_kind=_safe_str(data.get("provider_kind")).strip() or "unselected",
            provider_reference=_safe_str(data.get("provider_reference")).strip(),
            provider_identity=_safe_dict(data.get("provider_identity")),
            probe_runner_enforcement_contract=_safe_dict(data.get("probe_runner_enforcement_contract")),
            sandbox_provider_runtime_probe_runner_binding=_safe_dict(
                data.get("sandbox_provider_runtime_probe_runner_binding")
            ),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            runner_binding_present=bool(data.get("runner_binding_present", False)),
            probe_runner_binding_contract_declared=bool(data.get("probe_runner_binding_contract_declared", False)),
            probe_runner_binding_ready=bool(data.get("probe_runner_binding_ready", False)),
            probe_runner_enforcement_contract_declared=bool(
                data.get("probe_runner_enforcement_contract_declared", False)
            ),
            probe_runner_enforcement_bound=bool(data.get("probe_runner_enforcement_bound", False)),
            probe_runner_bound=bool(data.get("probe_runner_bound", False)),
            runtime_probe_bound=bool(data.get("runtime_probe_bound", False)),
            probe_runner_identity_bound=bool(data.get("probe_runner_identity_bound", False)),
            probe_runner_policy_bound=bool(data.get("probe_runner_policy_bound", False)),
            probe_runner_sandbox_bound=bool(data.get("probe_runner_sandbox_bound", False)),
            probe_runner_network_blocked=bool(data.get("probe_runner_network_blocked", False)),
            probe_runner_workspace_isolated=bool(data.get("probe_runner_workspace_isolated", False)),
            probe_runner_timeout_bound=bool(data.get("probe_runner_timeout_bound", False)),
            probe_runner_output_capture_bound=bool(data.get("probe_runner_output_capture_bound", False)),
            probe_runner_kill_switch_bound=bool(data.get("probe_runner_kill_switch_bound", False)),
            probe_runner_receipt_contract_bound=bool(data.get("probe_runner_receipt_contract_bound", False)),
            provider_runtime_probe_performed=bool(data.get("provider_runtime_probe_performed", False)),
            service_query_performed=bool(data.get("service_query_performed", False)),
            process_launched=bool(data.get("process_launched", False)),
            container_launched=bool(data.get("container_launched", False)),
            sandbox_provider_bound=bool(data.get("sandbox_provider_bound", False)),
            sandbox_bound=bool(data.get("sandbox_bound", False)),
            sandbox_enforced=bool(data.get("sandbox_enforced", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabExecutionReceiptWriteReadiness:
    id: str
    approval_id: str
    sandbox_readiness_id: str
    command_allowlist_enforcement_id: str
    receipt_sink_reservation_id: str
    approval_handoff_id: str
    runner_enforcement_id: str
    runner_binding_id: str
    runner_readiness_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    reserved_execution_receipt: dict[str, Any] = field(default_factory=dict)
    receipt_write_contract: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    receipt_schema_bound: bool = False
    prewrite_bound: bool = False
    final_write_bound: bool = False
    execution_receipt_prewritten: bool = False
    execution_receipt_finalized: bool = False
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabExecutionReceiptWriteReadiness | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        sandbox_readiness_id = _safe_str(data.get("sandbox_readiness_id")).strip()
        reservation_id = _safe_str(data.get("receipt_sink_reservation_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not sandbox_readiness_id
            or not reservation_id
            or not preflight_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_EXECUTION_RECEIPT_WRITE_READINESS_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            sandbox_readiness_id=sandbox_readiness_id,
            command_allowlist_enforcement_id=_safe_str(data.get("command_allowlist_enforcement_id")).strip(),
            receipt_sink_reservation_id=reservation_id,
            approval_handoff_id=_safe_str(data.get("approval_handoff_id")).strip(),
            runner_enforcement_id=_safe_str(data.get("runner_enforcement_id")).strip(),
            runner_binding_id=_safe_str(data.get("runner_binding_id")).strip(),
            runner_readiness_id=_safe_str(data.get("runner_readiness_id")).strip(),
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=_safe_str(data.get("workspace_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            reserved_execution_receipt=_safe_dict(data.get("reserved_execution_receipt")),
            receipt_write_contract=_safe_dict(data.get("receipt_write_contract")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            receipt_schema_bound=bool(data.get("receipt_schema_bound", False)),
            prewrite_bound=bool(data.get("prewrite_bound", False)),
            final_write_bound=bool(data.get("final_write_bound", False)),
            execution_receipt_prewritten=bool(data.get("execution_receipt_prewritten", False)),
            execution_receipt_finalized=bool(data.get("execution_receipt_finalized", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabExecutionReceiptPrewriteBinding:
    id: str
    approval_id: str
    receipt_write_readiness_id: str
    sandbox_readiness_id: str
    command_allowlist_enforcement_id: str
    receipt_sink_reservation_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    reserved_execution_receipt: dict[str, Any] = field(default_factory=dict)
    execution_receipt_schema: dict[str, Any] = field(default_factory=dict)
    prewrite_contract: dict[str, Any] = field(default_factory=dict)
    final_write_contract: dict[str, Any] = field(default_factory=dict)
    contract_binding: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    upstream_blockers: list[str] = field(default_factory=list)
    receipt_schema_bound: bool = True
    prewrite_contract_bound: bool = True
    final_write_contract_bound: bool = True
    prewrite_writer_bound: bool = False
    final_write_writer_bound: bool = False
    execution_receipt_prewritten: bool = False
    execution_receipt_finalized: bool = False
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabExecutionReceiptPrewriteBinding | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        write_readiness_id = _safe_str(data.get("receipt_write_readiness_id")).strip()
        reservation_id = _safe_str(data.get("receipt_sink_reservation_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not write_readiness_id
            or not reservation_id
            or not preflight_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_EXECUTION_RECEIPT_PREWRITE_BINDING_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            receipt_write_readiness_id=write_readiness_id,
            sandbox_readiness_id=_safe_str(data.get("sandbox_readiness_id")).strip(),
            command_allowlist_enforcement_id=_safe_str(data.get("command_allowlist_enforcement_id")).strip(),
            receipt_sink_reservation_id=reservation_id,
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=_safe_str(data.get("workspace_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            reserved_execution_receipt=_safe_dict(data.get("reserved_execution_receipt")),
            execution_receipt_schema=_safe_dict(data.get("execution_receipt_schema")),
            prewrite_contract=_safe_dict(data.get("prewrite_contract")),
            final_write_contract=_safe_dict(data.get("final_write_contract")),
            contract_binding=_safe_dict(data.get("contract_binding")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            upstream_blockers=[
                _safe_str(item).strip() for item in _safe_list(data.get("upstream_blockers")) if _safe_str(item).strip()
            ],
            receipt_schema_bound=bool(data.get("receipt_schema_bound", True)),
            prewrite_contract_bound=bool(data.get("prewrite_contract_bound", True)),
            final_write_contract_bound=bool(data.get("final_write_contract_bound", True)),
            prewrite_writer_bound=bool(data.get("prewrite_writer_bound", False)),
            final_write_writer_bound=bool(data.get("final_write_writer_bound", False)),
            execution_receipt_prewritten=bool(data.get("execution_receipt_prewritten", False)),
            execution_receipt_finalized=bool(data.get("execution_receipt_finalized", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabExecutionReceiptWriterPreflight:
    id: str
    approval_id: str
    receipt_prewrite_binding_id: str
    receipt_write_readiness_id: str
    sandbox_readiness_id: str
    command_allowlist_enforcement_id: str
    receipt_sink_reservation_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    reserved_execution_receipt: dict[str, Any] = field(default_factory=dict)
    writer_contract: dict[str, Any] = field(default_factory=dict)
    prewrite_operation: dict[str, Any] = field(default_factory=dict)
    final_write_operation: dict[str, Any] = field(default_factory=dict)
    writer_boundary: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    upstream_blockers: list[str] = field(default_factory=list)
    writer_interface_declared: bool = True
    writer_implementation_bound: bool = False
    writer_path_within_sink: bool = False
    atomic_write_plan_declared: bool = True
    redaction_policy_bound: bool = True
    prewrite_writer_bound: bool = False
    final_write_writer_bound: bool = False
    execution_receipt_prewritten: bool = False
    execution_receipt_finalized: bool = False
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabExecutionReceiptWriterPreflight | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        prewrite_binding_id = _safe_str(data.get("receipt_prewrite_binding_id")).strip()
        write_readiness_id = _safe_str(data.get("receipt_write_readiness_id")).strip()
        reservation_id = _safe_str(data.get("receipt_sink_reservation_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not prewrite_binding_id
            or not write_readiness_id
            or not reservation_id
            or not preflight_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_EXECUTION_RECEIPT_WRITER_PREFLIGHT_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            receipt_prewrite_binding_id=prewrite_binding_id,
            receipt_write_readiness_id=write_readiness_id,
            sandbox_readiness_id=_safe_str(data.get("sandbox_readiness_id")).strip(),
            command_allowlist_enforcement_id=_safe_str(data.get("command_allowlist_enforcement_id")).strip(),
            receipt_sink_reservation_id=reservation_id,
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=_safe_str(data.get("workspace_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            reserved_execution_receipt=_safe_dict(data.get("reserved_execution_receipt")),
            writer_contract=_safe_dict(data.get("writer_contract")),
            prewrite_operation=_safe_dict(data.get("prewrite_operation")),
            final_write_operation=_safe_dict(data.get("final_write_operation")),
            writer_boundary=_safe_dict(data.get("writer_boundary")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            upstream_blockers=[
                _safe_str(item).strip() for item in _safe_list(data.get("upstream_blockers")) if _safe_str(item).strip()
            ],
            writer_interface_declared=bool(data.get("writer_interface_declared", True)),
            writer_implementation_bound=bool(data.get("writer_implementation_bound", False)),
            writer_path_within_sink=bool(data.get("writer_path_within_sink", False)),
            atomic_write_plan_declared=bool(data.get("atomic_write_plan_declared", True)),
            redaction_policy_bound=bool(data.get("redaction_policy_bound", True)),
            prewrite_writer_bound=bool(data.get("prewrite_writer_bound", False)),
            final_write_writer_bound=bool(data.get("final_write_writer_bound", False)),
            execution_receipt_prewritten=bool(data.get("execution_receipt_prewritten", False)),
            execution_receipt_finalized=bool(data.get("execution_receipt_finalized", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabRunBoundaryPreflight:
    id: str
    approval_id: str
    source_mount_contract_id: str
    source_mount_readiness_id: str
    execution_receipt_writer_preflight_id: str
    receipt_prewrite_binding_id: str
    receipt_write_readiness_id: str
    sandbox_readiness_id: str
    sandbox_provider_contract_id: str
    sandbox_provider_binding_id: str
    sandbox_provider_selection_id: str
    sandbox_provider_verifier_id: str
    sandbox_provider_runtime_probe_id: str
    sandbox_provider_runtime_probe_harness_id: str
    sandbox_provider_runtime_probe_runner_enforcement_id: str
    command_allowlist_enforcement_id: str
    approval_handoff_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    boundary_kind: str = "francis.lab.run_boundary_preflight"
    boundary_mode: str = "preflight_only_no_execution"
    run_mode: str = "future_sandboxed_rebuild_run_test"
    run_boundary_contract: dict[str, Any] = field(default_factory=dict)
    source_mount_contract: dict[str, Any] = field(default_factory=dict)
    execution_receipt_writer_preflight: dict[str, Any] = field(default_factory=dict)
    runner_sandbox_readiness: dict[str, Any] = field(default_factory=dict)
    sandbox_provider_contract: dict[str, Any] = field(default_factory=dict)
    sandbox_provider_binding: dict[str, Any] = field(default_factory=dict)
    sandbox_provider_selection: dict[str, Any] = field(default_factory=dict)
    sandbox_provider_verifier: dict[str, Any] = field(default_factory=dict)
    sandbox_provider_runtime_probe: dict[str, Any] = field(default_factory=dict)
    sandbox_provider_runtime_probe_harness: dict[str, Any] = field(default_factory=dict)
    sandbox_provider_runtime_probe_runner_enforcement: dict[str, Any] = field(default_factory=dict)
    runner_command_allowlist_enforcement: dict[str, Any] = field(default_factory=dict)
    approval_consumption_handoff: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    source_mount_contract_declared: bool = False
    read_only_mount_bound: bool = False
    mount_enforced: bool = False
    source_copied: bool = False
    source_write_allowed: bool = False
    sandbox_provider_contract_declared: bool = False
    sandbox_provider_binding_ready: bool = False
    sandbox_provider_selection_ready: bool = False
    sandbox_provider_verifier_ready: bool = False
    sandbox_provider_runtime_probe_ready: bool = False
    sandbox_provider_runtime_probe_harness_ready: bool = False
    sandbox_provider_runtime_probe_runner_enforcement_ready: bool = False
    runtime_probe_harness_contract_declared: bool = False
    runtime_probe_runner_enforcement_contract_declared: bool = False
    runtime_probe_runner_enforcement_bound: bool = False
    runtime_probe_runner_bound: bool = False
    runtime_probe_sandbox_bound: bool = False
    runtime_probe_service_query_guard_bound: bool = False
    runtime_probe_output_capture_bound: bool = False
    runtime_probe_kill_switch_bound: bool = False
    provider_runtime_probe_performed: bool = False
    sandbox_provider_bound: bool = False
    sandbox_bound: bool = False
    sandbox_enforced: bool = False
    runner_bound: bool = False
    runner_identity_verified: bool = False
    command_allowlist_enforced: bool = False
    writer_implementation_bound: bool = False
    receipt_prewrite_bound: bool = False
    receipt_final_write_bound: bool = False
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    commands_executed: bool = False
    repo_code_executed: bool = False
    ran_repo_scripts: bool = False
    ran_install: bool = False
    ran_build: bool = False
    ran_tests: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    candidate_validated: bool = False
    capability_promoted: bool = False
    store_file_contents: bool = False
    store_sensitive_values: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabRunBoundaryPreflight | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        workspace_id = _safe_str(data.get("workspace_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        source_mount_contract_id = _safe_str(data.get("source_mount_contract_id")).strip()
        writer_preflight_id = _safe_str(data.get("execution_receipt_writer_preflight_id")).strip()
        if (
            not record_id
            or not source_id
            or not candidate_id
            or not workspace_id
            or not preflight_id
            or not source_mount_contract_id
            or not writer_preflight_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_RUN_BOUNDARY_PREFLIGHT_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            source_mount_contract_id=source_mount_contract_id,
            source_mount_readiness_id=_safe_str(data.get("source_mount_readiness_id")).strip(),
            execution_receipt_writer_preflight_id=writer_preflight_id,
            receipt_prewrite_binding_id=_safe_str(data.get("receipt_prewrite_binding_id")).strip(),
            receipt_write_readiness_id=_safe_str(data.get("receipt_write_readiness_id")).strip(),
            sandbox_readiness_id=_safe_str(data.get("sandbox_readiness_id")).strip(),
            sandbox_provider_contract_id=_safe_str(data.get("sandbox_provider_contract_id")).strip(),
            sandbox_provider_binding_id=_safe_str(data.get("sandbox_provider_binding_id")).strip(),
            sandbox_provider_selection_id=_safe_str(data.get("sandbox_provider_selection_id")).strip(),
            sandbox_provider_verifier_id=_safe_str(data.get("sandbox_provider_verifier_id")).strip(),
            sandbox_provider_runtime_probe_id=_safe_str(data.get("sandbox_provider_runtime_probe_id")).strip(),
            sandbox_provider_runtime_probe_harness_id=_safe_str(
                data.get("sandbox_provider_runtime_probe_harness_id")
            ).strip(),
            sandbox_provider_runtime_probe_runner_enforcement_id=_safe_str(
                data.get("sandbox_provider_runtime_probe_runner_enforcement_id")
            ).strip(),
            command_allowlist_enforcement_id=_safe_str(data.get("command_allowlist_enforcement_id")).strip(),
            approval_handoff_id=_safe_str(data.get("approval_handoff_id")).strip(),
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=workspace_id,
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            boundary_kind=_safe_str(data.get("boundary_kind")).strip() or "francis.lab.run_boundary_preflight",
            boundary_mode=_safe_str(data.get("boundary_mode")).strip() or "preflight_only_no_execution",
            run_mode=_safe_str(data.get("run_mode")).strip() or "future_sandboxed_rebuild_run_test",
            run_boundary_contract=_safe_dict(data.get("run_boundary_contract")),
            source_mount_contract=_safe_dict(data.get("source_mount_contract")),
            execution_receipt_writer_preflight=_safe_dict(data.get("execution_receipt_writer_preflight")),
            runner_sandbox_readiness=_safe_dict(data.get("runner_sandbox_readiness")),
            sandbox_provider_contract=_safe_dict(data.get("sandbox_provider_contract")),
            sandbox_provider_binding=_safe_dict(data.get("sandbox_provider_binding")),
            sandbox_provider_selection=_safe_dict(data.get("sandbox_provider_selection")),
            sandbox_provider_verifier=_safe_dict(data.get("sandbox_provider_verifier")),
            sandbox_provider_runtime_probe=_safe_dict(data.get("sandbox_provider_runtime_probe")),
            sandbox_provider_runtime_probe_harness=_safe_dict(data.get("sandbox_provider_runtime_probe_harness")),
            sandbox_provider_runtime_probe_runner_enforcement=_safe_dict(
                data.get("sandbox_provider_runtime_probe_runner_enforcement")
            ),
            runner_command_allowlist_enforcement=_safe_dict(data.get("runner_command_allowlist_enforcement")),
            approval_consumption_handoff=_safe_dict(data.get("approval_consumption_handoff")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            source_mount_contract_declared=bool(data.get("source_mount_contract_declared", False)),
            read_only_mount_bound=bool(data.get("read_only_mount_bound", False)),
            mount_enforced=bool(data.get("mount_enforced", False)),
            source_copied=bool(data.get("source_copied", False)),
            source_write_allowed=bool(data.get("source_write_allowed", False)),
            sandbox_provider_contract_declared=bool(data.get("sandbox_provider_contract_declared", False)),
            sandbox_provider_binding_ready=bool(data.get("sandbox_provider_binding_ready", False)),
            sandbox_provider_selection_ready=bool(data.get("sandbox_provider_selection_ready", False)),
            sandbox_provider_verifier_ready=bool(data.get("sandbox_provider_verifier_ready", False)),
            sandbox_provider_runtime_probe_ready=bool(data.get("sandbox_provider_runtime_probe_ready", False)),
            sandbox_provider_runtime_probe_harness_ready=bool(
                data.get("sandbox_provider_runtime_probe_harness_ready", False)
            ),
            sandbox_provider_runtime_probe_runner_enforcement_ready=bool(
                data.get("sandbox_provider_runtime_probe_runner_enforcement_ready", False)
            ),
            runtime_probe_harness_contract_declared=bool(data.get("runtime_probe_harness_contract_declared", False)),
            runtime_probe_runner_enforcement_contract_declared=bool(
                data.get("runtime_probe_runner_enforcement_contract_declared", False)
            ),
            runtime_probe_runner_enforcement_bound=bool(data.get("runtime_probe_runner_enforcement_bound", False)),
            runtime_probe_runner_bound=bool(data.get("runtime_probe_runner_bound", False)),
            runtime_probe_sandbox_bound=bool(data.get("runtime_probe_sandbox_bound", False)),
            runtime_probe_service_query_guard_bound=bool(data.get("runtime_probe_service_query_guard_bound", False)),
            runtime_probe_output_capture_bound=bool(data.get("runtime_probe_output_capture_bound", False)),
            runtime_probe_kill_switch_bound=bool(data.get("runtime_probe_kill_switch_bound", False)),
            provider_runtime_probe_performed=bool(data.get("provider_runtime_probe_performed", False)),
            sandbox_provider_bound=bool(data.get("sandbox_provider_bound", False)),
            sandbox_bound=bool(data.get("sandbox_bound", False)),
            sandbox_enforced=bool(data.get("sandbox_enforced", False)),
            runner_bound=bool(data.get("runner_bound", False)),
            runner_identity_verified=bool(data.get("runner_identity_verified", False)),
            command_allowlist_enforced=bool(data.get("command_allowlist_enforced", False)),
            writer_implementation_bound=bool(data.get("writer_implementation_bound", False)),
            receipt_prewrite_bound=bool(data.get("receipt_prewrite_bound", False)),
            receipt_final_write_bound=bool(data.get("receipt_final_write_bound", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            commands_executed=bool(data.get("commands_executed", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            ran_repo_scripts=bool(data.get("ran_repo_scripts", False)),
            ran_install=bool(data.get("ran_install", False)),
            ran_build=bool(data.get("ran_build", False)),
            ran_tests=bool(data.get("ran_tests", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            candidate_validated=bool(data.get("candidate_validated", False)),
            capability_promoted=bool(data.get("capability_promoted", False)),
            store_file_contents=bool(data.get("store_file_contents", False)),
            store_sensitive_values=bool(data.get("store_sensitive_values", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSandboxProviderRuntimeProbeExecutionBoundary:
    id: str
    approval_id: str
    run_boundary_preflight_id: str
    source_mount_contract_id: str
    execution_receipt_writer_preflight_id: str
    sandbox_provider_runtime_probe_runner_enforcement_id: str
    sandbox_provider_runtime_probe_harness_id: str
    sandbox_provider_runtime_probe_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    boundary_kind: str = "francis.lab.sandbox_provider_runtime_probe_execution_boundary"
    boundary_mode: str = "execution_boundary_preflight_only_no_provider_execution"
    probe_mode: str = "future_sandbox_provider_runtime_probe"
    execution_boundary_contract: dict[str, Any] = field(default_factory=dict)
    run_boundary_preflight: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    run_boundary_present: bool = False
    run_boundary_ready: bool = False
    runtime_probe_runner_enforcement_present: bool = False
    runtime_probe_runner_enforcement_ready: bool = False
    runtime_probe_runner_enforcement_bound: bool = False
    runtime_probe_runner_bound: bool = False
    runtime_probe_bound: bool = False
    provider_runtime_probe_performed: bool = False
    provider_probe_execution_boundary_declared: bool = False
    provider_probe_execution_boundary_bound: bool = False
    execution_receipt_writer_bound: bool = False
    receipt_prewrite_bound: bool = False
    receipt_final_write_bound: bool = False
    sandbox_bound: bool = False
    sandbox_enforced: bool = False
    network_blocked_or_policy_bound: bool = False
    workspace_isolated: bool = False
    timeout_policy_bound: bool = False
    kill_switch_bound: bool = False
    output_capture_bound: bool = False
    approval_not_consumed: bool = False
    execution_authority_absent: bool = False
    provider_binary_not_executed: bool = False
    service_query_not_performed: bool = False
    process_not_launched: bool = False
    container_not_launched: bool = False
    repo_code_not_executed: bool = False
    network_not_accessed: bool = False
    repo_write_not_performed: bool = False
    execution_receipt_not_written: bool = False
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    service_query_performed: bool = False
    process_launched: bool = False
    container_launched: bool = False
    repo_code_executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    execution_receipt_written: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSandboxProviderRuntimeProbeExecutionBoundary | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        run_boundary_id = _safe_str(data.get("run_boundary_preflight_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        workspace_id = _safe_str(data.get("workspace_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not run_boundary_id
            or not preflight_id
            or not workspace_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_EXECUTION_BOUNDARY_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            run_boundary_preflight_id=run_boundary_id,
            source_mount_contract_id=_safe_str(data.get("source_mount_contract_id")).strip(),
            execution_receipt_writer_preflight_id=_safe_str(data.get("execution_receipt_writer_preflight_id")).strip(),
            sandbox_provider_runtime_probe_runner_enforcement_id=_safe_str(
                data.get("sandbox_provider_runtime_probe_runner_enforcement_id")
            ).strip(),
            sandbox_provider_runtime_probe_harness_id=_safe_str(
                data.get("sandbox_provider_runtime_probe_harness_id")
            ).strip(),
            sandbox_provider_runtime_probe_id=_safe_str(data.get("sandbox_provider_runtime_probe_id")).strip(),
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=workspace_id,
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            boundary_kind=_safe_str(data.get("boundary_kind")).strip()
            or "francis.lab.sandbox_provider_runtime_probe_execution_boundary",
            boundary_mode=_safe_str(data.get("boundary_mode")).strip()
            or "execution_boundary_preflight_only_no_provider_execution",
            probe_mode=_safe_str(data.get("probe_mode")).strip() or "future_sandbox_provider_runtime_probe",
            execution_boundary_contract=_safe_dict(data.get("execution_boundary_contract")),
            run_boundary_preflight=_safe_dict(data.get("run_boundary_preflight")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            run_boundary_present=bool(data.get("run_boundary_present", False)),
            run_boundary_ready=bool(data.get("run_boundary_ready", False)),
            runtime_probe_runner_enforcement_present=bool(data.get("runtime_probe_runner_enforcement_present", False)),
            runtime_probe_runner_enforcement_ready=bool(data.get("runtime_probe_runner_enforcement_ready", False)),
            runtime_probe_runner_enforcement_bound=bool(data.get("runtime_probe_runner_enforcement_bound", False)),
            runtime_probe_runner_bound=bool(data.get("runtime_probe_runner_bound", False)),
            runtime_probe_bound=bool(data.get("runtime_probe_bound", False)),
            provider_runtime_probe_performed=bool(data.get("provider_runtime_probe_performed", False)),
            provider_probe_execution_boundary_declared=bool(
                data.get("provider_probe_execution_boundary_declared", False)
            ),
            provider_probe_execution_boundary_bound=bool(data.get("provider_probe_execution_boundary_bound", False)),
            execution_receipt_writer_bound=bool(data.get("execution_receipt_writer_bound", False)),
            receipt_prewrite_bound=bool(data.get("receipt_prewrite_bound", False)),
            receipt_final_write_bound=bool(data.get("receipt_final_write_bound", False)),
            sandbox_bound=bool(data.get("sandbox_bound", False)),
            sandbox_enforced=bool(data.get("sandbox_enforced", False)),
            network_blocked_or_policy_bound=bool(data.get("network_blocked_or_policy_bound", False)),
            workspace_isolated=bool(data.get("workspace_isolated", False)),
            timeout_policy_bound=bool(data.get("timeout_policy_bound", False)),
            kill_switch_bound=bool(data.get("kill_switch_bound", False)),
            output_capture_bound=bool(data.get("output_capture_bound", False)),
            approval_not_consumed=bool(data.get("approval_not_consumed", False)),
            execution_authority_absent=bool(data.get("execution_authority_absent", False)),
            provider_binary_not_executed=bool(data.get("provider_binary_not_executed", False)),
            service_query_not_performed=bool(data.get("service_query_not_performed", False)),
            process_not_launched=bool(data.get("process_not_launched", False)),
            container_not_launched=bool(data.get("container_not_launched", False)),
            repo_code_not_executed=bool(data.get("repo_code_not_executed", False)),
            network_not_accessed=bool(data.get("network_not_accessed", False)),
            repo_write_not_performed=bool(data.get("repo_write_not_performed", False)),
            execution_receipt_not_written=bool(data.get("execution_receipt_not_written", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            service_query_performed=bool(data.get("service_query_performed", False)),
            process_launched=bool(data.get("process_launched", False)),
            container_launched=bool(data.get("container_launched", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            execution_receipt_written=bool(data.get("execution_receipt_written", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSandboxProviderRuntimeProbeRefusal:
    id: str
    approval_id: str
    execution_boundary_id: str
    run_boundary_preflight_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    timestamp: str
    actor: str
    status: str = "blocked"
    reason: str = "sandbox_provider_runtime_probe_not_available"
    refusal_kind: str = "francis.lab.sandbox_provider_runtime_probe_refusal"
    refusal_mode: str = "refusal_only_no_provider_execution"
    blockers: list[str] = field(default_factory=list)
    permission_scope: str = "ingest.lab.sandbox.provider_runtime_probe.refuse"
    execution_boundary: dict[str, Any] = field(default_factory=dict)
    execution_authority: bool = False
    executed: bool = False
    provider_runtime_probe_performed: bool = False
    provider_binary_executed: bool = False
    service_query_performed: bool = False
    process_launched: bool = False
    container_launched: bool = False
    repo_code_executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    execution_receipt_written: bool = False
    approval_consumed: bool = False
    receipt_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSandboxProviderRuntimeProbeRefusal | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        boundary_id = _safe_str(data.get("execution_boundary_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if not record_id or not boundary_id or not source_id or not candidate_id:
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_REFUSAL_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            execution_boundary_id=boundary_id,
            run_boundary_preflight_id=_safe_str(data.get("run_boundary_preflight_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            timestamp=_safe_str(data.get("timestamp")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            status=status,
            reason=_safe_str(data.get("reason")).strip() or "sandbox_provider_runtime_probe_not_available",
            refusal_kind=_safe_str(data.get("refusal_kind")).strip()
            or "francis.lab.sandbox_provider_runtime_probe_refusal",
            refusal_mode=_safe_str(data.get("refusal_mode")).strip() or "refusal_only_no_provider_execution",
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            permission_scope=_safe_str(data.get("permission_scope")).strip()
            or "ingest.lab.sandbox.provider_runtime_probe.refuse",
            execution_boundary=_safe_dict(data.get("execution_boundary")),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            provider_runtime_probe_performed=bool(data.get("provider_runtime_probe_performed", False)),
            provider_binary_executed=bool(data.get("provider_binary_executed", False)),
            service_query_performed=bool(data.get("service_query_performed", False)),
            process_launched=bool(data.get("process_launched", False)),
            container_launched=bool(data.get("container_launched", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            execution_receipt_written=bool(data.get("execution_receipt_written", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            receipt_path=_safe_str(data.get("receipt_path")).strip(),
        )


@dataclass(frozen=True)
class LabSandboxProviderRuntimeProbeApprovalRequest:
    id: str
    approval_id: str
    upstream_approval_id: str
    execution_boundary_id: str
    run_boundary_preflight_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.sandbox_provider_runtime_probe"
    action_hash: str = ""
    approval_path: str = ""
    approval_payload: dict[str, Any] = field(default_factory=dict)
    execution_boundary: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    permission_scope: str = "ingest.lab.sandbox.provider_runtime_probe.request_approval"
    approval_created: bool = False
    approval_consumed: bool = False
    upstream_approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    provider_runtime_probe_performed: bool = False
    provider_binary_executed: bool = False
    service_query_performed: bool = False
    process_launched: bool = False
    container_launched: bool = False
    repo_code_executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    execution_receipt_written: bool = False
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSandboxProviderRuntimeProbeApprovalRequest | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        approval_id = _safe_str(data.get("approval_id")).strip()
        boundary_id = _safe_str(data.get("execution_boundary_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if not record_id or not approval_id or not boundary_id or not source_id or not candidate_id:
            return None
        status = _safe_str(data.get("status")).strip() or "failed"
        if status not in LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_APPROVAL_REQUEST_STATUSES:
            status = "failed"
        return cls(
            id=record_id,
            approval_id=approval_id,
            upstream_approval_id=_safe_str(data.get("upstream_approval_id")).strip(),
            execution_boundary_id=boundary_id,
            run_boundary_preflight_id=_safe_str(data.get("run_boundary_preflight_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.sandbox_provider_runtime_probe",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            approval_path=_safe_str(data.get("approval_path")).strip(),
            approval_payload=_safe_dict(data.get("approval_payload")),
            execution_boundary=_safe_dict(data.get("execution_boundary")),
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            permission_scope=_safe_str(data.get("permission_scope")).strip()
            or "ingest.lab.sandbox.provider_runtime_probe.request_approval",
            approval_created=bool(data.get("approval_created", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            upstream_approval_consumed=bool(data.get("upstream_approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            provider_runtime_probe_performed=bool(data.get("provider_runtime_probe_performed", False)),
            provider_binary_executed=bool(data.get("provider_binary_executed", False)),
            service_query_performed=bool(data.get("service_query_performed", False)),
            process_launched=bool(data.get("process_launched", False)),
            container_launched=bool(data.get("container_launched", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            execution_receipt_written=bool(data.get("execution_receipt_written", False)),
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSandboxProviderRuntimeProbeApprovalConsumption:
    id: str
    approval_id: str
    approval_request_id: str
    upstream_approval_id: str
    execution_boundary_id: str
    run_boundary_preflight_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    consumed_at: str
    actor: str
    action: str = "francis.lab.sandbox_provider_runtime_probe"
    action_hash: str = ""
    approval_status: str = ""
    approval_path: str = ""
    approval_snapshot: dict[str, Any] = field(default_factory=dict)
    approval_binding: dict[str, Any] = field(default_factory=dict)
    approval_request: dict[str, Any] = field(default_factory=dict)
    permission_scope: str = "ingest.lab.sandbox.provider_runtime_probe.consume_approval"
    consumption_kind: str = "sandbox_provider_runtime_probe_approval"
    approval_consumed: bool = True
    single_use_enforced: bool = True
    upstream_approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    provider_runtime_probe_performed: bool = False
    provider_binary_executed: bool = False
    service_query_performed: bool = False
    process_launched: bool = False
    container_launched: bool = False
    repo_code_executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    execution_receipt_written: bool = False
    store_file_contents: bool = False
    store_sensitive_values: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSandboxProviderRuntimeProbeApprovalConsumption | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        approval_id = _safe_str(data.get("approval_id")).strip()
        request_id = _safe_str(data.get("approval_request_id")).strip()
        boundary_id = _safe_str(data.get("execution_boundary_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if not record_id or not approval_id or not request_id or not boundary_id or not source_id or not candidate_id:
            return None
        status = _safe_str(data.get("status")).strip() or "failed"
        if status not in LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_APPROVAL_CONSUMPTION_STATUSES:
            status = "failed"
        return cls(
            id=record_id,
            approval_id=approval_id,
            approval_request_id=request_id,
            upstream_approval_id=_safe_str(data.get("upstream_approval_id")).strip(),
            execution_boundary_id=boundary_id,
            run_boundary_preflight_id=_safe_str(data.get("run_boundary_preflight_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            consumed_at=_safe_str(data.get("consumed_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.sandbox_provider_runtime_probe",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            approval_status=_safe_str(data.get("approval_status")).strip(),
            approval_path=_safe_str(data.get("approval_path")).strip(),
            approval_snapshot=_safe_dict(data.get("approval_snapshot")),
            approval_binding=_safe_dict(data.get("approval_binding")),
            approval_request=_safe_dict(data.get("approval_request")),
            permission_scope=_safe_str(data.get("permission_scope")).strip()
            or "ingest.lab.sandbox.provider_runtime_probe.consume_approval",
            consumption_kind=_safe_str(data.get("consumption_kind")).strip()
            or "sandbox_provider_runtime_probe_approval",
            approval_consumed=bool(data.get("approval_consumed", True)),
            single_use_enforced=bool(data.get("single_use_enforced", True)),
            upstream_approval_consumed=bool(data.get("upstream_approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            provider_runtime_probe_performed=bool(data.get("provider_runtime_probe_performed", False)),
            provider_binary_executed=bool(data.get("provider_binary_executed", False)),
            service_query_performed=bool(data.get("service_query_performed", False)),
            process_launched=bool(data.get("process_launched", False)),
            container_launched=bool(data.get("container_launched", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            execution_receipt_written=bool(data.get("execution_receipt_written", False)),
            store_file_contents=bool(data.get("store_file_contents", False)),
            store_sensitive_values=bool(data.get("store_sensitive_values", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSandboxProviderRuntimeProbeInvocationBoundary:
    id: str
    approval_id: str
    approval_consumption_id: str
    approval_request_id: str
    execution_boundary_id: str
    run_boundary_preflight_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.sandbox_provider_runtime_probe"
    action_hash: str = ""
    boundary_kind: str = "francis.lab.sandbox_provider_runtime_probe_invocation_boundary"
    boundary_mode: str = "invocation_boundary_preflight_only_no_provider_execution"
    invocation_mode: str = "future_sandbox_provider_runtime_probe_invocation"
    permission_scope: str = "ingest.lab.sandbox.provider_runtime_probe.invocation_boundary"
    approval_consumption: dict[str, Any] = field(default_factory=dict)
    execution_boundary: dict[str, Any] = field(default_factory=dict)
    invocation_contract: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    approval_consumed: bool = False
    single_use_consumption_found: bool = False
    single_use_enforced: bool = False
    exact_action_binding_verified: bool = False
    upstream_approval_consumed: bool = False
    execution_boundary_present: bool = False
    execution_boundary_recorded: bool = False
    execution_boundary_ready: bool = False
    provider_probe_execution_boundary_bound: bool = False
    probe_runner_bound: bool = False
    probe_runner_policy_bound: bool = False
    probe_runner_sandbox_bound: bool = False
    probe_runner_network_blocked: bool = False
    probe_runner_workspace_isolated: bool = False
    probe_runner_timeout_bound: bool = False
    probe_runner_output_capture_bound: bool = False
    probe_runner_kill_switch_bound: bool = False
    probe_runner_receipt_writer_bound: bool = False
    execution_authority: bool = False
    executed: bool = False
    provider_runtime_probe_performed: bool = False
    provider_binary_executed: bool = False
    service_query_performed: bool = False
    process_launched: bool = False
    container_launched: bool = False
    repo_code_executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    execution_receipt_written: bool = False
    store_file_contents: bool = False
    store_sensitive_values: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSandboxProviderRuntimeProbeInvocationBoundary | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        approval_id = _safe_str(data.get("approval_id")).strip()
        consumption_id = _safe_str(data.get("approval_consumption_id")).strip()
        boundary_id = _safe_str(data.get("execution_boundary_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if (
            not record_id
            or not approval_id
            or not consumption_id
            or not boundary_id
            or not source_id
            or not candidate_id
        ):
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_INVOCATION_BOUNDARY_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=approval_id,
            approval_consumption_id=consumption_id,
            approval_request_id=_safe_str(data.get("approval_request_id")).strip(),
            execution_boundary_id=boundary_id,
            run_boundary_preflight_id=_safe_str(data.get("run_boundary_preflight_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.sandbox_provider_runtime_probe",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            boundary_kind=_safe_str(data.get("boundary_kind")).strip()
            or "francis.lab.sandbox_provider_runtime_probe_invocation_boundary",
            boundary_mode=_safe_str(data.get("boundary_mode")).strip()
            or "invocation_boundary_preflight_only_no_provider_execution",
            invocation_mode=_safe_str(data.get("invocation_mode")).strip()
            or "future_sandbox_provider_runtime_probe_invocation",
            permission_scope=_safe_str(data.get("permission_scope")).strip()
            or "ingest.lab.sandbox.provider_runtime_probe.invocation_boundary",
            approval_consumption=_safe_dict(data.get("approval_consumption")),
            execution_boundary=_safe_dict(data.get("execution_boundary")),
            invocation_contract=_safe_dict(data.get("invocation_contract")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            approval_consumed=bool(data.get("approval_consumed", False)),
            single_use_consumption_found=bool(data.get("single_use_consumption_found", False)),
            single_use_enforced=bool(data.get("single_use_enforced", False)),
            exact_action_binding_verified=bool(data.get("exact_action_binding_verified", False)),
            upstream_approval_consumed=bool(data.get("upstream_approval_consumed", False)),
            execution_boundary_present=bool(data.get("execution_boundary_present", False)),
            execution_boundary_recorded=bool(data.get("execution_boundary_recorded", False)),
            execution_boundary_ready=bool(data.get("execution_boundary_ready", False)),
            provider_probe_execution_boundary_bound=bool(data.get("provider_probe_execution_boundary_bound", False)),
            probe_runner_bound=bool(data.get("probe_runner_bound", False)),
            probe_runner_policy_bound=bool(data.get("probe_runner_policy_bound", False)),
            probe_runner_sandbox_bound=bool(data.get("probe_runner_sandbox_bound", False)),
            probe_runner_network_blocked=bool(data.get("probe_runner_network_blocked", False)),
            probe_runner_workspace_isolated=bool(data.get("probe_runner_workspace_isolated", False)),
            probe_runner_timeout_bound=bool(data.get("probe_runner_timeout_bound", False)),
            probe_runner_output_capture_bound=bool(data.get("probe_runner_output_capture_bound", False)),
            probe_runner_kill_switch_bound=bool(data.get("probe_runner_kill_switch_bound", False)),
            probe_runner_receipt_writer_bound=bool(data.get("probe_runner_receipt_writer_bound", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            provider_runtime_probe_performed=bool(data.get("provider_runtime_probe_performed", False)),
            provider_binary_executed=bool(data.get("provider_binary_executed", False)),
            service_query_performed=bool(data.get("service_query_performed", False)),
            process_launched=bool(data.get("process_launched", False)),
            container_launched=bool(data.get("container_launched", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            execution_receipt_written=bool(data.get("execution_receipt_written", False)),
            store_file_contents=bool(data.get("store_file_contents", False)),
            store_sensitive_values=bool(data.get("store_sensitive_values", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSandboxProviderRuntimeProbeRunnerPreExecutionBoundary:
    id: str
    approval_id: str
    approval_consumption_id: str
    invocation_boundary_id: str
    approval_request_id: str
    execution_boundary_id: str
    run_boundary_preflight_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.sandbox_provider_runtime_probe"
    action_hash: str = ""
    boundary_kind: str = "francis.lab.sandbox_provider_runtime_probe_runner_pre_execution_boundary"
    boundary_mode: str = "runner_pre_execution_boundary_no_provider_execution"
    pre_execution_mode: str = "future_sandbox_provider_runtime_probe_runner_pre_execution"
    permission_scope: str = "ingest.lab.sandbox.provider_runtime_probe.runner_pre_execution_boundary"
    approval_consumption: dict[str, Any] = field(default_factory=dict)
    invocation_boundary: dict[str, Any] = field(default_factory=dict)
    execution_boundary: dict[str, Any] = field(default_factory=dict)
    pre_execution_contract: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    invocation_boundary_found: bool = False
    invocation_boundary_recorded: bool = False
    invocation_boundary_ready: bool = False
    approval_consumed: bool = False
    single_use_consumption_found: bool = False
    single_use_enforced: bool = False
    exact_action_binding_verified: bool = False
    runner_identity_declared: bool = False
    runner_identity_bound: bool = False
    runner_policy_declared: bool = False
    runner_policy_bound: bool = False
    sandbox_policy_declared: bool = False
    sandbox_policy_bound: bool = False
    sandbox_bound: bool = False
    sandbox_enforced: bool = False
    network_block_declared: bool = False
    network_block_bound: bool = False
    timeout_policy_declared: bool = False
    timeout_policy_bound: bool = False
    output_capture_declared: bool = False
    output_capture_bound: bool = False
    kill_switch_declared: bool = False
    kill_switch_bound: bool = False
    execution_receipt_writer_declared: bool = False
    execution_receipt_writer_bound: bool = False
    execution_authority: bool = False
    executed: bool = False
    provider_runtime_probe_performed: bool = False
    provider_binary_executed: bool = False
    service_query_performed: bool = False
    process_launched: bool = False
    container_launched: bool = False
    repo_code_executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    execution_receipt_written: bool = False
    store_file_contents: bool = False
    store_sensitive_values: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSandboxProviderRuntimeProbeRunnerPreExecutionBoundary | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        approval_id = _safe_str(data.get("approval_id")).strip()
        invocation_boundary_id = _safe_str(data.get("invocation_boundary_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if not record_id or not approval_id or not invocation_boundary_id or not source_id or not candidate_id:
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_PRE_EXECUTION_BOUNDARY_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=approval_id,
            approval_consumption_id=_safe_str(data.get("approval_consumption_id")).strip(),
            invocation_boundary_id=invocation_boundary_id,
            approval_request_id=_safe_str(data.get("approval_request_id")).strip(),
            execution_boundary_id=_safe_str(data.get("execution_boundary_id")).strip(),
            run_boundary_preflight_id=_safe_str(data.get("run_boundary_preflight_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.sandbox_provider_runtime_probe",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            boundary_kind=_safe_str(data.get("boundary_kind")).strip()
            or "francis.lab.sandbox_provider_runtime_probe_runner_pre_execution_boundary",
            boundary_mode=_safe_str(data.get("boundary_mode")).strip()
            or "runner_pre_execution_boundary_no_provider_execution",
            pre_execution_mode=_safe_str(data.get("pre_execution_mode")).strip()
            or "future_sandbox_provider_runtime_probe_runner_pre_execution",
            permission_scope=_safe_str(data.get("permission_scope")).strip()
            or "ingest.lab.sandbox.provider_runtime_probe.runner_pre_execution_boundary",
            approval_consumption=_safe_dict(data.get("approval_consumption")),
            invocation_boundary=_safe_dict(data.get("invocation_boundary")),
            execution_boundary=_safe_dict(data.get("execution_boundary")),
            pre_execution_contract=_safe_dict(data.get("pre_execution_contract")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            invocation_boundary_found=bool(data.get("invocation_boundary_found", False)),
            invocation_boundary_recorded=bool(data.get("invocation_boundary_recorded", False)),
            invocation_boundary_ready=bool(data.get("invocation_boundary_ready", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            single_use_consumption_found=bool(data.get("single_use_consumption_found", False)),
            single_use_enforced=bool(data.get("single_use_enforced", False)),
            exact_action_binding_verified=bool(data.get("exact_action_binding_verified", False)),
            runner_identity_declared=bool(data.get("runner_identity_declared", False)),
            runner_identity_bound=bool(data.get("runner_identity_bound", False)),
            runner_policy_declared=bool(data.get("runner_policy_declared", False)),
            runner_policy_bound=bool(data.get("runner_policy_bound", False)),
            sandbox_policy_declared=bool(data.get("sandbox_policy_declared", False)),
            sandbox_policy_bound=bool(data.get("sandbox_policy_bound", False)),
            sandbox_bound=bool(data.get("sandbox_bound", False)),
            sandbox_enforced=bool(data.get("sandbox_enforced", False)),
            network_block_declared=bool(data.get("network_block_declared", False)),
            network_block_bound=bool(data.get("network_block_bound", False)),
            timeout_policy_declared=bool(data.get("timeout_policy_declared", False)),
            timeout_policy_bound=bool(data.get("timeout_policy_bound", False)),
            output_capture_declared=bool(data.get("output_capture_declared", False)),
            output_capture_bound=bool(data.get("output_capture_bound", False)),
            kill_switch_declared=bool(data.get("kill_switch_declared", False)),
            kill_switch_bound=bool(data.get("kill_switch_bound", False)),
            execution_receipt_writer_declared=bool(data.get("execution_receipt_writer_declared", False)),
            execution_receipt_writer_bound=bool(data.get("execution_receipt_writer_bound", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            provider_runtime_probe_performed=bool(data.get("provider_runtime_probe_performed", False)),
            provider_binary_executed=bool(data.get("provider_binary_executed", False)),
            service_query_performed=bool(data.get("service_query_performed", False)),
            process_launched=bool(data.get("process_launched", False)),
            container_launched=bool(data.get("container_launched", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            execution_receipt_written=bool(data.get("execution_receipt_written", False)),
            store_file_contents=bool(data.get("store_file_contents", False)),
            store_sensitive_values=bool(data.get("store_sensitive_values", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSandboxProviderRuntimeProbeRunnerControlBinding:
    id: str
    approval_id: str
    approval_consumption_id: str
    invocation_boundary_id: str
    pre_execution_boundary_id: str
    approval_request_id: str
    execution_boundary_id: str
    run_boundary_preflight_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.sandbox_provider_runtime_probe"
    action_hash: str = ""
    binding_kind: str = "francis.lab.sandbox_provider_runtime_probe_runner_control_binding"
    binding_mode: str = "control_binding_preflight_only_no_provider_execution"
    control_binding_mode: str = "future_sandbox_provider_runtime_probe_runner_control_binding"
    permission_scope: str = "ingest.lab.sandbox.provider_runtime_probe.runner_control_binding"
    approval_consumption: dict[str, Any] = field(default_factory=dict)
    invocation_boundary: dict[str, Any] = field(default_factory=dict)
    pre_execution_boundary: dict[str, Any] = field(default_factory=dict)
    execution_boundary: dict[str, Any] = field(default_factory=dict)
    control_binding_contract: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    pre_execution_boundary_found: bool = False
    pre_execution_boundary_recorded: bool = False
    pre_execution_boundary_ready: bool = False
    invocation_boundary_found: bool = False
    invocation_boundary_recorded: bool = False
    invocation_boundary_ready: bool = False
    approval_consumed: bool = False
    single_use_consumption_found: bool = False
    single_use_enforced: bool = False
    exact_action_binding_verified: bool = False
    control_binding_recorded: bool = False
    runner_identity_declared: bool = False
    runner_identity_binding_recorded: bool = False
    runner_identity_bound: bool = False
    runner_policy_declared: bool = False
    runner_policy_binding_recorded: bool = False
    runner_policy_bound: bool = False
    sandbox_policy_declared: bool = False
    sandbox_policy_binding_recorded: bool = False
    sandbox_policy_bound: bool = False
    sandbox_bound: bool = False
    sandbox_enforced: bool = False
    network_block_declared: bool = False
    network_block_binding_recorded: bool = False
    network_block_bound: bool = False
    timeout_policy_declared: bool = False
    timeout_policy_binding_recorded: bool = False
    timeout_policy_bound: bool = False
    output_capture_declared: bool = False
    output_capture_binding_recorded: bool = False
    output_capture_bound: bool = False
    kill_switch_declared: bool = False
    kill_switch_binding_recorded: bool = False
    kill_switch_bound: bool = False
    execution_receipt_writer_declared: bool = False
    execution_receipt_writer_binding_recorded: bool = False
    execution_receipt_writer_bound: bool = False
    execution_authority: bool = False
    executed: bool = False
    provider_runtime_probe_performed: bool = False
    provider_binary_executed: bool = False
    service_query_performed: bool = False
    process_launched: bool = False
    container_launched: bool = False
    repo_code_executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    execution_receipt_written: bool = False
    store_file_contents: bool = False
    store_sensitive_values: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSandboxProviderRuntimeProbeRunnerControlBinding | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        approval_id = _safe_str(data.get("approval_id")).strip()
        pre_execution_boundary_id = _safe_str(data.get("pre_execution_boundary_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if not record_id or not approval_id or not pre_execution_boundary_id or not source_id or not candidate_id:
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_CONTROL_BINDING_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=approval_id,
            approval_consumption_id=_safe_str(data.get("approval_consumption_id")).strip(),
            invocation_boundary_id=_safe_str(data.get("invocation_boundary_id")).strip(),
            pre_execution_boundary_id=pre_execution_boundary_id,
            approval_request_id=_safe_str(data.get("approval_request_id")).strip(),
            execution_boundary_id=_safe_str(data.get("execution_boundary_id")).strip(),
            run_boundary_preflight_id=_safe_str(data.get("run_boundary_preflight_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.sandbox_provider_runtime_probe",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            binding_kind=_safe_str(data.get("binding_kind")).strip()
            or "francis.lab.sandbox_provider_runtime_probe_runner_control_binding",
            binding_mode=_safe_str(data.get("binding_mode")).strip()
            or "control_binding_preflight_only_no_provider_execution",
            control_binding_mode=_safe_str(data.get("control_binding_mode")).strip()
            or "future_sandbox_provider_runtime_probe_runner_control_binding",
            permission_scope=_safe_str(data.get("permission_scope")).strip()
            or "ingest.lab.sandbox.provider_runtime_probe.runner_control_binding",
            approval_consumption=_safe_dict(data.get("approval_consumption")),
            invocation_boundary=_safe_dict(data.get("invocation_boundary")),
            pre_execution_boundary=_safe_dict(data.get("pre_execution_boundary")),
            execution_boundary=_safe_dict(data.get("execution_boundary")),
            control_binding_contract=_safe_dict(data.get("control_binding_contract")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            pre_execution_boundary_found=bool(data.get("pre_execution_boundary_found", False)),
            pre_execution_boundary_recorded=bool(data.get("pre_execution_boundary_recorded", False)),
            pre_execution_boundary_ready=bool(data.get("pre_execution_boundary_ready", False)),
            invocation_boundary_found=bool(data.get("invocation_boundary_found", False)),
            invocation_boundary_recorded=bool(data.get("invocation_boundary_recorded", False)),
            invocation_boundary_ready=bool(data.get("invocation_boundary_ready", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            single_use_consumption_found=bool(data.get("single_use_consumption_found", False)),
            single_use_enforced=bool(data.get("single_use_enforced", False)),
            exact_action_binding_verified=bool(data.get("exact_action_binding_verified", False)),
            control_binding_recorded=bool(data.get("control_binding_recorded", False)),
            runner_identity_declared=bool(data.get("runner_identity_declared", False)),
            runner_identity_binding_recorded=bool(data.get("runner_identity_binding_recorded", False)),
            runner_identity_bound=bool(data.get("runner_identity_bound", False)),
            runner_policy_declared=bool(data.get("runner_policy_declared", False)),
            runner_policy_binding_recorded=bool(data.get("runner_policy_binding_recorded", False)),
            runner_policy_bound=bool(data.get("runner_policy_bound", False)),
            sandbox_policy_declared=bool(data.get("sandbox_policy_declared", False)),
            sandbox_policy_binding_recorded=bool(data.get("sandbox_policy_binding_recorded", False)),
            sandbox_policy_bound=bool(data.get("sandbox_policy_bound", False)),
            sandbox_bound=bool(data.get("sandbox_bound", False)),
            sandbox_enforced=bool(data.get("sandbox_enforced", False)),
            network_block_declared=bool(data.get("network_block_declared", False)),
            network_block_binding_recorded=bool(data.get("network_block_binding_recorded", False)),
            network_block_bound=bool(data.get("network_block_bound", False)),
            timeout_policy_declared=bool(data.get("timeout_policy_declared", False)),
            timeout_policy_binding_recorded=bool(data.get("timeout_policy_binding_recorded", False)),
            timeout_policy_bound=bool(data.get("timeout_policy_bound", False)),
            output_capture_declared=bool(data.get("output_capture_declared", False)),
            output_capture_binding_recorded=bool(data.get("output_capture_binding_recorded", False)),
            output_capture_bound=bool(data.get("output_capture_bound", False)),
            kill_switch_declared=bool(data.get("kill_switch_declared", False)),
            kill_switch_binding_recorded=bool(data.get("kill_switch_binding_recorded", False)),
            kill_switch_bound=bool(data.get("kill_switch_bound", False)),
            execution_receipt_writer_declared=bool(data.get("execution_receipt_writer_declared", False)),
            execution_receipt_writer_binding_recorded=bool(
                data.get("execution_receipt_writer_binding_recorded", False)
            ),
            execution_receipt_writer_bound=bool(data.get("execution_receipt_writer_bound", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            provider_runtime_probe_performed=bool(data.get("provider_runtime_probe_performed", False)),
            provider_binary_executed=bool(data.get("provider_binary_executed", False)),
            service_query_performed=bool(data.get("service_query_performed", False)),
            process_launched=bool(data.get("process_launched", False)),
            container_launched=bool(data.get("container_launched", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            execution_receipt_written=bool(data.get("execution_receipt_written", False)),
            store_file_contents=bool(data.get("store_file_contents", False)),
            store_sensitive_values=bool(data.get("store_sensitive_values", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSandboxedRebuildRunTestBoundary:
    id: str
    approval_id: str
    approval_consumption_id: str
    invocation_boundary_id: str
    pre_execution_boundary_id: str
    control_binding_id: str
    approval_request_id: str
    execution_boundary_id: str
    run_boundary_preflight_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    boundary_kind: str = "francis.lab.sandboxed_rebuild_run_test_boundary"
    boundary_mode: str = "sandboxed_rebuild_run_test_boundary_no_execution"
    run_mode: str = "future_sandboxed_rebuild_run_test"
    permission_scope: str = "ingest.lab.sandboxed_rebuild_run_test.boundary"
    control_binding: dict[str, Any] = field(default_factory=dict)
    pre_execution_boundary: dict[str, Any] = field(default_factory=dict)
    invocation_boundary: dict[str, Any] = field(default_factory=dict)
    execution_boundary: dict[str, Any] = field(default_factory=dict)
    approval_consumption: dict[str, Any] = field(default_factory=dict)
    sandboxed_execution_contract: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    control_binding_found: bool = False
    control_binding_recorded: bool = False
    control_binding_ready: bool = False
    approval_consumed: bool = False
    single_use_consumption_found: bool = False
    single_use_enforced: bool = False
    exact_action_binding_verified: bool = False
    execution_approval_required: bool = True
    execution_approval_consumed: bool = False
    runner_identity_bound: bool = False
    runner_policy_bound: bool = False
    sandbox_policy_bound: bool = False
    sandbox_bound: bool = False
    sandbox_enforced: bool = False
    network_block_bound: bool = False
    timeout_policy_bound: bool = False
    output_capture_bound: bool = False
    kill_switch_bound: bool = False
    execution_receipt_writer_bound: bool = False
    rebuild_declared: bool = False
    run_declared: bool = False
    test_declared: bool = False
    execution_authority: bool = False
    executed: bool = False
    process_launched: bool = False
    container_launched: bool = False
    commands_executed: bool = False
    repo_code_executed: bool = False
    ran_install: bool = False
    ran_build: bool = False
    ran_tests: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    execution_receipt_written: bool = False
    candidate_validated: bool = False
    capability_promoted: bool = False
    store_file_contents: bool = False
    store_sensitive_values: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSandboxedRebuildRunTestBoundary | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        approval_id = _safe_str(data.get("approval_id")).strip()
        control_binding_id = _safe_str(data.get("control_binding_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if not record_id or not approval_id or not control_binding_id or not source_id or not candidate_id:
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_SANDBOXED_REBUILD_RUN_TEST_BOUNDARY_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=approval_id,
            approval_consumption_id=_safe_str(data.get("approval_consumption_id")).strip(),
            invocation_boundary_id=_safe_str(data.get("invocation_boundary_id")).strip(),
            pre_execution_boundary_id=_safe_str(data.get("pre_execution_boundary_id")).strip(),
            control_binding_id=control_binding_id,
            approval_request_id=_safe_str(data.get("approval_request_id")).strip(),
            execution_boundary_id=_safe_str(data.get("execution_boundary_id")).strip(),
            run_boundary_preflight_id=_safe_str(data.get("run_boundary_preflight_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            boundary_kind=_safe_str(data.get("boundary_kind")).strip()
            or "francis.lab.sandboxed_rebuild_run_test_boundary",
            boundary_mode=_safe_str(data.get("boundary_mode")).strip()
            or "sandboxed_rebuild_run_test_boundary_no_execution",
            run_mode=_safe_str(data.get("run_mode")).strip() or "future_sandboxed_rebuild_run_test",
            permission_scope=_safe_str(data.get("permission_scope")).strip()
            or "ingest.lab.sandboxed_rebuild_run_test.boundary",
            control_binding=_safe_dict(data.get("control_binding")),
            pre_execution_boundary=_safe_dict(data.get("pre_execution_boundary")),
            invocation_boundary=_safe_dict(data.get("invocation_boundary")),
            execution_boundary=_safe_dict(data.get("execution_boundary")),
            approval_consumption=_safe_dict(data.get("approval_consumption")),
            sandboxed_execution_contract=_safe_dict(data.get("sandboxed_execution_contract")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            control_binding_found=bool(data.get("control_binding_found", False)),
            control_binding_recorded=bool(data.get("control_binding_recorded", False)),
            control_binding_ready=bool(data.get("control_binding_ready", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            single_use_consumption_found=bool(data.get("single_use_consumption_found", False)),
            single_use_enforced=bool(data.get("single_use_enforced", False)),
            exact_action_binding_verified=bool(data.get("exact_action_binding_verified", False)),
            execution_approval_required=bool(data.get("execution_approval_required", True)),
            execution_approval_consumed=bool(data.get("execution_approval_consumed", False)),
            runner_identity_bound=bool(data.get("runner_identity_bound", False)),
            runner_policy_bound=bool(data.get("runner_policy_bound", False)),
            sandbox_policy_bound=bool(data.get("sandbox_policy_bound", False)),
            sandbox_bound=bool(data.get("sandbox_bound", False)),
            sandbox_enforced=bool(data.get("sandbox_enforced", False)),
            network_block_bound=bool(data.get("network_block_bound", False)),
            timeout_policy_bound=bool(data.get("timeout_policy_bound", False)),
            output_capture_bound=bool(data.get("output_capture_bound", False)),
            kill_switch_bound=bool(data.get("kill_switch_bound", False)),
            execution_receipt_writer_bound=bool(data.get("execution_receipt_writer_bound", False)),
            rebuild_declared=bool(data.get("rebuild_declared", False)),
            run_declared=bool(data.get("run_declared", False)),
            test_declared=bool(data.get("test_declared", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            process_launched=bool(data.get("process_launched", False)),
            container_launched=bool(data.get("container_launched", False)),
            commands_executed=bool(data.get("commands_executed", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            ran_install=bool(data.get("ran_install", False)),
            ran_build=bool(data.get("ran_build", False)),
            ran_tests=bool(data.get("ran_tests", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            execution_receipt_written=bool(data.get("execution_receipt_written", False)),
            candidate_validated=bool(data.get("candidate_validated", False)),
            capability_promoted=bool(data.get("capability_promoted", False)),
            store_file_contents=bool(data.get("store_file_contents", False)),
            store_sensitive_values=bool(data.get("store_sensitive_values", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSandboxedRebuildRunTestApprovalRequest:
    id: str
    approval_id: str
    upstream_approval_id: str
    sandboxed_boundary_id: str
    control_binding_id: str
    pre_execution_boundary_id: str
    invocation_boundary_id: str
    approval_consumption_id: str
    approval_request_id: str
    execution_boundary_id: str
    run_boundary_preflight_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.sandboxed_rebuild_run_test"
    action_hash: str = ""
    approval_path: str = ""
    approval_payload: dict[str, Any] = field(default_factory=dict)
    sandboxed_boundary: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    permission_scope: str = "ingest.lab.sandboxed_rebuild_run_test.request_approval"
    approval_created: bool = False
    approval_consumed: bool = False
    upstream_approval_consumed: bool = False
    boundary_recorded: bool = False
    boundary_ready: bool = False
    execution_authority: bool = False
    executed: bool = False
    process_launched: bool = False
    container_launched: bool = False
    commands_executed: bool = False
    repo_code_executed: bool = False
    ran_install: bool = False
    ran_build: bool = False
    ran_tests: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    execution_receipt_written: bool = False
    candidate_validated: bool = False
    capability_promoted: bool = False
    store_file_contents: bool = False
    store_sensitive_values: bool = False
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSandboxedRebuildRunTestApprovalRequest | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        approval_id = _safe_str(data.get("approval_id")).strip()
        boundary_id = _safe_str(data.get("sandboxed_boundary_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if not record_id or not approval_id or not boundary_id or not source_id or not candidate_id:
            return None
        status = _safe_str(data.get("status")).strip() or "failed"
        if status not in LAB_SANDBOXED_REBUILD_RUN_TEST_APPROVAL_REQUEST_STATUSES:
            status = "failed"
        return cls(
            id=record_id,
            approval_id=approval_id,
            upstream_approval_id=_safe_str(data.get("upstream_approval_id")).strip(),
            sandboxed_boundary_id=boundary_id,
            control_binding_id=_safe_str(data.get("control_binding_id")).strip(),
            pre_execution_boundary_id=_safe_str(data.get("pre_execution_boundary_id")).strip(),
            invocation_boundary_id=_safe_str(data.get("invocation_boundary_id")).strip(),
            approval_consumption_id=_safe_str(data.get("approval_consumption_id")).strip(),
            approval_request_id=_safe_str(data.get("approval_request_id")).strip(),
            execution_boundary_id=_safe_str(data.get("execution_boundary_id")).strip(),
            run_boundary_preflight_id=_safe_str(data.get("run_boundary_preflight_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.sandboxed_rebuild_run_test",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            approval_path=_safe_str(data.get("approval_path")).strip(),
            approval_payload=_safe_dict(data.get("approval_payload")),
            sandboxed_boundary=_safe_dict(data.get("sandboxed_boundary")),
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            permission_scope=_safe_str(data.get("permission_scope")).strip()
            or "ingest.lab.sandboxed_rebuild_run_test.request_approval",
            approval_created=bool(data.get("approval_created", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            upstream_approval_consumed=bool(data.get("upstream_approval_consumed", False)),
            boundary_recorded=bool(data.get("boundary_recorded", False)),
            boundary_ready=bool(data.get("boundary_ready", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            process_launched=bool(data.get("process_launched", False)),
            container_launched=bool(data.get("container_launched", False)),
            commands_executed=bool(data.get("commands_executed", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            ran_install=bool(data.get("ran_install", False)),
            ran_build=bool(data.get("ran_build", False)),
            ran_tests=bool(data.get("ran_tests", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            execution_receipt_written=bool(data.get("execution_receipt_written", False)),
            candidate_validated=bool(data.get("candidate_validated", False)),
            capability_promoted=bool(data.get("capability_promoted", False)),
            store_file_contents=bool(data.get("store_file_contents", False)),
            store_sensitive_values=bool(data.get("store_sensitive_values", False)),
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSandboxedRebuildRunTestApprovalConsumption:
    id: str
    approval_id: str
    approval_request_id: str
    upstream_approval_id: str
    upstream_approval_consumption_id: str
    sandboxed_boundary_id: str
    control_binding_id: str
    pre_execution_boundary_id: str
    invocation_boundary_id: str
    upstream_approval_request_id: str
    execution_boundary_id: str
    run_boundary_preflight_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    consumed_at: str
    actor: str
    action: str = "francis.lab.sandboxed_rebuild_run_test"
    action_hash: str = ""
    approval_status: str = ""
    approval_path: str = ""
    approval_snapshot: dict[str, Any] = field(default_factory=dict)
    approval_binding: dict[str, Any] = field(default_factory=dict)
    approval_request: dict[str, Any] = field(default_factory=dict)
    sandboxed_boundary: dict[str, Any] = field(default_factory=dict)
    permission_scope: str = "ingest.lab.sandboxed_rebuild_run_test.consume_approval"
    consumption_kind: str = "sandboxed_rebuild_run_test_approval"
    approval_consumed: bool = True
    single_use_enforced: bool = True
    upstream_approval_consumed: bool = False
    boundary_recorded: bool = False
    boundary_ready: bool = False
    execution_authority: bool = False
    executed: bool = False
    process_launched: bool = False
    container_launched: bool = False
    commands_executed: bool = False
    repo_code_executed: bool = False
    ran_install: bool = False
    ran_build: bool = False
    ran_tests: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    execution_receipt_written: bool = False
    candidate_validated: bool = False
    capability_promoted: bool = False
    store_file_contents: bool = False
    store_sensitive_values: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSandboxedRebuildRunTestApprovalConsumption | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        approval_id = _safe_str(data.get("approval_id")).strip()
        request_id = _safe_str(data.get("approval_request_id")).strip()
        boundary_id = _safe_str(data.get("sandboxed_boundary_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if not record_id or not approval_id or not request_id or not boundary_id or not source_id or not candidate_id:
            return None
        status = _safe_str(data.get("status")).strip() or "failed"
        if status not in LAB_SANDBOXED_REBUILD_RUN_TEST_APPROVAL_CONSUMPTION_STATUSES:
            status = "failed"
        return cls(
            id=record_id,
            approval_id=approval_id,
            approval_request_id=request_id,
            upstream_approval_id=_safe_str(data.get("upstream_approval_id")).strip(),
            upstream_approval_consumption_id=_safe_str(data.get("upstream_approval_consumption_id")).strip(),
            sandboxed_boundary_id=boundary_id,
            control_binding_id=_safe_str(data.get("control_binding_id")).strip(),
            pre_execution_boundary_id=_safe_str(data.get("pre_execution_boundary_id")).strip(),
            invocation_boundary_id=_safe_str(data.get("invocation_boundary_id")).strip(),
            upstream_approval_request_id=_safe_str(data.get("upstream_approval_request_id")).strip(),
            execution_boundary_id=_safe_str(data.get("execution_boundary_id")).strip(),
            run_boundary_preflight_id=_safe_str(data.get("run_boundary_preflight_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            consumed_at=_safe_str(data.get("consumed_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.sandboxed_rebuild_run_test",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            approval_status=_safe_str(data.get("approval_status")).strip(),
            approval_path=_safe_str(data.get("approval_path")).strip(),
            approval_snapshot=_safe_dict(data.get("approval_snapshot")),
            approval_binding=_safe_dict(data.get("approval_binding")),
            approval_request=_safe_dict(data.get("approval_request")),
            sandboxed_boundary=_safe_dict(data.get("sandboxed_boundary")),
            permission_scope=_safe_str(data.get("permission_scope")).strip()
            or "ingest.lab.sandboxed_rebuild_run_test.consume_approval",
            consumption_kind=_safe_str(data.get("consumption_kind")).strip() or "sandboxed_rebuild_run_test_approval",
            approval_consumed=bool(data.get("approval_consumed", True)),
            single_use_enforced=bool(data.get("single_use_enforced", True)),
            upstream_approval_consumed=bool(data.get("upstream_approval_consumed", False)),
            boundary_recorded=bool(data.get("boundary_recorded", False)),
            boundary_ready=bool(data.get("boundary_ready", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            process_launched=bool(data.get("process_launched", False)),
            container_launched=bool(data.get("container_launched", False)),
            commands_executed=bool(data.get("commands_executed", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            ran_install=bool(data.get("ran_install", False)),
            ran_build=bool(data.get("ran_build", False)),
            ran_tests=bool(data.get("ran_tests", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            execution_receipt_written=bool(data.get("execution_receipt_written", False)),
            candidate_validated=bool(data.get("candidate_validated", False)),
            capability_promoted=bool(data.get("capability_promoted", False)),
            store_file_contents=bool(data.get("store_file_contents", False)),
            store_sensitive_values=bool(data.get("store_sensitive_values", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSandboxedRebuildRunTestRunnerBindingPreflight:
    id: str
    approval_id: str
    approval_consumption_id: str
    approval_request_id: str
    sandboxed_boundary_id: str
    control_binding_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.sandboxed_rebuild_run_test"
    action_hash: str = ""
    permission_scope: str = "ingest.lab.sandboxed_rebuild_run_test.runner_binding"
    binding_kind: str = "sandboxed_rebuild_run_test_runner_binding_preflight"
    binding_mode: str = "static_provider_reference_only_no_live_runner"
    provider_kind: str = ""
    selected_provider_kind: str = ""
    approval_consumption: dict[str, Any] = field(default_factory=dict)
    sandboxed_boundary: dict[str, Any] = field(default_factory=dict)
    provider_reference: dict[str, Any] = field(default_factory=dict)
    provider_policy_manifest: dict[str, Any] = field(default_factory=dict)
    runner_binding_contract: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    approval_consumed: bool = True
    single_use_enforced: bool = True
    static_provider_reference_bound: bool = False
    provider_reference_checked: bool = False
    provider_reference_present: bool = False
    provider_reference_verified: bool = False
    provider_policy_manifest_present: bool = False
    provider_policy_manifest_bound: bool = False
    runner_binding_declared: bool = False
    live_runner_bound: bool = False
    sandbox_runner_bound: bool = False
    sandbox_bound: bool = False
    sandbox_enforced: bool = False
    network_block_bound: bool = False
    timeout_policy_bound: bool = False
    output_capture_bound: bool = False
    kill_switch_bound: bool = False
    command_allowlist_bound: bool = False
    source_mount_bound: bool = False
    execution_receipt_writer_bound: bool = False
    provider_binary_executed: bool = False
    provider_service_queried: bool = False
    execution_authority: bool = False
    executed: bool = False
    process_launched: bool = False
    container_launched: bool = False
    commands_executed: bool = False
    repo_code_executed: bool = False
    ran_install: bool = False
    ran_build: bool = False
    ran_tests: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    execution_receipt_written: bool = False
    candidate_validated: bool = False
    capability_promoted: bool = False
    store_file_contents: bool = False
    store_sensitive_values: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSandboxedRebuildRunTestRunnerBindingPreflight | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        approval_id = _safe_str(data.get("approval_id")).strip()
        consumption_id = _safe_str(data.get("approval_consumption_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if not record_id or not approval_id or not consumption_id or not source_id or not candidate_id:
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_SANDBOXED_REBUILD_RUN_TEST_RUNNER_BINDING_PREFLIGHT_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=approval_id,
            approval_consumption_id=consumption_id,
            approval_request_id=_safe_str(data.get("approval_request_id")).strip(),
            sandboxed_boundary_id=_safe_str(data.get("sandboxed_boundary_id")).strip(),
            control_binding_id=_safe_str(data.get("control_binding_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.sandboxed_rebuild_run_test",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            permission_scope=_safe_str(data.get("permission_scope")).strip()
            or "ingest.lab.sandboxed_rebuild_run_test.runner_binding",
            binding_kind=_safe_str(data.get("binding_kind")).strip()
            or "sandboxed_rebuild_run_test_runner_binding_preflight",
            binding_mode=_safe_str(data.get("binding_mode")).strip() or "static_provider_reference_only_no_live_runner",
            provider_kind=_safe_str(data.get("provider_kind")).strip(),
            selected_provider_kind=_safe_str(data.get("selected_provider_kind")).strip(),
            approval_consumption=_safe_dict(data.get("approval_consumption")),
            sandboxed_boundary=_safe_dict(data.get("sandboxed_boundary")),
            provider_reference=_safe_dict(data.get("provider_reference")),
            provider_policy_manifest=_safe_dict(data.get("provider_policy_manifest")),
            runner_binding_contract=_safe_dict(data.get("runner_binding_contract")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            approval_consumed=bool(data.get("approval_consumed", True)),
            single_use_enforced=bool(data.get("single_use_enforced", True)),
            static_provider_reference_bound=bool(data.get("static_provider_reference_bound", False)),
            provider_reference_checked=bool(data.get("provider_reference_checked", False)),
            provider_reference_present=bool(data.get("provider_reference_present", False)),
            provider_reference_verified=bool(data.get("provider_reference_verified", False)),
            provider_policy_manifest_present=bool(data.get("provider_policy_manifest_present", False)),
            provider_policy_manifest_bound=bool(data.get("provider_policy_manifest_bound", False)),
            runner_binding_declared=bool(data.get("runner_binding_declared", False)),
            live_runner_bound=bool(data.get("live_runner_bound", False)),
            sandbox_runner_bound=bool(data.get("sandbox_runner_bound", False)),
            sandbox_bound=bool(data.get("sandbox_bound", False)),
            sandbox_enforced=bool(data.get("sandbox_enforced", False)),
            network_block_bound=bool(data.get("network_block_bound", False)),
            timeout_policy_bound=bool(data.get("timeout_policy_bound", False)),
            output_capture_bound=bool(data.get("output_capture_bound", False)),
            kill_switch_bound=bool(data.get("kill_switch_bound", False)),
            command_allowlist_bound=bool(data.get("command_allowlist_bound", False)),
            source_mount_bound=bool(data.get("source_mount_bound", False)),
            execution_receipt_writer_bound=bool(data.get("execution_receipt_writer_bound", False)),
            provider_binary_executed=bool(data.get("provider_binary_executed", False)),
            provider_service_queried=bool(data.get("provider_service_queried", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            process_launched=bool(data.get("process_launched", False)),
            container_launched=bool(data.get("container_launched", False)),
            commands_executed=bool(data.get("commands_executed", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            ran_install=bool(data.get("ran_install", False)),
            ran_build=bool(data.get("ran_build", False)),
            ran_tests=bool(data.get("ran_tests", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            execution_receipt_written=bool(data.get("execution_receipt_written", False)),
            candidate_validated=bool(data.get("candidate_validated", False)),
            capability_promoted=bool(data.get("capability_promoted", False)),
            store_file_contents=bool(data.get("store_file_contents", False)),
            store_sensitive_values=bool(data.get("store_sensitive_values", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSandboxedRebuildRunTestSandboxPolicyPreflight:
    id: str
    approval_id: str
    approval_consumption_id: str
    runner_binding_id: str
    approval_request_id: str
    sandboxed_boundary_id: str
    control_binding_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.sandboxed_rebuild_run_test"
    action_hash: str = ""
    permission_scope: str = "ingest.lab.sandboxed_rebuild_run_test.sandbox_policy"
    policy_kind: str = "sandboxed_rebuild_run_test_sandbox_policy_preflight"
    policy_mode: str = "policy_preflight_no_live_sandbox"
    approval_consumption: dict[str, Any] = field(default_factory=dict)
    runner_binding: dict[str, Any] = field(default_factory=dict)
    provider_reference: dict[str, Any] = field(default_factory=dict)
    provider_policy_manifest: dict[str, Any] = field(default_factory=dict)
    sandbox_policy: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    approval_consumed: bool = True
    single_use_enforced: bool = True
    runner_binding_present: bool = False
    static_provider_reference_bound: bool = False
    provider_kind_selected: bool = False
    sandbox_policy_declared: bool = False
    network_default_deny: bool = True
    network_allowed: bool = False
    repo_write_allowed: bool = False
    destructive_allowed: bool = False
    secret_storage_allowed: bool = False
    command_execution_enabled: bool = False
    command_allowlist_bound: bool = False
    execution_receipt_writer_bound: bool = False
    live_sandbox_bound: bool = False
    sandbox_enforced: bool = False
    source_read_only_reference: bool = True
    process_launch_allowed: bool = False
    container_launch_allowed: bool = False
    provider_binary_execution_allowed: bool = False
    provider_service_query_allowed: bool = False
    timeout_policy_bound: bool = False
    output_capture_bound: bool = False
    kill_switch_bound: bool = False
    env_passthrough_allowed: bool = False
    execution_authority: bool = False
    executed: bool = False
    process_launched: bool = False
    container_launched: bool = False
    commands_executed: bool = False
    repo_code_executed: bool = False
    ran_install: bool = False
    ran_build: bool = False
    ran_tests: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    execution_receipt_written: bool = False
    candidate_validated: bool = False
    capability_promoted: bool = False
    store_file_contents: bool = False
    store_sensitive_values: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSandboxedRebuildRunTestSandboxPolicyPreflight | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        approval_id = _safe_str(data.get("approval_id")).strip()
        consumption_id = _safe_str(data.get("approval_consumption_id")).strip()
        runner_binding_id = _safe_str(data.get("runner_binding_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if not record_id or not approval_id or not consumption_id or not runner_binding_id or not source_id:
            return None
        if not candidate_id:
            return None
        status = _safe_str(data.get("status")).strip() or "blocked"
        if status not in LAB_SANDBOXED_REBUILD_RUN_TEST_SANDBOX_POLICY_PREFLIGHT_STATUSES:
            status = "blocked"
        return cls(
            id=record_id,
            approval_id=approval_id,
            approval_consumption_id=consumption_id,
            runner_binding_id=runner_binding_id,
            approval_request_id=_safe_str(data.get("approval_request_id")).strip(),
            sandboxed_boundary_id=_safe_str(data.get("sandboxed_boundary_id")).strip(),
            control_binding_id=_safe_str(data.get("control_binding_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.sandboxed_rebuild_run_test",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            permission_scope=_safe_str(data.get("permission_scope")).strip()
            or "ingest.lab.sandboxed_rebuild_run_test.sandbox_policy",
            policy_kind=_safe_str(data.get("policy_kind")).strip()
            or "sandboxed_rebuild_run_test_sandbox_policy_preflight",
            policy_mode=_safe_str(data.get("policy_mode")).strip() or "policy_preflight_no_live_sandbox",
            approval_consumption=_safe_dict(data.get("approval_consumption")),
            runner_binding=_safe_dict(data.get("runner_binding")),
            provider_reference=_safe_dict(data.get("provider_reference")),
            provider_policy_manifest=_safe_dict(data.get("provider_policy_manifest")),
            sandbox_policy=_safe_dict(data.get("sandbox_policy")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            approval_consumed=bool(data.get("approval_consumed", True)),
            single_use_enforced=bool(data.get("single_use_enforced", True)),
            runner_binding_present=bool(data.get("runner_binding_present", False)),
            static_provider_reference_bound=bool(data.get("static_provider_reference_bound", False)),
            provider_kind_selected=bool(data.get("provider_kind_selected", False)),
            sandbox_policy_declared=bool(data.get("sandbox_policy_declared", False)),
            network_default_deny=bool(data.get("network_default_deny", True)),
            network_allowed=bool(data.get("network_allowed", False)),
            repo_write_allowed=bool(data.get("repo_write_allowed", False)),
            destructive_allowed=bool(data.get("destructive_allowed", False)),
            secret_storage_allowed=bool(data.get("secret_storage_allowed", False)),
            command_execution_enabled=bool(data.get("command_execution_enabled", False)),
            command_allowlist_bound=bool(data.get("command_allowlist_bound", False)),
            execution_receipt_writer_bound=bool(data.get("execution_receipt_writer_bound", False)),
            live_sandbox_bound=bool(data.get("live_sandbox_bound", False)),
            sandbox_enforced=bool(data.get("sandbox_enforced", False)),
            source_read_only_reference=bool(data.get("source_read_only_reference", True)),
            process_launch_allowed=bool(data.get("process_launch_allowed", False)),
            container_launch_allowed=bool(data.get("container_launch_allowed", False)),
            provider_binary_execution_allowed=bool(data.get("provider_binary_execution_allowed", False)),
            provider_service_query_allowed=bool(data.get("provider_service_query_allowed", False)),
            timeout_policy_bound=bool(data.get("timeout_policy_bound", False)),
            output_capture_bound=bool(data.get("output_capture_bound", False)),
            kill_switch_bound=bool(data.get("kill_switch_bound", False)),
            env_passthrough_allowed=bool(data.get("env_passthrough_allowed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            process_launched=bool(data.get("process_launched", False)),
            container_launched=bool(data.get("container_launched", False)),
            commands_executed=bool(data.get("commands_executed", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            ran_install=bool(data.get("ran_install", False)),
            ran_build=bool(data.get("ran_build", False)),
            ran_tests=bool(data.get("ran_tests", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            execution_receipt_written=bool(data.get("execution_receipt_written", False)),
            candidate_validated=bool(data.get("candidate_validated", False)),
            capability_promoted=bool(data.get("capability_promoted", False)),
            store_file_contents=bool(data.get("store_file_contents", False)),
            store_sensitive_values=bool(data.get("store_sensitive_values", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSyntheticExecutionReceipt:
    id: str
    operation: str
    schema_version: int
    mode: str
    phase: str
    status: str
    result_status: str
    created_at: str
    updated_at: str
    approval_id: str
    writer_preflight_id: str
    receipt_prewrite_binding_id: str
    receipt_write_readiness_id: str
    receipt_sink_reservation_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    finalized_at: str = ""
    reserved_execution_receipt: dict[str, Any] = field(default_factory=dict)
    writer_boundary: dict[str, Any] = field(default_factory=dict)
    writer_contract: dict[str, Any] = field(default_factory=dict)
    synthetic: bool = True
    noop: bool = True
    prewritten: bool = False
    finalized: bool = False
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    ran_repo_scripts: bool = False
    ran_install: bool = False
    ran_build: bool = False
    ran_tests: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    repo_code_executed: bool = False
    store_file_contents: bool = False
    store_sensitive_values: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSyntheticExecutionReceipt | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        writer_preflight_id = _safe_str(data.get("writer_preflight_id")).strip()
        if not record_id or not source_id or not candidate_id or not preflight_id or not writer_preflight_id:
            return None
        status = _safe_str(data.get("status")).strip() or "failed"
        if status not in LAB_SYNTHETIC_EXECUTION_RECEIPT_STATUSES:
            status = "failed"
        try:
            schema_version = int(data.get("schema_version") or 1)
        except (TypeError, ValueError):
            schema_version = 1
        return cls(
            id=record_id,
            operation=_safe_str(data.get("operation")).strip() or "lab.execution.run",
            schema_version=schema_version,
            mode=_safe_str(data.get("mode")).strip() or "synthetic_noop_execution_receipt",
            phase=_safe_str(data.get("phase")).strip() or "prewrite",
            status=status,
            result_status=_safe_str(data.get("result_status")).strip() or status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            approval_id=_safe_str(data.get("approval_id")).strip(),
            writer_preflight_id=writer_preflight_id,
            receipt_prewrite_binding_id=_safe_str(data.get("receipt_prewrite_binding_id")).strip(),
            receipt_write_readiness_id=_safe_str(data.get("receipt_write_readiness_id")).strip(),
            receipt_sink_reservation_id=_safe_str(data.get("receipt_sink_reservation_id")).strip(),
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=_safe_str(data.get("workspace_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            finalized_at=_safe_str(data.get("finalized_at")).strip(),
            reserved_execution_receipt=_safe_dict(data.get("reserved_execution_receipt")),
            writer_boundary=_safe_dict(data.get("writer_boundary")),
            writer_contract=_safe_dict(data.get("writer_contract")),
            synthetic=bool(data.get("synthetic", True)),
            noop=bool(data.get("noop", True)),
            prewritten=bool(data.get("prewritten", False)),
            finalized=bool(data.get("finalized", False)),
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            ran_repo_scripts=bool(data.get("ran_repo_scripts", False)),
            ran_install=bool(data.get("ran_install", False)),
            ran_build=bool(data.get("ran_build", False)),
            ran_tests=bool(data.get("ran_tests", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            store_file_contents=bool(data.get("store_file_contents", False)),
            store_sensitive_values=bool(data.get("store_sensitive_values", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabApprovalConsumptionRecord:
    id: str
    approval_id: str
    synthetic_execution_receipt_id: str
    writer_preflight_id: str
    receipt_prewrite_binding_id: str
    receipt_write_readiness_id: str
    receipt_sink_reservation_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    consumed_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    approval_status: str = ""
    approval_path: str = ""
    approval_snapshot: dict[str, Any] = field(default_factory=dict)
    approval_binding: dict[str, Any] = field(default_factory=dict)
    synthetic_execution_receipt: dict[str, Any] = field(default_factory=dict)
    consumption_kind: str = "synthetic_noop_execution_receipt"
    consumption_scope: str = "francis.lab.synthetic_noop"
    approval_consumed: bool = True
    single_use_enforced: bool = True
    execution_authority: bool = False
    executed: bool = False
    ran_repo_scripts: bool = False
    ran_install: bool = False
    ran_build: bool = False
    ran_tests: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    repo_code_executed: bool = False
    store_file_contents: bool = False
    store_sensitive_values: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabApprovalConsumptionRecord | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        approval_id = _safe_str(data.get("approval_id")).strip()
        execution_receipt_id = _safe_str(data.get("synthetic_execution_receipt_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if not record_id or not approval_id or not execution_receipt_id or not preflight_id or not source_id:
            return None
        status = _safe_str(data.get("status")).strip() or "failed"
        if status not in LAB_APPROVAL_CONSUMPTION_RECORD_STATUSES:
            status = "failed"
        return cls(
            id=record_id,
            approval_id=approval_id,
            synthetic_execution_receipt_id=execution_receipt_id,
            writer_preflight_id=_safe_str(data.get("writer_preflight_id")).strip(),
            receipt_prewrite_binding_id=_safe_str(data.get("receipt_prewrite_binding_id")).strip(),
            receipt_write_readiness_id=_safe_str(data.get("receipt_write_readiness_id")).strip(),
            receipt_sink_reservation_id=_safe_str(data.get("receipt_sink_reservation_id")).strip(),
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=_safe_str(data.get("workspace_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            consumed_at=_safe_str(data.get("consumed_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            approval_status=_safe_str(data.get("approval_status")).strip(),
            approval_path=_safe_str(data.get("approval_path")).strip(),
            approval_snapshot=_safe_dict(data.get("approval_snapshot")),
            approval_binding=_safe_dict(data.get("approval_binding")),
            synthetic_execution_receipt=_safe_dict(data.get("synthetic_execution_receipt")),
            consumption_kind=_safe_str(data.get("consumption_kind")).strip() or "synthetic_noop_execution_receipt",
            consumption_scope=_safe_str(data.get("consumption_scope")).strip() or "francis.lab.synthetic_noop",
            approval_consumed=bool(data.get("approval_consumed", True)),
            single_use_enforced=bool(data.get("single_use_enforced", True)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            ran_repo_scripts=bool(data.get("ran_repo_scripts", False)),
            ran_install=bool(data.get("ran_install", False)),
            ran_build=bool(data.get("ran_build", False)),
            ran_tests=bool(data.get("ran_tests", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            store_file_contents=bool(data.get("store_file_contents", False)),
            store_sensitive_values=bool(data.get("store_sensitive_values", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabNoopRunnerEnvelope:
    id: str
    approval_id: str
    approval_consumption_record_id: str
    synthetic_execution_receipt_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    runner_kind: str = "francis.lab.noop_runner"
    runner_mode: str = "builtin_noop_only"
    approval_consumption_record_path: str = ""
    synthetic_execution_receipt_path: str = ""
    approval_consumption_record: dict[str, Any] = field(default_factory=dict)
    synthetic_execution_receipt: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    noop_performed: bool = False
    approval_consumed: bool = True
    single_use_enforced: bool = True
    execution_authority: bool = False
    executed: bool = False
    commands_executed: bool = False
    repo_code_executed: bool = False
    ran_repo_scripts: bool = False
    ran_install: bool = False
    ran_build: bool = False
    ran_tests: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    store_file_contents: bool = False
    store_sensitive_values: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabNoopRunnerEnvelope | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        approval_id = _safe_str(data.get("approval_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if not record_id or not approval_id or not source_id or not candidate_id:
            return None
        status = _safe_str(data.get("status")).strip() or "failed"
        if status not in LAB_NOOP_RUNNER_ENVELOPE_STATUSES:
            status = "failed"
        return cls(
            id=record_id,
            approval_id=approval_id,
            approval_consumption_record_id=_safe_str(data.get("approval_consumption_record_id")).strip(),
            synthetic_execution_receipt_id=_safe_str(data.get("synthetic_execution_receipt_id")).strip(),
            preflight_id=_safe_str(data.get("preflight_id")).strip(),
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=_safe_str(data.get("workspace_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            runner_kind=_safe_str(data.get("runner_kind")).strip() or "francis.lab.noop_runner",
            runner_mode=_safe_str(data.get("runner_mode")).strip() or "builtin_noop_only",
            approval_consumption_record_path=_safe_str(data.get("approval_consumption_record_path")).strip(),
            synthetic_execution_receipt_path=_safe_str(data.get("synthetic_execution_receipt_path")).strip(),
            approval_consumption_record=_safe_dict(data.get("approval_consumption_record")),
            synthetic_execution_receipt=_safe_dict(data.get("synthetic_execution_receipt")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            noop_performed=bool(data.get("noop_performed", False)),
            approval_consumed=bool(data.get("approval_consumed", True)),
            single_use_enforced=bool(data.get("single_use_enforced", True)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            commands_executed=bool(data.get("commands_executed", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            ran_repo_scripts=bool(data.get("ran_repo_scripts", False)),
            ran_install=bool(data.get("ran_install", False)),
            ran_build=bool(data.get("ran_build", False)),
            ran_tests=bool(data.get("ran_tests", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            store_file_contents=bool(data.get("store_file_contents", False)),
            store_sensitive_values=bool(data.get("store_sensitive_values", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabNoopRunnerTranscript:
    id: str
    noop_runner_envelope_id: str
    approval_id: str
    approval_consumption_record_id: str
    synthetic_execution_receipt_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    capture_kind: str = "francis.lab.noop_runner_transcript"
    capture_mode: str = "builtin_noop_empty_output"
    noop_runner_envelope_path: str = ""
    noop_runner_envelope: dict[str, Any] = field(default_factory=dict)
    stdout: dict[str, Any] = field(default_factory=dict)
    stderr: dict[str, Any] = field(default_factory=dict)
    combined_output_hash: str = ""
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    noop_performed: bool = False
    builtin_noop_output_captured: bool = False
    real_process_output_captured: bool = False
    stdout_content_stored: bool = False
    stderr_content_stored: bool = False
    output_content_stored: bool = False
    execution_authority: bool = False
    executed: bool = False
    commands_executed: bool = False
    repo_code_executed: bool = False
    ran_repo_scripts: bool = False
    ran_install: bool = False
    ran_build: bool = False
    ran_tests: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    store_file_contents: bool = False
    store_sensitive_values: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabNoopRunnerTranscript | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        envelope_id = _safe_str(data.get("noop_runner_envelope_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if not record_id or not envelope_id or not source_id or not candidate_id:
            return None
        status = _safe_str(data.get("status")).strip() or "failed"
        if status not in LAB_NOOP_RUNNER_TRANSCRIPT_STATUSES:
            status = "failed"
        return cls(
            id=record_id,
            noop_runner_envelope_id=envelope_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            approval_consumption_record_id=_safe_str(data.get("approval_consumption_record_id")).strip(),
            synthetic_execution_receipt_id=_safe_str(data.get("synthetic_execution_receipt_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            capture_kind=_safe_str(data.get("capture_kind")).strip() or "francis.lab.noop_runner_transcript",
            capture_mode=_safe_str(data.get("capture_mode")).strip() or "builtin_noop_empty_output",
            noop_runner_envelope_path=_safe_str(data.get("noop_runner_envelope_path")).strip(),
            noop_runner_envelope=_safe_dict(data.get("noop_runner_envelope")),
            stdout=_safe_dict(data.get("stdout")),
            stderr=_safe_dict(data.get("stderr")),
            combined_output_hash=_safe_str(data.get("combined_output_hash")).strip(),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            noop_performed=bool(data.get("noop_performed", False)),
            builtin_noop_output_captured=bool(data.get("builtin_noop_output_captured", False)),
            real_process_output_captured=bool(data.get("real_process_output_captured", False)),
            stdout_content_stored=bool(data.get("stdout_content_stored", False)),
            stderr_content_stored=bool(data.get("stderr_content_stored", False)),
            output_content_stored=bool(data.get("output_content_stored", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            commands_executed=bool(data.get("commands_executed", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            ran_repo_scripts=bool(data.get("ran_repo_scripts", False)),
            ran_install=bool(data.get("ran_install", False)),
            ran_build=bool(data.get("ran_build", False)),
            ran_tests=bool(data.get("ran_tests", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            store_file_contents=bool(data.get("store_file_contents", False)),
            store_sensitive_values=bool(data.get("store_sensitive_values", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabNoopRunnerIdentityBinding:
    id: str
    noop_runner_transcript_id: str
    noop_runner_envelope_id: str
    approval_id: str
    approval_consumption_record_id: str
    synthetic_execution_receipt_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    runner_id: str = "francis.lab.runner.builtin_noop.v0"
    runner_kind: str = "francis.lab.noop_runner"
    runner_mode: str = "builtin_noop_only"
    runner_version: str = "v0"
    noop_runner_transcript_path: str = ""
    noop_runner_envelope_path: str = ""
    noop_runner_transcript: dict[str, Any] = field(default_factory=dict)
    noop_runner_envelope: dict[str, Any] = field(default_factory=dict)
    runner_identity: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    runner_identity_bound: bool = False
    builtin_noop_only: bool = True
    live_runner_bound: bool = False
    sandbox_runner_bound: bool = False
    execution_authority: bool = False
    executed: bool = False
    commands_executed: bool = False
    repo_code_executed: bool = False
    ran_repo_scripts: bool = False
    ran_install: bool = False
    ran_build: bool = False
    ran_tests: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    real_process_output_captured: bool = False
    candidate_validated: bool = False
    capability_promoted: bool = False
    store_file_contents: bool = False
    store_sensitive_values: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabNoopRunnerIdentityBinding | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        transcript_id = _safe_str(data.get("noop_runner_transcript_id")).strip()
        envelope_id = _safe_str(data.get("noop_runner_envelope_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        if not record_id or not transcript_id or not envelope_id or not source_id or not candidate_id:
            return None
        status = _safe_str(data.get("status")).strip() or "failed"
        if status not in LAB_NOOP_RUNNER_IDENTITY_BINDING_STATUSES:
            status = "failed"
        return cls(
            id=record_id,
            noop_runner_transcript_id=transcript_id,
            noop_runner_envelope_id=envelope_id,
            approval_id=_safe_str(data.get("approval_id")).strip(),
            approval_consumption_record_id=_safe_str(data.get("approval_consumption_record_id")).strip(),
            synthetic_execution_receipt_id=_safe_str(data.get("synthetic_execution_receipt_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            runner_id=_safe_str(data.get("runner_id")).strip() or "francis.lab.runner.builtin_noop.v0",
            runner_kind=_safe_str(data.get("runner_kind")).strip() or "francis.lab.noop_runner",
            runner_mode=_safe_str(data.get("runner_mode")).strip() or "builtin_noop_only",
            runner_version=_safe_str(data.get("runner_version")).strip() or "v0",
            noop_runner_transcript_path=_safe_str(data.get("noop_runner_transcript_path")).strip(),
            noop_runner_envelope_path=_safe_str(data.get("noop_runner_envelope_path")).strip(),
            noop_runner_transcript=_safe_dict(data.get("noop_runner_transcript")),
            noop_runner_envelope=_safe_dict(data.get("noop_runner_envelope")),
            runner_identity=_safe_dict(data.get("runner_identity")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            runner_identity_bound=bool(data.get("runner_identity_bound", False)),
            builtin_noop_only=bool(data.get("builtin_noop_only", True)),
            live_runner_bound=bool(data.get("live_runner_bound", False)),
            sandbox_runner_bound=bool(data.get("sandbox_runner_bound", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            commands_executed=bool(data.get("commands_executed", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            ran_repo_scripts=bool(data.get("ran_repo_scripts", False)),
            ran_install=bool(data.get("ran_install", False)),
            ran_build=bool(data.get("ran_build", False)),
            ran_tests=bool(data.get("ran_tests", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            real_process_output_captured=bool(data.get("real_process_output_captured", False)),
            candidate_validated=bool(data.get("candidate_validated", False)),
            capability_promoted=bool(data.get("capability_promoted", False)),
            store_file_contents=bool(data.get("store_file_contents", False)),
            store_sensitive_values=bool(data.get("store_sensitive_values", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSourceMountReadiness:
    id: str
    noop_runner_identity_binding_id: str
    noop_runner_transcript_id: str
    noop_runner_envelope_id: str
    approval_id: str
    approval_consumption_record_id: str
    synthetic_execution_receipt_id: str
    workspace_id: str
    plan_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    source_mount_mode: str = "reference_only_read_only"
    mount_kind: str = "source_reference_readiness"
    workspace_path: str = ""
    workspace_manifest_path: str = ""
    noop_runner_identity_binding_path: str = ""
    workspace: dict[str, Any] = field(default_factory=dict)
    source_reference: dict[str, Any] = field(default_factory=dict)
    noop_runner_identity_binding: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    source_reference_ready: bool = False
    read_only_reference_confirmed: bool = False
    read_only_mount_bound: bool = False
    source_mount_enforced: bool = False
    source_copied: bool = False
    source_write_allowed: bool = False
    runner_identity_verified: bool = False
    builtin_noop_only: bool = True
    live_runner_bound: bool = False
    sandbox_runner_bound: bool = False
    execution_authority: bool = False
    executed: bool = False
    commands_executed: bool = False
    repo_code_executed: bool = False
    ran_repo_scripts: bool = False
    ran_install: bool = False
    ran_build: bool = False
    ran_tests: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    candidate_validated: bool = False
    capability_promoted: bool = False
    store_file_contents: bool = False
    store_sensitive_values: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSourceMountReadiness | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        workspace_id = _safe_str(data.get("workspace_id")).strip()
        if not record_id or not source_id or not candidate_id or not workspace_id:
            return None
        status = _safe_str(data.get("status")).strip() or "failed"
        if status not in LAB_SOURCE_MOUNT_READINESS_STATUSES:
            status = "failed"
        return cls(
            id=record_id,
            noop_runner_identity_binding_id=_safe_str(data.get("noop_runner_identity_binding_id")).strip(),
            noop_runner_transcript_id=_safe_str(data.get("noop_runner_transcript_id")).strip(),
            noop_runner_envelope_id=_safe_str(data.get("noop_runner_envelope_id")).strip(),
            approval_id=_safe_str(data.get("approval_id")).strip(),
            approval_consumption_record_id=_safe_str(data.get("approval_consumption_record_id")).strip(),
            synthetic_execution_receipt_id=_safe_str(data.get("synthetic_execution_receipt_id")).strip(),
            workspace_id=workspace_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            source_mount_mode=_safe_str(data.get("source_mount_mode")).strip() or "reference_only_read_only",
            mount_kind=_safe_str(data.get("mount_kind")).strip() or "source_reference_readiness",
            workspace_path=_safe_str(data.get("workspace_path")).strip(),
            workspace_manifest_path=_safe_str(data.get("workspace_manifest_path")).strip(),
            noop_runner_identity_binding_path=_safe_str(data.get("noop_runner_identity_binding_path")).strip(),
            workspace=_safe_dict(data.get("workspace")),
            source_reference=_safe_dict(data.get("source_reference")),
            noop_runner_identity_binding=_safe_dict(data.get("noop_runner_identity_binding")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            source_reference_ready=bool(data.get("source_reference_ready", False)),
            read_only_reference_confirmed=bool(data.get("read_only_reference_confirmed", False)),
            read_only_mount_bound=bool(data.get("read_only_mount_bound", False)),
            source_mount_enforced=bool(data.get("source_mount_enforced", False)),
            source_copied=bool(data.get("source_copied", False)),
            source_write_allowed=bool(data.get("source_write_allowed", False)),
            runner_identity_verified=bool(data.get("runner_identity_verified", False)),
            builtin_noop_only=bool(data.get("builtin_noop_only", True)),
            live_runner_bound=bool(data.get("live_runner_bound", False)),
            sandbox_runner_bound=bool(data.get("sandbox_runner_bound", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            commands_executed=bool(data.get("commands_executed", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            ran_repo_scripts=bool(data.get("ran_repo_scripts", False)),
            ran_install=bool(data.get("ran_install", False)),
            ran_build=bool(data.get("ran_build", False)),
            ran_tests=bool(data.get("ran_tests", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            candidate_validated=bool(data.get("candidate_validated", False)),
            capability_promoted=bool(data.get("capability_promoted", False)),
            store_file_contents=bool(data.get("store_file_contents", False)),
            store_sensitive_values=bool(data.get("store_sensitive_values", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabSourceMountContract:
    id: str
    source_mount_readiness_id: str
    noop_runner_identity_binding_id: str
    approval_id: str
    workspace_id: str
    plan_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    contract_kind: str = "francis.lab.source_mount_contract"
    contract_version: int = 1
    contract_mode: str = "contract_only_no_live_mount"
    mount_mode: str = "future_read_only_source_mount"
    workspace_path: str = ""
    workspace_manifest_path: str = ""
    source_mount_readiness_path: str = ""
    source_mount_contract: dict[str, Any] = field(default_factory=dict)
    source_mount_readiness: dict[str, Any] = field(default_factory=dict)
    source_reference: dict[str, Any] = field(default_factory=dict)
    required_checks: list[str] = field(default_factory=list)
    current_checks: dict[str, Any] = field(default_factory=dict)
    missing_checks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    contract_declared: bool = False
    source_reference_ready: bool = False
    read_only_reference_confirmed: bool = False
    live_mount_bound: bool = False
    mount_enforced: bool = False
    read_only_mount_bound: bool = False
    source_copied: bool = False
    source_write_allowed: bool = False
    live_runner_bound: bool = False
    sandbox_runner_bound: bool = False
    execution_authority: bool = False
    executed: bool = False
    commands_executed: bool = False
    repo_code_executed: bool = False
    ran_repo_scripts: bool = False
    ran_install: bool = False
    ran_build: bool = False
    ran_tests: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    candidate_validated: bool = False
    capability_promoted: bool = False
    store_file_contents: bool = False
    store_sensitive_values: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_performed: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabSourceMountContract | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        readiness_id = _safe_str(data.get("source_mount_readiness_id")).strip()
        source_id = _safe_str(data.get("source_id")).strip()
        candidate_id = _safe_str(data.get("candidate_id")).strip()
        workspace_id = _safe_str(data.get("workspace_id")).strip()
        if not record_id or not readiness_id or not source_id or not candidate_id or not workspace_id:
            return None
        status = _safe_str(data.get("status")).strip() or "failed"
        if status not in LAB_SOURCE_MOUNT_CONTRACT_STATUSES:
            status = "failed"
        return cls(
            id=record_id,
            source_mount_readiness_id=readiness_id,
            noop_runner_identity_binding_id=_safe_str(data.get("noop_runner_identity_binding_id")).strip(),
            approval_id=_safe_str(data.get("approval_id")).strip(),
            workspace_id=workspace_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            contract_kind=_safe_str(data.get("contract_kind")).strip() or "francis.lab.source_mount_contract",
            contract_version=int(data.get("contract_version", 1) or 1),
            contract_mode=_safe_str(data.get("contract_mode")).strip() or "contract_only_no_live_mount",
            mount_mode=_safe_str(data.get("mount_mode")).strip() or "future_read_only_source_mount",
            workspace_path=_safe_str(data.get("workspace_path")).strip(),
            workspace_manifest_path=_safe_str(data.get("workspace_manifest_path")).strip(),
            source_mount_readiness_path=_safe_str(data.get("source_mount_readiness_path")).strip(),
            source_mount_contract=_safe_dict(data.get("source_mount_contract")),
            source_mount_readiness=_safe_dict(data.get("source_mount_readiness")),
            source_reference=_safe_dict(data.get("source_reference")),
            required_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("required_checks")) if _safe_str(item).strip()
            ],
            current_checks=_safe_dict(data.get("current_checks")),
            missing_checks=[
                _safe_str(item).strip() for item in _safe_list(data.get("missing_checks")) if _safe_str(item).strip()
            ],
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            contract_declared=bool(data.get("contract_declared", False)),
            source_reference_ready=bool(data.get("source_reference_ready", False)),
            read_only_reference_confirmed=bool(data.get("read_only_reference_confirmed", False)),
            live_mount_bound=bool(data.get("live_mount_bound", False)),
            mount_enforced=bool(data.get("mount_enforced", False)),
            read_only_mount_bound=bool(data.get("read_only_mount_bound", False)),
            source_copied=bool(data.get("source_copied", False)),
            source_write_allowed=bool(data.get("source_write_allowed", False)),
            live_runner_bound=bool(data.get("live_runner_bound", False)),
            sandbox_runner_bound=bool(data.get("sandbox_runner_bound", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            commands_executed=bool(data.get("commands_executed", False)),
            repo_code_executed=bool(data.get("repo_code_executed", False)),
            ran_repo_scripts=bool(data.get("ran_repo_scripts", False)),
            ran_install=bool(data.get("ran_install", False)),
            ran_build=bool(data.get("ran_build", False)),
            ran_tests=bool(data.get("ran_tests", False)),
            network_accessed=bool(data.get("network_accessed", False)),
            wrote_to_repo=bool(data.get("wrote_to_repo", False)),
            candidate_validated=bool(data.get("candidate_validated", False)),
            capability_promoted=bool(data.get("capability_promoted", False)),
            store_file_contents=bool(data.get("store_file_contents", False)),
            store_sensitive_values=bool(data.get("store_sensitive_values", False)),
            warnings=[_safe_str(item).strip() for item in _safe_list(data.get("warnings")) if _safe_str(item).strip()],
            errors=[_safe_str(item).strip() for item in _safe_list(data.get("errors")) if _safe_str(item).strip()],
            validation_performed=[
                _safe_str(item).strip()
                for item in _safe_list(data.get("validation_performed"))
                if _safe_str(item).strip()
            ],
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )


@dataclass(frozen=True)
class LabApprovalConsumptionPreflight:
    id: str
    approval_id: str
    preflight_id: str
    plan_id: str
    workspace_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    status: str
    created_at: str
    updated_at: str
    actor: str
    action: str = "francis.lab.execute"
    action_hash: str = ""
    approval_status: str = ""
    approval_path: str = ""
    approval_snapshot: dict[str, Any] = field(default_factory=dict)
    binding: dict[str, Any] = field(default_factory=dict)
    runner_contract_id: str = ""
    runner_contract: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    approval_consumed: bool = False
    execution_authority: bool = False
    executed: bool = False
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabApprovalConsumptionPreflight | None":
        data = _safe_dict(value)
        record_id = _safe_str(data.get("id")).strip()
        approval_id = _safe_str(data.get("approval_id")).strip()
        preflight_id = _safe_str(data.get("preflight_id")).strip()
        if not record_id or not approval_id or not preflight_id:
            return None
        status = _safe_str(data.get("status")).strip() or "failed"
        if status not in LAB_APPROVAL_CONSUMPTION_PREFLIGHT_STATUSES:
            status = "failed"
        return cls(
            id=record_id,
            approval_id=approval_id,
            preflight_id=preflight_id,
            plan_id=_safe_str(data.get("plan_id")).strip(),
            workspace_id=_safe_str(data.get("workspace_id")).strip(),
            source_id=_safe_str(data.get("source_id")).strip(),
            candidate_id=_safe_str(data.get("candidate_id")).strip(),
            candidate_name=_safe_str(data.get("candidate_name")).strip(),
            status=status,
            created_at=_safe_str(data.get("created_at")).strip(),
            updated_at=_safe_str(data.get("updated_at")).strip(),
            actor=_safe_str(data.get("actor")).strip() or "francis/system",
            action=_safe_str(data.get("action")).strip() or "francis.lab.execute",
            action_hash=_safe_str(data.get("action_hash")).strip(),
            approval_status=_safe_str(data.get("approval_status")).strip(),
            approval_path=_safe_str(data.get("approval_path")).strip(),
            approval_snapshot=_safe_dict(data.get("approval_snapshot")),
            binding=_safe_dict(data.get("binding")),
            runner_contract_id=_safe_str(data.get("runner_contract_id")).strip(),
            runner_contract=_safe_dict(data.get("runner_contract")),
            blockers=[_safe_str(item).strip() for item in _safe_list(data.get("blockers")) if _safe_str(item).strip()],
            approval_consumed=bool(data.get("approval_consumed", False)),
            execution_authority=bool(data.get("execution_authority", False)),
            executed=bool(data.get("executed", False)),
            receipts=[_safe_str(item).strip() for item in _safe_list(data.get("receipts"))],
        )
