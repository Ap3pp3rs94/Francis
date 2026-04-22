# FRANCIS - COMPLETION_LEDGER

Shipped-state ledger for the current repository posture, hardening progress, and
productization gaps.

This file is intentionally narrower than `docs/canonical/ROADMAP.md`. The roadmap
defines the target state. This ledger records what is materially true in the repo,
using direct inspection plus validation that was actually run.

## 1. Document contract

Use this file for:

- current build posture
- high-confidence validated surfaces
- known gaps that still block a truthful "finished" claim
- the latest targeted validation evidence
- the first continuity/orientation source for recurring build automations

Do not use this file for:

- aspirational future capabilities
- unverified completion claims
- UI/demo descriptions that outrun server truth
- casual rewrites of canonical roadmap direction

Automation rule:

- recurring build automations should read this ledger first before re-reading the
  full canonical roadmap set
- canonical roadmap docs should be re-read when this ledger is missing, stale,
  contradicted by repo truth, or when milestone/workstream closure is being
  evaluated
- update this ledger at the end of a run when a validated surface materially
  changed, a major blocker was removed, or the strongest truthful build posture
  changed
- update `docs/canonical/BUILD_MANIFEST.md` or other canonical roadmap docs only
  when their own update contracts are actually met

## 2. Current build phase

Francis is in `Phase 2` per `docs/canonical/BUILD_MANIFEST.md`.

The strongest current posture is still the governed runtime spine, not the finished
operator product surface:

- `P9_OBSERVABILITY`: strongest plane today
- `P3_GOVERNANCE`: materially real
- `P1_INTERFACE`: partial
- `P7_EXECUTION`: partial
- `P8_MEMORY`: partial

This matches the current canonical build priority in `docs/BUILD_ORDER.md`:

1. close remaining governance and identity gaps
2. complete the end-to-end plan -> gate -> execute -> trace -> memory loop
3. expose that loop clearly in the chat UI

As of `2026-04-21`, Stage 2 Observer has a receipt-backed transition posture for
the current local state. A live `POST /system/observer/scan` returned readiness
`ready` with `5/5` criteria satisfied and receipt
`obs_scan_1776798650837_20306fb7`. That supports beginning Stage 3 Mission work,
with the caveat that Observer readiness is state-dependent and should be re-run
before any milestone or release claim.

As of `2026-04-21`, Stage 3 Mission work has begun with a readiness projection,
not a completion claim. Mission continuity can now report which Stage 3 criteria
are satisfied, missing, or attention-worthy from the current local mission
records, queue, deadletter, history, and briefing context.

As of `2026-04-21`, mission mutation responses now carry post-action
continuity envelopes. Create, update, tick, deadletter, and advance responses can
return the current mission history, linked operations, run-ledger projection, and
loop-state handoff, so callers do not need to reconstruct mission state after an
action.

As of `2026-04-21`, mission queue-run results now carry bounded post-run
handoff context. Each processed mission result can expose the current mission
record, loop-state handoff, and compact continuity evidence counts, so the ORB
mission queue summary can show what changed and what should happen next without
implying hidden autonomy or requiring a full detail reload for every row.

As of `2026-04-21`, mission records now carry explicit context fields for
continuity handoff: `owner_id`, `dependency_ids`, and `escalation_path`.
These fields are preserved through the mission store, API, world-state
snapshots, and ORB composer/inspector surfaces, so operators can see who owns a
mission, what it depends on, and how blocked work should be escalated.

As of `2026-04-22`, mission queue recommendations are dependency-aware. Queued
or active missions with unresolved `dependency_ids` now report a bounded
dependency state and wait for the dependency instead of creating or running
linked work prematurely.

As of `2026-04-22`, continuity briefings now carry dependency blocker evidence
from mission queue state. Dependency-gated focus items include dependency ids,
counts, state, and escalation path, so shift handoff can explain why work is
waiting instead of implying it is simply ready.

As of `2026-04-22`, the ORB Shift Briefing UI now renders that dependency
blocker evidence directly in the Focus Now cards. Dependency action targets route
to mission inspection when they identify a mission and to operation inspection
when they identify a linked task, so operator handoff actions follow the actual
blocked surface.

As of `2026-04-22`, mission approval holds now survive into the ORB re-entry
surfaces. The Settings client preserves mission approval ids and statuses from
world-state queues and continuity focus items, and the Shift Briefing / Mission
Queue cards can open the exact pending approval without forcing a mission-detail
round trip first.

As of `2026-04-20`, the strongest truthful CI posture is:

- feature-branch pushes no longer create duplicate GitHub `push` + `pull_request`
  runs; PR validation now executes once per change on non-`main` branches
- repo-wide type debt is still materially present, but `mypy.ini` now scopes that
  debt explicitly to known modules instead of letting the CI surface imply the
  whole tree is already under a clean type gate
- `mypy src` is now green again for the currently gated tree, which removes an
  unrelated GitHub blocker from the active Stage 2 observer follow-up line

## 3. High-confidence current slice

As of `2026-04-22`, the highest-confidence surface newly advanced in the current
Stage 3 line is approval-aware mission re-entry. This advances the active
`Phase 2 / P8_MEMORY -> P1_INTERFACE` line by keeping governance blockers
actionable from mission handoff surfaces:

- `apps/chat_ui/src/settings/index.ts` now preserves
  `last_task_approval_id`, `last_task_previous_approval_id`, and
  `last_task_approval_status` on world-state mission queue items and continuity
  briefing focus items.
- `apps/chat_ui/src/App.tsx` now shows approval ids/statuses in Shift Briefing
  and Mission Queue cards and routes `Review approval` through the existing
  approvals panel with mission/operation context.
- `apps/chat_ui/src/settings/index.test.ts` now proves the browser parser keeps
  these approval-hold fields instead of dropping backend handoff truth.

As of `2026-04-22`, the highest-confidence surface newly advanced in the current
Stage 3 line is dependency-aware Shift Briefing rendering. This advances the
active `Phase 2 / P8_MEMORY -> P1_INTERFACE` line by making existing dependency
truth visible at the operator handoff point:

- `apps/chat_ui/src/App.tsx` now shows dependency resolved/total counts,
  dependency state, first unresolved dependency id, and escalation path on Shift
  Briefing focus cards.
- Shift Briefing focus actions now distinguish mission action targets from
  operation action targets, avoiding a false "Open linked task" action for a
  dependency mission id.
- This is UI surfacing of already-governed mission state; it does not add new
  mission progression or autonomous behavior.

As of `2026-04-22`, the highest-confidence surface newly advanced in the current
Stage 3 line is dependency blocker briefing. This advances the active
`Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by carrying queue
blocker truth into shift handoff:

- `src/francis/world_state/snapshot.py` now projects dependency waiting counts
  and dependency state into continuity briefing focus and readiness evidence.
- `apps/chat_ui/src/settings/index.ts` now preserves dependency blocker fields
  in the continuity briefing parser.
- `tests/test_api_continuity.py` and
  `apps/chat_ui/src/settings/index.test.ts` now prove dependency-gated handoff
  keeps the blocker id, dependency state, and escalation path visible.

As of `2026-04-22`, the highest-confidence surface newly advanced in the current
Stage 3 line is dependency-aware mission queue gating. This advances the active
`Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by preventing
declared dependencies from becoming passive metadata:

- `src/francis/missions/store.py` now projects dependency state for mission and
  operation dependency ids, including resolved, waiting, blocked, missing, and
  self-dependency cases.
- Queue recommendations now return `wait_for_dependency` or
  `resolve_dependency_blocker` for queued/active missions whose dependencies are
  not clear, so `/missions/run_once` does not create fake progress before the
  dependency is satisfied.
- `apps/chat_ui/src/missions/index.ts`,
  `apps/chat_ui/src/settings/index.ts`, and `apps/chat_ui/src/App.tsx` now
  preserve and render dependency-state evidence in ORB mission queue surfaces.
- `tests/test_mission_store.py`, `tests/test_api_missions.py`,
  `apps/chat_ui/src/missions/index.test.ts`, and
  `apps/chat_ui/src/settings/index.test.ts` now prove unresolved dependencies
  block auto-advance and completed dependencies make the mission actionable.

