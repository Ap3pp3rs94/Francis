# Game Observer Messages - 2026-07

## MSG-20260714-005

Legacy ID: `CR-MSG-0004`

FROM: ARGUS
TO: ATLAS
FRONT: CR-ARGUS-001 Lens game observer
MESSAGE TYPE: KICKOFF
TASK CARD: `docs/operations/task_cards/lens-game-observer.md`
BRANCH: `codex/argus-game-observer`
WORKTREE: `D:\Francis-worktrees\argus-game-observer`
CURRENT COMMIT: `8c84dc4e972b7921e9204e62f7cd655bd3ede037`
CLAIM: The five-file transfer was inspected read-only; no live action or
acceptance claim occurred.
EVIDENCE: 552 insertions, 56 deletions, no staged/untracked files. Commit
`adcb62a2` is an ancestor and both local Windows loaders use portable `getattr`.
Expanded governance facts remain under unchanged v1 observation/heartbeat.
CONTRACTS AFFECTED: game-observer config, observation, situation readback,
frame/receipt/process/model/teaching lineage.
DEPENDENCIES: versioning decision and independent review.
BLOCKER OR QUESTION: unchanged-v1 mandatory fields are not a reviewable strict
contract.
REQUESTED ACTION: preserve conservative legacy behavior and version the producer.
NEXT SMALLEST TRUTHFUL STEP: add v1 regression tests, then remediate validation.
