# Managed Copies Model

## Purpose
Define the business and operating model for scaling Francis without transferring core IP ownership.

## Core IP Principle
- The core Francis platform is retained and operated by the owner.
- Francis is delivered as managed, customer-specific isolated copies.
- Commercial value is service delivery, reliability, and governed autonomy.

## Customer Copy Isolation
- Each customer copy has isolated runtime state, policies, and connectors.
- Scope boundaries are tenant-specific and auditable.
- Cross-copy data access is denied by default.

## Service Fee Model
- Recurring fees cover copy creation, hosting, support, and policy maintenance.
- Premium tiers can include faster SLAs, advanced governance controls, and priority upgrades.
- Optional add-ons can cover federation/remote approval infrastructure and enhanced hardening.

## Federated Deltas (No Raw Data)
- Global improvements ingest only approved deltas (capability metadata, eval outcomes, anonymized patterns).
- Raw customer artifacts, secrets, and private telemetry are never replicated into core learning paths.
- Delta ingestion is policy-gated and receipted.

## Rogue Detection and Kill/Replace
- Detect anomalies such as repeated critical halts, scope escapes, or policy bypass attempts.
- Trigger immediate kill/revocation workflow for compromised copy behavior.
- Rebuild from clean baseline plus approved global state and tenant policy profile.
- Provide full incident and recovery receipts.

## SLA and Tiering Concepts
- Tier 1: standard support, scheduled updates, baseline governance.
- Tier 2: priority response, expanded observability, accelerated patch windows.
- Tier 3: premium protections including advanced rogue containment and continuity options.

## Acceptance Criteria Checklist
- [ ] Core Francis IP remains centrally controlled and is not sold as transferable ownership.
- [ ] Customer copies are isolated by default with audited scope boundaries.
- [ ] Federated learning consumes deltas only, never raw customer data.
- [ ] Rogue kill/replace workflow is documented, tested, and receipted.
- [ ] SLA tiers map clearly to operational guarantees and governance posture.
