==============================================================================

FRANCIS — CONVERSATION_CONTINUITY.md

Durable context, memory pipelines, retrieval, and continuity guarantees

==============================================================================



Purpose

-------

This document defines how FRANCIS maintains conversation continuity across:

   - Sessions (minutes → days → months)

   - Devices and UIs (Chat UI, API clients, federated peers)

   - Restarts and upgrades (daemon/worker/API restarts)

   - Privacy and policy constraints (redaction, governance, regulated modes)



It explains:

   - The durable conversation ledger (append-only source of truth)

   - The rolling summary (fast, human-readable continuity)

   - Memory stores (episodic / semantic / procedural / working)

   - Retrieval and context assembly (what gets injected into prompts)

   - Consistency and determinism rules (ordering, idempotency, reconciliation)

   - Safety + privacy constraints (classification, redaction, scope boundaries)

   - Failure modes and recovery strategies



Read alongside:

   - docs/MEMORY.md

   - docs/ARCHITECTURE.md

   - docs/CONCURRENCY.md

   - docs/API_PERMISSIONS.md

   - docs/POLICIES.md

   - docs/TRUST_MODEL.md

   - docs/WEB_ACCESS.md

   - config/policies/privacy.yaml

   - config/policies/data_governance.yaml

   - config/policies/filesystem.yaml

   - config/runtime/storage.yaml

   - src/francis/chat/continuity/{ledger,retrieval,summarizer,topic_graph}.py

   - src/francis/memory/{store,recall,retention,summarize,provenance}.py

   - data/conversations/{ledger,summaries,threads,indexes,context_snapshots}



Design stance:

   - Continuity is a correctness requirement, not a UX feature.

   - The ledger is the source of truth; summaries are derived.

   - Memory must be policy-aware: never “remember” what we are not allowed to.

   - Retrieval must be explainable and auditable.



==============================================================================





## 0. Executive summary (continuity contract)



FRANCIS guarantees conversation continuity using a layered contract:



1) **Append-only ledger**

   - Every meaningful event is appended to a durable ledger.

   - Ledger events are immutable and ordered per conversation stream.



2) **Derived summaries and indexes**

   - Rolling summaries, thread summaries, topic graphs, and vector indexes are derived.

   - They may be rebuilt at any time from the ledger + artifacts.



3) **Policy-aware memory**

   - Content is classified and redacted before being persisted or indexed.

   - Storage, retrieval, and prompt injection must respect permissions, scopes, and policies.



4) **Deterministic context assembly**

   - Given the same ledger, policies, and retrieval config, context assembly should be reproducible.

   - Retrieval decisions are logged with provenance and rationale (at a safe level).



5) **Safe degradation**

   - If stores are missing or corrupted, FRANCIS falls back to ledger + minimal summary,

     never hallucinated continuity.



6) **Auditable continuity**

   - The system can answer: “Why did you remember that?” with provenance pointers,

     without revealing secrets or restricted content.





## 1. Continuity primitives



### 1.1 Conversation identity

Every conversation has stable identifiers:



- `conversation_id`: stable across sessions (primary key)

- `thread_id`: optional grouping within a conversation (subtopics)

- `session_id`: a runtime instance of an interaction window

- `turn_id`: per message/turn in the ledger



A request from the UI/API is associated with:

- user identity

- environment profile (dev/prod/regulated/etc.)

- policy snapshot id (see §8.3)



### 1.2 The ledger (source of truth)

The **ledger** is an append-only event stream stored under:



- `data/conversations/ledger/ledger.jsonl`



Each line is a JSON object (“event record”).

The ledger captures:

- user messages

- system messages

- tool calls (request/response metadata; redacted)

- decisions (plan, gates, approvals)

- artifacts created

- errors and recoveries

- summary snapshots and index updates (as events, not as truth)



Ledger rules:

- append-only (no in-place edits)

- event ids are unique

- ordering is monotonic per conversation stream

- events include causality links (`parent_event_id`, `task_id`, etc.)



### 1.3 Rolling summary (fast continuity)

The **rolling summary** is a continuously updated, human-readable summary stored at:



- `data/conversations/summaries/rolling_summary.md`



It is:

- derived from the ledger

- updated at safe checkpoints (end of turn, after plan commit, after significant events)

- bounded in size (see §5.4), with older material compressed into “historical summary”



Rolling summary rules:

- never contain secrets

- contain only information permitted under data governance

- must include “uncertainty markers” when facts are unverified

