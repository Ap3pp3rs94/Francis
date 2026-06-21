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

As of the 2026-06-21 Stage 17 quality-standard receipt and invocation audit
pass, Stage 17
remains open. The completion-model readback is expected to select the latest
open Stage 17 ledger entry, report `current_phase=Phase 2`, preserve
`read_only_contract=true`, and report `writes_repo=false`, `writes_data=false`,
`grants_execution_authority=false`, and `grants_mutation_authority=false`.

Recent Stage 17 evidence now proves multiple metadata-receipt backlog
reductions, receipt-linked mission-shape invocation proofs, unsupported
operation receipt rejection visibility, receipt-bound lifecycle rollback,
lifecycle repair compatibility guards, quality-standard dry-run/apply
confirmation, dedicated quality-standard remediation batch receipts, and
generated-sync-aware quality-standard after-counts. The current live
quality-standard tests/docs queue readback reached zero after three governed
applies, including a lead-level post-validation cleanup after the focused test
run generated one more legacy candidate. Stage 17 still does not prove
validation-receipt closure, proposal
lineage closure, migration-candidate closure, promotion, enablement, execution,
full CI, or phase movement.

## Closure Criteria

| Criterion | Required evidence to close | Current evidence | Status |
| --- | --- | --- | --- |
| 1. Stage 17 source posture | Completion ledger and build manifest identify Stage 17 as closed, with the completion model reporting the same posture. | Completion model reports `stage17_status.status=open` from the latest Stage 17 ledger entry. | Open |
| 2. Governed route boundary | All Stage 17 apply behavior uses existing governed routes with dry-run confirmation, bounded scope, and focused validation. | Metadata batch apply, quality-standard remediation apply, lifecycle rollback/repair, proposal evidence/review routes, and invocation audits preserve governance and focused validation for their bounded scopes. Quality-standard remediation now writes a dedicated batch receipt and stays dry-run-fingerprint gated. | Partial |
| 3. Queue-count and projection timing | Closure claim has route/apply evidence with projection scope, global-count inclusion, before/after counts, generated-at or receipt timestamp, and focused validation for the intended scope. | Current quality-standard tests/docs queue evidence is stronger: full-library readback moved from 18 to 0 after generated-sync-aware follow-up applies, including a lead-level post-validation `1 -> 0` cleanup. Closure still lacks validation/proposal queue closure and full projection timing for every remaining Stage 17 class. | Partial |
| 4. Proposal evidence, review, validation refs, and catalog maintainability | Proposal artifact refs, proposal-review receipt refs, validation or quality-evidence refs, bounded plugin id scope, catalog lifecycle provenance, and focused validation are verified for the closure scope. | Catalog projects lifecycle receipt provenance and prior status fields; quality-standard candidate reference backfill is receipt-backed; remaining blocked packs still report `validation_receipt_missing=18` and `proposal_id_missing=18`. | Weakest |
| 5. Publication and worker handoff | Matching worker lane readback plus PM-owned publication marker references the same prompt hash and represents GitHub push, explicit no-change receipt, or blocked-with-evidence receipt. | Current W1/W2/W3 packets have lane readbacks. They require PM-owned publication markers and a pushed integration commit before this row can count this cycle. | Partial |
| 6. CI and wiring trust | Full project validation passes or any substitute gates are named, and route mounts/wiring diagram match current repo truth. | Full `scripts/check.ps1` remains red from Lens runtime/proof-script failures identified in the W4 lane; route/wiring audit evidence remains useful but not a green full-CI gate. | In progress |

## Weakest Criterion

The weakest Stage 17 closure criterion is now criterion 4: validation/proposal
evidence closure. The current quality-standard tests/docs queue is receipt
backed at zero, but 18 packs still lack validation receipts and proposal ids,
and one generated legacy pack still appears in the migration-plan operator
review path. A closure claim still needs fresh, scope-explicit, receipt-backed
queue evidence across those remaining classes with focused validation.

The weakest Worker 4 audit blocker was criterion 6: durable wiring evidence was
incomplete because the route-family inventory did not list every mounted route
family and this matrix did not exist. This pass addresses that audit blocker
without claiming Stage 17 closure.

## Next Evidence Needed

The next highest-value Stage 17 action is to reduce
`migration_candidate_total=1` for `legacy.generated.stage17reusableinvocationplugin`
through the existing metadata receipt/operator-review path, then advance
validation receipt and proposal-lineage remediation for the 18 still-blocked
packs. Global closure claims should wait until route output proves fresh
full-scope counts across those remaining classes.

The next highest-value Worker 4 action is to rerun `scripts/check.ps1` after
active worker-lane edits settle, then preserve the exact pass/fail signature in
the lane readback and Lead Builder packet.
