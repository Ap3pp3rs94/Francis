# FRANCIS - Canonical Build Order

This file translates the ORB model into the practical sequence for building Francis.

The authoritative architectural sources are:

- `docs/PLANES.md`
- `meta/plane_map.yaml`
- `docs/canonical/BUILD_MANIFEST.md`

## 1. Rule

Build Francis by completing planes and enforcing transitions, not by filling folders
or shipping isolated UI features.

The ORB is canonical. If a roadmap decision conflicts with plane boundaries, the
plane model wins.

## 2. Runtime flow vs build order

The runtime flow of a request is:

`P1_INTERFACE -> P4_COGNITION -> P3_GOVERNANCE -> P2_IDENTITY -> P7_EXECUTION -> P9_OBSERVABILITY -> P8_MEMORY`

Optional paths:

- `P4_COGNITION -> P5_EVIDENCE -> P4_COGNITION`
- `P4_COGNITION -> P6_SIMULATION -> P4_COGNITION`
- `P5_EVIDENCE/source_ingest -> P3_GOVERNANCE/P2_IDENTITY -> P7_EXECUTION`
  only after a governed lab plan is approved; otherwise the flow ends in a
  receipt-backed refusal
- `P8_MEMORY <-> P10_FEDERATION`

The build order is different because the control spine must exist before the product
surface is trusted:

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

## 3. What "functional" means

Francis is functionally real when a primary operator request can move end to end
through the ORB:

- request captured in `P1_INTERFACE`
- plan produced in `P4_COGNITION`
- gate evaluated in `P3_GOVERNANCE`
- identity and scope confirmed in `P2_IDENTITY`
- authorized action performed in `P7_EXECUTION`
- trace recorded in `P9_OBSERVABILITY`
- continuity updated in `P8_MEMORY`

Anything less is still partial runtime infrastructure.

## 4. What "user-friendly" means

Francis is user-friendly when the operator can understand the ORB without reading
source code.

Required UX outcomes:

- current plane is visible
- blocked work names the missing approval, policy, or trust gate
- approvals are tied to concrete actions
- traces and artifacts are easy to inspect
- backlog and continuity state are trustworthy
- errors are actionable

The ORB should be the visible product shape, not hidden implementation detail.

## 5. Current priority

Near-term work should stay in this order:

1. close server-side governance and identity gaps
2. finish the end-to-end plan -> gate -> execute -> trace -> memory loop
3. expose that loop clearly in the chat UI
4. only then expand evidence, simulation, and federation surfaces

