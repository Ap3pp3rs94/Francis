# Francis 2.0 - ORB Build Manifest (Phase 2)

> Authoritative scope: this manifest is the human-readable control plane for Francis Phase 2.
>
> Canonical model: Francis is built around the ORB plane model defined in
> `docs/PLANES.md` and `meta/plane_map.yaml`.
>
> Legacy cone/layer language is retained only as a translation aid. It is no longer
> the primary build axis.

---

## 0. Document Contract

### 0.1 What this file is

This manifest is the authoritative implementation schedule and quality-gate
definition for Francis, expressed in ORB terms.

It exists to prevent:

- scaffold drift
- hidden authority leaps between planes
- UI polish landing on top of missing runtime guarantees
- "AI behavior" being shipped without explainable gates, traces, or recovery paths

### 0.2 What this file is not

- Not a replacement for architecture docs. Read `docs/PLANES.md` and
  `meta/plane_map.yaml` first.
- Not a CI file.
- Not a wishlist.
- Not permission to skip plane boundaries because a feature "already works locally."

### 0.3 How this manifest should be updated

Update this document only when one of the following is true:

- a plane gate materially changes
- a milestone is genuinely reached
- the canonical build order changes
- a priority workstream is closed or re-sequenced

Implementation can remain file-by-file, but completion is tracked by plane readiness
and transition enforcement, not by folder churn.

---

## 1. ORB Canon

### 1.1 What ORB means in this repository

In Francis, ORB is the plane-governed operating model:

- work happens inside explicit planes
- cross-plane transitions are structured, policy-checked, and audited
- proposal is never execution
- authority is granted by governance and identity, not by model confidence
- the operator must be able to see the current plane, the active gate, and the next
  allowed transition

If the UI cannot explain where a request is in the ORB and why it is blocked, the
system is not done no matter how much backend machinery exists.

### 1.2 Authoritative ORB sources

The ORB is defined by:

- `docs/PLANES.md` for plane responsibilities and invariants
- `meta/plane_map.yaml` for canonical planes, transitions, forbidden transitions,
  and validation invariants

This manifest translates those sources into:

- build order
- milestone gates
- acceptance criteria
- priority workstreams

### 1.3 Non-negotiables

1. Determinism
   - cold start plus identical config and state should produce materially identical
     runtime behavior
2. Observability before autonomy
   - side effects must be inspectable before they are scaled up
3. Policy before power
   - no execution path may outrun governance, identity, and approval requirements
4. Evidence is untrusted until re-derived
   - web content, imported content, and model output are inputs to reasoning, not
     executable authority
5. No secrets in interface or telemetry
   - only references, hashes, and redacted hints cross outward-facing boundaries
6. ORB visibility is a product requirement
   - Francis must expose plane, gate, and trace state in operator-facing surfaces

---

## 2. Current Build Posture

Francis is no longer a blank scaffold. It is a partial ORB runtime with a stronger
control spine than product surface.

### 2.1 Plane readiness snapshot

- `P0_FOUNDATION`: partial
  - runtime bootstrapping, settings surfaces, and baseline service startup exist, but
    the build contract still needed ORB alignment
- `P1_INTERFACE`: partial
  - API and chat UI exist, but the operator experience is not yet a complete ORB
    console
- `P2_IDENTITY`: partial
  - credential and delegation surfaces exist, but identity enforcement is not yet the
    unmistakable source of truth across every privileged route
- `P3_GOVERNANCE`: materially real
  - approvals, trust artifacts, policy surfaces, and audit expectations exist; recent
    hardening removed obvious approval bypass behavior
- `P4_COGNITION`: partial
  - planning/orchestration structures exist, but not every user journey is clearly
    routed through a visible plan-to-gate-to-execution loop
- `P5_EVIDENCE`: early
  - policy and evidence concepts exist, but the evidence workflow is not yet a
    product-grade differentiator
- `P6_SIMULATION`: early
  - routes and artifacts exist, but this is not yet a trusted production surface
- `P7_EXECUTION`: partial
  - supervised and tool execution paths exist; the remaining gap is broader
    authorization consistency, artifacting, and explanation
- `P8_MEMORY`: partial
  - continuity and snapshot concepts exist; memory still needs a stronger retrieval
    and operator-facing story
- `P9_OBSERVABILITY`: strongest plane today
  - logging, audit, metrics, tracing, and state visibility are among the most real
    parts of the system
