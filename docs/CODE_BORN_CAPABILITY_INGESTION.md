# Code-Born Capability Ingestion v0

## Roadmap Fit

Code-born capability ingestion supports the Phase 2 governed runtime spine by
feeding Stage 4 Forge and Stage 17 Capability Economy without granting execution
authority. It also aligns with the roadmap supply-chain requirement that imported
capability preserve provenance, reviewability, quarantine, and revocation paths.

## Purpose

Francis treats repositories as executable human knowledge: source code, build
systems, tests, docs, examples, scripts, manifests, and design patterns. v0 makes
that knowledge inspectable as local records and receipts. It does not rebuild,
install, run, test, publish, or promote unknown repository code.

## Local Layout

Runtime state is resolved through `FRANCIS_DATA_DIR` via `francis.kernel.paths.data_dir()`.
The ingest subsystem creates:

```text
data/
  ingest/
    incoming/
    processing/
    indexed/
    studied/
    needs-permission/
    failed/
    archived/
    _source_registry.json
    _capability_registry.json
  artifacts/
    ingest/
      repo_maps/
      capabilities/
      lab_plans/
      lab_workspaces/
      lab_preflights/
      lab_approval_requests/
      lab_approval_consumption_preflights/
      lab_approval_consumptions/
      lab_noop_runner_envelopes/
      lab_noop_runner_identity_bindings/
      lab_noop_runner_transcripts/
      lab_source_mount_readiness/
      lab_source_mount_contracts/
      lab_run_boundary_preflights/
      lab_sandbox_provider_contracts/
      lab_sandbox_provider_bindings/
      lab_sandbox_provider_selections/
      lab_sandbox_provider_verifier_preflights/
      lab_sandbox_provider_runtime_probe_preflights/
      lab_runtime_probe_harness_preflights/
      lab_runtime_probe_runner_readiness/
      lab_runtime_probe_runner_bindings/
      lab_runtime_probe_runner_enforcements/
      lab_runtime_probe_execution_boundaries/
      lab_runtime_probe_refusals/
      lab_runtime_probe_approval_requests/
      lab_runtime_probe_approval_consumptions/
      lab_runtime_probe_invocation_boundaries/
      lab_runtime_probe_preexec_boundaries/
      lab_runtime_probe_control_bindings/
      lab_sandboxed_rebuild_run_test_boundaries/
      lab_sandboxed_rebuild_run_test_approval_requests/
      lab_sandboxed_rebuild_run_test_approval_consumptions/
      lab_sandboxed_rebuild_run_test_runner_bindings/
      lab_sandboxed_rebuild_run_test_sandbox_policies/
      lab_execution_receipts/
      lab_runner_bindings/
      lab_runner_contracts/
      lab_runner_enforcement_preflights/
      lab_runner_readiness/
      lab_refusals/
      receipts/
```

The source registry records source identity, local path, fingerprint, conservative
permissions, metadata, derived artifacts, and receipts. The capability registry
stores drafted candidate records derived from source inspection.

## Source Registry

Each source record stores:

- `id`
- `type`: `file`, `folder`, `repo`, `app`, or `unknown`
- `original_path`
- `canonical_path`
- `created_at`
- `updated_at`
- `fingerprint`
- `status`
- conservative permissions
- metadata
- derived artifacts
- receipts

Default permissions are read-only:

```json
{
  "read": true,
  "execute": false,
  "network": false,
  "write": false,
  "destructive": false
}
```

## Repo Adapter

`RepoAdapter` inspects a local repository read-only and produces a repo map. It
uses repo markers such as `.git`, `package.json`, `pyproject.toml`, `Cargo.toml`,
`go.mod`, lockfiles, `requirements.txt`, README files, and source directories.

The adapter records:

- repo root
- local git metadata when available, using local git commands only
- detected languages and stacks
- package managers
- manifest files
- declared manifest scripts
- test files
- docs and README files
- entrypoints
- config files
- source directories
- dependency manifests
- license files
- risk signals
- suggested validation commands
- protected or sensitive-looking files

Risk detection includes install hooks, shell scripts, Docker/Compose files, CI,
environment files, credential-looking files, deployment scripts, migration paths,
destructive command hints, and network command hints.

## Capability Candidates

The v0 extractor creates descriptive, bounded candidates such as:

- `inspect_project_structure`
- `explain_repo_architecture`
- `run_project_tests`
- `lint_project`
- `build_project`
- `package_project`
- `inspect_container_build`
- `inspect_database_migrations`
- `inspect_cli_entrypoint`

Candidates start as `drafted` or `discovered`. Read-only candidates require only
read permission. Any candidate that would run, build, lint, package, publish, or
write artifacts is marked as requiring explicit permission and future Francis Lab
support.

## Francis Lab Boundary

v0 defines the boundary instead of pretending it exists. Current lab status is:

- unknown-repo execution support: false
- network isolation support: false
- filesystem write isolation support: false
- live readonly source mount enforcement support: false

Before build/run/test phases can be truthful, Francis needs explicit operator
permission, a sandboxed workspace, network blocking policy, filesystem write
boundaries, resource limits, execution receipts, and promotion gates.

The first lab-boundary slice adds plan and refusal records. A lab plan projects a
capability candidate into explicit permissions, suggested commands, required
workspace controls, blockers, and promotion requirements. If the candidate would
execute, build, test, lint, package, access the network, or write files, the plan
is blocked until the governed lab runner exists.

The execution boundary is intentionally a refusal surface. It writes a
`lab.execution.refuse` receipt with `executed: false`, `execution_authority:
false`, no network access, and no repo writes. This proves Francis recognized an
execution request and declined to run it instead of silently treating a plan as
permission.

The workspace boundary can prepare an empty Francis-owned directory with a
manifest under `data/artifacts/ingest/lab_workspaces/`. The workspace records the
source as a read-only reference, creates only controlled empty subdirectories, and
keeps `execution_enabled: false`, `runner_bound: false`, `source_copied: false`,
and `execution_authority: false`.

The execution preflight boundary creates an exact-action payload and stable action
hash for a candidate/workspace pair. It projects the approval gate, approval
scope, readiness blockers, and required runner controls, then stops. The
preflight operation does not create approval records, consume approvals, or treat
a preflight as execution authority.

The approval-request boundary can create a pending exact-action request through
the existing Francis approvals store for `francis.lab.execute`. The request
records the preflight action hash and blocked readiness state, then stops. It
does not approve the request, consume an approval, bind a runner, or grant
execution authority.

