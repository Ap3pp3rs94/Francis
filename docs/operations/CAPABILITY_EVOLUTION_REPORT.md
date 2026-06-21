# Francis Capability Evolution Report

This report tracks capability accumulation, architectural evolution, and build
effectiveness over time. It is not a completion percentage source and it does
not treat commit count as progress by itself.

Progress means validated capability growth: stronger contracts, new receipt
evidence, safer governance, better observability, more useful operator paths,
and clearer continuation state.

## Tracking Rules

- Count activity separately from progress.
- Classify every accepted change by capability category.
- Record rejected packets and rejected artifacts explicitly.
- Treat documentation-only changes as progress only when they create durable
  operational or governance state.
- Do not count a capability as live unless validation proves the live path.
- Keep sandbox, fixture, mock, replay, and live evidence distinct.

## Capability Categories

- Presence
- Lens
- Voice
- Memory
- Governance
- Receipts
- Missions
- Overlay
- Observability
- Completion Model
- Capability Registry
- Swarm Infrastructure
- Operator Controls
- API Surface
- Documentation
- Testing

## Running Capability Ledger

Baseline: report initialized after the four-worker pass completed on
2026-06-20 UTC / 2026-06-19 America/Chicago.

| Category | Accepted Changes | Current Advancement |
| --- | ---: | --- |
| Presence | 2 | Orb voice proof diagnostics now distinguish local acoustic proof from bridge-file receipts and expose whether manual proof is required. |
| Lens | 4 | Lens observation contracts gained unmapped-coordinate refusal coverage, invalid-dimension refusal, and command-palette proof readbacks. |
| Voice | 4 | Voice receipts now separate acoustic proof source, gate mode, provider receipt modes, and embedded provider-boundary evidence. |
| Memory | 0 | No memory contract advancement in this cycle. |
| Governance | 20 | Refusal/no-authority boundaries strengthened for acoustic proof, provider receipts, Stage 17 worker-readback/publication handoff claims, invalid coordinates, generated-spec compatibility, lifecycle history readback compatibility, unsupported invocation receipt rejection, quality-standard dry-run/apply receipt gates, pack-selection binding, activity-vs-progress reporting, worker liveness truth, unversioned migration refusal, read-only invocation proof readiness, artifact reconstruction dry-run confirmation, lifecycle-blocked re-enable refusal, operation-readback-bound invocation proof, and long-path proposal-review readiness. |
| Receipts | 20 | New receipt/readback fields for acoustic proof rejection, provider mode state/linkage, worker-readback and worker/publication handoff requirements, capability-evolution worker packets, worker execution liveness, metadata receipt batch evidence, quality-standard remediation batch receipts, lifecycle history compatibility evidence, invocation pack-selection/rejection receipts, migration identity, proof-readiness linkage, artifact reconstruction queue evidence, validation/proposal reconstruction receipts, operation caller-context readback binding, and long-path proposal-review receipt readability. |
| Missions | 4 | Stage 17 mission-linked invocation audit rejects tampered embedded pack-selection bindings, surfaces unsupported operation-capability receipts as rejected evidence, requires operation-readback mission-shape reuse before readiness, and now has a passing isolated reusable-invocation mission proof. |
| Overlay | 4 | Overlay-related proof now requires local overlay speech source, exposes manual proof mode, and blocked/invalid coordinate cases stay before screen/session readback. |
| Observability | 17 | Added diagnostics for acoustic proof, provider mode/linkage disambiguation, Stage 17 readback and handoff guard state, quality-standard after-sync queue honesty, unsupported invocation rejection visibility, build capability evolution, Exec worker liveness, publication-marker prompt matching, migration identity readback, invocation proof readiness, artifact reconstruction before/after queue evidence, operation caller-context audit binding, and retained long-path proposal-review failure evidence. |
| Completion Model | 2 | Completion model now rejects selected Stage 17 gaps as worker-readback proof and worker/publication handoff proof. |
| Capability Registry | 9 | Stage 17 now has generated-spec compatibility binding, catalog lifecycle provenance projection, selected live metadata-receipt backlog reduction evidence, receipt-backed quality-standard backlog reduction, lifecycle-history compatibility readback evidence, versioned migration identity enforcement, one live artifact reconstruction backlog reduction, lifecycle-blocked re-enable prevention, and long-path-safe proposal review state for promotion readiness. |
| Swarm Infrastructure | 4 | Completion model now requires worker readback/handoff evidence, coordinator prompts require capability-evolution packet fields, and active Exec workers are no longer treated as stale. |
| Operator Controls | 2 | Manual acoustic Orb movement proof now has source-specific next-step diagnostics and explicit manual-proof-required state. |
| API Surface | 14 | Monitor route sanitizer, ChatGPT voice contract/receipt surfaces, plugin promotion readiness, plugin runtime execution guards, quality-standard remediation receipts, lifecycle-history compatibility readbacks, migration identity refusal, artifact reconstruction evidence fields, lifecycle enable refusal, invocation audit readbacks, and long-path-safe forge proposal review expose stricter behavior. |
| Documentation | 10 | Completion model docs, worker prompt docs, Stage 17 closure matrix, ledger entries, and this evolution report record durable operating rules, current Stage 17 blockers, and accepted/rejected local-drone evidence. |
| Testing | 23 | Added or expanded focused tests across worker lanes, coordinator prompt contracts, worker liveness status, plugin compatibility, metadata receipt batching, quality-standard receipt/after-sync behavior, lifecycle history compatibility, migration identity refusal, artifact reconstruction queue evidence, lifecycle enable refusal, invocation audit binding, long-path proposal review, and isolated reusable-invocation mission proof. |

## Cycle Log

### Cycle 2026-06-20T01:37Z to 2026-06-20T01:55Z

Scope: four-worker Francis recursive build pass. All four active workers
finished once before review.

Active workers:

- `worker-1-orb-voice-proof`
- `worker-2-lens-overlay-spatial`
- `worker-3-voice-receipts`
- `worker-4-stage17-completion`

Active drones: 0 reported by all worker packets.

Commits produced:

- `b10ecab1` - `feat(observability): tighten manual acoustic orb proof diagnostics`
- `fa98cbe1` - `test(lens): cover unmapped overlay coordinate refusals`
- `5410a424` - `feat(voice): disambiguate ChatGPT provider receipt modes`
- `64082d4d` - `fix(completion-model): require worker readback evidence for stage17 claims`

Commits accepted: 4.

Commits rejected: 0 complete worker packets rejected.

Artifacts rejected or deferred:

- `docs/operations/COMPLETION_LEDGER.md` from Worker 4 was excluded from the
  accepted commit because the file already contained a mixed 7,551-line dirty
  append from prior lane work. The accepted W4 commit kept the code, tests, CLI,
  and docs guard only.

Validations run:

- Worker 1 focused monitor proof pytest selection.
- Worker 1 `tests/unit/test_lens_orb_mcp_status_route.py`.
- Worker 1 PowerShell parser check for `scripts/lens-command-palette-monitor.ps1`.
- Worker 1 Ruff check and Ruff format check.
- Worker 1 `git diff --check` for accepted files.
- Worker 2 `tests/unit/test_lens_mcp_perception.py`.
- Worker 2 Ruff check and Ruff format check.
- Worker 2 `git diff --check` for accepted file.
- Worker 3 `tests/test_chatgpt_voice_bridge.py`.
- Worker 3 `tests/test_orb_voice_overlay_lens_validation_script.py`.
- Worker 3 Ruff check, Ruff format check, mypy, and `git diff --check`.
- Worker 4 `tests/test_completion_model.py` and `tests/test_francis_completion_model_script.py`.
- Worker 4 Ruff check, Ruff format check, mypy, PowerShell parser check, and
  `git diff --check` for accepted non-ledger files.

Validations passed: all accepted validation commands passed.

Validations failed:

- Worker 1 reported one broader full monitor test-file attempt timed out in
  `test_lens_command_palette_monitor_reports_chatgpt_connector_localtunnel_fallback`.
  That connector fallback timeout was outside the accepted acoustic-proof change
  and remains a follow-up risk.

Receipts generated:

- `.francis/worker-terminal-coordinator/readbacks/worker-1-orb-voice-proof.md`
- `.francis/worker-terminal-coordinator/readbacks/worker-2-lens-overlay-spatial.md`
- `.francis/worker-terminal-coordinator/readbacks/worker-3-voice-receipts.md`
- `.francis/worker-terminal-coordinator/readbacks/worker-4-stage17-completion.md`

Files touched by accepted commits:

- `scripts/lens-command-palette-monitor.ps1`
- `src/francis/lens/command_palette_monitor.py`
- `tests/test_lens_command_palette_monitor_script.py`
- `tests/unit/test_lens_orb_mcp_status_route.py`
- `tests/unit/test_lens_mcp_perception.py`
- `src/francis/chatgpt_voice_bridge.py`
- `tests/test_chatgpt_voice_bridge.py`
- `src/francis/completion_model.py`
- `scripts/francis-completion-model.ps1`
- `tests/test_completion_model.py`
- `tests/test_francis_completion_model_script.py`
- `docs/operations/COMPLETION_MODEL.md`

Roadmap items advanced:

- Phase 2 / Stage 6 Lens MVP truthfulness.
- Voice-to-Orb proof receipt integrity.
- Lens-to-overlay coordinate refusal truth.
- Stage 17 completion-model guardrails.
- P1 interface truthfulness.
- P9 observability and receipt-backed readback.

Capability classes advanced:

- Presence
- Lens
- Voice
- Governance
- Receipts
- Overlay
- Observability
- Completion Model
- Swarm Infrastructure
- Operator Controls
- API Surface
- Documentation
- Testing

Velocity metrics:

- Worker pass duration: about 18 minutes from first active prompt start to last
  worker completion.
- Commits per hour for accepted lane commits: about 13.3.
- Accepted commits per hour: about 13.3.
- Validated capability classes per hour: about 43.3 based on 13 distinct classes
  advanced in this pass.
- Roadmap closures per day: 0. No roadmap gate closed.
- Worker efficiency: 4 accepted packets from 4 completed workers.
- Drone efficiency: not applicable; no drones used.
- Integration efficiency: 4 accepted lane commits from 4 reviewed packets, with
  one partial artifact rejected.

## Daily Evolution Summary - 2026-06-20 UTC

STATUS

- Active evolution tracking initialized.
- Four-worker pass reviewed, validated, committed, and pushed.
- No completion percentage movement claimed.

COMMITS PRODUCED

- 4 accepted lane commits.

COMMITS ACCEPTED

- 4.

COMMITS REJECTED

- 0 full commits.
- 1 partial artifact rejected/deferred: mixed `COMPLETION_LEDGER.md` append.

VALIDATIONS PASSED

- Focused validation passed for every accepted lane commit.

VALIDATIONS FAILED

- 1 broader connector fallback test attempt timed out outside the accepted W1
  slice.

CAPABILITIES ADVANCED

- Acoustic Orb proof diagnostics.
- Lens blocked-coordinate refusal coverage.
- ChatGPT voice provider receipt mode disambiguation.
- Stage 17 worker-readback claim guard.

NEW CAPABILITIES CREATED

- Acoustic proof now reports trusted local-overlay speech source checks and
  source-specific rejection reasons.
- Provider receipts now expose a structured provider mode state separating
  provider calls from provider status modes.
- Completion model now states that selected Stage 17 gaps are not worker packet
  evidence.
- Lens tests now prove malformed/missing/unsupported coordinate cases are
  blocked before screen/session readback.

ROADMAP ITEMS ADVANCED

- Stage 6 Lens MVP truthfulness and observation boundaries.
- Stage 17 completion-model guardrails.
- P9 observability readbacks.
- Voice receipt integrity.

ARCHITECTURAL IMPROVEMENTS

- Strengthened separation between local microphone-origin proof and bridge-file
  command receipts.
- Strengthened separation between transcript availability and provider
  availability.
- Strengthened separation between worker selection and worker evidence.
- Preserved lens-to-overlay refusal before any screen/session readback on
  unmapped coordinate cases.

GOVERNANCE IMPROVEMENTS

- Acoustic proof rejects non-local overlay speech sources.
- Completion model rejects selected Stage 17 gaps as worker-readback authority.
- Voice bridge maintains no direct Orb control and no live provider claim
  without provider receipt evidence.

RECEIPT IMPROVEMENTS

- Added acoustic proof source contract and rejection reasons.
- Added voice provider mode state readback.
- Added worker-readback future evidence requirements.
- Preserved worker lane readbacks as reviewable receipt packets.

MOST IMPORTANT CHANGE OF THE DAY

- The system gained stronger truth boundaries around evidence claims: acoustic
  proof, provider state, coordinate observation, and worker-readback claims now
  require explicit evidence instead of inferred progress.

BIGGEST REMAINING BOTTLENECK

- Live proof is still gated by actual external/local runtime evidence: real
  microphone-origin Orb movement, public ChatGPT app ingress, live ElevenLabs
  provider receipts, and clean Stage 17 queue-reduction artifacts.

NEXT HIGHEST LEVERAGE ACTION

- Run the next worker cycle against live-evidence bottlenecks: local microphone
  Orb proof, public ChatGPT ingress or clearly marked fixture proof, and a
  single governed Stage 17 plugin API slice with focused validation.

## PM Follow-Up - 2026-06-20T02:20Z

Commit:

- `dc5acac9` - `feat(operations): require capability evolution worker packets`

Capability classes advanced:

- Governance
- Receipts
- Observability
- Swarm Infrastructure
- Documentation
- Testing

What changed:

- Coordinator dispatch prompts now require a `CAPABILITY EVOLUTION` section in
  worker readbacks.
- Worker prompt documentation now lists the capability categories and requires
  workers to distinguish activity from progress.
- Coordinator tests now assert future dispatch prompts include capability
  evolution requirements.

Validation:

- `.\.venv\Scripts\python.exe -m pytest tests\test_francis_worker_terminals_script.py -q` passed.
- `.\.venv\Scripts\python.exe -m ruff check --no-cache tests\test_francis_worker_terminals_script.py` passed.
- `.\.venv\Scripts\python.exe -m ruff format --check --no-cache tests\test_francis_worker_terminals_script.py` passed.
- PowerShell parser check for `scripts\francis-worker-coordinator.ps1` returned `parse_ok`.
- `git diff --check -- scripts/francis-worker-coordinator.ps1 docs/operations/worker_prompts/README.md tests/test_francis_worker_terminals_script.py` passed with the existing CRLF warning for the PowerShell script.

Effect:

- Future worker packets should be easier to classify into the running
  capability ledger without reconstructing intent from diffs alone.

## PM Follow-Up - 2026-06-20T12:35Z

Commit:

- `815b66b4` - `fix(operations): keep active exec workers from stale churn`

Capability classes advanced:

- Governance
- Receipts
- Observability
- Swarm Infrastructure
- Testing

What changed:

- Launcher status now reports `exec_runner_alive` and
  `worker_execution_alive`.
- Coordinator stale-runner detection now uses truthful worker execution
  liveness instead of treating every Exec runner without a direct Codex child as
  stale.
- Coordinator receipts now distinguish `worker_execution_missing` from process
  absence.

Validation:

- `.\.venv\Scripts\python.exe -m pytest tests\test_francis_worker_terminals_script.py -q` passed.
- `.\.venv\Scripts\python.exe -m ruff check --no-cache tests\test_francis_worker_terminals_script.py` passed.
- `.\.venv\Scripts\python.exe -m ruff format --check --no-cache tests\test_francis_worker_terminals_script.py` passed.
- PowerShell parser checks for `scripts/start-francis-worker-terminals.ps1` and
  `scripts/francis-worker-coordinator.ps1` returned `parse_ok`.
- `git diff --check -- scripts/start-francis-worker-terminals.ps1 scripts/francis-worker-coordinator.ps1 tests/test_francis_worker_terminals_script.py` passed with existing CRLF warnings for the PowerShell scripts.

Effect:

- Removed a swarm bottleneck where active `codex exec` workers could be
  misclassified as stale because the launcher only looked for direct Codex child
  processes.

### Cycle 2026-06-20T12:20Z to 2026-06-20T12:34Z

Scope: four-worker pass launched by the old in-memory coordinator before the
Exec-liveness fix was restarted. All four workers finished once with exit code
0. The PM reviewed all four packets before opening the next gate.

Active workers:

- `worker-1-orb-voice-proof`
- `worker-2-lens-overlay-spatial`
- `worker-3-voice-receipts`
- `worker-4-stage17-completion`

Active drones: 0 reported by all worker packets.

Commits produced:

- `d43b7827` - `feat(observability): expose manual acoustic proof gate mode`
- `ffc5fe99` - `fix(lens): reject invalid overlay observation dimensions`
- `ec91ad41` - `feat(voice): clarify ChatGPT provider receipt linkage`
- `f5cc2adf` - `fix(completion-model): require worker publication handoff evidence`

Commits accepted: 4.

Commits rejected: 0 complete worker packets rejected.

Artifacts rejected or deferred:

- `docs/operations/COMPLETION_LEDGER.md` from Worker 4 was again excluded from
  the accepted commit because it remained a mixed multi-entry dirty append.

Validations passed:

- Worker 1 parser, py_compile, focused pytest selection, route sanitizer test,
  Ruff check, Ruff format check, and diff check.
- Worker 2 pytest, Ruff check, Ruff format check, mypy, and diff check.
- Worker 3 pytest, supplemental proof-surface pytest, Ruff check, Ruff format
  check, mypy, and diff check.
- Worker 4 pytest, Ruff check, Ruff format check, mypy, PowerShell parser
  check, and non-ledger diff check.

Validations failed:

- No accepted validation failed in PM review.
- Worker 1 disclosed intermittent combined PowerShell-backed pytest timeouts
  during worker-side validation; isolated cases passed and the PM accepted the
  focused validated slice.

Receipts generated:

- `.francis/worker-terminal-coordinator/readbacks/worker-1-orb-voice-proof.md`
- `.francis/worker-terminal-coordinator/readbacks/worker-2-lens-overlay-spatial.md`
- `.francis/worker-terminal-coordinator/readbacks/worker-3-voice-receipts.md`
- `.francis/worker-terminal-coordinator/readbacks/worker-4-stage17-completion.md`

Roadmap items advanced:

- Phase 2 / Stage 6 Lens MVP truthfulness.
- Voice-to-Orb proof receipt integrity.
- Lens-to-overlay invalid coordinate refusal truth.
- Stage 17 completion-model handoff guardrails.
- P1 interface truthfulness.
- P9 observability and receipt-backed readback.

Capability classes advanced:

- Presence
- Lens
- Voice
- Governance
- Receipts
- Overlay
- Observability
- Completion Model
- Swarm Infrastructure
- Operator Controls
- API Surface
- Documentation
- Testing

Velocity metrics:

- Worker pass duration: about 13 minutes from first active prompt start to last
  worker completion.
