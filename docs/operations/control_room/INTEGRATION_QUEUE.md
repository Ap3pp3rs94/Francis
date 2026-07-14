# Francis Control Room Integration Queue

Updated: 2026-07-14

No branch is currently eligible for promotion. Publishing or pushing any ref is
operator-gated.

| Front | Branch | Worker commit | Worker evidence | Specialist reviews | VERA | ATLAS exact-head validation | Operator gate | State |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CR-ARGUS-001 | `codex/argus-game-observer` | `2e454ba5` | `VAL-003` interrupted known remediation; cycle one active | ATLAS blocked/teaching projection findings; affected reviews only after new hash | preflight only | first integration priority after focused-green hash | push gated | `REMEDIATION_REQUIRED` |
| CR-FORGE-001 | `codex/forge-managed-copies-safe-delta` | `90c4dbe0` | `VAL-002` interrupted known remediation; cycle one active | SENTINEL/MERIDIAN remediation archived; affected reviews only after new hash | preflight only | pending new hash/rebase | no production action; push gated | `REMEDIATION_REQUIRED` |
| CR-LUMEN-001 | `codex/lumen-orb-choreography` | `a1b2c60b` | `VAL-004` interrupted known remediation; cycle one active | HARBOR publication/cardinality/bounds remediation archived | preflight only | pending new hash/rebase | live proof separate; push gated | `REMEDIATION_REQUIRED` |

Promotion requires an exact worker commit, task-card evidence, required concrete
specialist reviews, independent VERA acceptance, ARCHIVIST traceability where
applicable, and ATLAS certainty. Before fast-forward, the branch must be rebased
onto the exact committed local-main Control Room head and the complete card plus
`scripts/check.ps1` must pass on that rebased commit. Pre-rebase evidence is not
sufficient.
