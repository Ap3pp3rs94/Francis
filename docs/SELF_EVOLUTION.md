==============================================================================

FRANCIS — SELF_EVOLUTION.md

Safe self-evolution: proposals, experiments, promotion, rollback, and learning

==============================================================================



Purpose

-------

This document defines the self-evolution system in FRANCIS:

   - what “evolution” means (and what it does NOT mean)

   - how improvements are proposed, tested, and promoted

   - how safety, approvals, and trust constrain evolution

   - how regressions are detected and rolled back

   - how evidence, provenance, and auditability are preserved end-to-end



Self-evolution is the controlled process of improving:

   - policies + prompts + configs

   - routing + tool selection logic

   - evaluators + guardrails

   - domain intelligence and specializations

   - runbooks and operational procedures



It is NOT:

   - unconstrained code mutation

   - “the model rewrites itself” with no oversight

   - silent policy drift

   - self-approval for high-risk changes



Read alongside:

   - docs/ARCHITECTURE.md

   - docs/GOVERNANCE.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/POLICIES.md

   - docs/ACTION_READINESS.md

   - docs/CONCURRENCY.md

   - docs/DOMAIN_INTELLIGENCE.md

   - docs/COLLABORATIVE_INTELLIGENCE.md

   - docs/SELF_IMPROVEMENT.md

   - docs/SELF_HEALING.md

   - config/prompts/self_evolve.yaml

   - config/policies/action_readiness.yaml

   - config/policies/approvals.yaml

   - config/policies/trust_boundaries.yaml

   - config/policies/data_governance.yaml

   - config/policies/offensive_security.yaml

   - src/francis/metalearn/*

   - src/francis/governance/*

   - src/francis/trust/*

   - src/francis/telemetry/*

   - data/evolution/*

   - schemas/proposals.schema.json

   - schemas/evaluation_suite.schema.json

   - schemas/system_profile.schema.json



Design stance

------------

   - Default: conservative, reversible, auditable improvements.

   - Evolution is a capability multiplier and a risk multiplier.

   - Every promoted change is evidence-backed and survivable under rollback.

   - Production safety > novelty. Regressions are treated as incidents.



==============================================================================





## 0. Executive summary



FRANCIS self-evolution is a governed pipeline that turns “ideas for improvement”

into deployed changes only when they pass:

1) policy constraints,

2) permission + trust gates,

3) evaluation suites,

4) staged promotion (canary),

5) and monitoring with rollback.



Evolution is treated as “continuous engineering under safety constraints”:

- propose → test → promote → monitor → learn.





## 1. Definitions



### 1.1 Evolution

**Evolution** is any controlled change intended to improve performance, safety,

reliability, cost, maintainability, or operator experience.



Evolution targets include:

- prompt templates and orchestration prompts

- policies (risk thresholds, approvals, web access rules)

- model routing and ensemble logic

- tool schemas, adapters, and connectors

- evaluators and guardrails

- domain intelligence (ingestion, induction, validation)

- runbook generation patterns

- UI affordances that affect operational safety



### 1.2 Variant

A **variant** is a named candidate implementation of a change:

- “baseline” vs “variant_A”

- “routing_v3” vs “routing_v4”

- “policy_pack_regulated_2026_01” vs “policy_pack_regulated_2026_02”



Variants must be identifiable, reproducible, and comparable.



### 1.3 Experiment

An **experiment** is the controlled evaluation of one or more variants against:

- evaluation suites,

- real workloads (if permitted),

- and safety constraints.



### 1.4 Promotion

**Promotion** is the act of deploying a variant to become the new baseline in an

environment, typically via staged rollout (dev → staging → production).



### 1.5 Regression

A **regression** is any measurable degradation from the baseline on:

- correctness,

- safety compliance,

- privacy guarantees,

- latency/cost,

- reliability/availability,

- or operator UX constraints.



### 1.6 Auditability

**Auditability** means the system can later answer:

- what changed,

- who/what proposed it,

- what evidence justified it,

- what tests were run,

- what approvals were used,

- what environment it affected,

- and how rollback would work.



### 1.7 “Self” boundary

FRANCIS “self-evolves” within explicit boundaries:

- it may propose and implement changes in allowed areas

- but it must not broaden its own authority

- and it must not bypass approvals by changing approval rules





## 2. Goals and non-goals



### 2.1 Goals

- Improve quality over time with measurable evidence.

- Prevent silent policy drift.

- Make improvements reproducible and reversible.

- Keep evolution safe in regulated and safety-critical environments.

- Support multiple evolution loops:

  - fast local iteration (dev)

  - conservative operational improvements (production)

  - domain knowledge maturation (domain workbench)



### 2.2 Non-goals

- Autonomous, unbounded code rewriting in production.

- “Model self-modification” without governance.

- Eliminating human oversight for high-risk changes.

- Treating user instructions as authorization to change policies.





## 3. Threat model for evolution



Self-evolution introduces a privileged pathway: “change the system.”



Key threat categories:



### 3.1 Policy capture

A variant attempts to:

- weaken approvals,

- reduce audit logging,

- broaden filesystem/network permissions,

- loosen redaction rules,

- or disable offensive-security restrictions.



Mitigation:

- invariants + guarded policy fields

- out-of-band policy integrity checks

- mandatory “policy drift pause” mid-run (see §9.4)



### 3.2 Data poisoning

Evaluation inputs or training-like data (if any) are poisoned to promote unsafe

behavior.



Mitigation:

- provenance requirements

- poisoned data detection

- strict separation between:

  - “observations” (logs, outcomes)

  - “trusted evaluation suites”

  - “external web content”



### 3.3 Reward hacking / metric gaming

Variants optimize for a metric while harming true objectives.



Mitigation:

- multi-metric scorecards

- safety floor constraints

- adversarial test suites

- human review for high-impact promotions



### 3.4 Supply chain compromise

Dependencies or connector changes introduce vulnerabilities.



Mitigation:

- dependency pinning and scanning (process outside this doc)

- sandboxed execution

- staged rollout + monitoring



### 3.5 Credential exfiltration via evolution artifacts

Runbooks/proposals accidentally include secrets.



Mitigation:

- redaction pipeline

- “no secrets in artifacts” invariant

- scanning before persistence/export





## 4. Evolution surfaces: what can change



FRANCIS should classify changes into surfaces with different risk profiles.



### 4.1 Low-risk surfaces (more autonomous)

- docs and explanatory content

- internal comments

- non-executing templates (if not used in gating)

- evaluation suite additions (if not removing tests)



### 4.2 Medium-risk surfaces

- prompts that influence tool choice

- routing configs (model selection)

- UI affordances that influence approvals visibility

- runbook generation defaults

- domain induction heuristics



### 4.3 High-risk surfaces (strong governance)

- policies (approvals, trust boundaries, sandbox rules, web access)

- permission gates (scopes, delegations, tool allowlists)

- redaction rules and privacy enforcement

- any code path that executes tools

- connector operations that can write/exfiltrate



### 4.4 Forbidden surfaces (never self-modify)

In regulated/safety-critical profiles, it is recommended to forbid autonomous

changes to:

- approval requirements themselves

- trust threshold definitions

- audit logging mandatory fields

- redaction “must deny” rules

- credential storage rules



If edits are allowed at all, they must require explicit operator approval and

often “two-man rule” review (see docs/GOVERNANCE.md).





## 5. Core evolution architecture (conceptual)



Self-evolution is composed of these subsystems:



1) **Observer**

   - collects outcomes, metrics, incidents, operator feedback



2) **Proposer**

   - generates improvement candidates (variants) with explicit hypotheses



3) **Experiment Designer**

   - builds evaluation plans and chooses suites/benchmarks



4) **Evaluator**

   - runs offline tests, adversarial suites, and scenario simulations



5) **Gatekeeper**

   - policy engine + permission gate + trust gate + approvals



6) **Promoter**

   - staged rollout with canarying and feature flags



7) **Monitor**

   - detects regressions and triggers rollback



8) **Learner**

   - records results and updates “what works” meta-knowledge



Code map hints:

- proposal + experiments:

  - `src/francis/metalearn/*`

  - `data/evolution/*`

- gates:

  - `src/francis/governance/*`

  - `src/francis/trust/*`

- telemetry:

  - `src/francis/telemetry/*`





## 6. Evolution lifecycle (the canonical pipeline)



### 6.1 Stage A — Signal intake

Inputs:

- failed evaluations

- denied tool calls

- operator feedback

- drift detections

- cost/latency spikes

- incident retrospectives

- domain induction disagreements



Outputs:

- a normalized “improvement opportunity” record



Recommended record fields:

- `opportunity_id`

- `signal_type` (incident, metric, feedback, test failure)

- `severity`

- `scope` (module/domain/environment)

- `evidence_refs` (logs, artifacts)

- `hypothesis_space` (what might fix it)



Storage:

- `data/evolution/improvement_experiments/` (if you log as experiments)

- and/or a dedicated “opportunities” collection (optional)



### 6.2 Stage B — Proposal creation

A proposal must include:

- hypothesis (what will improve and why)

- change set description (what will change)

- risk assessment

- evaluation plan

- rollback plan

- promotion plan (environments, canary fraction)

- required approvals (if any)

- success criteria (metrics + thresholds)



Proposals should be stored under:

- `data/evolution/architectural_variants/` (for architecture-level)

- `data/evolution/improvement_experiments/` (for experiment-level)

- and referenced from logs.



### 6.3 Stage C — Variant construction

Variant must be built as one of:

- config-only variant (YAML changes)

- prompt-only variant

- code variant (branch/commit or patch)

- hybrid variant



Every variant must be fingerprinted:

- config hash

- prompt hash

- code commit hash (or patch hash)

- dependency snapshot hash (if relevant)



### 6.4 Stage D — Offline evaluation

Run evaluation suites:

- correctness suites

- safety suites

- adversarial robustness suites

- performance profiles (latency/cost)

- regression tests for prior incidents



Outputs:

- evaluation report artifact

- per-suite scores

- failure cases with repro steps



Storage:

- `data/evolution/performance_profiles/`

- `data/evolution/capability_discoveries/` (if it reveals new behavior)

- `data/artifacts/evaluations/`



### 6.5 Stage E — Governance gates (promotion eligibility)

Before promotion:

- permissions: is the promoter allowed to deploy?

- policy: is the change category allowed in this environment?

- trust/readiness: does risk require approval/human review?

- approvals: present and valid?



Any gate failure must:

- deny promotion,

- produce a safe explanation,

- write an audit record.



### 6.6 Stage F — Staged promotion (canary)

Promotion should follow:

- dev → staging → production

- start with a canary percentage (e.g., 1–5% of eligible sessions)

- expand only when monitoring stays healthy



Required controls:

- feature flags or versioned config pointers

- fast rollback (single toggle)

- pinned baselines for safety-critical workloads



### 6.7 Stage G — Monitoring and regression detection

Monitor:

- error rates

- policy denial spikes

- tool execution failure rates

- safety incidents

- latency/cost deltas

- trust metric deltas



If regression triggers:

- auto-rollback (if policy allows)

- or pause + require operator decision



### 6.8 Stage H — Learning and institutionalization

After a successful promotion:

- record the “why it worked”

- update meta-knowledge of effective interventions

- update runbooks (operational) if needed

- add regression tests to prevent reoccurrence





## 7. Evidence-first evolution



### 7.1 Provenance

Every evolutionary claim should be traceable to:

- evaluation artifacts

- tool traces (redacted)

- logs (redacted)

- scenario definitions

- version fingerprints



### 7.2 Minimal evidence bundle (promotion package)

A promotion package should include:

- proposal document

- variant fingerprint manifest

- evaluation report(s)

- policy + approvals snapshot

- rollout plan + rollback plan

- monitoring plan

- decision artifact (why promote)



### 7.3 No “evidence laundering”

Do not allow:

- web content to be treated as “truth” without citation and recency checks

- internal summaries to replace raw, audited tool results when available

- missing evidence for “but it feels better” promotions





## 8. Safety invariants for self-evolution



The system should enforce invariants that cannot be weakened by a variant

without triggering a hard deny.



Recommended invariants:



### 8.1 Approval invariants

- A variant cannot reduce approval requirements for a category of action unless:

  - explicit operator approval is provided, and

  - the environment profile allows such changes.



### 8.2 Audit invariants

- Audit logging cannot be disabled or materially reduced.

- Required audit fields must remain required.



### 8.3 Redaction invariants

- Redaction pipeline must remain enabled for tool traces and artifacts.

- “Never store secrets” and “never echo secrets” must remain enforced.



### 8.4 Trust boundary invariants

- Variants cannot broaden trust boundaries (e.g., allow more tool writes at lower trust)

  without explicit approvals and a policy-allowed change window.



### 8.5 Sandbox invariants

- Execution sandbox limits (filesystem/network/CPU) cannot be relaxed by a variant

  without explicit approvals and staging validation.



### 8.6 Offensive security invariants (recommended)

- Prohibitions on unsafe offensive behavior must not be weakened.





## 9. Evaluation model (how we decide “better”)



### 9.1 Scorecards (multi-metric)

Promotions should never optimize a single metric.



Recommended scorecard dimensions:

- Correctness (task success)

- Safety compliance (policy adherence)

- Privacy compliance (PII/secret handling)

- Reliability (crash rate, error rate)

- Cost (tokens/compute, external API calls)

- Latency (p50/p95)

- Operator experience (approval burden, clarity)



### 9.2 Floors and ceilings

Use floors (minimum requirements) to prevent tradeoffs from causing harm:

- safety_score must not drop

- privacy incidents must not increase

- destructive action denial must not drop below baseline without approvals



### 9.3 Adversarial suites

For any variant affecting:

- tool routing,

- web research,

- prompt handling,

- or safety policies,

run adversarial test suites that simulate:

- prompt injection

- social engineering

- malicious attachments

- policy evasion attempts



### 9.4 Policy drift detection (during evolution)

If a policy file changes between:

- evaluation and promotion,

- or between canary and full rollout,

the system should:

- pause rollout,

- require re-evaluation,

- and (if high-risk) re-approval.



This prevents “swap the policy after tests pass” attacks.





## 10. Experiment design patterns



### 10.1 A/B testing

Use when:

- variant impact is measurable

- workloads are comparable

- risks are low-to-medium



Requirements:

- fixed cohort assignment rules

- consistent logging

- clear statistical stopping rules



### 10.2 Canary + guardrails

Use when:

- write actions are involved

- risk is medium-to-high



Pattern:

- deploy to a small cohort

- add extra verification and stricter thresholds

- promote gradually



### 10.3 Replay-based evaluation

Use when:

- you have recorded sessions/traces (redacted)

- you need deterministic comparisons



Pattern:

- run baseline and variant against the same replay input set

- compare outputs under a strict rubric



### 10.4 Simulation-based evaluation

Use when:

- industrial/digital twin behavior matters

- scenario coverage is needed

- real-world testing is expensive/unsafe



Pattern:

- define simulation scenarios

- run baseline vs variant

- verify safety constraints and physics validity





## 11. Promotion and rollback mechanics



### 11.1 Versioning discipline

Everything that can affect behavior should be versioned:

- configs

- prompts

- policies

- routing rules

- tool schemas/adapters



Recommendation:

- use explicit version identifiers in paths and references

- avoid “latest” pointers in safety-critical profiles



### 11.2 Rollback triggers

Rollback may be triggered by:

- safety incident

- denial spike indicating policy mismatch

- error/latency spikes beyond threshold

- evaluation regression detected in production monitoring



### 11.3 Rollback strategy (recommended)

- Feature-flag revert (fast)

- Config pointer revert (fast)

- Code deployment rollback (slower)

- Data migration rollback (requires explicit plan; may be irreversible)



Every promotion must specify:

- rollback method

- rollback owner (role)

- rollback “time to safe” objective

- evidence to confirm rollback success



### 11.4 Post-rollback learning

Treat rollback as:

- an incident

- and generate:

  - root cause analysis

  - new regression test

  - updated promotion guardrails





## 12. Evolution data model and storage layout



The `data/evolution/` directory expresses the durable state of evolution.



Suggested interpretation:



- `data/evolution/architectural_variants/`

  - high-level system designs and major refactors

  - variants with broad impact



- `data/evolution/improvement_experiments/`

  - experiment specs and results

  - links to evaluation artifacts



- `data/evolution/capability_discoveries/`

  - newly discovered capabilities/limitations

  - “what the system can/can’t do” updates



- `data/evolution/performance_profiles/`

  - latency/cost/throughput profiles per environment/model route



All records should carry:

- unique ids

- timestamps

- environment profile

- variant fingerprints

- evidence references





## 13. Governance integration (hard requirements)



Self-evolution must never bypass governance.



### 13.1 Action readiness modes

In regulated environments, evolution may be constrained to:

- propose-only (no auto-apply)

- evaluate-only (produce reports)

- execute-only with explicit approvals



### 13.2 Separation of duties

High-risk promotions should require:

- Builder proposes

- Reviewer validates

- Operator approves

- Executor deploys

- Auditor certifies



A single identity should not:

- propose + approve + deploy high-risk changes.



### 13.3 Approvals as first-class artifacts

Approval records must be:

- durable

- linked to a change hash

- time-bounded

- revocable





## 14. Federation and shared evolution (optional but powerful)



In federated setups, evolution benefits from redundancy:

- one instance proposes,

- another validates,

- a third monitors.



### 14.1 What can be shared

Share:

- evaluation results (sanitized)

- regression tests (non-sensitive)

- safe runbooks/templates

- aggregate metrics



Never share:

- secrets

- raw PII

- proprietary payloads unless explicitly allowed by policy



### 14.2 Reputation and promotion

Federation may weight evidence by:

- peer trust level

- historical accuracy

- safety compliance record



Promotion should not be decided solely by federation votes;

governance still applies locally.





## 15. Operational runbooks for evolution



Recommended runbooks (see docs/RUNBOOK.md):

- “Propose improvement from incident”

- “Run offline evaluation suite for variant”

- “Canary deploy config-only change”

- “Rollback variant and certify baseline”

- “Generate regression test from incident”



Related scripts:

- `scripts/self-evolve.ps1`

- `scripts/self-heal.ps1`

- `scripts/trust-reset.ps1`

- `scripts/system-probe.ps1`



Each runbook should define:

- allowed environments

- required approvals

- evidence bundle outputs





## 16. Implementation pointers (code map)



Evolution and metalearning:

- `src/francis/metalearn/architectural_evolution/*`

  - proposing architectures, A/B tests, evolution manager



- `src/francis/metalearn/capability_discovery/*`

  - frontier mapping, gap identification, synthesis suggestions



- `src/francis/metalearn/performance_analysis/*`

  - blindspots, error patterns, improvement recommendations



Governance gates:

- `src/francis/governance/policy_engine.py`

- `src/francis/governance/action_readiness.py`

- `src/francis/governance/approvals.py`

- `src/francis/governance/api_permission_gate.py`



Trust coupling:

- `src/francis/trust/*`



Telemetry and audit:

- `src/francis/telemetry/*`





## 17. Appendix A — Proposal template (illustrative)



```yaml

proposal_id: evolve.routing.2026-01-01.v1

title: Improve model routing to reduce latency while preserving safety

created_at: "2026-01-01T00:00:00Z"

created_by:

  identity: "system"

  role: "metalearn.proposer"



hypothesis:

  statement: "Routing more short queries to the fast model reduces p95 latency without increasing safety denials."

  rationale:

    - "Short queries rarely require deep reasoning."

    - "Safety gate remains unchanged; denials should not decrease."



change_set:

  surface: "config"

  files:

    - "config/models/routing.yaml"

  variant_label: "routing_fastpath_v2"



risk_assessment:

  level: "medium"

  primary_risks:

    - "Routing error could degrade answer quality."

    - "Unexpected distribution shift in production."

  mitigations:

    - "Offline replay evaluation"

    - "Canary rollout 2% → 10% → 50% → 100%"

    - "Rollback via config pointer"



evaluation_plan:

  suites:

    - "eval.core.correctness"

    - "eval.safety.injection"

    - "eval.performance.latency"

  success_criteria:

    - metric: "latency_p95_ms"

      direction: "decrease"

      threshold_delta: "-15%"

    - metric: "safety_denial_rate"

      direction: "no_worse"

      threshold_delta: "+0%"

    - metric: "task_success_rate"

      direction: "no_worse"

      threshold_delta: "-0.5%"



promotion_plan:

  environments: ["dev", "staging", "production"]

  canary:

    start_percent: 2

    ramp_schedule: ["2", "10", "50", "100"]

  approvals_required:

    - type: "ops.deploy.config"

      when: "production"



rollback_plan:

  method: "config_pointer_revert"

  trigger_thresholds:

    - metric: "safety_incidents"

      threshold: ">0"

    - metric: "error_rate"

      threshold: "+2% vs baseline"



