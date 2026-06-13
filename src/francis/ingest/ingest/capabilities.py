from __future__ import annotations

import hashlib
from typing import Any

from ..shared.models import CapabilityCandidate, RepoMap, SourcePermissionProfile


def _candidate_id(source_id: str, name: str) -> str:
    digest = hashlib.sha256(f"{source_id}:{name}".encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"cap_{digest}"


def _signal_ids(repo_map: RepoMap) -> set[str]:
    return {item.id for item in repo_map.risk_signals}


def _risk_level(repo_map: RepoMap, *, base: str = "low") -> str:
    ids = _signal_ids(repo_map)
    if "destructive_command_hint" in ids or "credential_like_file_present" in ids:
        return "high"
    if "package_postinstall_script" in ids or "package_preinstall_script" in ids:
        return "high"
    if "deploy_script_present" in ids:
        return "high"
    if ids & {
        "env_file_present",
        "dockerfile_present",
        "compose_file_present",
        "ci_workflow_present",
        "shell_script_present",
        "network_command_hint",
        "migration_script_present",
    }:
        return "medium" if base == "low" else base
    return base


def _read_permissions() -> SourcePermissionProfile:
    return SourcePermissionProfile(read=True, execute=False, network=False, write=False, destructive=False)


def _execute_permissions(
    *, write: bool = False, network: bool = False, destructive: bool = False
) -> SourcePermissionProfile:
    return SourcePermissionProfile(read=True, execute=True, network=network, write=write, destructive=destructive)


def _evidence(kind: str, values: list[str] | dict[str, Any], detail: str = "") -> list[dict[str, Any]]:
    if isinstance(values, dict):
        return [{"kind": kind, "path": path, "detail": detail or str(value)} for path, value in values.items()]
    return [{"kind": kind, "path": value, "detail": detail} for value in values]


def _candidate(
    *,
    repo_map: RepoMap,
    name: str,
    status: str,
    description: str,
    evidence: list[dict[str, Any]],
    permissions_required: SourcePermissionProfile,
    risk_level: str,
    suggested_validation: list[str] | None = None,
    inferred_inputs: list[str] | None = None,
    inferred_outputs: list[str] | None = None,
    promotion_requirements: list[str] | None = None,
) -> CapabilityCandidate:
    return CapabilityCandidate(
        id=_candidate_id(repo_map.source_id, name),
        name=name,
        source_id=repo_map.source_id,
        source_type="repo",
        status=status,
        description=description,
        evidence=evidence,
        inferred_inputs=inferred_inputs or ["repo_map"],
        inferred_outputs=inferred_outputs or ["structured_readback"],
        permissions_required=permissions_required,
        risk_level=risk_level,
        suggested_validation=suggested_validation or [],
        promotion_requirements=promotion_requirements
        or [
            "operator_review",
            "receipts_linked_to_source_record",
            "remain_non_executing_until_Francis_Lab_boundary_exists",
        ],
    )


class CapabilityCandidateExtractor:
    def extract(self, repo_map: RepoMap) -> list[CapabilityCandidate]:
        candidates: list[CapabilityCandidate] = []
        candidates.append(
            _candidate(
                repo_map=repo_map,
                name="inspect_project_structure",
                status="drafted",
                description="Read-only inspection of repository structure, manifests, docs, tests, and risk signals.",
                evidence=_evidence("repo_map", ["repo_map"], "repo map created"),
                permissions_required=_read_permissions(),
                risk_level="low",
                promotion_requirements=["source_map_exists", "operator_review", "no_execution_required"],
            )
        )

        if repo_map.docs_readmes or repo_map.source_directories:
            candidates.append(
                _candidate(
                    repo_map=repo_map,
                    name="explain_repo_architecture",
                    status="drafted",
                    description="Use the repo map, docs, manifests, and source-directory layout to explain architecture.",
                    evidence=_evidence("docs_or_source_dirs", repo_map.docs_readmes + repo_map.source_directories),
                    permissions_required=_read_permissions(),
                    risk_level="low",
                    inferred_outputs=["architecture_summary"],
                    promotion_requirements=["source_map_exists", "doc_summary_generated", "operator_review"],
                )
            )

        validation_commands = [
            item["command"] for item in repo_map.suggested_validation_commands if item.get("command")
        ]
        test_commands = [
            item["command"]
            for item in repo_map.suggested_validation_commands
            if item.get("command") and "test" in str(item.get("command")).lower()
        ]
        if repo_map.test_files or test_commands:
            candidates.append(
                _candidate(
                    repo_map=repo_map,
                    name="run_project_tests",
                    status="discovered",
                    description="Potential test-running capability discovered from test files or declared test commands.",
                    evidence=_evidence("tests", repo_map.test_files[:20])
                    + _evidence("validation_commands", test_commands),
                    permissions_required=_execute_permissions(),
                    risk_level=_risk_level(repo_map, base="medium"),
                    suggested_validation=test_commands,
                    inferred_outputs=["test_receipt", "test_result_summary"],
                    promotion_requirements=[
                        "explicit_operator_permission",
                        "Francis_Lab_network_blocked",
                        "Francis_Lab_filesystem_write_boundary",
                        "execution_receipt_created",
                    ],
                )
            )

        package_scripts = repo_map.script_commands.get("package.json", {})
        if "lint" in package_scripts:
            lint_command = next((item for item in validation_commands if "lint" in item), "npm run lint")
            candidates.append(
                _candidate(
                    repo_map=repo_map,
                    name="lint_project",
                    status="discovered",
                    description="Potential lint capability discovered from package manifest scripts.",
                    evidence=_evidence("manifest_script", {"package.json#lint": package_scripts["lint"]}),
                    permissions_required=_execute_permissions(),
                    risk_level=_risk_level(repo_map, base="medium"),
                    suggested_validation=[lint_command],
                    inferred_outputs=["lint_receipt", "lint_result_summary"],
                    promotion_requirements=[
                        "explicit_operator_permission",
                        "Francis_Lab_execution_boundary",
                        "execution_receipt_created",
                    ],
                )
            )

        if "build" in package_scripts or {"Cargo.toml", "go.mod", "pyproject.toml"} & set(repo_map.manifest_files):
            build_commands = [item for item in validation_commands if "build" in item]
            candidates.append(
                _candidate(
                    repo_map=repo_map,
                    name="build_project",
                    status="discovered",
                    description="Potential build capability discovered from manifests or build scripts.",
                    evidence=_evidence("manifest_files", repo_map.manifest_files)
                    + _evidence("manifest_script", {"package.json#build": package_scripts.get("build", "")}),
                    permissions_required=_execute_permissions(write=True),
                    risk_level=_risk_level(repo_map, base="medium"),
                    suggested_validation=build_commands,
                    inferred_outputs=["build_receipt", "build_artifact_references"],
                    promotion_requirements=[
                        "explicit_operator_permission",
                        "Francis_Lab_sandboxed_workspace",
                        "Francis_Lab_network_policy",
                        "build_receipt_created",
                    ],
                )
            )

        if {"package", "pack", "publish"} & set(package_scripts):
            candidate_scripts = {
                f"package.json#{name}": command
                for name, command in package_scripts.items()
                if name in {"package", "pack", "publish"}
            }
            candidates.append(
                _candidate(
                    repo_map=repo_map,
                    name="package_project",
                    status="discovered",
                    description="Potential package capability discovered from package-related manifest scripts.",
                    evidence=_evidence("manifest_script", candidate_scripts),
                    permissions_required=_execute_permissions(write=True, network="publish" in package_scripts),
                    risk_level="high" if "publish" in package_scripts else _risk_level(repo_map, base="medium"),
                    inferred_outputs=["package_artifact_references", "package_receipt"],
                    promotion_requirements=[
                        "explicit_operator_permission",
                        "Francis_Lab_sandboxed_workspace",
                        "publish_network_denied_unless_separately_approved",
                        "package_receipt_created",
                    ],
                )
            )

        if "dockerfile_present" in _signal_ids(repo_map) or "compose_file_present" in _signal_ids(repo_map):
            candidates.append(
                _candidate(
                    repo_map=repo_map,
                    name="inspect_container_build",
                    status="discovered",
                    description="Read-only container setup inspection; image build remains a future lab operation.",
                    evidence=_evidence(
                        "container_files",
                        [
                            item.path
                            for item in repo_map.risk_signals
                            if item.id in {"dockerfile_present", "compose_file_present"}
                        ],
                    ),
                    permissions_required=_read_permissions(),
                    risk_level="medium",
                    inferred_outputs=["container_setup_summary"],
                    promotion_requirements=[
                        "source_map_exists",
                        "operator_review",
                        "future_build_requires_Francis_Lab",
                    ],
                )
            )

        if "migration_script_present" in _signal_ids(repo_map):
            candidates.append(
                _candidate(
                    repo_map=repo_map,
                    name="inspect_database_migrations",
                    status="discovered",
                    description="Read-only database migration inspection; applying migrations is outside v0.",
                    evidence=_evidence(
                        "migration_paths",
                        [item.path for item in repo_map.risk_signals if item.id == "migration_script_present"],
                    ),
                    permissions_required=_read_permissions(),
                    risk_level="medium",
                    inferred_outputs=["migration_inventory"],
                    promotion_requirements=[
                        "source_map_exists",
                        "operator_review",
                        "future_execution_requires_database_sandbox",
                    ],
                )
            )

        if repo_map.entrypoints:
            candidates.append(
                _candidate(
                    repo_map=repo_map,
                    name="inspect_cli_entrypoint",
                    status="discovered",
                    description="Read-only CLI or package entrypoint inspection.",
                    evidence=repo_map.entrypoints,
                    permissions_required=_read_permissions(),
                    risk_level="low",
                    inferred_outputs=["entrypoint_inventory"],
                    promotion_requirements=["source_map_exists", "operator_review", "no_execution_required"],
                )
            )

        return candidates