- Accepted lane commits per hour: about 18.5.
- Validated capability classes per hour: about 60.0 based on 13 distinct
  classes advanced in this pass.
- Roadmap closures per day: 0. No roadmap gate closed.
- Worker efficiency: 4 accepted packets from 4 completed workers.
- Drone efficiency: not applicable; no drones used.
- Integration efficiency: 4 accepted lane commits from 4 reviewed packets, with
  one partial artifact rejected.

Most important change:

- Francis gained stronger proof gates around manual acoustic Orb proof, invalid
  lens observation regions, embedded voice provider-boundary evidence, and
  worker/publication handoff claims.

Next bottleneck:

- Live evidence remains the major blocker: microphone-origin Orb movement,
  public ChatGPT ingress or marked fixture proof, live ElevenLabs provider
  receipts, and clean Stage 17 queue-reduction artifacts.

## PM Follow-Up - 2026-06-20T22:39Z

Commit:

- `3f9a7390` - `feat(stage17): bind specs and pack selection proof`

Capability classes advanced:

- Capability Registry
- Governance
- Receipts
- Missions
- Observability
- API Surface
- Documentation
- Testing

What changed:

- Generated `plugin.spec.json` core compatibility now participates in the
  effective Stage 17 promotion-readiness and runtime-execution gate.
- Invocation audit proof now requires the embedded `pack_selection` binding to
  match the same pack, plugin, capability, action, reuse key, and supported
  caller-context set before an operation can count toward reuse proof.
- A fifth selected live metadata-receipt batch reduction was accepted from the
  worker packet and recorded in the completion ledger.
- PM-owned publication markers for W1, W2, and W3 were updated to the pushed
  commit so the coordinator could relaunch those lanes with fresh prompts.

Validation:

- Focused plugin metadata and compatibility pytest group passed.
- Worker-side mission invocation audit proof passed; the Lead Builder local
  rerun was stopped after the active W4 full-CI lane starved pytest startup
  without emitting a failure.
- Python compile and Ruff checks passed before integration for the accepted
  files.
- `git diff --cached --check` passed.
- `scripts/francis-completion-model.ps1 -Mode Status` returned `status=ready`,
  `current_phase=Phase 2`, `stage17_status=open`, and no percentage movement
  allowed.
- `git push origin main` pushed `3f9a7390` to `origin/main`.

Effect:

- Stage 17 gained stronger executable-lifecycle and reusable-invocation
  evidence without claiming closure. The weakest closure blockers remain
  full-library queue/projection evidence and the still-running project-wide
  CI/wiring lane.

## PM Follow-Up - 2026-06-20T23:07Z

Commit:

- `e09af591` - `feat(stage17): harden lifecycle and invocation proof`

Active workers:

- W1 backlog class reduction: accepted and published.
- W2 lifecycle behavior: accepted and published.
- W3 reusable invocation proof: accepted and published.
- W4 CI/wiring: still active on the broad project gate.

Commits produced:

- 1 coherent Lead Builder integration commit.

Commits accepted:

- 1.

Commits rejected:

- 0 from the reviewed W1/W2/W3 packets.

Validations passed:

- `py_compile` for `src\francis\api\routes\plugins.py` and
  `tests\test_api_plugins.py`.
- Focused 13-test Stage 17 plugin acceptance set covering invocation audit
  replay, lifecycle repair compatibility, lifecycle repair/rollback safety, and
  metadata receipt bulk no-write plus selected-batch behavior.
- Ruff check for the touched Python files.
- Ruff format check for the touched Python files.
- `git diff --check` for the accepted files.
- `scripts\francis-completion-model.ps1 -Mode Status`, with Stage 17 still
  open and no percentage movement allowed.
- `git push origin main` pushed `e09af591`.

Validations failed:

- None in the accepted integration packet.
- Full-project CI remains red from the existing Lens proof-script cluster named
  by W4; this commit did not claim to close that gate.

Receipts generated:

- PM publication markers were updated for W1, W2, and W3 with commit
  `e09af591` and their matching prompt hashes.
- W1 live route apply wrote batch
  `stage17_metadata_receipts_bulk_1781996165` with 18 metadata receipts under
  ignored runtime data.
- Completion ledger entries were added for the invocation replay proof,
  lifecycle compatibility guard, and remaining live metadata receipt batch
  reduction.

Roadmap items advanced:

- Stage 17 / Capability Economy.
- Phase 2 governed capability-pack lifecycle and reuse evidence.
- P3 Governance and P9 Observability around capability packs.

Capability classes advanced:

- Capability Registry
- Governance
- Receipts
- Missions
- API Surface
- Documentation
- Testing
- Observability

New capabilities created or strengthened:

- Metadata receipt bulk planning now stays no-write during dry-run and
  failed-fingerprint paths while still clearing the current live selected
  metadata-receipt backlog when confirmed.
- Lifecycle repair now refuses generated-spec/core ambiguous or incompatible
  candidates before dry-run fingerprinting, registry mutation, or lifecycle
  receipt writes.
- Invocation audit proof now has a fast durable-fixture replay path for one pack
  reuse key across multiple mission-shaped operation records, including a guard
  rejection for memory-writing receipts.

Most important change:

- The remaining live `pack_metadata_receipt_missing` backlog class moved from
  18 candidates to 0 through the existing governed route, while lifecycle repair
  became compatibility-aware and reusable invocation proof became easier to
  replay.

Biggest remaining bottleneck:

- Stage 17 remains open. The next named Stage 17 gap is
  `stage17_capability_pack_quality_standards`; full-library/global queue
  projection evidence, proposal/quality evidence closure, publication coverage
  for future worker packets, and full CI/wiring trust remain open.

Next highest leverage action:

- Advance `stage17_capability_pack_quality_standards` through an existing
  governed readback/apply path or build the smallest missing governed path that
  can prove before/after quality-standard evidence without promotion,
  enablement, execution, memory write, or Stage 17 closure overclaim.

## PM Follow-Up - 2026-06-20T23:30Z

Commit:

- `8dd00569` - `fix(stage17): harden quality and reuse safety gates`.

Active workers:

- W1 backlog class reduction: accepted packet for quality-standard batch
  evidence.
- W2 lifecycle behavior: accepted packet for rollback source-receipt safety.
- W3 reusable invocation proof: accepted packet for failed-status reuse
  rejection.
- W4 CI/wiring: parked to preserve usage; not part of the three-worker pass.

Commits produced:

- 1 coherent Stage 17 integration commit.

Commits accepted:

- 1 pushed commit on `main`: `8dd00569`.

Commits rejected:

- 0 complete worker packets rejected. No fresh worker packets were available for
  this cycle.

Validations passed:

- `py_compile` for `src\francis\api\routes\plugins.py` and
  `tests\test_api_plugins.py`.
- Focused invocation audit test for failed-status rejection.
- Focused lifecycle rollback tests for safe source receipts and tampered source
  refusal.
- Focused quality-standard remediation test for dry-run fingerprinting,
  unconfirmed no-write refusal, selected queue count reduction, and selected
  two-pack batch reduction.
- Ruff check for the touched Python files.
- Ruff format check for the touched Python files.
- `git diff --check` for the committed Stage 17 files.
- Completion-model readback after the change still reports Stage 17 open.

Validations failed:

- An initial combined pytest invocation exited without useful output while the
  same tests were still being diagnosed. The Lead Builder split validation by
  lane; the focused lane checks passed.

Receipts generated:

- Completion ledger entry for Stage 17 quality standard and reuse safety gates.
- Worker publication markers for W1/W2/W3 point at `8dd00569` before
  re-prompting those lanes.

Roadmap items advanced:

- Stage 17 / Capability Economy.
- Governed quality-standard remediation.
- Receipt-bound lifecycle rollback.
- Reusable invocation proof truthfulness.

Capability classes advanced:

- Capability Registry
- Governance
- Receipts
- Missions
- API Surface
- Documentation
- Testing
- Observability

New capabilities created or strengthened:

- Quality-standard remediation now requires an echoed dry-run fingerprint before
  registry mutation and reports selected/full-library queue-count evidence.
- Lifecycle rollback now safety-checks the current lifecycle source receipt
  before fingerprinting or mutation and refuses tampered governance/state
  evidence.
- Invocation audit reuse proof now rejects failed operation, invocation, or
  dispatch status records.

Most important change:

- The next `stage17_capability_pack_quality_standards` blocker now has a
  governed dry-run/apply boundary with queue-count evidence instead of a
  mutation-capable plain apply.

Biggest remaining bottleneck:

- Stage 17 remains open. Quality-evidence/proposal closure, full-library/global
  projection proof, publication for future worker packets, and full CI/wiring
  trust remain open.

Next highest leverage action:

- Restart the three-worker coordinator and continue into quality-evidence /
  proposal closure or the next accepted worker packet.

## PM Follow-Up - 2026-06-21T11:50Z

Commit:

- `4b7a2a6c` - `fix(stage17): receipt quality and invocation evidence`.

Active workers:

- W1 quality-standard backlog class reduction: accepted lane readback.
- W2 lifecycle behavior: accepted lane readback.
- W3 reusable invocation proof: accepted lane readback.
- W4 parked to preserve usage.

Commits produced:

- 1 coherent Lead Builder integration commit.

Commits accepted:

- 1 pushed commit on `main`: `4b7a2a6c`.

Commits rejected:

- 0 complete worker packets rejected.

Validations passed:

- `py_compile` for `src\francis\api\routes\plugins.py`,
  `tests\test_api_plugins.py`, and `tests\test_api_missions.py`.
