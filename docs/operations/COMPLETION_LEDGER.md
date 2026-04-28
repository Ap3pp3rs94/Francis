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
- completion percentages are evidence claims, not progress decoration. They must
  be tied to a known baseline, validated repo evidence, and explicit remaining
  blockers; prompt-only, admin-only, diagnosis-only, or documentation-only turns
  must not move overall Francis or current build-phase percentages unless they
  close a documented governance/readiness gate with validation evidence.

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

As of `2026-04-27`, the Stage 3/Missions completion audit now supports a
truthful closure claim for the current local data set. The implemented contracts
cover mission creation, advancement, governed approvals, denied paths, approved
execution, trace/run and artifact handles, mission memory receipts,
explanation/evidence readback, operator readback, and failed/deadletter recovery
paths in targeted tests. The live continuity briefing for `D:\Francis\data` was
first confirmed at `review`, with `1/5` criteria satisfied, then the bounded
Stage 3 readiness proof was run through public API routes after a scoped
operator-posture transition from Observe to Assist. The proof created completed
mission `msn_20260427_133357_b4e13d71` and deadlettered mission
`msn_20260427_133357_367eab3c`, then `/continuity/briefing` reported Stage 3
readiness as `ready`, with `5/5` criteria satisfied and no blocked, attention,
or review criteria. Observe mode was restored after the proof and a follow-up
briefing still reported Stage 3 readiness as `ready`. Stage 4 Forge has not
started in this ledger entry.

As of `2026-04-27`, Stage 3 readiness proof has a bounded operator diagnostic
command instead of relying on a hand-reconstructed test recipe. `python -m
francis stage3-readiness-proof --confirm --actor <scoped_actor>` creates one
completed proof mission and one explicitly deadlettered proof mission through
the public mission API routes, then reports the continuity briefing readiness
payload. The command refuses to run without `--confirm` and still requires the
actor to have `missions.write` in `FRANCIS_API_ACTOR_SCOPES`; it does not create
new mission authority, execution authority, approval bypasses, memory writes, or
Stage 4 behavior. This made the remaining Stage 3 blocker reproducible before
the live readiness proof closed it.

As of `2026-04-27`, Stage 4/Forge has begun with a narrow no-auto-promotion
boundary on generated capability builds. `POST /plugins/build` still requires
the existing `plugins.write` API permission gate and still writes generated
artifacts, contract specs, registry snapshots, and catalog projections, but a
freshly built generated plugin is now recorded as `status: staged` with
`enabled: false`, `promotion_status: staged`, and an explicit next step to
review, validate, and enable before use. Direct execution of that staged plugin
returns `plugin_staged` and does not run the capability. Existing generated-dir
sync behavior and explicit `/plugins/enable` lifecycle behavior remain
unchanged. This is a Forge staging/isolation contract only; it is not a full
proposal system, validation flow, promotion receipt flow, or capability economy
closure claim.

As of `2026-04-27`, Stage 4/Forge generated-plugin promotion has a first
receipt boundary. When a plugin moves directly from `status: staged` to
`enabled` through explicit `POST /plugins/enable` with `plugins.write` scope,
Francis now writes an inspectable `plugin.promotion.receipt` under
`data/artifacts/plugins/promotions/`, returns the receipt in the enable response,
and preserves promotion lineage in plugin registry metadata. The receipt records
the previous staged state, promoted state, actor, redacted reason/context,
proposal id/evidence when supplied, quality fields, validation/catalog pointers,
and the permission gate used for activation. This does not create a full Forge
proposal system, does not add new execution authority, does not auto-promote,
and does not yet enforce promotion readiness from tests/docs/risk material.

As of `2026-04-27`, Stage 4/Forge generated-plugin builds now create a first
proposal artifact linked to the staged output. `POST /plugins/build` accepts
bounded build metadata for friction summary, proposal evidence, expected
benefit, risk tier, tests, docs, validation path, and known limits; writes a
redacted `plugin.proposal` record under `data/artifacts/plugins/proposals/`;
returns that proposal in the build response; and stores proposal id/path,
proposal evidence, and quality references in the staged plugin registry
metadata. The promotion receipt path can inherit proposal id, proposal evidence,
tests, docs, and risk tier from that staged metadata when the explicit enable
request does not repeat them. This is a proposal-artifact linkage boundary only:
there is still no independent Forge proposal approval workflow, no automated
readiness enforcement, and no claim that generated proposals are high quality
without human/operator review.

As of `2026-04-27`, Stage 4/Forge proposal and promotion artifacts have a
read-only API readback surface. `GET /forge/status`, `/forge/proposals/list`,
`/forge/proposals/get`, `/forge/promotions/list`, and `/forge/promotions/get`
inspect the existing `data/artifacts/plugins/proposals/` and
`data/artifacts/plugins/promotions/` records without creating new write
authority, promotion authority, execution authority, or UI claims. Readbacks are
bounded to the Forge artifact directories, support plugin/status/id filtering,
and re-apply governed display redaction before returning records. This makes
Forge artifacts inspectable through the backend API, but it is still not a
proposal approval workflow or promotion-readiness enforcement.

As of `2026-04-27`, Stage 4/Forge staged generated-plugin promotion now has a
first readiness enforcement gate. When explicit `POST /plugins/enable` targets a
staged Forge candidate, Francis now blocks promotion before registry mutation or
promotion-receipt creation unless the staged proposal metadata has a proposal id,
friction evidence, tests, docs, and a bounded risk tier. The denial response
keeps the plugin staged, exposes the missing readiness requirements, and points
the operator back to attaching proposal evidence, tests, docs, and risk before
promotion. Non-staged plugin enable remains governed by the existing
`plugins.write` permission gate. This is readiness enforcement only; it is still
not an independent proposal approval workflow or UI review surface.

As of `2026-04-27`, Stage 4/Forge proposal artifacts have a first explicit
review decision receipt. `POST /forge/proposals/decision` requires the existing
`plugins.write` actor scope, accepts bounded approve/reject/request-changes
decisions, updates only the proposal artifact status/review fields, and writes a
redacted `plugin.proposal.review.receipt` under
`data/artifacts/plugins/proposal_reviews/`. The Forge readback API now includes
proposal-review counts plus list/get routes for those receipts. This creates an
inspectable proposal review workflow without promoting plugins, enabling staged
capabilities, granting execution authority, or adding UI claims.

As of `2026-04-27`, Stage 4/Forge staged generated-plugin promotion readiness is
now tied to that proposal review truth. When explicit `POST /plugins/enable`
targets a staged Forge candidate, Francis reads the linked proposal artifact and
blocks promotion unless the proposal has an approved review receipt, even when
the candidate already has proposal evidence, tests, docs, and a bounded risk
tier. Successful promotion receipts now preserve the approved proposal-review
status and receipt id alongside the proposal id and evidence. This connects the
review workflow to promotion readiness without auto-promoting plugins, granting
execution authority, changing non-staged plugin enable behavior, or adding UI
claims.

As of `2026-04-27`, Stage 4/Forge promotion readiness also has a read-only
backend readback surface. `GET /forge/promotion_readiness/list` inspects staged
generated-plugin registry records and linked proposal artifacts, reports whether
each staged candidate is blocked or ready for explicit promotion, exposes the
missing readiness requirements, and returns proposal-review status/receipt
evidence without mutating plugin state. `GET /forge/status` now includes staged
promotion candidate, ready, and blocked counts. This gives operators and future
UI surfaces promotion-readiness truth before attempting `/plugins/enable`, but
does not promote plugins, grant write authority, execute capabilities, or claim
that the chat UI exposes Forge review yet.

As of `2026-04-27`, the chat UI plugin browser has a first read-only Forge
promotion-readiness readback. `PluginBrowserClient` now consumes
`GET /forge/promotion_readiness/list`, the chat UI route contract asserts that
the endpoint is mounted, and the Plugins panel renders backend-returned staged
candidate, ready, blocked, proposal-review, missing-requirement, and next-step
fields. This is operator readback only: it does not add promotion controls,
write authority, approval authority, execution authority, or client-side
readiness decisions.

As of `2026-04-27`, that plugin browser readback also includes Forge proposal
and proposal-review receipt evidence. `PluginBrowserClient` now consumes
`GET /forge/proposals/list` and `GET /forge/proposal_reviews/list`, the chat UI
route contract asserts both endpoints are mounted, and the Plugins panel renders
the selected plugin's linked proposal artifact, friction summary, evidence/test/doc
counts, risk tier, review status, and latest review receipt when the backend
returns them. This remains read-only operator evidence: it does not decide
proposals, promote staged capabilities, execute plugins, or infer readiness
client-side.

As of `2026-04-27`, the chat UI plugin browser also surfaces Forge validation
receipt evidence already returned by the backend. `PluginBrowserClient` now
preserves validation receipt id/path fields from promotion-readiness evidence and
proposal quality analysis, and the Plugins panel renders the selected staged
candidate's linked validation receipt/artifact path when present. This is
readback-only UI evidence: it does not call new write routes, make validation
receipts a new promotion gate, decide proposals, promote staged capabilities,
execute plugins, write memory, or infer readiness client-side.

As of `2026-04-27`, the chat UI plugin browser has a first governed Forge
proposal-decision workflow. `PluginBrowserClient` now posts proposal decisions
to the existing `POST /forge/proposals/decision` route with an explicit
`chat_ui.plugins` actor, preserves the returned review receipt/proposal item,
and treats permission-gate denials as mutation errors. The Plugins panel renders
bounded `Approve proposal`, `Request changes`, and `Reject proposal` controls
for the selected linked Forge proposal, with a decision reason field and readback
refresh after the backend responds. The chat UI route contract now asserts the
decision endpoint is mounted. This uses the existing backend permission gate and
review receipt path only: it does not change backend scopes, create promotion
authority, promote staged capabilities, execute plugins, write memory, or bypass
the explicit `/plugins/enable` promotion step.

As of `2026-04-27`, the chat UI plugin browser also has read-only Forge
promotion receipt readback. `PluginBrowserClient` now consumes
`GET /forge/promotions/list`, the chat UI route contract asserts that the
endpoint is mounted, and the Plugins panel renders the latest selected
plugin/proposal promotion receipt id, status, artifact path, and linked review
receipt when the backend returns them. This is receipt visibility only: it does
not add promotion controls, change backend scopes, grant execution authority,
grant approval authority, grant promotion authority, write memory, or bypass
the explicit `/plugins/enable` promotion step.

As of `2026-04-27`, the chat UI plugin browser lifecycle client preserves the
promotion receipt returned by an explicit staged-plugin enable response.
`PluginBrowserClient.enable()` now carries backend-returned
`promotion_status`, `promotion_receipt_id`, optional receipt path, and parsed
`plugin.promotion.receipt` evidence into its mutation response contract. This
keeps the operator-facing client contract aligned with the existing
`/plugins/enable` promotion receipt truth; it does not add a promotion control,
change backend scopes, grant execution authority, grant approval authority,
grant promotion authority, write memory, or bypass the existing permission gate
and Forge readiness checks.

As of `2026-04-27`, the chat UI plugin browser has a first bounded Forge
promotion action surface. The Plugins panel renders `Promote staged candidate`
only when the backend promotion-readiness record for the selected staged plugin
reports ready, calls the existing `PluginBrowserClient.enable()` /
`POST /plugins/enable` route with the `chat_ui.plugins` actor and an operator
promotion reason, and displays the returned promotion receipt id/artifact/review
evidence when the backend returns it. This is an operator control over the
existing governed promotion route only: it does not change backend scopes, does
not infer readiness client-side, does not bypass Forge readiness or permission
gates, does not grant execution authority, does not grant approval authority,
does not grant promotion authority outside `/plugins/enable`, and does not
write memory.

As of `2026-04-27`, Stage 4/Forge capability catalog readback has a first
summary and lineage index at the plugin registry layer. The catalog emitted by
`PluginRegistry.to_dict()` now includes deterministic plugin risk counts,
tool-risk counts, approval-required tool count, lifecycle status counts, and
Forge lineage references for proposal and promotion receipt metadata already
stored on plugin specs. This is passive catalog projection only: it does not
create proposal authority, promotion authority, execution authority, memory
writes, or UI claims.

As of `2026-04-27`, Stage 4/Forge generated plugin artifacts now carry staged
lifecycle truth in their embedded contract spec and registry snapshot. The
plugin factory writes `promotion_status: staged`, `status: staged`, an explicit
no-auto-promotion flag, and the review/validate/enable next step into
`plugin.spec.json`; the generated `plugin.registry.json` then reflects that
staged status through the registry catalog summary and lineage index. This keeps
artifact-level readback aligned with the route-level staged isolation contract;
it does not enable, promote, execute, or approve generated capabilities.

As of `2026-04-27`, the Capability Economy scaffold has a passive catalog
projection for capability lifecycle and provenance readback. `CapabilityListing`
can now carry version, staged/promoted status, risk tier, source, proposal id,
promotion receipt id, tests, docs, and metadata, while `CapabilityMarketplace`
can return filtered catalog entries and summary counts for those fields. This is
an in-memory catalog model only; it does not connect Forge routes, create
marketplace publication, grant execution authority, promote capabilities, or
claim operator UI exposure.

As of `2026-04-27`, that passive Capability Economy model can now be populated
from existing plugin registry catalog data. The new projection adapter derives
`CapabilityListing` entries from plugin catalog records, preserving staged or
promoted status, risk tier, source, proposal id, promotion receipt id,
tests/docs, proposal evidence, validation path, known limits, and plugin
metadata into the in-memory catalog summary. This remains read-only adaptation:
it does not add a route, mutate registries, publish a marketplace, execute
capabilities, promote staged plugins, or create UI claims.

As of `2026-04-27`, Stage 4/Forge capability catalog work also has a first
passive coherence analysis helper. The analyzer accepts catalog entries and
reports duplicate capability names, duplicate proposal lineage, staged entries
missing proposal ids, promoted entries missing promotion receipt ids, and
entries missing tests or docs. This directly supports the Forge/Capability
Economy anti-clutter requirement, but it remains analysis-only: it does not
block proposals, mutate catalog records, publish routes, promote capabilities,
execute tools, or create UI claims.

As of `2026-04-27`, Stage 4/Forge capability catalog lineage also preserves
validation receipt evidence. The passive plugin-catalog projection now carries
validation receipt id/path into capability metadata, and the passive coherence
analyzer reports Forge/generated staged or promoted catalog entries missing a
validation receipt id under `validation_lineage_gaps`. This is catalog
readback and analysis only: it does not add routes, mutate registry state,
publish marketplace entries, change promotion readiness, grant approval or
promotion authority, execute tools, write memory, or create UI claims.

As of `2026-04-27`, Stage 4/Forge capability catalog readback is now exposed
through a read-only backend API. `GET /plugins/capabilities/catalog` compiles
the runtime plugin catalog, projects it through the existing Capability Economy
catalog adapter, and returns filtered capability entries, summary counts,
coherence analysis, and registry catalog metadata. Generated plugin contract
compilation now preserves registry-held Forge metadata so proposal,
validation, and promotion lineage survive into the runtime catalog readback.
This is backend readback only: it does not add UI controls, mutate proposal
decisions, change promotion readiness, grant approval or promotion authority,
execute tools, write memory, or publish marketplace capabilities.

As of `2026-04-27`, the chat UI plugin browser has a first read-only Forge
capability catalog surface. The plugin browser client now parses
`/plugins/capabilities/catalog`, and the Plugins panel displays backend-returned
catalog totals, staged/promoted counts, tested/documented counts, coherence gap
counts, and selected-plugin capability lineage such as proposal, promotion
receipt, validation receipt, risk tier, source, and tests/docs counts. This is
operator readback only: it does not add proposal decisions, change promotion
readiness, grant approval or promotion authority, execute tools, write memory,
or infer catalog truth client-side.

As of `2026-04-27`, Stage 4/Forge proposal artifacts also have a passive
quality-readiness analyzer. The analyzer accepts existing `plugin.proposal`
records and normalizes the current friction, evidence, tests, docs, risk tier,
validation path, known limits, and review receipt fields into deterministic
requirements, missing-requirement lists, evidence, and analysis-only governance
metadata. This gives Forge a reusable proposal-quality inspection contract
without changing proposal decisions, promotion gates, registry state, execution
authority, approval authority, memory writes, routes, or UI claims.

As of `2026-04-27`, that passive proposal-quality analysis is now surfaced in
read-only Forge proposal API readbacks. `GET /forge/proposals/list` and
`GET /forge/proposals/get` attach `quality_analysis` to existing proposal
records, preserving deterministic requirements, missing-requirement lists,
evidence, and analysis-only governance flags without adding proposal decisions,
promotion authority, execution authority, approval authority, memory writes, or
UI claims.

As of `2026-04-27`, Stage 4/Forge proposal quality also has a passive summary
helper. The helper accepts existing proposal records, reuses the deterministic
proposal-quality analyzer, and summarizes ready/blocked counts, status counts,
risk-tier counts, review-status counts, missing-requirement counts, and blocked
proposal references. This is a backend helper only: it does not add a route,
mutate proposal records, change promotion readiness, create approval authority,
execute tools, write memory, or create UI claims.

As of `2026-04-27`, that passive proposal-quality summary is now included in
the read-only Forge status API. `GET /forge/status` reuses existing proposal
records and returns `proposal_quality_summary` with ready/blocked totals,
status/risk/review distributions, missing-requirement counts, blocked proposal
references, and analysis-only governance flags. This is aggregate readback
only: it does not mutate proposal records, change proposal decisions, create
approval authority, create promotion authority, execute tools, write memory, or
create UI claims.

As of `2026-04-27`, Stage 4/Forge generated-plugin build validation has a
first receipt and readback boundary. `POST /plugins/build` now writes a
redacted `plugin.validation.receipt` under
`data/artifacts/plugins/validations/`, links the validation receipt from the
staged plugin registry metadata and proposal record, and returns it in the build
response. `GET /forge/validations/list`, `GET /forge/validations/get`, and
`GET /forge/status` now expose those validation receipts read-only with
plugin/proposal/status filtering. This persists validation evidence for staged
Forge candidates without mutating proposal decisions, changing promotion
readiness, granting approval authority, granting promotion authority, executing
tools, writing memory, or creating UI claims.

As of `2026-04-27`, those Forge validation receipts now carry through the
promotion evidence chain. Promotion-readiness readbacks include the linked
validation receipt id/path when staged plugin metadata or the proposal record
contains them, and successful promotion receipts preserve those validation
receipt references in `quality.validation`. This links staged validation
evidence to readiness inspection and promotion receipts without making
validation receipts a new promotion gate, changing proposal decisions, granting
approval authority, granting promotion authority, executing tools, writing
memory, or creating UI claims.

As of `2026-04-27`, the passive Forge proposal-quality analyzer also preserves
validation receipt evidence from proposal records. `quality_analysis.evidence`
now includes the linked validation receipt id/path and a boolean presence flag,
and the read-only proposal API readback carries those fields through
`GET /forge/proposals/list` and `/forge/proposals/get`. This is readback-only
analysis evidence: it does not make validation receipts a new proposal-quality
requirement, does not change promotion readiness, does not change proposal
decisions, does not grant approval or promotion authority, does not execute
tools, does not write memory, and does not create UI claims.

As of `2026-04-27`, the passive Forge proposal-quality summary also aggregates
validation receipt evidence. `proposal_quality_summary` now reports
`validation_receipt_counts` with present/missing totals, and `/forge/status`
carries those counts from existing proposal records. This is aggregate readback
only: it does not make validation receipts a new readiness requirement, does
not change proposal decisions or promotion readiness, does not grant approval
or promotion authority, does not execute tools, does not write memory, and does
not create UI claims.

As of `2026-04-27`, Stage 4/Forge staging now enforces the missing upfront
quality gate found during the completion audit. `POST /plugins/build` still
requires the existing `plugins.write` permission gate, but it now blocks before
artifact, proposal, validation-receipt, registry, or catalog mutation unless
the request carries explicit friction summary, proposal evidence, tests, docs,
and a valid risk tier. The plugin build UI now collects and sends those same
Forge proposal metadata fields instead of issuing a metadata-free build. This
removes the blocker where incomplete generated capabilities could be staged and
only fail later at promotion-readiness time. The change restricts staging; it
does not create execution authority, approval authority, promotion authority,
memory writes, policy bypasses, or hidden auto-promotion.

As of `2026-04-27`, the Stage 4/Forge completion audit supports a truthful
closure claim for the current repo posture. The implemented and validated chain
covers recurring-friction proposal metadata, generated staged implementation
isolation, tests/docs/risk staging requirements, build validation receipts,
proposal review decision receipts, read-only promotion-readiness inspection,
explicit user promotion, promotion receipts linked back to proposal evidence,
capability catalog projection/coherence/readback, and operator UI surfaces for
staging metadata, review, promotion, and catalog readback. Nothing auto-promotes
and staged candidates remain non-operative until explicit promotion succeeds.
Stage 5/Reactor has not begun in this entry.

As of `2026-04-27`, Stage 5/Reactor has begun with a non-dispatching event
intake queue and decision journal. `/reactor/status`, `/reactor/events/list`,
and `/reactor/events/get` expose read-only Reactor queue state, while
`POST /reactor/events/enqueue` requires a new explicit `reactor.write` actor
scope before it writes any event record. Enqueued events must come from a known
trigger source, carry a summary, and are stored under `data/reactor/events/`
with redacted trigger metadata, classification, mode/risk/action class,
execution budgets, stop conditions, dispatch status, stable state, decision
journal, and an intake receipt. The current dispatch engine is explicitly
`not_implemented`; the slice creates no autonomous execution, approval,
promotion, memory-write, plugin, mission, or operation authority.

As of `2026-04-27`, Stage 5/Reactor also records bounded dispatch-attempt
receipts without executing work. `POST /reactor/events/dispatch_attempt`
requires the same explicit `reactor.write` actor scope before mutating an
existing Reactor event record. A dispatch attempt appends a decision-journal
entry, preserves a `reactor.dispatch_attempt.receipt`, records the current
budget snapshot, and moves the event to either `dispatch_deferred` when the
event is dispatch-eligible but the dispatch engine is still
`not_implemented`, or `dispatch_blocked` when classification says approval,
mode, or another blocker prevents dispatch. This is traceability only: it does
not start execution, consume operation budgets, decide approvals, retry,
deadletter, write memory, promote capabilities, or dispatch missions/plugins.

As of `2026-04-27`, blocked Reactor dispatch attempts also preserve explicit
blocker records. When classification prevents dispatch, the Reactor event now
records a `reactor.dispatch_blocker` with blocker id, route, gate, queue
status, stable state, next step, mode/risk/action class, budget snapshot, and
approval id when present. Approval-required blockers route to
`approval_queue`, Observe/mode blockers route to `operator_review`, and budget
blockers are marked as `deadletter_candidate` without creating a real
deadletter item. `/reactor/status` now summarizes `blocker_route_counts` from
persisted event state. This is blocker readback and receipt context only: it
does not create approvals, decide approvals, enqueue deadletters, retry,
dispatch, execute, write memory, or create UI claims.

As of `2026-04-27`, budget-exhausted Reactor dispatch blockers also preserve a
deadletter-candidate receipt. `max_actions: 0` is now a valid zero-budget event
bound that classifies the event as `blocked_by_budget` instead of being clamped
up to one action. When a dispatch attempt hits that terminal budget blocker,
the event records a `reactor.deadletter_candidate.receipt`, links it from the
dispatch blocker and decision journal, keeps the dispatch attempt receipt, and
surfaces `deadletter_candidate_counts` through `/reactor/status`. This is
candidate readback only: it does not enqueue a real deadletter item, start a
retry, execute work, consume operation budgets, decide approvals, write memory,
or create UI claims.

As of `2026-04-27`, deferred Reactor dispatch attempts can also preserve a
retry-candidate receipt when retry budget exists. When a dispatch-eligible event
is attempted while the dispatch engine remains `not_implemented`, the event can
record a `reactor.retry_candidate.receipt`, link it from dispatch state,
decision journal, latest receipt, and receipt history, and surface
`retry_candidate_counts` through `/reactor/status`. The receipt preserves
attempt count, max retries, remaining retry budget, backoff seconds, stop
conditions, and the next retry timestamp candidate. This is candidate readback
only: it does not schedule a retry, start retry execution, consume budgets,
decide approvals, enqueue deadletters, dispatch work, write memory, or create UI
claims.

As of `2026-04-27`, Reactor dispatch attempts that exceed their retry budget now
preserve an explicit retry-exhausted receipt. When a dispatch-eligible event is
attempted after its retry budget is spent, the event records a
`reactor.retry_exhausted.receipt`, moves the stable state to
`retry_budget_exhausted`, links the exhaustion from dispatch state, decision
journal, latest receipt, and receipt history, and surfaces
`retry_exhausted_counts` through `/reactor/status`. The exhaustion receipt points
at the `deadletter_candidate` route but remains readback only: it does not
enqueue a deadletter, schedule or start a retry, execute work, consume operation
budgets, decide approvals, write memory, or create UI claims.

As of `2026-04-27`, Reactor event readback also supports bounded review filters.
`GET /reactor/events/list` can now filter persisted events by stable state,
blocker route, review route, and receipt kind, so approval-queue blockers,
operator-review blockers, deadletter candidates, retry candidates, and
retry-exhausted records can be discovered without manually scanning every event.
These filters are readback-only and reuse persisted Reactor records; they do not
enqueue approvals or deadletters, schedule or start retries, dispatch work,
execute anything, write memory, or create UI claims.

As of `2026-04-27`, Reactor review evidence also has a compact read-only queue
projection. `GET /reactor/review_queue` summarizes active approval-queue,
operator-review, deadletter-candidate, retry-backoff, and retry-exhausted review
items from the existing persisted Reactor event receipts, with route counts,
stable-state counts, trigger context, receipt references, next steps, and
explicit no-authority governance flags. This is review projection only: it does
not enqueue approvals or deadletters, schedule or start retries, dispatch work,
execute anything, write memory, or create UI claims.

As of `2026-04-27`, the chat UI can also read that Reactor review queue from the
System/ORB panel. A typed Reactor UI client calls `GET /reactor/review_queue`,
parses route counts, stable-state counts, trigger context, classification,
review next steps, and receipt references, then renders a compact read-only
operator surface with links into existing approval, operation, and mission
inspectors. This is interface/readback only: it does not add execution authority,
approval authority, memory-write behavior, retry scheduling, deadletter enqueue,
or new Reactor backend behavior.

As of `2026-04-27`, approval-required Reactor dispatch attempts can create a real
pending approval request when the event has no approval id yet. The dispatch
attempt remains blocked, records `reactor.approval_request.receipt`, links the
new approval id back into the Reactor event trigger, blocker, dispatch state,
decision journal, receipts, status counts, and review-queue readback, and
preserves the pending approval through the existing approvals queue. This is
approval request queueing only: it does not decide approvals, resume dispatch
after approval, execute work, write memory, schedule retries, enqueue
deadletters, or grant approval authority.

As of `2026-04-27`, Reactor dispatch attempts also reconcile terminal approval
decisions through the existing approvals queue. When a previously queued
Reactor dispatch approval is approved, a later dispatch attempt records a
`reactor.approval_decision.receipt`, removes the active approval blocker, and
moves only to `dispatch_deferred` / `awaiting_dispatch_engine` because the
dispatch engine is still `not_implemented`. When that approval is rejected or
emergency-routed, a later dispatch attempt records the same decision receipt and
keeps the event blocked for operator review. `/reactor/status` now summarizes
approval decision receipt statuses. This is approval-decision readback and
dispatch gating only: it does not decide approvals, execute work, write memory,
schedule retries, enqueue deadletters, or grant approval, dispatch, or execution
authority.

As of `2026-04-28`, the rejected approval-decision path also has focused API
proof. The API test covers a critical Reactor event that queues an approval,
receives a rejected approval decision, and then remains
`dispatch_blocked` / `approval_rejected` on a later dispatch attempt with
operator-review routing, approval-denied verification, stable-return readback,
status counts, and no dispatch-execution receipt. This is test-only evidence
for the existing denied path; it adds no route, no runtime behavior, no
approval-decision authority, no execution authority, no retry/deadletter
handoff, no UI claim, and no memory-write authority.

As of `2026-04-27`, Reactor deadletter candidates can now create a real durable
deadletter queue item. Budget-exhausted dispatch blockers and retry-exhausted
dispatch attempts write one idempotent `reactor.deadletter.item` under the
Reactor deadletter queue, record a `reactor.deadletter.enqueue.receipt`, link
the deadletter id back into the event dispatch state, decision journal, receipt
history, and latest receipt, and expose read-only `/reactor/deadletters/list`
and `/reactor/deadletters/get` routes plus `/reactor/status`
`deadletter_queue_counts`. This is queue persistence and readback only: it does
not retry work, escalate work, resolve deadletters, execute dispatches, write
memory, or grant retry, escalation, dispatch, execution, or deadletter
resolution authority.

As of `2026-04-27`, Reactor deadletter queue items can also record bounded
operator review receipts. `POST /reactor/deadletters/review` requires
`reactor.write`, accepts an existing deadletter id, records
`reactor.deadletter.review.receipt`, updates the deadletter queue item to
`reviewed`, and links that review back through the Reactor event dispatch state,
decision journal, receipt history, `latest_deadletter_review_receipt`,
receipt-kind filtering, review-queue projection, deadletter status filtering,
and `/reactor/status` deadletter-review counts. This is review traceability
only: it does not retry work, resolve deadletters, run recovery, escalate work,
execute dispatches, write memory, or grant retry, escalation, execution,
dispatch, or deadletter-resolution authority.

As of `2026-04-27`, Reactor dispatch attempts also preserve an explicit stable
return receipt after every attempted dispatch path. Each dispatch attempt now
appends `reactor.stable_return.receipt`, records the route that currently holds
the event (`dispatch_engine`, `approval_queue`, `operator_review`,
`retry_backoff`, or `deadletter_queue`), links back to the source receipt that
caused that settled state, exposes `latest_stable_return`, keeps
`latest_receipt` aligned to that terminal-for-now receipt, and summarizes
`stable_return_counts` through `/reactor/status`. This is stable-state readback
only: it does not implement dispatch execution, verification, retry scheduling,
deadletter resolution/escalation, memory writes, approval decisions, or any new
execution, dispatch, retry, escalation, or approval authority.

As of `2026-04-27`, Reactor dispatch attempts also preserve an explicit
verification-state receipt before the stable-return receipt. Each dispatch
attempt now appends `reactor.verification.receipt`, records whether verification
is `not_available` or `not_run`, names the reason such as missing dispatch
engine, missing retry scheduler, pending approval, denied approval, blocked
dispatch, or queued deadletter review, and keeps `completion_claimed: false` /
`completion_claim_allowed: false` until a real verification path exists.
`latest_verification_receipt`, receipt-kind filtering, stable-return metadata,
decision-journal metadata, and `/reactor/status` verification counts now expose
that state. This is verification-state readback only: it does not implement
dispatch execution, execute verification hooks, schedule retries, resolve or
escalate deadletters, write memory, decide approvals, or grant execution,
dispatch, verification, retry, escalation, or approval authority.

