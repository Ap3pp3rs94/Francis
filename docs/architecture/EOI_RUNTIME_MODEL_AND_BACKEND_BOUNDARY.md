# EOI Runtime Model And Future Backend Boundary

This is the concise runtime note for the orb-first Francis build after Sections 1 through 15.

Use this note when future work touches the visible operator runtime, review HUD, or any future backend Codex integration.

## Non-Negotiable Runtime Law

- Francis is an Embodied Operator Intelligence.
- The orb is the visible operator body.
- The orb-first strip is sufficient for basic trust, control, and state.
- Lens/HUD is a secondary review and support surface.
- Backend expansion must extend canonical seams instead of creating a hidden-brain-plus-orb-shell split.

## Canonical Runtime Seams

- Startup law:
  - [startup-surface.js](/D:/francis/electron/startup-surface.js)
  - [main.js](/D:/francis/electron/main.js)
  - orb boots by default; Lens stays explicit
- Body-state seam:
  - [orb-motion.js](/D:/francis/services/hud/app/static/orb/orb-motion.js)
  - [orb-surface-state.js](/D:/francis/services/hud/app/static/orb/orb-surface-state.js)
  - [OrbStateController.ts](/D:/francis/francis-orb/control/OrbStateController.ts)
  - [OrbTransitionController.ts](/D:/francis/francis-orb/control/OrbTransitionController.ts)
- Safety seam:
  - [orb-control-state.js](/D:/francis/electron/orb-control-state.js)
  - [orb-panic.js](/D:/francis/electron/orb-panic.js)
  - [main.js](/D:/francis/electron/main.js)
- Degraded seam:
  - [orb-runtime-health.js](/D:/francis/electron/orb-runtime-health.js)
  - [hud-runtime.js](/D:/francis/electron/hud-runtime.js)
  - [index.html](/D:/francis/services/hud/app/static/index.html)
- Ownership seam:
  - [orb-ownership-state.js](/D:/francis/electron/orb-ownership-state.js)
  - [main.js](/D:/francis/electron/main.js)
- Attention seam:
  - [orb_perception.py](/D:/francis/services/orchestrator/app/orb_perception.py)
  - [orb.py](/D:/francis/services/hud/app/orb.py)
  - [OrbAttentionController.ts](/D:/francis/francis-orb/control/OrbAttentionController.ts)
- Execution seam:
  - [orb-execution.js](/D:/francis/electron/orb-execution.js)
  - [orb-plan.js](/D:/francis/electron/orb-plan.js)
  - [windows-input.js](/D:/francis/electron/windows-input.js)
  - [orb_authority.py](/D:/francis/services/orchestrator/app/orb_authority.py)
- Policy seam:
  - [lens_operator.py](/D:/francis/services/orchestrator/app/lens_operator.py)
  - [orb_authority.py](/D:/francis/services/orchestrator/app/orb_authority.py)
  - [orb.py](/D:/francis/services/hud/app/orb.py)
  - [InterjectionPolicy.ts](/D:/francis/francis-orb/policy/InterjectionPolicy.ts)
- Perception seam:
  - [orb-perception.js](/D:/francis/electron/orb-perception.js)
  - [main.py](/D:/francis/services/hud/app/main.py)
  - [orb_perception.py](/D:/francis/services/orchestrator/app/orb_perception.py)
- Desktop-authority seam:
  - [orb-surface.js](/D:/francis/electron/orb-surface.js)
  - [windows-input.js](/D:/francis/electron/windows-input.js)
  - [foreground-window.js](/D:/francis/electron/foreground-window.js)
  - [main.js](/D:/francis/electron/main.js)
- Receipt seam:
  - [orb_authority.py](/D:/francis/services/orchestrator/app/orb_authority.py)
  - [orb_memory.py](/D:/francis/services/hud/app/orb_memory.py)
  - [execution_journal.py](/D:/francis/services/hud/app/views/execution_journal.py)
- Review/support-role seam:
  - [index.html](/D:/francis/services/hud/app/static/index.html)
  - [dashboard.py](/D:/francis/services/hud/app/views/dashboard.py)
  - [runs.py](/D:/francis/services/hud/app/views/runs.py)

## Review HUD Boundary

What belongs in the orb-first surface:

- current operator posture
- approval-needed truth
- stop and pause
- authority posture
- degraded/disconnected truth
- concise target and execution truth

What belongs in Lens/HUD:

- detailed receipts and replay
- diagnostics
- expanded controls
- deeper review surfaces
- longer inspection paths

The orb must never become a teaser for the panel, and the review HUD must never quietly reclaim startup or default-live primacy.

## Known Limits

- [index.html](/D:/francis/services/hud/app/static/index.html) is still a shared orb/review renderer choke point.
- Windows still imposes real limits for elevated apps, secure desktop, protected surfaces, anti-cheat paths, and exclusive fullscreen.
- UI Automation and accessibility grounding can still be partial or absent on some surfaces.
- The shell still uses one virtual orb window across displays instead of separate per-monitor orb bodies.
- Internal API and bridge names still use `lens` / `HUD` in places for compatibility even though the user-facing surface is now a secondary review HUD.
- Legacy receipts are normalized forward, but producers that do not emit v2 receipt context still have lower replay fidelity.

## Future Backend Francis Codex Boundary

Future backend Codex is allowed to provide:

- deeper planning
- longer-horizon orchestration
- remote or federated capability
- richer mission reasoning
- better evidence and receipt enrichment

Future backend Codex is not allowed to become:

- a separate visible operator identity
- the “real” product while the orb becomes a shell
- a panel-first orchestration center that demotes orb-first runtime truth
- a backend-only source of truth that the orb mirrors late

Explicit anti-patterns to reject:

- hidden brain + orb shell
- panel-first backend orchestration
- backend bypass of safety, policy, ownership, execution, or receipt seams
- backend actuation truth that appears only after action already started

Required integration rule:

- backend Codex may propose, plan, analyze, or orchestrate
- canonical runtime truth must still resolve through the existing seams
- orb-visible posture must update from canonical seams before or as action commitment becomes real
- receipt and policy truth must remain canonical, structured, and reviewable

In practice, future backend work should plug in at these boundaries:

- planning and evidence upstream of the execution seam
- policy/advisory reasoning upstream of the policy seam
- perception enrichment upstream of the perception seam
- receipt enrichment downstream of the receipt seam without replacing it

It must not bypass:

- local-first safety
- degraded-mode containment
- ownership/pass-through governance
- canonical execution-state derivation
- desktop-authority truth

## Verification Lane

Focused renderer and shell checks:

```powershell
node --check electron/main.js
node --check services/hud/app/static/orb/orb-motion.js
node --check services/hud/app/static/orb/orb-surface-state.js
node -e 'const fs=require("fs"); const html=fs.readFileSync("services/hud/app/static/index.html","utf8"); const matches=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)]; matches.forEach((m)=>new Function(m[1])); console.log(`parsed ${matches.length} inline scripts`);'
```

Focused orb/runtime contract lane:

```powershell
node --test electron/startup-surface.test.cjs electron/orb-motion.test.cjs electron/orb-surface-state.test.cjs electron/orb-surface-contract.test.cjs electron/orb-control-state.test.cjs electron/orb-ownership-state.test.cjs electron/orb-runtime-health.test.cjs electron/orb-panic.test.cjs electron/orb-perception.test.cjs electron/orb-plan.test.cjs electron/windows-input.test.cjs electron/orb-surface.test.cjs electron/foreground-window.test.cjs
```

Focused Python review/receipt lane:

```powershell
ruff check services/orchestrator/app/orb_authority.py services/hud/app/orb.py services/hud/app/orb_memory.py services/hud/app/views/execution_journal.py services/hud/app/views/dashboard.py services/hud/app/views/runs.py tests/unit/test_orb_authority.py tests/unit/test_orb_memory.py tests/unit/test_dashboard_view.py tests/unit/test_orb_view.py tests/integration/test_hud_foundation.py
python -m pytest -q tests/unit/test_orb_authority.py tests/unit/test_orb_memory.py tests/unit/test_dashboard_view.py tests/unit/test_orb_view.py tests/integration/test_hud_foundation.py -k "orb_authority or orb_memory or dashboard or get_orb_view or hud_root_supports_standalone_orb_window_mode"
```

## Closure Rule

If future work cannot preserve orb-first truth cleanly, prefer holding Francis in the safer compact/review-routed posture instead of reintroducing panel-era ambiguity.
