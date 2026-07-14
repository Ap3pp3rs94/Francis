# Francis Control Room Dependency Graph

Updated: 2026-07-14T10:24:54-05:00

## Critical Path

The ledger's first Stage 18 production gate is a real operator-supplied managed-
copy request. That external fact is unavailable and Francis must not invent it.
`CR-FORGE-001` is therefore the highest-priority executable internal engineering
path, not evidence that the production gate closed. `CR-ARGUS-001` and
`CR-LUMEN-001` are approved cross-stage hardening fronts with disjoint write
sets; they do not block FORGE integration.

Integration order is FORGE first after its authorized final remediation and
exact-head review. ARGUS and LUMEN are parked on explicit contract-ownership
scope blockers and are not promotion candidates.
Every promotion remains local-only until the operator authorizes a push.

## Front Graph

| Front | Objective / priority | Exact worker commit | Dependencies | Downstream consumers | Unresolved contracts | Validation | Required review | Operator gates | Next executable action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CR-FORGE-001` | Stage 18 hash-only safe-delta candidate review; sole active internal critical path | `cd9cd50422115761a2340e3d322b449516f85b0d` | provision receipt, isolation-owned guarded subpath, tenant policy, actor scope | Stage 18 approval/export work after separate authority | canonical path-owner reuse; exact full-fingerprint readback; independent governance/type/production-empty/link evidence | focused worker suites pass; pre-rebase specialist review blocks promotion | MERIDIAN, HARBOR, and VERA findings routed; affected exact-delta review only after new hash | tenancy/authority weakening, production data/action, promotion uncertainty, push | FORGE executes final `CR-DEC-0012` cycle; no third remediation cycle |
| `CR-ARGUS-001` | game-observer readback truth | `683134a7cccd6b4dd1b1cd1604d2641615f07307` | teaching recorder v2 compatibility, strict heartbeat projection, receipt lineage | Lens situation model and semantic observer use | task-card scope excludes the apprenticeship consumer required by the v2 producer | focused suite passed; exact full gate not reusable; VERA/SENTINEL rejected | new task-card scope required before remediation | authority/live-observer activation, uncertain promotion, push | parked; do not validate or expand until reassigned |
| `CR-LUMEN-001` | loss-resistant native right-click delivery and ring truth | `600704383d71c072b29a29e4061c86977f38a245` | durable sequence allocator/outcome owner, overlay queue, visual-lock parity | operator-facing Orb local UI; no broader choreography claim | restart-safe global sequence and producer-failure readback need new durable schema ownership | focused suite/build passed; full gate interrupted after review blockers | HARBOR, VERA, SENTINEL, ARCHIVIST rejected | live Orb use, shell/authority change, uncertain promotion, push | parked; reassign durable allocator/outcome contract before edits |

## Shared Integration Dependencies

- Current local `main`: `8a5ca378a854b29eb0ca7adcad591e2a57f1a653`.
- Open Control Room sync `CR-20260714-004` records the FORGE scope revision; its
  commit becomes the exact rebase target for the next FORGE hash.
- Exact rebased acceptance and `scripts/check.ps1` evidence supersede all
  pre-rebase results.
- GitHub CI `29340258995` applies only to remote `8c84dc4e`, not local Control
  Room or worker commits.
- Unknown `src/francis/cli.py` work is excluded from every front and cannot enter
  an integration candidate without a new owner/card.
