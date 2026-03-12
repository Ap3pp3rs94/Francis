# Francis

Francis is a governed operator layer for human work.

If the project succeeds, the machine stops feeling like a pile of disconnected tools and starts feeling like an environment with a resident operator that understands context, carries continuity, acts inside explicit scope, returns receipts, and never stops being subordinate to the user.

This README is the all-in-one top-level document for the repository. It is meant to stand on its own as the public entrypoint on GitHub:

* what Francis is
* what Francis is not
* how the system is supposed to behave
* what exists in the repo now
* how the architecture is shaped
* how the project is built
* what the staged roadmap looks like
* how to run the current code

`ROADMAP.md` still contains the longer doctrine and build detail, but this file is intentionally large enough to carry the whole shape of the project in one place.

## The Short Version

Francis is not trying to be:

* a chatbot with tools
* a workflow toy
* a dashboard
* a generic autonomous loop
* a surveillance layer
* a coding copilot trapped inside one editor tab
* a personality shell wrapped around a model

Francis is trying to become:

* an Operator Layer over the user's computing environment
* a Digital Twin of how the user actually works
* a 4th-wall interface that appears where the work is happening
* a mission-bearing system that carries continuity over time
* a forge-bearing system that can create new capability under governance
* a governed executor that can become the user's hands inside explicit scope
* a bounded away-mode operator that can keep momentum alive without becoming a hidden sovereign

The key phrase is simple:

Francis should feel unreal in capability and boringly trustworthy in law.

## What Francis Is

Francis is a compound system. It is not one trick.

At maturity, it is all of the following at once:

* an Operator Layer
* a Digital Twin
* a persistent Presence
* a Mission system
* a Forge system
* an Apprenticeship system
* a Knowledge Fabric
* a Trust-calibrated intelligence
* a governed execution substrate
* a Lens surface that lives in place instead of behind a detached chat tab
* an embodied Orb presence object that makes presence, conversation, execution, and stop paths physically legible
* a Swarm-capable internal architecture
* a Federated multi-node architecture
* a managed-copy business platform

Those are not side features. They reinforce each other.

## What Francis Is Not

Francis must not drift into weaker categories during buildout.

It is not:

* a health monitor that over-focuses on telemetry and under-focuses on work context
* a chat wrapper that waits passively for prompts
* a generic agent playground that hides power behind novelty
* a spyware assistant that captures too much and governs too little
* a personality-first product that borrows trust from style
* a loose script pile that looks powerful but does not compound cleanly
* a black box that cannot explain what it did, why, or under what authority

## The Core Promise

The user should eventually be able to say:

* watch what I am doing
* help when it matters
* take over when I say so
* keep bounded momentum alive while I am away
* learn from how I work
* build new capabilities from repeated friction
* never cross the line without telling me

If Francis can do that truthfully, safely, visibly, and with receipts, then it is becoming real.

## System Law

Francis is governance-first. The law is not a later hardening pass.

The system is built around these non-negotiables:

* the user is always sovereign
* scope is always explicit
* approvals are real, not implied
* meaningful action must produce receipts
* trust calibration must remain visible
* revocation must always be possible
* content never grants authority
* no fabricated state
* no hidden control

### Control Modes

Francis operates through explicit modes:

* `Observe` - read, summarize, inspect, compare, and prepare without mutation
* `Assist` - propose, draft, explain, and stage while the user still holds execution
* `Pilot` - execute within explicit delegated scope, with visible authority and interruptibility
* `Away` - continue bounded, event-driven, governed night-shift work while the user is away

These are legal states, not just UI labels.

### Scope

Francis may only act inside declared boundaries:

* approved repos and directories
* approved applications or windows
* approved risk envelopes
* approved nodes or copies

Relevance is not permission.

### Approvals

Francis must not quietly reinterpret:

* prior approval as standing approval
* familiarity as authority
* repeated behavior as new permission
* "probably okay" as lawful delegation

Approval has to be explicit, current, and inspectable.

### Receipts

Every meaningful action should leave evidence such as:

* run id
* trace context
* authority basis
* artifacts
* verification outcome
* summary
* rollback or recovery path where relevant

If receipts do not exist, Francis must not overclaim.

## Why This Project Exists

Traditional computing makes the human carry too much hidden coordination cost.

The human has to:

* remember context across tools
* reconstruct what changed
* translate intent into commands and apps
* notice repeated friction
* manage continuity across sessions
* keep track of what is pending, blocked, staged, or done
* decide what should become reusable capability

Francis exists to absorb part of that burden without stealing authority from the user.

The goal is not "more features."

The goal is a new computing posture:

* more continuity
* more leverage
* more operational memory
* more bounded initiative
* less manual glue work
* less reset between sessions

## What Exists In The Repo Today

