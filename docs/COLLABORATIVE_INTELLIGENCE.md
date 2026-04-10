==============================================================================
FRANCIS — COLLABORATIVE_INTELLIGENCE.md
Multi-agent collaboration, delegation, consensus, and shared cognition
==============================================================================

Purpose
-------
This document defines how FRANCIS collaborates with:
   - Humans (operators/users)
   - Internal agents (workers/roles/specializations)
   - Federated peers (other FRANCIS instances)

It explains:
   - Delegation mechanics and authority boundaries
   - Consensus building and conflict resolution
   - Shared knowledge exchange (safe synchronization)
   - Collaboration safety: approvals, trust, and auditability
   - Practical collaboration patterns (runbooks, incident response)

Read alongside:
   - docs/API_PERMISSIONS.md
   - docs/TRUST_MODEL.md
   - docs/THREAT_MODEL.md
   - docs/GOVERNANCE.md
   - docs/POLICIES.md
   - docs/HUMAN_AI_SYMBIOSIS.md
   - docs/CONCURRENCY.md
   - docs/CONVERSATION_CONTINUITY.md
   - docs/WEB_ACCESS.md
   - config/policies/collaborative_trust.yaml
   - config/policies/approvals.yaml
   - config/policies/trust_boundaries.yaml
   - src/francis/collective/*
   - src/francis/agent/*

Design stance:
   - Collaboration is a capability multiplier and a risk multiplier.
   - Default to conservative coordination: explicit roles, explicit authority,
     measurable outcomes, and immutable audit trails.
   - "Many minds" without controls becomes "many ways to fail".

==============================================================================


## 0. Collaboration contract (executive summary)

FRANCIS collaboration is governed by **four non-negotiables**:

1) **No implicit authority**
   - No collaborator (human, internal agent, federated peer) can grant execution rights by suggestion.
   - Authority comes only from permissions + delegations + policy + approvals.

2) **No secret sharing**
   - Collaboration may share context and evidence, never credentials or sensitive payloads beyond policy.

3) **Audit-first execution**
   - Every cross-boundary act produces a durable trace: inputs (redacted), decisions, gates, outputs.

4) **Trust gates are real**
   - Even permitted actions can be blocked, downgraded, or forced into review/dry-run based on risk.


## 1. Definitions

### 1.1 Collaboration
A **collaboration** is any workflow where more than one actor contributes to a single outcome:
- human + FRANCIS
- multiple internal agents
- multiple federated instances

### 1.2 Actor
An **actor** is an entity that can contribute information, proposals, or actions:
- User / Operator (human)
- Service identity (api/daemon/worker)
- Internal agent role (planner/reviewer/etc.)
- Federated peer instance

Actors are always represented as **verifiable identity contexts**, not strings.

### 1.3 Delegation
A **delegation** is a bounded authorization grant to act with specific tools on specific resources under constraints.

Delegation is not “trust”; it is *authority with limits*.
Trust determines whether authority should be exercised now.

### 1.4 Consensus
**Consensus** is a structured method for combining multiple proposals and evidence into one outcome that:
- is coherent
- is policy-compliant
- is safe under uncertainty
- and is auditable

### 1.5 Shared cognition
**Shared cognition** means:
- shared context
- shared state
- shared evidence
- shared outcome tracking

It does **not** mean shared secrets.

### 1.6 Collaboration boundary
A **collaboration boundary** is the point at which information or authority crosses from:
- one identity → another
- one subsystem → another
- one instance → another

Boundaries require explicit governance:
- identity verification
- scope checks
- approval gates (when needed)
- audit events
- redaction rules

### 1.7 Collaboration artifact
A **collaboration artifact** is a durable record produced by collaboration:
- plan
- proposal set
- decision record
- approval record
- tool traces
- runbook
- export/import manifest


## 2. Collaboration layers in FRANCIS

FRANCIS supports collaboration at three layers:

### 2.1 Human ↔ System (mixed initiative)
- Users request goals.
- FRANCIS proposes plans and executes (as allowed).
- Humans approve or modify high-impact actions.

Primary interfaces:
- Chat UI (apps/chat_ui)
- Approvals workflow (data/approvals)

### 2.2 Internal collective (multi-agent orchestration)
- Specialized agent roles handle different tasks:
  - research
  - coding
  - safety review
  - industrial simulation
  - domain induction
- A coordinator merges results and resolves conflict.

Primary modules:
- `src/francis/agent/*`
- `src/francis/collective/*`

### 2.3 Federation (peer-to-peer knowledge exchange)
- Multiple FRANCIS instances coordinate on:
  - shared knowledge (sanitized)
  - reputation/trust signals
  - task splitting
  - redundancy / high availability

Primary modules:
- `src/francis/collective/federation/*`
- `src/francis/collective/knowledge_sharing/*`
- `data/federation/*`


## 3. Roles and responsibility model

Collaboration is safer when responsibilities are explicit.

### 3.1 Canonical roles (recommended)
- **Orchestrator**: coordinates execution and merges results
- **Planner**: decomposes goals into tasks + dependencies
- **Researcher**: gathers sources + evidence
- **Builder**: writes code/config/runbooks
- **Reviewer**: checks safety, policy compliance, correctness
- **Operator**: human-in-the-loop approval and oversight
- **Auditor**: post-hoc inspection and certification workflows

A single process may play multiple roles, but the UI and logs must preserve role context.

### 3.2 Separation of duties (high-risk default)
High-risk actions should not allow a single role to:
1) propose a risky plan
2) approve it
3) execute it
4) certify it

Conservative flow:
- Builder proposes
- Reviewer validates
- Operator approves (if required)
- Executor runs
- Auditor records and certifies

### 3.3 Two-man rule (irreversible actions)
For destructive or high-impact actions:
- require **two independent reviewer attestations** OR
- one reviewer + one operator approval, depending on policy
- record both attestations in the decision artifact


## 4. Collaboration lifecycle

Treat collaboration like a transaction with an explicit lifecycle:

1) **Intake**
   - collect goal + constraints
   - classify sensitivity
   - assign a collaboration id

2) **Plan**
   - generate candidate strategies
   - enumerate risks + required approvals

3) **Task decomposition**
   - create tasks with clear outputs
   - assign tasks to roles/agents

4) **Execution**
   - run allowed operations
   - record tool traces and artifacts

5) **Synthesis**
   - merge outputs
   - resolve conflicts
   - cite evidence

6) **Review**
   - policy compliance checks
   - safety review
   - correctness checks

7) **Commit**
   - deliver outcome
   - export runbooks/reports if requested

8) **Retrospective**
   - update trust metrics
   - record lessons learned
   - optionally update domain knowledge


## 5. Delegation in collaborative workflows

### 5.1 Delegation is explicit and scoped
Delegations must include:
- subject identity
- issuer identity
- scope constraints
- expiration
- audit linkage

### 5.2 Delegation propagation rules
A delegated agent cannot automatically sub-delegate unless explicitly allowed.

If sub-delegation is allowed, the new delegation must:
- narrow scopes (never broaden)
- shorten expiration (never extend)
- add constraints (never remove)
- attach parent delegation reference

### 5.3 Delegation revocation
All delegations must be revocable.
Revocation should immediately:
- block tool execution
- invalidate cached sessions
- write an audit record
- optionally trigger containment steps if active executions exist

### 5.4 Delegation chain-of-custody (required fields)
A delegation (or delegation event) must be traceable:
- `delegation_id`
- `issuer_identity`
- `subject_identity`
- `scope_ids`
- `created_at`, `expires_at`
- `parent_delegation_id` (optional)
- `approval_refs` (optional)
- `reason`
- `signature` (or integrity token)


## 6. Consensus model

FRANCIS uses consensus when:
- multiple agents disagree
- multiple sources conflict
- multiple execution plans exist
- federated peers provide competing recommendations

### 6.1 Decision object (minimum schema)
Every consensus decision must generate a decision artifact including:

- `decision_id`
- `timestamp`
- `collaboration_id` (if applicable)
- `participants`: list of {identity, role, trust_level}
- `inputs`: normalized problem statement + constraints
- `candidates`: list of proposals
- `evidence`: list of evidence items (with provenance)
- `policy_checks`: pass/fail + policy refs
- `risk_assessment`: risk class + rationale
- `approval_requirements`: required/waived + why
- `final_decision`: selected proposal + execution intent
- `confidence`: numeric + qualitative band
- `dissent`: minority report(s), if any

### 6.2 Consensus methods (select based on risk)

**Low risk**
- majority vote (weighted by competence + recency)
- simple ranking with tie-breakers

**Medium risk**
- evidence-weighted scoring
- explicit conflict resolution rules (see 6.3)

**High risk**
- default to conservative outcome
- require human approval
- optionally require two-man rule for irreversible actions

### 6.3 Conflict resolution rules
When outputs conflict:
1) prefer primary sources over secondary summaries
2) prefer audited tool results over web content
3) prefer more recent evidence if freshness matters
4) if still ambiguous → abstain / require operator decision / require approval

### 6.4 Trust-weighted participation
Participation is weighted by:
- trust level of the agent/instance
- historical accuracy on similar tasks
- policy compliance record
- evidence quality

Weighting must be transparent in logs and explainable in the UI.

### 6.5 Reference scoring model (illustrative)
This is an example scoring approach (not a mandated implementation):

- Evidence score (0–1): provenance strength, primary-ness, internal tool trace availability
- Trust score (0–1): trust system output for agent/peer on task class
- Recency score (0–1): freshness relevance for the domain

`proposal_score = 0.55*evidence + 0.35*trust + 0.10*recency`

If risk is high, apply a **conservatism penalty** for proposals with:
- irreversible actions
- broad scopes
- weak verification steps


## 7. Shared knowledge exchange (federation-safe)

### 7.1 What can be shared
Allowed (subject to policy):
- public domain sources and citations
- abstracted lessons learned (no secrets)
- derived embeddings or indexes only if policy allows and provenance is kept
- capability outcomes (success/failure metrics)
- non-sensitive runbooks/templates

### 7.2 What must never be shared
- credentials, tokens, secrets
- raw PII or regulated data
- internal-only documents unless explicitly authorized
- proprietary code unless policy allows distribution
- anything classified beyond federation sharing policy

### 7.3 Sanitization pipeline (export/import)
Before exporting:
1) classify payload + attachments
2) redact prohibited fields
3) minimize: prefer summary + provenance over raw dumps
4) attach provenance metadata (source IDs, timestamps)
5) write an export decision audit event

On import:
1) validate manifest integrity
2) validate peer trust threshold
3) run content safety checks
4) store in quarantine first if uncertain
5) only promote to active knowledge store after validation

### 7.4 Export manifest (recommended)
Every export should include a manifest (example):

```json
{
  "export_id": "exp_2026_01_01_0001",
  "timestamp": "2026-01-01T00:00:00Z",
  "peer_target": "francis://peer-instance-123",
  "classification": "internal",
  "contents": [
    {"type": "runbook", "path": "data/artifacts/runbooks/runbook_foo.md", "redacted": true},
    {"type": "metrics", "path": "data/trust/metrics/success_rates.json", "redacted": false}
  ],
  "policy_refs": ["config/policies/data_governance.yaml", "config/policies/trust_boundaries.yaml"],
  "decision_ref": "dec_...",
  "signature": "..."
}