- Ruff check for the three accepted Python files.
- Ruff format check for the three accepted Python files.
- `git diff --check` for the accepted Stage 17 source/test files.
- Combined focused pytest selection covering quality-standard receipt/after-sync
  behavior, lifecycle history compatibility readback, durable invocation audit
  replay, and mission-linked invocation proof.

Validations failed:

- None in the accepted integration packet.
- Full `scripts\check.ps1` was not run in this bounded cycle; the known broad
  CI/wiring gate remains outside this accepted packet.

Receipts generated:

- W1 readback:
  `.francis\worker-terminal-readbacks\worker-1-stage17-backlog-class-reduction.md`.
- W2 readback:
  `.francis\worker-terminal-readbacks\worker-2-stage17-lifecycle-history-compatibility-guard-20260621T113336Z.md`.
- W3 readback:
  `.francis\worker-terminal-coordinator\readbacks\worker-3-voice-receipts.md`.
- W1 live route apply wrote two ignored runtime receipts:
  `stage17_quality_standard_remediation_batch_1782041640_receipt.json` and
  `stage17_quality_standard_remediation_batch_1782042062_receipt.json`.
- Lead Builder post-validation cleanup wrote ignored runtime receipt
  `stage17_quality_standard_remediation_batch_1782042862_receipt.json` after
  the combined focused test run reintroduced one generated quality-standard
  candidate.

Roadmap items advanced:

- Stage 17 / Capability Economy.
- Governed quality-standard remediation and receipt evidence.
- Lifecycle repair-history readback/apply consistency.
- Reusable invocation proof truthfulness.

Capability classes advanced:

- Capability Registry
- Governance
- Receipts
- Missions
- Observability
- API Surface
- Documentation
- Testing

New capabilities created or strengthened:

- Quality-standard remediation now writes durable batch receipts and reports
  generated-sync-aware after counts.
- Lifecycle repair history no longer advertises repair availability when
  generated-spec/core compatibility would block the apply route.
- Invocation audit now exposes unsupported operation-capability receipts as
  rejected evidence instead of silently skipping embedded invocation receipts.

Most important change:

- The current live quality-standard tests/docs backlog class moved from 18
  packs to 0 through the existing governed route, with dedicated receipts and a
  regression preventing after-count overclaims when generated sync adds a new
  candidate. A lead-level post-validation cleanup proved the same route can
  clear a newly reintroduced generated-sync candidate with a separate receipt.

Biggest remaining bottleneck:

- Stage 17 remains open. Final readback still reports
  `migration_candidate_total=1`, `validation_receipt_missing=18`, and
  `proposal_id_missing=18`; full CI/wiring trust is also still not green.

Next highest leverage action:

- Reduce the remaining migration candidate through the existing metadata
  receipt/operator-review path, then use governed remediation to attach
  validation receipts and proposal lineage for the 18 still-blocked packs.

## PM Follow-Up - 2026-06-21T12:25Z

Commit:

- Pending at the time of this entry: Stage 17 migration identity and invocation
  proof-readiness integration.

Active workers:

- W1 metadata-receipt backlog reduction: accepted as runtime evidence only; the
  current lead readback still reports `migration_candidate_total=1`.
- W2 lifecycle/promotion lane: accepted source change for versioned migration
  identity enforcement.
- W3 reusable invocation proof lane: accepted read-only proof-readiness API and
  fixture coverage; mission-linked test assertions were rejected because the
  lead machine could not complete that test.
- W4 parked to preserve usage.

Commits produced:

- 1 pending coherent Lead Builder integration commit.

Commits accepted:

- 0 pushed at the time of this entry.

Commits rejected:

- 0 complete worker packets rejected.
- 1 worker sub-output rejected: W3 mission-linked assertion additions were not
  kept because the lead validation command did not finish in this workspace.

Validations passed:

- `py_compile` for `src\francis\api\routes\plugins.py`,
  `tests\test_api_plugins.py`, and `tests\test_api_missions.py`.
- Focused plugin pytest selection covering metadata receipt migration planning,
  dry-run/no-write behavior, ambiguous version blocking, unversioned migration
  identity blocking, selected before/after counts, and durable invocation audit
  proof-readiness.
- Ruff check and Ruff format check for the accepted Python files.
- `git diff --check` for the accepted source, test, and ledger files.
- Completion-model readback selected the latest Stage 17 ledger entry and kept
  Stage 17 open.

Validations failed or blocked:

- `tests\test_api_missions.py::test_stage17_capability_pack_invocation_reuses_pack_across_direct_and_mission_contexts`
  did not finish in two lead-level isolated attempts, including a longer bounded
  run. No new assertions from this cycle remain in that test.
- Full `scripts\check.ps1` was not run in this bounded cycle.

Receipts generated:

- W1 readback:
  `.francis\worker-terminal-coordinator\readbacks\worker-1-orb-voice-proof.md`.
- W2 readback:
  `.francis\worker-terminal-coordinator\readbacks\worker-2-stage17-lifecycle-promotion.md`.
- W3 readback:
  `.francis\worker-terminal-coordinator\readbacks\worker-3-voice-receipts.md`.
- W1 live route apply wrote ignored runtime receipt
  `capability_pack_metadata_1782043295_legacy-generated-stage17reusableinvocationplugin.json`.

Roadmap items advanced:

- Stage 17 / Capability Economy.
- Governed migration metadata identity.
- Reusable invocation proof readback.
- Receipt-linked auditability.

Capability classes advanced:

- Capability Registry
- Governance
- Receipts
- Observability
- API Surface
- Documentation
- Testing

New capabilities created or strengthened:

- Metadata-receipt migration now blocks unversioned pack candidates before dry
  run fingerprinting, registry mutation, or receipt writes.
- Successful migration metadata receipts now carry a versioned migration
  identity contract.
- Invocation audit now exposes an authority-denying `proof_readiness` summary
  that names the strongest accepted reuse evidence and missing evidence.

Most important change:

- Stage 17 gained stricter migration identity governance and a coordinator-
  consumable invocation proof-readiness readback without adding execution
  authority or a parallel capability substrate.

Biggest remaining bottleneck:

- Stage 17 remains open. Current lead readback reports
  `migration_candidate_total=1`; validation/proposal closure and full CI remain
  unproven.

Next highest leverage action:

- Have the next three-worker cycle target the still-live migration candidate,
  the 18 validation/proposal blockers, and the mission test hang as separate
  lanes, with local drones limited to narrow analysis packets.

## PM Follow-Up - 2026-06-21T13:00Z

Commit:

- Pending at the time of this entry: Stage 17 artifact reconstruction,
  lifecycle enable, and operation-readback proof integration.

Active workers:

- W1 quality-evidence artifact reconstruction: accepted source/test hardening
  plus live runtime evidence reducing the artifact reconstruction queue from
  `18 -> 17`.
- W2 executable lifecycle lane: accepted non-staged `/plugins/enable`
  lifecycle-blocking gate.
- W3 reusable invocation proof lane: accepted read-only operation
  caller-context readback binding for the durable invocation audit fixture.
  Worker-attempted live mission proof remained inconclusive and was not counted
  as accepted evidence.
- W4 parked to preserve usage.

Active drones:

- 0 local drones reported by the accepted worker packets. The next cycle should
  use local drones only for narrow analysis packets that workers independently
  verify.

Commits produced:

- 1 pending coherent Lead Builder integration commit.

Commits accepted:

- 0 pushed at the time of this entry.

Commits rejected:

- 0 complete worker packets rejected.
- 1 worker sub-output rejected: W3 mission-linked test assertions were not kept
  because the live mission proof did not finish in the bounded window.

Validations passed:

- `py_compile` for `src\francis\api\routes\plugins.py`,
  `tests\test_api_plugins.py`, and `tests\test_api_missions.py`.
- Ruff check for the three accepted Python files.
- Ruff format check for the three accepted Python files.
- `git diff --check` for the accepted Stage 17 source/test files.
- Focused pytest selection covering artifact reconstruction queue evidence and
  dry-run apply confirmation, lifecycle enable blocking, adjacent lifecycle
  promotion/readback behavior, and durable invocation audit replay.
- Completion-model readback kept Stage 17 open.
- FastAPI `TestClient` readback reported `migration_candidate_total=1`,
  `remediation_queue_count=17`, `validation_receipt_missing=17`, and
  `proposal_id_missing=17`.

Validations failed or blocked:

- Full `scripts\check.ps1` was not run in this bounded cycle.
- Worker 3's live mission-linked proof did not complete in its bounded window.
  No live mission-path pass is claimed by this entry.

Receipts generated:

- W1 readback:
  `.francis\worker-terminal-coordinator\readbacks\worker-1-orb-voice-proof.md`.
- W2 readback:
  `.francis\worker-terminal-coordinator\readbacks\worker-2-stage17-lifecycle-promotion.md`.
- W3 readback:
  `.francis\worker-terminal-coordinator\readbacks\worker-3-voice-receipts.md`.
- W1 live route apply wrote ignored runtime validation receipts and proposal
  lineage receipts under `data/artifacts/plugins/validations/` and
  `data/artifacts/plugins/proposals/` for four
  `legacy.generated.capabilitylineageplugin` capabilities.

Roadmap items advanced:

- Stage 17 / Capability Economy.
- Governed validation/proposal artifact reconstruction.
- Executable lifecycle behavior.
- Reusable invocation proof truthfulness.
- Receipt-linked queue observability.

Capability classes advanced:

- Capability Registry
- Governance
- Receipts
- Missions
- Observability
- API Surface
- Documentation
- Testing

New capabilities created or strengthened:

- Artifact reconstruction apply now requires a matching dry-run fingerprint and
  exposes selected/global before-after queue evidence.
