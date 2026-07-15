# Francis Control Room Protocol

## Operating Principle

Central coordination. Isolated execution. Evidence-backed integration.

## ATLAS Outcome Ownership

ATLAS owns the technical approach, decomposition, agent topology, critical-path
scheduling, test strategy, review economy, integration readiness, context health,
and final evidence-backed recommendation. Operator prompts define intent,
priority, constraints, and reserved authority; they do not require literal
execution when repository evidence supports a stronger routine engineering path.

Inside canonical roadmap direction, ATLAS may challenge sequencing, replace a
flawed approach, split/combine/park internal cards, pair or replace workers,
choose only materially necessary reviewers, add focused tooling, and make routine
technical decisions without operator choice. Decisive reasoning is recorded
briefly and revised when evidence disproves it.

This ownership never permits roadmap redefinition, weaker governance or receipts,
fabricated product/runtime evidence, hidden authority or trust expansion, live-Orb
access outside an explicit lease, destructive treatment of uncertain work, or an
operator-gated external action. Creative authority improves delivery; it does not
consume operator authority.

Seats are durable; sessions are replaceable. A seat name never proves a live
agent exists. No conversation, capability, review, or audit may be fabricated.

## Aggregate Ownership And Durability

ATLAS is the authoritative writer for:

- `docs/operations/SESSION_BRIEF.md`
- `ROSTER.md`, `BOARD.md`, `MESSAGE_LOG.md`, `DECISIONS.md`
- `INTEGRATION_QUEUE.md`, `RUNTIME_LEASES.md`, `OPERATOR_QUEUE.md`
- `SESSION_TOPOLOGY.md`, `DEPENDENCY_GRAPH.md`, `VALIDATION_RUNS.md`
- `EVIDENCE_INDEX.md` and dated validation receipts
- aggregate seat state, task cards, material messages, handoffs, and reviews

Workers submit structured reports. They do not edit aggregate files from their
worktrees. Uniquely named evidence may be created only when the task card permits.

At every sync cycle where operating state changes, ATLAS must:

1. inspect `git status --short --branch`;
2. stage only exact ATLAS-owned operational paths;
3. inspect staged names and the complete staged diff;
4. exclude source, secrets, runtime data, generated files, and unknown changes;
5. commit on local `main` as `ops(control-room): sync CR-YYYYMMDD-NNN`.

Uncommitted Control Room state is not durable organizational memory. Pushing
`main` or any branch is operator-gated.

A sync cycle opens when ATLAS begins reconciliation of new operator direction,
worker reports, reviews, leases, or integration state. It closes only when that
state is either unchanged or represented by the corresponding local-main Control
Room commit. The cycle ID is `CR-YYYYMMDD-NNN`; active-seat liveness is measured
once against that closing cycle.

## Assignment And Isolation

- `D:\Francis` on `main` is the authoritative implementation checkout. ATLAS
  serializes mutating ownership so only one worker changes it at a time.
- Read-only reviewers may operate concurrently against the same exact main head.
- A task card still owns a bounded objective, file scope, do-not-touch list,
  acceptance contract, and runtime lease; a branch/worktree is exceptional, not
  automatic.
- Temporary isolation is allowed only for rollback safety, conflicting mutation,
  or exact-head validation. Normally no more than one temporary mutating worktree
  exists, under `D:\Francis-support\worktrees`, with an owner, task, exact base,
  lease, and removal condition.
- Workers never merge themselves or modify another assignment's files. ATLAS
  owns the mutating queue, review routing, integration, and cleanup.
- Promoted, rejected, superseded, or parked worktrees are removed in the same
  integration cycle after unique state is retained by `main` or an intentional
  ref. Parked branches do not retain permanent checkouts.
- Temporary reversible drive mappings may provide short Windows paths; permanent
  drive-root worktree aliases are prohibited.
- Capital Room content remains outside the Francis repository under
  `D:\Francis-support\capital`.

ATLAS remains an active build director. At the start of each management turn it
reconciles native session topology, then spends available capacity on executable
work, evidence review, validation, integration preparation, or a concrete
operator escalation. Control Room writing follows operating state and does not
replace implementation or review work.

`SESSION_TOPOLOGY.md` distinguishes durable seats from live, controllable,
running, idle, completed, stale, and unreachable sessions. A UUID alone is not
proof of reachability. ATLAS does not duplicate a live seat and uses native agent
controls to steer, wait, release, resume, or replace sessions when available.

## Runtime Isolation

Worktrees do not isolate runtime state. Every mutating card must assign:

- unique `FRANCIS_DATA_DIR` and any other state directories;
- API, overlay, and frontend ports;
- permitted services and processes;
- whether the operator-visible Orb may be used;
- startup, shutdown, and cleanup procedures.

All allocations are recorded in `RUNTIME_LEASES.md`. Live-service access is
denied by default. Ports `8000`, `8787`, and `5173` are operator-reserved. No two
fronts may share a writable data directory or active port. Unknown processes are
never killed merely because they hold a desired port.

New runtime state belongs under `D:\Francis-support\runtime-leases`. Released
lease data is removed or archived during the same integration cycle after
required logs and receipts are preserved. Historical receipts retain their
original recorded paths.

Before `READY_FOR_REVIEW`, the worker stops every owned service, releases ports,
preserves required logs/receipts, and submits cleanup evidence. ARGUS and LUMEN
may not operate against the same live Orb or shared runtime state concurrently.

## Front States

Allowed states:

`QUEUED`, `READY`, `ACTIVE`, `BLOCKED`, `READY_FOR_REVIEW`, `IN_REVIEW`,
`REMEDIATION_REQUIRED`, `READY_FOR_PROMOTION`, `PROMOTED`, `CANCELLED`.

Workers never report `DONE`. A state transition requires exact evidence in a
message shard and an updated board entry.

## Messages And Shards

Each material report has ID `MSG-YYYYMMDD-NNN` and exactly these fields:

```text
FROM:
TO:
FRONT:
MESSAGE TYPE:
TASK CARD:
BRANCH:
WORKTREE:
CURRENT COMMIT:
CLAIM:
EVIDENCE:
CONTRACTS AFFECTED:
DEPENDENCIES:
BLOCKER OR QUESTION:
REQUESTED ACTION:
NEXT SMALLEST TRUTHFUL STEP:
```

Message types: `KICKOFF`, `FINDING`, `DEPENDENCY`, `QUESTION`,
`CONTRACT_COLLISION`, `BLOCKER`, `EVIDENCE`, `READY_FOR_REVIEW`,
`REVIEW_RESULT`, `DECISION`, `HANDOFF`.

`MESSAGE_LOG.md` is a bounded index. Messages live under monthly/front shards.
Roll a shard at 128 KiB or 250 material messages. Closed shards are immutable;
corrections are new messages referencing the original ID.

`EVIDENCE_INDEX.md` records exact commits, commands/runs, receipt IDs, external
artifact paths/hashes, and verification status. `OPERATOR_QUEUE.md` contains only
gated decisions; queue presence never grants authority.

## Seat Liveness

Each staffed active seat submits a material report or structured heartbeat every
Control Room sync cycle. A heartbeat includes seat, front, card, branch,
worktree, commit, state, latest validation, blocker, and next action.

- One consecutive missed cycle: mark `STALE`, request a heartbeat, inspect held
  dependencies/leases, and reject reliance on unverified progress.
- Two consecutive missed cycles: mark the session `PRESUMED_DEAD`, preserve the
  last verified commit, inspect without reset/clean, preserve and quarantine
  uncertain work, release only proven resources, replace the session in the same
  seat, and use a continuation branch such as `codex/<slice>-r2` if necessary.

The replacement receives the seat file, card, messages, contracts, last verified
commit, unresolved questions, and next action. Recovery state is committed in
the next Control Room sync.

## Review Routing

1. Worker reports `READY_FOR_REVIEW at <commit>` with exact acceptance evidence.
2. MERIDIAN reviews architecture/contract impact when the card asks a concrete
   architecture question.
3. SENTINEL reviews authority, tenancy, security, or destructive impact when
   applicable.
4. HARBOR reviews portability, branch base, CI, and exact-head integration.
5. VERA independently maps every acceptance criterion to evidence.
6. ARCHIVIST verifies receipt, ledger, and traceability claims when applicable.
7. CLAUDE audits the story/substrate only through a verified external bridge.
8. ATLAS decides whether routine local promotion is justified.
9. The operator decides every gated action.

Review is not ceremonial. Each requested seat receives a concrete question. A
reviewer reports findings; it does not edit the worker branch or redefine the
card. Remediation returns to the owning worker.

The two-cycle ceiling applies to new independent defect families and scope
expansion, not to proof that an existing acceptance criterion still fails. A
review finding mapped directly to an unsatisfied card criterion remains in the
current cycle until that criterion passes. After two unsuccessful attempts on the
same defect, ATLAS replaces or pairs the worker rather than escalating
automatically. Split, park, or seek operator direction only when correction would
expand accepted scope or change authority, policy, trust boundaries, or another
established gate. Every new regression test must name the original acceptance
criterion, a reachable failure path, and the exact contract claim it protects.
General fail-closed value alone does not expand a card.

