==============================================================================

FRANCIS — SPECIALIZATIONS.md

Domain specializations: manifests, capabilities, knowledge, evaluation, routing

==============================================================================



Purpose

-------

This document defines the specialization system in FRANCIS:

   - How domain "specializations" are represented and loaded

   - How capabilities, prompts, ontologies, and evaluation suites attach to a domain

   - How specialization routing selects models and agent roles per task

   - How specialization knowledge is stored, governed, and updated safely

   - How specializations are packaged, versioned, validated, and federated



Specializations are FRANCIS’s way to be both:

   - broad (general reasoning), and

   - deep (domain-specific competence),

while keeping governance, safety, and reproducibility intact.



Read alongside:

   - docs/DOMAIN_INTELLIGENCE.md

   - docs/PLUGINS.md

   - docs/POLICIES.md

   - docs/TRUST_MODEL.md

   - docs/ACTION_READINESS.md

   - docs/CONVERSATION_CONTINUITY.md

   - docs/CROSS_DOMAIN_SYNTHESIS.md

   - docs/INTEGRATION_GUIDE.md

   - docs/WEB_ACCESS.md

   - config/models/routing.yaml

   - config/capabilities/taxonomy.yaml

   - config/capabilities/catalog.yaml

   - config/prompts/specialization_selector.yaml

   - src/francis/specializations/*

   - src/francis/domain_intelligence/*

   - src/francis/llm/router.py

   - src/francis/agent/*

   - schemas/domain_spec.schema.json

   - schemas/evaluation_suite.schema.json

   - meta/ontology.yaml

   - data/domains/*

   - specializations/*



Design stance

------------

   - Specialization is an interface contract: capabilities + knowledge + evals.

   - Default safe: specializations never bypass policy, permissions, or trust.

   - Versioned and auditable: manifests and artifacts are provenance-carrying.

   - Decoupled: you can add/remove specializations without changing the kernel.

   - Measured: selection is driven by evaluation signals and trust metrics.



==============================================================================





## 1. What is a specialization?



A **specialization** is a domain package that equips FRANCIS to perform well in a

specific problem area (e.g., energy, healthcare, devops, industrial control) by

providing:



- **Capabilities**

  - domain tools and internal skill modules

  - task patterns / runbooks

  - domain-specific constraints



- **Knowledge**

  - curated sources (safe references and citations)

  - ontologies / taxonomies

  - “domain priors” and assumptions



- **Prompts**

  - instruction templates for domain reasoning

  - structured output schemas and rubrics



- **Evaluation suites**

  - tests to detect competence regressions

  - safety / policy compliance checks in-domain

  - scenario and “golden case” benchmarks



- **Routing hints**

  - which model(s) to use for which domain tasks

  - which agent roles to involve (researcher, reviewer, planner, etc.)



Specializations are not “new models.” They are domain instrumentation around

models and agents.





## 2. Specializations in the repository



### 2.1 On-disk layout (typical)



`specializations/<domain>/`

- `manifest.yaml`                       (required)

- `capabilities/`                       (optional but common)

- `knowledge/`                          (optional but common)

- `models/`                             (optional; domain adapters)

- `evaluations/`                        (optional but recommended)



`specializations/_shared/`

- `constraints/`                        (shared constraints)

- `evaluations/`                        (shared eval suites)

- `ontologies/`                         (shared ontologies)

- `playbooks/`                          (shared runbooks)

- `prompts/`                            (shared prompt fragments)

- `simulation/`                         (shared simulation harness)



These are loaded by:

- `src/francis/specializations/loader.py`

- `src/francis/specializations/registry.py`

- `src/francis/specializations/selector.py`



### 2.2 Manifest is the contract



Every specialization is anchored by `manifest.yaml`.

It is the minimum viable interface between a domain package and the core system.



A specialization may have extensive content, but **the manifest defines what

exists, where it is, and how it should be used**.





## 3. Specialization lifecycle



### 3.1 Creation

1) choose domain id and name

2) create `specializations/<domain>/manifest.yaml`

3) define capabilities and constraints

4) attach knowledge references + provenance rules

5) add evaluation suite (minimum smoke tests)

6) register routing hints



### 3.2 Activation

- specialization becomes discoverable by the selector

- capabilities become eligible for tool selection (subject to policy gates)

- prompt fragments become available to orchestration



### 3.3 Operation

- tasks routed into specialization context

- actions gated by permissions, trust, action readiness

- artifacts recorded and linked to specialization id



### 3.4 Evolution

- knowledge updates (curated and provenance-preserving)

- new capabilities and runbooks

- improved evaluation suites

- trust metrics updated based on outcomes



### 3.5 Deprecation

- mark as deprecated in manifest

- selector stops routing new work by default

- keep artifacts for audit; optionally archive





## 4. Specialization selection and routing



### 4.1 The selector’s job

Given a user request, the selector determines:

- which specializations are relevant (0–N)

- which agent roles should participate

- which model profiles should be used (reasoning/research/simulation/etc.)

- which safety posture is required



Inputs (typical):

- request classification (domain, sensitivity, risk)

- conversation context and user intent

- available tools/connectors in environment

- trust state and policy constraints

- historical performance signals



### 4.2 Multi-specialization routing

Many real tasks are cross-domain (e.g., “industrial + security + governance”).

FRANCIS supports:

- primary specialization + secondary specializations

- cross-domain synthesis (see docs/CROSS_DOMAIN_SYNTHESIS.md)

- explicit conflict resolution rules:

  - prefer stricter policy constraints

  - require shared vocabulary mapping via ontology

  - preserve provenance per domain contribution



### 4.3 Fallback behavior

If specialization selection is uncertain:

- default to general reasoning profile

- request more context only if necessary

- avoid risky tool actions

- use conservative assumptions with explicit uncertainty





## 5. Capability model inside a specialization



### 5.1 Capability types

A specialization can provide:

- **Internal capabilities** (pure code modules)

  - e.g., analyzers, planners, scoring functions

- **Connector-backed capabilities**

  - tools that call external systems (GitHub, Jira, DBs, etc.)

- **Runbook capabilities**

  - structured procedural knowledge and checklists

- **Simulation capabilities**

  - environment + model specs for safe testing



Capabilities must be registered in:

- `config/capabilities/catalog.yaml`

- `config/capabilities/aliases.yaml`

- `config/capabilities/taxonomy.yaml`

and must respect:

- `config/capabilities/trust_permissions_map.yaml`



### 5.2 Capability constraints

A specialization can narrow allowed behavior by attaching constraints:

- allowed operations

- allowed resources

- data classifications

- rate limits and query limits

- allowed file paths or network domains



Constraints are enforced by:

- permission gate (scopes/delegations)

- policy engine (domain rules)

- sandbox (resource limits)

- trust + readiness gating





## 6. Knowledge inside a specialization



### 6.1 Knowledge forms

A specialization’s knowledge can include:

- curated documents and summaries

- citation-safe web sources (with provenance)

- ontologies and entity dictionaries

- priors and heuristics (explicit assumptions)

- simulation parameters (with uncertainty bounds)



### 6.2 Knowledge governance

Knowledge is subject to:

- privacy/data governance rules

- regulated domain rules (when applicable)

- provenance and attribution requirements

- web access policy constraints



Key rules:

- never store secrets as “knowledge”

- never store raw PII unless explicitly allowed by policy and protected

- keep provenance metadata alongside derived artifacts



### 6.3 “Domain priors” vs “facts”

Specializations may provide priors (typical values, default thresholds, heuristics).

Priors must be labeled as priors, not asserted as facts.

When priors are used, FRANCIS must:

- disclose assumptions,

- quantify uncertainty where possible,

- and prefer measurement/verification for high-impact decisions.





## 7. Evaluation: how we know a specialization works



### 7.1 Why domain evals are mandatory

A specialization is only “real” if:

- it improves outcomes measurably,

- and it does not violate safety/policy constraints.



### 7.2 Evaluation suite types

A specialization should include:

- **Smoke tests**

  - import/load tests

  - schema validation

- **Competence tests**

  - domain question benchmarks

  - scenario-based tasks

- **Safety tests**

  - policy compliance under pressure

  - refusal correctness

  - redaction checks

- **Tooling tests**

  - connector stubs and replay tests

  - rate-limit and permission enforcement tests

- **Regression tests**

  - golden-case snapshots for stable outputs



### 7.3 Evaluation results and trust

Evaluation outcomes feed into:

- trust metrics per domain

- routing preference weights

- readiness requirements

- automatic downgrades on regression





## 8. Specialization manifests (recommended schema)



`manifest.yaml` should be machine-checkable and include:



- `id`: stable identifier (e.g., `energy`, `devops`)

- `name`: display name

- `version`: semantic version for the specialization package

- `status`: `active | deprecated | experimental | disabled`

- `description`: purpose and scope

- `owners`: maintainers or stewardship group

- `capabilities`:

  - lists of capability ids / modules / runbooks

- `knowledge`:

  - directories and source registries

  - provenance requirements

- `ontologies`:

  - ontology references

  - entity dictionaries

- `evaluations`:

  - suite ids and paths

  - minimum pass thresholds (optional)

- `routing_hints`:

  - model profile preferences

  - agent role suggestions

  - risk posture default

- `constraints`:

  - safety limits and domain-specific restrictions

- `federation`:

  - shareable artifacts and export rules (optional)



Example shape (illustrative):



```yaml

id: energy

name: Energy Systems

version: 1.2.0

status: active

description: Modeling, planning, and analysis for energy generation, storage, and grids.

owners:

  - team: domain-engineering

capabilities:

  internal:

    - energy_demand_forecast

    - storage_dispatch_planner

  runbooks:

    - energy_incident_response

knowledge:

  paths:

    - knowledge/

  provenance:

    require_citations: true

    allowed_sources: [academic, documentation]

ontologies:

  - ref: _shared/ontologies/energy.yaml

evaluations:

  - id: energy_smoke

    path: evaluations/smoke.yaml

  - id: energy_regression

    path: evaluations/regression.yaml

routing_hints:

  primary_profile: research

  secondary_profiles: [reasoning, simulation]

  roles: [planner, researcher, reviewer]

constraints:

  data_classification_allowed: [public, internal]

  requires_uq_for_high_impact: true

federation:

  export:

    allow: true

    share: [runbooks, public_sources, eval_results_summary]



