from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from francis import managed_copy_pilot_runtime
from francis import managed_copy_safe_delta_runtime_invocation as invocation
from francis import managed_copy_safe_delta_runtime_source as source
from francis.api.app import create_app
from francis.governance.pilot_scope_lease import (
    PilotLeaseBinding,
    PilotScopeLease,
    PilotScopeLeaseRegistry,
)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _request(**updates: Any) -> dict[str, Any]:
    value = {
        "request_actor": "stage18.safe-delta-invoker",
        "copy_id": "managed-copy-001",
        "provisioning_receipt_id": "provision-001",
        "isolation_verification_receipt_id": "isolation-001",
        "runtime_invocation_receipt_id": "runtime-invocation-001",
        "runtime_invocation_receipt_fingerprint": _hash("invocation-receipt"),
        "runtime_invocation_fingerprint": _hash("invocation"),
        "pilot_lease_id": "lease-safe-delta-001",
        "package_id": "package-safe-delta-001",
        "pilot_run_id": "run-safe-delta-001",
        "trace_id": "trace-safe-delta-001",
        "dry_run": True,
        "source_fingerprint": "",
        "confirm_source_recording": False,
    }
    value.update(updates)
    return value


def _lineage() -> dict[str, Any]:
    invocation_receipt = {
        "actor": "stage18.safe-delta-invoker",
        "tenant_key": _hash("tenant"),
        "copy_id": "managed-copy-001",
        "provisioning_receipt_id": "provision-001",
        "provisioning_receipt_fingerprint": _hash("provision"),
        "isolation_verification_receipt_id": "isolation-001",
        "isolation_verification_receipt_fingerprint": _hash("isolation"),
        "artifact_plan_fingerprint": _hash("artifact-plan"),
        "export_artifact_receipt_id": "artifact-001",
        "export_artifact_receipt_fingerprint": _hash("artifact-receipt"),
        "artifact_content_fingerprint": _hash("artifact"),
        "receipt_id": "runtime-invocation-001",
        "receipt_fingerprint": _hash("invocation-receipt"),
        "invocation_fingerprint": _hash("invocation"),
        "invocation_result_fingerprint": _hash("result"),
        "pilot_lease_id": "lease-safe-delta-001",
        "package_id": "package-safe-delta-001",
        "package_fingerprint": _hash("package"),
        "pilot_run_id": "run-safe-delta-001",
        "operator_decision_fingerprint": _hash("decision"),
        "lease_authority_fingerprint": _hash("first-authority"),
        "trace_id": "trace-safe-delta-001",
        "invocation_result": {"eligible_for_core_review": True},
    }
    artifact_receipt = {
        "review_fingerprint": _hash("review"),
        "authorization_decision_receipt_id": "export-decision-001",
        "authorization_decision_receipt_fingerprint": _hash("export-decision"),
    }
    return {
        "tenant_key": _hash("tenant"),
        "invocation": invocation_receipt,
        "artifact_receipt": artifact_receipt,
        "review": {
            "receipt_id": "review-001",
            "receipt_fingerprint": _hash("review-receipt"),
            "signal_class": "approved_non_private_signal",
        },
        "decision": {
            "receipt_id": "safe-delta-decision-001",
            "receipt_fingerprint": _hash("safe-delta-decision"),
        },
    }


def _authority(count: int = 2) -> dict[str, Any]:
    prefixes = [_hash("first-authority"), _hash("second-authority")][:count]
    return {
        "valid": True,
        "actor_id": "stage18.safe-delta-invoker",
        "lease_id": "lease-safe-delta-001",
        "package_id": "package-safe-delta-001",
        "package_fingerprint": _hash("package"),
        "pilot_run_id": "run-safe-delta-001",
        "operator_decision_fingerprint": _hash("decision"),
        "effective_state": "consumed" if count == 2 else "active",
        "consumed_binding_count": count,
        "operation_consumed_binding_count": count,
        "lease_authority_fingerprint": prefixes[-1],
        "consumed_prefix_fingerprints": prefixes,
    }


