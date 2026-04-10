==============================================================================

FRANCIS — POLICIES.md

Unified policy framework: governance, safety, privacy, access, execution constraints

==============================================================================



Purpose

-------

This document defines the policy framework for FRANCIS:

   - What “policy” means in FRANCIS and how it differs from permissions/trust

   - Where policies live (config vs runtime vs data artifacts)

   - How policies are evaluated, versioned, audited, and enforced

   - How policies interact with: permissions, trust, approvals, sandbox, web access

   - How to add/modify policies safely (especially in regulated/safety-critical modes)



Read alongside:

   - docs/ARCHITECTURE.md

   - docs/API_PERMISSIONS.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/GOVERNANCE.md

   - docs/RUNBOOK.md

   - docs/WEB_ACCESS.md

   - docs/ATTACHMENTS.md

   - config/policies/*.yaml

   - meta/*.yaml (policy axioms / risk model / evidence model)

   - schemas/*.schema.json

   - src/francis/governance/policy_engine.py

   - src/francis/governance/risk.py

   - src/francis/telemetry/audit.py



Where to look
-------------

   - PHILOSOPHY.md (Canonical source of truth for taxonomy + gates)
   - meta/risk_model.yaml (computable taxonomy mirror)
   - meta/capabilities.yaml (capability registry)
   - schemas/delegation_token.schema.json (delegation token shape)
   - tools/policy_term_lint.py (terminology lint; not executed here)

Design stance
------------
Design stance

------------

   - Policy is the system’s *constitution*: stable, explicit, enforceable.

   - Default deny for dangerous actions and unknown situations.

   - Policies must be machine-enforceable and auditable (no “vibes-based” rules).

   - Enforcement is defense-in-depth: permissions + policy + trust + sandbox.

   - When policies conflict, the system must resolve conservatively and log why.



==============================================================================





## 1. What policy is (and is not)



### 1.1 Policy vs permissions

- **Permissions** answer: *“Is the identity authorized to do this?”*

- **Policy** answers: *“Is this category of action allowed under our rules, given

  the environment, data sensitivity, risk posture, and constraints?”*



An identity might have permission to call a tool, but policy can still block it.



### 1.2 Policy vs trust

- **Trust** answers: *“Should we do this now, given uncertainty and risk?”*

- **Policy** is rule-based and deterministic (as much as possible).

Trust can increase scrutiny or require approvals, but policy defines the hard lines.



### 1.3 Policy vs approvals

- **Approvals** are governance artifacts authorizing specific actions/categories.

- Policies can **require** approvals for certain risk classes or contexts.



Approval does not override absolute prohibitions unless an explicit emergency

policy path exists.



### 1.4 Policy vs sandbox

- **Sandbox** enforces execution constraints at the runtime boundary (OS/network/fs).

- Policy determines what should be allowed; sandbox makes bypass harder and limits blast radius.



Policy drives sandbox profile selection.





## 2. Policy sources of truth (where rules live)



### 2.1 Config policy files

Primary policy definitions live in:

- `config/policies/*.yaml`



Examples (typical roles):

- `action_readiness.yaml` — execution mode gates, required reviews, “dry-run” defaults

- `api_permissions.yaml` — cross-checks tool eligibility + scope expectations

- `approvals.yaml` — approval types, requirements, workflow rules

- `credential_usage.yaml` — credential handling, rotation rules, logging requirements

- `data_governance.yaml` — data classification, retention, export/redaction rules

- `filesystem.yaml` — allowed path rules, write constraints, quarantine behaviors

- `guard.yaml` — high-level safety boundaries (content/action categories)

- `human_safety.yaml` — physical safety constraints for actions affecting people

- `industrial_safety.yaml` — safety-critical controls for industrial toolchains

- `networks.yaml` — network allowlists, airgapped constraints, egress restrictions

- `offensive_security.yaml` — restrictions on exploit/weaponization activities

- `privacy.yaml` — PII handling, minimization, retention, consent constraints

- `regulated_domains.yaml` — special constraints for regulated sectors

- `sandbox.yaml` — sandbox profiles and enforcement expectations

- `trust_boundaries.yaml` — trust thresholds and cross-boundary rules

- `web_access.yaml` — web fetching constraints, citations, blocked domains behavior



### 2.2 Meta-policy and axioms

Foundational “why” and shared definitions live in:

- `meta/*.yaml`



Examples:

- `risk_model.yaml` — risk taxonomy, severity definitions

- `evidence_model.yaml` — evidence categories, provenance rules

- `internet_safety_model.yaml` — web safety boundaries

- `trust_model.yaml` — trust computation expectations

- `axioms.yaml` — invariants that should not be violated



Meta-policy is not necessarily directly enforced at runtime, but is used by:

- policy compilation

- risk scoring

- guardrails

- audits and explanations



### 2.3 Runtime policy snapshot

At runtime, FRANCIS should bind the session to a **policy snapshot**:

- policy version identifiers (hashes)

- environment profile (dev/regulated/airgapped)

- enabled plugins/tools

- sandbox profile set



This prevents “silent policy drift” mid-session and supports audit reproducibility.



### 2.4 Policy artifacts (audit + decisions)

When policy blocks or permits an action, the decision should generate artifacts:

- audit events (immutable log entries)

- decision rationale references

- policy rule references (rule ids)

- redacted parameter and outcome summaries



Typical storage:

- `data/logs/audit/*`

- `data/logs/decisions/*`

- `data/state/snapshots/*` (optional)





## 3. Policy evaluation pipeline (high level)



A proposed action (tool call) must pass:



1) **Classification**

   - Determine action category (read/write/delete/execute)

   - Determine risk tier (Low/Medium/High/Catastrophic)

   - Determine reversibility (Reversible/Partially reversible/Irreversible)

   - Determine authority confidence (Certain/Probable/Uncertain)

   - Determine evidence grade (Instrumented/Primary/Multi-source/Single/Unverified)

   - Determine data sensitivity (Public/Internal/Confidential/Regulated)

   - Determine environment mode (dev/regulated/airgapped/etc.)

Risk taxonomy and gating rules: see [PHILOSOPHY.md#Gating rules](../PHILOSOPHY.md#gating-rules) (canonical source of truth). Key gates include: high-impact requests with evidence below Primary require review/block; irreversible actions with authority confidence below Certain are blocked except for carefully controlled dry-runs; and regulated-data web accesses demand explicit approvals plus a redaction path.



2) **Eligibility**

   - Is this tool allowed in this environment?

   - Is this operation permitted by policy? (e.g., web fetch disabled in airgapped)



3) **Constraints**

   - Apply thresholds and limits:

     - rate limits

     - max payload sizes

     - max DB rows

     - allowed domains/paths

     - time windows



4) **Cross-policy checks**

   - Privacy policy checks

   - Offensive security restrictions (if applicable)

   - Data governance (export/retention/redaction)

   - Filesystem and quarantine rules

   - Network egress rules



5) **Approvals requirement evaluation**

   - Determine whether approvals are required

   - Validate approval artifact presence/validity



6) **Trust/readiness gate**

   - Determine whether to deny, dry-run, or allow with monitoring



7) **Sandbox profile selection \& enforcement**

   - Confirm selected sandbox profile complies with policy constraints



8) **Audit + explanation**

   - Emit “allow/deny” audit event with safe explanation

   - Store a policy decision record linked to request context





## 4. Policy model: rules, priorities, and conflict resolution
### 4.1 Rule structure (recommended)

A practical rule format (conceptual):



- `rule_id` (stable)

- `scope` (tools/operations/resources/categories)

- `conditions`

  - environment mode

  - trust level threshold

  - data classification

  - time windows

  - actor identity type (user/service/federated peer)

- `effect` (`allow` | `deny` | `require_approval` | `require_review` | `dry_run_only`)

- `constraints`

  - rate limiting

  - payload limits

  - allowlists (domains/paths/resources)

- `rationale` (human-readable)

- `audit_level` (minimal/standard/full)

- `references` (docs or external compliance mapping)



### 4.2 Priority order (recommended default)

When multiple policies apply:

Policy precedence: see `PHILOSOPHY.md` (Canonical source of truth; section 7.5).



1) Safety-critical prohibitions (human_safety / industrial_safety)

2) Regulated domain constraints (regulated_domains)

3) Privacy constraints (privacy + data_governance)

4) Offensive security constraints (offensive_security)

5) Network/filesystem constraints (networks + filesystem + sandbox)

6) Tool-specific policy (api_permissions + plugin metadata)

7) Action readiness and trust boundary (action_readiness + trust_boundaries)



If any higher-priority policy denies, the decision is deny.



### 4.3 Conflict resolution principles

- Prefer **deny** over allow in ambiguous conflicts.

- Prefer **more restrictive constraints** when merging.

- Log conflicts explicitly (policy_conflict events) with rule_ids involved.

- If an explicit emergency override exists:

  - require emergency approval

  - require increased audit verbosity

  - constrain blast radius (timeouts, allowlist narrowing)







### 4.4 Supervised-exec policy contract

- **Exit codes:** `0` for allowed commands, non-zero when denied.

- **Decision line:** supervised-exec writes one machine-parseable line per run to `stderr` in the exact form `DECISION: <ALLOW|DENY> reason="<reason>" artifact="<artifact id?>"` (uppercase verdict, sanitized reason text, optional artifact id); helpers must consume it once and avoid duplicates.

- **Log routing:** structured policy logs stay on `stderr`; stdout is reserved for pure JSON/decision data.

- **Validation:** the executed process must exactly match the provided `--cmd`; special operators only pass through when already in that string.

- **Audit:** include any related artifact/log identifier on the decision line instead of repeating gating text.

Wrappers that capture the CLI output may need to synthesize this line when the CLI's `stderr` stream is empty, but they must still emit exactly one `DECISION:` line (on `stderr`) so the JSON on `stdout` remains clean.
## 5. Environment profiles (policy bundles)



Environment profiles define “policy presets”:

- dev

- production

- regulated

- safety_critical

- airgapped

- federated

- workstation

- edge

- high_availability

- home



Stored in:

- `config/environments/*.yaml`



### 5.1 Example differences by environment

**Dev**

- broader tool enablement

- verbose logs

- less strict approvals (still required for destructive actions)



**Regulated**

- strict data governance

- mandatory redaction for artifacts

- approvals required for external communication and exports

- stronger retention rules



**Airgapped**

- web access disabled (or routed to internal mirrors only)

- strict network egress deny

- local-only connectors allowed



**Safety-critical**

- safety-critical tool calls require:

  - explicit approval

  - dry-run capability (if possible)

  - postcondition verification

  - “two-man rule” review for irreversible operations



Environment policies should be visible in UI and recorded in audit snapshots.





## 6. Data governance policy (where compliance lives)



Policy must define:

- data classifications (Public/Internal/Confidential/Regulated)

- allowed flows:

  - ingestion

  - processing

  - storage

  - export

  - federation sharing

- retention limits per class

- redaction requirements

- encryption-at-rest expectations (especially for secrets/vault)



Key principles:

- **minimize**: don’t store what you don’t need

- **segregate**: separate sensitive classes physically/logically

- **provenance**: keep track of where data came from

- **auditability**: record decisions without leaking payloads



Artifacts/locations:

- `data/uploads/*` (intake)

- `data/artifacts/*` (outputs)

- `data/conversations/*` (summaries/ledger)

- `data/web_knowledge/*` (web content cache and block logs)





## 7. Web access policy



Web access is not “just another tool.” It is a high-risk ingestion channel.



Policy should define:

- whether web access is enabled by environment

- allowed domain categories and allowlists/denylists

- rate limiting, caching behavior

- citation requirements

- content filtering:

  - malware/suspicious content quarantine

  - misinformation detection thresholds

  - harmful content blocking (safety model)

- extraction constraints (avoid executing embedded code, avoid downloads unless approved)



Storage:

- `data/web_knowledge/cache/web_pages/*`

- `data/web_knowledge/blocked/harmful_content_log.jsonl`

- `data/quarantine/*` (if suspicious payloads are captured)





## 8. Offensive security policy



Even benign “security research” can drift into weaponization.



Policy should:

- restrict exploit development and operational instructions

- allow defensive actions (detection, remediation, safe guidance)

- require approvals for activities that increase capability to harm

- log and label any suspicious intent patterns



Enforcement points:

- tool eligibility checks

- content filter on prompts/instructions

- output verifier for security-sensitive tools

- approvals + trust gating





## 9. Filesystem and secrets policy



### 9.1 Filesystem policy

Define:

- allowed read roots

- allowed write roots

- quarantine directories

- restricted patterns (e.g., system dirs, credentials)

- max file sizes for reads/writes

- symlink traversal rules (recommended: deny by default)

- extension-based handling (binary vs text)



### 9.2 Secrets policy

Define:

- where secrets live (e.g., vault db)

- how they are referenced (never inline in prompts/logs)

- rotation expectations

- redaction and logging rules

- access rules by environment and role



Note:

- Secrets should never appear in:

  - conversation summaries

  - audit logs

  - generated reports

  - plugin specs





## 10. Sandbox policy (execution containment)



Sandbox policy must define:

- sandbox profiles by risk class and tool category

- process isolation expectations

- timeouts and resource limits

- network allowlists

- file allowlists

- environment variables exposure rules

- logging and trace requirements



Safety-critical and critical tools should:

- have stricter sandbox profiles

- have mandatory postcondition checks

- have constrained egress and filesystem access





## 11. Federation and cross-boundary policy



Federation introduces:

- identity uncertainty

- different policy stacks

- data exfiltration risk

- reputation manipulation



Policy must define:

- what can be shared

- what must never be shared

- trust requirements for peers

- sanitization pipeline and provenance requirements

- audit requirements for export/import events





## 12. Policy versioning, change control, and auditability



### 12.1 Versioning strategy (recommended)

Policies should be versioned by:

- git commit hash

- plus a compiled policy hash (for runtime snapshot)



### 12.2 Change control

For high-risk environments:

- policy changes require review approvals

- changes should be rolled out with:

  - staged environments

  - canary runs

  - rollback plan



### 12.3 Policy drift detection

FRANCIS should detect:

- policy file changed since session start

- registry changed (tools enabled/disabled)

- environment changed



If drift is detected:

- require re-approval for pending high-risk actions

- emit drift audit event

- display in UI





## 13. Operator-facing explanations (safe transparency)



When policy denies:

- Provide an explanation that is:

  - actionable (what to change)

  - safe (no secret leakage)

  - auditable (rule references)

- Suggest alternatives:

  - dry-run

  - reduced scope

  - narrower resource target

  - request approval with justification



When policy allows:

- Still log the decision and show key constraints:

  - rate limits

  - allowlists

  - redactions

  - sandbox profile





## 14. Consent and capabilities (aligned to PHILOSOPHY)

- Consent is operational and capability-based.
- Canonical capability manifest and delegation token shape: see `PHILOSOPHY.md` (Canonical source of truth).
- Risk taxonomy and gates: see `PHILOSOPHY.md` (Canonical source of truth).
- Policy must check capability + risk tier before execution.

## 15. Implementation pointers (code map)



- Policy evaluation:

  - `src/francis/governance/policy_engine.py`

- Risk assessment:

  - `src/francis/governance/risk.py`

- Permission gate:

  - `src/francis/governance/api_permission_gate.py`

- Trust gate:

  - `src/francis/trust/*`

- Sandbox enforcement:

  - `src/francis/plugin_system/sandbox/*`

- Audit trail:

  - `src/francis/telemetry/audit.py`

  - `src/francis/telemetry/logging.py`





## 15. Appendix: example policy rule (illustrative)

```yaml

rule_id: web_access_regulated_default_deny

description: Deny arbitrary web access in regulated mode unless allowlisted.

applies_to:

  tools: ["web.fetch", "web.search", "web.open"]

conditions:

  environment: ["regulated", "safety_critical"]

effect: deny

constraints:

  allowlist_domains: ["docs.vendor.com", "standards.org"]

rationale: >

  Web access can ingest untrusted content and enable data exfiltration. In

  regulated mode, only allow web sources that have been reviewed/allowlisted.

audit_level: full

references:

  - docs/WEB_ACCESS.md

  - config/policies/web_access.yaml
```




## 16. Terminology lint

Run a lightweight check to keep terminology canonical.

Command:

```bash
python tools/policy_term_lint.py
```

Checks:

- Canonical enumerations match PHILOSOPHY.md and meta/risk_model.yaml.
- The three gating rules are present in PHILOSOPHY.md and referenced here.
- Capability manifest required fields are canonical (ignores `*_legacy`).
- Capabilities use canonical tier casing in meta/capabilities.yaml.

Notes:

- The lint is read-only; it does not modify files.
- *_legacy fields are allowed but excluded from strict matching.

Location: `tools/policy_term_lint.py`.

## 17. Capabilities manifest (canonical)

- Canonical capability manifest: `meta/capabilities.yaml`.
- Legacy alias: `meta/capability_manifest.yaml` (pointer only; do not edit).
- Tools and docs should reference `meta/capabilities.yaml` for capability definitions.
- Gating rules (must be reflected in implementation and lint): see [PHILOSOPHY.md#Gating rules](../PHILOSOPHY.md#gating-rules) for the canonical text.

## 18. Policy sanity check (read-only)

- Run locally (PowerShell): `powershell -ExecutionPolicy Bypass -File tools/policy_check.ps1`
- What it validates (read-only):
  - Canonical enumerations and gating rules align with PHILOSOPHY.md and meta/risk_model.yaml.
  - Capability manifest uses the canonical `meta/capabilities.yaml` (alias file is pointer-only).
  - Delegation token schema title/description references capabilities/consent/delegation terms.
  - Legacy alias (`meta/capability_manifest.yaml`) does not contain duplicate capability data.
- Exits non-zero on failure or missing python/script; does not modify files or runtime behavior.

## 19. Domain learner readiness and results

- Trigger via CLI: `python tools/run_domain_learner.py --domain <name> [--require-eval] [--min-scenarios N]` (default N=3, override with `--min-scenarios` or `DOMAIN_LEARNER_MIN_SCENARIOS`).
- UI trigger: Settings → Domain learner (domain, threshold, optional sources, require-eval toggle). Results and readiness errors surface in the Settings panel.
- Require-eval readiness: needs at least N scenarios and non-empty knowledge sections (`procedures.md`, `hazards.md`, `compliance.md`, `models.md`); empty/TODO fails fast with a structured error and non-zero exit.
- Artifacts: `data/knowledge/{domain}/` (evaluation_report.json/md, tests/scenarios.json) plus logs under `data/logs/operations/`.
- Activity: domain_learner events include domain, score, pass/fail, scenario count, and evaluation report path; visible in Activity screen and backend logs.


