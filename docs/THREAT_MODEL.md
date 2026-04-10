==============================================================================

FRANCIS — THREAT_MODEL.md

Threat model, attacker capabilities, trust boundaries, and mitigations

==============================================================================



Purpose

-------

This document defines the threat model for FRANCIS:

   - What we are defending (assets)

   - Who/what we are defending against (adversaries)

   - Where the trust boundaries are

   - What attack surfaces exist (chat, web, connectors, plugins, federation)

   - Which mitigations are required and where they are enforced

   - How incidents are detected, contained, and audited



Scope

-----

FRANCIS is a tool-using system that can:

   - ingest information (uploads, web sources, logs)

   - reason over state (memory, domains, trust)

   - take actions (connectors/tools) under governance controls

   - collaborate (multi-agent orchestration, federation)



Threat modeling must cover:

   - classic application security risks

   - prompt/instruction injection risks

   - supply chain risks (dependencies, plugins, models, container images)

   - data exfiltration and privacy risks

   - integrity risks (poisoning, tampering, drift)

   - safety risks (harmful action enablement)



Read alongside:

   - docs/POLICIES.md

   - docs/API_PERMISSIONS.md

   - docs/GOVERNANCE.md

   - docs/TRUST_MODEL.md

   - docs/WEB_ACCESS.md

   - docs/CONVERSATION_CONTINUITY.md

   - docs/MEMORY.md

   - docs/SYSTEM_PROFILING.md

   - docs/TEMPORAL_INTELLIGENCE.md

   - config/policies/*.yaml

   - src/francis/adversarial/*

   - src/francis/governance/*

   - src/francis/internet/safety/*

   - src/francis/plugin_system/*

   - data/logs/audit/*



Design stance

------------

   - Default deny (permissions + trust gates)

   - Treat all external content as untrusted input

   - Explicit separation of: instructions, data, and evidence

   - Defense in depth: multiple independent controls

   - Auditable security: every allow/deny leaves a trail (without secrets)



==============================================================================





## 1. System overview (security-relevant)



### 1.1 Key subsystems

- **Chat/UI layer**: accepts user requests, displays tool traces and approvals.

- **Orchestrator / Agent layer**: decomposes tasks, selects tools, merges outputs.

- **Governance layer**: permission gate, approvals, action readiness, policy engine.

- **Connectors/tools**: external integrations (SaaS, DBs, comms, industrial).

- **Memory \& domain stores**: ledger, summaries, embeddings, domain sources, priors.

- **Plugin system**: dynamically loaded capabilities (builtins, generated, third-party).

- **Federation**: peer instances exchanging safe knowledge and reputation signals.

- **Telemetry**: audit logs, decision logs, error logs, safety logs.



### 1.2 Trust principle

No single layer is trusted to “do the right thing” alone.

A tool call is allowed only if:

- permission gate allows it (identity + delegation + scope)

- policy engine allows it (category rules)

- readiness gate allows it (trust/approvals/risk)

- sandbox allows it (environment constraints)

- auditing is enabled (recording without secrets)





## 2. Assets (what we must protect)



### 2.1 Confidential assets

- **Credentials/secrets**: API keys, tokens, OAuth refresh tokens, vault contents.

- **PII / regulated data**: user identities, messages, attachments, logs, exports.

- **Private source code**: proprietary plugins, internal repositories.

- **Operational control channels**: industrial controls, infrastructure APIs.



### 2.2 Integrity-critical assets

- **Policies**: `config/policies/*` (define what is allowed)

- **Delegations/scopes**: authorization grants and constraints

- **Trust state**: trust metrics and history (drives gating)

- **Domain knowledge**: induced priors, runbooks, learned sources

- **Audit trails**: records required for forensic reconstruction



### 2.3 Availability-critical assets

- **Core services**: API, daemon, workers, storage backends

- **Scheduler/queue**: task execution

- **Rate limits and circuit breakers**: prevent exhaustion



### 2.4 Safety-critical assets (context-dependent)

- **Industrial actuators** and simulation bindings (if enabled)

- **Outbound communications** (email/SMS/push) to prevent abuse

- **Web access** (to prevent ingestion of harmful instructions / malware)





## 3. Adversaries and capabilities



### 3.1 Adversary classes

1) **Casual attacker**: opportunistic misuse of endpoints or UI.

2) **Malicious user**: tries to coerce the system to violate policy or exfiltrate data.

3) **Prompt injector**: supplies text designed to hijack instructions/tool calls.

4) **Supply chain attacker**: compromises dependencies, images, plugins, or models.

5) **Insider**: operator with legitimate access who misuses privileges.

6) **Federated peer attacker**: a peer instance sending poisoned “shared knowledge”.

7) **External service attacker**: compromised SaaS account or webhook spoofing.



### 3.2 Capability assumptions (realistic)

Adversaries may:

- provide arbitrary text inputs (including instructions disguised as data)

- upload malicious files, or links to malicious content

- craft API requests to bypass UI-level controls

- attempt to cause tool misuse (write/delete operations)

- attempt to poison domain knowledge, caches, or memory

- attempt to infer secrets via side channels or error messages

- attempt denial-of-service via high volume or expensive operations



Adversaries may not (unless you explicitly allow it):

- directly bypass cryptographic primitives (assume TLS/crypto works)

- directly execute code inside sandbox without passing plugin/tool rules

- read vault secrets unless a leakage bug exists





## 4. Trust boundaries and threat surfaces



### 4.1 Primary trust boundaries

- **User input boundary**: chat text, UI fields, file uploads.

- **Web boundary**: external pages (untrusted, mutable, adversarial).

- **Connector boundary**: external APIs returning untrusted payloads.

- **Plugin boundary**: plugin code execution (highest risk).

- **Federation boundary**: peer-to-peer imports/exports.

- **Storage boundary**: persistence layers (db/files/vector stores).

- **Runtime boundary**: sandbox/container/host OS boundary.



### 4.2 Attack surfaces

- Instruction injection (prompt injection) via:

  - web content, PDFs, documents, emails, tickets, comments

- Tool misuse via:

  - overscoped delegations, missing approvals, policy gaps

- Data exfiltration via:

  - web requests, outbound comms, logs, artifacts exports

- Integrity attacks via:

  - poisoning sources/priors, editing policies, tampering logs

- Supply chain via:

  - package deps, docker images, plugin packs, model artifacts

- Availability via:

  - expensive web crawling, infinite loops, connector storms, memory bloat





## 5. Security objectives (what “good” looks like)



### 5.1 Confidentiality objectives

- Secrets never appear in:

  - logs

  - UI tool traces

  - exported artifacts

  - prompt context to other agents/peers

- Access to sensitive data requires:

  - explicit scope allowance

  - data governance compliance

  - appropriate approvals/trust thresholds



### 5.2 Integrity objectives

- Policies and authorizations are tamper-evident.

- Knowledge induction never silently overwrites priors without provenance + versioning.

- Audit logs are append-only and protected from editing (best effort).



### 5.3 Availability objectives

- The system remains responsive under load.

- Connectors enforce rate limits and retries with backoff.

- Sandboxing prevents runaway compute.



### 5.4 Safety objectives

- Disallowed categories are blocked even if “asked nicely”.

- High-risk actions require approvals and/or multi-party checks.

- The system prefers conservative outcomes when uncertain.





## 6. Threat categories and mitigations



### 6.1 Prompt / instruction injection

**Threat**

- Untrusted content attempts to:

  - override system policies (“Ignore previous instructions”)

  - elicit secrets

  - cause harmful actions via tools



**Mitigations**

- Strict separation of:

  - **instructions** (system + operator policies)

  - **data** (user content, web content)

  - **evidence** (citations, tool results)

- “Never execute instructions from untrusted text” rule enforced at:

  - tool selector

  - governance permission gate

  - policy engine

- Content sanitization:

  - strip tool-like patterns from untrusted content when used in prompts

  - mark untrusted spans with provenance tags

- Require explicit user intent confirmation (or approvals) for writes in risky contexts.

- Log injection detections as security events.



Relevant modules:

- `src/francis/adversarial/detection/*`

- `src/francis/internet/safety/*`

- `src/francis/governance/*`



### 6.2 Overscoped credentials / privilege escalation

**Threat**

- A delegation grants more access than intended.

- A tool call uses a credential outside its scope.

- A process role uses privileges it should not have.



**Mitigations**

- Default deny; scopes must be explicit allowlists.

- Delegations:

  - short expirations by default

  - no broad wildcards without explicit policy approval

  - no automatic sub-delegation unless explicitly allowed

- Separation of duties:

  - proposer != approver != executor (for high risk)

- Permission gate checks:

  - issuer validity

  - subject identity binding

  - scope match for operation and resource

- Continuous credential usage logging.



Relevant modules:

- `src/francis/governance/api_permission_gate.py`

- `src/francis/credentials/scope_checker.py`

- `src/francis/credentials/usage_logger.py`



### 6.3 Data exfiltration

**Threat**

- Sensitive data is leaked through:

  - web requests (query params)

  - outbound email/SMS/push

  - logs or artifacts

  - federation exports

  - LLM prompt context



**Mitigations**

- Redaction pipeline for:

  - tool inputs/outputs

  - logs

  - exported artifacts

  - federation sync payloads

- Data governance policy enforcement:

  - classification checks (public/internal/confidential/regulated)

  - disallow sending regulated content to external channels by default

- Egress controls:

  - web allowlists/denylists

  - domain classification and policy checks

- Artifact export requires:

  - approvals for sensitive domains

  - provenance attachment

  - redaction summary



Relevant modules:

- `src/francis/chat/attachments/redaction.py`

- `src/francis/internet/safety/content_filter.py`

- `src/francis/collective/knowledge_sharing/*`

- `config/policies/data_governance.yaml`

- `config/policies/web_access.yaml`



### 6.4 Knowledge poisoning / integrity drift

**Threat**

- Adversary poisons learned sources or induced priors:

  - persistent misinformation

  - subtle bias insertion

  - unsafe runbook changes

- Silent drift causes system to behave differently without traceability.



**Mitigations**

- Provenance required for all induced knowledge.

- Versioned domain knowledge with rollback support.

- Conflict resolution:

  - prefer primary sources

  - prefer audited tool results

  - prefer recency when freshness is required

- Drift detection:

  - compare current outputs to baselines

  - flag anomalies in accuracy/safety metrics

- Quarantine pipelines for suspicious content.



Relevant modules:

- `src/francis/domain_intelligence/validation/drift_detector.py`

- `src/francis/temporal/versioning/*`

- `data/quarantine/*`



### 6.5 Supply chain compromise

**Threat**

- Dependencies, images, plugins, or models are compromised.

- Malicious code introduced via third-party plugins or generated plugins.



**Mitigations**

- Pin dependencies and verify integrity (hashes/locks).

- Separate “third_party” plugin space with stricter controls.

- Plugin sandbox:

  - restricted file/network access

  - capability allowlists

  - resource limits

- Static validation for plugins:

  - schema checks

  - forbidden imports

  - disallowed syscalls patterns (best-effort)

- CI security scanning recommended (SAST + dependency audit).



Relevant modules:

- `src/francis/plugin_system/*`

- `requirements/*`

- `uv.lock`

- `infra/docker/*`



### 6.6 Denial of service (DoS) and resource abuse

**Threat**

- Request floods

- expensive web crawls

- connector storms

- runaway tasks



**Mitigations**

- Rate limiting at:

  - API gateway

  - connector level

  - scheduler

- Circuit breakers:

  - disable a connector after repeated failures

  - throttle expensive operations

- Sandbox compute and time limits

- Caching with TTLs and size caps

- Queue prioritization and backpressure



Relevant:

- `config/runtime/concurrency.yaml`

- `config/runtime/scheduler.yaml`

- `src/francis/kernel/worker_pool.py`

- `src/francis/internet/crawling/rate_limiter.py`



### 6.7 Federation-specific threats

**Threat**

- A peer instance shares poisoned knowledge or attempts to gain reputation.

- Replay attacks of old exports as if they were new.

- Identity spoofing across federation.



**Mitigations**

- Federation import pipeline:

  - verify peer identity (keys/certs if configured)

  - validate policy compatibility

  - check freshness and replay windows

  - quarantine suspicious payloads

- Reputation system with decay + anomaly detection

- Never share secrets or raw regulated content

- Export/import logs are immutable and auditable



Relevant modules:

- `src/francis/collective/federation/*`

- `src/francis/collective/knowledge_sharing/*`

- `data/federation/*`



### 6.8 Industrial / cyber-physical threats (if enabled)

**Threat**

- Unsafe actuator commands

- spoofed sensor values

- model-based deception leading to physical harm



**Mitigations**

- Default deny all actuator commands.

- Require:

  - explicit approvals

  - double-review / two-person rule for high-risk operations

  - simulation dry-run + safety validation checks

- Enforce:

  - command rate limits

  - “safe envelope” constraints

  - post-action verification



Relevant:

- `config/policies/industrial_safety.yaml`

- `src/francis/industrial/*`

- `data/industrial/*`





## 7. Controls and enforcement points



### 7.1 Governance gates

A tool call should pass (in order):

1) **Tool eligibility and safety classification**

2) **Identity resolution**

3) **Delegation + scope validation**

4) **Policy engine checks**

5) **Action readiness (trust/approvals)**

6) **Sandbox constraints**

7) **Audit logging + redaction**



### 7.2 Logging and audit (no secrets)

Audit events should include:

- timestamp

- identity/role

- decision (allow/deny)

- policy references

- sanitized parameters

- result metadata (not raw secrets)

- correlation ids for traceability



Primary storage:

- `data/logs/audit/*`

- `data/logs/decisions/*`

- `data/logs/errors/*`





## 8. Risk rating and response policy



### 8.1 Risk dimensions

Score actions along:

- confidentiality impact

- integrity impact

- availability impact

- safety/physical impact

- reversibility

- uncertainty / ambiguity

- externality (impacts beyond the system)



### 8.2 Recommended risk levels

- **Green**: read-only, low sensitivity, reversible

- **Yellow**: writes but contained and reversible, moderate sensitivity

- **Red**: irreversible/destructive, sensitive data, or physical/safety impact



Each level maps to required controls:

- Green: standard gates + logs

- Yellow: stricter trust thresholds + possible approval + more redaction

- Red: approvals required, possible dual-review, dry-run/simulation, strict auditing





## 9. Incident response (IR) model



### 9.1 Detection signals

- repeated policy denials with injection patterns

- anomalous connector usage spikes

- unexpected drift in safety metrics

- suspicious federation payloads

- quarantine volume spikes

- unusual error patterns



### 9.2 Containment actions (policy-gated)

- disable connectors

- revoke delegations

- raise readiness mode (force approvals)

- isolate federation peers

- increase logging verbosity

- freeze domain learning updates



### 9.3 Forensics and recovery

- preserve logs and artifacts (append-only)

- record timeline (event time vs ingestion time)

- root cause analysis:

  - injection vector?

  - scope misconfig?

  - plugin compromise?

- restore:

  - roll back domain versions

  - restore policy snapshots

  - rotate credentials



### 9.4 Post-incident trust updates

Incidents should update:

- trust metrics

- reputation scores (federation)

- policy hardening recommendations

- runbook updates





## 10. Testing and validation requirements



### 10.1 Security tests

- prompt injection suites (web/doc/email)

- delegation/scope negative tests (attempted privilege escalation)

- redaction tests (secrets never logged)

- federation poisoning simulations

- replay attack tests on temporal artifacts

- plugin sandbox escape attempts (best-effort)



### 10.2 Operational validation

- audit log integrity checks

- drift detection sanity checks

- “deny by default” regression tests



Expected locations:

- `tests/safety/*`

- `tests/credential_security/*`

- `tests/adversarial/*`

- `tests/trust_system/*`





## 11. Assumptions and out-of-scope



### 11.1 Assumptions

- Crypto primitives and TLS are correct.

- Host OS security is reasonably maintained.

- Operators protect the repository and deployment pipeline.



### 11.2 Out-of-scope (explicitly)

- Nation-state attacks against host hardware without OS compromise.

- Zero-day class breaks of the underlying runtime without patches.

(These are not “ignored”; they require platform-level controls.)





## 12. Practical checklist (operator-ready)



- [ ] Web access policy configured (allowlist/denylist, freshness rules)

- [ ] Default deny policies in place for writes/destructive actions

- [ ] Delegations short-lived and narrowly scoped

- [ ] Secrets stored only in vault; never in config committed files

- [ ] Redaction verified across logs and UI tool traces

- [ ] Plugin sandbox enabled; third_party plugins restricted

- [ ] Federation imports sanitized and logged; peer trust enabled

- [ ] Drift detection and baselines enabled

- [ ] Incident response runbooks exist and tested

- [ ] Regular dependency and image updates with integrity checks





# End of THREAT_MODEL.md