@pytest.fixture
def isolated_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    directory = tmp_path / "safe-delta-runtime"
    monkeypatch.setattr(source, "safe_delta_runtime_source_directory", lambda: directory)
    monkeypatch.setattr(source, "_load_lineage", lambda request: (_lineage(), ""))
    monkeypatch.setattr(
        managed_copy_pilot_runtime,
        "execute_pilot_runtime_lease_authority_transaction",
        lambda lease_id, *, actor, expected_bindings, operation: (
            True,
            "pilot_lease_authority_transaction_committed",
            operation(_authority()),
        ),
    )
    monkeypatch.setattr(
        source,
        "verify_safe_delta_runtime_source",
        lambda receipt_id, fingerprint: {"valid": True, "blocker": ""},
    )
    return directory


def _plan() -> dict[str, Any]:
    return source.plan_safe_delta_runtime_source(_request(), actor="stage18.safe-delta-invoker")


def test_plan_and_confirmed_record_write_one_exact_redacted_source(isolated_source: Path) -> None:
    plan = _plan()
    recorded = source.record_safe_delta_runtime_source(
        plan,
        provided_fingerprint=plan["source_fingerprint"],
        confirmed=True,
        authority=_authority(),
    )

    assert plan["ok"] is True
    assert recorded["ok"] is True
    assert recorded["writes_receipt"] is True
    receipt = recorded["receipt"]
    assert receipt["evidence_class"] == "canonical_runtime"
    assert receipt["fixture_only"] is False
    assert receipt["runtime_gate_ready"] is True
    assert receipt["invocation_lease_authority_fingerprint"] == _hash("first-authority")
    assert receipt["source_lease_authority_fingerprint"] == _hash("second-authority")
    assert "runtime_nonce" not in json.dumps(receipt)
    assert len(list(isolated_source.glob("*.json"))) == 1


def test_source_replay_is_idempotent_and_conflict_fails_closed(
    isolated_source: Path,
) -> None:
    plan = _plan()
    first = source.record_safe_delta_runtime_source(
        plan,
        provided_fingerprint=plan["source_fingerprint"],
        confirmed=True,
        authority=_authority(),
    )
    replay = source.record_safe_delta_runtime_source(
        plan,
        provided_fingerprint=plan["source_fingerprint"],
        confirmed=True,
        authority=_authority(),
    )
    path = next(isolated_source.glob("*.json"))
    tampered = json.loads(path.read_text())
    tampered["actor"] = "other-actor"
    path.write_text(json.dumps(tampered))
    conflict = source.record_safe_delta_runtime_source(
        plan,
        provided_fingerprint=plan["source_fingerprint"],
        confirmed=True,
        authority=_authority(),
    )

    assert first["writes_receipt"] is True
    assert replay["status"] == "already_recorded"
    assert replay["writes_receipt"] is False
    assert conflict["error"] == "safe_delta_runtime_source_conflict"


@pytest.mark.parametrize(
    ("blocker", "expected"),
    [
        ("safe_delta_runtime_source_invocation_invalid", "safe_delta_runtime_source_invocation_invalid"),
        ("safe_delta_runtime_source_artifact_lineage_invalid", "safe_delta_runtime_source_artifact_lineage_invalid"),
        (
            "safe_delta_runtime_source_review_or_decision_invalid",
            "safe_delta_runtime_source_review_or_decision_invalid",
        ),
    ],
)
def test_source_rejects_invalid_or_drifted_lineage(
    monkeypatch: pytest.MonkeyPatch,
    blocker: str,
    expected: str,
) -> None:
    monkeypatch.setattr(source, "_load_lineage", lambda request: ({}, blocker))
    plan = source.plan_safe_delta_runtime_source(_request(), actor="stage18.safe-delta-invoker")
    assert plan["ok"] is False
    assert plan["error"] == expected


def test_source_rejects_wrong_or_stale_authority_before_write(isolated_source: Path) -> None:
    plan = _plan()
    for authority in (
        {},
        _authority(1),
        {**_authority(), "actor_id": "wrong"},
        {**_authority(), "package_id": "wrong"},
        {**_authority(), "pilot_run_id": "wrong"},
    ):
        result = source.record_safe_delta_runtime_source(
            plan,
            provided_fingerprint=plan["source_fingerprint"],
            confirmed=True,
            authority=authority,
        )
        assert result["error"] == "safe_delta_runtime_source_authority_lineage_invalid"
    assert not isolated_source.exists()


