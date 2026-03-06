# Panic and Revocation

## Purpose
Define immediate-stop and authority-revocation behavior so the user can halt Francis safely and deterministically at any time.

## Panic/Kill Switch Semantics
- Panic is an immediate halt signal across active execution surfaces.
- On panic, no new mutating actions may start.
- In-flight actions must stop at the next safe checkpoint and emit partial receipts.
- Panic state is visible in control surfaces and logs until explicitly cleared.

## Privilege Revocation Rules
- Revocation can target mode, scope, capability, node, or full system authority.
- Revocation takes effect before queued actions are dispatched.
- Any queued action now out-of-scope is canceled or moved to approval queue.
- Revocation events require receipts with actor, reason, and impacted scopes.

## Safe-Stop Behavior
- Preserve integrity first: avoid partial writes where transactional boundaries exist.
- Flush buffered receipts/logs before process suspension when possible.
- Record what was completed, canceled, or uncertain at stop time.
- Require explicit user action to resume Pilot or Away execution.

## Recovery and Handback
- Recovery starts in Observe mode unless user explicitly re-grants authority.
- Handback summary MUST include: halted tasks, pending approvals, and recommended next actions.
- Any ambiguous task state is marked for re-verification before continuation.

## Acceptance Criteria Checklist
- [ ] Panic halts new mutating actions immediately.
- [ ] Revocation is scope-aware and blocks unauthorized queued work.
- [ ] Safe-stop emits receipts for completed, partial, and canceled actions.
- [ ] Resume requires explicit user re-authorization.
- [ ] Control surfaces clearly indicate panic/revoked status.