As of `2026-04-21`, the highest-confidence surface newly advanced in the current
Stage 3 line is the mission context contract. This advances the active
`Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by making mission
continuity data explicit instead of inferred from loose text:

- `src/francis/missions/store.py` now stores typed `owner_id`,
  `dependency_ids`, and `escalation_path` fields, records continuity updates,
  and keeps legacy mission records readable with bounded defaults.
- `src/francis/api/routes/missions.py` and
  `src/francis/world_state/snapshot.py` now expose those fields through mission
  reads, mutation responses, queue payloads, and recent mission summaries.
- `apps/chat_ui/src/App.tsx`, `apps/chat_ui/src/missions/index.ts`, and
  `apps/chat_ui/src/settings/index.ts` now preserve and render mission owner,
  dependency, and escalation context in the ORB composer, mission inspector, and
  briefing parsers.
- `tests/test_mission_store.py`, `tests/test_api_missions.py`,
  `apps/chat_ui/src/missions/index.test.ts`, and
  `apps/chat_ui/src/settings/index.test.ts` now prove the contract survives
  create, update, readback, parsing, and legacy-record paths.

As of `2026-04-21`, the highest-confidence surface newly advanced in the current
Stage 3 line is mission queue-run handoff continuity. This advances the active
`Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by making bounded
queue passes report truthful next-step context per processed mission:

- `src/francis/api/routes/missions.py` now enriches `/missions/run_once` result
  rows with each mission's serialized record, current loop-state handoff, and
  bounded history/linked-operation/run-ledger counts.
- The queue-run endpoint intentionally does not attach full histories or full
  operation logs per row; it returns enough evidence for operator re-entry while
  keeping detailed inspection behind the existing mission detail route.
- `apps/chat_ui/src/missions/index.ts` now preserves the queue-run mission,
  loop-state, handoff, and continuity-count fields.
- `apps/chat_ui/src/App.tsx` now renders the active stage, handoff detail, and
  compact evidence counts in the ORB mission queue pass summary.
- `tests/test_api_missions.py` and `apps/chat_ui/src/missions/index.test.ts`
  now prove queue-run results preserve mission handoff context for created,
  completed, blocked, and approval-gated mission outcomes.

As of `2026-04-21`, the highest-confidence surface newly advanced in the current
Stage 3 line is post-action mission continuity. This advances the active
`Phase 2 / P8_MEMORY -> P7_EXECUTION -> P1_INTERFACE` line by making mutation
responses return the same continuity evidence as mission detail reads:

- `src/francis/api/routes/missions.py` now centralizes mission detail projection
  for history, linked operations, run-ledger entries, and loop-state handoff.
- Mission create, patch, tick, deadletter, and advance responses now include
  this projection when a mission record is available, reducing the need for
  operator surfaces to perform a second read before knowing the next truthful
  action.
- Mission loop state now treats fresh missions with no linked operation as
  `plan` instead of `execute`, and deadlettered/failed missions hand off through
  explicit deadletter review rather than pretending they are still live at a
  gate.
- `apps/chat_ui/src/missions/index.ts` now preserves mission detail projection
  fields on create and advance responses. `apps/chat_ui/src/App.tsx` can use
  returned loop-state handoff detail in mission action notices.
- `tests/test_api_missions.py` and `apps/chat_ui/src/missions/index.test.ts`
  now prove post-action responses carry continuity envelopes and preserve
  deadletter/plan handoff truth.

As of `2026-04-21`, the highest-confidence surface newly advanced in the current
Stage 3 line is a mission readiness projection inside the continuity briefing.
This advances the active `Phase 2 / P8_MEMORY -> P1_INTERFACE` line by mapping
Mission state to the roadmap's Stage 3 done criteria without adding new
autonomy or fake progress:

- `src/francis/world_state/snapshot.py` now computes a bounded
  `mission_readiness` projection from existing mission status counts, queue
  items, deadletter items, recent mission summaries, mission histories, and
  run-ledger-linked activity.
- The projection maps to the Stage 3 criteria: idempotent ticks, clean
  deadletter behavior, visible mission status, session continuity, and reduced
  manual reconstruction.
- `/continuity/briefing` now includes this readiness object under the existing
  mission briefing payload, so operator handback can distinguish `ready`,
  `review`, and `attention` mission posture from actual local evidence.
- `apps/chat_ui/src/settings/index.ts` and `apps/chat_ui/src/App.tsx` now
  preserve and render Mission readiness in the Shift Briefing. The UI shows
  criterion status plus the next truthful action instead of implying mission
  completion.
- `tests/test_api_continuity.py` and
  `apps/chat_ui/src/settings/index.test.ts` now prove idle missions report a
  review posture, real handoff/completion evidence can satisfy continuity
  criteria, clean deadletters are detected, and zero satisfied counts are not
  dropped by the UI parser.

As of `2026-04-21`, the highest-confidence surface newly advanced in the current
Stage 2 line is an explicit Observer readiness checklist. This advances the
active `Phase 2 / P9_OBSERVABILITY -> P1_INTERFACE` line by making Stage 2
closure criteria inspectable without claiming completion automatically:

- `src/francis/world_state/snapshot.py` now computes a bounded
  `observer_readiness` projection from the current incident snapshot and recent
  explicit scan receipts. The projection maps directly to the Stage 2 done
  criteria: evidence-backed incidents, traceable scans, receipted findings,
  truthful presence links, and explicit/non-invasive awareness.
- `src/francis/api/routes/system.py` now includes the readiness projection in
  `/system/observer` and `/system/observer/scan`, so the live observer surface
  can distinguish `ready`, `review`, and `attention` states from actual local
  evidence.
- `src/francis/api/routes/continuity.py` now carries the same readiness
  projection into the continuity briefing, keeping the operator handback surface
  aligned with observer truth instead of requiring source diving.
- `apps/chat_ui/src/settings/index.ts` and `apps/chat_ui/src/App.tsx` now
  preserve and render Observer readiness in the embedded observer surface. The
  UI shows criterion status and the next truthful action, such as recording an
  explicit observer scan when scan receipts are missing.
- `tests/test_api_system_settings.py`, `tests/test_api_continuity.py`, and
  `apps/chat_ui/src/settings/index.test.ts` now prove idle observer state reports
  a review posture until a scan is receipted, while post-scan observer state can
  reach `ready` when current findings are covered by traceable receipts.

As of `2026-04-21`, the highest-confidence surface newly advanced in the current
Stage 2 line is observer finding timestamp lineage. This advances the active
`Phase 2 / P9_OBSERVABILITY -> P1_INTERFACE` line by making observer truth more
traceable without adding new probes, background sensing, or autonomy:

- `src/francis/world_state/snapshot.py` now preserves the already-computed
  observation timestamp on every emitted observer incident and probe summary.
  Findings can now say when they were observed instead of only what was found.
- `src/francis/api/routes/system.py` now exposes `observed_at` on the live
  `/system/observer` and `/system/observer/scan` response envelope while keeping
  existing `generated_at` behavior intact.
- `src/francis/api/routes/continuity.py` now carries the same observer
  observation timestamp into the continuity briefing, so presence and handback
  surfaces can cite observer truth with time context.
- `apps/chat_ui/src/settings/index.ts` now preserves the top-level observer scan
  `observed_at` field in the browser control-plane client. Existing incident and
  probe parsers already preserve their own `observed_at` fields.
- `tests/test_api_system_settings.py`, `tests/test_api_continuity.py`, and
  `apps/chat_ui/src/settings/index.test.ts` now prove observation timestamps
  survive world-state incidents, explicit observer scan receipts, recent-scan
  history, continuity observer focus, probe summaries, and the UI client parser.

As of `2026-04-21`, the highest-confidence surface newly advanced in the current
Stage 2 line is a system-runtime mutation posture guard, following the CI
platform cleanup already landed on `main`. This advances the active `Phase 2 /
P3_GOVERNANCE -> P2_IDENTITY -> P9_OBSERVABILITY` line without changing
operator-mode control semantics:

- `.github/workflows/ci.yml` now uses Node-24-ready major versions for the
  GitHub-managed checkout and Python setup actions, removing the CI platform
  deprecation warning from the canonical `main` validation path while preserving
  the existing OS/Python matrix.
- `src/francis/api/routes/system.py` now applies the existing operator posture
  write guard to service actions, feature-flag writes, and runtime config
  mutations. Observe mode keeps these system mutations read-only instead of
  allowing runtime behavior changes through `/system` while execution and
  mission paths are blocked.
- `tests/test_api_system_settings.py` now proves observe mode blocks those
  system mutation routes without writing feature-flag or runtime-settings state,
  while still allowing `/system/operator-mode` to return the operator to an
  active mode. Existing mutation alias tests continue to prove canonical state
  sharing when posture allows writes.
- `src/francis/kernel/feature_flags.py` now keeps default env-backed feature
  flag timestamps stable for the process lifetime, so `/system/flags`,
  `/system/feature_flags`, and `/system/features` stay alias-equivalent across
  reads instead of racing a timestamp boundary.

