from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from francis import managed_copy_container_isolation as isolation
from francis.managed_copy_pilot_runtime import pilot_runtime_lease_authority_snapshot

LIFECYCLE_EVENT_PREFIX = "mclc_"
_BASE_RECEIPT_FIELDS = {
    "kind",
    "contract",
    "receipt_id",
    "event",
    "actor",
    "approval_id",
    "runtime_start_approval_id",
    "descriptor_fingerprint",
    "tenant_key",
    "copy_id",
    "proof_run_id",
    "lease_id",
    "trace_id",
    "recorded_at_unix_ms",
    "receipt_fingerprint",
}
_CLEANUP_FIELDS = _BASE_RECEIPT_FIELDS | {
    "container_id",
    "container_name",
    "status",
    "post_removal_inspect_absent",
    "post_removal_inspect_exit_code",
}
_READY_FIELDS = _BASE_RECEIPT_FIELDS | {
    "container_id",
    "container_name",
    "image_id",
    "image_platform_digest",
    "mount_set_fingerprint",
    "security_profile_fingerprint",
    "handshake_fingerprint",
    "heartbeat_fingerprint",
    "operation",
    "operation_receipt_fingerprint",
    "output_fingerprint",
    "controller_verifier_fingerprint",
    "container_host_pid",
    "runtime_namespace_pid",
    "runtime_namespace_parent_pid",
    "bounded_cross_tenant_mount_denial",
    "cross_tenant_production_isolation_proven",
    "fixture_only",
    "evidence_class",
    "runtime_gate_ready",
    "stage18_ready",
}
_TENANT_BOUNDARY_READY_FIELDS = _READY_FIELDS | {
    "tenant_boundary_probe_contract",
    "tenant_boundary_probe_id",
    "approved_tenant_input_read",
    "approved_tenant_input_fingerprint",
    "sibling_boundary_id",
    "sibling_tenant_boundary_absent",
    "tenant_boundary_probe_output_fingerprint",
    "comprehensive_tenant_isolation_proven",
}
_LIFECYCLE_FIELDS = _BASE_RECEIPT_FIELDS | {
    "ready_receipt_id",
    "ready_receipt_fingerprint",
    "cleanup_receipt_id",
    "cleanup_receipt_fingerprint",
    "output_fingerprint",
    "isolation_approval_fingerprint",
    "authority_snapshot_fingerprint",
    "authority_actor_id",
    "authority_lease_id",
    "authority_package_id",
    "authority_package_fingerprint",
    "authority_pilot_run_id",
    "authority_operator_decision_fingerprint",
    "authority_lease_fingerprint",
    "terminal_state",
    "post_removal_inspect_absent",
    "fixture_only",
    "evidence_class",
}