- A live artifact reconstruction packet removed one capability pack from the
  remaining quality-evidence queue through the existing governed route.
- Non-staged `/plugins/enable` can no longer mark lifecycle-blocked plugins as
  enabled before repair/rollback.
- Invocation audit proof readiness now requires operation caller-context
  readback binding across supported mission operation shapes.

Most important change:

- Stage 17 moved from merely having artifact reconstruction as a writer to
  having a fingerprint-confirmed, queue-evidenced artifact reconstruction apply
  path that reduced one live pack while still reporting the remaining queue
  honestly.

Biggest remaining bottleneck:

- Stage 17 remains open. Current lead readback reports
  `migration_candidate_total=1`, `remediation_queue_count=17`,
  `validation_receipt_missing=17`, and `proposal_id_missing=17`; full CI and
  live mission proof remain unproven.

Next highest leverage action:

- Launch the next three-worker cycle with W1 reducing the next
  validation/proposal artifact-reconstruction pack, W2 converting lifecycle
  block visibility into an operator-readable selected-scope readback, and W3
  isolating the mission-linked invocation proof hang without modifying mission
  assertions until the command finishes.

## PM Follow-Up - 2026-06-21T13:30Z

Commit:

- Pending at the time of this entry: Stage 17 artifact reconstruction batch
  receipts, metadata migration lifecycle guard, and invocation caller-context
  binding.

Active workers:

- W1 quality-evidence artifact reconstruction: accepted durable batch receipt
  contract and API response linkage for governed artifact reconstruction apply.
- W2 lifecycle and migration guard: accepted selected lifecycle blocking for
  metadata receipt migration before dry-run fingerprinting or writes.
- W3 reusable invocation proof: accepted caller-context binding in reusable
  invocation receipts across direct dry-run contexts.
- W4 parked to preserve usage.

Active drones:

- 0 local drones reported by the accepted worker packets. Local drones remain
  available for the next cycle as narrow inspection/validation packets verified
  by each worker.

Commits produced:

- 1 pending coherent Lead Builder integration commit.

Commits accepted:

- 0 pushed at the time of this entry.

Commits rejected:

- 0 complete worker packets rejected.
- 1 brittle lead-side test assumption was rejected and replaced with
  long-path-safe filesystem verification for the accepted artifact receipt test.

Validations passed:

- Single focused reconstruction receipt pytest passed after the lead fixture
  repair.
- 10-test focused Stage 17 selection passed for reconstruction receipts,
  metadata receipt lifecycle guard coverage, metadata migration regressions,
  durable invocation audit replay, and direct invocation caller-context binding.
- `py_compile` passed for `src\francis\api\routes\plugins.py`,
  `tests\test_api_plugins.py`, and `tests\test_api_missions.py`.
- Ruff check passed for the same three files.
- Ruff format check passed for the same three files.
- `git diff --check` passed for the same Stage 17 source/test files.
- Completion-model readback kept Stage 17 open.
- FastAPI `TestClient` readback reported `migration_candidate_total=1`,
  `remediation_queue_count=17`,
  `validation_receipt_reconstruction_required_count=2830`, and
  `proposal_lineage_reconstruction_required_count=2830`.

Validations failed or blocked:

- Full `scripts\check.ps1` was not run in this bounded integration cycle.
- Stage 17 did not close. Migration, quality-evidence backlog closure,
  proposal review, promotion, enablement, live mission-path proof, and full CI
  remain unproven.

Receipts generated:

- W1 readback:
  `.francis\worker-terminal-coordinator\readbacks\worker-1-orb-voice-proof.md`.
- W2 readback:
  `.francis\worker-terminal-coordinator\readbacks\worker-2-lens-overlay-spatial.md`.
- W3 readback:
  `.francis\worker-terminal-coordinator\readbacks\worker-3-voice-receipts.md`.
- W1 live route proof wrote ignored runtime receipt artifacts including
  `stage17_artifact_reconstruction_batch_1782047557_receipt.json`, 25
  validation receipts, and 25 proposal lineage receipts for the selected legacy
  generated pack. This evidence was treated as local runtime proof, not source
  truth.

Roadmap items advanced:

- Stage 17 / Capability Economy.
- Receipt-backed artifact reconstruction.
- Executable lifecycle migration safety.
- Reusable invocation receipt truthfulness.
- Worker-swarm integration discipline.

Capability classes advanced:

- Capability Registry
- Governance
- Receipts
- Missions
- Observability
- API Surface
- Documentation
- Testing

New capabilities created or strengthened:

- Artifact reconstruction apply now leaves a durable receipt that explains the
  batch, fingerprint confirmation, queue before/after counts, artifacts written,
  and authority boundaries.
- Metadata receipt migration cannot proceed for selected lifecycle-blocked packs
  before the dry-run/apply path records that refusal.
- Reusable invocation receipts bind caller context to pack selection without
  granting execution or mutation authority.
- Stage 17 readback now has stronger evidence separating applied source
  contracts, live runtime proof, and remaining blockers.

Most important change:

- Stage 17 reconstruction moved from response-only proof to durable,
  receipt-backed batch evidence while preserving dry-run confirmation and
  authority limits.

Biggest remaining bottleneck:

- Stage 17 remains open. Current readback reports
  `migration_candidate_total=1`, `remediation_queue_count=17`, and 2,830
  validation/proposal reconstruction gaps. The remaining generated invocation
  pack and quality-evidence backlog are the highest leverage targets.

Next highest leverage action:

- Launch the next three-worker cycle with W1 reducing the remaining
  quality-evidence reconstruction queue, W2 closing the live metadata migration
  candidate safely, and W3 proving reusable invocation through a mission path
  without adding fake execution claims.

## PM Follow-Up - 2026-06-21T14:15Z

Commit:

- Pending at the time of this entry: deterministic artifact reconstruction
  selection, metadata receipt apply revalidation, live migration-candidate
  removal, and lead fixture hardening.

Active workers:

- W1 backlog reduction: accepted deterministic `smallest_full_pack_first`
  selection on the existing artifact reconstruction route, plus live
  quality-evidence queue reduction from `17 -> 16`.
- W2 lifecycle/migration: accepted
  `stage17_capability_pack_metadata_receipt_apply_revalidation_v1` so metadata
  receipt apply revalidates lifecycle immediately before registry/receipt
  writes.
- W3 reusable invocation/migration: accepted live metadata readback movement
  from `migration_candidate_total=1` to `0`, while preserving the caveat that
  one route response returned `internal_api_error` after a Windows registry
  replace `PermissionError`.
- W4 remained parked.

Active drones:

- 0 local drones reported by the accepted worker packets.

Commits produced:

- 1 pending coherent Lead Builder integration commit.

Commits accepted:

- 0 pushed at the time of this entry.

Commits rejected:

- 0 complete worker packets rejected.
- 1 metadata apply success claim was narrowed: durable readback and receipt
  evidence were accepted, but a clean route-response success was not claimed.

Validations passed:

- Lead `py_compile`, Ruff check, Ruff format check, and `git diff --check`
  passed on the accepted Stage 17 source/test/docs paths.
- Lead focused pytest passed for artifact reconstruction receipts, truncated
  chunk reconstruction, deterministic smallest-pack selection, metadata receipt
  apply revalidation/lifecycle guard behavior, selected batch reporting,
  durable invocation audit replay, and direct invocation caller-context binding.
- Completion-model readback reported latest ledger entry
  `2026-06-21 14:00Z - Stage 17 deterministic smallest-pack artifact reconstruction batch`,
  `stage17_status=open`, and `current_phase=Phase 2`.
- FastAPI `TestClient` readback reported `migration_candidate_total=0`,
  `remediation_queue_count=16`,
  `validation_receipt_reconstruction_required_count=2821`, and
  `proposal_lineage_reconstruction_required_count=2821`.

Validations failed or blocked:

- The initial lead focused pytest run exposed nondeterministic artifact-link
  fixture behavior; this was repaired and the focused group then passed.
- Full `scripts\check.ps1`, full plugin suite, and CI were not run.
- Stage 17 remains open. Full quality-evidence closure, proposal review,
  promotion, enablement, execution, clean metadata apply response closure, and
  live mission-path proof remain unproven.

Receipts generated:

- W1 readback:
  `.francis\worker-terminal-readbacks\worker-1-stage17-backlog-class-reduction.md`.
- W2 readback:
  `.francis\worker-terminal-readbacks\worker-2-stage17-metadata-receipt-apply-revalidation-20260621T084445-0500.md`.
- W3 last-message packet:
  `.francis\worker-terminal-logs\worker-3-voice-receipts-20260621T1334184704159Z.last-message.md`.
- Runtime receipt evidence included
  `stage17_artifact_reconstruction_batch_1782050127_receipt.json` and
  `capability_pack_metadata_1782050038_legacy-generated-stage17reusableinvocationplugin.json`.

Roadmap items advanced:

- Stage 17 / Capability Economy.
- Governed artifact reconstruction selection and receipt linkage.
- Metadata receipt migration lifecycle safety.
- Capability registry migration posture.
- Worker-swarm integration discipline.

Capability classes advanced:

- Capability Registry
- Governance
- Receipts
- Missions
- Observability
- API Surface
- Documentation
- Testing

New capabilities created or strengthened:

- Operators can ask the existing artifact reconstruction route to select the
  smallest eligible full pack deterministically without hand-picking pack IDs.
- Artifact reconstruction dry-run/apply fingerprints and receipts now bind the
  selection strategy and selected pack IDs.
