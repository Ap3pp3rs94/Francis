==============================================================================

FRANCIS — ACTION_READINESS.md

Policy + Mechanics: When the system is allowed to act

==============================================================================



Purpose

-------

This document defines FRANCIS "Action Readiness": a deterministic, auditable

gate that decides whether a proposed action may be executed, must be reviewed,

must be simulated/dry-run, or must be denied.



Action Readiness is the bridge between:

   - Intents (what the user/system wants)

   - Plans (how it would be done)

   - Authority (who/what is allowed to do it)

   - Risk (what could go wrong)

   - Evidence (why we believe it will work safely)



Read alongside:

   - docs/API_PERMISSIONS.md

   - docs/GOVERNANCE.md

   - docs/ATTACHMENTS.md

   - docs/CONCURRENCY.md

   - docs/TRUST_MODEL.md

   - docs/RUNBOOK.md

   - config/policies/action_readiness.yaml

   - schemas/action_readiness.schema.json

==============================================================================





## 1. What “Action Readiness” means



**Action Readiness** is a *decision* produced from structured signals that answers:



> “Given the current environment, identity, permissions, trust level, evidence,

> and risk posture — is it safe and authorized to execute this action now?”



This is **not** just “permissions” and not just “safety.”

It is a multi-factor gate that considers:



- **Authorization:** is the actor allowed (scopes, delegations, environment rules)?

- **Capability:** do we have the right tools/connectors/models to do it reliably?

- **Risk:** could it cause harm (data loss, irreversible change, safety hazards)?

- **Evidence:** do we have enough verified context to justify execution?

- **Controls:** are mitigations in place (sandboxing, rate limits, rollback)?

- **Accountability:** can we audit the decision and outcomes?



Action Readiness is designed to be:

- **Deterministic** (same inputs → same decision)

- **Explainable** (decision includes reasons and required conditions)

- **Auditable** (logged with evidence + policy rule IDs)

- **Fail-safe** (uncertainty pushes toward review/deny, not execution)





## 2. Core objects and vocabulary



### 2.1 Action (what we are gating)

An **Action** is a concrete operation that changes state or accesses sensitive data,

typically through connectors, tools, or internal subsystems.



Examples:

- Read-only: “Fetch Jira tickets”, “Query Postgres”, “Download documentation”

- Mutating: “Send email”, “Create GitHub PR”, “Deploy”, “Rotate credentials”

- Safety-critical: “Write PLC register”, “Stop industrial process”, “Emergency shutdown”



### 2.2 Plan (how we execute)

A **Plan** is a sequence of steps (tool calls or internal operations), each step

having:

- target system

- required credentials/scopes

- side effects classification

- expected output schema

- rollback strategy (where applicable)



Action Readiness evaluates both:

- the *action intent*

- the *plan structure* (because a safe-sounding intent can hide unsafe steps)



### 2.3 Evidence (why we believe this will work safely)

Evidence includes:

- verified sources (documents, APIs, state snapshots)

- citations / provenance records

- recent success/failure history

- simulation results or dry-run outputs



Evidence quality is crucial: “I think” is not readiness.





## 3. Readiness decision outcomes



Readiness is a discrete decision with constraints.



### 3.1 Canonical readiness outcomes

FRANCIS uses a small set of outcomes (your policy may rename them, but keep the semantics):



- **DENY**

  - Action must not run.

  - Reasons include: policy violation, insufficient authorization, unsafe category,

    missing mandatory approval, or prohibited environment.



- **REVIEW_REQUIRED**

  - Action may run only after a human approves (or a higher-trust delegate approves),

    typically because the blast radius is non-trivial.



- **DRY_RUN_REQUIRED**

  - Action may run only after a simulation/dry-run step passes thresholds.

  - Often used for deployments, migrations, large writes, external side-effects.



- **READY_WITH_GUARDS**

  - Action may execute automatically, but only with enforced guardrails:

    rate limits, sandbox constraints, write boundaries, allowlists, output schemas,

    additional logging.



- **READY**

  - Action may execute automatically under normal controls.



- **EMERGENCY_ONLY**

  - Action may execute only in declared emergency mode with mandatory logging,

    stricter auditing, and post-incident review.



### 3.2 “Readiness is not permission”

Permissions answer: **“May I call this tool?”**

Readiness answers: **“Should I do it now, given risk and uncertainty?”**



You can be permitted but not ready.





## 4. The Readiness pipeline



Action Readiness is best implemented as a pipeline of checks:



1. **Normalize action request**

   - Validate schema

   - Normalize targets, identities, environment tags

   - Expand plan steps where necessary



