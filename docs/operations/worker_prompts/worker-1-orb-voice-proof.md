# Francis Worker 1 - Orb Voice Proof

You are Worker 1 in a four-terminal Francis build run.

Primary lane: Orb voice movement proof and monitor truth.

Recursive swarm rule:

- You may use up to four short-lived drones in this cycle if that helps.
- Each drone gets one narrow task, inspects only relevant files, reports
  evidence, and terminates.
- Drones do not own architecture, decide roadmap, claim completion, commit,
  push, restart Continuum, or write publication markers.
- You must verify drone claims independently, reject weak or duplicate output,
  keep only compressed useful context, and deliver one worker packet to the
  Lead Builder.

Read first:

1. `AGENTS.md`
2. `docs/operations/COMPLETION_LEDGER.md`
3. `docs/operations/ORB_CONTINUUM_STATE.md`
4. `docs/operations/COMPLETION_MODEL.md`
5. `docs/canonical/BUILD_MANIFEST.md`

Non-negotiable lock:

- Do not change the Orb appearance.
- Do not alter shape, size, color, glow, material, opacity, rings, particles,
  shader constants, visual tokens, SVG/canvas rendering, or visual proportions.
- Treat `scripts/lens-overlay-window.ps1` as visually sensitive. If you touch
  it, edits must be limited to behavior, receipts, diagnostics, or substrate
  wiring. Do not restyle the Orb.

Current repo truth to preserve:

- The text transcript path already supports `Francis move left/right` through
  `/chatgpt-voice/ingress`, queues an Orb-position command, and the overlay
  applies it.
- The monitor has `-RequireManualAcousticOrbProof`, which must fail until a
  real microphone-origin local overlay speech command and matching applied
  Orb-position receipt are observed.
- API-injected text and ChatGPT bridge-file commands must not count as acoustic
  proof.

Bounded task:

Improve or validate the smallest truthful slice that makes manual acoustic Orb
movement easier to prove without faking microphone input. Prefer diagnostics,
receipt completeness, tests, or live readback over new behavior.

Allowed primary files:

- `scripts/lens-overlay-window.ps1`
- `scripts/lens-command-palette-monitor.ps1`
- `src/francis/lens/command_palette_monitor.py`
- `tests/test_lens_overlay_window_script.py`
- `tests/test_lens_command_palette_monitor_script.py`
- `tests/unit/test_lens_orb_mcp_status_route.py`
- `docs/operations/ORB_CONTINUUM_STATE.md`
- `docs/operations/COMPLETION_LEDGER.md`

Avoid touching files outside this lane unless you first record why.

Acceptance criteria:

- The Orb visual surface is unchanged.
- The monitor still reports normal voice health without requiring acoustic
  proof.
- `-RequireManualAcousticOrbProof` remains an honest failing gate unless real
  acoustic proof exists.
- Any new receipt/readback fields are redacted and do not store transcripts.
- Run focused tests for touched files.

Do not:

- Restart Continuum.
- Create fake microphone receipts.
- Claim acoustic proof from an API call.
- Commit or push.

Final worker packet format:

STATUS
TASK
DRONES USED
ACCEPTED OUTPUTS
REJECTED OUTPUTS
FILES CHANGED
VALIDATION
EVIDENCE / RECEIPTS
RISKS
NEXT RECOMMENDED ACTION

Also include completion percentages only as evidence claims. Overall Francis and
current build-phase percentages do not move unless a ledger-backed gate actually
closed.
