# Francis 2.0 — Capabilities



> This document is the canonical capability inventory for Francis 2.0.

> It defines **what the system does**, **how it is accessed**, and **what governance gates apply**.

>

> Phase 2 rule: capabilities mature **in conical dependency order**. Higher-layer capabilities must not

> bypass lower-layer invariants (state, governance, observability).



---



## 0) Capability Contract



### 0.1 What “capability” means in Francis

A **capability** is a user- or system-invocable function that:

- has a defined interface (API/WS/CLI/UI)

- has defined state surfaces (ledger, artifacts, queues, config)

- emits observable traces (logs + audi# Francis 2.0 — Capabilities



> This document is the canonical capability inventory for Francis 2.0.

> It defines **what the system does**, **how it is accessed**, and **what governance gates apply**.

>

> Phase 2 rule: capabilities mature **in conical dependency order**. Higher-layer capabilities must not

> bypass lower-layer invariants (state, governance, observability).



---



## 0) Capability Contract



### 0.1 What “capability” means in Francis

A **capability** is a user- or system-invocable function that:

- has a defined interface (API/WS/CLI/UI)

- has defined state surfaces (ledger, artifacts, queues, config)

- emits observable traces (logs + audit)

- is governed by policy (trust level, approvals, permissions)



### 0.2 Non-negotiable invariants

1) **Determinism**

   - Same inputs + same config + same state ⇒ behavior is repeatable and explainable.

2) **Observability first**

   - Every meaningful action is logged (structured) and auditable.

3) **Policy before power**

   - Actions that can change the world are gated by governance.

4) **No secrets in the browser**

   - UI sees only metadata + references. Never raw keys/tokens/passwords.

5) **Backwards compatibility**

   - Public contracts evolve via additive changes or explicit versioning.



---



## 1) Runtime Surfaces (How Francis is Operated)



Francis exposes four primary runtime surfaces:



### 1.1 API Service (Backend)

- **Role:** authoritative control plane and data plane for core operations

- **Interfaces:** HTTP + WebSocket

- **Responsibilities:**

  - state access (ledger, approvals, credentials metadata, domains)

  - governance enforcement (approval + trust gating)

  - audit emission

  - tool/agent orchestration endpoints (as implemented)



### 1.2 Daemon (Autonomous Loop)

- **Role:** scheduler/orchestrator for background tasks (timed ticks, maintenance, watchers)

- **Responsibilities:**

  - periodic polling/tick model

  - dispatching work to workers (directly or via queue)

  - emitting heartbeat and operator-grade logs

  - fail-fast behavior under strict modes



### 1.3 Workers (Execution Pool)

- **Role:** bounded-concurrency execution engines for background work

- **Responsibilities:**

  - execute jobs/tasks safely

  - emit job lifecycle telemetry

  - respect governance constraints (server-side enforcement)



### 1.4 Chat UI (Operator Console)

- **Role:** human control interface for chat, approvals, continuity inspection, dashboards

- **Responsibilities:**

  - real-time chat via WS

  - view continuity ledger timeline

  - manage approvals (decision submission)

  - view system dashboards (as implemented)



---



## 2) Governance Model (Applies to All Capabilities)



Francis is built for **autonomy with constraints**. Governance is not optional.



### 2.1 Autonomy levels (operational modes)

These represent *policy posture*, not just scheduling:



- **Safe**

  - executes non-destructive tasks without prompts

  - examples: health reports, index maintenance, cache cleanup (bounded)

- **Normal**

  - can execute workflows but may require a single confirmation per workflow or per category

  - examples: provisioning a connector, running a multi-step automation

- **Critical**

  - requires explicit approval for destructive/high-risk actions

  - examples: live trading, credential revocation, industrial actuation, external web actions (if configured)



> Note: exact autonomy wiring is implemented in governance layer; this document describes the intended control semantics.



### 2.2 Approvals

- **Concept:** any high-risk action becomes an approval item.

- **Operator flow:**

  1) request created (reason + action + context)

  2) pending approval appears in UI

  3) operator approves/rejects/emergency

  4) decision is audited and becomes enforceable state



### 2.3 Trust

- **Concept:** a durable trust state influences what Francis is allowed to do.

- **Constraints:**

  - trust should be *explainable* (why a level changed)

  - trust changes should be auditable

  - trust should never silently grant high-risk permissions



### 2.4 Audit

Every meaningful capability must emit:

- who/what/why (actor + intent + scope)