A completed specialist question is not repeated unless the new diff materially
touches that contract. No additional pre-remediation review runs against an
exact candidate already classified `REMEDIATION_REQUIRED`.

## Dependency And Throughput Scheduling

`DEPENDENCY_GRAPH.md` records for every front its exact objective, roadmap
priority, current commit, dependencies, consumers, unresolved contracts,
validation, reviewers, integration order, operator gates, critical-path state,
and next executable action.

ATLAS prioritizes work that unblocks multiple fronts, then the current critical
path, contract clarification, validation, review, integration preparation, and
lower-risk work already inside a card. It does not create speculative fronts to
occupy compute. Unused native-agent capacity may perform concrete read-only
acceptance, architecture, security, portability, receipt, integration, failure,
or Control Room consistency reviews.

While a distinct exact-head validation runs, ATLAS continues non-conflicting
diff review, contract searches, reviewer preparation, dependency analysis, and
integration planning. It does not write to a branch while that run is intended
to prove the branch's current exact head.

## Validation Tiers And Receipts

Validation tiers are:

1. edit loop: syntax, changed-file Ruff/format, changed-module mypy, focused
   tests, and diff checks;
2. stable candidate head: card acceptance, subsystem regression, changed-path
   static checks, and independent affected-delta review;
3. integrated local main: meaningful post-integration checks against the exact
   head;
4. pushed main: remote CI/CodeQL is the normal repository-wide gate. Local full
   `scripts/check.ps1` is reserved for broad integration, release checkpoints,
   or CI-divergence diagnosis.

Every material run receives a `VAL-YYYYMMDD-NNN` entry indexed by
`VALIDATION_RUNS.md`. It records seat/front, exact commit, branch/worktree,
command, working directory, runtime lease, reproducibility-relevant environment,
start/finish, exit and counts, artifact, disposition, what it proves, and what it
does not prove. PID, silence, and elapsed time are never pass evidence.

An otherwise identical rerun requires a changed commit/base/environment/platform/
selection/lease/hypothesis, an incomplete prior run, a flake measurement, an
independent reviewer reproduction, or suspected contamination.

Do not start a full suite on a candidate already known to require remediation
unless that run was active before the finding and its exact-head result is being
preserved. Remediation uses edit-loop and card-focused validation first; the full
gate begins only after the focused acceptance target is green.

New evidence is immediately classified as accepted, incomplete, failed, scope
violation, contract collision, remediation required, review-ready,
promotion-ready, or operator-gated. ATLAS routes the corresponding next action
before batching documentation.

## Exact-Head Promotion

Before promotion ATLAS must:

1. record the worker's review-ready commit;
2. confirm the candidate is based on the intended exact `main` head;
3. run focused acceptance, the complete affected card/subsystem suite, and
   changed-path static checks;
4. confirm the final diff satisfies the card and affected reviews;
5. freeze unrelated local-main mutation;
6. commit or fast-forward the exact validated candidate on `main`;
7. verify commit reachability and run meaningful post-integration validation;
8. remove any temporary checkout after its state, processes, lease, and artifacts
   pass the removal checklist;
9. commit the resulting Control Room sync when material state changed.

The exact promoted head must be the head that passed final validation. Publishing
or pushing remains operator-gated. Remote branch deletion is operator-gated.

During an active promotion campaign, ATLAS holds at most one open material
Control Room sync between local-main promotions. Once a worker becomes
review-ready, ATLAS commits that bounded sync, freezes further local-main docs
movement, and keeps the freeze until the candidate is promoted or rejected.
Non-material wording or index polish does not delay a green exact-head promotion.

## Operator Escalation Gates

The operator alone controls these actions.

### Governance And Authority

- governance-rule, authority-boundary, policy, approval-rule, tenancy, or trust-
  boundary changes;
- weakening receipts, auditability, or readback requirements.

### Legal

- `LICENSE`, legal text, copyright, attribution, or acceptance of third-party
  legal terms.

### Secrets And Credentials

- creating, exposing, rotating, transmitting, committing, or deleting secrets;
- credential-store changes, production credentials, or sensitive data.

### External And Public Surfaces

- pushing `main`, publishing branches, GitHub settings/visibility, releases,
  public tags/packages/docs/announcements, or external-service changes.

### Roadmap And Closure

- roadmap redefinition, closure-criteria changes, stage closure/reopening,
  project completion, or accepting unresolved remediation as complete.

### Destructive Or Irreversible Actions

