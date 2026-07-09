# ADR 0006: Francis Compute Substrate Managed Worker Boundary

Date: 2026-07-09

Status: Accepted as contract-only managed worker boundary

## Context

Francis Compute Substrate is a Phase 2 / `P7_EXECUTION` architecture layer for
governed, local-first, receipts-backed execution. It already has typed task
envelopes, resource budgets, safe internal backend functions, worker registry
checks, substrate governance, approval consumption and persistence, durable
compute receipts, durable status records, adapter contracts, internal/local-dev
API submission/status routes, receipt readback, capability readback, and
checkpoint coverage.

The next risk is worker expansion. Future local managed workers, containers,
VMs, microVMs, remote workers, and simulation workers could accidentally invent
their own authority path if Francis adds runtime-specific code before a contract
boundary exists.

ADR 0005 records that OS-level resource enforcement is not implemented yet. It
lists possible future enforcement mechanisms such as Windows Job Objects,
managed out-of-process workers, cgroups, containers, microVMs, process
priority/affinity, GPU limits, and scheduler throttling. This ADR defines the
contract boundary that those future mechanisms must satisfy before any real
worker implementation is added.

## Decision

Francis now has a contract-only managed worker boundary. It defines labels,
descriptors, policies, sandbox profiles, readiness checks, resource envelopes,
launch plans, execution plans, bindings, and a backend contract protocol for
future managed workers.

Managed worker kinds are labels only:

- `local_safe`
- `container`
- `vm`
- `microvm`
- `remote`
- `simulation`
- `custom`
- `unknown`

The contract does not execute work. It produces bounded readiness results and
contract-only execution plans. A plan is not a launch. A launch plan is not a
running worker. A worker kind label is not proof that a container, VM, microVM,
remote worker, or simulator exists.

## Managed Worker Registry Integration

Francis now has a process-local, in-memory managed worker registry for
contract-only metadata.

The managed worker registry can register, validate, query, summarize, and bind
`ManagedWorkerDescriptor` objects as future-worker metadata. It does not execute
workers, start workers, register executable backends, submit tasks, mutate
approvals, mutate receipts, mutate status, persist managed-worker records, or
write memory.

This registry is separate from the executable `WorkerRegistry` used by
`SubstrateGovernor`. A managed worker descriptor is not an `ExecutionBackend`.
Registering a managed worker descriptor does not create a SafeLocalBackend
capability, does not create a substrate executable capability, and does not make
VM, container, microVM, remote, or simulation execution available.

Managed worker capability summaries must remain explicitly labeled:

- `contract_only=true`
- `non_executable=true`
- `future_worker=true`
- `executable_substrate_capability=false`
- `registered_execution_backend=false`

The current `/compute-substrate/capabilities` route reports executable substrate
capability truth only. It must not mix managed-worker metadata into executable
capability readback unless a later governance-reviewed contract adds a separate
bounded managed-worker metadata readback.

Durable managed-worker persistence remains future work. The current registry is
not production durable and is not a worker scheduler, queue, runtime, launcher,
or recovery mechanism.

Future managed worker implementations must attach through the existing Compute
Substrate authority path:

1. `TaskEnvelope`
2. `ResourceBudget`
3. approval store validation and consumption
4. `SubstrateGovernor`
5. `WorkerRegistry`
6. `ExecutionBackend` contract
7. receipt store
8. status store
9. API and adapter permission boundaries where applicable

No worker may bypass the substrate. The substrate governs whether work is
allowed. Future worker backends may prove how work ran, but they do not become
the governance truth layer.

## Contract Rules

The managed worker boundary is default-deny.

It denies:

- unsafe worker ids
- unsafe plan ids
- unsafe capability ids
- disabled workers
- unknown or unsupported worker kinds unless explicitly allowed by policy
- undeclared capabilities
- capabilities outside policy
- risk above policy
- runtime, memory, CPU, or compute-unit budgets above policy
- network requests unless explicitly allowed
- GPU requests unless explicitly allowed
- filesystem scope outside `none` unless explicitly allowed
- persistent storage unless explicitly allowed
- remote execution unless explicitly allowed
- shell requests
- approval-required downgrades
- missing explicit deadline context when policy requires it
- missing cancellation context when policy requires it
- missing receipt support when policy requires receipts
- missing status support when policy requires status records

