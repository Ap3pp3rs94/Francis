from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from francis import managed_copy_pilot_runtime
from francis import managed_copy_runtime_evidence as runtime_evidence
from francis import managed_copy_safe_delta_runtime_invocation as invocation
from francis.managed_copies import managed_copy_completion_review_snapshot
from francis.api.app import create_app
from francis.governance.pilot_scope_lease import PilotScopeLease, PilotScopeLeaseRegistry


ACTOR = "stage18.safe-delta-invoker"
LEASE_ID = "lease-safe-delta-final-001"
PACKAGE_ID = "package-safe-delta-final-001"
RUN_ID = "run-safe-delta-final-001"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _registry(*, now: list[int] | None = None) -> PilotScopeLeaseRegistry:
    clock = now or [1_000]
    registry = PilotScopeLeaseRegistry(clock_ms=lambda: clock[0])
    registry.issue(
        PilotScopeLease(
            lease_id=LEASE_ID,
            actor_id=ACTOR,
            package_id=PACKAGE_ID,
            package_fingerprint=_hash("package"),
            pilot_run_id=RUN_ID,
            bindings=invocation.lease_bindings(include_runtime_evidence=True),
            issued_at_ms=900,
            expires_at_ms=10_000,
            runtime_nonce="runtime-nonce-safe-delta-final",
            operator_decision_fingerprint=_hash("decision"),
        )
    )
    return registry


def _consume(registry: PilotScopeLeaseRegistry, count: int) -> None:
    for binding in invocation.lease_bindings(include_runtime_evidence=True)[:count]:
        decision = registry.authorize_binding(
            lease_id=LEASE_ID,
            actor_id=ACTOR,
            scope=binding.scope,
            route=binding.route,
            method=binding.method,
            action=binding.action,
        )
        assert decision.allowed is True


def _authority_context(registry: PilotScopeLeaseRegistry, *, required_count: int) -> dict[str, object]:
    authority = managed_copy_pilot_runtime.pilot_runtime_lease_authority_snapshot(
        LEASE_ID,
        actor=ACTOR,
        expected_bindings=invocation.lease_bindings(include_runtime_evidence=True),
    )
    if authority.get("valid") is not True or authority.get("operation_consumed_binding_count") != required_count:
        return {"valid": False, "blocker": "stage18_safe_delta_runtime_source_authority_lineage_invalid"}
    return {
        "valid": True,
        "blocker": "",
        "actor_id": ACTOR,
        "pilot_lease_id": LEASE_ID,
        "package_id": PACKAGE_ID,
        "package_fingerprint": _hash("package"),
        "pilot_run_id": RUN_ID,
        "operator_decision_fingerprint": _hash("decision"),
        "lease_authority_fingerprint": authority["lease_authority_fingerprint"],
    }


def _source(_: str, __: str) -> dict[str, object]:
    return {
        "valid": True,
        "blocker": "",
        "evidence_class": "canonical_runtime",
        "source_lineage_hash": _hash("lineage-final-authority"),
        "current_state_hash": _hash("state-final-authority"),
    }


def _payload(*, dry_run: bool = False) -> dict[str, object]:
    base = {
        "request_actor": ACTOR,
        "requirement_id": runtime_evidence.SAFE_DELTA_REQUIREMENT,
        "proof_kind": runtime_evidence.SAFE_DELTA_PROOF_KIND,
        "source_receipt_id": "safe-delta-runtime-source-final-001",
        "source_receipt_fingerprint": _hash("source"),
        "trace_id": "trace-safe-delta-final-001",
        "dry_run": True,
        "record_fingerprint": "",
        "confirm_runtime_evidence": False,
    }
    plan = runtime_evidence.plan_runtime_evidence(
        base,
        actor=ACTOR,
        stage17_closed=True,
        source_verifier=_source,
    )
    assert plan["ok"] is True
    if not dry_run:
        base.update(
            dry_run=False,
            record_fingerprint=plan["record_fingerprint"],
            confirm_runtime_evidence=True,
        )
    return base


