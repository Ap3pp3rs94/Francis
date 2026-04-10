==============================================================================

FRANCIS — TEMPORAL_INTELLIGENCE.md

Time, recency, versioning, memory timelines, and change-aware reasoning

==============================================================================



Purpose

-------

This document defines how FRANCIS represents, reasons about, and enforces

time-aware behavior across:

   - memory and conversation continuity

   - web research and recency validation

   - domain knowledge evolution and versioning

   - system profiling and drift over time

   - governance, approvals, and audit trails



"Temporal intelligence" means FRANCIS can:

   - distinguish old facts from current facts

   - cite and validate recency where freshness matters

   - track how beliefs, policies, and capabilities change

   - avoid unsafe extrapolation from stale data

   - provide reproducible outputs by anchoring to timestamps + versions



Read alongside:

   - docs/CONVERSATION_CONTINUITY.md

   - docs/MEMORY.md

   - docs/DOMAIN_INTELLIGENCE.md

   - docs/WEB_ACCESS.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/GOVERNANCE.md

   - docs/SYSTEM_PROFILING.md

   - config/policies/web_access.yaml

   - config/policies/data_governance.yaml

   - src/francis/temporal/*

   - src/francis/chat/continuity/*

   - src/francis/internet/validation/recency_validator.py

   - data/domains/*/temporal/*

   - data/system/* (profiles/drift/baselines)

   - data/trust/levels/history.jsonl



Design stance

------------

   - Default to timestamped, versioned, explainable decisions.

   - Be conservative when freshness is uncertain.

   - Prefer explicit dates over relative time words ("yesterday") in artifacts.

   - Time is part of safety: stale assumptions can cause real harm.



==============================================================================





## 1. Core concepts



### 1.1 Time as a first-class dimension

FRANCIS treats time as part of the data model, not as an afterthought.



Every artifact that matters (decisions, memories, baselines, policies, exports)

should be:

- timestamped

- versioned (where applicable)

- linked to provenance (source + context)



### 1.2 Recency vs truth

A statement can be:

- **true but outdated** (e.g., “CEO was X”)

- **recent but unreliable** (e.g., unverified forum claim)

- **recent and reliable** (primary sources, audited tool results)



Temporal intelligence requires evaluating both:

- **freshness**

- **credibility**



### 1.3 Temporal validity window

Many facts are only valid within a time window:

- prices, schedules, laws, policies

- leadership, org charts

- system state

- scientific consensus edges and evolving guidance



FRANCIS must represent “valid_from / valid_until” when feasible, or at least

acknowledge uncertainty.



### 1.4 Event time vs ingestion time

Two timestamps matter:

- **event_time**: when the thing happened in the world

- **ingested_at**: when FRANCIS learned/recorded it



Ingestion time can be misleading if the source describes past events.



### 1.5 Temporal causality

Temporal ordering matters for reasoning:

- a decision made *before* evidence was available is different from one made after

- drift detected *after* a deploy is not the same as drift detected randomly

- approvals must be valid at the time of execution





## 2. Where temporal intelligence shows up in FRANCIS



### 2.1 Conversation continuity and memory timelines

- Conversation summaries are time-indexed and appended/rolled forward.

- “What the user said” must preserve ordering and timestamps.

- Retrieval should bias toward:

  - relevant

  - recent

  - high-confidence

  - policy-compatible



Primary storage:

- `data/conversations/ledger/ledger.jsonl` (append-only)

- `data/conversations/summaries/rolling_summary.md` (rolling synthesis)

- `data/memory/*` (episodic/semantic/working)



### 2.2 Domain learning (induction + evolution)

As domains evolve, FRANCIS must:

- store versions of induced beliefs

- record why a belief changed

- preserve old versions for audit and rollback



Primary storage:

- `data/domains/<domain>/temporal/versions/*`

- `data/domains/<domain>/history/*`

- `data/evolution/*`



### 2.3 System profiling and drift

System state is time-varying:

- deployments, package upgrades, config changes

- load patterns and performance profiles



Temporal intelligence is required to:

- compare “now” to “baseline”

- correlate drift events with deploy events

- avoid false positives during known windows



Primary storage:

- `data/system/profiles/*`

- `data/system/drift/*`

- `data/system/baselines/*`



### 2.4 Web research and recency validation

Web-derived claims require:

- source time extraction (publish date, updated date)

- event-time inference (if clearly indicated)

- freshness scoring and conflict resolution



Primary modules:

- `src/francis/internet/validation/recency_validator.py`

- `src/francis/internet/research/*`

- `src/francis/domain_intelligence/induction/web_learning.py`





## 3. Temporal data model (recommended fields)



When FRANCIS records time-aware objects, prefer explicit fields:



- `id` (stable)

- `event_time` (ISO 8601, UTC preferred)

- `ingested_at` (ISO 8601)

- `valid_from` / `valid_until` (optional)

- `timezone` (if relevant)

- `source` (URI, tool reference, doc id)

- `provenance` (method, extractor, confidence)

- `hash` (content hash)

- `supersedes` / `superseded_by` (version chain)

- `reason_for_change` (for version transitions)



Objects that should carry this:

- decisions

- trust changes

- policy snapshots

- domain beliefs

- approvals

- drift events

- research claims





## 4. Recency scoring and freshness policy



### 4.1 Freshness is context-dependent

FRANCIS must decide whether freshness matters.



Examples where freshness is critical:

- security advisories

- legal compliance requirements

- pricing and availability

- schedules, operating hours

- “latest” anything



Examples where freshness is less critical:

- stable math facts

- long-established historical dates

- basic physics constants



### 4.2 Freshness classes (recommended)

Define classes used by recency validator:



- **F0 (timeless)**: generally stable; freshness low importance

- **F1 (slow-changing)**: months/years acceptable

- **F2 (medium-changing)**: prefer within ~6 months

- **F3 (fast-changing)**: prefer within ~90 days

- **F4 (very fast)**: prefer within ~60 days

- **F5 (latest required)**: prefer within ~30 days or explicitly current



These classes should map to:

- query strategy

- citation requirements

- confidence penalties for stale sources

- governance gating for high-stakes tasks



### 4.3 Recency validation pipeline

For each web claim:

1) Extract publish/updated time if present.

2) Detect event-time (e.g., “In 2021…”).

3) Assign freshness class based on task category.

4) Score freshness vs requirement.

5) If insufficient:

   - search for more recent sources

   - warn or abstain if still uncertain

6) Log recency decision as part of evidence record.





## 5. Temporal conflict resolution



When sources conflict, FRANCIS should apply rules in order:



1) **Prefer audited tool outputs** over scraped text.

2) **Prefer primary sources** (official docs, direct statements).

3) **Prefer more recent evidence** *only if* freshness matters for the claim.

4) If still ambiguous:

   - present multiple hypotheses

   - attach confidence estimates

   - recommend verification steps

5) For high-impact decisions:

   - require approval

   - default to conservative action (least irreversible)



This logic should be encoded in:

- synthesis modules

- consensus builder logic

- explanation artifacts





## 6. Temporal reasoning in planning and execution



### 6.1 Time-aware planning

Plans must include:

- ordering constraints

- time windows (when actions are allowed)

- deadlines and expirations

- expected durations (bounded by uncertainty)



### 6.2 Expiration-aware execution

Execution must enforce:

- delegation expiration

- approval expiration

- scope time windows

- rate limits per time window

- “cooldown” after failures or drift



### 6.3 Replayability

FRANCIS should support replay:

- given a timestamp and policy snapshot, reproduce:

  - what evidence was available

  - what decision was made

  - why it was made



This is required for:

- audits

- incident review

- trust certification

- debugging nondeterministic outcomes





## 7. Versioning model (domains, policies, capabilities)



### 7.1 Domain versions

A domain’s induced knowledge should be versioned:

- `v1`, `v2`, etc.

- each version includes:

  - summary

  - evidence set

  - confidence scores

  - drift/changes from previous

  - compatibility notes



### 7.2 Policy snapshots

Policies must be treated as time-sensitive:

- policy changes can change what’s allowed

- approvals may need revalidation if policy changed



Recommendation:

- each session pins a `policy_snapshot_hash`

- changes trigger:

  - UI warning

  - readiness recalculation

  - possible re-approval requirement



### 7.3 Capability versions

Capabilities evolve:

- connector updates

- model routing changes

- sandbox improvements



Track:

- capability id

- version

- behavior changes

- regression risks

- evaluation results by version



Primary storage:

- `data/evolution/*`

- `data/system/inventories/*`





## 8. Temporal intelligence in trust and governance



### 8.1 Trust history

Trust is time-dependent:

- it can decay without evidence

- it can increase with repeated correct outcomes

- it can drop sharply after drift/incidents



Primary store:

- `data/trust/levels/history.jsonl`



Trust changes should include:

- timestamp

- reason category

- evidence links

- before/after trust states



### 8.2 Governance readiness over time

Readiness can change due to:

- time-of-day constraints

- environment mode

- recent incidents

- new drift events

- expired approvals



Readiness should be recalculated when:

- policy changes

- drift changes

- approvals expire

- new high-risk evidence appears





## 9. Storage: temporal artifacts and retention



### 9.1 Append-only logs for auditability

Use JSONL where possible:

- events can be appended

- tampering is easier to detect

- incremental processing is easy



Examples:

- ledger.jsonl

- trust history.jsonl

- drift_summary.jsonl

- harmful_content_log.jsonl



### 9.2 Snapshots for state

Use JSON snapshots for current state:

- current trust state

- current baselines

- current policy snapshot references



### 9.3 Retention policy

Retention should be policy-driven:

- regulated environments may require longer retention and stronger immutability

- consumer/dev environments may have shorter retention



Retention must include:

- secure deletion semantics (if required)

- immutable audit segments (if required)

- export controls for federation sharing





## 10. Implementation pointers (code map)



Temporal intelligence modules:

- `src/francis/temporal/*`

  - `adaptation/*` (continuous learning, drift correction)

  - `forecasting/*` (regulatory change tracking, horizon scanning)

  - `history/*` (decision replay, archaeology)

  - `versioning/*` (domain version manager, rollback)



Related:

- `src/francis/chat/continuity/*` (ledger, summaries, retrieval)

- `src/francis/domain_intelligence/*` (domain induction and updates)

- `src/francis/internet/validation/*` (recency + credibility)

- `src/francis/system_intelligence/probe/*` (profiling + drift events)





## 11. UI requirements



The Chat UI should make time explicit:



Must display:

- current date/time context (timezone-aware)

- evidence timestamps for web sources

- confidence penalties for stale sources

- pinned policy snapshot id

- trust state and recent changes

- drift timeline and last baseline check



Must support:

- “view as-of date” (replay mode)

- “show what changed since last session”

- “why is this blocked?” explanations referencing:

  - expirations

  - drift events

  - policy changes





## 12. Common failure modes and mitigations



### 12.1 Stale but confident answers

Mitigation:

- freshness class enforcement

- explicit recency validation with citations

- abstain or warn when freshness cannot be verified



### 12.2 Confusing event time with publish time

Mitigation:

- extract and store both fields

- heuristics for event-time parsing

- explain ambiguity when present



### 12.3 Temporal inconsistency across artifacts

Mitigation:

- consistent clock source (UTC in logs)

- time sync monitoring

- monotonic ordering checks in append-only logs



### 12.4 Policy drift breaks reproducibility

Mitigation:

- pin policy snapshot per session

- record policy hash in all decision artifacts

- require re-approval when relevant policy changed





## 13. Minimal recommended schemas (high level)



### 13.1 Temporal event record (JSONL)

```json

{

  "id": "evt_...",

  "event_time": "2026-01-01T12:00:00Z",

  "ingested_at": "2026-01-01T12:00:05Z",

  "type": "trust_change|drift|decision|approval|memory_update",

  "subject": "domain|system|user|connector",

  "severity": "green|yellow|red",

  "policy_snapshot_hash": "sha256:...",

  "evidence": [{"ref": "...", "kind": "tool|web|doc", "hash": "sha256:..."}],

  "payload": { "..." : "..." }

}



