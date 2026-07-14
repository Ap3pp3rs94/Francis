# Francis Control Room Roster

Updated: 2026-07-14, sync cycle `CR-20260714-002`

Call signs are durable seats, not proof of active agents. A replacement inherits
the seat file, task card, branch/worktree, messages, contracts, evidence,
runtime lease, blocker, and next action.

| Seat | Role | Classification | Mutation mode | Staffed | Availability | Assignment | Liveness | Activity evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ATLAS | Build Manager and integrator | internal | local-main operations/docs; bounded integration only | yes | `ACTIVE` | Control Room sync/integration | current cycle | local session; Control Room head `8c84dc4e` |
| FORGE | systems and capability worker | internal | mutating slot 1 | yes | `ACTIVE` | CR-FORGE-001 | current cycle | KICKOFF `MSG-20260714-004`; agent `019f6100-96ab-7631-98b0-5b92909186e0` |
| ARGUS | observation and instrumentation worker | internal | mutating slot 2 | yes | `ACTIVE` | CR-ARGUS-001 | current cycle | KICKOFF `MSG-20260714-005`; agent `019f6100-97e3-7e23-a5c7-255ec738fd9b` |
| LUMEN | interaction and choreography worker | internal | mutating slot 3 | yes | `ACTIVE` | CR-LUMEN-001 | current cycle | KICKOFF `MSG-20260714-006`; agent `019f6100-9898-7353-9359-ed4727e2a4cb` |
| VERA | internal verification and contract reviewer | internal | read-only | yes | `RESPONDED` | preflight review of three fronts | current cycle | `MSG-20260714-008`; `reviews/VERA/CR-20260714-preflight.md`; agent `019f6100-9955-78f0-abda-5abd175b953a` |
| CLAUDE | external auditor and substrate verifier | external | read-only | no | `UNVERIFIED` | no active audit | not applicable | no verified bridge or audit; inventory candidate unverified |
| MERIDIAN | architecture and contract steward | internal | read-only/advisory | no | `READY_UNSTAFFED` | queued concrete contract reviews | not applicable | seat file only; no review report |
| SENTINEL | security, tenancy, authority reviewer | internal | read-only/advisory | no | `READY_UNSTAFFED` | queued front-specific reviews | not applicable | seat file only; no review report |
| HARBOR | CI, portability, integration steward | internal | read-only/advisory | no | `READY_UNSTAFFED` | queued exact-head and CI reviews | not applicable | `MSG-20260714-007`; no review report |
| ARCHIVIST | receipts, ledger, operational-memory steward | internal | read-only/advisory | no | `READY_UNSTAFFED` | queued evidence traceability | not applicable | transfer handoff; no review report |
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