The approval-consumption preflight boundary reads an approval id and checks it
against the exact action hash plus source, candidate, plan, preflight, and
workspace identity. It refuses stale or mismatched approvals and can recognize an
approved exact-action record, but v0 still does not consume the approval or bind
a runner. It also writes a runner contract projection that names the controls a
future governed runner must satisfy before execution can become truthful.

The runner-readiness boundary projects the future governed Lab runner controls
against the current workspace, preflight, and optional approval id. It can prove
that the Francis-owned empty workspace manifest exists and that source content was
not copied, but it remains blocked until approval consumption, runner binding,
command allowlisting, environment scrubbing, network isolation, filesystem write
isolation, resource limits, stdout/stderr capture, timeout policy, and execution
receipt sink controls are all real.

The runner-binding boundary projects the future runner binding and execution
receipt sink contracts. It records the runner identity fields, command and
environment binding controls, network/filesystem/resource/timeout policy controls,
stdout/stderr capture controls, and execution-receipt sink schema/write controls
that must exist before imported repository code can run. v0 writes this as a
blocked preflight only: no runner is bound, no receipt sink is bound, no approval
is consumed, and no execution authority is granted.

The runner-enforcement boundary verifies whether the projected runner binding and
execution receipt sink are enforceable. It checks runner identity, declared runner
binary, runner contract load, command allowlist, environment scrubbing, network
policy, filesystem write policy, resource limits, timeout policy, stdout/stderr
capture, receipt sink binding, receipt prewrite/final-write controls, and
approval consumption. v0 records the missing checks and remains blocked; it does
not execute repository code or treat an enforcement preflight as enforcement.

The approval-consumption handoff boundary binds an approval id, exact-action
approval evidence, and runner-enforcement readback into the future consumption
contract. It can recognize an approved exact-action record, but it still remains
blocked until runner enforcement is ready, a live runner and receipt sink are
bound, and a governed approval consumer exists. v0 writes the handoff as
readback-only evidence; it does not consume approvals or grant execution
authority.

The execution-receipt sink reservation boundary reserves the future
`lab.execution.run` receipt id/path that a governed runner would have to prewrite
and finalize. It depends on approval-consumption handoff readback and runner
enforcement state, then records whether sink binding, schema binding, prewrite,
and final-write controls are present. v0 writes only the reservation artifact and
ingest receipt; it does not write an execution receipt, bind a receipt sink, or
execute repository code.

The runner command allowlist binding boundary projects the exact-action command
plan from the execution preflight and binds it to the missing allowlist controls
that a future governed runner must satisfy. It depends on execution-receipt sink
reservation readback, then records whether commands were declared, bound, and
covered by allowlist entries. v0 writes only the binding artifact and ingest
receipt; it does not declare a live allowlist, bind command execution, consume an
approval, write an execution receipt, or execute repository code.

The runner command allowlist declaration boundary creates deterministic
allowlist-entry records from the exact-action command plan. It depends on runner
command allowlist binding readback, then records command ids, hashes, and
declaration status for future binding. v0 writes only the declaration artifact
and ingest receipt; it does not bind the allowlist to a live runner, enable
command execution, consume an approval, write an execution receipt, or execute
repository code.

The runner command allowlist enforcement preflight boundary checks the declared
exact-action allowlist entries against the still-missing live runner controls. It
depends on runner command allowlist declaration readback, then records whether
entries are declared, bound, enforced, and executable. v0 writes only the
enforcement-preflight artifact and ingest receipt; it does not bind a live
runner, bind or enforce a live allowlist, enable command execution, consume an
approval, write an execution receipt, or execute repository code.

The runner sandbox readiness boundary checks the prepared workspace and future
sandbox controls after command allowlist enforcement readback. It can prove the
empty Francis-owned workspace manifest exists and source content was not copied,
then records that sandbox provider binding, runner identity, readonly source
mounting, environment scrubbing, filesystem policy, resource limits, timeout
policy, capture, kill switch, allowlist enforcement, receipt prewrite, and
receipt final-write controls are still missing. v0 writes only the sandbox
readiness artifact and ingest receipt; it does not bind a sandbox, bind a
runner, enforce a live allowlist, consume approval, write an execution receipt,
or execute repository code.

The execution receipt write readiness boundary checks the reserved
`lab.execution.run` receipt id/path after sandbox readiness readback. It can prove
the reserved execution receipt has not been written, then records that receipt
schema binding, prewrite writer binding, and final-write writer binding are still
missing. v0 writes only the receipt-write readiness artifact and ingest receipt;
it does not prewrite or finalize an execution receipt, consume approval, grant
execution authority, or execute repository code.

The execution receipt prewrite binding boundary is the next contract-only step.
It binds a serializable `lab.execution.run` receipt schema plus prewrite and
final-write contracts for the reserved execution receipt id/path. This is still
not a writer implementation: the reserved execution receipt remains absent, the
prewrite/final writer controls remain unbound, approval is not consumed,
execution authority stays false, and no repository command runs.

The sandbox provider runtime-probe preflight boundary declares the future
provider probe contract after static verifier readback. It records authorization,
timeout, network-blocking, workspace-isolation, receipt, and repository-execution
separation requirements. v0 writes this as blocked contract evidence only: no
provider binary is executed, no provider service is queried, no container is
launched, no sandbox provider is bound, no approval is consumed, and no
repository code runs.

The sandbox provider runtime-probe harness preflight boundary declares the future
probe harness controls after runtime-probe contract readback. It records the
missing governed probe runner, sandbox binding, service-query guard,
stdout/stderr output capture, and kill-switch controls. v0 writes this as
blocked contract evidence only: no provider binary is executed, no provider
service is queried, no container is launched, no sandbox provider is bound, no
approval is consumed, no execution receipt is written, and no repository code
runs.

The sandbox provider runtime-probe runner readiness boundary declares the future
probe-runner interface after harness readback. It records the missing runner
implementation, runner identity, runner policy, sandbox binding, network block,
workspace isolation, timeout, output capture, kill switch, and receipt contract
controls. v0 writes this as blocked contract evidence only: no provider binary
is executed, no provider service is queried, no container is launched, no runner
is bound, no approval is consumed, no execution receipt is written, and no
repository code runs.

The sandbox provider runtime-probe runner binding preflight boundary declares
the future binding contract after runner-readiness readback. It records that a
future governed runner binding must prove runner implementation, identity,
policy, sandbox binding, network block, workspace isolation, timeout, output
capture, kill switch, receipt contract, and runtime-probe binding controls
before any provider probe can run. v0 writes this as blocked contract evidence
only: no provider binary is executed, no provider service is queried, no process
or container is launched, no runner is bound, no approval is consumed, no
execution receipt is written, and no repository code runs.

