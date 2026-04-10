==============================================================================

FRANCIS — CONCURRENCY.md

Deterministic concurrency, worker orchestration, and safe parallel execution

==============================================================================



Purpose

-------

This document defines FRANCIS’s concurrency model across:

   - The API service (request handling, websocket streaming)

   - The daemon (background orchestration loops)

   - Workers (task execution, tool calls, simulations, crawlers)

   - Shared state (memory, ledgers, trust metrics, approvals, artifacts)



It explains:

   - What can run in parallel, what must be serialized, and why

   - Concurrency primitives (queues, semaphores, locks, idempotency, retries)

   - Backpressure and overload control

   - Correctness guarantees (ordering, atomicity, exactly-once vs at-least-once)

   - Failure modes (race conditions, deadlocks, retry storms) + mitigations

   - Observability requirements for concurrency



Read alongside:

   - docs/ARCHITECTURE.md

   - docs/API_PERMISSIONS.md

   - docs/GOVERNANCE.md

   - docs/TRUST_MODEL.md

   - docs/CONVERSATION_CONTINUITY.md

   - config/runtime/concurrency.yaml

   - config/runtime/worker_pool.yaml

   - config/runtime/scheduler.yaml

   - config/policies/approvals.yaml

   - config/policies/api_permissions.yaml

   - src/francis/kernel/orchestrator.py

   - src/francis/kernel/scheduler.py

   - src/francis/kernel/worker_pool.py

   - src/francis/chat/message_bus.py

   - src/francis/telemetry/{logging,metrics,tracing}.py



Design stance:

   - Concurrency is a capability multiplier and a correctness multiplier *only*

     when it is governed by explicit invariants.

   - Side effects must be safe under retries and partial failures.

   - Determinism beats throughput for high-risk operations.



==============================================================================





## 0. Executive summary (the contract)



FRANCIS concurrency is governed by **six invariants**:



1) **State updates are append-first**

   - Durable ledgers and audit trails are append-only.

   - Derived state can be rebuilt; the ledger is the source of truth.



2) **Side effects are idempotent or fenced**

   - Any tool operation that can have an external side effect must be:

     - idempotent (safe to repeat), or

     - protected by a fence (a dedupe token / lock / transactional outbox).



3) **High-impact writes are serialized per resource**

   - Writes to the same resource key must not race.

   - “Resource key” is domain-specific: repo+branch, DB table+row-range, file path, ticket id, etc.



4) **Gates are evaluated per action, not per request**

   - Permission checks, trust checks, and approvals apply to the **action**.

   - Parallel steps cannot bypass gates by running “under the same request”.



5) **Backpressure is mandatory**

   - When overloaded: degrade gracefully, shed load, or downgrade to read-only/dry-run.

   - Never let concurrency silently amplify failure.



6) **Observability is non-optional**

   - Every task has: a stable id, causality links, timing, retries, and final outcome.

   - Concurrency without traceability is un-debuggable and unsafe.





## 1. Definitions



### 1.1 Task

A **task** is the smallest schedulable unit of work with:

- inputs

- expected outputs (artifacts, state updates)

- a declared risk class

- declared resource keys (what it touches)

- execution constraints (timeouts, concurrency limits)



### 1.2 Job

A **job** is a collection of tasks with a DAG (dependencies). A job is typically:

- “Answer this question”

- “Run this runbook”

- “Learn this domain”

- “Perform this incident response sequence”



### 1.3 Step

A **step** is a task that is part of a plan; steps are used in audit logs, UI traces, and approvals.

A step can map to one or more tasks if execution is parallelized.



### 1.4 Tool call

A **tool call** is an external integration invocation (connector operation). Tool calls are:

- the highest-risk boundary (external side effects, exfil risk)

- always subject to permission + trust + policy checks



### 1.5 Resource key

A **resource key** is a deterministic identifier used for concurrency control, e.g.:

- `fs:/path/to/file`

- `github:org/repo#branch:main`

- `db:postgres://cluster/db/schema/table`

- `slack:workspace#channel`

- `approval:action_hash:<hash>`



Resource keys are used for:

- serialization (locks)

- rate limiting (per connector / per target)

- audit correlation



### 1.6 Concurrency policy

A **concurrency policy** declares:

- parallelism limits (global, per subsystem, per connector, per resource)

- which risk classes require serialization

- retry policy and timeouts

- backpressure strategy





## 2. Concurrency surfaces in FRANCIS



FRANCIS has multiple concurrency surfaces; each has distinct correctness hazards.



### 2.1 API request concurrency

- Many users/sessions can hit the API concurrently.

- Each request can spawn multiple tasks (fan-out).

- Streaming (websocket) introduces partial-response concerns.



Rules:

- Request handlers must be non-blocking where possible.

- Heavy work goes to workers; request threads/event-loop should not do heavy CPU.



### 2.2 Daemon orchestration concurrency

The daemon runs ongoing loops:

- scheduling

- monitoring

- self-heal checks

- federation sync (if enabled)



Rules:

- Daemon loops must be idempotent across restarts.

- Any “tick” operation must be safe if executed twice.



### 2.3 Worker execution concurrency

Workers run:

- tool calls

- indexing and retrieval tasks

- simulations and evaluations

- domain induction / crawling (if enabled)



Rules:

- Workers must honor:

  - per-connector rate limits

  - per-resource locks

  - global backpressure signals



### 2.4 Shared state concurrency

Shared state includes:

- conversation ledger(s)

- approval records

- trust metrics

- caches

- artifacts



Rules:

- Prefer append-only writes; minimize in-place mutation.

- Any mutable “current state” must be updated via CAS/optimistic checks or guarded by locks.





## 3. The concurrency architecture



### 3.1 High-level execution model


### 3.2 Coordinator vs executor separation

FRANCIS should maintain a strict separation:

- **Coordinator/orchestrator**: decides *what* should run, in what order.

- **Executor/worker**: runs a single task safely and reports outcomes.



Benefits:

- easier reasoning and auditing

- safer retries (executor can be idempotent)

- scalable parallelism without policy drift



### 3.3 Dependency graph (DAG) is the concurrency boundary

Parallelism is allowed only among tasks that are:

- independent per DAG

- safe per resource keys

- allowed per risk class and policy



No task may “start early” unless it is explicitly marked:

- speculative

- dry-run only

- non-side-effecting



### 3.4 Priority classes

Common priority classes:

- **P0**: emergency shutdown / containment

- **P1**: interactive user requests

- **P2**: scheduled maintenance jobs

- **P3**: background learning, indexing, exports



Scheduler must enforce:

- bounded queues per priority

- starvation avoidance (age-based promotion)





## 4. Concurrency primitives and mechanisms



### 4.1 Queues (work dispatch)

At minimum:

- an in-memory queue for local dev

- optionally a durable queue for production (recommended)



Required queue features:

- visibility timeout / lease

- retry count and backoff metadata

- idempotency key support

- priority lanes



### 4.2 Semaphores (global concurrency caps)

Use semaphores for:

- maximum concurrent tool calls

- maximum concurrent web fetches

- maximum concurrent simulations

- maximum concurrent LLM requests



Example semaphore categories:

- `global.tool_calls`

- `global.llm_requests`

- `global.web_fetches`

- `connector.github`

- `connector.slack`

- `connector.db.postgres`



### 4.3 Rate limiting (per connector and per target)

Rate limiting is not just “global”; it must be hierarchical:

- per connector (GitHub vs Slack)

- per tenant/workspace/org

- per endpoint (some APIs have tighter sub-limits)



Recommended models:

- token bucket

- leaky bucket

- concurrency-limited + jittered backoff on 429



### 4.4 Locks (serialization by resource key)

Locks are used to prevent races between tasks.



Required lock properties:

- key-based (resource key)

- TTL/lease (avoid deadlocks on crashes)

- re-entrant (optional; depends on execution model)

- observable (lock acquisition logged in trace)



Recommended lock tiers:

- **In-process lock**: fastest; safe only within one process.

- **Host-level lock**: file lock or OS primitive.

- **Distributed lock**: needed when multiple workers/nodes operate on same resource keys.



If distributed locks are not enabled, the scheduler must ensure that

tasks with the same resource key are never scheduled onto different processes concurrently.



### 4.5 Idempotency keys (exactly-once intent)

For any task with side effects:

- derive an idempotency key from:

  - job_id

  - step_id

  - operation name

  - normalized target (resource key)

  - normalized payload hash



