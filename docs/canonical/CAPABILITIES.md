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



## 3.6.2 Code-Born Capability Ingestion

**Maturity:** Now (source indexing, repo mapping, candidate drafting, lab-boundary approval preflight/refusal)

**Interfaces:** CLI + internal ingest service + permission-gated API readback + operator UI readback

**State:** source registry, capability candidate registry, repo-map artifacts, lab-plan/workspace/preflight/approval-request/runner-contract/runner-readiness/runner-binding/runner-enforcement/approval-consumption-handoff/approval-consumption-record/no-op-runner-envelope/no-op-runner-transcript/no-op-runner-identity-binding/source-mount-readiness/source-mount-contract/run-boundary-preflight/sandbox-provider-contract/sandbox-provider-binding-preflight/sandbox-provider-selection-preflight/sandbox-provider-verifier-preflight/sandbox-provider-runtime-probe-preflight/sandbox-provider-runtime-probe-harness-preflight/sandbox-provider-runtime-probe-runner-readiness/sandbox-provider-runtime-probe-runner-binding-preflight/sandbox-provider-runtime-probe-runner-enforcement-preflight/sandbox-provider-runtime-probe-execution-boundary/sandbox-provider-runtime-probe-refusal/sandbox-provider-runtime-probe-approval-request/sandbox-provider-runtime-probe-approval-consumption/sandbox-provider-runtime-probe-invocation-boundary/sandbox-provider-runtime-probe-runner-pre-execution-boundary/sandbox-provider-runtime-probe-runner-control-binding/sandboxed-rebuild-run-test-boundary/sandboxed-rebuild-run-test-approval-request/sandboxed-rebuild-run-test-approval-consumption/sandboxed-rebuild-run-test-runner-binding-preflight/sandboxed-rebuild-run-test-sandbox-policy-preflight/execution-receipt-sink-reservation/execution-receipt-write-readiness/execution-receipt-prewrite-binding/execution-receipt-writer-preflight/synthetic-execution-receipt/runner-command-allowlist-binding/runner-command-allowlist-declaration/runner-command-allowlist-enforcement/runner-sandbox-readiness artifacts, refusal receipts

**Governance:** read-only by default; build/run/test/package actions require explicit future Francis Lab authority; synthetic no-op execution receipt writes require `ingest.lab.receipt.write`; synthetic no-op approval consumption requires `ingest.lab.approval.consume`; built-in no-op runner envelopes require `ingest.lab.runner.noop`; built-in no-op runner transcripts require `ingest.lab.runner.noop.transcript`; built-in no-op runner identity bindings require `ingest.lab.runner.noop.identity`; source-mount readiness records require `ingest.lab.source_mount.readiness`; source-mount contract records require `ingest.lab.source_mount.contract`; sandbox provider contracts require `ingest.lab.sandbox.provider_contract`; sandbox provider binding preflights require `ingest.lab.sandbox.provider_binding`; sandbox provider selection preflights require `ingest.lab.sandbox.provider_selection`; sandbox provider verifier preflights require `ingest.lab.sandbox.provider_verifier`; sandbox provider runtime-probe preflights require `ingest.lab.sandbox.provider_runtime_probe`; sandbox provider runtime-probe harness preflights require `ingest.lab.sandbox.provider_runtime_probe_harness`; sandbox provider runtime-probe runner readiness records require `ingest.lab.sandbox.provider_runtime_probe_runner_readiness`; sandbox provider runtime-probe runner binding preflights require `ingest.lab.sandbox.provider_runtime_probe_runner_binding`; sandbox provider runtime-probe runner enforcement preflights require `ingest.lab.sandbox.provider_runtime_probe_runner_enforcement`; sandbox provider runtime-probe execution boundaries require `ingest.lab.sandbox.provider_runtime_probe_execution_boundary`; sandbox provider runtime-probe refusals require `ingest.lab.sandbox.provider_runtime_probe.refuse`; sandbox provider runtime-probe approval requests require `ingest.lab.sandbox.provider_runtime_probe.request_approval`; sandbox provider runtime-probe approval consumption requires `ingest.lab.sandbox.provider_runtime_probe.consume_approval`; sandbox provider runtime-probe invocation boundaries require `ingest.lab.sandbox.provider_runtime_probe.invocation_boundary`; sandbox provider runtime-probe runner pre-execution boundaries require `ingest.lab.sandbox.provider_runtime_probe.runner_pre_execution_boundary`; sandbox provider runtime-probe runner control bindings require `ingest.lab.sandbox.provider_runtime_probe.runner_control_binding`; sandboxed rebuild/run/test boundaries require `ingest.lab.sandboxed_rebuild_run_test.boundary`; sandboxed rebuild/run/test approval requests require `ingest.lab.sandboxed_rebuild_run_test.request_approval`; sandboxed rebuild/run/test approval consumption requires `ingest.lab.sandboxed_rebuild_run_test.consume_approval`; sandboxed rebuild/run/test runner-binding preflights require `ingest.lab.sandboxed_rebuild_run_test.runner_binding`; sandboxed rebuild/run/test sandbox-policy preflights require `ingest.lab.sandboxed_rebuild_run_test.sandbox_policy`; run-boundary preflights require `ingest.lab.run_boundary.preflight`