Denial reasons are stable and testable. Plans store bounded summaries only.

## Bounded Data Requirements

Managed worker descriptors and plans must not store:

- raw `TaskEnvelope.payload`
- raw execution output
- secrets
- raw approval notes
- raw model prompts
- broad filesystem paths
- raw container image credentials
- raw environment variables
- host usernames
- USB paths
- `D:\Francis` runtime paths
- arbitrary user content beyond bounded summaries

Filesystem scope summaries may say that a non-default scope was requested, but
they must not echo broad host paths.

## Relationship To Existing Substrate Components

The managed worker layer does not replace `WorkerRegistry`. It defines future
worker obligations before a worker becomes an executable backend.

The managed worker layer does not replace `ExecutionBackend`. Future real
worker backends still need an explicit backend contract and must be registered
through the governed path.

The managed worker layer does not replace `ComputeAdapterGateway`. Adapters may
request work, but adapter validation remains separate from worker backend
validation. An adapter cannot become a worker just by declaring a worker kind.

The managed worker layer does not replace durable receipts, status records, or
approval stores. Future worker execution must still produce substrate receipts
and status truth through the existing persistence boundaries.

## Relationship To ADR 0005

ADR 0005 remains the OS/resource-enforcement design record. This ADR does not
choose or implement a resource enforcement mechanism.

Before any real managed worker execution is implemented, a later slice must
select and validate the relevant enforcement mechanism for the worker class. For
example:

- Windows local workers likely need Windows-native process-boundary validation.
- Container workers need container runtime policy, mount policy, network policy,
  output capture, cleanup, and receipt/status evidence.
- VM or microVM workers need image, launch, lifecycle, filesystem, network,
  secret, cleanup, and receipt/status evidence.
- Remote workers need network authority, identity, request signing, audit, and
  failure semantics before execution.

Resource enforcement remains a future implementation requirement. Current
managed worker plans report `contract_only=true`, `dry_run=true`, no process
start, no network use, no GPU use, no shell, no daemon, no real container
execution, no real VM execution, and no OS-level CPU/memory enforcement.

## Future Implementation Gates

Before real managed worker execution is allowed, Francis must have:

- selected OS/resource enforcement strategy for the worker class
- implemented the sandbox profile rather than only describing it
- resolved approval reservation semantics for multi-process or production use
- preserved API permission gates and adapter governance boundaries
- kept worker submission through `ComputeSubstrateService` and
  `SubstrateGovernor`
- extended receipts/status records with worker runtime evidence
- validated timeout, cancellation, termination, cleanup, and redaction behavior
- validated unsupported-platform behavior
- proved no raw payloads, outputs, secrets, approval notes, prompts, or broad
  host paths leak into durable records

## Testing Requirements Before Real Worker Execution

Future real worker slices must include tests for:

- worker registration without bypassing the governor
- approval-required execution with valid and invalid approvals
- timeout, cancellation, and kill/termination semantics at the claimed boundary
- OS-specific resource limits when such limits are claimed
- unsupported-platform denial or unavailable responses
- receipt/status evidence for enforcement attempted, active, unavailable, or
  failed
- no raw payload, raw output, secret, approval note, model prompt, broad path, or
  runtime credential persistence
- no hidden shell, unrestricted process launch, unrestricted network, GPU, daemon
  authority, or memory write

A mock-only test is not proof of OS-level resource enforcement.

## Non-Goals

This ADR and the matching contract slice do not implement:

- VM execution
- container execution
- microVM execution
- remote worker execution
- simulation worker execution
- real adapter implementation
- subprocess execution
- shell execution
- unrestricted process launch
- network client execution
- GPU execution
- daemon or background worker execution
- OS-level CPU enforcement
- OS-level memory enforcement
- process or thread preemption
- distributed locking
- cross-process approval reservation
- durable adapter persistence
- task recovery or resume
- production API exposure
- long-term memory persistence
- live-learning persistence
- model training
- autonomous learning

## Consequences

Francis now has a contract boundary that future worker implementations must
satisfy before they can attach to the Compute Substrate. This strengthens the
substrate without adding execution power.

The next substantive implementation should remain governance-first: either
review and harden this contract, or design a specific managed worker backend
contract for one enforcement mechanism. It should not jump directly into
container, VM, shell, or remote execution.
