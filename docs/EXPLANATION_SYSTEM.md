==============================================================================

FRANCIS — EXPLANATION_SYSTEM.md

Decision transparency, evidence grounding, and audit-grade rationale

==============================================================================



Purpose

-------

This document defines the Explanation System for FRANCIS:

   - how FRANCIS explains *why* it chose an action or answer,

   - how evidence is collected, normalized, ranked, and cited,

   - how uncertainty and confidence are communicated,

   - how explanations are made auditable without leaking secrets,

   - how explanations integrate with governance, permissions, and trust gates,

   - and how explanations are rendered in the UI (Explanation Explorer).



The Explanation System is not "nice-to-have" UX.

It is a safety + reliability subsystem that:

   - reduces hallucinations and overconfidence,

   - makes decisions reviewable and repeatable,

   - supports regulated and safety-critical deployments,

   - and supports forensics (who/what/when/why).



Read alongside:

   - docs/TRUST_MODEL.md

   - docs/GOVERNANCE.md

   - docs/POLICIES.md

   - docs/API_PERMISSIONS.md

   - docs/ATTRIBUTION.md

   - docs/WEB_ACCESS.md

   - docs/CONVERSATION_CONTINUITY.md

   - config/policies/data_governance.yaml

   - config/policies/privacy.yaml

   - config/policies/action_readiness.yaml

   - schemas/explanation.schema.json

   - schemas/action_request.schema.json

   - schemas/action_result.schema.json

   - src/francis/explanation/*

   - src/francis/telemetry/audit.py



Design stance

------------

   - Explainability is a *contract*, not a vibe.

   - Policies and secrecy constraints override completeness.

   - Prefer grounded, evidence-linked explanations over eloquent stories.

   - Uncertainty is explicit; confidence is earned, not asserted.

   - Explanations must survive adversarial review (internal or external).



==============================================================================





## 0) Explanation System contract



When FRANCIS produces an explanation for an answer or action, it MUST be able to

emit (at minimum) the following fields, even if some are empty for safe reasons:



1) **What happened** (or what is being proposed)

   - action/decision summary



2) **Why** (rationale)

   - key reasons

   - key tradeoffs



3) **Evidence**

   - list of evidence items (tool outputs, documents, policies, user constraints)

   - provenance metadata



4) **Assumptions**

   - assumptions and defaults used

   - what was *not* verified



5) **Uncertainty**

   - confidence (calibrated, not rhetorical)

   - known unknowns + sensitivity triggers



6) **Constraints \& gates**

   - permission gate results (allow/deny rationale)

   - trust/readiness/approval requirements



7) **Safety \& privacy**

   - redactions performed

   - withheld details rationale (without revealing withheld content)



If an explanation cannot satisfy this contract (e.g., missing evidence, conflicting

inputs), the system must:

- downgrade claims,

- abstain where necessary,

- and propose evidence-gathering steps (VoI-style).





## 1) Core concepts



### 1.1 Explanation vs justification vs audit

- **Explanation**: a structured account of reasons and evidence.

- **Justification**: a defensible argument for why a choice is acceptable under

  policy, safety, and objectives (often includes risk tradeoffs).

- **Audit record**: immutable event trail of what decisions/actions occurred,

  with references to evidence and configurations used.



FRANCIS should generate all three as separate artifacts:

- explanation payload (human-facing)

- justification payload (review-facing)

- audit event (forensic/log-facing)



### 1.2 Evidence

Evidence is any artifact that supports a claim:

- tool outputs (preferred when available)

- configuration/policy snapshots

- local documents / attachments

- user-provided constraints

- web sources (only if allowed; must carry provenance)

- test results, evaluations, simulation outputs



Evidence is never “because the model said so”.



### 1.3 Provenance

Provenance answers:

- where this evidence came from,

- when it was obtained,

- under what policies,

- with what identity,

- and whether it was modified (redaction/normalization).



### 1.4 Claim

A claim is a statement with a truth value (or a probability).

Claims are categorized and scored.



### 1.5 Confidence

Confidence is a calibrated estimate of correctness given:

- evidence quality,

- evidence freshness,

- agreement/consensus,

- historical reliability of the pipeline on similar tasks,

- and model uncertainty.



Confidence is not “how confident the assistant sounds”.



### 1.6 Redaction

Redaction is removal or masking of sensitive content while retaining enough

structure to remain auditably meaningful.



Examples:

- token → `***`

- email → `u***@domain.com`

- path constraints shown, but file contents omitted





## 2) Principles (non-negotiables)



### 2.1 Groundedness over fluency

If evidence is weak:

- reduce scope,

- reduce certainty,

- or ask for more inputs.



### 2.2 Explicit uncertainty

Every non-trivial output should include:

- confidence band,

- and the top 1–3 uncertainty drivers.



### 2.3 Policy-aware transparency

Explanations must not leak:

- secrets,

- prohibited data classes,

- or disallowed operational details.



But they must still explain *why something is withheld*.



### 2.4 Deterministic traceability

Given a decision artifact and referenced evidence IDs, an auditor should be able to:

- reproduce the decision context,

- re-run checks,

- and compare to current policy (drift detection).





## 3) Explanation types (what FRANCIS can produce)



The system supports multiple explanation modes. Selection depends on:

- user intent,

- environment mode,

- action risk,

- and policy constraints.



### 3.1 Summary explanation (default)

- short rationale

- key evidence references

- confidence and top uncertainties



### 3.2 Step-by-step reasoning (procedural)

- ordered steps

- intermediate states

- checkpoints and verification gates



Used for:

- runbooks

- migrations

- multi-step operations



### 3.3 Causal chain explanation

- cause → effect chain

- dependencies

- counterfactual notes



Implemented via:

- `src/francis/explanation/decision_justification/causal_chain.py`



### 3.4 Risk tradeoff explanation

- why risk is acceptable (or not)

- what mitigations exist

- what approvals/gates apply



Implemented via:

- `risk_tradeoff_explainer.py`



### 3.5 Counterfactual explanation

- “If we had chosen X instead of Y, then…”

- used to explain preference between alternatives



Implemented via:

- `counterfactual_explainer.py`



### 3.6 Assumption listing

- enumerates assumptions and their impact

- proposes validation steps



Implemented via:

- `knowledge_articulation/assumption_lister.py`



### 3.7 Teaching explanation

- pedagogical mode (simplified)

- checks for misconceptions

- includes exercises/quizzes (if enabled)



Implemented via:

- `explanation/teaching/*`



### 3.8 Transparency explanation (meta)

- what sources were used

- how confidence was computed

- how policies affected the output



Implemented via:

- `explanation/transparency/*`





## 4) Explanation generation pipeline



### 4.1 Pipeline overview

1) **Request classification**

   - determine if this is: answer, plan, tool execution, policy decision, etc.



2) **Evidence collection**

   - gather tool results, config snapshots, policy references, attachments, web sources



3) **Evidence normalization**

   - canonicalize fields, strip secrets, attach provenance



4) **Claim extraction**

   - identify major claims that need support



5) **Evidence-to-claim linking**

   - map claims → supporting evidence items

   - detect unsupported claims



6) **Conflict detection**

   - identify contradictions across evidence sources

   - resolve or downgrade



7) **Confidence calibration**

   - compute confidence based on evidence, recency, conflict, and task history



8) **Policy and privacy pass**

   - redact

   - enforce disclosure limitations



9) **Explanation rendering**

   - choose mode and produce structured output



10) **Artifact storage**

   - store explanation object and index references

   - write audit event pointing to it



### 4.2 Relationship to conversation continuity

Explanations should link to:

- conversation ledger entries

- the context snapshot used at decision time

- the specific prompt template version (if applicable)





## 5) Evidence model (recommended structure)



### 5.1 Evidence item schema (conceptual)

Evidence items should be machine-checkable and referenced by ID.



```yaml

evidence_item:

  evidence_id: "ev_2026_01_01T120000Z_9f2c"

  type: "tool_result"              # tool_result | policy | config | doc | web | user_input | test | simulation

  title: "Permission gate decision"

  source:

    system: "francis"

    module: "src/francis/governance/api_permission_gate.py"

    ref: "audit:event:aud_abc123"

  collected_at: "2026-01-01T12:00:00Z"

  freshness:

    max_age_seconds: 300

    observed_age_seconds: 2

  integrity:

    hash_sha256: "..."             # optional

    signed: false

  sensitivity:

    classification: "internal"     # public | internal | confidential | regulated

    redacted: true

    redaction_reason: "contains credential identifiers"

  payload_ref:

    uri: "data/artifacts/explanations/ev_...json"



