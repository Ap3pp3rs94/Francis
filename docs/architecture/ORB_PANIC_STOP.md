# Orb Panic Stop

The orb panic path is now local first and fail closed.

## Previous Problem

The visible stop control depended too heavily on remote HUD execution. When that fetch path failed, the main operator surface could show a raw transport failure instead of a trustworthy stop result.

## Current Contract

When the orb stop path is triggered, Francis now does this in order:

1. cancel queued orb authority commands locally
2. release local orb authority immediately
3. mark the surface as stopped locally
4. attempt remote control-plane sync separately

Remote sync is now secondary reporting, not the only stop mechanism.

## User-Facing Behavior

- The compact strip and details console show clean stop summaries.
- Raw transport/runtime errors stay in diagnostics.
- If local stop succeeds but remote sync fails, the surface still reports a real stop:
  - local authority dropped
  - remote sync pending

## Failure Modes

- `stopped`: local stop succeeded and remote sync succeeded
- `local_only`: local stop succeeded and remote sync failed
- `degraded`: local stop work did not complete cleanly and diagnostics must be inspected

## Scope

This path applies to:

- strip stop button
- details-console stop button
- orb hold-to-stop gesture

All of them now share the same local-first stop implementation.