def test_source_revalidates_authority_under_lock(
    monkeypatch: pytest.MonkeyPatch,
    isolated_source: Path,
) -> None:
    monkeypatch.setattr(
        managed_copy_pilot_runtime,
        "execute_pilot_runtime_lease_authority_transaction",
        lambda lease_id, *, actor, expected_bindings, operation: (
            True,
            "pilot_lease_authority_transaction_committed",
            operation(_authority(1)),
        ),
    )
    plan = _plan()

    result = source.record_safe_delta_runtime_source(
        plan,
        provided_fingerprint=plan["source_fingerprint"],
        confirmed=True,
        authority=_authority(),
    )

    assert result["error"] == "safe_delta_runtime_source_authority_changed_under_lock"
    assert not isolated_source.exists()


def test_post_write_lineage_drift_is_cleanup_required(
    monkeypatch: pytest.MonkeyPatch,
    isolated_source: Path,
) -> None:
    calls = 0

    def load(request: dict[str, str]) -> tuple[dict[str, Any], str]:
        nonlocal calls
        calls += 1
        lineage = _lineage()
        if calls >= 4:
            lineage["decision"] = {**lineage["decision"], "receipt_fingerprint": _hash("changed")}
        return lineage, ""

    monkeypatch.setattr(source, "_load_lineage", load)
    plan = _plan()
    result = source.record_safe_delta_runtime_source(
        plan,
        provided_fingerprint=plan["source_fingerprint"],
        confirmed=True,
        authority=_authority(),
    )

    assert result["status"] == "cleanup_required"
    assert result["error"] == "safe_delta_runtime_source_post_write_lineage_drift"
    assert result["quarantined_receipt_preserved"] is True
    assert result["canonical_runtime_evidence"] is False
    assert result["runtime_gate_ready"] is False


@pytest.mark.parametrize("race", ["expiry", "registry_replacement"])
def test_authority_race_during_source_publication_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    race: str,
) -> None:
    actor = "stage18.safe-delta-invoker"
    now = [1_000]
    registry = PilotScopeLeaseRegistry(clock_ms=lambda: now[0])
    registry.issue(
        PilotScopeLease(
            lease_id="lease-safe-delta-001",
            actor_id=actor,
            package_id="package-safe-delta-001",
            package_fingerprint=_hash("package"),
            pilot_run_id="run-safe-delta-001",
            bindings=invocation.lease_bindings(),
            issued_at_ms=900,
            expires_at_ms=10_000,
            runtime_nonce="runtime-nonce-safe-delta",
            operator_decision_fingerprint=_hash("decision"),
        )
    )
    for binding in invocation.lease_bindings():
        assert registry.authorize_binding(
            lease_id="lease-safe-delta-001",
            actor_id=actor,
            scope=binding.scope,
            route=binding.route,
            method=binding.method,
            action=binding.action,
        ).allowed
    monkeypatch.setattr(managed_copy_pilot_runtime, "PILOT_RUNTIME_LEASES", registry)
    directory = tmp_path / "safe-delta-runtime"
    monkeypatch.setattr(source, "safe_delta_runtime_source_directory", lambda: directory)
    monkeypatch.setattr(source, "_load_lineage", lambda request: (_lineage(), ""))
    monkeypatch.setattr(
        source,
        "verify_safe_delta_runtime_source",
        lambda receipt_id, fingerprint: {"valid": True, "blocker": ""},
    )
    authority = managed_copy_pilot_runtime.pilot_runtime_lease_authority_snapshot(
        "lease-safe-delta-001",
        actor=actor,
        expected_bindings=invocation.lease_bindings(),
    )
    original_publish = source._publish_exclusive

    def publish(path: Path, content: bytes) -> None:
        original_publish(path, content)
        if race == "expiry":
            now[0] = 10_000
        else:
            managed_copy_pilot_runtime.PILOT_RUNTIME_LEASES = PilotScopeLeaseRegistry()

    monkeypatch.setattr(source, "_publish_exclusive", publish)
    plan = _plan()
    result = source.record_safe_delta_runtime_source(
        plan,
        provided_fingerprint=plan["source_fingerprint"],
        confirmed=True,
        authority=authority,
    )

    assert result["status"] == "cleanup_required"
    assert result["quarantined_receipt_preserved"] is True
    assert result["canonical_runtime_evidence"] is False
    assert result["runtime_gate_ready"] is False
    assert "authority_transaction" in result["error"]