As of `2026-04-21`, the highest-confidence surface newly touched in the current
working tree is a mission-loop handoff projection that advances the active
`Phase 2 / P7_EXECUTION -> P9_OBSERVABILITY -> P8_MEMORY -> P1_INTERFACE` line
without adding new mission state or autonomous behavior:

- `src/francis/api/routes/missions.py` now derives a bounded
  `loop_state.handoff` object from existing mission, linked-operation,
  governance, trace, and history receipts. The handoff names the active loop
  stage, next operator action, evidence detail, and relevant task, approval,
  gate, trace, or continuity receipt identifiers when present.
- `apps/chat_ui/src/missions/index.ts` now preserves that handoff contract in
  the browser parser instead of forcing the ORB mission inspector to infer the
  next step from individual stage cards.
- `apps/chat_ui/src/App.tsx` now renders a compact “Loop Handoff” card in the
  ORB mission detail surface, with direct approval/task actions when the
  handoff is backed by those identifiers.
- `tests/test_api_missions.py` and `apps/chat_ui/src/missions/index.test.ts`
  now prove both blocked governance missions and completed linked-operation
  missions expose a truthful next handoff from the plan -> gate -> execute ->
  trace -> memory loop.

As of `2026-04-18`, the highest-confidence surface newly touched in the current
working tree is an operator-triggerable observer scan path in the live ORB
surface that advances the active `Phase 2 / P9_OBSERVABILITY -> P1_INTERFACE`
line without introducing hidden polling or unreceipted observer activity:

- `apps/chat_ui/src/settings/index.ts` now exposes a dedicated
  `recordObserverScan()` mutation on the governed settings client, bound to the
  explicit `/system/observer/scan` route instead of using ad hoc fetch logic.
- `apps/chat_ui/src/App.tsx` now adds a visible `Record observer scan` action in
  the embedded observer section of the ORB/Shift Briefing surface and wires it
  through the existing refresh path, so explicit observer receipts can be
  created and then immediately inspected in the same truthful continuity UI.
- The command palette now also exposes that same explicit scan action, which
  keeps the scan pathway operator-legible without implying background autonomy.
- `tests/test_api_contract_chat_ui.py` now pins `/system/observer/scan` into the
  mounted UI contract, and `apps/chat_ui/src/settings/index.test.ts` now proves
  the client mutation preserves observer receipt ids and decisions.

As of `2026-04-18`, the highest-confidence surface newly touched in the current
working tree is a continuity-facing observer decisions log that advances the
active `Phase 2 / P9_OBSERVABILITY -> P1_INTERFACE` line without creating
ambient observer activity or adding a second observer polling path:

- `src/francis/world_state/snapshot.py` now exposes shared observer scan receipt
  projection and history helpers, so explicit `observer.scan` audit receipts can
  be reused consistently across system and continuity surfaces instead of being
  reinterpreted differently at each API edge.
- `src/francis/api/routes/continuity.py` now embeds recent explicit observer
  scan receipts inside the continuity briefing’s observer payload. The shift
  briefing can now carry both current observer truth and the recent receipted
  scan/decision trail in one bounded payload.
- `apps/chat_ui/src/settings/index.ts` and
  `apps/chat_ui/src/settings/index.test.ts` now preserve that recent observer
  scan history through the browser parser, including decision, status, receipt
  id, probes, and top focus incidents.
- `apps/chat_ui/src/App.tsx` now renders a compact “Recent explicit observer
  scans” block inside the embedded observer surface in Shift Briefing, making
  the Stage 2 observer decisions log visible in the same return-to-work surface
  as orb/operator handback truth.
- `tests/test_api_continuity.py` now proves that an explicit observer scan
  receipt survives into the continuity briefing instead of remaining stranded in
  the backend-only observer API.

As of `2026-04-18`, the highest-confidence surface newly touched in the current
working tree is an explicit observer scan receipt path that advances the active
`Phase 2 / P9_OBSERVABILITY` line without inventing ambient autonomy or writing
audit noise on passive reads:

- `src/francis/api/routes/system.py` now exposes a bounded `/system/observer`
  surface for current observer truth plus recent explicit scan receipts, and a
  `/system/observer/scan` route that snapshots incidents and writes an
  `observer.scan` audit record only when the operator explicitly requests a
  scan.
- Observer scan receipts now carry a concrete decision (`stable`, `review`, or
  `urgent_review`), bounded severity counts, incident ids, probe ids, and the
  top evidence-backed findings, so Stage 2 scans are both traceable and rich
  enough to support a real decisions log instead of a vague “observer ran”
  claim.
- The same route family now exposes `/system/observer/events`,
  `/system/observer/log`, and `/system/observer/audit` aliases that project
  recent `observer.scan` receipts without emitting new ones, preserving the
  distinction between observation state and receipted scan actions.
- `tests/test_api_system_settings.py` now proves the important contract:
  read-only observer routes stay passive, explicit scans emit one receipt,
  recent-scan history is queryable through the alias routes, and the receipt
  carries the expected governance-backed incident ids and probes.

As of `2026-04-18`, the highest-confidence surface newly touched in the current
working tree is an evidence-backed observer continuity bridge that advances the
active `Phase 2 / P9_OBSERVABILITY -> P1_INTERFACE` line without widening
authority or inventing mission state:

- `src/francis/world_state/snapshot.py` now exposes bounded observer evidence on
  each derived incident instead of only returning category/title/count summaries.
  Incidents now carry their generating probe id plus concrete evidence items
  such as missing stack/service surfaces, pending approvals, or task ids and
  status reasons from governed task state.
- The observer summary path is now reusable through
  `observer_incident_snapshot()`, so both world-state and continuity surfaces
  project the same locally derived findings instead of drifting into parallel
  observer logic.
- `src/francis/api/routes/continuity.py` now embeds an observer briefing inside
  the continuity briefing payload, with an observer headline, bounded severity
  counts, and the top active incidents. This lets the presence surface cite
  observer truth directly instead of forcing the operator to switch to the
  separate world-state panel.
- `apps/chat_ui/src/settings/index.ts` now preserves the new observer briefing
  contract plus incident probe/evidence fields through the browser parser rather
  than silently dropping them.
- `apps/chat_ui/src/App.tsx` now renders the embedded observer surface inside the
  Shift Briefing card and shows probe/evidence details in both the briefing and
  incident-view cards, so observer findings are inspectable from the same
  return-to-work surface that already carries operator and ORB handback state.
- `tests/test_api_continuity.py`, `tests/test_api_system_settings.py`, and
  `apps/chat_ui/src/settings/index.test.ts` now prove that the observer bridge is
  evidence-backed, alias-stable, and preserved by the UI parser.

As of `2026-04-17`, the highest-confidence surface newly touched in the current
working tree is a read-only continuation/build observer for the canonical Codex
watcher, which advances the active `Phase 2 / P9_OBSERVABILITY` line without
changing watcher authority or repo execution behavior.

Directly inspected implementation truth:

- `scripts/francis-observer-lib.ps1` now provides the shared read-only observer
  contract for watcher pid/state/log inspection, pinned-session resolution,
  recent task-event parsing from the live session jsonl, real build/test command
  detection from session exit codes, and git branch/commit/status summarization
  from `C:\Francis`.
- The observer/session resolution path is now locked to one exact session file:
  it resolves an explicit session path or the watcher-side
  `watch-session.txt` pin first, falls back only to the already-known
  `last_seen_session_file` for bootstrap, and no longer scans all matching Codex
  session files for the thread.
- `scripts/watch-francis-live.ps1` now renders a 25-second-by-default terminal
  dashboard showing watcher pid/alive truth, thread id, last launch
  decision/verification state, last task start and terminal timestamps, idle
  seconds, pinned session file path, latest git branch/commit/status, and the
  latest build/test command with `test_status` derived from real session exit
  codes instead of inferred progress.
- `scripts/tail-francis-events.ps1` now exposes observer tail/snapshot modes for
  watcher log, watcher state json, and pinned-session recent task events.
- The observer surface keeps execution and observability separate: it reads the
  canonical watcher files and repo state but does not mutate watcher control,
  repo state, or continuation logic.
- Live validation also proved the observer does not trust stale files blindly:
  during this run the watcher pid file still pointed at `34640`, but the live
  dashboard reported `watcher_alive: false` while still surfacing the last
  verified launch receipt and pinned session path, which is the truthful state
  the operator needs.

The `2026-04-17` ORB mission receipt recency slice is now materially true in the
repo and advances the same `Phase 2 / P1_INTERFACE -> P8_MEMORY` continuity line
without widening authority or inventing progress:

- `src/francis/api/routes/missions.py` now carries the latest trace receipt name
  and timestamp plus the latest mission-history receipt timestamp into mission
  `loop_state`, so the ORB mission inspector can show when trace or continuity
  actually moved instead of only showing counts.
- `apps/chat_ui/src/missions/index.ts` now preserves the bounded `latest_ts`
  mission loop-stage field through client parsing instead of dropping receipt
  recency on the browser side.
- `apps/chat_ui/src/App.tsx` now renders receipt recency directly inside the ORB
  mission loop cards, alongside the existing latest receipt label, so the
  operator can judge whether trace or continuity is fresh without leaving the
  loop surface for raw ledgers.
- `tests/test_api_missions.py` now proves the mission detail route returns
  truthful latest trace and memory receipt recency for a governed blocked
  mission.
- `apps/chat_ui/src/missions/index.test.ts` now proves the browser client keeps
  the same `latest_event` and `latest_ts` fields relied on by the ORB mission
  inspector.

The `2026-04-17` mission-feed latest-activity parity slice is now materially
true in the repo and continues the same `Phase 2 / P1_INTERFACE` continuity line
without adding backend authority or new synthetic state:

- `apps/chat_ui/src/settings/index.ts` now preserves backend-provided
  `latest_activity` records through the world-state mission summary and mission
  queue parser instead of silently dropping them before the UI can render them.
- `apps/chat_ui/src/App.tsx` now reuses a shared latest-activity formatter across
  the ORB mission surfaces, adding the same `latest/status/gate/at` recency
  language to shift-focus, recent mission progress, and mission queue cards.
- This closes the gap where freshness was visible only after opening the full
  mission inspector, even though the broader world-state cards already had
  truthful latest-activity receipts available from the backend.
- `apps/chat_ui/src/settings/index.test.ts` now proves the browser parser keeps
  `latest_activity` on recent mission and mission queue records.

The `2026-04-17` observer push-sync slice is now materially true in the repo and
continues the active `Phase 2 / P9_OBSERVABILITY` line without changing watcher
authority:

- `scripts/francis-observer-lib.ps1` now includes push-watcher log summarization
  alongside the existing continuation watcher/session/git helpers, plus timestamp
  age calculation so stale watcher state can be distinguished from merely old
  receipts.
- `scripts/watch-francis-live.ps1` now renders the background GitHub push
  watcher in the main observer dashboard, including pid/alive truth, stop-flag
  state, branch, latest commit, ahead/behind counts, repo-dirty truth, last
  push decision, last push timestamp/result, and explicit watcher/push
  `state_age_seconds` derived from the real `last_checked_at` fields.
- `scripts/tail-francis-events.ps1` now exposes `push-log` and `push-state`
  views so raw GitHub-sync watcher receipts can be inspected without leaving the
  existing observer toolchain.
- Live validation showed the observer reporting the truthful in-progress state:
  continuation watcher alive, push watcher alive, and repo dirty with observer
  changes not yet committed, rather than inventing a clean/pushed status.

As of `2026-04-15`, the highest-confidence surface newly touched in the current
working tree is the governed operations/runtime extension for exact-action
approval refresh on `git.push`, `codex.supervised_exec`, and approval-bound
plugin execution, with canonical Francis environment alias resolution still
materially true in the repo.

Directly inspected implementation truth:

- `src/francis/agent/git_push.py` now binds approval to the exact local repo root,
  remote URL, branch, and upstream intent, and refreshes approval requests when
  that payload changes after an approval was granted instead of reusing a stale
  approval receipt.
- `src/francis/agent/supervised_exec.py` now reissues a fresh exact-action
  approval when the prior approval record is missing/corrupt or when the approved
  supervised-exec payload no longer matches the queued command/cwd/timeout/artifact
  request, instead of returning a dead approval id.
- `src/francis/agent/executor.py`, `src/francis/operations/runtime.py`, and
  `src/francis/api/routes/operations.py` expose the same capability through the
  governed operations loop without bypassing `P3_GOVERNANCE`.
- `src/francis/api/routes/plugins.py` now binds `plugin.run` approvals to the
  exact plugin/action/input/meta request, strips volatile approval-routing fields
  from the approval payload, and refreshes approvals when records are
  missing/corrupt or when the approved plugin request no longer matches the
  queued exact-action payload instead of reusing stale approval receipts.
- `src/francis/api/routes/web_learning.py` now binds approval-backed enable and
  quarantine-delete mutations to the exact requested action payload, refreshes
  missing/corrupt or mismatched approvals into fresh approval ids with receipt
  artifacts, and only mutates web-learning state after a matching approval is
  present instead of reusing stale approval receipts.
- `src/francis/api/routes/web_learning.py` now also binds approval-backed
  `web_learning.request` ingestion to the exact requested URL/source/ingest
  payload, refreshes missing/corrupt or mismatched approvals into fresh approval
  ids with receipt artifacts, and reuses the same record on approved replay
  instead of minting a new approval or leaving duplicate pending request state.
- `tests/test_api_operations.py` now proves that changing the configured remote
  after approval does not silently push and instead forces a fresh exact-action
  approval before execution can continue.
- `tests/test_api_operations.py` and `tests/test_api_supervised_exec.py` now also
  prove that stale supervised-exec approvals are refreshed through both the
  direct API route and the governed operations detail path, with the new approval
  id surfaced back into the queued task state.
- `tests/test_api_plugins.py` now proves plugin approval refresh on exact-input
  drift, cross-tool approval mismatch, and missing approval records, with fresh
  approval lineage and request/mismatch/error artifacts returned to the caller.
- `tests/test_api_operations.py` now also proves the governed `plugin.run`
  operation path refreshes exact-action approvals, rewrites the queued task to
  the new approval id, and preserves truthful governance-hold detail after the
  held task is requeued.
- `tests/test_api_web_learning.py` now proves exact-action approval refresh on
  mismatched enable requests and missing quarantine-delete approvals, with
  refreshed approval lineage and receipt artifacts before the mutation is
  allowed to proceed.
- `tests/test_api_web_learning.py` now also proves exact-action approval refresh
  on mismatched and missing `web_learning.request` approvals, with approved
  replay ingesting against the same record id and preserving truthful approval
  lineage.
- `src/francis/settings.py` and `src/francis/llm/client.py` now resolve canonical
  `FRANCIS_*` environment aliases for repo/runtime/Ollama configuration while
  preserving legacy env-name fallback.

The `2026-04-14` operator-critical Chat UI/API continuity bridge remains
materially true in the repo and is still part of the active `P1_INTERFACE`
continuity line:

Directly inspected implementation truth:

- `apps/chat_ui/src/settings/index.ts` now probes canonical and compatibility alias
  routes for world state, continuity ledger, continuity briefing, orb state,
  operator mode, effective config, config mutation, and feature-flag mutation.
- `apps/chat_ui/src/settings/index.ts` now parses `/continuity/ledger` as a typed
  receipt feed so the operator console can render recent local continuity records
  without inventing synthetic state.
- `apps/chat_ui/src/settings/index.ts` now preserves continuity briefing counts,
  recently completed items, and deadletter preview items even when the backend
  omits a headline or focus list, so sparse handoff payloads do not disappear in
  the operator UI.
- `apps/chat_ui/src/operations/index.ts` now exposes the existing
  `POST /operations/run-once` worker-cycle route as a typed client method so the UI
  can trigger one bounded queue advancement step without inventing a new contract.
- `apps/chat_ui/src/App.tsx` now renders the continuity-embedded `operator` and
  `orb` surfaces inside the ORB panel shift briefing so handoff truth remains
  visible even if dedicated status polling degrades.
- `apps/chat_ui/src/App.tsx` now renders the raw continuity ledger tail in the ORB
  panel so recent chat/daemon continuity receipts remain inspectable during
  return-to-work review.
- `apps/chat_ui/src/App.tsx` now surfaces an explicit worker-cycle control in the
  `Operations` panel, tied to the active operator environment and disabled while the
  control posture is `observe`.
- `src/francis/api/routes/system.py` exposes the corresponding system aliases for
  read and mutation paths.
- `src/francis/api/routes/continuity.py` exposes continuity briefing at
  `/continuity/briefing`, `/continuity/shift_briefing`, and
  `/continuity/shift-briefing`.
- `src/francis/api/routes/continuity.py` also exposes the raw continuity ledger at
  `/continuity/ledger`.
- `src/francis/api/routes/operations.py` exposes both `/operations/run-once` and
  `POST /operations/{operation_id}/run`.
- `docs/CHAT_UI.md` now defines the current compatibility contract for these
  operator-critical surfaces instead of leaving them implied.

