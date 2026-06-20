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
| Presence | 1 | Orb voice proof diagnostics now distinguish local acoustic proof from bridge-file receipts. |
| Lens | 2 | Lens observation contracts gained unmapped-coordinate refusal coverage and command-palette proof readbacks. |
| Voice | 2 | Voice receipts now separate acoustic proof source and ChatGPT provider receipt modes. |
| Memory | 0 | No memory contract advancement in this cycle. |
| Governance | 3 | Refusal/no-authority boundaries strengthened for acoustic proof, provider receipts, and Stage 17 worker-readback claims. |
| Receipts | 3 | New receipt/readback fields for acoustic proof rejection, provider mode state, and worker-readback evidence requirements. |
| Missions | 0 | No mission-routing advancement in this cycle. |
| Overlay | 2 | Overlay-related proof now requires local overlay speech source and blocked coordinate cases stay before screen/session readback. |
| Observability | 3 | Added diagnostics for acoustic proof, provider mode disambiguation, and Stage 17 worker-readback guard state. |
| Completion Model | 1 | Completion model now rejects selected Stage 17 gaps as worker-readback proof. |
| Capability Registry | 0 | No capability registry advancement in this cycle. |
| Swarm Infrastructure | 1 | Completion model now requires worker readback evidence before worker-packet claims. |
| Operator Controls | 1 | Manual acoustic Orb movement proof now has source-specific next-step diagnostics. |
| API Surface | 2 | Monitor route sanitizer and ChatGPT voice contract expose stricter readback fields. |
| Documentation | 2 | Completion model docs and this evolution report record durable operating rules. |
| Testing | 4 | Added or expanded focused tests across all four worker lanes. |

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