- inputs/outputs (redacted when necessary)

- timestamps + correlation identifiers where feasible



---



## 3) Capability Inventory (By Cone Layer)



Each capability is listed with:

- **Maturity:** Now / Stabilizing / Planned

- **Interfaces:** where it is accessed

- **State:** durable artifacts involved

- **Governance:** required gates

- **Observability:** what must be emitted



---



# Layer 0 — Foundation



## 3.0.1 Repository Hygiene \& Contracts

**Maturity:** Now  

**Interfaces:** tooling + pre-commit  

**State:** `.editorconfig`, `.gitignore`, `.pre-commit-config.yaml`, `.env.example`  

**Governance:** N/A  

**Observability:** N/A (tooling output)



**What it provides**

- consistent formatting \& line endings across languages

- safe ignore strategy (no secrets/runtime state committed)

- local quality gates (fast checks at commit, heavier checks at push)



---



# Layer 1 — Kernel



## 3.1.1 Process Entrypoints (API / Daemon / Workers)

**Maturity:** Now (launcher-level)  

**Interfaces:** python entrypoints in `apps/`  

**State:** logs, configuration resolution  

**Governance:** mode-dependent  

**Observability:**

- startup banner (version, profile, mode, pid, python, config summary)

- clear exit codes for failure classification



**What it provides**

- deterministic startup behavior (CLI > ENV > defaults)

- safe logging bootstrap with optional delegation to system logging module

- forward-compatible runner resolution and signature-safe kwarg forwarding



---



# Layer 2 — Memory



## 3.2.1 Continuity Ledger (Conversation/Action Timeline)

**Maturity:** Now / Stabilizing  

**Interfaces:** API + UI “Ledger Timeline”  

**State:** append-only ledger artifacts (e.g., JSONL)  

**Governance:** read allowed broadly; writes are internal/governed  

**Observability:** ledger write emits audit + log



**What it provides**

- durable timeline of conversation + actions

- supports operator inspection and debugging

- supports governance narratives (“why did Francis do X?”)



> UI contract expectation: a ledger listing endpoint exists (or will exist) that returns a bounded list of entries.



---



# Layer 3 — Governance



## 3.3.1 Approvals (Operator Decision Queue)

**Maturity:** Now / Stabilizing  

**Interfaces:** UI approvals panel + API endpoints  

**State:** approvals queue + decision records  

**Governance:** approvals are themselves governance machinery  

**Observability:** decision emits audit record + log



**What it provides**

- enforceable gating for high-risk actions

- operator-visible pending queue

- decision submission with status feedback



## 3.3.2 Credential Governance (Metadata-Only)

**Maturity:** Stabilizing  

**Interfaces:** credential manager client (UI) + API endpoints  

**State:** credential vault DB (server-side), metadata indexes, delegation records  

**Governance:** always approval/policy gated for creation/revocation  

**Observability:** every credential lifecycle event is audited



**Hard rule**

- secrets never reach the browser

- UI only sees references, labels, hints, fingerprints, scopes, and status



---



# Layer 4 — LLM Subsystem



## 3.4.1 Model Routing \& Provider Abstraction

**Maturity:** Planned (until contracts finalize)  

**Interfaces:** backend internal APIs + config  

**State:** provider configs, routing config  

**Governance:** tool usage gated, prompt policies enforced  

**Observability:** model selection, tool call intent, and failures logged/audited



**What it will provide**

- routing by task/classifier (chat vs reasoning vs tools)

- deterministic fallbacks (timeouts, provider down, model missing)

- strict tool invocation contracts (schema validated)



---



# Layer 5 — Chat



## 3.5.1 Real-Time Chat (WebSocket)

**Maturity:** Now / Stabilizing  

**Interfaces:** chat UI + WS endpoint  

**State:** conversation state + ledger entries  

**Governance:** governed tools/actions invoked through chat must be gated  

**Observability:**

- WS connection lifecycle (connect/disconnect/reconnect)

- message send/receive events (redacted where needed)



**UI expectations**

- reconnection backoff + jitter

- defensive parsing of plain text vs JSON payloads

- status visibility for operator



---



# Layer 6 — Plugins



## 3.6.1 Plugin Execution (Sandboxed, Audited)

**Maturity:** Planned  

**Interfaces:** API + daemon/workers + UI plugin browser  

**State:** plugin registry, plugin artifacts, execution logs, audit  

**Governance:** approvals/trust required depending on plugin risk class  

