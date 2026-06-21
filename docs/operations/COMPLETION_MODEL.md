# Francis Completion Model

This model exists to stop build-loop drift. It is a status/readback contract for
deciding what a `continue` run may truthfully advance.

The executable readback is:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\francis-completion-model.ps1 -Mode Status
```

The API readback is:

```text
GET /completion-model/status
```

## Contract

The completion model reads:

- `docs/operations/COMPLETION_LEDGER.md`
- `docs/canonical/BUILD_MANIFEST.md`

It emits one JSON object with:

- the current canonical phase
- the plane readiness snapshot from the build manifest
- the latest ledger entry before the update-rule section
- the latest true Stage 17 ledger entry, even when a newer non-Stage-17 slice is
  the latest overall ledger entry
- the latest remaining truthful gap, when the ledger names one
- the loop guards that must pass before a `continue` run chooses work
- the selected next continue decision, preferring the latest open Stage 17
  remaining truthful gap over unrelated newer ledger entries
- the selected-gap contract, which states that choosing a gap is a read-only
  selection and grants no apply, proposal-review, promotion, mutation, or
  execution authority
- the queue-count evidence guard, which states that choosing a Stage 17 gap is
  not proof of queue movement, does not recompute global counts, and does not
  authorize queue-count claims without a route readback or apply response that
  carries projection scope, global-count inclusion, before/after counts, and
  focused validation
- the projection-timing evidence guard, which states that choosing a Stage 17
  gap is not proof that a global projection is fresh, complete, or generated
  after the current slice; projection-timing claims require route/apply output
  with a generated-at or receipt timestamp, projection scope, bounded plugin
  scope or full-library declaration, global-count inclusion, and focused
  validation
- the proposal-evidence reference guard, which states that choosing a Stage 17
  gap is not proof that proposal evidence, proposal reviews, validation
  receipts, or quality-evidence references have been verified
- the publication evidence guard, which states that choosing a Stage 17 gap is
  not proof of a GitHub push, publication marker, no-change receipt, or
  blocked-with-evidence receipt
- the worker-readback evidence guard, which states that choosing a Stage 17 gap
  is not proof of a worker lane readback, worker packet, files-touched record,
  validation record, blocker/risk summary, commit-scope proposal, or next-prompt
  recommendation
- the worker/publication handoff guard, which states that choosing a Stage 17
  gap is not proof that a worker lane readback and PM-owned publication marker
  have both been produced for the same prompt hash
- the worker execution/session-liveness guard, which states that choosing a
  Stage 17 gap is not proof that a worker process is alive, completed, blocked,
  or represented by a valid session readback
- the percentage movement rules

The model is read-only. The API route is backed by the Francis Python substrate,
not by shelling out to the PowerShell script. It does not write repo files,
write runtime data, grant authority, mutate state, or close milestones.

## Continue Rule

Before continuing implementation work, use the model to answer:

1. What is the latest validated ledger slice?
2. What remaining truthful gap is named there?
3. Which roadmap area does the slice support?
4. What is the smallest coherent change that can be validated now?
5. What evidence would be strong enough to update the ledger?
6. Can any percentage move without violating the evidence rules?

If those answers are not available, the next task is to restore completion
readback, not to continue feature work.

Stage 17 readback is separate from the latest overall ledger slice so Worker 4
and future capability-economy continuations do not lose the current Stage 17 gap
behind unrelated Orb, UI, or live-ops ledger entries. This projection is
read-only and does not promote, enable, execute, or close capabilities.

When Stage 17 is open and has a remaining truthful gap, `next_continue_decision`
selects that Stage 17 ledger entry as `selected_gap_source` instead of the
latest overall ledger entry. If Stage 17 is not open, the model falls back to the
latest ledger gap. If required source documents are missing, the decision is
blocked on restoring the completion-model sources.

`next_continue_decision.selected_gap_contract` is part of that readback. It
names the selection basis and repeats the authority boundary: the completion
model can select a bounded gap for the next worker prompt, but it cannot apply
proposal evidence, approve proposal reviews, promote or enable capabilities,
write repo/data state, or grant execution/mutation authority. Any future Stage
17 apply must still use an existing governed route with dry-run confirmation,
bounded scope, and focused validation.

The selected-gap contract is also not queue-count evidence. A selected Stage 17
gap can point a worker at the next bounded slice, but it does not prove queue
movement, recompute global queue counts, or authorize a completion claim. Queue
movement claims require a concrete route readback or apply response with
`projection_scope`, `global_counts_included`, before/after counts, and focused
validation.

The selected-gap contract is also not projection-timing evidence. A selected
Stage 17 gap can name a broad-readback or projection-hardening target, but it
does not prove when a projection was generated, whether it is fresh, or whether
it covers the intended scope. Projection timing claims require route/apply
output with `generated_at` or an equivalent receipt timestamp, `projection_scope`,
bounded plugin scope or an explicit full-library declaration,
`global_counts_included`, and focused validation.

The selected-gap contract is also not proposal-evidence proof. A selected Stage
17 gap can name the next capability-economy slice, but it does not verify
proposal artifact refs, proposal-review receipts, validation receipts, or
quality-evidence refs. Proposal-evidence claims require an existing governed
route, bounded plugin id scope, proposal/review/evidence references, and focused
validation.

The selected-gap contract is also not publication proof. A selected Stage 17 gap
can route a worker to a bounded slice, but it does not prove that the slice has
been committed, pushed, represented by a PM-owned publication marker, accepted
as an explicit no-change receipt, or blocked with evidence. Publication claims
require the PM-owned marker to reference the matching prompt hash and represent a
GitHub push, explicit no-change receipt, or blocked-with-evidence receipt, with
focused validation named.

The selected-gap contract is also not worker-readback proof. A selected Stage 17
gap can route a worker to a bounded slice, but it does not prove that a worker
packet or lane readback exists. Worker-readback claims require a lane readback
path, matching prompt hash, files changed, validation run, blockers/risks,
proposed commit scope, and next recommended prompt.

The selected-gap contract is also not worker/publication handoff proof. A
selected Stage 17 gap can route a worker to a bounded slice, but it does not
prove that both the worker lane readback and PM-owned publication marker exist
for the same prompt hash. Handoff claims require a lane readback path, PM-owned
publication marker, matching prompt hash, GitHub push or explicit no-change or
blocked receipt, files changed, validation run, blockers/risks, proposed commit
scope, and next recommended prompt.

The selected-gap contract is also not worker execution or session-liveness
proof. A selected Stage 17 gap can route a worker to a bounded slice, but it
does not prove that a worker terminal/session is alive, completed, blocked, or
represented by a usable readback. Worker execution claims require a worker
session path, matching prompt hash, process liveness or exit code, completed or
blocked status, lane readback or last message, files-changed or no-change scope,
and validation or blocker evidence.

## Percentage Rule

The model does not invent numeric completion baselines. Overall Francis and
current build-phase percentages may move only when there is:

- a known baseline source
- validated repo evidence
- a ledger-backed gate or milestone change
- explicit remaining blockers

Runtime-only success, elapsed time, effort, prompt agreement, or documentation
cleanup does not move project or phase percentages.

## Loop Guards

Every `continue` run should satisfy these guards:

- read the completion ledger
- read the build manifest when phase or milestone posture matters
- identify the latest validated slice
- name the remaining truthful gap
- preserve the open Stage 17 gap when Stage 17 remains open behind newer
  non-Stage-17 ledger entries
- inspect and preserve unrelated dirty work before editing
- preserve dirty work unless explicitly told to revert it
- choose one bounded roadmap-aligned slice
- validate the touched path
- update the ledger only when repo truth materially changed
- keep Stage 17 readback/apply boundaries explicit: readbacks remain
  authority-denying, and any apply route must be governed, dry-run confirmed,
  scoped, and tested
- keep Stage 17 queue-count claims evidence-backed: selected gaps are not global
  queue counts, and queue movement needs route/apply evidence with projection
  scope, global-count inclusion, before/after counts, and validation
- keep Stage 17 projection-timing claims evidence-backed: selected gaps are not
  freshness proof, and broad readback/projection hardening needs route/apply
  evidence with generated-at or receipt timestamp, projection scope, bounded
  plugin scope or full-library declaration, global-count inclusion, and
  validation
- keep Stage 17 proposal-evidence claims reference-backed: selected gaps are not
  proposal evidence refs, and proposal-evidence movement needs existing route
  evidence, bounded plugin scope, proposal/review/validation refs, and focused
  validation
- keep Stage 17 publication claims marker-backed: selected gaps are not
  publication evidence, and publication claims need a PM-owned marker with the
  matching prompt hash, GitHub push or explicit no-change/blocked receipt, and
  focused validation
- keep Stage 17 worker-readback claims receipt-backed: selected gaps are not
  worker lane readbacks, and worker packet claims need a lane readback path,
  matching prompt hash, files changed, validation, blockers/risks, proposed
  commit scope, and next recommended prompt
- keep Stage 17 worker/publication handoff claims receipt-backed: selected gaps
  are not proof that the lane readback plus PM-owned publication marker exist
  for a matching prompt hash, GitHub push/no-change/blocked receipt,
  validation, blockers/risks, proposed commit scope, and next prompt
- keep Stage 17 worker execution/session-liveness claims evidence-backed:
  selected gaps are not proof that a worker process is alive, completed,
  blocked, or represented by a valid session readback; worker execution claims
  need a worker session path, matching prompt hash, process liveness or exit
  code, completed or blocked status, lane readback or last message,
  files-changed or no-change scope, and validation or blocker evidence

## Non-Goals

This is not a roadmap replacement, a CI gate, an automatic stage closer, or a
claim that Francis is complete. It is a conservative readback model for keeping
implementation work out of loops.