def live_container_source_verifier(
    *,
    plan: dict[str, Any],
    proof_root: Path,
    operation_input: object,
    run: isolation.DockerRunner,
    expected_authority: dict[str, Any],
    authority_locked: bool = False,
) -> Callable[[str, str], dict[str, Any]]:
    descriptor = plan["descriptor"]
    ready_path = proof_root / "receipts" / "ready.json"
    state = proof_root / "state"
    source_snapshot = isolation._mount_source_snapshot(proof_root, descriptor=descriptor)

    def verify(source_receipt_id: str, source_receipt_fingerprint: str) -> dict[str, Any]:
        if isolation._file_sha256(isolation.LIVE_EVIDENCE_VERIFIER) != descriptor["live_evidence_verifier_fingerprint"]:
            return _blocked("stage18_copy_creation_live_verifier_changed")
        ready = isolation._read_json(ready_path)
        if (
            ready.get("receipt_id") != source_receipt_id
            or ready.get("receipt_fingerprint") != source_receipt_fingerprint
            or ready.get("event") != "ready"
            or ready.get("fixture_only") is not False
        ):
            return _blocked("stage18_copy_creation_live_receipt_invalid")
        container_id = isolation._container_id(str(ready.get("container_id", "")))
        inspected = isolation._inspect(run, container_id)
        blocker = isolation._inspect_blocker(
            inspected,
            descriptor,
            name=str(ready.get("container_name", "")),
            root=proof_root,
            require_running=True,
        )
        if blocker:
            return _blocked("stage18_copy_creation_live_container_invalid")
        if isolation._container_host_pid(inspected) != ready.get("container_host_pid"):
            return _blocked("stage18_copy_creation_live_process_changed")
        if isolation._mount_source_snapshot(proof_root, descriptor=descriptor) != source_snapshot:
            return _blocked("stage18_copy_creation_live_mount_changed")
        records = {
            name: isolation._read_json(state / f"{name}.json")
            for name in ("handshake", "heartbeat", "operation", isolation._runtime_output_name(descriptor))
        }
        if isolation._runtime_records_blocker(records, descriptor, operation_input=operation_input):
            return _blocked("stage18_copy_creation_live_runtime_invalid")
        output = isolation._runtime_output(records, descriptor)
        if (
            isolation._fingerprint(records["handshake"]) != ready.get("handshake_fingerprint")
            or isolation._fingerprint(records["heartbeat"]) != ready.get("heartbeat_fingerprint")
            or records["operation"].get("receipt_fingerprint") != ready.get("operation_receipt_fingerprint")
            or output.get("output_fingerprint") != ready.get("output_fingerprint")
        ):
            return _blocked("stage18_copy_creation_live_output_changed")
        if not _owned_lineage_valid(plan, expected_authority, authority_locked=authority_locked):
            return _blocked("stage18_copy_creation_live_authority_invalid")
        current = {
            "inspect": isolation._fingerprint(inspected.stdout),
            "records": isolation._fingerprint(records),
            "output": isolation._fingerprint(output),
            "authority": expected_authority["sequence_prefix_fingerprints"],
        }
        return {
            "valid": True,
            "blocker": "",
            "source_lineage_hash": isolation._fingerprint(
                {
                    "descriptor": plan["descriptor_fingerprint"],
                    "ready": source_receipt_fingerprint,
                    "provision": descriptor["provision_fingerprint"],
                    "isolation": descriptor["isolation_verification_fingerprint"],
                    "runtime_approval": descriptor["runtime_start_approval_fingerprint"],
                }
            ),
            "current_state_hash": isolation._fingerprint(current),
            "evidence_class": "canonical_runtime",
        }

    return verify


def write_lifecycle_complete_receipt(
    *,
    plan: dict[str, Any],
    proof_root: Path,
    ready: dict[str, Any],
    cleanup: dict[str, Any],
    output: dict[str, Any],
    authority: dict[str, Any],
) -> dict[str, Any]:
    if (
        cleanup.get("status") != "removed"
        or cleanup.get("post_removal_inspect_absent") is not True
        or authority.get("valid") is not True
        or authority.get("operation_consumed_binding_count") != 2
    ):
        return {}
    receipt = isolation._receipt(
        plan,
        "lifecycle_complete",
        {
            "ready_receipt_id": ready.get("receipt_id"),
            "ready_receipt_fingerprint": ready.get("receipt_fingerprint"),
            "cleanup_receipt_id": cleanup.get("receipt_id"),
            "cleanup_receipt_fingerprint": cleanup.get("receipt_fingerprint"),
            "output_fingerprint": output.get("output_fingerprint"),
            "isolation_approval_fingerprint": isolation._fingerprint(isolation._approval(plan["approval_id"])),
            "authority_snapshot_fingerprint": isolation._fingerprint(authority),
            "authority_actor_id": authority.get("actor_id"),
            "authority_lease_id": authority.get("lease_id"),
            "authority_package_id": authority.get("package_id"),
            "authority_package_fingerprint": authority.get("package_fingerprint"),
            "authority_pilot_run_id": authority.get("pilot_run_id"),
            "authority_operator_decision_fingerprint": authority.get("operator_decision_fingerprint"),
            "authority_lease_fingerprint": authority.get("lease_authority_fingerprint"),
            "terminal_state": "removed",
            "post_removal_inspect_absent": True,
            "fixture_only": False,
            "evidence_class": "canonical_creation_lifecycle_event",
        },
    )
    receipt["receipt_id"] = _lifecycle_id(receipt)
    receipt["receipt_fingerprint"] = isolation._fingerprint(
        {key: value for key, value in receipt.items() if key != "receipt_fingerprint"}
    )
    try:
        isolation._write_immutable(proof_root / "receipts" / "lifecycle-complete.json", receipt)
    except (OSError, FileExistsError):
        return {}
    return receipt


