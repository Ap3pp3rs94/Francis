# Digital Twin Contract

## Purpose
The Digital Twin Contract is the persistent operator profile that defines how Francis should act as the user's counterpart. It encodes conventions, risk posture, and quality preferences so behavior is stable and auditable across sessions.

## Persistent Style
- Branching style (branch-first, naming conventions, merge strategy).
- Commit and review discipline (message format, PR hygiene, changelog expectations).
- Testing discipline (required checks before claim/promotion).
- Minimal-diff preference and rollback expectations.

## Risk Posture
- Defines which actions require approval by default.
- Specifies stricter gates for production-affecting or high-risk operations.
- Binds mode-specific authority (Observe/Assist/Pilot/Away) to allowed action classes.

## Taste Preferences
- Clarity over cleverness in code and communication.
- Explicit plans before mutation where feasible.
- Receipts over claims for all meaningful actions.
- Consistent formatting, naming, and documentation standards.

## Customization Model (Conceptual)
- User can tune contract fields by repository, project, or mission.
- Contract versions are saved with timestamped change history.
- Runtime decisions should cite the contract rule that influenced behavior.
- Temporary overrides require explicit session-level acknowledgement.

## Acceptance Criteria Checklist
- [ ] Contract fields are explicit and versionable.
- [ ] Operational decisions can reference contract rules in receipts.
- [ ] Approval thresholds reflect declared risk posture.
- [ ] Style/taste preferences remain configurable without code redeploy.
- [ ] Overrides are visible, bounded, and auditable.
