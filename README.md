# Francis

[![CI](https://github.com/Ap3pp3rs94/Francis/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Ap3pp3rs94/Francis/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue)
![Build Posture](https://img.shields.io/badge/build-ledger--grounded-orange)
![Local First](https://img.shields.io/badge/posture-local--first-brightgreen)
![Governed](https://img.shields.io/badge/actions-policy--guarded-2f6f9f)

Francis is a local-first, policy-guarded, auditable operator layer for a personal computing environment. It is being built as an OS-layer Digital Twin Operator: a resident system that can understand work context, carry mission continuity, stage and execute bounded actions, and leave receipts for what happened.

Francis is not a chatbot wrapper, demo UI, generic agent loop, or dashboard with a model attached. The project goal is a governed operating layer where cognition, approval, execution, observability, and memory are separated by explicit contracts.

New here? Start with [docs/START_HERE.md](docs/START_HERE.md) for the truthful first-reader path through roadmap, shipped state, runtime model, and contribution surfaces.

## Why Watch Francis

Most AI tooling optimizes for prompts, agents, or dashboards. Francis is being built around a different target: a governed local operator layer that can carry missions across sessions without hiding authority, faking progress, or treating model output as permission.

Current work is focused on the hard parts that make that credible:

- local-first runtime behavior before cloud dependency
- policy and approvals before side effects
- receipts and audit trails before autonomy claims
- mission continuity before generic agent loops
- operator-facing truth before cosmetic UX

If you are interested in trustworthy local AI systems, governed automation, auditable agent execution, or OS-layer operator interfaces, this repository is the build log and implementation spine.

## Current Build Posture

Francis should be read from current repo truth, not from a hard-coded phase label. The strongest shipped posture is a governed runtime spine, not a finished operator product. The active roadmap work is currently Stage 17 / Capability Economy: turning generated and promoted capabilities into versioned, tested, documented, governed internal assets rather than a pile of scripts.

- `P9_OBSERVABILITY` is the strongest plane today.
- `P3_GOVERNANCE` is materially real.
- `P1_INTERFACE`, `P7_EXECUTION`, and `P8_MEMORY` are partial and actively being connected into a truthful loop.
- Stage 3 / Missions and Stage 5 / Reactor are closed for the current repo posture by ledger-backed audits.
- Stage 6 / Lens has backend and chat-UI readback for Lens primitives, host readiness contracts, activation-denial receipts, preflight diagnostics, and bounded proof scripts. Do not read later roadmap work as proof of finished OS-wide summon, always-on resident presence, tray/hotkey/overlay runtime, or live Pilot takeover.
- Stage 17 / Capability Economy now has read-only pack readiness, migration-plan, metadata-receipt, quality-standards, promotion-rules, quality-test, and quality-doc evidence surfaces. The current gap is still capability-library maturity: legacy packs need stronger evidence, operator-facing review, validation receipts, and promotion discipline before Stage 17 can be called complete.

## Latest Progress Snapshot

This block is intentionally overwritten as the build moves. The append-only
history stays in [docs/operations/COMPLETION_LEDGER.md](docs/operations/COMPLETION_LEDGER.md).

- Last updated: 2026-06-01, 21:17 America/Chicago.
- Latest confirmed GitHub gate: `main` commit `b7919c34` passed CI on Ubuntu
  3.12, Ubuntu 3.13, Windows 3.12, and Windows 3.13; CodeQL passed for Actions,
  JavaScript/TypeScript, and Python.
- Current slice: Stage 17 capability pack quality-docs readback, adding a
  read-only API surface that audits declared pack documentation against
  `README.md` and `docs/` paths without reading documentation contents or
  granting authority.
- Next truthful gap: capability-library maturity still needs validation
  receipts, operator-facing review, and promotion discipline before Stage 17 can
  be called complete.

Use [docs/operations/COMPLETION_LEDGER.md](docs/operations/COMPLETION_LEDGER.md) for shipped truth. Use [docs/canonical/ROADMAP.md](docs/canonical/ROADMAP.md) and [docs/canonical/BUILD_MANIFEST.md](docs/canonical/BUILD_MANIFEST.md) for target state and build order. Phase and stage names are orientation markers only; each build pass should derive the active priority from the ledger and canonical roadmap instead of locking Francis into one fixed phase.

## ORB Runtime Model

Francis is organized around ORB planes. A request should move through explicit stages:

![Francis governed runtime loop](docs/assets/francis-runtime-loop.svg)

```text
P1_INTERFACE -> P4_COGNITION -> P3_GOVERNANCE -> P2_IDENTITY
  -> P7_EXECUTION -> P9_OBSERVABILITY -> P8_MEMORY
```

The rule is simple: proposal is not execution. Model output does not grant authority. Side effects must be policy-aware, scoped, auditable, and visible to the operator.

## Repository Map

- `src/francis/` - Python runtime: API, governance, missions, memory, execution, observability.
- `apps/chat_ui/` - Vite/React operator UI for ORB, mission, settings, and continuity surfaces.
- `tests/` - pytest coverage for API contracts, runtime behavior, and integration paths.
- `docs/` - architecture, policies, trust model, memory, web access, and domain-specific design docs.
- `docs/canonical/` - roadmap, build manifest, philosophy, vision, and capability targets.
- `docs/operations/` - shipped-state ledger and operational truth.
- `scripts/` - local bootstrap, runtime, validation, and observer entrypoints.
- `config/`, `schemas/`, `connectors/`, `plugins/`, `specializations/` - policy, contract, integration, and extension surfaces.

## Quick Start

From PowerShell:

```powershell
cd D:\francis
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

Francis separates command proposal from authorized execution. Use supervised exec for bounded local commands:

```powershell
.\scripts\francis.ps1 supervised-exec --cmd "echo hello" --print-summary
```

If the run returns `needs_approval`, approve the exact `approval_id` and rerun with that id:

```powershell
.\.venv\Scripts\python.exe -c "from francis.governance.approvals import decide; decide('<approval_id>','approve')"
.\scripts\francis.ps1 supervised-exec --cmd "echo hello" --approval-id <approval_id> --print-summary
```

`DECISION:` and `SUMMARY:` lines are written to `stderr`; `stdout` remains JSON.

## Operating Rules

- Do not claim autonomy where the repo only has scaffolding.
- Do not create fake progress, fake state, or demo-only UX signals.
- Preserve orb interaction fidelity, HUD truthfulness, shell integration, memory contracts, policy surfaces, logs, receipts, and auditability.
- Treat memory as a governed subsystem with typed, testable read/write paths.
- Treat any file mutation, external action, or trust-boundary crossing as policy-aware and auditable.

## Contributing

Start with [AGENTS.md](AGENTS.md), [CONTRIBUTING.md](CONTRIBUTING.md), and the shipped-state ledger before making non-trivial changes. Keep diffs bounded, roadmap-aligned, and validated with the narrowest meaningful tests. When touching operator-facing behavior, report exactly what was validated and what remains partial.

Local checkout rule: if a repo root contains `.francis-mirror`, standard runtime entrypoints refuse to start there. Use that marker for mirror-only copies and run Francis from the primary checkout instead.

## License

Francis is proprietary and all rights are reserved by Austin Peppers. Viewing, cloning, forking, or submitting material to this repository does not grant permission to use, copy, distribute, commercialize, or create derivative works from Francis except under a separate written agreement. See [LICENSE](LICENSE).

Only clean additions that Austin Peppers fully accepts and incorporates into Francis, and that materially improve Francis by creating measurable build momentum or acceleration, are eligible for ownership consideration of up to one percent (1%) of Francis project ownership. Submission, review, discussion, partial acceptance, experimental use, temporary use, or rejection does not qualify. Contributions that create advantages beyond Austin Peppers' own current implementation capacity may open a broader ownership conversation. Any ownership grant must be documented in a separate written agreement; contribution or full acceptance alone does not create ownership rights.

## GitHub Engagement

This repository is public, but it is not looking for speculative feature sprawl. Useful issues and PRs should improve one of the active roadmap surfaces reflected in the ledger and build manifest: governance, identity, observability, mission continuity, memory contracts, local execution, or truthful operator UI.

Good contributions name the roadmap surface, describe the trust boundary involved, include validation that actually ran, and avoid claiming scaffolded behavior as finished capability.
