# Takeover (Pilot Mode)

## Pilot Mode Experience
Pilot Mode is user-commanded takeover where Francis becomes your hands for a bounded task while you remain the pilot and authority.

## Standard Takeover Flow
1. Confirm mode + scope + objective.
2. Establish branch-first execution context for code tasks.
3. Execute bounded actions with live receipts.
4. Verify outcomes (tests/checks/expected deltas).
5. Summarize changes, risks, and pending approvals.
6. Return control explicitly.

## Verification Gates
- Scope gate: action must be inside declared boundary.
- Policy gate: risk and approval checks must pass.
- Quality gate: relevant tests/checks run before handback.

## Receipt Requirements
- `run_id` per execution burst.
- Diff summary and touched-file list.
- Command/test outcomes.
- Decision journal entry with rationale.

## Return-Control Ritual
Pilot Mode ends with:
- concise outcome summary,
- explicit pending approvals,
- clear statement that control has returned to user.

## Conceptual Takeover Triggers (No Runtime Binding Yet)
- "Pilot this task"
- "Take over and execute"
- "Run this mission end-to-end"
- "Finish this branch and hand back"

## Acceptance Criteria
- Pilot Mode is always visible while active.
- User can revoke Pilot instantly.
- Branch-first and verification gates are default for code tasks.
- Every takeover action leaves receipts.
- Control handback is explicit and logged.
