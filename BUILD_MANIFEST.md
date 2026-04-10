# Francis 2.0 — Build Manifest (Phase 2)



> **Authoritative scope:** This document is the build system’s human-readable control plane.

> It defines **WHAT gets implemented**, **WHEN**, and **WHAT “done” means**, using the **conical dependency model**

> (foundation → kernel → memory → governance → LLM → chat → plugins → higher systems).

>

> **Phase 2 rule:** File-by-file implementation only. No tree redesign. No speculative subsystems.



---



## 0) Document Contract



### 0.1 What this file is

This manifest is the **authoritative implementation schedule** and the **quality-gate definition** for Francis.



It exists to prevent:

- “scaffold drift” (empty files that never become real)

- hidden coupling (features added above missing foundations)

- silent regression (features that run but aren’t observable, testable, or governed)



### 0.2 What this file is NOT

- Not a replacement for architecture docs (see `docs/ARCHITECTURE.md`, `docs/BUILD_ORDER.md`)

- Not a CI config (see `.pre-commit-config.yaml`, future CI workflows)

- Not a roadmap “wishlist” (only list what we intend to implement)



### 0.3 How to update this manifest

- Update **only when**:

  - a layer is completed

  - a quality gate changes

  - file-order changes are explicitly requested

- When a file is completed, mark it ✅ in the relevant queue section.



---



## 1) Operating Principles (Non‑Negotiables)



### 1.1 Build invariants (must always hold)

1) **Determinism**

   - A cold start should behave the same given the same config + state.

2) **Observability first**

   - Logging, audit events, and minimal metrics precede “clever behavior.”

3) **Policy before power**

   - Any action that touches the world must be governed (trust, approvals, safety policies).

4) **No secrets in UI**

   - Browser/UI never receives raw secrets; only metadata + references.

5) **Backwards compatibility**

   - Public interfaces (API routes, event schemas, storage layouts) evolve with explicit versioning / compatibility shims.



### 1.2 Phase 2 execution protocol (file-by-file)

For each file:

- Explain purpose in system

- Provide **full drop** (complete file content)

- Keep it advanced, correct, extensible

- Do not introduce new files unless explicitly approved

- Prefer clarity + correctness + observability over cleverness



---



## 2) Conical Dependency Model



### 2.1 Why “cone layers” exist

Francis is a long-lived autonomous system. The cone model enforces:

- strong foundations (config/logging/state)

- explicit governance gates

- modular evolution (plugins, specializations)

- safe expansion into higher-risk domains (industrial, web learning, federation)



### 2.2 Cone layers (authoritative)

**Layer 0 — Foundation**

- repo hygiene, formatting, environment surfaces, dev ergonomics, packaging invariants



**Layer 1 — Kernel**

- config loader, paths, process lifecycle, error model, base types, core utilities



**Layer 2 — Memory**

- ledger/continuity, storage backends, indexing, retrieval primitives, attachments pipeline



**Layer 3 — Governance**

- approvals, trust calculus, policy evaluation, audit, permissions, safety boundaries



**Layer 4 — LLM Subsystem**

- provider abstraction, routing, model constraints, tool invocation contracts



**Layer 5 — Chat**

- protocol, session orchestration, streaming, conversation state, UI integration



**Layer 6 — Plugins**

- plugin spec, registry, sandboxing, execution, artifact outputs, plugin building



**Layer 7 — Higher Systems**

- federation, industrial control, system profiling, self-heal/evolve loops, specialization layer



---



## 3) Runtime Surfaces (What must keep working)



### 3.1 Services

- **API** (backend HTTP + WS)

- **Daemon** (scheduler + autonomous loop runner)

- **Workers** (background execution pool)

- **Chat UI** (operator console)



### 3.2 Minimum “always works” commands (baseline)

These are **baseline acceptance checks** during Phase 2:

- API: `python -m francis api`

- Daemon: `python -m francis daemon`

- UI: `npm run dev` (from `apps/chat_ui`)