This repository is not just a vision dump. It already contains meaningful system surfaces.

### Core services

* `services/orchestrator/` - main API surface and system coordination layer
* `services/observer/` - probes, baselines, anomaly detection, scoring, and event emission
* `services/worker/` - queued execution with leases, backoff, deadletter, and safety controls
* `services/gateway/` - gateway and middleware for auth, RBAC, panic mode, request IDs, rate limiting, and proxy flows
* `services/hud/` - Lens/HUD operator surfaces for current work focus, approval queue, execution journal, repo drilldown, incidents, missions, and runs
* `services/voice/` - voice scaffolding

### Shared package layers

The root package config wires in shared internal packages for:

* `francis_core`
* `francis_brain`
* `francis_policy`
* `francis_skills`
* `francis_presence`
* `francis_forge`
* `francis_connectors`
* `francis_llm`

### Tests

The repo includes:

* unit tests
* integration tests
* evals
* red-team coverage

### Runtime state

Francis is local-first and stateful. Live artifacts land in areas like:

* `workspace/`
* `runtime/`

These hold journals, queues, missions, incidents, receipts, telemetry, and other live system artifacts.
`workspace/` is runtime-managed local state, not a source-controlled artifact surface.

### Current Lens usage loop

The most important HUD/operator surfaces are now shifting from status cards toward real usage flow:

* `Dashboard Cards` - server-shaped landing cards with signal, summary, evidence, and detail so the first HUD surface stops flattening operator state into generic text
* `Shift Report` - a Stage 10 away-continuity surface with backend-owned state, severity, evidence, recommendations, handback detail, mission focus, trust posture, autonomy budget/guardrail posture, away-safe task visibility, teaching-session continuity, and return-briefing controls so Away Mode returns the user to a receipted summary and the next operator move instead of a mystery
* `Teaching Sessions` - a Stage 11 Apprenticeship surface with session creation, step capture, replay detail, generalized workflow review, cited related evidence, explicit trust posture, backend-derived create/record defaults from live mission/repo/terminal context, and governed generalize/skillize controls so bounded demonstration becomes a visible Lens workflow instead of a hidden API-only feature
* `Capability Library` - a Stage 17 capability-economy surface with governed internal-library rows, promotion approval state, backend-owned focus selection, compact audits, and explicit `Request Promotion Approval` / `Promote Capability` controls so staged packs become visible assets instead of hidden Forge residue
* `Swarm Units` - a Stage 15 swarm surface with explicit role-bearing units, bounded delegation envelopes, lease / completion / failure controls, backend-owned delegation focus, compact audits, and deadletter visibility so internal specialization becomes inspectable instead of turning into an agent zoo
* `Federation Topology` - a Stage 16 federation surface with explicit paired nodes, scoped trust, heartbeat / stale-state visibility, revocation controls, backend-owned focus selection, compact audits, node-attributed receipts, and paired-node remote approval controls so multi-node continuity becomes inspectable instead of vague
* `Current Work Focus` - repo state, changed paths, blockers, latest terminal pressure, active teaching-session pressure, active staged-capability pressure, a structured terminal breakdown, review-ready apprenticeship focus, the next actionable move, whether the current operator link is still active or stale, what the first terminal failure edge actually was, explicit evidence for why Lens picked the current move, cited local fabric evidence when a cached Knowledge Fabric snapshot can ground the recommendation, a backend-owned approval-resume state so `Approve + Run` is described by the current-work contract instead of only by button text, and a backend-owned focus-action contract so the main next-move controls are no longer client-inferred
* `Action Deck` - the generic Lens action grid now renders from a backend-owned operator surface instead of raw action payloads, with server-shaped action summaries, primary button labels, execution args, and focus continuity
* `Approval Queue` - pending approvals with in-place approve/reject controls, resumable `Approve + Run` handling for supported usage actions, server-shaped approval detail cards, explicit current-vs-historical state, backend-selected focus rows, and compact audit objects instead of raw approval rows
* `Blocked Actions` - policy-denied or approval-gated actions with backend detail summaries, detail cards, backend-selected focus, and compact audit objects instead of raw blocked rows
* `Execution Journal` - recent receipts and active run state, linked back to the current operator move with server-shaped receipt summaries, receipt presentation cards for repo actions, explicit current-vs-historical state, backend-selected focus rows, and compact audit objects instead of raw receipt rows
* `Execution Feed` - server-shaped execution guidance, severity, and evidence so the active operator chain is described by a stable contract instead of browser-only composition
* `Repo Drilldown` - direct `repo.status`, `repo.diff`, `repo.lint`, and fast-check execution from the same Lens surface, with server-shaped execution summaries, compact result cards, structured drilldown evidence, explicit severity, persisted repo context across Lens refresh, a backend-owned control contract for the repo buttons, and a backend-owned audit object instead of a browser-retained raw payload
* `Mission Stack` and `Incident Posture` - server-shaped mission and incident summaries plus per-item detail cards, backend-selected focus rows, and compact audit objects so active work pressure, security pressure, and current operational focus stop reading like raw snapshot dumps
* `Inbox Surface` and `Run Surface` - backend-shaped message and run surfaces now rendered in the HUD with current-vs-historical detail state, backend-selected focus rows, stronger message detail cards, run continuity that carries the latest receipt summary directly into the run surface, and compact audit objects instead of raw row dumps

