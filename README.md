# Francis

Francis is a local-first, policy-guarded, auditable operator layer for a personal computing environment. It is being built as an OS-layer Digital Twin Operator: a resident system that can understand work context, carry mission continuity, stage and execute bounded actions, and leave receipts for what happened.

Francis is not a chatbot wrapper, demo UI, generic agent loop, or dashboard with a model attached. The project goal is a governed operating layer where cognition, approval, execution, observability, and memory are separated by explicit contracts.

## Current Build Posture

Francis is in **Phase 2**. The strongest shipped posture is a governed runtime spine, not a finished operator product.

- `P9_OBSERVABILITY` is the strongest plane today.
- `P3_GOVERNANCE` is materially real.
- `P1_INTERFACE`, `P7_EXECUTION`, and `P8_MEMORY` are partial and actively being connected into a truthful loop.
- Current priority is the end-to-end `plan -> gate -> execute -> trace -> memory` path, then making that path clear in the operator UI.

Use [docs/operations/COMPLETION_LEDGER.md](docs/operations/COMPLETION_LEDGER.md) for shipped truth. Use [docs/canonical/ROADMAP.md](docs/canonical/ROADMAP.md) and [docs/canonical/BUILD_MANIFEST.md](docs/canonical/BUILD_MANIFEST.md) for target state and build order.

## ORB Runtime Model

Francis is organized around ORB planes. A request should move through explicit stages:

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
cd C:\Francis
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
