# Completion Ledger

Snapshot date: `2026-03-27`

This ledger tracks repo reality, not roadmap aspiration. Francis is already a substantial operator system. The current posture is broad alpha coverage with real runtime, governance, HUD, worker, and packaging surfaces in place, but with productization debt still concentrated in runtime health, backlog control, and release packaging.

Estimated completion:

* overall: `96%`
* feature and build coverage: `96%`
* production readiness: `95%`

Current live runtime pressure after the repair pass, replay drain, inbox cleanup, synthetic mission cleanup, incident cleanup, and release-lane verification on `2026-03-26`:

* active missions: `0`
* queued mission jobs / queue due: `0`
* deadletters: `0`
* open incidents: `0`
* critical open incidents: `0`
* active inbox messages: `0`
* inbox alerts: `0`

These counts come from the live event reactor and presence surfaces and now use active deadletters, open incidents, and active inbox rows rather than raw historical append volume.

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
* Inbox hygiene: presence briefings now reuse a managed inbox message instead of appending a fresh system alert on every `/presence/briefing`, and inbox counts now ignore archived, resolved, acknowledged, or superseded rows.
* Mission hygiene: governed runtime repair now cancels stale synthetic missions from shared-workspace integration residue, supersedes their queued `mission.tick` jobs, and records the affected mission/job ids in repair receipts.
* Queue integrity: mission queue normalization now also supersedes orphaned `mission.tick` jobs that reference missing missions instead of leaving them due forever.
* Queue hygiene: governed runtime repair now supersedes stale malformed queued `skill.run` rows that have no executable skill payload instead of leaving them due indefinitely.
* Operator traceability: mission and worker results now carry queue-repair summaries, replayed job IDs, and repair reasons so cleanup and replay operations are inspectable after the fact.
* Backlog drainage: the live repair pass archived `93` stale unsupported deadletters, replayed `88` stale timeout deadletters, resolved `283` stale security probe incidents, and then drained the replayed forge backlog back to the mission baseline queue.
* Backlog drainage: the governed inbox cleanup pass archived `1628` stale synthetic inbox rows and reduced live inbox alerts from `1656` to `28` without changing the active mission baseline queue.
* Backlog drainage: the governed synthetic-mission cleanup pass cancelled `849` stale test missions, superseded `848` queued `mission.tick` jobs, and brought active mission pressure from `849` to `0` with only a single non-mission queued job left.
* Backlog drainage: the governed incident/queue cleanup pass resolved the final `10` stale quarantine-generated security incidents, superseded the last malformed queued `skill.run`, and brought live due-queue pressure from `1` to `0` while leaving only `2` real observer incidents open.
* Observer trust: pathological observer baseline files are now normalized in place through `WorkspaceFS`, so absurd threshold residue such as `100%` disk or memory minima no longer pins false anomaly incidents open.
* Backlog drainage: the observer baseline normalization pass cleared the final `2` false observer incidents and brought live open-incident pressure from `2` to `0`.
* Inbox hygiene: governed runtime repair now archives stale unkeyed inbox test residue such as legacy `hello/world` rows and pre-managed presence briefings instead of leaving them active forever.
* Telemetry hygiene: governed runtime repair now prunes stale `source=pytest` telemetry rows so synthetic verification crashes stop keeping `telemetry.critical_present` alive after the run that created them.
* Backlog drainage: the governed inbox and telemetry cleanup pass archived the final `205` stale inbox rows and pruned the final `3` stale pytest telemetry rows, bringing active inbox pressure from `205` to `0`, inbox alerts from `28` to `0`, and telemetry critical residue from `1` to `0`.
* Scheduled housekeeping: the autonomy reactor now previews stale runtime-hygiene debt, emits a `runtime.hygiene_due` signal, budgets a low-risk `worker.repair` action, and executes the existing governed cleanup path through normal autonomy receipts instead of leaving hygiene as a purely manual operator action.
* Verification lanes: focused hardening tests exist for mission queue repair, runtime hygiene, observer incident lifecycle, presence/inbox state, inbox/telemetry shared-workspace isolation, and security-quarantine isolation, alongside validated mission/observer integration smoke lanes, the Electron overlay test lane, and a bundled `release:hardening` command that now leaves the shared workspace counters unchanged before and after execution.
* Verification discipline: the monolithic `pytest -q` run cleared end to end with `359 passed in 2291.66s`, and the remaining workspace-leak cases it exposed in the worker deadletter retry path and red-team policy-bypass lens path are now isolated and folded into the bounded release lane.
* Distribution trust: the overlay packaging flow now uses a dedicated Electron Builder config that is wired to the signing routes the repo actually supports, namely local certificate signing, Windows cert-store signing, and Azure Trusted Signing.
* Distribution trust: Windows packaging now also supports signtool certificate-store selection through `FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME` and optional `FRANCIS_WINDOWS_SIGNING_SHA1`, so provisioned Windows builders do not need to expose a PFX path just to produce signed artifacts.
* Distribution trust: packaged artifact builds now emit `electron/generated/build-signing.json`, `npm run overlay:verify-signing` inspects the real artifacts with the vendored `signtool.exe` verifier, and `npm run overlay:verify-signing:required` can fail a release packaging pass until signed outputs are present.
* Distribution trust: the repo now exposes `npm run overlay:pack:signed`, `npm run overlay:installer:signed`, `npm run overlay:dist:signed`, and the canonical `npm run release:publish:windows` path so Windows publication fails closed unless both the bounded hardening lane and signed artifact verification pass.
* Distribution trust: signing posture now accepts verifier-backed executable state instead of assuming every packaged build is unsigned, while still falling back cleanly when no verifier is available in the current runtime.
* Distribution trust: the signing manifest now records the actual leaf signer subject, issuer, and thumbprint instead of collapsing to the timestamp responder identity.
* Distribution trust: the repo now exposes `npm run overlay:verify-signing:public`, `npm run overlay:dist:public`, and `npm run release:publish:windows:public` so self-issued or publisher-mismatched signers fail closed even when local signed packaging succeeds.
* Distribution trust: the repo now exposes `npm run overlay:signing-doctor`, which diagnoses whether the current machine is ready for public-trust release signing or blocked on missing publisher hint, self-issued-only certs, publisher mismatch, or absent public-trust signer material, and emits exact PowerShell env suggestions for the viable local-store and Azure routes.
* Distribution trust: `npm run release:publish:windows:public` and `npm run overlay:dist:public` now run the signing-doctor public preflight first, so a machine that only has a self-issued dev signer fails closed before the expensive Windows packaging step.
* Distribution trust: the repo now includes `scripts/signing-public.example.ps1`, ignores `scripts/signing-public.local.ps1`, and exposes `npm run release:publish:windows:public:local` so real publisher credentials can live in one local PowerShell bootstrap file instead of ad hoc shell residue.
* Distribution trust: placeholder signing-template values such as `<legal publisher name>` are now treated as unset across the signing surfaces, so the local bootstrap file can exist safely before real publisher material is provisioned.
* Distribution trust: the local public-release wrapper now stops in PowerShell before npm starts if the bootstrap file is missing, still placeholder-valued, or does not yet contain one complete public signing route.
* Distribution trust: public-signing verification now also requires `FRANCIS_WINDOWS_SIGNING_CHAIN_HINT`, so the expected non-leaf issuer or chain identity is pinned and an arbitrary privately issued non-self-issued certificate cannot silently satisfy the public gate.
* Distribution trust: the generated signing manifest and verifier output now capture primary-chain metadata such as `rootSubject`, `rootIssuer`, and `chainSubjects`, so leaf-vs-root signer identity is inspectable during public-release review.
* Distribution trust: `npm run release:publish:windows` is now a first-class internal beta lane for QA / tester-only distribution. It auto-selects a safe machine-local signer when needed, emits relabeled artifacts into `dist/internal-beta/windows/current`, writes an internal-beta manifest and notice, and exports a tester-trust cert when the local cert-store route is in use.
* Shared-workspace discipline: the remaining mission-writing integration files now snapshot and restore workspace state so routine test runs stop repopulating the live mission backlog.
* Shared-workspace discipline: security quarantine and red-team lanes now snapshot and restore their runtime artifacts so bounded release verification stops reintroducing synthetic security incidents into the live workspace.
* Shared-workspace discipline: inbox and telemetry integration lanes now snapshot and restore their runtime artifacts so bounded release verification stops reintroducing synthetic inbox and telemetry pressure into the live workspace.
* Shared-workspace discipline: portability, receipts-lens, and lens-usage integration files now isolate their runtime write sets, prune new handback-export artifacts, and stop depending on ad hoc manual cleanup when run serially.
* Verification discipline: the repo now exposes `npm run test:full:first-failure` for serial full-suite triage, and the formerly dirty portability/receipts/lens nodes now pass together in a single serial pytest process.
* Verification discipline: shared-workspace isolation now restores giant append-only ledgers such as `journals/fs.jsonl` and `runs/run_ledger.jsonl` by truncation instead of full copies, which reduced the formerly dirty serial portability/receipts/lens batch from `572.73s` to `249.52s`, with the slowest single nodes now bounded at `46.30s` and `30.04s`.
* Swarm integrity: the swarm unit loader now merges canonical built-in units back into partial or portability-imported `swarm/units.json` payloads instead of treating a one-row registry as authoritative, and the swarm integration file now isolates its runtime write set before mutating delegations, deadletters, or receipts.
* Verification discipline: after fixing the swarm tail break, `pytest -q --maxfail=1` had already cleared `196` tests before the swarm failure, `python -m pytest -q --stepwise --maxfail=1` then passed the remaining `355` tests in `2541.74s`, and a fresh monolithic `pytest -q` run on the final code state then cleared end to end with `359 passed in 2291.66s`.
* Documentation truthfulness: changelog, README, roadmap framing, and workspace guidance now reflect a real build under productization instead of a scaffold claim.

