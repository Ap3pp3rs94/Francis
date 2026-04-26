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

As of `2026-04-25`, credential request metadata has a bounded secret-redaction
contract at the identity/governance boundary. Sensitive metadata keys and
secret-like string values are redacted before credential request data reaches
approval records, approval artifacts, credential registry state, or credential
list responses, while non-sensitive audit context such as ticket ids remains
inspectable. `tests/test_api_credentials.py` proves raw OpenAI-key-like,
GitHub-token-like, and password-like values do not appear in those surfaces.

As of `2026-04-25`, credential request and revoke free-text reasons share that
redaction posture across identity/governance receipt surfaces. Approval records,
approval artifacts, credential metadata, credential registry events, and
delegation/list projections preserve operator context while replacing
secret-like password, token, key, and credential strings before persistence or
return.

As of `2026-04-26`, credential request and revoke receipts can carry explicit
actor identity instead of relying on a fixed API actor. The actor is redacted
through the same secret filter as credential reasons, then preserved in
approval payloads, approval artifacts, credential list projections, registry
events, delegation projections, and revocation metadata. This is receipt
identity only; it does not mint credentials, bypass approvals, or change
approval decision behavior.

As of `2026-04-26`, the API permission gate module has a default-deny
identity/scope decision contract. `ApiPermissionGate.check` denies missing actor
identity, invalid or empty required scopes, missing actor scopes, and missing
resolved scopes with bounded count-only evidence, while allowing only when
resolved actor scopes satisfy the requested gate scopes. `ScopeChecker` now
returns the same count-only decision evidence for direct scope checks. This is a
reusable gate contract; privileged routes still need explicit integration before
claiming API-wide permission enforcement.

As of `2026-04-26`, the direct supervised-exec API side-effect route is wired to
that permission gate. `POST /operations/supervised-exec/run` now denies before
creating an approval request unless the request actor is present in the
server-side `FRANCIS_API_ACTOR_SCOPES` policy with the `codex.supervised_exec`
scope. When allowed by that policy, the existing exact-action approval and
artifact behavior remains unchanged. This applies to the direct supervised-exec
API route only; mission-linked and operation-run paths remain governed by their
existing approval/execution flow.

As of `2026-04-26`, domain registry write routes are also wired to the API
permission gate. `POST /domains/create`, `PATCH /domains/update`, and
`POST /domains/delete` now deny before mutating local domain registry state unless
the request actor is present in the server-side `FRANCIS_API_ACTOR_SCOPES`
policy with the `domains.write` scope. Domain read/list/summary routes remain
read-only. This is another narrow route integration, not a claim of API-wide
permission enforcement.

As of `2026-04-25`, the same metadata redaction contract is shared by governed
approval-backed plugin, industrial intervention, and web-learning request
surfaces. `src/francis/governance/redaction.py` now owns the reusable redaction
rules, and focused API tests prove sensitive metadata is removed from approval
records, approval artifacts, and relevant local registries while non-sensitive
audit fields remain available.

As of `2026-04-25`, the shared redaction contract recognizes additional common
token families in free text and approval-bound values, including OpenAI
project-style keys, GitHub fine-grained PATs, GitLab PATs, Slack tokens, Google
API keys, AWS access keys, and JWT-shaped strings. Unit tests prove those values
are redacted from display text and sealed when used in exact-action approval
payloads.

As of `2026-04-25`, governed exact-action approval payloads can seal
secret-like action values without dropping exact-match protection. Plugin run
inputs, industrial intervention params, and web-learning request payload fields
replace inline secret-like values with redacted HMAC-backed sealed values before
approval records or artifacts are written. Replays with different secret values
still produce `approval_payload_mismatch` instead of reusing the prior approval.

As of `2026-04-25`, plugin execution responses redact secret-like receipt output
before returning it to API callers. The plugin handler still receives the raw
approved input for execution, but returned `output`, `receipt.output`, and
`receipt.sandbox.output` are normalized through the governed redaction contract,
so generated echo-style plugin responses do not turn approved secret-bearing
inputs into operator-facing secret replay.

As of `2026-04-25`, web-learning runtime records redact secret-like request
surface values before persisting or returning them through registry-backed
requests, records, events, lists, and exports. Raw URLs, titles, summaries,
actors, sources, and reasons are still used for policy checks and exact approval
matching, but operator-facing runtime state stores the governed redacted values
so approved learn requests do not replay inline tokens or passwords.

As of `2026-04-25`, industrial safety, intervention, and digital-twin runtime
records separate exact approval payloads from operator-facing registry state.
Approval requests still receive HMAC-sealed params for replay mismatch
protection, while `safety_validations`, `interventions`, and
`digital_twin_actions` persist redacted params without raw secrets or approval
digests in the runtime registry.

As of `2026-04-25`, approval request reasons and decision comments have a shared
free-text secret redaction contract at the approval store boundary. Approval
records, approval list responses, and approved/rejected/emergency decision files
preserve non-sensitive operator context while replacing secret-like password,
token, key, and credential strings before persistence.

As of `2026-04-25`, trust history and operator control-mode reason fields share
the same free-text secret redaction posture. Trust adjust events written through
the API or tracker and persisted control-mode overrides keep operator context
while replacing secret-like passwords, tokens, and keys before those values reach
history files, runtime state files, or system/operator-mode responses.

As of `2026-04-25`, mission recovery receipts and system mutation context share
that redaction posture. Mission deadletter reasons, mission history notes,
linked-task status reasons, feature flag descriptions/meta, observer scan
reasons/meta, service-action unknown target names, and runtime-setting mutation
response metadata preserve non-sensitive audit context while replacing
secret-like passwords, tokens, keys, and secrets before those values reach
operator-facing receipts or local runtime files.

As of `2026-04-25`, operation and delegation surfaces redact operator-facing
context without removing raw action inputs needed for local execution. Delegation
objectives, status reasons, audit details, operation projections, operation
logs, raw task metadata returned by the API, patch notes/meta, and export/list
responses replace secret-like free text before returning to callers. Action
inputs remain available in local task storage for execution, but API projections
return redacted views.

As of `2026-04-26`, delegation creation audit receipts preserve bounded request
context without recording input values. Created task audit entries now include
requester id, priority, ttl, mission id when already present, and input key
count, while continuing to redact audit details through the operation redaction
boundary. This improves traceability for the plan/delegation entry point without
changing task routing, execution, approval, or memory behavior.

As of `2026-04-25`, lower-level telemetry audit, operation log, and error log
writers apply the same governed redaction boundary. Telemetry fields and trace
context are coerced into JSON-safe values and secret-like passwords, tokens,
keys, and secrets are redacted before `audit.jsonl`, `francis.jsonl`, or
`errors.jsonl` are written or before `telemetry.audit.record` returns its
receipt payload.

As of `2026-04-25`, memory timeline writes, reads, and exports share the
governed secret-redaction boundary. `POST /memory/timeline/record` normalizes
free text, tags, payloads, artifacts, and metadata before persistence, while
`/memory/timeline/get`, `/memory/timeline/list`, and
`/memory/timeline/export` return the same redacted event shape without dropping
non-sensitive audit context. Timeline projections also expose explicit
`provenance` and `retention` hints when those fields are backed by event fields
or metadata, and the chat UI memory timeline client preserves that context
without inventing memory truth. Timeline events can also carry bounded
mission/operation/trace references and can be filtered by `mission_id`,
`operation_id`, or `trace_id`, giving existing operator surfaces a contract for
opening memory evidence only when backed by real ids. `tests/test_api_memory_timeline.py`
proves raw OpenAI-key-like, GitHub-token-like, and HTTPS userinfo secret values
do not appear in the local timeline registry or API/export payloads, while
`apps/chat_ui/src/memory_timeline/index.test.ts` proves the browser client keeps
the returned provenance, retention, and reference contract.

As of `2026-04-25`, memory timeline retrieval can also filter by receipt
`run_id` and `artifact_dir`. The API already preserved those references on
timeline events; the list/export routes and chat UI memory timeline client now
carry the same run and artifact filters, and the memory-evidence helper can
build bounded run/artifact receipt queries without including payloads.

As of `2026-04-26`, memory timeline retrieval can also filter terminal
operation receipts by `operation_status`. The API promotes the existing
receipt-backed status from event metadata onto public timeline events,
`/memory/timeline/list` and `/memory/timeline/export` accept an
`operation_status` filter, CSV exports include the same field, and the chat UI
memory timeline client can request and preserve it without inspecting raw
payloads.

As of `2026-04-26`, the operation memory-evidence interface can carry that
terminal status into bounded timeline lookups. The evidence query helper accepts
real operation status candidates from the selected mission task and selected
operation, adds `operation_status=succeeded|failed` only when one of those
statuses is terminal, and avoids broad status-only searches or non-terminal
status as memory truth.

As of `2026-04-25`, the operations detail surface can use that memory timeline
contract from the mission loop bridge. When a selected operation exposes a real
mission id, linked operation id, or trace id, the chat UI can issue bounded
`/memory/timeline/list` lookups for those exact ids, de-duplicate returned
events, and render only receipt-backed memory timeline entries. The UI does not
invent memory status when the timeline route returns no entries or is
unavailable.

As of `2026-04-25`, the selected operation memory-evidence lookup also carries
real execution receipt handles into the same bounded timeline path. When the
operation detail exposes a `run_id` or `artifact_dir`, the chat UI includes
those exact filters alongside mission, operation, and trace filters instead of
leaving run/artifact-backed continuity receipts unreachable from the operation
surface.

As of `2026-04-25`, those operations memory-evidence query rules are covered by
a direct UI contract helper. The chat UI builds only mission, linked-task or
fallback-task, and trace filters from real ids, keeps payloads out of the bounded
timeline list requests, de-duplicates returned events by id, and sorts newest
receipt-backed evidence first before rendering it.

As of `2026-04-26`, explanation and audit records can preserve and filter by
receipt handles across `trace_id`, `run_id`, and `artifact_dir`.
`/explanations/list` and `/explanations/export` accept bounded receipt filters,
summaries/detail/export payloads retain the same handles, CSV exports include
the artifact handle column, and the chat UI explanation explorer client
preserves the same linkage across list, get, and export calls. This gives
trace/run/artifact-bearing mission and operation receipts another read path
without adding execution or synthetic trace state.

As of `2026-04-26`, the selected operation detail surface can use that
explanation receipt contract from real operation and mission loop handles. The
chat UI now builds bounded `/explanations/list` queries for the selected
trace/run/artifact handles, de-duplicates returned audit/explanation records,
and renders only backend-returned records when the operator manually loads them.
It does not invent explanation status when no receipt handles or records exist.

As of `2026-04-26`, operations list and export routes can also filter by real
execution receipt handles. `/operations/list` and `/operations/export` accept
`trace_id`, `run_id`, and `artifact_dir` filters, JSON export keeps the same
operation projection, CSV export includes those receipt handle columns, and the
chat UI operations client can request the same filters without inventing
receipt state. This makes execution -> trace/artifact inspection reachable from
operations read models without changing worker execution or approvals.

As of `2026-04-26`, `plan.create` operation results include a bounded plan
receipt summary alongside the existing full plan payload. Completed plan-create
operations now return the real plan status, current in-progress step id/title,
step count, and checkpoint count from the generated `PlanStateMachine` state,
so the cognition step can be inspected from operation output without parsing the
entire plan object.

As of `2026-04-26`, untraced capability execution results also receive bounded
task execution trace/run handles. `plan.create` now returns `trace_id` and
`run_id` from the persisted task result, so `/operations/list` can filter the
completed cognition step by its real execution handles. Capability results that
already expose their own trace/run receipts, such as plugin execution, keep their
existing receipt-provided handles. No scheduling, approval, operation status
mapping, or memory-write behavior is changed.

As of `2026-04-26`, completed task audit events also carry the real execution
receipt handles when they exist. The final `status_updated` task audit entry now
records `trace_id`, `run_id`, and `artifact_dir` from the result payload, and
operation log projections expose those handles as first-class log fields while
preserving the same details inside `output`/`meta`. This makes the operation
audit trail line up with the operation result trace without changing execution,
approval, scheduling, or memory-write behavior.

As of `2026-04-26`, world-state mission activity projections preserve those
operation-log receipt handles. Mission `latest_activity` now carries real
`trace_id`, `run_id`, and `artifact_dir` values from the selected run-ledger log
or operation state, and the derived `current_task` projection keeps the same
handles for chat UI settings/world-state clients. This is a read-model/interface
handoff only; it does not create traces, mutate missions, or write memory.

As of `2026-04-26`, the chat UI operations client preserves bounded
`plan.create` receipt summaries as typed operation data. When backend operation
output includes the real plan status, current step id/title, step count, and
checkpoint count, the client exposes those fields as `plan_summary` while
leaving the raw output intact. This is a parser/interface contract only; it does
not add UI claims, create plans, execute work, or write memory.

As of `2026-04-26`, the chat UI Operation Detail view consumes that typed
`plan_summary` contract as a read-only plan receipt block. Selected operations
that carry backend-provided plan status, current step id/title, step count, or
checkpoint count render those fields alongside existing trace/run/artifact
handles while leaving the raw input/output payload visible. Operations without a
real plan summary render no synthetic plan receipt.

As of `2026-04-26`, mission loop plan stages can carry that same bounded
`plan.create` receipt summary from the current linked operation. When the linked
operation output contains real plan status, current step id/title, step count,
or checkpoint count, `/missions/{mission_id}` includes those fields on
`loop_state.plan`, and the chat UI missions client preserves them as typed loop
stage data. This does not create or advance plans; it only connects existing
operation receipt truth to the mission loop read model.

As of `2026-04-26`, mission loop stage cards render that plan receipt handoff
when it exists. The selected mission inspector and linked-operation mission
bridge show backend-provided plan status, current step id/title, step count, and
checkpoint count from `loop_state.plan`; stages without those fields render no
plan receipt line. This is read-only interface exposure, not a new planning or
execution behavior.

As of `2026-04-26`, approval queue projections can expose the real held
mission/operation loop handles for approval-gated work. Approval list items now
derive `mission_id`, `operation_id`, `operation_status`,
`operation_result_status`, `gate`, `next_step`, `trace_id`, `run_id`, and
`artifact_dir` from existing task records that already reference the approval id;
no approval decision behavior, exact-action matching, or execution path is
changed. The chat UI approval client, world-state parser, approval panel, and
pending-approvals cards preserve and render those handles so an operator can move
from gate review back to the linked mission/task without raw JSON inspection.

As of `2026-04-26`, world-state governance incident evidence now preserves the
same approval-gate loop handles for pending approvals. The
`governance.pending_approvals` and `governance.awaiting_approval` incident
evidence items carry `approval_id`, `mission_id`, `operation_id`, `gate`,
`next_step`, `trace_id`, `run_id`, and `artifact_dir` when those values already
exist in the pending approval projection. No approval decision behavior,
execution path, policy rule, or memory-write path is changed.

As of `2026-04-26`, chat mission ingress continuity entries preserve bounded ORB
loop metadata for newly declared missions. The assistant ledger entry written by
`POST /chat/send` or websocket mission ingress now carries the real mission id,
ingress plane, active loop stage, handoff stage/action/next step, current-task
source/next step, and receipt counts from the mission detail projection. The
conversation ledger still redacts the operator objective before persistence and
does not add execution, approval, or memory-timeline writes.

As of `2026-04-26`, memory timeline public events project bounded ORB loop
metadata from continuity ledger entries. Chat-declared missions can now be found
through `/memory/timeline/list?mission_id=...` and expose a structured `loop`
object with ingress plane, active stage, handoff stage/action/next step,
current-task source/next step, and receipt counts when those values are already
present in redacted ledger metadata. This is a read-model projection only; no
execution, approval, policy, or memory-write behavior is changed.

As of `2026-04-26`, memory timeline loop projections also preserve real
`run_id` and `artifact_dir` handles from mission-loop continuity metadata. The
backend includes those handles in the structured `loop` object for
mission-loop receipts, and the chat UI memory timeline client now preserves the
typed loop projection instead of dropping it during parsing. This keeps memory
evidence aligned with the same run/artifact handles exposed by mission and
operation loop surfaces without adding new execution or inspection behavior.

