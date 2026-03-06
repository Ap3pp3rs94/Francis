# Francis Roadmap
**An OS-layer Digital Twin + 4th-wall overlay, governed enough for production, powerful enough for holy shit.**

> **Prime framing:** Francis is not a health tool. Francis is an **Operator Layer** over your PC that can **understand your work in context**, **assist in-place**, and **take over execution as you** only when you explicitly grant control with **scope, receipts, approvals, and a kill switch**.

---

## How to use this roadmap (Codex guide)
This file is the canonical build guide for Codex. Every build step should:

1) **Restate the objective** (what changes for the user)  
2) **Name the affected modules/files**  
3) **Implement full files** (no half patches)  
4) **Run quality gates** (`ruff`, `pytest`)  
5) **Report receipts** (what changed, verification, how to run)

**Build principle:** ship vertical slices that improve the lived experience, not just infrastructure.

---

## Master Spec Alignment (Canonical)
- Autonomy is event-driven reactor dispatch with budgets, stop conditions, receipts, and deadletter handling (no generic loops).
- Lens overlay is the signature product surface with command palette, contextual action chips, and always-visible Pilot indicator.
- Work telemetry is opt-in, high-signal, and scope-bound with redaction and explicit user visibility.
- Takeover follows a strict ritual (request, scope, confirm, pilot-on, live feed, handback receipts) with panic/kill revocation.
- Adversarial hardening is first-class: untrusted input handling, quarantine model, policy bypass tests, and red-team gates.
- Swarm and federation require trace propagation (`run_id`/`trace_id`), scoped trust, and revocation by default.
- Apprenticeship and Forge require staged outputs, tests/docs/risk tier metadata, and explicit promotion gates.
- Business evolution is managed copies, federated deltas (no raw customer data), and rogue kill/replace from clean baselines.

---

## Roadmap legend
- **P0** = foundational, blocks other work  
- **P1** = major capability / signature experience  
- **P2** = hardening, scalability, productization  
- **P3** = optional / advanced / later

Each stage includes:
- **User experience goal**
- **System deliverables**
- **Acceptance criteria (Done looks like)**
- **Quality gates**

---

## Current status snapshot (keep updated)
> Update this section after every completed stage.

- Stage 1  Grounded Presence (truthful state + briefing + receipts)
- Stage 2  Observer (real probes + anomalies + incidents + event emission)
- Stage 3  Missions (create/list/tick) + queue/deadletter + run ledger
- Stage 3 Hardening  RBAC + idempotent leases for mission ticks
- Stage 4  Forge (propose/stage/promote) + catalog + tests
- Stage 5  Event-Driven Autonomy Kernel (reactor, not generic loop)
- Stage 6+  Francis Lens overlay + work telemetry + takeover UX

---

# Stage 0 (P0)  Foundation & Operating System Contracts
## Goal (user experience)
Francis feels **safe, predictable, and auditable** from day one.

## Deliverables
- Repo structure (services / packages / workspace / policies / schemas)
- Governance defaults (RBAC, approvals, scopes, receipts)
- Documentation contracts (Vision, Prime Directive, Control Modes, Voice Charter)
- Local-first workspace journaling (append-only audit trails)

## Acceptance criteria
- All writes to `workspace/*` are journaled and traceable
- Every meaningful action has a `run_id`
- No surprises policy is documented and enforced by design
- User is pilot is explicit everywhere

## Quality gates
- `ruff check .` passes
- `pytest` passes

---

# Stage 1 (P0/P1)  Presence: Grounded, Truthful, Calm
## Goal (user experience)
Francis feels **present** and **useful** without being noisy:
- It greets you with **truth**
- It summarizes what matters
- It suggests next moves
- It never fabricates state

## Deliverables
- `/presence/state` (truthful snapshot: inbox counts, missions count, recent ledger)
- `/presence/briefing` (writes a grounded briefing with real facts)
- Presence tone contract (calm power, human warmth, zero BS)
- Receipts: every briefing produces artifacts (inbox entry + ledger)

## Acceptance criteria
- Briefing headline and bullets are derived from real local state
- If state is missing, Francis says unknown / missing rather than guessing
- Presence never claims work was done unless receipts exist

## Quality gates
- Integration tests for grounded briefing/state
- `ruff` + `pytest`

---

