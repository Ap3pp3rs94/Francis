from __future__ import annotations

from dataclasses import replace
from threading import Barrier, Thread
import time

import pytest

from francis.governance.api_permission_gate import ApiPermissionGate
from francis.governance.pilot_scope_lease import (
    PilotLeaseBinding,
    PilotLeaseCheck,
    PilotLeaseState,
    PilotScopeLease,
    PilotScopeLeaseRegistry,
)

_HASH_A = "a" * 64
_HASH_B = "b" * 64
_NOW = time.time_ns() // 1_000_000
_ACTOR = "pilot.actor"
_PACKAGE = "stage18-local-pilot-001"
_RUN = "stage18-local-pilot-001-run-001"
_NONCE = "runtime-nonce-001"

_CREATE = PilotLeaseBinding(
    "managed_copies.copy_creation.write",
    "/managed-copies/copy-creation-provision",
    "POST",
    "managed_copies.provision_copy",
)
_START = PilotLeaseBinding(
    "managed_copies.runtime_start.execute",
    "/managed-copies/runtime-start",
    "POST",
    "managed_copies.runtime_start",
)


def _lease(**changes: object) -> PilotScopeLease:
    values: dict[str, object] = {
        "lease_id": "pilot-lease-001",
        "actor_id": _ACTOR,
        "package_id": _PACKAGE,
        "package_fingerprint": _HASH_A,
        "pilot_run_id": _RUN,
        "bindings": (_CREATE, _START),
        "issued_at_ms": _NOW - 1_000,
        "expires_at_ms": _NOW + 10_000,
        "runtime_nonce": _NONCE,
        "operator_decision_fingerprint": _HASH_B,
    }
    values.update(changes)
    return PilotScopeLease(**values)  # type: ignore[arg-type]


def _check(binding: PilotLeaseBinding = _CREATE, **changes: object) -> PilotLeaseCheck:
    values: dict[str, object] = {
        "lease_id": "pilot-lease-001",
        "package_id": _PACKAGE,
        "package_fingerprint": _HASH_A,
        "pilot_run_id": _RUN,
        "runtime_nonce": _NONCE,
        "operator_decision_fingerprint": _HASH_B,
        "scope": binding.scope,
        "route": binding.route,
        "method": binding.method,
        "action": binding.action,
    }
    values.update(changes)
    return PilotLeaseCheck(**values)  # type: ignore[arg-type]


def test_exact_run_sequence_consumes_each_binding_once_then_seals() -> None:
    registry = PilotScopeLeaseRegistry([_lease()])

    first = registry.authorize_and_consume(actor_id=_ACTOR, check=_check(_CREATE), now_ms=_NOW)
    second = registry.authorize_and_consume(actor_id=_ACTOR, check=_check(_START), now_ms=_NOW)

    assert first.allowed is True
    assert first.state is PilotLeaseState.ACTIVE
    assert second.allowed is True
    assert second.state is PilotLeaseState.CONSUMED
    assert registry.seal("pilot-lease-001", now_ms=_NOW).state is PilotLeaseState.SEALED
    replay = registry.authorize_and_consume(actor_id=_ACTOR, check=_check(_CREATE), now_ms=_NOW)
    assert replay.allowed is False
    assert replay.reason == "pilot_lease_sealed"


def test_binding_sequence_rejects_out_of_order_action() -> None:
    registry = PilotScopeLeaseRegistry([_lease()])

    out_of_order = registry.authorize_and_consume(actor_id=_ACTOR, check=_check(_START), now_ms=_NOW)
    assert out_of_order.reason == "pilot_lease_binding_out_of_order"
    assert registry.authorize_and_consume(actor_id=_ACTOR, check=_check(_CREATE), now_ms=_NOW).allowed
    assert registry.authorize_and_consume(actor_id=_ACTOR, check=_check(_START), now_ms=_NOW).allowed