- `P10_FEDERATION`: roadmap-stage
  - important to the vision, but not yet close to core-runtime readiness

### 2.2 What that means

The build is closest to a governed runtime kernel, not yet a polished operator
product.

The main risk is not "there is no architecture." The main risk is that higher-level
surfaces could outrun ORB clarity and server-side enforcement. The next work must make
the existing planes coherent, visible, and end-to-end functional before adding more
surface area.

---

## 3. Canonical ORB Order

### 3.1 Runtime request flow

The canonical request lifecycle remains:

`P1_INTERFACE -> P4_COGNITION -> P5_EVIDENCE/P6_SIMULATION (optional) -> P3_GOVERNANCE -> P2_IDENTITY -> P7_EXECUTION -> P9_OBSERVABILITY -> P8_MEMORY -> P1_INTERFACE`

`P10_FEDERATION` is downstream and optional. It must never bypass the same gates.

Code-born capability ingestion follows the same law. A local repository may enter
as `P5_EVIDENCE`/provenance through the ingest source registry and produce
capability candidates, but any build, test, run, package, or rewrite attempt must
cross `P3_GOVERNANCE` and `P2_IDENTITY` before `P7_EXECUTION`. Until a governed
Francis Lab exists, Francis may create a pending exact-action approval request,
preflight approval consumption against an exact action hash, and project a runner
contract, runner-readiness controls, a runner-binding/execution-receipt sink
contract checklist, a runner-enforcement checklist, and an approval-consumption
handoff contract, an execution-receipt sink reservation, and a runner command
allowlist binding, a runner command allowlist declaration, and a runner command
allowlist enforcement preflight, a runner sandbox readiness preflight, an
execution receipt write readiness preflight, and an execution receipt prewrite
binding preflight, and an execution receipt writer preflight, plus
source-mount readiness records, source-mount contract records, sandbox provider
contract records, sandbox provider binding preflights, sandbox provider
selection preflights, sandbox provider verifier preflights with static
identity/policy evidence, sandbox provider runtime-probe preflights that declare
future probe authorization, timeout, network-blocking, workspace-isolation,
receipt, and repository-execution separation controls without probing providers,
runtime-probe harness preflights that declare future probe runner, sandbox,
service-query guard, output capture, and kill-switch controls without binding or
running a provider, sandbox provider runtime-probe runner readiness records that
declare the missing future runner implementation, identity, policy, sandbox,
network-block, workspace-isolation, timeout, output-capture, kill-switch, and
receipt-contract controls without launching a process, querying services, or
running a provider, sandbox provider runtime-probe runner binding preflights
that declare the future probe-runner binding contract and missing live runner,
runtime-probe binding, sandbox, network, timeout, output-capture, kill-switch,
and receipt controls without launching a process, querying services, writing
execution receipts, or running a provider, sandbox provider runtime-probe
runner enforcement preflights that declare the future probe-runner enforcement
contract and missing live enforcement, runner binding, runtime-probe binding,
provider runtime probe, sandbox, network, timeout, output-capture, kill-switch,
and receipt controls without enforcing a runner, launching a process, querying
services, writing execution receipts, or running a provider,
and run-boundary preflights that aggregate those Lab control records, including
runtime-probe harness and runtime-probe runner enforcement evidence, without
binding or running a provider, and sandbox provider runtime-probe execution
boundaries that declare the future provider-probe execution gate without
probing, launching, consuming approval, or writing execution receipts, and
sandbox provider runtime-probe refusals that write receipts when probe
execution is requested too early, and sandbox provider runtime-probe approval
requests that queue pending exact-action approval without consuming approval or
probing providers, and sandbox provider runtime-probe approval-consumption
records that consume approved provider-probe approvals once without probing
providers, launching processes/containers, writing execution receipts, or
executing repository code, and sandbox provider runtime-probe invocation
boundaries that bind consumed provider-probe approval evidence to the remaining
future runner policy, sandbox, network, timeout, output-capture, kill-switch, and
execution receipt writer controls without invoking a provider, and sandbox
provider runtime-probe runner pre-execution boundaries that bind the invocation
boundary to still-missing live runner identity, policy, sandbox, network,
timeout, output-capture, kill-switch, and execution receipt writer controls
without launching or probing a provider, and sandbox provider runtime-probe
runner control bindings that record those future controls as governance evidence
while live runner, sandbox, provider, and execution bindings remain false, and
sandboxed rebuild/run/test boundaries that record the future governed execution
boundary while separate execution approval, live runner, sandbox, network,
output, receipt, build, test, validation, and promotion controls remain missing,
and sandboxed rebuild/run/test approval-request records that queue pending
exact-action operator approval for future governed repository execution without
consuming approval or running install/build/test commands, and sandboxed
rebuild/run/test approval-consumption records that consume approved exact-action
sandboxed rebuild/run/test approvals once as governance evidence without live
runner binding, sandbox enforcement, command execution, install/build/test
execution, network access, repo writes, execution receipt writing, validation,
promotion, or execution authority, and sandboxed rebuild/run/test runner-binding
preflights that record static local provider reference and policy-manifest
metadata after approval consumption while live runner binding, sandbox
enforcement, provider execution, provider service queries, command execution,
execution receipt writing, validation, promotion, and execution authority remain
blocked, and sandboxed rebuild/run/test sandbox-policy preflights that record
default-deny network, read-only source-reference, no repo-write, no destructive
action, no secret storage, command execution disabled, and missing live sandbox,
command allowlist, and execution receipt writer controls after runner-binding
evidence. It may also
prewrite/finalize synthetic no-op execution receipts with all execution flags
false, and consume exact-action approvals only for finalized synthetic no-op
receipts to block approval reuse without granting execution authority, and
complete built-in no-op runner envelopes without repository commands, and record
built-in no-op runner transcripts with deterministic empty stdout/stderr
metadata without real process output capture, and bind only the Francis-owned
built-in no-op runner identity without live runner or sandbox runner binding. API clients and the
operator UI may read source/candidate/Lab proof state through permission-gated
readback routes, but the correct execution result is still a receipted refusal,
not a hidden shell call.