**Observability:** every add, inspect, candidate extraction, lab plan, workspace preparation, execution preflight, approval request, approval-consumption preflight, runner-readiness preflight, runner-binding preflight, runner-enforcement preflight, approval-consumption handoff, synthetic no-op approval consumption, built-in no-op runner envelope, built-in no-op runner transcript, built-in no-op runner identity binding, source-mount readiness, source-mount contract, sandbox provider contract, sandbox provider binding preflight, sandbox provider selection preflight, sandbox provider verifier preflight, sandbox provider runtime-probe preflight, sandbox provider runtime-probe harness preflight, sandbox provider runtime-probe runner readiness, sandbox provider runtime-probe runner binding preflight, sandbox provider runtime-probe runner enforcement preflight, sandbox provider runtime-probe execution boundary, sandbox provider runtime-probe refusal, sandbox provider runtime-probe approval request, sandbox provider runtime-probe approval consumption, sandbox provider runtime-probe invocation boundary, sandbox provider runtime-probe runner pre-execution boundary, sandbox provider runtime-probe runner control binding, sandboxed rebuild/run/test boundary, sandboxed rebuild/run/test approval request, sandboxed rebuild/run/test approval consumption, sandboxed rebuild/run/test runner-binding preflight, sandboxed rebuild/run/test sandbox-policy preflight, run-boundary preflight, execution-receipt sink reservation, execution receipt write readiness, execution receipt prewrite binding, execution receipt writer preflight, synthetic execution receipt prewrite/finalize, runner command allowlist binding, runner command allowlist declaration, runner command allowlist enforcement preflight, runner sandbox readiness preflight, and execution refusal emits compact receipts

**Lab v0 runtime (gated, separate downstream subsystem):** as of `2026-06-10`, `IngestService.run_lab_capability` (CLI `francis lab run … [--opt-in]`, API `POST /ingest/lab/run`, scope `ingest.lab.execute.run`) can perform a sandboxed rebuild/run. Real execution requires **all** of: a consumed `sandboxed_rebuild_run_test` approval, a safety-gated non-destructive candidate, explicit operator opt-in, and a live Docker daemon; absent any of these it runs a Francis-owned no-op marked `execution_mode: "simulated"`. Deterministic validation returns `PARTIAL` for simulated, `VALID`/`INVALID` only for real runs; promotion advances at most one ladder rung and only on real `VALID` evidence, never reaching `registered`. **Honesty caveat:** the real-Docker path is implemented and unit-tested against a mocked daemon only — it has not been verified against a live daemon, no pinned base image exists, and no candidate has been promoted to `validated` from real execution. See `docs/CODE_BORN_CAPABILITY_INGESTION.md` and `docs/INGEST_CORE_LAB_SHARED_CONTRACTS.md`. Known gap: refusal/blocked `run_lab_capability` paths do not yet emit a receipt (success path does).



**What it provides**

- local-first ingestion of files, folders, and repositories as source records

- read-only repository maps with manifests, scripts, docs, tests, entrypoints, and risk signals