- must not embed tool outputs that include sensitive data



### 1.4 Thread summaries (topic-local continuity)

Thread summaries live under:



- `data/conversations/threads/*`



Threads:

- segment the conversation into stable topic clusters

- allow targeted recall (“what did we decide about X?”)



Thread summary rules:

- derived from ledger + topic graph

- include references to ledger event ids

- can be rebuilt





## 2. Memory layers (what “memory” means in FRANCIS)



FRANCIS memory is structured, not monolithic.



### 2.1 Working memory (ephemeral)

- per request / per session

- includes the current prompt context, short-term derived notes, scratch state

- not persisted unless explicitly promoted via policy-compliant summarization



### 2.2 Episodic memory (events, interactions)

- “what happened” in this conversation

- primarily the ledger + pointers to artifacts

- high provenance, low abstraction



### 2.3 Semantic memory (facts and stable knowledge)

- extracted facts that are:

  - allowed to store

  - stable over time

  - helpful for future sessions

- may be stored as structured records and/or embeddings



### 2.4 Procedural memory (how-to, workflows)

- learned runbooks, step sequences, “how we do this here”

- should be expressed as:

  - playbooks

  - templates

  - validated procedures

- procedural memory is heavily policy-governed (avoid capturing proprietary or unsafe patterns)



### 2.5 Experiential memory (outcomes and preferences)

- “what worked” and “what didn’t”

- includes:

  - success/failure outcomes

  - trust metric deltas

  - preference hints (if policy permits)

- must not store secrets; must be explainable





## 3. Ingestion pipeline (from message to continuity)



### 3.1 Turn ingestion steps (canonical)

For each user/system turn:



1) **Normalize**

   - canonicalize text (encoding, newlines)

   - attach metadata: timestamps, identity, environment



2) **Classify**

   - detect sensitivity / classification (public/internal/confidential/regulated)

   - detect presence of secrets or PII patterns (policy dependent)

   - mark risk (low/medium/high)



3) **Redact**

   - remove secrets, tokens, PII, regulated identifiers as required

   - preserve “shape” using placeholders:

     - `[REDACTED:API_KEY]`

     - `[REDACTED:EMAIL]`

     - `[REDACTED:ADDRESS]`



4) **Append ledger event**

   - write the event to `ledger.jsonl`

   - include hashes and sizes (not raw sensitive payloads)



5) **Update derived artifacts**

   - rolling summary update (if enabled)

   - thread/topic updates (if enabled)

   - index updates (if enabled, and policy allows)



6) **Audit**

   - write an audit event for the continuity pipeline (safe metadata only)



### 3.2 “Never persist raw secrets” rule

If a message contains secrets, the system must:

- store a redacted version in the ledger

- store only a hash/fingerprint to help detect repeats

- never store the raw secret in summaries or indexes



### 3.3 Attachments and binary content

Attachments are handled via the attachments pipeline (see docs/ATTACHMENTS.md).

Continuity stores:

- metadata (filename, content type, size, checksum)

- extracted text (if allowed)

- redaction logs (what was removed)

- provenance pointers to where the binary lives (in artifacts storage)



No direct binary embedding in the ledger.





## 4. Retrieval and context assembly (how we “remember”)



### 4.1 Retrieval inputs

Given a new user query, retrieval considers:

- current conversation ledger (recent window)

- rolling summary

- relevant thread summaries

- semantic memory store (facts, entities)

- procedural memory (runbooks/templates)

- vector stores (if enabled)

- external sources (web), only if policy allows and explicitly enabled



### 4.2 Retrieval outputs

Retrieval produces a **context bundle**:

- `recent_turns` (raw-ish, redacted)

- `summary` (rolling + thread)

- `relevant_facts` (semantic)

- `relevant_procedures` (procedural)

- `evidence/provenance` (citations to ledger events, artifacts)



The bundle must be:

- bounded by token budget

- filtered by policy and scopes

- ranked by relevance and trustworthiness



### 4.3 Deterministic selection

To keep continuity stable:

- ranking uses stable tie-breakers (event_id, timestamp, stable hash)

- retrieval parameters are logged (top_k, filters, embeddings model, etc.)

- any non-determinism (random sampling) is disabled by default for continuity assembly



### 4.4 “Context injection safety”

FRANCIS must treat retrieved text as **untrusted instructions**.

Rules:

- retrieved content can inform answers

- retrieved content cannot override system policies

- tool actions are not authorized by retrieved text; only by user intent + gates