As of `2026-04-26`, memory timeline loop projections also preserve approval
posture when mission-loop continuity metadata already includes it. The backend
structured `loop` object now keeps handoff and current-task approval ids and
statuses, and the chat UI memory timeline client preserves those typed fields
instead of reducing gate evidence to adjacent receipt ids. This is still a
read-model/client contract change only; it does not create approvals, alter
policy decisions, or advance mission execution.

As of `2026-04-26`, terminal mission-linked operation receipts can now feed that
approval posture into memory evidence. When a completed or failed mission-linked
operation carries a real approval id in the operation result or retained task
input context, `operations.runtime` records the approval id and resolved local
approval status in the continuity receipt metadata, including
handoff/current-task loop fields that `/memory/timeline/list` projects as
structured loop evidence. The operation API projection and chat UI operations
client preserve that receipt approval status for the returned execution handoff.
This does not change approval decisions, policy gates, operation execution, or
mission advancement.

As of `2026-04-26`, mission advance receipts preserve the identity of the real
operation they just created or ran. The mission record, queue item, current-task
projection, and `advance_receipt` history entry now carry the existing
operation name and ORB plane from the operation projection, scoped to the same
operation id so stale advance metadata is not attached to an unrelated current
task. No operation creation, execution, governance, approval, or memory-write
behavior is changed.

As of `2026-04-26`, the chat UI mission client preserves that advance operation
identity without adding new visual claims. `MissionQueueItem` and
`MissionCurrentTask` parsing now retain the backend-provided operation name,
operation ORB plane, and advance action, so later interface surfaces can render
the real plan/execute stage identity from the typed mission contract instead of
falling back to ids alone.

As of `2026-04-25`, continuity ledger entries imported into the memory timeline
preserve bounded mission, operation, trace, approval, run, and artifact
references from ledger metadata. This lets memory timeline filters find existing
continuity receipts by the same real ids exposed in operation and mission loop
surfaces, without requiring a separate manual `/memory/timeline/record` write for
ledger-backed continuity evidence.

As of `2026-04-26`, terminal mission-linked operation runs now append a bounded
continuity receipt that the memory timeline can retrieve by mission,
operation, and available trace/run/artifact handles.
`operations.runtime.run_operation` records this only after an actual
mission-linked operation returns `succeeded` or `failed`, preserving the
execution -> trace -> memory link for both results and failures without
inventing memory state for blocked, unlinked, or merely queued work.

As of `2026-04-26`, direct mission-linked operation execution responses surface
that terminal-operation memory handoff when the continuity ledger append
actually succeeds. `POST /operations/{operation_id}/run` returns a bounded
`memory_receipt` projection with the ledger source, role, message, scope,
operation status, subsystem, and real mission/operation/trace/run/artifact
references when those handles exist, so callers can move from execution result
or failure to receipt-backed memory retrieval without claiming memory for
non-mission or non-terminal runs.

As of `2026-04-25`, the chat UI operations client preserves that direct
operation-run memory handoff. `OperationsClient.run` now keeps the returned
`memory_receipt` projection with source/kind, receipt scope, operation status,
capability/subsystem, and real mission/operation/trace/run/artifact references,
so interface code consuming direct operation execution results no longer drops
the execution-to-memory receipt bridge.

As of `2026-04-25`, the chat UI operation run completion notice can surface that
direct memory handoff when the backend returns it. The selected operation `Run
now` flow appends only the receipt-backed mission, operation, trace, approval,
run, and artifact references from `memory_receipt`; it does not claim memory
when the run response has no receipt projection.

As of `2026-04-25`, mission advance and bounded mission queue-run responses
preserve that same terminal-operation `memory_receipt` handoff when mission
progression executes a linked operation through the governed runtime. Direct
`POST /missions/{mission_id}/advance`, top-level `POST /missions/run_once`, and
the chat UI missions client now retain the receipt-backed mission, operation,
trace, run, and artifact references instead of dropping the execution-to-memory
handoff at the mission boundary.

As of `2026-04-25`, the mission continuity/world-state projection now carries
those terminal mission operation receipts as bounded memory evidence. Stage 3
mission readiness evidence exposes sampled missions with memory receipts,
receipt-backed operation and trace ids, and memory-backed reconstruction context;
mission briefing failed-preview and recent-completion payloads expose the latest
receipt without changing readiness status semantics or creating new execution
behavior.

As of `2026-04-26`, mission detail projections carry the same terminal-operation
memory receipts without requiring a world-state or briefing lookup. The
`GET /missions/{mission_id}` route returns bounded receipt-backed memory
evidence, latest receipt handles, and receipt-summary counts derived from
continuity-ledger entries for succeeded or failed mission-linked operation runs;
the memory loop stage exposes those receipts only when real mission and
operation ids exist.

As of `2026-04-26`, mission memory receipt projections also preserve a
structured `references` object alongside their flat mission, operation, trace,
approval, run, and artifact handle fields. This aligns mission detail,
continuity, and world-state memory receipts with the existing operation-run and
memory-timeline receipt contracts, so consumers can read one bounded reference
shape without parsing raw ledger metadata.

As of `2026-04-26`, mission memory receipt projections also preserve terminal
operation approval posture. When a mission-loop continuity receipt includes a
real `approval_status`, `mission_operation_receipts()` carries that status into
mission detail, continuity, and world-state receipt projections alongside the
existing approval id, without changing the receipt reference shape or approval
decision behavior.

As of `2026-04-26`, the chat UI missions client preserves that mission-detail
memory receipt contract. `MissionsClient.get` now retains flat ledger receipt ids,
mission, operation, trace, approval posture, run, artifact, domain, scope, and
count fields from mission detail, receipt summary, and the memory loop stage
while still preserving direct action response receipt references.

As of `2026-04-26`, the selected mission inspector and linked-operation mission
bridge render that preserved mission-detail memory receipt contract. The
Continuity Receipts panels and mission loop-stage cards now show backend-provided
memory receipt counts, latest receipt handles, timestamps, statuses, and bounded
mission/operation/trace/approval/run/artifact references when those fields are
present, without inventing memory state when no receipt is returned.

As of `2026-04-26`, artifact handles have a bounded backend inspection contract.
`GET /artifacts/inspect` accepts absolute or artifact-root-relative handles under
the local `data/artifacts` root and returns metadata-only directory/file
projections, with path containment enforced and no artifact file contents
returned. This makes mission and operation `artifact_dir` receipts inspectable as
backend truth before any UI claims richer artifact browsing.

As of `2026-04-26`, the chat UI artifacts client preserves that artifact
inspection contract without rendering new UI claims. `ArtifactsClient.inspect`
issues bounded `/artifacts/inspect` requests with the returned `artifact_dir`
and limit, keeps metadata-only file/directory projections, preserves missing or
failed artifact state, and drops any drifted content/payload fields so artifact
receipts remain inspectable without moving file contents into browser state.

As of `2026-04-26`, the selected operation detail panel can inspect artifact
handles through that client contract. When a selected operation exposes a real
`artifact_dir`, the chat UI offers a manual metadata inspection action and
renders only backend-returned availability, kind, path, size, timestamp, count,
and directory-entry metadata. Missing or unreadable artifact handles remain
visible as backend failure state instead of being converted into a UI success
claim, and file contents are not requested or displayed.

As of `2026-04-26`, selected mission continuity receipts can use the same
metadata-only artifact inspection path. When the selected mission receipt summary
exposes a real current `artifact_dir`, the Continuity Receipts panel offers a
manual receipt-artifact inspection action backed by `ArtifactsClient.inspect`.
The operation detail artifact inspector now uses the same shared panel component,
so both surfaces preserve the same backend failure-state and no-content boundary.

As of `2026-04-26`, artifact inspection failures include bounded recovery
guidance. `GET /artifacts/inspect` now returns backend-authored
`recovery_hint`, `next_step`, and `retryable` fields for missing, invalid,
outside-root, and unreadable artifact handles, and the chat UI artifacts client
and shared inspection panel preserve and render that guidance without requesting
or displaying artifact file contents.

As of `2026-04-25`, the chat UI settings client preserves that receipt-backed
mission memory contract and the Shift Briefing renders only the returned
continuity-backed memory receipts. The browser parser keeps receipt count,
latest receipt, mission, operation, trace, approval status, run, artifact,
domain, and scope fields, and readiness evidence now prioritizes memory receipt
ids without claiming synthesized memory when the backend does not return
receipts.

As of `2026-04-25`, mission loop detail includes an explicit read-only
`interface` stage after `plan -> gate -> execute -> trace -> memory`. The stage
is backed only by fields already returned by the mission detail API: loop
handoff, current task, and receipt summary. The chat UI mission parser preserves
that stage and the existing mission loop grids render it alongside the other
loop stages, so operators can see when backend interface context is available
without inventing UI-only state.

As of `2026-04-25`, `/chat/send` has a narrow P1 mission ingress path for
explicit `/mission ...` or `mission: ...` commands. That path creates only a
queued mission, respects the same operator posture write guard as mission APIs,
redacts the chat objective before mission and conversation persistence, and
returns the mission detail loop envelope so the interface can see the resulting
plan-stage handoff without claiming execution or autonomous routing.

As of `2026-04-25`, `/chat/ws` accepts the structured chat message envelope that
the browser chat client already sends, extracts only `message.content`, and
routes explicit mission ingress through the same guarded mission declaration
path. Mission ingress replies are returned as structured assistant events with
bounded mission loop metadata; ordinary WebSocket fallback replies remain plain
text for compatibility.

As of `2026-04-25`, the chat UI preserves explicit mission ingress metadata from
both `/chat/send` responses and structured WebSocket message events. When the
backend returns a real mission id, the chat surface can show the queued mission
status, active loop stage, next backend handoff, and an `Open mission flow`
action that jumps to the existing mission inspector. The UI does not create this
surface for ordinary chat replies or mission-less responses.

As of `2026-04-25`, the chat UI operations client preserves backend operation
creation mission-link truth. Mission-linked create requests are explicitly typed,
and create responses retain the returned operation projection, `mission_id`,
`mission_linked`, `mission_link_error`, approval id, status, and message. This
keeps first-operation handoff evidence available to operator surfaces, including
the partial-failure case where an operation was created but mission linking
failed.

As of `2026-04-25`, bounded mission queue runs preserve the concrete operation
projection returned by the governed mission runtime. `run_queue_once` result
items now keep the same operation object already returned by direct mission
advance, and the chat UI mission client preserves that operation projection
without requiring a follow-up operation lookup before an interface can reason
from the queue-run receipt.

As of `2026-04-25`, supervised execution approval and artifact surfaces no
longer persist raw secret-like command text or command output. Approval payloads
seal secret-bearing commands with HMAC-backed values so exact-action matching is
preserved, while request, plan, mismatch, result, stdout, and stderr artifacts
store redacted views. Raw task inputs still remain in local task records for the
approved execution path and API projections continue to return redacted views.

As of `2026-04-25`, git push approval and artifact surfaces share that execution
redaction posture. Credential-bearing remote URLs are sealed in approval payloads
so approval replay still rejects changed remotes, while git push request, plan,
mismatch, result, stdout, and stderr artifacts persist redacted views instead of
raw secret-like remote credentials. Raw task/result records may still retain live
execution data locally, but operation API projections redact those values.

As of `2026-04-25`, the shared governance redaction contract also treats HTTPS
URL userinfo as secret-bearing material. Credential-style remotes such as
`https://token@host/repo.git` are sealed and rendered as
`https://[REDACTED:secret]@host/repo.git` in git-push approval records,
artifacts, operation projections, and approval list projections while retaining
HMAC-backed exact-action protection in the persisted approval payload.

As of `2026-04-25`, approval API read projections redact sealed-secret internals.
Persisted approval records can retain HMAC-backed sealed values for exact-action
matching, but `/approvals/request`, `/approvals/list`, and `/approvals/decision`
responses collapse those values to their redacted display text so operator-facing
approval payloads do not expose raw secrets or `hmac-sha256:` digests.

As of `2026-04-25`, approval mismatch projections also read request-shaped
mismatch artifacts when `expected_payload` is not present. Industrial and
web-learning replacement approvals can now expose bounded expected/previous key
scope and changed-key evidence from their redacted mismatch artifacts without
showing payload values.

As of `2026-04-25`, supervised execution and git-push JSON receipt artifacts also
collapse sealed approval values to display-redacted text. Request, pending,
denied, error, mismatch, plan, and result artifacts can still show the bounded
action shape, but they no longer expose `hmac-sha256:` proof material. Persisted
approval records remain the exact-action matching source of truth.

As of `2026-04-25`, plugin approval receipt artifacts follow the same display
redaction boundary. Plugin approval request, error, and mismatch artifacts can
show the plugin id, action, changed payload shape, and redacted input values, but
they no longer expose sealed HMAC proof material. The persisted approval store
continues to hold sealed payloads for exact-action replay protection.

As of `2026-04-25`, web-learning approval receipt artifacts also use the display
redaction boundary. Learn-request, enable/disable, and quarantine-delete approval
request, error, and mismatch artifacts can preserve action shape and redacted URL
or note context without exposing sealed HMAC proof material. Persisted approval
records remain the exact-action replay source of truth.

As of `2026-04-25`, industrial approval receipt artifacts also use the display
redaction boundary. Safety validation, intervention request/execute, and digital
twin action approval request, error, and mismatch artifacts can preserve target,
action, and redacted parameter context without exposing sealed HMAC proof
material. Persisted approval records remain the exact-action replay source of
truth.

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

As of `2026-04-25`, failed and deadlettered mission queue items carry a
read-only `recovery` projection. The projection records source status, review
action, target task, recovery reason, next step, operator-required posture, and
the fact that automatic retry is not enabled. Mission detail, world-state
deadletter lists, continuity deadletter previews, and ORB deadletter cards can
show this recovery posture without implying a reopen or retry mutation path.

As of `2026-04-26`, linked-task transition receipts preserve the task record's
own `updated_at` timestamp when syncing task state back into mission metadata.
Mission ticks compare against the same task timestamp instead of a second
mission-store clock sample, so a repeated tick does not create false
`mission_ticked` progress just because the transition sync and task update
landed on different seconds. This hardens Stage 3 tick idempotence without
changing execution, approval, retry, or deadletter policy.

As of `2026-04-25`, failed-but-not-deadlettered missions are visible as their
own recovery queue. World-state snapshots expose `failed_missions`, continuity
briefings expose `failed_preview`, mission queue-run responses preserve a
bounded `failed` list, and ORB surfaces show failed mission recovery posture
separately from deadletter review. Stage 3 readiness now treats sampled failed
missions as attention-worthy until an explicit retry or deadletter decision is
made.

As of `2026-04-25`, operator recovery reviews for failed or deadlettered
missions are receipted explicitly. Invoking the bounded mission advance path on
`retry_or_deadletter` or `review_deadletter` records a `recovery_review`
mission-history event and `last_recovery_*` metadata without reopening the
mission, retrying automatically, or implying hidden autonomy. World-state,
continuity, mission clients, and ORB recovery cards can surface the latest
review action, outcome, target, actor, and timestamp.

As of `2026-04-25`, failed or deadlettered missions can declare a bounded
replacement mission from the recovery surface. The source mission remains in its
terminal recovery state, receives a `recovery_review` receipt with outcome
`replacement_declared`, and the new queued mission carries explicit replacement
metadata linking it to the source mission, action, target, actor, and reason. No
linked task is retried or run automatically by this path.

As of `2026-04-25`, replacement mission lineage is visible without raw metadata
inspection. Mission detail/list payloads, queue items, world-state recent/queue
surfaces, continuity focus items, and the selected ORB mission inspector can
surface the replacement source mission id, source status, recovery action,
source target, reason, actor, and note as bounded fields.

As of `2026-04-25`, source mission recovery surfaces also carry read-only
replacement follow-through. When a failed or deadlettered mission has declared a
replacement, its recovery projection can show the replacement mission id, live
status, objective, next step, latest task, update time, terminal posture, or a
missing-reference error without reopening the source or implying automatic retry.
Shift Briefing and overview recovery cards can show the same follow-through
without requiring the operator to open the selected mission inspector first.
Those recovery cards now prioritize missing or failed replacement follow-through
ahead of ordinary review items, so broken continuation links do not hide behind
newer but lower-risk recovery work.

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

As of `2026-04-22`, ready Shift Briefing focus items can now advance through the
existing bounded mission-advance path. The UI exposes this only for
`create_first_operation` and `run_linked_operation`; dependency and approval
blockers remain review-only and do not trigger mutation from the briefing card.

