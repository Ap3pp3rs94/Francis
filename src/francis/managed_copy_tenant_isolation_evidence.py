from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir

TENANT_ISOLATION_SOURCE_CONTRACT = "stage18_managed_copy_tenant_isolation_source_v1"
TENANT_ISOLATION_SOURCE_KIND = "francis.stage18.managed_copies.tenant_isolation_source_receipt"
TENANT_ISOLATION_STATE_KIND = "francis.stage18.managed_copies.tenant_isolation_current_state_receipt"
TENANT_ISOLATION_DOMAIN_KIND = "francis.stage18.managed_copies.tenant_isolation_domain_receipt"
TENANT_ISOLATION_SOURCE_MISSING = "stage18_tenant_isolation_runtime_source_receipt_missing"
TENANT_ISOLATION_CONTAINER_SOURCE_MISSING = (
    "stage18_tenant_isolation_runtime_canonical_container_source_verifier_not_implemented"
)
TENANT_ISOLATION_PROOF_KIND = "tenant_isolation_runtime_receipt"
_MAX_STATE_AGE_MS = 30_000
_IDENTIFIER_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-")
_ISOLATION_ASSERTIONS = (
    "tenant_data_isolated",
    "tenant_memory_isolated",
    "tenant_receipts_isolated",
    "tenant_connectors_isolated",
    "tenant_policy_isolated",
    "tenant_support_authority_isolated",
    "cross_tenant_denial_proven",
)
_PROOF_DOMAINS = (
    "provisioning_lineage",
    "structural_isolation",
    "runtime_identity",
    "container_security",
    "tenant_data",
    "tenant_memory",
    "tenant_receipts",
    "tenant_connectors",
    "tenant_policy",
    "tenant_support_authority",
    "cross_tenant_denial",
)
_SOURCE_FIELDS = frozenset(
    {
        "kind",
        "contract",
        "receipt_id",
        "status",
        "evidence_class",
        "tenant_key",
        "copy_id",
        "pilot_run_id",
        "runtime_identity",
        "provisioning_receipt_id",
        "provisioning_receipt_fingerprint",
        "structural_isolation_receipt_id",
        "structural_isolation_receipt_fingerprint",
        "runtime_start_receipt_id",
        "runtime_start_receipt_fingerprint",
        "container_isolation_receipt_id",
        "container_isolation_receipt_fingerprint",
        "operator_approval_receipt_id",
        "operator_approval_receipt_fingerprint",
        "actor_scope_lease_id",
        "actor_scope_lease_fingerprint",
        "tenant_boundary_fingerprint",
        "proof_receipts",
        *_ISOLATION_ASSERTIONS,
        "fixture_only",
        "runtime_gate_ready",
        "current_state_receipt_id",
        "current_state_receipt_fingerprint",
        "trace_id",
        "recorded_at_unix_ms",
        "receipt_fingerprint",
    }
)
_DOMAIN_FIELDS = frozenset(
    {
        "kind",
        "contract",
        "receipt_id",
        "status",
        "proof_domain",
        "tenant_key",
        "copy_id",
        "pilot_run_id",
        "runtime_identity",
        "evidence_class",
        "fixture_only",
        "current",
        "observed_at_unix_ms",
        "expires_at_unix_ms",
        "trace_id",
        "receipt_fingerprint",
    }
)
_STATE_FIELDS = frozenset(
    {
        "kind",
        "contract",
        "receipt_id",
        "status",
        "source_receipt_id",
        "source_lineage_hash",
        "tenant_key",
        "copy_id",
        "pilot_run_id",
        "runtime_identity",
        "runtime_identity_current",
        "source_lineage_current",
        "tenant_boundary_fingerprint",
        *_ISOLATION_ASSERTIONS,
        "fixture_only",
        "observed_at_unix_ms",
        "expires_at_unix_ms",
        "receipt_fingerprint",
    }
)


def tenant_isolation_source_directory() -> Path:
    return data_dir() / "logs" / "managed_copies" / "tenant_isolation_runtime"


