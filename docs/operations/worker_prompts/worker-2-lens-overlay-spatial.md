# Francis Worker 2 - Stage 17 Lifecycle And Promotion

You are Worker 2 in a four-terminal Francis build run.

Primary lane: implement executable Stage 17 lifecycle behavior: versioning, migration, compatibility, promotion/apply, quarantine, deprecation, and repair.

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
5. Existing Stage 17 API/governance/tests around plugin readback/apply, managed copies, proposal evidence, and completion-model claims.

Current repo truth to preserve:

- Readback routes must remain authority-denying.
- Apply/promotion routes must stay tightly governance-bounded and auditable.
- Artifact existence alone is not approval.
- Compatibility, migration, quarantine, and deprecation must be executable behavior, not only documentation.

Bounded task:

Advance one lifecycle blocker with code plus focused validation. Prefer the smallest executable behavior that makes packs safer to promote or maintain, such as compatibility refusal, migration dry-run evidence, quarantine/deprecation receipt fields, rollback/repair metadata, or policy-aware apply guards.

Acceptance criteria:

- Names the exact lifecycle behavior made executable.
- Preserves or strengthens governance and authority boundaries.
- Adds receipt/readback evidence for before/after state where applicable.
- Adds focused tests for allowed, denied, and ambiguous cases.
- Does not claim Stage 17 closure.

Allowed primary files:

- `src/francis/api/routes/plugins.py`
- `src/francis/capabilities/**`
- `src/francis/governance/**`
- `tests/test_api_plugins.py`
- `tests/test_api_managed_copies.py`
- `docs/operations/COMPLETION_LEDGER.md`
- `docs/operations/COMPLETION_MODEL.md`

Do not:

- Do not touch Orb visual files.
- Restart Continuum.
- Create ungoverned apply or promotion paths.
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