- conservative capability candidates that remain discovered/drafted until validated

- Francis Lab plan records that project permissions, blockers, and required controls

- empty Francis-owned lab workspaces with manifests and source references, not source copies

- exact-action lab preflights with action hashes and approval intent, not approval grants

- pending exact-action lab approval requests in the Francis approvals queue, not execution authority

- approval-consumption preflights that refuse stale or mismatched approval ids before any runner can consume them

- blocked runner contract projections that name required future sandbox, isolation, resource, and receipt controls

- runner-readiness preflights that enumerate missing sandbox, runner, isolation, command, environment, resource, and receipt controls

- runner-binding preflights that enumerate missing governed runner binding and execution-receipt sink controls

- runner-enforcement preflights that verify missing runner identity, command allowlist, environment, network, filesystem, resource, timeout, capture, receipt-write, and approval-consumption controls

- approval-consumption handoff readbacks that bind an approved exact-action id to runner-enforcement state while still blocking consumption and execution

- execution-receipt sink reservation readbacks that reserve a future execution receipt id/path while still blocking receipt prewrite, final write, and execution

- runner command allowlist binding readbacks that project exact-action command plans while still blocking allowlist declaration, allowlist binding, approval consumption, and command execution

- runner command allowlist declaration readbacks that derive deterministic allowlist entries from exact-action command plans while still blocking live allowlist binding, approval consumption, and command execution

- runner command allowlist enforcement preflight readbacks that check declared exact-action entries against missing live runner, allowlist-binding, receipt-prewrite, and receipt-final-write controls while still blocking approval consumption and command execution

- runner sandbox readiness readbacks that check workspace evidence and future sandbox controls while still blocking sandbox binding, approval consumption, and command execution

- sandbox provider contract records that declare the future provider boundary and required enforcement controls while still blocking provider binding, sandbox enforcement, runner binding, command execution, validation, and promotion

- sandbox provider binding preflight records that declare the future binding checklist while still blocking provider selection, provider binary/service verification, provider policy binding, sandbox enforcement, runner binding, command execution, validation, and promotion

- sandbox provider selection preflight records that record requested provider kind, local provider reference metadata, and optional provider policy manifest metadata while still blocking provider binary/service verification, live provider binding, sandbox enforcement, runner binding, command execution, validation, and promotion