As of `2026-04-27`, Reactor retry candidates also persist a durable retry
schedule queue item. When a dispatch-eligible event has retry budget remaining
and dispatch is deferred because the dispatch engine is still absent, the event
now writes one `reactor.retry_schedule.item`, records a
`reactor.retry.schedule.receipt`, links the schedule id through dispatch state,
the retry candidate, decision journal, receipt history, latest schedule
readback, stable-return source metadata, review-queue projection, receipt-kind
filtering, `/reactor/retries/list`, `/reactor/retries/get`, and
`/reactor/status` retry schedule counts. This is retry schedule persistence and
readback only: it does not start retry execution, run the dispatch engine,
consume execution budgets, decide approvals, resolve or escalate deadletters,
write memory, or grant execution, dispatch, retry-execution, escalation, or
approval authority.

As of `2026-04-27`, Reactor retry schedules can also be marked due through a
bounded handoff receipt. `POST /reactor/retries/mark_due` requires
`reactor.write`, checks the durable schedule due time, updates the schedule to
`due` only when eligible, records `reactor.retry.due.receipt`, links it through
the Reactor event dispatch state, decision journal, receipt history,
`latest_retry_due_receipt`, `latest_receipt`, review-queue projection,
receipt-kind filtering, retry schedule status filtering, and `/reactor/status`
retry-due counts. This is due-state handoff and readback only: it does not
start retry execution, dispatch work, run the dispatch engine, consume execution
budgets, decide approvals, resolve or escalate deadletters, write memory, or
grant execution, dispatch, retry-execution, escalation, or approval authority.

As of `2026-04-27`, due Reactor retry schedules can also record a bounded retry
dispatch-attempt handoff. `POST /reactor/retries/dispatch_attempt` requires
`reactor.write`, accepts an existing due retry schedule id, marks that schedule
`attempted`, records `reactor.retry.dispatch_attempt.receipt`, and links the
source schedule through the Reactor event dispatch state, decision journal,
receipt history, `latest_retry_dispatch_attempt_receipt`, receipt-kind
filtering, retry schedule status filtering, and `/reactor/status`
retry-dispatch-attempt counts. The handoff then uses the existing bounded
dispatch-attempt path, so with the dispatch engine still absent it can settle
back into retry backoff or exhaustion/deadletter review according to the
existing budgets. This is schedule-to-dispatch traceability only: it does not
run a dispatch engine, start retry execution, execute work, decide approvals,
resolve or escalate deadletters, write memory, or grant execution, dispatch,
retry-execution, escalation, or approval authority.

As of `2026-04-27`, Stage 5/Reactor has a first partial dispatch engine for
existing operation runs. `operation_run` Reactor events with an existing
operation id can now dispatch through the existing operations runtime only when
the dispatch actor also has the existing `operations.run` scope and current
operator posture allows execution. Successful dispatch records
`reactor.dispatch.execution.receipt`, updates the Reactor event to
`dispatch_completed` / `dispatch_succeeded`, links operation id, status, trace,
and run handles into the dispatch, verification, stable-return, receipt-history,
receipt-kind filtering, and `/reactor/status` execution counts, and marks
verification as passed only when the operation run succeeds. If the actor lacks
`operations.run` or posture blocks execution, Reactor records a blocked
dispatch-execution receipt and leaves the existing operation queued. Unsupported
action classes still use the prior non-executing deferred/retry/deadletter path.
This creates bounded Reactor execution only through the already-governed
operations runtime; it does not add approval-decision authority, promotion
authority, deadletter resolution/escalation, generic plugin/mission dispatch,
new memory-write authority beyond any memory receipts already produced by
operation execution, or UI controls.

As of `2026-04-28`, Reactor `operation_run` execution failures can now feed the
bounded retry and deadletter path instead of stopping at operation-run review
only. When the partial dispatch engine starts a linked operation and the
operation result is failed, the event still preserves the failed
`reactor.dispatch.execution.receipt`, but remaining retry budget now records an
`operation_run_failed` retry candidate, schedules a durable retry item, settles
the event into `awaiting_retry`, and keeps verification/stable-return readback
from claiming completion. A due retry dispatch attempt uses the existing retry
handoff path to run the same governed operation dispatch again; if the retry
budget is exhausted after another failed execution, Reactor records
`reactor.retry_exhausted.receipt`, queues a durable Reactor deadletter item, and
routes stable-return/readback to the deadletter queue. This is failure routing
through the existing `operations.run`-gated `operation_run` dispatcher only; it
does not add new action classes, generic looping, approval authority,
retry-execution authority outside explicit due retry handoffs, deadletter
resolution/escalation, memory-write authority, promotion authority, or UI
controls.

As of `2026-04-28`, the Stage 5/Reactor retry handoff also has explicit
successful due-retry proof for `operation_run`. A focused contract test proves a
failed linked operation can schedule an immediate retry, mark that retry due,
dispatch the due retry through the same `operations.run`-gated `operation_run`
path, and settle back to `dispatch_completed` / `dispatch_succeeded` when the
retry execution succeeds. The resulting event readback preserves the retry
dispatch-attempt receipt, marks the retry schedule as `attempted`, records the
successful dispatch-execution receipt with trace/run handles, marks
verification as passed, and returns stable-state readback to `operation_run`
without leaving stale retry-backoff or deadletter review items active. This is
proof/readback only; no runtime code, UI, approval authority, memory-write
authority, promotion authority, deadletter resolution/escalation, or new
dispatch action class changed in this slice.

As of `2026-04-28`, Reactor `mission_tick` execution also has focused API proof
for the existing mission-write authority boundary. The API test proves that an
actor with `reactor.write` but without `missions.write` can enqueue and attempt
a Reactor `mission_tick`, but the dispatch remains `dispatch_blocked` /
`mission_tick_permission_denied`, routes verification and stable-return readback
to operator review, preserves a blocked `reactor.dispatch.execution.receipt`,
does not start mission execution, and leaves the queued mission unchanged. This
is test-only evidence for the existing scope gate; it adds no route, no runtime
behavior, no mission execution authority, no approval authority, no memory-write
authority, no retry/deadletter behavior, and no UI claim.

As of `2026-04-28`, Reactor deadletter items can record bounded disposition
receipts after review. `POST /reactor/deadletters/resolve` requires the existing
`reactor.write` API scope, accepts an existing reviewed deadletter id, and
records a `reactor.deadletter.resolution.receipt` for either
`resolved_no_action` or `escalation_pending`. The receipt updates the durable
deadletter item, parent Reactor event, decision journal, receipt history,
receipt-kind filters, review-route filters, review-queue projection, and
`/reactor/status`
`deadletter_resolution_counts`. Resolved deadletters leave the active review
queue while escalation-pending deadletters remain visible on the
`deadletter_escalation` review route. This is deadletter disposition
traceability only: it does not retry work, run recovery, execute dispatches,
start external escalation, decide approvals, write memory, promote
capabilities, or grant execution, retry-execution, approval, memory-write,
promotion, or external-escalation authority.

As of `2026-04-28`, the chat UI Reactor review queue can also filter the
read-only queue by backend review route. The System/ORB panel now keeps a local
route filter, passes it to the existing `GET /reactor/review_queue?route=...`
read path, and includes the new `deadletter_escalation` route in the operator
filter set so escalation-pending deadletter dispositions are directly
inspectable instead of buried in the mixed queue. The Reactor UI client contract
also proves that `deadletter_escalation` readback preserves
`reactor.deadletter.resolution.receipt`, `deadletter_escalation_pending`, and
the non-executing `execution_started: false` flag. This is readback/UI-only; it
does not add write routes, execution authority, retry authority, approval
authority, memory-write behavior, external-escalation authority, or new backend
behavior.

As of `2026-04-28`, the chat UI System/ORB panel also reads the durable Reactor
deadletter queue directly through the existing `GET /reactor/deadletters/list`
backend route. The typed Reactor UI client parses deadletter ids, event ids,
status, route, stable state, review and resolution decisions, latest review or
resolution receipt summaries, source receipt handles, and the non-executing
retry/execution/escalation flags. The panel renders a compact read-only
deadletter queue and disposition-history section so resolved deadletters remain
inspectable after leaving the active review queue, while escalation-pending
deadletters remain visible through both queue history and the
`deadletter_escalation` review route. This is readback/UI-only; it does not add
write routes, backend behavior, execution authority, retry authority, approval
authority, memory-write behavior, external-escalation authority, or recovery
execution.

As of `2026-04-28`, Reactor escalation-pending deadletters can record a durable
non-executing escalation handoff receipt. `POST
/reactor/deadletters/escalation_handoff` requires the existing `reactor.write`
API scope and only applies after a deadletter has been reviewed and
dispositioned to `escalation_pending`. The handoff records
`reactor.deadletter.escalation_handoff.receipt`, updates the durable
deadletter item, parent Reactor event, decision journal, receipt history,
receipt-kind filters, review-route filters, review-queue projection, and
`/reactor/status` `deadletter_escalation_handoff_counts`. This is a bounded
operator/external-followup handoff record only: it does not retry work, execute
recovery, start external escalation, decide approvals, write memory, promote
capabilities, or grant execution, retry-execution, approval, memory-write,
promotion, or external-escalation authority.

As of `2026-04-28`, the chat UI Reactor readback surface also preserves
deadletter escalation handoff state. The typed Reactor UI client parses
`latest_escalation_handoff_receipt`, `escalation_handoff_recorded`, and
`external_escalation_started`, the review queue can filter the backend
`deadletter_escalation_handoff` route, and the System/ORB deadletter queue
shows the handoff receipt as the latest receipt when present. This is
readback/UI-only; it does not add backend routes, write controls, execution
authority, retry authority, approval authority, memory-write behavior,
external-escalation authority, or recovery execution.

As of `2026-04-28`, Reactor deadletter escalation handoffs can now record a
durable non-executing acknowledgement receipt. `POST
/reactor/deadletters/escalation_acknowledgement` requires the existing
`reactor.write` API scope and only applies after a deadletter has recorded an
`escalation_handoff_recorded` receipt. The acknowledgement records
`reactor.deadletter.escalation_acknowledgement.receipt`, updates the durable
deadletter item to `escalation_acknowledged`, links the receipt through the
parent Reactor event, decision journal, receipt history, receipt-kind filters,
review-route filters, review-queue projection, and `/reactor/status`
`deadletter_escalation_acknowledgement_counts`. This is an acknowledgement and
readback boundary only: it does not retry work, execute recovery, dispatch
work, start external escalation, decide approvals, write memory, promote
capabilities, or grant execution, retry-execution, approval, memory-write,
promotion, recovery, or external-escalation authority.

As of `2026-04-28`, the chat UI Reactor readback surface also preserves
deadletter escalation acknowledgement state. The typed Reactor UI client parses
`latest_escalation_acknowledgement_receipt`, `escalation_acknowledged`,
`external_escalation_started`, and `recovery_started`, the review queue can
filter the backend `deadletter_escalation_acknowledgement` route, and the
System/ORB deadletter queue shows the acknowledgement receipt as the latest
receipt when present. This is readback/UI-only; it does not add backend routes,
write controls, execution authority, retry authority, approval authority,
memory-write behavior, external-escalation authority, or recovery execution.

As of `2026-04-28`, acknowledged Reactor deadletters can request recovery
through a bounded event handoff without executing it. `POST
/reactor/deadletters/recovery_request` requires the existing `reactor.write`
API scope and only applies after `escalation_acknowledged`. The request records
`reactor.deadletter.recovery_request.receipt`, moves the durable deadletter to
`recovery_requested`, links the receipt through the parent Reactor event,
decision journal, receipt history, receipt-kind filters, review-route filters,
review-queue projection, and `/reactor/status`
`deadletter_recovery_request_counts`, and enqueues a separate
`deadletter_recovery` Reactor event with `action_class=operation_run` for the
same source operation id. This is a recovery request and dispatch-handoff
boundary only: it does not itself run recovery, execute dispatch, decide
approvals, write memory, promote capabilities, start external escalation, or
grant execution, retry-execution, approval, memory-write, promotion,
recovery-execution, or external-escalation authority.

As of `2026-04-28`, queued Reactor `deadletter_recovery` events have a
validated dispatch proof through the existing `operation_run` engine and
`operations.run` gate. The focused unit and API route tests prove the recovery
request remains non-executing until an explicit dispatch attempt is made, then
the queued recovery event runs the linked operation, records
`reactor.dispatch.execution.receipt`, verification, and stable-return readback,
and exposes the recovery event through receipt-kind, stable-state, status, and
operation-status readback. This proof adds no new route, no new dispatch engine,
no automatic deadletter settlement, no approval authority, no promotion
authority, and no external-escalation execution; the original deadletter remains
durably visible as `recovery_requested` until a later settlement/closure path
exists.

As of `2026-04-28`, successful queued Reactor `deadletter_recovery` dispatches
now settle the original recovery-requested deadletter with an explicit receipt.
When a `deadletter_recovery` event runs the linked operation successfully
through the existing `operation_run` engine and `operations.run` gate, the
runtime records `reactor.deadletter.recovery_dispatch.receipt`, moves the
durable deadletter item from `recovery_requested` to `recovery_dispatched`,
updates the original parent Reactor event to
`deadletter_recovery_dispatched`, removes it from the active recovery-request
review queue, and exposes the settlement through receipt-kind filters,
review-route filters, `/reactor/deadletters/list`, and `/reactor/status`
`deadletter_recovery_dispatch_counts`. This is a settlement/readback boundary
for a successful existing dispatch only: it adds no new route, no new dispatch
engine, no automatic retry loop, no approval authority, no promotion authority,
no memory-write behavior, and no external-escalation execution.

As of `2026-04-28`, acknowledged Reactor deadletters can also record an explicit
non-executing external escalation attempt receipt before recovery is requested.
`POST /reactor/deadletters/external_escalation_attempt` requires the existing
`reactor.write` API scope, requires the deadletter to have reached
`escalation_acknowledged`, records
`reactor.deadletter.external_escalation_attempt.receipt`, preserves declared
channel/target/adapter intent with `not_configured` adapter state, and exposes
the attempt through receipt-kind filters, review-route filters,
`/reactor/deadletters/list`, and `/reactor/status`
`deadletter_external_escalation_attempt_counts`. Recovery request handoff can
continue from that receipt. This is attempt/readback truth only: it sends no
external message, starts no external delivery, executes no work, writes no
memory, decides no approval, and grants no external-escalation, dispatch,
execution, retry, approval, promotion, or memory-write authority.

As of `2026-04-28`, Reactor external escalation attempts now include bounded
adapter preflight readback. The preflight distinguishes undeclared or unsupported
adapters from the built-in `local_outbox` adapter and records adapter status,
configured/known flags, delivery mode, readiness, blocker, missing-requirement,
and next-step fields on the same
`reactor.deadletter.external_escalation_attempt.receipt`, parent event dispatch
state, decision journal, and governance readback. Unsupported adapters still
record `not_configured`; `local_outbox` can be recognized as configured and
delivery-ready when channel and target are present, but this slice does not
queue an outbox item, send an external message, start external delivery, execute
work, write memory, or grant external-escalation, delivery, dispatch, execution,
approval, promotion, retry, or memory-write authority.

As of `2026-04-28`, preflight-ready Reactor external escalation attempts can
now queue a bounded local outbox delivery artifact without sending externally.
`POST /reactor/deadletters/external_escalation_delivery` requires the existing
`reactor.write` API scope, only applies after an external escalation attempt
has a configured `local_outbox` adapter with channel and target, writes a
durable `reactor.deadletter.external_escalation.local_outbox.item`, records
`reactor.deadletter.external_escalation_delivery.receipt`, moves the durable
deadletter to `external_escalation_delivery_queued`, and links the receipt
through the parent Reactor event, decision journal, receipt-kind filters,
review-route filters, review-queue projection, and `/reactor/status`
`deadletter_external_escalation_delivery_counts`. This is local queue
persistence and readback only: it does not send an external message, start
external delivery, execute work, dispatch work, decide approvals, write memory,
promote capabilities, or grant external-delivery, external-escalation,
execution, approval, promotion, retry, or memory-write authority.

As of `2026-04-28`, queued Reactor local outbox external escalation artifacts
also have direct read-only API readback. `GET
/reactor/deadletters/external_escalation_deliveries/list` reads the persisted
local outbox delivery artifact queue and can filter by status, deadletter id,
and event id; `GET /reactor/deadletters/external_escalation_deliveries/get`
returns one delivery artifact by delivery id. The readback preserves the same
no-send/no-execution flags recorded on
`reactor.deadletter.external_escalation.local_outbox.item` and carries explicit
readback governance denying external-delivery, external-escalation, execution,
dispatch, retry, and memory-write authority. This is direct artifact readback
only: it does not send external messages, start delivery, execute work, change
deadletter state, decide approvals, write memory, or grant new authority.

As of `2026-04-28`, queued Reactor local outbox external escalation artifacts
also expose a read-only delivery processor readiness projection. `GET
/reactor/deadletters/external_escalation_deliveries/processor_readiness/list`
and `GET
/reactor/deadletters/external_escalation_deliveries/processor_readiness/get`
derive whether a persisted local outbox item is ready for a later explicit
processor handoff, including processor status, blocker list, no-send flags,
and readback governance. This is processor-readiness readback only: it does not
claim, lease, send, deliver, start execution, change deadletter state, decide
approvals, write memory, or grant external-delivery, external-escalation,
execution, dispatch, approval, retry, promotion, or memory-write authority.

As of `2026-04-28`, queued Reactor local outbox external escalation artifacts
can record a bounded local processor handoff receipt without claiming external
send or delivery. `POST
/reactor/deadletters/external_escalation_delivery_processor_handoff` requires
the existing `reactor.write` API scope and only applies to a queued
`local_outbox` delivery artifact whose processor-readiness projection is ready.
The route records
`reactor.deadletter.external_escalation_delivery_processor_handoff.receipt`,
updates the local outbox artifact to `processor_handoff_recorded`, moves the
durable deadletter and parent Reactor event to
`deadletter_external_escalation_delivery_processor_handoff_recorded`, and links
the receipt through the parent decision journal, receipt-kind filters,
review-route filters, deadletter history, review-queue projection, and
`/reactor/status` processor-handoff counts. This is a local handoff/readback
boundary only: it does not send an external message, start external delivery,
complete a processor run, execute work, dispatch work, decide approvals, write
memory, promote capabilities, or grant external-delivery, external-escalation,
execution, approval, promotion, retry, or memory-write authority. The next
truthful gap remains an explicit external delivery sender before anything can
be marked sent.

As of `2026-04-28`, Reactor local outbox external escalation artifacts can also
record a bounded local processor completion after handoff without claiming
external send or delivery. `POST
/reactor/deadletters/external_escalation_delivery_processor_completion`
requires the existing `reactor.write` API scope and only applies after a
processor handoff was recorded. The route writes a durable local processor
output artifact under the Reactor outbox-processed store, records
`reactor.deadletter.external_escalation_delivery_processor_completion.receipt`,
moves the local outbox item, durable deadletter, and parent Reactor event to
processor-completed state, and links the receipt through the parent decision
journal, receipt-kind filters, review-route filters, deadletter history,
review-queue projection, and `/reactor/status` processor-completion counts.
This is local processor completion only: it does not send an external message,
start external delivery, perform a network send, decide approvals, write
memory, promote capabilities, or grant external-delivery, external-escalation,
execution, approval, promotion, retry, or memory-write authority. The next
truthful gap remains an explicit external delivery sender before any record may
claim a sent external message.

As of `2026-04-28`, Reactor local outbox external escalation artifacts can now
record an explicit blocked sender-attempt receipt after local processor
completion without claiming delivery. `POST
/reactor/deadletters/external_escalation_delivery_sender_attempt` requires the
existing `reactor.write` API scope, only applies after the local processor
completion receipt exists, records
`reactor.deadletter.external_escalation_delivery_sender_attempt.receipt`, moves
the local outbox item, durable deadletter, and parent Reactor event to
sender-blocked state, and links the receipt through the parent decision journal,
receipt-kind filters, review-route filters, deadletter history, review-queue
projection, and `/reactor/status` sender-attempt counts. The current sender
preflight intentionally reports no configured external sender, preserving
`external_delivery_started: false`, `external_message_sent: false`, and
`external_network_send: false`; this grants no external-delivery,
external-escalation, execution, approval, promotion, retry, or memory-write
authority. The next truthful gap remains a real configured external sender
contract before any record may claim a sent external message.

As of `2026-04-28`, Reactor local outbox external escalation artifacts also
have read-only sender-readiness readback. `GET
/reactor/deadletters/external_escalation_deliveries/sender_readiness/list` and
`/reactor/deadletters/external_escalation_deliveries/sender_readiness/get`
derive whether a persisted local outbox item has a configured external sender
after processor completion, including sender status, blocker list,
processor-completion evidence, no-send flags, and readback governance. This is
readback only: it does not attempt, claim, send, deliver, start execution,
change deadletter state, decide approvals, write memory, or grant
external-delivery or external-escalation authority. The current readiness
projection remains blocked until a real configured external sender contract
exists.

As of `2026-04-28`, Reactor deadletters have direct read-only history
readback. `GET /reactor/deadletters/history/get` derives a chronological
history for one persisted deadletter from the durable deadletter item,
source receipt, review receipts, resolution receipts, escalation receipts,
external-escalation receipts, delivery receipts, and recovery receipts already
stored on the deadletter record. The route supports receipt-kind and route
filters and carries explicit readback governance denying execution, dispatch,
retry, deadletter-resolution, external-delivery, external-escalation,
approval, promotion, and memory-write authority. This is direct history
readback only: it does not mutate deadletters, start recovery, send or deliver
external messages, execute work, decide approvals, write memory, or grant new
authority.

As of `2026-04-28`, Reactor recovery receipts also have direct read-only
list/get readback. `GET /reactor/deadletters/recovery_receipts/list` and
`/reactor/deadletters/recovery_receipts/get` derive recovery-request and
recovery-dispatch receipts from persisted deadletter records, support status,
deadletter id, event id, recovery event id, and route filters, preserve source
governance evidence, and wrap each result in explicit readback governance
denying execution, dispatch, retry, deadletter disposition/resolution,
external-delivery, external-escalation, approval, promotion, and memory-write
authority. This is receipt readback only: it does not request or dispatch
recovery, execute retry work, settle deadletters, send external messages,
decide approvals, write memory, or grant new authority.

As of `2026-04-28`, the chat UI Reactor readback surface preserves that recovery
request and recovery-dispatch settlement truth from the existing backend routes.
The typed Reactor UI client parses `latest_recovery_request_receipt`,
`latest_recovery_dispatch_receipt`, `recovery_requested`, and
`recovery_dispatched`; the review queue can filter
`deadletter_recovery_request` and `deadletter_recovery_dispatch`; and the
System/ORB deadletter queue prioritizes the recovery receipt as the latest
receipt when present. This is readback/UI-only; it does not add backend routes,
write controls, execution authority, retry authority, approval authority,
memory-write behavior, external-escalation authority, or recovery execution.

As of `2026-04-28`, Reactor `forge_proposal` events can dispatch a bounded
read-only proposal-quality review through the Stage 5 dispatch engine. The
default `proposal_review` action reads the linked Forge proposal artifact from
the event metadata, reuses the existing passive proposal-quality analyzer, and
records a `reactor.dispatch.execution.receipt` plus verification and
stable-return readback with proposal id, plugin id, readiness, missing
requirements, review status, and validation receipt references. Missing or
unlinked proposal artifacts block back to operator review instead of claiming
completion. This broadens dispatch coverage beyond `operation_run` and
`mission_tick`, but remains readback-only: it does not decide proposals, approve
reviews, promote capabilities, execute plugins, write memory, create UI claims,
or grant execution, approval, promotion, retry, or external-escalation
authority.

As of `2026-04-28`, the chat UI Reactor readback surface also exposes those
bounded Forge proposal-review dispatch receipts. `ReactorClient` now consumes
`GET /reactor/events/list` filtered to `trigger_source=forge_proposal`,
`stable_state=proposal_review_inspected`, and
`receipt_kind=reactor.dispatch.execution.receipt`; preserves proposal id,
plugin id, quality readiness, missing requirements, validation receipt,
verification, stable-return, and no-decision/no-promotion/no-memory flags; and
the System/ORB panel renders a read-only Reactor Forge Reviews section. This is
event-history readback only: it does not add backend routes, proposal decisions,
review approvals, promotions, plugin execution, memory writes, controls, or new
execution, approval, promotion, or external-escalation authority.

As of `2026-04-28`, Reactor proposal-review dispatch history also has a direct
read-only backend readback surface. `GET /reactor/proposal_reviews/history/list`
projects completed `forge_proposal` Reactor events with
`proposal_review_inspected` stable state into compact history items carrying
proposal id, plugin id, quality readiness, missing requirements, review
receipt, validation receipt, verification, stable-return, source governance,
and explicit no-authority readback governance. The route supports proposal id,
plugin id, quality-ready, and review-status filters. This is event-history
readback only: it does not dispatch events, decide proposals, approve reviews,
promote staged capabilities, execute plugins, write memory, or grant execution,
approval, proposal-decision, promotion, dispatch, or external-escalation
authority.

As of `2026-04-28`, Reactor operator visibility also has a compact no-authority
backend summary readback. `GET /reactor/operator_visibility/summary` aggregates
existing Reactor status, review queue, retry schedule, deadletter, recovery
receipt, proposal-review history, external-delivery artifact, and
delivery-processor readiness readbacks into one bounded operator snapshot with
attention counts, stable surface links, latest review/proposal-review items, and
explicit governance denying execution, dispatch, approval, deadletter, retry,
external-delivery, external-escalation, proposal-decision, promotion, and
memory-write authority. This is backend readback only: it does not add UI
claims, dispatch events, decide approvals or proposals, resolve deadletters,
start retries, send external messages, promote capabilities, execute plugins, or
write memory.

As of `2026-04-28`, the chat UI System/ORB panel also consumes that Reactor
operator-visibility summary through the typed Reactor client. The client parses
`GET /reactor/operator_visibility/summary` as a read-only contract, preserving
attention counts, route/stable-state counts, readback surface links, latest
review items, latest proposal-review items, and no-authority governance; the
System/ORB panel renders those fields in a compact Reactor Operator Visibility
card beside the existing Reactor review, Forge review, and deadletter surfaces.
This is readback/UI-only: it does not add controls, dispatch events, decide
approvals or proposals, resolve deadletters, start retries, send external
messages, promote capabilities, execute plugins, write memory, or create new
backend authority.

As of `2026-04-28`, Stage 5/Reactor also has a bounded read-only classification
dispatch path for observation-style triggers. The dispatch engine now supports
`action_class=classify` for `telemetry_event` and `observer_anomaly` Reactor
events only, producing a `reactor.dispatch.execution.receipt`,
verification receipt, and stable-return receipt with `route=classification` and
`stable_state=classification_recorded`. This broadens dispatch coverage beyond
operation runs, mission queue ticks, and Forge proposal review while preserving
the old deferred/not-implemented behavior for non-observation `classify` events.
The path does not start execution, decide approvals, resolve deadletters,
perform retries, send external messages, promote capabilities, execute plugins,
or write memory.

As of `2026-04-28`, Stage 5/Reactor also records bounded approval-decision
resume receipts without executing the target event. The dispatch engine now
supports `action_class=resume` for `approval_decision` Reactor events only. A
dispatch attempt reads the existing approval record status from the approvals
queue, requires a terminal approval state, and records a
`reactor.dispatch.execution.receipt`, verification receipt, and stable-return
receipt with `route=approval_resume`, approval id/status, target Reactor event
id, and operation id readback. Missing or non-terminal approvals block back to
operator review instead of claiming progress. This is approval-decision resume
readback only: it does not dispatch the target event, decide approvals, start
execution, write memory, promote capabilities, send external messages, or grant
approval-decision, execution, memory-write, promotion, or external-delivery
authority.

As of `2026-04-28`, Reactor approval-decision resume receipts also have direct
read-only history readback. `GET /reactor/approval_resumes/history/list`
projects completed `approval_decision` Reactor events with
`approval_resume_recorded` stable state into compact history items carrying
approval id/status, whether the approval allows dispatch, target Reactor event
id, operation id, receipt id, verification state, stable-return state, source
governance, and explicit no-authority readback governance. The route supports
approval id, approval status, target event id, operation id, and
approval-allows-dispatch filters. This is approval-resume history readback only:
it does not dispatch target events, decide approvals, execute work, retry,
write memory, promote capabilities, send external messages, or grant execution,
dispatch, approval-decision, retry, promotion, external-delivery,
external-escalation, or memory-write authority.

As of `2026-04-28`, the Reactor operator-visibility summary also includes
direct sender-readiness visibility for local outbox external escalation
artifacts. `GET /reactor/operator_visibility/summary` now aggregates the
existing sender-readiness projection into attention counts, status counts, a
stable readback surface link, and limited ready/blocked sender-readiness item
lists. This makes the current `external_sender_adapter` blocker visible from
the compact backend operator summary without adding UI controls or changing the
sender route. It does not attempt, send, deliver, execute, decide approvals,
write memory, promote capabilities, or grant external-delivery,
external-escalation, execution, approval, promotion, retry, dispatch, or
memory-write authority.

As of `2026-04-28`, the chat UI Reactor operator-visibility card also consumes
that sender-readiness summary. The typed Reactor client parses
`external_delivery_sender_readiness_total`, sender readiness attention/count
maps, readback links, and ready/blocked sender-readiness items; the System/ORB
panel renders the sender blocker, processor-complete evidence, and no-send
state inside the existing read-only Reactor Operator Visibility surface. This
is readback/UI-only: it does not add backend routes, write controls, delivery
attempts, external sends, execution, approval decisions, memory writes,
promotion, retry execution, or external-delivery authority.

As of `2026-04-28`, Stage 5/Reactor also has an explicit plugin-run dispatch
boundary. `action_class=plugin_run` Reactor events now produce a blocked
`reactor.dispatch.execution.receipt` with `route=plugin_run`, stable
`plugin_run_dispatch_not_enabled` state, verification and stable-return
receipts, operator-review projection, and `/reactor/status`
`dispatch_engine_boundary_actions` readback. This replaces a generic
not-implemented deferment for plugin-run attempts with a typed, reviewable
boundary while keeping plugin execution disabled. It does not execute plugins,
load plugin code, dispatch plugin work, decide approvals, write memory, promote
capabilities, send external messages, start retries, or grant plugin-run,
execution, dispatch, approval, promotion, external-delivery, or memory-write
authority.

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