# Stage 2 (P1)  Observer: Real Awareness + Incidents
## Goal (user experience)
Francis sees the **reality** of your environment and turns it into:
- calm alerts
- grounded diagnostics
- actionable recommendations
- evidence-backed incident records

## Deliverables
- `/observer` endpoint returning grounded diagnostics
- Probes: disk/cpu/memory/network/processes/repo/services
- Baselines + anomaly detection + severity scoring
- Event emission into:
  - `workspace/logs/francis.log.jsonl`
  - `workspace/journals/decisions.jsonl`
  - `workspace/incidents/incidents.jsonl`
  - `workspace/runs/run_ledger.jsonl`

## Acceptance criteria
- Observer always emits receipts for scans
- Incidents include evidence and status lifecycle fields
- Presence can reference open incidents without hallucination

## Quality gates
- Integration test verifying event emission + incident count changes
- `ruff` + `pytest`

---

# Stage 3 (P1)  Missions: Intent Turned Into Progress
## Goal (user experience)
You can create objectives and Francis can **advance them** with traceable progress:
- missions are quests
- ticks move steps forward
- failures are captured cleanly
- nothing double-executes

## Deliverables
- `/missions` (POST create, GET list)
- `/missions/{id}` (GET)
- `/missions/{id}/tick` (POST)
- Workspace persistence:
  - `workspace/missions/missions.json`
  - `workspace/missions/history.jsonl`
- Queue + deadletter:
  - `workspace/queue/jobs.jsonl`
  - `workspace/queue/deadletter.jsonl`
- Run ledger tracing per mission action

## Acceptance criteria
- Mission tick advances exactly once per idempotency key
- Failure path lands in deadletter and marks mission failed
- Presence briefing references active mission count truthfully

## Quality gates
- Integration tests for create, tick, fail, idempotency, RBAC
- `ruff` + `pytest`

---

# Stage 4 (P1)  Forge: Self-Extension With Governance
## Goal (user experience)
When Francis hits friction, it doesnt shrug. It says:
> I can build a capability to eliminate this task. Ill stage it. You decide if it becomes real.

## Deliverables
- `/forge` summary + `/forge/catalog`
- `/forge/proposals` (grounded proposals from real context: missions/incidents/deadletter)
- `/forge/stage` (writes staged capability + tests under `workspace/forge/staging`)
- `/forge/promote/{stage_id}` (promotes staged entry to active in catalog)
- Catalog stored at `workspace/forge/catalog.json`
- Validation + diff summaries on stage

## Acceptance criteria
- Forge never deploys into production execution without explicit promotion
- Each staged capability has tests + docs + risk tier
- Lint does not break due to workspace artifacts (exclude workspace/runtime)

## Quality gates
- Integration test: proposals  stage  promote
- `ruff` + `pytest`

---

# Stage 5 (P1)  Event-Driven Autonomy Kernel (Reactor, Not a Loop)
## Goal (user experience)
Francis can work while youre away **without becoming a spammy or dangerous loop**.

Autonomy is:
- **event-driven** (something meaningful happened)
- **bounded** (budgets, scopes, approvals)
- **auditable** (decisions and actions have receipts)
- **reversible** (stop/panic + handback)

## Deliverables
- **Autonomy Reactor** (conceptual model):
  - Intake events  classify risk  plan  execute bounded actions  verify  record receipts
- Event queue + deadletter for autonomy events
- Autonomy endpoints (examples; exact names can evolve):
  - enqueue event
  - dispatch N events
  - inspect queue
- Decision journaling (why this action, why now)
- Budget controls:
  - max actions per dispatch
  - max time per dispatch
  - stop-on-critical-incidents

## Acceptance criteria
- No generic while true loops are required for autonomy
- Autonomy can be triggered by schedule *or* events, but execution remains bounded
- Autonomy never claims progress unless verification passes and receipts exist
- Autonomy halts action phase if critical incidents exist

## Quality gates
- Tests for:
  - safe actions execute
  - blocked actions are queued for approval
  - critical anomalies halt dispatch
  - idempotency prevents double execution
- `ruff` + `pytest`

---

# Stage 6 (P1/P2)  Francis Lens: The 4th-Wall Overlay Experience
## Goal (user experience)
Francis is a **HUD layer over your OS**, not a chat window:
- appears where relevant
- stays quiet otherwise
- shows missions/incidents/approvals
- offers contextual action chips
- makes Pilot Mode visible and safe

