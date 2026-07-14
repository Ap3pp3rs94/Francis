# Francis

[![CI](https://github.com/Ap3pp3rs94/Francis/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Ap3pp3rs94/Francis/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue)
![Build Posture](https://img.shields.io/badge/build-ledger--grounded-orange)
![Local First](https://img.shields.io/badge/posture-local--first-brightgreen)
![Governed](https://img.shields.io/badge/actions-policy--guarded-2f6f9f)

Francis is a local-first AI operator layer for a personal computing environment:
a governed runtime that turns intent into plans, approvals, bounded execution,
receipts, memory, and observable desktop presence. It is being built toward an
OS-layer Digital Twin Operator, with the current repository strongest in
governance, observability, mission continuity, capability lifecycle readbacks,
Lens/orb surfaces, and receipt-backed dry-run operator input.

Francis is not a chatbot wrapper, generic agent loop, model demo, or dashboard
with tools attached. The project is about separating cognition, policy,
identity, execution, observability, and memory so an AI system can eventually do
real work without hiding authority or faking progress.

New here? Start with [docs/START_HERE.md](docs/START_HERE.md), then read the
ledger-backed current state in
[docs/operations/COMPLETION_LEDGER.md](docs/operations/COMPLETION_LEDGER.md).

## Why Francis Exists

Most AI products still behave like bounded conversation systems. They answer
questions, generate text, call tools, or write code inside one session. That is
useful, but it leaves the human carrying the harder work: preserving context,
sequencing actions, checking authority, tracking state, recovering from failures,
and proving what actually happened.

Francis is attempting a different category: operating software for governed AI
work. The goal is a persistent local operator that can understand work context,
carry missions across sessions, stage exact actions, request approval, execute
through bounded channels, preserve receipts, and return continuity to the user.

The core bet is simple: useful autonomy requires governance before power and
observability before scale.

## Why Francis Is Different

| Common AI assistant pattern | Francis direction |
| --- | --- |
| Conversation as the product | Persistent operator layer across work context |
| Single answer or short task loop | Long-running missions with continuity and recovery |
| Model output treated as action intent | Proposal is not execution; actions cross gates |
| Tool calls with weak after-the-fact trace | Receipt-first execution and denial records |
| Mostly stateless interaction | Memory and continuity as governed subsystems |
| Cloud-first assumptions | Local-first runtime posture with external paths gated |
| Text generation as the main output | Plans, approvals, artifacts, traces, and bounded operations |
| Assistant metaphor | Operator metaphor: visible, subordinate, auditable, revocable |

The difference is not that Francis has more tools. The difference is the runtime
law around tool use.

## Current State

Francis is in the Phase 2 / ORB Build Manifest posture: a partial local operator
runtime with a stronger governed control spine than finished product surface.
The completion ledger is the source of shipped truth; this README is a public
orientation layer.

| Implemented or materially real | In progress and partial | Future vision |
| --- | --- | --- |
| FastAPI runtime routes and Vite/React operator UI surfaces | Complete visible `plan -> gate -> execute -> trace -> memory` loop | Fully resident desktop-native operator |
| Governance, approval, policy, and audit expectations | ORB console that makes plane, gate, and recovery state obvious | Mature local autonomy under human oversight |
| Mission continuity, recovery, and deadletter readbacks | Live Orb-driven desktop control and HUD feedback | Simulation-backed high-risk action review |
| Forge proposal, review, promotion-readiness, and capability catalog readbacks | Memory retrieval/write UX and durable learning flow | Federated, sanitized knowledge sharing |
| Observability, traces, receipts, and ledger-backed posture reporting | ChatGPT/Claude/Codex/local-model collaboration reliability | Managed-copy platform and broader capability economy |
| Lens/orb overlay and status readbacks, command-palette monitoring, passive voice controls | Operator-approved tool dispatch without impersonation | Desktop presence that can act, stop, and hand back cleanly |
| Orb operator dry-run intent receipts for move/click/type proposals | Stage 6 Lens and Stage 17 Capability Economy closure | Product-grade execution across trusted local surfaces |
| Francis1 self-model, intelligence-seat, usage, and draft-dispatch readbacks | Full local `.\scripts\check.ps1`, CI, and browser proof for every broad release claim | End-state OS-layer Digital Twin Operator |

What this does not mean:

- Francis is not a finished autonomous operator.
- The Orb does not yet provide fully proven live desktop control.
- Dry-run receipts are not live mouse or keyboard input.
- Proposal, review, or catalog evidence is not automatic capability promotion.
- Collaboration with Codex, Claude, and local models does not make those systems
  the source of authority.

## Architecture

Francis is organized around ORB planes: bounded responsibility surfaces that
separate interface, cognition, governance, identity, execution, observability,
memory, evidence, simulation, and federation.

![Francis governed runtime loop](docs/assets/francis-runtime-loop.svg)

```text
P1_INTERFACE -> P4_COGNITION -> P3_GOVERNANCE -> P2_IDENTITY
  -> P7_EXECUTION -> P9_OBSERVABILITY -> P8_MEMORY -> P1_INTERFACE
```

The canonical rule is: proposal is not permission. Model output can propose work,
but side effects must cross governance, identity, execution, and receipt
boundaries.

| Subsystem | Role in Francis | Primary locations |
| --- | --- | --- |
| ORB substrate | Plane model, runtime order, build gates, transition law | [docs/PLANES.md](docs/PLANES.md), [meta/plane_map.yaml](meta/plane_map.yaml), [docs/canonical/BUILD_MANIFEST.md](docs/canonical/BUILD_MANIFEST.md) |
| Interface and HUD | Operator UI, ORB surfaces, mission readbacks, settings, collaboration views | [apps/chat_ui/](apps/chat_ui/), [src/francis/api/](src/francis/api/) |
| Governance and identity | Policy checks, approvals, scopes, permission boundaries, trust decisions | [src/francis/governance/](src/francis/governance/), [docs/GOVERNANCE.md](docs/GOVERNANCE.md), [docs/TRUST_MODEL.md](docs/TRUST_MODEL.md) |
| Missions and cognition | Planning, continuity, mission state, recovery, handoff context | [src/francis/missions/](src/francis/missions/), [src/francis/agent/](src/francis/agent/) |
| Execution | Supervised execution, input-actuator contracts, dry-run/live gates | [src/francis/input_actuator/](src/francis/input_actuator/), [src/francis/agent/supervised_exec.py](src/francis/agent/supervised_exec.py) |
| Observability and receipts | Audit records, traces, receipts, progress evidence, operational truth | [docs/operations/COMPLETION_LEDGER.md](docs/operations/COMPLETION_LEDGER.md), [src/francis/telemetry/](src/francis/telemetry/) |
| Memory | Continuity, bounded memory contracts, retrieval/write behavior under governance | [docs/MEMORY.md](docs/MEMORY.md), [src/francis/memory/](src/francis/memory/) |
| Forge and capabilities | Proposal artifacts, review receipts, promotion readiness, plugin/capability catalog | [docs/PLUGINS.md](docs/PLUGINS.md), [plugins/](plugins/), [src/francis/economy/](src/francis/economy/) |
| Lens and Orb | Visible operator presence, overlay/readback surfaces, desktop-operation path | [docs/operations/ORB_VISUAL_LOCK.md](docs/operations/ORB_VISUAL_LOCK.md), [docs/architecture/FRANCIS_INPUT_ACTUATOR.md](docs/architecture/FRANCIS_INPUT_ACTUATOR.md) |
| Developer bridge | MCP bridge, collaboration relay, Francis1 self-model, Codex/Claude/local model lanes | [docs/architecture/FRANCIS_MCP_GATEWAY.md](docs/architecture/FRANCIS_MCP_GATEWAY.md), [docs/architecture/FRANCIS1_INTELLIGENCE_ORCHESTRATION_ROADMAP.md](docs/architecture/FRANCIS1_INTELLIGENCE_ORCHESTRATION_ROADMAP.md) |

For the broader design, read
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md),
[docs/canonical/ROADMAP.md](docs/canonical/ROADMAP.md), and
[docs/canonical/VISION.md](docs/canonical/VISION.md).

## Engineering Principles

Francis work is judged against these constraints:

- observable execution before autonomy
- policy before power
- local-first runtime paths where feasible
- receipts for attempted input, output, approval, denial, and execution actions
- deterministic behavior where state and configuration match
- explicit contracts across trust boundaries
- no hidden execution from model output
- memory as a typed subsystem, not transcript dumping
- UI truth over cosmetic state
- bounded diffs and validation tied to the touched surface

These principles are enforced through docs, tests, scripts, and implementation
contracts. They are not branding language.

## Roadmap

The roadmap is intentionally staged so higher-level autonomy cannot outrun the
runtime spine.

| Milestone | Meaning | Current posture |
| --- | --- | --- |
| M1 ORB Core | Server-side plane transitions, identity, approvals, and audit records are enforced | Active Phase 2 priority |
| M2 Functional Francis | One operator request can plan, gate, execute, trace, and update continuity | Partial, not closed |
| M3 User-Friendly Francis | The UI explains plane, gate, approval, trace, artifact, and recovery state | Partial, actively being connected |
| M4 Differentiated Francis | Evidence, simulation, federation, code-born ingest, and capability economy mature on top of ORB core | Roadmap and bounded slices only |

Full roadmap:

- [docs/canonical/ROADMAP.md](docs/canonical/ROADMAP.md) for target state.
- [docs/canonical/BUILD_MANIFEST.md](docs/canonical/BUILD_MANIFEST.md) for
  Phase 2 ORB build gates.
- [docs/BUILD_ORDER.md](docs/BUILD_ORDER.md) for build sequencing.
- [docs/operations/COMPLETION_LEDGER.md](docs/operations/COMPLETION_LEDGER.md)
  for shipped truth and validation history.

## Evidence This Is Real

The repository is an active engineering project, not just a concept document.
Evidence should be read from the repo, not inferred from claims.

- The append-only completion ledger records shipped posture, validation, and
  remaining gaps.
- Recent local commit history includes security cleanup, GitHub posture cleanup,
  Francis1 orchestration readbacks, Orb operator dry-run receipts, Trust Ladder
  grounding, and collaboration/runtime UI work.
- The Python runtime and React UI have targeted tests and a full local check
  command.
- The ledger names exact validation commands when a surface changes.
- The latest ledger-backed implementation slices include dry-run Orb
  move/click/type intent receipts and Francis1 self-model/draft-dispatch MCP
  readbacks.
- The CI badge reflects the live GitHub Actions workflow for `main`; specific
  passing or failing gates should be read from Actions or the ledger, not
  assumed from this README.

Current visual asset:

- The runtime-loop diagram above is a real repository asset. Additional Orb,
  HUD, or desktop screenshots should be added only when tied to live UI proof, so
  this README does not present mock visuals as shipped functionality.

## Presentation Demo

Francis has a safe visual presentation path that shows current build posture,
MCP governance smoke, and Orb operator dry-run receipts without claiming live
desktop control:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\francis-presentation-demo.ps1
```

Use [docs/presentation/FRANCIS_PRESENTATION_DEMO.md](docs/presentation/FRANCIS_PRESENTATION_DEMO.md)
for the presenter runbook, visual artifact location, allowed claims, and claims
that must not be made.

## Repository Navigation

| Need | Start here |
| --- | --- |
| First-reader path | [docs/START_HERE.md](docs/START_HERE.md) |
| Current shipped truth | [docs/operations/COMPLETION_LEDGER.md](docs/operations/COMPLETION_LEDGER.md) |
| Canonical vision | [docs/canonical/VISION.md](docs/canonical/VISION.md) |
| Roadmap | [docs/canonical/ROADMAP.md](docs/canonical/ROADMAP.md) |
| Build gates | [docs/canonical/BUILD_MANIFEST.md](docs/canonical/BUILD_MANIFEST.md) |
| Architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/PLANES.md](docs/PLANES.md) |
| Governance | [docs/GOVERNANCE.md](docs/GOVERNANCE.md), [docs/POLICIES.md](docs/POLICIES.md), [docs/TRUST_MODEL.md](docs/TRUST_MODEL.md) |
| Memory | [docs/MEMORY.md](docs/MEMORY.md) |
| Web and external data | [docs/WEB_ACCESS.md](docs/WEB_ACCESS.md) |
| Plugins and capabilities | [docs/PLUGINS.md](docs/PLUGINS.md), [plugins/](plugins/) |
| MCP and developer bridge | [docs/operations/MCP_CLIENT_SETUP.md](docs/operations/MCP_CLIENT_SETUP.md), [docs/architecture/FRANCIS_MCP_GATEWAY.md](docs/architecture/FRANCIS_MCP_GATEWAY.md) |
| Input and desktop operation path | [docs/architecture/FRANCIS_INPUT_ACTUATOR.md](docs/architecture/FRANCIS_INPUT_ACTUATOR.md), [src/francis/input_actuator/](src/francis/input_actuator/) |
| Presentation demo | [docs/presentation/FRANCIS_PRESENTATION_DEMO.md](docs/presentation/FRANCIS_PRESENTATION_DEMO.md), [scripts/francis-presentation-demo.ps1](scripts/francis-presentation-demo.ps1) |
| Contribution rules | [AGENTS.md](AGENTS.md), [CONTRIBUTING.md](CONTRIBUTING.md) |

Core code map:

- [src/francis/](src/francis/) - Python runtime: API, governance, missions,
  memory, execution, observability.
- [apps/chat_ui/](apps/chat_ui/) - Vite/React operator UI.
- [tests/](tests/) - pytest coverage for API contracts, runtime behavior, and
  integration paths.
- [scripts/](scripts/) - local bootstrap, runtime, proof, and validation
  entrypoints.
- [config/](config/), [schemas/](schemas/), [connectors/](connectors/),
  [plugins/](plugins/), [specializations/](specializations/) - policy,
  contract, integration, and extension surfaces.

## Quick Start

From PowerShell:

```powershell
cd D:\Francis
.\scripts\bootstrap.ps1
.\scripts\francis.ps1 api
```

Open API docs at `http://127.0.0.1:8000/docs`.

Run the chat UI:

```powershell
.\scripts\bootstrap.ps1 -IncludeChatUI
cd apps\chat_ui
npm run dev
```

Open the UI at `http://localhost:5173`.

## Validation

Run the main repository gate:

```powershell
.\scripts\check.ps1
```

This runs branch-state checks, Ruff lint, Ruff format check, mypy, and pytest.

For targeted validation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_api_missions.py -q
.\.venv\Scripts\python.exe -m mypy src
cd apps\chat_ui
npm test
npm run build
```

## Supervised Execution

Francis separates command proposal from authorized execution. Use supervised exec
for bounded local commands:

```powershell
.\scripts\francis.ps1 supervised-exec --cmd "echo hello" --print-summary
```

If the run returns `needs_approval`, approve the exact `approval_id` and rerun
with that id:

```powershell
.\.venv\Scripts\python.exe -c "from francis.governance.approvals import decide; decide('<approval_id>','approve')"
.\scripts\francis.ps1 supervised-exec --cmd "echo hello" --approval-id <approval_id> --print-summary
```

`DECISION:` and `SUMMARY:` lines are written to `stderr`; `stdout` remains JSON.

## Contributing

Francis is useful work for AI engineers, systems programmers, UI developers,
infrastructure engineers, security reviewers, HCI researchers, robotics-minded
operator-interface builders, plugin developers, and documentation contributors
who are comfortable working inside strict governance boundaries.

High-value contributions improve one of the active roadmap surfaces reflected in
the ledger and build manifest:

- governance and approval contracts
- observer/readiness and receipt-backed truth
- mission continuity, deadletter recovery, and handoff context
- memory read/write contracts with bounded behavior
- ORB UI truthfulness and recovery paths
- local execution paths that remain policy-aware and auditable
- plugin and capability lifecycle evidence
- Lens, Orb, and desktop-operation readbacks that do not fake authority

Start with [AGENTS.md](AGENTS.md), [CONTRIBUTING.md](CONTRIBUTING.md), and the
completion ledger before making non-trivial changes. Keep diffs bounded,
roadmap-aligned, and validated with the narrowest meaningful tests.

Local checkout rule: if a repo root contains `.francis-mirror`, standard runtime
entrypoints refuse to start there. Use that marker for mirror-only copies and run
Francis from the primary checkout instead.

## License

Francis is proprietary and all rights are reserved by Austin Peppers. Viewing,
cloning, forking, or submitting material to this repository does not grant
permission to use, copy, distribute, commercialize, or create derivative works
from Francis except under a separate written agreement. See [LICENSE](LICENSE).

Accepted contributions may be recognized individually — credit and
acknowledgment are given at Austin Peppers' sole discretion. No ownership,
equity, or compensation is offered, implied, or created by submitting a
contribution or by having one accepted. Any exception exists only in a separate
written agreement signed by Austin Peppers.

Licensing and permission inquiries: peppera091@gmail.com

## GitHub Engagement

This repository is public, but it is not looking for speculative feature sprawl.
Useful issues and PRs should improve an active roadmap surface: governance,
identity, observability, mission continuity, memory contracts, local execution,
Lens/orb embodiment, truthful operator UI, or capability lifecycle evidence.

Good contributions name the roadmap surface, describe the trust boundary
involved, include validation that actually ran, and avoid claiming scaffolded
behavior as finished capability.

## Vision

Francis is being built toward persistent desktop-native intelligence: an
operator that can observe, remember, plan, request permission, act through
governed channels, produce receipts, and stop cleanly when authority is revoked.

The long-term direction is not AGI theater. It is a local-first operating layer
where human intent, machine context, delegated capability, and auditability can
coexist without turning the model into a hidden sovereign.