def verify_tenant_isolation_runtime_source(
    source_receipt_id: str,
    source_receipt_fingerprint: str,
    *,
    now_ms: int | None = None,
) -> dict[str, Any]:
    """Validate a canonical non-fixture tenant-isolation receipt and current state."""
    if not _identifier(source_receipt_id) or not _is_hash(source_receipt_fingerprint):
        return _blocked("stage18_tenant_isolation_runtime_source_binding_invalid")
    if source_receipt_id.startswith("mclc_"):
        from francis.managed_copy_container_live_evidence import (
            verify_server_resolved_tenant_isolation_source,
        )

        return verify_server_resolved_tenant_isolation_source(
            source_receipt_id,
            source_receipt_fingerprint,
        )
    source = _read_json(tenant_isolation_source_directory() / f"{source_receipt_id}.json")
    if not source:
        return _blocked(TENANT_ISOLATION_SOURCE_MISSING)
    if not _valid_source_receipt(source):
        return _blocked("stage18_tenant_isolation_runtime_source_receipt_invalid")
    if source["receipt_fingerprint"] != source_receipt_fingerprint:
        return _blocked("stage18_tenant_isolation_runtime_source_receipt_hash_mismatch")
    lineage_blocker = _owned_lineage_blocker(source)
    if lineage_blocker:
        return _blocked(lineage_blocker)
    linked = _load_linked_proofs(source, now_ms=now_ms)
    if linked["blocker"]:
        return _blocked(linked["blocker"])

    state_id = source["current_state_receipt_id"]
    state = _read_json(tenant_isolation_source_directory() / "current" / f"{state_id}.json")
    if not _valid_current_state(state):
        return _blocked("stage18_tenant_isolation_runtime_current_state_invalid")
    if state["receipt_fingerprint"] != source["current_state_receipt_fingerprint"]:
        return _blocked("stage18_tenant_isolation_runtime_current_state_hash_mismatch")
    if not _state_matches_source(state, source):
        return _blocked("stage18_tenant_isolation_runtime_current_state_lineage_mismatch")

    observed_at = state["observed_at_unix_ms"]
    expires_at = state["expires_at_unix_ms"]
    current_ms = int(time.time() * 1000) if now_ms is None else now_ms
    if observed_at > current_ms or expires_at <= current_ms or current_ms - observed_at > _MAX_STATE_AGE_MS:
        return _blocked("stage18_tenant_isolation_runtime_current_state_stale")
    return {
        "valid": True,
        "blocker": "",
        "evidence_class": "canonical_runtime",
        "source_lineage_hash": _lineage_hash(source, linked["fingerprints"]),
        "current_state_hash": state["receipt_fingerprint"],
    }


def _valid_source_receipt(receipt: dict[str, Any]) -> bool:
    if set(receipt) != _SOURCE_FIELDS:
        return False
    if (
        receipt.get("kind") != TENANT_ISOLATION_SOURCE_KIND
        or receipt.get("contract") != TENANT_ISOLATION_SOURCE_CONTRACT
        or receipt.get("status") != "ready"
        or receipt.get("evidence_class") != "canonical_runtime"
        or receipt.get("fixture_only") is not False
        or receipt.get("runtime_gate_ready") is not True
        or type(receipt.get("recorded_at_unix_ms")) is not int
    ):
        return False
    if any(receipt.get(field) is not True for field in _ISOLATION_ASSERTIONS):
        return False
    if any(not _identifier(receipt.get(field)) for field in _source_identifier_fields()):
        return False
    if any(not _is_hash(receipt.get(field)) for field in _source_hash_fields()):
        return False
    proof_receipts = receipt.get("proof_receipts")
    if not isinstance(proof_receipts, dict) or tuple(proof_receipts) != _PROOF_DOMAINS:
        return False
    if any(
        not isinstance(binding, dict)
        or set(binding) != {"receipt_id", "receipt_fingerprint"}
        or not _identifier(binding.get("receipt_id"))
        or not _is_hash(binding.get("receipt_fingerprint"))
        for binding in proof_receipts.values()
    ):
        return False
    return receipt["receipt_fingerprint"] == _fingerprint_without(receipt, "receipt_fingerprint")


def _valid_current_state(state: dict[str, Any]) -> bool:
    if set(state) != _STATE_FIELDS:
        return False
    if (
        state.get("kind") != TENANT_ISOLATION_STATE_KIND
        or state.get("contract") != TENANT_ISOLATION_SOURCE_CONTRACT
        or state.get("status") != "ready"
        or state.get("runtime_identity_current") is not True
        or state.get("source_lineage_current") is not True
        or state.get("fixture_only") is not False
        or type(state.get("observed_at_unix_ms")) is not int
        or type(state.get("expires_at_unix_ms")) is not int
    ):
        return False
    if any(state.get(field) is not True for field in _ISOLATION_ASSERTIONS):
        return False
    if any(not _identifier(state.get(field)) for field in _state_identifier_fields()):
        return False
    if any(not _is_hash(state.get(field)) for field in ("source_lineage_hash", "tenant_boundary_fingerprint")):
        return False
    return state["receipt_fingerprint"] == _fingerprint_without(state, "receipt_fingerprint")


