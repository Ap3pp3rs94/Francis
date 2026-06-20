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

As of the 2026-06-20 Stage 17 catalog lifecycle provenance pass, Stage 17
remains open. The completion-model readback is expected to select the latest
open Stage 17 ledger entry, report `current_phase=Phase 2`, preserve
`read_only_contract=true`, and report `writes_repo=false`, `writes_data=false`,
`grants_execution_authority=false`, and `grants_mutation_authority=false`.

Recent Stage 17 evidence now proves multiple selected metadata-receipt backlog
reductions, receipt-linked mission-shape invocation proofs, receipt-bound
lifecycle rollback, and catalog readback of lifecycle receipt provenance. It
does not prove full-library queue closure, migration apply closure, fresh global
projection timing, publication for every active worker packet, promotion,
enablement, execution, or phase movement.

## Closure Criteria

| Criterion | Required evidence to close | Current evidence | Status |
| --- | --- | --- | --- |
| 1. Stage 17 source posture | Completion ledger and build manifest identify Stage 17 as closed, with the completion model reporting the same posture. | Completion model reports `stage17_status.status=open` from the latest Stage 17 ledger entry. | Open |
| 2. Governed route boundary | All Stage 17 apply behavior uses existing governed routes with dry-run confirmation, bounded scope, and focused validation. | Metadata batch apply, lifecycle rollback repair, proposal evidence/review routes, and invocation audits preserve governance and focused validation for their bounded scopes. | Partial |
| 3. Queue-count and projection timing | Closure claim has route/apply evidence with projection scope, global-count inclusion, before/after counts, generated-at or receipt timestamp, and focused validation for the intended scope. | Recent metadata batches prove selected-scope candidate reductions; full-library projection timing and global queue closure remain unproven. | Weakest |
| 4. Proposal evidence, review, validation refs, and catalog maintainability | Proposal artifact refs, proposal-review receipt refs, validation or quality-evidence refs, bounded plugin id scope, catalog lifecycle provenance, and focused validation are verified for the closure scope. | Catalog now projects lifecycle receipt provenance and prior status fields; proposal/review evidence is still proven only for bounded selected scopes. | Partial |
| 5. Publication and worker handoff | Matching worker lane readback plus PM-owned publication marker references the same prompt hash and represents GitHub push, explicit no-change receipt, or blocked-with-evidence receipt. | Prior accepted packets have publication markers. New active worker lanes still require fresh packets and PM-owned publication before integration. | Partial |
| 6. CI and wiring trust | Full project validation passes or any substitute gates are named, and route mounts/wiring diagram match current repo truth. | Full `scripts/check.ps1` remains red from Lens runtime/proof-script failures identified in the W4 lane; route/wiring audit evidence remains useful but not a green full-CI gate. | In progress |

## Weakest Criterion

The weakest Stage 17 closure criterion is criterion 3: full-library queue-count
and projection-timing evidence. Current validated evidence is still
selected-scope only. A closure claim still needs fresh, scope-explicit,
receipt-backed global or deliberately bounded queue evidence with focused
validation.

The weakest Worker 4 audit blocker was criterion 6: durable wiring evidence was
incomplete because the route-family inventory did not list every mounted route
family and this matrix did not exist. This pass addresses that audit blocker
without claiming Stage 17 closure.

## Next Evidence Needed

The next highest-value Stage 17 action is to continue bounded selected-batch
backlog reductions through existing governed routes while implementing the next
executable lifecycle/migration apply blocker. Global projection claims should
wait until route output proves fresh full-scope counts.

The next highest-value Worker 4 action is to rerun `scripts/check.ps1` after
active worker-lane edits settle, then preserve the exact pass/fail signature in
the lane readback and Lead Builder packet.
