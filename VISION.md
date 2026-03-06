# Vision

## Francis Operator Layer
Francis is an operator layer over the PC: a 4th-wall AI presence that understands what the user is building and assists directly inside the real work context.

## Francis Lens Experience
Francis Lens is the visible overlay/control surface across development and operations workflows. It should expose mission intent, current state, blockers, and high-value next actions in place, not in disconnected dashboards.

## User Control First
The user is always the pilot. Francis can execute as the user's operator only when mode, scope, and approvals allow it. Control must be explicit, reversible, and continuously visible.

## In-Place Assistance
Francis should assist where work already happens: repository, terminal, IDE diagnostics, build/test logs, and optional browser console telemetry. It should reduce context switching and increase execution speed.

## Pilot Mode
Pilot Mode is takeover-on-command with hard guardrails. Francis acts within approved scope, follows branch-first workflows for code, verifies outcomes, and returns control with receipts and a concise summary.

## Away Mode
Away Mode is optional continuity. Francis advances approved missions, stages improvements, prepares decisions, and queues approvals. It should produce ordered progress and clear handback briefings, never chaos.

## Capability Evolution
Francis evolves through Forge by staging new capabilities from observed friction. Staged capabilities are validated and cataloged, but never promoted/deployed without explicit promotion gates.

## Grounded Truthfulness
Francis must never fabricate system state or work outcomes. Claims require evidence. Actions require receipts. The system should feel powerful because it is reliable, not because it is dramatic.

## Personality as Interface
Francis has a measured personality as an interface layer: calm, confident, and human-readable. Presence improves usability and trust, but personality never overrides governance, control modes, scope limits, approvals, or receipt contracts.

## Vision Addendum: The Missing Pillars

### A) Apprenticeship Mode
#### What It Is
Apprenticeship Mode captures user demonstrations and converts them into reusable operator patterns. The flow is explicit and staged: Demonstrate, Label Intent, Replay, Generalize, then Skillize.

#### Why It Matters
It lets Francis learn the user's real workflow conventions without sacrificing approval gates or observability.

#### Done Looks Like
- Teaching sessions can be recorded with scope, receipts, and redaction boundaries.
- Replay can run in Assist/Pilot with user-visible step plans before execution.
- Generalized outcomes are emitted as staged capabilities with tests and docs, never auto-promoted.

### B) Personal Knowledge Fabric
#### What It Is
The Knowledge Fabric is a local-first index over user artifacts such as repos, docs, decisions, logs, and mission history. It supports searchable, cited retrieval so Francis can reason from evidence instead of memory guesses.

#### Why It Matters
It turns fragmented history into actionable context that is traceable to local sources.

#### Done Looks Like
- Artifact ingestion records metadata, provenance, and freshness timestamps.
- Retrieval responses include explicit local citations for every factual claim.
- Operators can filter by scope, artifact type, and recency for grounded planning.

### C) Intent Engine
#### What It Is
The Intent Engine maintains a live model of objective, constraints, stage, definition-of-done, and active risks. Missions remain concrete execution units while intent provides global direction and prioritization.

#### Why It Matters
It prevents drift by keeping every recommendation and action aligned to the actual goal state.

#### Done Looks Like
- Intent state is updated from user directives, mission progress, and event signals.
- Suggestions and takeover plans reference intent fields explicitly.
- Conflicts between mission activity and intent constraints are surfaced before execution.

### D) Remote Presence
#### What It Is
Remote Presence provides optional approve/deny/pause controls from phone or remote devices. It extends control-plane access without changing the sovereignty rule: user is always pilot.

#### Why It Matters
It keeps governance and continuity intact when the user is away from the primary workstation.

#### Done Looks Like
- Approval queue and critical alerts are available on a secure remote channel.
- Remote actions map to the same scope contracts, receipts, and policy checks as local actions.
- Session handback includes concise state deltas and unresolved approvals.

### E) Trust Calibration
#### What It Is
Trust Calibration labels claims and plans by confidence levels and enforces verification gates before completion claims. Francis distinguishes Confirmed, Likely, and Uncertain states in operator-facing output.

#### Why It Matters
It reduces hallucination risk by aligning language certainty with real verification evidence.

#### Done Looks Like
- Every major claim carries confidence level plus evidence links.
- "Done" status requires configured verification artifacts (tests/build/preview/log checks).
- Uncertain outputs default to recommendation mode, not authoritative action claims.

### F) Digital Twin Contract
#### What It Is
The Digital Twin Contract is a persistent operator profile for conventions, risk posture, and taste preferences. It defines how Francis should act as the user's digital counterpart across repositories and missions.

#### Why It Matters
It makes behavior consistent over time without hidden autonomy shifts.

#### Done Looks Like
- Contract fields include branching style, testing discipline, review strictness, and approval thresholds.
- Runtime decisions reference contract rules in receipts and decision logs.
- Users can version and update contract preferences with explicit change history.

### G) Capability Economy
#### What It Is
Capability Economy treats capability packs as versioned assets managed through stage, validate, promote, and catalog workflows. It starts as an internal library and can later expand to controlled sharing or marketplace models.

#### Why It Matters
It scales Francis beyond one-off scripts into a governed portfolio of reusable operator assets.

#### Done Looks Like
- Packs include semantic version, risk tier, tests, docs, and promotion metadata.
- Promotion requires policy checks and traceable approval receipts.
- Discovery surfaces capability quality, ownership, and compatibility signals.

## Francis as a Swarm (Multi-Unit + Federation)

### Why
Francis needs specialization, parallel execution, and away-mode continuity that a single unit cannot provide alone. Multi-unit coordination raises throughput while keeping governance and receipts intact.

### Two Forms
- Internal multi-agent: specialized Francis units on one machine/repo cooperate through the event-driven reactor.
- Federated multi-node: multiple Francis instances across devices/services coordinate through explicit pairing and scoped trust.

### Done Looks Like
- Capability discovery works: units advertise role and capabilities before delegation.
- Delegation works: work is routed to the right unit/node with explicit scope and risk context.
- Receipts propagate: every delegated action carries `run_id`/`trace_id` and writes auditable artifacts.

## Acceptance Criteria
- Francis never acts outside declared scope.
- Pilot Mode is always visible and revocable.
- Every action leaves receipts (`run_id`, logs, diffs, journals).
- Away Mode returns tangible progress and explicit pending approvals.
- Lens reflects mission intent and execution reality, not just health metrics.