- Metadata receipt apply now has a named apply-time lifecycle revalidation
  contract before writes.
- The live reusable-invocation metadata migration candidate count is now zero
  in readback, with a truthful caveat about the route-response error.

Most important change:

- Stage 17 now has a reusable governed mechanism for reducing the remaining
  quality-evidence reconstruction backlog one smallest full pack at a time,
  with receipts and before/after counts.

Biggest remaining bottleneck:

- Stage 17 remains open with `remediation_queue_count=16` and 2,821
  validation/proposal reconstruction gaps. The metadata apply
  `internal_api_error` also needs a bounded repair before that route can be
  called clean.

Next highest leverage action:

- Investigate and fix the metadata receipt apply Windows registry replacement
  error, then continue selector-backed quality-evidence reconstruction batches
  with receipts and before/after readbacks.

## PM Follow-Up - 2026-06-21T15:00Z

Commit:

- Pending at the time of this entry: budget-aware artifact reconstruction
  selection, metadata receipt persistence guard, invocation mission-shape audit
  proof, and mission-test diagnostic readback.

Active workers:

- W1 quality-evidence artifact reconstruction: accepted the budget-aware
  `smallest_full_pack_first` selector behavior and fixture proof for reducing a
  bounded two-pack batch while skipping an oversized pack. Live apply evidence
  was rejected because the attempted live apply returned no JSON route output
  and no new receipt-backed queue movement.
- W2 metadata receipt apply: accepted
  `stage17_capability_pack_metadata_receipt_apply_persistence_guard_v1`, which
  blocks metadata receipt writes when registry/catalog persistence fails,
  attempts rollback, and returns a structured blocked response.
- W3 reusable invocation proof: accepted the read-only plugin invocation audit
  `mission_shape_proof` projection and durable fixture coverage. The
  mission-test assertion additions were rejected because the existing mission
  fixture fails before the new assertions while approving the forge proposal.
- W4 remained parked to honor the three-worker usage cap.

Active drones:

- 0 local drones reported by the accepted worker packets. The next prompts
  should require each worker to use or explicitly skip up to four local drones
  and report their evidence packets separately.

Commits produced:

- 1 pending coherent Lead Builder integration commit.

Commits accepted:

- 0 pushed at the time of this entry.

Commits rejected:

- 0 complete worker packets rejected.
- 2 worker sub-outputs rejected: W1 live apply queue-movement claim and W3
  mission-test assertion additions.

Validations passed:

- Lead `py_compile`, Ruff check, Ruff format check, and `git diff --check`
  passed on the accepted Stage 17 source/test/docs paths.
- Lead focused pytest passed for metadata receipt persistence failure rollback,
  durable invocation audit replay, smallest full-pack reconstruction selection,
  budget-aware reconstruction selection, missing artifact reconstruction, and
  truncated plan chunk reconstruction.
- Completion-model readback selected latest Stage 17 ledger entry
  `2026-06-21 14:29Z - Stage 17 budget-aware artifact reconstruction selector`,
  kept `stage17_status=open`, and kept `current_phase=Phase 2`.
- FastAPI readback returned `migration_candidate_total=1`,
  `remediation_queue_count=16`,
  `validation_receipt_reconstruction_required_count=2822`, and
  `proposal_lineage_reconstruction_required_count=2822`.

Validations failed or blocked:

- `tests\test_api_missions.py::test_stage17_capability_pack_invocation_reuses_pack_across_direct_and_mission_contexts`
  failed before W3's new assertions with forge proposal approval
  `{'applied': False, 'error': 'not_found', 'item': None, 'ok': False}`.
  The retained change only adds the response body to the helper assertion so the
  fixture failure remains diagnosable.
- Full `scripts\check.ps1`, full plugin suite, and CI were not run.
- Stage 17 remains open. Live quality-evidence queue reduction, clean metadata
  apply response closure, full quality-evidence closure, proposal review,
  promotion, enablement, execution, and live mission-path proof remain unproven.

Receipts generated:

- W1 last-message packet:
  `.francis\worker-terminal-logs\worker-1-orb-voice-proof-20260621T1417491890974Z.last-message.md`.
- W2 last-message packet:
  `.francis\worker-terminal-logs\worker-2-lens-overlay-spatial-20260621T1418074441138Z.last-message.md`.
- W3 last-message packet:
  `.francis\worker-terminal-logs\worker-3-voice-receipts-20260621T1418233624474Z.last-message.md`.
- Coordinator publication markers still require the final pushed commit hash
  before the next worker prompts may launch.

Roadmap items advanced:

- Stage 17 / Capability Economy.
- Governed artifact reconstruction selection.
- Metadata receipt apply safety.
- Reusable invocation proof readback.
- Worker-swarm publication discipline.

Capability classes advanced:

- Capability Registry
- Governance
- Receipts
- Missions
- Observability
- API Surface
- Documentation
- Testing

New capabilities created or strengthened:

- Artifact reconstruction selection can now build a bounded batch that respects
  both per-pack and total capability budgets when using
  `smallest_full_pack_first`.
- Metadata receipt bulk apply now fails closed before receipt writes when
  registry/catalog persistence fails, with rollback evidence and no false
  receipt record.
- Reusable invocation audit now exposes a read-only mission-shape proof based
  on accepted operation-output invocation receipts without granting execution or
  mutation authority.
- Mission test proposal approval failures now include the response body in the
  assertion output.

Most important change:

- Stage 17 gained stronger fail-closed persistence and selector controls around
  the existing capability-pack routes without creating a parallel substrate.

Biggest remaining bottleneck:

- Stage 17 remains open with `migration_candidate_total=1`,
  `remediation_queue_count=16`, and 2,822 validation/proposal reconstruction
  gaps. The live mission-path proof still fails at proposal lookup before the
  reusable invocation assertions can run.

Next highest leverage action:

- Re-prompt W1 to complete a bounded live budget-aware reconstruction apply
  with a returned receipt, W2 to close the remaining metadata migration
  candidate cleanly, and W3 to repair the mission fixture proposal lookup before
  proving mission-shape invocation reuse. Each worker should use or explicitly
  skip up to four local drones and publish a packet before the next prompt.

### Cycle 2026-06-21T15:08Z to 2026-06-21T15:36Z

Scope: three-worker Stage 17 continuation with local-drone assistance while
Codex worker launches were blocked by usage limits.

Active workers:

- `worker-1-orb-voice-proof`
- `worker-2-lens-overlay-spatial`
- `worker-3-voice-receipts`

Active drones:

- 12 local-drone attempts were recorded under `.francis\local-drones`.
- The first untuned drone in each worker lane timed out and was rejected as
  unavailable evidence.
- The remaining tuned drones completed advisory packets. Only the W3 long-path
  proposal-root hypothesis survived direct repo verification.

Commits produced: pending at report time.

Commits accepted: pending at report time.

Commits rejected: 0.

Validations passed:

- `py_compile` for `src\francis\api\routes\forge.py`,
  `src\francis\api\routes\plugins.py`, `tests\test_api_plugins.py`, and
  `tests\test_api_missions.py`.
- `ruff check --no-cache` for the same touched files.
- `ruff format --check --no-cache` for the same touched files.
- Focused pytest:
  `tests\test_api_plugins.py::test_plugins_forge_proposal_review_supports_long_windows_artifact_paths`.
- Focused pytest:
  `tests\test_api_missions.py::test_stage17_capability_pack_invocation_reuses_pack_across_direct_and_mission_contexts`.
- Combined focused pytest for both tests in one command.

Validations failed or blocked:

- The prior Codex worker iterations 118 and 119 failed before implementation
  because Codex reported a usage-limit retry time of 11:19 AM.
- The first local-drone attempt in each lane timed out through Ollama and was
  rejected as unavailable evidence.
- An unisolated mission-proof run was stopped after exceeding the focused-test
  window while syncing a 10 MB generated-plugin registry. It is not accepted as
  passing validation.

Receipts generated:

- Local-drone receipts:
  `.francis\local-drones\receipts.jsonl`.
- Retained pytest evidence roots:
  `data\test_runs\pytest\stage17-lead-longpath-regression2`,
  `data\test_runs\pytest\stage17-lead-mission-proof-isolated`, and
  `data\test_runs\pytest\stage17-lead-final-focused2`.

Roadmap items advanced:

- Stage 17 / Capability Economy.
- Governed proposal review and promotion-readiness path.
- Reusable invocation mission proof.
- Worker/drone evidence discipline.

Capability classes advanced:

- Governance
- Receipts
- Missions
- Observability
- Capability Registry
- API Surface
- Documentation
- Testing

New capabilities created or strengthened:

- Forge proposal review can now operate on retained Windows artifact paths
  longer than 260 characters.
- Plugin proposal review state and proposal friction evidence can now read the
  same long-path proposal records that plugin build wrote.
- The Stage 17 reusable invocation mission proof now passes in an isolated
  generated-plugin root, preserving the actual governed build, review, enable,
  direct/tool invocation, mission-linked operation, and receipt assertions.
- A focused long-path regression prevents recurrence of false `not_found`
  proposal-review failures caused by Windows path length.

Most important change:

- Stage 17 mission-path proof moved from blocked at proposal lookup to a passing
  validated mission invocation proof without weakening governance.

Biggest remaining bottleneck:

- Live quality-evidence queue reduction remains open. The next accepted queue
  movement still requires clean JSON output, before/after counts, and a durable
  artifact reconstruction receipt.

Next highest leverage action:

- Run a bounded live `smallest_full_pack_first` artifact reconstruction apply
  that records `stage17_capability_pack_artifact_reconstruction_receipt_v1`, or
  produce a precise blocker if the live apply still cannot return clean JSON.

