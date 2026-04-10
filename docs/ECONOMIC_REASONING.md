==============================================================================

FRANCIS — ECONOMIC_REASONING.md

Cost, value, incentives, risk-adjusted utility, and resource allocation

==============================================================================



Purpose

-------

This document defines the Economic Reasoning subsystem in FRANCIS:

   - how FRANCIS estimates cost, value, and opportunity cost,

   - how it selects actions under constraints and uncertainty,

   - how it allocates budgets (money, time, compute, risk),

   - and how governance + trust gates restrict economic actions.



Economic reasoning is not “profit-maximization at all costs”.

In FRANCIS it is a disciplined method to:

   - maximize utility,

   - minimize waste,

   - respect hard constraints (policy/safety/regulatory),

   - and make decisions auditable and explainable.



Read alongside:

   - docs/TRUST_MODEL.md

   - docs/GOVERNANCE.md

   - docs/POLICIES.md

   - docs/API_PERMISSIONS.md

   - docs/EXPLANATION_SYSTEM.md

   - docs/THREAT_MODEL.md

   - docs/CONVERSATION_CONTINUITY.md

   - config/policies/action_readiness.yaml

   - config/policies/api_permissions.yaml

   - config/policies/data_governance.yaml

   - config/policies/privacy.yaml

   - src/francis/economy/*

   - src/francis/trust/*

   - schemas/proposals.schema.json

   - schemas/action_request.schema.json

   - schemas/action_result.schema.json



Design stance

------------

   - Economics is **decision support**, not authority.

   - Policies, approvals, and safety constraints override utility.

   - Uncertainty is explicit: decisions carry confidence and sensitivity.

   - Avoid false precision: prefer ranges and scenario analysis.

   - Always preserve an audit trail (inputs → model → decision).



==============================================================================





## 0) Economic reasoning contract (what FRANCIS guarantees)



When FRANCIS uses economic reasoning, it must be able to produce:



1) **Objective(s)**

   - what is being optimized (utility, cost, latency, risk, success probability).



2) **Constraints**

   - policies, safety rules, budgets, deadlines, approvals, scope limits.



3) **Assumptions**

   - stated explicitly (prices, rates, success probabilities, demand).



4) **Alternatives**

   - at least 2 plausible options when the decision is non-trivial.



5) **Inputs and provenance**

   - where numbers came from (tool output, config, user input, defaults).



6) **Outputs**

   - recommended action with cost/value ranges, confidence, and triggers to re-evaluate.



If any of the above cannot be satisfied:

- degrade to conservative suggestions,

- ask for missing inputs,

- or abstain from quantitative recommendations.





## 1) Definitions



### 1.1 Cost

**Cost** includes:

- direct financial cost (cash)

- compute cost (GPU/CPU time, tokens, storage)

- labor cost (human minutes/hours)

- risk cost (expected loss)

- latency cost (time-to-result)

- operational cost (complexity, maintenance)



### 1.2 Value

**Value** includes:

- expected benefit (revenue, savings, time saved)

- risk reduction (avoided incidents, compliance wins)

- capability improvement (new domain knowledge, automation leverage)

- strategic value (optionality, future flexibility)



### 1.3 Opportunity cost

**Opportunity cost** is the value of the best alternative foregone.

In FRANCIS:

- opportunity cost is tracked across scarce resources:

  - time, compute, attention, risk capacity, budget.



### 1.4 Utility

**Utility** is a common internal score combining:

- value gained

- costs paid

- risk-adjusted penalties

- preference weights



Utility is not necessarily money.



### 1.5 Risk-adjusted value (Expected Value)

The core primitive is:

- `EV = Σ (probability(outcome_i) * value(outcome_i)) - expected_costs`



FRANCIS must represent probabilities as uncertain ranges when evidence is weak.



### 1.6 Regret

**Regret** is the penalty for choosing poorly relative to the best choice in hindsight.

Regret minimization is useful under uncertainty:

- choose actions that are robust to model error.



### 1.7 Budget

A **budget** is a constraint over:

- money

- time

- compute

- risk

- approvals latency



Budgets exist at:

- per-task

- per-domain

- per-environment

- per-identity (delegation/scopes)





## 2) Economic reasoning in the overall decision pipeline



Economic reasoning is never the first gate.



A decision passes in this order (conceptual):

1) **Policy constraints** (hard rules)

2) **Permissions** (scopes/delegations)

3) **Action readiness** (trust/approvals)

4) **Safety filters** (harmful actions, regulated constraints)

5) **Economic reasoning** (optimize within allowed actions)

6) **Execution + audit**



If any earlier gate fails:

- economic reasoning cannot override it.





## 3) Where economic reasoning lives in the codebase



Primary module:

- `src/francis/economy/*`



Submodules (as in your tree):

- `src/francis/economy/budgeting/*`

  - `budget_allocator.py`

  - `financial_planning.py`

  - `revenue_maximizer.py`

  - `spend_optimizer.py`



- `src/francis/economy/cost_modeling/*`

  - `action_cost_estimator.py`

  - `opportunity_cost.py`

  - `resource_pricer.py`

  - `total_cost_of_ownership.py`



- `src/francis/economy/markets/*`

  - `capability_marketplace.py`

  - `compute_futures.py`

  - `data_exchange.py`

  - `pricing_engine.py`



- `src/francis/economy/value_optimization/*`

  - `pareto_optimizer.py`

  - `roi_calculator.py`

  - `utility_maximizer.py`

  - `value_of_information.py`



Supporting systems:

- trust: `src/francis/trust/*`

- governance: `src/francis/governance/*`

- explanation: `src/francis/explanation/*`

- telemetry/audit: `src/francis/telemetry/*`





## 4) Data model: how economic inputs are represented



### 4.1 Economic context object (recommended)

Every economic evaluation should have a structured context:



- identity + environment

- budgets

- constraints (policy-derived)

- resource prices

- risk parameters

- success probability priors

- time horizon and discounting



Illustrative shape:

```yaml

econ_context:

  context_id: "econ_2026_01_01T120000Z_abc123"

  identity:

    actor_id: "user:local"

    delegation_id: null

  environment:

    mode: "dev"              # dev | production | regulated | airgapped | etc.

    writes_enabled: false

    web_access_enabled: true



  horizon:

    timeframe_days: 30

    discount_rate_annual: 0.15



  budgets:

    money_usd: 5000

    human_hours: 12

    compute_gpu_hours: 4

    risk_budget: "low"       # low | medium | high



  resource_prices:

    human_hour_usd: 75

    cpu_hour_usd: 0.05

    gpu_hour_usd: 2.50

    storage_gb_month_usd: 0.10



  risk_params:

    incident_cost_usd_range: [5000, 50000]

    compliance_penalty_usd_range: [0, 250000]

    risk_aversion: 1.6



  uncertainty:

    use_ranges: true

    confidence_floor: 0.25