As of `2026-04-26`, direct operation lifecycle mutation routes also respect the
operator posture write boundary. `PATCH /operations/{operation_id}`,
`POST /operations/{operation_id}/cancel`, and `DELETE /operations/{operation_id}`
now deny in Observe mode before changing operation metadata, tags, notes, or
cancellation state, while returning the current operation projection and blocked
posture. Operation create, direct run, and worker-cycle routes already had
posture guards. This is a posture guard integration only; it does not add an
API-scope permission gate to operation lifecycle routes.

As of `2026-04-26`, those operation lifecycle posture-denial responses no longer
fabricate operation projections for missing operation records. When the blocked
target exists, the response still carries the current operation projection and
status. When it does not exist, the response carries the requested `operation_id`
plus blocked posture without inventing an `operation` object. This tightens
operator-surface truthfulness only; it does not alter Observe-mode enforcement,
allowed lifecycle mutations, execution, approval, or memory behavior.

As of `2026-04-27`, direct operation execution routes are also wired to the API
permission gate. `POST /operations/{operation_id}/run` and
`POST /operations/run-once` now deny before running queued work or a worker cycle
unless the request actor is present in the server-side
`FRANCIS_API_ACTOR_SCOPES` policy with the `operations.run` scope. Existing
posture guards, exact-action approvals, traces, artifacts, and operation memory
receipts remain unchanged when the permission gate allows execution.

As of `2026-04-27`, direct operation declaration and lifecycle mutation routes
are also wired to the API permission gate. `POST /operations/create`,
`PATCH /operations/{operation_id}`, `POST /operations/{operation_id}/cancel`,
and `DELETE /operations/{operation_id}` now deny before creating queued work or
changing operation metadata, cancellation, or deletion state unless the request
actor has `operations.write` in `FRANCIS_API_ACTOR_SCOPES`. Existing Observe
mode posture blocks and read projections remain unchanged when the permission
gate allows the request.

As of `2026-04-27`, the chat UI operations client preserves those direct
operation permission-gate denials across create, patch, cancel, run,
worker-cycle, and delete response contracts. `OperationsClient` now keeps the
backend `status`, `error`, and bounded `governance` denial body instead of
collapsing mutation and execution denials to a bare failed operation response.
This is interface truth only; it does not widen execution, approval, memory
write, or mutation authority.

As of `2026-04-27`, the chat UI Operations panel consumes that preserved
operation denial governance in operator action notices. Direct operation create,
immediate run, selected run, selected cancel, and worker-cycle failure notices
now prefer the backend gate, reason, next-step, and operator hint fields before
falling back to generic error/status text. This is a read-only display change;
it does not alter route policy, execution, approval, memory write, or mutation
behavior.

As of `2026-04-26`, domain registry write routes are also wired to the API
permission gate. `POST /domains/create`, `PATCH /domains/update`, and
`POST /domains/delete` now deny before mutating local domain registry state unless
the request actor is present in the server-side `FRANCIS_API_ACTOR_SCOPES`
policy with the `domains.write` scope. Domain read/list/summary routes remain
read-only. This is another narrow route integration, not a claim of API-wide
permission enforcement.

As of `2026-04-26`, approval decisions are also wired to the API permission gate.
`POST /approvals/decision` still requires a local caller unless remote approval
decisions are explicitly enabled, and then denies before moving an approval out of
the pending queue unless the decision actor is present in the server-side
`FRANCIS_API_ACTOR_SCOPES` policy with the `approvals.decide` scope. Allowed
decisions persist a redacted `decision_actor` in the approved/rejected/emergency
approval record. The chat UI approvals client now sends its bounded
`chat_ui.approvals` actor and treats backend denial responses as decision errors
instead of presenting them as successful moves. This does not widen approval
request/list behavior, exact-action matching, execution, or remote decision
access.

As of `2026-04-26`, trust mutation routes are also wired to the API permission
gate. `POST /trust/adjust`, `POST /trust/mutate`, `POST /trust/set`, and
`POST /trust/policy`, including their system-prefixed aliases, deny before
changing trust state or policy unless the request actor is present in the
server-side `FRANCIS_API_ACTOR_SCOPES` policy with the `trust.write` scope.
Trust state, history, events, and policy reads remain read-only. The chat UI
trust client now sends its bounded `chat_ui.trust` actor for trust adjustments
and treats backend denial responses as mutation errors instead of presenting
them as successful changes. This is another narrow route integration, not a
claim of API-wide permission enforcement.

As of `2026-04-26`, credential request and revocation routes are also wired to
the API permission gate. `POST /credentials/request` and
`POST /credentials/revoke` deny before creating approval records, approval
artifacts, registry entries, or credential registry events unless the request
actor is present in the server-side `FRANCIS_API_ACTOR_SCOPES` policy with the
`credentials.write` scope. Credential status, list, scopes, and delegation
surfaces remain read-only. The chat UI credential manager now sends its bounded
`chat_ui.credentials` actor for credential mutations and treats backend denial
responses as mutation errors instead of presenting request/revoke operations as
successful. This is another narrow route integration, not a claim of API-wide
permission enforcement.

As of `2026-04-26`, system runtime mutation routes are also wired to the API
permission gate. `POST /system/operator_mode`, `POST /system/operator-mode`,
`POST /system/services/action`, `POST /system/flags/set`,
`POST /system/feature_flags/set`, keyed feature-flag write aliases, and runtime
settings/config mutation aliases deny before changing control mode, service
action receipts, feature flags, or runtime settings unless the request actor is
present in the server-side `FRANCIS_API_ACTOR_SCOPES` policy with the
`system.write` scope. Read-only system status, health, world-state, ORB,
operator-mode, flags, and config surfaces remain read-only. The chat UI settings
client now sends its bounded `chat_ui.system` actor for system mutations and
treats permission-denial responses as mutation errors instead of presenting them
as successful changes.
This is another narrow route integration, not a claim of API-wide permission
enforcement.

As of `2026-04-26`, explicit observer scans are also wired to that same system
write permission gate. `POST /system/observer/scan` now denies before creating an
observer audit receipt unless the request actor has `system.write` in
`FRANCIS_API_ACTOR_SCOPES`. Read-only observer status, observer audit history,
world-state, continuity, and ORB observer projections remain read-only. The chat
UI settings client sends the bounded system mutation actor fallback for scan
requests and treats backend permission denials as mutation errors. This is
receipt-write governance only; it does not change passive observer snapshots,
probe scoring, mission execution, or readiness semantics.

As of `2026-04-26`, plugin catalog and lifecycle mutation routes are also wired
to the API permission gate. `POST /plugins/build`, `POST /plugins/enable`,
`POST /plugins/disable`, `POST /plugins/install`, `POST /plugins/uninstall`,
and `POST /plugins/reload` deny before changing generated plugin artifacts,
plugin registry/catalog state, or lifecycle status unless the request actor is
present in the server-side `FRANCIS_API_ACTOR_SCOPES` policy with the
`plugins.write` scope. Plugin list/get/download/tool catalog/export routes
remain read-only. `POST /plugins/run` and `POST /plugins/tools/run` are
unchanged in this slice and remain governed by their existing trust,
exact-action approval, receipt, and trace flow. The chat UI plugin browser now
sends its bounded `chat_ui.plugins` actor for plugin lifecycle writes and treats
backend permission denials as mutation errors instead of successful lifecycle
responses. This is another narrow route integration, not a claim of API-wide
permission enforcement.

As of `2026-04-26`, mission execution-capable routes are also wired to the API
permission gate. `POST /missions/run_once` and
`POST /missions/{mission_id}/advance` deny before reconciling or advancing
mission execution unless the request actor is present in the server-side
`FRANCIS_API_ACTOR_SCOPES` policy with the `missions.write` scope. Mission read
surfaces remain unchanged in this slice. This is a narrow execution-gate
integration for Stage 3 mission flow, not a claim of API-wide mission permission
enforcement.

As of `2026-04-26`, actor-bearing mission lifecycle mutation routes are also
wired to that mission write permission gate. `POST /missions/tick`,
`PATCH /missions/{mission_id}`, `POST /missions/{mission_id}/tick`,
`POST /missions/{mission_id}/deadletter`, and
`POST /missions/{mission_id}/replace` deny before reconciling, updating,
deadlettering, or declaring replacement mission state unless the request actor
has `missions.write` in `FRANCIS_API_ACTOR_SCOPES`.

As of `2026-04-26`, direct mission declaration is also wired to that mission
write permission gate. `POST /missions/create` accepts an explicit `actor`,
falls back to `requester_id` for legacy direct callers, and denies before
creating mission records, history, or queue state unless the resolved identity
has `missions.write` in `FRANCIS_API_ACTOR_SCOPES`. The chat UI mission client
now sends an explicit create actor instead of relying only on requester id.

As of `2026-04-26`, chat mission ingress is also wired to that mission write
permission gate. `/chat/send` and `/chat/ws` mission commands use the bounded
`chat.send` actor and deny before creating mission records or the first
`plan.create` operation unless that actor has `missions.write` in
`FRANCIS_API_ACTOR_SCOPES`. Denials return the same bounded `governance`
envelope with gate, reason, next step, and count-only evidence, and the chat UI
chat client preserves that envelope in mission-ingress metadata instead of
collapsing policy truth to a plain error string.

As of `2026-04-26`, those chat mission ingress permission denials also preserve
bounded gate handoff metadata in the continuity ledger. The assistant ledger
entry keeps the ingress plane, gate stage, handoff gate/action/next step,
governance reason, and count-only evidence, and `/memory/timeline/list` projects
that denial as a read-only loop event without creating mission or task records.
This is trace/readback only; it does not grant mission authority, bypass policy,
or synthesize mission state for denied ingress.

As of `2026-04-26`, chat mission ingress posture blocks now use the same
structured gate readback path. When observe mode or blocked operator posture
prevents `/chat/send` or websocket mission ingress from creating mission state,
the response and assistant continuity ledger entry carry an `operator_posture`
governance gate, reason, next step, and gate-stage handoff action. This does not
change posture enforcement, create missions, queue operations, or widen
`chat.send` authority.

As of `2026-04-26`, direct mission continuity text is redacted at the mission
store boundary. Mission `objective`, `summary`, `next_step`, and
`escalation_path` fields are normalized through the governed free-text secret
filter on create, update, and record read, so direct mission API responses,
record files, and history entries do not replay inline password, token, key, or
secret values. This does not change mission authority, queue eligibility, or
execution behavior.

As of `2026-04-26`, mission queue-run execution handoff text also has a final
runtime redaction boundary. `/missions/run_once` result and error projections
redact free-text handoff fields such as `message`, `next_step`,
`operation_error`, `result_message`, and `recovery_next_step` before returning
queue-run responses, while preserving bounded identifiers such as operation,
approval, trace, run, and artifact handles. This closes a response-truth gap; it
does not add new execution authority or retry behavior.

As of `2026-04-26`, direct mission advance responses share that runtime
redaction boundary. `POST /missions/{mission_id}/advance` now redacts free-text
handoff messages and operator guidance before returning them or writing advance
receipts, while preserving operation, approval, trace, run, and artifact handles.
This keeps direct advance and queue-run responses aligned without changing
execution authority, queue eligibility, or approval behavior.

As of `2026-04-26`, read-only mission queue responses carry the receipt-backed
mission loop projection. `GET /missions/queue` enriches visible queue, failed,
and deadletter items with the existing `loop_state`, `handoff`,
`receipt_summary`, receipt-backed `current_task` fields, and bounded
history/linked-operation/run-ledger counts. This is a read projection only; it
does not advance missions, run operations, widen approvals, or replace the full
mission detail/log inspection route.

As of `2026-04-27`, mission tick reconstruction also promotes approval handles
from nested execution receipts on linked task records. When `tick_mission`
rebuilds blocked mission state from task truth, it now treats
`result.data.receipt.approval_id` and `previous_approval_id` as bounded approval
references for mission meta, queue hints, and current-task readback. This is
mission readback normalization only; it does not approve work, execute tasks, or
create new receipts.

As of `2026-04-27`, mission queue-run handoff results also promote nested
approval receipt lineage. When the mission runtime advances a queued linked
operation and the operation returns approval handles under its receipt, the
queue-run result/error readback preserves the current approval id, previous
approval id, and approval status alongside gate and next-step context. This is
runtime readback normalization only; it does not approve work, execute tasks, or
widen queue eligibility.

As of `2026-04-26`, the chat UI missions client can consume that direct queue
read projection. `MissionsClient.queue` now reads `GET /missions/queue` with
bounded limit and terminal-inclusion params, and `MissionQueueItem` preserves
queue-level `loop_state`, `handoff`, `receipt_summary`, current-task receipt
fields, and bounded linked-operation/run-ledger counts. This is a typed client
contract only; it does not add new rendering claims or execution authority.

As of `2026-04-26`, the world-state mission overview path also carries a
bounded loop/readout projection for queue, failed, deadletter, and recent mission
items. `/system/world_state` mission records now include overview-level
`loop_state`, `handoff`, and `receipt_summary` data derived from existing
mission queue, current-task, latest-activity, history, and memory receipt facts;
the chat UI settings parser preserves those fields and the ORB mission queue
cards render the loop stage, handoff action, receipt task, trace/run/artifact
handles, and receipt counts before opening full mission detail. This is a
read-only overview projection; it does not advance missions, create receipts,
broaden approvals, or replace the full mission detail/log inspection route.

As of `2026-04-26`, those persistent ORB mission queue cards also expose direct
receipt reachability from the overview path. When the overview projection carries
a receipt operation, approval, or artifact handle, the card can open the receipt
task, review the receipt approval, and inspect the receipt artifact from the
existing artifact-inspection surface. This is a UI reachability improvement over
already-projected handles only; it does not create artifacts, synthesize memory,
or add execution authority.

As of `2026-04-26`, the explanation registry can preserve and query the same
mission loop handles used by the Stage 3 trace and memory surfaces. Explanation
records now lift `mission_id` and `operation_id` from either top-level fields or
metadata, include those handles in list/get/export summaries, and support bounded
list/export filtering by mission and operation id. This is evidence readback
truth only; it does not create mission state, write memory, or add execution
authority.

As of `2026-04-26`, explanation records also accept the structured receipt
`references` shape used by mission-loop memory receipts. `references` can carry
bounded mission, operation/task, approval, trace, run, and artifact handles; the
backend promotes those handles into the existing list/get/export query contract
and persists a normalized `references` block. This is trace/evidence readback
only; it does not synthesize explanation evidence or broaden execution authority.

As of `2026-04-26`, explanation evidence also preserves receipt-backed current
task identity. Explanation records can now promote `current_task_*` receipt
handles from top-level fields, `loop`, `references`, or metadata into bounded
mission/operation/approval/trace/run/artifact filters, and list/get/export
summaries keep the current task source, status, operation name, ORB plane, gate,
advance action, and next step when backend truth provides them. The chat UI
explanation client preserves those fields and normalized receipt references for
read-only evidence display. This is trace/evidence readback only; it does not
write memory, create explanation records, execute work, or synthesize missing
task identity.

As of `2026-04-27`, explanation evidence also preserves current-task previous
approval lineage. Explanation records can promote
`current_task_previous_approval_id` and
`current_task_previous_approval_status` from loop evidence into list/get/export
summaries and CSV exports alongside the current approval id/status. This is
trace/evidence readback only; it does not approve work, refresh approvals,
execute operations, write memory, or infer missing lineage.

As of `2026-04-26`, explanation evidence also promotes handoff-only receipt
handles into the same normalized reference contract. When a mission loop
handoff provides operation, approval, trace, run, artifact, or mission handles
without top-level/current-task ids, the explanation registry now lifts those
handles into list/get/export filters and persists the normalized `references`
block. This is readback normalization only; it does not create handoff state,
write memory, execute work, or infer missing evidence.

As of `2026-04-26`, explanation evidence also preserves bounded recovery
context from receipt-backed execution records. Explanation records can promote
`operation_error`, `result_message`, and `recovery_next_step` from top-level
fields, `loop`, `references`, or metadata into list/get/export summaries, and
those values are passed through the governed operation free-text redaction
boundary before persistence or return. The chat UI explanation client preserves
those fields as read-only evidence. This is recovery evidence readback only; it
does not create retry authority, deadletter authority, execution state, or new
operator controls.

As of `2026-04-26`, explanation evidence also preserves bounded plan receipt
summaries from mission-loop evidence. Explanation records can promote
`plan_status`, current step id/title, step count, and checkpoint count from
top-level fields, `loop`, `references`, or metadata into list/get/export
summaries and CSV exports, and the chat UI explanation client preserves those
fields as typed read-only evidence. This is plan evidence readback only; it does
not create plans, revise plans, execute work, write memory, or infer missing
plan state.

As of `2026-04-26`, the chat UI explanation evidence path can use those
mission and operation explanation filters. The selected operation/mission audit
evidence helper now sends bounded `mission_id` and `operation_id` queries before
falling back to approval, trace, run, or artifact handles, and explanation
records render returned mission/task references when present. This is read-only
interface reachability; it does not create explanation records or infer missing
evidence.

As of `2026-04-27`, the chat UI explanation evidence query builder also follows
loop-only mission receipt handles. `buildExplanationEvidenceQueries` now
recognizes `current_task_mission_id` and `handoff_mission_id` on terminal
receipts before falling back to top-level or normalized mission references, so
bounded explanation lookups can follow the same mission handoff aliases already
promoted by the backend explanation registry. This is interface query
reachability only; it does not create explanation records, change backend
filtering, execute operations, alter approvals, or infer mission state.

As of `2026-04-27`, the chat UI explanation explorer client also preserves
loop-only receipt aliases when explanation records are sparse. The read-only
parser now builds normalized receipt references from backend `references`,
`loop`, `meta`, and raw fields using the same current-task and handoff alias
families as the explanation route, so mission, operation, approval, trace, run,
and artifact handles remain visible even if the response omits a pre-normalized
`references` block. This is client readback normalization only; it does not
create explanation records, change backend filtering, execute operations, alter
approvals, or infer mission state.

As of `2026-04-26`, the repeated main-branch CI failure was traced to the
workflow Mypy gate, not pytest runtime failures. The static typing gap in
mission receipt readback and chat mission-ingress metadata compaction is now
closed with typed dict narrowing while preserving existing runtime behavior.

As of `2026-04-26`, terminal mission-operation memory receipts are reachable
from operation detail surfaces after the immediate run response is gone. The
shared receipt reader can query continuity-ledger receipts by operation id with
optional mission scoping, `/operations/{operation_id}` and
`/operations/get_many` project `memory_receipt_count` plus
`latest_memory_receipt` onto backed operation details, and the chat UI
operations client preserves that receipt summary. This does not mint new memory
or infer completion; it exposes existing continuity-ledger receipts for
mission-linked operations that already reached a terminal status.

As of `2026-04-26`, the chat UI operation detail panel uses those backed
operation memory receipts when loading memory evidence for the selected
operation. When an operation detail exposes `latest_memory_receipt`, the
interface prefers that receipt's operation id and receipt references for the
bounded memory-timeline query, and shows the operation memory receipt count plus
reference line in the selected operation detail. This is a receipt-reachability
slice only; it does not synthesize memory evidence or broaden query scope.

As of `2026-04-26`, failed terminal mission-operation receipts also preserve
bounded recovery context. When a mission-linked operation reaches failed
terminal status, the operations runtime writes redacted `operation_error`,
`result_message` when present, and `recovery_next_step=review_operation_detail`
into the continuity-ledger receipt. Operation receipt projections,
operation-detail memory summaries, mission receipt helpers, and memory timeline
loop projections preserve those fields so failure review can start from the
receipt itself instead of inferring the failure reason from mission detail state.

As of `2026-04-26`, failed terminal mission-operation receipts also preserve a
bounded deadletter handoff loop. The terminal operation receipt now carries
`active_stage=deadletter`, `handoff_stage=deadletter`,
`handoff_action=retry_or_deadletter`, terminal operation/trace/run/artifact
handles, and `current_task_source=terminal_operation_receipt` so recovery
surfaces can point at the real receipt-backed operation review path. Mission
receipt helpers, operation detail memory summaries, and memory timeline loop
projections preserve those fields from receipt truth. This is receipt truth
only; it does not add retry authority, deadletter mutation authority,
scheduling behavior, or synthetic operation state.

As of `2026-04-26`, that failed terminal operation receipt handoff also carries
the same explicit `operator_review` gate on `handoff_gate` and
`current_task_gate`. Downstream mission, world-state, and memory timeline
surfaces already read those gate fields, so failed execution review now keeps
stage, action, gate, operation, trace, run, artifact, and next-step handles
together in one terminal receipt. This is receipt metadata only; it does not
open retry or deadletter mutation paths.

As of `2026-04-26`, the continuity briefing also uses those terminal
mission-operation receipts as a fallback when projecting a mission's current
task. Failed mission previews keep the receipt-backed operation id, trace
references, failure reason, and `recovery_next_step` visible in `current_task`
when mission metadata or run-ledger activity does not already provide those
fields. This does not create retry authority; it keeps the existing recovery
handoff tied to a receipt-backed operation detail review.

As of `2026-04-26`, ORB status handback state now carries the concrete
continuity item that triggered a handback even when the normal continuity focus
list is empty. Failed, deadletter, and recently-completed previews can become
`handback_state.focus` with a `focus_source`, preserving existing mission,
current-task, trace, run, artifact, and memory-receipt handles from backend
truth. This is read-model focus selection only; it does not create retry,
deadletter, execution, memory, or UI state.

As of `2026-04-26`, operator-mode continuity readback exposes the same concrete
handoff focus before ORB consumes it. `/system/operator_mode` now returns
`continuity.handoff_focus` and `continuity.handoff_focus_source`, choosing the
first existing item from focus, failed preview, deadletter preview, or recently
completed continuity. Existing focus, preview, and receipt arrays remain
unchanged; this is read-model selection only and does not create retry,
deadletter, execution, memory, or UI state.

As of `2026-04-27`, operator-mode continuity readback also preserves the mission
briefing's existing terminal operation memory receipts. `/system/operator_mode`
now returns `continuity.memory_receipts` from the already-built mission
continuity briefing so operator surfaces can inspect receipt-backed mission,
operation, trace, run, artifact, and handoff evidence without requiring a
separate continuity lookup. This is read-model pass-through only; it does not
create memory receipts, inspect artifacts, execute operations, or change ORB
handback focus selection.

As of `2026-04-27`, ORB handback state also preserves a bounded summary of
those continuity memory receipts. `handback_state.memory_receipt_count` and
`handback_state.latest_memory_receipt` now carry the existing receipt-backed
mission, operation, trace, run, artifact, and handoff evidence through the ORB
state read model. This does not change ORB focus selection, render state,
execution authority, retry/deadletter authority, or memory-write behavior.

As of `2026-04-26`, mission advance and queue-run handoff results preserve that
receipt-backed recovery context when linked operation execution fails. The
mission runtime projects `operation_error`, `result_message` when present, and
`recovery_next_step` from the terminal operation memory receipt into the
immediate mission result and queue error records. This keeps retry/deadletter
decisions actionable from the mission handoff without creating retry authority
or inferring recovery state outside the receipt.

As of `2026-04-26`, the chat UI missions client also preserves that
receipt-backed recovery context instead of dropping it at the browser contract
boundary. Mission advance responses, mission queue-run results, queue error
records, and terminal mission memory receipts keep `operation_error`,
`result_message`, and `recovery_next_step` when the backend provides them. This
is a client contract slice only; it does not add new execution controls or claim
new visible rendering outside the existing mission result surfaces.

As of `2026-04-26`, the ORB mission action and queue-run result surfaces render
that preserved recovery context in the existing mission result cards. Mission
advance failures and queue-run result/error rows now show receipt-backed
`operation_error`, `result_message`, and `recovery_next_step` when present,
without adding retry authority, new mutation controls, or inferred recovery
state.

As of `2026-04-26`, the chat UI mission client preserves those mission
execution permission-gate denials instead of collapsing them to a bare error
string. Mission advance and queue-run responses now retain the backend
`governance` envelope with gate, reason, next step, and bounded evidence, and
the ORB mission action notices/queue error cards can surface that exact
permission posture when mission execution is denied. This is an interface truth
slice only; it does not expand mission execution authority or add new backend
mutation routes.

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

As of `2026-04-27`, delegation creation audit receipts and executor mission
transition sync also resolve mission identity from loop alias fields. When a
task input carries `current_task_mission_id` or `handoff_mission_id` instead of
top-level `mission_id`, the created audit receipt still records the bounded
mission handle and executor status transitions still update the linked mission
history. This is mission-link/readback normalization only; it does not change
capability routing, execution eligibility, approval behavior, or memory writes.

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

As of `2026-04-26`, memory timeline retrieval can also filter by receipt
`approval_id`. The API already preserves approval handles on event references
and mission-loop continuity receipts; `/memory/timeline/list` and
`/memory/timeline/export` now accept an `approval_id` filter, and the chat UI
memory timeline client can request the same bounded filter. This makes
approval-gated mission memory evidence reachable by the real approval handle
without broad timeline searches, payload inspection, or new memory writes.

As of `2026-04-26`, selected-operation memory evidence can now request that
same bounded approval-handle lookup from the interface. The selected operation
panel passes the real selected mission/operation approval id into
`buildMemoryEvidenceQueries`, and the helper can also follow approval ids from
terminal receipt references. This is bounded memory evidence lookup only; it
does not create approval decisions, execute operations, inspect payloads, write
memory, or synthesize evidence.

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

As of `2026-04-26`, the operation memory-evidence interface can also fall back
to terminal mission memory receipt references when the selected task projection
is sparse. The evidence query helper accepts a parsed receipt reference and can
derive mission, operation, trace, run, artifact, and terminal status filters
from that receipt without including payloads. The selected-operation mission
bridge passes the latest parsed mission memory receipt into that helper, so the
operator can load memory evidence from backend receipt truth instead of UI-only
state.

As of `2026-04-26`, that selected-operation mission bridge path has headless
browser proof against a mock API shaped like the backend receipt contract. The
proof opens the real Vite UI, enters Operations, loads memory evidence from a
mission loop bridge, and confirms timeline requests include receipt-derived
`trace_id`, `run_id`, and `artifact_dir` filters with no browser HTTP failures.

As of `2026-04-26`, the chat UI no longer crashes during initial Vite render
when the command palette builds its observer-scan command. `App` now owns a real
observer-scan command handler for the command palette, while `SystemPanel` owns
its local observer-scan button state. This restores the explicit operator scan
entry points without adding background scanning or hidden observer activity.

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

As of `2026-04-26`, explanation and audit records also preserve `run_id` when
that handle is supplied through record metadata instead of a top-level field.
The backend normalizes metadata-only run handles into the same public summary,
detail, filter, and export contract, and the chat UI explanation explorer
client preserves the same fallback when parsing list/get responses. This is a
read-model/client contract change only; it does not create explanations,
execute work, or infer trace state.

As of `2026-04-26`, explanation and audit records also preserve `approval_id`
when that handle is supplied through record metadata instead of a top-level
field. The backend normalizes metadata-only approval handles into the same
summary, detail, list-filter, and export contract used by top-level approval
handles, and the chat UI explanation explorer client preserves the same
metadata fallback when parsing list/get responses while carrying explicit
approval filters into export requests. This keeps approval-backed mission and
operation receipts reachable through explanation evidence without changing
approval decisions, execution, or explanation creation behavior.

As of `2026-04-26`, the selected operation detail surface can use that
explanation receipt contract from real operation and mission loop handles. The
chat UI now builds bounded `/explanations/list` queries for the selected
trace/run/artifact handles, de-duplicates returned audit/explanation records,
and renders only backend-returned records when the operator manually loads them.
It does not invent explanation status when no receipt handles or records exist.

As of `2026-04-26`, operations list and export routes can also filter by real
execution receipt handles. `/operations/list` and `/operations/export` accept
`approval_id`, `trace_id`, `run_id`, and `artifact_dir` filters, JSON export
keeps the same operation projection, CSV export includes those receipt handle
columns, and the chat UI operations client can request the same filters without
inventing receipt state. This makes execution -> approval/trace/artifact
inspection reachable from operations read models without changing worker
execution or approvals.

As of `2026-04-26`, operation readback also treats mission linkage as a
first-class read handle. Operation projections now expose top-level
`mission_id` when the task already carries it, `/operations/list` and
`/operations/export` accept a bounded `mission_id` filter, and CSV export
includes the same mission id column. This is read-model reachability only; it
does not create mission links, mutate missions, execute operations, or infer
missing mission state.

As of `2026-04-26`, operation records also preserve trace/run/artifact handles
when those handles are only stored in task metadata or input metadata. The API
operation projection and runtime mirror keep receipt/output handles as the first
source of truth, then fall back to `trace_id`, `run_id`, and `artifact_dir`
metadata for list, detail, filter, and export read models. The chat UI
operations client preserves the same fallback when parsing operation records.
This is read-model reachability only; it does not create traces, execute work,
or infer receipt state.

As of `2026-04-26`, `plan.create` operation results include a bounded plan
receipt summary alongside the existing full plan payload. Completed plan-create
operations now return the real plan status, current in-progress step id/title,
step count, and checkpoint count from the generated `PlanStateMachine` state,
so the cognition step can be inspected from operation output without parsing the
entire plan object.

As of `2026-04-26`, successful `plan.revise` operation results use that same
bounded plan receipt summary contract. Revision results preserve the full
revised plan, but also return `plan_status`, current in-progress step id/title
when present, step count, and checkpoint count as first-class output fields.
This keeps the cognition recovery path inspectable from operation read models
and the chat UI operation parser without changing planner state transitions,
execution authority, approvals, or mission mutation behavior.

As of `2026-04-26`, operation CSV export also preserves those bounded plan
summary fields. `/operations/export?format=csv` now includes `plan_status`,
current step id/title, step count, and checkpoint count from existing
plan-create or plan-revise operation output, so exported operation ledgers can
show cognition progress without parsing the full embedded plan object. This is
read-model/export only; it does not change planner state, execution, approval,
or memory behavior.

As of `2026-04-26`, untraced capability execution results also receive bounded
task execution trace/run handles. `plan.create` now returns `trace_id` and
`run_id` from the persisted task result, so `/operations/list` can filter the
completed cognition step by its real execution handles. Capability results that
already expose their own trace/run receipts, such as plugin execution, keep their
existing receipt-provided handles. No scheduling, approval, operation status
mapping, or memory-write behavior is changed.

