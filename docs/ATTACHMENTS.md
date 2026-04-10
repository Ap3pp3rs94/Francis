==============================================================================

FRANCIS — ATTACHMENTS.md

Attachment intake, parsing, indexing, redaction, and governance

==============================================================================



Purpose

-------

This document defines how FRANCIS handles user-supplied and system-supplied

attachments end-to-end, including:

   - Accepted formats and ingestion pathways

   - Storage layout and lifecycle (inbox → processed/redacted/rejected)

   - Parsing and normalization into canonical text/structured forms

   - Safety scanning, data classification, and redaction

   - Indexing and retrieval (with provenance + citations)

   - Policy gates (permissions, approvals, privacy, regulated domains)

   - Audit logging and traceability



Read alongside:

   - docs/POLICIES.md

   - docs/PRIVACY.md (if present) / config/policies/privacy.yaml

   - docs/THREAT_MODEL.md

   - docs/TRUST_MODEL.md

   - docs/API_PERMISSIONS.md

   - docs/WEB_ACCESS.md (for URL-based “attachments”)

   - docs/CONVERSATION_CONTINUITY.md



Key code references:

   - src/francis/chat/attachments/intake.py

   - src/francis/chat/attachments/parsers.py

   - src/francis/chat/attachments/indexing.py

   - src/francis/chat/attachments/redaction.py

   - src/francis/governance/*

   - src/francis/memory/*



Core stance:

   - Attachments are untrusted input.

   - Default to safety: scan → classify → redact → then index.

   - Do not leak secrets into model context.

   - Always preserve provenance and enable auditability.



==============================================================================





## 0. Definitions



**Attachment**: Any non-message payload ingested into a conversation context:

- user uploads (files)

- pasted blobs (treated as “inline attachments”)

- referenced artifacts (reports/runbooks)

- URL fetch results (when allowed) treated as “web attachments”



**Canonical representation**:

- `text/plain` for unstructured content

- JSON for structured content

- metadata describing source, time, author, classification, transformations



**Provenance**:

- Who provided it, when, how it was obtained

- Hashes for integrity

- Transform chain (parse steps, redactions, normalizations)





## 1. Goals and non-goals



### 1.1 Goals

- Safe ingestion of arbitrary user files in a predictable pipeline

- Deterministic parsing to canonical forms

- Redaction \& classification before model exposure

- Indexing for retrieval with strong citations

- Auditability (what we read, what we stored, what we referenced)

- Operate across environments (dev/prod/regulated/airgapped)



### 1.2 Non-goals

- Provide a “general file execution sandbox”

- Treat attachment content as trusted instructions

- Ingest secrets and make them available to the model without explicit policy





## 2. Attachment lifecycle (storage + states)



Attachments move through states and directories:



- **INBOX**: `data/uploads/inbox/`

  - raw user uploads or captured payloads

- **PROCESSED**: `data/uploads/processed/`

  - successfully parsed and normalized

- **REDACTED**: `data/uploads/redacted/`

  - sanitized derivative (PII/secrets removed)

- **REJECTED**: `data/uploads/rejected/`

  - rejected due to policy, scan, unsupported format, or safety



### 2.1 State machine



```text

receive → quarantine_scan → classify → (reject | accept)

accept → parse → normalize → redact(optional/required) → index → available_for_retrieval