- deleting or overwriting unknown work; destructive reset/clean; force-push;
  shared-history rewrite; remote-branch, receipt, or operator-data deletion;
  irreversible migrations or external actions.

### Uncertain Promotion

- any merge ATLAS is less than certain about; unresolved conflict; missing
  evidence; unexplained scope expansion; ambiguous validation; uncertain
  portability/authority impact; or uncertain protected-live-path impact.

When a gate is reached: stop that action, preserve work, stage exact evidence,
name the decision, present options, recommend one, state risks/consequences, and
ask the operator. Other isolated work may continue.

## ATLAS Context Lifecycle

ATLAS is a durable seat; its conversational session is disposable. A reset is
justified only by a repository-truth contradiction, loss of a precise critical
path, context dominated by completed or superseded work, materially degraded
clarity after compaction, a clean campaign or promotion boundary, or an operator
request. Elapsed time and sync count alone are not reset triggers.

An in-session reread and reconciliation is a **context refresh**. It improves
hygiene but does not erase or replace conversation. A **context replacement**
starts a genuinely fresh ATLAS root session. ATLAS must never claim replacement
after only refreshing or summarizing. If native controls cannot create a fresh
root manager session, ATLAS says so and may prepare only the minimum operator
action or bounded checkpoint required; it does not simulate replacement.

Truth order is operator instruction, `AGENTS.md`, completion-ledger shipped
posture, live Git/agent/process/validation/lease/runtime evidence, Control Room
campaign state, roadmap/architecture intent, then old conversation. Goal-
controller labels do not define Francis build state.

Continuity has four layers: the standing goal preserves mission, the completion
ledger preserves accepted shipped posture, the Control Room preserves campaign
organization, and live inspection preserves present-tense truth. Old conversation
is not an authoritative continuity layer. Unpromoted commits, assignments,
reviews, context maintenance, and running validations never move ledger posture
or completion percentages.

During a refresh, ATLAS pauses new dispatches briefly; reads `AGENTS.md`, bounded
current ledger sections, `SESSION_BRIEF.md`, `BOARD.md`, `INTEGRATION_QUEUE.md`,
`RUNTIME_LEASES.md`, and active cards; verifies heads, worktrees, dirty ownership,
controllable sessions, validation exits, leases, ports, and protected runtime;
classifies remembered claims as current, stale, superseded, incomplete, or
unverified; discards stale assumptions; reconstructs the critical path; and
continues useful work in the same turn. Refresh alone creates no handoff, commit,
service action, full gate, or operator request.

Before reset, ATLAS briefly stops new assignments, reconciles exact heads, dirty
ownership, sessions, validations, leases, blockers, reviews, and gates, and
ensures every active worker has a seat, card, branch/worktree, verified head,
assignment, next action, and lease. Existing Control Room files are updated and
committed only when material state already requires a normal sync. Routine
resets do not create parallel handoffs or stop workers.

An actual replacement uses existing Control Room surfaces when sufficient. Only
exceptional recovery may add one `ATLAS-CONTEXT-REPLACEMENT-YYYYMMDD-NNN.md`
checkpoint under `handoffs/`, below 8 KiB and limited to navigation facts. The
checkpoint is not a source of truth and never justifies a commit by itself.

A fresh ATLAS reads only `AGENTS.md`, current/latest ledger sections,
`SESSION_BRIEF.md`, `BOARD.md`, `INTEGRATION_QUEUE.md`, `RUNTIME_LEASES.md`, and
active task cards before verifying local/remote heads, worktrees, controllable
sessions, validation exits, and protected runtime boundaries. It loads deeper
history only when the next action requires it and must dispatch or resume useful
work in the same turn.

A fresh ATLAS assumes no old agent handle is controllable. It matches exact IDs
through native controls, requests acknowledgement before depending on delivery,
preserves unreachable worktrees, and replaces sessions through the durable-seat
protocol. A successful send proves control-plane acceptance, not worker receipt.

Reset success means the fresh seat can state shipped posture, active fronts,
exact heads, validation state, critical path, cheapest promotion candidate,
protected boundaries, and next executable action without conversational memory.

## Handoff Minimum

A handoff names the seat, front, card, branch, worktree, runtime lease, latest
verified commit, contracts, validation, messages, findings, dependencies,
blocker, and next smallest truthful action. No handoff may rely on chat memory.

## Continuous Operating Condition

ATLAS continues until each active front is promoted with exact evidence, ready
for promotion behind an operator gate, blocked by a concrete external fact,
waiting on a named operator decision, actively assigned remediation, or
operator-cancelled. A report, running or failed test, initial commit, task-card
creation, or temporary missing session is not a terminal condition.