def _state_matches_source(state: dict[str, Any], source: dict[str, Any]) -> bool:
    return (
        all(
            state[field] == source[field]
            for field in ("tenant_key", "copy_id", "pilot_run_id", "runtime_identity", "tenant_boundary_fingerprint")
        )
        and state["source_receipt_id"] == source["receipt_id"]
        and state["source_lineage_hash"] == _lineage_hash(source)
    )


def _lineage_hash(source: dict[str, Any], proof_fingerprints: dict[str, str] | None = None) -> str:
    fields = (
        "tenant_key",
        "copy_id",
        "pilot_run_id",
        "runtime_identity",
        "provisioning_receipt_id",
        "provisioning_receipt_fingerprint",
        "structural_isolation_receipt_id",
        "structural_isolation_receipt_fingerprint",
        "runtime_start_receipt_id",
        "runtime_start_receipt_fingerprint",
        "container_isolation_receipt_id",
        "container_isolation_receipt_fingerprint",
        "operator_approval_receipt_id",
        "operator_approval_receipt_fingerprint",
        "actor_scope_lease_id",
        "actor_scope_lease_fingerprint",
        "tenant_boundary_fingerprint",
    )
    binding: dict[str, Any] = {field: source[field] for field in fields}
    binding["proof_fingerprints"] = proof_fingerprints or {
        domain: source["proof_receipts"][domain]["receipt_fingerprint"] for domain in _PROOF_DOMAINS
    }
    return _fingerprint(binding)


def _load_linked_proofs(source: dict[str, Any], *, now_ms: int | None) -> dict[str, Any]:
    current_ms = int(time.time() * 1000) if now_ms is None else now_ms
    fingerprints: dict[str, str] = {}
    for domain in _PROOF_DOMAINS:
        binding = source["proof_receipts"][domain]
        receipt = _read_json(tenant_isolation_source_directory() / "proofs" / f"{binding['receipt_id']}.json")
        if not _valid_domain_receipt(receipt, domain=domain, source=source, current_ms=current_ms):
            return {"blocker": f"stage18_tenant_isolation_runtime_{domain}_proof_invalid", "fingerprints": {}}
        if receipt["receipt_fingerprint"] != binding["receipt_fingerprint"]:
            return {"blocker": f"stage18_tenant_isolation_runtime_{domain}_proof_hash_mismatch", "fingerprints": {}}
        fingerprints[domain] = receipt["receipt_fingerprint"]
    return {"blocker": "", "fingerprints": fingerprints}


def _owned_lineage_blocker(source: dict[str, Any]) -> str:
    from francis.managed_copy_isolation import latest_managed_copy_isolation_verification_for_provision
    from francis.managed_copy_pilot_runtime import verify_pilot_runtime_authority_lineage
    from francis.managed_copy_provisioning import managed_copy_provision_for_copy

    provision = managed_copy_provision_for_copy(
        source["copy_id"], provisioning_receipt_id=source["provisioning_receipt_id"]
    )
    if (
        not provision
        or provision.get("tenant_key") != source["tenant_key"]
        or provision.get("provision_fingerprint") != source["provisioning_receipt_fingerprint"]
    ):
        return "stage18_tenant_isolation_runtime_provisioning_lineage_invalid"
    isolation = latest_managed_copy_isolation_verification_for_provision(
        source["provisioning_receipt_id"],
        provision_fingerprint=source["provisioning_receipt_fingerprint"],
        copy_id=source["copy_id"],
    )
    if (
        not isolation
        or isolation.get("receipt_id") != source["structural_isolation_receipt_id"]
        or isolation.get("verification_fingerprint") != source["structural_isolation_receipt_fingerprint"]
        or isolation.get("live_state_aligned") is not True
    ):
        return "stage18_tenant_isolation_runtime_structural_lineage_invalid"
    runtime = verify_pilot_runtime_authority_lineage(
        source["runtime_start_receipt_id"], source["runtime_start_receipt_fingerprint"]
    )
    if runtime.get("valid") is not True or runtime.get("evidence_class") != "canonical_runtime":
        return "stage18_tenant_isolation_runtime_canonical_runtime_source_invalid"
    authority_lineage = runtime.get("authority_lineage")
    if not isinstance(authority_lineage, dict) or any(
        authority_lineage.get(field) != source[field]
        for field in (
            "tenant_key",
            "copy_id",
            "pilot_run_id",
            "runtime_identity",
            "runtime_start_receipt_id",
            "runtime_start_receipt_fingerprint",
            "operator_approval_receipt_id",
            "operator_approval_receipt_fingerprint",
            "actor_scope_lease_id",
            "actor_scope_lease_fingerprint",
        )
    ):
        return "stage18_tenant_isolation_runtime_pilot_authority_lineage_invalid"
    # The existing Docker receipt is fixture evidence and the proof container is
    # removed before control returns. No current canonical container verifier
    # exists that can independently prove this source binding.
    return TENANT_ISOLATION_CONTAINER_SOURCE_MISSING


