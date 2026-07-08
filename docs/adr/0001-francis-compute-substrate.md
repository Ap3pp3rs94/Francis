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

Adapters may request work through this service, but the substrate still governs, the governor still decides, approvals still authorize, and receipts still prove what happened. The service does not add Unreal, VSC-1, desktop Lens, avatar, voice, VM/container, remote worker, simulation, model-training, network, GPU, shell, subprocess, broad filesystem, OS-level CPU/memory enforcement, durable approval persistence, or long-term learning capability.

## Approval Consumption

An internal approval-consumption slice lets approval-required compute tasks execute only when a valid `ApprovalGrant` is supplied through the internal approval store boundary.

Approvals are scope-checked before execution. The scope can bind a grant to a task id, correlation id, capability, worker id, risk ceiling, and resource-budget ceiling. Expired, revoked, already-consumed, unbounded, mismatched, over-risk, and over-budget approvals fail closed before backend execution. Single-use grants are consumed before backend execution is attempted, so a failed execution after valid consumption still truthfully reports that the approval was consumed for the attempt.

`CapabilityReceipt` objects summarize approval evidence with approval-required, approval-satisfied, approval-id, decision, denial reason, consumed state, and scope summary fields. Approval notes are not persisted into compute receipts. This slice keeps approval grants process-local and in-memory; durable approval persistence, cross-process atomic reservation, and broader enterprise approval audit storage remain future governance work.

## Receipts And Learning

The baseline slice returned a typed `CapabilityReceipt` object through a narrow adapter boundary without pretending durable compute receipt persistence existed.

A follow-on internal slice adds durable persistence for `CapabilityReceipt` only through an optional local JSON receipt store. When no store is configured, the governor still returns an in-memory receipt object. When a store is configured, `persisted=true` and `receipt_path` are set only after an actual local receipt write succeeds. Failed receipt writes are reported on the returned result and receipt instead of being treated as successful persistence.

Durable compute receipts are bounded to compute receipt fields. They do not persist raw task payloads, task outputs, long-term memory, raw approval notes, model-training events, network execution, GPU execution, shell execution, daemon state, or arbitrary filesystem authority. Approval consumption evidence is summarized rather than treated as durable approval-grant persistence.

The substrate also returns an explicit `LiveLearningEvent` contract object. It does not persist that event into long-term memory. Memory persistence requires a separate governance review because it crosses a durable memory boundary.

## Consequences

The substrate can grow toward stronger workers without changing Francis's authority model. Visual runtimes, virtual machines, containers, remote workers, and simulations become bounded execution adapters with policy, budget, receipt, and verification obligations.

The current limitation is deliberate: this foundation proves the internal contract, safe dispatch path, bounded compute receipt persistence, internal approval consumption, cooperative cancellation/deadline semantics, and internal synchronous submission/status readback. It does not prove production-grade sandboxing, OS resource isolation, durable approval persistence, cross-process atomic approval reservation, OS-level CPU/memory preemption, API submission, adapter execution, or long-term learning persistence.