**Observability:** every execution emits audit and artifacts written to controlled directories



**What it will provide**

- deterministic plugin discovery/registration

- explicit plugin manifest schema

- safe artifact handling (no leaking secrets)

- governance integration (risk-based gating)



---



# Layer 7 — Higher Systems



These are powerful capabilities that must *never* outrun governance.



## 3.7.1 Web Learning Monitor (Governed Web Access)

**Maturity:** Planned / Stabilizing (depends on backend policy wiring)  

**Interfaces:** UI dashboard + backend policy engine  

**State:** browsing logs, approvals, cached pages (if enabled)  

**Governance:** explicit policy + approval gates  

**Observability:** every fetch logged/audited (URL, reason, result, redactions)



## 3.7.2 Domain Workbench (Domain Registry + Specialization)

**Maturity:** Stabilizing  

**Interfaces:** UI + API  

**State:** domain metadata registry, specialization manifests  

**Governance:** domain creation/update/delete governed by policy  

**Observability:** all changes audited (who changed what and why)



> Domain update/delete are explicitly supported as first-class capabilities when backend endpoints exist.



## 3.7.3 Federation Hub (Multi-Instance Coordination)

**Maturity:** Planned  

**Interfaces:** UI + API  

**State:** federation instance registry, consensus logs, discovery data  

**Governance:** strict gating; federation affects trust boundaries  

**Observability:** consensus logs append-only + auditable



## 3.7.4 Industrial Control (Digital Twins + Industrial Ops)

**Maturity:** Planned (safety-critical)  

**Interfaces:** UI + API + workers  

**State:** simulation outputs, digital twin models, control logs  

**Governance:** **Critical-only** by default; approvals required for actuation  

**Observability:** control actions emit strong audit records + safety checks results



---



## 4) Capability Interfaces (Practical Contracts)



This section defines the *shape* of interfaces without locking implementation prematurely.



### 4.1 HTTP (REST-ish)

- **Reads:** list/get endpoints return bounded, paginated responses where relevant

- **Writes:** create/update/delete endpoints require:

  - actor identity (implicit or explicit)

  - reason/justification for governance

  - audit emission on success/failure



### 4.2 WebSocket (Chat)

Minimum expectations:

- message event: role + content + optional ts

- error/status events: operator-readable message + optional code/context

- server may send plain text or JSON; client must parse defensively



### 4.3 UI (Operator Console)

Operator console must:

- never store secrets

- clearly show connection state + failures

- present approvals with clear “why” and decision controls

- offer ledger inspection to debug reality



---



## 5) Observability Guarantees (Operator Grade)



### 5.1 Logs

Every capability should log:

- component name

- action name

- correlation id (when available)

- duration/latency for remote calls

- failure classification (retryable vs non-retryable)



### 5.2 Audit

Audit should capture:

- actor (human/system)

- intent/reason

- inputs/outputs (redacted)

- scope (domain, workspace, federation instance, etc.)

- decision gating results (approval id, trust level)



### 5.3 “Explainability”

Where a capability makes a decision (routing, tool selection, risk scoring):

- store the decision and rationale in a retrievable form

- avoid black-box behavior in critical paths



---



## 6) Security Posture (Hard Rules)



### 6.1 Secrets

- **Never** expose raw secrets to UI or logs.

- UI only receives:

  - reference ids

  - redacted hints

  - fingerprints

  - status + timestamps

  - scope metadata



### 6.2 Default bind posture

- dev servers bind to loopback unless explicitly configured

- reverse proxy / TLS termination preferred for production



### 6.3 High-risk actions

Examples:

- credential revoke

- web access (if enabled)

- industrial actuation

- federated commands



These must be:

- approval gated (policy-defined)

- auditable with strong context

- rate-limited where appropriate (backend responsibility)



---



## 7) Build-Forward Notes (Avoiding Future Rewrites)



The system is explicitly shaped to avoid the most common long-lived autonomy failures:



1) **Contract drift between UI and backend**

   - schemas and defensive parsing are first-class

2) **Governance bolted-on too late**

   - approvals/trust/audit are treated as core, not “features”

3) **Hidden state corruption**

   - append-only logs and explicit migrations preferred

4) **Unsafe browser patterns**

   - zero-secret UI posture is mandatory

5) **Overcoupled internals**

   - entrypoints adapt to runner evolution via signature filtering



---



## 8) What “Done” Means for a Capability



A capability is considered production-grade when it has:

- explicit interface contract

- safe defaults

