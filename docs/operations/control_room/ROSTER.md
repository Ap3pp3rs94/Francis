# Francis Control Room Roster

Updated: 2026-07-14

## Operating Rule

Central coordination. Isolated execution. Evidence-backed integration.

Call signs are durable seats. A replacement session inherits the seat file,
current task card, branch, worktree, Control Room messages, contracts, evidence,
blockers, and next action.

| Seat | Charter | Current assignment | Branch | Worktree | Availability |
| --- | --- | --- | --- | --- | --- |
| ATLAS | Management, sequencing, review, integration | Control Room activation | `main` | `D:\Francis` | ACTIVE |
| FORGE | Governed backend systems and durable receipts | Managed-copy safe-delta candidate review | `codex/forge-managed-copies-safe-delta` | `D:\Francis-worktrees\forge-managed-copies-safe-delta` | QUEUED |
| ARGUS | Observation, instrumentation, and readback truth | Lens game observer | `codex/argus-game-observer` | `D:\Francis-worktrees\argus-game-observer` | QUEUED |
| LUMEN | Orb interaction, visual behavior, and choreography | Orb visual/choreography | `codex/lumen-orb-choreography` | `D:\Francis-worktrees\lumen-orb-choreography` | QUEUED |
| VERA | Independent verification and contract review | Awaiting first worker evidence | read-only | no implementation worktree | READY |

## Replacement Instructions

1. Read `AGENTS.md`, `docs/operations/COMPLETION_LEDGER.md`, and
   `docs/operations/SESSION_BRIEF.md`.
2. Read `BOARD.md`, `MESSAGE_LOG.md`, `DECISIONS.md`, and the seat file under
   `agents/`.
3. Verify the recorded branch, worktree, commit, and validation state directly.
4. Resume only the recorded next smallest truthful action.
5. Report material changes using `PROTOCOL.md`; never rely on chat memory alone.
