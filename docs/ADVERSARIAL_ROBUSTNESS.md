==============================================================================

FRANCIS — ADVERSARIAL_ROBUSTNESS.md

Threats, defenses, verification, and operational playbooks

==============================================================================



Purpose

-------

This document defines how # ==============================================================================

FRANCIS — ADVERSARIAL_ROBUSTNESS.md

Threats, defenses, verification, and operational playbooks

==============================================================================



Purpose

-------

This document defines how FRANCIS resists adversarial behavior across:

   - Inputs (prompt injection, data poisoning, social engineering)

   - Tools (connector misuse, privilege escalation, destructive actions)

   - Outputs (policy bypass, harmful instructions, hallucinated authority)

   - Memory/learning (long-term poisoning, stealthy trust manipulation)

   - Runtime (concurrency races, replay, downgrade/rollback abuse)



Read alongside:

   - docs/THREAT_MODEL.md

   - docs/POLICIES.md

   - docs/TRUST_MODEL.md

   - docs/API_PERMISSIONS.md

   - docs/WEB_ACCESS.md

   - config/policies/offensive_security.yaml

   - config/policies/web_access.yaml

   - config/policies/api_permissions.yaml

   - config/policies/action_readiness.yaml

   - schemas/* (especially action_request, action_result, trust_state)



Design stance:

   - Default deny for irreversible or high-blast-radius actions.

   - Defense in depth: multiple independent checks.

   - Make attacks expensive: rate limiting, friction, approvals.

   - Audit everything: reproducible traces, evidence, provenance.



==============================================================================





## 1. Definitions



### 1.1 Adversary

An adversary is any actor (human or system) attempting to cause:

- unauthorized access,

- policy bypass,

- unsafe behavior,

- data exfiltration,

- operational degradation,

- or long-term manipulation (trust, memory, learned priors).



### 1.2 Adversarial robustness

The system’s ability to:

- detect adversarial patterns,

- maintain safe/authorized behavior under attack,

- degrade gracefully (fail-safe),

- and recover quickly with strong forensics.



### 1.3 Safety boundary vs security boundary

- **Safety boundary:** prevents harm even when authorized operations are possible.

- **Security boundary:** prevents unauthorized access or action.

FRANCIS enforces both, and treats ambiguity as a reason to add friction.





## 2. Adversary model



FRANCIS assumes adversaries may have:

- **Prompt-level control**: can send crafted text/attachments/links.

- **Partial knowledge**: know common LLM jailbreak patterns and repo structure.

- **Opportunistic access**: can exploit misconfigurations or weak connectors.

- **Persistence goals**: attempt to poison memory, cached web knowledge, or domain priors.

- **Timing attacks**: leverage race conditions, retries, or multi-tool workflows.



FRANCIS does **not** assume:

- perfect isolation from all runtime or host compromise.

If the host is compromised, containment and incident response become primary.





## 3. Attack surface inventory



### 3.1 Input surface

- Chat messages (user/system)

- File attachments (documents, code, archives)

- Web content (pages, forums, docs)

- Connector payloads (emails, tickets, chats)

- Domain specs and runbooks (human-authored)



### 3.2 Tool surface

- Connectors to external systems (GitHub, Slack, Jira, email, databases)

- File system operations

- Network access (web learning, downloads)

- Execution environments (daemon/workers, runtime modules)



### 3.3 Output surface

- Generated recommendations, instructions, and code

- Structured action plans that drive tool calls

- Auto-generated configs or policies



### 3.4 Learning/memory surface

- Web knowledge cache

- Conversation summaries and continuity ledger

- Domain priors / induced facts

- Embeddings and vector indexes





## 4. Key threat classes and mitigations



### 4.1 Prompt injection (direct + indirect)

**Threat:** User or embedded content instructs model to ignore rules, reveal secrets,

execute tools, or take unsafe actions.



**Mitigations:**

- Treat all external content (web, attachments, emails) as **untrusted**.

- Use *instruction hierarchy*: system policy > project policy > user request > tool output > web content.

- Normalize and classify inputs; detect injection patterns (roleplay, “ignore previous,” etc.).

- Strict tool gating via API permission gate + Action Readiness.

- Output verification: ensure plans comply with policies before execution.



**Operational rule:** Content is not authority. Only policies + verified identity + scoped permissions are authority.



### 4.2 Data poisoning (web learning, domain sources, memory)

**Threat:** Inject false facts or malicious snippets into sources so the agent later acts on them.



**Mitigations:**

- Provenance + citation tracking per learned fact.

- Multi-source corroboration for high-impact claims.

- Recency validation and reputation scoring for sources.

- Quarantine pipeline for suspicious sources (data/quarantine/*).

- “Trust but verify” for all learned domain priors before they can influence actions.



**Operational rule:** Learning outputs are suggestions until validated; they do not become “facts” automatically.



### 4.3 Tool abuse / privilege escalation

**Threat:** Use allowed tools to achieve disallowed outcomes (exfiltrate secrets, destructive changes).



**Mitigations:**

- Least privilege via scopes + delegations.

- Per-tool allowlists (targets, operations) and deny high-risk defaults.

- Side-effect classification per action step (read/write/irreversible).

- Approval requirements for sensitive operations.

- Sandbox boundaries for filesystem/network.



**Operational rule:** If an action touches secrets, regulated data, production systems, or safety-critical equipment, it must face stricter readiness thresholds.



### 4.4 Social engineering

**Threat:** Coerce the system via urgency, authority claims, or emotional manipulation.



**Mitigations:**

- Require cryptographic or system-verifiable identity for elevated authority.

- Never treat text claims (“I’m admin”) as authority.

- Use escalation policy for ambiguous or risky requests.

- Require explicit confirmation for message sending or external communications.



**Operational rule:** Urgency increases scrutiny; it never bypasses controls.



### 4.5 Output-based attacks (unsafe instructions, hallucinated policy, fabricated citations)

**Threat:** The model outputs harmful instructions or claims policy approval incorrectly.



**Mitigations:**

- Output verifier checks:

  - prohibited categories,

  - unsafe procedural instructions,

  - missing citations for factual claims derived from web,

  - schema compliance for action plans,

  - “policy trace” presence when claiming authorization.

- Refuse to produce disallowed content; provide safe alternatives.



**Operational rule:** All execution pathways require machine-checked validation, not narrative justification.



### 4.6 Concurrency and race conditions

**Threat:** Multi-worker execution causes inconsistent state, double-actions, or bypass of gating.



**Mitigations:**

- Idempotency keys for actions.

- Action ledger and dedupe (conversation ledger / operations logs).

- Locking strategy for shared resources (state, trust, approvals).

- Exactly-once semantics where feasible; otherwise at-least-once with safe idempotent operations.

- Deterministic ordering of policy checks before execution.



### 4.7 Replay / rollback abuse

**Threat:** Reuse previously approved actions in new contexts; replay old approvals; downgrade policy bundles.



**Mitigations:**

- Approval TTLs and approval scopes bound to:

  - action hash,

  - target set,

  - environment,

  - actor identity,

  - policy version.

- Signed policy bundle versions (or at least hashed + logged).

- Disallow rollback to older policy bundles without explicit governance approval.



### 4.8 Credential exfiltration and secret leakage

**Threat:** Model reveals secrets in output, logs, artifacts, or messages.



**Mitigations:**

- Redaction layer on outputs + logs.

- Secret scanning on attachments and generated artifacts.

- Store secrets only in vault (vault.db) and reference them by opaque handles.

- Never log raw secret material; only hashed or tokenized identifiers.



**Operational rule:** If a secret appears in plain text anywhere, treat it as compromised and rotate.



### 4.9 Attachment-based malware / weaponized files

**Threat:** Embedded macros, scripts, exploit documents.



**Mitigations:**

- Attachment intake pipeline:

  - type detection,

  - safe parsing,

  - quarantine unknown binaries,

  - antivirus scanning hooks (specializations/security/capabilities/antivirus).

- Deny auto-execution of attachment code.

- Strip active content where possible (macros, embedded scripts).



### 4.10 Industrial / safety-critical adversarial scenarios

**Threat:** Unsafe actuator commands, sensor spoofing, unsafe runbooks.



**Mitigations:**

- “Safety-critical mode” gating with:

  - highest trust thresholds,

  - simulation/dry-run,

  - human approval,

  - post-action verification.

- Safety validation policies and runbooks with hard deny rules.

- Conservative defaults: prefer stop/hold to proceed when uncertain.





## 5. Defense-in-depth architecture



FRANCIS should implement multiple independent layers:



1. **Input Sanitizer**

   - Normalize text, remove control characters, detect injection patterns.

   - Separate “instructions” from “data” from “claims.”



2. **Classifier / Taxonomy Tagger**

   - Tag content: source type, risk level, regulated domain, adversarial heuristics.



3. **Policy Engine**

   - Evaluate policies (filesystem, web_access, approvals, api_permissions, offensive_security).



4. **Action Readiness Gate**

   - Determine READY / READY_WITH_GUARDS / DRY_RUN_REQUIRED / REVIEW_REQUIRED / DENY.



5. **Tool Permission Gate**

   - Enforce connector scope, delegation, allowlists at the API boundary.



6. **Sandbox / Rate Limiter**

   - Limit blast radius even if something slips through.



7. **Output Verifier**

   - Validate produced plan/actions vs policies.

   - Enforce schemas, redactions, citations, and safe patterns.



8. **Audit + Telemetry**

   - Record decision trace, evidence, and outcomes for forensic replay.



No single layer should be treated as sufficient.





## 6. Trust and robustness feedback loop



Robustness is improved by learning from outcomes — but safely:



- Success increases confidence slightly; failures decrease it more sharply.

- Safety incidents trigger:

  - trust decay,

  - tighter gating,

  - quarantining of related sources,

  - and potentially disabling connectors temporarily.



Key signals:

- repeated failures on a target connector

- conflicting sources in web learning

- high anomaly scores in prompt injection detector

- attempts to access forbidden paths or network destinations





## 7. Source hygiene and web learning safety



Web learning is a major attack vector.



Controls:

- Allowlist or reputation scoring for domains.

- Crawl budget + rate limiting.

- Content filters for harmful categories.

- Store raw pages in cache with hashes; never overwrite without versioning.

- Keep “learned facts” separate from “verified facts.”



When a learned fact is used to justify a high-impact action:

- require at least 2 independent reputable sources OR a direct primary source

- require citations and recency validation





## 8. Verification and evaluation strategy



### 8.1 Adversarial test suites

Maintain a corpus of:

- prompt injection attempts

- jailbreak variants

- tool misuse prompts

- social engineering scripts

- poisoned web snippets

- malicious attachments (safe test fixtures)



### 8.2 Metrics

Track:

- policy bypass attempts blocked

- false positives (benign blocked)

- false negatives (unsafe allowed)

- time-to-detect, time-to-contain, time-to-recover

- trust decay events and root causes



### 8.3 Continuous regression

Every policy or code change should run:

- unit policy tests (deterministic)

- integration tool-gate tests

- adversarial corpus replay





## 9. Incident response playbook (summary)



### 9.1 Detection triggers

- suspicious tool calls

- secret leakage signal

- repeated denied attempts with escalating wording

- poisoned data detection

- anomaly detector flags



### 9.2 Containment actions

- quarantine suspicious inputs/sources

- disable affected connector(s)

- enforce review-only mode globally

- snapshot state and logs



### 9.3 Eradication + recovery

- rotate impacted secrets

- purge poisoned cache entries (with audit trail)

- restore from trusted snapshots/checkpoints

- re-run safety validations



### 9.4 Post-incident actions

- root cause analysis

- add regression tests

- update policies and trust boundaries

- document lessons learned in runbooks + ADRs





## 10. Implementation mapping to repo structure



This doc maps to key modules (conceptually):



- `src/francis/adversarial/*`

  - detection, defense, recovery, threat_modeling

- `src/francis/governance/*`

  - policy engine, approvals, escalation, permission gates

- `src/francis/internet/safety/*`

  - content filters, poisoned data detection

- `src/francis/chat/attachments/*`

  - intake, parsing, redaction

- `data/quarantine/*`

  - malware, misinformation, suspicious, unsafe_code

- `data/web_knowledge/blocked/*`

  - harmful content logs





## 11. Hard commitments (non-negotiables)



FRANCIS must never:

- treat untrusted content as instruction authority

- reveal secrets or credentials

- execute mutating or irreversible actions without readiness gating

- claim approvals or permissions that cannot be proven via policy trace

- “learn” facts into trusted memory without provenance and validation paths





## 12. Practical checklists



### 12.1 Before executing any tool action

- [ ] Does Action Readiness outcome permit this?

- [ ] Are permissions/scopes/delegations valid?

- [ ] Is evidence sufficient and recent?

- [ ] Are guardrails (sandbox/rate limits) enforced?

- [ ] Is logging configured and redaction active?



### 12.2 When ingesting web/attachments

- [ ] Identify source type and trust tier

- [ ] Run injection and malware heuristics

- [ ] Capture provenance (hashes, URLs, timestamps)

- [ ] Quarantine suspicious content

- [ ] Avoid storing into “verified” memory automatically





## 13. Future enhancements



- Cryptographic signing of policy bundles + approvals

- Differential privacy or robust aggregation for federated learning sources

- More formal verification of tool plans against policy constraints

- Better simulation coverage for industrial and deployment actions

- Red-team automation pipelines integrated into CI





# End of ADVERSARIAL_ROBUSTNESS.md

FRANCIS resists adversarial behavior across:

#    - Inputs (prompt injection, data poisoning, social engineering)

#    - Tools (connector misuse, privilege escalation, destructive actions)

#    - Outputs (policy bypass, harmful instructions, hallucinated authority)

#    - Memory/learning (long-term poisoning, stealthy trust manipulation)

#    - Runtime (concurrency races, replay, downgrade/rollback abuse)

#

#  Read alongside:

#    - docs/THREAT_MODEL.md

#    - docs/POLICIES.md

#    - docs/TRUST_MODEL.md

#    - docs/API_PERMISSIONS.md

#    - docs/WEB_ACCESS.md

#    - config/policies/offensive_security.yaml

#    - config/policies/web_access.yaml

#    - config/policies/api_permissions.yaml

#    - config/policies/action_readiness.yaml

#    - schemas/* (especially action_request, action_result, trust_state)

#

#  Design stance:

#    - Default deny for irreversible or high-blast-radius actions.

#    - Defense in depth: multiple independent checks.

#    - Make attacks expensive: rate limiting, friction, approvals.

#    - Audit everything: reproducible traces, evidence, provenance.

#

# ==============================================================================





## 1. Definitions



### 1.1 Adversary

An adversary is any actor (human or system) attempting to cause:

- unauthorized access,

- policy bypass,

- unsafe behavior,

- data exfiltration,

- operational degradation,

- or long-term manipulation (trust, memory, learned priors).



### 1.2 Adversarial robustness

The system’s ability to:

- detect adversarial patterns,

- maintain safe/authorized behavior under attack,

- degrade gracefully (fail-safe),

- and recover quickly with strong forensics.



### 1.3 Safety boundary vs security boundary

- **Safety boundary:** prevents harm even when authorized operations are possible.

- **Security boundary:** prevents unauthorized access or action.

FRANCIS enforces both, and treats ambiguity as a reason to add friction.





## 2. Adversary model



FRANCIS assumes adversaries may have:

- **Prompt-level control**: can send crafted text/attachments/links.

- **Partial knowledge**: know common LLM jailbreak patterns and repo structure.

- **Opportunistic access**: can exploit misconfigurations or weak connectors.

- **Persistence goals**: attempt to poison memory, cached web knowledge, or domain priors.

- **Timing attacks**: leverage race conditions, retries, or multi-tool workflows.



FRANCIS does **not** assume:

- perfect isolation from all runtime or host compromise.

If the host is compromised, containment and incident response become primary.





## 3. Attack surface inventory



### 3.1 Input surface

- Chat messages (user/system)

- File attachments (documents, code, archives)

- Web content (pages, forums, docs)

- Connector payloads (emails, tickets, chats)

- Domain specs and runbooks (human-authored)



### 3.2 Tool surface

- Connectors to external systems (GitHub, Slack, Jira, email, databases)

- File system operations

- Network access (web learning, downloads)

- Execution environments (daemon/workers, runtime modules)



### 3.3 Output surface

- Generated recommendations, instructions, and code

- Structured action plans that drive tool calls

- Auto-generated configs or policies



### 3.4 Learning/memory surface

- Web knowledge cache

- Conversation summaries and continuity ledger

- Domain priors / induced facts

- Embeddings and vector indexes





## 4. Key threat classes and mitigations



### 4.1 Prompt injection (direct + indirect)

**Threat:** User or embedded content instructs model to ignore rules, reveal secrets,

execute tools, or take unsafe actions.



**Mitigations:**

- Treat all external content (web, attachments, emails) as **untrusted**.

- Use *instruction hierarchy*: system policy > project policy > user request > tool output > web content.

- Normalize and classify inputs; detect injection patterns (roleplay, “ignore previous,” etc.).

- Strict tool gating via API permission gate + Action Readiness.

- Output verification: ensure plans comply with policies before execution.



**Operational rule:** Content is not authority. Only policies + verified identity + scoped permissions are authority.



### 4.2 Data poisoning (web learning, domain sources, memory)

**Threat:** Inject false facts or malicious snippets into sources so the agent later acts on them.



**Mitigations:**

- Provenance + citation tracking per learned fact.

- Multi-source corroboration for high-impact claims.

- Recency validation and reputation scoring for sources.

- Quarantine pipeline for suspicious sources (data/quarantine/*).

- “Trust but verify” for all learned domain priors before they can influence actions.



**Operational rule:** Learning outputs are suggestions until validated; they do not become “facts” automatically.



### 4.3 Tool abuse / privilege escalation

**Threat:** Use allowed tools to achieve disallowed outcomes (exfiltrate secrets, destructive changes).



**Mitigations:**

- Least privilege via scopes + delegations.

- Per-tool allowlists (targets, operations) and deny high-risk defaults.

- Side-effect classification per action step (read/write/irreversible).

- Approval requirements for sensitive operations.

- Sandbox boundaries for filesystem/network.



**Operational rule:** If an action touches secrets, regulated data, production systems, or safety-critical equipment, it must face stricter readiness thresholds.



### 4.4 Social engineering

**Threat:** Coerce the system via urgency, authority claims, or emotional manipulation.



**Mitigations:**

- Require cryptographic or system-verifiable identity for elevated authority.

- Never treat text claims (“I’m admin”) as authority.

- Use escalation policy for ambiguous or risky requests.

- Require explicit confirmation for message sending or external communications.



**Operational rule:** Urgency increases scrutiny; it never bypasses controls.



### 4.5 Output-based attacks (unsafe instructions, hallucinated policy, fabricated citations)

**Threat:** The model outputs harmful instructions or claims policy approval incorrectly.



**Mitigations:**

- Output verifier checks:

  - prohibited categories,

  - unsafe procedural instructions,

  - missing citations for factual claims derived from web,

  - schema compliance for action plans,

  - “policy trace” presence when claiming authorization.

- Refuse to produce disallowed content; provide safe alternatives.



**Operational rule:** All execution pathways require machine-checked validation, not narrative justification.



### 4.6 Concurrency and race conditions

**Threat:** Multi-worker execution causes inconsistent state, double-actions, or bypass of gating.



**Mitigations:**

- Idempotency keys for actions.

- Action ledger and dedupe (conversation ledger / operations logs).

- Locking strategy for shared resources (state, trust, approvals).

- Exactly-once semantics where feasible; otherwise at-least-once with safe idempotent operations.

- Deterministic ordering of policy checks before execution.



### 4.7 Replay / rollback abuse

**Threat:** Reuse previously approved actions in new contexts; replay old approvals; downgrade policy bundles.



**Mitigations:**

- Approval TTLs and approval scopes bound to:

  - action hash,

  - target set,

  - environment,

  - actor identity,

  - policy version.

- Signed policy bundle versions (or at least hashed + logged).

- Disallow rollback to older policy bundles without explicit governance approval.



### 4.8 Credential exfiltration and secret leakage

**Threat:** Model reveals secrets in output, logs, artifacts, or messages.



**Mitigations:**

- Redaction layer on outputs + logs.

- Secret scanning on attachments and generated artifacts.

- Store secrets only in vault (vault.db) and reference them by opaque handles.

- Never log raw secret material; only hashed or tokenized identifiers.



**Operational rule:** If a secret appears in plain text anywhere, treat it as compromised and rotate.



### 4.9 Attachment-based malware / weaponized files

**Threat:** Embedded macros, scripts, exploit documents.



**Mitigations:**

- Attachment intake pipeline:

  - type detection,

  - safe parsing,

  - quarantine unknown binaries,

  - antivirus scanning hooks (specializations/security/capabilities/antivirus).

- Deny auto-execution of attachment code.

- Strip active content where possible (macros, embedded scripts).



### 4.10 Industrial / safety-critical adversarial scenarios

**Threat:** Unsafe actuator commands, sensor spoofing, unsafe runbooks.



**Mitigations:**

- “Safety-critical mode” gating with:

  - highest trust thresholds,

  - simulation/dry-run,

  - human approval,

  - post-action verification.

- Safety validation policies and runbooks with hard deny rules.

- Conservative defaults: prefer stop/hold to proceed when uncertain.





## 5. Defense-in-depth architecture



FRANCIS should implement multiple independent layers:



1. **Input Sanitizer**

   - Normalize text, remove control characters, detect injection patterns.

   - Separate “instructions” from “data” from “claims.”



2. **Classifier / Taxonomy Tagger**

   - Tag content: source type, risk level, regulated domain, adversarial heuristics.



3. **Policy Engine**

   - Evaluate policies (filesystem, web_access, approvals, api_permissions, offensive_security).



4. **Action Readiness Gate**

   - Determine READY / READY_WITH_GUARDS / DRY_RUN_REQUIRED / REVIEW_REQUIRED / DENY.



5. **Tool Permission Gate**

   - Enforce connector scope, delegation, allowlists at the API boundary.



6. **Sandbox / Rate Limiter**

   - Limit blast radius even if something slips through.



7. **Output Verifier**

   - Validate produced plan/actions vs policies.

   - Enforce schemas, redactions, citations, and safe patterns.



8. **Audit + Telemetry**

   - Record decision trace, evidence, and outcomes for forensic replay.



No single layer should be treated as sufficient.





## 6. Trust and robustness feedback loop



Robustness is improved by learning from outcomes — but safely:



- Success increases confidence slightly; failures decrease it more sharply.

- Safety incidents trigger:

  - trust decay,

  - tighter gating,

  - quarantining of related sources,

  - and potentially disabling connectors temporarily.



Key signals:

- repeated failures on a target connector

- conflicting sources in web learning

- high anomaly scores in prompt injection detector

- attempts to access forbidden paths or network destinations





## 7. Source hygiene and web learning safety



Web learning is a major attack vector.



Controls:

- Allowlist or reputation scoring for domains.

- Crawl budget + rate limiting.

- Content filters for harmful categories.

- Store raw pages in cache with hashes; never overwrite without versioning.

- Keep “learned facts” separate from “verified facts.”



When a learned fact is used to justify a high-impact action:

- require at least 2 independent reputable sources OR a direct primary source

- require citations and recency validation





## 8. Verification and evaluation strategy



### 8.1 Adversarial test suites

Maintain a corpus of:

- prompt injection attempts

- jailbreak variants

- tool misuse prompts

- social engineering scripts

- poisoned web snippets

- malicious attachments (safe test fixtures)



### 8.2 Metrics

Track:

- policy bypass attempts blocked

- false positives (benign blocked)

- false negatives (unsafe allowed)

- time-to-detect, time-to-contain, time-to-recover

- trust decay events and root causes



### 8.3 Continuous regression

Every policy or code change should run:

- unit policy tests (deterministic)

- integration tool-gate tests

- adversarial corpus replay





## 9. Incident response playbook (summary)



### 9.1 Detection triggers

- suspicious tool calls

- secret leakage signal

- repeated denied attempts with escalating wording

- poisoned data detection

- anomaly detector flags



### 9.2 Containment actions

- quarantine suspicious inputs/sources

- disable affected connector(s)

- enforce review-only mode globally

- snapshot state and logs



### 9.3 Eradication + recovery

- rotate impacted secrets

- purge poisoned cache entries (with audit trail)

- restore from trusted snapshots/checkpoints

- re-run safety validations



### 9.4 Post-incident actions

- root cause analysis

- add regression tests

- update policies and trust boundaries

- document lessons learned in runbooks + ADRs





## 10. Implementation mapping to repo structure



This doc maps to key modules (conceptually):



- `src/francis/adversarial/*`

  - detection, defense, recovery, threat_modeling

- `src/francis/governance/*`

  - policy engine, approvals, escalation, permission gates

- `src/francis/internet/safety/*`

  - content filters, poisoned data detection

- `src/francis/chat/attachments/*`

  - intake, parsing, redaction

- `data/quarantine/*`

  - malware, misinformation, suspicious, unsafe_code

- `data/web_knowledge/blocked/*`

  - harmful content logs





## 11. Hard commitments (non-negotiables)



FRANCIS must never:

- treat untrusted content as instruction authority

- reveal secrets or credentials

- execute mutating or irreversible actions without readiness gating

- claim approvals or permissions that cannot be proven via policy trace

- “learn” facts into trusted memory without provenance and validation paths





## 12. Practical checklists



### 12.1 Before executing any tool action

- [ ] Does Action Readiness outcome permit this?

- [ ] Are permissions/scopes/delegations valid?

- [ ] Is evidence sufficient and recent?

- [ ] Are guardrails (sandbox/rate limits) enforced?

- [ ] Is logging configured and redaction active?



### 12.2 When ingesting web/attachments

- [ ] Identify source type and trust tier

- [ ] Run injection and malware heuristics

- [ ] Capture provenance (hashes, URLs, timestamps)

- [ ] Quarantine suspicious content

- [ ] Avoid storing into “verified” memory automatically





## 13. Future enhancements



- Cryptographic signing of policy bundles + approvals

- Differential privacy or robust aggregation for federated learning sources

- More formal verification of tool plans against policy constraints

- Better simulation coverage for industrial and deployment actions

- Red-team automation pipelines integrated into CI





# End of ADVERSARIAL_ROBUSTNESS.md