- sandbox provider verifier preflight records that bind the Francis static verifier identity, capture local provider reference fingerprints, sanitize provider policy manifest summaries/hashes, and record declared provider version evidence while still blocking provider runtime probes, provider binary execution, service queries, container launch, live provider binding, sandbox enforcement, runner binding, command execution, validation, and promotion
- sandbox provider runtime-probe preflight records that declare future provider probe authorization, timeout, network-blocking, workspace-isolation, receipt, and repository-execution separation controls while still blocking provider binary execution, provider service queries, container launch, live provider binding, sandbox enforcement, approval consumption, command execution, validation, and promotion
- sandbox provider runtime-probe harness preflight records that declare future provider probe runner, sandbox, service-query guard, output capture, and kill-switch controls while still blocking provider binary execution, provider service queries, container launch, live provider binding, sandbox enforcement, approval consumption, execution receipt writes, command execution, validation, and promotion
- sandbox provider runtime-probe runner readiness records that declare the future probe-runner interface and missing runner implementation, identity, policy, sandbox, network-block, workspace-isolation, timeout, output-capture, kill-switch, and receipt-contract controls while still blocking provider binary execution, provider service queries, process launch, container launch, live provider binding, sandbox enforcement, approval consumption, execution receipt writes, command execution, validation, and promotion
- sandbox provider runtime-probe runner binding preflight records that declare the future probe-runner binding contract and missing live runner, runtime-probe binding, sandbox, network, timeout, output-capture, kill-switch, and receipt controls while still blocking provider binary execution, provider service queries, process launch, container launch, live provider binding, sandbox enforcement, approval consumption, execution receipt writes, command execution, validation, and promotion
- sandbox provider runtime-probe runner enforcement preflight records that declare the future probe-runner enforcement contract and missing live enforcement, runner binding, runtime-probe binding, provider runtime probe, sandbox, network, timeout, output-capture, kill-switch, and receipt controls while still blocking provider binary execution, provider service queries, process launch, container launch, live provider binding, sandbox enforcement, approval consumption, execution receipt writes, command execution, validation, and promotion
- sandbox provider runtime-probe execution-boundary records that compose run-boundary and runtime-probe runner enforcement readbacks and declare the future provider-probe execution gate while still blocking provider binary execution, provider service queries, process launch, container launch, live provider binding, sandbox enforcement, approval consumption, execution receipt writes, command execution, validation, and promotion
- sandbox provider runtime-probe refusal records that depend on the execution boundary and write a compact refusal receipt while still blocking provider binary execution, provider service queries, process launch, container launch, live provider binding, sandbox enforcement, approval consumption, execution receipt writes, command execution, validation, and promotion
- sandbox provider runtime-probe approval-request records that depend on the execution boundary and create a pending exact-action approval request for future provider probing while still blocking approval consumption, provider binary execution, provider service queries, process launch, container launch, live provider binding, sandbox enforcement, execution receipt writes, command execution, validation, and promotion
- sandbox provider runtime-probe approval-consumption records that consume an approved exact-action provider-probe approval as single-use governance evidence while still blocking provider binary execution, provider service queries, process launch, container launch, live provider binding, sandbox enforcement, execution receipt writes, command execution, validation, and promotion
- sandboxed rebuild/run/test approval-consumption records that consume an approved exact-action sandboxed rebuild/run/test approval as single-use governance evidence while still blocking live runner binding, sandbox enforcement, process launch, container launch, command execution, repository code execution, install/build/test execution, network access, repository writes, execution receipt writing, validation, promotion, and execution authority
- sandboxed rebuild/run/test runner-binding preflight records that record static local provider reference and policy-manifest metadata after approval consumption while still blocking live runner binding, sandbox enforcement, provider execution, provider service queries, command execution, execution receipt writing, validation, promotion, and execution authority
- sandboxed rebuild/run/test sandbox-policy preflight records that bind approval-consumption and static runner-binding evidence to conservative default-deny network, read-only source-reference, no repo write, no destructive action, no secret storage, command-execution-disabled, and missing live sandbox/allowlist/receipt-writer controls while still blocking execution, validation, promotion, and execution authority

- execution receipt write readiness readbacks that check the reserved execution receipt id/path and future prewrite/final-write controls while still blocking execution receipt writes, approval consumption, and command execution

- execution receipt prewrite binding readbacks that bind the future `lab.execution.run` receipt schema plus prewrite/final-write contracts while still blocking writer implementations, execution receipt writes, approval consumption, execution authority, and command execution

- execution receipt writer preflight readbacks that declare future writer boundary, reserved sink path, atomic write, and redaction controls while still blocking writer implementations, execution receipt writes, approval consumption, execution authority, and command execution

- synthetic execution receipt readbacks that prove the reserved receipt writer can prewrite/finalize a no-op `lab.execution.run` receipt while all execution, approval-consumption, network, and repo-write flags stay false

- synthetic no-op approval-consumption records that consume an exact-action approval only after a finalized synthetic/no-op execution receipt exists, enforce single-use reuse blocking, and still grant no execution authority

- built-in no-op runner envelope records that consume no repository authority, perform only a Francis-owned no-op envelope step, and keep repository command, network, write, and validation flags false

- built-in no-op runner transcript records that record deterministic empty stdout/stderr metadata for the Francis-owned no-op envelope without real process output capture or stored output content

- built-in no-op runner identity binding records that bind only the Francis-owned no-op runner identity to the completed no-op proof chain while keeping live runner binding, sandbox runner binding, execution, validation, and promotion false

- source-mount readiness records that confirm the Lab workspace source reference is `reference_only_read_only` after the no-op identity chain while keeping live readonly mount binding, mount enforcement, source copy, source writes, execution, validation, and promotion false

- source-mount contract records that declare the future read-only source mount contract and required enforcement controls while keeping live mount binding, mount enforcement, source copy, source writes, execution, validation, and promotion false

