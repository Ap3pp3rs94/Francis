# Away Mode

## Night Shift Operator Behavior
Away Mode is optional autonomous continuity for approved scopes. Francis should:
- advance active missions,
- run observer/reactor actions,
- stage low-risk improvements,
- prepare approval packets for higher-risk operations,
- keep journals and receipts coherent.

## Can Do (Without Additional Approval)
- Read/observe within scope.
- Run scheduled observer scans.
- Tick queued missions within approved policy envelope.
- Stage forge artifacts for review.
- Produce summaries and decision packets.

## Must Queue for User Approval
- High-risk mutating actions.
- Promotions/deployments beyond pre-approval envelope.
- Scope expansion requests.
- Any action blocked by policy/RBAC.

## Come-Back Briefing Format
- What advanced (missions, incidents, staged capabilities).
- What changed (files/artifacts) with receipts.
- What failed and why.
- What is waiting for approval.
- Recommended first 1-3 actions for the user.

## Acceptance Criteria
- Away Mode produces ordered progress, not uncontrolled churn.
- All actions remain within declared scope and mode policy.
- Pending approvals are explicit and prioritized.
- Return briefing is concise, evidence-linked, and actionable.
- Every away-mode run is traceable by `run_id` and ledger/journal receipts.
