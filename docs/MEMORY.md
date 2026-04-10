==============================================================================

FRANCIS — MEMORY.md

Memory architecture, retention policy, provenance, retrieval, and safety

==============================================================================



Purpose

-------

This document defines how FRANCIS stores, retrieves, and governs “memory”:

   - What “memory” means in FRANCIS (and what it does NOT mean)

   - Memory layers (working, episodic, semantic, procedural, experiential)

   - Modalities (text, structured, web sources, audio/image/video)

   - Storage layout on disk + vector/graph indexes

   - Provenance, evidence, and citation requirements

   - Retention, expiration, redaction, right-to-forget, and legal holds

   - Retrieval pipeline (hybrid search + re-ranking + policy filtering)

   - Safety constraints (privacy, regulated data, injection/poisoning defense)

   - Federation-safe sharing rules (no secrets, no regulated payloads)

   - Operational guidance and deployment profiles



Read alongside:

   - docs/POLICIES.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/CONVERSATION_CONTINUITY.md

   - docs/API_PERMISSIONS.md

   - docs/WEB_ACCESS.md

   - docs/ATTACHMENTS.md

   - config/policies/privacy.yaml

   - config/policies/data_governance.yaml

   - config/policies/web_access.yaml

   - config/policies/trust_boundaries.yaml

   - config/policies/approvals.yaml

   - config/runtime/storage.yaml

   - src/francis/memory/*

   - src/francis/chat/continuity/*

   - src/francis/internet/* (web provenance + safety)

   - src/francis/telemetry/* (audit + trace)

   - data/memory/*

   - data/vectors/*

   - data/knowledge_graph/*

   - data/conversations/*



Design stance

------------

   - Memory is a capability multiplier and a liability multiplier.

   - Default to minimal retention; keep only what is necessary and provable.

   - Provenance is mandatory for durability: no provenance → no durable memory.

   - “Stored” does not mean “usable”: retrieval is policy-gated every time.

   - Never treat memory as authority. Permissions are enforced by governance.



==============================================================================





## 0. Executive summary



FRANCIS memory is a governed persistence layer for:

- continuity (conversations and decisions),

- knowledge (facts, entities, relationships),

- procedure (runbooks, workflows),

- and experience (what worked, what failed, performance signals),



…while enforcing:

- provenance (where it came from),

- retention (how long it stays),

- classification (how sensitive it is),

- and access controls (who can retrieve it and for what purpose).



The overall goal is **safe continuity**: better outcomes over time without

turning the system into an uncontrolled data sink.





## 1. Definitions



### 1.1 Memory (in FRANCIS)

**Memory** is any persisted representation of information that can influence

future behavior: responses, plans, tool selection, or execution.



Memory may include:

- conversation-derived summaries and key decisions

- extracted facts with evidence references

- structured outputs from tools (sanitized)

- runbooks and playbooks

- performance outcomes and reliability signals

- vector embeddings and indexes (derived artifacts)



### 1.2 What memory is NOT

Memory is not:

- a source of truth by itself

- a substitute for up-to-date verification

- an authorization layer (no memory can grant tool permissions)

- a secret vault (secrets belong in the credential vault)

- “training” (persistence does not imply model weight updates)



### 1.3 Durable vs transient

- **Transient memory**: session-scoped context (default).

- **Durable memory**: stored across sessions (explicit and governed).



Rule: durable memory requires explicit classification, provenance, and a

retention policy.





## 2. Memory layers (conceptual model)



FRANCIS organizes memory into layers with different value/risk tradeoffs:



### 2.1 Working memory (ephemeral)

- request/session scoped

- includes immediate context, intermediate state, scratch artifacts

- should not be persisted unless explicitly configured for debugging



Typical risks:

- may contain secrets/PII transiently

- may contain untrusted input (prompt injection payloads)



### 2.2 Episodic memory (what happened)

- time-indexed events: conversations, approvals, decisions, incidents

- ties every entry to provenance and a timeline



Examples:

- “User requested X; system executed Y; approval Z granted; result R.”



### 2.3 Semantic memory (what is believed true)

- facts, entity records, normalized knowledge

- always includes provenance + recency/validity metadata

- supports conflict tracking (multiple sources, disagreements)



### 2.4 Procedural memory (how to do it)

- runbooks, workflows, step sequences with safety checks

- should encode constraints (“only in dev”, “requires approval”, “dry-run first”)



### 2.5 Experiential memory (what worked before)

- outcomes, error patterns, performance profiles

- used to improve routing/recommendations and reduce repeat failures

- must not silently override policy or trust decisions



Note: experiential signals may inform trust metrics but cannot bypass governance.





## 3. Memory modalities (what can be stored)



FRANCIS supports memory modalities via `src/francis/memory/modalities/*`:



### 3.1 Text

- chat messages (as raw threads)

- summaries

- runbooks and notes



### 3.2 Structured

- JSON/YAML records derived from tools or ingestion

- KB entity records and relationship edges

- policy-safe normalized forms



### 3.3 Web sources

- “web source records” containing:

  - retrieval timestamp

  - canonical URL

  - content hash

  - extracted claims

  - safety classification

  - conflict markers



### 3.4 Media-derived

- audio/image/video typically stored as:

  - transcripts

  - derived descriptors

  - embeddings (if allowed)

- raw media persistence is off by default and must be explicitly enabled



Rule: media-derived memory is considered high-risk by default due to latent PII.





## 4. Storage layout and directories (practical mapping)



### 4.1 Conversations

- `data/conversations/threads/`

  - canonical persisted conversation thread objects

- `data/conversations/ledger/ledger.jsonl`

  - append-only event record (tool calls, approvals, decisions, key transitions)

- `data/conversations/summaries/rolling_summary.md`

  - auto-updated rolling summary for continuity

- `data/conversations/indexes/`

  - derived indexes (keyword, vector pointers, topic graph caches)

- `data/conversations/context_snapshots/`

  - pinned snapshots used for reproducibility and audit



### 4.2 Memory layer roots

- `data/memory/working/`

  - optional ephemeral spillover (MUST be TTL-managed)

- `data/memory/episodic/`

  - curated episode records beyond raw threads

- `data/memory/semantic/`

  - normalized facts, entity assertions, validated claims

- `data/memory/procedural/`

  - runbooks, procedures, playbooks

- `data/memory/experiential/`

  - outcomes, error patterns, performance data



### 4.3 Vector data

- `data/vectors/embeddings_cache/`

  - cache of embeddings for dedup + latency reduction (bounded; purgeable)

- `data/vectors/indexes/`

  - vector indexes (FAISS) or index metadata (Qdrant/pgvector)

- `data/vectors/stores/`

  - backend store data (if embedded) or config pointers



### 4.4 Knowledge graph

- `data/knowledge_graph/entities/`

- `data/knowledge_graph/relationships/`

- `data/knowledge_graph/ontologies/`

- `data/knowledge_graph/causal/`

- `data/knowledge_graph/temporal/`



### 4.5 Logs as memory sources

Raw logs are inputs to experiential memory but are not automatically “knowledge”:

- `data/logs/*`

- `data/trust/*`

- `data/evolution/*`





## 5. Memory object model (minimum schemas)



Memory should be machine-checkable. Recommended universal envelope:



### 5.1 Minimum envelope fields

- `memory_id` (stable identifier)

- `created_at` / `updated_at`

- `layer` (working/episodic/semantic/procedural/experiential)

- `modality` (text/structured/web_sources/audio/image/video)

- `created_by` (identity + role context)

- `classification` (public/internal/confidential/regulated)

- `retention_policy` (ttl, review, deletion triggers)

- `provenance` (source type + reference + hashes)

- `content` (payload)

- `confidence` (0..1) + rationale

- `validity` (valid_from / valid_until or recency metadata)

- `tags` (domain, topic, project, safety flags)



### 5.2 Provenance is mandatory for durability

If `provenance.source_type` is missing or unverifiable:

- do not promote to durable semantic/procedural memory

- keep as transient context only (or quarantine it)



### 5.3 Canonicalization for hashing

For consistent deduplication and integrity checks:

- normalize JSON keys order

- normalize whitespace for text (where safe)

- store `content_hash` over the canonical representation





## 6. Provenance and evidence requirements



### 6.1 Why provenance is non-negotiable

Without provenance, memory becomes:

- an error amplifier,

- a compliance hazard,

- and un-auditable.



Therefore: **no durable memory without provenance**.



### 6.2 Provenance minimum fields

- `source_type`: `conversation | tool | web | attachment | import | system`

- `source_ref`: pointer (thread id, tool trace id, file hash, web_source_id)

- `retrieved_at`: timestamp

- `content_hash`: hash of original/normalized payload

- `transformations`: list of transforms (redaction, summarization, extraction)

- `policy_snapshot`: policy version/hash used at time of write (recommended)



### 6.3 Evidence vs instruction separation

Memory ingestion must separate:

- “facts/claims” (candidate knowledge)

from

- “instructions” (untrusted and never stored as authoritative directives)



Policy:

- do not store “do X next time” as trusted procedural memory unless it is a

  human-authored runbook or explicitly approved template.





## 7. Write path (how memory is created)



### 7.1 Write pipeline (recommended)

1) **Classify input**

   - sensitivity (PII, regulated, secrets)

   - trust level (tool output vs web content vs user free text)

2) **Sanitize**

   - redact secrets and prohibited fields

   - normalize structure

3) **Attach provenance**

   - source ref, timestamps, hashes, transformation log

4) **Assign retention policy**

   - TTL, review cadence, deletion triggers

5) **Store payload**

   - correct layer directory

   - encrypt-at-rest if classification demands

6) **Index derived artifacts**

   - embeddings (if allowed)

   - keyword index entries

   - knowledge graph edges (if semantic)

7) **Audit**

   - write a memory-write audit event (no sensitive payload leakage)



### 7.2 Promotion rules (strong default)

Promoting content to *semantic* or *procedural* memory requires:

- provenance

- non-regulated classification (or explicit regulated-mode approval)

- pass of injection/poisoning heuristics

- optional human review for high-impact procedures



### 7.3 Quarantine rules

If content triggers:

- secret detection failures,

- malicious instruction patterns,

- unsupported classification,

- or provenance gaps,



store only in quarantine (or keep transient only), and log:

- `data/quarantine/*` (if configured)

- an audit event explaining why it was blocked





## 8. Read path (retrieval and ranking)



### 8.1 Core retrieval principles

Retrieval must be:

- minimal (least data necessary)

- relevant (task-aware)

- safe (policy-gated)

- auditable (traceable influence)



### 8.2 Retrieval pipeline (recommended)

1) **Request classification**

   - determine whether retrieval is allowed (privacy/trust boundaries)

2) **Store selection**

   - episodic vs semantic vs procedural vs experiential

3) **Hybrid search**

   - keyword + vector + graph pointers (as configured)

4) **Re-ranking**

   - relevance score

   - provenance quality

   - recency/validity

   - trust weight

5) **Policy filtering**

   - remove disallowed classifications

   - apply data governance rules

6) **Redaction-on-read**

   - apply outbound redaction rules

7) **Assembly**

   - return minimal excerpts + references

8) **Audit**

   - log retrieval event (memory ids, scores, filters applied)



### 8.3 Memory influence logging

When memory influences outputs or decisions, record:

- memory ids used

- type of influence (facts, preference, procedure, experience)

- confidence/recency notes

- policy checks applied



This supports “explainability” without leaking private content.





## 9. Retention, expiration, deletion



### 9.1 Retention objectives

Retention balances:

- usefulness (continuity, reduced repetition)

- risk (privacy, regulated data, secrets, exfiltration)

- cost (storage/index maintenance)



Default posture:

- store summaries and structured facts with provenance

- avoid retaining raw unbounded payloads



### 9.2 TTL + review cadence

Every durable memory category should specify:

- `ttl_days`

- `review_days` (how often to re-verify)

- `valid_until` for time-sensitive facts

- `refresh_strategy` (re-check via tool/web, or mark stale)



### 9.3 Right-to-forget and deletion completeness

Deletion must remove:

- the payload

- derived embeddings

- index entries

- cached summaries

- any export artifacts (if applicable)



Recommended deletion flow:

1) enumerate memory ids and derived artifacts

2) delete payloads

3) purge embeddings_cache entries

4) tombstone + compact or rebuild indexes

5) write audit record with deletion scope and result



### 9.4 Legal holds

If legal holds are supported, they must be explicit and auditable:

- legal hold prevents deletion of specified records

- legal hold metadata must not expose sensitive payloads

- legal holds should be restricted to regulated deployments only





## 10. Redaction and classification



### 10.1 Classification levels (illustrative)

- `public`

- `internal`

- `confidential`

- `regulated`



Classification determines:

- storage location eligibility

- encryption requirements

- retrieval eligibility

- export/federation eligibility



### 10.2 Redaction categories (illustrative)

- secrets (API keys, tokens, passwords)

- credentials and session cookies

- PII (emails, addresses, phone, SSNs)

- regulated identifiers (health/financial identifiers)

- internal-only identifiers (infrastructure topology, access tokens)



### 10.3 Deterministic redaction

Redaction should be:

- deterministic (same input → same redaction result)

- logged by category counts, not raw redacted text

- applied both on write and on read



### 10.4 No secrets in memory by default

Storing secrets requires:

- explicit policy allowance

- encrypted-at-rest storage

- separation from conversational memory

- explicit approval flows (recommended)



Otherwise, secrets must be stored only in the vault subsystem.





## 11. Safety: memory-specific threat model



Memory introduces unique threats beyond “normal prompting”.



### 11.1 Prompt injection persistence

Threat:

- malicious text is ingested and later retrieved as if it were guidance

Mitigations:

- separate facts from instructions

- store normalized claims, not raw instruction payloads

- quarantine untrusted content

- retrieval-time “instruction stripping” for untrusted sources

- never allow retrieved content to directly trigger tool execution without

  governance checks



### 11.2 Data poisoning (semantic)

Threat:

- attacker injects false “facts” into semantic memory

Mitigations:

- provenance required

- confidence + recency required

- conflict tracking (multiple sources)

- prefer tool traces / primary sources

- periodic review for sensitive domains

- trust-weighted sources



### 11.3 Embedding poisoning (vector)

Threat:

- attacker crafts text to dominate retrieval results

Mitigations:

- hybrid retrieval with keyword/graph cross-checks

- anomaly detection on embedding similarity distributions

- per-source caps during retrieval

- recency/provenance weighting

- quarantining suspicious sources



### 11.4 Privacy leakage via retrieval

Threat:

- system retrieves and exposes sensitive memory unnecessarily

Mitigations:

- policy filtering by classification

- least-privilege retrieval (task-scoped)

- redaction-on-read

- audit traces for retrieval usage



### 11.5 Model inversion / membership inference (operational)

Threat:

- sensitive text in embeddings could be indirectly inferred

Mitigations:

- do not embed regulated content by default

- isolate embeddings per classification

- purge embeddings on deletion

- restrict export of embeddings across federation





## 12. Encryption and access controls



### 12.1 Encryption at rest (recommended)

- confidential/regulated memory MUST be encrypted at rest

- encryption keys MUST be managed outside memory stores (vault or OS keystore)

- encryption metadata should support rotation



### 12.2 Access controls

Memory retrieval should respect:

- identity (user vs service)

- scopes and delegations (for tool-derived memory access)

- environment mode (regulated/airgapped)

- trust gating and approvals for sensitive retrieval actions



Key rule:

- “This exists on disk” ≠ “This can be retrieved into prompts.”



### 12.3 Separation from credential vault

Credential material must never be stored alongside normal memory.

`data/credentials/vault.db` is a separate subsystem with stricter controls.





## 13. Federation and sharing



### 13.1 What can be shared

Allowable exports (policy-dependent):

- public web source citations (metadata + hashes)

- sanitized lessons learned (no secrets, no PII)

- non-sensitive runbooks/templates

- aggregate performance metrics



### 13.2 What must never be shared

- raw credentials

- raw PII

- regulated payloads

- internal-only documents unless explicitly authorized

- proprietary material unless policy explicitly permits



### 13.3 Export/import envelope

Federation transfers must include:

- provenance envelope

- sanitization summary

- policy decision snapshot

- audit event references





## 14. Operational guidance



### 14.1 Recommended defaults (general)

- keep conversation ledger and rolling summaries

- store semantic facts only with provenance

- keep embeddings_cache bounded and purgeable

- do not store raw media; store transcripts/descriptors only if approved

- disable federation export by default



### 14.2 Regulated mode defaults

- minimal retention

- no web ingestion unless explicitly approved

- strict classification + encryption

- retrieval requires additional trust threshold and/or approvals

- aggressive deletion and index compaction schedules



### 14.3 Dev mode defaults

- allow verbose audit traces (still redact secrets)

- keep retention short to avoid “dev memory pollution”

- prefer local-only storage unless explicitly configured





## 15. Implementation map (code pointers)



### 15.1 Core memory modules

- `src/francis/memory/store.py` — storage interface + implementations

- `src/francis/memory/schema.py` — memory schemas and validation

- `src/francis/memory/provenance.py` — provenance envelopes

- `src/francis/memory/recall.py` — retrieval orchestration

- `src/francis/memory/retention.py` — TTL, purge, deletion workflows

- `src/francis/memory/summarize.py` — summarization and compression



### 15.2 Vector stores

- `src/francis/memory/vectorstores/base.py`

- `src/francis/memory/vectorstores/faiss_store.py`

- `src/francis/memory/vectorstores/qdrant_store.py`

- `src/francis/memory/vectorstores/pgvector_store.py`



### 15.3 Conversation continuity

- `src/francis/chat/continuity/ledger.py`

- `src/francis/chat/continuity/summarizer.py`

- `src/francis/chat/continuity/retrieval.py`

- `src/francis/chat/continuity/topic_graph.py`



### 15.4 Attachment integration (redaction + parsing)

- `src/francis/chat/attachments/parsers.py`

- `src/francis/chat/attachments/redaction.py`

- `src/francis/chat/attachments/indexing.py`





## 16. Example: durable semantic memory record (illustrative)



```json

{

  "memory_id": "mem_2026_01_01_000123",

  "created_at": "2026-01-01T12:34:56Z",

  "updated_at": "2026-01-01T12:34:56Z",

  "layer": "semantic",

  "modality": "structured",

  "created_by": { "identity": "user:operator", "role": "operator" },

  "classification": "internal",

  "content": {

    "type": "claim",

    "entity": "FRANCIS",

    "claim": "Tool execution is gated by permissions and trust/approvals.",

    "confidence": 0.92,

    "notes": "Derived from design docs; verify against current policies at runtime."

  },

  "provenance": {

    "source_type": "document",

    "source_ref": "docs/API_PERMISSIONS.md",

    "retrieved_at": "2026-01-01T12:34:56Z",

    "content_hash": "sha256:...",

    "transformations": ["normalized", "structured_extraction"],

    "policy_snapshot": "sha256:policy_bundle_hash..."

  },

  "validity": {

    "valid_from": "2026-01-01T00:00:00Z",

    "valid_until": "2026-06-30T00:00:00Z",

    "review_days": 30

  },

  "retention_policy": {

    "ttl_days": 180,

    "delete_on_user_request": true

  },

  "tags": ["architecture", "governance", "permissions"]

}



