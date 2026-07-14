# HARBOR Seat State

- Role: CI, portability, and integration steward
- Classification: internal, read-only/advisory by default
- Staffing: unstaffed after completed review; prior agent
  `019f6119-b5ef-7721-91c1-5c628ce3ec61`
- Availability: `RESPONDED`
- Liveness: responded in `CR-20260714-003`; session released
- Current assignment: environment root cause and LUMEN preflight archived; await
  exact post-remediation candidates
- Current task card: worker cards name the next concrete portability trigger
- Branch/worktree: none
- Contracts in play: GitHub CI, Windows/Ubuntu portability, collection, branch
  base, exact promoted head
- Known trap: verified commit `adcb62a2` uses
  `getattr(ctypes, "WinDLL", None)` for portable Windows-only APIs
- Latest verified evidence: `reviews/HARBOR/CR-20260714-exact-head-gate-review.md`
  and `reviews/HARBOR/CR-20260714-lumen-preflight.md`; corrupt Typer payload was
  proven/repaired, but the later static-pass receipt is incomplete; LUMEN remains
  `REMEDIATION_REQUIRED`
- Current blocker: exact-snapshot and worker pytest plus GitHub Windows pytest remain pending;
  concurrent `src/francis/cli.py` candidate is unassigned
- Next action: remain unstaffed until a concrete worker integration or
  portability review is routed
- Replacement instruction: verify the tested hash equals the candidate hash
  before certifying integration readiness
