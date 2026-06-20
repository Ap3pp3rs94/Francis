# Francis Worker Prompts

These prompts are for Codex worker sessions launched by
`scripts/start-francis-worker-terminals.ps1`.

The worker model is intentionally bounded:

- one active Codex child per worker lane
- one roadmap-aligned lane per worker
- up to four short-lived drones per worker cycle when useful
- no uncontrolled recursive agents or self-spawning loops
- no Continuum restart unless the operator explicitly asks
- no Orb visual changes
- no commits or pushes unless the operator explicitly asks

Each worker must inspect repo truth before editing, preserve unrelated dirty
work, validate its own lane, and leave a concise handoff if it cannot complete
the bounded slice.

## Recursive Build Swarm Doctrine

Hierarchy:

- Lead Builder controls direction, integration, validation, commits, and pushes.
- Four workers own roadmap-aligned lanes.
- Each worker may use up to four short-lived drones per cycle.
- Drones complete narrow tasks, produce evidence packets, and terminate.

Drones do not own architecture, decide roadmap, claim completion, restart
Continuum, commit, push, or write publication markers. A drone receives one
narrow task, inspects only relevant files, makes the smallest coherent change
or analysis, validates the touched path, reports evidence, and stops.

Each drone packet must include:

- files inspected
- files changed
- exact change
- validation run
- risks
- recommended next step

Workers must compare drone outputs, reject weak or duplicate work, independently
verify claims, consolidate only accepted output, discard noise, and create a
worker packet for the Lead Builder.

Worker packet format:

```text
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
```

The `CAPABILITY EVOLUTION` section must classify accepted work using the
operation report categories when applicable: Presence, Lens, Voice, Memory,
Governance, Receipts, Missions, Overlay, Observability, Completion Model,
Capability Registry, Swarm Infrastructure, Operator Controls, API Surface,
Documentation, and Testing. Workers should distinguish activity from progress
and name any new receipt, governance protection, validation coverage, or
architectural contract strengthened.

Only verified work survives. Only compressed context survives. Only
roadmap-aligned capability survives.

## Four-Lane Pass Rule

Each coordinator pass should keep all four lanes active at the same time:

- Worker 1 advances Stage 17 backlog class reduction through bounded pack/batch mechanisms.
- Worker 2 advances Stage 17 lifecycle, versioning, migration, compatibility, promotion/apply, quarantine, and deprecation.
- Worker 3 advances Stage 17 governed reusable invocation and visible cross-context reuse.
- Worker 4 runs project-wide CI and wiring checks, verifies the current build
  diagram against repo truth, and fixes only narrow CI/wiring blockers.

The worker IDs are retained for script compatibility, but the active priority is
truthful Stage 17 closure. At least three active workers must remain on direct
Stage 17 construction while Worker 4 owns the CI/wiring truth lane. CI,
receipts, governance, docs, and observability support construction; they do not
replace it.

Manual launches default to physical visible terminals. Add `-LaunchMode Exec`
when a worker should run as a true background Codex execution with JSONL logs
and a last-message file. Add `-LaunchMode Minimized` only when an operator wants
a real terminal kept available in the taskbar.

The coordinator should use
`powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-francis-worker-terminals.ps1 -Mode Status`
to verify that every lane has a live worker process, a Codex child process, a
launch-mode record, and a stable prompt hash before treating the pass as active.

For continuous operation, use the bounded coordinator:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\francis-worker-coordinator.ps1 -Mode Start
```

The coordinator keeps one active Codex child per lane. When a lane finishes and
its Codex child exits, the coordinator records a receipt and relaunches that
lane with an individualized project-manager dispatch prompt. Coordinator
relaunches default to `-WorkerLaunchMode Exec`, so future passes run through
`codex exec` instead of the interactive TUI. Exec launches write per-lane JSONL
stdout, stderr, and last-message paths under `.francis/worker-terminal-logs/`
and expose those paths through worker status. Hidden `Background` launches use
the interactive TUI without a TTY and may fail; do not use that mode for the
continuous PM loop. Minimized launches remain available as an operator fallback.
The coordinator does not spawn nested coordinators and it records
`uncontrolled_recursion_allowed=false`.

Each relaunch uses an individual project-manager dispatch prompt under
`.francis/worker-terminal-coordinator/dispatches/`. The dispatch prompt includes
the worker's lane prompt, current completion-model readback, dirty worktree
summary, prior worker status, and lane-specific project-manager direction.
Workers are instructed to leave concise lane readbacks under
`.francis/worker-terminal-coordinator/readbacks/` so the project-manager session
can inspect files touched, validation, blockers, and the next lane prompt
without relying on terminal scrollback. Workers also name their proposed commit
scope there, but the project-manager session owns validation, staging, commit,
and push so GitHub receives reviewable lane-sized updates instead of mixed
terminal output.

## Publication Gate

The coordinator may launch the first prompt for a lane without prior evidence.
After that, a lane is not eligible for a new prompt until the prior pass has:

- a lane readback under `.francis/worker-terminal-coordinator/readbacks/`
- a PM-owned publication marker under
  `.francis/worker-terminal-coordinator/publications/`

Publication markers are keyed by worker ID and the prior prompt SHA-256. Valid
marker statuses are:

- `github_pushed`
- `no_changes`
- `blocked_with_receipt`

This prevents silent prompt loops: every re-prompt must be preceded by either a
GitHub-backed update, an explicit no-change receipt, or a blocked receipt with
evidence.

Preview the next four dispatch prompts without launching duplicate workers:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\francis-worker-coordinator.ps1 -Mode Run -MaxIterations 1 -PollSeconds 5 -NoLaunch -ForcePromptAll -StateRoot .\.francis\worker-terminal-coordinator-preview
```

Stop it with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\francis-worker-coordinator.ps1 -Mode Stop
```

Read it with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\francis-worker-coordinator.ps1 -Mode Status
```
