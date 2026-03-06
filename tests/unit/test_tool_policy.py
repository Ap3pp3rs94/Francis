from francis_policy.tool_policy import approval_policy_for_tool


def test_selected_high_risk_tools_require_approval() -> None:
    write_policy = approval_policy_for_tool(
        skill_name="workspace.write",
        risk_tier="medium",
        mutating=True,
        source="builtin",
    )
    assert write_policy.requires_approval is True

    tests_policy = approval_policy_for_tool(
        skill_name="repo.tests",
        risk_tier="medium",
        mutating=False,
        source="builtin",
    )
    assert tests_policy.requires_approval is True


def test_low_risk_read_only_tool_does_not_require_approval() -> None:
    policy = approval_policy_for_tool(
        skill_name="workspace.read",
        risk_tier="low",
        mutating=False,
        source="builtin",
    )
    assert policy.requires_approval is False