As of `2026-04-26`, completed task audit events also carry the real execution
receipt handles when they exist. The final `status_updated` task audit entry now
records `approval_id`, `trace_id`, `run_id`, and `artifact_dir` from the result
payload or nested receipt/audit payload, and operation log projections expose
the approval/trace/run/artifact handles as first-class log fields and metadata
while preserving the same details inside `output`. The chat UI operations client
parses the approval handle from top-level, metadata, input metadata, or output
fields. This makes the operation audit trail line up with the operation result
and gate receipt without changing execution, approval, scheduling, or
memory-write behavior.

As of `2026-04-26`, the supervised-exec CLI human summary preserves the same
gate and trace handles already present in the task result. `python -m francis
supervised-exec --print-summary` now prints `approval_id` and `trace_id` when
they exist, alongside the existing task/run/artifact summary lines. This is
interface reachability only; stdout remains the JSON task record, and the CLI
does not create approvals, traces, runs, or artifact state.

As of `2026-04-26`, world-state mission activity projections preserve those
operation-log receipt handles. Mission `latest_activity` now carries real
`approval_id`, `trace_id`, `run_id`, and `artifact_dir` values from the selected
run-ledger log or operation state, and the derived `current_task` projection
keeps the same handles for chat UI settings/world-state clients. This is a
read-model/interface handoff only; it does not create approvals, traces, mutate
missions, or write memory.

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

As of `2026-04-26`, terminal mission operation memory receipts also preserve the
bounded `plan.create` summary when the completed linked operation produced one.
`operations.runtime` writes plan status, current step id/title, step count, and
checkpoint count into the continuity-ledger receipt metadata; operation run
responses, mission receipt projections, memory timeline loop projections, and
the chat UI memory timeline client preserve those fields. This is a memory
read/write contract only; it does not create plans, change execution, or alter
approval behavior.

As of `2026-04-26`, the terminal `plan.create` mission receipt readback contract
is covered through operation detail surfaces too. A chat-ingressed mission that
advances its linked `plan.create` operation now has test coverage proving the
receipt-backed plan status, current step id/title, and plan step/checkpoint
counts survive through mission latest receipt, operation detail
`latest_memory_receipt`, operation metadata `latest_memory_receipt`,
`operations/get_many`, and memory timeline loop projection. This is readback
coverage for existing receipt metadata, not new execution authority or
UI-synthesized plan state.

As of `2026-04-26`, terminal successful mission-operation memory receipts also
preserve the current-task trace handle alongside the existing current-task run
and artifact handles. `operations.runtime` writes `current_task_trace_id` into
the continuity-ledger metadata, and both the immediate operation-run receipt
projection and the mission receipt reader preserve it. This keeps the memory
handoff aligned with the same operation trace already exposed by the mission loop
without creating traces, changing execution, or expanding memory writes.

As of `2026-04-26`, mission operation memory receipt readback also promotes
existing handoff/current-task receipt handles into normalized receipt
references. When continuity-ledger metadata carries mission, operation,
approval, trace, run, or artifact handles only in `handoff_*` or
`current_task_*` fields, the mission receipt reader now preserves those handles
on the top-level receipt and `references` block so mission and operation memory
lookups remain reachable. This is readback normalization only; it does not write
new receipts, create memory, execute work, or change approval state.

As of `2026-04-27`, mission operation memory receipt readback also preserves
current-task previous approval lineage from continuity-ledger metadata. When a
terminal operation receipt already carries `current_task_previous_approval_id`
and `current_task_previous_approval_status`, the mission receipt reader now
keeps those fields alongside the current-task approval id/status instead of
dropping the retry lineage at the memory handoff. This is readback preservation
only; it does not create approvals, retry operations, write memory, or expand
execution authority.

As of `2026-04-26`, mission detail loop state also uses terminal operation
memory receipts to carry approved execution posture through the memory and
interface handoff stages. When an approved supervised execution completes, the
mission loop memory stage now exposes the receipt-backed `approval_id` and
`approval_status`, and the completed mission remains on the `interface /
review_result` handoff instead of being pulled back to a stale approval gate
from old operation metadata. This is a read-model truth fix only; it does not
approve actions, execute work, create receipts, or change policy decisions.

As of `2026-04-26`, approved mission-linked supervised execution is covered for
full receipt-handle continuity across execution readbacks. The approved
operation response, operation detail, terminal mission memory receipt, and
`/memory/timeline/list` filters preserve the same `approval_id`,
`approval_status`, `trace_id`, `run_id`, and `artifact_dir` values for the
completed run. This proves the real `gate -> execute -> trace -> memory`
readback path for artifact-backed supervised execution; it does not widen
approval authority, auto-rerun approved work, or synthesize artifact handles for
operation types that do not emit them.

As of `2026-04-26`, the chat UI settings, continuity, and dedicated missions
clients preserve those receipt-backed approval handoff handles when parsing
world-state, continuity briefing, and mission-detail mission memory receipts.
Mission memory receipt projections now retain top-level `approval_id`,
handoff/current-task approval id and status fields, and bounded receipt
references including `references.approval_id`. This is a parser contract only;
it does not render new authority, create receipts, approve work, or infer
missing approval posture.

As of `2026-04-27`, the dedicated chat UI missions client also preserves
current-task previous approval lineage on mission memory receipts. Mission detail
receipt summaries, latest memory receipt projections, memory loop-stage receipt
readbacks, and receipt arrays now keep `current_task_previous_approval_id` and
`current_task_previous_approval_status` when the backend supplies them from
receipt metadata. This is typed interface preservation only; it does not alter
mission state, approval decisions, execution authority, or memory writes.

As of `2026-04-26`, the chat UI operations client preserves operation memory
receipt handoff and current-task handles from operation detail responses.
`OperationsClient.get` now keeps receipt `active_stage`, handoff
stage/action/gate/approval/trace/run/artifact/next-step handles, current-task
source/approval/operation/gate/trace/run/artifact/next-step handles, and memory
receipt counts alongside existing references. This keeps approved supervised
execution receipt truth available to the existing operation-detail and memory
evidence client paths without creating evidence, inspecting artifacts, or
widening execution authority.

As of `2026-04-27`, the chat UI operations client also preserves current-task
previous approval lineage on operation memory receipts. Operation detail
`latest_memory_receipt` and `memory_receipts` arrays now keep
`current_task_previous_approval_id` and
`current_task_previous_approval_status` when the backend supplies them from
receipt metadata. This is typed interface preservation only; it does not alter
operation state, approval decisions, execution authority, or memory writes.

As of `2026-04-26`, the selected operation detail surface uses those operation
memory receipt handoff and current-task handles when rendering operation memory
receipt context and when building bounded memory/explanation evidence queries.
The operation detail panel now keeps the same receipt-backed source, active
stage, handoff stage/action, gate, approval, operation, trace, run, artifact,
next-step, and receipt-count handles from direct detail responses or operation
metadata fallback before falling back to older operation fields. This is
read-only interface reachability; it does not create evidence records, inspect
artifacts, decide approvals, execute work, or synthesize missing receipt state.

As of `2026-04-26`, the shared terminal mission receipt reader also carries the
same receipt-backed approval and gate posture from continuity-ledger metadata.
`francis.memory.mission_receipts` now preserves `handoff_gate`,
`handoff_approval_id`, `handoff_approval_status`, `current_task_gate`,
`current_task_approval_id`, and `current_task_approval_status` when projecting
terminal mission-operation memory receipts. This is readback-only memory truth;
it does not change execution, approval decisions, receipt writes, or UI
authority.

As of `2026-04-26`, successful terminal mission-operation memory receipts now
write and project the completed-loop operator-review gate explicitly.
`operations.runtime` records `handoff_gate=operator_review` and
`current_task_gate=operator_review` for succeeded mission-linked operation
receipts, immediate operation-run receipt projections preserve those fields, and
mission detail plus world-state current-task read models can carry that gate from
receipt truth into the `memory -> interface` handoff. This names an existing
operator review checkpoint only; it does not approve work, rerun execution, or
add a new mutation path.

As of `2026-04-26`, approval queue projections can expose the real held
mission/operation loop handles for approval-gated work. Approval list items now
derive `mission_id`, `operation_id`, `operation_status`,
`operation_result_status`, `gate`, `next_step`, `trace_id`, `run_id`, and
`artifact_dir` from existing task records that already reference the approval id;
no approval decision behavior, exact-action matching, or execution path is
changed. The chat UI approval client, world-state parser, approval panel, and
pending-approvals cards preserve and render those handles so an operator can move
from gate review back to the linked mission/task without raw JSON inspection.

As of `2026-04-26`, that approval queue loop-handle projection also preserves
trace/run/artifact handles when a linked task stores them only in task metadata
or input metadata. Result and receipt handles remain the first source of truth;
metadata is only a fallback for the approval read model. This keeps gate review
connected to existing trace and artifact evidence without creating approvals,
executing work, or inferring receipt state.

As of `2026-04-26`, approval queue projections also preserve the held task's
operation identity. Pending approval items can now expose `operation_name`,
`operation_plane`, and backend-provided `advance_action` from the linked task
record or task metadata, and the chat UI approvals client preserves those fields
for read-only review. This keeps gate review connected to the exact operation
that is blocked without changing approval decisions, exact-action matching,
execution behavior, or mission mutation.

As of `2026-04-27`, approval queue and decision-item projections also preserve
bounded plan receipt summaries from the linked held task. `/approvals/list` and
approval decision item readbacks can now expose `plan_status`, current plan step
id/title, step count, and checkpoint count when those fields already exist on
the matched task result or metadata, and the chat UI approvals client preserves
those fields with typed count parsing. This is read-only gate readback only; it
does not change approval decisions, exact-action matching, execution, memory
writes, or plan mutation.

As of `2026-04-27`, approval queue task projections also preserve current-task
previous approval lineage from the linked held task. `/approvals/list` can now
expose `current_task_previous_approval_id` and
`current_task_previous_approval_status` when those fields already exist on the
matched task result or metadata, keeping retry lineage visible at the gate
review surface. This is read-only gate readback only; it does not create
approvals, refresh approvals, approve work, execute operations, or write memory.

As of `2026-04-27`, the chat UI approvals client also preserves that current-task
previous approval lineage. `ApprovalsClient.list` and decision item parsing keep
`current_task_previous_approval_id` and
`current_task_previous_approval_status` when the backend provides them, so the
interface contract does not drop retry lineage exposed by the approval gate
readback. This is typed interface preservation only; it does not change approval
decisions, execution, policy, memory writes, or rendered controls.

As of `2026-04-26`, approval decision responses are also covered for the same
mission/operation loop-handle readback. When an approval decision returns the
approved item, the API projection and chat UI approvals client preserve the
linked `operation_id`, `operation_name`, `operation_plane`, `mission_id`,
operation status/result status, approval gate, next step, run id, artifact
directory, and payload summary fields. This is response truth only; it does not
auto-advance approved work, broaden approval authority, or change exact-action
matching.

As of `2026-04-26`, world-state governance incident evidence now preserves the
same approval-gate loop handles for pending approvals. The
`governance.pending_approvals` and `governance.awaiting_approval` incident
evidence items carry `approval_id`, `mission_id`, `operation_id`, `gate`,
`next_step`, `trace_id`, `run_id`, and `artifact_dir` when those values already
exist in the pending approval projection. No approval decision behavior,
execution path, policy rule, or memory-write path is changed.

As of `2026-04-26`, those world-state pending approval and governance incident
readbacks also preserve the held task's operation identity. Pending approval
overview items and governance incident evidence can carry `operation_name`,
`operation_plane`, and backend-provided `advance_action`, and the chat UI
settings/world-state client preserves those fields for read-only operator
review. This is projection truth only; it does not change approval decisions,
execution, policy gates, or mission mutation.

As of `2026-04-27`, world-state pending approval readbacks and governance
incident evidence also preserve approval-gate plan summaries. Pending approval
overview items and approval incident evidence can now carry `plan_status`,
current plan step id/title, step count, and checkpoint count from the pending
approval projection, and the chat UI settings/world-state client preserves those
fields with typed count parsing. This keeps the `plan -> gate` context visible
in the world-state interface path only; it does not change approval decisions,
execution, policy gates, memory writes, or plan mutation.

As of `2026-04-27`, the chat UI settings/world-state client also preserves
current-task previous approval lineage on pending approval overview items.
`SettingsClient.getWorldState` keeps `current_task_previous_approval_id` and
`current_task_previous_approval_status` when `/system/world_state` returns them
from the shared approval projection. This is typed interface preservation only;
it does not change approval decisions, execution, policy gates, memory writes,
or rendered controls.

As of `2026-04-27`, the chat UI approval review surfaces render those
approval-gate plan summaries when backend truth provides them. The selected
approval card, approval queue cards, and system pending-approval overview now
show the read-only plan status, current step id/title, step count, and
checkpoint count already parsed by the approvals and world-state clients. This
is interface readback only; it does not change approval decisions, execution,
policy gates, memory writes, or plan mutation.

As of `2026-04-26`, mission loop gate and execute projections preserve trace
handles when the linked operation already exposes one. `/missions/{mission_id}`
now carries `trace_id` through the active gate handoff plus gate and execute
stages alongside the existing run and artifact handles, so operator surfaces can
move from gate review toward trace evidence without relying only on
`current_task`. This does not mint traces, approve work, execute operations, or
write memory.

As of `2026-04-26`, the chat UI mission client contract also proves those loop
stage trace handles survive browser-side parsing. The ORB mission inspector
fixture now requires `trace_id` on the active handoff, gate stage, and execute
stage, alongside the existing approval, operation, run, and artifact handles.
This is a client contract proof only; it does not change UI authority, approval
decisions, execution, backend projection behavior, or memory writes.

As of `2026-04-26`, chat mission ingress continuity entries preserve bounded ORB
loop metadata for newly declared missions. The assistant ledger entry written by
`POST /chat/send` or websocket mission ingress now carries the real mission id,
ingress plane, active loop stage, handoff stage/action/next step, current-task
source/next step, and receipt counts from the mission detail projection. The
conversation ledger still redacts the operator objective before persistence and
does not add execution, approval, or memory-timeline writes.

As of `2026-04-26`, chat mission ingress metadata also preserves the trace and
receipt handles needed to reconnect the interface to completed or gated mission
work. Compact assistant ledger metadata keeps handoff/current-task approval
status, trace id, run id, and artifact directory when the mission detail
projection already has them, websocket mission-ingress events preserve top-level
mission memory receipt summaries, and the chat UI protocol parser keeps those
receipt summaries on `/chat/send` messages. This is pass-through only; it does
not execute operations, mint receipts, inspect artifacts, or infer completion.

As of `2026-04-27`, chat mission ingress compact metadata also preserves
current-task previous approval lineage when the mission detail projection already
contains it. Assistant continuity entries now carry
`current_task_previous_approval_id` and
`current_task_previous_approval_status` alongside the current-task approval
id/status, trace, run, and artifact handles. This is pass-through interface
metadata only; it does not create approvals, retry operations, execute work, or
write new memory receipts.

As of `2026-04-26`, explicit chat mission ingress also creates the first bounded
mission-linked `plan.create` operation. `POST /chat/send` and websocket mission
ingress still require an explicit `/mission` or `mission:` declaration and still
respect operator posture before mutating state, but a successful declaration now
advances the new mission through the existing mission runtime once so the first
queued operation is linked immediately. The response, websocket event, assistant
continuity metadata, memory timeline loop projection, and chat UI message
surface preserve the real operation id and `create_first_operation` advance
receipt. This queues the first plan operation only; it does not run the
operation, bypass governance, make approval decisions, or claim terminal memory.

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

As of `2026-04-27`, memory timeline loop projections also preserve
current-task previous approval lineage. When mission-loop continuity metadata
already includes `current_task_previous_approval_id` and
`current_task_previous_approval_status`, `/memory/timeline/list` and CSV export
keep those fields in the structured loop readback alongside the current-task
approval id/status. This is readback/export preservation only; it does not
create approvals, retry operations, write memory, or expand execution authority.

As of `2026-04-27`, the chat UI memory timeline client also preserves that
current-task previous approval lineage. `MemoryTimelineClient.list` and `get`
keep `current_task_previous_approval_id` and
`current_task_previous_approval_status` from either explicit `loop` payloads or
sparse event metadata. This is browser-side readback preservation only; it does
not create approvals, retry operations, write memory, or expand execution
authority.

As of `2026-04-26`, memory timeline filters can also resolve exact loop-only
mission receipt handles. `/memory/timeline/list` now treats handoff and
current-task operation, trace, approval, run, and artifact handles in event
metadata as queryable read references when the normalized top-level reference is
not present. This keeps receipt-backed evidence lookup aligned with the visible
`loop` projection without broad search, inferred linkage, execution, or
approval authority.

As of `2026-04-27`, memory timeline filters and public references also resolve
loop-only mission handles from `handoff_mission_id` and
`current_task_mission_id`. `/memory/timeline/list?mission_id=...` can now find
continuity receipts whose mission id is present only in mission-loop metadata,
and JSON/CSV readbacks promote that same handle into the bounded
`references.mission_id` field. This is retrieval/readback normalization only; it
does not create memory, execute operations, infer mission state, or broaden
authority beyond exact supplied receipt handles.

As of `2026-04-27`, the chat UI memory evidence query builder follows those
loop-only mission receipt handles. `buildMemoryEvidenceQueries` now recognizes
`current_task_mission_id` and `handoff_mission_id` on terminal receipts before
falling back to normalized mission references, so operator memory-evidence
lookups can request bounded mission evidence for receipts whose mission id is
only present in loop current-task or handoff metadata. This is interface query
reachability only; it does not create memory, change backend filtering, execute
operations, alter approvals, or infer mission state.

As of `2026-04-26`, memory timeline public events also promote those loop-only
receipt handles into the bounded `references` block when top-level references
are sparse. `/memory/timeline/list`, `/memory/timeline/get`, and exports now
prefer existing normalized mission/operation/trace/approval/run/artifact
references, then fall back to current-task or handoff handles already present in
redacted loop metadata. This keeps evidence found through loop-handle filters
self-describing in JSON and CSV readbacks without minting new traces, approvals,
runs, artifacts, operations, or memory receipts.

As of `2026-04-26`, the chat UI selected-operation memory evidence cards render
those loop-only handles when memory timeline events do not include normalized
top-level references. The reference line now falls back to event `loop`
current-task and handoff operation, trace, approval, run, and artifact handles,
so evidence found by the backend loop-handle filters does not appear
unlinked in the operator surface. This is display-only; it does not change
queries, execution, approvals, or receipt writes.

As of `2026-04-26`, memory timeline loop projections also preserve
`current_task_trace_id` from mission-loop continuity metadata. This keeps
current-task trace handles aligned with the existing handoff trace, run, and
artifact handles when the operator follows memory evidence back to active or
completed mission work. This is a read-model/client contract change only; it
does not inspect artifacts, execute operations, mint memory receipts, or infer
completion.

As of `2026-04-26`, direct memory timeline writes can also preserve structured
`references` and `loop` objects instead of requiring callers to flatten every
mission-loop handle into metadata first. `/memory/timeline/record` and
`/memory/timeline/create` now normalize structured mission, operation, trace,
approval, run, artifact, handoff, and current-task fields into the same redacted
public event contract used by continuity-ledger receipts, including persistence
reload. This is a memory write/read contract fix only; it does not create
mission state, execute operations, or infer missing linkage.

As of `2026-04-26`, memory timeline CSV exports now preserve the same explicit
receipt references and loop handles that list/get/export JSON already expose.
`/memory/timeline/export?format=csv` includes bounded mission, operation, trace,
approval, run, artifact, handoff, current-task, plan, and receipt-count columns
derived from the existing public event `references` and `loop` projections. This
is export readback only; it does not create memory, inspect artifacts, change
queries, execute operations, or synthesize missing receipts.

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

As of `2026-04-26`, the top-level mission detail `current_task` projection now
keeps that operation identity alongside the queue item's current-task view.
`GET /missions/{mission_id}` carries the backend-provided operation name, ORB
plane, and advance action for the same current operation, so interface consumers
do not have to fall back to the nested queue item to render the real current
plan/execute stage identity. This is read-model alignment only; it does not
create operations, advance missions, or add execution authority.

As of `2026-04-27`, that top-level mission detail `current_task` projection also
preserves previous approval lineage. `GET /missions/{mission_id}` and enriched
mission queue readbacks carry `previous_approval_id` and
`previous_approval_status` from existing mission/queue truth alongside the
current approval id and status. This is read-model alignment only; it does not
approve work, refresh approvals, execute operations, or change queue
eligibility.

As of `2026-04-26`, the chat UI mission client preserves that advance operation
identity without adding new visual claims. `MissionQueueItem` and
`MissionCurrentTask` parsing now retain the backend-provided operation name,
operation ORB plane, and advance action, so later interface surfaces can render
the real plan/execute stage identity from the typed mission contract instead of
falling back to ids alone.

As of `2026-04-26`, the selected mission inspector and linked-operation mission
bridge render that backend-provided current-task operation identity. When the
mission detail contract includes operation name, ORB plane, or advance action,
the existing read-only mission flow rows show those fields next to the
current-task id and receipt posture. This is interface exposure only; it does
not add mission controls, infer missing operation identity, or change execution
authority.

As of `2026-04-26`, mission detail receipt summaries also preserve the current
operation identity and plan summary. `GET /missions/{mission_id}` now carries
`current_operation_name`, `current_operation_plane`, `current_advance_action`,
and existing plan status/current-step/count fields inside `receipt_summary`
when the linked operation already exposes them. This is compact readback only;
it does not alter mission advancement, execution authority, or plan generation.

As of `2026-04-26`, the chat UI mission client preserves those mission detail
receipt-summary operation identity and plan fields. `MissionReceiptSummary`
parsing now retains the current operation name, ORB plane, advance action, plan
status, current plan step, and plan/checkpoint counts when the backend provides
them, without adding new rendering claims or execution authority.

As of `2026-04-26`, the chat UI mission inspector and queue cards render those
receipt-summary operation identity and plan fields from existing backend/client
truth. The selected mission Continuity Receipts panel and mission queue receipt
line now show task name, ORB plane, advance action, plan status, current plan
step, and plan/checkpoint counts when present. This is read-only interface
exposure; it does not infer missing fields, create operations, or add execution
authority.

As of `2026-04-26`, continuity and world-state mission current-task read models
also preserve that backend-backed operation identity. Mission queue, recent
mission, and shift-briefing current-task projections can now carry operation name,
operation ORB plane, and last advance action from mission metadata or operation
activity, so return-to-work surfaces do not lose the plan/execute identity after
leaving the mission detail route. This is read-model propagation only; it does not
add new controls, execute missions, infer missing operation records, or change
mission authority.

As of `2026-04-27`, continuity and world-state mission current-task read models
also preserve previous approval lineage. Shift-briefing/deadletter current-task
projections now carry `previous_approval_id` and `previous_approval_status` from
existing mission and approval projection truth alongside the current approval id
and status. This is read-model propagation only; it does not approve work,
refresh approvals, execute missions, or widen memory writes.

As of `2026-04-26`, chat mission ingress continuity metadata and memory timeline
loop projections also preserve current-task operation identity. Compact assistant
ledger metadata, `/memory/timeline/list` loop projection, and the chat UI memory
timeline client now carry operation name, operation ORB plane, and advance action
with the existing current-task operation id. This is contract propagation only; it
does not create memory writes outside the existing chat ingress path, infer
missing operation records, or add execution authority.

As of `2026-04-26`, the chat UI settings/world-state client also preserves that
current-task operation identity across world-state mission projections,
continuity briefing handoff lists, and mission memory receipts. The parser now
keeps operation name, operation ORB plane, and advance action when the backend
already supplies those fields. This is typed interface preservation only; it does
not add new rendering, infer missing operation records, or widen backend state.

As of `2026-04-26`, the chat UI settings/world-state client also preserves compact
mission receipt-summary operation identity and plan fields on world-state mission
projections. `WorldStateMissionReceiptSummary` now keeps current operation name,
ORB plane, advance action, plan status, current plan step, and plan/checkpoint
counts when the backend supplies them. This is typed overview-contract
preservation only; it does not add rendering, infer missing operation records, or
widen backend state.

As of `2026-04-26`, the chat UI missions client preserves the same current-task
operation identity on mission memory receipts. Mission detail receipt summaries,
latest memory receipt projections, and receipt arrays now keep current-task
operation name, operation ORB plane, and advance action alongside the existing
current-task operation id. This is client contract preservation only; it does not
add UI rendering, mutate mission state, or infer missing receipt fields.

As of `2026-04-26`, the chat UI operations client preserves that same
current-task operation identity on operation memory receipts. Direct operation
run `memory_receipt` responses, operation detail `latest_memory_receipt`, and
operation detail `memory_receipts` arrays now keep operation name, operation ORB
plane, and advance action alongside existing receipt references. This is client
contract preservation only; it does not add UI rendering, execute operations, or
infer missing receipt fields.

As of `2026-04-26`, the chat UI operations client also preserves plan readback
fields on operation memory receipts. Direct operation-run `memory_receipt`
responses, operation detail `latest_memory_receipt`, and operation detail
`memory_receipts` arrays now keep receipt-backed `plan_status`, current plan
step id/title, and plan step/checkpoint counts when the backend supplies them.
This is typed client-boundary preservation only; it does not add rendering,
infer missing plan state, or change operation execution authority.

As of `2026-04-26`, terminal mission-linked operation receipts now emit that
current-task operation identity from the backend receipt source. The continuity
ledger append, returned operation-run `memory_receipt`, operation detail
`latest_memory_receipt`, operation detail `memory_receipts`, and memory timeline
loop projection now carry the operation name, operation ORB plane, and bounded
advance action with the existing current-task operation id. This is
receipt-contract alignment only; it does not add operation execution authority,
infer missing operation records, or change mission advancement.

As of `2026-04-26`, the chat UI selected-operation receipt surface renders that
backend-backed operation identity when receipts provide it. The operation detail
memory receipt line and post-run notice now show receipt-backed operation name,
operation ORB plane, and advance action alongside existing mission/task/trace
handles. This is read-only interface exposure only; it does not create new
receipt fields, execute operations, or infer missing operation identity.

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

As of `2026-04-27`, those direct operation-run `memory_receipt` projections
also carry the same flat mission, operation, approval, trace, run, and artifact
handles that the structured `references` object already carried. The operations
runtime promotes direct, current-task, or handoff receipt handles into both
shapes, and the chat UI operations client preserves both shapes for operation
run and detail readbacks. This is receipt contract normalization only; it does
not change execution, approval decisions, memory-write timing, or receipt
creation conditions.

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

As of `2026-04-26`, Stage 3 session-continuity readiness evidence also preserves
normalized memory receipt approval, run, and artifact handles from the same
bounded mission receipt samples. This keeps continuity readbacks linked to the
existing governed operation handoff receipts without widening execution,
approval, or memory-write authority.

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

As of `2026-04-26`, artifact inspection can also link the inspected handle back
to its originating mission-operation receipt when the continuity ledger already
contains that receipt truth. `GET /artifacts/inspect` now scans existing
operation runtime ledger receipts for matching `artifact_dir`,
`handoff_artifact_dir`, or `current_task_artifact_dir` handles and returns a
bounded `originating_receipt` block with mission, operation, approval, trace,
run, artifact, status, handoff, and redacted recovery context. The chat UI
artifacts client and shared inspection panel preserve that origin readback.
This is artifact-origin readback only; it does not inspect file contents, mint
receipts, execute work, retry failed operations, or deadletter missions.

As of `2026-04-26`, artifact-origin readback also preserves the receipt-backed
handoff and current-task context used by the Stage 3 loop. Originating artifact
receipts now keep active/handoff stages, handoff operation/trace/run/artifact
handles, handoff approval id/status, current-task gate, approval id/status,
operation name/plane/advance action, trace/run/artifact handles, and next-step
guidance through both `GET /artifacts/inspect` and the chat UI artifacts client.
The shared artifact inspection panel renders those backend-projected handles as
origin context. This is read-only artifact receipt context; it does not approve
actions, inspect file contents, retry work, or synthesize missing receipt state.

As of `2026-04-27`, backend artifact-origin readback also preserves current-task
previous approval lineage from the same originating mission-loop receipt.
`GET /artifacts/inspect` now carries `current_task_previous_approval_id` and
`current_task_previous_approval_status` when the matched continuity receipt
already provides them. This is read-only artifact receipt context; it does not
approve actions, refresh approvals, inspect file contents, retry work, or infer
missing lineage.

As of `2026-04-27`, artifact-origin readback also normalizes loop-only receipt
handles into the same bounded origin reference contract. When the matched
mission-loop receipt provides mission, operation, approval, trace, run, or
artifact handles only through current-task or handoff metadata,
`GET /artifacts/inspect` promotes those handles into `mission_id`,
`operation_id`, `approval_id`, `trace_id`, `run_id`, `artifact_dir`, and the
`references` block using current-task handles before handoff handles. The chat
UI artifacts client now preserves returned current-task/handoff mission aliases
and current-task previous approval lineage in the originating receipt. This is
read-only artifact receipt normalization only; it does not inspect file contents,
execute operations, alter approvals, retry work, or infer missing mission state.

As of `2026-04-26`, artifact-origin readback also preserves bounded plan receipt
summaries from the same originating mission-loop receipt. `GET /artifacts/inspect`
now projects `plan_status`, current step id/title, step count, and checkpoint
count when the matched continuity receipt provides them, and the chat UI
artifacts client preserves those fields with typed count parsing. This is
metadata-only origin readback; it does not create plans, revise plans, inspect
artifact contents, execute work, or infer missing plan state.

As of `2026-04-26`, artifact-origin trace rendering follows the same
receipt-backed current-task and handoff priority as the rest of the origin
context. The chat UI artifacts module now exposes `artifactOriginTraceId`, and
the shared artifact inspection panel renders `current_task_trace_id` or
`handoff_trace_id` when an originating receipt is sparse at top-level
`trace_id`, falling back to legacy receipt references only after those handles.
A real-browser proof against a mock API confirmed the selected-operation
artifact inspection path renders the current-task trace from backend-shaped
origin receipt context without HTTP failures. This is read-only trace
reachability; it does not inspect file contents, create traces, or infer missing
receipt handles.

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

As of `2026-04-26`, mission detail interface readback preserves bounded plan
summary context on the same current-task and interface-stage surfaces used for
operator handoff. When the linked operation output already carries
`plan_status`, current step id/title, step count, and checkpoint count,
`GET /missions/{id}` now returns those fields on `current_task` and
`loop_state.interface` in addition to the existing plan, receipt, and operation
surfaces. This is read-only plan context for the Stage 3 loop; it does not
revise plans, execute work, approve actions, or synthesize missing plan output.

As of `2026-04-26`, the chat UI missions client preserves that mission
current-task plan summary contract. `MissionCurrentTask` now keeps
`plan_status`, current step id/title, step count, and checkpoint count from
mission detail payloads, and the missions client contract test proves those
fields survive browser-side parsing. This is typed readback only; it does not
add new rendering claims, plan mutation, execution authority, or approval
authority.