2. **Classify**

   - Determine action category from taxonomy

   - Determine side-effect class: read-only / reversible write / irreversible write

   - Determine data class: public / internal / confidential / regulated / secrets



3. **Policy evaluation**

   - Apply global denies (hard rules)

   - Apply environment constraints (airgapped, regulated, safety-critical)

   - Apply connector-specific rules (email, github, industrial, etc.)



4. **Trust + authority checks**

   - Verify identity context (who is acting)

   - Verify credential scope + delegation chain

   - Verify minimum trust level for the category

   - Verify no active trust restrictions (decay, quarantine, incident flags)



5. **Evidence sufficiency**

   - Confirm required evidence exists (citations, snapshots)

   - Confirm recency constraints (stale context is not readiness)

   - Confirm plan preconditions and expected schemas



6. **Control selection**

   - Decide required controls: approval, dry-run, sandbox, rate limit, rollback

   - Attach “required_conditions” and “enforced_controls” to the decision



7. **Decision emission + logging**

   - Emit readiness decision object

   - Log to audit trail with rule IDs and evidence references



8. **Post-action feedback loop**

   - Update outcome tracking

   - Update trust metrics (success/failure, safety record)

   - Append to run history for future readiness calibrations





## 5. Inputs to the readiness engine



Action Readiness must be computed from explicit inputs so it remains auditable.



### 5.1 Required inputs (minimum viable)

- **ActionRequest** (intent, targets, plan steps)

- **ActorContext** (user/service identity, delegation chain)

- **EnvironmentProfile** (dev/home/production/regulated/etc.)

- **PolicyBundle** (action_readiness, api_permissions, sandbox, web_access, etc.)

- **TrustState** (current trust level + restrictions)

- **EvidenceSummary** (what sources/snapshots support the action)



### 5.2 Optional but strongly recommended inputs

- **RecentOutcomeHistory** (last N attempts by category/target)

- **IncidentFlags** (active quarantine, suspicious behavior, failed attestations)

- **BlastRadiusEstimates** (records affected, systems affected)

- **RateLimitBudgets** (per connector, per domain, per run)





## 6. Policy model: hard rules vs soft rules



Action readiness policies should be split into:



### 6.1 Hard rules (deny / require review)

Examples:

- Disallow “production deploy” without approval in production environment

- Disallow credential export to plaintext

- Disallow industrial write commands unless safety-critical mode is enabled and

  a higher trust threshold is met

- Disallow actions in regulated environments that violate data governance tags



Hard rules must:

- have stable rule IDs

- produce deterministic outcomes



### 6.2 Soft rules (increase requirements)

Examples:

- Low confidence → require dry-run

- Unverified evidence → require review

- Stale snapshot → require refresh step

- Large blast radius → require stricter rate limits + staged rollout



Soft rules typically attach conditions rather than deny outright.





## 7. Readiness and environments



Environment profiles drive strictness.



Typical environments:

- **dev**: permissive, still logged, sandbox on by default

- **home/workstation**: moderate, protect secrets and personal data

- **production**: strict, approvals + rollbacks required for writes

- **regulated**: strictest on data governance, retention, and auditability

- **airgapped**: block network actions entirely; allow local-only workflows

- **safety_critical**: enforce high-trust thresholds and emergency controls



Environment policies must be able to:

- override defaults

- tighten rule sets

- enforce denylists/allowlists for connectors and targets





## 8. Control catalog (what readiness can require/enforce)



A readiness decision may attach one or more controls:



### 8.1 Human approval

- required approver class (owner/admin/security officer)

- approval TTL (expires)

- approval scope (what exactly is approved)

- approval artifact (stored in data/approvals)



### 8.2 Dry-run / simulation

- must produce schema-valid outputs

- must meet thresholds (diff size, error count, risk score)

- must record artifacts (logs, simulation traces)



### 8.3 Sandboxing

- filesystem sandbox: path allowlist + write boundaries

- network sandbox: domain allowlist, egress controls

- tool sandbox: restrict high-risk tools unless explicitly allowed



### 8.4 Rate limits and budgets

- per connector (e.g., GitHub API, Slack)

- per domain (web learning)

- per action category (mutating vs read-only)



### 8.5 Rollback and checkpointing

- pre-action checkpoint required for irreversible operations

- rollback plan required for deploy/migrations

- post-action verification required for safety



### 8.6 Output constraints

- enforce output schema validation (reject unstructured outputs)

- redact or block disallowed disclosures (secrets, regulated data)

- require citations when any web-derived claims are used





## 9. Trust integration (readiness depends on trust)



Readiness must consult the trust system:

- **Trust level**: minimum required by action category

