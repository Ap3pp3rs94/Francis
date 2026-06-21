# Stage 17 Closure Matrix

This matrix is a current-state closure audit for Stage 17 / Capability Economy.
It is not a closure claim, publication marker, queue receipt, or roadmap
replacement.

Sources inspected for this matrix:

- `docs/operations/COMPLETION_LEDGER.md`
- `docs/operations/COMPLETION_MODEL.md`
- `docs/canonical/BUILD_MANIFEST.md`
- `docs/operations/CURRENT_BUILD_WIRING_DIAGRAM.md`
- `src/francis/economy/markets/capability_catalog_projection.py`
- `src/francis/api/app.py`
- `src/francis/completion_model.py`
- `scripts/francis-completion-model.ps1`
- `scripts/francis-worker-coordinator.ps1`
- `scripts/start-francis-worker-terminals.ps1`

## Current Readback

As of the 2026-06-21 19:34Z Stage 17 execution-readiness checkpoint,
Stage 17 / Capability Economy remains open. The current ledger records
proposal evidence, proposal review, explicit promotion, promotion receipts, and
the current promoted-only operator surface as closed for the 2,438
evidence-backed capability records. The promoted library now has a read-only
execution-readiness surface, and invocation-audit reuse proof is hardened so
only post-promotion invocation receipts can count.

This is not closure. The current open gates are the governed dry-run execution
probe through existing `/plugins/run` or `/plugins/tools/run`, invocation-audit
verification of that probe, full local `.\scripts\check.ps1`, GitHub CI, and
final Stage 17 closure reconciliation. A local triage pass on 2026-06-21 found
the available pytest cache unsuitable for identifying current full-check
failures (`lastfailed={}`), found no active Lens command-palette or pytest
subprocess, and verified the command-palette monitor target with
`.\.venv\Scripts\python.exe -m pytest tests\test_lens_command_palette_monitor_script.py -q --tb=short --maxfail=1`.
That focused target passed, so it is not the immediate current first-fail
evidence for the full gate.

## Closure Criteria

| Criterion | Required evidence to close | Current evidence | Status |
| --- | --- | --- | --- |
| 1. Stage 17 source posture | Completion ledger and build manifest identify Stage 17 as closed, with the completion model reporting the same posture. | Completion model reports `stage17_status.status=open` from the latest Stage 17 ledger entry. | Open |
| 2. Governed route boundary | All Stage 17 apply behavior uses existing governed routes with dry-run confirmation, bounded scope, and focused validation. | Metadata, quality-standard, artifact reconstruction, operator review, proposal evidence, proposal review, and explicit promotion routes are recorded as governed and receipt-backed for their bounded scopes. The execution-readiness route is read-only and grants no apply authority. | Partial |
| 3. Queue-count and projection timing | Closure claim has route/apply evidence with projection scope, global-count inclusion, before/after counts, generated-at or receipt timestamp, and focused validation for the intended scope. | The latest ledger records artifact reconstruction at zero, proposal evidence/review complete for 2,438 evidence-backed records, promoted capability count 2,438, promotion receipt ids 2,438, and promoted enabled count 2,438. A closure claim still needs a fresh execution/reuse probe and final reconciliation. | Partial |
| 4. Proposal evidence, review, validation refs, and catalog maintainability | Proposal artifact refs, proposal-review receipt refs, validation or quality-evidence refs, bounded plugin id scope, catalog lifecycle provenance, and focused validation are verified for the closure scope. | The current surface records proposal evidence, approved proposal reviews, explicit promotion, and promotion receipts for the 2,438 evidence-backed capability records. This row is no longer the weakest current blocker, but it still needs final closure reconciliation and CI-backed confirmation. | Partial |
| 5. Publication and worker handoff | Matching worker lane readback plus PM-owned publication marker references the same prompt hash and represents GitHub push, explicit no-change receipt, or blocked-with-evidence receipt. | Latest accepted worker packets and ledger entries exist, but Lead still owns integration, no commit/push is claimed by this matrix update, and full local/GitHub validation remains unresolved. | Partial |
| 6. CI and wiring trust | Full project validation passes or any substitute gates are named, and route mounts/wiring diagram match current repo truth. | Full `scripts/check.ps1` remains red/unproven. Prior W4 evidence identified 16 Lens runtime/proof-script failures; latest ledger says a later full-check attempt emitted multiple failure markers and was stopped while a Lens command-palette proof subprocess was active. The scoped command-palette monitor pytest passed in this triage pass, so the remaining full-check risk still points to the broader Lens runtime/proof-script cluster until a fresh full gate proves otherwise. | Weakest |

## Weakest Criterion

The weakest current Stage 17 closure criterion is criterion 6: CI and wiring
trust. The current repo has strong receipt-backed progress through proposal,
review, and promotion, but full local validation is still red/unproven and the
remaining failure evidence sits in Lens runtime/proof-script territory rather
than in a green Stage 17 checkpoint.

Criterion 4 remains partial until final closure reconciliation proves the same
proposal/review/promotion facts against the current repo state and validation
set, but it is no longer the next blocker named by the latest ledger.

## Next Evidence Needed

The next highest-value Stage 17 action is a governed dry-run execution probe
through an existing dispatch route:

1. Select one promoted, routeable, no-approval capability from the
   execution-readiness readback.
2. Run it through existing `/plugins/run` or `/plugins/tools/run` dry-run
   dispatch without bypassing policy, routing, receipts, or mission readbacks.
3. Verify the resulting post-promotion invocation receipt through
   `/plugins/capabilities/library/invocations/audit`.
4. Preserve exact output, dry-run status, receipt id, and any blocker before
   attempting full local check again.

For CI triage, do not rerun the entire suite repeatedly. The cheapest useful
next check is targeted pytest for the known Lens runtime/proof-script cluster
from the W4 failure list, then one full `.\scripts\check.ps1` only after that
cluster is green or explicitly classified.
