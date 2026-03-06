# Swarm and Federation

## Purpose
Define how Francis coordinates specialized internal units and federated nodes while preserving user sovereignty, scope boundaries, and receipts.

## Internal Multi-Unit Swarm
### Roles
- Presence/Narrator unit
- Observer/Watcher unit
- Mission Operator unit
- Forge Builder unit
- Executor/Worker unit
- Lens UI unit

### Delegation Etiquette
- Delegate by capability and scope fit, never by convenience alone.
- Include objective, constraints, risk tier, and verification requirements.
- Preserve `run_id`/`trace_id` across all handoffs.
- Return results with artifacts and confidence labels.

## Message Envelope Contract
Inter-unit and inter-node messages use a canonical envelope with:
- `id`
- `ts`
- `from`
- `to`
- `kind`
- `run_id`
- `trace_id`
- `risk_tier`
- `scope`
- `payload`

Optional metadata may include `role`, `idempotency_key`, and attempt counters.

## Federation Model (Multi-Node)
### Pairing and Zero Trust
- Node pairing requires explicit user consent and short-lived pairing material.
- Device fingerprints are verified before trust activation.
- Default is deny-all until scoped permissions are granted.

### Revocation and Recovery
- Node or capability trust can be revoked instantly.
- Revocation blocks dispatch and invalidates affected leases.
- Recovery requires explicit re-pairing or policy re-authorization.

### Replication Boundaries
- Replicate allowed summaries: mission state, incident summaries, ledger summaries.
- Keep secrets, raw private files, and unscoped telemetry local.
- Cross-node conflicts use domain rules and ownership leases, not naive last-write-wins.

## Acceptance Criteria Checklist
- [ ] Swarm roles and delegation rules are explicit and auditable.
- [ ] Every cross-unit message carries `run_id`, `trace_id`, `risk_tier`, and `scope`.
- [ ] Federation is zero-trust by default and requires explicit pairing.
- [ ] Revocation interrupts unauthorized dispatch immediately.
- [ ] Replication boundaries prevent secrets or out-of-scope telemetry leakage.
