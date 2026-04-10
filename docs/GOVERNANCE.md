==============================================================================

FRANCIS — GOVERNANCE.md

Control plane for authority, approvals, safety review, and accountable action

==============================================================================



Purpose

-------

This document defines the governance system for FRANCIS — the rules, gates,

artifacts, and workflows that ensure:

   - Default-deny tool use (least privilege)

   - Explicit approvals for high-risk actions

   - Separation of duties (propose / review / approve / execute / certify)

   - Audit-grade traceability (immutable logs + evidence references)

   - Safe operation in regulated, safety-critical, and federated environments



Governance is a runtime control plane, not a policy PDF.

It must be enforceable by code and inspectable by humans.



Read alongside:

   - docs/API_PERMISSIONS.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/POLICIES.md

   - docs/WEB_ACCESS.md

   - docs/EXPLANATION_SYSTEM.md

   - config/policies/action_readiness.yaml

   - config/policies/approvals.yaml

   - config/policies/api_permissions.yaml

   - config/policies/offensive_security.yaml

   - config/policies/privacy.yaml

   - config/policies/data_governance.yaml

   - schemas/action_readiness.schema.json

   - schemas/action_request.schema.json

   - schemas/action_result.schema.json

   - src/francis/governance/*

   - src/francis/telemetry/audit.py

   - data/approvals/*



Design stance

------------

   - Governance is conservative by default: “no” is safe, “yes” must be earned.

   - Authorization (permission) and suitability (trust) are separate gates.

   - Humans are first-class governors, not fallback error handlers.

   - Every allow/deny decision must be attributable and reproducible.



==============================================================================





## 0) Governance in one page



A tool call or high-impact action in FRANCIS is allowed only if it passes:



1) **Permission Gate** (identity + scope + delegation)

2) **Policy Engine Gate** (rule evaluation for category-specific constraints)

3) **Action Readiness Gate** (risk/trust/approvals for *this* context)

4) **Sandbox Gate** (environment constraints, rate limits, dry-run constraints)

5) **Audit + Explanation** (immutable record, evidence references, safe rationale)



If any gate fails → deny + explain safely + log denial.



Governance artifacts are stored in:

- `data/approvals/*`

- `data/logs/audit/*`

- `data/logs/decisions/*`

- `data/artifacts/*` (reports/runbooks/explanations)





## 1) Concepts and definitions



### 1.1 Governance

**Governance** is the set of enforceable controls that determine:

- which actions can occur,

- under what constraints,

- who can authorize them,

- how they are audited,

- and how risk is managed in real time.



### 1.2 Authority vs approval vs trust

- **Authority**: who is *allowed* to do something (permission model).

- **Approval**: explicit authorization for a risky action/category (governance artifact).

- **Trust**: whether it is *wise* to do the action now, given uncertainty and risk.



All three can be required.



### 1.3 Action readiness

**Action readiness** is a context-aware go/no-go decision combining:

- action class risk,

- environment mode,

- sensitivity classification,

- trust level,

- approval status,

- operational constraints (dry-run, review required).



### 1.4 Separation of duties

A safety principle where different roles handle:

- propose,

- review,

- approve,

- execute,

- certify (optional).



This prevents single-actor failure modes.



### 1.5 Policy vs governance

- **Policy** = declarative rules describing what should be allowed.

- **Governance** = runtime system that evaluates policy and enforces decisions,

  producing auditable artifacts and user-visible explanations.





## 2) Governance layers (the control plane)



FRANCIS governance operates in layers:



### 2.1 Identity + permission layer

Ensures the requester has authority:

- identity is resolved (user/service/delegated)

- scope checks pass

- delegations validate (issuer, subject, expiration, constraints)



Primary code:

- `src/francis/governance/api_permission_gate.py`

- `src/francis/credentials/scope_checker.py`

- `src/francis/credentials/delegation.py`



### 2.2 Policy engine layer

Evaluates domain rules:

- privacy rules

- data governance rules

- offensive security rules

- filesystem/network constraints

- web access constraints



Primary code:

- `src/francis/governance/policy_engine.py`



### 2.3 Action readiness + approvals layer

Determines if the action is appropriate *now*:

- trust threshold for category

- approvals required (standard/emergency/regulated)

- dry-run required

- reviewer required

- two-person rule required



Primary code:

- `src/francis/governance/action_readiness.py`

- `src/francis/governance/approvals.py`



### 2.4 Sandbox + runtime enforcement layer

Ensures operational safety:

- rate limiting

- environment locks (airgapped, regulated, etc.)

- filesystem sandbox

- network restrictions

- tool circuit breakers



Primary code:

- `src/francis/plugin_system/sandbox/*`

- `src/francis/internet/safety/*`

- `src/francis/telemetry/*`



### 2.5 Audit + explanation layer

Ensures accountability:

- immutable audit events

- explanation artifacts referencing evidence, policy snapshots, gate outcomes

- redaction to avoid secret leakage



Primary code:

- `src/francis/telemetry/audit.py`

- `src/francis/explanation/*`





## 3) Governance pipeline (authoritative order)



The governance pipeline is executed for:

- tool calls,

- write operations,

- destructive operations,

- high-risk reads (regulated/PII),

- federation export/import,

- industrial simulation/actuation requests.



### 3.1 Standard pipeline steps



1) **Classify request**

   - action category (read/write/destructive/industrial/federation/etc.)

   - sensitivity classification

   - environment mode impact



2) **Resolve identity**

   - user session identity

   - service identity (daemon/worker)

   - delegated identity (if tool credential is attached)



3) **Permission gate**

   - default deny

   - validate delegation and scope for tool + resource + method



4) **Policy evaluation**

   - evaluate applicable policies:

     - `api_permissions.yaml`

     - `privacy.yaml`

     - `data_governance.yaml`

     - `offensive_security.yaml`

     - `filesystem.yaml`, `networks.yaml`, `web_access.yaml`

   - compute policy verdict + rationale



5) **Action readiness**

   - compute risk score / level

   - verify trust thresholds

   - require approvals if needed

   - impose additional constraints (dry-run, review, two-person rule)



6) **Sandbox + execution constraints**

   - rate limit

   - path whitelists

   - network allowlists

   - time windows

   - resource caps



7) **Execute**

   - tool call or action run



8) **Post-checks**

   - outcome validation

   - side-effect detection

   - rollback where applicable



9) **Audit + explanation**

   - record decision and execution trace

   - store artifacts

   - present safe explanation to UI





## 4) Approval system



### 4.1 What approvals are for

Approvals authorize:

- high-risk writes,

- destructive actions,

- regulated-data access,

- federation exports,

- industrial actions,

- emergency overrides.



Approvals are additive to permissions.

Even if permission allows, approval may still be required.



### 4.2 Approval types (recommended)

- **Standard approval**

  - routine high-impact actions with normal review

- **Emergency approval**

  - time-critical actions; may allow limited overrides

  - requires stricter audit logging and post-mortem

- **Regulated approval**

  - actions involving regulated data or safety-critical operations

  - requires higher trust and possibly two-person rule

- **Change management approval**

  - deployments, config changes, schema migrations



### 4.3 Approval artifact requirements

Every approval must include:

- approval id

- action category (or action hash)

- issuer identity (who approved)

- subject identity (who may execute)

- scope/resource constraints

- expiration

- rationale

- evidence references

- policy snapshot references

- optional: reviewer notes



### 4.4 Approval storage layout

Approvals live in:

- `data/approvals/pending/`

- `data/approvals/approved/`

- `data/approvals/rejected/`

- `data/approvals/emergency/`



Files should be immutable after approval; changes create new artifacts.



### 4.5 Approval binding strategies

Approvals can bind to:

- **category** (e.g., “send_email” in internal domain)

- **action hash** (exact action + parameters signature)

- **resource constraint** (repo/project/channel/database)

- **time window** (expires quickly)



More specific is safer.



### 4.6 Two-person rule (when required)

For high-risk actions, require:

- reviewer approval (independent)

- operator approval

- both recorded as separate artifacts



The readiness gate enforces this when configured.





## 5) Trust gates and readiness modes



### 5.1 Trust thresholds

Trust thresholds can be defined by:

- environment (regulated vs dev)

- action risk level

- data classification

- connector type (email, DB write, cloud admin)



Trust interacts with:

- historical success rates

- safety incidents

- policy violations

- review outcomes



Trust computation is defined in:

- `docs/TRUST_MODEL.md`

- `config/policies/trust_boundaries.yaml` (if used)



### 5.2 Readiness modes (recommended)

The action readiness engine should support modes such as:



- **observe**

  - no tool execution; planning and explanation only



- **dry_run**

  - execute only non-side-effect probes / validation steps



- **review_required**

  - generate plan + require reviewer before execution



- **execute_limited**

  - only allow read-only tools + low-risk operations



- **execute_full**

  - allow writes within scope + approvals



- **emergency**

  - allow narrowly-scoped high-impact actions with emergency approvals,

    extra logging, and automatic post-mortem trigger



### 5.3 Mode selection inputs

Mode selection is influenced by:

- environment profile (`config/environments/*.yaml`)

- policies

- trust score

- presence/absence of approvals

- action category and risk score





## 6) Risk model integration



Governance uses a risk model to:

- classify actions,

- require controls,

- and produce explainable gating decisions.



### 6.1 Risk factors (examples)

- irreversibility (delete vs read)

- blast radius (single record vs entire DB)

- sensitivity of data involved

- external communications (email/slack)

- credential scope breadth

- network exposure (web access enabled)

- automation level (autonomous vs human-approved)



### 6.2 Risk scoring output (recommended)

The readiness gate should output:

- risk_level: low/medium/high/critical

- risk_score: 0..1 (or 0..100)

- required_controls:

  - approvals

  - review

  - dry-run

  - two-person

  - post-checks

- recommended mitigations





## 7) Governance artifacts and logging



### 7.1 Audit log requirements

Every gated event must generate an audit event including:

- timestamp

- identity context (user/service/delegated)

- requested action/tool/operation

- policy snapshot references

- gate outcomes (permission/policy/readiness/sandbox)

- redaction flags

- result status

- artifact references (approval IDs, explanation IDs)



Audit logs must never contain secrets.



### 7.2 Decision logs vs audit logs

- **Audit logs**: low-level immutable trace for forensics.

- **Decision logs**: summarized outcomes with rationale and links.



### 7.3 Where logs live

- `data/logs/audit/*`

- `data/logs/decisions/*`

- `data/logs/errors/*`

- `data/logs/operations/*`





## 8) Governance for federation



Federation introduces unique risks:

- cross-instance data leakage

- trust spoofing

- poisoned knowledge import

- silent privilege escalation via shared artifacts



### 8.1 Export governance

Before exporting anything:

- classify data

- apply redaction rules

- ensure policies allow export

- require approval if necessary

- log export decision with evidence and constraints



### 8.2 Import governance

Before importing:

- validate provenance

- validate peer trust level / reputation

- sandbox imported data

- run safety and conflict checks

- annotate imported artifacts as external/untrusted



### 8.3 Federation-specific controls

- strict allowlist of shareable artifact types

- never share secrets or raw regulated data

- trust-weighted acceptance





## 9) Governance for industrial / safety-critical operations



Industrial operations require stricter controls:

- simulation validation before execution

- safety envelopes and constraints

- two-person approvals for actuation

- immediate rollback and emergency shutdown support

- constant telemetry monitoring



### 9.1 Conservative defaults

- disallow actuation by default

- require simulation proof for changes

- require certified policy profile (safety_critical)



### 9.2 Emergency shutdown

Emergency procedures must be:

- explicit

- permissioned

- audited

- reversible where possible





## 10) Human-in-the-loop workflows (UI requirements)



Governance must be visible and controllable by humans.



### 10.1 Approvals UI

Must show:

- pending approvals

- required approvals for current action

- reason for requirement

- constraints and expiration

- audit trail links



### 10.2 Gate inspector UI

For each attempted action:

- permission verdict + reason

- policy verdict + matched rules

- readiness verdict + required controls

- sandbox constraints applied

- redacted inputs/outputs

- link to explanation artifact



### 10.3 Safe explanation presentation

In the UI, explanations should be:

- structured

- short by default, expandable

- evidence-linked

- explicit about uncertainty





## 11) Common governance scenarios (runbook patterns)



### 11.1 “Write to external system” (email/slack/jira)

1) plan proposal

2) policy check (privacy + external comms)

3) require approval if configured

4) execute in constrained scope

5) audit + store message artifact (redacted)



### 11.2 “Production deploy”

1) require change-management approval

2) require review + dry-run checks

3) execute via deployment script tool

4) post-check health + rollback plan

5) write deployment report artifact



### 11.3 “Regulated data access”

1) verify identity + delegation scope

2) apply minimum necessary access

3) require regulated approval

4) log all queries and row-count limits

5) redact outputs aggressively



### 11.4 “Emergency containment”

1) emergency approval

2) execute narrowly-scoped mitigations

3) force post-mortem creation

4) strict audit logs





## 12) Failure modes and mitigations



### 12.1 Policy bypass attempts

Mitigation:

- mandatory gate ordering

- deny-by-default fallback

- centralized enforcement



### 12.2 Privilege creep

Mitigation:

- short delegation expiration defaults

- narrow scopes

- approval-binding to action hashes

- periodic permission audits



### 12.3 Silent drift / config misalignment

Mitigation:

- snapshot policy hashes in logs

- drift detection jobs

- require re-approval when policy changes materially



### 12.4 Audit log poisoning

Mitigation:

- append-only storage

- hashing/signing (optional)

- separate write path for audit events





## 13) Implementation map (code pointers)



- Permission gate:

  - `src/francis/governance/api_permission_gate.py`

  - `src/francis/credentials/scope_checker.py`

  - `src/francis/credentials/delegation.py`



- Readiness and approvals:

  - `src/francis/governance/action_readiness.py`

  - `src/francis/governance/approvals.py`

  - `src/francis/governance/risk.py`



- Policy engine:

  - `src/francis/governance/policy_engine.py`



- Explanations:

  - `src/francis/explanation/*`



- Audit:

  - `src/francis/telemetry/audit.py`

  - `src/francis/telemetry/logging.py`



- Web learning approvals:

  - `src/francis/governance/web_learning_approval.py`





## 14) Ship checklist (governance readiness)



- [ ] Default deny enforced for tools/connectors

- [ ] Permission gate logs allow/deny with safe rationale

- [ ] Policy engine evaluates all relevant policies by category

- [ ] Action readiness gate enforces approvals and review requirements

- [ ] Approvals stored immutably with identity + constraints + expiration

- [ ] Sandbox constraints active (network/filesystem/rate limits)

- [ ] Audit logs append-only with policy snapshot references

- [ ] UI exposes approvals and gate reasoning

- [ ] Emergency path exists but requires emergency approvals and post-mortem





# End of GOVERNANCE.md

