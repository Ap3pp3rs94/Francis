from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from francis.executor_substrate import (
    executor_branch_first_workflow_review_snapshot,
    executor_leases_idempotency_review_snapshot,
    executor_substrate_status_snapshot,
    executor_toolbelt_allowlist_review_snapshot,
    executor_verification_hooks_review_snapshot,
)

router = APIRouter()


@router.get("/substrate/status")
def substrate_status() -> dict[str, Any]:
    return executor_substrate_status_snapshot()


@router.get("/substrate/toolbelt-allowlist-review")
def toolbelt_allowlist_review() -> dict[str, Any]:
    return executor_toolbelt_allowlist_review_snapshot()


@router.get("/substrate/branch-first-workflow-review")
def branch_first_workflow_review() -> dict[str, Any]:
    return executor_branch_first_workflow_review_snapshot()


@router.get("/substrate/leases-idempotency-review")
def leases_idempotency_review() -> dict[str, Any]:
    return executor_leases_idempotency_review_snapshot()


@router.get("/substrate/verification-hooks-review")
def verification_hooks_review() -> dict[str, Any]:
    return executor_verification_hooks_review_snapshot()
