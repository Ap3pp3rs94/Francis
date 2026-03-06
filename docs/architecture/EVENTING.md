# EVENTING

## Inter-Agent Events and Federated Messages
Francis eventing must support both internal multi-agent coordination and federated multi-node communication under one observable contract.

### Internal Event Flow
- Internal units publish/consume events through the orchestrated event-driven reactor.
- Cross-unit delegation carries `run_id`/`trace_id` plus scope and risk metadata.
- Idempotency and leases prevent duplicate execution across unit boundaries.

### Federated Message Flow
- Node-to-node communication follows explicit pairing/trust contracts.
- Message transport is denied-by-default unless node scope grants it.
- Replicated state is domain-scoped and excludes secrets/unscoped telemetry.

### Canonical References
- Multi-agent architecture: [MULTI_AGENT.md](D:/francis/docs/architecture/MULTI_AGENT.md)
- Federation architecture: [FEDERATION.md](D:/francis/docs/architecture/FEDERATION.md)
- Message envelope and delivery contract: [MESSAGING.md](D:/francis/docs/architecture/MESSAGING.md)
