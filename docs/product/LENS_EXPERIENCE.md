# Lens Experience

## Purpose
Define the product contract for Francis Lens as the 4th-wall overlay control surface.

## Overlay UI Contract
- Lens is a contextual HUD over active work surfaces, not a detached status page.
- Core panels: Missions, Incidents, Approvals, Autonomy Queue, Forge, and Receipts.
- Docking/undocking and command palette summon are first-class interactions.
- Lens must prioritize intent, blockers, and next actions over raw system vitals.

## Pilot Mode Indicator Requirements
- Pilot Mode state is always visible while delegated control is active.
- Indicator shows scope boundaries and current operator activity.
- Panic/Stop control is one action away from any Pilot view.
- Indicator history is receipted for audit replay.

## Command Palette and Action Chips
- Command palette exposes high-value actions with scope/risk previews.
- Action chips appear near relevant failures (build/test/terminal/diagnostics).
- Every mutating action path displays approval requirements before execution.
- Chips should prefer staged plans and verification-first workflows.

## Telemetry Visibility and Privacy
- Telemetry status is always visible when streams are active.
- Telemetry is opt-in, scope-bound, and redacted by policy.
- Lens must clearly show what stream is active and why.

## Acceptance Criteria Checklist
- [ ] Lens surfaces intent/state/blockers, not only health metrics.
- [ ] Pilot indicator is always visible during delegated control.
- [ ] Panic/Stop is immediately accessible and effective.
- [ ] Action chips provide contextual, approval-aware actions.
- [ ] Active telemetry and scope boundaries are visible to the user.
