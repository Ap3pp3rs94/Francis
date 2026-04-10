==============================================================================

FRANCIS — HUMAN_AI_SYMBIOSIS.md

Mixed-initiative operation, operator experience, and human-centered control

==============================================================================



Purpose

-------

This document defines how FRANCIS is designed to work *with* humans:

   - as a decision-support and execution system (when authorized),

   - as a transparent collaborator (explanations + evidence),

   - and as a safely governed tool user (approvals + trust + auditability).



"Symbiosis" here is not marketing — it is an operational contract:

   - Humans remain accountable and in control of high-impact outcomes.

   - The system remains useful without demanding constant micromanagement.

   - Boundaries are explicit, enforceable, and visible in the UI.



Read alongside:

   - docs/GOVERNANCE.md

   - docs/API_PERMISSIONS.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/POLICIES.md

   - docs/EXPLANATION_SYSTEM.md

   - docs/CONVERSATION_CONTINUITY.md

   - docs/CONCURRENCY.md

   - docs/CHAT_UI.md

   - config/policies/approvals.yaml

   - config/policies/action_readiness.yaml

   - config/policies/privacy.yaml

   - src/francis/symbiosis/*



Design stance

------------

   - Mixed-initiative by default: the human sets intent; the system proposes

     and executes *only when allowed*.

   - The UI is a control surface, not a chat toy: it must display state,

     gates, risks, and what will happen next.

   - Explanations are first-class artifacts: every consequential action is

     explainable and auditable without leaking secrets.

   - The system must be safe under adversarial inputs and social pressure.



==============================================================================





## 1) Principles of human–AI symbiosis



### 1.1 Human sovereignty

FRANCIS is designed so that:

- humans set goals and constraints,

- humans can override or stop execution,

- and humans explicitly approve high-risk actions.



The system does not "take over" — it *assists*.



### 1.2 Bounded autonomy

Autonomy is never global. It is:

- scoped (what tools/resources),

- conditioned (what trust thresholds),

- gated (what approvals),

- and revocable (immediate stop + delegation revocation).



### 1.3 Legibility over magic

The system must show:

- what it believes,

- why it believes it,

- what it intends to do,

- what it is allowed to do,

- and what it refused to do.



Opaque helpfulness is unsafe.



### 1.4 Cost-awareness

Good symbiosis minimizes:

- operator attention cost,

- repeated clarification,

- and "compliance theater" (busywork approvals).



FRANCIS should absorb complexity while keeping humans informed.



### 1.5 Accountability and auditability

When the system acts:

- the responsible identity is known,

- the authority chain is traceable,

- and the action is reconstructable from logs and artifacts.



### 1.6 Safety against manipulation

FRANCIS must resist:

- prompt injection,

- social engineering ("just do it"),

- urgency pressure,

- and authority impersonation.



The system treats all text as untrusted input unless proven otherwise.





## 2) Operational modes (how humans and the system share control)



FRANCIS supports multiple *interaction modes*. These are not UX preferences — they

are governance-enforced operating regimes.



### 2.1 Explain-only mode

- The system proposes plans, risks, and options.

- No tool execution.

- Useful for: early scoping, policy review, regulated environments.



### 2.2 Plan-first mode (recommended default)

- The system produces a plan + explicit execution steps.

- The operator approves the plan (or edits it) before execution.

- Suitable for: most non-trivial tasks.



### 2.3 Execute-with-gates mode

- The system may execute low-risk steps automatically.

- High-risk steps trigger approvals.

- Suitable for: maintenance tasks, routine operations.



### 2.4 Fully manual mode

- The system never executes tools.

- It outputs copy/paste commands, runbooks, or scripts.

- Suitable for: airgapped or strict compliance contexts.



### 2.5 Emergency mode

- Requires emergency approval artifacts.

- Enables narrowly-scoped actions under strict audit rules.

- Forces retrospective creation and incident tagging.



Mode selection is governed by:

- environment profile (dev/production/regulated/etc.)

- trust state

- approvals and delegation scope

- policy engine rules





## 3) Roles and responsibilities



Human–AI symbiosis improves when roles are explicit.



### 3.1 Human roles (recommended)

- **Operator**: primary user interacting with the system

- **Approver**: authorizes high-impact actions (may be same as operator in small setups)

- **Reviewer**: checks safety/correctness (separate role for high-risk domains)

- **Auditor**: post-hoc verification/certification role



### 3.2 System roles

- **Planner**: decomposes goals into steps and dependencies

- **Executor**: runs tools within constraints

- **Reviewer**: performs safety review checks (internal)

- **Explainer**: produces user-facing rationale and evidence trails



A single runtime process may embody multiple system roles, but all outputs must

be tagged with role context for auditability.





## 4) Interaction contract (what the system owes the human)



Every meaningful interaction should satisfy:



### 4.1 State disclosure

The UI must show:

- current environment mode (dev/production/regulated/airgapped)

- whether web access is enabled

- whether writes are enabled

- active identity (user/service/delegated)

- trust level and what it implies

- pending approvals required for the next step



### 4.2 Intent reflection

Before executing risky actions, FRANCIS must confirm:

- the target resource,

- the intended side effects,

- and the rollback plan (if applicable).



### 4.3 Options, not ultimatums

FRANCIS should present alternatives:

- safer version (dry-run / limited scope)

- faster version (requires approval)

- reversible version (staging first)

- manual version (operator executes commands)



### 4.4 Explicit uncertainty

When uncertain, the system must:

- quantify uncertainty where possible,

- identify missing data,

- propose low-risk probes,

- and avoid irreversible actions.



### 4.5 Compressed + expandable explanations

Default explanation should be short and safe, with expandable:

- evidence list

- policy rules matched

- gate outcomes

- tool trace summaries





## 5) Human-centered safety controls



### 5.1 Approval UX patterns

Approval requests should include:

- what will happen if approved

- why approval is needed (policy + risk)

- constraints (scope, expiration, rate limits)

- the minimal information needed to decide

- an explicit "deny" path that is easy and safe



### 5.2 Two-step confirmation for irreversible actions

For destructive operations:

- show explicit consequences

- require an additional confirmation phrase or UI action

- optionally require two-person approval



### 5.3 Reversible by default

Where possible:

- prefer idempotent actions

- create backups/snapshots first

- use staged rollouts

- implement rollback hooks



### 5.4 Stop button and immediate revocation

Humans must be able to:

- stop in-flight execution

- revoke delegations

- disable specific tools/connectors

- switch to manual mode instantly



### 5.5 "No surprises" external comms

For email, SMS, Slack, Teams:

- show message preview

- show recipient list and channels

- show attachments (and redactions)

- require approval where configured



### 5.6 Privacy by default

- avoid showing secrets

- redact sensitive values in logs and UI

- minimize copying of PII into chat history

- prefer pointers (IDs, references) over payloads





## 6) Cognitive offloading (what the system should take on)



Symbiosis is strongest when the system reduces cognitive load responsibly.



### 6.1 Memory scaffolding

FRANCIS should maintain:

- persistent summaries (rolling)

- decisions and rationales

- task status

- constraints and preferences



Primary artifacts:

- `data/conversations/summaries/rolling_summary.md`

- `data/conversations/ledger/*`



### 6.2 Task decomposition

FRANCIS should:

- break down ambiguous requests into actionable tasks

- surface dependencies

- propose sequencing and time estimates (when helpful)

- generate checklists and runbooks



### 6.3 Evidence organization

FRANCIS should:

- collect sources and attach provenance

- highlight disagreements

- keep "why" separate from "what to do"



### 6.4 Decision support

For decisions, FRANCIS should provide:

- tradeoff table

- risks and mitigations

- "minimum safe plan" option

- "fastest acceptable plan" option



### 6.5 Attention management

The system should:

- batch low-value notifications

- highlight only critical changes

- avoid repeated questions when state is already known





## 7) Communication style and operator experience



### 7.1 Cadence control

The system must be able to operate in a cadence the operator prefers:

- one-file-at-a-time workflows

- bulk plan + incremental execution

- strict "do not proceed without approval"



### 7.2 Plain language first

Complex internals should be:

- summarized in plain language

- with technical detail expandable



### 7.3 Consistency of interface

The UI should consistently show:

- action cards for tool calls

- gate outcomes

- artifacts produced

- links to logs/approvals



### 7.4 Error behavior

When something fails:

- explain what failed (safe detail)

- show what was attempted

- show next steps and safe remediation options

- never blame the operator





## 8) Symbiosis under adversarial conditions



### 8.1 Treat all text as untrusted

Any instruction originating from:

- web pages,

- attachments,

- collaborators,

- federated peers,

should be treated as untrusted.



The system must separate:

- extracted facts/evidence

- from operational instructions.



### 8.2 Social engineering resistance

FRANCIS must not change safety posture due to:

- urgency language (“ASAP”, “emergency”)

- appeals to authority (“CEO said so”)

- threats or pressure

- repeated persuasion



Only governance artifacts (delegations/approvals/policy) can change authority.



### 8.3 Prompt injection resilience

When ingesting documents, FRANCIS must:

- strip or isolate instructions

- apply content filter rules

- require explicit operator confirmation for tool actions

- log the presence of suspicious patterns





## 9) Collaboration (humans + internal agents + federation)



Symbiosis extends beyond a single human and a single process.



### 9.1 Internal multi-agent orchestration

- assign specialized roles to subtasks

- merge outputs via consensus

- require review for high-risk domains



See:

- `docs/COLLABORATIVE_INTELLIGENCE.md`



### 9.2 Federated collaboration

- exchange sanitized knowledge, not secrets

- trust-weighted imports

- approval-gated exports (when sensitive)



See:

- `docs/WEB_ACCESS.md`

- `docs/TRUST_MODEL.md`





## 10) Implementation pointers (code map)



Human–AI symbiosis touches UI, governance, and explanation:



- Symbiosis modules:

  - `src/francis/symbiosis/*`

    - augmentation/*

    - cognitive_offloading/*

    - collaboration/*

    - learning_from_human/*



- Governance gates:

  - `src/francis/governance/*`



- Conversation continuity:

  - `src/francis/chat/continuity/*`

  - `data/conversations/*`



- Explanations:

  - `src/francis/explanation/*`

  - `data/artifacts/explanations/*`



- UI:

  - `apps/chat_ui/*`





## 11) Symbiosis quality metrics



Measure whether symbiosis is working:



- time-to-completion per task class

- number of approvals requested vs required

- rate of blocked actions (by gate)

- operator edits per plan (signal of plan quality)

- post-incident findings related to UI clarity

- trust score changes over time

- user satisfaction prompts (optional)



These metrics inform:

- readiness thresholds,

- prompt tuning,

- UI improvements,

- and safer defaults.





## 12) Checklist: ship-ready symbiosis



- [ ] UI shows identity, mode, trust, web/write toggles

- [ ] High-risk actions require approval with clear preview

- [ ] Stop/revoke controls are immediate and reliable

- [ ] Explanations cite evidence and policy checks safely

- [ ] Logs are redacted and append-only

- [ ] Default workflow is plan-first with safe incremental execution

- [ ] Adversarial inputs are treated as untrusted and isolated

- [ ] Federation sharing never includes secrets or regulated payloads





# End of HUMAN_AI_SYMBIOSIS.md



