# Francis Control Room Dependency Graph

Updated: 2026-07-14T16:29:41-05:00

## Critical Path

The ledger's first Stage 18 production gate is a real operator-supplied managed-
copy request. That external fact is unavailable and Francis must not invent it.
`CR-FORGE-001` is therefore the highest-priority executable internal engineering
path, not evidence that the production gate closed. `CR-ARGUS-001` and
`CR-LUMEN-001` are approved cross-stage hardening fronts with disjoint write
sets; they do not block FORGE integration.

Integration order remains FORGE first. `OPQ-20260714-003` is resolved, correction
`24658090` passed affected review, and integration head `cdfc4a23` passed its full
gate. ARGUS and LUMEN remain parked and are not promotion candidates.
Every promotion remains local-only until the operator authorizes a push.

## Front Graph

| Front | Objective / priority | Exact worker commit | Dependencies | Downstream consumers | Unresolved contracts | Validation | Required review | Operator gates | Next executable action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CR-FORGE-001` | Stage 18 hash-only safe-delta candidate review; nearest promotion candidate | worker `246580901b145a7f1f59d9c85d199ffdfdf536d8`; integration `cdfc4a23fe030b4e31dbf3b067c39d3e3daae1f8` | existing provision/isolation/policy/scope contracts; exact rebased-head validation | Stage 18 approval/export work after separate authority | no open product-contract defect; rebase proof remains | focused suite/Ruff/format/mypy/diff-check pass; SENTINEL/VERA/HARBOR affected reviews pass; `VAL-028` full gate exit `0` | exact rebased-diff review after CR-005 | production facts/actions, uncertain promotion; push authorized only after validation | commit CR-005; rebase and re-prove |
| `CR-ARGUS-001` | game-observer readback truth | `683134a7cccd6b4dd1b1cd1604d2641615f07307` | teaching recorder v2 compatibility, strict heartbeat projection, receipt lineage | Lens situation model and semantic observer use | task-card scope excludes the apprenticeship consumer required by the v2 producer | focused suite passed; exact full gate not reusable; VERA/SENTINEL rejected | new task-card scope required before remediation | authority/live-observer activation, uncertain promotion, push | parked; do not validate or expand until reassigned |
| `CR-LUMEN-001` | loss-resistant native right-click delivery and ring truth | `600704383d71c072b29a29e4061c86977f38a245` | durable sequence allocator/outcome owner, overlay queue, visual-lock parity | operator-facing Orb local UI; no broader choreography claim | restart-safe global sequence and producer-failure readback need new durable schema ownership | focused suite/build passed; full gate interrupted after review blockers | HARBOR, VERA, SENTINEL, ARCHIVIST rejected | live Orb use, shell/authority change, uncertain promotion, push | parked; reassign durable allocator/outcome contract before edits |

Post-FORGE order: revise and rebase ARGUS first. MERIDIAN review
`reviews/MERIDIAN/CR-20260714-post-forge-sequencing.md` bounds that revision to
explicit game-observation v1/v2 teaching-consumer compatibility and direct
composition proof. LUMEN remains parked until a separate durable sequence and
outcome owner is justified.

## Shared Integration Dependencies

- CR-005 local-`main` parent:
  `6e883d1d19a18d157ed99799d598a7f8285771fd`; resolve the containing sync
  commit live.
- Open Control Room sync `CR-20260714-005` records the resolved operator decision,
  correction evidence, integration delta, and passed pre-rebase full gate.
- Exact rebased acceptance and `scripts/check.ps1` evidence supersede all
  pre-rebase results.
- GitHub CI `29340258995` succeeded but applies only to remote `8c84dc4e`, not
  local Control Room or worker commits.
- Unknown `src/francis/cli.py` work is excluded from every front and cannot enter
  an integration candidate without a new owner/card.
