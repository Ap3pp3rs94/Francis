# Francis Control Room Runtime Leases

Updated: 2026-07-14T09:37:19-05:00

Runtime access is denied unless a current task card explicitly grants it. A
worktree does not isolate runtime state. The default operator ports `8000`,
`8787`, and `5173` are reserved and are never worker defaults.

At lease acquisition, worker ports had no listeners and the assigned data
directories did not exist. Port `5173` had an unknown listener owned by PID
`12780`; it is operator-reserved and must not be stopped or inspected by a
worker merely to acquire a port.

| Lease | Seat | Front | Task card | Branch / worktree | State directories | API / overlay / frontend ports | Permitted services | Real Orb | Processes | Acquired | Cleanup evidence | Release state |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `LEASE-FORGE-001` | FORGE | CR-FORGE-001 | `task_cards/managed-copy-safe-delta.md` | `codex/forge-managed-copies-safe-delta` / `D:\Francis-worktrees\forge-managed-copies-safe-delta` | `FRANCIS_DATA_DIR=D:\Francis-runtime-leases\forge-managed-copies-safe-delta\data` | `18001` / `18781` / `15171` | none; test processes only | denied | none | 2026-07-14T09:37:19-05:00 | ports free; state root absent | `ACQUIRED_IDLE` |
| `LEASE-ARGUS-001` | ARGUS | CR-ARGUS-001 | `task_cards/lens-game-observer.md` | `codex/argus-game-observer` / `D:\Francis-worktrees\argus-game-observer` | `FRANCIS_DATA_DIR=D:\Francis-runtime-leases\argus-game-observer\data` | `18002` / `18782` / `15172` | none; test processes only | denied | none | 2026-07-14T09:37:19-05:00 | ports free; state root absent | `ACQUIRED_IDLE` |
| `LEASE-LUMEN-001` | LUMEN | CR-LUMEN-001 | `task_cards/orb-visual-choreography.md` | `codex/lumen-orb-choreography` / `D:\Francis-worktrees\lumen-orb-choreography` | `FRANCIS_DATA_DIR=D:\Francis-runtime-leases\lumen-orb-choreography\data` | `18003` / `18783` / `15173` | none; tests and compile only | denied | none | 2026-07-14T09:37:19-05:00 | ports free; state root absent | `ACQUIRED_IDLE` |

## Lease Rules

- No two fronts may share a writable state directory or active port.
- The three worker leases prohibit API, overlay, frontend, observer, bridge,
  supervisor, tray, or persistent process startup.
- Startup command: prohibited for the current cards.
- Shutdown procedure: before review, prove no front-owned persistent process is
  running; do not kill an unknown process.
- Cleanup: preserve required test logs and receipts, remove only proven
  front-owned temporary state, and record release evidence before setting a
  lease to `RELEASED`.
- ARGUS and LUMEN may not simultaneously use the operator-visible Orb. Their
  current leases deny it to both.