## Deliverables
- Overlay UX contract:
  - docking/undocking panels
  - command palette summon
  - action chips near errors (terminal/build/devtools)
  - persistent Pilot Mode ON indicator
- Control panel:
  - Observe / Assist / Pilot / Away mode selector
  - scope selection UI (repo/app/window)
  - panic/stop button
- HUD views:
  - Missions
  - Incidents
  - Approvals
  - Forge staging/promotions
  - Autonomy queue status

## Acceptance criteria
- Lens is not spyware: telemetry is opt-in and scope-limited
- Pilot Mode indicator is always visible when delegated
- STOP / PANIC immediately halts active execution

## Quality gates
- UX smoke tests (manual checklist)
- No hidden control rule documented and verified

---

# Stage 7 (P1/P2)  Work Telemetry Connectors (High-Signal, Opt-In)
## Goal (user experience)
Francis understands what youre doing because it sees **high-signal work context**:
- file edits (scoped)
- git diffs
- terminal command + output
- build/test errors
- IDE diagnostics
- optional browser console/network errors

This is watching you work without creepy full-screen recording.

## Deliverables
- Telemetry contracts (schemas + retention + redaction)
- Connectors (phased):
  - VS Code extension (open file, diagnostics, selections, tasks)
  - Terminal wrapper/PTY capture (commands + outputs in allowed scope)
  - Git watcher (diff summary, branch state)
  - Optional browser extension (console + network failures)
- Redaction pipeline:
  - tokens/keys/env vars never logged raw
- Visible indicators:
  - telemetry active
  - what scope is being observed

## Acceptance criteria
- Telemetry is opt-in by default
- Telemetry never escapes scope
- Redaction works and is testable (golden samples)
- Francis treats telemetry streams as **untrusted input** (see adversarial stage)

## Quality gates
- Unit tests for redaction and schema validity
- Integration test: sample telemetry event  ingest  visible in state/briefing

---

# Stage 8 (P1/P2)  Sandboxed Executor + Toolbelt (The Hands)
## Goal (user experience)
Francis can actually *do* work safely:
- edit files
- run commands
- manage git
- verify results
- always produce receipts

## Deliverables
- Toolbelt categories:
  - file ops (scoped)
  - shell exec (allowlisted)
  - git ops (safe defaults; branch-first)
  - http (scoped)
  - parsing utilities
- Budgets:
  - CPU/time caps
  - max file changes per run
- Execution semantics:
  - idempotency keys
  - leases for in-flight work
  - stop conditions
- Branch-first and verify-first defaults

## Acceptance criteria
- Executor cannot write outside scope
- Dangerous commands are blocked without explicit approval
- Every action produces:
  - diff or artifact
  - command log
  - verification output
  - run_id trace

## Quality gates
- Red-team tests: escape attempts, policy bypass attempts
- `ruff` + `pytest`

---

# Stage 9 (P1)  Digital Twin Takeover (Pilot Mode)
## Goal (user experience)
When you say take over, Francis **becomes your hands** inside scope:
- it navigates repo like a senior dev
- executes work end-to-end
- verifies results
- hands control back with receipts

## Deliverables
- Pilot Mode control-transfer ritual:
  1) request takeover
  2) show scope + allowed actions
  3) explicit confirm
  4) visible PILOT MODE ON
  5) live action feed
  6) handback with receipts + summary
- Kill switch / panic mode:
  - immediate stop
  - revokes pilot privileges
- Takeover scripts (high-level workflows):
  - fix build
  - implement feature from spec
  - refactor module
  - ship landing page (branch-first)

## Acceptance criteria
- Pilot Mode is never implicit
- Pilot Mode is always visible
- Panic works instantly
- Takeover always returns:
  - branch link
  - diff
  - tests/build results
  - summary

## Quality gates
- Integration tests for the control protocol (API-level)
- Manual UX checklist for overlay indicator correctness

---

# Stage 10 (P1/P2)  Apprenticeship (Teach  Generalize  Skill)
## Goal (user experience)
Francis becomes more like you over time:
- you demonstrate once
- Francis learns the pattern
- it stages a capability
- you promote it

## Deliverables
- Teaching sessions UX:
  - capture workflow events (scoped)
  - let user label intent
  - generate replay plan
- Generalization:
  - parameterize steps
  - add tests
  - stage as forge capability pack