- governance gates (as applicable)

- clear audit/log emissions

- predictable failure modes and operator guidance

- no secrets leakage path



---



## Appendix A — Common Capability Maturity Labels



- **Now:** in active operation and relied on

- **Stabilizing:** implemented but contract surface may still tighten

- **Planned:** named and constrained, but not implemented yet



---



## Appendix B — Operator Checklist (Minimal)



A minimal operator workflow should always be possible:

- start API + daemon + workers cleanly

- use UI to:

  - connect chat

  - see ledger timeline

  - view pending approvals and decide

  - detect errors and fix misconfiguration quickly

t)

- is governed by policy (trust level, approvals, permissions)



### 0.2 Non-negotiable invariants

1) **Determinism**

   - Same inputs + same config + same state ⇒ behavior is repeatable and explainable.

2) **Observability first**

   - Every meaningful action is logged (structured) and auditable.

3) **Policy before power**

   - Actions that can change the world are gated by governance.

4) **No secrets in the browser**

   - UI sees only metadata + references. Never raw keys/tokens/passwords.

5) **Backwards compatibility**

   - Public contracts evolve via additive changes or explicit versioning.



---



## 1) Runtime Surfaces (How Francis is Operated)



Francis exposes four primary runtime surfaces:



### 1.1 API Service (Backend)

- **Role:** authoritative control plane and data plane for core operations

- **Interfaces:** HTTP + WebSocket

- **Responsibilities:**

  - state access (ledger, approvals, credentials metadata, domains)

  - governance enforcement (approval + trust gating)

  - audit emission

  - tool/agent orchestration endpoints (as implemented)



### 1.2 Daemon (Autonomous Loop)

- **Role:** scheduler/orchestrator for background tasks (timed ticks, maintenance, watchers)

- **Responsibilities:**

  - periodic polling/tick model

  - dispatching work to workers (directly or via queue)

  - emitting heartbeat and operator-grade logs

  - fail-fast behavior under strict modes



### 1.3 Workers (Execution Pool)

- **Role:** bounded-concurrency execution engines for background work

- **Responsibilities:**

  - execute jobs/tasks safely

  - emit job lifecycle telemetry

  - respect governance constraints (server-side enforcement)



### 1.4 Chat UI (Operator Console)

- **Role:** human control interface for chat, approvals, continuity inspection, dashboards

- **Responsibilities:**

  - real-time chat via WS

  - view continuity ledger timeline

  - manage approvals (decision submission)

  - view system dashboards (as implemented)



---



## 2) Governance Model (Applies to All Capabilities)



Francis is built for **autonomy with constraints**. Governance is not optional.



### 2.1 Autonomy levels (operational modes)

These represent *policy posture*, not just scheduling:



- **Safe**

  - executes non-destructive tasks without prompts

  - examples: health reports, index maintenance, cache cleanup (bounded)

- **Normal**

  - can execute workflows but may require a single confirmation per workflow or per category

  - examples: provisioning a connector, running a multi-step automation

- **Critical**

  - requires explicit approval for destructive/high-risk actions

  - examples: live trading, credential revocation, industrial actuation, external web actions (if configured)



> Note: exact autonomy wiring is implemented in governance layer; this document describes the intended control semantics.



### 2.2 Approvals

- **Concept:** any high-risk action becomes an approval item.

- **Operator flow:**

  1) request created (reason + action + context)

  2) pending approval appears in UI

  3) operator approves/rejects/emergency

  4) decision is audited and becomes enforceable state



### 2.3 Trust

- **Concept:** a durable trust state influences what Francis is allowed to do.

- **Constraints:**

  - trust should be *explainable* (why a level changed)

  - trust changes should be auditable

  - trust should never silently grant high-risk permissions



### 2.4 Audit

Every meaningful capability must emit:

- who/what/why (actor + intent + scope)

- inputs/outputs (redacted when necessary)

- timestamps + correlation identifiers where feasible



---



## 3) Capability Inventory (By Cone Layer)



Each capability is listed with:

- **Maturity:** Now / Stabilizing / Planned

- **Interfaces:** where it is accessed

- **State:** durable artifacts involved

- **Governance:** required gates

- **Observability:** what must be emitted



---



# Layer 0 — Foundation



## 3.0.1 Repository Hygiene \& Contracts

**Maturity:** Now  

**Interfaces:** tooling + pre-commit  

**State:** `.editorconfig`, `.gitignore`, `.pre-commit-config.yaml`, `.env.example`  