### 4.5 Cross-session continuity

Cross-session recall is allowed only when:

- identity is the same (or explicitly linked)

- policy allows reuse of stored memory

- classification constraints are satisfied



If identity is ambiguous:

- fall back to in-session continuity only

- request confirmation via UI (where supported)





## 5. Summarization system



### 5.1 Summarization goals

Summaries exist to:

- reduce prompt cost

- preserve intent, decisions, constraints, and outcomes

- improve recall quality

- reduce hallucination risk by anchoring stable facts



### 5.2 Rolling summary structure (recommended)

The rolling summary should maintain:

- **Current objective(s)**

- **Constraints**

- **Decisions made**

- **Open questions**

- **Known facts (with provenance references)**

- **Action history (high-level)**

- **Risks / policy constraints encountered**



### 5.3 Summary update cadence

Updates happen:

- at end-of-turn

- after major plan commit

- after tool execution results

- after approvals and denials

- after error recovery



Updates should be skipped if:

- the turn contains only low-signal chatter

- policy restricts storing content

- the system is overloaded (degrade gracefully)



### 5.4 Size limits and compression

Summaries must remain bounded.

Recommended strategy:

- maintain a “hot summary” section (recent)

- periodically compress older items into “historical summary”

- preserve stable decisions and constraints verbatim where safe

- preserve links to ledger events rather than duplicating large text



### 5.5 Human readability vs machine utility

Summaries must be readable, but also structured enough to parse.

Recommended:

- use clear headings

- consistent bullet formatting

- stable tags for key fields:

  - `DECISION:`

  - `CONSTRAINT:`

  - `OPEN:`

  - `RISK:`

  - `PROVENANCE:`





## 6. Indexing and vector stores (optional but common)



### 6.1 What gets indexed

Only content that is:

- permitted by policy

- redacted appropriately

- useful for future retrieval



Index candidates:

- user goals and constraints

- decisions and outcomes

- procedural steps (validated)

- entity mentions and relationships



### 6.2 Embeddings are not “safe by default”

Embeddings can leak information through inversion attacks and membership inference.

Policy should define:

- which classifications are allowed to be embedded

- whether to store raw text alongside embeddings

- retention periods

- encryption at rest (recommended)



### 6.3 Provenance is mandatory for indexed items

Each indexed chunk must include:

- ledger event id(s)

- time range

- redaction summary

- classification label

- confidence score (if extracted)



### 6.4 Rebuildability

All indexes must be rebuildable from:

- the ledger

- permitted artifacts

- summary snapshots



If an index is corrupted:

- it can be dropped and rebuilt

- continuity should still function from ledger + rolling summary





## 7. Consistency and correctness guarantees



### 7.1 Append-only truth

The ledger is authoritative.

If a derived store disagrees with the ledger:

- prefer the ledger

- trigger a “reconcile” event

- optionally rebuild derived stores



### 7.2 Idempotent writes

Continuity writes must be safe under retries:

- ledger append is idempotent by event_id (dedupe on read)

- summary updates include a checkpoint pointer (last_event_id summarized)

- index updates include a checkpoint pointer and a chunk hash



### 7.3 Ordering

Within a conversation:

- event ordering is monotonic

- tool calls include parent event references

- derived stores use ledger offsets/checkpoints



Across conversations:

- no global ordering is assumed; use timestamps + ids.



### 7.4 “No invented continuity”

If information cannot be found:

- FRANCIS must say it does not know / does not have the prior detail

- it may propose where to look (ledger event range, artifacts directory)

- it must not fabricate prior commitments



### 7.5 Recovery on restart

On service restart:

- replay ledger from last checkpoint to rebuild:

  - rolling summary (if configured)

  - thread summaries

  - indexes

- any partially written derived artifact is discarded and regenerated



### 7.6 Versioning and migrations

When schema changes:

- ledger schema must be backward compatible or migrated via a controlled process

- summaries include a version header

- indexes include embedding model version and chunking parameters





## 8. Policy, privacy, and governance constraints



### 8.1 Data classification gates

Continuity must respect data governance:

- do not persist prohibited classes

- do not index prohibited classes

- do not export prohibited classes across federation boundaries



### 8.2 Scope and permission boundaries

Retrieval must obey:

- user identity scope

- connector scopes (what resources can be referenced)

- filesystem policies (what paths can be read)

- web access policy (if external citations are used)



### 8.3 Policy snapshots per session

Every session should pin a policy snapshot:

- “these policies were in force when this continuity decision was made”