That is still not the final Lens, but it is the right direction: Francis should expose what matters now, what is blocked, what it can do next, what it just did, and what happened while the user was away. The HUD is increasingly being shaped as one operator loop instead of a set of unrelated panels, with current-work linkage carrying through approvals, approval-resume continuity, execution, receipts, stale/active continuity cues, terminal-failure anchors, server-shaped repo execution summaries, explicit mission and incident summaries, backend-owned action-grid controls, mission-centered shift reports, run-surface receipt carry-through instead of leaving run review to the journal alone, capability-library pressure so staged Forge output can become governed internal leverage, explicit swarm delegation so specialization stays inspectable and bounded, and explicit federation topology so paired nodes remain inspectable and revocable. The detail panes should read as operator guidance first and raw proof second, with structured evidence where possible instead of nested raw payloads, and the browser should increasingly rerender only the surfaces whose backend digests actually changed. The SSE path is now moving in the same direction: one full bootstrap, then narrower server-owned surface updates instead of repeated full-surface pushes.

## Current Architecture Shape

At a high level, the repository is shaped like this:

1. The user interacts with the system through routes, control surfaces, and future in-place Lens surfaces.
2. The orchestrator holds control state, approvals, missions, receipts, autonomy coordination, and system-level routing.
3. The observer scans the environment and emits grounded evidence.
4. The worker executes queued work under limits, leases, and safety controls.
5. Shared packages provide common policy, state, memory, presence, and LLM-facing logic.
6. Runtime artifacts are stored locally for continuity, auditability, and receipts.

### Main orchestrator route families

The orchestrator currently exposes families such as:

* approvals
* autonomy
* capabilities
* control
* forge
* health
* inbox
* lens
* missions
* observer
* presence
* receipts
* runs
* telemetry
* tools
* worker

That is already the shape of a serious operator platform, not just a single endpoint demo.

## Repository Map

Use this as the practical top-level orientation:

* `README.md` - all-in-one repo entrypoint
* `ROADMAP.md` - long-form doctrine and stage detail
* `VISION.md` - project vision framing
* `services/` - runtime service surfaces
* `packages/` - shared internal libraries
* `docs/` - architecture, governance, operations, product, business, and lore
* `tests/` - unit, integration, eval, and red-team coverage
* `policies/` - policy surfaces
* `schemas/` - schema contracts
* `proto/` - protocol contracts
* `infra/` - infrastructure and secret-related repo surfaces
* `workspace/` - live local-first runtime state
* `runtime/` - runtime-only data

## Build Cadence

Francis should not be built as a pile of disconnected enthusiasm.

Every meaningful change should follow the same cadence:

1. Restate the user-experience objective.
2. Name the affected modules and files.
3. Implement coherent full-file changes.
4. Run quality gates.
5. Return receipts.

This matters because the project is trying to build:

* law before power
* truth before theater
* visibility before deep delegation
* continuity before compounding
* safe execution before takeover

### Non-negotiables during buildout

* user sovereignty stays explicit
* scope stays explicit
* no hidden control
* no fabricated state
* no unreceipted action
* content never grants authority
* stronger power requires stronger gates

## Quality Gates

The roadmap defines three gate families for serious work:

* code quality
* safety quality
* product quality

In this repository, the minimum expected routine is:

* run the fast lane with `./scripts/test.ps1 -Lane fast`
* run `./scripts/lint.ps1`
* run the full lane with `./scripts/test.ps1 -Lane full` before shipping major slices
* verify that scope, approvals, receipts, and user-visible behavior still hold

`workspace/` and `runtime/` are intentionally excluded from Ruff because they contain live artifacts rather than source code.
Git should treat `workspace/` the same way: local runtime state stays local unless an artifact is intentionally promoted into a real repo surface.

## Operating Realism

The roadmap now explicitly names the practical failure domains that usually break ambitious systems late:

* model and provider strategy
* secret, credential, and identity handling
* state and schema migration discipline
* performance, availability, and graceful degradation
* accessibility and human factors
* supply-chain and capability provenance
* deletion, decommissioning, and clean exit paths

This matters because a system can be philosophically correct and still fail in production through:

* provider collapse
* weak secret handling
* broken upgrades
* stale state
* invisible degraded mode
* exhausting UI behavior
* unsafe imports
* bad decommission paths

Francis has to be stronger than that class of failure.

## Staged Roadmap In One File

The long-form roadmap is expansive. This is the condensed build sequence.

### Stage 0 - Foundation and operating system contracts

Establish run identity, journaling, governance defaults, receipts, and local-first workspace law.

### Stage 1 - Grounded presence

Make Francis truthful, calm, and useful through grounded state, briefings, and honest continuity.

### Stage 2 - Observer

Add real probes, anomaly detection, incident evidence, and event emission.

### Stage 3 - Missions

Turn intent into durable structured motion with mission objects, lifecycle, and continuity-bearing progress.

### Stage 4 - Forge

Turn repeated friction into staged, governable capability growth rather than manual repetition forever.

### Stage 5 - Event-driven reactor

Replace generic loops with bounded, event-driven autonomy.

### Stage 6 - Lens MVP

Make Francis experientially real in place, with visible mode and authority surfaces.

The long-term Lens embodiment is not just panels and chips. It also includes the Orb: a single presence object that can rest ambiently, unfold into voice and chat in place, become the visible operator cursor during execution, and serve as the immediate kill surface.

### Stage 7 - Telemetry MVP

Add high-signal, scope-bound visibility into the user's real work context without becoming invasive.

### Stage 8 - Executor substrate

Give Francis real hands through sandboxed tools, allowlists, budgets, and receipts.

### Stage 9 - Takeover

Let Francis become the user's hands under explicit Pilot authority, live visibility, and handback discipline.

### Stage 10 - Away mode

Allow lawful night-shift continuity without hidden authority growth.

### Stage 11 - Apprenticeship

Teach once, keep forever, under bounded demonstration and reviewable learning.

### Stage 12 - Knowledge Fabric

Build real operational memory over artifacts, runs, receipts, incidents, and decisions.

### Stage 13 - Trust calibration

Make claim strength track evidence strength so Francis never overclaims progress or certainty.

### Stage 14 - Adversarial hardening

Treat content as untrusted input and continuously test for prompt injection, policy bypass, and authority laundering.

### Stage 15 - Swarm

Scale one governed Francis through specialized internal units without multiplying authority, with explicit roles, bounded delegation envelopes, trace-preserving handoff, and deadletter visibility.

### Stage 16 - Federation

Extend continuity across nodes and devices under zero-trust defaults and revocable relationships, with explicit pairing, scoped trust, stale-node visibility, safe remote approvals, and node-attributed continuity.

### Stage 17 - Capability economy

Turn useful capability into governed, versioned, tested, documented, promotable assets, with an internal library surface that makes staged packs, approvals, and promotions visible inside Lens.

### Stage 18 - Managed copies

Create isolated customer-specific copies without surrendering the core or pooling raw private data.

### Stage 19 - Productization

Make Francis a real machine-resident daily-layer product with startup, summon, update, recovery, export/import, and clean install/uninstall behavior.

That is also where the Orb becomes an implemented embodiment layer instead of a doctrine note: a state-driven overlay object whose motion, pulse, handback, and stop behavior map to real operational state.

## What The User Should Feel

If Francis is built correctly, the user should eventually feel:

* I am not alone inside a machine anymore
* continuity survived my interruption
* the system understands what I am trying to do
* it can help in place instead of making me switch contexts
* it can take over when I explicitly allow it
* it never pretends authority it does not have
* it remembers what matters
* it does not act creepy, hidden, or hungry

That emotional standard matters just as much as mechanical correctness.

## Quickstart

### Prerequisites

* Python 3.10+
* a virtual environment is recommended

### Install

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e .[dev]
```

### Run tests

```bash
./scripts/test.ps1 -Lane fast
```

Full sweep:

```bash
./scripts/test.ps1 -Lane full
```

Make targets:

```bash
make test-fast
make test-full
```

### Run the orchestrator

```bash
uvicorn services.orchestrator.app.main:app --reload
```

### Run the gateway

```bash
uvicorn services.gateway.app.main:app --reload --port 8001
```

## Where To Start Reading In The Code

If you are new to the codebase, start here:

1. `README.md`
2. `ROADMAP.md`
3. `VISION.md`
4. `services/orchestrator/app/main.py`
5. `services/orchestrator/app/routes/`
6. `services/observer/app/main.py`
7. `services/worker/app/main.py`
8. `tests/integration/`
9. `docs/governance/`

## Notes

* The orchestrator is the primary operational surface today.
* The repository already contains meaningful implementation, not just future-state prose.
* The roadmap is still the deepest doctrine source, but this README now carries the public all-in-one project story.