Example:

`idem = sha256(job_id + step_id + tool + operation + resource_key + payload_hash)`



Use the idempotency key to:

- dedupe repeated tasks after retries

- fence tool calls (send once)

- prevent double approvals/executions



### 4.6 Transactional outbox (side-effect safety)

When a task must update internal state *and* call an external tool, a safe pattern is:



1) Write “intent” to a durable outbox (append-only) with idempotency key

2) Commit internal state change

3) A dispatcher reads outbox and performs the external call

4) Record “delivered” status, keyed by idempotency key

5) Retries are safe because delivery is deduped



This avoids the classic failure:

- external call succeeds

- internal state write fails

- system retries and calls external again



### 4.7 Optimistic concurrency control (OCC)

For “current state” documents (trust levels, environment state, etc.):

- store version numbers

- update with compare-and-swap semantics



Example:

- read `current_state` at version 12

- propose update -> write only if version is still 12

- else re-read and merge



### 4.8 Cancellation and timeouts

All tasks must:

- honor cancellation tokens (job cancellation)

- enforce timeouts

- distinguish between:

  - soft timeout (stop trying, report partial)

  - hard timeout (force stop, containment)



Timeout policy must be explicit per risk class:

- interactive tasks shorter

- batch tasks longer

- tool calls bounded with retries





## 5. Concurrency under governance and safety



Concurrency becomes dangerous when it lets actions slip past gates, or

when it causes duplicated/contradictory side effects.



### 5.1 Gate ordering (required)

Every side-effecting operation must pass, in order:



1) **Permission gate**

   - identity, delegation, scope, resource constraints

2) **Policy engine**

   - domain policy constraints (privacy, offensive security, filesystem, web access)

3) **Trust/readiness gate**

   - trust thresholds, approvals required, environment mode constraints

4) **Sandbox**

   - filesystem/network limits, process isolation

5) **Rate limit + lock**

   - connector concurrency/rate

   - per-resource lock acquisition

6) **Execution**

7) **Audit logging (decision + outcome)**

   - always log allow/deny and outcome, with redaction rules



If any stage fails: deny safely, record the denial, and do not “partially execute”.



### 5.2 Approvals are concurrency-sensitive

Approvals must be safe under concurrent attempts:

- two workers might try to execute the same “approved” action

- one worker might execute while another revokes approval



Rules:

- approval records must be keyed by action hash/idempotency key

- execution must record a “consumed approval” reference

- revocation must be observable and block future executions

- emergency approvals must have short TTL and strict audit traces



### 5.3 Delegation revocation propagation

Revoking delegation must:

- invalidate cached auth decisions

- cancel or quarantine queued tasks that relied on revoked delegation

- force re-check of gates before execution (never rely on stale checks)



### 5.4 Trust updates under concurrency

Trust metrics update must be:

- monotonic where possible (append events)

- aggregated deterministically

- protected against double-counting (idempotency keys for events)



Example:

- “tool_call_success” metric increments only once per idempotency key.





## 6. Ordering and determinism



### 6.1 Deterministic DAG evaluation

Even with concurrency, plan execution should be reproducible:

- stable sort of tasks by (priority, dependency depth, stable task id)

- stable merge of multi-agent outputs (explicit tie-breaker rules)



### 6.2 Event ordering model

FRANCIS should define ordering for:

- conversation ledger events

- decision events

- tool events



Recommended:

- each event includes:

  - `event_id` (unique)

  - `job_id`, `task_id`, `step_id`

  - `parent_event_id` (causality)

  - `timestamp`

  - `sequence` (monotonic per stream, if feasible)



If strict total ordering is not feasible, enforce:

- per-stream ordering (e.g., per conversation, per job)

- causality links for cross-stream reconstruction



### 6.3 Exactly-once vs at-least-once semantics

Be explicit:



- **Internal logs/ledgers**: aim for at-least-once append (duplicates allowed but dedupable)

- **External side effects**: must behave as exactly-once intent using idempotency/fencing

- **State projections**: derived views; can be rebuilt and should tolerate duplicates





## 7. Backpressure and overload control



### 7.1 Why backpressure matters

Without backpressure, concurrency amplifies:

- timeouts

- retries

