from francis_policy.risk_tiers import RiskTier
from francis_policy.rbac import can


def test_risk_tier_enum() -> None:
    assert RiskTier.LOW.value == 'low'


def test_rbac_rules() -> None:
    assert can("architect", "missions.create")
    assert can("observer", "missions.read")
    assert not can("observer", "missions.create")