As of `2026-04-22`, mission queue and continuity briefing records now carry an
explicit `advance` projection. Ready items identify bounded advance eligibility
from the mission store contract, while dependency, approval, trust, and other
operator-required blockers remain ineligible and explain why.

As of `2026-04-22`, the dedicated mission queue client and ORB Mission Queue
surface also preserve and use that `advance` projection. Queue cards now disable
mutation from `advance.eligible` instead of only checking dependency action
strings.

As of `2026-04-22`, mission detail responses and the selected mission inspector
now share the same queue actionability contract. The mission detail API includes
the current `queue_item` projection, the chat UI parser preserves it, and the
selected mission advance control disables or labels mutation from
`queue_item.advance.eligible` instead of offering an unconditional advance
button.

As of `2026-04-22`, the selected mission inspector now exposes recovery targets
from the same queue actionability contract. Mission detail queue items preserve
approval ids, approval status, and last-advance receipt metadata in the browser
client, and the inspector can route the operator to the exact approval,
dependency mission, linked task, or last advanced task without creating a new
mutation path.

As of `2026-04-23`, mission queue-run result cards now preserve and render the
same queue actionability contract after a bounded batch pass. Each run result can
carry its current `queue_item`, and the ORB Mission Queue summary can show
post-run advance posture, approval/dependency state, last-advance outcome, and
review links without requiring the operator to infer recovery targets from raw
counts.

As of `2026-04-23`, the bounded Mission Queue view now prioritizes
review-required missions over already-eligible work and reports hidden queue
counts explicitly. Return-to-work recommendations, mission selection ordering,
and the first queue cards now reuse the same contract, so the operator is sent
to the most constrained mission instead of whichever queue item happened to land
first.

As of `2026-04-23`, the deadletter preview surfaces now preserve more explicit
failure truth from the existing payloads. Shift Briefing deadletter review and
overview deadletter cards both show the recommended review action, latest
recorded activity, updated time, and hidden-count disclosure instead of looking
like a vague truncated list of failures.

As of `2026-04-23`, the continuity deadletter preview now preserves the last
attempted task identity, stored task state, failed attempt result, and gate in
the briefing payload. Shift Briefing deadletter review can route the operator
to the actual failed task and show whether the hold came from the task state or
from the last blocked result instead of only naming the mission.

As of `2026-04-23`, deadletter surfaces now carry a lightweight
mission-history receipt summary instead of relying only on current state.
Continuity deadletter review and overview deadletter cards can show how many
mission receipts exist plus the latest recorded history event/time, which keeps
deadletter recovery tied to persisted evidence rather than implied failure
stories.

As of `2026-04-23`, deadletter briefing surfaces now carry a bounded
mission-history tail instead of only aggregated receipt metadata. Operators can
see the last two persisted mission history entries, including event names,
timestamps, and stored details, directly in deadletter cards before opening the
full mission inspector.

As of `2026-04-23`, deadletter briefing surfaces now derive a compact operator
receipt narrative from the bounded history tail. The cards still expose the raw
receipts, but they also summarize the common deadletter path in plain operator
language so continuity review does not start with event-name decoding.

As of `2026-04-23`, deadletter approval review now preserves approval lineage
instead of only the current approval target. Shift Briefing and overview
deadletter cards can show the superseded approval id when it exists and route
the operator to either the current pending approval or the prior approval record
through the existing approval inspector.

As of `2026-04-24`, deadletter approval review now preserves superseded
approval status as part of the same governed lineage. When an exact-action
approval is refreshed and the mission is later deadlettered, continuity and
world-state review now preserve whether the prior approval had already been
approved before the replacement request was issued.

As of `2026-04-24`, refreshed approval review also preserves the bounded
replacement reason and changed top-level payload keys from existing mismatch
artifacts. Deadletter review, approval review, and world-state pending approval
cards can show that a replacement came from `approval_payload_mismatch` and
which request key changed without exposing raw payload values.

As of `2026-04-24`, deadletter replacement approval routing is explicit in the
operator surface. Deadletter cards label replacement reviews distinctly, preserve
the deadletter source/reason/changed-key context when opening approvals, and the
approval inspector shows that context only for the focused approval it came from.

As of `2026-04-24`, deadletter approval replacement review also preserves the
bounded mismatch artifact kind. Continuity and world-state mission items now
carry `last_task_approval_replacement_kind`, and deadletter cards plus approval
return context can show `plugin.run.mismatch`-style provenance without exposing
raw expected or actual payload values.

As of `2026-04-24`, approval replacement review now also preserves bounded
mismatch key scope. Approval list/world-state projections can show the expected
and prior top-level payload keys involved in an exact-action mismatch, while
still withholding raw expected and approved payload values.

As of `2026-04-24`, Francis has a more explicit public GitHub discovery posture.
The repository README, package metadata, issue templates, PR template, GitHub
description, topics, discussions setting, and `roadmap` label now present Francis
as a Phase 2 local-first governed AI operator layer without claiming finished
autonomy.

As of `2026-04-24`, first-time GitHub readers now have a bounded repository
orientation path. `docs/START_HERE.md` and the static ORB runtime loop diagram
explain the Phase 2 truth, canonical reading order, contribution surfaces, and
proposal-to-receipt flow without changing runtime behavior or overstating
scaffolded capability.

As of `2026-04-25`, mission detail loop-state projection now pins the active
operation to mission continuity truth. When multiple operations are linked, the
handoff prefers `last_task_id` from the mission record before falling back to
newest operation timestamp, so older queued work no longer hides a newer
governance hold in the operator-facing `plan -> gate -> execute -> trace ->
memory` projection.

As of `2026-04-25`, world-state mission activity now follows the same
current-task truth. Mission queue, recent mission, and briefing activity
enrichment prefer the mission record's current task target before falling back
to newest linked-operation receipts, so a stale linked task with a later audit
receipt cannot mask the active blocker the operator needs to review.

As of `2026-04-26`, mission detail loop-state projections carry receipt handles
past the trace id. Loop stages and handoffs can now include the current
`run_id` and `artifact_dir` alongside `operation_id` and `trace_id`, and the
chat UI mission client preserves those handles in the typed mission loop
contract. This keeps trace/artifact reachability tied to backend receipts rather
than requiring operators or interface code to reconstruct handles from raw task
JSON.

As of `2026-04-26`, the ORB mission loop inspector renders those loop-stage
receipt handles directly. Handoff and stage metadata now surface `run` and
bounded `artifact` handles next to task and trace handles when the backend
returns them, without inventing handles when the loop state omits them.

As of `2026-04-26`, mission loop stage artifact handles are inspectable from
the ORB mission loop inspector through the existing bounded artifact inspection
panel. Stage cards only render the inspector when the backend loop stage returns
an `artifact_dir`, and inspection remains read-only metadata retrieval through
the existing artifact route.

As of `2026-04-25`, the ORB chat UI also prefers current mission task truth for
mission recovery links. Selected mission recovery posture, return-to-work
mission actions, and recent mission progress cards use `last_task_id`, loop
handoff operation, or queue actionability targets before falling back to the
first linked task, so operators are routed to the active mission task rather
than an older linked operation.

As of `2026-04-25`, that ORB chat UI current-task routing rule is now a shared
mission client contract with direct TypeScript coverage. The tested selector
preserves the precedence order from queue `last_task_id`, loop handoff
operation, mission/meta `last_task_id`, task-shaped action targets, last
advance operation, and finally linked-task fallback, reducing the chance that a
future UI edit silently reintroduces stale mission routing.

As of `2026-04-25`, ORB mission recovery targets also share a tested UI helper
that preserves dependency mission links while routing operation links through
current-task truth. Return-to-work queue leads, Shift Briefing focus cards,
mission queue run summaries, and visible mission queue cards no longer prefer a
stale task-shaped `action_target_id` over the current task id when opening
linked work or approval context.

As of `2026-04-25`, selected mission post-advance approval notices now use the
same current-operation contract. When an advance response needs to fall back to
the refreshed mission detail payload, the UI selects the linked operation that
matches current mission task truth before falling back to the first linked
operation, so multi-operation missions do not surface approval context from
older work.

As of `2026-04-25`, mission API records now expose bounded current-task fields
directly, not only inside `meta` or queue projections. Mission detail/list
payloads can carry `last_task_id`, last task status/result/gate/next-step
reason, and last advance operation id, and the chat UI mission client preserves
those fields so current-task selectors can rely on the mission record contract
when queue context is not present.

As of `2026-04-25`, the selected mission inspector also reads those direct
mission current-task fields before falling back to legacy `meta`. Latest run,
result, gate, and reason badges in the ORB mission detail surface now follow
the mission record contract instead of requiring callers to know where the
backend used to store those values internally.

As of `2026-04-25`, mission detail and post-run payloads also include a bounded
`current_task` projection. It carries the active mission task id, operation
status, task status, result, gate, approval handoff, latest receipt, and source
lineage so clients can show the live mission target without reconstructing it
from meta, queue items, loop state, linked operations, and run-ledger receipts
separately.

As of `2026-04-25`, the ORB selected mission inspector now consumes that
`current_task` projection first for the current task id, latest run status,
task status, result, gate, approval id/status, and recovery target. Existing
mission, queue, and loop-state fields remain as fallback compatibility paths.

As of `2026-04-20`, the strongest truthful CI posture is:

- feature-branch pushes no longer create duplicate GitHub `push` + `pull_request`
  runs; PR validation now executes once per change on non-`main` branches
- repo-wide type debt is still materially present, but `mypy.ini` now scopes that
  debt explicitly to known modules instead of letting the CI surface imply the
  whole tree is already under a clean type gate
- `mypy src` is now green again for the currently gated tree, which removes an
  unrelated GitHub blocker from the active Stage 2 observer follow-up line

## 3. High-confidence current slice

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is current-task receipt-status continuity. This advances the active
`Phase 2 / P7_EXECUTION -> P9_OBSERVABILITY -> P8_MEMORY -> P1_INTERFACE` line
by carrying run-ledger receipt status into the mission current-task contract used
by mission detail, world-state, continuity briefing, and chat UI operator
surfaces:

- `src/francis/api/routes/missions.py` now includes `latest_receipt_status` on
  mission current-task projections when the selected current-task receipt has a
  status.
- `src/francis/world_state/snapshot.py` preserves that status when enriching
  mission current-task data for world-state and continuity surfaces.
- `apps/chat_ui/src/missions/index.ts` and `apps/chat_ui/src/settings/index.ts`
  preserve the field through mission and settings/briefing parsers.
- `apps/chat_ui/src/App.tsx` renders the status next to current-task receipt
  context in focused operator surfaces without adding new mutation behavior.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is trace receipt-status continuity in the mission loop. This
advances the active `Phase 2 / P7_EXECUTION -> P9_OBSERVABILITY -> P8_MEMORY ->
P1_INTERFACE` line by carrying the latest run-ledger receipt status into the
operator-visible loop contract:

- `src/francis/api/routes/missions.py` now includes
  `latest_receipt_status` on the loop trace stage when a real run-ledger receipt
  supplies that status.
- `apps/chat_ui/src/missions/index.ts` preserves that field through the mission
  detail parser.
- `apps/chat_ui/src/App.tsx` renders the receipt status in both the mission
  inspector loop and the operation detail mission bridge, without changing
  execution behavior or inventing memory state.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is the positive ready-state continuity contract. This advances the
active `Phase 2 / P7_EXECUTION -> P8_MEMORY` line by proving the mission
readiness model can reach a fully satisfied state from real API paths:

- `tests/test_api_continuity.py` now constructs a completed mission plus a clean
  deadlettered mission through the public mission APIs.
- The resulting continuity briefing must report Stage 3 mission readiness
  `ready`, `5/5` criteria satisfied, and empty blocked/attention/review
  closure lists.
- The test asserts the ready state is backed by tick evidence, persisted mission
  history, reconstruction context, and clean deadletter evidence instead of a
  hand-written readiness fixture.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is readiness closure blocker disclosure. This advances the active
`Phase 2 / P8_MEMORY -> P1_INTERFACE` line by making Stage 3 readiness summaries
name their own unresolved closure criteria:

- `src/francis/world_state/snapshot.py` now includes `blocked_criteria_ids`,
  `attention_criteria_ids`, and `review_criteria_ids` in the mission readiness
  summary.
- `apps/chat_ui/src/settings/index.ts` preserves those arrays through the
  readiness parser, and `apps/chat_ui/src/App.tsx` renders them in the shared
  readiness evidence panel.
- Readiness closure now remains explicit even when a compact UI card only shows
  a bounded number of criterion details.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is recovery-review readiness evidence context. This advances the
active `Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by making
failed-mission readiness evidence cite bounded review outcomes instead of only
mission ids:

- `src/francis/world_state/snapshot.py` now includes recovery review action,
  outcome, and target maps in the `deadletter_cleanly` readiness evidence for
  sampled failed missions.
- Replacement-declared failed sources now also expose replacement follow-through
  status by replacement mission id, while still keeping source missions terminal
  and non-mutating.
- `apps/chat_ui/src/settings/index.ts` now prioritizes those recovery-review
  evidence keys so the Shift Briefing and Mission Feed readiness panels surface
  receipt-backed context before lower-value counts.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is shared Mission readiness evidence rendering. This advances the
active `Phase 2 / P8_MEMORY -> P1_INTERFACE` line by keeping the Shift Briefing
and Mission Feed overview on one read-only readiness presentation path:

- `apps/chat_ui/src/App.tsx` now uses a shared
  `MissionReadinessEvidencePanel` for both readiness surfaces instead of
  duplicating JSX and presentation state.
- The Shift Briefing preserves its fuller readiness view: criterion badges,
  prioritized detail cards, bounded evidence lines, and hidden-count disclosure.
- The Mission Feed overview preserves its compact readiness view with the same
  prioritized criteria and bounded evidence formatting, reducing drift risk
  without changing mission mutation, policy, or recovery behavior.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is overview Mission readiness evidence parity. This advances the
active `Phase 2 / P8_MEMORY -> P1_INTERFACE` line by making the same readiness
blocker evidence visible in the Mission Feed overview, not only the Shift
Briefing:

- `apps/chat_ui/src/settings/index.ts` now preserves the
  `/system/world_state.overview.mission_briefing.readiness` payload so the
  overview client can consume the same Stage 3 readiness contract as the
  continuity briefing route.
- `apps/chat_ui/src/App.tsx` now renders compact Mission readiness evidence in
  the Mission Feed overview, including stage/status, next action, prioritized
  criterion badges, bounded evidence lines, and hidden-count disclosure.
- `apps/chat_ui/src/settings/index.test.ts` now proves world-state parsing
  preserves mission briefing readiness and formats failed/replacement evidence
  for the overview path.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is mission readiness evidence rendering. This advances the active
`Phase 2 / P8_MEMORY -> P1_INTERFACE` line by making readiness blockers
inspectable in the operator briefing instead of leaving them as badge-only
signals:

- `apps/chat_ui/src/settings/index.ts` now exports a tested readiness
  presentation helper that orders attention/review criteria before satisfied
  criteria and formats bounded evidence lines from the readiness payload.
- `apps/chat_ui/src/App.tsx` now shows the highest-priority Mission readiness
  criteria with detail text and compact evidence in the Shift Briefing card,
  including hidden-count disclosure for criteria outside the bounded view.
- `apps/chat_ui/src/settings/index.test.ts` now proves readiness criteria are
  prioritized and that failed/replacement follow-through evidence is formatted
  without exposing raw payloads.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is recovery-reviewed failure readiness. This advances the active
`Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by keeping Stage 3
readiness tied to recovery receipts instead of raw terminal status alone:

- `src/francis/world_state/snapshot.py` now distinguishes unreviewed failed
  missions from failed source missions that have explicit
  `replacement_declared` recovery follow-through.
- Stage 3 readiness evidence now reports sampled failed ids, unsampled failed
  count, recovery-reviewed failed ids, replacement-reviewed failed ids,
  replacement follow-through ids, replacement attention ids, and unresolved
  failed ids.
- `tests/test_api_continuity.py` now proves an operator-reviewed failure that
  still requires a decision remains attention-worthy, while a failed source with
  a queued replacement no longer blocks readiness solely because the source
  correctly remains terminal.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is replacement follow-through priority ordering. This advances the
