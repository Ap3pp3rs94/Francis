# Francis Worker 2 - Lens Overlay Spatial Contract

You are Worker 2 in a four-terminal Francis build run.

Primary lane: lens-to-overlay desktop-space contract.

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
- Do not create a second overlay or separate lens app.
- The overlay is the desktop-space host; the lens is the substrate-backed
  observation interface through that overlay.

Current repo truth to preserve:

- The lens/overlay observation contract is currently metadata-only.
- It does not yet claim screenshots, pixels, OCR, accessibility tree, or visual
  similarity evidence.
- The current blocker is that the lens/overlay path needs stronger coordinate,
  region, evidence, and limitation contracts without claiming unsupported
  perception.

Bounded task:

Strengthen the smallest truthful lens/overlay spatial contract or test coverage
available now. Good slices include coordinate transform readback, mapped versus
captured region fields, limitation fields, failure reasons, or replayable
receipt shape. Do not add fake perception.

Allowed primary files:

- `src/francis/lens/**`
- `src/francis/api/routes/**` only where existing lens routes live
- `tests/unit/test_lens_*.py`
- `tests/test_api_lens*.py`
- `docs/operations/ORB_CONTINUUM_STATE.md`
- `docs/operations/COMPLETION_LEDGER.md`

Avoid `scripts/lens-overlay-window.ps1` unless absolutely required. If you must
touch it, do not change visuals.

Acceptance criteria:

- Lens and overlay remain one coherent path.
- Observations distinguish requested region, mapped overlay region, actual
  observed/captured region, source, status, confidence, limitations, and
  unknowns where applicable.
- Unsupported perception remains explicitly unsupported.
- Coordinate/boundary behavior has focused tests.

Do not:

- Claim Francis can see desktop pixels unless evidence exists.
- Add a standalone lens app.
- Restart Continuum.
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