### Cycle 2026-06-21T15:36Z to 2026-06-21T17:04Z

Scope: three-worker Stage 17 continuation after the usage reset, with the lead
owning the live artifact reconstruction apply.

Active workers:

- Worker 1: artifact reconstruction route/test defect isolation.
- Worker 2: Stage 17 CI and wiring pass.
- Worker 3: completion-model artifact reconstruction receipt readback.

Active drones:

- 0 local drones were accepted in this cycle.
- Workers were allowed up to 4 local drones each, but the accepted packets used
  direct inspection and validation instead.

Commits produced: pending at report time.

Commits accepted: pending at report time.

Commits rejected: 0.

Validations passed:

- Live reconstruction dry-run through FastAPI `TestClient` returned clean JSON
  for `selection_strategy=smallest_full_pack_first`,
  `planned_pack_count=1`, `planned_capability_count=4`, and fingerprint
  `6c84132a7b52e87c7f0789e81e7dc1f982633c362077b1fc1ae28137a1ae1256`.
- Live reconstruction apply through FastAPI `TestClient` returned
  `ok=true`, `applied=true`, `status=recorded`,
  `recorded_pack_count=1`, `recorded_capability_count=4`, and
  `candidate_reduction_count=1`.
- Live remediation readback returned `remediation_queue_count=15` and
  `artifact_reconstruction_required_count=15`.
- `.\scripts\francis-completion-model.ps1` returned clean JSON with
  `stage17_artifact_reconstruction_evidence` for
  `stage17_artifact_reconstruction_batch_1782061142_receipt`.
- Focused pytest:
  `tests\test_api_plugins.py::test_plugins_capability_pack_quality_evidence_reconstruction_dry_run_avoids_registry_persistence`.
- Focused pytest:
  `tests\test_api_plugins.py::test_plugins_capability_pack_quality_evidence_reconstruction_selects_smallest_full_pack`.
- Focused pytest:
  `tests\test_francis_completion_model_script.py::test_francis_completion_model_reports_stage17_artifact_reconstruction_evidence`.
- `ruff check --no-cache` on `src\francis\api\routes\plugins.py`,
  `tests\test_api_plugins.py`, and
  `tests\test_francis_completion_model_script.py`.
- `ruff format --check --no-cache` on the same files.
- Worker 2 reported `tests\test_completion_model.py` plus
  `tests\test_francis_completion_model_script.py` passed with 11 tests, a
  `/completion-model/status` `TestClient` probe passed, and focused
  plugin/governance reconstruction tests passed.

Validations failed or blocked:

- An initial full-library dry-run took longer than the practical command
  window, but later returned clean JSON; no second dry-run was launched.
- `.\scripts\francis-completion-model.ps1 -Json` failed because the script
  does not expose a `-Json` parameter; the accepted readback command uses the
  existing `-Mode Status` default output.
- Worker 2 rejected
  `test_plugins_forge_proposal_review_supports_long_windows_artifact_paths` as
  evidence because the generated path was 245 characters, below the test's
  `>260` precondition in this checkout.

Receipts generated:

- `data\artifacts\plugins\capability_packs\artifact_reconstructions\stage17_artifact_reconstruction_batch_1782061142_receipt.json`.
- Receipt SHA-256:
  `DE7AD0136A8471219F136C86912468C1F59915BE92EEECC241C01792D1EB6A9D`.

Roadmap items advanced:

- Stage 17 / Capability Economy.
- Governed quality-evidence artifact reconstruction.
- Completion-model readback for live Stage 17 receipt evidence.
- Worker packet verification and integration discipline.

Capability classes advanced:

- Capability Registry
- Governance
- Receipts
- Observability
- Completion Model
- API Surface
- Documentation
- Testing

New capabilities created or strengthened:

- Artifact reconstruction dry-run now avoids premature registry/catalog
  persistence before dry-run confirmation or operator approval.
- A regression proves dry-run can still produce a governed fingerprint when
  registry persistence is unavailable.
- Completion-model readback can now surface durable Stage 17 artifact
  reconstruction receipt evidence without granting write, approval, promotion,
  execution, or memory authority.
- The current wiring diagram now records the mounted route-family inventory and
  clarifies the Stage 17 live quality-evidence reconstruction queue as the
  active blocker.
- The live Stage 17 quality-evidence queue has one receipt-backed reduction:
  `16 -> 15`.

Most important change:

- Stage 17 moved from "live reconstruction apply still unproven" to a verified
  live queue reduction backed by a durable reconstruction receipt.

Biggest remaining bottleneck:

- Stage 17 still has 15 artifact reconstruction-required packs, plus remaining
  metadata, proposal-review, promotion, enablement/execution, and full-CI gates.

Next highest leverage action:

- Run the next bounded `smallest_full_pack_first` apply, or choose the smallest
  independent Stage 17 gate that can produce receipt-backed before/after
  evidence without touching Orb visuals or unrelated dirty work.

### Cycle 2026-06-21T17:04Z to 2026-06-21T17:12Z

Scope: second Stage 17 live artifact reconstruction apply plus receipt
integrity hardening for repeated applies.

Active workers:

- Worker 1: repeated-apply route/test receipt integrity.
- Worker 2: read-only CI/wiring verification for pushed commit `09a2e468`.
- Worker 3: completion-model readback sufficiency inspection.

Active drones:

- 0 local drones were accepted in this cycle.

Commits produced: `41471603 fix(stage17): preserve reconstruction receipt integrity`.

Commits accepted: `41471603 fix(stage17): preserve reconstruction receipt integrity`.

Commits rejected: 0.

Validations passed:

- Live reconstruction dry-run through FastAPI `TestClient` returned clean JSON
  for `legacy.generated.capabilitypromotionreceiptsplugin`,
  `planned_pack_count=1`, `planned_capability_count=4`, and fingerprint
  `03b41f8da94c1eacc86f2a755d7a243bbeec2b2a650ee37facbcf462ba5c42be`.
- Live reconstruction apply through FastAPI `TestClient` returned
  `ok=true`, `applied=true`, `status=recorded`,
  `recorded_pack_count=1`, `recorded_capability_count=4`, and
  `candidate_reduction_count=1`.
- Live remediation readback returned `remediation_queue_count=14` and
  `artifact_reconstruction_required_count=14`.
- `.\scripts\francis-completion-model.ps1` returned clean JSON with
  `stage17_artifact_reconstruction_evidence` for
  `stage17_artifact_reconstruction_batch_1782061814_1c931221_receipt`.
- `py_compile` on `src\francis\api\routes\plugins.py` and
  `tests\test_api_plugins.py`.
- Focused pytest:
  `tests\test_api_plugins.py::test_plugins_capability_pack_quality_evidence_reconstruction_receipts_do_not_collide_same_second`.
- Focused pytest:
  `tests\test_api_plugins.py::test_plugins_capability_pack_quality_evidence_reconstruction_dry_run_avoids_registry_persistence`.
- Focused pytest:
  `tests\test_api_plugins.py::test_plugins_capability_pack_quality_evidence_reconstruction_selects_smallest_full_pack`.
- Focused pytest:
  `tests\test_api_plugins.py::test_plugins_capability_pack_quality_evidence_reconstruction_selects_smallest_budgeted_batch`.
- `ruff check --no-cache` and `ruff format --check --no-cache` on
  `src\francis\api\routes\plugins.py` and `tests\test_api_plugins.py`.

Validations failed or blocked:

- Full GitHub CI was not accepted as complete. Worker 2 reported CodeQL action
  and JavaScript/TypeScript checks succeeded for `09a2e468`, but other checks
  were still in progress.
- Full local `.\scripts\check.ps1` was not run.

Receipts generated:

- `data\artifacts\plugins\capability_packs\artifact_reconstructions\stage17_artifact_reconstruction_batch_1782061814_1c931221_receipt.json`.
- Receipt SHA-256:
  `048341DA24D9F394B420C5E36312C9AA42FEC42D83A583D6E5F33B5212FE52D1`.

Roadmap items advanced:

- Stage 17 / Capability Economy.
- Governed quality-evidence artifact reconstruction.
- Receipt integrity for repeated operator-approved applies.
- Completion-model receipt readback continuity.

Capability classes advanced:

- Capability Registry
- Governance
- Receipts
- Observability
- Completion Model
- API Surface
- Testing
- Documentation

New capabilities created or strengthened:

- Repeated artifact reconstruction applies now produce unique batch and receipt
  IDs even when two applies share the same second.
- A regression verifies same-second receipt paths do not collide and that each
  preserved receipt retains its selected pack evidence.
- The live Stage 17 quality-evidence queue has another receipt-backed
  reduction: `15 -> 14`.

Most important change:

- Stage 17 now has repeatable reconstruction queue movement without risking
  same-second receipt overwrite.

Biggest remaining bottleneck:

- Stage 17 still has 14 artifact reconstruction-required packs and unresolved
  metadata, proposal-review, promotion, enablement/execution, and full-CI gates.

Next highest leverage action:

- Continue bounded `smallest_full_pack_first` applies while the route remains
  clean, or pause to close the next non-reconstruction Stage 17 gate if the
  queue stops yielding safe full-pack candidates.

### Cycle 2026-06-21T17:12Z to 2026-06-21T17:16Z

Scope: third Stage 17 live artifact reconstruction apply through the governed
route after receipt-integrity hardening.

Active workers:

- Worker 1: read-only repeat-apply integrity inspection.
- Worker 2: read-only GitHub/check-run and local readback verification.
- Worker 3: ledger/evolution evidence checklist and prior-cycle correction.