- **Trust boundaries**: per domain, per connector, per environment

- **Trust decay**: stale or degraded trust reduces autonomy

- **Trust incidents**: recent safety violations trigger stricter gating



A common policy pattern:

- Read-only actions: allow at lower trust with logging

- Reversible writes: require moderate trust + rollback controls

- Irreversible writes: require high trust + approvals

- Safety-critical actions: require highest trust + emergency mode constraints





## 10. Evidence sufficiency rules



Readiness should require evidence when:

- actions are high blast radius

- actions are based on web-derived or untrusted content

- targets are production/regulated/safety-critical

- the plan is complex or multi-step



Evidence sufficiency checks can include:

- source provenance exists for each key assumption

- sources meet recency window (configurable)

- contradictions resolved or escalated

- attachments scanned/redacted where needed



“Evidence required” should be a first-class condition, not an afterthought.





## 11. Logging and auditability requirements



Every readiness decision must be logged with:

- timestamps, run_id, actor identity

- action request summary (redacted as needed)

- applied rules (IDs + versions)

- final decision + conditions

- evidence references and hashes

- integrity chain (optional but recommended)



Logs should support:

- forensic reconstruction

- “why was this allowed?”

- “which policy changed?”

- differential comparisons across environments





## 12. Recommended schema shape (conceptual)



(Exact fields are defined in `schemas/action_readiness.schema.json` — this is the intent.)



A readiness decision should include:



- `decision`:

  - `outcome`: READY / READY_WITH_GUARDS / DRY_RUN_REQUIRED / REVIEW_REQUIRED / DENY / EMERGENCY_ONLY

  - `reason_codes`: stable identifiers

  - `human_summary`: short readable text

- `requirements`:

  - approvals required (who/what)

  - dry-run required (what simulation)

  - controls enforced (sandbox/rate limits)

- `risk`:

  - risk score + category (qualitative)

  - blast radius estimate

- `evidence`:

  - list of evidence refs + provenance

  - recency and confidence annotations

- `policy_trace`:

  - list of rules applied and decisions at each stage



This decision object becomes an artifact and should be stored.





## 13. Operational examples (how readiness behaves)



### 13.1 Example: read-only web research

- Outcome: READY_WITH_GUARDS

- Controls:

  - web_access allowlist

  - blocked-content logging

  - mandatory citations

  - rate limits



### 13.2 Example: send an email via connector

- Outcome: REVIEW_REQUIRED (in regulated/prod) or READY_WITH_GUARDS (in dev)

- Controls:

  - require explicit recipient + subject confirmation

  - redact secrets

  - log message hash (not raw content if privacy policy demands)



### 13.3 Example: production deploy

- Outcome: DRY_RUN_REQUIRED + REVIEW_REQUIRED

- Controls:

  - run preflight checks

  - capture current state snapshot

  - staged rollout plan + rollback



### 13.4 Example: industrial write command

- Outcome: EMERGENCY_ONLY (default), or REVIEW_REQUIRED with strict gating

- Controls:

  - safety-critical mode enabled

  - highest trust threshold

  - mandatory post-action verification and incident review logging





## 14. Testing and continuous validation



Action Readiness must be tested like a security boundary:



- **Unit tests**

  - deterministic outcomes per policy/rule

  - deny rules cannot regress silently



- **Integration tests**

  - approvals flow

  - sandbox enforcement

  - credential scope enforcement



- **Simulation tests**

  - dry-run artifact correctness

  - rollback feasibility



- **Audit tests**

  - logs include policy trace + evidence

  - integrity chains verify





## 15. Implementation notes (how to wire it)



Recommended call order in runtime:



1. Build `ActionRequest` + `ActorContext`

2. Load `EnvironmentProfile`

3. Load policies (action_readiness + api_permissions + sandbox + domain rules)

4. Pull `TrustState`

5. Run readiness evaluation (pure function if possible)

6. If outcome requires approval/dry-run, emit required artifacts and stop

7. If ready, execute with enforced controls

8. Capture outcome + update trust metrics



Key principle:

- **Execution must never bypass readiness.**

- Readiness must be enforceable at the API boundary (e.g., `api_permission_gate`).





## 16. Non-goals



- Action Readiness is not a replacement for:

  - authentication/authorization systems

  - endpoint security

  - human governance

  - formal safety proofs



It complements them by providing a unified “should we act?” gate.





## 17. Change management



Policy changes must be:

- versioned

- reviewed

- auditable

- tested



When a policy changes:

- log the diff

- run regression suite against a catalog of canonical action requests

- ensure deny rules remain deny rules unless explicitly approved





# End of ACTION_READINESS.md



