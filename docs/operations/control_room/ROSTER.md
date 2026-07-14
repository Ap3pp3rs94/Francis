# Francis Control Room Roster

Updated: 2026-07-14, sync cycle `CR-20260714-004`

Call signs are durable seats, not proof of active agents. A replacement inherits
the seat file, task card, branch/worktree, messages, contracts, evidence,
runtime lease, blocker, and next action.

| Seat | Role | Classification | Mutation mode | Staffed | Availability | Assignment | Liveness | Activity evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ATLAS | Build Manager and integrator | internal | local-main operations/docs; bounded integration only | yes | `ACTIVE` | Control Room sync/integration | current cycle | local session; local Control Room head `d5516a54`; `VAL-20260714-001` running |
| FORGE | systems and capability worker | internal | mutating slot 1 | no | `REMEDIATION_REQUIRED` | CR-FORGE-001 final cycle prepared | completed/released | resumable agent `019f6100-96ab-7631-98b0-5b92909186e0`; `cd9cd504`; `VAL-014` focused pass; `CR-DEC-0012` |
| ARGUS | observation and instrumentation worker | internal | mutating slot 2 | no | `BLOCKED` | CR-ARGUS-001 parked on teaching-consumer scope | completed/released | resumable agent `019f6100-97e3-7e23-a5c7-255ec738fd9b`; `683134a7`; VERA/SENTINEL rejected |
| LUMEN | interaction and choreography worker | internal | mutating slot 3 | no | `BLOCKED` | CR-LUMEN-001 parked on durable sequence/outcome ownership | completed/released | resumable agent `019f6100-9898-7353-9359-ed4727e2a4cb`; `60070438`; exact reviewers rejected |
| VERA | internal verification and contract reviewer | internal | read-only | no | `RESPONDED` | preflight archived; await worker commits | last cycle | `MSG-20260714-008`; `reviews/VERA/CR-20260714-preflight.md`; prior agent `019f6100-9955-78f0-abda-5abd175b953a` |
| CLAUDE | external auditor and substrate verifier | external | read-only | no | `UNVERIFIED` | no active audit | not applicable | no verified bridge or audit; inventory candidate unverified |
| MERIDIAN | architecture and contract steward | internal | read-only/advisory | no | `RESPONDED` | FORGE preflight archived; await remediation | CR-003 | `reviews/MERIDIAN/CR-20260714-forge-preflight.md`; prior agent `019f613f-ae1a-7643-ba3d-b3793cc79233` |
| SENTINEL | security, tenancy, authority reviewer | internal | read-only/advisory | no | `RESPONDED` | FORGE review archived; await remediation | CR-003 | `reviews/SENTINEL/CR-20260714-forge-preflight.md`; prior agent `019f612d-46f2-78b1-bb84-2942081c86c1` |
| HARBOR | CI, portability, integration steward | internal | read-only/advisory | no | `RESPONDED` | environment and LUMEN reviews archived; await remediation | CR-003 | `reviews/HARBOR/CR-20260714-exact-head-gate-review.md`; `reviews/HARBOR/CR-20260714-lumen-preflight.md`; prior agent `019f6119-b5ef-7721-91c1-5c628ce3ec61` |
| ARCHIVIST | receipts, ledger, operational-memory steward | internal | read-only/advisory | no | `RESPONDED` | CR-003 precommit audited; corrections applied | CR-003 | `reviews/ARCHIVIST/CR-20260714-003-precommit.md`; prior agent `019f6144-d5f2-7923-80c9-ae0b3f2bfce4` |
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