## Partial

* Runtime backlog drainage is materially improved and the live workspace is now quiet by default, with governed cleanup now available both as an explicit operator action and as a budgeted autonomy housekeeping action. The remaining risk is keeping those policies narrow and routine rather than inventing broader self-directed cleanup.
* Deadletter discipline is now materially stronger, but timeout replay still remains an explicit operator action rather than a scheduled housekeeping policy.
* Incident, inbox, and telemetry posture are now quiet, so the remaining productization risk is release confidence and distribution trust rather than day-to-day runtime noise.
* Productization is real in the overlay shell, and the signing routes plus verification gates are now explicit. The current machine can now ship labeled internal beta artifacts immediately, but public-trust distribution remains blocked on a real publisher identity.
* Verification structure is materially better, and the fresh monolithic `pytest -q` lane is now confirmed green, but it is still materially slower than the focused lanes.

## Missing

* A first-class operator runbook for bulk queue repair, deadletter replay selection, and stale incident cleanup across an already-heavy workspace.
* Public-trust signed Windows distribution for the portable and installer artifacts.
* A routinely enforced full-suite release lane with bounded runtime expectations.

## Blocked

* Public release remains blocked primarily on publisher-grade Windows signing material and ongoing release-lane operating cost rather than on live queue, incident, inbox, telemetry, or full-suite confidence.
* Distribution trust is blocked on actual public signer material and public artifact publication, not on missing packaging or verification plumbing.