- rate limits

- cascading failures

- cost runaway (LLM calls, web requests)



### 7.2 Backpressure toolbox

FRANCIS should support:

- bounded queues (reject or defer when full)

- priority lanes (P1 interactive protected from P3 background)

- concurrency caps (semaphores)

- adaptive throttling (reduce parallelism on error)

- load shedding (drop low-priority tasks)

- downgrade modes:

  - read-only

  - dry-run

  - “plan-only”

  - “summarize existing state only”



### 7.3 Retry storms and jitter

Retry policy must include:

- exponential backoff

- jitter

- maximum attempts

- circuit breaker integration



A circuit breaker is recommended per connector:

- open on sustained failures / rate-limits

- half-open test calls

- close on recovery



### 7.4 Cost-aware throttling

Some tasks have cost multipliers:

- LLM calls

- web crawling

- simulations



Throttling should consider:

- estimated cost per task

- daily budget caps (if enabled)

- environment mode (regulated/airgapped may disallow web entirely)





## 8. Common concurrency failure modes (and mitigations)



### 8.1 Race conditions (state corruption)

Symptoms:

- inconsistent “current_state”

- missing or duplicated artifacts

- conflicting trust updates



Mitigations:

- OCC on mutable state

- append-only event logs

- per-resource locks

- deterministic reducers



### 8.2 Deadlocks (lock cycles)

Symptoms:

- tasks waiting forever

- queues draining but nothing completes



Mitigations:

- enforce global lock ordering rules (lexicographic by key)

- lock timeouts/TTLs

- avoid holding multiple locks across awaits/tool calls

- detect and kill stuck tasks



### 8.3 Livelocks (endless retries)

Symptoms:

- work repeats but never commits

- high CPU, no progress



Mitigations:

- bounded retries

- circuit breakers

- fallback strategies

- human escalation for repeated failures



### 8.4 Thundering herd

Symptoms:

- many workers wake on the same event and hit the same API

- rate limits spike



Mitigations:

- leader election for certain loops

- jittered schedules

- centralized rate limiting / token sharing



### 8.5 Split-brain (distributed scheduling)

Symptoms:

- two schedulers both think they’re leader

- duplicate execution



Mitigations:

- explicit scheduler leadership mechanism

- durable leases

- idempotency keys on all side effects

- “single writer” constraints for critical streams



### 8.6 Partial failure across side effects

Symptoms:

- external tool executed, internal state not updated (or vice versa)



Mitigations:

- transactional outbox pattern

- sagas (compensating actions) where feasible

- post-action reconciliation jobs





## 9. Concurrency patterns FRANCIS should use



### 9.1 Fan-out / fan-in (parallel research or analysis)

Pattern:

- split into independent tasks

- run in parallel

- merge results deterministically



Rules:

- fan-out only for read-only or non-side-effect tasks unless fenced

- merge must cite provenance and record conflicts



### 9.2 Speculative execution (safe variant)

Allowed only when:

- tasks are read-only OR

- tasks are dry-run OR

- side effects are fully fenced and reversible



Speculative results must be marked as such and revalidated before commit.



### 9.3 Two-phase plan execution (recommended default)

Phase 1: Plan + Review

- build DAG

- enumerate resource keys

- determine required approvals

- run policy/trust simulation (“can we execute?”)



Phase 2: Execute

- acquire locks

- run tasks

- record outcomes and artifacts



This reduces “mid-execution surprises”.



### 9.4 Sagas for multi-resource workflows

When one logical action spans multiple external systems:

- model as a saga with ordered steps

- each step has:

  - forward action

  - compensating action (if possible)

- the saga state is appended to a durable log



If compensating actions do not exist, require:

- human approval

- explicit “irreversible” flag in logs/UI





## 10. Testing and validation of concurrency



### 10.1 Deterministic test harness

Concurrency tests should run under a deterministic scheduler (where feasible):

- fixed seeds

- controlled task ordering

- simulated timeouts and retries



### 10.2 Fault injection

Required fault types:

- tool call timeouts

- partial responses

- rate-limit responses

- worker crash mid-task

- scheduler restart mid-job

- lock lease expiration



### 10.3 Property-based tests (recommended)

Examples:

- “no more than one side effect per idempotency key”

