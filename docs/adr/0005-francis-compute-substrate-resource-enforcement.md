# ADR 0005: Francis Compute Substrate Resource Enforcement Options

Date: 2026-07-09

Status: Proposed design for future OS-level resource enforcement

## Context

Francis Compute Substrate is a core architecture layer under Phase 2
`P7_EXECUTION`. It already has typed resource budgets, approval scope checks,
worker registration, cooperative cancellation/deadlines, durable approvals,
durable compute receipts, durable status records, adapter contracts, and
internal/local-dev API routes.

The current substrate does not implement OS-level CPU enforcement, OS-level
memory enforcement, process preemption, thread killing, subprocess killing,
container isolation, cgroup enforcement, Windows Job Object enforcement, GPU
quota enforcement, or distributed resource scheduling. Current enforcement is
limited to truthful budget validation, default-deny network/GPU/filesystem
posture, cooperative timeout/deadline behavior, approval scope checks, and
bounded safe local backend functions.

This matters before Francis adds VM/container backends, remote workers,
simulation workers, real adapters, or production API exposure. Francis must not
claim that a budget field is the same thing as operating-system enforcement.

## Decision

Future OS-level resource enforcement requires a separate governance-reviewed
implementation slice. Until that slice exists and is validated, Francis must
continue to report resource control as:

- budget validation
- approval scope validation
- cooperative timeout/deadline observation
- default-deny network, GPU, and filesystem policy
- no OS-level CPU or memory preemption
- no OS-level process or thread kill semantics
- no production-grade scheduler isolation

Compute receipts, status records, API responses, adapter results, and docs must
not imply stronger enforcement than the runtime actually provides.

## Current Enforcement Truth

Current substrate behavior is intentionally narrow:

- `ResourceBudget` can express max runtime, memory budget, CPU weight, priority,
  network allowance, filesystem scope, GPU allowance, and approval requirement.
- The governor can reject tasks that exceed worker or adapter policy ceilings.
- Approval scopes can bind or cap budget values before execution.
- Safe local registered functions can observe cooperative cancellation and
  deadline state through execution context.
- Post-execution runtime and deadline overruns can be reported truthfully.
- Backend work is restricted to explicitly registered internal functions.

Current substrate behavior does not:

- cap process CPU through the operating system
- cap process memory through the operating system
- kill runaway code by OS mechanism
- isolate workers in containers or microVMs
- enforce GPU memory or GPU compute quotas
- throttle distributed workers
- reserve CPU or memory capacity across processes
- make local JSON stores production coordination primitives

## Enforcement Options

### Windows Job Objects

Windows Job Objects can place processes under an operating-system control group
with limits for process lifetime, memory, CPU rate, and child process handling.

Benefits:

- aligns with the primary local Windows laptop environment
- can bound child processes when workers eventually run out-of-process
- provides a plausible local-first enforcement path

Risks:

- requires workers to run in a process that Francis can assign to a job
- does not apply to in-process Python function calls
- CPU rate and memory behavior need Windows-specific validation
- lifecycle, nested jobs, crash cleanup, and handle ownership must be tested

### Subprocess Worker With Resource Limits

Francis can move risky work into a managed subprocess and apply platform-specific
limits around that process.

Benefits:

- creates a clear kill boundary
- makes timeout and process termination observable
- separates worker failure from the main API process

Risks:

- must not become arbitrary subprocess execution
- needs a strict command/capability allowlist
- requires output capture, redaction, receipt linkage, and cleanup semantics
- Windows and POSIX limit mechanisms differ

### Linux Cgroups

On Linux, cgroups can enforce CPU, memory, process, and IO limits for worker
processes or containers.

Benefits:

- strong fit for container and server deployment paths
- mature process-group enforcement model
- can support future VM/container backend contracts

Risks:

- not directly portable to the user's primary Windows local environment
- requires runtime privilege and host configuration decisions
- must not be represented as available on Windows when it is not

### Containers

Container runtimes can provide process, filesystem, network, CPU, and memory
boundaries for future worker backends.

Benefits:

- aligns with future VM/container backend contracts
- can isolate dependencies and filesystem scope
- can make resource ceilings easier to audit

Risks:

- container availability varies by machine
- Docker or compatible runtime policy becomes a dependency
- network, mount, and secret handling need separate governance
- container limits are not proof of production scheduling correctness by
  themselves

### MicroVMs

MicroVMs can create stronger isolation boundaries than standard local
subprocesses or many container configurations.

Benefits:

- strong separation for high-risk workers
- clear fit for future remote or sandboxed execution backends
- may support stronger filesystem and network isolation

Risks:

- materially higher implementation and operations complexity
- hardware and virtualization support vary
- startup latency and image management affect local-first ergonomics
- requires explicit backup, log, receipt, and cleanup design

### Process Priority And Affinity

Francis can lower process priority, bind CPU affinity, or adjust scheduling
class for worker processes.

