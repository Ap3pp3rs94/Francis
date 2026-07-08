# ADR 0001: Francis Compute Substrate

Date: 2026-07-08

Status: Accepted for first internal foundation slice

## Context

Francis is in Phase 2 with `P7_EXECUTION` still partial. The roadmap already defines the Sandboxed Executor as the governed action substrate: branch-safe, scope-enforced, receipted, budgeted, interruptible, and verifiable. New compute-adjacent systems must strengthen that substrate instead of bypassing it or redefining Francis around a specific runtime, visual engine, virtual PC, avatar, or worker implementation.

## Decision

Francis Compute Substrate is a core expanding architecture layer under the existing Phase 2 / `P7_EXECUTION` direction.

Future VSC-1, Unreal, desktop Lens, avatar, VM/container, remote worker, and simulation systems must attach as adapters to this substrate. They must not become the substrate themselves.

The grounded thesis is not free compute and not a solved data-center crisis. Francis aims to improve useful work per watt through local-first processing, resource-aware scheduling, sandboxing, simulation, reusable capabilities, persistent memory, model/tool routing, and receipts-backed execution.

## First Slice Boundary

The first implementation slice is internal only:

- no API route
- no arbitrary subprocess execution
- no shell execution
- no unrestricted filesystem writes
- no unrestricted network
- no background daemon
- no fake receipt persistence
- no long-term memory persistence

The initial safe local backend supports registered internal functions only:

- `echo`
- `health_check`
- `compute_test`
- `summarize_status`

The contract includes `TaskEnvelope`, `ResourceBudget`, `WorkerDescriptor`, `ExecutionBackend`, `WorkerRegistry`, `SubstrateGovernor`, `SafeLocalBackend`, `ExecutionResult`, `CapabilityReceipt`, `LiveLearningEvent`, `ApprovalScope`, `ApprovalGrant`, and `ApprovalConsumptionResult`.

## Resource Protection

Every task envelope carries a resource budget with:

- max runtime
- memory budget
- CPU weight
- priority
- network allowance
- filesystem scope
- GPU allowance
- cancellation state
- approval requirement
- compute-unit ceiling

This slice enforces truthful configuration and validation boundaries, rejects unauthorized network/GPU/filesystem work, requires valid internal approval consumption for approval-required work, and caps registered compute-test units. It does not claim OS-level CPU or memory enforcement. OS-level enforcement remains a future sandbox/runner adapter requirement.

The worker registry rejects duplicate worker IDs and duplicate capability bindings. Disabled workers remain registered for readback but are denied by the governor before backend execution.

## Cancellation And Deadline Semantics

An internal cancellation/deadline slice adds cooperative execution controls through `ExecutionDeadline`, `CancellationToken`, and `ExecutionContext`.

The governor now checks approval validity before cancellation/deadline denial, then denies already-cancelled or already-expired work before backend execution. Valid approval grants are not consumed when a pre-execution cancellation or expired deadline blocks execution before the backend starts. Approval grants are consumed only once execution is allowed to start, so a timeout or failure after backend start still reports approval consumption truthfully.

Safe local registered functions receive the execution context and can cooperatively observe cancellation/deadline state. The bounded `cooperative_delay_test` function exists only as an internal deterministic test capability for this contract. It does not add subprocess, shell, network, GPU, daemon, broad filesystem, model-training, long-term memory, adapter, or API authority.

Post-execution runtime or deadline overruns are reported as timeouts without pretending that Francis preempted the work. This slice does not implement OS-level preemption, CPU scheduling, memory enforcement, thread killing, process killing, subprocess killing, container isolation, or cgroup/job-object enforcement. Those remain future sandbox/runner adapter requirements.

`CapabilityReceipt` objects now summarize cancellation and timeout evidence, including cancellation request state, cancellation reason, deadline summary, timeout stage, execution started/finished state, duration, and over-budget runtime. Durable compute receipts persist only that bounded summary.

## Internal Submission And Status Surface

An internal submission/status slice adds `ComputeSubstrateService`, `ComputeSubmission`, `ComputeSubmissionResult`, `ComputeTaskStatus`, `ComputeTaskRecord`, and a process-local in-memory status store.

The service is a synchronous, in-process Python control surface. It owns or receives a configured `SubstrateGovernor` and `WorkerRegistry`, submits `TaskEnvelope` objects through the existing governed execution path, and records bounded status summaries for readback by task id or correlation id. A task may move directly from `submitted` to a final status during a single call; this slice does not create background workers, daemons, async execution, or a new HTTP/API route.