- “ledger events remain append-only”

- “approval cannot be consumed twice”

- “revoked delegation blocks subsequent execution”



### 10.4 Load tests

Validate:

- backpressure triggers

- queue stability

- latency under mixed priorities

- no runaway retries





## 11. Observability requirements (concurrency visibility)



### 11.1 Tracing

Every task should emit spans with:

- `job_id`

- `task_id`

- `step_id`

- `resource_keys`

- `attempt`

- `idempotency_key`

- gate outcomes (permission/trust/policy)

- tool request ids (redacted as needed)



### 11.2 Metrics

Minimum metrics:

- queue depth per priority lane

- active workers

- task success/failure rates

- retry counts

- time-to-first-byte for streaming

- per-connector 429s / errors

- lock contention rate

- circuit breaker open/close events



### 11.3 Logs (structured)

Logs must be structured and correlated:

- never rely on string parsing

- preserve causality links



For sensitive contexts:

- redact payloads

- keep hashes, sizes, and identifiers





## 12. Configuration knobs (runtime)



These are conceptual knobs; the actual source of truth is `config/runtime/*`.



### 12.1 Concurrency configuration

Expected fields:

- `global_max_workers`

- `max_concurrent_tool_calls`

- `max_concurrent_llm_requests`

- `max_concurrent_web_fetches`

- per-connector limits

- per-risk-class serialization rules



### 12.2 Scheduler configuration

Expected fields:

- priority queue sizes

- default timeouts

- retry policies

- backoff parameters

- jitter

- task leasing/visibility timeouts



### 12.3 Worker pool configuration

Expected fields:

- process vs thread execution mode

- worker count per queue

- CPU/memory limits (where supported)

- graceful shutdown and drain behavior





## 13. Practical rules of thumb (developer guidance)



### 13.1 Safe by default

- Default concurrency for **writes**: 1 per resource key

- Default concurrency for **external side effects**: low and fenced

- Default concurrency for **reads**: parallel, but rate-limited



### 13.2 Never hold locks across tool calls

Acquire lock → prepare immutable request → release lock if safe → call tool

OR

Acquire lock → call tool only if tool call is short and bounded → release quickly



Long tool calls while holding locks are a deadlock factory.



### 13.3 Normalize resource keys early

If resource keys are inconsistent:

- locks will not work

- dedupe will not work

- metrics will lie



### 13.4 Prefer append-only event logs

When in doubt:

- append an event

- rebuild projections

- avoid “mutating in place” in the hot path



### 13.5 Make retries safe

Every retry must not “repeat the world”:

- ensure idempotency keys are used

- ensure tool calls can dedupe or are fenced internally





## 14. Implementation pointers (code map)



Concurrency + orchestration:

- `src/francis/kernel/orchestrator.py`

- `src/francis/kernel/scheduler.py`

- `src/francis/kernel/worker_pool.py`

- `src/francis/kernel/realtime_kernel.py`

- `src/francis/kernel/distributed_kernel.py`



Chat/event flow:

- `src/francis/chat/message_bus.py`

- `src/francis/chat/router.py`

- `src/francis/chat/sessions.py`



Governance gates (must be concurrency-safe):

- `src/francis/governance/api_permission_gate.py`

- `src/francis/governance/action_readiness.py`

- `src/francis/governance/approvals.py`



Telemetry (required for concurrency correctness):

- `src/francis/telemetry/logging.py`

- `src/francis/telemetry/metrics.py`

- `src/francis/telemetry/tracing.py`

- `src/francis/telemetry/audit.py`





## 15. Operational checklist (production readiness)



Before enabling high parallelism:



- [ ] Idempotency keys are implemented for all side-effect tasks

- [ ] Per-connector rate limiting is enforced and tested

- [ ] Per-resource locking strategy is defined and observed

- [ ] Approval consumption is atomic and deduped

- [ ] Delegation revocation propagates to queued tasks

- [ ] Backpressure policies are configured (bounded queues, load shedding)

- [ ] Circuit breakers are enabled for external connectors

- [ ] Tracing links job → tasks → tool calls

- [ ] Metrics dashboards exist for queue depth, retries, 429s, lock contention

- [ ] Chaos tests validate safe behavior under crashes and timeouts





# End of CONCURRENCY.md