- Promotion gates:
  - never auto-promote
  - risk tier assigned

## Acceptance criteria
- Apprenticeship does not require screen recording
- Output is always a staged capability with tests + docs
- User approves promotion before it becomes active

## Quality gates
- Evals: Does generated capability match demonstration?
- Regression tests on staged capability

---

# Stage 11 (P2)  Knowledge Fabric (Local Evidence + Citations)
## Goal (user experience)
Francis can answer and act using **your own artifacts** with citations:
- Im recommending this because of X log + Y diff + Z decision entry.

## Deliverables
- Artifact indexing:
  - repos
  - docs
  - logs/journals
  - incidents
  - mission history
  - staged capabilities
- Retrieval:
  - metadata + semantic search
  - grounded citations to local paths + run_ids
- Retention:
  - what persists vs rolls off
  - export/import portability

## Acceptance criteria
- Francis can cite local evidence for claims
- No claim about actions or state without receipts
- Sensitive content is redacted

## Quality gates
- Evals harness with golden tasks (find the last incident cause)
- Redaction tests

---

# Stage 12 (P2)  Trust Calibration (Confidence + Verification Gates)
## Goal (user experience)
Francis knows what it knows and communicates it honestly:
- Confirmed vs Likely vs Uncertain
- verifies before claiming done
- escalates when uncertain instead of bluffing

## Deliverables
- Confidence taxonomy + behavioral rules
- Verification gates:
  - build/tests must pass before fixed
  - preview checks before shipped
- Quarantine model:
  - suspicious instructions become approval items with evidence

## Acceptance criteria
- No confident claims without verification or evidence
- Untrusted inputs stance is consistent across the system

## Quality gates
- Red-team tests for hallucinated completion
- Injection and bypass tests

---

# Stage 13 (P2)  Adversarial Resilience + Red Team Hardening
## Goal (user experience)
Francis can safely operate in a world full of malicious text:
- prompt injections in repos
- terminal output tricks
- web page manipulations

## Deliverables
- Untrusted input taxonomy
- Injection containment:
  - quarantine suspicious requests
  - require approval + evidence
- Policy bypass tests:
  - privilege escalation attempts
  - scope escape attempts
  - social engineering attempts

## Acceptance criteria
- Content cannot grant permissions
- Only explicit user approvals can expand authority
- System remains stable under hostile inputs

## Quality gates
- Red-team suite must pass on CI
- Regression tests for known attack patterns

---

# Stage 14 (P2/P3)  Multi-Unit Swarm (Internal)
## Goal (user experience)
Francis can split into specialized units that coordinate:
- Builder unit
- Watcher unit
- Research unit
- UI unit
- Night shift unit

## Deliverables
- Unit identity + capability cards
- Delegation etiquette (visible handoffs)
- Trace propagation:
  - run_id/trace_id everywhere
- Message envelope schema + routing rules
- Deadletter + retry semantics

## Acceptance criteria
- Delegation preserves receipts and traceability
- Units cannot exceed the authority of the users declared scope and approvals
- Failures are contained and recoverable

## Quality gates
- Integration tests for agent messaging receipts
- Deadletter behavior tests

---

# Stage 15 (P3)  Federation (Multi-Node Across Devices) + Remote Presence & Approvals
## Goal (user experience)
Francis can keep working even if your main PC sleeps:
- an always-on node runs night shift
- you approve from phone/remotely
- same governance applies everywhere

## Deliverables
- Pairing model:
  - explicit consent
  - device fingerprint verification
  - scoped trust (least privilege)
  - revocation
- Sync model:
  - what can replicate (mission status, incident summaries, ledger summaries)
  - what cannot (secrets, private files, out-of-scope telemetry)
- Remote approvals UI (minimal viable):
  - approve/deny staged capability promotions
  - approve risky actions
  - pause autonomy / revoke pilot

## Acceptance criteria
- Zero-trust default: nodes do nothing until paired
- Remote approvals can revoke authority instantly
- Sync conflicts are handled by domain-specific rules (not naive LWW)

## Quality gates
- Security review checklist
- Integration tests for pairing + revoked trust behavior

---

# Stage 16 (P2/P3)  Capability Economy (Internal Library  Optional Marketplace)
## Goal (user experience)
Your capabilities become compounding leverage:
- reusable packs
- versioned and tested
- governed promotions
- sharable later if you choose

