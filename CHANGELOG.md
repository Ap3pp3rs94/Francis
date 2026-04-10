# Changelog — Francis 2.0



All notable changes to this project will be documented in this file.



This changelog follows a **SemVer-aligned** and **operator-first** format:



- **Added**: new features/capabilities

- **Changed**: behavior changes, refactors, config changes

- **Deprecated**: still works, but will be removed later

- **Removed**: deleted features/files/endpoints

- **Fixed**: bug fixes

- **Security**: security fixes, policy tightening, secret-handling changes



> **Phase 2 note:** During Phase 2 (file-by-file implementation), entries may be frequent and granular.

> The goal is traceability without noise. Prefer grouping by subsystem and calling out operator impact.



---



## [Unreleased]



### Added

- (placeholder) Phase 2 implementation cadence established: one file at a time, conical dependency order.

- (placeholder) Operator-grade entrypoints for API/daemon/workers (thin wrappers, deterministic config precedence).



### Changed

- (placeholder) Repository hygiene and environment surfaces standardized.



### Fixed

- (placeholder) Build/format consistency issues and early boot edge cases as they are discovered.



### Security

- (placeholder) Explicit “no secrets in UI” posture documented and enforced in UI client design.



---



## [0.3.1] — 2025-12-29



> **Release focus:** UI install + Vite dev server readiness; baseline runtime verification.



### Added

- Chat UI dependency baseline established (React 18, Vite 5, TypeScript 5.9).

- Initial operator console scaffolding for chat + ledger + approvals.



### Fixed

- Dependency installation workflow validated via `npm install` and `npm ci`.



### Security

- Identified `npm audit` report: `esbuild <=0.24.2` vulnerability reachable via Vite dev server in affected ranges.

  - **Operator impact:** primarily affects **dev server exposure**; mitigate by binding to loopback and avoiding LAN exposure.

  - **Upgrade path:** `npm audit fix --force` suggests Vite major upgrade (breaking). Deferred until compatibility review.



---



## [0.3.0] — 2025-12-XX



> **Release focus:** Mega-tree bootstrap complete; services run locally.



### Added

- Mega-tree bootstrap completed and verified.

- Baseline services confirmed runnable locally:

  - `python -m francis api`

  - `python -m francis daemon`

- Ledger + logging confirmed (continuity + observability baseline).



---



## Changelog Maintenance Rules



### 1) Entry requirements

Every entry should include:

- **What changed**

- **Why it matters** (operator/developer impact)

- **Risk level** if applicable (Low/Medium/High)

- **Migration notes** if breaking



### 2) Breaking change format

When a change breaks compatibility, include:



- **BREAKING:** description

- **Migration:** exact steps

- **Rollback:** what to revert and what state may be impacted



Example:



- **BREAKING:** Renamed `FRANCIS_API_PORT` → `FRANCIS_API_HTTP_PORT`

- **Migration:** update `.env` and deployment manifests

- **Rollback:** restore old variable and restart services



### 3) Security entries

Security entries must include:

- vulnerability or risk summary

- affected surfaces (API, UI, daemon, workers)

- mitigations (immediate + long-term)

- whether secrets/state were at risk



### 4) Date format

Use ISO-style dates: `YYYY-MM-DD`.



### 5) Versioning

- Pre-1.0: minor bumps may include breaking changes (still must be flagged).

- Post-1.0: follow SemVer strictly.



---



## Links (optional, future)

- Releases: (link later)

- Issues: (link later)

- Architecture docs: `docs/ARCHITECTURE.md`

- Build order: `docs/BUILD_ORDER.md`

- Governance: `docs/GOVERNANCE.md`



