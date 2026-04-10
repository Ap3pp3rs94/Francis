==============================================================================

FRANCIS — SELF_IMPROVEMENT.md

Self-improvement: evaluation → learning loops → proposals → governed change

==============================================================================



Purpose

-------

This document defines the self-improvement system in FRANCIS:

   - what “self-improvement” means (and what it must never mean)

   - the end-to-end improvement lifecycle: detect gaps → propose → evaluate

     → approve → implement → verify → deploy → monitor

   - how evaluations, trust, safety, and governance constrain change

   - how FRANCIS generates improvement experiments and learns from outcomes

   - how improvements are tracked, audited, and rolled back



Self-improvement is a governed R\&D pipeline. It is not a permission to mutate.



Read alongside:

   - docs/SELF_EVOLUTION.md

   - docs/SELF_HEALING.md

   - docs/GOVERNANCE.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/POLICIES.md

   - docs/ACTION_READINESS.md

   - docs/DOMAIN_INTELLIGENCE.md

   - docs/EXPLANATION_SYSTEM.md

   - docs/ADVERSARIAL_ROBUSTNESS.md

   - docs/CONCURRENCY.md

   - docs/INTEGRATION_GUIDE.md

   - config/policies/action_readiness.yaml

   - config/policies/approvals.yaml

   - config/policies/offensive_security.yaml

   - config/policies/privacy.yaml

   - config/policies/data_governance.yaml

   - config/policies/sandbox.yaml

   - config/models/routing.yaml

   - src/francis/metalearn/*

   - src/francis/domain_intelligence/*

   - src/francis/trust/*

   - src/francis/governance/*

   - src/francis/telemetry/*

   - data/evolution/*

   - data/artifacts/evaluations/*

   - data/artifacts/reports/*



Design stance

------------

   - Default to stability: improvements must earn their way into production.

   - Safety and correctness dominate “cleverness”.

   - Improvements are reversible and observable.

   - Every improvement must be measurable with pre-registered criteria.

   - Treat evaluation data as high-value security-sensitive assets.



==============================================================================





## 0. Executive summary



Self-improvement in FRANCIS is the controlled process of increasing capability,

reliability, safety, and usefulness over time without compromising governance.



FRANCIS improves via:

- evaluation suites (what is broken or weak)

- controlled experiments (what changes help)

- proposals (what to change, with evidence)

- approvals (when change is allowed)

- implementation (code/config)

- verification (tests + safety checks)

- monitoring (regressions, drift)

- learning (update priors, playbooks, routing, and trust metrics)



Self-improvement does not bypass the permission system. It is a pipeline, not a

superpower.





## 1. Definitions



### 1.1 Self-improvement

**Self-improvement** is the iterative process of:

- identifying performance or safety gaps,

- proposing modifications,

- validating them under evaluation,

- and promoting them only when governance allows.



### 1.2 Improvement target types

FRANCIS improvement targets include:

- **Capability**: better task completion, broader coverage.

- **Correctness**: fewer errors, stronger validation.

- **Safety**: fewer unsafe outputs, stronger guardrails.

- **Reliability**: fewer crashes/timeouts, better recovery.

- **Efficiency**: lower cost, lower latency, better caching.

- **Usability**: better explanations, better UI/UX, better docs.



### 1.3 Proposal

A **proposal** is a structured change request with:

- motivation and evidence

- affected subsystems

- risk analysis and policy mapping

- evaluation plan and success criteria

- rollback strategy



### 1.4 Experiment

An **experiment** is a controlled comparison of baseline vs candidate(s)

(architectural variants, prompts, routing, thresholds, constraints, etc.)

executed under fixed metrics.



### 1.5 Promotion

**Promotion** is the governance-controlled step of adopting an improvement

candidate as the new baseline for an environment.



### 1.6 Improvement provenance

**Provenance** is the traceability of:

- what data informed the proposal

- what evaluations were run

- what change was made

- who approved it

- what outcomes followed





## 2. Hard constraints and “must never” rules



### 2.1 No privilege escalation by improvement

Self-improvement must never:

- broaden tool permissions/scopes

- weaken sandboxing

- relax safety policies

- reduce logging/auditing

without explicit governance and approvals.



### 2.2 No hidden changes

All improvements that affect behavior must be:

- versioned

- attributable

- logged

- reversible



### 2.3 No training on secrets or prohibited data

Improvement processes must not:

- ingest secrets (tokens, keys)

- store raw regulated data without explicit policy basis

- use private data in ways that violate `privacy.yaml` / `data_governance.yaml`



### 2.4 No “self-referential loopholes”

FRANCIS must not interpret:

- its own outputs as authority

- untrusted text as instructions to change policies

- a user request as authorization to bypass controls



### 2.5 Safety regressions are a hard block

If an improvement increases unsafe behavior beyond thresholds, it is rejected

regardless of capability gains.





## 3. Improvement lifecycle (end-to-end)



### 3.1 Observe

Collect signals from:

- success/failure outcomes

- error patterns

- audit denials and near-misses

- latency and cost

- user feedback

- incident postmortems

- drift detectors



Sources:

- `data/logs/*`

- `data/artifacts/*`

- `data/evolution/*`

- trust metrics



### 3.2 Diagnose the gap

Convert signals into a precise problem statement:

- what fails?

- under what conditions?

- why does it matter?

- what constraints apply?



Produce an “improvement case” record.



### 3.3 Generate candidate interventions

Possible intervention types:

- prompt/routing tweaks

- tool selection constraints

- evaluator improvements

- new guardrails

- caching policy changes

- model/provider changes

- algorithmic changes (retrieval, summarization, planning)

- connector retries/backoff strategies

- workflow/runbook improvements



### 3.4 Pre-register success criteria

Before running experiments, define:

- primary metrics

- acceptable risk envelope

- stopping rules

- rollback requirements



This prevents “p-hacking” by iterating until something looks good.



### 3.5 Run evaluation and experiments

Use:

- offline evaluation suites

- replay tests

- shadow mode (observe-only)

- A/B tests with strict gating

- canary deployments in lower-risk environments



Artifacts:

- `data/artifacts/evaluations/*`

- `data/evolution/improvement_experiments/*`

- `data/evolution/performance_profiles/*`



### 3.6 Review and governance gating

A candidate must pass:

- policy checks

- safety review (including adversarial robustness)

- correctness validation

- operational readiness (deploy, rollback, observability)



High-risk changes require approvals and sometimes human sign-off.



### 3.7 Implement under change control

Implementation should be:

- minimally invasive

- versioned (config and code)

- feature-flagged where possible

- rolled out gradually



### 3.8 Verify

Verification includes:

- unit tests

- integration tests

- evaluation suite re-run

- safety regression suite

- performance checks (latency/cost)

- trust metric updates



### 3.9 Deploy and monitor

After promotion:

- monitor for regressions and drift

- maintain canary checks

- update baselines and documentation



### 3.10 Learn

Record outcomes:

- what worked

- what failed

- update priors and playbooks

- propose further improvements if needed





## 4. Improvement categories and recommended methods



### 4.1 Prompt and orchestration improvements

Targets:

- better decomposition

- less hallucination

- clearer answers

Methods:

- prompt variant experiments

- self-consistency toggles

- evidence requirements tuning



### 4.2 Retrieval improvements

Targets:

- better grounding in sources and memory

- fewer irrelevant retrievals

Methods:

- reranking changes

- embedding model experiments

- chunking strategies

- provenance-aware retrieval rules



### 4.3 Tooling and action planning improvements

Targets:

- fewer unsafe tool calls

- higher success of tool usage

Methods:

- stronger preflight validation

- resource constraints

- dry-run scaffolding

- improved schema enforcement



### 4.4 Safety and guardrails improvements

Targets:

- stronger injection resistance

- fewer policy bypasses

Methods:

- adversarial tests

- stricter sanitization

- layered output verification

- policy/risk model refinement



### 4.5 Performance and cost improvements

Targets:

- lower latency

- lower token usage

Methods:

- caching and memoization

- smarter routing

- concurrency tuning

- rate limiting tuning



### 4.6 Documentation and runbook improvements

Targets:

- fewer operator mistakes

- faster incident resolution

Methods:

- postmortem-driven doc updates

- runbook tests (dry-run simulations)





## 5. Metrics



### 5.1 Core metrics (recommended)

- task success rate (by category)

- policy compliance rate

- unsafe output rate (caught + uncaught estimates)

- tool call success rate

- mean and p95 latency

- cost per successful outcome

- denial rate by gate (permission/trust/readiness)

- operator approval latency

- regression frequency after deploy



### 5.2 Safety metrics (non-negotiable)

- prompt injection detection rate (true positives / false negatives)

- sandbox escape attempts (should be zero)

- prohibited data leakage incidents

- unsafe tool execution attempts blocked



### 5.3 Trust metrics integration

Trust should incorporate:

- accuracy deltas from evaluations

- safety record deltas

- reliability deltas

- compliance deltas



Artifacts:

- `data/trust/metrics/*`

- `data/trust/levels/*`





## 6. Evaluation suites and test strategy



### 6.1 Types of evaluations

- **Unit**: components (parsers, validators)

- **Integration**: end-to-end flows (chat → tool → result)

- **Scenario**: domain-specific workflows

- **Adversarial**: injections, poisoning, deception

- **Replay**: recorded cases

- **Property-based**: invariants (no secrets in logs, etc.)



### 6.2 Golden tasks and fixtures

Maintain a set of stable “golden tasks” for:

- connectors

- summarization

- citations

- policy compliance

- high-risk decision gating



### 6.3 Regression budget

Define allowed regressions:

- capability regressions might be tolerated if safety improves (rare and explicit)

- safety regressions are not tolerated



### 6.4 Evidence-based grading

Prefer evaluations that:

- enforce citations

- compare tool outputs to ground truth

- penalize confident errors more than uncertain abstentions





## 7. Improvement artifacts and storage



Recommended storage layout:



- `data/evolution/improvement_experiments/`

  - experiment specs, variants, results



- `data/evolution/performance_profiles/`

  - baseline and candidate performance snapshots



- `data/evolution/capability_discoveries/`

  - newly discovered useful strategies or patterns



- `data/artifacts/evaluations/`

  - evaluation outputs, scores, reports



- `data/artifacts/reports/`

  - postmortems, synthesis reports, decision memos



All artifacts must:

- include provenance

- be redacted

- reference policies and approvals (if applicable)





## 8. Governance model for improvements



### 8.1 Change classification (recommended)

Classify changes as:

- **Type A: Low risk** (docs, minor UI, non-safety code refactors)

- **Type B: Medium risk** (routing tweaks, retries, caching behavior)

- **Type C: High risk** (permission model, sandbox changes, connector write behavior)

- **Type D: Safety-critical** (industrial controls, regulated workflows)



Each class has:

- required tests

- required reviewers

- required approvals

- allowed environments



### 8.2 Two-person integrity for high risk

For irreversible or safety-critical changes:

- require independent review

- require explicit operator approval

- log dissent if present



### 8.3 Promotion rules

Promotion to production requires:

- passing evaluation thresholds

- no safety regressions

- rollback plan validated

- monitoring dashboards prepared



### 8.4 Rollback rules

Rollback should be:

- rapid (feature flags/config snapshots)

- reversible

- auditable





## 9. Security considerations for self-improvement



### 9.1 Data poisoning risks

Evaluation datasets and replay logs are attack targets.

Mitigations:

- provenance checks

- signed artifacts

- quarantine suspicious inputs

- differential testing vs clean baselines



### 9.2 Prompt injection risks

Treat web and user content as hostile:

- never allow content to instruct policy/config changes

- isolate “instructions” from “evidence”

- require policy engine enforcement



### 9.3 Supply chain risks

Dependency changes require:

- review

- lockfile checks

- reproducible builds

- vulnerability scanning (if available)



### 9.4 Model/provider risks

Changing models can change behavior substantially.

Mitigations:

- staged rollout

- strict evaluation suite gating

- fallback routing





## 10. Practical improvement playbooks



### 10.1 “Postmortem → Regression test” loop

1) Incident occurs

2) Postmortem identifies failure mode

3) Add regression test reproducing it

4) Candidate fixes must pass the new test



### 10.2 “Shadow mode first” for risky changes

1) Deploy candidate in observe-only mode

2) Compare decisions against baseline

3) Promote only if differences are beneficial and safe



### 10.3 “Quality gates” for config-only tuning

For routing/threshold changes:

- run evaluation suite

- run cost/latency profile

- run safety suite

- promote with a rollback toggle



### 10.4 “Improvement debt” tracking

Maintain a backlog of:

- known weaknesses

- missing runbooks

- missing tests

- tech debt

Rank by impact and risk.





## 11. Implementation pointers (code map)



Metalearning and experiment management:

- `src/francis/metalearn/*`



Domain learning loops:

- `src/francis/domain_intelligence/*`



Trust computation and gating:

- `src/francis/trust/*`

- `src/francis/governance/*`



Telemetry and audit:

- `src/francis/telemetry/*`



Operational scripts:

- `scripts/self-evolve.ps1`

- `scripts/self-heal.ps1`

- `scripts/doctor.ps1`





## 12. Appendix — Improvement proposal template (illustrative)



```yaml

proposal_id: improve.2026-01-01.routing.retrieval_rerank_v2

title: "Improve retrieval quality via reranker + provenance-aware filtering"

owner: "francis.metalearn"

created_at: "2026-01-01T00:00:00Z"



problem:

  summary: "High irrelevant retrieval rate in technical Q\&A; increases hallucinations."

  signals:

    - "declining accuracy_scores.json on retrieval-heavy suites"

    - "increased user corrections in certain domains"



constraints:

  policies:

    - "privacy.yaml"

    - "data_governance.yaml"

    - "sandbox.yaml"

  environments: ["dev", "workstation"]



hypotheses:

  - "Reranking improves precision without harming recall"

  - "Provenance filter reduces poisoned or low-quality sources"



change:

  type: "config+code"

  components:

    - "src/francis/chat/continuity/retrieval.py"

    - "config/models/routing.yaml"

  feature_flag: "retrieval_rerank_v2"



evaluation_plan:

  primary_metrics:

    - "task_success_rate +2%"

    - "unsafe_output_rate -10%"

  secondary_metrics:

    - "latency_p95 +<=5%"

    - "cost_per_success +<=3%"

  suites:

    - "retrieval_core"

    - "citation_integrity"

    - "adversarial_poisoning"

  stopping_rules:

    - "any safety regression > threshold → reject"



risk:

  level: "medium"

  rollback: "disable feature flag + restore routing snapshot"



approvals_required:

  - "none in dev"

  - "operator approval required for production promotion"



