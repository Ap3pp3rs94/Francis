# Francis Worker 4 - Stage 17 And Completion Model

You are Worker 4 in a four-terminal Francis build run.

Primary lane: Stage 17 capability-economy gaps and completion-model truth.

Read first:

1. `AGENTS.md`
2. `docs/operations/COMPLETION_LEDGER.md`
3. `docs/operations/ORB_CONTINUUM_STATE.md`
4. `docs/operations/COMPLETION_MODEL.md`
5. `docs/canonical/BUILD_MANIFEST.md`

Non-negotiable lock:

- Do not touch Orb visual files.
- Do not promote, enable, or execute capabilities unless an existing governed
  route explicitly supports the dry-run/apply boundary and the scoped tests
  prove it.
- Keep readback/apply boundaries explicit.

Current repo truth to preserve:

- Stage 17 remains open.
- The completion model is read-only and exists to prevent build-loop drift.
- Current build phase is Phase 2. Do not move overall or phase percentages
  without a ledger-backed gate closure.

Bounded task:

Pick the smallest Stage 17 or completion-model gap that can be advanced with
evidence. Good slices include readback clarity, operator proposal evidence refs,
bounded queue reduction, missing tests, or completion-model protection against
loop drift.

Allowed primary files:

- `src/francis/api/routes/plugins.py`
- `tests/test_api_plugins.py`
- `tests/test_api_managed_copies.py`
- `src/francis/completion_model.py`
- `src/francis/api/routes/completion_model.py`
- `scripts/francis-completion-model.ps1`
- `tests/test_completion_model.py`
- `tests/test_francis_completion_model_script.py`
- `docs/operations/COMPLETION_MODEL.md`
- `docs/operations/COMPLETION_LEDGER.md`

Acceptance criteria:

- A bounded Stage 17/completion readback gap is improved.
- Existing governance boundaries remain intact.
- No broad refactor or unrelated formatting.
- Focused tests pass.
- Any ledger update names exact validation and remaining blockers.

Do not:

- Restart Continuum.
- Touch Orb visuals.
- Commit or push.
- Claim Stage 17 closure unless every closure criterion is proven.

Final response format:

STATUS
FILES CHANGED
WHAT CHANGED
WHY
VALIDATION
RISKS / FOLLOW-UPS

Also include completion percentages only as evidence claims. Overall Francis and
current build-phase percentages do not move unless a ledger-backed gate actually
closed.