Status records are bounded to safe summary fields such as task id, correlation id, capability, worker id, final status, denial reason, approval summary, cancellation/timeout summary, receipt id, receipt persistence truth, and timing fields. They do not store raw task payloads, raw execution output, secrets, raw approval notes, model prompts, long-term memory, live-learning persistence, broad filesystem paths, or adapter-specific state.

Adapters may request work through this service, but the substrate still governs, the governor still decides, approvals still authorize, and receipts still prove what happened. A service configured with a governor using `LocalJsonComputeApprovalStore` benefits from durable approval readback and consumption through that same governed path. The service does not add Unreal, VSC-1, desktop Lens, avatar, voice, VM/container, remote worker, simulation, model-training, network, GPU, shell, subprocess, broad filesystem, OS-level CPU/memory enforcement, durable adapter persistence, or long-term learning capability.

## Durable Status Persistence

An internal durable status-persistence slice adds `LocalJsonComputeStatusStore` behind the same `ComputeStatusStore` contract while preserving `InMemoryComputeStatusStore`.

Compute task status can now be stored and read back as bounded local JSON records by task id and correlation id when a service is explicitly configured with the durable status store. The store uses safe task and correlation ids, rejects path-like ids, writes under a configured local status root, and uses temp-file then replace persistence.

Durable status persistence is separate from durable compute receipt persistence and durable approval persistence. Status reports the bounded task state. Receipts prove what happened during execution attempts. Approvals prove why Francis was allowed to attempt execution. A configured durable status store does not imply durable compute receipts, durable approvals, durable adapter persistence, task recovery, resumability, public API exposure, async/background execution, long-term memory persistence, live-learning persistence, or model training.

Persisted status JSON contains bounded `ComputeTaskRecord` fields such as task id, correlation id, capability, worker id, final status, denial reason, approval summary, cancellation/timeout summary, receipt id, receipt persistence truth, and timing fields. It does not persist raw `TaskEnvelope.payload`, raw execution outputs, secrets, raw approval notes, raw model prompts, broad filesystem paths, adapter state, long-term memory, live-learning events, network authority, GPU authority, shell authority, daemon state, or new execution authority.

If a task passes through `ComputeAdapterGateway`, durable compute status is still written only through the configured `ComputeSubstrateService` status store. Adapter contracts remain contract-only, and durable adapter persistence is not implemented.

## Internal Adapter Contract Layer

An internal adapter contract slice adds `ComputeAdapterKind`, `ComputeAdapterDescriptor`, `ComputeAdapterPolicy`, `ComputeAdapterRequest`, `ComputeAdapterSubmissionResult`, `ComputeAdapterRegistry`, `InMemoryComputeAdapterRegistry`, and `ComputeAdapterGateway`.

This layer defines obligations for future Francis bodies and runtimes before they can request compute substrate work. Adapter kinds such as Unreal, VSC-1, desktop Lens, avatar, voice, VM/container, remote worker, simulation, and internal are labels only in this slice. No real adapter implementation, runtime bridge, visual engine binding, virtual PC binding, remote worker, simulator, voice adapter, avatar adapter, or Lens adapter is added.

The adapter gateway is synchronous and in-process. It validates adapter identity, enabled state, declared capabilities, adapter policy, resource ceilings, risk ceiling, default-deny network/GPU/filesystem posture, approval requirements, and optional cancellation/deadline context before converting a request into a `TaskEnvelope` and submitting only through `ComputeSubstrateService.submit`. It does not call backends directly and does not bypass the governor, approval store, budget validation, cancellation/deadline handling, receipt generation, or status readback path.

Adapter request payloads may exist only in memory long enough to create a governed `TaskEnvelope`. Adapter descriptors, policies, request summaries, and submission results do not persist raw payloads, raw execution outputs, secrets, raw approval notes, raw model prompts, long-term memory, live-learning events, broad filesystem paths, or adapter-specific state. A valid durable approval grant may authorize adapter-requested work only after adapter validation passes and only through `ComputeSubstrateService` and `SubstrateGovernor`. This slice does not add a public API route, async execution, background workers, durable adapter status persistence, durable adapter persistence, long-term memory persistence, live-learning persistence, model training, OS-level CPU/memory enforcement, network, GPU, shell, subprocess, daemon, or new execution authority. A later durable status store can record adapter-submitted compute task status only through the service status path.

