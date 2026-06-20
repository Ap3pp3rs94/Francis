# Francis Worker 4 - Stage 17 Catalog Coherence And Closure Audit

You are Worker 4 in a four-terminal Francis build run.

Primary lane: implement catalog coherence and integration, audit Stage 17 closure evidence, then directly fix the highest-leverage blocker found.

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
5. Stage 17 catalog, plugin API, completion model, and tests.

Stage 17 closure criteria:

1. Packs are reusable operational assets.
2. Governance, permissions, risks, receipts, and validation travel with each pack.
3. Versioning, migration, testing, promotion, quarantine, deprecation, and documentation are executable lifecycle behavior.
4. The catalog is discoverable, deduplicated, curated, and maintainable.
5. Operators can inspect, evaluate, promote, invoke, and maintain packs through governed paths.
6. Reuse creates visible leverage across multiple real contexts.

Bounded task:

Build a closure matrix from current repo evidence, identify the weakest criterion, and remove one real blocker. Prefer executable catalog coherence work over report-only changes: deduplication behavior, curated readback fields, stale/duplicate refusal, closure-matrix test coverage, integration evidence references, or catalog health receipts.

Acceptance criteria:

- Names the weakest criterion and evidence gap before editing.
- Implements one code/test/doc change that makes the criterion more true.
- Records before/after blocker evidence.
- Keeps completion claims conservative.
- Does not claim Stage 17 closure unless all six criteria are proven by current evidence.

Allowed primary files:

- `src/francis/api/routes/plugins.py`
- `src/francis/completion_model.py`
- `scripts/francis-completion-model.ps1`
- `tests/test_api_plugins.py`
- `tests/test_completion_model.py`
- `tests/test_francis_completion_model_script.py`
- `docs/operations/COMPLETION_MODEL.md`
- `docs/operations/COMPLETION_LEDGER.md`
- `docs/operations/STAGE17_CLOSURE_MATRIX.md` if a durable matrix is needed

Do not:

- Do not touch Orb visual files.
- Restart Continuum.
- Let broad CI cleanup replace Stage 17 construction.
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
