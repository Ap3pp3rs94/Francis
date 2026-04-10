==============================================================================

FRANCIS — SELF_HEALING.md

Self-healing: detection, diagnosis, containment, remediation, and recovery

==============================================================================



Purpose

-------

This document defines the self-healing system in FRANCIS:

   - what “self-healing” means in practice

   - what signals trigger healing workflows

   - how FRANCIS diagnoses failures and chooses safe remediations

   - how containment/rollback/restart are executed under governance

   - how recovery is verified and learned from (postmortems → regressions tests)



Self-healing is the operational response loop:

   detect → diagnose → contain → remediate → verify → learn



It is NOT:

   - silent mutation of code/policies to “make errors go away”

   - bypassing approvals for high-risk actions

   - rewriting security boundaries or lowering trust requirements

   - deleting evidence to hide incidents



Read alongside:

   - docs/ARCHITECTURE.md

   - docs/GOVERNANCE.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/POLICIES.md

   - docs/ACTION_READINESS.md

   - docs/CONCURRENCY.md

   - docs/RUNBOOK.md

   - docs/SELF_EVOLUTION.md

   - docs/ADVERSARIAL_ROBUSTNESS.md

   - docs/API_PERMISSIONS.md

   - config/policies/action_readiness.yaml

   - config/policies/approvals.yaml

   - config/policies/sandbox.yaml

   - config/policies/filesystem.yaml

   - config/policies/networks.yaml

   - config/policies/offensive_security.yaml

   - config/policies/privacy.yaml

   - config/policies/data_governance.yaml

   - config/runtime/logging.yaml

   - config/runtime/scheduler.yaml

   - src/francis/governance/*

   - src/francis/telemetry/*

   - src/francis/adversarial/recovery/*

   - src/francis/kernel/*

   - scripts/self-heal.ps1

   - scripts/doctor.ps1

   - scripts/emergency-shutdown.ps1

   - data/logs/*

   - data/state/*

   - data/quarantine/*



Design stance

------------

   - Healing is governed operations: safe by default, reversible by default.

   - Prefer containment and rollback over “clever” fixes.

   - Treat security-relevant anomalies as incidents first, bugs second.

   - Preserve evidence. Never “clean up” in ways that destroy forensics value.

   - Make every remediation auditable and reproducible.



==============================================================================





## 0. Executive summary



Self-healing is the operational stability loop for FRANCIS.



At runtime, FRANCIS continuously monitors for:

- failures (crashes, exceptions, timeouts)

- degraded behavior (latency/cost spikes, tool errors)

- security anomalies (injection attempts, poisoned inputs)

- policy violations (near-miss or breach)

- drift (behavior changes relative to baselines)



When a trigger fires, FRANCIS:

1) captures context (evidence bundle),

2) classifies the incident and risk,

3) chooses a safe plan under governance,

4) executes remediation in a sandboxed and reversible way when possible,

5) verifies recovery with health checks and regression tests,

6) records a postmortem and optionally proposes longer-term evolution changes.





## 1. Definitions



### 1.1 Self-healing

**Self-healing** is the ability of the system to restore safe, correct operation

after faults or attacks, while preserving auditability.



### 1.2 Incident vs degradation

- **Incident**: a safety/security/correctness event that violates constraints or

  requires containment. Often requires approvals/human review depending on mode.

- **Degradation**: performance or reliability drop without a confirmed breach.



Degradation can become an incident if thresholds are exceeded.



### 1.3 Containment

**Containment** means limiting blast radius:

- disable high-risk tools

- restrict network/web access

- quarantine inputs/artifacts

- switch to safe mode / read-only mode

- pause automation



Containment is prioritized over full remediation.



### 1.4 Remediation

**Remediation** is the corrective action to restore function:

- restart services

- rollback configs

- rotate ephemeral sessions (not secrets unless approved)

- purge safe caches

- reindex corrupted local indexes

- reduce concurrency / throttle

- disable a problematic connector



### 1.5 Recovery verification

**Verification** confirms that:

- the system is healthy

- the safety constraints are intact

- the regression is gone

- the root cause is understood enough to prevent recurrence



### 1.6 Evidence bundle

An **evidence bundle** is the minimal set of artifacts needed to audit and debug:

- timestamps

- request/session ids

- redacted tool traces

- policy snapshots + config versions

- error stack traces

- environment profile

- “what changed recently” markers





## 2. Safety invariants for self-healing



These invariants are “hard rails” for the healing loop.



### 2.1 Preserve evidence

- Never delete or overwrite evidence artifacts needed for forensics.

- If storage is constrained, compress and archive; do not erase selectively.



### 2.2 No silent privilege elevation

- Self-healing must not broaden tool permissions, scopes, or sandbox limits.

- Any permission change must go through governance and approvals.



### 2.3 Default to reversible actions

Prefer:

- restart

- rollback

- disable feature / connector

over:

- destructive database edits

- sweeping policy changes

- unbounded “cleanup”



### 2.4 Containment before remediation

If there is any plausible security dimension:

- contain first

- then diagnose safely

- remediate only with clear evidence and approvals if needed



### 2.5 Respect environment modes

In regulated or safety-critical profiles:

- “self-heal” may be propose-only or contain-only

- remediation requires operator approval

- destructive operations may be forbidden





## 3. Signals and triggers



Self-healing is driven by signals. Signals are categorized and thresholded.



### 3.1 Reliability signals

- process crash / restart loop

- unhandled exceptions

- task timeouts / deadlocks

- queue backlogs

- connector timeouts

- disk space pressure

- database connection failures



### 3.2 Performance signals

- latency (p95/p99) spikes

- LLM token cost spikes

- elevated external API error rates

- memory/cpu saturation

- vector index query slowdown



### 3.3 Correctness signals

- evaluation suite failure (in staging/prod smoke tests)

- replay tests failing

- systematic user-facing errors (patterned complaints)

- mismatch between tool result and expected schema



### 3.4 Governance / policy signals

- repeated denials on previously allowed workflows (may indicate drift)

- “near miss” events where a risky action was almost executed

- approvals mismatches / invalid approvals detected



### 3.5 Security signals

- prompt injection detections

- suspicious attachment flags

- anomalous tool selection patterns

- poisoned data detector hits

- repeated access attempts to forbidden paths/domains



### 3.6 Trust signals

- trust score decay crossing threshold

- spike in unsafe outputs caught by verifiers

- unexpected variance in agent confidence reporting





## 4. Healing lifecycle (canonical run)



### 4.1 Detect

The monitor identifies a trigger and opens a healing case:

- `case_id`

- severity

- category

- affected subsystem

- time window



### 4.2 Stabilize (immediate safety actions)

Perform minimal blast-radius reductions:

- pause risky workers

- switch to read-only mode

- disable web access (if policy allows)

- throttle concurrency

- disable specific connector operations



This is a safe action set chosen by policy.



### 4.3 Capture evidence

Capture an evidence bundle:

- policy snapshot (hashes, versions)

- config versions (routing, sandbox, permissions)

- recent deployment markers

- relevant logs (redacted)

- tool traces (redacted)

- last N errors and their stack traces

- metrics snapshots for the incident window



Write the bundle to a safe artifact store:

- `data/artifacts/reports/` (or a dedicated incident folder)

- ensure secrets redacted



### 4.4 Classify and triage

Classification determines what can be done automatically.

Examples:

- reliability-only → restart/rollback permitted

- performance-only → throttle/cache purge permitted

- security-suspected → contain-only until approval

- privacy-suspected → contain + lock export channels + escalate



### 4.5 Diagnose

Diagnosis is hypothesis-driven:

- reproduce (if safe)

- isolate subsystem

- compare against baselines

- identify “recent changes” correlations

- consult known failure catalog/runbooks



Outputs:

- ranked hypotheses

- recommended remediation options with risk ratings

- required approvals list (if any)



### 4.6 Remediate (governed execution)

Execute the least risky remediation that satisfies the objective.

Common actions:

- restart a process (api/daemon/workers)

- rollback config pointer to last known good

- disable a feature flag

- switch model routing to fallback

- clear safe caches (LLM cache, web cache) if corruption suspected

- rebuild indexes from known-good sources

- quarantine suspicious inputs/artifacts



All actions must:

- pass permission gate

- pass trust gate

- pass readiness/approval gate if required

- be logged with rationale



### 4.7 Verify recovery

Verification steps should be explicit and repeatable:

- health endpoints

- smoke tests

- targeted regression tests

- re-run the failing scenario (if safe)

- confirm metrics return within thresholds



### 4.8 Learn and prevent recurrence

After stabilization:

- write a postmortem artifact

- add regression tests where applicable

- propose evolution work (config change, code fix, new evaluator)





## 5. Severity levels and allowed actions



Severity should be computed from:

- blast radius

- irreversibility

- safety/privacy impact

- confidence of maliciousness



A recommended schema:



### 5.1 Sev-0 (Info)

Examples:

- transient timeout, auto-recovered

Allowed:

- record metrics, no action required



### 5.2 Sev-1 (Minor)

Examples:

- intermittent connector errors, minor latency

Allowed:

- throttle, retry policy adjustments, restart connector client



### 5.3 Sev-2 (Major)

Examples:

- persistent failures in a subsystem

Allowed:

- rollback config, restart services, disable noncritical features



### 5.4 Sev-3 (Critical)

Examples:

- suspected security incident, policy bypass attempt

Allowed:

- contain-only by default; emergency actions require approvals

- may trigger emergency shutdown/runbook



### 5.5 Sev-4 (Catastrophic)

Examples:

- confirmed credential compromise, unsafe actuation risk

Allowed:

- emergency shutdown / isolation

- operator escalation mandatory

- preserve forensic evidence





## 6. Containment toolbox



Containment should be granular and reversible.



### 6.1 Tool containment

- disable specific tool operations (write/delete)

- force read-only scopes

- restrict certain connectors

- require approvals for all tool calls temporarily



### 6.2 Network/web containment

- disable web access

- restrict to allowlisted domains only

- enforce stricter content filters

- lower rate limits



### 6.3 Filesystem containment

- restrict to allowlisted paths

- disable writes outside workspace

- quarantine suspicious files



### 6.4 Execution containment

- reduce concurrency

- disable autonomous workers

- route to safe, conservative model

- enforce “dry-run only” for write actions



### 6.5 Data containment

- quarantine suspicious artifacts

- block exports/imports in federation mode

- lock down logs to prevent exfiltration





## 7. Diagnosis methods



### 7.1 “Recent change” analysis

Compare:

- config/policy hashes now vs last known good

- dependency lock changes

- model roster changes

- connector auth changes



### 7.2 Failure fingerprinting

Compute a stable fingerprint:

- exception type + top stack frames

- connector operation id

- schema validation errors

- environment + route signature



Use fingerprints to:

- group incidents

- match known runbooks

- reduce duplicate work



### 7.3 Replay-based reproduction (safe mode)

If you have recorded traces (redacted):

- replay inputs against baseline and current

- compare tool selection, outputs, denials, and latencies



### 7.4 Differential diagnosis (A/B)

When safe:

- run a small cohort through baseline and variant

- isolate causal changes



### 7.5 Security-informed diagnosis

If maliciousness is plausible:

- treat user/inputs as hostile

- never execute “fix scripts” suggested by untrusted content

- verify integrity of artifacts and configs before use





## 8. Remediation patterns



### 8.1 Restart loops

Symptoms:

- repeated crash at startup

Actions:

- capture crash logs

- disable newest optional modules

- rollback config changes

- start in “safe minimal” mode



### 8.2 Connector degradation

Symptoms:

- timeouts, auth failures

Actions:

- switch connector to read-only

- reduce rate, exponential backoff

- rotate ephemeral sessions if configured

- escalate if secrets rotation is needed (approval required)



### 8.3 LLM provider instability

Symptoms:

- high error rates, elevated latency

Actions:

- failover to fallback model/provider

- reduce concurrency

- enable response caching (if safe)

- adjust routing thresholds



### 8.4 Index corruption / vector store issues

Symptoms:

- retrieval failures, slow queries

Actions:

- snapshot current indexes

- rebuild from known-good sources

- verify provenance

- test retrieval quality vs baselines



### 8.5 Policy mismatch / denial spikes

Symptoms:

- workflows blocked unexpectedly

Actions:

- verify policy snapshot change

- roll back policy pack if allowed

- if policy was intentionally updated, update runbooks/UI messaging

- require re-approval if policy drift occurred mid-session



### 8.6 Suspected injection / poisoned inputs

Symptoms:

- manipulation detector triggers, suspicious content patterns

Actions:

- quarantine inputs

- disable web ingestion temporarily

- enforce stricter sanitization

- require human review for tool executions

- run adversarial suite validation





## 9. Governance and approvals for self-healing



### 9.1 Permission gate

Remediation actions still require:

- identity resolution

- scope checks

- delegation validity



### 9.2 Trust gate

Even if permitted:

- trust threshold may block execution

- require dry-run or review



### 9.3 Action readiness and approvals

Actions that may require approvals:

- writing to external systems

- deleting/purging data

- rotating credentials

- changing policy enforcement

- industrial control actions

- federation exports/imports



### 9.4 “Policy drift pause” invariant

If governance/policy files changed during an active healing case:

- pause remediation

- capture new snapshot

- re-run gating

- require re-approval if impact is high





## 10. Audit and telemetry requirements



Self-healing must produce a complete audit trail.



### 10.1 Minimum audit fields per remediation step

- case_id

- timestamp

- actor identity + role

- subsystem + action type

- inputs (redacted)

- outputs (redacted)

- policy references used

- approval references used (if any)

- success/failure + error details



### 10.2 Logs and artifact destinations

Common storage:

- `data/logs/errors/*`

- `data/logs/operations/francis.jsonl`

- `data/logs/audit/*`

- `data/artifacts/reports/*`

- `data/quarantine/*` (for suspicious artifacts)



### 10.3 Redaction policy

All stored artifacts must:

- remove secrets/tokens

- remove raw PII where not required

- preserve enough context to debug safely





## 11. Verification: what “healed” means



A remediation is “successful” only if:



### 11.1 Health checks pass

- API responds

- workers are stable

- queues drain normally



### 11.2 Safety checks pass

- policy engine is active

- guardrails active

- approvals required remain required

- denied actions remain denied where expected



### 11.3 Regression tests pass

- rerun the failing test case

- run a minimal critical suite:

  - tool permission checks

  - injection defenses

  - schema validations

  - smoke retrieval



### 11.4 Metrics return to expected ranges

- latency

- error rate

- denial rate

- cost per request

- memory usage





## 12. Postmortems and continuous improvement



Every Sev-2+ case should produce a postmortem.



Recommended postmortem fields:

- summary

- timeline

- impact (what broke, who affected)

- root cause

- contributing factors

- what worked / what didn’t

- corrective actions (short-term)

- preventative actions (long-term)

- new tests/runbooks added

- trust metric impacts



Link postmortem to:

- incident evidence bundle

- remediation logs

- change/version hashes



If the fix requires persistent change:

- generate a SELF_EVOLUTION proposal and route it through the evolution pipeline.





## 13. Operational runbooks (recommended)



These runbooks should exist (see docs/RUNBOOK.md):



- **Runbook: Stabilize system**

  - actions: disable writes, throttle workers, disable web

  - intended for Sev-2/Sev-3



- **Runbook: Restart core services**

  - api/daemon/workers restart in controlled order

  - verify health endpoints



- **Runbook: Roll back config pack**

  - revert to last known good config snapshot

  - re-run smoke suite



- **Runbook: Quarantine suspicious artifact**

  - move to `data/quarantine/*`

  - record provenance and triggers



- **Runbook: Emergency shutdown**

  - immediate halt of high-risk components

  - preserve evidence and escalate





## 14. Implementation pointers (code map)



Self-healing and recovery modules:

- `src/francis/adversarial/recovery/*`

  - containment, forensics, restoration, compromise detection



Kernel orchestration and workers:

- `src/francis/kernel/*`

  - orchestrator, scheduler, runtime, worker pool



Governance gates:

- `src/francis/governance/*`



Telemetry:

- `src/francis/telemetry/*`



Entry points / ops scripts:

- `scripts/self-heal.ps1`

- `scripts/doctor.ps1`

- `scripts/emergency-shutdown.ps1`





## 15. Appendix — Healing case template (illustrative)



```yaml

case_id: heal.2026-01-01T12-00-00Z.sev2.connector_timeout

opened_at: "2026-01-01T12:00:00Z"

severity: 2

category: reliability

subsystem: connectors.saas.github

signals:

  - type: error_rate

    value: "35% timeouts"

  - type: latency_p95

    value: "+300% vs baseline"



stabilization:

  actions:

    - disable_operations: ["create_issue", "update_issue"]

    - throttle: { per_minute: 10 }

    - route_to_fallback_provider: true



evidence_bundle:

  policy_snapshot: "hash:abcd..."

  config_snapshot: "hash:efgh..."

  logs:

    - "data/logs/errors/..."

  tool_traces:

    - "redacted://trace/..."



diagnosis:

  hypotheses_ranked:

    - "Provider outage or rate limit change"

    - "Credential token expired"

    - "Network egress blocked by policy change"

  chosen_remediation: "backoff + fallback route"



remediation:

  steps:

    - action: set_backoff

      params: { strategy: exponential, max_delay_s: 60 }

    - action: switch_provider

      params: { provider: "secondary" }



verification:

  health_checks: pass

  smoke_tests: pass

  metrics:

    error_rate: "-30%"

    latency_p95: "-40%"



postmortem_required: true