def _install_registry(monkeypatch: pytest.MonkeyPatch, registry: PilotScopeLeaseRegistry) -> None:
    monkeypatch.setattr(managed_copy_pilot_runtime, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr("francis.api.routes.managed_copies.PILOT_RUNTIME_LEASES", registry)


def test_unscoped_safe_delta_denial_precedes_source_read_and_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")
    monkeypatch.setattr(
        "francis.api.routes.managed_copies.safe_delta_runtime_source_authority_context",
        lambda *args, **kwargs: pytest.fail("source authority must not be read"),
    )
    monkeypatch.setattr(
        "francis.api.routes.managed_copies.managed_copy_runtime_evidence_readback_blocked_snapshot",
        lambda *args, **kwargs: pytest.fail("evidence handler must not run"),
    )

    body = TestClient(create_app()).post("/managed-copies/runtime-evidence-readback", json=_payload()).json()

    assert body["error"] == "api_permission_denied"
    assert not tmp_path.joinpath("data").exists()


def test_exact_third_binding_is_consumed_once_and_replay_is_denied(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry = _registry()
    _consume(registry, 2)
    _install_registry(monkeypatch, registry)
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({ACTOR: [invocation.RUNTIME_EVIDENCE_SCOPE]}),
    )
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(
        "francis.api.routes.managed_copies.safe_delta_runtime_source_authority_context",
        lambda *args, **kwargs: _authority_context(registry, required_count=2),
    )
    monkeypatch.setattr(
        "francis.managed_copy_safe_delta_runtime_evidence.safe_delta_runtime_source_authority_context",
        lambda *args, **kwargs: _authority_context(registry, required_count=3),
    )
    monkeypatch.setattr(
        "francis.managed_copy_safe_delta_runtime_evidence.verify_safe_delta_runtime_source_for_final_evidence",
        _source,
    )
    monkeypatch.setattr(
        "francis.managed_copies.managed_copy_runtime_evidence_contract_snapshot",
        lambda: {
            "stage17_closed_by_receipt": True,
            "stage17_blocker": "",
            "requirements": [],
            "routes": {},
            "next_smallest_truthful_gap": "stage18_safe_delta_runtime_proof",
        },
    )
    client = TestClient(create_app())

    first = client.post("/managed-copies/runtime-evidence-readback", json=_payload()).json()
    replay = client.post("/managed-copies/runtime-evidence-readback", json=_payload()).json()

    assert first["status"] == "recorded"
    assert first["writes_receipt"] is True
    assert registry.state(LEASE_ID).value == "consumed"
    assert replay["error"] == "api_permission_denied"
    assert len(list(runtime_evidence.receipt_directory().glob("*.json"))) == 1


@pytest.mark.parametrize("state", ["missing", "revoked", "expired", "wrong_order"])
def test_invalid_final_lease_state_denies_before_evidence_handler(
    monkeypatch: pytest.MonkeyPatch,
    state: str,
) -> None:
    now = [1_000]
    registry = PilotScopeLeaseRegistry() if state == "missing" else _registry(now=now)
    if state in {"revoked", "expired"}:
        _consume(registry, 2)
    if state == "revoked":
        assert registry.revoke(LEASE_ID).allowed is True
    if state == "expired":
        now[0] = 10_000
    if state == "wrong_order":
        _consume(registry, 1)
    _install_registry(monkeypatch, registry)
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({ACTOR: [invocation.RUNTIME_EVIDENCE_SCOPE]}),
    )
    monkeypatch.setattr(
        "francis.api.routes.managed_copies.safe_delta_runtime_source_authority_context",
        lambda *args, **kwargs: {
            "valid": True,
            "actor_id": ACTOR,
            "pilot_lease_id": LEASE_ID,
            "package_id": PACKAGE_ID,
            "pilot_run_id": RUN_ID,
        },
    )
    monkeypatch.setattr(
        "francis.api.routes.managed_copies.managed_copy_runtime_evidence_readback_blocked_snapshot",
        lambda *args, **kwargs: pytest.fail("evidence handler must not run"),
    )

    body = TestClient(create_app()).post("/managed-copies/runtime-evidence-readback", json=_payload()).json()

    assert body["error"] == "api_permission_denied"


