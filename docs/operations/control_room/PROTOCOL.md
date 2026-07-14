# Francis Control Room Protocol

## Operating Principle

Central coordination. Isolated execution. Evidence-backed integration.

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

- Maximum three concurrent mutating fronts.
- One named worker, task card, `codex/*` branch, worktree, bounded objective,
  file scope, do-not-touch list, acceptance contract, and runtime lease per front.
- Workers never write to `main`, share implementation worktrees, merge
  themselves, or modify another front's files without a revised assignment.
- ATLAS is manager/integrator, not a fourth feature worker.
- Read-only seats do not consume mutating slots. A specialist may mutate only
  after receiving one of those slots plus a card, branch, and worktree.

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

A front receives at most two remediation cycles after its first reviewable
candidate. Cycle one addresses findings mapped directly to the existing card;
cycle two may address only regressions introduced by cycle one. A third
independent issue set must be split into a new card, parked, or escalated. Every
new regression test must name the original acceptance criterion, a reachable
failure path, and the exact contract claim it protects. General fail-closed value
alone does not expand a card.

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
2. stable worker head: card acceptance, subsystem regression, required full
   gate, and independent exact-commit review;
3. rebased promotion head: complete acceptance, full gate, final diff, and any
   materially affected specialist review;
4. integrated local main: meaningful post-promotion checks and one authoritative
   combined full gate; remote CI/CodeQL only after an operator-authorized push.

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

Control Room commits can advance local `main`, so pre-rebase evidence is not
sufficient. Before promotion ATLAS must:

1. record the worker's review-ready commit;
2. commit current Control Room state;
3. rebase the worker branch onto that exact local `main` head;
4. rerun the complete card acceptance suite on the rebased head;
5. run `scripts/check.ps1` on the rebased head;
6. confirm the final diff still satisfies the card and required reviews;
7. freeze new local-main commits;
8. fast-forward local `main` only when certain;
9. verify commit reachability;
10. run meaningful post-promotion validation;
11. commit the resulting Control Room sync.

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

## ATLAS Context Reset

ATLAS is a durable seat; its conversational session is disposable. A reset is
justified only by a repository-truth contradiction, loss of a precise critical
path, context dominated by completed or superseded work, materially degraded
clarity after compaction, a clean campaign or promotion boundary, or an operator
request. Elapsed time and sync count alone are not reset triggers.

Truth order is operator instruction, `AGENTS.md`, completion-ledger shipped
posture, live Git/agent/process/validation/lease/runtime evidence, Control Room
campaign state, roadmap/architecture intent, then old conversation. Goal-
controller labels do not define Francis build state.

Before reset, ATLAS briefly stops new assignments, reconciles exact heads, dirty
ownership, sessions, validations, leases, blockers, reviews, and gates, and
ensures every active worker has a seat, card, branch/worktree, verified head,
assignment, next action, and lease. Existing Control Room files are updated and
committed only when material state already requires a normal sync. Routine
resets do not create parallel handoffs or stop workers.

A fresh ATLAS reads only `AGENTS.md`, current/latest ledger sections,
`SESSION_BRIEF.md`, `BOARD.md`, `INTEGRATION_QUEUE.md`, `RUNTIME_LEASES.md`, and
active task cards before verifying local/remote heads, worktrees, controllable
sessions, validation exits, and protected runtime boundaries. It loads deeper
history only when the next action requires it and must dispatch or resume useful
work in the same turn.

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