The sandbox provider runtime-probe runner enforcement preflight boundary
declares the future enforcement contract after runner-binding readback. It
records that a future governed probe runner must prove the binding is ready,
live enforcement is bound, the runner and runtime probe are bound, and provider
runtime probing has occurred inside controlled sandbox constraints before any
provider probe result can be trusted. v0 writes this as blocked contract
evidence only: no provider binary is executed, no provider service is queried,
no process or container is launched, no runner is enforced, no approval is
consumed, no execution receipt is written, and no repository code runs.

## Francis Lab v0 Runtime (separate, opt-in, sandboxed execution)

The ingest subsystem above remains strictly non-executing. Francis Lab is a
**separate downstream subsystem** (`src/francis/ingest/lab/lab_runtime.py` plus
`IngestService.run_lab_capability`) that is the first and only place capable of
actually running repository code. It does not modify or relax any ingest rule.

A Lab run is REAL only when **all four** conditions hold:

1. A consumed exact-action `sandboxed_rebuild_run_test` approval exists upstream
   for the same source + candidate (the operator authority handoff).
2. The capability candidate passes the safety gate: non-destructive, no network
   requirement, risk level not `high`, and no blocked risk signal present
   (`destructive_command_hint`, `credential_like_file_present`, install hooks,
   deploy scripts, migrations, network hints).
3. The operator passes explicit `--opt-in` / `opt_in: true`.
4. A live Docker daemon is reachable.

If any condition is missing, the run is **SIMULATED**: a Francis-owned no-op runs
in place of the real command, the receipt is marked `execution_mode: "simulated"`,
and no repository code executes. Today Docker is installed but stopped, so the
default exercised path is simulation.

When real, execution is confined to a locked-down container:
`--network none`, `--read-only` root, `--cap-drop ALL`,
`--security-opt no-new-privileges`, `--pids-limit`, `--memory`, `--cpus`, the
source mounted read-only at `/src`, and the **only** writable surface a
size-limited tmpfs scratch at `/work` (the rebuilder copies the read-only source
into scratch before running detected commands). The pinned base image
(`FRANCIS_LAB_IMAGE`) must already exist locally; the runtime **fails closed to
simulation rather than pulling** over the disabled network. Timeouts are enforced
host-side with a `docker kill` fallback.

Deterministic validation never trusts simulated evidence:

- simulated run → `PARTIAL`
- real run, exit code 0 → `VALID`
- real run, non-zero exit or timeout → `INVALID`

Promotion (`discovered → drafted → runnable → validated → registered`) advances
**at most one rung per run and only on real + `VALID` + no-network evidence**.
Simulated or `INVALID` runs never promote, so a capability can never reach
`validated` without real sandboxed execution that produced a receipt. Advancement
stops at `validated`; `registered` remains a separate governance decision.

Every run writes a `lab.execution.run` receipt plus a
`data/artifacts/ingest/lab_execution_runs/` artifact carrying `lab_run_id`,
`sandbox_id`, `execution_mode`, `commands_run`, container argv, `exit_code`,
stdout/stderr summaries, `validation_status`, promotion result, and the truth
booleans (`executed`, `repo_code_executed`, `network_accessed`, `wrote_to_repo`,
`execution_authority`). These surface in `GET /ingest/readback` and the operator
panel. Surfaces: `francis lab run <src> <candidate> <approval-id> [--opt-in]` and
`POST /ingest/lab/run` (scope `ingest.lab.execute.run`).

## Receipts

Every v0 operation writes compact receipts under `data/artifacts/ingest/receipts/`:

- `source.add`
- `repo.inspect`
- `capability.extract`
- `lab.execution.run` (Francis Lab v0 runtime; simulated by default)
- `lab.plan`
- `lab.workspace.prepare`
- `lab.execution.preflight`
- `lab.execution.approval_request`
- `lab.execution.approval_consumption_preflight`
- `lab.runner.readiness.preflight`
- `lab.runner.binding.preflight`
- `lab.runner.enforcement.preflight`
- `lab.execution.approval_consumption_handoff`
- `lab.execution.receipt_sink_reservation`
- `lab.runner.command_allowlist.binding`
- `lab.runner.command_allowlist.declaration`
- `lab.runner.command_allowlist.enforcement_preflight`
- `lab.runner.sandbox_readiness.preflight`
- `lab.sandbox.provider_runtime_probe.preflight`
- `lab.sandbox.provider_runtime_probe_harness.preflight`
- `lab.sandbox.provider_runtime_probe_runner.readiness`
- `lab.sandbox.provider_runtime_probe_runner.binding_preflight`
- `lab.sandbox.provider_runtime_probe_runner.enforcement_preflight`
- `lab.sandboxed_rebuild_run_test.sandbox_policy`
- `lab.execution.receipt_write_readiness.preflight`
- `lab.execution.refuse`

Receipts record actor, operation, source id, input paths or fingerprints, inspected
file counts, result status, warnings, generated artifacts, and validation performed.
They do not store raw file contents or secrets.

## What v0 Does

- Creates local ingest directories.
- Creates source records for files, folders, and repos.
- Detects repositories from local markers without network access.
- Produces read-only repo maps.
- Extracts conservative capability candidates.
- Records risk signals and sensitive-file presence.
- Creates non-executing Francis Lab plan records for candidate capabilities.
- Prepares empty Francis-owned lab workspaces without copying source files.
- Creates lab execution preflight records with exact-action hashes and approval
  intent, without creating or consuming approval artifacts.
- Creates pending exact-action lab approval requests through the Francis
  approvals queue, without consuming approval artifacts or granting authority.
- Creates approval-consumption preflight records that bind approval id, action
  hash, source, candidate, plan, preflight, and workspace identity.
- Creates blocked runner contract projections for the future governed Lab runner.
- Creates runner-readiness preflight records that enumerate missing sandbox,
  runner, isolation, command, environment, resource, and receipt controls.
- Creates runner-binding preflight records that enumerate missing governed runner
  binding and execution-receipt sink controls.
- Creates runner-enforcement preflight records that verify missing runner,
  policy, capture, approval-consumption, and execution-receipt write controls.
- Creates approval-consumption handoff records that bind approved exact-action
  evidence to runner-enforcement readback while approval consumption remains
  disabled.
- Creates execution-receipt sink reservation records that reserve a future
  execution receipt id/path while prewrite and final-write controls remain
  disabled.
- Creates runner command allowlist binding records that project exact-action
  command plans while command allowlist declaration, binding, and execution
  remain disabled.
- Creates runner command allowlist declaration records that derive deterministic
  allowlist entries from exact-action command plans while live binding and
  execution remain disabled.