- run-boundary preflight records that aggregate source-mount contract, sandbox readiness, sandbox provider contract, sandbox provider binding preflight, sandbox provider selection preflight, sandbox provider verifier preflight, sandbox provider runtime-probe preflight, sandbox provider runtime-probe harness preflight, sandbox provider runtime-probe runner enforcement preflight, command allowlist enforcement, execution receipt writer, and approval-handoff evidence while still blocking live runner enforcement, sandbox provider binding, provider runtime probing, sandbox enforcement, approval consumption for repo execution, execution receipt writes, command execution, validation, and promotion

- `GET /ingest/readback` readback for source records, repo maps, capability candidates, lab preflights, approval-consumption preflights, approval-consumption records, no-op runner envelope records, no-op runner transcript records, no-op runner identity binding records, source-mount readiness records, source-mount contract records, sandbox provider contract records, sandbox provider binding preflight records, sandbox provider selection preflight records, sandbox provider verifier preflight records, sandbox provider runtime-probe preflight records, sandbox provider runtime-probe harness preflight records, sandbox provider runtime-probe runner readiness records, sandbox provider runtime-probe runner binding preflight records, sandbox provider runtime-probe runner enforcement preflight records, sandbox provider runtime-probe execution-boundary records, sandbox provider runtime-probe refusal records, sandbox provider runtime-probe approval-request records, sandbox provider runtime-probe approval-consumption records, sandboxed rebuild/run/test approval-consumption records, sandboxed rebuild/run/test runner-binding preflight records, sandboxed rebuild/run/test sandbox-policy preflight records, run-boundary preflight records, runner contracts, runner-readiness records, runner-binding records, runner-enforcement records, approval-consumption handoff records, execution-receipt sink reservation records, execution receipt write readiness records, execution receipt prewrite binding records, execution receipt writer preflight records, synthetic execution receipts, runner command allowlist binding records, runner command allowlist declaration records, runner command allowlist enforcement preflight records, and runner sandbox readiness records

- Chat UI Code Ingest readback panel using the bounded `chat_ui.ingest` actor

- `POST /ingest/lab/approval-consumption-preflight` readback for API clients with `ingest.lab.readback` scope

- `POST /ingest/lab/runner-readiness` readback for API clients with `ingest.lab.readback` scope

- `POST /ingest/lab/runner-binding` readback for API clients with `ingest.lab.readback` scope

- `POST /ingest/lab/runner-enforcement` readback for API clients with `ingest.lab.readback` scope

- `POST /ingest/lab/approval-consumption-handoff` readback for API clients with `ingest.lab.readback` scope

- `POST /ingest/lab/execution-receipt-sink-reservation` readback for API clients with `ingest.lab.readback` scope

- `POST /ingest/lab/runner-command-allowlist-binding` readback for API clients with `ingest.lab.readback` scope

- `POST /ingest/lab/runner-command-allowlist-declaration` readback for API clients with `ingest.lab.readback` scope

- `POST /ingest/lab/runner-command-allowlist-enforcement` readback for API clients with `ingest.lab.readback` scope

- `POST /ingest/lab/runner-sandbox-readiness` readback for API clients with `ingest.lab.readback` scope

- `POST /ingest/lab/execution-receipt-write-readiness` readback for API clients with `ingest.lab.readback` scope

- `POST /ingest/lab/execution-receipt-prewrite-binding` readback for API clients with `ingest.lab.readback` scope

- `POST /ingest/lab/execution-receipt-writer-preflight` readback for API clients with `ingest.lab.readback` scope

- `POST /ingest/lab/synthetic-execution-receipt-prewrite` for API clients with `ingest.lab.receipt.write` scope

- `POST /ingest/lab/synthetic-execution-receipt-finalize` for API clients with `ingest.lab.receipt.write` scope

- `POST /ingest/lab/approval-consume-synthetic-noop` for API clients with `ingest.lab.approval.consume` scope

- `POST /ingest/lab/noop-runner-envelope` for API clients with `ingest.lab.runner.noop` scope

- `POST /ingest/lab/noop-runner-transcript` for API clients with `ingest.lab.runner.noop.transcript` scope

