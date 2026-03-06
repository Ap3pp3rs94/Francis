from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolApprovalPolicy:
    requires_approval: bool
    reason: str


# Selected high-impact tools require explicit approval.
TOOL_APPROVAL_RULES: dict[str, ToolApprovalPolicy] = {
    "workspace.write": ToolApprovalPolicy(
        requires_approval=True,
        reason="Workspace write is mutating and requires explicit approval.",
    ),
    "repo.tests": ToolApprovalPolicy(
        requires_approval=True,
        reason="Repository test execution consumes significant compute/time and requires approval.",
    ),
}


def approval_policy_for_tool(
    *,
    skill_name: str,
    risk_tier: str,
    mutating: bool,
    source: str = "builtin",
    declared_requires_approval: bool = False,
) -> ToolApprovalPolicy:
    normalized = skill_name.strip().lower()
    if normalized in TOOL_APPROVAL_RULES:
        return TOOL_APPROVAL_RULES[normalized]

    if declared_requires_approval:
        return ToolApprovalPolicy(requires_approval=True, reason="Tool metadata requires approval.")

    normalized_risk = risk_tier.strip().lower()
    if normalized_risk in {"high", "critical"}:
        return ToolApprovalPolicy(requires_approval=True, reason=f"{normalized_risk} risk tool requires approval.")

    if source == "forge" and mutating:
        return ToolApprovalPolicy(requires_approval=True, reason="Mutating forge tool packs require approval.")

    return ToolApprovalPolicy(requires_approval=False, reason="No approval required by tool policy.")
