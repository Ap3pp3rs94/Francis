# Completion Ledger

Snapshot date: `2026-03-25`

This ledger tracks repo reality, not roadmap aspiration. Francis is already a substantial operator system. The current posture is broad alpha coverage with real runtime, governance, HUD, worker, and packaging surfaces in place, but with productization debt still concentrated in runtime health, backlog control, and release packaging.

Estimated completion:

* overall: `~70%`
* feature and build coverage: `~80%`
* production readiness: `~55%`

Current live runtime pressure after the repair pass, replay drain, and release-lane verification on `2026-03-25`:

* active missions: `849`
* queued mission jobs / queue due: `849`
* deadletters: `0`
* open incidents: `12`
* critical open incidents: `0`
* inbox alerts: `1656`

These counts come from the live event reactor and now use active deadletters plus open incidents rather than raw historical append volume.

## Shipped

* Orchestrator API with major governance, control, missions, autonomy, receipts, and operator routes.
* HUD / Lens with current work, approvals, execution journal, incidents, missions, runs, swarm, federation, capability, dependency, and managed-copy surfaces.
* Gateway middleware with request IDs, RBAC, panic-mode, auth, and proxy routing.
* Worker execution substrate with leasing, backoff, deadletter, forge execution, and queue status surfaces.
* Observer probes, anomaly scoring, and event emission.
* Governance surfaces for control modes, approvals, adversarial quarantine, receipts, and trust calibration.
* Windows Electron overlay shell with Orb/Lens split surfaces, shell-state handling, accessibility, authority posture, update posture, and runtime bootstrap scripts.
* Local-first workspace substrate for missions, queues, incidents, receipts, telemetry, forge artifacts, and runtime journals.

## Hardened In This Sprint

* Mission queue integrity: duplicate queued `mission.tick` jobs are normalized instead of accumulating, and terminal missions now supersede stale queued work rather than leaving orphaned queue pressure behind.
* Worker backlog drainage: worker cycles run mission-queue normalization before dispatch and record mission queue repair posture in cycle summaries and receipts.
* Runtime repair discipline: the worker surface now exposes a governed `worker/repair` path for previewing or applying queue normalization, stale deadletter replay/archive, and stale security incident cleanup with receipts.
* Incident hygiene: observer incidents are now managed by anomaly kind, refreshed in place, deduplicated, and resolved when the anomaly clears instead of inflating open-incident counts on every scan.
* Operator traceability: mission and worker results now carry queue-repair summaries, replayed job IDs, and repair reasons so cleanup and replay operations are inspectable after the fact.
* Backlog drainage: the live repair pass archived `93` stale unsupported deadletters, replayed `88` stale timeout deadletters, resolved `283` stale security probe incidents, and then drained the replayed forge backlog back to the mission baseline queue.
* Verification lanes: focused hardening tests exist for mission queue repair, runtime hygiene, and observer incident lifecycle, alongside validated mission/observer integration smoke lanes, the Electron overlay test lane, and a bundled `release:hardening` command that now leaves the shared workspace counters unchanged before and after execution.
* Documentation truthfulness: changelog, README, roadmap framing, and workspace guidance now reflect a real build under productization instead of a scaffold claim.

## Partial

* Runtime backlog drainage is improved, but the live workspace still carries a large active mission queue and inbox backlog that needs controlled cleanup or operational handling.
* Deadletter discipline is now materially stronger, but replay/archive still runs as an explicit operator action rather than a scheduled housekeeping policy.
* Incident posture is much cleaner, but the inbox backlog and active mission queue still dominate day-to-day runtime pressure.
* Productization is real in the overlay shell, but the distribution is still unsigned and Windows trust prompts remain expected.
* Verification structure is materially better, but the full `pytest -q` lane is still slower and less decisive than the focused lanes.

## Missing

* A first-class operator runbook for bulk queue repair, deadletter replay selection, and stale incident cleanup across an already-heavy workspace.
* Signed Windows distribution for the portable and installer artifacts.
* A fully green and routinely enforced full-suite release lane with bounded runtime expectations.

## Blocked

* Production-readiness claims are blocked on draining or explicitly triaging the existing workspace backlog so current counts reflect live operational truth instead of historical residue.
* Distribution trust is blocked on Windows code signing even though the pack and installer lanes now complete successfully on this machine.

## Verification Lanes

Use these commands as the current release-hardening lanes:

* `npm run release:hardening`
* `ruff check .`
* `pytest -q tests/unit/test_mission_queue_repair.py tests/unit/test_runtime_hygiene.py tests/unit/test_observer_emitter.py`
* `pytest -q tests/integration/test_observer_emits_events.py`
* `pytest -q tests/integration/test_mission_tick.py -k "create_mission_persists_and_queues or tick_advances_mission_and_history or failed_tick_goes_to_deadletter or tick_idempotency_replays_without_double_advance"`
* `pytest -q tests/integration/test_worker_cycle.py -k "worker_cycle_processes_mission_queue or worker_cycle_action_timeout_can_escalate_to_deadletter"`
* `npm run overlay:test`
* `npm run overlay:prepare-runtime`
* `npm run overlay:pack`
* `npm run overlay:installer`

`pytest -q` remains the full-suite lane and should still be treated as the release-wide check once its runtime and reliability are tightened further.
