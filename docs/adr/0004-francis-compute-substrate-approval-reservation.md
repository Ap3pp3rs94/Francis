# ADR 0004: Francis Compute Substrate Approval Reservation Semantics

Date: 2026-07-09

Status: Proposed design for future production/multi-process approval safety

## Context

The Francis Compute Substrate supports internal approval consumption through `ApprovalStore`, `InMemoryApprovalStore`, and `LocalJsonComputeApprovalStore`.

The durable local JSON approval store provides bounded local persistence and tested sequential single-use consumption. It does not implement cross-process atomic reservation, distributed locking, or production-grade multi-process approval coordination.

This matters before Francis promotes the Compute Substrate API beyond internal/local-dev use or adds VM/container backends, remote workers, real adapters, or background execution. Approval grants prove why Francis was allowed to attempt execution. If multiple processes can consume the same single-use grant concurrently, approval truth becomes unsafe.

## Decision

Production or multi-process approval-required execution must not rely on the current local JSON approval consumption semantics alone.

Before production/multi-process use, Francis needs an explicit approval reservation contract that can atomically move a grant from available to reserved or consumed for exactly one governed execution attempt.

Current posture:

- local JSON durable approval persistence exists
- sequential single-process tests exist
- cross-process atomic reservation is not implemented
- distributed locking is not implemented
- rollback/resume semantics are not implemented
- production/multi-process API posture is deferred until reservation semantics are implemented and validated

## Required Future Semantics

A future approval reservation implementation must define:

- which actor or service may reserve an approval
- what task, correlation, capability, worker, risk, and budget scope are bound to the reservation
- when a reservation is created
- when a reservation becomes consumed
- how cancellation before execution start releases or records the reservation
- how deadline expiry before execution start releases or records the reservation
- how failure after execution start preserves consumed truth
- how receipts link approval reservation, consumption, execution start, and final status
- how stale reservations are detected
- whether stale reservations can be repaired, expired, or manually reviewed
- how errors are reported without leaking raw approval notes, task payloads, paths, tracebacks, or secrets

Single-use approval consumption should remain aligned with the current substrate truth model: once execution is allowed to start, approval consumption is evidence for the attempt even if backend execution fails, times out after start, or returns an error. Francis must not fake rollback of an approval that already authorized a started attempt.

Pre-execution cancellation or pre-execution deadline expiry may avoid consumption only when the future reservation protocol can prove execution did not start. If that proof is unavailable, the system must fail conservatively and report the ambiguity.

## Possible Implementation Options

### File Lock

Use an OS file lock around approval grant read/validate/write.

Benefits:

- closest to current local JSON store
- minimal new infrastructure
- can preserve local-first operation

Risks:

- Windows and POSIX lock behavior differs
- lock timeout and crash recovery need careful design
- network or USB filesystem behavior may be unreliable
- does not provide distributed coordination across machines

### SQLite Transaction

Move durable approvals into SQLite and use transactions for reservation and consumption.

Benefits:

- atomic updates are a native fit
- easier query/readback for approval history
- can model reserved, consumed, expired, and revoked states

Risks:

- migration from local JSON needs a compatibility plan
- database corruption/backup/restore policy must be explicit
- still local unless paired with a larger deployment model

### Single Process Authority Service

Route all approval reservation and consumption through one local authority process.

Benefits:

- avoids multi-writer file races
- keeps policy centralized
- aligns with a future local operator-grade control plane

Risks:

- service availability becomes part of execution readiness
- restart and recovery semantics must be defined
- not sufficient for distributed/multi-machine execution by itself

### OS-Native Lock

Use platform-specific locking such as Windows named mutexes or file handles.

Benefits:

- can be strong on a single machine
- may fit local-first Windows operation

Risks:

- platform-specific behavior increases complexity
- tests must cover Windows realities
- does not solve distributed reservation

### Database-Backed Reservation

Use a database with row-level locking or compare-and-swap semantics.

Benefits:

- clearer production path
- can support multi-process and possibly multi-host coordination
- stronger audit/readback options

Risks:

- adds deployment dependency
- backup, retention, migration, and secret management become larger
- must not be introduced as fake production readiness without operational proof

## Failure Semantics

Future reservation must fail closed when:

- approval ID is unsafe
- grant is missing
- grant is expired or revoked
- grant is already reserved by another active attempt
- grant is already consumed
- scope does not match task, correlation, capability, worker, risk, or budget
- reservation store is unavailable
- reservation write fails
- reservation state is corrupt or ambiguous

Responses and receipts must use bounded stable reasons. They must not include raw approval notes, raw task payloads, raw execution outputs, raw model prompts, broad filesystem paths, tracebacks, or full exception details.

## Receipt And Status Linkage

Capability receipts must show approval truth separately from execution truth:

- approval was required
- approval was found and valid
- approval was reserved, if reservation exists
- approval was consumed, if execution was allowed to start
- approval denial reason, if denied
- approval reservation or persistence failure, if applicable
- whether cross-process reservation was enforced

Status records may summarize the same truth for readback, but status persistence must not replace receipt evidence.

## Non-Goals

This ADR does not implement:

- file locks
- SQLite stores
- authority service
- OS-native locks
- database-backed reservation
- distributed locking
- cross-process approval reservation
- approval rollback
- task recovery or resume
- async/background execution
- VM/container execution
- real adapter execution
- production API exposure
- long-term memory persistence
- live-learning persistence
- model training

## Consequences

Francis remains honest about current approval guarantees: durable local approval persistence exists, but production/multi-process approval reservation does not. Future execution expansion must implement and test one of these reservation paths before treating approval-required multi-process work as production safe.