As of `2026-04-26`, the chat UI settings and continuity client also preserves
plan summary context on mission memory receipts. `MissionMemoryReceipt` now
keeps `plan_status`, current step id/title, step count, and checkpoint count
from world-state and briefing payloads, and the settings client contract test
proves those fields survive parsing on recent-mission and mission-briefing
memory receipts. This is typed readback only; it does not add new rendering
claims, memory writes, plan mutation, execution authority, or approval
authority.

As of `2026-04-26`, completed receipt-backed mission loops now return their
active handoff to the `interface` stage after memory closes. A completed mission
with a terminal operation memory receipt keeps the `memory` stage and receipt
details intact, but `loop_state.active_stage` and the top-level handoff now
point to `interface` / `review_result` with the real operation, trace, run, and
artifact handles. This makes the final `memory -> interface` leg visible without
adding execution authority or changing blocked, failed, deadlettered, or
pre-memory missions.

As of `2026-04-26`, succeeded terminal mission-operation memory receipts carry
that same completed-loop interface handoff into continuity-ledger memory
evidence. The receipt metadata now records `active_stage=interface`,
`handoff_action=review_result`, the real operation/trace/run/artifact handles,
and `review_completed_mission` next-step context for succeeded mission-linked
operations. Failed terminal receipts remain on their existing recovery context
path.

As of `2026-04-26`, shared mission memory receipt projections and
world-state/briefing current-task projections preserve that completed-loop
handoff. `mission_operation_receipts()` now keeps the receipt-backed loop
handoff/current-task fields, and completed mission briefing cards prefer the
receipt-backed `review_result` / `review_completed_mission` posture over the
older status-derived `review_completion` fallback when a succeeded terminal
receipt is present.

As of `2026-04-26`, the chat UI mission and settings clients preserve those
completed-loop receipt handoff fields at the browser contract boundary.
Mission detail, receipt summary, memory receipt arrays, Shift Briefing
recently-completed items, and shared briefing memory receipt projections now
keep `active_stage`, `handoff_*`, `current_task_*`, and receipt count fields
from backend memory receipts instead of dropping them before operator surfaces
can render the completed `memory -> interface` handoff.

As of `2026-04-26`, the chat UI mission and settings clients also preserve the
receipt-backed gate names on those mission memory receipts. Mission detail,
receipt summary, memory receipt arrays, Shift Briefing recently-completed items,
and shared briefing memory receipt projections now keep `handoff_gate` and
`current_task_gate` when the backend provides them, so the operator interface can
show the real approval gate context already recorded by memory without
inventing approval posture or changing execution authority.

As of `2026-04-26`, the mission operation memory receipt helper contract is
covered for plan readback metadata. `mission_operation_receipts()` and
`operation_memory_receipts()` preserve receipt-backed `plan_status`, current
plan step id/title, and plan step/checkpoint counts from continuity receipt
metadata alongside operation/current-task identity. This is read-model contract
coverage for existing receipt data; it does not add new memory writes,
execution authority, or UI-synthesized plan state.

As of `2026-04-26`, existing chat UI mission receipt surfaces render those
receipt-backed completed-loop handoff fields when the backend provides them.
Shift Briefing memory evidence, recently-completed mission cards, selected
mission continuity receipts, and mission loop stage memory rows now show the
backend `active_stage`, `handoff`, `next`, current-task handle, and receipt-count
lineage without adding new mutation controls or UI-synthesized state.

As of `2026-04-26`, memory and explanation evidence queries can also follow
those completed-loop receipt handoff handles. Browser-side memory evidence now
uses receipt `current_task_*` / `handoff_*` mission, operation, approval, trace,
run, and artifact handles as bounded fallbacks, and explanation evidence uses
the same approval/trace/run/artifact fallback from the selected mission receipt
before giving up. This keeps completed `memory -> interface` handoff review
connected to existing approval, trace, artifact, and memory evidence paths
without creating new evidence or execution authority.

As of `2026-04-26`, those browser-side evidence queries prefer loop-specific
receipt handles when they exist. Explicit operator-selected ids still win, but
selected mission receipt queries now choose `current_task_*` then `handoff_*`
handles before older top-level or reference handles for operation, approval,
trace, run, and artifact filters. This keeps completed handoff review pointed at
the active loop evidence instead of stale receipt aliases without broadening the
query scope or inventing evidence.

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

Latest targeted validation for the `2026-04-28` Stage 5/Reactor external
escalation adapter preflight slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_external_escalation_adapter_preflight_distinguishes_local_outbox tests\unit\test_reactor_event_queue.py::test_reactor_external_escalation_attempt_records_adapter_preflight_without_delivery tests\unit\test_reactor_event_queue.py::test_reactor_deadletter_escalation_handoff_records_receipt_without_execution -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py::test_reactor_deadletter_resolve_route_records_escalation_pending_without_execution -q`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Stage 5/Reactor
proposal-review UI readback slice:

- `cd apps\chat_ui; npm run test`
  Result: `passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 5/Reactor deadletter
review receipt slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `failed before formatting src\francis\reactor\events.py; passed after running Ruff format`
- `python -m ruff format src\francis\reactor\events.py`
  Result: `passed`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 5/Reactor due retry
dispatch-attempt slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 5/Reactor retry due
handoff slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 5/Reactor retry schedule
queue slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `failed before mechanical formatting of src\francis\reactor\events.py; passed after running Ruff format`
- `python -m ruff format src\francis\reactor\events.py`
  Result: `passed`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 5/Reactor
verification-state receipt slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `failed once because the existing approval-required blocker test
  expected awaiting_approval where the new verification receipt truthfully
  reported approval_required; passed after correcting that assertion`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 5/Reactor
stable-return receipt slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `failed once while existing assertions still expected the previous
  latest receipt kinds; passed after updating the Reactor contract tests for
  reactor.stable_return.receipt as the latest terminal-for-now receipt`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`; Ruff reported non-blocking cache write warnings under
  `.ruff_cache`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 5/Reactor
deadletter queue baseline slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: failed once during collection because the new unit test imported
  deadletter helpers from `events.py`; failed once on Windows path length for
  verbose deadletter filenames; passed after importing from
  `francis.reactor.deadletters` and shortening persisted deadletter ids
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `failed before formatting src\francis\reactor\deadletters.py; passed
  after formatting`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 5/Reactor
approval-decision reconciliation slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_approvals.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `failed before formatting src\francis\reactor\events.py; passed
  after formatting`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 5/Reactor
approval-request queue handoff slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `python -m pytest tests\test_api_approvals.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_contract_chat_ui.py tests\unit\test_imports.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `failed once on an unrelated capability-catalog filtered assertion
  that used the default page limit against a locally crowded plugin catalog;
  passed after the assertion used the same bounded high limit as the preceding
  catalog readback`

Latest targeted validation for the `2026-04-27` Stage 5/Reactor
review-queue operator UI readback slice:

- `node --test --experimental-strip-types src/reactor/index.test.ts`
  Result: `passed`
- `python -m pytest tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `passed`
- `python -m ruff check tests\test_api_contract_chat_ui.py`
  Result: `passed`; Ruff reported a non-blocking cache write warning under
  `.ruff_cache`
- `python -m ruff format --check tests\test_api_contract_chat_ui.py`
  Result: `passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`; Git reported a non-blocking package.json line-ending
  warning

Latest targeted validation for the `2026-04-27` Stage 5/Reactor
review-queue projection slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `failed once during collection because of an indentation error in
  src\francis\reactor\events.py; passed after correction`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py tests\test_api_contract_chat_ui.py tests\unit\test_imports.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 5/Reactor
event review-filter readback slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py tests\test_api_contract_chat_ui.py tests\unit\test_imports.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 5/Reactor
retry-exhaustion receipt slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`; Ruff reported non-blocking cache write warnings under
  `.ruff_cache`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `failed before formatting src\francis\reactor\events.py; passed
  after formatting`; later reruns reported non-blocking cache write warnings
  under `.ruff_cache`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py tests\test_api_contract_chat_ui.py tests\unit\test_imports.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 5/Reactor
retry-candidate receipt slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`; Ruff reported non-blocking cache write warnings under
  `.ruff_cache`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`; Ruff reported non-blocking cache write warnings under
  `.ruff_cache`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py tests\test_api_contract_chat_ui.py tests\unit\test_imports.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 5/Reactor
deadletter-candidate receipt slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `failed before formatting test updates; passed after formatting
  tests\unit\test_reactor_event_queue.py`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 5/Reactor
blocked-dispatch blocker readback slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`; Ruff reported non-blocking cache write warnings under
  `.ruff_cache`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 5/Reactor
dispatch-attempt receipt slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `failed before widening the payload helper type; passed after fix`
- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py tests\test_api_contract_chat_ui.py tests\unit\test_imports.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 5/Reactor trigger
intake queue slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py tests\test_api_contract_chat_ui.py tests\unit\test_imports.py -q`
  Result: `passed`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py src\francis\api\app.py`
  Result: `failed before fixing optional trigger narrowing; passed after fix`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py src\francis\api\app.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py src\francis\api\app.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge plugin-browser
capability catalog readback slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\plugin_browser\index.test.ts`
  Result: `8 passed`
- `python -m pytest tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `78 passed`
- `python -m ruff check tests\test_api_contract_chat_ui.py`
  Result: `passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`; Git also reported the existing CRLF/LF working-copy warning
  for `apps/chat_ui/src/plugin_browser/index.ts`

Latest targeted validation for the `2026-04-27` Stage 4/Forge capability
catalog API readback slice:

- `python -m pytest tests\test_api_plugins.py::test_plugins_capability_catalog_readback -q`
  Result: `passed`
- `python -m pytest tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m pytest tests\unit\test_capability_catalog_projection.py tests\unit\test_capability_catalog_coherence.py tests\unit\test_capability_marketplace.py -q`
  Result: `4 passed`
- `python -m pytest tests\test_api_plugins.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge plugin-browser
promotion action surface slice:

- `cd apps\chat_ui; npm run test`
  Result: `77 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge plugin-browser
promotion action receipt response contract slice:

- `cd apps\chat_ui; npm run test`
  Result: `77 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge plugin-browser
promotion-receipt readback slice:

- `python -m pytest tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_forge.py::test_forge_proposal_and_promotion_readback -q`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `76 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `python -m ruff check tests\test_api_contract_chat_ui.py`
  Result: `passed`
- `python -m ruff format --check tests\test_api_contract_chat_ui.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge plugin-browser
proposal-decision workflow slice:

- `python -m pytest tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_forge.py::test_forge_proposal_decision_receipts_without_promotion -q`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `75 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `python -m ruff check tests\test_api_contract_chat_ui.py`
  Result: `passed`
- `python -m ruff format --check tests\test_api_contract_chat_ui.py`
  Result: `passed`; Ruff also reported a non-blocking cache write warning for
  `.ruff_cache`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge plugin-browser
validation-evidence readback slice:

- `cd apps\chat_ui; npm run test`
  Result: `74 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge capability
catalog validation-lineage slice:

- `python -m pytest tests\unit\test_capability_catalog_projection.py tests\unit\test_capability_catalog_coherence.py -q`
  Result: `3 passed`
- `python -m pytest tests\unit\test_capability_catalog_projection.py tests\unit\test_capability_catalog_coherence.py tests\unit\test_capability_marketplace.py -q`
  Result: `4 passed`
- `python -m mypy src\francis\economy\markets\capability_catalog_projection.py src\francis\economy\markets\capability_catalog_coherence.py`
  Result: `passed`
- `python -m ruff check src\francis\economy\markets\capability_catalog_projection.py src\francis\economy\markets\capability_catalog_coherence.py tests\unit\test_capability_catalog_projection.py tests\unit\test_capability_catalog_coherence.py`
  Result: `passed`
- `python -m ruff format --check src\francis\economy\markets\capability_catalog_projection.py src\francis\economy\markets\capability_catalog_coherence.py tests\unit\test_capability_catalog_projection.py tests\unit\test_capability_catalog_coherence.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge proposal-quality
validation-receipt summary readback slice:

- `python -m pytest tests\unit\test_forge_proposal_quality_summary.py tests\unit\test_forge_proposal_quality.py -q`
  Result: `5 passed`
- `python -m pytest tests\test_api_forge.py::test_forge_proposal_and_promotion_readback -q`
  Result: `passed`
- `python -m pytest tests\test_api_forge.py tests\unit\test_forge_proposal_quality_summary.py tests\unit\test_forge_proposal_quality.py -q`
  Result: `7 passed`
- `python -m mypy src\francis\forge\proposal_quality_summary.py src\francis\forge\proposal_quality.py src\francis\api\routes\forge.py`
  Result: `passed`
- `python -m ruff check src\francis\forge\proposal_quality_summary.py tests\unit\test_forge_proposal_quality_summary.py tests\test_api_forge.py`
  Result: `passed`
- `python -m ruff format --check src\francis\forge\proposal_quality_summary.py tests\unit\test_forge_proposal_quality_summary.py tests\test_api_forge.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge proposal-quality
validation-receipt evidence readback slice:

- `python -m pytest tests\unit\test_forge_proposal_quality.py -q`
  Result: `3 passed`
- `python -m pytest tests\test_api_forge.py::test_forge_proposal_and_promotion_readback -q`
  Result: `passed`
- `python -m pytest tests\test_api_forge.py tests\unit\test_forge_proposal_quality.py tests\unit\test_forge_proposal_quality_summary.py -q`
  Result: `7 passed`
- `python -m mypy src\francis\forge\proposal_quality.py src\francis\api\routes\forge.py`
  Result: `passed`
- `python -m ruff check src\francis\forge\proposal_quality.py tests\unit\test_forge_proposal_quality.py tests\test_api_forge.py`
  Result: `passed`
- `python -m ruff format --check src\francis\forge\proposal_quality.py tests\unit\test_forge_proposal_quality.py tests\test_api_forge.py`
  Result: `passed after formatting tests\unit\test_forge_proposal_quality.py`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge validation
receipt promotion-evidence linkage slice:

- `python -m pytest tests\test_api_forge.py::test_forge_proposal_and_promotion_readback -q`
  Result: `passed`
- `python -m mypy src\francis\api\routes\plugins.py src\francis\api\routes\forge.py`
  Result: `passed`
- `python -m pytest tests\test_api_forge.py tests\test_api_plugins.py tests\test_api_plugins_permission_gate.py tests\unit\test_plugin_factory_spec_builder.py tests\unit\test_forge_proposal_quality_summary.py tests\unit\test_forge_proposal_quality.py -q`
  Result: `20 passed`
- `python -m ruff check src\francis\api\routes\plugins.py src\francis\api\routes\forge.py tests\test_api_forge.py tests\test_api_plugins.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\plugins.py src\francis\api\routes\forge.py tests\test_api_forge.py tests\test_api_plugins.py`
  Result: `passed after formatting tests\test_api_forge.py`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge validation
receipt and readback slice:

- `python -m pytest tests\test_api_forge.py::test_forge_proposal_and_promotion_readback -q`
  Result: `passed`
- `python -m mypy src\francis\api\routes\plugins.py src\francis\api\routes\forge.py`
  Result: `passed`
- `python -m pytest tests\test_api_forge.py tests\test_api_plugins.py tests\test_api_plugins_permission_gate.py tests\unit\test_plugin_factory_spec_builder.py tests\unit\test_forge_proposal_quality_summary.py tests\unit\test_forge_proposal_quality.py -q`
  Result: `20 passed`
- `python -m ruff check src\francis\api\routes\plugins.py src\francis\api\routes\forge.py tests\test_api_forge.py tests\test_api_plugins.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\plugins.py src\francis\api\routes\forge.py tests\test_api_forge.py tests\test_api_plugins.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge proposal-quality
status summary readback slice:

- `python -m pytest tests\test_api_forge.py::test_forge_proposal_and_promotion_readback -q`
  Result: `passed`
- `python -m pytest tests\test_api_forge.py tests\unit\test_forge_proposal_quality_summary.py tests\unit\test_forge_proposal_quality.py -q`
  Result: `7 passed`
- `python -m mypy src\francis\api\routes\forge.py src\francis\forge\proposal_quality_summary.py src\francis\forge\proposal_quality.py`
  Result: `passed`
- `python -m ruff check src\francis\api\routes\forge.py src\francis\forge tests\test_api_forge.py tests\unit\test_forge_proposal_quality_summary.py tests\unit\test_forge_proposal_quality.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\forge.py src\francis\forge tests\test_api_forge.py tests\unit\test_forge_proposal_quality_summary.py tests\unit\test_forge_proposal_quality.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge passive
proposal-quality summary helper slice:

- `python -m pytest tests\unit\test_forge_proposal_quality_summary.py tests\unit\test_forge_proposal_quality.py -q`
  Result: `5 passed`
- `python -m pytest tests\unit\test_imports.py -q`
  Result: `17 passed, 1 skipped`
- `python -m mypy src\francis\forge\proposal_quality_summary.py src\francis\forge\proposal_quality.py`
  Result: `passed`
- `python -m ruff check src\francis\forge tests\unit\test_forge_proposal_quality_summary.py tests\unit\test_forge_proposal_quality.py`
  Result: `passed`
- `python -m ruff format --check src\francis\forge tests\unit\test_forge_proposal_quality_summary.py tests\unit\test_forge_proposal_quality.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge proposal
quality-readback API slice:

- `python -m pytest tests\test_api_forge.py::test_forge_proposal_and_promotion_readback -q`
  Result: `passed`
- `python -m pytest tests\unit\test_forge_proposal_quality.py -q`
  Result: `3 passed`
- `python -m mypy src\francis\api\routes\forge.py src\francis\forge\proposal_quality.py`
  Result: `passed`
- `python -m ruff check src\francis\api\routes\forge.py src\francis\forge tests\test_api_forge.py tests\unit\test_forge_proposal_quality.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\forge.py src\francis\forge tests\test_api_forge.py tests\unit\test_forge_proposal_quality.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `python -m pytest tests\test_api_forge.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_plugins.py::test_plugins_build_lifecycle_and_run -q`
  Result: `passed`
- `python -m pytest tests\test_api_contract_chat_ui.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge passive
proposal quality-readiness analyzer slice:

- `python -m pytest tests\unit\test_forge_proposal_quality.py -q`
  Result: `3 passed`
- `python -m mypy src\francis\forge\proposal_quality.py`
  Result: `passed`
- `python -m ruff check src\francis\forge\proposal_quality.py tests\unit\test_forge_proposal_quality.py`
  Result: `passed`
- `python -m ruff format --check src\francis\forge\proposal_quality.py tests\unit\test_forge_proposal_quality.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge passive
capability catalog coherence analysis slice:

- `python -m pytest tests\unit\test_capability_catalog_coherence.py tests\unit\test_capability_catalog_projection.py tests\unit\test_capability_marketplace.py -q`
  Result: `4 passed`
- `python -m mypy src\francis\economy\markets\capability_catalog_coherence.py`
  Result: `passed`
- `python -m ruff check src\francis\economy\markets\capability_catalog_coherence.py tests\unit\test_capability_catalog_coherence.py`
  Result: `passed`
- `python -m ruff format --check src\francis\economy\markets\capability_catalog_coherence.py tests\unit\test_capability_catalog_coherence.py`
  Result: `2 files already formatted`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge plugin-catalog to
Capability Economy projection slice:

- `python -m pytest tests\unit\test_capability_catalog_projection.py tests\unit\test_capability_marketplace.py -q`
  Result: `2 passed`
- `python -m pytest tests\unit\test_imports.py -q`
  Result: `17 passed, 1 skipped`
- `python -m mypy src\francis\economy\markets\capability_catalog_projection.py src\francis\economy\markets\capability_marketplace.py`
  Result: `passed`
- `python -m ruff check src\francis\economy\markets\capability_catalog_projection.py src\francis\economy\markets\__init__.py src\francis\economy\__init__.py tests\unit\test_capability_catalog_projection.py`
  Result: `passed`
- `python -m ruff format --check src\francis\economy\markets\capability_catalog_projection.py src\francis\economy\markets\__init__.py src\francis\economy\__init__.py tests\unit\test_capability_catalog_projection.py`
  Result: `4 files already formatted`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge passive
capability catalog economy model slice:

- `python -m pytest tests\unit\test_capability_marketplace.py -q`
  Result: `1 passed`
- `python -m pytest tests\unit\test_imports.py -q`
  Result: `17 passed, 1 skipped`
- `python -m mypy src\francis\economy\markets\capability_marketplace.py`
  Result: `passed`
- `python -m ruff check src\francis\economy\markets\capability_marketplace.py tests\unit\test_capability_marketplace.py`
  Result: `passed`
- `python -m ruff format --check src\francis\economy\markets\capability_marketplace.py tests\unit\test_capability_marketplace.py`
  Result: `2 files already formatted` (`.ruff_cache` write warning only)
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge generated
artifact staged-lifecycle contract slice:

- `python -m pytest tests\unit\test_plugin_factory_spec_builder.py -q`
  Result: `1 passed`
- `python -m pytest tests\test_api_plugins.py::test_plugins_build_lifecycle_and_run tests\unit\test_plugin_system_contracts.py -q`
  Result: `7 passed`
- `python -m ruff check src\francis\plugin_factory\spec_builder.py tests\unit\test_plugin_factory_spec_builder.py`
  Result: `passed`
- `python -m ruff format --check src\francis\plugin_factory\spec_builder.py tests\unit\test_plugin_factory_spec_builder.py`
  Result: `2 files already formatted`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge capability catalog
summary and lineage readback slice:

- `python -m pytest tests\unit\test_plugin_system_contracts.py -q`
  Result: `6 passed`
- `python -m pytest tests\test_api_plugins.py::test_plugins_build_lifecycle_and_run tests\test_api_plugins.py::test_plugins_tools_catalog_and_action_validation -q`
  Result: `2 passed`
- `python -m ruff check src\francis\plugin_system\registry.py tests\unit\test_plugin_system_contracts.py`
  Result: `passed`
- `python -m ruff format --check src\francis\plugin_system\registry.py tests\unit\test_plugin_system_contracts.py`
  Result: `2 files already formatted`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge proposal and
proposal-review chat UI readback slice:

- `cd apps\chat_ui && npm run test`
  Result: `74 passed`
- `cd apps\chat_ui && npm run build`
  Result: `passed`
- `python -m pytest tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m ruff check tests\test_api_contract_chat_ui.py`
  Result: `passed` (`.ruff_cache` write warning only)
- `python -m ruff format --check tests\test_api_contract_chat_ui.py`
  Result: `1 file already formatted`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge promotion-readiness
chat UI readback slice:

- `cd apps\chat_ui && npm run test`
  Result: `73 passed`
- `cd apps\chat_ui && npm run build`
  Result: `passed`
- `python -m pytest tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m ruff check tests\test_api_contract_chat_ui.py`
  Result: `passed`
- `python -m ruff format --check tests\test_api_contract_chat_ui.py`
  Result: `1 file already formatted`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 4/Forge generated-build
proposal, staging, proposal review, review-gated promotion-readiness,
promotion-receipt, and readback boundary:

- `python -m pytest tests\test_api_forge.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_forge.py tests\test_api_plugins.py tests\test_api_plugins_permission_gate.py tests\unit\test_plugin_factory_spec_builder.py -q`
  Result: `passed`
- `python -m mypy src\francis\api\routes\forge.py`
  Result: `passed`
- `python -m ruff check src\francis\api\routes\forge.py tests\test_api_forge.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\forge.py tests\test_api_forge.py`
  Result: `2 files already formatted`
- `git diff --check`
  Result: `passed`
- `python -m pytest tests\test_api_plugins.py::test_staged_plugin_promotion_requires_approved_proposal_review tests\test_api_plugins.py::test_plugins_build_lifecycle_and_run tests\test_api_plugins.py::test_plugins_tools_catalog_and_action_validation tests\test_api_forge.py::test_forge_proposal_and_promotion_readback -q`
  Result: `passed`
- `python -m pytest tests\test_api_plugins.py tests\test_api_forge.py tests\test_api_plugins_permission_gate.py tests\test_api_operations.py tests\test_api_missions.py tests\unit\test_plugin_factory_spec_builder.py -q`
  Result: `passed`
- `python -m ruff check src\francis\api\routes\plugins.py tests\test_api_plugins.py tests\test_api_forge.py tests\test_api_operations.py tests\test_api_missions.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\plugins.py tests\test_api_plugins.py tests\test_api_forge.py tests\test_api_operations.py tests\test_api_missions.py`
  Result: `5 files already formatted`
- `git diff --check`
  Result: `passed`
- `python -m pytest tests\test_api_missions.py::test_mission_linked_plugin_run_surfaces_operation_trace tests\test_api_operations.py::test_operations_plugin_run_action_executes tests\test_api_operations.py::test_operations_run_surfaces_completed_mission_memory_receipt tests\test_api_operations.py::test_operations_tool_run_action_executes -q`
  Result: `4 passed`
- `python -m pytest tests\test_api_forge.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_forge.py tests\test_api_plugins.py tests\test_api_plugins_permission_gate.py tests\unit\test_plugin_factory_spec_builder.py -q`
  Result: `passed`
- `python -m ruff check src\francis\api\routes\forge.py tests\test_api_forge.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\forge.py tests\test_api_forge.py`
  Result: `2 files already formatted`
- `python -m pytest tests\test_api_plugins.py::test_plugins_build_lifecycle_and_run -q`
  Result: `passed`
- `python -m pytest tests\test_api_plugins.py::test_staged_plugin_promotion_requires_forge_readiness tests\test_api_plugins.py::test_plugins_build_lifecycle_and_run tests\test_api_plugins.py::test_plugins_tools_catalog_and_action_validation -q`
  Result: `passed`
- `python -m pytest tests\test_api_forge.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_plugins.py tests\test_api_forge.py tests\test_api_plugins_permission_gate.py tests\unit\test_plugin_factory_spec_builder.py tests\test_api_operations.py::test_operations_plugin_run_action_executes tests\test_api_operations.py::test_operations_run_surfaces_completed_mission_memory_receipt tests\test_api_operations.py::test_operations_tool_run_action_executes tests\test_api_missions.py::test_mission_linked_plugin_run_surfaces_operation_trace -q`
  Result: `passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_operations.py tests\test_api_plugins.py tests\test_api_plugins_permission_gate.py tests\test_api_forge.py tests\unit\test_plugin_factory_spec_builder.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_forge.py tests\test_api_plugins.py tests\test_api_plugins_permission_gate.py tests\unit\test_plugin_factory_spec_builder.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_plugins.py tests\test_api_plugins_permission_gate.py tests\unit\test_plugin_factory_spec_builder.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_operations.py tests\test_api_plugins.py tests\test_api_plugins_permission_gate.py tests\unit\test_plugin_factory_spec_builder.py -q`
  Result: `passed`
- `python -m ruff check src\francis\api\routes\plugins.py tests\test_api_plugins.py tests\test_api_operations.py tests\test_api_missions.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\plugins.py tests\test_api_plugins.py tests\test_api_operations.py tests\test_api_missions.py`
  Result: `4 files already formatted`
- `python -m ruff check src\francis\api\routes\plugins.py tests\test_api_plugins.py`
  Result: `passed`
- `python -m ruff check src\francis\api\routes\forge.py src\francis\api\app.py tests\test_api_forge.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\forge.py src\francis\api\app.py tests\test_api_forge.py`
  Result: `3 files already formatted`
- `python -m ruff check src\francis\api\routes\plugins.py tests\test_api_plugins.py tests\test_api_operations.py tests\test_api_missions.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\plugins.py tests\test_api_plugins.py tests\test_api_operations.py tests\test_api_missions.py`
  Result: `4 files already formatted`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3/Missions closure proof:

- `python -c "... GET /continuity/briefing ..."`
  Result: `D:\Francis\data` initially reported Stage 3 readiness as `review`,
  with `1/5` criteria satisfied.
- `POST /system/operator_mode` with actor `operator.stage3.readiness` and
  `system.write` scope
  Result: control mode changed from Observe to Assist for the bounded proof run.
- `python -m francis stage3-readiness-proof --confirm --actor operator.stage3.readiness`
  Result: `ok: true`, status `ready`, completed mission
  `msn_20260427_133357_b4e13d71`, deadlettered mission
  `msn_20260427_133357_367eab3c`, Stage 3 readiness `5/5`.
- `POST /system/operator_mode` with actor `operator.stage3.readiness` and
  `system.write` scope
  Result: control mode restored to Observe after the proof.
- `python -c "... GET /system/operator_mode and /continuity/briefing ..."`
  Result: control mode `observe`; Stage 3 readiness still `ready`, with `5/5`
  criteria satisfied and no blocked, attention, or review criteria.
- `python -m pytest tests\test_stage3_readiness_proof.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_approvals.py tests\test_api_credentials.py tests\unit\test_governance_redaction.py -q`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `72 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 readiness proof
diagnostic slice:

- `python -m pytest tests\test_stage3_readiness_proof.py -q`
  Result: `3 passed`
- `python -m pytest tests\test_stage3_readiness_proof.py tests\test_api_continuity.py::test_continuity_briefing_reports_ready_stage3_mission_posture -q`
  Result: `4 passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `python -m ruff check src\francis\missions\readiness_proof.py src\francis\__main__.py tests\test_stage3_readiness_proof.py`
  Result: `passed`
- `python -m ruff format --check src\francis\missions\readiness_proof.py src\francis\__main__.py tests\test_stage3_readiness_proof.py`
  Result: `3 files already formatted`
- `python -m francis stage3-readiness-proof`
  Result: refused without `--confirm` and returned `confirmation_required`

Latest targeted validation for the `2026-04-26` Stage 3 mission queue receipt
reachability slice:

- `cd apps\chat_ui; npm run test`
  Result: `66 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 world-state mission
overview loop projection slice:

- `python -m pytest tests\test_api_system_settings.py::test_system_world_state_projects_mission_queue_and_deadletter_preview -q`
  Result: `1 passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\settings\index.test.ts`
  Result: `12 passed`
- `cd apps\chat_ui; npm run test`
  Result: `66 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `python -m ruff check src\francis\world_state\snapshot.py tests\test_api_system_settings.py`
  Result: `passed`
- `python -m ruff format --check src\francis\world_state\snapshot.py tests\test_api_system_settings.py`
  Result: `2 files already formatted`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission queue loop
client contract slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\missions\index.test.ts`
  Result: `15 passed`
- `cd apps\chat_ui; npm run test`
  Result: `66 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission queue loop
projection slice:

