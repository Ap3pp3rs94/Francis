# Messaging Contract

## Purpose
Define the canonical message envelope and delivery semantics for internal unit coordination and federated node communication.

## Message Envelope
Each message uses a standard envelope with these fields:
- `message_id`
- `ts`
- `from`
- `to`
- `role`
- `kind`
- `run_id`
- `trace_id`
- `payload`
- `risk_tier`

## Delivery Semantics
- At-least-once delivery is the baseline.
- Idempotency keys are required to make repeated deliveries safe.
- In-flight work uses leases with explicit expiry, renewal, and recovery semantics.

## Routing
- Capability-based routing: agents/nodes advertise capabilities and accepted scopes.
- Priority queues separate urgent incident traffic from routine operational work.
- Routing decisions include policy and approval context, not only capability match.

## Audit And Journaling
- All messages are journaled into workspace logs with receipt metadata.
- Message status transitions (queued, leased, done, failed, deadlettered) are auditable.
- `run_id` and `trace_id` propagation is mandatory across every hop.

## Acceptance Criteria
- [ ] Envelope fields are present and machine-validated at ingress.
- [ ] At-least-once delivery plus idempotency prevents duplicate side effects.
- [ ] Lease semantics exist for in-flight messages/tasks.
- [ ] Capability-based routing and priority handling are explicit.
- [ ] Message journaling is complete enough for end-to-end audit replay.
