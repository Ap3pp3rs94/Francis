from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from francis import managed_copy_runtime_evidence as runtime_evidence
from francis import managed_copy_tenant_isolation_evidence as isolation_evidence

_NOW = 1_800_000_000_000


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fingerprint(value: dict[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _write_canonical_source(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    source_dir = root / "logs" / "managed_copies" / "tenant_isolation_runtime"
    state_dir = source_dir / "current"
    proof_dir = source_dir / "proofs"
    state_dir.mkdir(parents=True)
    proof_dir.mkdir()
    source_id = "mcti_source_001"
    state_id = "mcti_state_001"
    source: dict[str, Any] = {
        "kind": isolation_evidence.TENANT_ISOLATION_SOURCE_KIND,
        "contract": isolation_evidence.TENANT_ISOLATION_SOURCE_CONTRACT,
        "receipt_id": source_id,
        "status": "ready",
        "evidence_class": "canonical_runtime",
        "tenant_key": "tenant-key-001",
        "copy_id": "managed-copy-001",
        "pilot_run_id": "pilot-run-001",
        "runtime_identity": "managed-copy-runtime-001",
        "provisioning_receipt_id": "provision-001",
        "provisioning_receipt_fingerprint": _hash("provision"),
        "structural_isolation_receipt_id": "isolation-001",
        "structural_isolation_receipt_fingerprint": _hash("isolation"),
        "runtime_start_receipt_id": "runtime-start-001",
        "runtime_start_receipt_fingerprint": _hash("runtime-start"),
        "container_isolation_receipt_id": "container-isolation-001",
        "container_isolation_receipt_fingerprint": _hash("container-isolation"),
        "operator_approval_receipt_id": "operator-approval-001",
        "operator_approval_receipt_fingerprint": _hash("operator-approval"),
        "actor_scope_lease_id": "pilot-lease-001",
        "actor_scope_lease_fingerprint": _hash("pilot-lease"),
        "tenant_boundary_fingerprint": _hash("tenant-boundary"),
        "proof_receipts": {},
        "tenant_data_isolated": True,
        "tenant_memory_isolated": True,
        "tenant_receipts_isolated": True,
        "tenant_connectors_isolated": True,
        "tenant_policy_isolated": True,
        "tenant_support_authority_isolated": True,
        "cross_tenant_denial_proven": True,
        "fixture_only": False,
        "runtime_gate_ready": True,
        "current_state_receipt_id": state_id,
        "current_state_receipt_fingerprint": "",
        "trace_id": "trace-001",
        "recorded_at_unix_ms": _NOW - 1_000,
        "receipt_fingerprint": "",
    }
    state: dict[str, Any] = {
        "kind": isolation_evidence.TENANT_ISOLATION_STATE_KIND,
        "contract": isolation_evidence.TENANT_ISOLATION_SOURCE_CONTRACT,
        "receipt_id": state_id,
        "status": "ready",
        "source_receipt_id": source_id,
        "source_lineage_hash": "",
        "tenant_key": source["tenant_key"],
        "copy_id": source["copy_id"],
        "pilot_run_id": source["pilot_run_id"],
        "runtime_identity": source["runtime_identity"],
        "runtime_identity_current": True,
        "source_lineage_current": True,
        "tenant_boundary_fingerprint": source["tenant_boundary_fingerprint"],
        "tenant_data_isolated": True,
        "tenant_memory_isolated": True,
        "tenant_receipts_isolated": True,
        "tenant_connectors_isolated": True,
        "tenant_policy_isolated": True,
        "tenant_support_authority_isolated": True,
        "cross_tenant_denial_proven": True,
        "fixture_only": False,
        "observed_at_unix_ms": _NOW - 1_000,
        "expires_at_unix_ms": _NOW + 10_000,
        "receipt_fingerprint": "",
    }
    proof_receipts: dict[str, Any] = {}
    for domain in isolation_evidence._PROOF_DOMAINS:
        receipt_id = f"mcti-proof-{domain}"
        proof: dict[str, Any] = {
            "kind": isolation_evidence.TENANT_ISOLATION_DOMAIN_KIND,
            "contract": isolation_evidence.TENANT_ISOLATION_SOURCE_CONTRACT,
            "receipt_id": receipt_id,
            "status": "ready",
            "proof_domain": domain,
            "tenant_key": source["tenant_key"],
            "copy_id": source["copy_id"],
            "pilot_run_id": source["pilot_run_id"],
            "runtime_identity": source["runtime_identity"],
            "evidence_class": "canonical_runtime",
            "fixture_only": False,
            "current": True,
            "observed_at_unix_ms": _NOW - 1_000,
            "expires_at_unix_ms": _NOW + 10_000,
            "trace_id": source["trace_id"],
            "receipt_fingerprint": "",
        }
        proof["receipt_fingerprint"] = _fingerprint(
            {key: value for key, value in proof.items() if key != "receipt_fingerprint"}
        )
        proof_receipts[domain] = {
            "receipt_id": receipt_id,
            "receipt_fingerprint": proof["receipt_fingerprint"],
        }
        (proof_dir / f"{receipt_id}.json").write_text(json.dumps(proof), encoding="utf-8")
    source["proof_receipts"] = proof_receipts
    state["source_lineage_hash"] = isolation_evidence._lineage_hash(source)
    state["receipt_fingerprint"] = _fingerprint(
        {key: value for key, value in state.items() if key != "receipt_fingerprint"}
    )
    source["current_state_receipt_fingerprint"] = state["receipt_fingerprint"]
    source["receipt_fingerprint"] = _fingerprint(
        {key: value for key, value in source.items() if key != "receipt_fingerprint"}
    )
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / f"{source_id}.json").write_text(json.dumps(source), encoding="utf-8")
    (state_dir / f"{state_id}.json").write_text(json.dumps(state), encoding="utf-8")
    return source, state


@pytest.fixture
def isolated_data(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "francis-data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(root))
    return root


def test_missing_canonical_source_fails_without_creating_state(isolated_data: Path) -> None:
    result = isolation_evidence.verify_tenant_isolation_runtime_source("missing-source", _hash("missing"), now_ms=_NOW)

    assert result["valid"] is False
    assert result["blocker"] == isolation_evidence.TENANT_ISOLATION_SOURCE_MISSING
    assert not isolated_data.exists()


def test_self_consistent_source_cannot_replace_owned_provision_lineage(isolated_data: Path) -> None:
    source, _ = _write_canonical_source(isolated_data)

    result = isolation_evidence.verify_tenant_isolation_runtime_source(
        source["receipt_id"], source["receipt_fingerprint"], now_ms=_NOW
    )

    assert result["valid"] is False
    assert result["blocker"] == "stage18_tenant_isolation_runtime_provisioning_lineage_invalid"


def test_linked_domain_proof_is_independently_loaded_and_revalidated(
    isolated_data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, _ = _write_canonical_source(isolated_data)
    monkeypatch.setattr(isolation_evidence, "_owned_lineage_blocker", lambda _: "")
    binding = source["proof_receipts"]["tenant_memory"]
    path = isolation_evidence.tenant_isolation_source_directory() / "proofs" / f"{binding['receipt_id']}.json"
    proof = json.loads(path.read_text(encoding="utf-8"))
    proof["fixture_only"] = True
    proof["receipt_fingerprint"] = _fingerprint(
        {key: value for key, value in proof.items() if key != "receipt_fingerprint"}
    )
    path.write_text(json.dumps(proof), encoding="utf-8")

    result = isolation_evidence.verify_tenant_isolation_runtime_source(
        source["receipt_id"], source["receipt_fingerprint"], now_ms=_NOW
    )

    assert result["valid"] is False
    assert result["blocker"] == "stage18_tenant_isolation_runtime_tenant_memory_proof_invalid"


@pytest.mark.parametrize(
    ("target", "field", "value", "blocker"),
    [
        ("source", "fixture_only", True, "stage18_tenant_isolation_runtime_source_receipt_invalid"),
        ("source", "tenant_memory_isolated", False, "stage18_tenant_isolation_runtime_source_receipt_invalid"),
        ("state", "tenant_connectors_isolated", False, "stage18_tenant_isolation_runtime_current_state_invalid"),
        ("state", "expires_at_unix_ms", _NOW, "stage18_tenant_isolation_runtime_current_state_stale"),
    ],
)
def test_fixture_weaker_and_stale_evidence_fail_closed(
    isolated_data: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
    field: str,
    value: object,
    blocker: str,
) -> None:
    source, state = _write_canonical_source(isolated_data)
    monkeypatch.setattr(isolation_evidence, "_owned_lineage_blocker", lambda _: "")
    item = source if target == "source" else state
    item[field] = value
    item["receipt_fingerprint"] = _fingerprint(
        {key: field_value for key, field_value in item.items() if key != "receipt_fingerprint"}
    )
    path = isolation_evidence.tenant_isolation_source_directory()
    if target == "source":
        source = item
        (path / f"{source['receipt_id']}.json").write_text(json.dumps(source), encoding="utf-8")
    else:
        state = item
        source["current_state_receipt_fingerprint"] = state["receipt_fingerprint"]
        source["receipt_fingerprint"] = _fingerprint(
            {key: field_value for key, field_value in source.items() if key != "receipt_fingerprint"}
        )
        state["source_lineage_hash"] = isolation_evidence._lineage_hash(source)
        state["receipt_fingerprint"] = _fingerprint(
            {key: field_value for key, field_value in state.items() if key != "receipt_fingerprint"}
        )
        source["current_state_receipt_fingerprint"] = state["receipt_fingerprint"]
        source["receipt_fingerprint"] = _fingerprint(
            {key: field_value for key, field_value in source.items() if key != "receipt_fingerprint"}
        )
        (path / f"{source['receipt_id']}.json").write_text(json.dumps(source), encoding="utf-8")
        (path / "current" / f"{state['receipt_id']}.json").write_text(json.dumps(state), encoding="utf-8")

    result = isolation_evidence.verify_tenant_isolation_runtime_source(
        source["receipt_id"], source["receipt_fingerprint"], now_ms=_NOW
    )

    assert result["valid"] is False
    assert result["blocker"] == blocker


def test_runtime_recorder_selects_tenant_isolation_verifier_and_kind(isolated_data: Path) -> None:
    payload = {
        "request_actor": "stage18.test-writer",
        "requirement_id": runtime_evidence.TENANT_ISOLATION_REQUIREMENT,
        "proof_kind": runtime_evidence.TENANT_ISOLATION_PROOF_KIND,
        "source_receipt_id": "tenant-isolation-source",
        "source_receipt_fingerprint": _hash("source"),
        "trace_id": "trace-stage18-tenant-isolation",
        "dry_run": True,
        "record_fingerprint": "",
        "confirm_runtime_evidence": False,
    }
    result = runtime_evidence.plan_runtime_evidence(
        payload,
        actor="stage18.test-writer",
        stage17_closed=True,
    )

    assert result["ok"] is False
    assert result["error"] == isolation_evidence.TENANT_ISOLATION_SOURCE_MISSING
    assert not isolated_data.exists()


def test_tenant_requirement_rejects_copy_creation_proof_kind(isolated_data: Path) -> None:
    payload = {
        "request_actor": "stage18.test-writer",
        "requirement_id": runtime_evidence.TENANT_ISOLATION_REQUIREMENT,
        "proof_kind": runtime_evidence.COPY_CREATION_PROOF_KIND,
        "source_receipt_id": "tenant-isolation-source",
        "source_receipt_fingerprint": _hash("source"),
        "trace_id": "trace-stage18-tenant-isolation",
        "dry_run": True,
        "record_fingerprint": "",
        "confirm_runtime_evidence": False,
    }

    result = runtime_evidence.plan_runtime_evidence(
        payload,
        actor="stage18.test-writer",
        stage17_closed=True,
    )

    assert result["error"] == "stage18_runtime_evidence_proof_kind_mismatch"
    assert not isolated_data.exists()


def test_canonical_tenant_isolation_source_records_one_requirement_receipt(
    isolated_data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, _ = _write_canonical_source(isolated_data)
    monkeypatch.setattr(isolation_evidence, "_owned_lineage_blocker", lambda _: "")

    def verifier(receipt_id: str, fingerprint: str) -> dict[str, Any]:
        return isolation_evidence.verify_tenant_isolation_runtime_source(receipt_id, fingerprint, now_ms=_NOW)

    payload: dict[str, Any] = {
        "request_actor": "stage18.test-writer",
        "requirement_id": runtime_evidence.TENANT_ISOLATION_REQUIREMENT,
        "proof_kind": runtime_evidence.TENANT_ISOLATION_PROOF_KIND,
        "source_receipt_id": source["receipt_id"],
        "source_receipt_fingerprint": source["receipt_fingerprint"],
        "trace_id": "trace-stage18-tenant-isolation",
        "dry_run": True,
        "record_fingerprint": "",
        "confirm_runtime_evidence": False,
    }
    plan = runtime_evidence.plan_runtime_evidence(
        payload,
        actor="stage18.test-writer",
        stage17_closed=True,
        source_verifier=verifier,
    )
    payload.update(
        dry_run=False,
        record_fingerprint=plan["record_fingerprint"],
        confirm_runtime_evidence=True,
    )

    result = runtime_evidence.record_runtime_evidence(
        payload,
        actor="stage18.test-writer",
        stage17_closed=True,
        source_verifier=verifier,
    )

    assert result["status"] == "recorded"
    assert result["receipt_ready"] is False
    assert result["receipt"]["requirement_id"] == runtime_evidence.TENANT_ISOLATION_REQUIREMENT
    assert runtime_evidence.valid_runtime_evidence_receipt(result["receipt"]) is True
    assert runtime_evidence.receipt_satisfies_runtime_requirement(result["receipt"], source_verifier=verifier) is True
