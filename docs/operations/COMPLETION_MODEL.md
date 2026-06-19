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
- preserve dirty work unless explicitly told to revert it
- choose one bounded roadmap-aligned slice
- validate the touched path
- update the ledger only when repo truth materially changed

## Non-Goals

This is not a roadmap replacement, a CI gate, an automatic stage closer, or a
claim that Francis is complete. It is a conservative readback model for keeping
implementation work out of loops.