def historical_lifecycle_source_verifier(
    *,
    plan: dict[str, Any],
    proof_root: Path,
    expected_authority: dict[str, Any],
) -> Callable[[str, str], dict[str, Any]]:
    def verify(source_receipt_id: str, source_receipt_fingerprint: str) -> dict[str, Any]:
        return _verify_historical_lifecycle(
            source_receipt_id,
            source_receipt_fingerprint,
            plan=plan,
            proof_root=proof_root,
            expected_authority=expected_authority,
        )

    return verify


def verify_server_resolved_lifecycle_source(
    source_receipt_id: str,
    source_receipt_fingerprint: str,
) -> dict[str, Any]:
    matches: list[tuple[Path, dict[str, Any]]] = []
    base = isolation._proof_base()
    if not base.exists() or not isolation._safe_existing_chain(base):
        return _blocked("stage18_copy_creation_live_proof_root_missing")
    for lifecycle_path in sorted(base.glob("*/receipts/lifecycle-complete.json")):
        lifecycle = isolation._read_json(lifecycle_path)
        if lifecycle.get("receipt_id") == source_receipt_id:
            matches.append((lifecycle_path.parent.parent, lifecycle))
    if len(matches) != 1:
        return _blocked("stage18_copy_creation_live_receipt_not_unique")
    proof_root, lifecycle = matches[0]
    if (
        proof_root.parent.resolve() != base.resolve()
        or not isolation._safe_existing_chain(proof_root)
        or lifecycle.get("receipt_fingerprint") != source_receipt_fingerprint
        or lifecycle.get("proof_run_id") != proof_root.name
    ):
        return _blocked("stage18_copy_creation_lifecycle_receipt_invalid")
    approval = isolation._approval(str(lifecycle.get("approval_id", "")))
    payload = approval.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    descriptor = payload.get("descriptor")
    descriptor = descriptor if isinstance(descriptor, dict) else {}
    descriptor_fingerprint = isolation._fingerprint(descriptor) if descriptor else ""
    if (
        descriptor_fingerprint != lifecycle.get("descriptor_fingerprint")
        or descriptor_fingerprint != payload.get("descriptor_fingerprint")
        or descriptor.get("proof_run_id") != proof_root.name
    ):
        return _blocked("stage18_copy_creation_live_descriptor_invalid")
    approval_payload = approval.get("payload")
    approval_payload = approval_payload if isinstance(approval_payload, dict) else {}
    if (
        isolation._fingerprint(approval) != lifecycle.get("isolation_approval_fingerprint")
        or approval.get("action") != isolation.CONTAINER_ISOLATION_ACTION
        or approval.get("status") != "approved"
        or approval.get("decision") != "approve"
        or approval_payload.get("revoked") is not False
        or approval_payload.get("descriptor") != descriptor
        or approval_payload.get("descriptor_fingerprint") != descriptor_fingerprint
    ):
        return _blocked("stage18_copy_creation_live_approval_invalid")
    authority = _authority_from_lifecycle(lifecycle)
    plan = {
        "actor": lifecycle.get("actor"),
        "approval_id": lifecycle.get("approval_id"),
        "descriptor": descriptor,
        "descriptor_fingerprint": descriptor_fingerprint,
    }
    return _verify_historical_lifecycle(
        source_receipt_id,
        source_receipt_fingerprint,
        plan=plan,
        proof_root=proof_root,
        expected_authority=authority,
    )


