# Knowledge Fabric

## Purpose
The Knowledge Fabric is Francis's local evidence substrate: searchable, cited, and actionable context built from user artifacts. It exists to improve grounded decision quality across Presence, Missions, Forge, and Autonomy.

## Artifact Types
- Source repositories and commit history.
- Product docs, architecture docs, runbooks, and governance policies.
- Logs, incident records, and observer/anomaly outputs.
- Decisions journals, approvals, mission history, and run ledgers.
- Screenshots or captures that are explicitly opted in and scope-approved.

## Indexing Strategy
### Metadata Index
- Captures source path, timestamp, artifact type, scope, owner, and retention class.
- Supports precise filters for mode, mission, time window, and subsystem.

### Semantic Retrieval
- Builds embeddings/chunks over eligible artifacts for contextual lookup.
- Uses reranking plus policy filters before results are surfaced.

## Grounded Citations Requirement
- Every factual claim from retrieval must include local evidence references.
- Citations should identify artifact path/ID and relevant timestamp.
- If evidence is missing or stale, Francis must mark output as uncertain and avoid definitive claims.

## Retention Policy Concepts
- Durable records: mission history, approvals, decisions, ledgers.
- Rolling records: high-volume operational logs with time-window retention.
- Sensitive artifacts: redacted or sealed according to policy and scope.
- Retention settings remain user-controlled and policy-auditable.

## Acceptance Criteria Checklist
- [ ] Artifact ingestion enforces scope boundaries and provenance metadata.
- [ ] Retrieval returns citations for evidence-backed claims.
- [ ] Filters support mission/time/scope constrained search.
- [ ] Retention classes are explicit and configurable.
- [ ] Uncited claims are blocked or clearly marked uncertain.