- `python -m pytest tests\test_api_missions.py::test_mission_linked_governance_hold_updates_blocked_state -q`
  Result: `1 passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `python -m ruff check src\francis\api\routes\missions.py tests\test_api_missions.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\missions.py tests\test_api_missions.py`
  Result: `2 files already formatted`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` observer scan permission-gate
slice:

- `python -m pytest tests\test_api_system_permission_gate.py -q`
  Result: `2 passed`
- `python -m pytest tests\test_api_system_settings.py::test_system_observer_scan_is_receipted_and_read_paths_remain_passive tests\test_api_continuity.py::test_continuity_briefing_surfaces_handoff_and_recent_completion tests\test_api_system_settings.py::test_system_mutation_context_redacts_secret_text -q`
  Result: `3 passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\settings\index.test.ts`
  Result: `12 passed`
- `python -m ruff check src\francis\api\routes\system.py tests\conftest.py tests\test_api_system_permission_gate.py tests\test_api_system_settings.py tests\test_api_continuity.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\system.py tests\conftest.py tests\test_api_system_permission_gate.py tests\test_api_system_settings.py tests\test_api_continuity.py`
  Result: `5 files already formatted`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_approvals.py tests\test_api_credentials.py tests\unit\test_governance_redaction.py -q`
  Result: `17 passed`
- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 top-level mission
current-task identity slice:

- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py::test_mission_advance_creates_first_operation_with_receipt -q`
  Result: `1 passed`
- `.\.venv\Scripts\python.exe -m ruff check src\francis\api\routes\missions.py tests\test_api_missions.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff format --check src\francis\api\routes\missions.py tests\test_api_missions.py`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 failed terminal receipt
operator-review gate slice:

- `.\.venv\Scripts\python.exe -m pytest tests\test_api_operations.py::test_operations_run_surfaces_failed_mission_memory_receipt tests\test_mission_receipts.py -q`
  Result: `3 passed`
- `.\.venv\Scripts\python.exe -m ruff check src\francis\operations\runtime.py tests\test_api_operations.py tests\test_mission_receipts.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff format --check src\francis\operations\runtime.py tests\test_api_operations.py tests\test_mission_receipts.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_operations.py tests\test_api_memory_timeline.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 failed terminal receipt
handoff slice:

- `.\.venv\Scripts\python.exe -m pytest tests\test_api_operations.py::test_operations_run_surfaces_failed_mission_memory_receipt tests\test_mission_receipts.py -q`
  Result: `3 passed`
- `.\.venv\Scripts\python.exe -m ruff check src\francis\operations\runtime.py tests\test_api_operations.py tests\test_mission_receipts.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff format --check src\francis\operations\runtime.py tests\test_api_operations.py tests\test_mission_receipts.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_operations.py tests\test_mission_receipts.py tests\test_api_memory_timeline.py -q`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m mypy src`
  Result: `Success: no issues found in 475 source files`
- `.\scripts\check.ps1`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 structured explanation
reference readback slice:

- `.\.venv\Scripts\python.exe -m pytest tests\test_api_explanation.py -q`
  Result: `3 passed`
- `.\.venv\Scripts\python.exe -m ruff check src\francis\api\routes\explanation.py tests\test_api_explanation.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff format --check src\francis\api\routes\explanation.py tests\test_api_explanation.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m mypy src`
  Result: `Success: no issues found in 475 source files`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py tests\test_api_explanation.py -q`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 explanation mission-handle interface slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\explanation_evidence\index.test.ts src\explanation_explorer\index.test.ts`
  Result: `6 passed`
- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests/test_api_explanation.py -q`
  Result: `2 passed`

Latest targeted validation for the `2026-04-27` Stage 3 explanation evidence mission-handle interface slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\explanation_evidence\index.test.ts`
  Result: `5 passed`
- `cd apps\chat_ui; npm run test`
  Result: `70 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 explanation explorer loop-alias parser slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\explanation_explorer\index.test.ts`
  Result: `3 passed`
- `cd apps\chat_ui; npm run test`
  Result: `71 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 explanation handle readback and CI Mypy recovery slice:

- `gh run list --branch main --limit 12 --json databaseId,displayTitle,conclusion,status,workflowName,createdAt,headSha,url`
  Result: confirmed the latest 12 main-branch `ci` runs were failing.
- `gh run view 24959187567 --log-failed`
  Result: `Mypy` failed on all matrix jobs with 36 errors in `src/francis/memory/mission_receipts.py` and `src/francis/api/routes/chat.py`.
- `.\.venv\Scripts\python.exe -m ruff format src\francis\memory\mission_receipts.py src\francis\api\routes\chat.py src\francis\api\routes\explanation.py tests\test_api_explanation.py`
  Result: `4 files left unchanged`
- `.\.venv\Scripts\python.exe -m ruff check src\francis\memory\mission_receipts.py src\francis\api\routes\chat.py src\francis\api\routes\explanation.py tests\test_api_explanation.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m mypy src`
  Result: `Success: no issues found in 475 source files`
- `.\.venv\Scripts\python.exe -m pytest tests/test_mission_receipts.py tests/test_api_chat.py tests/test_api_explanation.py -q`
  Result: `7 passed`
- `.\.venv\Scripts\python.exe -m pytest tests/test_api_missions.py tests/test_api_continuity.py tests/test_api_system_settings.py -q`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission recovery handoff rendering slice:

- `cd apps\chat_ui; npm run test`
  Result: `60 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 ORB failed handback focus slice:

- `python -m pytest tests\unit\test_kernel_contracts.py::test_orb_snapshot_handback_uses_failed_preview_as_receipt_focus -q`
  Result: `1 passed`
- `python -m ruff check src\francis\world_state\orb.py tests\unit\test_kernel_contracts.py`
  Result: `passed`
- `python -m ruff format --check src\francis\world_state\orb.py tests\unit\test_kernel_contracts.py`
  Result: `2 files already formatted` (cache warning only: `.ruff_cache` access denied)
- `python -m pytest tests\unit\test_kernel_contracts.py tests\test_api_system_settings.py -q`
  Result: `33 passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 operator-mode handoff focus slice:

- `python -m pytest tests\unit\test_operator_mode.py -q`
  Result: `4 passed`
- `python -m ruff check src\francis\world_state\operator_mode.py tests\unit\test_operator_mode.py`
  Result: `passed`
- `python -m ruff format --check src\francis\world_state\operator_mode.py tests\unit\test_operator_mode.py`
  Result: `2 files already formatted`
- `python -m pytest tests\unit\test_operator_mode.py tests\test_api_system_settings.py -q`
  Result: `28 passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 operator-mode memory receipt pass-through slice:

- `python -m pytest tests\unit\test_operator_mode.py::test_operator_mode_snapshot_preserves_briefing_memory_receipts -q`
  Result: `failed before implementation with KeyError: memory_receipts; passed after the operator-mode readback fix`
- `python -m pytest tests\unit\test_operator_mode.py tests\unit\test_kernel_contracts.py -q`
  Result: `14 passed`
- `python -m ruff check src\francis\world_state\operator_mode.py tests\unit\test_operator_mode.py`
  Result: `passed`
- `python -m ruff format --check src\francis\world_state\operator_mode.py tests\unit\test_operator_mode.py`
  Result: `2 files already formatted`
- `python -m mypy src\francis\world_state\operator_mode.py`
  Result: `passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 ORB memory receipt summary pass-through slice:

- `python -m pytest tests\unit\test_kernel_contracts.py::test_orb_snapshot_handback_preserves_memory_receipt_summary -q`
  Result: `failed before implementation with KeyError: memory_receipt_count; passed after the ORB handback readback fix`
- `python -m pytest tests\unit\test_kernel_contracts.py -q`
  Result: `10 passed`
- `python -m ruff check src\francis\world_state\orb.py tests\unit\test_kernel_contracts.py`
  Result: `passed; Ruff emitted a .ruff_cache access warning`
- `python -m ruff format --check src\francis\world_state\orb.py tests\unit\test_kernel_contracts.py`
  Result: `2 files already formatted`
- `python -m mypy src\francis\world_state\orb.py`
  Result: `passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` direct operation execution permission-gate slice:

- `python -m pytest tests\test_api_operations.py::test_operations_run_denies_unscoped_actor_before_execution tests\test_api_operations.py::test_operations_run_once_denies_unscoped_actor_before_worker_cycle -q`
  Result: `failed before implementation because both routes still executed; passed after the permission-gate integration`
- `python -m pytest tests\test_api_operations.py -q`
  Result: `28 passed`
- `python -m ruff check src\francis\api\routes\operations.py tests\test_api_operations.py tests\conftest.py`
  Result: `passed; Ruff emitted .ruff_cache access warnings`
- `python -m ruff format --check src\francis\api\routes\operations.py tests\test_api_operations.py tests\conftest.py`
  Result: `3 files already formatted`
- `python -m mypy src\francis\api\routes\operations.py`
  Result: `passed`
- `python -m pytest tests\unit\test_api_permission_gate.py tests\test_api_missions_permission_gate.py -q`
  Result: `5 passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` direct operation mutation permission-gate slice:

- `python -m pytest tests\test_api_operations.py::test_operations_create_denies_unscoped_actor_before_mutation tests\test_api_operations.py::test_operations_lifecycle_mutations_deny_unscoped_actor_before_mutation -q`
  Result: `failed before implementation because create, patch, cancel, and delete still mutated; passed after the permission-gate integration`
- `python -m pytest tests\test_api_operations.py -q`
  Result: `30 passed`
- `python -m ruff check src\francis\api\routes\operations.py tests\test_api_operations.py tests\conftest.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\operations.py tests\test_api_operations.py tests\conftest.py`
  Result: `3 files already formatted`
- `python -m mypy src\francis\api\routes\operations.py`
  Result: `passed`
- `python -m pytest tests\unit\test_api_permission_gate.py tests\test_api_missions_permission_gate.py -q`
  Result: `5 passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` chat UI operations permission-denial contract slice:

- `npm run test -- src/operations/index.test.ts`
  Result: `failed before implementation because operation mutation responses dropped the backend governance body; the focused operations-client contract passed after the parser update`
- `node --test --experimental-strip-types src/operations/index.test.ts`
  Result: `9 passed`
- `npm run test`
  Result: `68 passed`
- `npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-27` chat UI operations denial notice slice:

- `npm run test`
  Result: `68 passed`
- `npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 completed mission interface handoff slice:

- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_mission_loop_contract.py tests\test_api_missions.py -q`
  Result: `28 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py tests\test_api_mission_loop_contract.py -q`
  Result: `passed`
- `python -m ruff check src\francis\api\routes\missions.py tests\test_api_mission_loop_contract.py tests\test_api_missions.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\missions.py tests\test_api_mission_loop_contract.py tests\test_api_missions.py`
  Result: `passed; ruff warned it could not write cache files under .ruff_cache due to access denied`

Latest targeted validation for the `2026-04-26` Stage 3 completed mission memory evidence interface handoff slice:

- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_mission_loop_contract.py tests\test_api_memory_timeline.py -q`
  Result: `8 passed`
- `python -m ruff check src\francis\operations\runtime.py tests\test_api_mission_loop_contract.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `python -m ruff format --check src\francis\operations\runtime.py tests\test_api_mission_loop_contract.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py tests\test_mission_receipts.py tests\test_api_memory_timeline.py tests\test_api_mission_loop_contract.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `95 passed`

Latest targeted validation for the `2026-04-26` Stage 3 completed mission briefing handoff projection slice:

- `$env:PYTHONPATH='src'; python -m pytest tests\test_mission_receipts.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `38 passed`
- `python -m ruff check src\francis\memory\mission_receipts.py src\francis\world_state\snapshot.py tests\test_mission_receipts.py tests\test_api_continuity.py tests\test_api_system_settings.py`
  Result: `passed`
- `python -m ruff format --check src\francis\memory\mission_receipts.py src\francis\world_state\snapshot.py tests\test_mission_receipts.py tests\test_api_continuity.py tests\test_api_system_settings.py`
  Result: `passed; ruff warned it could not write cache files under .ruff_cache due to access denied`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py tests\test_mission_receipts.py tests\test_api_memory_timeline.py tests\test_api_mission_loop_contract.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `95 passed`

Latest targeted validation for the `2026-04-26` Stage 3 completed mission receipt client contract slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\missions\index.test.ts src\settings\index.test.ts`
  Result: `26 passed`
- `cd apps\chat_ui; npm run test`
  Result: `60 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 completed mission receipt handoff rendering slice:

- `cd apps\chat_ui; npm run test`
  Result: `60 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 completed mission evidence handoff query slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\memory_evidence\index.test.ts src\explanation_evidence\index.test.ts`
  Result: `10 passed`
- `cd apps\chat_ui; npm run test`
  Result: `62 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission memory plan receipt slice:

- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_memory_timeline.py::test_memory_timeline_finds_completed_mission_operation_receipt -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_mission_receipts.py -q`
  Result: `passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\memory_timeline\index.test.ts`
  Result: `2 passed`
- `python -m ruff check src\francis\operations\runtime.py src\francis\memory\mission_receipts.py src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `python -m ruff format --check src\francis\operations\runtime.py src\francis\memory\mission_receipts.py src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_memory_timeline.py tests\test_api_operations.py tests\test_api_missions.py -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `45 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

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

Latest targeted validation for the `2026-04-26` mission execution permission-gate UI contract slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\missions\index.test.ts`
  Result: `13 passed`
- `cd apps\chat_ui; npm run test`
  Result: `57 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission loop gate trace-handoff slice:

- `.\.venv\Scripts\python.exe -m ruff check src\francis\api\routes\missions.py tests\test_api_mission_loop_contract.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_mission_loop_contract.py -q`
  Result: `2 passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_mission_loop_contract.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission loop UI trace-handoff contract slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src/missions/index.test.ts`
  Result: `14 passed`
- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git -c safe.directory=D:/Francis diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` operation lifecycle posture guard slice:

- `.\.venv\Scripts\python.exe -m pytest tests\test_api_operations.py -q`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff check src\francis\api\routes\operations.py tests\test_api_operations.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff format --check src\francis\api\routes\operations.py tests\test_api_operations.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_operations.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-26` operation lifecycle posture-denial truthfulness slice:

- `.\.venv\Scripts\python.exe -m pytest tests\test_api_operations.py -q`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff check src\francis\api\routes\operations.py tests\test_api_operations.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff format --check src\francis\api\routes\operations.py tests\test_api_operations.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_operations.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git -c safe.directory=D:/Francis diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` mission execution permission-gate slice:

- `python -m ruff check --no-cache src\francis\api\routes\missions.py tests\conftest.py tests\test_api_missions_permission_gate.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\api\routes\missions.py tests\conftest.py tests\test_api_missions_permission_gate.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions_permission_gate.py tests\unit\test_api_permission_gate.py tests\unit\test_scope_checker.py -q`
  Result: `10 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_approvals.py tests\test_api_credentials.py tests\unit\test_governance_redaction.py -q`
  Result: `16 passed`

Latest targeted validation for the `2026-04-26` mission receipt-summary operation identity slice:

- `python -m ruff check src\francis\api\routes\missions.py tests\test_api_missions.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\missions.py tests\test_api_missions.py`
  Result: `passed`
- `python -m mypy src\francis\api\routes\missions.py`
  Result: `passed`
- `python -m pytest tests\test_api_missions.py::test_mission_advance_creates_first_operation_with_receipt tests\test_api_missions.py::test_mission_advance_runs_linked_queued_operation -q`
  Result: `2 passed`
- `python -m pytest tests\test_api_missions.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-26` mission client receipt-summary identity slice:

- `cd apps\chat_ui; npm run test`
  Result: `66 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` mission receipt-summary identity rendering slice:

- `cd apps\chat_ui; npm run test`
  Result: `66 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` world-state receipt-summary identity slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src/settings/index.test.ts`
  Result: `12 passed`
- `cd apps\chat_ui; npm run test`
  Result: `66 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` mission memory receipt plan-readback contract slice:

- `python -m pytest tests\test_mission_receipts.py -q`
  Result: `2 passed`
- `python -m ruff check src\francis\memory\mission_receipts.py tests\test_mission_receipts.py`
  Result: `passed`
- `python -m ruff format --check src\francis\memory\mission_receipts.py tests\test_mission_receipts.py`
  Result: `passed`; Ruff emitted a cache write warning for `.ruff_cache` access denied.
- `python -m pytest tests\test_mission_receipts.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` chat mission ingress first-operation slice:

- `python -m ruff check src\francis\api\routes\chat.py tests\test_api_chat.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\chat.py tests\test_api_chat.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_chat.py tests\test_api_memory_timeline.py::test_memory_timeline_projects_chat_mission_ingress_loop_metadata -q`
  Result: `4 passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\chat\index.test.ts`
  Result: `2 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_chat.py tests\test_api_memory_timeline.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_approvals.py tests\test_api_credentials.py tests\unit\test_governance_redaction.py -q`
  Result: `16 passed`
- `cd apps\chat_ui; npm run test`
  Result: `55 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` chat mission ingress handoff-handle slice:

- `python -m ruff check src\francis\api\routes\chat.py tests\test_api_chat.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\chat.py tests\test_api_chat.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_chat.py -q`
  Result: `5 passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\chat\index.test.ts`
  Result: `2 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `62 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` chat mission ingress permission-gate continuity slice:

- `python -m ruff check src\francis\api\routes\chat.py tests\test_api_chat.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\chat.py tests\test_api_chat.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `python -m mypy src\francis\api\routes\chat.py`
  Result: `passed`
- `python -m pytest tests\test_api_chat.py tests\test_api_memory_timeline.py::test_memory_timeline_projects_chat_mission_ingress_permission_gate -q`
  Result: `6 passed`
- `python -m pytest tests\test_api_chat.py tests\test_api_memory_timeline.py -q`
  Result: `15 passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-26` chat mission ingress posture-gate continuity slice:

- `python -m pytest tests\test_api_chat.py::test_chat_mission_command_respects_observe_mode -q`
  Result: `1 passed`
- `python -m pytest tests\test_api_chat.py -q`
  Result: `5 passed`
- `python -m pytest tests\test_api_memory_timeline.py::test_memory_timeline_projects_chat_mission_ingress_permission_gate -q`
  Result: `1 passed`
- `python -m pytest tests\test_api_memory_timeline.py -q`
  Result: `10 passed`
- `python -m ruff check src\francis\api\routes\chat.py tests\test_api_chat.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\chat.py tests\test_api_chat.py`
  Result: `2 files already formatted`
- `python -m mypy src\francis\api\routes\chat.py`
  Result: `passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` plugin lifecycle permission-gate slice:

- `python -m ruff check src\francis\api\routes\plugins.py tests\conftest.py tests\test_api_plugins.py tests\test_api_plugins_permission_gate.py tests\test_api_operations.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py tests\test_api_approvals.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\plugins.py tests\conftest.py tests\test_api_plugins.py tests\test_api_plugins_permission_gate.py tests\test_api_operations.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py tests\test_api_approvals.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_plugins_permission_gate.py tests\unit\test_api_permission_gate.py tests\unit\test_scope_checker.py -q`
  Result: `9 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_plugins.py tests\test_api_operations.py -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_approvals.py tests\test_api_credentials.py tests\unit\test_governance_redaction.py -q`
  Result: `16 passed`
- `cd apps\chat_ui; npm run test`
  Result: `55 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` system runtime permission-gate slice:

- `python -m ruff check src\francis\api\routes\system.py tests\conftest.py tests\test_api_system_settings.py tests\test_api_system_permission_gate.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\system.py tests\conftest.py tests\test_api_system_settings.py tests\test_api_system_permission_gate.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_system_permission_gate.py tests\unit\test_api_permission_gate.py tests\unit\test_scope_checker.py -q`
  Result: `9 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_approvals.py tests\test_api_credentials.py tests\unit\test_governance_redaction.py -q`
  Result: `16 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_contract_chat_ui.py -q`
  Result: `1 passed`
- `cd apps\chat_ui; npm run test`
  Result: `53 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` credential mutation permission-gate slice:

- `python -m ruff check src\francis\api\routes\credentials.py tests\conftest.py tests\test_api_credentials.py tests\test_api_approvals.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\credentials.py tests\conftest.py tests\test_api_credentials.py tests\test_api_approvals.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_credentials.py tests\unit\test_api_permission_gate.py tests\unit\test_scope_checker.py -q`
  Result: `14 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_approvals.py tests\test_api_credentials.py tests\unit\test_governance_redaction.py -q`
  Result: `16 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_contract_chat_ui.py -q`
  Result: `1 passed`
- `cd apps\chat_ui; npm run test`
  Result: `52 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` trust mutation permission-gate slice:

- `python -m ruff check src\francis\api\routes\trust.py tests\conftest.py tests\test_api_trust.py tests\test_api_approvals.py tests\test_api_continuity.py tests\test_api_missions.py tests\test_api_operations.py tests\test_api_plugins.py tests\test_api_system_settings.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\trust.py tests\conftest.py tests\test_api_trust.py tests\test_api_approvals.py tests\test_api_continuity.py tests\test_api_missions.py tests\test_api_operations.py tests\test_api_plugins.py tests\test_api_system_settings.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_trust.py tests\unit\test_api_permission_gate.py tests\unit\test_scope_checker.py -q`
  Result: `11 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_approvals.py tests\test_api_credentials.py tests\unit\test_governance_redaction.py -q`
  Result: `16 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py tests\test_api_plugins.py -q`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `49 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` approval decision permission-gate slice:

- `python -m ruff check src\francis\api\routes\approvals.py src\francis\governance\approvals.py tests\conftest.py tests\test_api_approvals.py tests\test_api_continuity.py tests\test_api_credentials.py tests\test_api_industrial.py tests\test_api_memory_timeline.py tests\test_api_missions.py tests\test_api_operations.py tests\test_api_plugins.py tests\test_api_system_settings.py tests\test_api_web_learning.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\approvals.py src\francis\governance\approvals.py tests\conftest.py tests\test_api_approvals.py tests\test_api_continuity.py tests\test_api_credentials.py tests\test_api_industrial.py tests\test_api_memory_timeline.py tests\test_api_missions.py tests\test_api_operations.py tests\test_api_plugins.py tests\test_api_system_settings.py tests\test_api_web_learning.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_approvals.py tests\test_api_credentials.py tests\unit\test_governance_redaction.py -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py tests\test_api_plugins.py tests\test_api_industrial.py tests\test_api_web_learning.py tests\test_api_memory_timeline.py -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\unit\test_api_permission_gate.py tests\unit\test_scope_checker.py -q`
  Result: `7 passed`
- `cd apps\chat_ui; npm run test`
  Result: `47 passed`
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

Latest targeted validation for the `2026-04-26` Stage 3 plan revision receipt summary slice:

- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_plan_revision.py -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `python -m ruff check src\francis\agent\executor.py tests\test_api_plan_revision.py`
  Result: `passed`
- `python -m ruff format --check src\francis\agent\executor.py tests\test_api_plan_revision.py`
  Result: `passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\operations\index.test.ts`
  Result: `8 passed`
- `cd apps\chat_ui; npm run test`
  Result: `64 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 operations plan summary CSV export slice:

- `python -m pytest tests\test_api_plan_revision.py::test_plan_revise_result_carries_bounded_plan_summary -q`
  Result: `1 passed`
- `python -m pytest tests\test_api_plan_revision.py -q`
  Result: `1 passed`
- `python -m pytest tests\test_api_operations.py -q`
  Result: `passed`
- `python -m ruff check src\francis\api\routes\operations.py tests\test_api_plan_revision.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\operations.py tests\test_api_plan_revision.py`
  Result: `2 files already formatted`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission interface plan summary readback slice:

- `python -m pytest tests\test_api_mission_loop_contract.py::test_chat_ingress_advances_to_terminal_memory_receipt -q`
  Result: `1 passed`
- `python -m pytest tests\test_api_mission_loop_contract.py -q`
  Result: `2 passed`
- `python -m ruff check src\francis\api\routes\missions.py tests\test_api_mission_loop_contract.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\missions.py tests\test_api_mission_loop_contract.py`
  Result: `2 files already formatted`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `python -m mypy src\francis\api\routes\missions.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission current-task plan summary client slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\missions\index.test.ts`
  Result: `15 passed`
- `cd apps\chat_ui; npm run test`
  Result: `67 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission memory receipt plan summary settings-client slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\settings\index.test.ts`
  Result: `12 passed`
- `cd apps\chat_ui; npm run test`
  Result: `67 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
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

Latest targeted validation for the `2026-04-26` Stage 3 mission current-task identity and failed receipt review-gate slice:

- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py::test_mission_advance_creates_first_operation_with_receipt -q`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_operations.py::test_operations_run_surfaces_failed_mission_memory_receipt tests\test_mission_receipts.py -q`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff check src\francis\api\routes\missions.py src\francis\operations\runtime.py tests\test_api_missions.py tests\test_api_operations.py tests\test_mission_receipts.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff format --check src\francis\api\routes\missions.py src\francis\operations\runtime.py tests\test_api_missions.py tests\test_api_operations.py tests\test_mission_receipts.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission current-task identity interface slice:

- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission current-task identity continuity read-model slice:

- `.\.venv\Scripts\python.exe -m pytest tests\test_api_continuity.py::test_continuity_briefing_surfaces_handoff_and_recent_completion -q`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff check src\francis\world_state\snapshot.py tests\test_api_continuity.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff format --check src\francis\world_state\snapshot.py tests\test_api_continuity.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
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

Latest targeted validation for the `2026-04-26` Stage 3 memory timeline current-task trace-handle slice:

- `python -m ruff check src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_memory_timeline.py::test_memory_timeline_filters_continuity_ledger_by_references -q`
  Result: `passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\memory_timeline\index.test.ts`
  Result: `2 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_memory_timeline.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `62 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 structured memory timeline receipt write slice:

- `.\.venv\Scripts\python.exe -m pytest tests\test_api_memory_timeline.py -q`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff check src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff format --check src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `passed` with non-blocking `.ruff_cache` write warnings
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py tests\test_api_memory_timeline.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 memory timeline CSV loop-handle export slice:

- `python -m pytest tests\test_api_memory_timeline.py::test_memory_timeline_record_preserves_structured_references_and_loop -q`
  Result: `1 passed`
- `python -m pytest tests\test_api_memory_timeline.py tests\test_api_mission_loop_contract.py -q`
  Result: `11 passed`
- `python -m ruff check src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `2 files already formatted`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py tests\test_api_memory_timeline.py tests\test_api_mission_loop_contract.py -q`
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

Latest targeted validation for the `2026-04-26` Stage 3 chat ingress current-task identity memory-loop slice:

- `.\.venv\Scripts\python.exe -m pytest tests\test_api_chat.py tests\test_api_memory_timeline.py tests\test_api_mission_loop_contract.py -q`
  Result: `16 passed`
- `.\.venv\Scripts\python.exe -m ruff check src\francis\api\routes\chat.py src\francis\api\routes\memory_timeline.py tests\test_api_chat.py tests\test_api_memory_timeline.py tests\test_api_mission_loop_contract.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff format --check src\francis\api\routes\chat.py src\francis\api\routes\memory_timeline.py tests\test_api_chat.py tests\test_api_memory_timeline.py tests\test_api_mission_loop_contract.py`
  Result: `passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\memory_timeline\index.test.ts`
  Result: `2 passed`
- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_chat.py tests\test_api_memory_timeline.py tests\test_api_mission_loop_contract.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 chat mission-ingress previous-approval metadata slice:

- `python -m pytest tests\test_api_chat.py::test_chat_mission_ingress_compact_meta_preserves_handoff_trace_handles -q`
  Result: `failed before implementation with KeyError: current_task_previous_approval_id; passed after the compact metadata fix`
- `python -m pytest tests\test_api_chat.py -q`
  Result: `5 passed`
- `python -m ruff check src\francis\api\routes\chat.py tests\test_api_chat.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\chat.py tests\test_api_chat.py`
  Result: `2 files already formatted`
- `python -m mypy src\francis\api\routes\chat.py`
  Result: `passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 settings current-task identity client slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\settings\index.test.ts`
  Result: `12 passed`
- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 missions memory-receipt current-task identity client slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\missions\index.test.ts`
  Result: `14 passed`
- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 operations memory-receipt current-task identity client slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\operations\index.test.ts`
  Result: `8 passed`
- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 operations-client memory receipt previous-approval interface slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\operations\index.test.ts`
  Result: `failed before implementation because operation memory receipt parsing omitted current_task_previous_approval_id; passed after parser fix with 9 tests`
- `cd apps\chat_ui; npm run test`
  Result: `72 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 operations memory-receipt plan-readback client slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\operations\index.test.ts`
  Result: `8 passed`
- `cd apps\chat_ui; npm run test`
  Result: `66 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 terminal plan receipt operation-readback contract slice:

- `python -m pytest tests\test_api_mission_loop_contract.py::test_chat_ingress_advances_to_terminal_memory_receipt -q`
  Result: `passed`
- `python -m ruff check tests\test_api_mission_loop_contract.py`
  Result: `passed`
- `python -m ruff format --check tests\test_api_mission_loop_contract.py`
  Result: `passed`
- `python -m pytest tests\test_api_mission_loop_contract.py tests\test_api_operations.py::test_operations_run_executes_plan_create tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 terminal operation receipt current-task identity backend slice:

- `python -m pytest tests\test_mission_receipts.py tests\test_api_operations.py::test_operations_run_surfaces_completed_mission_memory_receipt tests\test_api_operations.py::test_operations_run_surfaces_failed_mission_memory_receipt tests\test_api_mission_loop_contract.py::test_chat_ingress_advances_to_terminal_memory_receipt -q`
  Result: `5 passed`
- `python -m pytest tests/test_api_mission_runtime_redaction.py::test_mission_advance_redacts_secret_handoff_text tests/test_api_mission_loop_contract.py::test_chat_ingress_advances_to_terminal_memory_receipt -q`
  Result: `2 passed`
- `python -m ruff check src\francis\operations\runtime.py src\francis\missions\runtime.py src\francis\memory\mission_receipts.py tests\test_api_operations.py tests\test_api_mission_loop_contract.py tests\test_mission_receipts.py tests\test_api_mission_runtime_redaction.py`
  Result: `passed` (non-blocking Ruff cache write warnings from local `.ruff_cache` access)
- `python -m ruff format --check src\francis\operations\runtime.py src\francis\missions\runtime.py src\francis\memory\mission_receipts.py tests\test_api_operations.py tests\test_api_mission_loop_contract.py tests\test_mission_receipts.py tests\test_api_mission_runtime_redaction.py`
  Result: `passed`
- `python -m pytest tests/test_api_missions.py tests/test_api_continuity.py tests/test_api_system_settings.py tests/test_api_operations.py tests/test_api_mission_loop_contract.py tests/test_mission_receipts.py -q`
  Result: `passed`
- `python -m pytest -q`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 selected-operation receipt identity interface slice:

- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 explanation current-task receipt identity evidence slice:

- `python -m pytest tests\test_api_explanation.py -q`
  Result: `4 passed`
- `ruff check src\francis\api\routes\explanation.py tests\test_api_explanation.py`
  Result: `passed`
- `ruff format --check src\francis\api\routes\explanation.py tests\test_api_explanation.py`
  Result: `passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\explanation_explorer\index.test.ts`
  Result: `2 passed`
- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 explanation current-task previous-approval evidence slice:

- `python -m pytest tests\test_api_explanation.py::test_explanations_preserve_current_task_receipt_identity -q`
  Result: `failed before implementation, then passed`
- `python -m pytest tests\test_api_explanation.py -q`
  Result: `5 passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py tests\test_api_explanation.py -q`
  Result: `passed`
- `python -m ruff check src\francis\api\routes\explanation.py tests\test_api_explanation.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\explanation.py tests\test_api_explanation.py`
  Result: `2 files already formatted`
- `python -m mypy src\francis\api\routes\explanation.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 approval gate plan-summary readback slice:

- `python -m pytest tests\test_api_approvals.py::test_approval_list_preserves_metadata_only_loop_handles -q`
  Result: `passed`
- `python -m pytest tests\test_api_approvals.py -q`
  Result: `passed`
- `python -m ruff check src\francis\governance\approval_projection.py tests\test_api_approvals.py`
  Result: `passed` (Ruff cache write warned on local `.ruff_cache` access)
- `python -m ruff format --check src\francis\governance\approval_projection.py tests\test_api_approvals.py`
  Result: `passed` (Ruff cache write warned on local `.ruff_cache` access)
- `cd apps\chat_ui; node --test --experimental-strip-types src\index.test.ts`
  Result: `3 passed`
- `cd apps\chat_ui; npm run test`
  Result: `67 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `python -m mypy src`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 approval queue previous-approval lineage slice:

- `python -m pytest tests\test_api_approvals.py::test_approval_list_preserves_metadata_only_loop_handles -q`
  Result: `failed before implementation with KeyError: current_task_previous_approval_id; passed after the readback fix`
- `python -m pytest tests\test_api_approvals.py -q`
  Result: `8 passed`
- `python -m pytest tests\test_api_approvals.py tests\test_api_credentials.py tests\unit\test_governance_redaction.py -q`
  Result: `17 passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `python -m ruff check src\francis\governance\approval_projection.py tests\test_api_approvals.py`
  Result: `passed`
- `python -m ruff format --check src\francis\governance\approval_projection.py tests\test_api_approvals.py`
  Result: `2 files already formatted`
- `python -m mypy src\francis\governance\approval_projection.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 approval queue previous-approval interface slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\index.test.ts`
  Result: `failed before implementation with undefined current_task_previous_approval_id; passed after the parser fix`
- `cd apps\chat_ui; npm run test`
  Result: `72 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 world-state pending approval previous-approval interface slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\settings\index.test.ts`
  Result: `failed before implementation because pending approval overview parsing omitted current_task_previous_approval_id; passed after parser fix with 12 tests`
- `cd apps\chat_ui; npm run test`
  Result: `72 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 world-state approval gate plan-summary evidence slice:

- `python -m pytest tests\test_api_system_settings.py::test_system_world_state_surfaces_exact_pending_approval_for_blocked_mission -q`
  Result: `passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\settings\index.test.ts`
  Result: `12 passed`
- `python -m pytest tests\test_api_system_settings.py -q`
  Result: `passed`
- `python -m ruff check src\francis\world_state\snapshot.py tests\test_api_system_settings.py`
  Result: `passed`
- `python -m ruff format --check src\francis\world_state\snapshot.py tests\test_api_system_settings.py`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `67 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `python -m mypy src`
  Result: `passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_approvals.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 approval gate plan-summary interface slice:

- `cd apps\chat_ui; npm run test`
  Result: `67 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 operation memory receipt handle normalization slice:

- `python -m pytest tests\test_api_operations.py::test_operations_run_surfaces_completed_mission_memory_receipt tests\test_api_operations.py::test_operations_run_surfaces_failed_mission_memory_receipt tests\test_api_mission_loop_contract.py::test_chat_ingress_advances_to_terminal_memory_receipt -q`
  Result: `3 passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `python -m ruff check src\francis\operations\runtime.py tests\test_api_operations.py`
  Result: `passed`
- `python -m ruff format --check src\francis\operations\runtime.py tests\test_api_operations.py`
  Result: `2 files already formatted`
- `python -m mypy src`
  Result: `passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\operations\index.test.ts`
  Result: `8 passed`
- `cd apps\chat_ui; npm run test`
  Result: `67 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 memory timeline mission-handle fallback slice:

- `python -m pytest tests\test_api_memory_timeline.py::test_memory_timeline_filters_continuity_loop_handle_fallbacks -q`
  Result: `passed`
- `python -m pytest tests\test_api_memory_timeline.py -q`
  Result: `10 passed`
- `python -m ruff check src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `2 files already formatted`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 memory timeline previous-approval lineage slice:

- `python -m pytest tests\test_api_memory_timeline.py::test_memory_timeline_filters_continuity_loop_handle_fallbacks -q`
  Result: `failed before implementation with KeyError: current_task_previous_approval_id; passed after the readback/export fix`
- `python -m pytest tests\test_api_memory_timeline.py -q`
  Result: `10 passed`
- `python -m ruff check src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `2 files already formatted`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 memory timeline previous-approval interface slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\memory_timeline\index.test.ts`
  Result: `failed before implementation because loop readbacks omitted current_task_previous_approval_id/current_task_previous_approval_status; passed after parser fix with 2 tests`
- `cd apps\chat_ui; npm run test`
  Result: `72 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 memory evidence mission-handle interface slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\memory_evidence\index.test.ts`
  Result: `8 passed`
- `cd apps\chat_ui; npm run test`
  Result: `69 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 executor mission-alias sync slice:

- `python -m pytest tests\unit\test_executor_audit_references.py::test_executor_syncs_mission_transition_from_loop_mission_alias -q`
  Result: `passed`
- `python -m pytest tests\unit\test_executor_audit_references.py tests\unit\test_delegation_audit.py -q`
  Result: `3 passed`
- `python -m ruff check src\francis\agent\delegation.py src\francis\agent\executor.py tests\unit\test_executor_audit_references.py tests\unit\test_delegation_audit.py`
  Result: `passed`
- `python -m ruff format --check src\francis\agent\delegation.py src\francis\agent\executor.py tests\unit\test_executor_audit_references.py tests\unit\test_delegation_audit.py`
  Result: `4 files already formatted` (Ruff cache write warned on local `.ruff_cache` access)
- `python -m pytest tests\unit\test_daemon_runner.py tests\unit\test_workers_runner.py -q`
  Result: `4 passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `python -m mypy src`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 mission tick nested-approval receipt slice:

- `python -m pytest tests\test_mission_store.py::test_tick_mission_promotes_nested_receipt_approval_context -q`
  Result: `failed before implementation, then passed`
- `python -m pytest tests\test_mission_store.py -q`
  Result: `7 passed`
- `python -m ruff check src\francis\missions\store.py tests\test_mission_store.py`
  Result: `passed`
- `python -m ruff format --check src\francis\missions\store.py tests\test_mission_store.py`
  Result: `2 files already formatted`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `python -m mypy src`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 mission runtime nested-approval receipt slice:

- `python -m pytest tests\test_mission_runtime.py -q`
  Result: `failed before implementation, then passed`
- `python -m pytest tests\test_api_mission_runtime_redaction.py tests\test_mission_runtime.py -q`
  Result: `3 passed`
- `python -m ruff check src\francis\missions\runtime.py tests\test_mission_runtime.py`
  Result: `passed`
- `python -m ruff format --check src\francis\missions\runtime.py tests\test_mission_runtime.py`
  Result: `2 files already formatted`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `python -m mypy src\francis\missions\runtime.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 mission current-task approval-lineage readback slice:

- `python -m pytest tests\test_api_mission_current_task.py -q`
  Result: `failed before implementation, then passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_mission_current_task.py -q`
  Result: `passed`
- `python -m ruff check src\francis\api\routes\missions.py tests\test_api_mission_current_task.py`
  Result: `passed` (Ruff cache write warned on local `.ruff_cache` access)
- `python -m ruff format --check src\francis\api\routes\missions.py tests\test_api_mission_current_task.py`
  Result: `2 files already formatted`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `python -m mypy src\francis\api\routes\missions.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 continuity current-task approval-lineage readback slice:

- `python -m pytest tests\test_api_continuity.py::test_continuity_briefing_deadletter_preview_preserves_pending_approval_linkage -q`
  Result: `failed before implementation, then passed`
- `python -m pytest tests\test_api_continuity.py -q`
  Result: `12 passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `python -m ruff check src\francis\world_state\snapshot.py tests\test_api_continuity.py`
  Result: `passed`
- `python -m ruff format --check src\francis\world_state\snapshot.py tests\test_api_continuity.py`
  Result: `2 files already formatted`
- `python -m mypy src\francis\world_state\snapshot.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 approval queue task identity readback slice:

- `python -m pytest tests\unit\test_approval_projection.py tests\test_api_approvals.py::test_approval_list_surfaces_linked_operation_gate_handles tests\test_api_approvals.py::test_approval_list_preserves_metadata_only_loop_handles -q`
  Result: `4 passed`
- `ruff check src\francis\governance\approval_projection.py tests\unit\test_approval_projection.py tests\test_api_approvals.py`
  Result: `passed`
- `ruff format --check src\francis\governance\approval_projection.py tests\unit\test_approval_projection.py tests\test_api_approvals.py`
  Result: `passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\index.test.ts`
  Result: `3 passed`
- `python -m pytest tests\test_api_approvals.py tests\test_api_credentials.py tests\unit\test_governance_redaction.py -q`
  Result: `17 passed`
- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `cd apps\chat_ui; npm run build`
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

Latest targeted validation for the `2026-04-26` Stage 3 world-state approval task identity evidence slice:

- `python -m pytest tests\test_api_system_settings.py::test_system_world_state_surfaces_exact_pending_approval_for_blocked_mission -q`
  Result: `passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\settings\index.test.ts`
  Result: `12 passed`
- `ruff check src\francis\world_state\snapshot.py tests\test_api_system_settings.py`
  Result: `passed`
- `ruff format --check src\francis\world_state\snapshot.py tests\test_api_system_settings.py`
  Result: `passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` settings mission receipt approval-handle parser slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\settings\index.test.ts`
  Result: `12 passed`
- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` missions client receipt approval-handle parser slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\missions\index.test.ts`
  Result: `14 passed`
- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` terminal mission receipt approval-handoff slice:

- `python -m ruff check src\francis\api\routes\missions.py tests\test_api_missions.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\missions.py tests\test_api_missions.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests/test_api_missions.py::test_mission_linked_supervised_exec_surfaces_artifact_handle -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests/test_api_missions.py tests/test_api_continuity.py tests/test_api_system_settings.py`
  Result: `63 passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` memory evidence approval-handle lookup slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\memory_evidence\index.test.ts`
  Result: `7 passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\memory_timeline\index.test.ts`
  Result: `2 passed`
- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` memory timeline approval-filter slice:

- `python -m ruff check src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_memory_timeline.py`
  Result: `7 passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\memory_timeline\index.test.ts`
  Result: `2 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `64 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` memory timeline loop-handle filter slice:

- `python -m pytest tests\test_api_memory_timeline.py::test_memory_timeline_filters_continuity_loop_handle_fallbacks -q`
  Result: `1 passed`
- `python -m pytest tests\test_api_memory_timeline.py -q`
  Result: `8 passed`
- `ruff check src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `ruff format --check src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `2 files already formatted`
- `python -m pytest tests\test_api_mission_loop_contract.py -q`
  Result: `1 passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-26` selected memory evidence loop-handle display slice:

- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` terminal mission receipt current-task trace slice:

- `python -m ruff check src\francis\operations\runtime.py src\francis\memory\mission_receipts.py tests\test_mission_receipts.py tests\test_api_operations.py`
  Result: `passed`
- `python -m ruff format --check src\francis\operations\runtime.py src\francis\memory\mission_receipts.py tests\test_mission_receipts.py tests\test_api_operations.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_mission_receipts.py tests\test_api_operations.py::test_operations_run_surfaces_completed_mission_memory_receipt -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py tests\test_mission_receipts.py`
  Result: `25 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py`
  Result: `63 passed`

Latest targeted validation for the `2026-04-26` Stage 3 executor audit approval-handle slice:

- `$env:PYTHONPATH='src'; python -m pytest tests\unit\test_executor_audit_references.py -q`
  Result: `1 passed`
- `$env:PYTHONPATH='src'; python -m ruff check src\francis\agent\executor.py tests\unit\test_executor_audit_references.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m ruff format --check src\francis\agent\executor.py tests\unit\test_executor_audit_references.py`
  Result: `2 files already formatted`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py -q`
  Result: `23 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 operation audit approval projection slice:

- `$env:PYTHONPATH='src'; python -m pytest tests\unit\test_operation_log_projection.py -q`
  Result: `1 passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\operations\index.test.ts`
  Result: `8 passed`
- `$env:PYTHONPATH='src'; python -m ruff check src\francis\api\routes\operations.py tests\unit\test_operation_log_projection.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m ruff format --check src\francis\api\routes\operations.py tests\unit\test_operation_log_projection.py`
  Result: `2 files already formatted`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py -q`
  Result: `23 passed`
- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 world-state latest-activity approval slice:

- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_system_settings.py::test_system_world_state_surfaces_exact_pending_approval_for_blocked_mission -q`
  Result: `1 passed`
- `$env:PYTHONPATH='src'; python -m ruff check src\francis\world_state\snapshot.py tests\test_api_system_settings.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m ruff format --check src\francis\world_state\snapshot.py tests\test_api_system_settings.py`
  Result: `2 files already formatted`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-26` supervised-exec CLI summary handle slice:

- `python -m ruff check src\francis\__main__.py tests\unit\test_cli_supervised_exec_summary.py`
  Result: `passed`
- `python -m ruff format --check src\francis\__main__.py tests\unit\test_cli_supervised_exec_summary.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\unit\test_cli_supervised_exec_summary.py tests\test_api_supervised_exec.py`
  Result: `5 passed`

Latest targeted validation for the `2026-04-26` Stage 3 approval gate loop-handle projection slice:

- `python -m ruff check src\francis\governance\approval_projection.py tests\test_api_approvals.py`
  Result: `passed`
- `python -m ruff format --check src\francis\governance\approval_projection.py tests\test_api_approvals.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_approvals.py -q`
  Result: `8 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_approvals.py tests\test_api_credentials.py tests\unit\test_governance_redaction.py -q`
  Result: `17 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\index.test.ts`
  Result: `3 passed`
- `cd apps\chat_ui; npm run test`
  Result: `64 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 approval decision loop-handle readback slice:

- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_approvals.py::test_approval_list_surfaces_linked_operation_gate_handles -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_approvals.py tests\test_api_credentials.py tests\unit\test_governance_redaction.py -q`
  Result: `17 passed`
- `python -m ruff check tests\test_api_approvals.py`
  Result: `passed`
- `python -m ruff format --check tests\test_api_approvals.py`
  Result: `1 file already formatted`
- `cd apps\chat_ui; node --test --experimental-strip-types src\index.test.ts`
  Result: `3 passed`
- `cd apps\chat_ui; npm run test`
  Result: `66 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
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

Latest targeted validation for the `2026-04-26` Stage 3 operations approval receipt filter slice:

- `.\.venv\Scripts\python.exe -m pytest tests\test_api_operations.py::test_operations_list_get_and_export_preserve_metadata_only_trace_handles -q`
  Result: `1 passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\operations\index.test.ts`
  Result: `8 passed`
- `.\.venv\Scripts\python.exe -m ruff check --no-cache src\francis\api\routes\operations.py tests\test_api_operations.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff format --check --no-cache src\francis\api\routes\operations.py tests\test_api_operations.py`
  Result: `2 files already formatted`
- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_operations.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 operations mission-link readback slice:

- `python -m pytest tests\test_api_operations.py::test_operations_list_get_and_export_preserve_metadata_only_trace_handles -q`
  Result: `1 passed`
- `python -m pytest tests\test_api_operations.py tests\test_api_mission_loop_contract.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py tests\test_api_operations.py tests\test_api_mission_loop_contract.py -q`
  Result: `passed`
- `python -m ruff check src\francis\api\routes\operations.py tests\test_api_operations.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\operations.py tests\test_api_operations.py`
  Result: `2 files already formatted`
- `git diff --check`
  Result: `passed`

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

Latest targeted validation for the `2026-04-26` Stage 3 explanation metadata run-handle slice:

- `python -m ruff check src\francis\api\routes\explanation.py tests\test_api_explanation.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\explanation.py tests\test_api_explanation.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_explanation.py -q`
  Result: `2 passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\explanation_explorer\index.test.ts`
  Result: `2 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_explanation.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `62 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 explanation recovery-context readback slice:

- `python -m pytest tests\test_api_explanation.py -q`
  Result: `passed`
- `python -m ruff check src\francis\api\routes\explanation.py tests\test_api_explanation.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\explanation.py tests\test_api_explanation.py`
  Result: `2 files already formatted`
- `cd apps\chat_ui; node --test --experimental-strip-types src\explanation_explorer\index.test.ts`
  Result: `2 passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `66 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 explanation plan-summary readback slice:

- `python -m pytest tests\test_api_explanation.py::test_explanations_preserve_current_task_receipt_identity -q`
  Result: `passed`
- `python -m pytest tests\test_api_explanation.py -q`
  Result: `5 passed`
- `python -m ruff check src\francis\api\routes\explanation.py tests\test_api_explanation.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\explanation.py tests\test_api_explanation.py`
  Result: `2 files already formatted`
- `cd apps\chat_ui; node --test --experimental-strip-types src\explanation_explorer\index.test.ts`
  Result: `2 passed`
- `cd apps\chat_ui; npm run test`
  Result: `67 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 explanation metadata approval-handle slice:

- `.\.venv\Scripts\python.exe -m pytest tests\test_api_explanation.py -q`
  Result: `2 passed`
- `.\.venv\Scripts\python.exe -m ruff check --no-cache src\francis\api\routes\explanation.py tests\test_api_explanation.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m ruff format --check --no-cache src\francis\api\routes\explanation.py tests\test_api_explanation.py`
  Result: `2 files already formatted`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_explanation.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `65 passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\explanation_explorer\index.test.ts`
  Result: `2 passed`
- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 explanation handoff receipt readback slice:

- `python -m pytest tests\test_api_explanation.py::test_explanations_promote_handoff_receipt_references -q`
  Result: `1 passed`
- `python -m pytest tests\test_api_explanation.py -q`
  Result: `5 passed`
- `python -m ruff check src\francis\api\routes\explanation.py tests\test_api_explanation.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\explanation.py tests\test_api_explanation.py`
  Result: `2 files already formatted`
- `git diff --check`
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

Latest targeted validation for the `2026-04-26` Stage 3 explanation evidence approval-handle query slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\explanation_evidence\index.test.ts`
  Result: `4 passed`
- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_api_explanation.py -q`
  Result: `passed`
- `git diff --check`
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

Latest targeted validation for the `2026-04-26` Stage 3 artifact-origin receipt readback slice:

- `python -m pytest tests\test_api_artifacts.py -q`
  Result: `5 passed`
- `python -m ruff check src\francis\api\routes\artifacts.py tests\test_api_artifacts.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\artifacts.py tests\test_api_artifacts.py`
  Result: `2 files already formatted`
- `cd apps\chat_ui; node --test --experimental-strip-types src\artifacts\index.test.ts`
  Result: `4 passed`
- `python -m pytest tests\test_api_artifacts.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `66 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 artifact-origin current-task approval-lineage slice:

- `python -m pytest tests\test_api_artifacts.py::test_artifact_inspect_projects_originating_receipt -q`
  Result: `failed before implementation, then passed`
- `python -m pytest tests\test_api_artifacts.py -q`
  Result: `5 passed`
- `python -m pytest tests\test_api_artifacts.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `python -m ruff check src\francis\api\routes\artifacts.py tests\test_api_artifacts.py`
  Result: `passed` (Ruff cache write warned on local `.ruff_cache` access)
- `python -m ruff format --check src\francis\api\routes\artifacts.py tests\test_api_artifacts.py`
  Result: `2 files already formatted`
- `python -m mypy src\francis\api\routes\artifacts.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 artifact-origin loop-handle normalization slice:

- `python -m pytest tests\test_api_artifacts.py::test_artifact_inspect_projects_loop_only_originating_receipt_handles -q`
  Result: `failed before implementation with KeyError: mission_id; passed after the readback fix`
- `python -m pytest tests\test_api_artifacts.py -q`
  Result: `6 passed`
- `python -m pytest tests\test_api_artifacts.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `python -m ruff check src\francis\api\routes\artifacts.py tests\test_api_artifacts.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\artifacts.py tests\test_api_artifacts.py`
  Result: `2 files already formatted`
- `cd apps\chat_ui; node --test --experimental-strip-types src\artifacts\index.test.ts`
  Result: `6 passed`
- `cd apps\chat_ui; npm run test`
  Result: `72 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 artifact-origin trace rendering slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\artifacts\index.test.ts`
  Result: `5 passed`
- `cd apps\chat_ui; npm run test`
  Result: `67 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `python -m pytest tests\test_api_artifacts.py -q`
  Result: `5 passed`
- `$npxDir = Get-ChildItem "$env:LOCALAPPDATA\npm-cache\_npx" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1; $env:NODE_PATH = Join-Path $npxDir.FullName "node_modules"; npx --yes --package @playwright/test playwright test --config data\test_runs\playwright\artifact-origin.config.cjs`
  Result: `1 passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 artifact-origin plan-summary readback slice:

- `python -m pytest tests\test_api_artifacts.py::test_artifact_inspect_projects_originating_receipt -q`
  Result: `1 passed`
- `python -m mypy src`
  Result: `passed`
- `python -m pytest tests\test_api_artifacts.py -q`
  Result: `5 passed`
- `python -m ruff check src\francis\api\routes\artifacts.py tests\test_api_artifacts.py`
  Result: `passed` (Ruff cache write warned with access denied; check completed successfully)
- `python -m ruff format --check src\francis\api\routes\artifacts.py tests\test_api_artifacts.py`
  Result: `2 files already formatted`
- `cd apps\chat_ui; node --test --experimental-strip-types src\artifacts\index.test.ts`
  Result: `5 passed`
- `cd apps\chat_ui; npm run test`
  Result: `67 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 artifact-origin receipt handoff context slice:

- `python -m pytest tests/test_api_artifacts.py -q`
  Result: `5 passed`
- `python -m ruff check --no-cache src/francis/api/routes/artifacts.py tests/test_api_artifacts.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src/francis/api/routes/artifacts.py tests/test_api_artifacts.py`
  Result: `2 files already formatted`
- `cd apps\chat_ui; node --test --experimental-strip-types src\artifacts\index.test.ts`
  Result: `4 passed`
- `python -m pytest tests/test_api_artifacts.py tests/test_api_missions.py tests/test_api_continuity.py tests/test_api_system_settings.py -q`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `66 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

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

Latest targeted validation for the `2026-04-26` Stage 3 direct mission create permission-gate slice:

- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions_permission_gate.py -q`
  Result: `5 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py tests\test_api_memory_timeline.py tests\test_api_approvals.py -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_approvals.py tests\test_api_credentials.py tests\unit\test_governance_redaction.py -q`
  Result: `16 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\unit\test_api_permission_gate.py tests\unit\test_scope_checker.py -q`
  Result: `7 passed`
- `$env:PYTHONPATH='src'; python -m ruff check src\francis\api\routes\missions.py tests\conftest.py tests\test_api_missions_permission_gate.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m ruff format --check src\francis\api\routes\missions.py tests\conftest.py tests\test_api_missions_permission_gate.py`
  Result: `passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\missions\index.test.ts`
  Result: `13 passed`
- `cd apps\chat_ui; npm run test`
  Result: `58 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission lifecycle permission-gate slice:

- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions_permission_gate.py -q`
  Result: `4 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_chat.py -q`
  Result: `4 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_approvals.py tests\test_api_credentials.py tests\unit\test_governance_redaction.py -q`
  Result: `16 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\unit\test_api_permission_gate.py tests\unit\test_scope_checker.py -q`
  Result: `7 passed`
- `$env:PYTHONPATH='src'; python -m ruff check src\francis\api\routes\missions.py tests\conftest.py tests\test_api_missions_permission_gate.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m ruff format --check src\francis\api\routes\missions.py tests\conftest.py tests\test_api_missions_permission_gate.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 chat mission ingress permission-gate slice:

- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_chat.py tests\test_api_missions_permission_gate.py -q`
  Result: `7 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_approvals.py tests\test_api_credentials.py tests\unit\test_governance_redaction.py -q`
  Result: `16 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\unit\test_api_permission_gate.py tests\unit\test_scope_checker.py -q`
  Result: `7 passed`
- `$env:PYTHONPATH='src'; python -m ruff check src\francis\api\routes\chat.py tests\conftest.py tests\test_api_chat.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m ruff format --check src\francis\api\routes\chat.py tests\conftest.py tests\test_api_chat.py`
  Result: `passed`
- `cd apps\chat_ui; npm run test -- src/chat/index.test.ts`
  Result: `58 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed` (Git emitted a line-ending warning only)

Latest targeted validation for the `2026-04-26` Stage 3 operation detail memory receipt reachability slice:

- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py::test_operations_run_surfaces_completed_mission_memory_receipt tests\test_mission_receipts.py -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py tests\test_api_memory_timeline.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m ruff check src\francis\memory\mission_receipts.py src\francis\operations\runtime.py src\francis\api\routes\operations.py tests\test_mission_receipts.py tests\test_api_operations.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m ruff format --check src\francis\memory\mission_receipts.py src\francis\operations\runtime.py src\francis\api\routes\operations.py tests\test_mission_receipts.py tests\test_api_operations.py`
  Result: `passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\operations\index.test.ts`
  Result: `6 passed`
- `cd apps\chat_ui; npm run test`
  Result: `59 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed` (Git emitted a line-ending warning only)

Latest targeted validation for the `2026-04-26` Stage 3 operation metadata receipt-handle reachability slice:

- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `python -m ruff check src\francis\api\routes\operations.py src\francis\operations\runtime.py tests\test_api_operations.py`
  Result: `passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\operations\index.test.ts`
  Result: `7 passed`
- `cd apps\chat_ui; npm run test`
  Result: `63 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 operation memory receipt interface reachability slice:

- `cd apps\chat_ui; npm run test`
  Result: `59 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 failed operation memory receipt recovery context slice:

- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py::test_operations_run_surfaces_failed_mission_memory_receipt tests\test_mission_receipts.py -q`
  Result: `3 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py tests\test_api_memory_timeline.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m ruff check src\francis\operations\runtime.py src\francis\memory\mission_receipts.py src\francis\api\routes\memory_timeline.py tests\test_api_operations.py tests\test_mission_receipts.py`
  Result: `passed`
- `$env:PYTHONPATH='src'; python -m ruff format --check src\francis\operations\runtime.py src\francis\memory\mission_receipts.py src\francis\api\routes\memory_timeline.py tests\test_api_operations.py tests\test_mission_receipts.py`
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

Latest targeted validation for the `2026-04-26` Stage 3 terminal receipt memory evidence interface slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\memory_evidence\index.test.ts`
  Result: `5 passed`
- `cd apps\chat_ui; npm run test`
  Result: `58 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 terminal receipt memory evidence browser-proof slice:

- `npx --yes --package @playwright/test playwright install chromium`
  Result: `passed`
- `npx --yes --package @playwright/test playwright test --config data\test_runs\playwright\playwright.config.ts`
  Result: `1 passed`
- `cd apps\chat_ui; npm run test`
  Result: `58 passed`
- `cd apps\chat_ui; npm run build`
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

- `python -m pytest tests\test_api_memory_timeline.py::test_memory_timeline_filters_continuity_loop_handle_fallbacks -q`
  Result: `1 passed`
- `python -m pytest tests\test_api_memory_timeline.py -q`
  Result: `10 passed`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `python -m ruff check src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\memory_timeline.py tests\test_api_memory_timeline.py`
  Result: `2 files already formatted`

Earlier validation for this surface:

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

Latest targeted validation for the `2026-04-26` Stage 3 mission memory receipt handoff-reference fallback slice:

- `python -m pytest tests\test_mission_receipts.py::test_mission_operation_receipts_promote_handoff_reference_fallbacks -q`
  Result: `1 passed`
- `python -m pytest tests\test_mission_receipts.py -q`
  Result: `3 passed`
- `python -m ruff check src\francis\memory\mission_receipts.py tests\test_mission_receipts.py`
  Result: `passed`
- `python -m ruff format --check src\francis\memory\mission_receipts.py tests\test_mission_receipts.py`
  Result: `2 files already formatted`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 continuity memory receipt handle evidence slice:

- `python -m pytest tests\test_api_continuity.py::test_continuity_briefing_reports_ready_stage3_mission_posture -q`
  Result: `1 passed`
- `python -m pytest tests\test_api_continuity.py -q`
  Result: `12 passed`
- `python -m ruff check src\francis\world_state\snapshot.py tests\test_api_continuity.py`
  Result: `passed`
- `python -m ruff format --check src\francis\world_state\snapshot.py tests\test_api_continuity.py`
  Result: `2 files already formatted`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 mission memory receipt current-task approval-lineage slice:

- `python -m pytest tests\test_mission_receipts.py::test_mission_operation_receipts_preserve_structured_references -q`
  Result: `failed before implementation with KeyError: current_task_previous_approval_id; passed after the readback fix`
- `python -m pytest tests\test_mission_receipts.py -q`
  Result: `3 passed`
- `python -m ruff check src\francis\memory\mission_receipts.py tests\test_mission_receipts.py`
  Result: `passed`
- `python -m ruff format --check src\francis\memory\mission_receipts.py tests\test_mission_receipts.py`
  Result: `2 files already formatted`
- `python -m mypy src\francis\memory\mission_receipts.py`
  Result: `passed`
- `python -m pytest tests\test_mission_receipts.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Stage 3 missions-client memory receipt previous-approval interface slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\missions\index.test.ts`
  Result: `failed before implementation because mission memory receipt parsing omitted current_task_previous_approval_id; passed after parser fix with 15 tests`