def _registry() -> PilotScopeLeaseRegistry:
    registry = PilotScopeLeaseRegistry(clock_ms=lambda: 1_000)
    registry.issue(
        PilotScopeLease(
            lease_id="lease-safe-delta-001",
            actor_id="stage18.safe-delta-invoker",
            package_id="package-safe-delta-001",
            package_fingerprint=_hash("package"),
            pilot_run_id="run-safe-delta-001",
            bindings=invocation.lease_bindings(),
            issued_at_ms=900,
            expires_at_ms=10_000,
            runtime_nonce="runtime-nonce-safe-delta",
            operator_decision_fingerprint=_hash("decision"),
        )
    )
    return registry


def test_api_exact_sequence_consumes_invocation_then_source_and_denies_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = "stage18.safe-delta-invoker"
    registry = _registry()
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps(
            {
                actor: [
                    invocation.WRITE_SCOPE,
                    invocation.SOURCE_SCOPE,
                ]
            }
        ),
    )
    monkeypatch.setattr(managed_copy_pilot_runtime, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr("francis.api.routes.managed_copies.PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(
        "francis.api.routes.managed_copies.managed_copy_safe_delta_runtime_invocation_snapshot",
        lambda payload, *, actor, authority: {"ok": True, "authority": authority},
    )
    monkeypatch.setattr(
        "francis.api.routes.managed_copies.managed_copy_safe_delta_runtime_source_snapshot",
        lambda payload, *, actor, authority: {"ok": True, "authority": authority},
    )
    client = TestClient(create_app())

    source_first = client.post("/managed-copies/safe-delta-runtime-source", json=_request()).json()
    invoked = client.post("/managed-copies/safe-delta-runtime-invocation", json=_request()).json()
    sourced = client.post("/managed-copies/safe-delta-runtime-source", json=_request()).json()
    replay = client.post("/managed-copies/safe-delta-runtime-source", json=_request()).json()

    assert source_first["error"] == "api_permission_denied"
    assert invoked["authority"]["consumed_binding_count"] == 1
    assert sourced["authority"]["consumed_binding_count"] == 2
    assert replay["error"] == "api_permission_denied"


def test_missing_registry_lease_denies_before_handlers_or_filesystem(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    actor = "stage18.safe-delta-invoker"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({actor: [invocation.WRITE_SCOPE, invocation.SOURCE_SCOPE]}),
    )
    monkeypatch.setattr(managed_copy_pilot_runtime, "PILOT_RUNTIME_LEASES", PilotScopeLeaseRegistry())
    monkeypatch.setattr(
        "francis.api.routes.managed_copies.PILOT_RUNTIME_LEASES",
        PilotScopeLeaseRegistry(),
    )
    monkeypatch.setattr(
        "francis.api.routes.managed_copies.managed_copy_safe_delta_runtime_invocation_snapshot",
        lambda *args, **kwargs: pytest.fail("invocation handler must not run"),
    )
    monkeypatch.setattr(
        "francis.api.routes.managed_copies.managed_copy_safe_delta_runtime_source_snapshot",
        lambda *args, **kwargs: pytest.fail("source handler must not run"),
    )
    client = TestClient(create_app())

    assert client.post("/managed-copies/safe-delta-runtime-invocation", json=_request()).json()["error"] == (
        "api_permission_denied"
    )
    assert client.post("/managed-copies/safe-delta-runtime-source", json=_request()).json()["error"] == (
        "api_permission_denied"
    )
    assert not tmp_path.joinpath("data").exists()


@pytest.mark.parametrize(
    ("route", "handler"),
    [
        (
            "/managed-copies/safe-delta-runtime-invocation",
            "managed_copy_safe_delta_runtime_invocation_snapshot",
        ),
        (
            "/managed-copies/safe-delta-runtime-source",
            "managed_copy_safe_delta_runtime_source_snapshot",
        ),
    ],
)
def test_unscoped_denial_precedes_handler_and_filesystem(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    route: str,
    handler: str,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")
    monkeypatch.setattr(
        f"francis.api.routes.managed_copies.{handler}",
        lambda *args, **kwargs: pytest.fail("handler must not run"),
    )

    body = TestClient(create_app()).post(route, json=_request()).json()

    assert body["error"] == "api_permission_denied"
    assert not tmp_path.joinpath("data").exists()


def test_wrong_package_or_run_denies_without_consuming_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = "stage18.safe-delta-invoker"
    registry = _registry()
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({actor: [invocation.WRITE_SCOPE]}),
    )
    monkeypatch.setattr(managed_copy_pilot_runtime, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr("francis.api.routes.managed_copies.PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(
        "francis.api.routes.managed_copies.managed_copy_safe_delta_runtime_invocation_snapshot",
        lambda payload, *, actor, authority: {"ok": True, "authority": authority},
    )
    client = TestClient(create_app())

    wrong_package = client.post(
        "/managed-copies/safe-delta-runtime-invocation",
        json=_request(package_id="wrong-package"),
    ).json()
    wrong_run = client.post(
        "/managed-copies/safe-delta-runtime-invocation",
        json=_request(pilot_run_id="wrong-run"),
    ).json()
    valid = client.post("/managed-copies/safe-delta-runtime-invocation", json=_request()).json()

    assert wrong_package["error"] == "api_permission_denied"
    assert wrong_run["error"] == "api_permission_denied"
    assert valid["authority"]["consumed_binding_count"] == 1


def test_revoked_expired_and_restarted_registries_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = "stage18.safe-delta-invoker"
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({actor: [invocation.WRITE_SCOPE]}),
    )
    client = TestClient(create_app())

    revoked = _registry()
    assert revoked.revoke("lease-safe-delta-001").allowed is True
    expired = PilotScopeLeaseRegistry(clock_ms=lambda: 11_000)
    expired.issue(
        PilotScopeLease(
            lease_id="lease-safe-delta-001",
            actor_id=actor,
            package_id="package-safe-delta-001",
            package_fingerprint=_hash("package"),
            pilot_run_id="run-safe-delta-001",
            bindings=invocation.lease_bindings(),
            issued_at_ms=900,
            expires_at_ms=10_000,
            runtime_nonce="runtime-nonce-safe-delta",
            operator_decision_fingerprint=_hash("decision"),
        )
    )
    for registry in (revoked, expired, PilotScopeLeaseRegistry()):
        monkeypatch.setattr(managed_copy_pilot_runtime, "PILOT_RUNTIME_LEASES", registry)
        monkeypatch.setattr("francis.api.routes.managed_copies.PILOT_RUNTIME_LEASES", registry)
        body = client.post("/managed-copies/safe-delta-runtime-invocation", json=_request()).json()
        assert body["error"] == "api_permission_denied"


def test_authority_snapshot_accepts_safe_delta_as_consecutive_later_bindings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = "stage18.safe-delta-invoker"
    prior = PilotLeaseBinding(
        "managed_copies.pilot_runtime.start",
        "/managed-copies/pilot-runtime-start",
        "POST",
        "managed_copies.pilot_runtime.start",
    )
    registry = PilotScopeLeaseRegistry(clock_ms=lambda: 1_000)
    registry.issue(
        PilotScopeLease(
            lease_id="lease-safe-delta-001",
            actor_id=actor,
            package_id="package-safe-delta-001",
            package_fingerprint=_hash("package"),
            pilot_run_id="run-safe-delta-001",
            bindings=(prior, *invocation.lease_bindings()),
            issued_at_ms=900,
            expires_at_ms=10_000,
            runtime_nonce="runtime-nonce-safe-delta",
            operator_decision_fingerprint=_hash("decision"),
        )
    )
    assert registry.authorize_binding(
        lease_id="lease-safe-delta-001",
        actor_id=actor,
        scope=prior.scope,
        route=prior.route,
        method=prior.method,
        action=prior.action,
    ).allowed
    first = invocation.lease_bindings()[0]
    assert registry.authorize_binding(
        lease_id="lease-safe-delta-001",
        actor_id=actor,
        scope=first.scope,
        route=first.route,
        method=first.method,
        action=first.action,
    ).allowed
    monkeypatch.setattr(managed_copy_pilot_runtime, "PILOT_RUNTIME_LEASES", registry)

    observed = managed_copy_pilot_runtime.pilot_runtime_lease_authority_snapshot(
        "lease-safe-delta-001",
        actor=actor,
        expected_bindings=invocation.lease_bindings(),
    )

    assert observed["valid"] is True
    assert observed["consumed_binding_count"] == 2
    assert observed["operation_consumed_binding_count"] == 1
    assert len(observed["consumed_prefix_fingerprints"]) == 1
