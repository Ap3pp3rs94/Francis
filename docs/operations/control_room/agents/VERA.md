# VERA Seat State

- Role: independent verification and contract review
- Classification: internal read-only reviewer
- Staffing: unstaffed after completed preflight; prior agent
  `019f6100-9955-78f0-abda-5abd175b953a`
- Availability: `RESPONDED`
- Liveness: current cycle `CR-20260714-002`
- Current assignment: preflight completed; await post-remediation exact commits
- Current task card: worker cards define acceptance; VERA does not redefine them
- Branch: read-only inspection only
- Worktree: no implementation worktree
- Contracts in play: all three cards plus repository workflow and ledger evidence
- Known traps: tests are evidence only when they cover the claim; receipts do not
  prove live effects; Windows-only typing must pass Ubuntu; no stage closure claim
- Latest verified evidence: `MSG-20260714-008` and
  `reviews/VERA/CR-20260714-preflight.md`; three first candidate commits now
  exist but all are `REMEDIATION_REQUIRED`
- Unresolved questions: whether each worker fully remediates the routed findings
- Current blocker: post-remediation reviewable commits unavailable
- Dependencies: worker `READY_FOR_REVIEW` reports routed by ATLAS
- Next action: independently map each exact worker commit after remediation to
  code, tests, receipt/readback, runtime cleanup, and portability evidence
- Replacement instruction: remain read-only, write uniquely named reports under
  `control_room/reviews/`, and return remediation to ATLAS rather than editing
