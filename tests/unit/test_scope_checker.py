from __future__ import annotations

from francis.credentials.scope_checker import ScopeChecker


def test_scope_checker_returns_count_only_missing_scope_evidence() -> None:
    decision = ScopeChecker(["missions:run"]).check(["missions:run", "secrets:read"])

    assert decision.allowed is False
    assert decision.reason == "missing_scopes"
    assert decision.evidence == {
        "requested_scope_count": 2,
        "allowed_scope_count": 1,
        "missing_scope_count": 1,
    }
    assert "secrets:read" not in repr(decision.evidence)


def test_scope_checker_preserves_no_policy_behavior_with_evidence() -> None:
    decision = ScopeChecker().check(["missions:run"])

    assert decision.allowed is True
    assert decision.reason == "no_policy"
    assert decision.evidence == {
        "requested_scope_count": 1,
        "allowed_scope_count": 0,
    }
