==============================================================================

FRANCIS — TRUST_MODEL.md

Trust scoring, decay, certification, and action readiness gating

==============================================================================



Purpose

-------

This document defines the TRUST model in FRANCIS:

   - What "trust" means (and what it does NOT mean)

   - How trust differs from permissions and identity

   - How trust is computed, versioned, and audited

   - How trust gates actions (Action Readiness)

   - How trust evolves over time (growth, decay, shocks, recovery)

   - How per-domain and per-capability trust is tracked

   - How certification tests and evaluations raise trust safely



Trust in FRANCIS is a *runtime governance signal* that answers:

   “Given uncertainty + risk, should we execute this action now?”



Trust is not:

   - a user’s opinion

   - a role label (“admin”, “operator”)

   - a static permission grant

   - a substitute for least privilege



Read alongside:

   - docs/API_PERMISSIONS.md

   - docs/POLICIES.md

   - docs/THREAT_MODEL.md

   - docs/ACTION_READINESS.md

   - docs/GOVERNANCE.md

   - docs/CONVERSATION_CONTINUITY.md

   - docs/WEB_ACCESS.md

   - config/policies/action_readiness.yaml

   - config/policies/trust_boundaries.yaml

   - config/policies/collaborative_trust.yaml

   - src/francis/trust/*

   - src/francis/governance/action_readiness.py

   - src/francis/telemetry/audit.py



Data model references:

   - data/trust/levels/current_state.json

   - data/trust/levels/history.jsonl

   - data/trust/levels/per_domain/*

   - data/trust/metrics/accuracy_scores.json

   - data/trust/metrics/safety_record.json

   - data/trust/metrics/success_rates.json

   - data/trust/certifications/passed_tests.json



Design stance

------------

   - Default conservative: trust grows slowly, drops quickly on violations.

   - Trust is evidence-driven: measured outcomes > self-assertion.

   - Trust is scoped: domain/capability/tool/environment-specific.

   - Trust is auditable: every trust change is an event with provenance.



==============================================================================





## 1. Core concepts



### 1.1 Permission vs Trust vs Readiness

- **Permission**: “Is this action allowed for this identity + delegation + scope?”

  - enforced by the Permission Gate (scopes/delegations/policies)

- **Trust**: “Should we do it now given risk and uncertainty?”

  - derived from observed performance, safety history, certification status

- **Action Readiness**: “What mode of execution is allowed right now?”

  - combines trust + risk + policy + approvals into an actionable decision:

    - deny

    - allow (dry-run)

    - allow (review required)

    - allow (execute)



Trust never overrides permissions.

Permissions can allow; trust can still block.



### 1.2 Trust is scoped, not global

FRANCIS tracks trust at multiple scopes:

- **Global trust** (baseline safety posture)

- **Per-domain trust** (e.g., “industrial”, “security”, “finance”, “healthcare”)

- **Per-capability trust** (e.g., “web_research”, “db_query”, “send_email”)

- **Per-tool/provider trust** (e.g., a connector’s reliability and abuse risk)

- **Per-environment trust** (dev vs production vs regulated vs airgapped)

- **Per-identity trust** (optional, if multi-identity mode is enabled)



The system should make it difficult for trust earned in low-risk contexts

to “transfer” to high-risk contexts without explicit certification.



### 1.3 Trust is evidence-driven

Trust is derived from:

- measured correctness (task outcomes, evaluation suites)

- safety compliance (policy adherence, blocked attempts, incident history)

- reliability (success rate, timeouts, retries, connector stability)

- audit quality (trace completeness, provenance correctness)

- certification tests (explicit test passes, continuous validation)



“Confidence” in a single answer is not the same as long-run trust.



### 1.4 Trust boundaries

A trust boundary is crossed when:

- authority changes (delegation, approvals, role changes)

- data classification increases (internal → confidential → regulated)

- external content enters (web, uploads, SaaS payloads)

- execution side effects begin (writes, deletes, actuator commands)



Crossing a boundary typically requires higher trust and/or approvals.





## 2. Trust state model



### 2.1 Trust state fields (recommended)

A trust state object (global or scoped) should include at least:

- `trust_level`: numeric, normalized to [0.0, 1.0]

- `confidence`: numeric, [0.0, 1.0] representing evidence volume/quality

- `risk_tolerance`: policy-driven modifier (environment/domain dependent)

- `last_updated_at`: timestamp

- `sources`:

  - metrics pointers (accuracy/safety/reliability)

  - certification pointers (test ids and timestamps)

  - incident pointers (audit ids)

- `constraints`:

  - max autonomy

  - required approvals

  - mandatory review modes

- `explanations`:

  - human-readable rationale for current trust



### 2.2 Persistent storage

FRANCIS stores:

- **Current trust snapshot**:

  - `data/trust/levels/current_state.json`

- **Trust event log** (append-only, temporal truth):

  - `data/trust/levels/history.jsonl`

- **Per-domain trust state**:

  - `data/trust/levels/per_domain/*`

- **Metrics**:

  - `data/trust/metrics/*`

- **Certification results**:

  - `data/trust/certifications/passed_tests.json`



The current snapshot is derived from the event log + metrics; it is not the

authoritative record when reconstructing history.



### 2.3 Trust events (history.jsonl)

A trust event should be an append-only record:

- `event_id`

- `timestamp`

- `scope` (global/domain/capability/tool/env/identity)

- `delta` (trust change and confidence change)

- `reason_code` (e.g., `EVAL_PASS`, `POLICY_VIOLATION`, `INCIDENT`, `DECAY_TICK`)

- `evidence_refs` (audit ids, evaluation ids, policy snapshot ids)

- `actor` (system/service identity; never “the model”)

- `notes` (redacted, safe)



Events enable:

- rollback analysis

- drift detection on governance

- post-incident forensics





## 3. Trust signals and metrics



### 3.1 Metric categories

FRANCIS uses four primary trust signal categories:



1) **Correctness**

- evaluation suite scores

- task success/failure (grounded by checks)

- regression tests for specific domains/capabilities



2) **Safety**

- policy violations (hard and soft)

- injection detection triggers

- unsafe tool attempts

- data governance violations



3) **Reliability**

- connector success rates

- timeouts, retries, rate-limit hits

- latency/throughput stability

- worker crash frequency



4) **Auditability**

- trace completeness

- provenance correctness (source attribution present)

- redaction compliance (no secrets in logs/artifacts)



### 3.2 Canonical metric stores

- `data/trust/metrics/accuracy_scores.json`

  - recommended: per-domain + per-capability rolling windows

- `data/trust/metrics/safety_record.json`

  - recommended: counts + severity + recency-weighted penalties

- `data/trust/metrics/success_rates.json`

  - recommended: per-connector + per-operation success and failure modes



### 3.3 Evidence quality weighting

Not all evidence is equal.

Trust should weight evidence by:

- **provenance strength**

  - audited tool results > web summaries > unverified text

- **freshness**

  - recent evidence matters more for operational reliability and evolving domains

- **coverage**

  - diverse task coverage beats repeated easy wins

- **adversarial exposure**

  - passing tests under injection pressure is stronger evidence



A good trust model avoids “trust inflation” by making it hard to accumulate

trust from repetitive, low-entropy evidence.





## 4. Trust computation (recommended model)



### 4.1 Separating “score” from “confidence”

Trust level answers: “How good is the system at this scope?”

Confidence answers: “How sure are we about that trust estimate?”



This prevents:

- over-trusting when evidence is sparse

- under-trusting after evidence grows



### 4.2 Suggested formula (high-level)

For a given scope S:



- Let:

  - `C` = correctness score ∈ [0,1]

  - `S` = safety score ∈ [0,1] (1 = perfect compliance)

  - `R` = reliability score ∈ [0,1]

  - `A` = auditability score ∈ [0,1]

  - `P` = policy posture modifier ∈ [0,1] (environment strictness)

  - `K` = confidence ∈ [0,1]



Compute raw trust:

- `T_raw = wC*C + wS*S + wR*R + wA*A`

  - where weights sum to 1 and are policy-tunable per environment/domain



Apply policy posture:

- `T_policy = T_raw * P`



Apply confidence shaping (conservative early):

- `T = K * T_policy + (1 - K) * T_floor`

  - where `T_floor` is a conservative baseline (e.g., 0.1–0.3 depending on env)



This ensures low-evidence contexts remain conservative.



### 4.3 Safety as a multiplicative gate (optional but recommended)

For high-risk scopes (security, industrial, regulated):

- treat safety as multiplicative:

  - `T = T * (S ^ gamma)` where `gamma > 1`

This makes repeated safety violations disproportionately costly.



### 4.4 Recency and decay

Trust should decay toward a baseline if:

- evidence is old

- environment changed

- model/provider changed

- policies changed materially



A common decay form:

- `T(t) = T_baseline + (T0 - T_baseline) * exp(-λ * Δt)`

- `K(t)` should also decay if evidence is stale (confidence recency penalty)



Decay parameters should be stricter in:

- fast-changing domains (web research, security)

- unstable connectors

- regulated environments



### 4.5 Trust shocks (fast drops)

Trust must drop quickly on:

- confirmed policy violation (severity-weighted)

- data leakage

- unsafe connector misuse

- sandbox escape attempt

- federation poisoning incident



A shock is typically applied as:

- `T := max(T_min, T - shock(severity, recency))`

- `K := max(K_min, K - k_shock(severity))`



And also triggers readiness mode escalation (see §5).





## 5. Action Readiness: how trust gates execution



### 5.1 Readiness decision inputs

Action readiness should consider:

- trust level at relevant scopes:

  - global trust

  - domain trust

  - capability/tool trust

- action risk classification:

  - read vs write vs destructive vs safety-critical

- data classification involved:

  - public/internal/confidential/regulated

- environment mode:

  - dev vs production vs regulated vs airgapped

- approvals required by policy:

  - action type approvals

  - domain approvals

  - emergency approvals

- contextual uncertainty:

  - conflicting evidence

  - injection suspicion signals

  - incomplete provenance



### 5.2 Readiness modes (recommended)

- **DENY**

  - block execution

  - provide safe explanation and remediation guidance

- **ALLOW_DRY_RUN**

  - produce a plan, previews, diffs, or simulated tool calls

  - no side effects

- **ALLOW_REVIEW**

  - allow execution only after explicit human review/approval

- **ALLOW_EXECUTE**

  - permitted within scope constraints; still audited and rate-limited



### 5.3 Default readiness policy shape

A conservative default is:

- READ actions:

  - allow at moderate trust, unless data classification is high

- WRITE actions:

  - require higher trust and/or approvals

- DESTRUCTIVE actions:

  - require very high trust + explicit approvals + dual-review (optional)

- SAFETY-CRITICAL actions:

  - default deny unless explicitly configured + simulated + approved



These mappings should live in:

- `config/policies/action_readiness.yaml`

- `config/policies/trust_boundaries.yaml`



### 5.4 “Two-key” pattern for high risk

For actions classified as “red”:

- require:

  - trust threshold met

  - approval present

  - and optionally a second reviewer (two-person rule)

Trust alone should never allow irreversible actions in regulated modes.





## 6. Per-domain and per-capability trust



### 6.1 Domain trust

Domains map to:

- specializations (e.g., `specializations/security`, `specializations/finance`)

- domain knowledge stores (e.g., `data/domains/*`)

- domain-specific policies (regulated domains list, allowed tools)



Domain trust should be computed using:

- domain-specific eval suites

- domain-specific safety policies

- domain-specific incident history

- domain drift detection outputs



### 6.2 Capability trust

Capability trust measures:

- tool selection correctness

- safe execution discipline

- output verification reliability

- adherence to domain-specific constraints



Examples:

- `web_research`: requires strong recency validation and source credibility checks

- `db_query`: requires strict scope and row limits, PII redaction

- `send_email`: requires approvals and anti-exfil checks



### 6.3 Tool/provider trust

Tool trust should incorporate:

- operational reliability metrics (timeouts, auth failures)

- abuse risk (ability to exfiltrate data or cause side effects)

- provider security posture (if modeled)

- per-operation granularity (read vs write endpoints)



This allows the system to:

- keep trust high for internal computations

- keep trust lower for high-exfil connectors unless certified





## 7. Certification model (raising trust safely)



### 7.1 What certification means

A certification is a recorded, reproducible test outcome that:

- is tied to a scope (domain/capability/tool)

- is tied to a version (policy snapshot, runtime version)

- has provenance (test id, runner, inputs class, evaluation suite)

- can expire or be invalidated by significant changes



Certification results are stored in:

- `data/trust/certifications/passed_tests.json`



### 7.2 Certification types

Recommended certification categories:

- **Safety certification**

  - injection robustness tests

  - policy compliance tests

  - redaction and secret-handling tests

- **Correctness certification**

  - curated test suites per domain

  - regression tests after updates

- **Reliability certification**

  - connector integration tests

  - rate limit and retry behavior tests

- **Auditability certification**

  - trace completeness checks

  - provenance + citation requirements



### 7.3 Certification expiry and invalidation

Certifications should expire when:

- policies change materially

- connector/provider changes

- model/provider version changes (if relevant)

- runtime changes (sandbox, permission gate)

- time-based TTL elapsed (freshness requirement)



Expired certifications should not count toward trust growth.



### 7.4 Certification-driven trust growth

Passing a certification should:

- increase trust level slightly (bounded)

- increase confidence more meaningfully (evidence strength)

- annotate state with certification refs

- be auditable and reproducible



Trust growth should remain conservative:

- repeated passes of the same test should give diminishing returns





## 8. Trust recovery and remediation



### 8.1 After policy violations or incidents

When trust drops:

- readiness mode should automatically tighten:

  - force dry-run

  - require approvals

  - reduce allowed tools

- remediation path should be explicit:

  - run a certification suite

  - improve redaction

  - narrow delegations/scopes

  - patch policy gaps



### 8.2 Trust reset (controlled)

A reset is a governance action, not a convenience.

Resets should:

- be policy-gated and audited

- require approvals in production/regulated modes

- preserve the history log (never delete events)



### 8.3 “Quarantine then learn”

If a domain ingestion pipeline is suspected poisoned:

- quarantine sources

- stop induction/updates

- re-run validation against trusted baselines

- only then resume learning with tightened constraints





## 9. Collaboration and federation trust



### 9.1 Internal multi-agent trust weighting

When multiple agents contribute:

- weight contributions by:

  - per-role competence metrics

  - domain trust

  - historical accuracy on similar tasks

  - policy compliance record



Consensus must be explainable:

- minority reports preserved when risk is high

- policy checks always override votes



### 9.2 Federated peer trust

Peer trust should include:

- identity verification (where configured)

- historical contribution quality

- poisoning/anomaly record

- recency and replay protection

- policy compatibility checks



Federation imports should be:

- sanitized

- provenance-tagged

- optionally staged in quarantine before adoption





## 10. Implementation pointers (code map)



Recommended module responsibilities:

- `src/francis/trust/calculator.py`

  - compute trust scores from metrics + certifications + decay

- `src/francis/trust/levels.py`

  - load/store trust state, resolve scoped trust inheritance

- `src/francis/trust/decay.py`

  - recency decay functions and staleness logic

- `src/francis/trust/growth.py`

  - trust growth rules and diminishing returns

- `src/francis/trust/certification.py`

  - certification ingestion, expiry, invalidation rules

- `src/francis/trust/tracker.py`

  - event emission into `history.jsonl`

- `src/francis/governance/action_readiness.py`

  - map trust + risk + approvals → readiness decision

- `src/francis/telemetry/audit.py`

  - immutable audit events for trust changes and gate decisions





## 11. Operator tuning guide (practical)



### 11.1 Tune via policy, not code

Operators should primarily tune:

- weights (`wC, wS, wR, wA`)

- decay rates by environment and domain

- readiness thresholds by action class

- certification requirements and expiry rules



These should live under:

- `config/policies/*`

- `config/environments/*`



### 11.2 Recommended defaults by environment

- **dev**

  - faster trust growth, slower decay

  - fewer approval requirements for writes (still audited)

- **production**

  - balanced growth, balanced decay

  - approvals required for high-impact writes

- **regulated / safety_critical**

  - very conservative growth

  - fast decay and severe shocks

  - approvals for most writes; two-person rule for destructive actions

  - web access tightly constrained



### 11.3 What to monitor

- spikes in policy denials (possible injection attempts)

- connector failure patterns (reliability trust drop)

- drift detection alerts (integrity issues)

- unexpected trust growth (possible metric bug or test loophole)

- certification expiry events and their operational impact





## 12. Trust invariants (non-negotiables)



- Trust must not grant permissions.

- Trust must not leak secrets (ever).

- Trust changes must be auditable and attributable.

- Trust must be scoped; cross-scope transfer is limited and explicit.

- Safety violations must reduce trust sharply, especially in high-risk domains.

- High-impact actions require approvals as defined by policy, regardless of trust.





# End of TRUST_MODEL.md