def _verify_historical_lifecycle(
    source_receipt_id: str,
    source_receipt_fingerprint: str,
    *,
    plan: dict[str, Any],
    proof_root: Path,
    expected_authority: dict[str, Any],
) -> dict[str, Any]:
    lifecycle = isolation._read_json(proof_root / "receipts" / "lifecycle-complete.json")
    ready = isolation._read_json(proof_root / "receipts" / "ready.json")
    cleanup = isolation._read_json(proof_root / "receipts" / "cleanup.json")
    descriptor = plan["descriptor"]
    expected_ready_fields = (
        _TENANT_BOUNDARY_READY_FIELDS
        if descriptor.get("operation") == isolation.TENANT_BOUNDARY_OPERATION
        else _READY_FIELDS
    )
    if (
        set(lifecycle) != _LIFECYCLE_FIELDS
        or set(cleanup) != _CLEANUP_FIELDS
        or set(ready) != expected_ready_fields
        or not _valid_fingerprint(lifecycle)
        or lifecycle.get("receipt_id") != _lifecycle_id(lifecycle)
        or not _valid_fingerprint(cleanup)
        or not _valid_fingerprint(ready)
        or lifecycle.get("receipt_id") != source_receipt_id
        or lifecycle.get("receipt_fingerprint") != source_receipt_fingerprint
        or lifecycle.get("ready_receipt_id") != ready.get("receipt_id")
        or lifecycle.get("ready_receipt_fingerprint") != ready.get("receipt_fingerprint")
        or lifecycle.get("cleanup_receipt_id") != cleanup.get("receipt_id")
        or lifecycle.get("cleanup_receipt_fingerprint") != cleanup.get("receipt_fingerprint")
        or lifecycle.get("output_fingerprint") != ready.get("output_fingerprint")
        or cleanup.get("container_id") != ready.get("container_id")
        or cleanup.get("container_name") != ready.get("container_name")
        or lifecycle.get("descriptor_fingerprint") != plan["descriptor_fingerprint"]
        or ready.get("event") != "ready"
        or ready.get("kind") != "francis.stage18.managed_copies.container_isolation_ready_receipt"
        or ready.get("contract") != isolation.CONTAINER_ISOLATION_CONTRACT
        or ready.get("descriptor_fingerprint") != plan["descriptor_fingerprint"]
        or ready.get("operation") != descriptor["operation"]
        or cleanup.get("status") != "removed"
        or cleanup.get("post_removal_inspect_absent") is not True
        or cleanup.get("post_removal_inspect_exit_code") == 0
        or lifecycle.get("terminal_state") != "removed"
        or lifecycle.get("post_removal_inspect_absent") is not True
        or lifecycle.get("fixture_only") is not False
        or ready.get("fixture_only") is not False
        or lifecycle.get("evidence_class") != "canonical_creation_lifecycle_event"
        or not isolation._hash(lifecycle.get("isolation_approval_fingerprint"))
        or not isolation._hash(lifecycle.get("authority_snapshot_fingerprint"))
        or (
            expected_authority.get("_historical") is not True
            and lifecycle.get("authority_snapshot_fingerprint") != isolation._fingerprint(expected_authority)
        )
        or lifecycle.get("authority_lease_fingerprint") != expected_authority.get("lease_authority_fingerprint")
        or lifecycle.get("authority_actor_id") != plan["actor"]
        or lifecycle.get("authority_lease_id") != descriptor["lease_id"]
        or lifecycle.get("authority_pilot_run_id") != descriptor["proof_run_id"]
        or not isolation._identifier(lifecycle.get("authority_package_id"))
        or not isolation._hash(lifecycle.get("authority_package_fingerprint"))
        or not isolation._hash(lifecycle.get("authority_operator_decision_fingerprint"))
        or not isolation._hash(lifecycle.get("authority_lease_fingerprint"))
    ):
        return _blocked("stage18_copy_creation_lifecycle_invalid")
    if not _owned_lineage_valid(plan, expected_authority, authority_locked=True):
        return _blocked("stage18_copy_creation_lifecycle_lineage_invalid")
    lineage = {
        "descriptor": plan["descriptor_fingerprint"],
        "ready": ready["receipt_fingerprint"],
        "cleanup": cleanup["receipt_fingerprint"],
        "lifecycle": lifecycle["receipt_fingerprint"],
        "provision": descriptor["provision_fingerprint"],
        "isolation": descriptor["isolation_verification_fingerprint"],
        "runtime_approval": descriptor["runtime_start_approval_fingerprint"],
        "authority": lifecycle["authority_snapshot_fingerprint"],
    }
    terminal = {
        "container_id": cleanup["container_id"],
        "terminal_state": "removed",
        "post_removal_inspect_absent": True,
        "cleanup_receipt_fingerprint": cleanup["receipt_fingerprint"],
    }
    return {
        "valid": True,
        "blocker": "",
        "source_lineage_hash": isolation._fingerprint(lineage),
        "current_state_hash": isolation._fingerprint(terminal),
        "evidence_class": "canonical_runtime",
    }


