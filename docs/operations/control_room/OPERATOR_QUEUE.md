# Francis Control Room Operator Queue

Updated: 2026-07-14, sync cycle `CR-20260714-002`

This bounded queue contains only operator-gated decisions. Diagnosis and routine
worker blockers belong on the board. A queued action is not authorization.

| ID | Decision needed | Evidence | Options | ATLAS recommendation | State |
| --- | --- | --- | --- | --- | --- |
| `OPQ-20260714-001` | Whether to push the local Control Room sync to `origin/main` | local commit pending; CI `29340258995` for prior head pending at last read | push after exact local validation; keep local only | keep local until `scripts/check.ps1` passes and current GitHub CI is read | `NOT_READY` |
| `OPQ-20260714-002` | Whether to authorize any real Stage 18 customer request, tenant, candidate review, or approval | ledger says no production customer/tenant/request exists | provide a real bounded request later; keep production empty | keep production empty; worker uses fixtures only | `DEFERRED` |

Tool-state notice, not an operator decision: the goal controller reports the old
roadmap objective as `blocked` but rejects the requested replacement as
unfinished. The repository-backed ATLAS mandate remains active; ATLAS will not
mislabel the old objective complete to bypass the controller.

When an item becomes actionable, its packet must state the exact decision,
evidence, options, recommendation, and risks before ATLAS asks the operator.