If any file change breaks these, the file is not “done.”



---



## 4) Quality Gates (Definition of Done)



### 4.1 Per-file “done” gate

A file is considered ✅ complete when:

- It has a clear purpose + contract (docstring/header comments where appropriate)

- It is typed (Python typing / TS types) and defensively coded

- It is observable (logs/errors are actionable; no silent failures)

- It preserves compatibility with the current tree + running services

- It has no obvious security footguns (secrets, unsafe defaults, missing redaction)

- It passes local checks relevant to its layer:

  - lint/format (ruff/prettier/etc as configured)

  - unit tests (where applicable)

  - runtime smoke (if it’s an entrypoint, protocol, or config surface)



### 4.2 Layer completion gate

A layer is considered complete when:

- Its public contracts are stable (types, schemas, core APIs)

- It has tests for critical invariants

- It has instrumentation hooks (logging/audit/metrics) for core flows

- Higher layers are not forced to “work around” missing behavior



---



## 5) Canonical Order Source



### 5.1 Canonical file list

The canonical file ordering is derived from the repository’s enumerated file list:

- `francis_tree_ps.filtered.txt`



### 5.2 Canonical ordering rule (deterministic)

Within a cone layer:

1) Prefer **interfaces/types/schemas** first

2) Then **core utilities**

3) Then **providers/adapters**

4) Then **service wiring / entrypoints**

5) Then **UI bindings**



Tie-breaker is stable lexicographic order by path.



---



## 6) System Map (Orientation)



### 6.1 Top-level directories (what they are)

- `apps/` — runnable entrypoints (api/daemon/workers/chat_ui)

- `src/francis/` — main Python package (core runtime)

- `config/` — runtime configuration (profiles, policies, prompts, models)

- `meta/` — foundational models (axioms, risk, trust, governance principles)

- `schemas/` — JSON schemas for contracts (messages, actions, domains, etc.)

- `plugins/` — plugin system (registry/spec/templates/packs)

- `connectors/` — external integration adapters (cloud, protocols, comms)

- `runtimes/` — model runtimes and execution environments (ollama, etc.)

- `scripts/` — operational scripts (doctor, reset, deploy, trust reset, etc.)

- `data/` — runtime state (ignored by git; templates allowed)

- `docs/` — deep documentation set

- `specializations/` — domain specialization manifests + assets

- `infra/` — docker/k8s/terraform deployment artifacts

- `sdk/` — integration SDKs (polyglot)



### 6.2 State + artifacts (do not commit)

- `data/conversations/ledger/ledger.jsonl` — continuity ledger

- `data/approvals/*` — approval queues

- `data/artifacts/*` — generated outputs

- `data/vectors/*` — vector indices/cache

- `data/credentials/vault.db` — credential vault database



---



## 7) Implementation Queue (Phase 2)



> **Important:** This queue is grouped by cone layer.  

> We execute **one file at a time**. Each completed file becomes ✅ here.



---



### Layer 0 — Foundation ✅/⬜



#### L0 goals

- Establish consistent formatting + safe ignores

- Lock down environment surfaces

- Ensure developer workflows are fast and reproducible



#### L0 queue

- ✅ `.editorconfig`

- ✅ `.env.example`

- ✅ `.gitignore`

- ✅ `.pre-commit-config.yaml`

- ⬜ `.python-version`

- ⬜ `pyproject.toml` (only if changes are required; otherwise treat as locked)

- ⬜ `ruff.toml` (only if changes are required; otherwise treat as locked)

- ⬜ `mypy.ini` / `pytest.ini` (only if changes are required; otherwise treat as locked)

- ⬜ `BUILD_MANIFEST.md` (this file)



---



### Layer 1 — Kernel ⬜



#### L1 goals

- Make the package runtime deterministic and inspectable

- Provide canonical config, logging, error model, and path handling

- Define core types used everywhere else



#### L1 queue (representative / anchor files; expand as we reach them)

- ✅ `src/francis/telemetry/logging.py`