**Governance:** N/A  

**Observability:** N/A (tooling output)



**What it provides**

- consistent formatting \& line endings across languages

- safe ignore strategy (no secrets/runtime state committed)

- local quality gates (fast checks at commit, heavier checks at push)



---



# Layer 1 — Kernel



## 3.1.1 Process Entrypoints (API / Daemon / Workers)

**Maturity:** Now (launcher-level)  

**Interfaces:** python entrypoints in `apps/`  

**State:** logs, configuration resolution  

**Governance:** mode-dependent  

**Observability:**

- startup banner (version, profile, mode, pid, python, config summary)

- clear exit codes for failure classification



**What it provides**

- deterministic startup behavior (CLI > ENV > defaults)

- safe logging bootstrap with optional delegation to system logging module

- forward-compatible runner resolution and signature-safe kwarg forwarding



---



# Layer 2 — Memory



## 3.2.1 Continuity Ledger (Conversation/Action Timeline)

**Maturity:** Now / Stabilizing  

**Interfaces:** API + UI “Ledger Timeline”  

**State:** append-only ledger artifacts (e.g., JSONL)  

**Governance:** read allowed broadly; writes are internal/governed  

**Observability:** ledger write emits audit + log



**What it provides**

- durable timeline of conversation + actions

- supports operator inspection and debugging

- supports governance narratives (“why did Francis do X?”)



> UI contract expectation: a ledger listing endpoint exists (or will exist) that returns a bounded list of entries.



---



# Layer 3 — Governance



## 3.3.1 Approvals (Operator Decision Queue)

**Maturity:** Now / Stabilizing  

**Interfaces:** UI approvals panel + API endpoints  

**State:** approvals queue + decision records  

**Governance:** approvals are themselves governance machinery  

**Observability:** decision emits audit record + log



**What it provides**

- enforceable gating for high-risk actions

- operator-visible pending queue

- decision submission with status feedback



## 3.3.2 Credential Governance (Metadata-Only)

**Maturity:** Stabilizing  

**Interfaces:** credential manager client (UI) + API endpoints  

**State:** credential vault DB (server-side), metadata indexes, delegation records  

**Governance:** always approval/policy gated for creation/revocation  

**Observability:** every credential lifecycle event is audited



**Hard rule**

- secrets never reach the browser

- UI only sees references, labels, hints, fingerprints, scopes, and status



---



# Layer 4 — LLM Subsystem



## 3.4.1 Model Routing \& Provider Abstraction

**Maturity:** Planned (until contracts finalize)  

**Interfaces:** backend internal APIs + config  

**State:** provider configs, routing config  

**Governance:** tool usage gated, prompt policies enforced  

**Observability:** model selection, tool call intent, and failures logged/audited



**What it will provide**

- routing by task/classifier (chat vs reasoning vs tools)

- deterministic fallbacks (timeouts, provider down, model missing)

- strict tool invocation contracts (schema validated)



---



# Layer 5 — Chat



## 3.5.1 Real-Time Chat (WebSocket)

**Maturity:** Now / Stabilizing  

**Interfaces:** chat UI + WS endpoint  

**State:** conversation state + ledger entries  

**Governance:** governed tools/actions invoked through chat must be gated  

**Observability:**

- WS connection lifecycle (connect/disconnect/reconnect)

- message send/receive events (redacted where needed)



**UI expectations**

- reconnection backoff + jitter

- defensive parsing of plain text vs JSON payloads

- status visibility for operator



---



# Layer 6 — Plugins



## 3.6.1 Plugin Execution (Sandboxed, Audited)

**Maturity:** Planned  

**Interfaces:** API + daemon/workers + UI plugin browser  

**State:** plugin registry, plugin artifacts, execution logs, audit  

**Governance:** approvals/trust required depending on plugin risk class  

**Observability:** every execution emits audit and artifacts written to controlled directories



**What it will provide**

- deterministic plugin discovery/registration

- explicit plugin manifest schema

- safe artifact handling (no leaking secrets)

- governance integration (risk-based gating)



---



# Layer 7 — Higher Systems



These are powerful capabilities that must *never* outrun governance.



## 3.7.1 Web Learning Monitor (Governed Web Access)

**Maturity:** Planned / Stabilizing (depends on backend policy wiring)  

**Interfaces:** UI dashboard + backend policy engine  

**State:** browsing logs, approvals, cached pages (if enabled)  

**Governance:** explicit policy + approval gates  

