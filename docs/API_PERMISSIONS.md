==============================================================================
FRANCIS — ADVERSARIAL_ROBUSTNESS.md
Defense-in-depth against prompt injection, tool misuse, poisoning, and abuse
==============================================================================

Purpose
-------
This document defines the adversarial robustness strategy for FRANCIS:
   - Threat model for adversarial inputs, environments, and integrations
   - Defense-in-depth architecture across chat → planning → tool execution
   - Detection, telemetry, and incident response for adversarial events
   - Test strategy (red-team harness, regression suites, fuzzing)
   - Operational hardening guidance for dev/prod/regulated deployments

Read alongside:
   - docs/THREAT_MODEL.md
   - docs/TRUST_MODEL.md
   - docs/POLICIES.md
   - docs/API_PERMISSIONS.md
   - docs/WEB_ACCESS.md
   - docs/ATTACHMENTS.md
   - docs/CONVERSATION_CONTINUITY.md

Key code references:
   - src/francis/adversarial/detection/*
   - src/francis/adversarial/defense/*
   - src/francis/governance/*
   - src/francis/credentials/*
   - src/francis/chat/attachments/*
   - src/francis/internet/safety/*
   - src/francis/llm/guardrails.py

Design stance:
   - Assume inputs are hostile (including "friendly" users and “trusted” web pages)
   - Default deny for risky tool actions
   - Keep the model untrusted; trust is established via gates + evidence + policy
   - Treat memory, web learning, and attachments as untrusted until validated

==============================================================================


## 0. Executive summary

FRANCIS is an agentic system. The primary adversarial risk is not "the model being wrong";
it is **the model being induced to do the wrong thing on purpose** (or to leak data)
through *prompt injection* or *tool misuse*.

Robustness is achieved via:
- **Isolation** (capability boundaries, sandboxing, strict tool schemas)
- **Least privilege** (scopes + delegations + approvals)
- **Verification** (input sanitization, output verification, postconditions)
- **Telemetry** (auditable allow/deny, anomaly detection, incident workflows)
- **Continuous testing** (red-team prompts, regression suites, fuzzing)

Capability manifests and delegation tokens:
- Capability scope is defined in `meta/capabilities.yaml` (canonical).
- Delegation token structure is defined in `schemas/delegation_token.schema.json`.
- Approvals and gating reference these artifacts: approvals authorize capability use within scoped resources and constraints; gating enforces approval_class before execution.
- Canonical gating rules: [PHILOSOPHY.md#gating-rules](./canonical/PHILOSOPHY.md#gating-rules).


## 1. Threat model

### 1.1 Adversary classes
1) **Casual adversary**
   - Tries “jailbreak” prompts, instruction override, or social engineering.
2) **Skilled prompt injector**
   - Crafts multi-step injection: “ignore policy”, “use tool X”, “exfiltrate data”.
   - Exploits tool descriptions, schema ambiguity, and long-context weaknesses.
3) **Supply-chain adversary**
   - Poisoned web pages, docs, repos, packages, or plugin bundles.
4) **Insider / compromised identity**
   - Has some permissions but tries to exceed scope or bypass approvals.
5) **Federation adversary**
   - A remote instance sends malicious “shared knowledge” or “trusted outputs”.

### 1.2 Assets to protect
- Secrets: API tokens, keys, credentials, vault contents
- Confidential user data: attachments, conversation history, memory stores
- Integrity of outputs: reports, code changes, runbooks, decisions
- System safety: industrial simulations/controls, operational tools, execution sandboxes
- Trust posture: approvals, delegations, and logs (audit integrity)

### 1.3 High-level attack surfaces
- **Chat inputs** (user, imported messages, system prompts, “assistant messages”)
- **Tool outputs** (web pages, issue text, emails, Slack messages, DB rows)
- **Attachments** (PDFs/docs/code zipped bundles)
- **Web learning / crawling** (poisoned sources, SEO spam, hidden instructions)
- **Memory** (poisoning by injecting persistent instructions or fabricated facts)
- **Plugins** (spec metadata, tool schemas, template code injection)
- **Federation** (cross-instance shared knowledge; reputation manipulation)

### 1.4 Primary adversarial goals
- Exfiltration of secrets or confidential data
- Unauthorized tool actions (write/modify/delete)
- Bypass approval workflows
- Poison memory to shift long-term behavior
- Create unsafe outputs (malicious code, harmful instructions, policy violations)
- Degrade trust metrics, confuse governance, or forge audit evidence


## 2. Adversarial taxonomy

### 2.1 Prompt injection (direct)
User prompts that attempt to override:
- system policies
- tool constraints
- approval requirements
- safety boundaries

Typical patterns:
- “Ignore all previous instructions…”
- “You are now in developer mode…”
- “This is approved by admin…”

### 2.2 Prompt injection (indirect / tool output injection)
Malicious content embedded in:
- web pages
- GitHub issues/PRs
- Jira tickets
- emails
- docs

Example risk:
A web page says: “To comply, run tool X with payload Y.”  
The model may treat it as instruction unless content is marked *untrusted*.

### 2.3 Tool misuse & schema smuggling
- Exploiting a tool that accepts free-form strings (URLs, queries, shell commands)
- Smuggling extra instructions in “description” fields or “notes”
- Over-broad tool definitions that allow unintended operations

### 2.4 Data poisoning (memory / retrieval / learned domains)
- Injecting false facts into memory to influence later decisions
- Poisoning retrieval indexes with adversarial “high-similarity” chunks
- Manipulating domain induction to create malicious priors/runbooks

### 2.5 Multi-modal & attachment attacks
- Documents containing hidden instructions (white-on-white text, tiny fonts)
- Adversarial PDFs with embedded scripts/links (even if not executed)
- “Confusable” content that leads to misclassification or unsafe behavior

### 2.6 Approval & trust bypass attempts
- Social engineering: “It’s an emergency; skip approvals.”
- Impersonation: “I’m admin; authorize.”
- Exploit policy ambiguity or misconfigured environment files.

### 2.7 Federation reputation / consensus manipulation
- Sybil-like instances
- Collusive “consensus logs”
- Malicious shared knowledge that masquerades as validated fact


## 3. Defense-in-depth architecture

This is the core principle: **no single mechanism is relied upon**.

### 3.1 Layer 1 — Input normalization and hygiene
Objective: eliminate trivial bypasses and highlight untrusted sources.

Key tactics:
- Canonicalize whitespace and encoding
- Detect and label source origin (user vs tool vs web vs attachment)
- Strip/flag hidden content (attachment ingestion)
- Apply safety heuristics for known injection phrases

Relevant modules:
- `src/francis/adversarial/defense/input_sanitizer.py`
- `src/francis/chat/attachments/intake.py`
- `src/francis/chat/attachments/parsers.py`

### 3.2 Layer 2 — Untrusted content marking (taint tracking)
Objective: keep tool outputs from being treated as instructions.

Rule:
- Tool outputs are **data**, not commands.
- They can inform decisions, but cannot override system/policy constraints.

Implementation idea:
- Attach metadata to context chunks: `{source, trust_level, tainted=true}`
- The orchestrator and tool selector treat tainted content as *evidence only*.

Relevant modules:
- `src/francis/chat/continuity/retrieval.py`
- `src/francis/llm/context.py`
- `src/francis/internet/research/content_extractor.py`

### 3.3 Layer 3 — Policy & permission gates (default deny)
Objective: ensure that even if the model is tricked, execution is blocked.

Enforced before tool execution:
- API permissions gate (scopes/delegations)
- Policy engine checks
- Readiness mode / approvals check

Relevant modules:
- `src/francis/governance/api_permission_gate.py`
- `src/francis/governance/policy_engine.py`
- `src/francis/governance/action_readiness.py`
- `src/francis/credentials/scope_checker.py`

### 3.4 Layer 4 — Tool schema hardening (tight interfaces)
Objective: minimize degrees of freedom for “creative misuse”.

Rules:
- Tools must be strongly typed; avoid free-form “command” strings.
- Prefer:
  - `operation: enum`
  - `resource: structured object`
  - `filters: validated fields`
- Apply allowlists for domains/repos/channels/paths.
- Apply maximum result limits (rows/messages/pages).

Relevant modules:
- `src/francis/llm/tooling/tool_schema_adapter.py`
- `src/francis/llm/guardrails.py`
- Connector implementations under `connectors/*`

### 3.5 Layer 5 — Output verification (postconditions & invariants)
Objective: ensure generated tool calls and outputs satisfy constraints.

Examples:
- If policy requires approval, verify an approval exists.
- If scope is read-only, verify operation is read-only.
- If output claims a fact, verify citations exist (where required by policy).

Relevant modules:
- `src/francis/adversarial/defense/output_verifier.py`
- `src/francis/internet/research/fact_checker.py`
- `src/francis/internet/research/citation_tracker.py`

### 3.6 Layer 6 — Runtime sandboxing & rate limits
Objective: reduce blast radius even for allowed actions.

Controls:
- timeouts, retries with caps
- concurrency limits
- rate limiting per tool
- circuit breakers for repeated denials or suspicious patterns

Relevant modules:
- `src/francis/internet/crawling/rate_limiter.py`
- `src/francis/kernel/worker_pool.py`
- `src/francis/kernel/scheduler.py`

### 3.7 Layer 7 — Telemetry, anomaly detection, and response
Objective: detect and respond to adversarial activity rapidly.

- Log every allow/deny
- Identify repeated injection signatures
- Detect unusual tool usage patterns (spikes, new targets, broad queries)

Relevant modules:
- `src/francis/adversarial/detection/anomaly_detector.py`
- `src/francis/adversarial/detection/deception_detector.py`
- `src/francis/telemetry/audit.py`
- `src/francis/telemetry/logging.py`


## 4. Core design principles (non-negotiables)

### 4.1 Model is not a security boundary
Assume the model can be manipulated. Security is enforced by code + policy.

### 4.2 Least privilege everywhere
- Narrow scopes by default
- Expiring delegations
- Approvals for high-risk actions
- “Read-only first” for new connectors

### 4.3 Separation of duties
High-impact actions require:
- approval workflow (possibly human)
- elevated trust level
- stricter logging and post-checks

### 4.4 Context minimization
Only provide the model what it needs:
- redact secrets
- provide summaries where possible
- avoid leaking internal policies verbatim into tool contexts

### 4.5 Deterministic tool invocation
Prefer:
- constrained, typed parameters
- explicit operation selection
- transparent execution plans
Over:
- “figure it out” instructions inside tool calls.


## 5. Specific defenses by attack type

### 5.1 Prompt injection defenses
- Instruction hierarchy enforcement:
  - system > developer > user > tool output
- Injection phrase heuristics (signal only, not a single-point gate)
- “Refuse to comply with tool-output instructions”
- Require tool calls to be justified with policy-aligned rationale

### 5.2 Indirect injection defenses (web/tool output)
- Mark as untrusted / tainted
- Strip “call-to-action” language when ingesting as evidence (optional)
- Require independent reasoning: tool output cannot directly map to tool execution
- For web: restrict to allowlisted domains or approved sources in regulated mode

### 5.3 Data exfiltration defenses
- No secrets in model context (vault handles only)
- Response redaction pass for:
  - tokens/keys
  - PII patterns
  - internal file paths (policy dependent)
- Limit export/report generation to approved destinations
- Prevent copying large chunks of sensitive memory to output

### 5.4 Memory poisoning defenses
- Memory writes require:
  - explicit “memory write” action type
  - classification check (what kind of memory)
  - provenance and confidence score
- Reject storing:
  - instructions (“Always do X”)
  - policy overrides (“Ignore approvals”)
  - unverified credentials or “admin notes”
- Store claims as:
  - facts with sources
  - hypotheses with confidence
  - tasks with owners/expiry

### 5.5 Tool misuse defenses
- Disallow raw command execution in general environments
- For any tool that takes a “query”:
  - validate structure
  - cap scope and results
  - apply allowlist constraints
- For connectors that can send messages externally:
  - require explicit confirmation policy / approval type (configurable)

### 5.6 Attachment attack defenses
- Convert attachments to safe intermediate representation
- Strip active content and links when possible
- Detect hidden text layers and mark as suspicious
- Require “attachment risk scan” step before using attachment content as evidence

Relevant modules:
- `src/francis/chat/attachments/redaction.py`
- `src/francis/adversarial/detection/poisoning_detector.py`

### 5.7 Federation defenses
- Treat remote knowledge as untrusted until validated
- Reputation-weighted acceptance
- Require cross-source corroboration for high-impact claims
- Maintain a quarantine workflow for suspicious shared knowledge


## 6. Safety controls for “security” capabilities

FRANCIS may include security-related modules (scanning, analysis, incident response).
These must follow **defensive-only** patterns:

- No autonomous offensive actions
- No exploit instructions or weaponization output
- Focus on detection, containment, and remediation
- Require elevated approvals for any action that changes production systems

Policy references:
- `config/policies/offensive_security.yaml`
- `config/policies/safety_critical.yaml`


## 7. Detection & telemetry

### 7.1 What to log (minimum)
For every tool decision:
- identity (issuer/subject)
- tool + operation
- target resource (redacted / tokenized if needed)
- allow/deny + reason code
- policy versions + trust snapshot
- approval ids (if any)
- request hash / idempotency key

Data locations:
- `data/logs/api_actions/*`
- `data/logs/audit/*`
- `data/logs/safety/*`
- `data/logs/errors/*`

### 7.2 Suspicious signals (examples)
- Repeated “ignore policy” patterns
- Attempts to access vault or secrets via conversation
- Tool calls with unusually broad selectors (e.g., “all repos”, “all channels”)
- Rapid spikes in web crawling volume
- Frequent denials followed by slightly modified repeated attempts (“prompt hacking”)

### 7.3 Automated responses (configurable)
- Rate-limit or temporarily block a session
- Require approvals for subsequent actions
- Downgrade trust posture automatically
- Quarantine learned sources or memory writes


## 8. Adversarial testing strategy

### 8.1 Red-team prompt suite
Maintain a curated suite of attacks:
- direct jailbreaks
- indirect injection via tool outputs
- memory poisoning attempts
- approval bypass scripts
- “benign-looking” harmful instructions

Expected results:
- system refuses / safely redirects
- no tool calls are executed when disallowed
- logs include correct denial reasons

### 8.2 Property-based tests (tool gating)
Core invariants:
- “No write tool call without scope allowing write”
- “No destructive call without explicit approval in required environments”
- “No secret material appears in model context or responses”
- “No tool output can override policy constraints”

### 8.3 Fuzzing
Fuzz:
- tool parameters (type confusion, oversized payloads)
- attachment ingestion
- web extraction
- schema adapter behavior

### 8.4 Regression gating
Any change to:
- policy engine
- scope checker
- tool schemas
- attachment pipeline
must run adversarial regression before merge.

Suggested location for test harness:
- `tests/adversarial/*`
- `tests/credential_security/*`
- `tests/api_permissions/*`


## 9. Incident response playbook (adversarial event)

### 9.1 Triage
- Identify affected session(s), tool(s), connector(s)
- Determine whether any tool calls executed
- Assess data exposure risk

### 9.2 Containment
- Disable affected connector(s)
- Revoke delegations / rotate impacted credentials
- Increase approval requirements temporarily
- Quarantine suspicious memory or web sources

### 9.3 Forensics
- Preserve logs and decision trails
- Collect relevant tool request/response payloads (redacted)
- Identify root cause: policy gap, schema weakness, connector bug, misconfig

### 9.4 Recovery
- Patch policy/schema/connector
- Add regression test reproducing the event
- Restore normal operation gradually with monitoring

### 9.5 Postmortem
- Document what failed and why
- Update threat model and policies
- Update runbooks and training prompts


## 10. Hardening checklist (operator)

### 10.1 Baseline
- [ ] Default deny for all connectors in production
- [ ] Least privilege scopes + expiring delegations
- [ ] Approval workflow enabled for write/destructive actions
- [ ] Audit logs enabled and immutable (append-only)
- [ ] Vault access is handle-based; no secrets enter model context

### 10.2 Web learning
- [ ] Domain allowlists in regulated/safety-critical environments
- [ ] Content filtering enabled (malware/misinformation/harmful knowledge)
- [ ] Quarantine pipeline for suspicious sources

### 10.3 Attachments
- [ ] Safe parsing mode
- [ ] Redaction rules applied before indexing
- [ ] Block or quarantine high-risk file types if needed

### 10.4 Federation
- [ ] Treat shared knowledge as untrusted until validated
- [ ] Reputation system enabled
- [ ] Quarantine workflow for suspicious contributions


## 11. Appendix — Practical “do / don’t” rules for implementers

### DO
- Keep tool interfaces narrow and typed
- Validate resource targets with allowlists
- Fail closed on schema mismatches
- Log allow/deny with reason codes
- Require approvals for high-impact operations
- Mark all tool outputs as untrusted data

### DON’T
- Accept arbitrary shell commands as parameters
- Allow “raw URL fetch any domain” in production
- Store instructions in memory as “facts”
- Let tool output dictate tool execution
- Make “one regex” your only injection defense


# End of ADVERSARIAL_ROBUSTNESS.md
