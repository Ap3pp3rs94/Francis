# Francis Control Room Integration Queue

Updated: 2026-07-15

CR-FORGE-006 is promoted locally and awaits the authorized integrated-main push
after the current prior-head GitHub CI run terminates.

| Front | Branch | Worker commit | Worker evidence | Specialist reviews | VERA | ATLAS exact-head validation | Operator gate | State |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CR-FORGE-006 | `codex/forge-safe-delta-export-artifact-plan` | `8131692d`; remediations `10d14689`, `2673cd5e` | 3 focused tests and complete 94-test card suite | SENTINEL/HARBOR pass | VERA pass | post-promotion focused/route/matrix/static checks passed; broad gate delegated to GitHub | integrated-main push authorized; real artifact/export operator-only | `PROMOTED` |
| CR-FORGE-005 | `codex/forge-safe-delta-export-authorization-decision` | `1a68de41`; remediations `17bccd28`, `0a0cfd55` | 6 focused tests and complete 91-test card suite | SENTINEL/HARBOR pass | VERA pass | static gates passed; full pytest interrupted without verdict; post-promotion focused-green | integrated-main push authorized; real decision/export operator-only | `PROMOTED` |
| CR-FORGE-004 | `codex/forge-safe-delta-export-authorization-request` | `9c43bb45`; remediation `44048d85`; main fix `f3cc8c7c` | 6 focused tests and complete 85-test card suite | SENTINEL/HARBOR pass | VERA pass | exact `44048d85` full gate exit `0`; post-promotion focused-green | integrated-main push authorized; real approval/export operator-only | `PROMOTED` |
| CR-FORGE-003 | `codex/forge-safe-delta-export-preflight` | `b5fbb3af`; remediation/main `287a27c8` | 6 focused tests, 2 matrix tests, complete 79-test card suite | SENTINEL/HARBOR pass | VERA pass | exact `287a27c8` full gate exit `0`; post-promotion focused-green | integrated-main push authorized; no production action | `PROMOTED` |
| CR-FORGE-002 | `codex/forge-safe-delta-approval` | reviewed `49893be5`; rebased `e799c857`; main `ff58d6d9` | 18 decision tests and complete 77-test card suite passed | SENTINEL/HARBOR pass | VERA pass | exact `e799c857` full gate exit `0`; post-promotion path fix focused-green | integrated-main push authorized; no production action | `PROMOTED` |
| CR-ARGUS-001 | `codex/argus-game-observer` | `7af273af` | 103 card tests and post-promotion 115-test suite passed | MERIDIAN/HARBOR/SENTINEL pass | VERA pass | promoted; portability and completion readback CI fixes followed | final integrated CI pending | `PROMOTED` |
| CR-LUMEN-001 | `codex/lumen-orb-choreography` | `60070438` | focused suite/Ruff/format/native build/diff-check passed | HARBOR/SENTINEL/ARCHIVIST reject durable sequence/outcome truth | VERA rejected | no further validation until durable contract reassignment | live proof separate; push gated | `BLOCKED` |

Promotion requires an exact worker commit, task-card evidence, required concrete
specialist reviews, independent VERA acceptance, ARCHIVIST traceability where
applicable, and ATLAS certainty. Focused acceptance, the complete affected
card/subsystem suite, changed-path checks, and affected reviews prove the local
candidate. GitHub CI/CodeQL is the normal repository-wide exact-head gate; local
`scripts/check.ps1` is reserved for broad integration, release checkpoints, or
CI divergence diagnosis.
