==============================================================================

FRANCIS — ARCHITECTURE.md

System architecture, runtime topology, and request→action lifecycle

==============================================================================



Purpose

-------

This document is the canonical high-level architecture reference for FRANCIS.

It explains:

   - Core subsystems and their responsibilities

   - Runtime topology (API, daemon, workers, UI)

   - The end-to-end flow: input → reasoning → governance → tools → artifacts

   - Data layout under /data and how persistence is managed

   - Extensibility via connectors, plugins, and specializations

   - Deployment profiles (dev/prod/regulated/airgapped/federated)



Read alongside:

   - docs/PLANES.md

   - docs/POLICIES.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/API_PERMISSIONS.md

   - docs/CONCURRENCY.md

   - docs/CONVERSATION_CONTINUITY.md

   - docs/WEB_ACCESS.md

   - docs/INTEGRATION_GUIDE.md



Key code references:

   - apps/api/main.py

   - src/francis/api/app.py

   - src/francis/kernel/orchestrator.py

   - src/francis/governance/*

   - src/francis/agent/*

   - src/francis/llm/*

   - src/francis/plugin_system/*

   - src/francis/api/routes/ingest.py

   - src/francis/ingest/*

   - src/francis/chat/continuity/*

   - src/francis/memory/*

   - connectors/*



Design stance:

   - The model is not a security boundary

   - Default deny for tool actions; explicit delegation + approvals for risk

   - Everything important is auditable: decisions, evidence, tool calls

   - Separate "thinking" from "acting" with hard gates in between



==============================================================================





## 0. Architecture in one page



FRANCIS is an **agentic orchestration system** with a strict separation between:

- **Cognition** (planning and synthesis),

- **Governance** (permission + trust + readiness),

- **Execution** (sandboxed tool calls),

- **Memory** (provenance-based storage and retrieval),

- **Telemetry** (auditability, metrics, incident traceability).



The system is designed to run in multiple operational modes:

- **Local dev** (fast iteration, permissive logging)

- **Production** (stable, conservative)

- **Regulated / safety-critical** (strict approvals, narrow scopes)

- **Airgapped** (no external web)

- **Federated** (multiple instances share knowledge under trust controls)





## 1. System boundaries and invariants



### 1.1 Hard invariants (must always hold)

1) **Policy beats model output**

   - No matter what the model suggests, governance gates decide what is allowed.

2) **Default deny for risky tool actions**

   - Especially write/destructive/external communication.

3) **Secrets never enter model context**

   - The model works with handles, references, redacted summaries, or bounded views.

4) **All tool decisions are auditable**

   - Allow/deny is logged with a reason code and policy snapshot.

5) **Provenance is required for persistent knowledge**

   - Persistent memory must contain source metadata, validation status, and confidence.

6) **Imported code is evidence before capability**

   - Repositories, source folders, and third-party packages may be indexed as
     provenance-backed sources, but they do not become executable authority until
     governance, identity, sandboxing, and receipts are bound to a real lab path.
   - Operator UI readback may expose source records, repo maps, risk signals,
     candidates, and Lab blockers; it must not imply buildable, runnable, or
     validated capability without the governed Lab path.
   - Runner-readiness records may enumerate missing sandbox and runner controls,
     but they are not sandbox enforcement, runner binding, approval consumption,
     or execution authority.
   - Runner-binding records may enumerate missing runner binding and
     execution-receipt sink controls, but they are not live runner bindings,
     receipt-sink bindings, approval consumption, or execution authority.
   - Runner-enforcement records may verify missing runner identity, policy,
     capture, receipt-write, and approval-consumption checks, but they are not
     live policy enforcement, receipt writes, approval consumption, or execution
     authority.
   - Approval-consumption handoff records may bind approved exact-action evidence
     to runner-enforcement readback, but they are not approval consumption, live
     runner enforcement, receipt-sink binding, or execution authority.
   - Execution-receipt sink reservation records may reserve a future execution
     receipt id/path, but they are not receipt-sink binding, execution receipt
     prewrite, execution receipt final write, or execution authority.
   - Runner command allowlist binding records may project exact-action command
     plans against missing allowlist controls, but they are not live command
     allowlists, command execution bindings, approval consumption, or execution
     authority.
   - Runner command allowlist declaration records may derive deterministic
     allowlist entries from exact-action command plans, but they are not live
     allowlist bindings, runner bindings, command execution, approval
     consumption, or execution authority.
   - Runner command allowlist enforcement preflight records may check declared
     exact-action entries against missing live runner, allowlist-binding, and
     receipt-write controls, but they are not live allowlist enforcement, runner
     binding, command execution, approval consumption, receipt-sink writes, or
     execution authority.
   - Runner sandbox readiness records may check workspace evidence and missing
     sandbox controls, but they are not live sandboxes, live runner bindings,
     readonly source mounts, command execution, approval consumption,
     receipt-sink writes, or execution authority.
   - Sandbox provider contract records may declare the future provider boundary
     and required enforcement controls after sandbox readiness, but they are not
     live provider bindings, sandbox enforcement, runner bindings, process
     launches, command execution, approval consumption, receipt-sink writes, or
     execution authority.
   - Sandbox provider binding preflight records may declare the future
     provider-selection and provider-binding checklist after the provider
     contract, but they are not provider selection, provider binary/service
     verification, provider policy binding, live provider binding, sandbox
     enforcement, process launch, command execution, approval consumption, or
     execution authority.
   - Sandbox provider selection preflight records may record requested provider
     kind, local provider reference metadata, and optional provider policy
     manifest metadata after the provider-binding preflight, but they are not
     provider binary/service verification, live provider binding, sandbox
     enforcement, process launch, service query, container launch, command
     execution, approval consumption, or execution authority.
   - Sandbox provider verifier preflight records may capture static provider
     reference fingerprints, sanitized policy-manifest hashes, declared version
     evidence, and Francis verifier identity after provider selection, but they
     are not provider runtime probe success, live provider binding, sandbox
     enforcement, process launch, service query, container launch, command
     execution, approval consumption, or execution authority.
   - Sandbox provider runtime-probe preflight records may declare future
     provider probe authorization, timeout, network-blocking,
     workspace-isolation, receipt, and repository-execution separation controls
     after static verifier readback, but they are not provider runtime probe
     success, provider binary execution, service query, container launch, live
     provider binding, sandbox enforcement, command execution, approval
     consumption, or execution authority.
   - Sandbox provider runtime-probe harness preflight records may declare future
     probe runner, sandbox, service-query guard, output capture, and kill-switch
     controls after runtime-probe contract readback, but they are not provider
     runtime probe success, provider binary execution, service query, container
     launch, live provider binding, sandbox enforcement, execution receipt
     writing, command execution, approval consumption, or execution authority.
   - Sandbox provider runtime-probe runner readiness records may declare the
     future probe-runner interface and missing runner implementation, identity,
     policy, sandbox, network-block, workspace-isolation, timeout,
     output-capture, kill-switch, and receipt-contract controls after harness
     readback, but they are not provider runtime probe success, provider binary
     execution, service query, process launch, container launch, live provider
     binding, sandbox enforcement, execution receipt writing, command execution,
     approval consumption, or execution authority.
   - Sandbox provider runtime-probe runner binding preflight records may declare
     the future probe-runner binding contract and missing live runner,
     runtime-probe binding, sandbox, network, timeout, output-capture,
     kill-switch, and receipt controls after runner-readiness readback, but they
     are not live runner binding, provider runtime probe success, provider
     binary execution, service query, process launch, container launch, live
     provider binding, sandbox enforcement, execution receipt writing, command
     execution, approval consumption, or execution authority.
   - Sandbox provider runtime-probe runner enforcement preflight records may
     declare the future probe-runner enforcement contract and missing live
     enforcement, runner binding, runtime-probe binding, provider runtime probe,
     sandbox, network, timeout, output-capture, kill-switch, and receipt
     controls after runner-binding readback, but they are not live runner
     enforcement, provider runtime probe success, provider binary execution,
     service query, process launch, container launch, live provider binding,
     sandbox enforcement, execution receipt writing, command execution,
     approval consumption, or execution authority.
   - Sandbox provider runtime-probe execution-boundary records may compose
     run-boundary and probe-runner enforcement readbacks to declare the future
     provider-probe execution gate, but they are not provider runtime probe
     success, provider binary execution, service query, process launch,
     container launch, live provider binding, sandbox enforcement, execution
     receipt writing, approval consumption, command execution, or execution
     authority.
   - Sandbox provider runtime-probe refusal records may write receipts when a
     provider probe is requested before governed probe execution exists, but
     they are not provider runtime probe success, provider binary execution,
     service query, process launch, container launch, live provider binding,
     sandbox enforcement, execution receipt writing, approval consumption,
     command execution, or execution authority.
  - Sandbox provider runtime-probe approval-request records may queue a pending
    exact-action approval for future provider probing, but they are not
    approval decisions, approval consumption, provider runtime probe success,
    provider binary execution, service query, process launch, container
    launch, live provider binding, sandbox enforcement, execution receipt
    writing, command execution, or execution authority.
  - Sandbox provider runtime-probe approval-consumption records may consume an
    approved exact-action provider-probe approval once, but they are not
    provider runtime probe success, provider binary execution, service query,
    process launch, container launch, live provider binding, sandbox
    enforcement, execution receipt writing, command execution, validation,
    promotion, or execution authority.
  - Sandbox provider runtime-probe invocation-boundary records may bind consumed
    provider-probe approval evidence to execution-boundary readback and enumerate
    the missing future runner controls, but they are not provider runtime probe
    success, provider binary execution, service query, process launch, container
    launch, live runner binding, sandbox enforcement, execution receipt writing,
    command execution, validation, promotion, or execution authority.
  - Sandbox provider runtime-probe runner pre-execution-boundary records may bind
    a recorded invocation boundary to the still-missing live runner identity,
    policy, sandbox policy, sandbox binding/enforcement, network block, timeout,
    output capture, kill switch, and execution receipt writer controls, but they
    are not provider runtime probe success, provider binary execution, service
    query, process launch, container launch, live runner binding, sandbox
    enforcement, execution receipt writing, command execution, validation,
    promotion, or execution authority.
  - Sandbox provider runtime-probe runner control-binding records may record
    future runner identity, policy, sandbox policy, network block, timeout,
    output capture, kill switch, and execution receipt writer bindings as
    governance evidence, but they are not live runner binding, sandbox
    enforcement, provider runtime probe success, provider binary execution,
    service query, process launch, container launch, execution receipt writing,
    command execution, validation, promotion, or execution authority.
  - Sandboxed rebuild/run/test boundary records may record the future governed
    install/build/run/test/validate boundary after runner control-binding
    evidence, but they are not live execution approval, live runner binding,
    sandbox enforcement, process launch, container launch, command execution,
    repository code execution, network access, repository write, execution
    receipt writing, validation, promotion, or execution authority.
  - Sandboxed rebuild/run/test approval-request records may queue pending
    exact-action operator approval for future governed repository execution, but
    they are not approval decisions, approval consumption, live runner binding,
    sandbox enforcement, process launch, container launch, command execution,
    repository code execution, network access, repository write, execution
    receipt writing, validation, promotion, or execution authority.
  - Sandboxed rebuild/run/test approval-consumption records may consume an
    approved exact-action sandboxed rebuild/run/test approval once as
    governance evidence, but they are not live runner binding, sandbox
    enforcement, process launch, container launch, command execution,
    repository code execution, install/build/test execution, network access,
    repository write, execution receipt writing, validation, promotion, or
    execution authority.
  - Sandboxed rebuild/run/test runner-binding preflight records may record static
    local provider reference and policy-manifest metadata after approval
    consumption, but they are not live runner binding, sandbox enforcement,
    provider execution, provider service query, command execution, execution
    receipt writing, validation, promotion, or execution authority.
  - Sandboxed rebuild/run/test sandbox-policy preflight records may record
    conservative no-network, read-only-source, no-write, no-destructive-action,
    no-secret-storage, command-disabled policy evidence after runner-binding
    readback, but they are not live sandbox binding, sandbox enforcement,
    command allowlist binding, execution receipt writer binding, process
    launch, repository command execution, install/build/test execution,
    validation, promotion, or execution authority.
  - Execution receipt write readiness records may check reserved execution
     receipt ids/paths and missing prewrite/final-write controls, but they are
     not receipt schema binding, execution receipt prewrite, execution receipt
     final write, command execution, approval consumption, or execution
     authority.
   - Execution receipt prewrite binding records may bind the future
     `lab.execution.run` receipt schema plus prewrite/final-write contracts, but
     they are not writer implementations and may not prewrite, finalize, or
     otherwise write execution receipts.
   - Execution receipt writer preflight records may declare reserved sink path,
     temp-file/replace, and redaction controls for a future writer, but they are
     not writer implementations and may not prewrite, finalize, or otherwise
     write execution receipts.
  - Synthetic execution receipt records may prewrite/finalize only no-op
     `lab.execution.run` receipts with execution, approval consumption, network,
     and repository write flags false; they are not command execution,
     candidate validation, runner binding, or sandbox enforcement.
  - Synthetic no-op approval-consumption records may consume exact-action
     approvals only after finalized synthetic receipts exist, and only to block
     approval reuse; they are not repository command execution, candidate
     validation, general Lab approval consumption, or execution authority.
   - Built-in no-op runner envelope records may complete only a Francis-owned
     no-op handoff from consumed synthetic approval evidence; they are not live
     sandbox runner bindings, repository command execution, candidate
     validation, or permission to run repository code.
   - Built-in no-op runner transcript records may record only deterministic
     empty stdout/stderr metadata for completed Francis-owned no-op envelopes;
     they are not real process output capture, repository command execution,
     candidate validation, or permission to run repository code.
   - Built-in no-op runner identity binding records may bind only the
     Francis-owned no-op runner identity to the completed no-op proof chain;
     they are not live runner bindings, sandbox runner bindings, repository
     command execution, candidate validation, or permission to run repository
     code.
   - Source-mount readiness records may confirm the empty Lab workspace source
     reference is `reference_only_read_only` after the no-op runner identity
     chain, but they are not live readonly source mounts, source mount
     enforcement, source copies, source write permission, command execution,
     candidate validation, or execution authority.
   - Source-mount contract records may declare the future read-only source mount
     contract and required enforcement controls after source-mount readiness,
     but they are not live source mounts, mount enforcement, source copies,
     source write permission, command execution, candidate validation, or
     execution authority.
   - Run-boundary preflight records may aggregate source-mount, sandbox
     provider, sandbox provider binding, sandbox provider selection, sandbox
     provider verifier, sandbox provider runtime-probe, sandbox provider
     runtime-probe harness, sandbox readiness, command allowlist, receipt
     writer, and approval-handoff evidence for a future guarded Lab run, but
     they are not live runner bindings, provider verification, provider
     probing, provider bindings, sandbox enforcement, read-only mount
     enforcement, approval consumption for repo execution, command execution,
     candidate validation, or execution authority.



### 1.2 System boundary (what FRANCIS is and isn’t)

FRANCIS is:

- a policy-driven orchestration kernel + APIs

- a tool/connector runtime with strict gating

- a knowledge/memory system with provenance



FRANCIS is not:

- a “model wrapper” that trusts the model to behave

- a general remote execution framework

- an autonomous offensive security platform





## 2. Top-level runtime topology



FRANCIS typically runs as 3 cooperating processes plus optional workers:



- **API Service** (HTTP + WebSocket)

  - routes, session management, orchestration entrypoint

- **Daemon**

  - background system tasks (learning schedules, cleanup, monitoring, federation sync)

- **Workers**

  - concurrency for tool execution, long-running jobs, simulations, crawls

- **Chat UI**

  - React/Vite UI for interactive operation



### 2.1 Topology diagram (conceptual)



```text

┌───────────────────────────┐

│        Chat UI (Web)       │

│  apps/chat_ui (Vite+React) │

└───────────────┬───────────┘

                │ HTTPS / WS

┌───────────────▼───────────┐

│         API Service         │

│  apps/api + src/francis/api  │

│  - auth/session              │

│  - chat routes               │

│  - tool invocation broker    │

└───────────────┬───────────┘

                │ internal calls / queue

┌───────────────▼───────────┐

│      Kernel / Orchestrator  │

│  src/francis/kernel/*        │

│  - planning                  │

│  - governance gates          │

│  - tool selection            │

│  - evidence + citations       │

└───────────────┬───────────┘

                │

     ┌──────────▼──────────┐

     │   Execution Layer     │

     │ - connectors/*        │

     │ - plugin_system/*     │

     │ - ingest lab boundary │
     │   (request/refuse/    │
     │    approval intake)   │

     │ - sandbox limits      │

     └──────────┬──────────┘

                │

┌───────────────▼───────────┐

│   Data Plane (/data)        │

│ - logs, artifacts, memory   │

│ - approvals, trust, state   │
│ - pending lab approval reqs │
│ - lab runner contracts      │
│ - lab runner bindings       │
│ - lab runner enforcement    │

│ - domains, vectors, cache   │

│ - ingest registries/receipts│

└────────────────────────────┘
