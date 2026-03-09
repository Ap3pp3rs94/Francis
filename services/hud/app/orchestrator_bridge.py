from __future__ import annotations

from typing import Any

from services.orchestrator.app.lens_operator import DEFAULT_ROLE, DEFAULT_USER
from services.orchestrator.app.lens_operator import execute_lens_action as execute_shared_lens_action
from services.orchestrator.app.lens_operator import get_lens_actions as get_shared_lens_actions


def get_lens_actions(*, max_actions: int = 8, role: str = DEFAULT_ROLE, user: str = DEFAULT_USER) -> dict[str, Any]:
    return get_shared_lens_actions(max_actions=max_actions, role=role, user=user)


def execute_lens_action(
    *,
    kind: str,
    args: dict[str, Any] | None = None,
    dry_run: bool = False,
    role: str = DEFAULT_ROLE,
    user: str = DEFAULT_USER,
    trace_id: str | None = None,
) -> dict[str, Any]:
    return execute_shared_lens_action(
        kind=kind,
        args=args,
        dry_run=dry_run,
        role=role,
        user=user,
        trace_id=trace_id,
    )