Benefits:

- can reduce laptop impact for cooperative local work
- may be available without heavyweight isolation
- useful as a soft scheduling hint

Risks:

- not a hard CPU budget
- does not enforce memory limits
- behavior varies by OS and current system load
- must be reported as priority/affinity control, not isolation

### GPU Limits

Future GPU-enabled workers need separate policy for GPU visibility, memory use,
device selection, and acceleration authority.

Benefits:

- can make GPU use explicit and auditable
- protects the laptop from unexpected accelerator contention
- supports future model/tool routing honesty

Risks:

- GPU quota mechanisms are vendor and runtime specific
- local consumer GPUs often lack strong per-process memory enforcement
- allowing GPU work crosses a higher resource and thermal boundary
- receipts must distinguish GPU allowed, GPU requested, GPU used, and GPU
  enforceable

### Queue And Scheduler Throttling

Francis can place governed work behind a queue that enforces concurrency,
priority, rate, and admission controls.

Benefits:

- protects the laptop by limiting how much work starts at once
- works before full OS-level enforcement exists
- composes with approvals, receipts, and status readback

Risks:

- throttling is not the same as per-task CPU or memory enforcement
- queued tasks need cancellation, expiration, and handback semantics
- durable queue recovery must not be faked before implementation

## Windows And Local Laptop Reality

Francis is being built local-first on a Windows laptop. That environment makes
truthful boundaries more important:

- in-process Python work cannot be safely killed or memory-capped without
  risking the host process
- OS-level enforcement likely requires out-of-process workers
- Windows Job Objects are the most plausible native local hard-limit path
- containers or WSL-based cgroups may be useful but add setup and operational
  assumptions
- USB-hosted source code does not provide runtime durability, isolation, or
  resource enforcement
- thermal, battery, fan, GPU, and interactive desktop responsiveness should be
  treated as first-class operator constraints

Francis must not run "all the time" at high resource use. Future schedulers and
worker backends must default to conservative local budgets, low concurrency,
visible status, cancellation, and receipts.

## Receipt And Status Requirements

When OS-level enforcement is implemented, receipts and status records must
separate requested limits, validated policy, attempted enforcement, and observed
runtime evidence.

Minimum fields or summaries should include:

- requested runtime, memory, CPU, GPU, network, and filesystem budget
- validated budget after policy and approval checks
- enforcement backend selected
- enforcement mechanism attempted
- whether OS-level CPU enforcement was actually active
- whether OS-level memory enforcement was actually active
- whether GPU enforcement was actually active
- process or container boundary summary, without broad paths or secrets
- timeout, cancellation, kill, or termination stage
- exit category, without raw tracebacks or raw outputs
- whether enforcement setup failed before execution
- whether enforcement failed after execution started

If enforcement setup fails, Francis must deny or report failure according to the
contract. It must not silently fall back to weaker execution while claiming the
stronger resource boundary.

## Testability

Future implementation must include tests at the boundary it claims:

- budget validation remains covered by unit tests
- cooperative deadline behavior remains covered by deterministic local tests
- OS-specific enforcement gets platform-specific integration tests
- subprocess or worker kill behavior gets bounded timeout tests
- receipts/status records prove whether enforcement was active or unavailable
- unsupported-platform cases return bounded denial or unavailable responses
- no test should require arbitrary shell execution or broad filesystem access

Windows Job Object work should include Windows-native validation. Linux cgroup
or container enforcement should include Linux/container validation. A design or
mock test alone is not proof that OS enforcement works.

## Relationship To VM/Container Backends

VM/container backend contracts should attach as execution backends or adapter
gateways to the Compute Substrate. They must not bypass:

- `ComputeSubstrateService`
- `SubstrateGovernor`
- approval validation and consumption
- worker registry capability checks
- budget validation
- cancellation/deadline contracts
- durable receipt persistence
- durable status persistence
- API permission gates

VM/container workers may eventually provide stronger enforcement, but the
substrate remains the governance truth layer. The backend proves how work ran;
the substrate governs whether work was allowed and records what happened.

## Non-Goals

This ADR does not implement:

- Windows Job Objects
- cgroups
- containers
- microVMs
- subprocess workers
- process priority or affinity controls
- GPU enforcement
- queue execution
- scheduler throttling
- OS-level CPU enforcement
- OS-level memory enforcement
- process or thread kill semantics
- VM/container backend contracts
- real adapter execution
- production API exposure
- async/background execution
- task recovery or resume
- durable adapter persistence
- long-term memory persistence
- live-learning persistence
- model training

## Consequences

Francis can continue to improve the Compute Substrate without overstating its
resource controls. The next implementation that increases execution power must
either remain within the existing cooperative/local-safe model or implement a
specific enforcement mechanism with tests and receipt/status evidence.

The safest next resource-hardening implementation is likely a design-to-contract
slice for a managed worker boundary before any OS-specific enforcement code.
