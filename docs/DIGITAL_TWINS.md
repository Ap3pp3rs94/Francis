==============================================================================

FRANCIS — DIGITAL_TWINS.md

Digital twin modeling, simulation, safety validation, and operational coupling

==============================================================================



Purpose

-------

This document defines how FRANCIS creates, governs, calibrates, validates,

simulates, and operationally couples **digital twins** to real systems.



A digital twin in FRANCIS is NOT a static diagram. It is:

   - a versioned, executable model of a bounded system,

   - continuously reconciled with telemetry,

   - used to simulate outcomes before execution,

   - governed by trust + approvals + policy,

   - and fully auditable.



Read alongside:

   - docs/ARCHITECTURE.md

   - docs/INDUSTRIAL_SIMULATIONS.md

   - docs/SIMULATION_VALIDATION.md

   - docs/CONCURRENCY.md

   - docs/CROSS_DOMAIN_SYNTHESIS.md

   - docs/GOVERNANCE.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/POLICIES.md

   - docs/API_PERMISSIONS.md

   - docs/WEB_ACCESS.md

   - config/policies/industrial_safety.yaml

   - config/policies/approvals.yaml

   - config/policies/trust_boundaries.yaml

   - config/policies/data_governance.yaml

   - config/policies/filesystem.yaml

   - src/francis/api/routes/digital_twin.py

   - src/francis/industrial/*

   - src/francis/system_intelligence/*

   - src/francis/governance/*

   - src/francis/telemetry/*

   - schemas/digital_twin.schema.json



Design stance

------------

   - A twin is allowed to be wrong; it is NOT allowed to be wrong silently.

   - Simulation is mandatory before high-risk real-world actions unless policy

     explicitly permits a waiver and the waiver is approved and logged.

   - “Model authority” is earned via validation and can be revoked via drift.

   - “Execution authority” always remains gated by permissions + trust + approvals.



==============================================================================





## 0) The digital twin contract (what a “twin” guarantees)



A twin must be able to answer, with artifacts:



1) **What is modeled?**

   - explicit boundary, topology, and assumptions.



2) **What version is this?**

   - stable version identifiers and reproducible runs.



3) **What evidence supports trust?**

   - validation metrics, calibration history, drift reports, and safety results.



4) **What are the limits?**

   - safety envelope (soft/hard), valid operating region, and uncertainty bounds.



5) **What changed since last time?**

   - version diff + policy snapshot + calibration delta.



6) **Can we reproduce it?**

   - same inputs + same version + same seed => same output (within stated stochasticity).





## 1) Definitions and scope



### 1.1 Digital twin (FRANCIS definition)

A **digital twin** is a persistent, versioned, executable representation of a

bounded system that includes:



- **Structure**: components and relationships (topology)

- **State**: variables representing the current condition

- **Dynamics**: how the state changes over time

- **Interfaces**: sensors, actuators, and software integration points

- **Constraints**: safety envelopes, invariants, and operational limits

- **Uncertainty**: explicit error/variance modeling

- **Provenance**: where parameters came from and how confident they are



A twin supports both:

- **Prediction** (what happens next?)

- **Counterfactual** (what happens if we do X?)



### 1.2 Simulation vs twin

- **Twin**: the enduring model + its lifecycle + its coupling to telemetry.

- **Simulation**: a single execution of the twin under a scenario.



### 1.3 Calibration vs validation

- **Calibration**: fitting parameters to align model outputs with observed data.

- **Validation**: proving performance against acceptance criteria on held-out or

  out-of-sample scenarios (and confirming safety invariants).



### 1.4 Authority types

FRANCIS distinguishes:

- **Model authority**: whether the twin is trusted to make predictions/advice.

- **Execution authority**: whether actions derived from the twin can be executed.



Execution authority is always gated by:

- permission checks (scopes/delegations),

- trust/action readiness,

- approvals (if required),

- sandbox / environment constraints,

- audit logging.



### 1.5 Where twins live (project conventions)

Primary data locations:

- `data/industrial/digital_twins/*`

- `data/industrial/simulations/*`

- `data/industrial/safety_validations/*`

- `data/knowledge_graph/*` (optional representation of twin entities/relationships)

- `data/logs/*` (audit, decisions, operations)





## 2) Twin types (what kinds of twins FRANCIS supports)



### 2.1 Physical / industrial twins

Examples:

- reactor / process train

- turbine / generator

- battery + inverter system

- HVAC plant

- CNC line / conveyor



Key requirements:

- strong safety envelopes

- conservative uncertainty modeling

- explicit actuator constraints

- mandatory pre-execution simulation for high risk



### 2.2 Cyber / infrastructure twins

Examples:

- service dependency graph

- network topology + failure propagation

- latency + throughput models

- deployment/rollout impact models



Key requirements:

- configuration provenance

- environment snapshotting

- blast-radius modeling

- rollback and failover simulation



### 2.3 Socio-technical / process twins

Examples:

- approvals workflow throughput

- ticket triage pipeline

- staffing vs latency model

- procurement / inventory planning model



Key requirements:

- data governance

- bias monitoring and uncertainty reporting

- explainable assumptions and guardrails



### 2.4 Hybrid and surrogate twins

- **Hybrid**: physics/logic model + data-driven residual correction.

- **Surrogate**: learned approximation of a more expensive simulator.



Rules:

- Surrogates must be versioned and validated like any other model.

- Surrogates must fail “closed” (degrade to safer, slower, more conservative

  methods) if confidence is low.





## 3) Lifecycle: create → calibrate → validate → operate → retire



### 3.1 Create (bootstrap)

Creation outputs:

- twin manifest (boundary, topology, state variables, assumptions)

- safety envelope definitions

- telemetry mapping (sensor → variable)

- initial parameter priors (ranges/distributions)



### 3.2 Calibrate (fit to reality)

Calibration outputs:

- parameter posterior snapshot (or fitted parameter set)

- calibration dataset references + provenance

- error metrics (per-variable + aggregate)

- calibration report artifact



### 3.3 Validate (prove fitness for purpose)

Validation outputs:

- validation suite + scenario definitions

- acceptance criteria results

- safety invariants checks

- uncertainty calibration results (e.g., coverage)



### 3.4 Operate (telemetry-coupled advisory)

Operation outputs:

- state snapshots over time

- rolling drift metrics

- anomaly events

- recommended mitigations (advisory by default)



### 3.5 Retire (archive)

Retirement triggers:

- drift beyond tolerance + no timely recalibration

- system boundary changed (hardware replaced, topology changed)

- policy changes forbid current modeling approach

- decommissioned physical system



Retirement outputs:

- archived manifest, last calibration + validation reports

- explicit “retired reason” audit record





## 4) Twin specification (data model)



### 4.1 Twin manifest (recommended shape)

A twin must have a machine-checkable manifest (schema-backed).



```yaml

twin_id: twin_<domain>_<system>_<nn>

name: "Battery Bank Twin #01"

domain: energy

owner: "ops_team"                # not a secret; ownership for review workflows

status: active                   # active | degraded | frozen | retired

version: "1.2.0"

created_at: "2026-01-01T00:00:00Z"

updated_at: "2026-01-01T00:00:00Z"



purpose:

  description: "Predict SOC/temperature; prevent unsafe charge/discharge commands."

  decision_classes:

    - advisory_prediction

    - safety_limit_enforcement

    - maintenance_planning



boundary:

  includes:

    - battery_cells

    - bms

    - inverter

  excludes:

    - upstream_grid_controls

    - human_override_panel



topology:

  components:

    - id: bms_1

      type: bms

    - id: inverter_1

      type: inverter

  relationships:

    - from: bms_1

      to: inverter_1

      kind: controls



state_variables:

  - name: soc

    unit: percent

    range: [0, 100]

  - name: temp_pack

    unit: celsius

    range: [-20, 70]

  - name: voltage

    unit: volts

    range: [0, 1000]



inputs:

  - name: power_request_kw

    unit: kw

  - name: ambient_temp

    unit: celsius



outputs:

  - name: soc_pred

  - name: temp_pred

  - name: risk_score



dynamics:

  model_type: hybrid             # analytical | hybrid | empirical | surrogate

  solver:

    kind: discrete_time

    dt_seconds: 1

  assumptions:

    - "Thermal model ignores direct sunlight heating."

    - "Cell balancing treated as averaged effect."



safety_envelope:

  soc:

    soft_min: 10

    soft_max: 95

    hard_min: 5

    hard_max: 98

  temp_pack:

    soft_max: 45

    hard_max: 55

  voltage:

    hard_max: 950



uncertainty:

  method: probabilistic_bounds   # none | probabilistic_bounds | ensemble | bayesian

  targets:

    soc_pred:

      expected_abs_error: 2.0

    temp_pred:

      expected_abs_error: 1.5



telemetry_mapping:

  sources:

    - kind: mqtt

      ref: "battery/telemetry"

  sensors:

    - sensor: "bms.soc"

      maps_to: soc

    - sensor: "bms.temp_pack"

      maps_to: temp_pack

    - sensor: "bms.voltage"

      maps_to: voltage



actuation_mapping:

  # what the twin can recommend; execution remains gated elsewhere

  actuators:

    - actuator: "inverter.set_power_kw"

      constraints:

        min_kw: -250

        max_kw: 250



policy_refs:

  - config/policies/industrial_safety.yaml

  - config/policies/data_governance.yaml

  - config/policies/approvals.yaml

  - config/policies/trust_boundaries.yaml



