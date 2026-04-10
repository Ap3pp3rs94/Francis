==============================================================================

FRANCIS — CREATIVE_INTELLIGENCE.md

Creativity as a governed capability: ideation, innovation, art, storytelling

==============================================================================



Purpose

-------

This document defines the Creative Intelligence subsystem in FRANCIS:

   - What “creative” means in a system that must remain correct, safe, and auditable

   - How divergent ideation + convergent validation are orchestrated

   - How creative outputs are evaluated (novelty, usefulness, feasibility, safety)

   - How creative generation interfaces with governance, trust, permissions, and logging

   - How artifacts (stories, designs, prototypes, prompts, code sketches) are stored

   - How the system prevents "creativity" from becoming hallucination, policy drift,

     unsafe suggestions, or IP leakage



Read alongside:

   - docs/POLICIES.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/API_PERMISSIONS.md

   - docs/HUMAN_AI_SYMBIOSIS.md

   - docs/CONVERSATION_CONTINUITY.md

   - docs/EXPLANATION_SYSTEM.md

   - config/models/specialized/creative.yaml

   - config/prompts/creative_ideation.yaml

   - src/francis/creativity/*



Design stance:

   - Creativity is a capability multiplier and a risk multiplier.

   - “New” is not enough; outputs must also be coherent, feasible, and policy-compliant.

   - Creative work must be reversible, reviewable, and provenance-tagged.

   - The system should prefer many cheap hypotheses + fewer validated commitments.



==============================================================================





## 0. Executive summary (what the system guarantees)



FRANCIS treats creativity as **governed exploration**:



- **Divergence**: generate multiple candidate ideas, narratives, metaphors, prototypes.

- **Convergence**: evaluate candidates using feasibility + correctness + policy gates.

- **Traceability**: record decisions and artifacts with provenance (conversation + sources).

- **Safety**: apply content policies and domain restrictions before outputs are delivered or executed.

- **Separation of duties**: creative generation does not directly authorize tool actions.



Creative intelligence is therefore a pipeline: **propose → test → refine → approve → deliver**.





## 1. Definitions and boundaries



### 1.1 Creativity (system definition)

In FRANCIS, *creativity* is the ability to produce outputs that are:

- **Novel** (not trivial rephrases)

- **Useful** (serves a user goal)

- **Coherent** (internally consistent)

- **Feasible** (implementable within constraints)

- **Aligned** (policy compliant, safety aware)



Creativity is not:

- guessing facts,

- inventing continuity,

- violating policy boundaries under the excuse of “fiction”,

- reproducing copyrighted text verbatim.



### 1.2 Creative output types

Common creative outputs include:

- **Ideation**: brainstorms, option sets, tradeoff maps

- **Innovation**: prototype specs, experiment plans, product concepts

- **Artistic**: generative art concepts, style exploration, aesthetic scoring

- **Storytelling**: scenarios, metaphors, narratives, vision articulation

- **Creative planning**: alternative strategies, reframes, “outside-the-box” decompositions



### 1.3 Creativity vs hallucination

A core rule:



> If an output claims to be factual, it must be supported by evidence or explicitly marked as uncertain.



Creative modes may imagine *scenarios* and *fictional examples*, but must label them as such and never “launder” fiction into operational decisions.



### 1.4 The “creative sandbox”

Creative exploration runs in a conceptual sandbox:

- It may generate bold or speculative ideas.

- It may not execute high-impact actions without permissions + trust + approvals.

- It must not generate disallowed content (see policies).





## 2. Architectural overview



### 2.1 Subsystem layout (code map)

Creative Intelligence is implemented under:



- `src/francis/creativity/`

  - `ideation/`

    - `analogical_reasoning.py`

    - `bisociation.py`

    - `combination_explorer.py`

    - `constraint_relaxation.py`

  - `innovation/`

    - `experiment_designer.py`

    - `feasibility_checker.py`

    - `novelty_generator.py`

    - `prototype_builder.py`

  - `artistic/`

    - `aesthetic_evaluator.py`

    - `generative_art.py`

    - `music_composition.py`

    - `style_transfer.py`

  - `storytelling/`

    - `metaphor_generator.py`

    - `narrative_builder.py`

    - `scenario_writer.py`

    - `vision_articulator.py`



These modules are orchestrated by the agent/planning layer and governed by the

trust/policy gates.



### 2.2 Interaction with the rest of the system

Creative intelligence connects to:

- **LLM routing** (choose creative vs reasoning vs code models)

  - `config/models/specialized/creative.yaml`

  - `src/francis/llm/router.py`

- **Governance / policy** (what is permitted)

  - `src/francis/governance/*`

  - `config/policies/*`

- **Conversation continuity** (what to remember, how to summarize)

  - `src/francis/chat/continuity/*`

  - `data/conversations/*`

- **Artifacts** (where outputs go)

  - `data/artifacts/deliverables/*`

  - `data/artifacts/explanations/*`

  - `data/artifacts/runbooks/*` (when creativity produces procedures)



### 2.3 The creative pipeline (canonical)

A typical creative task follows this pipeline:



1) **Intake**

   - goal, constraints, style, risk classification

   - desired format and deliverable type



2) **Divergent generation**

   - multiple candidates (N ≥ 3 by default)

   - include variations on:

     - framing

     - assumptions

     - style

     - level of ambition



3) **Convergent evaluation**

   - feasibility scoring

   - novelty scoring

   - policy compliance checks

   - risk tagging



4) **Refinement**

   - merge the best parts

   - repair gaps / contradictions

   - tighten constraints



5) **Review + governance**

   - if output implies tool actions or irreversible consequences:

     - require approvals per policy

     - enforce trust thresholds



6) **Delivery**

   - produce the final artifact

   - store with provenance + metadata



The system should default to “many candidates → one validated deliverable.”





## 3. Creative modes and when to use them



### 3.1 Divergent ideation (breadth-first)

Use when:

- you need options quickly,

- you’re searching a design space,

- requirements are unclear.



Techniques:

- analogical reasoning (“like X, but for Y”)

- bisociation (combine unrelated domains)

- constraint relaxation (temporarily loosen non-critical constraints)

- combination exploration (feature recombination)



Expected output:

- a ranked list of candidates with short rationales

- explicit assumptions and open questions



### 3.2 Convergent synthesis (depth-first)

Use when:

- you already have options and must choose

- correctness and feasibility matter



Techniques:

- tradeoff mapping

- feasibility checks

- risk review

- policy compliance scan



Expected output:

- one plan/spec with measurable acceptance criteria



### 3.3 Storytelling and scenario modeling

Use when:

- you need to persuade, explain, or align stakeholders

- you need “future narratives” to test strategy



Techniques:

- scenario writing

- narrative arc construction

- metaphor generation

- vision articulation



Expected output:

- story/scenario plus a non-fiction “interpretation layer” explaining what it means operationally



### 3.4 Artistic generation (aesthetic exploration)

Use when:

- you want style exploration or aesthetic scoring

- you want “creative artifacts” that are not purely textual (still described and stored as text specs)



Techniques:

- style transfer descriptors (not execution unless safe)

- aesthetic evaluation scoring rubric

- motif exploration



Expected output:

- a structured design brief (palette/mood/texture/constraints) and evaluation notes





## 4. Creative task specification (recommended interface)



Creative tasks should be machine-checkable and auditable. Recommended fields:



- `task_id`: stable id

- `objective`: what success looks like

- `deliverable_type`: {idea_set, spec, narrative, prototype_plan, creative_brief}

- `constraints`:

  - must-haves

  - must-not-haves

  - budget/time/compute limits

- `style`:

  - tone

  - target audience

  - references (allowed)

- `risk_profile`: {low, medium, high}

- `policy_tags`: {privacy_sensitive, regulated, offensive_security_adjacent, etc.}

- `evaluation`:

  - novelty weight

  - feasibility weight

  - safety weight

- `output_format`: {markdown, json, yaml}



Illustrative (not normative) example:



```yaml

task_id: creative_brief_2026_01_01_001

objective: Draft 5 UI concepts for a trust dashboard that makes approvals visible.

deliverable_type: idea_set

constraints:

  must_haves:

    - shows identity + mode + web access state

    - tool trace inspection

    - exportable decision artifacts

  must_not_haves:

    - exposes secrets

    - implies auto-approval

style:

  tone: pragmatic

  audience: operators + auditors

risk_profile: medium

policy_tags: [privacy_sensitive]

evaluation:

  novelty_weight: 0.35

  feasibility_weight: 0.35

  safety_weight: 0.30

output_format: markdown