### 3.2 Build completion order

The canonical build order is not the same as the runtime request flow. To make
Francis safe and real, the implementation sequence is:

1. `P0_FOUNDATION`
2. `P9_OBSERVABILITY`
3. `P3_GOVERNANCE`
4. `P2_IDENTITY`
5. `P4_COGNITION`
6. `P7_EXECUTION`
7. `P8_MEMORY`
8. `P1_INTERFACE`
9. `P5_EVIDENCE`
10. `P6_SIMULATION`
11. `P10_FEDERATION`

Rationale:

- Foundation exists first so the system can fail closed.
- Observability comes before "smartness" so every later plane is inspectable.
- Governance and identity come before execution so authority is explicit.
- Cognition exists to produce proposals, not direct power.
- Execution only becomes product-worthy once it is fully governed and explainable.
- Memory must be real before the UI claims continuity.
- Interface polish comes after the core loop is trustworthy, but interface ingress
  still exists from the start.
- Evidence, simulation, and federation are differentiators only after the core ORB is
  stable.

### 3.3 Legacy translation map

If older docs or discussions still use layer language, translate them like this:

- Foundation and kernel -> `P0_FOUNDATION`, parts of `P2_IDENTITY`, parts of
  `P9_OBSERVABILITY`
- Memory -> `P8_MEMORY`
- Governance -> `P3_GOVERNANCE`
- LLM and planning -> `P4_COGNITION`
- Web and research -> `P5_EVIDENCE`
- Chat and operator console -> `P1_INTERFACE`
- Plugins and tool side effects -> `P7_EXECUTION`
- Industrial and digital twin systems -> `P6_SIMULATION`
- Federation and shared knowledge -> `P10_FEDERATION`

The translation is for orientation only. Roadmap decisions should be made in plane
terms.

### 3.4 Phase 2 compute substrate amendment

Francis Compute Substrate is a core expanding architecture layer under the existing
Phase 2 `P7_EXECUTION` direction. It does not replace the Sandboxed Executor
doctrine; it gives future compute workers a narrow place to attach while preserving
ORB law.

Future VSC-1, Unreal, desktop Lens, avatar, VM/container, remote worker, and
simulation systems must attach as adapters to this substrate, not become the
substrate themselves.

The grounded thesis is that Francis should improve useful work per watt through
local-first processing, resource-aware scheduling, sandboxing, simulation, reusable
capabilities, persistent memory, model/tool routing, and receipts-backed execution.
This is not a claim that virtual compute creates free compute or that Francis has
solved data-center scaling.