active `Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by making
broken replacement references harder to miss:

- `apps/chat_ui/src/settings/index.ts` now exports a shared recovery
  presentation sorter and ranks missing, errored, failed, deadlettered, or
  cancelled replacement follow-through ahead of ordinary review cards.
- `apps/chat_ui/src/App.tsx` now uses that sorter for Shift Briefing and
  overview failed-mission recovery cards, while deadletter cards share the same
  replacement severity rank.
- `apps/chat_ui/src/settings/index.test.ts` now proves both failed-recovery and
  deadletter presentation paths prioritize broken replacement follow-through.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is replacement follow-through card parity. This advances the active
`Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by bringing the
read-only replacement status context into the broader recovery surfaces:

- `apps/chat_ui/src/App.tsx` now renders replacement follow-through in Shift
  Briefing and overview failed/deadletter recovery cards, with a bounded route to
  open the replacement mission.
- `apps/chat_ui/src/settings/index.test.ts` now proves world-state and
  continuity deadletter recovery payloads preserve replacement follow-through
  fields through the presentation path.
- No new mutation path was added; source missions remain failed/deadlettered
  until explicit governed action changes them.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is replacement follow-through visibility. This advances the active
`Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by letting operators
see what happened after a source mission declared replacement work:

- `src/francis/missions/store.py` now enriches failed/deadlettered recovery
  projections with read-only replacement mission status, objective, next step,
  latest task, terminal posture, and missing-reference truth.
- `apps/chat_ui/src/missions/index.ts` and `apps/chat_ui/src/settings/index.ts`
  now preserve those fields through mission and world-state/continuity clients.
- `apps/chat_ui/src/App.tsx` now shows replacement follow-through in the
  selected mission recovery panel and routes to the replacement mission.
- `tests/test_api_missions.py`, `tests/test_api_system_settings.py`,
  `tests/test_api_continuity.py`, `apps/chat_ui/src/missions/index.test.ts`,
  and `apps/chat_ui/src/settings/index.test.ts` now prove the contract.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is approval-status label parity across mission cards. This advances
the active `Phase 2 / P3_GOVERNANCE -> P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE`
line by making compact briefing and queue surfaces use the same approval
language as the selected mission inspector:

- `apps/chat_ui/src/App.tsx` now renders explicit `approval_status` labels in
  Shift Briefing focus cards, mission queue-run result cards, and Mission Queue
  cards when approval posture is available.
- This keeps compact operator surfaces aligned with the selected mission ORB
  Loop State inspector instead of relying on a generic `status` label.
- No mutation or execution path changed; this only clarifies already-projected
  approval posture in the UI.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is mission queue-run receipt continuity. This advances the active
`Phase 2 / P7_EXECUTION -> P9_OBSERVABILITY -> P8_MEMORY -> P1_INTERFACE` line
by keeping the immediate queue-run result tied to the local mission receipt trail:

- `apps/chat_ui/src/App.tsx` now renders the latest mission receipt and bounded
  history tail inside mission queue-run result cards when the backend returns
  `queue_item.latest_history_*` and `queue_item.history_tail`.
- This makes the post-action result card carry the same continuity evidence
  already visible in steady-state Mission Queue cards.
- No mutation, approval, execution, shell, or memory-write behavior changed; this
  is a read-only operator-truth surface.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is mission queue-run trace posture. This advances the active
`Phase 2 / P7_EXECUTION -> P9_OBSERVABILITY -> P8_MEMORY -> P1_INTERFACE` line
by making immediate queue-run results show the trace-bearing receipt summary:

- `apps/chat_ui/src/App.tsx` now carries `receipt_summary` into mission queue-run
  result cards and renders receipt task, receipt status, receipt gate,
  receipt approval, trace id, latest run event, run status, and run time when
  present.
- `apps/chat_ui/src/missions/index.test.ts` now asserts the queue-run client
  preserves the trace and latest-run receipt fields consumed by the UI.
- No new execution, approval, shell, policy, or memory-write path was added; this
  only exposes already-returned receipt metadata.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is mission queue-run receipt target reachability. This advances the
active `Phase 2 / P3_GOVERNANCE -> P7_EXECUTION -> P9_OBSERVABILITY ->
P1_INTERFACE` line by making receipt-only approval and task references actionable
from the immediate queue-run result:

- `apps/chat_ui/src/App.tsx` now offers `Review receipt approval` when a
  queue-run receipt summary carries an approval id not already exposed by the
  queue item/result envelope.
- `apps/chat_ui/src/App.tsx` now offers `Open receipt task` when the receipt
  summary's current operation is not already reachable through the linked task,
  action target, or last-advanced task buttons.
- No new mutation, approval decision, execution, shell, policy, or memory-write
  behavior was added; this only routes the operator to existing governed
  inspection panels.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is mission queue-run error actionability. This advances the active
`Phase 2 / P7_EXECUTION -> P9_OBSERVABILITY -> P8_MEMORY -> P1_INTERFACE` line
by keeping bounded queue-run failures visible inside the immediate result card:

- `apps/chat_ui/src/App.tsx` now carries bounded `errors` from
  `/missions/run_once` into the queue-run summary and renders error cards with
  mission, operation, approval, gate, next-step, status, and action context when
  present.
- Queue-run error cards now route to existing mission, task, and approval
  inspection surfaces rather than hiding all detail behind a single notice.
- `apps/chat_ui/src/missions/index.test.ts` now proves the client preserves
  bounded queue error records for UI actionability.
- No mutation, approval decision, execution, shell, policy, or memory-write
  behavior changed; this is read-only failure visibility.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is mission queue-run summary posture. This advances the active
`Phase 2 / P7_EXECUTION -> P9_OBSERVABILITY -> P8_MEMORY -> P1_INTERFACE` line
by making the queue-run summary header report status, total error count, and
backend queue counts alongside processed/applied/advanced totals:

- `apps/chat_ui/src/App.tsx` now carries `/missions/run_once` status, total
  error count, top-level error, and queue counts into the queue-run summary.
- The queue-run summary now renders status, error count, top-level error, and
  queued/active/blocked/failed/deadlettered counts when returned by the backend.
- `apps/chat_ui/src/missions/index.test.ts` now asserts the queue-run client
  preserves the processed total and bounded error count consumed by the UI.
- No mutation, approval decision, execution, shell, policy, or memory-write
  behavior changed; this is read-only result posture visibility.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is mission queue-run top-level status truth. This advances the
active `Phase 2 / P7_EXECUTION -> P9_OBSERVABILITY -> P8_MEMORY -> P1_INTERFACE`
line by making the backend contract match the queue-run summary posture exposed
to operators:

- `src/francis/missions/runtime.py` now returns a top-level queue-run `status`
  of `succeeded` or `failed`, plus a bounded top-level `error` when the run
  records errors.
- `src/francis/missions/store.py` mirrors the same status/error contract for
  the repo-root compatibility path.
- `src/francis/api/routes/missions.py` now returns `status: failed` and a
  top-level `error` for runtime exceptions, while preserve-mode blocks keep
  `status: blocked` with the same error surfaced at the top level.
- `tests/test_api_missions.py` and `apps/chat_ui/src/missions/index.test.ts`
  now prove the successful, blocked, failed, and UI client status paths.
- No queue selection, mission mutation, approval decision, shell, policy, or
  memory-write behavior changed; this only makes the queue-run envelope truthful.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is mission queue-run request identity visibility. This advances the
active `Phase 2 / P2_IDENTITY -> P7_EXECUTION -> P9_OBSERVABILITY ->
P1_INTERFACE` line by making queue-run envelopes identify the bounded request
that caused the pass:

- `src/francis/api/routes/missions.py`, `src/francis/missions/runtime.py`, and
  `src/francis/missions/store.py` now return a bounded `request` projection with
  redacted `actor`, redacted `note`, and effective `limit` for successful,
  blocked, and failed queue-run responses.
- `apps/chat_ui/src/missions/index.ts` now preserves that request projection
  without materializing absent optional fields.
- `apps/chat_ui/src/App.tsx` now renders queue-run actor, limit, and note inside
  the immediate queue-run summary when returned by the backend.
- `tests/test_api_missions.py` now proves request identity is present on success,
  blocked, and runtime-failure paths and that secret-like note text is redacted.
- No queue selection, mission mutation, approval decision, shell, policy, or
  memory-write behavior changed; this is bounded request identity visibility.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is mission queue-run failure context parity. This advances the
active `Phase 2 / P7_EXECUTION -> P9_OBSERVABILITY -> P1_INTERFACE` line by
making runtime queue-run failure records carry the same bounded handoff context
the UI already knows how to render:

- `src/francis/missions/runtime.py` now enriches failed queue-advance error
  records with action, status, operation id, approval id, gate, next step, and
  message when those fields are returned by the failed advance outcome.
- `tests/test_api_missions.py` now proves `/missions/run_once` preserves that
  context in the top-level `errors` list for operator actionability.
- No queue selection, mission mutation, approval decision, shell, policy, or
  memory-write behavior changed; this only keeps existing failure context
  attached to the immediate queue-run result.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is mission queue-run failure trace visibility. This advances the
active `Phase 2 / P7_EXECUTION -> P9_OBSERVABILITY -> P1_INTERFACE` line by
keeping failed advance traces attached to immediate queue-run error cards:

- `src/francis/missions/runtime.py` now preserves `trace_id` on top-level
  queue-run error records when a failed advance outcome returns one.
- `apps/chat_ui/src/App.tsx` now carries and renders the queue-run error trace
  id beside the operation, approval, gate, and next-step context.
- Backend and UI client tests now prove the trace handle is not dropped from the
  bounded `/missions/run_once` error contract.
- No queue selection, mission mutation, approval decision, shell, policy, or
  memory-write behavior changed; this only keeps an existing trace handle
  visible when the runtime returns it.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is mission queue-run result trace visibility. This advances the
active `Phase 2 / P7_EXECUTION -> P9_OBSERVABILITY -> P1_INTERFACE` line by
keeping successful advance trace handles attached to immediate queue-run result
cards:

- `src/francis/missions/runtime.py` now preserves `trace_id` on queue-run result
  records when a mission advance outcome or operation handoff returns one.
- `apps/chat_ui/src/missions/index.ts` now preserves result-level `trace_id`
  through the bounded `/missions/run_once` client contract.
- `apps/chat_ui/src/App.tsx` now renders a queue-run result trace from receipt
  summary, direct result context, or current-task context, in that order.
- Backend and UI client tests now prove queue-run result trace handles are not
  dropped.
- No queue selection, mission mutation, approval decision, shell, policy, or
  memory-write behavior changed; this only keeps an existing trace handle
  reachable when returned.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is operation receipt trace projection. This advances the active
`Phase 2 / P7_EXECUTION -> P9_OBSERVABILITY -> P1_INTERFACE` line by making
receipt-backed plugin execution traces visible through operation and mission
read models:

- `src/francis/operations/runtime.py` and `src/francis/api/routes/operations.py`
  now project trace ids from operation result receipts, sandbox receipts, and
  audit events onto `operation.trace_id` and `operation.meta.trace_id`.
- `src/francis/api/routes/missions.py` now recognizes those same receipt-backed
  trace sources when deriving mission current-task, receipt-summary, and loop
  trace state.
- `src/francis/missions/runtime.py` now carries receipt-backed operation traces
  through mission advance handoffs when the operation result includes them.
- API tests now prove plugin operation traces survive create/run/get/list
  projections and reach mission receipt-summary, current-task, and loop trace
  surfaces.
- No queue selection, mission mutation, approval decision, shell, policy, or
  memory-write behavior changed; this only exposes existing receipt trace ids.

As of `2026-04-25`, the highest-confidence surface newly advanced in the
current Stage 3 line is operation receipt handle projection. This advances the
active `Phase 2 / P7_EXECUTION -> P9_OBSERVABILITY -> P1_INTERFACE` line by
making existing execution `run_id` and artifact handles visible beside trace
handles in operation and mission read models:

- Operation projections now lift `run_id` and `artifact_dir` from operation
  result payloads, nested receipts, sandbox receipts, and audit events onto the
  operation record and `operation.meta`.
- Mission detail and queue-run projections now expose those handles through
  current-task and receipt-summary surfaces so operators can inspect the exact
  run or artifact directory without spelunking raw task files.
- The chat UI parser and ORB mission inspector preserve and render those
  handles on selected mission continuity receipts, queue-run result cards, and
  queue-run error context.
- API and UI client tests now prove plugin `run_id` handles and supervised
  execution artifact directories survive operation, mission, and queue-run
  projections.
- No queue selection, approval decision, shell execution, policy, memory-write,
  or hidden-autonomy behavior changed; this only exposes handles that execution
  receipts already produced.

As of `2026-04-25`, the highest-confidence surface newly advanced in the
current Stage 3 line is operation detail receipt-handle visibility. This
advances the active `Phase 2 / P7_EXECUTION -> P9_OBSERVABILITY -> P1_INTERFACE`
line by making operation inspection show receipt run and artifact handles
directly instead of requiring raw JSON inspection:

- `apps/chat_ui/src/App.tsx` now derives operation `run_id` and `artifact_dir`
  from the operation record, metadata, result output, nested receipt, or sandbox
  receipt using the same defensive pattern already used for trace handles.
- The Operation Detail panel now renders `Run` and `Artifact` beside `Trace`
  when those handles exist, so opening a receipt task exposes inspectable
  evidence without terminal spelunking.
- No operation mutation, approval decision, execution, shell, policy, memory, or
  mission queue behavior changed; this is a read-only operator visibility
  improvement for existing receipt handles.

As of `2026-04-25`, the highest-confidence surface newly advanced in the
current Stage 3 line is operation detail recovery guidance visibility. This
advances the active `Phase 2 / P7_EXECUTION -> P9_OBSERVABILITY -> P1_INTERFACE`
line by making important operation failures actionable in the operator console:

- `apps/chat_ui/src/App.tsx` now derives recovery guidance from existing
  operation truth: governance next step, gate, approval id, artifact directory,
  trace id, and captured error state.
- The Operation Detail panel now renders a `Recovery` line beside explicit
  errors, and for blocked/denied/failed/error states when there is no raw error
  string.
- No operation mutation, approval decision, execution, shell, policy, memory, or
  mission queue behavior changed; this is a read-only operator actionability
  improvement for existing failure context.

As of `2026-04-25`, the highest-confidence surface newly advanced in the
current Stage 3 line is operation detail mission-loop bridge visibility. This
advances the active `Phase 2 / P7_EXECUTION -> P9_OBSERVABILITY -> P8_MEMORY ->
P1_INTERFACE` line by making the selected operation show its linked mission
loop and continuity posture without forcing a raw JSON inspection:

- `apps/chat_ui/src/App.tsx` now loads the selected operation's linked mission
  detail from the existing mission detail route when a real `mission_id` is
  present.
- Operation Detail now renders a read-only `Mission Loop Bridge` with the
  linked mission active stage, handoff context, plan/gate/execute/trace/memory
  stage statuses, run receipt count, history receipt count, and latest memory
  receipt metadata when those fields exist.
- No operation mutation, mission mutation, approval decision, execution, shell,
  policy, or memory-write behavior changed; this only connects existing mission
  loop truth back to task inspection.

As of `2026-04-25`, the highest-confidence surface newly advanced in the
current Stage 3 line is operation detail mission-loop refresh fidelity. This
advances the active `Phase 2 / P7_EXECUTION -> P9_OBSERVABILITY -> P8_MEMORY ->
P1_INTERFACE` line by keeping the operation-to-mission loop bridge current after
explicit operator actions:

- `apps/chat_ui/src/App.tsx` now reuses a bounded linked-mission detail refresh
  helper instead of only loading the bridge when the selected operation's
  `mission_id` changes.
- Operation Detail now refreshes the linked mission loop after `Create request`,
  `Create + run now`, `Run now`, `Cancel`, and `Run worker cycle` paths when a
  real linked mission id is available.
- No operation mutation, mission mutation, approval decision, execution, shell,
  policy, or memory-write behavior changed; this only prevents stale
  operator-facing loop and continuity posture after live-path actions.

As of `2026-04-25`, the highest-confidence surface newly advanced in the
current Stage 3 line is operation detail mission-loop retry visibility. This
advances the active `Phase 2 / P7_EXECUTION -> P9_OBSERVABILITY -> P8_MEMORY ->
P1_INTERFACE` line by making reconnect/retry behavior visible from task
inspection:

- `apps/chat_ui/src/App.tsx` now makes the Operations panel `Refresh` action
  reload the operation list, selected operation detail, and linked mission loop
  bridge together instead of only refreshing the list.
- The Operation Detail `Mission Loop Bridge` now exposes an explicit
  `Refresh loop` action so a transient linked-mission read failure can be
  retried in place.
- No operation mutation, mission mutation, approval decision, execution, shell,
  policy, or memory-write behavior changed; this only makes the existing read
  path recoverable after reconnect or route failure.

As of `2026-04-25`, the highest-confidence surface newly advanced in the
current Stage 3 line is operation detail mission current-task posture
visibility. This advances the active `Phase 2 / P3_GOVERNANCE -> P7_EXECUTION
-> P9_OBSERVABILITY -> P8_MEMORY -> P1_INTERFACE` line by making the selected
operation's mission bridge show the same current-task posture that the mission
inspector already receives:

- `apps/chat_ui/src/App.tsx` now derives current-task id, task status, approval
  status, result status, gate, and next step from the linked mission detail
  bridge.
- Operation Detail now renders those fields inside `Mission Loop Bridge` so the
  task inspection path shows gate, approval state, execution result, and
  continuity context together.
- No operation mutation, mission mutation, approval decision, execution, shell,
  policy, or memory-write behavior changed; this only exposes existing
  mission-detail truth from the active task surface.

As of `2026-04-25`, the highest-confidence surface newly advanced in the
current Stage 3 line is operation detail mission bridge action routing. This
advances the active `Phase 2 / P3_GOVERNANCE -> P7_EXECUTION ->
P9_OBSERVABILITY -> P8_MEMORY -> P1_INTERFACE` line by making the selected
operation's mission bridge actionable without raw JSON inspection:

- `apps/chat_ui/src/App.tsx` now derives bridge approval and task handles from
  linked mission current-task, loop handoff, and receipt-summary fields.
- Operation Detail now exposes `Review bridge approval`, `Open bridge task`, and
  `Open mission flow` actions from `Mission Loop Bridge` when those real handles
  exist.
- No operation mutation, mission mutation, approval decision, execution, shell,
  policy, or memory-write behavior changed; this only routes existing handles to
  their existing operator surfaces.

As of `2026-04-25`, the highest-confidence surface newly advanced in the
current Stage 3 line is operation detail mission bridge stage receipt
visibility. This advances the active `Phase 2 / P3_GOVERNANCE -> P7_EXECUTION
-> P9_OBSERVABILITY -> P8_MEMORY -> P1_INTERFACE` line by making the selected
operation's mission bridge show the same loop-stage evidence already projected
by mission detail:

- `apps/chat_ui/src/App.tsx` now renders bridge loop stages as compact cards
  with stage detail, count, gate, approval status, next step, task id, trace id,
  latest receipt event, and latest receipt time when those real fields exist.
- Bridge stage cards expose `Review stage approval` and `Open stage task`
  actions only when the backend-projected loop stage carries those handles.
- No operation mutation, mission mutation, approval decision, execution, shell,
  policy, or memory-write behavior changed; this only makes existing loop
  receipt evidence visible from operation inspection.

As of `2026-04-25`, the highest-confidence surface newly advanced in the
current Stage 3 line is active-flow receipt ledger reachability. This advances
the active `Phase 2 / P7_EXECUTION -> P9_OBSERVABILITY -> P8_MEMORY ->
P1_INTERFACE` line by letting operators jump from active task and mission
receipt contexts to the existing ORB continuity ledger:

- `apps/chat_ui/src/App.tsx` now exposes `Open ORB ledger` from Operation Detail
  when the selected operation or linked mission bridge carries real trace, run,
  artifact, loop, or receipt evidence.
- The selected mission `Continuity Receipts` card now exposes `Open continuity
  ledger` when mission receipt evidence exists, and the command palette includes
  the same direct ledger navigation.
- No ledger write, memory write, trace generation, mission mutation, operation
  mutation, approval decision, execution, shell, or policy behavior changed; this
  only routes existing read-only receipt surfaces together.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is visible loop approval status. This advances the active
`Phase 2 / P3_GOVERNANCE -> P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by
showing the loop-level approval posture in the operator mission inspector:

- `apps/chat_ui/src/App.tsx` now renders `approval_status` on the selected
  mission ORB Loop State handoff and per-stage cards when the backend provides
  it.
- The selected mission actionability summary now falls back to loop handoff
  approval status when current-task or queue status is unavailable.
- No mutation or execution path changed; this only makes an already-projected
  contract visible to the operator.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is loop-state approval-status contract parity. This advances the
active `Phase 2 / P3_GOVERNANCE -> P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE`
line by making the mission loop contract carry approval posture directly:

- `src/francis/api/routes/missions.py` now includes `approval_status` on
  approval-aware loop stages and handoffs, sourced from the refreshed queue
  posture rather than stale mission meta.
- `apps/chat_ui/src/missions/index.ts` now preserves `approval_status` through
  `MissionLoopStage` and `MissionLoopHandoff` parsing so UI callers do not need
  to reconstruct the active gate state from sibling queue fields.
- `tests/test_api_missions.py` and `apps/chat_ui/src/missions/index.test.ts`
  now prove the pending and approved approval-status loop contracts.
- No execution behavior changed; this is a truthful contract/read-model
  improvement for the existing governed loop.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is approved-gate loop-state handoff parity. This advances the
active `Phase 2 / P3_GOVERNANCE -> P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE`
line by making mission detail loop state agree with the queue-derived approval
posture:

- `src/francis/api/routes/missions.py` now passes the fresh queue item into
  mission loop-state derivation and treats an approved exact-action approval as a
  clear gate with an `execute` / `run_linked_operation` handoff.
- Mission detail responses no longer show stale `plan` or `gate` handoffs when
  the local approval record has already moved to `approved` and the queue is
  eligible for one bounded governed advance.
- `tests/test_api_missions.py` now proves the approved-gate detail response
  aligns `mission`, `queue_item`, `current_task`, and `loop_state` around the
  same `run_linked_operation` next action.
- No new automatic execution path was added; the change only makes the existing
  operator-facing handoff truthful.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is mission-record approved-gate projection parity. This advances
the active `Phase 2 / P3_GOVERNANCE -> P7_EXECUTION -> P8_MEMORY ->
P1_INTERFACE` line by keeping mission detail and list payloads aligned with the
fresh queue-derived approval posture:

- `src/francis/api/routes/missions.py` now serializes approval id, decided
  approval status, prior approval status, replacement evidence, and advance
  operation context from the queue-derived mission posture when available.
- Mission create, get, list, patch, tick, deadletter, replacement, and advance
  responses now avoid stale `pending` approval status when the local approval
  record has already moved to `approved`, `rejected`, or `emergency`.
- `tests/test_api_missions.py` now proves `GET /missions/{id}` and
  `/missions/list` expose an approved exact-action gate as `approved` while the
  queue recommends the existing governed `run_linked_operation` handoff.
- No background autonomy path was added; the API only projects already-recorded
  governed approval state.

As of `2026-04-25`, the highest-confidence surface newly advanced in the current
Stage 3 line is approved-gate mission re-entry. This advances the active
`Phase 2 / P3_GOVERNANCE -> P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by
turning a decided exact-action approval into a truthful bounded rerun handoff
instead of leaving continuity stuck on stale pending-approval language:

- `src/francis/missions/store.py` now refreshes mission queue approval posture
  from local approval records across pending, approved, rejected, and emergency
  buckets before deriving mission actionability.
- Blocked missions whose exact approval is now `approved` recommend
  `run_linked_operation` through the existing governed mission runtime; rejected
  and emergency approval states remain review-only.
- `src/francis/world_state/snapshot.py` reads mission approval projections from
  all approval decision buckets so continuity and recent-mission surfaces do not
  preserve stale `pending` status after an operator decision.
- `apps/chat_ui/src/missions/index.ts` now preserves approval status, previous
  approval status, and bounded replacement evidence fields through the mission
  client contract.
- `tests/test_mission_store.py`,
  `tests/test_api_continuity.py`, and
  `apps/chat_ui/src/missions/index.test.ts` now prove the approved-gate re-entry
  contract without adding a background autonomy path.

As of `2026-04-24`, the highest-confidence surface newly advanced in the current
documentation/productization line is public GitHub discoverability. This does not
advance a runtime capability claim; it makes the public repository easier to find
and easier to engage with while preserving shipped-state truth:

- `README.md` now includes CI/build/posture badges, a concise "Why Watch Francis"
  section, and contribution guidance for roadmap-aligned public engagement.
- `.github/ISSUE_TEMPLATE/` now includes bug and roadmap-slice forms that require
  affected surface, trust-boundary, and validation details.
- `.github/PULL_REQUEST_TEMPLATE.md` now asks contributors to name roadmap
  surface, validation, governance/trust-boundary impact, UI screenshots, and
  residual risk.
- GitHub repository metadata now includes a truthful description, issues and
  discussions are enabled, discovery topics are set, and a `roadmap` label exists.
- `pyproject.toml` now describes Francis as a local-first, policy-guarded,
  auditable AI operator layer instead of implying finished colleague behavior.

As of `2026-04-24`, the highest-confidence surface newly advanced in the current
Stage 3 line is approval replacement mismatch key-scope review. This advances
the active `Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by making
replacement approval review more inspectable without exposing payload values or
adding a new mutation path:

- `src/francis/governance/approval_projection.py` now projects bounded
  `replacement_expected_payload_keys` and `replacement_previous_payload_keys`
  from mismatch artifacts.
- `apps/chat_ui/src/index.ts` and `apps/chat_ui/src/settings/index.ts` now
  preserve those fields in approval-list and world-state approval summaries.
- `apps/chat_ui/src/App.tsx` now shows mismatch key scope in approval review
  cards and the selected approval evidence panel.
- `tests/test_api_approvals.py`, `apps/chat_ui/src/index.test.ts`, and
  `apps/chat_ui/src/settings/index.test.ts` now prove the bounded key-scope
  contract.

As of `2026-04-24`, the highest-confidence surface newly advanced in the current
Stage 3 line is deadletter replacement artifact-kind continuity. This advances
the active `Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by keeping
replacement approval provenance visible across backend, continuity, and UI
review surfaces without adding a new mutation path:

- `src/francis/world_state/snapshot.py` now carries bounded
  `replacement_kind` from approval projection into mission queue, recent mission,
  and deadletter hold projections as `last_task_approval_replacement_kind`.
- `apps/chat_ui/src/settings/index.ts` now parses and presents that field in
  world-state and continuity deadletter contracts, including the shared
  replacement summary and review-label logic.
- `apps/chat_ui/src/App.tsx` now renders replacement artifact kind on
  deadletter cards and carries it through approval return context for the
  focused approval review.
- `tests/test_api_system_settings.py`, `tests/test_api_continuity.py`, and
  `apps/chat_ui/src/settings/index.test.ts` now prove the replacement-kind
  contract on the deadletter review path.

As of `2026-04-24`, the highest-confidence surface newly advanced in the current
Stage 3 line is deadletter replacement approval routing context. This advances
the active `Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by making
replacement review routing explicit without adding a new mutation path:

- `apps/chat_ui/src/settings/index.ts` now derives bounded deadletter approval
  review labels, distinguishing replacement approval review from ordinary
  approval review.
- `apps/chat_ui/src/App.tsx` now carries deadletter source, replacement reason,
  and changed-key context through the existing `onOpenApprovals` route and shows
  that context in the approval inspector only while the focused approval matches.
- `apps/chat_ui/src/settings/index.test.ts` now proves the shared deadletter
  presentation helper emits the replacement-specific review labels.

As of `2026-04-24`, the highest-confidence surface newly advanced in the current
Stage 3 line is deadletter refreshed-approval replacement evidence. This
advances the active `Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line
by preserving why a replacement approval exists when deadlettered work is
blocked behind a refreshed exact-action approval:

- `src/francis/governance/approval_projection.py` now reads bounded
  `mismatch.json` evidence for approval records and projects
  `replacement_reason`, `replacement_kind`, and changed top-level payload keys.
- `src/francis/world_state/snapshot.py` now carries that replacement evidence
  onto mission queue and deadletter items as last-task approval context before
  building continuity and world-state projections.
- `apps/chat_ui/src/index.ts`, `apps/chat_ui/src/settings/index.ts`, and
  `apps/chat_ui/src/App.tsx` now preserve and render the replacement reason and
  changed keys in approval and deadletter review surfaces.
- `tests/test_api_approvals.py`, `tests/test_api_continuity.py`,
  `tests/test_api_system_settings.py`, `apps/chat_ui/src/index.test.ts`, and
  `apps/chat_ui/src/settings/index.test.ts` now prove the bounded replacement
  evidence contract.

As of `2026-04-24`, the highest-confidence surface newly advanced in the current
Stage 3 line is deadletter refreshed-approval status continuity. This advances
the active `Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by
preserving whether a superseded approval had already been approved when a
deadlettered mission is waiting on a refreshed exact-action approval:

- `src/francis/world_state/snapshot.py` now enriches mission queue and
  deadletter items from the live pending-approval registry before building the
  continuity briefing and world-state projections, carrying
  `last_task_previous_approval_status` alongside the existing approval lineage.
- `apps/chat_ui/src/settings/index.ts` and `apps/chat_ui/src/App.tsx` now keep
  that prior approval status through the shared deadletter presentation contract
  and show it directly in bounded deadletter cards.
- `tests/test_api_continuity.py`,
  `tests/test_api_system_settings.py`, and
  `apps/chat_ui/src/settings/index.test.ts` now prove the refreshed-approval
  deadletter contract end to end, including `previous_approval_status:
  approved`.

As of `2026-04-23`, the highest-confidence surface newly advanced in the current
Stage 3 line is deadletter approval-lineage review routing. This advances the
active `Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by preserving
what might unblock deadlettered work when approval replacement history exists:

- `apps/chat_ui/src/settings/index.ts` now derives a shared deadletter
  `approval_summary` from the current approval id, approval status, and prior
  approval lineage preserved in mission continuity/world-state payloads.
- `apps/chat_ui/src/App.tsx` now renders previous approval lineage in both
  deadletter card surfaces and exposes `Open previous approval` when the
  deadlettered mission still carries a superseded approval reference.
- `apps/chat_ui/src/settings/index.test.ts` now proves the shared deadletter
  presentation helper emits the expected approval-lineage summary.

As of `2026-04-23`, the highest-confidence surface newly advanced in the current
Stage 3 line is deadletter approval-link recovery routing. This advances the
active `Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by keeping
deadletter review attached to the exact governed approval target when a mission
is deadlettered while approval is still pending:

- `apps/chat_ui/src/settings/index.ts` now preserves deadletter approval linkage
  through the continuity parser and shared deadletter presentation contract,
  instead of dropping `last_task_approval_id`, previous approval lineage, and
  approval status on the continuity path.
- `apps/chat_ui/src/App.tsx` now renders exact approval id/status on both
  deadletter card surfaces and routes `Review approval` directly into the
  existing approval inspector with mission/task return context.
- `tests/test_api_continuity.py`,
  `tests/test_api_system_settings.py`, and
  `apps/chat_ui/src/settings/index.test.ts` now prove that deadletter review
  preserves the pending approval target from snapshot to UI contract.

As of `2026-04-23`, the highest-confidence surface newly advanced in the current
Stage 3 line is deadletter receipt narrative clarity. This advances the active
`Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by reducing the last
manual reconstruction step in bounded deadletter review while preserving the raw
receipt trail underneath:

- `apps/chat_ui/src/settings/index.ts` now derives `history_summary` from the
  existing bounded `history_tail`, translating common receipt sequences such as
  deadletter status transitions, linked-task transitions, and advance receipts
  into direct operator-readable summaries.
- `apps/chat_ui/src/App.tsx` now renders that derived receipt narrative in both
  Shift Briefing deadletter review and overview deadletter cards before the raw
  receipt entries.
- `apps/chat_ui/src/settings/index.test.ts` now proves the shared deadletter
  presentation helper emits the expected narrative for the common
  status-changed-plus-deadletter-reason sequence.

As of `2026-04-23`, the highest-confidence surface newly advanced in the current
Stage 3 line is bounded deadletter history-tail visibility. This advances the
active `Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by making
deadletter recovery show the latest persisted mission-history trail instead of
forcing the operator to reconstruct it from counts and separate inspector
navigation:

