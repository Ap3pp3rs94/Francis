# Apprenticeship

## Purpose
Apprenticeship Mode teaches Francis from real user demonstrations without bypassing governance. It converts observed expert behavior into staged, testable capabilities.

## The 5-Step Pipeline
### 1) Demonstrate
- The user performs the workflow in a declared scope.
- Francis records operational telemetry and artifacts with receipts.

### 2) Label
- The user labels intent, constraints, and definition-of-done.
- Francis binds labels to observed steps and evidence.

### 3) Replay
- Francis proposes a replay plan in Assist/Pilot modes.
- User approves execution before mutating steps.

### 4) Generalize
- Francis identifies stable patterns and parameterizes variable inputs.
- Unsafe or brittle steps are flagged for review instead of auto-reuse.

### 5) Skillize
- Francis emits a staged capability pack with tests and docs.
- Result enters Forge staging and requires explicit promotion.

## Teaching Sessions UX
- Session starts with a clear banner: mode, scope, and capture status.
- User sees live step timeline, captured artifacts, and inferred intent labels.
- Before replay, Francis shows a diff-like plan with risk tier and approval requirements.
- Session end includes receipts: `run_id`, artifacts, unresolved questions, and proposed capability draft.

## Guardrails
- Scope contract is mandatory; out-of-scope actions are denied.
- Redaction controls hide secrets/sensitive content from retained artifacts.
- Mutating replay steps require approvals based on policy and risk tier.
- Apprenticeship output is always staged first; no auto-promote behavior.

## Outputs
- Staged capability pack (code/spec manifest).
- Generated tests and validation summary.
- Operator-facing docs and usage notes.
- Receipt bundle linking demonstration evidence to generated artifacts.

## Acceptance Criteria Checklist
- [ ] Demonstration capture is local-first and scope-bound.
- [ ] Intent labels are explicit and user-reviewable.
- [ ] Replay plan is visible before execution.
- [ ] Generalization preserves safety boundaries and approval gates.
- [ ] Skillized output is staged with tests/docs and never auto-promoted.