## Verification Lanes

Use these commands as the current release-hardening lanes:

* `npm run release:hardening`
* `npm run release:publish:windows`
* `npm run release:publish:windows:internal-beta`
* `npm run release:publish:windows:public`
* `npm run release:publish:windows:public:local`
* `npm run test:full:first-failure`
* `npm run test:full:stepwise`
* `ruff check .`
* `pytest -q tests/unit/test_mission_queue_repair.py tests/unit/test_runtime_hygiene.py tests/unit/test_observer_emitter.py tests/unit/test_observer_baselines.py`
* `pytest -q tests/unit/test_presence_state.py tests/test_presence_state_grounding.py`
* `pytest -q tests/unit/test_telemetry_reactor.py::test_event_reactor_surfaces_runtime_hygiene_signal tests/unit/test_telemetry_reactor.py::test_decision_engine_selects_worker_repair_when_runtime_hygiene_due tests/integration/test_autonomy_cycle.py::test_autonomy_can_execute_worker_repair_when_runtime_hygiene_due tests/integration/test_autonomy_events.py::test_autonomy_collect_events_enqueues_runtime_hygiene_signal`
* `pytest -q tests/integration/test_inbox_pipeline.py tests/integration/test_telemetry_pipeline.py`
* `pytest -q tests/integration/test_observer_emits_events.py`
* `pytest -q tests/integration/test_security_quarantine.py tests/redteam/test_prompt_injection.py tests/redteam/test_fs_escape_attempts.py tests/redteam/test_policy_bypass.py`
* `pytest -q tests/integration/test_mission_tick.py -k "create_mission_persists_and_queues or tick_advances_mission_and_history or failed_tick_goes_to_deadletter or tick_idempotency_replays_without_double_advance"`
* `pytest -q tests/integration/test_worker_cycle.py -k "worker_cycle_processes_mission_queue or worker_retry_backoff_and_deadletter_escalation or worker_cycle_action_timeout_can_escalate_to_deadletter"`
* `npm run overlay:test`
* `npm run overlay:prepare-runtime`
* `npm run overlay:verify-signing`
* `npm run overlay:verify-signing:required`
* `npm run overlay:verify-signing:public`
* `npm run overlay:signing-doctor`
* `npm run overlay:signing-doctor:public`
* `npm run overlay:pack`
* `npm run overlay:pack:signed`
* `npm run overlay:installer`
* `npm run overlay:installer:signed`
* `npm run overlay:dist`
* `npm run overlay:dist:signed`
* `npm run overlay:dist:public`

`pytest -q` remains the unbounded full-suite lane. `npm run test:full:first-failure` is the current release-triage command for narrowing the first failing node without waiting for the entire suite to finish, and `npm run test:full:stepwise` is the current resume command for continuing from the last failure point without replaying the already-confirmed prefix. Full-suite completion time is lower at the old serial hot spots, the remaining tail now passes through the saved stepwise state, the bounded hardening lane now also exercises autonomy housekeeping plus the formerly leaking worker deadletter and policy-bypass cases, and the monolithic lane is now directly confirmed green (`359 passed in 2291.66s`), but it is still too long to call cheap routine verification. `npm run release:publish:windows` is now the canonical internal beta Windows publish lane and writes a labeled tester bundle under `dist/internal-beta/windows/current`, `npm run overlay:dist:public` now fails fast through the public signing-doctor preflight before any packaging work, and `npm run release:publish:windows:public` adds publisher-name, chain-hint, and non-self-issued validation for public-trust release packaging.