- `src/francis/world_state/snapshot.py` now attaches a bounded `history_tail`
  to deadlettered missions using the same persisted mission history that powers
  the full mission inspector.
- `apps/chat_ui/src/settings/index.ts` now preserves that `history_tail`
  through both world-state and continuity deadletter contracts and keeps the
  shared presentation helper typed.
- `apps/chat_ui/src/App.tsx` now renders the last two history receipts directly
  inside Shift Briefing deadletter review and overview deadletter cards.
- `tests/test_api_continuity.py`, `tests/test_api_system_settings.py`, and
  `apps/chat_ui/src/settings/index.test.ts` now prove the bounded history-tail
  contract end to end.

As of `2026-04-23`, the highest-confidence surface newly advanced in the current
Stage 3 line is deadletter receipt linkage in bounded continuity surfaces. This
advances the active `Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line
by making deadletter review carry mission-history evidence instead of only task
state snapshots:

- `src/francis/world_state/snapshot.py` now attaches `history_count`,
  `latest_history_event`, and `latest_history_ts` to deadlettered missions
  before building both world-state and continuity deadletter surfaces.
- `apps/chat_ui/src/settings/index.ts` now preserves that receipt summary on
  world-state deadletter items, continuity deadletter items, and the shared
  `presentMissionDeadletterItems` contract.
- `apps/chat_ui/src/App.tsx` now shows receipt count and latest receipt
  event/time in both deadletter cards so bounded review stays evidence-backed.
- `tests/test_api_continuity.py`, `tests/test_api_system_settings.py`, and
  `apps/chat_ui/src/settings/index.test.ts` now prove the receipt-summary
  contract end to end.

As of `2026-04-23`, the highest-confidence surface newly advanced in the current
Stage 3 line is continuity deadletter evidence parity. This advances the active
`Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by making early
continuity deadletter review preserve the last attempted task identity and the
exact blocked-result evidence that operators need for recovery:

- `src/francis/world_state/snapshot.py` now includes `last_task_id`,
  `last_task_status`, `last_task_result_status`, and `last_task_gate` in the
  continuity `deadletter_preview` payload.
- `apps/chat_ui/src/settings/index.ts` now preserves those fields on
  `ContinuityBriefingDeadletterItem` and through
  `presentMissionDeadletterItems`.
- `apps/chat_ui/src/App.tsx` now shows those task/result details in Shift
  Briefing deadletter review and exposes `Open last task` when the preview has
  a concrete task target.
- `tests/test_api_continuity.py` and
  `apps/chat_ui/src/settings/index.test.ts` now prove the backend/UI contract
  for continuity deadletter evidence.

As of `2026-04-23`, the highest-confidence surface newly advanced in the current
Stage 3 line is deadletter preview truthfulness. This advances the active
`Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by making early
deadletter surfaces preserve why continuation failed, what review action is
expected next, and whether additional deadlettered missions remain hidden:

- `apps/chat_ui/src/settings/index.ts` now exports
  `presentMissionDeadletterItems`, which normalizes reason fields across world
  state and continuity deadletter payloads, orders more actionable items first,
  and reports hidden counts for bounded views.
- `apps/chat_ui/src/App.tsx` now uses that contract for both the Shift Briefing
  deadletter review panel and the overview deadletter panel, showing action,
  latest activity, updated time, and hidden-count disclosure.
- `apps/chat_ui/src/settings/index.test.ts` now proves the deadletter
  presentation helper preserves reason normalization and bounded ordering.

As of `2026-04-23`, the highest-confidence surface newly advanced in the current
Stage 3 line is mission queue prioritization parity. This advances the active
`Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by making bounded
queue surfaces recover-first instead of first-come-first-shown:

- `apps/chat_ui/src/missions/index.ts` now exports `presentMissionQueue`, which
  ranks pending-approval, dependency-blocked, and other review-required missions
  ahead of already-eligible work while reporting hidden counts.
- `apps/chat_ui/src/App.tsx` now uses that ordering for the return-to-work queue
  lead, mission selection candidates, and the bounded Mission Queue card list.
- `apps/chat_ui/src/missions/index.test.ts` now proves the queue view surfaces
  recovery-required work first and keeps hidden-count reporting truthful.

As of `2026-04-23`, the highest-confidence surface newly advanced in the current
Stage 3 line is mission queue-run recovery result parity. This advances the
active `Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by making
batch advancement results as actionable as the selected mission inspector:

- `src/francis/api/routes/missions.py` now includes `queue_item` in each
  `/missions/run_once` result projection.
- `apps/chat_ui/src/missions/index.ts` now parses `queue_item` on
  `MissionRunOnceResult`.
- `apps/chat_ui/src/App.tsx` now renders run-once result actionability,
  approval/dependency posture, last advance outcome, and recovery links to the
  existing mission, operation, and approval inspectors.
- `tests/test_api_missions.py` and `apps/chat_ui/src/missions/index.test.ts`
  now prove run-once results preserve queue actionability through the API and
  browser parser.

As of `2026-04-22`, the highest-confidence surface newly advanced in the current
Stage 3 line is selected mission recovery action routing. This advances the
active `Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by turning
non-eligible mission states into concrete review paths instead of dead-end
disabled controls:

- `apps/chat_ui/src/missions/index.ts` now preserves approval handoff and
  last-advance receipt metadata on `MissionQueueItem`.
- `apps/chat_ui/src/App.tsx` now renders a Mission Actionability panel for the
  selected mission, showing recommended action, advance posture, approval state,
  dependency counts, and last advance outcome.
- The same panel routes to existing approval, mission, and operation inspectors
  for review-only recovery; it does not add a new mutation path.
- `tests/test_api_missions.py` and `apps/chat_ui/src/missions/index.test.ts`
  now prove approval handoff and last-advance metadata survive through mission
  detail and browser parsing.

As of `2026-04-22`, the highest-confidence surface newly advanced in the current
Stage 3 line is mission inspector advance contract parity. This advances the
active `Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by bringing
the selected mission detail surface under the same explicit actionability
contract as the queue and briefing surfaces:

- `src/francis/api/routes/missions.py` now includes `queue_item` in mission
  detail projections and reuses that projection for `GET /missions/{id}`.
- `apps/chat_ui/src/missions/index.ts` now parses `queue_item` on mission
  detail, create, and advance response envelopes.
- `apps/chat_ui/src/App.tsx` now renders selected mission action posture from
  `queue_item.advance` and disables mutation for dependency, approval, trust,
  completion-review, and other non-eligible states.
- `tests/test_api_missions.py` and `apps/chat_ui/src/missions/index.test.ts`
  now prove mission detail payloads carry ready/review-required queue
  actionability through the API and browser parser.

As of `2026-04-22`, the highest-confidence surface newly advanced in the current
Stage 3 line is mission queue advance contract parity. This advances the active
`Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line by keeping the
dedicated queue runner path aligned with the Shift Briefing contract:

- `apps/chat_ui/src/missions/index.ts` now preserves the `advance` projection on
  mission queue items returned by `/missions/run_once`.
- `apps/chat_ui/src/App.tsx` now renders ORB Mission Queue advance posture from
  `advance.eligible`, disabling mutation for dependency, approval, trust, and
  other review-required blockers.
- `tests/test_api_missions.py` and `apps/chat_ui/src/missions/index.test.ts`
  now prove the queue-run path carries ready and blocked advance eligibility
  through the API and browser parser.

As of `2026-04-22`, the highest-confidence surface newly advanced in the current
Stage 3 line is explicit mission advance eligibility for Shift Briefing. This
advances the active `Phase 2 / P7_EXECUTION -> P8_MEMORY -> P1_INTERFACE` line
by making actionability a backend contract instead of a UI string heuristic:

- `src/francis/missions/store.py` now emits an `advance` projection on mission
  queue items with `eligible`, `action`, `target_id`, and `reason` fields.
- `src/francis/missions/runtime.py` now reuses the store's
  `AUTO_ADVANCE_ACTIONS`, so the queue runner and exposed contract share the
  same bounded action set.
- `src/francis/world_state/snapshot.py`,
  `apps/chat_ui/src/settings/index.ts`, and `apps/chat_ui/src/App.tsx` now carry
  that projection into Shift Briefing and render advance controls only when
  `advance.eligible` is true.
- `tests/test_mission_store.py`, `tests/test_api_continuity.py`,
  `tests/test_api_system_settings.py`, and
  `apps/chat_ui/src/settings/index.test.ts` now prove ready missions are
  eligible while dependency and approval blockers remain non-mutating.

As of `2026-04-22`, the highest-confidence surface newly advanced in the current
Stage 3 line is bounded Shift Briefing actionability. This advances the active
`Phase 2 / P7_EXECUTION -> P1_INTERFACE` line by letting ready mission handoff
cards use the same governed `/missions/{id}/advance` path as the mission
inspector:

- `apps/chat_ui/src/App.tsx` now renders a bounded advance control on Shift
  Briefing focus cards only when the recommendation is `create_first_operation`
  or `run_linked_operation`.
- Dependency blockers and approval blockers stay non-mutating from the briefing
  card; they keep their dependency/approval review actions.
- The control respects the existing operator-mode write posture and busy-state
  guards used by the ORB mission inspector and queue runner.

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

Latest targeted validation for the `2026-04-26` Stage 3 mission loop plan receipt rendering slice:

- `cd apps\chat_ui; npm run test`
  Result: `45 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission loop plan receipt handoff slice:

- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py::test_mission_advance_runs_linked_queued_operation -q`
  Result: `passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\missions\index.test.ts`
  Result: `11 passed`
- `python -m ruff check src\francis\api\routes\missions.py tests\test_api_missions.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\missions.py tests\test_api_missions.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `45 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 operation plan receipt detail slice:

- `cd apps\chat_ui; npm run test`
  Result: `45 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 operation plan summary interface slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\operations\index.test.ts`
  Result: `5 passed`
- `cd apps\chat_ui; npm run test`
  Result: `45 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 world-state activity trace-handle slice:

- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_system_settings.py::test_system_world_state_reports_mission_counts_and_continuity -q`
  Result: `passed`
- `python -m ruff check src\francis\world_state\snapshot.py tests\test_api_system_settings.py`
  Result: `passed`
- `python -m ruff format --check src\francis\world_state\snapshot.py tests\test_api_system_settings.py`
  Result: `passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\settings\index.test.ts`
  Result: `11 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `45 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 operation audit trace handles slice:

- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py::test_operations_run_executes_plan_create tests\test_api_operations.py::test_operations_plugin_run_action_executes -q`
  Result: `passed`
- `python -m ruff check src\francis\agent\executor.py src\francis\operations\runtime.py src\francis\api\routes\operations.py tests\test_api_operations.py`
  Result: `passed`
- `python -m ruff format --check src\francis\agent\executor.py src\francis\operations\runtime.py src\francis\api\routes\operations.py tests\test_api_operations.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 plan execution trace handles slice:

- `python -m ruff check src\francis\agent\executor.py tests\test_api_operations.py tests\test_api_missions.py tests\test_api_continuity.py`
  Result: `passed`
- `python -m ruff format --check src\francis\agent\executor.py tests\test_api_operations.py tests\test_api_missions.py tests\test_api_continuity.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py::test_operations_run_executes_plan_create tests\test_api_operations.py::test_operations_plugin_run_action_executes tests\test_api_operations.py::test_operations_run_surfaces_failed_mission_memory_receipt tests\test_api_missions.py::test_mission_detail_surfaces_failed_operation_memory_receipt tests\test_api_continuity.py::test_continuity_briefing_surfaces_failed_mission_recovery -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 approved mission operation receipt posture slice:

- `python -m ruff check src\francis\operations\runtime.py src\francis\api\routes\operations.py tests\test_api_operations.py`
  Result: `passed`
- `python -m ruff format --check src\francis\operations\runtime.py src\francis\api\routes\operations.py tests\test_api_operations.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py::test_operations_approved_mission_run_receipt_preserves_approval_posture -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\operations\index.test.ts`
  Result: `5 passed`
- `cd apps\chat_ui; npm run test`
  Result: `45 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 Shift Briefing memory receipt approval-status client slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\settings\index.test.ts`
  Result: `11 passed`
- `cd apps\chat_ui; npm run test`
  Result: `45 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` domain registry permission-gate slice:

- `python -m ruff check src\francis\api\routes\domains.py tests\test_api_domains.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\domains.py tests\test_api_domains.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_domains.py -q`
  Result: `3 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_contract_chat_ui.py -q`
  Result: `1 passed`

Latest targeted validation for the `2026-04-26` direct supervised-exec permission-gate slice:

- `python -m ruff check src\francis\governance\api_permission_gate.py src\francis\api\routes\supervised_exec.py tests\unit\test_api_permission_gate.py tests\test_api_supervised_exec.py`
  Result: `passed`
- `python -m ruff format --check src\francis\governance\api_permission_gate.py src\francis\api\routes\supervised_exec.py tests\unit\test_api_permission_gate.py tests\test_api_supervised_exec.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\unit\test_api_permission_gate.py tests\test_api_supervised_exec.py -q`
  Result: `9 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_supervised_exec.py tests\test_api_operations.py::test_operations_supervised_exec_seals_secret_command_and_redacts_artifacts tests\test_api_operations.py::test_operations_supervised_exec_refreshes_stale_approval tests\unit\test_api_permission_gate.py tests\unit\test_scope_checker.py -q`
  Result: `13 passed`

Latest targeted validation for the `2026-04-26` API permission gate decision contract slice:

- `python -m ruff check src\francis\credentials\scope_checker.py src\francis\governance\api_permission_gate.py tests\unit\test_scope_checker.py tests\unit\test_api_permission_gate.py`
  Result: `passed`
- `python -m ruff format --check src\francis\credentials\scope_checker.py src\francis\governance\api_permission_gate.py tests\unit\test_scope_checker.py tests\unit\test_api_permission_gate.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\unit\test_scope_checker.py tests\unit\test_api_permission_gate.py -q`
  Result: `6 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_approvals.py tests\test_api_credentials.py tests\unit\test_governance_redaction.py tests\unit\test_scope_checker.py tests\unit\test_api_permission_gate.py -q`
  Result: `22 passed`

Latest targeted validation for the `2026-04-26` delegation creation audit context slice:

- `python -m ruff check src\francis\agent\delegation.py tests\unit\test_delegation_audit.py tests\unit\test_workers_runner.py tests\unit\test_daemon_runner.py tests\test_api_operations.py`
  Result: `passed`
- `python -m ruff format --check src\francis\agent\delegation.py tests\unit\test_delegation_audit.py tests\unit\test_workers_runner.py tests\unit\test_daemon_runner.py tests\test_api_operations.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\unit\test_delegation_audit.py -q`
  Result: `1 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\unit\test_delegation_audit.py tests\unit\test_workers_runner.py tests\unit\test_daemon_runner.py tests\test_api_operations.py::test_operations_create_list_get_cancel tests\test_api_operations.py::test_operations_operator_surfaces_redact_secret_text -q`
  Result: `7 passed`

Latest targeted validation for the `2026-04-26` plan-create receipt summary slice:

- `python -m ruff check src\francis\agent\executor.py tests\test_api_operations.py`
  Result: `passed`
- `python -m ruff format --check src\francis\agent\executor.py tests\test_api_operations.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py::test_operations_run_executes_plan_create -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-26` credential actor receipt identity slice:

- `python -m ruff check src\francis\api\routes\credentials.py tests\test_api_credentials.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\credentials.py tests\test_api_credentials.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_credentials.py -q`
  Result: `7 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_approvals.py tests\test_api_credentials.py tests\unit\test_governance_redaction.py -q`
  Result: `16 passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission advance operation-identity UI contract slice:

- `cd apps\chat_ui; npm run test`
  Result: `41 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission advance operation-identity slice:

- `python -m ruff check src\francis\missions\store.py src\francis\missions\runtime.py tests\test_api_missions.py`
  Result: `passed`
- `python -m ruff format --check src\francis\missions\store.py src\francis\missions\runtime.py tests\test_api_missions.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py::test_mission_advance_creates_first_operation_with_receipt -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 memory timeline loop projection slice:

- `python -m ruff check src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_memory_timeline.py -q`
  Result: `6 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_chat.py tests\test_api_memory_timeline.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 chat mission-ingress continuity metadata slice:

- `python -m ruff check src\francis\api\routes\chat.py tests\test_api_chat.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\chat.py tests\test_api_chat.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_chat.py -q`
  Result: `3 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_chat.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 world-state approval incident loop-handle evidence slice:

- `python -m ruff check src\francis\world_state\snapshot.py tests\test_api_system_settings.py`
  Result: `passed`
- `python -m ruff format --check src\francis\world_state\snapshot.py tests\test_api_system_settings.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_system_settings.py::test_system_world_state_surfaces_exact_pending_approval_for_blocked_mission -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 approval gate loop-handle projection slice:

- `python -m ruff check src\francis\governance\approval_projection.py tests\test_api_approvals.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_approvals.py -q`
  Result: `7 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_approvals.py tests\test_api_credentials.py tests\unit\test_governance_redaction.py -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `41 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check -- src\francis\governance\approval_projection.py tests\test_api_approvals.py apps\chat_ui\src\index.ts apps\chat_ui\src\index.test.ts apps\chat_ui\src\settings\index.ts apps\chat_ui\src\settings\index.test.ts apps\chat_ui\src\App.tsx`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 operations receipt filter slice:

- `.\.venv\Scripts\python.exe -m ruff check src\francis\api\routes\operations.py tests\test_api_operations.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_operations.py::test_operations_plugin_run_action_executes tests\test_api_operations.py::test_operations_list_and_export_filter_artifact_receipts -q`
  Result: `2 passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_operations.py -q`
  Result: `20 passed`
- `cd apps\chat_ui; npm run test`
  Result: `41 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check -- src\francis\api\routes\operations.py tests\test_api_operations.py apps\chat_ui\src\operations\index.ts apps\chat_ui\src\operations\index.test.ts docs\operations\COMPLETION_LEDGER.md`
  Result: `passed` (line-ending warning only for existing UI file normalization)

Latest targeted validation for the `2026-04-26` Stage 3 explanation receipt filter slice:

- `.\.venv\Scripts\python.exe -m ruff check src\francis\api\routes\explanation.py tests\test_api_explanation.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff format --check src\francis\api\routes\explanation.py tests\test_api_explanation.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_explanation.py -q`
  Result: `passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\explanation_explorer\index.test.ts`
  Result: `2 passed`
- `cd apps\chat_ui; npm run test`
  Result: `41 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 operation explanation evidence interface slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\explanation_evidence\index.test.ts`
  Result: `3 passed`
- `cd apps\chat_ui; npm run test`
  Result: `44 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --cached --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 explanation trace-link contract slice:

- `.\.venv\Scripts\python.exe -m ruff check src\francis\api\routes\explanation.py tests\test_api_explanation.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_explanation.py -q`
  Result: `2 passed`
- `cd apps\chat_ui; npm run test`
  Result: `40 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check -- src\francis\api\routes\explanation.py tests\test_api_explanation.py apps\chat_ui\src\explanation_explorer\index.ts apps\chat_ui\src\explanation_explorer\index.test.ts apps\chat_ui\package.json docs\operations\COMPLETION_LEDGER.md`
  Result: `passed` (line-ending warnings only for existing CRLF/LF normalization)

Latest targeted validation for the `2026-04-26` Stage 3 artifact inspection recovery guidance slice:

- `.\.venv\Scripts\python.exe -m ruff check src\francis\api\routes\artifacts.py tests\test_api_artifacts.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_artifacts.py -q`
  Result: `4 passed`
- `cd apps\chat_ui; npm run test`
  Result: `38 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check -- src\francis\api\routes\artifacts.py tests\test_api_artifacts.py apps\chat_ui\src\artifacts\index.ts apps\chat_ui\src\artifacts\index.test.ts apps\chat_ui\src\artifacts\ArtifactInspectionPanel.tsx docs\operations\COMPLETION_LEDGER.md`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission receipt artifact inspection interface slice:

- `cd apps\chat_ui; npm run test`
  Result: `38 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 operation artifact inspection interface slice:

- `cd apps\chat_ui; npm run test`
  Result: `38 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 artifact inspect UI client contract slice:

- `cd apps\chat_ui; npm run test`
  Result: `38 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 artifact inspection contract slice:

- `.\.venv\Scripts\python.exe -m ruff check src\francis\api\routes\artifacts.py src\francis\api\app.py tests\test_api_artifacts.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_artifacts.py -q`
  Result: `4 passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_artifacts.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 operation run memory receipt notice slice:

- `cd apps\chat_ui; npm run test`
  Result: `34 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 operation run/artifact memory evidence slice:

- `cd apps\chat_ui; npm run test`
  Result: `34 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 operation client memory receipt contract slice:

- `cd apps\chat_ui; npm run test`
  Result: `34 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_operations.py::test_operations_run_surfaces_completed_mission_memory_receipt -q`
  Result: `1 passed`
- `git diff --check`
  Result: `passed` (Git emitted a line-ending warning for `apps/chat_ui/src/operations/index.ts`)

Latest targeted validation for the `2026-04-25` Stage 3 mission memory receipt handoff slice:

- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py::test_mission_advance_runs_linked_queued_operation tests\test_api_missions.py::test_mission_run_once_executes_linked_queued_operation -q`
  Result: `2 passed`
- `cd apps\chat_ui; npm run test`
  Result: `34 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py tests\test_api_operations.py tests\test_api_memory_timeline.py -q`
  Result: `85 passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 operation run memory receipt handoff slice:

- `.\.venv\Scripts\python.exe -m pytest tests\test_api_operations.py::test_operations_run_surfaces_completed_mission_memory_receipt tests\test_api_memory_timeline.py::test_memory_timeline_finds_completed_mission_operation_receipt -q`
  Result: `2 passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_operations.py tests\test_api_memory_timeline.py -q`
  Result: `24 passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 memory timeline run/artifact retrieval slice:

- `.\.venv\Scripts\python.exe -m pytest tests\test_api_memory_timeline.py -q`
  Result: `5 passed`
- `cd apps\chat_ui; npm run test`
  Result: `34 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py tests\test_api_memory_timeline.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 memory timeline operation-status filter slice:

- `.\.venv\Scripts\python.exe -m pytest tests\test_api_memory_timeline.py -q`
  Result: `6 passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\memory_timeline\index.test.ts`
  Result: `2 passed`
- `.\.venv\Scripts\python.exe -m ruff check --no-cache src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff format --check --no-cache src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py tests\test_api_memory_timeline.py -q`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `44 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 mission queue operation projection slice:

- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py::test_mission_run_once_advances_safe_queue_actions tests\test_api_missions.py::test_mission_run_once_executes_linked_queued_operation tests\test_api_missions.py::test_mission_store_run_once_uses_bounded_runtime_path -q`
  Result: `3 passed`
- `cd apps\chat_ui; npm run test`
  Result: `34 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 operation create mission-link UI contract slice:

- `cd apps\chat_ui; npm run test`
  Result: `34 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_operations.py tests\test_api_missions.py -q`
  Result: `43 passed`

Latest targeted validation for the `2026-04-25` Stage 3 chat mission ingress interface slice:

- `cd apps\chat_ui; npm run test`
  Result: `33 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_chat.py tests\test_api_contract_chat_ui.py -q`
  Result: `4 passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `61 passed`

Latest targeted validation for the `2026-04-25` Stage 3 Shift Briefing memory receipt interface slice:

- `cd apps\chat_ui; npm run test`
  Result: `31 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 mission continuity memory receipt projection slice:

- `.\.venv\Scripts\python.exe -m ruff format --no-cache src\francis\world_state\snapshot.py tests\test_api_continuity.py`
  Result: `2 files left unchanged`
- `.\.venv\Scripts\python.exe -m ruff check --no-cache src\francis\world_state\snapshot.py tests\test_api_continuity.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests/test_api_continuity.py::test_continuity_briefing_reports_ready_stage3_mission_posture -q`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests/test_api_missions.py tests/test_api_continuity.py tests/test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 completed mission operation memory receipt slice:

- `python -m ruff format --no-cache src\francis\operations\runtime.py tests\test_api_memory_timeline.py`
  Result: `src\francis\operations\runtime.py left unchanged; tests\test_api_memory_timeline.py reformatted after approved retry`
- `python -m ruff check --no-cache src\francis\operations\runtime.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_memory_timeline.py::test_memory_timeline_finds_completed_mission_operation_receipt -q`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_memory_timeline.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 failed mission detail memory receipt projection slice:

- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py::test_mission_detail_surfaces_failed_operation_memory_receipt -q`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff check --no-cache src\francis\memory\mission_receipts.py src\francis\api\routes\missions.py tests\test_api_missions.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff format --check --no-cache src\francis\memory\mission_receipts.py src\francis\api\routes\missions.py tests\test_api_missions.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 failed mission continuity receipt projection slice:

- `.\.venv\Scripts\python.exe -m pytest tests\test_api_continuity.py::test_continuity_briefing_surfaces_failed_mission_recovery -q`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff format --no-cache tests\test_api_continuity.py`
  Result: `1 file left unchanged`
- `.\.venv\Scripts\python.exe -m ruff check --no-cache tests\test_api_continuity.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 failed mission operation memory receipt slice:

- `.\.venv\Scripts\python.exe -m ruff check src\francis\operations\runtime.py tests\test_api_operations.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff format --check src\francis\operations\runtime.py tests\test_api_operations.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_operations.py::test_operations_run_surfaces_failed_mission_memory_receipt -q`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_operations.py::test_operations_run_surfaces_completed_mission_memory_receipt tests\test_api_operations.py::test_operations_run_surfaces_failed_mission_memory_receipt tests\test_api_memory_timeline.py::test_memory_timeline_finds_completed_mission_operation_receipt -q`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_operations.py tests\test_api_memory_timeline.py -q`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 memory evidence UI contract slice:

- `cd apps\chat_ui; npm run test`
  Result: `30 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 terminal status memory evidence interface slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\memory_evidence\index.test.ts`
  Result: `4 passed`
- `cd apps\chat_ui; npm run test`
  Result: `45 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission loop receipt-handle projection slice:

- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py::test_mission_linked_plugin_run_surfaces_operation_trace tests\test_api_missions.py::test_mission_linked_supervised_exec_surfaces_artifact_handle -q`
  Result: `passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\missions\index.test.ts`
  Result: `11 passed`
- `.\.venv\Scripts\python.exe -m ruff check --no-cache src\francis\api\routes\missions.py tests\test_api_missions.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff format --check --no-cache src\francis\api\routes\missions.py tests\test_api_missions.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `45 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 ORB mission loop receipt-handle rendering slice:

- `cd apps\chat_ui; npm run test`
  Result: `45 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission loop artifact inspection slice:

- `cd apps\chat_ui; npm run test`
  Result: `45 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 memory timeline loop handle projection slice:

- `.\.venv\Scripts\python.exe -m ruff format --no-cache src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `2 files left unchanged`
- `.\.venv\Scripts\python.exe -m ruff check --no-cache src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_memory_timeline.py -q`
  Result: `6 passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\memory_timeline\index.test.ts`
  Result: `2 passed`
- `cd apps\chat_ui; npm run test`
  Result: `45 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py tests\test_api_memory_timeline.py -q`
  Result: `failed once in tests/test_api_missions.py::test_mission_deadletter_endpoint_moves_blocked_mission_cleanly; isolated rerun of that test passed; same bundle rerun passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission tick timestamp-idempotence slice:

- `.\.venv\Scripts\python.exe -m ruff format --no-cache src\francis\missions\store.py src\francis\operations\runtime.py src\francis\agent\executor.py src\francis\api\routes\operations.py tests\test_mission_store.py`
  Result: `5 files left unchanged`
- `.\.venv\Scripts\python.exe -m ruff check --no-cache src\francis\missions\store.py src\francis\operations\runtime.py src\francis\agent\executor.py src\francis\api\routes\operations.py tests\test_mission_store.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_mission_store.py tests\test_api_missions.py::test_mission_deadletter_endpoint_moves_blocked_mission_cleanly -q`
  Result: `7 passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py -q`
  Result: `26 passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py tests\test_api_operations.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `93 passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission memory receipt approval-status projection slice:

- `.\.venv\Scripts\python.exe -m ruff format --no-cache src\francis\memory\mission_receipts.py tests\test_mission_receipts.py`
  Result: `2 files left unchanged`
- `.\.venv\Scripts\python.exe -m ruff check --no-cache src\francis\memory\mission_receipts.py tests\test_mission_receipts.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_mission_receipts.py -q`
  Result: `1 passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\missions\index.test.ts`
  Result: `11 passed`
- `cd apps\chat_ui; npm run test`
  Result: `45 passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_mission_receipts.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission memory receipt references slice:

- `.\.venv\Scripts\python.exe -m ruff format --no-cache src\francis\memory\mission_receipts.py tests\test_mission_receipts.py`
  Result: `2 files left unchanged`
- `.\.venv\Scripts\python.exe -m ruff check --no-cache src\francis\memory\mission_receipts.py tests\test_mission_receipts.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_mission_receipts.py -q`
  Result: `1 passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py::test_mission_linked_operation_run_updates_history_and_status tests\test_api_missions.py::test_mission_detail_surfaces_failed_operation_memory_receipt tests\test_api_continuity.py::test_continuity_briefing_reports_ready_stage3_mission_posture tests\test_api_continuity.py::test_continuity_briefing_surfaces_failed_mission_recovery -q`
  Result: `4 passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_mission_receipts.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `63 passed`

Latest targeted validation for the `2026-04-25` continuity-ledger memory reference projection slice:

- `python -m ruff format --no-cache src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `2 files left unchanged`
- `python -m ruff check --no-cache src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_memory_timeline.py tests\unit\test_governance_redaction.py -q`
  Result: `6 passed`

Latest targeted validation for the `2026-04-25` Stage 3 operation memory evidence interface slice:

- `cd apps\chat_ui; npm run test`
  Result: `27 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_memory_timeline.py tests\unit\test_governance_redaction.py -q`
  Result: `5 passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 memory timeline redaction and context projection slice:

- `python -m ruff format --no-cache src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `2 files left unchanged`
- `python -m ruff check --no-cache src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_memory_timeline.py tests\unit\test_governance_redaction.py -q`
  Result: `5 passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\memory_timeline\index.test.ts`
  Result: `2 passed`
- `cd apps\chat_ui; npm run test`
  Result: `27 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `61 passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 current-task receipt-status continuity slice:

- `pytest tests/test_api_missions.py::test_mission_linked_governance_hold_updates_blocked_state tests/test_api_continuity.py::test_continuity_briefing_surfaces_handoff_and_recent_completion -q`
  Result: `2 passed`
- `python -m ruff check src/francis/api/routes/missions.py src/francis/world_state/snapshot.py tests/test_api_missions.py tests/test_api_continuity.py`
  Result: `passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\missions\index.test.ts src\settings\index.test.ts`
  Result: `21 passed`
- `cd apps\chat_ui; npm test`
  Result: `25 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 mission loop trace receipt-status slice:

- `pytest tests/test_api_missions.py::test_mission_linked_governance_hold_updates_blocked_state -q`
  Result: `passed`
- `python -m ruff check src/francis/api/routes/missions.py tests/test_api_missions.py`
  Result: `passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\missions\index.test.ts`
  Result: `11 passed`
- `cd apps\chat_ui; npm test`
  Result: `25 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 operation detail receipt-handle visibility slice:

- `cd apps\chat_ui; npm run test`
  Result: `25 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 operation receipt handle projection slice:

- `pytest tests/test_api_operations.py::test_operations_plugin_run_action_executes tests/test_api_operations.py::test_operations_git_push_refreshes_approval_when_remote_changes tests/test_api_missions.py::test_mission_linked_plugin_run_surfaces_operation_trace tests/test_api_missions.py::test_mission_linked_supervised_exec_surfaces_artifact_handle -q`
  Result: `4 passed`
- `cd apps\chat_ui; npm run test`
  Result: `25 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 operation receipt trace projection slice:

- `pytest tests/test_api_operations.py::test_operations_plugin_run_action_executes tests/test_api_missions.py::test_mission_linked_plugin_run_surfaces_operation_trace tests/test_api_missions.py::test_mission_run_once_results_preserve_advance_trace -q`
  Result: `3 passed`
