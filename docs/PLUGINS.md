==============================================================================

FRANCIS — PLUGINS.md

Plugin system architecture: tools, specs, templates, registry, sandbox, and governance

==============================================================================



Purpose

-------

This document defines the FRANCIS plugin system end-to-end:

   - What a “plugin” is in FRANCIS (and what it is not)

   - How plugin specs become callable tools

   - How plugins are discovered, validated, registered, and executed

   - How safety, permissions, trust, approvals, and sandboxing apply to plugins

   - How plugins are packaged (builtins / packs / generated / third_party)

   - How the UI and API expose plugin browsing and invocation



Read alongside:

   - docs/ARCHITECTURE.md

   - docs/API_PERMISSIONS.md

   - docs/POLICIES.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/RUNBOOK.md

   - config/policies/sandbox.yaml

   - config/policies/filesystem.yaml

   - config/policies/web_access.yaml

   - config/policies/api_permissions.yaml

   - config/policies/approvals.yaml

   - config/capabilities/trust_permissions_map.yaml

   - schemas/plugins.schema.json

   - src/francis/plugin_system/*

   - src/francis/plugin_factory/*

   - src/francis/llm/tooling/*

   - plugins/templates/*.tpl



Design stance

------------

   - A plugin is *an authority amplifier*; treat it like infrastructure.

   - Default deny: plugins do not get power “because they exist.”

   - Specs are contracts; code must enforce contracts.

   - Every plugin execution must be attributable, scoped, sandboxed, and audited.

   - Safety-critical tools require stricter templates, policies, and approvals.



==============================================================================





## 1. Definitions



### 1.1 Plugin

A **plugin** is a packaged capability that exposes one or more **tools** to the

FRANCIS runtime, typically backed by:

- connector operations (SaaS, DB, web, industrial protocols),

- internal services (indexing, summarization, export),

- or “composite workflows” that orchestrate safe sub-operations.



A plugin is defined by **spec + implementation + policy mapping**, then registered.



### 1.2 Tool

A **tool** is a callable function exposed to the orchestration/execution stack.

Tools must have:

- a stable name,

- a schema-validated input contract,

- output shape expectations,

- and governance metadata.



### 1.3 Plugin spec

A **plugin spec** is the declarative description of a plugin’s tools:

- names, descriptions, params schema,

- risk class,

- required scopes/permissions,

- rate limits and constraints,

- and sandbox + governance hooks.



Specs are *machine-checkable* and must conform to `schemas/plugins.schema.json`.



### 1.4 Template

A **template** is a standardized tool-definition generator used to produce:

- tool schemas consumable by the LLM/tool router,

- UI metadata,

- and policy tags.



Templates enforce category-specific invariants:

- normal tools vs critical tools vs safety-critical tools.



See:

- `plugins/templates/tool_normal.tpl`

- `plugins/templates/tool_critical.tpl`

- `plugins/templates/tool_safety_critical.tpl`

- `plugins/templates/tool_readonly.tpl`



### 1.5 Registry

The **plugin registry** is the authoritative list of available plugins/tools,

including metadata needed for:

- discovery,

- compatibility checks,

- trust/permission mapping,

- execution routing.



Registry location (conceptual):

- `plugins/registry/*`

- and/or generated runtime registry in memory.



### 1.6 Sandbox

The **sandbox** is the execution containment system:

- resource limits,

- network/filesystem allowlists,

- process isolation model (where applicable),

- and policy-enforced constraints.



See:

- `src/francis/plugin_system/sandbox/*`

- `config/policies/sandbox.yaml`





## 2. Plugin taxonomy in this repo



FRANCIS organizes plugin code and artifacts to separate trust levels and origins.



### 2.1 builtins/

**Built-in plugins**: first-party, versioned with core.

- Highest baseline trust, but still policy-gated.

- Must meet strict test and audit requirements.



Location:

- `plugins/builtins/*`



### 2.2 packs/

**Plugin packs**: curated bundles of plugins for a domain or environment.

- Can be enabled/disabled by environment config.

- Packs define defaults: which plugins are available in regulated/airgapped modes.



Location:

- `plugins/packs/*`



### 2.3 generated/

**Generated plugins**: created by the plugin factory from specs/templates.

- Always re-generated from source-of-truth specs.

- Must not be edited manually (treat as build artifacts).



Location:

- `plugins/generated/*`



### 2.4 third_party/

**Third-party plugins**: external code integrated into FRANCIS.

- Strictest sandbox and review requirements by default.

- Often pinned to hashes/versions, ideally with attestations.



Location:

- `plugins/third_party/*`



### 2.5 spec/

**Specifications**: declarative plugin definitions and metadata.

Location:

- `plugins/spec/*`





## 3. Plugin spec model (contract)



### 3.1 Core required fields (conceptual)

A well-formed plugin spec should include:



- `plugin_id` (stable identifier)

- `name` (human-friendly)

- `version` (semantic version)

- `description`

- `origin` (`builtin` | `pack` | `generated` | `third_party`)

- `tools` (list)

- `capabilities` (taxonomy tags)

- `risk_class` (see below)

- `permissions` mapping (scopes + methods)

- `constraints` (rate limits, max payloads, allowed targets)

- `sandbox_profile` reference

- `telemetry` requirements (audit level, redaction rules)

- `compatibility` (min core version, runtime requirements)

- `signing/attestation` metadata (recommended)



### 3.2 Tool definition shape

Each tool within a plugin should provide:



- `tool_name` (namespaced, stable)

- `summary` (one-line)

- `description` (operator-grade, precise)

- `input_schema` (JSON schema compatible)

- `output_schema` (recommended; helps verification)

- `methods` (`read` | `write` | `delete` | `execute`)

- `resources` (structured constraints: org/repo/db/table/channel)

- `policy_tags` (privacy, regulated, web_access, offensive_security, etc.)

- `requires_approvals` (optional)

- `requires_trust_level` (optional)

- `rate_limits` (optional)

- `idempotency` (recommended: safe retries)

- `dry_run_supported` (recommended for high impact)



### 3.3 Risk classes (canonical)

Risk classification drives governance and template selection.



Recommended classes:

- **readonly**: read operations with limited side effects

- **normal**: bounded writes, reversible operations

- **critical**: high-impact writes; can affect systems/users

- **safety_critical**: irreversible or physically hazardous operations



A plugin/tool’s risk class must be:

- explicitly set,

- validated by policy engine,

- and visible to operators in UI.



### 3.4 Namespacing rule

Tool names should be namespaced to avoid collision and clarify authority:

- `github.list_issues`

- `slack.post_message`

- `db.postgres.query_readonly`

- `industrial.modbus.write_register` (safety-critical)



This is not cosmetic. Namespacing supports:

- policy rules,

- scopes,

- audit clarity,

- and operator review.





## 4. How specs become tools (build pipeline)



FRANCIS treats tool schemas as build artifacts derived from specs.



### 4.1 Build stages (conceptual)

1) **Spec ingestion**

   - Load plugin specs from `plugins/spec/*` and enabled packs.

   - Validate against `schemas/plugins.schema.json`.



2) **Template selection**

   - Choose a template by tool risk class:

     - readonly → `tool_readonly.tpl`

     - normal → `tool_normal.tpl`

     - critical → `tool_critical.tpl`

     - safety_critical → `tool_safety_critical.tpl`



3) **Tool schema generation**

   - Produce tool definitions consumable by:

     - `src/francis/llm/tooling/tool_schema_adapter.py` (LLM-facing format)

     - UI plugin browser metadata

     - policy metadata attachments



4) **Registry compilation**

   - Merge generated artifacts into the runtime plugin registry.

   - Apply environment disables/allowlists.



5) **Verification**

   - Ensure tool schemas match implementation signatures (where applicable).

   - Enforce “no missing policy tags” for sensitive tools.



6) **Packaging**

   - Write outputs into `plugins/generated/*` as deterministic artifacts (optional).

   - Emit telemetry event: plugin build snapshot.



### 4.2 Deterministic generation rules

To avoid non-reproducible drift:

- Generation must be deterministic given the same inputs.

- Ordering and formatting must be stable.

- Generated artifacts should include:

  - source spec hash,

  - generator version,

  - build timestamp (optional, or stored separately to preserve diffs).





## 5. Execution model (what happens at runtime)



### 5.1 Invocation phases

A tool call lifecycle is:



1) **Proposal**

   - Reasoning plane proposes calling `tool_name` with params.



2) **Preflight validation**

   - Validate params against `input_schema`.

   - Normalize values (canonicalize paths, hosts, IDs).



3) **Governance gates**

   - Permission gate (identity/scopes/delegations)

   - Policy engine checks (privacy/offensive/web/filesystem/etc.)

   - Trust/readiness gate (approvals, environment mode)

   - Sandbox eligibility checks (profile allows this operation)



4) **Dispatch**

   - Route tool to implementation:

     - connector,

     - plugin execution dispatcher,

     - internal service.



5) **Sandboxed execution**

   - Enforce resource limits, network/filesystem constraints.



6) **Postconditions**

   - Validate outputs (shape, invariants).

   - Apply output verification (for critical tools).

   - Redact sensitive fields.



7) **Telemetry + artifacts**

   - Emit audit trail entries:

     - decision

     - execution trace

     - outcome status

   - Store artifacts (if configured) in `data/artifacts/*`.



### 5.2 Dispatcher and lifecycle hooks

Core runtime components (conceptual mapping):

- `src/francis/plugin_system/execution/dispatcher.py`

  - routes tool calls to correct handler

- `src/francis/plugin_system/execution/lifecycle.py`

  - standardized hooks:

    - on_register

    - on_validate

    - on_authorize

    - on_execute

    - on_postprocess

    - on_audit



This ensures every plugin gets consistent:

- policy enforcement,

- telemetry,

- redaction,

- and error classification.





## 6. Security \& governance model for plugins



Plugins are where “capability” becomes “power.” FRANCIS must assume:

- plugin input is attacker-controlled,

- plugin output can be wrong or malicious,

- and plugin code can be compromised.



Defense-in-depth is required.



### 6.1 Default deny and explicit enablement

A plugin/tool is callable only if:

- it is present in the registry,

- it is enabled by environment config,

- and permissions + policy gates allow it.



Environment configs should be able to:

- disable entire plugin families (e.g., web connectors in airgapped mode),

- allowlist only specific tools,

- require approvals for particular tool classes.



### 6.2 Scope enforcement (least privilege)

All execution must bind to scopes:

- tools allowed,

- operations allowed,

- resources allowed,

- methods allowed,

- constraints (rate, time window, max rows, path allowlists).



Scopes are referenced and enforced via:

- `docs/API_PERMISSIONS.md`

- `config/policies/api_permissions.yaml`

- `src/francis/credentials/scope_checker.py`



### 6.3 Approval gating

Some tools require approvals:

- destructive actions

- external communications (email, messaging)

- credential rotation

- industrial operations

- cross-domain exports



Approvals live in:

- `data/approvals/*`

and are enforced in governance before execution.



### 6.4 Trust gating and safety mode interaction

Even if a scope allows an operation:

- trust can force **deny**, **dry-run**, or **require review**

depending on:

- environment mode,

- tool risk class,

- recent policy drift,

- and historical performance.



### 6.5 Sandbox profiles (per plugin/tool)

Sandbox profiles define constraints like:

- filesystem: allowed roots, read/write rules

- network: allowlisted hosts/ports/protocols

- process: timeouts, memory/cpu limits

- concurrency: max parallel executions

- payload: max input/output sizes



Safety-critical tools should default to:

- minimal network access,

- strict parameter validation,

- mandatory postcondition checks,

- and mandatory audit verbosity.



### 6.6 Output verification for critical/safety-critical tools

For high-risk tools:

- Outputs must be checked against output schema.

- Additional invariants should be validated:

  - no hidden side effects implied by output

  - returned IDs match expected patterns

  - status reflects confirmed tool result, not “optimistic” success

- Optional: “two-man rule” via:

  - independent verifier agent

  - or mandatory human approval step



See also:

- `src/francis/llm/guardrails.py`

- `src/francis/adversarial/defense/output_verifier.py`





## 7. Plugin registry \& discovery



### 7.1 Registry responsibilities

The registry must answer:

- What tools exist?

- What are their schemas?

- What risk class do they have?

- What policies apply?

- What scopes are required?

- Where is the implementation?

- What versions are installed?



### 7.2 Registry sources

Registry may be compiled from:

- builtins

- enabled packs

- generated artifacts

- third_party sources



The registry should include:

- `plugin_id`, `version`

- tool list

- spec hash

- implementation entrypoint reference

- required policies and sandbox profile

- signature/attestation status (recommended)



### 7.3 Hot-reload vs pinned registry (recommended behavior)

For production/regulated modes:

- prefer pinned registry snapshots

- require explicit operator action to reload plugins

- record a registry snapshot artifact for auditability



For dev modes:

- allow reload with strict logging, and discourage silent drift





## 8. Plugin packaging and distribution



### 8.1 Semantic versioning and compatibility

Plugins should use semantic versioning:

- MAJOR: breaking schema or behavior changes

- MINOR: backward-compatible new tools/fields

- PATCH: bugfixes, security patches



Compatibility metadata should specify:

- min core version

- required runtimes (python/js/etc.)

- external dependencies and constraints



### 8.2 Signing and attestations (strongly recommended)

For third_party and safety-critical plugins:

- store signature metadata in spec

- pin dependencies (hashes/lockfiles)

- support provenance attestations:

  - build system

  - commit hash

  - artifact hash

  - signer identity



If signing is absent:

- governance should reduce trust and increase required approvals.



### 8.3 Packs as policy-driven bundles

A pack should define:

- plugin allowlist

- default sandbox profiles per plugin

- default approval requirements

- environment overrides (regulated vs dev)



This creates a safe, reproducible “capability profile”.





## 9. Generated plugins and plugin_factory



### 9.1 Why generation exists

Generated plugins reduce error-prone hand wiring by:

- enforcing consistent tool schemas,

- attaching correct policy tags,

- and producing deterministic registry entries.



### 9.2 plugin_factory responsibilities

The plugin factory should:

- validate specs,

- select templates,

- generate tool definitions and stubs,

- generate tests (optional),

- produce registry entries,

- and report deltas vs previous generation.



Code map:

- `src/francis/plugin_factory/spec_builder.py`



### 9.3 Drift detection

Generated outputs should embed:

- source spec hash,

- generator version,

- and stable IDs.



If runtime sees:

- mismatch between spec hash and generated tool schema,

it must:

- refuse to execute (or require elevated approval),

- and emit a drift audit event.





## 10. UI and operator controls (plugin browser)



The Chat UI should provide a **Plugin Browser** that supports:



- Search and filter by:

  - risk class

  - policy tags (privacy, web_access)

  - origin (builtin/third_party)

  - enabled/disabled

  - approval requirements

- Inspect tool schema:

  - required parameters

  - resource constraints

  - sandbox profile

- Inspect governance:

  - which scopes are required

  - what approvals are required

  - what trust thresholds apply

- Inspect telemetry:

  - last executions

  - failure rates

  - blocked attempts and reasons

- Export:

  - plugin registry snapshot

  - tool schema bundle for review





## 11. Testing strategy for plugins



### 11.1 Required test layers

- **Schema tests**

  - validate spec against schema

  - validate generated tool definitions against schema

- **Policy tests**

  - ensure correct policy tags

  - ensure default deny works

  - ensure approvals are required for the right categories

- **Sandbox tests**

  - confirm blocked network/filesystem behavior

- **Integration tests**

  - run against mocks for SaaS/DB

- **E2E tests (optional)**

  - run in controlled environment with non-production credentials



### 11.2 Contract testing (recommended)

Every tool should have a contract test that checks:

- input normalization

- output shape

- idempotency (if declared)

- error classification

- redaction correctness



### 11.3 Safety-critical test gates

Safety-critical tools should require:

- explicit enablement in CI

- review approvals for changes

- stronger linting and static checks

- postcondition test suite





## 12. Operational runbooks (plugin management)



### 12.1 Install / enable

- Add plugin spec (or pack enable)

- Regenerate registry (if applicable)

- Validate in dev mode

- Promote to production with pinned snapshot

- Record:

  - plugin version,

  - spec hash,

  - approval artifacts (if required)



### 12.2 Disable / quarantine

Disable conditions:

- repeated failures

- suspicious outputs

- policy violations

- unexpected network access attempts



Quarantine actions:

- disable plugin in environment config

- revoke delegations/scopes related to it

- preserve logs and traces

- run forensics if compromise suspected



### 12.3 Emergency shutdown

Plugins that can cause external or physical impact must support:

- immediate disable switch

- “circuit breaker” in runtime

- emergency approvals path (where policy allows)

- high-verbosity audit trail





## 13. Implementation pointers (code map)



- Plugin discovery/registry:

  - `src/francis/plugin_system/registry.py`

- Execution:

  - `src/francis/plugin_system/execution/dispatcher.py`

  - `src/francis/plugin_system/execution/lifecycle.py`

- Sandbox:

  - `src/francis/plugin_system/sandbox/*`

- Spec building / generation:

  - `src/francis/plugin_factory/spec_builder.py`

- Tool schema adaptation (LLM-facing):

  - `src/francis/llm/tooling/tool_schema_adapter.py`

- Governance gate for tool calls:

  - `src/francis/governance/api_permission_gate.py`

  - `src/francis/governance/policy_engine.py`

- Credentials + scopes + delegations:

  - `src/francis/credentials/*`

- Telemetry/audit:

  - `src/francis/telemetry/*`





## 14. Appendix: minimal illustrative plugin spec (example)



```yaml

plugin_id: slack_messaging

name: Slack Messaging

version: 1.2.0

origin: builtin

description: Post messages to Slack with scoped channel constraints.

capabilities: [communication, messaging]

risk_class: critical

sandbox_profile: net_saas_minimal

tools:

  - tool_name: slack.post_message

    summary: Post a message to a Slack channel

    description: >

      Sends a message to an allowlisted Slack channel. Requires approval in

      regulated environments and uses redaction to prevent secret leakage.

    methods: [write]

    policy_tags: [privacy, external_communication]

    requires_approvals: [external_message_send]

    input_schema:

      type: object

      required: [channel, text]

      properties:

        channel:

          type: string

        text:

          type: string

          maxLength: 4000

    constraints:

      allowed_channels: ["#ops", "#alerts"]

      rate_limit:

        per_minute: 10

permissions:

  required_scopes:

    - slack_channel_write_ops

telemetry:

  audit_level: full

  redact_fields: ["text"]



