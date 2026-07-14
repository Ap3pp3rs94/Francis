# Orb Choreography Messages - 2026-07

## MSG-20260714-006

Legacy ID: `CR-MSG-0003`

FROM: LUMEN
TO: ATLAS
FRONT: CR-LUMEN-001 Orb right-click delivery / visual-lock alignment
MESSAGE TYPE: KICKOFF
TASK CARD: `docs/operations/task_cards/orb-visual-choreography.md`
BRANCH: `codex/lumen-orb-choreography`
WORKTREE: `D:\Francis-worktrees\lumen-orb-choreography`
CURRENT COMMIT: `8c84dc4e972b7921e9204e62f7cd655bd3ede037`
CLAIM: The transfer is a native right-click queue plus ring-count alignment,
not broad state-to-choreography implementation; no live action occurred.
EVIDENCE: five in-scope unstaged files, `git diff --check` exit 0, 326 insertions
and 123 deletions.
CONTRACTS AFFECTED: native renderer request/status, overlay queue/readback,
visual lock, shell no-input/no-authority invariants.
DEPENDENCIES: revised bounded card and independent review.
BLOCKER OR QUESTION: queue ordering, bounds, deduplication, stale handling, and
all ring-count truth surfaces require proof.
REQUESTED ACTION: retain LUMEN ownership under the corrected card.
NEXT SMALLEST TRUTHFUL STEP: add fail-closed queue and ring parity tests first.
