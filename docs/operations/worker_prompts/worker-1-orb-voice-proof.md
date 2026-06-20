# Francis Worker 1 - Stage 17 Backlog Class Reduction

You are Worker 1 in a four-terminal Francis build run.

Primary lane: eliminate live Stage 17 backlog classes with bounded pack/batch mechanisms.

The worker ID is retained for script compatibility. The active lane is Stage 17 construction.

Recursive swarm rule:

- You may use up to four short-lived drones in this cycle if that helps.
- Each drone gets one narrow task, inspects only relevant files, reports evidence, and terminates.
- Drones do not own architecture, decide roadmap, claim completion, commit, push, restart Continuum, or write publication markers.
- You must verify drone claims independently, reject weak or duplicate output, keep only compressed useful context, and deliver one worker packet to the Lead Builder.

Read first:

1. `AGENTS.md`
2. `docs/operations/COMPLETION_LEDGER.md`
3. `docs/operations/COMPLETION_MODEL.md`
4. `docs/canonical/BUILD_MANIFEST.md`
5. Stage 17 implementation and tests under `src/francis/api/routes/plugins.py`, `src/francis/capabilities`, `tests/test_api_plugins.py`, and nearby capability catalog tests.

Current repo truth to preserve:

- Stage 17 remains open until repo evidence proves reusable operational capability packs, governed lifecycle behavior, discoverability, promotion/invocation paths, and visible reuse leverage.
- Prompt volume, readback volume, broad reporting, and projections do not close Stage 17.
- Any queue or backlog reduction must be bounded, deterministic, receipted, and validated.

Bounded task:

Find the smallest live Stage 17 backlog class that can be reduced by a reusable mechanism rather than another one-off metadata patch. Good slices include bounded batch intake, duplicate grouping, queue item promotion to structured evidence, deterministic pack normalization, or a test-backed helper that removes a repeated blocker class.

Acceptance criteria:

- Names the exact Stage 17 criterion advanced.
- Removes or measurably reduces one real blocker class with before/after evidence.
- Keeps governance, receipts, permissions, risks, and validation attached to each affected pack or batch.
- Adds focused tests for the mechanism or proves an existing test covers it.
- Does not claim Stage 17 closure.

Allowed primary files:

- `src/francis/api/routes/plugins.py`
- `src/francis/capabilities/**`
- `tests/test_api_plugins.py`
- `tests/test_api_managed_copies.py`
- `docs/operations/COMPLETION_LEDGER.md`
- `docs/operations/COMPLETION_MODEL.md`
- narrowly scoped Stage 17 scripts or fixtures already present in the repo

Do not:

- Do not touch Orb visual files.
- Restart Continuum.
- Run broad CI unless it directly validates your Stage 17 mechanism.
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
CAPABILITY EVOLUTION
RISKS
NEXT RECOMMENDED ACTION

Also state the Stage 17 criterion advanced, blocker removed, before/after evidence, and proposed Git commit scope.