- Creates runner command allowlist enforcement preflight records that check
  declared entries against missing live runner, allowlist-binding,
  receipt-prewrite, and receipt-final-write controls while execution remains
  disabled.
- Creates runner sandbox readiness records that check workspace evidence and
  future sandbox controls while sandbox binding and execution remain disabled.
- Creates sandbox provider contract records that declare the future provider
  boundary and required enforcement controls while provider binding, sandbox
  enforcement, runner binding, and execution remain disabled.
- Creates sandbox provider binding preflight records that declare the future
  provider binding checklist while provider selection, provider binary/service
  verification, provider policy manifest binding, sandbox enforcement, and
  execution remain disabled.
- Creates sandbox provider selection preflight records that record requested
  provider kind, local provider reference metadata, and optional provider policy
  manifest metadata while provider binary/service verification, live provider
  binding, sandbox enforcement, and execution remain disabled.
- Creates sandbox provider verifier preflight records that bind the Francis
  static verifier identity, capture provider reference fingerprints, sanitize
  provider policy manifest summaries/hashes, and record declared provider
  version evidence while provider runtime probes, provider binary execution,
  service queries, container launch, live provider binding, sandbox enforcement,
  and repository execution remain disabled.
- Creates sandbox provider runtime-probe preflight records that declare future
  provider probe authorization, timeout, network-blocking, workspace-isolation,
  receipt, and repository-execution separation controls while provider binary
  execution, provider service queries, container launch, live provider binding,
  approval consumption, and repository execution remain disabled.
- Creates sandbox provider runtime-probe harness preflight records that declare
  future provider probe runner, sandbox, service-query guard, output capture,
  and kill-switch controls while provider binary execution, provider service
  queries, container launch, live provider binding, approval consumption,
  execution receipt writing, and repository execution remain disabled.
- Creates sandbox provider runtime-probe runner readiness records that declare
  the future probe-runner interface and missing runner identity, policy,
  sandbox, network-blocking, workspace-isolation, timeout, output-capture,
  kill-switch, and receipt controls while provider binary execution, provider
  service queries, container launch, live provider binding, approval
  consumption, execution receipt writing, and repository execution remain
  disabled.
- Creates sandbox provider runtime-probe runner binding preflight records that
  declare the future probe-runner binding contract and missing live runner,
  runtime-probe binding, sandbox, network, timeout, output-capture, kill-switch,
  and receipt controls while provider binary execution, provider service
  queries, process/container launch, live provider binding, approval
  consumption, execution receipt writing, and repository execution remain
  disabled.
- Creates sandbox provider runtime-probe runner enforcement preflight records
  that declare the future runner-enforcement contract and missing live
  enforcement, runner binding, runtime-probe binding, provider runtime probe,
  sandbox, network, timeout, output-capture, kill-switch, and receipt controls
  while provider binary execution, provider service queries, process/container
  launch, live provider binding, approval consumption, execution receipt
  writing, and repository execution remain disabled.
- Creates execution receipt write readiness records that check the reserved
  execution receipt id/path and future prewrite/final-write controls while
  execution receipt writing remains disabled.
- Creates execution receipt prewrite binding records that bind the future
  `lab.execution.run` receipt schema plus prewrite/final-write contracts while
  writer implementations and execution receipt writes remain disabled.
- Creates execution receipt writer preflight records that declare the future
  writer boundary, atomic write plan, reserved sink path checks, and redaction
  policy while the writer implementation and execution receipt writes remain
  disabled.
- Creates run-boundary preflight records that aggregate source-mount contract,
  sandbox readiness, sandbox provider contract, sandbox provider binding,
  sandbox provider selection, sandbox provider verifier, sandbox provider
  runtime-probe preflight, sandbox provider runtime-probe harness preflight,
  sandbox provider runtime-probe runner enforcement preflight, command allowlist
  enforcement, execution receipt writer, and approval-handoff evidence into one
  blocked future run boundary while live runner enforcement, provider runtime
  probing, and repository execution remain disabled.
- Creates sandbox provider runtime-probe execution-boundary records that compose
  the run-boundary readback and declare the future provider probe execution gate
  while provider probing, provider binary execution, provider service queries,
  process/container launch, approval consumption, execution receipt writes, and
  repository execution remain disabled.
- Refuses sandbox provider runtime-probe requests with receipts until governed
  provider-probe execution exists. Refusal records depend on the execution
  boundary and keep provider probing, provider binary execution, service
  queries, process/container launch, approval consumption, execution receipt
  writes, and repository execution disabled.
- Creates sandbox provider runtime-probe approval-request records that queue a
  pending exact-action approval for future provider probing after execution
  boundary readback. These records do not consume approvals, probe providers,
  execute provider binaries, query services, launch processes/containers, write
  execution receipts, or execute repository code.
- Creates sandbox provider runtime-probe approval-consumption records that
  consume an approved exact-action provider-probe approval once while still
  blocking provider probing, provider binary execution, service queries,
  process/container launch, execution receipt writes, and repository execution.
- Creates sandbox provider runtime-probe invocation-boundary records that bind
  consumed provider-probe approval evidence to the execution-boundary record and
  enumerate the remaining future runner controls: policy, sandbox, network
  block, workspace isolation, timeout, output capture, kill switch, and
  execution receipt writer. These records still do not probe providers, execute
  binaries, query services, launch processes/containers, write execution
  receipts, or execute repository code.
- Creates sandbox provider runtime-probe runner pre-execution-boundary records
  that bind the recorded invocation boundary to the next future runner-control
  requirements: runner identity, runner policy, sandbox policy, live sandbox
  binding/enforcement, network block, timeout, output capture, kill switch, and
  execution receipt writer. These records still do not probe providers, execute
  binaries, query services, launch processes/containers, bind a live runner or
  sandbox, write execution receipts, or execute repository code.
- Creates sandbox provider runtime-probe runner control-binding records that
  record the future runner identity, runner policy, sandbox policy, network
  block, timeout, output capture, kill switch, and execution receipt writer
  bindings as governance evidence while keeping live runner, sandbox, provider,
  and execution bindings false. These records still do not probe providers,
  execute binaries, query services, launch processes/containers, bind or enforce
  a live runner or sandbox, write execution receipts, or execute repository
  code.
- Creates sandboxed rebuild/run/test boundary records that depend on the
  provider runtime-probe runner control-binding evidence and record the future
  install/build/run/test/validate boundary while requiring a separate future
  execution approval and live runner/sandbox/network/output/kill-switch/receipt
  controls. These records still do not launch processes or containers, execute
  repository commands, run install/build/test steps, access the network, write
  execution receipts, validate candidates, or promote capabilities.
