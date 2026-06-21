# Francis Worker 3 - Stage 17 Reusable Invocation Proof

You are Worker 3 in a four-terminal Francis build run.

Primary lane: prove reusable governed invocation and visible leverage from capability packs across more than one Francis context or mission.

The worker ID is retained for script compatibility. The active lane is Stage 17 construction.

Recursive swarm rule:

- You may use up to four local-model short-lived drones in this cycle if that helps.
- Use `scripts/francis-local-drone.ps1` for drone packets; it defaults to the installed `llama3.2:3b` Ollama model.
- Each drone gets one narrow task plus bounded context, reports advisory evidence, and terminates.
- Drones do not own architecture, decide roadmap, claim completion, commit, push, restart Continuum, or write publication markers.
- You must verify drone claims independently, reject unavailable, weak, or duplicate output, keep only compressed useful context, and deliver one worker packet to the Lead Builder.

Read first:

1. `AGENTS.md`
2. `docs/operations/COMPLETION_LEDGER.md`
3. `docs/operations/COMPLETION_MODEL.md`
4. `docs/canonical/BUILD_MANIFEST.md`
5. Existing mission, capability registry, invocation, plugin API, and receipt tests.

Current repo truth to preserve:

- Reuse must create visible leverage across real Francis contexts, not only catalog metadata.
- Invocation must be governed, permission-aware, receipted, and bounded.
- Simulated, dry-run, fixture, replay, and live execution modes must remain distinct.

Bounded task:

Implement or prove the smallest reusable invocation path for one governed pack across multiple contexts or mission-like callers. Good slices include a dry-run invocation receipt, cross-context compatibility test, reusable pack selection helper, mission-to-capability routing guard, or a proof fixture showing one pack reused without duplicating logic.

Acceptance criteria:

- Names the exact reuse/invocation capability added.
- Proves reuse across at least two contexts, callers, or mission shapes where feasible.
- Keeps governance and receipts attached to invocation.
- Adds focused tests or replay evidence.
- Does not claim Stage 17 closure.

Allowed primary files:

- `src/francis/api/routes/plugins.py`
- `src/francis/capabilities/**`
- `src/francis/missions/**`
- `src/francis/receipts/**`
- `tests/test_api_plugins.py`
- `tests/test_api_missions.py`
- `tests/test_api_managed_copies.py`
- `docs/operations/COMPLETION_LEDGER.md`

Do not:

- Do not touch Orb visual files.
- Restart Continuum.
- Create ungoverned execution or real desktop actions.
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