The `2026-04-15` operator-console ingress slice is now materially true in the
repo and advances the same `P1_INTERFACE -> P7_EXECUTION` clarity line without
claiming a finished ORB console:

Directly inspected implementation truth:

- `apps/chat_ui/src/missions/index.ts` now exposes typed `list` and `create`
  client methods for `/missions/list` and `/missions/create`, so the browser can
  declare mission continuity through the same stable contract the API already
  exposes instead of staying read-only on mission state.
- `apps/chat_ui/src/App.tsx` now includes a `Governed Request Composer` inside
  the `Operations` panel that can:
  - declare a mission with explicit objective/summary/next-step continuity
  - create the first governed operation against that mission
  - optionally advance the created task immediately through the existing
    `POST /operations/{operation_id}/run` path
  - surface the resulting mission id, task id, and approval id back to the
    operator without inventing hidden progress
- `apps/chat_ui/src/App.tsx` now also hands created mission ids directly into the
  ORB mission inspector, so the operator can move from request ingress to mission
  flow inspection without manual hunting across panels.
- `apps/chat_ui/src/operations/index.test.ts` now proves the UI client preserves
  operation-create approval handoff fields.
- `apps/chat_ui/src/missions/index.test.ts` now proves mission list/create client
  behavior for the new operator-ingress path.

The `2026-04-16` world-state approval projection UI slice is now materially true
in the repo and advances the same `P3_GOVERNANCE -> P1_INTERFACE` clarity line
without changing backend approval law:

- `apps/chat_ui/src/settings/index.ts` now preserves `request_kind`,
  approval-refresh lineage (`previous_approval_id`, `previous_approval_status`),
  and bounded `payload_summary` detail from `/system/world_state` instead of
  collapsing pending approvals down to only id/action/reason/status.
- `apps/chat_ui/src/App.tsx` now renders that truthful approval projection in the
  ORB world-state surfaces, including:
  - request kind and exact-action scope detail in the return-to-work approval
    card
  - request kind, bounded exact-action summary, and approval-refresh lineage in
    the `Pending Approvals` list
- `apps/chat_ui/src/settings/index.test.ts` now proves the browser parser keeps
  the new approval projection fields intact through the compatibility alias path.
- `apps/chat_ui` production build still succeeds after the UI rendering change,
  so the new operator-visible approval context does not break the current chat
  UI bundle.

The `2026-04-16` approvals-panel projection parity slice is now also materially
true in the repo and closes the next operator-review gap on the same governed
line without widening approval scope:

- `apps/chat_ui/src/index.ts` now preserves bounded approval projection fields
  (`request_kind`, approval-refresh lineage, and `payload_summary`) through the
  `/approvals/list` client instead of treating the richer response as an
  untyped cast.
- `apps/chat_ui/src/App.tsx` now reuses that same bounded projection language in
  the direct approvals panel, including:
  - requested-action titles instead of raw action ids when available
  - request kind, exact-action detail, and approval-refresh lineage in both the
    selected approval view and queue cards
  - projection-backed evidence and scope summaries without requiring the
    operator to inspect raw payload JSON first
- `apps/chat_ui/src/index.test.ts` now proves the approvals client preserves the
  richer approval projection contract used by the panel.
- `apps/chat_ui` production build still succeeds after the approvals-panel
  rendering change.

The `2026-04-15` bounded mission-control productivity slice is now also
materially true in the repo and advances the same `P8_MEMORY -> P7_EXECUTION`
continuity line without claiming hidden autonomy:

- `apps/chat_ui/src/missions/index.ts` now exposes typed `advance` and
  `runOnce` client methods for `/missions/{mission_id}/advance` and
  `/missions/run_once`, so the browser can move mission continuity forward
  through the same governed API contracts the backend already exposes.
- `apps/chat_ui/src/App.tsx` now lets the operator advance a selected mission
  once from the ORB mission inspector, with refreshed continuity/task state and
  truthful notices when the mission remains blocked or requires operator review.
- `apps/chat_ui/src/App.tsx` now exposes a bounded `Run mission queue once`
  control inside the ORB mission queue surface, with a compact result summary
  showing which missions moved, which action was applied, and which linked task
  was created or reused.
- `apps/chat_ui/src/App.tsx` now adds direct `Advance once` controls on mission
  queue cards so high-priority continuity work can move forward without
  requiring panel-hopping or manual task hunting.
- `apps/chat_ui/src/missions/index.test.ts` now proves the mission-control
  client preserves the bounded advance and queue-run request/response contracts
  relied on by the new operator controls.

The `2026-04-15` mission approval-handoff productivity slice is now materially
true in the repo and closes another Phase 2 operator-friction gap in the same
governed loop:

- `src/francis/missions/runtime.py` now carries approval handoff fields
  (`approval_id`, `gate`, `next_step`) through mission `advance` and
  `run_queue_once` result envelopes when bounded mission progression lands in a
  governance hold instead of leaving the operator to rediscover that approval by
  re-inspecting mission/task detail.
- `apps/chat_ui/src/missions/index.ts` now preserves those mission-runtime
  approval handoff fields in its typed `advance` and `runOnce` responses.
- `apps/chat_ui/src/App.tsx` now surfaces direct approval-review actions from
  mission advance results and bounded mission queue summaries, so the operator
  can jump straight from continuity advancement to the exact pending approval.
- `tests/test_api_missions.py` now proves that mission advance and mission queue
  execution surface truthful approval handoff when governed execution lands at
  `approvals_gate` rather than requiring another manual lookup.
- `apps/chat_ui/src/missions/index.test.ts` now proves the browser client
  preserves the same approval handoff fields for the new UI actions.

The `2026-04-15` approval-decision continuity handoff slice is now materially
true in the repo and closes a second Phase 2 operator-friction gap on the same
governed path without changing backend law:

- `apps/chat_ui/src/App.tsx` now extracts approval continuity context
  (`mission_id` and linked `task_id` / `operation_id`) from approval payload,
  nested input, and recorded meta when that context is actually present instead
  of forcing the operator to infer mission lineage from raw payload JSON.
- `apps/chat_ui/src/App.tsx` now exposes direct `Open mission flow` and
  `Open linked task` actions inside the approvals panel whenever that context is
  present, so governed review no longer dead-ends the operator in the approval
  queue.
- `apps/chat_ui/src/App.tsx` now preserves return context when the ORB mission
  inspector, mission queue summary, incident feed, or operations composer opens
  a specific approval, and keeps that handoff available after the operator
  approves/rejects/escalates the request instead of requiring panel-hopping and
  manual mission/task rediscovery.

The `2026-04-15` operation-detail mission continuity slice is now materially
true in the repo and closes another `P1_INTERFACE` clarity gap on the same
Phase 2 governed loop without changing backend law:

- `apps/chat_ui/src/App.tsx` now derives mission lineage directly from the
  selected operation record instead of leaving the operator to infer task
  continuity from raw payload JSON.
- `apps/chat_ui/src/App.tsx` now exposes direct `Open mission flow` actions from
  the operation detail controls and governance outcome card whenever the task
  actually carries a linked `mission_id`.
- `apps/chat_ui/src/App.tsx` now renders trace id plus mission/task lineage
  alongside operation detail and audit trail context, tightening the visible
  `plan -> gate -> execute -> trace` path without fabricating memory state.

The `2026-04-15` ORB mission loop actionability slice is now materially true
in the repo and closes another `P1_INTERFACE` explanation gap on the same
Phase 2 governed loop without bypassing backend law:

- `src/francis/api/routes/missions.py` now carries governed `next_step`
  guidance into mission `loop_state` stage receipts whenever the current linked
  operation exposes a concrete next-step handoff through governance metadata.
- `apps/chat_ui/src/missions/index.ts` now preserves that `next_step` field in
  the typed mission loop-stage contract instead of dropping it during client
  parsing.
- `apps/chat_ui/src/App.tsx` now renders mission loop-stage metadata
  (`count`, `gate`, `next_step`) directly inside the ORB mission inspector and
  exposes direct `Review approval` / `Open linked task` actions from the active
  plan-gate-execute loop cards so the operator can move from loop explanation to
  the exact governed object without panel hopping.
- `tests/test_api_missions.py` now proves the mission detail route carries
  truthful `next_step` guidance through blocked mission loop-state receipts.
- `apps/chat_ui/src/missions/index.test.ts` now proves the browser client
  preserves the same `next_step` mission loop-stage field relied on by the ORB
  mission inspector.

The `2026-04-16` industrial intervention-request exact-action approval slice is
now materially true in the repo and continues the same `Phase 2 / P3_GOVERNANCE`
hardening line on a governed industrial mutation surface:

- `src/francis/api/routes/industrial.py` now binds `industrial.intervention.request`
  approvals to the exact requested target/action/risk/domain/actor/params/meta
  payload instead of minting generic approvals that can be replayed after the
  request meaning changed.
- `src/francis/api/routes/industrial.py` now refreshes missing/corrupt or
  mismatched intervention-request approvals into a fresh approval id, writes
  receipt artifacts, preserves `previous_approval_id`, and reuses the same
  intervention request record on replay instead of silently forking request
  lineage.
- `src/francis/api/routes/industrial.py` now marks the existing request record
  `approved` only when a matching approved exact-action receipt exists, instead
  of leaving replay truth ambiguous after approval is granted.
- `tests/test_api_industrial.py` now proves exact-action approval refresh on
  mismatched and missing `industrial.intervention.request` approvals, with
  approved replay completing against the same `intervention_id`.

The `2026-04-16` credential approval-reconciliation slice is now materially
true in the repo and advances the same `Phase 2 / P2_IDENTITY -> P3_GOVERNANCE`
hardening line without inventing secret material or hidden issuance:

- `src/francis/api/routes/credentials.py` now reconciles credential metadata
  against approval decisions so the credential manager stops reporting stale
  `pending` state after the operator approves or rejects a governed request.
- `src/francis/api/routes/credentials.py` now turns approved credential requests
  into truthful `active` metadata references, turns denied requests into `error`,
  and applies approved credential revocations as `revoked` while clearing the
  pending revocation flag instead of leaving approval outcomes disconnected from
  credential state.
- `src/francis/api/routes/credentials.py` now records approval-status and
  status-reconciliation events inside the credential registry so approval
  outcomes remain auditable through the identity surface itself.
- `tests/test_api_credentials.py` now proves that an approved credential request
  materializes as `active` on the next governed read and that an approved
  revocation materializes as `revoked` instead of remaining indefinitely
  `pending`.

The `2026-04-16` credential approval-recovery slice is now also materially true
in the repo and closes the next truthful-identity boundary on that same surface:

- `src/francis/api/routes/credentials.py` now treats missing or corrupt
  approval records as explicit credential-state recovery cases instead of
  leaving the identity surface stranded in fake `pending` posture.
- `src/francis/api/routes/credentials.py` now reconciles broken request
  approvals to `error` and broken revocation approvals back to the prior
  credential state while clearing the pending revocation flag, so approval-file
  loss no longer implies a credential is still awaiting review.
- `tests/test_api_credentials.py` now proves missing request approvals
  reconcile to `error` and missing revocation approvals restore the previous
  credential status instead of leaving stale pending state behind.

The `2026-04-16` credential approval-queue visibility slice is now also
materially true in the repo and tightens ORB governance visibility on the same
identity surface:

- `src/francis/api/routes/credentials.py` now writes approval `request.json`
  artifacts for credential request and revoke actions using the same artifact
  convention as the other governed approval-backed surfaces.
- `src/francis/api/routes/approvals.py` now reads credential approval artifacts
  and surfaces credential-specific payload summary fields (`scope_id`,
  `provider`, `credential_type`, `label`, `credential_id`) through
  `/approvals/list` instead of forcing the operator to inspect raw payload JSON
  or infer credential lineage manually.
- `tests/test_api_approvals.py` now proves pending credential request and
  revoke approvals expose truthful request kinds and credential context in the
  approval queue.

The `2026-04-16` exact-action approval summary slice is now also materially
true in the repo and strengthens approval-queue truthfulness for non-plugin
governed actions:

- `src/francis/api/routes/approvals.py` now unwraps exact-action approval
  envelopes when building `payload_summary`, so industrial and similar governed
  actions surface their real requested action and nested target context instead
  of opaque top-level wrapper keys.
- `src/francis/api/routes/approvals.py` now carries nested exact-action fields
  such as `target_kind`, `target_id`, `domain`, `actor`, `risk`, `dry_run`,
  and `params_keys` into the approval queue summary where present.
- `tests/test_api_approvals.py` now proves pending industrial intervention
  approvals expose truthful exact-action context in `/approvals/list`.

The `2026-04-16` world-state approval projection parity slice is now also
materially true in the repo and closes the next operator-truthfulness gap on
the same `Phase 2 / P3_GOVERNANCE -> P2_IDENTITY` line:

- `src/francis/governance/approval_projection.py` now centralizes approval
  payload summary and artifact-backed enrichment so governed approval surfaces
  stop drifting between route-local and world-state-specific reducers.
- `src/francis/api/routes/approvals.py` and `src/francis/world_state/snapshot.py`
  now read the same projection path, so `/system/world_state` preserves the
  existing pending-approval shape while adding the same bounded request kind,
  credential context, and exact-action target/risk fields already surfaced in
  `/approvals/list`.
- `tests/test_api_system_settings.py` now proves world-state pending approvals
  expose artifact-backed plugin request kinds and industrial exact-action
  context instead of falling back to the older plugin-only summary logic.

## 4. Latest validation evidence

Latest live validation for the `2026-04-21` Stage 2 Observer transition check:

- `POST /system/observer/scan` through the local FastAPI app with actor
  `codex.stage2.observer` and reason `stage_2_readiness_live_verification`
  Result: `ok=true`, `decision=urgent_review`, readiness `ready`, `5/5`
  criteria satisfied.
- Receipt `obs_scan_1776798650837_20306fb7`
  Result: `status=attention`, `trace_id=trace_46d47c3517ff5bea`,
  `run_id=run_1776798650_ab604268`, `incident_count=3`, anomaly score `100`
  with level `critical`.
- Readback checks:
  Result: `/system/observer`, `/system/observer/audit`, and
  `/continuity/briefing` all surfaced the same latest receipt id; continuity
  briefing reported observer readiness `ready`.
- Criterion statuses:
  Result: evidence-backed incidents, traceable scans, receipted findings,
  presence truth link, and non-invasive awareness all reported `satisfied`.

Latest targeted validation for the `2026-04-22` Stage 3 approval-aware mission re-entry slice:

- `.\scripts\check.ps1`
  Result: `passed`
- `cd apps/chat_ui && npm test -- --test-name-pattern="SettingsClient"`
  Result: `16 passed`
- `cd apps/chat_ui && npm test`
  Result: `16 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-22` Stage 3 Shift Briefing dependency rendering slice:

- `.\scripts\check.ps1`
  Result: `passed`
- `cd apps/chat_ui && npm test -- --test-name-pattern="SettingsClient|MissionsClient"`
  Result: `16 passed`
- `cd apps/chat_ui && npm test`
  Result: `16 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-22` Stage 3 dependency blocker briefing slice:

- `.\scripts\check.ps1`
  Result: `passed`
- `python -m pytest tests/test_api_continuity.py -q`
  Result: `7 passed`
- `python -m ruff check src/francis/world_state/snapshot.py tests/test_api_continuity.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `cd apps/chat_ui && npm test -- --test-name-pattern="SettingsClient"`
  Result: `16 passed`
- `cd apps/chat_ui && npm test`
  Result: `16 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-22` Stage 3 dependency-aware mission queue slice:

- `.\scripts\check.ps1`
  Result: `passed`
- `python -m pytest tests/test_mission_store.py tests/test_api_missions.py -q`
  Result: `passed`
- `python -m ruff check src/francis/missions/store.py tests/test_mission_store.py tests/test_api_missions.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `cd apps/chat_ui && npm test -- --test-name-pattern="MissionsClient|SettingsClient"`
  Result: `16 passed`
- `cd apps/chat_ui && npm test`
  Result: `16 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-21` Stage 3 mission context contract slice:

- `.\scripts\check.ps1`
  Result: `passed`
- `python -m pytest tests/test_mission_store.py tests/test_api_missions.py -q`
  Result: `passed`
- `python -m ruff check src/francis/missions/store.py src/francis/api/routes/missions.py src/francis/world_state/snapshot.py tests/test_mission_store.py tests/test_api_missions.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `cd apps/chat_ui && npm test -- --test-name-pattern="MissionsClient|SettingsClient"`
  Result: `16 passed`
- `cd apps/chat_ui && npm test`
  Result: `16 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-21` Stage 3 mission readiness slice:

- `.\scripts\check.ps1`
  Result: `passed`
- `python -m pytest tests/test_api_continuity.py -q`
  Result: `6 passed`
- `python -m ruff check src/francis/world_state/snapshot.py tests/test_api_continuity.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `cd apps/chat_ui && npm test -- --test-name-pattern="SettingsClient"`
  Result: `16 passed`
