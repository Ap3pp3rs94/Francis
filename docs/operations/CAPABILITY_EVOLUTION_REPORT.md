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
| Governance | 8 | Refusal/no-authority boundaries strengthened for acoustic proof, provider receipts, Stage 17 worker-readback/publication handoff claims, invalid coordinates, activity-vs-progress reporting, and worker liveness truth. |
| Receipts | 8 | New receipt/readback fields for acoustic proof rejection, provider mode state/linkage, worker-readback and worker/publication handoff requirements, capability-evolution worker packets, and worker execution liveness. |
| Missions | 0 | No mission-routing advancement in this cycle. |
| Overlay | 4 | Overlay-related proof now requires local overlay speech source, exposes manual proof mode, and blocked/invalid coordinate cases stay before screen/session readback. |
| Observability | 9 | Added diagnostics for acoustic proof, provider mode/linkage disambiguation, Stage 17 readback and handoff guard state, build capability evolution, and Exec worker liveness. |
| Completion Model | 2 | Completion model now rejects selected Stage 17 gaps as worker-readback proof and worker/publication handoff proof. |
| Capability Registry | 0 | No capability registry advancement in this cycle. |
| Swarm Infrastructure | 4 | Completion model now requires worker readback/handoff evidence, coordinator prompts require capability-evolution packet fields, and active Exec workers are no longer treated as stale. |
| Operator Controls | 2 | Manual acoustic Orb movement proof now has source-specific next-step diagnostics and explicit manual-proof-required state. |
| API Surface | 3 | Monitor route sanitizer and ChatGPT voice contract/receipt surfaces expose stricter readback fields. |
| Documentation | 4 | Completion model docs, worker prompt docs, and this evolution report record durable operating rules. |
| Testing | 10 | Added or expanded focused tests across worker lanes, coordinator prompt contracts, and worker liveness status. |

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
