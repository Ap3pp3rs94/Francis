from __future__ import annotations

from francis.governance.api_permission_gate import ApiPermissionGate


def test_api_permission_gate_denies_missing_actor() -> None:
    gate = ApiPermissionGate({"operator": ["missions:run"]})

    decision = gate.check(
        actor_id="",
        required_scopes=["missions:run"],
        route="/missions/run_once",
        method="post",
    )

    assert decision.allowed is False
    assert decision.reason == "missing_actor"
    assert decision.evidence["actor_present"] is False
    assert decision.evidence["required_scope_count"] == 1


def test_api_permission_gate_denies_unscoped_gate_check() -> None:
    gate = ApiPermissionGate({"operator": ["missions:run"]})

    decision = gate.check(actor_id="operator", required_scopes=[], route="/missions/run_once", method="post")

    assert decision.allowed is False
    assert decision.reason == "empty_required_scopes"
    assert decision.evidence["required_scope_count"] == 0


def test_api_permission_gate_denies_missing_scope_without_leaking_scope_names() -> None:
    gate = ApiPermissionGate({"operator": ["missions:run"]})

    decision = gate.check(
        actor_id="operator",
        required_scopes=["missions:run", "secrets:read"],
        route="/missions/run_once",
        method="post",
    )

    assert decision.allowed is False
    assert decision.reason == "missing_scopes"
    assert decision.evidence["actor_scope_count"] == 1
    assert decision.evidence["scope_decision"] == {
        "requested_scope_count": 2,
        "allowed_scope_count": 1,
        "missing_scope_count": 1,
    }
    assert "secrets:read" not in repr(decision.evidence)


def test_api_permission_gate_allows_resolved_actor_scope() -> None:
    gate = ApiPermissionGate()

    decision = gate.check(
        actor_id="token=sk-supersecret0000000000000000",
        actor_scopes=["missions:run"],
        required_scopes=["missions:run"],
        route="/missions/run_once",
        method="post",
    )

    assert decision.allowed is True
    assert decision.reason == "ok"
    assert decision.evidence["actor_present"] is True
    assert decision.evidence["method"] == "POST"
    assert "sk-supersecret" not in repr(decision.evidence)
