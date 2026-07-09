# ADR 0003: Francis Compute Substrate Store Policy

Date: 2026-07-09

Status: Accepted for local durable store policy baseline

## Context

The Francis Compute Substrate now has internal/local-dev API routes for submission, status readback, receipt readback, and bounded capability discovery. The governed path uses local JSON stores for durable approval grants, compute capability receipts, and compute task status records when configured through the existing Francis data-root pattern.

These stores are useful local durability boundaries, but they are not production audit infrastructure, not distributed coordination, and not a backup system. Francis must keep that distinction explicit before adding VM/container backends, real adapters, production API exposure, or multi-process execution.

## Decision

Compute Substrate approval, receipt, and status stores must resolve through the configured Francis runtime data root, normally `FRANCIS_DATA_DIR` or the repo's existing data-dir helper. Source code must not hardcode USB drive paths, `D:\Francis` runtime paths, user profile paths, or global writable directories for these stores.

The local JSON stores are local durability only:

- `LocalJsonComputeApprovalStore` persists bounded approval grants and consumption truth.
- `LocalJsonComputeReceiptStore` persists bounded compute capability receipts.
- `LocalJsonComputeStatusStore` persists bounded compute task status records.

The stores must remain separate. Approval persistence proves why Francis was allowed to attempt execution. Capability receipts prove what happened. Status records report bounded task truth for readback. One store must not silently stand in for another.

## Runtime Data Root

The runtime data root is an operational input, not a repository constant. Tests must use temporary data roots. Local development may use a repo-local or operator-configured data root. USB-hosted code does not mean runtime data is automatically backed up or production durable.

Rules:

- no hardcoded USB storage path
- no hardcoded `D:\Francis` runtime data path
- no hardcoded user profile store root
- no broad filesystem writes outside configured store roots
- store roots must be bounded, resolved, and permissioned
- unsafe IDs must fail before path construction
- path traversal must not be normalized into aliases

## Retention And Cleanup

Retention and cleanup are not implemented by the current API routes or stores.

Until a later governance-reviewed slice adds explicit retention behavior:

- API routes must not delete approval, receipt, or status records.
- API routes must not compact or rewrite stores as a side effect of readback.
- Readback routes must not create fake retention, archival, recovery, or cleanup signals.
- Old records remain subject to local disk/operator management.

Future retention work must define record classes, retention windows, deletion authority, receipt behavior for cleanup, failure semantics, and validation before implementation.

## Backup And USB Operational Honesty

The repository is GitHub-anchored and may be hosted on a USB drive, but runtime data under `FRANCIS_DATA_DIR` has a separate backup problem.

Current posture:

- Git commits and pushes anchor source code to GitHub.
- Local JSON stores anchor bounded runtime evidence locally.
- Local runtime evidence is not automatically backed up by a git push.
- Backup policy is separate from API route implementation.
- No current API route claims backup, replication, remote audit durability, or disaster recovery.

Future backup work must define where runtime data is copied, how integrity is checked, how secrets are protected, how restore works, and what receipt proves the backup operation.

## Corruption And Read Failure Handling

Store readback must preserve truth without leaking sensitive details.

Requirements:

- missing safe IDs return bounded not-found responses
- unsafe IDs fail closed before filesystem access
- corrupt or undecodable receipt files should be distinguishable from not-found when the store exposes that distinction
- read failures must be represented with bounded stable errors
- responses must not include tracebacks, absolute paths, raw JSON contents, raw task payloads, raw execution outputs, approval-note secrets, model prompts, or broad filesystem paths

Corruption handling does not imply repair, recovery, rollback, or resume. Any future repair path requires a separate governance-reviewed contract.

## Concurrency And Production Limits

Current local JSON stores provide sequential local durability only. They do not implement:

- distributed locking
- cross-process approval reservation
- multi-process status coordination
- multi-process receipt coordination
- production-grade audit durability
- database transactions
- remote replication
- queue recovery
- task resume

Production or multi-process API use requires future reservation and coordination semantics before approval-required work can be treated as production safe.

## Logging And Redaction

Store records and readback responses must remain bounded. They must not become a side channel for sensitive content.

Default exclusions:

- raw `TaskEnvelope.payload`
- raw execution output
- secrets
- raw approval notes
- raw model prompts
- raw adapter metadata
- raw logs
- broad filesystem paths
- tracebacks and full exception details

If a future slice needs to persist more detail, it must define field-level redaction, retention, access scope, and receipt semantics first.

## Non-Goals

This ADR does not implement:

- new API routes
- source-code behavior changes
- retention or cleanup jobs
- backup or restore
- distributed locking
- cross-process approval reservation
- database-backed stores
- production audit authority
- adapter implementation
- async/background execution
- recovery or resumability
- OS-level CPU or memory enforcement
- memory persistence
- live-learning persistence
- model training

## Consequences

Francis can use local JSON approval, receipt, and status stores as bounded local evidence while staying honest about their limits. Future VM/container, adapter, production API, and multi-process work must treat store policy as an explicit dependency rather than assuming local files are sufficient production infrastructure.
