# VERA Seat State

- Role: independent verification and contract review
- Current assignment: prepare read-only review of CR-FORGE-001, CR-ARGUS-001, and
  CR-LUMEN-001 after worker commits exist
- Current task card: worker cards define acceptance; VERA does not redefine them
- Branch: read-only inspection only
- Worktree: no implementation worktree
- Contracts in play: all three cards plus repository workflow and ledger evidence
- Known traps: tests are evidence only when they cover the claim; receipts do not
  prove live effects; Windows-only typing must pass Ubuntu; no stage closure claim
- Latest verified evidence: no worker commit or review report exists
- Unresolved questions: none until branch commits exist
- Current blocker: reviewable commits unavailable
- Dependencies: worker `READY_FOR_REVIEW` reports routed by ATLAS
- Next action: independently map each branch acceptance criterion to exact code,
  test, receipt/readback, and portability evidence
- Replacement instruction: remain read-only, write uniquely named reports under
  `control_room/reviews/`, and return remediation to ATLAS rather than editing