- `cd apps\chat_ui; npm run test`
  Result: `25 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 mission queue-run result trace visibility slice:

- `pytest tests/test_api_missions.py::test_mission_run_once_results_preserve_advance_trace tests/test_api_missions.py::test_mission_run_once_error_records_preserve_advance_context tests/test_api_missions.py::test_mission_run_once_advances_safe_queue_actions -q`
  Result: `3 passed`
- `cd apps\chat_ui; npm run test`
  Result: `25 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 mission queue-run failure trace visibility slice:

- `pytest tests/test_api_missions.py::test_mission_run_once_error_records_preserve_advance_context tests/test_api_missions.py::test_mission_run_once_reports_failed_status_for_runtime_errors tests/test_api_missions.py::test_mission_run_once_advances_safe_queue_actions -q`
  Result: `3 passed`
- `cd apps\chat_ui; npm run test`
  Result: `25 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 mission queue-run failure context parity slice:

- `pytest tests/test_api_missions.py::test_mission_run_once_error_records_preserve_advance_context tests/test_api_missions.py::test_mission_run_once_reports_failed_status_for_runtime_errors tests/test_api_missions.py::test_mission_run_once_advances_safe_queue_actions -q`
  Result: `3 passed`
- `cd apps\chat_ui; npm run test`
  Result: `25 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 mission queue-run request identity visibility slice:

- `pytest tests/test_api_missions.py::test_mission_mutation_routes_are_blocked_in_observe_mode tests/test_api_missions.py::test_mission_run_once_reports_failed_status_for_runtime_errors tests/test_api_missions.py::test_mission_run_once_advances_safe_queue_actions tests/test_api_missions.py::test_mission_run_once_executes_linked_queued_operation tests/test_api_missions.py::test_mission_store_run_once_uses_bounded_runtime_path -q`
  Result: `5 passed`
- `cd apps\chat_ui; npm run test`
  Result: `25 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 mission queue-run top-level status truth slice:

- `pytest tests/test_api_missions.py::test_mission_mutation_routes_are_blocked_in_observe_mode tests/test_api_missions.py::test_mission_run_once_reports_failed_status_for_runtime_errors tests/test_api_missions.py::test_mission_run_once_advances_safe_queue_actions tests/test_api_missions.py::test_mission_run_once_executes_linked_queued_operation tests/test_api_missions.py::test_mission_store_run_once_uses_bounded_runtime_path -q`
  Result: `5 passed`
- `cd apps\chat_ui; npm run test`
  Result: `25 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 mission queue-run summary posture slice:

- `cd apps\chat_ui; npm run test`
  Result: `25 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 mission queue-run error actionability slice:

- `cd apps\chat_ui; npm run test`
  Result: `25 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 mission queue-run receipt target reachability slice:

- `cd apps\chat_ui; npm run test`
  Result: `24 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 mission queue-run trace posture slice:

- `cd apps\chat_ui; npm run test`
  Result: `24 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 mission queue-run receipt continuity slice:

- `cd apps\chat_ui; npm run test`
  Result: `24 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 approval-status label parity slice:

- `cd apps\chat_ui; npm run test`
  Result: `24 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 approved-gate mission re-entry slice:

- `.venv\Scripts\python.exe -m pytest tests\test_mission_store.py tests\test_api_continuity.py::test_continuity_briefing_refreshes_approved_gate_into_rerun_handoff tests\test_api_missions.py::test_mission_advance_surfaces_approval_handoff_for_governed_execution -q`
  Result: `7 passed`
- `.venv\Scripts\python.exe -m ruff check src\francis\missions\store.py src\francis\world_state\snapshot.py tests\test_mission_store.py tests\test_api_continuity.py`
  Result: `passed`
- `cd apps\chat_ui; npm run test -- src/missions/index.test.ts`
  Result: `24 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 positive ready-state continuity contract slice:

- `python -m pytest tests/test_api_continuity.py::test_continuity_briefing_reports_ready_stage3_mission_posture tests/test_api_continuity.py::test_continuity_briefing_marks_clean_deadletter_readiness -q`
  Result: `2 passed`
- `python -m ruff check tests/test_api_continuity.py`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 readiness closure blocker disclosure slice:

- `python -m pytest tests/test_api_continuity.py::test_continuity_briefing_reports_idle_operator_start_state tests/test_api_continuity.py::test_continuity_briefing_surfaces_handoff_and_recent_completion tests/test_api_continuity.py::test_continuity_briefing_surfaces_failed_mission_recovery -q`
  Result: `3 passed`
- `python -m ruff check src/francis/world_state/snapshot.py tests/test_api_continuity.py`
  Result: `passed`
- `cd apps/chat_ui; npm test -- settings`
  Result: `24 passed`
- `cd apps/chat_ui; npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 recovery-review readiness evidence context slice:

- `python -m pytest tests/test_api_continuity.py::test_continuity_briefing_surfaces_failed_mission_recovery tests/test_api_continuity.py::test_continuity_briefing_focus_preserves_replacement_lineage -q`
  Result: `2 passed`
- `python -m ruff check src/francis/world_state/snapshot.py tests/test_api_continuity.py`
  Result: `passed`
- `cd apps/chat_ui; npm test -- settings`
  Result: `24 passed`
- `cd apps/chat_ui; npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 shared readiness evidence renderer slice:

- `git diff --check`
  Result: `passed`
- `cd apps/chat_ui; npm test -- settings`
  Result: `24 passed`
- `cd apps/chat_ui; npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 overview readiness evidence parity slice:

- `cd apps/chat_ui; npm test -- settings`
  Result: `24 passed`
- `cd apps/chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 mission readiness evidence rendering slice:

- `cd apps/chat_ui; npm test -- settings`
  Result: `24 passed`
- `cd apps/chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 recovery-reviewed failure readiness slice:

- `python -m pytest tests/test_api_continuity.py::test_continuity_briefing_surfaces_failed_mission_recovery tests/test_api_continuity.py::test_continuity_briefing_focus_preserves_replacement_lineage -q`
  Result: `2 passed`
- `python -m ruff check src/francis/world_state/snapshot.py tests/test_api_continuity.py`
  Result: `passed`
- `python -m pytest tests/test_api_continuity.py -q`
  Result: `10 passed`

Latest targeted validation for the `2026-04-25` Stage 3 replacement follow-through priority-ordering slice:

- `cd apps/chat_ui; npm test -- settings`
  Result: `23 passed`
- `cd apps/chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 replacement follow-through card parity slice:

- `cd apps/chat_ui; npm test -- settings`
  Result: `22 passed`
- `cd apps/chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 replacement lineage visibility slice:

- `pytest tests/test_api_missions.py::test_mission_replace_declares_bounded_replacement_from_failed_source tests/test_api_system_settings.py::test_system_world_state_projects_mission_queue_and_deadletter_preview tests/test_api_continuity.py::test_continuity_briefing_focus_preserves_replacement_lineage -q`
  Result: `3 passed`
- `cd apps/chat_ui; npm test -- missions settings`
  Result: `22 passed`
- `.\.venv\Scripts\python.exe -m ruff check src/francis/missions/store.py src/francis/missions/__init__.py src/francis/api/routes/missions.py src/francis/world_state/snapshot.py tests/test_api_missions.py tests/test_api_system_settings.py tests/test_api_continuity.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff format --check src/francis/missions/store.py src/francis/missions/__init__.py src/francis/api/routes/missions.py src/francis/world_state/snapshot.py tests/test_api_missions.py tests/test_api_system_settings.py tests/test_api_continuity.py`
  Result: `7 files already formatted`
- `cd apps/chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 replacement mission declaration slice:

- `pytest tests/test_api_missions.py::test_mission_deadletter_endpoint_moves_blocked_mission_cleanly tests/test_api_missions.py::test_mission_replace_declares_bounded_replacement_from_failed_source tests/test_api_missions.py::test_mission_mutation_routes_are_blocked_in_observe_mode -q`
  Result: `3 passed`
- `cd apps/chat_ui; npm test -- missions`
  Result: `22 passed`
- `cd apps/chat_ui; npm run build`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff check src/francis/missions/store.py src/francis/api/routes/missions.py tests/test_api_missions.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff format --check src/francis/missions/store.py src/francis/api/routes/missions.py tests/test_api_missions.py`
  Result: `3 files already formatted`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-25` Stage 3 failed mission recovery visibility slice:

- `pytest tests/test_api_system_settings.py::test_system_world_state_projects_mission_queue_and_deadletter_preview tests/test_api_continuity.py::test_continuity_briefing_surfaces_failed_mission_recovery tests/test_api_missions.py::test_mission_run_once_advances_safe_queue_actions -q`
  Result: `3 passed`
- `cd apps/chat_ui && npm test`
  Result: `21 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

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

Latest targeted validation for the `2026-04-25` Stage 3 mission recovery-review receipt slice:

- `pytest tests/test_api_continuity.py::test_continuity_briefing_surfaces_failed_mission_recovery tests/test_api_missions.py::test_mission_deadletter_endpoint_moves_blocked_mission_cleanly -q`
  Result: `2 passed`
- `pytest tests/test_api_continuity.py::test_continuity_briefing_surfaces_failed_mission_recovery -q`
  Result: `1 passed`
- `cd apps/chat_ui && npm test`
  Result: `21 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-24` public GitHub discoverability slice:

- `gh repo view Ap3pp3rs94/Francis --json nameWithOwner,description,homepageUrl,repositoryTopics,hasIssuesEnabled,hasDiscussionsEnabled,url,visibility`
  Result: description set, issues enabled, discussions enabled, visibility
  `PUBLIC`, and topics include `local-first`, `governance`, `auditability`,
  `digital-twin`, `observability`, `memory`, `fastapi`, `react`, and `python`.
- `gh label list --limit 100`
  Result: `roadmap` label exists with description `Roadmap-aligned implementation slice`.
- `.\scripts\check.ps1`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-24` Stage 3 approval replacement mismatch key-scope slice:

- `python -m pytest tests/test_api_approvals.py::test_approval_list_surfaces_refresh_lineage_and_payload_summary -q`
  Result: `1 passed`
- `python -m ruff check src/francis/governance/approval_projection.py tests/test_api_approvals.py`
  Result: `All checks passed!`
- `cd apps/chat_ui && npm test -- index.test.ts settings/index.test.ts`
  Result: `18 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-24` Stage 3 deadletter replacement artifact-kind continuity slice:

- `python -m pytest tests/test_api_system_settings.py::test_system_world_state_deadletter_preview_preserves_pending_approval_linkage tests/test_api_continuity.py::test_continuity_briefing_deadletter_preview_preserves_pending_approval_linkage -q`
  Result: `2 passed`
- `python -m ruff check src/francis/world_state/snapshot.py tests/test_api_system_settings.py tests/test_api_continuity.py`
  Result: `All checks passed!`
- `cd apps/chat_ui && npm test -- settings/index.test.ts`
  Result: `18 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-24` Stage 3 deadletter replacement approval-routing context slice:

- `cd apps/chat_ui && npm test -- settings/index.test.ts`
  Result: `18 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-24` Stage 3 deadletter refreshed approval replacement-evidence slice:

- `python -m pytest tests/test_api_approvals.py tests/test_api_continuity.py tests/test_api_system_settings.py`
  Result: `33 passed in 37.04s`
- `cd apps/chat_ui && npm test -- index.test.ts settings/index.test.ts`
  Result: `18 passed`
- `python -m ruff check src/francis/governance/approval_projection.py src/francis/world_state/snapshot.py tests/test_api_approvals.py tests/test_api_continuity.py tests/test_api_system_settings.py`
  Result: `All checks passed!`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-24` Stage 3 deadletter refreshed approval-status continuity slice:

- `python -m pytest tests/test_api_continuity.py tests/test_api_system_settings.py`
  Result: `29 passed in 12.84s`
- `cd apps/chat_ui && npm test -- settings/index.test.ts`
  Result: `18 passed`
- `python -m ruff check src/francis/world_state/snapshot.py tests/test_api_continuity.py tests/test_api_system_settings.py`
  Result: `All checks passed!`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-23` Stage 3 deadletter approval-lineage review routing slice:

- `cd apps/chat_ui && npm test -- settings/index.test.ts`
  Result: `18 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-23` Stage 3 deadletter approval-link recovery routing slice:

- `python -m pytest tests/test_api_continuity.py tests/test_api_system_settings.py -q`
  Result: `29 passed`
- `cd apps/chat_ui && npm test -- settings/index.test.ts`
  Result: `18 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-23` Stage 3 deadletter receipt narrative clarity slice:

- `cd apps/chat_ui && npm test -- settings/index.test.ts`
  Result: `18 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-23` Stage 3 deadletter history-tail visibility slice:

- `python -m pytest tests/test_api_continuity.py tests/test_api_system_settings.py -q`
  Result: `27 passed`
- `cd apps/chat_ui && npm test -- settings/index.test.ts`
  Result: `18 passed`
- `python -m ruff check src/francis/world_state/snapshot.py tests/test_api_continuity.py tests/test_api_system_settings.py`
  Result: `passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-23` Stage 3 deadletter receipt linkage slice:

- `python -m pytest tests/test_api_continuity.py tests/test_api_system_settings.py -q`
  Result: `27 passed`
- `cd apps/chat_ui && npm test -- settings/index.test.ts`
  Result: `18 passed`
- `python -m ruff check src/francis/world_state/snapshot.py tests/test_api_continuity.py tests/test_api_system_settings.py`
  Result: `passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-23` Stage 3 continuity deadletter evidence parity slice:

- `python -m pytest tests/test_api_continuity.py -q`
  Result: `7 passed`
- `cd apps/chat_ui && npm test -- settings/index.test.ts`
  Result: `18 passed`
- `python -m ruff check src/francis/world_state/snapshot.py tests/test_api_continuity.py`
  Result: `passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-23` Stage 3 deadletter preview truthfulness slice:

- `cd apps/chat_ui && npm test -- settings/index.test.ts`
  Result: `18 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-23` Stage 3 mission queue-run recovery result parity slice:

- `python -m pytest tests/test_api_missions.py -q`
  Result: `16 passed`
- `cd apps/chat_ui && npm test -- missions/index.test.ts`
  Result: `16 passed`
- `python -m ruff check src/francis/api/routes/missions.py tests/test_api_missions.py`
  Result: `passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-23` Stage 3 mission queue prioritization parity slice:

- `cd apps/chat_ui && npm test -- missions/index.test.ts`
  Result: `17 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-22` Stage 3 selected mission recovery action routing slice:

- `python -m pytest tests/test_api_missions.py -q`
  Result: `16 passed`
- `cd apps/chat_ui && npm test -- missions/index.test.ts`
  Result: `16 passed`
- `python -m ruff check tests/test_api_missions.py`
  Result: `passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-22` Stage 3 mission inspector advance contract parity slice:

- `python -m pytest tests/test_api_missions.py -q`
  Result: `16 passed`
- `cd apps/chat_ui && npm test -- missions/index.test.ts`
  Result: `16 passed`
- `python -m ruff check src/francis/api/routes/missions.py tests/test_api_missions.py`
  Result: `passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-22` Stage 3 explicit briefing advance contract slice:

- `python -m pytest tests/test_mission_store.py tests/test_api_continuity.py tests/test_api_system_settings.py -q`
  Result: `31 passed`
- `cd apps/chat_ui && npm test -- settings/index.test.ts`
  Result: `16 passed`
- `python -m ruff check src/francis/missions/store.py src/francis/missions/runtime.py src/francis/world_state/snapshot.py tests/test_mission_store.py tests/test_api_continuity.py tests/test_api_system_settings.py`
  Result: `passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-22` Stage 3 mission queue advance contract parity slice:

- `python -m pytest tests/test_api_missions.py -q`
  Result: `16 passed`
- `cd apps/chat_ui && npm test -- missions/index.test.ts`
  Result: `16 passed`
- `python -m ruff check tests/test_api_missions.py`
  Result: `passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-22` Stage 3 bounded Shift Briefing actionability slice:

- `.\scripts\check.ps1`
  Result: `passed`
- `cd apps/chat_ui && npm test -- --test-name-pattern="MissionsClient|SettingsClient"`
  Result: `16 passed`
- `cd apps/chat_ui && npm test`
  Result: `16 passed`
- `cd apps/chat_ui && npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

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
