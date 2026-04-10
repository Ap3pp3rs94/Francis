==============================================================================

FRANCIS — SYSTEM_PROFILING.md

System profiling, baselines, drift detection, inventories, and observability

==============================================================================



Purpose

-------

This document defines how FRANCIS profiles the host system(s) it runs on and

maintains a trustworthy, auditable picture of:

   - hardware and OS characteristics

   - software inventories (services, runtimes, dependencies)

   - network topology and runtime connectivity

   - performance baselines and drift over time

   - operational health signals used for safety, governance, and execution



System profiling is a prerequisite for:

   - safe tool execution (sandboxing and resource limits)

   - deterministic behavior across environments (dev/edge/prod/airgapped)

   - incident response (forensics, rollback, containment)

   - capacity planning (worker pools, model hosting, caches)

   - trust measurement (detecting tampering, drift, or misconfiguration)



Read alongside:

   - docs/ARCHITECTURE.md

   - docs/CONCURRENCY.md

   - docs/GOVERNANCE.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/LOCAL_MODELS.md

   - docs/OLLAMA.md

   - docs/WEB_ACCESS.md

   - docs/POLICIES.md

   - config/environments/*.yaml

   - config/policies/filesystem.yaml

   - config/policies/networks.yaml

   - config/policies/sandbox.yaml

   - config/policies/data_governance.yaml

   - config/runtime/*.yaml

   - src/francis/system_intelligence/*

   - src/francis/telemetry/*

   - data/system/* (baselines, drift, inventories, profiles, topologies)

   - data/logs/* (operations, audit, errors)



Design stance

------------

   - Profile safely: never exfiltrate secrets or sensitive host data.

   - Profile deterministically: results must be reproducible and comparable.

   - Profile with provenance: every profile snapshot is timestamped, hashed,

     and linked to policy/environment configuration.

   - Prefer least-invasive collection: collect only what is needed for safety

     and operational correctness; redact by default.

   - Treat profiling as security-relevant: drift may indicate tampering.



==============================================================================





## 1. What "system profiling" means in FRANCIS



System profiling is the ongoing process of:

- **observing** the runtime environment

- **summarizing** it into structured artifacts

- **comparing** current state to known-good baselines

- **detecting drift** that could affect correctness or safety

- **feeding** results into:

  - governance (readiness gates)

  - trust scoring

  - scheduler and worker pool configuration

  - sandbox and permission boundaries

  - incident response workflows



Profiling does **not** mean:

- scanning arbitrary user files for content

- collecting secrets

- sending telemetry off-host by default





## 2. Why profiling matters (safety + reliability)



### 2.1 Safety

Many unsafe outcomes come from environment mismatch:

- wrong model backend

- missing sandbox constraints

- unexpected network reachability

- services running with excessive privileges

- altered binaries or libraries



Profiling provides early warning and gating signals.



### 2.2 Reliability

FRANCIS relies on:

- a coordinator (API + orchestration)

- optional local model hosting (Ollama or similar)

- worker pools and caches

- connectors to external services (where allowed)



Profiling ensures the system can execute tasks predictably across dev/edge/prod.





## 3. Scope: what gets profiled



### 3.1 Host and OS layer

- OS name/version/build

- kernel version

- CPU architecture and core count

- RAM, swap, and memory pressure signals

- storage volumes and free space (coarse)

- time sync status (coarse; drift matters for audits)

- virtualization/containerization detection



### 3.2 Hardware layer

- CPU model identifiers (coarse)

- GPU presence (CUDA/ROCm/Metal availability) if relevant

- accelerators (optional)

- disk type and throughput characteristics (optional, coarse)

- thermal throttling indicators (optional)



### 3.3 Software inventory

- installed runtimes (python, node, rust, etc.)

- critical services and their versions:

  - API service

  - daemon

  - worker processes

  - local model servers (Ollama)

  - vector stores (if configured)

  - databases (if configured)

- Python dependency freeze (hashed, not raw tokens)

- Node package lock signature (hashed)

- container image tags and digests (if in containers)



### 3.4 Process and service topology

- which FRANCIS components are running

- ports bound (only for known components)

- health endpoints (internal only)

- worker pool size, queue depth, and latency



### 3.5 Network and connectivity (policy-bound)

- active interfaces (coarse metadata)

- DNS configuration (coarse)

- outbound reachability (allowed domains only)

- required endpoints for configured connectors

- federation peer connectivity (if enabled)



### 3.6 Security posture indicators (non-secret)

- privilege level (user vs admin)

- container isolation status

- filesystem policy compliance (sandbox boundaries)

- presence of suspicious drift in key directories

- signing/hashing verification for critical artifacts (optional)





## 4. Data products: what gets written where



System profiling output is recorded under `data/system/*` with strict governance.



Recommended structure:



- `data/system/profiles/`

  - `profile_<timestamp>.json`

  - `profile_latest.json` (pointer/rollup)

- `data/system/inventories/`

  - `services_<timestamp>.json`

  - `deps_<timestamp>.json`

  - `containers_<timestamp>.json` (if applicable)

- `data/system/baselines/`

  - `baseline_<environment>.json`

  - `baseline_hashes.json`

- `data/system/drift/`

  - `drift_<timestamp>.json`

  - `drift_summary.jsonl` (append-only timeline)

- `data/system/topologies/`

  - `topology_<timestamp>.json`



The system should also record a linked audit event:

- `data/logs/audit/*` referencing:

  - profile id

  - baseline id

  - drift result

  - active policy snapshot

  - environment name





## 5. Baselines: establishing “known good”



### 5.1 Baseline definition

A baseline is a canonical snapshot for an environment (dev, edge, prod, regulated).

Baselines should include:

- expected component versions and config hashes

- expected service presence/absence

- expected resource bounds

- expected network policies

- expected enabled/disabled features



Baselines must be:

- **versioned**

- **signed or hashed**

- **tied to an environment config** (e.g., `config/environments/production.yaml`)



### 5.2 Baseline creation workflow

Recommended workflow:

1) deploy environment

2) run profiler in “baseline mode”

3) review baseline output

4) approve baseline (governance approval if required)

5) store in `data/system/baselines/`

6) pin baseline hash into audit log and optionally into repo config



### 5.3 Baseline evolution

Baselines change when:

- dependencies update

- new connectors are added

- new model backends are installed

- policy config changes



Baseline updates should require:

- explicit change log entry

- re-evaluation suite run

- approval when in regulated/high availability modes





## 6. Drift detection



### 6.1 Drift categories

Drift is classified by severity:



**Green (expected drift)**

- routine log growth

- cache growth

- expected minor performance variance



**Yellow (review drift)**

- new service detected

- dependency version differs from baseline

- repeated performance regressions

- unexpected network reachability



**Red (block drift)**

- critical binary hash mismatch

- policy config mismatch

- privilege escalation detected

- unexpected connector enabled

- suspicious filesystem changes in protected paths



### 6.2 Drift report format

A drift report should include:

- timestamp

- baseline id and hash

- observed profile id and hash

- diff summary (human-readable)

- structured diffs per subsystem:

  - runtimes

  - services

  - network

  - filesystem protections

- severity classification

- recommended action:

  - allow

  - warn

  - require approval

  - block execution

  - emergency shutdown recommendation



### 6.3 Drift gating

Drift feeds into:

- **Action Readiness Gate** (can downgrade readiness or force approval)

- **Trust** (drift can reduce trust score)

- **Scheduler** (may reduce concurrency when under resource pressure)

- **Sandbox** (tighten limits when environment is unstable)





## 7. Performance profiling and capacity baselines



### 7.1 Metrics collected (typical)

- API latency p50/p95/p99

- worker queue latency and backlog

- model inference latency (if local models)

- cache hit/miss rate

- memory usage and GC pressure (per runtime)

- disk IO utilization (coarse)

- network throughput (coarse)



### 7.2 Performance baselines

Performance baselines should be created per environment because:

- dev laptop vs edge device vs server differs

- local model hardware acceleration differs



Store:

- baseline windows (e.g., 15 minutes under typical load)

- variance bounds (tolerances)

- “redline thresholds” for safety (e.g., memory pressure > X => block)



### 7.3 Use in scheduler

Scheduler can adapt:

- scale worker pool down when memory pressure rises

- delay expensive tasks when IO is saturated

- route to lighter model profiles when under load

- disable non-critical background jobs in regulated/critical modes





## 8. Integration with governance, trust, and safety



### 8.1 Governance

System profiling produces inputs for:

- readiness mode selection

- approval requirements (if drift is yellow/red)

- audit record completeness



### 8.2 Trust model

Trust can incorporate:

- baseline conformity score

- drift history

- incident history correlations

- measured reliability by component



Trust changes must be logged with:

- evidence references (profile + drift report)

- reversible reasoning (why did trust change?)



### 8.3 Security posture

Profiling supports:

- anomaly detection

- compromise detection triggers

- forensic preservation actions (when configured)

- emergency shutdown gating (see scripts/emergency-shutdown.ps1)





## 9. Privacy, data governance, and redaction rules



Profiling must adhere to strict redaction:



Allowed (generally):

- versions, hashes, counts, coarse capacity measures

- service names (for known FRANCIS components)

- policy/environment identifiers

- non-secret host identifiers (prefer anonymized)



Never store:

- secrets (tokens, keys, connection strings)

- raw environment variables

- full file contents from user directories

- raw email/chat payloads

- regulated datasets unless explicitly authorized and encrypted



Recommended safeguards:

- hash sensitive strings before writing

- whitelist-based collection (explicit allowed fields)

- policy-driven allowlist of directories for filesystem inspection

- write artifacts to `data/system/*` only (controlled zone)





## 10. Implementation overview (module map)



FRANCIS’s profiling is implemented under `src/francis/system_intelligence/`.



Key modules:



- `probe/os_profiler.py`

  - OS and kernel facts, virtualization detection



- `probe/hardware_profiler.py`

  - CPU/GPU/memory/storage coarse facts



- `probe/service_inventory.py`

  - running services, FRANCIS component presence, ports (known only)



- `probe/app_inventory.py`

  - installed runtime facts, dependencies hash snapshots



- `probe/network_mapper.py`

  - policy-constrained topology and reachability checks



- `probe/baseline_builder.py`

  - baseline generation from profile snapshots



- `probe/drift_detector.py`

  - baseline comparison + severity classification



- `modeling/system_profile_builder.py`

  - merges probe outputs into one canonical profile artifact



- `modeling/topology_builder.py`

  - builds topology artifacts for UI/diagnostics



- `export/to_reports.py`

  - generates human-friendly reports



Outputs are logged via:

- `src/francis/telemetry/*`

and stored under:

- `data/system/*` and `data/logs/*`





## 11. Operational runbooks (recommended)



### 11.1 Initial setup

1) select environment config (dev/edge/prod/regulated)

2) run profiler → store profile snapshot

3) build baseline → review and approve

4) enable drift detection schedule

5) integrate readiness gate thresholds



### 11.2 On drift warning

1) inspect drift report

2) verify whether change is expected (deploy event)

3) if expected: update baseline via controlled process

4) if unexpected: treat as security incident (containment + forensics)



### 11.3 Pre-deploy check

- run profiler

- confirm baseline conformity

- run evaluation suites (especially trust/safety)

- only then scale up workers or enable write actions



### 11.4 Post-incident verification

- freeze artifacts

- run profiler in forensic mode (policy-bound)

- verify hashes and configs

- restore baseline conformity

- document trust impact and approvals





## 12. UI requirements (Chat UI / operations)



The UI should expose:

- current environment and baseline id

- drift status indicator (green/yellow/red)

- recent profiling timeline

- ability to expand:

  - system profile snapshot

  - drift report

  - linked policy snapshot

- clear explanation of any readiness downgrade due to drift





## 13. Failure modes and mitigations



### 13.1 False positives in drift

Mitigation:

- tolerances for expected variance

- allowlist scheduled maintenance windows

- attach deploy/version metadata to profiles



### 13.2 Blind spots

Mitigation:

- baseline includes explicit coverage list

- “coverage gaps” reported as part of profile



### 13.3 Profiling becomes a data leak vector

Mitigation:

- strict redaction pipeline

- policy-driven allowlist collection

- never export profiling artifacts by default



### 13.4 Profiling overhead impacts performance

Mitigation:

- tiered profiling:

  - fast (heartbeat)

  - standard (scheduled)

  - deep (manual/incident mode)

- rate limits and concurrency controls





## 14. Recommended profile artifact schema (high level)



A typical `profile_*.json` should include:



- `profile_id`, `timestamp`, `environment`

- `policy_snapshot_hash`

- `system`

  - os, kernel, arch

- `hardware`

  - cpu, memory, gpu (coarse)

- `services`

  - components, versions, health

- `runtimes`

  - python/node versions, dependency hashes

- `network`

  - connectivity summary (policy-allowed only)

- `storage`

  - free space summary (coarse)

- `security_posture`

  - privilege level, sandbox status

- `hashes`

  - artifact integrity hashes

- `notes`

  - redaction summary, coverage gaps



Validation should reference:

- `schemas/system_profile.schema.json`





# End of SYSTEM_PROFILING.md



