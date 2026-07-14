# Francis Control Room Integration Queue

Updated: 2026-07-14

FORGE is the active promotion candidate but is not yet eligible for promotion.
Publishing or pushing any ref is operator-gated.

| Front | Branch | Worker commit | Worker evidence | Specialist reviews | VERA | ATLAS exact-head validation | Operator gate | State |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CR-FORGE-001 | `codex/forge-managed-copies-safe-delta` | worker `24658090`; integration `cdfc4a23` | correction focused suite/Ruff/format/mypy/diff-check passed | SENTINEL and HARBOR affected-delta passes | exact-type correction pass | `VAL-20260714-028` full gate exit `0`; rebase proof pending | no production action; final validated main push authorized | `READY_FOR_PROMOTION` |
| CR-ARGUS-001 | `codex/argus-game-observer` | `683134a7` | focused suite/Ruff/format/mypy/diff-check passed | MERIDIAN/HARBOR static pass; SENTINEL blocks teaching/readback composition | VERA rejected | no further validation until scope reassignment | push gated | `BLOCKED` |
| CR-LUMEN-001 | `codex/lumen-orb-choreography` | `60070438` | focused suite/Ruff/format/native build/diff-check passed | HARBOR/SENTINEL/ARCHIVIST reject durable sequence/outcome truth | VERA rejected | no further validation until durable contract reassignment | live proof separate; push gated | `BLOCKED` |

Promotion requires an exact worker commit, task-card evidence, required concrete
specialist reviews, independent VERA acceptance, ARCHIVIST traceability where
applicable, and ATLAS certainty. Before fast-forward, the branch must be rebased
onto the exact committed local-main Control Room head and the complete card plus
`scripts/check.ps1` must pass on that rebased commit. Pre-rebase evidence is not
sufficient.