- `cd apps/chat_ui && npm test`
  Result: `16 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-21` Stage 3 mission queue-run handoff slice:

- `.\scripts\check.ps1`
  Result: `passed`
- `python -m pytest tests/test_api_missions.py -q`
  Result: `passed`
- `python -m ruff check src/francis/api/routes/missions.py tests/test_api_missions.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `cd apps/chat_ui && npm test -- --test-name-pattern="MissionsClient"`
  Result: `16 passed`
- `cd apps/chat_ui && npm test`
  Result: `16 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-21` Stage 3 post-action mission continuity slice:

- `.\scripts\check.ps1`
  Result: `passed`
- `python -m pytest tests/test_api_missions.py tests/test_mission_store.py -q`
  Result: `17 passed`
- `python -m ruff check src/francis/api/routes/missions.py tests/test_api_missions.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `cd apps/chat_ui && npm test -- --test-name-pattern="MissionsClient"`
  Result: `16 passed`
- `cd apps/chat_ui && npm test`
  Result: `16 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-21` observer readiness checklist slice:

- `.\scripts\check.ps1`
  Result: `passed`
- `python -m pytest tests/test_api_system_settings.py::test_system_observer_scan_is_receipted_and_read_paths_remain_passive tests/test_api_continuity.py::test_continuity_briefing_reports_idle_operator_start_state tests/test_api_continuity.py::test_continuity_briefing_surfaces_handoff_and_recent_completion -q`
  Result: `3 passed`
- `python -m ruff check src/francis/world_state/snapshot.py src/francis/api/routes/system.py src/francis/api/routes/continuity.py tests/test_api_system_settings.py tests/test_api_continuity.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `cd apps/chat_ui && npm test -- --test-name-pattern="SettingsClient"`
  Result: `16 passed`
- `cd apps/chat_ui && npm test`
  Result: `16 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-21` observer timestamp lineage slice:

- `.\scripts\check.ps1`
  Result: `passed`
- `python -m ruff check src/francis/world_state/snapshot.py src/francis/api/routes/system.py src/francis/api/routes/continuity.py tests/test_api_system_settings.py tests/test_api_continuity.py`
  Result: `passed`
- `python -m pytest tests/test_api_system_settings.py::test_system_read_aliases_match_primary_routes tests/test_api_system_settings.py::test_system_world_state_reports_governance_backlog_states tests/test_api_system_settings.py::test_system_observer_scan_is_receipted_and_read_paths_remain_passive tests/test_api_continuity.py::test_continuity_briefing_aliases_match_primary_route tests/test_api_continuity.py::test_continuity_briefing_reports_idle_operator_start_state tests/test_api_continuity.py::test_continuity_briefing_surfaces_handoff_and_recent_completion -q`
  Result: `6 passed`
- `git diff --check`
  Result: `passed`
- `cd apps/chat_ui && npm test -- --test-name-pattern="SettingsClient"`
  Result: `16 passed`
- `cd apps/chat_ui && npm test`
  Result: `16 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`

The following validations were run against the current working tree on
`2026-04-16` and `2026-04-17`:

- `pwsh -NoProfile -File scripts/watch-francis-live.ps1 -Once -NoClear`
  Result: `passed`
- `pwsh -NoProfile -File scripts/tail-francis-events.ps1 -Mode all -Lines 8 -NoClear`
  Result: `passed`
- `pwsh -NoProfile -File scripts/tail-francis-events.ps1 -Mode session -Lines 10 -NoClear`
  Result: `passed`
- `pwsh -NoProfile -File C:\Users\Ap3pp\.codex\automations\francis-thread-builder\watch-thread.ps1 -DryRun -Once`
  Result: `passed`
- `pytest tests/test_api_operations.py -q -rA`
  Result: `14 passed`
- `git diff --check -- scripts/francis-observer-lib.ps1 scripts/watch-francis-live.ps1 scripts/tail-francis-events.ps1`
  Result: `passed`

- `pytest tests/test_api_system_settings.py tests/test_api_approvals.py --disable-warnings`
  Result: `22 passed in 10.37s`

- `pytest tests/test_api_operations.py tests/test_api_supervised_exec.py tests/test_paths_data_dir.py -q`
  Result: `16 passed`
- `git diff --check -- src/francis/agent/supervised_exec.py tests/test_api_operations.py tests/test_api_supervised_exec.py`
  Result: `passed`
- `pytest tests/test_api_plugins.py tests/test_api_operations.py --disable-warnings`
  Result: `19 passed in 17.29s`
- `git diff --check -- src/francis/api/routes/plugins.py tests/test_api_plugins.py tests/test_api_operations.py`
  Result: `passed`
- `pytest tests/test_api_web_learning.py --disable-warnings`
  Result: `7 passed in 2.87s`
- `git diff --check -- src/francis/api/routes/web_learning.py tests/test_api_web_learning.py`
  Result: `passed` (Git emitted a line-ending warning only)
- `pytest tests/test_api_operations.py tests/test_llm_client.py tests/test_settings.py`
  Result: `15 passed in 6.71s`
- `git diff --check -- src/francis/agent/git_push.py src/francis/agent/executor.py src/francis/api/routes/operations.py src/francis/operations/runtime.py src/francis/llm/client.py src/francis/settings.py tests/test_api_operations.py tests/test_llm_client.py tests/test_settings.py`
  Result: `passed`
- `cd apps/chat_ui && npm test`
  Result: `13 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `pytest tests/test_api_missions.py tests/test_api_operations.py --disable-warnings`
  Result: `24 passed in 13.75s`
- `pytest tests/test_api_missions.py --disable-warnings`
  Result: `15 passed in 20.03s`
- `pytest tests/test_api_missions.py --disable-warnings`
  Result: `15 passed in 8.53s`
- `cd apps/chat_ui && npm test`
  Result: `13 passed`
- `cd apps/chat_ui && npm test`
  Result: `14 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `git diff --check -- apps/chat_ui/src/App.tsx docs/operations/COMPLETION_LEDGER.md`
  Result: `passed`
- `git diff --check -- src/francis/api/routes/missions.py apps/chat_ui/src/missions/index.ts apps/chat_ui/src/missions/index.test.ts apps/chat_ui/src/App.tsx tests/test_api_missions.py`
  Result: `passed`
- `pytest tests/test_api_industrial.py --disable-warnings`
  Result: `10 passed in 4.05s`
- `git diff --check -- src/francis/api/routes/industrial.py tests/test_api_industrial.py`
  Result: `passed` (Git emitted a line-ending warning only)
- `pytest tests/test_api_credentials.py --disable-warnings`
  Result: `4 passed in 1.85s`
- `pytest tests/test_api_credentials.py --disable-warnings`
  Result: `6 passed in 2.37s`
- `pytest tests/test_api_approvals.py tests/test_api_credentials.py --disable-warnings`
  Result: `9 passed in 9.03s`
- `pytest tests/test_api_approvals.py --disable-warnings`
  Result: `4 passed in 2.68s`
- `git diff --check -- src/francis/api/routes/credentials.py tests/test_api_credentials.py`
  Result: `passed`

Those validations specifically cover:

- live dashboard rendering against the real watcher pid/state/log files
- real thread/session resolution through the pinned session jsonl path
- exact-session lock bootstrap through watcher-side `watch-session.txt`, with
  `session_lock_source: pin_file` and the exact pinned jsonl path surfaced in
  both the observer and watcher state
- explicit reporting of a dead watcher process even when stale state/log receipts
  still exist on disk
- live repo branch/commit/dirty-state reporting from `C:\Francis`
- recent session-event visibility, including observer commands and the targeted
  repo `pytest` run
- real build/test status projection from session command exit codes, including a
  confirmed `test_status: passed` after the targeted `pytest` invocation

- governed `git.push` capability registration through the operations runtime
- approval-bound local Git push execution
- approval refresh when the approved remote payload becomes stale before execution
- approval refresh when supervised-exec approval records disappear or the approved
  command payload drifts before execution
- approval refresh when plugin approval records disappear or the approved
  plugin action/input payload drifts before execution
- approval refresh when web-learning enable approvals drift from the exact
  requested actor/meta payload before the control mutation is applied
- approval refresh when web-learning quarantine-delete approval records
  disappear before the destructive mutation is retried
- approval refresh when `web_learning.request` approvals drift from the exact
  requested ingest payload or disappear before the approved learn request is
  replayed
- operator-visible operations detail preserving the refreshed plugin approval id
  and `approvals_gate` posture after the held task is requeued
- operator-visible operations detail preserving the refreshed supervised-exec
  approval id and `approvals_gate` posture after the hold is requeued
- canonical `FRANCIS_*` settings alias resolution and Ollama client fallback order
- mission list/create client behavior for the operator-console ingress path
- operation-create client behavior for mission-linked governed requests
- mission-advance client behavior for bounded ORB progression
- mission-queue run client behavior for bounded backlog advancement
- mission-runtime approval handoff for bounded mission advance and queue
  progression when governed execution yields a pending approval
- operation-detail mission continuity visibility from task inspection back to
  the linked mission flow
- mission loop-state `next_step` continuity for governed holds and queued
  linked operations
- ORB mission loop cards exposing direct approval/task actions from the visible
  loop state itself
- mission loop-stage receipt recency for the latest trace and continuity
  movement directly inside the ORB mission inspector
- world-state mission latest-activity receipts surviving browser parsing and
  showing up on the ORB mission progress and mission queue cards before the
  operator opens a full mission detail view
- live observer visibility for background GitHub-sync state, including raw push
  watcher tails and truthful ahead/behind/dirty reporting in the same surface
  as continuation/build state
- chat UI production build integrity after adding the governed request composer
- chat UI production build integrity after adding bounded mission advance and
  queue-run controls
- backend mission and operation contracts relied on by the new UI ingress flow
- approval refresh when `industrial.intervention.request` approvals drift from
  the exact requested target/action payload or disappear before the same request
  is replayed
- intervention-request lineage reusing the same governed request record after
  approval refresh instead of minting duplicate request state
- credential-request approval outcomes reconciling from governed approval
  decisions into truthful `active` or `error` metadata state
- credential-revocation approval outcomes reconciling from governed approval
  decisions into truthful `revoked` state instead of remaining indefinitely
  pending in the identity surface
- missing credential-request approvals no longer leaving dead `pending`
  credential references in the identity surface
- missing credential-revocation approvals no longer leaving live credentials
  stranded in fake pending-revocation state
- pending credential approvals now surfacing artifact-backed request context in
  the approval queue instead of remaining second-class relative to plugin,
  web-learning, and industrial approvals
- pending industrial approvals now surfacing nested exact-action context in the
  approval queue instead of opaque wrapper payload keys
- `/system/world_state` pending approvals now sharing the same artifact-backed
  request kind and exact-action summary contract as `/approvals/list` instead
  of regressing to a plugin-only payload reducer
- `pytest tests/test_api_missions.py -q`
  Result: `passed`
- `cd apps/chat_ui && npm test -- missions/index.test.ts`
  Result: `15 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `cd apps/chat_ui && npm test -- settings/index.test.ts`
  Result: `15 passed`