- `cd apps\chat_ui; npm run test`
  Result: `72 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

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

Latest targeted validation for the `2026-04-26` Stage 3 mission memory receipt approval-gate readback slice:

- `python -m pytest tests\test_mission_receipts.py -q`
  Result: `2 passed`
- `python -m pytest tests\test_api_memory_timeline.py tests\test_api_mission_loop_contract.py -q`
  Result: `8 passed`
- `ruff check src\francis\memory\mission_receipts.py tests\test_mission_receipts.py`
  Result: `passed`
- `ruff format --check src\francis\memory\mission_receipts.py tests\test_mission_receipts.py`
  Result: `2 files already formatted`
- `python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission memory receipt gate parser slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\missions\index.test.ts`
  Result: `14 passed`
- `cd apps\chat_ui; node --test --experimental-strip-types src\settings\index.test.ts`
  Result: `12 passed`
- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `cd apps\chat_ui; npx tsc --noEmit`
  Result: `failed on existing broad strict TypeScript errors across unrelated UI modules; not used as the targeted gate`

Latest targeted validation for the `2026-04-26` Stage 3 direct mission advance handoff redaction slice:

- `.\.venv\Scripts\python.exe -m ruff format src\francis\missions\runtime.py tests\test_api_mission_runtime_redaction.py`
  Result: `2 files left unchanged`
- `.\.venv\Scripts\python.exe -m ruff check src\francis\missions\runtime.py tests\test_api_mission_runtime_redaction.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests/test_api_mission_runtime_redaction.py -q`
  Result: `2 passed`
- `.\.venv\Scripts\python.exe -m ruff check src\francis\missions\runtime.py tests\test_api_mission_runtime_redaction.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests/test_api_missions.py tests/test_api_continuity.py tests/test_api_system_settings.py tests/test_api_mission_runtime_redaction.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 mission queue-run handoff redaction slice:

- `.\.venv\Scripts\python.exe -m ruff format src\francis\missions\runtime.py tests\test_api_mission_runtime_redaction.py`
  Result: `1 file reformatted, 1 file left unchanged`
- `.\.venv\Scripts\python.exe -m ruff check src\francis\missions\runtime.py tests\test_api_mission_runtime_redaction.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests/test_api_mission_runtime_redaction.py -q`
  Result: `1 passed`
- `.\.venv\Scripts\python.exe -m ruff check src\francis\missions\runtime.py tests\test_api_mission_runtime_redaction.py tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests/test_api_missions.py tests/test_api_continuity.py tests/test_api_system_settings.py tests/test_api_mission_runtime_redaction.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 direct mission continuity redaction slice:

- `python -m ruff format src\francis\missions\store.py tests\test_api_missions.py`
  Result: `2 files left unchanged`
- `python -m ruff check src\francis\missions\store.py tests\test_api_missions.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests/test_api_missions.py::test_mission_create_and_update_redact_continuity_text -q`
  Result: `1 passed`
- `.\.venv\Scripts\python.exe -m pytest tests/test_api_missions.py tests/test_api_continuity.py tests/test_api_system_settings.py -q`
  Result: `64 passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 terminal mission receipt operator-review gate slice:

- `.\.venv\Scripts\python.exe -m pytest tests/test_api_missions.py::test_mission_linked_operation_run_updates_history_and_status tests/test_api_system_settings.py::test_system_world_state_projects_mission_briefing_and_advance_receipts -q`
  Result: `2 passed`
- `.\.venv\Scripts\python.exe -m ruff format --no-cache src\francis\operations\runtime.py src\francis\api\routes\missions.py src\francis\world_state\snapshot.py tests\test_api_missions.py tests\test_api_system_settings.py`
  Result: `5 files left unchanged`
- `.\.venv\Scripts\python.exe -m ruff check --no-cache src\francis\operations\runtime.py src\francis\api\routes\missions.py src\francis\world_state\snapshot.py tests\test_api_missions.py tests\test_api_system_settings.py`
  Result: `passed`
- `.\.venv\Scripts\python.exe -m pytest tests/test_api_missions.py tests/test_api_continuity.py tests/test_api_system_settings.py -q`
  Result: `63 passed`
- `.\.venv\Scripts\python.exe -m pytest tests/test_api_operations.py::test_operations_run_surfaces_completed_mission_memory_receipt -q`
  Result: `1 passed`
- `.\.venv\Scripts\python.exe -m pytest tests/test_api_operations.py -q`
  Result: `23 passed`

Latest targeted validation for the `2026-04-26` Stage 3 approved execution receipt-handle continuity slice:

- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py::test_operations_approved_mission_run_receipt_preserves_approval_posture tests\test_api_operations.py::test_operations_approved_supervised_exec_preserves_receipt_handles -q`
  Result: `2 passed`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_operations.py -q`
  Result: `26 passed`
- `python -m ruff check --no-cache tests\test_api_operations.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_api_operations.py`
  Result: `1 file already formatted`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_api_missions.py tests\test_api_continuity.py tests\test_api_system_settings.py -q`
  Result: `64 passed`

Latest targeted validation for the `2026-04-26` Stage 3 operations memory receipt handoff-handle client slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\operations\index.test.ts`
  Result: `8 passed`
- `cd apps\chat_ui; npm run test`
  Result: `66 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 selected operation receipt handoff interface slice:

- `cd apps\chat_ui; npm run test`
  Result: `66 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-26` Stage 3 completed handoff evidence handle priority slice:

- `cd apps\chat_ui; node --test --experimental-strip-types src\memory_evidence\index.test.ts src\explanation_evidence\index.test.ts`
  Result: `11 passed`
- `cd apps\chat_ui; npm run test`
  Result: `65 passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

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

Latest targeted validation for the `2026-04-27` Stage 4/Forge completion audit
and staging-quality gate slice:

- `python -m pytest tests\test_api_plugins.py::test_plugins_build_requires_forge_staging_quality tests\test_api_plugins.py::test_staged_plugin_promotion_requires_approved_proposal_review tests\test_api_plugins.py::test_plugins_build_lifecycle_and_run -q`
  Result: `passed`
- `python -m pytest tests\test_api_plugins.py tests\test_api_forge.py tests\test_api_plugins_permission_gate.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_contract_chat_ui.py tests\unit\test_capability_catalog_projection.py tests\unit\test_capability_catalog_coherence.py tests\unit\test_capability_marketplace.py tests\unit\test_forge_proposal_quality.py tests\unit\test_forge_proposal_quality_summary.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_operations.py::test_operations_plugin_run_action_executes tests\test_api_operations.py::test_operations_tool_run_action_executes tests\test_api_missions.py::test_mission_linked_plugin_run_surfaces_operation_trace -q`
  Result: `passed`
- `python -m ruff check src\francis\api\routes\plugins.py tests\test_api_plugins.py`
  Result: `passed`
- `python -m ruff format --check src\francis\api\routes\plugins.py tests\test_api_plugins.py`
  Result: `passed`
- `cd apps\chat_ui && npm run test`
  Result: `78 passed`
- `cd apps\chat_ui && npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-27` Reactor operation dispatch engine
slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_dispatch_engine_runs_existing_operation_with_receipts tests\unit\test_reactor_event_queue.py::test_reactor_dispatch_engine_blocks_operation_run_without_operations_scope tests\test_api_reactor.py::test_reactor_operation_dispatch_route_runs_existing_operation -q`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor operation failure
retry/deadletter routing slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_failed_operation_dispatch_schedules_retry_then_deadletters -q`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor\events.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor\events.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m mypy src\francis\reactor\events.py src\francis\reactor\dispatch.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor successful due-retry
proof/readback slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_due_retry_dispatch_can_return_to_successful_stable_state -q`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor deadletter disposition
receipt slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_deadletter_resolution_records_receipt_without_recovery -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py::test_reactor_deadletter_resolve_route_records_escalation_pending_without_execution -q`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor\deadletters.py src\francis\reactor\events.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed after removing one unused local variable`
- `python -m ruff format --check src\francis\reactor\deadletters.py src\francis\reactor\events.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed after formatting the two new tests`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor review-route filter UI
readback slice:

- `cd apps\chat_ui; npm run test`
  Result: `passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor deadletter queue UI
readback slice:

- `cd apps\chat_ui; npm run test`
  Result: `passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor escalation handoff
receipt slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_deadletter_escalation_handoff_records_receipt_without_execution tests\test_api_reactor.py::test_reactor_deadletter_resolve_route_records_escalation_pending_without_execution -q`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed after formatting tests\unit\test_reactor_event_queue.py`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor escalation handoff UI
readback slice:

- `cd apps\chat_ui; npm run test`
  Result: `passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor escalation
acknowledgement receipt slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_deadletter_escalation_handoff_records_receipt_without_execution tests\test_api_reactor.py::test_reactor_deadletter_resolve_route_records_escalation_pending_without_execution -q`
  Result: `passed`
- `python -m ruff format src\francis\reactor\deadletters.py src\francis\reactor\events.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `2 files reformatted, 4 files left unchanged`
- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed after formatting`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor escalation
acknowledgement UI readback slice:

- `cd apps\chat_ui; npm run test`
  Result: `passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor recovery request
handoff slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_deadletter_escalation_handoff_records_receipt_without_execution tests\test_api_reactor.py::test_reactor_deadletter_resolve_route_records_escalation_pending_without_execution -q`
  Result: `passed after moving the API test operation setup into the focused test`
- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed after formatting tests\unit\test_reactor_event_queue.py and tests\test_api_reactor.py`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor recovery event
dispatch proof slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_deadletter_escalation_handoff_records_receipt_without_execution -q`
  Result: `failed before assertion correction, then passed`
- `python -m pytest tests\test_api_reactor.py::test_reactor_deadletter_resolve_route_records_escalation_pending_without_execution -q`
  Result: `failed before assertion correction, then passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor recovery dispatch
settlement slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_deadletter_escalation_handoff_records_receipt_without_execution -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py::test_reactor_deadletter_resolve_route_records_escalation_pending_without_execution -q`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff format src\francis\reactor\deadletters.py src\francis\reactor\events.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `3 files reformatted, 1 file left unchanged`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor recovery settlement UI
readback slice:

- `cd apps\chat_ui; npm run test`
  Result: `passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor mission tick dispatch
slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_dispatch_engine_runs_mission_tick_with_receipts tests\unit\test_reactor_event_queue.py::test_reactor_dispatch_engine_blocks_mission_tick_without_missions_scope tests\test_api_reactor.py::test_reactor_mission_tick_dispatch_route_runs_bounded_queue -q`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_failed_mission_tick_dispatch_schedules_retry -q`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed after formatting src\francis\reactor\dispatch.py`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor mission tick retry
exhaustion deadletter proof slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_failed_mission_tick_dispatch_schedules_retry_then_deadletters tests\test_api_reactor.py::test_reactor_mission_tick_retry_exhaustion_route_queues_deadletter -q`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed with Ruff cache write warnings only`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor external escalation
attempt receipt slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_deadletter_escalation_handoff_records_receipt_without_execution -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py::test_reactor_deadletter_resolve_route_records_escalation_pending_without_execution -q`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m mypy src\francis\reactor src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `.\scripts\check.ps1`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor local outbox external
delivery queue slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_external_escalation_attempt_records_adapter_preflight_without_delivery -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py::test_reactor_deadletter_external_delivery_route_queues_local_outbox_without_send -q`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor\deadletters.py src\francis\reactor\events.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor\deadletters.py src\francis\reactor\events.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `failed before formatting src\francis\reactor\events.py and tests\unit\test_reactor_event_queue.py; passed after formatting`
- `python -m mypy src\francis\reactor\deadletters.py src\francis\reactor\events.py src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor local outbox delivery
artifact readback slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_external_escalation_attempt_records_adapter_preflight_without_delivery -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py::test_reactor_deadletter_external_delivery_route_queues_local_outbox_without_send -q`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor\deadletters.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor\deadletters.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `failed before formatting tests\unit\test_reactor_event_queue.py with Ruff cache write warnings; passed after formatting`
- `python -m mypy src\francis\reactor\deadletters.py src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor local outbox delivery
processor readiness readback slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_external_escalation_attempt_records_adapter_preflight_without_delivery -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py::test_reactor_deadletter_external_delivery_route_queues_local_outbox_without_send -q`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor\deadletters.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor\deadletters.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `failed before formatting tests\unit\test_reactor_event_queue.py with Ruff cache write warnings; passed after formatting`
- `python -m mypy src\francis\reactor\deadletters.py src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor local outbox processor
handoff receipt slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_external_escalation_attempt_records_adapter_preflight_without_delivery tests\test_api_reactor.py::test_reactor_deadletter_external_delivery_route_queues_local_outbox_without_send -q`
  Result: `failed before adding the processor-handoff review-route projection; passed after updating the projection`
- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_external_escalation_attempt_records_adapter_preflight_without_delivery tests\test_api_reactor.py::test_reactor_deadletter_external_delivery_route_queues_local_outbox_without_send -q`
  Result: `passed after adding deadletter-history readback assertions`
- `python -m pytest tests\test_api_reactor.py tests\unit\test_reactor_event_queue.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor\deadletters.py src\francis\reactor\events.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor\deadletters.py src\francis\reactor\events.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `failed before formatting src\francis\reactor\events.py, tests\test_api_reactor.py, and tests\unit\test_reactor_event_queue.py; passed after formatting`
- `python -m mypy src\francis\reactor\deadletters.py src\francis\reactor\events.py src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor local outbox processor
completion receipt slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_external_escalation_attempt_records_adapter_preflight_without_delivery tests\test_api_reactor.py::test_reactor_deadletter_external_delivery_route_queues_local_outbox_without_send -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py tests\unit\test_reactor_event_queue.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor\deadletters.py src\francis\reactor\events.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor\deadletters.py src\francis\reactor\events.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `failed before formatting tests\unit\test_reactor_event_queue.py; passed after formatting`
- `python -m mypy src\francis\reactor\deadletters.py src\francis\reactor\events.py src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor deadletter history
readback slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_deadletter_resolution_records_receipt_without_recovery -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py::test_reactor_deadletter_resolve_route_records_escalation_pending_without_execution -q`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor\deadletters.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor\deadletters.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `failed before formatting src\francis\reactor\deadletters.py and tests\test_api_reactor.py; passed after formatting`
- `python -m mypy src\francis\reactor\deadletters.py src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor recovery receipt
readback slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_deadletter_escalation_handoff_records_receipt_without_execution -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py::test_reactor_deadletter_resolve_route_records_escalation_pending_without_execution -q`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor\deadletters.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor\deadletters.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed with Ruff cache write warnings`
- `python -m mypy src\francis\reactor\deadletters.py src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor proposal-review
history readback slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_proposal_review_history_readback_is_read_only -q`
  Result: `failed before correcting the test proposal fixture to include validation path and known limits; passed after fixture correction`
- `python -m pytest tests\test_api_reactor.py::test_reactor_proposal_review_dispatch_reads_forge_quality_without_authority -q`
  Result: `passed`
- `python -m pytest tests\unit\test_reactor_event_queue.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor\events.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor\events.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed with Ruff cache write warnings`
- `python -m mypy src\francis\reactor\events.py src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor operator visibility
summary readback slice:

- `python -m pytest tests\unit\test_reactor_operator_visibility.py tests\test_api_reactor_visibility.py -q`
  Result: `failed before aligning approval-state assertions to the existing awaiting_approval contract; passed after correction`
- `python -m pytest tests\unit\test_reactor_event_queue.py tests\unit\test_reactor_operator_visibility.py tests\test_api_reactor.py tests\test_api_reactor_visibility.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor\visibility.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_operator_visibility.py tests\test_api_reactor_visibility.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor\visibility.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_operator_visibility.py tests\test_api_reactor_visibility.py`
  Result: `failed before formatting src\francis\reactor\visibility.py, tests\unit\test_reactor_operator_visibility.py, and tests\test_api_reactor_visibility.py; passed after formatting`
- `python -m mypy src\francis\reactor\visibility.py src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor operator visibility UI
readback slice:

- `cd apps\chat_ui; npm run test`
  Result: `passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor classification dispatch
slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_dispatch_engine_classifies_telemetry_without_execution tests\unit\test_reactor_event_queue.py::test_reactor_dispatch_attempt_records_receipt_without_execution tests\test_api_reactor.py::test_reactor_classification_dispatch_records_read_only_receipts tests\test_api_reactor.py::test_reactor_event_routes_enqueue_and_readback -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py tests\unit\test_reactor_event_queue.py tests\unit\test_reactor_operator_visibility.py tests\test_api_reactor_visibility.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor\dispatch.py tests\test_api_reactor.py tests\unit\test_reactor_event_queue.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor\dispatch.py tests\test_api_reactor.py tests\unit\test_reactor_event_queue.py`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor approval-decision
resume dispatch slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_dispatch_engine_records_approval_resume_without_execution tests\test_api_reactor.py::test_reactor_approval_decision_event_records_resume_receipt_without_execution -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py tests\unit\test_reactor_event_queue.py tests\unit\test_reactor_operator_visibility.py tests\test_api_reactor_visibility.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor\dispatch.py tests\test_api_reactor.py tests\unit\test_reactor_event_queue.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor\dispatch.py tests\test_api_reactor.py tests\unit\test_reactor_event_queue.py`
  Result: `passed`
- `python -m mypy src\francis\reactor\dispatch.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor rejected approval
decision API proof slice:

- `python -m pytest tests\test_api_reactor.py::test_reactor_dispatch_attempt_keeps_rejected_decision_in_operator_review -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py::test_reactor_dispatch_attempt_reconciles_approved_decision tests\test_api_reactor.py::test_reactor_dispatch_attempt_keeps_rejected_decision_in_operator_review tests\test_api_reactor.py::test_reactor_approval_decision_event_records_resume_receipt_without_execution tests\unit\test_reactor_event_queue.py::test_reactor_dispatch_attempt_blocks_rejected_approval_without_execution -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py tests\unit\test_reactor_event_queue.py tests\unit\test_reactor_operator_visibility.py tests\test_api_reactor_visibility.py -q`
  Result: `passed`
- `python -m ruff check tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check tests\test_api_reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor approval-resume history
readback slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_dispatch_engine_records_approval_resume_without_execution tests\test_api_reactor.py::test_reactor_approval_decision_event_records_resume_receipt_without_execution -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py tests\unit\test_reactor_event_queue.py tests\unit\test_reactor_operator_visibility.py tests\test_api_reactor_visibility.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor\events.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\test_api_reactor.py tests\unit\test_reactor_event_queue.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor\events.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\test_api_reactor.py tests\unit\test_reactor_event_queue.py`
  Result: `failed before formatting src\francis\reactor\events.py; passed after formatting`
- `python -m mypy src\francis\reactor\events.py src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor mission tick
permission-denial API proof slice:

- `python -m pytest tests\test_api_reactor.py::test_reactor_mission_tick_dispatch_route_blocks_without_missions_scope -q`
  Result: `failed before correcting the expected verification route to match
  the existing operator-review contract; passed after test correction`
- `python -m pytest tests\test_api_reactor.py::test_reactor_mission_tick_dispatch_route_blocks_without_missions_scope tests\test_api_reactor.py::test_reactor_mission_tick_dispatch_route_runs_bounded_queue tests\unit\test_reactor_event_queue.py::test_reactor_dispatch_engine_blocks_mission_tick_without_missions_scope tests\unit\test_reactor_event_queue.py::test_reactor_dispatch_engine_runs_mission_tick_with_receipts -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor_visibility.py tests\unit\test_reactor_operator_visibility.py -q`
  Result: `passed`
- `python -m ruff check tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check tests\test_api_reactor.py`
  Result: `passed with Ruff cache write warning`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor external delivery
sender-boundary slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_external_delivery_sender_preflight_requires_explicit_sender tests\unit\test_reactor_event_queue.py::test_reactor_external_escalation_attempt_records_adapter_preflight_without_delivery tests\test_api_reactor.py::test_reactor_deadletter_external_delivery_route_queues_local_outbox_without_send -q`
  Result: `passed before formatting and passed after formatting`
- `python -m pytest tests\test_api_reactor.py tests\unit\test_reactor_event_queue.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor\external_escalation.py src\francis\reactor\deadletters.py src\francis\reactor\events.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format src\francis\reactor\external_escalation.py src\francis\reactor\deadletters.py src\francis\reactor\events.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `formatted touched files before final format check`
- `python -m ruff format --check src\francis\reactor\external_escalation.py src\francis\reactor\deadletters.py src\francis\reactor\events.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m mypy src\francis\reactor\external_escalation.py src\francis\reactor\deadletters.py src\francis\reactor\events.py src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor external delivery
sender-readiness readback slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_external_escalation_attempt_records_adapter_preflight_without_delivery tests\test_api_reactor.py::test_reactor_deadletter_external_delivery_route_queues_local_outbox_without_send -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor.py tests\unit\test_reactor_event_queue.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor\deadletters.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor\deadletters.py src\francis\reactor\__init__.py src\francis\api\routes\reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m mypy src\francis\reactor\deadletters.py src\francis\api\routes\reactor.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor sender-readiness UI
readback slice:

- `cd apps\chat_ui; npm run test`
  Result: `passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

Stage 5/Reactor checkpoint audit as of `2026-04-28`: Stage 5 remains active and
is not ready to close. The current repo truth proves bounded event intake,
dispatch-attempt receipts, approval/deadletter/retry readbacks, governed
`operation_run` dispatch, governed `mission_tick` dispatch, read-only Forge
proposal review, read-only telemetry/observer classification, read-only
approval-decision resume receipts, local outbox external-escalation queueing,
processor handoff/completion, blocked sender-attempt receipt/readback, and chat
UI sender-readiness readback. The audit did not add execution, approval,
memory-write, promotion, external-delivery, or external-escalation authority.
Stage 5 is still blocked from closure by broader dispatch action coverage,
broader failure-routing/deadletter proof beyond the currently covered
`operation_run` and `mission_tick` paths, broader operator UI visibility beyond
the current read-only Reactor surfaces, and real external escalation
send/execution beyond the current non-sending local outbox and blocked sender
boundary.

Latest checkpoint validation for the `2026-04-28` Stage 5/Reactor audit:

- `python -m pytest tests\test_api_reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor_visibility.py tests\unit\test_reactor_operator_visibility.py tests\unit\test_reactor_visibility.py -q`
  Result: `passed`

Latest targeted validation for the `2026-04-28` Reactor plugin-run boundary
slice:

- `python -m pytest tests\unit\test_reactor_event_queue.py::test_reactor_dispatch_engine_blocks_plugin_run_boundary_without_execution tests\test_api_reactor.py::test_reactor_plugin_run_dispatch_route_blocks_without_execution -q`
  Result: `failed before aligning review-queue receipt-kind assertions with the
  existing blocker projection contract; passed after correction`
- `python -m pytest tests\test_api_reactor.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor_visibility.py tests\unit\test_reactor_operator_visibility.py tests\unit\test_reactor_visibility.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor\dispatch.py src\francis\reactor\events.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor\dispatch.py src\francis\reactor\events.py tests\unit\test_reactor_event_queue.py tests\test_api_reactor.py`
  Result: `passed`
- `python -m mypy src\francis\reactor\dispatch.py src\francis\reactor\events.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

As of `2026-04-28`, the Reactor backend operator visibility summary also
surfaces the dispatch engine's supported and boundary action contract. The
read-only `/reactor/operator_visibility/summary` response now mirrors
`/reactor/status` dispatch-engine state, exposes supported and boundary action
lists/counts, includes the `plugin_run` boundary in summary counts, and proves a
blocked `plugin_run` review item remains visible without plugin execution. The
summary governance explicitly keeps `plugin_run_authority` false. This is
backend readback only: it does not run plugins, implement plugin dispatch,
decide approvals, schedule retries, enqueue deadletters, send externally, write
memory, promote capabilities, or add UI claims.

Latest targeted validation for the `2026-04-28` Reactor boundary visibility
summary slice:

- `python -m pytest tests\unit\test_reactor_operator_visibility.py::test_reactor_operator_visibility_summary_aggregates_readbacks_without_authority tests\test_api_reactor_visibility.py::test_reactor_operator_visibility_summary_route_is_read_only -q`
  Result: `passed`
- `python -m pytest tests\test_api_reactor_visibility.py tests\unit\test_reactor_operator_visibility.py tests\unit\test_reactor_visibility.py -q`
  Result: `passed`
- `python -m ruff check src\francis\reactor\visibility.py tests\unit\test_reactor_operator_visibility.py tests\test_api_reactor_visibility.py tests\unit\test_reactor_visibility.py`
  Result: `passed`
- `python -m ruff format --check src\francis\reactor\visibility.py tests\unit\test_reactor_operator_visibility.py tests\test_api_reactor_visibility.py tests\unit\test_reactor_visibility.py`
  Result: `failed before formatting tests\test_api_reactor_visibility.py;
  passed after formatting`
- `python -m mypy src\francis\reactor\visibility.py`
  Result: `passed`

## 5. Known truthful gaps

These remain true and should block any "finished" claim:

- the operator experience is not yet a complete ORB console in `P1_INTERFACE`
- the full plan -> gate -> execute -> trace -> memory loop is not yet clearly
  exposed end-to-end in the chat UI
- memory and continuity are materially present but still partial as operator-facing,
  retrieval-backed systems
- evidence, simulation, and federation remain downstream/gated work, not current
  product-ready surfaces
- Stage 5/Reactor currently has trigger intake, readback, dispatch-attempt
  receipts, blocked-dispatch blocker records, and deadletter-candidate,
  retry-candidate, retry-exhausted, and review-filter readback plus a read-only
  review-queue projection with chat UI readback only. Reactor dispatch attempts
  can create a pending approval request when missing, reconcile terminal
  approval decisions back into deferred dispatch or operator-review-blocked
  state, persist real Reactor deadletter queue items with bounded review
  receipts, record verification-state and stable-return receipts, persist retry
  schedule queue items, mark retry schedules due, and feed one bounded retry
  dispatch-attempt receipt. Reactor now has a partial dispatch engine for
  existing `operation_run` events guarded by the existing `operations.run` scope
  and operator posture, with execution, verification, stable-return, and status
  readback. It also supports one bounded `mission_tick` dispatch through the
  existing mission queue runtime guarded by `missions.write` and operator
  posture, with execution, verification, stable-return, status readback,
  unit/API permission-denial proof, failure retry scheduling, and retry-exhaustion
  deadletter proof through a `mission_tick_failed` gate. Failed `operation_run`
  dispatches can now schedule bounded retries and deadletter after retry
  exhaustion through the same governed retry handoff path, and successful due
  retry can settle back into operation success readback without active
  retry/deadletter review leftovers. Deadletter items can now record bounded
  resolved/no-action or escalation-pending
  disposition receipts without starting recovery, retry, execution, memory
  writes, approval decisions, or external escalation, and escalation-pending
  deadletters can now record a durable non-executing escalation handoff receipt,
  acknowledgement receipt, a non-executing external escalation attempt receipt,
  and recovery request receipt that queues a separate `deadletter_recovery`
  `operation_run` event for the same source operation id without dispatching it.
  The external escalation attempt receipt records channel/target/adapter intent,
  adapter preflight state including unsupported `not_configured` adapters and
  configured `local_outbox` readiness, no-delivery/no-execution flags,
  receipt-kind filtering, review-queue readback, and status counts without
  granting external escalation or delivery authority. Preflight-ready
  `local_outbox` attempts can now queue one durable local outbox artifact with
  an external-delivery receipt, receipt-kind/review-route filters, review-queue
  projection, direct artifact list/get readback, processor-readiness readback,
  explicit local processor-handoff receipt/readback, deadletter-history linkage,
  explicit local processor-completion receipt/readback, local processor output
  artifact persistence, explicit blocked sender-attempt receipt/readback after
  processor completion, direct sender-readiness readback, and status counts
  while still sending no external message, starting no external delivery, and
  granting no external-delivery or external-escalation authority. Queued
  `deadletter_recovery` events
  now have focused unit and API proof that explicit dispatch attempts run
  through the existing `operation_run` engine and `operations.run` scope with
  execution, verification, stable-return, and readback receipts, and successful
  recovery dispatches now settle the original `recovery_requested` deadletter
  into `recovery_dispatched` with a dedicated recovery-dispatch receipt and
  parent-event readback. Direct deadletter history readback now derives
  chronological receipt history for one deadletter from the durable item and
  stored receipt arrays with receipt-kind and route filters. Direct recovery
  receipt readback now exposes recovery-request and recovery-dispatch receipts
  through list/get routes with status, deadletter, event, recovery-event, and
  route filters while preserving source governance as read-only evidence.
  Chat UI Reactor readback now preserves recovery-request
  and recovery-dispatch filters, badges, and latest receipt handles from the
  existing read routes, and the System/ORB panel now exposes read-only
  proposal-review execution receipts from Reactor event history for completed
  Forge proposal inspections. Direct proposal-review history readback now
  projects completed `forge_proposal` Reactor inspections through a dedicated
  list route with proposal, plugin, quality-ready, and review-status filters.
  Backend operator visibility summary now aggregates status, review queue,
  retry/deadletter, recovery receipt, proposal-review history, external
  delivery/readiness, and stable route-link readbacks through
  `/reactor/operator_visibility/summary` without new authority, and the chat UI
  System/ORB panel now renders that summary as read-only operator visibility.
  Read-only classification dispatch now covers `telemetry_event` and
  `observer_anomaly` triggers with receipts and stable-return proof, and
  approval-decision Reactor events can now record read-only resume receipts
  without dispatching the target event, with direct route-filtered
  approval-resume history readback. Reactor also has an explicit no-execution
  plugin-run dispatch boundary with operator-review readback, so plugin-run
  attempts are blocked by typed receipt instead of generic not-implemented
  deferment. Remaining Stage 5 gaps still include broader dispatch action
  coverage beyond existing
  operation runs, bounded mission queue ticks, read-only Forge proposal reviews,
  read-only telemetry/observer classification, read-only approval-decision
  resume receipts, and the blocked plugin-run boundary; broader
  execution-failure routing/deadletter proof beyond the currently tested
  `operation_run` and `mission_tick` dispatch-engine paths, broader operator UI
  visibility beyond the current read-only Reactor summary, route-filtered review
  queue, deadletter queue, recovery receipt, and proposal-review readbacks,
  and actual external escalation send/execution beyond the current non-sending
  local outbox queue, artifact readback, processor-readiness readback, local
  processor-handoff/completion receipt readback, and blocked sender-attempt
  receipt/readback plus sender-readiness readback

## 6. Update rule

Update this ledger only when at least one of the following is true:

- a validated surface materially changed
- a plane posture changed in a way that is now directly inspectable
- a major blocker was removed
- the latest evidence set changed and should replace stale validation claims
