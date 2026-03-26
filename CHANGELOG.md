# Changelog

## Unreleased
- Release-hardening sprint for queue integrity, incident hygiene, verification lanes, and packaging truthfulness.
- Mission queue repair now normalizes duplicate `mission.tick` jobs, supersedes stale queued work for terminal missions, and exposes repair counts in mission/worker receipts.
- Worker cycles now run queue normalization before dispatch and record mission-queue repair posture in the worker-cycle summary and ledger.
- Expanded the governed `worker/repair` path so it can preview or apply mission queue normalization, archive stale unsupported deadletters, replay stale timeout deadletters, and resolve stale security probe incidents with receipts.
- Observer scans now manage incidents by anomaly kind instead of appending a fresh open row on every pass; repeated anomalies refresh existing incidents and cleared anomalies resolve in place.
- Applied the new repair path against the live workspace, reducing active deadletters from `183` to `0`, open incidents from `295` to `12`, and draining replayed `forge.propose` residue back to the mission baseline queue.
- Added focused hardening tests for mission queue repair, runtime hygiene replay/archive logic, and observer incident lifecycle, plus updated observer integration assertions for managed incident state.
- Verified `ruff check .`, focused mission/observer pytest lanes, `npm run overlay:test`, `npm run overlay:prepare-runtime`, `npm run overlay:pack`, and `npm run overlay:installer`.
- Added a bounded `npm run release:hardening` lane so the current release-hardening checks are runnable as one command, and isolated the shared-workspace integration smoke tests so the lane now preserves live workspace counters before and after execution.
- Added a completion ledger under `docs/operations/COMPLETION_LEDGER.md` and updated README/workspace docs to reflect current maturity and verification lanes.