- `pwsh -NoProfile -File scripts/watch-francis-live.ps1 -Once -NoClear`
  Result: `passed`
- `pwsh -NoProfile -File scripts/tail-francis-events.ps1 -Mode push-state -NoClear`
  Result: `passed`

Earlier validation evidence from `2026-04-14` remains relevant for the continuity
bridge slice:

- `pytest tests/test_api_continuity.py tests/test_api_contract_chat_ui.py tests/test_api_operations.py tests/test_api_system_settings.py -q`
  Result: `28 passed`
- `cd apps/chat_ui && npm test`
  Result: `8 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-18` observer scan receipt slice:

- `python -m pytest tests/test_api_system_settings.py -q`
  Result: `19 passed`
- `python -m ruff check src/francis/api/routes/system.py tests/test_api_system_settings.py`
  Result: `passed`
- `python -m ruff format src/francis/api/routes/system.py tests/test_api_system_settings.py`
  Result: `1 file reformatted, 1 file left unchanged`

Latest targeted validation for the `2026-04-18` observer continuity decisions-log slice:

- `python -m pytest tests/test_api_continuity.py tests/test_api_system_settings.py -q`
  Result: `24 passed`
- `python -m ruff check src/francis/world_state/snapshot.py src/francis/api/routes/system.py src/francis/api/routes/continuity.py tests/test_api_continuity.py tests/test_api_system_settings.py`
  Result: `passed`
- `python -m ruff format src/francis/world_state/snapshot.py src/francis/api/routes/system.py src/francis/api/routes/continuity.py tests/test_api_continuity.py`
  Result: `1 file reformatted, 3 files left unchanged`
- `cd apps/chat_ui && npm test`
  Result: `15 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-18` operator-triggered observer scan slice:

- `python -m pytest tests/test_api_contract_chat_ui.py -q`
  Result: `1 passed`
- `python -m ruff check tests/test_api_contract_chat_ui.py`
  Result: `passed`
- `cd apps/chat_ui && npm test`
  Result: `15 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-18` observer continuity bridge:

- `python -m pytest tests/test_api_continuity.py tests/test_api_system_settings.py -q`
  Result: `24 passed`
- `python -m ruff check src/francis/world_state/snapshot.py src/francis/api/routes/continuity.py src/francis/api/routes/system.py tests/test_api_continuity.py tests/test_api_system_settings.py`
  Result: `passed`
- `cd apps/chat_ui && npm test`
  Result: `15 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-19` observer anomaly scoring slice:

- `python -m pytest tests/test_api_system_settings.py tests/test_api_continuity.py -q`
  Result: `24 passed`
- `python -m ruff check src/francis/world_state/snapshot.py src/francis/api/routes/system.py src/francis/api/routes/continuity.py tests/test_api_system_settings.py tests/test_api_continuity.py`
  Result: `passed`
- `cd apps/chat_ui && npm test`
  Result: `15 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-19` observer truth-state link into ORB presence slice:

- `python -m pytest tests/test_api_system_settings.py tests/unit/test_kernel_contracts.py -q`
  Result: `26 passed`
- `python -m ruff check src/francis/world_state/orb.py tests/test_api_system_settings.py tests/unit/test_kernel_contracts.py`
  Result: `passed`
- `cd apps/chat_ui && npm test`
  Result: `15 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-19` observer probe-visibility slice:

- `python -m pytest tests/test_api_system_settings.py tests/test_api_continuity.py -q`
  Result: `24 passed`
- `python -m ruff check src/francis/world_state/snapshot.py src/francis/api/routes/system.py src/francis/api/routes/continuity.py tests/test_api_system_settings.py tests/test_api_continuity.py`
  Result: `passed`
- `cd apps/chat_ui && npm test`
  Result: `15 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-19` observer receipt probe-status slice:

- `python -m ruff format src/francis/world_state/snapshot.py src/francis/api/routes/system.py tests/test_api_system_settings.py tests/test_api_continuity.py`
  Result: `2 files reformatted, 2 files left unchanged`
- `python -m ruff check src/francis/world_state/snapshot.py src/francis/api/routes/system.py tests/test_api_system_settings.py tests/test_api_continuity.py`
  Result: `passed`
- `python -m pytest tests/test_api_system_settings.py tests/test_api_continuity.py -q`
  Result: `24 passed`
- `cd apps/chat_ui && npm test`
  Result: `15 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-19` observer receipt lineage slice:

- `python -m ruff check src/francis/api/routes/system.py tests/test_api_system_settings.py tests/test_api_continuity.py`
  Result: `passed`
- `python -m pytest tests/test_api_system_settings.py tests/test_api_continuity.py -q`
  Result: `24 passed`
- `cd apps/chat_ui && npm test`
  Result: `15 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-19` observer audit-log surface slice:

- `cd apps/chat_ui && npm test`
  Result: `16 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-19` observer audit-route contract slice:

- `python -m pytest tests/test_api_contract_chat_ui.py -q`
  Result: `1 passed`

Those validations specifically cover:

- continuity ledger route tail behavior
- continuity briefing alias parity
- system read alias parity
- system mutation alias parity
- operations run and worker-pump routes
- chat UI continuity ledger client parsing and bounded limit requests
- chat UI worker-cycle client control and existing operation-run control
- chat UI endpoint fallback order and defensive parsing
- sparse continuity briefing retention when handoff payloads omit headline/focus
- chat UI production build integrity after surfacing embedded continuity operator/orb state and raw continuity ledger receipts

## 5. Known truthful gaps

These remain true and should block any "finished" claim:

- the operator experience is not yet a complete ORB console in `P1_INTERFACE`
- the full plan -> gate -> execute -> trace -> memory loop is not yet clearly
  exposed end-to-end in the chat UI
- memory and continuity are materially present but still partial as operator-facing,
  retrieval-backed systems
- evidence, simulation, and federation remain downstream/gated work, not current
  product-ready surfaces

## 6. Update rule

Update this ledger only when at least one of the following is true:

- a validated surface materially changed
- a plane posture changed in a way that is now directly inspectable
- a major blocker was removed
- the latest evidence set changed and should replace stale validation claims
