==============================================================================

FRANCIS — PLANES.md

Planes of operation: separation of concerns, boundaries, and cross-plane flow

==============================================================================



Purpose

-------

This document defines FRANCIS “planes” — the primary separation-of-concerns

model that keeps the system safe, explainable, testable, and evolvable.



Planes are NOT “folders”; they are *operational strata* with explicit

boundaries, invariants, and allowed transitions.



This document explains:

   - What a plane is (and what it is not)

   - The canonical plane taxonomy used across FRANCIS

   - Boundary rules: what can cross, how it crosses, and how it is audited

   - How planes map to code, config, runtime processes, and UI affordances

   - How planes interact with trust, governance, approvals, and policies

   - Implementation guidance for adding a new feature without boundary erosion



Read alongside:

   - docs/ARCHITECTURE.md

   - docs/GOVERNANCE.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/POLICIES.md

   - docs/API_PERMISSIONS.md

   - docs/CONCURRENCY.md

   - docs/CONVERSATION_CONTINUITY.md

   - docs/MEMORY.md

   - docs/WEB_ACCESS.md

   - meta/plane_map.yaml

   - meta/action_taxonomy.yaml

   - config/policies/*

   - src/francis/kernel/*

   - src/francis/governance/*

   - src/francis/llm/*

   - src/francis/agent/*

   - src/francis/telemetry/*



Design stance

------------

   - Planes are security boundaries AND engineering boundaries.

   - Cross-plane transitions must be explicit, policy-checked, and logged.

   - “Model output” is never an action. It’s a proposal that must cross gates.

   - The system must remain composable: each plane is testable in isolation.

   - Plane boundaries must be enforced in code, not just in documentation.



==============================================================================





## 1. What is a “plane”?



A **plane** is an operational domain with:

- a clear responsibility,

- defined inputs/outputs,

- explicit constraints and invariants,

- and explicit boundary-crossing rules.



A plane is intentionally conservative:

- it limits what information flows where,

- it limits what authority flows where,

- and it makes unsafe coupling harder.



### 1.1 What a plane is NOT

Planes are not:

- a module naming scheme,

- a UI grouping,

- or a “team ownership” construct.



You can have many modules per plane, and a module can *touch multiple planes*,

but it must do so through explicit interfaces that preserve the boundary rules.



### 1.2 Why planes exist (core reasons)

Planes solve predictable failure modes:



- **Security**: prevent “reasoning plane” content from becoming “execution plane” authority.

- **Safety**: enforce that tool actions go through governance gates.

- **Auditability**: ensure decisions and actions are reconstructable post-hoc.

- **Reliability**: isolate slow/unstable parts (LLMs, web) from core runtime correctness.

- **Evolvability**: allow upgrading one plane without breaking the entire system.

- **Testing**: enable unit tests per plane without needing full system integration.





## 2. Canonical plane taxonomy



FRANCIS uses the following canonical planes. Each plane includes:

- what it does,

- what it must never do,

- and where it tends to live in the codebase.



> NOTE: The exact plane set can be extended via `meta/plane_map.yaml`,

> but the invariants below should remain stable.



### 2.1 Interface Plane

**Responsibility**

- Interact with humans and external callers.

- Collect user intent, constraints, and context.

- Present system decisions, plans, and audited traces.



**Must never**

- Execute privileged actions directly.

- Store secrets in UI-visible state.

- Bypass governance for “convenience”.



**Examples**

- Chat UI (apps/chat_ui)

- API entrypoints (apps/api/main.py, src/francis/api/*)



**Boundary outputs**

- Normalized user request object (structured)

- Presentation artifacts (safe summaries, redacted traces)



---



### 2.2 Orchestration Plane

**Responsibility**

- Turn a request into a workflow: tasks, dependencies, sequencing.

- Dispatch to specialized roles/agents.

- Coordinate multi-agent collaboration and synthesis.



**Must never**

- Skip policy checks.

- Treat LLM output as authoritative execution directives.

- Mutate durable state without going through proper state/memory planes.



**Examples**

- src/francis/agent/*

- src/francis/chat/router.py

- src/francis/collective/*



**Boundary outputs**

- Task graph

- Candidate plans

- Proposed tool calls (not executed yet)



---



### 2.3 Reasoning Plane

**Responsibility**

- Produce *proposals*: plans, summaries, code drafts, hypotheses.

- Provide structured rationale and uncertainty.

- Integrate evidence (local sources, retrieved memory, web sources via policy).



**Must never**

- Execute tools by itself.

- Write to durable state directly.

- Claim to have performed external actions unless confirmed by tool traces.



**Examples**

- src/francis/llm/*

- src/francis/llm/reasoning/*

- config/models/* (routing/constraints guide selection)



**Boundary outputs**

- Proposed actions with justifications

- Structured outputs conforming to schemas

- Evidence lists and citations (when available)



---



### 2.4 Governance Plane

**Responsibility**

- Decide whether a proposed action is allowed *now* under:

  - permissions (identity/scopes/delegations),

  - policies (privacy, offensive security, sandbox, web access),

  - trust/readiness/approvals requirements,

  - environment (regulated/airgapped/production/dev).



**Must never**

- Execute tools directly (it authorizes; it doesn’t perform).

- Accept untrusted claims as proof (requires evidence).

- Store secrets in logs; must enforce redaction.



**Examples**

- src/francis/governance/*

- src/francis/credentials/scope_checker.py

- src/francis/credentials/delegation.py

- config/policies/*



**Boundary outputs**

- Allow/Deny decisions with rationale

- Approval requirements (if not satisfied)

- Redacted audit events



---



### 2.5 Execution Plane

**Responsibility**

- Perform *authorized* operations safely:

  - tool calls,

  - connector operations,

  - filesystem operations (within policy),

  - compute jobs,

  - (optionally) industrial controls (highly gated).



**Must never**

- Decide policy.

- Expand authority beyond what governance granted.

- Execute instructions sourced from untrusted text without structured authorization.



**Examples**

- src/francis/agent/executor.py

- connectors/*

- src/francis/plugin_system/execution/*

- src/francis/plugin_system/sandbox/*



**Boundary outputs**

- Tool results (raw + redacted)

- Execution traces (timing, request ids, outcome status)



---



### 2.6 Knowledge Plane

**Responsibility**

- Manage domain knowledge, sources, induced priors, and provenance.

- Support learning workflows without contaminating safety boundaries.

- Provide “what we know” with origin and freshness tracking.



**Must never**

- Accept or store secrets as “knowledge”.

- Treat web content as truth without provenance and policy checks.

- Mutate trust state directly (trust is its own plane).



**Examples**

- data/domains/*

- src/francis/domain_intelligence/*

- src/francis/internet/* (when enabled)

- data/web_knowledge/*



**Boundary outputs**

- Provenance-tagged knowledge objects

- Evidence references (not raw secret payloads)



---



### 2.7 Memory Plane

**Responsibility**

- Persist conversation continuity and durable context:

  - summaries,

  - episodic/semantic/procedural memory,

  - indexes/embeddings (as allowed),

  - retention rules and deletion completeness.



**Must never**

- Store prohibited classes of data (per data governance policy).

- Retain raw sensitive payloads beyond configured windows.

- Leak memory content into UI without redaction/classification checks.



**Examples**

- docs/MEMORY.md

- src/francis/memory/*

- data/conversations/*

- data/vectors/*



**Boundary outputs**

- Retrieved memory snippets (classified + redacted)

- Summaries with provenance and timestamps

- Vector search results (metadata-forward)



---



### 2.8 Trust Plane

**Responsibility**

- Maintain trust state, metrics, decay/growth rules, certifications.

- Provide trust-weighted decisions as inputs to governance.

- Record trust changes as auditable, explainable transitions.



**Must never**

- Override permissions (trust is not authority).

- Self-certify without evidence.

- Hide trust changes or make them non-reproducible.



**Examples**

- src/francis/trust/*

- data/trust/*

- docs/TRUST_MODEL.md



**Boundary outputs**

- Trust scores/levels with reason codes

- Certification artifacts (passed tests, evaluation summaries)



---



### 2.9 Telemetry Plane

**Responsibility**

- Provide observability:

  - structured logs,

  - audit trails,

  - metrics/tracing,

  - decision records.



**Must never**

- Log secrets or unredacted regulated payloads.

- Become a “backdoor memory store” that violates retention policies.



**Examples**

- src/francis/telemetry/*

- data/logs/*

- data/credentials/usage_logs/*



**Boundary outputs**

- Immutable audit events

- Redaction summaries

- Operator-facing diagnostics



---



### 2.10 State Plane

**Responsibility**

- Manage runtime state:

  - checkpoints,

  - snapshots,

  - realtime runtime state,

  - rollback and restore hooks.



**Must never**

- Store secrets in plaintext outside the credential vault.

- Allow ungoverned mutation of state in regulated modes.



**Examples**

- data/state/*

- src/francis/self_model/*

- src/francis/kernel/*



**Boundary outputs**

- State snapshots and diffs

- Checkpoint metadata (not secret payloads)





## 3. Plane boundaries: invariants and rules



### 3.1 The prime directive: “proposal ≠ execution”

Anything produced by the Reasoning Plane is a **proposal** until:

1) governance authorizes it, and

2) execution performs it, and

3) telemetry records it.



This is the single most important invariant in the system.



### 3.2 Boundary crossing must be explicit

Crossing planes requires:

- a structured request object (not free-form text),

- a plane transition event in telemetry,

- a policy reference (where relevant),

- and redaction classification (when payload is sensitive).



### 3.3 Default deny across authority boundaries

Any path that could confer authority must be:

- default deny,

- allowlisted,

- and audited.



Examples:

- tool execution,

- file writes outside allowed roots,

- web access,

- credential usage.



### 3.4 Data minimization at boundaries

When data crosses into:

- UI plane → must be redacted + summarized when sensitive.

- reasoning plane → must avoid secrets; use references when possible.

- telemetry plane → never record raw secrets; use hashes and metadata.



### 3.5 “No hidden couplings”

A plane must not rely on side effects from another plane unless explicitly

declared (and tested). For example:

- Reasoning must not assume a tool call succeeded until tool trace confirms it.

- Orchestration must not mutate memory unless memory plane APIs confirm write.

- Execution must not infer policy; it must consume an authorization artifact.





## 4. Plane transition lifecycle (canonical flow)



A typical safe request flows like this:



1) **Interface Plane**

   - user provides goal + constraints

   - request is normalized and classified



2) **Orchestration Plane**

   - tasks created, roles assigned

   - candidate plan(s) produced



3) **Reasoning Plane**

   - plan refined

   - tool calls proposed (structured)

   - uncertainty and risk enumerated



4) **Governance Plane**

   - permission gate: identity/scopes/delegations

   - policy checks: privacy/offensive security/sandbox/web access

   - action readiness gate: trust thresholds, approvals, environment mode

   - result: allow/deny + rationale



5) **Execution Plane**

   - executes only what was authorized

   - collects tool results



6) **Telemetry Plane**

   - records decisions, traces, results (redacted)

   - updates metric counters



7) **Memory/Knowledge/Trust Planes**

   - memory update (summaries, indexes) if allowed

   - knowledge updates (domain sources) if enabled and approved

   - trust updates (based on outcomes and evaluations)





## 5. Plane map (declarative registration)



FRANCIS uses `meta/plane_map.yaml` as the declarative source of truth describing:

- plane identities,

- invariants,

- permitted transitions,

- and enforcement hooks.



### 5.1 Illustrative plane_map.yaml shape



```yaml

# meta/plane_map.yaml

version: 1

planes:

  - plane_id: interface

    description: Human/API interaction layer

    invariants:

      - "No direct tool execution"

      - "No secrets in UI payloads"

    allowed_outbound:

      - orchestration



  - plane_id: orchestration

    description: Tasking, routing, multi-agent coordination

    invariants:

      - "Must not bypass governance"

    allowed_outbound:

      - reasoning

      - governance



  - plane_id: reasoning

    description: Proposal generation and synthesis

    invariants:

      - "Output is a proposal, not an action"

      - "No claims of execution without tool traces"

    allowed_outbound:

      - governance



  - plane_id: governance

    description: Permission + policy + trust/approval gates

    invariants:

      - "Default deny"

      - "All allow/deny decisions audited"

    allowed_outbound:

      - execution

      - interface



  - plane_id: execution

    description: Authorized tool/connector execution

    invariants:

      - "Must consume authorization artifact"

      - "Must emit tool trace + outcome"

    allowed_outbound:

      - telemetry

      - memory

      - knowledge



  - plane_id: telemetry

    description: Audit/logs/metrics

    invariants:

      - "Never log secrets"

      - "Retention rules enforced"

    allowed_outbound:

      - trust

      - interface



