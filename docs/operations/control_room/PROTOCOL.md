# Francis Control Room Protocol

## Ownership

ATLAS is the sole writer for aggregate Control Room state:

- `docs/operations/SESSION_BRIEF.md`
- `ROSTER.md`
- `BOARD.md`
- `MESSAGE_LOG.md`
- `DECISIONS.md`
- `INTEGRATION_QUEUE.md`

Workers submit structured reports to ATLAS. Workers may add uniquely named
evidence/handoff artifacts only when their task card permits it. VERA writes
uniquely named review reports; ATLAS integrates their disposition into aggregates.

## Assignment Rules

- Maximum three concurrent mutating fronts.
- One worker, task card, `codex/*` branch, and worktree per front.
- Workers never write `main`, share implementation worktrees, merge themselves,
  or edit another front's scope without a revised card.
- VERA is read-only by default and does not consume a mutating slot.
- ATLAS may make only small, necessary, immediately validated integration fixes.

## Front States

Allowed states:

`QUEUED`, `READY`, `ACTIVE`, `BLOCKED`, `READY_FOR_REVIEW`, `IN_REVIEW`,
`REMEDIATION_REQUIRED`, `READY_FOR_PROMOTION`, `PROMOTED`, `CANCELLED`.

`DONE` is forbidden. State transitions require evidence in `MESSAGE_LOG.md` and
an updated board entry.

## Required Worker Reports

Workers report assignment acceptance, initial inspection, first material
finding, dependencies, contract collisions, blockers, acceptance evidence,
review readiness, remediation completion, and handoff/reassignment.

Every material report uses exactly these fields:

```text
FROM:
TO:
FRONT:
MESSAGE TYPE:
TASK CARD:
BRANCH:
WORKTREE:
CURRENT COMMIT:
CLAIM:
EVIDENCE:
CONTRACTS AFFECTED:
DEPENDENCIES:
BLOCKER OR QUESTION:
REQUESTED ACTION:
NEXT SMALLEST TRUTHFUL STEP:
```

Allowed message types: `KICKOFF`, `FINDING`, `DEPENDENCY`, `QUESTION`,
`CONTRACT_COLLISION`, `BLOCKER`, `EVIDENCE`, `READY_FOR_REVIEW`,
`REVIEW_RESULT`, `DECISION`, `HANDOFF`.

## Review Routing

1. Worker reports `READY_FOR_REVIEW at <commit>`.
2. ATLAS verifies branch/worktree identity and task-card scope.
3. VERA independently maps every acceptance criterion to exact evidence.
4. Findings return to the same worker unless ATLAS creates a separate card.
5. ATLAS runs required validation, including `scripts/check.ps1`.
6. Certain routine work may be fast-forwarded to `main`; uncertain promotion is
   escalated to the operator.
7. Post-merge reachability, checks, readback, receipts, and ledger truth are
   verified before the front becomes `PROMOTED`.

## Escalation

Operator-only: governance/authority changes, legal/license text, secrets,
credentials, public releases/settings, stage closure, destructive/irreversible
operations, live process changes outside an explicit card, and any merge ATLAS
is not certain about.

## Handoff Minimum

A replacement packet names the seat, front, card, branch, worktree, latest
verified commit, contracts, validation, findings, dependencies, blocker, and next
smallest truthful action. No handoff may depend on chat memory alone.
