==============================================================================

FRANCIS — CROSS_DOMAIN_SYNTHESIS.md

Composing knowledge, constraints, and plans across multiple domains safely

==============================================================================



Purpose

-------

FRANCIS often receives goals that span multiple domains (e.g., “triage an

incident, draft a patch, update runbooks, and notify stakeholders”). This

document defines how the system:

   - Represents multiple domains simultaneously

   - Normalizes evidence across heterogeneous sources

   - Resolves cross-domain conflicts and constraint incompatibilities

   - Produces coherent, auditable syntheses (plans, reports, decisions)

   - Enforces safety, permissions, approvals, and trust boundaries throughout



Read alongside:

   - docs/ARCHITECTURE.md

   - docs/DOMAIN_INTELLIGENCE.md

   - docs/WEB_ACCESS.md

   - docs/POLICIES.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/API_PERMISSIONS.md

   - docs/COLLABORATIVE_INTELLIGENCE.md

   - docs/CONVERSATION_CONTINUITY.md

   - config/policies/trust_boundaries.yaml

   - config/policies/data_governance.yaml

   - config/policies/api_permissions.yaml

   - src/francis/cross_domain/*

   - src/francis/domain_intelligence/*

   - src/francis/memory/*

   - src/francis/internet/*



Design stance:

   - Cross-domain synthesis is both a power multiplier and a failure amplifier.

   - Prefer explicit domain boundaries + typed interfaces over implicit blending.

   - When conflicts exist, default to conservative outputs and require review.

   - Every synthesis must be traceable to sources and policy decisions.



==============================================================================





## 1. What “cross-domain synthesis” means in FRANCIS



### 1.1 Definition

**Cross-domain synthesis** is the process of combining:

- domain knowledge (facts, heuristics, priors),

- constraints (policies, approvals, resource limits),

- evidence (documents, tool outputs, logs),

- and candidate actions (plans, tool calls),

into a single **coherent** and **auditable** output.



This includes:

- multi-step plans that cross tools and subsystems

- integrated reports with citations and provenance

- reconciled decisions when sources disagree

- composite evaluations or simulations that require multiple models



### 1.2 What it is not

Cross-domain synthesis is **not**:

- “averaging” opinions

- freeform blending of instructions from untrusted sources

- bypassing policy by reasoning around it

- automatically executing actions without gating





## 2. Core requirements



Any cross-domain synthesis must satisfy:



1) **Coherence**

   - The output must not contradict itself.

   - Assumptions must be explicit.



2) **Traceability**

   - Every key claim should point to:

     - a tool result,

     - a document,

     - or an explicit assumption.



3) **Safety**

   - Synthesis cannot cause policy bypass.

   - Untrusted inputs cannot become tool instructions.



4) **Boundedness**

   - Domain boundaries and authority boundaries are explicit.

   - Where a boundary is crossed, it is logged and validated.



5) **Reproducibility**

   - Given the same inputs (sources, policies, trust state),

     the synthesis process should yield the same result.



6) **Auditability**

   - The system must emit decision artifacts explaining:

     - what was considered,

     - why one option won,

     - which policies constrained the choice.





## 3. Data model: domain packets



FRANCIS represents each domain as a **Domain Packet**: a typed bundle of:

- vocabulary (ontology)

- priors (assumptions, heuristics)

- constraints (policy refs and local limits)

- evidence (sources + provenance)

- models (predictors/simulators/evaluators)

- candidate actions (domain-specific operations)



### 3.1 Recommended domain packet shape

```yaml

domain_id: security_incident_response

version: "2026-01-01"

ontology_ref: "meta/ontology.yaml#security"

priors_ref: "data/domains/security/priors/*"

constraints:

  policy_refs:

    - "config/policies/offensive_security.yaml"

    - "config/policies/privacy.yaml"

    - "config/policies/data_governance.yaml"

evidence:

  items:

    - source_id: tool:logs_query

      provenance:

        collected_at: "..."

        collector: "worker:triage"

        hash: "sha256:..."

      payload_ref: "data/artifacts/reports/incident_123.json"

models:

  - model_id: threat_scorer_v1

    impl: "src/francis/specializations/security/models/threat_scorer.py"

actions:

  - name: "containment_plan"

    readiness: "review_required"



