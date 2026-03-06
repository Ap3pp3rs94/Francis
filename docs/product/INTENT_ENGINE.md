# Intent Engine

## Purpose
The Intent Engine maintains the live strategic model that keeps execution aligned with user goals. It complements missions by tracking global direction, constraints, and completion criteria.

## Live Intent Model Fields
- `objective`: the primary target outcome.
- `constraints`: hard boundaries (scope, policy, budget, deadlines, standards).
- `stage`: current phase (discovery, build, validate, deploy, stabilize).
- `definition_of_done`: explicit completion criteria with verification requirements.
- `risks`: active known risks, assumptions, and mitigation status.

## Relationship to Missions
- Missions are concrete execution units with queued work and receipts.
- Intent is the global contract that prioritizes and validates mission relevance.
- Mission plans should reference intent fields so drift is visible early.

## How It Drives Suggestions and Takeover Plans
- Suggestions are ranked by intent fit, risk, and expected leverage.
- Pilot takeover plans are generated with intent constraints and DoD gates up front.
- Away-mode actions are selected by intent urgency plus governance allowability.
- Lens surfaces intent deltas, blockers, and recommended next actions.

## Acceptance Criteria Checklist
- [ ] Intent model exists as explicit structured state.
- [ ] Every major recommendation references intent alignment.
- [ ] Takeover plans include constraints and DoD checks before execution.
- [ ] Mission-intent conflicts are surfaced before mutating actions.
- [ ] Intent updates leave receipts and change history.
