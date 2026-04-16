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

## 3. High-confidence current slice

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

## 4. Latest validation evidence

The following validations were run against the current working tree on
`2026-04-15`:

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

Those validations specifically cover:

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
- chat UI production build integrity after adding the governed request composer
- chat UI production build integrity after adding bounded mission advance and
  queue-run controls
- backend mission and operation contracts relied on by the new UI ingress flow
- approval refresh when `industrial.intervention.request` approvals drift from
  the exact requested target/action payload or disappear before the same request
  is replayed
- intervention-request lineage reusing the same governed request record after
  approval refresh instead of minting duplicate request state

Earlier validation evidence from `2026-04-14` remains relevant for the continuity
bridge slice:

- `pytest tests/test_api_continuity.py tests/test_api_contract_chat_ui.py tests/test_api_operations.py tests/test_api_system_settings.py -q`
  Result: `28 passed`
- `cd apps/chat_ui && npm test`
  Result: `8 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`

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