- `POST /ingest/lab/noop-runner-identity-binding` for API clients with `ingest.lab.runner.noop.identity` scope

- `POST /ingest/lab/source-mount-readiness` for API clients with `ingest.lab.source_mount.readiness` scope

- `POST /ingest/lab/source-mount-contract` for API clients with `ingest.lab.source_mount.contract` scope

- `POST /ingest/lab/sandbox-provider-contract` for API clients with `ingest.lab.sandbox.provider_contract` scope

- `POST /ingest/lab/sandbox-provider-binding` for API clients with `ingest.lab.sandbox.provider_binding` scope

- `POST /ingest/lab/sandbox-provider-selection` for API clients with `ingest.lab.sandbox.provider_selection` scope

- `POST /ingest/lab/sandbox-provider-verifier` for API clients with `ingest.lab.sandbox.provider_verifier` scope
- `POST /ingest/lab/sandbox-provider-runtime-probe` for API clients with `ingest.lab.sandbox.provider_runtime_probe` scope
- `POST /ingest/lab/sandbox-provider-runtime-probe-harness` for API clients with `ingest.lab.sandbox.provider_runtime_probe_harness` scope
- `POST /ingest/lab/sandbox-provider-runtime-probe-runner-readiness` for API clients with `ingest.lab.sandbox.provider_runtime_probe_runner_readiness` scope
- `POST /ingest/lab/sandbox-provider-runtime-probe-runner-binding` for API clients with `ingest.lab.sandbox.provider_runtime_probe_runner_binding` scope
- `POST /ingest/lab/sandbox-provider-runtime-probe-runner-enforcement` for API clients with `ingest.lab.sandbox.provider_runtime_probe_runner_enforcement` scope
- `POST /ingest/lab/sandbox-provider-runtime-probe-execution-boundary` for API clients with `ingest.lab.sandbox.provider_runtime_probe_execution_boundary` scope
- `POST /ingest/lab/sandbox-provider-runtime-probe-refuse` for API clients with `ingest.lab.sandbox.provider_runtime_probe.refuse` scope
- `POST /ingest/lab/sandbox-provider-runtime-probe-request-approval` for API clients with `ingest.lab.sandbox.provider_runtime_probe.request_approval` scope
- `POST /ingest/lab/sandbox-provider-runtime-probe-consume-approval` for API clients with `ingest.lab.sandbox.provider_runtime_probe.consume_approval` scope
- `POST /ingest/lab/sandboxed-rebuild-run-test-consume-approval` for API clients with `ingest.lab.sandboxed_rebuild_run_test.consume_approval` scope
- `POST /ingest/lab/sandboxed-rebuild-run-test-runner-binding` for API clients with `ingest.lab.sandboxed_rebuild_run_test.runner_binding` scope
- `POST /ingest/lab/sandboxed-rebuild-run-test-sandbox-policy` for API clients with `ingest.lab.sandboxed_rebuild_run_test.sandbox_policy` scope

- `POST /ingest/lab/run-boundary-preflight` for API clients with `ingest.lab.run_boundary.preflight` scope

- refusal receipts proving unknown repo execution was blocked when no governed runner exists



**Hard rule**

- imported repository content is evidence and capability DNA, not execution authority

- no install, build, test, lint, package, Docker, deploy, or shell command may run from an ingested source unless the governed lab path has explicit permission, sandbox controls, and execution receipts

- a lab preflight is not an approval; it can identify the approval gate and action hash, but it must not grant execution authority

- a pending lab approval request is not an approval decision, approval consumption, runner binding, or permission to execute

- an approved matching lab approval id is still not execution authority until a governed runner is bound and receipt-backed

- sandbox provider runtime-probe approval consumption is single-use governance evidence only; it is not provider probing, provider execution, runner binding, sandbox enforcement, execution receipt writing, validation, promotion, or authority to run repository code

- sandboxed rebuild/run/test approval consumption is single-use governance evidence only; it is not live runner binding, sandbox enforcement, process launch, command execution, install/build/test execution, network access, repository write, execution receipt writing, validation, promotion, or authority to run repository code

