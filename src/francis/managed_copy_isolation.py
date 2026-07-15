from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir
from francis.managed_copy_provisioning import managed_copy_provision_for_copy
from francis.telemetry.audit import record as audit_record

MANAGED_COPY_ISOLATION_VERIFICATION_CONTRACT = "stage18_managed_copy_structural_isolation_verification_v1"
MANAGED_COPY_ISOLATION_VERIFICATION_RECEIPT_KIND = (
    "francis.stage18.managed_copies.structural_isolation_verification_receipt"
)
MANAGED_COPY_ISOLATION_VERIFICATION_RECEIPTS_KIND = (
    "francis.stage18.managed_copies.structural_isolation_verification_receipts"
)

_REQUEST_MAPPING_FIELDS = (
    "tenant_identity",
    "tenant_policy",
    "isolation_profile",
    "capability_lineage",
    "safe_delta_policy",
    "support_boundary",
    "decommission_policy",
)
_ISOLATION_LAYOUT = {
    "tenant_data": "data",
    "tenant_memory": "memory",
    "tenant_receipts": "receipts",
    "tenant_connectors": "connectors",
    "tenant_capability_packs": "capability_packs",
    "tenant_policy": "policy",
    "support_operator_authority": "support",
}
_ARTIFACT_CHECK_IDS = (
    "tenant_root_canonical",
    "tenant_root_not_linked",
    "tenant_layout_exact",
    "tenant_configuration_identity_aligned",
    "tenant_configuration_fingerprint_aligned",
    "tenant_configuration_fields_aligned",
    "tenant_manifest_identity_aligned",
    "tenant_manifest_lineage_aligned",
    "provisioning_receipt_aligned",
    "approval_consumption_aligned",
    "registry_aligned",
    "copy_identity_unique",
    "tenant_key_unique",
)
_VERIFICATION_LOCK = threading.Lock()


