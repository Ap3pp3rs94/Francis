==============================================================================

FRANCIS — DOMAIN_INTELLIGENCE.md

Domain induction, authority modeling, provenance, and operational runbooks

==============================================================================



Purpose

-------

This document defines the **Domain Intelligence** subsystem in FRANCIS:

   - how FRANCIS learns a domain (from sources + telemetry + outcomes),

   - how it structures, versions, and validates domain knowledge,

   - how it converts knowledge into **runbooks, constraints, and actions**,

   - and how governance + safety policies constrain domain learning and usage.



"Domain intelligence" is how FRANCIS becomes *useful* in a specific area

(energy, devops, legal, healthcare, industrial processes, etc.) without

sacrificing: provenance, safety, auditability, or trust.



Read alongside:

   - docs/ARCHITECTURE.md

   - docs/CROSS_DOMAIN_SYNTHESIS.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/WEB_ACCESS.md

   - docs/POLICIES.md

   - docs/GOVERNANCE.md

   - docs/CONVERSATION_CONTINUITY.md

   - docs/TEMPORAL_INTELLIGENCE.md

   - docs/ATTRIBUTION.md

   - config/policies/web_access.yaml

   - config/policies/data_governance.yaml

   - config/policies/offensive_security.yaml

   - config/policies/privacy.yaml

   - config/policies/approvals.yaml

   - config/policies/trust_boundaries.yaml

   - src/francis/domain_intelligence/*

   - src/francis/internet/* (intake, safety, validation)

   - src/francis/governance/* (approval + policy gates)

   - schemas/domain_spec.schema.json

   - schemas/web_source.schema.json



Design stance

------------

   - Domain learning must be **traceable** (provenance-first).

   - Knowledge must be **versioned** (temporal snapshots + migrations).

   - Knowledge must be **bounded** (safety constraints, trust gating).

   - Knowledge must be **validated** (correctness + drift + recency).

   - Domain outputs must be **operational** (runbooks, constraints, checks).



==============================================================================





## 0) What “domain intelligence” guarantees (the contract)



A domain in FRANCIS must be able to answer, with artifacts:



1) **What do we believe?**

   - explicit claims with confidence and evidence.



2) **Why do we believe it?**

   - citations / provenance and validation records.



3) **What is the boundary?**

   - what the domain covers, and what it explicitly does not.



4) **How fresh is it?**

   - recency checks, temporal versions, and drift signals.



5) **How safe is it to use?**

   - policy constraints, prohibited actions, and trust thresholds.



6) **How do we operationalize it?**

   - runbooks, checklists, constraints, and tool-access guidance.



If any part is missing or fails validation:

- the domain degrades to conservative behavior (advisory-only, ask-for-approval,

  abstain, or require human decision).





## 1) Definitions



### 1.1 Domain

A **domain** is a bounded scope of knowledge and operational practice (e.g.,

“telecommunications provisioning”, “industrial safety validation”, “finance”).

It includes:

- concepts and ontology (what things are),

- entities (what exists),

- relationships (how things connect),

- constraints (what must never happen),

- interventions (what actions are possible),

- and runbooks (what to do in practice).



### 1.2 Source

A **source** is any input used to derive domain knowledge:

- documents (policies, manuals, specs)

- web pages (subject to web access policy + approvals)

- code repositories

- telemetry (metrics/logs)

- human guidance (with attribution and role context)



All sources must carry provenance and classification.



### 1.3 Evidence

**Evidence** is a unit of support for a claim:

- citation + excerpt reference

- tool output

- validated telemetry slice

- controlled experiment result

- reviewed human-provided statement (with identity context)



### 1.4 Claim

A **claim** is an asserted statement the domain believes, such as:

- a factual statement,

- a constraint/invariant (“never do X under condition Y”),

- a best practice,

- or an operational heuristic.



Claims are stored with:

- confidence,

- evidence links,

- scope/boundary tags,

- recency metadata,

- and safety classification.



### 1.5 Domain intelligence vs knowledge graph

- The **knowledge graph** is the representation substrate (entities + edges).

- **Domain intelligence** is the full lifecycle: intake → induction → modeling →

  validation → operationalization → temporal versioning → governance.





## 2) Storage model (how domains are laid out on disk)



Primary domain storage root:

- `data/domains/`



Registry:

- `data/domains/_registry.json` (domain index: ids, status, versions, metadata)



Template scaffold:

- `data/domains/_template_domain/`



Recommended per-domain layout (aligned with your repo tree):