**Observability:** every fetch logged/audited (URL, reason, result, redactions)



## 3.7.2 Domain Workbench (Domain Registry + Specialization)

**Maturity:** Stabilizing  

**Interfaces:** UI + API  

**State:** domain metadata registry, specialization manifests  

**Governance:** domain creation/update/delete governed by policy  

**Observability:** all changes audited (who changed what and why)



> Domain update/delete are explicitly supported as first-class capabilities when backend endpoints exist.



## 3.7.3 Federation Hub (Multi-Instance Coordination)

**Maturity:** Planned  

**Interfaces:** UI + API  

**State:** federation instance registry, consensus logs, discovery data  

**Governance:** strict gating; federation affects trust boundaries  

**Observability:** consensus logs append-only + auditable



## 3.7.4 Industrial Control (Digital Twins + Industrial Ops)

**Maturity:** Planned (safety-critical)  

**Interfaces:** UI + API + workers  

**State:** simulation outputs, digital twin models, control logs  

**Governance:** **Critical-only** by default; approvals required for actuation  

**Observability:** control actions emit strong audit records + safety checks results



---



## 4) Capability Interfaces (Practical Contracts)



This section defines the *shape* of interfaces without locking implementation prematurely.



### 4.1 HTTP (REST-ish)

- **Reads:** list/get endpoints return bounded, paginated responses where relevant

- **Writes:** create/update/delete endpoints require:

  - actor identity (implicit or explicit)

  - reason/justification for governance

  - audit emission on success/failure



### 4.2 WebSocket (Chat)

Minimum expectations:

- message event: role + content + optional ts

- error/status events: operator-readable message + optional code/context

- server may send plain text or JSON; client must parse defensively



### 4.3 UI (Operator Console)

Operator console must:

- never store secrets

- clearly show connection state + failures

- present approvals with clear “why” and decision controls

- offer ledger inspection to debug reality



---



## 5) Observability Guarantees (Operator Grade)



### 5.1 Logs

Every capability should log:

- component name

- action name

- correlation id (when available)

- duration/latency for remote calls

- failure classification (retryable vs non-retryable)



### 5.2 Audit

Audit should capture:

- actor (human/system)

- intent/reason

- inputs/outputs (redacted)

- scope (domain, workspace, federation instance, etc.)

- decision gating results (approval id, trust level)



### 5.3 “Explainability”

Where a capability makes a decision (routing, tool selection, risk scoring):

- store the decision and rationale in a retrievable form

- avoid black-box behavior in critical paths



---



## 6) Security Posture (Hard Rules)



### 6.1 Secrets

- **Never** expose raw secrets to UI or logs.

- UI only receives:

  - reference ids

  - redacted hints

  - fingerprints

  - status + timestamps

  - scope metadata



### 6.2 Default bind posture

- dev servers bind to loopback unless explicitly configured

- reverse proxy / TLS termination preferred for production



### 6.3 High-risk actions

Examples:

- credential revoke

- web access (if enabled)

- industrial actuation

- federated commands



These must be:

- approval gated (policy-defined)

- auditable with strong context

- rate-limited where appropriate (backend responsibility)



---



## 7) Build-Forward Notes (Avoiding Future Rewrites)



The system is explicitly shaped to avoid the most common long-lived autonomy failures:



1) **Contract drift between UI and backend**

   - schemas and defensive parsing are first-class

2) **Governance bolted-on too late**

   - approvals/trust/audit are treated as core, not “features”

3) **Hidden state corruption**

   - append-only logs and explicit migrations preferred

4) **Unsafe browser patterns**

   - zero-secret UI posture is mandatory

5) **Overcoupled internals**

   - entrypoints adapt to runner evolution via signature filtering



---



## 8) What “Done” Means for a Capability



A capability is considered production-grade when it has:

- explicit interface contract

- safe defaults

- governance gates (as applicable)

- clear audit/log emissions

- predictable failure modes and operator guidance

- no secrets leakage path



---



## Appendix A — Common Capability Maturity Labels



- **Now:** in active operation and relied on

- **Stabilizing:** implemented but contract surface may still tighten

- **Planned:** named and constrained, but not implemented yet



---



## Appendix B — Operator Checklist (Minimal)



A minimal operator workflow should always be possible:

- start API + daemon + workers cleanly

- use UI to:

  - connect chat

  - see ledger timeline

  - view pending approvals and decide

  - detect errors and fix misconfiguration quickly



