# ATLAS / Operator Messages - 2026-07

## MSG-20260714-001

FROM: OPERATOR
TO: ATLAS
FRONT: Francis Control Room activation
MESSAGE TYPE: KICKOFF
TASK CARD: Control Room mandate
BRANCH: `main`
WORKTREE: `D:\Francis`
CURRENT COMMIT: verify against repository truth
CLAIM: ATLAS is the durable Build Manager; FORGE, ARGUS, and LUMEN own no more
than three isolated mutating fronts; VERA independently reviews; repository
state must survive agent replacement.
EVIDENCE: operator directive dated 2026-07-14; initial Control Room commit
`8c84dc4e972b7921e9204e62f7cd655bd3ede037`.
CONTRACTS AFFECTED: repository workflow, task cards, review, promotion, handoff.
DEPENDENCIES: repo-truth verification and exact worktree isolation.
BLOCKER OR QUESTION: none.
REQUESTED ACTION: activate and continuously operate the named Control Room.
NEXT SMALLEST TRUTHFUL STEP: externalize current state and verify each seat.

## MSG-20260714-002

FROM: OPERATOR
TO: ATLAS
FRONT: Francis Control Room operating protocol
MESSAGE TYPE: DECISION
TASK CARD: Control Room addendum
BRANCH: `main`
WORKTREE: `D:\Francis`
CURRENT COMMIT: `8c84dc4e972b7921e9204e62f7cd655bd3ede037`
CLAIM: The addendum controls where it conflicts: Control Room updates require
local-main docs-only commits; pushes and other listed gates remain operator-only;
message logs are sharded; runtime access requires leases; seat liveness is
numeric; CLAUDE and specialist seats are durable but may not be simulated.
EVIDENCE: operator addendum dated 2026-07-14.
CONTRACTS AFFECTED: Control Room durability, runtime isolation, escalation,
liveness, review routing, promotion.
DEPENDENCIES: CR-20260714-002 protocol sync.
BLOCKER OR QUESTION: goal-controller replacement was requested separately; the
controller retained the already-blocked prior goal and rejected replacement as
unfinished.
REQUESTED ACTION: implement the addendum and do not push without approval.
NEXT SMALLEST TRUTHFUL STEP: commit the reconciled docs-only sync locally.

## MSG-20260714-009

FROM: ATLAS
TO: OPERATOR
FRONT: Control Room operational hardening
MESSAGE TYPE: DECISION
TASK CARD: Control Room addendum
BRANCH: `main`
WORKTREE: `D:\Francis`
CURRENT COMMIT: pre-commit sync state based on `8c84dc4e`
CLAIM: A precise sync-cycle boundary, bounded operator decision queue, and
bounded evidence index are required to make liveness and gated actions auditable.
EVIDENCE: addendum liveness/push/evidence requirements and current pending CI,
goal-controller, and archive state.
CONTRACTS AFFECTED: liveness, escalation, evidence traceability.
DEPENDENCIES: local docs-only commit `CR-20260714-002`.
BLOCKER OR QUESTION: none; these are routine operating controls and confer no
product authority.
REQUESTED ACTION: record the additions; retain operator control of every gate.
NEXT SMALLEST TRUTHFUL STEP: validate and commit the exact operational diff.
