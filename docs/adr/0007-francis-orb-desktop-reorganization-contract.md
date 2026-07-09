# ADR 0007: Francis Orb Desktop Reorganization Contract

Date: 2026-07-09

Status: Proposed as a blocking contract before real desktop reorganization

## Context

Francis is in Phase 2. The current active workstream is Orb embodiment / Stage 6
Lens runtime completion, while `P1_INTERFACE` and `P7_EXECUTION` both remain
partial.

The roadmap defines the Orb as Francis's embodied interface object and says it
becomes the visible operator cursor during Pilot or approved execution. The
current implementation already has a separate Orb virtual pointer posture that
does not take the user's OS cursor. It also has a default-gated desktop bridge
and receipt-backed Orb operator paths.

Desktop reorganization is the first discussed Orb capability class where a
normal execution receipt is not enough. A receipt can prove that Francis moved a
window, dragged an icon, or applied a layout step. It does not automatically
prove what was displaced, how to restore it, or whether a batch of moves matched
the operator-approved plan.

For this capability class, "preview/undo where practical" is too weak.
Reversibility is an entry requirement before real desktop reorganization is
allowed.

## Decision

Francis must not implement real desktop reorganization as raw coordinate drag
authority.

Before Francis can reorganize a desktop, move windows, drag files or icons, snap
applications, or arrange a workspace through the Orb, it must have all of these
contract pieces:

1. Lens semantic target mapping.
2. Plan-level approval.
3. Pre-state and reversal evidence.
4. Receipts proving execution matched the approved plan.

The Orb may remain the visible separate pointer for intent and action legibility.
The Orb does not own authority. It requests governed action through the Francis
substrate and desktop action path.

## Lens Semantic Target Requirement

Coordinate-only desktop action is not sufficient for reorganization.

Francis must know what the target is before asking for approval:

- window
- application
- file icon
- folder icon
- shell surface
- control
- forbidden or unknown target

The target should be derived from a semantic map such as UI Automation, shell
metadata, window metadata, or another governed Lens evidence source. Pixels and
screen coordinates can support pointing, but they are not enough to justify
action approval by themselves.

An approval that says "drag at `(847, 203)`" is not an acceptable safety
contract for desktop reorganization. The approval must bind to bounded semantic
targets and intended state changes, not only to coordinates.

## Plan-Level Approval Requirement

"Arrange my desktop" is a batch action, not one click.

Francis must propose an arrangement plan before executing a batch. The plan must
summarize the intended changes at a level the operator can review, such as:

- move this window from one rectangle to another
- place these files in this group
- align these icons into this region
- snap this application to this side
- leave these surfaces untouched

The approval must authorize the plan, not generic drag authority. Executing
forty drags under one broad grant is not acceptable unless those drags are
bounded as steps inside an approved plan.

The trust ladder's `propose_plan` mode is the natural gate for this capability
class. Desktop reorganization should not skip from observe/read/request into
supervised or approved action without a plan.

## Reversibility Requirement

Desktop reorganization must capture enough pre-state to support review and
reversal before performing real moves.

Capturable and reversible are different claims:

- `capturable` means Francis can observe and record bounded prior state.
- `reversible` means Francis can use that evidence to restore the prior state,
  or can truthfully prove a bounded undo path exists.

Captured state must not imply reversible state. A window position may be both
capturable and reversible. A closed window, an app that repositioned itself, or
a file moved into an auto-sorted folder may be capturable without being
reversible from the captured evidence.

The required evidence depends on the target class, but the contract must include
one of these patterns before action:

- `pre_state`: bounded before-state for the target and relevant neighbors
- `reversal_hint`: bounded instructions or target state needed to restore
- `snapshot_before_batch`: bounded arrangement snapshot for a multi-step plan
- explicit `irreversible_or_not_restorable` denial when state cannot be captured
  safely or cannot be restored from the captured evidence

For desktop reorganization, reversal evidence is not optional decoration. If
Francis cannot capture a safe before-state and prove a bounded reversal path, it
must deny the real reorganization action or fall back to a non-mutating preview.

A future policy may define rare explicitly approved irreversible actions, but no
such policy exists in this contract. Until it exists, captured-but-not-reversible
desktop reorganization fails closed.

## Receipt Requirements

Receipts for desktop reorganization must prove more than "a drag happened."

They must include bounded evidence for:

- approved plan id
- plan step id or batch step index
- semantic target id or bounded target summary
- pre-state evidence id or bounded pre-state summary
- `capturable` truth
- `reversible` truth
- reversal limitation summary when reversible is false
- intended post-state
- observed post-state when available
- reversal hint or reversal evidence id
- whether the step matched the approved plan
- whether the step was skipped, denied, interrupted, reverted, or partially
  confirmed

Receipts must not persist raw screenshots, raw OCR, raw file contents, secret
values, broad filesystem paths, or unbounded desktop metadata by default.

## Approval Requirements

Approval scope for desktop reorganization must bind to:

- actor
- capability
- approved plan id
- semantic target set
- maximum step count
- risk ceiling
- resource and runtime budget
- cancellation/deadline context
- reversal evidence requirement
- reversibility requirement

A single broad grant for arbitrary drag, click, type, or shell rearrangement is
not acceptable. Single-action approval remains possible for small operations,
but batch reorganization needs plan-level approval and receipt chaining.

## Cancellation And Stop Requirements

The Orb remains the visible stop surface, but stop semantics must be truthful.

Desktop reorganization can leave partial state after interruption. Receipts and
status records must distinguish:

- not started
- step denied
- step skipped
- step completed
- batch interrupted before step
- batch interrupted after step
- reversal attempted
- reversal completed
- reversal failed or unavailable

Francis must not claim full undo, recovery, or handback unless the state was
actually restored or the final state was observed and receipted.

## Non-Goals

This ADR does not implement:

- real desktop reorganization
- real drag authority
- real file/icon/window movement
- new API routes
- new adapter implementation
- UI Automation mapping
- snapshot persistence
- undo execution
- screenshot capture
- OCR
- shell execution
- subprocess execution
- network access
- GPU execution
- daemon authority
- OS-level input preemption
- broad filesystem authority
- new memory persistence
- model training

## Future Implementation Gates

Before implementing real desktop reorganization, Francis must add and validate:

- Lens semantic target mapping for the target classes in scope
- a bounded arrangement-plan contract
- plan-level approval consumption
- pre-state or reversal evidence capture
- denial when state is captured but not reversible from the captured evidence
- receipt chaining from plan to step to final status
- denial when reversal evidence is missing
- default-deny handling for unknown, forbidden, or ambiguous targets
- bounded cancellation and partial-completion truth
- explicit tests proving no user OS cursor takeover

The first safe implementation slice should be non-mutating: preview or
highlight-only arrangement guidance using the separate Orb pointer.

## Consequences

This keeps the Orb pointer direction intact while preventing desktop
reorganization from becoming generic coordinate automation.

The hard order is:

1. Lens semantics.
2. Plan-level approval.
3. Reversibility evidence.
4. Real click/drag/arrange execution.

Until those contracts exist, Francis may point, preview, and explain, but it
must not claim it can safely reorganize the desktop.