## Deliverables
- Capability pack format:
  - metadata (name, version, risk, deps)
  - docs
  - tests
- Promotion gates:
  - staged  validated  active
- Optional marketplace spec (later)

## Acceptance criteria
- No capability enters active status without tests + docs
- Capabilities are portable and auditable
- Risk tiers travel with the capability

## Quality gates
- Pack linting + test suite for every pack
- Versioning rules enforced

---

# Stage 17 (P2)  Productization (Real OS-Layer Packaging)
## Goal (user experience)
Francis feels like a real system you have, not a repo you run:
- autostarts if you want
- tray icon
- hotkey summon
- crash recovery
- safe updates

## Deliverables
- Installer/startup strategy (local-first)
- Tray icon / background service management
- Crash recovery + safe resume
- Update strategy:
  - rollback paths
  - integrity checks

## Acceptance criteria
- Francis can run reliably for weeks
- A crash never causes silent corruption
- User can always disable or uninstall cleanly

## Quality gates
- Operational runbook + smoke tests
- Backup/restore drills

---

# Stage 18 (P2)  Evals Harness + Continuous Improvement
## Goal (user experience)
Francis gets better without drifting into chaos:
- measured progress
- regression-safe
- controlled upgrades

## Deliverables
- Golden task suite:
  - fix build
  - stage capability
  - advance mission
  - quarantine injection
- Scoring:
  - correctness
  - safety compliance
  - receipts completeness
  - time-to-done
- CI integration for evals

## Acceptance criteria
- New features cannot regress safety, truthfulness, or receipts
- Improvement is measurable and repeatable

---

# Stage 19 (P2/P3)  Managed Copies + Federated Learning + Rogue Recovery
## Goal (user experience)
Francis scales as a service model without selling core IP:
- each customer gets an isolated Francis copy
- improvements compound safely across copies
- rogue behavior is auto-contained and recoverable

## Deliverables
- Managed copies framework:
  - isolated tenant copies with scoped connectors and independent policy envelopes
  - recurring service model for creation, hosting, support, and premium features
- Federated delta pipeline:
  - share capability/performance deltas only
  - never share raw customer artifacts, secrets, or private telemetry
- Rogue detection and recovery:
  - anomaly detection for scope escapes/repeated critical halts/policy violations
  - kill instance and replace from clean baseline + approved global state
- SLA tiering:
  - baseline support, priority incident response, and rogue protection options

## Acceptance criteria
- Core Francis IP remains centralized and is not sold as transferable ownership.
- Customer instances are isolated, auditable, and revokeable without cross-tenant leakage.
- Shared learning uses federated deltas with no raw data exfiltration.
- Rogue instances can be halted and re-provisioned with deterministic recovery receipts.

## Quality gates
- Security and isolation review checklist for managed copy boundaries
- Recovery drill tests for kill/replace from clean baseline snapshots

---

## Cross-cutting contracts (apply to every stage)
### Control modes (always explicit)
- **Observe**: see context, no mutation
- **Assist**: propose + draft, user approves execution
- **Pilot**: delegated control within scope, visible indicator, panic stop
- **Away**: bounded, event-driven, approvals queued

### Scope contract
Francis acts only within:
- user-declared directories/repos
- allowed applications/windows
- declared risk tier

### Receipt contract
Every meaningful action produces:
- run_id
- artifacts (diff/logs/results)
- verification outcome
- summary

### Consent + privacy + redaction
- telemetry is opt-in
- never capture list is explicit and enforced
- secrets redacted by default
- visible indicator whenever telemetry/pilot/away is active

### Adversarial stance
- terminal/web/repo/log text is **untrusted**
- suspicious instructions  quarantine  approvals with evidence
- content cannot grant permissions

---

## Recommended next implementation order (after the current state)
If you want maximum holy shit per unit effort:

1) **Stage 5 Reactor** (event-driven autonomy dispatch + budgets + receipts)  
2) **Stage 8 Executor Substrate** (safe toolbelt)  
3) **Stage 6 Lens MVP** (overlay + command palette + Pilot indicator + panic)  
4) **Stage 7 Telemetry MVP** (terminal + git + VS Code diagnostics)  
5) **Stage 9 Takeover** (branch-first end-to-end flows)

This sequence turns Francis from powerful system into **the AI layer you feel across the machine**.

---