def test_expiry_boundary_and_revocation_between_actions_fail_closed() -> None:
    expired = PilotScopeLeaseRegistry([_lease()]).authorize_and_consume(
        actor_id=_ACTOR,
        check=_check(),
        now_ms=_NOW + 10_000,
    )
    assert expired.reason == "pilot_lease_expired"

    registry = PilotScopeLeaseRegistry([_lease()])
    assert registry.authorize_and_consume(actor_id=_ACTOR, check=_check(_CREATE), now_ms=_NOW).allowed
    assert registry.revoke("pilot-lease-001", now_ms=_NOW).allowed
    denied = registry.authorize_and_consume(actor_id=_ACTOR, check=_check(_START), now_ms=_NOW)
    assert denied.reason == "pilot_lease_revoked"


def test_issuance_boundary_fails_closed_until_exact_issue_time() -> None:
    registry = PilotScopeLeaseRegistry([_lease(issued_at_ms=_NOW, expires_at_ms=_NOW + 10_000)])

    before = registry.authorize_and_consume(actor_id=_ACTOR, check=_check(), now_ms=_NOW - 1)
    at_issue = registry.authorize_and_consume(actor_id=_ACTOR, check=_check(), now_ms=_NOW)

    assert before.reason == "pilot_lease_pending"
    assert at_issue.allowed is True


@pytest.mark.parametrize(
    ("actor", "changes", "reason"),
    [
        ("wrong.actor", {}, "pilot_lease_actor_mismatch"),
        (_ACTOR, {"pilot_run_id": "wrong-run"}, "pilot_lease_run_mismatch"),
        (_ACTOR, {"package_id": "wrong-package"}, "pilot_lease_package_mismatch"),
        (_ACTOR, {"package_fingerprint": "c" * 64}, "pilot_lease_package_fingerprint_mismatch"),
        (_ACTOR, {"action": "managed_copies.wrong"}, "pilot_lease_action_mismatch"),
        (_ACTOR, {"route": "/managed-copies/wrong"}, "pilot_lease_route_mismatch"),
        (_ACTOR, {"method": "DELETE"}, "pilot_lease_method_mismatch"),
        (_ACTOR, {"scope": "managed_copies.wrong"}, "pilot_lease_scope_mismatch"),
        (_ACTOR, {"runtime_nonce": "wrong-nonce"}, "pilot_lease_runtime_nonce_mismatch"),
        (_ACTOR, {"operator_decision_fingerprint": "c" * 64}, "pilot_lease_operator_decision_mismatch"),
    ],
)
def test_exact_binding_mismatches_are_denied(actor: str, changes: dict[str, object], reason: str) -> None:
    decision = PilotScopeLeaseRegistry([_lease()]).authorize_and_consume(
        actor_id=actor,
        check=_check(**changes),
        now_ms=_NOW,
    )
    assert decision.allowed is False
    assert decision.reason == reason


def test_scope_subset_does_not_merge_with_wildcard_static_grant() -> None:
    registry = PilotScopeLeaseRegistry([_lease(bindings=(_START,))])
    gate = ApiPermissionGate({_ACTOR: ["*"]}, pilot_lease_registry=registry, require_pilot_lease=True)

    wildcard = gate.check(
        actor_id=_ACTOR,
        required_scopes=[_CREATE.scope],
        route=_CREATE.route,
        method=_CREATE.method,
        pilot_lease_check=_check(_CREATE),
        action=_CREATE.action,
    )
    assert wildcard.allowed is False
    assert wildcard.reason == "missing_scopes"

    scoped_gate = ApiPermissionGate(
        {_ACTOR: [_CREATE.scope]},
        pilot_lease_registry=registry,
        require_pilot_lease=True,
    )
    escalated = scoped_gate.check(
        actor_id=_ACTOR,
        required_scopes=[_CREATE.scope],
        route=_CREATE.route,
        method=_CREATE.method,
        pilot_lease_check=_check(_CREATE),
        action=_CREATE.action,
    )
    assert escalated.allowed is False
    assert escalated.reason == "pilot_lease_scope_mismatch"