- sandboxed rebuild/run/test runner-binding preflight is static provider-reference evidence only; it is not live runner binding, sandbox enforcement, provider execution, provider service query, command execution, execution receipt writing, validation, promotion, or authority to run repository code

- runner-readiness preflight is a control checklist, not sandbox enforcement or runner binding

- runner-binding preflight is a contract checklist, not a live runner binding, receipt-sink binding, approval consumption, or execution authority

- runner-enforcement preflight is an enforcement checklist, not live policy enforcement, approval consumption, receipt-sink writes, or execution authority

- approval-consumption handoff is a future-consumer contract, not approval consumption, live runner enforcement, receipt-sink binding, or execution authority

- execution-receipt sink reservation is a future receipt-write contract, not receipt-sink binding, execution receipt prewrite, execution receipt final write, or execution authority

- runner command allowlist binding is a future command-control contract, not a live command allowlist, command execution binding, approval consumption, or execution authority

- runner command allowlist declaration is a future command-control record, not a live allowlist binding, runner binding, command execution, approval consumption, or execution authority

- runner command allowlist enforcement preflight is a future command-control check, not live allowlist enforcement, runner binding, command execution, approval consumption, receipt-sink writes, or execution authority

- runner sandbox readiness is a future sandbox-control check, not a live sandbox, live runner binding, readonly source mount, command execution, approval consumption, receipt-sink writes, or execution authority

- execution receipt write readiness is a future receipt-write check, not receipt schema binding, execution receipt prewrite, execution receipt final write, command execution, approval consumption, or execution authority

- execution receipt prewrite binding is a future receipt schema/prewrite contract check, not an execution receipt prewrite, execution receipt final write, writer implementation, command execution, approval consumption, or execution authority

- execution receipt writer preflight is a future receipt-writer boundary check, not a writer implementation, execution receipt prewrite, execution receipt final write, command execution, approval consumption, or execution authority

- synthetic no-op execution receipt prewrite/finalize is a receipt-writer proof path, not repository command execution, candidate validation, approval consumption, runner binding, sandbox binding, or execution authority

- synthetic no-op approval consumption consumes an exact-action approval only for an already finalized synthetic/no-op receipt; it is not repository command execution, candidate validation, runner binding, sandbox binding, general Lab approval consumption, or execution authority

- built-in no-op runner envelopes are Francis-owned no-op handoff proofs, not live sandbox runner bindings, repository command execution, candidate validation, build/test execution, promotion, or permission to run repository code

- built-in no-op runner transcripts are deterministic empty-output proofs for Francis-owned no-op envelopes, not real process stdout/stderr capture, repository command execution, sandbox runner binding, candidate validation, build/test execution, promotion, or permission to run repository code

- built-in no-op runner identity bindings are Francis-owned runner-identity proofs, not live runner binding, sandbox runner binding, repository command execution, real process output capture, candidate validation, build/test execution, promotion, or permission to run repository code

- source-mount readiness records are source-reference proofs, not live readonly source mounts, source mount enforcement, source copies, source write permission, repository command execution, candidate validation, build/test execution, promotion, or permission to run repository code

- source-mount contract records are future mount-boundary declarations, not live readonly source mounts, source mount enforcement, source copies, source write permission, repository command execution, candidate validation, build/test execution, promotion, or permission to run repository code

- sandbox provider contract records are future provider-boundary declarations, not live provider binding, sandbox enforcement, runner binding, process launch, repository command execution, candidate validation, build/test execution, promotion, or permission to run repository code

- sandbox provider binding preflights are future binding checklists, not provider selection, provider binary/service verification, provider policy binding, live provider binding, sandbox enforcement, process launch, repository command execution, candidate validation, build/test execution, promotion, or permission to run repository code

- sandbox provider selection preflights are metadata-only selection/reference records, not provider binary/service verification, live provider binding, sandbox enforcement, process launch, service query, container launch, repository command execution, candidate validation, build/test execution, promotion, or permission to run repository code

