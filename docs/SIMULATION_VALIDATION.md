==============================================================================

FRANCIS — SIMULATION_VALIDATION.md

Validation, verification, calibration, uncertainty, and governance for sims

==============================================================================



Purpose

-------

This document defines the simulation validation system in FRANCIS:

   - How simulations (including industrial simulations and digital twins) are

     verified (built correctly) and validated (match reality well enough).

   - How calibration, uncertainty quantification (UQ), and sensitivity analysis

     are performed and governed.

   - How simulation outputs become admissible evidence for planning decisions,

     including safety-critical and regulated contexts.

   - How simulation versions, datasets, and results are tracked with provenance

     to keep the system reproducible and auditable.



Simulation is a decision-support instrument. If it is not validated, it is

not trusted—and must not be used to justify high-impact actions.



Read alongside:

   - docs/INDUSTRIAL_SIMULATIONS.md

   - docs/DIGITAL_TWINS.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/ACTION_READINESS.md

   - docs/GOVERNANCE.md

   - docs/POLICIES.md

   - docs/DOMAIN_INTELLIGENCE.md

   - docs/CONCURRENCY.md

   - docs/EXPLANATION_SYSTEM.md

   - docs/ADVERSARIAL_ROBUSTNESS.md

   - config/policies/industrial_safety.yaml

   - config/policies/safety_critical.yaml

   - config/policies/data_governance.yaml

   - config/policies/privacy.yaml

   - config/policies/sandbox.yaml

   - config/policies/action_readiness.yaml

   - config/models/specialized/simulation.yaml

   - schemas/industrial_simulation.schema.json

   - schemas/simulation_env.schema.json

   - schemas/digital_twin.schema.json

   - src/francis/api/routes/simulation.py

   - src/francis/api/routes/industrial.py

   - src/francis/governance/*

   - src/francis/trust/*

   - data/industrial/*

   - data/artifacts/simulations/*

   - data/artifacts/evaluations/*



Design stance

------------

   - Verification ≠ Validation. Both are mandatory, and both are logged.

   - Strong provenance is non-optional: no provenance, no promotion.

   - UQ is mandatory for high-impact decisions; point estimates are not enough.

   - Validation results are environment- and domain-scoped; portability is a claim

     that must be validated itself.

   - Default conservative: when uncertain, abstain or require human review.



==============================================================================





## 0. Executive summary



FRANCIS uses simulations in multiple roles:

- forecasting likely outcomes,

- testing plans safely before acting,

- validating constraints and safety envelopes,

- training runbooks and incident-response playbooks,

- calibrating domain models and digital twins.



To prevent “simulation theater” (pretty outputs with false confidence), FRANCIS

treats simulation outputs as admissible evidence only when:

1) the simulator implementation is verified,

2) the model is validated against relevant data,

3) uncertainty is quantified and within an acceptable envelope,

4) provenance and versioning are complete,

5) governance gates allow the use of simulation evidence for the decision class.



This document defines the procedures, artifacts, and gates that enforce that.





## 1. Definitions



### 1.1 Simulation

A **simulation** is a computational process that maps:

- an initial state,

- a set of model parameters,

- and a policy/plan (inputs)

to predicted trajectories and outcomes.



### 1.2 Verification (built right)

**Verification** answers: *“Did we implement the simulation correctly?”*

Examples:

- code correctness

- numerical method correctness

- unit tests for components

- invariants and conservation checks

- deterministic reproducibility



### 1.3 Validation (right model for purpose)

**Validation** answers: *“Is the simulation accurate enough for this decision?”*

Validation is always:

- scoped to a domain,

- scoped to an operating regime,

- scoped to a use case (“fitness for purpose”).



### 1.4 Calibration

**Calibration** is the process of estimating model parameters so simulated outputs

match observations, within uncertainty.



### 1.5 Uncertainty quantification (UQ)

**UQ** characterizes how uncertain the simulation outputs are, including:

- parameter uncertainty,

- structural/model-form uncertainty,

- measurement noise,

- initial condition uncertainty,

- numerical/discretization error.



### 1.6 Validation regime (operating envelope)

A **validation regime** is the region of conditions under which a model has been

shown to behave acceptably:

- temperature ranges, loads, pressures, speeds,

- network traffic levels,

- user behavior patterns,

- regulatory constraints,

- system configurations.



Using a model outside its validated regime requires a new validation claim.



### 1.7 Ground truth and reference data

**Ground truth** is the best available reference:

- measured sensor data,

- lab experiments,

- operational telemetry,

- historical outcomes,

- audited datasets.



“Ground truth” is often uncertain; its uncertainty must be modeled.



### 1.8 Validation claim

A **validation claim** is a statement of the form:

> For decision class D, in regime R, model M (version V) predicts metric set K

> with error bounds E at confidence C, based on dataset(s) S and procedure P.



Claims must be machine-readable and auditable.





## 2. Where simulation validation is enforced in FRANCIS



### 2.1 Decision gating (simulation evidence admissibility)

Simulation outputs are treated as *evidence objects* and must pass:

- Policy checks (industrial safety, privacy/data governance, sandbox)

- Trust gate (confidence thresholds and safety record)

- Action readiness gate (execution mode requirements; approvals)



A validated simulation can still be blocked if:

- action risk is high,

- approvals are missing,

- trust is insufficient,

- the context is out-of-regime.



### 2.2 Storage and provenance expectations

Expected storage locations:

- `data/industrial/simulations/*` (simulation specs and templates)

- `data/industrial/safety_validations/*` (safety-focused validation artifacts)

- `data/artifacts/simulations/*` (run outputs, traces, plots, summaries)

- `data/artifacts/evaluations/*` (validation evaluation reports)

- `data/knowledge_graph/*` (optional: entities/relationships/provenance links)

- `data/logs/*` (audit trail and enforcement decisions)



Every artifact must contain:

- model version identifiers

- environment fingerprint

- dataset references + hashes

- parameter priors / posteriors (when applicable)

- seed and determinism controls

- evaluator and tool trace metadata





## 3. Simulation types and validation posture



### 3.1 Industrial physics simulations

Examples:

- thermodynamics / heat transfer

- fluid flow

- mechanical stress

- actuator response

- process control loops



Validation posture:

- strict numerical verification

- conservative uncertainty bounds

- emphasis on safety envelope correctness



### 3.2 Digital twins

A **digital twin** is a simulation tethered to a real system via telemetry.

Validation posture:

- continuous calibration

- drift detection and periodic re-validation

- careful handling of sensor noise and missing data

- “safe fallback” when telemetry quality drops



### 3.3 Socio-technical simulations (operations, policy, human behavior)

Examples:

- incident response workflows

- queueing systems and call centers

- organization decision processes

- multi-agent coordination outcomes



Validation posture:

- focus on calibration against historical outcomes

- structural uncertainty is high; results are advisory

- require broader confidence intervals and conservative decisions



### 3.4 Network / security simulations

Examples:

- load testing and throughput

- adversarial scenarios (without enabling offensive misuse)

- reliability and failure injection



Validation posture:

- strong reproducibility

- bounded scenario assumptions

- emphasize “what would break first” rather than “exact predictions”



### 3.5 World-model forecasting

Examples:

- time-series forecasting of domain drift

- regulatory change impact models



Validation posture:

- heavy recency weighting

- frequent re-validation

- explicit abstention when evidence is weak





## 4. Validation levels (graduated rigor)



FRANCIS uses a tiered validation scheme. Higher tiers unlock higher-impact use.



### 4.1 Tier 0 — Unvalidated (exploratory)

Allowed:

- brainstorming

- hypothesis generation

- internal exploration



Not allowed:

- justifying high-impact actions

- safety-critical decisions



Requirements:

- provenance still required

- outputs must be labeled “exploratory / unvalidated”



### 4.2 Tier 1 — Verified implementation

Requirements:

- unit tests pass

- deterministic replays pass

- numerical sanity checks pass (where applicable)



Still not “validated against reality.”



### 4.3 Tier 2 — Validated against reference datasets

Requirements:

- comparison to measured data or reference benchmarks

- error bounds quantified for key metrics

- regime clearly described



### 4.4 Tier 3 — Operational validation (in-situ)

Requirements:

- validated using real operational telemetry

- drift monitoring enabled

- periodic re-validation scheduled

- rollback plan for model updates



### 4.5 Tier 4 — Safety-critical certification path

Requirements:

- strongest evidence and review

- independent verification (two-person integrity)

- conservative UQ and fail-safe rules

- explicit approvals and audit sign-off

- traceable to safety policy requirements



This tier is required for industrial actuator decisions and regulated domains.





## 5. Verification methods (build correctness)



### 5.1 Unit and integration tests

- component unit tests (physics kernels, solvers, parsers)

- integration tests for full pipeline execution

- schema validation for specs (`schemas/*.schema.json`)



### 5.2 Determinism and replayability

For any simulation run used as evidence, record:

- RNG seed(s)

- environment fingerprint (OS, CPU/GPU, library versions)

- solver settings and tolerances

- exact config snapshot



Replays must reproduce within:

- exact match (deterministic sims)

- bounded tolerance (floating-point / parallelism allowed)



### 5.3 Numerical stability and convergence

For numerical sims:

- step-size sensitivity checks

- mesh/discretization refinement checks

- convergence checks on iterative solvers

- conservation-law checks where applicable



### 5.4 Invariants and safety constraints

Examples:

- mass/energy conservation

- non-negativity constraints

- bounded actuator rates

- monotonicity requirements



Violations are hard failures unless explicitly justified by model form.



### 5.5 “Known answer tests”

Use analytic solutions or established benchmarks for:

- canonical flows

- simple thermodynamic cycles

- simple control loops





## 6. Validation methods (fit for purpose)



### 6.1 Define the validation question

Validation always starts with:

- decision class: what decisions does this support?

- metrics: what outputs matter for those decisions?

- regime: where will it be used?

- risk: how harmful is a wrong answer?



### 6.2 Select reference datasets

Reference selection criteria:

- provenance is known

- measurement uncertainty is documented

- coverage of the intended regime is sufficient

- data governance allows usage



For regulated data:

- apply redaction and aggregation policies

- store only the minimum required for validation reproducibility

- keep raw data access tightly scoped and audited



### 6.3 Choose validation metrics

Common metrics:

- MAE / RMSE / MAPE (forecasting)

- calibration curves (probabilistic outputs)

- coverage probability (does the predicted interval contain truth at the expected rate?)

- confusion metrics for categorical outcomes (if applicable)

- constraint satisfaction rate

- safety envelope violations rate



### 6.4 Accept/reject criteria (pre-registered)

Before testing:

- define thresholds per metric

- define confidence levels

- define failure conditions

- define what counts as “out-of-regime”



### 6.5 Cross-validation and holdout strategy

Avoid validating on the same data used to calibrate:

- holdout sets

- time-split validation for temporal data

- scenario-based splits for discrete regimes



### 6.6 External validity and transfer claims

If claiming portability:

- validate across multiple datasets

- validate across multiple operational regimes

- document where the model fails





## 7. Calibration and parameter estimation



### 7.1 Calibration objectives

Calibration should optimize the metrics relevant to decisions, not a generic loss.



### 7.2 Priors, constraints, and identifiability

- Maintain parameter priors (domain knowledge) and keep them explicit.

- Enforce physically plausible bounds.

- Diagnose identifiability: if two parameter sets fit equally well, output UQ

  must reflect that.



### 7.3 Calibration procedures (typical)

- least squares / maximum likelihood (simple cases)

- Bayesian calibration (preferred for UQ-heavy domains)

- sequential assimilation for digital twins



### 7.4 Calibration provenance

Record:

- dataset references (hashes)

- parameter priors

- posterior summaries

- optimization settings

- convergence diagnostics



### 7.5 Calibration drift

For digital twins:

- continuous calibration must be bounded to avoid “chasing noise”

- sudden parameter jumps must trigger investigation





## 8. Uncertainty quantification (UQ)



### 8.1 Why UQ is mandatory

Without UQ, simulations produce false precision.

FRANCIS requires UQ for:

- medium/high-risk decisions

- safety envelope reasoning

- any decision gated by trust thresholds



### 8.2 UQ sources

- parameter uncertainty

- measurement error (sensor noise)

- initial condition uncertainty

- numerical error

- model-form uncertainty (missing physics, simplifying assumptions)



### 8.3 UQ methods (typical toolbox)

- Monte Carlo sampling (baseline approach)

- Latin Hypercube Sampling (efficiency)

- polynomial chaos / surrogate models (when expensive)

- ensemble modeling (multiple plausible model forms)

- interval analysis for bounded worst-case checks

- bootstrapping for dataset-driven uncertainty



### 8.4 Output form requirements

Simulation evidence should include:

- point estimate

- uncertainty interval (credible/confidence interval)

- coverage validation results (does it match observed coverage?)

- explicit “confidence grade” used by trust model



### 8.5 Conservative mode for safety-critical uses

For safety-critical actions:

- prioritize worst-case and bound-based reasoning

- require robust satisfaction: constraints must hold across uncertainty set

- treat unknowns as adversarial within plausible bounds





## 9. Sensitivity analysis



### 9.1 Purpose

Sensitivity analysis answers:

- what parameters matter most?

- where does uncertainty come from?

- which sensors would reduce uncertainty most?



### 9.2 Methods

- one-at-a-time perturbations (quick, limited)

- global sensitivity (Sobol indices, variance-based)

- partial dependence / saliency (for learned components)

- scenario sweeps across regimes



### 9.3 Governance use

Sensitivity outcomes inform:

- instrumentation investments (digital twins)

- policy constraints

- which approvals are required for certain actions

- risk scoring in action readiness





## 10. Safety validation (industrial and high-impact contexts)



### 10.1 Safety envelope validation

Validate not only nominal accuracy, but:

- does the simulation correctly identify unsafe states?

- does it overestimate safety (dangerous) or underestimate safety (conservative)?



The unacceptable failure mode is:

- “declares safe when unsafe.”



### 10.2 Fail-safe and fallback logic

If simulation uncertainty is high:

- default to conservative recommendations

- require human approval

- prefer non-actuation actions (observe, measure, run diagnostics)



### 10.3 Independent review for safety-critical promotion

Safety-critical validation claims require:

- independent reviewer sign-off

- separate evidence verification

- immutable audit artifacts



### 10.4 Red-team testing of assumptions

Simulations can be attacked through:

- poisoned data

- adversarial parameter settings

- regime-shifting inputs

- narrative manipulation in reports



Mitigations:

- provenance checks

- anomaly detection in calibration data

- strict separation between untrusted text and model parameters

- policy engine enforcement on all action outputs





## 11. Provenance, auditability, and reproducibility



### 11.1 Minimum provenance fields (recommended)

Every evidence-grade simulation run should include:

- `simulation_id`

- `model_id` and `model_version`

- `environment_id` (env config + hardware/software fingerprint)

- `dataset_refs` (hashes, provenance IDs)

- `parameter_set` (or references if sensitive)

- `seed`

- `solver_settings`

- `time_started`, `time_finished`

- `operator_identity` / `service_identity`

- `policies_applied` snapshot references

- `validation_tier_claimed` and `validation_tier_verified`



### 11.2 Reproducible builds

Recommended practices:

- containerized runtime for sim execution

- pinned dependencies (lockfiles)

- deterministic settings where possible

- CI/CD verification runs for critical models



### 11.3 Audit trail integration

All validation decisions and promotions must generate:

- audit events (who/what/why)

- policy references

- redaction confirmation





## 12. Versioning and drift



### 12.1 Version everything

Version identifiers should exist for:

- model implementations

- model parameters

- datasets

- simulation environment settings

- evaluation suites

- policies relevant to the claim



### 12.2 Drift detection for operational models

Monitor for:

- input distribution shift

- sensor degradation

- regime changes

- persistent residual growth vs truth



When drift exceeds thresholds:

- downgrade validation tier

- block safety-critical actions

- require re-validation



### 12.3 Safe rollback and canarying

Before promotion:

- run canary evaluations against recent telemetry

After promotion:

- keep last known-good version ready for rollback

- maintain a rolling regression suite





## 13. How validated simulations influence trust and readiness



### 13.1 Trust integration (recommended)

Validated simulation performance can:

- increase confidence in specific decision classes

- improve routing to simulation-specialized models

- raise trust metrics in well-validated regimes



But trust must be domain- and regime-scoped:

- a validated thermal model does not validate a process-control model.



### 13.2 Action readiness integration (recommended rules)

- **Tier 0**: advisory only; no execution justification

- **Tier 1**: can inform planning but requires extra review for high impact

- **Tier 2**: acceptable evidence for medium-risk decisions (with UQ)

- **Tier 3**: acceptable evidence for operational decision support

- **Tier 4**: eligible evidence for safety-critical gating (still requires approvals)



### 13.3 Abstention policy

If:

- the regime is out-of-scope,

- uncertainty is high,

- drift is detected,

then:

- abstain from strong recommendations,

- propose measurement or diagnostic actions,

- and require explicit human decision for execution.





## 14. Validation artifacts (formats and expected contents)



### 14.1 Validation report (human-readable)

A validation report should include:

- scope and purpose

- regime definition

- datasets used and governance constraints

- calibration methods

- verification checks performed

- validation metrics and results

- uncertainty intervals and coverage checks

- failure cases and limitations

- decision admissibility guidance (which actions this supports)



### 14.2 Validation record (machine-readable)

A structured record should include:

- validation claim fields

- numeric metrics

- thresholds

- pass/fail

- provenance references



### 14.3 Evidence packaging

When simulations are used in an explanation or runbook:

- include citations to validation artifacts

- include the tier and regime label

- include uncertainty bounds and confidence grade





## 15. Templates and checklists



### 15.1 Validation plan template (outline)

1) Decision class and risk level

2) Model and version

3) Regime definition

4) Data sources and governance

5) Verification checklist

6) Calibration procedure

7) Validation metrics and thresholds (pre-registered)

8) UQ method and reporting format

9) Sensitivity analysis plan

10) Promotion gate requirements

11) Monitoring and drift thresholds

12) Rollback plan



### 15.2 Safety-critical checklist

- [ ] Tier 4 target explicitly stated

- [ ] Independent review completed

- [ ] UQ demonstrates conservative coverage

- [ ] Worst-case constraints tested

- [ ] Drift monitor configured

- [ ] Approvals recorded and linked

- [ ] Rollback tested

- [ ] Audit trail complete





## 16. Implementation pointers (project map)



Relevant components (typical):

- Simulation API route:

  - `src/francis/api/routes/simulation.py`

- Industrial orchestration:

  - `src/francis/api/routes/industrial.py`

- Governance gates:

  - `src/francis/governance/*`

- Trust system:

  - `src/francis/trust/*`

- Schemas:

  - `schemas/industrial_simulation.schema.json`

  - `schemas/simulation_env.schema.json`

  - `schemas/digital_twin.schema.json`

- Artifacts:

  - `data/artifacts/simulations/*`

  - `data/artifacts/evaluations/*`

- Industrial templates:

  - `data/industrial/simulations/_template_sim`

  - `data/industrial/digital_twins/_template_asset`

  - `data/industrial/processes/_template_process`





# End of SIMULATION_VALIDATION.md



