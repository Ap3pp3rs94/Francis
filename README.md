# Francis

Francis is a governed operator layer for human work.

It is not a chat wrapper, not a workflow toy, and not a generic autonomous loop. The target is an OS-layer digital twin that can observe, assist, stage, execute, and continue work inside explicit scope, approvals, receipts, and revocation.

The canonical vision and build law live in `ROADMAP.md`. This README is the practical entrypoint.

## What Exists Now

The repository already contains the core service surfaces for:

* orchestrator
* observer
* worker
* gateway
* HUD scaffolding
* voice scaffolding
* shared packages for core logic, brain, policy, presence, Forge, connectors, skills, and LLM integration

The current implementation is broader than a blank scaffold and narrower than the full roadmap. Build from the staged plan, not from feature excitement.

## Build Cadence

Every meaningful Francis change should follow the same cadence:

1. Restate the user-experience objective.
2. Name the affected modules and files.
3. Implement coherent full-file changes.
4. Run quality gates.
5. Return receipts.

Non-negotiables:

* user sovereignty stays explicit
* scope stays explicit
* no hidden control
* no fabricated state
* no unreceipted action
* content never grants authority

## Repository Map

* `services/orchestrator/` - main API surface; includes control, approvals, autonomy, forge, lens, missions, observer, presence, receipts, runs, telemetry, tools, and worker routes
* `services/observer/` - grounded probes, anomaly detection, scoring, and event emission
* `services/worker/` - queued execution, lease handling, backoff, deadletter, and sandbox/resource safety
* `services/gateway/` - gateway and middleware for auth, rate limiting, panic mode, RBAC, and proxy/admin flows
* `services/hud/` - UI scaffolding for dashboard, inbox, incidents, missions, and runs
* `services/voice/` - voice scaffolding
* `packages/` - shared libraries used across the system
* `francis/` - top-level package namespace
* `workspace/` - local-first runtime state, journals, queues, missions, receipts, telemetry, and other live artifacts
* `runtime/` - runtime-only data
* `docs/` - architecture, governance, operations, product, business, and lore
* `policies/`, `schemas/`, `proto/`, `infra/` - contracts, policy, schema, and infrastructure surfaces
* `tests/` - unit, integration, eval, and red-team coverage

## Quickstart

Prerequisites:

* Python 3.10+
* a virtual environment is recommended

Install:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e .[dev]
```

Run tests:

```bash
pytest
```

Or:

```bash
make test
```

Run the orchestrator:

```bash
uvicorn services.orchestrator.app.main:app --reload
```

Run the gateway:

```bash
uvicorn services.gateway.app.main:app --reload --port 8001
```

## Working Model

Francis operates through explicit control modes:

* `Observe` - read, inspect, summarize, and assess without mutation
* `Assist` - propose, draft, and stage with the user still holding execution
* `Pilot` - execute within explicit delegated scope
* `Away` - continue bounded, governed night-shift work

These are legal and product states, not just UX labels.

## Quality Gates

The roadmap expects three gate families on meaningful work:

* code quality
* safety quality
* product quality

In practice, the minimum routine here is:

* run `pytest`
* run `ruff check .` when Ruff is available in the environment
* verify that receipts, scope boundaries, and user-visible behavior still hold

`workspace/` and `runtime/` are intentionally excluded from Ruff because they contain live artifacts rather than source code.

## Where To Start Reading

If you are new to the repo, read in this order:

1. `ROADMAP.md`
2. `VISION.md`
3. `services/orchestrator/app/main.py`
4. `services/orchestrator/app/routes/`
5. `tests/integration/`
6. `docs/governance/`

## Notes

* The orchestrator is the primary operational surface today.
* The roadmap is the source of truth for sequence and doctrine.
* The README is intentionally shorter and more practical than the roadmap.