Active drones:

- 0 local drones were accepted in this cycle.

Commits produced: pending at report time.

Commits accepted: pending at report time.

Commits rejected: 0.

Validations passed:

- Live reconstruction dry-run through FastAPI `TestClient` returned clean JSON
  for `legacy.generated.capabilityqualitydocsplugin`,
  `planned_pack_count=1`, `planned_capability_count=4`, and fingerprint
  `fdafcbbc8cf31cf83862fdf831d319d042258a684e3f69501c598a004bb47d2f`.
- Live reconstruction apply through FastAPI `TestClient` returned
  `ok=true`, `applied=true`, `status=recorded`,
  `recorded_pack_count=1`, `recorded_capability_count=4`, and
  `candidate_reduction_count=1`.
- Live remediation readback returned `remediation_queue_count=13` and
  `artifact_reconstruction_required_count=13`.
- `.\scripts\francis-completion-model.ps1` returned clean JSON with
  `stage17_artifact_reconstruction_evidence` for
  `stage17_artifact_reconstruction_batch_1782062155_d792f162_receipt`.
- Worker 1 reported `py_compile` pass for
  `src\francis\api\routes\plugins.py` and `tests\test_api_plugins.py`.
- Worker 1 reported the four focused reconstruction tests passed.
- Worker 3 reported `git diff --check -- docs\operations\CAPABILITY_EVOLUTION_REPORT.md`
  passed after correcting the prior cycle's commit-status lines.

Validations failed or blocked:

- Full GitHub CI was not accepted as complete. Worker 2 reported CodeQL checks
  and CI for `41471603` were still in progress.
- Full local `.\scripts\check.ps1` was not run.
- Worker 2 rejected `09a2e468` as complete CI proof because CI matrix jobs were
  cancelled despite CodeQL success.

Receipts generated:

- `data\artifacts\plugins\capability_packs\artifact_reconstructions\stage17_artifact_reconstruction_batch_1782062155_d792f162_receipt.json`.
- Receipt SHA-256:
  `522F79E50E9DA7678094990D70A2AE42085716A2047D8A44CAF813310C4968D7`.

Roadmap items advanced:

- Stage 17 / Capability Economy.
- Governed quality-evidence artifact reconstruction.
- Completion-model receipt readback continuity.
- Worker packet verification and evidence discipline.

Capability classes advanced:

- Capability Registry
- Governance
- Receipts
- Observability
- Completion Model
- Documentation

New capabilities created or strengthened:

- The live Stage 17 quality-evidence queue has another receipt-backed
  reduction: `14 -> 13`.
- Completion-model status continued to select the newest durable artifact
  reconstruction receipt without implying closure or authority.
- The evolution report now records pushed commit `41471603` as produced and
  accepted in the prior cycle instead of leaving that cycle pending.

Most important change:

- The governed reconstruction route has now produced three consecutive
  receipt-backed live queue reductions.

Biggest remaining bottleneck:

- Stage 17 still has 13 artifact reconstruction-required packs and unresolved
  metadata, proposal-review, promotion, enablement/execution, and full-CI gates.

Next highest leverage action:

- Continue bounded `smallest_full_pack_first` applies while clean candidates
  remain, with each accepted movement backed by dry-run fingerprint, apply
  response, receipt hash, readback, and focused validation.

### Cycle 2026-06-21T17:16Z to 2026-06-21T17:20Z

Scope: fourth Stage 17 live artifact reconstruction apply through the governed
route.

Active workers:

- Lead-only live mutation. Prior cycle workers were closed before this apply.

Active drones:

- 0 local drones were accepted in this cycle.

Commits produced: pending at report time.

Commits accepted: pending at report time.

Commits rejected: 0.

Validations passed:

- Live reconstruction dry-run through FastAPI `TestClient` returned clean JSON
  for `legacy.generated.capabilityqualitystandardsplugin`,
  `planned_pack_count=1`, `planned_capability_count=4`, and fingerprint
  `7b91a8195cf17ae0ce9d629b6fd516d983bfb448408e3877ae9fc4c5198ec59b`.
- Live reconstruction apply through FastAPI `TestClient` returned
  `ok=true`, `applied=true`, `status=recorded`,
  `recorded_pack_count=1`, `recorded_capability_count=4`, and
  `candidate_reduction_count=1`.
- Live remediation readback returned `remediation_queue_count=12` and
  `artifact_reconstruction_required_count=12`.
- `.\scripts\francis-completion-model.ps1` returned clean JSON with
  `stage17_artifact_reconstruction_evidence` for
  `stage17_artifact_reconstruction_batch_1782062370_b0f0ddd6_receipt`.

Validations failed or blocked:

- Full local `.\scripts\check.ps1` was not run.
- Full GitHub CI was not accepted for this intermediate commit series because
  rapid pushes can cancel earlier runs; CI remains a final stabilization gate.

Receipts generated:

- `data\artifacts\plugins\capability_packs\artifact_reconstructions\stage17_artifact_reconstruction_batch_1782062370_b0f0ddd6_receipt.json`.
- Receipt SHA-256:
  `12162F7AB67689F324145AC86EEA92C6E67B247DCD57D792FCD330DCD9BFF2E0`.

Roadmap items advanced:

- Stage 17 / Capability Economy.
- Governed quality-evidence artifact reconstruction.
- Completion-model receipt readback continuity.

Capability classes advanced:

- Capability Registry
- Governance
- Receipts
- Observability
- Completion Model
- Documentation

New capabilities created or strengthened:

- The live Stage 17 quality-evidence queue has another receipt-backed
  reduction: `13 -> 12`.
- The repeated reconstruction loop continued without new route changes.

Most important change:

- Stage 17 artifact reconstruction-required packs dropped to 12 remaining.

Biggest remaining bottleneck:

- Stage 17 still has 12 artifact reconstruction-required packs and unresolved
  metadata, proposal-review, promotion, enablement/execution, and full-CI gates.

Next highest leverage action:

- Continue bounded `smallest_full_pack_first` applies while clean candidates
  remain, or shift to the next non-reconstruction Stage 17 gate once the queue
  stops producing safe full-pack candidates.

### Cycle 2026-06-21T17:20Z to 2026-06-21T17:24Z

Scope: bounded three-apply Stage 17 live artifact reconstruction batch through
the governed route.

Active workers:

- Lead-only live mutation. No worker packets were accepted in this batch cycle.

Active drones:

- 0 local drones were accepted in this cycle.

Commits produced: pending at report time.

Commits accepted: pending at report time.

Commits rejected: 0.

Validations passed:

- Batch iteration 1 dry-run/apply selected
  `legacy.generated.capabilityqualitytestsplugin`, reconstructed 4
  capabilities, and moved the queue `12 -> 11`.
- Batch iteration 2 dry-run/apply selected
  `legacy.generated.capabilityvalidationreceiptsplugin`, reconstructed 4
  capabilities, and moved the queue `11 -> 10`.
- Batch iteration 3 dry-run/apply selected `legacy.generated.catalogplugin`,
  reconstructed 4 capabilities, and moved the queue `10 -> 9`.
- Every iteration returned `ok=true`, `applied=true`, `status=recorded`,
  `recorded_pack_count=1`, `recorded_capability_count=4`,
  `failed_count=0`, `skipped_count=0`, and `candidate_reduction_count=1`.
- Live remediation readback returned `remediation_queue_count=9` and
  `artifact_reconstruction_required_count=9`.
- `.\scripts\francis-completion-model.ps1` returned clean JSON with the newest
  receipt `stage17_artifact_reconstruction_batch_1782062632_90b171fc_receipt`.

Validations failed or blocked:

- Full local `.\scripts\check.ps1` was not run.
- Full GitHub CI was not accepted for this intermediate commit series because
  rapid pushes can cancel earlier runs; CI remains a final stabilization gate.

Receipts generated:

- `stage17_artifact_reconstruction_batch_1782062524_0fd77876_receipt`;
  SHA-256 `14B16D804CFF0A0BE2A7562CD60EBFAE1CDB917F5DEC7AED5902A1826829D0BE`.
- `stage17_artifact_reconstruction_batch_1782062577_603ec279_receipt`;
  SHA-256 `95D956BC4A04CC470CB9D6203E306B8B2DE9E6A6E4B95A408F64886AE83631D5`.
- `stage17_artifact_reconstruction_batch_1782062632_90b171fc_receipt`;
  SHA-256 `94B199381DF36EF4981EC20AAFBAF9EEF372FE324F9AB0C5BAF0AF99CC0AEB57`.

Roadmap items advanced:

- Stage 17 / Capability Economy.
- Governed quality-evidence artifact reconstruction.
- Completion-model receipt readback continuity.

Capability classes advanced:

- Capability Registry
- Governance
- Receipts
- Observability
- Completion Model
- Documentation

New capabilities created or strengthened:

- The live Stage 17 quality-evidence queue has a bounded batch reduction:
  `12 -> 9`.
- The route completed three sequential governed applies without receipt
  collision, failed records, skipped records, or authority broadening.

Most important change:

- Stage 17 artifact reconstruction-required packs dropped below 10 for the
  first time in this run.

Biggest remaining bottleneck:

- Stage 17 still has 9 artifact reconstruction-required packs and unresolved
  metadata, proposal-review, promotion, enablement/execution, and full-CI gates.

Next highest leverage action:

- Continue bounded `smallest_full_pack_first` applies while clean candidates
  remain, then switch to the next non-reconstruction Stage 17 gate once the
  queue is exhausted or stops producing safe full-pack candidates.
