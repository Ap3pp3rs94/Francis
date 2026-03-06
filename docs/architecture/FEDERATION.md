# Federation Architecture

## Purpose
Define how multiple Francis nodes coordinate safely across devices/services while keeping user sovereignty, explicit scope, and auditable control.

## What A Node Is
A node is a Francis instance with a stable device identity, role profile, capability set, and policy-bound trust scope.

## Pairing Model (Explicit User Consent)
- Generate pairing token on initiating node with short TTL and intended trust scope.
- Verify node fingerprints out-of-band before trust is established.
- Establish trust contract: "this node may only do X" with explicit scope and revocation metadata.

## Zero-Trust Defaults
- No remote mutating action is allowed without explicit node permissions.
- Messages are encrypted in transit and signed for authenticity (conceptual contract).
- Trust and capabilities are revocable at any time without redeploying nodes.

## Shared State Strategy
### Replicable State
- Mission summaries/progress state.
- Incident summaries and escalation metadata.
- Ledger summaries and delegation receipts.

### Local-Only State
- Secrets and credential material.
- Private files outside granted scopes.
- Unscoped telemetry and raw sensitive artifacts.

## Conflict Resolution
- Last-write-wins alone is insufficient; each domain must define merge semantics.
- Missions use ownership + lease contracts across nodes to avoid split-brain execution.
- Conflicts produce explicit review records and a deterministic reconciliation path.

## Away-Mode Continuity
- Always-on node can run night-shift operations within delegated scope.
- Primary workstation can sleep/offline without losing mission momentum.
- Return briefings summarize deltas, unresolved conflicts, and pending approvals.

## Acceptance Criteria
- [ ] Pairing requires explicit user consent, token exchange, and fingerprint verification.
- [ ] Remote permissions are scoped, revocable, and denied-by-default.
- [ ] Replicated data excludes secrets and unscoped private telemetry.
- [ ] Cross-node mission execution uses ownership/leases to prevent double execution.
- [ ] Away-mode progress is resumable with full receipts and pending approval queues.