- Creates sandboxed rebuild/run/test approval-request records that queue a
  pending exact-action approval for future governed repository execution after
  the sandboxed boundary readback. These records do not consume approvals,
  launch processes or containers, execute repository commands, run
  install/build/test steps, access the network, write execution receipts,
  validate candidates, or promote capabilities.
- Creates sandboxed rebuild/run/test approval-consumption records that consume
  an approved exact-action sandboxed rebuild/run/test approval once as
  governance evidence while still blocking process/container launch,
  repository commands, install/build/test steps, network access, repository
  writes, execution receipt writes, candidate validation, capability promotion,
  and execution authority.
- Creates sandboxed rebuild/run/test runner-binding preflight records that
  record static local provider reference and policy-manifest metadata after
  approval consumption while still blocking live runner binding, sandbox
  enforcement, provider execution, provider service queries, command execution,
  execution receipt writing, validation, promotion, and execution authority.
- Creates sandboxed rebuild/run/test sandbox-policy preflight records that bind
  approval-consumption and runner-binding evidence to conservative Lab policy:
  default-deny network, read-only source reference, no repo writes, no
  destructive action, no secret storage, command execution disabled, and
  missing command allowlist, execution receipt writer, live sandbox, and
  sandbox enforcement controls.
- Creates synthetic no-op execution receipts that can be prewritten and
  finalized at the reserved sink path with all execution, approval-consumption,
  network, and repo-write flags set to false.
- Creates approval-consumption records for finalized synthetic no-op execution
  receipts, enforcing single-use approval reuse blocking without granting
  execution authority.
- Creates built-in no-op runner envelope records from consumed synthetic no-op
  approval evidence, proving the runner handoff can complete a Francis-owned
  no-op without running repository commands.
- Creates built-in no-op runner transcript records that record deterministic
  empty stdout/stderr metadata for the completed Francis-owned no-op envelope
  without capturing real process output or storing output content.
- Creates built-in no-op runner identity binding records that bind only the
  Francis-owned built-in no-op runner identity to the completed no-op proof
  chain without binding a live runner or sandbox runner.
- Refuses lab execution with receipts until a governed runner exists.
- Writes source/capability registries and receipts.
- Exposes CLI entrypoints:
  - `francis ingest add <path>`
  - `francis repo inspect <path-or-source-id>`
  - `francis capability candidates <source-id-or-path>`
  - `francis lab plan <source-id-or-path> <candidate-id-or-name>`
  - `francis lab prepare <source-id-or-path> <candidate-id-or-name>`
  - `francis lab preflight <source-id-or-path> <candidate-id-or-name>`
  - `francis lab request-approval <source-id-or-path> <candidate-id-or-name>`
  - `francis lab approval-consumption-preflight <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab runner-readiness <source-id-or-path> <candidate-id-or-name> [--approval-id <approval-id>]`
  - `francis lab runner-binding <source-id-or-path> <candidate-id-or-name> [--approval-id <approval-id>]`
  - `francis lab runner-enforcement <source-id-or-path> <candidate-id-or-name> [--approval-id <approval-id>]`
  - `francis lab approval-consumption-handoff <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab execution-receipt-sink-reservation <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab runner-command-allowlist-binding <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab runner-command-allowlist-declaration <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab runner-command-allowlist-enforcement <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab runner-sandbox-readiness <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab sandbox-provider-contract <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab sandbox-provider-binding <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab sandbox-provider-selection <source-id-or-path> <candidate-id-or-name> <approval-id> --provider-kind <kind> --provider-reference <path-or-name> --provider-policy-manifest <path>`
  - `francis lab sandbox-provider-verifier <source-id-or-path> <candidate-id-or-name> <approval-id> --provider-kind <kind> --provider-reference <path-or-name> --provider-policy-manifest <path>`
  - `francis lab sandbox-provider-runtime-probe <source-id-or-path> <candidate-id-or-name> <approval-id> --provider-kind <kind> --provider-reference <path-or-name> --provider-policy-manifest <path>`
  - `francis lab sandbox-provider-runtime-probe-harness <source-id-or-path> <candidate-id-or-name> <approval-id> --provider-kind <kind> --provider-reference <path-or-name> --provider-policy-manifest <path>`
  - `francis lab sandbox-provider-runtime-probe-runner-readiness <source-id-or-path> <candidate-id-or-name> <approval-id> --provider-kind <kind> --provider-reference <path-or-name> --provider-policy-manifest <path>`
  - `francis lab sandbox-provider-runtime-probe-runner-binding <source-id-or-path> <candidate-id-or-name> <approval-id> --provider-kind <kind> --provider-reference <path-or-name> --provider-policy-manifest <path>`
  - `francis lab sandbox-provider-runtime-probe-runner-enforcement <source-id-or-path> <candidate-id-or-name> <approval-id> --provider-kind <kind> --provider-reference <path-or-name> --provider-policy-manifest <path>`
  - `francis lab execution-receipt-write-readiness <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab execution-receipt-prewrite-binding <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab execution-receipt-writer-preflight <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab synthetic-execution-receipt-prewrite <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab synthetic-execution-receipt-finalize <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab approval-consume-synthetic-noop <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab noop-runner-envelope <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab noop-runner-transcript <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab noop-runner-identity-binding <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab source-mount-readiness <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab source-mount-contract <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab run-boundary-preflight <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab sandbox-provider-runtime-probe-execution-boundary <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab sandbox-provider-runtime-probe-refuse <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab sandbox-provider-runtime-probe-request-approval <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab sandbox-provider-runtime-probe-consume-approval <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab sandbox-provider-runtime-probe-invocation-boundary <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab sandbox-provider-runtime-probe-runner-pre-execution-boundary <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab sandbox-provider-runtime-probe-runner-control-binding <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab sandboxed-rebuild-run-test-boundary <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab sandboxed-rebuild-run-test-request-approval <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab sandboxed-rebuild-run-test-consume-approval <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab sandboxed-rebuild-run-test-runner-binding <source-id-or-path> <candidate-id-or-name> <approval-id> --provider-kind <kind> --provider-reference <path-or-name> --provider-policy-manifest <path>`
  - `francis lab sandboxed-rebuild-run-test-sandbox-policy <source-id-or-path> <candidate-id-or-name> <approval-id>`
  - `francis lab execute <source-id-or-path> <candidate-id-or-name>`
