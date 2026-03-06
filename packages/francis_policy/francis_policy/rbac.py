from __future__ import annotations

from collections.abc import Iterable


ROLE_RULES: dict[str, set[str]] = {
    "architect": {
        "missions.read",
        "missions.create",
        "missions.tick",
        "forge.read",
        "forge.propose",
        "forge.stage",
        "forge.promote",
        "approvals.read",
        "approvals.request",
        "approvals.decide",
        "tools.read",
        "tools.run",
        "telemetry.read",
        "telemetry.write",
        "autonomy.read",
        "autonomy.enqueue",
        "autonomy.dispatch",
        "autonomy.cycle",
        "worker.read",
        "worker.cycle",
    },
    "operator": {
        "missions.read",
        "missions.create",
        "missions.tick",
        "forge.read",
        "forge.propose",
        "forge.stage",
        "approvals.read",
        "approvals.request",
        "tools.read",
        "tools.run",
        "telemetry.read",
        "telemetry.write",
        "autonomy.read",
        "autonomy.enqueue",
        "autonomy.dispatch",
        "autonomy.cycle",
        "worker.read",
        "worker.cycle",
    },
    "worker": {
        "missions.read",
        "missions.tick",
        "forge.read",
        "approvals.read",
        "tools.read",
        "tools.run",
        "telemetry.read",
        "telemetry.write",
        "autonomy.read",
        "worker.read",
        "worker.cycle",
    },
    "observer": {
        "missions.read",
        "forge.read",
        "forge.propose",
        "approvals.read",
        "tools.read",
        "telemetry.read",
        "autonomy.read",
        "worker.read",
    },
}


def can(role: str, action: str) -> bool:
    normalized_role = role.strip().lower()
    allowed = ROLE_RULES.get(normalized_role, set())
    return action in allowed


def allowed_actions(role: str) -> list[str]:
    normalized_role = role.strip().lower()
    return sorted(ROLE_RULES.get(normalized_role, set()))


def register_role(role: str, actions: Iterable[str]) -> None:
    normalized_role = role.strip().lower()
    ROLE_RULES[normalized_role] = set(actions)
