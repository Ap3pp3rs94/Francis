# Changelog

## Unreleased
- Release-hardening sprint for queue integrity, incident hygiene, verification lanes, and packaging truthfulness.
- Mission queue repair now normalizes duplicate `mission.tick` jobs, supersedes stale queued work for terminal missions, and exposes repair counts in mission/worker receipts.
- Worker cycles now run queue normalization before dispatch and record mission-queue repair posture in the worker-cycle summary and ledger.
- Expanded the governed `worker/repair` path so it can preview or apply mission queue normalization, archive stale unsupported deadletters, replay stale timeout deadletters, and resolve stale security probe incidents with receipts.
- Observer scans now manage incidents by anomaly kind instead of appending a fresh open row on every pass; repeated anomalies refresh existing incidents and cleared anomalies resolve in place.
- Applied the new repair path against the live workspace, reducing active deadletters from `183` to `0`, open incidents from `295` to `12`, and draining replayed `forge.propose` residue back to the mission baseline queue.
- Inbox system messages now support managed replacement via `message_key`, `/presence/briefing` reuses its existing managed inbox row instead of appending indefinitely, and active-only inbox counting now ignores archived lifecycle rows across presence and reactor surfaces.
- Applied the governed inbox cleanup path against the live workspace, archiving `1628` stale synthetic inbox rows and reducing active inbox alerts from `1656` to `28`.
- Added focused hardening tests for mission queue repair, runtime hygiene replay/archive logic, and observer incident lifecycle, plus updated observer integration assertions for managed incident state.
- Added focused presence/inbox coverage so shared-workspace presence smoke tests now snapshot and restore workspace state, and the managed briefing flow is verified end to end.
- Expanded governed runtime repair again so it can cancel stale synthetic missions from shared-workspace integration residue, supersede their queued `mission.tick` jobs, and preview/report the affected mission and job ids before apply.
- Mission queue normalization now supersedes orphaned `mission.tick` jobs that reference missing missions instead of leaving them queued indefinitely.
- Isolated the remaining mission-writing integration files that still used the live workspace, so older runs stop rebuilding synthetic mission backlog during autonomy, runs, receipts, control, tools, and trace tests.
- Applied the synthetic mission cleanup path against the live workspace, cancelling `849` stale test missions, superseding `848` queued `mission.tick` jobs, and reducing active mission pressure from `849` to `0` with one residual non-mission queued job left.
- Governed runtime repair now also supersedes stale malformed queued `skill.run` rows and resolves stale quarantine-generated `security.untrusted_input` incidents from the bounded security/red-team lanes with explicit repair reasons and receipt metadata.
- Shared-workspace security quarantine and red-team tests now snapshot and restore their runtime artifacts instead of leaving synthetic incident residue behind, and `npm run release:hardening` now includes that security-hardening lane.
- Applied the governed incident/queue cleanup path against the live workspace, reducing open incidents from `12` to `2` and removing the final malformed queued `skill.run` so queue-due pressure is now `0`.
- Verified `ruff check .`, focused mission/observer pytest lanes, `npm run overlay:test`, `npm run overlay:prepare-runtime`, `npm run overlay:pack`, and `npm run overlay:installer`.
- Added a bounded `npm run release:hardening` lane so the current release-hardening checks are runnable as one command, and isolated the shared-workspace integration smoke tests so the lane now preserves live workspace counters before and after execution, including the new presence/inbox hardening step.
- Added a completion ledger under `docs/operations/COMPLETION_LEDGER.md` and updated README/workspace docs to reflect current maturity and verification lanes.
