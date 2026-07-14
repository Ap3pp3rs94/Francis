# Francis Control Room Roster

Updated: 2026-07-14, sync cycle `CR-20260714-005`

Call signs are durable seats, not proof of active agents. A replacement inherits
the seat file, task card, branch/worktree, messages, contracts, evidence,
runtime lease, blocker, and next action.

| Seat | Role | Classification | Mutation mode | Staffed | Availability | Assignment | Liveness | Activity evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ATLAS | Build Manager and integrator | internal | local-main operations/docs; bounded integration only | yes | `ACTIVE` | Control Room sync/integration | current cycle | local session; CR-005 parent `6e883d1d`; `VAL-028` passed on `cdfc4a23` |
| FORGE | systems and capability worker | internal | mutating slot 1 | no | `READY_FOR_PROMOTION` | CR-FORGE-001 correction delivered and pre-rebase gate passed | unavailable after delivery | correction `24658090`; SENTINEL/VERA pass; integration `cdfc4a23`; `VAL-028` exit `0` |
| ARGUS | observation and instrumentation worker | internal | mutating slot 2 | no | `BLOCKED` | CR-ARGUS-001 parked on teaching-consumer scope | unavailable | prior handle `019f6100-97e3-7e23-a5c7-255ec738fd9b` is `not_found`; `683134a7`; VERA/SENTINEL rejected |
| LUMEN | interaction and choreography worker | internal | mutating slot 3 | no | `BLOCKED` | CR-LUMEN-001 parked on durable sequence/outcome ownership | unavailable | prior handle `019f6100-9898-7353-9359-ed4727e2a4cb` is `not_found`; `60070438`; exact reviewers rejected |
| VERA | internal verification and contract reviewer | internal | read-only | no | `RESPONDED` | final FORGE review archived | unavailable | `reviews/VERA/CR-20260714-forge-final.md`; prior handle `019f6100-9955-78f0-abda-5abd175b953a` is `not_found` |
| CLAUDE | external auditor and substrate verifier | external | read-only | no | `UNVERIFIED` | no active audit | not applicable | no verified bridge or audit; inventory candidate unverified |
| MERIDIAN | architecture and contract steward | internal | read-only/advisory | no | `RESPONDED` | final FORGE review archived | unavailable | `reviews/MERIDIAN/CR-20260714-forge-final.md`; prior handle `019f613f-ae1a-7643-ba3d-b3793cc79233` is `not_found` |
| SENTINEL | security, tenancy, authority reviewer | internal | read-only/advisory | no | `RESPONDED` | final FORGE review archived | unavailable | `reviews/SENTINEL/CR-20260714-forge-final.md`; prior handle `019f612d-46f2-78b1-bb84-2942081c86c1` is `not_found` |
| HARBOR | CI, portability, integration steward | internal | read-only/advisory | no | `RESPONDED` | `cdfc4a23` affected-delta review passed | current cycle | handle `019f623e-597e-7040-be36-f6d93164407d` completed and released; review archived |
| ARCHIVIST | receipts, ledger, operational-memory steward | internal | read-only/advisory | no | `RESPONDED` | CR-005 reconciliation completed | current cycle | handle `019f623d-ae53-79c0-9645-abbfb6051d02` completed and released; reconciliation evidence retained in session |
| ECHO | collaboration and handoff steward | internal | read-only/advisory | no | `READY_UNSTAFFED` | queued routing/handoff checks | not applicable | seat file only; no review report |

## Replacement Instructions

1. Read `AGENTS.md`, the completion ledger, `SESSION_BRIEF.md`, this roster, the
   board, protocol, message index, affected shards, decisions, and seat file.
2. Verify branch, worktree, commit, runtime lease, process/port ownership, and
   validation directly.
3. Resume only the recorded next action and report in the current sync cycle.
4. Never infer staffing, external availability, or completed work from a seat name.

Liveness enforcement is defined in `PROTOCOL.md`: one missed active sync cycle is
`STALE`; two consecutive misses make the current session `PRESUMED_DEAD` and
trigger preservation and replacement without deleting uncertain work.
