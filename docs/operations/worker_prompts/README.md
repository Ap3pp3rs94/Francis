# Francis Worker Prompts

These prompts are for Codex worker sessions launched by
`scripts/start-francis-worker-terminals.ps1`.

The worker model is intentionally bounded:

- one active Codex child per worker lane
- one roadmap-aligned lane per worker
- no uncontrolled recursive agents
- no Continuum restart unless the operator explicitly asks
- no Orb visual changes
- no commits or pushes unless the operator explicitly asks

Each worker must inspect repo truth before editing, preserve unrelated dirty
work, validate its own lane, and leave a concise handoff if it cannot complete
the bounded slice.

## Four-Lane Pass Rule

Each coordinator pass should keep all four lanes active at the same time:

- Worker 1 advances Orb voice proof and monitor truth.
- Worker 2 advances lens-to-overlay spatial contracts.
- Worker 3 advances voice receipts and provider boundaries.
- Worker 4 advances Stage 17 and completion-model truth.

Manual launches default to physical visible terminals. Add
`-LaunchMode Background` when a worker should run hidden but still keep the same
session and receipt status contract.

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
relaunches default to `-WorkerLaunchMode Background`, so future passes do not
need four physical terminals open. It does not spawn nested coordinators and it
records `uncontrolled_recursion_allowed=false`.

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