def test_exact_final_authority_transaction_records_one_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry = _registry()
    _consume(registry, 3)
    _install_registry(monkeypatch, registry)
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(
        "francis.managed_copy_safe_delta_runtime_evidence.safe_delta_runtime_source_authority_context",
        lambda *args, **kwargs: _authority_context(registry, required_count=3),
    )
    monkeypatch.setattr(
        "francis.managed_copy_safe_delta_runtime_evidence.verify_safe_delta_runtime_source_for_final_evidence",
        _source,
    )

    result = runtime_evidence.record_safe_delta_runtime_evidence_with_lease(
        _payload(),
        actor=ACTOR,
        stage17_closed=True,
    )

    assert result["status"] == "recorded"
    assert result["writes_receipt"] is True
    assert runtime_evidence.load_runtime_evidence_receipts() == [result["receipt"]]
    completion = managed_copy_completion_review_snapshot()
    safe_delta = next(item for item in completion["checks"] if item["id"] == "safe_delta_model_contract")
    assert safe_delta["runtime_ready"] is False
    assert safe_delta["runtime_evidence_receipt_id"] == ""


@pytest.mark.parametrize("race", ["revocation", "expiry", "registry_replacement"])
def test_final_write_authority_race_fails_closed_and_removes_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    race: str,
) -> None:
    now = [1_000]
    registry = _registry(now=now)
    _consume(registry, 3)
    _install_registry(monkeypatch, registry)
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(
        "francis.managed_copy_safe_delta_runtime_evidence.safe_delta_runtime_source_authority_context",
        lambda *args, **kwargs: _authority_context(registry, required_count=3),
    )
    monkeypatch.setattr(
        "francis.managed_copy_safe_delta_runtime_evidence.verify_safe_delta_runtime_source_for_final_evidence",
        _source,
    )
    original_build = runtime_evidence._build_receipt

    def build(plan: dict[str, object], *, receipt_id: str) -> dict[str, object]:
        receipt = original_build(plan, receipt_id=receipt_id)
        if race == "revocation":
            registry.revoke(LEASE_ID)
        elif race == "expiry":
            now[0] = 10_000
        else:
            managed_copy_pilot_runtime.PILOT_RUNTIME_LEASES = PilotScopeLeaseRegistry()
        return receipt

    monkeypatch.setattr(runtime_evidence, "_build_receipt", build)
    result = runtime_evidence.record_safe_delta_runtime_evidence_with_lease(
        _payload(),
        actor=ACTOR,
        stage17_closed=True,
    )

    assert result["ok"] is False
    assert result["cleanup_completed"] is True
    assert result["writes_receipt"] is False
    assert list(runtime_evidence.receipt_directory().glob("*.json")) == []


def test_source_authority_mismatch_denies_without_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry = _registry()
    _consume(registry, 3)
    _install_registry(monkeypatch, registry)
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(
        "francis.managed_copy_safe_delta_runtime_evidence.safe_delta_runtime_source_authority_context",
        lambda *args, **kwargs: {
            **_authority_context(registry, required_count=3),
            "package_fingerprint": _hash("wrong-package"),
        },
    )

    result = runtime_evidence.record_safe_delta_runtime_evidence_with_lease(
        _payload(),
        actor=ACTOR,
        stage17_closed=True,
    )

    assert result["error"] == "stage18_safe_delta_runtime_evidence_authority_changed_under_lock"
    assert not tmp_path.joinpath("data").exists()
