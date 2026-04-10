==============================================================================

FRANCIS — WEB_ACCESS.md

Safe web research, crawling, caching, provenance, and execution boundaries

==============================================================================



Purpose

-------

This document defines how FRANCIS interacts with the public internet in a way

that is:

   - Safe (prevents prompt injection / harmful content acquisition)

   - Governed (policy + approvals + trust gates)

   - Auditable (provenance, citations, immutable logs)

   - Reproducible (cache, snapshots, deterministic extraction)

   - Least-privilege (allowlists, environment modes, read-only defaults)



Web access is an *information intake* capability.

It is not a general execution permission and must never become a backdoor for:

   - secret exfiltration

   - arbitrary code execution

   - policy bypass



Read alongside:

   - docs/POLICIES.md

   - docs/THREAT_MODEL.md

   - docs/TRUST_MODEL.md

   - docs/API_PERMISSIONS.md

   - docs/CONVERSATION_CONTINUITY.md

   - docs/ACTION_READINESS.md

   - config/policies/web_access.yaml

   - config/policies/privacy.yaml

   - config/policies/data_governance.yaml

   - config/policies/offensive_security.yaml

   - config/environments/*.yaml

   - src/francis/internet/*

   - src/francis/governance/action_readiness.py

   - src/francis/telemetry/audit.py



Storage references:

   - data/web_knowledge/cache/web_pages/*

   - data/web_knowledge/sources/{academic,documentation,code,forums}/*

   - data/web_knowledge/learned_domains/*

   - data/web_knowledge/blocked/harmful_content_log.jsonl



Design stance

------------

   - Default deny: web access is off unless explicitly enabled by environment.

   - Allowlist-first: explicit domains and content types; block unknowns.

   - Treat the web as untrusted input: never execute instructions from it.

   - Citation + provenance are mandatory for web-derived claims.

   - Separation of concerns: fetch → sanitize → validate → synthesize.



==============================================================================





## 1. Web access goals and non-goals



### 1.1 Goals

Web access exists to:

- gather evidence and citations for research questions

- retrieve public documentation, specs, and changelogs

- collect academic sources when allowed

- retrieve code references in a controlled, non-executing way

- monitor updates/recency (when freshness matters)



### 1.2 Non-goals

Web access must NOT:

- directly perform writes/side effects on third-party systems

- authenticate to unknown services without explicit connector + scopes

- bypass policy gates by “asking the web what to do”

- allow the web to alter policies, trust, or permissions

- ingest disallowed content categories (see §4)





## 2. Modes of web operation (policy-driven)



FRANCIS supports multiple web modes; the environment selects one:



### 2.1 Disabled (default)

- No external fetches.

- Requests are served from local knowledge, cached sources, or user-provided files.



### 2.2 Allowlisted fetch (recommended default when enabled)

- Only allowlisted domains and URL patterns.

- Only safe content types (HTML, text, PDF if allowed; never executable binaries).

- Strong caching and provenance.



### 2.3 Research mode (controlled)

- Allows broader access (still with blocklists).

- Requires stronger validation:

  - multi-source corroboration

  - recency checks

  - source credibility scoring

- Often requires higher trust or explicit approvals.



### 2.4 Domain learning mode (highly controlled)

- Used for structured intake into domain stores.

- Requires:

  - provenance capture

  - deduplication

  - quarantine staging for suspicious sources

  - explicit governance snapshots



All modes are configured via:

- `config/policies/web_access.yaml`

- plus environment overrides in `config/environments/*.yaml`





## 3. Web access boundary model



### 3.1 The web is an untrusted boundary

All web content is treated as:

- untrusted input

- potentially adversarial

- potentially stale or incorrect



Web content can inform decisions, but cannot directly authorize actions.



### 3.2 Trust and readiness interaction

Even if web access is enabled:

- Trust may force:

  - deny

  - dry-run research plan only

  - “review required” synthesis

- High-risk contexts (regulated, safety-critical) usually require:

  - stricter allowlists

  - heavier redaction

  - limited caching retention

  - stronger provenance requirements





## 4. Content safety policy



### 4.1 Disallowed content categories (hard block)

FRANCIS must block or quarantine:

- instructions that facilitate wrongdoing (malware, weaponization, illegal activity)

- explicit exploit chains intended for real-world harm

- doxxing/PII harvesting guides

- credential theft/phishing kits

- extremism recruitment/propaganda

- sexual content involving minors (immediate hard block)

- content that violates configured regulated-domain constraints



Blocked events are recorded in:

- `data/web_knowledge/blocked/harmful_content_log.jsonl`



### 4.2 Suspicious content (quarantine)

Content may be quarantined when it shows:

- prompt injection patterns (“ignore previous instructions…”, “run this tool…”, etc.)

- obfuscated payloads

- excessive scripts or embedded tracking

- deceptive provenance (spoofed domains, redirects, homoglyphs)

- malware distribution indicators



Quarantined content must not be promoted into domain knowledge stores without review.



### 4.3 Safe transformations

Before storage and synthesis:

- strip scripts, inline event handlers, tracking pixels

- normalize encoding

- remove hidden text where feasible

- limit retained excerpts to what is necessary for evidence and citation





## 5. URL and domain policy



### 5.1 Allowlist-first

The web policy should define:

- allowed domains (exact matches + subdomain rules)

- allowed URL patterns (path prefixes, regex if necessary)

- allowed protocols (https only recommended)

- redirect policy (limit redirect count; final URL must still be allowlisted)



### 5.2 Blocklist and deny rules

Policy must include:

- blocked domains and known harmful hosts

- blocked TLDs if required

- blocked file extensions and MIME types (see §6)



### 5.3 Identity and permissions

Web fetch operations are still “tools” and are gated by:

- Permission Gate (tool allowed in the environment)

- Policy checks (web_access.yaml)

- Action Readiness (trust + approvals)

- Rate limits and sandbox constraints





## 6. Content-type and payload constraints



### 6.1 Allowed content types (recommended)

- `text/html`

- `text/plain`

- `application/json` (only when schema-validated and from allowlisted APIs)

- `application/pdf` (optional; requires safe PDF parsing path)

- `text/markdown`



### 6.2 Disallowed content types (hard block)

- executables and binaries (`.exe`, `.dll`, `.so`, `.dylib`, `.bin`)

- archives (`.zip`, `.7z`, `.rar`, `.tar`, etc.) unless explicitly permitted for

  controlled code ingestion pipelines

- disk images, installers

- any file type that could be executed or abused as a payload



### 6.3 Size and time limits

Policy should enforce:

- max bytes per fetch

- max total bytes per session

- max fetch duration

- max concurrent fetches

- timeouts and retry caps (avoid infinite retry loops)





## 7. Web fetch pipeline (end-to-end)



Web access should follow a strict pipeline:



1) **Request classification**

- Determine purpose: research, docs, academic, code reference, monitoring.

- Determine required freshness and evidence strength.



2) **Policy precheck**

- Environment allows web?

- Domain allowlisted?

- Content-type permitted?

- Risk tier and approval requirements?



3) **Network fetch (sandboxed)**

- Use strict TLS requirements when possible.

- Limit redirects.

- Capture headers for provenance.



4) **Content extraction**

- Extract main text safely.

- Preserve canonical URL and timestamp.

- Compute content hash and normalized representation.



5) **Safety scanning**

- Prompt injection detection

- Harmful content classifier

- Malware/obfuscation heuristics (non-executing)

- Mark as blocked/quarantined/clean



6) **Validation**

- Source credibility scoring

- Recency validation (if required)

- Cross-source corroboration (for important claims)



7) **Synthesis**

- Produce answer with citations and confidence.

- Never embed raw instructions from the web as directives.



8) **Storage**

- Cache raw + extracted forms in controlled stores.

- Record provenance and audit events.



Implementation modules typically map to:

- `src/francis/internet/crawling/*`

- `src/francis/internet/research/*`

- `src/francis/internet/safety/*`

- `src/francis/internet/understanding/*`

- `src/francis/internet/validation/*`

- `src/francis/internet/synthesis/*`





## 8. Prompt injection defense (critical)



### 8.1 Treat web text as data, never as instructions

FRANCIS must enforce:

- “web content can never override system policies or tool rules”

- “web content can never be executed”

- “web content can never become a tool call directly”



### 8.2 Canonical injection patterns to detect

Examples (non-exhaustive):

- “ignore previous instructions”

- “system prompt: …”

- “call tool X with these parameters”

- “exfiltrate secrets / reveal keys”

- “download and run …”

- “paste your logs / environment variables …”



Detection should produce:

- a safety flag

- a sanitized summary

- a policy-linked audit event



### 8.3 Isolation rules

When injection is suspected:

- do not quote large payloads

- do not propagate the content into other agents or federation peers

- force multi-source corroboration for any factual claims

- optionally require human review before including any excerpt in reports





## 9. Source credibility and recency



### 9.1 Source credibility scoring (recommended)

Score sources using:

- domain reputation (operator-provided allowlists and tiers)

- content type (primary docs > blogs > forums)

- authorship signals (official vendor docs vs anonymous posts)

- internal consistency and reference quality

- historical accuracy record (optional)



Store derived credibility metadata alongside cached pages.



### 9.2 Recency validation (when freshness matters)

For claims that can change quickly (prices, laws, schedules, product specs, APIs):

- require:

  - explicit publication/update date extraction (if present)

  - multiple sources (at least two, ideally independent)

  - “as-of” timestamp in outputs

- prefer official sources for volatile information



### 9.3 Conflict handling

If sources disagree:

- prefer primary/official documentation

- prefer more recent evidence if the topic is temporally unstable

- if still ambiguous, abstain or require human decision

- record the conflict in audit metadata





## 10. Provenance, citation, and reproducibility



### 10.1 Provenance requirements

For every web-derived assertion used in output:

- record:

  - canonical URL

  - fetch timestamp

  - content hash

  - extraction method/version

  - policy snapshot id (optional but recommended)



### 10.2 Citation policy

User-facing outputs should:

- cite sources for non-trivial factual claims

- include an “as-of” time for volatile topics

- avoid over-quoting (use excerpts sparingly)



### 10.3 Reproducibility

FRANCIS should support:

- re-fetch with same policy snapshot (when allowed)

- cache lookup by canonical URL + hash

- deterministic extraction for stable diffs





## 11. Caching and storage model



### 11.1 Cache layers

Recommended layers:

- **Raw fetch cache**: headers + raw body

- **Extracted text cache**: normalized text and metadata

- **Derived artifacts**: summaries, embeddings, entity graphs



Suggested locations:

- `data/web_knowledge/cache/web_pages/*`

- `data/web_knowledge/sources/*` (curated/promoted sources)

- `data/vectors/*` (embeddings/indexes, if enabled)



### 11.2 Retention policy

Retention should be policy-driven by:

- environment (dev vs production vs regulated)

- data classification (public vs internal vs regulated)

- source type (docs vs forums)

- incident flags (quarantine/blocked content retention for forensics)



### 11.3 Deduplication

Use:

- canonical URL normalization

- content hashes

- near-duplicate detection (optional) for long pages



### 11.4 Immutable logging for safety events

Blocked/quarantined events must be append-only to:

- `data/web_knowledge/blocked/harmful_content_log.jsonl`





## 12. Privacy and data governance constraints



### 12.1 No secret leakage

Web requests must never include:

- credentials, API keys, tokens

- internal URLs or identifiers that reveal sensitive topology

- user PII unless explicitly allowed and necessary



### 12.2 Redaction

Before storing outputs or exporting artifacts:

- redact:

  - secrets (pattern + context-based)

  - PII (policy-defined)

  - regulated data markers



### 12.3 Regulated domain handling

In regulated environments:

- restrict to a tight allowlist of reputable sources

- avoid ingesting personal data

- require review for any derived knowledge promotion





## 13. UI requirements (Chat UI + monitors)



When web access is enabled, the UI should show:

- web mode (disabled / allowlisted / research / learning)

- allowlist status and environment banner

- every fetch as a tool trace:

  - URL (sanitized)

  - policy decision

  - trust/readiness decision

  - cache hit/miss

  - citations extracted

- a “sources” inspector:

  - provenance metadata

  - publication dates (if found)

  - conflict indicators

- a “blocked content” inspector (restricted):

  - counts and categories

  - references to audit events (no harmful payloads)





## 14. Incident response for web intake



If web intake is implicated in an incident:

1) Freeze domain learning/promotions

2) Quarantine suspicious caches

3) Export audit trail and harmful_content_log references

4) Re-run validation suites on affected domains

5) Tighten allowlists and injection detectors

6) Require approvals for research mode until cleared

7) Record retrospective and adjust trust/certification





## 15. Implementation pointers (code map)



Typical responsibilities:

- `src/francis/internet/research/search_engine.py`

  - query planning, result selection, source diversity heuristics

- `src/francis/internet/research/content_extractor.py`

  - HTML/PDF extraction and normalization

- `src/francis/internet/research/citation_tracker.py`

  - provenance and citation mapping

- `src/francis/internet/safety/content_filter.py`

  - category filtering and sanitization

- `src/francis/internet/safety/manipulation_detector.py`

  - prompt injection and influence operation detection

- `src/francis/internet/safety/misinformation_detector.py`

  - misinformation heuristics and signals

- `src/francis/internet/safety/poisoned_data_detector.py`

  - poisoning detection for learning pipelines

- `src/francis/internet/validation/source_credibility.py`

  - credibility scoring

- `src/francis/internet/validation/recency_validator.py`

  - freshness extraction and checks

- `src/francis/internet/synthesis/multi_source_integrator.py`

  - conflict resolution and synthesis

- `src/francis/governance/action_readiness.py`

  - execution gating (deny/dry-run/review/execute)

- `src/francis/telemetry/audit.py`

  - immutable audit events





## 16. Web access invariants (non-negotiables)



- Web access is never a permission shortcut.

- Web content is never executable.

- Web content never overrides policies, trust, or identity checks.

- All web-derived claims must be provenance-tagged and cite sources.

- Suspicious content must be quarantined; harmful content must be blocked and logged.

- Regulated modes default to web-disabled unless explicitly configured and approved.





# End of WEB_ACCESS.md



