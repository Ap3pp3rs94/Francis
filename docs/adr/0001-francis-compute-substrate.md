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

The contract includes `TaskEnvelope`, `ResourceBudget`, `WorkerDescriptor`, `ExecutionBackend`, `WorkerRegistry`, `SubstrateGovernor`, `SafeLocalBackend`, `ExecutionResult`, `CapabilityReceipt`, and `LiveLearningEvent`.

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

This slice enforces truthful configuration and validation boundaries, rejects unauthorized network/GPU/filesystem/approval-required work, and caps registered compute-test units. It does not claim OS-level CPU or memory enforcement. OS-level enforcement remains a future sandbox/runner adapter requirement.

The worker registry rejects duplicate worker IDs and duplicate capability bindings. Disabled workers remain registered for readback but are denied by the governor before backend execution.

## Receipts And Learning

The first slice returns a typed `CapabilityReceipt` object through a narrow adapter boundary. It marks receipt persistence as not implemented instead of pretending a durable compute receipt was written.

The first slice also returns an explicit `LiveLearningEvent` contract object. It does not persist that event into long-term memory. Memory persistence requires a separate governance review because it crosses a durable memory boundary.

## Consequences

The substrate can grow toward stronger workers without changing Francis's authority model. Visual runtimes, virtual machines, containers, remote workers, and simulations become bounded execution adapters with policy, budget, receipt, and verification obligations.

The current limitation is deliberate: this foundation proves the internal contract and safe dispatch path, not production-grade sandboxing, OS resource isolation, or persistent compute receipts.
