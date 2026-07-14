# Francis Control Room Operator Queue

Updated: 2026-07-14, sync cycle `CR-20260714-005`

This bounded queue contains only operator-gated decisions. Diagnosis and routine
worker blockers belong on the board. A queued action is not authorization.

| ID | Decision needed | Evidence | Options | ATLAS recommendation | State |
| --- | --- | --- | --- | --- | --- |
| `OPQ-20260714-001` | Push final validated integrated `main` to `origin/main` | operator directed ATLAS to ensure GitHub is updated; current pre-promotion head remains unproved | push only after CR-005, exact rebase proof, local promotion, and post-promotion validation; never push an intermediate docs-only or failed head | use the authorization once the exact integrated head is green, then monitor CI and CodeQL | `AUTHORIZED_PENDING_VALIDATION` |
| `OPQ-20260714-002` | Whether to authorize any real Stage 18 customer request, tenant, candidate review, or approval | ledger says no production customer/tenant/request exists | provide a real bounded request later; keep production empty | keep production empty; worker uses fixtures only | `DEFERRED` |
| `OPQ-20260714-003` | Whether the FORGE exact-type correction requires an exception after two cycles | operator clarified that SENTINEL/VERA proved an existing exact-schema criterion remains unsatisfied at `1ca30a04` | continue inside the current card; no scope/authority exception | reconstitute FORGE and complete only the existing criterion | `RESOLVED_CONTINUE_CURRENT_CARD` |

Tool-state notice, not an operator decision: the goal controller reports the old
roadmap objective as `blocked` but rejects the requested replacement as
unfinished. The repository-backed ATLAS mandate remains active; ATLAS will not
mislabel the old objective complete to bypass the controller.

When an item becomes actionable, its packet must state the exact decision,
evidence, options, recommendation, and risks before ATLAS asks the operator.
