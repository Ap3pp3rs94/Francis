from __future__ import annotations

from dataclasses import dataclass

from .approvals import requires_approval


@dataclass(frozen=True)
class PolicyDecision:
    action: str
    allowed: bool
    reason: str


def decide(action: str, *, approved: bool = False) -> PolicyDecision:
    needs_approval = requires_approval(action)
    if not needs_approval:
        return PolicyDecision(action=action, allowed=True, reason="No approval required.")
    if approved:
        return PolicyDecision(action=action, allowed=True, reason="Approved.")
    return PolicyDecision(action=action, allowed=False, reason="Approval required.")
