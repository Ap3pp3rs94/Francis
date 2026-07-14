# Francis Control Room Integration Queue

Updated: 2026-07-14

No branch is currently eligible for promotion. Publishing or pushing any ref is
operator-gated.

| Front | Branch | Worker commit | Worker evidence | Specialist reviews | VERA | ATLAS exact-head validation | Operator gate | State |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CR-FORGE-001 | `codex/forge-managed-copies-safe-delta` | unverified | unverified | pending concrete card questions | preflight findings routed; acceptance pending | pending | no production action; push gated | NOT ELIGIBLE |
| CR-ARGUS-001 | `codex/argus-game-observer` | unverified | unverified | pending concrete card questions | preflight findings routed; acceptance pending | pending | push gated | NOT ELIGIBLE |
| CR-LUMEN-001 | `codex/lumen-orb-choreography` | unverified | unverified | pending concrete card questions | preflight findings routed; acceptance pending | pending | live proof separate; push gated | NOT ELIGIBLE |

Promotion requires an exact worker commit, task-card evidence, required concrete
specialist reviews, independent VERA acceptance, ARCHIVIST traceability where
applicable, and ATLAS certainty. Before fast-forward, the branch must be rebased
onto the exact committed local-main Control Room head and the complete card plus
`scripts/check.ps1` must pass on that rebased commit. Pre-rebase evidence is not
sufficient.
