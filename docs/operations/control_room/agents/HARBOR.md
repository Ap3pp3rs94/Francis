# HARBOR Seat State

- Role: CI, portability, and integration steward
- Classification: internal, read-only/advisory by default
- Staffing: unstaffed
- Availability: `READY_UNSTAFFED`
- Liveness: not applicable while unstaffed
- Current assignment: queued exact-head portability reviews and bootstrap/CI
  extra-drift finding from MSG-20260714-007
- Current task card: worker cards name review triggers; bootstrap drift needs a
  future bounded card if it remains reproducible
- Branch/worktree: none
- Contracts in play: GitHub CI, Windows/Ubuntu portability, collection, branch
  base, exact promoted head
- Known trap: verified commit `adcb62a2` uses
  `getattr(ctypes, "WinDLL", None)` for portable Windows-only APIs
- Latest verified evidence: CodeQL `29340258957` passed; CI `29340258995` was in
  progress at last read; first local full gate was invalid due missing `bridge`
- Current blocker: no exact-head local gate result for CR-20260714-002
- Next action: verify CI and exact-head evidence after the local sync commit
- Replacement instruction: verify the tested hash equals the candidate hash
  before certifying integration readiness
