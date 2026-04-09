# Module Boundaries

This document is the practical code-navigation map for Francis.

Use it to answer:

* which directories are the real runtime spine
* which directories are compatibility wrappers
* which directories are adjacent or secondary
* where new work should land by default

This is not a replacement for the higher-level architecture docs. It is the contributor-facing answer to: "where do I actually change the repo without drifting into the wrong layer?"

## The Short Rule

If you are changing real Francis behavior, start in:

* `services/`
* `packages/`
* `electron/`
* `build/sign/`
* `tests/`

Do **not** start in:

* `apps/api/`
* `francis/`
* `francis-orb/`

unless you are intentionally maintaining compatibility, legacy routes, or an adjacent prototype surface.

## Primary Runtime Spine

These directories define the current product.

### `services/`

This is the primary Python runtime surface.

* [`services/orchestrator/`](../../services/orchestrator/) is the system center of gravity.
  It owns control, approvals, missions, receipts, autonomy coordination, runtime hygiene, Lens-facing routes, and most cross-system state transitions.
* [`services/worker/`](../../services/worker/) owns queued execution, leases, retries, backoff, deadletters, and bounded job execution.
* [`services/observer/`](../../services/observer/) owns probes, anomaly detection, baseline handling, scoring, and incident emission.
* [`services/gateway/`](../../services/gateway/) owns request IDs, auth, panic mode, actor context, rate limiting, and proxy/admin edges.
* [`services/hud/`](../../services/hud/) owns the Lens/HUD contract, server-shaped view models, Orb-facing bridges, and operator surfaces.
* [`services/voice/`](../../services/voice/) is the current voice scaffold.

Default rule:

* API behavior changes belong in `services/*/app/**`
* system coordination changes usually belong in `services/orchestrator/app/**`
* queue and execution behavior belongs in `services/worker/app/**`
* anomaly and incident behavior belongs in `services/observer/app/**`

### `packages/`

These are the shared internal libraries that the services are supposed to build on.

* [`packages/francis_core/`](../../packages/francis_core/) defines the current shared substrate:
  config, clocks, telemetry helpers, journaling, and workspace IO.
* [`packages/francis_brain/`](../../packages/francis_brain/) owns ledger, memory, recall, retrieval, and reflection helpers.
* [`packages/francis_policy/`](../../packages/francis_policy/) owns approvals, RBAC, panic mode, risk tiers, and policy evaluation.
* [`packages/francis_presence/`](../../packages/francis_presence/) owns presence, tone, narrator, rituals, orb/presence state, and notifications.
* [`packages/francis_forge/`](../../packages/francis_forge/) owns capability-generation and promotion support.
* [`packages/francis_skills/`](../../packages/francis_skills/) owns skill contracts, execution, registry, and toolbelt utilities.
* [`packages/francis_connectors/`](../../packages/francis_connectors/) owns connector abstractions and connector library data.
* [`packages/francis_llm/`](../../packages/francis_llm/) owns model routing and eval harness surfaces.

Default rule:

* shared logic belongs in `packages/*`
* service-local orchestration belongs in `services/*`

Do not push shared behavior down into service folders if multiple services need it.

### `electron/`

This is the shipping Windows overlay shell.

It is not just a launcher. It owns:

* overlay and Orb windows
* lifecycle/session/update state
* authority posture
* runtime bootstrap and recovery
* Windows integration points
* packaged distribution trust posture

If the change affects the shipped desktop shell, installer behavior, retained shell state, signing posture, first-run/update posture, or Orb window behavior, start in [`electron/`](../../electron/).

### `build/sign/`

This is part of the primary release spine.

[`build/sign/windows-sign.cjs`](../../build/sign/windows-sign.cjs) and its config/tests are the repo-owned public-signing path. Changes to Windows public-signing behavior belong here, not in ad hoc shell wrappers.

### `tests/`

This is part of the primary product surface, not an afterthought.

The repo already treats:

* `tests/unit/`
* `tests/integration/`
* `tests/redteam/`
* `tests/evals/`

as core release evidence. Behavior changes are not complete until the corresponding test surface is updated.

## Compatibility / Transitional Surfaces

These directories are real, but they are not the preferred place for new product logic.

### `apps/api/`

This is a thin compatibility façade.

The clearest sign is [`apps/api/main.py`](../../apps/api/main.py), which simply re-exports the orchestrator app. The route files under [`apps/api/routes/`](../../apps/api/routes/) represent an older, slimmer API layer that still exists for continuity, but they are not the main system center anymore.

Default rule:

* do not start new runtime work in `apps/api/`
* only edit it when preserving compatibility or updating a legacy façade intentionally

### `francis/`

This is a legacy root package façade beside the real package implementations in `packages/`.

It contains overlapping implementations such as:

* `francis/core/workspace_fs.py`
* `francis/brain/ledger.py`
* `francis/presence/state.py`

The current primary implementations live under:

* [`packages/francis_core/`](../../packages/francis_core/)
* [`packages/francis_brain/`](../../packages/francis_brain/)
* [`packages/francis_presence/`](../../packages/francis_presence/)

Default rule:

* new shared logic belongs in `packages/*`
* only touch `francis/*` when maintaining import compatibility or explicitly retiring the façade

## Secondary / Adjacent Surfaces

These directories matter, but they are not the main runtime spine.

### `francis-orb/`

This is an adjacent Orb engine package, not the shipping shell.

It is a standalone TypeScript / Three.js surface for Orb rendering and control experiments. It can inform the product, but the currently shipped overlay shell lives in [`electron/`](../../electron/), not here.

Default rule:

* do not start shell or packaging work in `francis-orb/`
* edit it only when intentionally advancing the standalone Orb engine package

### `scripts/`

This is operator tooling and release glue.

These scripts matter for developer workflow, release lanes, and build ergonomics, but most domain behavior should still live in `services/`, `packages/`, or `electron/`.

Default rule:

* workflow orchestration belongs in `scripts/`
* product behavior should not be invented here if it has a real runtime home

### `docs/`

This is doctrine, architecture, governance, product, lore, and operations truth.

Documentation is important, but docs are downstream of the runtime surfaces above. Change docs when the product shape changes or when repo truth is unclear.

### `policies/`, `schemas/`, `proto/`, `infra/`

These are support surfaces:

* `policies/` for policy assets
* `schemas/` and `proto/` for contracts
* `infra/` for infrastructure or secret-management context

They are important, but they are not where the bulk of runtime behavior currently lives.

## File Placement Rules

Use these defaults when deciding where a change belongs.

### If you are changing API behavior

Start in:

* `services/orchestrator/app/routes/`
* `services/gateway/app/routes/`
* `services/hud/app/`

Do not start in:

* `apps/api/routes/`

unless the change is specifically about the compatibility layer.

### If you are changing workspace-backed state or journaling

Start in:

* `packages/francis_core/francis_core/`
* `services/orchestrator/app/`
* `services/worker/app/`

Treat [`packages/francis_core/francis_core/workspace_fs.py`](../../packages/francis_core/francis_core/workspace_fs.py) as the current shared workspace substrate.

### If you are changing mission, queue, incident, inbox, telemetry, or autonomy behavior

Start in:

* `services/orchestrator/app/`
* `services/worker/app/`
* `services/observer/app/`

These are primary runtime concerns, not wrapper-layer concerns.

### If you are changing the shipping desktop experience

Start in:

* `electron/`

Only touch `francis-orb/` if the standalone Orb engine package itself is the target.

### If you are changing signing, packaging, or Windows release trust

Start in:

* `electron/`
* `build/sign/`
* `scripts/`

The public-signing truth is now repo-owned and should stay explicit there.

## Practical Contributor Guidance

If you are new to the repo, read in this order:

1. [`README.md`](../../README.md)
2. [`AGENTS.md`](../../AGENTS.md)
3. [`docs/operations/COMPLETION_LEDGER.md`](../operations/COMPLETION_LEDGER.md)
4. [`services/orchestrator/app/main.py`](../../services/orchestrator/app/main.py)
5. [`services/worker/app/main.py`](../../services/worker/app/main.py)
6. [`services/observer/app/emitter.py`](../../services/observer/app/emitter.py)
7. [`services/hud/app/main.py`](../../services/hud/app/main.py)
8. [`electron/main.js`](../../electron/main.js)

If you are deciding whether a directory is "real" or "transitional", use this test:

* if it owns current runtime behavior, it is primary
* if it mainly forwards, mirrors, or preserves old import paths, it is transitional
* if it is useful but not on the current shipping path, it is adjacent

## Current Classification Summary

### Primary

* `services/`
* `packages/`
* `electron/`
* `build/sign/`
* `tests/`

### Compatibility / Transitional

* `apps/api/`
* `francis/`

### Secondary / Adjacent

* `francis-orb/`
* `scripts/`
* `docs/`
* `policies/`
* `schemas/`
* `proto/`
* `infra/`

When in doubt, follow the primary spine and only touch the compatibility layers deliberately.