- sandbox provider verifier preflights may record static provider reference fingerprints, sanitized policy-manifest hashes, declared provider version, and Francis verifier identity; they are not provider runtime probe success, live provider binding, sandbox enforcement, process launch, service query, container launch, repository command execution, candidate validation, build/test execution, promotion, or permission to run repository code
- sandbox provider runtime-probe preflights may record a future provider probe contract with authorization, timeout, network-blocking, workspace-isolation, receipt, and repository-execution separation controls; they are not provider runtime probe success, provider binary execution, provider service query, container launch, live provider binding, sandbox enforcement, repository command execution, candidate validation, build/test execution, promotion, or permission to run repository code
- sandbox provider runtime-probe harness preflights may record a future provider probe harness contract with runner, sandbox, service-query guard, output capture, and kill-switch controls; they are not provider runtime probe success, provider binary execution, provider service query, container launch, live provider binding, sandbox enforcement, repository command execution, execution receipt writing, candidate validation, build/test execution, promotion, or permission to run repository code
- sandbox provider runtime-probe runner readiness records may record a future provider probe-runner interface and missing live runner controls; they are not provider runtime probe success, provider binary execution, provider service query, process launch, container launch, live provider binding, sandbox enforcement, execution receipt writing, repository command execution, candidate validation, build/test execution, promotion, or permission to run repository code
- sandbox provider runtime-probe runner binding preflights may record a future provider probe-runner binding contract and missing live runner controls; they are not live probe-runner binding, provider runtime probe success, provider binary execution, provider service query, process launch, container launch, live provider binding, sandbox enforcement, execution receipt writing, repository command execution, candidate validation, build/test execution, promotion, or permission to run repository code
- sandbox provider runtime-probe runner enforcement preflights may record a future provider probe-runner enforcement contract and missing live enforcement controls; they are not live probe-runner enforcement, runtime-probe binding, provider runtime probe success, provider binary execution, provider service query, process launch, container launch, live provider binding, sandbox enforcement, execution receipt writing, repository command execution, candidate validation, build/test execution, promotion, or permission to run repository code
- sandbox provider runtime-probe execution boundaries may record the blocked future provider-probe execution gate; they are not provider runtime probe success, provider binary execution, provider service query, process launch, container launch, live provider binding, sandbox enforcement, execution receipt writing, approval consumption, repository command execution, candidate validation, build/test execution, promotion, or permission to run repository code
- sandbox provider runtime-probe refusals may record that a requested provider probe was blocked; they are not provider runtime probe success, provider binary execution, provider service query, process launch, container launch, live provider binding, sandbox enforcement, execution receipt writing, approval consumption, repository command execution, candidate validation, build/test execution, promotion, or permission to run repository code
- sandbox provider runtime-probe approval requests may queue operator approval for a future provider probe; they are not approval decisions, approval consumption, provider runtime probe success, provider binary execution, provider service query, process launch, container launch, live provider binding, sandbox enforcement, execution receipt writing, repository command execution, candidate validation, build/test execution, promotion, or permission to run repository code
- sandbox provider runtime-probe approval consumption may consume an approved exact-action provider-probe approval once; it is not provider runtime probe success, provider binary execution, provider service query, process launch, container launch, live provider binding, sandbox enforcement, execution receipt writing, repository command execution, candidate validation, build/test execution, promotion, or permission to run repository code
- sandboxed rebuild/run/test approval consumption may consume an approved exact-action sandboxed rebuild/run/test approval once; it is not live runner binding, sandbox enforcement, process launch, container launch, repository command execution, install/build/test execution, network access, repository writes, execution receipt writing, candidate validation, promotion, or permission to run repository code
- sandboxed rebuild/run/test sandbox-policy preflights may record conservative no-network, read-only-source, no-write, no-destructive-action, no-secret-storage, command-disabled policy evidence after runner-binding readback; they are not live sandbox binding, sandbox enforcement, command allowlist binding, execution receipt writer binding, process launch, repository command execution, install/build/test execution, candidate validation, promotion, or permission to run repository code

- run-boundary preflights are aggregate control proofs, not live provider binding, provider runtime probing, live runner binding or enforcement, sandbox enforcement, approval consumption for repository execution, execution receipt writes, repository command execution, candidate validation, build/test execution, promotion, or permission to run repository code



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

