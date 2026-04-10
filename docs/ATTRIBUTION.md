==============================================================================

FRANCIS — ATTRIBUTION.md

Evidence attribution, provenance, citations, and anti-hallucination controls

==============================================================================



Purpose

-------

This document defines the attribution and evidence model for FRANCIS:

   - What counts as evidence and how it is tracked

   - How provenance is captured for all knowledge inputs

   - How citations are produced in responses and artifacts

   - How conflicts are handled (multi-source disagreement)

   - How uncertainty is communicated and logged

   - How attribution requirements interact with trust + approvals



Read alongside:

   - docs/POLICIES.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/WEB_ACCESS.md

   - docs/API_PERMISSIONS.md

   - docs/CONVERSATION_CONTINUITY.md

   - config/policies/data_governance.yaml

   - config/policies/privacy.yaml

   - config/policies/web_access.yaml

   - src/francis/explanation/transparency/evidence_citation.py

   - src/francis/internet/research/citation_tracker.py

   - src/francis/internet/research/fact_checker.py

   - src/francis/domain_intelligence/intake/provenance_capture.py



Design stance:

   - “No evidence” is a first-class state (must be surfaced explicitly).

   - Claims should be traceable to sources, segments, and timestamps.

   - When evidence is weak or conflicting, say so and downgrade confidence.

   - Prefer primary sources, and store enough metadata to re-verify later.



==============================================================================





## 0. Key principles



1) **Attribution is mandatory for non-trivial claims**

   - If a claim would matter to a decision, it needs evidence or it must be

     labeled as inference/speculation.



2) **Provenance always travels with content**

   - Every extracted segment includes where it came from, when it was obtained,

     which tool fetched it, and any transformations (redaction, parsing, etc.).



3) **Citations must be stable**

   - Citations reference durable identifiers, not fragile offsets.



4) **Conflicts are not “averaged away”**

   - Disagreement is preserved and surfaced with source-specific citations.



5) **Uncertainty is communicated**

   - Confidence is not hidden. “Unknown” is acceptable.



6) **Safety overrides completeness**

   - If citing or quoting would leak sensitive info, redact or refuse.





## 1. Definitions



**Evidence**: Any content used to support a claim, including:

- User-provided content (messages, attachments)

- System artifacts (logs, runbooks, configuration snapshots)

- External sources (web pages, academic papers, docs)

- Tool outputs (DB query results, API responses)



**Provenance**: Metadata that describes origin and handling:

- `source_type`: user | attachment | tool | web | artifact | system

- `source_id`: stable id (attachment_id, url hash, tool invocation id)

- `retrieved_at`: timestamp

- `transform_chain`: parsing, normalization, redaction steps

- `integrity`: hashes (sha256), ETags, commit SHAs where applicable



**Citation**: A compact, human-readable pointer to a provenance object.



**Claim**: A statement with truth value that can be contested.





## 2. Evidence taxonomy (what FRANCIS recognizes)



### 2.1 Primary sources (preferred)

- Official docs from the provider/vendor

- Standards/specs (IETF, W3C, ISO where appropriate)

- Direct API responses (with request parameters logged)

- Signed artifacts (releases, commits)



### 2.2 Secondary sources (use with caution)

- Blog posts

- Tutorials

- Forums/StackOverflow/Reddit

- News articles



### 2.3 Internal sources

- Conversation ledger

- Attachment store

- Domain intelligence sources

- Operational logs



Internal sources must still be:

- scoped correctly (no cross-workspace leaks)

- classified correctly (privacy/regulatory rules)





## 3. Provenance capture pipeline



### 3.1 When provenance is captured

Provenance is captured whenever content is:

- ingested (attachments)

- fetched (web/tool)

- generated (reports, runbooks, explanations)

- transformed (redaction, summarization, chunking)



### 3.2 Provenance record (recommended shape)



```json

{

  "provenance_id": "prov_01HXYZ...",

  "source_type": "web",

  "source_ref": {

    "url": "https://example.com/spec",

    "fetch_method": "http_connector.get",

    "request": { "headers": { "Accept": "text/html" } }

  },

  "retrieved_at": "2026-01-01T12:34:56Z",

  "integrity": {

    "sha256": "…",

    "etag": "\"abc\"",

    "last_modified": "Wed, 01 Jan 2026 10:00:00 GMT"

  },

  "classification": "public",

  "transform_chain": [

    "html_extract_v2",

    "normalize_whitespace",

    "chunk_v1"

  ],

  "policy_snapshot_ref": "pol_snapshot_…",

  "notes": "Primary vendor documentation"

}