- Exposes a permission-gated API readback endpoint:
  - `GET /ingest/readback`
  - `POST /ingest/lab/approval-consumption-preflight`
  - `POST /ingest/lab/runner-readiness`
  - `POST /ingest/lab/runner-binding`
  - `POST /ingest/lab/runner-enforcement`
  - `POST /ingest/lab/approval-consumption-handoff`
  - `POST /ingest/lab/execution-receipt-sink-reservation`
  - `POST /ingest/lab/runner-command-allowlist-binding`
  - `POST /ingest/lab/runner-command-allowlist-declaration`
  - `POST /ingest/lab/runner-command-allowlist-enforcement`
  - `POST /ingest/lab/runner-sandbox-readiness`
  - `POST /ingest/lab/sandbox-provider-contract`
  - `POST /ingest/lab/sandbox-provider-binding`
  - `POST /ingest/lab/sandbox-provider-selection`
  - `POST /ingest/lab/sandbox-provider-verifier`
  - `POST /ingest/lab/sandbox-provider-runtime-probe`
  - `POST /ingest/lab/sandbox-provider-runtime-probe-harness`
  - `POST /ingest/lab/sandbox-provider-runtime-probe-runner-readiness`
  - `POST /ingest/lab/sandbox-provider-runtime-probe-runner-binding`
  - `POST /ingest/lab/sandbox-provider-runtime-probe-runner-enforcement`
  - `POST /ingest/lab/execution-receipt-write-readiness`
  - `POST /ingest/lab/execution-receipt-prewrite-binding`
  - `POST /ingest/lab/execution-receipt-writer-preflight`
  - `POST /ingest/lab/synthetic-execution-receipt-prewrite`
  - `POST /ingest/lab/synthetic-execution-receipt-finalize`
  - `POST /ingest/lab/approval-consume-synthetic-noop`
  - `POST /ingest/lab/noop-runner-envelope`
  - `POST /ingest/lab/noop-runner-transcript`
  - `POST /ingest/lab/noop-runner-identity-binding`
  - `POST /ingest/lab/source-mount-readiness`
  - `POST /ingest/lab/source-mount-contract`
  - `POST /ingest/lab/run-boundary-preflight`
  - `POST /ingest/lab/sandbox-provider-runtime-probe-execution-boundary`
  - `POST /ingest/lab/sandbox-provider-runtime-probe-refuse`
  - `POST /ingest/lab/sandbox-provider-runtime-probe-request-approval`
  - `POST /ingest/lab/sandbox-provider-runtime-probe-consume-approval`
  - `POST /ingest/lab/sandbox-provider-runtime-probe-invocation-boundary`
  - `POST /ingest/lab/sandbox-provider-runtime-probe-runner-pre-execution-boundary`
  - `POST /ingest/lab/sandbox-provider-runtime-probe-runner-control-binding`
  - `POST /ingest/lab/sandboxed-rebuild-run-test-boundary`
  - `POST /ingest/lab/sandboxed-rebuild-run-test-request-approval`
  - `POST /ingest/lab/sandboxed-rebuild-run-test-consume-approval`
  - `POST /ingest/lab/sandboxed-rebuild-run-test-runner-binding`
  - `POST /ingest/lab/sandboxed-rebuild-run-test-sandbox-policy`
- Exposes the aggregate readback in the operator UI through a read-only Code
  Ingest panel using the bounded `chat_ui.ingest` actor.

## What v0 Does Not Do

> Scope note: the statements below describe the **ingest** subsystem, which stays
> strictly non-executing. The separate Francis Lab v0 runtime (see above) is the
> only execution path, and only under the four-condition gate (consumed approval +
> safe candidate + explicit opt-in + live Docker); absent any of those it
> simulates. Ingest never executes regardless of Lab.

- It does not clone from GitHub or access the network.
- It does not run install, build, test, lint, package, Docker, CI, shell, or deploy
  commands from ingested repositories.
- It does not copy arbitrary source trees into a lab.
- It does not bind or enforce a live source mount.
- It does not create an enforced sandbox runner.
- It does not grant execution authority.
- It does not approve lab execution approval records.
- It does not use consumed approvals to execute repository code; approval
  consumption is limited to finalized synthetic no-op execution receipts,
  provider-probe approval records, and sandboxed rebuild/run/test approval
  records, and only blocks reuse or records exact-action governance evidence
  without granting execution authority.
- It does not treat sandboxed rebuild/run/test runner-binding preflight as a
  live runner binding, live sandbox binding, sandbox enforcement, execution
  receipt writing, validation, promotion, or execution authority.
- It does not treat sandboxed rebuild/run/test sandbox-policy preflight as a
  live sandbox, sandbox enforcement, command allowlist binding, execution
  receipt writer binding, process launch, repository command execution,
  install/build/test execution, validation, promotion, or execution authority.
- It does not treat a pending approval request as permission to execute.
- It does not bind or implement a governed Lab runner.
- It does not treat runner-readiness preflight as runner binding or sandbox
  enforcement.
- It does not treat runner-binding preflight as a live runner binding or
  execution-receipt sink binding.
- It does not treat runner-enforcement preflight as live policy enforcement,
  approval consumption, receipt-sink writes, or execution authority.
- It does not treat approval-consumption handoff as approval consumption,
  receipt-sink binding, runner enforcement, or execution authority.
- It does not treat execution-receipt sink reservation as receipt-sink binding,
  execution receipt prewrite, execution receipt final write, runner enforcement,
  or execution authority.
- It does not treat runner command allowlist binding as a live command allowlist,
  command execution binding, receipt-sink prewrite, approval consumption, or
  execution authority.
- It does not treat runner command allowlist declaration as a live command
  allowlist binding, runner binding, command execution, approval consumption, or
  execution authority.
- It does not treat runner command allowlist enforcement preflight as live
  allowlist enforcement, runner binding, command execution, approval
  consumption, receipt-sink writes, or execution authority.
- It does not treat runner sandbox readiness as a live sandbox, live runner
  binding, readonly source mount, command execution, approval consumption,
  receipt-sink writes, or execution authority.
- It does not treat sandbox provider contracts as live provider binding,
  sandbox enforcement, runner binding, filesystem isolation, process launch,
  command execution, approval consumption, or execution authority.
- It does not treat sandbox provider binding preflights as provider selection,
  provider binary/service verification, provider policy binding, live provider
  binding, sandbox enforcement, process launch, command execution, approval
  consumption, or execution authority.
- It does not treat sandbox provider selection preflights as provider
  binary/service verification, live provider binding, sandbox enforcement,
  process launch, command execution, approval consumption, or execution
  authority.
- It does not treat sandbox provider verifier preflights as provider runtime
  probe success, live provider binding, sandbox enforcement, process launch,
  service query, container launch, repository command execution, approval
  consumption, validation, promotion, or execution authority. Static verifier
  evidence may prove local provider reference identity and policy-manifest
  hashes; it does not prove that a provider can safely run commands.