def managed_copy_isolation_verification_plan(
    payload: dict[str, Any],
    *,
    actor: str,
    provision_receipt: dict[str, Any],
) -> dict[str, Any]:
    safe_actor = _redacted_text(actor)[:240]
    provided_copy_id = _safe_text(payload.get("copy_id"))
    provided_receipt_id = _safe_text(payload.get("provisioning_receipt_id"))
    copy_id = _safe_text(provision_receipt.get("copy_id"))
    tenant_key = _safe_text(provision_receipt.get("tenant_key"))
    provisioning_receipt_id = _safe_text(provision_receipt.get("receipt_id"))
    raw_domains = payload.get("domains")
    domain_values = raw_domains if isinstance(raw_domains, list) else []
    requested_domains = sorted({_safe_text(domain) for domain in domain_values if _safe_text(domain)})
    required_domains = list(_ISOLATION_LAYOUT)
    missing_domains = sorted(set(required_domains).difference(requested_domains))
    unknown_domains = sorted(set(requested_domains).difference(required_domains))
    domain_checks, artifact_checks = _live_structural_checks(provision_receipt)

    blockers: list[str] = []
    if not safe_actor:
        blockers.append("isolation_verification_actor_missing")
    if not provided_copy_id:
        blockers.append("copy_id_missing")
    if not provided_receipt_id:
        blockers.append("copy_provision_receipt_id_missing")
    if not provision_receipt:
        blockers.append("copy_provision_receipt_missing_or_mismatch")
    if copy_id and provided_copy_id != copy_id:
        blockers.append("copy_id_mismatch")
    if provisioning_receipt_id and provided_receipt_id != provisioning_receipt_id:
        blockers.append("copy_provision_receipt_id_mismatch")
    blockers.extend(f"{domain}_verification_not_requested" for domain in missing_domains)
    blockers.extend(f"unknown_isolation_domain:{domain}" for domain in unknown_domains)
    blockers.extend(
        _safe_text(check.get("blocker")) for check in [*domain_checks, *artifact_checks] if not check.get("ready")
    )
    blockers = [blocker for blocker in blockers if blocker]

    verification_fingerprint = (
        _verification_fingerprint(
            actor=safe_actor,
            copy_id=copy_id,
            tenant_key=tenant_key,
            provisioning_receipt_id=provisioning_receipt_id,
            provision_fingerprint=_safe_text(provision_receipt.get("provision_fingerprint")),
            requested_domains=requested_domains,
            domain_checks=domain_checks,
            artifact_checks=artifact_checks,
        )
        if not blockers
        else ""
    )
    existing_receipt = _read_json(_verification_receipt_path(tenant_key)) if tenant_key else {}
    existing_matches = bool(
        existing_receipt
        and _valid_verification_receipt(existing_receipt)
        and _safe_text(existing_receipt.get("verification_fingerprint")) == verification_fingerprint
    )
    if existing_receipt and not existing_matches and not blockers:
        blockers.append("isolation_verification_receipt_conflict")
        verification_fingerprint = ""

    structural_ready = not blockers
    return {
        "ok": structural_ready,
        "kind": "francis.stage18.managed_copies.structural_isolation_verification_plan",
        "contract": MANAGED_COPY_ISOLATION_VERIFICATION_CONTRACT,
        "status": "structural_isolation_verification_ready" if structural_ready else "blocked",
        "actor": safe_actor,
        "copy_id": copy_id,
        "tenant_key": tenant_key,
        "provisioning_receipt_id": provisioning_receipt_id,
        "provision_fingerprint": _safe_text(provision_receipt.get("provision_fingerprint")),
        "state_root": _safe_text(provision_receipt.get("state_root")),
        "requested_domains": requested_domains,
        "required_domains": required_domains,
        "missing_domains": missing_domains,
        "unknown_domains": unknown_domains,
        "domain_checks": domain_checks,
        "artifact_checks": artifact_checks,
        "verified_domain_count": sum(1 for check in domain_checks if check.get("ready")),
        "required_domain_count": len(required_domains),
        "verified_artifact_count": sum(1 for check in artifact_checks if check.get("ready")),
        "required_artifact_count": len(_ARTIFACT_CHECK_IDS),
        "structural_isolation_ready": structural_ready,
        "structural_isolation_verified": False,
        "filesystem_acl_isolation_verified": False,
        "runtime_access_boundary_verified": False,
        "cross_tenant_denial_executed": False,
        "full_customer_isolation_verified": False,
        "blockers": blockers,
        "verification_fingerprint": verification_fingerprint,
        "existing_verification_matches": existing_matches,
        "dry_run_confirmation": {
            "required_for_recording": True,
            "fingerprint": verification_fingerprint,
            "fingerprint_contract": MANAGED_COPY_ISOLATION_VERIFICATION_CONTRACT,
        },
        "writes_receipt": False,
        "writes_tenant_state": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def record_managed_copy_isolation_verification(
    plan: dict[str, Any],
    *,
    provision_receipt: dict[str, Any],
    provided_fingerprint: str,
    confirm_verification: bool,
) -> dict[str, Any]:
    expected_fingerprint = _safe_text(plan.get("verification_fingerprint"))
    if not plan.get("structural_isolation_ready"):
        return _blocked("blocked_isolation_verification_contract", "isolation_verification_contract_not_ready")
    if not confirm_verification:
        return _blocked("blocked_isolation_verification_confirmation", "isolation_verification_confirmation_required")
    if not expected_fingerprint or _safe_text(provided_fingerprint) != expected_fingerprint:
        return _blocked(
            "blocked_isolation_verification_dry_run_confirmation",
            "isolation_verification_fingerprint_mismatch",
        )

    tenant_key = _safe_text(plan.get("tenant_key"))
    receipt_path = _verification_receipt_path(tenant_key)
    with _VERIFICATION_LOCK:
        current_domain_checks, current_artifact_checks = _live_structural_checks(provision_receipt)
        current_fingerprint = _verification_fingerprint(
            actor=_safe_text(plan.get("actor")),
            copy_id=_safe_text(plan.get("copy_id")),
            tenant_key=tenant_key,
            provisioning_receipt_id=_safe_text(plan.get("provisioning_receipt_id")),
            provision_fingerprint=_safe_text(plan.get("provision_fingerprint")),
            requested_domains=list(plan.get("requested_domains") or []),
            domain_checks=current_domain_checks,
            artifact_checks=current_artifact_checks,
        )
        if (
            not all(check.get("ready") for check in [*current_domain_checks, *current_artifact_checks])
            or current_fingerprint != expected_fingerprint
        ):
            return _blocked(
                "blocked_isolation_verification_state_drift",
                "isolation_state_changed_since_dry_run",
            )

        existing = _read_json(receipt_path)
        if existing:
            if (
                _valid_verification_receipt(existing)
                and _safe_text(existing.get("verification_fingerprint")) == expected_fingerprint
            ):
                return _recorded_result(existing, status="already_verified", writes_receipt=False)
            return _blocked(
                "blocked_isolation_verification_receipt_conflict",
                "isolation_verification_receipt_conflict",
            )

        recorded_ts = int(time.time())
        receipt = {
            "ok": True,
            "kind": MANAGED_COPY_ISOLATION_VERIFICATION_RECEIPT_KIND,
            "contract": MANAGED_COPY_ISOLATION_VERIFICATION_CONTRACT,
            "receipt_id": f"managed_copy_isolation_{expected_fingerprint[:16]}",
            "status": "structural_isolation_verified",
            "actor": _safe_text(plan.get("actor")),
            "copy_id": _safe_text(plan.get("copy_id")),
            "tenant_key": tenant_key,
            "provisioning_receipt_id": _safe_text(plan.get("provisioning_receipt_id")),
            "provision_fingerprint": _safe_text(plan.get("provision_fingerprint")),
            "state_root": _safe_text(plan.get("state_root")),
            "requested_domains": list(plan.get("requested_domains") or []),
            "domain_checks": current_domain_checks,
            "artifact_checks": current_artifact_checks,
            "verified_domain_count": len(current_domain_checks),
            "required_domain_count": len(_ISOLATION_LAYOUT),
            "verified_artifact_count": len(current_artifact_checks),
            "required_artifact_count": len(_ARTIFACT_CHECK_IDS),
            "structural_isolation_verified": True,
            "filesystem_acl_isolation_verified": False,
            "runtime_access_boundary_verified": False,
            "cross_tenant_denial_executed": False,
            "full_customer_isolation_verified": False,
            "verification_fingerprint": expected_fingerprint,
            "recorded_ts": recorded_ts,
            "governance": {
                "copy_provision_receipt_required": True,
                "copy_provision_receipt_aligned": True,
                "tenant_root_derived_from_tenant_key": True,
                "tenant_local_receipt_only": True,
                "raw_tenant_payload_returned": False,
                "filesystem_acl_isolation_claimed": False,
                "runtime_access_boundary_claimed": False,
                "cross_tenant_denial_claimed": False,
                "starts_runtime": False,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
        }
        if not _valid_verification_receipt(receipt):
            return _blocked("failed_isolation_verification_receipt", "isolation_verification_receipt_invalid")
        try:
            _write_json_atomic(receipt_path, receipt)
        except OSError:
            return _blocked("failed_isolation_verification_write", "isolation_verification_receipt_write_failed")

    audit_record(
        "managed_copies.structural_isolation_verified",
        actor=_safe_text(plan.get("actor")),
        copy_id=_safe_text(plan.get("copy_id")),
        tenant_key=tenant_key,
        provisioning_receipt_id=_safe_text(plan.get("provisioning_receipt_id")),
        verification_fingerprint=expected_fingerprint,
    )
    return _recorded_result(receipt, status="structural_isolation_verified", writes_receipt=True)


def managed_copy_isolation_verification_receipts_readback(*, limit: int = 20) -> dict[str, Any]:
    items = sorted(
        (
            item
            for path in _tenant_roots_path().glob("*/receipts/isolation_verification.json")
            if (item := _read_json(path))
        ),
        key=lambda item: _safe_int(item.get("recorded_ts")),
        reverse=True,
    )
    valid_items = [item for item in items if _valid_verification_receipt(item)]
    live_items = [_with_live_alignment(item) for item in valid_items]
    aligned_items = [item for item in live_items if item.get("live_state_aligned")]
    latest = items[0] if items else {}
    latest_valid = live_items[0] if live_items else {}
    safe_limit = _safe_limit(limit)
    return {
        "ok": True,
        "kind": MANAGED_COPY_ISOLATION_VERIFICATION_RECEIPTS_KIND,
        "status": "ready" if aligned_items else "drift_detected" if valid_items else "empty",
        "items": live_items[:safe_limit],
        "count": len(items),
        "valid_count": len(valid_items),
        "live_aligned_count": len(aligned_items),
        "latest_receipt": latest,
        "latest_receipt_id": _safe_text(latest.get("receipt_id")),
        "latest_receipt_valid": _valid_verification_receipt(latest),
        "latest_valid_receipt": latest_valid,
        "latest_valid_receipt_id": _safe_text(latest_valid.get("receipt_id")),
        "structural_isolation_verified": bool(aligned_items),
        "full_customer_isolation_verified": False,
        "reads_tenant_receipts": True,
        "writes_receipts": False,
        "writes_tenant_state": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "next_smallest_truthful_gap": (
            "stage18_copy_isolation_runtime_access_boundary"
            if aligned_items
            else "stage18_copy_isolation_reverification"
            if valid_items
            else "stage18_copy_isolation_verification"
        ),
    }


def latest_managed_copy_isolation_verification_for_provision(
    provisioning_receipt_id: str,
    *,
    provision_fingerprint: str = "",
    copy_id: str = "",
) -> dict[str, Any]:
    expected_receipt_id = _safe_text(provisioning_receipt_id)
    expected_provision_fingerprint = _safe_text(provision_fingerprint)
    expected_copy_id = _safe_text(copy_id)
    if not expected_receipt_id or not expected_copy_id:
        return {}
    provision_receipt = managed_copy_provision_for_copy(
        expected_copy_id,
        provisioning_receipt_id=expected_receipt_id,
    )
    tenant_key = _safe_text(provision_receipt.get("tenant_key"))
    item = _read_json(_verification_receipt_path(tenant_key)) if tenant_key else {}
    if (
        not _valid_verification_receipt(item)
        or _safe_text(item.get("provisioning_receipt_id")) != expected_receipt_id
        or (
            expected_provision_fingerprint
            and _safe_text(item.get("provision_fingerprint")) != expected_provision_fingerprint
        )
        or _safe_text(item.get("copy_id")) != expected_copy_id
    ):
        return {}
    return _with_live_alignment(item, provision_receipt=provision_receipt)


def managed_copy_isolation_guarded_subpath(
    provision_receipt: dict[str, Any],
    isolation_receipt: dict[str, Any],
    *,
    domain: str,
    relative_parts: tuple[str, ...] = (),
    create_leaf_directory: bool = False,
    require_live: bool = True,
) -> Path | None:
    """Return a contained, non-linked tenant subpath owned by structural isolation."""
    relative_name = _ISOLATION_LAYOUT.get(domain)
    tenant_key = _safe_text(provision_receipt.get("tenant_key"))
    copy_id = _safe_text(provision_receipt.get("copy_id"))
    provisioning_receipt_id = _safe_text(provision_receipt.get("receipt_id"))
    expected_state_root = f"managed_copies/tenants/{tenant_key}" if _is_sha256(tenant_key) else ""
    if (
        relative_name is None
        or not expected_state_root
        or _safe_text(provision_receipt.get("state_root")) != expected_state_root
        or _safe_text(isolation_receipt.get("copy_id")) != copy_id
        or _safe_text(isolation_receipt.get("tenant_key")) != tenant_key
        or _safe_text(isolation_receipt.get("provisioning_receipt_id")) != provisioning_receipt_id
        or _safe_text(isolation_receipt.get("state_root")) != expected_state_root
        or (require_live and isolation_receipt.get("live_state_aligned") is not True)
        or (create_leaf_directory and not relative_parts)
        or any(
            not isinstance(part, str)
            or not part
            or part in {".", ".."}
            or "/" in part
            or "\\" in part
            or Path(part).is_absolute()
            or Path(part).name != part
            for part in relative_parts
        )
    ):
        return None

    tenant_roots_path = _tenant_roots_path()
    tenant_root = _tenant_root(tenant_key)
    domain_path = tenant_root / relative_name
    if (
        not tenant_roots_path.is_dir()
        or _is_link_like(tenant_roots_path)
        or not _resolved_within(tenant_roots_path, data_dir())
        or not tenant_root.is_dir()
        or _is_link_like(tenant_root)
        or not _resolved_within(tenant_root, tenant_roots_path)
        or not domain_path.is_dir()
        or _is_link_like(domain_path)
        or not _resolved_within(domain_path, tenant_root)
    ):
        return None

    guarded_path = domain_path
    for index, part in enumerate(relative_parts):
        guarded_path = guarded_path / part
        leaf = index == len(relative_parts) - 1
        if _is_link_like(guarded_path):
            return None
        if not guarded_path.exists():
            if create_leaf_directory and leaf:
                try:
                    guarded_path.mkdir()
                except FileExistsError:
                    pass
                except OSError:
                    return None
            elif leaf:
                return guarded_path
            else:
                return None
        if (
            _is_link_like(guarded_path)
            or not _resolved_within(guarded_path, domain_path)
            or (not leaf and not guarded_path.is_dir())
            or (create_leaf_directory and leaf and not guarded_path.is_dir())
        ):
            return None
    return guarded_path


def managed_copy_isolation_integrity_checks(
    provision_receipt: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Evaluate the existing structural isolation checks without planning or writing."""
    domain_checks, artifact_checks = _live_structural_checks(provision_receipt)
    return ([dict(item) for item in domain_checks], [dict(item) for item in artifact_checks])


def _live_structural_checks(
    provision_receipt: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tenant_key = _safe_text(provision_receipt.get("tenant_key"))
    copy_id = _safe_text(provision_receipt.get("copy_id"))
    state_root = _safe_text(provision_receipt.get("state_root"))
    expected_state_root = f"managed_copies/tenants/{tenant_key}" if tenant_key else ""
    tenant_root = _tenant_root(tenant_key)
    tenant_roots_path = _tenant_roots_path()
    isolation_paths = _mapping(provision_receipt.get("isolation_paths"))
    root_exists = tenant_root.is_dir()
    root_linked = _is_link_like(tenant_root) if tenant_root.exists() else False
    tenant_roots_boundary_ready = bool(
        tenant_roots_path.is_dir()
        and not _is_link_like(tenant_roots_path)
        and _resolved_within(tenant_roots_path, data_dir())
    )
    root_contained = _resolved_within(tenant_root, tenant_roots_path) if root_exists else False

    domain_checks: list[dict[str, Any]] = []
    for domain, relative_name in _ISOLATION_LAYOUT.items():
        domain_path = tenant_root / relative_name
        expected_relative_path = f"{expected_state_root}/{relative_name}" if expected_state_root else ""
        declared_path = _safe_text(isolation_paths.get(domain))
        exists = domain_path.is_dir()
        linked = _is_link_like(domain_path) if domain_path.exists() else False
        contained = _resolved_within(domain_path, tenant_root) if exists else False
        ready = bool(
            root_exists
            and tenant_roots_boundary_ready
            and root_contained
            and state_root == expected_state_root
            and declared_path == expected_relative_path
            and exists
            and not linked
            and contained
        )
        blocker = ""
        if state_root != expected_state_root or declared_path != expected_relative_path:
            blocker = f"{domain}_path_contract_mismatch"
        elif not exists:
            blocker = f"{domain}_directory_missing"
        elif linked:
            blocker = f"{domain}_link_boundary_not_allowed"
        elif not contained:
            blocker = f"{domain}_path_escapes_tenant_root"
        elif not root_exists or not tenant_roots_boundary_ready or not root_contained:
            blocker = "tenant_root_invalid"
        domain_checks.append(
            {
                "id": domain,
                "ready": ready,
                "status": "verified" if ready else "blocked",
                "relative_path": expected_relative_path,
                "path_declared": declared_path == expected_relative_path,
                "directory_present": exists,
                "link_like": linked,
                "contained_in_tenant_root": contained,
                "blocker": blocker,
            }
        )

    config_path = tenant_root / "config" / "managed_copy.json"
    manifest_path = tenant_root / "manifest.json"
    provisioning_path = tenant_root / "receipts" / "provisioning.json"
    consumption_path = tenant_root / "receipts" / "approval_consumption.json"
    config = _read_json(config_path)
    manifest = _read_json(manifest_path)
    disk_provision = _read_json(provisioning_path)
    consumption = _read_json(consumption_path)
    expected_top_level = {*_ISOLATION_LAYOUT.values(), "config", "manifest.json"}
    actual_top_level = {path.name for path in tenant_root.iterdir()} if root_exists else set()
    config_identity_ready = bool(
        config
        and config_path.is_file()
        and not _is_link_like(config_path.parent)
        and not _is_link_like(config_path)
        and _resolved_within(config_path, tenant_root)
        and _safe_text(config.get("copy_id")) == copy_id
        and _safe_text(config.get("tenant_key")) == tenant_key
        and _safe_text(config.get("contract")) == "stage18_managed_copy_configuration_v1"
    )
    config_fingerprint_ready = bool(
        config and _fingerprint(config) == _safe_text(provision_receipt.get("config_fingerprint"))
    )
    field_fingerprints = _mapping(provision_receipt.get("request_field_fingerprints"))
    config_fields_ready = bool(
        config
        and all(
            _fingerprint(_mapping(config.get(field))) == _safe_text(field_fingerprints.get(field))
            for field in _REQUEST_MAPPING_FIELDS
        )
    )
    manifest_identity_ready = bool(
        manifest
        and manifest_path.is_file()
        and not _is_link_like(manifest_path)
        and _resolved_within(manifest_path, tenant_root)
        and _safe_text(manifest.get("copy_id")) == copy_id
        and _safe_text(manifest.get("tenant_key")) == tenant_key
        and _safe_text(manifest.get("state_root")) == expected_state_root
    )
    manifest_lineage_ready = bool(
        manifest
        and _safe_text(manifest.get("provisioning_receipt_id")) == _safe_text(provision_receipt.get("receipt_id"))
        and _safe_text(manifest.get("plan_receipt_id")) == _safe_text(provision_receipt.get("plan_receipt_id"))
        and _safe_text(manifest.get("approval_id")) == _safe_text(provision_receipt.get("approval_id"))
        and _safe_text(manifest.get("config_fingerprint")) == _safe_text(provision_receipt.get("config_fingerprint"))
        and bool(manifest.get("registry_written"))
    )
    provisioning_ready = bool(
        disk_provision
        and provisioning_path.is_file()
        and not _is_link_like(provisioning_path)
        and _resolved_within(provisioning_path, tenant_root)
        and _safe_text(disk_provision.get("receipt_id")) == _safe_text(provision_receipt.get("receipt_id"))
        and _safe_text(disk_provision.get("provision_fingerprint"))
        == _safe_text(provision_receipt.get("provision_fingerprint"))
        and bool(disk_provision.get("registry_written"))
    )
    consumption_ready = bool(
        consumption
        and consumption_path.is_file()
        and not _is_link_like(consumption_path)
        and _resolved_within(consumption_path, tenant_root)
        and _safe_text(consumption.get("approval_id")) == _safe_text(provision_receipt.get("approval_id"))
        and _safe_text(consumption.get("provisioning_receipt_id")) == _safe_text(provision_receipt.get("receipt_id"))
        and bool(consumption.get("approval_consumed"))
        and bool(consumption.get("single_use_enforced"))
    )
    copy_match_count, tenant_match_count = _identity_match_counts(copy_id=copy_id, tenant_key=tenant_key)
    artifact_checks = [
        _artifact_check(
            "tenant_root_canonical",
            bool(root_exists and tenant_roots_boundary_ready and root_contained and state_root == expected_state_root),
            "tenant_root_not_canonical",
        ),
        _artifact_check(
            "tenant_root_not_linked",
            bool(root_exists and not root_linked),
            "tenant_root_link_boundary_not_allowed",
        ),
        _artifact_check(
            "tenant_layout_exact",
            bool(root_exists and actual_top_level == expected_top_level),
            "tenant_root_layout_mismatch",
        ),
        _artifact_check(
            "tenant_configuration_identity_aligned",
            config_identity_ready,
            "tenant_configuration_identity_mismatch",
        ),
        _artifact_check(
            "tenant_configuration_fingerprint_aligned",
            config_fingerprint_ready,
            "tenant_configuration_fingerprint_mismatch",
        ),
        _artifact_check(
            "tenant_configuration_fields_aligned",
            config_fields_ready,
            "tenant_configuration_field_fingerprint_mismatch",
        ),
        _artifact_check(
            "tenant_manifest_identity_aligned",
            manifest_identity_ready,
            "tenant_manifest_identity_mismatch",
        ),
        _artifact_check(
            "tenant_manifest_lineage_aligned",
            manifest_lineage_ready,
            "tenant_manifest_lineage_mismatch",
        ),
        _artifact_check(
            "provisioning_receipt_aligned",
            provisioning_ready,
            "tenant_provisioning_receipt_mismatch",
        ),
        _artifact_check(
            "approval_consumption_aligned",
            consumption_ready,
            "tenant_approval_consumption_mismatch",
        ),
        _artifact_check(
            "registry_aligned",
            bool(provision_receipt.get("registry_aligned") and provision_receipt.get("provision_complete")),
            "managed_copy_registry_mismatch",
        ),
        _artifact_check(
            "copy_identity_unique",
            copy_match_count == 1,
            "copy_identity_not_unique",
        ),
        _artifact_check(
            "tenant_key_unique",
            tenant_match_count == 1,
            "tenant_key_not_unique",
        ),
    ]
    return domain_checks, artifact_checks


def _with_live_alignment(
    item: dict[str, Any],
    *,
    provision_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provision = provision_receipt or managed_copy_provision_for_copy(
        _safe_text(item.get("copy_id")),
        provisioning_receipt_id=_safe_text(item.get("provisioning_receipt_id")),
    )
    domain_checks, artifact_checks = _live_structural_checks(provision)
    blockers = [
        _safe_text(check.get("blocker"))
        for check in [*domain_checks, *artifact_checks]
        if not check.get("ready") and _safe_text(check.get("blocker"))
    ]
    current_fingerprint = _verification_fingerprint(
        actor=_safe_text(item.get("actor")),
        copy_id=_safe_text(item.get("copy_id")),
        tenant_key=_safe_text(item.get("tenant_key")),
        provisioning_receipt_id=_safe_text(item.get("provisioning_receipt_id")),
        provision_fingerprint=_safe_text(item.get("provision_fingerprint")),
        requested_domains=list(item.get("requested_domains") or []),
        domain_checks=domain_checks,
        artifact_checks=artifact_checks,
    )
    live_aligned = bool(
        provision and not blockers and current_fingerprint == _safe_text(item.get("verification_fingerprint"))
    )
    return {
        **item,
        "live_state_aligned": live_aligned,
        "live_drift_detected": bool(item and not live_aligned),
        "live_blockers": blockers,
    }


def _valid_verification_receipt(item: dict[str, Any]) -> bool:
    governance = _mapping(item.get("governance"))
    domain_checks = item.get("domain_checks")
    artifact_checks = item.get("artifact_checks")
    expected_fingerprint = _verification_fingerprint(
        actor=_safe_text(item.get("actor")),
        copy_id=_safe_text(item.get("copy_id")),
        tenant_key=_safe_text(item.get("tenant_key")),
        provisioning_receipt_id=_safe_text(item.get("provisioning_receipt_id")),
        provision_fingerprint=_safe_text(item.get("provision_fingerprint")),
        requested_domains=list(item.get("requested_domains") or []),
        domain_checks=domain_checks if isinstance(domain_checks, list) else [],
        artifact_checks=artifact_checks if isinstance(artifact_checks, list) else [],
    )
    return (
        _safe_text(item.get("kind")) == MANAGED_COPY_ISOLATION_VERIFICATION_RECEIPT_KIND
        and _safe_text(item.get("contract")) == MANAGED_COPY_ISOLATION_VERIFICATION_CONTRACT
        and _safe_text(item.get("receipt_id")).startswith("managed_copy_isolation_")
        and _safe_text(item.get("status")) == "structural_isolation_verified"
        and bool(_safe_text(item.get("actor")))
        and _safe_text(item.get("copy_id")).startswith("managed_copy_")
        and _is_sha256(item.get("tenant_key"))
        and _safe_text(item.get("provisioning_receipt_id")).startswith("managed_copy_provision_")
        and _is_sha256(item.get("provision_fingerprint"))
        and _safe_text(item.get("state_root")) == f"managed_copies/tenants/{_safe_text(item.get('tenant_key'))}"
        and set(item.get("requested_domains") or []) == set(_ISOLATION_LAYOUT)
        and _valid_domain_checks(domain_checks)
        and _valid_artifact_checks(artifact_checks)
        and _safe_int(item.get("verified_domain_count")) == len(_ISOLATION_LAYOUT)
        and _safe_int(item.get("required_domain_count")) == len(_ISOLATION_LAYOUT)
        and _safe_int(item.get("verified_artifact_count")) == len(_ARTIFACT_CHECK_IDS)
        and _safe_int(item.get("required_artifact_count")) == len(_ARTIFACT_CHECK_IDS)
        and bool(item.get("structural_isolation_verified"))
        and not bool(item.get("filesystem_acl_isolation_verified"))
        and not bool(item.get("runtime_access_boundary_verified"))
        and not bool(item.get("cross_tenant_denial_executed"))
        and not bool(item.get("full_customer_isolation_verified"))
        and _is_sha256(item.get("verification_fingerprint"))
        and _safe_text(item.get("verification_fingerprint")) == expected_fingerprint
        and _safe_int(item.get("recorded_ts")) > 0
        and bool(governance.get("copy_provision_receipt_required"))
        and bool(governance.get("copy_provision_receipt_aligned"))
        and bool(governance.get("tenant_root_derived_from_tenant_key"))
        and bool(governance.get("tenant_local_receipt_only"))
        and not bool(governance.get("raw_tenant_payload_returned"))
        and not bool(governance.get("filesystem_acl_isolation_claimed"))
        and not bool(governance.get("runtime_access_boundary_claimed"))
        and not bool(governance.get("cross_tenant_denial_claimed"))
        and not bool(governance.get("starts_runtime"))
        and not bool(governance.get("grants_execution_authority"))
        and not bool(governance.get("grants_mutation_authority"))
    )


def _valid_domain_checks(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != len(_ISOLATION_LAYOUT):
        return False
    return all(
        isinstance(item, dict)
        and _safe_text(item.get("id")) == expected_id
        and item.get("ready") is True
        and _safe_text(item.get("status")) == "verified"
        and not _safe_text(item.get("blocker"))
        for item, expected_id in zip(value, _ISOLATION_LAYOUT, strict=True)
    )


def _valid_artifact_checks(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != len(_ARTIFACT_CHECK_IDS):
        return False
    return all(
        isinstance(item, dict)
        and _safe_text(item.get("id")) == expected_id
        and item.get("ready") is True
        and _safe_text(item.get("status")) == "verified"
        and not _safe_text(item.get("blocker"))
        for item, expected_id in zip(value, _ARTIFACT_CHECK_IDS, strict=True)
    )


def _artifact_check(check_id: str, ready: bool, blocker: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "ready": ready,
        "status": "verified" if ready else "blocked",
        "blocker": "" if ready else blocker,
    }


def _identity_match_counts(*, copy_id: str, tenant_key: str) -> tuple[int, int]:
    copy_match_count = 0
    tenant_match_count = 0
    for path in _tenant_roots_path().glob("*/manifest.json"):
        manifest = _read_json(path)
        if _safe_text(manifest.get("copy_id")) == copy_id:
            copy_match_count += 1
        if _safe_text(manifest.get("tenant_key")) == tenant_key:
            tenant_match_count += 1
    return copy_match_count, tenant_match_count


def _verification_fingerprint(
    *,
    actor: str,
    copy_id: str,
    tenant_key: str,
    provisioning_receipt_id: str,
    provision_fingerprint: str,
    requested_domains: list[Any],
    domain_checks: list[dict[str, Any]],
    artifact_checks: list[dict[str, Any]],
) -> str:
    return _fingerprint(
        {
            "contract": MANAGED_COPY_ISOLATION_VERIFICATION_CONTRACT,
            "actor": actor,
            "copy_id": copy_id,
            "tenant_key": tenant_key,
            "provisioning_receipt_id": provisioning_receipt_id,
            "provision_fingerprint": provision_fingerprint,
            "requested_domains": requested_domains,
            "domain_checks": domain_checks,
            "artifact_checks": artifact_checks,
        }
    )


def _recorded_result(receipt: dict[str, Any], *, status: str, writes_receipt: bool) -> dict[str, Any]:
    return {
        "ok": True,
        "status": status,
        "error": "",
        "receipt": receipt,
        "receipt_id": _safe_text(receipt.get("receipt_id")),
        "structural_isolation_verified": True,
        "full_customer_isolation_verified": False,
        "writes_receipt": writes_receipt,
        "writes_tenant_state": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def _blocked(status: str, error: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": status,
        "error": error,
        "receipt": None,
        "receipt_id": "",
        "structural_isolation_verified": False,
        "full_customer_isolation_verified": False,
        "writes_receipt": False,
        "writes_tenant_state": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def _tenant_roots_path() -> Path:
    return data_dir() / "managed_copies" / "tenants"


def _tenant_root(tenant_key: str) -> Path:
    return _tenant_roots_path() / tenant_key


def _verification_receipt_path(tenant_key: str) -> Path:
    return _tenant_root(tenant_key) / "receipts" / "isolation_verification.json"


def _resolved_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return False
    return True


def _is_link_like(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction and is_junction())


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".iv-{uuid.uuid4().hex[:8]}.tmp")
    try:
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _is_sha256(value: Any) -> bool:
    text = _safe_text(value)
    return len(text) == 64 and all(character in "0123456789abcdef" for character in text)


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_limit(value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 20
    return min(max(parsed, 1), 500)


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _redacted_text(value: Any) -> str:
    return redact_secret_text(_safe_text(value))