def test_process_restart_loses_registry_and_gate_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    first_registry = PilotScopeLeaseRegistry([_lease()])
    assert first_registry.state("pilot-lease-001", now_ms=_NOW) is PilotLeaseState.ACTIVE
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", '{"pilot.actor":["managed_copies.copy_creation.write"]}')

    restarted_gate = ApiPermissionGate.from_env(
        pilot_lease_registry=PilotScopeLeaseRegistry(),
        require_pilot_lease=True,
    )
    decision = restarted_gate.check(
        actor_id=_ACTOR,
        required_scopes=[_CREATE.scope],
        route=_CREATE.route,
        method=_CREATE.method,
        pilot_lease_check=_check(),
        action=_CREATE.action,
    )
    assert decision.allowed is False
    assert decision.reason == "missing_pilot_lease"


@pytest.mark.parametrize(
    ("route", "method", "action", "reason"),
    [
        ("/managed-copies/wrong", _CREATE.method, _CREATE.action, "pilot_lease_route_mismatch"),
        (_CREATE.route, "DELETE", _CREATE.action, "pilot_lease_method_mismatch"),
        (_CREATE.route, _CREATE.method, "managed_copies.wrong", "pilot_lease_action_mismatch"),
    ],
)
def test_gate_correlates_lease_binding_to_actual_action_route_and_method(
    route: str,
    method: str,
    action: str,
    reason: str,
) -> None:
    gate = ApiPermissionGate(
        {_ACTOR: [_CREATE.scope]},
        pilot_lease_registry=PilotScopeLeaseRegistry([_lease()]),
        require_pilot_lease=True,
    )
    decision = gate.check(
        actor_id=_ACTOR,
        required_scopes=[_CREATE.scope],
        route=route,
        method=method,
        action=action,
        pilot_lease_check=_check(),
    )
    assert decision.allowed is False
    assert decision.reason == reason


@pytest.mark.parametrize(
    "changes",
    [
        {"lease_id": "../unsafe"},
        {"issued_at_ms": True},
        {"expires_at_ms": 1.5},
        {"expires_at_ms": _NOW - 2_000},
        {"expires_at_ms": _NOW + 30 * 60 * 1_000 + 1},
        {"package_fingerprint": "not-a-hash"},
        {"bindings": (replace(_CREATE, route="/managed-copies/../escape"),)},
    ],
)
def test_malformed_lease_fields_are_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        PilotScopeLeaseRegistry([_lease(**changes)])


def test_concurrent_checks_consume_one_binding_at_most_once() -> None:
    registry = PilotScopeLeaseRegistry([_lease(bindings=(_CREATE,))])
    barrier = Barrier(3)
    results = []

    def attempt() -> None:
        barrier.wait()
        results.append(registry.authorize_and_consume(actor_id=_ACTOR, check=_check(), now_ms=_NOW))

    threads = [Thread(target=attempt), Thread(target=attempt)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()

    assert sum(result.allowed for result in results) == 1
    assert {result.reason for result in results} == {"pilot_lease_binding_consumed", "pilot_lease_consumed"}


def test_api_permission_gate_remains_compatible_without_lease_mode() -> None:
    decision = ApiPermissionGate({_ACTOR: [_CREATE.scope]}).check(
        actor_id=_ACTOR,
        required_scopes=[_CREATE.scope],
        route=_CREATE.route,
        method=_CREATE.method,
    )
    assert decision.allowed is True
    assert decision.reason == "ok"


def test_lease_denial_evidence_does_not_leak_bindings_or_fingerprints() -> None:
    gate = ApiPermissionGate(
        {_ACTOR: [_CREATE.scope]},
        pilot_lease_registry=PilotScopeLeaseRegistry([_lease()]),
        require_pilot_lease=True,
    )
    decision = gate.check(
        actor_id=_ACTOR,
        required_scopes=[_CREATE.scope],
        route=_CREATE.route,
        method=_CREATE.method,
        action=_CREATE.action,
        pilot_lease_check=_check(pilot_run_id="wrong-run"),
    )
    assert decision.allowed is False
    assert _CREATE.scope not in repr(decision.evidence)
    assert _HASH_A not in repr(decision.evidence)
    assert _HASH_B not in repr(decision.evidence)