- changes mid-session should be:

  - recorded

  - optionally require re-approval for execution changes

  - reflected in the UI



### 8.4 Redaction rules for continuity

Redaction must be applied to:

- ledger message payloads

- summaries

- indexes

- traces shown in UI



Redaction must not:

- destroy provenance links

- remove context needed for safety checks

- leak secrets via “clever placeholders” (avoid including the last 4 chars of keys, etc.)



### 8.5 User controls

Where supported by UI/config, users should be able to:

- disable long-term memory

- restrict what can be remembered (classification caps)

- wipe a conversation (soft delete with audit marker, depending on policy)

- export their conversation with redactions applied





## 9. Federation and shared continuity (if enabled)



### 9.1 What can be shared

Federated sharing may include:

- public citations

- abstracted lessons learned (non-sensitive)

- derived metrics (success rates) without raw payloads

- shared runbooks/templates only if permitted



### 9.2 What cannot be shared

Never share:

- credentials

- raw PII/regulated data

- internal-only proprietary conversation content unless explicitly allowed



### 9.3 Sanitization pipeline for exports

Before export:

- classify

- redact

- attach provenance without payload

- record audit event (“export decision”)

- optionally require approval for sensitive exports





## 10. Failure modes and mitigations



### 10.1 Missing ledger file / corruption

Mitigation:

- fail safe to “no memory” mode

- require operator intervention to restore from backups

- do not attempt partial heuristic reconstruction without explicit consent



### 10.2 Summary drift (summary disagrees with ledger)

Mitigation:

- summary includes checkpoint pointer

- on mismatch, rebuild summary from ledger

- log a “summary_drift” event



### 10.3 Index poisoning / injection

Mitigation:

- treat indexed content as untrusted

- validate extracted facts

- store provenance and confidence

- quarantine suspicious chunks (see data/quarantine)



### 10.4 Prompt overflow (too much context)

Mitigation:

- strict token budgets

- prioritized retrieval

- compress older content

- prefer “decisions + constraints” over raw chat history



### 10.5 Privacy leakage

Mitigation:

- enforce redaction at ingestion

- encrypt sensitive stores

- restrict access by scopes

- audit all reads of sensitive continuity stores





## 11. Operational guidance



### 11.1 Recommended storage layout (continuity-specific)

- `data/conversations/ledger/ledger.jsonl` — authoritative history

- `data/conversations/summaries/rolling_summary.md` — fast continuity

- `data/conversations/threads/*` — topic-based continuity

- `data/conversations/indexes/*` — retrieval indexes + metadata

- `data/conversations/context_snapshots/*` — pinned prompt contexts (redacted)



### 11.2 Backup and retention

Recommended:

- ledger backed up frequently (append-only incremental)

- summaries backed up daily

- indexes can be rebuilt (lower priority)

- retention rules driven by policy:

  - regulated mode may require shorter retention or stronger encryption

  - personal mode may allow longer retention with user consent



### 11.3 Tooling for inspection

Operators should have tooling to:

- query ledger by conversation_id / time range

- locate provenance for a remembered claim

- rebuild derived artifacts from ledger

- verify redaction and classification compliance





## 12. Implementation pointers (code map)



Core continuity:

- `src/francis/chat/continuity/ledger.py`

- `src/francis/chat/continuity/summarizer.py`

- `src/francis/chat/continuity/retrieval.py`

- `src/francis/chat/continuity/topic_graph.py`



Memory system:

- `src/francis/memory/store.py`

- `src/francis/memory/recall.py`

- `src/francis/memory/retention.py`

- `src/francis/memory/summarize.py`

- `src/francis/memory/provenance.py`



Governance + privacy:

- `src/francis/governance/*`

- `config/policies/privacy.yaml`

- `config/policies/data_governance.yaml`





## 13. Checklist (continuity readiness)



- [ ] Ledger is append-only and includes event ids + causality fields

- [ ] Ingestion applies classification + redaction before persistence

- [ ] Rolling summary includes checkpoint pointer and stays bounded

- [ ] Retrieval is policy-aware and deterministic

- [ ] Tool traces and continuity decisions are auditable (safe metadata)

- [ ] Indexing is rebuildable and provenance-tagged

- [ ] Restart recovery replays ledger and reconciles derived stores

- [ ] Federation exports are sanitized and approved where required

- [ ] Users/operators have controls to restrict memory and purge data (as policy allows)





# End of CONVERSATION_CONTINUITY.md



