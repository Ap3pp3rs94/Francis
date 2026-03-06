# Multi-Agent Architecture

## Purpose
Define how Francis operates as an internal swarm of specialized units on one machine/repository while preserving governance, traceability, and user control.

## What A Unit Is
A unit is an agent role implemented as a process/service with declared capabilities, bounded scope, and policy-constrained execution rights.

## Role Taxonomy
- Presence/Narrator: user-facing briefings, status framing, and handback summaries.
- Observer/Watcher: probes, anomaly detection, and signal emission.
- Mission Operator: mission planning, routing, and mission tick decisions.
- Forge Builder: proposes/scaffolds capabilities and prepares promotion candidates.
- Executor/Worker: executes queued actions with leases, retries, and receipts.
- Lens UI: control surface for mode/state/actions and operator visibility.

## Agent Lifecycle
- Register: unit announces identity, role, version, and trust level.
- Advertise capabilities: unit publishes supported actions, risk tiers, and required scopes.
- Accept tasks: unit receives routed tasks with scope, approval context, and idempotency keys.
- Report results: unit publishes status, artifacts, and receipts with `run_id` and `trace_id`.

## Coordination Model
- Orchestrator routes work to units using capability and policy constraints.
- Units communicate through an event bus/message router, not ad-hoc point-to-point calls.
- Cross-unit execution uses idempotency keys and leases to prevent duplicate work and race conditions.

## Receipts And Traceability
- Every inter-agent task includes `run_id`, `trace_id`, task identity, and risk metadata.
- Each unit writes decision/log artifacts so delegation paths are reconstructable end to end.
- Result artifacts must reference source task and produced outputs for audit replay.

## Failure Handling
- Deadletter queue stores undeliverable or repeatedly failed messages/tasks.
- Retry policy is explicit (attempt limits, backoff, terminal failure semantics).
- Timeouts and cancellation are first-class: units must stop or hand back with partial receipts.

## Acceptance Criteria
- [ ] Units register and advertise capabilities before receiving delegated tasks.
- [ ] Orchestrator routing is capability-based and policy-gated.
- [ ] Inter-agent tasks always propagate `run_id` and `trace_id`.
- [ ] Idempotency and lease semantics prevent duplicate execution across units.
- [ ] Failed messages/tasks are recoverable via deadletter + retry controls.
