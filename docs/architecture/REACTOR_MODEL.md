# Reactor Model

## Purpose
Define the canonical event-driven autonomy reactor for Francis.

## Event-Driven Pipeline
1. Intake event.
2. Normalize and classify risk.
3. Validate scope, policy, and approval requirements.
4. Build bounded execution plan.
5. Execute approved actions.
6. Verify outcomes.
7. Record receipts and decision logs.
8. Emit follow-up events or queue approvals.

## Budgets and Bounded Dispatch
- Dispatch MUST enforce `max_actions_per_dispatch`.
- Dispatch MUST enforce `max_runtime_seconds`.
- Per-action CPU/memory/time budgets are policy-bound.
- Budget breaches create receipts and move unfinished work to queue/deadletter as configured.

## Stop Conditions
- Critical incidents can block execution phase automatically.
- Panic/revocation always preempts execution.
- Scope violation or missing approval transitions task to blocked/approval queue.
- Verification failure prevents "done" state and triggers retry or escalation policy.

## Deadletter and Retry with Backoff
- Failed events/tasks move to deadletter after max attempts.
- Retry policy is explicit: attempt count, exponential backoff, jitter, and terminal status.
- Retries MUST be idempotent via stable keys and lease coordination.
- Deadletter entries require remediation hints and evidence pointers.

## Observability and Receipts
- Every reactor step emits `run_id`, `trace_id`, stage, and outcome.
- Decision rationale is journaled for audits.
- Reactor summaries provide success/failure counts, budget usage, and pending approvals.

## Acceptance Criteria Checklist
- [ ] Reactor executes through event-driven dispatch, not generic `while true` loops.
- [ ] Budgets cap dispatch actions and runtime.
- [ ] Critical incidents and panic state halt execution safely.
- [ ] Deadletter and retry-with-backoff behavior are deterministic and auditable.
- [ ] Receipts cover intake, plan, execute, verify, and decision outcomes.
