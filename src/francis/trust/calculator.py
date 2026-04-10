from __future__ import annotations

from dataclasses import dataclass

_MIN_TRUST_BY_RISK: dict[str, int] = {
    "readonly": -10,
    "low": -5,
    "normal": 0,
    "medium": 2,
    "high": 5,
    "critical": 5,
    "safety_critical": 8,
}

_RISK_ORDER: tuple[str, ...] = ("readonly", "low", "normal", "medium", "high", "critical", "safety_critical")


def normalize_risk_tier(risk_tier: str | None) -> str:
    raw = (risk_tier or "").strip().lower()
    if not raw:
        return "normal"
    if raw == "info":
        return "low"
    if raw == "warn":
        return "medium"
    if raw in _MIN_TRUST_BY_RISK:
        return raw
    return "normal"


def minimum_trust_for_risk(risk_tier: str | None) -> int:
    return _MIN_TRUST_BY_RISK[normalize_risk_tier(risk_tier)]


def trust_tier(level: int) -> str:
    if level <= -5:
        return "critical"
    if level <= -1:
        return "degraded"
    if level <= 2:
        return "guarded"
    if level <= 6:
        return "elevated"
    return "high"


def max_risk_for_level(level: int) -> str:
    allowed = allowed_risk_tiers(level)
    return allowed[-1] if allowed else "readonly"


def allowed_risk_tiers(level: int) -> tuple[str, ...]:
    allowed = [risk for risk in _RISK_ORDER if minimum_trust_for_risk(risk) <= level]
    return tuple(allowed or ["readonly"])


@dataclass(frozen=True, slots=True)
class TrustDecision:
    level: int
    risk_tier: str
    allowed: bool
    approvals_required: bool
    tier: str
    required_trust: int
    max_risk_tier: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "level": self.level,
            "risk_tier": self.risk_tier,
            "allowed": self.allowed,
            "approvals_required": self.approvals_required,
            "tier": self.tier,
            "required_trust": self.required_trust,
            "max_risk_tier": self.max_risk_tier,
            "allowed_risk_tiers": list(allowed_risk_tiers(self.level)),
            "reasons": list(self.reasons),
        }


def evaluate(
    level: int,
    risk_tier: str | None = None,
    *,
    explicit_min_trust: int | None = None,
    policy_requires_approval: bool = False,
) -> TrustDecision:
    normalized_risk = normalize_risk_tier(risk_tier)
    required = explicit_min_trust if explicit_min_trust is not None else minimum_trust_for_risk(normalized_risk)
    allowed = int(level) >= int(required)

    reasons: list[str] = [f"risk_tier={normalized_risk}", f"required_trust={required}", f"current_level={level}"]
    if allowed:
        reasons.append("trust_threshold_satisfied")
    else:
        reasons.append("trust_threshold_not_met")

    approvals_required = policy_requires_approval or normalized_risk in {"high", "critical", "safety_critical"}
    if approvals_required:
        reasons.append("approval_gate_required")

    return TrustDecision(
        level=int(level),
        risk_tier=normalized_risk,
        allowed=allowed,
        approvals_required=approvals_required,
        tier=trust_tier(int(level)),
        required_trust=int(required),
        max_risk_tier=max_risk_for_level(int(level)),
        reasons=tuple(reasons),
    )