## Approval Consumption

An internal approval-consumption slice lets approval-required compute tasks execute only when a valid `ApprovalGrant` is supplied through the internal approval store boundary.

Approvals are scope-checked before execution. The scope can bind a grant to a task id, correlation id, capability, worker id, risk ceiling, and resource-budget ceiling. Expired, revoked, already-consumed, unbounded, mismatched, over-risk, and over-budget approvals fail closed before backend execution. Single-use grants are consumed before backend execution is attempted, so a failed execution after valid consumption still truthfully reports that the approval was consumed for the attempt.

`CapabilityReceipt` objects summarize approval evidence with approval-required, approval-satisfied, approval-id, decision, denial reason, consumed state, and scope summary fields. Approval notes are not persisted into compute receipts. The first approval-consumption slice kept approval grants process-local and in-memory; cross-process atomic reservation and broader enterprise approval audit storage remain future governance work.

## Durable Approval Persistence

An internal durable approval-persistence slice adds `LocalJsonComputeApprovalStore` behind the same `ApprovalStore` contract while preserving `InMemoryApprovalStore`.

Approval grants can now be stored, read back, authorized, and consumed through a bounded local JSON approval store. The durable store uses safe approval IDs, rejects path-like IDs, writes under a configured local approval root, uses temp-file then replace persistence, and records consumed state for single-use approvals by preserving `consumed_at_ms` and `consumed_by_task_id`.

Durable approval persistence is separate from durable compute receipt persistence. Approvals prove why Francis was allowed to attempt execution. Receipts prove what happened during the attempt. A configured durable approval store does not imply compute receipt persistence, and a configured durable compute receipt store does not imply durable approval persistence.

Persisted approval JSON contains bounded approval-grant fields and redacted note/reason summaries only. It does not persist raw task payloads, raw execution outputs, raw approval notes, raw model prompts, secrets, broad filesystem paths, long-term memory, live-learning events, adapter state, status records, network authority, GPU authority, shell authority, daemon state, or new execution authority.

The durable approval store provides local JSON durability and sequential single-use consumption within the tested store semantics. It does not implement cross-process atomic reservation, distributed locks, durable compute status persistence by itself, durable adapter persistence, durable compute receipt persistence by itself, OS-level CPU/memory enforcement, process/thread preemption, API submission, Unreal, VSC-1, desktop Lens, avatar, voice, VM/container, remote worker, simulation, long-term memory persistence, live-learning persistence, or model training.

## Receipts And Learning

The baseline slice returned a typed `CapabilityReceipt` object through a narrow adapter boundary without pretending durable compute receipt persistence existed.

A follow-on internal slice adds durable persistence for `CapabilityReceipt` only through an optional local JSON receipt store. When no store is configured, the governor still returns an in-memory receipt object. When a store is configured, `persisted=true` and `receipt_path` are set only after an actual local receipt write succeeds. Failed receipt writes are reported on the returned result and receipt instead of being treated as successful persistence.

Durable compute receipts are bounded to compute receipt fields. They do not persist raw task payloads, task outputs, long-term memory, raw approval notes, model-training events, network execution, GPU execution, shell execution, daemon state, or arbitrary filesystem authority. Approval consumption evidence is summarized separately from durable approval-grant persistence, and receipts indicate durable approval-store truth only when the approval result actually came from the durable approval store.

The substrate also returns an explicit `LiveLearningEvent` contract object. It does not persist that event into long-term memory. Memory persistence requires a separate governance review because it crosses a durable memory boundary.

## Consequences

The substrate can grow toward stronger workers without changing Francis's authority model. Visual runtimes, virtual machines, containers, remote workers, and simulations become bounded execution adapters with policy, budget, receipt, and verification obligations.

The current limitation is deliberate: this foundation proves the internal contract, safe dispatch path, bounded compute receipt persistence, internal approval consumption, durable local approval persistence, cooperative cancellation/deadline semantics, internal synchronous submission/status readback, durable local compute status persistence, and internal adapter request obligations. It does not prove production-grade sandboxing, OS resource isolation, cross-process atomic approval reservation, OS-level CPU/memory preemption, API submission, adapter execution, task recovery/resume, durable adapter persistence, or long-term learning persistence.
