# Francis Control Room Runtime Leases

Updated: 2026-07-15T02:37:00-05:00

Runtime access is denied unless a current task card explicitly grants it. A
worktree does not isolate runtime state. The default operator ports `8000`,
`8787`, and `5173` are reserved and are never worker defaults.

At lease acquisition, worker ports had no listeners and the assigned data
directories did not exist. Port `5173` had an unknown listener owned by PID
`12780`; it is operator-reserved and must not be stopped or inspected by a
worker merely to acquire a port.

All three worktrees currently junction `.venv` to the repaired shared
`D:\Francis\.venv` with CI extras `core`, `web`, `dev`, and `bridge`. The leases
isolate writable runtime/test state but do not isolate package files or physical
disk load. Package installation, sync, repair, or removal is prohibited while a
leased validation process is active.

At CR-005 reconciliation, no persistent worker service is running and every
assigned worker port is free. Only the protected unknown listener on operator-
reserved port `5173` remains. FORGE's test-only lease completed full gate
`VAL-20260714-028` on clean integration head `cdfc4a23` in `D:\fg`, using
`D:\Francis-runtime-leases\forge-managed-copies-safe-delta\val-028-full-gate`.
The gate exited `0`, its test-owned process tree exited, and the lease is released
with logs/state preserved. ARGUS and LUMEN remain released. No persistent service
or live Orb access occurred.

| Lease | Seat | Front | Task card | Branch / worktree | State directories | API / overlay / frontend ports | Permitted services | Real Orb | Processes | Acquired | Cleanup evidence | Release state |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `LEASE-FORGE-003` | FORGE | CR-FORGE-003 | `task_cards/managed-copy-safe-delta-export-preflight.md` | `codex/forge-safe-delta-export-preflight` / `D:\fg` | `FRANCIS_DATA_DIR=D:\Francis-runtime-leases\forge-safe-delta-export-preflight\data` | `18004` / `18784` / `15174` | none while released | denied | none; promoted locally at `287a27c8` | 2026-07-15T02:42:00-05:00 | full gate exit `0`; focused post-promotion checks passed; processes exited; ports unused | `RELEASED` |
| `LEASE-FORGE-002` | FORGE | CR-FORGE-002 | `task_cards/managed-copy-safe-delta-approval.md` | `codex/forge-safe-delta-approval` / `D:\fg` | `FRANCIS_DATA_DIR=D:\Francis-runtime-leases\forge-safe-delta-approval\data`; validation artifacts under the same lease root | `18001` / `18781` / `15171` | none while released | denied | none; promoted locally at `ff58d6d9` | 2026-07-15T00:30:00-05:00 | full gate exit `0`; all owned test processes exited; logs preserved; ports unused | `RELEASED` |
| `LEASE-ARGUS-001` | ARGUS | CR-ARGUS-001 | `task_cards/lens-game-observer.md` | `codex/argus-game-observer` / `D:\Francis-worktrees\argus-game-observer` | assigned `FRANCIS_DATA_DIR=D:\Francis-runtime-leases\argus-game-observer\data`; pytest retention `worktree\data\test_runs\pytest` | `18002` / `18782` / `15172` | none while released | denied | none; promoted at `7af273af` | 2026-07-14T19:38:00-05:00 | test processes exited; logs preserved; ports unused | `RELEASED` |
| `LEASE-LUMEN-001` | LUMEN | CR-LUMEN-001 | `task_cards/orb-visual-choreography.md` | `codex/lumen-orb-choreography` / `D:\Francis-worktrees\lumen-orb-choreography` | assigned `FRANCIS_DATA_DIR=D:\Francis-runtime-leases\lumen-orb-choreography\data`; pytest retention `worktree\data\test_runs\pytest` | `18003` / `18783` / `15173` | none while released | denied | none at CR-005 reconciliation | 2026-07-14T09:37:19-05:00 | no validation/service process; partial state preserved; assigned ports free | `RELEASED` |

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