- ✅ `src/francis/telemetry/audit.py`

- ✅ `src/francis/telemetry/metrics.py`

- ✅ `src/francis/telemetry/tracing.py`

- ⬜ `src/francis/temporal/versioning/backward_compatibility.py`

- ✅ `src/francis/world_state/snapshot.py`



**Kernel acceptance tests (layer gate):**

- import-time sanity: `python -c "import francis"`

- API/daemon start without stack traces

- logs contain clear startup banners and configuration redaction



---



### Layer 2 — Memory ⬜



#### L2 goals

- Make continuity, storage, and retrieval real (and safe)

- Ensure attachments + ingestion pipeline is deterministic and governed

- Make memory timelines queryable and exportable



#### L2 queue (representative / anchor files)

- ✅ `schemas/memory.schema.json` (contract)

- ✅ `schemas/conversation_state.schema.json` (contract)

- ⬜ `data/conversations/ledger/ledger.jsonl` (runtime artifact; format contract only)

- ⬜ `docs/CONVERSATION_CONTINUITY.md` (validate reality vs doc)



**Memory acceptance tests:**

- ledger read/write paths stable

- export path produces redacted output if needed

- no UI receives raw sensitive payloads from attachments



---



### Layer 3 — Governance ⬜



#### L3 goals

- Approvals are enforceable, not decorative

- Trust is computed, stored, and used to gate actions

- Audit is complete enough to support compliance narratives



#### L3 queue (representative / anchor files)

- ✅ `schemas/risk_assessment.schema.json`

- ✅ `schemas/authority_model.schema.json`

- ✅ `schemas/action_request.schema.json`

- ✅ `schemas/action_result.schema.json`

- ✅ `src/francis/trust/calculator.py`

- ✅ `src/francis/trust/levels.py`

- ✅ `src/francis/trust/tracker.py`

- ✅ `src/francis/trust/boundaries.py`



**Governance acceptance tests:**

- approvals cannot be bypassed by API calls

- audit events are emitted for decisions and tool invocations

- trust state persists and is explainable



---



### Layer 4 — LLM Subsystem ⬜



#### L4 goals

- Provider abstraction, routing, constraints, fallbacks

- Tool invocation contract + structured outputs

- Safe sampling and prompt hygiene



#### L4 queue (representative / anchor files)

- ⬜ `config/models/providers/openai.yaml`

- ⬜ `config/models/providers/ollama.yaml`

- ⬜ `config/models/routing.yaml`

- ⬜ `runtimes/ollama/model_roster.yaml`

- ✅ `schemas/chat_message.schema.json`



**LLM acceptance tests:**

- provider routing deterministically selects a model

- timeouts/fallbacks behave predictably

- structured tool calls validated against schemas



---



### Layer 5 — Chat ⬜



#### L5 goals

- Stable chat protocol (WS events, message schemas, streaming)

- Conversation orchestration ties into memory + governance

- UI becomes a faithful operator console (not a demo)



#### L5 queue (UI-focused; expand as backend contracts stabilize)

- ✅ `apps/chat_ui/index.html`

- ⬜ `apps/chat_ui/public/manifest.json` (PWA shell; add if used)

- ✅ `apps/chat_ui/src/App.tsx`

- ⬜ `apps/chat_ui/src/chat/*` (protocol + client)

- ⬜ `apps/chat_ui/src/attachments/*`

- ✅ `apps/chat_ui/src/approvals/*`

- ✅ `apps/chat_ui/src/credential_manager/*`



**Chat acceptance tests:**

- WS reconnects cleanly with backoff

- events parse defensively (plain text / JSON / structured)

- sending a message updates continuity ledger (end-to-end)



---



### Layer 6 — Plugins ⬜



#### L6 goals

- Plugin spec is enforceable (schemas + validators)

- Plugin registry is deterministic

- Plugin execution is sandboxed and audited



#### L6 queue (representative / anchor files)

- ✅ `schemas/plugins.schema.json`

- ✅ `plugins/spec/*`