- It does not treat sandbox provider runtime-probe preflights as provider runtime
  probe success, provider binary execution, provider service query, container
  launch, live provider binding, sandbox enforcement, approval consumption,
  repository command execution, validation, promotion, or execution authority.
  Runtime-probe preflights declare the controls a future governed provider probe
  must satisfy; they do not perform the probe.
- It does not treat sandbox provider runtime-probe harness preflights as provider
  runtime probe success, provider binary execution, provider service query,
  container launch, live provider binding, sandbox enforcement, approval
  consumption, execution receipt writing, repository command execution,
  validation, promotion, or execution authority. Harness preflights declare the
  controls a future governed probe harness must satisfy; they do not bind or run
  the harness.
- It does not treat sandbox provider runtime-probe runner readiness as a bound
  probe runner, runner identity binding, sandbox binding, provider runtime probe
  success, provider binary execution, provider service query, container launch,
  execution receipt writing, repository command execution, validation,
  promotion, or execution authority. Runner readiness declares the interface and
  missing controls a future governed probe runner must satisfy; it does not bind
  or run that runner.
- It does not treat sandbox provider runtime-probe runner binding preflight as a
  live probe-runner binding, runtime-probe binding, provider runtime probe
  success, provider binary execution, provider service query, process launch,
  container launch, execution receipt writing, repository command execution,
  validation, promotion, or execution authority. Runner binding preflight
  declares the contract a future governed probe-runner binding must satisfy; it
  does not bind or run that runner.
- It does not treat sandbox provider runtime-probe runner enforcement preflight
  as live runner enforcement, runtime-probe binding, provider runtime probe
  success, provider binary execution, provider service query, process launch,
  container launch, execution receipt writing, repository command execution,
  validation, promotion, or execution authority. Runner enforcement preflight
  declares the contract a future governed probe-runner enforcement must satisfy;
  it does not enforce, bind, probe, or run that runner.
- It does not treat execution receipt write readiness as receipt schema binding,
  execution receipt prewrite, execution receipt final write, command execution,
  approval consumption, or execution authority.
- It does not treat execution receipt prewrite binding as an execution receipt
  prewrite, execution receipt final write, writer implementation, command
  execution, approval consumption, or execution authority.
- It does not treat execution receipt writer preflight as a writer
  implementation, execution receipt prewrite, execution receipt final write,
  command execution, approval consumption, or execution authority.
- It does not treat run-boundary preflight as live runner binding, sandbox
  provider binding, provider selection, provider verification, provider runtime
  probing, runtime-probe runner enforcement, sandbox enforcement, read-only
  source mount enforcement, approval consumption for repo execution, execution
  receipt writes, repository command execution, candidate validation, or
  capability promotion.
- It does not treat sandbox provider runtime-probe execution boundary as
  provider runtime probe success, provider binary execution, provider service
  query, process launch, container launch, live sandbox provider binding,
  sandbox enforcement, execution receipt writing, approval consumption,
  repository command execution, validation, promotion, or execution authority.
- It does not treat sandbox provider runtime-probe refusal as provider runtime
  probe success, provider binary execution, provider service query, process
  launch, container launch, live sandbox provider binding, sandbox enforcement,
  execution receipt writing, approval consumption, repository command
  execution, validation, promotion, or execution authority. Refusal receipts
  prove that a requested provider probe was blocked, not that any probe ran.
- It does not treat sandbox provider runtime-probe approval requests as approval
  decisions, approval consumption, provider runtime probe success, provider
  binary execution, provider service query, process launch, container launch,
  live sandbox provider binding, sandbox enforcement, execution receipt writing,
  repository command execution, validation, promotion, or execution authority.
  They only queue operator approval for a future governed provider probe.
- It does not treat sandbox provider runtime-probe approval consumption as
  provider runtime probe success, provider binary execution, provider service
  query, process launch, container launch, live sandbox provider binding,
  sandbox enforcement, execution receipt writing, repository command execution,
  validation, promotion, or execution authority. Consumption only marks the
  exact-action provider-probe approval as single-use governance evidence.
- It does not treat sandbox provider runtime-probe invocation boundaries as
  provider runtime probe success, provider binary execution, provider service
  query, process launch, container launch, live runner binding, live sandbox
  binding, network isolation enforcement, execution receipt writing, repository
  command execution, validation, promotion, or execution authority. They only
  record the post-consumption controls that must exist before a future provider
  probe runner may be invoked.
- It does not treat sandbox provider runtime-probe runner pre-execution
  boundaries as provider runtime probe success, provider binary execution,
  provider service query, process launch, container launch, live runner binding,
  live sandbox binding/enforcement, network isolation enforcement, execution
  receipt writing, repository command execution, validation, promotion, or
  execution authority. They only record the required live runner controls still
  missing before a future provider-probe runner can be started.
- It does not treat sandbox provider runtime-probe runner control bindings as
  provider runtime probe success, provider binary execution, provider service
  query, process launch, container launch, live runner binding, live sandbox
  binding/enforcement, network isolation enforcement, execution receipt writing,
  repository command execution, validation, promotion, or execution authority.
  They only record the future control-binding evidence that must later be
  enforced by a governed runner.
- It does not treat sandboxed rebuild/run/test boundaries as repository
  execution, install/build/test execution, process launch, container launch,
  network isolation enforcement, execution receipt writing, candidate
  validation, promotion, or execution authority. They only record the future
  governed execution boundary that must later be backed by a separate execution
  approval and a live sandboxed runner.
- It does not treat sandboxed rebuild/run/test approval requests as approval
  decisions, approval consumption, repository execution, install/build/test
  execution, process launch, container launch, network isolation enforcement,
  execution receipt writing, candidate validation, promotion, or execution
  authority. They only queue operator approval for a future governed
  sandboxed rebuild/run/test attempt.
- It does not treat sandboxed rebuild/run/test approval consumption as
  repository execution, install/build/test execution, process launch, container
  launch, live runner binding, live sandbox binding/enforcement, network
  isolation enforcement, execution receipt writing, candidate validation,
  promotion, or execution authority. Consumption only marks the exact-action
  sandboxed rebuild/run/test approval as single-use governance evidence.
- It does not treat synthetic no-op execution receipts as command execution,
  candidate validation, approval consumption, runner binding, sandbox binding,
  build/test execution, or permission to run repository code.
- It does not treat synthetic no-op approval consumption as repository command
  execution, candidate validation, runner binding, sandbox binding, or
  permission to run repository code.