def _authority_from_lifecycle(lifecycle: dict[str, Any]) -> dict[str, Any]:
    return {
        "valid": True,
        "actor_id": lifecycle.get("authority_actor_id"),
        "lease_id": lifecycle.get("authority_lease_id"),
        "package_id": lifecycle.get("authority_package_id"),
        "package_fingerprint": lifecycle.get("authority_package_fingerprint"),
        "pilot_run_id": lifecycle.get("authority_pilot_run_id"),
        "operator_decision_fingerprint": lifecycle.get("authority_operator_decision_fingerprint"),
        "lease_authority_fingerprint": lifecycle.get("authority_lease_fingerprint"),
        "operation_consumed_binding_count": 2,
        "sequence_prefix_fingerprints": [],
        "_historical": True,
    }


def _valid_fingerprint(receipt: dict[str, Any]) -> bool:
    fingerprint = receipt.get("receipt_fingerprint")
    return bool(
        isinstance(fingerprint, str)
        and fingerprint
        == isolation._fingerprint({key: value for key, value in receipt.items() if key != "receipt_fingerprint"})
    )


def _lifecycle_id(receipt: dict[str, Any]) -> str:
    identity = {
        key: value
        for key, value in receipt.items()
        if key not in {"receipt_id", "receipt_fingerprint", "recorded_at_unix_ms"}
    }
    return f"{LIFECYCLE_EVENT_PREFIX}{isolation._fingerprint(identity)[:24]}"


def _owned_lineage_valid(
    plan: dict[str, Any],
    expected_authority: dict[str, Any],
    *,
    authority_locked: bool,
) -> bool:
    descriptor = plan["descriptor"]
    provision = isolation.managed_copy_provision_for_copy(
        descriptor["copy_id"],
        provisioning_receipt_id=descriptor["provisioning_receipt_id"],
    )
    verification = isolation.latest_managed_copy_isolation_verification_for_provision(
        descriptor["provisioning_receipt_id"],
        provision_fingerprint=descriptor["provision_fingerprint"],
        copy_id=descriptor["copy_id"],
    )
    if expected_authority.get("_historical") is True:
        runtime_approval_valid = (
            isolation._fingerprint(isolation._approval(descriptor["runtime_start_approval_id"]))
            == descriptor["runtime_start_approval_fingerprint"]
        )
    else:
        runtime_approval = isolation.validate_runtime_start_approval_reference(
            descriptor["runtime_start_approval_id"],
            actor=plan["actor"],
            copy_id=descriptor["copy_id"],
            provisioning_receipt_id=descriptor["provisioning_receipt_id"],
            provision_fingerprint=descriptor["provision_fingerprint"],
            isolation_verification_receipt_id=descriptor["isolation_verification_receipt_id"],
            isolation_verification_fingerprint=descriptor["isolation_verification_fingerprint"],
        )
        runtime_approval_valid = runtime_approval.get("valid") is True
    authority = expected_authority
    if not authority_locked:
        authority = pilot_runtime_lease_authority_snapshot(
            descriptor["lease_id"],
            actor=plan["actor"],
            expected_bindings=isolation.container_isolation_lease_bindings(),
        )
    return bool(
        provision.get("provision_fingerprint") == descriptor["provision_fingerprint"]
        and verification.get("receipt_id") == descriptor["isolation_verification_receipt_id"]
        and verification.get("live_state_aligned") is True
        and runtime_approval_valid
        and authority.get("valid") is True
        and authority.get("sequence_prefix_fingerprints") == expected_authority.get("sequence_prefix_fingerprints")
        and authority.get("operation_consumed_binding_count") in {1, 2}
    )


def _blocked(blocker: str) -> dict[str, Any]:
    return {
        "valid": False,
        "blocker": blocker,
        "source_lineage_hash": "",
        "current_state_hash": "",
        "evidence_class": "",
    }