First-slice substrate work must stay internal until its policy, budget, receipt,
timeout, filesystem, network, memory, and worker boundaries are reviewable. An API,
visual engine, virtual PC, avatar, desktop Lens bridge, remote worker, or simulator
may only bind after it can satisfy those substrate adapter obligations.

---

## 4. ORB Milestones

### M1. ORB Core

Francis reaches ORB Core when:

- forbidden transitions are enforced server-side
- approvals are bound to the exact authorized action
- identity and scope checks are part of every privileged path
- every side effect emits a trace and audit record
- the system can explain why an action was denied

This milestone is about making the ORB real in code rather than rhetorical in docs.

### M2. Functional Francis

Francis becomes functionally usable when one complete operator request can:

- enter through `P1_INTERFACE`
- produce a visible plan in `P4_COGNITION`
- request and satisfy gates in `P3_GOVERNANCE` and `P2_IDENTITY`
- execute in `P7_EXECUTION`
- return a result plus trace through `P9_OBSERVABILITY`
- update continuity through `P8_MEMORY`

This is the first milestone where Francis is a working governed agent rather than a
well-instrumented shell.

### M3. User-Friendly Francis

Francis becomes user-friendly when the operator no longer has to infer the ORB from
logs or source code.

Required outcomes:

- the UI shows the active plane for a request
- blocked work shows the exact gate, policy, or approval that is waiting
- approvals are understandable and scoped to the concrete action
- tool traces and artifacts are discoverable without terminal spelunking
- errors include recovery guidance instead of opaque stack traces
- continuity and backlog state are visible and trustworthy

The ORB should be visible as the product, not hidden as internal architecture.

### M4. Differentiated Francis

Francis becomes distinct from a generic agent shell when:

- `P5_EVIDENCE` produces provenance-rich evidence packs
- `P6_SIMULATION` can validate high-risk plans before execution
- `P10_FEDERATION` shares sanitized knowledge under trust and policy gates
- code-born ingest can map local repositories into source records, repo maps,
  risk signals, lab plans, exact-action approval requests, approval-consumption
  preflights, runner contracts, runner-readiness control checklists,
  runner-binding/execution-receipt sink contract checklists,
  runner-enforcement checklists, approval-consumption handoff contracts,
  execution-receipt sink reservations, execution receipt write readiness
  preflights, execution receipt prewrite binding contracts, execution receipt
  writer preflights, synthetic no-op execution receipts, synthetic no-op
  approval-consumption records, built-in no-op runner envelopes, built-in no-op
  runner transcripts, built-in no-op runner identity bindings, runner command
  allowlist bindings, runner command allowlist declarations, runner command
  allowlist enforcement preflights, runner sandbox readiness preflights,
  source-mount readiness records, source-mount contract records, sandbox
  provider contract records, sandbox provider binding preflights, sandbox
  provider selection preflights, sandbox provider verifier preflights with
  static identity/policy evidence, sandbox provider runtime-probe preflights
  with future probe authorization, timeout, network-blocking,
  workspace-isolation, receipt, and repository-execution separation controls,
runtime-probe harness preflights with future probe runner, sandbox,
service-query guard, output capture, and kill-switch controls, sandbox provider
runtime-probe runner readiness records with future runner implementation,
identity, policy, sandbox, network-block, workspace-isolation, timeout,
output-capture, kill-switch, and receipt-contract controls, sandbox provider
runtime-probe runner binding preflights with future runner/runtime-probe
binding, sandbox, network, timeout, output-capture, kill-switch, and receipt
controls, sandbox provider runtime-probe runner enforcement preflights with
future runner enforcement, live runner/runtime-probe binding, provider runtime
probe, sandbox, network, timeout, output-capture, kill-switch, and receipt
controls,
run-boundary preflights that include runtime-probe harness and runtime-probe
runner enforcement evidence, sandboxed rebuild/run/test approval-consumption
records, and
capability candidates without granting execution authority
- the operator UI can inspect code-born source, risk, candidate, and Lab-boundary
  readback without creating receipts, consuming approvals, or running repo code
- the UI lets the operator inspect cross-plane reasoning, gating, and outcomes as a
  first-class experience

This milestone is where the ORB becomes the recognizable differentiator.

---

## 5. Priority Workstreams

### Workstream A. Close the server-side ORB contract

Goal: make forbidden transitions impossible in code, not just disallowed in theory.

Anchor surfaces:

- `src/francis/governance/*`
- `src/francis/api/routes/approvals.py`
- `src/francis/agent/supervised_exec.py`
- `src/francis/credentials/*`
- `src/francis/telemetry/*`

Done when:

- approved requests are cryptographically or structurally bound to the authorized
  payload and scope
- remote or unauthenticated callers cannot decide approvals
- execution paths always carry request identifiers, decision identifiers, and actor
  identity
- audit records are complete enough to reconstruct who authorized what and why

### Workstream B. Make the core loop functional

Goal: make the canonical ORB loop work end to end for real operator tasks.

Anchor surfaces:

- `src/francis/agent/*`
- `src/francis/chat/router.py`
- `src/francis/agent/executor.py`
- `src/francis/world_state/snapshot.py`
- `src/francis/memory/*`

Done when:

- a request can be planned, gated, executed, and persisted without manual patching
- backlog and world state reflect real queued work
- results and failures flow back through a stable operator-facing contract
- continuity updates are visible and do not silently drop context

### Workstream C. Make the ORB user-friendly

Goal: turn the existing backend planes into an operator console that explains itself.

Anchor surfaces:

- `apps/chat_ui/src/App.tsx`
- `apps/chat_ui/src/chat/*`
- `apps/chat_ui/src/approvals/*`
- `apps/chat_ui/src/credential_manager/*`
- `apps/chat_ui/src/explanation_explorer/*`
- `apps/chat_ui/src/ingest/*`
- `apps/chat_ui/src/trust_dashboard/*`

Done when:

- the UI shows plane, gate, approval state, and execution result as one coherent flow
- reconnect, retry, and pending-work states are visible
- trust and approval decisions are explained in plain language
- artifacts, traces, and ledger entries are reachable from the active conversation

### Workstream D. Build the differentiators on top of the stable core

Goal: add the features that make Francis distinct only after the ORB core is stable.

Anchor surfaces:

- `src/francis/internet/*`
- `src/francis/explanation/*`
- `src/francis/api/routes/simulation.py`
- `src/francis/api/routes/industrial.py`
- `src/francis/collective/federation/*`
- `src/francis/collective/knowledge_sharing/*`

Done when:

- evidence is provenance-rich and injection-safe
- simulation can validate plans before they are allowed to execute
- federation shares only sanitized, policy-approved knowledge
- none of these capabilities open a shortcut around governance or observability

---

## 6. Cross-Plane Gates

These gates are always on. A feature is not done if it weakens them.

### 6.1 Transition gates

- no `P1_INTERFACE -> P7_EXECUTION`
- no `P5_EVIDENCE -> P7_EXECUTION`
- no `P10_FEDERATION -> P7_EXECUTION`
- no privileged action without `P3_GOVERNANCE` plus `P2_IDENTITY`

### 6.2 Data gates

- no secrets in UI payloads
- no secrets in audit or metrics
- no memory write without provenance or retention alignment
- no raw untrusted external content treated as executable authority

### 6.3 UX gates

- every operator-visible action must map to a plane
- every blocked action must explain the active gate
- every completed side effect must expose a trace or artifact handle
- every important failure must be recoverable without source diving

---

## 7. Release Readiness

A production-ish release is allowed only if:

- `M1 ORB Core` is complete
- the `M2 Functional Francis` loop works on the primary operator journey
- `P9_OBSERVABILITY` can reconstruct privileged actions and denials
- `P1_INTERFACE` exposes approvals, traces, and recovery paths clearly
- `P5_EVIDENCE`, `P6_SIMULATION`, and `P10_FEDERATION` remain disabled or gated
  unless they have met their own ORB acceptance requirements

If the ORB is invisible to the operator or unenforced on the server, the release is
not ready.

---

## Appendix A. What to read while building

- `docs/PLANES.md`
- `meta/plane_map.yaml`
- `docs/BUILD_ORDER.md`
- `docs/ARCHITECTURE.md`
- `docs/GOVERNANCE.md`
- `docs/TRUST_MODEL.md`
- `docs/MEMORY.md`
- `docs/POLICIES.md`
- `docs/WEB_ACCESS.md`

## Appendix B. Minimal operator workflow

The minimal operator experience must support:

- submit a request
- see the active plane and next gate
- approve or deny the exact action being requested
- inspect the resulting trace, artifact, or denial reason
- view continuity and pending work state
- recover cleanly from reconnects and failures

Everything else is built on top of that loop, not beside it.
