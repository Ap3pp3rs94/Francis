from __future__ import annotations


def requires_approval(action: str) -> bool:
    """Simple policy gate for high-risk actions."""
    normalized = action.strip().lower()
    high_risk_prefixes = (
        "danger.",
        "admin.",
        "shell.exec",
        "fs.delete",
        "git.reset",
    )
    high_risk_exact_actions = {
        "forge.promote",
    }
    return normalized.startswith(high_risk_prefixes) or normalized in high_risk_exact_actions