def _valid_domain_receipt(receipt: dict[str, Any], *, domain: str, source: dict[str, Any], current_ms: int) -> bool:
    if set(receipt) != _DOMAIN_FIELDS:
        return False
    if (
        receipt.get("kind") != TENANT_ISOLATION_DOMAIN_KIND
        or receipt.get("contract") != TENANT_ISOLATION_SOURCE_CONTRACT
        or receipt.get("status") != "ready"
        or receipt.get("proof_domain") != domain
        or receipt.get("evidence_class") != "canonical_runtime"
        or receipt.get("fixture_only") is not False
        or receipt.get("current") is not True
        or type(receipt.get("observed_at_unix_ms")) is not int
        or type(receipt.get("expires_at_unix_ms")) is not int
    ):
        return False
    if any(
        receipt.get(field) != source[field]
        for field in ("tenant_key", "copy_id", "pilot_run_id", "runtime_identity", "trace_id")
    ):
        return False
    if any(not _identifier(receipt.get(field)) for field in ("receipt_id", "proof_domain", "trace_id")):
        return False
    observed_at = receipt["observed_at_unix_ms"]
    if (
        observed_at > current_ms
        or receipt["expires_at_unix_ms"] <= current_ms
        or current_ms - observed_at > _MAX_STATE_AGE_MS
    ):
        return False
    return _is_hash(receipt.get("receipt_fingerprint")) and receipt["receipt_fingerprint"] == _fingerprint_without(
        receipt, "receipt_fingerprint"
    )


def _source_identifier_fields() -> tuple[str, ...]:
    return (
        "receipt_id",
        "tenant_key",
        "copy_id",
        "pilot_run_id",
        "runtime_identity",
        "provisioning_receipt_id",
        "structural_isolation_receipt_id",
        "runtime_start_receipt_id",
        "container_isolation_receipt_id",
        "operator_approval_receipt_id",
        "actor_scope_lease_id",
        "current_state_receipt_id",
        "trace_id",
    )


def _source_hash_fields() -> tuple[str, ...]:
    return (
        "provisioning_receipt_fingerprint",
        "structural_isolation_receipt_fingerprint",
        "runtime_start_receipt_fingerprint",
        "container_isolation_receipt_fingerprint",
        "operator_approval_receipt_fingerprint",
        "actor_scope_lease_fingerprint",
        "tenant_boundary_fingerprint",
        "current_state_receipt_fingerprint",
        "receipt_fingerprint",
    )


def _state_identifier_fields() -> tuple[str, ...]:
    return (
        "receipt_id",
        "source_receipt_id",
        "tenant_key",
        "copy_id",
        "pilot_run_id",
        "runtime_identity",
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _fingerprint_without(value: dict[str, Any], field: str) -> str:
    return _fingerprint({key: item for key, item in value.items() if key != field})


def _fingerprint(value: dict[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _identifier(value: Any) -> str:
    if type(value) is not str:
        return ""
    text = value.strip()
    if not text or len(text) > 240 or any(char not in _IDENTIFIER_CHARS for char in text):
        return ""
    return text if redact_secret_text(text) == text else ""


def _is_hash(value: Any) -> bool:
    return type(value) is str and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _blocked(blocker: str) -> dict[str, Any]:
    return {
        "valid": False,
        "blocker": blocker,
        "evidence_class": "",
        "source_lineage_hash": "",
        "current_state_hash": "",
    }