- ✅ `plugins/registry/*`

- ⬜ `plugins/templates/*`

- ⬜ `scripts/plugin-build.ps1`



**Plugin acceptance tests:**

- plugin build produces artifacts into `data/artifacts/plugins/`

- plugin execution emits audit records

- policy gates apply before plugin side effects



---



### Layer 7 — Higher Systems ⬜



#### L7 goals

- Federation (multi-instance coordination)

- Industrial control \& digital twins

- System profiling, self-heal/evolve loops

- Domain workbench + specialization expansion



#### L7 queue (UI + contracts; expand as backend is implemented)

- ⬜ `apps/chat_ui/src/federation_hub/*`

- ⬜ `apps/chat_ui/src/industrial_control/*`

- ⬜ `apps/chat_ui/src/digital_twin_center/*`

- ⬜ `apps/chat_ui/src/domain_workbench/*`

- ⬜ `apps/chat_ui/src/explanation_explorer/*`

- ⬜ `apps/chat_ui/src/trust_dashboard/*`

- ⬜ `apps/chat_ui/src/web_learning_monitor/*`

- ⬜ `tests/industrial/*`

- ⬜ `tests/resilience/*`

- ⬜ `docs/INDUSTRIAL_SIMULATIONS.md`

- ⬜ `docs/FEDERATION.md` (if present; otherwise keep governance/policies aligned)



**Higher-systems acceptance tests:**

- no “control” action bypasses governance

- industrial safety validations are logged and reproducible

- federation consensus logs are append-only and auditable



---



## 8) Cross-Cutting Gates (Always On)



### 8.1 Security gates

- UI never receives secrets (only refs + redacted hints)

- Approval required for risky actions by default

- Web learning must honor `config/policies/web_access.yaml` and `meta/internet_safety_model.yaml`



### 8.2 Observability gates

- Every important action produces:

  - structured logs (component, action, outcome)

  - audit record (who/what/why)

  - correlation identifiers where feasible



### 8.3 Compatibility gates

- Schema evolution is additive unless explicitly versioned

- Storage files are append-only where possible (ledger, logs)

- Backwards-compat shims exist if any contract changes



---



## 9) Known Hotspots (Build Forward Mindset)



These are areas where “works locally” often hides future failure modes:



1) **Windows path + CRLF handling**

   - Ensure scripts and PowerShell files remain CRLF where appropriate.

2) **State deletion safety**

   - Never require deleting `data/` to fix correctness; build migrations and resets.

3) **UI/Backend contract drift**

   - Prefer schemas under `schemas/` and validate payloads at both ends.

4) **Web learning and compliance**

   - Treat browsing as a governed capability with logging + approvals.

5) **Industrial control**

   - All actuation is safety-critical; policy gates must be enforced server-side.



---



## 10) Release Readiness Checklist (Future, but grounded)



A “production-ish” release is allowed only if:

- API + daemon can restart cleanly (no manual state hacks)

- logs/audit are sufficient to reconstruct actions

- approvals and trust gates are effective

- plugin execution is sandboxed + auditable

- UI is a reliable operator console, not a toy



---



## Appendix A — What to read when implementing a layer



- Build order philosophy: `docs/BUILD_ORDER.md`

- Architecture: `docs/ARCHITECTURE.md`

- Policies: `docs/POLICIES.md`

- Governance: `docs/GOVERNANCE.md`

- Trust model: `docs/TRUST_MODEL.md`

- Memory model: `docs/MEMORY.md`

- Plugins: `docs/PLUGINS.md`

- Industrial: `docs/INDUSTRIAL_SIMULATIONS.md`

- Runbook: `docs/RUNBOOK.md`



---



## Appendix B — Minimal operator workflow (UI)



UI should support:

- view chat status + reconnect state

- send/receive messages

- view continuity ledger

- view pending approvals + decide (when enabled)

- inspect errors with enough context to fix root cause



Everything beyond that is layered on top of governance and memory, not beside them.