- It does not treat built-in no-op runner envelopes as repository command
  execution, sandbox runner binding, candidate validation, build/test execution,
  or permission to run repository code.
- It does not treat built-in no-op runner transcripts as real process output
  capture, repository command execution, sandbox runner binding, candidate
  validation, build/test execution, or permission to run repository code.
- It does not treat built-in no-op runner identity bindings as live runner
  binding, sandbox runner binding, repository command execution, candidate
  validation, build/test execution, or permission to run repository code.
- It does not treat source-mount readiness as a live readonly source mount,
  mount enforcement, source copy, source write permission, command execution,
  candidate validation, or permission to run repository code.
- It does not validate candidates as buildable, runnable, or mature.
- It does not register candidates for use by Francis.
- It does not promote capability into Forge or the Capability Economy.
- It does not treat repository docs or scripts as trusted instructions.

## Forge Synthesis Corridor v0 (governed, non-applying)

The local builder (`builder.local.ollama`) produces a **proposal artifact only** —
a Francis-native patch or plan that is recorded but never applied. The Forge
synthesis corridor is the governed forward arc that picks up there and drives a
proposal toward an operator-approvable — but still un-applied — state. Like the
ingest subsystem, it is a **capability of Francis, not Francis authority**: it
writes evidence and never calls `approvals.decide`, applies a patch, writes to the
repo, runs a command, validates a candidate, or promotes a capability.

The corridor is six deterministic, evidence-only bricks
(`src/francis/ingest/core/proposal_review.py` + `forge_service.py`):

1. **`builder.proposal.review`** (`review_builder_proposal`) — the deterministic
   review gate. A verdict is **only ever computed over the full proposal text
   whose sha256 matches the digest recorded on the builder run**. Absent or
   mismatched text yields an honest `indeterminate` verdict — never a clean signal
   over truncated content. When verified, it parses the unified diff and checks:
   touched files ⊆ `allowed_files` and ∩ `forbidden_files` = ∅, file count ≤
   `max_files_changed`, diff well-formedness, secret/destructive token scan
   (blocking) and network token scan (flagged), and a **bounded third-party
   copy-overlap scan** against the ingested source tree (token-shingle Jaccard;
   high overlap flags `possible_third_party_copy`, turning the `do_not_copy`
   policy into actual evidence). Verdict: `clean` / `blocked` / `indeterminate`.
2. **`forge.apply.preflight`** (`preflight_forge_apply`) — depends on a `clean`
   review; computes the exact-action apply hash and projects the apply gate plus
   the required operator approval scope `ingest.forge.apply.execute`. Creates no
   approval and applies nothing.
3. **`forge.apply.approval_request`** (`request_forge_apply_approval`) — queues a
   pending exact-action approval through the Francis approvals store. Does not
   consume or grant.
4. **`forge.apply.approval_consumption`** (`consume_forge_apply_approval`) —
   consumes an approved exact-action approval once (single-use, reuse-blocked,
   action-hash matched) as governance evidence. Apply stays impossible.
5. **`forge.apply.boundary`** (`boundary_forge_apply`) — the honest refusal
   surface: even with a consumed approval, applying is refused until a separate
   governed applier (atomic write + rollback, apply receipt sink, forbidden-path
   write guard, post-apply Lab validation) exists. Records `patch_applied: false`,
   `wrote_to_repo: false`, `execution_authority: false`.
5b. **`forge.apply.dryrun`** (`dryrun_forge_apply`) — the first governed applier
   control: applies a clean, approved, **consumed** proposal to an **isolated
   Francis-owned scratch copy** of the source tree (`forge_dryrun_workspaces/`),
   never the real repo. Requires the full proposal text digest-matched to the
   review (no fuzzy/forced application — context/removed-line mismatches reject the
   file), enforces the forbidden-path write guard, and refuses any path that would
   escape the scratch tree. Records per-file `applied`/`rejected` status with
   before/after digests; `wrote_to_repo` stays `false`. This proves the proposal
   applies cleanly without ever mutating the host repo — the evidence a future
   real applier and post-apply Lab validation will build on.
5c. **`forge.synthesized_source.bind`** (`bind_synthesized_source`) — closes the
   loop. Registers the dry-run scratch tree (the synthesized capability, applied in
   isolation) as a **new first-class ingest source**, inspects it read-only, and
   extracts its candidates. The synthesized capability can then be validated through
   the **existing, already-verified governed Lab corridor** (acquisition orchestrator
   → `sandboxed_rebuild_run_test` approval → `run_lab_capability` real Docker
   sandbox) — no new execution path and no weakened gate. End-to-end:
   *ingest a repo → synthesize a Francis-native proposal → apply to scratch →
   re-ingest the synthesized tree → (operator) validate it in the sandbox.*
6. **`forge.validation.plan`** (`plan_forge_validation`) — projects how an applied
   proposal would later be validated through the existing Francis Lab v0
   sandboxed rebuild/run/test path (reading the capability spec's validation
   commands). Records that validation requires an applied proposal first and a
   separate Lab execution approval; runs nothing.

### Synthesis orchestrator (ingest pushes synthesis end-to-end)

`synthesize_capability` / `continue_synthesis_after_approval`
(`src/francis/ingest/core/forge_orchestrator.py`) make ingest *push* the whole
corridor the way the acquisition orchestrator pushes the Lab corridor. The first
call drives compile-spec → builder proposal → digest-gated review → apply preflight
→ apply approval request, then **pauses at the real `francis.forge.apply` operator
gate** (the minted approval is never auto-granted). After the operator approves,
`continue_synthesis_after_approval` resumes through single-use consumption → the
apply boundary (refusal) → the validation plan, terminating in the honest
`refused` state (approved, consumed, apply still refused — nothing applied or
promoted). The builder step uses the production localhost Ollama path, or an
injected deterministic client for tests. Runs persist under
`data/artifacts/ingest/forge_synthesis_runs/` and surface in readback.

Each brick writes a record under
`data/artifacts/ingest/{builder_proposal_reviews,forge_apply_preflights,
forge_apply_approval_requests,forge_apply_approval_consumptions,
forge_apply_boundaries,forge_validation_plans,forge_synthesis_runs}/` plus a receipt
(`builder.proposal.review`, `forge.apply.preflight`,
`forge.apply.approval_request`, `forge.apply.approval_consumption`,
`forge.apply.boundary`, `forge.validation.plan`). All six surface in
`GET /ingest/readback` aggregates and counts. Reviews never persist raw added
source lines (only counts + digests), so no third-party code or secret content is
stored.

Future work should add the governed Francis Lab only after sandbox, permission,
network, filesystem, resource, and receipt controls are enforceable.