Code-born capability ingestion is an evidence/provenance feeder in this order,
not a shortcut to execution. Local repos can be indexed and mapped before the
full lab exists, and exact-action lab approval requests may be queued at the
governance gate. Approval ids may be preflighted against exact action hashes,
runner contracts and runner-readiness control checklists may be projected, and
runner-binding/execution-receipt sink contract checklists may be projected, and
runner-enforcement checklists may verify missing controls. Approval-consumption
handoffs may bind approved exact-action evidence to runner-enforcement readback,
execution-receipt sink reservations may reserve future receipt ids/paths, and
runner command allowlist bindings may project exact-action command plans, and
runner command allowlist declarations may derive deterministic command entries,
and runner command allowlist enforcement preflights may check declared entries
against missing live runner/allowlist controls, and runner sandbox readiness
preflights may check workspace evidence against missing sandbox controls, and
sandbox provider contracts may declare the future provider boundary and missing
provider enforcement controls without binding a provider, and sandbox provider
binding preflights may declare the future provider-selection/binding checklist
without selecting, verifying, or binding a provider, and
execution receipt write readiness preflights may check reserved receipt
prewrite/final-write controls, and execution receipt prewrite binding
preflights may bind future `lab.execution.run` schema/prewrite/final-write
contracts, and execution receipt writer preflights may declare reserved sink
path, atomic write, and redaction controls, and synthetic execution receipt
writes may prewrite/finalize only no-op receipts with execution flags false, and
synthetic no-op approval-consumption records may enforce single-use reuse
blocking after finalized no-op receipts, and built-in no-op runner envelopes may
complete a Francis-owned no-op handoff without repository commands, and built-in
no-op runner transcripts may record deterministic empty stdout/stderr metadata
without real process output capture, and built-in no-op runner identity bindings
may bind only the Francis-owned no-op runner identity without live runner or
sandbox runner binding, and source-mount readiness records may confirm the
workspace source reference is read-only without binding or enforcing a live
source mount, and source-mount contract records may declare the future
read-only mount contract without binding or enforcing a live source mount, and
run-boundary preflights may aggregate the missing mount, sandbox provider,
sandbox binding, sandbox provider selection, sandbox provider verifier,
sandbox provider runtime-probe preflight, sandbox provider runtime-probe
harness preflight, runtime-probe runner enforcement preflight, sandbox
enforcement, allowlist, receipt-writer, and approval-consumption controls
without executing, and
sandbox provider verifier evidence remains static identity/policy evidence while
runtime-probe preflights declare future authorization, timeout,
network-blocking, workspace-isolation, receipt, and repository-execution
separation controls without probing providers, and runtime-probe harness
preflights declare the missing future probe runner, sandbox, service-query
guard, output capture, and kill-switch controls without binding or running a
provider, and runtime-probe runner readiness records declare the missing future
runner implementation, identity, policy, sandbox, network-block,
workspace-isolation, timeout, output-capture, kill-switch, and receipt-contract
controls without binding a runner, launching a process, querying a service, or
running a provider, and runtime-probe runner binding preflights declare the
future binding contract and missing live runner/runtime-probe controls without
binding a runner, launching a process, querying a service, writing execution
receipts, or running a provider, and runtime-probe runner enforcement
preflights declare the future enforcement contract and missing live enforcement,
runner binding, runtime-probe binding, and provider runtime probe controls
without enforcing a runner, launching a process, querying a service, writing
execution receipts, or running a provider, and runtime-probe execution-boundary
records declare the future provider-probe execution gate while provider
probing, provider binary execution, provider service queries, process/container
launch, approval consumption, execution receipt writes, and repository
execution remain blocked, and runtime-probe refusal records may write receipts
when a provider probe is requested before governed probe execution exists, and
runtime-probe approval-request records may queue a pending exact-action approval
for future provider probing without consuming approval or probing providers, and
runtime-probe approval-consumption records may consume an approved provider-probe
approval once without probing providers, executing binaries, launching
processes/containers, writing execution receipts, or executing repository code,
and runtime-probe invocation-boundary records may bind consumed provider-probe
approval evidence to missing future runner, policy, sandbox, network, timeout,
output-capture, kill-switch, and receipt-writer controls without invoking a
provider, and runtime-probe runner pre-execution-boundary records may bind the
invocation boundary to still-missing live runner identity, policy, sandbox,
network, timeout, output-capture, kill-switch, and receipt-writer controls
without launching or probing a provider, and runtime-probe runner
control-binding records may record those future controls as governance evidence
while live runner, sandbox, provider, and execution bindings remain false
without launching or probing a provider, and sandboxed rebuild/run/test boundary
records may record the future governed execution boundary while separate
execution approval, live runner, sandbox, network, output, receipt, build, test,
validation, and promotion controls remain missing, and sandboxed rebuild/run/test
approval-request records may queue a pending exact-action operator approval for
future governed repository execution without consuming approval or running
install/build/test commands, and sandboxed rebuild/run/test approval-consumption
records may consume that approved exact-action approval once as governance
evidence without live runner binding, sandbox enforcement, command execution,
install/build/test execution, network access, repo writes, execution receipt
writing, validation, promotion, or execution authority, and sandboxed
rebuild/run/test runner-binding preflights may record static local provider
reference and policy-manifest metadata after approval consumption while live
runner binding, sandbox enforcement, provider execution, provider service
queries, command execution, execution receipt writing, validation, promotion,
and execution authority remain missing, and sandboxed rebuild/run/test
sandbox-policy preflights may record default-deny network, read-only source
reference, no repo write, no destructive action, no secret storage, disabled
command execution, and missing live sandbox/allowlist/receipt-writer controls
after runner-binding evidence, but
permission-gated API/UI readbacks may only expose source/candidate/Lab proof
state. Unknown repo commands still stay blocked until the plan -> gate -> lab ->
trace path is real.

## 6. Local run commands

1. Optional services:
   `docker compose -f infra/docker/compose.yaml up -d`

2. Python:
   `uv venv`
   `uv pip install -e .`
   `python -m francis api`
   `python -m francis daemon`

3. UI:
   `cd apps/chat_ui`
   `npm install`
   `npm run dev`
