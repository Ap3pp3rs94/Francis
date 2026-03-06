# Takeover Ritual

## Purpose
Define the canonical, user-controlled takeover flow for Pilot Mode.

## Canonical Sequence
1. Request takeover.
2. Declare and display scope boundaries.
3. Present planned actions, risk tier, and verification gates.
4. Require explicit user confirmation.
5. Enter Pilot Mode with visible `PILOT MODE ON` indicator.
6. Stream live action feed with receipts in real time.
7. Verify outcomes and generate handback package.
8. Return control to user with summary and pending decisions.

## Receipts During Takeover
- Each action emits `run_id`, `trace_id`, command/diff artifacts, and verification status.
- Handback package includes branch context, changed files, test/build results, and unresolved risks.
- Any blocked action is queued with approval evidence, never silently skipped.

## Forbidden Behaviors
- No implicit control transfer.
- No scope expansion without explicit approval.
- No completion claims without verification artifacts.
- No hidden background mutations after handback.

## Handback Ritual
- Exit Pilot by default after requested objective completes or user cancels.
- Deliver concise summary: done, pending, blocked, recommended next action.
- Persist all receipts before mode reset.

## Acceptance Criteria Checklist
- [ ] Takeover cannot begin without explicit confirmation.
- [ ] Scope and risk are visible before and during execution.
- [ ] Live feed and receipts are available throughout Pilot Mode.
- [ ] Handback includes verification results and pending approvals.
- [ ] Pilot control is revocable instantly via panic/revocation controls.
