==============================================================================

FRANCIS — INDUSTRIAL_SIMULATIONS.md

Digital twins, physics/constraints, safe actuation, and simulation governance

==============================================================================



Purpose

-------

This document defines the industrial simulation and digital twin subsystem in

FRANCIS, including:

   - simulation types (physics, process, discrete-event, hybrid)

   - digital twin lifecycle and model fidelity

   - safety validation and boundary enforcement

   - runbooks for simulation → recommendation → (optional) actuation

   - auditability, provenance, and regulated operation



The guiding idea:

   "Simulate first. Constrain always. Actuate only with authority + evidence."



Read alongside:

   - docs/DIGITAL_TWINS.md

   - docs/SIMULATION_VALIDATION.md

   - docs/THREAT_MODEL.md

   - docs/GOVERNANCE.md

   - docs/API_PERMISSIONS.md

   - docs/TRUST_MODEL.md

   - docs/POLICIES.md

   - config/policies/industrial_safety.yaml

   - config/policies/action_readiness.yaml

   - config/policies/approvals.yaml

   - src/francis/api/routes/industrial.py

   - src/francis/industrial/*

   - data/industrial/*



Design stance

------------

   - Industrial actions are safety-critical by default.

   - The system must support "recommendation-only" operation permanently.

   - Simulation results must carry provenance, assumptions, and validity bounds.

   - Every model is wrong; our job is to quantify where it is useful.



==============================================================================





## 1) Scope and definitions



### 1.1 What counts as "industrial" in FRANCIS

Industrial domains include any system where actions can cause:

- physical harm (people, environment),

- equipment damage,

- safety incidents,

- regulatory violations,

- significant financial loss,

- or operational downtime.



Examples:

- process plants, manufacturing lines

- energy systems (generators, batteries, grids)

- water treatment, HVAC

- robotics and automated material handling

- safety instrumentation and control systems



### 1.2 Simulation vs actuation

- **Simulation**: compute predictions under assumptions; no physical side effects.

- **Recommendation**: propose actions based on simulation and policy constraints.

- **Actuation**: command real systems via connectors/protocols (e.g., Modbus).



Actuation is always behind:

- permission gate,

- trust gate,

- policy gate,

- and (usually) approval gate.



### 1.3 Digital twin

A **digital twin** is a model of an asset/process that includes:

- state representation,

- dynamics/constraints,

- sensors/observables,

- and a mapping from actions → predicted outcomes.



Twins can be:

- **static** (configuration baseline),

- **dynamic** (stateful, time-varying),

- **hybrid** (data-driven + physics-informed).





## 2) Industrial simulation goals



### 2.1 Primary goals

- reduce risk of real-world changes

- predict outcomes under constraints

- detect unsafe proposals before execution

- support operator decisions with quantified tradeoffs

- generate safe runbooks (procedures) with checks



### 2.2 Non-goals

- perfect prediction

- replacing safety engineering

- bypassing human responsibility

- acting without constraints or auditability





## 3) Simulation taxonomy in FRANCIS



FRANCIS supports multiple simulation styles; choosing the right one matters.



### 3.1 Deterministic physics-based simulation

- conservation laws, ODE/PDE models, kinematics/dynamics

- best for: mechanical systems, thermal systems, fluid flow (where modeled)



Tradeoffs:

- requires parameter calibration

- may be expensive computationally



### 3.2 Discrete-event simulation (DES)

- system modeled as events and queues

- best for: manufacturing lines, logistics, throughput optimization



Tradeoffs:

- can miss continuous physical constraints unless hybridized



### 3.3 Control-oriented simulation

- plant model + controller model (PID/MPC)

- best for: setpoint changes, stability, overshoot, safety margins



### 3.4 Process simulation / state machine simulation

- finite states, transitions, recipes, SOPs

- best for: procedural operations, interlocks, alarm handling



### 3.5 Data-driven simulation (surrogate models)

- ML models approximating complex dynamics

- best for: fast what-if exploration

- must include guardrails and validity detection



### 3.6 Hybrid simulation

- physics constraints + learned residuals

- best for: "useful enough" accuracy with real-time feasibility



### 3.7 Monte Carlo / stochastic simulation

- distributions on uncertain parameters

- best for: risk analysis, safety margin quantification





## 4) Simulation lifecycle



### 4.1 Model creation

- define asset/process boundaries

- define inputs/outputs and control variables

- encode constraints (hard/soft)

- attach provenance (sources, assumptions)



Stored in:

- `data/industrial/digital_twins/*`

- `data/industrial/processes/*`

- `data/industrial/simulations/*`



### 4.2 Calibration

Calibration aligns the model to reality:

- parameter fitting using historical telemetry

- sensor bias correction

- alignment to known operating points



Calibration artifacts should include:

- dataset references (not raw secrets)

- calibration method and version

- validation results



### 4.3 Validation

Validation answers:

- where does the model match reality?

- where does it fail?

- what is the maximum safe operating envelope?



Validation artifacts are stored in:

- `data/industrial/safety_validations/*`

- `data/artifacts/evaluations/*` (optional export)



### 4.4 Operation

In operation, simulation is used to:

- explore candidate actions

- compute predicted outcomes

- compute safety margins

- generate recommendations or runbooks



### 4.5 Drift detection and update

Models must detect when they are becoming invalid:

- compare predictions vs observed telemetry

- detect bias or regime change

- trigger recalibration or human review





## 5) Safety model: constraints and interlocks



### 5.1 Hard constraints (never violate)

Hard constraints must be enforced at:

- planning time,

- simulation time,

- and execution time (if actuation is allowed).



Examples:

- max temperature/pressure

- max current/voltage

- min flow rate

- safety interlocks states

- forbidden actuator states

- regulatory limits



### 5.2 Soft constraints (optimize within)

Soft constraints guide optimization:

- energy efficiency

- throughput

- wear reduction

- emissions reduction



Violating soft constraints is allowed only if:

- policy permits,

- and the risk tradeoff is explicitly logged.



### 5.3 Layered safety enforcement

Safety is enforced in layers:



1) **Policy layer** (what is allowed)

- `config/policies/industrial_safety.yaml`



2) **Simulation layer** (what is predicted)

- checks on predicted trajectories



3) **Execution layer** (what actually happens)

- runtime checks, rate limiters, allowlists

- protocol-level safety constraints (where possible)



4) **Human layer**

- approvals, manual confirmations, emergency stop





## 6) From simulation to recommendation



### 6.1 Recommendation object

Every recommendation should be packaged as an artifact with:

- recommendation_id

- asset/process id

- current state snapshot reference

- candidate actions considered

- predicted outcomes per candidate

- constraints checked and margins

- risks, failure modes, mitigations

- approvals required (if any)

- confidence/validity score

- trace to policies and validation results



Store as:

- `data/artifacts/reports/*` or `data/artifacts/runbooks/*`

- and log a decision event in `data/logs/decisions/*`



### 6.2 Validity and confidence

Confidence is not vibes; it is computed from:

- validation coverage for the current regime

- drift score (prediction error trend)

- sensor health and completeness

- model uncertainty (if available)

- novelty detection signals



If confidence is low:

- recommendation must degrade to conservative or abstain

- prefer manual review or further data gathering





## 7) Optimization and planning in industrial contexts



### 7.1 Objectives

Industrial planning often involves multi-objective optimization:

- safety margin (primary)

- uptime and stability

- cost (energy, consumables)

- output quality

- wear and maintenance risk



### 7.2 Pareto frontier handling

FRANCIS should support:

- producing a Pareto set of feasible options

- explaining tradeoffs in plain language

- highlighting dominated options (worse in all objectives)



### 7.3 Constraint-first solving

Optimization must be structured:

1) enforce hard constraints

2) prune unsafe options

3) optimize soft objectives



If the only way to meet the objective violates hard constraints:

- do not propose it

- propose alternatives or abstain





## 8) Optional actuation (high-risk pathway)



### 8.1 Actuation is not default

Default behavior for industrial domains is:

- simulate → recommend → human approves → human executes (manual)



Automatic actuation is only enabled when:

- connector is explicitly allowed

- delegation scope includes the asset and operation

- trust gate allows current risk level

- required approvals exist

- safety validation coverage is sufficient

- runtime sandbox and rate limits are in effect



### 8.2 Execution envelope and rate limiting

Actuation must be constrained by:

- allowed commands list

- parameter bounds

- maximum step change / slew rate

- cooldown timers

- retry limits

- "dead man switch" style timeouts



### 8.3 Pre-flight checks

Before any actuation:

- confirm identity and delegation

- confirm approvals (if required)

- confirm current sensor state is fresh

- confirm drift score below threshold

- confirm simulation predicts safe outcome with margin

- log an "execution intent" event



### 8.4 Post-flight verification

After actuation:

- verify telemetry matches expected trajectory

- detect anomalies

- if deviation: trigger containment/rollback runbook

- record outcome for continuous improvement





## 9) Runbooks and operator workflow



### 9.1 Runbook-first operating style

Runbooks encode safe procedures:

- prerequisites and checks

- step-by-step actions

- validation steps between actions

- stop/rollback conditions

- required approvals and sign-offs



Runbooks live in:

- `data/domains/*/runbooks/*` (domain-scoped)

- `data/artifacts/runbooks/*` (generated)



### 9.2 Human-in-the-loop best practices

For safety-critical systems:

- require plan-first

- require independent review for high-risk changes

- execute in staging/test environment when possible

- use gradual rollouts and monitoring



### 9.3 Incident response integration

Industrial anomalies should link to:

- triage runbooks

- containment plans

- forensics capture

- retrospective reporting



Reference:

- `src/francis/specializations/security/*` (if used for IR patterns)





## 10) Provenance, auditability, and compliance



### 10.1 Provenance requirements

Every simulation/recommendation must include:

- input sources (sensor streams, configs, docs)

- versioned model identifier

- assumptions list

- policy snapshot references

- code version / build id (if available)



### 10.2 Audit logging requirements

For industrial actions (even recommendations):

- log decision artifacts with timestamps

- log policy matches and gate outcomes

- keep redacted trace for operator inspection

- never log secrets or raw credentials



Primary locations:

- `data/logs/audit/*`

- `data/logs/industrial_ops/*`

- `data/logs/decisions/*`



### 10.3 Regulated operation

If environment profile is regulated:

- stricter approvals

- mandatory evidence linkage

- reduced autonomy

- retention rules and access controls apply





## 11) Storage layout (industrial data)



Recommended structure (as already scaffolded):

- `data/industrial/digital_twins/`

  - `_template_asset/` (template for new assets)

- `data/industrial/processes/`

  - `_template_process/`

- `data/industrial/simulations/`

  - `_template_sim/`

- `data/industrial/safety_validations/`



Artifacts:

- `data/artifacts/simulations/`

- `data/artifacts/reports/`

- `data/artifacts/runbooks/`





## 12) Threats and failure modes



### 12.1 Model misuse

Failure: using simulation outside validity bounds.

Mitigation:

- enforce validity checks

- abstain when out-of-distribution

- require human review on low confidence



### 12.2 Sensor spoofing / bad telemetry

Failure: wrong state leads to wrong action.

Mitigation:

- sensor health checks

- redundancy where available

- anomaly detection

- conservative defaults



### 12.3 Injection via documentation or operators

Failure: malicious instructions embedded in documents.

Mitigation:

- treat all text as untrusted input

- isolate evidence from instructions

- approvals for high-risk actions



### 12.4 Over-automation

Failure: the system becomes the only operator.

Mitigation:

- keep manual runbooks valid

- train humans

- require periodic drills



### 12.5 Hidden coupling and cascading effects

Failure: local optimization causes system-level failure.

Mitigation:

- system boundary modeling

- conservative constraints

- staged deployment and monitoring





## 13) Testing and evaluation



Industrial simulation requires rigorous evaluation:

- unit tests for constraints and conversions

- regression tests on known scenarios

- validation suites against historical telemetry

- adversarial tests for unsafe proposals

- drift detection tests



Where possible, export evaluations to:

- `data/artifacts/evaluations/*`





## 14) Implementation pointers (code map)



Suggested code areas (scaffolded in repo):

- API routing:

  - `src/francis/api/routes/industrial.py`

- Simulation and twin management:

  - `src/francis/industrial/*`

- Governance and safety gates:

  - `src/francis/governance/*`

- Policies:

  - `config/policies/industrial_safety.yaml`

  - `config/policies/action_readiness.yaml`

- Telemetry and audit:

  - `src/francis/telemetry/*`





# End of INDUSTRIAL_SIMULATIONS.md



