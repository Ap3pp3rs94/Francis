# Orb Surface Model

Francis now uses a 3-surface orb shell instead of a default floating mini-app.

## Surface A: Orb Body

- Primary visible identity.
- Persistent, spatial, and compact.
- Conveys motion, targeting, lock, interruption, and actuation state.
- Stays present without occupying a large panel footprint.

## Surface B: Operator Strip

- Default visible HUD attached to the orb body.
- Answers only the live trust questions:
  - what Francis is doing
  - whether Francis can act or only observe
  - whether approval is needed
  - whether stop is available
- Keeps the visible contract compact:
  - state label
  - authority/mode chips
  - target/confidence line
  - stop, pause, and Lens controls

The strip is the new default live surface. It replaces the old chat-first dock posture.

## Surface C: Lens Detail Surface

- Opened intentionally from the strip or orb context actions.
- Holds the verbose material that should not dominate the live surface:
  - receipts
  - runtime-health detail
  - authority and action receipts
  - diagnostics
  - longer interaction and review context
- The live orb window no longer owns an inline console path. In orb-window mode, deeper detail always hands off to Lens instead of expanding in place.

## Supporting Spines

The orb-first shell is now held up by three explicit runtime spines:

- canonical authority posture: whether Francis is observing, armed, live, locally stopped, paused, or disconnected
- canonical runtime-health posture: `nominal`, `degraded`, `disconnected`, and `recovering`
- canonical ownership posture: `pass_through`, `interactable_orb`, `interactable_lens`, and `restricted`

The strip reads those spines directly. It should not guess authority, health, or ownership from renderer-local heuristics.

## Product Consequence

Francis should now read as:

- orb first
- compact by default
- interruptible
- operator-grade

Francis should no longer read as:

- floating chat widget
- continuity wall
- debug shell
- always-open panel
- hidden mini console behind the orb
